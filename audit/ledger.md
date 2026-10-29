# Finding ledger

Author: Taylor Kalin. Audited edition: arXiv:2607.07106v1.

| Finding | Evidence | Conclusion and limit |
|---|---|---|
| Physical initial moments are not matched by the posted fluid prescription | Original Appendices A/C; Zenodo input decks; 13 pinned initial HDF5 members, five reloaded initial BP states and the authors' diagnostic definitions | Near the lower center, initial PIC moment current is about 11.5% below the staggered magnetic curl; Pxx and Pzz differ from the fluid prescription by about 20% and 38.4%. Native deposited PIC current is not identifiable in the complete posted inventory. The conditional public-loader check does not identify the private historical implementation. |
| Matching aggregate PIC moments lowers four one-fluid numerical endpoint errors | Clean-source unmatched and aggregate-matched evolutions at identical regular-frame-30 times; strict initial/final conformance and full-grid comparisons | Density/Jz/Pxx/Pzz errors change from 3.9763/28.3046/36.2872/34.6557 percent to 3.4774/26.5123/28.8547/30.7718 percent. This imports all aggregate moments and sampled spatial variation; it is not a current-only intervention or physical-trajectory validation. |
| Admissible endpoints can conceal non-realizable saved intermediate covariances | Complete regular-frame0--30 scans for the two completed one-fluid cases | The baseline has three non-PSD saved frames and matching has five, with minima -0.0017235454 and -0.0053207379. Lower endpoint errors coexist with more observed covariance failures. Saved scans do not identify the first invalid timestep or its cause. |
| The clean two-fluid baseline completes natively but its final population1 covariance is inadmissible | Strict collector rejection, full-tensor eigenvalues, independent long-double centering/principal-minor witness, and exact clean-source predicate | Sixteen endpoint cells are indefinite despite positive density and diagonal pressures. Primary performance metrics are withheld. The source's original archived endpoint is positive definite; the clean reconstruction does not identify its dirty executable or intermediate history. |
| The matched two-fluid clean run fails before the comparison endpoint | Native failed receipt with returncode1 and no native stop/regular30; repeated MomentSpecies.lua:495 assertion messages and MPI nonzero exit | The last closed regular output is frame22 at220.00011000001655. It is not the exact failure time. The failing transient state, cell, population and cause are not established. No final error, full31-snapshot pressure audit or same-runtime two-fluid initialization contrast is claimed. |
| Finite isotropization can produce a growing longitudinal mode absent from the collisionless reference | Explicit nine-variable model, exact negative Penrose bound, independent dielectric and Gauss checks | A homogeneous model benchmark at the reference relaxation-rate scale. It does not show that this mode appears in the original current sheet or establish global electromagnetic stability. |
| Zero mid-plane normal velocity does not prohibit density accumulation | Continuity identity and exact positive periodic solution | Corrects the geometric explanation on source p. 5; does not dispute the reported single-fluid density deficit. |
| A speed ratio alone does not give a universal relative-error guarantee | Exact mixture identity, conditioned bound and positive near-Maxwellian cancellation example | Conditions an extension of the empirical scan; the source's observed parameter collapse is not disproved. |
| Finite relaxation has a finite-duration effect | Homogeneous pressure/entropy calculation | A convergence diagnostic. The source openly retains finite isotropization, and no measured PIC entropy or external heat input is claimed. |

The original scalar and tensor mixture identities are correct. The genuine
information limitation of a memoryless closure using only total density,
velocity and pressure is preserved. Prior multibeam and electrostatic-closure
work limits broad novelty/impossibility language but does not establish prior
use of this particular electron-only reconnection application.

The source's physical-unit pressure scale and the printed/posted Gaussian seed
center also warrant documentation care. They are supporting recipe issues,
not evidence that the plotted dynamics are invalid. The y-coordinate shift is
consistent and is not an error.

This ledger describes verified statements and their scope. It is not an
exhaustive error inventory or a human peer-review certificate. New clean-source
fluid evolutions are distinguished from the original archived simulations;
no new PIC calculation or experimental measurement is claimed.
