# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/_lib"))
import selfheal  # noqa: E402

SELFHEAL = os.path.expanduser("~/.claude/skills/_lib/selfheal.py")


def _store(tmp_path):
    return str(tmp_path / "status.json")


def test_attempt_increments_from_zero(tmp_path):
    s = _store(tmp_path)
    selfheal.cmd_attempt_api(s, "u1", reason="first fail")
    selfheal.cmd_attempt_api(s, "u1", reason="second fail")
    store = selfheal.load_store(s)
    assert store["tasks"]["u1"]["attempts"] == 2
    assert store["tasks"]["u1"]["last_reason"] == "second fail"


def test_attempt_truncates_oversized_reason(tmp_path):
    s = _store(tmp_path)
    big = "x" * (selfheal.REASON_MAX + 50)
    selfheal.cmd_attempt_api(s, "u1", reason=big)
    rec = selfheal.load_store(s)["tasks"]["u1"]["last_reason"]
    assert len(rec) <= selfheal.REASON_MAX + len("...[truncated]")
    assert rec.endswith("...[truncated]")


def test_quarantine_sets_status_and_keeps_attempts(tmp_path):
    s = _store(tmp_path)
    selfheal.cmd_attempt_api(s, "u1")
    selfheal.cmd_quarantine_api(s, "u1", reason="never passed")
    e = selfheal.load_store(s)["tasks"]["u1"]
    assert e["status"] == "quarantined"
    assert e["attempts"] == 1
    assert e["last_reason"] == "never passed"


def test_is_quarantined_exit_codes(tmp_path):
    s = _store(tmp_path)
    assert selfheal.is_quarantined_api(s, "missing") is False
    selfheal.cmd_quarantine_api(s, "u1")
    assert selfheal.is_quarantined_api(s, "u1") is True


def test_report_aggregates_confirmed_and_quarantined(tmp_path):
    s = _store(tmp_path)
    # simulate a done unit the way taskhash would record it
    store = selfheal.load_store(s)
    store["tasks"]["done1"] = {"status": "done", "attempts": 1,
                               "output_path": "results/done1.json"}
    selfheal.save_store(s, store)
    selfheal.cmd_attempt_api(s, "q1")
    selfheal.cmd_quarantine_api(s, "q1", reason="exhausted")
    rep = selfheal.report_api(s)
    assert rep["confirmed"] == ["done1"]
    assert rep["quarantined"] == ["q1"]
    assert rep["attempts_by_unit"] == {"done1": 1, "q1": 1}


def test_should_continue_attempts_boundary(tmp_path):
    s = _store(tmp_path)
    # 0 attempts, max 2 -> continue
    r = selfheal.should_continue_attempts(s, "u1", 2)
    assert r["ok"] is True and r["attempts"] == 0
    # 1 attempt, max 2 -> continue
    selfheal.cmd_attempt_api(s, "u1")
    assert selfheal.should_continue_attempts(s, "u1", 2)["ok"] is True
    # 2 attempts, max 2 -> halt (attempts < max is False)
    selfheal.cmd_attempt_api(s, "u1")
    r2 = selfheal.should_continue_attempts(s, "u1", 2)
    assert r2["ok"] is False and r2["halt"] is True


def test_fail_open_on_corrupt_ledger(tmp_path):
    s = _store(tmp_path)
    with open(s, "w", encoding="utf-8") as fh:
        fh.write("{ this is not valid json")
    # load_store must treat corruption as empty, never raise
    assert selfheal.load_store(s) == {"schema": selfheal.STORE_SCHEMA, "tasks": {}}
    # and a decision on an unknown unit treats it as 0 attempts (continue)
    assert selfheal.should_continue_attempts(s, "u1", 2)["ok"] is True


def test_attempt_preserves_taskhash_fields(tmp_path):
    s = _store(tmp_path)
    # taskhash.py would have written this entry first
    store = {"schema": selfheal.STORE_SCHEMA,
             "tasks": {"u1": {"status": "claimed", "output_path": "results/u1.json",
                              "spec_version": "v3", "label": "build:u1"}}}
    selfheal.save_store(s, store)
    selfheal.cmd_attempt_api(s, "u1", reason="verify failed")
    e = selfheal.load_store(s)["tasks"]["u1"]
    # selfheal added attempts + last_reason WITHOUT dropping taskhash's fields
    assert e["attempts"] == 1
    assert e["last_reason"] == "verify failed"
    assert e["status"] == "claimed"
    assert e["output_path"] == "results/u1.json"
    assert e["spec_version"] == "v3"
    assert e["label"] == "build:u1"


def test_stall_cli_missing_history_exits_2_no_traceback(tmp_path):
    # A bad --history must NOT crash and must NOT masquerade as halt (exit 1):
    # it exits 2 (bad input) with an error JSON.
    r = subprocess.run([sys.executable, SELFHEAL, "should-continue", "--policy", "stall",
                        "--history", str(tmp_path / "nope.json"), "--k", "2"],
                       capture_output=True, text=True)
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "Traceback" not in r.stderr
    assert json.loads(r.stdout)["ok"] is False


def test_stall_cli_malformed_history_exits_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not a list", encoding="utf-8")
    r = subprocess.run([sys.executable, SELFHEAL, "should-continue", "--policy", "stall",
                        "--history", str(bad), "--k", "2"],
                       capture_output=True, text=True)
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "Traceback" not in r.stderr
