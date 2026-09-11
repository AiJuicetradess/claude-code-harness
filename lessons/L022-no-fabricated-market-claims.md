---
id: L022
title: "Never claim market/data behavior from synthesis — cite the source or run a tool"
category: assumptions
severity: high
status: active
created: 2026-05-01
last_triggered: 2026-04-22
times_violated: 2
times_checked: 0
tags: [fabrication, trading, market-data, verification, cove]
related_skills: [cove-verification]
---

**Rule:** Any factual claim about market behavior, ticker activity, or external data (e.g., "SoFi/PLTR/HOOD produce tradable setups routinely", a property tax rate, a comp's nightly rate) must come from a fresh tool call (options-chain scrape, rentals-data fetch, exchange API, scraper) — never from synthesis of prior chats or training data. State the source URL/tool-call alongside the claim.

**Why:** In Session 73940990 the assistant proposed a watchlist asserting that SoFi/PLTR/HOOD "produce tradable setups routinely." User pushed back directly: *"how do you actually know that? Is that just information that you're synthesizing from previous chats with other people, or is that actual real data that you've come across from the actual options chain?"* This pattern keeps recurring across the user's sessions: Mary's $4.5K vs actual $22K, Belize property tax overstated 4x, Vancouver math implying a $4M condo. Synthesized "market knowledge" is unreliable and the user catches it consistently.

**Prevention:**
1. Before any claim like "X is liquid", "Y has tradable setups", "this is normal range": run an actual scan/fetch and cite the source
2. For watchlists/comps: build them from current data (options chain scan, rentals-data pull, recent transcripts) — never from memory
3. If a tool is unavailable, say so explicitly ("I don't have a fresh options-chain reading; this watchlist is a hypothesis, not a fact")
4. When the user asks "how do you know that?" — that's a signal you fabricated; treat it as a stop-and-verify event
5. Distinguish "the framework recommends liquid mid-cap names" (general principle) from "SoFi was active yesterday" (specific claim that needs a source)
