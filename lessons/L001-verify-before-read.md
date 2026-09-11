---
id: L001
title: "Verify file existence before reading"
category: assumptions
severity: critical
status: enforced
created: 2026-03-13
last_triggered: 2026-08-14
times_violated: 40
times_checked: 6
tags: [file-io, verification, pre-read-guard]
related_skills: [cove-verification]
---

**Rule:** Always glob/grep for a file before attempting to Read it. Never assume a path exists.

**Why:** Sessions wasted on FileNotFoundError from assumed paths. The cove-verification skill requires this but the habit breaks under time pressure.

**Prevention:**
1. Use Glob to verify file exists before Read
2. If a path was mentioned in conversation but not verified, verify it
3. When given a relative path, resolve it against cwd before using
4. Never Read a path that ends with a directory name — always check if it's a file first

**Hook enforcement (2026-08-15):** `pre_read_guard.py` (PreToolUse: Read) BLOCKS Read on nonexistent paths — the block message names the nearest existing ancestor plus difflib close-matches so the retry is informed, not a second guess — and BLOCKS Read on directories with a Glob pointer. NOT covered: bad paths given to Grep/Glob/Bash (those fail soft on their own), and oversized-file reads (that is L029).
