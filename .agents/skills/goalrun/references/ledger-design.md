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
| `check` | A shell command, or `MANUAL:<owner>`. Exit 0 means the condition holds. Never empty — the script refuses the ledger. |
| `deliverable` | Optional path this row must have produced. `—`, `-` or empty means none. |
| `break` | Optional command that plants the exact defect `check` exists to catch. Read by `--verify`. |

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
EXPORT	CSV export writes one row per order	python3 -m unittest -q tests.test_export	src/export.py	printf 'def export(orders):\n    return []\n' > src/export.py
DOCS	the --export flag is documented	grep -q -- '--export' docs/cli.md	docs/cli.md	grep -v -- '--export' docs/cli.md > t && mv t docs/cli.md
LINT	no debug prints left in src	! grep -rn 'print(' src/	—	printf 'print(1)\n' >> src/export.py
NOTE	the release note names the export	grep -qi 'csv export' CHANGELOG.md	CHANGELOG.md	—
UX	the CSV opens cleanly in Excel	MANUAL:tuananh	—	—
```

Run, in this order:

```bash
python3 "$GOALRUN" --baseline                 # before anything else; rows with deliverables refuse to run without it
python3 "$GOALRUN" --lint-ledger              # shape of the ledger; exit 0 = "ledger measures something"
python3 "$GOALRUN"                            # pre-flight: which rows are red before work starts
python3 "$GOALRUN" --only EXPORT,LINT         # one phase; PHASE OK / PHASE NOT OK
python3 "$GOALRUN" --verify                   # after committing: VERIFIED / HOLLOW / BREAK FAILED per break row
python3 "$GOALRUN" --sign UX --who tuananh --note "opened in Excel 16, columns intact"
python3 "$GOALRUN"                            # DONE — all 5 checks pass
```

`--verify` needs a clean tree: it restores with `git checkout -- . && git clean -fdq`, so
uncommitted work would be lost and the script refuses instead. `--verify EXPORT,LINT` limits
it to named rows; rows with no `break`, and `MANUAL` rows, are skipped. If it refuses right
after a check ran, the check probably wrote something the repo does not ignore (`__pycache__/`,
coverage output) — gitignore it; that is a repo bug the run just found.

## Turning a vague sentence into a check

The row is written when the command would fail today if the work were not done.

**"the docs are up to date"** — a passing doc build proves the docs compile, not that they say
anything. Derive required-vs-written and exit non-zero on the gap:
`python3 tools/doc_gap.py spec.md docs/`.

**"it's fast enough"** — a benchmark that prints a number decides nothing; a human still has
to read it. Put the threshold in the command: `python3 tools/bench.py --p95-max-ms 400`.

**"the feature works"** — the narrowest command that fails if it does not. Not the whole
suite: a full-suite row passes on the day the feature is missing entirely.

**Empty results are broken until proven otherwise.** A `grep`/`find` that reports nothing may
be filtering everything (pattern, `--include`, a proxy rewriting output, non-ASCII paths —
use `git -c core.quotePath=false`). Before a check may say "not found", run it against a case
you know matches. And a name being absent is not a gap: the rule may live under another name,
inlined, or as a constraint elsewhere — read the code path.

## When `MANUAL` is legitimate and when it is laziness

Legitimate when the decision belongs to someone else — a business owner's call on wording, a
designer approving a screen, legal signing off on a notice. No command produces that answer.

Laziness when you could have written the check and did not. "the code is clean", "performance
looks fine", "the migration is safe" are commands you chose not to write.

Name the owner: `MANUAL:` with nothing after it fails `--lint-ledger`, and so does a ledger
with more than one `MANUAL` row where they exceed 30% of rows — a list of promises. `--sign`
accepts only the named owner, and stores a hash of `what`: change the wording and the row is
back to `WAIT — signature is for an older wording`.

## What `--lint-ledger` catches, and what it does not

Catches: no rows; `MANUAL` without an owner; mostly-`MANUAL` ledgers; rows naming
deliverables while no baseline is recorded; signatures whose id is no longer in the ledger.

Does not catch a fake check. `true`, `echo ok`, a test file that asserts nothing — all lint
clean. Only `--verify` tells a real check from a hollow one: plant the defect, watch the check
go red, or learn that it never could.

## Flags and exit codes

`--timeout N` seconds per check (default 1800; a timed-out check is `FAIL`). `--only A,B`
runs a subset and ends `PHASE OK` / `PHASE NOT OK`, never `DONE`. `--sign ID --who WHO
[--note ...]`: ID must be a `MANUAL` row, WHO its owner.

| Exit | Means |
| ---- | ----- |
| 0 | every row `PASS` (`DONE`), every chosen row `PASS` (`PHASE OK`), every break row `VERIFIED` |
| 1 | something `FAIL` or `WAIT`; a `HOLLOW` or `BREAK FAILED` row |
| 2 | misuse or broken ledger — no ledger, empty check, duplicate id, unknown `--only`/`--verify` id, unresolvable baseline, deliverable without baseline, bad `--sign`, dirty tree for `--verify` |

`check` and `break` run with the caller's shell and permissions in the caller's cwd. A ledger
is an executable file: read every row before running it, as you would a `Makefile`. A break
that touches state outside the repo (databases, services, `$HOME`) is not undone.
