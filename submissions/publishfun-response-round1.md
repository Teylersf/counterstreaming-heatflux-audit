# Response to Publish.fun round 1

**Author:** Taylor Kalin  
**Revision:** 1.1.0 — diagnostic comment  

Dear Editor and Reviewers,

Thank you for the detailed evaluation. We agree that the initial submission
did not establish the dynamical significance of either the initial-state
differences or the separate homogeneous stability example. We present the
revised work as a **diagnostic comment**. Its primary purpose is to document
initial-state controls using the public archive; the homogeneous dispersion
calculation is an auxiliary test of the stated continuum closure. We do not
claim that either diagnostic overturns the source's nonlinear conclusions.

The new analysis extends the current comparison across both sheets, tests
specific diagnostic choices, audits the complete posted PIC member inventory,
and provides a conditional finite-temperature loading calculation. The
archived fluid snapshots have also been retrieved and decoded for direct
corroboration. We distinguish those completed data operations from requests
that cannot be fulfilled with the deposited fields or have not been performed.
The exact mixture identities and the physical usefulness of population
information remain intact.

## Responses to the editor's key concerns

### 1. Compare the PIC moments with archived Gkeyll t=0 output

We agree that an initializer prescription alone does not establish the state
actually written by the fluid calculation. Five initial BP snapshots have
been retrieved from the one- and two-electron-fluid archives: one field and
one electron snapshot for the one-fluid case, and one field plus two electron
snapshots for the two-fluid case. Each selected member passed its ZIP CRC32
and recorded SHA-256 checks. The decoded time/frame is zero and the grid
matches the PIC domain and resolution. The embedded Lua inputs are
byte-identical to the posted input decks.

The decoded one-fluid state matches all ten posted initializer components
over all `480 x 640` cells to a maximum absolute difference below `4.38e-16`.
The sum of the two-fluid states differs from the one-fluid state by at most
`1.12e-16`. Both archived field arrays are identical to each other and their
first six components agree with the posted field initializer within `1.12e-15`.
The component order follows the byte-identical embedded input and is checked
against every initialized component; the metadata specifies zero ghost cells,
polynomial order zero, domain bounds and cell counts. Comparisons use matching
cell centers and center local pressures before x averaging.

The direct archived-fluid/PIC results across all 640 x-averaged profile rows are:

| Diagnostic | Relative L2 PIC–archived-fluid difference |
|---|---:|
| Physical moment current Jz | 9.867534% |
| Local centered pressure Pxx | 8.316864% |
| Local centered pressure Pzz | 9.543957% |

The one-fluid and summed two-fluid references give the same values to displayed
precision. At the two lower sheet-adjacent rows the reloaded fluid current is
`-0.4987525573`, giving PIC current deficits 11.58196% and 11.60412% relative
to that archived current. The corresponding PIC/fluid pressure ratios are
0.795900 and 0.798040 in Pxx, and 0.615727 and 0.615447 in Pzz. These directly
confirm the earlier prescription-based pressure comparison. The 11.5%
comparison against the staggered magnetic curl is a distinct reference and
is retained under its own definition. Results, metadata and file hashes are
in `results/revision-data.json` and
`data/derived/revision-fluid-profiles.csv`, and the manuscript subsection
“Corroboration against the saved fluid state.”

The BP metadata also records the fluid build date and changeset `9663ea594e80+`.
This is useful provenance, but the plus suffix does not identify a clean exact
source tree or certify an executable. We do not use it to remove uncertainty
about historical implementation details.

### 2. Native deposited current, full profiles, staggering and averaging

The complete PIC ZIP central directory has now been inventoried: 223 entries,
including 94 scientific nondirectory entries. No native deposited-current
dump is identifiable among those member names. The posted `diag_current`
block is empty. The inventory and its scope are recorded in
`data/provenance-revision.json`; the archived `vfl` moments are not relabeled
as native charge-conserving deposited current. Consequently, a direct native
current comparison cannot be supplied from an identifiable current dump in
this deposit. We do not infer the original executable's exact electric-field
update from the moment current.

The comparison is no longer confined to the two lower central cells. Across
all 640 rows of the **x-averaged current profile**, the relative L2 difference
between the PIC moment current and the correctly aligned staggered magnetic
curl is 0.09826455. The corresponding values in the 40-row neighborhoods
`14 <= Y/d_e <= 18` and `46 <= Y/d_e <= 50` are 0.09828687 and 0.09840814.
Both sheets show the same central deficit with reversed current sign.

The recorded offsets determine the primary Yee curl. As a separate
representation-sensitivity calculation, we first collocate the magnetic
components by averaging and then use centered differences. This smoothed
curl differs from the primary x-averaged curl by relative L2 0.00375462;
the four sheet-adjacent current deficits remain approximately 11.05–11.10%,
compared with 11.49–11.54% for the primary staggered diagnostic. The smoothed
derivative is not treated as an alternative interpretation of the known
offsets. The initializer-prescription current differs from the Yee profile
by relative L2 0.00062971.

We also report spatial scatter and eight contiguous x-block means. For
example, at `Y=15.95 d_e`, the current's spatial standard deviation is
0.00199058 and the block means range from -0.44171035 to -0.44043512,
compared with the staggered-curl value -0.49833998. These are descriptive
spatial checks, not independent-sample confidence intervals. Reversing the
order of pressure centering and x averaging adds the resolved bulk-flow
variance, approximately `4e-6` in Pzz at the central rows, rather than
removing the observed pressure difference. The full profiles, definitions
and machine-readable results are in `results/profile-sensitivity.json` and
`data/derived/profile-sensitivity.csv`, and the manuscript subsection
“Archived initial current and staggered magnetic curl.”

The selected PIC files have `TIME=0` and `ITER=0`; no later dump was substituted.
Their recorded offsets and the complete posted diagnostic configuration are
checked explicitly. The posted reports do not specify a time-averaged
diagnostic. This does not identify undocumented behavior of the authors'
custom diagnostic or an unrecorded internal substep of the historical build.

### 3. Full-deck override audit and finite-temperature speed deficit

The entire 155-line reference PIC deck has been checked, not only an excerpt.
Its SHA-256 is
`c19a01a2987630ed14a22d3d21ffaede8082ea193f505e07f8e05595a9d10340`.
Both `udist` blocks enable `use_spatial_ufl` and set all three thermal momentum
widths to 0.111803. No active `use_classical_uadd` override, thermal-distribution
override or include directive appears. The official parameter and units
documentation explicitly defines the input as proper momentum/proper velocity;
an informal example comment using the phrase “fluid velocity” does not change
that definition. We retain the distinction between a public parameter
definition and identification of the exact historical executable.

The cold conversion is not a finite-temperature mean. To make the additional
deficit quantitative, we inspect the public OSIRIS loader at commit
`a858fe1da3d6dbf3652b16556af87f7dad7881eb` and calculate its conditional
prediction. This branch draws independent isotropic Gaussian thermal
momenta, boosts each sample by the prescribed proper-momentum drift, and
retains the particle weights. With rest momentum `u`, `gamma_0=sqrt(1+|u|^2)`,
drift `U` and `G=sqrt(1+|U|^2)`, the tested transformation is

`p=u+U*(gamma_0+(u dot U)/(G+1))`,
`gamma_lab=G*gamma_0+u dot U`, and `v=p/gamma_lab`.

For the unperturbed center `U=(0,0,0.5)`, the cold speed is 0.44721360c,
whereas the finite-temperature unweighted-sample prediction is 0.44297014c.
At row 159, retaining the complete posted drift expressions gives
0.44197416c before particle-shape deposition. A separate no-fit sensitivity
calculation using the posted quadratic interpolation and 25 regular subcell
sites per axis gives 0.44098868c, compared with the archived 0.44098722c.
At row 160 the same conditional prediction is 0.44098868c, compared with
0.44087669c. The calculation also reports predicted velocity covariances
and the finite-particle mean-square correction, rather than using the cold
formula as a pressure-matching condition.

The qualifications are essential. An invariant scalar distribution with the
appropriate equal-laboratory-time Jacobian weighting is a different measure
and has the cold mean exactly; it must not be conflated with this unweighted
sample-boost loader. The quadratic sensitivity follows the posted interpolation
order and a public generic deposition shape; it does not verify the authors'
custom `vfl` implementation. No parameter was calibrated to the archived
values. Quadrature-order refinement and an independent coordinate quadrature
give numerical convergence controls, not a formally certified integration
bound. The finite-sample covariance adjustment assumes deterministic deposition
weights and independent thermal draws; it does not certify the original random
sequence. The active PIC density profiles are complementary sharp indicators:
each regular particle site has one unit-density species, with charge magnitude
`1/625`, rather than two overlapping smooth fluid populations. This is the
particle weighting used in the conditional adjustment. No simulation confidence
interval is claimed.
Thus the added calculation explains how a below-cold mean can arise under the
documented public loading branch and gives a close conditional consistency
check, not an exact reconstruction of the private build. Details and source
hashes are in `results/thermal-loading.json` and the manuscript subsection
“A conditional finite-temperature loading calculation.”

### 4. DataCite registration, version/concept DOI and archive integrity

Reference [2]'s version DOI,
[10.5281/zenodo.21114117](https://doi.org/10.5281/zenodo.21114117), is genuine.
The [DOI registration-agency lookup](https://doi.org/ra/10.5281/zenodo.21114117)
identifies DataCite, and the
[authoritative DataCite record](https://api.datacite.org/dois/10.5281/zenodo.21114117)
returns the exact identifier, dataset title and Zenodo publisher with state
`findable`. The Crossref works lookup returns 404 because this DOI is registered
with DataCite; that registry-specific miss does not invalidate the reference.
The direct repository link is
[Zenodo record 21114117](https://zenodo.org/records/21114117).

The concept DOI is
[10.5281/zenodo.21114116](https://doi.org/10.5281/zenodo.21114116).
It identifies the version family, whereas 21114117 identifies the inspected
version. The revision identifies both roles explicitly rather than silently
replacing a valid version DOI with the concept DOI.

We have **not** verified the complete simulation ZIP checksums. The integrity
evidence consists of complete central-directory inventories and verified
CRC32/SHA-256 for the selected retrieved members. Published whole-archive MD5
values remain declared, not verified. The complete-directory inspection must
not be mistaken for full-payload verification. This part of the request is
not reported as completed. The manuscript records these limits in
“Reproducible calculations and evidence limits.”

### 5. Sheet geometry, periodic wavenumbers, magnetization and relativity

We agree that the homogeneous example does not establish an instability of
the source's sheet. We take the editor's stated alternative of demoting the
claim: the stability calculation is retained as an auxiliary nonrelativistic
longitudinal continuum diagnostic. It shows that population resolution alone
does not guarantee collisionless kinetic spectral fidelity. It does not
disprove the source's application-specific statement that a two-population
model can capture some streaming instability growth.

The existing mode-14 check uses **kx**, `kx=2*pi*14/(48 d_e)`, in the homogeneous
system. It gives growth `0.00951299405 omega_pe` and wavelength `3.42857 d_e`.
It establishes compatibility with the periodic x length, not a ky eigenmode
or a y-dependent sheet eigenanalysis. The source's initial populations share
the same velocity, unlike this test's `+/-U` equilibrium. A local rotation or
choice of periodic mode does not supply the missing sheet profiles and
couplings.

For a uniform field parallel to the beams and wavevector, the kinetic
gyrophase-independent longitudinal subspace and its fluid counterpart with
equal transverse pressures are invariant; magnetic rotation vanishes there.
This explains the limited parallel-field statement. It is not robustness
to the source's spatially rotating field or arbitrary guide-field geometry,
and no relativistic sheet correction has been computed. The Penrose statement
remains restricted to longitudinal electrostatic perturbations, not all
electromagnetic modes. No sheet-mode survival or visible contamination of
the reconnection figures is asserted.

### 6. Matched reruns, dynamical significance and continuity priority

No matched-initial-state PIC/Gkeyll reconnection rerun or current-sheet
eigenanalysis is supplied. A matched-state dynamical comparison remains
necessary to quantify the initial mismatch's effect on the reported nonlinear
comparison; a sheet eigenanalysis would address the separate mode-survival
question. The diagnostic-comment scope makes this
limitation central: the initial discrepancy can identify a control issue,
but it does not determine the sign or size of its effect on the later
nonlinear comparison. The original qualitative benefit of retaining two
populations may survive correction of that control. We recognize that a
narrower claim is not a substitute for the requested dynamical experiment
or a guarantee that the journal's significance threshold has been met.

We also agree that the continuity observation is standard. The section is now
explicitly titled “A secondary continuity clarification,” and identifies its
content as standard continuum kinematics rather than a new plasma mechanism.
The exact periodic example remains as an illustration, not a primary novelty
claim; it has not been moved to a supplement.
Zero normal velocity at a plane does not fix the divergence of mass flux,
but this elementary fact does not show that the source authors misunderstand
continuity or refute their plotted one-fluid density deficit. The conditioned
error bound similarly qualifies a relative-error scaling argument without
claiming to overturn the empirical parameter scan.

## Additional replies to individual reviewers

**Reviewer 1.** The identical-snapshot and override questions are addressed
above in Responses 2 and 3. The gradient/pressure-deviator question is not
answered by a claimed sheet stabilization estimate; no such estimate has
been performed. Response 5 states the resulting scope reduction. We do not
claim original-author confirmation, private-build access, external numerical
corroboration or human peer review. The execution records support transparent
reproduction in the author environment; they are not third-party certification.

**Reviewer 2.** The missing native-current comparison, below-cold mean and
geometry questions are addressed in Responses 2, 3 and 5. We correct the DOI
and parameter-interpretation disputes using the registration agency and
explicit parameter definitions rather than an external aggregator or an
informal input-file comment. Numerical findings newly derived from archived
data need not already appear in an external publication, but their formulas,
inputs, conventions and limitations must be reproducible. The new full-profile
and archived-fluid checks are intended to make that assessment more direct.
The source's mid-plane transport explanation is quoted from the supplied
versioned paper; the revised continuity note makes only the limited
interpretive point described in Response 6.

**Reviewer 3.** The full-deck override audit is now explicit. The mode-number
response distinguishes the existing x-periodic homogeneous calculation from
the requested inhomogeneous/ky analysis; the latter is not supplied. We accept
the diagnostic-comment framing proposed in the review and prioritize the
archived-data result over the elementary continuity observation. We also
accept the distinction between a DataCite DOI and Crossref coverage. The
mixture algebra, useful population information and empirical reconnection
evidence are preserved rather than presented as errors.

Sincerely,  
Taylor Kalin
