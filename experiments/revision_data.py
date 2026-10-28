"""Selective archived-fluid corroboration and complete diagnostic inventory.

This revision utility leaves the four original pinned analysis scripts intact.
Network retrieval is serialized and bounded; raw BP/NPZ files remain in data/raw/.
No full simulation archive, solver run or native deposited-current reconstruction.
"""
from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import platform
import sys
from urllib.request import Request, urlopen
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw/revision"
MANIFEST = DATA / "provenance-revision.json"
AGENT = "Taylor-Kalin-Counterstreaming-Revision/1.1"
PINNED = ["verify.py", "closure_checks.py", "data_checks.py", "fetch_data.py"]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=json_value) + "\n", encoding="utf-8", newline="\n")


def byte_range(url: str, first: int, last: int, total: int) -> bytes:
    assert 0 <= first <= last < total
    length = last - first + 1
    assert length <= 32_000_000, "One request may not become a full-archive retrieval"
    req = Request(url, headers={"User-Agent": AGENT, "Accept-Encoding": "identity",
                               "Range": f"bytes={first}-{last}"})
    with urlopen(req, timeout=60) as response:
        assert response.status == 206, "HTTP 200 full-archive fallback is refused"
        assert response.headers.get("Content-Range") == f"bytes {first}-{last}/{total}"
        assert response.headers.get("Content-Encoding", "identity") == "identity"
        b = response.read(length + 1)
    assert len(b) == length
    return b


def central_directory(archive: dict) -> dict:
    total = archive["bytes"]
    first = max(0, total - 65557)
    tail = byte_range(archive["url"], first, total - 1, total)
    where = tail.rfind(b"PK\x05\x06")
    assert where >= 0
    signature, disk, cd_disk, disk_entries, count, size, offset, comment = struct.unpack_from("<4s4H2IH", tail, where)
    assert disk == cd_disk == 0 and disk_entries == count and count < 65535
    assert where + 22 + comment == len(tail)
    assert offset + size <= first + where
    cd = tail[offset - first:offset - first + size] if offset >= first else byte_range(archive["url"], offset, offset + size - 1, total)
    assert len(cd) == size
    entries, p = [], 0
    while p < len(cd):
        f = struct.unpack_from("<4s6H3I5H2I", cd, p)
        assert f[0] == b"PK\x01\x02" and not (f[3] & 1), "Encrypted/invalid member"
        name_len, extra_len, comment_len = f[10:13]
        name = cd[p + 46:p + 46 + name_len].decode("utf-8" if f[3] & 0x800 else "cp437")
        entries.append({"name": name, "flags": f[3], "method": f[4], "compressed_bytes": f[8],
                        "uncompressed_bytes": f[9], "local_offset": f[16], "crc32": f"{f[7]:08x}"})
        p += 46 + name_len + extra_len + comment_len
    assert p == len(cd) and len(entries) == count
    return {"entry_count": count, "offset": offset, "bytes": size, "sha256": sha(cd),
            "tail_first_byte": first, "tail_bytes": len(tail), "tail_sha256": sha(tail),
            "end_record_sha256": sha(tail[where:]), "entries": entries}


def inventory() -> dict:
    req = Request("https://zenodo.org/api/records/21114117", headers={"User-Agent": AGENT})
    with urlopen(req, timeout=45) as response:
        assert response.status == 200
        b = response.read(2_000_001)
    assert len(b) <= 2_000_000
    record = json.loads(b)
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    archives = []
    # Each request finishes and is checked before the next archive is touched.
    for f in record["files"]:
        if not f["key"].endswith(".zip"):
            continue
        a = {"filename": f["key"], "bytes": f["size"], "url": f["links"]["self"],
             "publisher_declared_checksum": f["checksum"], "full_archive_checksum_verified": False}
        a["central_directory"] = central_directory(a)
        archives.append(a)
        print("INVENTORIED", a["filename"], a["central_directory"]["entry_count"], flush=True)
    result = {**old, "record_url": "https://zenodo.org/records/" + str(record["id"]), "record_api_url": "https://zenodo.org/api/records/21114117",
              "version_doi": record["doi"], "concept_doi": record["conceptdoi"],
              "record_metadata_sha256": sha(b), "license": record["metadata"]["license"],
              "record_metadata_version": record["metadata"].get("version"),
              "inventoried_at_utc": datetime.now(timezone.utc).isoformat(), "archives": archives,
              "selected_members": old.get("selected_members", []),
              "integrity_scope": "Complete ZIP central directories and selected member CRC32/SHA-256 only; no full-archive checksum verification",
              "core_scripts_sha256": {n: sha((ROOT / "experiments" / n).read_bytes()) for n in PINNED}}
    pic = next(a for a in archives if "_PIC" in a["filename"])
    scientific = [e["name"] for e in pic["central_directory"]["entries"] if not e["name"].endswith("/") and not e["name"].startswith("__MACOSX/")]
    candidates = [n for n in scientific if any(part.lower() in {"j1", "j2", "j3", "jx", "jy", "jz", "current", "currents", "cu"} for part in n.split("/"))]
    result["native_pic_current_inventory"] = {"entire_central_directory_examined": True,
        "all_entries": pic["central_directory"]["entry_count"], "scientific_non_directory_entries": len(scientific),
        "candidate_native_current_paths": candidates, "native_deposited_current_archived": bool(candidates),
        "scope": "No native deposited-current file is identifiable among the complete posted PIC member names. UDIST velocity moments are not substituted for native deposited current.",
        "all_scientific_paths": scientific}
    write_json(MANIFEST, result)
    return result


def retrieve(archive: dict, entry: dict) -> bytes:
    off = entry["local_offset"]
    header = byte_range(archive["url"], off, off + 29, archive["bytes"])
    f = struct.unpack("<4s5H3I2H", header)
    assert f[0] == b"PK\x03\x04" and not (f[2] & 1) and f[3] == entry["method"]
    name_len, extra_len = f[9:11]
    assert 0 < name_len <= 1024 and extra_len <= 65535
    ne = byte_range(archive["url"], off + 30, off + 29 + name_len + extra_len, archive["bytes"])
    assert ne[:name_len].decode("utf-8" if f[2] & 0x800 else "cp437") == entry["name"]
    start = off + 30 + name_len + extra_len
    compressed = byte_range(archive["url"], start, start + entry["compressed_bytes"] - 1, archive["bytes"])
    assert entry["uncompressed_bytes"] <= 80_000_000
    if entry["method"] == 8:
        decoder = zlib.decompressobj(-15)
        b = decoder.decompress(compressed, entry["uncompressed_bytes"] + 1)
        assert decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data
    else:
        assert entry["method"] == 0
        b = compressed
    assert len(b) == entry["uncompressed_bytes"]
    assert f"{zlib.crc32(b) & 0xffffffff:08x}" == entry["crc32"]
    return b


def fetch(manifest: dict) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for archive in manifest["archives"]:
        if "Fluid" not in archive["filename"]:
            continue
        label = "fluid1" if "_1-e" in archive["filename"] else "fluid2"
        for entry in archive["central_directory"]["entries"]:
            if not entry["name"].endswith("_0.bp"):
                continue
            local = label + "-" + Path(entry["name"]).name
            path = RAW / local
            pinned = next((e for e in manifest["selected_members"] if e["local_filename"] == local), None)
            if pinned and path.is_file() and sha(path.read_bytes()) == pinned["sha256"]:
                print("REUSED verified BP", local, flush=True)
                continue
            b = retrieve(archive, entry)
            if pinned:
                assert sha(b) == pinned["sha256"], "Previously pinned member changed"
            part = path.with_suffix(".bp.part")
            part.write_bytes(b)
            part.replace(path)
            new = {"archive": archive["filename"], "archive_member": entry["name"],
                   "local_filename": local, "compressed_bytes": entry["compressed_bytes"],
                   "uncompressed_bytes": len(b), "crc32": entry["crc32"], "sha256": sha(b)}
            if not pinned:
                manifest["selected_members"].append(new)
            write_json(MANIFEST, manifest)
            print("VERIFIED BP", local, len(b), sha(b), flush=True)


def decode_bp() -> None:
    """Use the official optional ADIOS2 reader; may run in an isolated Linux env."""
    import adios2

    for path in sorted(RAW.glob("*.bp")):
        with adios2.FileReader(str(path)) as reader:
            variables = reader.available_variables()
            attributes = reader.available_attributes()
            arrays = {name: reader.read(name) for name in variables}
            attrs = {}
            for name in attributes:
                value = reader.read_attribute(name)
                attrs[name] = value.tolist() if isinstance(value, np.ndarray) else value
        metadata = {"source_filename": path.name, "source_sha256": sha(path.read_bytes()),
                    "reader": "ADIOS2 " + adios2.__version__, "numpy": np.__version__,
                    "python": sys.version, "platform": platform.platform(),
                    "variables": variables, "attributes": attributes, "attribute_values": attrs,
                    "decoded_variables": {name: {"shape": list(np.asarray(a).shape), "dtype": str(np.asarray(a).dtype)} for name, a in arrays.items()}}
        np.savez(path.with_suffix(".npz"), **arrays)
        metadata["numeric_export_sha256"] = sha(path.with_suffix(".npz").read_bytes())
        write_json(path.with_suffix(".metadata.json"), metadata)
        print(json.dumps({"decoded": path.name, "reader": metadata["reader"],
                          "variables": metadata["decoded_variables"]}), flush=True)


def compare() -> dict:
    """Corroborate the initializer with archived fluid output over the full grid."""
    from data_checks import analyze_profiles
    import h5py

    manifest = json.loads(MANIFEST.read_text())
    core_manifest = json.loads((DATA / "provenance.json").read_text())
    bp_metadata = []

    def read(label: str, field: bool = False) -> np.ndarray:
        pin = next(e for e in manifest["selected_members"] if e["local_filename"] == label + ".bp")
        assert sha((RAW / (label + ".bp")).read_bytes()) == pin["sha256"]
        meta = json.loads((RAW / (label + ".metadata.json")).read_text())
        assert meta["source_sha256"] == pin["sha256"]
        assert meta["numeric_export_sha256"] == sha((RAW / (label + ".npz")).read_bytes())
        attrs = meta["attribute_values"]
        assert attrs["numCells"] == [480, 640]
        assert attrs["lowerBounds"] == [-24.0, -32.0] and attrs["upperBounds"] == [24.0, 32.0]
        assert attrs["lowerGhost"] == attrs["upperGhost"] == attrs["polyOrder"] == 0
        if not field:
            assert attrs["charge"] == -1 and attrs["mass"] == 1
        deck = DATA / "input-decks" / ("input_1-e-Fluid.lua" if label.startswith("fluid1") else "input_2-e-Fluid.lua")
        deck_pin = next(e for e in core_manifest["input_decks"] if e["file"] == deck.name)
        assert sha(deck.read_bytes()) == deck_pin["sha256"]
        embedded = base64.b64decode(attrs["inputfile"], validate=True)
        assert embedded == deck.read_bytes(), "Archived inputfile differs from the standalone posted deck"
        with np.load(RAW / (label + ".npz"), allow_pickle=False) as z:
            assert z["time"].item() == 0.0 and z["frame"].item() == 0
            assert all(int(v["AvailableStepsCount"]) == 1 for v in meta["variables"].values())
            array = z["CartGridField"]
            assert array.shape == (480, 640, 8 if field else 10)
            assert np.isfinite(array).all()
        bp_metadata.append({"file": label + ".bp", "bp_sha256": pin["sha256"],
            "numeric_export_sha256": meta["numeric_export_sha256"], "time": 0.0, "frame": 0,
            "available_steps": 1, "source_shape": list(array.shape), "reader": meta["reader"],
            "reader_python": meta["python"], "reader_platform": meta["platform"], "reader_numpy": meta["numpy"],
            "attributes": {k: v for k, v in attrs.items() if k != "inputfile"},
            "embedded_input_bytes": len(embedded), "embedded_input_sha256": sha(embedded),
            "embedded_input_byte_identical_to_posted_deck": True,
            "explicit_time_averaging_attribute_names": [k for k in attrs if any(w in k.lower() for w in ("average", "averaging", "tavg"))]})
        # BP records [x,y,component]; PIC records [y,x]. The dimensions and
        # full-grid analytical comparisons below independently check alignment.
        return np.transpose(array, (1, 0, 2))

    fluid1 = read("fluid1-electrons1_0")
    pop1, pop2 = read("fluid2-electrons1_0"), read("fluid2-electrons2_0")
    fluid2 = pop1 + pop2
    field1, field2 = read("fluid1-field_0", True), read("fluid2-field_0", True)
    x, y = -24 + (np.arange(480) + .5) * .1, -32 + (np.arange(640) + .5) * .1
    xx, yy = np.meshgrid(x, y)
    bx = .5 * (np.tanh(yy + 16) - np.tanh(yy - 16) - 1)
    dbx = .5 * (1 / np.cosh(yy + 16)**2 - 1 / np.cosh(yy - 16)**2)
    bz = np.sqrt(.25 + .05**2 - bx**2)
    by = .005 * np.sin(2 * np.pi * xx / 48) + .00125 * np.exp(-((xx + 12) / 6)**2)
    vx = bx * dbx / bz
    vz = dbx - .005 * (2 * np.pi / 48) * np.cos(2 * np.pi * xx / 48) + .00125 * 2 * (xx + 12) / 36 * np.exp(-((xx + 12) / 6)**2)
    temperature = .111803**2
    expected = np.stack([np.ones_like(xx), vx, np.zeros_like(xx), vz,
                         temperature + vx**2, np.zeros_like(xx), vx * vz,
                         np.full_like(xx, temperature), np.zeros_like(xx), temperature + vz**2], axis=-1)
    n1 = .03 + .47 * (np.tanh(yy + 16) - np.tanh(yy - 16))
    expected_field = np.stack([np.zeros_like(xx)] * 3 + [bx, by, bz], axis=-1)
    component_names = ["rho", "rho_ux", "rho_uy", "rho_uz", "Mxx", "Mxy", "Mxz", "Myy", "Myz", "Mzz"]
    initializer = {
        "fluid1_component_max_absolute_errors": dict(zip(component_names, np.max(np.abs(fluid1 - expected), axis=(0, 1)))),
        "fluid2_population1_component_max_absolute_errors": dict(zip(component_names, np.max(np.abs(pop1 - n1[..., None] * expected), axis=(0, 1)))),
        "fluid2_population2_component_max_absolute_errors": dict(zip(component_names, np.max(np.abs(pop2 - (1 - n1[..., None]) * expected), axis=(0, 1)))),
        "fluid1_field_first_six_components_max_absolute_error": float(np.max(np.abs(field1[..., :6] - expected_field))),
        "fluid2_field_first_six_components_max_absolute_error": float(np.max(np.abs(field2[..., :6] - expected_field))),
        "fluid2_sum_vs_fluid1_full_state_max_absolute_error": float(np.max(np.abs(fluid2 - fluid1))),
        "fluid2_field_vs_fluid1_max_absolute_error": float(np.max(np.abs(field2 - field1))),
        "component_order_evidence": "Byte-identical embedded inputfiles return rho,rho*ux,rho*uy,rho*uz,Mxx,Mxy,Mxz,Myy,Myz,Mzz. Every component is compared over all 480*640 cells with its analytic initializer; BP metadata gives [480,640,10], mass=1, charge=-1, zero ghosts and polyOrder=0."}
    assert max(initializer["fluid1_component_max_absolute_errors"].values()) < 1e-12
    assert max(initializer["fluid2_population1_component_max_absolute_errors"].values()) < 1e-12
    assert max(initializer["fluid2_population2_component_max_absolute_errors"].values()) < 1e-12
    assert initializer["fluid2_sum_vs_fluid1_full_state_max_absolute_error"] < 1e-12
    assert initializer["fluid1_field_first_six_components_max_absolute_error"] < 1e-12
    assert initializer["fluid2_field_first_six_components_max_absolute_error"] < 1e-12

    def moments(state: np.ndarray) -> dict:
        rho, mx, mz = state[..., 0], state[..., 1], state[..., 3]
        assert np.min(rho) > 0
        return {"n": rho, "jz": -mz, "vz": mz / rho,
                "pxx": state[..., 4] - mx**2 / rho,
                "pyy": state[..., 7] - state[..., 2]**2 / rho,
                "pzz": state[..., 9] - mz**2 / rho}

    fm = {"fluid1": moments(fluid1), "fluid2": moments(fluid2)}
    pic = analyze_profiles()
    profiles = {"raw_y": y, "paper_y": y + 32,
                **{"pic_" + k: pic["pic_" + k] for k in ("jz", "vz", "pxx", "pzz")},
                "pic_staggered_required_jz": pic["staggered_required_jz"]}
    for label, values in fm.items():
        for name, value in values.items():
            profiles[label + "_" + name] = value.mean(axis=1)
    csv_path = DATA / "derived/revision-fluid-profiles.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(list(profiles))
        writer.writerows(zip(*profiles.values()))
    summaries = {}
    masks = {"entire_640_row_profile": np.ones(640, dtype=bool),
             "both_sheets_within_3de": (np.abs(y + 16) <= 3) | (np.abs(y - 16) <= 3)}
    for region, mask in masks.items():
        summaries[region] = {"rows": int(mask.sum())}
        for label in fm:
            summaries[region][label] = {k: {"relative_L2_PIC_minus_archived_fluid": float(np.linalg.norm((profiles["pic_" + k] - profiles[label + "_" + k])[mask]) / np.linalg.norm(profiles[label + "_" + k][mask])),
                                               "max_absolute_PIC_minus_archived_fluid": float(np.max(np.abs((profiles["pic_" + k] - profiles[label + "_" + k])[mask])))}
                                        for k in ("jz", "pxx", "pzz")}
    rows = []
    for j in (159, 160, 479, 480):
        rows.append({"row": j, **{name: float(values[j]) for name, values in profiles.items()},
                     "current_deficit_relative_to_archived_fluid1": float(1 - profiles["pic_jz"][j] / profiles["fluid1_jz"][j]),
                     "Pxx_ratio_to_archived_fluid1": float(profiles["pic_pxx"][j] / profiles["fluid1_pxx"][j]),
                     "Pzz_ratio_to_archived_fluid1": float(profiles["pic_pzz"][j] / profiles["fluid1_pzz"][j])})
    pic_timing = []
    for entry in core_manifest["selected_members"]:
        with h5py.File(DATA / "raw" / entry["filename"], "r") as f:
            assert float(f.attrs["TIME"][0]) == 0 and int(f.attrs["ITER"][0]) == 0
            pic_timing.append({"file": entry["filename"], "TIME": 0.0, "ITER": 0,
                               "explicit_time_averaging_attribute_names": [k for k in f.attrs if any(w in k.lower() for w in ("average", "averaging", "tavg"))]})
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "revision_script_sha256": sha(Path(__file__).read_bytes()),
              "scope": "Reanalysis of posted t=0 outputs; no new simulation or dynamical-effect claim",
              "complete_native_current_inventory": {k: v for k, v in manifest["native_pic_current_inventory"].items() if k != "all_scientific_paths"},
              "BP_snapshot_evidence": bp_metadata, "PIC_snapshot_timing": pic_timing,
              "time_averaging_scope": "Fluid time/frame and PIC TIME/ITER are zero and no explicit averaging attribute is present. This checks posted snapshot metadata; it is not private-code certification that an undocumented averaging operation is impossible.",
              "build_identifier_scope": "Recorded changeset 9663ea594e80+ includes a plus suffix and is a dirty/partial build identifier, not certification of a clean exact source tree or executable.",
              "initializer_corroboration": initializer, "profile_comparisons": summaries, "sheet_center_rows": rows,
              "profile_csv": csv_path.relative_to(ROOT).as_posix(), "profile_csv_sha256": sha(csv_path.read_bytes()),
              "full_archive_checksum_verified": False, "native_deposited_current_compared": False,
              "all_checks_passed": True}
    manifest["decoded_numeric_exports"] = [{k: b[k] for k in ("file", "bp_sha256", "numeric_export_sha256", "reader", "reader_python", "reader_platform", "reader_numpy", "embedded_input_sha256", "embedded_input_byte_identical_to_posted_deck")} for b in bp_metadata]
    manifest["revision_profile_csv_sha256"] = result["profile_csv_sha256"]
    manifest["diagnostic_definitions"] = core_manifest["diagnostic_definitions"]
    write_json(MANIFEST, manifest)
    write_json(ROOT / "results/revision-data.json", result)
    print(json.dumps({"all_checks_passed": True, "bp_snapshots": len(bp_metadata), "profile_rows": 640,
                      "full_profile_comparisons": summaries["entire_640_row_profile"],
                      "native_current_archived": False, "profile_csv_sha256": result["profile_csv_sha256"]}, default=json_value))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true", help="Refresh complete small ZIP central-directory inventories")
    parser.add_argument("--fetch", action="store_true", help="Retrieve selected t=0 fluid BP members serially")
    parser.add_argument("--decode-bp", action="store_true", help="Decode cached BP through optional official adios2")
    parser.add_argument("--compare", action="store_true", help="Compare verified decoded BP with posted input and PIC profiles")
    args = parser.parse_args()
    if args.inventory:
        manifest = inventory()
    elif args.fetch:
        manifest = json.loads(MANIFEST.read_text())
    if args.fetch:
        fetch(manifest)
    if args.decode_bp:
        decode_bp()
    if args.compare:
        compare()
    if MANIFEST.exists():
        pins = json.loads(MANIFEST.read_text())["core_scripts_sha256"]
        assert all(sha((ROOT / "experiments" / n).read_bytes()) == v for n, v in pins.items()), "An original pinned script changed"


if __name__ == "__main__":
    main()
