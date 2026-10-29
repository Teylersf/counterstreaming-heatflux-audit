# Manuscript conversion checks — version 1.2.0

- Converted `paper/main.tex` and its 15 included TeX files using pandoc.exe 3.3; the current compiled auxiliary file records 26 PDF pages. The exact inputs are listed below.
- Reproduce after compiling the TeX: `python -X utf8 scripts/tex_to_markdown.py --version 1.2.0 --date 2026-10-28` (use `--pandoc PATH` if needed). The saved script performs no network or publication actions.
- Mathematics was protected before prose conversion. Custom expectation, norm, real-number, differential and operator macros were expanded to standard KaTeX-compatible LaTeX; formulas were never passed through Pandoc.
- Preserved 21 numbered equations and cross-checked all 21 labeled equation positions against current `main.aux`. Output equation tags are complete, consecutive and in source order.
- Preserved 3 complete proofs, 3 propositions, 0 lemmas and 0 corollaries. Proof start and end marks were checked.
- Protected 355 inline and 32 display-math segments, including proof end marks. Every protected segment and block was restored exactly once. An independent parse of the final Markdown recovered all 387 exact formula contents, 2 unchanged code blocks and no raw markup.
- Preserved 8 tables with 33 data rows, 6 figures with full captions, 2 source code blocks, and all 12 compiled bibliography entries in actual numerical order.
- Checked preservation of all 14 direct body source URLs and all 12 bibliography URLs. Figure links use versioned public GitHub raw PNG URLs for these actual source figures: `initial-state.png`, `profile-sensitivity.png`, `numerical-endpoints-pressure-history.png`, `numerical-endpoints-errors.png`, `numerical-endpoints-profiles.png`, `stability.png`; versioning affects venue ingestion, not image pixels.
- Scientific statements and qualifications come from the current TeX inputs; these conversion checks do not establish scientific correctness or supply missing experiments.
- Taylor Kalin is the sole header author, with the website, email and ORCID from the TeX author block. No phone number was added. The separate author/methods disclosure and owner-confirmed self-funded statement are preserved.
- No unresolved internal references, citations, custom math macros, placeholders, absolute local paths or trailing whitespace remain. Length limits are checked by the script.
- Manuscript length: 81667 characters; title 97 characters; abstract 1841 characters.
- Conversion checks verify preservation and formatting, not independent scientific peer review.

Compiled inputs used:

| File | SHA-256 |
| --- | --- |
| `paper/main.tex` | `b5c59f3992d35566641095ed982581cedf591cf1b425b8b2ba5cb785da1920f9` |
| `paper/sections/introduction.tex` | `dd1c5152ae298283c848c18c957fbe2f2ba9c1c18de5eaff149af401fa1b6e50` |
| `paper/sections/initialization.tex` | `36aec013ea0da9fb6665f62202b67dfaebcdc1e055685805c8821568d2d24792` |
| `paper/sections/controls.tex` | `0162376565940e0480cbcdf7a1a6ee43416dc04e06cfe61da439449edc33358a` |
| `figures/numerical-endpoints-outcomes-table.tex` | `befe9c887bee4f59652c94de197e881505f112e1ecdfde3eeef02dd9ff158d2a` |
| `figures/numerical-endpoints-fidelity-table.tex` | `1bad9674eea8cef936dba35e164903c4e08cc94ead0485e0a74a1acd104f52f3` |
| `figures/numerical-endpoints-table.tex` | `7672245feeaf396a1a2744a6f19d9877fcac2b053da3c66076906bc46fa0f272` |
| `paper/sections/stability.tex` | `1f18510547b4bbe9f08e9ccdf2c028c0229345a815be3b4a5643db80e912323a` |
| `paper/sections/continuity.tex` | `8adeeec627724fb98b831ce9c55fd05811f45a982c1fc8630151c169705724e9` |
| `paper/sections/conditioning.tex` | `0fc116c8ccfbd1223e6e8abff3ef3787ac7f83505e80214dca4418b479c1d345` |
| `paper/sections/entropy.tex` | `652e42e28e7e49a32100c5e1041a02fb320862cd313b0c7bb48f3ac58f351d06` |
| `paper/sections/reproducibility.tex` | `3095e62fd1fb062f8e3d4ba1d91399654d28b38a3c3e1ea0ea280416257c3dd9` |
| `paper/results-table.tex` | `600f9b6e869a80051c6daafe3a7b3053a0c19b4d8059454442f6b4e59346c4c6` |
| `paper/sections/discussion.tex` | `59532a1c3a97e9d47011150906060dbad1e3c6275fd9785d2a1e386652d3acfb` |
| `paper/sections/source-evidence.tex` | `f13468d81065bd7a438b5e2a9081a6af06931b2d731ace62b8454915527fb48f` |
| `paper/sections/execution.tex` | `bf3d89db24710e16d166a48ea574ad69701bbd9648d80841768b7fcb35bf106d` |
| `paper/main.aux` | `28d28356b4a5829e115e6e5ae2d6cc002bc31f42d3b968a343fc704471b773b5` |
| `paper/main.bbl` | `0ee7dfd75c7313d27914dd938de118f93d2f79701c8734e1b27345405e46609c` |
