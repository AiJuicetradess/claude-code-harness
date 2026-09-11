---
name: session-resume-from-memory
description: Use when the user opens a session with phrases like "refer to your memory", "review the project", "prepare to assist me further", "pick up from the last session", "had to restart my computer", "familiarize yourself with the current state", or names a project then says "what did we leave off on". Loads project-scoped MEMORY.md, reads recent plan/checkpoint files, and produces a one-screen status anchor before any new work begins.
confidence: 0.88
sessions_observed: [13271f2e-dd50-4df1-ba82-c4e9420f3034, f44df517-1267-42fd-a038-58ede861f471, 73940990-2326-4203-aeee-60670f717944, 0121268d-446f-42e2-9146-573ace32cf20, 4333a814-4782-426b-972f-3698261247fb, e0408977-44ba-4b94-b0a8-67a990ac0b0e, 04dd4206-ee06-4d04-a91f-03aec56cf603, e022098a-cc69-4ee6-bde7-8bcf2cf3c9b2, b83b5a28-ee07-48ed-84c5-5c39b2a2e752, 883a204b-4c8e-4ae6-b094-2d8ca9eec277, a273437c-b449-4743-804e-6ad905aef08c, adfafa5e-d339-4221-bb9f-e51fa9946aab, 0e1a7603-5e4e-4d79-b179-04c0a9a048e9]
---

# Session Resume From Memory

## When to use

The user opens a fresh session and asks Claude to re-orient itself within a *specific* project (not a cross-project briefing). Trigger phrases observed across 13 of the last 20 sessions: "refer to your memory and review the project", "prepare to assist me further", "pick up from the last session", "Hey Claude. I had to restart my computer which interrupted our conversation", "familiarize yourself with the current status of [project]", "Start by reading the checkpoint, then read the FULL [file]". This is distinct from `context-management` (which compacts mid-session).

## What it does

Reads the project-scoped `MEMORY.md` index, opens the 1-3 most recently dated plan / checkpoint / changelog files referenced from it, scans the latest commit messages, and produces a five-line "where we are" anchor in the response: current goal, last completed milestone, next pending step, known blockers, and the file Claude should re-read first before touching code. No code edits in this turn — just orientation.

## Procedure

1. **Identify the project root** from the cwd or from the user's quoted path. If they pasted a path, use the deepest directory that contains either `.claude/projects/...memory/MEMORY.md` or `docs/plans/`.
2. **Read the project memory index** at `~/.claude/projects/{project-slug}/memory/MEMORY.md` if it exists. If the file is more than 7 days old, flag that in the anchor — memories drift.
3. **Open the latest 1-3 plan/checkpoint files** the index points at (look for `docs/plans/YYYY-MM-DD-*.md` or memory entries flagged "checkpoint" / "status"). Prefer files dated within the last 14 days.
4. **Run `git log --oneline -n 10`** in the project root if it is a git repo, so the anchor reflects code state, not just doc state.
5. **Produce a five-line anchor** in this exact shape:
   - **Goal:** {one-line goal carried over from memory}
   - **Last done:** {most recent completed milestone, with file or commit reference}
   - **Next step:** {single concrete next action — pulled from plan, not invented}
   - **Blockers:** {any flagged in memory or commit messages, or "None known"}
   - **Re-read first:** {the file most likely to be edited — usually a `signal_runner.py`, `produce_reel*.py`, or active plan doc}
6. **Wait for the user to confirm** before doing any edits. The point is alignment, not action.

## Inputs the skill expects

- The project's cwd (from the conversation environment) or a quoted absolute path
- Read access to `~/.claude/projects/{project-slug}/memory/` and the project's `docs/plans/` directory
- Optional: `git` available in the project root

## Outputs

- A five-line anchor block in the assistant response (Goal / Last done / Next step / Blockers / Re-read first)
- A flag in the same response if memory files are stale (>7 days), so claims are calibrated
- No edits, no commits, no script execution in this turn

## Example invocation

User: *"Hey Claude. I had to restart my computer which interrupted our conversation. Can you refer back to your memory and find out what we were talking about last?"* (verbatim from sessions a273437c, adfafa5e, 0e1a7603)

User: *"Alright, go ahead and familiarize yourself with the current status and state of the Acme project. Refer to your memory and prepare to assist me further."*

User: *"Start by reading the checkpoint, then read the FULL signal_runner.py before touching anything."* (verbatim from session b83b5a28)

## Anti-patterns

- **Do not** start writing code in the same turn as the resume. The user's intent is to align first.
- **Do not** invent a "next step" — pull it from the plan or memory; if neither names one, say "Next step is unclear from memory; please confirm direction."
- **Do not** load every memory file. Three is the cap. The point is a *one-screen* anchor.
- **Do not** turn this into a multi-project briefing. This skill is single-project.
