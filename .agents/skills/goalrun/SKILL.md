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

**The work is the deliverable; the ledger is scaffolding.** It lives under
`.testcases/goalrun/` (`ledger.tsv`, `signoff.tsv`, `baseline`), never committed:

```bash
root=$(git rev-parse --show-toplevel) && gitdir=$(git rev-parse --git-dir)
mkdir -p "$root/.testcases/goalrun"
grep -qxF '/.testcases/' "$gitdir/info/exclude" 2>/dev/null \
  || echo '/.testcases/' >> "$gitdir/info/exclude"
```

Not optional: `--verify` runs `git clean -fdq`, which spares only what git ignores.
The script is POSIX-only (`sh -c`, process groups, git) — no Windows.

## Four modes

Look for the ledger, **confirm in one sentence**, act. No ledger → "Plan the work for «...»?".
Red rows → "3 of 6 green. Continue, replan, or measure only?". All green → run, print.
Told it is done, no ledger → "Derive one from the spec and measure?".

`--plan` `--resume` `--measure` `--audit` in the user's request skip the question — words for
*you*, rejected by the script. A status question ("is it done yet?") is not a mode
choice: run the script, paste the table, then offer the menu.

## Plan

1. **Recon** — stack, existing commands (`package.json`, `Makefile`, test runner), specs.
2. `python3 "$GOALRUN" --baseline` — first; deliverable rows refuse to run without it.
3. **Write the ledger** per `references/ledger-design.md`. **If you cannot write the check,
   you do not yet understand the goal.**
4. `python3 "$GOALRUN" --lint-ledger` — shape only; realness is `--verify`'s job.
5. **Slice phases** — groups of row ids, by dependency.
6. **Pre-flight** `python3 "$GOALRUN"` — know what is already red.

Show ledger, phases, red rows, and a menu: **run / edit a row / re-slice / skip pre-flight**.

## Build — one subagent per phase

The subagent gets its rows and the baseline sha — never your conclusions. Its verdict is
not evidence; **you** run `python3 "$GOALRUN" --only DARK,SHIP` (`PHASE OK`, never `DONE`).

**Three strikes**, counted by you: first red → probe (command, exit, last lines), redispatch;
second → fresh subagent scoped to that row; third → stop, hand back with all three.

## Prove — before you may say done

1. **Whole ledger** — phases cannot see cross-phase regressions.
2. **Commit, then `python3 "$GOALRUN" --verify`** — plants each row's `break`, demands the
   check go red, restores. `HOLLOW` = the check tests nothing; fix the check, not the row.
3. **Unsigned `MANUAL` rows** — ask the user row by row, then
   `python3 "$GOALRUN" --sign UX --who tuananh --note "viewed 3 surfaces"`.
   ⛔ Never run `--sign` except to record an answer the user actually gave.
4. **When SKILL.md changes materially** — re-run the pressure test per
   `references/pressure-test.md` and update the record.

`DONE` only when every row is `PASS`. Anything short: the table, `NOT DONE`.

## Report the ledger, not a narrative

Every "is it done?" gets the table, at most two sentences, and one structured line —
`Demo-able now: … · Provable by: … · Needs a person: …`:

```text
BUILD  PASS  the suite passes
DARK   FAIL  dark toggle survives reload — deliverable not shipped: src/theme/toggle.ts
UX     WAIT  three dark surfaces read ok — awaiting tuananh

NOT DONE — 1 failing (DARK), 1 waiting on tuananh (UX)
```

Failing needs you; waiting needs a person. An unverified `PASS` is a claim you cannot back:
`--verify` every `break` row before the first table you show, write `unverified` after any
row without one. Re-pointing a red row is the forbidden edit unless you `--verify` it and say so.

## Rules

1. **Done is an exit code.**
2. **Empty means broken** until a known match lights up.
3. **Fix the class, not the instance.**
4. **Unsteered reviews only.**
5. **Report what a check says, not what you hope.** Blocked is red.
6. **Green without a deliverable is red** — by script.
7. **A check that has never gone red is untested.** `--verify` it.
8. **Three reds on one row is a handoff.**
9. **Subjective criteria need a human signature**, bound to the wording.

## Red flags — STOP and run the script

"done" / "shipped" with no table above it · "effectively done" · a check run by hand ·
editing a row's `check` or `what` after it went red · `--sign` for an answer nobody gave ·
"this is different because…"

## Rationalizations

| Thought | Reality |
| ------- | ------- |
| "The suite is green, so the work is done" | Rule 6. Where is the file? |
| "The row is green, so the row is right" | Rule 7. `true` with extra steps until verified. |
| "Same code, different file" | Move the code, or fix the row *and* `--verify`, and say which. |
| "'No' is safe, so skip the script" | The table is the content of "no". |
| "Code I wrote fast and never exercised" | A spec item not met, dressed as a caveat. |
| "Quick status, the table is overkill" | A status is a claim. The script takes seconds. |
| "I'll mark it green and caveat in prose" | A caveat on `PASS` is `FAIL` with makeup. |
| "I know the user would approve" | ⛔ Rule 9. Ask, wait, then `--sign`. |
