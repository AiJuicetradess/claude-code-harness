"""PreToolUse guard for Edit|NotebookEdit|Write.

Merges pre-env-block + pre-secrets-scan + pre-edit-guardian into ONE
interpreter spawn (was three bash+python spawns per Edit, ~0.6-1.5s of
Miniconda cold-start latency on every file operation).

Check order: env/secrets file block (L006) -> hardcoded-secret scan (L010)
-> non-ASCII in .py print/log payloads (L018, added 2026-08-25)
-> read-before-edit guardian (L001/L013/L021). First block wins.
New-file creation (nonexistent path) is always allowed by the guardian.

L018 (11 logged violations): Windows consoles default to cp1252/cp437, so
non-ASCII inside print()/logging calls crashes UnicodeEncodeError at
runtime. Scans only print/log LINES of the payload (comments/docstrings
with Unicode are fine — Write lands UTF-8 on disk). Escape hatch: the
payload or existing file declares PYTHONIOENCODING / reconfigure(encoding /
TextIOWrapper.
Fail-open by design: an internal error must never block the tool call.
"""
import fnmatch
import json
import os
import re
import sys

ENV_ALLOW = ['.env.example', '*.env.example', '.env.sample', '*.env.sample',
             '.env.template', '*.env.template']
ENV_DENY = ['.env', '.env.*', '*.env', 'credentials.json', 'secrets.json',
            'secrets.yaml', '*.pem', '*.key']

# Keep in sync with pre_bash_guard.py (kept self-contained on purpose —
# hooks must not depend on import paths).
SECRET_PATTERNS = [
    r"(?:sk-|sk_live_|sk_test_)[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"gho_[a-zA-Z0-9]{36}",
    r"AKIA[0-9A-Z]{16}",
    r"(?:password|passwd|pwd)\s*[=:]\s*[\x22\x27][^\x22\x27]{8,}[\x22\x27]",
    r"(?:api_key|apikey|api_secret)\s*[=:]\s*[\x22\x27][^\x22\x27]{10,}[\x22\x27]",
    r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
    r"xox[bpsar]-[a-zA-Z0-9-]{10,}",
]


def emit_block(msg):
    # Both the legacy decision field and the current PreToolUse
    # permissionDecision so the block holds on old and new CC builds.
    print(json.dumps({
        'decision': 'block',
        'reason': msg,
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': msg,
        },
    }))


def main():
    data = json.load(sys.stdin)
    session_id = data.get('session_id', 'unknown')
    inp = data.get('tool_input', {}) or {}
    file_path = inp.get('file_path') or inp.get('notebook_path') or ''

    # --- 1. env/secrets FILE block (L006) ---
    if file_path:
        base = os.path.basename(file_path)
        if not any(fnmatch.fnmatch(base, p) for p in ENV_ALLOW):
            if any(fnmatch.fnmatch(base, p) for p in ENV_DENY):
                emit_block('BLOCKED: Editing secrets/env files is not allowed. '
                           'Use environment variables or a secrets manager instead. '
                           '(Enforced by pre-file-guard hook, lesson L006)')
                return

    # --- 2. hardcoded-secret CONTENT scan (L010) ---
    text = ' '.join([inp.get('new_string') or '', inp.get('content') or '',
                     inp.get('command') or '']).strip()
    if text:
        for p in SECRET_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                emit_block('BLOCKED: Detected hardcoded secret/credential in payload. '
                           'Use environment variables instead — e.g. $GITHUB_TOKEN in shell, '
                           'os.environ[...] in Python, process.env[...] in Node. '
                           '(Enforced by pre-file-guard hook, lesson L010)')
                return

    # --- 2.5 L018: non-ASCII in .py print/log payload lines ---
    if file_path.lower().endswith(('.py', '.pyw')):
        payload = (inp.get('new_string') or inp.get('content') or '')
        hatch = ('PYTHONIOENCODING' in payload
                 or 'reconfigure(encoding' in payload
                 or 'TextIOWrapper' in payload)
        if payload and not hatch and os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8',
                          errors='ignore') as f:
                    head = f.read(32768)
                hatch = ('PYTHONIOENCODING' in head
                         or 'reconfigure(encoding' in head
                         or 'TextIOWrapper' in head)
            except OSError:
                pass
        if payload and not hatch:
            bad = []
            for i, line in enumerate(payload.splitlines(), 1):
                if re.search(r'\bprint\s*\(|\blog(?:ger|ging)\.[a-z]+\s*\(',
                             line):
                    chars = sorted({c for c in line if ord(c) > 127})
                    if chars:
                        bad.append('payload line %d: %s' % (
                            i, ' '.join('U+%04X' % ord(c)
                                        for c in chars[:5])))
            if bad:
                emit_block('BLOCKED: Non-ASCII inside print/log calls in a '
                           '.py file (%s). Windows consoles default to '
                           'cp1252/cp437 — this raises UnicodeEncodeError at '
                           'runtime (11 logged sessions). Use ASCII stand-ins '
                           '(-->, [OK], [!], -) and fix ALL occurrences in '
                           'ONE pass (replace_all), or declare '
                           "sys.stdout.reconfigure(encoding='utf-8') / set "
                           'PYTHONIOENCODING=utf-8 at the launcher. '
                           '(Enforced by pre-file-guard hook, lesson L018)'
                           % '; '.join(bad[:4]))
                return

    # --- 3. read-before-edit guardian (L001/L013/L021) ---
    if not file_path:
        return
    file_path = os.path.normpath(file_path)
    if not os.path.exists(file_path):
        return  # new file — nothing to have read yet

    tracker_dir = os.path.join(os.path.expanduser('~'), '.claude', 'session-state')
    tracker_file = os.path.join(tracker_dir, session_id + '.json')
    state = {}
    if os.path.exists(tracker_file):
        with open(tracker_file, 'r') as f:
            state = json.load(f)

    reads = state.get('reads', {})
    edits = state.get('edits', {})

    # Accept either the given form or the absolute form of the path (the
    # tracker records both since 2026-09-05).
    abs_path = os.path.normpath(os.path.abspath(file_path))
    read_key = file_path if file_path in reads else (abs_path if abs_path in reads else None)
    if read_key is None:
        emit_block('BLOCKED: You have not Read %s in this session. Read the file '
                   'before editing. (Enforced by pre-file-guard hook, lessons L001/L013)'
                   % os.path.basename(file_path))
        return

    edit_info = edits.get(file_path, {'count': 0, 'last_read': 0})
    last_read_time = reads.get(read_key, 0)
    consecutive = edit_info.get('count', 0)

    if consecutive >= 3 and edit_info.get('last_read', 0) >= last_read_time:
        emit_block('BLOCKED: %d consecutive edits to %s without a verification read. '
                   'Re-read the file. (Enforced by pre-file-guard hook, lesson L021/P15)'
                   % (consecutive, os.path.basename(file_path)))
        return

    warnings = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
        if line_count > 300:
            warnings.append('File is %d LOC (>300). If refactoring, remove dead '
                            'code first (Step 0).' % line_count)
    except Exception:
        pass

    if last_read_time > edit_info.get('last_read', 0):
        edit_info = {'count': 1, 'last_read': last_read_time}
    else:
        edit_info['count'] = consecutive + 1
    edits[file_path] = edit_info
    state['edits'] = edits

    os.makedirs(tracker_dir, exist_ok=True)
    tmp = tracker_file + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f)
    os.replace(tmp, tracker_file)  # atomic — no partial/clobbered state (L030)

    if warnings:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'additionalContext': ' | '.join(warnings),
        }}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass  # fail open — a guard crash must never block work
    sys.exit(0)
