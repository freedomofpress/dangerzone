#!/usr/bin/env python3
# Generate site/dangerzone-docs.pdf from the built site.

import datetime
import re
import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import tomllib
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
OUTPUT = SITE / "dangerzone-docs.pdf"
CONFIG = tomllib.loads((REPO / "zensical.toml").read_text())["project"]
VERSION = (REPO / "share" / "version.txt").read_text().strip()

EXCLUDED_PAGES = {
    "reference/license.md",
}

MERMAID_JS = REPO / "docs" / "javascripts" / "vendor" / "mermaid.min.js"

MERMAID_INIT = (
    'mermaid.initialize({startOnLoad: true, theme: "neutral",'
    " htmlLabels: false, flowchart: {htmlLabels: false}});"
)

# Literal emoji need an explicit emoji font, but that font must not end up in
# the regular font fallback chain: Noto Color Emoji also contains digit glyphs
# (for keycap sequences) and would hijack every number in the text. So emoji
# get wrapped in their own span instead.
EMOJI_RE = re.compile("[\u2600-\u27bf\u2b00-\u2bff\U0001f000-\U0001faff]\ufe0f?")


def md_to_url(md_path: str) -> str:
    """Map a nav entry ("how-to/install/index.md") to its site URL path."""
    path = re.sub(r"(^|/)index$", "", md_path.removesuffix(".md")).strip("/")
    return path + "/" if path else ""


def walk_nav(nav: list, breadcrumbs: tuple = ()):
    """Yield (breadcrumbs, title, md_path) for every page, in nav order."""
    for item in nav:
        ((title, value),) = item.items() if isinstance(item, dict) else [(item, item)]
        if isinstance(value, list):
            yield from walk_nav(value, breadcrumbs + (title,))
        else:
            yield breadcrumbs, title, value


def extract_article(url: str, slug: str, url_slugs: dict) -> BeautifulSoup:
    page_file = SITE / url / "index.html"
    soup = BeautifulSoup(page_file.read_text(), "html.parser")
    article = soup.find("article")
    if article is None:
        raise SystemExit(f"no <article> found in {page_file}")

    # Drop site chrome that makes no sense on paper: the pilcrow anchors
    # after headings and the edit / view-source icons.
    for node in article.select("a.headerlink, .md-content__button"):
        node.decompose()

    # Prefix ids so the same anchor can exist on several pages.
    for node in article.find_all(id=True):
        node["id"] = f"{slug}--{node['id']}"
    article["id"] = slug

    # Rewrite internal links to in-document anchors; keep external ones.
    for a in article.find_all("a", href=True):
        parsed = urlparse(a["href"])
        if parsed.scheme:
            continue
        if not parsed.path:  # same-page anchor
            a["href"] = f"#{slug}--{parsed.fragment}"
            continue
        target = urljoin("/" + url, parsed.path).strip("/")
        target = target + "/" if target else ""
        if target in url_slugs:
            fragment = f"--{parsed.fragment}" if parsed.fragment else ""
            a["href"] = f"#{url_slugs[target]}{fragment}"
        else:  # a file download or an unknown page: point at the live site
            a["href"] = urljoin(CONFIG["site_url"] + url, a["href"])

    # Point images at the local files so WeasyPrint can embed them.
    for img in article.find_all("img", src=True):
        if not urlparse(img["src"]).scheme:
            img["src"] = str((SITE / url / img["src"]).resolve())

    # Content tabs: turn each tab pane into a labelled block, stacked.
    for tab_set in article.select(".tabbed-set"):
        replacement = soup.new_tag("div", attrs={"class": "print-tabs"})
        for label, block in zip(
            tab_set.select(".tabbed-labels > label"),
            tab_set.select(".tabbed-content > .tabbed-block"),
        ):
            caption = soup.new_tag("p", attrs={"class": "print-tab-label"})
            caption.string = label.get_text(strip=True)
            block["class"] = ["print-tab-block"]
            replacement.append(caption)
            replacement.append(block)
        tab_set.replace_with(replacement)

    # Collapsible blocks: always open on paper.
    for details in article.find_all("details"):
        details["open"] = "open"

    return article


def render_mermaid_diagrams(articles: list) -> None:
    """Replace every mermaid code block with an SVG of the diagram.

    Mermaid can only be laid out by a browser DOM, and WeasyPrint executes no
    JavaScript, so all the sources are rendered in a single headless Chromium
    run and the resulting SVGs take the place of the code blocks.
    """
    nodes = [node for article in articles for node in article.select("pre.mermaid")]
    if not nodes:
        return
    browsers = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
    browser = next(filter(None, map(shutil.which, browsers)), None)
    if browser is None:
        raise SystemExit("rendering the mermaid diagrams needs Chromium or Chrome")
    if not MERMAID_JS.exists():
        raise SystemExit(f"{MERMAID_JS} is missing, run `make docs-vendor` first")

    # Without HTML labels, mermaid renders every tag other than <br> as
    # literal text; the emphasis some labels carry is cosmetic, drop it.
    blocks = "\n".join(
        f'<pre class="mermaid">'
        f"{escape(re.sub(r'</?(i|b|em|strong)>', '', node.get_text()))}</pre>"
        for node in nodes
    )
    page = (
        '<!doctype html><meta charset="utf-8"><body>'
        f'{blocks}<script src="{MERMAID_JS.as_uri()}"></script>'
        f"<script>{MERMAID_INIT}</script>"
    )
    with tempfile.TemporaryDirectory() as tmp:
        page_file = Path(tmp) / "mermaid.html"
        page_file.write_text(page)
        dump = subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--virtual-time-budget=15000",
                "--dump-dom",
                page_file.as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    svgs = BeautifulSoup(dump, "html.parser").select("pre.mermaid > svg")
    if len(svgs) != len(nodes):
        raise SystemExit(f"mermaid rendered {len(svgs)} of {len(nodes)} diagrams")
    for node, svg in zip(nodes, svgs):
        # An explicit width keeps the size WeasyPrint gives the SVG in step
        # with the coordinates mermaid computed; the viewBox keeps the aspect
        # ratio. 660px is roughly the printable width of the page.
        viewbox = (svg.get("viewBox") or "0 0 660 400").split()
        svg["width"] = f"{min(float(viewbox[2]), 660):.0f}px"
        svg["class"] = (svg.get("class") or []) + ["mermaid-diagram"]
        del svg["height"]
        node.replace_with(svg.extract())


def build_html() -> str:
    pages = [
        (crumbs, title, md_to_url(md))
        for crumbs, title, md in walk_nav(CONFIG["nav"])
        if md not in EXCLUDED_PAGES
    ]
    url_slugs = {
        url: "page--" + (url.strip("/").replace("/", "-") or "home")
        for _, _, url in pages
    }
    articles = [extract_article(url, url_slugs[url], url_slugs) for _, _, url in pages]
    render_mermaid_diagrams(articles)

    body = []
    toc = []
    parts: list[str] = []
    for (crumbs, title, url), article in zip(pages, articles):
        part = crumbs[0] if crumbs else None
        if part and part not in parts:
            parts.append(part)
            part_id = f"part-{len(parts)}"
            body.append(f'<h1 class="part-title" id="{part_id}">{part}</h1>')
            toc.append(f'<li class="toc-part"><a href="#{part_id}">{part}</a></li>')
        toc.append(f'<li class="toc-page"><a href="#{url_slugs[url]}">{title}</a></li>')
        # Wrap literal emoji in a span carrying the emoji font (see EMOJI_RE).
        body.append(EMOJI_RE.sub(r'<span class="emoji">\g<0></span>', str(article)))

    logo = (SITE / "assets" / "logo.png").resolve()
    date = datetime.datetime.now(tz=datetime.timezone.utc).date().isoformat()
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{CONFIG["site_name"]} documentation</title></head>
<body>
<section class="cover">
  <img src="{logo}" alt="" class="cover-logo">
  <h1 class="cover-title">{CONFIG["site_name"]}</h1>
  <p class="cover-subtitle">{CONFIG["site_description"]}</p>
  <p class="cover-meta">Version {VERSION} &mdash; {date}<br>{CONFIG["site_url"]}</p>
</section>
<section class="toc">
  <h1>Contents</h1>
  <ul>{"".join(toc)}</ul>
</section>
{"".join(body)}
</body></html>"""


STYLE = """
@page {
    size: A4;
    margin: 20mm 18mm 22mm 18mm;
    @bottom-center { content: counter(page); font-size: 9pt; color: #666; }
    @top-right { content: string(chapter); font-size: 8pt; color: #999; }
}
@page :first { @bottom-center { content: none; } @top-right { content: none; } }
html { font-family: sans-serif; font-size: 10pt; line-height: 1.5; }
.emoji { font-family: "Noto Color Emoji"; }
h1, h2, h3, h4 { line-height: 1.25; }

/* PDF outline: parts > pages > sections */
h1.part-title { bookmark-level: 1; }
article h1 { bookmark-level: 2; string-set: chapter content(); }
article h2 { bookmark-level: 3; }
article h3 { bookmark-level: 4; }
article h4 { bookmark-level: none; }

.cover { page-break-after: always; text-align: center; padding-top: 45mm; }
.cover-logo { width: 40mm; }
.cover-title { font-size: 28pt; margin: 10mm 0 4mm; }
.cover-subtitle { font-size: 12pt; color: #444; }
.cover-meta { margin-top: 30mm; color: #666; }

.toc { page-break-after: always; }
.toc ul { list-style: none; padding: 0; }
.toc a { text-decoration: none; color: inherit; }
.toc li a::after { content: leader('.') target-counter(attr(href), page); }
.toc-part { font-weight: bold; margin-top: 4mm; }
.toc-page { margin-left: 6mm; }

h1.part-title {
    page-break-before: always; font-size: 24pt;
    padding-top: 60mm; text-align: center;
}
article { page-break-before: always; }
article h1 { font-size: 18pt; border-bottom: 1pt solid #ccc; padding-bottom: 2mm; }

a { color: #b71c1c; }
img { max-width: 100%; }
hr { border: none; border-top: 0.5pt solid #ccc; margin: 5mm 0; }

/* Grids: side-by-side content (e.g. the home page screenshots). */
.grid { display: flex; gap: 4mm; }
.grid > * { flex: 1; min-width: 0; }

/* Card grids: bordered boxes, two per row like the site's tiles. */
.grid.cards > ul {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-wrap: wrap; gap: 3mm;
}
.grid.cards > ul > li {
    flex: 1 1 42%; box-sizing: border-box;
    border: 0.5pt solid #bbb; padding: 3mm 4mm;
    page-break-inside: avoid;
}
.grid.cards hr { margin: 2mm 0; }
/* Inline icons and emoji (span.twemoji > svg for icons, img.twemoji for
   emoji) carry no size attributes; keep them text-sized. */
svg:not([width]) { width: 1.1em; height: 1.1em; }
.twemoji { display: inline-block; vertical-align: text-bottom; }
.twemoji, .twemoji svg { width: 1.1em; height: 1.1em; }

svg.mermaid-diagram {
    display: block; margin: 4mm auto;
    max-width: 100%; page-break-inside: avoid;
}

pre {
    background: #f5f5f5; padding: 3mm; font-size: 8.5pt;
    white-space: pre-wrap; overflow-wrap: break-word;
}
code { font-family: monospace; font-size: 0.9em; background: #f5f5f5; }
table { border-collapse: collapse; font-size: 9pt; }
th, td { border: 0.5pt solid #bbb; padding: 1.5mm 2.5mm; text-align: left; }
blockquote { border-left: 2pt solid #ccc; margin-left: 0; padding-left: 4mm; color: #444; }

.admonition, details {
    border: 0.5pt solid #bbb; border-left: 2pt solid #b71c1c;
    padding: 2mm 3mm; margin: 3mm 0; page-break-inside: avoid;
}
.admonition-title, summary { font-weight: bold; margin: 0 0 1mm; }

.print-tab-label {
    font-weight: bold; background: #eee; padding: 1mm 3mm; margin: 3mm 0 0;
    border-left: 2pt solid #b71c1c;
}
.print-tab-block { border-left: 0.5pt solid #ccc; padding: 1mm 3mm; margin: 0 0 2mm; }

/* Task lists: hide the checkbox form widget and draw a glyph instead. */
.task-list-item { list-style-type: none; text-indent: -6mm; padding-left: 6mm; }
/* The hanging indent is inherited: without a reset, the first line of any
   block nested in a task item is pulled 6mm to the left. */
.task-list-item div, .task-list-item pre, .task-list-item details,
.task-list-item blockquote, .task-list-item table { text-indent: 0; }
.task-list-item input { display: none; }
.task-list-indicator::before { content: "☐"; margin-right: 2mm; }
input[checked] + .task-list-indicator::before { content: "☑"; }
"""


def main() -> None:
    from pygments.formatters import HtmlFormatter
    from weasyprint import CSS, HTML

    css = STYLE + HtmlFormatter(style="default").get_style_defs(".highlight")
    HTML(string=build_html(), base_url=str(SITE)).write_pdf(
        OUTPUT, stylesheets=[CSS(string=css)]
    )
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
