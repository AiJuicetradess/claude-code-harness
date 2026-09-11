---
id: L035
title: "Don't put PowerShell cmdlets/redirects in the Bash tool (or bash syntax in PowerShell) - match the dialect to the tool"
category: tool-usage
severity: critical
status: enforced
created: 2026-06-14
last_triggered: 2026-08-12
times_violated: 9
times_checked: 0
tags: [windows, bash, powershell, shell-dialect, redirect, cmdlet]
related_skills: []
---
**Rule:** The Bash tool runs Git Bash (POSIX sh); the PowerShell tool runs Windows PowerShell. Never mix dialects: in a Bash command do NOT use 2>$null, Select-Object, Get-Process, (Get-Item x).Length, $env:VAR, or findstr; use 2>/dev/null, head/grep, $VAR, and POSIX utilities. Choose the tool whose shell natively supports the syntax instead of pasting the other shell's commands into it.

**Why:** Across the batch, agents repeatedly authored one command blending the two Windows shells and it failed instantly: PowerShell pipelines/cmdlets typed into the Bash tool returned 'Select-Object: command not found', '$null: ambiguous redirect', and 'syntax error near unexpected token .Length'. These are wasted round-trips that often also cascade-cancel sibling parallel calls (L030). Distinct from L003 (path-format/backslash mangling) and L034 (2>&1 on native exes in PowerShell) - here the failure is using the wrong shell's command vocabulary entirely.

**Prevention:**
1. Before composing a shell command, fix which tool you're calling: Bash tool = POSIX sh, PowerShell tool = Windows PowerShell. Write only that dialect.
2. In the Bash tool use 2>/dev/null (never 2>$null), grep/head/ls (never Select-Object/findstr/Get-Process), and $VAR/stat -c%s (never $env:VAR/(Get-Item).Length).
3. If the task genuinely needs a cmdlet (process/port enumeration, Get-Process, Get-NetTCPConnection), call the PowerShell tool instead of shoehorning it into Bash.
4. If you catch a 'command not found' / 'ambiguous redirect', rewrite in one dialect rather than re-running a tweaked hybrid.

**Hook enforcement (2026-08-25, PROMOTED):** `pre_bash_guard.py` blocks both directions. Bash tool: `2>$null`, `$env:VAR`, and canonical Verb-Noun cmdlets (quoted spans exempt). PowerShell tool: `&&`/`||` (PS 5.1 parser error), `/dev/null`, `export VAR=` — checked on comment/quote/here-string-stripped text. Tests in `test_promoted_guards.py`.
