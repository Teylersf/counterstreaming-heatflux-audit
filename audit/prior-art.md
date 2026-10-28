# Prior art and the scope of a defensible correction

Checked on 28 October 2026. The audited source is the byte-identified
arXiv:2607.07106v1 in [SOURCE.md](../SOURCE.md). Its exact algebraic mixture
identities are standard moment recentering and should not be described as
incorrect or newly invented by this audit. A valid application of those
identities can still reveal useful physics in electron-only reconnection.

## Verified primary references

DOI/title/author/journal/year metadata for the paper entries below were checked
through ordinary Crossref registry requests. Documentation was checked at its
official source. Access descriptions identify what was actually read; metadata
verification is not a substitute for reading a claimed result.

| Reference | Primary access and relevance | Scope limit |
|---|---|---|
| O. Penrose, *Electrostatic Instabilities of a Uniform Non-Maxwellian Plasma*, The Physics of Fluids **3**, 258-265 (1960), DOI [10.1063/1.1706024](https://doi.org/10.1063/1.1706024) | [Publisher-deposited Crossref record and abstract](https://api.crossref.org/works/10.1063/1.1706024) give the local-minimum integral criterion for exponentially growing electrostatic modes. | The full 1960 article was not inspected in the theory/source checks; its DOI redirect was inaccessible to the web-reading tool. The new paper supplies its own equilibrium analysis. This criterion concerns the longitudinal electrostatic problem, not complete nonlinear electromagnetic stability. |
| OSIRIS Collaboration, *Momentum Distribution: udist*, OSIRIS Reference Guide, [official documentation](https://osiris-code.github.io/osiris/reference/udist), accessed 28 October 2026 | The guide defines fluid momenta as proper velocities and documents relativistic addition as the default. | No page-specific publication year or DOI is asserted. Current public documentation does not identify the authors' exact historical executable; custom archived diagnostics are interpreted using the authors' deposit description. |
| G. W. Hammett and F. W. Perkins, *Fluid moment models for Landau damping with application to the ion-temperature-gradient instability*, Physical Review Letters **64**, 3019-3022 (1990), DOI [10.1103/PhysRevLett.64.3019](https://doi.org/10.1103/PhysRevLett.64.3019) | [Publisher abstract](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.64.3019) and [author-hosted full paper](https://w3.pppl.gov/~hammett/gyrofluid/papers/1990/Hammett_90_PRL_Landau_fluid_corrected.pdf). Finite-pole approximations of kinetic linear response are established closure ingredients. | Does not prove a low-order closure reproduces arbitrary non-Maxwellian distributions. |
| L. Wang, A. H. Hakim, A. Bhattacharjee and K. Germaschewski, *Comparison of multi-fluid moment models with particle-in-cell simulations of collisionless magnetic reconnection*, Physics of Plasmas **22**, 012108 (2015), DOI [10.1063/1.4906063](https://doi.org/10.1063/1.4906063) | [Full author manuscript](https://arxiv.org/html/1409.0262v3), Section III, Eqs. (20)-(24). The local pressure-isotropization surrogate is explicitly derived as a sequence of approximations to a nonlocal collisionless closure. | Already cited as source Ref. 31. Its approximate nature is not a newly discovered concealed omission. |
| M. V. Goldman, D. L. Newman, J. P. Eastwood and G. Lapenta, *Multibeam Energy Moments of Multibeam Particle Velocity Distributions*, Journal of Geophysical Research: Space Physics **125**, e2020JA028340 (2020), DOI [10.1029/2020JA028340](https://doi.org/10.1029/2020JA028340) | [Publisher full text](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020JA028340), especially Section 4.4 and Eqs. (16)-(17); [author preprint](https://arxiv.org/abs/2005.09113). Recentring multibeam moments and separating bulk/thermal contributions, including nonzero total heat flux from individually symmetric beams, predates the audited work. | The heat-flux vector treatment is not itself the identical ten-component rank-three closure or its electron-only-reconnection validation. |
| E. R. Ingelsten, M. C. McGrae-Menge, E. P. Alves and I. Pusztai, *Data-driven discovery of a heat flux closure for electrostatic plasma phenomena*, Journal of Plasma Physics **91**, E64 (2025), DOI [10.1017/S0022377825000285](https://doi.org/10.1017/S0022377825000285) | [Publisher full text](https://www.cambridge.org/core/journals/journal-of-plasma-physics/article/datadriven-discovery-of-a-heat-flux-closure-for-electrostatic-plasma-phenomena/F13037CC86712A9B320EB962DDA069A3), including nonlinear two-stream-instability results. Published online 28 April 2025. A single-species data-driven heat-flux description is studied beyond linear Maxwellian perturbations. | One-dimensional electrostatic data and fitted closures do not establish an already validated model for the source's magnetic geometry. |
| E. R. Ingelsten, M. C. McGrae-Menge, E. P. Alves and I. Pusztai, *Data-driven multi-species heat flux closures for two-stream-unstable plasmas with nonlinear sparse regression*, Physics of Plasmas **33**, 042106 (2026), DOI [10.1063/5.0311956](https://doi.org/10.1063/5.0311956) | [Full author manuscript](https://arxiv.org/html/2511.10147v1), Section II.1 and Appendix A; [institutional journal record](https://research.chalmers.se/en/publication/551781). Preprint submitted 13 November 2025; journal issue April 2026. Separate counter-streaming electron populations and their nonzero intrinsic heat flux are modeled. | Not the same zero-intrinsic-heat-flux assumption or the same reconnection problem. The DOI resolver was inaccessible to the web-reading tool; Crossref, arXiv and the institution supplied consistent metadata. |
| J. Ng, A. Hakim, A. Bhattacharjee, A. Stanier and W. Daughton, *Simulations of anti-parallel reconnection using a nonlocal heat flux closure*, Physics of Plasmas **24**, 082112 (2017), DOI [10.1063/1.4993195](https://doi.org/10.1063/1.4993195) | Original source Ref. 32; Crossref metadata and the source's cited description checked. A nonlocal moment closure is relevant background. | This audit's source-verification role did not independently inspect this paper's complete numerical results; do not cite it for a new quantitative assertion without doing so. |
| L. Wang, A. H. Hakim, J. Ng, C. Dong and K. Germaschewski, *Exact and locally implicit source term solvers for multifluid-Maxwell systems*, Journal of Computational Physics **415**, 109510 (2020), DOI [10.1016/j.jcp.2020.109510](https://doi.org/10.1016/j.jcp.2020.109510) | Original source Ref. 43; Crossref metadata and original bibliography checked. This is the solver-method reference used by the audited work. | A source-term algorithm reference is not evidence that an arbitrary kinetic closure is accurate or that a reported state-count ratio is a measured speedup. |
| J. Ng, A. Hakim, J. Juno and A. Bhattacharjee, *Drift Instabilities in Thin Current Sheets Using a Two-Fluid Model With Pressure Tensor Effects*, Journal of Geophysical Research: Space Physics **124**, 3331-3346 (2019), DOI [10.1029/2018JA026313](https://doi.org/10.1029/2018JA026313) | [Publisher full text](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018JA026313), Sections 2 and 5, Appendix A; [author preprint](https://arxiv.org/abs/1903.09618). Linear eigenmodes and kinetic response depend on closure and relaxation parameters. | Its electron-ion current-sheet modes are not a direct numerical benchmark of the source's electron-only two-electron-fluid run. |
| T. Pianpanit et al., *Flow Crossover and Parallel Outflow during Collisionless Magnetic Reconnection*, Physical Review Letters **136**, 085201 (2026), DOI [10.1103/whtm-nvkp](https://doi.org/10.1103/whtm-nvkp) | Publisher/Crossref metadata and original source citation checked. The source explicitly credits it for above/below flow crossover. | No omission claim is warranted; a complete independent audit of this reference was not performed here. |
| P. Suetrong et al., *Electron crossover and diffusion region width in symmetric, collisionless magnetic reconnection*, Physics of Plasmas **33**, 052102 (2026), DOI [10.1063/5.0305141](https://doi.org/10.1063/5.0305141) | Crossref metadata and original source citation checked. The source explicitly credits it for population-resolved pressure supporting the reconnection field. | It does not by itself establish the source's new heat-flux application was anticipated. |

## What follows from this literature

The exact mixture pressure and third-moment expansions are applications of
standard recentering. Goldman et al. provide particularly relevant prior
context. A counter-streaming contribution can be expressed using the labeled
subpopulation moments even when it cannot be inferred uniquely from the
unlabeled ten moments. Those are different information sets.

The broad introductory/concluding wording that no existing fluid closure can
capture non-Maxwellian counter-streaming must be restricted to the particular
models, regimes and observables actually compared. The two Ingelsten studies
predate July 2026 and are relevant counterexamples to an unrestricted claim
that all fluid heat-flux descriptions fail for two-stream systems. Neither
study demonstrates the same forward electron-only magnetic-reconnection
benchmark. Their omission is a scope/prior-art issue, not evidence of plagiarism
or proof that the source's specific application lacks novelty. The supplied
TeX bibliography contains no Goldman, Ingelsten, Newman or Pusztai entry.

Wang et al. explicitly call the isotropization form a crude local approximation
and discuss better nonlocal alternatives. Thus a homogeneous-anisotropy or
periodic-divergence compatibility test can clarify its meaning and limitations,
but the audit should not present the general fact that it is approximate as a
new discovery. The source also states a finite isotropization coefficient and
acknowledges that its displayed fluid heat-flux excludes this contribution.

Ng et al. show why merely adding separate populations does not certify an
arbitrary kinetic instability's threshold or growth rate. Any new instability
counterexample in this audit must derive its own dispersion relations and state
the regime, rather than importing numbers from a different current sheet.

## Claims this audit should preserve

- The original mixture identities, including the explicitly defined
  unnormalized index symmetrization, are valid standard algebra.
- The paper openly reports finite isotropization, amplitude differences,
  independent fluid color scales in Fig. 5, late-time stream folding and
  free-expansion limitations. These are not hidden assumptions uncovered here.
- The Zenodo record and input decks are available; an audit must not describe
  the work as having supplied no data or no input files.
- No full new PIC or Gkeyll run was performed in this provenance/prior-art
  check. Availability, exact-input checks and analysis of deposited snapshots
  must be distinguished from independent simulation reproduction.
- There is no basis here for a universal refutation of multi-fluid modeling,
  an allegation about the authors' intentions, or an exhaustive priority claim.

The strongest defensible contribution is a source-specific mathematical and
reproducibility audit, with explicit tests of the claims that go beyond the
data and approximations actually established.
