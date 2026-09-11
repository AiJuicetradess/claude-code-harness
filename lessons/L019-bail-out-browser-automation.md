---
id: L019
title: "Bail out of failing browser automation after 2-3 attempts — ask user to do UI actions"
category: workflow
severity: high
status: active
created: 2026-04-06
last_triggered: 2026-04-13
times_violated: 2
times_checked: 0
tags: [playwright, browser, automation, ui, efficiency]
related_skills: []
---

**Rule:** When browser automation (Playwright) fails to accomplish a UI action after 2-3 attempts, stop and ask the user to do it manually. Complex UI interactions (drawing polygons on maps, drag-and-drop, multi-step filter workflows) are often faster for a human than for an automation agent.

**Why:** In one session, 50+ tool calls were spent trying to draw a polygon on a third-party map widget through browser automation. The assistant zoomed, panned, clicked draw, tried coordinates, redrew — never succeeded. The user did it manually in seconds. Additionally, 25 calls were wasted recovering from accidentally clicking "Reset" instead of "Apply" in a filter UI. Browser automation is a means, not an end — when it's fighting the UI, the user is a better tool.

**Prevention:**
1. After 2 failed browser automation attempts on the same UI action: ask the user to do it
2. For spatial interactions (drawing, drag-and-drop, map manipulation): prefer asking the user from the start
3. For form-filling and navigation: automation is fine, but verify button refs before clicking
4. When using browser snapshots: save to file for consistent parsing, don't alternate between inline and file-based approaches
