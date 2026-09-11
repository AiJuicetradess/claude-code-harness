# Claude Code Harness

A sanitized export of a working Claude Code `~/.claude` setup: hooks that enforce
mechanical rules, a global `CLAUDE.md` of working principles, subagent definitions,
a lessons store with a reflection loop, and a set of general-purpose skills.
Project-specific skills, project history, and personal paths were stripped before
publishing.

## Layout

| Path | What it is |
|------|------------|
| `CLAUDE.md` | Global principles: agent teams, SDD seat standard, adversarial gates, validation contract, spec/plan lifecycle, hook reference |
| `settings.json` | Hook wiring, permissions, plugin flags, env. Merge the `hooks` block into your own file rather than replacing it |
| `hooks/` | 14 hooks plus two test files. Guards run as `python ~/.claude/hooks/*.py`, the rest as `bash ~/.claude/hooks/*.sh` |
| `agents/` | 14 subagent definitions (architect, code-reviewer, adversarial-critic, security-reviewer, ...) |
| `skills/` | General skills. Highlights below |
| `lessons/` | 46 lesson files plus the `LESSONS.md` digest injected at session start. Evidence sections were removed; Rule, Why, and Prevention remain |
| `reflections/` | The scripts behind the `/reflect` self-improvement loop |
| `bin/grok-dispatch.sh` | Wrapper used by the SDD seat standard to run a headless implementer. Needs the `grok` CLI |

## Skills worth looking at first

- `spec-lifecycle`: audits `docs/superpowers` plans by whether their declared targets exist, reverse-syncs the spec, retires the plan. 42 tests.
- `diagram-geometry`: six connector rules for hand-drawn SVG plus `verify_connectors.py`. 56 tests.
- `archify`: architecture, sequence, data-flow, and state diagrams as standalone HTML. Patched to make zero network calls.
- `swarm-verify`: ground-truth preflight, on-disk deliverable verification, and content-hash task dedup for multi-agent runs.
- `ui-ux-pro-max`: design-system generator with the three-color diagram palette rule.
- `memory-synthesizer`, `session-resume-from-memory`, `project-memory-bootstrap`: the memory-currency pattern.

Third-party plugin skills (Cloudflare, HyperFrames) are not included; install those from their own plugins. `archify` is included under its MIT license, see `skills/archify/LICENSE`.

## New on 2026-09-10

- `skills/spec-lifecycle/` with `plan_audit.py` and `retire_plan.py`
- `skills/diagram-geometry/` with `verify_connectors.py`
- `skills/archify/` with the four network-free patches described in its `SKILL.md`
- `hooks/session-start-plan-audit.sh`, registered under SessionStart in `settings.json`
- `ARCHIFY_UPDATE_CHECK_DISABLED=1` in the `settings.json` env block
- The "Spec & Plan Lifecycle" section in `CLAUDE.md`
- Keyword triggers for the three new skills in `hooks/skill-keywords.json`
- The "Diagram & Illustration Palette" section emitted by `ui-ux-pro-max/scripts/design_system.py`

## Installing

Do not clone this straight into `~/.claude`. It would replace your `settings.json`
and `CLAUDE.md`. Clone it somewhere else and copy the pieces you want:

1. `hooks/` into `~/.claude/hooks/`, then merge the `hooks` block from `settings.json`
   into your own `settings.json`. Every command path is already `~/.claude/hooks/...`.
2. `skills/<name>/` into `~/.claude/skills/`. Each folder stands alone.
3. `agents/` into `~/.claude/agents/`.
4. `lessons/` and `reflections/` if you want the lessons injection and `/reflect`.
   `session-start-lessons.sh` reads `~/.claude/lessons/LESSONS.md`.
5. `CLAUDE.md`: read it and pull what you agree with into your own. The SDD seat
   standard names specific models and a `grok` wrapper; treat that as one house's
   choice, not a requirement.
6. `bin/grok-dispatch.sh` into `~/.claude/bin/` only if you use the `grok` CLI.

## Assumptions the hooks make

- Windows with Git Bash. Hooks are invoked as `bash ~/.claude/hooks/x.sh` and
  `python ~/.claude/hooks/x.py`, so both `bash` and `python` (3.11 or newer) must be
  on PATH. They should run on macOS and Linux as well but were not tested there.
- Hooks keep small state files under `~/.claude` and fail open. A hook that errors
  never blocks Claude.
- `archify` needs Node 18 or newer.
- `session-start-cwd-router.sh` reads `hooks/cwd-skill-map.json`, which ships with an
  example entry only. Add one entry per project that has a preflight skill.
- `post_edit_track.py` runs pytest automatically only when `CLAUDE_AUTO_PYTEST_ROOT`
  is set to a directory. Unset, that feature is off.

## Tests

```
python hooks/test_pre_bash_guard.py
python hooks/test_promoted_guards.py
python -m pytest skills/diagram-geometry/tests skills/spec-lifecycle/tests skills/ui-ux-pro-max/scripts/test_design_system_diagram_palette.py -q -p no:cacheprovider
```

## Repo hygiene

`.gitignore` is an allowlist: everything is ignored, and only harness source is opted
back in. If you do decide to run this as your `~/.claude`, credentials, session
transcripts, caches, and plugin state stay out of git by construction.
