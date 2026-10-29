# Archived-output and future-control comparison

`experiments/analyze_gkeyll_controls.py` analyzes existing numeric exports. It
does not run a solver, download data, interpolate time, repair raw values, or
select a region of interest. The source configuration compares the actual
archived one- and two-fluid final outputs. The four-case example is disabled
until real control outputs have been decoded; it contains no solver results.

## Reproduction

Use the ordinary NumPy requirements. ADIOS2 is needed only for the separate BP
decoding step described in `fluid-reference-README.md`, not for comparison.
Prepare a local cache with these relative directories:

```text
$CACHE_ROOT/reference-fluid/decoded/*.npz
$CACHE_ROOT/reference-fluid/decoded/*.metadata.json
$CACHE_ROOT/pic-export-v2/reference-pic-frame-000300-conserved.f64
$CACHE_ROOT/pic-export-v2/reference-pic-frame-000300-observables.f64
$CACHE_ROOT/pic-export-v2/reference-pic-frame-000300-tagged.npz
```

The BP files are decoded using `experiments/read_gkeyll_bp.py`. The PIC files
are generated using `experiments/export_pic_moments.py`; select the same output
directory in that exporter's `--output-dir`. Export and archive verification
receipts are checked before comparison. Cache files remain outside Git or under
the ignored `data/raw/` tree.

```sh
python experiments/analyze_gkeyll_controls.py --self-test
python experiments/analyze_gkeyll_controls.py --cache-root "$CACHE_ROOT"
```

Outputs are `results/source-final-comparison.json`,
`data/provenance-source-final-comparison.json`, and
`data/derived/source-final-comparison-profiles.csv`. The JSON pins input/export,
script, configuration, result, and CSV hashes. No private cache path is needed
in the scientific logic or public receipts.

## Quantities, domains, and times

The conserved order is independently documented in
`gkeyll-layout-provenance.json`: rho, rho*ux, rho*uy, rho*uz, Mxx, Mxy, Mxz, Myy,
Myz, Mzz. With the source's electron mass 1 and charge -1, Jz is minus the z
momentum. Pressure is recovered from the complete conserved tensor after
population aggregation. This current is moment-derived, not a native deposited
current diagnostic.

Primary errors use every 640 by 480 cell without masking. Relative L2 is
norm(model-reference)/norm(reference); relative L1 is
sum(abs(model-reference))/sum(abs(reference)). Separate profile metrics first
average over x and then take one-dimensional norms; those projected metrics can
cancel x structure. Zero reference norms produce null relative errors with a
reason, never an epsilon denominator.

The actual PIC reference time is 300.0015 (ITER 4500). Archived one-fluid frame
30 is at 300.0001500000136 and two-fluid frame 30 at 300.0499847996274. Filenames
ending in `_300` do not establish equal times. The comparison records these
offsets and performs no temporal interpolation. These existing runs do not
isolate an initialization effect or establish a new simulation result.

## Two distinct counter-streaming comparisons

For two fluid populations the script reconstructs

```text
qCSxxx = sum_s [3*P_sxx*(u_sx-u_x) + rho_s*(u_sx-u_x)^3].
```

This is a population-recentering contribution. A local divergence closure does
not uniquely supply the omitted intrinsic population heat-flux tensors.
One-population zero counter-streaming contributions are omitted; no zero full
heat-flux claim follows.

The same fluid contribution is compared to two explicitly different targets:

* `qCSxxx_contribution_vs_tagged_PIC`: actual deposited PIC tag1/tag2 qCS, using
  the documented first/second diagnostics only. The independently recovered
  contribution agrees with the exporter within 3.47e-18. This is dependent on
  the population decomposition, not a full heat-flux comparison.
* `qCSxxx_contribution`: conditional PIC central qxxx, assuming that the third
  diagnostics are unnormalized raw moments. The deposit does not explicitly
  establish that normalization; HDF5 names and units do not resolve it. Every
  error using this target remains conditional. The first target and the four
  ordinary moment comparisons do not use this assumption.

The tagged reference has exact-vacuum cells with entirely zero conserved
vectors. Their velocities are set to zero solely to evaluate a vanishing
weighted contribution. No density floor is used. Recovered tag covariances
also have small negative diagnostic entries: diagonal minima approximately
-2.18e-11 and -1.91e-11, and eigenvalue minima -3.84e-11 and -2.25e-11. These
fail strict covariance nonnegativity and are retained explicitly without
clipping or excluding cells. The tagged qCS comparison is an algebraic
diagnostic, not certification of physical positive-semidefinite tagged states.
All fluid populations and the aggregate PIC reference pass strict positive
density and positive-definite pressure tests. Nonfinite/negative fluid states
are rejected with retained failure reports.

## Read-only completed-control workflow

`experiments/collect_completed_gkeyll_cases.py` never launches or controls a
solver and never writes into a run directory. Run it under Linux/WSL with the
separately installed optional ADIOS2 reader. The expected hashes below must
come from the reviewed controller/runtime/dependency/preparation records;
observing an unreviewed run receipt alone does not authenticate those pins.
Use explicit local paths for the existing runs, authoritative prepared jobs,
and a separate ignored/nonpublic decoded cache:

```sh
nice -n 10 env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python experiments/collect_completed_gkeyll_cases.py \
  --runs-root "$RUNS_ROOT" --jobs-root "$JOBS_ROOT" --cache-root "$CACHE_ROOT" \
  --expected-controller-sha256 "$CONTROLLER_SHA" \
  --expected-executable-sha256 "$SOLVER_SHA" \
  --expected-research-code-revision "$CODE_REVISION" \
  --expected-runtime-manifest-sha256 "$RUNTIME_SHA" \
  --expected-dependency-lock-sha256 "$DEPENDENCY_LOCK_SHA"
```

If ADIOS2 lives in an isolated target rather than a virtual environment, set
that command's `PYTHONPATH` to its site directory. This changes only the
postprocessor's environment. The collector requires each case's final
`completed_native_stop` receipt, exit zero, retained native logs without the
known numerical-failure marker, and the controller's unchanged-after-exit
regular-frame30 check. It verifies the preparation manifest and actual copied
inputs, selected raw-file hashes against both stop/final receipts, and decoded
time/frame across every moment and eight-component field file. Frame0 moment
files are independently decoded for initial/final integral diagnostics. A
forced-final or later output is never substituted for regular frame30.

Portable receipts preserve the source start/finish UTC timestamps, their
separately calculated `UTC_timestamp_difference_seconds`, and the controller's
original `elapsed_seconds`. The latter is explicitly Linux `time.monotonic`
elapsed duration, not CPU time. These two timing conventions can differ after
clock adjustments; neither is silently corrected to match the other, and no
clock or runtime setting is changed by the postprocessor.

Missing, running, failed, and rejected cases remain explicit. Merely finding
BP files or reading progress/run-started files cannot enable a case. Numeric
arrays must be finite and all population/aggregate densities and covariance
pressures must pass strict positivity tests. The decoder preserves existing
raw files and refuses conflicting/partial decoded caches; use a fresh cache
when investigating one. Repeated checks reuse verified completed exports.

The collector writes:

* `results/gkeyll-control-decoding.json`: portable status and sanitized
  per-case completion/decoding provenance, without private local paths.
* `data/gkeyll-completed-control-cases.json`: both archived source cases and
  only actual completed controls enabled. Cache-relative completion receipts
  bind every enabled control NPZ/metadata input for the analyzer.

Once actual controls have completed, produce their distinct analysis artifacts:

```sh
nice -n 10 env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python experiments/analyze_gkeyll_controls.py --cache-root "$CACHE_ROOT" \
  --case-config data/gkeyll-completed-control-cases.json \
  --output results/gkeyll-control-comparison.json \
  --provenance-output data/provenance-gkeyll-control-comparison.json \
  --profiles-output data/derived/gkeyll-control-comparison-profiles.csv
```

The case IDs are `archived_one_fluid`, `archived_two_fluid`,
`baseline_one_fluid`, `baseline_two_fluid`, `matched_one_fluid`, and
`matched_two_fluid`. Every valid case has ordinary moment/PIC errors and
two-fluid contribution comparisons as qualified above. Each baseline also
has an explicit direct comparison with its archived source counterpart,
including complete-grid and x-profile moment/qCS errors and all eight field
components, both combined and individually. The direct comparison records
the actual clean-minus-archived time offset at native frame30; it does not
certify the source's private dirty executable.

Every initialization pair requires identical reviewed runtime context and
reports matched-minus-baseline fields/errors against the same PIC target,
with actual time differences. Negative delta-error means smaller error; zero
baseline error gives null fractional change. Missing/rejected pairs remain
not computed. The disabled `gkeyll-control-cases.example.json` is a planning
template; supplying arbitrary arrays without a completed receipt cannot
create a solver-control result.

## Initial/final particle-moment diagnostics

For every supplied actual frame0/final conserved state, the analyzer integrates
mass, three momenta, bulk kinetic energy, internal energy, and their sum over
the full domain with the uniform cell area. In source units,
bulk energy is the integral of `|momentum|^2/(2*rho)` and the particle-energy
sum is the integral of `(Mxx+Myy+Mzz)/2`. Internal energy is their difference.
Per-population and aggregate values are separate: aggregate internal energy
contains relative population drift. Initial/final differences and fractional
changes are diagnostics only. Electromagnetic energy and boundary/numerical
budgets are absent, so these numbers do not assert exact total-energy
conservation. No initial-to-final change is imputed if initial outputs are
unavailable.
