#!/usr/bin/env python
"""
sign.py -- the authorization PROOF seam: detached SSH signatures over a fingerprint.

The operator's PRIVATE key never leaves their workstation (hardware-token / FIDO
sk- key compatible); each box carries only the PUBLIC key in an ssh allowed_signers
file. Authorization = a detached signature over the canon fingerprint, produced with
`ssh-keygen -Y sign` and verified on the box with `ssh-keygen -Y verify`. No Python
crypto dependency; the trust boundary is asymmetric crypto, so a privileged-but-
confused agent on the box cannot forge a token -- it has no private key.

stdlib only (shells out to ssh-keygen); ASCII output; Windows-safe (list-arg
subprocess, no shell quoting). Exit (direct): 0 OK, 1 failed, 2 ssh-keygen absent.
"""
import os
import subprocess
import sys
import tempfile


def _run(args, input_bytes=None, timeout=30):
    try:
        r = subprocess.run(args, input=input_bytes, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, b"", b"ssh-keygen not found"
    except subprocess.TimeoutExpired:
        return 124, b"", b"ssh-keygen timeout"


def have_ssh_keygen():
    # -Q with empty stdin errors fast (no interactive key-gen prompt); 127 == absent.
    rc, _, _ = _run(["ssh-keygen", "-Q"], input_bytes=b"")
    return rc != 127


def sign_message(message_bytes, key_path, namespace):
    """Produce a detached SSH signature over message_bytes. Returns signature bytes."""
    d = tempfile.mkdtemp(prefix="audit_sign_")
    msg = os.path.join(d, "msg")
    try:
        with open(msg, "wb") as f:
            f.write(message_bytes)
        rc, out, err = _run(["ssh-keygen", "-Y", "sign", "-f", key_path, "-n", namespace, msg])
        if rc != 0:
            raise RuntimeError("ssh-keygen sign failed: %s" % err.decode("utf-8", "replace"))
        with open(msg + ".sig", "rb") as f:
            return f.read()
    finally:
        _rmtree(d)


def verify_message(message_bytes, sig_bytes, allowed_signers, identity, namespace):
    """Verify a detached SSH signature against the public key in allowed_signers.
    Returns {ok, reason}."""
    if not os.path.isfile(allowed_signers):
        return {"ok": False, "reason": "allowed_signers not found: %s" % allowed_signers}
    d = tempfile.mkdtemp(prefix="audit_verify_")
    sig = os.path.join(d, "msg.sig")
    try:
        with open(sig, "wb") as f:
            f.write(sig_bytes)
        rc, out, err = _run(["ssh-keygen", "-Y", "verify", "-f", allowed_signers,
                            "-I", identity, "-n", namespace, "-s", sig],
                           input_bytes=message_bytes)
        if rc == 0:
            return {"ok": True, "reason": "signature verified"}
        return {"ok": False, "reason": (err.decode("utf-8", "replace").strip() or "verify rc=%d" % rc)}
    finally:
        _rmtree(d)


def make_allowed_signers(identity, pub_key_path, namespace, out_path):
    """Build an allowed_signers line: '<identity> namespaces="<ns>" <type> <base64>'."""
    with open(pub_key_path, "r", encoding="utf-8") as f:
        parts = f.read().strip().split()
    line = '%s namespaces="%s" %s\n' % (identity, namespace, " ".join(parts[:2]))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(line)
    return out_path


def _rmtree(d):
    try:
        for root, dirs, files in os.walk(d, topdown=False):
            for fn in files:
                try:
                    os.remove(os.path.join(root, fn))
                except Exception:
                    pass
            for dn in dirs:
                try:
                    os.rmdir(os.path.join(root, dn))
                except Exception:
                    pass
        os.rmdir(d)
    except Exception:
        pass


def self_test():
    if not have_ssh_keygen():
        return None
    d = tempfile.mkdtemp(prefix="audit_signtest_")
    try:
        key = os.path.join(d, "k")
        rc, out, err = _run(["ssh-keygen", "-t", "ed25519", "-f", key, "-N", "",
                            "-C", "audit-selftest", "-q"], input_bytes=b"")
        if rc != 0:
            raise RuntimeError("keygen failed: %s" % err.decode("utf-8", "replace"))
        ident, ns = "audit-selftest", "infra-audit-gate"
        allowed = make_allowed_signers(ident, key + ".pub", ns,
                                       os.path.join(d, "allowed_signers"))
        msg = b"4e2835c2b7650095511f71843bac273cf5c0d89f3e509630aef2d6c995471387"
        sig = sign_message(msg, key, ns)
        assert verify_message(msg, sig, allowed, ident, ns)["ok"], "verify good sig"
        assert not verify_message(msg + b"X", sig, allowed, ident, ns)["ok"], "tamper must fail"
        assert not verify_message(msg, sig, allowed, ident, "wrong-ns")["ok"], "wrong ns must fail"
    finally:
        _rmtree(d)
    return True


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        res = self_test()
    except AssertionError as e:
        sys.stdout.write("sign self-test FAILED: %s\n" % e)
        sys.exit(1)
    except Exception as e:
        sys.stdout.write("sign self-test ERROR: %s\n" % e)
        sys.exit(1)
    if res is None:
        sys.stdout.write("sign self-test SKIPPED: ssh-keygen not on PATH (validated at deploy)\n")
        sys.exit(2)
    sys.stdout.write("sign self-test OK (round-trip; tamper + wrong-namespace rejected)\n")
    sys.exit(0)
