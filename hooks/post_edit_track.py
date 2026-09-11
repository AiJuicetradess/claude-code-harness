"""PostToolUse tracker for Edit|NotebookEdit|Write.

Merges post-edit-tracker + post-edit-pytest into ONE interpreter spawn.
Optional auto-pytest: set CLAUDE_AUTO_PYTEST_ROOT to a directory and any
.py edit under it runs the nearest tests/ suite (proper JSON parse, normcase
prefix compare, bounded pytest (45s), only FAILURES are surfaced).
Fail-open: never blocks; tracker state written atomically (L030).
"""
import json
import os
import subprocess
import sys
import tempfile
import time

AUTO_PYTEST_ROOT = os.environ.get('CLAUDE_AUTO_PYTEST_ROOT', '')


def run_auto_pytest(file_path):
    """If file is a .py under AUTO_PYTEST_ROOT, walk up to a project with tests/
    and run pytest. Returns a message only on failure/timeout."""
    if not file_path.lower().endswith('.py'):
        return None
    if not AUTO_PYTEST_ROOT:
        return None
    sb = os.path.normcase(os.path.normpath(AUTO_PYTEST_ROOT))
    if not os.path.normcase(file_path).startswith(sb + os.sep):
        return None
    d = os.path.dirname(file_path)
    while os.path.normcase(d) != sb:
        if os.path.isdir(os.path.join(d, 'tests')):
            try:
                r = subprocess.run(
                    [sys.executable, '-m', 'pytest', 'tests/', '-x', '-q'],
                    cwd=d, capture_output=True, text=True, timeout=45)
                if r.returncode != 0:
                    out = ((r.stdout or '') + '\n' + (r.stderr or '')).strip()
                    tail = '\n'.join(out.splitlines()[-10:])
                    return 'auto-pytest FAILED in %s:\n%s' % (d, tail)
            except subprocess.TimeoutExpired:
                return 'auto-pytest timed out (45s) in %s' % d
            except Exception:
                pass
            return None
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def in_scope(file_path, cwd):
    """Track only PROJECT files: under the session cwd, never under the OS temp dir.
    Scratchpad probes and out-of-project files (memory, hooks) don't need pytest or
    re-read enforcement — tracking them made stop-verify-reminder fire on every stop
    for the rest of the session (2026-07-08)."""
    p = os.path.normcase(os.path.normpath(file_path))
    tmpdir = os.path.normcase(os.path.normpath(tempfile.gettempdir()))
    if p.startswith(tmpdir + os.sep):
        return False
    if cwd:
        c = os.path.normcase(os.path.normpath(cwd))
        return p == c or p.startswith(c + os.sep)
    return True


def main():
    data = json.load(sys.stdin)
    session_id = data.get('session_id', 'unknown')
    tool_name = data.get('tool_name', '')
    inp = data.get('tool_input', {}) or {}
    file_path = inp.get('file_path') or inp.get('notebook_path') or ''
    if not file_path:
        return
    file_path = os.path.normpath(file_path)

    messages = []
    if in_scope(file_path, data.get('cwd') or ''):
        tracker_dir = os.path.join(os.path.expanduser('~'), '.claude', 'session-state')
        os.makedirs(tracker_dir, exist_ok=True)
        tracker_file = os.path.join(tracker_dir, session_id + '.json')

        state = {}
        if os.path.exists(tracker_file):
            with open(tracker_file, 'r') as f:
                state = json.load(f)

        edited_files = state.setdefault('edited_files', {})
        if file_path not in edited_files:
            edited_files[file_path] = {'first_edit': time.time(), 'tool': tool_name}
        edited_files[file_path]['last_edit'] = time.time()

        ext = os.path.splitext(file_path)[1].lower()
        edited_extensions = set(state.get('edited_extensions', []))
        edited_extensions.add(ext)
        state['edited_extensions'] = sorted(edited_extensions)
        state['edited_files'] = edited_files

        tmp = tracker_file + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f)
        os.replace(tmp, tracker_file)  # atomic (L030)

        if len(edited_files) == 5:
            messages.append('5 unique files modified this phase. Consider checkpointing '
                            'for review before continuing. (Phased execution enforcement)')

    pytest_msg = run_auto_pytest(file_path)
    if pytest_msg:
        messages.append(pytest_msg)

    if messages:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': ' | '.join(messages),
        }}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass  # fail open
    sys.exit(0)
