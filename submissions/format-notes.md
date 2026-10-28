# Manuscript conversion checks — version 1.1.0

- Converted `paper/main.tex` and its 11 included TeX files using pandoc.exe 3.3; the current compiled auxiliary file records 19 PDF pages. The exact inputs are listed below.
- Reproduce after compiling the TeX: `python -X utf8 scripts/tex_to_markdown.py --version 1.1.0 --date 2026-10-28` (use `--pandoc PATH` if needed). The saved script performs no network or publication actions.
- Mathematics was protected before prose conversion. Custom expectation, norm, real-number, differential and operator macros were expanded to standard KaTeX-compatible LaTeX; formulas were never passed through Pandoc.
- Preserved 21 numbered equations and cross-checked all 21 labeled equation positions against current `main.aux`. Output equation tags are complete, consecutive and in source order.
- Preserved 3 complete proofs, 3 propositions, 0 lemmas and 0 corollaries. Proof start and end marks were checked.
- Protected 277 inline and 29 display-math segments, including proof end marks. Every protected segment and block was restored exactly once. An independent parse of the final Markdown recovered all 306 exact formula contents, 3 unchanged code blocks and no raw markup.
- Preserved 5 tables with 31 data rows, 3 figures with full captions, 3 source code blocks, and all 11 compiled bibliography entries in actual numerical order.
- Checked preservation of all 9 direct body source URLs and all 11 bibliography URLs. Figure links use the public GitHub raw PNG paths for these actual source figures: `initial-state.png`, `profile-sensitivity.png`, `stability.png`.
- Scientific statements and qualifications come from the current TeX inputs; these conversion checks do not establish scientific correctness or supply missing experiments.
- Taylor Kalin is the sole header author, with the website, email and ORCID from the TeX author block. No phone number was added. The separate author/methods disclosure and owner-confirmed self-funded statement are preserved.
- No unresolved internal references, citations, custom math macros, placeholders, absolute local paths or trailing whitespace remain. Length limits are checked by the script.
- Manuscript length: 59514 characters; title 95 characters; abstract 1566 characters.
- Conversion checks verify preservation and formatting, not independent scientific peer review.

Compiled inputs used:

| File | SHA-256 |
| --- | --- |
| `paper/main.tex` | `d3985b6881e108e8175cfb3eb19377d48af8ed36d30bc7c0850ee1a654d47250` |
| `paper/sections/introduction.tex` | `94feaa63cf6ca1ef17fa80188e873becda4f30c18f73cefbb0bd374e35ca14bb` |
| `paper/sections/initialization.tex` | `6c8291c4ec72c0de39809e6007af1e600951f22c488a578e66c4b8080829525a` |
| `paper/sections/stability.tex` | `1f18510547b4bbe9f08e9ccdf2c028c0229345a815be3b4a5643db80e912323a` |
| `paper/sections/continuity.tex` | `8adeeec627724fb98b831ce9c55fd05811f45a982c1fc8630151c169705724e9` |
| `paper/sections/conditioning.tex` | `0fc116c8ccfbd1223e6e8abff3ef3787ac7f83505e80214dca4418b479c1d345` |
| `paper/sections/entropy.tex` | `652e42e28e7e49a32100c5e1041a02fb320862cd313b0c7bb48f3ac58f351d06` |
| `paper/sections/reproducibility.tex` | `bbc1c7a4c845a7147d0dc945d5c24379438ab33f1edb79415a01446837af1f55` |
| `paper/results-table.tex` | `600f9b6e869a80051c6daafe3a7b3053a0c19b4d8059454442f6b4e59346c4c6` |
| `paper/sections/discussion.tex` | `cbbf6a4dcd4558628ce91866e2f7076f5439d8f9fd34f424e41a80784acce222` |
| `paper/sections/source-evidence.tex` | `f13468d81065bd7a438b5e2a9081a6af06931b2d731ace62b8454915527fb48f` |
| `paper/sections/execution.tex` | `885bb147af675b3bf6e7c29f6f9f814b6d91469de97f17a7534307e1a81cdaff` |
| `paper/main.aux` | `58679829d94f812f3a723014f05dfea9e5d9aa5e0d440febc5f81e9f128988d2` |
| `paper/main.bbl` | `aa6f3170e7f38bbce60e72ba5537f9b9e85c7d114ce4b225edb708d24e0a8d36` |
