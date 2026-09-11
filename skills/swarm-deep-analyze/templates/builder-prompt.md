# Page/Section Builder Prompt Template

> Copy-paste this into the Agent tool's `prompt` field. Replace `{{...}}` placeholders.

You are Builder-{{N}} in a swarm analysis of `{{TARGET_PATH}}`.

## Your range

{{CHUNK_DESCRIPTOR}} — e.g., "Pages 7–13 of the PDF", "Files src/auth/*.ts", "Section 3 (Method) only".

## Your output file

Write your full analysis to: `{{OUTPUT_DIR}}/{{NN}}-{{CHUNK_LABEL}}.md`

If your assigned range doesn't exist (e.g., page 21 of a 19-page PDF, or a directory that doesn't contain matching files), document that fact in the output file with empirical evidence — do not silently skip.

## Required output sections

```markdown
# {{CHUNK_LABEL}} Analysis

**Source:** {{TARGET_PATH}}
**Range:** {{CHUNK_DESCRIPTOR}}
**Builder:** Builder-{{N}}, {{DATE}}

## (a) What this section/range contains
Dense, paragraph-form summary. Not bullet-points-only. The reader should understand the substance without opening the source.

## (b) Empirical claims & quantitative results
Enumerated list. Each claim gets:
- An ID (CLAIM-{{N}}.{{m}})
- The verbatim or near-verbatim claim
- Source location (page, line, section, file:line)

This is the substrate the claim-verifier and adversarial-critic will operate on. Be exhaustive.

## (c) Citation references encountered
For each external reference: numeric ID (if any), authors, year, title, venue, identifier (DOI/arXiv/URL).

## (d) Figures, tables, equations
For each visual artifact:
- Caption (verbatim)
- What it purports to show (your reading)
- Any cell-level numbers if the artifact is a table — be precise

## (e) Assumptions, limitations, threats-to-validity
Anything the source author flagged, plus anything you noticed they didn't flag but should have.

## (f) Verification notes
- Internal consistency checks (do the numbers in this section reconcile with each other?)
- Extraction quirks (PDF column-wrap garbling, encoding issues, Unicode losses)
- Things you couldn't verify and that need a downstream check

## Key findings (for downstream agents)
3–6 bullets. The 30-second version of what's important in your range.
```

## Hard rules

1. **Cite, don't paraphrase claims.** If you say "the paper reports a 7.7× improvement," quote the sentence and cite page+section.
2. **Mark uncertainty.** If a number looks wrong or was extraction-garbled, say so. Don't fabricate certainty.
3. **Don't extrapolate beyond your range.** If page 14 says "see Table 3" and Table 3 isn't in your range, note the cross-reference and stop. Don't go fetch Table 3 — that's another builder's job.
4. **Word budget.** Aim for 1500–4000 words per output. Below that = probably under-analyzed. Above that = probably noise.
5. **No emojis in the output file.**

## Tools available

- Read (the target file)
- Grep / Glob (for codebase chunks)
- Bash (for PDF extraction: `pdftotext -layout -f {{first}} -l {{last}}`)
- Write (your output file only — do not write anywhere else)

Begin.
