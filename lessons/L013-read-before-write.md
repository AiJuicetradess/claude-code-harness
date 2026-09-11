---
id: L013
title: "Read existing files before using Edit or Write tool"
category: tool-usage
severity: critical
status: enforced
created: 2026-03-15
last_triggered: 2026-06-30
times_violated: 129
times_checked: 17
tags: [write, edit, read, tool-constraint, pre-edit-guardian]
related_skills: [cove-verification]
---

**Rule:** Always Read an existing file before using Edit or Write on it. The pre-edit-guardian hook AND the built-in Edit/Write tool both enforce this — they will block with "BLOCKED: You have not Read X in this session" or "File has not been read yet."

**Why:** Editing without reading produces stale assumptions about file content, wrong line numbers, and failed string matches. The Write tool has a built-in safety check requiring a prior Read of the target file. The pre-edit-guardian hook adds session-scoped tracking. Both fire repeatedly when this rule is violated, wasting 1-3 tool calls per violation.

**Prevention:**
1. Before any Edit/Write to an existing file: Read it first (even if you "know" the content)
2. For new files that don't exist yet: Write works without prior Read
3. After context compaction or session resume: re-read the file before editing
4. In multi-step workflows (like regenerating LESSONS.md or audit doc updates): include the Read step in your plan
5. When dispatching subagents: confirm they Read each target before editing. **Subagent reads do NOT transfer to the main agent's read tracker** — re-read in the main session before editing, especially after task-completion subagent dispatches that clear the assistant's read cache.
