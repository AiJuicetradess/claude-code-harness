"""Tests for the 2026-08-25 lesson-to-hook promotions (L018/L029/L034/L035/L028-ask)
plus regressions on the pre-existing checks. ASCII-only output (L018).

Run: python test_promoted_guards.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOKS = os.path.dirname(os.path.abspath(__file__))
BASH_GUARD = os.path.join(HOOKS, 'pre_bash_guard.py')
FILE_GUARD = os.path.join(HOOKS, 'pre_file_guard.py')
READ_GUARD = os.path.join(HOOKS, 'pre_read_guard.py')


def run_hook(hook, tool, tool_input, session):
    payload = json.dumps({'tool_name': tool, 'session_id': session,
                          'tool_input': tool_input})
    p = subprocess.run([sys.executable, hook], input=payload,
                       capture_output=True, text=True, timeout=30)
    out = p.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out.splitlines()[0])
    except Exception:
        return {'raw': out}


def blocked(res):
    return bool(res) and (
        res.get('decision') == 'block'
        or (res.get('hookSpecificOutput') or {}).get('permissionDecision') == 'deny')


def asked(res):
    return bool(res) and (
        (res.get('hookSpecificOutput') or {}).get('permissionDecision') == 'ask')


# --- fixtures for the read guard ---
FIX = tempfile.mkdtemp(prefix='guardtest-')
BIG_MULTI = os.path.join(FIX, 'big_multiline.txt')
BIG_BLOB = os.path.join(FIX, 'big_oneline.json')
SMALL = os.path.join(FIX, 'small.txt')
BIG_PNG = os.path.join(FIX, 'big_image.png')
with open(BIG_MULTI, 'w') as f:
    f.write(('x' * 80 + '\n') * 800)          # ~64KB, many lines
with open(BIG_BLOB, 'w') as f:
    f.write('{"k": "' + 'y' * 60000 + '"}')   # ~60KB, one line
with open(SMALL, 'w') as f:
    f.write('hello\n' * 10)
with open(BIG_PNG, 'wb') as f:
    f.write(b'\x89PNG' + b'\x00' * 60000)      # >50KB, media ext

ARROW = '\u2192'
CHECK = '\u2713'
SECRET = 'api_key = "abc' + 'defghij12345"'   # split so writing THIS file passes

n = [0]


def sid(name):
    n[0] += 1
    return 'promtest-%d-%s' % (n[0], name.replace(' ', '')[:16])


CASES = []

# --- pre_bash_guard: L035 PowerShell tool ---
CASES += [
    ('ps && chain', BASH_GUARD, 'PowerShell',
     {'command': 'npm install && npm test'}, 'block', 'L035'),
    ('ps || chain', BASH_GUARD, 'PowerShell',
     {'command': 'ping -n 1 host || echo down'}, 'block', 'L035'),
    ('ps && in dquotes ok', BASH_GUARD, 'PowerShell',
     {'command': 'bash -c "a && b"'}, 'allow', None),
    ('ps && in herestring ok', BASH_GUARD, 'PowerShell',
     {'command': "@'\na && b\n'@ | Set-Content x.txt"}, 'allow', None),
    ('ps && in comment ok', BASH_GUARD, 'PowerShell',
     {'command': 'Get-Date # a && b'}, 'allow', None),
    ('ps /dev/null', BASH_GUARD, 'PowerShell',
     {'command': 'node x.js 2>/dev/null'}, 'block', 'L035'),
    ('ps export', BASH_GUARD, 'PowerShell',
     {'command': 'export FOO=1; node x.js'}, 'block', 'L035'),
    ('ps native 2>&1', BASH_GUARD, 'PowerShell',
     {'command': 'uv run mypy src 2>&1 | Select-Object -First 5'},
     'block', 'L034'),
    ('ps git 2>&1', BASH_GUARD, 'PowerShell',
     {'command': 'git status 2>&1'}, 'block', 'L034'),
    ('ps cmdlet redirect ok', BASH_GUARD, 'PowerShell',
     {'command': 'Get-Content x.txt 2>$null'}, 'allow', None),
    ('ps plain pipeline ok', BASH_GUARD, 'PowerShell',
     {'command': 'Get-ChildItem | Select-Object Name'}, 'allow', None),
]

# --- pre_bash_guard: L035 Bash tool ---
CASES += [
    ('bash 2>$null', BASH_GUARD, 'Bash',
     {'command': 'ls x 2>$null'}, 'block', 'L035'),
    ('bash cmdlet', BASH_GUARD, 'Bash',
     {'command': 'ls | Select-Object -First 3'}, 'block', 'L035'),
    ('bash $env:', BASH_GUARD, 'Bash',
     {'command': 'echo $env:PATH'}, 'block', 'L035'),
    ('bash quoted cmdlet ok', BASH_GUARD, 'Bash',
     {'command': "grep 'Select-Object' file.txt"}, 'allow', None),
    ('bash dquoted cmdlet ok', BASH_GUARD, 'Bash',
     {'command': 'grep "Get-Item" file.txt'}, 'allow', None),
    ('bash lowercase read ok', BASH_GUARD, 'Bash',
     {'command': 'while read -r line; do echo "$line"; done < f'},
     'allow', None),
]

# --- pre_bash_guard: L018 inline python ---
CASES += [
    ('bash python -c unicode', BASH_GUARD, 'Bash',
     {'command': 'python -c "print(\'' + ARROW + ' done\')"'},
     'block', 'L018'),
    ('ps python -c unicode', BASH_GUARD, 'PowerShell',
     {'command': 'python -c "print(\'' + CHECK + '\')"'}, 'block', 'L018'),
    ('python -c ascii ok', BASH_GUARD, 'Bash',
     {'command': 'python -c "print(1+1)"'}, 'allow', None),
    ('python file arg unicode ok', BASH_GUARD, 'Bash',
     {'command': 'python x.py "caf\u00e9"'}, 'allow', None),
]

# --- pre_bash_guard: L028 ask gate ---
CASES += [
    ('ssh systemctl restart', BASH_GUARD, 'Bash',
     {'command': 'ssh root@1.2.3.4 "systemctl restart n8n"'}, 'ask', 'L028'),
    ('ssh rm -rf relative', BASH_GUARD, 'Bash',
     {'command': 'ssh host "rm -rf ./releases/old"'}, 'ask', 'L028'),
    ('ssh truncate', BASH_GUARD, 'PowerShell',
     {'command': 'ssh db "psql -c \'TRUNCATE events\'"'}, 'ask', 'L028'),
    # deny outranks ask: absolute-path rm -rf / DROP TABLE over ssh still hit
    # the pre-existing DESTRUCTIVE hard-block, not the L028 ask gate.
    ('ssh rm -rf abs = deny', BASH_GUARD, 'Bash',
     {'command': 'ssh host "rm -rf /opt/app/data"'}, 'block', 'Destructive'),
    ('ssh drop table = deny', BASH_GUARD, 'PowerShell',
     {'command': 'ssh db "psql -c \'DROP TABLE users\'"'}, 'block',
     'Destructive'),
    ('curl delete', BASH_GUARD, 'Bash',
     {'command': 'curl -X DELETE https://api.example.com/v1/thing/9'},
     'ask', 'L028'),
    ('ssh readonly ok', BASH_GUARD, 'Bash',
     {'command': 'ssh host "docker ps"'}, 'allow', None),
    ('ssh tail ok', BASH_GUARD, 'Bash',
     {'command': 'ssh host "tail -n 50 /var/log/syslog"'}, 'allow', None),
    ('local rm untouched', BASH_GUARD, 'Bash',
     {'command': 'rm -f ./scratch.txt'}, 'allow', None),
]

# --- pre_bash_guard: regressions on pre-existing checks ---
CASES += [
    ('regr backslash path', BASH_GUARD, 'Bash',
     {'command': 'ls "C:\\Users\\alice\\Desktop"'}, 'block', 'L003'),
    ('regr win native flag', BASH_GUARD, 'Bash',
     {'command': 'ipconfig /all'}, 'block', 'L003'),
    ('regr destructive git', BASH_GUARD, 'Bash',
     {'command': 'git push --force origin main'}, 'block', 'Destructive'),
    ('regr unset var', BASH_GUARD, 'Bash',
     {'command': 'python "$S/probe.py"'}, 'block', 'L003'),
    ('regr plain ok', BASH_GUARD, 'Bash',
     {'command': 'echo hi'}, 'allow', None),
    ('regr ps plain ok', BASH_GUARD, 'PowerShell',
     {'command': 'Get-Date; Get-Process | Measure-Object'}, 'allow', None),
]

# --- pre_read_guard: L029 + regressions ---
CASES += [
    ('read big no limit', READ_GUARD, 'Read',
     {'file_path': BIG_MULTI}, 'block', 'L029'),
    ('read big with limit ok', READ_GUARD, 'Read',
     {'file_path': BIG_MULTI, 'limit': 200}, 'allow', None),
    ('read blob even with limit', READ_GUARD, 'Read',
     {'file_path': BIG_BLOB, 'limit': 5}, 'block', 'single-line'),
    ('read small ok', READ_GUARD, 'Read',
     {'file_path': SMALL}, 'allow', None),
    ('read big png ok', READ_GUARD, 'Read',
     {'file_path': BIG_PNG}, 'allow', None),
    ('regr read missing', READ_GUARD, 'Read',
     {'file_path': os.path.join(FIX, 'nope.txt')}, 'block', 'L001'),
    ('regr read directory', READ_GUARD, 'Read',
     {'file_path': FIX}, 'block', 'DIRECTORY'),
]

# --- pre_file_guard: L018 + regressions ---
NEW_PY = os.path.join(FIX, 'newscript.py')
CASES += [
    ('write py unicode print', FILE_GUARD, 'Write',
     {'file_path': NEW_PY,
      'content': 'x = 1\nprint("' + ARROW + ' done")\n'}, 'block', 'L018'),
    ('write py unicode logger', FILE_GUARD, 'Write',
     {'file_path': NEW_PY,
      'content': 'import logging\nlogging.info("' + CHECK + '")\n'},
     'block', 'L018'),
    ('write py unicode comment ok', FILE_GUARD, 'Write',
     {'file_path': NEW_PY,
      'content': '# caf\u00e9 notes\nprint("ok")\n'}, 'allow', None),
    ('write py hatch ok', FILE_GUARD, 'Write',
     {'file_path': NEW_PY,
      'content': 'import sys, io\nsys.stdout.reconfigure(encoding="utf-8")\n'
                 'print("' + ARROW + '")\n'}, 'allow', None),
    ('write md unicode ok', FILE_GUARD, 'Write',
     {'file_path': os.path.join(FIX, 'notes.md'),
      'content': 'print("' + ARROW + '") in prose\n'}, 'allow', None),
    ('regr env file', FILE_GUARD, 'Write',
     {'file_path': os.path.join(FIX, '.env'), 'content': 'A=1'},
     'block', 'L006'),
    ('regr secret payload', FILE_GUARD, 'Write',
     {'file_path': NEW_PY, 'content': SECRET}, 'block', 'L010'),
]

fails = 0
for name, hook, tool, tool_input, expect, substr in CASES:
    res = run_hook(hook, tool, tool_input, sid(name))
    if expect == 'block':
        ok = blocked(res)
    elif expect == 'ask':
        ok = asked(res)
    else:
        ok = not blocked(res) and not asked(res)
    if ok and substr:
        reason = (res.get('reason') or
                  (res.get('hookSpecificOutput') or {})
                  .get('permissionDecisionReason') or '') if res else ''
        ok = substr.lower() in reason.lower()
    if ok:
        print('[PASS] %s' % name)
    else:
        fails += 1
        detail = json.dumps(res)[:200] if res else 'no output (allowed)'
        print('[FAIL] %s: expected %s :: %s' % (name, expect, detail))

print('\n%d/%d passed' % (len(CASES) - fails, len(CASES)))
sys.exit(1 if fails else 0)
