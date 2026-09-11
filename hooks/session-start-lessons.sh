#!/usr/bin/env bash
# SessionStart hook: injects LESSONS.md into conversation context.
# Follows the superpowers plugin pattern for hookSpecificOutput.additionalContext.
# No jq dependency — uses sed for JSON field extraction.
set -euo pipefail

LESSONS_FILE="$HOME/.claude/lessons/LESSONS.md"
REFLECTIONS_DIR="$HOME/.claude/reflections"
SESSION_LOG="$REFLECTIONS_DIR/session-log.jsonl"

INPUT=$(cat)
CWD=$(echo "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

# Reuse the superpowers escape_for_json pattern
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

context=""

# Global lessons — inject the Critical tier + a pointer (full set in LESSONS.md / via the drain).
if [ -f "$LESSONS_FILE" ]; then
    header=$(sed -n '1,2p' "$LESSONS_FILE")
    critical=$(awk '/^## Critical$/{f=1;next} /^## /{f=0} f' "$LESSONS_FILE")
    total=$(grep -cE '^- \*\*L' "$LESSONS_FILE" 2>/dev/null || true); total=${total:-0}
    shown=$(printf '%s\n' "$critical" | grep -cE '^- \*\*L' 2>/dev/null || true); shown=${shown:-0}
    more=$(( total - shown ))
    lessons_content="${header}"$'\n'$'\n'"## Critical"$'\n'"${critical}"
    if [ "$more" -gt 0 ]; then
        lessons_content="${lessons_content}"$'\n'"[+${more} more High/Standard lessons — read ~/.claude/lessons/LESSONS.md]"
    fi
    context="<lessons-learned>\n${lessons_content}\n</lessons-learned>"
fi

# Project-specific lessons (encode CWD to match Claude Code's project dir format)
if [ -n "$CWD" ]; then
    PROJECT_ENCODED=$(echo "$CWD" | sed 's|[\\\/: ]|-|g' | sed 's|^-*||')
    PROJECT_LESSONS="$HOME/.claude/projects/${PROJECT_ENCODED}/memory/LESSONS.md"
    if [ -f "$PROJECT_LESSONS" ]; then
        proj_content=$(cat "$PROJECT_LESSONS")
        context="${context}\n<project-lessons>\n${proj_content}\n</project-lessons>"
    fi
fi

# Count unreflected sessions and nudge if needed
unreflected=0
if [ -f "$SESSION_LOG" ]; then
    unreflected=$(grep -cE '"reflected"[[:space:]]*:[[:space:]]*false' "$SESSION_LOG" 2>/dev/null || true)
    unreflected=${unreflected:-0}
fi

# Tiered reflection escalation — FORGE-inspired failure-trigger pattern.
# As unreflected sessions accumulate, escalate from soft nudge → hard demand.
# Rationale: lesson violations climb when reflection cadence falls behind session cadence.
if [ "$unreflected" -gt 200 ]; then
    context="${context}\n<reflection-reminder priority=\"critical\">⚠ ${unreflected} UNREFLECTED SESSIONS — reflection backlog past critical threshold (>200). Run the cursor-based reflection drain in ~/.claude/reflections/: check \`python _mark_reflected.py --count --minable\`, mine minable batches with _batch_prep.py + a tool-less reflection sub-agent → _apply_delta.py → _mark_reflected.py --delta, and clear unmineable sessions with --mark-crons / --mark-no-transcript. (Replaces the retired 5-at-a-time /reflect call.) An unmined backlog drives lesson staleness — drain it before heavy work.</reflection-reminder>"
elif [ "$unreflected" -gt 100 ]; then
    context="${context}\n<reflection-reminder priority=\"high\">${unreflected} unreflected sessions — reflection backlog is high. Strongly consider running the reflection drain (~/.claude/reflections/: _batch_prep.py + a tool-less reflection sub-agent → _apply_delta.py → _mark_reflected.py) before any non-trivial work. Each unmined session is a missed lesson update.</reflection-reminder>"
elif [ "$unreflected" -gt 25 ]; then
    context="${context}\n<reflection-reminder priority=\"medium\">${unreflected} unreflected sessions — consider running /reflect when this task is done. Pattern: violation counts on L001/L013/L004 climb when reflection cadence does not keep up with session cadence.</reflection-reminder>"
elif [ "$unreflected" -gt 4 ]; then
    context="${context}\n<reflection-reminder>There are ${unreflected} unreflected sessions. Consider running /reflect to analyze recent sessions and update lessons.</reflection-reminder>"
fi

# Drain health (lesson L042): surface a repeat-failing or stalled nightly
# reflection drain loudly — silent when healthy, warning line otherwise.
drain_health=$(python "$REFLECTIONS_DIR/_drain_health.py" 2>/dev/null || true)
if [ -n "$drain_health" ]; then
    context="${context}\n<drain-health priority=\"critical\">${drain_health}</drain-health>"
fi

# Skip output if no context to inject
if [ -z "$context" ]; then
    exit 0
fi

escaped=$(escape_for_json "$context")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${escaped}"
  }
}
EOF

exit 0
