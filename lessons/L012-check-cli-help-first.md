---
id: L012
title: "Check CLI --help before trial-and-error flag combinations"
category: workflow
severity: high
status: active
created: 2026-03-15
last_triggered: 2026-07-14
times_violated: 4
times_checked: 0
tags: [cli, docs, trial-and-error]
related_skills: []
---

**Rule:** Before running an unfamiliar CLI command, run `command --help` or `command subcommand --help` first to see available flags. Never guess flag syntax through trial-and-error.

**Why:** Trial-and-error wastes 3-5 tool calls per command. In one session, 5 different n8n export flag combinations were tried before finding the right syntax. A single `--help` call would have shown the correct flags immediately.

**Prevention:**
1. First call: `tool --help` or `tool subcommand --help`
2. Read the output for available flags, required args, and examples
3. Then construct the correct command on the first real attempt
4. For complex tools (n8n, docker, kubectl): check docs if --help is insufficient
