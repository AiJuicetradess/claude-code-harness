#!/usr/bin/env python
"""
audit_preflight.py -- Phase-0 ground truth for the infra-audit gate.

Before any reading is taken, any snapshot is written, or any proposal is made, this
establishes that the world is what we think it is:
  - a manifest (audit.config.json) actually arms THIS tree -- with none, we REFUSE
    and exit 2; the gate never guesses its target, bounds, or destructive scope (S4)
  - the reference clock is plausible (a SUSPECT clock -> WARN; every time-derived
    metric downstream would be quarantined anyway)
  - the signing toolchain is present (ssh-keygen on PATH) -- a fact, surfaced, not
    assumed
  - if a swarm-verify preflight is discoverable, its verdict is folded in as ADVISORY
    (never authoritative, never fatal): compose ground truth, don't reinvent it

Emits a verdict (PASS / WARN / BLOCK / REFUSE) and the facts it rests on. Exits 0 for
PASS/WARN (the gate may proceed) and 2 for BLOCK/REFUSE (it may not).

stdlib only; ASCII output; Windows-safe: `python` (not python3), list-arg subprocess
with timeouts (no shell string interpolation). Reads JSON with utf-8-sig (BOM).
Exit (direct, no args): 0 self-test OK, 1 failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import bounds  # noqa: E402

MANIFEST_NAME = "audit.config.json"
PASS, WARN, BLOCK, REFUSE = "PASS", "WARN", "BLOCK", "REFUSE"
SWARM_PREFLIGHT_REL = os.path.join(".claude", "skills", "swarm-verify", "scripts", "preflight.py")
SUBPROC_TIMEOUT_SECONDS = 8


def find_manifest(start):
    """Walk up from `start` to find audit.config.json. Returns (manifest, path) or
    (None, None). A read/parse error is reported as (None, path) so the caller can
    distinguish 'no manifest' from 'broken manifest'."""
    d = os.path.abspath(start)
    seen = set()
    while d and d not in seen:
        seen.add(d)
        p = os.path.join(d, MANIFEST_NAME)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    return json.load(f), p
            except Exception:
                return None, p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None, None


def _which(name):
    """True if an executable is discoverable on PATH. Prefer shutil.which (no probe
    process); fall back to a list-arg version probe with a timeout."""
    if shutil.which(name):
        return True
    try:
        r = subprocess.run([name, "-V"], capture_output=True, text=True,
                           timeout=SUBPROC_TIMEOUT_SECONDS)
        return r.returncode == 0
    except Exception:
        return False


def _discover_swarm_preflight(manifest):
    """Locate a swarm-verify preflight.py. Priority: an explicit 'preflight' path in
    the manifest, else the conventional ~/.claude/skills/swarm-verify location.
    Returns a path or None (None => simply skip; never an error)."""
    explicit = (manifest or {}).get("preflight")
    if explicit and os.path.isfile(explicit):
        return explicit
    candidate = os.path.join(os.path.expanduser("~"), SWARM_PREFLIGHT_REL)
    return candidate if os.path.isfile(candidate) else None


def _swarm_advisory(manifest, root):
    """Best-effort: run the swarm-verify preflight and fold its verdict in as
    advisory. Any failure -- absent, timeout, non-zero, non-JSON -- yields a
    'skipped'/'unavailable' status and NEVER fails this preflight."""
    path = _discover_swarm_preflight(manifest)
    if not path:
        return {"status": "skipped", "detail": "no swarm-verify preflight discoverable"}
    try:
        r = subprocess.run(
            [sys.executable, path, "--json", "--cwd", os.path.abspath(root)],
            capture_output=True, text=True, timeout=SUBPROC_TIMEOUT_SECONDS)
    except Exception as e:
        return {"status": "unavailable", "detail": "probe failed (%s)" % type(e).__name__}
    out = (r.stdout or "").strip()
    try:
        parsed = json.loads(out)
    except Exception:
        # Inert / no-config / human-readable output -> ignore, as specified.
        return {"status": "non-json", "detail": "swarm preflight emitted no JSON verdict"}
    return {"status": "ok", "verdict": parsed.get("verdict"),
            "violations": parsed.get("violations", [])}


def run_preflight(root, now=None):
    """Pure function: gather facts + decide a verdict. Returns a result dict; the CLI
    layer maps that to stdout + an exit code. `now` is injectable for tests."""
    now = now if now is not None else int(time.time())
    manifest, mpath = find_manifest(root)

    if manifest is None:
        reason = ("manifest present but unreadable: %s" % mpath) if mpath \
            else "no %s at or above %s" % (MANIFEST_NAME, os.path.abspath(root))
        return {
            "verdict": REFUSE,
            "warnings": [],
            "blocks": [reason],
            "facts": {"manifest_path": mpath, "root": os.path.abspath(root)},
            "swarm_advisory": {"status": "skipped", "detail": "no manifest"},
        }

    warnings, blocks = [], []

    clock_state, clock_reason = bounds.clock_state(now, manifest.get("clock"))
    if clock_state == bounds.SUSPECT:
        warnings.append("reference clock SUSPECT: %s" % clock_reason)

    ssh_keygen = _which("ssh-keygen")
    if not ssh_keygen:
        # Signing is the heart of the gate; a missing toolchain is a real warning,
        # but it is the operator's call whether to proceed (not a hard block here).
        warnings.append("ssh-keygen not found on PATH -- signature verification unavailable")

    swarm = _swarm_advisory(manifest, root)
    if swarm.get("status") == "ok" and swarm.get("verdict") == "BLOCK":
        # Advisory only: a swarm BLOCK escalates us to WARN, never to BLOCK. The
        # infra-audit gate does not delegate its refuse/block authority outward.
        warnings.append("swarm-verify preflight reports BLOCK (advisory): %s"
                        % ("; ".join(swarm.get("violations") or []) or "see swarm STATE"))

    facts = {
        "manifest_path": mpath,
        "root": os.path.abspath(root),
        "box_id": manifest.get("box_id"),
        "box_class": manifest.get("box_class"),
        "state_dir": manifest.get("state_dir", ".audit"),
        "allowlist_size": len(manifest.get("allowlist", []) or []),
        "denylist_size": len(manifest.get("denylist", []) or []),
        "ssh_keygen_on_path": ssh_keygen,
        "clock_state": clock_state,
        "clock_reason": clock_reason,
    }

    verdict = BLOCK if blocks else (WARN if warnings else PASS)
    return {"verdict": verdict, "warnings": warnings, "blocks": blocks,
            "facts": facts, "swarm_advisory": swarm}


def exit_code_for(verdict):
    """0 lets the gate proceed (PASS/WARN); 2 stops it (BLOCK/REFUSE)."""
    return 0 if verdict in (PASS, WARN) else 2


def render(result):
    """ASCII human view of a preflight result."""
    f = result.get("facts", {})
    lines = ["=== infra-audit preflight (Phase-0 ground truth) ===",
             "VERDICT: %s" % result["verdict"]]
    lines.append("manifest    : %s" % f.get("manifest_path"))
    lines.append("box_id      : %s" % f.get("box_id"))
    lines.append("box_class   : %s" % f.get("box_class"))
    lines.append("state_dir   : %s" % f.get("state_dir"))
    lines.append("allowlist   : %s entries" % f.get("allowlist_size"))
    lines.append("denylist    : %s entries" % f.get("denylist_size"))
    lines.append("ssh-keygen  : %s" % ("on PATH" if f.get("ssh_keygen_on_path") else "NOT FOUND"))
    lines.append("clock       : %s (%s)" % (f.get("clock_state"), f.get("clock_reason")))
    sw = result.get("swarm_advisory", {})
    lines.append("swarm-verify: %s%s" % (
        sw.get("status"),
        (" verdict=%s" % sw.get("verdict")) if sw.get("verdict") else ""))
    for w in result.get("warnings", []):
        lines.append("  [WARN]  %s" % w)
    for b in result.get("blocks", []):
        lines.append("  [BLOCK] %s" % b)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="infra-audit Phase-0 preflight (ground truth)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--now", type=int, default=None, help="override epoch (else system time)")
    ap.add_argument("--json", action="store_true", help="emit machine result JSON to stdout")
    args = ap.parse_args()

    result = run_preflight(args.root, now=args.now)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        sys.stdout.write(render(result) + "\n")
    return exit_code_for(result["verdict"])


def self_test():
    now = 1800000000
    tmp = tempfile.mkdtemp(prefix="audit_preflight_test_")
    try:
        # --- fixture WITH a minimal manifest -> PASS or WARN, box_id matches ---
        manifest = {
            "schema": "audit-config/v1",
            "box_id": "fixture-box",
            "box_class": "client",
            "state_dir": ".audit",
            "allowlist": ["/var/log", "/tmp"],
            "denylist": ["*.key", ".env"],
            "clock": {"floor_epoch": bounds.CLOCK_FLOOR, "ceil_epoch": bounds.CLOCK_CEIL,
                      "max_skew_seconds": 300},
            "preflight": None,
        }
        with open(os.path.join(tmp, MANIFEST_NAME), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=True, indent=2)

        res = run_preflight(tmp, now=now)
        assert res["verdict"] in (PASS, WARN), "preflight: expected PASS/WARN, got %s" % res["verdict"]
        assert exit_code_for(res["verdict"]) == 0, "preflight: PASS/WARN must exit 0"
        assert res["facts"]["box_id"] == "fixture-box", "preflight: box_id mismatch"
        assert res["facts"]["box_class"] == "client", "preflight: box_class mismatch"
        assert res["facts"]["allowlist_size"] == 2, "preflight: allowlist size wrong"
        assert res["facts"]["denylist_size"] == 2, "preflight: denylist size wrong"
        assert res["facts"]["clock_state"] == bounds.OK, "preflight: good clock should be OK"
        # swarm advisory must be present and must NOT have flipped us to BLOCK/REFUSE.
        assert "swarm_advisory" in res, "preflight: swarm advisory missing"
        assert res["verdict"] not in (BLOCK, REFUSE), "preflight: advisory escalated improperly"

        # --- SUSPECT clock -> WARN (time-derived metrics would be quarantined) ---
        res_badclock = run_preflight(tmp, now=100)
        assert res_badclock["facts"]["clock_state"] == bounds.SUSPECT, "preflight: bad clock not SUSPECT"
        assert res_badclock["verdict"] == WARN, "preflight: SUSPECT clock should WARN"
        assert exit_code_for(res_badclock["verdict"]) == 0, "preflight: WARN must exit 0"

        # --- REFUSE: a dir with NO manifest -> verdict REFUSE, exit-code 2 ---
        empty = tempfile.mkdtemp(prefix="audit_preflight_empty_")
        try:
            res_none = run_preflight(empty, now=now)
            assert res_none["verdict"] == REFUSE, "preflight: no manifest must REFUSE"
            assert exit_code_for(res_none["verdict"]) == 2, "preflight: REFUSE must exit 2"
            assert res_none["blocks"], "preflight: REFUSE should carry a reason"
        finally:
            shutil.rmtree(empty, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # clean up the fixture tree
    return True


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) == 1:
        try:
            self_test()
        except AssertionError as e:
            sys.stdout.write("audit_preflight self-test FAILED: %s\n" % e)
            sys.exit(1)
        sys.stdout.write("audit_preflight self-test OK (PASS/WARN+box_id, SUSPECT-clock WARN, REFUSE exit-2)\n")
        sys.exit(0)
    sys.exit(main())  # main() returns the verdict's exit code (0 PASS/WARN, 2 BLOCK/REFUSE)
