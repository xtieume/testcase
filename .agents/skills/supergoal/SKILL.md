---
name: supergoal
description: Use when the user sets a standing goal to drive work to completion ("keep going until it's done", "is X finished?", "run until empty", "/goal"), especially work that loops through testcase or docs-review rounds. Holds a machine-checked ledger so "what's left?" is answered by a script instead of recall, and refuses to declare done while any check still fails.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Supergoal — drive a goal to done without re-litigating "what's left"

You are finishing a piece of work under a standing goal. The failure this skill exists to
prevent is not "forgetting to work":

> **You declare done. The user asks. You find more. Repeat.**

Each cycle costs the user a full round trip and teaches them your "done" means nothing. The
cause is never laziness — it is that **the thing you checked was not the whole thing**, and
nothing mechanical was holding the boundary.

## The rule this skill enforces

**Done is a script's exit code, not your judgement.** You may not report a goal met until
`scripts/goal_status.py` exits `0`. Until then the honest answer is "not yet, here is the
ledger" — which takes one line, not a paragraph of apology.

---

## Workflow

### 1. Write the goal down as checks, before working

Turn the user's sentence into rows in `.goal/ledger.tsv` — one row per thing that must be
true, each with a **command that decides it**:

```
id      what                                    check
BUILD   the suite passes                        cd src && dotnet test --nologo
DOCS    every requirement is covered or ruled   python3 scripts/check_report.py report.md
CITE    every citation resolves                 python3 scripts/verify_citations.py report.md
ASK     no unanswered questions to the owner    python3 scripts/goal_status.py --open-questions
```

A row whose `check` is `MANUAL` is allowed **only** when the decision belongs to someone else
(a business owner, an approval). Write who owns it. ⛔ Never use `MANUAL` for something you
could check but haven't.

**If you cannot write the check, you do not yet understand the goal.** Ask one question, then
write it.

### 2. Enumerate the scope MECHANICALLY — this is where it goes wrong

Before any audit or test pass, produce the list of things in scope **with a command**, and
save it. Not from memory, not from what you touched last time.

```bash
git -c core.quotePath=false ls-files -- <roots> > .goal/scope.txt
wc -l < .goal/scope.txt
```

⛔ `core.quotePath=false` is not optional. `git ls-files` octal-escapes non-ASCII paths and
wraps them in quotes, so every path with CJK/accented characters becomes a filename that does
not exist. Piped to `xargs`, those files are **silently skipped** and the sweep reports zero.

**Then prove the scope is real** with a *known positive*: pick something you are certain is in
scope, grep for it, and confirm you find it. A scope list you have not tested is a guess.

### 3. Never trust an empty result

> **An empty search result means "my search failed" until proven otherwise.**

Before writing "not found", "0 occurrences", or "not documented anywhere", run the same search
against a case you *know* matches. If the control does not light up, the tool is broken, not
the corpus.

Measured failure modes that all silently print zero:

| Symptom | Cause |
|---|---|
| `grep -r --include='*.md'` finds nothing | the pattern or wrapper is filtering everything |
| `find > file` yields a few lines but `find \| wc -l` says hundreds | output rewritten by a proxy/optimizer — use `git ls-files` |
| `xargs -a list` errors | GNU-only; BSD/macOS has no `-a`. Use `cat list \| tr '\n' '\0' \| xargs -0` |
| a sweep misses whole directories | non-ASCII path escaping (§2) |
| a symbol "is not implemented" | you searched the **name**, not the **behaviour** |

That last one is its own trap: an identifier may be absent while the rule is fully implemented
under a different name. Read the code path before concluding a gap. Equally, hits may be
matches inside vendored binaries — check what matched.

### 4. Run the rounds — unsteered

When the goal involves coverage, chain the catalog's own skills: `docs-review` for
spec→document gaps, `testcase` for behaviour coverage. Both already carry a mandatory
independent review loop; this skill's job is to keep running them and to hold the ledger.

⛔ **Never hand a reviewer a priority list, a "settled ground" summary, or your own reasoning.**
A steered round agrees with you. Every steered round in the session that produced this skill
returned "converged"; every unsteered rerun immediately found defects, including P0 money bugs.

Give a reviewer only: the spec, the scope list from §2, the artefact under review with your
round notes stripped, and the instruction that **an empty round is a valid result**.

### 5. When a round returns a finding, fix the CLASS — not the instance

This is the rule that would have saved the most time in the session behind this skill. The
same defect was found and "fixed" **five times** because each fix touched only what the
reviewer pointed at:

| Round | Reviewer said | What was fixed | What was left |
|---|---|---|---|
| 1 | this file is missing from scope | added that one file | the other 40 in its directory |
| 2 | that directory is missing | added that one directory | the two sibling directories |
| 3 | these 12 rows are wrong | fixed those 12 | the other 20 rows against the newly-added docs |
| 4 | these citations drifted | fixed those line numbers | — (finally mechanical) |

After every finding, ask **"what else is of this kind?"** and re-run the derivation over the
whole class. Concretely:

- added a document to scope → **re-derive every row against it**, not just the cited row
- fixed one call site → grep every call site of that function
- corrected one positive clause → find its negative clause
- edited a file you cite → re-check **all** citations into that file

**Widening the scope and not re-deriving is the same bug as not widening it.**

### 6. Convert a repeated lesson into a check

The third time you write the same lesson in prose, stop and write a script instead. Prose you
have written three times is prose that does not work.

⚠️ **Then verify the verifier.** A checker that has never failed is not passing — it is
untested. Plant the exact defect it exists to catch and confirm a non-zero exit. In the session
behind this skill, a freshly written citation checker reported **19 false mismatches** before it
was right; without a known-positive control it would have quietly reported "clean" forever.

### 7. Report the ledger, not a narrative

Every time the user asks "is it done?", run the script and show its table. Two lines of prose
at most. The user should never have to ask "what's left?" twice and get a different answer.

```
$ python3 scripts/goal_status.py
BUILD  ✅ 3104 passed, 0 failed
DOCS   ✅ 60 rows: Covered 49, Partial 5, Contradict 3, Stale 2, Conflict 1
CITE   ✅ 58 citations resolve
ASK    ❌ 20 open questions (01-takeoff 9, stage3 6, 05 2, 03 1, 04 1, DQ-050 1)
⇒ NOT DONE — 1 of 4 checks failing
```

When a check is red because someone else must decide, say so in the row and keep it red.
⛔ **A blocked check is not a passed check**, and rewording it does not move the work.

---

## Rules

**1 — Done is an exit code.** No green script, no "done".

**2 — Scope is a command, not a memory.** Re-run it each round; it changes.

**3 — Empty means broken until a control proves otherwise.** Four different tools in one
session each silently reported zero.

**4 — Fix the class, not the instance.** "What else is of this kind?" after every finding.

**5 — Unsteered reviews only.** A reviewer given your conclusions returns your conclusions.

**6 — Three repeats of a lesson ⇒ write the script.** Then break the script on purpose to
prove it works.

**7 — Report what a check says, not what you hope.** A correction that arrives because the
user asked again is worth less than one you volunteer.

## Rationalizations

| Thought | Reality |
|---|---|
| "The last round was empty, so it's converged" | Empty over an unproven scope means the reviewer shared your blind spot. |
| "I fixed what they found" | You fixed the instance. Rule 4. |
| "Searching found nothing, so it's not there" | Rule 3. Run the control. |
| "It's not implemented — the symbol doesn't exist" | You searched a name. Read the code path. |
| "The user is waiting, I'll report now and verify after" | The report is the thing they act on. Run the script first; it takes seconds. |
| "I'll note the lesson so I don't repeat it" | You have noted it twice already. Rule 6. |
| "This check is blocked on someone else, so it's effectively fine" | Then it is red and named. Rule 7. |
| "Widening scope is a big refactor, I'll do the named fix now" | The named fix is the one that guarantees another round. |
