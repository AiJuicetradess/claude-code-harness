"""Mark the next N unreflected sessions reflected:true + append reflection records.

Cursor-driven. The reflection step feeds the lesson delta via --delta.

Usage:
  python _mark_reflected.py --list [N] [--minable]          # print next N unreflected records (JSON lines), no writes
  python _mark_reflected.py --count [--minable]             # print backlog (optionally minable-only), no writes
  python _mark_reflected.py --mark-crons                    # bulk-mark all non-minable (cron/worker) sessions reflected:true
  python _mark_reflected.py N [--delta D.json] [--minable]  # mark next N (optionally minable-only), record delta

Definitions:
  unreflected session = reflected:false, has session_id, type != "reflection"
  minable session     = message_lines > MIN_LINES (substantial/interactive). The rest
                        (<= MIN_LINES) are single-shot cron/worker sessions, zero-signal
                        by construction and mechanically markable.
Cursor: newest-first by timestamp, lenient per-line decode, idempotent; untouched lines
(including unparseable) are passed through verbatim on rewrite.
"""

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SESSION_LOG = Path.home() / ".claude" / "reflections" / "session-log.jsonl"
REFLECTION_LOG = Path.home() / ".claude" / "reflections" / "reflection-log.jsonl"
MIN_LINES = 100  # > this = minable/interactive; <= = cron/worker (mechanically markable)

EMPTY_DELTA = {"lessons_created": [], "lessons_updated": [], "promoted": [], "internalized": []}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_records():
    out = []
    for line in SESSION_LOG.read_text(encoding="utf-8").splitlines():
        line = line.rstrip("\r")
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            obj = None
        out.append((line, obj))
    return out


def _is_unreflected_session(obj):
    return (
        isinstance(obj, dict)
        and obj.get("type") != "reflection"
        and obj.get("reflected") is False
        and bool(obj.get("session_id"))
    )


def is_minable(obj, min_lines=MIN_LINES):
    return (obj.get("message_lines") or 0) > min_lines


def _candidates(records, minable_only=False):
    cands = [obj for _, obj in records if _is_unreflected_session(obj)]
    if minable_only:
        cands = [o for o in cands if is_minable(o)]
    return cands


def select_next_records(n, records=None, minable_only=False):
    if records is None:
        records = read_records()
    cands = _candidates(records, minable_only)
    cands.sort(key=lambda o: o.get("timestamp", ""), reverse=True)
    return cands[:n]


def select_next(n, records=None, minable_only=False):
    return [o["session_id"] for o in select_next_records(n, records, minable_only)]


def backlog_count(records=None, minable_only=False):
    if records is None:
        records = read_records()
    return len(_candidates(records, minable_only))


def load_delta(path):
    if not path:
        return dict(EMPTY_DELTA)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out = dict(EMPTY_DELTA)
    for k in EMPTY_DELTA:
        v = raw.get(k, [])
        out[k] = list(v) if isinstance(v, list) else []
    return out


def _rewrite(ids, mutate_record):
    """Flip reflected:true for ids; append mutate_record. Untouched lines verbatim. Returns marked count."""
    records = read_records()
    lines_out = []
    marked = 0
    for raw, obj in records:
        if isinstance(obj, dict) and obj.get("session_id") in ids and obj.get("reflected") is False:
            obj["reflected"] = True
            marked += 1
            lines_out.append(json.dumps(obj))
        else:
            lines_out.append(raw)
    lines_out.append(json.dumps(mutate_record))
    SESSION_LOG.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return marked


def mark(n, delta, minable_only=False):
    ids = set(select_next(n, minable_only=minable_only))
    now = _now()
    rec = {
        "type": "reflection", "timestamp": now, "sessions_analyzed": sorted(ids),
        "lessons_created": delta["lessons_created"], "lessons_updated": delta["lessons_updated"],
        "promoted": delta["promoted"], "internalized": delta["internalized"],
    }
    marked = _rewrite(ids, rec)
    with REFLECTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now, "sessions_analyzed": len(ids), "session_ids": sorted(ids),
            "lessons_created": delta["lessons_created"], "lessons_updated": delta["lessons_updated"],
            "promoted": delta["promoted"], "internalized": delta["internalized"],
        }) + "\n")
    print(f"Marked {marked} entries reflected:true (requested {n}, selected {len(ids)}, minable_only={minable_only}).")
    print(f"Delta: +{len(delta['lessons_created'])} created, {len(delta['lessons_updated'])} updated, "
          f"{len(delta['promoted'])} promoted, {len(delta['internalized'])} internalized.")
    print(f"Backlog now: {backlog_count()} unreflected ({backlog_count(minable_only=True)} minable).")


def mark_crons():
    records = read_records()
    ids = set(o["session_id"] for o in _candidates(records) if not is_minable(o))
    now = _now()
    note = f"mechanically marked {len(ids)} cron/worker sessions (<= {MIN_LINES} msg_lines, zero-signal by construction)"
    rec = {
        "type": "reflection", "timestamp": now, "mechanical_mark": True,
        "sessions_analyzed": len(ids), "note": note,
        "lessons_created": [], "lessons_updated": [], "promoted": [], "internalized": [],
    }
    marked = _rewrite(ids, rec)
    with REFLECTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now, "mechanical_mark": True, "sessions_analyzed": len(ids), "note": note,
            "lessons_created": [], "lessons_updated": [], "promoted": [], "internalized": [],
        }) + "\n")
    print(f"Mechanically marked {marked} cron/worker sessions reflected:true.")
    print(f"Backlog now: {backlog_count()} unreflected ({backlog_count(minable_only=True)} minable).")


def mark_no_transcript():
    """Mechanically mark unreflected sessions whose transcript is gone (unmineable: no data)."""
    records = read_records()
    ids = set(o["session_id"] for o in _candidates(records)
              if not Path(o.get("transcript_path", "")).exists())
    now = _now()
    note = f"mechanically marked {len(ids)} sessions with no transcript on disk (unmineable - transcript rotated away)"
    rec = {
        "type": "reflection", "timestamp": now, "mechanical_mark": True,
        "sessions_analyzed": len(ids), "note": note,
        "lessons_created": [], "lessons_updated": [], "promoted": [], "internalized": [],
    }
    marked = _rewrite(ids, rec)
    with REFLECTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now, "mechanical_mark": True, "sessions_analyzed": len(ids), "note": note,
            "lessons_created": [], "lessons_updated": [], "promoted": [], "internalized": [],
        }) + "\n")
    print(f"Mechanically marked {marked} no-transcript sessions reflected:true.")
    print(f"Backlog now: {backlog_count()} unreflected ({backlog_count(minable_only=True)} minable).")


def main():
    args = sys.argv[1:]
    minable_only = "--minable" in args
    if args and args[0] == "--list":
        nargs = [a for a in args[1:] if not a.startswith("--")]
        n = int(nargs[0]) if nargs else 40
        for obj in select_next_records(n, minable_only=minable_only):
            print(json.dumps(obj))
        return
    if args and args[0] == "--count":
        print(backlog_count(minable_only=minable_only))
        return
    if args and args[0] == "--mark-crons":
        mark_crons()
        return
    if args and args[0] == "--mark-no-transcript":
        mark_no_transcript()
        return
    if not args or args[0].startswith("--"):
        print("usage: _mark_reflected.py N [--delta D.json] [--minable] | --list [N] [--minable] | --count [--minable] | --mark-crons", file=sys.stderr)
        sys.exit(2)
    n = int(args[0])
    delta_path = args[args.index("--delta") + 1] if "--delta" in args else None
    mark(n, load_delta(delta_path), minable_only=minable_only)


if __name__ == "__main__":
    main()
