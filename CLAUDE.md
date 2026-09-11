# CLAUDE.md (Global)

This file contains behavioral DNA — principles that shape HOW Claude thinks.
Mechanical rules (read-before-edit, secrets blocking, destructive command guards,
verification enforcement) are enforced by hooks in `~/.claude/hooks/`.

## Agent Teams

Prefer agent teams over plain subagents for tasks involving 2+ agents or parallel work.
- Teams: 3+ independent subtasks, feature dev pipelines, multi-angle research, security audits
- Plain subagents: single-purpose delegation, quick lookups

### Deep Research MCP (optional)
- If you run a deep-research API server on localhost:5000, expose it to: architect, researcher, code-reviewer, trading-researcher
- Uses the Anthropic API + Firecrawl for web scraping

### Frontend Design Pipeline
- frontend-dev has: stitch (screen gen), gemini-image (image gen), magic (21st.dev components)
- Architect instructs frontend-dev to generate design system first, then search Magic before building

### Team Defaults
- teammateMode: in-process (VS Code compatible)
- Architect always plans first (permissionMode: plan)
- Shut down teammates when work is complete

### SDD seat standard (BINDING — overrides any plugin skill's "Model Selection", incl. superpowers SDD)
House standard for every subagent-driven build loop. Plugin-skill cost defaults never override it:
- **Implementer seats:** Grok 4.6 headless, dispatched ONLY via `~/.claude/bin/grok-dispatch.sh <prompt-file> <repo-cwd> [extra args]` (Bash tool, never PowerShell — PS 5.1 mangles embedded-quote argv). The wrapper pins `--model grok-4.6 --reasoning-effort xhigh --permission-mode bypassPermissions` (CLI at `~/.grok/bin/grok.exe`; verify with `grok models`). Long tasks: run in background, generous timeout.
- **Reviewer seats (task reviews AND scoped re-reviews):** Fable 5 (`model: fable`), fresh context, between every task. Never a cheaper tier.
- **Final whole-branch review:** Fable 5.
- Cost is never a reason to downgrade a seat. Any deviation requires the user's explicit approval in that session, per-dispatch.

**Authored-artifact adversarial gates (spec/plan defects are the dominant defect source; task reviews are conformance-scoped and never catch them):**
- **Spec gate:** after spec approval, BEFORE writing-plans — dispatch `adversarial-critic` (Fable 5, fresh context) against the spec file. Brief: attack trust boundaries and identities ("who can trigger each transition, authenticated as whom"), falsify stated assumptions, hunt fail-open designs. Rule on every finding before planning starts. For high-risk/stateful specs, escalate to a multi-round adversarial exhaust harness: specs that get it ship with zero spec escapes; specs that skip it leak defects past every task review.
- **Plan gate:** BEFORE Task 1 — dispatch a fresh Fable code review of the plan's verbatim code blocks and test fixtures. When implementers are byte-faithful, plan-authored code is where the fix rounds come from.

**Verification gates:**
- **Controller-verify (BINDING):** the controller re-runs the full suite itself before dispatching each task reviewer and at merge — implementer-reported test counts are never trusted as ground truth.
- Arm `tdd.config.json` (run_suite/green_guard) only when the build's suite is flaky or multi-surface (e.g. Python suite green while frontend JS is broken); it is opt-in, not implied.
- **Ledger retention:** SDD ledgers, riders, and review packages live in the repo's `.superpowers/sdd/<plan>/` workspace and are committed with the branch — never scratchpad-only. The skill gitignores this dir by default: add `!.superpowers/sdd/**/progress.md` (and riders) to the repo .gitignore at build setup.

### Sub-agent swarming
- **Reads.** >5 files for research/grep/audit = parallel sub-agents (5-8 files per agent). Non-negotiable.
- **Writes.** Parallel writes only if files share no imports, types, or exports. Otherwise serial — one writer at a time, then handoff. Coordination drift > token savings.

### Structured handoffs
When a sub-agent finishes a unit of work, the handoff records:
- What was completed
- What was left undone
- Commands run + their exit codes
- Issues discovered
- Whether the spawning procedure was followed

State across handoffs is written down, not remembered. Connective tissue for any work that spans multiple agents or phases.

### Adversarial validation
Code-review, security-review, and behavioral-validation sub-agents must spawn with fresh context — no prior exposure to the implementation reasoning. The point of separation is removing sunk-cost bias toward implementation choices. If the conversation already discussed the code, spawn a fresh agent for review rather than asking the orchestrator to review.

## Swarm / Task Coordination

For multi-agent swarms (Workflow, agent-teams, or a custom control plane), the `swarm-verify` skill supplies three deterministic gates. This is the policy; enforcement lives in the scripts + the `swarm-preflight` hook.

- **Ground truth before dispatch.** Never act on assumed cwd / repo / host / time. The pre-flight hook injects a STATE snapshot before a swarm launches — read it first. Use STATE's `clock` as the trusted "now" and reject any epoch outside its `plausible_epoch_bounds`. Work only in the declared `canonical_dir`; never treat a `stale_dir` as source of truth.
- **Done is coordinator-verified, never self-reported.** Mark a task done only after `verify_deliverable.py` confirms the output exists, parses, and (for analysis work) carries provenance. A builder *claiming* completion is not completion.
- **Duplicate task notifications are idempotent no-ops.** Identity is `taskhash.py` (content hash of the canonicalized spec), not recognition. `is-done` (status==done AND output still on disk) gates re-dispatch; a repeat is a no-op.

Arm a project tree by dropping `swarm.config.json` at its root (template in the skill). No config ⇒ the hook is inert. See the `swarm-verify` skill for Workflow / teams / control-plane wiring.

## Validation Contract
For multi-step plans (≥3 implementation phases or ≥5 files touched), open with a Validation Contract before implementation steps. Defines correctness independently of how features get built. Tests satisfy the contract; the contract is not shaped by code. Run validators against the contract — not against the diff — at each milestone. Skip for trivial edits.

**Behavioral** — user-observable outcomes / end-to-end flows
- B1. <assertion>

**Structural** — function signatures, API shapes, data invariants, file boundaries
- S1. <assertion>

**Failure-mode** — errors, edge cases, expected refusals, retry behavior
- F1. <assertion>

**Non-goals** — explicitly out of scope (prevents scope creep)
- N1. <item>

**Coverage map** — each feature satisfies ≥1 assertion; sum of features covers every assertion
- Feature A → B1, S1
- Feature B → B2, F1

Expect first-pass validation failure as the norm. Plan for at least one corrective pass per milestone.

## Spec & Plan Lifecycle
Plans are execution scaffolding; specs are the design record; git history keeps retired plans. Zero implemented plans on disk is a repo's steady state.
- **After the final review is clean and before finishing-a-development-branch, invoke `spec-lifecycle`:** audit → reverse-sync the spec (Implementation record + `status: implemented` frontmatter, deviations from spec recorded) → retire the plan file. Retirement always needs the user's confirmation in that session; specs are never deleted (superseded/abandoned get a status, not an rm).
- `plan_audit.py <repo>` classifies plans by whether their declared Create/Test targets exist (checkboxes are never a signal). `session-start-plan-audit.sh` prints one line when the cwd repo has implemented plans or unsynced specs; treat it as a prompt, not a blocker.
- Diagram deliverables: standalone architecture/sequence/data-flow/state files → `archify` (network-free local install; never run its update check or `brands capture`); hand-drawn SVG in Artifact pages or HTML → `artifact-diagramming` + `diagram-geometry` (run `verify_connectors.py` before delivering).

## Self-Improvement Loop
- Never dismiss a lesson — flag for user review if you disagree
- Treat each lesson violation as a process bug, not a one-off
- **Persist standards at ruling time.** The second time any working rule is applied — or the first time the user calls it "our standard" — write it into this file or a feedback memory IN THAT SESSION, before work continues. A standard that lives only as practice loses to the next skill default.

## Hooks Reference

These rules are enforced by hooks (not by this file):

| Hook | Enforces |
|------|----------|
| `pre_file_guard.py` | Edit/NotebookEdit/Write gate (one spawn): .env/secrets file block (L006) → hardcoded-secret scan (L010) → L018 non-ASCII in .py print/log payload lines (hatch: PYTHONIOENCODING/reconfigure) → read-before-edit + 3-edit consecutive limit + 300 LOC warning (L001/L013/L021). New-file Writes always allowed. |
| `pre_bash_guard.py` | Bash+PowerShell gate (one spawn): destructive commands + hardcoded-secret scan → L018 inline-python non-ASCII (both shells) → L003 Bash-dialect traps (backslash paths, native /flags, `>nul`, unset path vars) → L035 dialect mixing both ways (Bash: cmdlets/`2>$null`/`$env:`; PowerShell: `&&`/`\|\|`, `/dev/null`, `export`) → L034 native-exe `2>&1` in PowerShell → L030 15s git-mutation lock → L028 ask-gate on high-blast-radius remote mutations + once-per-session remote-reach reminder → L011 once-per-session inline-ssh warn → grok-dispatch guard (SDD seat standard): BLOCKS `grok -p`/`--prompt-file` in PowerShell (PS 5.1 argv quote-mangling), once-per-session Bash nudge toward `~/.claude/bin/grok-dispatch.sh`. Tests: `test_pre_bash_guard.py`, `test_promoted_guards.py` |
| `pre_read_guard.py` | Read gate (L001, L029): blocks Read on nonexistent paths (nearest ancestor + close-matches) and directories → blocks no-limit Reads on >50KB text files and any Read of >50KB single-line blobs (media/PDF/ipynb exempt). Fail-open. |
| `post_edit_track.py` | Track PROJECT edits only — under the session cwd, never the OS temp/scratchpad (feeds stop-verify), warn at 5-file phase threshold, optional auto-pytest for Python edits under `CLAUDE_AUTO_PYTEST_ROOT` (surfaces failures only, 45s bound) |
| `post-read-tracker.sh` | Track file reads for the file-guard enforcement |
| `post-bash-verify-tracker.sh` | Track verification commands (tsc, eslint, pytest) — command-position matching only (echo/grep/git-commit/pip mentions don't count) + flags are timestamps so a verifier run only vouches for edits made before it. Matcher is Bash\|PowerShell (PowerShell pytest runs count as verification) + releases the L030 git lock. Release is ownership-scoped (pre_bash_guard stamps tool_use_id into the lock; only the owning call may release) |
| `post-bash-failure-release.sh` | PostToolUseFailure (Bash\|PowerShell): releases the L030 git lock when the tool call FAILED. PostToolUse never fires on failure, so a failed git command used to hold the lock for its full 15s TTL and block the retry. Ownership-scoped by tool_use_id so a hook-blocked parallel call cannot free a running call's lock. Release-only: a failed pytest/tsc never counts as verification. |
| `stop-verify-reminder.sh` | Stop-block (`decision:block`) when PROJECT code was edited but not verified/re-read — cwd-scoped (temp/out-of-project files ignored) + LATCHED to one warning per unchanged state snapshot, re-arms on new edits (`stop_hook_active` guard intact) |
| `time-inject.sh` | Inject time + skill keyword matches (`hooks/skill-keywords.json`) |
| `session-start-lessons.sh` | Inject LESSONS.md + reflection nudge |
| `session-start-cwd-router.sh` | Route cwd → a per-project preflight skill via `hooks/cwd-skill-map.json` (ships with an example entry only) |
| `session-start-plan-audit.sh` | One-line nudge when the cwd repo has implemented plans still on disk or unsynced specs (`spec-lifecycle`); silent otherwise, never blocks |
| `session-end-capture.sh` | Log session metadata for reflection |
| `swarm-preflight.sh` | Ground-truth pre-flight before swarm launch (PreToolUse: Workflow/TeamCreate); inert without a `swarm.config.json` |
