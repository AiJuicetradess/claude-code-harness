# -*- coding: utf-8 -*-
"""
selfheal.py -- the shared retry-governor for swarm-verify and tdd-pipeline.

Moves "should I retry this failing unit, or give up?" from an LLM judgment that
decays in long context to a deterministic, resumable ledger decision.

Two halt policies:
  attempts : per-unit bound (swarm tasks are independent) -- continue iff
             attempts < max.
  stall    : global stall-window over a red_count history (tdd shares one suite)
             -- halt if the failing-set has not shrunk for K rounds. This is the
             former green_guard.progress logic, verbatim, so the two skills share
             one source of truth.

Ledger reuses the swarm-status/v1 schema (the same store taskhash.py writes), so
attempt-count + quarantine live in the SAME entry taskhash already manages. Both
scripts preserve each other's fields on write.

Stdlib only. Windows-safe: `python` not python3, ASCII output (L018),
utf-8-sig reads (BOM-tolerant, L003). Fail-open on the LEDGER: a corrupt/missing
swarm-status store is read as an empty ledger -- never a crash, never a block.
(An unreadable/malformed --history file for the stall policy is a caller error,
not a ledger fault: it exits 2 with an error JSON -- never a traceback, and never
silently maps to halt.)

Exit codes:
  should-continue : 0 = continue, 1 = halt, 2 = bad input (cannot decide)
  is-quarantined  : 0 = quarantined (skip), 1 = not
  attempt/quarantine/report : 0
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

STORE_SCHEMA = "swarm-status/v1"
REASON_MAX = 500  # F4: bound the recorded reason so an oversized detail can't bloat the ledger


def load_store(path):
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                d = json.load(fh)
            if isinstance(d, dict) and isinstance(d.get("tasks"), dict):
                return d
        except Exception:
            pass  # F3 fail-open: corrupt ledger -> empty
    return {"schema": STORE_SCHEMA, "tasks": {}}


def save_store(path, store):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2)


def _stamp(entry):
    entry["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["updated_epoch"] = int(time.time())
    return entry


def _truncate(s):
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= REASON_MAX else s[:REASON_MAX] + "...[truncated]"


def cmd_attempt_api(store_path, unit_id, reason=None):
    store = load_store(store_path)
    entry = store["tasks"].get(unit_id, {})
    entry["attempts"] = int(entry.get("attempts", 0)) + 1
    if reason is not None:
        entry["last_reason"] = _truncate(reason)
    _stamp(entry)
    store["tasks"][unit_id] = entry
    save_store(store_path, store)
    return {"unit_id": unit_id, "attempts": entry["attempts"]}


def cmd_quarantine_api(store_path, unit_id, reason=None):
    store = load_store(store_path)
    entry = store["tasks"].get(unit_id, {})
    entry["status"] = "quarantined"
    if reason is not None:
        entry["last_reason"] = _truncate(reason)
    _stamp(entry)
    store["tasks"][unit_id] = entry
    save_store(store_path, store)
    return {"unit_id": unit_id, "status": "quarantined",
            "attempts": int(entry.get("attempts", 0))}


def is_quarantined_api(store_path, unit_id):
    entry = load_store(store_path)["tasks"].get(unit_id)
    return bool(entry) and entry.get("status") == "quarantined"


def report_api(store_path):
    store = load_store(store_path)
    confirmed, quarantined, attempts_by_unit = [], [], {}
    for uid, e in store["tasks"].items():
        attempts_by_unit[uid] = int(e.get("attempts", 0))
        st = e.get("status")
        if st == "done":
            confirmed.append(uid)
        elif st == "quarantined":
            quarantined.append(uid)
    return {"confirmed": sorted(confirmed),
            "quarantined": sorted(quarantined),
            "attempts_by_unit": attempts_by_unit}


def should_continue_attempts(store_path, unit_id, max_attempts):
    entry = load_store(store_path)["tasks"].get(unit_id) or {}
    attempts = int(entry.get("attempts", 0))
    cont = attempts < max_attempts
    return {"ok": cont, "policy": "attempts", "unit_id": unit_id,
            "attempts": attempts, "max": max_attempts, "halt": not cont,
            "reason": "under budget" if cont else "max_attempts reached"}


def should_continue_stall(history, k):
    # verbatim port of green_guard.cmd_progress: history = red_counts oldest..newest;
    # halt if the failing-set has not shrunk in the last k rounds.
    if len(history) <= k:
        return {"ok": True, "policy": "stall", "halt": False, "reason": "warming up"}
    window = history[-(k + 1):]
    shrank = any(window[i + 1] < window[i] for i in range(len(window) - 1))
    halt = not shrank
    return {"ok": not halt, "policy": "stall", "halt": halt, "window": window,
            "reason": ("no shrink in last %d rounds" % k) if halt else "progressing"}


def main():
    ap = argparse.ArgumentParser(description="Shared retry-governor (selfheal).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("attempt")
    a.add_argument("--store", required=True)
    a.add_argument("--unit-id", required=True)
    a.add_argument("--reason")

    q = sub.add_parser("quarantine")
    q.add_argument("--store", required=True)
    q.add_argument("--unit-id", required=True)
    q.add_argument("--reason")

    iq = sub.add_parser("is-quarantined")
    iq.add_argument("--store", required=True)
    iq.add_argument("--unit-id", required=True)

    rp = sub.add_parser("report")
    rp.add_argument("--store", required=True)

    sc = sub.add_parser("should-continue")
    sc.add_argument("--policy", choices=["attempts", "stall"], required=True)
    sc.add_argument("--store")
    sc.add_argument("--unit-id")
    sc.add_argument("--max", type=int)
    sc.add_argument("--history", help="JSON file: list of red_counts per round")
    sc.add_argument("--k", type=int, default=2)

    args = ap.parse_args()

    if args.cmd == "attempt":
        print(json.dumps(cmd_attempt_api(args.store, args.unit_id, args.reason)))
        return 0
    if args.cmd == "quarantine":
        print(json.dumps(cmd_quarantine_api(args.store, args.unit_id, args.reason)))
        return 0
    if args.cmd == "is-quarantined":
        q = is_quarantined_api(args.store, args.unit_id)
        print("yes" if q else "no")
        return 0 if q else 1
    if args.cmd == "report":
        print(json.dumps(report_api(args.store), indent=2))
        return 0
    if args.cmd == "should-continue":
        # exit 2 = bad input (cannot decide), kept distinct from 0=continue / 1=halt
        # so a caller error can never masquerade as a policy decision.
        if args.policy == "attempts":
            if not (args.store and args.unit_id and args.max is not None):
                print(json.dumps({"ok": False,
                                  "error": "attempts policy needs --store --unit-id --max"}))
                return 2
            res = should_continue_attempts(args.store, args.unit_id, args.max)
        else:
            if not args.history:
                print(json.dumps({"ok": False, "error": "stall policy needs --history"}))
                return 2
            try:
                with open(args.history, "r", encoding="utf-8-sig") as fh:
                    history = json.load(fh)
            except Exception as e:
                print(json.dumps({"ok": False,
                                  "error": "cannot read --history %s: %s" % (args.history, e)}))
                return 2
            if not isinstance(history, list):
                print(json.dumps({"ok": False,
                                  "error": "--history must be a JSON list of red_counts"}))
                return 2
            res = should_continue_stall(history, args.k)
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
