---
id: L025
title: "Subjective-quality iteration loops — keep-trying without changing the variable"
category: workflow
severity: critical
status: active
created: 2026-05-01
last_triggered: 2026-04-10
times_violated: 6
times_checked: 0
tags: [iteration, subjective-quality, model-swap, voice, video, parameter-sweep]
related_skills: [brainstorming]
---

**Rule:** When the user rejects an output for subjective quality reasons (voice sounds robotic, skin too smooth, accent wrong, video looks cheap), do not iterate by re-running the same model with tweaked parameters more than twice. After two parameter rejections on the same dimension, stop, present the user with three explicit options (different model, different prompt structure, different pipeline architecture), and ask which axis to vary.

**Why:** Subjective-quality issues rarely yield to parameter sweep — they usually need a model or method change. Continuing to tune the same knob after two rejections almost always means the model fundamentally cannot do what the user is asking for, and the right move is to escalate to alternatives, not regen. Four sessions burned 6-22 cycles each on subjective-quality regen without the assistant ever proposing a different upstream model.

This is structurally distinct from L009 (e2e flow, which is about whether output exists) and L020 (prototype-before-pipeline, which is about feasibility). L025 is "I have output, the user keeps rejecting it on quality, and I keep adjusting the same lever."

**Prevention:**
1. After two rejections on the same subjective-quality dimension (voice naturalness, skin texture, animation smoothness, accent accuracy): stop iterating, present three explicit alternatives across different axes (different model / different prompt template / different pipeline stage).
2. Track which knob you turned each iteration. If you have turned the same knob (TTS params, prompt phrasing, denoise strength) twice without user satisfaction, do not turn it a third time.
3. For accent / pronunciation issues: a parameter sweep on Chatterbox cannot fix a model that wasn't trained on Dominican Spanish. Move to a different model or to a manual phonetic respelling pass before re-running.
4. Distinguish "the model can almost do it" (parameter-tweakable) from "the model cannot do it" (architectural). Replicate model failure patterns are mostly the latter — the right fix is model swap, not param tune.
5. Time-box: if you have spent more than 30 minutes or 6 tool calls on the same subjective-quality dimension, escalate to user with options, not another regen.
