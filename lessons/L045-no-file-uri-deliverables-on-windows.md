---
id: L045
title: "file:// URIs are dead ends - serve over localhost, launch, or publish an artifact instead"
category: communication
severity: critical
status: active
created: 2026-08-14
last_triggered: 2026-08-26
times_violated: 3
times_checked: 0
tags: [windows, deliverables, terminal, file-links, playwright, localhost]
related_skills: []
---
**Rule:** file:// URIs are not clickable in the Windows terminal. When the deliverable is a local HTML/PDF report, do not end the turn with "your report is ready: file://...". Either open it for the user (Start-Process <path> in PowerShell), publish it as an Artifact and give the https link, or give the plain path with the one-line command to open it.

**Why:** The user hits a dead link, has to come back, and the turn is wasted ("i cant open it"). Start-Process is one call and closes the loop.

**Prevention:**
1. Deliverable is a local file -> default to Start-Process (after confirming the file exists) in the SAME turn the link would have gone out.
2. If the report has an audience beyond the user, publish an artifact instead and hand the https URL.
3. Browser automation blocks file:// too: Playwright MCP (and Claude-in-Chrome) refuse `file:` protocol navigation. To view/verify local HTML, start a local HTTP server first (`python -m http.server <port>` in the file's directory) and navigate to `http://localhost:<port>/...` — make that the FIRST move, not the recovery.
