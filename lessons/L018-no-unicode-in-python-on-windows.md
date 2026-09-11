---
id: L018
title: "Never use Unicode characters in Python print statements on Windows"
category: coding
severity: critical
status: enforced
created: 2026-04-06
last_triggered: 2026-09-02
times_violated: 14
times_checked: 2
tags: [windows, python, unicode, encoding, cp1252]
related_skills: []
---

**Rule:** Never use Unicode symbols (arrows →, checkmarks ✓, warnings ⚠, bullets •) in Python print statements or f-strings on Windows. Use ASCII alternatives (-->, [OK], [!], -).

**Why:** Windows console uses cp1252 encoding by default, not UTF-8. Any Unicode character outside cp1252 causes `UnicodeEncodeError` at runtime. This is a cross-session recurring pattern — the same bug (→ arrow in print statements) appeared in 2 completely separate sessions on different projects, wasting 6+ tool calls each time as characters were fixed one by one.

**Prevention:**
1. When writing Python scripts: use only ASCII in print/log statements
2. If Unicode is aesthetically needed: set `PYTHONIOENCODING=utf-8` at the top of the script, or use `sys.stdout.reconfigure(encoding='utf-8')`
3. After writing a script with any formatted output: grep for non-ASCII characters before running (`grep -P '[^\x00-\x7F]' script.py`)
4. Fix ALL Unicode characters in one pass with `replace_all`, not one at a time

**Hook enforcement (2026-08-25, PROMOTED):** `pre_file_guard.py` blocks Write/Edit payloads to `.py`/`.pyw` files whose print()/logging lines contain non-ASCII (comments/docstrings stay free; escape hatch when the payload or file declares PYTHONIOENCODING / reconfigure(encoding / TextIOWrapper). `pre_bash_guard.py` blocks inline python source (`-c` / stdin heredoc) containing non-ASCII in both shells — cp1252 pipes corrupt it before the interpreter runs. Tests in `test_promoted_guards.py`.
