#!/usr/bin/env bash
# PostToolUse hook (Read): Track which files have been Read in this session.
# Enables pre-edit-guardian.sh to enforce "read before edit" rule.
set -euo pipefail

INPUT=$(cat)

python -c "
import sys, json, os, time

try:
    data = json.load(sys.stdin)
    session_id = data.get('session_id', 'unknown')
    inp = data.get('tool_input', {})
    # Claude Code Read sends file_path; Grok Build's Read sends target_file
    # (harness gap found on the 2026-09-03 SDD build - every grok edit was
    # blocked because reads were never recorded). Accept both.
    file_path = inp.get('file_path') or inp.get('target_file') or inp.get('notebook_path') or ''
    if not file_path:
        sys.exit(0)

    # Normalize path for consistent tracking
    file_path = os.path.normpath(file_path)

    tracker_dir = os.path.join(os.path.expanduser('~'), '.claude', 'session-state')
    os.makedirs(tracker_dir, exist_ok=True)
    tracker_file = os.path.join(tracker_dir, f'{session_id}.json')

    # Load existing tracker
    state = {}
    if os.path.exists(tracker_file):
        with open(tracker_file, 'r') as f:
            state = json.load(f)

    # Record this Read under both the given form and the absolute form so a
    # relative Read still vouches for an absolute-path Edit (and vice versa).
    reads = state.setdefault('reads', {})
    now = time.time()
    for key in {file_path, os.path.normpath(os.path.abspath(file_path))}:
        reads[key] = now

    # Write tracker
    with open(tracker_file, 'w') as f:
        json.dump(state, f)

except Exception:
    pass
" <<< "$INPUT" 2>/dev/null

exit 0
