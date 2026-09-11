#!/usr/bin/env python3
"""Verify hand-authored SVG connector geometry.

Deterministic checks for the mandatory connector rules that can be measured
from the markup (rules R1, R3, R4, R6 of the diagram-geometry skill). Rules
R2 (label gap) and R5 (transit behind non-endpoint boxes) remain prose.

  R1  No diagonal straight segments between nodes. Every straight segment of a
      connector must be horizontal or vertical; bends are arcs/curves.
  R3  No two connectors share a stroke path: axis-aligned segments from
      different connectors must not overlap on the same line.
  R4  No two connectors share an attach point: start/end points of different
      connectors must not coincide.
  R6  A label mask rect must not be clipped by a node rect painted after it.
      (Ported from cathrynlavery/diagram-design scripts/verify-geometry.py, MIT.)

Scope: <line>, <path>, <polyline> elements outside <defs>/<marker>/<pattern>/
<symbol>/<clipPath>, and outside subtrees whose class names mark chart furniture
or icons (legend, axis, icon, lucide, divider, tick, gridline as whole class
tokens or hyphenated parts, plus the exact token grid). A <path> whose fill
attribute or style fill is not none is a shape, not a connector. Translate()
transforms on ancestors are applied; any other transform (rotate, scale, skew,
matrix) marks the subtree untracked and its elements are skipped by every rule,
because local coordinates say nothing about on-screen direction or position.

Usage:
    python verify_connectors.py FILE [FILE ...] [--json] [--allow-diagonal] [--tol 0.5]

Exit code 0 when every file passes, 1 when any finding is reported, 2 on usage
or read errors. Output is ASCII only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

SKIP_TAGS = {"defs", "marker", "pattern", "symbol", "clippath", "mask", "lineargradient", "radialgradient"}
CONNECTOR_TAGS = {"line", "path", "polyline"}

NODE_MIN_W, NODE_MIN_H = 60.0, 40.0
MASK_W_RANGE = (20.0, 200.0)
MASK_H_RANGE = (8.0, 16.0)

_NUM = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?"
_PATH_TOKEN = re.compile(r"[MmLlHhVvAaQqCcSsTtZz]|" + _NUM)
_TRANSLATE = re.compile(r"translate\(\s*(" + _NUM + r")\s*[, ]?\s*(" + _NUM + r")?\s*\)")
_TRANSFORM_FN = re.compile(r"([a-zA-Z]+)\s*\(")
# Subtrees whose class names mark chart furniture or icons: their strokes are
# not connectors (legend hairlines, axis ticks, card dividers, Lucide icons).
# Matched on whole class tokens (and their hyphen/underscore parts) so a layout
# wrapper such as class="diagram-grid" or "iconic-card" cannot hide a diagram.
_DECOR_WORDS = {"legend", "legends", "axis", "axes", "icon", "icons", "lucide", "divider", "dividers",
                "tick", "ticks", "gridline", "gridlines"}
_DECOR_EXACT = {"grid"}  # only as the whole token: class="grid" yes, "grid-layout" / "diagram-grid" no
_STYLE_FILL = re.compile(r"(?:^|;)\s*fill\s*:\s*([^;]+)", re.IGNORECASE)


def _is_decorative(class_attr: str | None) -> bool:
    for token in (class_attr or "").lower().split():
        if token in _DECOR_EXACT:
            return True
        parts = [p for p in re.split(r"[-_]", token) if p]
        if any(p in _DECOR_WORDS for p in parts) or "".join(parts) in _DECOR_WORDS:
            return True
    return False

Point = tuple[float, float]
Segment = tuple[Point, Point]


@dataclass
class Connector:
    label: str
    order: int
    segments: list[Segment] = field(default_factory=list)
    curves: int = 0
    start: Point | None = None
    end: Point | None = None
    untracked: bool = False


@dataclass
class RectBox:
    label: str
    order: int
    x: float
    y: float
    w: float
    h: float
    untracked: bool = False

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h


def _f(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    m = re.match(r"\s*(" + _NUM + ")", value)
    return float(m.group(1)) if m else default


def parse_transform(value: str | None) -> tuple[float, float, bool]:
    """Return (dx, dy, untracked). Only translate() is tracked."""
    if not value:
        return 0.0, 0.0, False
    dx = dy = 0.0
    untracked = False
    for fn in _TRANSFORM_FN.findall(value):
        if fn.lower() != "translate":
            untracked = True
    for m in _TRANSLATE.finditer(value):
        dx += float(m.group(1))
        dy += float(m.group(2)) if m.group(2) is not None else 0.0
    return dx, dy, untracked


def parse_path(d: str, dx: float, dy: float) -> tuple[list[Segment], int, Point | None, Point | None]:
    """Walk a path's d attribute. Returns (straight segments, curve count, start, end)."""
    tokens = _PATH_TOKEN.findall(d)
    segments: list[Segment] = []
    curves = 0
    cp: Point | None = None
    sp: Point | None = None
    first: Point | None = None
    cmd = None
    i = 0
    argc = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "A": 7, "Q": 4, "S": 4, "C": 6, "Z": 0}

    def nums(n: int) -> list[float] | None:
        nonlocal i
        if i + n > len(tokens):
            return None
        vals = []
        for k in range(n):
            tok = tokens[i + k]
            if tok[0].isalpha():
                return None
            vals.append(float(tok))
        i += n
        return vals

    def flag() -> int | None:
        """Consume one arc flag. Flags are single characters, and minifiers glue
        them to each other and to the next coordinate ("A8 8 0 01200 48")."""
        nonlocal i
        if i >= len(tokens) or tokens[i][0] not in "01":
            return None
        tok = tokens[i]
        if len(tok) > 1:
            tokens[i] = tok[1:]  # push the remainder back for the next consumer
        else:
            i += 1
        return int(tok[0])

    while i < len(tokens):
        tok = tokens[i]
        if tok[0].isalpha():
            cmd = tok
            i += 1
            if cmd in "Zz":
                if cp is not None and sp is not None and cp != sp:
                    segments.append((cp, sp))
                    cp = sp
                continue
        elif cmd is None or cmd in "Zz":
            break  # a number before any command, or after Z, is malformed: stop instead of looping
        else:
            # implicit repeat: after M comes L, after m comes l
            if cmd == "M":
                cmd = "L"
            elif cmd == "m":
                cmd = "l"
        upper = cmd.upper()
        if upper == "A":
            head = nums(3)
            f1 = flag() if head is not None else None
            f2 = flag() if f1 is not None else None
            tail = nums(2) if f2 is not None else None
            if tail is None:
                break
            vals = head + [float(f1), float(f2)] + tail
        else:
            n = argc.get(upper)
            if n is None:
                break
            vals = nums(n)
            if vals is None:
                break
        rel = cmd.islower() and cp is not None
        ox, oy = (cp if rel else (0.0, 0.0))
        if upper == "M":
            pt = (vals[0] + ox, vals[1] + oy) if rel else (vals[0] + dx, vals[1] + dy)
            cp = pt
            sp = pt
            if first is None:
                first = pt
        elif upper == "L" or upper == "T":
            pt = (vals[0] + ox, vals[1] + oy) if rel else (vals[0] + dx, vals[1] + dy)
            if cp is not None:
                if upper == "L":
                    segments.append((cp, pt))
                else:
                    curves += 1
            cp = pt
        elif upper == "H":
            x = vals[0] + ox if rel else vals[0] + dx
            if cp is not None:
                pt = (x, cp[1])
                segments.append((cp, pt))
                cp = pt
        elif upper == "V":
            y = vals[0] + oy if rel else vals[0] + dy
            if cp is not None:
                pt = (cp[0], y)
                segments.append((cp, pt))
                cp = pt
        elif upper in ("A", "Q", "S", "C"):
            ex, ey = vals[-2], vals[-1]
            pt = (ex + ox, ey + oy) if rel else (ex + dx, ey + dy)
            curves += 1
            cp = pt
    return segments, curves, first, cp


def _fill_of(a: dict) -> str:
    """Effective fill: an inline style wins over the presentation attribute."""
    m = _STYLE_FILL.search(a.get("style") or "")
    if m:
        return m.group(1).strip().lower()
    return (a.get("fill") or "none").strip().lower()


class SvgScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, float, float, bool, bool]] = []  # (tag, dx, dy, untracked, decorative)
        self.skip_depth = 0
        self.order = 0
        self.connectors: list[Connector] = []
        self.rects: list[RectBox] = []
        self.decorative_skipped = 0  # lines/paths/rects ignored inside decorative subtrees

    def _ctx(self) -> tuple[float, float, bool, bool]:
        if self.stack:
            _, dx, dy, un, dec = self.stack[-1]
            return dx, dy, un, dec
        return 0.0, 0.0, False, False

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v for k, v in attrs}
        pdx, pdy, pun, pdec = self._ctx()
        tdx, tdy, tun = parse_transform(a.get("transform"))
        dx, dy, un = pdx + tdx, pdy + tdy, pun or tun
        dec = pdec or _is_decorative(a.get("class"))
        self.stack.append((tag, dx, dy, un, dec))
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        if self.skip_depth or dec:
            if dec and not self.skip_depth and (tag == "rect" or tag in CONNECTOR_TAGS):
                self.decorative_skipped += 1  # surfaced in the summary so a vacuous pass is visible
            return  # chart furniture and icons are neither connectors nor nodes
        self.order += 1
        label = f"<{tag}" + (f' id="{a["id"]}"' if a.get("id") else "") + f"> #{self.order}"
        if tag == "rect":
            w, h = _f(a.get("width")), _f(a.get("height"))
            if w > 0 and h > 0:
                self.rects.append(RectBox(label, self.order, _f(a.get("x")) + dx, _f(a.get("y")) + dy, w, h, un))
            return
        if tag not in CONNECTOR_TAGS:
            return
        if tag == "path" and _fill_of(a) not in ("none", "transparent"):
            return  # filled shapes are not connectors
        c = Connector(label, self.order, untracked=un)
        if tag == "line":
            p1 = (_f(a.get("x1")) + dx, _f(a.get("y1")) + dy)
            p2 = (_f(a.get("x2")) + dx, _f(a.get("y2")) + dy)
            c.segments = [(p1, p2)]
            c.start, c.end = p1, p2
        elif tag == "polyline":
            pts = [float(v) for v in re.findall(_NUM, a.get("points") or "")]
            coords = [(pts[k] + dx, pts[k + 1] + dy) for k in range(0, len(pts) - 1, 2)]
            c.segments = [(coords[k], coords[k + 1]) for k in range(len(coords) - 1)]
            if coords:
                c.start, c.end = coords[0], coords[-1]
        else:
            segs, curves, start, end = parse_path(a.get("d") or "", dx, dy)
            c.segments, c.curves, c.start, c.end = segs, curves, start, end
        if c.segments or c.curves:
            self.connectors.append(c)

    def handle_endtag(self, tag: str) -> None:
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][0] == tag:
                removed = self.stack[idx:]
                del self.stack[idx:]
                self.skip_depth -= sum(1 for t in removed if t[0] in SKIP_TAGS)
                if self.skip_depth < 0:
                    self.skip_depth = 0
                return


def _same(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    lo = max(min(a1, a2), min(b1, b2))
    hi = min(max(a1, a2), max(b1, b2))
    return hi - lo


def check(source: str, tol: float = 0.5, allow_diagonal: bool = False) -> list[dict]:
    scan = SvgScan()
    scan.feed(source)
    findings: list[dict] = []
    tracked = [c for c in scan.connectors if not c.untracked]
    cell = tol if tol > 0 else 1e-9  # spatial hash cell; neighbouring cells cover the tolerance band

    # R1 diagonal straight segments
    if not allow_diagonal:
        for c in tracked:
            for (x1, y1), (x2, y2) in c.segments:
                if abs(x1 - x2) > tol and abs(y1 - y2) > tol:
                    findings.append({
                        "rule": "R1", "element": c.label,
                        "detail": f"diagonal segment ({x1:g},{y1:g}) -> ({x2:g},{y2:g}); use an orthogonal elbow",
                    })
                    break

    # R3 overlapping axis-aligned segments between different connectors
    axis_segs: list[tuple[str, float, float, float, Connector]] = []  # (axis, coord, lo, hi, connector)
    for c in tracked:
        for (x1, y1), (x2, y2) in c.segments:
            if abs(y1 - y2) <= tol and abs(x1 - x2) > tol:
                axis_segs.append(("h", (y1 + y2) / 2, min(x1, x2), max(x1, x2), c))
            elif abs(x1 - x2) <= tol and abs(y1 - y2) > tol:
                axis_segs.append(("v", (x1 + x2) / 2, min(y1, y2), max(y1, y2), c))
    def _cell(v: float) -> int:
        q = v / cell  # inf/nan input ("1e999"), or the division itself overflowing ("1e308" / 0.5), must not raise
        return math.floor(q) if math.isfinite(q) else 0

    by_line: dict[tuple[str, int], list[int]] = {}
    for idx, (ax, co, _lo, _hi, _c) in enumerate(axis_segs):
        by_line.setdefault((ax, _cell(co)), []).append(idx)
    reported: set[tuple[int, int]] = set()
    for i, (ax, co, lo, hi, ca) in enumerate(axis_segs):
        k = _cell(co)
        for j in sorted(j for d in (-1, 0, 1) for j in by_line.get((ax, k + d), ()) if j > i):
            _ay, cy, lo2, hi2, cb = axis_segs[j]
            if ca is cb or not _same(co, cy, tol):
                continue
            ov = _overlap_len(lo, hi, lo2, hi2)
            if ov > tol:
                key = (min(ca.order, cb.order), max(ca.order, cb.order))
                if key in reported:
                    continue
                reported.add(key)
                findings.append({
                    "rule": "R3", "element": ca.label,
                    "detail": f"shares a {'horizontal' if ax == 'h' else 'vertical'} stroke path with {cb.label} for {ov:g}px at {'y' if ax == 'h' else 'x'}={co:g}; offset by >=12px or reroute",
                })

    # R4 shared attach points between different connectors
    endpoints: list[tuple[Point, str, Connector]] = []
    for c in tracked:
        if c.start:
            endpoints.append((c.start, "start", c))
        if c.end:
            endpoints.append((c.end, "end", c))
    by_cell: dict[tuple[int, int], list[int]] = {}
    for idx, ((px, py), _kind, _c) in enumerate(endpoints):
        by_cell.setdefault((_cell(px), _cell(py)), []).append(idx)
    reported_pts: set[tuple[int, int]] = set()
    for i, (p, kind, ca) in enumerate(endpoints):
        kx, ky = _cell(p[0]), _cell(p[1])
        neighbours = sorted(
            j for ddx in (-1, 0, 1) for ddy in (-1, 0, 1) for j in by_cell.get((kx + ddx, ky + ddy), ()) if j > i
        )
        for j in neighbours:
            q, kind2, cb = endpoints[j]
            if ca is cb:
                continue
            if _same(p[0], q[0], tol) and _same(p[1], q[1], tol):
                key = (min(ca.order, cb.order), max(ca.order, cb.order))
                if key in reported_pts:
                    continue
                reported_pts.add(key)
                findings.append({
                    "rule": "R4", "element": ca.label,
                    "detail": f"{kind} point ({p[0]:g},{p[1]:g}) coincides with {kind2} of {cb.label}; fan attach points >=12px apart",
                })

    # R6 label mask clipped by a node painted later
    rects = [r for r in scan.rects if not r.untracked]
    nodes = [r for r in rects if r.w >= NODE_MIN_W and r.h >= NODE_MIN_H]
    masks = [r for r in rects if MASK_W_RANGE[0] <= r.w <= MASK_W_RANGE[1] and MASK_H_RANGE[0] <= r.h <= MASK_H_RANGE[1]]
    for m in masks:
        for n in nodes:
            if n.order <= m.order:
                continue
            ox = _overlap_len(m.x, m.x2, n.x, n.x2)
            oy = _overlap_len(m.y, m.y2, n.y, n.y2)
            if ox <= tol or oy <= tol:
                continue
            contained = m.x >= n.x - tol and m.y >= n.y - tol and m.x2 <= n.x2 + tol and m.y2 <= n.y2 + tol
            if contained:
                continue  # badge chip inside a node is legal
            findings.append({
                "rule": "R6", "element": m.label,
                "detail": f"label mask at ({m.x:g},{m.y:g} {m.w:g}x{m.h:g}) is clipped by later node {n.label}; move the label onto open canvas",
            })
            break
    return findings


def summarize(scan_source: str) -> dict:
    scan = SvgScan()
    scan.feed(scan_source)
    straight = sum(len(c.segments) for c in scan.connectors)
    return {"connectors": len(scan.connectors), "straight_segments": straight, "rects": len(scan.rects),
            "decorative_skipped": scan.decorative_skipped}


def _ascii_safe_stdout() -> None:
    """Piped stdout on Windows is cp1252: a non-ASCII file name in a print must degrade, not crash."""
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    _ascii_safe_stdout()
    ap = argparse.ArgumentParser(description="Verify SVG connector geometry (rules R1, R3, R4, R6).")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--allow-diagonal", action="store_true", help="skip R1 for data-driven charts (scatter, line, radar)")
    ap.add_argument("--tol", type=float, default=0.5, help="coordinate tolerance in px (default 0.5)")
    args = ap.parse_args(argv)

    results = []
    worst = 0
    for name in args.files:
        path = Path(name)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            results.append({"file": str(path), "ok": False, "error": str(exc), "findings": []})
            worst = max(worst, 2)
            continue
        findings = check(source, tol=args.tol, allow_diagonal=args.allow_diagonal)
        stats = summarize(source)
        results.append({"file": str(path), "ok": not findings, "findings": findings, **stats})
        if findings:
            worst = max(worst, 1)

    if args.json:
        print(json.dumps({"ok": worst == 0, "results": results}, indent=2))
    else:
        for r in results:
            if r.get("error"):
                print(f"ERROR {r['file']}: {r['error']}")
                continue
            if r["ok"]:
                skipped = f", {r['decorative_skipped']} decorative element(s) skipped" if r["decorative_skipped"] else ""
                print(f"OK   {r['file']}: {r['connectors']} connectors, {r['straight_segments']} straight segments{skipped}, no findings")
            else:
                print(f"FAIL {r['file']}: {len(r['findings'])} finding(s)")
                for f in r["findings"]:
                    print(f"  {f['rule']} {f['element']}: {f['detail']}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
