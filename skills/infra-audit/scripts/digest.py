#!/usr/bin/env python
"""
digest.py -- the NOTIFY-ONLY daily digest. It carries NO authority.

It reads a bounds-validated snapshot (plus any pending proposals and ledger status)
and renders a human summary: counts, the ALERTs, the SUSPECTs in their OWN section
("a sensor may be lying -- look"), the pending approvals a human still owes, and a
one-line drift summary. It cannot propose, sign, or execute -- the worst a
compromised digest can do is render text.

Two hard rules this module enforces:
  1. Agent-authored strings (reasons) are run through canon.sanitize_text before
     they are ever placed in the digest -- a homoglyph / ANSI / RTL-override reason
     cannot misrepresent what the operator reads.
  2. The Discord webhook is referenced ONLY by the NAME of an env var
     (manifest.digest.discord_webhook_env). The secret URL is read from the
     environment at send time and is NEVER printed, logged, written, or returned.
     Only the env-var NAME may ever appear in output (L010 / no hardcoded secrets).
     The CLI defaults to DRY-RUN; an explicit --send is required to actually POST.

stdlib only; ASCII output; Windows-safe. Reads JSON with utf-8-sig (BOM tolerance).
Exit (direct, no args): 0 self-test OK, 1 failed.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import canon  # noqa: E402
import bounds  # noqa: E402

MANIFEST_NAME = "audit.config.json"
POST_TIMEOUT_SECONDS = 8


def load_manifest(start):
    """Walk up from `start` to find audit.config.json. Returns (manifest, path) or
    (None, None)."""
    d = os.path.abspath(start)
    seen = set()
    while d and d not in seen:
        seen.add(d)
        p = os.path.join(d, MANIFEST_NAME)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8-sig") as f:
                return json.load(f), p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None, None


def _collect(results, want_state):
    """Metrics in a given state, with their (sanitized) reasons, sorted by name."""
    out = []
    for name in sorted(results or {}):
        r = results[name] or {}
        if r.get("state") == want_state:
            out.append({"metric": name, "reason": canon.sanitize_text(r.get("reason", ""))})
    return out


def _drift_summary(drift):
    """One-line ASCII summary of a snapshot.diff() result (or 'no prior snapshot')."""
    if not drift:
        return "no prior snapshot to compare"
    new_alerts = drift.get("new_alerts", [])
    cleared = drift.get("cleared_alerts", [])
    changed = drift.get("changed", [])
    return "drift: %d changed, %d new alert(s) [%s], %d cleared [%s]" % (
        len(changed),
        len(new_alerts), ",".join(new_alerts) if new_alerts else "-",
        len(cleared), ",".join(cleared) if cleared else "-",
    )


def _pending_view(pending_proposals):
    """Normalize pending proposals into display rows. Each proposal's reason is
    agent-authored, so it is sanitized; the fingerprint is the thing a human
    actually authorizes against."""
    rows = []
    for p in pending_proposals or []:
        payload = p.get("payload", {}) if isinstance(p, dict) else {}
        rows.append({
            "proposal_id": payload.get("proposal_id", p.get("proposal_id", "?")),
            "action": canon.sanitize_text(payload.get("action_type", "?")),
            "box_id": canon.sanitize_text(payload.get("box_id", "?")),
            "items": len(payload.get("enumerated_items", [])),
            "reason": canon.sanitize_text(payload.get("reason", "")),
            "fingerprint": p.get("fingerprint", "?") if isinstance(p, dict) else "?",
        })
    return rows


def build_digest(snapshot, pending_proposals, ledger_status, drift=None):
    """Assemble the notify-only digest structure + a text rendering.

    `snapshot` is a snapshot.take_snapshot() artifact. `pending_proposals` is a list
    of proposal records (propose.py output). `ledger_status` is an opaque dict the
    ledger module supplies (rendered as-is, no authority inferred from it)."""
    snapshot = snapshot or {}
    results = snapshot.get("results", {})
    counts = snapshot.get("counts", {bounds.OK: 0, bounds.SUSPECT: 0, bounds.ALERT: 0})
    clock = snapshot.get("clock", {"state": "?", "reason": ""})
    box_id = snapshot.get("provenance", {}).get("box_id", "?")

    alerts = _collect(results, bounds.ALERT)
    suspect = _collect(results, bounds.SUSPECT)
    pending = _pending_view(pending_proposals)

    digest = {
        "box_id": box_id,
        "generated_ts": int(time.time()),
        "clock": {"state": clock.get("state"), "reason": canon.sanitize_text(clock.get("reason", ""))},
        "counts": {
            bounds.OK: counts.get(bounds.OK, 0),
            bounds.SUSPECT: counts.get(bounds.SUSPECT, 0),
            bounds.ALERT: counts.get(bounds.ALERT, 0),
        },
        "alerts": alerts,
        "suspect": suspect,
        "pending_approvals": pending,
        "drift_summary": _drift_summary(drift),
        "ledger_status": ledger_status or {},
    }
    digest["text"] = render_digest(digest)
    return digest


def render_digest(digest):
    """ASCII text rendering. SUSPECT gets its OWN section so a possibly-lying sensor
    is never silently folded into the alert count."""
    c = digest["counts"]
    lines = []
    lines.append("=== infra-audit daily digest (NOTIFY-ONLY -- carries no authority) ===")
    lines.append("BOX    : %s" % digest["box_id"])
    lines.append("CLOCK  : %s (%s)" % (digest["clock"]["state"], digest["clock"]["reason"]))
    lines.append("COUNTS : OK=%d  SUSPECT=%d  ALERT=%d" % (
        c[bounds.OK], c[bounds.SUSPECT], c[bounds.ALERT]))
    lines.append("DRIFT  : %s" % digest["drift_summary"])

    lines.append("")
    lines.append("--- ALERTS (plausible value breached a real threshold) ---")
    if digest["alerts"]:
        for a in digest["alerts"]:
            lines.append("  [ALERT] %s : %s" % (a["metric"], a["reason"]))
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("--- SUSPECT (sensor may be lying -- look; NOT alarmed) ---")
    if digest["suspect"]:
        for s in digest["suspect"]:
            lines.append("  [SUSPECT] %s : %s" % (s["metric"], s["reason"]))
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("--- PENDING APPROVALS (a human still owes a signature) ---")
    if digest["pending_approvals"]:
        for p in digest["pending_approvals"]:
            lines.append("  [PENDING] %s  action=%s box=%s items=%d" % (
                p["proposal_id"], p["action"], p["box_id"], p["items"]))
            lines.append("            reason: %s" % p["reason"])
            lines.append("            fingerprint: %s" % p["fingerprint"])
    else:
        lines.append("  (none)")

    if digest["ledger_status"]:
        lines.append("")
        lines.append("--- LEDGER ---")
        lines.append("  %s" % canon.sanitize_text(json.dumps(digest["ledger_status"], sort_keys=True)))

    lines.append("")
    return "\n".join(lines)


def post(text, manifest, send=False):
    """Deliver the digest text to the configured Discord webhook.

    The webhook URL is resolved ONLY from the env var whose NAME lives in
    manifest.digest.discord_webhook_env. Return-dict and any output name the env var
    ONLY -- never the URL itself.

    - No env-var name configured        -> {"sent": False, "reason": "..."} (no send)
    - Env var unset                      -> {"sent": False, "reason": "env <NAME> not set; dry-run"}
    - Env var set but send=False (default)-> dry-run, do NOT POST
    - Env var set and send=True          -> POST via urllib (short timeout)
    """
    name = ((manifest or {}).get("digest", {}) or {}).get("discord_webhook_env")
    if not name:
        return {"sent": False, "reason": "no digest.discord_webhook_env configured; dry-run"}

    url = os.environ.get(name)
    if not url:
        return {"sent": False, "reason": "env %s not set; dry-run" % name, "env": name}

    if not send:
        # Secret IS present, but the CLI must opt in. We deliberately do not echo or
        # confirm the URL -- only that the named env var is populated.
        return {"sent": False, "reason": "dry-run (env %s set; pass --send to deliver)" % name,
                "env": name}

    try:
        data = json.dumps({"content": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=POST_TIMEOUT_SECONDS) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
        return {"sent": True, "status": status, "env": name}
    except Exception as e:
        # The exception text could conceivably echo the URL (urllib often includes it
        # in HTTPError messages). Report only the exception TYPE so the secret can
        # never leak through an error path.
        return {"sent": False, "reason": "post failed (%s); see box logs" % type(e).__name__,
                "env": name}


def _read_json_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="infra-audit notify-only digest (no authority)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--snapshot", required=True, help="path to a snapshot JSON")
    ap.add_argument("--pending", default=None, help="optional path to a JSON list of proposals")
    ap.add_argument("--drift", default=None, help="optional path to a snapshot.diff() JSON")
    ap.add_argument("--send", action="store_true",
                    help="actually POST to the configured webhook (default: dry-run)")
    args = ap.parse_args()

    manifest, _ = load_manifest(args.root)
    snapshot = _read_json_file(args.snapshot)
    pending = _read_json_file(args.pending) if args.pending else []
    drift = _read_json_file(args.drift) if args.drift else None

    digest = build_digest(snapshot, pending, ledger_status=None, drift=drift)
    sys.stdout.write(digest["text"] + "\n")

    result = post(digest["text"], manifest, send=args.send)
    sys.stdout.write("--- delivery ---\n%s\n" % json.dumps(result, ensure_ascii=True))
    return 0


def self_test():
    secret_env = "TESTHOOK"
    secret_url = "https://secret/AAA"
    os.environ[secret_env] = secret_url
    try:
        manifest = {"digest": {"discord_webhook_env": secret_env, "cadence": "daily"}}
        # Synthetic snapshot: one real ALERT, one SUSPECT, one OK.
        snapshot = {
            "provenance": {"box_id": "fixture-box", "ts": 1800000000},
            "clock": {"state": bounds.OK, "reason": "clock plausible"},
            "results": {
                "disk_pct": {"state": bounds.ALERT, "reason": "disk_pct 95 > 90"},
                "backup_age_hours": {"state": bounds.SUSPECT, "reason": "clock unreliable; backup age not trustworthy"},
                "proc_count": {"state": bounds.OK, "reason": "proc_count nominal"},
            },
            "counts": {bounds.OK: 1, bounds.SUSPECT: 1, bounds.ALERT: 1},
        }
        pending = [{
            "payload": {"proposal_id": "nonce-xyz", "action_type": "delete",
                        "box_id": "fixture-box", "reason": "rotate old logs",
                        "enumerated_items": [{"path": "/var/log/a.gz"}]},
            "fingerprint": "deadbeef",
        }]
        drift = {"changed": [{"metric": "disk_pct"}], "new_alerts": ["disk_pct"], "cleared_alerts": []}

        digest = build_digest(snapshot, pending, ledger_status={"head": "abc123"}, drift=drift)

        # Counts pass through faithfully.
        assert digest["counts"] == {bounds.OK: 1, bounds.SUSPECT: 1, bounds.ALERT: 1}, "digest: counts wrong"
        # The SUSPECT section exists AND lists the suspect metric.
        assert "SUSPECT (sensor may be lying" in digest["text"], "digest: SUSPECT section missing"
        assert "[SUSPECT] backup_age_hours" in digest["text"], "digest: suspect metric not listed"
        # The ALERT is present; the suspect is NOT counted as an alert.
        assert "[ALERT] disk_pct" in digest["text"], "digest: alert metric not listed"
        assert len(digest["alerts"]) == 1, "digest: suspect leaked into alerts"
        # Pending approval is surfaced with its fingerprint.
        assert "nonce-xyz" in digest["text"] and "deadbeef" in digest["text"], "digest: pending not shown"

        # SECRET CONTAINMENT: the URL must appear NOWHERE in the rendered digest.
        assert secret_url not in digest["text"], "digest: SECRET URL leaked into text"

        # post() in dry-run (env set, send defaults False): no send, URL never returned,
        # only the env-var NAME may appear.
        res = post(digest["text"], manifest)
        blob = json.dumps(res)
        assert res["sent"] is False, "post: should not send by default"
        assert secret_url not in blob, "post: SECRET URL leaked into result dict"
        assert secret_env in blob, "post: env-var NAME should be reportable"

        # Env-unset path: dry-run reason names the env var, not a URL.
        del os.environ[secret_env]
        res2 = post("x", manifest)
        assert res2["sent"] is False and secret_env in json.dumps(res2), "post: unset env path"
        assert secret_url not in json.dumps(res2), "post: SECRET URL leaked on unset path"

        # No env configured at all -> graceful dry-run.
        res3 = post("x", {"digest": {}})
        assert res3["sent"] is False, "post: missing env-name config should dry-run"
    finally:
        os.environ.pop(secret_env, None)  # clean up regardless of assertion outcome
    return True


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) == 1:
        try:
            self_test()
        except AssertionError as e:
            sys.stdout.write("digest self-test FAILED: %s\n" % e)
            sys.exit(1)
        sys.stdout.write("digest self-test OK (counts, SUSPECT section, no-secret-leak, dry-run default)\n")
        sys.exit(0)
    sys.exit(main())
