"""Extract high-signal events from a Claude Code transcript JSONL file."""

import io
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAX_USER = 600
MAX_ERR = 800
MAX_INPUT = 300


def truncate(s, n):
    if not isinstance(s, str):
        try:
            s = json.dumps(s, ensure_ascii=False)
        except Exception:
            s = str(s)
    return s if len(s) <= n else s[:n] + "...[trunc]"


def extract_text(msg):
    """Pull text out of a Claude message content array."""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for c in content:
            if isinstance(c, dict):
                if c.get("type") == "text":
                    chunks.append(c.get("text", ""))
                elif c.get("type") == "tool_result":
                    inner = c.get("content")
                    if isinstance(inner, list):
                        for ic in inner:
                            if isinstance(ic, dict) and ic.get("type") == "text":
                                chunks.append(ic.get("text", ""))
                    elif isinstance(inner, str):
                        chunks.append(inner)
        return "\n".join(chunks)
    return ""


def main():
    src = Path(sys.argv[1])
    sid = src.stem[:8]

    last_tool_use = {}  # tool_use_id -> (tool_name, input_summary)
    user_msgs = []
    errors = []
    pending_assistant_text = ""

    with open(src, "r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            t = obj.get("type")
            if t == "user":
                msg = obj.get("message", {})
                content = msg.get("content")
                # Skip pure tool_result wrapper messages — already captured via errors
                if isinstance(content, list):
                    has_text = any(isinstance(c, dict) and c.get("type") == "text" for c in content)
                    has_tool_result = any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)
                    if has_tool_result and not has_text:
                        # Check for error
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                                tu_id = c.get("tool_use_id")
                                tool_meta = last_tool_use.get(tu_id, {})
                                err_content = c.get("content")
                                if isinstance(err_content, list):
                                    err_text = "\n".join(
                                        x.get("text", "") for x in err_content
                                        if isinstance(x, dict) and x.get("type") == "text"
                                    )
                                else:
                                    err_text = str(err_content) if err_content else ""
                                errors.append({
                                    "line": line_no,
                                    "tool": tool_meta.get("name", "?"),
                                    "input": tool_meta.get("input", ""),
                                    "error": truncate(err_text, MAX_ERR),
                                    "preceded_by_assistant": truncate(pending_assistant_text, 200),
                                })
                        continue
                text = extract_text(msg)
                if text:
                    user_msgs.append({
                        "line": line_no,
                        "text": truncate(text, MAX_USER),
                    })
            elif t == "assistant":
                msg = obj.get("message", {})
                content = msg.get("content")
                if isinstance(content, list):
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") == "text":
                            pending_assistant_text = c.get("text", "")
                        elif c.get("type") == "tool_use":
                            inp = c.get("input", {})
                            try:
                                inp_str = json.dumps(inp, ensure_ascii=False)
                            except Exception:
                                inp_str = str(inp)
                            last_tool_use[c.get("id")] = {
                                "name": c.get("name", "?"),
                                "input": truncate(inp_str, MAX_INPUT),
                            }

    print(f"=== SESSION {sid} ===")
    print(f"USER_MESSAGES: {len(user_msgs)}")
    print(f"ERRORS: {len(errors)}")
    print()
    print("--- USER MESSAGES ---")
    for u in user_msgs:
        print(f"[L{u['line']}] {u['text']}")
        print()
    print("--- ERRORS ---")
    for e in errors:
        print(f"[L{e['line']}] tool={e['tool']}")
        print(f"  input: {e['input']}")
        print(f"  error: {e['error']}")
        if e["preceded_by_assistant"]:
            print(f"  said:  {e['preceded_by_assistant']}")
        print()


if __name__ == "__main__":
    main()
