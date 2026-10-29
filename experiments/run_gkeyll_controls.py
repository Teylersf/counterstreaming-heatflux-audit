"""Run the preregistered clean-base Gkeyll controls without editing model inputs.

Linux/WSL only. Requires existing isolated Gkeyll/OpenMPI prefixes and optional
ADIOS2 Python reader. It neither installs software nor downloads data. Every
case runs in a new copy of an authoritative prepared job. A native .stop is
requested only after all regular frame-30 files are closed and their stored
frame/time metadata agree. The forced-final frame is never the comparison.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

CASES = ['1-fluid-unmatched', '2-fluid-unmatched',
         '1-fluid-aggregate-matched', '2-fluid-aggregate-matched']
PREPARATION_SHA256 = '26681aceffaf2b2ac0dcf303e52bc2cef5d7f210c633f9675caa10872386831a'
SOURCE_COMMIT = '9663ea594e80f68eb305378e14512db390440e6b'
NATIVE_TIMESTEP_FAILURE = ('ERROR: Timestep below 1e-4*dt_init for 20 '
                           'consecutive steps. Exiting...')


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def descendants(pid):
    """Current descendants of mpirun, using Linux process-parent evidence."""
    parents = {}
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            text = (directory / 'stat').read_text()
            # comm may contain spaces or parentheses; fields after its last ')'
            # begin state,ppid,pgrp,... .
            parents[int(directory.name)] = int(text.rsplit(')', 1)[1].split()[1])
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    result = {pid}
    while True:
        extra = {child for child, parent in parents.items() if parent in result}
        if extra <= result:
            return sorted(result)
        result.update(extra)


def any_open_by(paths, pids):
    """A stable filename alone does not establish completion of an MPI write."""
    targets = {str(path.resolve()) for path in paths}
    for pid in pids:
        try:
            handles = list((Path('/proc') / str(pid) / 'fd').iterdir())
        except (FileNotFoundError, ProcessLookupError):
            continue
        for handle in handles:
            try:
                if os.readlink(handle) in targets:
                    return True
            except (FileNotFoundError, ProcessLookupError):
                continue
    return False


def frame_metadata(path):
    import adios2
    with adios2.FileReader(str(path)) as reader:
        frame = int(reader.read('frame').item())
        stamp = float(reader.read('time').item())
    return {'filename': path.name, 'frame': frame, 'time': stamp}


def frame_paths(directory, species, frame):
    return [directory / f'case_elc{i}_{frame}.bp' for i in range(1, species + 1)] + [
        directory / f'case_field_{frame}.bp']


def native_failure_messages(directory):
    """Exact clean-source graceful numerical-failure message, not generic ERROR.

    App/PlasmaOnCartGrid.lua:644-651 in SOURCE_COMMIT can force-write data and
    break normally after timestep collapse. Logger.lua writes the rank-zero
    message to case_0.log when the posted logToFile=true is retained. Check
    both the native case logs and captured console, preserving each occurrence.
    """
    result = []
    paths = sorted(set(directory.glob('case*.log')) | {directory / 'console.log'})
    for path in paths:
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if NATIVE_TIMESTEP_FAILURE in line:
                result.append({'filename': path.name, 'line_number': number, 'message': line})
    return result


def validate_prefix(prefix, expected, label):
    for relative, digest in expected.items():
        path = prefix / relative
        if not path.is_file() or sha(path) != digest:
            raise RuntimeError(f'{label} file differs from validated runtime: {relative}')


def validate_job(source):
    top = source.parent / 'prepared-controls.json'
    if sha(top) != PREPARATION_SHA256:
        raise RuntimeError('Authoritative preparation receipt changed')
    matches = [case for case in read(top)['cases'] if case['case'] == source.name]
    prepared = read(source / 'prepared-case.json')
    if len(matches) != 1 or prepared != matches[0] or prepared['case'] != source.name:
        raise RuntimeError('Per-case preparation record differs from the hash-pinned top manifest')
    expected = {'posted-input.lua': prepared['original_deck_sha256'],
                'case.lua': prepared['wrapper_sha256']}
    if prepared['aggregate_matched']:
        expected.update({'aggregate-pic-t0.f64': prepared['aggregate_binary_sha256'],
                         'matched_initializer.lua': prepared['matched_initializer_sha256']})
    if prepared['time_controls'] != {'tEnd': 600, 'nFrame': 60}:
        raise RuntimeError('Prepared time/output controls differ from 600/60')
    for name, digest in expected.items():
        if sha(source / name) != digest:
            raise RuntimeError('Prepared case input changed: ' + name)
    return prepared, expected


def run_case(args, case, overall):
    prepared, inputs = validate_job(args.jobs_root / case)
    target = args.output_root / case
    if target.exists():
        raise RuntimeError('Refusing to overwrite an existing case or interrupted attempt: ' + str(target))
    target.mkdir()
    for name in list(inputs) + ['prepared-case.json']:
        shutil.copyfile(args.jobs_root / case / name, target / name)
        expected = inputs[name] if name in inputs else sha(args.jobs_root / case / name)
        if sha(target / name) != expected:
            raise RuntimeError('Case copy is not byte-identical: ' + name)
    env = os.environ.copy()
    overrides = {'PATH': str(args.dependency_prefix / 'bin') + ':' + env.get('PATH', ''),
                 'LD_LIBRARY_PATH': str(args.solver_prefix / 'lib64') + ':' + str(args.dependency_prefix / 'lib'),
                 'OPAL_PREFIX': str(args.dependency_prefix), 'OMP_NUM_THREADS': '1',
                 'OPENBLAS_NUM_THREADS': '1', 'OMPI_MCA_btl': 'self,vader,tcp'}
    env.update(overrides)
    command = [str(args.dependency_prefix / 'bin/mpirun'), '--allow-run-as-root',
               '--oversubscribe', '--bind-to', 'none', '-np', '16',
               str(args.solver_prefix / 'bin/gkyl'), 'case.lua']
    started = time.monotonic()
    receipt = {'case': case, 'started_utc': now(), 'command': command,
               'working_directory': str(target), 'mpi_ranks': 16, 'decomposition': [4, 4],
               'time_controls': {'tEnd': 600, 'nFrame': 60},
               'controller_pid': os.getpid(), 'research_code_revision': args.research_code_revision,
               'controller_sha256': sha(Path(__file__)), 'source_commit': SOURCE_COMMIT,
               'original_dirty_build_reproduced': False,
               'executable_sha256': sha(args.solver_prefix / 'bin/gkyl'),
               'runtime_file_manifest_sha256': sha(args.runtime_manifest),
               'dependency_lock_sha256': sha(args.dependency_lock),
               'preparation_receipt_sha256': PREPARATION_SHA256,
               'matched_init_conformance_sha256': sha(args.matched_conformance),
               'prepared_case_sha256': sha(target / 'prepared-case.json'),
               'input_hashes': inputs, 'environment_overrides': overrides,
               'canonical_prepared_jobs_modified': False,
               'priority_policy': 'child process and MPI ranks inherit Linux nice +10',
               'regular_frame_to_compare': 30, 'compare_forced_final_frame': False}
    atomic_json(target / 'run-started.json', receipt)
    # Priority is process-specific. It does not change Windows/WSL/system policy.
    with (target / 'console.log').open('w') as console:
        process = subprocess.Popen(command, cwd=target, env=env, stdout=console,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   start_new_session=True, preexec_fn=lambda: os.nice(10))
        try:
            receipt['mpirun_pid'] = process.pid
            atomic_json(target / 'run-started.json', receipt)
            stable = None
            stop_receipt = None
            last_frame = -1
            last_native = None
            next_progress = 0.0
            while process.poll() is None:
                pids = descendants(process.pid)
                candidates = [int(match.group(1)) for path in target.glob('case_field_*.bp')
                              if (match := re.fullmatch(r'case_field_(\d+)\.bp', path.name))]
                # Progress time is read from native BP metadata, never inferred from
                # filename or wall time. An in-progress MPI write is skipped.
                for frame in sorted((f for f in candidates if last_frame < f <= 30), reverse=True):
                    files = frame_paths(target, prepared['species'], frame)
                    if all(p.is_file() and p.stat().st_size > 0 for p in files) and not any_open_by(files, pids):
                        try:
                            metadata = [frame_metadata(path) for path in files]
                        except Exception:
                            continue  # Writer may be between close/rename operations.
                        if (any(item['frame'] != frame or not math.isfinite(item['time']) for item in metadata)
                                or len({item['time'] for item in metadata}) != 1):
                            raise RuntimeError('Closed frame members have inconsistent native frame/time metadata')
                        last_frame, last_native = frame, metadata
                        break
                files = frame_paths(target, prepared['species'], 30)
                if stop_receipt is None and all(p.is_file() and p.stat().st_size > 0 for p in files):
                    snapshot = [(p.stat().st_size, p.stat().st_mtime_ns) for p in files]
                    if snapshot == stable and not any_open_by(files, pids):
                        failures = native_failure_messages(target)
                        if failures:
                            receipt['native_numerical_failure_markers'] = failures
                            raise RuntimeError('Native timestep-collapse failure marker detected')
                        metadata = [frame_metadata(path) for path in files]
                        if (any(m['frame'] != 30 or not math.isfinite(m['time']) or m['time'] < 300 for m in metadata)
                                or len({m['time'] for m in metadata}) != 1):
                            raise RuntimeError('Frame30 metadata inconsistent; refusing reference substitution')
                        stop_receipt = {'requested_utc': now(), 'elapsed_seconds': time.monotonic()-started,
                            'guard': 'all required frame30 files stable across polls, closed by all current MPI descendants, and native time/frame agree',
                            'regular_frame30': metadata,
                            'regular_frame30_sha256': {p.name: sha(p) for p in files}}
                        with (target / 'case.stop').open('x') as flag:
                            flag.write(json.dumps(stop_receipt, indent=2) + '\n')
                        atomic_json(target / 'native-stop-request.json', stop_receipt)
                    stable = snapshot
                if time.monotonic() >= next_progress:
                    progress = {'case': case, 'observed_utc': now(), 'status': 'running',
                        'elapsed_seconds': time.monotonic()-started, 'mpirun_pid': process.pid,
                        'current_descendant_pids': pids, 'latest_closed_regular_frame': last_frame,
                        'latest_native_metadata': last_native, 'native_stop_requested': stop_receipt is not None}
                    atomic_json(target / 'progress.json', progress)
                    overall.update(status='running', current_case=case, progress=progress)
                    atomic_json(args.output_root / 'progress.json', overall)
                    print(json.dumps(progress), flush=True)
                    next_progress = time.monotonic() + 10
                time.sleep(1)
        except BaseException as error:
            # A controller/metadata guard failure must not leave a full model
            # running unwatched to tEnd. Terminate only this owned process group;
            # do not invent a valid native frame30 or alter numerical settings.
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            receipt.update(status='failed_controller_guard', finished_utc=now(),
                           elapsed_seconds=time.monotonic()-started,
                           error_type=type(error).__name__, error=str(error),
                           owned_process_group_terminated=True,
                           returncode=process.returncode)
            atomic_json(target / 'run-receipt.json', receipt)
            raise
        returncode = process.wait()
    receipt.update(finished_utc=now(), elapsed_seconds=time.monotonic()-started,
                   returncode=returncode, native_stop=stop_receipt,
                   console_sha256=sha(target / 'console.log'),
                   last_recorded_regular_frame=last_frame)
    integrity = False
    if stop_receipt:
        try:
            final_files = frame_paths(target, prepared['species'], 30)
            final_metadata = [frame_metadata(path) for path in final_files]
            final_hashes = {path.name: sha(path) for path in final_files}
            integrity = (final_metadata == stop_receipt['regular_frame30']
                         and final_hashes == stop_receipt['regular_frame30_sha256'])
        except Exception as error:
            receipt['post_exit_integrity_error'] = type(error).__name__ + ': ' + str(error)
    receipt['regular_frame30_unchanged_after_exit'] = integrity
    receipt['native_numerical_failure_markers'] = native_failure_messages(target)
    receipt['checked_log_files'] = [p.name for p in sorted(target.glob('case*.log'))] + ['console.log']
    receipt['native_rank_log_present'] = bool(list(target.glob('case*.log')))
    receipt['native_failure_guard_source'] = 'App/PlasmaOnCartGrid.lua:644-651 at ' + SOURCE_COMMIT
    receipt['output_bp_files'] = [{'filename': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)}
                                  for p in sorted(target.glob('*.bp'))]
    receipt['checkpoint_files'] = [p.name for p in target.glob('*restart*.bp')]
    receipt['post_comparison_frame_numbers_excluded'] = sorted({int(m.group(1)) for p in target.glob('case_field_*.bp')
        if (m := re.fullmatch(r'case_field_(\d+)\.bp', p.name)) and int(m.group(1)) > 30})
    receipt['later_frame_kind_not_inferred_from_index'] = True
    receipt['status'] = ('completed_native_stop' if returncode == 0 and stop_receipt and integrity
                         and receipt['native_rank_log_present']
                         and not receipt['native_numerical_failure_markers'] else 'failed')
    atomic_json(target / 'run-receipt.json', receipt)
    atomic_json(target / 'progress.json', {'case': case, 'status': receipt['status'],
        'finished_utc': receipt['finished_utc'], 'elapsed_seconds': receipt['elapsed_seconds'],
        'regular_frame30': stop_receipt['regular_frame30'] if stop_receipt else None})
    if receipt['status'] != 'completed_native_stop':
        raise RuntimeError('Case failed or terminated before verified regular frame30: ' + case)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['solver-prefix', 'dependency-prefix', 'jobs-root', 'output-root',
                 'runtime-manifest', 'dependency-lock', 'matched-conformance']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--research-code-revision', required=True)
    p.add_argument('--case', choices=['all'] + CASES, default='all')
    p.add_argument('--preflight-only', action='store_true')
    args = p.parse_args()
    def abort_signal(signum, frame):
        # Convert termination into the same owned-MPI cleanup path as an error.
        # Ignore repeated termination while that cleanup is in progress.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        raise InterruptedError('Controller received ' + signal.Signals(signum).name)
    signal.signal(signal.SIGTERM, abort_signal)
    signal.signal(signal.SIGHUP, abort_signal)
    import adios2  # Fail before launch if the separate BP metadata reader is absent.
    if not Path('/proc/self/fd').is_dir():
        raise RuntimeError('This native write-completion guard requires Linux /proc')
    if sha(args.jobs_root / 'prepared-controls.json') != PREPARATION_SHA256:
        raise RuntimeError('Authoritative v2 preparation receipt changed')
    # The independently produced matched-state receipt must explicitly pass.
    conformance = read(args.matched_conformance)
    if not conformance.get('all_checks_passed', False):
        raise RuntimeError('Independent matched native-initial conformance is not a pass')
    if conformance.get('solver_executable_sha256') != sha(args.solver_prefix / 'bin/gkyl'):
        raise RuntimeError('Matched conformance used a different solver executable')
    manifest = read(args.runtime_manifest)
    if manifest['source_commit'] != SOURCE_COMMIT:
        raise RuntimeError('Runtime manifest is not the audited clean9663 source base')
    validate_prefix(args.solver_prefix, manifest['installed_solver_files_sha256'], 'Solver')
    validate_prefix(args.dependency_prefix, manifest['dependency_runtime_files_sha256'], 'Dependency runtime')
    validate_prefix(Path('/'), manifest['system_runtime_files_sha256'], 'System runtime')
    selected = CASES if args.case == 'all' else [args.case]
    for case in selected:
        validate_job(args.jobs_root / case)
        if (args.output_root / case).exists():
            raise RuntimeError('Existing case output requires explicit investigation, never overwrite/restart automatically: ' + case)
    if args.preflight_only:
        print(json.dumps({'preflight_passed': True, 'case_order': selected,
                          'no_solver_executed': True, 'controller_sha256': sha(Path(__file__))}, indent=2))
        return
    args.output_root.mkdir(parents=True, exist_ok=True)
    lock = args.output_root / 'controller.lock'
    with lock.open('x') as owner:
        owner.write(json.dumps({'controller_pid': os.getpid(), 'started_utc': now(),
                                'controller_sha256': sha(Path(__file__))}, indent=2) + '\n')
    overall = {'controller_pid': os.getpid(), 'started_utc': now(),
               'research_code_revision': args.research_code_revision,
               'controller_sha256': sha(Path(__file__)), 'case_order': selected,
               'completed_cases': [], 'status': 'starting'}
    atomic_json(args.output_root / 'progress.json', overall)
    try:
        for case in selected:
            # Recheck all runtime files before every case to prevent differing
            # executables/libraries within a paired comparison.
            validate_prefix(args.solver_prefix, manifest['installed_solver_files_sha256'], 'Solver')
            validate_prefix(args.dependency_prefix, manifest['dependency_runtime_files_sha256'], 'Dependency runtime')
            validate_prefix(Path('/'), manifest['system_runtime_files_sha256'], 'System runtime')
            receipt = run_case(args, case, overall)
            overall['completed_cases'].append({'case': case,
                'elapsed_seconds': receipt['elapsed_seconds'],
                'regular_frame30': receipt['native_stop']['regular_frame30'],
                'receipt_sha256': sha(args.output_root / case / 'run-receipt.json')})
            atomic_json(args.output_root / 'progress.json', overall)
        overall.update(status='completed', finished_utc=now(), current_case=None)
    except BaseException as error:
        overall.update(status='failed', finished_utc=now(), error_type=type(error).__name__, error=str(error))
        atomic_json(args.output_root / 'progress.json', overall)
        raise
    atomic_json(args.output_root / 'progress.json', overall)
    if overall['status'] == 'completed':
        os.replace(lock, args.output_root / 'controller-completed.json')


if __name__ == '__main__':
    main()
