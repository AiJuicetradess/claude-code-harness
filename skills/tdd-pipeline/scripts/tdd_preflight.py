#!/usr/bin/env python
"""
tdd_preflight.py -- Phase 0 of the tdd-pipeline skill (ground-truth before the loop).

Resolves and validates the TDD target from a tdd.config.json manifest BEFORE the
red->green loop runs. Composes with swarm-verify's preflight.py for repo/clock ground
truth, then adds TDD-specific probing: runner resolution + SAFE test discovery
(pytest --collect-only, which does NOT execute tests) and, with --baseline, records
the currently-passing test set (the green baseline the regression firewall protects).

Refuses (verdict BLOCK) when no manifest is found -- the harness never guesses a
target or a test command.

stdlib only. Windows-safe: 'python' not python3, ASCII-only output, utf-8-sig config
reads, argv arrays (no shell splitting), subprocess timeouts.

Exit codes: 0 = PASS or WARN, 2 = BLOCK.
"""
import argparse
import json
import os
import sys
import time
import subprocess
import tempfile
import xml.etree.ElementTree as ET

MANIFEST_NAME = "tdd.config.json"
CLOCK_FLOOR = 1735689600   # 2025-01-01 UTC
CLOCK_CEIL = 1893456000    # 2030-01-01 UTC
DEFAULT_PREFLIGHT = os.path.expanduser("~/.claude/skills/swarm-verify/scripts/preflight.py")


def _ascii(s):
    try:
        return str(s).encode("ascii", "replace").decode("ascii")
    except Exception:
        return "?"


def _reconfig_stdout():
    # cp1252 hardening: keep stdout from crashing on stray non-ASCII
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_manifest(start):
    d = os.path.abspath(start)
    seen = set()
    while d and d not in seen:
        seen.add(d)
        p = os.path.join(d, MANIFEST_NAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def run_cmd(args, cwd, timeout):
    """Run argv list, no shell. Return (rc, combined_output). rc is None on failure-to-run."""
    try:
        p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        out = p.stdout.decode("utf-8", "replace") if p.stdout else ""
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %ss" % timeout
    except FileNotFoundError as e:
        return None, "NOTFOUND: %s" % _ascii(e)
    except Exception as e:
        return None, "ERROR: %s" % _ascii(e)


def as_argv(cmd):
    if cmd is None:
        return None
    if isinstance(cmd, list):
        return [str(x) for x in cmd]
    return str(cmd).split()  # string fallback; array form preferred for spaces/backslashes


def detect_git(root):
    rc, out = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], root, 15)
    if rc == 0 and "true" in out.lower():
        return True
    return os.path.exists(os.path.join(root, ".git"))


def pytest_collect(test_cmd, root, timeout):
    argv = as_argv(test_cmd)
    if not argv:
        return {"ok": False, "count": None, "head": "no test_cmd"}
    rc, out = run_cmd(argv + ["--collect-only", "-q"], root, timeout)
    count = None
    for line in out.splitlines():
        ls = line.strip().lower()
        if "collected" in ls or "tests collected" in ls:
            for tok in ls.replace("/", " ").split():
                if tok.isdigit():
                    count = int(tok)
                    break
            if count is not None:
                break
    if count is None:
        ids = [ln for ln in out.splitlines() if "::" in ln]
        if ids:
            count = len(ids)
    ok = (rc == 0)
    head = "" if ok else _ascii("\n".join(out.splitlines()[-8:]))
    return {"ok": ok, "rc": rc, "count": count, "head": head}


def parse_junit(xml_path):
    # stdlib-only XXE / entity-expansion guard: JUnit XML from a test runner never
    # contains a DOCTYPE or entity declaration, so refuse any file that does. Blocks
    # billion-laughs and external-entity attacks without needing defusedxml (S2: no deps).
    try:
        if os.path.getsize(xml_path) > 25 * 1024 * 1024:
            return None, "junit refused: file too large (>25MB)"
        with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        return None, "junit read error: %s" % _ascii(e)
    low = text.lower()
    if "<!doctype" in low or "<!entity" in low:
        return None, "junit refused: DOCTYPE/ENTITY present (entity-expansion guard)"
    try:
        root = ET.fromstring(text)
    except Exception as e:
        return None, "junit parse error: %s" % _ascii(e)
    passed, failed = [], []
    for tc in root.iter("testcase"):
        name = tc.get("name") or ""
        cls = tc.get("classname") or ""
        tid = (cls + "::" + name) if cls else name
        bad = any(child.tag in ("failure", "error") for child in tc)
        (failed if bad else passed).append(tid)
    return {"passed": sorted(passed), "failed": sorted(failed)}, None


def run_baseline(test_cmd, root, timeout, runner):
    if runner != "pytest":
        return {"captured": False, "reason": "baseline only implemented for pytest"}
    argv = as_argv(test_cmd)
    fd, xmlpath = tempfile.mkstemp(suffix=".xml", prefix="tdd_junit_")
    os.close(fd)
    try:
        rc, out = run_cmd(argv + ["--junit-xml", xmlpath], root, timeout)
        if rc is None:
            return {"captured": False, "reason": _ascii(out)}
        parsed, err = parse_junit(xmlpath)
        if err:
            return {"captured": False, "reason": err, "rc": rc, "out_tail": _ascii("\n".join(out.splitlines()[-6:]))}
        parsed["captured"] = True
        parsed["rc"] = rc
        parsed["green_count"] = len(parsed["passed"])
        parsed["red_count"] = len(parsed["failed"])
        return parsed
    finally:
        try:
            os.remove(xmlpath)
        except Exception:
            pass


def compose_groundtruth(manifest, root):
    pf = manifest.get("preflight", None)
    if pf == "":
        return None  # explicitly skipped
    path = pf if pf else DEFAULT_PREFLIGHT
    if not os.path.isfile(path):
        return None
    rc, out = run_cmd(["python", path, "--json"], root, 30)
    if rc is None:
        return {"verdict": "UNKNOWN", "note": _ascii(out)}
    try:
        return json.loads(out)
    except Exception:
        return None  # preflight likely inert (no swarm.config) -> not JSON


def summarize(state):
    f = state.get("facts", {})
    L = ["TDD PRE-FLIGHT: %s" % state["verdict"]]
    if f.get("manifest_path"):
        L.append("  manifest: %s" % f["manifest_path"])
    if f.get("root"):
        L.append("  root:     %s  (exists=%s, git=%s, mode=%s)" % (
            f["root"], f.get("root_exists"), f.get("is_git_repo"), f.get("git_mode")))
    if f.get("runner"):
        L.append("  runner:   %s  cmd=%s" % (f["runner"], f.get("test_cmd")))
    d = f.get("discovery")
    if d:
        L.append("  discovery: ok=%s collected=%s" % (d.get("ok"), d.get("count")))
    b = f.get("baseline")
    if b:
        L.append("  baseline: captured=%s green=%s red=%s" % (
            b.get("captured"), b.get("green_count"), b.get("red_count")))
    gt = f.get("ground_truth")
    if gt:
        L.append("  ground_truth(swarm-verify): %s" % gt.get("verdict"))
    for v in state.get("violations", []):
        L.append("  [VIOLATION] %s" % _ascii(v))
    for w in state.get("warnings", []):
        L.append("  [warn] %s" % _ascii(w))
    if d and d.get("head"):
        L.append("  --- discovery tail ---")
        L.append(d["head"])
    return "\n".join(L)


def emit(state, as_json):
    if as_json:
        sys.stdout.write(json.dumps(state, ensure_ascii=True, indent=2) + "\n")
    else:
        sys.stdout.write(summarize(state) + "\n")


def main():
    _reconfig_stdout()
    ap = argparse.ArgumentParser(description="tdd-pipeline Phase 0 ground-truth pre-flight")
    ap.add_argument("--config", help="path to tdd.config.json (else search upward from --root/cwd)")
    ap.add_argument("--root", default=".", help="dir to start manifest search / run from")
    ap.add_argument("--baseline", action="store_true",
                    help="RUN the suite to record the green baseline (executes tests)")
    ap.add_argument("--timeout", type=int, default=90, help="per-probe timeout seconds (baseline uses 6x)")
    ap.add_argument("--json", action="store_true", help="machine JSON to stdout")
    args = ap.parse_args()

    cfg_path = args.config or find_manifest(args.root)
    if not cfg_path or not os.path.isfile(cfg_path):
        emit({"schema": "tdd-preflight/v1", "verdict": "BLOCK",
              "violations": ["no %s found at or above %s" % (MANIFEST_NAME, os.path.abspath(args.root))],
              "warnings": [], "facts": {}}, args.json)
        sys.exit(2)

    try:
        manifest = load_json(cfg_path)
    except Exception as e:
        emit({"schema": "tdd-preflight/v1", "verdict": "BLOCK",
              "violations": ["manifest unreadable: %s" % _ascii(e)],
              "warnings": [], "facts": {"manifest_path": cfg_path}}, args.json)
        sys.exit(2)

    violations, warnings = [], []
    cfg_dir = os.path.dirname(os.path.abspath(cfg_path))
    root_cfg = manifest.get("root", ".")
    root = root_cfg if os.path.isabs(root_cfg) else os.path.normpath(os.path.join(cfg_dir, root_cfg))
    runner = (manifest.get("runner") or "pytest").lower()

    facts = {"manifest_path": cfg_path, "root": root, "runner": runner,
             "root_exists": os.path.isdir(root)}
    if not facts["root_exists"]:
        violations.append("root does not exist: %s" % root)

    now = time.time()
    facts["clock"] = {"value": int(now), "plausible_epoch_bounds": [CLOCK_FLOOR, CLOCK_CEIL],
                      "sane": CLOCK_FLOOR <= now <= CLOCK_CEIL}
    if not facts["clock"]["sane"]:
        violations.append("system clock outside plausible bounds: %d" % int(now))

    git_mode = (manifest.get("git_mode") or "snapshot").lower()
    facts["git_mode"] = git_mode
    if facts["root_exists"]:
        facts["is_git_repo"] = detect_git(root)
        if git_mode == "git" and not facts["is_git_repo"]:
            violations.append("git_mode=git but %s is not a git work tree" % root)
        if git_mode == "worktree":
            wt = manifest.get("worktree_dir")
            facts["worktree_dir"] = wt
            if not wt or not os.path.isdir(os.path.join(root, wt)):
                warnings.append("git_mode=worktree but worktree_dir missing/not found")

    facts["test_cmd"] = manifest.get("test_cmd")
    facts["smoke_cmd"] = manifest.get("smoke_cmd")
    if manifest.get("smoke_cmd") is None:
        warnings.append("no smoke_cmd -- E2E gate disabled; pipeline would be unit-green only (L009)")

    disc = None
    if facts["root_exists"] and runner == "pytest":
        disc = pytest_collect(manifest.get("test_cmd"), root, args.timeout)
        if not disc["ok"]:
            warnings.append("pytest collection failed (env not set up?) -- see discovery tail")
        elif disc.get("count") in (0, None):
            warnings.append("pytest collected 0 tests at this root")
    elif runner != "pytest":
        warnings.append("runner '%s' discovery not implemented (seam only); declared, not validated" % runner)
    facts["discovery"] = disc

    gt = compose_groundtruth(manifest, root) if facts["root_exists"] else None
    if gt:
        facts["ground_truth"] = {"verdict": gt.get("verdict"), "violations": gt.get("violations", [])}
        if gt.get("verdict") == "BLOCK":
            violations.append("swarm-verify ground-truth BLOCK: %s" % _ascii(json.dumps(gt.get("violations", []))))

    if args.baseline and facts["root_exists"]:
        facts["baseline"] = run_baseline(manifest.get("test_cmd"), root, args.timeout * 6, runner)

    verdict = "BLOCK" if violations else ("WARN" if warnings else "PASS")
    emit({"schema": "tdd-preflight/v1", "verdict": verdict,
          "violations": violations, "warnings": warnings, "facts": facts}, args.json)
    sys.exit(2 if verdict == "BLOCK" else 0)


if __name__ == "__main__":
    main()
