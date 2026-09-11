---
id: L036
title: "Scheduled/headless job prompts must include a self-verification step"
category: workflow
severity: critical
status: active
created: 2026-07-07
last_triggered: 2026-07-14
times_violated: 5
times_checked: 0
tags: [cron, headless, verification, stop-verify, prompt-design]
related_skills: [verification-before-completion]
---

**Rule:** Any recurring headless job prompt (cron job, scheduled agent, pipeline script) that writes a deliverable must itself instruct: after writing, re-read the output and validate it (parses, meets constraints) BEFORE claiming done. When the same guard fires on the same scheduled job twice, patch the job's prompt template at its source — per-run correction cannot fix a template defect.

**Why:** A daily scheduled insights job wrote `insights_<date>.json` and claimed "Done." without verification on two consecutive days. The stop-verify-reminder hook blocked each run, forcing a redundant re-read/validate cycle. Because a scheduled job's prompt never changes between runs, the identical miss recurs every single run until the template is fixed — burning one correction cycle per day and relying entirely on the hook staying enabled.

**Prevention:**
1. When authoring any recurring/headless prompt that writes files, end it with an explicit verification step: "Re-read the written file, confirm it parses and meets the stated constraints, then report what you verified."
2. When a stop-verify reminder fires in a headless session, treat it as a defect report against the generating script/prompt template — locate and patch the template, don't just satisfy the hook once.
3. During reflection, two identical guard-fires from the same scheduled job = prompt-template bug. Fix at the source (poka-yoke), not in the transcript.
