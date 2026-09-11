#!/usr/bin/env python
"""
snapshot.py -- versioned, provenance-stamped system-state snapshots + drift.

A snapshot is the output of bounds.evaluate (OK/SUSPECT/ALERT per metric, plus the
clock verdict) FROZEN with provenance: when it was taken, by which audit version,
for which box, and the exact raw readings it was derived from. Because every
snapshot is a bounds-validated artifact, DRIFT is well-defined: diff() compares two
snapshots and reports only state transitions and value changes -- it never invents
an alert from a raw delta, because the snapshots it compares have each already
earned (or been denied) the right to alarm (Validation Contract B4).

This module carries NO authority: it observes and records. It does not propose,
sign, or execute anything.

stdlib only; ASCII output; Windows-safe. Reads JSON with utf-8-sig (BOM tolerance).
Exit (direct, no args): 0 self-test OK, 1 failed.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import bounds  # noqa: E402

MANIFEST_NAME = "audit.config.json"
AUDIT_VERSION = "infra-audit/v1"
SNAPSHOT_VERSION = "audit-snapshot/v1"


def load_manifest(start):
    """Walk up from `start` to find audit.config.json. Returns (manifest, path) or
    (None, None). Mirrors propose.load_manifest (utf-8-sig tolerates a BOM)."""
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


def take_snapshot(readings, manifest, now):
    """Run bounds.evaluate over `readings` and freeze the result with provenance.

    The returned dict is the snapshot artifact: provenance + the bounds verdict +
    the raw readings that produced it (so a later diff can show from/to values, not
    just from/to states)."""
    evaluated = bounds.evaluate(readings, manifest, now)
    return {
        "provenance": {
            "ts": now,
            "audit_version": AUDIT_VERSION,
            "box_id": (manifest or {}).get("box_id"),
            "snapshot_version": SNAPSHOT_VERSION,
        },
        "clock": evaluated["clock"],
        "results": evaluated["results"],
        "counts": evaluated["counts"],
        "readings": readings,
    }


def _state_dir(manifest, start_root):
    """Resolve state_dir relative to the manifest root unless absolute (mirrors
    propose.py)."""
    sd = (manifest or {}).get("state_dir", ".audit")
    return sd if os.path.isabs(sd) else os.path.join(os.path.abspath(start_root), sd)


def write_snapshot(snapshot, manifest, start_root):
    """Persist a snapshot to <state_dir>/snapshots/<ts>.json. Returns the path.

    A snapshot only earns its keep by being diff-able against its predecessor, so a
    same-second collision must NOT silently overwrite an earlier snapshot. The
    spec'd <ts>.json is the normal path; if it already exists we append a short
    suffix (<ts>-1.json, ...) and the caller surfaces the collision rather than
    losing history."""
    sdir = os.path.join(_state_dir(manifest, start_root), "snapshots")
    os.makedirs(sdir, exist_ok=True)
    ts = snapshot.get("provenance", {}).get("ts", "unknown")
    out_path = os.path.join(sdir, "%s.json" % ts)
    suffix = 0
    while os.path.exists(out_path):
        suffix += 1
        out_path = os.path.join(sdir, "%s-%d.json" % (ts, suffix))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=True, indent=2)
    return out_path


def _metric_value(snapshot, metric):
    """Raw reading value for a metric in a snapshot (None if not present). The _ctx
    bag is relational context, not a metric, so it is never a comparison subject."""
    readings = snapshot.get("readings", {}) or {}
    return readings.get(metric)


def diff(old_snapshot, new_snapshot):
    """Drift between two bounds-validated snapshots.

    A metric is reported in `changed` if its state transitioned (e.g. OK->ALERT) OR
    its raw value changed. new_alerts / cleared_alerts isolate the transitions that
    matter most for a daily digest: what started alarming and what stopped."""
    old_results = (old_snapshot or {}).get("results", {}) or {}
    new_results = (new_snapshot or {}).get("results", {}) or {}
    metrics = set(old_results) | set(new_results)

    changed, new_alerts, cleared_alerts = [], [], []
    for metric in sorted(metrics):
        from_state = old_results.get(metric, {}).get("state")
        to_state = new_results.get(metric, {}).get("state")
        from_value = _metric_value(old_snapshot, metric)
        to_value = _metric_value(new_snapshot, metric)

        state_changed = from_state != to_state
        value_changed = from_value != to_value
        if state_changed or value_changed:
            changed.append({
                "metric": metric,
                "from_state": from_state,
                "to_state": to_state,
                "from_value": from_value,
                "to_value": to_value,
            })
        if to_state == bounds.ALERT and from_state != bounds.ALERT:
            new_alerts.append(metric)
        if from_state == bounds.ALERT and to_state != bounds.ALERT:
            cleared_alerts.append(metric)

    return {"changed": changed, "new_alerts": new_alerts, "cleared_alerts": cleared_alerts}


def _read_json_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _cmd_take(args):
    manifest, mpath = load_manifest(args.root)
    if not manifest:
        print(json.dumps({"ok": False, "reason": "no %s at or above %s (S4)" %
                          (MANIFEST_NAME, os.path.abspath(args.root))}, ensure_ascii=True))
        return 1
    readings = _read_json_file(args.readings)
    now = args.now if args.now is not None else int(time.time())
    snap = take_snapshot(readings, manifest, now)
    out_path = write_snapshot(snap, manifest, args.root)
    print(json.dumps({
        "ok": True,
        "manifest": mpath,
        "snapshot": out_path,
        "clock_state": snap["clock"]["state"],
        "counts": snap["counts"],
    }, ensure_ascii=True, indent=2))
    return 0


def _cmd_diff(args):
    old_snapshot = _read_json_file(args.a)
    new_snapshot = _read_json_file(args.b)
    print(json.dumps(diff(old_snapshot, new_snapshot), ensure_ascii=True, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description="infra-audit snapshot + drift (no authority)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_take = sub.add_parser("take", help="evaluate readings and write a snapshot")
    p_take.add_argument("--root", default=".")
    p_take.add_argument("--readings", required=True, help="path to a JSON readings dict")
    p_take.add_argument("--now", type=int, default=None, help="override epoch (else system time)")
    p_take.set_defaults(func=_cmd_take)

    p_diff = sub.add_parser("diff", help="report drift between two snapshot files")
    p_diff.add_argument("--root", default=".")  # accepted for symmetry; unused by diff
    p_diff.add_argument("--a", required=True, help="older snapshot JSON")
    p_diff.add_argument("--b", required=True, help="newer snapshot JSON")
    p_diff.set_defaults(func=_cmd_diff)

    args = ap.parse_args()
    sys.exit(args.func(args))


def self_test():
    now = 1800000000
    manifest = {
        "box_id": "fixture-box",
        "state_dir": ".audit",
        "clock": {"floor_epoch": bounds.CLOCK_FLOOR, "ceil_epoch": bounds.CLOCK_CEIL,
                  "max_skew_seconds": 300},
        "bounds": {"disk_pct": {"min": 0, "max": 100, "alert_above": 90}},
    }
    # Two synthetic readings: disk goes from nominal (40) to a real breach (95).
    before = {"disk_pct": 40, "proc_count": 100}
    after = {"disk_pct": 95, "proc_count": 100}

    snap_a = take_snapshot(before, manifest, now)
    snap_b = take_snapshot(after, manifest, now)

    # Provenance is stamped.
    prov = snap_a["provenance"]
    assert prov["ts"] == now, "snapshot: ts not stamped"
    assert prov["audit_version"] == AUDIT_VERSION, "snapshot: audit_version not stamped"
    assert prov["snapshot_version"] == SNAPSHOT_VERSION, "snapshot: snapshot_version not stamped"
    assert prov["box_id"] == "fixture-box", "snapshot: box_id not stamped"
    # Clock verdict is carried (here: plausible).
    assert snap_a["clock"]["state"] == bounds.OK, "snapshot: clock state not carried"
    # Raw readings are preserved for value-level drift.
    assert snap_a["readings"] == before, "snapshot: readings not preserved"
    # The breach is a real ALERT (95 > 90, in-bounds), proving bounds ran.
    assert snap_b["results"]["disk_pct"]["state"] == bounds.ALERT, "snapshot: disk not ALERT"

    d = diff(snap_a, snap_b)
    disk_changes = [c for c in d["changed"] if c["metric"] == "disk_pct"]
    assert len(disk_changes) == 1, "diff: disk_pct change not reported"
    c = disk_changes[0]
    # (a) value change is captured ...
    assert c["from_value"] == 40 and c["to_value"] == 95, "diff: value change wrong"
    # (b) ... and the OK->ALERT transition is captured and surfaced as a new alert.
    assert c["from_state"] == bounds.OK and c["to_state"] == bounds.ALERT, "diff: state transition wrong"
    assert d["new_alerts"] == ["disk_pct"], "diff: new_alerts missing disk_pct"
    # proc_count was unchanged in both value and state -> not reported.
    assert all(x["metric"] != "proc_count" for x in d["changed"]), "diff: stable metric leaked"

    # A clear (ALERT->OK) is reported as a cleared alert.
    d_clear = diff(snap_b, snap_a)
    assert d_clear["cleared_alerts"] == ["disk_pct"], "diff: cleared_alerts missing disk_pct"

    # Non-destructive write: two snapshots at the SAME ts must not clobber -- a lost
    # predecessor would make drift silently undetectable (regression guard).
    tmp = tempfile.mkdtemp(prefix="audit_snapshot_test_")
    try:
        p1 = write_snapshot(snap_a, manifest, tmp)
        p2 = write_snapshot(snap_b, manifest, tmp)
        assert p1 != p2, "write_snapshot: same-ts collision clobbered the earlier snapshot"
        on_disk = diff(_read_json_file(p1), _read_json_file(p2))
        assert on_disk["new_alerts"] == ["disk_pct"], "write_snapshot: round-trip drift lost"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # clean up the fixture tree
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
            sys.stdout.write("snapshot self-test FAILED: %s\n" % e)
            sys.exit(1)
        sys.stdout.write("snapshot self-test OK (provenance, clock, value-drift, OK->ALERT)\n")
        sys.exit(0)
    main()
