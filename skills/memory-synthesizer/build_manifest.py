"""Build a manifest of the last N session transcripts for the memory synthesizer."""
import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-log", required=True, help="Path to session-log.jsonl")
    parser.add_argument("--output", required=True, help="Path to write manifest.json")
    parser.add_argument("--n", type=int, default=20, help="Number of sessions to include")
    parser.add_argument("--min-message-lines", type=int, default=10)
    args = parser.parse_args()

    log_path = Path(args.session_log)
    if not log_path.exists():
        print(f"session-log not found: {log_path}", file=sys.stderr)
        return 1

    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "reflection":
            continue
        if obj.get("message_lines", 0) < args.min_message_lines:
            continue
        entries.append(obj)

    # Sort newest first
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    # Dedupe by session_id, keep first (newest) occurrence
    deduped: "OrderedDict[str, dict]" = OrderedDict()
    for e in entries:
        sid = e.get("session_id", "")
        if sid and sid not in deduped:
            deduped[sid] = e

    take = list(deduped.values())[: args.n]
    sessions = [
        {
            "id": e.get("session_id"),
            "path": e.get("transcript_path"),
            "cwd": e.get("cwd"),
            "message_lines": e.get("message_lines"),
            "timestamp": e.get("timestamp"),
            "reason": e.get("reason"),
            "reflected": e.get("reflected", False),
        }
        for e in take
    ]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "generated_at": entries[0].get("timestamp") if entries else None,
                "session_count": len(sessions),
                "min_message_lines": args.min_message_lines,
                "sessions": sessions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(sessions)} sessions to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
