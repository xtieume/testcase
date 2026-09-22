# Writing a ledger

Read at Plan step 5, when the rows are being written.

## The shape of a row

Tab-separated, UTF-8 (BOM tolerated), `#` and blank lines skipped, extra columns ignored. No
field may contain a tab.

Write it with a file tool, never through `printf`/`echo` in a shell: single quotes turn `&&`
into `\&\&`, and under `sh -c` that runs the first command alone, exit 0, runner never called.
Read the check column back before the first run — `cut -f3 .testcases/goalrun/ledger.tsv` —
and the lint refuses `\&\&` or `\|\|` outright.

| Column | For |
| ------ | --- |
| `id` | Short, stable, unique, uppercase. Names the row in `--only`, `--sign`, `--verify`. |
| `what` | The condition in one sentence, carrying its `REQ-` id. Printed in the table; hashed into a `MANUAL` signature. |
| `check` | The command running the test that implements this requirement's `TC-`, or `MANUAL:<owner>`. Exit 0 means the condition holds. Never empty, never a search over source code. |
| `deliverable` | Optional path this row must have produced. `—`, `-` or empty means none. Not allowed on a `MANUAL` row — a row belongs to a decider or a file, not both. |
| `break` | The edit that plants the exact defect `check` exists to catch — `path :: what it says :: what it should say`, or a bare path to delete the file. Made and put back by `--verify`. Waivable only with a reason (below). |

**Verdict.** `MANUAL` → `WAIT` until signed. Otherwise the check runs; if it passes and the row
names a deliverable, that path must exist and its **content** must differ from what `--baseline`
recorded — a file the baseline never saw is new and counts, a directory counts if anything under
it was added, removed or changed, `touch` counts for nothing, absolute paths and `..` never
count. Else `FAIL — deliverable not shipped`. Work finished before the run has no deliverable to
name: nothing can differ from a baseline that already contains it.

## An example

```tsv
# id	what	check	deliverable	break
EXPORT	REQ-EXP-001 CSV export writes one row per order	python3 -m unittest -q tests.test_export.TC_EXP_001	src/export.py	printf 'def export(orders):\n    return []\n' > src/export.py
ROUND	REQ-EXP-002 money rounds half-up	python3 -m unittest -q tests.test_export.TC_EXP_004	src/export.py	sed 's/ROUND_HALF_UP/ROUND_HALF_EVEN/' src/export.py > t && mv t src/export.py
DOCS	REQ-DOC-001 the --export flag is documented	python3 -m unittest -q tests.test_docs.TC_DOC_001	docs/cli.md	grep -v -- '--export' docs/cli.md > t && mv t docs/cli.md
LINT	no debug prints left in src	! grep -rn 'print(' src/	—	printf 'print(1)\n' >> src/export.py
UX	REQ-UX-004 the CSV opens cleanly in Excel	MANUAL:tuananh	—	—
```

Each behavioural row names one test. `DOCS` is a claim about text and is still a test —
`tests/test_docs.py` reads the file and asserts — so a reviewer sees it in the diff and CI runs
it on every push. `LINT` is the exception that proves the shape: a hygiene rule belonging to no
requirement, so no `REQ-` and no test.

```bash
python3 "$GOALRUN" --baseline        # first of all, before the first edit — no ledger needed
python3 "$GOALRUN" --lint-ledger --requirements .testcases/goalrun/reqs.txt
python3 "$GOALRUN"                   # pre-flight, then per phase with --only
python3 "$GOALRUN" --verify          # VERIFIED / HOLLOW / STUCK / BREAK FAILED, plus the sweep
python3 "$GOALRUN" --sign UX --who tuananh --note "opened in Excel 16, columns intact"
```

## Where the rows come from

| Stage | Skill | Hands over |
| ----- | ----- | ---------- |
| What is required | `docs-review` | `REQ-<area>-<3 digits>`, atomic, one yes/no each |
| How it is proven | `testcase` | `TC-` traced to a `REQ-`, plus the runnable tests its step 7 writes |
| Whether it holds | `goalrun` | one row per `REQ-`, whose `check` runs those tests |

Carry the `REQ-` id into `what`: that string is what `--lint-ledger --requirements` matches. The
match is textual, so `REQ-DOC-002 deferred` satisfies the gate while measuring nothing — which
is why step 6 audits the ledger with `docs-review`'s loop as well. A `TC-` marked
`Automatable: N` becomes `MANUAL:<owner>`; ask who, never invent one.

No spec? Walk `.agents/skills/docs-review/references/dimensions.md` — its implicit requirements
(existing data at ship time, behaviour at every stated limit, the failure path of every success
path, reversibility) are the rows a ledger forgets.

**Waivers** are comment lines the script reads — id, space, dash, space, reason:

```tsv
# no-row-ok: REQ-DOC-002 — the manual ships from the docs repo, audited there
# verify-ok: ROUND — test-first from TC-EXP-004, seen red on 2026-09-18
```

No reason, no waiver. A waiver naming a row or requirement that is not in the ledger reads as an
accepted gap when it is only a line nobody deleted, so the lint reports it.

## Writing a `break`

A break is an edit goalrun makes and puts back, not a command it runs:

```
<path> :: <the text it holds now> :: <the text it should hold instead>
<path>                                       the file itself goes away
```

The text must appear in the file exactly once — twice, and which one the requirement means is
written down nowhere. Nothing goes through a shell, so there is no quoting to leak, no
`sed -i ''` that is BSD on one machine and GNU on the next, and no command that exits 0 having
done nothing. A break that finds nothing to change is `BREAK FAILED` **before** a check is
spent on it.

**From `what`, never from `check`.** A check that greps a symbol and a break that renames it
agree with each other and measure nothing, while printing `VERIFIED`. Hand `what`, the spec
extract and the source path to a subagent that has not seen the check.

**At the defect the requirement names**, not at the file holding it: remove the rounding, not
the function. Deleting `src/export.py` reddens any check that opens the file, so it proves the
check reads something, not that it reads this clause.

```tsv
ROUND	REQ-EXP-002 money rounds half-up	python3 -m unittest -q tests.test_export.TC_EXP_004	src/export.py	src/export.py :: ROUND_HALF_UP :: ROUND_HALF_EVEN
```

Three shapes that read as proof and are not:

| Shape | What `--verify` says |
| ----- | -------------------- |
| Break weaker than its requirement — deleting `src/tax.py` for a rounding clause | `VERIFIED`, and the clause stays untested |
| Row already red before anything was planted | `ALREADY RED`, kept out of the sweep |
| Check so broad it reddens on any defect | `BLAST` against rows shipping something else |

`--lint-ledger` reads the shape of a break, not its aim: it cannot tell a break weaker than its
clause from an exact one, the same way it cannot tell a real check from `true`. Only `--verify`
can.

## What a check costs

A verify costs one check per row, and `--blast` costs one per row per row. Narrow the command
and both shrink: one test project rather than the whole solution, one selector rather than the
suite. `--verify` times every check on its first pass and prints what the proof and the sweep
would cost before planting anything; read that line before deciding whether to pay for
`--blast`.

## What a break may and may not reach

`--verify` prints the ledger table, then per row makes the edit, runs the check, and writes the
file back byte for byte. It runs once, at the end, in place of the final plain run. The bytes
go to `.testcases/goalrun/undo/` before the check starts, so an interrupted verify restores on
its way out and a killed one is put back by the next run, which says which rows it repaired.

- **Only a file in the tree.** An absolute path, or one climbing out through `..`, is refused.
- **Only text.** A binary file has nothing to substitute in; delete it instead, or pick a
  different defect.
- **State outside the tree** — databases, services, `$HOME` — is neither changed nor undone by
  the break, and a check that writes to any of them leaves what it wrote.
- **A check runs in your tree**, as it does on a plain run, so a check that litters litters
  where it already did.
- **A directory deliverable** ships when anything under it changes — a check that writes a
  log into it counts, so keep generated output out of a directory a row names.

## The sweep

`--verify --blast` runs every other row under each planted break: `shared` for rows delivering
the same file (expected), `BLAST` (exit 1) for a row shipping something else, whose check
therefore cannot tell this defect from its own.

It costs a check per row per row, so its price is the price of one check. On a 12-row ledger of
0.25s checks, 4.4s becomes 42.8s — though rows running the identical command share one result,
so the ledger that most needs the sweep is cheapest on it (7.9s). On a check that builds a
solution, the same arithmetic is most of the run, which is why it is asked for rather than
assumed: a `--verify` without it says so, and says what it would cost. `--blast` sweeps under a
15-minute budget and prints `SWEEP STOPPED` (exit 1) over it, naming the rows it could not
finish; `--blast SECONDS` sets another. It discriminates only once checks are narrow: while
every row runs the whole suite, everything reddens everything.

## Turning a vague sentence into a check

Write the row when the command would fail today if the work were not done.

| Sentence | Check |
| -------- | ----- |
| "the docs are up to date" | derive required-vs-written, exit non-zero on the gap |
| "it's fast enough" | put the threshold in the command: `--p95-max-ms 400` |
| "the feature works" | the narrowest test that fails without it, never the whole suite |

**Empty results are broken until proven otherwise.** A search reporting nothing may be filtering
everything — pattern, `--include`, a non-ASCII path through a tool that is not multibyte-safe
(BSD `awk` and `sed` are not). Run it against a case you know matches before believing it. And
an absent name is not an absent rule: it may be inlined, renamed, or enforced elsewhere.

## `MANUAL`, and what the lint catches

Legitimate when the decision belongs to someone else — wording, a design, a legal sign-off. No
command produces that answer. Laziness when you could have written the check: "the code is
clean", "performance looks fine", "the migration is safe".

`--sign` accepts only the named owner and stores a hash of `what`; change the wording and the row
returns to `WAIT — signature is for an older wording`.

The lint catches: no rows; `MANUAL` without an owner; mostly-`MANUAL` ledgers; deliverables with
no baseline; stale signatures and waivers; rows with no `break`; with `--requirements`,
requirements no row measures. It does not catch a fake check or a break that cannot fire.

## Flags and exit codes

`--blast [SECONDS]` adds the sweep; `--no-blast` says out loud that it is not wanted.
`--timeout N` seconds per check (default 1800; a timed-out check is `FAIL`). `--only A,B` ends
`PHASE OK` / `PHASE NOT OK`, never `DONE`. `--baseline` records the tree once, skipping build
output (`obj/`, `bin/`, `target/`, `dist/`) and the usual caches; it is refused while
one exists, and `--baseline --reset` replaces it — which reads every edit so far as pre-existing. `--sign ID --who WHO [--note ...]`. `--requirements
PATH` is read by `--lint-ledger` only. `--ledger PATH` is for testing the script; the skill uses
the catalog path.

| Exit | Means |
| ---- | ----- |
| 0 | every row `PASS` (`DONE`), every chosen row `PASS` (`PHASE OK`), every break row `VERIFIED`, lint clean |
| 1 | something `FAIL` or `WAIT`; a `HOLLOW`, `STUCK`, `ALREADY RED`, `BREAK FAILED`, `BLAST`, `NOTHING VERIFIED` or `SWEEP STOPPED` result; lint found problems |
| 2 | misuse or broken ledger — no ledger, empty check, duplicate id, empty requirements file, `--blast` without `--verify`, unknown `--only`/`--verify` id, an argument to `--baseline`, a second `--baseline` without `--reset`, `--reset` without `--baseline`, deliverable without baseline, `MANUAL` row naming a deliverable, bad `--sign`, `--requirements` without `--lint-ledger`, another goalrun already running checks in this tree |

`check` and `break` run with the caller's shell and permissions. POSIX only (`sh -c`, process
groups, `flock`); no version control required. A ledger is an executable file — read every row
before running it, as you would a `Makefile`.
