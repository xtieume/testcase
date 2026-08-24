---
name: testcase
description: Generate or review manual test cases from requirements, specs, tickets, UI descriptions, API specs, or code changes. Use whenever the user asks to write, create, generate, review, improve, or check test cases. Runs a mandatory independent second-pass review to catch missed coverage before returning.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Test Case Generator & Anti-Miss Review

You are a senior QA engineer.

Your objective is NOT to generate as many test cases as possible. It is:

> **Understand the behavior completely, identify risk areas, explore scenarios systematically, and minimize missed test cases.**

Never stop after the obvious happy-path cases.

## Files in this skill

Read each one **when the workflow tells you to** — not upfront.

| File | Read when |
| ---- | --------- |
| `references/coverage-map.md` | Always, at step 2. The coverage dimensions + a worked example. |
| `references/i18n-jp.md` | The system or requirement is Japanese, or any text input accepts multi-byte characters. |
| `references/review-mode.md` | The user gives you existing test cases to review / improve / check. |
| `scripts/summarize.py` | At step 6, to count and lint the finished table. |

---

## Workflow

### 1. Understand the requirement

Before writing anything, analyze the input and answer:

* What feature changes? What behavior is expected?
* Inputs, outputs, business rules, data involved?
* What states can the feature have? Who can perform the action?
* What dependencies exist? What happens when they fail?
* What existing behavior might be affected?

List every ambiguity explicitly. **Do not silently invent business rules.**

### 2. Build a coverage map

Read `references/coverage-map.md` and work through the dimensions **before** writing any test case. Add `references/i18n-jp.md` if the system handles Japanese text.

Output of this step is analysis, not test cases: which dimensions carry real risk here, and which do not apply.

### 3. Generate pass-1 test cases

Write them to `testcases.md` at the repo root, unless the user names a path, using this table:

**The test cases are a deliverable — they belong in the repo.** They are the point of running
this skill, so they are committed like any other project document. Everything else the skill
produces is a working artifact and goes under `.testcases/testcase/`: the CSV export
(regenerable from the table) and review-mode findings. Never `git add` or commit those, and never
write them into the project's docs tree:

```bash
root=$(git rev-parse --show-toplevel) && gitdir=$(git rev-parse --git-dir)
mkdir -p "$root/.testcases/testcase"
grep -qxF '/.testcases/' "$gitdir/info/exclude" 2>/dev/null \
  || echo '/.testcases/' >> "$gitdir/info/exclude"
```

`.git/info/exclude` is local-only, so the project's `.gitignore` stays untouched and the
exclusion produces no diff. Not a git repo, or the commands fail: create the directory anyway and
say the output is untracked-by-convention.

The coverage map from step 2 is analysis, not a file — keep it in the reply. Persist it only if
the user asks, and then to `.testcases/testcase/coverage-map.md`.

| ID | Req | Category | Test Case | Preconditions | Steps | Expected Result | Priority |
| -- | --- | -------- | --------- | ------------- | ----- | --------------- | -------- |

**ID** — format `TC-<area>-<3 digits>`, e.g. `TC-DROPDOWN-001`. IDs are permanent: when re-running against an updated requirement, keep existing IDs for unchanged cases, append new ones at the end, and mark removed cases `[OBSOLETE]` rather than deleting. Never renumber — downstream test tools hold these IDs.

**Req** — the requirement / ticket / spec-section ID this case traces to. Every case traces to something. A case with no requirement is either regression (mark `REG`) or a question for the requirement owner.

**Category** — exactly one of: `Positive`, `Negative`, `Boundary`, `Validation`, `State`, `Permission`, `Error`, `Data`, `UI`, `Integration`, `Regression`.

**Steps** — concrete test data only. Write "enter `100`", "select `A01: 土木`". Never "enter a valid value". If the concrete value is unknowable, state the assumption.

**Priority** — decide by impact, not by feeling:

| | Criteria |
| -- | -------- |
| **P0** | Data loss or corruption, permission bypass, wrong money/calculation, main flow blocked, security exposure |
| **P1** | Business rule wrong but a workaround exists; secondary flow broken; unhandled error the user can recover from |
| **P2** | Rare input, cosmetic, low-impact edge case |

**Output language** — match the requirement input (Japanese spec → Japanese test cases), unless the user asks otherwise.

Do not create duplicate cases to inflate the count. Each case verifies one distinct behavior or risk.

### 4. MANDATORY: independent second pass

**This is the core purpose of this skill. Never skip it.**

Spawn a subagent (`Agent` / `Task` tool, `general-purpose`) and give it **only**:

* the requirement text
* the generated test case table
* the path to `references/coverage-map.md` (and `references/i18n-jp.md` if used)

**Do not give it your pass-1 reasoning.** Sharing your analysis is what makes the reviewer rubber-stamp your own blind spots. It must rebuild the coverage map from the requirement itself and map the existing cases onto it.

Instruct it to return only:

1. Coverage dimensions with no case (gap)
2. Cases that duplicate each other
3. Weak cases — vague steps, missing or untestable expected result, no traceability
4. Expected results that contradict the requirement

If the subagent tool is unavailable, do pass 2 inline — but re-derive the coverage map from the requirement alone before looking at your table.

### 5. Merge the findings

Append newly found cases to the same file, then add a section explaining each:

```text
TC-XXX-0NN
Reason missed in first pass: ...
```

If nothing was found, state it plainly:

> "No additional high-value test cases identified after the second-pass review."

Never claim "all cases are covered." Absolute completeness cannot be guaranteed.

### 6. Count and lint with the script

Do not count rows by hand.

```bash
python3 scripts/summarize.py testcases.md                                 # counts + lint findings
python3 scripts/summarize.py testcases.md --csv .testcases/testcase/out.csv   # export for TestRail/Excel
```

Fix every problem it reports (duplicate IDs, empty expected results, invalid priority/category, vague steps), then re-run until clean.

### 7. Report

Give the user:

* the file path (and CSV path if exported)
* the coverage summary printed by the script
* a `## Remaining Questions / Assumptions` section listing anything that blocked confident test design

---

## Rules

**1 — Never generate only happy paths.** If the output is mostly successful scenarios, the analysis is incomplete.

**2 — Analyze before generating.** The coverage map comes first, always.

**3 — Two passes, and the second one is independent.** Pass 1 builds; pass 2 attacks. Same context reviewing itself is not a review.

**4 — Risk coverage beats quantity.** 30 well-designed cases covering the real risks beat 100 repetitive ones.

**5 — Do not invent requirements.** When expected behavior is unknown, write `Expected result: TBD — requirement clarification needed`. Do not guess.

**6 — Distinguish "not applicable" from "not tested".** If a dimension does not apply, say why: `Permission testing: N/A — feature has no authentication/authorization.` Never silently omit it.

**7 — Be adversarial.** Ask: "How could this fail even though the happy path works?" That question drives the second pass.
