---
id: L037
title: "Don't assert 'bug'/'stale'/'broken' without running the discriminating check first"
category: assumptions
severity: critical
status: active
created: 2026-07-15
last_triggered: 2026-07-16
times_violated: 3
times_checked: 0
tags: [diagnosis, premature-conclusion, defect-claims, staleness, by-design, user-correction]
related_skills: [systematic-debugging]
---

**Rule:** Never assert a defect diagnosis in passing — "this is a desk bug", "the memory is stale", "X is broken" — without having run the check that distinguishes it from by-design behavior or an alternative cause. State observations as observations ("targets file is empty"); upgrade to a diagnosis only after evidence.

**Why:** Cross-session pattern (2 sessions, same day). Both drive-by defect claims were wrong, and both cost a user round-trip: the user had to bounce the claim back ("check why the desk run came up empty" / "i bet the memory is not stale, its probably that fable never edited the ground truth ledger"), and investigation proved the real cause was by-design cohort rules in one case and a missing prior-session write in the other. The unverified label is what creates the work — it plants a false fact the user must correct, and it primes future sessions with a wrong diagnosis if it lands in memory.

**Prevention:**
1. Before the words "bug", "stale", or "broken" appear in output, either (a) run the discriminating check NOW (read the selection/generation logic, probe the live source), or (b) phrase it as an open question: "targets file is empty — could be by-design (AM cohort is amc/tbd only) or a defect; want me to check?"
2. A defect claim about a pipeline requires reading that pipeline's selection/generation code first — not just observing its output.
3. A staleness claim about memory requires diffing memory against the live source (git log, Airtable probe) AND checking whether the prior session ever wrote the record — "never written" and "gone stale" have different fixes.
4. Treat the user replying "check why X" immediately after your defect claim as the signal that you skipped the investigation step — invoke systematic-debugging at that point, minimum.
5. When a defect claim turns out wrong, retract explicitly with the real cause (positive example: 38c0385e — "not a bug... I was wrong earlier").
