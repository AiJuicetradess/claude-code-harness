---
id: L033
title: "Edit old_string must match exactly and uniquely - grep/verify before editing repeated or propagated strings"
category: tool-usage
severity: critical
status: active
created: 2026-06-14
last_triggered: 2026-08-26
times_violated: 13
times_checked: 0
tags: [edit, old_string, replace_all, propagated-fix, unicode-drift]
related_skills: []
---
**Rule:** Before an Edit, confirm the old_string occurs exactly once with the exact bytes in the target file. If the same text repeats (propagated fix), either pass replace_all:true deliberately or add surrounding context to make it unique; never assume a single occurrence.

**Why:** Edit fails two ways that each waste a turn: 'Found N matches, replace_all is false' when the string repeats (common after a fix is propagated across a file or sibling files), and 'String to replace not found' when remembered text has drifted from the file's real bytes (whitespace, em-dashes, unicode-escape sequences, or an edit made earlier in the session). Both come from building old_string from memory instead of current ground truth.

**Prevention:**
1. Re-read (or grep) the exact target region immediately before editing, especially after prior edits to the same file.
2. If the string could repeat, decide up front: replace_all:true for an intentional global change, or extend old_string with unique surrounding lines.
3. Copy old_string from the just-read file content, not from earlier conversation memory - watch for em-dashes/unicode and indentation.
4. On 'not found' or 'N matches', do not retry blind; re-read the region and rebuild old_string from ground truth.
