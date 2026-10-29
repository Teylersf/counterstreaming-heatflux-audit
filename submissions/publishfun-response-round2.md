# Response to Publish.fun round 2

**Author:** Taylor Kalin  
**Revision:** 1.2.0 — diagnostic comment

Dear Editor and Reviewers,

This revision adds actual clean-source fluid evolutions through the requested
comparison time, complete verification of the three source archives, and an
independent ten-moment layout check. It also reports important failures of
the new computations. The result is a numerical one-fluid endpoint contrast
with explicit physical-admissibility limits, rather than a claim that the
source's nonlinear physical conclusion has been overturned.

## 1. Matched initial states and actual native outcomes

The four-case intervention, solver settings and primary endpoint measurements
were pinned before evolution. Both posted initializations and both
aggregate-PIC-matched initializations use the same clean Gkeyll source commit,
9663ea594e80f68eb305378e14512db390440e6b. All 1,998 native/Lua source files,
the original 480 by 640 grid, periodic boundaries, closures, CFL, 4 by 4 MPI
decomposition, tEnd=600 and nFrame=60 are retained. We use only closed regular
frame 30 outputs whose hashes remain unchanged after exit; subsequent stop
outputs are excluded. The original archived dirty identifier is not treated
as a fully recovered executable.

| Case | Native outcome | Regular frame 30 time | Endpoint measurement |
|---|---|---:|---|
| One-fluid unmatched | Completed | 300.0001500000136 | Eligible numerical endpoint |
| One-fluid aggregate-matched | Completed | 300.0001500000136 | Eligible numerical endpoint |
| Two-fluid unmatched | Completed | 300.04383248285376 | Rejected: indefinite population pressure |
| Two-fluid aggregate-matched | Failed, return code 1 | Unavailable | No final measurement |

The matched two-fluid run terminates after an invariant-check assertion at
MomentSpecies.lua:495 and an MPI nonzero-rank exit. Its last closed regular
output is frame 22 at 220.00011000001655. This is not the exact assertion time;
the failing transient cell, population and numerical cause are not identified.
No native stop request or regular frame 30 exists. We do not invent a final
metric, full 31-frame pressure audit or two-fluid initialization-effect pair.

The imported state matches measured aggregate density, ordinary momentum and
uncentered second moments, without smoothing, clamping or fitted drift. For
two fluids, the posted positive smooth weights split the entire aggregate
vector. This preserves aggregate moments but does not match the sharp PIC
tags, full distributions or intrinsic third moments. The intervention also
imports sampled spatial variation, so its effect is not attributed solely
to the current mismatch or proper-momentum convention.

## 2. Numerical improvement and covariance failures are reported together

For the same-time one-fluid pair, complete-grid relative L2 errors against
the same PIC reference are:

| Quantity | Unmatched (%) | Matched (%) | Change (percentage points) |
|---|---:|---:|---:|
| Density | 3.9763 | 3.4774 | -0.4990 |
| Jz | 28.3046 | 26.5123 | -1.7923 |
| Pxx | 36.2872 | 28.8547 | -7.4324 |
| Pzz | 34.6557 | 30.7718 | -3.8840 |

The clean unmatched one-fluid endpoint differs from its archived source
counterpart by 0.2104%, 0.7143%, 0.7158% and 1.2758% in the corresponding global
norms at identical times. The maximum absolute density difference is 0.09399 n0;
small global norms are not uniform pointwise bounds or recovery of the dirty
build.

The strict collector accepts the one-fluid initial/final tensors. An added
saved-history audit, developed after the rejected two-fluid endpoint, finds
three non-PSD saved snapshots in the unmatched one-fluid run and five in the
matched run. Their worst pressure eigenvalues are -0.0017235454 and
-0.0053207379 in normalized pressure units. Thus lower endpoint errors coexist
with more saved covariance failures. This additional diagnostic is not
described as a prespecified primary performance measurement, and the pair is
not represented as validated physical dynamics.

The completed unmatched two-fluid endpoint has 16 indefinite population 1 cells
with minimum eigenvalue -0.0014125968, despite positive density and diagonal
pressures. Population 2 and the aggregate remain positive definite. The
unchanged endpoint guard rejects the case and withholds primary errors.
The paper includes an explicit matrix witness and negative principal minor,
independent long-double centering/minor checks, and complete 31-frame scans
for the three successful native runs. The clean native predicate tests
coordinate pressures without enforcing full tensor positivity. This makes
normal completion compatible with an indefinite tensor; it does not identify
the loss-producing update.

Both original archived fluid endpoints pass the same full covariance test.
Their intermediate trajectories and exact historical executable remain
unidentified. We do not transfer clean-source failures to those unavailable
trajectories. No clipping, masking, relaxed physical guard or altered solver
is used to create an eligible measurement.

For heat flux, the documented first/second moments determine the tagged
population-recentering contribution, not a unique full tensor under a local
divergence closure. The failed/rejected two-fluid pair cannot supply a
validated before/after heat-flux result. The normalization of the posted
third-product diagnostics remains explicitly unverified. One-fluid zero
recentering contribution is a definition, not zero full heat transport.

## 3. Complete archives, layout and conditional loading

All three ZIP archives were downloaded serially and verified against the
publisher's exact byte counts and MD5 values, with full SHA-256 values
recorded separately. Their total is 1,367,080,859 bytes. All 18 original selected
inputs were re-extracted from those verified complete files and their member
lengths, CRC32 and SHA-256 values agree with the earlier selective retrieval.
The historical receipts remain historical; the full verification supplements
them rather than rewriting their scope.

The ten-component conserved order and off-diagonal convention were checked
against official Gkeyll eigensystem documentation and pinned Postgkyl source,
independently of the initializer comparison. Native startup tests also match
the original initialized arrays bit-for-bit. Exact source URLs, code hashes,
runtime/dependency pins and data bindings are public in the repository.

The public-loader calculation is consistently described as a conditional
consistency check. Agreement does not identify the historical private
diagnostic kernel. Matched inputs come directly from the deposited first and
second moments, not from fitting that conditional calculation.

## 4. Figures, provenance and remaining scope

The prior round's three stored images were checked directly: their decoded
RGBA arrays exactly match their canonical counterparts. Different upload
identifiers reuse a figure-2.png basename; this did not establish a figure
substitution. The saved comparison record preserves that evidence. This
revision uses versioned figure URLs, and its final stored figures and
mathematics are checked again before recording publication-format completion.

The record and concept DOIs are findable DataCite records; a Crossref absence
does not invalidate identifiers registered through a different agency. Direct
Zenodo, DOI-agency and DataCite links are supplied.

The exact mixture identities remain correct. The homogeneous stability test
is an auxiliary calibration, not an unstable eigenmode of the source sheet.
No new PIC calculation, resolution-converged physical comparison, measured
reconnection-rate change or independent human expert review is claimed.
The source's original archived two-fluid advantage is not erased by the
clean implementation's failures.

Taylor Kalin remains the canonical author. The study is self-funded, with no
external funding or reported competing interests; AI assistance is disclosed
separately. GitHub and AiraXiv deposits are preprints of this same study.
Other review submissions remain sequenced until this consideration closes.

The final paper, exact scientific code pin and machine-readable outcomes are
available in the [version 1.2.0 release](https://github.com/Teylersf/counterstreaming-heatflux-audit/releases/tag/v1.2.0).
