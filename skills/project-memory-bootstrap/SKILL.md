---
name: project-memory-bootstrap
description: Wire memory-currency infrastructure into any project or repo — produces a cwd-router entry, a domain preflight skill, a structured MEMORY.md, and the session-checkpoint convention that keeps memory fresh across sessions. Use when the user says "set up memory for [project]", "make this durable", "replicate the memory pattern", "bootstrap a new repo", "wire memory currency", "stop memory drift on [project]", or "do what [project A] does on [other project]".
---

# Project Memory Bootstrap

A reusable scaffolder for the 4-piece memory-currency pattern. Reproduces, for any new project or repo, the same wire-up that keeps a mature project's memory current across 100+ sessions while a freshly-bootstrapped project drifts within 24 hours.

## What the 4-piece pattern is

Memory currency on Claude Code is NOT automated by hooks. The hooks (`pre_file_guard`, `pre_bash_guard`, `session-end-capture`, etc.) are a *floor* that prevents regression. They do not write memory. Memory currency requires **discipline + scaffolding** — this skill produces the scaffolding so the discipline has something to attach to.

The 4 pieces:

| # | Piece | What it does | Lives at |
|---|---|---|---|
| 1 | **cwd-router entry** | One JSON entry that auto-suggests the domain preflight skill when cwd matches | `~/.claude/hooks/cwd-skill-map.json` |
| 2 | **Domain preflight skill** | 5-step cold-start grounding ritual — reads canonical docs, probes infra, surfaces state | `~/.claude/skills/{domain}-preflight/SKILL.md` |
| 3 | **Structured MEMORY.md** | Index with "Recently completed" star-rated section + Project / Infrastructure / User / Workflow Rules sections | `~/.claude/projects/{slug}/memory/MEMORY.md` |
| 4 | **Session-checkpoint convention** | `session_YYYY_MM_DD_<topic>.md` at end of each meaningful session, with one-line entry added to MEMORY.md | `~/.claude/projects/{slug}/memory/session_*.md` |

Without piece 2, sessions don't auto-ground in current state and drift goes undetected. Without piece 4, the index has nothing to index and `MEMORY.md` becomes a 3-line stub.

## When this fires

- User mentions: "set up memory for", "bootstrap memory", "make this durable", "replicate the memory pattern", "stop memory drift on", "wire memory currency", "do what [project A] does on", "make a preflight for"
- User just finished a memory-restructure on one project and wants to replicate elsewhere
- User opens a fresh repo and wants memory wired before substantive work begins

Do NOT auto-fire from session start. This is a setup tool, not a diagnostic.

## Procedure

### Inputs to gather (use AskUserQuestion if not supplied)

1. **Project name** (human-readable, e.g. "Research Platform", "Acme Site", "Client Portal")
2. **Project root path** (absolute, e.g. `C:/Users/you/Projects/my-app`)
3. **Domain shorthand** for skill naming (e.g. `quant-research`, `acme`, `client-portal`) — used in `{domain}-preflight`
4. **One-line system description** (e.g. "Regime-conditioned alpha research platform — 4-agent system")
5. **Canonical docs in repo** (e.g. `design/agent-1-design.md`, `docs/architecture.md`, `README.md`) — the preflight skill will read these
6. **Infra surfaces to probe**: which of these apply?
   - Git state (almost always)
   - Env vars (which keys? names only, never values)
   - Supabase MCP (which project_id, which tables?)
   - SSH server (host alias, which docker containers?)
   - Playwright MCP (yes/no)
   - Local tooling presence (which binaries — pdftoppm, ffmpeg, python, etc.)
   - Local artifact freshness (which dirs to ls -t?)

### Step 1 — Derive the slug and confirm paths

```text
project_slug = cwd path with "/", " ", ":", "\" -> "-" then strip leading "-"
  example: "C:/Users/you/Projects/my-app" -> "C--Users-you-Projects-my-app"
project_memory_dir = ~/.claude/projects/{project_slug}/memory/
skill_name = {domain}-preflight
skill_path = ~/.claude/skills/{skill_name}/SKILL.md
```

Confirm both target paths to the user before writing.

### Step 2 — Build the cwd-router entry

Add to `~/.claude/hooks/cwd-skill-map.json` (this is a hook-config edit; requires explicit user approval — surface as such):

```json
"{distinctive-substring-of-cwd}": {
  "skill": "{domain}-preflight",
  "description": "{one-line system description}"
}
```

The substring must be distinctive enough not to false-match other projects. Prefer the deepest unique segment (e.g. "Research output" not "Research"). Test against the existing entries before committing.

### Step 3 — Generate the domain preflight skill

Use this template (fork-and-adapt from an existing `*-preflight/SKILL.md` if you have one):

```markdown
---
name: {domain}-preflight
description: Cold-start preflight for {one-line description}. Use when the user mentions {trigger keywords list}, or starts work in `{cwd substring}`. Auto-invoke from session-start-cwd-router.sh when cwd matches {substring}.
---

# {Project Name} — Cold-Start Preflight

A 5-step grounding ritual that runs before any work on {project}. {one-paragraph "what this catches"}.

## When this fires
- Auto-invoked by `session-start-cwd-router.sh` when cwd contains `{substring}/`
- Manually via `/{domain}-preflight`
- When user mentions: {trigger keywords}

## Reference memory (read before probing)
- `~/.claude/projects/{slug}/memory/{canonical-project-memory}.md` — the system map
- `~/.claude/projects/{slug}/memory/{canonical-sprint-memory}.md` — the active sprint
- {other 1-2 most-important memories}

## Preflight steps

### Step 1 — Read the canonical doc
{cat the design doc / README / architecture doc}

### Step 2 — Git state probe
{git status, git log -8, branch}

### Step 3 — Env presence (existence only, never value)
{python -c presence check per L010}

### Step 4 — Service / infra probe
{Supabase MCP / SSH / Playwright / local binary check, per surfaces gathered}

### Step 5 — Artifact freshness
{ls -t of relevant dirs}

## Output format
One-page go/no-go table + ONE sentence: "Next move per {doc-section}: {action}" or "Blocked on {gap}".

## Failure-mode memory
- {past session ID + what went wrong + which step catches it}

## What NOT to do
- Standard list: never echo secrets (L010), never run destructive ops, never memory-checkpoint mid-preflight
```

### Step 4 — Scaffold the MEMORY.md skeleton

Write to `~/.claude/projects/{slug}/memory/MEMORY.md`:

```markdown
# Memory Index — {Project Name}

## Recently completed
- (Add session-checkpoint entries here at end of each meaningful session, star-rated by importance, dated, with commit refs)

## Project & Architecture
- (Project memories — system maps, sprint plans, decision logs)

## Infrastructure & Data
- (Reference memories — Supabase hosts, env vars, external services)

## User
- (User memory — role, preferences, working patterns)

## Workflow Rules
- (Feedback memories — locked rules with "Why:" and "How to apply:" lines)
```

### Step 5 — Create the session-checkpoint reminder

Write a single project memory `feedback_session_checkpoint_convention.md`:

```markdown
---
name: feedback-session-checkpoint-convention
description: At the end of each meaningful session (commits landed / decisions locked / blockers discovered), write a `session_YYYY_MM_DD_<topic>.md` and add a one-line star-rated entry to MEMORY.md's Recently completed section. Without this, MEMORY.md drifts within 24h.
metadata:
  node_type: memory
  type: feedback
---

**Rule.** Every meaningful session ends with a `session_YYYY_MM_DD_<topic>.md` memory + a one-line entry at the top of `MEMORY.md` -> Recently completed, star-rated.

**Why:** A mature project sustains memory currency across 100+ sessions because each session leaves a dated checkpoint. Projects without this convention have a 3-line MEMORY.md and drift within a day.

**How to apply:**
- "Meaningful" = code committed, decision locked, blocker discovered, learning surfaced, sprint phase completed
- Filename: `session_YYYY_MM_DD_<short-topic>.md` (e.g. `session_2026_05_12_phase_1c_data_refresh.md`)
- Content: what was done, what was discovered, what's the pickup point, cross-references via [[other-memory]]
- MEMORY.md entry: `- **⭐⭐⭐ [YYYY-MM-DD — short description (commit XXXXXXX)](session_YYYY_MM_DD_topic.md)** — one-paragraph hook`
- Stars: ⭐⭐⭐ load-bearing / ⭐⭐ useful / ⭐ minor
- Skip the checkpoint only for: trivial edits, exploratory sessions with no commits, conversations that produced no new state

**Cross-reference:** `[[project-memory-bootstrap]]` — the pattern this rule supports.
```

### Step 6 — Surface the hook-config edit for approval

The `cwd-skill-map.json` edit is a self-modification of hook infrastructure. The auto-mode classifier blocks broad approvals. Surface the proposed JSON entry explicitly and ask the user to approve specifically.

### Step 7 — Optional: rewrite stale memories

If the project already has memory files that are stale (>7 days old, written before recent commits), offer to rewrite them based on:
- Git log of commits since the memory was written
- Any design docs in the repo
- Sprint findings or reports

Do NOT auto-rewrite. Ask first.

## Output

When complete, render this summary:

```
| Piece                          | Status | Path                           |
|--------------------------------|--------|--------------------------------|
| cwd-router entry               | added/PENDING-approval | hooks/cwd-skill-map.json |
| {domain}-preflight skill       | created | skills/{domain}-preflight/SKILL.md |
| MEMORY.md skeleton             | created | projects/{slug}/memory/MEMORY.md |
| Session-checkpoint convention  | created | projects/{slug}/memory/feedback_session_checkpoint_convention.md |
| Stale memories rewritten       | N/A or N files | (list) |
```

Then ONE sentence: "Memory infrastructure wired. From this point, every {project} session auto-grounds via the preflight skill on cwd entry, and session-checkpoint memories should be written at every meaningful pause."

## Anti-patterns

- **Do NOT** create a preflight skill without confirming the infra surfaces — a preflight that probes services that don't exist is worse than no preflight (false-confidence + tool-call waste).
- **Do NOT** auto-write the `cwd-skill-map.json` entry. The harness blocks this; surface it explicitly for the user.
- **Do NOT** invent canonical docs — ask the user which docs in the repo are the source of truth. If the repo has no canonical doc yet, recommend creating one before bootstrapping memory infra.
- **Do NOT** scaffold without verifying the project memory dir slug. The slug encoding rule is `[\\/: ]` -> `-` then strip leading dashes. Mismatched slugs mean the session-start-lessons hook can't find project-specific lessons.

## Failure-mode memory

- **2026-05-13 Research-output bootstrap drift.** Project memory was written 2026-05-12 with "9-cov refit is active deliverable"; design doc finalized later same day deferred 9-cov to sprint 2. Memory drifted in <24h. Root cause: no preflight skill existed for "Research output" cwd, so subsequent sessions didn't auto-ground in the design doc — they read the stale memory and proceeded. This skill exists to prevent that recurrence.

## Cross-references

This skill produces files that reference each other via `[[name]]` slugs. Future sessions of the new project will follow the auto-memory rules in `~/.claude/CLAUDE.md` to extend the memory using the same conventions.
