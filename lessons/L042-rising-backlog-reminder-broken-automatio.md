---
id: L042
title: "Rising backlog reminder = broken automation - check the job log, don't ignore it"
category: workflow
severity: high
status: active
created: 2026-08-12
last_triggered: 2026-08-12
times_violated: 1
times_checked: 0
tags: [automation, cron, silent-failure, reflection-pipeline]
related_skills: []
---
**Rule:** When a recurring reminder or backlog counter keeps climbing session after session (e.g. 'N unreflected sessions'), treat it as an automation-failure alarm: tail the job's driver log for repeated identical errors BEFORE continuing other work. A scheduled job with no failure-surfacing can fail identically every night for weeks.

**Why:** The nightly reflection drain (_steady_drain.py) failed 20 consecutive nights (2026-07-23 to 2026-08-12) with the same FileNotFound error because _batch_prep.py was deleted; every session saw the backlog reminder climb toward 148 and none checked the log. One 30-second log read would have caught it on night 1.

**Prevention:**
1. On first sighting of a growing backlog/queue reminder, tail the responsible job's log (e.g. _steady_drain.log) and look for repeated identical failures.
2. Before deleting or renaming a helper script, grep the directory for dependents that invoke it (_steady_drain.py referenced _batch_prep.py by path).
3. When building unattended scheduled jobs, give them a fail-loud path: consecutive-failure counter, a status file a session-start hook can surface, or a push notification.
