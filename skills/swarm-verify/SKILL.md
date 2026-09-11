---
name: swarm-verify
description: >
  Self-verifying swarm coordination -- ground-truth pre-flight, on-disk deliverable
  verification, and content-hash task dedup. Use when launching or designing a
  multi-agent swarm (Workflow, agent-team, or custom control plane) that must not act
  on stale/unverified state, must verify builder outputs exist+parse on disk before
  marking a task done, or must idempotently dedup duplicate task notifications. Trigger
  on: swarm pre-flight, STATE.md, ground-truth gate, verify deliverable, taskhash,
  idempotent dispatch, wrong-repo guard, "did this builder actually finish", phantom-done.
---

# swarm-verify

Four deterministic gates that move swarm trust from **claims** to **measurements**.
Each replaces an LLM judgment that decays in long context with a filesystem/hash fact.

| # | Mechanism | Script | Replaces the judgment... |
|---|-----------|--------|--------------------------|
| 1 | Ground-truth pre-flight | `scripts/preflight.py` | "I'm in the right repo / it's the right time" |
| 2 | On-disk verification | `scripts/verify_deliverable.py` | "the builder said it's done" |
| 3 | Content-hash dedup | `scripts/taskhash.py` | "I think I've already done this one" |
| 4 | Self-heal loop (bounded auto-rerun + quarantine) | `~/.claude/skills/_lib/selfheal.py` | "I'll just reject the failures and move on" |

**They compose:** pre-flight gives trusted INPUT, taskhash gives stable IDENTITY,
verify gives trusted OUTPUT. Pull one and the others leak (dedup w/o verify =
phantom-done; verify w/o pre-flight = verifying the wrong repo's files).

All scripts are stdlib-only, config-driven (no hardcoded values/secrets), and
Windows-safe (`python` not python3, ASCII output, BOM-tolerant config reads).

---

## Arming a swarm (one-time, per project tree)

Copy `templates/swarm.config.json` to the **root of the swarm/project** and edit
`canonical_dir`, `stale_dirs`, optional `target_host`. **With no config present the
pre-flight hook is INERT** -- the toolkit is globally installed but dormant until you
opt a tree in. The hook (`~/.claude/hooks/swarm-preflight.sh`, PreToolUse matcher
`Workflow|TeamCreate`) auto-injects the STATE snapshot before any swarm launches, and
blocks the launch if `enforcement:"block"` + a hard violation (wrong repo / insane
clock / required host down).

State artifacts land in `<state_dir>/` (default `.swarm/`): `STATE.md`, `state.json`,
`status.json`.

---

## CLI quick reference

```bash
# 1. pre-flight (the hook runs this automatically; also runnable by hand)
python ~/.claude/skills/swarm-verify/scripts/preflight.py            # human STATE.md
python ~/.claude/skills/swarm-verify/scripts/preflight.py --json     # machine state.json

# 3. identity + idempotency  (exit 0 from is-done => already done, SKIP)
python ~/.claude/skills/swarm-verify/scripts/taskhash.py hash    --task-file task.json
python ~/.claude/skills/swarm-verify/scripts/taskhash.py is-done --task-file task.json --store .swarm/status.json
python ~/.claude/skills/swarm-verify/scripts/taskhash.py done    --task-file task.json --store .swarm/status.json --output results/x.json

# 2. on-disk verification  (exit 0 = PASS, 1 = FAIL)
python ~/.claude/skills/swarm-verify/scripts/verify_deliverable.py --file results/x.json \
    --required-fields summary sources --provenance-field sources --count-field sources --min-count 50
```

> **Quoting:** pass task specs via `--task-file`, not inline `--task-json`, whenever the
> task can contain quotes or non-ASCII (PowerShell 5.1 mangles embedded quotes to native
> exes; a file sidesteps it entirely).

---

## Wiring A -- Workflow tool (primary)

The deterministic gates ARE the pipeline. Pre-flight once, then every task flows:
**dedup -> build -> verify-on-disk -> mark-done**, with no barrier between stages.

```js
const SCRIPTS = '~/.claude/skills/swarm-verify/scripts'
const STORE = '.swarm/status.json'

const STATE_SCHEMA  = { type:'object', required:['verdict'], properties:{ verdict:{type:'string'}, violations:{type:'array'} } }
const BUILD_SCHEMA  = { type:'object', required:['skip','taskhash'], properties:{ skip:{type:'boolean'}, taskhash:{type:'string'}, output:{type:'string'} } }
const VERIFY_SCHEMA = { type:'object', required:['verdict'], properties:{ verdict:{type:'string'}, checks:{type:'array'} } }

// Phase 0 -- ground truth. (The PreToolUse hook already injected STATE; this makes the
// script HALT on BLOCK rather than relying on the model to heed the advisory.)
const state = await agent(
  `Run: python ${SCRIPTS}/preflight.py --json   -- return the parsed JSON verbatim.`,
  { schema: STATE_SCHEMA, label: 'preflight', phase: 'Preflight' })
if (state.verdict === 'BLOCK')
  throw new Error('pre-flight BLOCK: ' + JSON.stringify(state.violations))

// Per-task pipeline. tasks[] each have a stable {id, ...spec} written to a temp file
// by the builder (avoids inline-quote issues).
const results = await pipeline(tasks,
  // stage 1: dedup + build
  async (task, _orig, i) => {
    return await agent(
`Write this task spec to .swarm/task_${i}.json, then:
  python ${SCRIPTS}/taskhash.py is-done --task-file .swarm/task_${i}.json --store ${STORE}; echo EXIT:$?
If EXIT:0 -> already done; return {"skip":true,"taskhash":"<hash from 'taskhash hash'>"}.
Else do the work, write the deliverable to results/<hash>.json ending with
"<!-- END:<hash> -->", and return {"skip":false,"taskhash":"<hash>","output":"results/<hash>.json"}.
TASK: ${JSON.stringify(task)}`,
      { schema: BUILD_SCHEMA, label: `build:${task.id}`, phase: 'Build' })
  },
  // stage 2: verify on disk + mark done (cached items pass straight through)
  async (b, task, i) => {
    if (b.skip) return { ...b, verdict: 'PASS', cached: true }
    const v = await agent(
`Run and return parsed JSON:
  python ${SCRIPTS}/verify_deliverable.py --file ${b.output} --provenance-field sources --json
If verdict=="PASS", also run:
  python ${SCRIPTS}/taskhash.py done --task-file .swarm/task_${i}.json --store ${STORE} --output ${b.output}`,
      { schema: VERIFY_SCHEMA, label: `verify:${b.taskhash}`, phase: 'Verify' })
    return { ...b, verdict: v.verdict, checks: v.checks }
  }
)

const confirmed = results.filter(r => r && r.verdict === 'PASS')
const failed    = results.filter(r => r && r.verdict !== 'PASS')
log(`${confirmed.length} confirmed, ${failed.length} failed`)
return { confirmed, failed }
```

Why this shape: `schema:` is verification at the tool layer; `verify_deliverable.py` is
verification at the *disk* layer (the builder cannot fake a file that doesn't exist or
parse). `taskhash is-done` makes a re-dispatched task a cheap no-op. The pipeline has no
barrier, so a fast task verifies while a slow one still builds.

---

### Wiring A (self-heal) -- auto-rerun + quarantine

Mechanism 4. The per-task stage retries on a FAIL verdict, injecting the failed
checks as corrective feedback, bounded by `max_attempts` (config default 2, or a
per-task `max_attempts`), then quarantines + reports. Tasks self-heal independently
and concurrently (no barrier). `SELFHEAL = '~/.claude/skills/_lib/selfheal.py'`.

```js
const SELFHEAL = '~/.claude/skills/_lib/selfheal.py'
const N = config.deliverable.max_attempts ?? 2

async function verifiedBuild(task, _orig, i) {
  const id = task.id
  // Compute the task's stable identity ONCE from the canonical spec on disk, and use it as
  // BOTH the taskhash dedup key and the selfheal unit-id -- they MUST be the same string.
  // This keeps the pattern self-contained (no pre-populated task.hash to forget); without
  // it, every task's retries would collapse onto a single shared ledger entry.
  const th = (await agent(
`Write this task spec verbatim to .swarm/task_${i}.json (exact JSON, no extra keys), then run
  python ${SCRIPTS}/taskhash.py hash --task-file .swarm/task_${i}.json
and return {"hash":"<the 16-char hash it prints>"}.
TASK: ${JSON.stringify(task)}`,
    { schema:{ type:'object', required:['hash'], properties:{ hash:{type:'string'} } },
      label:`hash:${id}`, phase:'Build' })).hash

  // already done OR permanently quarantined -> no-op (idempotent re-dispatch)
  const done = await agent(
    `Run: python ${SCRIPTS}/taskhash.py is-done --task-file .swarm/task_${i}.json --store ${STORE}; echo EXIT:$?`,
    { schema: { type:'object', required:['done'], properties:{ done:{type:'boolean'} } },
      label:`dedup:${id}`, phase:'Build' })
  if (done.done) return { id, verdict:'PASS', cached:true }
  const quar = await agent(
    `Run: python ${SELFHEAL} is-quarantined --store ${STORE} --unit-id ${th}; echo EXIT:$?`,
    { schema: { type:'object', required:['quarantined'], properties:{ quarantined:{type:'boolean'} } },
      label:`quar?:${id}`, phase:'Build' })
  if (quar.quarantined) return { id, verdict:'QUARANTINED', cached:true }

  let lastChecks = null
  for (let attempt = 1; attempt <= (task.max_attempts ?? N); attempt++) {
    const feedback = attempt > 1 && lastChecks
      ? `\nPRIOR ATTEMPT FAILED these checks -- fix exactly these: ${JSON.stringify(lastChecks)}`
      : ''
    const b = await agent(
`Do the work for TASK ${JSON.stringify(task)}.${feedback}
Write the deliverable to results/${th}.json ending with "<!-- END:${th} -->".
Return {"output":"results/${th}.json"}.`,
      { schema:{ type:'object', required:['output'], properties:{ output:{type:'string'} } },
        label:`build:${id}#${attempt}`, phase:'Build' })

    const v = await agent(
`Run and return parsed JSON:
  python ${SCRIPTS}/verify_deliverable.py --file ${b.output} --provenance-field sources --json`,
      { schema:{ type:'object', required:['verdict'], properties:{ verdict:{type:'string'}, checks:{type:'array'} } },
        label:`verify:${th}#${attempt}`, phase:'Verify' })

    if (v.verdict === 'PASS') {
      await agent(`Run: python ${SCRIPTS}/taskhash.py done --task-file .swarm/task_${i}.json --store ${STORE} --output ${b.output}`,
        { label:`done:${id}`, phase:'Verify' })
      return { id, verdict:'PASS', attempt }
    }
    lastChecks = (v.checks || []).filter(c => c.status === 'fail')
    // Record a shell-SAFE summary (failed check names only -- no quotes/backslashes to
    // mangle the command). The rich JSON detail rides the build prompt above, not a CLI arg.
    await agent(`Run: python ${SELFHEAL} attempt --store ${STORE} --unit-id ${th} --reason failed:${lastChecks.map(c => c.check).join(',')}`,
      { label:`attempt:${id}`, phase:'Verify' })
    const cont = await agent(
      `Run: python ${SELFHEAL} should-continue --policy attempts --store ${STORE} --unit-id ${th} --max ${task.max_attempts ?? N}; echo EXIT:$?`,
      { schema:{ type:'object', required:['ok'], properties:{ ok:{type:'boolean'} } }, label:`cont?:${id}`, phase:'Verify' })
    if (!cont.ok) {
      await agent(`Run: python ${SELFHEAL} quarantine --store ${STORE} --unit-id ${th} --reason exhausted`,
        { label:`quar:${id}`, phase:'Verify' })
      return { id, verdict:'QUARANTINED', attempt }
    }
  }
  // unreachable: should-continue always halts at attempt == max_attempts (above), which
  // quarantines + returns. Kept as a defensive fallthrough only.
  return { id, verdict:'QUARANTINED' }
}

const results = await pipeline(tasks, verifiedBuild)
const report = await agent(`Run and return JSON: python ${SELFHEAL} report --store ${STORE}`,
  { schema:{ type:'object' }, label:'selfheal-report', phase:'Report' })
log(`${report.confirmed.length} confirmed, ${report.quarantined.length} quarantined`)
return report
```

The verifier's failed `checks` become the next attempt's instructions -- a corrective
retry, not a blind one. Quarantine is terminal and idempotent: a re-dispatched swarm
skips already-quarantined units. `max_attempts` keeps a stubborn task from looping
forever; `report` gives the coordinator the confirmed/quarantined ledger.

---

## Wiring B -- Agent teams (stub)

Pre-flight is automatic (the hook fires on `TeamCreate`). Then enforce **separation of
duties**: the builder declares its output path; the **coordinator** (not the builder)
accepts it.

- **Before dispatch:** coordinator runs `taskhash.py is-done`; skip on exit 0.
- **On "done" report:** coordinator runs `verify_deliverable.py --file <declared output>`.
  PASS -> `taskhash.py done`. FAIL -> reject, reissue (do NOT trust the builder's claim).
- High-stakes deliverables: add a fresh-context adversarial reader as a final gate
  (your CLAUDE.md adversarial-validation convention), on top of the on-disk checks.

## Wiring C -- Python control plane / ADE (stub)

```python
import json, subprocess
S = os.path.expanduser("~/.claude/skills/swarm-verify/scripts")

def preflight():
    r = subprocess.run(["python", f"{S}/preflight.py", "--json"], capture_output=True, text=True)
    st = json.loads(r.stdout)
    if st["verdict"] == "BLOCK":
        raise RuntimeError(f"pre-flight BLOCK: {st['violations']}")
    return st

def is_done(task_file, store):
    return subprocess.run(["python", f"{S}/taskhash.py", "is-done",
                           "--task-file", task_file, "--store", store]).returncode == 0

def verify(path, *extra):
    return subprocess.run(["python", f"{S}/verify_deliverable.py", "--file", path, *extra]).returncode == 0
# loop: preflight() once -> per task: if is_done skip; build; if verify(out): taskhash done; else reissue
```

---

## Data contracts (shared across all three scripts)

- **`state.json`** `swarm-state/v1` -- `facts{}` each tagged `status` (ok|unknown|violation)
  + `volatility` (stable|volatile); `clock.value.plausible_epoch_bounds` is the trusted
  window for sanity-checking ANY downstream epoch; `verdict` PASS|WARN|BLOCK.
- **`status.json`** `swarm-status/v1` -- `tasks{ <taskhash>: {status, output_path, spec_version, updated_at} }`.
  `is-done` = `status=="done"` AND `output_path` still exists (phantom-done guard).
- **Sentinel** -- deliverables end with `<!-- END:<taskhash> -->` (md) or carry a
  top-level `"_complete": true` (json); checked by `verify_deliverable.py --sentinel`.
- **taskhash** = sha256 of canonicalized spec (volatile keys stripped: timestamp,
  attempt, sender, run_id...; keys sorted; `spec_version` folded in so spec changes
  invalidate). Bias: when unsure include MORE identity -- under-hashing silently DROPS work.

## Honesty boundary

Existence/parse/schema catch **no-shows and truncation**, NOT fabrication. A file can
exist, parse, and be confidently wrong. To catch fabrication use `--provenance-field`
(the deliverable must embed the sources it claims to have used) and/or an adversarial
reader. Schema validates SHAPE, never truth.
