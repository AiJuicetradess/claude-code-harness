#!/usr/bin/env bash
# Stop hook: Check if verification was run before completion claims.
# Enforces: Forced Verification (P8), No "should work" (G28), re-read after edit (L021).
# Emits {"decision":"block","reason":...} — the schema Claude Code actually honors for
# Stop hooks (a bare stopReason without continue:false is silently dropped).
# stop_hook_active guard ensures at most ONE forced continuation per stop chain.
# 2026-07-08 patch: (1) PROJECT-SCOPED — files under the OS temp dir (scratchpad
# probes) or outside the session cwd (memory, hooks) are ignored; extensions are
# derived from the filtered set, not the stored cumulative list. (2) LATCHED —
# warns ONCE per state snapshot; re-warns only after NEW edits change the snapshot.
# Pre-patch it re-fired on every stop for the whole session over throwaway files.
set -euo pipefail

INPUT=$(cat)

RESULT=$(echo "$INPUT" | python -c "
import sys, json, os, hashlib, tempfile

try:
    data = json.load(sys.stdin)
    session_id = data.get('session_id', 'unknown')

    # Never re-block a stop that is already the result of a Stop-hook block —
    # prevents infinite continue loops.
    if data.get('stop_hook_active'):
        sys.exit(0)

    tracker_dir = os.path.join(os.path.expanduser('~'), '.claude', 'session-state')
    tracker_file = os.path.join(tracker_dir, session_id + '.json')

    if not os.path.exists(tracker_file):
        sys.exit(0)

    with open(tracker_file, 'r') as f:
        state = json.load(f)

    # Scope to project files: ignore temp/scratchpad and anything outside the cwd.
    cwd = data.get('cwd') or ''
    ncwd = os.path.normcase(os.path.normpath(cwd)) if cwd else ''
    tmpdir = os.path.normcase(os.path.normpath(tempfile.gettempdir()))
    def in_scope(fp):
        p = os.path.normcase(os.path.normpath(fp))
        if p.startswith(tmpdir + os.sep):
            return False
        if ncwd:
            return p == ncwd or p.startswith(ncwd + os.sep)
        return True

    edited_files = {fp: info for fp, info in state.get('edited_files', {}).items()
                    if in_scope(fp)}
    if not edited_files:
        sys.exit(0)

    verification_ran = state.get('verification_ran', {})

    # Staleness model (2026-07-08): verifier flags are timestamps; a run only vouches
    # for edits made BEFORE it. Legacy booleans (from the loose matcher) count as never.
    def latest_edit(exts):
        ts = [info.get('last_edit', 0) for fp, info in edited_files.items()
              if os.path.splitext(fp)[1].lower() in exts]
        return max(ts) if ts else 0

    def verified_at(*flags):
        vals = []
        for fl in flags:
            v = verification_ran.get(fl)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                vals.append(v)
        return max(vals) if vals else 0

    reminders = []

    # Check: TypeScript/JavaScript files edited after the last tsc/eslint run
    ts_edit = latest_edit({'.ts', '.tsx', '.js', '.jsx'})
    if ts_edit and ts_edit > verified_at('tsc', 'eslint'):
        reminders.append('TypeScript/JS files were edited but tsc --noEmit / eslint were not run.')

    # Check: Python files edited after the last pytest run
    py_edit = latest_edit({'.py'})
    if py_edit and py_edit > verified_at('pytest'):
        reminders.append('Python files were edited but pytest was not run.')

    # Check: Any code files edited but modified files not re-read
    reads = state.get('reads', {})
    unverified = []
    for fp, info in edited_files.items():
        last_edit = info.get('last_edit', 0)
        last_read = reads.get(fp, 0)
        if last_read < last_edit:
            unverified.append(os.path.basename(fp))

    if unverified and len(unverified) <= 10:
        names = ', '.join(unverified[:5])
        reminders.append(f'Modified files not re-read after editing: {names}')

    if reminders:
        # Latch: block ONCE per snapshot of (in-scope edits, verification, reminders).
        # A new edit changes the snapshot and re-arms the warning.
        snap_src = json.dumps({
            'edits': {fp: info.get('last_edit', 0) for fp, info in edited_files.items()},
            'verif': verification_ran,
            'reminders': reminders,
        }, sort_keys=True)
        snapshot = hashlib.sha1(snap_src.encode('utf-8')).hexdigest()
        if state.get('last_block_snapshot') == snapshot:
            sys.exit(0)
        state['last_block_snapshot'] = snapshot
        tmp = tracker_file + '.tmp'
        with open(tmp, 'w') as f2:
            json.dump(state, f2)
        os.replace(tmp, tracker_file)  # atomic (L030)

        ctx = 'VERIFICATION REMINDER: ' + ' | '.join(reminders) + ' Run verification (or re-read the modified files) before claiming done. If verification is genuinely not applicable here, state why and stop.'
        print(json.dumps({
            'decision': 'block',
            'reason': ctx
        }))

except Exception:
    pass
" 2>/dev/null)

if [ -n "$RESULT" ]; then
    echo "$RESULT"
fi

exit 0
