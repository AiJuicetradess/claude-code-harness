---
id: L029
title: "Read on speculative-large files without size pre-check — token cap blocks"
category: tool-usage
severity: critical
status: enforced
created: 2026-05-09
last_triggered: 2026-07-16
times_violated: 11
times_checked: 1
tags: [read, token-cap, file-size, plans, configs, json]
related_skills: [cove-verification]
---

**Rule:** Before Reading any file in these high-risk classes — multi-week plans, full project specs, complete brochure JSON, full carousel `slides.json`, transcript JSONLs, full LLM prompt template files — pre-check size and use `offset`/`limit` from the start. The Read tool hard-caps at ~25K tokens (general) and ~10K tokens (plan files), and when it fires it forces a wasted retry plus a re-orientation.

**Why:** This is structurally distinct from L001 (file existence). The file *exists*; you just can't fit it into one Read call. The hard cap is enforced silently — there is no "warning at 8K, error at 10K" — the call returns an error mid-flow, and you have to either chunk-read or pivot to Grep. Two recent instances both wasted ~1 round-trip and ~1 minute of session time. Both files were *known content classes* — a `.md` plan, a project `slides.json` — both could have been size-probed in 1 cheap Bash call before the Read.

**Prevention:**
1. Before Reading a file in any of these classes, do `wc -c` (bytes) or `wc -l` (lines) first. Heuristic: anything over ~50KB or ~600 lines will likely exceed the cap.
2. If you only need a section, search-then-read: Grep for the section header, then Read with `offset` and `limit` around the match.
3. For multi-week implementation plans (`docs/superpowers/plans/*.md`) — these run 8-15K tokens routinely. Default to `Read` with `limit: 200` and Grep for sub-sections you need.
4. For `slides.json` / full template carousel files in this project — these run 30-50K tokens. Always `offset/limit` or `Grep` for the slide ID you need.
5. Subagents consume their own Read budget. If dispatching a subagent to "read a plan and report on X," include explicit chunking instructions or have it Grep first.
6. **Do not retry the same Read after a token-cap error** — go straight to Grep + offset/limit. Retrying in any form (e.g., adding `limit: 1000` blindly) wastes another round-trip if the offset is wrong.

**Hook enforcement (2026-08-25, PROMOTED):** `pre_read_guard.py` blocks a no-limit Read on any text file >50KB (message says to re-send with limit/offset or Grep first) and blocks ANY Read of a >50KB single-line blob (no newline in first 64KB — offset/limit cannot chunk one line; use Grep -o or a python script). Media/PDF/notebook extensions exempt. Tests in `test_promoted_guards.py`.
