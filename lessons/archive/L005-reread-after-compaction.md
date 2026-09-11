---
id: L005
title: "Re-read files after context compaction"
category: workflow
severity: standard
status: internalized
created: 2026-03-13
last_triggered: 2026-03-13
times_violated: 0
times_checked: 0
tags: [context, compaction, workflow]
related_skills: [context-management]
---

**Rule:** After context compaction (auto or manual), re-read all files that are actively being modified before making further edits.

**Why:** Compaction discards tool output including file contents. Editing from memory after compaction leads to stale content, wrong line numbers, and failed Edit operations.

**Prevention:**
1. After seeing a compaction notice, immediately re-read the current working files
2. Don't trust line numbers from before compaction
3. If editing multiple files, re-read each before editing
