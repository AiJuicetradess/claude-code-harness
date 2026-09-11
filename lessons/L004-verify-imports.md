---
id: L004
title: "Never assume an import path exists"
category: coding
severity: critical
status: active
created: 2026-03-13
last_triggered: 2026-04-10
times_violated: 13
times_checked: 0
tags: [imports, verification, cove]
related_skills: [cove-verification]
---

**Rule:** Before writing code that imports a module or calls a function, grep for its actual definition to confirm it exists with the expected signature.

**Why:** Hallucinated imports are the #1 error class. Confidently importing a function that doesn't exist wastes an edit + a test/run cycle to discover the error.

**Prevention:**
1. Before `from module import func`: run `grep -r "def func"` or `grep -r "class Func"`
2. Before `import module.submodule`: verify the file exists with Glob
3. Check the actual function signature — don't assume parameter names or return types
4. For database queries: verify table/column names exist before writing SQL
