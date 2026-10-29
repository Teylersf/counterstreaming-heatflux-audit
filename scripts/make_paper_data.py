"""Generate the unchanged original table and an evidence-gated execution appendix.

Run only after the final code/evidence pin is committed. All source, input and
result bytes listed in the generated inventories must match HEAD. The generated
inventories/TeX are subsequent derived outputs, not claimed members of that pin.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Teylersf/counterstreaming-heatflux-audit"
REVISION_CODE = ("profile_sensitivity.py", "revision_data.py", "thermal_loading.py")
CONTROL_CODE = ("export_pic_moments.py", "read_gkeyll_bp.py", "prepare_matched_control.py",
                "matched_initializer.lua", "run_gkeyll_controls.py", "analyze_gkeyll_controls.py",
                "check_matched_initial_outputs.py", "collect_completed_gkeyll_cases.py",
                "make_control_figures.py", "build_clean_gkeyll.py", "qualify_clean_gkeyll.py",
                "scan_gkeyll_saved_states.py", "build_gkeyll_admissibility.py")
REVISION_OUTPUTS = ("results/profile-sensitivity.json", "results/revision-data.json",
                    "results/thermal-loading.json", "data/provenance-revision.json")
SUPPORT_OUTPUTS = ("data/full-archive-verification.json", "data/provenance-fluid-reference.json",
    "data/source-final-comparison-config.json",
    "data/derived/pic-moment-export.json", "results/source-final-comparison.json",
    "data/provenance-source-final-comparison.json", "data/derived/source-final-comparison-profiles.csv",
    "results/gkeyll-runtime-conformance.json", "data/gkeyll-clean9663-dependencies.json",
    "data/gkeyll-clean9663-file-manifest.json", "results/gkeyll-matched-init-conformance.json",
    "results/gkeyll-matched-init-independent-checks.json", "results/gkeyll-controller-readiness.json",
    "data/gkeyll-clean-runtime-README.md")
CONTROL_IDS = {"baseline_one_fluid": ("1-fluid-unmatched", "baseline", 1),
    "baseline_two_fluid": ("2-fluid-unmatched", "baseline", 2),
    "matched_one_fluid": ("1-fluid-aggregate-matched", "matched", 1),
    "matched_two_fluid": ("2-fluid-aggregate-matched", "matched", 2)}
NATIVE_SOURCE_COMMIT = "9663ea594e80f68eb305378e14512db390440e6b"
RUNTIME_KEYS = {"controller_sha256", "research_code_revision", "source_commit", "executable_sha256",
    "runtime_file_manifest_sha256", "dependency_lock_sha256", "preparation_receipt_sha256",
    "matched_init_conformance_sha256"}
PAIR_IDS = {"one_fluid_initialization_effect": ("baseline_one_fluid", "matched_one_fluid"),
            "two_fluid_initialization_effect": ("baseline_two_fluid", "matched_two_fluid")}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path):
    resolved = (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as error:
        raise ValueError("Evidence must be a portable project file") from error
    require(resolved.is_file(), "Missing evidence file: " + relative.as_posix())
    return resolved, relative.as_posix()


def committed_entry(path, commit, expected=None):
    actual, relative = relative_path(path)
    digest = sha(actual)
    require(expected is None or digest == expected, "Historical file bytes changed: " + relative)
    committed = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=ROOT)
    require(hashlib.sha256(committed).hexdigest() == digest, "File is not byte-identical at HEAD: " + relative)
    return {"path": relative, "sha256": digest}


def controls_state(result, receipts):
    """Bind six-case analysis and native completion proofs, preserving partials."""
    reported = {item["id"]: item for item in result.get("cases", [])} if result else {}
    require(not result or len(reported) == len(result.get("cases", [])), "Duplicate comparison case IDs")
    compared, archived = {}, {}
    for identifier, item in reported.items():
        if item.get("status") != "compared":
            continue
        if identifier in CONTROL_IDS:
            native, role, populations = CONTROL_IDS[identifier]
            require(item.get("kind") == "solver_control" and item.get("role") == role
                    and item.get("population_count") == populations, "Control identity/role/population differs")
            destination = compared
        elif identifier in {"archived_one_fluid", "archived_two_fluid"}:
            populations = 1 if identifier == "archived_one_fluid" else 2
            require(item.get("kind") == "archived_source" and item.get("role") == "source_reference"
                    and item.get("population_count") == populations, "Archived reference identity differs")
            native, destination = None, archived
        else:
            continue
        stamp = item.get("actual_time")
        require(isinstance(stamp, (float, int)) and math.isfinite(stamp) and stamp >= 300
                and item.get("frame") == 30, "Invalid regular30 comparison time/frame")
        destination[identifier] = {"native_case": native, "actual_time": stamp, "frame": 30}
    completed, common_context = {}, None
    for inventory in receipts:
        for item in inventory.get("cases", []):
            if item.get("status") != "completed_and_decoded":
                continue
            native = item.get("case")
            if native not in {value[0] for value in CONTROL_IDS.values()}:
                continue
            proof = item.get("receipt", {})
            stamp = proof.get("actual_time")
            context = inventory.get("expected_runtime_context")
            require(isinstance(context, dict) and context.get("source_commit") == NATIVE_SOURCE_COMMIT
                    and proof.get("runtime_context") == context,
                    "Completion proof does not bind the expected clean native runtime")
            require(common_context is None or common_context == context,
                    "Control receipts mix differing native runtime contexts")
            common_context = context
            require(proof.get("case") == native and proof.get("status") == "completed_native_stop"
                    and proof.get("all_decoding_checks_passed") is True
                    and proof.get("source_comparison_is_regular_frame30") is True
                    and proof.get("original_dirty_build_reproduced") is False
                    and proof.get("frame") == 30 and isinstance(stamp, (int, float))
                    and math.isfinite(stamp) and stamp >= 300,
                    "Malformed completed-control decoding proof: " + str(native))
            portable_sha = hashlib.sha256((json.dumps(proof, indent=2, allow_nan=False) + "\n").encode()).hexdigest()
            require(item.get("portable_receipt_sha256") == portable_sha,
                    "Portable completed receipt serialization/hash differs")
            source_sha = proof.get("source_run_receipt_sha256")
            require(isinstance(source_sha, str) and re.fullmatch(r"[0-9a-f]{64}", source_sha),
                    "Missing native source-run receipt hash")
            entry = {"actual_time": stamp, "portable_sha256": portable_sha,
                     "source_run_receipt_sha256": source_sha, "runtime_context": context}
            require(native not in completed or completed[native] == entry, "Inconsistent repeated completion proof")
            completed[native] = entry
    for identifier, item in compared.items():
        if item["native_case"] not in completed:
            continue
        proof, case = completed[item["native_case"]], reported[identifier]
        binding = case.get("completed_case_receipt", {})
        require(item["actual_time"] == proof["actual_time"], "Comparison/receipt time differs")
        require(case.get("runtime_context") == proof["runtime_context"] == common_context,
                "Compared case is not bound to the common native runtime")
        require(binding.get("sha256") == proof["portable_sha256"]
                and binding.get("source_run_receipt_sha256") == proof["source_run_receipt_sha256"],
                "Compared case is not bound to its exact portable/native receipt")
    expected_pairs = {"one_fluid_initialization_effect": ("baseline_one_fluid", "matched_one_fluid"),
                      "two_fluid_initialization_effect": ("baseline_two_fluid", "matched_two_fluid")}
    pairs = {}
    for item in result.get("paired_effects", []) if result else []:
        if item.get("status") != "computed":
            continue
        identifier = item.get("id")
        require(identifier in expected_pairs and identifier not in pairs, "Unexpected/duplicate computed pair")
        require((item.get("baseline"), item.get("matched")) == expected_pairs[identifier],
                "Initialization pair endpoints differ")
        pairs[identifier] = True
    direct = {(item.get("clean"), item.get("archived")) for item in
              result.get("clean_unmatched_vs_archived_source", []) if item.get("status") == "computed"} if result else set()
    expected_archived = {"archived_one_fluid", "archived_two_fluid"}
    expected_direct = {("baseline_one_fluid", "archived_one_fluid"), ("baseline_two_fluid", "archived_two_fluid")}
    good_result = bool(result and result.get("all_actual_cases_passed") is True and not result.get("failures"))
    complete = (good_result and set(compared) == set(CONTROL_IDS) and set(archived) == expected_archived
                and set(reported) == set(CONTROL_IDS) | expected_archived
                and set(completed) == {value[0] for value in CONTROL_IDS.values()}
                and set(pairs) == set(expected_pairs) and direct == expected_direct)
    return {"comparison_result_supplied": result is not None,
            "valid_compared_case_count": len(compared), "compared_cases": compared,
            "compared_archived_cases": archived,
            "both_clean_versus_archive_comparisons_computed": direct == expected_direct,
            "validated_native_completion_count": len(completed),
            "completed_native_times": {name: item["actual_time"] for name, item in completed.items()},
            "all_four_completed_and_compared": complete,
            "result_reports_all_actual_cases_passed": good_result,
            "missing_control_comparison_ids": sorted(set(CONTROL_IDS) - set(compared)),
            "actual_times_retained_without_interpolation": True,
            "native_runtime_context": common_context,
            "original_dirty_executable_certified": False}


def digest_is_valid(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_tensor_flags(diagnostic):
    """Do not let summary booleans conceal their recorded counter/eigenvalue witness."""
    if diagnostic.get("eigenanalysis_status") != "computed_without_threshold_or_regularization":
        require(diagnostic.get("covariance_PSD_passed") is False
                and diagnostic.get("strict_covariance_PD_passed") is False,
                "Undefined/failed eigenanalysis cannot certify PSD or strict PD")
        return
    counters = ("nonfinite_conserved_value_count", "nonfinite_conserved_cell_count",
        "nonpositive_finite_density_cell_count", "covariance_undefined_cell_count",
        "nonfinite_covariance_value_count", "negative_eigenvalue_count",
        "negative_eigenvalue_cell_count", "zero_eigenvalue_count", "nonpositive_eigenvalue_cell_count")
    require(all(isinstance(diagnostic.get(key), int) and diagnostic[key] >= 0 for key in counters),
            "Computed saved-state diagnostic lacks valid finite/density/eigenvalue counters")
    minimum = diagnostic.get("minimum_pressure_eigenvalue")
    require(isinstance(minimum, (float, int)) and math.isfinite(minimum)
            and (minimum < 0) == (diagnostic["negative_eigenvalue_count"] > 0)
            and (minimum < 0) == (diagnostic["negative_eigenvalue_cell_count"] > 0)
            and (minimum <= 0) == (diagnostic["nonpositive_eigenvalue_cell_count"] > 0),
            "Saved-state minimum eigenvalue and negative/nonpositive counts contradict each other")
    defined = all(diagnostic[key] == 0 for key in counters[:5])
    psd = defined and minimum >= 0 and diagnostic["negative_eigenvalue_count"] == 0
    pd = defined and minimum > 0 and diagnostic["nonpositive_eigenvalue_cell_count"] == 0
    require(diagnostic.get("covariance_PSD_passed") is psd and diagnostic.get("strict_covariance_PD_passed") is pd,
            "Saved-state PSD/PD flags contradict the finite/density/eigenvalue witness")


def saved_history(outcome, scan, context):
    """Check the compact saved-frame proof independently of endpoint eligibility."""
    diagnostic = outcome["saved_snapshot_diagnostic"]
    if diagnostic["status"] != "completed_regular0_through30":
        require(scan is None, "Unclaimed/partial scan cannot be treated as a completed history")
        return {"status": diagnostic["status"], "saved_snapshots_only": True,
                "continuous_trajectory_certified": False}
    require(scan is not None and scan.get("status") == "completed_saved_snapshot_scan"
            and scan.get("native_case") == outcome["native_case"]
            and scan.get("source_run_receipt_sha256") == outcome["source_run_receipt_sha256"]
            and scan.get("runtime_context") == context
            and scan.get("all_requested_saved_frames_scanned") is True and not scan.get("failures"),
            "Completed saved-snapshot proof has a different case/native receipt/runtime/scope")
    frames = scan.get("frames", [])
    require([row.get("frame") for row in frames] == list(range(31)), "Saved history lacks exactly regular frames0--30")
    inventory = {item["filename"]: item for item in outcome["native_output_inventory"]}
    names = ["population" + str(index) for index in range(1, outcome["population_count"] + 1)]
    previous, summary, violations = -1., {}, []
    for row in frames:
        stamp = row.get("actual_time")
        require(isinstance(stamp, (int, float)) and math.isfinite(stamp) and stamp > previous,
                "Saved-snapshot times are not finite and strictly increasing")
        previous = stamp
        require(row["frame"] != 0 or stamp == 0, "Initial saved snapshot is not at time0")
        require(row["frame"] != 30 or stamp == outcome["actual_regular30_time"], "Saved frame30 time differs from native outcome")
        bindings = row.get("population_source_bindings", [])
        expected = {f"case_elc{index}_{row['frame']}.bp" for index in range(1, outcome["population_count"] + 1)}
        require(len(bindings) == len(expected) and {item["filename"] for item in bindings} == expected,
                "Saved population file identities differ")
        for item in bindings:
            pin = inventory.get(item["filename"], {})
            require(item["frame"] == row["frame"] and item["actual_time"] == stamp
                    and digest_is_valid(item.get("sha256")) and pin.get("sha256") == item["sha256"]
                    and pin.get("bytes") == item.get("bytes"), "Saved file is not bound to the native output inventory")
        for name in names + ["aggregate"]:
            validate_tensor_flags(row[name])
        bad = {name: {key: row[name].get(key) for key in ("negative_eigenvalue_cell_count",
                "minimum_pressure_eigenvalue", "nonfinite_conserved_cell_count", "covariance_undefined_cell_count")}
               for name in names + ["aggregate"] if row[name].get("covariance_PSD_passed") is not True}
        if bad:
            violations.append({"frame": row["frame"], "actual_time": stamp, "states": bad})
    for name in names + ["aggregate"]:
        rows = [row[name] for row in frames]
        failed = [row for row in frames if row[name].get("covariance_PSD_passed") is not True]
        values = [row["minimum_pressure_eigenvalue"] for row in rows if "minimum_pressure_eigenvalue" in row]
        summary[name] = {"saved_snapshots_scanned": len(rows), "saved_snapshots_not_PSD": len(failed),
            "first_non_PSD_saved_frame": failed[0]["frame"] if failed else None,
            "first_non_PSD_saved_time": failed[0]["actual_time"] if failed else None,
            "minimum_pressure_eigenvalue_over_saved_snapshots": min(values) if values else None,
            "maximum_negative_eigenvalue_cell_count": max((row.get("negative_eigenvalue_cell_count", 0) for row in rows), default=0),
            "all_saved_snapshots_PSD": not failed,
            "all_saved_snapshots_strict_PD": all(row.get("strict_covariance_PD_passed") is True for row in rows)}
    psd = all(summary[name]["all_saved_snapshots_PSD"] for name in names)
    pd = all(summary[name]["all_saved_snapshots_strict_PD"] for name in names)
    require(scan.get("summary") == diagnostic.get("summary") == summary
            and scan.get("all_scanned_populations_PSD") is psd and diagnostic.get("all_scanned_populations_PSD") is psd
            and scan.get("all_scanned_populations_strict_PD") is pd and diagnostic.get("all_scanned_populations_strict_PD") is pd
            and diagnostic.get("actual_saved_times") == [{"frame": row["frame"], "actual_time": row["actual_time"]} for row in frames],
            "Saved-history summary/PSD/PD flags differ from its recorded frame diagnostics")
    return {"status": "completed_regular0_through30", "scan_sha256": diagnostic["sha256"],
            "all_scanned_populations_PSD": psd, "all_scanned_populations_strict_PD": pd,
            "summary": summary, "non_PSD_saved_frames": violations,
            "saved_snapshots_only": True, "continuous_trajectory_certified": False}


def native_failure_state(outcome, decision, context, input_bindings):
    """Bind a terminal process failure without promoting it to a missing endpoint."""
    proof = decision.get("failure_receipt", {})
    portable_sha = hashlib.sha256((json.dumps(proof, indent=2, allow_nan=False) + "\n").encode()).hexdigest()
    evidence = outcome.get("failure_evidence", {})
    require(decision.get("status") == "failed_native_execution"
            and decision.get("failure_receipt_sha256") == portable_sha
            and evidence.get("portable_failure_receipt_sha256") == portable_sha,
            "Native failure lacks its exact classified portable failure proof")
    copied = ("native_status", "native_returncode", "source_run_receipt_sha256", "native_stop_requested",
        "regular30_endpoint_accepted", "regular30_frame_files_present", "metrics_accepted",
        "last_closed_regular_frame", "last_closed_regular_time", "last_closed_regular_bindings",
        "console_sha256", "console_bytes", "assertion_failures", "native_numerical_failure_markers",
        "native_numerical_failure_markers_scope", "last_saved_time_is_not_exact_abort_time",
        "no_failed_transient_population_or_split_operator_inferred")
    require(all(key in proof and evidence.get(key) == proof[key] for key in copied),
            "Copied terminal-failure evidence differs from its exact portable proof")
    require(proof.get("status") == "failed_native_execution" and proof.get("case") == outcome["native_case"]
            and proof.get("native_status") == outcome["native_status"] == "failed"
            and proof.get("native_returncode") == outcome.get("native_returncode")
            and isinstance(proof.get("native_returncode"), int) and proof["native_returncode"] != 0
            and proof.get("runtime_context") == context
            and proof.get("source_run_receipt_sha256") == outcome["source_run_receipt_sha256"]
            and proof.get("input_hashes") == outcome.get("input_hashes")
            and proof.get("last_saved_time_is_not_exact_abort_time") is True
            and proof.get("no_failed_transient_population_or_split_operator_inferred") is True
            and all(proof.get(key) is False for key in ("native_stop_requested", "regular30_endpoint_accepted",
                "regular30_frame_files_present", "metrics_accepted")),
            "Classified failure proof differs from actual native status/runtime/no-endpoint policy")
    frame, stamp = proof.get("last_closed_regular_frame"), proof.get("last_closed_regular_time")
    require(isinstance(frame, int) and 0 <= frame < 30 and isinstance(stamp, (int, float))
            and math.isfinite(stamp) and 0 <= stamp < 300
            and outcome.get("last_closed_regular_frame") == frame and outcome.get("last_closed_regular_time") == stamp,
            "Last closed failure output is not an actual pre-regular30 scalar observation")
    rows = outcome.get("native_output_inventory", [])
    inventory = {row["filename"]: row for row in rows}
    require(len(rows) == len(inventory) and bool(rows), "Failure native output inventory is empty/duplicated")
    bindings = proof.get("last_closed_regular_bindings", [])
    names = {f"case_elc{index}_{frame}.bp" for index in range(1, outcome["population_count"] + 1)} | {f"case_field_{frame}.bp"}
    require(len(bindings) == len(names) and {row.get("filename") for row in bindings} == names
            and not any(re.fullmatch(r"case_(?:elc[12]|field)_30\.bp", name) for name in inventory),
            "Failure proof invents a regular30 output or omits last-closed members")
    for row in bindings:
        actual = inventory.get(row["filename"], {})
        require(digest_is_valid(row.get("sha256")) and actual.get("sha256") == row["sha256"]
                and isinstance(row.get("bytes"), int) and row["bytes"] > 0 and actual.get("bytes") == row["bytes"]
                and row.get("frame") == frame and row.get("actual_time") == stamp,
                "Last-closed failure output differs from the exact native inventory")
    require(digest_is_valid(proof.get("console_sha256")) and isinstance(proof.get("console_bytes"), int)
            and proof["console_bytes"] > 0 and isinstance(proof.get("assertion_failures"), list)
            and bool(proof["assertion_failures"])
            and bool(proof.get("native_numerical_failure_markers_scope"))
            and proof.get("native_numerical_failure_markers") == outcome.get("native_failure_markers"),
            "Native failure lacks log hashes/classification or changes the narrow failure-marker evidence")
    selected = [(role, binding) for role, binding in input_bindings.items()
        if role.startswith("native_failure_proof_") and binding.get("path") == evidence.get("selected_independent_proof_path")
        and binding.get("sha256") == evidence.get("selected_independent_proof_sha256")]
    require(len(selected) == 1, "Native failure lacks its exact selected independent proof input")
    return {"portable_failure_receipt_sha256": portable_sha,
        "selected_independent_proof_path": evidence["selected_independent_proof_path"],
        "selected_independent_proof_sha256": evidence["selected_independent_proof_sha256"],
        "last_closed_regular_frame": frame, "last_closed_regular_time": stamp,
        "console_sha256": proof["console_sha256"], "console_bytes": proof["console_bytes"],
        "assertion_failures": proof["assertion_failures"], "native_returncode": proof["native_returncode"],
        "native_numerical_failure_markers_scope": proof["native_numerical_failure_markers_scope"],
        "native_stop_requested": False, "regular30_endpoint_accepted": False,
        "full_pressure_history_available": False}


def validate_independent_failure_proof(independent, portable):
    """Cross-check selected independent scalar/log/BP observations, without arrays."""
    frame, stamp = portable["last_closed_regular_frame"], portable["last_closed_regular_time"]
    require(independent.get("independent_failed_native_outcome_verified") is True
            and independent.get("native_case") == portable["case"]
            and independent.get("source_run_receipt_sha256") == portable["source_run_receipt_sha256"]
            and independent.get("native_status") == portable["native_status"]
            and independent.get("returncode") == portable["native_returncode"]
            and "native_stop" in independent and independent["native_stop"] is None
            and independent.get("last_recorded_regular_frame") == frame
            and independent.get("last_closed_saved_time") == stamp
            and independent.get("console_sha256") == portable["console_sha256"]
            and independent.get("last_saved_time_is_not_exact_abort_time") is True
            and independent.get("no_tensor_scan_or_endpoint_metrics") is True,
            "Selected independent failure proof differs from the portable native/log/time observations")
    expected = {row["filename"]: {key: row[key] for key in ("filename", "bytes", "sha256")}
                for row in portable["last_closed_regular_bindings"]}
    rows = independent.get("last_closed_BP_bindings", [])
    require(len(rows) == len(expected) and {row["filename"]: row for row in rows} == expected,
            "Independent failure raw BP hashes/sizes differ")
    metadata = independent.get("last_closed_BP_metadata", [])
    require(len(metadata) == len(expected) and {row["filename"] for row in metadata} == set(expected)
            and all(row.get("frame") == frame and row.get("actual_time") == stamp
                    and row.get("numCells") == [480, 640] for row in metadata),
            "Independent failure scalar BP metadata differs")
    indices = independent.get("output_regular_frame_indices", {})
    require(set(indices) == {name.rsplit("_", 1)[0] for name in expected}
            and all(values == list(range(frame + 1)) for values in indices.values()),
            "Independent failure inventory claims missing or invented regular frames")
    occurrences = sum(row.get("occurrences", 0) for row in portable["assertion_failures"])
    require(occurrences > 0 and independent.get("console_repeated_assertion_count") == occurrences
            and any(Path(row["source_relative_path"]).name + ":" + str(row["source_line"])
                    in str(independent.get("console_assertion_line")) for row in portable["assertion_failures"])
            and independent.get("specific_timestep_collapse_marker_absent") is (not bool(portable["native_numerical_failure_markers"]))
            and independent.get("empty_specific_marker_list_is_not_a_clean_log_claim") is True,
            "Independent assertion/narrow-marker observations differ from the classified log proof")


def admissibility_state(record, result, receipts_by_sha, scans, state):
    """Bind numerical endpoint subsets without changing the historical full-set gate."""
    defaults = {"admissibility_result_supplied": record is not None,
        "all_four_native_outcomes_completed": False, "all_four_saved_snapshot_scans_complete": False,
        "all_four_native_outcomes_observed": False, "all_four_collector_decisions_resolved": False,
        "all_four_saved_snapshot_diagnostics_resolved": False,
        "all_terminal_outcomes_and_required_histories_bound": False,
        "all_successful_native_saved_snapshot_scans_complete": False,
        "successful_native_outcome_count": 0, "failed_terminal_native_case_ids": [],
        "native_outcomes": {}, "saved_snapshot_histories": {}, "endpoint_admissible_numerical_pairs": {},
        "eligible_endpoint_analysis_case_ids": [], "valid_endpoint_pair_ids": [],
        "numerical_endpoint_subset_evidence_bound": False, "physical_trajectory_validation_claimed": False,
        "saved_histories_certify_between_output_states": False}
    if record is None:
        return defaults
    require(record.get("record_type") == "native_outcomes_and_admissibility"
            and record.get("comparison_metrics_included") is False and record.get("private_paths_included") is False,
            "Admissibility record has a different scope")
    context = record.get("runtime_context")
    require(isinstance(context, dict) and set(context) == RUNTIME_KEYS
            and context.get("source_commit") == NATIVE_SOURCE_COMMIT
            and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) for value in context.values())
            and (state["native_runtime_context"] is None or state["native_runtime_context"] == context),
            "Admissibility evidence differs from the full pinned native runtime")
    collection = receipts_by_sha.get(record.get("collector_manifest_sha256"))
    require(collection is not None and collection.get("expected_runtime_context") == context
            and collection.get("collector_sha256") == record.get("collector_sha256"),
            "Admissibility record lacks its exact supplied collector inventory/runtime")
    decisions = {item["case"]: item for item in collection.get("cases", [])}
    require(len(decisions) == len(collection.get("cases", [])), "Duplicate collector outcomes")
    outcomes = record.get("native_outcomes", [])
    expected = {value[0]: (key, value[1], value[2]) for key, value in CONTROL_IDS.items()}
    require(len(outcomes) == 4 and {item["native_case"] for item in outcomes} == set(expected),
            "Admissibility record must explicitly retain all four native outcomes")
    reported = {item["id"]: item for item in result.get("cases", [])} if result else {}
    complete, accepted, rejected, histories, native = set(), set(), set(), {}, {}
    for outcome in outcomes:
        name = outcome["native_case"]
        identifier, role, count = expected[name]
        require(outcome.get("analysis_case_id") == identifier and outcome.get("role") == role
                and outcome.get("population_count") == count, "Admissibility case identity differs")
        decision = outcome["collector_decision"]
        terminal = outcome["native_status"] != "pending_completed_receipt"
        require(outcome.get("native_outcome_observed") is terminal and outcome.get("native_outcome_terminal") is terminal,
                "Native outcome observed/terminal flags contradict its status")
        item = {"native_case": name, "native_status": outcome["native_status"],
                "native_outcome_terminal": terminal, "endpoint_collector_status": decision["status"],
                "primary_metrics_accepted": False}
        if outcome["native_status"] == "pending_completed_receipt":
            require(decision["status"] == "pending" and not outcome.get("source_run_receipt_sha256"), "Pending outcome claims a completed receipt")
            require(reported.get(identifier, {}).get("status") != "compared", "Pending native outcome has primary metrics")
        else:
            source_sha = outcome.get("source_run_receipt_sha256")
            require(digest_is_valid(source_sha) and outcome.get("runtime_context") == context,
                    "Native outcome lacks an exact source receipt/runtime binding")
            source_decision = decisions.get(name, {})
            if decision["status"] != "pending_completed_case_collection":
                require(source_decision.get("source_run_receipt_sha256") == source_sha,
                        "Admissibility decision and collector refer to different native receipts")
            item.update(source_run_receipt_sha256=source_sha, native_returncode=outcome.get("native_returncode"))
            if outcome["native_status"] == "completed_native_stop":
                stamp = outcome.get("actual_regular30_time")
                require(outcome.get("native_returncode") == 0 and outcome.get("native_execution_completed_successfully") is True
                        and not outcome.get("native_failure_markers") and outcome.get("native_regular_frame") == 30
                        and isinstance(stamp, (int, float)) and math.isfinite(stamp) and stamp >= 300
                        and outcome.get("time_controls") == {"tEnd": 600, "nFrame": 60},
                        "Native completion time/frame/return code/original controls differ")
                output_rows = outcome.get("native_output_inventory", [])
                outputs = {row["filename"]: row for row in output_rows}
                require(len(outputs) == len(output_rows) and bool(outputs)
                        and all(digest_is_valid(row.get("sha256")) and isinstance(row.get("bytes"), int)
                                and row["bytes"] > 0 for row in output_rows), "Malformed/duplicate native output inventory")
                final_rows = outcome.get("regular30_raw_output_bindings", [])
                final_names = {f"case_elc{index}_30.bp" for index in range(1, count + 1)} | {"case_field_30.bp"}
                require(len(final_rows) == len(final_names) and {row["filename"] for row in final_rows} == final_names
                        and all(outputs.get(row["filename"]) == row for row in final_rows),
                        "Regular30 raw outputs are not exactly bound to the native inventory")
                complete.add(identifier); item["actual_time"] = stamp
                if decision["status"] == "accepted_initial_and_regular30_states":
                    proof = source_decision.get("receipt", {})
                    portable_sha = hashlib.sha256((json.dumps(proof, indent=2, allow_nan=False) + "\n").encode()).hexdigest()
                    require(source_decision.get("status") == "completed_and_decoded"
                            and source_decision.get("portable_receipt_sha256") == portable_sha
                            and decision.get("portable_decoding_receipt_sha256") == portable_sha
                            and proof.get("runtime_context") == context and proof.get("source_run_receipt_sha256") == source_sha
                            and proof.get("case") == name and proof.get("actual_time") == stamp
                            and proof.get("frame") == 30 and proof.get("all_decoding_checks_passed") is True
                            and proof.get("source_comparison_is_regular_frame30") is True
                            and proof.get("original_dirty_build_reproduced") is False
                            and proof.get("input_hashes") == outcome.get("input_hashes"),
                            "Accepted endpoint lacks its exact portable/native completion proof")
                    exports = proof.get("initial_exports", []) + proof.get("exports", [])
                    expected_exports = final_names | {f"case_elc{index}_0.bp" for index in range(1, count + 1)}
                    require(len(exports) == len(expected_exports) and {row["filename"] for row in exports} == expected_exports,
                            "Endpoint proof does not contain every population at initial/regular30 and the final field")
                    for row in exports:
                        raw = outputs.get(row["filename"], {})
                        require(raw.get("bytes") == row.get("source_bytes") and raw.get("sha256") == row.get("source_sha256")
                                and row.get("actual_time") == (0 if row.get("frame") == 0 else stamp)
                                and row.get("frame") in (0, 30), "Decoded endpoint is not bound to the native raw output")
                        if "state_conformance" in row:
                            require(row["state_conformance"].get("passed") is True, "Accepted population failed endpoint conformance")
                    conformance = [{"filename": row["filename"], "frame": row["frame"], "actual_time": row["actual_time"],
                        "source_BP_sha256": row["source_sha256"], "numeric_export_sha256": row["numeric_export_sha256"],
                        "state_conformance": row["state_conformance"]} for row in exports if "state_conformance" in row]
                    require(decision.get("initial_and_regular30_population_conformance") == conformance,
                            "Accepted endpoint summary differs from its exact decoded-population proof")
                    item["portable_decoding_receipt_sha256"] = portable_sha
                    accepted.add(identifier)
                elif decision["status"] == "rejected_nonconforming_state":
                    require(source_decision.get("status") == "failed_validation_or_execution"
                            and source_decision.get("error_type") == "ConformanceError"
                            and decision.get("metrics_accepted") is False and decision.get("no_clipping_or_guard_relaxation") is True
                            and decision.get("conformance_failure") == source_decision.get("conformance_failure")
                            and bool(decision.get("conformance_failure")), "Rejected endpoint lacks its strict conformance proof")
                    rejected.add(identifier); item["rejection_reason"] = decision["conformance_failure"]
                elif decision["status"] == "pending_completed_case_collection":
                    require(source_decision.get("status") in {"pending_no_completed_receipt", "running_without_completed_receipt"},
                            "Pending collection claims a resolved collector decision")
                else:
                    raise ValueError("Completed native outcome lacks an accepted/rejected final endpoint decision")
            else:
                require(outcome["native_status"] in {"failed", "failed_controller_guard"}
                        and decision["status"] == "not_accepted_native_execution_failure" and decision.get("metrics_accepted") is False,
                        "Unsuccessful native outcome cannot supply primary metrics")
                require(outcome.get("actual_regular30_time") is None and outcome.get("native_regular_frame") != 30
                        and not outcome.get("regular30_raw_output_bindings")
                        and outcome["saved_snapshot_diagnostic"]["status"] == "not_applicable_native_execution_failed",
                        "Terminal native failure cannot claim a regular30 endpoint or a complete saved history")
                failure = native_failure_state(outcome, source_decision, context, record.get("input_bindings", {}))
                item.update(failure_evidence=failure, last_closed_regular_frame=failure["last_closed_regular_frame"],
                            last_closed_regular_time=failure["last_closed_regular_time"])
                item["rejection_reason"] = {"native_status": outcome["native_status"], "native_returncode": failure["native_returncode"],
                    "assertion_failures": failure["assertion_failures"], "failure_markers": outcome.get("native_failure_markers", []),
                    "scope": "Terminal native execution failure; last closed output does not identify the failing transient/species/time."}
        eligibility = True if identifier in accepted else False if identifier in rejected or decision["status"] == "not_accepted_native_execution_failure" else None
        collector_resolved = decision["status"] in {"accepted_initial_and_regular30_states", "rejected_nonconforming_state", "not_accepted_native_execution_failure"}
        history_resolved = outcome["saved_snapshot_diagnostic"]["status"] in {"completed_regular0_through30", "scanner_failed", "not_applicable_native_execution_failed"}
        require(outcome.get("endpoint_metrics_eligible") is eligibility
                and outcome.get("collector_decision_resolved") is collector_resolved
                and outcome.get("saved_snapshot_diagnostic_resolved") is history_resolved,
                "Endpoint eligibility or collector/history resolution flags contradict the actual decisions")
        item.update(endpoint_metrics_eligible=eligibility, collector_decision_resolved=collector_resolved,
                    saved_snapshot_diagnostic_resolved=history_resolved)
        case = reported.get(identifier, {})
        if identifier not in accepted:
            require(case.get("status") != "compared" and "metrics" not in case and case.get("metrics_accepted") is not True,
                    "Ineligible/rejected endpoint contains primary comparison metrics")
            if outcome["native_status"] == "failed" and result is not None:
                failure = item["failure_evidence"]
                require(case.get("status") == "failed_native_execution" and case.get("metrics_accepted") is False
                        and case.get("native_execution_successful") is False
                        and case.get("source_run_receipt_sha256") == item["source_run_receipt_sha256"]
                        and case.get("native_returncode") == item["native_returncode"]
                        and case.get("last_closed_regular_frame") == failure["last_closed_regular_frame"]
                        and case.get("last_closed_regular_time") == failure["last_closed_regular_time"]
                        and case.get("failure_receipt", {}).get("sha256") == failure["portable_failure_receipt_sha256"],
                        "Comparison report hides or misbinds the terminal native execution failure")
        elif case.get("status") == "compared":
            binding = case.get("completed_case_receipt", {})
            require(case.get("runtime_context") == context and case.get("actual_time") == item["actual_time"]
                    and binding.get("sha256") == item["portable_decoding_receipt_sha256"]
                    and binding.get("source_run_receipt_sha256") == item["source_run_receipt_sha256"],
                    "Endpoint comparison lacks exact runtime/portable/native receipt bindings")
            item["primary_metrics_accepted"] = True
        histories[identifier] = saved_history(outcome, scans.get(name), context)
        native[identifier] = item
    for pair in result.get("paired_effects", []) if result else []:
        if pair.get("baseline") not in accepted or pair.get("matched") not in accepted:
            require(pair.get("status") != "computed" and "quantities" not in pair,
                    "Unresolved/rejected endpoints contain paired primary metrics")
    for direct in result.get("clean_unmatched_vs_archived_source", []) if result else []:
        if direct.get("clean") in CONTROL_IDS and direct["clean"] not in accepted:
            require(direct.get("status") != "computed" and "moment_quantities" not in direct
                    and "all_eight_stored_field_components" not in direct,
                    "Unresolved/rejected native endpoint contains clean/archive primary metrics")
    scan_count = sum(item["status"] == "completed_regular0_through30" for item in histories.values())
    require(record.get("native_completed_outcome_count") == len(complete)
            and record.get("endpoint_collector_accepted_count") == len(accepted)
            and record.get("endpoint_collector_rejected_count") == len(rejected)
            and record.get("completed_saved_snapshot_scan_count") == scan_count
            and record.get("all_four_native_outcomes_completed") is (len(complete) == 4)
            and record.get("all_four_saved_snapshot_scans_complete") is (scan_count == 4),
            "Admissibility outcome/scan counts do not match the explicit evidence")
    terminal_count = sum(item["native_outcome_terminal"] for item in native.values())
    require(record.get("observed_terminal_native_outcome_count") == terminal_count
            and record.get("all_four_native_outcomes_observed") is (terminal_count == 4)
            and record.get("all_four_collector_decisions_resolved") is all(item["collector_decision_resolved"] for item in native.values())
            and record.get("all_four_saved_snapshot_diagnostics_resolved") is all(item["saved_snapshot_diagnostic_resolved"] for item in native.values())
            and sorted(record.get("endpoint_eligible_case_ids", [])) == sorted(accepted)
            and sorted(record.get("endpoint_rejected_case_ids", [])) == sorted(rejected),
            "Observed/resolved/eligible outcome summaries contradict their explicit states")
    pairs = {}
    for pair in result.get("paired_effects", []) if result else []:
        if pair.get("status") != "computed":
            continue
        identifier = pair["id"]
        require(identifier in PAIR_IDS and (pair.get("baseline"), pair.get("matched")) == PAIR_IDS[identifier], "Numerical pair identities differ")
        baseline, matched = PAIR_IDS[identifier]
        require(all(native[name]["primary_metrics_accepted"] for name in (baseline, matched))
                and pair.get("baseline_actual_time") == native[baseline]["actual_time"]
                and pair.get("matched_actual_time") == native[matched]["actual_time"]
                and pair.get("time_interpolation_performed") is False,
                "Computed pair includes an unbound or ineligible endpoint")
        archive = "archived_one_fluid" if CONTROL_IDS[baseline][2] == 1 else "archived_two_fluid"
        checks = [entry for entry in result.get("clean_unmatched_vs_archived_source", [])
                  if entry.get("clean") == baseline and entry.get("archived") == archive and entry.get("status") == "computed"]
        archived = reported.get(archive, {})
        require(len(checks) == 1 and archived.get("status") == "compared" and archived.get("kind") == "archived_source"
                and archived.get("frame") == 30 and checks[0].get("native_frame") == 30
                and checks[0].get("clean_actual_time") == native[baseline]["actual_time"]
                and checks[0].get("archived_actual_time") == archived.get("actual_time")
                and checks[0].get("time_interpolation_performed") is False,
                "Numerical endpoint pair lacks its clean-base versus archived-source comparison")
        pairs[identifier] = {"baseline": baseline, "matched": matched, "runtime_context": context,
            "baseline_actual_time": native[baseline]["actual_time"], "matched_actual_time": native[matched]["actual_time"],
            "endpoint_receipt_bindings": {name: {key: native[name][key] for key in
                ("source_run_receipt_sha256", "portable_decoding_receipt_sha256")} for name in (baseline, matched)},
            "clean_versus_archive": {"clean": baseline, "archived": archive, "clean_actual_time": native[baseline]["actual_time"],
                "archived_actual_time": archived["actual_time"], "time_interpolation_performed": False},
            "saved_snapshot_history_statuses": {name: histories[name]["status"] for name in (baseline, matched)},
            "saved_snapshot_PSD_violations_present": any(histories[name].get("all_scanned_populations_PSD") is False for name in (baseline, matched)),
            "scope": "Endpoint-admissible NUMERICAL sensitivity only; no physical-trajectory, causal or convergence validation."}
    failed_native = {name for name, outcome in native.items()
                     if outcome["native_outcome_terminal"] and outcome["native_status"] != "completed_native_stop"}
    successful_scans = all(histories[name]["status"] == "completed_regular0_through30" for name in complete)
    terminal_coverage = (terminal_count == 4 and (set(complete) | failed_native) == set(CONTROL_IDS)
        and all(item["collector_decision_resolved"] for item in native.values())
        and all(item["saved_snapshot_diagnostic_resolved"] for item in native.values())
        and successful_scans
        and all(histories[name]["status"] == "not_applicable_native_execution_failed" for name in failed_native))
    require(record.get("all_terminal_outcomes_and_required_histories_bound", terminal_coverage) is terminal_coverage,
            "Terminal-outcome/history coverage claim differs from the actual evidence")
    return {**defaults, "native_outcomes": native, "saved_snapshot_histories": histories,
        "all_four_native_outcomes_completed": len(complete) == 4,
        "all_four_saved_snapshot_scans_complete": scan_count == 4,
        "all_four_native_outcomes_observed": terminal_count == 4,
        "all_four_collector_decisions_resolved": all(item["collector_decision_resolved"] for item in native.values()),
        "all_four_saved_snapshot_diagnostics_resolved": all(item["saved_snapshot_diagnostic_resolved"] for item in native.values()),
        "all_terminal_outcomes_and_required_histories_bound": terminal_coverage,
        "all_successful_native_saved_snapshot_scans_complete": successful_scans,
        "successful_native_outcome_count": len(complete), "failed_terminal_native_case_ids": sorted(failed_native),
        "endpoint_collector_accepted_case_ids": sorted(accepted), "endpoint_collector_rejected_case_ids": sorted(rejected),
        "endpoint_admissible_numerical_pairs": pairs,
        "eligible_endpoint_analysis_case_ids": sorted(name for name in accepted if native[name]["primary_metrics_accepted"]),
        "valid_endpoint_pair_ids": sorted(pairs),
        "numerical_endpoint_subset_evidence_bound": terminal_coverage and bool(pairs),
        "admissibility_native_runtime_context": context}


def evidence_entry(path, commit=None, expected=None):
    """Hash a portable project file; optionally require exact committed bytes."""
    if commit is not None:
        return committed_entry(path, commit, expected)
    actual, relative = relative_path(path)
    digest = sha(actual)
    require(expected is None or digest == expected, "Evidence file bytes differ: " + relative)
    return {"path": relative, "sha256": digest}


def load_admissibility_evidence(path, receipts_by_sha, commit=None):
    """Read/hash only; used by publication and plotting without native actions."""
    entry = evidence_entry(path, commit)
    entries, scans = {entry["path"]: entry}, {}
    record = read(ROOT / entry["path"])
    for key, source in {"builder_sha256": "experiments/build_gkeyll_admissibility.py",
            "scanner_sha256": "experiments/scan_gkeyll_saved_states.py",
            "collector_sha256": "experiments/collect_completed_gkeyll_cases.py"}.items():
        source_entry = evidence_entry(source, commit)
        entries[source_entry["path"]] = source_entry
        require(record.get(key) == source_entry["sha256"], "Admissibility evidence/code differs: " + key)
    dependencies = record.get("input_bindings")
    require(isinstance(dependencies, dict) and dependencies, "Admissibility record lacks portable input bindings")
    require({"collector_manifest", "expected_context", "independent_diagnosis", "independent_details",
             "predicate_provenance", "runtime_file_manifest"}.issubset(dependencies), "Missing mandatory admissibility input roles")
    for binding in dependencies.values():
        require(isinstance(binding, dict) and isinstance(binding.get("path"), str)
                and digest_is_valid(binding.get("sha256")), "Malformed portable admissibility input binding")
        dependency = evidence_entry(binding["path"], commit, binding["sha256"])
        entries[dependency["path"]] = dependency
        if binding.get("source_full_record_sha256") is not None:
            require(digest_is_valid(binding["source_full_record_sha256"]), "Invalid original-record source anchor")
            payload = read(ROOT / dependency["path"])
            require(payload.get("source_full_record_sha256", dependency["sha256"]) == binding["source_full_record_sha256"],
                    "Selected public evidence and its original-record source anchor differ")
    for outcome in record.get("native_outcomes", []):
        diagnostic = outcome.get("saved_snapshot_diagnostic", {})
        if diagnostic.get("status") != "completed_regular0_through30":
            continue
        name = outcome["native_case"]
        require(name in {item[0] for item in CONTROL_IDS.values()}
                and diagnostic.get("filename") == name + ".json", "Unexpected portable saved-snapshot filename")
        scan_path = diagnostic.get("path", "results/gkeyll-saved-state-scans/" + diagnostic["filename"])
        resolved_scan = (ROOT / scan_path).resolve()
        require(resolved_scan.is_relative_to((ROOT / "results/gkeyll-saved-state-scans").resolve())
                and resolved_scan.name == diagnostic["filename"], "Saved-snapshot path leaves its portable evidence subtree")
        scan_entry = evidence_entry(scan_path, commit, diagnostic["sha256"])
        entries[scan_entry["path"]] = scan_entry
        scans[name] = read(ROOT / scan_entry["path"])
        require(scans[name].get("scanner_sha256") == record["scanner_sha256"], "Saved-snapshot scanner bytes differ")
    require(record.get("collector_manifest_sha256") in receipts_by_sha,
            "Supply the exact admissibility collector inventory with --controls-receipt")
    witness = record.get("independent_endpoint_witness", {})
    predicate = record.get("native_predicate_provenance", {})
    for role, digest in {"collector_manifest": record.get("collector_manifest_sha256"),
            "independent_diagnosis": witness.get("independent_diagnosis_sha256"),
            "independent_details": witness.get("independent_details_sha256"),
            "predicate_provenance": predicate.get("independent_evidence_sha256"),
            "runtime_file_manifest": record.get("runtime_context", {}).get("runtime_file_manifest_sha256")}.items():
        require(dependencies[role]["sha256"] == digest, "Admissibility input role/hash differs: " + role)
    require(read(ROOT / dependencies["expected_context"]["path"]) == record.get("runtime_context"),
            "Selected expected context differs from the actual runtime context")
    collection = receipts_by_sha[record["collector_manifest_sha256"]]
    for outcome in record.get("native_outcomes", []):
        if outcome.get("native_status") != "failed":
            continue
        evidence = outcome.get("failure_evidence", {})
        matches = [binding for role, binding in dependencies.items() if role.startswith("native_failure_proof_")
            and binding["path"] == evidence.get("selected_independent_proof_path")
            and binding["sha256"] == evidence.get("selected_independent_proof_sha256")]
        require(len(matches) == 1, "Selected independent failure input is missing or ambiguous")
        decision = next((item for item in collection["cases"] if item["case"] == outcome["native_case"]), {})
        require(decision.get("status") == "failed_native_execution", "Independent failure proof has no classified collector counterpart")
        validate_independent_failure_proof(read(ROOT / matches[0]["path"]), decision["failure_receipt"])
    evidence_shas = {item["sha256"] for item in entries.values()}
    for digest in (witness.get("independent_diagnosis_sha256"), witness.get("independent_details_sha256"),
                   predicate.get("independent_evidence_sha256")):
        require(digest_is_valid(digest) and digest in evidence_shas, "Independent admissibility witness lacks input evidence")
    return record, scans, entries


def validate_runtime_contexts(state, commit=None):
    entries = {}
    contexts = [context for context in (state["native_runtime_context"], state.get("admissibility_native_runtime_context")) if context]
    for context in contexts:
        for key, path in {"controller_sha256": "experiments/run_gkeyll_controls.py",
                "runtime_file_manifest_sha256": "data/gkeyll-clean9663-file-manifest.json",
                "dependency_lock_sha256": "data/gkeyll-clean9663-dependencies.json",
                "matched_init_conformance_sha256": "results/gkeyll-matched-init-conformance.json"}.items():
            entry = evidence_entry(path, commit)
            entries[entry["path"]] = entry
            require(context.get(key) == entry["sha256"], "Completed native runtime differs from pinned evidence: " + key)
        runtime = read(ROOT / "data/gkeyll-clean9663-file-manifest.json")
        init_gate = read(ROOT / "results/gkeyll-matched-init-conformance.json")
        require(runtime.get("source_commit") == context["source_commit"] == NATIVE_SOURCE_COMMIT
                and runtime.get("installed_solver_files_sha256", {}).get("bin/gkyl") == context.get("executable_sha256")
                and init_gate.get("all_checks_passed") is True
                and {item.get("id") for item in init_gate.get("cases", [])} == {"1-fluid-aggregate-matched", "2-fluid-aggregate-matched"}
                and all(item.get("solver_executable_sha256") == context.get("executable_sha256") for item in init_gate["cases"]),
                "Native context executable/source differs from the exact runtime/init gate")
    return entries


def validate_numerical_subset_evidence(comparison_path, decoding_paths, admissibility_path, *, commit=None):
    """Read-only shared gate for endpoint-subset plots/adapters.

    All paths must be project-local. With commit=None, current file/code/runtime
    hashes are checked; an explicit commit additionally pins every evidence byte
    read here. This never runs native code or writes a derived artifact. CSV/norm
    verification and publication source-pin coverage remain caller obligations.
    Final numerical subsets require all four terminal outcomes, resolved decisions,
    full saved scans for successful cases, explicit unavailable failed histories,
    and an actual same-runtime endpoint pair. Failure never supplies an endpoint.
    """
    result_entry = evidence_entry(comparison_path, commit)
    result = read(ROOT / result_entry["path"])
    analyzer = evidence_entry("experiments/analyze_gkeyll_controls.py", commit)
    helper = evidence_entry("scripts/make_paper_data.py", commit)
    require(result.get("script_sha256") == analyzer["sha256"],
            "Numerical subset result differs from the current analyzer")
    config = evidence_entry("data/gkeyll-completed-control-cases.json", commit)
    require(result.get("config_sha256") == config["sha256"], "Numerical subset result/config differs")
    entries, receipts = {item["path"]: item for item in (result_entry, config, analyzer, helper)}, {}
    for path in decoding_paths:
        entry = evidence_entry(path, commit)
        entries[entry["path"]] = entry
        receipts[entry["sha256"]] = read(ROOT / entry["path"])
    record, scans, added = load_admissibility_evidence(admissibility_path, receipts, commit)
    entries.update(added)
    state = controls_state(result, list(receipts.values()))
    state.update(admissibility_state(record, result, receipts, scans, state))
    entries.update(validate_runtime_contexts(state, commit))
    state["read_only_evidence_bindings"] = list(entries.values())
    return state


def write_numerical_table(result):
    g = result['groups']
    stability = g['finite_relaxation_stability']['finite_relaxation_mode']
    current = g['initial_current']['rows'][1]
    pressure = g['initial_pressure']['rows'][1]
    bound = g['conditioning_counterexample']['conditioned_example']
    rows = [
        ('Initial moment current at $Y=16.05d_e$', f"{100*current['relative_current_deficit']:.4f}\\% below staggered curl"),
        ('Initial $P_{zz}/p_{\\rm fl}$ at that row', f"{pressure['Pzz_ratio']:.9f}"),
        ('Exact mixture identities', 'All scalar and tensor checks pass'),
        ('Symmetry-plane continuity', 'Zero normal velocity; increasing density'),
        ('Conditioned relative-error example', f"{bound['relative_error']:.6f} $\\le$ {bound['sufficient_relative_error_bound']:.6f}"),
        ('Identical one-fluid lower moments', 'Different third moments'),
        ('Finite-relaxation mode growth', f"${stability['growth']:.9f}\\,\\omega_{{pe}}$"),
        ('Homogeneous relaxation over $300/\\omega_{pe}$', f"{100*g['isotropization_entropy']['anisotropy_remaining_fraction']:.4f}\\% anisotropy remains"),
    ]
    table = ['\\begin{table}[tbp]', '\\centering', '\\small',
             '\\caption{Selected verification outcomes. The code, data definitions and scope limits distinguish initial-state reanalysis from independent continuum tests.}',
             '\\label{tab:verification}', '\\begin{tabular}{p{.48\\linewidth}p{.43\\linewidth}}',
             '\\toprule', 'Check & Outcome \\\\', '\\midrule']
    table += [a + ' & ' + b + r' \\' for a, b in rows]
    table += ['\\bottomrule', '\\end{tabular}', '\\end{table}', '']
    (ROOT / 'paper/results-table.tex').write_text('\n'.join(table), encoding='utf-8', newline='\n')

    return len(rows)


def execution_text(pin, result, code_pin_sha, output_manifest_sha):
    environment, groups = result["environment"], result["groups"]
    lines = [r"\section{Pinned execution record}", r"\label{app:execution}",
        "The following immutable commit pins the checked code, input decks and evidence files:",
        r"\begin{quote}\small", r"\href{" + REPOSITORY + "/tree/" + pin["commit"] +
        r"}{\texttt{" + pin["commit"] + "}}", r"\end{quote}",
        "Every source/input/evidence hash listed in the inventories was checked against that commit. "
        "The inventories and manuscript files generated afterward are derived release outputs.",
        r"\paragraph{Historical original verification.}",
        "The original eight-group execution below retains its original timestamp, environment and results. "
        "Its four numerical code files are byte-identical at the pinned commit. This does not assert "
        "that every later analysis was executed together in that historical run.",
        r"\begin{verbatim}", "Started UTC: " + environment["started_at_utc"],
        "Python: " + environment["python"].splitlines()[0], "NumPy: " + environment["numpy"],
        "h5py: " + environment["h5py"]]
    lines += ["PASS: " + name for name in groups]
    lines += ["All assertions passed: true", "Exit status: 0", r"\end{verbatim}",
        "The selected verification table is unchanged from this original eight-group record.",
        r"\paragraph{Reproduction and later analyses.}", r"\begin{verbatim}",
        "git clone " + REPOSITORY + ".git", "cd counterstreaming-heatflux-audit",
        "git checkout " + pin["commit"], "python -m pip install -r requirements.txt",
        "python experiments/fetch_data.py", "python experiments/data_checks.py",
        "python -X utf8 experiments/verify.py", "python -X utf8 experiments/make_figures.py",
        "python experiments/profile_sensitivity.py",
        "python experiments/revision_data.py --inventory --fetch",
        "# Separate Linux ADIOS2 reader environment:", "python experiments/revision_data.py --decode-bp",
        "python experiments/revision_data.py --compare", "python experiments/thermal_loading.py",
        r"\end{verbatim}",
        "The pin additionally covers the portable full-PIC moment exporter, BP reader, matched-input "
        "preparer/initializer, native control runner, completed-output collector and comparison analyzer. "
        "Their CLI help and the data documentation specify the required cache paths and immutable run pins; "
        "the code itself does not imply that an uncompleted case was measured."]
    if pin["full_archive_checksums_verified"]:
        lines += ["The three complete source ZIP archives passed byte-size and publisher-MD5 checks, "
                  "with full SHA-256 hashes and selected-member bindings recorded in "
                  r"\nolinkurl{data/full-archive-verification.json}."]
    else:
        lines += ["This execution record does not assert complete-source-archive checksum verification."]
    state = pin["controls_state"]
    if state["native_runtime_context"]:
        lines += ["The native runs retain their recorded launch-code revision "
                  r"\texttt{" + state["native_runtime_context"]["research_code_revision"] +
                  "}; the final evidence pin above additionally contains the later analysis outputs."]
    if state["all_four_completed_and_compared"]:
        lines += ["All four clean-base native controls have bound native-stop/endpoint-decoding receipts and "
                  "endpoint numerical comparisons in the supplied result. They retain the original 600/60 controls "
                  "and use regular frame30 at each recorded actual time; later regular/forced frames are excluded. "
                  "The exact dirty 2023 executable remains unidentified, so clean-base baseline fidelity is "
                  "assessed against archived outputs rather than asserted from source ancestry. This full-set "
                  "endpoint flag does not certify physically admissible trajectories."]
    elif state["comparison_result_supplied"] or state["validated_native_completion_count"]:
        lines += [f"The supplied result lists {state['valid_compared_case_count']} control-case "
                  f"endpoint comparisons and {state['validated_native_completion_count']} accepted endpoint-decoding "
                  "receipts. The all-four completed-and-compared flag remains false; pending or rejected "
                  "cases remain explicit in the pinned inventories."]
    else:
        lines += ["No final four-case matched-state comparison is included in this execution record. "
                  "Run preparation, initialization conformance and cost probes alone are not completed "
                  "reconnection controls."]
    lines += [r"\paragraph{Native outcomes, endpoint eligibility and saved histories.}"]
    if state.get("admissibility_result_supplied"):
        outcomes = state["native_outcomes"]
        completed_count = sum(item["native_status"] == "completed_native_stop" for item in outcomes.values())
        failed_native = state["failed_terminal_native_case_ids"]
        rejected = state["endpoint_collector_rejected_case_ids"]
        lines += [f"The separate admissibility record retains all four native outcomes: {completed_count} "
                  f"normal regular30 completions, {len(failed_native)} terminal execution failures, and "
                  f"{len(rejected)} endpoints rejected by the strict state guard "
                  "in the supplied evidence. Native completion and positive-definite endpoint eligibility are "
                  "separate facts. Rejected endpoints have no accepted primary comparison metrics."]
        if failed_native:
            lines += ["The failed native cases are " + ", ".join(r"\nolinkurl{" + name + "}" for name in failed_native)
                + ". They supply no accepted regular30 endpoint or comparison metrics. Their pressure histories "
                "are explicitly unavailable; no regular0--30 scan is inferred from the available earlier outputs."]
            for identifier in failed_native:
                failure = outcomes[identifier]["failure_evidence"]
                lines += [r"\nolinkurl{" + identifier + "}: its last closed regular output is frame "
                    + str(failure["last_closed_regular_frame"]) + r" at $t\omega_{pe}="
                    + repr(failure["last_closed_regular_time"]) + "$. The exact native/portable receipt and console "
                    "hashes are retained with the selected independent failure proof. This scalar observation "
                    "does not identify the failing transient, species or update time."]
        if rejected:
            lines += ["The rejected endpoint cases are " + ", ".join(r"\nolinkurl{" + name + "}" for name in rejected) + "."]
        pairs = state["endpoint_admissible_numerical_pairs"]
        if pairs:
            lines += ["The bound endpoint-admissible NUMERICAL sensitivity pairs are " + ", ".join(
                r"\nolinkurl{" + name + "}" for name in pairs) + ". Each retains its exact runtime, native/portable "
                "receipt hashes, actual endpoint times and clean-base versus archived-source check. "
                "These endpoint contrasts do not establish physical causality, convergence or valid dynamics."]
        else:
            lines += ["No endpoint-admissible paired numerical contrast is established by the supplied evidence."]
        for identifier, history in state["saved_snapshot_histories"].items():
            if history["status"] != "completed_regular0_through30":
                qualification = " following terminal native failure" if history["status"] == "not_applicable_native_execution_failed" else ""
                lines += [r"\nolinkurl{" + identifier + "}: its regular0--30 pressure-history diagnostic is unavailable" + qualification + "."]
                continue
            failed = history["non_PSD_saved_frames"]
            if failed:
                frames = ", ".join(str(row["frame"]) for row in failed)
                lines += [r"\nolinkurl{" + identifier + "}: the saved-state covariance test fails at regular frames "
                    + frames + ". These history failures remain attached to any eligible endpoint contrast."]
            else:
                lines += [r"\nolinkurl{" + identifier + "}: every scanned population is positive semidefinite "
                    "at saved regular frames0--30; strict positive definiteness is recorded separately."]
        lines += ["Saved snapshots do not certify the intervening timesteps, locate the first invalid update, "
                  "or identify the operator that produced a loss of admissibility. No state was clipped or repaired."]
    else:
        lines += ["No separate all-outcome/saved-snapshot admissibility record is supplied. Endpoint decoding "
                  "alone cannot certify a physical trajectory or a saved-history claim."]
    lines += ["Third-diagnostic normalization qualifications remain attached to the heat-flux comparisons. "
        "No native deposited-current comparison or inhomogeneous-sheet eigenanalysis is claimed.",
        r"\paragraph{Compact file record.}",
        "The complete code hashes are grouped in code-pin.json; the separate output manifest groups "
        "revision results, supporting evidence and optional final control records. Only these fixed summary "
        "rows are repeated here, so a larger evidence inventory does not lengthen the PDF hash table.",
        r"\begin{center}", r"\scriptsize", r"\begin{tabular}{@{}p{.38\linewidth}p{.59\linewidth}@{}}",
        r"\toprule", r"File & SHA-256 \\", r"\midrule"]
    for path, digest in [("results/verification.json", pin["verification_sha256"]),
                         ("results/code-pin.json", code_pin_sha),
                         ("results/execution-output-manifest.json", output_manifest_sha)]:
        lines.append(r"\nolinkurl{" + path + r"} & \texttt{" + digest + r"} \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}",
        "This is an author-environment execution record, not third-party certification or independent human peer review.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls-result", type=Path,
        help="Optional committed results/gkeyll-control-comparison.json; absence never implies completion")
    parser.add_argument("--controls-receipt", type=Path, action="append", default=[],
        help="Repeat for committed portable receipts, normally results/gkeyll-control-decoding.json")
    parser.add_argument("--admissibility-results", type=Path,
        help="Optional committed results/gkeyll-admissibility.json; binds outcomes and saved histories separately from endpoint metrics")
    parser.add_argument("--check-only", action="store_true", help="Verify HEAD/evidence only; generate no files")
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Expected full HEAD commit")
    result = read(ROOT / "results/verification.json")
    require(result["all_assertions_passed"] is True and len(result["groups"]) == 8,
            "Historical eight-group verification did not pass")
    sources = {}
    for entry in result["environment"]["source_files"]:
        sources[entry["path"]] = committed_entry(entry["path"], commit, entry["sha256"])
    require(len(sources) == 4, "Unexpected original code-file count")
    historical_sources = list(sources.values())
    extras = ["experiments/" + name for name in (*REVISION_CODE, *CONTROL_CODE)]
    extras += ["experiments/make_figures.py", "scripts/make_paper_data.py"]
    for relative in extras:
        sources[relative] = committed_entry(relative, commit)
    provenance = read(ROOT / "data/provenance.json")
    inputs = [committed_entry("data/input-decks/" + entry["file"], commit, entry["sha256"])
              for entry in provenance["input_decks"]]
    inputs += [committed_entry("data/provenance.json", commit)]
    inputs += [committed_entry(path, commit) for path in
               ("requirements.txt", "experiments/matched-control-plan.md")]
    verification = committed_entry("results/verification.json", commit)
    revision_outputs = [committed_entry(path, commit) for path in REVISION_OUTPUTS]
    revision = read(ROOT / "results/revision-data.json")
    require(revision["all_checks_passed"] is True, "Archived-fluid revision checks did not pass")
    require(revision["revision_script_sha256"] == sha(ROOT / "experiments/revision_data.py"),
            "Archived-fluid revision script differs from its recorded bytes")
    support = [committed_entry(path, commit) for path in SUPPORT_OUTPUTS if (ROOT / path).is_file()]
    archive = read(ROOT / "data/full-archive-verification.json") if (ROOT / "data/full-archive-verification.json").is_file() else {}
    archive_verified = (archive.get("all_three_archives_and_18_selected_inputs_verified") is True
        and len(archive.get("archives", [])) == 3
        and all(item.get("full_archive_checksum_verified") is True for item in archive["archives"]))
    control_entries, receipt_payloads, receipts_by_sha, control_result = {}, [], {}, None
    for path in args.controls_receipt:
        entry = committed_entry(path, commit)
        control_entries[entry["path"]] = entry
        payload = read(ROOT / entry["path"])
        receipt_payloads.append(payload)
        receipts_by_sha[entry["sha256"]] = payload
    if args.controls_result:
        entry = committed_entry(args.controls_result, commit)
        control_entries[entry["path"]] = entry
        control_result = read(ROOT / entry["path"])
        require(control_result.get("script_sha256") == sha(ROOT / "experiments/analyze_gkeyll_controls.py"),
                "Control result does not match the pinned analyzer")
        config = committed_entry("data/gkeyll-completed-control-cases.json", commit)
        require(control_result.get("config_sha256") == config["sha256"], "Control result/config hash differs")
        control_entries[config["path"]] = config
        for path in ("data/provenance-gkeyll-control-comparison.json",
                     "data/derived/gkeyll-control-comparison-profiles.csv"):
            if (ROOT / path).is_file():
                item = committed_entry(path, commit)
                control_entries[item["path"]] = item
                if path.endswith("-profiles.csv"):
                    require(control_result.get("profile_export_sha256") == item["sha256"],
                            "Control profile/result hash differs")
                else:
                    proof = read(ROOT / path)
                    require(proof.get("result_sha256") == entry["sha256"]
                            and proof.get("script_sha256") == control_result["script_sha256"]
                            and proof.get("config_sha256") == config["sha256"],
                            "Control provenance/result/code/config hashes differ")
    state = controls_state(control_result, receipt_payloads)
    admissibility, scans = None, {}
    if args.admissibility_results:
        admissibility, scans, entries = load_admissibility_evidence(args.admissibility_results, receipts_by_sha, commit)
        control_entries.update(entries)
    state.update(admissibility_state(admissibility, control_result, receipts_by_sha, scans, state))
    validate_runtime_contexts(state, commit)
    require(not state["all_four_completed_and_compared"] or archive_verified,
            "Completed control claim lacks verified complete source archives")
    require(not state["endpoint_admissible_numerical_pairs"] or archive_verified,
            "Numerical endpoint pair lacks verified complete source archives")
    output_manifest = {"commit": commit, "all_listed_evidence_bytes_match_commit": True,
        "groups": {"revision_outputs": revision_outputs, "supporting_evidence": support,
                   "optional_control_outputs": list(control_entries.values())},
        "controls_state": state,
        "scope": "Hash inventory of committed evidence; presence is not a claim that every optional run completed."}
    manifest_bytes = (json.dumps(output_manifest, indent=2) + "\n").encode()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    pin = {"commit": commit, "repository": REPOSITORY,
        "verification_sha256": verification["sha256"], "source_files": list(sources.values()),
        "input_files": inputs, "revision_outputs": revision_outputs,
        "original_eight_group_code_bytes_unchanged": True,
        "historical_original_source_files": historical_sources,
        "historical_original_started_at_utc": result["environment"]["started_at_utc"],
        "full_archive_checksums_verified": archive_verified, "controls_state": state,
        "output_manifest": {"path": "results/execution-output-manifest.json", "sha256": manifest_sha},
        "all_listed_source_input_evidence_bytes_match_commit": True,
        "generated_inventories_are_derived_outputs_not_claimed_at_prior_pin": True}
    summary = {"code_commit": commit, "groups": len(result["groups"]), "pinned_source_files": len(sources),
               "controls_completed_and_compared": state["all_four_completed_and_compared"],
               "numerical_endpoint_subset_evidence_bound": state["numerical_endpoint_subset_evidence_bound"],
               "endpoint_admissible_numerical_pairs": list(state["endpoint_admissible_numerical_pairs"]),
               "check_only": args.check_only}
    if args.check_only:
        print(json.dumps(summary)); return
    pin_bytes = (json.dumps(pin, indent=2) + "\n").encode()
    # All validation precedes the first output write. No solver or analysis is rerun.
    (ROOT / "results/execution-output-manifest.json").write_bytes(manifest_bytes)
    (ROOT / "results/code-pin.json").write_bytes(pin_bytes)
    count = write_numerical_table(result)
    appendix = execution_text(pin, result, hashlib.sha256(pin_bytes).hexdigest(), manifest_sha)
    (ROOT / "paper/sections/execution.tex").write_text(appendix, encoding="utf-8", newline="\n")
    print(json.dumps({**summary, "generated_table_rows": count}))


if __name__ == "__main__":
    main()
