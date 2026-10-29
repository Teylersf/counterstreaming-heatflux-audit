"""Decode completed regular-frame30 controls without altering any run directory.

Linux/WSL with optional ADIOS2 for new decoding. Missing/in-progress/failed runs
are retained as explicit statuses, never converted into measurements. This
program cannot launch, stop, restart or otherwise control a solver.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np

from analyze_gkeyll_controls import (ROOT, ConformanceError, load_json, moments,
                                     require, sanitize_error, sha256, write_json)

SOURCE_COMMIT = "9663ea594e80f68eb305378e14512db390440e6b"
PREPARATION_SHA = "26681aceffaf2b2ac0dcf303e52bc2cef5d7f210c633f9675caa10872386831a"
CASES = [("1-fluid-unmatched", "baseline_one_fluid", 1, "baseline"),
         ("2-fluid-unmatched", "baseline_two_fluid", 2, "baseline"),
         ("1-fluid-aggregate-matched", "matched_one_fluid", 1, "matched"),
         ("2-fluid-aggregate-matched", "matched_two_fluid", 2, "matched")]
CONTEXT_KEYS = ("controller_sha256", "research_code_revision", "source_commit", "executable_sha256",
                "runtime_file_manifest_sha256", "dependency_lock_sha256", "preparation_receipt_sha256",
                "matched_init_conformance_sha256")


def timing_provenance(receipt: dict) -> dict:
    started = datetime.fromisoformat(receipt["started_utc"])
    finished = datetime.fromisoformat(receipt["finished_utc"])
    require(started.tzinfo is not None and finished.tzinfo is not None, "Run UTC timestamps must include a timezone")
    require(np.isfinite(receipt["elapsed_seconds"]) and receipt["elapsed_seconds"] >= 0, "Invalid recorded monotonic duration")
    return {"source_started_utc": receipt["started_utc"], "source_finished_utc": receipt["finished_utc"],
            "elapsed_seconds": receipt["elapsed_seconds"],
            "elapsed_seconds_basis": "Linux time.monotonic elapsed duration; not CPU time",
            "UTC_timestamp_difference_seconds": (finished.astimezone(timezone.utc) - started.astimezone(timezone.utc)).total_seconds(),
            "timing_qualification": "UTC timestamp subtraction and monotonic elapsed duration use distinct clock conventions and may differ after clock adjustments. Both are preserved without correction or a CPU-time inference."}


def validate_receipt(receipt: dict, case_name: str, species: int, expected: dict) -> dict:
    require(receipt["case"] == case_name and receipt["status"] == "completed_native_stop", "No completed-native-stop receipt")
    require(receipt["returncode"] == 0 and receipt["regular_frame30_unchanged_after_exit"], "Run exit/regular-frame integrity did not pass")
    require(receipt["native_rank_log_present"] and not receipt["native_numerical_failure_markers"], "Native log/failure guard did not pass")
    require(receipt["regular_frame_to_compare"] == 30 and receipt["compare_forced_final_frame"] is False, "Comparison frame policy differs")
    require(receipt["time_controls"] == {"tEnd": 600, "nFrame": 60} and receipt["mpi_ranks"] == 16 and receipt["decomposition"] == [4, 4], "Native physical/time/decomposition settings differ")
    require(receipt["canonical_prepared_jobs_modified"] is False and receipt["original_dirty_build_reproduced"] is False, "Unexpected run provenance claim")
    for key, value in expected.items():
        require(receipt[key] == value, "Completed receipt differs from expected pin: " + key)
    stop = receipt["native_stop"]
    names = {f"case_elc{i}_30.bp" for i in range(1, species + 1)} | {"case_field_30.bp"}
    metadata = stop["regular_frame30"]
    require(len(metadata) == species + 1 and {m["filename"] for m in metadata} == names, "Regular30 member set differs")
    require(all(m["frame"] == 30 and np.isfinite(m["time"]) and m["time"] >= 300 for m in metadata), "Invalid regular30 native time/frame")
    require(len({m["time"] for m in metadata}) == 1, "Regular30 members have different actual times")
    hashes = stop["regular_frame30_sha256"]
    require(set(hashes) == names, "Stop receipt's hash member set differs")
    final = {m["filename"]: m for m in receipt["output_bp_files"]}
    require(all(name in final and final[name]["sha256"] == digest for name, digest in hashes.items()), "Stop and final receipt hashes differ")
    return {"names": sorted(names), "sha256": hashes, "actual_time": metadata[0]["time"],
            "bytes": {name: final[name]["bytes"] for name in names}}


def guard_self_test() -> dict:
    """Synthetic receipt validation only; these are not native run receipts."""
    names = ["case_elc1_30.bp", "case_field_30.bp"]
    receipt = {"case": "synthetic", "status": "completed_native_stop", "returncode": 0,
               "regular_frame30_unchanged_after_exit": True, "native_rank_log_present": True,
               "native_numerical_failure_markers": [], "regular_frame_to_compare": 30,
               "compare_forced_final_frame": False, "time_controls": {"tEnd": 600, "nFrame": 60},
               "mpi_ranks": 16, "decomposition": [4, 4], "canonical_prepared_jobs_modified": False,
               "original_dirty_build_reproduced": False,
               "native_stop": {"regular_frame30": [{"filename": n, "frame": 30, "time": 300.05} for n in names],
                               "regular_frame30_sha256": {n: "synthetic-digest" for n in names}},
               "output_bp_files": [{"filename": n, "sha256": "synthetic-digest", "bytes": 1} for n in names]}
    validate_receipt(receipt, "synthetic", 1, {})
    rejected = 0
    for change in (lambda x: x.update(status="running"), lambda x: x.update(returncode=1),
                   lambda x: x.update(regular_frame30_unchanged_after_exit=False),
                   lambda x: x.update(native_numerical_failure_markers=["failure"]),
                   lambda x: x["native_stop"]["regular_frame30"][0].update(frame=31),
                   lambda x: x["native_stop"]["regular_frame30"][0].update(time=301.),
                   lambda x: x["output_bp_files"][0].update(sha256="different")):
        changed = json.loads(json.dumps(receipt)); change(changed)
        try:
            validate_receipt(changed, "synthetic", 1, {})
        except (ValueError, KeyError):
            rejected += 1
    require(rejected == 7, "A synthetic bad completed-receipt guard was accepted")
    timing = timing_provenance({"started_utc":"2026-01-01T00:00:00+00:00", "finished_utc":"2026-01-01T00:01:30+00:00", "elapsed_seconds":74.})
    require(timing["elapsed_seconds"] == 74 and timing["UTC_timestamp_difference_seconds"] == 90,
            "Distinct UTC and monotonic duration provenance was changed or conflated")
    return {"synthetic_valid_receipt_accepted": True, "seven_invalid_receipt_variants_rejected": True,
            "distinct_UTC_and_monotonic_durations_preserved": True,
            "scope": "Synthetic guard tests only, not evidence of actual solver completion."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path)
    parser.add_argument("--jobs-root", type=Path)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--expected-controller-sha256")
    parser.add_argument("--expected-executable-sha256")
    parser.add_argument("--expected-research-code-revision")
    parser.add_argument("--expected-runtime-manifest-sha256")
    parser.add_argument("--expected-dependency-lock-sha256")
    parser.add_argument("--matched-conformance", type=Path, default=ROOT / "results/gkeyll-matched-init-conformance.json")
    parser.add_argument("--config-output", type=Path, default=ROOT / "data/gkeyll-completed-control-cases.json")
    parser.add_argument("--manifest-output", type=Path, default=ROOT / "results/gkeyll-control-decoding.json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    tests = guard_self_test()
    if args.self_test:
        print(json.dumps(tests)); return 0
    for field in ("runs_root", "jobs_root", "cache_root", "expected_controller_sha256", "expected_executable_sha256",
                  "expected_research_code_revision", "expected_runtime_manifest_sha256", "expected_dependency_lock_sha256"):
        if getattr(args, field) is None:
            parser.error("--" + field.replace("_", "-") + " is required")
    preparation_path = args.jobs_root / "prepared-controls.json"
    require(sha256(preparation_path) == PREPARATION_SHA, "Authoritative preparation manifest differs")
    preparation = load_json(preparation_path)
    init_gate = load_json(args.matched_conformance)
    require(init_gate["all_checks_passed"] and init_gate["solver_executable_sha256"] == args.expected_executable_sha256,
            "Matched-initial gate does not pass with the expected solver")
    expected = {"controller_sha256": args.expected_controller_sha256, "executable_sha256": args.expected_executable_sha256,
                "research_code_revision": args.expected_research_code_revision, "source_commit": SOURCE_COMMIT,
                "runtime_file_manifest_sha256": args.expected_runtime_manifest_sha256,
                "dependency_lock_sha256": args.expected_dependency_lock_sha256,
                "preparation_receipt_sha256": PREPARATION_SHA, "matched_init_conformance_sha256": sha256(args.matched_conformance)}
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "collector_sha256": sha256(Path(__file__)),
                "reader_sha256": sha256(ROOT / "experiments/read_gkeyll_bp.py"),
                "analysis_helper_sha256": sha256(ROOT / "experiments/analyze_gkeyll_controls.py"),
                "synthetic_guard_checks": tests, "expected_runtime_context": expected, "cases": [],
                "scope": "Read-only processing of completed regular30 BP members. No solver action or numerical result is inferred from progress files. Pending/failed cases are not measurements.",
                "private_run_paths_included": False}
    archived_config = load_json(ROOT / "data/source-final-comparison-config.json")
    config = {"schema_version": 1, "scope": "Actual archived source and completed regular-frame30 clean-base control outputs only; incomplete/failed executions are explicit. Actual unequal times retained; no interpolation or causal effect imputed from missing pairs.",
              "PIC_reference": archived_config["PIC_reference"], "cases": archived_config["cases"],
              "direct_archived_comparisons": [{"clean":"baseline_one_fluid","archived":"archived_one_fluid"},
                                               {"clean":"baseline_two_fluid","archived":"archived_two_fluid"}],
              "pairs": [{"id": "one_fluid_initialization_effect", "baseline": "baseline_one_fluid", "matched": "matched_one_fluid"},
                        {"id": "two_fluid_initialization_effect", "baseline": "baseline_two_fluid", "matched": "matched_two_fluid"}]}
    for native_case, case_id, species, role in CASES:
        case = {"id": case_id, "enabled": False, "kind": "solver_control", "role": role,
                "population_count": species, "moment_exports": [], "initial_moment_exports": [], "execution_status": "not_started"}
        status = {"case": native_case, "analysis_case_id": case_id, "status": "pending_no_completed_receipt"}
        try:
            directory = args.runs_root / native_case
            receipt_path = directory / "run-receipt.json"
            if not receipt_path.is_file():
                if (directory / "run-started.json").is_file():
                    status["status"] = case["execution_status"] = "running_without_completed_receipt"
                case["pending_reason"] = "No completed per-case receipt; no BP read or metrics claimed."
                config["cases"].append(case); manifest["cases"].append(status); continue
            receipt_sha = sha256(receipt_path)
            receipt = load_json(receipt_path)
            status["source_run_receipt_sha256"] = receipt_sha
            selected = validate_receipt(receipt, native_case, species, expected)
            all_raw_pins = {p["filename"]: p for p in receipt["output_bp_files"]}
            selections = [(name, 30, selected["actual_time"], selected["sha256"][name], selected["bytes"][name]) for name in selected["names"]]
            for i in range(1, species + 1):
                name = f"case_elc{i}_0.bp"
                require(name in all_raw_pins, "Completed receipt lacks initial moment output")
                selections.append((name, 0, 0., all_raw_pins[name]["sha256"], all_raw_pins[name]["bytes"]))
            prepared = next(c for c in preparation["cases"] if c["case"] == native_case)
            require(load_json(directory / "prepared-case.json") == prepared, "Actual per-case preparation differs")
            require(sha256(directory / "prepared-case.json") == receipt["prepared_case_sha256"], "Prepared-case file differs from final receipt")
            expected_inputs = {"posted-input.lua": prepared["original_deck_sha256"], "case.lua": prepared["wrapper_sha256"]}
            if prepared["aggregate_matched"]:
                expected_inputs.update({"aggregate-pic-t0.f64": prepared["aggregate_binary_sha256"], "matched_initializer.lua": prepared["matched_initializer_sha256"]})
            require(receipt["input_hashes"] == expected_inputs, "Run input hash map differs from authoritative manifest")
            require(all(sha256(directory / name) == digest for name, digest in expected_inputs.items()), "Actual run input differs from preparation")
            local_relative = Path("controls-decoded") / native_case
            destination = args.cache_root / local_relative
            exported, initial_exported, states, initial_states = [], [], [], []
            for name, native_frame, native_time, expected_sha, expected_bytes in selections:
                source = directory / name
                require(source.stat().st_size == expected_bytes and sha256(source) == expected_sha, "Actual selected BP differs from final receipt (also stop receipt for regular30)")
                metadata_path = destination / (source.stem + ".metadata.json")
                npz_path = destination / (source.stem + ".npz")
                if metadata_path.is_file() and npz_path.is_file():
                    metadata = load_json(metadata_path)
                    require(metadata["source_sha256"] == expected_sha and metadata["reader_script_sha256"] == manifest["reader_sha256"]
                            and sha256(npz_path) == metadata["numeric_export_sha256"], "Existing decoded cache differs; use a fresh cache rather than overwrite")
                else:
                    require(not metadata_path.exists() and not npz_path.exists(), "Partial decoded cache exists; preserve it and use a fresh cache")
                    from read_gkeyll_bp import read_file
                    read_file(source, destination)
                    # ADIOS attributes are NumPy arrays before serialization;
                    # use the same normalized JSON types as the cached path.
                    metadata = load_json(metadata_path)
                require(metadata["time"] == native_time and metadata["frame"] == native_frame, "Decoded native time/frame differs from required initial/regular30 metadata")
                require(sha256(source) == expected_sha, "Selected BP changed during decoding")
                attrs = metadata["attribute_values"]
                require(attrs["numCells"] == [480, 640] and attrs["lowerBounds"] == [-24, -32] and attrs["upperBounds"] == [24, 32], "Decoded control grid differs")
                require(attrs["polyOrder"] == 0 and attrs["lowerGhost"] == attrs["upperGhost"] == 0, "Unexpected decoded basis/ghosts")
                with np.load(npz_path, allow_pickle=False) as z:
                    array = np.asarray(z["CartGridField"], dtype=np.float64).transpose(1, 0, 2)
                    require(float(z["time"].item()) == native_time and int(z["frame"].item()) == native_frame, "NPZ native time/frame differs")
                require(array.shape[:2] == (640, 480) and np.isfinite(array).all(), "Nonfinite/incorrect control array")
                item = {"filename": name, "source_bytes": expected_bytes, "source_sha256": expected_sha,
                        "npz": (local_relative / npz_path.name).as_posix(), "numeric_export_sha256": metadata["numeric_export_sha256"],
                        "metadata": (local_relative / metadata_path.name).as_posix(), "metadata_sha256": sha256(metadata_path),
                        "actual_time": native_time, "frame": native_frame, "reader": metadata["reader"]}
                if name.startswith("case_elc"):
                    require(array.shape[-1] == 10 and attrs["mass"] == 1 and attrs["charge"] == -1, "Control population components/normalization differ")
                    _, item["state_conformance"] = moments(array, native_case + " " + name)
                    (states if native_frame == 30 else initial_states).append(array)
                    case["moment_exports" if native_frame == 30 else "initial_moment_exports"].append({"npz": item["npz"], "metadata": item["metadata"]})
                else:
                    require(array.shape[-1] == 8, "Expected all eight field components")
                    item["finite_eight_component_field_passed"] = True
                    case["field_export"] = {"npz": item["npz"], "metadata": item["metadata"]}
                (exported if native_frame == 30 else initial_exported).append(item)
            require(len(states) == species and sha256(receipt_path) == receipt_sha, "Population count or final receipt changed during collection")
            _, aggregate_conformance = moments(sum(states), native_case + " aggregate")
            require(len(initial_states) == species, "Initial population count differs")
            _, initial_aggregate_conformance = moments(sum(initial_states), native_case + " initial aggregate")
            portable = {"case": native_case, "status": "completed_native_stop", "all_decoding_checks_passed": True,
                        "source_run_receipt_sha256": receipt_sha, **timing_provenance(receipt),
                        "runtime_context": {key: receipt[key] for key in CONTEXT_KEYS}, "input_hashes": receipt["input_hashes"],
                        "prepared_case_sha256": receipt["prepared_case_sha256"], "frame": 30, "actual_time": selected["actual_time"],
                        "console_sha256": receipt["console_sha256"],
                        "collector_sha256": manifest["collector_sha256"], "reader_sha256": manifest["reader_sha256"],
                        "exports": exported, "initial_exports": initial_exported,
                        "aggregate_conformance": aggregate_conformance, "initial_aggregate_conformance": initial_aggregate_conformance,
                        "later_frame_numbers_excluded": receipt["post_comparison_frame_numbers_excluded"],
                        "later_frame_kind_not_inferred_from_index": True, "original_dirty_build_reproduced": False,
                        "source_comparison_is_regular_frame30": True}
            completed_path = destination / "completed-case.json"
            write_json(completed_path, portable)
            case.update(enabled=True, execution_status="completed_native_stop", completion_receipt=(local_relative / "completed-case.json").as_posix())
            status.update(status="completed_and_decoded", receipt=portable, portable_receipt_sha256=sha256(completed_path))
        except Exception as error:
            status.update(status="failed_validation_or_execution", error_type=type(error).__name__,
                          message=sanitize_error(sanitize_error(error, args.runs_root), args.cache_root))
            if isinstance(error, ConformanceError):
                status["conformance_failure"] = error.report
            case.update(enabled=False, execution_status="failed_validation_or_execution", moment_exports=[], initial_moment_exports=[], pending_reason="Validation/execution failure retained in the decoding manifest; no metrics claimed.")
        config["cases"].append(case); manifest["cases"].append(status)
    manifest["completed_case_count"] = sum(c["enabled"] for c in config["cases"] if c["kind"] == "solver_control")
    manifest["any_case_failed_validation_or_execution"] = any(c["status"] == "failed_validation_or_execution" for c in manifest["cases"])
    write_json(args.config_output, config); manifest["case_config_sha256"] = sha256(args.config_output)
    write_json(args.manifest_output, manifest)
    print(json.dumps({"completed_and_decoded": manifest["completed_case_count"],
                      "actual_metrics_computed": False, "case_statuses": {c["case"]: c["status"] for c in manifest["cases"]}}))
    return 1 if manifest["any_case_failed_validation_or_execution"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
