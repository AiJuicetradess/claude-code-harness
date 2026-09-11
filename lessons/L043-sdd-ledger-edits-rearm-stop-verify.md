---
id: L043
title: "SDD ledger edits have side effects: they re-arm stop-verify (re-read in the turn) and block branch switches (commit before checkout/merge)"
category: workflow
severity: critical
status: active
created: 2026-08-14
last_triggered: 2026-09-01
times_violated: 4
times_checked: 0
tags: [sdd, orchestration, stop-verify, hooks, wasted-cycles, git, checkout, ledger]
related_skills: [subagent-driven-development]
---
**Rule:** During subagent-driven-development (or any orchestration that appends to a ledger/dispatch file every turn), each append re-arms the stop-verify hook, so ending the turn without re-reading the edited doc gets stop-blocked - every single turn. After editing progress.md / task-N dispatch briefs, either re-read the file in the same turn (a cheap targeted Read) or state in the final message why verification is not applicable. Do not just end the turn and eat the block.

**Why:** The hook is latched per state snapshot but re-arms on new edits; SDD touches the ledger every task loop, so the latch never saves you. Each block wastes a full turn round-trip and sprays "Stop hook feedback" noise into the transcript.

**Prevention:**
1. In SDD sessions, pair every ledger/dispatch Write/Edit with an immediate Read of the same file before ending the turn.
2. If the turn only touched process markdown (no code), say so explicitly in the closing message - the hook accepts a stated non-applicability.
3. HOOK-TUNING TODO (surface to the user): consider exempting .superpowers/sdd/** and dispatch/ledger markdown from stop-verify - they are process artifacts, not deliverables.

4. **At merge time the ledger is dirty.** `.superpowers/sdd/<plan>/progress.md` and `final-review.md` were appended during the last review round; `git checkout master` will refuse with 'local changes would be overwritten'. Run `git status --short` and commit the ledger FIRST (CLAUDE.md: ledgers are committed with the branch), then switch/merge in ONE chained command. A failed git call also arms the L030 15s lock, so one skipped status check becomes 3-4 wasted round-trips.
