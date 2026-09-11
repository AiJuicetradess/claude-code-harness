---
id: L009
title: "Verify end-to-end data flow, not just absence of errors"
category: workflow
severity: critical
status: active
created: 2026-03-15
last_triggered: 2026-07-14
times_violated: 12
times_checked: 3
tags: [verification, e2e, premature-victory]
related_skills: [verification-before-completion]
---

**Rule:** Before declaring a pipeline, workflow, or integration "working," verify that meaningful data actually flows through it end-to-end. "No errors in the logs" is not the same as "works."

**Why:** Three separate sessions had the same failure: the assistant declared success because execution completed without errors, but the user found that data wasn't actually flowing (empty results, wrong channels, missing deliveries). This wastes user trust and debugging time.

**Prevention:**
1. After activating a workflow: check the actual output (Slack message content, database rows, API response body)
2. After fixing a pipeline: verify at least one complete data cycle produces expected output
3. After deploying: don't just check status flags — check delivery receipts
4. Ask: "What would the user see?" not "Did the code throw?"
