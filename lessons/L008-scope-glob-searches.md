---
id: L008
title: "Scope Glob/Grep searches to specific directories — broad patterns time out"
category: tool-usage
severity: critical
status: active
created: 2026-03-15
last_triggered: 2026-05-23
times_violated: 10
times_checked: 0
tags: [glob, grep, search, performance, windows]
related_skills: []
---

**Rule:** Never Glob on your home directory or Desktop with recursive patterns. Always scope to a specific subdirectory (e.g., `Desktop/my-project/`).

**Why:** The home directory and Desktop are massive. Ripgrep times out after 20 seconds on every broad pattern. This wastes 5+ tool calls per attempt and forces fallback to Bash find, which itself is slow. Subagents are especially prone to this — they don't have memory context about known project paths.

**Prevention:**
1. For known projects: use memory/CLAUDE.md paths directly
2. For unknown projects: use `find` with `-maxdepth 2-3` first to narrow, then Glob the specific dir
3. Never use `**/*pattern*` on home or Desktop — always add at least one directory level
4. When dispatching subagents to find files: include known project paths in the prompt
