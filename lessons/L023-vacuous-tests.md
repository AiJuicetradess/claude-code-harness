---
id: L023
title: "Vacuous tests — passing tests that don't exercise the fix"
category: workflow
severity: critical
status: active
created: 2026-05-01
last_triggered: 2026-04-20
times_violated: 2
times_checked: 0
tags: [testing, verification, falsification, premature-victory]
related_skills: [verification-before-completion]
---

**Rule:** Before declaring "tests pass, fix verified," manually verify every assertion actually exercises the code path under test. Apply the falsification check: *"if I revert the fix, does this test now fail?"* If the answer is no, the test is vacuous and the fix is unverified — regardless of how green the suite looks.

**Why:** A test that passes is not the same as a test that *would have failed before the fix*. Common vacuous shapes:

- Asserting on hand-set inputs (`assert 13:00 > 13:00` as raw Python math) instead of values computed by the symbol under test
- Constructing the object via `__new__()` to skip `__init__`, then claiming the boot/seed path is tested
- Manually setting internal state (`obj._5m_prev_latest_low = 0.0`) so the assertion holds regardless of the fix
- An assertion gated by a branch (`if is_contained:`) that — after the fix — is always False, so the assertion never runs

In session b83b5a28 (line 766) the assistant declared *"20/20 passed. All fixes verified"* covering 8 critical bugs. User pushed back at line 771: *"All eight bugs passed with no failures? thats suspicious."* On audit at line 782 the assistant admitted: *"4 of the 8 tests are vacuous — they pass regardless of whether the fix exists."* Even after rewrite, one of the supposed bugs turned out to be unreachable in normal operation. The pattern carried into 4333a814, where the word "vacuous" appears 75 times across the session as the audit unwound the inflated pass count.

This is structurally distinct from L009 (which is about end-to-end data flow). The pipeline ran, the test runner exited 0, every test reported "passed" — but the tests asserted on the wrong layer.

**Prevention:**

1. After "X/X tests pass," for each test verify (a) it imports/calls the exact symbol being fixed, (b) the assertion is on a value computed by that symbol, not on hand-set inputs, (c) the assertion is reachable on both branches of any `if` it sits inside.
2. Run the falsification step explicitly: `git stash` the fix, re-run the test — it MUST fail. If it still passes, the test is vacuous and must be rewritten.
3. Never use `__new__()` or directly set internal state to set up a test for an `__init__` / boot / seed path. Drive through the public entry point so the path under test is actually exercised.
4. For boundary-condition fixes (`>` vs `>=`, off-by-one, equality at the seam): the test must construct the boundary input exactly. If the test uses random or nominal data, it does not test the boundary.
5. When reporting test counts, separate "tests written" from "tests that exercise the change." If only 4 of 8 are real, report `4/8 verified, 4 vacuous` — never `8/8 passed`.
6. Treat user pushback like *"thats suspicious"* / *"all of them?"* / *"no failures at all?"* as a stop-and-falsify event. The user often catches over-confident verification claims before the assistant does.
