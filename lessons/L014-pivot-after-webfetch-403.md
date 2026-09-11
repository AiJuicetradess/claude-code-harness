---
id: L014
title: "Pivot after first WebFetch 403/404 — don't retry same domain"
category: tool-usage
severity: high
status: active
created: 2026-03-17
last_triggered: 2026-03-16
times_violated: 1
times_checked: 0
tags: [webfetch, http-errors, wasted-cycles, subagents]
related_skills: []
---

**Rule:** When WebFetch returns 403 (Forbidden) or empty JS-rendered content on a domain, do NOT retry other URLs on the same domain. The entire domain is likely blocking automated access. Pivot immediately to: WebSearch, GitHub README, context7, or Firecrawl.

**Why:** In a research subagent, 8+ WebFetch calls were wasted on Coinbase docs (docs.cdp.coinbase.com) after the first 403. Each subsequent URL on the same domain also returned 403. The subagent also fetched CryptoPanic API docs and got only JavaScript config (no useful content). These wasted cycles delayed the research phase.

**Prevention:**
1. After first 403 on a domain: mark that domain as blocked for this session
2. Pivot to WebSearch with targeted queries to find the same info indirectly
3. Try GitHub READMEs (raw.githubusercontent.com) for library docs — these rarely block
4. Use context7 for popular libraries that have indexed docs
5. For JS-heavy pages: use Firecrawl (if available) or WebSearch instead of WebFetch
6. When dispatching research subagents: include this guidance in the prompt
