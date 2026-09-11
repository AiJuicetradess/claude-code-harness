#!/usr/bin/env bash
# Memory synthesizer - manual entry point.
# This script prepares the manifest and run directory, then prints the next step
# (which Claude Code itself executes via the Skill tool / Agent calls).
set -euo pipefail

DATE_STAMP=$(date -u +%Y-%m-%d)
SKILL_DIR="$HOME/.claude/skills/memory-synthesizer"
RUN_DIR="$SKILL_DIR/runs/$DATE_STAMP"

mkdir -p "$RUN_DIR/agent-outputs" "$RUN_DIR/proposed-skills"

python "$SKILL_DIR/build_manifest.py" \
  --session-log "$HOME/.claude/reflections/session-log.jsonl" \
  --output "$RUN_DIR/manifest.json" \
  --n 20

echo "Manifest written: $RUN_DIR/manifest.json"
echo
echo "Next step: invoke the memory-synthesizer skill via Claude Code,"
echo "passing manifest path = $RUN_DIR/manifest.json"
echo "Claude Code will dispatch the 5 parallel subagents and synthesize results."
