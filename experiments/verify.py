"""Execute the source-specific data audit and independent continuum checks."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import traceback

import h5py
import numpy as np

from closure_checks import run_checks as closure_checks
from data_checks import run_checks as data_checks

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    timer = time.perf_counter()
    output = ROOT / 'results'
    output.mkdir(exist_ok=True)
    source_files = [Path(__file__).resolve(),
                      ROOT / 'experiments/closure_checks.py',
                      ROOT / 'experiments/data_checks.py',
                      ROOT / 'experiments/fetch_data.py']
    environment = {'started_at_utc': started, 'python': sys.version,
                   'platform': platform.platform(), 'numpy': np.__version__,
                   'h5py': h5py.__version__,
                   'command': 'python -X utf8 experiments/verify.py',
                   'scope': 'Author-environment execution of archived-data analysis and deterministic classical model tests; no new PIC/Gkeyll run or third-party certification.',
                   'source_files': [{'path': p.relative_to(ROOT).as_posix(),
                                     'sha256': sha256(p)} for p in source_files]}
    log = ['AUTHOR-ENVIRONMENT EXECUTION RECORD', json.dumps(environment, indent=2)]
    try:
        groups = {}
        archive_results = data_checks()
        data_provenance = archive_results.pop('provenance')
        for collection in (archive_results, closure_checks()):
            assert not set(groups).intersection(collection), 'Duplicate verification group'
            groups.update(collection)
        for name, result in groups.items():
            if isinstance(result, dict):
                assert result.get('passed', True) is not False, name
            log.extend(['PASS: ' + name, json.dumps(result, indent=2, allow_nan=False)])
        document = {'environment': environment, 'data_provenance': data_provenance,
                    'groups': groups,
                    'all_assertions_passed': True,
                    'elapsed_seconds': time.perf_counter() - timer}
        target = output / 'verification.json'
        target.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n',
                          encoding='utf-8', newline='\n')
        log.extend(['All assertions passed: true', 'Exit status: 0',
                    'Verification JSON SHA-256: ' + sha256(target)])
        (output / 'execution.log').write_text('\n'.join(log) + '\n',
                                             encoding='utf-8', newline='\n')
        print(json.dumps({'all_assertions_passed': True, 'groups': list(groups),
                          'result': 'results/verification.json',
                          'execution_log': 'results/execution.log'}))
        return 0
    except Exception:
        log.extend(['Exit status: 1', traceback.format_exc()])
        (output / 'execution.log').write_text('\n'.join(log) + '\n',
                                             encoding='utf-8', newline='\n')
        raise


if __name__ == '__main__':
    raise SystemExit(main())
