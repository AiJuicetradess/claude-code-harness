---
id: L044
title: "Standing user model-selection rules override skill economy guidance - check feedback memories before dispatching subagents"
category: workflow
severity: high
status: active
created: 2026-08-14
last_triggered: 2026-08-27
times_violated: 2
times_checked: 0
tags: [subagents, model-selection, sdd, user-rules]
related_skills: [subagent-driven-development]
---
**Rule:** The SDD skill's model-economy guidance ("use the least powerful model", "cheap tier for scoped re-reviews") is a DEFAULT that the user's standing rules override. The user has a locked rule: ALL code-touching review subagents use the top tier (feedback_code_review_opus_only, now Fable). Before dispatching any reviewer/implementer, check project + global feedback memories for a standing model directive and apply it without being reminded.

**Why:** Skill text arrives fresh each session and looks authoritative; the user's rule lives in memory and is easy to skip when the skill says "conserve cost". User instructions > skills - the precedence is explicit in using-superpowers.

**Prevention:**
1. At SDD setup (before Task 1 dispatch), write the resolved model policy into the ledger: implementer model X (user-directed), reviewer model Y (user rule), citing the memory that set it.
2. If a skill default and a user memory conflict, the memory wins; note the override in the ledger rather than silently following the skill.
