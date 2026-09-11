---
id: L031
title: "Classifier-unavailable retry storm — pivot to read-only or wait, do not re-fire"
category: tool-usage
severity: critical
status: active
created: 2026-05-20
last_triggered: 2026-05-23
times_violated: 12
times_checked: 0
tags: [classifier, auto-mode, retry, wasted-cycles, bash, powershell, transient-errors]
related_skills: []
---

**Rule:** When a Bash or PowerShell call returns `claude-opus-4-7[1m] is temporarily unavailable, so auto mode cannot determine the safety of <tool> right now`, do NOT re-fire the same tool call in the next turn. The classifier outage is a multi-minute service issue, not a 5-second blip. After the first occurrence: switch to read-only operations (Read / Grep / Glob / WebSearch) that don't require the classifier, OR check back after at least 5 minutes / a substantive other task — never a tight retry loop.

**Why:** The auto-mode classifier evaluates Bash and PowerShell call safety. When opus-4-7 is overloaded or under maintenance, the classifier can't run, so the tool refuses pre-flight even on harmless commands. The error message *itself* says "Wait briefly and then try this action again ... if it keeps failing, continue with other tasks that don't require this action and come back to it later." Two recent sessions both ignored the "other tasks" guidance and burned 4-6 immediate retries with the same command. Cost: each retry is a full round-trip with zero progress, and the classifier doesn't get healthier between retries spaced seconds apart.

This is structurally distinct from L007 (never retry a denied tool — that's about permission decisions). L031 is about a *transient infrastructure outage that requires a wait or pivot*, not a denial.

**Prevention:**
1. **First classifier-unavailable error:** ack it, immediately pivot to a read-only operation (Read / Grep / Glob / WebSearch / WebFetch) or a different non-Bash tool that can advance the task. Do NOT re-fire the same Bash/PowerShell call.
2. **If no read-only path forward exists:** tell the user, then either (a) wait by working on a different task entirely, or (b) end the turn cleanly with a `needs input:` / `result:` line so the user can re-prompt later when the classifier is back.
3. **Never re-fire the identical command in the same turn batch.** Two retries spaced by one model-output is still inside the classifier's outage window — they will both fail.
4. **Do not "downgrade" by switching from Bash → PowerShell or PowerShell → Bash with the same intent** — both go through the same classifier. The L1314 attempt (Bash failed, then PowerShell with identical `npm run lint`) is the exact anti-pattern.
5. **If the task truly requires shell execution and the classifier stays down:** ask the user to run the command themselves via `! <command>` (per Session-specific guidance in the system prompt), capture the output, then continue.
