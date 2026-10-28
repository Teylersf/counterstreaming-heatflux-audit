# Selective source evidence

These attributed excerpts come from McGrae-Menge et al., *Counter-streaming
heat-flux closure for electron-only collisionless magnetic reconnection*,
[arXiv:2607.07106v1](https://arxiv.org/abs/2607.07106v1), distributed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The original authors
retain their rights. The excerpts identify passages being assessed; they do
not imply that every quoted statement is wrong.

| File | Purpose |
|---|---|
| `mixture-identities.txt` | Preserve the valid standard mixture formulas and explicit index-sum convention. |
| `matched-state-and-periodic-seed.txt` | Identify the stated periodic setup, Eq. (A3), ordinary-velocity/current relation and matched initialization claim. |
| `local-isotropization-and-instability.txt` | Identify the finite coefficient actually used, the acknowledged omitted contribution, and the linear-instability assertion. |
| `midplane-transport.txt` | Identify the symmetry-plane density-transport explanation. |
| `accuracy-and-cubic-scaling.txt` | Identify the best-time empirical metric and thermal/drift scaling argument. |
| `disclosed-scope.txt` | Preserve acknowledged stream folding, independently scaled fluid maps, and kinetic free-expansion limitations. |

There are **six excerpt files and 17 source fragments**, containing 5,544
bytes of source text. Each fragment records the original `apssamp.tex` line
numbers and character offsets. Lines are 1-based; character indices are
0-based Unicode-code-point offsets, with the end exclusive. Multiline
fragments join the original line contents using LF. Separate fragments are
not stitched together as one continuous quotation. Consult the full source
for context.

## Independent verification

Download the exact [versioned source archive](https://arxiv.org/src/2607.07106v1)
into a local temporary folder, then run from the repository root:

```sh
python source-excerpts/verify.py PATH_TO_DOWNLOADED_ARCHIVE
```

The verifier checks the complete archive SHA-256 and byte count, reads the
original TeX member without extracting archive contents to disk, verifies its
hash, and reconstructs every excerpt from the recorded positions. It checks
both individual fragments and the complete excerpt-file hashes against
[manifest.json](manifest.json). It makes no network requests. A mismatch means
a different byte artifact or excerpt, not automatically a scientific revision.

The original PDF and full source are not redistributed here. [SOURCE.md](../SOURCE.md)
records their hashes and the July 8 arXiv history / July 9 PDF / August 24
experimental-HTML date distinction. The original TeX uses `\date{\today}`;
conversion dates are not evidence of a new arXiv version.

The authors' standalone input decks and selected deposited-data analysis are
documented separately. This source verifier does not rerun a reconnection
simulation or certify the audit's mathematical conclusions.
