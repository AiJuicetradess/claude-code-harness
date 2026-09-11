---
name: tdd-pipeline
description: >
  Autonomous test-driven feature pipeline -- write the contract as a RED test suite first,
  then loop red->green with parallel fixers, a regression firewall that auto-reverts any
  edit that breaks a passing test, and a green+smoke gate that commits only when all tests
  pass. Use when implementing a feature under strict TDD, running a hands-off "implement X
  until green" loop, or hardening an agent build against buggy-code / wrong-approach drift.
  Trigger on: TDD pipeline, red-green loop, regression firewall, auto-revert on failing test,
  test-first, green gate, commit only when green, "make the tests pass", vacuous test guard.
---

# tdd-pipeline

The builder-side twin of `swarm-verify`: it moves trust from "the agent says the code
works" to "a RED test went GREEN and stayed green." Each mechanism replaces a judgment
that decays in long context with a filesystem/exit-code fact.

| # | Mechanism | Script | Replaces the judgment... |
|---|-----------|--------|--------------------------|
| 1 | Contract -> RED tests | (author agent) + `run_suite.py` + `green_guard.py red-first` | "this test means something" |
| 2 | Red -> green loop | `run_suite.py` + `green_guard.py progress` (stall logic now in `_lib/selfheal.py`; `progress` is a compat shim) | "I think it's basically working" |
| 3 | Regression firewall | `checkpoint.py` | "my fix didn't break anything" |
| 4 | Green + smoke gate | `run_suite.py --smoke` + `green_guard.py` | "it's done, ship it" |

All scripts are stdlib-only, manifest-driven (no hardcoded targets/commands), and
Windows-safe (`python` not python3, ASCII output, utf-8-sig config reads, argv arrays so
paths with spaces are safe). The regression firewall uses **content snapshots, not git
history rewrites**, so it works in git / worktree / non-git trees and never trips a
destructive-git guard.

---

## Arming a target (one-time, per project tree)

Copy `templates/tdd.config.json` to the **root of the project (or subproject)** as
`tdd.config.json` and set `test_cmd`, `smoke_cmd`, `git_mode`, `protect`. **With no
manifest the harness REFUSES to run** -- it never guesses the target or the test command.
For a monorepo, arm the *subproject* root, never the workspace root.

State lands in `<state_dir>/` (default `.tdd/`): `snapshot/<id>/`, run JSONs, `report.md`.

---

## CLI quick reference

```bash
SK=~/.claude/skills/tdd-pipeline/scripts

# Phase 0 -- ground truth (+ optional green baseline; --baseline RUNS the suite)
python $SK/tdd_preflight.py --root R --json
python $SK/tdd_preflight.py --root R --baseline --json

# Run the suite -> structured pass/fail set (exit 0 iff all-green)
python $SK/run_suite.py run   --root R [--smoke]
python $SK/run_suite.py run-k --root R --expr "<-k expr>" --times 3     # flaky probe

# Anti-cheat / anti-spin guards (exit 1 on violation / halt)
python $SK/green_guard.py red-first    --baseline base_with_new.json --new new_ids.json
python $SK/green_guard.py shrink        --before before.json --after after.json
python $SK/green_guard.py regressions   --baseline last_green.json --current now.json
python $SK/green_guard.py progress      --history red_counts.json --k 2   # DEPRECATED shim -> _lib/selfheal.py should-continue --policy stall

# Regression firewall -- content snapshot; never touches git history
python $SK/checkpoint.py snapshot --root R --id r1 --paths app/x.py pkg/
python $SK/checkpoint.py restore  --root R --id r1 --paths app/x.py pkg/
python $SK/checkpoint.py changed  --root R          # git modes: what the work tree changed
```

> **Quoting:** put commands in the manifest as ARRAYS (`["python","-m","pytest"]`), not
> strings -- PowerShell 5.1 mangles embedded quotes and Git Bash mangles backslashes.

---

## Wiring -- the autonomous Workflow (primary)

The deterministic scripts ARE the gates; agents only do the judgment work (write tests,
write fixes). Commit enforcement is **harness-only** (the Workflow simply does not commit
until the gates pass -- no commit-blocking hook).

```js
const S = '~/.claude/skills/tdd-pipeline/scripts'
const ROOT = args.root            // project root containing tdd.config.json
const K = 2                       // anti-spin window

const RUN   = { type:'object', required:['ok'], properties:{ ok:{type:'boolean'}, all_green:{type:'boolean'},
                passed:{type:'array'}, failed:{type:'array'}, red_count:{type:'number'} } }
const GUARD = { type:'object', required:['ok'], properties:{ ok:{type:'boolean'} } }
const STATE = { type:'object', required:['verdict'], properties:{ verdict:{type:'string'} } }

const runSuite = (smoke) => agent(
  `Run and return JSON verbatim: python ${S}/run_suite.py run --root "${ROOT}"${smoke ? ' --smoke' : ''}`,
  { schema: RUN, label: smoke ? 'smoke' : 'suite', phase: 'Loop' })

// Phase 0 -- ground truth + green baseline (executes the suite once).
const st = await agent(`Run, return JSON: python ${S}/tdd_preflight.py --root "${ROOT}" --baseline --json`,
  { schema: STATE, label: 'preflight', phase: 'Preflight' })
if (st.verdict === 'BLOCK') throw new Error('TDD pre-flight BLOCK')

// Phase 1 -- contract -> RED. The AUTHOR (never the implementer) writes tests; we PROVE
// each new test is red against current code (a new test that already passes is vacuous).
await agent(`You are the TEST AUTHOR -- you will NOT implement the feature. Translate each
  assertion of the Validation Contract (manifest contract_source) into tests. Write them;
  write the new test-id list to .tdd/new_ids.json; run
  python ${S}/run_suite.py run --root "${ROOT}" and save its JSON to .tdd/base_with_new.json.`,
  { label: 'author', phase: 'Contract' })
const rf = await agent(`Run, return JSON: python ${S}/green_guard.py red-first \
  --baseline "${ROOT}/.tdd/base_with_new.json" --new "${ROOT}/.tdd/new_ids.json"`,
  { schema: GUARD, label: 'red-first', phase: 'Contract' })
if (!rf.ok) throw new Error('vacuous tests passed before implementation: ' + JSON.stringify(rf.vacuous_passing))

// Phase 2 -- red -> green ratchet. Fixers serial by default; parallelize ONLY across
// import-disjoint modules (CLAUDE.md write rule), optionally with agent isolation:'worktree'.
let lastGreen = await runSuite()
const history = []
let cur = lastGreen
while (!cur.all_green) {
  // anti-spin via the shared governor (single source of truth with swarm-verify)
  await agent(`Write ${JSON.stringify(history)} to .tdd/history.json`, { label:'hist', phase:'Loop' })
  const cont = await agent(
    `Run: python ~/.claude/skills/_lib/selfheal.py should-continue --policy stall --history "${ROOT}/.tdd/history.json" --k ${K}; echo EXIT:$?`,
    { schema:{ type:'object', required:['ok'], properties:{ ok:{type:'boolean'} } }, label:'anti-spin', phase:'Loop' })
  if (!cont.ok)
    return { blocked: true, why: 'anti-spin: failing-set has not shrunk', failed: cur.failed }

  const groups = await groupByModule(cur.failed)   // static map (test->module->files) or a one-shot agent
  for (const g of groups) {                         // disjoint groups MAY be wrapped in parallel()
    const sid = `r${history.length}_${g.key}`
    await agent(`Run: python ${S}/checkpoint.py snapshot --root "${ROOT}" --id ${sid} --paths ${g.files.join(' ')}`,
      { label: `snap:${g.key}`, phase: 'Loop' })
    await agent(`IMPLEMENTER: make these failing tests pass by editing ONLY [${g.files.join(', ')}].
      Do NOT edit test files. Failing: ${g.tests.join(', ')}`, { label: `fix:${g.key}`, phase: 'Loop' })
    const after = await runSuite()
    const reg = await agent(`Save the prior run to .tdd/after.json, then run + return JSON:
      python ${S}/green_guard.py regressions --baseline "${ROOT}/.tdd/last_green.json" --current "${ROOT}/.tdd/after.json"`,
      { schema: GUARD, label: `reg:${g.key}`, phase: 'Loop' })
    if (!reg.ok)   // M3 firewall: this fixer turned a green test red -> revert just its files
      await agent(`Run: python ${S}/checkpoint.py restore --root "${ROOT}" --id ${sid} --paths ${g.files.join(' ')}`,
        { label: `revert:${g.key}`, phase: 'Loop' })
    else
      lastGreen = after   // ratchet forward; persist to .tdd/last_green.json
  }
  cur = await runSuite()
  history.push(cur.red_count)
}

// Phase 3 -- green + smoke gate, then commit (harness-only).
const smoke = await runSuite(true)
if (smoke.ok && smoke.all_green === false)
  return { blocked: true, why: 'unit-green but smoke failed (L009 E2E gate)', smoke }
await agent(`Run: cd "${ROOT}" && git add -A && git commit -m "tdd: contract green + smoke (${cur.passed.length} tests)"`,
  { label: 'commit', phase: 'Gate' })
return { done: true, green: cur.passed.length }
```

Why this shape: `schema:` verifies at the tool layer; `run_suite`/`green_guard`/`checkpoint`
verify at the *disk + exit-code* layer (an agent cannot fake a green JUnit file or a file
that doesn't exist). The loop is a ratchet, not a random walk -- the firewall guarantees
green tests stay green, and `progress` stops the loop instead of spinning.

A flaky test would trip the firewall spuriously; before trusting a green->red flip, re-run
just that test: `run_suite.py run-k --expr "<id>" --times N`. Mixed pass/fail => quarantine
and report, do NOT revert.

---

## Data contracts

- **`tdd.config.json`** (`tdd-config/v1`) -- the manifest. No manifest => harness refuses (the
  wrong-target guard). Commands are ARRAYS. `protect` globs are never snapshotted or deleted.
- **`tdd_preflight.py`** (`tdd-preflight/v1`) -- `verdict` PASS|WARN|BLOCK; `facts.runner`,
  `facts.discovery` (collect-only, no execution), `facts.baseline` (only with `--baseline`).
- **`run_suite.py`** -- `{passed[], failed[], all_green, red_count}`; exit 0 iff all-green.
- **`.tdd/snapshot/<id>/`** -- content snapshot + `_snapshot.json` (firewall state).
- **green baseline** -- the passing set captured at Phase 0; the ratchet may only grow it.

## Composition with swarm-verify

A green+smoke proof is a **stronger** deliverable than `verify_deliverable.py`'s
exists+parse+provenance. Inside a swarm, this harness's green report at `results/<x>` is
exactly what `swarm-verify`'s coordinator then confirms-on-disk and dedups by `taskhash`.
Builder-side discipline (here) feeds coordinator-side gates (there): preflight -> RED ->
green ratchet -> verify-on-disk -> mark-done.

## Honesty boundary

Green proves **no-shows and regressions are gone -- NOT that the contract is right.** A
suite can be vacuous, or faithfully encode a wrong intent, and still be green. Mitigations
inside the harness: author != implementer (Phase 1), red-first (F1), test-file immutability
+ shrink check (F2). Mitigation outside: a final fresh-context adversarial reader that asks
"do these tests encode the actual intent?" (your CLAUDE.md adversarial-validation
convention). **Autonomy is bounded by contract trust** -- the more hands-off the loop, the
more a bad contract can ship a polished wrong answer. Keep the human gate on the contract.
