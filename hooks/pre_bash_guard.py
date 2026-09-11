"""PreToolUse guard for Bash + PowerShell.

Merges pre-destructive-git + pre-secrets-scan into ONE interpreter spawn
(was two bash+python spawns before every Bash command).

2026-08-15 extended (reflection hook-conversion of 20+ violation lessons):
  - Matcher widened to Bash|PowerShell: destructive-git + secret scans now
    also cover the PowerShell tool (was a bypass gap).
  - L003 (Bash dialect only): blocks Windows backslash drive paths,
    Windows-native /flag commands, and cmd-style >nul redirects — the three
    deterministic shapes behind 53 logged violations.

2026-08-23 extended (reflection: the 6cd0e43e $S-empty variant that got past
the guard):
  - L003 unset-path-variable: blocks $VAR/... path construction when VAR is
    never assigned in the same command. Bash-tool state does not persist
    between calls, so the var expands EMPTY, the path degrades to a bare
    /script.py, and MSYS translates the leading slash to the Git install
    root (python received "C:\\Program Files\\Git\\fub_backlog_probe.py").
    Exempt: vars assigned/looped/read in-command, ${VAR:?}/${VAR:-} guarded
    forms, real environment variables, single-quoted spans, and
    quote-delimited heredoc bodies (no expansion there).
  - L030: 15s git-mutation lock serializes parallel git calls from the same
    session (released by post-bash-verify-tracker.sh; expires on its own if
    the release never fires).
  - L028: one-shot per-session NON-blocking reminder when a command reaches
    a remote system (ssh/scp/mutating curl).

2026-08-25 extended (lesson-to-hook promotion pass, after the memory/harness
audit; see L018/L029/L034/L035/L028 lesson files):
  - L035 both directions: PowerShell vocabulary (cmdlets, 2>$null, $env:) in
    the Bash tool, and bash-isms (&&/||, /dev/null, export VAR=) in the
    PowerShell tool. PS checks run on comment/quote/here-string-stripped text.
  - L034 (PowerShell): 2>&1 on a native executable — PS 5.1 wraps stderr as
    NativeCommandError and reports false exit-1 on green runs.
  - L018 (both): inline python source (-c / stdin heredoc) containing
    non-ASCII — cp1252 pipes corrupt it before the interpreter runs.
  - L028 upgrade: high-blast-radius REMOTE mutations (ssh rm -rf/systemctl
    stop/docker rm/DROP TABLE/... , curl -X DELETE) now emit permissionDecision
    "ask" per command. Routine ssh stays un-gated; reminder unchanged.
  - L011: once-per-session NON-blocking warn on long/nested inline ssh
    commands (prefer scp-ing a script file).

Fail-open by design: an internal error must never block the tool call.
"""
import json
import os
import re
import sys
import time

DESTRUCTIVE = [
    (r'git\s+push\s+.*--force(?!-with-lease)', 'git push --force (use --force-with-lease instead)'),
    (r'git\s+push\s+.*-f\b', 'git push -f (use --force-with-lease instead)'),
    (r'git\s+reset\s+--hard', 'git reset --hard (destructive, loses uncommitted work)'),
    (r'git\s+checkout\s+--\s+\.', 'git checkout -- . (discards all changes)'),
    (r'git\s+clean\s+-f', 'git clean -f (deletes untracked files)'),
    (r'rm\s+-rf\s+[/~]', 'rm -rf on root/home path'),
    (r'rm\s+-rf\s+\.\s', 'rm -rf . (deletes current directory)'),
    (r'git\s+branch\s+-D\s+(?:main|master)', 'deleting main/master branch'),
    (r'drop\s+(?:table|database)', 'DROP TABLE/DATABASE'),
]

# Keep in sync with pre_file_guard.py (self-contained on purpose).
SECRET_PATTERNS = [
    r"(?:sk-|sk_live_|sk_test_)[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"gho_[a-zA-Z0-9]{36}",
    r"AKIA[0-9A-Z]{16}",
    r"(?:password|passwd|pwd)\s*[=:]\s*[\x22\x27][^\x22\x27]{8,}[\x22\x27]",
    r"(?:api_key|apikey|api_secret)\s*[=:]\s*[\x22\x27][^\x22\x27]{10,}[\x22\x27]",
    r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
    r"xox[bpsar]-[a-zA-Z0-9-]{10,}",
]

# L003: Windows-native commands whose /flags Git Bash mangles into paths.
WIN_NATIVE = (r'(?:^|[;&|(]\s*|\s)'
              r'(?:ipconfig|taskkill|tasklist|schtasks|wmic|netsh|reg|sc|'
              r'chkdsk|sfc|robocopy|attrib|icacls)(?:\.exe)?\s+/[A-Za-z]')

# L003 unset-var: shell vars that legitimately arrive from the environment /
# profile — never flag these. Compared uppercase; os.environ is also consulted.
BASH_SAFE_VARS = {
    'HOME', 'PATH', 'PWD', 'OLDPWD', 'TMPDIR', 'TMP', 'TEMP',
    'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'PROGRAMFILES',
    'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC',
    'USER', 'USERNAME', 'LOGNAME', 'HOSTNAME', 'SHELL', 'MSYSTEM',
}


def strip_quoted_heredocs(text):
    """Drop bodies of quote-delimited heredocs (<<'EOF', <<"EOF", <<\\EOF).

    Bash performs no expansion inside them, so $VAR there is literal content
    and must not trigger the unset-var check. Unquoted heredocs DO expand and
    are deliberately kept.
    """
    while True:
        m = re.search(r'<<-?\s*(?:\'([A-Za-z_]\w*)\'|"([A-Za-z_]\w*)"|\\([A-Za-z_]\w*))',
                      text)
        if not m:
            return text
        delim = m.group(1) or m.group(2) or m.group(3)
        body_start = text.find('\n', m.end())
        if body_start == -1:
            return text[:m.start()]
        term = re.search(r'^\s*' + re.escape(delim) + r'\s*$',
                         text[body_start:], re.MULTILINE)
        end = body_start + term.end() if term else len(text)
        text = text[:m.start()] + ' ' + text[end:]


def unset_path_var(cmd):
    """Return the first $VAR used in path position with no in-command
    assignment, or None. See module docstring (L003 unset-path-variable)."""
    scan = re.sub(r"'[^']*'", "''", strip_quoted_heredocs(cmd))
    env_upper = {k.upper() for k in os.environ}
    for m in re.finditer(r'(?<!\\)\$(?:([A-Za-z_]\w*)|\{([A-Za-z_]\w*)\})"?/', scan):
        var = m.group(1) or m.group(2)
        if var.upper() in BASH_SAFE_VARS or var.upper() in env_upper:
            continue
        v = re.escape(var)
        assigned = (
            re.search(r'(?:^|[\s;&|({`])(?:export\s+|local\s+|readonly\s+|'
                      r'declare\s+(?:-\w+\s+)*)?' + v + r'=', cmd)
            or re.search(r'\bfor\s+' + v + r'\b', cmd)
            or re.search(r'\bread\b[^\n;|&]*\b' + v + r'\b', cmd)
        )
        if not assigned:
            return var
    return None


# L030: git subcommands that mutate the index/worktree/refs — the shapes
# that cascade-cancel when parallel-batched. Read-only git (status/log/diff)
# is deliberately excluded.
GIT_MUTATION = (r'\bgit\s+(?:-[^\s]+\s+)*'
                r'(?:add|commit|mv|rm|restore|stash|checkout|switch|merge|'
                r'rebase|cherry-pick|reset|revert|apply|am|pull|push|tag|'
                r'worktree|clean)\b')
GIT_LOCK_TTL = 15  # seconds

# L028: command reaches beyond this machine.
REMOTE_REACH = [
    r'(?:^|[;&|(]\s*)(?:ssh|scp|sftp|rsync)\s',
    r'\bcurl\b[^|;&\n]*-X\s*(?:POST|PUT|PATCH|DELETE)',
]

# --- 2026-08-25 promotions ---

# L034: native exes whose stderr PowerShell 5.1 wraps into NativeCommandError
# records under 2>&1, flipping $?/exit to failure on green runs.
PS_NATIVE_2GT1 = (r'(?:^|[;|(&{]\s*|\s)'
                  r'(?:git|uv|mypy|ruff|python[0-9.]*|py|pip3?|node|npm|npx|'
                  r'pnpm|yarn|ssh|scp|sftp|rsync|curl|wget|ffmpeg|ffprobe|'
                  r'docker|kubectl|gh|cargo|rustc|go|dotnet|pytest|tsc|'
                  r'eslint|prettier|wrangler|vercel|supabase)'
                  r'(?:\.exe)?\s[^\n|;]*2>&1')

# L035: canonical Verb-Noun cmdlet in the Bash tool (case-sensitive on
# purpose — pasted cmdlets arrive in canonical caps; lowercase words like
# bash's `read` must not match).
BASH_PS_CMDLET = (r'\b(?:Get|Set|New|Remove|Select|Where|ForEach|Out|Start|'
                  r'Stop|Test|Measure|Add|Clear|Copy|Move|Invoke|Read|Sort|'
                  r'Group|Compare|Format|Export|Import|ConvertTo|ConvertFrom)'
                  r'-[A-Z][A-Za-z]+\b')

# L018: inline python SOURCE in a shell command (-c or stdin-dash heredoc).
PY_INLINE = r'\bpy(?:thon)?[0-9.]*(?:\.exe)?\s+(?:(?:-[A-Za-z]+\s+)*-c\b|-\s*<<)'

# Seat-standard grok dispatch (2026-08-26 retro): PowerShell 5.1 splits argv
# on embedded double quotes inside -p "<prompt>" (a logged dispatch mis-parsed
# to exit 2 "unrecognized subcommand"), and raw dispatch strings had drifted
# into 4 variants across projects. ~/.claude/bin/grok-dispatch.sh pins
# model/effort/permissions and reads the prompt from a file; it is THE
# dispatch path (CLAUDE.md "SDD seat standard"). Wrapper invocations
# ("grok-dispatch.sh") never match: the pattern requires whitespace (or a
# closing quote) right after grok/grok.exe. PowerShell: hard block.
# Bash: once-per-session non-blocking nudge toward the wrapper.
# Matched against RAW command text (never literal-stripped: PS quoted paths
# like & "...\grok.exe" would lose the exe name to the stripper); the
# command-position anchor keeps "grok -p" inside prose/echo text from
# matching.
GROK_PROMPT_DISPATCH = (r'(?:^|[\n;&|(]\s*)(?:&\s+)?["\']?'
                        r'(?:[^\s;|&"\']*[/\\])?grok(?:\.exe)?["\']?'
                        r'(?:\s+[^\s;|&]+)*?\s+(?:-p|--prompt(?:-file)?)\b')

# L028: remote-mutation shapes with the highest blast radius (from the
# lesson's denial evidence). Matched inside the ssh command tail only.
SSH_HIGH_BLAST = [
    r'\brm\s+-[a-z]*f',
    r'\bsystemctl\s+(?:stop|restart|disable|mask)\b',
    r'\bdocker\s+(?:rm|stop|kill|restart)\b',
    r'\bdocker\s+compose\s+down\b',
    r'\b(?:iptables|nft|ufw)\b',
    r'\bshred\b',
    r'\bchown\b',
    r'\b(?:reboot|shutdown|poweroff)\b',
    r'\bcrontab\s+-r',
    r'\bkill(?:all)?\b',
    r'\bmkfs',
    r'\bdd\s+if=',
    r'\b(?:DROP\s+(?:TABLE|DATABASE)|ALTER\s+(?:ROLE|USER)|TRUNCATE)\b',
]


def strip_ps_literals(text):
    """Remove PowerShell here-strings, quoted spans, and comments so the
    dialect checks see only executable syntax, never string content."""
    text = re.sub(r"@'.*?'@", ' ', text, flags=re.DOTALL)
    text = re.sub(r'@".*?"@', ' ', text, flags=re.DOTALL)
    text = re.sub(r"'[^']*'", "''", text)
    text = re.sub(r'"[^"]*"', '""', text)
    text = re.sub(r'<#.*?#>', ' ', text, flags=re.DOTALL)
    text = re.sub(r'(?m)#.*$', '', text)
    return text


def emit_ask(msg):
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'ask',
        'permissionDecisionReason': msg,
    }}))


def state_path(session_id, suffix):
    return os.path.join(os.path.expanduser('~'), '.claude', 'session-state',
                        session_id + suffix)


def emit_block(msg):
    print(json.dumps({
        'decision': 'block',
        'reason': msg,
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': msg,
        },
    }))


def main():
    data = json.load(sys.stdin)
    tool = data.get('tool_name', 'Bash')
    session_id = data.get('session_id', 'unknown')
    tool_use_id = data.get('tool_use_id', '')
    cmd = (data.get('tool_input', {}) or {}).get('command', '')
    if not cmd:
        return

    for pattern, desc in DESTRUCTIVE:
        if re.search(pattern, cmd, re.IGNORECASE):
            emit_block('BLOCKED: Destructive command detected — %s. This requires '
                       'explicit user approval. (Enforced by pre-bash-guard hook)' % desc)
            return

    for p in SECRET_PATTERNS:
        if re.search(p, cmd, re.IGNORECASE):
            emit_block('BLOCKED: Detected hardcoded secret/credential in command. '
                       'Use environment variables instead. '
                       '(Enforced by pre-bash-guard hook, lesson L010)')
            return

    # --- L018: inline python source with non-ASCII (both shells) ---
    if re.search(PY_INLINE, cmd) and any(ord(c) > 127 for c in cmd):
        emit_block('BLOCKED: Inline python source (-c / stdin heredoc) '
                   'containing non-ASCII characters. cp1252 shell pipes '
                   'corrupt non-ASCII before the interpreter runs it '
                   '(an em-dash arrived as U+FFFD -> SyntaxError in a logged '
                   'session). Write the script to a file with the Write tool '
                   '(UTF-8 on disk) and run that file, or keep the inline '
                   'source ASCII-only. '
                   '(Enforced by pre-bash-guard hook, lesson L018)')
        return

    # --- L003: Bash-dialect Windows traps (PowerShell handles these fine) ---
    if tool == 'Bash':
        # Single-quoted spans survive Bash untouched — scan everything else.
        scan = re.sub(r"'[^']*'", "''", cmd)
        if re.search(r'(?<![A-Za-z0-9])[A-Za-z]:\\+[^\s\\/:*?"<>|]', scan):
            emit_block('BLOCKED: Windows backslash path in a Bash-tool command. '
                       'Git Bash strips backslashes (C:\\Users\\... arrives as '
                       'C:UsersWarren...) and quoted backslash paths hit '
                       'unexpected-EOF parser errors. Use forward slashes '
                       '(C:/Users/...) or /c/Users/... — or run it via the '
                       'PowerShell tool. If the backslashes are intended file '
                       'CONTENT, use the Write tool. '
                       '(Enforced by pre-bash-guard hook, lesson L003)')
            return
        if re.search(WIN_NATIVE, scan, re.IGNORECASE):
            emit_block('BLOCKED: Windows-native command with a /flag in the Bash '
                       'tool — Git Bash mangles /flags into paths (ipconfig /all '
                       'becomes \\all). Run it via the PowerShell tool instead. '
                       '(Enforced by pre-bash-guard hook, lesson L003)')
            return
        if re.search(r'(?<![A-Za-z0-9_.])\d?>\s*nul\b', scan):
            emit_block('BLOCKED: cmd.exe-style ">nul" redirect in Bash — it '
                       'creates a file literally named "nul" instead of '
                       'discarding output. Use 2>/dev/null, or the PowerShell '
                       'tool with $null. '
                       '(Enforced by pre-bash-guard hook, lesson L003)')
            return
        bad_var = unset_path_var(cmd)
        if bad_var:
            emit_block('BLOCKED: "$%s/..." builds a path from a variable never '
                       'assigned in this command. Bash-tool state does NOT '
                       'persist between calls, so $%s expands EMPTY — the path '
                       'degrades to a bare /file and MSYS resolves the leading '
                       'slash to the Git install root (C:/Program Files/Git/). '
                       'Fix: assign %s=... at the start of THIS command, or use '
                       '"${%s:?}" if it truly comes from the environment. '
                       '(Enforced by pre-bash-guard hook, lesson L003)'
                       % (bad_var, bad_var, bad_var, bad_var))
            return
        # --- L035: PowerShell vocabulary in the Bash tool ---
        scan2 = re.sub(r'"[^"]*"', '""', scan)
        ps_ism = None
        if re.search(r'2>\s*\$null', scan2):
            ps_ism = '2>$null (POSIX: 2>/dev/null)'
        elif re.search(r'\$env:[A-Za-z_]', scan2):
            ps_ism = '$env:VAR (POSIX: $VAR)'
        else:
            m = re.search(BASH_PS_CMDLET, scan2)
            if m:
                ps_ism = m.group(0) + ' (a PowerShell cmdlet)'
        if ps_ism:
            emit_block('BLOCKED: PowerShell syntax in the Bash tool — %s. '
                       'The Bash tool runs Git Bash (POSIX sh). Rewrite the '
                       'whole command in one POSIX dialect (grep/head/ls, '
                       '2>/dev/null, $VAR) or send it to the PowerShell tool '
                       'instead — never re-run a tweaked hybrid. '
                       '(Enforced by pre-bash-guard hook, lesson L035)' % ps_ism)
            return

    # --- L034 + L035: bash-isms in the PowerShell tool ---
    if tool == 'PowerShell':
        scan = strip_ps_literals(cmd)
        if re.search(GROK_PROMPT_DISPATCH, cmd):
            emit_block('BLOCKED: grok prompt dispatch in the PowerShell tool. '
                       'PowerShell 5.1 splits argv on embedded double quotes '
                       'inside -p "<prompt>" (a logged dispatch mis-parsed to '
                       'exit 2, "unrecognized subcommand"). Seat standard: '
                       'dispatch implementers from the BASH tool via '
                       '~/.claude/bin/grok-dispatch.sh <prompt-file> '
                       '<repo-cwd> — it pins grok-4.6/xhigh/bypassPermissions '
                       'and reads the prompt from a file. '
                       '(Enforced by pre-bash-guard hook, SDD seat standard)')
            return
        if re.search(r'&&|\|\|', scan):
            emit_block('BLOCKED: "&&" / "||" pipeline-chain operators are not '
                       'valid in Windows PowerShell 5.1 — parser error before '
                       'anything runs. Chain with ";" (unconditional) or '
                       '"A; if ($?) { B }" (on success). '
                       '(Enforced by pre-bash-guard hook, lesson L035)')
            return
        if re.search(r'/dev/null', scan):
            emit_block('BLOCKED: "/dev/null" in a PowerShell command — that is '
                       'a POSIX path. Use $null (e.g. 2>$null) or Out-Null. '
                       '(Enforced by pre-bash-guard hook, lesson L035)')
            return
        if re.search(r'(?:^|[;({|]\s*)export\s+[A-Za-z_]+=', scan):
            emit_block('BLOCKED: bash "export VAR=" in PowerShell. Use '
                       "$env:VAR = 'value' instead. "
                       '(Enforced by pre-bash-guard hook, lesson L035)')
            return
        if re.search(PS_NATIVE_2GT1, scan):
            emit_block('BLOCKED: "2>&1" on a native executable in PowerShell '
                       '5.1 — each stderr line gets wrapped as a '
                       'NativeCommandError record and the call reports exit-1 '
                       'even when the program returned 0 (10 logged '
                       'false-failure sessions). Drop the redirect — the '
                       'harness already captures stderr; check $LASTEXITCODE '
                       'for real status, or redirect streams to separate '
                       'files. (Enforced by pre-bash-guard hook, lesson L034)')
            return

    # --- L030: serialize git-mutating commands across parallel calls ---
    if re.search(GIT_MUTATION, cmd):
        lock = state_path(session_id, '.gitlock')
        try:
            age = time.time() - os.path.getmtime(lock)
        except OSError:
            age = None
        if age is not None and 0 <= age < GIT_LOCK_TTL:
            emit_block('BLOCKED: Another git command from this session started '
                       '%.0fs ago and may still be running — parallel git calls '
                       'on one index cascade-cancel when any of them fails. '
                       'Combine into ONE chained command (git add a b c && git '
                       'commit ...) or re-send this call alone after the other '
                       'finishes. Lock self-expires in %.0fs. '
                       '(Enforced by pre-bash-guard hook, lesson L030)'
                       % (age, GIT_LOCK_TTL - age))
            return
        try:
            os.makedirs(os.path.dirname(lock), exist_ok=True)
            with open(lock, 'w') as f:
                # line 1: timestamp; line 2: owner tool_use_id. Only the owner
                # (PostToolUse / PostToolUseFailure of THIS call) may release it.
                f.write(str(time.time()) + '\n' + tool_use_id)
        except OSError:
            pass

    # --- L028: high-blast-radius remote mutation -> per-command ask gate ---
    ssh_m = re.search(r'(?:^|[;&|(]\s*)ssh\s+(.*)', cmd, re.DOTALL)
    remote_tail = ssh_m.group(1) if ssh_m else ''
    high = None
    for p in (SSH_HIGH_BLAST if remote_tail else []):
        m = re.search(p, remote_tail, re.IGNORECASE)
        if m:
            high = m.group(0)
            break
    if not high and re.search(r'\bcurl\b[^|;&\n]*-X\s*DELETE', cmd, re.IGNORECASE):
        high = 'curl -X DELETE'
    if high:
        emit_ask('L028 gate: this command performs a high-blast-radius '
                 'mutation on a REMOTE/external system ("%s"). Session-level '
                 'plan approval does not authorize external-system changes — '
                 'per-command user confirmation required. '
                 '(Enforced by pre-bash-guard hook, lesson L028)' % high)
        return

    # --- Non-blocking context: L028 reminder + L011 inline-ssh warn ---
    contexts = []
    if any(re.search(p, cmd, re.IGNORECASE) for p in REMOTE_REACH):
        marker = state_path(session_id, '.l028')
        if not os.path.exists(marker):
            try:
                os.makedirs(os.path.dirname(marker), exist_ok=True)
                with open(marker, 'w') as f:
                    f.write('1')
                contexts.append(
                    'L028 reminder (once per session): this command reaches '
                    'a remote/external system. Session-level plan approval '
                    'does NOT authorize external-system changes — if this '
                    'call mutates anything beyond this machine and the user '
                    'has not individually confirmed it, confirm first.')
            except OSError:
                pass
    if tool == 'Bash' and 'grok-dispatch' not in cmd:
        if re.search(GROK_PROMPT_DISPATCH, cmd):
            marker = state_path(session_id, '.grokwrap')
            if not os.path.exists(marker):
                try:
                    os.makedirs(os.path.dirname(marker), exist_ok=True)
                    with open(marker, 'w') as f:
                        f.write('1')
                    contexts.append(
                        'Seat-standard note (once per session): raw "grok -p" '
                        'dispatch detected. Implementer dispatches route '
                        'through ~/.claude/bin/grok-dispatch.sh <prompt-file> '
                        '<repo-cwd> — it pins grok-4.6/xhigh/bypassPermissions '
                        'and avoids quote-drift. Quick one-off prompts are '
                        'fine raw.')
                except OSError:
                    pass
    if ssh_m and ('<<' in cmd or len(cmd) > 300):
        marker = state_path(session_id, '.l011')
        if not os.path.exists(marker):
            try:
                os.makedirs(os.path.dirname(marker), exist_ok=True)
                with open(marker, 'w') as f:
                    f.write('1')
                contexts.append(
                    'L011 (once per session): long/nested inline ssh command '
                    'detected. Prefer writing a local script file, scp-ing it '
                    'over, and running that — inline quote nesting is the #1 '
                    'remote-command failure shape.')
            except OSError:
                pass
    if contexts:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'additionalContext': ' | '.join(contexts),
        }}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass  # fail open
    sys.exit(0)
