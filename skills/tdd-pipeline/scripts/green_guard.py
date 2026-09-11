#!/usr/bin/env python
"""
green_guard.py -- the loop's conscience: the anti-cheat and anti-spin checks that keep
'green' honest.

  red-first   : new tests must FAIL against unmodified code. A new test that already
                passes is vacuous (L023) -> violation.
  shrink      : the suite must not lose tests between rounds. Green achieved by deleting
                or skipping tests is rejected.
  regressions : tests green in the baseline but red now = regressions the firewall must
                revert (the green ratchet may only move forward).
  progress    : halt the loop if the failing-set has not shrunk for K rounds (anti-spin,
                L025/L031) so we surface 'blocked' instead of burning tokens.

Pure logic over JSON inputs (run_suite.py results). stdlib only. ASCII output.
Exit: 0 = clean / no violation / progressing, 1 = violation / halt.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/_lib"))
import selfheal  # noqa: E402  (shared governor: single source of the stall logic)


def _load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _ids(run):
    return set(run.get("passed", [])) | set(run.get("failed", []))


def cmd_red_first(baseline, new_ids):
    # baseline = run of the suite (incl. the new tests) against UNMODIFIED code.
    passed = set(baseline.get("passed", []))
    vacuous = sorted(t for t in new_ids if t in passed)
    return {"ok": len(vacuous) == 0, "check": "red-first", "vacuous_passing": vacuous}


def cmd_shrink(before, after):
    deleted = sorted(_ids(before) - _ids(after))
    return {"ok": len(deleted) == 0, "check": "shrink", "deleted_tests": deleted,
            "before_total": len(_ids(before)), "after_total": len(_ids(after))}


def cmd_regressions(baseline, current):
    reg = sorted(set(baseline.get("passed", [])) & set(current.get("failed", [])))
    return {"ok": len(reg) == 0, "check": "regressions", "regressions": reg}


def cmd_progress(history, k):
    # COMPAT SHIM: the stall logic now lives in selfheal.should_continue_stall (single
    # source of truth). New callers should use that directly; this wrapper stays so the
    # `progress` CLI and existing callers keep their exact output shape. Do not delete.
    r = selfheal.should_continue_stall(history, k)
    out = {"ok": r["ok"], "check": "progress", "halt": r["halt"]}
    if "window" in r:
        out["window"] = r["window"]
    out["reason"] = r["reason"]
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="tdd-pipeline anti-cheat / anti-spin guard")
    ap.add_argument("cmd", choices=["red-first", "shrink", "regressions", "progress"])
    ap.add_argument("--baseline")
    ap.add_argument("--current")
    ap.add_argument("--before")
    ap.add_argument("--after")
    ap.add_argument("--new", help="JSON file: list of new test ids")
    ap.add_argument("--history", help="JSON file: list of red_counts per round")
    ap.add_argument("--k", type=int, default=2)
    args = ap.parse_args()

    if args.cmd == "red-first":
        res = cmd_red_first(_load(args.baseline), set(_load(args.new)))
    elif args.cmd == "shrink":
        res = cmd_shrink(_load(args.before), _load(args.after))
    elif args.cmd == "regressions":
        res = cmd_regressions(_load(args.baseline), _load(args.current))
    else:
        res = cmd_progress(_load(args.history), args.k)

    sys.stdout.write(json.dumps(res, ensure_ascii=True, indent=2) + "\n")
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
