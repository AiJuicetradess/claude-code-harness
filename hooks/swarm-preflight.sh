#!/usr/bin/env bash
# PreToolUse hook (matcher: Workflow|TeamCreate) -- swarm ground-truth pre-flight,
# mechanism 1 of the swarm-verify skill. Reads the hook payload on stdin and
# delegates to preflight.py --hook-emit, which:
#   * is INERT (prints nothing) unless a swarm.config.json exists at/above the cwd
#   * injects a STATE summary as PreToolUse additionalContext (verdict PASS/WARN)
#   * emits a {"decision":"block"} envelope when the config sets enforcement=block
#     AND a hard violation is found (wrong repo / insane clock / required host down)
# Fails open: any error => no output => the swarm launches normally.
# (All JSON logic lives in preflight.py so this stays trivial -- L011.)
set -uo pipefail

PREFLIGHT="$HOME/.claude/skills/swarm-verify/scripts/preflight.py"
[ -f "$PREFLIGHT" ] || exit 0

cat | python "$PREFLIGHT" --hook-emit 2>/dev/null || exit 0
exit 0
