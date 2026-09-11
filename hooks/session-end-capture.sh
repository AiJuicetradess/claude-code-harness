#!/usr/bin/env bash
# SessionEnd hook: captures session metadata for later reflection.
# Must complete in <1.5s. NO transcript parsing, NO analysis.
# No jq dependency — uses sed for JSON field extraction.
set -euo pipefail

INPUT=$(cat)

# Extract JSON fields with sed (no jq dependency)
extract_json_field() {
    echo "$INPUT" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p"
}

SESSION_ID=$(extract_json_field "session_id")
TRANSCRIPT_PATH=$(extract_json_field "transcript_path")
CWD=$(extract_json_field "cwd")
REASON=$(extract_json_field "reason")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Guard: skip if no session ID
[ -z "$SESSION_ID" ] && exit 0

REFLECTIONS_DIR="$HOME/.claude/reflections"
mkdir -p "$REFLECTIONS_DIR"

# Quick line count (fast, no full parse).
# The sed extraction keeps JSON-escaped backslashes (C:\\Users\\...), which
# fails [ -f ] on Git Bash — convert to forward slashes before testing.
MSG_COUNT=0
TRANSCRIPT_FS=$(printf '%s' "$TRANSCRIPT_PATH" | sed 's|\\\\|/|g')
if [ -n "$TRANSCRIPT_FS" ] && [ -f "$TRANSCRIPT_FS" ]; then
    MSG_COUNT=$(wc -l < "$TRANSCRIPT_FS" | tr -d ' ')
fi

# --- Headless-template filter (added 2026-07-07) ---
# Scheduled cron template runs (nightly repo brief, signal analyzer, earnings
# insights) were flooding the reflection queue (~3/day, near-zero lesson
# yield). Skip logging short sessions whose transcript head matches a known
# template opener, or whose prompt carries the generic [no-reflect] opt-out
# marker (add it to any future headless job prompt to keep it out of the
# queue). The MSG_COUNT<100 guard prevents false positives on long
# interactive sessions that merely QUOTE a template (e.g. a reflection run).
SHOULD_LOG=1
if [ "$MSG_COUNT" -gt 0 ] && [ "$MSG_COUNT" -lt 100 ]; then
    if head -c 262144 "$TRANSCRIPT_FS" 2>/dev/null | grep -qE 'You summarize repo activity metadata|You are generating the .{0,4}Key Insights|You analyze extracted signals from recent CLI coding sessions|\[no-reflect\]'; then
        SHOULD_LOG=0
    fi
fi

# Append to session log (fast JSONL append)
if [ "$SHOULD_LOG" -eq 1 ]; then
    echo "{\"session_id\":\"$SESSION_ID\",\"transcript_path\":\"$TRANSCRIPT_PATH\",\"cwd\":\"$CWD\",\"reason\":\"$REASON\",\"timestamp\":\"$TIMESTAMP\",\"message_lines\":$MSG_COUNT,\"reflected\":false}" >> "$REFLECTIONS_DIR/session-log.jsonl"
fi

# --- Retention pruner (added 2026-07-01, harness-audit step 13) ---
# Ages out per-session droppings the built-in cleanup never touches.
# Runs at most once per 24h (marker file); fail-open; CLAUDE_PRUNE_ROOT
# overrides the root for testing. Windows: teams/tasks are inert metadata
# dirs, not live processes — a 21-day newest-content window is safe.
python - <<'PYEOF' 2>/dev/null || true
import os, shutil, time

claude = os.environ.get('CLAUDE_PRUNE_ROOT') or os.path.join(os.path.expanduser('~'), '.claude')
marker = os.path.join(claude, '.last-prune')
now = time.time()

if os.path.exists(marker) and now - os.path.getmtime(marker) < 86400:
    raise SystemExit(0)


def prune_files(dirpath, days, prefix=None, suffix=None):
    cutoff = now - days * 86400
    try:
        names = os.listdir(dirpath)
    except OSError:
        return
    for n in names:
        if prefix and not n.startswith(prefix):
            continue
        if suffix and not n.endswith(suffix):
            continue
        p = os.path.join(dirpath, n)
        try:
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
        except OSError:
            pass


def newest_mtime(dirpath):
    newest = 0
    try:
        newest = os.path.getmtime(dirpath)
    except OSError:
        pass
    for root, dirs, files in os.walk(dirpath):
        for f in files:
            try:
                m = os.path.getmtime(os.path.join(root, f))
                if m > newest:
                    newest = m
            except OSError:
                pass
    return newest


def prune_dirs(dirpath, days):
    cutoff = now - days * 86400
    try:
        names = os.listdir(dirpath)
    except OSError:
        return
    for n in names:
        p = os.path.join(dirpath, n)
        if os.path.isdir(p) and newest_mtime(p) < cutoff:
            shutil.rmtree(p, ignore_errors=True)


prune_files(os.path.join(claude, 'session-state'), 14, suffix='.json')
prune_files(os.path.join(claude, 'security'), 30, prefix='security_warnings_state_', suffix='.json')
prune_files(os.path.join(claude, 'reflections'), 30, prefix='_batch')
prune_files(os.path.join(claude, 'reflections'), 30, prefix='_signals_')
prune_dirs(os.path.join(claude, 'file-history'), 60)
prune_dirs(os.path.join(claude, 'teams'), 21)
prune_dirs(os.path.join(claude, 'tasks'), 21)

with open(marker, 'w') as f:
    f.write(str(int(now)))
PYEOF
