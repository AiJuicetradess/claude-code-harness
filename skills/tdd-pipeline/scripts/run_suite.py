#!/usr/bin/env python
"""
run_suite.py -- the loop's eyes: run the test suite and normalize the result to a
structured pass/fail set (the failing-set the red->green loop drives to empty).

pytest is run via JUnit XML (--junit-xml, stdlib parse, no plugin dependency). go/jest
are declared seams (NOT implemented) so the harness fails loudly rather than faking a
result for a runner we have not built (N3).

Subcommands:
  run    [--smoke]                 run full suite (or smoke_cmd); report passed/failed
  run-k  --expr E [--times N]      run `test_cmd -k E` N times (flaky probe)

Reuses tdd_preflight for argv/junit handling (single source for the XXE guard).
stdlib only. Windows-safe. Exit: run -> 0 iff all-green; run-k -> 0 iff ran ok.
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tdd_preflight as tp  # noqa: E402  (sibling module; single source for parse_junit/XXE guard)


def _load_manifest(root):
    p = tp.find_manifest(root)
    if not p:
        return {}, None
    try:
        return tp.load_json(p), p
    except Exception:
        return {}, p


def _run_pytest_junit(argv, root, timeout):
    if not argv:
        return {"ok": False, "reason": "no test_cmd configured"}
    fd, xmlpath = tempfile.mkstemp(suffix=".xml", prefix="tdd_run_")
    os.close(fd)
    try:
        rc, out = tp.run_cmd(argv + ["--junit-xml", xmlpath], root, timeout)
        if rc is None:
            return {"ok": False, "reason": tp._ascii(out)}
        parsed, err = tp.parse_junit(xmlpath)
        if err:
            return {"ok": False, "reason": err, "rc": rc,
                    "out_tail": tp._ascii("\n".join(out.splitlines()[-8:]))}
        passed, failed = parsed["passed"], parsed["failed"]
        return {"ok": True, "rc": rc, "passed": passed, "failed": failed,
                "green_count": len(passed), "red_count": len(failed),
                "all_green": (len(failed) == 0 and len(passed) > 0)}
    finally:
        try:
            os.remove(xmlpath)
        except Exception:
            pass


def cmd_run(root, manifest, smoke, timeout):
    runner = (manifest.get("runner") or "pytest").lower()
    cmd = manifest.get("smoke_cmd") if smoke else manifest.get("test_cmd")
    if smoke and cmd is None:
        return {"ok": False, "reason": "no smoke_cmd configured"}
    if runner != "pytest":
        return {"ok": False, "reason": "runner '%s' not implemented (seam only)" % runner}
    return _run_pytest_junit(tp.as_argv(cmd), root, timeout)


def cmd_run_k(root, manifest, expr, times, timeout):
    runner = (manifest.get("runner") or "pytest").lower()
    if runner != "pytest":
        return {"ok": False, "reason": "runner '%s' not implemented (seam only)" % runner}
    base = tp.as_argv(manifest.get("test_cmd"))
    if not base:
        return {"ok": False, "reason": "no test_cmd configured"}
    npass = nfail = 0
    for _ in range(max(1, times)):
        r = _run_pytest_junit(base + ["-k", expr], root, timeout)
        if not r.get("ok"):
            return {"ok": False, "reason": r.get("reason"), "out_tail": r.get("out_tail")}
        if r["red_count"] == 0 and r["green_count"] > 0:
            npass += 1
        else:
            nfail += 1
    return {"ok": True, "expr": expr, "times": times, "pass": npass, "fail": nfail,
            "flaky": (npass > 0 and nfail > 0), "stable_pass": (nfail == 0)}


def main():
    tp._reconfig_stdout()
    ap = argparse.ArgumentParser(description="tdd-pipeline suite runner")
    ap.add_argument("cmd", choices=["run", "run-k"])
    ap.add_argument("--root", default=".")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--expr")
    ap.add_argument("--times", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--json", action="store_true", help="accepted for symmetry; output is always JSON")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    manifest, _ = _load_manifest(root)
    if args.cmd == "run":
        res = cmd_run(root, manifest, args.smoke, args.timeout)
    elif not args.expr:
        res = {"ok": False, "reason": "run-k needs --expr"}
    else:
        res = cmd_run_k(root, manifest, args.expr, args.times, args.timeout)

    sys.stdout.write(json.dumps(res, ensure_ascii=True, indent=2) + "\n")
    if not res.get("ok"):
        sys.exit(1)
    sys.exit(0 if (args.cmd != "run" or res.get("all_green")) else 1)


if __name__ == "__main__":
    main()
