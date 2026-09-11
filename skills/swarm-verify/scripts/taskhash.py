# -*- coding: utf-8 -*-
"""
taskhash.py -- Mechanism 3: content-hash task identity + status store.

Replaces dedup-by-recognition (an LLM judgment that decays as context fills)
with a deterministic identity: hash(canonicalized task spec). Dedup,
idempotency, and "already done?" become set-membership/lookup, not judgment.

Canonicalization is the whole game:
  - strip VOLATILE envelope fields (timestamp, notification_id, attempt, sender,
    run_id...) so the same task hashes the same regardless of how it arrived
  - sort keys, compact separators, ensure_ascii -> stable bytes -> sha256
  - fold in spec_version if present so a spec change invalidates the hash
Bias: when unsure, include MORE identity. Under-hashing silently DROPS work
(false "already done"); over-hashing only wastes compute.

"already done?" = status==done AND the recorded output still exists on disk
(ties to mechanism 2 -- a done-record whose file vanished is NOT done).

Stdlib only. Windows-safe: `python`, ASCII output (L018).

Examples:
  python taskhash.py hash      --task-json '{"op":"render","file":"a","ts":9}'
  python taskhash.py claim     --task-file t.json
  python taskhash.py done      --task-file t.json --output results/a.json
  python taskhash.py is-done   --task-file t.json     # exit 0=done(skip) 1=todo
  python taskhash.py status    --task-file t.json
"""
import argparse
import hashlib
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
DEFAULT_STRIP = ["timestamp", "ts", "time", "notification_id", "notif_id",
                 "attempt", "attempts", "sender", "received_at", "_received",
                 "run_id", "dispatched_at", "_envelope"]


def load_task(args):
    if args.task_json is not None:
        raw = args.task_json
    elif args.task_file:
        with open(args.task_file, "r", encoding="utf-8-sig") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        return raw  # freeform string task; hashed as-is


def canonicalize(task, strip):
    """Deterministic bytes for a task spec. Dict -> strip volatile keys, sort,
    compact. String/other -> normalized text."""
    if isinstance(task, dict):
        clean = {k: v for k, v in task.items() if k not in strip}
        return json.dumps(clean, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True)
    if isinstance(task, list):
        return json.dumps(task, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True)
    return " ".join(str(task).split())


def task_hash(task, strip, length=16):
    canon = canonicalize(task, strip)
    h = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    # fold spec_version into the visible identity so spec changes invalidate
    if isinstance(task, dict) and task.get("spec_version") is not None:
        sv = str(task["spec_version"])
        h = hashlib.sha256((h + "|" + sv).encode("utf-8")).hexdigest()
    return h[:length]


def store_path(args):
    if args.store:
        return args.store
    sd = args.state_dir or os.path.join(os.getcwd(), ".swarm")
    return os.path.join(sd, "status.json")


def load_store(path):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"schema": STORE_SCHEMA, "tasks": {}}


def save_store(path, store):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2)


def set_status(args, status, output=None):
    task = load_task(args)
    th = task_hash(task, set(DEFAULT_STRIP) | set(args.strip or []))
    path = store_path(args)
    store = load_store(path)
    entry = store["tasks"].get(th, {})
    entry["status"] = status
    if output is not None:
        entry["output_path"] = output
    if isinstance(task, dict):
        if task.get("spec_version") is not None:
            entry["spec_version"] = task["spec_version"]
        if args.label:
            entry["label"] = args.label
    entry["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    entry["updated_epoch"] = int(time.time())
    store["tasks"][th] = entry
    save_store(path, store)
    return th, entry


def cmd_hash(args):
    task = load_task(args)
    th = task_hash(task, set(DEFAULT_STRIP) | set(args.strip or []))
    print(th)
    return 0


def cmd_claim(args):
    th, _ = set_status(args, "claimed")
    print(th)
    return 0


def cmd_done(args):
    # phantom-done guard: refuse to mark done if the artifact is absent
    if not args.force and args.output and not os.path.exists(args.output):
        print("[taskhash] REFUSED: output does not exist: %s (use --force to override)"
              % args.output)
        return 3
    th, _ = set_status(args, "done", output=args.output)
    print(th)
    return 0


def cmd_fail(args):
    th, _ = set_status(args, "failed")
    print(th)
    return 0


def cmd_status(args):
    task = load_task(args)
    th = task_hash(task, set(DEFAULT_STRIP) | set(args.strip or []))
    store = load_store(store_path(args))
    entry = store["tasks"].get(th)
    print(json.dumps({"taskhash": th, "entry": entry}, indent=2))
    return 0


def cmd_is_done(args):
    """exit 0 = done AND artifact present on disk (skip it);
       exit 1 = not done / artifact missing (do the work)."""
    task = load_task(args)
    th = task_hash(task, set(DEFAULT_STRIP) | set(args.strip or []))
    store = load_store(store_path(args))
    entry = store["tasks"].get(th)
    if not entry or entry.get("status") != "done":
        print("no")
        return 1
    out = entry.get("output_path")
    if out and not os.path.exists(out):
        print("no (phantom-done: recorded output missing: %s)" % out)
        return 1
    print("yes")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Content-hash task identity + status store.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("hash", "claim", "done", "fail", "status", "is-done"):
        p = sub.add_parser(name)
        g = p.add_mutually_exclusive_group()
        g.add_argument("--task-json", help="task spec as a JSON/string literal")
        g.add_argument("--task-file", help="path to a file holding the task spec")
        p.add_argument("--store", help="path to status.json (default <cwd>/.swarm/status.json)")
        p.add_argument("--state-dir", help="state dir holding status.json")
        p.add_argument("--strip", nargs="*", help="extra volatile keys to strip before hashing")
        p.add_argument("--label", help="human label to record")
        if name == "done":
            p.add_argument("--output", help="path to the deliverable this task produced")
            p.add_argument("--force", action="store_true",
                           help="record done even if output is absent")
    args = ap.parse_args()
    return {
        "hash": cmd_hash, "claim": cmd_claim, "done": cmd_done,
        "fail": cmd_fail, "status": cmd_status, "is-done": cmd_is_done,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
