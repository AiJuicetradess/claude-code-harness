#!/usr/bin/env python
"""
ledger.py -- append-only, hash-chained, consume-once nonce ledger.

The clock-INDEPENDENT replay defense for the gate: a proposal_id may be consumed
exactly once, ever. A second presentation is rejected regardless of the system
clock, so a rewound clock cannot revive a token. The chain is tamper-evident --
truncation or rewrite breaks it and the ledger fails CLOSED.

Two failure modes are distinguished (so the digest can tell them apart):
  - integrity failure (tamper / rewrite / truncation) -> ok=False, integrity=True
  - cannot append (e.g., disk full)                    -> ok=False, degraded=True

stdlib only; ASCII output; Windows-safe. Exit (direct): 0 self-test OK, 1 failed.
"""
import contextlib
import hashlib
import json
import os
import sys
import time

GENESIS = "infra-audit-ledger/v1-genesis"


def _entry_hash(prev_hash, seq, proposal_id, ts):
    msg = "%s|%d|%s|%d" % (prev_hash, seq, proposal_id, ts)
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


def _read(ledger_path):
    entries = []
    if not os.path.isfile(ledger_path):
        return entries
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def verify_chain(ledger_path):
    """Recompute the hash chain; detect truncation / rewrite / seq gap."""
    try:
        entries = _read(ledger_path)
    except Exception as e:
        return {"ok": False, "reason": "ledger read/parse error: %s" % e, "length": 0}
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("seq") != i:
            return {"ok": False, "reason": "seq gap/rewrite at %d" % i, "length": len(entries)}
        if e.get("prev_hash") != prev:
            return {"ok": False, "reason": "chain break at %d" % i, "length": len(entries)}
        expect = _entry_hash(prev, i, e.get("proposal_id", ""), e.get("ts", 0))
        if e.get("entry_hash") != expect:
            return {"ok": False, "reason": "entry hash mismatch at %d (tamper)" % i, "length": len(entries)}
        prev = e["entry_hash"]
    return {"ok": True, "reason": "chain intact", "length": len(entries), "head": prev}


def has(ledger_path, proposal_id):
    try:
        return any(e.get("proposal_id") == proposal_id for e in _read(ledger_path))
    except Exception:
        return False


@contextlib.contextmanager
def _ledger_lock(ledger_path, timeout=10.0):
    """Exclusive lock around a consume so concurrent / overlapping runs cannot double-spend
    a nonce or corrupt the chain (review finding 2). POSIX uses fcntl.flock (auto-released
    on process death); elsewhere an O_CREAT|O_EXCL lockfile with a bounded wait."""
    d = os.path.dirname(ledger_path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    lockpath = ledger_path + ".lock"
    if os.name == "posix":
        import fcntl
        fd = os.open(lockpath, os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
    else:
        start = time.time()
        fd = None
        while True:
            try:
                fd = os.open(lockpath, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.time() - start > timeout:
                    raise TimeoutError("ledger lock timeout")
                time.sleep(0.01)
        try:
            yield
        finally:
            try:
                os.close(fd)
            finally:
                try:
                    os.remove(lockpath)
                except OSError:
                    pass


def consume(ledger_path, proposal_id, ts):
    """Consume a proposal_id exactly once, ATOMICALLY (exclusive lock). Fail CLOSED on
    integrity failure; flag DEGRADED (distinct) if the lock or the append fails."""
    try:
        with _ledger_lock(ledger_path):
            chk = verify_chain(ledger_path)
            if not chk["ok"]:
                return {"ok": False, "reason": chk["reason"], "integrity": True}
            entries = _read(ledger_path)
            if any(e.get("proposal_id") == proposal_id for e in entries):
                return {"ok": False, "reason": "replay: proposal_id already consumed", "replay": True}
            seq = len(entries)
            prev = entries[-1]["entry_hash"] if entries else GENESIS
            eh = _entry_hash(prev, seq, proposal_id, ts)
            rec = {"seq": seq, "proposal_id": proposal_id, "ts": ts, "prev_hash": prev, "entry_hash": eh}
            with open(ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
            return {"ok": True, "seq": seq, "entry_hash": eh}
    except TimeoutError as e:
        return {"ok": False, "reason": "ledger lock timeout: %s" % e, "degraded": True}
    except Exception as e:
        return {"ok": False, "reason": "ledger degraded: %s" % e, "degraded": True}


def self_test():
    import tempfile
    import threading
    base = tempfile.gettempdir()
    p = os.path.join(base, "infra_audit_ledger_selftest.jsonl")
    p2 = os.path.join(base, "infra_audit_ledger_conc_same.jsonl")
    p3 = os.path.join(base, "infra_audit_ledger_conc_distinct.jsonl")

    def _clean(x):
        for sfx in ("", ".lock"):
            if os.path.isfile(x + sfx):
                os.remove(x + sfx)

    _clean(p); _clean(p2); _clean(p3)
    try:
        # consume A -> ok ; A again -> replay (F3) ; B -> ok
        assert consume(p, "A", 1800000000)["ok"] is True, "consume A"
        r = consume(p, "A", 1800000001)
        assert r["ok"] is False and r.get("replay"), "F3 replay rejected"
        assert consume(p, "B", 1800000002)["ok"] is True, "consume B"
        assert verify_chain(p)["ok"] is True, "chain intact"
        assert has(p, "A") and has(p, "B") and not has(p, "C"), "has()"
        # tamper: rewrite line 0 -> integrity failure, consume fails closed
        lines = open(p, "r", encoding="utf-8").read().splitlines()
        bad = json.loads(lines[0]); bad["proposal_id"] = "X"
        lines[0] = json.dumps(bad)
        open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        assert verify_chain(p)["ok"] is False, "tamper detected"
        r = consume(p, "D", 1800000003)
        assert r["ok"] is False and r.get("integrity"), "fail closed on tamper"
        # concurrency (finding 2): 8 threads, SAME id -> exactly one winner, chain intact
        oks, lk = [], threading.Lock()

        def w_same():
            ok = consume(p2, "SAME", 1800000000).get("ok")
            with lk:
                oks.append(bool(ok))

        ts = [threading.Thread(target=w_same) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert sum(1 for x in oks if x) == 1, "concurrency same-id: exactly one winner"
        assert verify_chain(p2)["ok"] is True, "concurrency same-id: chain intact"
        # concurrency: 8 threads, DISTINCT ids -> all win, chain length 8
        oks2 = []

        def w_distinct(i):
            ok = consume(p3, "id-%d" % i, 1800000000).get("ok")
            with lk:
                oks2.append(bool(ok))

        ts = [threading.Thread(target=w_distinct, args=(i,)) for i in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert all(oks2) and len(oks2) == 8, "concurrency distinct: all win"
        c = verify_chain(p3)
        assert c["ok"] and c["length"] == 8, "concurrency distinct: chain length 8"
    finally:
        _clean(p); _clean(p2); _clean(p3)
    return True


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        self_test()
    except AssertionError as e:
        sys.stdout.write("ledger self-test FAILED: %s\n" % e)
        sys.exit(1)
    sys.stdout.write("ledger self-test OK\n")
    sys.exit(0)
