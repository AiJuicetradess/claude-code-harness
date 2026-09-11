#!/usr/bin/env python
"""
propose.py -- the UNPRIVILEGED agent side. It only PROPOSES; it executes nothing.

Given an executor-issued nonce and a list of concrete paths, it enumerates each item's
identity (path,dev,inode,size,mtime), screens the set against the allowlist/denylist
(defense in depth -- the executor re-checks authoritatively by (dev,inode)), screens the
predicted effect for plausibility (a proposal that would free more than exists is SUSPECT
before it ever reaches the human), and writes a PENDING proposal record whose fingerprint
the operator signs with `authorize`.

stdlib only; ASCII output; Windows-safe. Exit (direct, no args): 0 self-test OK, 1 failed.
"""
import argparse
import fnmatch
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import canon  # noqa: E402

MANIFEST_NAME = "audit.config.json"


def load_manifest(start):
    d = os.path.abspath(start)
    seen = set()
    while d and d not in seen:
        seen.add(d)
        p = os.path.join(d, MANIFEST_NAME)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8-sig") as f:
                return json.load(f), p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None, None


def _identity(path):
    st = os.lstat(path)
    return {"path": os.path.realpath(path), "dev": st.st_dev, "inode": st.st_ino,
            "size": st.st_size, "mtime": int(st.st_mtime)}


def _in_allowlist(rp, allow):
    rp = rp.replace("\\", "/")
    for a in allow:
        a = a.replace("\\", "/").rstrip("/")
        if rp == a or rp.startswith(a + "/"):
            return True
    return False


def _deny(rp, deny_globs):
    base = os.path.basename(rp)
    rpp = rp.replace("\\", "/")
    return any(fnmatch.fnmatch(rpp, g) or fnmatch.fnmatch(base, g) for g in deny_globs)


def screen_items(items, allowlist, deny_globs):
    """Defense-in-depth propose-time filter. Returns (proposable, rejected)."""
    proposable, rejected = [], []
    for it in items:
        rp = it.get("path", "")
        if not _in_allowlist(rp, allowlist):
            rejected.append({"path": rp, "why": "outside allowlist"})
        elif _deny(rp, deny_globs):
            rejected.append({"path": rp, "why": "denylist"})
        else:
            proposable.append(it)
    return proposable, rejected


def bounds_screen(predicted_effect, manifest, ctx=None):
    """Flag an implausible predicted reclaim as SUSPECT before it reaches the human."""
    ctx = ctx or {}
    caps = (manifest or {}).get("caps", {})
    if not isinstance(predicted_effect, int) or predicted_effect < 0:
        return {"state": "SUSPECT", "reason": "predicted_effect not a non-negative int"}
    disk_total = ctx.get("disk_total")
    if disk_total is not None and predicted_effect > disk_total:
        return {"state": "SUSPECT", "reason": "predicted reclaim exceeds disk_total"}
    if predicted_effect > caps.get("max_bytes", 1 << 62):
        return {"state": "SUSPECT", "reason": "predicted reclaim exceeds cap max_bytes"}
    return {"state": "OK", "reason": "predicted effect plausible"}


def build_payload(action_type, items, reason, nonce, box_id, now, ttl_seconds):
    return {
        "action_type": action_type,
        "box_id": box_id,
        "enumerated_items": items,
        "predicted_effect": int(sum(int(it.get("size") or 0) for it in items)),
        "reason": reason,
        "proposal_id": nonce,
        "not_after": int(now + ttl_seconds),
    }


def build_record(payload, identity_hint=""):
    return {"payload": payload, "fingerprint": canon.fingerprint(payload),
            "identity": identity_hint, "signature": None}


def propose(start_root, action_type, nonce, reason, paths, identity_hint, ttl_seconds, now=None):
    manifest, mpath = load_manifest(start_root)
    if not manifest:
        return {"ok": False, "reason": "no audit.config.json (S4)"}
    now = now or int(time.time())
    items, missing = [], []
    for p in paths:
        if os.path.lexists(p):
            items.append(_identity(p))
        else:
            missing.append(p)
    proposable, rejected = screen_items(items, manifest.get("allowlist", []),
                                        manifest.get("denylist", []))
    payload = build_payload(action_type, proposable, reason, nonce,
                            manifest.get("box_id"), now, ttl_seconds)
    screen = bounds_screen(payload["predicted_effect"], manifest)
    rec = build_record(payload, identity_hint)
    rec["created_ts"] = now
    rec["screen"] = screen
    rec["rejected"] = rejected
    rec["missing"] = missing
    sd = manifest.get("state_dir", ".audit")
    sd = sd if os.path.isabs(sd) else os.path.join(os.path.abspath(start_root), sd)
    pdir = os.path.join(sd, "proposals")
    os.makedirs(pdir, exist_ok=True)
    out_path = os.path.join(pdir, "%s.json" % nonce.replace("/", "_"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=True, indent=2)
    return {"ok": True, "proposal": out_path, "fingerprint": rec["fingerprint"],
            "proposable": len(proposable), "rejected": len(rejected), "screen": screen,
            "render": canon.render(payload)}


def self_test():
    items = [
        {"path": "/var/log/a.gz", "dev": 1, "inode": 1, "size": 10, "mtime": 1},
        {"path": "/etc/passwd", "dev": 1, "inode": 2, "size": 10, "mtime": 1},
        {"path": "/var/log/secret.key", "dev": 1, "inode": 3, "size": 10, "mtime": 1},
    ]
    prop, rej = screen_items(items, ["/var/log"], ["*.key", "/etc/*"])
    assert len(prop) == 1 and prop[0]["path"] == "/var/log/a.gz", "screen proposable"
    assert len(rej) == 2, "screen rejected /etc + *.key"
    payload = build_payload("delete", prop, "cleanup", "nonce-abc", "box1", 1800000000, 3600)
    rec = build_record(payload)
    assert rec["fingerprint"] == canon.fingerprint(payload), "fingerprint matches canon"
    assert bounds_screen(-5, {})["state"] == "SUSPECT", "negative -> suspect"
    assert bounds_screen(10, {}, {"disk_total": 5})["state"] == "SUSPECT", "exceeds disk -> suspect"
    assert bounds_screen(10, {"caps": {"max_bytes": 1000}})["state"] == "OK", "plausible -> ok"
    return True


def main():
    ap = argparse.ArgumentParser(description="infra-audit proposer (unprivileged)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--action", default="delete")
    ap.add_argument("--nonce", required=True)
    ap.add_argument("--reason", default="")
    ap.add_argument("--identity", default="")
    ap.add_argument("--ttl-seconds", type=int, default=86400)
    ap.add_argument("--paths", nargs="*", default=[])
    args = ap.parse_args()
    res = propose(args.root, args.action, args.nonce, args.reason, args.paths,
                  args.identity, args.ttl_seconds)
    print(json.dumps({k: v for k, v in res.items() if k != "render"}, ensure_ascii=True, indent=2))
    if res.get("render"):
        sys.stdout.write("\n--- authorize view ---\n" + res["render"] + "\n")
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) == 1:
        try:
            self_test()
        except AssertionError as e:
            sys.stdout.write("propose self-test FAILED: %s\n" % e)
            sys.exit(1)
        sys.stdout.write("propose self-test OK (screen, fingerprint, bounds-screen)\n")
        sys.exit(0)
    main()
