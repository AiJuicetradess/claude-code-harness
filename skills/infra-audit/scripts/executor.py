#!/usr/bin/env python
"""
executor.py -- the privileged gate: the ONLY component that performs destruction.

It refuses to act unless ALL hold:
  - self-check passes: agent not root, and no protected file (key/executor/manifest/ledger)
        is world/group-writable; the agent-uid active write-probe is added at Linux deploy
  - the SSH signature over the canon fingerprint verifies (sign.verify_message)
  - proposal_id was executor-issued and not yet consumed (clock-independent replay defense)
  - box_id matches THIS box; not_after holds under the bounds-checked clock (best-effort)
  - each item's FULL identity (path,dev,inode,size,mtime) still matches live state
        (missing/churned -> skip that item; same path, different inode -> VOID: swap)
  - the canonical real target is inside the allowlist and not on the denylist (by dev,inode
        + glob + nlink>1) -- enforced HERE from executor-owned config
  - blast-radius caps hold
Then it acts via an O_NOFOLLOW handle, quarantine-then-purge (recoverable), and logs
provenance. The destruction itself is a POSIX seam (guarded on non-POSIX).

stdlib only; ASCII output; Windows-safe. Pure predicates are unit-tested in self_test();
the signed end-to-end + real move are exercised by the task-11 integration test.
Exit (direct, no args): 0 self-test OK, 1 failed.
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
import bounds  # noqa: E402
import canon  # noqa: E402
import ledger  # noqa: E402
import sign  # noqa: E402

MANIFEST_NAME = "audit.config.json"


# ---------- manifest ----------
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


def load_manifest(start):
    p = find_manifest(start)
    if not p:
        return None, None
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f), p


# ---------- pure predicates (unit-tested) ----------
def evaluate_self_check(euid, writable, allow_root=False):
    """euid: effective uid (0 == root). writable: {name: agent_can_write_bool} for the
    key/executor/ledger. Returns {void, reasons}. The agent must be non-root and unable
    to write any of those, or the gate is VOID (F1, D3)."""
    reasons = []
    if euid == 0 and not allow_root:
        reasons.append("running as root: gate VOID (non-root precondition)")
    for name, w in (writable or {}).items():
        if w:
            reasons.append("agent can write %s: gate VOID" % name)
    return {"void": bool(reasons), "reasons": reasons}


def exact_set_decision(signed_items, live_items):
    """Compare signed vs live by full identity. Returns
    {verdict, act[], skip[], extra[], swap[]}. verdict 'VOID' iff a swap is detected
    (same path, different dev/inode). Missing/churned -> per-item skip (no batch VOID,
    so normal log churn cannot livelock the gate). Extra live items are never touched."""
    live_by_path = {}
    for it in live_items:
        live_by_path.setdefault(it.get("path"), []).append(it)
    act, skip, swap = [], [], []
    signed_paths = set()
    for s in signed_items:
        p = s.get("path")
        signed_paths.add(p)
        cands = live_by_path.get(p)
        if not cands:
            skip.append({"path": p, "why": "missing (gone since approval)"})
            continue
        live = cands[0]
        if (live.get("dev"), live.get("inode")) != (s.get("dev"), s.get("inode")):
            swap.append({"path": p, "why": "identity swap (dev/inode changed)"})
            continue
        if (live.get("size"), live.get("mtime")) != (s.get("size"), s.get("mtime")):
            skip.append({"path": p, "why": "churned (size/mtime changed since approval)"})
            continue
        act.append(s)
    extra = [it for it in live_items if it.get("path") not in signed_paths]
    return {"verdict": ("VOID" if swap else "OK"), "act": act, "skip": skip,
            "extra": extra, "swap": swap}


def within_allowlist(real_path, allow_real):
    rp = os.path.normcase(real_path)
    for a in allow_real:
        a = os.path.normcase(a.rstrip("/\\"))
        if rp == a or rp.startswith(a + os.sep) or rp.startswith(a + "/"):
            return True
    return False


def denylist_match(real_path, dev, inode, nlink, deny_globs, deny_inodes):
    """True => REFUSE. (dev,inode) identity catches hardlink/bind aliases (C5); nlink>1
    refuses hardlinked targets (F7); glob is defense-in-depth on the canonical real path."""
    if (dev, inode) in deny_inodes:
        return True, "denylisted object identity (dev,inode)"
    base = os.path.basename(real_path)
    rp = real_path.replace("\\", "/")
    for g in deny_globs:
        if fnmatch.fnmatch(rp, g) or fnmatch.fnmatch(base, g):
            return True, "denylist glob: %s" % g
    if isinstance(nlink, int) and nlink > 1:
        return True, "hardlinked target (nlink=%d) refused" % nlink
    return False, ""


def caps_ok(n_files, total_bytes, caps):
    caps = caps or {}
    if n_files > caps.get("max_files", 1 << 30):
        return False, "max_files exceeded"
    if total_bytes > caps.get("max_bytes", 1 << 62):
        return False, "max_bytes exceeded"
    return True, ""


# ---------- POSIX seams (guarded) ----------
def is_posix():
    return os.name == "posix"


def stat_identity(path):
    """Identity dict for a path via lstat (no symlink follow). realpath canonicalizes."""
    st = os.lstat(path)
    return {"path": os.path.realpath(path), "dev": st.st_dev, "inode": st.st_ino,
            "size": st.st_size, "mtime": int(st.st_mtime), "nlink": st.st_nlink}


def protected_writable_map(path_modes):
    """path_modes: {name: st_mode}. Returns {name: world/group-writable bool}. Pure and
    cross-platform-testable (the live gather is POSIX-only)."""
    return {name: bool(mode & 0o022) for name, mode in path_modes.items()}


def gather_self_check(manifest, manifest_path, state_dir=None):
    """Real OS self-check (POSIX). VOID if running as root, OR if any protected file
    (allowed_signers / executor / manifest / ledger) is world- or group-writable. The
    agent-uid-specific active write-probe (EACCES as the agent user) is added at Linux
    deploy; on non-POSIX this is reported as a deploy-time gate."""
    if not is_posix():
        return {"void": False, "reasons": [],
                "platform": "non-posix: self-check enforced at Linux deploy"}
    sigcfg = (manifest or {}).get("signing", {})
    paths = {"allowed_signers": sigcfg.get("allowed_signers"),
             "executor": os.path.abspath(__file__),
             "manifest": manifest_path}
    if state_dir:
        paths["ledger"] = os.path.join(state_dir, "ledger.jsonl")
    path_modes, observed = {}, {}
    for name, p in paths.items():
        if p and os.path.exists(p):
            mode = os.stat(p).st_mode
            path_modes[name] = mode
            observed[name] = oct(mode & 0o777)
    writable = protected_writable_map(path_modes)
    res = evaluate_self_check(os.geteuid(), writable, allow_root=False)
    res["platform"] = "posix"
    res["observed_modes"] = observed
    return res


def safe_quarantine(real_path, exp_dev, exp_inode, quarantine_dir):
    """POSIX handle-based move-to-quarantine (recoverable). Re-verifies identity on an
    O_NOFOLLOW handle before acting. Guarded on non-POSIX. (Deploy note: harden the move
    to renameat() relative to a pinned dir-fd.)"""
    if not is_posix():
        return {"ok": False, "reason": "destruction seam is POSIX-only (validated at deploy)"}
    import shutil
    try:
        fd = os.open(real_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        return {"ok": False, "reason": "open O_NOFOLLOW failed: %s" % e}
    try:
        st = os.fstat(fd)
        if (st.st_dev, st.st_ino) != (exp_dev, exp_inode):
            return {"ok": False, "reason": "identity changed at action time (TOCTOU)"}
    finally:
        os.close(fd)
    try:
        os.makedirs(quarantine_dir, exist_ok=True)
        dst = os.path.join(quarantine_dir, "%d_%s" % (exp_inode, os.path.basename(real_path)))
        shutil.move(real_path, dst)
        return {"ok": True, "quarantined_to": dst}
    except Exception as e:
        return {"ok": False, "reason": "move failed: %s" % e}


# ---------- state helpers ----------
def _state_dir(manifest, start_root):
    sd = (manifest or {}).get("state_dir", ".audit")
    return sd if os.path.isabs(sd) else os.path.join(os.path.abspath(start_root), sd)


def _quarantine_dir(manifest, start_root):
    q = (manifest or {}).get("quarantine", {}).get("dir", ".audit/quarantine")
    return q if os.path.isabs(q) else os.path.join(os.path.abspath(start_root), q)


def issue_nonce(state_dir):
    os.makedirs(state_dir, exist_ok=True)
    n = "nonce-" + os.urandom(12).hex()
    with open(os.path.join(state_dir, "issued.txt"), "a", encoding="utf-8") as f:
        f.write(n + "\n")
    return n


def _issued(issued_path, nonce):
    if not nonce or not os.path.isfile(issued_path):
        return False
    with open(issued_path, "r", encoding="utf-8") as f:
        return any(line.strip() == nonce for line in f)


def _resolve_deny_inodes(deny_globs):
    s = set()
    for g in deny_globs:
        if os.path.isabs(g) and "*" not in g and "?" not in g and os.path.lexists(g):
            try:
                st = os.lstat(g)
                s.add((st.st_dev, st.st_ino))
            except Exception:
                pass
    return s


def _provenance(state_dir, rec, out, now):
    try:
        os.makedirs(state_dir, exist_ok=True)
        line = {"ts": now, "proposal_id": rec.get("payload", {}).get("proposal_id"),
                "fingerprint": rec.get("fingerprint"), "verdict": out.get("verdict"),
                "predicted_bytes": out.get("predicted_bytes"),
                "actual_items": out.get("actual_items")}
        with open(os.path.join(state_dir, "provenance.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=True) + "\n")
    except Exception:
        pass


# ---------- orchestration ----------
def execute(proposal_path, start_root, now=None):
    manifest, mpath = load_manifest(start_root)
    if not manifest:
        return {"ok": False, "verdict": "REFUSE", "reason": "no audit.config.json (S4)"}
    now = now or int(time.time())
    state_dir = _state_dir(manifest, start_root)
    sc = gather_self_check(manifest, mpath, state_dir)
    if sc.get("void"):
        return {"ok": False, "verdict": "VOID", "reason": "self-check failed", "detail": sc.get("reasons")}
    with open(proposal_path, "r", encoding="utf-8-sig") as f:
        rec = json.load(f)
    payload = rec.get("payload", {})
    if canon.fingerprint(payload) != rec.get("fingerprint"):
        return {"ok": False, "verdict": "VOID", "reason": "fingerprint mismatch"}
    fp = rec.get("fingerprint")
    if payload.get("box_id") != manifest.get("box_id"):
        return {"ok": False, "verdict": "VOID", "reason": "box_id mismatch"}
    sig = rec.get("signature")
    if not sig:
        return {"ok": False, "verdict": "PENDING", "reason": "no signature (awaiting authorize)"}
    sigcfg = manifest.get("signing", {})
    sig_bytes = sig.encode("utf-8") if isinstance(sig, str) else sig
    vr = sign.verify_message(fp.encode("ascii"), sig_bytes, sigcfg.get("allowed_signers"),
                             rec.get("identity", ""), sigcfg.get("namespace", ""))
    if not vr["ok"]:
        return {"ok": False, "verdict": "VOID", "reason": "signature: %s" % vr["reason"]}
    cstate, _ = bounds.clock_state(now, manifest.get("clock"))
    na = payload.get("not_after")
    if cstate == bounds.OK and isinstance(na, int) and now > na:
        return {"ok": False, "verdict": "VOID", "reason": "token expired (not_after)"}
    nonce = payload.get("proposal_id", "")
    if not _issued(os.path.join(state_dir, "issued.txt"), nonce):
        return {"ok": False, "verdict": "VOID", "reason": "proposal_id not executor-issued (C9)"}
    # Re-resolve live identities + exact-set + allow/deny/caps BEFORE consuming the nonce,
    # so a no-op (everything churned/missing/denied) never burns a signed token (finding 1).
    signed_items = payload.get("enumerated_items", [])
    live_items = []
    for s in signed_items:
        p = s.get("path")
        if p and os.path.lexists(p):
            try:
                live_items.append(stat_identity(p))
            except Exception:
                pass
    dec = exact_set_decision(signed_items, live_items)
    if dec["verdict"] == "VOID":
        return {"ok": False, "verdict": "VOID", "reason": "identity swap detected", "swap": dec["swap"]}
    allow_real = [os.path.realpath(a) for a in manifest.get("allowlist", [])]
    deny_globs = manifest.get("denylist", [])
    deny_inodes = _resolve_deny_inodes(deny_globs)
    final, refused = [], []
    for it in dec["act"]:
        rp = it.get("path")
        if not within_allowlist(rp, allow_real):
            refused.append({"path": rp, "why": "outside allowlist"})
            continue
        dm, why = denylist_match(rp, it.get("dev"), it.get("inode"), it.get("nlink"),
                                 deny_globs, deny_inodes)
        if dm:
            refused.append({"path": rp, "why": why})
            continue
        final.append(it)
    nbytes = sum(int(it.get("size") or 0) for it in final)
    cok, cwhy = caps_ok(len(final), nbytes, manifest.get("caps"))
    if not cok:
        return {"ok": False, "verdict": "VOID", "reason": cwhy}
    # Nothing to act on -> do NOT consume the nonce; the signature stays valid for a retry
    # once the world settles (finding 1: a no-op must not burn the token).
    if not final:
        return {"ok": True, "verdict": "NOOP", "reason": "nothing to act on (all skipped/denied)",
                "skipped": dec["skip"], "ignored_extra": len(dec["extra"]), "refused": refused,
                "consumed": False}
    # Consume the nonce exactly now -- after the decision, immediately before acting.
    cons = ledger.consume(os.path.join(state_dir, "ledger.jsonl"), nonce, now)
    if not cons["ok"]:
        return {"ok": False, "verdict": "VOID", "reason": cons["reason"], "ledger": cons}
    qdir = _quarantine_dir(manifest, start_root)
    acted, failed = [], []
    for it in final:
        res = safe_quarantine(it["path"], it["dev"], it["inode"], qdir)
        (acted if res.get("ok") else failed).append({"path": it["path"], "res": res})
    out = {"ok": True, "verdict": "EXECUTED", "acted": acted, "failed": failed,
           "skipped": dec["skip"], "ignored_extra": len(dec["extra"]), "refused": refused,
           "predicted_bytes": payload.get("predicted_effect"), "actual_items": len(acted),
           "consumed": True}
    if cstate != bounds.OK:
        out["clock_note"] = "clock SUSPECT: not_after expiry not enforced (ledger is the replay defense)"
    _provenance(state_dir, rec, out, now)
    return out


def self_test():
    # F1 -- root / agent-writable -> VOID
    assert evaluate_self_check(0, {})["void"], "F1 root void"
    assert evaluate_self_check(1000, {"allowed_signers": True})["void"], "F1 writable void"
    assert not evaluate_self_check(1000, {"allowed_signers": False})["void"], "F1 clean ok"
    # F1 wiring -- protected_writable_map flags group/other-writable; gather feeds it to the void
    assert protected_writable_map({"k": 0o644, "x": 0o666}) == {"k": False, "x": True}, "F1 writable-map"
    assert evaluate_self_check(1000, protected_writable_map({"x": 0o666}))["void"], "F1 wiring void"
    # F2 -- exact-set equality
    A = {"path": "/s/a", "dev": 1, "inode": 10, "size": 5, "mtime": 100}
    B = {"path": "/s/b", "dev": 1, "inode": 11, "size": 6, "mtime": 101}
    d = exact_set_decision([A, B], [A, B])
    assert d["verdict"] == "OK" and len(d["act"]) == 2, "F2 full match"
    d = exact_set_decision([A, B], [A])
    assert len(d["act"]) == 1 and len(d["skip"]) == 1, "F2 subset -> skip"
    d = exact_set_decision([A], [A, B])
    assert len(d["act"]) == 1 and len(d["extra"]) == 1, "F2 extra ignored"
    swap = {"path": "/s/a", "dev": 1, "inode": 999, "size": 5, "mtime": 100}
    d = exact_set_decision([A], [swap])
    assert d["verdict"] == "VOID" and d["swap"], "F2 swap -> VOID"
    churn = {"path": "/s/a", "dev": 1, "inode": 10, "size": 999, "mtime": 100}
    d = exact_set_decision([A], [churn])
    assert len(d["act"]) == 0 and len(d["skip"]) == 1, "F2 churn -> skip"
    # F4 / C5 / F7 -- denylist
    deny_inodes = {(1, 77)}
    assert denylist_match("/s/x.db", 1, 5, 1, ["*.db"], deny_inodes)[0], "F4 db glob"
    assert denylist_match("/s/alias", 1, 77, 1, [], deny_inodes)[0], "C5 inode alias"
    assert denylist_match("/s/hl", 1, 5, 2, [], set())[0], "F7 hardlink nlink>1"
    assert not denylist_match("/s/ok.log", 1, 5, 1, ["*.db"], set())[0], "clean allow"
    # allowlist + caps
    assert within_allowlist("/var/log/a", ["/var/log"]), "allowlist in"
    assert not within_allowlist("/etc/x", ["/var/log"]), "allowlist out"
    assert caps_ok(3, 100, {"max_files": 5, "max_bytes": 1000})[0], "caps ok"
    assert not caps_ok(9, 100, {"max_files": 5, "max_bytes": 1000})[0], "caps files"
    return True


def main():
    ap = argparse.ArgumentParser(description="infra-audit privileged executor")
    ap.add_argument("cmd", choices=["execute", "issue-nonce", "self-check"])
    ap.add_argument("--root", default=".")
    ap.add_argument("--proposal")
    args = ap.parse_args()
    manifest, mpath = load_manifest(args.root)
    if not manifest:
        print(json.dumps({"ok": False, "verdict": "REFUSE", "reason": "no audit.config.json"}))
        sys.exit(2)
    if args.cmd == "issue-nonce":
        print(json.dumps({"ok": True, "nonce": issue_nonce(_state_dir(manifest, args.root))}))
    elif args.cmd == "self-check":
        print(json.dumps(gather_self_check(manifest, mpath, _state_dir(manifest, args.root)),
                         ensure_ascii=True, indent=2))
    else:
        if not args.proposal:
            print(json.dumps({"ok": False, "reason": "execute needs --proposal"}))
            sys.exit(2)
        res = execute(args.proposal, args.root)
        print(json.dumps(res, ensure_ascii=True, indent=2))
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
            sys.stdout.write("executor self-test FAILED: %s\n" % e)
            sys.exit(1)
        sys.stdout.write("executor self-test OK (F1, F2, F4/C5/F7, allowlist, caps)\n")
        sys.exit(0)
    main()
