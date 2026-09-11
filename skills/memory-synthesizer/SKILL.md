---
name: memory-synthesizer
description: Use at session end (or via `/synthesize-memory`) to mine the last N sessions for new lessons, contradictions vs current MEMORY.md, recurring friction patterns, tooling gaps, and skill-worthy workflows. Dispatches 5 parallel subagents and returns a single review surface — proposed memory diff, generated skill scaffolds, and a kill list of obsolete lessons. Triggers: "synthesize memory", "what should I learn from the last N sessions", "build me skills from my workflow", "find tooling gaps", "what lessons should I retire".
---

# Memory Synthesizer

A continuously-improving feedback loop that turns recent session activity into durable upgrades to MEMORY.md, lessons, and skills.

## When this fires

- Manually: user invokes the skill or types `/synthesize-memory` (if a slash command alias is registered)
- Periodically: a SessionEnd hook can `bash run_synthesis.sh` after long sessions
- After major work: when the user finishes a feature, audit, or campaign and wants to capture meta-learnings

This skill is **not** for one-off bug fixes — use `self-reflection` for those (it processes the last 5 sessions for direct lesson extraction). This skill takes a wider 20-session view and produces tooling/architecture proposals, not just lesson updates.

## How it works

```
session-log.jsonl + last 20 transcripts
              │
              ▼
   ┌──────────────────────┐
   │  Manifest builder    │  → manifest.json (transcript paths, metadata)
   └──────────────────────┘
              │
              ▼
   ┌─────────────────────────────────────────────────┐
   │  5 PARALLEL SUBAGENTS (single Agent batch)      │
   ├─────────────────────────────────────────────────┤
   │  1. lesson-extractor                            │
   │  2. contradiction-detector (vs MEMORY.md)        │
   │  3. friction-pattern-miner (cross-session)      │
   │  4. tooling-gap-identifier                      │
   │  5. skill-scaffolder                            │
   └─────────────────────────────────────────────────┘
              │
              ▼ (writes structured Markdown to agent-outputs/)
   ┌──────────────────────┐
   │  Synthesis (main)    │  → review.md, memory-diff.md, kill-list.md, proposed-skills/
   └──────────────────────┘
              │
              ▼
   USER REVIEW SURFACE
```

Synthesis happens in the main thread, not a 6th agent, so the user sees one consolidated review — not five separate reports.

## Subagent contract

Each of the 5 subagents receives:

- `manifest_path`: absolute path to `manifest.json` listing the 20 transcripts
- `output_path`: absolute path where this agent must write its structured Markdown report
- `current_memory_path`: absolute path to `MEMORY.md`
- `lessons_dir`: absolute path to `~/.claude/lessons/`

Each agent's output is a Markdown file with this header:

```markdown
# {agent-name} Report
> Generated: {timestamp} | Confidence: {0.0–1.0 overall} | Findings: {n}
```

followed by structured findings — see `prompts/<agent>.md` for the exact schema each agent must emit.

## Confidence threshold

Skill scaffolds are only auto-generated when **confidence ≥ 0.7** AND the underlying pattern appears in **≥ 3 sessions**. Below that, the skill-scaffolder still flags the candidate but emits a stub with `confidence_too_low: true` so the user can decide.

## What synthesis produces (the review surface)

| File | Purpose |
|------|---------|
| `review.md` | Single-page summary the user reads first |
| `memory-diff.md` | Proposed adds/updates/removes for MEMORY.md (Markdown diff format) |
| `kill-list.md` | Lessons proposed for internalization or archive |
| `proposed-skills/<name>/SKILL.md` | Auto-generated skill scaffolds for accepted candidates |
| `agent-outputs/*.md` | Raw subagent reports (kept for audit) |

## Running it

```bash
bash ~/.claude/skills/memory-synthesizer/run_synthesis.sh
# or invoke directly through the Skill tool — Claude Code will orchestrate the 5 agents.
```

Run artifacts go to `~/.claude/skills/memory-synthesizer/runs/{YYYY-MM-DD}/`. Old runs are kept for trend analysis.

## What the user MUST review (not auto-applied)

- The memory diff — none of the proposed changes to MEMORY.md are applied automatically
- Each new skill scaffold — they're created in `proposed-skills/`, not the live skills directory
- The kill list — lessons are flagged, not deleted

## Why a skill, not a plain command

Because the orchestration logic (5 parallel agents, contract enforcement, synthesis) is non-trivial and the schemas the agents emit must stay in sync with the synthesizer. Bundling everything as a skill keeps the contract co-located with the prompts.
