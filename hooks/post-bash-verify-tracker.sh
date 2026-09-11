#!/usr/bin/env bash
# PostToolUse hook (Bash|PowerShell): Track verification commands (pytest,
# tsc, eslint) and release the L030 git-mutation lock taken by pre_bash_guard.
# Feeds data to stop-verify-reminder.sh so it knows if verification ran.
# 2026-08-15: matcher widened to include PowerShell (pytest runs via the
# PowerShell tool now count as verification; git lock covers both shells).
# 2026-07-08 tightened: (1) COMMAND-POSITION matching per segment — a mention of
# pytest/typescript inside echo/printf text, grep patterns, git commit messages,
# or pip installs no longer counts as verification (pytest:True got set this way).
# (2) Flags are now TIMESTAMPS, not booleans — stop-verify compares them against
# each file's last_edit, so an old pytest run no longer vouches for newer edits.
set -euo pipefail

INPUT=$(cat)

echo "$INPUT" | python -c "
import sys, json, os, re, time

try:
    data = json.load(sys.stdin)
    session_id = data.get('session_id', 'unknown')

    # Release the L030 git-mutation lock taken by pre_bash_guard.py -
    # MUST happen before any early exit below. Ownership-scoped (2026-09-01):
    # the lock's 2nd line is the tool_use_id that took it; only that call
    # (or a legacy lock with no owner) may release it, so a parallel call
    # that was hook-BLOCKED cannot free a lock a running call still holds.
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

    inp = data.get('tool_input', {})
    cmd = inp.get('command', '')
    if not cmd:
        sys.exit(0)

    # Segments = naive split on separators. Quotes are NOT parsed; the excluded-leader
    # check below is what keeps quoted text (echo/git commit/grep args) from matching.
    segs = [s.strip() for s in re.split(r'(?:\|\||&&|[;|\n])', cmd) if s.strip()]

    # If a segment's first real token is one of these, nothing inside it counts —
    # they QUOTE or SEARCH text rather than run a verifier.
    excluded = {'echo', 'printf', 'grep', 'rg', 'cat', 'head', 'tail', 'sed', 'awk',
                'git', 'pip', 'pip3', 'winget', 'apt', 'apt-get', 'brew', 'choco',
                'which', 'type', 'find', 'ls'}

    def leader(seg):
        toks = seg.split()
        i = 0
        while i < len(toks) and (re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', toks[i])
                                 or toks[i] in ('sudo', 'env', 'nice', 'time')):
            i += 1
        return os.path.basename(toks[i]).lower() if i < len(toks) else ''

    hits = {}
    now = time.time()
    for seg in segs:
        if leader(seg) in excluded:
            continue
        pad = ' ' + seg + ' '
        if re.search(r'[\s/=]pytest(?:\.exe)?\s', pad) or re.search(r'python3?(?:\.exe)?\s+-m\s+pytest\b', seg):
            hits['pytest'] = now
        if re.search(r'[\s/=]tsc(?:\.cmd|\.exe)?\s', pad):
            hits['tsc'] = now
        if re.search(r'[\s/=]eslint(?:\.cmd)?\s', pad):
            hits['eslint'] = now
        if re.search(r'\b(?:npm|yarn|pnpm|bun)\s+(?:run\s+)?test\b', seg) or re.search(r'[\s/=]vitest(?:\.cmd)?\s', pad):
            hits['test_runner'] = now

    if not hits:
        sys.exit(0)

    tracker_dir = os.path.join(os.path.expanduser('~'), '.claude', 'session-state')
    os.makedirs(tracker_dir, exist_ok=True)
    tracker_file = os.path.join(tracker_dir, session_id + '.json')

    state = {}
    if os.path.exists(tracker_file):
        with open(tracker_file, 'r') as f:
            state = json.load(f)

    verification_ran = state.setdefault('verification_ran', {})
    verification_ran.update(hits)
    state['verification_ran'] = verification_ran

    tmp = tracker_file + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f)
    os.replace(tmp, tracker_file)  # atomic (L030)

except Exception:
    pass
" 2>/dev/null

exit 0
