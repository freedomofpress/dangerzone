"""Render mermaid code blocks to inline SVG at documentation build time.

Registered in zensical.toml as the pymdownx.superfences formatter for
`mermaid` fences, like this:

```toml
pymdownx.superfences.custom_fences = [
    { name = "mermaid", class = "mermaid-diagram", format = "dev_scripts.docs_mermaid.fence" },
]
```
"""

import hashlib
import re

import mermaidx
from pymdownx.superfences import SuperFencesException

# A linked node (`click NODE "https://..."`) is wrapped in an <a> that carries
# its position, and the label of such a node is a group of <text> at the end of
# the SVG, positioned relatively to the node (hence the x="0").
LINK_RE = re.compile(r'<a [^>]*\btransform="([^"]+)"')
LINK_LABEL_RE = re.compile(
    r'<g data-merman-foreignobject="fallback" class="[^"]*\bclickable\b[^"]*"'
    r'(?=><text x="0" )'
)


def place_link_labels(svg):
    """Move the labels of the linked nodes onto their node.

    merman leaves them in the top-left corner of the diagram: they are emitted
    outside of the link, which is the element that holds the node position.
    They come in the same order as the links, and clicks go through them.
    """
    positions = LINK_RE.findall(svg)
    if len(positions) != len(LINK_LABEL_RE.findall(svg)):
        raise ValueError("cannot match the linked nodes with their labels")
    positions = iter(positions)
    return LINK_LABEL_RE.sub(
        lambda m: f'{m.group(0)} transform="{next(positions)}" pointer-events="none"',
        svg,
    )


def fence(source, language, css_class, options, md, **kwargs):
    """pymdownx.superfences custom fence formatter (see extension docs)."""
    try:
        svg = place_link_labels(mermaidx.render(source, backend="merman").svg())
    except Exception as e:
        raise SuperFencesException(f"mermaid rendering failed: {e}") from e

    uid = "mermaid-" + hashlib.sha256(source.encode()).hexdigest()[:8]
    svg = svg.replace('id="merman', f'id="{uid}').replace("#merman", f"#{uid}")

    return f'<div class="{css_class}">{svg}</div>'
