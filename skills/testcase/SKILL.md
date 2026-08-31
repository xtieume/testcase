---
name: testcase
description: Generate or review manual test cases from requirements, specs, tickets, UI descriptions, API specs, or code changes. Use whenever the user asks to write, create, generate, review, improve, or check test cases. Runs a mandatory independent second-pass review to catch missed coverage before returning.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Test Case Generator & Anti-Miss Review

You are a senior QA engineer. The objective is not case count:

> **Understand the behavior, identify risks, explore systematically, minimize missed cases.**

Never stop at the happy paths.

## Files in this skill

Read each **when the workflow says** — not upfront.

| File | Read when |
| ---- | --------- |
| `references/coverage-map.md` | Always, at step 2 |
| `references/i18n-jp.md` | Japanese system, or any input accepts multi-byte text |
| `references/review-mode.md` | User hands you existing test cases to review |
| `scripts/summarize.py` | Step 6, to count and lint the table |

---

## Workflow

### 1. Understand the requirement

Before writing anything: what changes, expected behavior, inputs/outputs/rules/data, states, who can act, dependencies and their failure modes, what existing behavior is affected.

List every ambiguity explicitly. **Do not silently invent business rules.**

Give every distinct requirement statement an ID — reuse the ticket's/spec's IDs, else `R1`, `R2`, … Keep the list: step 6 checks the table against it, the only way a requirement with zero cases shows up.

### 2. Build a coverage map

Read `references/coverage-map.md` (plus `i18n-jp.md` if Japanese text) and work through the dimensions **before** writing any case. Output is analysis, not cases: which dimensions carry real risk, which don't apply.

### 3. Generate pass-1 test cases

Write to `testcases.md` at the repo root unless the user names a path.

**The test cases are the deliverable — they belong in the repo.** Everything else is a working artifact under `.testcases/testcase/` (CSV export, review-mode findings): never commit it, never put it in the docs tree.

```bash
root=$(git rev-parse --show-toplevel) && gitdir=$(git rev-parse --git-dir)
mkdir -p "$root/.testcases/testcase"
grep -qxF '/.testcases/' "$gitdir/info/exclude" 2>/dev/null \
  || echo '/.testcases/' >> "$gitdir/info/exclude"
```

`.git/info/exclude` is local-only — no diff, `.gitignore` untouched. Not a git repo: create the directory anyway and say the output is untracked-by-convention.

The coverage map stays in the reply; persist only on request, to `.testcases/testcase/coverage-map.md`.

| ID | Req | Category | Test Case | Preconditions | Steps | Expected Result | Priority | Automatable |
| -- | --- | -------- | --------- | ------------- | ----- | --------------- | -------- | ----------- |

**ID** — `TC-<area>-<3 digits>`, e.g. `TC-DROPDOWN-001`. IDs are permanent: on re-runs keep IDs for unchanged cases, append new ones, and mark removed cases `[OBSOLETE]` in the ID or Test Case cell (where the script looks) instead of deleting. Never renumber — downstream tools hold these IDs.

**Req** — the requirement/ticket/spec-section ID this case traces to. Every case traces to something; no requirement means regression (`REG`) or a question for the requirement owner.

**Category** — exactly one of: `Positive`, `Negative`, `Boundary`, `Validation`, `State`, `Permission`, `Error`, `Data`, `UI`, `Integration`, `Regression`.

**Steps** — concrete data only: "enter `100`", "select `A01: 土木`". Never "enter a valid value". Unknowable value → state the assumption.

**Priority** — by impact, not feeling:

| | Criteria |
| -- | -------- |
| **P0** | Data loss/corruption, permission bypass, wrong money/calculation, main flow blocked, security exposure |
| **P1** | Business rule wrong but workaround exists; secondary flow broken; recoverable unhandled error |
| **P2** | Rare input, cosmetic, low-impact edge case |

**Automatable** — `Y`: an automated test could drive it (deterministic setup, machine-checkable assertion). `N`: needs a person (visual judgement, physical device, unscriptable external system). The handoff to whoever builds the automated suite — decided once here, not re-litigated later.

**Output language** — match the requirement input (Japanese spec → Japanese cases) unless asked otherwise.

No duplicate cases to inflate the count. One distinct behavior or risk per case.

### 4. MANDATORY: independent second pass

**The core purpose of this skill. Never skip it.**

Spawn subagents (`Agent`/`Task`, `general-purpose`) and give each **only**: the requirement text, the test case table, and the path to `references/coverage-map.md` (+ `i18n-jp.md` if used).

**Not your pass-1 reasoning** — sharing your analysis makes the reviewer rubber-stamp your blind spots. It must rebuild the coverage map from the requirement and map the cases onto it.

Run **two reviewers per round, in parallel** — one holding both lenses finds the gaps of whichever it started with, then stops:

| Lens | Question |
| ---- | -------- |
| Trace | Every requirement statement has a case; every case traces back |
| Attack | How does it break while the happy path passes? State, permission, concurrency, dependency failure, boundary |

Each returns only: (1) dimensions with no case, (2) duplicates, (3) weak cases — vague steps, missing/untestable expected result, no traceability, (4) expected results contradicting the requirement. Merge the two, drop overlap.

**Repeat until a round converges** — adds no case, changes no expected result. Strip the previous round's notes first; a reviewer that sees them agrees instead of re-deriving. No fixed cap: P0/P1 gaps mean another round, P2 wording tweaks end the loop, and still finding P0/P1 gaps at round 4 → report **unconverged**, not finished.

No subagent tool: do pass 2 inline, one lens at a time, re-deriving the coverage map from the requirement before looking at your table.

### 5. Merge the findings

Append new cases to the same file, plus a section per case:

```text
TC-XXX-0NN
Reason missed in first pass: ...
```

Nothing found → say so plainly: "No additional high-value test cases identified after the second-pass review." Never claim "all cases are covered."

### 6. Count and lint with the script

Do not count rows by hand.

```bash
python3 scripts/summarize.py testcases.md                                      # counts + lint
python3 scripts/summarize.py testcases.md --requirements reqs.txt              # requirements with no case
python3 scripts/summarize.py testcases.md --csv .testcases/testcase/out.csv    # TestRail/Excel export
python3 scripts/summarize.py --diff .testcases/testcase/previous.md testcases.md
```

Fix every reported problem, re-run until clean.

**Two-way traceability.** The table proves case → requirement; `--requirements` proves the reverse. Feed it the step-1 IDs, one per line (`R1: description` fine, `#` comments skipped) — it names the requirements nothing traces to, a gap no review of the table can see.

**Accepting a gap needs a reason, not silence.** Two checks fail the run: >40% of live cases `Positive`, and a requirement covered by success-path cases only. Where genuinely correct, record it:

```text
<!-- coverage-ok: R7 — L1 is a read-only display field, it has no invalid input -->
<!-- coverage-ok: positive-ratio — feature only renders, every input path belongs to R3 -->
```

No reason = lint error. Stale (requirement gained risk cases, or has no live case) = reported for removal. Rule 6, made checkable.

**Re-running against an updated requirement.** Copy the current table to `.testcases/testcase/previous.md` first, `--diff` afterwards: reports added/changed/newly-`[OBSOLETE]`, **fails** on an ID deleted outright — the mistake that silently breaks downstream tools.

### 7. Report

Give the user: the file path (+ CSV if exported), the script's coverage summary, and a `## Remaining Questions / Assumptions` section for anything that blocked confident design.

---

## Rules

**1 — Never generate only happy paths.** The script decides, not your read of your own table: >40% `Positive`, or a requirement with no `Negative`/`Boundary`/`Validation`/`Error`/`Permission` case, fails the lint.

**2 — Analyze before generating.** Coverage map first, always.

**3 — Two passes, the second independent.** Pass 1 builds; pass 2 attacks. Same context reviewing itself is not a review.

**4 — Risk coverage beats quantity.** 30 cases covering real risks beat 100 repetitive ones.

**5 — Do not invent requirements.** Unknown behavior → `Expected result: TBD — requirement clarification needed`. Do not guess.

**6 — Distinguish "not applicable" from "not tested".** N/A needs a why: `Permission: N/A — no authentication/authorization.` Never silently omit. Where the lint would fail on it, put the reason in a `coverage-ok` comment so the next run inherits the decision.

**7 — Be adversarial.** "How could this fail even though the happy path works?" drives the second pass.
