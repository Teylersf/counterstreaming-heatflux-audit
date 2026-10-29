"""Record the inspected paper and public reproducibility artifacts."""
import argparse
from pathlib import Path
import hashlib
import json
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


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
    if any(part.startswith('.') or part == '__pycache__' or 'private' in part.lower()
           for part in relative.parts):
        return False
    if name == 'artifact-manifest.json':
        return False
    if any(word in name for word in ('receipt', 'credential', 'secret', 'access')):
        return False
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
        ('results', ('*.json', '*.log', '*.csv', '*.txt'), True),
    ]
    for directory, patterns, recursive in allowlist:
        folder = ROOT / directory
        for pattern in patterns:
            paths.update(folder.rglob(pattern) if recursive else folder.glob(pattern))
    return sorted((p for p in paths if public_artifact(p)),
                  key=lambda p: p.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True, help='Release version being recorded')
    parser.add_argument('--pages', required=True, type=positive_int,
                        help='Expected page count of the visually inspected final PDF')
    parser.add_argument('--visual-qa', help='Explicit description of visual QA actually completed')
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
    data = {'canonical_author': author, 'version': args.version,
            'pages': len(reader.pages), 'visual_QA': args.visual_qa,
            'code_pin': json.loads((ROOT / 'results/code-pin.json').read_text()),
            'artifacts': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    (ROOT / 'results/artifact-manifest.json').write_text(
        json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'version': args.version, 'pages': len(reader.pages), 'author': author,
                      'artifacts_recorded': len(paths), 'pdf_reference_checks_passed': True}))


if __name__ == '__main__':
    main()
