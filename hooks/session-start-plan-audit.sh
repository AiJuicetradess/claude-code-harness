#!/usr/bin/env bash
# SessionStart hook: one-line nudge when the cwd repo has implemented plans still
# on disk or specs whose status was never synced. Pairs with the spec-lifecycle
# skill (~/.claude/skills/spec-lifecycle). Silent when the cwd has no
# docs/superpowers directory or when the audit is clean. Never blocks startup.
# Emits hookSpecificOutput JSON, the same shape as the sibling SessionStart hooks.
set -uo pipefail

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | python -c "import sys, json
try:
    print(json.load(sys.stdin).get('cwd', '') or '')
except Exception:
    print('')" 2>/dev/null)
[ -z "$CWD" ] && CWD="${PWD:-}"
[ -z "$CWD" ] && exit 0
[ -d "$CWD/docs/superpowers" ] || exit 0

AUDIT="${HOME:-}/.claude/skills/spec-lifecycle/scripts/plan_audit.py"
[ -f "$AUDIT" ] || exit 0

MSG=$(python "$AUDIT" "$CWD" --brief 2>/dev/null) || exit 0
[ -z "$MSG" ] && exit 0

printf '%s' "$MSG" | python -c "import sys, json
msg = sys.stdin.read()
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart',
                  'additionalContext': '<spec-lifecycle>\n' + msg + '\n</spec-lifecycle>'}}))" 2>/dev/null || exit 0
exit 0
