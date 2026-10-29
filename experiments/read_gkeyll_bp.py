"""Decode Gkeyll BP files using an optional, separately installed ADIOS2.

Portable Linux reader CLI; no network, solver run, private paths or alteration
of the original analysis scripts. Outputs are raw NPZ arrays and JSON metadata.
Do not place raw outputs in a public repository.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def read_file(source: Path, output: Path) -> dict:
    import adios2

    with adios2.FileReader(str(source)) as reader:
        variables = reader.available_variables()
        attributes = reader.available_attributes()
        arrays = {name: reader.read(name) for name in variables}
        values = {name: reader.read_attribute(name) for name in attributes}
    output.mkdir(parents=True, exist_ok=True)
    numeric = output / (source.stem + ".npz")
    np.savez(numeric, **arrays)
    # Embedded source may be large; record its exact hash, not a base64 dump.
    embedded = values.pop("inputfile", None)
    input_bytes = base64.b64decode(str(embedded), validate=True) if embedded is not None else None
    metadata = {
        "source_filename": source.name, "source_bytes": source.stat().st_size,
        "source_sha256": sha256(source), "numeric_export_filename": numeric.name,
        "numeric_export_sha256": sha256(numeric), "reader_script_sha256": sha256(Path(__file__)),
        "decoded_at_utc": datetime.now(timezone.utc).isoformat(),
        "reader": {"adios2": adios2.__version__, "numpy": np.__version__,
                   "python": sys.version, "platform": platform.platform()},
        "variables": variables,
        "variable_exports": {name: {"shape": list(np.asarray(a).shape), "dtype": str(np.asarray(a).dtype)} for name, a in arrays.items()},
        "attribute_values": values,
        "embedded_input_bytes": len(input_bytes) if input_bytes is not None else None,
        "embedded_input_sha256": hashlib.sha256(input_bytes).hexdigest() if input_bytes is not None else None,
        "time": float(np.asarray(arrays["time"]).item()) if "time" in arrays else None,
        "frame": int(np.asarray(arrays["frame"]).item()) if "frame" in arrays else None,
        "scope": "Official ADIOS2 read of supplied BP file; no semantic or original-build certification from the filename alone."
    }
    if input_bytes is not None:
        # Retained locally for exact cadence parsing/independent deck comparison.
        (output / (source.stem + ".embedded-input.lua")).write_bytes(input_bytes)
    dest = output / (source.stem + ".metadata.json")
    dest.write_text(json.dumps(metadata, indent=2, allow_nan=False, default=json_value) + "\n", encoding="utf-8", newline="\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs="+", type=Path, required=True, help="BP files; ADIOS2 may also accept supported BP directories")
    parser.add_argument("--output-dir", type=Path, required=True, help="Nonpublic cache for NPZ/metadata exports")
    args = parser.parse_args()
    for source in args.input:
        if not source.is_file():
            parser.error("This checksum-pinning CLI currently requires a single-file BP input: " + str(source))
        metadata = read_file(source, args.output_dir)
        print(json.dumps({k: metadata[k] for k in ("source_filename", "source_sha256", "numeric_export_filename", "numeric_export_sha256", "time", "frame", "variable_exports")}), flush=True)


if __name__ == "__main__":
    main()
