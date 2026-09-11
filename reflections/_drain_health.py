"""Print a loud one-line warning if the nightly reflection drain looks broken; silent when healthy.

Consumed by session-start-lessons.sh (SessionStart hook). Lesson L042: a
repeat-failing or non-running scheduled job must surface on night 2, not
night 20 (the _batch_prep.py deletion went unnoticed 2026-07-23..08-12).

Usage: python _drain_health.py [status_json_path]   # path override for tests
Always exits 0 (hook safety); ASCII-only output (lesson L018).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REFL = Path.home() / ".claude" / "reflections"
STATUS = Path(sys.argv[1]) if len(sys.argv) > 1 else REFL / "_steady_drain.status.json"
LOG = REFL / "_steady_drain.log"
FAIL_THRESHOLD = 2   # one failed night self-retries; two identical = broken
STALE_HOURS = 72     # tolerate a weekend of PC-off before calling the scheduler dead


def main():
    if not STATUS.exists():
        if LOG.exists():
            print("[DRAIN-HEALTH] _steady_drain.status.json is missing (deleted, or the drain never "
                  "ran since the 2026-08-12 hardening). Check %s (lesson L042)." % LOG)
        return
    try:
        st = json.loads(STATUS.read_text(encoding="utf-8"))
    except Exception:
        print("[DRAIN-HEALTH] _steady_drain.status.json is unreadable - inspect %s and %s (lesson L042)."
              % (STATUS, LOG))
        return

    fails = int(st.get("consecutive_failures", 0) or 0)
    if fails >= FAIL_THRESHOLD:
        print("[DRAIN-HEALTH] Nightly reflection drain has FAILED %d consecutive runs (last error: %s). "
              "Fix it NOW - read %s, then re-run _steady_drain.py. Lesson L042: this exact pattern once "
              "went unnoticed for 20 nights." % (fails, st.get("last_error") or "?", LOG))
        return

    try:
        last = datetime.strptime(st["last_run"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return
    age_h = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
    if age_h > STALE_HOURS:
        print("[DRAIN-HEALTH] Nightly reflection drain has not run in %.0f hours (last: %s). If the PC "
              "was on overnight, the scheduled task is dead - check it and %s (lesson L042)."
              % (age_h, st.get("last_run"), LOG))


if __name__ == "__main__":
    main()
