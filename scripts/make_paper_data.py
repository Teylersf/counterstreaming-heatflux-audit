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
                "make_control_figures.py", "build_clean_gkeyll.py")
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
        lines += ["All four clean-base native controls have validated completion/decoding receipts and "
                  "paired comparisons in the supplied final result. They retain the original 600/60 controls "
                  "and use regular frame30 at each recorded actual time; later regular/forced frames are excluded. "
                  "The exact dirty 2023 executable remains unidentified, so clean-base baseline fidelity is "
                  "assessed against archived outputs rather than asserted from source ancestry."]
    elif state["comparison_result_supplied"] or state["validated_native_completion_count"]:
        lines += [f"The supplied result lists {state['valid_compared_case_count']} control-case "
                  f"comparisons and {state['validated_native_completion_count']} validated native completion "
                  "receipts. A completed four-case matched-state comparison is not asserted; pending or failed "
                  "cases remain explicit in the pinned inventories."]
    else:
        lines += ["No final four-case matched-state comparison is included in this execution record. "
                  "Run preparation, initialization conformance and cost probes alone are not completed "
                  "reconnection controls."]
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
    control_entries, receipt_payloads, control_result = {}, [], None
    for path in args.controls_receipt:
        entry = committed_entry(path, commit)
        control_entries[entry["path"]] = entry
        receipt_payloads.append(read(ROOT / entry["path"]))
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
    if state["native_runtime_context"]:
        for key, path in {"controller_sha256": "experiments/run_gkeyll_controls.py",
                "runtime_file_manifest_sha256": "data/gkeyll-clean9663-file-manifest.json",
                "dependency_lock_sha256": "data/gkeyll-clean9663-dependencies.json",
                "matched_init_conformance_sha256": "results/gkeyll-matched-init-conformance.json"}.items():
            require(state["native_runtime_context"].get(key) == sha(ROOT / path),
                    "Completed native runtime differs from pinned evidence: " + key)
    require(not state["all_four_completed_and_compared"] or archive_verified,
            "Completed control claim lacks verified complete source archives")
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
