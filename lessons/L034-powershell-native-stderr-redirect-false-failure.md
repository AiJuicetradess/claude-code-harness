---
id: L034
title: "Don't redirect a native exe's stderr with 2>&1 in PowerShell - it wraps stderr as NativeCommandError and reports a false exit-1"
category: tool-usage
severity: critical
status: enforced
created: 2026-06-14
last_triggered: 2026-07-10
times_violated: 10
times_checked: 0
tags: [powershell, windows, native-command, stderr, exit-code, false-failure, git, uv, mypy]
related_skills: []
---
**Rule:** In Windows PowerShell, never append 2>&1 to a native executable (git, uv, mypy, ruff, python, node, scp) when you only want its output. PowerShell wraps each stderr line in a NativeCommandError ErrorRecord and sets the call's exit/$? to failure even when the program returned 0. Let stderr flow to the console (the harness already captures it); if you must separate streams, redirect to files, or check $LASTEXITCODE explicitly instead of trusting the wrapped result.

**Why:** PowerShell's 2>&1 merge semantics differ from POSIX: redirected native stderr becomes typed error objects, not text, which flips success detection. Across these sessions the same operator repeatedly ran uv/pytest/mypy with 2>&1 | Select-Object, got a spurious NativeCommandError + exit-1 on a green suite, and had to re-run and explicitly note 'the exit-1 was my mistake redirecting native stderr' - burning turns on phantom failures and risking real failures masked by the noise.

**Prevention:**
1. For native exes in PowerShell, drop 2>&1 - run the command plain and read the captured output the harness already returns.
2. When you need exit status, check $LASTEXITCODE -eq 0 right after the call rather than inferring success from absence of a wrapped error.
3. If you must capture both streams separately, redirect to files: cmd 1> out.txt 2> err.txt (no merge), then read the files.
4. Treat known-benign stderr (uv's SSL_CERT_DIR warning, git's PowerShell quirk lines) as noise, not a failure signal.

**Hook enforcement (2026-08-25, PROMOTED):** `pre_bash_guard.py` blocks `2>&1` after a known native executable (git/uv/mypy/python/node/npm/docker/...) in PowerShell-tool commands, on comment/quote/here-string-stripped text. Cmdlet `2>&1` stays legal. Tests in `test_promoted_guards.py`.
