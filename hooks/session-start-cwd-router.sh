#!/usr/bin/env bash
# SessionStart hook: routes the current working directory to a domain-preflight
# skill suggestion. Reads ~/.claude/hooks/cwd-skill-map.json (substring -> skill
# name) and emits an additionalContext block proposing the matching preflight skill.
#
# Pairs with per-project preflight skills: add one entry per project to
# cwd-skill-map.json (substring of the project path -> skill name).
#
# Silent on no-match. Never blocks session start.
set -euo pipefail

MAP="$HOME/.claude/hooks/cwd-skill-map.json"
INPUT=$(cat)

# No map = no router (silent pass)
[ ! -f "$MAP" ] && exit 0

# Use Python for JSON parsing (sed-based extraction is brittle for nested objects)
ROUTER_OUT=$(echo "$INPUT" | python -c "
import sys, json, os, subprocess

try:
    data = json.load(sys.stdin)
    cwd = data.get('cwd', '') or os.environ.get('PWD', '')
    if not cwd:
        sys.exit(0)

    map_path = os.path.expanduser('~/.claude/hooks/cwd-skill-map.json')
    with open(map_path, 'r', encoding='utf-8') as f:
        skill_map = json.load(f)

    # Normalize cwd to forward slashes for case-insensitive substring match.
    # chr(92) is the backslash char — sidesteps bash double-quote backslash
    # mangling inside \$(python -c \"...\"), which would otherwise leave Python
    # with an unterminated string literal. (Per L011: avoid inline nested escaping.)
    cwd_norm = cwd.replace(chr(92), '/').lower()

    matched = None
    for substring, info in skill_map.items():
        if substring.startswith('_'):
            continue
        if substring.lower() in cwd_norm:
            matched = (substring, info)
            break

    if not matched:
        sys.exit(0)

    substring, info = matched
    skill = info.get('skill', '')
    desc = info.get('description', '')

    parts = [
        '<cwd-router>',
        'Domain match: ' + substring + ' -> ' + skill,
        desc,
        '',
        'Before any operational / diagnostic / audit work in this directory, invoke the [' + skill + '] skill via the Skill tool. It runs the cold-start preflight checks (auth, tooling presence, service liveness) so the session does not burn 10-30 cold tool calls re-deriving them.',
    ]

    # Optional cheap probe — last 3 commits, if cwd is a git repo
    if os.path.exists(os.path.join(cwd, '.git')):
        try:
            r = subprocess.run(
                ['git', '-C', cwd, 'log', '-3', '--oneline'],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0 and r.stdout.strip():
                parts.append('')
                parts.append('Recent commits:')
                parts.append(r.stdout.strip())
        except Exception:
            pass

    parts.append('</cwd-router>')
    print('\n'.join(parts))

except Exception:
    # Silent failure — never block session start
    pass
" 2>/dev/null)

[ -z "$ROUTER_OUT" ] && exit 0

# Escape for JSON (mirror session-start-lessons.sh pattern)
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

escaped=$(escape_for_json "$ROUTER_OUT")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${escaped}"
  }
}
EOF

exit 0
