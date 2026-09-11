"""Composition of the remaining unreflected backlog (cron-worker vs interactive)."""
import io
import sys
from collections import Counter

import _mark_reflected as M

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

recs = M.read_records()
unrefl = [o for _, o in recs if M._is_unreflected_session(o)]
print("remaining unreflected:", len(unrefl))


def bucket(n):
    if n is None:
        return "unknown"
    if n <= 3:
        return "1-3 (single-shot/cron)"
    if n <= 20:
        return "4-20 (tiny)"
    if n <= 100:
        return "21-100 (small)"
    if n <= 500:
        return "101-500 (medium)"
    return "500+ (large)"


bc = Counter(bucket(o.get("message_lines")) for o in unrefl)
print("\n=== message_lines buckets ===")
for k in ["1-3 (single-shot/cron)", "4-20 (tiny)", "21-100 (small)",
          "101-500 (medium)", "500+ (large)", "unknown"]:
    if k in bc:
        print(" %5d  %s" % (bc[k], k))

cc = Counter(o.get("cwd", "?") for o in unrefl)
print("\n=== top cwd (of remaining) ===")
for cwd, n in cc.most_common(15):
    print(" %5d  %s" % (n, cwd))

crons = [o for o in unrefl if (o.get("message_lines") or 0) <= 3]
inter = [o for o in unrefl if (o.get("message_lines") or 0) > 3]
big = [o for o in inter if (o.get("message_lines") or 0) > 100]
print("\n=== heuristic split ===")
print(" likely cron/single-shot (<=3 msg lines):", len(crons))
print(" likely interactive (>3 msg lines):", len(inter))
print(" of interactive, medium+large (>100 lines):", len(big))


def ts(o):
    return o.get("timestamp", "")


for label, grp in [("interactive", inter), ("cron", crons)]:
    s = sorted(grp, key=ts)
    if s:
        print(" %s date range: %s -> %s" % (label, ts(s[0])[:10], ts(s[-1])[:10]))
