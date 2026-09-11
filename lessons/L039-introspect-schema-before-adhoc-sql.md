---
id: L039
title: "Introspect the live target before ad-hoc commands — never a remembered/guessed schema, DB role, or container name"
category: coding
severity: critical
status: active
created: 2026-07-15
last_triggered: 2026-09-01
times_violated: 7
times_checked: 0
tags: [sql, sqlite, postgres, schema, pragma, adhoc-scripts, verification, docker, container-names, db-role, remote-ops]
related_skills: [cove-verification]
---

**Rule:** Before writing ad-hoc SQL — or a check script embedding SQL — against any database, introspect ground truth first: `PRAGMA table_info(...)` / `.tables` for sqlite, `\dt` / `\d table` for postgres, or read the module that owns the CREATE statements. This applies even to a schema you built earlier in the same session, and doubly to the question "which database is this table in".

**Why:** Three crashed scripts across two sessions on the same day, each wasting a write+run cycle plus a diagnosis turn. The sharpest case: the session that built the schema itself (pairsniper T1) guessed wrong about it twice, hours later — one script even printed the real column list immediately before crashing on its own hardcoded wrong column. Session-memory of a schema is not ground truth; 10 seconds of introspection is cheaper than any failed run.

**Prevention:**
1. First statements of any ad-hoc DB script: introspect the schema, assert the expected tables/columns exist, and on mismatch fail by printing the REAL schema (so the retry is free).
2. When the DB was created by project code, read that code's CREATE statements (e.g., journal.py) instead of recalling them.
3. "Which DB holds table X?" is a query, not a memory: list databases/tables first before pointing psql at one (claude_spend lived in the n8n DB, not dr_leads).
4. Applies to column names, table names, AND database selection — all three failed this week.

5. **Remote ops identifiers are schema too.** Before the first `docker exec <name>` run `docker ps --format '{{.Names}}'`; before the first `psql -U <role>` derive the role from the compose file or env (`grep -o 'DATABASE_URL=postgresql://[^:]*' <env>` / `POSTGRES_USER`) — one probe, then the real command. Handing the USER a command built on a guessed identifier is worse: their round-trip is the expensive one.
