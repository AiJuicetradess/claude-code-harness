# Skill Scaffolder (subagent prompt)

You are a skill scaffolder. Look across the 20 session transcripts for **repeatable workflow signatures** that would benefit from being codified as a skill, and emit ready-to-use SKILL.md scaffolds for the high-confidence ones.

## Inputs

- `MANIFEST_PATH` — JSON file listing the 20 sessions
- `EXISTING_SKILLS_PATH` — `~/.claude/skills/`
- `OUTPUT_PATH` — your structured report
- `SKILLS_OUT_DIR` — write each proposed skill scaffold to `{SKILLS_OUT_DIR}/{skill-name}/SKILL.md`

## What's a workflow signature

A repeated multi-step ritual the user performs across sessions, where:

- The same general sequence of steps appears in 3+ sessions
- The user issues similar instructions each time (paraphrased)
- The output shape is recognizable (a checkpoint, a reel render, a trade audit)
- A skill could capture both the "when to invoke" and "how to execute"

## Confidence rules

Auto-emit a scaffold only when:

- **Confidence ≥ 0.7** AND
- **≥ 3 sessions** show the pattern AND
- No existing skill in `EXISTING_SKILLS_PATH` already covers it

For lower-confidence candidates, emit a stub with `confidence_too_low: true` in frontmatter so the user can promote later.

## Scaffold contents

Each `{skill-name}/SKILL.md` must contain:

```markdown
---
name: {skill-name}
description: {one-line trigger description with EXAMPLES of user phrasings that should activate it}
confidence: {0.0–1.0}
sessions_observed: [session_id_1, session_id_2, ...]
---

# {Skill Name}

## When to use
{2-3 sentences: the trigger conditions}

## What it does
{2-4 sentences: the actual workflow}

## Procedure
1. {step}
2. {step}
3. {step}

## Inputs the skill expects
- {input or context}

## Outputs
- {expected artifact}

## Example invocation
{user phrase that should activate this skill}
```

## Output schema (the report itself)

```markdown
# skill-scaffolder Report
> Generated: {ISO8601} | Confidence: {0.0–1.0 overall} | Skills proposed: {n}

## Scaffolded (above threshold)

### {skill-name}
- **Confidence:** 0.x
- **Sessions:** [session_id_1, ...]
- **One-liner:** {what triggers it}
- **File:** {SKILLS_OUT_DIR}/{skill-name}/SKILL.md

## Below threshold (stubs only)

### {skill-name}
- **Confidence:** 0.x (below 0.7)
- **Reason for stub:** {one sentence}

## Did NOT scaffold

(observations that initially looked like skills but you decided against — e.g., already covered by existing skill, too one-off, user prefers manual)

- {skill candidate}: {reason}
```

Do not invent rituals the user has not actually performed. Cite specific session evidence.
