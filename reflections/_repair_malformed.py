"""One-time repair of malformed JSONL records (unescaped Windows-path backslashes).

Fixes only lines that fail json.loads, by doubling backslashes that don't start a
valid JSON escape. Valid lines are emitted byte-identical. Refuses to write unless
exactly the expected number of lines change and 0 remain unparseable (fail-safe).
Temp helper — delete after.
"""
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SESSION_LOG = Path.home() / ".claude" / "reflections" / "session-log.jsonl"
EXPECT = 7

# A backslash NOT followed by a valid JSON escape char -> needs doubling.
INVALID_ESC = re.compile(r'\\(?!["\\/bfnrtu])')

src = [l.rstrip("\r") for l in SESSION_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
out = []
repaired = []
failed = []
for i, s in enumerate(src, 1):
    try:
        json.loads(s)
        out.append(s)
        continue
    except Exception:
        pass
    fixed = INVALID_ESC.sub(r'\\\\', s)
    try:
        obj = json.loads(fixed)
        out.append(json.dumps(obj))
        repaired.append((i, obj.get("session_id"), obj.get("reflected")))
    except Exception as e:
        out.append(s)
        failed.append((i, str(e)[:120]))

changed = sum(1 for a, b in zip(src, out) if a != b)
print("input lines:", len(src), "| changed:", changed, "| repaired:", len(repaired), "| still-failing:", len(failed))
for i, sid, refl in repaired:
    print("  repaired L%d: %s reflected=%s" % (i, sid, refl))
for i, e in failed:
    print("  FAIL L%d: %s" % (i, e))

if failed or changed != EXPECT or len(out) != len(src):
    print("ABORT: unexpected state (changed=%d expected=%d, failed=%d, len_in=%d len_out=%d) -- NOT writing"
          % (changed, EXPECT, len(failed), len(src), len(out)))
    sys.exit(1)

SESSION_LOG.write_text("\n".join(out) + "\n", encoding="utf-8")
print("WROTE repaired session-log.jsonl")

# end-to-end verify
bad = 0
for s in SESSION_LOG.read_text(encoding="utf-8").splitlines():
    if not s.strip():
        continue
    try:
        json.loads(s)
    except Exception:
        bad += 1
print("post-repair unparseable lines:", bad)
