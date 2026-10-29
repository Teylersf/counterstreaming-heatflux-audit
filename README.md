# Initial-state matching and pressure realizability in counter-streaming electron-fluid comparisons

**Author: Taylor Kalin**

[taylorkalin.com](https://taylorkalin.com) ·
[teylersf@gmail.com](mailto:teylersf@gmail.com) ·
[ORCID 0009-0003-9000-9315](https://orcid.org/0009-0003-9000-9315)

A reproducible diagnostic comment on **arXiv:2607.07106v1**, using the original
authors' input decks, archived initial PIC moments and reloaded initial fluid
output, new clean-source fluid evolutions, and explicit continuum closure
tests. Version **1.2.0** adds complete-archive verification and reports all four
attempted aggregate-initialization controls: three completed native runs and
one failed execution. Native completion, endpoint eligibility and saved
pressure-tensor histories are separate results.

The same-time one-fluid numerical endpoint errors improve under matching,
but both saved histories contain non-realizable pressure tensors. The clean
unmatched two-fluid endpoint fails the population covariance check and
receives no primary performance metrics. The matched two-fluid run fails
with an invariant-check assertion before regular frame 30; its last closed
regular output is frame 22 at time 220.00011000001655, which is not its exact
failure time. No final metric or full pressure-history audit is invented for
that run.
The [runtime recipe](data/gkeyll-clean-runtime-README.md),
[prespecified protocol](experiments/matched-control-plan.md), and
[complete-archive receipt](data/full-archive-verification.json) document this
the inputs, implementation and integrity checks. The original historical
dirty executable remains unidentified.

## Findings and scope

- The archived initial PIC moment current is about **11.5% below the staggered
  magnetic-curl current** near the lower sheet center. The posted fluid
  initializer uses an ordinary velocity where the PIC input specifies proper
  momentum. Five reloaded fluid BP snapshots confirm the actual initial fluid
  state to roundoff. PIC and fluid current profiles differ by **9.87%** in the
  full-domain x-averaged relative L2 norm; central pressures differ by about
  **20% in Pxx** and **38.4% in Pzz**. A conditional public-loader calculation
  is a consistency check for the extra finite-temperature drift reduction;
  it does not identify the historical private diagnostic implementation.
- A homogeneous two-Maxwellian reference is stable to **longitudinal
  electrostatic** perturbations by the Penrose criterion, while the stated
  finite-isotropization fluid model has a growing mode. This is a separate
  continuum benchmark, not an observed mode in the original reconnection run.
- Zero velocity at a symmetry plane does not block density accumulation:
  continuity depends on flux divergence. A relative heat-flux bound also needs
  an imbalance/cancellation condition in addition to a speed ratio.
- Matching aggregate moments changes one-fluid full-grid errors in density,
  Jz, Pxx and Pzz from **3.9763%, 28.3046%, 36.2872%, 34.6557%** to
  **3.4774%, 26.5123%, 28.8547%, 30.7718%**, respectively. These are numerical
  endpoint contrasts, not validated physical trajectories. The unmatched
  one-fluid run has three non-PSD saved snapshots and the matched run has five.
- The identified clean implementation's density/diagonal-pressure predicate
  does not enforce full covariance positivity. Its unmatched two-fluid endpoint
  has 16 indefinite population-1 cells, despite positive diagonals. Both
  original archived endpoints pass the full tensor check. Clean-source failures
  do not establish failures of the unavailable original intermediate history.

The original mixture identities are correct. These findings do not establish
that correcting the initial state would reverse the original nonlinear result.
The new clean-source numerical endpoint contrasts do not establish that
causal conclusion: saved covariance failures, the unidentified original dirty
build and the absence of a resolution study remain material limits. The current
is a physical moment diagnostic rather than the code's native deposited
current; no such current file is identifiable in the complete PIC inventory.
The homogeneous test does not establish a mode in the source's inhomogeneous
sheet or refute its application-specific instability capability claim.

## Read and reproduce

- [Paper PDF](paper/main.pdf) and [LaTeX source](paper/main.tex)
- [AiraXiv preprint 2610.0109](https://airaxiv.com/papers/view/2610.0109/)
- [Source provenance](SOURCE.md) and [selective source evidence](source-excerpts/README.md)
- [Data definitions and retrieval](data/README.md)
- [Archived fluid checks and optional BP reader](data/revision-README.md)
- [Verification results](results/verification.json) and [execution log](results/execution.log)
- [Numerical endpoint comparisons](results/gkeyll-control-comparison.json)
- [All native outcomes and admissibility](results/gkeyll-admissibility.json)
- [Covariance scan definitions](data/gkeyll-admissibility-README.md)
- [Publication status](submissions/publication-status.json)

```sh
python -m pip install -r requirements.txt
python experiments/fetch_data.py
python experiments/data_checks.py
python -X utf8 experiments/verify.py
python -X utf8 experiments/make_figures.py
python -X utf8 experiments/profile_sensitivity.py
python -X utf8 experiments/thermal_loading.py
```

For the original small-data verification, the PIC downloader retrieves approximately **4.48 MB of selected compressed
members**, plus small headers, rather than the full 1.24 GB PIC archive. It
requires HTTP partial responses and verifies pinned member hashes. The later
revision also verified all three complete ZIP archives against their byte
counts and publisher MD5s, recorded full SHA-256s, and bound the original
selected inputs to those verified files. Historical selective-retrieval
receipts are retained separately. No OSIRIS/Gkeyll installation is needed
for the original archived-data checks.
The optional fluid-output corroboration retrieves another **24.77 MB** of
compressed members. Its ADIOS2 reader uses a separate Linux environment;
portable instructions and the resulting profiles are included.

## Authorship, funding and licenses

Taylor Kalin is the canonical author and self-funded this study. AI assistance
and the released manuscript's computational scope are disclosed separately in the paper.
Agent-only venue editions identify their agent author and credit Taylor Kalin
as human operator and canonical author.

Original manuscript text and figures use [CC BY 4.0](LICENSE-MANUSCRIPT).
Original analysis code uses the [MIT License](LICENSE-CODE). The original
authors' input decks, archived data and attributed excerpts retain their
authorship and license. The original paper and full simulation archive are not
redistributed here.
