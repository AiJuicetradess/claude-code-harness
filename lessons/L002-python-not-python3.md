---
id: L002
title: "Use python not python3 on Windows"
category: tool-usage
severity: high
status: active
created: 2026-03-13
last_triggered: 2026-03-13
times_violated: 3
times_checked: 0
tags: [windows, python, bash]
related_skills: []
---

**Rule:** On Windows, always use `python` not `python3`. The `python3` command does not exist on Windows.

**Why:** Windows installs Python as `python.exe`. Running `python3` fails with "command not found", wasting a tool call and requiring a retry.

**Prevention:**
1. In bash commands: always `python -m ...` or `python script.py`
2. In shebangs: use `#!/usr/bin/env python` not `python3`
3. Check platform context — this system is Windows 11
