---
id: L047
title: "Operator-run procedures ship as ONE driver script — never a copy-paste sequence of steps"
category: workflow
severity: high
status: active
created: 2026-09-01
last_triggered: 2026-08-31
times_violated: 1
times_checked: 0
tags: [deploy, runbook, operator-handoff, scripts, idempotent, user-correction, classifier]
related_skills: [subagent-driven-development]
---
**Rule:** When the user has to run a procedure themselves (the classifier blocks the deploy, or L028 requires their hand on the trigger), hand them ONE idempotent driver script that chains every automatable step with go/no-go gates and takes secrets as arguments — not N separate scripts plus ad-hoc ssh one-liners to paste in order. Bake in every value you already know (current HEAD, container/host layout). The only things the human supplies are the things only the human has: a password, a dashboard click, a text from their phone.

**Why:** Each handed-over command is a human round-trip that costs minutes, not seconds, and every one of them is a place for a stale literal or a guessed identifier to fail in the user's terminal instead of yours. Fragmented handoffs also make "what state is the server in now?" unanswerable mid-sequence. The user's own words: a one-shot bash is what they wanted, and it was fully scriptable — the model wrote exactly that consolidation *after* being asked.

**Prevention:**
1. Before handing over step 1 of anything with more than one step, write `deploy/run-all.sh` (or equivalent) that calls the steps in order, prints what it will do, aborts on the first failed gate, and is safe to re-run.
2. Any guard value the script needs (`EXPECT_HEAD`, a fingerprint, an image tag) is computed at handoff time or by the script itself — never a stale literal the user must discover and override on the first run.
3. Identifiers in handed-over commands are probed, not guessed (L039): a failed command the USER runs is the expensive failure.
4. Secrets: a positional arg or env at invocation (`bash run-all.sh '<hash>'`), never hardcoded, never prompted for mid-script (stdin is not guaranteed).
5. Steps that are inherently human (dashboard clicks, texting the number) are listed AFTER the script, numbered, each with the exact expected outcome so the user knows when to come back.
