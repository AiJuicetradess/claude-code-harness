"""Apply a reflection lesson-delta to the lessons/ dir (updates + new files).

Usage: python _apply_delta.py DELTA.json
Updates increment times_violated, bump last_triggered, append evidence bullets.
New lessons are written with the standard frontmatter+body schema. _regen_lessons.py
runs afterward to auto-promote/sort and rebuild LESSONS.md.
"""
import io
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LESSONS = Path.home() / ".claude" / "lessons"
TODAY = "2026-06-14"
delta = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))


def find_file(lid):
    hits = sorted(LESSONS.glob(lid + "-*.md"))
    return hits[0] if hits else None


def set_fm(text, key, val):
    pat = re.compile(r'^(%s:\s*).*$' % re.escape(key), re.MULTILINE)
    if pat.search(text):
        return pat.sub(lambda m: m.group(1) + str(val), text, count=1)
    return re.sub(r'\n---\n', '\n%s: %s\n---\n' % (key, val), text, count=1)


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:40]


updated_ids, created_ids = [], []

for upd in delta.get("lessons_updated", []):
    lid = upd["id"]
    p = find_file(lid)
    if not p:
        print("WARN: no file for", lid)
        continue
    t = p.read_text(encoding="utf-8")
    m = re.search(r'^times_violated:\s*(\d+)', t, re.MULTILINE)
    cur = int(m.group(1)) if m else 0
    newv = cur + int(upd.get("new_violations", 0))
    t = set_fm(t, "times_violated", newv)
    if upd.get("latest_date"):
        t = set_fm(t, "last_triggered", upd["latest_date"])
    ev = upd.get("evidence", [])
    if ev:
        t = t.rstrip("\n") + "\n" + "\n".join("- " + e for e in ev) + "\n"
    p.write_text(t, encoding="utf-8")
    updated_ids.append(lid)
    print("updated %s  violated %d -> %d  (+%d evidence)" % (lid, cur, newv, len(ev)))

for new in delta.get("lessons_created", []):
    lid = new["id"]
    fn = new.get("filename") or ("%s-%s.md" % (lid, slugify(new["title"])))
    p = LESSONS / fn
    fm = [
        "---",
        "id: " + lid,
        'title: "%s"' % new["title"].replace('"', "'"),
        "category: " + new.get("category", "tool-usage"),
        "severity: " + new.get("severity", "standard"),
        "status: active",
        "created: " + new.get("created", TODAY),
        "last_triggered: " + new.get("last_triggered", new.get("created", TODAY)),
        "times_violated: %d" % int(new.get("times_violated", 1)),
        "times_checked: 0",
        "tags: [%s]" % ", ".join(new.get("tags", [])),
        "related_skills: [%s]" % ", ".join(new.get("related_skills", [])),
        "---",
        "",
    ]
    body = ["**Rule:** " + new["rule"] + "\n", "**Why:** " + new.get("why", "") + "\n"]
    if new.get("prevention"):
        body.append("**Prevention:**")
        for i, pv in enumerate(new["prevention"], 1):
            body.append("%d. %s" % (i, re.sub(r'^\d+\.\s*', '', pv)))
        body.append("")
    if new.get("evidence"):
        body.append("**Evidence:**")
        for e in new["evidence"]:
            body.append("- " + e)
        body.append("")
    p.write_text("\n".join(fm) + "\n".join(body) + "\n", encoding="utf-8")
    created_ids.append(lid)
    print("created %s -> %s" % (lid, p.name))

print(json.dumps({"updated": updated_ids, "created": created_ids}))
