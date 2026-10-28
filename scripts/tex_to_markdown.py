#!/usr/bin/env python3
"""Convert the compiled manuscript without passing its math through Pandoc.

Run after compiling paper/main.tex so main.aux and main.bbl are current:
    python -X utf8 scripts/tex_to_markdown.py
Requires Pandoc on PATH, in its normal Windows installation directory, or at
--pandoc. No network requests or publication actions are performed.
"""
from __future__ import annotations

import argparse
import collections
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def group(text: str, at: int) -> tuple[str, int]:
    """Read one balanced TeX brace group, ignoring escaped braces."""
    while at < len(text) and text[at].isspace():
        at += 1
    if at >= len(text) or text[at] != "{":
        raise ValueError(f"Expected brace group near {text[at:at+70]!r}")
    start, depth, at = at + 1, 1, at + 1
    while at < len(text):
        if text[at] == "\\" and at + 1 < len(text) and text[at + 1] in "{}%":
            at += 2
            continue
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                return text[start:at], at + 1
        at += 1
    raise ValueError("Unbalanced TeX brace group")


def replace_group_command(text: str, command: str, transform) -> str:
    pattern = re.compile(r"\\" + re.escape(command) + r"\s*(?=\{)")
    chunks, pos = [], 0
    while match := pattern.search(text, pos):
        arg, end = group(text, match.end())
        chunks.extend((text[pos:match.start()], transform(arg)))
        pos = end
    chunks.append(text[pos:])
    return "".join(chunks)


class Converter:
    def __init__(self, root: Path, pandoc: str, version: str, date: str):
        self.root = root
        self.paper = root / "paper"
        self.pandoc = pandoc
        self.version = version
        self.date = date
        self.labels: dict[str, str] = {}
        self.citations: dict[str, str] = {}
        self.math: list[tuple[str, str, str]] = []
        self.blocks: list[tuple[str, str]] = []
        self.input_files: list[Path] = []
        self.equation = 0
        self.equation_checks: list[tuple[str, str]] = []
        self.stats = collections.Counter()
        self.headings: list[str] = []
        self.base = "https://raw.githubusercontent.com/Teylersf/counterstreaming-heatflux-audit/main/figures/"
        self.parse_aux()

    def parse_aux(self):
        aux = (self.paper / "main.aux").read_text(encoding="utf-8")
        for match in re.finditer(r"\\newlabel\s*(?=\{)", aux):
            key, end = group(aux, match.end())
            fields, _ = group(aux, end)
            number, _ = group(fields, 0)
            self.labels[key] = number
        self.citations = dict(re.findall(r"\\bibcite\{([^}]+)\}\{([^}]+)\}", aux))
        self.pages = int(re.search(r"\\@abspage@last\{(\d+)\}", aux).group(1))

    def expand_inputs(self, path: Path) -> str:
        path = path.resolve()
        if path in self.input_files:
            raise ValueError(f"Duplicate or recursive input: {path}")
        self.input_files.append(path)
        source = path.read_text(encoding="utf-8")
        source = re.sub(r"(?<!\\)%[^\n]*", "", source)
        def include(arg):
            candidate = self.paper / arg
            if not candidate.suffix:
                candidate = candidate.with_suffix(".tex")
            return "\n" + self.expand_inputs(candidate) + "\n"
        return replace_group_command(source, "input", include)

    def block(self, markdown: str) -> str:
        key = f"BLOCKZZ{len(self.blocks):06d}TOKEN"
        self.blocks.append((key, markdown))
        return "\n\n" + key + "\n\n"

    def math_token(self, raw: str, display: bool) -> str:
        raw = self.expand_math(raw.strip())
        key = f"MATHZZ{len(self.math):06d}TOKEN"
        rendered = "$$\n" + raw + "\n$$" if display else "$" + raw + "$"
        self.math.append((key, rendered, "display" if display else "inline"))
        return "\n\n" + key + "\n\n" if display else key

    def expand_math(self, raw: str) -> str:
        # Expand only the manuscript's author macros; retain standard LaTeX.
        for name, replacement in (("E", lambda x: r"\mathbb{E}\!\left[" + x + r"\right]"),
                                  ("norm", lambda x: r"\left\lVert " + x + r"\right\rVert"),
                                  ("bm", lambda x: r"\boldsymbol{" + x + "}")):
            while re.search(r"\\" + name + r"\s*\{", raw):
                raw = replace_group_command(raw, name, replacement)
        raw = re.sub(r"\\R\b", lambda _: r"\mathbb{R}", raw)
        raw = re.sub(r"\\dd\b", lambda _: r"\mathrm{d}", raw)
        for name in ("tr", "diag"):
            raw = re.sub(r"\\" + name + r"\b", lambda _, n=name: r"\operatorname{" + n + "}", raw)
        return raw.strip()

    def references(self, text: str) -> str:
        def citation(keys):
            values = [self.citations[k.strip()] for k in keys.split(",")]
            return "[" + ", ".join(values) + "]"
        text = replace_group_command(text, "cite", citation)
        text = replace_group_command(text, "eqref", lambda key: "(" + self.labels[key] + ")")
        text = replace_group_command(text, "ref", lambda key: self.labels[key])
        return text

    def protect_math(self, text: str) -> str:
        pattern = re.compile(
            r"(?P<environment>\\begin\{(?:equation|align|gather)\*?\}.*?\\end\{(?:equation|align|gather)\*?\})"
            r"|(?P<bracket>\\\[.*?\\\])|(?P<paren>\\\(.*?\\\))"
            r"|(?P<dollar>(?<!\\)\$(?!\$)(?:\\.|[^$])*?(?<!\\)\$)", re.S)
        def protect(match):
            value = match.group()
            if match.lastgroup == "environment":
                env = re.match(r"\\begin\{([^}]+)\}", value).group(1)
                raw = re.sub(r"^\\begin\{[^}]+\}|\\end\{[^}]+\}$", "", value)
                labels = re.findall(r"\\label\{([^}]+)\}", raw)
                raw = re.sub(r"\\label\{[^}]+\}", "", raw)
                numbers = []
                if not env.endswith("*"):
                    rows = re.split(r"\\\\(?:\[[^]]*\])?", raw) if env in ("align", "gather") else [raw]
                    for row in rows:
                        if row.strip() and not re.search(r"\\(?:nonumber|notag)\b", row):
                            self.equation += 1
                            numbers.append(str(self.equation))
                    if len(numbers) != 1:
                        raise ValueError(f"Expected one numbered row per source environment; got {numbers}")
                    for label in labels:
                        if self.labels[label] != numbers[0]:
                            raise ValueError(f"Equation mismatch for {label}: {numbers[0]} != {self.labels[label]}")
                        self.equation_checks.append((label, numbers[0]))
                raw = re.sub(r"\\(?:nonumber|notag)\b", "", raw).strip()
                if env.rstrip("*") == "align":
                    raw = r"\begin{aligned}" + "\n" + raw + "\n" + r"\end{aligned}"
                elif env.rstrip("*") == "gather":
                    raw = r"\begin{gathered}" + "\n" + raw + "\n" + r"\end{gathered}"
                if numbers:
                    raw += r"\tag{" + numbers[0] + "}"
                return self.math_token(raw, True)
            if match.lastgroup == "bracket":
                return self.math_token(value[2:-2], True)
            if match.lastgroup == "paren":
                return self.math_token(value[2:-2], False)
            return self.math_token(value[1:-1], False)
        return pattern.sub(protect, text)

    def to_md(self, text: str) -> str:
        result = subprocess.run([self.pandoc, "--from=latex", "--to=gfm+tex_math_dollars",
                                 "--wrap=none"], input=text, text=True, encoding="utf-8",
                                capture_output=True, check=True)
        if result.stderr.strip():
            raise RuntimeError("Pandoc warning: " + result.stderr.strip())
        return result.stdout.strip()

    def restore(self, markdown: str) -> str:
        for key, value in self.blocks:
            if markdown.count(key) != 1:
                raise ValueError(f"Lost/duplicated protected block {key}")
            markdown = markdown.replace(key, value)
        for key, value, _ in self.math:
            if markdown.count(key) != 1:
                raise ValueError(f"Lost/duplicated protected math {key}")
            markdown = markdown.replace(key, value)
        return markdown

    def bibliography(self) -> str:
        bbl = (self.paper / "main.bbl").read_text(encoding="utf-8")
        self.bibliography_urls = set(re.findall(r"\\(?:href|url)\{(https?://[^}]+)\}", bbl))
        entries = re.findall(r"\\bibitem\{([^}]+)\}\s*(.*?)(?=\\bibitem|\\end\{thebibliography\})", bbl, re.S)
        if len(entries) != len(self.citations):
            raise ValueError("Compiled bibliography/citation counts differ")
        output = [r"\section*{References}"]
        for i, (key, body) in enumerate(entries, 1):
            if self.citations[key] != str(i):
                raise ValueError("Compiled bibliography order differs from aux")
            body = body.replace(r"\newblock", " ")
            output.append(r"\noindent\textbf{[" + str(i) + "]} " + body + "\n\n")
        self.stats["references"] = len(entries)
        return "\n".join(output)

    def structure(self, text: str) -> str:
        # Number headings in the source order, including appendices.
        section, subsection, appendix = 0, 0, False
        pattern = re.compile(r"\\(?P<kind>section|subsection|subsubsection)(?P<star>\*)?\s*(?=\{)|\\appendix\b")
        pieces, pos = [], 0
        for match in pattern.finditer(text):
            pieces.append(text[pos:match.start()])
            if match.group() == r"\appendix":
                appendix, section, subsection = True, 0, 0
                pos = match.end()
                continue
            title, end = group(text, match.end())
            kind = match["kind"]
            if not match["star"]:
                if kind == "section":
                    section, subsection = section + 1, 0
                    prefix = chr(64 + section) if appendix else str(section)
                elif kind == "subsection":
                    subsection += 1
                    prefix = (chr(64 + section) if appendix else str(section)) + "." + str(subsection)
                else:
                    raise ValueError("Add explicit subsubsection numbering before using it")
                title = prefix + " " + title
            self.headings.append(title)
            pieces.append("\\" + kind + "*{" + title + "}")
            pos = end
        pieces.append(text[pos:])
        text = "".join(pieces)
        theorem = re.compile(r"\\begin\{(proposition|lemma|corollary)\}(?:\[([^]]*)\])?\s*\\label\{([^}]+)\}")
        def theorem_start(match):
            env, caption, label = match.groups()
            self.stats[env] += 1
            title = env.title() + " " + self.labels[label]
            if caption:
                title += " (" + caption + ")"
            return self.block("**" + title + ".**")
        text = theorem.sub(theorem_start, text)
        text = re.sub(r"\\end\{(?:proposition|lemma|corollary)\}", "\n", text)
        self.stats["proofs"] = len(re.findall(r"\\begin\{proof\}", text))
        text = re.sub(r"\\begin\{proof\}", lambda _: self.block("**Proof.**"), text)
        # One block token per proof ending, rather than reusing a placeholder.
        text = re.sub(r"\\end\{proof\}", lambda _: self.math_token(r"\square", False) + "\n", text)
        text = re.sub(r"\\label\{[^}]+\}", "", text)
        return text

    def tabular(self, text: str) -> str:
        match = re.search(r"\\begin\{tabular\}", text)
        _, body_at = group(text, match.end())
        end = text.index(r"\end{tabular}", body_at)
        body = text[body_at:end]
        body = re.sub(r"\\(?:toprule|midrule|bottomrule)\b(?:\[[^]]*\])?", "", body)
        body = re.sub(r"\\(?:hline|small|footnotesize|scriptsize)\b", "", body)
        rows = []
        for row in re.split(r"\\\\(?:\[[^]]*\])?", body):
            if not row.strip():
                continue
            cells = [self.to_md(cell.strip()).replace("\n", " ").replace("|", r"\|")
                     for cell in re.split(r"(?<!\\)&", row)]
            rows.append(cells)
        if len({len(row) for row in rows}) != 1:
            raise ValueError("Inconsistent table column count")
        self.stats["table_data_rows"] += len(rows) - 1
        self.stats["tables"] += 1
        lines = ["| " + " | ".join(rows[0]) + " |",
                 "| " + " | ".join("---" for _ in rows[0]) + " |"]
        lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
        return "\n".join(lines)

    def float_blocks(self, text: str) -> str:
        pattern = re.compile(r"\\begin\{(figure|table)\}(?:\[[^]]*\])?.*?\\end\{\1\}", re.S)
        def replace_float(match):
            block = match.group()
            kind = match.group(1)
            label = re.search(r"\\label\{([^}]+)\}", block)
            if not label:
                raise ValueError("Missing float label")
            number = self.labels[label.group(1)]
            cap = re.search(r"\\caption\s*(?=\{)", block)
            caption, _ = group(block, cap.end())
            caption_md = self.to_md(caption)
            if kind == "figure":
                image = re.search(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", block).group(1)
                name = Path(image).stem + ".png"
                self.stats["figures"] += 1
                result = f"![Figure {number}]({self.base}{name})\n\n**Figure {number}.** {caption_md}"
            else:
                result = f"**Table {number}.** {caption_md}\n\n" + self.tabular(block)
            return self.block(result)
        text = pattern.sub(replace_float, text)
        # An unnumbered pressure table and the execution hash table also matter.
        text = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}",
                      lambda m: self.block(self.tabular(m.group())), text, flags=re.S)
        return text

    def generate(self):
        expanded = self.expand_inputs(self.paper / "main.tex")
        title_match = re.search(r"\\title\s*(?=\{)", expanded)
        title_tex, _ = group(expanded, title_match.end())
        author_match = re.search(r"\\author\s*(?=\{)", expanded)
        author_tex, _ = group(expanded, author_match.end())
        website = re.search(r"\\href\{(https://taylorkalin\.com[^}]*)\}", author_tex).group(1)
        email = re.search(r"\\href\{mailto:([^}]+)\}", author_tex).group(1)
        orcid = re.search(r"https://orcid\.org/([^}]+)", author_tex).group(1)
        title = self.to_md(title_tex)
        body = expanded.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
        # Protect exact code before performing any TeX substitutions.
        def code_block(match):
            self.stats["code_blocks"] += 1
            content = match.group(1).strip("\n")
            return self.block("```text\n" + content + "\n```")
        body = re.sub(r"\\begin\{verbatim\}(.*?)\\end\{verbatim\}", code_block, body, flags=re.S)
        # Join only deliberately wrapped hexadecimal identifiers, never prose.
        body = re.sub(r"\\texttt\{([0-9a-f]{20,})\}\\\\\s*\\texttt\{([0-9a-f]{20,})\}",
                      lambda m: r"\texttt{" + m[1] + m[2] + "}", body)
        def join_hash_quote(match):
            inner = re.sub(r"\\(?:footnotesize|small|ttfamily)\b", "", match.group(1))
            joined = re.sub(r"\\\\|\s+", "", inner).strip()
            if re.fullmatch(r"[0-9a-f]{64}\.?", joined):
                return self.block("`" + joined.rstrip(".") + "`" + ("." if joined.endswith(".") else ""))
            return match.group()
        body = re.sub(r"\\begin\{quote\}(.*?)\\end\{quote\}", join_hash_quote, body, flags=re.S)
        body = body.replace(r"\maketitle", "")
        body = re.sub(r"\\bibliographystyle\{[^}]+\}", "", body)
        body = re.sub(r"\\bibliography\{[^}]+\}", lambda _: self.bibliography(), body)
        body = self.references(body)
        # Capture float labels before structure() removes all remaining labels.
        body = self.protect_math(body)
        body = self.float_blocks(body)
        body = self.structure(body)
        body = body.replace(r"\begin{abstract}", r"\section*{Abstract}")
        body = body.replace(r"\end{abstract}", "")
        body = re.sub(r"\\(?:begin|end)\{center\}", "\n", body)
        # Size and layout controls have no semantic role in platform Markdown.
        body = re.sub(r"\\(?:centering|small|footnotesize|scriptsize|noindent)\b", "", body)
        body = re.sub(r"\\fontsize\{[^}]+\}\{[^}]+\}\\selectfont", "", body)
        markdown = self.restore(self.to_md(body))
        # Pandoc escapes literal citation brackets. Keep the plain numerical
        # citation syntax so math renderers cannot mistake it for \[...\].
        markdown = re.sub(r"\\\[(\d+(?:,\s*\d+)*)\\\]", r"[\1]", markdown)
        header = ("# " + title + "\n\n**Taylor Kalin**\n\n"
                  f"[taylorkalin.com]({website}) · [{email}](mailto:{email}) · "
                  f"[ORCID: {orcid}](https://orcid.org/{orcid})\n\n"
                  + date.fromisoformat(self.date).strftime("%d %B %Y") + " · Version " + self.version + "\n\n")
        markdown = header + markdown
        markdown = "\n".join(line.rstrip() for line in markdown.splitlines()).strip() + "\n"
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        unresolved = re.findall(r"\\(?:ref|eqref|cite|label|norm|E|R|dd|tr|diag|bm|input)\b", markdown)
        if unresolved or re.search(r"(?:MATH|BLOCK)ZZ\d+TOKEN", markdown):
            raise ValueError(f"Unresolved TeX or placeholders: {unresolved}")
        if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", markdown):
            raise ValueError("An absolute local filesystem path remains")
        if len(markdown) >= 150000 or len(title) >= 200:
            raise ValueError("Submission body/title exceeds target limit")
        # Reuse the protected-math abstract already restored in the manuscript.
        abstract = re.search(r"(?ms)^# Abstract\n\n(.*?)(?=^# )", markdown).group(1)
        abstract = re.sub(r"\s+", " ", abstract).strip()
        if len(abstract) >= 3000:
            raise ValueError("Abstract exceeds target limit")
        tags = re.findall(r"\\tag\{([^}]+)\}", markdown)
        if tags != [str(i) for i in range(1, self.equation + 1)]:
            raise ValueError("Output equation numbers are missing, duplicated or out of order")
        # Ensure all direct source links survive (figure source paths are adapted).
        urls = set(re.findall(r"\\(?:href|url)\{(https?://[^}]+)\}", expanded))
        missing_urls = sorted(url for url in urls if url not in markdown)
        missing_urls += sorted(url for url in self.bibliography_urls if url not in markdown)
        if missing_urls:
            raise ValueError(f"Source URLs lost: {missing_urls}")
        if markdown.count("**Proof.**") != self.stats["proofs"] or markdown.count(r"$\square$") != self.stats["proofs"]:
            raise ValueError("Proof start/end count mismatch")
        self.validate_markdown(markdown)
        metadata = {
            "title": title, "abstract": abstract,
            "keywords": ["counter-streaming heat flux", "magnetic reconnection", "moment closures",
                         "initial-state matching", "plasma stability", "reproducibility"],
            "authors": [{"name": "Taylor Kalin", "orcid": orcid, "email": email, "website": website}],
            "date": self.date, "version": self.version, "source_version": "arXiv:2607.07106v1",
            "manuscript_characters": len(markdown),
            "funding": "Self-funded by Taylor Kalin; no external funding received."
        }
        (self.root / "submissions").mkdir(exist_ok=True)
        (self.root / "submissions/manuscript.md").write_text(markdown, encoding="utf-8", newline="\n")
        (self.root / "submissions/metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        self.stats.update(collections.Counter(kind + "_math" for _, _, kind in self.math))
        self.stats["numbered_equations"] = self.equation
        self.stats["equation_label_checks"] = len(self.equation_checks)
        self.stats["source_tex_files"] = len(self.input_files)
        self.stats["body_source_urls"] = len(urls)
        self.stats["bibliography_urls"] = len(self.bibliography_urls)
        self.stats["manuscript_characters"] = len(markdown)
        self.stats["title_characters"] = len(title)
        self.stats["abstract_characters"] = len(abstract)
        self.stats["compiled_pdf_pages"] = self.pages
        self.write_notes()
        print(json.dumps({"status": "passed", **self.stats}, ensure_ascii=False, indent=2))

    def validate_markdown(self, markdown: str):
        """Read the final Markdown independently and compare formula contents."""
        result = subprocess.run([self.pandoc, "--from=gfm+tex_math_dollars", "--to=json"],
                                input=markdown, text=True, encoding="utf-8",
                                capture_output=True, check=True)
        if result.stderr.strip():
            raise RuntimeError("Markdown reader warning: " + result.stderr.strip())
        tree = json.loads(result.stdout)
        nodes = []
        def walk(value):
            if isinstance(value, dict):
                if value.get("t") in ("Math", "CodeBlock", "RawInline", "RawBlock"):
                    nodes.append(value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(tree)
        # CommonMark removes line-leading indentation. Ignore only those
        # insignificant TeX spaces, retaining all formula tokens and commands.
        def normalized(value):
            return "\n".join(line.strip() for line in value.strip().splitlines())
        formulas = collections.Counter((n["c"][0]["t"], normalized(n["c"][1]))
                                       for n in nodes if n["t"] == "Math")
        expected = collections.Counter(
            ("DisplayMath" if kind == "display" else "InlineMath",
             normalized(value[2:-2] if kind == "display" else value[1:-1]))
            for _, value, kind in self.math)
        if formulas != expected:
            raise ValueError("Final Markdown parser did not recover every exact formula: "
                             + repr({"missing": list((expected - formulas).elements())[:3],
                                     "extra": list((formulas - expected).elements())[:3]}))
        if any(n["t"] in ("RawInline", "RawBlock") for n in nodes):
            raise ValueError("Unconverted raw markup remains in the Markdown")
        actual_code = [n["c"][1] for n in nodes if n["t"] == "CodeBlock"]
        expected_code = [value[len("```text\n"):-len("\n```")]
                         for _, value in self.blocks if value.startswith("```text\n")]
        if actual_code != expected_code:
            raise ValueError("Final Markdown changed an execution-code block")
        self.stats["parsed_math_segments"] = sum(formulas.values())

    def write_notes(self):
        version = subprocess.run([self.pandoc, "--version"], text=True, encoding="utf-8", capture_output=True, check=True).stdout.splitlines()[0]
        s = self.stats
        notes = f"""# Manuscript conversion checks — version {self.version}

- Converted `paper/main.tex`, every included section and `paper/results-table.tex` using {version}; the compiled PDF has {self.pages} pages.
- Reproduce after compiling the TeX: `python -X utf8 scripts/tex_to_markdown.py` (use `--pandoc PATH` if needed). The saved script performs no network or publication actions.
- Mathematics was protected before prose conversion. Custom expectation, norm, real-number, differential and operator macros were expanded to standard KaTeX-compatible LaTeX; formulas were never passed through Pandoc.
- Preserved {s['numbered_equations']} numbered equations and cross-checked all {s['equation_label_checks']} labeled equation positions against current `main.aux`. Output equation tags are complete, consecutive and in source order.
- Preserved {s['proofs']} complete proofs, {s['proposition']} propositions, {s['lemma']} lemmas and {s['corollary']} corollaries. Proof start and end marks were checked.
- Protected {s['inline_math']} inline and {s['display_math']} display-math segments, including proof end marks. Every protected segment and block was restored exactly once. An independent parse of the final Markdown recovered all {s['parsed_math_segments']} exact formula contents, both unchanged code blocks and no raw markup.
- Preserved {s['tables']} tables with {s['table_data_rows']} data rows, {s['figures']} figures with full captions, source passages, both execution-code blocks, all exact source and verification hashes, and all {s['references']} compiled bibliography entries in actual numerical order. The bibliography's undated OSIRIS entry remains undated.
- Checked preservation of all {s['body_source_urls']} direct body source URLs and all {s['bibliography_urls']} bibliography URLs. Figure links use the public GitHub raw PNG paths for `initial-state.png` and `stability.png`.
- Retained all scientific qualifications: archived-moment reanalysis is distinct from a new simulation; current mismatch is about 11.5%, pressure mismatch about 20% in the xx component and 38.4% in the zz component; the finite-relaxation false positive is a longitudinal continuum test.
- Taylor Kalin is the sole header author, with the website, email and ORCID from the TeX author block. No phone number was added. The separate author/methods disclosure and owner-confirmed self-funded statement are preserved.
- No unresolved internal references, citations, custom math macros, placeholders, absolute local paths or trailing whitespace remain. Length limits are checked by the script.
- Manuscript length: {s['manuscript_characters']} characters; title {s['title_characters']} characters; abstract {s['abstract_characters']} characters.
- Conversion checks verify preservation and formatting, not independent scientific peer review.

Compiled inputs used:

| File | SHA-256 |
| --- | --- |
"""
        for path in self.input_files + [self.paper / "main.aux", self.paper / "main.bbl"]:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            notes += f"| `{path.relative_to(self.root).as_posix()}` | `{digest}` |\n"
        (self.root / "submissions/format-notes.md").write_text(notes, encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pandoc")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--date", default="2026-10-28")
    args = parser.parse_args()
    pandoc = args.pandoc or shutil.which("pandoc")
    if not pandoc:
        candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc/pandoc.exe"
        if candidate.is_file():
            pandoc = str(candidate)
    if not pandoc:
        parser.error("Pandoc not found; install it or pass --pandoc")
    Converter(args.root.resolve(), pandoc, args.version, args.date).generate()


if __name__ == "__main__":
    main()
