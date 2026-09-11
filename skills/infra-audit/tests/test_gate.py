#!/usr/bin/env python
"""
test_gate.py -- end-to-end integration test of the propose -> sign -> execute gate.

Builds a throwaway "box": a temp root with an audit.config.json, a scratch allowlist
dir of real files, and a throwaway ssh keypair + allowed_signers. Then drives the full
signed flow and the Validation-Contract failure modes. The actual quarantine MOVE is
POSIX-only; on non-POSIX the whole decision pipeline is still exercised and the action
seam reports POSIX-only (the real move is validated at Linux deploy).

Run: python test_gate.py   ->  0 all pass, 1 fail, 2 ssh-keygen absent.
"""
import json
import os
import shutil
import sys
import tempfile

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
sys.path.insert(0, SCRIPTS)
import canon  # noqa: E402
import executor  # noqa: E402
import propose  # noqa: E402
import sign  # noqa: E402

NOW = 1800000000


def _write(p, data):
    with open(p, "w", encoding="utf-8") as f:
        f.write(data)


def setup_box(d, box_id="testbox"):
    scratch = os.path.join(d, "scratch")
    os.makedirs(scratch, exist_ok=True)
    for name, content in [("a.gz", "aaaa"), ("b.gz", "bbbbbb"), ("keep.db", "DB")]:
        _write(os.path.join(scratch, name), content)
    key = os.path.join(d, "k")
    rc, out, err = sign._run(["ssh-keygen", "-t", "ed25519", "-f", key, "-N", "", "-C", "test", "-q"],
                             input_bytes=b"")
    assert rc == 0, "keygen rc=%d %s" % (rc, err)
    ident, ns = "test-signer", "infra-audit-gate"
    allowed = sign.make_allowed_signers(ident, key + ".pub", ns, os.path.join(d, "allowed_signers"))
    manifest = {
        "schema": "audit-config/v1", "box_id": box_id, "box_class": "operator", "state_dir": ".audit",
        "signing": {"allowed_signers": allowed, "namespace": ns},
        "allowlist": [scratch],
        "denylist": ["*.db", "*.key", ".env"],
        "caps": {"max_files": 500, "max_bytes": 5000000},
        "clock": {"floor_epoch": 1735689600, "ceil_epoch": 1893456000, "max_skew_seconds": 300},
        "quarantine": {"dir": ".audit/quarantine", "purge_after_days": 14},
    }
    _write(os.path.join(d, "audit.config.json"), json.dumps(manifest))
    return scratch, key, ident, ns


def authorize(record_path, key, ns, identity):
    """Operator side: sign the fingerprint, attach the signature to the record."""
    with open(record_path, "r", encoding="utf-8") as f:
        rec = json.load(f)
    sig = sign.sign_message(rec["fingerprint"].encode("ascii"), key, ns)
    rec["signature"] = sig.decode("utf-8")
    rec["identity"] = identity
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(rec, f)
    return record_path


def run():
    if not sign.have_ssh_keygen():
        print("test_gate SKIPPED: ssh-keygen absent")
        return 2
    posix = (os.name == "posix")
    d = tempfile.mkdtemp(prefix="audit_gate_")
    try:
        scratch, key, ident, ns = setup_box(d)
        a_gz = os.path.join(scratch, "a.gz")
        b_gz = os.path.join(scratch, "b.gz")
        keepdb = os.path.join(scratch, "keep.db")
        sd = os.path.join(d, ".audit")

        # --- happy path: propose -> (pending) -> authorize -> execute ---
        nonce = executor.issue_nonce(sd)
        res = propose.propose(d, "delete", nonce, "cleanup logs", [a_gz, b_gz, keepdb], ident, 3600, now=NOW)
        assert res["ok"], "propose ok: %r" % res
        assert res["rejected"] == 1, "keep.db screened at propose (denylist *.db): %r" % res
        assert res["proposable"] == 2, "two proposable: %r" % res
        rec_path = res["proposal"]

        r = executor.execute(rec_path, d, now=NOW)
        assert r["verdict"] == "PENDING", "no signature -> PENDING: %r" % r

        authorize(rec_path, key, ns, ident)
        r = executor.execute(rec_path, d, now=NOW)
        assert r["ok"] and r["verdict"] == "EXECUTED", "executed: %r" % r
        if posix:
            assert r["actual_items"] == 2, "two quarantined: %r" % r
            assert not os.path.exists(a_gz) and not os.path.exists(b_gz), "files moved"
            assert os.path.exists(keepdb), "denylisted db untouched"
        else:
            assert r["actual_items"] == 0 and len(r["failed"]) == 2, "action seam POSIX-only: %r" % r

        # --- F3 replay: same proposal again -> VOID (ledger consume-once) ---
        r2 = executor.execute(rec_path, d, now=NOW)
        blob = (r2.get("reason", "") + json.dumps(r2.get("ledger", {}))).lower()
        assert not r2["ok"] and "replay" in blob, "F3 replay -> VOID: %r" % r2

        # --- tamper: flip box_id after fingerprint -> VOID (fingerprint mismatch) ---
        n2 = executor.issue_nonce(sd)
        res2 = propose.propose(d, "delete", n2, "x", [], ident, 3600, now=NOW)
        with open(res2["proposal"], "r", encoding="utf-8") as f:
            j = json.load(f)
        j["payload"]["box_id"] = "OTHERBOX"
        with open(res2["proposal"], "w", encoding="utf-8") as f:
            json.dump(j, f)
        authorize(res2["proposal"], key, ns, ident)
        r3 = executor.execute(res2["proposal"], d, now=NOW)
        assert not r3["ok"] and r3["verdict"] == "VOID", "tamper -> VOID: %r" % r3

        # --- expired: not_after in the past (good clock) -> VOID ---
        n3 = executor.issue_nonce(sd)
        res3 = propose.propose(d, "delete", n3, "x", [], ident, -10, now=NOW)
        authorize(res3["proposal"], key, ns, ident)
        r4 = executor.execute(res3["proposal"], d, now=NOW)
        assert not r4["ok"] and "expired" in r4.get("reason", "").lower(), "expired -> VOID: %r" % r4

        # --- not executor-issued: forged nonce -> VOID (C9) ---
        res5 = propose.propose(d, "delete", "nonce-forged-deadbeef", "x", [], ident, 3600, now=NOW)
        authorize(res5["proposal"], key, ns, ident)
        r5 = executor.execute(res5["proposal"], d, now=NOW)
        assert not r5["ok"] and "issued" in r5.get("reason", "").lower(), "not-issued -> VOID: %r" % r5

        # --- wrong signer key: a different key's signature -> VOID ---
        n6 = executor.issue_nonce(sd)
        res6 = propose.propose(d, "delete", n6, "x", [], ident, 3600, now=NOW)
        other = os.path.join(d, "other")
        sign._run(["ssh-keygen", "-t", "ed25519", "-f", other, "-N", "", "-C", "evil", "-q"], input_bytes=b"")
        with open(res6["proposal"], "r", encoding="utf-8") as f:
            j6 = json.load(f)
        sig = sign.sign_message(j6["fingerprint"].encode("ascii"), other, ns)
        j6["signature"] = sig.decode("utf-8")
        j6["identity"] = ident
        with open(res6["proposal"], "w", encoding="utf-8") as f:
            json.dump(j6, f)
        r6 = executor.execute(res6["proposal"], d, now=NOW)
        assert not r6["ok"] and r6["verdict"] == "VOID", "wrong-key signature -> VOID: %r" % r6

    finally:
        try:
            shutil.rmtree(d)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        rc = run()
    except AssertionError as e:
        print("test_gate FAILED: %s" % e)
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("test_gate ERROR: %s" % e)
        sys.exit(1)
    if rc == 2:
        sys.exit(2)
    print("test_gate OK: propose->sign->execute; replay/tamper/expired/not-issued/wrong-key all VOID")
    sys.exit(0)
