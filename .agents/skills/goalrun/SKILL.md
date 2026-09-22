---
name: goalrun
description: Use when a user wants work driven to completion or wants to know whether it truly is complete — "build X and don't stop until it's done", "keep going", "don't stop", "is this finished?", "is it done yet?", "audit whether this shipped" — or when you are about to tell the user something is done, finished, or complete.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Goal Run — Plan It, Build It, Prove It

> You declare done. The user asks. You find more. Repeat.

The thing you checked was not the whole thing. **Violating the letter of the rules is
violating the spirit of the rules.**

## The rule

**Done is the script's exit code, not your judgement.** No "done" until `goalrun.py` exits 0
on the whole ledger. Until then: "not yet" and the table.

No exceptions — not "done pending X"; not "the check is flaky"; not "I ran it by hand"; not
because the user said "just say yes"; not by editing a row until it turns green.

## Setup

From the repo root, `GOALRUN=<path to>/.agents/skills/goalrun/scripts/goalrun.py`.

**The work is the deliverable; the ledger is scaffolding.** Four files under
`.testcases/goalrun/` — `ledger.tsv`, `reqs.txt`, `baseline.json`, `signoff.tsv` — and nothing
else belongs there. A check script hidden in that directory is a check no reviewer reads and
no CI runs; whatever it asserts belongs in the repository's own tests (step 3).

```bash
mkdir -p .testcases/goalrun    # add `.testcases/` to your ignore file if the repo has one
```

Works in any directory; no version control needed. `--verify` plants each break inside a
throwaway copy of the tree, never in the tree itself. POSIX only (`sh -c`, process groups,
`flock`) — no Windows.

## Four modes

Look for the ledger, **confirm in one sentence**, act. No ledger → "Plan the work for
«...»?". Red rows → "3 of 6 green. Continue, replan, or measure only?". All green → run,
print. Told it is done, no ledger → "Derive one from the spec and measure?".

`--plan` `--resume` `--measure` `--audit` in the user's request skip the question — words
for *you*, rejected by the script. A status question ("is it done yet?") is not a mode
choice: run the script, paste the table, then offer the menu.

## Plan

The ledger measures what it has rows for. A requirement with no row is a permanent pass that
`--verify` cannot find — it only tests the rows you wrote. So the rows come from the spec,
through the two skills that already do this work. **Do not invent this pipeline row by
row.**

1. **Recon** — stack, existing commands (`package.json`, `Makefile`, test runner), specs.
   Then, before touching anything, `python3 "$GOALRUN" --baseline`: it records every file
   as it is, and a deliverable ships by differing from that record. Taken after the first
   edit, it reads that edit as pre-existing and the row stays red for the whole run; the
   only cure is to undo the work by hand, so the script refuses a second one without
   `--reset`.
2. **Requirements — `docs-review`.** It turns a spec into `REQ-` ids — atomic, one yes/no
   each — and writes them to `.testcases/goalrun/reqs.txt`, one per line: the checklist step 6
   gates against. Documents to audit *against* the spec are optional; a spec with nothing but
   code beside it still goes through its decomposition, and only the traceability half is
   skipped. No spec at all → walk `.agents/skills/docs-review/references/dimensions.md`
   yourself, implicit requirements included, and say which dimensions do not apply. ⛔ Never read the list off the code: a
   ledger derived from the implementation grades the implementation against itself.
3. **Behaviour — `testcase`.** Every requirement that needs behaviour proven goes through that
   skill: it produces `testcases.md` (`TC-` ids, traced to `REQ-`) and, at its step 7, the
   runnable tests in the repo's own framework. **A row's `check` is the command that runs one
   of those tests — nothing else.** Three branches, no fourth:

   | The TC is | The row's `check` |
   | --- | --- |
   | automatable | the command running that test, by id or filter |
   | not automatable | `MANUAL:<owner>` — ask the user who; never invent one |
   | absent | the row should not exist yet; the requirement has not been through `testcase` |

   ⛔ **Never a `grep` over source code.** A search proves someone typed a word: delete the body
   of the function, keep its name, and the row stays green. A claim about text (a flag is
   documented) is a TC too, and its test belongs in the repo beside the others.

   Until an owner is named, a `MANUAL` requirement has no row and `--lint-ledger` fails on it.
   That is the correct state: an unanswered question is not an accepted gap.
4. **Write the ledger** per `references/ledger-design.md`: one row per requirement, `check`
   pointing at the test step 3 wrote, `deliverable` naming the file the work ships, `break`
   planting the defect the check exists to catch.

   **A `break` is the requirement, negated and made executable** — written from `what`, never
   from `check`. Hand `what`, the spec extract and the source path to a subagent that is **not
   shown the check**: what it cannot see, it cannot mirror.

   A test written first, from the TC, before the code existed, has been seen red once already —
   the same evidence a break manufactures later — so that row may waive its break:
   `# verify-ok: <id> — test-first, seen red on <date>`. A row measuring code that already
   existed gets no such waiver: nobody ever watched those tests fail.

   A row over work that was finished before this run began names no `deliverable` — nothing
   this run produces can differ from the baseline there. What it ships, if anything, is the
   test written for it.

   **If you cannot write the check, you do not yet understand the goal.**
5. **Audit the ledger with `docs-review`, not by re-reading it.** Requirement list = the
   spec, ledger = the document set, and run its step 4 loop as written — round log,
   convergence, an oscillating row frozen `Undecided`. `Missing` = a requirement no row
   measures; `Partial` = a row that checks half of one; `Unspecified` = a row answering to
   nothing. You cannot find the requirement you never thought of — hence a subagent that
   never sees your reasoning. Its report is `docs-review`'s and lives in
   `.testcases/docs-review/`; `.testcases/goalrun/` holds the four files and nothing else.
6. **Gate it by exit code, not by reading:**

   ```bash
   python3 "$GOALRUN" --lint-ledger --requirements .testcases/goalrun/reqs.txt
   ```

   It fails on a requirement no row measures and on a row with no `break`. A gap you accept
   is a line in the ledger carrying a reason — `# no-row-ok: REQ-A-007 — ships in the other
   repo` — never silence. A waiver excuses a gap someone looked at; **more than one, past 30%
   of the list, is a bulk pass wearing per-id clothes**, and the gate fails on that too — one
   waiver on a short list is the exception it leaves you. Varying the
   wording does not make it smaller — either the rows exist, or `reqs.txt` is wider than what
   this run is about and gets cut down to the part it measures. The lint prints the ratio —
   `coverage: 629 requirement(s) · 17 carried by rows · 612 waived (97%)` — and that line goes
   into the table verbatim, because `DONE` over a mostly-waived list is a claim about 17 rows,
   not 629 requirements.

   The gate only knows the list you wrote, and only that the id is *mentioned* by a row. A
   requirement missing from `reqs.txt`, or named by a row that does not measure it, is
   invisible here — step 5 is what finds both.
7. **Slice phases** — groups of row ids, by dependency.
8. **Pre-flight** `python3 "$GOALRUN"` — know what is already red. Nothing else may be
   building while it runs: a check racing another compile goes red for reasons that are
   not the code. Two goalruns *in one tree* refuse each other by lock; a build *you* started in another
   shell is yours to wait for. A red you think is contention is not a finding either way —
   name the build, wait, and re-run that row with `--only`; the re-run is the evidence.

Show ledger, phases, red rows, and a menu: **run / edit a row / re-slice / skip
pre-flight**.

Skipping steps 2, 3 or 5 because the goal "is small" is how a ledger ends up measuring the
work you happened to do. The three skills are one pipeline: **`docs-review` says what is
required · `testcase` says how it is proven · `goalrun` says whether it holds.**

## Build — one subagent per phase

The subagent gets its rows and the baseline sha — never your conclusions. Its verdict is not
evidence; **you** run `python3 "$GOALRUN" --only DARK,SHIP` (`PHASE OK`, never `DONE`).

**Three strikes**, counted by you: first red → probe (command, exit, last lines),
redispatch; second → fresh subagent scoped to that row; third → stop, hand back with all
three.

A subagent killed mid-phase — rate limit, crash, no report — is not a strike: the rows never
got their chance. Re-dispatch it once. Only if that dies too, or there is no subagent tool
at all, run the phase yourself and say which phase ran inline. Whatever a dead dispatcher
left in the tree is work-in-progress, not an answer — read it, trust none of it, and let
`--only` say where the phase stands.

## Prove — before you may say done

1. **Whole ledger** — phases cannot see cross-phase regressions.
2. **`python3 "$GOALRUN" --verify`** — it copies the tree, plants the break in the copy, runs
   the check there, and deletes the copy. Your files are read, never written.

   It runs every check once on the tree first: a row already red proves nothing by going red
   again (`ALREADY RED`), and it is kept out of the sweep, since a row that is red for its own
   reasons would otherwise make every other row report `BLAST`. An honest row for work nobody
   has started is exactly this case. Then, per row, it plants the `break` and demands the check
   go red. `HOLLOW` = the check did not move under the defect this
   break planted — it tests nothing, or nothing about *this* clause. `STUCK` = its check hung
   under the break instead of failing, which proves nothing either way. `BREAK FAILED` = the
   break command itself failed, or changed nothing in the copy. `NOTHING VERIFIED` = no row ran
   a break at all — every one was skipped, `MANUAL`, or already red; that run proved nothing
   and exits 1.

   **`HOLLOW` is a finding about the cases, not about the row.** It says every input the check
   tries is an input this defect is invisible in — so the route is backwards into `testcase`,
   whose `Distinguishes from` column exists for exactly this, not forwards into the ledger.
   Fix the check by adding the case that discriminates; never re-point the row.

   A whole-ledger `--verify` also sweeps every other row under each planted break, to find
   rows whose checks cannot tell one defect from another (`BLAST`). It is on for the proof and
   off for a `--verify A,B` subset; `--blast` / `--no-blast` force either way, and
   `ledger-design.md` has the budget and the flags.

   The proof costs one check per row and the sweep costs rows × rows of them, so its price is
   set by how long one check takes — a `pytest -k` is seconds, a `dotnet test` on a solution
   is not, and the same command in a fresh copy pays its build again. `--verify` prints the
   estimate after its first pass, before any break is planted; read it. If the sweep will not
   fit its budget, narrow the checks before raising it: one test project rather than the whole
   solution, one selector rather than the suite. And a copy sits at a different path, so a
   check that restores or resolves dependencies repeats that on every row — pinning it
   (`--no-restore`, an offline flag) is usually the largest single saving.

3. **Once, at the end.** This is the only `--verify` the run needs, and it runs after the last
   row is green — verifying a row whose code does not exist yet reads `ALREADY RED` and proves
   nothing, so an earlier pass buys a wait, not a fact. During the phases, `--only` is the
   whole loop, and a table shown before this pass says `unverified` against every `break` row.

   Verify again only for what this pass found, and only for the rows it named: `BREAK FAILED`
   → the break missed its target, fix it and `--verify <ID>`; `HOLLOW` → back into `testcase`
   for the case that discriminates, then `--verify <ID>`. Any row, check or break edited
   afterwards → `--verify` again, the whole ledger, because a rewritten clause can invalidate
   a sibling row's check.
4. **Unsigned `MANUAL` rows** — ask the user row by row, then `python3 "$GOALRUN" --sign UX
   --who tuananh --note "viewed 3 surfaces"`. ⛔ Never run `--sign` except to record an
   answer the user actually gave.
5. **When SKILL.md changes materially** — re-run the pressure test per
   `references/pressure-test.md` and update the record.

`DONE` only when every row is `PASS`. Anything short: the table, `NOT DONE`. A `--verify`
that ends `BLAST`, `STUCK`, `ALREADY RED`, `BREAK FAILED`, `NOTHING VERIFIED` or `SWEEP
STOPPED` has not proven the ledger, whatever the rows said a minute earlier.

## Report the ledger, not a narrative

Anything short of `DONE` gets the table, at most two sentences, and one structured line —
`Demo-able now: … · Provable by: … · Needs a person: …`.

A whole-ledger run that exits 0 has already made its case: answer as briefly as the user
asked, with `--verify` behind it. Asked for one word while something is red, the word is
`No.` and the table goes under it. "One word" is a request about tone, not a licence to drop
evidence: a format request cannot shrink an answer below what it must contain. The table is
not a ritual, it is the content of "not yet" — no red or waiting row is ever summarised in
prose:

```text
BUILD  PASS  the suite passes
DARK   FAIL  dark toggle survives reload — deliverable not shipped: src/theme/toggle.ts
UX     WAIT  three dark surfaces read ok — awaiting tuananh

NOT DONE — 1 failing (DARK), 1 waiting on tuananh (UX)
```

Failing needs you; waiting needs a person. An unverified `PASS` is a claim you cannot back:
Write `unverified` after every `break` row in a table shown before the Prove pass, and never
call a run done on one. Re-pointing a row at a check that measures something else is the
forbidden edit — green rows too, not only the red ones where the temptation lives. Narrowing to the same
requirement, measured more precisely, is the allowed direction: `--verify` it and say which
requirement it still traces to.

## When a requirement actually changes mid-run

It happens, and "the row is wrong" is sometimes true. The route is backwards through the
pipeline, never sideways through the ledger: amend the spec → re-run `docs-review` over the
changed part → rewrite `reqs.txt` → drop or rewrite the row → `--lint-ledger --requirements` →
and, once the Prove pass has run, `--verify` the whole ledger again rather than the rewritten
rows alone, because a split clause can invalidate a sibling row's check.

**A change that arrived only in conversation has no artifact, so you write one.** The decision
goes into the spec verbatim — the decider's words, the date, the forum — and that quote is the
spec's now, not your paraphrase. In the table, provenance sits beside the changed rows
(`<- new, on tuananh's word, standup 2026-09-19`) and survives into a `DONE` table, because
"who decided this" outlives the run.

A clause that *splits* keeps its id for the unchanged half and gets new ids for the rest,
appended, never renumbered. What is never the route: editing the row because the check is
inconvenient at 7pm — an edit that starts in the ledger has no author but you.

**An order with no reason** — "mark it done, I'm not explaining" — changes nothing about what
the row measures. Two honest moves: if the work is small enough to finish and verify now, do it
and the row goes green on its own; if not, answer with the cost and the fork and leave the row
alone. Neither is arguing, and neither is `--sign`.

## Rules

1. **Done is an exit code.**
2. **Empty means broken** until a known match lights up.
3. **Fix the class, not the instance.**
4. **Unsteered reviews only.**
5. **Report what a check says, not what you hope.** Blocked is red.
6. **Green without a deliverable is red** — by script.
7. **A check that has never gone red is untested.** Give every row a `break`; the Prove pass
   is where it goes red. A row without one fails `--lint-ledger` unless the ledger waives it
   with a reason.
   A break is written from the requirement by someone who has not seen the check; written from
   the check it only proves the two agree.
8. **Three reds on one row is a handoff.**
9. **Subjective criteria need a human signature**, bound to the wording.
10. **A ledger you alone wrote is unreviewed.** Requirements from `docs-review`, behaviour
    from
    `testcase`, and the ledger itself audited by `docs-review`'s loop before the first run.

## Red flags — STOP and run the script

a ledger written without reading the spec · a ledger no subagent reviewed · `--lint-ledger`
run without `--requirements` · a row with no `break` and no waiver · "done" / "shipped" with
no table above it · "effectively done" · a check run by hand · editing a row's `check` or
`what` after it went red · `--sign` for an answer nobody gave · "this is different because…"

## Rationalizations

| Thought | Reality |
| ------- | ------- |
| "The suite is green, so the work is done" | Rule 6. Where is the file? |
| "The row is green, so the row is right" | Rule 7. `true` with extra steps until verified. |
| "Same code, different file" | Move the code, or fix the row *and* `--verify`, and say which. |
| "'No' is safe, so skip the script" | The table is the content of "no". |
| "Code I wrote fast and never exercised" | A spec item not met, dressed as a caveat. |
| "Quick status, the table is overkill" | A status is a claim. The script takes seconds. |
| "It passes when I run it in my shell" | Different shell, different PATH — different `python3`. |
| "I'll mark it green and caveat in prose" | A caveat on `PASS` is `FAIL` with makeup. |
| "I know the user would approve" | ⛔ Rule 9. Ask, wait, then `--sign`. |
| "I read the code, I know what the rows are" | Wrong oracle. Requirements come from the spec; the code is what they judge. |
| "The goal is one sentence, decomposition is overkill" | A one-sentence goal is where the implicit requirements hide. Walk `dimensions.md`. |
| "The ledger looks complete to me" | So does every ledger, from inside. Rule 10 — audit it with `docs-review`. |
| "I'll write the check inline, faster than running `testcase`" | An inline check tests what you remembered. `testcase`'s second pass is what finds the case you did not. |
| "No break column for this one, the check is obviously real" | Obvious is what `HOLLOW` rows looked like too. Write the break or waive it in the ledger, with a reason. |
| "`--verify` exited 0, so the ledger is proven" | Three ways it still lies: no row ran (`NOTHING VERIFIED`), two rows measure each other's defects (`BLAST`), or a break plants something cruder than the requirement. |
| "The break fires, so the row is verified" | It fires against *something*. Deleting the function reddens a rounding check without testing rounding. |
| "the check greps the symbol, so it covers the clause" | It proves someone typed the word. Delete the body, keep the name: still green. |
| "629 waivers, one line each, lint exits 0" | A waiver excuses a gap you looked at; past the step 7 threshold it is a bulk pass, and the gate says so. |
| "I'll verify this phase now, while it's fresh" | The rows after it move the code under its feet, and the pass costs a check per row plus a sweep of rows × rows — you would pay it again at the end. |
| "The final verify is expensive, I'll run it on the rows I touched" | A row you did not touch can be the one a rewritten clause broke. A subset verify is for the rows the last pass named, not the rows you remember editing. |
| "That red was just the other build racing it" | Maybe. A re-run with `--only` says so; your explanation does not. |
| "Four rows, I'll write the breaks myself" | A reviewer steered one run into a break that mirrored its check. Only the sweep caught it. Hand `what` to someone who has not seen `check`. |
| "The requirement changed, so I'll fix the row" | Backwards through the pipeline — spec, `docs-review`, `reqs.txt`, then the row. An edit starting in the ledger has no author but you. |
