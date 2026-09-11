"""Non-mutating test of the select_next cursor (temp, delete after)."""
import _mark_reflected as M

recs = M.read_records()
print("total records:", len(recs))
print("backlog_count:", M.backlog_count(recs))

sel = M.select_next_records(40, recs)
ts = [o.get("timestamp", "") for o in sel]
ids = [o["session_id"] for o in sel]
print("selected:", len(sel))
print("first ts:", ts[0], "| last ts:", ts[-1])
print("PASS newest-first:", ts == sorted(ts, reverse=True))
print("PASS all reflected False:", all(o.get("reflected") is False for o in sel))
print("PASS none reflection-type:", all(o.get("type") != "reflection" for o in sel))
print("PASS all have session_id:", all(o.get("session_id") for o in sel))
print("PASS unique ids:", len(set(ids)) == len(ids))
print("PASS deterministic:", M.select_next(40, recs) == M.select_next(40, recs))

# idempotent advance: flip batch-1 ids to true in-memory, next select must be disjoint
first = set(ids)
for _, o in recs:
    if isinstance(o, dict) and o.get("session_id") in first:
        o["reflected"] = True
nxt = M.select_next(40, recs)
print("PASS advance disjoint:", first.isdisjoint(set(nxt)))
print("advance count:", len(nxt), "| backlog after sim mark:", M.backlog_count(recs))
