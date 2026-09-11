#!/usr/bin/env python
"""
test_findings.py -- regression tests for the fresh-review findings.

Each test encodes the reviewer's live reproduction. Run BEFORE the fix to witness the
bug (the test fails), and AFTER the fix to confirm it is closed (the test passes).
No vacuous assertions (L023): each drives the real public API on real temp state.

  finding 1 (CRITICAL): a no-op (all signed items missing/churned/denied) must NOT
                        consume/burn the signed nonce -- re-presenting is not 'replay'.
  finding 2 (CRITICAL): concurrent consume() of one nonce must yield exactly ONE winner
                        and leave the hash chain intact (no double-spend, no corruption).

Run: python test_findings.py  -> 0 all pass, 1 any fail/error.
"""
import os
import shutil
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
import executor  # noqa: E402
import ledger  # noqa: E402
import propose  # noqa: E402
import sign  # noqa: E402
import test_gate  # reuse setup_box / authorize  # noqa: E402

NOW = 1800000000


def finding1_noop_preserves_nonce():
    """Propose a file, delete it before execute (-> exact-set skip -> empty final ->
    no-op). The nonce must survive: a second execute of the same signed proposal must
    NOT be rejected as replay."""
    if not sign.have_ssh_keygen():
        return "SKIP (no ssh-keygen)"
    d = tempfile.mkdtemp(prefix="audit_f1_")
    try:
        scratch, key, ident, ns = test_gate.setup_box(d)
        f = os.path.join(scratch, "a.gz")
        sd = os.path.join(d, ".audit")
        nonce = executor.issue_nonce(sd)
        res = propose.propose(d, "delete", nonce, "cleanup", [f], ident, 3600, now=NOW)
        os.remove(f)  # file gone at execute time -> nothing to act on
        test_gate.authorize(res["proposal"], key, ns, ident)
        r1 = executor.execute(res["proposal"], d, now=NOW)
        r2 = executor.execute(res["proposal"], d, now=NOW)
        replayed = (r2.get("verdict") == "VOID" and "replay" in r2.get("reason", "").lower())
        assert not replayed, "no-op burned the nonce (finding 1): r1=%s r2=%r" % (r1.get("verdict"), r2)
        return "PASS"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def finding2_concurrent_single_winner():
    """8 threads consume the SAME nonce concurrently -> exactly one wins, chain intact."""
    d = tempfile.mkdtemp(prefix="audit_f2_")
    try:
        p = os.path.join(d, "ledger.jsonl")
        oks, lk = [], threading.Lock()

        def w():
            r = ledger.consume(p, "SAME", NOW)
            with lk:
                oks.append(bool(r.get("ok")))

        ts = [threading.Thread(target=w) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        wins = sum(1 for x in oks if x)
        chain = ledger.verify_chain(p)
        assert wins == 1, "double-spend (finding 2): %d winners of one nonce" % wins
        assert chain["ok"], "chain corrupted by concurrency (finding 2): %s" % chain.get("reason")
        return "PASS"
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    fails = 0
    for name, fn in [("finding1_noop_preserves_nonce", finding1_noop_preserves_nonce),
                     ("finding2_concurrent_single_winner", finding2_concurrent_single_winner)]:
        try:
            r = fn()
            print("%-36s %s" % (name, r))
        except AssertionError as e:
            print("%-36s FAIL: %s" % (name, e))
            fails += 1
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("%-36s ERROR: %s" % (name, e))
            fails += 1
    print("--- %d failure(s) ---" % fails)
    sys.exit(1 if fails else 0)
