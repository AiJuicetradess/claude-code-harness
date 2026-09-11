# -*- coding: utf-8 -*-
"""green_guard.progress output SHAPE must be unchanged after it delegates to selfheal.
Frozen expected outputs captured from the pre-shim implementation."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/tdd-pipeline/scripts"))
import green_guard  # noqa: E402

# (history, k) -> exact expected dict from the ORIGINAL cmd_progress
FROZEN = [
    (([5, 5, 5], 2), {"ok": False, "check": "progress", "halt": True,
                      "window": [5, 5, 5], "reason": "no shrink in last 2 rounds"}),
    (([5, 4, 3], 2), {"ok": True, "check": "progress", "halt": False,
                      "window": [5, 4, 3], "reason": "progressing"}),
    (([5], 2), {"ok": True, "check": "progress", "halt": False, "reason": "warming up"}),
]


def test_progress_output_shape_frozen():
    for (history, k), expected in FROZEN:
        assert green_guard.cmd_progress(history, k) == expected
