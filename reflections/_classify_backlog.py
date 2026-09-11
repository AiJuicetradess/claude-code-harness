"""Show the minable (interactive) vs mechanical-mark (cron) cut at a line threshold."""
import io
import sys
from collections import Counter

import _mark_reflected as M

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MIN = 100
recs = M.read_records()
unrefl = [o for _, o in recs if M._is_unreflected_session(o)]
minable = [o for o in unrefl if (o.get("message_lines") or 0) > MIN]
cron = [o for o in unrefl if (o.get("message_lines") or 0) <= MIN]

print("threshold: > %d msg_lines = MINABLE (reflect); <= = MECHANICAL-MARK (cron)" % MIN)
print("total unreflected: %d | minable: %d | mechanical-mark: %d" % (len(unrefl), len(minable), len(cron)))

print("\n=== MINABLE set by cwd ===")
for cwd, n in Counter(o.get("cwd", "?") for o in minable).most_common(20):
    print(" %4d  %s" % (n, cwd))

print("\n=== sample MINABLE (lines | reason | ts | cwd) newest 12 ===")
for o in sorted(minable, key=lambda o: o.get("timestamp", ""), reverse=True)[:12]:
    print("  %5s | %-6s | %s | %s" % (o.get("message_lines"), o.get("reason"),
                                      o.get("timestamp", "")[:10], o.get("cwd", "?")))

scripts_minable = [o for o in minable if str(o.get("cwd", "")).replace("/", "\\").endswith("scripts")]
print("\nAIOS\\scripts sessions inside MINABLE (would be reflected; expect ~0):", len(scripts_minable))

noncron_marked = [o for o in cron if not str(o.get("cwd", "")).replace("/", "\\").endswith("scripts")]
print("non-scripts sessions inside MECHANICAL-MARK (mid-size; review):", len(noncron_marked))
print(" their cwd spread:")
for cwd, n in Counter(o.get("cwd", "?") for o in noncron_marked).most_common(12):
    print("   %4d  %s" % (n, cwd))
