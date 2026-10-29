"""Record the inspected paper and public reproducibility artifacts."""
import argparse
from pathlib import Path
import hashlib
import json
import re
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
NATIVE_CASES = {'1-fluid-unmatched', '2-fluid-unmatched',
                '1-fluid-aggregate-matched', '2-fluid-aggregate-matched'}
PORTABLE_INPUT = re.compile(r'(?:collector-inventory|expected-runtime-context|'
    r'independent-endpoint-(?:diagnosis|details)|native-predicate-provenance|'
    r'independent-intermediate-[1-9][0-9]*|independent-native-failure-[1-9][0-9]*)\.json\Z')
OPERATIONAL_NAMES = {'run-receipt.json', 'run-started.json', 'completed-case.json',
    'progress.json', 'watcher-state.json', 'launch-command.json', 'console.log', 'driver.log'}
RAW_SUFFIXES = {'.bp', '.npz', '.h5', '.hdf5', '.f64', '.bin', '.zip', '.tar', '.gz', '.7z', '.exe', '.dll'}
PUBLIC_RESULTS = {'verification.json', 'execution.log', 'code-pin.json', 'execution-output-manifest.json',
    'data-checks.json', 'figure-manifest.json', 'profile-sensitivity.json', 'revision-data.json',
    'thermal-loading.json', 'source-final-comparison.json', 'gkeyll-runtime-conformance.json',
    'gkeyll-matched-init-conformance.json', 'gkeyll-matched-init-independent-checks.json',
    'gkeyll-controller-readiness.json', 'gkeyll-control-decoding.json', 'gkeyll-control-comparison.json',
    'gkeyll-admissibility.json', 'gkeyll-scan-supersession.json', 'gkeyll-completed-workflow-checks.json',
    'matched-control-preparation.json', 'pic-moment-export-checks.json'}


def positive_int(value):
    pages = int(value)
    if pages < 1:
        raise argparse.ArgumentTypeError('Expected a positive page count')
    return pages


def public_artifact(path):
    """Restrict discovery to public scientific artifacts, even within results."""
    relative = path.relative_to(ROOT)
    name = path.name.lower()
    if not path.is_file() or path.is_symlink():
        return False
    if not path.resolve().is_relative_to(ROOT.resolve()):
        return False
    if any(parent.is_symlink() for parent in path.parents if parent != ROOT and ROOT in parent.parents):
        return False
    if any(part.startswith('.') or part == '__pycache__' or 'private' in part.lower()
           for part in relative.parts):
        return False
    if any(part.lower().startswith(('interim', 'candidate', 'final-candidate')) or part.lower() in {'raw', 'cache', 'receipts'}
           for part in relative.parts):
        return False
    if name == 'artifact-manifest.json':
        return False
    if path.suffix.lower() in RAW_SUFFIXES:
        return False
    if name in OPERATIONAL_NAMES or any(any(word in part.lower() for word in
           ('receipt', 'credential', 'secret', 'access')) for part in relative.parts):
        return False
    if relative.parts[:2] == ('results', 'gkeyll-saved-state-scans'):
        return len(relative.parts) == 3 and name in {case + '.json' for case in NATIVE_CASES}
    if relative.parts[:2] == ('results', 'gkeyll-admissibility-inputs'):
        return PORTABLE_INPUT.fullmatch(name) is not None
    if relative.parts[0] == 'results':
        return len(relative.parts) == 2 and name in PUBLIC_RESULTS
    return not name.startswith(('publication-', 'publishfun-', 'airaxiv-',
                                'agentpub-', 'aaes-', 'browser-',
                                'submission-', 'review-'))


def artifact_paths():
    required = ['paper/main.pdf', 'paper/main.tex', 'paper/references.bib',
                'paper/results-table.tex', 'submissions/manuscript.md',
                'submissions/metadata.json', 'submissions/format-notes.md',
                'requirements.txt', 'requirements-bp.txt', 'data/provenance.json',
                'data/derived/initial-profiles.csv', 'results/verification.json',
                'results/execution.log', 'results/code-pin.json']
    paths = {ROOT / name for name in required}
    missing = [p.relative_to(ROOT).as_posix() for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError('Required public artifacts missing: ' + ', '.join(sorted(missing)))
    excluded_required = [p.relative_to(ROOT).as_posix() for p in paths if not public_artifact(p)]
    if excluded_required:
        raise ValueError('Required artifacts fail the public release policy: ' + ', '.join(sorted(excluded_required)))
    for name in ('README.md', 'SOURCE.md', 'LICENSE-CODE', 'LICENSE-MANUSCRIPT',
                 'submissions/release-notes.md'):
        if (ROOT / name).is_file():
            paths.add(ROOT / name)
    # Only these public folders/extensions are eligible. Raw downloads, audit
    # notes and arbitrary submission records are deliberately not discovered.
    allowlist = [
        ('paper', ('*.tex',), False),
        ('paper/sections', ('*.tex',), True),
        ('experiments', ('*.py', '*.lua', '*.md'), True),
        ('scripts', ('*.py',), True),
        ('figures', ('*.pdf', '*.png', '*.svg', '*.jpg', '*.jpeg', '*.tex', '*.json'), True),
        ('source-excerpts', ('*.txt', '*.md', '*.json', '*.py'), True),
        ('data', ('*.json', '*.md'), False),
        ('data/input-decks', ('*.2d', '*.lua', '*.md', '*.json'), True),
        ('data/derived', ('*.csv', '*.json', '*.txt'), True),
        ('results', ('*.json',), False),
        ('results/gkeyll-saved-state-scans', ('*.json',), False),
        ('results/gkeyll-admissibility-inputs', ('*.json',), True),
    ]
    for directory, patterns, recursive in allowlist:
        folder = ROOT / directory
        for pattern in patterns:
            paths.update(folder.rglob(pattern) if recursive else folder.glob(pattern))
    return sorted((p for p in paths if public_artifact(p)),
                  key=lambda p: p.relative_to(ROOT).as_posix())


def validate_dependency_closure(paths):
    """Fail on omitted/stale scientific dependencies instead of silently dropping them."""
    selected = {path.relative_to(ROOT).as_posix(): path for path in paths}
    checked = {}

    def require_entry(entry, origin):
        relative, expected = entry.get('path'), entry.get('sha256')
        if not isinstance(relative, str) or '\\' in relative or ':' in relative or '..' in Path(relative).parts or Path(relative).is_absolute():
            raise ValueError('Nonportable scientific dependency in ' + origin)
        if not isinstance(expected, str) or re.fullmatch(r'[0-9a-f]{64}', expected) is None:
            raise ValueError('Missing scientific SHA-256 in ' + origin + ': ' + relative)
        actual = ROOT / relative
        if not actual.is_file():
            raise FileNotFoundError('Missing scientific dependency: ' + relative)
        if relative not in selected:
            raise ValueError('Scientific dependency is excluded by the public release allowlist: ' + relative)
        digest = hashlib.sha256(actual.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError('Stale scientific dependency hash: ' + relative)
        if relative in checked and checked[relative] != expected:
            raise ValueError('Contradictory scientific dependency pins: ' + relative)
        checked[relative] = expected

    pin = json.loads((ROOT / 'results/code-pin.json').read_text(encoding='utf-8'))
    if pin.get('verification_sha256') is not None:
        require_entry({'path': 'results/verification.json', 'sha256': pin['verification_sha256']}, 'code-pin.verification')
    for group in ('source_files', 'input_files', 'revision_outputs'):
        for entry in pin.get(group, []):
            require_entry(entry, 'code-pin.' + group)
    output = pin.get('output_manifest')
    if output is not None:
        require_entry(output, 'code-pin.output_manifest')
        manifest = json.loads((ROOT / output['path']).read_text(encoding='utf-8'))
        if manifest.get('commit') != pin.get('commit') or manifest.get('all_listed_evidence_bytes_match_commit') is not True:
            raise ValueError('Grouped evidence manifest does not bind the scientific code pin')
        if manifest.get('controls_state') != pin.get('controls_state'):
            raise ValueError('Grouped evidence and code pin have different control-outcome claims')
        if not isinstance(manifest.get('groups'), dict):
            raise ValueError('Grouped evidence manifest has no evidence groups')
        for group, entries in manifest['groups'].items():
            if not isinstance(entries, list):
                raise ValueError('Malformed grouped scientific evidence: ' + group)
            for entry in entries:
                require_entry(entry, 'output-manifest.' + group)
    figure_outputs = 0
    for path in paths:
        legacy_figure_record = path == ROOT / 'results/figure-manifest.json'
        if not legacy_figure_record and (not path.is_relative_to(ROOT / 'figures') or not path.name.endswith('-figure-manifest.json')):
            continue
        figure_manifest = json.loads(path.read_text(encoding='utf-8'))
        outputs = figure_manifest.get('figures' if legacy_figure_record else 'outputs', [])
        names = [entry.get('path' if legacy_figure_record else 'filename') for entry in outputs]
        if not outputs or len(names) != len(set(names)):
            raise ValueError('Empty/duplicate figure output manifest: ' + path.name)
        for entry in outputs:
            if legacy_figure_record:
                require_entry(entry, path.name)
                target = ROOT / entry['path']
                if target.stat().st_size != entry.get('bytes'):
                    raise ValueError('Figure output byte-size mismatch: ' + entry['path'])
                figure_outputs += 1
                continue
            filename = entry.get('filename')
            if not isinstance(filename, str) or Path(filename).name != filename or '/' in filename or '\\' in filename:
                raise ValueError('Nonportable figure output name: ' + path.name)
            target = path.parent / filename
            require_entry({'path': target.relative_to(ROOT).as_posix(), 'sha256': entry.get('sha256')}, path.name)
            if target.stat().st_size != entry.get('bytes'):
                raise ValueError('Figure output byte-size mismatch: ' + filename)
            figure_outputs += 1
    return pin, {'code_pin_dependencies_checked': len(checked), 'figure_outputs_checked': figure_outputs,
                 'every_pinned_scientific_dependency_included': True,
                 'interim_private_raw_and_operational_records_excluded': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True, help='Release version being recorded')
    parser.add_argument('--pages', required=True, type=positive_int,
                        help='Expected page count of the visually inspected final PDF')
    parser.add_argument('--visual-qa', help='Explicit description of visual QA actually completed')
    parser.add_argument('--check-only', action='store_true', help='Validate inventory/closure/PDF without writing a manifest')
    args = parser.parse_args()
    pdf = ROOT / 'paper/main.pdf'
    reader = PdfReader(pdf)
    author = reader.metadata.author if reader.metadata else None
    if author != 'Taylor Kalin':
        raise ValueError(f'Unexpected PDF author: {author!r}')
    if len(reader.pages) != args.pages:
        raise ValueError(f'Expected {args.pages} PDF pages, found {len(reader.pages)}')
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        if not text.strip() or '??' in text:
            raise ValueError(f'Empty PDF text or unresolved reference on page {number}')
    paths = artifact_paths()
    pin, closure = validate_dependency_closure(paths)
    data = {'canonical_author': author, 'version': args.version,
            'pages': len(reader.pages), 'visual_QA': args.visual_qa,
            'code_pin': pin, 'scientific_dependency_closure': closure,
            'artifacts': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    if not args.check_only:
        (ROOT / 'results/artifact-manifest.json').write_text(
            json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'version': args.version, 'pages': len(reader.pages), 'author': author,
                      'artifacts_recorded': len(paths), 'pdf_reference_checks_passed': True,
                      'scientific_dependency_closure': closure, 'check_only': args.check_only}))


if __name__ == '__main__':
    main()
