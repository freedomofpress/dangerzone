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

import mermaidx
from pymdownx.superfences import SuperFencesException


def fence(source, language, css_class, options, md, **kwargs):
    """pymdownx.superfences custom fence formatter (see extension docs)."""
    try:
        svg = mermaidx.render(source, backend="merman").svg()
    except Exception as e:
        raise SuperFencesException(f"mermaid rendering failed: {e}") from e

    uid = "mermaid-" + hashlib.sha256(source.encode()).hexdigest()[:8]
    svg = svg.replace('id="merman', f'id="{uid}').replace("#merman", f"#{uid}")

    return f'<div class="{css_class}">{svg}</div>'
