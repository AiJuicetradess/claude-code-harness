"""Tests for verify_connectors.py (rules R1, R3, R4, R6)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import verify_connectors as vc  # noqa: E402


def svg(body: str) -> str:
    return f'<html><body><svg viewBox="0 0 400 300"><defs><marker id="arrow"><polygon points="0 0, 8 3, 0 6"/></marker></defs>{body}</svg></body></html>'


CLEAN = svg(
    # arrows first
    '<path d="M 100 40 H 192 A 8 8 0 0 1 200 48 V 100" fill="none" stroke="#000" marker-end="url(#arrow)"/>'
    '<line x1="100" y1="60" x2="160" y2="60" stroke="#000"/>'
    '<rect x="120" y="20" width="36" height="12" fill="#fff"/>'  # mask above the y=40 arrow
    # nodes after
    '<rect x="20" y="20" width="80" height="60" fill="#fff" stroke="#000"/>'
    '<rect x="200" y="100" width="80" height="60" fill="#fff" stroke="#000"/>'
)


def rules(findings: list[dict]) -> set[str]:
    return {f["rule"] for f in findings}


def test_clean_diagram_has_no_findings():
    assert vc.check(CLEAN) == []


def test_r1_diagonal_line_fails():
    doc = svg('<line x1="10" y1="10" x2="90" y2="70" stroke="#000"/>')
    assert rules(vc.check(doc)) == {"R1"}


def test_r1_diagonal_path_segment_fails_and_arcs_pass():
    bad = svg('<path d="M 10 10 L 90 70" fill="none" stroke="#000"/>')
    good = svg('<path d="M 10 10 H 82 A 8 8 0 0 1 90 18 V 70" fill="none" stroke="#000"/>')
    assert rules(vc.check(bad)) == {"R1"}
    assert vc.check(good) == []


def test_r1_allow_diagonal_flag_skips_rule():
    doc = svg('<line x1="10" y1="10" x2="90" y2="70" stroke="#000"/>')
    assert vc.check(doc, allow_diagonal=True) == []


def test_r1_ignores_filled_shapes_and_defs():
    doc = svg('<path d="M 10 10 L 90 70 L 10 70 Z" fill="#000"/>')
    assert vc.check(doc) == []


def test_r3_overlapping_horizontal_segments_fail():
    doc = svg(
        '<line x1="10" y1="50" x2="100" y2="50" stroke="#000"/>'
        '<line x1="60" y1="50" x2="200" y2="50" stroke="#000"/>'
    )
    assert rules(vc.check(doc)) == {"R3"}


def test_r3_touching_end_to_end_is_not_overlap():
    doc = svg(
        '<line x1="10" y1="50" x2="100" y2="50" stroke="#000"/>'
        '<line x1="100" y1="50" x2="200" y2="50" stroke="#000"/>'
    )
    # they share an endpoint (R4) but do not overlap (no R3)
    assert rules(vc.check(doc)) == {"R4"}


def test_r4_shared_attach_point_fails():
    doc = svg(
        '<path d="M 100 40 H 200" fill="none" stroke="#000"/>'
        '<path d="M 100 40 V 120" fill="none" stroke="#000"/>'
    )
    assert rules(vc.check(doc)) == {"R4"}


def test_r4_fanned_attach_points_pass():
    doc = svg(
        '<path d="M 100 36 H 200" fill="none" stroke="#000"/>'
        '<path d="M 100 52 H 200" fill="none" stroke="#000"/>'
    )
    assert vc.check(doc) == []


def test_r6_mask_clipped_by_later_node_fails():
    doc = svg(
        '<rect x="90" y="30" width="36" height="12" fill="#fff"/>'  # mask, painted first
        '<rect x="100" y="20" width="80" height="60" fill="#fff"/>'  # node painted later, overlaps mask
    )
    assert rules(vc.check(doc)) == {"R6"}


def test_r6_badge_chip_inside_node_is_legal():
    doc = svg(
        '<rect x="110" y="26" width="28" height="12" fill="none"/>'
        '<rect x="100" y="20" width="80" height="60" fill="#fff"/>'
    )
    assert vc.check(doc) == []


def test_r6_mask_before_earlier_node_is_fine():
    doc = svg(
        '<rect x="100" y="20" width="80" height="60" fill="#fff"/>'  # node first (zone-like)
        '<rect x="90" y="30" width="36" height="12" fill="#fff"/>'  # mask after: stays on top
    )
    assert vc.check(doc) == []


def test_translate_transform_is_applied_for_r4():
    doc = svg(
        '<g transform="translate(50, 0)"><path d="M 50 40 H 150" fill="none" stroke="#000"/></g>'
        '<path d="M 100 40 V 120" fill="none" stroke="#000"/>'
    )
    assert rules(vc.check(doc)) == {"R4"}


def test_rotate_transform_marks_subtree_untracked_for_r4():
    doc = svg(
        '<g transform="rotate(10)"><path d="M 100 40 H 150" fill="none" stroke="#000"/></g>'
        '<path d="M 100 40 V 120" fill="none" stroke="#000"/>'
    )
    assert vc.check(doc) == []


def test_cli_exit_codes_and_json(tmp_path: Path):
    good = tmp_path / "good.html"
    bad = tmp_path / "bad.html"
    good.write_text(CLEAN, encoding="utf-8")
    bad.write_text(svg('<line x1="10" y1="10" x2="90" y2="70" stroke="#000"/>'), encoding="utf-8")
    ok = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_connectors.py"), str(good)], capture_output=True, text=True)
    assert ok.returncode == 0 and ok.stdout.startswith("OK")
    fail = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_connectors.py"), str(bad), "--json"], capture_output=True, text=True)
    assert fail.returncode == 1
    data = json.loads(fail.stdout)
    assert data["ok"] is False and data["results"][0]["findings"][0]["rule"] == "R1"
    assert fail.stdout.isascii()


def test_missing_file_exits_2(tmp_path: Path):
    r = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_connectors.py"), str(tmp_path / "nope.svg")], capture_output=True, text=True)
    assert r.returncode == 2


@pytest.mark.parametrize("d", ["M 0 0 h 50 v 50", "m 10 10 l 0 40", "M 10 10 Q 20 20 30 10", "M 10 10 C 1 2 3 4 50 10"])
def test_path_parser_handles_relative_and_curve_commands(d: str):
    doc = svg(f'<path d="{d}" fill="none" stroke="#000"/>')
    assert vc.check(doc) == []


def _run_with_timeout(fn, seconds: float = 3.0):
    """Run fn on a daemon thread; fail instead of hanging pytest if the parser loops."""
    import threading

    box: dict = {}
    t = threading.Thread(target=lambda: box.setdefault("v", fn()), daemon=True)
    t.start()
    t.join(seconds)
    assert not t.is_alive(), "parser did not terminate"
    return box["v"]


def test_number_after_z_terminates_parser():
    segs, curves, start, end = _run_with_timeout(lambda: vc.parse_path("M 0 0 L 10 0 Z 5 5", 0, 0))
    assert segs == [((0.0, 0.0), (10.0, 0.0)), ((10.0, 0.0), (0.0, 0.0))]
    assert start == (0.0, 0.0)


def test_number_after_z_in_document_does_not_hang():
    doc = svg('<path d="M 10 10 H 50 Z 5" fill="none" stroke="#000"/>')
    assert _run_with_timeout(lambda: vc.check(doc)) == []


@pytest.mark.parametrize("compact", [
    "M 100 40 H 192 A8 8 0 01 200 48 V 100",     # flags glued together
    "M 100 40 H 192 A8 8 0 01200 48 V 100",      # flags glued to the x coordinate
    "M 100 40 H 192 A8,8,0,0,1,200,48 V 100",    # comma separated
])
def test_compact_arc_flags_parse_like_spaced_arcs(compact: str):
    spaced = vc.parse_path("M 100 40 H 192 A 8 8 0 0 1 200 48 V 100", 0, 0)
    assert vc.parse_path(compact, 0, 0) == spaced
    assert spaced[3] == (200.0, 100.0)  # the V after the arc was consumed, not dropped


def test_style_fill_marks_path_as_shape_not_connector():
    doc = svg('<path d="M 10 10 L 90 70 L 10 70 Z" style="stroke:none; fill: #000"/>')
    assert vc.check(doc) == []


def test_legend_axis_and_icon_subtrees_are_not_connectors():
    doc = svg(
        '<path d="M 100 40 H 200" fill="none" stroke="#000"/>'
        # legend hairline touching the connector start would be R4
        '<g class="legend"><line x1="100" y1="40" x2="120" y2="40" stroke="#000"/></g>'
        # axis tick starting on the connector would be R4
        '<g class="chart-axis"><line x1="100" y1="40" x2="100" y2="46" stroke="#000"/></g>'
        # diagonal icon stroke would be R1
        '<svg class="lucide lucide-check" viewBox="0 0 24 24"><path d="M 5 12 L 10 17" fill="none" stroke="#000"/></svg>'
        # a card divider ending on the connector end would be R4
        '<line class="divider" x1="200" y1="10" x2="200" y2="40" stroke="#000"/>'
    )
    assert vc.check(doc) == []
    assert vc.summarize(doc)["connectors"] == 1


@pytest.mark.parametrize("cls", ["diagram-grid", "grid-layout", "iconic-card", "ticker", "sticky-header", "silicon", "taxis", "legendary"])
def test_decorative_class_needs_a_whole_token(cls: str):
    # a substring match would hide the whole diagram behind a layout wrapper
    doc = svg(f'<g class="{cls}"><line x1="10" y1="10" x2="90" y2="70" stroke="#000"/></g>')
    assert rules(vc.check(doc)) == {"R1"}


@pytest.mark.parametrize("cls", ["legend", "chart-legend", "x-axis", "axes", "icon", "lucide lucide-check", "card-divider",
                                 "ticks", "tick-major", "gridlines", "grid-line"])
def test_decorative_class_tokens_are_skipped_and_counted(cls: str):
    doc = svg(f'<g class="{cls}"><line x1="10" y1="10" x2="90" y2="70" stroke="#000"/></g>')
    assert vc.check(doc) == []
    assert vc.summarize(doc)["decorative_skipped"] == 1


def test_ok_line_reports_decorative_skips(tmp_path: Path):
    f = tmp_path / "d.html"
    f.write_text(svg('<g class="legend"><line x1="10" y1="10" x2="90" y2="70" stroke="#000"/></g>'), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_connectors.py"), str(f)], capture_output=True, text=True)
    assert r.returncode == 0 and "1 decorative element(s) skipped" in r.stdout


@pytest.mark.parametrize("body", [
    '<line x1="1e999" y1="0" x2="10" y2="10" stroke="#000"/>',
    '<path d="M 1e999 0 L 10 10" fill="none" stroke="#000"/>',
])
def test_non_finite_coordinates_do_not_crash(body: str):
    assert rules(vc.check(svg(body))) == {"R1"}


@pytest.mark.parametrize("body,tol", [
    ('<line x1="1e308" y1="0" x2="10" y2="10" stroke="#000"/>', 0.5),  # v / cell overflows to inf
    ('<line x1="1e300" y1="0" x2="10" y2="10" stroke="#000"/>', 0.0),
])
def test_huge_finite_coordinates_do_not_crash(body: str, tol: float):
    assert rules(vc.check(svg(body), tol=tol)) == {"R1"}


def test_bare_grid_class_is_decorative_but_grid_prefixes_are_not():
    grid = "".join(f'<line x1="20" y1="{40 + 20 * k}" x2="200" y2="{40 + 20 * k}" stroke="#eee"/>' for k in range(5))
    doc = svg(f'<g class="grid">{grid}</g><line x1="20" y1="40" x2="20" y2="200" stroke="#000"/>')
    assert vc.check(doc) == []  # gridline endpoints touching the axis are not R4
    assert vc.summarize(doc)["decorative_skipped"] == 5
    wrapped = svg('<g class="grid-layout"><line x1="10" y1="10" x2="90" y2="70" stroke="#000"/></g>')
    assert rules(vc.check(wrapped)) == {"R1"}


def test_non_ascii_file_name_prints_under_cp1252(tmp_path: Path):
    import os

    f = tmp_path / ("diagram-" + chr(0x56F3) + ".html")
    f.write_text(CLEAN, encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    r = subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_connectors.py"), str(f)],
                       capture_output=True, env=env, encoding="cp1252", errors="replace")
    assert r.returncode == 0 and r.stdout.startswith("OK"), r.stderr


def test_r1_is_skipped_inside_rotated_subtrees():
    # local coordinates are meaningless under rotate(): a locally diagonal line may be axis-aligned on screen
    doc = svg('<g transform="rotate(45)"><line x1="0" y1="0" x2="50" y2="50" stroke="#000"/></g>')
    assert vc.check(doc) == []


def test_r3_and_r4_still_match_across_tolerance_cell_boundaries():
    # y=50.4 and y=50.6 fall in different 0.5px cells but are within tolerance
    doc = svg(
        '<line x1="10" y1="50.4" x2="100" y2="50.4" stroke="#000"/>'
        '<line x1="60" y1="50.6" x2="200" y2="50.6" stroke="#000"/>'
    )
    assert rules(vc.check(doc)) == {"R3"}
    doc2 = svg(
        '<path d="M 100.4 40.4 H 200" fill="none" stroke="#000"/>'
        '<path d="M 100.6 40.6 V 120" fill="none" stroke="#000"/>'
    )
    assert rules(vc.check(doc2)) == {"R4"}


def test_many_connectors_check_quickly():
    import time

    body = "".join(
        f'<line x1="{10 + (k % 50) * 30}" y1="{10 + (k // 50) * 20}" x2="{25 + (k % 50) * 30}" y2="{10 + (k // 50) * 20}" stroke="#000"/>'
        for k in range(3000)
    )
    t0 = time.perf_counter()
    assert vc.check(svg(body)) == []
    assert time.perf_counter() - t0 < 2.0
