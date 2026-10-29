# Native outcomes and covariance admissibility

`results/gkeyll-admissibility.json` separates three findings for every native
case: whether the process produced a valid regular-frame30 receipt, whether
the strict collector accepted its initial/final state, and whether covariance
PSD held in the available regular saved moment snapshots0--30. Pending cases
have null endpoint eligibility. A rejected completed case has no primary
comparison metrics; it is not described as an unattempted run or a zero error.
A terminal failed execution is also distinct: it has no eligible regular30
endpoint and its full-history diagnostic is explicitly
`not_applicable_native_execution_failed`. This is an unavailable audit, not a
PSD certificate, zero failures or a claim that31 snapshots were scanned.

Accepted comparisons and pairs are **NUMERICAL endpoint comparisons only**.
An admissible final covariance does not certify earlier states. A complete
saved-snapshot scan also does not check every timestep or locate the split
operator that first lost admissibility. The historical source's unidentified
dirty executable and intermediate trajectory are not inferred from a clean
rerun. Frame31 and later forced-final outputs are excluded from these scans.

## Compact saved-state scanner

The portable optional-ADIOS2 CLI is
`experiments/scan_gkeyll_saved_states.py`. It requires a completed native
receipt and the complete reviewed eight-key runtime context. Every selected BP
is bound to its native receipt's byte size/SHA256 before and after reading, and
native frame/time ordering and common population times are checked. Outputs
contain counts, extrema, coordinates and provenance only; no raw fields,
repairs, clipping or performance metrics are written. PSD (`eigenvalue >= 0`)
and strict PD (`eigenvalue > 0`) are distinct.

```sh
python experiments/scan_gkeyll_saved_states.py --self-test
python experiments/scan_gkeyll_saved_states.py \
  --run-directory "$COMPLETED_NATIVE_CASE" \
  --expected-context "$REVIEWED_CONTEXT_JSON" --output "$FRESH_SCAN_JSON"
```

Use the separate Linux/WSL environment in `requirements-bp.txt`. Per-process
`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1` and `nice` can limit interference
with unrelated work. The scanner refuses existing outputs/temporary files,
leaf symlinks, outputs in the native run directory, and the context file as an
output target. Preserve prior partial/failed scans and choose a fresh path.

## Portable outcome record

`experiments/build_gkeyll_admissibility.py` assembles the record from native
receipts, the collector inventory, completed compact scans, and independent
tensor/predicate evidence. It exports selected portable input JSON into the
requested project-local evidence directory, retains hashes of the full source
audit records, and binds every selected input by project-relative path/SHA256.
Only one small endpoint witness and an invalid-cell index/eigenvalue list
retain physical arrays. Full native output inventories are copied from the
native receipt; the scanner independently rehashes moment snapshots0--30.

The CLI's `--help` lists the evidence inputs. `--evidence-directory` must be
under project `data/` or `results/`, and different existing evidence is never
overwritten. A fresh `--output` is required. Compact completed scans are copied
to `--public-scan-directory` (default `results/gkeyll-saved-state-scans/`),
again refusing different existing files. Final selected inputs live under
`results/gkeyll-admissibility-inputs/`; interim subfolders are not a final
completion claim.

Consumers must distinguish these fields:

* `native_outcomes[].native_outcome_terminal`: a final native outcome was
  observed, including a terminal execution failure.
* `endpoint_metrics_eligible`: true/false/null for accepted endpoint,
  rejected/unavailable endpoint, or pending collection respectively.
* `collector_decision_resolved` and `saved_snapshot_diagnostic_resolved`:
  whether those assessments have terminal results; a diagnostic failure is
  not a successful scan or a PSD certificate.
* `saved_snapshot_diagnostic.actual_saved_times` and `summary`: actual saved
  times and all population and aggregate PSD/PD counts/minima. Aggregate PSD never overrides an
  individual population's failure.
* `all_four_native_outcomes_observed` versus
  `all_four_native_outcomes_completed`: every terminal outcome was seen versus
  every run successfully reached the guarded regular30 endpoint.
* `all_four_saved_snapshot_scans_complete`: all31 requested snapshots were
  checked for every case, independent of whether their covariance passed.

These literal all-four success/full-scan flags remain false in the released
experiment: three native cases complete and one fails before regular30.
Numerical subset readiness instead requires all four terminal outcomes and
resolved collector/history decisions, a full scan of each successfully
completed native run, and at least one genuine eligible same-runtime endpoint
pair. A terminal failure cannot enable a metric or substitute for a full scan.
The failed matched two-fluid run's last closed regular output is22 at
220.00011000001655; the assertion occurs afterward at an unrecorded exact
time. Its transient state, species and numerical cause are not established.
The saved-history audit was added after the first rejected endpoint; it is
not described as a prespecified primary performance measurement.

Each scan preserves the actual scanner and IO-helper hashes used to produce
it. The later terminal-failure classification branch changes the collector
and analyzer file hashes without changing the pressure or error formulas.
The scan IO versions are available at public commit
`b2e763e46eb24b87db03a4315d16dd0f74549960`; the release code pin identifies
the final classification helpers separately. Fresh baseline rescans reproduce
all 31 scientific frame records and their summaries exactly. Historical stamps
are retained rather than rewritten to the later helper version.

`endpoint_eligible_pairs` includes actual endpoint times, runtime context and
raw/receipt/scan anchors, with no physical-trajectory claim. Consumers should
independently validate those bindings and require the explicitly selected
numerical-subset mode; the original full valid-case gate remains stricter.

## Clean-build predicate scope

The source/installed hashes and versioned URLs in the record identify the
tested clean build. Its
[TenMoment predicate](https://github.com/liangwang0734/gkyl/blob/9663ea594e80f68eb305378e14512db390440e6b/Eq/TenMoment.lua#L128-L136)
checks density and diagonal pressure conditions. Passing that predicate for a
finite witness does not establish positive-semidefinite covariance: offdiagonal
entries can produce a negative principal minor and negative variance along a
rotated direction. The record preserves an explicit tensor witness and
independently verified archived endpoint comparison. It neither identifies
the loss-producing timestep/operator nor attributes an indefinite archived
state to the original authors.
