---
id: L046
title: "Re-read a shared artifact before republishing - cross-session versions conflict"
category: tool-usage
severity: high
status: active
created: 2026-08-23
last_triggered: 2026-08-22
times_violated: 1
times_checked: 0
tags: [artifact, publish, version-conflict, multi-session, stale-state]
related_skills: []
---
**Rule:** Before publishing to an artifact URL that this session did not itself publish last (a `url:` passed in, an artifact resumed from a prior session, or any artifact after a republish notice), Read the artifact first (`action: "read"`), merge your changes onto the latest content, then publish. Never reach for `force: true` to get past the conflict — it discards the other session's version and is only for explicit user instruction.

**Why:** Artifacts are shared mutable state across sessions (and across page-self-saves). Publishing from a local file that predates another writer's version gets rejected with "This session hasn't viewed the latest version of the artifact" — one wasted turn, and the local file is silently behind. This is the artifact-shaped twin of L033's sub-rule: any resource another writer may have touched since your last read is a drift candidate.

**Prevention:**
1. Publishing with a `url` parameter to an artifact this session didn't just publish → Artifact `action: "read"` FIRST, then apply edits to the fetched latest content, then publish.
2. On a version-conflict rejection: re-read, merge, republish. `force: true` only when the user explicitly says to discard the newer version.
3. After any republish notification on a watched artifact: treat the local file as stale until re-read.
