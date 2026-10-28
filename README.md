# Initial-state matching and stability diagnostics for a counter-streaming electron-fluid closure

**Author: Taylor Kalin**

[taylorkalin.com](https://taylorkalin.com) ·
[teylersf@gmail.com](mailto:teylersf@gmail.com) ·
[ORCID 0009-0003-9000-9315](https://orcid.org/0009-0003-9000-9315)

A reproducible audit of **arXiv:2607.07106v1**, using the original authors'
published input decks and archived initial moments, together with explicit
continuum closure tests.

## Findings and scope

- The archived initial PIC moment current is about **11.5% below the staggered
  magnetic-curl current** near the lower sheet center. The posted fluid
  initializer uses an ordinary velocity where the PIC input specifies proper
  momentum. The archived velocity-moment pressures also differ from the fluid
  prescription: about **20% in Pxx** and **38.4% in Pzz** at those cells.
- A homogeneous two-Maxwellian reference is stable to **longitudinal
  electrostatic** perturbations by the Penrose criterion, while the stated
  finite-isotropization fluid model has a growing mode. This is a separate
  continuum benchmark, not an observed mode in the original reconnection run.
- Zero velocity at a symmetry plane does not block density accumulation:
  continuity depends on flux divergence. A relative heat-flux bound also needs
  an imbalance/cancellation condition in addition to a speed ratio.

The original mixture identities are correct. These findings do not establish
that correcting the initial state would reverse the original nonlinear result.
Matched-state reruns would be needed for that causal conclusion. The fluid
comparison here uses its posted initializer, not reloaded `.bp` output; the
current is a physical moment diagnostic rather than the code's native
charge-conserving deposited current.

## Read and reproduce

- [Paper PDF](paper/main.pdf) and [LaTeX source](paper/main.tex)
- [AiraXiv preprint 2610.0109 (v1)](https://airaxiv.com/papers/view/2610.0109/)
- [Source provenance](SOURCE.md) and [selective source evidence](source-excerpts/README.md)
- [Data definitions and retrieval](data/README.md)
- [Verification results](results/verification.json) and [execution log](results/execution.log)
- [Publication status](submissions/publication-status.json)

```sh
python -m pip install -r requirements.txt
python experiments/fetch_data.py
python experiments/data_checks.py
python -X utf8 experiments/verify.py
python -X utf8 experiments/make_figures.py
```

The downloader retrieves approximately **4.48 MB of selected compressed
members**, plus small headers, rather than the full 1.24 GB PIC archive. It
requires HTTP partial responses and verifies pinned member hashes. The complete
archive's publisher-declared checksum is not represented as independently
verified. No OSIRIS/Gkeyll installation or new reconnection run is required.

## Authorship, funding and licenses

Taylor Kalin is the canonical author and self-funded this study. AI assistance
and the absence of a new simulation run are disclosed separately in the paper.
Agent-only venue editions identify their agent author and credit Taylor Kalin
as human operator and canonical author.

Original manuscript text and figures use [CC BY 4.0](LICENSE-MANUSCRIPT).
Original analysis code uses the [MIT License](LICENSE-CODE). The original
authors' input decks, archived data and attributed excerpts retain their
authorship and license. The original paper and full simulation archive are not
redistributed here.
