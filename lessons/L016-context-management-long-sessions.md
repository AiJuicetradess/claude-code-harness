---
id: L016
title: "Proactive context management in long sessions — summarize before compaction forces it"
category: workflow
severity: critical
status: active
created: 2026-03-28
last_triggered: 2026-09-01
times_violated: 8
times_checked: 0
tags: [context, compaction, cost, efficiency]
related_skills: [context-management]
---

**Rule:** In sessions that touch 5+ files or exceed 30 tool calls, proactively summarize processed files and shed spent context. Don't wait for automatic compaction — by then you've already lost context and will re-read the same files repeatedly.

**Why:** One session read the same module **40 times**, and two sibling modules 20 and 19 times — all because the session grew so large that compaction dropped file content, forcing re-reads, which burned more context, causing more compaction. This is a vicious cost spiral. Parallel sessions on another project also showed 3-5x re-reads on the same files.

**Prevention:**
1. After reading and understanding a file, write a brief summary of its key elements (functions, interfaces, behavior) in a scratchpad note
2. Use the `context-management` skill (currently 0 uses) when sessions extend past 30 minutes
3. At natural phase boundaries (design → implement → test), explicitly re-anchor: "What do I still need in context? What can I release?"
4. For files read 3+ times: stop and summarize the file instead of reading it again
5. For sessions touching 30+ tool calls and a single multi-thousand-line file: dispatch parallel subagents as a cache buffer instead of reading the file multiple times in the main session.
