# Initial-state matching and stability diagnostics for a counter-streaming electron-fluid closure

**Author: Taylor Kalin**

[taylorkalin.com](https://taylorkalin.com) ·
[teylersf@gmail.com](mailto:teylersf@gmail.com) ·
[ORCID 0009-0003-9000-9315](https://orcid.org/0009-0003-9000-9315)

A reproducible diagnostic comment on **arXiv:2607.07106v1**, using the original
authors' input decks, archived initial PIC moments and reloaded initial fluid
output, together with explicit continuum closure tests. Version **1.1.0**
contains the 19-page manuscript and additional archived-data checks.

**Revision in progress:** the `revision/matched-controls` branch additionally
contains complete-archive verification, a clean-source Gkeyll build recipe,
and the four-case aggregate-initialization protocol. The four native cases
started sequentially on 29 October 2026 at 01:06 UTC (28 October Pacific).
Their final comparisons are pending; the released PDF remains v1.1.0.
The [runtime recipe](data/gkeyll-clean-runtime-README.md),
[prespecified protocol](experiments/matched-control-plan.md), and
[complete-archive receipt](data/full-archive-verification.json) document this
work without representing a running process as a completed result.

## Findings and scope

- The archived initial PIC moment current is about **11.5% below the staggered
  magnetic-curl current** near the lower sheet center. The posted fluid
  initializer uses an ordinary velocity where the PIC input specifies proper
  momentum. Five reloaded fluid BP snapshots confirm the actual initial fluid
  state to roundoff. PIC and fluid current profiles differ by **9.87%** in the
  full-domain x-averaged relative L2 norm; central pressures differ by about
  **20% in Pxx** and **38.4% in Pzz**. A conditional public-loader calculation
  accounts for the size of the extra finite-temperature drift reduction.
- A homogeneous two-Maxwellian reference is stable to **longitudinal
  electrostatic** perturbations by the Penrose criterion, while the stated
  finite-isotropization fluid model has a growing mode. This is a separate
  continuum benchmark, not an observed mode in the original reconnection run.
- Zero velocity at a symmetry plane does not block density accumulation:
  continuity depends on flux divergence. A relative heat-flux bound also needs
  an imbalance/cancellation condition in addition to a speed ratio.

The original mixture identities are correct. These findings do not establish
that correcting the initial state would reverse the original nonlinear result.
Matched-state reruns would be needed for that causal conclusion. The current
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
