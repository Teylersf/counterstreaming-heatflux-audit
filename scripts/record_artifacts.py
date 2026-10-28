"""Record the inspected paper and public reproducibility artifacts."""
from pathlib import Path
import hashlib
import json
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    pdf = ROOT / 'paper/main.pdf'
    reader = PdfReader(pdf)
    assert reader.metadata.author == 'Taylor Kalin'
    assert len(reader.pages) == 15
    assert not any('??' in page.extract_text() for page in reader.pages)
    names = ['paper/main.pdf', 'paper/main.tex', 'paper/references.bib',
             'paper/results-table.tex', 'submissions/manuscript.md',
             'submissions/metadata.json', 'submissions/format-notes.md',
             'requirements.txt', 'data/provenance.json',
             'data/derived/initial-profiles.csv', 'results/verification.json',
             'results/execution.log', 'results/code-pin.json']
    paths = [ROOT / name for name in names]
    for directory, pattern in [('experiments', '*.py'), ('scripts', '*.py'),
                                ('paper/sections', '*.tex'), ('figures', '*'),
                                ('source-excerpts', '*'), ('data/input-decks', '*')]:
        paths += sorted(p for p in (ROOT / directory).glob(pattern) if p.is_file())
    data = {'canonical_author': reader.metadata.author, 'version': '1.0.0',
            'pages': len(reader.pages), 'visual_QA': 'Every page inspected; final execution appendix rechecked after compaction.',
            'code_pin': json.loads((ROOT / 'results/code-pin.json').read_text()),
            'artifacts': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    (ROOT / 'results/artifact-manifest.json').write_text(
        json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'pages': len(reader.pages), 'author': reader.metadata.author,
                      'artifacts_recorded': len(paths), 'pdf_reference_checks_passed': True}))


if __name__ == '__main__':
    main()
