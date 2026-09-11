"""Timestamped backup of reflection state before Phase 1 mutations (temp helper)."""
import io
import shutil
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

base = Path.home() / ".claude"
stamp = time.strftime("%Y%m%d-%H%M%S")
dst = base / "reflections" / ("_backup_" + stamp)
dst.mkdir(parents=True, exist_ok=True)

shutil.copy2(base / "reflections" / "session-log.jsonl", dst / "session-log.jsonl")
shutil.copy2(base / "reflections" / "reflection-log.jsonl", dst / "reflection-log.jsonl")
shutil.copytree(base / "lessons", dst / "lessons")

print("backup dir:", dst)
print("session-log lines:", len((dst / "session-log.jsonl").read_text(encoding="utf-8").splitlines()))
print("reflection-log lines:", len((dst / "reflection-log.jsonl").read_text(encoding="utf-8").splitlines()))
print("lessons files copied:", len(list((dst / "lessons").glob("*.md"))))
