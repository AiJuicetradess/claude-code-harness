#!/usr/bin/env python3
"""Retire an implemented plan and reverse-sync its spec.

What it does, in order:
  1. Resolves the plan's spec from its `**Spec:**` line (or --spec).
  2. Stamps the spec's frontmatter: status, implemented_on, retired_plan.
  3. Appends an "## Implementation record" entry to the spec: date, plan path,
     commit range, and the deviations text you supply (what shipped differently
     from the spec and why, plus follow-ups).
  4. Removes the plan file (git rm when the repo is a git checkout, else unlink).

It never commits. It prints the commit command to run next. Use --dry-run to
see every action without touching disk.

Usage:
    python retire_plan.py PLAN_FILE [--root REPO] [--spec SPEC_FILE]
        [--status implemented|abandoned|superseded] [--commits RANGE]
        [--deviations FILE] [--superseded-by SPEC] [--dry-run] [--no-git]

Exit 0 on success, 2 on a resolution error (missing plan, unresolvable spec).
Output is ASCII only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_audit import _BOM, _FRONTMATTER, _ascii_safe_stdout, _read, parse_plan, resolve_spec_ref  # noqa: E402

VALID_STATUS = ("implemented", "abandoned", "superseded")
RECORD_HEADER = "## Implementation record"


def _is_git_repo(root: Path) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0 and r.stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def upsert_frontmatter(text: str, fields: dict[str, str]) -> str:
    """Set keys in the leading YAML block, creating the block when absent."""
    m = _FRONTMATTER.match(text)
    if m:
        body = m.group(1)
        lines = body.split("\n")
        seen = set()
        for i, line in enumerate(lines):
            key = line.split(":", 1)[0].strip()
            if key in fields:
                lines[i] = f"{key}: {fields[key]}"
                seen.add(key)
        for key, value in fields.items():
            if key not in seen:
                lines.append(f"{key}: {value}")
        new_block = "---\n" + "\n".join(lines).rstrip("\r") + "\n---\n"
        return new_block + text[m.end():]
    block = "---\n" + "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\n---\n\n"
    return block + text


def build_record(today: str, plan_rel: str, status: str, commits: str | None, deviations: str | None,
                 superseded_by: str | None) -> str:
    lines = [f"### {today} - {status}", "", f"- Plan: `{plan_rel}` (retired; content remains in git history)"]
    if commits:
        lines.append(f"- Commits: `{commits}`")
    if superseded_by:
        lines.append(f"- Superseded by: `{superseded_by}`")
    lines.append("")
    lines.append("**Deviations from spec:**")
    lines.append("")
    lines.append(deviations.strip() if deviations and deviations.strip() else "None recorded.")
    lines.append("")
    return "\n".join(lines)


def append_record(text: str, record: str) -> str:
    text = text.rstrip("\n") + "\n"
    if RECORD_HEADER in text:
        return text + "\n" + record
    return text + "\n" + RECORD_HEADER + "\n\n" + record


def main(argv: list[str] | None = None) -> int:
    _ascii_safe_stdout()
    ap = argparse.ArgumentParser(description="Retire an implemented plan and reverse-sync its spec.")
    ap.add_argument("plan")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    ap.add_argument("--spec", help="spec path relative to root; overrides the plan's **Spec:** line")
    ap.add_argument("--status", default="implemented", choices=VALID_STATUS)
    ap.add_argument("--commits", help="commit range or list recorded in the spec, e.g. abc123..def456")
    ap.add_argument("--deviations", help="file whose text becomes the deviations section")
    ap.add_argument("--superseded-by", help="spec path that replaces this one (with --status superseded)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-git", action="store_true", help="unlink the plan instead of git rm")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    plan = Path(args.plan)
    if not plan.is_absolute():
        plan = (root / plan).resolve()
    if not plan.is_file():
        print(f"ERROR: plan not found: {plan}")
        return 2
    try:
        plan_rel = plan.relative_to(root).as_posix()
    except ValueError:
        print(f"ERROR: plan {plan} is outside root {root}")
        return 2

    plan_text = _read(plan)
    spec_ref = args.spec or resolve_spec_ref(parse_plan(plan_text)["spec_ref"], plan_rel)
    if not spec_ref:
        print("ERROR: plan has no **Spec:** line; pass --spec")
        return 2
    spec = Path(spec_ref)
    spec = (spec if spec.is_absolute() else root / spec).resolve()
    try:
        spec_rel = spec.relative_to(root).as_posix()
    except ValueError:
        print(f"ERROR: spec {spec_ref} resolves outside root {root}")
        return 2
    if not spec.is_file():
        print(f"ERROR: spec not found: {spec_rel}")
        return 2

    deviations = None
    if args.deviations:
        dev_path = Path(args.deviations)
        if not dev_path.is_file():
            print(f"ERROR: deviations file not found: {dev_path}")
            return 2
        deviations = _read(dev_path)

    today = date.today().isoformat()
    fields = {"status": args.status, f"{args.status}_on": today, "retired_plan": plan_rel}
    if args.superseded_by:
        fields["superseded_by"] = args.superseded_by
    # Work in LF, then restore the file's dominant line ending so a CRLF spec stays
    # CRLF and an LF spec stays LF on Windows (write_text would convert to CRLF).
    # A lone stray CRLF is normalised to the majority instead of flipping the file.
    raw = spec.read_bytes().decode("utf-8", errors="replace").lstrip(_BOM)
    crlf = raw.count("\r\n")
    eol = "\r\n" if crlf > raw.count("\n") - crlf else "\n"
    new_spec = append_record(upsert_frontmatter(raw.replace("\r\n", "\n"), fields),
                             build_record(today, plan_rel, args.status, args.commits, deviations, args.superseded_by))
    if eol != "\n":
        new_spec = new_spec.replace("\n", eol)

    use_git = not args.no_git and _is_git_repo(root)
    actions = [
        f"update spec {spec_rel}: frontmatter {fields}; append implementation record",
        f"remove plan {plan_rel} via {'git rm' if use_git else 'unlink'}",
    ]
    if args.dry_run:
        print("DRY RUN - no changes made")
        for a in actions:
            print("  would " + a)
        return 0

    with open(spec, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_spec)
    if use_git:
        # -f: a plan with local edits is still retired; its committed content stays in history.
        r = subprocess.run(["git", "-C", str(root), "rm", "-f", "-q", "--", plan_rel], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"WARN: git rm failed ({r.stderr.strip()}); unlinking instead")
            os.remove(plan)
    else:
        os.remove(plan)
    for a in actions:
        print("done: " + a)
    # In git mode the deletion is already staged (or the plan was never tracked), so only
    # the spec needs staging; with --no-git the plan path is included so a tracked plan's
    # deletion gets staged too.
    stage = spec_rel if use_git else spec_rel + " " + plan_rel
    print("next: git add -A -- " + stage + " && git commit -m \"chore(spec): retire plan "
          + Path(plan_rel).name + "; mark spec " + args.status + "\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
