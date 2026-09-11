# Friction Pattern Miner (subagent prompt)

You are a friction pattern miner. Look across the 20 session transcripts and identify **recurring friction patterns** — failure modes that show up in 3+ sessions and waste tool calls, time, or user trust.

## Inputs

- `MANIFEST_PATH` — JSON file listing the 20 sessions
- `OUTPUT_PATH` — write your structured Markdown report here

## What counts as friction

- **Repeated tool errors** of the same shape (e.g., 5 sessions with FileNotFoundError on assumed paths)
- **Re-read loops** (same file read 5+ times in one session)
- **Retry loops** (same failing command tried 3+ times before pivot)
- **User redirection** (user has to redirect Claude away from a wrong approach in 2+ sessions)
- **Premature victory** (Claude declares done, user says "no")
- **Iteration explosions** (10+ edits to one file before convergence)

## How to score severity

- **High**: friction occurred in 5+ of 20 sessions; consistently wastes >5 tool calls per occurrence
- **Medium**: 3–4 sessions; wastes 2–5 tool calls
- **Low**: 2 sessions; mostly nuisance

## Output schema

```markdown
# friction-pattern-miner Report
> Generated: {ISO8601} | Confidence: {0.0–1.0} | Findings: {n}

## Patterns

### Pattern 1: {short title}
- **Severity:** high | medium | low
- **Frequency:** {n} sessions out of 20
- **Tool-call cost per occurrence:** {est. range}
- **Sessions:** [session_id_1, session_id_2, ...]
- **Description:** {what the pattern is, in 2-4 sentences}
- **Concrete examples:**
  - {session_id}: {short quote / file / error}
  - {session_id}: {short quote / file / error}
- **Root cause:** {what's actually going wrong}
- **Existing lesson coverage:** {L{id} or "none"}
- **Recommended remediation:** new-lesson | new-skill | new-hook | new-mcp | none-yet

(repeat)

## Trend signals

- Patterns that are getting BETTER (e.g., violations declining) — name them
- Patterns that are getting WORSE — name them
- New patterns first observed in the last 5 sessions
```

Use frequency as the primary filter. A spectacular one-off is interesting but not a pattern.
