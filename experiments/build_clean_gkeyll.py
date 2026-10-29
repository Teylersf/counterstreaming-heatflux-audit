"""Reproduce the isolated clean9663 build from byte-pinned public artifacts.

Default action is a read-only plan. Downloads require explicit 'fetch'; prefix
creation requires 'prepare'; compilation/install/API probe requires 'build'.
No action launches a simulation, changes a system runtime or edits model code.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '9663ea594e80f68eb305378e14512db390440e6b'
SOURCE = {'filename': 'gkyl-' + COMMIT + '.tar.gz', 'bytes': 30034051,
    'sha256': '28a23b3729f6d79c6351fca444db7866f039e8e2d01b220e81d009c5486af588',
    'url': 'https://codeload.github.com/liangwang0734/gkyl/tar.gz/' + COMMIT}
BOOTSTRAP = {'filename': 'micromamba-linux-64-latest.tar.bz2', 'bytes': 7317886,
    'sha256': '9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b',
    'url': 'https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.10.0-0.tar.bz2'}
OBSERVED_EXE = '8207720b3fa7a1fee47041374b8e6935b7f51cb1792a9875e1d239922e1f32d7'
PACKAGE_LOCK_SHA256 = '486c0ddcb4b06333365eb14f767a10430bf5f32207fdf1dbdccd3669456f4232'
REFERENCE_MANIFEST_SHA256 = 'a29f66bbf1c0651d58d748e85cb9350490bfbb1b146bd44cdd6c3e574695d8f3'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def checked(path, entry):
    require(path.is_file(), 'Missing pinned artifact: ' + str(path))
    require(path.stat().st_size == entry['bytes'], 'Wrong artifact size: ' + path.name)
    for algorithm in ('sha256', 'md5'):
        if entry.get(algorithm):
            require(sha(path, algorithm) == entry[algorithm], 'Wrong ' + algorithm + ': ' + path.name)


def artifact_paths(args, packages):
    return [(args.cache_root / SOURCE['filename'], SOURCE),
            (args.cache_root / BOOTSTRAP['filename'], BOOTSTRAP)] + [
                (args.cache_root / 'compiler-packages' / p['filename'], p) for p in packages]


def fetch_all(artifacts):
    # Deliberately serial, with no mirror, version or dependency substitution.
    for path, entry in artifacts:
        if path.exists():
            checked(path, entry)
            continue
        require(entry['url'].startswith('https://'), 'Only pinned HTTPS artifacts are fetched')
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + '.partial')
        with partial.open('xb') as output:
            with urllib.request.urlopen(entry['url'], timeout=60) as response:
                received = 0
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    received += len(block)
                    require(received <= entry['bytes'], 'Transfer exceeds pinned size: ' + path.name)
                    output.write(block)
        checked(partial, entry)
        require(not path.exists(), 'Destination appeared during transfer; refusing overwrite')
        partial.rename(path)


def source_audit(source, expected):
    require(len(expected) == 1998, 'Expected the published 1,998-file native/Lua source manifest')
    changed = [name for name, digest in expected.items()
               if not (source / name).is_file() or sha(source / name) != digest]
    require(not changed, 'Original native/Lua source differs: ' + ', '.join(changed[:5]))
    return {'source_files_checked': len(expected), 'original_source_files_changed': []}


def run_logged(argv, cwd, env, log, separate_stderr=False):
    started = time.monotonic()
    stderr_path = log.with_name(log.stem + '.stderr.txt')
    with log.open('xb') as stdout:
        if separate_stderr:
            with stderr_path.open('xb') as stderr:
                result = subprocess.run(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
        else:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=stdout, stderr=subprocess.STDOUT)
    receipt = {'argv': [str(a) for a in argv], 'returncode': result.returncode,
               'elapsed_seconds': time.monotonic() - started, 'log_sha256': sha(log)}
    if separate_stderr:
        receipt['stderr_sha256'] = sha(stderr_path)
    write(log.with_suffix('.command.json'), receipt)
    require(result.returncode == 0, 'Command failed; preserve and inspect ' + str(log))
    return receipt


def prepare(args, artifacts, packages, manifest):
    require(platform.system() == 'Linux' and platform.machine() in ('x86_64', 'AMD64'),
            'Prefix creation/build requires compatible x86_64 Linux')
    require(hasattr(tarfile, 'data_filter'), 'Host Python must provide tarfile data-filter extraction')
    require(not any(ch.isspace() for ch in str(args.work_root)) and ':' not in str(args.work_root),
            'Use a whitespace/colon-free work root for legacy compiler/Waf prefix compatibility')
    require(not args.work_root.exists() or not any(args.work_root.iterdir()),
            'Work root must be new or empty; no existing attempt is overwritten')
    for path, entry in artifacts:
        checked(path, entry)
    args.work_root.mkdir(parents=True, exist_ok=True)
    logs, bootstrap, sources = [args.work_root / name for name in ('logs', 'bootstrap', 'source')]
    for directory in (logs, bootstrap, sources):
        directory.mkdir()
    with tarfile.open(args.cache_root / BOOTSTRAP['filename'], 'r:bz2') as archive:
        binary = archive.extractfile('bin/micromamba')
        require(binary is not None, 'Pinned bootstrap lacks bin/micromamba')
        (bootstrap / 'bin').mkdir()
        executable = bootstrap / 'bin/micromamba'
        executable.write_bytes(binary.read())
        executable.chmod(0o755)
    with tarfile.open(args.cache_root / SOURCE['filename'], 'r:gz') as archive:
        archive.extractall(sources, filter='data')
    source = sources / ('gkyl-' + COMMIT)
    source_audit(source, manifest['source_files_sha256'])
    explicit = args.work_root / 'packages.explicit'
    explicit.write_text('@EXPLICIT\n' + '\n'.join(
        (args.cache_root / 'compiler-packages' / p['filename']).as_uri() + '#' + p['md5']
        for p in packages) + '\n', encoding='utf-8', newline='\n')
    env = os.environ.copy()
    env.update(MAMBA_ROOT_PREFIX=str(args.work_root / 'mamba-root'),
               CONDA_PKGS_DIRS=str(args.work_root / 'package-cache'))
    argv = [str(executable), 'create', '--offline', '--yes', '--json', '--no-rc',
            '-p', str(args.work_root / 'dependencies'), '--file', str(explicit)]
    run_logged(argv, args.work_root, env, logs / 'dependency-install.json', True)
    state = {'phase': 'prepared', 'source_commit': COMMIT,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'helper_sha256': sha(Path(__file__)),
        'package_lock_sha256': sha(args.package_lock), 'reference_manifest_sha256': sha(args.reference_manifest),
        'source_archive': SOURCE, 'bootstrap_archive': BOOTSTRAP,
        'package_count': len(packages), 'package_archive_bytes': sum(p['bytes'] for p in packages),
        'source_audit': source_audit(source, manifest['source_files_sha256']),
        'system_runtime_modified': False, 'simulation_run': False}
    write(args.work_root / 'recipe-state.json', state)
    return state


def build(args, manifest):
    require(platform.system() == 'Linux', 'Compilation requires Linux')
    state = read(args.work_root / 'recipe-state.json')
    require(state['phase'] == 'prepared' and state['package_lock_sha256'] == sha(args.package_lock)
            and state['reference_manifest_sha256'] == sha(args.reference_manifest),
            'Prepared attempt or canonical raw-byte lock changed')
    require(state['helper_sha256'] == sha(Path(__file__)), 'Build helper changed since preparation')
    deps, solver = args.work_root / 'dependencies', args.work_root / 'solver'
    source = args.work_root / 'source' / ('gkyl-' + COMMIT)
    logs = args.work_root / 'logs'
    require(not solver.exists(), 'Refusing to overwrite an installed solver prefix')
    source_audit(source, manifest['source_files_sha256'])
    env = os.environ.copy()
    removed = ['CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'FCFLAGS', 'CONDA_BUILD_SYSROOT',
               'CMAKE_SYSROOT', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV',
               'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE']
    for name in removed:
        env.pop(name, None)
    env.update(PATH=str(deps / 'bin') + ':' + env.get('PATH', ''),
               LD_LIBRARY_PATH=str(deps / 'lib'),
               CC=str(deps / 'bin/x86_64-conda-linux-gnu-gcc'),
               CXX=str(deps / 'bin/x86_64-conda-linux-gnu-g++'),
               GIT_CEILING_DIRECTORIES=str(args.work_root))
    configure = [str(deps / 'bin/python'), 'waf', 'configure', '--prefix=' + str(solver),
        '--disable-cuda', '--enable-mpi', '--luajit-inc-dir=' + str(deps / 'include/luajit-2.1'),
        '--luajit-lib-dir=' + str(deps / 'lib'), '--luajit-share-dir=' + str(deps / 'share/luajit-2.1'),
        '--mpi-inc-dir=' + str(deps / 'include'), '--mpi-lib-dir=' + str(deps / 'lib'),
        '--adios-inc-dir=' + str(deps / 'include'), '--adios-lib-dir=' + str(deps / 'lib'),
        '--eigen-inc-dir=' + str(deps / 'include/eigen3'), '--extra-link-libs=blosc,z,bz2']
    write(logs / 'environment.json', {'CC': env['CC'], 'CXX': env['CXX'],
        'LD_LIBRARY_PATH': env['LD_LIBRARY_PATH'], 'PATH_prepend': str(deps / 'bin'),
        'GIT_CEILING_DIRECTORIES': env['GIT_CEILING_DIRECTORIES'],
        'inherited_flag_variables_removed': removed, 'compile_jobs': args.jobs})
    try:
        run_logged(configure, source, env, logs / 'configure.log')
        run_logged([str(deps / 'bin/python'), 'waf', 'build', '-j' + str(args.jobs)],
                   source, env, logs / 'build.log')
        run_logged([str(deps / 'bin/python'), 'waf', 'install'], source, env, logs / 'install.log')
    finally:
        write(logs / 'source-audit.json', source_audit(source, manifest['source_files_sha256']))
    runtime = env.copy()
    runtime.update(LD_LIBRARY_PATH=str(solver / 'lib64') + ':' + str(deps / 'lib'),
        OPAL_PREFIX=str(deps), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', OMPI_MCA_btl='self,vader,tcp')
    chunk = ('local M=require("App.PlasmaOnCartGrid").Moments; assert(type(M)=="function"); '
             'local A=M(); assert(A.Species and A.App); print("CLEAN9663_MOMENTS_FACTORY_OK")')
    run_logged([str(solver / 'bin/gkyl'), '-e', chunk], logs, runtime, logs / 'native-api.log')
    require('CLEAN9663_MOMENTS_FACTORY_OK' in (logs / 'native-api.log').read_text(),
            'Native API probe lacks success marker')
    state.update(phase='built_and_api_probed', finished_utc=datetime.now(timezone.utc).isoformat(),
        source_audit=source_audit(source, manifest['source_files_sha256']),
        installed_executable_sha256=sha(solver / 'bin/gkyl'),
        observed_author_executable_sha256=OBSERVED_EXE,
        byte_identical_to_observed_author_executable=sha(solver / 'bin/gkyl') == OBSERVED_EXE,
        binary_bit_reproducibility_asserted=False, original_dirty_build_reproduced=False)
    write(args.work_root / 'recipe-state.json', state)
    return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', nargs='?', default='plan', choices=['plan', 'verify', 'fetch', 'prepare', 'build'])
    p.add_argument('--cache-root', type=Path, required=True)
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--package-lock', type=Path, default=ROOT / 'data/gkeyll-clean9663-dependencies.json')
    p.add_argument('--reference-manifest', type=Path, default=ROOT / 'data/gkeyll-clean9663-file-manifest.json')
    p.add_argument('--jobs', type=int, default=4)
    args = p.parse_args()
    args.cache_root, args.work_root = args.cache_root.resolve(), args.work_root.resolve()
    require(args.jobs > 0, 'Compile jobs must be positive')
    require(sha(args.package_lock) == PACKAGE_LOCK_SHA256,
            'Package lock is not the published raw-byte artifact (do not normalize/rewrite it)')
    require(sha(args.reference_manifest) == REFERENCE_MANIFEST_SHA256,
            'Reference manifest is not the published raw-byte artifact')
    packages = read(args.package_lock)['packages']
    manifest = read(args.reference_manifest)
    require(len(packages) == 51 and sum(p['bytes'] for p in packages) == 159828558,
            'Expected the exact published 51-package lock')
    require(manifest['source_commit'] == COMMIT, 'Wrong clean source manifest')
    for package in packages:
        require(Path(package['filename']).name == package['filename'], 'Package filename must be a basename')
    artifacts = artifact_paths(args, packages)
    if args.action == 'plan':
        result = {'action': 'plan', 'source': SOURCE, 'bootstrap': BOOTSTRAP, 'dependency_packages': 51,
            'dependency_bytes': 159828558, 'total_archive_bytes': sum(p['bytes'] for _, p in artifacts),
            'cache_root': str(args.cache_root), 'new_work_root': str(args.work_root), 'simulation_run': False}
    elif args.action in ('verify', 'fetch'):
        if args.action == 'fetch':
            fetch_all(artifacts)
        for path, entry in artifacts:
            checked(path, entry)
        result = {'action': args.action, 'artifacts_verified': len(artifacts),
                  'all_size_sha256_and_available_md5_passed': True, 'simulation_run': False}
    elif args.action == 'prepare':
        result = prepare(args, artifacts, packages, manifest)
    else:
        result = build(args, manifest)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
