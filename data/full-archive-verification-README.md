# Complete-archive integrity and analysis-input binding

`full-archive-verification.json` is the portable receipt for the three source
simulation ZIP files. A complete successful receipt has
`all_three_archives_and_18_selected_inputs_verified=true`.

For each archive it records its public source URL, exact byte length,
publisher-declared MD5, computed MD5, computed full SHA-256 and verification
time. Full source ZIPs belong in a local research cache, outside the public
repository. Machine-specific cache paths are not part of the public receipt.
The source files are downloaded serially in bounded resumable ranges; size
and publisher MD5 must pass before the next archive starts.

The receipt also binds the original **13 PIC HDF5 + 5 fluid BP inputs** to
the complete verified archives. Each is looked up by its exact ZIP member
name and read to completion. Its size, ZIP CRC32 and SHA-256 must match the
existing analysis provenance. Whole-file integrity therefore supplements the
earlier selective retrieval rather than silently replacing the analyzed data.

The portable receipt does not claim that every simulation diagnostic was
analyzed, that a historical executable build was identified, or that a new
reconnection simulation was performed. Additional offline exports from a
verified ZIP need their own exact member pins.

The following standard-library Python check can be saved as a temporary
script and run from the repository root with the local cache directory as
its first argument. It performs no downloads or extraction to disk:

```python
from pathlib import Path
import hashlib, json, sys, zipfile

cache = Path(sys.argv[1])
receipt = json.loads(Path("data/full-archive-verification.json").read_text())
assert receipt["all_three_archives_and_18_selected_inputs_verified"]
for archive in receipt["archives"]:
    path = cache / archive["filename"]
    assert path.stat().st_size == archive["bytes"]
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            md5.update(block)
            sha.update(block)
    assert md5.hexdigest() == archive["publisher_md5"]
    assert sha.hexdigest() == archive["computed_sha256"]
    with zipfile.ZipFile(path) as z:
        for item in receipt["selected_member_bindings"]:
            if item["archive"] != archive["filename"]:
                continue
            info = z.getinfo(item["exact_member_name"])
            assert info.file_size == item["uncompressed_bytes"]
            assert f"{info.CRC:08x}" == item["crc32"]
            member_sha = hashlib.sha256()
            with z.open(info) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    member_sha.update(block)
            assert member_sha.hexdigest() == item["sha256"]
print("All three complete archives and 18 analysis-input bindings passed.")
```
