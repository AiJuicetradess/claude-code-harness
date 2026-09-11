#!/usr/bin/env bash
# grok-dispatch.sh — THE dispatch path for SDD implementer seats.
# Pins the house seat standard (~/.claude/CLAUDE.md "SDD seat standard"):
#   grok-4.6, xhigh reasoning, bypassPermissions, prompt read from a FILE.
#
# Why this exists: PowerShell 5.1 splits argv on embedded double quotes inside
# -p "<prompt>" (observed in practice: exit 2, "unrecognized
# subcommand"), and dispatch strings had drifted into 4 variants across
# projects. Run this from the Bash tool ONLY.
#
# Usage:
#   grok-dispatch.sh <prompt-file> <repo-cwd> [extra grok args...]
# Examples:
#   grok-dispatch.sh .superpowers/sdd/plan/task-3-brief.md /c/Users/you/repo
#   grok-dispatch.sh brief.md /c/repo --resume <sessionId>
# Exit code: grok's own exit code (2 = CLI usage error, check argv).

set -u

if [ $# -lt 2 ]; then
  echo "usage: grok-dispatch.sh <prompt-file> <repo-cwd> [extra grok args...]" >&2
  exit 64
fi

PROMPT_FILE="$1"
REPO_CWD="$2"
shift 2

if [ ! -f "$PROMPT_FILE" ]; then
  echo "grok-dispatch: prompt file not found: $PROMPT_FILE" >&2
  exit 66
fi
if [ ! -s "$PROMPT_FILE" ]; then
  echo "grok-dispatch: prompt file is EMPTY: $PROMPT_FILE" >&2
  exit 66
fi
if [ ! -d "$REPO_CWD" ]; then
  echo "grok-dispatch: cwd not a directory: $REPO_CWD" >&2
  exit 66
fi

GROK="$HOME/.grok/bin/grok.exe"
if [ ! -x "$GROK" ]; then
  GROK="$(command -v grok || true)"
fi
if [ -z "$GROK" ]; then
  echo "grok-dispatch: grok CLI not found (~/.grok/bin/grok.exe)" >&2
  exit 69
fi

"$GROK" -p "$(cat "$PROMPT_FILE")" \
  --model grok-4.6 \
  --reasoning-effort xhigh \
  --permission-mode bypassPermissions \
  --cwd "$REPO_CWD" \
  "$@"
rc=$?
echo "grok-dispatch: exit=$rc prompt=$PROMPT_FILE cwd=$REPO_CWD" >&2
exit $rc
