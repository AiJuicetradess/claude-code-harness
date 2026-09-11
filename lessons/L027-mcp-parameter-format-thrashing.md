---
id: L027
title: "Stop thrashing on MCP tool parameter formats — pivot to local equivalent after 3 failed shapes"
category: tool-usage
severity: high
status: active
created: 2026-05-07
last_triggered: 2026-05-03
times_violated: 1
times_checked: 0
tags: [mcp, parameter-format, schema-mismatch, kali, thrashing, pivot]
related_skills: [cove-verification]
---

**Rule:** When an MCP tool rejects 3 different parameter shapes for the same call, stop iterating and pivot. Either (a) use a local-equivalent tool (PowerShell/native CLI), (b) ask the user for the correct schema, or (c) report the tool as broken. Do not keep guessing format variations.

**Why:** The cost of iterating past 3 failed format guesses grows fast — each retry is 1 round-trip, the error messages rarely converge to a workable shape (because the underlying issue is often a schema/implementation mismatch in the MCP server, not user error), and the alternative (a native command) usually exists and works on the first try. In one session, 10 retries on `mcp__kali__nmap` with progressively-more-creative `kwargs` strings all failed because the tool's JSON schema (`kwargs: string`) didn't match its implementation (which dict-keyed `kwargs['target']`). No format the assistant could craft would have worked — the tool itself was broken.

**Prevention:**
1. After 2 different parameter shapes fail with **the same error class** (e.g., both raise `KeyError: 'target'`): treat it as a tool bug, not a syntax issue. Stop guessing.
2. After 3 failed shapes total (even with different errors): pivot. The signal-to-noise on retries is too low.
3. Read the tool's schema once with ToolSearch (`select:<tool_name>`) — if the schema declares one shape (e.g., `kwargs: string`) but the error implies another (e.g., `KeyError`), that's a schema/implementation mismatch and no input will satisfy both.
4. Pivot targets, in order of preference:
   - Native local tool (PowerShell `Get-NetTCPConnection`, `Test-NetConnection`, `Resolve-DnsName` for nmap-equivalent recon)
   - Different MCP tool with similar capability
   - Ask user to run the equivalent command manually and paste output
5. When starting work that depends on an unfamiliar MCP tool: do a **2-line probe** with the simplest possible call before building a multi-step pipeline around it. (Echoes L020 — prototype with minimal test before full pipeline.)
