---
name: cove-verification
description: Use BEFORE writing any code or modifying any file - requires verifying assumptions against the actual codebase before implementation. Pairs with verification-before-completion which verifies AFTER. This skill prevents hallucinated APIs, wrong function signatures, missing imports, and incorrect assumptions. Evidence before implementation always.
---

# COVE: Chain of Verification (Pre-Implementation)

## Overview

Writing code based on assumptions is how hallucinated APIs, wrong signatures, and phantom imports ship. Verify against the actual codebase before writing a single line.

**Core principle:** Every assumption about the codebase must be verified with evidence before acting on it.

**Relationship to verification-before-completion:** That skill gates AFTER implementation (did the tests pass? did the build succeed?). This skill gates BEFORE implementation (does this API exist? is this the right function signature? is this import available?). Together they form a verification sandwich — nothing ships unverified on either end.

## The COVE Loop

```
BEFORE writing or modifying any code:

1. DRAFT: Formulate what you intend to do
   - "I'll call utils.parseConfig() to load the settings"

2. IDENTIFY ASSUMPTIONS: List what you're assuming
   - Does utils.parseConfig() exist?
   - What arguments does it take?
   - What does it return?
   - Where is it imported from?

3. VERIFY EACH ASSUMPTION: Search the codebase
   - grep/ripgrep for the function definition
   - Read the actual file, check the actual signature
   - Confirm the return type from source, not memory

4. REFINE OR DISCARD:
   - If verified: Proceed with confidence
   - If contradicted: Discard the draft, form a new one
   - If inconclusive: State clearly what you cannot verify

Skip any step = guessing, not engineering
```

## The COVE Logic Check Block

Before ANY file modification, produce this block (internally or explicitly):

```
COVE Logic Check:
- Draft: [One sentence — what I intend to do]
- Verified: [2-3 bullets proving I checked the codebase]
  • Confirmed X exists via grep at file:line
  • Confirmed Y accepts string arg via definition at file:line
  • Confirmed Z is exported from module via file:line
- Decision: [Why this change is safe based on verification]
```

## What Must Be Verified

| Assumption Type | How to Verify | Not Sufficient |
|----------------|---------------|----------------|
| Function exists | grep for definition, find file:line | "I think it exists" |
| Function signature | Read the actual definition | Remembering from earlier |
| Import path | grep for export, check package.json | Guessing the path |
| Variable in scope | Read the enclosing function/module | "It should be available" |
| Return type | Read the function body or type annotation | Inferring from name |
| Config key exists | grep config files, check schema | "Projects usually have this" |
| Dependency installed | Check package.json / requirements.txt | "It's a common library" |
| API endpoint exists | grep route definitions | Assuming RESTful convention |
| Database column exists | Check migrations or schema file | "The table probably has it" |
| Environment variable | Check .env.example or config loader | "Standard practice" |

## Verification Tools

Use these in order of specificity:

**1. Targeted grep** (best for "does X exist?")
```bash
grep -rn "function parseConfig\|parseConfig =" src/
grep -rn "export.*parseConfig" lib/
```

**2. File read** (best for "what does X look like?")
```bash
# Read the actual definition, not a summary
cat src/utils/config.ts | head -50
```

**3. AST-level search** (best for complex patterns)
```bash
# Find all callers of a function
grep -rn "parseConfig(" src/ --include="*.ts"
```

**4. Dependency check** (best for "is X available?")
```bash
cat package.json | grep "lodash"
pip list | grep requests
```

## Red Flags — STOP

These thoughts mean you're about to write unverified code:

| Thought | Reality |
|---------|---------|
| "This function probably takes a string" | Read the definition |
| "I've seen this pattern before" | This codebase may differ |
| "It's a standard library function" | Version may differ, check docs |
| "The import should be from here" | Grep for the actual export |
| "This config key is typical" | Check the actual config |
| "I'll just try it and see" | Verify first, save the round-trip |
| "The types will catch it" | Not all projects have strict types |
| "I remember from earlier in the conversation" | Context may be stale, re-verify |

## Common Failure Patterns

**Hallucinated API:**
```
❌ Draft: "Call response.getHeaders()"
   Reality: Method is response.headers (property, not method)
   Cause: Assumed API without checking
```

**Wrong Import Path:**
```
❌ Draft: "Import from '@/utils/helpers'"
   Reality: File is at '@/lib/helpers'
   Cause: Guessed directory structure
```

**Phantom Dependency:**
```
❌ Draft: "Use dayjs for date formatting"
   Reality: Project uses date-fns, dayjs not installed
   Cause: Assumed common library was available
```

**Stale Context:**
```
❌ Draft: "Modify the handleSubmit function in Form.tsx"
   Reality: Function was renamed to onFormSubmit in a recent refactor
   Cause: Relied on memory instead of re-reading the file
```

## Brownfield Codebase Rules

In existing codebases, these additional verification steps apply:

**Before modifying any file:**
- Read the current state of the file (not from memory)
- Check recent git log for that file (has it changed recently?)
- Identify who else touches this code (grep for imports/callers)

**Before adding imports:**
- Verify the module exports what you need
- Check that the dependency is in the project's package manager
- Confirm no circular dependency would be created

**Before changing function signatures:**
- Find ALL callers of the function
- Verify each caller can accommodate the change
- Check if the function is part of a public API or interface

**Before touching shared utilities:**
- Map the blast radius (who imports this?)
- Verify your change doesn't break other consumers
- Consider whether a new function is safer than modifying

## Integration with Other Skills

**Pairs with verification-before-completion:**
- COVE verifies BEFORE you write code
- verification-before-completion verifies AFTER you write code
- Together: nothing ships based on assumptions at either end

**Pairs with systematic-debugging:**
- When debugging, COVE prevents "fix based on guess" cycles
- Verify root cause hypothesis against actual code before applying fix

**Pairs with executing-plans:**
- Before executing each plan step, run COVE on the step's assumptions
- Don't execute plan steps that rely on unverified codebase state

**Pairs with brainstorming:**
- During design, COVE validates that proposed approaches are feasible
- "Can we use X?" → grep for X, verify it exists and works as expected

## When to Apply

**ALWAYS before:**
- Writing new code that references existing code
- Modifying existing functions or modules
- Adding imports or dependencies
- Changing configuration
- Refactoring or renaming
- Any change in a brownfield codebase

**Intensity scales with risk:**
- Touching shared utility used by 50 files → full COVE with blast radius analysis
- Adding a local variable → quick verify the type is correct
- Changing an API endpoint → full COVE with caller mapping

## The Bottom Line

**Every assumption is a potential bug.**

Grep the codebase. Read the definition. Check the signature. THEN write the code.

This is the front gate. verification-before-completion is the back gate. Nothing passes without evidence at both ends.
