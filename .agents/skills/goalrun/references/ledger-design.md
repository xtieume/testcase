# Ledger Design — Turning a Goal into Rows a Script Can Decide

Read this while writing `.testcases/goalrun/ledger.tsv`. Every command below runs from the
repo root with `GOALRUN` set as in `SKILL.md`.

## The shape of a row

Tab-separated, UTF-8 (a BOM is tolerated), `#` lines and blank lines skipped, extra columns
ignored. Tab is the separator, so no field may contain one — a check that needs a heredoc or
an awk program goes into a wrapper script and the row calls the script.

| Column | For |
| ------ | --- |
| `id` | Short, stable, unique, uppercase. Names the row in `--only`, `--sign`, `--verify`. |
| `what` | The condition in one sentence, in the user's words. Printed in the table; hashed into a `MANUAL` signature. |
| `check` | A shell command, or `MANUAL:<owner>` — the prefix is exactly `MANUAL:`; a bare `MANUAL` is refused, and anything else (including `MANUALIZE ...`) is a shell command. Exit 0 means the condition holds. Never empty — the script refuses the ledger. |
| `deliverable` | Optional path this row must have produced. `—`, `-` or empty means none. Not allowed on a `MANUAL` row — a row belongs to a decider or a file, not both. |
| `break` | The command that plants the exact defect `check` exists to catch. Read by `--verify`. Only a `MANUAL` row may go without one; any other row lacking it fails `--lint-ledger`. |

**Verdict per row.** `MANUAL` → `WAIT` until signed. Otherwise the check runs; if it passes
and the row names a deliverable, the path must exist and have changed since the baseline —
committed, staged, unstaged or untracked; a directory counts if anything under it changed;
absolute paths and `..` never count. Else `FAIL — deliverable not shipped: <path>`. A row
cannot be green while its file is missing.

## A complete example

A CLI gains a CSV export. Five rows; one deliverable per shipped file, a break wherever the
check can be tricked, one owner-named `MANUAL` row for the judgement no command makes.

```tsv
# id	what	check	deliverable	break
EXPORT	REQ-EXP-001 CSV export writes one row per order	python3 -m unittest -q tests.test_export	src/export.py	printf 'def export(orders):\n    return []\n' > src/export.py
DOCS	the --export flag is documented	grep -q -- '--export' docs/cli.md	docs/cli.md	grep -v -- '--export' docs/cli.md > t && mv t docs/cli.md
LINT	no debug prints left in src	! grep -rn 'print(' src/	—	printf 'print(1)\n' >> src/export.py
NOTE	the release note names the export	grep -qi 'csv export' CHANGELOG.md	CHANGELOG.md	grep -vi 'csv export' CHANGELOG.md > t && mv t CHANGELOG.md
UX	REQ-UX-004 the CSV opens cleanly in Excel	MANUAL:tuananh	—	—
```

Run, in this order:

```bash
python3 "$GOALRUN" --baseline                 # before anything else; rows with deliverables refuse to run without it
python3 "$GOALRUN" --lint-ledger --requirements .testcases/goalrun/reqs.txt   # every REQ has a row, every row has a break
python3 "$GOALRUN"                            # pre-flight: which rows are red before work starts
python3 "$GOALRUN" --only EXPORT,LINT         # one phase; PHASE OK / PHASE NOT OK
python3 "$GOALRUN" --verify                   # after committing: VERIFIED / HOLLOW / STUCK / BREAK FAILED per break row, plus the blast sweep
python3 "$GOALRUN" --sign UX --who tuananh --note "opened in Excel 16, columns intact"
python3 "$GOALRUN"                            # DONE — all 5 checks pass
```

`--verify` needs a clean tree: it restores with `git checkout -- . && git clean -fdq`, so
uncommitted work would be lost and the script refuses instead. `--verify EXPORT,LINT` limits
it to named rows; rows with no `break`, and `MANUAL` rows, are skipped. If it refuses right
after a check ran, the check probably wrote something the repo does not ignore
(`__pycache__/`, coverage output) — gitignore it; that is a repo bug the run just found.

## Where the rows come from

A ledger is the last stage of a three-skill pipeline, never the first. Writing rows straight
from the diff is what makes a green run meaningless.

| Stage | Skill | What it hands over |
| ----- | ----- | ------------------ |
| What is required | `docs-review` | `REQ-<area>-<3 digits>`, atomic, one yes/no each |
| How it is proven | `testcase` | `TC-<area>-<3 digits>` traced to a `REQ-`, plus the runnable tests its step 7 writes |
| Whether it holds | `goalrun` | one row per `REQ-`, whose `check` runs those tests |

Carry the `REQ-` id into the row's `what` — that string is what `--lint-ledger
--requirements` matches on, and it keeps the trail readable months later. The match is
textual: a row saying `REQ-DOC-002 deferred` satisfies the gate while measuring nothing,
which is why the ledger is also audited by `docs-review`'s loop. A `TC-` case marked
`Automatable: N` becomes `MANUAL:<owner>`; ask the user who that owner is — the test case
table has no owner column, so an owner you did not ask for is one you invented.

Without a spec, walk `.agents/skills/docs-review/references/dimensions.md` — its implicit
requirements (existing data at ship time, behavior at every stated limit, the failure path
of every success path, reversibility) are the rows a ledger forgets.

**Two omissions the script now refuses**, because prose never stopped either:

```bash
python3 "$GOALRUN" --lint-ledger --requirements .testcases/goalrun/reqs.txt
```

* a requirement with no row — a permanent pass no `--verify` can reach
* a row with no `break` — nothing proves its check can fail

Run without `--requirements` and the coverage half is skipped; the script says so rather
than implying the ledger is complete. An empty requirements file is a misuse, not an empty
check.

Accepting one needs a reason in the ledger, as a comment line the script reads — id, a
space, a dash or em dash, a space, then the reason:

```tsv
# no-row-ok: REQ-DOC-002 — the manual ships from the docs repo, audited there
# verify-ok: SMOKE — one-line smoke row; every branch under it has its own row
```

No reason, no waiver. Silence is the failure mode, not the shortcut. A waiver naming a row
or requirement that no longer exists is reported like a stale signature: it reads as a gap
someone accepted, when it is only a line nobody deleted.

## Writing a `break` for code that does not exist yet

At plan time the tests exist (`testcase` step 7 wrote them) but the implementation does not,
so a break cannot name a symbol inside it. Guessing one is worse than useless: a
substitution like `s/ROUND_HALF_UP/ROUND_HALF_DOWN/` or `s/> 1000000/>= 1000000/` silently
does nothing against `f"{total:.2f}"` or `1_000_000`, and a break that cannot fire makes
`--verify` print `VERIFIED` for a row it never tested.

**Greenfield: break the deliverable, not the implementation.** Remove or revert the file the
row ships — always effective, no guessing, and it is exactly the defect the row exists to
catch:

```tsv
EXPORT	REQ-EXP-001 export writes one row per order	python3 -m unittest -q tests.test_export	src/export.py	rm -f src/export.py
```

**Brownfield: the narrowest edit that plants the real defect.** A token substitution is
honest once you can read the token in the file. Write it portably: `sed -i ''` is BSD and
`sed -i` is GNU, so a ledger written on one and run on the other reports `BREAK FAILED` on
every row it uses. `python3 -c`, or `sed ... > t && mv t <file>`, runs on both.

Two failure modes to avoid either way:

* **Blast radius.** Rows that deliver the same file *should* go red on each other's break —
  `rm -f src/export.py` reddening all four export rows is the greenfield pattern working,
  not a fault. The fault is collateral that crosses: a break leaving a syntax error, or a
  check so broad (the whole suite) that it reddens rows shipping something else entirely.
  Those rows read `VERIFIED` while proving nothing of their own. `--verify --blast`
  separates the two — `shared` for same-deliverable siblings, `BLAST` (exit 1) for the
  crossed ones — at the cost of one full check sweep per break row. A sibling that *hangs*
  under the break is reported separately as `stuck` — a check that times out says nothing
  either way, and it is a defect in that check. The same holds for the row being verified:
  its own check timing out under the break is `STUCK`, not `VERIFIED`, and exits 1. Timeout
  is detected structurally, never by the words in a check's output — `curl: (28) Connection
  timed out` is a failing check, not a hung one. A swept sibling is capped at whatever the
  sweep has left of its budget, so one hang cannot eat thirty minutes per break row.

  **What the sweep costs.** Measured on a 12-row ledger whose checks take 0.25s each:
  `--verify --no-blast` 4.4s, with the sweep 42.8s — ten times, because the sweep is rows ×
  rows. Rows running the *identical* command are run once per break and share the result, so
  the ledger that most needs the sweep is also the one it is cheapest on (the same 12 rows
  sharing one whole-suite command: 7.9s, not 42.8s). Distinct per-row checks pay the full
  square.

  A default sweep therefore runs against a 15-minute budget, counted in sweeping time only —
  a row's own break and check are the proof, not the sweep — and checked before every
  sibling rather than between rows. Over it, `SWEEP STOPPED` names the rows whose sweep it
  could not finish and exits 1: a proof that covered half the ledger is not a proof, and
  silence there would be the same lie as never running it. A sibling the budget left no time
  for is counted unswept, never `stuck` — the sweep starving a check is not the check
  hanging. `--blast SECONDS` sets a different budget — `--blast 0` sweeps nothing and says
  so — while bare `--blast` removes the budget and accepts the cost; `--no-blast` skips the
  sweep and says what is unproven.
* **A break weaker than its requirement.** `rm -f src/tax.py` reddens a rounding check
  without going anywhere near rounding: the row prints `VERIFIED` while the clause it exists
  for is untested. That is the shape the greenfield advice produces, and it is a plan-time
  loan, not a final state — once the code exists, re-point the break at the defect the
  requirement names (remove the `quantize`, keep the addition) and verify again.
* **A row that was red already.** Its break changes nothing about the verdict, and before
  the pre-pass existed it printed `VERIFIED` beside the real ones. `--verify` now runs every
  check once on the clean tree and reports those rows as `ALREADY RED`, keeping them out of
  the sweep — otherwise one unbuilt row makes every other row report `BLAST`.
* **A no-op break.** `git checkout -- .` restores, so an ineffective break leaves no trace
  but a `VERIFIED` line. If a break's `check` fails for a reason you did not plant — an
  import error, a missing file — the row is not verified, it is confused.

`--lint-ledger` cannot tell a real break from a no-op, the same way it cannot tell a real
check from `true`. Only `--verify` can, and only after the code exists.

## Turning a vague sentence into a check

The row is written when the command would fail today if the work were not done.

**"the docs are up to date"** — a passing doc build proves the docs compile, not that they
say anything. Derive required-vs-written and exit non-zero on the gap: `python3
tools/doc_gap.py spec.md docs/`.

**"it's fast enough"** — a benchmark that prints a number decides nothing; a human still has
to read it. Put the threshold in the command: `python3 tools/bench.py --p95-max-ms 400`.

**"the feature works"** — the narrowest command that fails if it does not. Not the whole
suite: a full-suite row passes on the day the feature is missing entirely.

**Empty results are broken until proven otherwise.** A `grep`/`find` that reports nothing
may be filtering everything (pattern, `--include`, a proxy rewriting output, non-ASCII paths
— use `git -c core.quotePath=false`). Before a check may say "not found", run it against a
case you know matches. And a name being absent is not a gap: the rule may live under another
name, inlined, or as a constraint elsewhere — read the code path.

## When `MANUAL` is legitimate and when it is laziness

Legitimate when the decision belongs to someone else — a business owner's call on wording, a
designer approving a screen, legal signing off on a notice. No command produces that answer.

Laziness when you could have written the check and did not. "the code is clean",
"performance looks fine", "the migration is safe" are commands you chose not to write.

Name the owner: `MANUAL:` with nothing after it fails `--lint-ledger`, and so does a ledger
with more than one `MANUAL` row where they exceed 30% of rows — a list of promises. `--sign`
accepts only the named owner, and stores a hash of `what`: change the wording and the row is
back to `WAIT — signature is for an older wording`.

## What `--lint-ledger` catches, and what it does not

Catches: no rows; `MANUAL` without an owner; mostly-`MANUAL` ledgers; rows naming
deliverables while no baseline is recorded; signatures and waivers whose id is no longer in
the ledger (coverage waivers only when `--requirements` says what the ids should be);
non-`MANUAL` rows with no `break`; with `--requirements`, requirements no row measures —
each waivable only by a `# verify-ok:` / `# no-row-ok:` line carrying a reason.

Does not catch a fake check, nor a break that cannot fire. `true`, `echo ok`, a test file
that asserts nothing, a substitution matching no line — all lint clean. Only `--verify`
tells a real check from a hollow one: plant the defect, watch the check go red, or learn
that it never could.

## Flags and exit codes

`--timeout N` seconds per check (default 1800; a timed-out check is `FAIL`). `--only A,B`
runs a subset and ends `PHASE OK` / `PHASE NOT OK`, never `DONE`. `--sign ID --who WHO
[--note ...]`: ID must be a `MANUAL` row, WHO its owner. `--requirements PATH` is read by
`--lint-ledger` only. The blast sweep is on for a whole-ledger `--verify`, off for a subset;
`--blast [SECONDS]` / `--no-blast` force it either way, and it only tells you much once
checks are narrow — while every row still runs the whole suite, everything reddens
everything. `--ledger PATH` points at a ledger elsewhere, which is for testing the script —
the skill itself always uses the catalog path. A `--verify` in which no row ran a break
prints `NOTHING VERIFIED` and exits 1 — a run that proved nothing is not a pass.

| Exit | Means |
| ---- | ----- |
| 0 | every row `PASS` (`DONE`), every chosen row `PASS` (`PHASE OK`), every break row `VERIFIED`, `--lint-ledger` finds no problems |
| 1 | something `FAIL` or `WAIT`; a `HOLLOW`, `STUCK`, `ALREADY RED`, `UNRESTORABLE`, `BREAK FAILED`, `BLAST`, `NOTHING VERIFIED` or `SWEEP STOPPED` result; `--lint-ledger` found problems |
| 2 | misuse or broken ledger — no ledger, empty check, duplicate id, an empty requirements file, `--blast`/`--no-blast` without `--verify`, unknown or empty `--only`/`--verify` id, unresolvable baseline, deliverable without baseline, `MANUAL` row that names a deliverable, bare `MANUAL` check, bad `--sign`, dirty tree for `--verify`, `--requirements` without `--lint-ledger` or naming a file that does not exist, another goalrun already running checks in this tree |

`check` and `break` run with the caller's shell and permissions in the caller's cwd. POSIX
only: process groups (`os.killpg`), `sh -c` and git — not for Windows. A ledger is an
executable file: read every row before running it, as you would a `Makefile`. A break may only touch files git can restore: the restore is `git checkout`/`git clean`, so a
break naming a gitignored path is refused (`UNRESTORABLE`). What a break reaches indirectly —
through a variable, a subshell, a symlink — is covered instead by a snapshot of the ledger
directory and of every ignored deliverable, taken before each break and compared after. One
consequence: a check that *regenerates* its own ignored deliverable during `--verify` reads as
a break that changed it, so let the check assert the artifact rather than rebuild it. A
deliverable git does not track cannot be seen to change either, so it ships by mtime against
the moment `--baseline` ran — a weaker standard the lint names on every run, and one a tracked
file never falls to, ignore pattern or not. A deliverable that is a symlink has its target
snapshotted too, so a break writing *through* the link is seen and put back — the link itself
never moves, which is what makes that write invisible otherwise. A target outside the repo is
not followed.

Two edges the snapshot does not cover, both cheap to avoid: the pre-pass that runs every check
once on the clean tree happens before any snapshot is taken, so a check writing into
`.testcases/` there sets the state everything is later compared against; and the copy is taken
per break, so a ledger of many rows with a large ignored deliverable copies it many times —
keep artifacts the run ships small, or leave them out of the deliverable column. A break that
touches state outside the repo (databases, services, `$HOME`) is not undone.
