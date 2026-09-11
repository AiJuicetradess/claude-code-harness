---
id: L032
title: "Never pass multi-line or unquoted strings inline to git -m / git add - the shell word-splits them into bogus pathspecs"
category: tool-usage
severity: high
status: active
created: 2026-06-14
last_triggered: 2026-06-10
times_violated: 4
times_checked: 0
tags: [git, shell, powershell, bash, commit, quoting, windows]
related_skills: [git-pushing]
---
**Rule:** For any commit message with newlines, dollar signs, or punctuation, write it to a file and use `git commit -F msgfile` (or a verified here-string). Never inline a multi-line message into `git commit -m` or build a long `git add` arglist the shell can word-split, and never guess flags like `git status --cached`.

**Why:** On both Git Bash and PowerShell 5.1 an inline multi-line -m body or an unquoted arg list is tokenized on whitespace, so each word becomes a separate argument - git then reports 'pathspec "in" did not match' for every word, the commit silently fails or commits the wrong set, and turns are wasted rediscovering it. Compounding it, the assistant twice misread the failure and reported the commit succeeded.

**Prevention:**
1. Write the commit message to a temp file and run `git commit -F <file>` for anything longer than a single short line.
2. If you must use -m, keep it to one line with no shell-special characters; for multi-line use a single-quoted here-string whose closing token is at column 0 (PowerShell) - and verify it parsed.
3. After committing, confirm with `git log -1 --format=%H` before claiming success; do not trust your own pre-commit verification flag.
4. Don't guess git flags (`--cached` is not a `git status` option); run `git <cmd> --help` first.
