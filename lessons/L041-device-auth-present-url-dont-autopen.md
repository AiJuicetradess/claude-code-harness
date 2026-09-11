---
id: L041
title: "OAuth/device-auth flows: present the URL + code — don't auto-open the default browser"
category: workflow
severity: high
status: active
created: 2026-07-16
last_triggered: 2026-07-16
times_violated: 1
times_checked: 0
tags: [oauth, device-auth, browser, environment-assumption, user-correction]
related_skills: []
---

**Rule:** When a CLI device-auth/OAuth flow needs a browser, print the verification URL and user code and let the user open it in the browser/profile of THEIR choice. Do not auto-open (`start <url>`, `--open`) — the OS default browser is frequently not the profile that holds the user's session, and a one-time code consumed by the wrong profile forces a full restart of the flow.

**Why:** Auto-open binds a single-use code to a browser you didn't choose. The failure costs a full round trip: kill the polling process, mint a fresh code, re-prompt the user — plus the user has to notice and correct it ("wrong browser do it again").

**Prevention:**
1. Default: display URL + code in the terminal and say "open this in whichever browser has your account."
2. If the flow insists on auto-opening, ask which browser/profile first, or pre-empt with the flag that suppresses auto-open when one exists.
3. If the wrong browser grabs the code, kill the poller and restart the flow cleanly — never ask the user to transplant a possibly-consumed code across browsers.
