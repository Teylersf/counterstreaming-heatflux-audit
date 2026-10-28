"""Retrieve only pinned small members from the original Zenodo ZIP, serially.

The 1.24 GB archive is never downloaded in full. HTTP 206, exact Content-Range,
bounded reads, member CRC32 and member SHA-256 are required. The full archive's
MD5 is a declaration from Zenodo, NOT a checksum verified by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.request import Request, urlopen
import zlib

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
AGENT = 'Taylor-Kalin-Counterstreaming-Audit/1.0'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def byte_range(url: str, start: int, stop: int, archive_bytes: int) -> bytes:
    """Read an inclusive byte range; refuse servers that offer the full ZIP."""
    if not 0 <= start <= stop < archive_bytes:
        raise ValueError('Range lies outside the declared archive')
    size = stop - start + 1
    req = Request(url, headers={'User-Agent': AGENT, 'Accept-Encoding': 'identity',
                               'Range': f'bytes={start}-{stop}'})
    with urlopen(req, timeout=45) as response:
        if response.status != 206:
            raise RuntimeError('Server did not honor HTTP Range; full-archive fallback is disabled')
        expected = f'bytes {start}-{stop}/{archive_bytes}'
        if response.headers.get('Content-Range') != expected:
            raise RuntimeError('Unexpected Content-Range: ' + str(response.headers.get('Content-Range')))
        if response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise RuntimeError('Unexpected encoding of a byte-range response')
        data = response.read(size + 1)
        if len(data) != size:
            raise RuntimeError('Byte-range response length mismatch')
    return data


def verified_member(archive: dict, entry: dict) -> tuple[bytes, int]:
    off = entry['local_offset']
    header = byte_range(archive['url'], off, off + 29, archive['bytes'])
    fields = struct.unpack('<4s5H3I2H', header)
    if fields[0] != b'PK\x03\x04' or fields[2] & 1:
        raise RuntimeError('Invalid or encrypted ZIP member')
    method, name_len, extra_len = fields[3], fields[9], fields[10]
    if method != entry['compression_method'] or name_len > 1024 or extra_len > 65535:
        raise RuntimeError('Unexpected ZIP local header')
    name_and_extra = byte_range(archive['url'], off + 30,
                                off + 29 + name_len + extra_len, archive['bytes'])
    if name_and_extra[:name_len].decode('utf-8') != entry['archive_member']:
        raise RuntimeError('ZIP member name mismatch')
    payload_start = off + 30 + name_len + extra_len
    compressed = byte_range(archive['url'], payload_start,
                            payload_start + entry['compressed_bytes'] - 1, archive['bytes'])
    if method == 8:
        decoder = zlib.decompressobj(-15)
        data = decoder.decompress(compressed, entry['uncompressed_bytes'] + 1)
        if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise RuntimeError('Incomplete, excessive or trailing DEFLATE data')
    elif method == 0:
        data = compressed
    else:
        raise RuntimeError('Unsupported ZIP compression method')
    if len(data) != entry['uncompressed_bytes']:
        raise RuntimeError('Uncompressed size mismatch')
    if f'{zlib.crc32(data) & 0xffffffff:08x}' != entry['crc32']:
        raise RuntimeError('Member CRC32 mismatch')
    if sha256(data) != entry['sha256']:
        raise RuntimeError('Member SHA-256 mismatch')
    if not data.startswith(b'\x89HDF\r\n\x1a\n'):
        raise RuntimeError('Expected an HDF5 member')
    return data, len(header) + len(name_and_extra) + len(compressed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Verify cached files without network access')
    parser.add_argument('--force', action='store_true', help='Re-fetch already verified files')
    args = parser.parse_args()
    manifest = json.loads((DATA / 'provenance.json').read_text(encoding='utf-8'))
    raw = DATA / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for entry in manifest['selected_members']:
        name = entry['filename']
        if Path(name).name != name or not re.fullmatch(r'[A-Za-z0-9_.-]+\.h5', name):
            raise ValueError('Unsafe local member filename')
        path = raw / name
        good = path.is_file() and sha256(path.read_bytes()) == entry['sha256']
        if args.check_only:
            if not good:
                raise RuntimeError('Missing or changed cached member: ' + name)
        elif args.force or not good:
            data, count = verified_member(manifest['archive'], entry)
            part = path.with_suffix('.h5.part')
            part.write_bytes(data)
            part.replace(path)
            downloaded += count
        print('VERIFIED member: ' + name)
    for entry in manifest['input_decks']:
        name = entry['file']
        if Path(name).name != name:
            raise ValueError('Unsafe input-deck filename')
        path = DATA / 'input-decks' / name
        good = path.is_file() and sha256(path.read_bytes()) == entry['sha256']
        if args.check_only and not good:
            raise RuntimeError('Missing or changed input deck: ' + name)
        if not args.check_only and (args.force or not good):
            with urlopen(Request(entry['url'], headers={'User-Agent': AGENT}), timeout=45) as response:
                data = response.read(entry['bytes'] + 1)
            if len(data) != entry['bytes'] or sha256(data) != entry['sha256']:
                raise RuntimeError('Input-deck SHA-256/length mismatch')
            if hashlib.md5(data).hexdigest() != entry['md5']:
                raise RuntimeError('Input-deck published MD5 mismatch')
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
            downloaded += len(data)
        print('VERIFIED input deck: ' + name)
    print(json.dumps({'verified_members': len(manifest['selected_members']),
                      'verified_input_decks': len(manifest['input_decks']),
                      'downloaded_response_payload_bytes': downloaded,
                      'full_archive_checksum_verified': False}))


if __name__ == '__main__':
    main()
