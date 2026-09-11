---
id: L040
title: "Counterfactual/backtest claims must replay the full policy — one-branch replays flip signs"
category: workflow
severity: standard
status: active
created: 2026-07-16
last_triggered: 2026-07-16
times_violated: 1
times_checked: 0
tags: [analysis, counterfactual, backtest, trading, premature-conclusion]
related_skills: [systematic-debugging]
---

**Rule:** When evaluating "what would have happened without X" on recorded data, simulate EVERY decision branch of the alternative policy — especially the adverse exits — not just the favorable branch. A one-branch replay ("the original target was eventually hit") is not a counterfactual; it is a cherry-pick, and it can flip the SIGN of the conclusion.

**Why:** One-branch counterfactuals systematically overstate the forgone alternative because the branches you skipped are exactly the ones that would have terminated it early. Narrating the resulting wrong conclusion live also anchors the user on a false mechanism diagnosis for hours before the analysis runs.

**Prevention:**
1. Before running a counterfactual, write down the alternative policy's complete exit/decision set (target touch AND stop AND structure/time exits). Simulate the EARLIEST of them, not the one you're curious about.
2. If a refined sim would reverse an opinion you already voiced, treat the first result as suspect by default — look for the missing branch before publishing either number.
3. During live monitoring, label mechanism-effect judgments ("this feature is leaking money") as hypotheses until a full-policy replay confirms; log them for the eval instead of asserting them.
4. Sanity-gate sim outputs by magnitude: a per-trade counterfactual larger than the day's range means a branch or field is wrong (see L039 close_px case — same session).
