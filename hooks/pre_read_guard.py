"""PreToolUse guard for Read (lesson L001, created 2026-08-15).

Blocks Read on a nonexistent path BEFORE the tool errors, and turns the
dead end into a self-correcting one: the block message names the nearest
existing ancestor directory and close-match filenames inside it, so the
next call is the right one instead of a second guess. Also blocks Read on
a directory (EISDIR) with a pointer to Glob.

40 logged L001 violations were exactly these two shapes: assumed paths
and directory-as-file reads.

2026-08-25 extended (L029 promotion, 11 logged violations): size pre-check
before the Read token cap fires. Blocks a no-limit Read on files >50KB
(re-send with limit/offset or Grep first), and any Read of a single-line
blob >50KB (offset/limit cannot chunk one line — use Grep -o or a script).
Media/PDF/notebook extensions are exempt (Read handles them natively).

Fail-open by design: an internal error must never block the tool call.
"""
import difflib
import json
import os
import sys

# L029: formats Read renders natively — the text token cap logic does not
# apply the same way; never size-gate these.
MEDIA_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico',
              '.pdf', '.ipynb'}
SIZE_GATE = 51200  # 50KB — lesson heuristic: above this the cap likely fires


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
    fp = (data.get('tool_input', {}) or {}).get('file_path', '')
    if not fp:
        return
    fp = os.path.normpath(os.path.expanduser(fp))

    if os.path.isfile(fp):
        # --- L029: size pre-check before the token cap wastes the call ---
        try:
            size = os.path.getsize(fp)
        except OSError:
            return
        if size <= SIZE_GATE:
            return
        if os.path.splitext(fp)[1].lower() in MEDIA_EXTS:
            return
        inp = data.get('tool_input', {}) or {}
        one_line = False
        try:
            with open(fp, 'rb') as f:
                one_line = b'\n' not in f.read(65536)
        except OSError:
            pass
        if one_line:
            emit_block('BLOCKED: %s is %dKB with no newline in its first '
                       '64KB — a single-line blob. offset/limit cannot chunk '
                       'one line and the whole line exceeds the Read token '
                       'cap. Extract the fields you need with Grep -o, or '
                       'parse it in a python script (json.load) instead. '
                       '(Enforced by pre-read-guard hook, lesson L029)'
                       % (os.path.basename(fp), size // 1024))
            return
        if not inp.get('limit'):
            emit_block('BLOCKED: %s is %dKB (>50KB) — an unbounded Read will '
                       'likely exceed the Read token cap and waste the round '
                       'trip. Re-send with an explicit limit (e.g. limit: 400, '
                       'plus offset for later sections), or Grep for the '
                       'section you need first. '
                       '(Enforced by pre-read-guard hook, lesson L029)'
                       % (os.path.basename(fp), size // 1024))
        return  # exists — nothing else to guard

    if os.path.isdir(fp):
        emit_block('BLOCKED: %s is a DIRECTORY, not a file. Use Glob '
                   '(pattern "*", path "%s") to list it, then Read a specific '
                   'file. (Enforced by pre-read-guard hook, lesson L001)'
                   % (fp, fp.replace('\\', '/')))
        return

    # Missing path: walk up to the nearest existing ancestor and suggest
    # close-match entries there.
    parent = os.path.dirname(fp)
    probe = parent
    while probe and not os.path.isdir(probe):
        nxt = os.path.dirname(probe)
        if nxt == probe:
            probe = ''
            break
        probe = nxt

    suggestions = []
    base = os.path.basename(fp)
    if probe:
        try:
            entries = os.listdir(probe)[:4000]
            suggestions = difflib.get_close_matches(base, entries, n=5,
                                                    cutoff=0.45)
            if not suggestions:
                stem = os.path.splitext(base)[0].lower()[:8]
                if stem:
                    suggestions = [e for e in entries
                                   if stem in e.lower()][:5]
        except OSError:
            pass

    msg = 'BLOCKED: File does not exist: %s.' % fp
    if probe and probe != parent:
        msg += (' The directory chain breaks at %s (nearest existing '
                'ancestor).' % probe)
    if suggestions:
        msg += ' Close matches in %s: %s.' % (probe, ', '.join(suggestions))
    msg += (' Glob before Read — never assume a path. '
            '(Enforced by pre-read-guard hook, lesson L001)')
    emit_block(msg)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass  # fail open
    sys.exit(0)
