---
name: infra-audit
description: >
  Standing, schedule-driven infrastructure audit-and-stabilize agent for a live box.
  Probes system state, validates every metric three-state (OK/SUSPECT/ALERT, clock checked
  FIRST so a bad epoch is SUSPECT not a false alarm), detects drift as a diff of versioned
  snapshots, and performs NO destructive action without a per-action, cryptographically
  signed human authorization. Use for live-box health auditing, freeing disk behind a hard
  approval gate, drift detection, scheduled health digests, and durable runbooks. Trigger on:
  infra audit, audit-and-stabilize, stabilization plan, drift detection, free disk safely,
  snapshot prune approval, destructive-action authorization, scheduled health digest,
  audit.py, live box health.
---

# infra-audit

The ops-side member of a trilogy with `swarm-verify` (coordinator) and `tdd-pipeline`
(builder). Same thesis: move trust from a claim to a measurement. Here *healthy* is a
bounds-validated fact and *destructive* is a human-signed one. The agent probes and
PROPOSES; a separate privileged executor is the ONLY thing that can destroy, and only with
a per-action signed token.

## Mechanisms

| # | Mechanism | Script(s) | Guarantee |
|---|-----------|-----------|-----------|
| 1 | Durable versioned tool | this skill | extend, never re-scratch |
| 2 | Three-state bounds | `bounds.py` | OK / SUSPECT / ALERT; clock validated first |
| 3 | Per-action destructive gate | `propose.py` `sign.py` `executor.py` `ledger.py` `canon.py` | signed enumerated fingerprint; the agent cannot self-authorize |
| 4 | Digest + drift + runbook | `snapshot.py` `digest.py` `audit_preflight.py` | notify-only; drift = diff of two validated snapshots |

## The gate invariant (hardened via two cold design red-teams)

No destructive action executes unless ALL hold: the self-check passes (agent non-root;
key/executor/ledger not agent-writable -- else VOID); the SSH signature over the canon
fingerprint verifies; the `proposal_id` was executor-issued and not yet consumed
(clock-independent); `box_id` matches this box; each item's FULL identity
(path,dev,inode,size,mtime) still matches live (missing/churned -> skip that item; same path,
different inode -> VOID swap); the canonical real target is inside the allowlist and not on
the denylist (by dev,inode + nlink + glob); blast-radius caps hold. Then it acts via an
`O_NOFOLLOW` handle, quarantine-then-purge (recoverable). **Per-action only** -- there is no
path by which the agent destroys anything without a human signature, on any box.

## Arming a box (one-time)

1. Copy `templates/audit.config.json` to the box (or subproject root) as `audit.config.json`.
   With NO manifest the tools REFUSE to run -- nothing is ever guessed.
2. Set `box_id` (unique), `box_class` (operator|client), `allowlist` (the only trees the agent
   may propose against), `denylist` (never-deletable; enforced by dev,inode at runtime),
   `bounds` (per-metric plausibility + thresholds), `clock` (plausible epoch bounds).
3. Provision signing (private key OFF-box, public key on-box):
   - Workstation: `ssh-keygen -t ed25519-sk -f ~/.ssh/audit_gate` (a FIDO sk- key needs a
     physical touch per signature -- the best anti-fatigue tripwire).
   - Box: an allowed_signers file holding ONLY the public key:
     `<identity> namespaces="infra-audit-gate" ssh-ed25519 AAAA...` at `signing.allowed_signers`.
   - Set `digest.discord_webhook_env` to the NAME of the env var that holds your webhook URL
     (never the URL itself).

## CLI quick reference

```
SK=~/.claude/skills/infra-audit/scripts

# Phase 0 -- ground truth (REFUSE + exit 2 if no manifest)
python $SK/audit_preflight.py --root R --json

# Snapshot + drift (B4: drift = diff of two bounds-validated snapshots)
python $SK/snapshot.py take --root R --readings readings.json
python $SK/snapshot.py diff --root R --a snap1.json --b snap2.json

# Notify-only digest (dry-run unless --send; webhook resolved by env NAME only)
python $SK/digest.py --root R --snapshot latest.json [--send]

# --- the per-action gate ---
python $SK/executor.py issue-nonce --root R                       # executor mints the nonce
python $SK/propose.py  --root R --action delete --nonce N \
        --reason "..." --paths p1 p2                              # unprivileged; writes a PENDING proposal
#   operator reviews the rendered item list + signs the fingerprint (authorize):
ssh-keygen -Y sign -f <priv_key> -n infra-audit-gate <fingerprint-file>   # attach signature+identity to the record
python $SK/executor.py execute --root R --proposal <record.json>  # privileged; verifies everything, then acts
python $SK/executor.py self-check --root R                        # the non-root / writability gate
```

> No secrets in any file: the webhook is an env-var NAME, the signing key lives off-box.
> All scripts: stdlib only, `python` (not python3), ASCII output, utf-8-sig config reads.

## The authorize step

`authorize` = the operator signing the proposal's `fingerprint` with their off-box key and
attaching the SSH signature + identity to the proposal record. The authorize view
(`canon.render`) foregrounds the concrete item list and sizes over the agent-authored reason,
sanitizes agent text (no ANSI / control / confusable tricks), and shows the fingerprint. The
signing primitive is `sign.py` (`ssh-keygen -Y sign/-Y verify`); a thin `authorize` wrapper is
a deploy convenience.

## Linux deploy seam (O3/O4 -- NOT performed by the local build)

The pure logic and the full signed pipeline are validated locally; these box-side steps make
the privilege split and the actual destruction real:

- Run the agent as an UNPRIVILEGED user; the executor as a separate privileged component
  (a systemd unit with its own `User=`, or a tightly scoped NOPASSWD sudoers entry for the
  executor path only). The agent gets NO destructive sudo.
- Make protected files root-owned and NOT agent-writable -- the allowed_signers (public key),
  `executor.py` + manifest, and the nonce ledger -- and `chattr +i` them. Extend
  `gather_self_check` with the active write-probe-AS-the-agent-uid (require EACCES) so the gate
  fails VOID if any are reachable.
- Put the ledger on reserved/dedicated storage (ext4 reserved blocks or a small dedicated
  volume) so a full app disk cannot deadlock the consume step. Fail closed with a DISTINCT
  'degraded' alarm vs a 'safe VOID'.
- Harden the action to `renameat()` relative to a pinned dir-fd (the move is already
  `O_NOFOLLOW` + `fstat`-identity verified); use pidfd + exe-inode for process kills.
- Provision the public key via a signed/logged ceremony (pin to an offline root key, or TOFU
  with a recorded fingerprint + alarm-on-change); define rotation/revocation; per-box keypairs.
- Wire `snapshot` + `digest` to a daily cron. The digest is the surface for SUSPECT items and
  pending approvals. Destructive proposals NEVER auto-fire from cron -- they wait for a signature.

## Data contracts

- `audit.config.json` (`audit-config/v1`) -- the manifest; no manifest => refuse.
- proposal record -- `{ payload:{ action_type, box_id, enumerated_items:[{path,dev,inode,size,mtime}],
  predicted_effect, reason, proposal_id, not_after }, fingerprint, signature, identity }`.
- snapshot (`audit-snapshot/v1`) -- provenance-stamped bounds result + raw readings.
- ledger -- append-only hash-chained consume-once nonce log (clock-independent replay defense).

## Composition

- **swarm-verify**: composed as strictly ADVISORY in preflight -- a swarm `BLOCK` escalates
  infra-audit only to `WARN`, never `REFUSE` (the gate keeps its own refuse authority). Reuses
  the `plausible_epoch_bounds` primitive (now its third reuse).
- **tdd-pipeline**: same manifest-or-refuse + template-then-arm pattern; quarantine-then-purge
  is the "set aside, don't destroy" idea applied to ops.

## Honesty boundary

"Healthy" proves *no bound tripped + no known-drift signature fired + no unauthorized
destruction* -- NOT that the box is truly fine (unknown failure modes do not trip known
bounds), and NOT that an approved action was wise (a signature authenticates approval, not
correctness). Two truths to keep loud: a root agent makes the gate decoration (non-root is a
hard precondition), and over months human gate-fatigue is the likeliest cause of a real bad
delete (cheap batched hardware-touch signing + bounds pre-screening + foregrounding the item
list are the defenses). Per-action only by design: the agent never destroys anything without you.

## Status

Built and validated locally: every script self-tests green; the end-to-end
propose -> sign -> execute pipeline passes; replay / tamper / expired / forged-nonce / wrong-key
all VOID. The actual quarantine MOVE and the OS privilege split are POSIX/Linux deploy steps
(above), not exercised on the build host. Armable per box; NOT deployed or pointed at any live box.
