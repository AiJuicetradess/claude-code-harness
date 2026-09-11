"""Compact digest of existing lessons for dedup (fed to the reflection agent)."""
import io
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
LESSONS = Path.home() / ".claude" / "lessons"


def fm_get(text, key):
    m = re.search(r'^%s:\s*(.+)$' % re.escape(key), text, re.MULTILINE)
    return m.group(1).strip().strip('"') if m else ""


rows = []
for p in sorted(LESSONS.glob("L*.md")):
    t = p.read_text(encoding="utf-8")
    m = re.search(r'\*\*Rule:\*\*\s*(.+)', t)
    rule = m.group(1).strip() if m else ""
    rows.append((fm_get(t, "id"), fm_get(t, "severity"), fm_get(t, "category"),
                 fm_get(t, "times_violated"), fm_get(t, "title"), rule[:220]))

for r in rows:
    print("%s | %s | %s | violated=%s | %s\n    rule: %s" % r)
print("\nTOTAL existing lessons:", len(rows))
nums = [int(r[0][1:]) for r in rows if re.match(r"^L\d+$", r[0])]
print("Next new id: L%03d" % (max(nums) + 1))
