---
id: L007
title: "Never retry a denied tool call — adjust approach or report"
category: tool-usage
severity: critical
status: active
created: 2026-03-13
last_triggered: 2026-05-23
times_violated: 5
times_checked: 0
tags: [permissions, tool-calls, workflow]
related_skills: []
---

**Rule:** When a tool call is denied (permission not granted), never re-attempt the exact same call. Either adjust the approach or clearly report the failure.

**Why:** System instructions explicitly prohibit re-attempting denied tool calls. Retrying wastes a tool call and annoys users. Permission denials are intentional — retrying won't change the outcome.

**Prevention:**
1. After a tool denial, immediately communicate the issue to the user
2. If there's an alternative approach (different path, different tool), try that instead
3. Never assume "not yet granted" means "try again" — treat all denials as final
