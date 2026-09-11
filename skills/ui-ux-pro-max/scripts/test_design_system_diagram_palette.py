"""MASTER.md must carry a Diagram & Illustration Palette derived from the UI roles."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_system as ds  # noqa: E402


def test_master_md_has_diagram_palette_section():
    system = {
        "project_name": "T",
        "category": "Test",
        "colors": {"primary": "#111111", "secondary": "#222222", "cta": "#333333", "background": "#444444", "text": "#555555"},
        "typography": {"heading": "A", "body": "B"},
    }
    md = ds.format_master_md(system)
    assert "### Diagram & Illustration Palette" in md
    section = md.split("### Diagram & Illustration Palette", 1)[1].split("### Typography", 1)[0]
    assert "| `paper` | `#444444` |" in section
    assert "| `ink` | `#555555` |" in section
    assert "| `accent` | `#333333` |" in section
    assert "| `muted` | `#222222` |" in section
    assert "at most THREE chromatic roles" in section
    assert "No box-shadow inside diagrams" in section
    # section sits between the palette and typography, inside Global Rules
    assert md.index("### Color Palette") < md.index("### Diagram & Illustration Palette") < md.index("### Typography")
