"""Test harness for pre_bash_guard.py — regression + new L003 unset-var check."""
import json
import subprocess
import sys

from pathlib import Path
HOOK = str(Path(__file__).resolve().parent / "pre_bash_guard.py")

def run(tool, cmd, session="testsess-l003var"):
    payload = json.dumps({
        "tool_name": tool,
        "session_id": session,
        "tool_input": {"command": cmd},
    })
    p = subprocess.run([sys.executable, HOOK], input=payload,
                       capture_output=True, text=True, timeout=30)
    out = p.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out.splitlines()[0])
    except Exception:
        return {"raw": out}

def blocked(res):
    return bool(res) and res.get("decision") == "block"

CASES = [
    # (name, tool, command, expect_block, reason_substr or None)
    # --- NEW: L003 unset-path-variable variant ---
    ("unset var double-quoted", "Bash", 'python "$S/fub_backlog_probe.py"', True, "L003"),
    ("unset var braces", "Bash", 'python ${S}/probe.py', True, "L003"),
    ("unset var in unquoted heredoc", "Bash", 'bash <<EOF\npython "$S/probe.py"\nEOF', True, "L003"),
    ("unset var quote-then-slash", "Bash", 'python "$S"/probe.py', True, "L003"),
    # --- false-positive guards (must ALLOW) ---
    ("assigned same command", "Bash", 'S=/c/foo; python "$S/probe.py"', False, None),
    ("exported same command", "Bash", 'export S=/c/foo && python "$S/probe.py"', False, None),
    ("safe var HOME", "Bash", 'ls "$HOME/x"', False, None),
    ("real env var TEMP", "Bash", 'ls "$TEMP/x"', False, None),
    ("self-guarding :?", "Bash", 'python "${S:?}/probe.py"', False, None),
    ("single-quoted literal", "Bash", "echo '$S/literal'", False, None),
    ("quoted heredoc body", "Bash", "cat <<'EOF'\n$S/inside\nEOF", False, None),
    ("for-loop var", "Bash", 'for f in a b; do cp "$f/x" dest; done', False, None),
    ("awk positional", "Bash", "awk '{print $1/2}' f.txt", False, None),
    ("powershell not covered", "PowerShell", 'python "$S/probe.py"', False, None),
    ("escaped dollar", "Bash", 'echo "\\$S/x"', False, None),
    # --- regressions: existing checks unchanged ---
    ("backslash path", "Bash", r'ls "C:\Users\alice\Desktop"', True, "backslash"),
    ("win native flag", "Bash", "ipconfig /all", True, "/flag"),
    ("cmd nul redirect", "Bash", "ls x 2>nul", True, "nul"),
    ("destructive git", "Bash", "git push --force origin main", True, "Destructive"),
    ("plain command", "Bash", "echo hi", False, None),
    # --- SDD seat standard: grok dispatch guard (2026-08-26) ---
    ("grok -p in PowerShell", "PowerShell",
     'grok -p "do the task" --model grok-4.6', True, "grok-dispatch.sh"),
    ("grok.exe pathed -p in PS", "PowerShell",
     '& "$env:USERPROFILE/.grok/bin/grok.exe" -p "task" --cwd C:/repo', True, "grok-dispatch.sh"),
    ("grok --prompt-file in PS", "PowerShell",
     'grok --prompt-file brief.md --model grok-4.6', True, "grok-dispatch.sh"),
    ("grok models in PS allowed", "PowerShell", "grok models", False, None),
    ("wrapper in Bash allowed", "Bash",
     '~/.claude/bin/grok-dispatch.sh brief.md /c/repo --resume abc', False, None),
    ("grok -p quoted text only", "Bash",
     "echo 'run grok -p later'", False, None),
]

fails = 0
for name, tool, cmd, expect_block, substr in CASES:
    res = run(tool, cmd)
    is_block = blocked(res)
    ok = is_block == expect_block
    if ok and expect_block and substr:
        ok = substr.lower() in (res.get("reason") or "").lower()
    status = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
        detail = json.dumps(res)[:160] if res else "no output (allowed)"
        print(f"[{status}] {name}: expected block={expect_block}, got block={is_block} :: {detail}")
    else:
        print(f"[{status}] {name}")

# --- Bash raw-dispatch warn arm: non-blocking, once per session ---
import time
warn_sess = f"testsess-grokwrap-{time.time()}"
r1 = run("Bash", 'grok -p "$(cat brief.md)" --model grok-4.6 --cwd /c/repo', session=warn_sess)
ctx1 = ((r1 or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")
r2 = run("Bash", 'grok -p "$(cat brief2.md)" --model grok-4.6 --cwd /c/repo', session=warn_sess)
ctx2 = ((r2 or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")
w_ok = (not blocked(r1)) and "grok-dispatch.sh" in ctx1 and "grok-dispatch.sh" not in ctx2
if w_ok:
    print("[PASS] bash raw grok -p warns once, never blocks")
else:
    fails += 1
    print(f"[FAIL] bash raw grok -p warn arm :: r1={json.dumps(r1)[:160]} r2={json.dumps(r2)[:160]}")

total = len(CASES) + 1
print(f"\n{total - fails}/{total} passed")
sys.exit(1 if fails else 0)
