"""Compare actual decoded Gkeyll states to a verified archived PIC export.

No network, solver, time interpolation, raw-data repair or favorable ROI.
Cases and paired controls are declared in JSON; absent/invalid cases retain
explicit failure records. qCS is a population-recentering contribution only.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ["rho", "rho_ux", "rho_uy", "rho_uz", "Mxx", "Mxy", "Mxz", "Myy", "Myz", "Mzz"]
TENSOR = ((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2))
QNAME = "qCSxxx_contribution"
QTAGNAME = "qCSxxx_contribution_vs_tagged_PIC"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def sanitize_error(error: Exception | str, cache_root: Path | None, project_root: Path = ROOT) -> str:
    """Remove local prefixes including Python's repr-escaped Windows filenames."""
    replacements = []
    for root, label in ((cache_root, "$CACHE_ROOT"), (project_root, "$PROJECT_ROOT")):
        if root is None:
            continue
        forms = set()
        for value in (str(root), str(root.resolve())):
            for form in (value, value.replace("\\", "/"), value.replace("/", "\\")):
                forms.update((form, repr(form)[1:-1]))
        replacements.extend((form, label) for form in forms if form)
    message = str(error)
    for prefix, label in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        message = message.replace(prefix, label)
    return message


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative_path(base: Path, name: str) -> Path:
    path = Path(name)
    require(not path.is_absolute() and ".." not in path.parts, "Config input paths must be portable relative paths without parent traversal")
    return base / path


class ConformanceError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("; ".join(report["violations"]))


def moments(state: np.ndarray, label: str) -> tuple[dict, dict]:
    report = {"label": label, "shape": list(state.shape), "nonfinite_count": int(np.count_nonzero(~np.isfinite(state))),
              "no_clipping_or_regularization": True, "violations": []}
    if state.ndim != 3 or state.shape[-1] != 10:
        report["violations"].append("State must have shape [y,x,10]")
    if report["nonfinite_count"]:
        report["violations"].append("Nonfinite conserved values")
    if report["violations"]:
        raise ConformanceError(report)
    rho, momentum = state[..., 0], state[..., 1:4]
    report["minimum_density"] = float(rho.min())
    if report["minimum_density"] <= 0:
        report["violations"].append("Density is not strictly positive")
        raise ConformanceError(report)
    pressure = np.empty(state.shape[:2] + (3, 3), dtype=np.float64)
    for component, (i, j) in enumerate(TENSOR, 4):
        value = state[..., component] - momentum[..., i] * momentum[..., j] / rho
        pressure[..., i, j] = pressure[..., j, i] = value
    if not np.isfinite(pressure).all():
        report["violations"].append("Nonfinite recovered pressure")
        raise ConformanceError(report)
    report["minimum_pressure_diagonal"] = float(np.diagonal(pressure, axis1=-2, axis2=-1).min())
    report["minimum_pressure_eigenvalue"] = float(np.linalg.eigvalsh(pressure).min())
    if report["minimum_pressure_diagonal"] <= 0 or report["minimum_pressure_eigenvalue"] <= 0:
        report["violations"].append("Covariance pressure is not strictly positive definite")
        raise ConformanceError(report)
    report["passed"] = True
    return {"rho": rho, "Jz": -momentum[..., 2], "Pxx": pressure[..., 0, 0],
            "Pzz": pressure[..., 2, 2], "ux": momentum[..., 0] / rho}, report


def error_metrics(model: np.ndarray, reference: np.ndarray) -> dict:
    require(model.shape == reference.shape, "Metric arrays have different shapes")
    require(np.isfinite(model).all() and np.isfinite(reference).all(), "Nonfinite metric inputs")
    difference = model - reference
    l1 = float(np.sum(np.abs(difference), dtype=np.float64))
    l2 = float(np.linalg.norm(difference.ravel()))
    r1 = float(np.sum(np.abs(reference), dtype=np.float64))
    r2 = float(np.linalg.norm(reference.ravel()))
    require(all(np.isfinite(x) for x in (l1, l2, r1, r2)), "Nonfinite or overflowing metric norms")
    return {"relative_L1": l1 / r1 if r1 != 0 else None,
            "relative_L2": l2 / r2 if r2 != 0 else None,
            "reference_L1_norm": r1, "reference_L2_norm": r2,
            "absolute_difference_L1_norm": l1, "absolute_difference_L2_norm": l2,
            "RMS_difference": float(np.sqrt(np.mean(difference * difference))),
            "maximum_absolute_difference": float(np.max(np.abs(difference))),
            "relative_L1_null_reason": "zero_reference_L1_norm" if r1 == 0 else None,
            "relative_L2_null_reason": "zero_reference_L2_norm" if r2 == 0 else None}


def compare_fields(model: dict[str, np.ndarray], reference: dict[str, np.ndarray]) -> dict:
    report = {}
    for name, array in model.items():
        if name == "ux":
            continue
        target = "qxxx_conditional_raw_third" if name == QNAME else "qCSxxx" if name == QTAGNAME else name
        require(target in reference, "Reference lacks quantity " + target)
        report[name] = {"target": "PIC_central_qxxx_CONDITIONAL_raw_third_interpretation" if name == QNAME else "PIC_tagged_population_qCSxxx_from_documented_first_second_moments" if name == QTAGNAME else "PIC_" + name,
                       "conditional_on_unverified_third_diagnostic_normalization": name == QNAME,
                       "full_2D_grid": error_metrics(array, reference[target]),
                       "x_averaged_profile": error_metrics(array.mean(axis=1), reference[target].mean(axis=1))}
        if name == QTAGNAME:
            report[name]["reference_qualification"] = "Algebraic actual-tag moment recentering only; negative covariance diagnostics are retained in PIC_reference.tagged_qCS_interpretation, so this is not a positive-semidefinite reference-state certificate."
    return report


def cs_contribution(populations: list[np.ndarray], aggregate: np.ndarray, *, exact_vacuum_allowed: bool = False) -> np.ndarray:
    require(np.all(aggregate[..., 0] > 0), "Aggregate density must be positive for qCS")
    aggregate_ux = aggregate[..., 1] / aggregate[..., 0]
    q = np.zeros(aggregate.shape[:2], dtype=np.float64)
    for state in populations:
        rho = state[..., 0]
        require(np.isfinite(state).all() and np.all(rho >= 0), "Invalid population state for qCS")
        vacuum = rho == 0
        require(exact_vacuum_allowed or not np.any(vacuum), "Population vacuum is not allowed for fluid qCS")
        require(not np.any(state[vacuum] != 0), "Zero-density tag has a nonzero conserved component")
        velocity = np.divide(state[..., 1], rho, out=np.zeros_like(rho), where=~vacuum)
        pxx = state[..., 4] - state[..., 1] * velocity
        delta = velocity - aggregate_ux
        q += 3 * pxx * delta + rho * delta**3
    require(np.isfinite(q).all(), "Nonfinite counter-streaming contribution")
    return q


def integrated_particle_moments(populations: list[np.ndarray], cell_area: float) -> dict:
    """Particle-moment diagnostics, not electromagnetic total-energy budgets."""
    def one(state):
        rho, momentum = state[..., 0], state[..., 1:4]
        require(np.isfinite(state).all() and np.all(rho > 0), "Invalid integrated-moment state")
        bulk = float(.5 * cell_area * np.sum(np.sum(momentum * momentum, axis=-1) / rho, dtype=np.float64))
        total = float(.5 * cell_area * np.sum(state[..., 4] + state[..., 7] + state[..., 9], dtype=np.float64))
        return {"mass": float(cell_area * np.sum(rho, dtype=np.float64)),
                "momentum_xyz": (cell_area * np.sum(momentum, axis=(0, 1), dtype=np.float64)).tolist(),
                "bulk_kinetic_energy": bulk, "internal_energy": total - bulk,
                "bulk_plus_internal_particle_energy": total}
    per_population = [one(state) for state in populations]
    return {"cell_area": cell_area, "per_population": per_population,
            "sum_of_population_bulk_kinetic_energy": sum(p["bulk_kinetic_energy"] for p in per_population),
            "sum_of_population_internal_energy": sum(p["internal_energy"] for p in per_population),
            "aggregate": one(sum(populations)),
            "scope": "Complete-grid conserved particle moments only. Aggregate internal energy includes relative population drift; it differs from the sum of population internal energies. Electromagnetic energy, boundary/numerical budgets and an exact conservation assertion are not supplied."}


def diagnostic_tag_pressure(state: np.ndarray, label: str) -> tuple[np.ndarray, dict]:
    """Retain, rather than repair, nonphysical covariance in archived diagnostics.

    These arrays are reference measurements, not accepted solver states. A failed
    covariance test remains explicit; qCS can still be evaluated algebraically.
    """
    require(state.ndim == 3 and state.shape[-1] == 10 and np.isfinite(state).all(), "Invalid tagged diagnostic array")
    rho, momentum = state[..., 0], state[..., 1:4]
    require(np.all(rho >= 0), "Negative tagged diagnostic density")
    vacuum = rho == 0
    require(not np.any(state[vacuum] != 0), "Zero-density tag has nonzero conserved components")
    velocity = np.divide(momentum, rho[..., None], out=np.zeros_like(momentum), where=~vacuum[..., None])
    pressure = np.empty(state.shape[:2] + (3, 3), dtype=np.float64)
    for component, (i, j) in enumerate(TENSOR, 4):
        pressure[..., i, j] = pressure[..., j, i] = state[..., component] - momentum[..., i] * velocity[..., j]
    require(np.isfinite(pressure).all(), "Nonfinite tagged diagnostic pressure")
    diagonal = np.diagonal(pressure, axis1=-2, axis2=-1)
    eigenvalues = np.linalg.eigvalsh(pressure)
    negative_diagonal = int(np.count_nonzero(diagonal < 0))
    negative_eigenvalues = int(np.count_nonzero(eigenvalues < 0))
    report = {"label": label, "minimum_density": float(rho.min()), "exact_vacuum_cell_count": int(vacuum.sum()),
              "minimum_pressure_diagonal": float(diagonal.min()), "negative_pressure_diagonal_count": negative_diagonal,
              "minimum_pressure_eigenvalue": float(eigenvalues.min()), "negative_pressure_eigenvalue_count": negative_eigenvalues,
              "covariance_nonnegative_passed": not (negative_diagonal or negative_eigenvalues),
              "no_clipping_or_regularization": True,
              "scope": "Archived diagnostic covariance; failed nonnegativity is retained, not accepted as a conforming solver state. Algebraic moment-recentering comparisons do not certify positive-semidefinite tagged pressure."}
    return pressure, report


def load_binary(cache: Path, directory: str, entry: dict) -> np.ndarray:
    path = relative_path(relative_path(cache, directory), entry["filename"])
    shape = tuple(entry["shape"])
    require(entry["dtype"] == "<f8" and entry["order"] == "C", "Unexpected exported binary dtype/order")
    require(path.stat().st_size == entry["bytes"] == int(np.prod(shape)) * 8, "Export byte size differs")
    require(sha256(path) == entry["sha256"], "PIC binary export SHA-256 mismatch")
    return np.memmap(path, dtype="<f8", mode="r", shape=shape, order="C")


def load_pic(config: dict, project: Path, cache: Path) -> tuple[dict, dict, dict]:
    path = relative_path(project, config["metadata"])
    meta = load_json(path)
    receipt_path = relative_path(project, config.get("full_archive_receipt", "data/full-archive-verification.json"))
    receipt = load_json(receipt_path)
    require(receipt["all_three_archives_and_18_selected_inputs_verified"], "Full-archive verification gate is not true")
    require(meta["electron_mass"] == 1 and meta["electron_charge"] == -1, "This comparison requires source normalized electron mass=1 and charge=-1")
    archive = next(a for a in receipt["archives"] if a["filename"] == meta["archive"]["filename"])
    require(meta["archive"]["full_archive_checksum_verified"] and meta["archive"]["computed_sha256"] == archive["computed_sha256"], "PIC export is not bound to the verified complete ZIP")
    frame = str(config["filename_frame_token"])
    snap = next(s for s in meta["snapshots"] if s["filename_frame_token"] == frame)
    require(snap["conditional_qxxx_available"], "PIC reference lacks conditional central qxxx export")
    conserved = next(e for e in meta["binary_outputs"] if e["filename"] == f"reference-pic-frame-{frame}-conserved.f64")
    observable = next(e for e in meta["binary_outputs"] if e["filename"] == f"reference-pic-frame-{frame}-observables.f64")
    require(conserved["components"] == COMPONENTS, "PIC conserved component order differs")
    state = load_binary(cache, config["binary_directory"], conserved)
    fields, conformance = moments(state, "PIC reference")
    obs = load_binary(cache, config["binary_directory"], observable)
    require(obs.shape[:2] == state.shape[:2] and np.isfinite(obs).all(), "PIC observable shape/values differ")
    names = observable["components"]
    require(set(names) == {"density", "Jz", "Pxx", "Pzz", "qCSxxx", "qxxx_conditional_raw_third"}, "Unexpected PIC observable columns")
    derivation = {}
    for source_name, target in (("density", "rho"), ("Jz", "Jz"), ("Pxx", "Pxx"), ("Pzz", "Pzz")):
        value = obs[..., names.index(source_name)]
        maximum = float(np.max(abs(fields[target] - value)))
        require(np.allclose(fields[target], value, rtol=1e-12, atol=1e-14), "PIC exported primitive disagrees with its conserved state: " + target)
        derivation[target] = maximum
    fields["qxxx_conditional_raw_third"] = np.asarray(obs[..., names.index("qxxx_conditional_raw_third")])
    fields["qCSxxx"] = np.asarray(obs[..., names.index("qCSxxx")])
    fields.pop("ux")
    tagged = next(e for e in meta["npz_outputs"] if e["filename"] == config["tagged_export_filename"])
    tagged_path = relative_path(relative_path(cache, config["binary_directory"]), tagged["filename"])
    require(tagged_path.stat().st_size == tagged["bytes"] and sha256(tagged_path) == tagged["sha256"], "Tagged PIC NPZ receipt differs")
    tag_conformance, tag_recovery = [], {}
    with np.load(tagged_path, allow_pickle=False) as z:
        require(set(z.files) == set(tagged["array_keys"]), "Tagged NPZ keys differ from receipt")
        require(all(list(z[k].shape) == tagged["array_shapes"][k] for k in z.files), "Tagged NPZ shapes differ from receipt")
        require(all(str(z[k].dtype) == tagged["array_dtypes"][k] for k in z.files), "Tagged NPZ dtypes differ from receipt")
        require(z["conserved_component_order"].tolist() == COMPONENTS, "Tagged PIC conserved component order differs")
        require(float(z["TIME"].item()) == snap["TIME"] and int(z["ITER"].item()) == snap["ITER"], "Tagged PIC timing differs")
        for axis, count in (("x", 1), ("y", 0)):
            bounds = meta["grid"]["bounds_" + axis]
            expected = bounds[0] + (np.arange(state.shape[count]) + .5) * meta["grid"]["spacing_x_y"][0 if axis == "x" else 1]
            require(np.allclose(z[axis], expected, rtol=0, atol=1e-13), "Tagged PIC coordinates differ")
        populations = [np.asarray(z["conserved_tag" + str(i)]) for i in (1, 2)]
        require(all(p.shape == state.shape for p in populations), "Tagged conserved shape differs")
        require(np.array_equal(sum(populations), state), "PIC tag states do not recombine exactly to the aggregate export")
        for i, population in enumerate(populations, 1):
            pressure, diagnostic = diagnostic_tag_pressure(population, "PIC tag" + str(i))
            tag_conformance.append(diagnostic)
            pmax = float(np.max(abs(pressure - z["pressure_tag" + str(i)])))
            require(np.allclose(pressure, z["pressure_tag" + str(i)], rtol=1e-12, atol=1e-14), "Tagged exported pressure disagrees with conserved moments")
            tag_recovery["tag" + str(i) + "_pressure"] = pmax
        qcs = cs_contribution(populations, np.asarray(state), exact_vacuum_allowed=True)
        for label, recovered, exported in (("qCSxxx_tagged_NPZ", qcs, z["qCSxxx"]),
                                            ("qCSxxx_observable_binary", qcs, fields["qCSxxx"]),
                                            ("conditional_qxxx_NPZ", fields["qxxx_conditional_raw_third"], z["qxxx_conditional_raw_third"])):
            maximum = float(np.max(abs(recovered - exported)))
            require(np.allclose(recovered, exported, rtol=1e-12, atol=1e-14), "PIC tagged recovery disagrees: " + label)
            tag_recovery[label] = maximum
    provenance = {"metadata": config["metadata"], "metadata_sha256": sha256(path),
                  "full_archive_receipt": config.get("full_archive_receipt", "data/full-archive-verification.json"),
                  "full_archive_receipt_sha256": sha256(receipt_path), "archive": meta["archive"],
                  "conserved_export": conserved, "observable_export": observable,
                  "tagged_export": tagged,
                  "snapshot": {k: snap[k] for k in ("filename_frame_token", "TIME", "ITER", "aggregate_moment_members", "raw_third_members", "conditional_qxxx_available")},
                  "grid": meta["grid"], "moment_semantics": meta["moment_semantics"],
                  "conditional_qxxx_definition": meta["conditional_qxxx_definition"], "conformance": conformance,
                  "tagged_qCS_interpretation": {"definition": meta["qCSxxx_definition"],
                      "depends_on_third_diagnostic": False, "population_decomposition": "Actual deposited PIC tag1/tag2 first and second moments, not a synthetic split of the aggregate.",
                      "tag_covariance_conformance": tag_conformance,
                      "all_tag_covariances_nonnegative": all(d["covariance_nonnegative_passed"] for d in tag_conformance),
                      "independent_recovery_max_absolute_difference": tag_recovery,
                      "qualification": "The algebraic qCS reference uses documented first/second diagnostics. Small negative recovered tagged covariance values are retained without clipping and do not pass strict nonnegativity; this diagnostic comparison is not a physical-state conformance certificate or a full heat-flux comparison."},
                  "central_qxxx_interpretation": {"normalization_verified": False,
                      "assumption": "The v1v1v1 population diagnostics are unnormalized raw third moments.",
                      "qualification": "The deposit explicitly defines first/second diagnostics, but third HDF5 LABEL/UNITS do not distinguish normalization and the exact custom implementation is unavailable. Every comparison using exported central qxxx is conditional; density/current/pressure are unaffected."},
                  "primitive_recovery_max_absolute_difference": derivation}
    return fields, provenance, meta["grid"]


def load_case(case: dict, project: Path, cache: Path, grid: dict) -> tuple[dict, dict, dict]:
    populations, inputs, conformances, times, frames = [], [], [], [], []
    require(case["population_count"] in (1, 2), "Expected one or two populations")
    require(len(case["moment_exports"]) == case["population_count"], "Population count differs from moment exports")
    reference_pins = load_json(relative_path(project, case["archive_reference_provenance"]))["reference_snapshots"] if case["kind"] == "archived_source" else []
    completion = None
    if case["kind"] == "solver_control":
        require(case.get("execution_status") == "completed_native_stop", "Enabled solver control must declare completed-native-stop execution")
        require(case.get("role") in {"baseline", "matched"}, "Unknown solver-control intervention role")
        require(bool(case.get("completion_receipt")), "Solver-control inputs require the read-only collector's completed regular30 receipt")
        completion_path = relative_path(cache, case["completion_receipt"])
        completion = load_json(completion_path)
        require(completion["status"] == "completed_native_stop" and completion["all_decoding_checks_passed"]
                and completion["source_comparison_is_regular_frame30"] and completion["frame"] == 30,
                "Solver-control completion/regular30 receipt does not pass")
        expected_native_case = str(case["population_count"]) + "-fluid-" + ("unmatched" if case["role"] == "baseline" else "aggregate-matched")
        require(completion["case"] == expected_native_case, "Completed native case differs from declared intervention role/population count")
        expected_case_id = case["role"] + ("_one_fluid" if case["population_count"] == 1 else "_two_fluid")
        require(case["id"] == expected_case_id, "Solver-control case ID differs from its declared intervention role/population count")
    for entry in case["moment_exports"]:
        archive_binding = None
        npz_path, metadata_path = relative_path(cache, entry["npz"]), relative_path(cache, entry["metadata"])
        metadata = load_json(metadata_path)
        require(sha256(npz_path) == metadata["numeric_export_sha256"], "Decoded NPZ SHA-256 differs from reader metadata")
        if completion is not None:
            pin = next(p for p in completion["exports"] if p["npz"] == entry["npz"] and p["metadata"] == entry["metadata"])
            require(pin["source_sha256"] == metadata["source_sha256"] and pin["numeric_export_sha256"] == metadata["numeric_export_sha256"]
                    and pin["metadata_sha256"] == sha256(metadata_path), "Control decoded inputs differ from completed-case receipt")
        if reference_pins:
            pin = next(p for p in reference_pins if p["local_filename"] == metadata["source_filename"])
            require(pin["sha256"] == metadata["source_sha256"] and pin["numeric_export_sha256"] == metadata["numeric_export_sha256"], "Archived source export is not bound to reference provenance")
            require(pin["archive_size_and_publisher_MD5_verified"], "Archived fluid reference lacks complete archive verification")
            archive_binding = {k: pin[k] for k in ("archive", "archive_sha256", "exact_member_name", "sha256", "archive_full_MD5", "archive_full_SHA256", "archive_size_and_publisher_MD5_verified")}
        attrs = metadata["attribute_values"]
        require(attrs["numCells"] == list(reversed(grid["shape_y_x"])), "Different grid resolution; interpolation is disabled")
        require(attrs["lowerBounds"] == [grid["bounds_x"][0], grid["bounds_y"][0]] and attrs["upperBounds"] == [grid["bounds_x"][1], grid["bounds_y"][1]], "Different grid bounds")
        require(attrs["polyOrder"] == 0 and attrs["lowerGhost"] == attrs["upperGhost"] == 0, "Expected zero-ghost point/cell values with polyOrder=0")
        require(attrs["mass"] == 1 and attrs["charge"] == -1, "Different population mass/charge normalization")
        with np.load(npz_path, allow_pickle=False) as z:
            require(z["CartGridField"].shape == tuple(attrs["numCells"]) + (10,), "Different BP conserved component count")
            state = np.asarray(z["CartGridField"], dtype=np.float64).transpose(1, 0, 2)
            time, frame = float(z["time"].item()), int(z["frame"].item())
        require(np.isfinite(time) and time >= 0 and frame >= 0, "Invalid actual snapshot time/frame")
        require(time == metadata["time"] and frame == metadata["frame"], "NPZ timing differs from reader metadata")
        if completion is not None:
            require(time == completion["actual_time"] and frame == 30, "Control output differs from completed regular30 timing")
        _, conformance = moments(state, metadata["source_filename"])
        populations.append(state)
        times.append(time); frames.append(frame); conformances.append(conformance)
        inputs.append({"npz": entry["npz"], "npz_sha256": metadata["numeric_export_sha256"],
                       "metadata": entry["metadata"], "metadata_sha256": sha256(metadata_path),
                       "source_BP_filename": metadata["source_filename"], "source_BP_sha256": metadata["source_sha256"],
                       "actual_time": time, "frame": frame, "recorded_changeset": attrs.get("changeset"),
                       "recorded_builddate": attrs.get("builddate"), "verified_archive_member_binding": archive_binding})
    require(len(set(times)) == len(set(frames)) == 1, "Population outputs have different actual times or frames")
    aggregate = np.sum(populations, axis=0)
    fields, aggregate_conformance = moments(aggregate, case["id"] + " aggregate")
    fields.pop("ux")
    if len(populations) == 2:
        fields[QNAME] = cs_contribution(populations, aggregate)
        fields[QTAGNAME] = fields[QNAME]
        qscope = {"status": "computed_contribution", "definition": "sum_s[3*P_sxx*(u_sx-u_x)+rho_s*(u_sx-u_x)^3]",
                  "scope": "Population-recentering contribution only. Intrinsic population heat flux is not reconstructed; a local-divergence closure does not uniquely determine the full tensor.",
                  "target": "PIC central qxxx conditional on the unnormalized-raw-third interpretation",
                  "third_diagnostic_normalization_verified": False,
                  "additional_target": "Actual tagged PIC qCS from documented first/second diagnostics; population-decomposition dependent and algebraic covariance caveats retained.",
                  "same_contribution_two_distinct_reference_targets": [QNAME, QTAGNAME]}
    else:
        qscope = {"status": "omitted_for_one_population", "scope": "The single-population counter-streaming contribution is identically zero; this does not assert zero full heat flux under a finite local-divergence closure."}
    case_report = {"id": case["id"], "kind": case["kind"], "role": case.get("role"), "population_count": len(populations),
                    "actual_time": times[0], "frame": frames[0], "inputs": inputs,
                    "population_conformance": conformances, "aggregate_conformance": aggregate_conformance,
                    "qCS_scope": qscope}
    if completion is not None:
        case_report.update(runtime_context=completion["runtime_context"],
                           completed_case_receipt={"path": case["completion_receipt"], "sha256": sha256(completion_path),
                                                   "source_run_receipt_sha256": completion["source_run_receipt_sha256"]})
    diagnostic = {"frame30_or_source_final": {"actual_time": times[0], "frame": frames[0],
                  "integrals": integrated_particle_moments(populations, float(np.prod(grid["spacing_x_y"])))} }
    if case.get("initial_moment_exports"):
        initial_states, initial_inputs = [], []
        initial_pins = load_json(relative_path(project, case["archive_initial_provenance"]))["decoded_numeric_exports"] if case["kind"] == "archived_source" else []
        require(len(case["initial_moment_exports"]) == case["population_count"], "Initial population count differs")
        for entry in case["initial_moment_exports"]:
            base = project if entry.get("base") == "project" else cache
            npz_path, metadata_path = relative_path(base, entry["npz"]), relative_path(base, entry["metadata"])
            metadata = load_json(metadata_path)
            require(sha256(npz_path) == metadata["numeric_export_sha256"], "Initial numeric export SHA differs")
            attrs = metadata["attribute_values"]
            require(attrs["numCells"] == list(reversed(grid["shape_y_x"])) and attrs["lowerBounds"] == [grid["bounds_x"][0], grid["bounds_y"][0]]
                    and attrs["upperBounds"] == [grid["bounds_x"][1], grid["bounds_y"][1]] and attrs["mass"] == 1 and attrs["charge"] == -1,
                    "Initial grid/normalization differs")
            require(attrs["polyOrder"] == 0 and attrs["lowerGhost"] == attrs["upperGhost"] == 0, "Unexpected initial basis/ghosts")
            if completion is not None:
                pin = next(p for p in completion["initial_exports"] if p["npz"] == entry["npz"] and p["metadata"] == entry["metadata"])
                require(pin["source_sha256"] == metadata["source_sha256"] and pin["numeric_export_sha256"] == metadata["numeric_export_sha256"]
                        and pin["metadata_sha256"] == sha256(metadata_path), "Initial export differs from completed receipt")
            if initial_pins:
                pin = next(p for p in initial_pins if p["file"] == metadata["source_filename"])
                require(pin["bp_sha256"] == metadata["source_sha256"] and pin["numeric_export_sha256"] == metadata["numeric_export_sha256"], "Archived initial pin differs")
            with np.load(npz_path, allow_pickle=False) as z:
                require(float(z["time"].item()) == 0 and int(z["frame"].item()) == 0, "Initial export is not native time0/frame0")
                initial = np.asarray(z["CartGridField"], dtype=np.float64).transpose(1, 0, 2)
            require(initial.shape == tuple(grid["shape_y_x"]) + (10,), "Initial state shape differs")
            _, conformance = moments(initial, case["id"] + " initial")
            initial_states.append(initial)
            initial_inputs.append({"npz": entry["npz"], "base": entry.get("base", "cache"), "npz_sha256": metadata["numeric_export_sha256"],
                                   "metadata": entry["metadata"], "metadata_sha256": sha256(metadata_path),
                                   "source_BP_sha256": metadata["source_sha256"], "conformance": conformance})
        _, initial_aggregate_conformance = moments(sum(initial_states), case["id"] + " initial aggregate")
        diagnostic["frame0"] = {"actual_time": 0., "frame": 0, "inputs": initial_inputs,
                                "aggregate_conformance": initial_aggregate_conformance,
                                "integrals": integrated_particle_moments(initial_states, float(np.prod(grid["spacing_x_y"])))}
    else:
        diagnostic["frame0"] = {"status": "not_supplied", "scope": "No initial-to-final drift inferred without actual initial outputs."}
    if "integrals" in diagnostic["frame0"]:
        initial, final = diagnostic["frame0"]["integrals"]["aggregate"], diagnostic["frame30_or_source_final"]["integrals"]["aggregate"]
        diagnostic["aggregate_final_minus_initial"] = {k: (np.asarray(final[k]) - np.asarray(initial[k])).tolist() for k in initial}
        diagnostic["aggregate_fractional_change"] = {k: ((final[k] - initial[k]) / initial[k] if initial[k] != 0 else None)
                                                     for k in ("mass", "bulk_kinetic_energy", "internal_energy", "bulk_plus_internal_particle_energy")}
    case_report["particle_moment_diagnostics"] = diagnostic
    auxiliary = {}
    if case.get("field_export"):
        entry = case["field_export"]
        npz_path, metadata_path = relative_path(cache, entry["npz"]), relative_path(cache, entry["metadata"])
        metadata = load_json(metadata_path)
        require(sha256(npz_path) == metadata["numeric_export_sha256"], "Field export SHA differs")
        if completion is not None:
            pin = next(p for p in completion["exports"] if p["npz"] == entry["npz"] and p["metadata"] == entry["metadata"])
            require(pin["source_sha256"] == metadata["source_sha256"] and pin["numeric_export_sha256"] == metadata["numeric_export_sha256"]
                    and pin["metadata_sha256"] == sha256(metadata_path), "Field export differs from completed receipt")
        if reference_pins:
            pin = next(p for p in reference_pins if p["local_filename"] == metadata["source_filename"])
            require(pin["sha256"] == metadata["source_sha256"] and pin["numeric_export_sha256"] == metadata["numeric_export_sha256"], "Archived field export differs from provenance")
        with np.load(npz_path, allow_pickle=False) as z:
            require(float(z["time"].item()) == times[0] and int(z["frame"].item()) == frames[0], "Field/moment native time/frame differs")
            field = np.asarray(z["CartGridField"], dtype=np.float64).transpose(1, 0, 2)
        require(field.shape == tuple(grid["shape_y_x"]) + (8,) and np.isfinite(field).all(), "Expected finite all-eight-component field array")
        auxiliary["all_eight_fields"] = field
        case_report["field_input"] = {"npz": entry["npz"], "metadata": entry["metadata"], "npz_sha256": metadata["numeric_export_sha256"],
                                      "metadata_sha256": sha256(metadata_path), "source_BP_sha256": metadata["source_sha256"],
                                      "actual_time": times[0], "frame": frames[0]}
    return fields, case_report, auxiliary


def paired_effects(pair: dict, fields: dict, cases: dict) -> dict:
    baseline_id, matched_id = pair["baseline"], pair["matched"]
    if baseline_id not in fields or matched_id not in fields:
        return {"id": pair["id"], "status": "not_computed", "baseline": baseline_id, "matched": matched_id,
                "reason": "Both actual valid case outputs are required; no result is imputed."}
    baseline, matched = cases[baseline_id], cases[matched_id]
    require(baseline["population_count"] == matched["population_count"], "Paired cases have different population counts")
    if baseline.get("kind") == "solver_control" or matched.get("kind") == "solver_control":
        require(baseline.get("kind") == matched.get("kind") == "solver_control" and baseline["runtime_context"] == matched["runtime_context"],
                "Paired controls have different controller/research revision/executable/runtime/dependency/preparation/init-gate context")
        require(baseline["role"] == "baseline" and matched["role"] == "matched", "Paired control intervention roles are reversed or undeclared")
    values = {}
    for quantity in sorted(set(fields[baseline_id]) & set(fields[matched_id])):
        values[quantity] = {"error_change_depends_on_unverified_third_diagnostic_normalization": quantity == QNAME,
                            "field_effect_depends_on_third_diagnostic": False}
        for domain, transform in (("full_2D_grid", lambda x: x), ("x_averaged_profile", lambda x: x.mean(axis=1))):
            effect = error_metrics(transform(fields[matched_id][quantity]), transform(fields[baseline_id][quantity]))
            deltas = {}
            for norm in ("relative_L1", "relative_L2"):
                b = baseline["metrics"][quantity][domain][norm]
                m = matched["metrics"][quantity][domain][norm]
                change = m - b if b is not None and m is not None else None
                deltas[norm] = {"matched_minus_baseline_error": change,
                                "fractional_change_from_baseline_error": change / b if change is not None and b != 0 else None,
                                "fractional_change_null_reason": "missing_or_zero_baseline_error" if change is None or b == 0 else None}
            values[quantity][domain] = {"matched_minus_baseline_field_effect": effect, "error_changes_against_same_PIC_reference": deltas}
    return {"id": pair["id"], "status": "computed", "baseline": baseline_id, "matched": matched_id,
            "baseline_actual_time": baseline["actual_time"], "matched_actual_time": matched["actual_time"],
            "matched_minus_baseline_time": matched["actual_time"] - baseline["actual_time"],
            "time_interpolation_performed": False, "negative_error_change_means_smaller_error": True, "quantities": values}


def clean_versus_archive(specification: dict, fields: dict, auxiliary: dict, cases: dict) -> dict:
    clean_id, archive_id = specification["clean"], specification["archived"]
    if clean_id not in fields or archive_id not in fields:
        return {"clean": clean_id, "archived": archive_id, "status": "not_computed",
                "reason": "Both actual valid clean-unmatched and archived source outputs are required."}
    clean, archived = cases[clean_id], cases[archive_id]
    require(clean["kind"] == "solver_control" and clean["role"] == "baseline" and archived["kind"] == "archived_source", "Direct archive comparison has different roles")
    require(clean["population_count"] == archived["population_count"] and clean["frame"] == archived["frame"] == 30,
            "Direct comparison requires same population count and native regular frame30")
    values = {}
    names = ["rho", "Jz", "Pxx", "Pzz"] + ([QNAME] if QNAME in fields[clean_id] and QNAME in fields[archive_id] else [])
    for name in names:
        model, reference = fields[clean_id][name], fields[archive_id][name]
        values[name] = {"full_2D_grid": error_metrics(model, reference),
                        "x_averaged_profile": error_metrics(model.mean(axis=1), reference.mean(axis=1)),
                        "reference": "Archived source fluid output of same population count, not PIC",
                        "depends_on_third_diagnostic_normalization": False}
    require("all_eight_fields" in auxiliary[clean_id] and "all_eight_fields" in auxiliary[archive_id], "Direct archive comparison lacks all-eight-component fields")
    model, reference = auxiliary[clean_id]["all_eight_fields"], auxiliary[archive_id]["all_eight_fields"]
    return {"clean": clean_id, "archived": archive_id, "status": "computed", "clean_actual_time": clean["actual_time"],
            "archived_actual_time": archived["actual_time"], "clean_minus_archived_time": clean["actual_time"] - archived["actual_time"],
            "native_frame": 30, "time_interpolation_performed": False, "moment_quantities": values,
            "all_eight_stored_field_components": {"full_2D_grid": error_metrics(model, reference),
                "x_averaged_profile": error_metrics(model.mean(axis=1), reference.mean(axis=1)),
                "by_stored_component": {str(i): {"full_2D_grid": error_metrics(model[..., i], reference[..., i]),
                    "x_averaged_profile": error_metrics(model[..., i].mean(axis=1), reference[..., i].mean(axis=1))} for i in range(8)},
                "scope": "All eight stored components retained; vector norms include every cell/component. Component indices do not assign physical meaning to the final two values."},
            "scope": "Direct clean-base versus archived dirty-build output agreement at actual available times, not a claim to reproduce the private original executable. qCS is only the population-recentering contribution."}


def self_test() -> dict:
    ref = np.array([[1., -1.], [2., -2.]])
    metrics = error_metrics(2 * ref, ref)
    require(metrics["relative_L1"] == metrics["relative_L2"] == 1, "Known norm check failed")
    zero = error_metrics((2 * ref).mean(axis=1), ref.mean(axis=1))
    require(zero["relative_L1"] is None and zero["relative_L2"] is None, "Zero denominator was not null")
    states = []
    for velocity, temperature in ((1., 1.), (-1., 2.)):
        a = np.zeros((2, 2, 10)); a[..., 0] = .5; a[..., 1] = .5 * velocity
        a[..., 4] = .5 * (temperature + velocity**2); a[..., 7] = a[..., 9] = .5 * temperature
        moments(a, "analytic Gaussian population")
        states.append(a)
    require(np.array_equal(cs_contribution(states, sum(states)), np.full((2, 2), -1.5)), "Analytic two-Gaussian third-moment contribution failed")
    integrals = integrated_particle_moments(states, 1.)
    require(integrals["aggregate"]["mass"] == 4 and integrals["aggregate"]["bulk_plus_internal_particle_energy"] == 11
            and integrals["aggregate"]["bulk_kinetic_energy"] == 0 and integrals["sum_of_population_bulk_kinetic_energy"] == 2,
            "Analytic mass/particle-energy or decomposition check failed")
    exact_vacuum = np.zeros_like(states[0])
    require(np.array_equal(cs_contribution([sum(states), exact_vacuum], sum(states), exact_vacuum_allowed=True), np.zeros((2, 2))), "Exact-vacuum tag contribution was not zero")
    bad_vacuum = exact_vacuum.copy(); bad_vacuum[..., 4] = 1
    try:
        cs_contribution([sum(states), bad_vacuum], sum(states), exact_vacuum_allowed=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Nonzero vacuum-tag moment was accepted")
    bad = states[0].copy(); bad[..., 4] = -1
    try:
        moments(bad, "expected invalid pressure")
    except ConformanceError as e:
        require(bool(e.report["violations"]), "Invalid-pressure failure not retained")
    else:
        raise AssertionError("Negative pressure was accepted")
    analytic_fields = {"baseline": {"rho": ref}, "matched": {"rho": 2 * ref}}
    analytic_cases = {name: {"population_count": 1, "actual_time": 0,
                            "metrics": compare_fields(values, {"rho": ref})} for name, values in analytic_fields.items()}
    pair = paired_effects({"id": "analytic_pair", "baseline": "baseline", "matched": "matched"}, analytic_fields, analytic_cases)
    change = pair["quantities"]["rho"]["full_2D_grid"]["error_changes_against_same_PIC_reference"]["relative_L2"]
    require(change["matched_minus_baseline_error"] == 1 and change["fractional_change_from_baseline_error"] is None,
            "Paired delta-error sign or zero-baseline null handling failed")
    direct_fields = {name: {q: (2 * ref if name == "clean" else ref) for q in ("rho", "Jz", "Pxx", "Pzz")} for name in ("clean", "archive")}
    direct_cases = {"clean": {"kind": "solver_control", "role": "baseline", "population_count": 1, "frame": 30, "actual_time": 300.1},
                    "archive": {"kind": "archived_source", "population_count": 1, "frame": 30, "actual_time": 300.}}
    direct_aux = {name: {"all_eight_fields": np.zeros((2, 2, 8))} for name in ("clean", "archive")}
    direct = clean_versus_archive({"clean": "clean", "archived": "archive"}, direct_fields, direct_aux, direct_cases)
    require(direct["moment_quantities"]["Jz"]["full_2D_grid"]["relative_L2"] == 1 and
            direct["all_eight_stored_field_components"]["full_2D_grid"]["relative_L2"] is None,
            "Direct archive comparison or zero-field denominator check failed")
    private_cache, private_project = Path("G:/Private Cache Redaction Check"), Path("E:/Private Project Redaction Check")
    errors = [FileNotFoundError(2, "missing", str(private_cache / "missing.npz")),
              "Missing " + str(private_cache).replace("\\", "/") + "/missing.npz",
              FileNotFoundError(2, "missing", str(private_project / "missing.json"))]
    redacted = [sanitize_error(error, private_cache, private_project) for error in errors]
    require(all("Redaction Check" not in value and ("$CACHE_ROOT" in value or "$PROJECT_ROOT" in value) for value in redacted),
            "Private local prefix survived Windows filename or slash-form failure redaction")
    return {"known_norm_scaling": True, "zero_denominator_null": True, "analytic_unequal_temperature_qCS": True,
            "exact_vacuum_zero_contribution": True, "inconsistent_vacuum_rejected": True,
            "paired_error_difference_and_zero_baseline_null": True,
            "Windows_repr_and_slash_form_failure_paths_redacted": True,
            "analytic_integrated_particle_mass_energy_and_decomposition": True,
            "analytic_direct_archive_comparison_and_zero_field_null": True,
            "negative_pressure_rejected_with_failure_record": True, "scope": "Small analytic pipeline checks, not solver results."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-config", type=Path, default=ROOT / "data/source-final-comparison-config.json")
    parser.add_argument("--cache-root", type=Path, help="Local nonpublic input cache; no private path is built into the code/config")
    parser.add_argument("--output", type=Path, default=ROOT / "results/source-final-comparison.json")
    parser.add_argument("--provenance-output", type=Path, default=ROOT / "data/provenance-source-final-comparison.json")
    parser.add_argument("--profiles-output", type=Path, default=ROOT / "data/derived/source-final-comparison-profiles.csv")
    parser.add_argument("--self-test", action="store_true", help="Run analytic norm/contribution/conformance checks only")
    args = parser.parse_args()
    tests = self_test()
    if args.self_test:
        print(json.dumps(tests)); return 0
    if args.cache_root is None:
        parser.error("--cache-root is required for actual data comparison")
    config = load_json(args.case_config)
    require(config["schema_version"] == 1, "Unsupported case-config schema")
    require(len({c["id"] for c in config["cases"]}) == len(config["cases"]), "Duplicate case IDs")
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": sha256(Path(__file__)),
              "config_sha256": sha256(args.case_config), "numpy": np.__version__, "analytic_pipeline_checks": tests,
              "scope": config["scope"], "simulation_performed_by_this_script": False,
              "metric_definitions": {"full_2D_grid": "Unmasked complete [y,x] domain; relative L2=norm(model-PIC)/norm(PIC), relative L1=sum(abs(model-PIC))/sum(abs(PIC)). Uniform cell-area factors cancel.",
                    "x_averaged_profile": "First arithmetic x mean at each y, then one-dimensional L1/L2 errors. These are separate projected diagnostics and may cancel x structure.",
                    "zero_denominator": "Null relative error, with an explicit reason; no epsilon denominator or favorable ROI.",
                    "time": "Actual available output times retained, with offsets; no time interpolation or exact-t=300 substitution."},
              "cases": [], "paired_effects": [], "clean_unmatched_vs_archived_source": [], "failures": []}
    all_fields, all_auxiliary = {}, {}
    try:
        reference, pic, grid = load_pic(config["PIC_reference"], ROOT, args.cache_root)
        report["PIC_reference"] = pic
    except Exception as e:
        report["failures"].append({"stage": "PIC_reference", "error_type": type(e).__name__, "message": sanitize_error(e, args.cache_root)})
        report["all_actual_cases_passed"] = False
        report["profile_export_generated"] = False
        write_json(args.output, report)
        write_json(args.provenance_output, {"script_sha256": report["script_sha256"], "config_sha256": report["config_sha256"],
                                            "all_actual_cases_passed": False, "failures": report["failures"], "profile_export_generated": False})
        print(json.dumps({"status": "failed", "stage": "PIC_reference", "failure_count": 1})); return 1
    for case in config["cases"]:
        if not case.get("enabled", True):
            report["cases"].append({"id": case["id"], "status": "not_run", "reason": case.get("pending_reason", "Disabled; no actual solver output is claimed."),
                                     "execution_status": case.get("execution_status", "not_claimed")})
            continue
        try:
            require(case["kind"] in {"archived_source", "solver_control"}, "Unknown case kind")
            fields, case_report, auxiliary = load_case(case, ROOT, args.cache_root, grid)
            case_report.update({"status": "compared", "PIC_reference_actual_time": pic["snapshot"]["TIME"],
                                "time_minus_PIC": case_report["actual_time"] - pic["snapshot"]["TIME"],
                                "same_actual_time_as_PIC": case_report["actual_time"] == pic["snapshot"]["TIME"],
                                "time_interpolation_performed": False, "metrics": compare_fields(fields, reference)})
            report["cases"].append(case_report)
            all_fields[case["id"]] = fields
            all_auxiliary[case["id"]] = auxiliary
        except Exception as e:
            failure = {"id": case["id"], "status": "failed", "error_type": type(e).__name__,
                       "message": sanitize_error(e, args.cache_root)}
            if isinstance(e, ConformanceError):
                failure["conformance_failure"] = e.report
            report["cases"].append(failure); report["failures"].append(failure)
    cases = {c["id"]: c for c in report["cases"]}
    for pair in config.get("pairs", []):
        try:
            report["paired_effects"].append(paired_effects(pair, all_fields, cases))
        except Exception as e:
            failure = {"id": pair["id"], "status": "failed", "error_type": type(e).__name__, "message": sanitize_error(e, args.cache_root)}
            report["paired_effects"].append(failure); report["failures"].append(failure)
    for specification in config.get("direct_archived_comparisons", []):
        try:
            report["clean_unmatched_vs_archived_source"].append(clean_versus_archive(specification, all_fields, all_auxiliary, cases))
        except Exception as e:
            failure = {"clean": specification["clean"], "archived": specification["archived"], "status": "failed",
                       "error_type": type(e).__name__, "message": sanitize_error(e, args.cache_root)}
            report["clean_unmatched_vs_archived_source"].append(failure); report["failures"].append(failure)
    profiles = {"raw_y": grid["bounds_y"][0] + (np.arange(grid["shape_y_x"][0]) + .5) * grid["spacing_x_y"][1]}
    for name, value in reference.items():
        profiles["PIC_" + ("qxxx_CONDITIONAL_raw_third" if name == "qxxx_conditional_raw_third" else name)] = value.mean(axis=1)
    for name, fields in all_fields.items():
        for quantity, value in fields.items():
            profiles[name + "_" + quantity] = value.mean(axis=1)
    args.profiles_output.parent.mkdir(parents=True, exist_ok=True)
    with args.profiles_output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n"); writer.writerow(profiles); writer.writerows(zip(*profiles.values()))
    enabled_count = sum(c.get("enabled", True) for c in config["cases"])
    report["requested_actual_case_count"] = enabled_count
    report["all_actual_cases_passed"] = not report["failures"] if enabled_count else None
    report["profile_export_sha256"] = sha256(args.profiles_output)
    report["counter_streaming_qualification"] = "qCSxxx is only a population-recentering contribution, not unique full fluid heat flux under a local-divergence closure. Its separate comparison to the actual tagged PIC qCS uses documented first/second moments, with negative tagged covariance diagnostics retained explicitly. Exported PIC central qxxx additionally assumes unverified unnormalized third diagnostics, so that target's comparisons are conditional. One-population zero contributions are omitted."
    write_json(args.output, report)
    provenance = {"generated_at_utc": report["generated_at_utc"], "script_sha256": report["script_sha256"],
                  "config_sha256": report["config_sha256"], "result_sha256": sha256(args.output),
                  "profile_export_sha256": report["profile_export_sha256"], "PIC_reference": pic,
                  "case_inputs": [{k: c[k] for k in ("id", "kind", "role", "actual_time", "frame", "inputs", "field_input", "runtime_context", "completed_case_receipt", "execution_status") if k in c} for c in report["cases"]],
                  "all_actual_cases_passed": report["all_actual_cases_passed"], "failure_count": len(report["failures"]),
                  "raw_cache_paths_omitted": True, "simulation_performed_by_this_script": False}
    write_json(args.provenance_output, provenance)
    print(json.dumps({"status": "not_run" if not enabled_count else "passed" if report["all_actual_cases_passed"] else "failed", "actual_cases": len(all_fields),
                      "failed_cases_or_pairs": len(report["failures"]), "PIC_actual_time": pic["snapshot"]["TIME"],
                      "case_times": {c["id"]: c.get("actual_time") for c in report["cases"] if c["status"] == "compared"}}))
    return 1 if report["all_actual_cases_passed"] is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
