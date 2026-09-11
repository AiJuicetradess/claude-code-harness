#!/usr/bin/env python
"""
canon.py -- the canonical-serialization spine of the infra-audit gate.

Produces a deterministic, unambiguous byte encoding of a proposal payload and a
sha256 fingerprint over it. The SAME module is used by the proposer (to build the
fingerprint), by `authorize` (to render what the human sees AND hash what they
sign), and by the executor (to recompute and compare) -- so "what you see == what
you sign == what executes" holds BY CONSTRUCTION, not by three implementations
happening to agree. This closes the canonicalization-parity hole.

Encoding rules that remove ambiguity:
  - dict keys are sorted; encoding is insertion-order-independent
  - strings are utf-8, length-prefixed
  - integers are decimal-ascii, length-prefixed
  - FLOATS ARE REJECTED (sizes/counts/epochs are ints; no float-format ambiguity)
  - bool / None carry distinct type tags (never confused with 0 / 1 / "")
  - lists are count-prefixed
  - CANON_VERSION is bound into every fingerprint

stdlib only. ASCII output. Windows-safe.
Exit (run directly): 0 self-test OK, 1 self-test failed.
"""
import hashlib
import re
import sys
import unicodedata

CANON_VERSION = "audit-canon/v1"

_T_DICT = b"D"
_T_LIST = b"L"
_T_STR = b"S"
_T_INT = b"I"
_T_BOOL = b"B"
_T_NONE = b"N"


def _enc(obj):
    """Deterministic length-prefixed encoding -> bytes."""
    if isinstance(obj, bool):
        # MUST precede the int check: bool is a subclass of int in Python.
        return _T_BOOL + (b"1" if obj else b"0")
    if obj is None:
        return _T_NONE
    if isinstance(obj, int):
        s = str(obj).encode("ascii")
        return _T_INT + str(len(s)).encode("ascii") + b":" + s
    if isinstance(obj, float):
        raise TypeError("canon: floats are not allowed in a signed payload")
    if isinstance(obj, str):
        b = obj.encode("utf-8")
        return _T_STR + str(len(b)).encode("ascii") + b":" + b
    if isinstance(obj, (list, tuple)):
        out = [_T_LIST + str(len(obj)).encode("ascii") + b":"]
        for el in obj:
            out.append(_enc(el))
        return b"".join(out)
    if isinstance(obj, dict):
        keys = sorted(obj.keys())
        out = [_T_DICT + str(len(keys)).encode("ascii") + b":"]
        for k in keys:
            if not isinstance(k, str):
                raise TypeError("canon: dict keys must be strings")
            kb = k.encode("utf-8")
            out.append(str(len(kb)).encode("ascii") + b":" + kb)
            out.append(_enc(obj[k]))
        return b"".join(out)
    raise TypeError("canon: unsupported type %s" % type(obj).__name__)


def canon_bytes(payload):
    """Canonical bytes of a payload dict, with CANON_VERSION bound in."""
    wrapped = {"canon_version": CANON_VERSION, "payload": payload}
    return _enc(wrapped)


def fingerprint(payload):
    """sha256 hex over the canonical bytes of the payload."""
    return hashlib.sha256(canon_bytes(payload)).hexdigest()


_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def sanitize_text(s):
    """Make agent-authored text safe to DISPLAY in `authorize`: strip ANSI escapes,
    replace control chars, and escape non-ascii (so a homoglyph / RTL-override path
    or a terminal-escape `reason` cannot misrepresent what is actually being signed).
    """
    if not isinstance(s, str):
        s = str(s)
    s = _ANSI.sub("", s)
    out = []
    flagged = False
    for ch in s:
        if unicodedata.category(ch).startswith("C"):  # control/format/surrogate/etc
            out.append("?")
            flagged = True
        elif ord(ch) > 0x7E:
            out.append("<U+%04X>" % ord(ch))
            flagged = True
        else:
            out.append(ch)
    text = "".join(out)
    return text + ("  [non-ascii flagged]" if flagged else "")


def render(payload):
    """Human-facing view for `authorize`, derived from the SAME payload that is
    hashed. Foregrounds the concrete item list over the prose reason (anti-fatigue,
    anti-social-engineering)."""
    lines = []
    lines.append("ACTION : %s" % sanitize_text(payload.get("action_type", "?")))
    lines.append("BOX    : %s" % sanitize_text(payload.get("box_id", "?")))
    items = payload.get("enumerated_items", [])
    total = 0
    lines.append("ITEMS  : %d" % len(items))
    for it in items:
        size = it.get("size")
        if isinstance(size, int):
            total += size
        ident = it.get("path")
        if ident is None:
            ident = "pid=%s exe_inode=%s start=%s" % (
                it.get("pid"), it.get("exe_inode"), it.get("start_time"))
        lines.append("  - %s  (size=%s dev=%s inode=%s)" % (
            sanitize_text(ident), it.get("size"), it.get("dev"), it.get("inode")))
    lines.append("BYTES  : %d" % total)
    lines.append("REASON : %s" % sanitize_text(payload.get("reason", "")))
    lines.append("EXPIRES: %s (not_after; best-effort, clock-bounded)" % payload.get("not_after"))
    lines.append("FINGERPRINT: %s" % fingerprint(payload))
    return "\n".join(lines)


# Pinned fixture + digest: any drift in the encoder (or the fixture) breaks the
# pinned assertion -- the tripwire that keeps proposer/authorize/executor in lockstep.
_PINNED = {
    "action_type": "delete",
    "box_id": "fixture-box",
    "enumerated_items": [
        {"path": "/var/log/a.gz", "dev": 2049, "inode": 100, "size": 10, "mtime": 5},
        {"path": "/var/log/b.gz", "dev": 2049, "inode": 101, "size": 20, "mtime": 6},
    ],
    "predicted_effect": 30,
    "proposal_id": "fixture-nonce-0001",
    "reason": "fixture",
    "not_after": 1800000000,
}
PINNED_DIGEST = "4e2835c2b7650095511f71843bac273cf5c0d89f3e509630aef2d6c995471387"


def self_test():
    # order-independence
    a = fingerprint(_PINNED)
    b = fingerprint(dict(reversed(list(_PINNED.items()))))
    assert a == b, "canon: not order-independent"
    # determinism
    assert canon_bytes(_PINNED) == canon_bytes(_PINNED), "canon: not deterministic"
    # type distinctness (bool vs int vs str vs None vs "")
    assert len({_enc(True), _enc(1), _enc("1")}) == 3, "canon: bool/int/str collide"
    assert _enc(None) != _enc(""), "canon: None/empty collide"
    # float rejection
    try:
        canon_bytes({"x": 1.5})
    except TypeError:
        pass
    else:
        raise AssertionError("canon: float not rejected")
    # pinned vector (skipped until filled)
    if PINNED_DIGEST != "<FILL>":
        assert a == PINNED_DIGEST, "canon: pinned digest mismatch (encoder drift)"
    return a


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        digest = self_test()
    except AssertionError as e:
        sys.stdout.write("canon self-test FAILED: %s\n" % e)
        sys.exit(1)
    sys.stdout.write("canon self-test OK; fixture fingerprint = %s\n" % digest)
    sys.exit(0)
