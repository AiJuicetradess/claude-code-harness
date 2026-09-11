---
id: L015
title: "Delete existing team before creating a new one"
category: workflow
severity: standard
status: active
created: 2026-03-17
last_triggered: 2026-03-16
times_violated: 1
times_checked: 0
tags: [teams, agent-management, lifecycle]
related_skills: []
---

**Rule:** Before calling TeamCreate, check if you're already leading a team. Only one team can be active at a time. Use TeamDelete on the existing team first if you need to switch.

**Why:** TeamCreate errors with "Already leading team X" if a team exists. This wastes a tool call and requires additional calls to ToolSearch for TeamDelete schema + the actual TeamDelete call — 3 wasted calls total.

**Prevention:**
1. Before TeamCreate: mentally check if a team was created earlier in the session
2. If switching from research phase to build phase: explicitly delete the research team first
3. If the session involves multiple phases with different teams: plan the team lifecycle upfront
