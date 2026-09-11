#!/usr/bin/env python3
"""Audit superpowers plan and spec files in a repository.

Plans are execution scaffolding; specs are the design record. This audit finds
plans whose deliverables already exist on disk (implemented but never retired)
and specs whose status no longer matches reality.

Classification of a plan is derived from the file paths its tasks declare:

    **Files:**
    - Create: `pipeline/dedupe.py`
    - Modify: `pipeline/db.py` (SCHEMA string)
    - Test: `tests/test_dedupe.py`

Create and Test targets are checked for existence under the repo root.
    IMPLEMENTED   >= threshold (default 0.8) of targets exist
    PARTIAL       some targets exist
    UNSTARTED     no target exists
    UNKNOWN       the plan declares no Create/Test targets
    SUPERSEDED    the plan header carries a SUPERSEDED banner

Checkbox ticks are deliberately NOT used: in practice executing-plans and SDD
track progress in a separate ledger and plans keep 0/N boxes ticked forever.

Spec status comes from YAML-style frontmatter (`status: implemented`). Specs are
reported as:
    IMPLEMENTED / SUPERSEDED / ABANDONED   from frontmatter
    ACTIVE        referenced by a PARTIAL or UNSTARTED plan
    UNSYNCED      referenced only by IMPLEMENTED/SUPERSEDED plans and not stamped
                  implemented/superseded/abandoned (a draft/approved status still
                  counts as sync debt)
    UNKNOWN       referenced only by UNKNOWN plans (e.g. SDD task files), no status
    UNTRACKED     no plan references it and no status              (design-only spec)
    MISSING       a plan names it but the file does not exist       (retire would refuse)

Files are read as UTF-8 with a leading BOM dropped; `- Create:` lines inside
fenced code blocks are ignored; a bare (unbackticked) target must look like a
repo-relative path; a bare filename resolves beside the plan's other targets of
the same kind; a markdown-relative spec ref (../specs/x.md) is resolved against
the plan's own directory.

Usage:
    python plan_audit.py [REPO_ROOT] [--json] [--brief] [--strict] [--threshold 0.8] [--no-git]

--brief prints one line (or nothing when clean) for session-start hooks.
--strict exits 1 when any IMPLEMENTED plan or UNSYNCED spec exists.
Output is ASCII only.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

PLANS_DIR = Path("docs/superpowers/plans")
SPECS_DIR = Path("docs/superpowers/specs")
LEDGER_DIR = Path(".superpowers/sdd")

_FILE_LINE = re.compile(r"^\s*-\s*(Create|Modify|Test|Delete)\s*:\s*(.+)$", re.IGNORECASE)
# Inline form: **Files:** Create `a.py` (writer), Modify `b.py`, Test `tests/test_a.py`
_FILES_INLINE = re.compile(r"^\s*(?:-\s*)?\**\s*Files\s*:?\s*\**\s*:?\s*(.+)$", re.IGNORECASE)
# Case-sensitive on purpose: prose such as "to test `b.py` and delete `old/c.py`" is not a declaration.
_INLINE_TARGET = re.compile(r"\b(Create|Modify|Test|Delete)\s*:?\s*`([^`]+)`")
_BACKTICK = re.compile(r"`([^`]+)`")
# A bare (unbackticked) target must look like a repo-relative path: at least one
# slash, not absolute, not a bare number ("- Test: 11. run ..." yields "11.").
_BARE_PATH = re.compile(r"^(?!/)(?![\d.]+$)[\w.-]+(?:/[\w.-]+)+$")
_PATHLIKE_MD = re.compile(r"(?:[\w.-]+/)+[\w.-]+\.md")
_SPEC_LABEL = re.compile(r"^\s*(?:>\s*)?\**\s*spec\b", re.IGNORECASE)
# The banner must lead the line: "> **SUPERSEDED 2026-08-21.**", "# SUPERSEDED", "SUPERSEDED: ...".
# Prose such as "this plan SUPERSEDED the July draft" does not retire a plan.
_SUPERSEDED = re.compile(r"^\s*(?:>\s*)?(?:#+\s*)?\**\s*SUPERSEDED\b")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_BOM = chr(0xFEFF)
HEADER_LINES = 60
_LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_STATUS = re.compile(r"^status\s*:\s*([A-Za-z_-]+)\s*$", re.MULTILINE)


def _clean_path(raw: str) -> str:
    p = raw.strip().strip("'\"")
    p = _LINE_SUFFIX.sub("", p)
    p = p.replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def _read(path: Path) -> str:
    """Read UTF-8 text, dropping a leading BOM (Notepad and PowerShell Set-Content write one)."""
    return path.read_text(encoding="utf-8", errors="replace").lstrip(_BOM)


def _unfenced(text: str) -> list[str]:
    """Lines outside ``` / ~~~ fences. Fenced examples of plan syntax are not declarations."""
    out: list[str] = []
    fence = None
    for line in text.splitlines():
        if _FENCE.match(line):
            marker = line.strip()[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            out.append(line)
    return out


def find_spec_ref(text: str) -> str | None:
    """First spec path named in the plan header.

    Accepts a bold or quoted Spec label with trailing commentary after the
    path, and any header line naming a specs/...md path in backticks or bare.
    """
    lines = _unfenced(text)[:HEADER_LINES]
    fallback = None
    for line in lines:
        candidates = [p for p in _BACKTICK.findall(line) if p.endswith(".md")]
        candidates += [m.group(0) for m in _PATHLIKE_MD.finditer(line)]
        for c in candidates:
            c = _clean_path(c)
            if "specs/" in c:
                return c
        if fallback is None and candidates and _SPEC_LABEL.match(line):
            fallback = _clean_path(candidates[0])
    return fallback


def is_superseded(text: str) -> bool:
    """A plan whose header carries a SUPERSEDED banner is retired as superseded."""
    return any(_SUPERSEDED.search(line) for line in text.splitlines()[:15])


def _looks_like_target(p: str) -> bool:
    """Repo-relative file path: no spaces, not absolute (leading slash or drive colon),
    not a bare number such as a test index, and a directory component or an extension."""
    return bool(p) and " " not in p and ":" not in p and not p.startswith("/") \
        and ("/" in p or "." in p) and not re.fullmatch(r"[\d.]+", p)


def parse_plan(text: str) -> dict:
    """Extract spec reference and declared file targets from a plan body."""
    spec_ref = find_spec_ref(text)
    targets: dict[str, set[str]] = {"create": set(), "modify": set(), "test": set(), "delete": set()}
    for line in _unfenced(text):
        m = _FILE_LINE.match(line)
        if m:
            kind = m.group(1).lower()
            paths = _BACKTICK.findall(m.group(2))
            if not paths:
                # bare path without backticks: the first token, only when it looks like a repo path
                tokens = m.group(2).split()
                paths = [tokens[0]] if tokens and _BARE_PATH.match(_clean_path(tokens[0])) else []
            found = [(kind, p) for p in paths]
        else:
            inline = _FILES_INLINE.match(line)
            found = [(k.lower(), p) for k, p in _INLINE_TARGET.findall(inline.group(1))] if inline else []
        for kind, p in found:
            p = _clean_path(p)
            if _looks_like_target(p):
                targets[kind].add(p)
    return {"spec_ref": spec_ref, "targets": targets}


def frontmatter_status(text: str) -> str | None:
    m = _FRONTMATTER.match(text.lstrip(_BOM))
    if not m:
        return None
    s = _STATUS.search(m.group(1))
    return s.group(1).lower() if s else None


def git_last_commit_date(root: Path, rel: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cs", "--", str(rel)],
            capture_output=True, text=True, timeout=10,
        )
        val = out.stdout.strip()
        return val or None
    except (OSError, subprocess.SubprocessError):
        return None


def ledger_status(root: Path, plan: Path) -> dict | None:
    ledger = root / LEDGER_DIR / plan.stem / "progress.md"
    if not ledger.is_file():
        return None
    text = _read(ledger)
    done = len(re.findall(r"^Task \d+: complete", text, re.MULTILINE))
    return {"path": str(ledger.relative_to(root)).replace("\\", "/"), "tasks_complete": done}


def classify_plan(exists: int, total: int, threshold: float) -> str:
    if total == 0:
        return "UNKNOWN"
    ratio = exists / total
    if ratio >= threshold:
        return "IMPLEMENTED"
    if exists == 0:
        return "UNSTARTED"
    return "PARTIAL"


def resolve_spec_ref(ref: str | None, plan_rel: str) -> str | None:
    """Markdown-relative refs (../specs/x.md) are resolved against the plan's own directory."""
    if ref and ref.startswith(("../", "./")):
        return posixpath.normpath(posixpath.join(posixpath.dirname(plan_rel), ref))
    return ref


def _target_exists(root: Path, p: str, sibling_dirs: list[str]) -> bool:
    """A declared path exists at the root; a bare filename (no directory) may also sit
    beside another declared target of the same kind, e.g. a snapshot named next to
    its sibling snapshot."""
    if (root / p).exists():
        return True
    return "/" not in p and any((root / d / p).exists() for d in sibling_dirs)


def audit(root: Path, threshold: float = 0.8, use_git: bool = True) -> dict:
    root = root.resolve()
    plans_root = root / PLANS_DIR
    specs_root = root / SPECS_DIR
    plans = []
    spec_refs: dict[str, list[dict]] = {}

    if plans_root.is_dir():
        for path in sorted(plans_root.rglob("*.md")):
            rel = path.relative_to(root)
            rel_posix = str(rel).replace("\\", "/")
            text = _read(path)
            parsed = parse_plan(text)
            spec_ref = resolve_spec_ref(parsed["spec_ref"], rel_posix)
            found: set[str] = set()
            absent: set[str] = set()
            for kind in ("create", "test"):
                dirs = sorted({p.rsplit("/", 1)[0] for p in parsed["targets"][kind] if "/" in p})
                for p in parsed["targets"][kind]:
                    (found if _target_exists(root, p, dirs) else absent).add(p)
            existing = sorted(found)
            missing = sorted(absent - found)
            total = len(existing) + len(missing)
            status = "SUPERSEDED" if is_superseded(text) else classify_plan(len(existing), total, threshold)
            entry = {
                "path": rel_posix,
                "status": status,
                "spec": spec_ref,
                "targets": total,
                "existing": len(existing),
                "missing": missing[:10],
                "modify_targets": len(parsed["targets"]["modify"]),
                "last_commit": git_last_commit_date(root, rel) if use_git else None,
                "ledger": ledger_status(root, path),
            }
            plans.append(entry)
            if spec_ref:
                spec_refs.setdefault(spec_ref, []).append(entry)

    specs = []
    if specs_root.is_dir():
        for path in sorted(specs_root.rglob("*.md")):
            rel = str(path.relative_to(root)).replace("\\", "/")
            text = _read(path)
            fm = frontmatter_status(text)
            refs = spec_refs.pop(rel, [])
            statuses = {p["status"] for p in refs}
            if fm in ("implemented", "superseded", "abandoned"):
                status = fm.upper()
            elif statuses & {"PARTIAL", "UNSTARTED"}:
                status = "ACTIVE"
            elif statuses & {"IMPLEMENTED", "SUPERSEDED"}:
                status = "UNSYNCED"  # only finished plans reference it and nothing was reverse-synced
            elif fm:
                status = fm.upper()
            elif refs:
                status = "UNKNOWN"  # referenced only by plans that declare no targets (e.g. SDD task files)
            else:
                status = "UNTRACKED"
            specs.append({
                "path": rel,
                "status": status,
                "frontmatter_status": fm,
                "plans": [p["path"] for p in refs],
                "last_commit": git_last_commit_date(root, path.relative_to(root)) if use_git else None,
            })
    # Plans that name a spec which does not exist: retire would refuse, so surface it now.
    for rel, refs in sorted(spec_refs.items()):
        if not (root / rel).exists():
            specs.append({
                "path": rel,
                "status": "MISSING",
                "frontmatter_status": None,
                "plans": [p["path"] for p in refs],
                "last_commit": None,
            })

    counts_p: dict[str, int] = {}
    for p in plans:
        counts_p[p["status"]] = counts_p.get(p["status"], 0) + 1
    counts_s: dict[str, int] = {}
    for s in specs:
        counts_s[s["status"]] = counts_s.get(s["status"], 0) + 1
    return {
        "root": str(root).replace("\\", "/"),
        "audited_on": date.today().isoformat(),
        "threshold": threshold,
        "plans": plans,
        "specs": specs,
        "summary": {"plans": counts_p, "specs": counts_s},
    }


def brief_line(report: dict) -> str:
    done = report["summary"]["plans"].get("IMPLEMENTED", 0)
    superseded = report["summary"]["plans"].get("SUPERSEDED", 0)
    unsynced = report["summary"]["specs"].get("UNSYNCED", 0)
    missing = report["summary"]["specs"].get("MISSING", 0)
    if not done and not unsynced and not superseded and not missing:
        return ""
    parts = []
    if done:
        parts.append(f"{done} implemented plan(s) still on disk")
    if superseded:
        parts.append(f"{superseded} superseded plan(s) still on disk")
    if unsynced:
        parts.append(f"{unsynced} spec(s) unsynced")
    if missing:
        parts.append(f"{missing} spec(s) missing")
    return "spec-lifecycle: " + ", ".join(parts) + ". Run plan_audit.py for details; retire with the spec-lifecycle skill."


def render(report: dict) -> str:
    lines = [f"Plan/spec audit for {report['root']} (threshold {report['threshold']:.0%})", ""]
    if report["plans"]:
        lines.append("PLANS")
        lines.append(f"  {'status':<12} {'targets':>8}  {'last commit':<11}  path")
        for p in report["plans"]:
            tgt = f"{p['existing']}/{p['targets']}" if p["targets"] else "-"
            lines.append(f"  {p['status']:<12} {tgt:>8}  {p['last_commit'] or '-':<11}  {p['path']}")
    else:
        lines.append("PLANS: none found")
    lines.append("")
    if report["specs"]:
        lines.append("SPECS")
        lines.append(f"  {'status':<12} {'plans':>5}  {'last commit':<11}  path")
        for s in report["specs"]:
            lines.append(f"  {s['status']:<12} {len(s['plans']):>5}  {s['last_commit'] or '-':<11}  {s['path']}")
    else:
        lines.append("SPECS: none found")
    lines.append("")
    lines.append("SUMMARY plans=" + json.dumps(report["summary"]["plans"], sort_keys=True)
                 + " specs=" + json.dumps(report["summary"]["specs"], sort_keys=True))
    b = brief_line(report)
    if b:
        lines.append(b)
    return "\n".join(lines)


def _ascii_safe_stdout() -> None:
    """Piped stdout on Windows is cp1252: a non-ASCII path in a print must degrade, not crash."""
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    _ascii_safe_stdout()
    ap = argparse.ArgumentParser(description="Audit superpowers plans and specs for retirement and sync debt.")
    ap.add_argument("root", nargs="?", default=".", help="repository root (default: cwd)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--brief", action="store_true", help="one-line summary for hooks; prints nothing when clean")
    ap.add_argument("--strict", action="store_true", help="exit 1 when IMPLEMENTED plans or UNSYNCED specs exist")
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--no-git", action="store_true", help="skip git last-commit lookups (faster)")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}")
        return 2
    report = audit(root, threshold=args.threshold, use_git=not (args.no_git or args.brief))

    if args.brief:
        line = brief_line(report)
        if line:
            print(line)
        return 0
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report))
    if args.strict and brief_line(report):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
