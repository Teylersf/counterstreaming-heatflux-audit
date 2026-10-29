"""Qualify a separately built clean runtime for startup/initial-output checks.

Default plan is read-only. Register inventories an existing build into a NEW
directory; init explicitly runs four native init-only cases; check independently
decodes those recorded cases into another NEW directory. Historical readback
never emits a fresh-startup gate. No action builds/installs software or launches
a time-integrated control. Existing author/runtime/run records are never edited.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time

# Keep plan/registration/readback from creating import caches in the checkout.
sys.dont_write_bytecode = True

import build_clean_gkeyll as builder
import run_gkeyll_controls as control

ROOT = Path(__file__).resolve().parents[1]
LEGACY_GATE_SHA256 = '26a9c8eb27aa641528e96a45e5396bdc714cc71774012e9efe77755a8a63b8fe'
ORIGINAL_RECEIPT_SHA = {
    '1-fluid': 'a9c8e346c449c8b466ce556daae0234f4b534a2d446442c3290284e9065ff01b',
    '2-fluid': '38636021127d2184a1dbbae97c010799c637481f7fdded7de6f70b6c93cc51c2'}
MAP_KEYS = ('installed_solver_files_sha256', 'dependency_runtime_files_sha256',
            'system_runtime_files_sha256')
LOADED_QUALIFIER_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return builder.sha(path)


def own_sha():
    require(builder.sha(Path(__file__)) == LOADED_QUALIFIER_SHA, 'Qualifier source changed during this command')
    return LOADED_QUALIFIER_SHA


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_new(path, value):
    with path.open('xb') as stream:
        stream.write((json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def required(args, *names):
    for name in names:
        require(getattr(args, name) is not None, '--' + name.replace('_', '-') + ' is required')


def safe_new_path(args, candidate):
    path = candidate.resolve()
    require(not path.exists(), 'Refusing an existing/partial output directory')
    forbidden = [ROOT.resolve(), args.source_root.resolve(), args.solver_prefix.resolve(),
                 args.dependency_prefix.resolve()]
    require(not any(path == root or path.is_relative_to(root) or root.is_relative_to(path)
                    for root in forbidden), 'Output must be outside source/solver/dependency/repository trees')
    for parent in path.parents:
        require(not any((parent / name).exists() for name in
                        ('controller.lock', 'launch-command.json', 'run-started.json')),
                'Output must not be inside an existing model-run tree')
    return path


def new_output(args):
    path = safe_new_path(args, args.output_root)
    path.mkdir(parents=True)
    return path


def runtime_env(args):
    env = os.environ.copy()
    env.update(PATH=str(args.dependency_prefix / 'bin') + ':' + env.get('PATH', ''),
        LD_LIBRARY_PATH=str(args.solver_prefix / 'lib64') + ':' + str(args.dependency_prefix / 'lib'),
        OPAL_PREFIX=str(args.dependency_prefix), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
        OMPI_MCA_btl='self,vader,tcp')
    return env


def init_command(args):
    return [str(args.dependency_prefix / 'bin/mpirun'), '--allow-run-as-root', '--oversubscribe',
            '--bind-to', 'none', '-np', '16', str(args.solver_prefix / 'bin/gkyl'), 'case.lua', 'init']


def environment_record(args):
    env = runtime_env(args)
    return {key: env[key] for key in ('LD_LIBRARY_PATH', 'OPAL_PREFIX', 'OMP_NUM_THREADS',
                                     'OPENBLAS_NUM_THREADS', 'OMPI_MCA_btl')}


def configure_command(deps, solver):
    return [str(deps / 'bin/python'), 'waf', 'configure', '--prefix=' + str(solver),
        '--disable-cuda', '--enable-mpi', '--luajit-inc-dir=' + str(deps / 'include/luajit-2.1'),
        '--luajit-lib-dir=' + str(deps / 'lib'), '--luajit-share-dir=' + str(deps / 'share/luajit-2.1'),
        '--mpi-inc-dir=' + str(deps / 'include'), '--mpi-lib-dir=' + str(deps / 'lib'),
        '--adios-inc-dir=' + str(deps / 'include'), '--adios-lib-dir=' + str(deps / 'lib'),
        '--eigen-inc-dir=' + str(deps / 'include/eigen3'), '--extra-link-libs=blosc,z,bz2']


def linked_files(args):
    """Inventory actual ELF resolution; reject an unexpected third prefix."""
    system, signatures = {}, {}
    prefixes = {'solver': args.solver_prefix.resolve(), 'dependency': args.dependency_prefix.resolve()}
    for label, executable in [('gkyl', args.solver_prefix / 'bin/gkyl'),
                              ('mpirun', args.dependency_prefix / 'bin/mpirun')]:
        result = subprocess.run(['ldd', str(executable)], env=runtime_env(args), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        require(result.returncode == 0 and 'not found' not in result.stdout,
                'Unresolved native linkage for ' + label)
        paths = set()
        for line in result.stdout.splitlines():
            match = re.search(r'=>\s+(/[^\s(]+)|^\s*(/[^\s(]+)\s+\(', line)
            if match:
                paths.add(Path(match.group(1) or match.group(2)))
        require(paths, 'No dynamic libraries discovered for ' + label)
        entries = []
        for path in sorted(paths):
            require(path.is_file(), 'Linked library is not a file')
            owned = next((kind for kind, prefix in prefixes.items()
                          if path.resolve().is_relative_to(prefix)), None)
            if owned:
                relative = path.resolve().relative_to(prefixes[owned]).as_posix()
                entries.append({'kind': owned, 'path': relative, 'sha256': sha(path)})
            else:
                require(str(path).startswith(('/lib/', '/lib64/', '/usr/lib/', '/usr/lib64/')),
                        'Unexpected linked library outside the selected prefixes/system')
                system[str(path)] = sha(path)
                entries.append({'kind': 'system', 'path': str(path), 'sha256': sha(path)})
        signatures[label] = entries
    return system, signatures


def inventory(args):
    require(os.name == 'posix' and Path('/proc').is_dir(), 'Runtime inventory requires Linux')
    reference_path = ROOT / 'data/gkeyll-clean9663-file-manifest.json'
    lock_path = ROOT / 'data/gkeyll-clean9663-dependencies.json'
    require(sha(reference_path) == builder.REFERENCE_MANIFEST_SHA256
            and sha(lock_path) == builder.PACKAGE_LOCK_SHA256, 'Published raw lock/reference bytes changed')
    reference = read(reference_path)
    builder.checked(args.source_archive, builder.SOURCE)
    source = builder.source_audit(args.source_root, reference['source_files_sha256'])
    archive_count = 0
    with tarfile.open(args.source_archive, 'r:gz') as archive:
        for member in archive:
            if not member.isfile():
                continue
            parts = Path(member.name).parts
            require(parts[0] == 'gkyl-' + builder.COMMIT and '..' not in parts,
                    'Unexpected source archive path')
            actual = args.source_root.joinpath(*parts[1:])
            require(actual.resolve().is_relative_to(args.source_root.resolve()) and actual.is_file(),
                    'Original archive file missing/escaping source root')
            stream = archive.extractfile(member)
            require(stream is not None, 'Unreadable original source archive member')
            expected = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                expected.update(block)
            require(sha(actual) == expected.hexdigest(), 'Original archive file changed: ' + member.name)
            archive_count += 1
    solver = {p.relative_to(args.solver_prefix).as_posix(): sha(p)
              for p in sorted(args.solver_prefix.rglob('*')) if p.is_file()}
    paths = {p for p in (args.dependency_prefix / 'lib').rglob('*') if p.is_file() and '.so' in p.name}
    paths.update(args.dependency_prefix / 'bin' / name for name in ('mpirun', 'orted', 'luajit'))
    deps = {p.relative_to(args.dependency_prefix).as_posix(): sha(p) for p in sorted(paths)}
    require('bin/gkyl' in solver and all((args.dependency_prefix / 'bin' / name).is_file()
            for name in ('mpirun', 'orted', 'luajit')), 'Incomplete installed runtime')
    system, linkage = linked_files(args)
    return {'source_commit': builder.COMMIT, 'source_files_sha256': reference['source_files_sha256'],
        'installed_solver_files_sha256': solver, 'dependency_runtime_files_sha256': deps,
        'system_runtime_files_sha256': system, 'linkage_signature': linkage,
        'source_audit': source, 'full_source_archive_audit': {'regular_files_checked': archive_count,
            'all_original_regular_files_unchanged': True, 'archive_sha256': builder.SOURCE['sha256']}}, reference


def register(args):
    safe_new_path(args, args.output_root)
    actual, reference = inventory(args)
    if args.author_reference:
        require(all(actual[key] == reference[key] for key in MAP_KEYS),
                'Author-reference registration requires the exact complete author runtime maps')
        origin, evidence = 'historical_author_runtime_readback', {'reference_sha256': builder.REFERENCE_MANIFEST_SHA256}
    else:
        required(args, 'build_state')
        state = read(args.build_state)
        require(state['phase'] == 'built_and_api_probed' and state['source_commit'] == builder.COMMIT
                and state['source_archive'] == builder.SOURCE and state['bootstrap_archive'] == builder.BOOTSTRAP
                and state['package_lock_sha256'] == builder.PACKAGE_LOCK_SHA256
                and state['reference_manifest_sha256'] == builder.REFERENCE_MANIFEST_SHA256
                and state['helper_sha256'] == sha(ROOT / 'experiments/build_clean_gkeyll.py')
                and state['installed_executable_sha256'] == actual['installed_solver_files_sha256']['bin/gkyl']
                and state['source_audit'] == {'source_files_checked': 1998, 'original_source_files_changed': []},
                'Fresh build state/helper/source/executable/lock proof differs')
        work = args.build_state.resolve().parent
        require(args.source_root == work / 'source' / ('gkyl-' + builder.COMMIT)
                and args.solver_prefix == work / 'solver' and args.dependency_prefix == work / 'dependencies',
                'Prefixes/source differ from the recorded portable build layout')
        logs = {}
        for name in ('configure', 'build', 'install', 'native-api'):
            receipt = work / 'logs' / (name + '.command.json')
            log = work / 'logs' / (name + '.log')
            command = read(receipt)
            require(command['returncode'] == 0 and command['log_sha256'] == sha(log),
                    'Build command/log proof differs: ' + name)
            logs[name] = {'receipt_sha256': sha(receipt), 'log_sha256': sha(log), 'argv': command['argv']}
        require(logs['configure']['argv'] == configure_command(args.dependency_prefix, args.solver_prefix)
                and logs['install']['argv'] == [str(args.dependency_prefix / 'bin/python'), 'waf', 'install']
                and logs['build']['argv'][:3] == [str(args.dependency_prefix / 'bin/python'), 'waf', 'build']
                and len(logs['build']['argv']) == 4 and re.fullmatch(r'-j[1-9]\d*', logs['build']['argv'][3])
                and logs['native-api']['argv'][:2] == [str(args.solver_prefix / 'bin/gkyl'), '-e'],
                'Recorded build commands differ from the published clean recipe')
        cache = args.source_root / 'build/c4che/_cache.py'
        flags = {line.split('=', 1)[0].strip(): ast.literal_eval(line.split('=', 1)[1].strip())
                 for line in cache.read_text().splitlines() if line.startswith(('CFLAGS =', 'CXXFLAGS ='))}
        require(flags == {'CFLAGS': ['-O3', '-Wall'], 'CXXFLAGS': ['-O3', '-Wall', '-std=c++17']},
                'Actual Waf compiler flags differ from the recorded defaults')
        require('CLEAN9663_MOMENTS_FACTORY_OK' in (work / 'logs/native-api.log').read_text(), 'API probe missing')
        origin, evidence = 'portable_clean_build', {'build_state_sha256': sha(args.build_state), 'build_commands': logs}
    output = new_output(args)
    actual['registration'] = {'origin': origin, 'observed_utc': datetime.now(timezone.utc).isoformat(),
        'qualifier_sha256': own_sha(), 'builder_sha256': sha(ROOT / 'experiments/build_clean_gkeyll.py'),
        'package_lock_sha256': builder.PACKAGE_LOCK_SHA256, 'reference_manifest_sha256': builder.REFERENCE_MANIFEST_SHA256,
        'evidence': evidence, 'startup_qualification_performed': False,
        'scope': 'File/runtime identity registration only; no model launch or dynamical equivalence claim.'}
    write_new(output / 'runtime-manifest.json', actual)
    return {'registered': True, 'origin': origin, 'runtime_manifest_sha256': sha(output / 'runtime-manifest.json')}


def validate_runtime(args):
    manifest = read(args.runtime_manifest)
    require(manifest['registration']['qualifier_sha256'] == own_sha(), 'Qualifier changed since registration')
    actual, reference = inventory(args)
    require(manifest['source_commit'] == builder.COMMIT and all(actual[k] == manifest[k] for k in MAP_KEYS)
            and actual['linkage_signature'] == manifest['linkage_signature']
            and actual['full_source_archive_audit'] == manifest['full_source_archive_audit'],
            'Executable/dependency/system/linkage differs from registered runtime')
    return manifest, reference


def pinned_jobs(root):
    require(sha(root / 'prepared-controls.json') == control.PREPARATION_SHA256,
            'Prepared job manifest differs; use the canonical export metadata and exact target')
    return {case: control.validate_job(root / case) for case in control.CASES}


def numeric_outputs(directory, prefix, populations):
    expected = {f'{prefix}_elc{i}_0.bp' for i in range(1, populations + 1)} | {f'{prefix}_field_0.bp'}
    actual = {p.name for p in directory.glob(prefix + '_*.bp')
              if re.fullmatch(re.escape(prefix) + r'_(?:elc\d+|field)_\d+\.bp', p.name)}
    require(actual == expected and not (directory / (prefix + '_dt.bp')).exists(),
            'Expected only explicit native frame0 outputs; evolved/extra output detected')
    for log in directory.glob('*.log'):
        text = log.read_text(encoding='utf-8', errors='replace')
        require('Starting main loop of Multi-fluid simulation' not in text
                and control.NATIVE_TIMESTEP_FAILURE not in text, 'Probe log indicates evolution/numerical failure')
    return sorted(expected)


def init_probes(args):
    safe_new_path(args, args.output_root)
    validate_runtime(args)
    jobs = pinned_jobs(args.jobs_root)
    output = new_output(args)
    for case in control.CASES:
        validate_runtime(args)
        prepared, inputs = jobs[case]
        directory = output / case
        directory.mkdir()
        for name in list(inputs) + ['prepared-case.json']:
            shutil.copyfile(args.jobs_root / case / name, directory / name)
        require(all(sha(directory / name) == digest for name, digest in inputs.items()), 'Staged input differs')
        require(sha(directory / 'prepared-case.json') == sha(args.jobs_root / case / 'prepared-case.json')
                and read(directory / 'prepared-case.json') == prepared, 'Staged preparation record differs')
        argv = init_command(args)
        receipt = {'case': case, 'probe': 'native init only; no time integration',
            'qualifier_sha256': own_sha(), 'runtime_manifest_sha256': sha(args.runtime_manifest),
            'executable_sha256': sha(args.solver_prefix / 'bin/gkyl'), 'source_commit': builder.COMMIT,
            'source_preparation_receipt_sha256': control.PREPARATION_SHA256,
            'copied_input_hashes': inputs, 'prepared_case_sha256': sha(directory / 'prepared-case.json'),
            'runtime_environment_overrides': environment_record(args),
            'command': argv, 'started_utc': datetime.now(timezone.utc).isoformat(), 'returncode': None}
        write_new(directory / 'run-started.json', receipt)
        receipt['started_receipt_sha256'] = sha(directory / 'run-started.json')
        process = None
        started = time.monotonic()
        try:
            with (directory / 'console.log').open('xb') as log:
                mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGHUP, signal.SIGINT})
                def child_setup():
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                    os.nice(10)
                try:
                    process = subprocess.Popen(argv, cwd=directory, env=runtime_env(args), stdout=log,
                        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, preexec_fn=child_setup)
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                receipt['mpi_pid'] = process.pid
                receipt['returncode'] = process.wait(timeout=args.init_timeout)
            require(receipt['returncode'] == 0, 'Native init returned a failure')
            numeric_outputs(directory, 'case', prepared['species'])
            validate_runtime(args)
            receipt['status'] = 'native_init_complete'
        except BaseException as error:
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    pass
            receipt.update(status='failed', error_type=type(error).__name__, error=str(error))
            receipt['returncode'] = process.returncode if process else None
            receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
            write_new(directory / 'run-receipt.json', receipt)
            raise
        receipt.update(finished_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                       console_sha256=sha(directory / 'console.log'),
                       output_files=[{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)}
                                     for p in sorted(directory.glob('*.bp'))])
        write_new(directory / 'run-receipt.json', receipt)
    return {'native_init_cases_completed': 4, 'time_integration_performed': False}


def validate_fresh_receipt(args, case, directory, receipt, prepared, inputs, manifest):
    """Validate recorded launch provenance independently of array comparisons."""
    start_path = directory / 'run-started.json'
    start = read(start_path)
    bound_keys = ('case', 'probe', 'qualifier_sha256', 'runtime_manifest_sha256',
                  'executable_sha256', 'source_commit', 'source_preparation_receipt_sha256',
                  'copied_input_hashes', 'prepared_case_sha256', 'command', 'runtime_environment_overrides')
    require(receipt.get('case') == case and receipt.get('status') == 'native_init_complete'
        and receipt.get('returncode') == 0
        and receipt.get('executable_sha256') == manifest['installed_solver_files_sha256']['bin/gkyl']
        and receipt.get('probe') == 'native init only; no time integration'
        and receipt.get('qualifier_sha256') == own_sha()
        and receipt.get('runtime_manifest_sha256') == sha(args.runtime_manifest)
        and receipt.get('source_commit') == builder.COMMIT
        and receipt.get('source_preparation_receipt_sha256') == control.PREPARATION_SHA256
        and receipt.get('copied_input_hashes') == inputs
        and receipt.get('command') == init_command(args)
        and receipt.get('runtime_environment_overrides') == environment_record(args)
        and receipt.get('prepared_case_sha256') == sha(directory / 'prepared-case.json')
        == sha(args.jobs_root / case / 'prepared-case.json')
        and read(directory / 'prepared-case.json') == prepared
        and receipt.get('started_receipt_sha256') == sha(start_path)
        and all(start.get(key) == receipt.get(key) for key in bound_keys)
        and receipt.get('console_sha256') == sha(directory / 'console.log'),
        'Fresh probe/runtime/case binding differs')
    require(all(sha(directory / name) == digest for name, digest in inputs.items()), 'Fresh probe input changed')


def check_data(args, historical=False):
    import numpy as np
    import check_matched_initial_outputs as checker
    from read_gkeyll_bp import read_file
    from analyze_gkeyll_controls import moments
    safe_new_path(args, args.output_root)
    manifest, reference = validate_runtime(args)
    jobs = pinned_jobs(args.jobs_root)
    if historical:
        require(manifest['registration']['origin'] == 'historical_author_runtime_readback'
                and all(manifest[k] == reference[k] for k in MAP_KEYS),
                'Historical fixtures cannot qualify a differing executable/full runtime')
    output = new_output(args)
    export = read(args.export_metadata)
    require(sha(args.export_metadata) == read(args.jobs_root / 'prepared-controls.json')['export_metadata_sha256'],
            'Target export metadata differs from pinned preparation')
    require(export['archive']['full_archive_checksum_verified'], 'Target lacks complete-source-archive verification')
    target_entry = next(e for e in export['binary_outputs'] if e['filename'] == 'aggregate-pic-t0.f64')
    target_path = args.pic_export_directory / target_entry['filename']
    require(sha(target_path) == target_entry['sha256'] and target_path.stat().st_size == target_entry['bytes'], 'Target bytes differ')
    require(target_entry['components'] == checker.COMPONENTS and target_entry['shape'] == [640, 480, 10]
            and target_entry['dtype'] == '<f8' and target_entry['order'] == 'C', 'Target layout differs')
    target = np.memmap(target_path, dtype='<f8', mode='r', shape=(640, 480, 10))
    _, target_conformance = moments(target, 'PIC aggregate target')
    baseline_pins = {e['file']: e for e in read(ROOT / 'data/provenance-revision.json')['decoded_numeric_exports']}
    def baseline(stem):
        pin = baseline_pins[stem + '.bp']
        return checker.decoded(args.baseline_directory, stem, raw_directory=args.baseline_directory,
            expected_source_sha=pin['bp_sha256'], expected_numeric_sha=pin['numeric_export_sha256'])[0]
    original = {(n, i): baseline(f'fluid{n}-electrons{i}_0') for n in (1, 2) for i in range(1, n + 1)}
    original_conformances = {str(key): moments(value, 'archived original population ' + str(key))[1]
                             for key, value in original.items()}
    fields = {n: baseline(f'fluid{n}-field_0') for n in (1, 2)}
    weights = [original[2, i][..., 0] for i in (1, 2)]
    require(all(np.all(w > 0) for w in weights) and np.all(np.abs(sum(weights) - 1) <= checker.ROUND_EPS), 'Original weights differ')
    legacy_path = ROOT / 'results/gkeyll-matched-init-conformance.json'
    if historical:
        require(sha(legacy_path) == LEGACY_GATE_SHA256, 'Published historical init-gate bytes changed')
    legacy_gate = read(legacy_path) if historical else None
    reports = []
    for case in control.CASES:
        prepared, inputs = jobs[case]
        n, matched = prepared['species'], prepared['aggregate_matched']
        if historical:
            directory = args.historical_matched_root / case if matched else args.historical_original_root / f'{n}-fluid'
            prefix = 'case' if matched else 'init' + str(n)
        else:
            directory, prefix = args.probe_root / case, 'case'
        path = directory / 'run-receipt.json'
        receipt = read(path)
        require(receipt['returncode'] == 0 and receipt['executable_sha256'] == manifest['installed_solver_files_sha256']['bin/gkyl'], 'Probe exit/executable differs')
        if historical:
            expected_receipt = (next(c['run_receipt_sha256'] for c in legacy_gate['cases'] if c['id'] == case)
                                if matched else ORIGINAL_RECEIPT_SHA[f'{n}-fluid'])
            require(sha(path) == expected_receipt, 'Historical receipt differs from recorded reference')
            actual_inputs = receipt['copied_input_hashes'] if matched else {prefix + '.lua': receipt['input_sha256']}
            require(all(sha(directory / name) == digest for name, digest in actual_inputs.items()), 'Historical input file changed')
            if matched:
                require(actual_inputs == inputs, 'Historical matched case inputs differ')
            else:
                require(receipt['mode'] == 'init' and receipt['model'] == f'{n}-fluid'
                        and receipt['input_sha256'] == prepared['original_deck_sha256'], 'Historical original probe differs')
        else:
            validate_fresh_receipt(args, case, directory, receipt, prepared, inputs, manifest)
        names = numeric_outputs(directory, prefix, n)
        pins = {e['name']: e for e in receipt['output_files']}
        states, comparisons = [], []
        decoded = output / case
        for name in names:
            raw = directory / name
            require(raw.stat().st_size == pins[name]['bytes'] and sha(raw) == pins[name]['sha256'], 'Actual BP differs from probe receipt')
            read_file(raw, decoded)
            # Reload the serialized JSON: read_file's in-memory attributes may
            # be NumPy arrays; the saved representation is the portable schema.
            metadata = read(decoded / (raw.stem + '.metadata.json'))
            require(metadata['source_sha256'] == pins[name]['sha256']
                    and metadata['reader_script_sha256'] == sha(ROOT / 'experiments/read_gkeyll_bp.py'), 'Independent decode binding differs')
            array, info = checker.decoded(decoded, raw.stem, raw_directory=directory, expected_source_sha=pins[name]['sha256'])
            if name == prefix + '_field_0.bp':
                expected = fields[n]
                require(array.shape[-1] == 8, 'Expected all eight field components')
            else:
                i = int(re.search(r'_elc(\d+)_0', name).group(1))
                require(metadata['attribute_values']['mass'] == 1
                        and metadata['attribute_values']['charge'] == -1, 'Electron mass/charge normalization differs')
                _, population_conformance = moments(array, case + ' population ' + str(i))
                expected = (target if n == 1 else target * weights[i - 1][..., None]) if matched else original[n, i]
                states.append(array)
            comparison = checker.comparison(array, expected)
            require(comparison['roundoff_conformance_passed'], 'Initial full-grid state/field differs')
            item = {'input': info, 'comparison': comparison}
            if name != prefix + '_field_0.bp':
                item['population_conformance'] = population_conformance
            comparisons.append(item)
        aggregate = sum(states)
        _, aggregate_conformance = moments(aggregate, case + ' aggregate')
        aggregate_comparison = checker.comparison(aggregate, target if matched else sum(original[n, i] for i in range(1, n + 1)))
        require(aggregate_comparison['roundoff_conformance_passed'], 'Initial aggregate differs')
        reports.append({'case': case, 'receipt_sha256': sha(path), 'components': comparisons,
                        'aggregate_comparison': aggregate_comparison, 'aggregate_conformance': aggregate_conformance,
                        'all_data_checks_passed': True})
    validate_runtime(args)
    success = len(reports) == 4
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'qualifier_sha256': own_sha(),
        'runtime_manifest_sha256': sha(args.runtime_manifest),
        'solver_executable_sha256': manifest['installed_solver_files_sha256']['bin/gkyl'],
        'all_data_checks_passed': success, 'all_checks_passed': success and not historical,
        'fresh_startup_qualified': success and not historical,
        'mode': 'historical_author_fixture_readback' if historical else 'manifest_bound_native_initial_output_qualification',
        'cases': reports, 'target_conformance': target_conformance,
        'archived_population_conformances': original_conformances,
        'export_metadata_sha256': sha(args.export_metadata), 'target_sha256': target_entry['sha256'],
        'scope': 'Startup/full-grid initial-output checks only; no dynamical equivalence or historical dirty-build certification.',
        'time_integration_performed': False,
        'new_model_probe_launched_by_this_check': False}
    write_new(output / ('historical-readback.json' if historical else 'qualification-gate.json'), report)
    return {k: report[k] for k in ('all_data_checks_passed', 'all_checks_passed', 'fresh_startup_qualified', 'mode')}


def preflight(args):
    manifest, _ = validate_runtime(args)
    pinned_jobs(args.jobs_root)
    gate = read(args.qualification_gate)
    safe_new_path(args, args.controls_output_root)
    require(gate.get('all_checks_passed') is True and gate.get('fresh_startup_qualified') is True
            and gate.get('runtime_manifest_sha256') == sha(args.runtime_manifest)
            and gate.get('solver_executable_sha256') == manifest['installed_solver_files_sha256']['bin/gkyl']
            and gate.get('qualifier_sha256') == own_sha(),
            'Only a matching manifest-bound startup gate can pass; historical readback is not a gate')
    require(gate.get('mode') == 'manifest_bound_native_initial_output_qualification'
            and len(gate.get('cases', [])) == 4
            and {case['case'] for case in gate['cases']} == set(control.CASES)
            and all(case['all_data_checks_passed'] is True for case in gate['cases']),
            'Startup gate does not contain all four exact initial-output cases')
    argv = [sys.executable, str(ROOT / 'experiments/run_gkeyll_controls.py'),
        '--solver-prefix', str(args.solver_prefix), '--dependency-prefix', str(args.dependency_prefix),
        '--jobs-root', str(args.jobs_root), '--output-root', str(args.controls_output_root),
        '--runtime-manifest', str(args.runtime_manifest),
        '--dependency-lock', str(ROOT / 'data/gkeyll-clean9663-dependencies.json'),
        '--matched-conformance', str(args.qualification_gate),
        '--research-code-revision', args.research_code_revision, '--case', 'all', '--preflight-only']
    result = subprocess.run(argv, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {'qualification_gate_manifest_binding_passed': True, 'runner_preflight': json.loads(result.stdout),
            'no_time_integration_or_model_probe_launched': True,
            'full_control_argv': argv[:-1]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', nargs='?', default='plan', choices=['plan', 'register', 'init', 'check', 'readback', 'preflight'])
    for name in ('source-root', 'source-archive', 'solver-prefix', 'dependency-prefix', 'output-root', 'build-state',
                 'runtime-manifest', 'jobs-root', 'probe-root', 'baseline-directory', 'pic-export-directory',
                 'historical-original-root', 'historical-matched-root', 'qualification-gate', 'controls-output-root'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--export-metadata', type=Path, default=ROOT / 'data/derived/pic-moment-export.json')
    p.add_argument('--author-reference', action='store_true', help='Exact retained author runtime only; not an alternative fresh-build proof')
    p.add_argument('--init-timeout', type=int, default=300)
    p.add_argument('--research-code-revision')
    args = p.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    if args.action == 'plan':
        print(json.dumps({'actions': ['register existing build', 'explicit four init-only probes',
            'independent check of manifest-bound probes', 'nonqualifying historical data readback',
            'matching gate/runtime read-only control preflight'],
            'default_is_read_only': True, 'time_integration_available': False}, indent=2)); return
    required(args, 'source_root', 'source_archive', 'solver_prefix', 'dependency_prefix')
    if args.action != 'preflight':
        required(args, 'output_root')
    require(args.init_timeout > 0, 'Init timeout must be positive')
    if args.action == 'register':
        result = register(args)
    else:
        required(args, 'runtime_manifest', 'jobs_root')
        if args.action == 'preflight':
            required(args, 'qualification_gate', 'controls_output_root', 'research_code_revision')
            result = preflight(args)
        elif args.action == 'init':
            def abort_signal(signum, frame):
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                signal.signal(signal.SIGHUP, signal.SIG_IGN)
                raise InterruptedError('Qualification received ' + signal.Signals(signum).name)
            signal.signal(signal.SIGTERM, abort_signal)
            signal.signal(signal.SIGHUP, abort_signal)
            result = init_probes(args)
        else:
            required(args, 'baseline_directory', 'pic_export_directory')
            required(args, *('historical_original_root', 'historical_matched_root') if args.action == 'readback' else ('probe_root',))
            result = check_data(args, args.action == 'readback')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
