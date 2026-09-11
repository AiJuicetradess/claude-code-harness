---
id: L020
title: "Prototype with a minimal test before building a full pipeline"
category: workflow
severity: high
status: active
created: 2026-04-06
last_triggered: 2026-04-06
times_violated: 3
times_checked: 0
tags: [prototyping, pipeline, validation, iteration]
related_skills: [brainstorming]
---

**Rule:** Before building a full production pipeline (video processing, data ETL, model inference chain), validate the tool chain with a minimal 5-second or single-item test. Confirm core assumptions (API compatibility, output quality, format support) before investing in the full implementation.

**Why:** Two sessions had 3+ complete pipeline rewrites because fundamental assumptions about tool capabilities weren't validated upfront. One session rewrote a reel production pipeline 3 times (ffmpeg -> MoviePy -> MoviePy+XTTS) because each tool's limitations were only discovered during full production runs. Another session spent 14 tool calls retrying voice cloning with MiniMax before discovering it had strict file format requirements — a single test with a 1-second clip would have revealed this immediately.

**Prevention:**
1. Before committing to a tool chain: run a minimal test (5-second clip, single data point, one API call) to validate format compatibility and output quality
2. When the first attempt produces poor quality: investigate the root cause before rewriting the pipeline. Is it the tool, the parameters, or the approach?
3. When switching to a new API/model: check its actual input constraints (file formats, sizes, required params) before integrating it
4. Budget one exploration/prototyping phase before the implementation phase — don't combine them
