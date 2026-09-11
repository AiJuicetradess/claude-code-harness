---
name: diagram-geometry
description: Connector geometry rules plus a deterministic verifier for hand-authored SVG diagrams (architecture, flowchart, sequence, data-flow, state, swimlane) in HTML files or Artifact pages. Use whenever drawing or editing SVG arrows, edges, connectors, elbows, arrow labels, attach points, or legends by hand, alongside artifact-diagramming or any inline-SVG work. Run scripts/verify_connectors.py before delivering. Not for archify output (already validated) or data-driven charts with legitimate diagonals (scatter, line, radar) unless run with --allow-diagonal.
---

# Diagram Geometry

Six connector rules for node-and-arrow diagrams, four of them machine-checked.
Adapted from cathrynlavery/diagram-design SKILL.md section 6 (MIT). The verifier
is stdlib Python and runs on any HTML or SVG file:

```bash
python ~/.claude/skills/diagram-geometry/scripts/verify_connectors.py <file.html|file.svg> [--json] [--allow-diagonal]
```

Exit 0 means no findings. Exit 1 lists each finding as `R<n> <element>: <detail>`.
Fix the element, re-run, and only then deliver. Never hand over a diagram with an
unresolved finding; if a rule cannot be met, say which one and why.

## The six rules

1. **Orthogonal connectors only (R1, checked).** Never a diagonal `<line>` or a
   slanted `L` segment between nodes that do not share an x or y axis. Every bend
   is a quarter-arc (`A 8 8 0 0 1 ...`) or quadratic curve with radius 8 (6 minimum
   in tight layouts). A plain straight segment is allowed only when its endpoints
   share x or y.
2. **Label-to-connector gap of 6 to 10 px (prose).** A label sits above the line
   (beside it for vertical runs) on an opaque mask rect, and the mask never touches
   the stroke. The reader must be able to trace the connector under the label.
3. **No overlapping connectors (R3, checked).** Two connectors never share a stroke
   path or run parallel on top of each other. Crossing arrows use a bridge/hop.
   Parallel runs stay at least 12 px apart end to end. If connectors stack, the
   layout is over budget: split into overview plus detail.
4. **Fan the attach points (R4, checked).** When N connectors leave or enter the same
   box edge of length L, connector k attaches at `L * k / (N + 1)` from the leading
   corner, at least 12 px apart (8 px on very small boxes). No two connectors share
   a point on a box.
5. **No transit behind a non-endpoint box (prose).** Reroute around intervening
   boxes. The single exception is a cross-cutting bar that physically sits on the
   only straight path; then the stroke is dashed (`stroke-dasharray="4,3"`), the
   label sits at the visible end, and no arrowhead lands on the intervening box.
6. **A label mask must not be clipped by a later node (R6, checked).** Paint order is
   background, zones, arrows, labels, nodes. A mask that lands partly inside a node
   painted later is covered by the node fill. Place labels on a segment that runs
   through open canvas. A mask fully inside a node is a badge chip and is fine.

## Patterns that satisfy the rules

**Draw arrows before boxes** so z-order keeps strokes behind nodes. Define the arrow
markers once in `<defs>`; the verifier ignores everything inside `<defs>`,
`<marker>`, `<pattern>`, `<symbol>`, `<clipPath>`.

**Elbow path** from (x1,y1) right then down to (x2,y2) with r=8:

```svg
<path d="M x1 y1 H x2-8 A 8 8 0 0 1 x2 y1+8 V y2" fill="none" stroke="#4f5d75" stroke-width="1" marker-end="url(#arrow)"/>
```

**Arrow label with mask and gap** (8 px text, 6 px gap, stroke at ARROW_Y):

```svg
<rect x="MID_X-18" y="ARROW_Y-20" width="36" height="12" rx="2" fill="#f5f5f5"/>
<text x="MID_X" y="ARROW_Y-11" font-size="8" text-anchor="middle" letter-spacing="0.06em">WRITE</text>
```

Labels are 14 characters or fewer, centered on the segment midpoint, never
`writing-mode` vertical. For vertical segments place the label to the side with
the same gap.

**Legend** is a horizontal strip below the diagram after a hairline separator, never
floating inside the drawing. Expand the viewBox height by about 60 px for it.

**Grid.** Every coordinate, size, and gap divisible by 4.

## Verifier scope and limits

- Reads `<line>`, `<path>`, `<polyline>` outside the skipped containers; filled
  paths are shapes, not connectors.
- Applies `translate()` on ancestors. Any other transform (scale, rotate, matrix)
  marks that subtree untracked: R1 still runs, R3/R4/R6 skip those elements.
- Node heuristic: `<rect>` at least 60x40. Mask heuristic: `<rect>` 20 to 200 wide
  and 8 to 16 tall. Zone containers are large and painted first, so they never
  trigger R6.
- Charts with data-driven diagonals: pass `--allow-diagonal` to skip R1 only.
