---
id: L026
title: "Memory write storms — multiple per-slice memory files instead of one consolidated update"
category: workflow
severity: critical
status: active
created: 2026-05-01
last_triggered: 2026-07-14
times_violated: 6
times_checked: 0
tags: [memory, organization, file-sprawl, semantic-not-chronological]
related_skills: []
---

**Rule:** Per session, write at most 3 net memory files: (a) update existing memory files when new evidence is on-topic, (b) create new memory files only for genuinely new topics. Do not split a single audit/checkpoint/session into 4+ date-stamped or severity-stamped sibling files (e.g., `project_crit_fixes_2026_04_20.md` + `project_high_fixes_2026_04_20.md` + `project_medium_fixes_2026_04_20.md`).

**Why:** The global instructions explicitly say *"Organize memory semantically by topic, not chronologically"* — slice files violate that rule and create lookup ambiguity in future sessions. One project memory directory reached **87 .md files**, two others **70** and **34**; **302 memory files** across all projects as of 2026-05-01. When the assistant feels a phase boundary, it creates a new file rather than updating an existing semantic file. Future sessions then have to re-read all the slice files to reconstruct the topic — turning what should be a single load into N loads, which feeds back into L016 context bloat.

**Prevention:**
1. Before creating a new memory file: grep the project's `MEMORY.md` for the topic. If a file with overlapping topic exists, update it instead.
2. For audit/fix work: one `project_<system>_audit.md` file (updated as new findings land), not separate `crit_fixes`, `high_fixes`, `medium_fixes` files.
3. For session checkpoints: do not create `session_<date>_<topic>.md` files unless the session is the *first* time a topic appeared. If it's a continuation, append to the existing topic file with a `## 2026-04-26 update` header.
4. Cap per-session memory writes at **3 files** (cap confirmed 2026-05-01 by user). If you feel pressure to write a 4th, that's a signal to consolidate two of them first.
5. When updating MEMORY.md index: if you're adding more than 2 lines to MEMORY.md from one session, you are probably over-slicing. Reconsider whether the new entries deserve their own files or belong inside an existing entry.
6. **Edit-count churn on a single memory file is the same storm:** batch memory deltas into 1-2 consolidated Edits at natural checkpoints (user "save memory", pre-compact, closeout) instead of dozens of per-line edits throughout the session. Per-line memory editing is what saturates the consecutive-edit guard (L021) and triggers the parallel-bounce cascades (L030).
