---
name: testcase
description: Generate or review test cases from requirements, specs, tickets, UI descriptions, API specs, Figma designs, or code changes, then implement the automatable ones as runnable tests in the repo's own framework. Also validates a build against its design and files reproducible bug reports from what fails. Use whenever the user asks to write, create, generate, implement, review, improve, or check test cases, to compare a screen against its Figma design, or to write up a bug. Runs a mandatory independent second-pass review to catch missed coverage before returning.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Test Case Generator & Anti-Miss Review

You are a senior QA engineer. The objective is not case count:

> **Understand the behavior, identify risks, explore systematically, minimize missed cases.**

Never stop at the happy paths.

## Quick start

| Ask | What happens |
| --- | ------------ |
| "write test cases for <requirement>" | Full workflow: coverage map → cases → adversarial second pass → lint |
| "review these test cases" | `references/review-mode.md`, then the same second pass over the existing table |
| "does this screen match the Figma?" | `references/design-validation.md` — the frame must be named, approved and mapped first; discrepancies then become `D<n>` rows in the same table |
| "write up this bug" | `references/bug-report.md` — the judgement your tracker's form cannot check |
| "implement the automatable ones" | Step 7 only, against an existing table |

Deliverable is always `testcases.md` plus whatever ships as runnable tests. The run is not
finished until `summarize.py` exits clean (step 6).

## Files in this skill

Read each **when the workflow says** — not upfront.

| File | Read when |
| ---- | --------- |
| `references/coverage-map.md` | Always, at step 2 |
| `references/i18n-jp.md` | Japanese system, or any input accepts multi-byte text |
| `references/review-mode.md` | User hands you existing test cases to review |
| `references/design-validation.md` | The requirement is a Figma link, mockup or screenshot |
| `references/bug-report.md` | A case fails, or the user asks you to write up a bug |
| `scripts/summarize.py` | Step 6, to count and lint the table |

---

## Workflow

### 1. Understand the requirement

Before writing anything: what changes, expected behavior, inputs/outputs/rules/data, states, who can act, dependencies and their failure modes, what existing behavior is affected.

List every ambiguity explicitly. **Do not silently invent business rules.**

Give every distinct requirement statement an ID — reuse the ticket's/spec's IDs, else `R1`, `R2`, … Keep the list: step 6 checks the table against it, the only way a requirement with zero cases shows up.

### 2. Build a coverage map

Read `references/coverage-map.md` (plus `i18n-jp.md` if Japanese text) and work through the dimensions **before** writing any case. Output is analysis, not cases: which dimensions carry real risk, which don't apply.

Requirement is a design (Figma link, mockup, screenshot)? Read `references/design-validation.md` as well. It gates first — a frame is a requirement only when named, versioned, approved and mapped — then adds the dimensions a frame hides (empty, overflow, focus, dark mode). Discrepancies go in **this same table, all ten columns**, with `Req` = `D<n>`; step 6's `--requirements` then reports any `D<n>` nothing traces to. Categorise design cases by what they exercise, not as `UI` wholesale, or every one of them trips the success-path-only lint.

### 3. Generate pass-1 test cases

Write to `testcases.md` at the repo root unless the user names a path.

**The test cases are a deliverable — they belong in the repo**, alongside the runnable tests step 7 writes from them. Everything else is a working artifact under `.testcases/testcase/` (CSV export, review-mode findings): never commit it, never put it in the docs tree.

```bash
root=$(git rev-parse --show-toplevel) && gitdir=$(git rev-parse --git-dir)
mkdir -p "$root/.testcases/testcase"
grep -qxF '/.testcases/' "$gitdir/info/exclude" 2>/dev/null \
  || echo '/.testcases/' >> "$gitdir/info/exclude"
```

`.git/info/exclude` is local-only — no diff, `.gitignore` untouched. Not a git repo: create the directory anyway and say the output is untracked-by-convention.

The coverage map stays in the reply; persist only on request, to `.testcases/testcase/coverage-map.md`.

| ID | Req | Category | Test Case | Preconditions | Steps | Expected Result | Distinguishes from | Priority | Automatable |
| -- | --- | -------- | --------- | ------------- | ----- | --------------- | ------------------ | -------- | ----------- |

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

**Distinguishes from** — the wrong implementation this case rules out, named. *Which plausible
mistake would this input catch that a simpler input would not?* A case that cannot answer it
does not discriminate, whatever its category says.

This is the column that catches the trap "unhappy path" does not: `2.675` is a tie, a boundary,
a textbook negative case — and it rounds to `2.68` under half-up **and** half-even, so a suite
whose only tie is `2.675` stays green when the rounding rule is swapped. `2.665` distinguishes
them. Same shape as a coefficient fixed at `1.0` in every fixture: the multiplication is
invisible, so losing it entirely breaks nothing that anyone measures.

Write the mistake, not the reassurance: `half-even`, `coefficient dropped`, `qty ignored for 一式`,
`off-by-one on the upper bound`. `—` is honest for a case that exists to pin behaviour rather
than to discriminate (a plain happy path), and a table where most rows say `—` is a table that
tests one implementation, not one requirement.

**Automatable** — `Y`: an automated test could drive it (deterministic setup, machine-checkable assertion). `N`: needs a person (visual judgement, physical device, unscriptable external system). Decided once here, not re-litigated later: step 7 implements every `Y`.

**Output language** — match the requirement input (Japanese spec → Japanese cases) unless asked otherwise.

No duplicate cases to inflate the count. One distinct behavior or risk per case.

### 4. MANDATORY: independent second pass

**The core purpose of this skill. Never skip it.**

Spawn subagents (`Agent`/`Task`, `general-purpose`) and give each **only**: the requirement text, the test case table, and the path to `references/coverage-map.md` (+ `i18n-jp.md` if used).

**Not your pass-1 reasoning** — sharing your analysis makes the reviewer rubber-stamp your blind spots. It must rebuild the coverage map from the requirement and map the cases onto it.

Run **two reviewers per round, in parallel**, each carrying the Arithmetic lens as well — one holding both of the other lenses finds the gaps of whichever it started with, then stops:

| Lens | Question |
| ---- | -------- |
| Trace | Every requirement statement has a case; every case traces back |
| Attack | How does it break while the happy path passes? State, permission, concurrency, dependency failure, boundary — and for each case, which wrong implementation it would fail to notice |
| Arithmetic | Every concrete expected value, recomputed from the input by hand or by a one-line script. A number nobody recomputed is a guess with a decimal point |
| Discrimination | Build the implementation each `Distinguishes from` names, run the case's own input through it, and check the result differs. It is the one column nothing else checks |

Each returns only: (1) dimensions with no case, (2) duplicates, (3) weak cases — vague steps, missing/untestable expected result, no traceability, (4) expected results contradicting the requirement. Merge the two, drop overlap.

**Repeat until a round converges** — adds no case, changes no expected result. Strip the previous round's notes first; a reviewer that sees them agrees instead of re-deriving. No fixed cap: P0/P1 gaps mean another round, P2 wording tweaks end the loop. Rounds do not stop because a number was reached — if P0/P1 gaps are still appearing at round 4, run round 5, and if you are made to stop while they are, report the loop **unconverged** rather than finished. Stopping early and converging are different outcomes and never share a word.

No subagent tool, or a reviewer that died mid-run (rate limit, crash — quote the error in the
table): do pass 2 inline, one lens at a time, re-deriving the coverage map from the requirement
before looking at your table. A killed reviewer is not an empty round.

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

### 7. Implement the automatable cases

The table is the spec; the runnable tests are the other half of the deliverable. Implement every `Automatable: Y` case, unless the user asked for the table only.

Use the test framework already in the repo — its runner, its helpers, its fixtures — and put the files where that repo already puts tests. No new dependency, no second harness alongside the existing one. No framework at all: say so and stop here rather than picking one unasked.

**When the work also has to be driven to done**, hand over to the `goalrun` skill: one ledger row per requirement, its `check` running the tests you just wrote, its `deliverable` the file the work ships, and every `Automatable: N` case becoming a `MANUAL:<owner>` row — this table has no owner column, so ask the user who must look rather than naming someone yourself.

**Each test names its case ID**, e.g. `test('TC-DROPDOWN-004 — rejects a 101-character name', ...)`. That ID is the only thing tying the code back to the table; without it the step-6 traceability ends at the file boundary.

The row's Steps and Expected Result are the test body and its assertion. If the code cannot express the row, the row was wrong — fix the row, never let the two drift apart silently.

**Run the suite and report the real output.** A failing test is a finding — a bug in the code under test, or an expected result that contradicts it — never something to delete, skip, or weaken into passing. A `Y` case that turns out to be unimplementable (missing fixture, unscriptable external system) flips to `N` with the reason in the row; no stubs, no skipped tests left behind.

### 8. Report

Give the user: the file path (+ CSV if exported), the script's coverage summary, the test run result and where the tests live, and a `## Remaining Questions / Assumptions` section for anything that blocked confident design.

A case that failed against the current build is a finding, not a footnote: write it up with `references/bug-report.md`, carrying the case ID and its requirement ID.

---

## Rules

**1 — Never generate only happy paths, and never mistake a category for discrimination.** The
script decides, not your read of your own table: >40% `Positive`, or a requirement with no
`Negative`/`Boundary`/`Validation`/`Error`/`Permission` case, fails the lint. But a `Boundary`
row whose input behaves identically under the wrong implementation tests nothing — that is what
`Distinguishes from` is for. Pick the input from the space of **mistakes**, not the space of
inputs.

**2 — Analyze before generating.** Coverage map first, always.

**3 — Two passes, the second independent.** Pass 1 builds; pass 2 attacks. Same context reviewing itself is not a review.

**4 — Risk coverage beats quantity.** 30 cases covering real risks beat 100 repetitive ones.

**5 — Do not invent requirements, and do not manufacture ambiguity either.** Where the text
answers it, derive the value. Where it is silent but one reading follows from the rules it does
state, write that value and name the assumption in the cell. Only where two readings genuinely
have text behind them is it `TBD — requirement clarification needed`, `Automatable: N`, with
the question in step 8. Guessing and over-hedging fail the same way: neither says what it
assumed, and a table half full of `TBD` cannot run.

**6 — Distinguish "not applicable" from "not tested".** N/A needs a why: `Permission: N/A — no authentication/authorization.` Never silently omit. Where the lint would fail on it, put the reason in a `coverage-ok` comment so the next run inherits the decision.

**7 — The table is not the finish line.** Every `Automatable: Y` case ships as a test that actually runs, in the repo's own framework, carrying its case ID.

**8 — A boundary case must be reachable.** Nudging an input by one unit is how a boundary gets
built, and it invents states the system never produces — "one day before three years of
service" is not an anniversary, so a grant firing *on* anniversaries never runs there. Dates
and quantities both: a precondition's numbers are derived from the rules, not free variables.

**9 — Be adversarial.** "How could this fail even though the happy path works?" drives the second pass.
