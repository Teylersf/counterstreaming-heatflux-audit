## Version 1.1.0

**Author: Taylor Kalin**

This 19-page diagnostic comment audits initial-state controls in
arXiv:2607.07106v1. It preserves the valid mixture identities and makes no
claim that the source's later nonlinear conclusions have been disproved.

- Reloads five archived fluid BP snapshots and confirms their embedded input
  decks exactly match the posted Lua files. All ten initialized moment
  components agree to roundoff over the full grid.
- Measures a 9.87% relative L2 difference between the full x-averaged PIC and
  fluid current profiles; central PIC pressures remain about 20% lower in
  Pxx and 38.4% lower in Pzz.
- Adds full-domain sensitivity results and a conditional, unfitted
  finite-temperature loading calculation with converged quadrature.
- Presents stability as an auxiliary homogeneous closure benchmark, with no
  claimed eigenmode in the source's inhomogeneous sheet.
- Retains eight original passing verification groups and their identical
  code bytes, with separate additional archived-data and loading checks.

Numerical code pin: `0d07de76f3d0b56e49e9ef2b9de931b8567ad0c8`.
All 19 pages were rendered and visually inspected. Markdown preserves 306
math expressions, 21 numbered equations, three proofs, three figures, five
tables and 11 compiled references.

No native deposited-current diagnostic is identifiable in the complete PIC
archive inventory. No full-archive checksum verification, matched-state
reconnection rerun, sheet eigenanalysis or independent human peer review is
claimed. Taylor Kalin self-funded this study; AI assistance is disclosed
separately from his authorship.

The PDF, source, code, derived profiles and provenance are included. Raw
snapshots and full simulation archives remain excluded. Actual venue outcomes
are tracked separately in the publication-status record.
