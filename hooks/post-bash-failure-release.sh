#!/usr/bin/env bash
# PostToolUseFailure hook (Bash|PowerShell): release the L030 git-mutation lock
# taken by pre_bash_guard.py when the tool call FAILED.
#
# Why this exists (2026-09-01): PostToolUse fires only on successful tool calls
# (docs: PostToolUse = "after a tool call succeeds", PostToolUseFailure = "after
# a tool call fails"), so post-bash-verify-tracker.sh never ran after a git
# command that exited non-zero. The lock then sat until its 15s TTL and blocked
# the very retry the failure called for (observed 2026-08-31:
# failed checkout -> two blocked commits -> PowerShell sleep -> 4 round-trips).
# Reproduced live 2026-09-01 18:44: failed `git commit` -> `git add` 5s later
# BLOCKED; the same pair with a successful commit -> not blocked.
#
# Ownership-scoped: the lock's 2nd line is the tool_use_id that took it. The
# docs do not say whether this event also fires for pre-hook-BLOCKED calls; if
# it does, a blocked parallel git call must NOT free the lock a running call
# still holds. A legacy lock with no owner line is released unconditionally.
#
# Deliberately does ONLY the release: a failed pytest/tsc run must NOT be
# recorded as "verification ran" (stop-verify would then vouch for edits the
# failing suite did not).
# Fail-open by design.
set -uo pipefail

INPUT=$(cat)

echo "$INPUT" | python -c "
import sys, json, os
try:
    data = json.load(sys.stdin)
    session_id = data.get('session_id', 'unknown')
    tool_use_id = data.get('tool_use_id', '')
    lock = os.path.join(os.path.expanduser('~'), '.claude',
                        'session-state', session_id + '.gitlock')
    try:
        with open(lock) as lf:
            parts = lf.read().split('\n')
        owner = parts[1].strip() if len(parts) > 1 else ''
        if not owner or owner == tool_use_id:
            os.remove(lock)
    except OSError:
        pass
except Exception:
    pass
" 2>/dev/null

exit 0
