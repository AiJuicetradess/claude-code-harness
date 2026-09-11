"""Mark 2026-05-09 reflection sessions as reflected:true and append reflection records."""

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SESSION_LOG = Path.home() / ".claude" / "reflections" / "session-log.jsonl"
REFLECTION_LOG = Path.home() / ".claude" / "reflections" / "reflection-log.jsonl"

ANALYZED = {
    "76226ccc-b7a2-43cc-b4c5-5aa37846ba63",
    "8f84a1d7-83bc-4166-b3d0-7495ea36db5c",
    "84412735-a4de-4c47-a5ba-559a63b48748",
    "e0408977-44ba-4b94-b0a8-67a990ac0b0e",
    "04dd4206-ee06-4d04-a91f-03aec56cf603",
}

LESSONS_CREATED = ["L029", "L030"]
LESSONS_UPDATED = ["L003", "L004", "L011", "L013", "L024", "L025"]
PROMOTED = ["L011", "L024", "L025"]
INTERNALIZED = []

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# 1. Rewrite session-log.jsonl flipping reflected:false -> true for analyzed sessions.
lines_in = SESSION_LOG.read_text(encoding="utf-8").splitlines()
lines_out = []
marked = 0
for line in lines_in:
    line = line.rstrip("\r")
    if not line.strip():
        continue
    try:
        obj = json.loads(line)
    except Exception:
        lines_out.append(line)
        continue
    sid = obj.get("session_id")
    if sid in ANALYZED and obj.get("reflected") is False:
        obj["reflected"] = True
        marked += 1
        lines_out.append(json.dumps(obj))
    else:
        lines_out.append(line)

# 2. Append a reflection-type record into session-log (matches prior convention).
session_log_record = {
    "type": "reflection",
    "timestamp": now,
    "sessions_analyzed": sorted(ANALYZED),
    "lessons_created": LESSONS_CREATED,
    "lessons_updated": LESSONS_UPDATED,
    "promoted": PROMOTED,
    "internalized": INTERNALIZED,
}
lines_out.append(json.dumps(session_log_record))
SESSION_LOG.write_text("\n".join(lines_out) + "\n", encoding="utf-8")

# 3. Append canonical record to reflection-log.jsonl.
with REFLECTION_LOG.open("a", encoding="utf-8") as f:
    f.write(json.dumps({
        "timestamp": now,
        "sessions_analyzed": 5,
        "session_ids": sorted(ANALYZED),
        "lessons_created": LESSONS_CREATED,
        "lessons_updated": LESSONS_UPDATED,
        "promoted": PROMOTED,
        "internalized": INTERNALIZED,
    }) + "\n")

print(f"Marked {marked} session entries as reflected:true.")
print(f"Appended reflection record to session-log.jsonl ({now}).")
print(f"Appended reflection record to reflection-log.jsonl.")
