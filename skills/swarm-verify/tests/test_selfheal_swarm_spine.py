# -*- coding: utf-8 -*-
"""Integration: build -> verify -> retry -> quarantine spine, real CLIs, fake builder.

Faithful Python mirror of the SKILL.md `verifiedBuild` loop: the taskhash is computed
ONCE and used as BOTH the dedup key (taskhash.py) and the selfheal unit-id, so every
ledger entry for a task lands on the same key -- exactly as the real wiring does."""
import json
import os
import subprocess
import sys

SV = os.path.expanduser("~/.claude/skills/swarm-verify/scripts")
LIB = os.path.expanduser("~/.claude/skills/_lib")


def _run(argv):
    r = subprocess.run([sys.executable] + argv, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def _th(unit_id):
    """The taskhash of a task -- the shared key for taskhash + selfheal entries."""
    return _run([os.path.join(SV, "taskhash.py"), "hash",
                 "--task-json", json.dumps({"id": unit_id})])[1]


def _verify(path):
    # require a non-empty 'sources' provenance field (the anti-fabrication gate)
    rc, out = _run([os.path.join(SV, "verify_deliverable.py"), "--file", path,
                    "--provenance-field", "sources", "--json"])
    return json.loads(out)["verdict"]  # "PASS" / "FAIL"


def _fake_build(path, good):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"summary": "x", "sources": (["s1"] if good else [])}, fh)


def _report(store):
    return json.loads(_run([os.path.join(LIB, "selfheal.py"), "report", "--store", store])[1])


def _verified_build(tmp, store, unit_id, outcomes, max_attempts):
    """Mirror of verifiedBuild. `outcomes` is the per-attempt good/bad sequence the fake
    builder produces. Returns 'confirmed' | 'quarantined'."""
    task_json = json.dumps({"id": unit_id})
    th = _run([os.path.join(SV, "taskhash.py"), "hash", "--task-json", task_json])[1]
    # idempotent re-dispatch: skip already-done OR already-quarantined units
    if _run([os.path.join(SV, "taskhash.py"), "is-done",
             "--task-json", task_json, "--store", store])[0] == 0:
        return "confirmed"
    if _run([os.path.join(LIB, "selfheal.py"), "is-quarantined",
             "--store", store, "--unit-id", th])[0] == 0:
        return "quarantined"
    out = os.path.join(tmp, th + ".json")
    for i in range(1, max_attempts + 1):
        _fake_build(out, good=outcomes[min(i, len(outcomes)) - 1])
        if _verify(out) == "PASS":
            _run([os.path.join(SV, "taskhash.py"), "done",
                  "--task-json", task_json, "--store", store, "--output", out])
            return "confirmed"
        _run([os.path.join(LIB, "selfheal.py"), "attempt",
              "--store", store, "--unit-id", th, "--reason", "provenance fail"])
        cont = _run([os.path.join(LIB, "selfheal.py"), "should-continue",
                     "--policy", "attempts", "--store", store,
                     "--unit-id", th, "--max", str(max_attempts)])[0] == 0
        if not cont:
            _run([os.path.join(LIB, "selfheal.py"), "quarantine",
                  "--store", store, "--unit-id", th, "--reason", "exhausted"])
            return "quarantined"
    return "quarantined"


def test_passes_on_first_attempt_marks_done(tmp_path):
    # happy path: PASS on attempt 1 -> done, never touches selfheal (0 attempts recorded)
    store = str(tmp_path / "status.json")
    res = _verified_build(str(tmp_path), store, "u0", outcomes=[True], max_attempts=2)
    assert res == "confirmed"
    rep = _report(store)
    th = _th("u0")
    assert rep["confirmed"] == [th]
    assert rep["attempts_by_unit"].get(th, 0) == 0


def test_fail_twice_then_pass_resolves_confirmed(tmp_path):
    # attempt1 bad, attempt2 good -> PASS within budget (F2: transient fail recovers)
    store = str(tmp_path / "status.json")
    res = _verified_build(str(tmp_path), store, "u1", outcomes=[False, True], max_attempts=2)
    assert res == "confirmed"
    rep = _report(store)
    th = _th("u1")
    assert rep["confirmed"] == [th]
    assert rep["attempts_by_unit"][th] == 1  # one failed attempt before the pass


def test_always_fails_quarantines_and_reports(tmp_path):
    store = str(tmp_path / "status.json")
    res = _verified_build(str(tmp_path), store, "u2", outcomes=[False, False], max_attempts=2)
    assert res == "quarantined"
    rep = _report(store)
    th = _th("u2")
    assert rep["quarantined"] == [th]
    assert rep["attempts_by_unit"][th] == 2


def test_already_done_is_skipped_without_rebuild(tmp_path):
    # B3 idempotency: a re-dispatched already-done unit short-circuits at is-done and is
    # NOT rebuilt (the second call's builder would FAIL if it ran).
    store = str(tmp_path / "status.json")
    assert _verified_build(str(tmp_path), store, "u3", outcomes=[True], max_attempts=2) == "confirmed"
    res = _verified_build(str(tmp_path), store, "u3", outcomes=[False, False], max_attempts=2)
    assert res == "confirmed"  # cached, not rebuilt
