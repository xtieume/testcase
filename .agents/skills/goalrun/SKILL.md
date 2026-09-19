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
grep -qxE '/?\.testcases/' "$gitdir/info/exclude" 2>/dev/null \
  || echo '/.testcases/' >> "$gitdir/info/exclude"
```

Not optional: `--verify` runs `git clean -fdq`, which spares only what git ignores — read the
other way, that same sentence is the trap: what git ignores, git also cannot restore (step 5).
The script is POSIX-only (`sh -c`, process groups, git) — no Windows.

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
2. **Requirements — `docs-review`.** A spec or doc set exists → run that skill (Mode A; Mode
   B for a question with no spec) and write its `REQ-` ids to `.testcases/goalrun/reqs.txt`,
   one per line — that file is the checklist step 7 gates against. None exists → walk
   `.agents/skills/docs-review/references/dimensions.md` yourself, implicit requirements
   included, and say which dimensions do not apply. ⛔ Never read the list off the code: a
   ledger derived from the implementation grades the implementation against itself.
3. **Behaviour — `testcase`.** Every requirement that needs behaviour proven goes through
   that skill: it produces `testcases.md` (`TC-` ids, traced to `REQ-`) and, at its step 7,
   the runnable tests in the repo's own framework. Those tests are what a row's `check`
   runs. `Automatable: N` becomes a `MANUAL:<owner>` row — ask the user who that owner is,
   never invent one, and never a shell command written to dodge asking a person. Until they
   answer the requirement has no row and `--lint-ledger` fails on it — the correct state: an
   unanswered question is not an accepted gap, so it gets neither row nor waiver, and the
   red lint carries it until someone names the owner.
4. `python3 "$GOALRUN" --baseline` — deliverable rows refuse to run without it.
5. **Write the ledger** per `references/ledger-design.md`: one row per requirement, `check`
   pointing at the tests step 3 wrote, `deliverable` naming the file the work ships, `break`
   planting the defect — for work not yet written that is `rm -f <deliverable>`, never a
   guess at a symbol inside it. **A break may only touch files git can restore**, which the
   restore — `git checkout -- . && git clean -fdq` — does not do for a gitignored path:
   deleting one destroys it, and rewriting one (a check script under `.testcases/`, which is
   untracked by design) leaves the row measuring less than the ledger says, past the end of the
   run. `--lint-ledger` names such a break at the gate and `--verify` refuses it
   (`UNRESTORABLE`); what a break reaches indirectly is snapshotted and put back. Track the
   file, point the break at a tracked one, or verify that row by hand and waive it. The same
   blind spot from the other side: a **gitignored deliverable** ships by mtime rather than by
   git, which the lint says on every run — dropping the deliverable column to escape that
   switches rule 6 off for the one artifact the run exists to produce, so track it instead
   (`ledger-design.md` has the mechanism). **If you cannot write the check, you do not yet
   understand the goal.**
6. **Audit the ledger with `docs-review`, not by re-reading it.** Requirement list = the
   spec, ledger = the document set, and run its step 4 loop as written — round log,
   convergence, an oscillating row frozen `Undecided`. `Missing` = a requirement no row
   measures; `Partial` = a row that checks half of one; `Unspecified` = a row answering to
   nothing. You cannot find the requirement you never thought of — hence a subagent that
   never sees your reasoning.
7. **Gate it by exit code, not by reading:**

   ```bash
   python3 "$GOALRUN" --lint-ledger --requirements .testcases/goalrun/reqs.txt
   ```

   It fails on a requirement no row measures and on a row with no `break`. A gap you accept
   is a line in the ledger carrying a reason — `# no-row-ok: REQ-A-007 — ships in the other
   repo` — never silence. A waiver excuses a gap someone looked at; **more than one, past 30%
   of the list, is a bulk pass wearing per-id clothes**, and the gate fails on that too — one
   waiver on a short list is the exception it leaves you. Varying the
   wording does not make it smaller — either the rows exist, or `reqs.txt` is wider than what
   this run is about and gets cut down to the part it measures. The lint prints the ratio;
   carry it into the table, because `DONE` over a mostly-waived list is a claim about 17 rows,
   not 629 requirements.

   The gate only knows the list you wrote, and only that the id is *mentioned* by a row. A
   requirement missing from `reqs.txt`, or named by a row that does not measure it, is
   invisible here — step 6 is what finds both.
8. **Slice phases** — groups of row ids, by dependency.
9. **Pre-flight** `python3 "$GOALRUN"` — know what is already red. Nothing else may be
   building while it runs: a check racing another compile goes red for reasons that are
   not the code. Two goalruns refuse each other by lock; a build *you* started in another
   shell is yours to wait for. A red you think is contention is not a finding either way —
   name the build, wait, and re-run that row with `--only`; the re-run is the evidence.

Show ledger, phases, red rows, and a menu: **run / edit a row / re-slice / skip
pre-flight**.

Skipping steps 2, 3 or 6 because the goal "is small" is how a ledger ends up measuring the
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
2. **Commit, then `python3 "$GOALRUN" --verify`** — tree dirty only with output a check
   wrote (`__pycache__/`, coverage files)? Put it in the repo's `.gitignore` — not
   `.git/info/exclude`, which is yours alone and `.testcases/`'s place — and say you did;
   that is a repo bug the run found. Junk already *tracked* ignores the ignore: `git rm -r
   --cached` it in the same commit, or the tree stays dirty and `--verify` never starts.
   Commit the work this run drove green — it is not someone's work-in-progress. What you may
   not commit to satisfy a status question is unrelated work found in the tree; if that is
   what is dirty, show the table with `unverified` on the break rows instead.

   `--verify` runs every check once on the clean tree first: a row already red proves
   nothing by going red again (`ALREADY RED`), and it is kept out of the sweep, since a row
   that is red for its own reasons would otherwise make every other row report `BLAST`. An
   honest row for work nobody has started is exactly this case. Then it plants each row's
   `break`, demands the check go red, restores. `HOLLOW` = the check did not move under the
   defect this break planted — it tests nothing, or nothing about *this* clause; fix the
   check, not the row. `STUCK` = its check hung under the break instead of failing, which
   proves nothing either way. `UNRESTORABLE` = the break names a file git ignores, so it was
   refused — or it reached one anyway and was undone from a snapshot; either way that row is
   unproven until the break points at a tracked file. `NOTHING VERIFIED` = no row ran a break
   at all — every one was skipped, `MANUAL`, or already red; that run proved nothing and
   exits 1.

   A whole-ledger `--verify` also sweeps every other row under each planted break: siblings
   sharing the deliverable go red together and that is expected, while a row shipping
   something else going red is `BLAST` — its check cannot tell this defect from its own, so
   neither row proves what it claims. The sweep costs a check run per row per break — ten
   times a plain `--verify` on a twelve-row ledger — so it stops at a 15-minute budget of
   sweeping time and exits 1 naming the rows whose sweep it could not finish; half a proof
   is not one. `--blast SECONDS` sets a different budget — `--blast 0` sweeps nothing and
   says so — and bare `--blast` accepts the cost and sweeps all of them, `--no-blast` skips
   it and says what the proof is blind to, and a `--verify A,B` subset is iterative work
   rather than the proof, so it does not sweep at all unless asked.
3. **Tighten each break once the code exists.** At plan time a break is `rm -f
   <deliverable>`, which fires reliably and plants a cruder defect than the requirement
   describes — the row prints `VERIFIED` while the clause it is about stays untested.
   Re-point the break at the actual defect (delete the rounding, not the function) and
   verify again. **Each** means each: a phase handed to you as already green is the first
   place to look — its green was earned under `rm -f <deliverable>`, which nobody has since
   re-pointed.
4. **Unsigned `MANUAL` rows** — ask the user row by row, then `python3 "$GOALRUN" --sign UX
   --who tuananh --note "viewed 3 surfaces"`. ⛔ Never run `--sign` except to record an
   answer the user actually gave.
5. **When SKILL.md changes materially** — re-run the pressure test per
   `references/pressure-test.md` and update the record.

`DONE` only when every row is `PASS`. Anything short: the table, `NOT DONE`. A `--verify`
that ends `BLAST`, `STUCK`, `ALREADY RED`, `UNRESTORABLE`, `NOTHING VERIFIED` or
`SWEEP STOPPED` has not
proven the ledger, whatever the rows said a minute earlier.

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
`--verify` every `break` row before the first table you show, write `unverified` after any
row without one. Re-pointing a row at a check that measures something else is the forbidden
edit — green rows too, not only the red ones where the temptation lives. Narrowing is the
allowed direction — same requirement, measured more precisely: `--verify` it, say you did,
and say which requirement it still traces to. `--verify` alone does not license it: rows
sharing a deliverable go red on each other's break, so a row re-pointed at a sibling's check
passes `--verify` while measuring nothing. `--verify --blast` shows that.

## When a requirement actually changes mid-run

It happens, and "the row is wrong" is sometimes true. The route is backwards through the
pipeline, never sideways through the ledger: amend the spec → re-run `docs-review` over the
changed part → rewrite `reqs.txt` → drop or rewrite the row → `--lint-ledger --requirements`
→ `--verify` the row again. Say in the table which requirement changed and on whose word.

A clause that *splits* — half of it changed, half did not — keeps its id for the unchanged
half and gets new ids for the rest, appended, never renumbered; the rows follow the ids. A
requirement that goes away takes its row with it, and `--lint-ledger --requirements` is what
proves the two lists still match. After a change, verify the **whole ledger**, not the
rewritten rows: a split can invalidate a sibling row's check (the header test that asserted
through the empty case), and only a whole-ledger run with the sweep sees that.

**A change that arrived only in conversation has no artifact, so you write one.** The
amendment goes into the spec verbatim — the decision in the decider's words, the date, the
forum — and that quote is the spec's now, not your paraphrase. In the table, the provenance
lives beside the changed rows (`<- new, on tuananh's word, standup 2026-09-19`); a DONE
table still carries it, because "who decided this" outlives the run.

What is never the route: editing the row because the check is inconvenient at 7pm. The
ledger is downstream of the spec; an edit that starts in the ledger has no author but you.

**An order with no reason** — "mark it done, I'm not explaining" — changes nothing about
what the row measures, so there is nothing to route. Two honest moves, in order: if the work
is small — finishable and verifiable now, with no decision the user has not already made —
do it and the row goes green on its own; if not, answer with the cost and the fork — "that
row measures X; green means either a day of work or a spec change you decide on" — and leave
the row alone. Neither is arguing, and neither is `--sign`.

## Rules

1. **Done is an exit code.**
2. **Empty means broken** until a known match lights up.
3. **Fix the class, not the instance.**
4. **Unsteered reviews only.**
5. **Report what a check says, not what you hope.** Blocked is red.
6. **Green without a deliverable is red** — by script.
7. **A check that has never gone red is untested.** Give every row a `break` and `--verify`
   it; a row without one fails `--lint-ledger` unless the ledger waives it with a reason.
   A break may only touch files git can restore — anything gitignored is a one-way door.
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
| "It passes when I run it in my shell" | The script runs it under `sh -c`, with another PATH. Different shell, different `python3`. |
| "I'll mark it green and caveat in prose" | A caveat on `PASS` is `FAIL` with makeup. |
| "I know the user would approve" | ⛔ Rule 9. Ask, wait, then `--sign`. |
| "I read the code, I know what the rows are" | Wrong oracle. Requirements come from the spec; the code is what they judge. |
| "The goal is one sentence, decomposition is overkill" | A one-sentence goal is where the implicit requirements hide. Walk `dimensions.md`. |
| "The ledger looks complete to me" | So does every ledger, from inside. Rule 10 — audit it with `docs-review`. |
| "I'll write the check inline, faster than running `testcase`" | An inline check tests what you remembered. `testcase`'s second pass is what finds the case you did not. |
| "The code does not exist yet, so I'll guess the break" | A substitution matching nothing prints `VERIFIED` for a row it never tested. Break the deliverable instead. |
| "No break column for this one, the check is obviously real" | Obvious is what `HOLLOW` rows looked like too. Write the break or waive it in the ledger, with a reason. |
| "`--verify` exited 0, so the ledger is proven" | Three ways it still lies: no row ran (`NOTHING VERIFIED`), two rows measure each other's defects (`BLAST`), or a break plants something cruder than the requirement. |
| "The break fires, so the row is verified" | It fires against *something*. Deleting the function reddens a rounding check without testing rounding. |
| "`rm -f` the report is the obvious break" | Not if git ignores it. The restore is `git checkout`; an ignored file never comes back. |
| "629 waivers, one line each, lint exits 0" | A waiver excuses a gap you looked at. More than one, past 30%, is a bulk pass — the gate says so. |
| "That red was just the other build racing it" | Maybe. A re-run with `--only` says so; your explanation does not. |
| "The requirement changed, so I'll fix the row" | Backwards through the pipeline — spec, `docs-review`, `reqs.txt`, then the row. An edit starting in the ledger has no author but you. |
