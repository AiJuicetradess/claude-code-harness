---
id: L021
title: "Re-read a file before each new edit when iterating — stale state breaks Edit"
category: tool-usage
severity: critical
status: enforced
created: 2026-05-01
last_triggered: 2026-08-14
times_violated: 89
times_checked: 15
tags: [edit, iteration, pre-edit-guardian, P15, stale-state]
related_skills: [cove-verification]
---

**Rule:** When making 3 or more sequential Edits to the same file, re-read it after every 2-3 edits. The pre-edit-guardian P15 hook blocks "3 consecutive edits without a verification read" — and even when the hook isn't enforcing, your view of the file diverges from disk after each edit.

**Why:** Each Edit changes line numbers, surrounding context, and string-match anchors. After 3 consecutive edits without a fresh Read, the in-memory snapshot is stale. The next Edit's `old_string` may no longer match, or — worse — may match unintended text. The P15 hook fires explicitly to enforce this. Distinct from L013 (Read before *first* edit) and L005 (re-read after *compaction*) — this is about iteration-induced drift within a single working session.

**Prevention:**
1. After 2-3 consecutive Edits to the same file: insert a Read before the next Edit
2. Use `replace_all` for multi-instance renames instead of stacking single-Edit calls
3. When restructuring a file: write the full new content with Write (after a Read) instead of 10+ Edits
4. If the P15 hook blocks: stop, Read the file, and re-plan the remaining edits in fewer passes
5. For plan/design doc revisions: draft the full edited content first, then apply as 1-2 Edits — not 19
