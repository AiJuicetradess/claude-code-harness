---
id: L030
title: "Parallel tool calls on a shared resource cascade-cancel when one fails"
category: tool-usage
severity: critical
status: enforced
created: 2026-05-09
last_triggered: 2026-07-14
times_violated: 28
times_checked: 2
tags: [parallel-calls, cascade, git, batching, validation, wasted-cycles, pre-bash-guard]
related_skills: []
---

**Rule:** When firing N parallel tool calls that touch the same shared resource (git index, database transaction, the same filesystem subtree, the same MCP session), be aware that the harness will *cancel the remaining N-1 if any single one errors*. Pre-validate inputs before parallel-firing, OR run sequentially when calls are interdependent or share fail-fast semantics.

**Why:** The runtime's parallel-batch semantics are "any-failure aborts the batch," which is correct for many cases (don't waste calls if the first ones already failed) but it means a single typo in one input redoes the work for the others. Two recent observations:

1. **Git index pre-stage validation:** `git add` rejects pathspec that doesn't match. If you fire 4 parallel `git add` calls and one path is wrong, you get 1 real error + 3 `<tool_use_error>Cancelled: parallel tool call ... errored</tool_use_error>` and have to re-fire all 3 successful ones individually.
2. **Single-OS-tool flag mangling cascade:** A bash-mangled flag (`ipconfig /all` → `\all`) on one parallel call cancelled 3 unrelated parallel Bash calls (netstat / tasklist / ToolSearch).

The fix is not "stop using parallel" — parallelism is high-value when calls are truly independent. The fix is *input pre-validation when batching against a shared resource* and *sequencing when calls depend on each other*.

**Prevention:**
1. Before firing N parallel `git add` calls: run `git status --short` once and only stage paths you confirmed exist. Or stage in a single multi-arg `git add a b c d` call — atomic, no cascade.
2. Before firing N parallel Bash calls: each command should pass a 5-second sanity test. If any of them depends on Windows-specific syntax (forward-slash paths, `/flag` arguments) and the others are POSIX-clean, separate them — don't co-batch.
3. When batching reads/edits across files: parallel is fine, because each tool call is independent. When batching writes/commands against shared mutable state (git index, DB, lock files), prefer atomic multi-arg invocation OR sequential.
4. After receiving a `Cancelled: parallel tool call ... errored` message: do not re-fire the cancelled calls in another parallel batch with the same broken neighbor. Either fix the broken one first, or fire the surviving N-1 in a fresh batch without it.
5. **Heuristic:** the more your parallel batch looks like "do these 4 things to the same target," the more likely they should be sequential or atomic. The more they look like "look up these 4 unrelated facts in different places," the safer parallel is.

**Hook enforcement (2026-08-15, PARTIAL):** `pre_bash_guard.py` (matcher now Bash|PowerShell) takes a 15s lock on git-MUTATING commands (add/commit/checkout/push/... — read-only git exempt); a second git call from the same session inside the window is blocked with "combine into one chained command." Lock released by `post-bash-verify-tracker.sh`, self-expires otherwise. The other big cascade trigger — a Bash-mangled Windows command co-batched with safe calls — is eliminated at the source by the L003 blocks in the same hook. NOT covered: generic parallel batches (Read/Glob/Edit/MCP) with one bad input; that stays behavioral.
