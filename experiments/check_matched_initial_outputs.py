"""Independently check native matched init probes; never launch a solver.

Read independently decoded BP outputs, verify their raw/export/input hashes,
and compare full-grid moments and all eight fields. No clipping or masking.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

from analyze_gkeyll_controls import (ROOT, COMPONENTS, load_json, moments,
                                     require, sanitize_error, sha256, write_json)

ROUND_EPS = 64 * np.finfo(np.float64).eps


def comparison(actual: np.ndarray, expected: np.ndarray) -> dict:
    require(actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(),
            "Nonfinite values or differing comparison shapes")
    difference = actual - expected
    per_component = np.max(np.abs(difference), axis=(0, 1))
    scale = np.maximum(1., np.abs(expected))
    return {"shape": list(actual.shape), "bitwise_equal": actual.tobytes() == expected.tobytes(),
            "maximum_absolute_difference": float(np.max(np.abs(difference))),
            "maximum_absolute_difference_by_component": per_component.tolist(),
            "maximum_difference_divided_by_epsilon_times_max_1_abs_reference": float(np.max(np.abs(difference) / scale) / np.finfo(np.float64).eps),
            "roundoff_bound_epsilon_multiple": 64,
            "roundoff_conformance_passed": bool(np.all(np.abs(difference) <= ROUND_EPS * scale)),
            "interpretation": "Bitwise equality and a declared 64*epsilon*max(1,abs(reference)) roundoff bound are distinct; no values are changed."}


def decoded(directory: Path, stem: str, *, raw_directory: Path | None = None,
            expected_source_sha: str | None = None, expected_numeric_sha: str | None = None) -> tuple[np.ndarray, dict]:
    npz, metadata_path = directory / (stem + ".npz"), directory / (stem + ".metadata.json")
    metadata = load_json(metadata_path)
    require(sha256(npz) == metadata["numeric_export_sha256"], "Decoded export SHA mismatch")
    if expected_source_sha is not None:
        require(metadata["source_sha256"] == expected_source_sha, "Source BP differs from pinned baseline/run receipt")
    if expected_numeric_sha is not None:
        require(metadata["numeric_export_sha256"] == expected_numeric_sha, "Baseline numeric export differs from provenance")
    if raw_directory is not None:
        require(sha256(raw_directory / (stem + ".bp")) == metadata["source_sha256"], "Actual raw BP differs from independent decoding metadata")
    attrs = metadata["attribute_values"]
    require(attrs["numCells"] == [480, 640] and attrs["lowerBounds"] == [-24, -32] and attrs["upperBounds"] == [24, 32], "Grid differs")
    require(attrs["polyOrder"] == 0 and attrs["lowerGhost"] == attrs["upperGhost"] == 0, "Unexpected basis or ghosts")
    with np.load(npz, allow_pickle=False) as z:
        array = np.asarray(z["CartGridField"], dtype=np.float64).transpose(1, 0, 2)
        require(float(z["time"].item()) == 0 and int(z["frame"].item()) == 0, "Probe/baseline is not native time0 frame0")
    require(array.shape[:2] == (640, 480), "Unexpected array grid")
    return array, {"source_filename": metadata["source_filename"], "source_sha256": metadata["source_sha256"],
                   "numeric_export_filename": npz.name, "numeric_export_sha256": sha256(npz),
                   "metadata_sha256": sha256(metadata_path), "time": 0., "frame": 0,
                   "reader_script_sha256": metadata.get("reader_script_sha256"),
                   "reader": metadata.get("reader"), "recorded_changeset": attrs.get("changeset")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-root", type=Path, required=True)
    parser.add_argument("--pic-export-directory", type=Path, required=True)
    parser.add_argument("--baseline-directory", type=Path, default=ROOT / "data/raw/revision")
    parser.add_argument("--solver-executable", type=Path, required=True)
    parser.add_argument("--export-metadata", type=Path, default=ROOT / "data/derived/pic-moment-export.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/gkeyll-matched-init-conformance.json")
    args = parser.parse_args()
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": sha256(Path(__file__)),
              "reader_script_sha256": sha256(ROOT / "experiments/read_gkeyll_bp.py"),
              "analysis_helper_sha256": sha256(ROOT / "experiments/analyze_gkeyll_controls.py"),
              "all_checks_passed": False, "cases": [], "failures": [],
              "scope": "Independent decode and full-grid checks of actual native init-only output. No time integration or solver launch by this checker. No claim to reproduce the source's dirty executable or PIC tags.",
              "raw_cache_paths_included": False, "component_order": COMPONENTS,
              "field_scope": "All eight stored field components compared; no physical meaning assigned to the final two solely from storage position."}
    try:
        report["solver_executable_sha256"] = executable_sha = sha256(args.solver_executable)
        export = load_json(args.export_metadata)
        target_entry = next(e for e in export["binary_outputs"] if e["filename"] == "aggregate-pic-t0.f64")
        target_path = args.pic_export_directory / target_entry["filename"]
        require(target_path.stat().st_size == target_entry["bytes"] and sha256(target_path) == target_entry["sha256"], "Aggregate PIC target receipt differs")
        require(target_entry["components"] == COMPONENTS and target_entry["shape"] == [640, 480, 10] and target_entry["dtype"] == "<f8" and target_entry["order"] == "C", "Target layout differs")
        require(export["archive"]["full_archive_checksum_verified"], "PIC archive verification is absent")
        target = np.memmap(target_path, dtype="<f8", mode="r", shape=(640, 480, 10))
        _, target_conformance = moments(target, "aggregate PIC time0 target")
        report["PIC_target"] = {"export_metadata_sha256": sha256(args.export_metadata), "binary": target_entry,
                                 "conformance": target_conformance, "archive_sha256": export["archive"]["computed_sha256"]}
        baseline_provenance_path = ROOT / "data/provenance-revision.json"
        baseline_provenance = load_json(baseline_provenance_path)
        report["baseline_provenance_sha256"] = sha256(baseline_provenance_path)
        baseline_pins = {e["file"]: e for e in baseline_provenance["decoded_numeric_exports"]}
        preparation = load_json(ROOT / "results/matched-control-preparation.json")
        report["preparation_receipt_sha256"] = sha256(ROOT / "results/matched-control-preparation.json")

        def baseline(stem):
            pin = baseline_pins[stem + ".bp"]
            return decoded(args.baseline_directory, stem, raw_directory=args.baseline_directory,
                           expected_source_sha=pin["bp_sha256"], expected_numeric_sha=pin["numeric_export_sha256"])

        weights, weight_receipts = [], []
        for i in (1, 2):
            original, receipt = baseline("fluid2-electrons" + str(i) + "_0")
            _, original_conformance = moments(original, "archived original fluid label " + str(i))
            weights.append(original[..., 0]); weight_receipts.append({"input": receipt, "original_conformance": original_conformance})
        report["positive_original_label_weights"] = {"source": "Actual archived native fluid t0 density; posted n0=mass=1, so rho is the original initializer's positive label weight.",
            "PIC_tag_assignment_claimed": False, "minimum": [float(w.min()) for w in weights],
            "maximum": [float(w.max()) for w in weights],
            "maximum_sum_minus_one": float(np.max(np.abs(sum(weights) - 1))), "receipts": weight_receipts}
        require(all(np.all(w > 0) for w in weights) and np.all(np.abs(sum(weights) - 1) <= ROUND_EPS), "Original label weights are not a positive partition")
        for population_count in (1, 2):
            case_id = str(population_count) + "-fluid-aggregate-matched"
            raw = args.probe_root / case_id
            run_path = raw / "run-receipt.json"
            run = load_json(run_path)
            require(run["returncode"] == 0 and run["probe"] == "native init only; no time integration", "Probe did not complete as native init-only")
            require(run["executable_sha256"] == executable_sha, "Run receipt solver differs from independently hashed executable")
            prepared_case = next(c for c in preparation["cases"] if c["case"] == case_id)
            require(run["source_preparation_receipt_sha256"] == preparation["prepared_manifest_sha256"], "Probe preparation receipt differs")
            require(run["copied_input_hashes"]["case.lua"] == prepared_case["wrapper_sha256"], "Probe wrapper differs from pinned prepared case")
            for filename, expected_hash in run["copied_input_hashes"].items():
                require(sha256(raw / filename) == expected_hash, "Actual probe input differs from run receipt")
            require(run["copied_input_hashes"]["aggregate-pic-t0.f64"] == target_entry["sha256"], "Probe target differs")
            require(run["copied_input_hashes"]["matched_initializer.lua"] == sha256(ROOT / "experiments/matched_initializer.lua"), "Probe helper differs from repository helper")
            require(run["copied_input_hashes"]["posted-input.lua"] == sha256(ROOT / f"data/input-decks/input_{population_count}-e-Fluid.lua"), "Probe posted deck differs")
            output_pins = {p["name"]: p["sha256"] for p in run["output_files"]}
            directory = args.probe_root / f"independent-{population_count}-fluid"
            populations, population_reports = [], []
            for i in range(1, population_count + 1):
                stem = f"case_elc{i}_0"
                state, source = decoded(directory, stem, raw_directory=raw, expected_source_sha=output_pins[stem + ".bp"])
                require(source["reader_script_sha256"] == report["reader_script_sha256"], "Probe decode reader differs")
                _, state_conformance = moments(state, case_id + " population " + str(i))
                expected = target if population_count == 1 else target * weights[i - 1][..., None]
                split_check = comparison(state, expected)
                require(split_check["roundoff_conformance_passed"], "Native matched population differs from expected aggregate/positive-weight split")
                populations.append(state); population_reports.append({"input": source, "conformance": state_conformance, "expected_state_comparison": split_check})
            aggregate = sum(populations)
            _, aggregate_conformance = moments(aggregate, case_id + " aggregate")
            aggregate_comparison = comparison(aggregate, target)
            require(aggregate_comparison["roundoff_conformance_passed"], "Matched aggregate differs from PIC target")
            fields, field_source = decoded(directory, "case_field_0", raw_directory=raw, expected_source_sha=output_pins["case_field_0.bp"])
            require(field_source["reader_script_sha256"] == report["reader_script_sha256"], "Probe field decoder differs")
            original_fields, original_field_source = baseline(f"fluid{population_count}-field_0")
            require(fields.shape[-1] == original_fields.shape[-1] == 8, "Expected eight field components")
            field_comparison = comparison(fields, original_fields)
            require(field_comparison["roundoff_conformance_passed"], "Matched field differs from archived baseline")
            report["cases"].append({"id": case_id, "run_receipt_sha256": sha256(run_path), "solver_executable_sha256": executable_sha,
                "copied_input_hashes": run["copied_input_hashes"], "actual_time": 0., "frame": 0,
                "populations": population_reports, "aggregate_conformance": aggregate_conformance,
                "aggregate_PIC_target_comparison": aggregate_comparison,
                "field_input": field_source, "archived_baseline_field_input": original_field_source,
                "all_eight_field_components_comparison": field_comparison, "all_checks_passed": True})
        report["all_checks_passed"] = len(report["cases"]) == 2
    except Exception as error:
        report["failures"].append({"error_type": type(error).__name__, "message": sanitize_error(error, args.probe_root)})
        if hasattr(error, "report"):
            report["failures"][-1]["conformance"] = error.report
    write_json(args.output, report)
    print(__import__("json").dumps({"all_checks_passed": report["all_checks_passed"], "solver_executable_sha256": report.get("solver_executable_sha256"),
          "completed_cases": len(report["cases"]), "failure_count": len(report["failures"])}))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
