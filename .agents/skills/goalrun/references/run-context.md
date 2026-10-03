# Persistent run context

Read before creating outputs, resuming work, or dispatching a child skill. A run belongs to
one piece of work; it survives agent changes, compaction and host restarts. Select its ID
explicitly. Never choose the newest directory or report as the active run.

## Start and select

Run from the workspace root; set `GOALRUN` to the installed `scripts/goalrun.py` path.
Run IDs are 1–80 letters, digits, underscores or hyphens, starting with a letter or digit.

```bash
RUN=export-v1
python3 "$GOALRUN" init "$RUN" --goal "Ship CSV export" --spec spec.md
python3 "$GOALRUN" resume "$RUN" --owner controller-a
python3 "$GOALRUN" inspect "$RUN"
python3 "$GOALRUN" list
```

`init` takes the baseline **before any edits**, creates an unowned run, and refuses duplicate
IDs. Copy the top-level `token` from `resume` JSON into `TOKEN`; it authorizes this owner.
`inspect` and `list` are read-only and never return an ownership token. Read the goal, spec,
checkpoint, handoff, generation and evidence before continuing. Resume never resets the
baseline, requirements, permanent IDs, failure counts or prior decisions.

Use the exact absolute paths in the selected run's JSON `paths`:

| Key | Use |
| --- | --- |
| `run_dir` | `.testcases/runs/<id>/`: manifest, checkpoint and evidence |
| `goalrun_dir` | ledger.tsv, reqs.txt, baseline.json, signoff.tsv and guarded undo/ |
| `docs_review_dir` | this run's reports and review artifacts |
| `testcase_dir` | this run's CSV, previous table, coverage map and review artifacts |
| `testcases` | tracked `docs/testcases/<id>/testcases.md` deliverable |
| `checkpoint` / `handoff` | same checkpoint.json; its handoff field is canonical |

Set `GOAL_DIR`, `DOCS_REVIEW_DIR`, `TESTCASE_DIR` and `TESTCASES` from these keys when following
examples. These variables are path selections, not script flags. The report scripts remain
in their installed skills' `scripts/` directories. Keep `.testcases/` excluded locally; the
tracked test case table and runnable tests belong in the repository. Do not place test code
inside ignored run artifacts. An explicit user output path takes precedence; record that
selection in the spec and handoff and pass it to every child instead of silently mixing it
with the default.

## Ownership and handoff

Checkpoint after each meaningful step: phase, next action, decisions already recorded in the
spec, relevant paths and evidence to inspect next. Engine runs automatically persist row
and proof failures. Use `--failure` only for inline or delegated failures the engine has not
already recorded; never count the same red twice. Counts survive agent changes.

```bash
python3 "$GOALRUN" checkpoint "$RUN" --token "$TOKEN" --phase build \
  --next "Implement TC-EXP-004" --note "Tests red; decision recorded in spec.md"
python3 "$GOALRUN" checkpoint "$RUN" --token "$TOKEN" --phase build \
  --next "Fix rounding" --failure inline-ROUND --note "Delegated inline test failed; log in handoff"
python3 "$GOALRUN" release "$RUN" --token "$TOKEN" --note "Continue at TC-EXP-004"
python3 "$GOALRUN" resume "$RUN" --owner controller-b
```

`release` revokes the token, clears ownership, increments generation and atomically saves the
handoff with the checkpoint. There is no independently authoritative `handoff.md`.
An old token cannot checkpoint, release, sign or execute the engine. Ownership has **no TTL**.
If a prior owner crashed, inspect first, establish that its agent and check processes have
stopped, then deliberately take over using the observed generation:

```bash
python3 "$GOALRUN" resume "$RUN" --owner controller-b --expected-generation 7
```

Replace `7` with the current inspection value. Stale generations refuse; being old, quiet or
on another host never grants permission. A controller owns the token. Its subagents receive
run ID, canonical workspace, schema version, spec, exact input/output path selections and an
ownership role such as `delegated writer: tests/test_export.py` or `read-only reviewer`.
They write only assigned files, return evidence, and never resume, release or take over the
run. The controller checkpoints their merged results. Context fields do not include the
controller's reasoning or earlier review findings.

## Execute and trust current evidence

```bash
python3 "$GOALRUN" --run "$RUN" --token "$TOKEN" --lint-ledger
python3 "$GOALRUN" --run "$RUN" --token "$TOKEN" --only EXPORT,ROUND
python3 "$GOALRUN" --run "$RUN" --token "$TOKEN" --verify
```

Named engine commands bind all artifacts to the run. Do not pass `--ledger` or
`--requirements`; lint uses that run's reqs.txt automatically. `--baseline` and `--reset`
are refused: init owns the one baseline. Signing also requires `--run` and `--token` and
still records only the human answer actually received.

Saved evidence contains per-check commands, outputs and exit codes, a run log and an input
fingerprint and ownership epoch. `inspect` exposes `last_evidence` and `evidence_stale`. A new
resumed controller must rerun the whole ledger before claiming completion, even with unchanged
source; its new ownership epoch makes prior evidence stale. Changed source, tests, runtime, tool
version, spec or authoritative run inputs (requirements, ledger, baseline, signatures) also
make old evidence stale; a previous proof is not current proof.
Derived session logs, CSV exports and working review reports do not invalidate measurement
evidence; requirements and tracked test case tables remain authoritative inputs.
The fingerprint is a freshness check, not proof that the requirements or tests were correctly
derived. Only a successful **bare, whole-ledger `--verify`** with unchanged inputs records
`whole_ledger_verified: true`. Full proof first gates requirement coverage with lint. A ledger
consisting only of signed MANUAL rows or explicit test-first waivers can pass without mutation;
unwaived checks without breaks fail lint. `--only` and `--verify <ids>` give phase verdicts and
cannot justify completion. After a subset repair, rerun the whole ledger before claiming done.

The CLI holds a run lock across ownership checks and writes, and a global workspace lock
across source-sensitive operations. Before lifecycle writes or named engine operations it
recovers **all runs'** pending verify journals under that global lock. Restoration compares
current bytes to the original or planted fingerprint; conflicting external edits refuse
recovery and retain the journal for reconciliation. After a parent crash, an orphan check
process retains the workspace lock until it stops. `inspect` can still read state.
Direct artifact edits by cooperating agents follow the owner's delegation contract; these
locks do not enforce OS access control, and external editors/builds do not participate.

## Portability and legacy state

Manifest and checkpoint schema version is `1`; unknown versions refuse and require explicit
migration. The workspace is its canonical real path, not the installed skill path or host
name. Another host may resume in the **same workspace**. A clone or moved worktree requires a
deliberate transfer of matching source and ignored state and an explicit workspace migration;
automatic relocation is outside this workflow. Never copy only a token or assume a clone
contains `.testcases/`.

Legacy commands work only while no named run exists. To adopt unfinished legacy work:

```bash
python3 "$GOALRUN" migrate export-v1 --goal "Ship CSV export" --spec spec.md
python3 "$GOALRUN" resume export-v1 --owner controller-a
```

`migrate` copies the existing legacy baseline, ledger, reqs, signatures, docs-review/testcase
artifacts and root testcases.md into selected run paths, leaves originals untouched and never
retakes the baseline. Reconcile pending legacy undo before migration. Once a named run exists,
select `--run` explicitly for engine commands.
