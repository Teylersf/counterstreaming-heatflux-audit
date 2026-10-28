# Source, version and data provenance

The audited work is **arXiv:2607.07106v1**, *Counter-streaming heat-flux closure
for electron-only collisionless magnetic reconnection*, by Madox C.
McGrae-Menge, Jacob R. Pierce, Maria Almanza, Alexander Velberg, Nathaniel
Barbour, William D. Dorland, Nuno F. Loureiro, Frederico Fiuza and E. Paulo Alves.

- [Versioned record](https://arxiv.org/abs/2607.07106v1)
- [Versioned PDF](https://arxiv.org/pdf/2607.07106v1)
- [Experimental HTML](https://arxiv.org/html/2607.07106v1)
- [Versioned TeX source](https://arxiv.org/src/2607.07106v1)

## Version scope

A fresh ordinary public request to the unversioned arXiv record on **28 October
2026** listed only v1, submitted **8 July 2026 at 07:43:25 UTC**, with no journal
reference or later arXiv version. A bounded exact-title/identifier search with
correction and erratum terms did not identify a dedicated correction. This is
not proof that no correction or differently titled subsequent work exists.
Findings concern the identified v1, not an unexamined later edition.

The supplied PDF has **10 pages** and prints **9 July 2026** on its title page.
The experimental HTML prints **24 August 2026**. These display dates do not
establish different scientific revisions: the exact TeX at `apssamp.tex:95`
uses `\date{\today}`, making its displayed date compilation-dependent. The
arXiv version history and byte-verified PDF identify the audited artifact.
Equation and figure locators below use **PDF numbering**, rather than the
HTML converter's presentation of appendix equations.

No source author has been contacted. No author confirmation, independent
human peer review, or knowledge of an unpublished revision is claimed.

## Exact artifacts

The supplied local file and a newly downloaded versioned PDF are byte-identical.
The PDF finished downloading and passed its hash/page checks before the source
archive download began.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Supplied PDF and fresh arXiv v1 PDF | 7,847,791 | `fc5344e2ba8f4db98baf90d805bb6b7ce8835c32ea7bf54bba4d62f405b955a3` |
| Versioned arXiv source archive | 7,439,982 | `4f9abd5f41ffca0f1879981429165ff1a989276792c812e860f57cb5038c3b2e` |
| Original `apssamp.tex` | 48,800 | `5cf2c6e38a9914d0e7607b303220a2af2e4a70a1ae0d8b64c1882126321eba89` |
| Original `apssamp.bib` | 66,487 | `21d0487f530d186085bf488f0f4d05e62279bfa62ea566f3e7688a0d9a7c04a0` |

The source has 307 original TeX lines and 893 BibTeX lines. The archive was read
without executing its contents; only regular `.tex`/`.bib` files with safe
relative names were extracted to a local temporary directory. The full source
archive and original PDF are not redistributed as part of this audit.

Six [selective excerpt files](source-excerpts/README.md) preserve 17 fragments
(5,544 bytes of source text), including valid mixture algebra, targeted claims
and disclosed limitations. Their manifest identifies exact original TeX line
and character positions. The offline `source-excerpts/verify.py` reads a
downloaded archive, verifies its whole-file hash and original TeX hash, and
reconstructs all excerpt files. It passed against the identified archive.

## Targeted source anchors

| Statement | PDF location | Original `apssamp.tex` lines |
|---|---|---|
| General novelty and single-electron-fluid claims | Abstract and Introduction, pp. 1-2 | 111, 119, 138, 152 |
| Pressure/third-moment definitions | Eqs. (1)-(2), p. 2 | 140-146 |
| Thermal/pressure/heat-flux normalization | p. 3 | 148 |
| Exact one-component mixture decomposition | Eqs. (3)-(4), p. 3 | 171-175 |
| Approximate intrinsic heat-flux hypothesis | pp. 3-4 | 177 |
| Ten-moment implementation, 156 ratio, local isotropization and timescale | p. 4 | 179 |
| Omitted isotropization contribution and divergence-only qualification | Fig. 3 caption, p. 4 | 166 |
| Mid-plane density/transport explanation | p. 5 | 191 |
| Pressure-modification proxy timescale | p. 5 | 193 |
| Best-time scan metric and proposed thermal/drift collapse | Fig. 4 and text, p. 5 | 198, 202 |
| Linear-instability assertion and late-time limitation | p. 5 | 207 |
| PIC normalization, domain, grid, particles and duration | Appendix A, p. 6 | 225 |
| Magnetic equilibrium and perturbation | Eqs. (A1)-(A3), p. 6 | 229-244 |
| Full mixture tensors and explicitly unnormalized index sum | Eqs. (B1)-(B2), p. 6; continuation p. 8 | 258-269 |
| Separate color scales for fluid and PIC tensor maps | Fig. 5 caption, p. 7 | 250 |
| Fluid initialization and positive-density floor | Appendix C, p. 8 | 280-291 |
| Disclosed kinetic free-expansion limitation | Appendix C, p. 8 | 293 |

These anchors are locators, not a declaration that every listed statement is
wrong. In particular, the exact mixture identities, the stated finite
isotropization, separately scaled fluid plots, late-time stream folding and
the free-expansion limitation must be retained when assessing the conclusions.

## Public simulation data and input decks

The paper's data citation resolves to **Madox McGrae-Menge, Zenodo record
21114117**, DOI [10.5281/zenodo.21114117](https://doi.org/10.5281/zenodo.21114117).
The [public API record](https://zenodo.org/api/records/21114117) returned HTTP
200 on 28 October 2026. It reports:

- Publication date: `2026-07-02`.
- Created: `2026-07-02T21:24:15.058586+00:00`.
- Modified: `2026-07-02T21:24:15.451811+00:00`.
- Record DOI: `10.5281/zenodo.21114117`; concept DOI:
  `10.5281/zenodo.21114116`.
- `metadata.license` is exactly `{"id":"cc-by-4.0"}`:
  [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
- `metadata.version` is absent/null; no numbered dataset version is inferred.
- Creator: McGrae-Menge, Madox, ORCID `0000-0002-2779-0570`.

The API lists these six files:

| Public file | Bytes | Deposited MD5 |
|---|---:|---|
| `BgBr0point1-Beta0point1_PIC.zip` | 1,238,114,672 | `89f8256fe66809412f3814dd8663c833` |
| `BgBr0point1-Beta0point1_1-e-Fluid.zip` | 48,626,312 | `381d3ddb5dbbfda1089a3857232af17f` |
| `BgBr0point1-Beta0point1_2-e-Fluid.zip` | 80,339,875 | `024ca4759bb41b53159858f583a48432` |
| `input_1-e-Fluid.lua` | 8,500 | `0d2d8ccad04d0430869010e3833b792d` |
| `input_2-e-Fluid.lua` | 10,979 | `2e39964404ba359b9861f5d8b41f9b98` |
| `input_PIC.2d` | 4,753 | `fe97a792f564b1c656059948a086e600` |

The three standalone decks were downloaded serially, each passing its deposited
MD5 and recorded SHA-256 before the next. Their SHA-256 values are:

- 1-electron-fluid deck: `a716823d81a8abdb119326537b2289e819381683919803a35c50c24765884a7d`.
- 2-electron-fluid deck: `f9cc244a6e52522d03aa1a127a1f79ff35506b0f9b98b1abe8973a3c6ff4bf69`.
- PIC deck: `c19a01a2987630ed14a22d3d21ffaede8082ea193f505e07f8e05595a9d10340`.

The deposit description says it contains moments at times 0 and 300 and raw
particle data at time 300, rather than all diagnostics. It says the parameter
scan can be regenerated by varying the guide field and thermal-speed inputs.
Thus the audit must not claim that no data or input decks were provided.
Any selected archive-member extraction or analysis is separately documented
with its own checksums; availability checks alone are not a rerun of OSIRIS or
Gkeyll. The landing page was inaccessible to the web-reading tool, but the
ordinary public record API and standalone downloads succeeded.

## Input-language and diagnostic semantics

The current official [OSIRIS momentum-distribution documentation](https://osiris-code.github.io/osiris/reference/udist)
defines `ufl` and `spatial_ufl` in proper-velocity units and documents relativistic
momentum addition as the default. Public implementation code was inspected at
commit `a858fe1da3d6dbf3652b16556af87f7dad7881eb`, in
`source/spec/os-spec-udist.f03`; its default and spatial-boost branches are
recorded in the implementation-inspection manifest. This is current public
implementation evidence, not proof of the exact executable used by the authors.

The archived `vfl` and `vivj` definitions used in the analysis come from the
authors' own Zenodo description: `vfl_i=(1/n) integral f v_i d^3v` and
`vivj=integral f v_i v_j d^3v`. The custom diagnostic keys are not identified
with a matching implementation in the inspected current public diagnostic
code. The study should state that access limit rather than infer a private
code revision or silently replace the authors' stated diagnostic definitions.

## Related-work verification

[The prior-art audit](audit/prior-art.md) identifies primary sources and separates
standard multibeam identities and known local-closure approximations from the
paper's specific electron-only-reconnection application. DOI metadata were
checked against Crossref; an inaccessible publisher landing page is recorded
as an access limit, not evidence that a DOI is invalid.
