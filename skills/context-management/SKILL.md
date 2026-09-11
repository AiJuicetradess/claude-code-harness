---
name: context-management
description: Use during long-running tasks, multi-file investigations, large codebase exploration, or any session where context accumulation threatens quality. Provides strategies for proactive summarization, phase-boundary compaction, and maintaining working memory clarity. Prevents context degradation in extended coding sessions.
---

# Context Management for Long-Running Sessions

## Overview

Long coding sessions accumulate context — file contents, grep results, test output, error logs, conversation history. As context grows, reasoning quality degrades: earlier details get lost, instructions drift, and the agent starts making assumptions instead of checking. This skill prevents that.

**Core principle:** Proactively manage what you're holding in working memory. Summarize aggressively, discard what's no longer needed, and re-anchor on the task at hand at every phase boundary.

## When to Apply

**Automatic triggers — do this without being asked:**
- You've read 3+ large files in the current task
- You've received a long test output or error log
- You're transitioning between phases (research → planning → implementation)
- The user changes the topic or task mid-session
- You notice yourself re-reading things you already processed
- You're about to start a complex multi-step implementation

**User triggers:**
- "Let's take stock" / "Where are we?"
- "Summarize what you know"
- "Fresh start on this"
- Session has been running for 10+ exchanges

## The Compaction Protocol

### Phase 1: Identify What to Keep

Before compacting, classify everything in your working context:

| Category | Action | Example |
|----------|--------|---------|
| Active task requirements | KEEP verbatim | "Add retry logic to the API client" |
| Current file being edited | KEEP | The function you're modifying right now |
| Function signatures you're calling | KEEP as reference | `parseConfig(path: string): Config` |
| Full file contents already processed | SUMMARIZE | 500-line file → key exports, structure, patterns |
| Test output (passing) | DISCARD | "47/47 tests pass" is sufficient |
| Test output (failing) | KEEP failure details only | Error message, stack trace, failing test name |
| Grep results already acted on | SUMMARIZE | "parseConfig used in 12 files, mainly in src/services/" |
| Boilerplate / imports / type declarations | DISCARD | Standard library imports add no value |
| Previous conversation about different topic | DISCARD | Old discussion not relevant to current task |
| Error logs already diagnosed | SUMMARIZE to root cause | "Root cause: missing null check in line 47" |

### Phase 2: Summarize

When summarizing file contents or investigation results, use this format:

```
## [filename] Summary
- **Purpose:** [one line]
- **Key exports:** [function names and signatures]
- **Patterns:** [relevant patterns for current task]
- **Dependencies:** [what it imports that matters]
- **Touch points:** [what imports/calls it that matters]
```

When summarizing investigation results:

```
## Investigation: [topic]
- **Finding:** [what you discovered]
- **Evidence:** [file:line references]
- **Implication:** [what this means for the current task]
- **Open questions:** [what still needs verification]
```

### Phase 3: Re-Anchor

After compacting, explicitly restate:
1. **Current task:** What am I trying to accomplish right now?
2. **Current step:** Where am I in the plan?
3. **Key constraints:** What must I not break?
4. **Next action:** What specifically am I doing next?

## Phase Boundary Compaction

At every major phase transition, perform a full compaction:

### Research → Planning
```
Compact: All research findings into structured summaries
Keep: File references, function signatures, dependency map
Discard: Raw file contents, full grep output, exploratory dead ends
Re-anchor: "Based on research, the plan is..."
```

### Planning → Implementation
```
Compact: Plan into actionable checklist
Keep: Step-by-step implementation plan, file paths, key signatures
Discard: Alternative approaches that were rejected, design discussion
Re-anchor: "Implementing step 1: [specific action]"
```

### Implementation Step N → Step N+1
```
Compact: Previous step's details
Keep: What was changed (file + summary), test results, remaining steps
Discard: The full code that was written (it's in the file now), debug output
Re-anchor: "Step N complete. Moving to step N+1: [specific action]"
```

### After Test Failure → Debugging
```
Compact: Everything except the failure
Keep: Exact error message, stack trace, failing test, relevant code
Discard: Passing test details, unrelated file contents
Re-anchor: "Test failing because [error]. Investigating [specific area]."
```

## Large Input Handling

When you receive large inputs, process them immediately rather than holding them raw:

**Large file (200+ lines):**
```
1. Read the file
2. Extract what's relevant to the current task
3. Note the file path for re-reading later if needed
4. Work with the extracted information, not the full file
```

**Large test output:**
```
1. Count pass/fail immediately
2. Extract failing test names and error messages
3. Discard passing test details
4. Work with the failure summary
```

**Large error log:**
```
1. Find the root error (often at the bottom)
2. Extract the relevant stack trace
3. Note the timestamp and error type
4. Discard the rest
```

**Large grep output:**
```
1. Count total matches
2. Group by file/directory
3. Extract the most relevant matches (closest to current task)
4. Summarize the pattern ("used in 23 files, mostly in src/services/")
5. Keep specific file:line references you'll need
```

## Working Memory Discipline

### The Three-Item Rule

At any point during implementation, you should be able to clearly state:

1. **What** — the specific thing you're doing right now (not the whole task)
2. **Where** — the exact file and function you're modifying
3. **Why** — the specific reason this change is needed

If you can't state all three, you've lost focus. Re-anchor before continuing.

### The Stale Context Rule

Information becomes stale and should be re-verified when:

- You read a file more than 5 exchanges ago → re-read before modifying
- A function signature was noted before running tests → re-check (tests may have changed things)
- An assumption was verified in a different part of the codebase → re-verify for current context
- You're referencing something from "earlier" without a specific file:line → re-find it

### The Blast Radius Rule

When a change touches shared code, explicitly track:

```
Blast Radius for [change]:
- Direct: [files that import/call the changed code]
- Indirect: [files that depend on direct dependents]
- Tests: [test files that cover this code]
```

Keep this in working memory until the change is verified. Discard after tests pass.

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Holding 5 full files in context | Can't reason about any of them well | Summarize to signatures and key logic |
| Re-reading the same file repeatedly | Wasting context on redundant reads | Summarize once, reference the summary |
| Keeping rejected approaches | Clutters decision-making | Note the rejection reason, discard details |
| Accumulating passing test output | Zero information value | "47/47 pass" is the only thing to keep |
| Not re-anchoring after digressions | Lose track of the actual task | Explicitly restate task after any tangent |
| Holding raw error logs | Most of the log is noise | Extract root cause, discard the rest |

## Integration with Other Skills

**Pairs with cove-verification:**
- After compacting, any summarized information should be re-verified before acting on it
- Summaries are for orientation, not for implementation decisions — always re-read the actual code

**Pairs with executing-plans:**
- Compact at each batch boundary in the plan
- Keep the plan checklist as the anchor, discard completed step details

**Pairs with systematic-debugging:**
- During long debugging sessions, periodically compact findings
- Keep the hypothesis and evidence, discard dead-end investigations

**Pairs with dispatching-parallel-agents:**
- When agents return results, immediately summarize each agent's findings
- Don't hold all three agents' full output simultaneously

## Session Health Check

Periodically ask yourself:

```
□ Can I state the current task in one sentence?
□ Can I name the exact file I'm working on?
□ Do I know the next specific action to take?
□ Am I holding any information I no longer need?
□ Have I re-verified any facts I'm relying on from earlier?
```

If any answer is "no" — stop and re-anchor before continuing.

## The Bottom Line

**Context is finite. Treat it like RAM, not a hard drive.**

Summarize what you've processed. Discard what's served its purpose. Re-anchor on what matters now. Re-verify before acting on memories.

The goal is not to remember everything — it's to always have the right information active for the current step.
