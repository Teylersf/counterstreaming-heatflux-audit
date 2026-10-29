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

## Four future control cases

Copy `gkeyll-control-cases.example.json`, supply the actual decoded NPZ and
metadata paths in each case's `moment_exports`, and enable only cases that
exist. A moment export entry is:

```json
{"npz":"controls/case-electrons1.npz","metadata":"controls/case-electrons1.metadata.json"}
```

Two-population cases need two such entries at the same actual time and frame.
Use `--case-config`, `--output`, `--provenance-output`, and `--profiles-output`
to keep new controls separate from the archived-source result. Every pair
reports matched-minus-baseline fields and errors against the same PIC target,
with actual time differences. Negative delta-error means smaller error. A zero
baseline error gives a null fractional change. Missing or rejected runs remain
explicitly not computed; no effect is imputed from a template or absent file.
