"""Tests for retire_plan.py (spec stamping, record append, plan removal, dry-run)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import retire_plan as rp  # noqa: E402

PLAN = "# P\n\n**Spec:** `docs/superpowers/specs/s.md`\n\n**Files:**\n- Create: `src/a.py`\n"


def make(tmp_path: Path, spec_text: str = "# Spec S\n\nBody.\n") -> tuple[Path, Path, Path]:
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True)
    (tmp_path / "docs/superpowers/specs").mkdir(parents=True)
    plan = tmp_path / "docs/superpowers/plans/p.md"
    spec = tmp_path / "docs/superpowers/specs/s.md"
    plan.write_text(PLAN, encoding="utf-8")
    spec.write_text(spec_text, encoding="utf-8")
    return tmp_path, plan, spec


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT_DIR / "retire_plan.py"), *args], capture_output=True, text=True)


def test_upsert_frontmatter_creates_block():
    out = rp.upsert_frontmatter("# T\n", {"status": "implemented"})
    assert out.startswith("---\nstatus: implemented\n---\n\n# T\n")


def test_upsert_frontmatter_updates_existing_key_and_adds_new():
    out = rp.upsert_frontmatter("---\nstatus: draft\nowner: w\n---\n# T\n", {"status": "implemented", "retired_plan": "p.md"})
    assert out.startswith("---\nstatus: implemented\nowner: w\nretired_plan: p.md\n---\n# T\n")


def test_append_record_adds_header_once():
    once = rp.append_record("# T\n", "### rec1\n")
    twice = rp.append_record(once, "### rec2\n")
    assert twice.count(rp.RECORD_HEADER) == 1
    assert "### rec1" in twice and "### rec2" in twice


def test_retire_stamps_spec_and_removes_plan(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    dev = tmp_path / "dev.md"
    dev.write_text("- Used sqlite instead of postgres for the cache.\n", encoding="utf-8")
    r = run([str(plan), "--root", str(root), "--commits", "abc123..def456", "--deviations", str(dev), "--no-git"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert not plan.exists()
    text = spec.read_text(encoding="utf-8")
    assert text.startswith("---\nstatus: implemented\nimplemented_on: ")
    assert "retired_plan: docs/superpowers/plans/p.md" in text
    assert rp.RECORD_HEADER in text
    assert "abc123..def456" in text and "sqlite instead of postgres" in text
    assert "next: git add -A -- docs/superpowers/specs/s.md docs/superpowers/plans/p.md" in r.stdout
    assert r.stdout.isascii()


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          capture_output=True, text=True)


def test_git_mode_stages_the_deletion_even_with_local_edits(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    assert git(root, "init", "-q").returncode == 0
    assert git(root, "add", "-A").returncode == 0
    assert git(root, "commit", "-q", "-m", "init").returncode == 0
    plan.write_text(PLAN + "\n- [x] ticked locally\n", encoding="utf-8")  # unstaged edit: plain git rm refuses
    r = run([str(plan), "--root", str(root)])
    assert r.returncode == 0, r.stdout + r.stderr
    assert not plan.exists()
    status = git(root, "status", "--porcelain").stdout
    assert "D  docs/superpowers/plans/p.md" in status  # staged deletion, not an unstaged one
    # the deletion is already staged, so the printed command must not name the plan
    # (git add on a path git rm already removed exits 128)
    assert "next: git add -A -- docs/superpowers/specs/s.md &&" in r.stdout
    assert git(root, "add", "-A", "--", "docs/superpowers/specs/s.md").returncode == 0


def test_spec_outside_root_is_refused(tmp_path: Path):
    root, plan, spec = make(tmp_path / "repo")
    outside = tmp_path / "outside.md"
    outside.write_text("# outside\n", encoding="utf-8")
    for ref in ("../outside.md", str(outside)):
        r = run([str(plan), "--root", str(root), "--spec", ref, "--no-git"])
        assert r.returncode == 2, r.stdout
        assert plan.exists() and outside.read_text(encoding="utf-8") == "# outside\n"


def test_bom_spec_is_stamped_in_place(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    spec.write_text("---\nstatus: draft\n---\n# S\n", encoding="utf-8-sig")
    r = run([str(plan), "--root", str(root), "--no-git"])
    assert r.returncode == 0, r.stdout + r.stderr
    text = spec.read_text(encoding="utf-8")
    assert chr(0xFEFF) not in text
    assert text.startswith("---\nstatus: implemented\n")
    assert "status: draft" not in text and text.count("\n---\n") == 1


def test_crlf_spec_keeps_crlf(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    spec.write_bytes(b"---\r\nstatus: draft\r\n---\r\n# S\r\n\r\nBody.\r\n")
    r = run([str(plan), "--root", str(root), "--no-git"])
    assert r.returncode == 0, r.stdout + r.stderr
    raw = spec.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    assert raw.startswith(b"---\r\nstatus: implemented\r\n")
    assert rp.RECORD_HEADER.encode() in raw


def test_lf_spec_keeps_lf(tmp_path: Path):
    # write_text on Windows would silently convert an LF spec to CRLF
    root, plan, spec = make(tmp_path)
    spec.write_bytes(b"---\nstatus: draft\n---\n# S\n\nBody.\n")
    r = run([str(plan), "--root", str(root), "--no-git"])
    assert r.returncode == 0, r.stdout + r.stderr
    raw = spec.read_bytes()
    assert b"\r" not in raw
    assert raw.startswith(b"---\nstatus: implemented\n")


def test_untracked_plan_next_command_omits_the_plan(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    assert git(root, "init", "-q").returncode == 0
    assert git(root, "add", "--", "docs/superpowers/specs/s.md").returncode == 0
    assert git(root, "commit", "-q", "-m", "spec only").returncode == 0
    r = run([str(plan), "--root", str(root)])  # plan never tracked: git rm fails, unlink runs
    assert r.returncode == 0 and not plan.exists(), r.stdout + r.stderr
    assert "next: git add -A -- docs/superpowers/specs/s.md &&" in r.stdout
    assert "plans/p.md &&" not in r.stdout
    assert git(root, "add", "-A", "--", "docs/superpowers/specs/s.md").returncode == 0


def test_single_stray_crlf_does_not_flip_an_lf_spec(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    spec.write_bytes(b"---\nstatus: draft\n---\n# S\n\nBody.\r\nMore.\nEnd.\n")
    r = run([str(plan), "--root", str(root), "--no-git"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert b"\r" not in spec.read_bytes()


def test_markdown_relative_spec_ref_resolves(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    plan.write_text("# P\n\n**Spec:** [design](../specs/s.md)\n\n- Create: `src/a.py`\n", encoding="utf-8")
    r = run([str(plan), "--root", str(root), "--no-git"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert not plan.exists() and "status: implemented" in spec.read_text(encoding="utf-8")


def test_non_ascii_plan_name_prints_under_cp1252(tmp_path: Path):
    import os

    root, plan, spec = make(tmp_path)
    odd = plan.with_name("pl" + chr(0x56F3) + "n.md")
    plan.rename(odd)
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    r = subprocess.run([sys.executable, str(SCRIPT_DIR / "retire_plan.py"), str(odd), "--root", str(root), "--no-git"],
                       capture_output=True, env=env, encoding="cp1252", errors="replace")
    assert r.returncode == 0, r.stderr
    assert not odd.exists() and "next: git add" in r.stdout


def test_dry_run_changes_nothing(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    before = spec.read_text(encoding="utf-8")
    r = run([str(plan), "--root", str(root), "--dry-run", "--no-git"])
    assert r.returncode == 0 and "DRY RUN" in r.stdout
    assert plan.exists() and spec.read_text(encoding="utf-8") == before


def test_missing_spec_refuses(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    spec.unlink()
    r = run([str(plan), "--root", str(root), "--no-git"])
    assert r.returncode == 2 and plan.exists()


def test_plan_without_spec_line_needs_flag(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    plan.write_text("# no spec line\n- Create: `src/a.py`\n", encoding="utf-8")
    r = run([str(plan), "--root", str(root), "--no-git"])
    assert r.returncode == 2 and plan.exists()
    r2 = run([str(plan), "--root", str(root), "--spec", "docs/superpowers/specs/s.md", "--no-git"])
    assert r2.returncode == 0 and not plan.exists()


def test_abandoned_status_and_superseded_by(tmp_path: Path):
    root, plan, spec = make(tmp_path)
    r = run([str(plan), "--root", str(root), "--status", "superseded", "--superseded-by", "docs/superpowers/specs/s2.md", "--no-git"])
    assert r.returncode == 0
    text = spec.read_text(encoding="utf-8")
    assert "status: superseded" in text and "superseded_by: docs/superpowers/specs/s2.md" in text
