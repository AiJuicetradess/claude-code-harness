#!/bin/bash
# UserPromptSubmit hook: injects current time + skill keyword matches
# Uses a single python call for fast matching (< 1s)

CURRENT_TIME=$(date +"%A, %B %d, %Y at %I:%M %p %Z")

# Read stdin (hook input JSON)
INPUT=$(cat)

# Use Python for fast JSON parsing + keyword matching in one shot
# Note: Python needs Windows-style path, not Git Bash /c/ path
MATCHED_SKILLS=$(echo "$INPUT" | python -c "
import sys, json, os

try:
    hook_input = json.load(sys.stdin)
    prompt = hook_input.get('prompt', '').lower()
    if not prompt:
        sys.exit(0)

    kw_file = os.path.join(os.path.expanduser('~'), '.claude', 'hooks', 'skill-keywords.json')
    with open(kw_file) as f:
        data = json.load(f)

    matched = []
    for skill in data.get('skills', []):
        for kw in skill.get('keywords', []):
            if kw.lower() in prompt:
                matched.append(skill['name'])
                break

    if matched:
        print(', '.join(matched))
except Exception:
    pass
" 2>/dev/null)

# Build output
CONTEXT="Current time: ${CURRENT_TIME}"
if [ -n "$MATCHED_SKILLS" ]; then
  CONTEXT="${CONTEXT}\nSkill keyword match detected: [${MATCHED_SKILLS}]. Consider invoking the matching skill(s) if relevant to the user's request."
fi

CONTEXT_ESCAPED=$(echo -e "$CONTEXT" | sed ':a;N;$!ba;s/\n/\\n/g')
echo "{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptSubmit\",\"additionalContext\":\"${CONTEXT_ESCAPED}\"}}"
