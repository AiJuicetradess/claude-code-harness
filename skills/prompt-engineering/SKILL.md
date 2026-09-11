---
name: prompt-engineering
description: Expert guide on prompt engineering for text/LLM, AI image generation (Gemini/Imagen, GPT-Image, Midjourney, Stable Diffusion, Flux), and video generation (Sora, Runway, Pika, Kling, Luma, Veo). Use when user wants to improve prompts, learn prompting strategies, generate image/video prompts, or debug agent behavior.
---

# Prompt Engineering Patterns

Advanced prompt engineering techniques to maximize LLM performance, reliability, and controllability.

## Core Capabilities

### 1. Few-Shot Learning

Teach the model by showing examples instead of explaining rules. Include 2-5 input-output pairs that demonstrate the desired behavior. Use when you need consistent formatting, specific reasoning patterns, or handling of edge cases. More examples improve accuracy but consume tokens—balance based on task complexity.

**Example:**

```markdown
Extract key information from support tickets:

Input: "My login doesn't work and I keep getting error 403"
Output: {"issue": "authentication", "error_code": "403", "priority": "high"}

Input: "Feature request: add dark mode to settings"
Output: {"issue": "feature_request", "error_code": null, "priority": "low"}

Now process: "Can't upload files larger than 10MB, getting timeout"
```

### 2. Chain-of-Thought Prompting

Request step-by-step reasoning before the final answer. Add "Let's think step by step" (zero-shot) or include example reasoning traces (few-shot). Use for complex problems requiring multi-step logic, mathematical reasoning, or when you need to verify the model's thought process. Improves accuracy on analytical tasks by 30-50%.

**Example:**

```markdown
Analyze this bug report and determine root cause.

Think step by step:

1. What is the expected behavior?
2. What is the actual behavior?
3. What changed recently that could cause this?
4. What components are involved?
5. What is the most likely root cause?

Bug: "Users can't save drafts after the cache update deployed yesterday"
```

### 3. Prompt Optimization

Systematically improve prompts through testing and refinement. Start simple, measure performance (accuracy, consistency, token usage), then iterate. Test on diverse inputs including edge cases. Use A/B testing to compare variations. Critical for production prompts where consistency and cost matter.

**Example:**

```markdown
Version 1 (Simple): "Summarize this article"
→ Result: Inconsistent length, misses key points

Version 2 (Add constraints): "Summarize in 3 bullet points"
→ Result: Better structure, but still misses nuance

Version 3 (Add reasoning): "Identify the 3 main findings, then summarize each"
→ Result: Consistent, accurate, captures key information
```

### 4. Template Systems

Build reusable prompt structures with variables, conditional sections, and modular components. Use for multi-turn conversations, role-based interactions, or when the same pattern applies to different inputs. Reduces duplication and ensures consistency across similar tasks.

**Example:**

```python
# Reusable code review template
template = """
Review this {language} code for {focus_area}.

Code:
{code_block}

Provide feedback on:
{checklist}
"""

# Usage
prompt = template.format(
    language="Python",
    focus_area="security vulnerabilities",
    code_block=user_code,
    checklist="1. SQL injection\n2. XSS risks\n3. Authentication"
)
```

### 5. System Prompt Design

Set global behavior and constraints that persist across the conversation. Define the model's role, expertise level, output format, and safety guidelines. Use system prompts for stable instructions that shouldn't change turn-to-turn, freeing up user message tokens for variable content.

**Example:**

```markdown
System: You are a senior backend engineer specializing in API design.

Rules:

- Always consider scalability and performance
- Suggest RESTful patterns by default
- Flag security concerns immediately
- Provide code examples in Python
- Use early return pattern

Format responses as:

1. Analysis
2. Recommendation
3. Code example
4. Trade-offs
```

## Key Patterns

### Progressive Disclosure

Start with simple prompts, add complexity only when needed:

1. **Level 1**: Direct instruction

   - "Summarize this article"

2. **Level 2**: Add constraints

   - "Summarize this article in 3 bullet points, focusing on key findings"

3. **Level 3**: Add reasoning

   - "Read this article, identify the main findings, then summarize in 3 bullet points"

4. **Level 4**: Add examples
   - Include 2-3 example summaries with input-output pairs

### Instruction Hierarchy

```
[System Context] → [Task Instruction] → [Examples] → [Input Data] → [Output Format]
```

### Error Recovery

Build prompts that gracefully handle failures:

- Include fallback instructions
- Request confidence scores
- Ask for alternative interpretations when uncertain
- Specify how to indicate missing information

## Best Practices

1. **Be Specific**: Vague prompts produce inconsistent results
2. **Show, Don't Tell**: Examples are more effective than descriptions
3. **Test Extensively**: Evaluate on diverse, representative inputs
4. **Iterate Rapidly**: Small changes can have large impacts
5. **Monitor Performance**: Track metrics in production
6. **Version Control**: Treat prompts as code with proper versioning
7. **Document Intent**: Explain why prompts are structured as they are

## Common Pitfalls

- **Over-engineering**: Starting with complex prompts before trying simple ones
- **Example pollution**: Using examples that don't match the target task
- **Context overflow**: Exceeding token limits with excessive examples
- **Ambiguous instructions**: Leaving room for multiple interpretations
- **Ignoring edge cases**: Not testing on unusual or boundary inputs

## Image & Video Generation Prompt Engineering

Techniques for crafting prompts that produce high-quality AI-generated images and videos across all major platforms.

### 1. Universal Image Prompt Formula

Build prompts by combining these elements in order of importance:

```
[Subject] + [Action/Pose] + [Setting/Environment] + [Style/Medium] + [Lighting] + [Camera/Composition] + [Mood/Atmosphere] + [Quality Modifiers] + [Constraints]
```

Use this structured template for complex scenes:

```
SCENE: [Environment / setting / time of day]
SUBJECT: [Detailed description with physical specifics]
ACTION: [What they're doing and how]
LIGHTING: [Source, quality, direction, color temperature]
CAMERA: [Shot type, lens, angle, depth of field]
STYLE: [Medium, artistic reference, era]
COLOR: [Palette, mood, temperature]
CONSTRAINTS: [What to exclude; what must not change]
INTENDED USE: [Platform, use case]
```

Not every field is required — use only what matters for the image. 80% of quality comes from Subject + Lighting + Style.

### 2. Platform Prompt Style Matrix

Each model processes prompts differently. Match your prompt style to the platform:

| Platform | Style | Notes |
|----------|-------|-------|
| Gemini/Imagen | Natural language narrative | Rewards prose, not keywords |
| GPT-Image-1.5 | Labeled structure (SCENE/SUBJECT/STYLE) | Direct processing, best text rendering |
| Midjourney V7 | Natural language + parameters | --ar, --stylize, --sref, --oref |
| SDXL | Natural language preferred | Dual-encoder, handles sentences |
| SD 1.5 | Keyword/tag style | Comma-separated Booru-style tags |
| Flux 1.x | Dual input (T5=narrative, CLIP=keywords) | Different prompt per encoder |
| Flux 2.x | Natural language | Single Mistral encoder |

**Rule of thumb**: Newer models prefer natural language. Older diffusion models prefer keyword lists.

### 3. Gemini MCP Image Generation

When using the `mcp__gemini-image__generate_image` tool:

- Write narrative, descriptive paragraphs — not keyword lists
- Front-load the subject, then lighting, then style
- Specify camera lens for realism: "85mm portrait lens, f/2.8, shallow depth of field"
- Use photography vocabulary: golden hour, Rembrandt lighting, chiaroscuro, rim light
- For text in images: keep under 25 characters, put text in quotes
- For consistency: describe the character the same way every time (50-word character anchor)
- Negative concepts: describe what you DO want, not what you don't. "pristine wilderness" not "no buildings"

**Example (Gemini narrative style):**

```
A weathered fisherman mending nets on a wooden dock at golden hour.
Warm Rembrandt lighting catches the texture of his calloused hands.
Shot with an 85mm portrait lens at f/2.0, shallow depth of field
blurs the harbor behind him into soft bokeh. Muted earth tones with
pops of turquoise from the water. Documentary photography style
reminiscent of Steve McCurry.
```

### 4. Common Mistakes in Image Prompting

1. **Keyword stuffing** — redundant quality words don't stack. "Ultra HD, 8K, hyperrealistic, best quality, masterpiece" wastes tokens. Pick one or two quality descriptors.
2. **Negative instructions that backfire** — "no cars" makes the model think about cars. Describe what you DO want instead.
3. **Over-prompting** — 80% of quality comes from subject + lighting + style. Adding 50 adjectives rarely improves the result.
4. **Starting over instead of iterating** — refine in the same session. Change one element at a time to understand what each word does.
5. **Ignoring reference images when available** — one reference image is worth 1000 words of description. Use image-to-image or style references when the platform supports them.
6. **Inconsistent style across a series** — copy the style specification block verbatim across every prompt in a series. Don't rephrase it.

### 5. Photography & Cinematography Vocabulary

Use precise technical language to control the output. Vague words like "beautiful" or "nice" give the model nothing to work with.

**Shot types:** extreme close-up, close-up, medium close-up, medium shot, medium full shot, full body, wide shot, extreme wide shot, flat lay, birds-eye view

**Angles:** eye level, low angle (hero shot), high angle (vulnerability), Dutch angle (tension), three-quarter view, over-the-shoulder, POV

**Lenses:**
- Ultra wide (14-24mm) — architecture, landscapes, dramatic distortion
- Wide (24-35mm) — environmental portraits, street photography
- Standard (50mm) — natural perspective, closest to human eye
- Portrait (85mm) — flattering compression, shallow DOF, classic portraits
- Telephoto (100-200mm) — compressed backgrounds, sports, wildlife
- Macro — extreme close-up detail
- Tilt-shift — miniature effect, selective focus planes

**Lighting:**
- Golden hour — warm, soft, low angle (first/last hour of sunlight)
- Blue hour — cool, moody, twilight tones
- Rembrandt — triangle of light on shadowed cheek, dramatic portraits
- Butterfly/Paramount — overhead, glamorous, symmetrical shadow under nose
- Split — half face lit, half in shadow, high drama
- Rim/backlight — subject outlined with light, separates from background
- Chiaroscuro — extreme contrast, deep shadows, Caravaggio-style
- Volumetric — visible light rays through atmosphere (fog, dust, windows)

**Film stocks (for analog look):**
- Kodak Portra 400 — warm skin tones, soft, wedding/portrait standard
- Fuji Velvia — vivid saturated colors, landscapes
- Ilford HP5 — classic black and white, rich midtones
- Kodak Tri-X — gritty high-contrast black and white, photojournalism

### 6. Video Generation Prompting

Video generation requires a fundamentally different approach than images. Lead with motion, not appearance.

**Structure:**
```
[Camera movement] + [Subject] + [Action/Motion] + [Environment] + [Lighting] + [Temporal cues]
```

**Rules:**
- Lead with motion, not appearance — the model needs to know what moves and how
- One primary action per generation — complex choreography fails
- Use active verbs with direction: "sprints left to right", "glides forward", "drifts upward"
- Specify what stays still: "background remains static", "camera is locked off"
- Think in shots, not scenes — one camera angle, one action, 3-5 seconds
- Describe temporal progression: "starts with..., then transitions to..., ending on..."

**Camera movements:**
- Dolly — camera moves toward or away from subject (in/out)
- Pan — camera rotates horizontally (left/right) from fixed position
- Tilt — camera rotates vertically (up/down) from fixed position
- Tracking/truck — camera moves alongside subject laterally
- Crane/jib — camera moves vertically through space
- Zoom — focal length change (different from dolly — flattens/stretches space)
- Steadicam — smooth handheld following movement
- Dolly zoom (Vertigo effect) — dolly in while zooming out (or reverse), creates disorienting scale shift

**Example (video prompt):**

```
Slow dolly forward through a misty forest at dawn. Camera glides
at waist height between towering redwood trunks. Volumetric light
rays pierce the canopy from upper left. A deer lifts its head in
the middle distance, ears alert. Background fog drifts slowly right
to left. Cinematic, 24fps, anamorphic widescreen.
```

### 7. The 6-Prompt Strategy (Claude as Creative Director)

When asked to generate image prompts, produce 6 variations at different detail levels. This lets the user choose the right density for their platform and gives them options to iterate from.

| Level | Words | Contains |
|-------|-------|----------|
| Minimal | 10-15 | Core subject + mood |
| Concise | 20-30 | + environment + lighting |
| Standard | 40-60 | + artistic references + composition |
| Detailed | 80-120 | + foreground/midground/background layers |
| Technical | 100-150 | + camera specs, film stock, post-processing |
| Maximal | 150+ | Complete art direction document |

**When to use each level:**
- Minimal/Concise — quick exploration, Midjourney, brainstorming phase
- Standard — most platforms, most use cases, best starting point
- Detailed — when you know what you want and need precision
- Technical — product photography, architectural visualization, client work
- Maximal — hero images, brand assets, when pixel-level control matters

### 8. Consistency Across Generations

Maintaining visual consistency across multiple generations (character series, product shots, brand assets) is the hardest problem in AI image generation.

**50-word character anchor:** Write a fixed physical description and paste it verbatim into every prompt. Never rephrase it — rephrasing introduces drift.

```
CHARACTER ANCHOR: A tall woman in her mid-30s with deep brown skin,
close-cropped natural hair, high cheekbones, and warm amber eyes.
She has a small scar above her left eyebrow. Athletic build,
broad shoulders, confident posture. Wearing a navy linen blazer
over a white crew-neck t-shirt.
```

**Style specification block:** Define the visual treatment once and copy it exactly.

```
STYLE SPEC: Soft editorial photography. Warm color palette dominated
by terracotta, cream, and sage green. Slightly desaturated. Shot on
Kodak Portra 400. Natural window light, soft shadows. 85mm lens,
f/2.0, shallow depth of field. Grain visible at 100% crop.
```

**KEEP/CHANGE format:** When iterating on a previous generation, explicitly state what stays and what changes.

```
KEEP: Same character, same outfit, same lighting style, same color palette
CHANGE: Setting moves from indoor cafe to outdoor garden terrace.
Character is now standing, leaning against a stone railing, looking
off-camera to the right.
```

**Reference images:** When the platform supports them, one reference image provides more consistency than any amount of text description. Use style references (--sref in Midjourney), image-to-image, or ControlNet for diffusion models.

**Same session:** Stay in the same conversation when generating a series. Models with visual context (Gemini, GPT) retain implicit style memory within a session.
