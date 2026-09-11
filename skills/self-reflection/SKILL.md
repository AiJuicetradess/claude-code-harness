---
name: self-reflection
description: "Analyze recent session transcripts to extract lessons, detect repeated mistakes, and update the lessons store. Invoke when reminded about unreflected sessions, when the user asks for reflection, or periodically after significant work."
---

# Self-Reflection: Post-Session Analysis

You are performing a structured self-reflection to identify mistakes, extract lessons, and update the lessons store. Follow each phase exactly.

## Phase 1: Select Sessions

1. Read `~/.claude/reflections/session-log.jsonl`
2. Filter for entries where `"reflected":false`
3. Sort by timestamp descending, take the most recent 5 (or all if fewer)
4. Skip sessions with fewer than 10 `message_lines` (too short for useful analysis)
5. For transcripts larger than 2MB, plan to read only user messages and tool errors (not full content)

If there are no unreflected sessions, report that and stop.

## Phase 2: Analyze Each Transcript

For each selected session, read the transcript file (JSONL format where each line is a JSON object with `type` field).

**MANDATORY (L018, violated by the miner itself 3x — 2026-05-07, 2026-08-14, 2026-08-26):** any Python script that prints or processes transcript content MUST be launched with `PYTHONIOENCODING=utf-8` (e.g. `PYTHONIOENCODING=utf-8 python extract.py ...`). Transcript data always contains non-ASCII; ASCII-only print literals do NOT protect you — the crash comes from the data. The pre_file_guard hook cannot catch this variant.

Extract and analyze these 5 signal types:

### 2a. Tool Errors
Find all entries where a `tool_result` has `is_error: true`. These are objective failures — wrong paths, missing files, failed commands. Each is a potential lesson.

**EXCLUDE enforcement noise.** An error emitted by a guard doing its job is prevention working, NOT a violation. Do not count:
- pre-edit-guardian blocks ("BLOCKED: You have not Read...", "consecutive edits ... without a verification read")
- the built-in Edit/Write "File has not been read yet" safety error
- pre_bash_guard / pre_file_guard / pre_read_guard blocks (and their legacy names in older transcripts: pre-env-block / pre-secrets-scan / pre-destructive-git / pre-edit-guardian)
- permission denials and auto-mode classifier denials

Only count errors that got PAST the guards (or that no guard covers). When a guard fired, increment the matching lesson's `times_checked` instead — that is the compliance denominator internalization decisions need.

Record: what tool failed, what input caused it, what the error message was.

### 2b. User Corrections
Find user messages that immediately follow an assistant message AND contain correction signals:
- Explicit negation: "no", "that's wrong", "not what I asked"
- Redirection: "I meant...", "actually...", "what I want is..."
- Frustration: "you keep...", "again?", "I already said..."
- Re-explanation: user repeats something they said earlier

For each correction, record: what the assistant did wrong, what the user wanted instead.

### 2c. Assumption Failures
Find sequences where the assistant states something confidently, then has to backtrack — either because of a subsequent tool error or user correction.

Record: what was assumed, what was actually true.

### 2d. Wasted Cycles
Find cases where:
- The same tool is called 3+ times on similar inputs (retry loops)
- A file is read that was already read earlier in the session
- An approach is tried, fails, and a completely different approach is needed

Record: what was wasted, what the efficient path would have been.

### 2e. Cross-Session Patterns
Compare findings across all analyzed sessions. If the same type of error appears in 2+ sessions, flag it as a high-priority pattern.

## Phase 3: Generate/Update Lessons

For each detected issue:

1. **Read existing lessons:** Glob `~/.claude/lessons/L*.md` and read each to check for matches
2. **If a matching lesson exists** (same category and similar root cause):
   - Increment `times_violated` in the frontmatter
   - Update `last_triggered` to today's date
   - Add new evidence to the bottom of the file
3. **If no matching lesson exists**, create a new one:
   - Assign the next available ID (L006, L007, etc.)
   - Choose category: `assumptions` | `coding` | `workflow` | `tool-usage` | `communication`
   - Set severity based on impact:
     - User correction → `high`
     - Tool error → `high`
     - Wasted cycles → `standard`
     - Cross-session pattern → `critical`
   - Write concrete, specific prevention steps (not vague advice)
   - Use the standard lesson file format (see existing lessons for template)

## Phase 4: Regenerate LESSONS.md

After processing all sessions:

1. Read ALL lesson files from `~/.claude/lessons/L*.md`
2. **Promote:** Any lesson with `times_violated >= 5` → set `severity: critical`
3. **Enforce (escalation rung):** Any active lesson with `times_violated >= 20` whose rule a deterministic hook already enforces (a hook name appears in its `tags`, e.g. `pre-edit-guardian`) → set `status: enforced`. Enforced lessons leave the LESSONS.md tiers — the hook does the work; stop paying per-session context for the reminder and stop re-counting the guard's own blocks. Any lesson at `times_violated >= 20` with NO enforcing hook → add a "convert this lesson to a hook" TODO to the Phase 6 report. Recording more violations of an unenforced 20+ lesson is waste (poka-yoke: move from detection to prevention).
4. **Internalize:** Any lesson with `times_violated: 0` AND `last_triggered` more than 30 days ago → set `status: internalized`
5. **Archive:** Any lesson with `status: internalized` for more than 90 days → move file to `~/.claude/lessons/archive/`
6. **Reactivate:** If an internalized lesson was just violated → set `status: active`, `severity: high`. If a hook backing an `enforced` lesson is removed from settings.json, reactivate that lesson the same way.
7. Sort active lessons: critical > high > standard, then by `times_violated` descending within each tier
8. Write the top 20 active lessons to `~/.claude/lessons/LESSONS.md` in this format:

```markdown
# Active Lessons (auto-generated by /reflect)
> Last reflection: {today's date} | Active: {count} | Internalized: {count}
> Hook-enforced (not listed; hooks do the work): {comma-separated ids, e.g. L013, L021}

## Critical
- **L{id}** [{category}] {title} (violations: {n})

## High
- **L{id}** [{category}] {title} (violations: {n})

## Standard
- **L{id}** [{category}] {title} (violations: {n})

## Internalized (0 violations 30+ days)
- ~~L{id} [{category}] {title}~~
```

Cap LESSONS.md at approximately 3KB to stay within context budget.

## Phase 5: Mark Sessions Reflected

For each processed session in `session-log.jsonl`:
- The JSONL is append-only, so create a new version of the file with `reflected` set to `true` for processed entries
- Alternatively, append a reflection record: `{"type":"reflection","timestamp":"{now}","sessions_analyzed":[...],"lessons_created":[],"lessons_updated":[]}`

Then append to `~/.claude/reflections/reflection-log.jsonl`:
```json
{"timestamp":"{now}","sessions_analyzed":5,"lessons_created":["L006"],"lessons_updated":["L001","L003"],"promoted":[],"internalized":[]}
```

## Phase 6: Report

Summarize what you found to the user:
- Number of sessions analyzed
- Key mistakes identified (with specific examples)
- Lessons created or updated
- Any promotions or internalizations
- Current lesson counts by severity

## Important Rules

- **Be specific, not vague.** "Always verify files" is too weak. "Use Glob before Read for any path not verified in the current session" is actionable.
- **Root cause, not symptom.** Don't create a lesson for "fix the typo" — create one for "verify variable names against actual codebase before using them."
- **One lesson per root cause.** Don't create 3 lessons for 3 instances of the same underlying issue.
- **Evidence required.** Every lesson must cite the session and specific error that prompted it.
- **Never delete lessons.** Internalize and archive, but never delete. They may reoccur.
