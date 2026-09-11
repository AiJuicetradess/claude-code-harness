---
name: spec-lifecycle
description: Keep superpowers plan and spec files from piling up and going stale. Use after a final review is clean (before finishing-a-development-branch), when the session-start nudge reports implemented plans still on disk, or when the user mentions stale plans, old plans, outdated specs, plan cleanup, retire a plan, spec sync, or asks what is still open in docs/superpowers. Audits plans by whether their declared Create/Test targets exist, reverse-syncs the spec with what actually shipped, stamps its status, and retires the plan file. Never deletes specs; never retires a plan without the user's confirmation.
---

# Spec Lifecycle

**Principle.** A plan is execution scaffolding; git history keeps it forever. A spec
is the durable design record and must say what actually shipped. Zero implemented
plans on disk is the steady state of a repo.

Adapted from open-spdd's "fix the prompt first, then the code" sync loop, applied
to the superpowers spec-then-plan layout.

## Tools

```bash
python ~/.claude/skills/spec-lifecycle/scripts/plan_audit.py <repo> [--json] [--strict] [--no-git]
python ~/.claude/skills/spec-lifecycle/scripts/retire_plan.py <plan.md> --root <repo> --commits <range> --deviations <file> [--status implemented|abandoned|superseded] [--dry-run]
```

The audit classifies each plan from the file paths its tasks declare
(`- Create:` and `- Test:` lines). It does not trust checkboxes: executing-plans
and SDD track progress in the ledger, so plan boxes stay unticked forever.

| Plan status | Meaning | Action |
|---|---|---|
| IMPLEMENTED | at least 80% of Create/Test targets exist | retire (step 2) |
| PARTIAL | some targets exist | ask: still in progress, or abandoned? |
| UNSTARTED | no target exists | ask: still wanted? if not, mark spec abandoned |
| UNKNOWN | no targets declared (task files, runbooks, dossiers) | judge by hand |

| Spec status | Meaning | Action |
|---|---|---|
| ACTIVE | a non-implemented plan references it | none |
| UNSYNCED | only implemented plans reference it, no `status:` | reverse-sync (step 2) |
| UNTRACKED | no plan references it, no `status:` | design-only spec; stamp `status: draft` or `abandoned` when the user rules |
| IMPLEMENTED / SUPERSEDED / ABANDONED | stamped | none |

## Protocol

1. **Audit.** Run `plan_audit.py <repo>` and show the table. Group by status.

2. **Retire each IMPLEMENTED plan, with confirmation.** List the candidates and
   ask the user to confirm the set once. For each confirmed plan:
   - Gather evidence: the spec, the plan, `git log --oneline` for the branch or
     range, and the final code review findings if this session ran them.
   - Write a short deviations file (scratchpad is fine): what shipped differently
     from the spec and why, non-goals that became goals or vice versa, follow-ups.
     "None recorded." is acceptable only after you actually compared spec and code.
   - Run `retire_plan.py` with `--commits` and `--deviations`. It stamps the spec
     frontmatter (`status: implemented`, `implemented_on`, `retired_plan`),
     appends an Implementation record, and `git rm`s the plan. It does not commit.
   - Commit: `chore(spec): retire plan <name>; mark spec implemented`.

3. **Rule on PARTIAL and UNSTARTED plans older than 60 days.** Ask the user per
   plan. Abandoned: `retire_plan.py --status abandoned` (spec keeps the record).
   Still wanted: leave it, note it in the reply.

4. **Report.** One line per action taken, then the fresh audit summary.

## Hard rules

- Never delete a spec. Superseded specs get `status: superseded` and `superseded_by`.
- Never retire a plan the user has not confirmed in this session. The audit is
  read-only; only `retire_plan.py` writes, and only after confirmation.
- Never mark a plan implemented from the plan's own claims. The audit's evidence
  is files on disk; the reviewer's evidence is the diff.
- SDD ledgers in `.superpowers/sdd/<plan>/` are handled by the SDD skill's own
  "delete this plan's workspace" step, not here.

## Where this runs in the pipeline

subagent-driven-development or executing-plans finishes -> final review clean ->
**spec-lifecycle (this skill)** -> finishing-a-development-branch.

The session-start hook `session-start-plan-audit.sh` prints one line when the cwd
repo has implemented plans on disk or unsynced specs. Treat it as a prompt to run
step 1 when the current task allows.
