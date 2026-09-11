# -*- coding: utf-8 -*-
"""
preflight.py -- Mechanism 1: ground-truth pre-flight.

Probes live environment state at swarm-launch time and writes a trusted
snapshot (STATE.md + state.json) that every builder must read FIRST. Replaces
"the agent's assumption about the world" with "a measurement of the world."

Kills the wrong-repo / stale-dir / bad-epoch class of failures by:
  - measuring cwd, git root/remote/HEAD, hostname (never assuming them)
  - asserting the canonical target and a stale-dir blacklist
  - sanity-bounding the clock and publishing a trusted `now` + bounds
  - treating an unreachable probe as UNKNOWN (never a silent assumption)

Config-driven (swarm.config.json) so it carries NO hardcoded values/secrets.
Stdlib only. Windows-safe: `python` (not python3), ASCII output (L018).

Usage:
  python preflight.py [--config PATH] [--cwd PATH] [--json] [--hook]

Exit codes:
  0  PASS or WARN (swarm may launch; WARN injects advisories)
  2  BLOCK (a hard violation; enforcement=block in config)
  0  also returned when no config is found (inert / silent pass)
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

try:  # never crash on a cp1252 console (recurring Windows friction / L018)
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCHEMA = "swarm-state/v1"
CONFIG_NAME = "swarm.config.json"
# Absolute plausibility window for the SYSTEM clock (2025-01-01 .. 2030-01-01).
CLOCK_FLOOR = 1735689600
CLOCK_CEIL = 1893456000


def find_config(start, explicit):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    cur = os.path.abspath(start)
    while True:
        cand = os.path.join(cur, CONFIG_NAME)
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def run(cmd, timeout=3):
    """Run a probe command. Returns (ok, stdout) or (False, None) on any error.
    A failure is UNKNOWN, never an assumption."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return True, r.stdout.strip()
        return False, None
    except Exception:
        return False, None


def fact(value, volatility, status="ok", detail=""):
    return {"value": value, "volatility": volatility, "status": status, "detail": detail}


def norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def probe(cwd, config):
    facts = {}
    violations = []

    # --- cwd (stable for the run) ---
    facts["cwd"] = fact(cwd, "stable")

    # --- git (volatile: HEAD moves) ---
    ok, root = run(["git", "-C", cwd, "rev-parse", "--show-toplevel"])
    facts["git_root"] = fact(root if ok else None, "stable",
                             "ok" if ok else "unknown",
                             "" if ok else "not a git repo or git unavailable")
    if config.get("require_git") and not ok:
        violations.append("require_git=true but cwd is not inside a git repo")

    ok, remote = run(["git", "-C", cwd, "remote", "-v"])
    facts["git_remote"] = fact((remote.splitlines()[0] if (ok and remote) else None),
                               "stable", "ok" if (ok and remote) else "unknown")

    ok, head = run(["git", "-C", cwd, "rev-parse", "--short", "HEAD"])
    facts["git_head"] = fact(head if ok else None, "volatile",
                             "ok" if ok else "unknown")

    # --- hostname (stable) ---
    try:
        facts["hostname"] = fact(socket.gethostname(), "stable")
    except Exception:
        facts["hostname"] = fact(None, "stable", "unknown")

    # --- canonical target assertion (the wrong-repo guard) ---
    canonical = config.get("canonical_dir")
    if canonical:
        ok_dir = norm(cwd).startswith(norm(canonical))
        facts["canonical_dir"] = fact(canonical, "stable",
                                      "ok" if ok_dir else "violation",
                                      "" if ok_dir else "cwd is OUTSIDE the canonical dir")
        if not ok_dir:
            violations.append(
                "cwd is not under canonical_dir (%s) -- you may be in the WRONG repo" % canonical)

    # --- stale-dir blacklist (negative assertion) ---
    stale = config.get("stale_dirs") or []
    cwd_low = cwd.replace("\\", "/").lower()
    hit = [s for s in stale if ("/%s" % s.lower().strip("/")) in cwd_low
           or cwd_low.rstrip("/").endswith(s.lower().strip("/"))]
    if hit:
        facts["stale_dir"] = fact(hit, "stable", "violation",
                                  "cwd matches a known stale/non-canonical dir")
        violations.append("cwd matches stale_dirs %s -- do NOT treat as source of truth" % hit)
    else:
        facts["stale_dir"] = fact(None, "stable", "ok")

    # --- clock sanity + trusted `now` (the bad-epoch guard) ---
    now = time.time()
    clock_ok = CLOCK_FLOOR <= now <= CLOCK_CEIL
    past_days, fut_days = (config.get("clock_bounds_days") or [365, 1])
    bounds = [int(now - past_days * 86400), int(now + fut_days * 86400)]
    facts["clock"] = fact(
        {"epoch": int(now),
         "iso": datetime.now().astimezone().isoformat(timespec="seconds"),
         "iso_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "plausible_epoch_bounds": bounds},
        "volatile", "ok" if clock_ok else "violation",
        "" if clock_ok else "SYSTEM CLOCK implausible -- any derived timestamp is suspect")
    if not clock_ok:
        violations.append("system clock outside plausible window -- timestamps untrustworthy")

    # --- optional remote host liveness (UNKNOWN on failure, never assume up) ---
    host = config.get("target_host")
    if host:
        check = config.get("host_check_cmd") or "true"
        ok, out = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                       host, check], timeout=8)
        if ok:
            facts["target_host"] = fact({"host": host, "result": out or "alive"},
                                        "volatile", "ok")
        else:
            facts["target_host"] = fact({"host": host}, "volatile", "unknown",
                                        "host probe failed/timed out -- treat as UNKNOWN")
            if config.get("require_host"):
                violations.append("require_host=true but %s is UNKNOWN (unreachable)" % host)

    return facts, violations


def build_state(cwd, config, config_path):
    facts, violations = probe(cwd, config)
    now = time.time()
    enforcement = (config.get("enforcement") or "warn").lower()
    if violations:
        verdict = "BLOCK" if enforcement == "block" else "WARN"
    else:
        verdict = "PASS"
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_at_epoch": int(now),
        "ttl_seconds": int(config.get("ttl_seconds") or 900),
        "config_path": config_path,
        "enforcement": enforcement,
        "facts": facts,
        "violations": violations,
        "verdict": verdict,
    }


def state_dir_for(cwd, config):
    sd = config.get("state_dir") or ".swarm"
    d = sd if os.path.isabs(sd) else os.path.join(cwd, sd)
    os.makedirs(d, exist_ok=True)
    return d


def render_md(state):
    L = ["# SWARM GROUND-TRUTH STATE",
         "",
         "Generated: %s  (epoch %d, ttl %ds)" % (
             state["generated_at"], state["generated_at_epoch"], state["ttl_seconds"]),
         "Verdict: **%s**" % state["verdict"],
         "",
         "> Read this BEFORE acting. Do not act on any state claim absent here.",
         "> Use `clock.value.iso` as the trusted current time; reject any epoch",
         "> outside `plausible_epoch_bounds`.",
         "",
         "## Facts"]
    for k, f in state["facts"].items():
        tag = {"ok": "[OK]", "unknown": "[UNKNOWN]", "violation": "[VIOLATION]"}.get(
            f.get("status"), "[?]")
        v = f.get("value")
        v = json.dumps(v) if isinstance(v, (dict, list)) else v
        line = "- %s **%s** (%s): %s" % (tag, k, f.get("volatility"), v)
        if f.get("detail"):
            line += "  -- %s" % f["detail"]
        L.append(line)
    if state["violations"]:
        L += ["", "## VIOLATIONS"] + ["- [VIOLATION] %s" % v for v in state["violations"]]
    L.append("")
    return "\n".join(L)


def summarize(state):
    """One-screen ASCII summary for hook context injection."""
    f = state["facts"]
    parts = ["<swarm-preflight verdict=%s>" % state["verdict"]]
    parts.append("Ground truth measured (read STATE before dispatching builders):")
    if "canonical_dir" in f:
        parts.append("- canonical_dir: %s [%s]" % (f["canonical_dir"]["value"],
                                                   f["canonical_dir"]["status"]))
    parts.append("- cwd: %s" % f["cwd"]["value"])
    if f.get("git_root", {}).get("value"):
        parts.append("- git_root: %s  HEAD %s" % (f["git_root"]["value"],
                                                  f.get("git_head", {}).get("value")))
    parts.append("- now: %s (reject epochs outside %s)" % (
        f["clock"]["value"]["iso"], f["clock"]["value"]["plausible_epoch_bounds"]))
    if "target_host" in f:
        parts.append("- target_host: %s [%s]" % (json.dumps(f["target_host"]["value"]),
                                                 f["target_host"]["status"]))
    for v in state["violations"]:
        parts.append("- [VIOLATION] %s" % v)
    parts.append("STATE written to .swarm/STATE.md")
    parts.append("</swarm-preflight>")
    return "\n".join(parts)


def hook_envelope(state):
    """Full PreToolUse hook JSON: block-decision on BLOCK, else context injection.
    (Block is conveyed via JSON + exit 0, mirroring pre-edit-guardian.)"""
    s = summarize(state)
    if state["verdict"] == "BLOCK":
        return json.dumps({"decision": "block",
                           "reason": "swarm pre-flight BLOCKED launch:\n" + s})
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": s}})


def main():
    ap = argparse.ArgumentParser(description="Swarm ground-truth pre-flight probe.")
    ap.add_argument("--config", help="path to swarm.config.json (else search cwd upward)")
    ap.add_argument("--cwd", default=os.getcwd(), help="working dir to probe")
    ap.add_argument("--json", action="store_true", help="emit machine state.json to stdout")
    ap.add_argument("--hook", action="store_true",
                    help="hook mode: print context summary; silent+exit0 if no config")
    ap.add_argument("--hook-emit", action="store_true",
                    help="PreToolUse mode: read hook payload on stdin, print full hook JSON")
    args = ap.parse_args()

    if args.hook_emit:
        args.hook = True  # share inert / TTL / no-config behavior
        try:
            # read raw bytes + decode utf-8 so a non-ASCII payload can't trigger a
            # cp1252 stdin crash on Windows (recurring friction / L018)
            raw = sys.stdin.buffer.read().decode("utf-8", "replace")
            payload = json.loads(raw)
            args.cwd = payload.get("cwd") or os.environ.get("PWD") or args.cwd
        except Exception:
            args.cwd = os.environ.get("PWD") or args.cwd

    cwd = os.path.abspath(args.cwd)
    config_path = find_config(cwd, args.config)

    if not config_path:
        if args.hook:
            return 0  # inert: no config => no pre-flight (silent pass, like cwd-router)
        print("[swarm-preflight] no %s found at or above %s -- nothing to do." %
              (CONFIG_NAME, cwd))
        return 0

    try:
        with open(config_path, "r", encoding="utf-8-sig") as fh:  # tolerate BOM (PowerShell)
            config = json.load(fh)
    except Exception as e:
        msg = "[swarm-preflight] failed to read %s: %s" % (config_path, e)
        if not args.hook:
            print(msg)
        return 0  # fail open

    # TTL fast-path: in hook mode, reuse a fresh snapshot (avoid re-probing remote
    # hosts on every Workflow call).
    sd = state_dir_for(cwd, config)
    state_json = os.path.join(sd, "state.json")
    if args.hook and os.path.isfile(state_json):
        try:
            age = time.time() - os.path.getmtime(state_json)
            with open(state_json, "r", encoding="utf-8") as fh:
                cached = json.load(fh)
            if age < cached.get("ttl_seconds", 900):
                if args.hook_emit:
                    print(hook_envelope(cached))
                    return 0
                print(summarize(cached))
                return 2 if cached.get("verdict") == "BLOCK" else 0
        except Exception:
            pass

    state = build_state(cwd, config, config_path)
    try:
        with open(state_json, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        with open(os.path.join(sd, "STATE.md"), "w", encoding="utf-8") as fh:
            fh.write(render_md(state))
    except Exception:
        pass  # fail open on write

    if args.hook_emit:
        print(hook_envelope(state))
        return 0
    if args.json:
        print(json.dumps(state, indent=2))
    elif args.hook:
        print(summarize(state))
    else:
        print(render_md(state))

    return 2 if state["verdict"] == "BLOCK" else 0


if __name__ == "__main__":
    sys.exit(main())
