---
id: L017
title: "Don't poll containers with sleep+retry loops — use targeted commands or report to user"
category: workflow
severity: critical
status: active
created: 2026-03-28
last_triggered: 2026-05-28
times_violated: 5
times_checked: 2
tags: [docker, containers, efficiency, polling]
related_skills: [systematic-debugging]
---

**Rule:** When waiting for a Docker container to start or a process to produce output, don't blindly retry `sleep N && docker compose logs` in a loop. Use targeted diagnostic commands or report the status to the user and ask how to proceed.

**Why:** One session had **37 identical consecutive bash retries** — mostly `docker compose up -d`, `sleep 90 && docker compose logs`, and `sleep 120 && docker compose logs` cycles. Each retry consumed a tool call, burned context, and provided no new diagnostic information.

**Prevention:**
1. After `docker compose up -d`, check container status with `docker compose ps` (instant, no sleep)
2. If a container is running but not producing expected output, use `docker compose logs --tail=50 <service>` once — don't loop
3. If the container is crash-looping, check `docker compose logs <service> 2>&1 | tail -30` for the actual error
4. After 2 failed checks, **report to the user** with what you've found rather than continuing to poll
5. Use `run_in_background` for long-running commands instead of sleeping in foreground
