---
id: L011
title: "Use file-based scripts for complex remote commands — no inline nesting"
category: tool-usage
severity: critical
status: active
created: 2026-03-15
last_triggered: 2026-08-22
times_violated: 12
times_checked: 0
tags: [ssh, docker, shell-escaping, remote]
related_skills: []
---

**Rule:** When executing multi-line or JSON-heavy commands via SSH -> docker exec -> interpreter, write a script file, scp/copy it to the remote, and execute it. Never use deeply nested inline shell escaping.

**Why:** Triple-nested quoting (bash -> SSH -> docker exec -> node -e -> JSON template literals) breaks constantly. Across 3 sessions, 15+ syntax errors came from shell escaping alone, each requiring a retry. Writing a script file and executing it remotely succeeds on the first attempt.

**Prevention:**
1. If a command has more than 1 level of nesting (e.g., SSH + docker exec), write it to a temp file
2. Use heredoc (`cat <<'SCRIPT' > /tmp/fix.py ... SCRIPT`) to create the script, then execute it
3. For node/python one-liners: if they contain JSON, quotes, or template literals, use a file
4. Alternative: pipe the script via stdin (`cat script.py | ssh host 'docker exec -i container python'`)
5. **Local one-liners count too:** any `python -c` / `node -e` containing quotes-within-quotes (SQL strings, JSON, f-strings) in PowerShell 5.1 or Bash gets a scratchpad script file instead. Once ONE inline one-liner of a class has quote-mangled in a session, every subsequent one-liner of that class goes through a file — no reverting to inline later in the session.

**Hook enforcement (2026-08-25, WARN-ONLY):** `pre_bash_guard.py` injects a once-per-session non-blocking warn when an ssh command carries a heredoc or exceeds 300 chars inline — "write a script file, scp it, run that." Kept non-blocking because short legitimate inline ssh is the majority case; the deterministic failure shapes (dialect mixing, inline non-ASCII python) are separately hard-blocked under L035/L018.
