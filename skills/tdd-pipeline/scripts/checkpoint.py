#!/usr/bin/env python
"""
checkpoint.py -- the regression-firewall primitive of the tdd-pipeline skill.

Captures a content snapshot of a fixer's in-scope files BEFORE it runs, and restores
them if the fixer introduces a regression (a previously-green test goes red). Uses
plain file copies under <state_dir>/snapshot/<id> -- NOT git history rewrites -- so it
works identically in git / worktree / non-git trees and never touches git history or
trips a destructive-git guard.

SAFETY: 'protect' paths (secrets/artifacts from the manifest) and, in git_mode=git,
gitignored files are NEVER snapshotted AND NEVER deleted on restore.

Subcommands:
  snapshot --id ID --paths P [P ...]   save in-scope paths
  restore  --id ID [--paths P ...]     restore them (copy back; delete fixer-added files)
  changed                              list files changed in the work tree (git modes only)
  list                                 list snapshot ids

stdlib only. Windows-safe: 'python', ASCII output, utf-8-sig manifest reads, paths with spaces.
Exit: 0 ok, 1 error.
"""
import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time

MANIFEST_NAME = "tdd.config.json"
PRUNE = (".git", ".tdd", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache")


def _reconfig():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_manifest(start):
    d = os.path.abspath(start)
    seen = set()
    while d and d not in seen:
        seen.add(d)
        p = os.path.join(d, MANIFEST_NAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def load_manifest(root):
    p = find_manifest(root)
    if not p:
        return {}, None
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            return json.load(f), p
    except Exception:
        return {}, p


def run_git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=30)
        return r.returncode, r.stdout.decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def is_protected(rel, protect):
    base = os.path.basename(rel)
    rel_posix = rel.replace("\\", "/")
    for g in protect:
        if fnmatch.fnmatch(rel_posix, g) or fnmatch.fnmatch(base, g):
            return True
    return False


def git_ignored(root, rel):
    # git check-ignore wants forward slashes; os.path.relpath yields backslashes on Windows (L003)
    rc, _ = run_git(["check-ignore", "-q", rel.replace("\\", "/")], root)
    return rc == 0


def iter_files(root, path):
    """Yield rel-to-root paths for a path that may be a file or a directory."""
    abs_p = os.path.join(root, path)
    if os.path.isfile(abs_p):
        yield path
    elif os.path.isdir(abs_p):
        for dirpath, dirs, files in os.walk(abs_p):
            dirs[:] = [d for d in dirs if d not in PRUNE]
            for fn in files:
                yield os.path.relpath(os.path.join(dirpath, fn), root)


def _excluded(root, rel, protect, git_mode):
    if is_protected(rel, protect):
        return True
    if git_mode in ("git", "worktree") and git_ignored(root, rel):
        return True
    return False


def snap_dir(state_dir, sid):
    return os.path.join(state_dir, "snapshot", sid)


def _within_scope(rel, scope_paths):
    rp = rel.replace("\\", "/")
    for s in scope_paths:
        sp = s.replace("\\", "/").rstrip("/")
        if rp == sp or rp.startswith(sp + "/"):
            return True
    return False


def cmd_snapshot(root, manifest, state_dir, sid, paths):
    protect = manifest.get("protect", [])
    git_mode = (manifest.get("git_mode") or "snapshot").lower()
    sd = snap_dir(state_dir, sid)
    saved, skipped = [], []
    for p in paths:
        for rel in iter_files(root, p):
            if _excluded(root, rel, protect, git_mode):
                skipped.append(rel)
                continue
            dst = os.path.join(sd, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(root, rel), dst)
            saved.append(rel)
    os.makedirs(sd, exist_ok=True)
    meta = {"id": sid, "root": root, "paths": paths, "scope_files": saved,
            "skipped_protected_or_ignored": skipped, "ts": int(time.time())}
    with open(os.path.join(sd, "_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=True, indent=2)
    return {"ok": True, "id": sid, "saved": len(saved), "skipped": len(skipped), "dir": sd}


def cmd_restore(root, manifest, state_dir, sid, paths):
    protect = manifest.get("protect", [])
    git_mode = (manifest.get("git_mode") or "snapshot").lower()
    sd = snap_dir(state_dir, sid)
    metap = os.path.join(sd, "_snapshot.json")
    if not os.path.isfile(metap):
        return {"ok": False, "error": "no snapshot '%s'" % sid}
    with open(metap, "r", encoding="utf-8-sig") as f:
        meta = json.load(f)
    scope_paths = paths if paths else meta.get("paths", [])
    saved_set = set(meta.get("scope_files", []))
    restored, removed = [], []
    # 1. copy back every saved file within the requested scope
    for rel in saved_set:
        if scope_paths and not _within_scope(rel, scope_paths):
            continue
        src = os.path.join(sd, rel)
        if os.path.isfile(src):
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(rel)
    # 2. delete fixer-ADDED files (present now, not in snapshot) -- but never protected/ignored
    for p in scope_paths:
        for rel in iter_files(root, p):
            if rel in saved_set:
                continue
            if _excluded(root, rel, protect, git_mode):
                continue
            try:
                os.remove(os.path.join(root, rel))
                removed.append(rel)
            except Exception:
                pass
    return {"ok": True, "id": sid, "restored": len(restored),
            "removed": len(removed), "removed_files": removed[:50]}


def cmd_changed(root, manifest):
    git_mode = (manifest.get("git_mode") or "snapshot").lower()
    if git_mode not in ("git", "worktree"):
        return {"ok": False, "error": "changed requires git_mode git/worktree"}
    rc, out = run_git(["status", "--porcelain"], root)
    if rc != 0:
        return {"ok": False, "error": "git status failed", "detail": out[:300]}
    changed = [line[3:].strip().strip('"') for line in out.splitlines() if len(line) > 3]
    return {"ok": True, "changed": changed}


def main():
    _reconfig()
    ap = argparse.ArgumentParser(description="tdd-pipeline regression-firewall checkpoint")
    ap.add_argument("cmd", choices=["snapshot", "restore", "changed", "list"])
    ap.add_argument("--root", default=".")
    ap.add_argument("--id")
    ap.add_argument("--paths", nargs="*", default=[])
    ap.add_argument("--state-dir", help="override manifest state_dir")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    manifest, _ = load_manifest(root)
    state_dir = args.state_dir or manifest.get("state_dir", ".tdd")
    if not os.path.isabs(state_dir):
        state_dir = os.path.join(root, state_dir)

    if args.cmd == "snapshot":
        if not args.id or not args.paths:
            print(json.dumps({"ok": False, "error": "snapshot needs --id and --paths"}))
            sys.exit(1)
        res = cmd_snapshot(root, manifest, state_dir, args.id, args.paths)
    elif args.cmd == "restore":
        if not args.id:
            print(json.dumps({"ok": False, "error": "restore needs --id"}))
            sys.exit(1)
        res = cmd_restore(root, manifest, state_dir, args.id, args.paths)
    elif args.cmd == "changed":
        res = cmd_changed(root, manifest)
    else:  # list
        base = os.path.join(state_dir, "snapshot")
        res = {"ok": True, "ids": sorted(os.listdir(base)) if os.path.isdir(base) else []}

    print(json.dumps(res, ensure_ascii=True, indent=2))
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
