---
id: L038
title: "Empty Glob result is not proof of absence — Windows brace/path patterns silently return false-empty"
category: tool-usage
severity: standard
status: active
created: 2026-07-15
last_triggered: 2026-07-14
times_violated: 2
times_checked: 0
tags: [glob, windows, brace-expansion, false-negative, verification]
related_skills: []
---

**Rule:** On Windows, an empty Glob result where you expected matches is a suspect result, not a conclusion. Brace patterns (`{JPM,BAC,GS}_*`) and some relative-path shapes silently return empty even when files exist. Confirm absence with one `ls` of the parent directory (or a simpler single pattern) before acting on "no matches".

**Why:** Two false-empties in one session, each costing an extra roundtrip — and the second used a brace pattern AFTER the first false-empty had already forced an `ls` fallback. Acting on a false "no matches" is worse than the wasted call: it can cascade into "file doesn't exist" conclusions, skipped processing, or redundant regeneration of files that were there all along.

**Prevention:**
1. Don't use brace expansion in Glob patterns — fire N simple patterns in parallel, or one prefix pattern and filter the results.
2. On any empty Glob where you expected hits: one `ls` (or `Get-ChildItem`) of the parent directory before concluding absence.
3. Never chain a consequential action (regeneration, "missing file" report, skip-processing decision) off an unverified empty Glob.
4. Once a Glob shape has returned a false-empty in a session, stop using that shape for the rest of the session.
