# -*- coding: utf-8 -*-
"""Golden test: selfheal `stall` policy must make the SAME continue/halt decision
as the CURRENT green_guard.progress, across a battery of histories. This is the
gate that must be green BEFORE green_guard is touched in Phase 3."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/_lib"))
sys.path.insert(0, os.path.expanduser("~/.claude/skills/tdd-pipeline/scripts"))
import selfheal       # noqa: E402
import green_guard    # noqa: E402

HISTORIES = [
    [], [5], [5, 4], [5, 5], [5, 4, 4], [4, 4, 4], [3, 3, 3, 3],
    [5, 4, 3, 2, 1], [5, 5, 5, 4], [9, 9, 8, 8, 8], [1, 0],
    [7, 7, 7, 6, 6, 6, 6], [2, 2, 1, 1], [0], [0, 0, 0],
]
KS = [1, 2, 3]


def test_stall_matches_green_guard_progress():
    # Assert the FULL decision shape, not just ok/halt -- this test is the gate
    # before green_guard.cmd_progress becomes a selfheal shim in Phase 3, so it
    # must catch any divergence in window/reason too. The only key that differs
    # by design is the label ("policy":"stall" here vs "check":"progress" there).
    for h in HISTORIES:
        for k in KS:
            gg = green_guard.cmd_progress(h, k)
            sh = selfheal.should_continue_stall(h, k)
            assert sh["ok"] == gg["ok"], (h, k, "ok", sh, gg)
            assert sh["halt"] == gg["halt"], (h, k, "halt", sh, gg)
            assert sh["reason"] == gg["reason"], (h, k, "reason", sh, gg)
            assert sh.get("window") == gg.get("window"), (h, k, "window", sh, gg)
