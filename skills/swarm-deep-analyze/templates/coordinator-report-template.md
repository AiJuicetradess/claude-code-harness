# {{TARGET_NAME}} — Master Coordinator Report

**Source:** {{TARGET_PATH}}
**Swarm run:** Orch-1 + {{N}} builders, {{DATE}}
**Output set:** `{{OUTPUT_DIR}}/01-{{N}}-*.md` (per-section deep dives), this file (master synthesis)

---

## 0. Bottom line

{{2–4 sentence summary}}

{{Table of headline verdicts:}}
| Axis | Verdict |
|---|---|
| Overall evidence (Adversarial-Critic) | |
| Reproducibility (Adversarial-Critic) | |
| External claims verified (Claim-Verifier) | |
| Implementation feasibility on our stack (Infra-Mapper) | |
| MVP effort | |
| Full-parity effort | |
| Main "alpha" worth extracting | |
| Main thing to ignore in marketing | |

---

## 1. Anatomy — what it is in one screenful

{{2–4 paragraphs. Reader should understand the substance without opening any builder file.}}

→ Full chunked summaries in `{{OUTPUT_DIR}}/01-...md` ... `{{OUTPUT_DIR}}/0N-...md`.

---

## 2. The "alpha" — what's actually worth taking

Ranked by transferability:

1. **{{ALPHA-1}}** — {{evidence + caveat + transferability}}
2. **{{ALPHA-2}}** — ...
3. **{{ALPHA-3}}** — ...
4. ...

The thing NOT worth taking: {{what to ignore in the marketing}}.

---

## 3. Claim validation — what's verified vs what isn't

Claim-Verifier (`{{OUTPUT_DIR}}/07-claim-verification.md`) spot-checked **N headline claims**:

| Claim (paraphrased) | Verdict | Evidence |
|---|---|---|

**Notes flagged:**
- {{any unverifiable first-party numbers}}
- {{any missing contemporaneous citations}}
- {{any tool-result anomalies}}

→ Detailed verification table at `{{OUTPUT_DIR}}/07-claim-verification.md`.

---

## 4. Adversarial critique — where it cracks

Adversarial-Critic's full peer review at `{{OUTPUT_DIR}}/06-critique-methodology.md`. Summary:

| Thesis | Evidence | Notes |
|---|---|---|

**Top methodology gaps:**
- ...

**Top 5 demands for a revision:**
1. ...

**Reproducibility:** {{summary}}

---

## 5. Implementation on our stack

Infra-Mapper's full design at `{{OUTPUT_DIR}}/08-implementation-{{stack}}.md`. Headline mapping:

| Target layer | Our primitive | Feasibility |
|---|---|---|

**Missing-but-needed capabilities:**
1. ...

**Effort table:**
| Phase | Effort | Prereqs |
|---|---|---|
| MVP | | |
| Parity | | |

---

## 6. Recommendation for {{user's project}} specifically

{{Decision-relevant guidance. What to do first. What to skip. What's a real opportunity vs a research bet.}}

Ladder if pursuing:
1. ...
2. ...
3. **Decision gate** — {{when to commit further}}

---

## 7. File index

| File | Author | Range | Content |
|---|---|---|---|
| `01-...md` | Builder-1 | | |
| `02-...md` | Builder-2 | | |
| `06-critique-methodology.md` | Adversarial-Critic | full | |
| `07-claim-verification.md` | Claim-Verifier | external | |
| `08-implementation-{{stack}}.md` | Infra-Mapper | full | |

---

## 8. Caveats worth remembering

- {{extraction quirks}}
- {{reproducibility ceiling}}
- {{any single number to never quote without context}}
- {{first-party data we haven't independently re-run}}
- {{tool/harness oddities}}

---

**End of master report.**
