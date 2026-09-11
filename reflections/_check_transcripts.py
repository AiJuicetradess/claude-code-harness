"""How many remaining minable sessions still have a transcript on disk?"""
import io
import sys
from pathlib import Path

import _mark_reflected as M

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

minable = M.select_next_records(10000, minable_only=True)
present = [o for o in minable if Path(o.get("transcript_path", "")).exists()]
missing = [o for o in minable if not Path(o.get("transcript_path", "")).exists()]
print("minable total: %d | transcript present: %d | missing: %d" % (len(minable), len(present), len(missing)))
print("\n=== PRESENT (reflectable) — id | lines | date | cwd ===")
for o in sorted(present, key=lambda o: o.get("timestamp", ""), reverse=True):
    print("  %s | %5s | %s | %s" % (o["session_id"][:8], o.get("message_lines"),
                                    o.get("timestamp", "")[:10], o.get("cwd")))
print("\nmissing date range:", end=" ")
ms = sorted(missing, key=lambda o: o.get("timestamp", ""))
if ms:
    print(ms[0].get("timestamp", "")[:10], "->", ms[-1].get("timestamp", "")[:10])
