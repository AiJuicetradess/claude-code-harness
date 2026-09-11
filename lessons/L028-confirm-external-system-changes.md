---
id: L028
title: "Session-level plan approval doesn't authorize external-system changes — confirm each one"
category: communication
severity: critical
status: active
created: 2026-05-07
last_triggered: 2026-09-01
times_violated: 26
times_checked: 0
tags: [scope, permission, external-systems, wordpress, websites, plan-approval, scope-creep, pre-bash-guard]
related_skills: [brainstorming]
---

**Rule:** When a user approves a plan with "execute" / "approved" / "go", that approval covers internal-only actions (file edits, local scripts, code changes). It does NOT automatically authorize changes to **external systems**: deployed websites (WordPress, Webflow, Wix), public DNS, social media accounts, billing/payment configs, third-party SaaS dashboards, public APIs, or anything visible to people other than the user. Confirm each external-system change separately, even if it appeared in the plan.

**Why:** The system prompt already says "actions visible to others or that affect shared state" need confirmation, but plan-mode approvals tend to override that caution implicitly — the user said "execute the plan, make no mistakes" and the assistant interprets "the plan" as the whole bundle. The user often hasn't mentally separated "fix the n8n workflow" (safe, reversible) from "modify our live WordPress page" (visible to customers, sometimes intentional state, hard to revert). The user catches this only when they notice the change after the fact, and the correction always carries an irritated tone ("wait, that was there by design").

**Prevention:**
1. When drafting a plan that mixes internal + external changes: split it into **two columns** — *internal-only (safe to batch)* vs. *external-system (each needs separate go-ahead)*. Show the user this split before asking for approval.
2. When the user gives a global approval: re-read the plan's external-system items and explicitly call out each one before doing it: *"Plan item #4 modifies the live WordPress site — should I proceed with that specifically?"*
3. If a planned action would create or remove pages, posts, redirects, DNS entries, social posts, scheduled emails, or paid-ad campaigns: STOP at execution time and ask. These are the highest-blast-radius items.
4. "Make no mistakes" = "be careful," not "skip confirmations." Treat such phrases as raising the confirmation bar, not lowering it.
5. If you discover unexpected state on an external system (a "Location Guide" page you don't recognize, a redirect rule, a cron job): **investigate before deleting/overwriting** — it may be the user's intentional state. Echoes the executing-actions-with-care rule in the system prompt.

**Hook enforcement (2026-08-15, REMINDER-ONLY):** `pre_bash_guard.py` injects a once-per-session NON-blocking reminder when a command first reaches a remote system (ssh/scp/sftp/rsync, or curl with a mutating -X verb): "session-level approval does not authorize external-system changes — confirm individually." The judgment call itself cannot be a deterministic block (most ssh here is legitimate deploy work); primary enforcement remains behavioral + the auto-mode classifier, which has caught every attempt since 2026-05-16.

**Hook enforcement upgrade (2026-08-25, ASK GATE):** high-blast-radius remote mutations now emit `permissionDecision: "ask"` per command — ssh command tails containing rm -rf / systemctl stop|restart|disable / docker rm|stop|kill|restart / iptables|nft|ufw / shred / chown / reboot|shutdown / crontab -r / kill(all) / mkfs / dd if= / DROP|ALTER|TRUNCATE, plus `curl -X DELETE` anywhere. The pre-existing DESTRUCTIVE hard-deny list still outranks the ask gate (absolute-path rm -rf and DROP TABLE stay denied outright). Routine ssh reads/deploys remain un-gated; the once-per-session reminder stays. Tests in `test_promoted_guards.py`.

**HOOK-TUNING TODO (2026-09-01, user deciding):** the ask-gate missed the CRM writes twice over: (a) the POST lived inside a script piped over ssh (ssh host bash -s < file), so the guard never saw a verb; (b) POST/PUT/PATCH to third-party APIs only trip the once-per-session reminder, never the gate. Options on the table: scan the local file when a command pipes a script into ssh; ask on mutating verbs aimed at third-party API hosts (a CRM, Airtable, Meta Graph) while leaving VPS-local deploy traffic un-gated. Recommended both. Not implemented pending ruling.
