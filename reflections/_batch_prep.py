"""Prepare a signals bundle for a reflection batch (non-mutating).

Selects the next N unreflected sessions (newest-first, via _mark_reflected's
selector so prep and mark always agree), runs _extract_signals.py over each
transcript, and concatenates the results into a single bundle file.

Rebuilt 2026-08-12 — the original was lost ~2026-07-22, which silently broke
the nightly _steady_drain for 20 nights (see _steady_drain.log). Contract
reconstructed from _steady_drain.py's call site and the surviving
_steady_bundle.txt format.

Usage:
  python _batch_prep.py N BUNDLE_PATH [--minable]

Output: bundle written to BUNDLE_PATH; last stdout line is JSON:
  {"session_ids": [...], "bundle_bytes": N, "missing_transcripts": [...]}
Exit 0 on success (even if some transcripts are missing); non-zero on bad args.
"""

import json
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REFL = Path.home() / ".claude" / "reflections"
sys.path.insert(0, str(REFL))
import _mark_reflected as M  # noqa: E402

EXTRACT = REFL / "_extract_signals.py"
MAX_BUNDLE_CHARS = 60_000  # keep in sync with _steady_drain.MAX_BUNDLE_CHARS
EXTRACT_TIMEOUT = 60


def extract_signals(transcript_path):
    proc = subprocess.run(
        [sys.executable, str(EXTRACT), str(transcript_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=EXTRACT_TIMEOUT,
    )
    if proc.returncode != 0:
        return "(signal extraction failed: %s)" % (proc.stderr or "").strip()[:200]
    return (proc.stdout or "").strip()


def main():
    args = sys.argv[1:]
    minable_only = "--minable" in args
    pos = [a for a in args if not a.startswith("--")]
    if len(pos) < 2:
        print("usage: _batch_prep.py N BUNDLE_PATH [--minable]", file=sys.stderr)
        sys.exit(2)
    n = int(pos[0])
    bundle_path = Path(pos[1])

    records = M.select_next_records(n, minable_only=minable_only)
    # Budget the bundle so late sessions aren't crowded out by early huge ones.
    per_session_cap = max(4000, MAX_BUNDLE_CHARS // max(len(records), 1))

    session_ids = []
    missing = []
    parts = []
    for i, rec in enumerate(records, 1):
        sid = rec.get("session_id", "")
        session_ids.append(sid)
        header = "=== SESSION %d/%d  %s  ts=%s  cwd=%s  reason=%s  lines=%s ===" % (
            i, len(records), sid[:8], rec.get("timestamp", "?"),
            rec.get("cwd", "?"), rec.get("reason", "?"), rec.get("message_lines", "?"),
        )
        tp = Path(rec.get("transcript_path", ""))
        if not tp.exists():
            missing.append(sid)
            parts.append(header + "\n(transcript missing on disk - unmineable)\n")
            continue
        try:
            body = extract_signals(tp)
        except subprocess.TimeoutExpired:
            body = "(signal extraction timed out)"
        if len(body) > per_session_cap:
            body = body[:per_session_cap] + "\n...[session excerpt truncated]..."
        parts.append(header + "\n" + body + "\n")

    bundle = "\n".join(parts)
    bundle_path.write_text(bundle, encoding="utf-8")

    print(json.dumps({
        "session_ids": session_ids,
        "bundle_bytes": len(bundle.encode("utf-8")),
        "missing_transcripts": missing,
    }))


if __name__ == "__main__":
    main()
