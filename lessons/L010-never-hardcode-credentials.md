---
id: L010
title: "Never hardcode credentials in scripts or commands — use env vars"
category: coding
severity: critical
status: active
created: 2026-03-15
last_triggered: 2026-06-22
times_violated: 8
times_checked: 1
tags: [security, credentials, secrets, env-vars]
related_skills: []
---

**Rule:** Never embed passwords, API keys, or tokens directly in script content or inline shell commands. Always use environment variable references ($VAR, os.environ['VAR'], process.env.VAR). This is CLAUDE.md Rule 7.

**Why:** Hardcoded credentials appear in tool output, shell history, error traces, and git commits. In one session, a Firecrawl API key was exposed in a SyntaxError stack trace when shell variable expansion failed. In another, a GoDaddy SFTP password was embedded in 20+ paramiko scripts.

**Prevention:**
1. For SSH commands: set env vars on the remote first (`export KEY=...`), then reference them in scripts
2. For inline scripts via SSH: pass credentials as env vars in the SSH command (`KEY=$KEY ssh ... 'echo $KEY'`)
3. For Python scripts: always use `os.environ['VAR']` — fail loudly if missing
4. Be especially careful with nested shell contexts (SSH -> docker exec) where variable expansion timing is tricky
5. If a credential must be used inline temporarily: delete the command from history immediately after
