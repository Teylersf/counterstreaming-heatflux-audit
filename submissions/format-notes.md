# Manuscript conversion checks — version 1.0.0

- Converted `paper/main.tex`, every included section and `paper/results-table.tex` using pandoc.exe 3.3; the compiled PDF has 15 pages.
- Reproduce after compiling the TeX: `python -X utf8 scripts/tex_to_markdown.py` (use `--pandoc PATH` if needed). The saved script performs no network or publication actions.
- Mathematics was protected before prose conversion. Custom expectation, norm, real-number, differential and operator macros were expanded to standard KaTeX-compatible LaTeX; formulas were never passed through Pandoc.
- Preserved 21 numbered equations and cross-checked all 21 labeled equation positions against current `main.aux`. Output equation tags are complete, consecutive and in source order.
- Preserved 3 complete proofs, 3 propositions, 0 lemmas and 0 corollaries. Proof start and end marks were checked.
- Protected 210 inline and 27 display-math segments, including proof end marks. Every protected segment and block was restored exactly once. An independent parse of the final Markdown recovered all 237 exact formula contents, both unchanged code blocks and no raw markup.
- Preserved 4 tables with 17 data rows, 2 figures with full captions, source passages, both execution-code blocks, all exact source and verification hashes, and all 10 compiled bibliography entries in actual numerical order. The bibliography's undated OSIRIS entry remains undated.
- Checked preservation of all 6 direct body source URLs and all 10 bibliography URLs. Figure links use the public GitHub raw PNG paths for `initial-state.png` and `stability.png`.
- Retained all scientific qualifications: archived-moment reanalysis is distinct from a new simulation; current mismatch is about 11.5%, pressure mismatch about 20% in the xx component and 38.4% in the zz component; the finite-relaxation false positive is a longitudinal continuum test.
- Taylor Kalin is the sole header author, with the website, email and ORCID from the TeX author block. No phone number was added. The separate author/methods disclosure and owner-confirmed self-funded statement are preserved.
- No unresolved internal references, citations, custom math macros, placeholders, absolute local paths or trailing whitespace remain. Length limits are checked by the script.
- Manuscript length: 47290 characters; title 95 characters; abstract 1415 characters.
- Conversion checks verify preservation and formatting, not independent scientific peer review.

Compiled inputs used:

| File | SHA-256 |
| --- | --- |
| `paper/main.tex` | `db2edd75a47338d81c1a14f4297b824026b2fc85e82e34cd58443d1e1acc631a` |
| `paper/sections/introduction.tex` | `93958099fbd0cc36b5cb16bcaf037605126f9595589d63e07cf6a12505549443` |
| `paper/sections/initialization.tex` | `936de8bf9e0eab5c62c98f2efed90d55ad698b263ad40f8b2e59eae5fd608316` |
| `paper/sections/stability.tex` | `b6314ec5d76ff81f15edb5773190e9123ee0c17792ae85ab0e703673140c78a5` |
| `paper/sections/continuity.tex` | `3e8b28cb31aa24b84ff7f52a865ee9f36d241ecffb9c7570c401c2464fbd0aca` |
| `paper/sections/conditioning.tex` | `0fc116c8ccfbd1223e6e8abff3ef3787ac7f83505e80214dca4418b479c1d345` |
| `paper/sections/entropy.tex` | `652e42e28e7e49a32100c5e1041a02fb320862cd313b0c7bb48f3ac58f351d06` |
| `paper/sections/reproducibility.tex` | `9877f5478886e29c4d5d44746b2a675bb9a9d688182f615c46f5eb326d603262` |
| `paper/results-table.tex` | `600f9b6e869a80051c6daafe3a7b3053a0c19b4d8059454442f6b4e59346c4c6` |
| `paper/sections/discussion.tex` | `703277ef8a30c977ca4c9c593dcb549e3bbc5c21773fa14ccbf471666585a42e` |
| `paper/sections/source-evidence.tex` | `f13468d81065bd7a438b5e2a9081a6af06931b2d731ace62b8454915527fb48f` |
| `paper/sections/execution.tex` | `d35eef845723747fbc9e156a7d2fecbfab1dc16963cec3ebfee08efab68c1e5d` |
| `paper/main.aux` | `aa0021786943a48d3a6a024eb010de5276d37efcd8c26c71248b1a695321aa23` |
| `paper/main.bbl` | `a92561b15e9d281a92e2e4db0e6e97ddab0b75f5d02b887e6334cd0ee4a3224c` |
