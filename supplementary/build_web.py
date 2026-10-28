"""Build the web version of the Supplementary Material (docs/index.html).

The page is generated from supplementary_material.tex so that the PDF and the
web version share their text and their S-numbering. Only the LaTeX constructs
used in that file are supported; anything else stops the build.

Usage (from the repository root or this folder):
    python supplementary/build_web.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEX = HERE / "supplementary_material.tex"
OUT = ROOT / "docs" / "index.html"
REPO = "https://github.com/atilimkoca/holonic-clinical-evidence"
SITE = "https://atilimkoca.github.io/holonic-clinical-evidence/"
TITLE = ("Holonic Knowledge Representation for Clinical Evidence: Boundary-Aware "
         "Validation and Hallucination Control in LLM-Augmented Knowledge Graphs")
AUTHORS = ("Deniz Kılınç, Orhan Er, Okan Bursa, Murat Uçar, Ömer Atılım Koca, "
           "Emre Turan, Kaan Kıvırcık")
AFFILIATION = "Department of Computer Engineering, Izmir Bakircay University, Izmir, Turkey"


def braced(s: str, i: int) -> tuple[str, int]:
    """Return the content of the brace group starting at s[i] and the index after it."""
    if s[i] != "{":
        raise ValueError(f"expected '{{' at: {s[i:i + 40]!r}")
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif s[j] == "}" and s[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    raise ValueError(f"unbalanced braces: {s[i:i + 40]!r}")


def math_html(m: str) -> str:
    """Render the small amount of inline math used in the supplement."""
    m = m.replace("\\times", "×").replace("\\kappa", "κ")
    m = re.sub(r"\^\{([^}]*)\}", lambda g: "<sup>" + g.group(1).replace("-", "−") + "</sup>", m)
    m = re.sub(r"_\{([^}]*)\}|_(\w)", lambda g: "<sub>" + (g.group(1) or g.group(2)) + "</sub>", m)
    m = re.sub(r"(?<![\w<>/])([A-Za-z])(?![\w>])", r"<i>\1</i>", m)
    if "\\" in m:
        raise ValueError(f"unsupported math: {m!r}")
    return f'<span class="math">{m}</span>'


def inline(s: str, labels: dict[str, str]) -> str:
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if s.startswith("\\(", i):
            j = s.index("\\)", i)
            out.append(math_html(s[i + 2:j]))
            i = j + 2
        elif c == "$":
            j = s.index("$", i + 1)
            out.append(math_html(s[i + 1:j]))
            i = j + 1
        elif c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            cmd = m.group(1)
            i += len(m.group(0))
            if cmd in ("texttt", "textbf", "emph", "url", "breakid", "ref", "c"):
                arg, i = braced(s, i)
                if cmd == "texttt":
                    out.append("<code>" + inline(arg, labels) + "</code>")
                elif cmd == "textbf":
                    out.append("<strong>" + inline(arg, labels) + "</strong>")
                elif cmd == "emph":
                    out.append("<em>" + inline(arg, labels) + "</em>")
                elif cmd == "url":
                    out.append(f'<a href="{html.escape(arg)}">{html.escape(arg)}</a>')
                elif cmd == "breakid":
                    out.append("<code>" + html.escape(arg) + "</code>")
                elif cmd == "ref":
                    out.append(f'<a href="#{labels[arg]["id"]}">{labels[arg]["num"]}</a>')
                elif cmd == "c" and arg == "c":
                    out.append("ç")
                else:
                    raise ValueError(f"unsupported \\c{{{arg}}}")
            elif cmd in ("%", "_", "&", "#"):
                out.append(html.escape(cmd))
            elif cmd == " ":
                out.append(" ")
            else:
                raise ValueError(f"unsupported command \\{cmd} in {s[:60]!r}")
        elif s.startswith("``", i):
            out.append("“"); i += 2
        elif s.startswith("''", i):
            out.append("”"); i += 2
        elif s.startswith("---", i):
            out.append("—"); i += 3
        elif s.startswith("--", i):
            out.append("–"); i += 2
        elif c == "~":
            out.append("&nbsp;"); i += 1
        elif c in "{}":
            i += 1
        else:
            out.append(html.escape(c)); i += 1
    return "".join(out)


def parse_table(block: str, labels: dict[str, str]) -> str:
    caption, _ = braced(block, block.index("\\caption") + len("\\caption"))
    label, _ = braced(block, block.index("\\label") + len("\\label"))
    m = re.search(r"\\begin\{(tabularx?)\}", block)
    i = m.end()
    if m.group(1) == "tabularx":
        _, i = braced(block, i)
    spec, i = braced(block, i)
    body = block[i:block.index("\\end{" + m.group(1) + "}")]
    spec = re.sub(r"@\{\}", "", spec)
    aligns = []
    k = 0
    while k < len(spec):
        ch = spec[k]
        if ch in "lrc":
            aligns.append({"l": "left", "r": "right", "c": "center"}[ch]); k += 1
        elif ch == "X":
            aligns.append("left"); k += 1
        elif ch == "p":
            _, k = braced(spec, k + 1); aligns.append("left")
        else:
            k += 1
    rows, rule_before = [], False
    for raw in body.split("\\\\"):
        raw = raw.strip()
        while raw.startswith(("\\toprule", "\\midrule", "\\bottomrule")):
            if raw.startswith("\\midrule"):
                rule_before = True
            raw = raw.split("rule", 1)[1].strip()
        if not raw:
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)&", raw)]
        rows.append((cells, rule_before))
        rule_before = False
    num = labels[label]["num"]
    parts = [f'<figure class="table" id="{labels[label]["id"]}">',
             f"<figcaption><strong>{num}.</strong> {inline(caption, labels)}</figcaption>",
             '<div class="scroll"><table>']
    head, *rest = rows
    parts.append("<thead><tr>" + "".join(
        f'<th style="text-align:{aligns[n]}">{inline(c, labels)}</th>' for n, c in enumerate(head[0])) + "</tr></thead><tbody>")
    for cells, rule in rest:
        cls = ' class="rule"' if rule else ""
        parts.append(f"<tr{cls}>" + "".join(
            f'<td style="text-align:{aligns[n]}">{inline(c, labels)}</td>' for n, c in enumerate(cells)) + "</tr>")
    parts.append("</tbody></table></div></figure>")
    return "\n".join(parts)


def main() -> None:
    tex = TEX.read_text(encoding="utf-8")
    body = tex[tex.index("\\maketitle") + len("\\maketitle"):tex.index("\\end{document}")]
    body = "\n".join(line for line in body.splitlines() if not line.startswith("%"))

    # First pass: number sections, subsections, tables and listings like LaTeX does.
    labels: dict[str, dict[str, str]] = {}
    toc: list[tuple[int, str, str]] = []
    sec = sub = tab = lst = 0
    for m in re.finditer(r"\\(section|subsection|label|artifact|begin\{table\})", body):
        kind = m.group(1)
        if kind == "section":
            sec += 1; sub = 0
            toc.append((1, f"S{sec}", braced(body, m.end())[0]))
        elif kind == "subsection":
            sub += 1
            toc.append((2, f"S{sec}.{sub}", braced(body, m.end())[0]))
        elif kind == "begin{table}":
            tab += 1
            last = {"id": f"table-S{tab}", "num": f"Table S{tab}"}
        elif kind == "artifact":
            lst += 1
        elif kind == "label":
            name = braced(body, m.end())[0]
            labels[name] = last if name.startswith("tab:") else {"id": f"S{sec}", "num": f"Section S{sec}"}

    out: list[str] = []
    sec = sub = lst = 0
    para: list[str] = []

    def flush() -> None:
        text = " ".join(para).strip()
        if text:
            out.append(f"<p>{inline(text, labels)}</p>")
        para.clear()

    lines = body.splitlines()
    k = 0
    while k < len(lines):
        line = lines[k].strip()
        k += 1
        if not line:
            flush()
        elif line in ("\\tableofcontents", "\\clearpage"):
            flush()
        elif line.startswith("\\section{"):
            flush(); sec += 1; sub = 0
            title = braced(line, len("\\section"))[0]
            if sec > 1:
                out.append("</section>")
            out.append(f'<section id="S{sec}"><h2><a class="anchor" href="#S{sec}">S{sec}</a> {inline(title, labels)}</h2>')
        elif line.startswith("\\subsection{"):
            flush(); sub += 1
            title = braced(line, len("\\subsection"))[0]
            out.append(f'<h3 id="S{sec}.{sub}"><a class="anchor" href="#S{sec}.{sub}">S{sec}.{sub}</a> {inline(title, labels)}</h3>')
        elif line.startswith("\\label{"):
            pass
        elif line.startswith("\\begin{table}"):
            flush()
            block = [line]
            while not lines[k].strip().startswith("\\end{table}"):
                block.append(lines[k]); k += 1
            k += 1
            out.append(parse_table("\n".join(block), labels))
        elif line.startswith("\\artifact{"):
            flush(); lst += 1
            path, i = braced(line, len("\\artifact"))
            caption, _ = braced(line, i)
            code = (ROOT / "paper_artifacts" / path).read_text(encoding="utf-8")
            url = f"{REPO}/blob/main/paper_artifacts/{path}"
            out.append(
                f'<figure class="listing" id="listing-S{lst}"><pre><code>{html.escape(code.rstrip())}</code></pre>'
                f"<figcaption><strong>Listing S{lst}.</strong> {inline(caption, labels)} "
                f'File: <a href="{url}"><code>paper_artifacts/{html.escape(path)}</code></a>.</figcaption></figure>')
        else:
            para.append(line)
    flush()
    out.append("</section>")

    intro = out.pop(0)  # the paragraph before S1 describes the document
    nav = ["<ol>"]
    in_sub = False
    for level, num, title in toc:
        link = f'<a href="#{num}"><span>{num}</span> {inline(title, labels)}</a>'
        if level == 1:
            if in_sub:
                nav.append("</ol>")
                in_sub = False
            if len(nav) > 1:
                nav.append("</li>")
            nav.append(f"<li>{link}")
        else:
            if not in_sub:
                nav.append("<ol>")
                in_sub = True
            nav.append(f"<li>{link}</li>")
    nav.append(("</ol>" if in_sub else "") + "</li></ol>")
    nav_html = "".join(nav)

    page = PAGE.format(title=html.escape(TITLE), authors=html.escape(AUTHORS),
                       affiliation=html.escape(AFFILIATION), repo=REPO, site=SITE,
                       intro=intro, nav=nav_html, body="\n".join(out))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {sec} sections, {len(labels)} labels, {lst} listings")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Supplementary Material – Holonic Knowledge Representation for Clinical Evidence</title>
<meta name="description" content="Supplementary Material (Sections S1–S11) of the article {title}.">
<style>
:root {{
  --bg: #ffffff; --fg: #1d1f23; --muted: #5b616b; --line: #d9dce1;
  --accent: #1f4f8a; --code-bg: #f6f7f9; --rule: #8a9099;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #15171a; --fg: #e4e6ea; --muted: #a0a6b0; --line: #33373d;
    --accent: #8db8ee; --code-bg: #1d2024; --rule: #6b717a;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ scroll-padding-top: 1rem; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
a {{ color: var(--accent); }}
code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 0.86em; }}
.layout {{ display: grid; grid-template-columns: minmax(0, 1fr); max-width: 76rem; margin: 0 auto; padding: 0 16px; }}
header {{ padding: 2.5rem 0 1.5rem; border-bottom: 1px solid var(--line); }}
header .kicker {{ margin: 0; color: var(--muted); font-size: .9rem; letter-spacing: .04em; text-transform: uppercase; }}
header h1 {{ margin: .4rem 0 .6rem; font-size: 1.6rem; line-height: 1.3; }}
header .authors {{ margin: 0; }}
header .affil {{ margin: .2rem 0 1rem; color: var(--muted); font-size: .92rem; }}
header .links {{ display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; margin: 0; padding: 0; list-style: none; font-size: .95rem; }}
nav {{ font-size: .92rem; padding: 1.25rem 0; border-bottom: 1px solid var(--line); }}
nav h2 {{ font-size: 1rem; margin: 0 0 .5rem; }}
nav ol {{ list-style: none; margin: 0; padding: 0; }}
nav ol ol {{ padding-left: 2.6rem; }}
nav li {{ margin: .15rem 0; }}
nav a {{ display: grid; grid-template-columns: 2.6rem 1fr; text-decoration: none; color: var(--fg); }}
nav ol ol a {{ grid-template-columns: 3.2rem 1fr; }}
nav a:hover {{ color: var(--accent); text-decoration: underline; }}
nav span {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
main {{ min-width: 0; padding-bottom: 3rem; }}
main > p:first-child {{ margin-top: 1.5rem; }}
section {{ border-top: 1px solid var(--line); margin-top: 2rem; }}
h2 {{ font-size: 1.35rem; margin: 1.5rem 0 .75rem; }}
h3 {{ font-size: 1.08rem; margin: 1.75rem 0 .6rem; }}
a.anchor {{ color: var(--muted); text-decoration: none; margin-right: .35rem; font-variant-numeric: tabular-nums; }}
a.anchor:hover {{ color: var(--accent); }}
.math i {{ font-family: "Times New Roman", Times, serif; font-size: 1.08em; }}
p, figcaption {{ overflow-wrap: anywhere; }}
figure {{ margin: 1.25rem 0; }}
figcaption {{ font-size: .92rem; color: var(--muted); margin: .5rem 0; }}
figcaption strong {{ color: var(--fg); }}
.scroll {{ overflow-x: auto; }}
table {{ border-collapse: collapse; font-size: .92rem; border-top: 1.5px solid var(--rule); border-bottom: 1.5px solid var(--rule); }}
th, td {{ padding: .35rem .75rem; vertical-align: top; }}
thead th {{ border-bottom: 1px solid var(--rule); }}
tr.rule td {{ border-top: 1px solid var(--line); }}
td code, th code {{ font-size: .82rem; word-break: break-all; }}
.listing pre {{ margin: 0; padding: .9rem 1rem; background: var(--code-bg); border: 1px solid var(--line);
  border-radius: 4px; overflow: auto; max-height: 36rem; line-height: 1.45; }}
footer {{ border-top: 1px solid var(--line); padding: 1.25rem 0 2.5rem; color: var(--muted); font-size: .88rem; }}
@media (min-width: 1100px) {{
  .layout {{ grid-template-columns: 18rem minmax(0, 1fr); column-gap: 2.5rem; }}
  header, footer {{ grid-column: 1 / -1; }}
  nav {{ position: sticky; top: 0; align-self: start; max-height: 100vh; overflow-y: auto; border-bottom: 0; }}
}}
</style>
</head>
<body>
<div class="layout">
<header>
<p class="kicker">Supplementary Material</p>
<h1>{title}</h1>
<p class="authors">{authors}</p>
<p class="affil">{affiliation}</p>
<ul class="links">
<li><a href="supplementary_material.pdf">PDF version</a></li>
<li><a href="{repo}">Code and data repository</a></li>
<li><a href="https://atilimkoca.github.io/syz-ontology/">Ontology modules</a></li>
</ul>
</header>
<nav aria-label="Contents"><h2>Contents</h2>{nav}</nav>
<main>
{intro}
{body}
</main>
<footer>
<p>Generated from <code>supplementary/supplementary_material.tex</code> by <code>supplementary/build_web.py</code> in the
<a href="{repo}">repository</a>. Code: MIT Licence. Data, RDF exports, SHACL shapes and other generated artifacts:
CC BY 4.0. The extracted clinical relations are research artifacts and must not be used for clinical decisions.</p>
</footer>
</div>
</body>
</html>
"""

if __name__ == "__main__":
    main()
