"""Build a compact portable native-outcome/admissibility record, without metrics.

Only completed native receipts and completed saved-snapshot diagnostics are
read. No raw field arrays, solver action, clipping or gate relaxation.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

from analyze_gkeyll_controls import ROOT, load_json, require, sha256
from collect_completed_gkeyll_cases import CASES, timing_provenance, validate_receipt
from scan_gkeyll_saved_states import require_complete_context


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-14)


def full_source_sha(path: Path) -> str:
    value = load_json(path)
    return value.get("source_full_record_sha256", sha256(path))


def export_public_inputs(args) -> None:
    directory = args.evidence_directory.resolve()
    require(directory.is_relative_to((ROOT/"data").resolve()) or directory.is_relative_to((ROOT/"results").resolve()),
            "Portable evidence directory must be inside project data/ or results/")
    directory.mkdir(parents=True, exist_ok=True)
    exporter_sha = sha256(Path(__file__))

    def write_one(source, filename, kind):
        original = load_json(source)
        selected = copy.deepcopy(original)
        if kind == "diagnosis":
            for name, diagnostic in selected["pressure_checks"].items():
                if name != "population1":
                    for key in list(diagnostic):
                        if key.startswith("worst_"):
                            del diagnostic[key]
        elif kind == "details":
            for cell in selected["invalid_clean_population1_cells"]:
                cell.pop("paper_Y",None)
                cell["states"] = {name:{"pressure_eigenvalues":cell["states"][name]["pressure_eigenvalues"]}
                                  for name in ("clean_population1","archived_population1")}
        elif kind == "predicate":
            for file in selected["files"]:
                for anchor in file["line_anchors"]:
                    anchor.pop("text",None)
        elif kind == "intermediate":
            selected.pop("development_guard_fix",None); selected.pop("supersedes_development_record_sha256",None)
            keys=("frame","population","actual_time","source_BP_sha256","source_BP_bytes","numeric_export_sha256",
                  "minimum_density","minimum_pressure_diagonal","minimum_pressure_eigenvalue","negative_eigenvalue_cell_count",
                  "worst_native_zero_based_x_y","worst_raw_center_x_y")
            selected["frames"]=[{key:row[key] for key in keys if key in row} for row in selected["frames"]]
        if kind in {"diagnosis","details","predicate","intermediate"}:
            selected["source_full_record_sha256"] = original.get("source_full_record_sha256",sha256(source))
            selected["public_exporter_script_sha256"] = exporter_sha
            selected["public_export_scope"] = "Selected portable metadata; only the single endpoint witness and small invalid-index/eigenvalue list retain physical arrays. Full source record hash is preserved."
            encoded=(json.dumps(selected,indent=2,allow_nan=False)+"\n").encode("utf-8")
        else:
            encoded=source.read_bytes()  # Preserve reviewed context/inventory hashes exactly.
        text=encoded.decode("utf-8-sig")
        require(not re.search(r"\b[A-Za-z]:[\\/]",text) and not any(token in text for token in ("/mnt/","/root/")),
                "Private absolute path survived evidence selection")
        target=directory/filename
        require(not target.is_symlink(),"Evidence export may not overwrite a symlink")
        if target.exists():
            require(target.read_bytes()==encoded,"Different existing evidence export; preserve it and select a fresh evidence directory")
        else:
            with target.open("xb") as stream:
                stream.write(encoded)
        return target

    roles=(("collector_manifest","collector-inventory.json","inventory"),("expected_context","expected-runtime-context.json","context"),
           ("independent_diagnosis","independent-endpoint-diagnosis.json","diagnosis"),
           ("independent_details","independent-endpoint-details.json","details"),
           ("predicate_provenance","native-predicate-provenance.json","predicate"))
    for role,filename,kind in roles:
        setattr(args,role,write_one(getattr(args,role),filename,kind))
    args.intermediate_proof=[write_one(path,f"independent-intermediate-{i+1}.json","intermediate") for i,path in enumerate(args.intermediate_proof)]


def source_predicate_record(path: Path, expected: dict, diagnosis_sha: str, runtime_manifest: dict) -> dict:
    evidence = load_json(path)
    require(evidence["source_predicate_provenance_verified"] and evidence["clean_source_commit"] == expected["source_commit"]
            and evidence["published_runtime_manifest_sha256"] == expected["runtime_file_manifest_sha256"]
            and evidence["independent_tensor_diagnosis_sha256"] == diagnosis_sha, "Predicate provenance is not bound to the tested clean runtime/witness")
    files = []
    for entry in evidence["files"]:
        require(entry["source_sha256"] == entry["installed_sha256"] and entry["published_source_and_installed_maps_match"], "Source/installed predicate hashes differ")
        require(runtime_manifest["source_files_sha256"][entry["path"]] == entry["source_sha256"]
                and runtime_manifest["installed_solver_files_sha256"][entry["installed_relative_path"]] == entry["installed_sha256"],
                "Predicate source/installed digests differ from the actual published runtime maps")
        files.append({k: entry[k] for k in ("path", "source_sha256", "installed_relative_path", "installed_sha256", "primary_versioned_source_url")}
                     | {"line_anchors": [{k: anchor[k] for k in ("first_line", "last_line", "url")} for anchor in entry["line_anchors"]]})
    return {"independent_evidence_sha256": sha256(path), "producer_script_sha256": evidence["producer_script_sha256"],
            "clean_source_commit": evidence["clean_source_commit"], "files": files,
            "predicate_scope": evidence["predicate_scope"], "caller_scope": evidence["caller_scope"],
            "finite_positive_diagonal_witness_accepted_by_native_predicate": evidence["witness"]["diagonal_only_predicate_accepts_witness"],
            "inference": evidence["inference"], "limits": evidence["limits"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--collector-manifest", type=Path, required=True)
    parser.add_argument("--scan-directory", type=Path, required=True)
    parser.add_argument("--expected-context", type=Path, required=True)
    parser.add_argument("--independent-diagnosis", type=Path, required=True)
    parser.add_argument("--independent-details", type=Path, required=True)
    parser.add_argument("--predicate-provenance", type=Path, required=True)
    parser.add_argument("--intermediate-proof", action="append", type=Path, default=[])
    parser.add_argument("--evidence-directory", type=Path, required=True, help="Fresh project-local selected evidence directory under data/ or results/")
    parser.add_argument("--runtime-file-manifest", type=Path, default=ROOT/"data/gkeyll-clean9663-file-manifest.json")
    parser.add_argument("--public-scan-directory", type=Path, default=ROOT/"results/gkeyll-saved-state-scans")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.is_symlink() and not args.output.with_suffix(args.output.suffix + ".tmp").is_symlink(), "Output may not be a leaf symlink")
    args.output = args.output.resolve(); runs_root = args.runs_root.resolve()
    inputs = [args.collector_manifest, args.expected_context, args.independent_diagnosis, args.independent_details, args.predicate_provenance,args.runtime_file_manifest] + args.intermediate_proof
    require(not args.output.is_relative_to(runs_root) and args.output not in {p.resolve() for p in inputs}
            and not args.output.exists(), "Output must be fresh and outside native/input evidence")
    export_public_inputs(args)
    expected = load_json(args.expected_context); require_complete_context(expected)
    runtime_manifest=load_json(args.runtime_file_manifest)
    require(sha256(args.runtime_file_manifest)==expected["runtime_file_manifest_sha256"] and runtime_manifest["source_commit"]==expected["source_commit"],
            "Published runtime manifest hash/source differs from reviewed expected context")
    collection = load_json(args.collector_manifest)
    require(collection["expected_runtime_context"] == expected, "Collector/runtime context differs")
    diagnosis, details = load_json(args.independent_diagnosis), load_json(args.independent_details)
    require(diagnosis["independent_diagnosis_completed"] and diagnosis["no_analyzer_helper_imported"]
            and diagnosis["solver_or_raw_input_changed"] is False and diagnosis["conformance_gate_relaxed"] is False,
            "Independent tensor diagnosis scope/guards differ")
    require(details["independent_details_complete"] and details["previous_independent_diagnosis_sha256"] == full_source_sha(args.independent_diagnosis)
            and details["no_conformance_gate_relaxed"] and details["no_rejected_case_performance_metrics_generated"], "Independent tensor detail binding/scope differs")
    report = {"schema_version": 1, "record_type": "native_outcomes_and_admissibility", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "builder_sha256": sha256(Path(__file__)), "scanner_sha256": sha256(ROOT / "experiments/scan_gkeyll_saved_states.py"),
              "collector_sha256": collection["collector_sha256"], "collector_manifest_sha256": sha256(args.collector_manifest),
              "runtime_context": expected, "native_outcomes": [], "comparison_metrics_included": False, "private_paths_included": False,
              "scope": "Native process completion, strict endpoint collector decisions and regular saved-snapshot PSD diagnostics are separate facts. Saved frames0--30 do not certify every timestep; frame31/later outputs are excluded from admissibility scans. No repairs, clipping, rejected-state performance metrics or automatic reruns.",
              "native_output_inventory_scope": "Output filenames/byte sizes/hashes are copied from each hash-pinned final native receipt. The saved-state scanner independently rehashes regular moment files0--30; it does not claim to rescan all field/restart arrays."}
    report["input_bindings"] = {role:{"path":path.resolve().relative_to(ROOT.resolve()).as_posix(),"filename":path.name,"sha256":sha256(path),
                                       "source_full_record_sha256":full_source_sha(path)} for role,path in
        (("collector_manifest",args.collector_manifest),("expected_context",args.expected_context),
         ("independent_diagnosis",args.independent_diagnosis),("independent_details",args.independent_details),
         ("predicate_provenance",args.predicate_provenance),("runtime_file_manifest",args.runtime_file_manifest))}
    for i,path in enumerate(args.intermediate_proof):
        report["input_bindings"][f"intermediate_proof_{i+1}"] = {"path":path.resolve().relative_to(ROOT.resolve()).as_posix(),"filename":path.name,
                                                               "sha256":sha256(path),"source_full_record_sha256":full_source_sha(path)}
    scans = {}
    for native_case, case_id, population_count, role in CASES:
        receipt_path = runs_root / native_case / "run-receipt.json"
        outcome = {"native_case": native_case, "analysis_case_id": case_id, "population_count": population_count, "role": role,
                   "native_status": "pending_completed_receipt", "native_outcome_observed":False,
                   "native_outcome_terminal":False,"collector_decision_resolved":False,"saved_snapshot_diagnostic_resolved":False,
                   "endpoint_metrics_eligible":None,
                   "collector_decision": {"status": "pending"},
                   "saved_snapshot_diagnostic": {"status": "pending"}}
        if not receipt_path.is_file():
            report["native_outcomes"].append(outcome); continue
        receipt, receipt_sha = load_json(receipt_path), sha256(receipt_path)
        require(receipt["status"] in {"completed_native_stop","failed","failed_controller_guard"}, "Native receipt is not a recognized terminal outcome")
        require(receipt["case"] == native_case and all(receipt[key] == value for key, value in expected.items()), "Native case/runtime receipt differs")
        outcome.update(native_status=receipt["status"], native_outcome_observed=True,native_outcome_terminal=True,native_returncode=receipt.get("returncode"),
                       source_run_receipt_sha256=receipt_sha, runtime_context={k:receipt[k] for k in expected},
                       time_controls=receipt["time_controls"], input_hashes=receipt["input_hashes"],
                       **timing_provenance(receipt), native_output_inventory=receipt.get("output_bp_files", []),
                       native_failure_markers=receipt.get("native_numerical_failure_markers", []))
        if receipt["status"] != "completed_native_stop":
            outcome["collector_decision"] = {"status":"not_accepted_native_execution_failure", "metrics_accepted":False}
            outcome.update(endpoint_metrics_eligible=False,collector_decision_resolved=True,saved_snapshot_diagnostic_resolved=True,
                           saved_snapshot_diagnostic={"status":"not_applicable_native_execution_failed","scope":"No successful regular30 endpoint or complete31-snapshot diagnostic is inferred."})
            report["native_outcomes"].append(outcome); continue
        selected = validate_receipt(receipt, native_case, population_count, expected)
        outcome.update(actual_regular30_time=selected["actual_time"], native_regular_frame=30,
                       native_execution_completed_successfully=True,
                       regular30_raw_output_bindings=[{"filename":name,"bytes":selected["bytes"][name],"sha256":selected["sha256"][name]} for name in selected["names"]])
        decision = next(c for c in collection["cases"] if c["case"] == native_case)
        if decision["status"] in {"completed_and_decoded","failed_validation_or_execution"}:
            require(decision.get("source_run_receipt_sha256") == receipt_sha, "Collector decision is not bound to actual native receipt")
        if decision["status"] == "completed_and_decoded":
            portable = decision["receipt"]
            require(portable["all_decoding_checks_passed"] and portable["actual_time"] == selected["actual_time"] and portable["frame"] == 30,
                    "Accepted collector decision has different time/frame/scope")
            outcome["collector_decision"] = {"status":"accepted_initial_and_regular30_states", "metrics_accepted_at_endpoints":True,
                "scope":"Strict finite/positive-density/positive-definite covariance checks at actual initial and regular30 outputs; not a continuous-trajectory certificate.",
                "portable_decoding_receipt_sha256":decision["portable_receipt_sha256"],
                "initial_and_regular30_population_conformance":[{"filename":e["filename"],"frame":e["frame"],"actual_time":e["actual_time"],
                    "source_BP_sha256":e["source_sha256"],"numeric_export_sha256":e["numeric_export_sha256"],"state_conformance":e["state_conformance"]}
                    for e in portable["initial_exports"]+portable["exports"] if "state_conformance" in e]}
            outcome.update(endpoint_metrics_eligible=True,collector_decision_resolved=True)
        elif decision["status"] == "failed_validation_or_execution":
            require(decision["error_type"] == "ConformanceError" and decision.get("conformance_failure"), "Unresolved provenance/decoder failure is not a physical admissibility diagnosis")
            outcome["collector_decision"] = {"status":"rejected_nonconforming_state", "metrics_accepted":False,
                                            "conformance_failure":decision["conformance_failure"], "no_clipping_or_guard_relaxation":True}
            outcome.update(endpoint_metrics_eligible=False,collector_decision_resolved=True)
        else:
            require(decision["status"] in {"pending_no_completed_receipt","running_without_completed_receipt"}, "Unknown collector outcome state")
            outcome["collector_decision"]={"status":"pending_completed_case_collection","scope":"Native completion observed; endpoint collection has not yet resolved."}
        scan_path = args.scan_directory / (native_case + ".json")
        if scan_path.is_file():
            scan = load_json(scan_path)
            if scan["status"] == "completed_saved_snapshot_scan":
                require(scan["all_requested_saved_frames_scanned"] and scan["source_run_receipt_sha256"] == receipt_sha
                        and scan["runtime_context"] == expected and scan["scanner_sha256"] == report["scanner_sha256"]
                        and [f["frame"] for f in scan["frames"]] == list(range(31)), "Saved-snapshot scan binding/completeness differs")
                scans[native_case] = scan
                outcome["saved_snapshot_diagnostic_resolved"]=True
                public_scan_directory=args.public_scan_directory.resolve()
                require(public_scan_directory.is_relative_to((ROOT/"results").resolve()),"Public compact scans must remain inside project results/")
                public_scan_directory.mkdir(parents=True,exist_ok=True)
                public_scan=public_scan_directory/(native_case+".json")
                require(not public_scan.is_symlink(),"Public compact scan may not be a symlink")
                if public_scan.exists():
                    require(public_scan.read_bytes()==scan_path.read_bytes(),"Different existing public compact scan; preserve it and select a fresh public scan directory")
                else:
                    with public_scan.open("xb") as stream: stream.write(scan_path.read_bytes())
                outcome["saved_snapshot_diagnostic"] = {"status":"completed_regular0_through30", "filename":native_case+".json", "path":public_scan.relative_to(ROOT.resolve()).as_posix(), "sha256":sha256(scan_path),
                    "actual_saved_times":[{"frame":f["frame"],"actual_time":f["actual_time"]} for f in scan["frames"]],
                    "summary":scan["summary"], "all_scanned_populations_PSD":scan["all_scanned_populations_PSD"],
                    "all_scanned_populations_strict_PD":scan["all_scanned_populations_strict_PD"],
                    "non_PSD_saved_frames":[{"frame":f["frame"],"actual_time":f["actual_time"],
                        "states":[{"state":key,**{k:value[k] for k in ("minimum_finite_density","minimum_pressure_diagonal","minimum_pressure_eigenvalue",
                            "negative_eigenvalue_count","negative_eigenvalue_cell_count","covariance_undefined_cell_count","minimum_eigenvalue_native_zero_based_x_y") if k in value}}
                            for key,value in f.items() if (key.startswith("population") and key != "population_source_bindings" or key == "aggregate")
                            and isinstance(value,dict) and not value["covariance_PSD_passed"]]}
                        for f in scan["frames"] if any(not f[key]["covariance_PSD_passed"] for key in [f"population{i}" for i in range(1,population_count+1)]+["aggregate"])],
                    "scope":"Saved snapshots only; does not identify the first invalid timestep or loss-producing split operator."}
            else:
                outcome["saved_snapshot_diagnostic"] = {"status":scan["status"],"scan_file_sha256":sha256(scan_path),"saved_frames_present":len(scan.get("frames",[]))}
                outcome["saved_snapshot_diagnostic_resolved"]=scan["status"]=="scanner_failed"
        report["native_outcomes"].append(outcome)
    bad_outcome = next(o for o in report["native_outcomes"] if o["native_case"] == "2-fluid-unmatched")
    require(bad_outcome["collector_decision"]["status"]=="rejected_nonconforming_state"
            and bad_outcome["actual_regular30_time"]==diagnosis["actual_time"]==details["clean_time"],
            "Rejected outcome/independent witness times or collector decision differ")
    require(bad_outcome.get("source_run_receipt_sha256") == diagnosis["native_receipt_sha256"], "Independent witness is not bound to the rejected native outcome")
    native_inventory = {p["filename"]:p for p in bad_outcome["native_output_inventory"]}
    require(all(native_inventory[e["filename"]]["sha256"] == e["raw_sha256"] for e in diagnosis["inputs"]), "Independent witness raw BP bindings differ")
    archived = load_json(ROOT / "data/provenance-fluid-reference.json")["reference_snapshots"]
    for entry in details["archived_reference_bindings"]:
        pin = next(p for p in archived if p["sha256"] == entry["source_BP_sha256"])
        require(pin["archive_sha256"] == entry["archive_sha256"] and pin["exact_member_name"] == entry["exact_member_name"]
                and pin["numeric_export_sha256"] == entry["numeric_export_sha256"], "Archived comparison/witness binding differs")
    pop1 = diagnosis["pressure_checks"]["population1"]
    invalid=details["invalid_clean_population1_cells"]
    require(len(invalid)==pop1["negative_eigenvalue_cell_count"] and len({tuple(c["native_zero_based_x_y"]) for c in invalid})==len(invalid)
            and all(min(c["states"]["clean_population1"]["pressure_eigenvalues"])<0 for c in invalid)
            and close(min(min(c["states"]["clean_population1"]["pressure_eigenvalues"]) for c in invalid),pop1["minimum_pressure_eigenvalue"]),
            "Invalid-cell list length/uniqueness/negative minima differ from independent diagnosis")
    for name in ("population1","population2","aggregate"):
        detail,diagnostic=details["summary"]["clean_"+name],diagnosis["pressure_checks"][name]
        require(detail["negative_eigenvalue_cell_count"]==diagnostic["negative_eigenvalue_cell_count"]
                and close(detail["minimum_density"],diagnostic["minimum_density"])
                and close(detail["minimum_diagonal"],diagnostic["minimum_pressure_diagonal"])
                and close(detail["minimum_eigenvalue"],diagnostic["minimum_pressure_eigenvalue"]),
                "Independent detail/diagnosis minimum or negative-cell count differs")
    require(pop1["minimum_pressure_eigenvalue"] < 0 and pop1["worst_principal_2x2_minors"]["xz"] < 0
            and pop1["worst_explicit_3x3_determinant"] < 0, "Witness does not establish indefinite covariance")
    if "2-fluid-unmatched" in scans:
        endpoint = scans["2-fluid-unmatched"]["frames"][-1]["population1"]
        require(endpoint["negative_eigenvalue_cell_count"] == pop1["negative_eigenvalue_cell_count"] and
                close(endpoint["minimum_pressure_eigenvalue"], pop1["minimum_pressure_eigenvalue"]), "Scanner/witness endpoint diagnosis differs")
    report["independent_endpoint_witness"] = {"native_case":"2-fluid-unmatched", "frame":30, "actual_time":diagnosis["actual_time"],
        "independent_diagnosis_sha256":sha256(args.independent_diagnosis), "independent_details_sha256":sha256(args.independent_details),
        "independent_producer_script_sha256":diagnosis["script_sha256"], "raw_BP_and_numeric_bindings":diagnosis["inputs"],
        "native_zero_based_x_y":pop1["worst_native_x_y_indices"], "raw_center_x_y":pop1["worst_cell_center_x_y"],
        "conserved_component_order":details["component_order"], "conserved_components":pop1["worst_conserved_vector"],
        "pressure_matrix":pop1["worst_pressure_matrix"], "pressure_eigenvalues":pop1["worst_eigenvalues"],
        "minimum_eigenvalue":pop1["minimum_pressure_eigenvalue"], "xz_principal_minor":pop1["worst_principal_2x2_minors"]["xz"],
        "explicit_determinant":pop1["worst_explicit_3x3_determinant"], "invalid_cell_count":pop1["negative_eigenvalue_cell_count"],
        "clean_and_archived_summary":details["summary"], "archived_raw_BP_and_numeric_bindings":details["archived_reference_bindings"],
        "archived_actual_time":details["archived_time"],"clean_minus_archived_time":details["clean_minus_archived_time"],"time_interpolation_performed":False,
        "invalid_cell_list":[{"native_zero_based_x_y":c["native_zero_based_x_y"],"analysis_zero_based_y_x":c["analysis_zero_based_y_x"],
            "raw_center_x_y":c["raw_center_x_y"],"clean_population1_minimum_eigenvalue":min(c["states"]["clean_population1"]["pressure_eigenvalues"]),
            "archived_population1_minimum_eigenvalue_at_same_index":min(c["states"]["archived_population1"]["pressure_eigenvalues"])} for c in details["invalid_clean_population1_cells"]],
        "scope":"Small raw witness and invalid-index list only, not full fields or rejected-case performance metrics. Archived final populations remain PD; the unidentified original dirty build is not inferred from this clean rerun."}
    report["native_predicate_provenance"] = source_predicate_record(args.predicate_provenance, expected, full_source_sha(args.independent_diagnosis),runtime_manifest)
    report["independent_intermediate_checks"] = []
    for proof_path in args.intermediate_proof:
        proof = load_json(proof_path)
        require(proof["independent_intermediate_failure_confirmed"] and proof["native_receipt_before_after_and_prior_endpoint_binding_passed"]
                and proof["no_clipping_repair_or_gate_change"] and proof["no_performance_metrics_or_solver_action"], "Intermediate independent proof scope differs")
        outcome = next(o for o in report["native_outcomes"] if o["native_case"] == proof["native_case"])
        require(outcome["source_run_receipt_sha256"] == proof["native_receipt_sha256"], "Independent intermediate proof native binding differs")
        inventory = {p["filename"]:p for p in outcome["native_output_inventory"]}
        checked = []
        for row in proof["frames"]:
            population = row.get("population",proof.get("population",1))
            name = f"case_elc{population}_{row['frame']}.bp"
            require(inventory[name]["sha256"] == row["source_BP_sha256"] and inventory[name]["bytes"] == row["source_BP_bytes"], "Intermediate proof raw BP binding differs")
            scanrow = scans[proof["native_case"]]["frames"][row["frame"]]
            diagnostic = scanrow[f"population{population}"]
            require(scanrow["actual_time"] == row["actual_time"] and diagnostic["negative_eigenvalue_cell_count"] == row["negative_eigenvalue_cell_count"]
                    and close(diagnostic["minimum_pressure_eigenvalue"],row["minimum_pressure_eigenvalue"]), "Intermediate scanner/independent diagnosis differs")
            checked.append({k:row[k] for k in ("frame","actual_time","source_BP_sha256","source_BP_bytes","numeric_export_sha256",
                "minimum_density","minimum_pressure_diagonal","minimum_pressure_eigenvalue","negative_eigenvalue_cell_count","worst_native_zero_based_x_y","worst_raw_center_x_y")})
        report["independent_intermediate_checks"].append({"native_case":proof["native_case"],"source_proof_filename":proof_path.name,
            "source_proof_sha256":sha256(proof_path),"producer_script_sha256":proof["producer_script_sha256"],
            "native_receipt_sha256":proof["native_receipt_sha256"],"checked_saved_frames":checked,
            "scope":"Independent checks of specified saved snapshots only; no onset timestep/operator or physical trajectory is inferred."})
    report["native_completed_outcome_count"] = sum(o.get("native_execution_completed_successfully",False) for o in report["native_outcomes"])
    report["endpoint_collector_accepted_count"] = sum(o["collector_decision"]["status"]=="accepted_initial_and_regular30_states" for o in report["native_outcomes"])
    report["endpoint_collector_rejected_count"] = sum(o["collector_decision"]["status"]=="rejected_nonconforming_state" for o in report["native_outcomes"])
    report["completed_saved_snapshot_scan_count"] = len(scans)
    report["all_four_native_outcomes_completed"] = report["native_completed_outcome_count"] == 4
    report["all_four_saved_snapshot_scans_complete"] = len(scans) == 4
    report["observed_terminal_native_outcome_count"] = sum(o["native_outcome_observed"] for o in report["native_outcomes"])
    report["all_four_native_outcomes_observed"] = report["observed_terminal_native_outcome_count"] == 4
    report["all_four_collector_decisions_resolved"] = all(o["collector_decision_resolved"] for o in report["native_outcomes"])
    report["all_four_saved_snapshot_diagnostics_resolved"] = all(o["saved_snapshot_diagnostic_resolved"] for o in report["native_outcomes"])
    report["native_regular30_completion_count"] = report["native_completed_outcome_count"]
    report["endpoint_admissible_case_ids"] = [o["analysis_case_id"] for o in report["native_outcomes"] if o["collector_decision"]["status"] == "accepted_initial_and_regular30_states"]
    report["endpoint_eligible_case_ids"] = [o["analysis_case_id"] for o in report["native_outcomes"] if o["endpoint_metrics_eligible"] is True]
    report["endpoint_rejected_case_ids"] = [o["analysis_case_id"] for o in report["native_outcomes"] if o["collector_decision"]["status"] == "rejected_nonconforming_state"]
    report["non_PSD_saved_history_case_ids"] = [o["analysis_case_id"] for o in report["native_outcomes"] if o["saved_snapshot_diagnostic"].get("all_scanned_populations_PSD") is False]
    report["endpoint_eligible_pairs"] = []
    for count,label in ((1,"one"),(2,"two")):
        ids = [f"baseline_{label}_fluid",f"matched_{label}_fluid"]
        if all(name in report["endpoint_eligible_case_ids"] and next(o for o in report["native_outcomes"] if o["analysis_case_id"]==name)["saved_snapshot_diagnostic"]["status"]=="completed_regular0_through30" for name in ids):
            endpoints = [next(o for o in report["native_outcomes"] if o["analysis_case_id"] == name) for name in ids]
            anchors = [{"analysis_case_id":o["analysis_case_id"],"native_case":o["native_case"],"actual_regular30_time":o["actual_regular30_time"],
                        "source_run_receipt_sha256":o["source_run_receipt_sha256"],"regular30_raw_output_bindings":o["regular30_raw_output_bindings"],
                        "saved_scan_filename":o["saved_snapshot_diagnostic"]["filename"],"saved_scan_sha256":o["saved_snapshot_diagnostic"]["sha256"],
                        "saved_history_all_PSD":o["saved_snapshot_diagnostic"]["all_scanned_populations_PSD"]} for o in endpoints]
            report["endpoint_eligible_pairs"].append({"id":label+"_fluid_initialization_effect","baseline":ids[0],"matched":ids[1],
                "status":"endpoint_eligible_NUMERICAL_only","endpoints":anchors,"runtime_context":expected,
                "matched_minus_baseline_actual_time":endpoints[1]["actual_regular30_time"]-endpoints[0]["actual_regular30_time"],
                "physical_trajectory_admissibility_claimed":False,"scope":"Numerical endpoint comparison only; both31-snapshot histories are bound and separately reported, including non-PSD states."})
    encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
    require(not re.search(r"\b[A-Za-z]:[\\/]", encoded) and not any(token in encoded for token in ("/mnt/", "/root/")), "Private absolute path survived portable record assembly")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
    print(json.dumps({k:report[k] for k in ("native_completed_outcome_count","endpoint_collector_accepted_count","endpoint_collector_rejected_count","completed_saved_snapshot_scan_count","all_four_native_outcomes_completed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
