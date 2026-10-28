# Finding ledger

Author: Taylor Kalin. Audited edition: arXiv:2607.07106v1.

| Finding | Evidence | Conclusion and limit |
|---|---|---|
| Physical initial moments are not matched by the posted fluid prescription | Original Appendices A/C; Zenodo input decks; 13 pinned initial HDF5 members and the authors' diagnostic definitions | Near the lower center, initial PIC moment current is about 11.5% below the staggered magnetic curl; Pxx and Pzz differ from the fluid prescription by about 20% and 38.4%. Native deposited PIC current and fluid `.bp` fields were not reloaded. Later causal effects need reruns. |
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
exhaustive error inventory, a human peer-review certificate, or a new
reconnection simulation.
