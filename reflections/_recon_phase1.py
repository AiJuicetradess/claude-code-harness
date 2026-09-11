"""Phase 1 recon (temp, delete after). ASCII-only prints."""
import json
import re
from pathlib import Path
from collections import Counter

SESSION_LOG = Path.home() / ".claude" / "reflections" / "session-log.jsonl"
REFLECTION_LOG = Path.home() / ".claude" / "reflections" / "reflection-log.jsonl"

raw_text = SESSION_LOG.read_text(encoding="utf-8")
raw = raw_text.splitlines()
total = len(raw)
blank = 0
parseable = 0
malformed = []
by_type = Counter()
refl_true = 0
refl_false_parsed = 0
no_session_id = 0
session_records = []

for i, line in enumerate(raw, 1):
    s = line.rstrip("\r")
    if not s.strip():
        blank += 1
        continue
    try:
        obj = json.loads(s)
    except Exception:
        malformed.append((i, s))
        continue
    parseable += 1
    t = obj.get("type", "session")
    by_type[t] += 1
    if t == "reflection":
        continue
    r = obj.get("reflected")
    if r is True:
        refl_true += 1
    elif r is False:
        refl_false_parsed += 1
    if not obj.get("session_id"):
        no_session_id += 1
    session_records.append(obj)

pat = re.compile(r'"reflected"\s*:\s*false')
spacing_agnostic_false = len(pat.findall(raw_text))
nospace_false = raw_text.count('"reflected":false')
space_false = raw_text.count('"reflected": false')

print("=== session-log.jsonl ===")
print("total lines:", total, "| blank:", blank, "| parseable:", parseable, "| malformed:", len(malformed))
print("by type:", dict(by_type))
print("parsed session reflected True:", refl_true, "| False:", refl_false_parsed, "| no session_id:", no_session_id)
print("spacing-agnostic reflected:false (regex):", spacing_agnostic_false)
print("  no-space style:", nospace_false, "| spaced style:", space_false)
print()
print("=== malformed lines (", len(malformed), ") ===")
for ln, content in malformed:
    print("L%d: %s" % (ln, content[:220]))
print()
if session_records:
    print("=== sample session record keys ===")
    print(sorted(session_records[0].keys()))
    print("--- first parsed session record (full) ---")
    print(json.dumps(session_records[0], indent=2)[:1400])

def ts(o):
    return o.get("timestamp") or o.get("ts") or ""

false_sessions = [o for o in session_records if o.get("reflected") is False]
false_sessions_sorted = sorted(false_sessions, key=ts, reverse=True)
print()
print("=== reflected:false parsed sessions:", len(false_sessions), "===")
if false_sessions_sorted:
    print("newest ts:", ts(false_sessions_sorted[0]), "| oldest ts:", ts(false_sessions_sorted[-1]))
    print("--- newest 3 (id | ts) ---")
    for o in false_sessions_sorted[:3]:
        print(" ", o.get("session_id"), "|", ts(o))

print()
print("=== reflection-log.jsonl ===")
if REFLECTION_LOG.exists():
    rl = [l for l in REFLECTION_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    print("records:", len(rl))
    if rl:
        print("last record:", rl[-1][:400])
else:
    print("MISSING")
