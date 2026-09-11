---
id: L003
title: "Windows path format differs between bash and Python; Git Bash mangles /flags and \\backslashes"
category: tool-usage
severity: critical
status: enforced
created: 2026-03-13
last_triggered: 2026-08-22
times_violated: 55
times_checked: 3
tags: [windows, paths, python, bash, git-bash, flag-mangling, pre-bash-guard]
related_skills: []
---

**Rule:** Bash uses `/c/Users/...` paths. Python uses `C:\Users\...` or forward-slash equivalents. Never mix them. Additionally, **Git Bash mangles `/flags` (treating them as paths) and `\backslashes` in quoted strings** — Windows-native commands need `cmd.exe /c` or `powershell.exe`.

**Why:** FileNotFoundError when passing bash-style `/c/` paths to Python's `open()`, or when using backslash Windows paths in bash commands. Also: `ipconfig /all` becomes `ipconfig \all`, `taskkill /PID` becomes `taskkill \PID`, and `ls "C:\Users\..."` parses as an unterminated quoted string in Bash.

**Prevention:**
1. In Python scripts: always use `os.path.expanduser('~')` for home directory
2. In Python: use `pathlib.Path` for cross-platform path handling, or pass `C:/Users/...` (forward slashes) on the command line
3. In bash: use `/c/Users/<you>/...` format
4. When passing paths between tools: verify format matches the receiving tool
5. For Windows-native commands (`ipconfig`, `taskkill`, `schtasks`, `where.exe`): invoke through PowerShell tool or `cmd.exe /c` — Git Bash mangles `/flags` into filesystem paths
6. To pass Windows paths as arguments in Bash: use forward slashes (`C:/Users/...`) instead of backslashes — backslashes inside double quotes are still interpreted as escape characters by Bash

**Hook enforcement (2026-08-15):** `pre_bash_guard.py` now BLOCKS the three deterministic shapes in Bash-tool commands: backslash drive paths (`C:\...` outside single quotes), Windows-native commands with `/flags` (ipconfig/taskkill/schtasks/...), and cmd-style `>nul` redirects. NOT covered (stays behavioral): passing `/c/...`-style paths into Python `open()`/argv — that failure happens inside the script at runtime, not in the command shape.

**Hook enforcement (2026-08-23, status → ENFORCED):** `pre_bash_guard.py` extended with the unset-path-variable check: `$VAR/...` (also `${VAR}/`, `"$VAR"/`) in a Bash-tool command is BLOCKED when VAR is never assigned in the same command — Bash-tool state doesn't persist between calls, so the var expands empty and MSYS resolves the bare leading slash to the Git install root (the 6cd0e43e bypass). Exempt: in-command assignments/for/read, `${VAR:?}`/`${VAR:-}` guarded forms, real environment variables, single-quoted spans, quote-delimited heredoc bodies. Verified by 20-case suite (`~/.claude/hooks/test_pre_bash_guard.py`, 20/20 incl. all pre-existing checks — re-run it after any future edit to the guard). Still behavioral (reactivate if these recur): `/c/...`-paths handed to Python open()/argv at runtime.
