#!/usr/bin/env python
"""
bounds.py -- the three-state metric validator (OK / SUSPECT / ALERT).

An alert is a CLAIM. This module makes a reading EARN the right to alarm by first
passing a plausibility test. A value outside physical / manifest bounds is a sensor,
parse, or clock bug -> SUSPECT (surface it, do NOT alert). Only a PLAUSIBLE value
that also breaches a real threshold becomes an ALERT.

The reference clock is validated FIRST: if the box clock is implausible, every
time-derived metric is quarantined (SUSPECT), never alarmed -- the precise fix for
the epoch bug that produced false alarms. Reuses the swarm-verify
plausible_epoch_bounds primitive.

Pure logic; stdlib only; ASCII output; Windows-safe.
Exit (direct): 0 self-test OK, 1 failed.
"""
import sys

OK = "OK"
SUSPECT = "SUSPECT"
ALERT = "ALERT"

# Defaults reused from swarm-verify (overridable via manifest 'clock').
CLOCK_FLOOR = 1735689600   # 2025-01-01 UTC
CLOCK_CEIL = 1893456000    # 2030-01-01 UTC
MAX_SKEW = 300


def plausible_epoch(ts, floor=CLOCK_FLOOR, ceil=CLOCK_CEIL, now=None, skew=MAX_SKEW):
    """True if ts is a believable epoch: within [floor,ceil] and not in the future
    beyond a small skew."""
    if not isinstance(ts, int):
        return False
    if ts < floor or ts > ceil:
        return False
    if now is not None and ts > now + skew:
        return False
    return True


def clock_state(now, clock_cfg=None):
    """Validate the reference clock itself. A SUSPECT clock means the caller must
    quarantine every time-derived metric."""
    cfg = clock_cfg or {}
    floor = cfg.get("floor_epoch", CLOCK_FLOOR)
    ceil = cfg.get("ceil_epoch", CLOCK_CEIL)
    if not isinstance(now, int) or now < floor or now > ceil:
        return SUSPECT, "reference clock implausible (now=%s outside [%s,%s])" % (now, floor, ceil)
    return OK, "clock plausible"


def _result(state, reason):
    return {"state": state, "reason": reason}


def _epoch_kwargs(clock_cfg, now):
    cfg = clock_cfg or {}
    return {
        "floor": cfg.get("floor_epoch", CLOCK_FLOOR),
        "ceil": cfg.get("ceil_epoch", CLOCK_CEIL),
        "now": now,
        "skew": cfg.get("max_skew_seconds", MAX_SKEW),
    }


def evaluate_metric(name, value, spec, ctx):
    """Classify one metric. ctx carries: now, clock_ok (bool), clock_cfg, and any
    relational fields (equity, disk_total, disk_used, disk_avail, ...)."""
    spec = spec or {}
    clock_ok = ctx.get("clock_ok", True)
    now = ctx.get("now")
    clock_cfg = ctx.get("clock_cfg")

    # epoch / timestamp metrics
    if name.endswith("_ts") or name == "epoch":
        if not plausible_epoch(value, **_epoch_kwargs(clock_cfg, now)):
            return _result(SUSPECT, "implausible epoch: %s" % value)
        return _result(OK, "epoch plausible")

    # disk percentage
    if name == "disk_pct":
        lo, hi = spec.get("min", 0), spec.get("max", 100)
        if not isinstance(value, (int, float)) or value < lo or value > hi:
            return _result(SUSPECT, "disk_pct out of [%s,%s]: %s" % (lo, hi, value))
        total, used, avail = ctx.get("disk_total"), ctx.get("disk_used"), ctx.get("disk_avail")
        if total is not None and used is not None and avail is not None:
            if total <= 0 or abs((used + avail) - total) > max(1, int(0.02 * total)):
                return _result(SUSPECT, "disk relational check failed (used+avail != total)")
        thr = spec.get("alert_above")
        if thr is not None and value > thr:
            return _result(ALERT, "disk_pct %s > %s" % (value, thr))
        return _result(OK, "disk_pct nominal")

    # process count
    if name == "proc_count":
        lo, hi = spec.get("min", 0), spec.get("max", 100000)
        if not isinstance(value, int) or value < lo or value > hi:
            return _result(SUSPECT, "proc_count out of [%s,%s]: %s" % (lo, hi, value))
        return _result(OK, "proc_count nominal")

    # backup age in hours -- TIME-DERIVED: quarantine if the clock is not trustworthy
    if name == "backup_age_hours":
        if not clock_ok:
            return _result(SUSPECT, "clock unreliable; backup age not trustworthy")
        if not isinstance(value, (int, float)) or value < 0:
            return _result(SUSPECT, "backup_age_hours implausible: %s" % value)
        thr = spec.get("max_age_hours_alert")
        if thr is not None and value > thr:
            return _result(ALERT, "backup age %sh > %sh" % (value, thr))
        return _result(OK, "backup age nominal")

    # pnl plausibility (needs equity in ctx)
    if name == "pnl":
        equity = ctx.get("equity")
        k = spec.get("abs_max_x_equity")
        if equity is None or equity <= 0:
            return _result(SUSPECT, "no/invalid equity for pnl plausibility")
        if isinstance(k, (int, float)) and abs(value) > k * equity:
            return _result(SUSPECT, "pnl %s implausible vs equity %s (x%s)" % (value, equity, k))
        thr = spec.get("alert_drawdown_below")
        if thr is not None and value < thr:
            return _result(ALERT, "pnl %s < drawdown limit %s" % (value, thr))
        return _result(OK, "pnl plausible")

    # unknown metric: cannot bound -> SUSPECT (never silently alert on the unboundable)
    return _result(SUSPECT, "no bounds defined for metric '%s'" % name)


def evaluate(readings, manifest, now):
    """readings: {metric_name: value}, plus optional relational fields under
    readings['_ctx']. Returns clock state + per-metric results + counts."""
    clock_cfg = (manifest or {}).get("clock")
    bounds = (manifest or {}).get("bounds", {})
    cstate, creason = clock_state(now, clock_cfg)
    ctx = dict(readings.get("_ctx", {}))
    ctx.update({"now": now, "clock_ok": (cstate == OK), "clock_cfg": clock_cfg})
    results, counts = {}, {OK: 0, SUSPECT: 0, ALERT: 0}
    for name, value in readings.items():
        if name == "_ctx":
            continue
        r = evaluate_metric(name, value, bounds.get(name, {}), ctx)
        results[name] = r
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return {"clock": {"state": cstate, "reason": creason}, "results": results, "counts": counts}


def self_test():
    now = 1800000000
    mani = {
        "clock": {"floor_epoch": CLOCK_FLOOR, "ceil_epoch": CLOCK_CEIL, "max_skew_seconds": 300},
        "bounds": {
            "disk_pct": {"min": 0, "max": 100, "alert_above": 90},
            "proc_count": {"min": 0, "max": 100000},
            "backup_age_hours": {"max_age_hours_alert": 26},
        },
    }
    # F5: out-of-bounds -> SUSPECT, never ALERT
    assert evaluate({"disk_pct": 4000}, mani, now)["results"]["disk_pct"]["state"] == SUSPECT, "F5 disk suspect"
    # in-bounds + breach -> ALERT
    assert evaluate({"disk_pct": 95}, mani, now)["results"]["disk_pct"]["state"] == ALERT, "disk alert"
    # in-bounds nominal -> OK
    assert evaluate({"disk_pct": 40}, mani, now)["results"]["disk_pct"]["state"] == OK, "disk ok"
    # F6: bad clock -> time-derived metric quarantined (SUSPECT) not ALERT
    r = evaluate({"backup_age_hours": 99}, mani, 100)
    assert r["clock"]["state"] == SUSPECT, "F6 clock suspect"
    assert r["results"]["backup_age_hours"]["state"] == SUSPECT, "F6 backup quarantined"
    # good clock + stale backup -> ALERT
    assert evaluate({"backup_age_hours": 99}, mani, now)["results"]["backup_age_hours"]["state"] == ALERT, "backup alert"
    # epoch plausibility
    assert plausible_epoch(now, now=now) is True, "epoch ok"
    assert plausible_epoch(100) is False, "epoch floor"
    assert plausible_epoch(now + 10000, now=now) is False, "epoch future"
    return True


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        self_test()
    except AssertionError as e:
        sys.stdout.write("bounds self-test FAILED: %s\n" % e)
        sys.exit(1)
    sys.stdout.write("bounds self-test OK\n")
    sys.exit(0)
