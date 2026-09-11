---
name: swarm-deep-analyze
description: Use when the user wants a multi-builder swarm analysis of a large document, PDF, paper, codebase, or research target — produces structured per-section deep-dives plus an adversarial critique, external claim verification, infrastructure-mapping, and a master coordinator synthesis. Triggers on "deep analyze this paper", "swarm review this PDF", "audit this codebase end-to-end", "give me a builder swarm on X", "do what we did with the FORGE paper for this", "decompose this and assign builders", "I need a 360 on this document".
---

# Swarm Deep Analyze

A reusable orchestration pattern for "thoroughly understand X, then give me a synthesis I can act on."

## When to fire

- User drops a large PDF or document with "analyze this"
- User asks "what should we do with this paper / research / report"
- User wants an audit of a large codebase area (>20 files or >5000 LOC)
- User wants competitive intelligence on a product/market with multiple sources
- User wants legal or contract review across many pages
- User says "do what we did with FORGE", "spin up the swarm on X", or "give me a coordinator report"

Do NOT fire for: single-file edits, simple questions, anything that fits in one read.

## The pattern (8 builders + 1 coordinator)

```
                    USER PROMPT + TARGET
                            │
                            ▼
                   ┌──────────────────┐
                   │  ORCHESTRATOR    │ ← chunks target, dispatches builders
                   └──────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
  ┌──────────┐        ┌──────────┐        ┌──────────┐
  │ Builder  │        │ Builder  │  ...   │ Builder  │
  │ 1: §1-N  │        │ 2: §N-M  │        │ K: end   │  ← page/section chunks
  └──────────┘        └──────────┘        └──────────┘
        │                   │                   │
        └─────────────┬─────┴───────────────────┘
                      ▼
        ┌──────────────────────────────────┐
        │  PARALLEL CROSS-CUTTING BUILDERS │
        ├──────────────────────────────────┤
        │  • adversarial-critic            │  ← thesis taxonomy, evidence grades
        │  • claim-verifier                │  ← external citations cross-check
        │  • infra-mapper (optional)       │  ← maps target onto our stack
        └──────────────────────────────────┘
                      │
                      ▼
              ┌──────────────────┐
              │  COORDINATOR     │  ← single-page master synthesis
              └──────────────────┘
                      │
                      ▼
              USER REVIEW SURFACE
```

All builders run in parallel within a single Agent batch (one message, multiple Agent calls).

## Step-by-step

### Phase 0 — Triage (you, 30 seconds)

1. **Identify target.** PDF? Folder? URL? Multiple files? Decide chunking unit (pages, sections, modules, files).
2. **Identify question.** "What does this say?" or "Should we adopt this?" or "Is this safe?" or "How would this fit our stack?" — the question determines which cross-cutting builders to spawn.
3. **Choose output directory.** Default: `docs/<topic>-analysis/` relative to cwd. Adjust if cwd isn't a project.
4. **Estimate size.** If target > 30 chunks (e.g., a 60-page PDF at 2 pages/builder), warn the user about token cost before spawning.

### Phase 1 — Chunking decision

| Target type | Default chunk size | Builders to spawn |
|---|---|---|
| Academic paper (<25 pages) | 5–7 pages per builder | 4–5 page builders |
| Long report (25–60 pages) | 7 pages per builder | 6–8 page builders |
| Codebase audit | 5–8 files per builder OR 1 subsystem per builder | 4–8 builders |
| Multi-source market research | 1 source per builder | 3–6 builders |
| Legal contract | 1 logical section per builder | 4–6 builders |

For PDFs: probe page count first via `pdftotext` byte-count per page (see `templates/probe-pdf-pages.sh`). The FORGE swarm hit the "page 21–27 doesn't exist" edge case — Builder-4 documented an empty range, which was the right behavior.

### Phase 2 — Spawn page/section builders in parallel

Each builder gets:
- The full path to the target
- A specific page/section range
- A standardized output schema (see `templates/builder-prompt.md`)
- Output file path: `<output-dir>/<NN>-<chunk-label>.md`

**Use the Agent tool with `subagent_type: researcher`** for analytical chunks. **Use `subagent_type: developer`** for code chunks.

All builders run in a single Agent batch — one message with K parallel Agent calls.

### Phase 3 — Spawn cross-cutting builders

Based on the user's question, fire the relevant cross-cutters in the same batch (or a second batch if the page builders need to finish first to provide claim text):

| Cross-cutter | When to spawn | Subagent type |
|---|---|---|
| `adversarial-critic` | Always for papers/reports; optional for code | `adversarial-critic` (build first via task #2) |
| `claim-verifier` | When external claims/numbers/benchmarks appear | `claim-verifier` (build first via task #3) |
| `infra-mapper` | When user is considering adoption ("would this work for us?") | `architect` |
| `security-reviewer` | When target is code or has security implications | `security-reviewer` |
| `trading-researcher` | When target is trading/finance research | `trading-researcher` |

### Phase 4 — Coordinator synthesis (you, in-thread)

Do NOT spawn a coordinator subagent — do this synthesis yourself in the main thread so the user gets one consolidated voice.

Read all builder outputs. Produce `<output-dir>/coordinator-report.md` with these sections:

```
0. Bottom line — a single screenful: verdict, grades, top alpha, what to ignore
1. Anatomy — what the target is, in 1 screen
2. The "alpha" — what's actually worth taking, ranked by transferability
3. Claim validation — verified vs unverified vs disputed
4. Adversarial critique — where it cracks (top 5 weaknesses)
5. Implementation mapping (if applicable) — concrete next steps
6. Recommendation for <user's project> specifically
7. File index — links to every builder output
8. Caveats worth remembering — extraction quirks, reproducibility ceiling, etc.
```

The coordinator report is the canonical deliverable; copy the structure below.

### Phase 5 — Return to user

One message:
- One-paragraph TL;DR (max 4 sentences)
- Link to `coordinator-report.md`
- "Top 3 things to act on" — most decision-relevant findings

Do not dump the full coordinator report into chat. The user reads it from disk.

## Quality bars (non-negotiable)

1. **Every claim has provenance.** Builders cite page/section/file:line. No floating assertions.
2. **The adversarial-critic operates with fresh context.** It must not see the orchestrator's reasoning before producing its grades. Spawn it in a separate Agent call from the page builders if context bleed is a risk.
3. **The claim-verifier hits real external sources.** WebFetch / repo URLs / actual file reads — not paraphrase.
4. **Edge cases are documented, not silently swallowed.** If a chunk is empty, missing, or unparseable, the builder writes that fact (see Builder-4's "pages 21–27 don't exist" output).
5. **Coordinator separates "what holds up" from "what the marketing claims."** The FORGE coordinator's headline — "the science is real, the marketing is 10–20% hotter than the science" — is the right shape.

## Anti-patterns (caught from FORGE swarm)

- **Don't let a builder skip its range silently.** Builder-4 properly documented the empty range. A silent skip would have looked like coverage.
- **Don't trust a single number.** Builder-7 cross-checked the cited DRL top score (-3.47) against the actual leaderboard and found the Cardiff team's own re-runs now give -3.4108 — within variance but worth noting.
- **Don't mix builder and orchestrator concerns.** Synthesis happens in-thread, not in a 9th agent. One voice to the user.
- **Don't trust extraction without sanity-checking.** Both FORGE builders 4 and 5 caught the `pdftoppm` failure under Miniconda and fell back to `pdftotext`. Always probe before mass-extracting.

## Templates

See `templates/` directory:
- `builder-prompt.md` — drop-in prompt template for page/section builders
- `adversarial-critic-prompt.md` — drop-in prompt for the critic
- `claim-verifier-prompt.md` — drop-in prompt for the verifier
- `infra-mapper-prompt.md` — drop-in prompt for the infra mapper
- `coordinator-report-template.md` — skeleton for the master synthesis
- `probe-pdf-pages.sh` — bash one-liner to byte-count pages and detect empty ranges

## Compute cost notes

A FORGE-sized swarm (8 builders + 2 cross-cutters + coordinator synthesis) on a 19-page PDF cost ~120k–200k tokens total on Sonnet 4.6. For larger targets, scale linearly. Warn the user before spawning if the target is >50 pages or >50 code files.

## Related skills

- `memory-synthesizer` — same parallel pattern but applied to YOUR session transcripts, not external documents
- `self-reflection` — single-agent transcript review
- `cove-verification` — single-claim verification before implementation
