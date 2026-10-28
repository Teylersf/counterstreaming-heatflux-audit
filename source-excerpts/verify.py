"""Verify selective excerpts against the exact public arXiv source archive.

Usage: python source-excerpts/verify.py PATH_TO_DOWNLOADED_ARCHIVE
This script makes no network requests and does not extract files to disk.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import tarfile


ROOT = Path(__file__).resolve().parent


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    archive_bytes = args.archive.read_bytes()
    require(len(archive_bytes) == manifest['archive']['bytes'], 'Archive byte length differs.')
    require(sha256(archive_bytes) == manifest['archive']['sha256'], 'Archive SHA-256 differs.')
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:*') as archive:
        member = archive.getmember(manifest['source']['member'])
        require(member.isfile(), 'The source member is not a regular file.')
        require(member.size == manifest['source']['bytes'], 'Source byte length differs.')
        source_bytes = archive.extractfile(member).read()
    require(sha256(source_bytes) == manifest['source']['sha256'], 'Source SHA-256 differs.')
    lines = source_bytes.decode(manifest['source']['text_encoding']).splitlines()
    require(len(lines) == manifest['source']['lines'], 'Source line count differs.')

    count = 0
    for entry in manifest['files']:
        path = (ROOT / entry['path']).resolve()
        require(path.is_relative_to(ROOT), 'Excerpt path leaves the excerpt directory.')
        actual = path.read_bytes()
        require(len(actual) == entry['bytes'], f'Excerpt byte length differs: {entry["path"]}')
        require(sha256(actual) == entry['sha256'], f'Excerpt SHA-256 differs: {entry["path"]}')
        expected = (
            'Attributed selective TeX excerpts\n'
            'Source: McGrae-Menge et al., arXiv:2607.07106v1 (2026)\n'
            'Original: https://arxiv.org/src/2607.07106v1, apssamp.tex\n'
            'License: CC BY 4.0; original authors retain their rights\n'
            'Source SHA-256: ' + manifest['source']['sha256'] + '\n'
        )
        for fragment in entry['fragments']:
            first, last = fragment['first_line'], fragment['last_line']
            start, end = fragment['start_character'], fragment['end_character']
            require(1 <= first <= last <= len(lines), 'Invalid source line range.')
            require(0 <= start <= len(lines[first - 1]), 'Invalid starting character.')
            require(0 <= end <= len(lines[last - 1]), 'Invalid ending character.')
            if first == last:
                require(start <= end, 'Reversed character range.')
                text = lines[first - 1][start:end]
            else:
                text = '\n'.join([
                    lines[first - 1][start:],
                    *lines[first:last - 1],
                    lines[last - 1][:end],
                ])
            require(sha256(text.encode('utf-8')) == fragment['text_sha256'],
                    f'Source text differs at line {first}.')
            expected += (
                f'\n--- Original lines {first}-{last}, characters [{start},{end}) ---\n'
                + text + '\n'
            )
            count += 1
        require(actual == expected.encode('utf-8'), f'Excerpt reconstruction differs: {entry["path"]}')
    print(json.dumps({
        'all_checks_passed': True,
        'archive_sha256': sha256(archive_bytes),
        'source_sha256': sha256(source_bytes),
        'excerpt_files_verified': len(manifest['files']),
        'source_fragments_verified': count,
    }))


if __name__ == '__main__':
    main()
