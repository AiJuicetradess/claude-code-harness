---
id: L024
title: "Verbal spec drift — substituting a precedent template for the user's plain-English intent"
category: communication
severity: critical
status: active
created: 2026-05-01
last_triggered: 2026-08-01
times_violated: 8
times_checked: 0
tags: [verbal-spec, intent, precedent, ambiguity, user-correction]
related_skills: [brainstorming]
---

**Rule:** When the user describes desired output behavior in plain English, do not silently substitute a "standard treatment" or precedent pattern. If your interpretation maps the user's language onto a known workflow (CapCut Ken Burns, MoviePy crossfade, "swing trade", "session checkpoint"), call out the substitution explicitly and ask for confirmation before implementing.

**Why:** Three sessions show the same shape: user describes a behavior, assistant pattern-matches it to a known precedent, and only the explicit "actually" or "no" reveals the gap. The danger is that the assistant's vocabulary is biased toward known templates — when the user reaches for a less-common output, the assistant's pattern-matcher silently rounds the request toward the nearest template, and the resulting work has to be redone.

**Prevention:**
1. Before implementing from a verbal spec: paraphrase the user's intent back without using any standard-template terminology, then explicitly name the closest precedent and ask "is this the same?"
2. When the user uses a phrase like "smooth," "natural," "full," "actual" — those are quality-axis words, not template names. Don't auto-map them to a CapCut/MoviePy/finance preset.
3. If you are about to use a known precedent name in your reply (Ken Burns, swing trade, parallax, slideshow), pause: was that *user's* word or *yours*? If yours, ask before building.
4. Watch for "actually" in the next user reply — it is the single most reliable signal you substituted a template for the user's actual intent. Treat the next instance of "actually" as a stop-and-re-elicit event.
5. For media output: when ambiguous between "transform existing asset" vs "generate new asset," default to asking, not picking.
