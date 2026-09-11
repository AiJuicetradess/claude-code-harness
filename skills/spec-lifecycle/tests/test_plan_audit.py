"""Tests for plan_audit.py classification and reporting."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import plan_audit as pa  # noqa: E402

PLAN_TEMPLATE = """# {name} Implementation Plan

**Spec:** `{spec}`

### Task 1: thing

**Files:**
- Create: `{create1}`
- Create: `{create2}`
- Modify: `src/existing.py` (top of file)
- Test: `{test1}`

- [ ] **Step 1: Write the failing test**
"""


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True)
    (tmp_path / "docs/superpowers/specs").mkdir(parents=True)
    return tmp_path


def write_plan(root: Path, name: str, spec: str, create1: str, create2: str, test1: str) -> Path:
    p = root / "docs/superpowers/plans" / f"{name}.md"
    p.write_text(PLAN_TEMPLATE.format(name=name, spec=spec, create1=create1, create2=create2, test1=test1), encoding="utf-8")
    return p


def touch(root: Path, rel: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x", encoding="utf-8")


def test_parse_plan_extracts_spec_and_targets():
    text = PLAN_TEMPLATE.format(name="a", spec="docs/superpowers/specs/a.md", create1="src/a.py",
                                create2="src/b.py", test1="tests/test_a.py")
    parsed = pa.parse_plan(text)
    assert parsed["spec_ref"] == "docs/superpowers/specs/a.md"
    assert parsed["targets"]["create"] == {"src/a.py", "src/b.py"}
    assert parsed["targets"]["test"] == {"tests/test_a.py"}
    assert parsed["targets"]["modify"] == {"src/existing.py"}


def test_parse_plan_handles_line_suffixes_and_multiple_backticks():
    text = "- Modify: `src/postcall/inbound.ts:138-144` (`hasNonSentinelPositiveQual`)\n- Test: `tests/a.test.ts` (new), `tests/b.test.ts` (append)\n"
    parsed = pa.parse_plan(text)
    assert parsed["targets"]["modify"] == {"src/postcall/inbound.ts"}
    assert parsed["targets"]["test"] == {"tests/a.test.ts", "tests/b.test.ts"}


def test_classification_thresholds():
    assert pa.classify_plan(0, 0, 0.8) == "UNKNOWN"
    assert pa.classify_plan(0, 3, 0.8) == "UNSTARTED"
    assert pa.classify_plan(1, 3, 0.8) == "PARTIAL"
    assert pa.classify_plan(3, 3, 0.8) == "IMPLEMENTED"
    assert pa.classify_plan(4, 5, 0.8) == "IMPLEMENTED"


def test_audit_classifies_plans_and_specs(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/done.md").write_text("# Done spec\n", encoding="utf-8")
    (root / "docs/superpowers/specs/wip.md").write_text("# WIP spec\n", encoding="utf-8")
    (root / "docs/superpowers/specs/lonely.md").write_text("# Lonely spec\n", encoding="utf-8")
    (root / "docs/superpowers/specs/stamped.md").write_text("---\nstatus: implemented\n---\n# Stamped\n", encoding="utf-8")
    write_plan(root, "done-plan", "docs/superpowers/specs/done.md", "src/d1.py", "src/d2.py", "tests/test_d.py")
    write_plan(root, "wip-plan", "docs/superpowers/specs/wip.md", "src/w1.py", "src/w2.py", "tests/test_w.py")
    write_plan(root, "new-plan", "docs/superpowers/specs/wip.md", "src/n1.py", "src/n2.py", "tests/test_n.py")
    for rel in ("src/d1.py", "src/d2.py", "tests/test_d.py", "src/w1.py"):
        touch(root, rel)

    report = pa.audit(root, use_git=False)
    by_plan = {p["path"].split("/")[-1]: p["status"] for p in report["plans"]}
    assert by_plan == {"done-plan.md": "IMPLEMENTED", "wip-plan.md": "PARTIAL", "new-plan.md": "UNSTARTED"}
    by_spec = {s["path"].split("/")[-1]: s["status"] for s in report["specs"]}
    assert by_spec == {"done.md": "UNSYNCED", "wip.md": "ACTIVE", "lonely.md": "UNTRACKED", "stamped.md": "IMPLEMENTED"}
    assert report["summary"]["plans"]["IMPLEMENTED"] == 1
    assert "1 implemented plan(s) still on disk" in pa.brief_line(report)
    assert "1 spec(s) unsynced" in pa.brief_line(report)


def test_brief_is_empty_when_clean(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/wip.md").write_text("# WIP\n", encoding="utf-8")
    write_plan(root, "new-plan", "docs/superpowers/specs/wip.md", "src/n1.py", "src/n2.py", "tests/test_n.py")
    report = pa.audit(root, use_git=False)
    assert pa.brief_line(report) == ""


def test_audit_never_writes(tmp_path: Path):
    root = make_repo(tmp_path)
    write_plan(root, "p", "docs/superpowers/specs/s.md", "src/a.py", "src/b.py", "tests/t.py")
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    pa.audit(root, use_git=False)
    after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    assert before == after


def test_cli_modes(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/done.md").write_text("# Done\n", encoding="utf-8")
    write_plan(root, "done-plan", "docs/superpowers/specs/done.md", "src/d1.py", "src/d2.py", "tests/test_d.py")
    for rel in ("src/d1.py", "src/d2.py", "tests/test_d.py"):
        touch(root, rel)
    script = str(SCRIPT_DIR / "plan_audit.py")
    r = subprocess.run([sys.executable, script, str(root), "--json", "--no-git"], capture_output=True, text=True)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["plans"][0]["status"] == "IMPLEMENTED"
    strict = subprocess.run([sys.executable, script, str(root), "--strict", "--no-git"], capture_output=True, text=True)
    assert strict.returncode == 1 and strict.stdout.isascii()
    brief = subprocess.run([sys.executable, script, str(root), "--brief"], capture_output=True, text=True)
    assert brief.returncode == 0 and brief.stdout.startswith("spec-lifecycle:")
    missing = subprocess.run([sys.executable, script, str(root / "nope")], capture_output=True, text=True)
    assert missing.returncode == 2


def test_repo_without_superpowers_dirs_is_clean(tmp_path: Path):
    report = pa.audit(tmp_path, use_git=False)
    assert report["plans"] == [] and report["specs"] == []
    assert pa.brief_line(report) == ""


def test_find_spec_ref_tolerates_real_world_phrasings():
    cases = {
        "**Spec:** `docs/superpowers/specs/a.md` (rev 2.2, gate complete). Binding.\n": "docs/superpowers/specs/a.md",
        "**Spec:** `docs/superpowers/specs/b.md`.\n": "docs/superpowers/specs/b.md",
        "> Spec: docs/superpowers/specs/c-design.md (decisions + validation contract).\n": "docs/superpowers/specs/c-design.md",
        "**Tech Stack:** Python 3.11. Spec: `docs/superpowers/specs/d.md`.\n": "docs/superpowers/specs/d.md",
        "**Goal:** Build `src/x.py` per `docs/superpowers/specs/e.md`\n": "docs/superpowers/specs/e.md",
        "**Spec:** `docs/superpowers/specs/f.md` section 5 + section 8 step 7.\n": "docs/superpowers/specs/f.md",
        "# Plan with no spec\n- Create: `src/a.py`\n": None,
    }
    for text, expected in cases.items():
        assert pa.find_spec_ref(text) == expected, text


def test_superseded_banner_classifies_plan(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/s.md").write_text("# S\n", encoding="utf-8")
    p = write_plan(root, "old-plan", "docs/superpowers/specs/s.md", "src/a.py", "src/b.py", "tests/t.py")
    p.write_text("> **SUPERSEDED 2026-08-21.** Do not execute these tasks.\n\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
    report = pa.audit(root, use_git=False)
    assert report["plans"][0]["status"] == "SUPERSEDED"
    assert report["specs"][0]["status"] == "UNSYNCED"
    assert "1 superseded plan(s) still on disk" in pa.brief_line(report)


def test_clean_path_keeps_dot_directories():
    assert pa._clean_path("./.github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert pa._clean_path("./src/a.py:12-14") == "src/a.py"


def test_superseded_banner_must_lead_the_line():
    assert pa.is_superseded("> **SUPERSEDED 2026-08-21.** Do not execute.\n")
    assert pa.is_superseded("# SUPERSEDED by the v2 plan\n")
    assert pa.is_superseded("SUPERSEDED: see 2026-09-01-v2.md\n")
    assert not pa.is_superseded("This plan SUPERSEDED the July draft; execute it.\n")


def test_fenced_file_lines_are_not_targets():
    text = "**Files:**\n- Create: `src/real.py`\n\n```markdown\n**Files:**\n- Create: `src/example.py`\n- Test: `tests/test_example.py`\n```\n"
    parsed = pa.parse_plan(text)
    assert parsed["targets"]["create"] == {"src/real.py"}
    assert parsed["targets"]["test"] == set()


def test_inline_files_format_is_parsed():
    text = "**Files:** Create `ops/build_report.py` (writer), Modify `ops/db.py`, Create `tests/test_report.py`\n"
    parsed = pa.parse_plan(text)
    assert parsed["targets"]["create"] == {"ops/build_report.py", "tests/test_report.py"}
    assert parsed["targets"]["modify"] == {"ops/db.py"}


def test_bare_tokens_must_look_like_repo_paths():
    text = "- Test: 11. run the suite\n- Test: /health returns 200\n- Test: push-agent.ts manually\n- Create: src/new.py (bare, no backticks)\n"
    parsed = pa.parse_plan(text)
    assert parsed["targets"]["test"] == set()
    assert parsed["targets"]["create"] == {"src/new.py"}


def test_backticked_junk_is_ignored():
    text = ("- Test: boot and hit `/health` (explicit run steps below)\n"
            "- Test: `tests/relay/session.test.ts` (insert after test `11.`, which ends at line 547)\n"
            "- Create: `C:/abs/elsewhere.py`\n")
    parsed = pa.parse_plan(text)
    assert parsed["targets"]["test"] == {"tests/relay/session.test.ts"}
    assert parsed["targets"]["create"] == set()


def test_bare_filename_resolves_beside_sibling_targets(tmp_path: Path):
    root = make_repo(tmp_path)
    plan = root / "docs/superpowers/plans/snap.md"
    plan.write_text("# Snap\n\n**Files:**\n- Modify: `src/agent/prompt.ts`\n"
                    "- Test: `tests/agent/__snapshots__/config.test.ts.snap` and `config-inbound.test.ts.snap`\n"
                    "- Test: `push-agent.ts` run manually\n", encoding="utf-8")
    for rel in ("src/agent/prompt.ts", "tests/agent/__snapshots__/config.test.ts.snap",
                "tests/agent/__snapshots__/config-inbound.test.ts.snap"):
        touch(root, rel)
    report = pa.audit(root, use_git=False)
    entry = report["plans"][0]
    assert entry["existing"] == 2 and entry["targets"] == 3
    assert entry["missing"] == ["push-agent.ts"]  # not at the root nor beside any declared target


def test_inline_targets_are_case_sensitive():
    text = "**Files:** Create `src/a.py` to test `src/b.py` and delete `old/c.py`\n"
    parsed = pa.parse_plan(text)
    assert parsed["targets"]["create"] == {"src/a.py"}
    assert parsed["targets"]["test"] == set() and parsed["targets"]["delete"] == set()


def test_bare_filenames_resolve_only_beside_same_kind_targets(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/plans/p.md").write_text(
        "# P\n\n**Files:**\n- Modify: `tests/test_x.py`\n- Create: `config.json`\n- Create: `__init__.py`\n", encoding="utf-8")
    for rel in ("tests/test_x.py", "tests/config.json", "tests/__init__.py"):
        touch(root, rel)
    report = pa.audit(root, use_git=False)
    assert report["plans"][0]["status"] == "UNSTARTED"  # the Create names only exist beside a Modify target


def test_markdown_relative_spec_refs_resolve_against_the_plan(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/s.md").write_text("# S\n", encoding="utf-8")
    (root / "docs/superpowers/plans/p.md").write_text(
        "# P\n\n**Spec:** [design](../specs/s.md)\n\n- Create: `src/a.py`\n", encoding="utf-8")
    sub = root / "docs/superpowers/plans/sdd-p/task-1.md"
    sub.parent.mkdir()
    sub.write_text("# T1\n\n> Spec: ../../specs/s.md\n", encoding="utf-8")
    report = pa.audit(root, use_git=False)
    assert {p["spec"] for p in report["plans"]} == {"docs/superpowers/specs/s.md"}
    assert {s["path"]: s["status"] for s in report["specs"]} == {"docs/superpowers/specs/s.md": "ACTIVE"}


def test_bom_files_are_read(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/stamped.md").write_text("---\nstatus: implemented\n---\n# S\n", encoding="utf-8-sig")
    p = write_plan(root, "done-plan", "docs/superpowers/specs/stamped.md", "src/d1.py", "src/d2.py", "tests/test_d.py")
    p.write_text(p.read_text(encoding="utf-8"), encoding="utf-8-sig")
    for rel in ("src/d1.py", "src/d2.py", "tests/test_d.py"):
        touch(root, rel)
    report = pa.audit(root, use_git=False)
    assert report["plans"][0]["status"] == "IMPLEMENTED"
    assert report["plans"][0]["spec"] == "docs/superpowers/specs/stamped.md"
    assert report["specs"][0]["status"] == "IMPLEMENTED"


def test_unknown_task_files_do_not_keep_a_spec_active(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/s.md").write_text("# S\n", encoding="utf-8")
    write_plan(root, "main-plan", "docs/superpowers/specs/s.md", "src/a.py", "src/b.py", "tests/test_a.py")
    for rel in ("src/a.py", "src/b.py", "tests/test_a.py"):
        touch(root, rel)
    task = root / "docs/superpowers/plans/sdd-main-2026-09-01/task-1.md"
    task.parent.mkdir(parents=True)
    task.write_text("# Task 1\n\n**Spec:** `docs/superpowers/specs/s.md`\n\nDo the thing.\n", encoding="utf-8")
    report = pa.audit(root, use_git=False)
    by_plan = {p["path"].split("/")[-1]: p["status"] for p in report["plans"]}
    assert by_plan == {"main-plan.md": "IMPLEMENTED", "task-1.md": "UNKNOWN"}
    assert report["specs"][0]["status"] == "UNSYNCED"


def test_spec_referenced_only_by_unknown_plans_is_unknown(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "docs/superpowers/specs/s.md").write_text("# S\n", encoding="utf-8")
    (root / "docs/superpowers/plans/vague.md").write_text("# Vague\n\n**Spec:** `docs/superpowers/specs/s.md`\n", encoding="utf-8")
    report = pa.audit(root, use_git=False)
    assert report["specs"][0]["status"] == "UNKNOWN"
    assert pa.brief_line(report) == ""


def test_non_ascii_root_prints_under_cp1252(tmp_path: Path):
    import os

    root = make_repo(tmp_path / ("r" + chr(0x56F3) + "po"))
    write_plan(root, "p", "docs/superpowers/specs/s.md", "src/a.py", "src/b.py", "tests/t.py")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    r = subprocess.run([sys.executable, str(SCRIPT_DIR / "plan_audit.py"), str(root), "--no-git"],
                       capture_output=True, env=env, encoding="cp1252", errors="replace")
    assert r.returncode == 0 and r.stdout.startswith("Plan/spec audit for"), r.stderr


def test_missing_spec_gets_a_row(tmp_path: Path):
    root = make_repo(tmp_path)
    write_plan(root, "orphan-plan", "docs/superpowers/specs/nope.md", "src/a.py", "src/b.py", "tests/test_a.py")
    report = pa.audit(root, use_git=False)
    rows = {s["path"]: s["status"] for s in report["specs"]}
    assert rows == {"docs/superpowers/specs/nope.md": "MISSING"}
    assert report["specs"][0]["plans"] == ["docs/superpowers/plans/orphan-plan.md"]
    assert "1 spec(s) missing" in pa.brief_line(report)
