"""Read-only admissibility diagnostics for completed regular saved frames0--30.

No solver action, state repair, raw-array export or comparison metric. This
checks saved snapshots, not every timestep; frame31 and running cases are never
read. Both covariance PSD and the stricter PD condition are reported.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np

from analyze_gkeyll_controls import ROOT, load_json, require, sanitize_error, sha256
from collect_completed_gkeyll_cases import CONTEXT_KEYS, validate_receipt

PACKED = ((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2))


def require_complete_context(expected: dict) -> None:
    require(isinstance(expected, dict) and set(expected) == set(CONTEXT_KEYS)
            and all(isinstance(value, str) and value for value in expected.values()),
            "Expected context must contain every reviewed runtime-context key with a nonempty string pin")


def save(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def tensor_diagnostic(state: np.ndarray, lower: list, spacing: list) -> dict:
    require(state.ndim == 3 and state.shape[-1] == 10, "Expected native [x,y,10] conserved array")
    finite = np.isfinite(state).all(axis=-1)
    rho = state[..., 0]
    positive_density = np.isfinite(rho) & (rho > 0)
    defined = finite & positive_density
    finite_rho = rho[np.isfinite(rho)]
    report = {"nonfinite_conserved_value_count": int(np.count_nonzero(~np.isfinite(state))),
              "nonfinite_conserved_cell_count": int(np.count_nonzero(~finite)),
              "nonpositive_finite_density_cell_count": int(np.count_nonzero(np.isfinite(rho) & (rho <= 0))),
              "minimum_finite_density": float(finite_rho.min()) if finite_rho.size else None,
              "covariance_undefined_cell_count": int(np.count_nonzero(~defined)),
              "total_cell_count": int(rho.size), "no_clipping_repair_or_density_floor": True,
              "covariance_PSD_passed": False, "strict_covariance_PD_passed": False}
    if not np.any(defined):
        report["eigenanalysis_status"] = "no_defined_covariance_cells"
        return report
    values = state[defined]
    velocity = values[:, 1:4] / values[:, :1]
    raw_second = np.empty((len(values), 3, 3), dtype=np.float64)
    for component, (i, j) in enumerate(PACKED, 4):
        raw_second[:, i, j] = raw_second[:, j, i] = values[:, component]
    with np.errstate(over="ignore", invalid="ignore"):
        pressure = raw_second - values[:, 0, None, None] * np.einsum("ni,nj->nij", velocity, velocity)
    report["nonfinite_covariance_value_count"] = int(np.count_nonzero(~np.isfinite(pressure)))
    if report["nonfinite_covariance_value_count"]:
        report["eigenanalysis_status"] = "nonfinite_covariance_no_eigenanalysis_or_repair"
        return report
    try:
        eigenvalues = np.linalg.eigvalsh(pressure)
    except np.linalg.LinAlgError:
        report["eigenanalysis_status"] = "eigensolver_failed_no_repair_or_PSD_certificate"
        return report
    if not np.isfinite(eigenvalues).all():
        report["eigenanalysis_status"] = "nonfinite_eigenvalues_no_repair_or_PSD_certificate"
        return report
    negative = eigenvalues < 0
    nonpositive = eigenvalues <= 0
    location_in_defined = int(np.argmin(eigenvalues) // 3)
    flat_index = int(np.flatnonzero(defined.ravel())[location_in_defined])
    ix, iy = (int(v) for v in np.unravel_index(flat_index, rho.shape))
    all_defined = bool(np.all(defined))
    report.update(eigenanalysis_status="computed_without_threshold_or_regularization",
                  negative_eigenvalue_count=int(negative.sum()), negative_eigenvalue_cell_count=int(np.any(negative, axis=-1).sum()),
                  zero_eigenvalue_count=int(np.count_nonzero(eigenvalues == 0)),
                  nonpositive_eigenvalue_cell_count=int(np.any(nonpositive, axis=-1).sum()),
                  minimum_pressure_diagonal=float(np.diagonal(pressure, axis1=-2, axis2=-1).min()),
                  minimum_pressure_eigenvalue=float(eigenvalues.min()),
                  minimum_eigenvalue_native_zero_based_x_y=[ix, iy],
                  minimum_eigenvalue_raw_center_x_y=[float(lower[0] + (ix + .5) * spacing[0]), float(lower[1] + (iy + .5) * spacing[1])],
                  covariance_PSD_passed=all_defined and not bool(negative.any()),
                  strict_covariance_PD_passed=all_defined and not bool(nonpositive.any()))
    return report


def self_test() -> dict:
    state = np.zeros((1, 1, 10)); state[..., 0] = 1
    state[..., 4] = state[..., 7] = state[..., 9] = 1
    state[..., 5] = 2  # Positive diagonals, negative xy principal minor.
    result = tensor_diagnostic(state, [0, 0], [1, 1])
    require(result["minimum_pressure_eigenvalue"] == -1 and result["negative_eigenvalue_cell_count"] == 1
            and not result["covariance_PSD_passed"], "Indefinite positive-diagonal tensor was accepted")
    state[..., 5] = 0; state[..., 4] = 0
    result = tensor_diagnostic(state, [0, 0], [1, 1])
    require(result["covariance_PSD_passed"] and not result["strict_covariance_PD_passed"], "PSD and PD were conflated")
    state[..., 0] = 0
    require(tensor_diagnostic(state, [0, 0], [1, 1])["covariance_undefined_cell_count"] == 1, "Zero density was repaired")
    state[..., 0] = 1; state[..., 1] = np.nan
    require(tensor_diagnostic(state, [0, 0], [1, 1])["nonfinite_conserved_cell_count"] == 1, "Nonfinite state was accepted")
    try:
        require_complete_context({})
    except ValueError:
        pass
    else:
        raise AssertionError("Missing runtime context pins were accepted")
    return {"positive_diagonal_indefinite_tensor_rejected": True, "PSD_distinguished_from_PD": True,
            "undefined_density_and_nonfinite_cells_retained": True, "missing_runtime_pins_rejected": True,
            "scope": "Analytic scanner tests, not solver outcomes."}


def summary(frames: list, key: str) -> dict:
    rows = [(f["frame"], f["actual_time"], f[key]) for f in frames]
    failed = [r for r in rows if not r[2]["covariance_PSD_passed"]]
    values = [r[2]["minimum_pressure_eigenvalue"] for r in rows if "minimum_pressure_eigenvalue" in r[2]]
    return {"saved_snapshots_scanned": len(rows), "saved_snapshots_not_PSD": len(failed),
            "first_non_PSD_saved_frame": failed[0][0] if failed else None,
            "first_non_PSD_saved_time": failed[0][1] if failed else None,
            "minimum_pressure_eigenvalue_over_saved_snapshots": min(values) if values else None,
            "maximum_negative_eigenvalue_cell_count": max((r[2].get("negative_eigenvalue_cell_count", 0) for r in rows), default=0),
            "all_saved_snapshots_PSD": bool(rows) and not failed,
            "all_saved_snapshots_strict_PD": bool(rows) and all(r[2]["strict_covariance_PD_passed"] for r in rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path)
    parser.add_argument("--expected-context", type=Path, help="Reviewed portable runtime-context JSON object")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    tests = self_test()
    if args.self_test:
        print(json.dumps(tests)); return 0
    for name in ("run_directory", "expected_context", "output"):
        if getattr(args, name) is None:
            parser.error("--" + name.replace("_", "-") + " is required")
    require(not args.output.is_symlink() and not args.output.with_suffix(args.output.suffix + ".tmp").is_symlink(),
            "Output and temporary output must not be leaf symlinks")
    args.run_directory = args.run_directory.resolve()
    args.expected_context = args.expected_context.resolve()
    args.output = args.output.resolve()
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    require(not args.output.is_relative_to(args.run_directory) and args.output != args.expected_context,
            "Output must be outside the native run directory and different from the expected-context file")
    require(not args.output.exists() and not args.output.is_symlink() and not temporary.exists() and not temporary.is_symlink(),
            "Output and temporary output must be fresh; preserve previous partial/failed scans")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Own this new output before any incremental replacement; native evidence
    # and existing scan files can never be selected as overwrite targets.
    with args.output.open("x", encoding="utf-8") as reserved:
        reserved.write('{"status":"reserved_for_new_saved_snapshot_scan"}\n')
    report = {"status": "scanning", "started_utc": datetime.now(timezone.utc).isoformat(), "frames": [],
              "scanner_sha256": sha256(Path(__file__)), "collector_guard_sha256": sha256(ROOT / "experiments/collect_completed_gkeyll_cases.py"),
              "IO_helper_sha256": sha256(ROOT / "experiments/analyze_gkeyll_controls.py"), "analytic_scanner_tests": tests,
              "scope": "Completed-case regular saved moment snapshots0--30 only; not every timestep or a continuous-trajectory admissibility certificate. Frame31/later outputs are excluded. No raw arrays exported, no comparison metrics, clipping, threshold or repair.",
              "native_array_order": "[x,y,conserved_component]", "covariance_definition": "M_ij-rho*u_i*u_j, with u_i=momentum_i/rho",
              "covariance_PSD_criterion": "Every eigenvalue>=0 and every conserved value finite with strictly positive density; exact zero is distinguished from strict PD.",
              "aggregate_PSD_does_not_override_population_failure": True, "all_requested_saved_frames_scanned": False,
              "failures": [], "private_paths_included": False}
    try:
        run_path = args.run_directory / "run-receipt.json"
        receipt_sha = sha256(run_path); receipt = load_json(run_path)
        native_case = args.run_directory.name
        species = int(native_case.split("-", 1)[0])
        require(species in (1, 2), "Unknown case population count")
        expected = load_json(args.expected_context)
        require_complete_context(expected)
        selected = validate_receipt(receipt, native_case, species, expected)
        report.update(native_case=native_case, native_execution_status=receipt["status"], source_run_receipt_sha256=receipt_sha,
                      expected_context_sha256=sha256(args.expected_context), runtime_context=expected,
                      actual_regular30_time=selected["actual_time"], native_elapsed_seconds=receipt["elapsed_seconds"],
                      source_started_utc=receipt["started_utc"], source_finished_utc=receipt["finished_utc"])
        pins = {p["filename"]: p for p in receipt["output_bp_files"]}
        import adios2
        report["reader_environment"] = {"adios2": adios2.__version__, "numpy": np.__version__}
        previous_time = -1.
        for frame in range(31):
            states, times = [], []
            row = {"frame": frame, "population_source_bindings": []}
            for population in range(1, species + 1):
                filename = f"case_elc{population}_{frame}.bp"
                require(filename in pins, "Missing regular saved moment member in final receipt")
                pin, source = pins[filename], args.run_directory / filename
                require(source.stat().st_size == pin["bytes"] and sha256(source) == pin["sha256"], "Saved moment file differs from native final receipt")
                with adios2.FileReader(str(source)) as reader:
                    state = np.asarray(reader.read("CartGridField"), dtype=np.float64)
                    native_frame = int(np.asarray(reader.read("frame")).item())
                    native_time = float(np.asarray(reader.read("time")).item())
                    cells = np.asarray(reader.read_attribute("numCells")).ravel().tolist()
                    lower = np.asarray(reader.read_attribute("lowerBounds"), dtype=float).ravel().tolist()
                    upper = np.asarray(reader.read_attribute("upperBounds"), dtype=float).ravel().tolist()
                    mass, charge = float(np.asarray(reader.read_attribute("mass")).item()), float(np.asarray(reader.read_attribute("charge")).item())
                require(sha256(source) == pin["sha256"], "Saved moment file changed during read")
                require(cells == [480, 640] and lower == [-24, -32] and upper == [24, 32] and mass == 1 and charge == -1
                        and state.shape == (480, 640, 10), "Unexpected saved-state grid/layout/normalization")
                require(native_frame == frame and np.isfinite(native_time) and native_time >= 0, "Saved native frame/time differs")
                if frame == 0:
                    require(native_time == 0, "Initial saved state is not at native time0")
                if frame == 30:
                    require(native_time == selected["actual_time"] and pin["sha256"] == selected["sha256"][filename], "Regular30 scan member differs from stop receipt")
                spacing = [(upper[i] - lower[i]) / cells[i] for i in range(2)]
                row[f"population{population}"] = tensor_diagnostic(state, lower, spacing)
                row["population_source_bindings"].append({"filename": filename, "bytes": pin["bytes"], "sha256": pin["sha256"],
                                                          "frame": native_frame, "actual_time": native_time})
                states.append(state); times.append(native_time)
            require(len(set(times)) == 1 and times[0] > previous_time, "Population times differ or saved times are not strictly ordered")
            previous_time = row["actual_time"] = times[0]
            row["aggregate"] = tensor_diagnostic(sum(states), lower, spacing)
            report["frames"].append(row)
            save(args.output, report)
            if frame % 10 == 0 or any(not row[f"population{i}"]["covariance_PSD_passed"] for i in range(1, species + 1)):
                print(json.dumps({"native_case": native_case, "scanned_frame": frame, "actual_time": times[0],
                                  "negative_cells_by_population": [row[f"population{i}"].get("negative_eigenvalue_cell_count") for i in range(1, species + 1)]}), flush=True)
        require(sha256(run_path) == receipt_sha, "Native final receipt changed during scan")
        report.update(status="completed_saved_snapshot_scan", finished_utc=datetime.now(timezone.utc).isoformat(),
                      all_requested_saved_frames_scanned=True,
                      summary={key: summary(report["frames"], key) for key in [f"population{i}" for i in range(1, species + 1)] + ["aggregate"]})
        report["all_scanned_populations_PSD"] = all(report["summary"][f"population{i}"]["all_saved_snapshots_PSD"] for i in range(1, species + 1))
        report["all_scanned_populations_strict_PD"] = all(report["summary"][f"population{i}"]["all_saved_snapshots_strict_PD"] for i in range(1, species + 1))
    except Exception as error:
        report.update(status="scanner_failed", finished_utc=datetime.now(timezone.utc).isoformat())
        report["failures"].append({"error_type": type(error).__name__,
            "message": sanitize_error(sanitize_error(error, args.run_directory), args.expected_context.parent)})
    save(args.output, report)
    print(json.dumps({"status": report["status"], "saved_frames_scanned": len(report["frames"]),
                      "all_scanned_populations_PSD": report.get("all_scanned_populations_PSD"), "summary": report.get("summary")}), flush=True)
    return 0 if report["all_requested_saved_frames_scanned"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
