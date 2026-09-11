---
id: L006
title: "Never edit .env or secrets files — hooks will block it"
category: tool-usage
severity: high
status: active
created: 2026-03-13
last_triggered: 2026-05-16
times_violated: 3
times_checked: 0
tags: [secrets, env, hooks, security]
related_skills: []
---

**Rule:** Never attempt to Write or Edit `.env` or `.env.local` files. A PreToolUse hook blocks these operations. Instead, tell the user what values to set and let them edit the file manually.

**Why:** PreToolUse hooks block any Write/Edit to files matching `.env` or `.env.local`. Every attempt wastes a tool call and returns an error. This happened in 2 separate sessions on the same day.

**Prevention:**
1. When credentials or env vars need to be set, output the values as text and instruct the user to edit the file manually
2. For scripts that need env vars, generate a `.env.example` file (not `.env`) showing the expected keys without values
3. If creating deployment scripts, have them read from env vars, not write to `.env` files
