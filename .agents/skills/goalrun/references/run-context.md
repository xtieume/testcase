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
IDs. The baseline and migration payload are staged before a run becomes visible; a failed
preparation leaves the ID available for retry. Copy the top-level `token` from `resume` JSON into `TOKEN`; it authorizes this owner.
`inspect` and `list` are read-only and never return an ownership token. Read the goal, spec,
checkpoint, handoff, generation and evidence before continuing. Resume never resets the
baseline, requirements, permanent IDs, failure counts or prior decisions.

Use the exact absolute paths in the selected run's JSON `paths`:

| Key | Use |
| --- | --- |
| `run_dir` | `.testcases/runs/<id>/`: manifest, checkpoint and evidence |
| `goalrun_dir` | ledger.tsv, reqs.txt, baseline.json, signoff.tsv, verify-waivers.json and guarded undo/ |
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
fingerprint and ownership epoch. `inspect` exposes `last_evidence`/`evidence_stale` for the latest operation and
`last_proof`/`proof_stale` for the latest whole-ledger proof. Successful measurements and lint
preserve a current proof; a later failed check invalidates it until whole verification passes again. A new
resumed controller must rerun the whole ledger before claiming completion, even with unchanged
source; its new ownership epoch makes prior evidence stale. Changed source, tests, runtime, tool
version, spec or authoritative run inputs (requirements, ledger, baseline, signatures, waiver bindings) also
make old evidence stale; a previous proof is not current proof. Workspace symlinks include
both link identity and resolved contents; directory links are followed with cycle detection.
Ordinary workspace files participate even when Git ignores them, including `.env` and
pre-existing schema deliverables; empty directories participate in proof freshness too.
Init records the same file selection in the original baseline. Known dependency, cache and
private-run directories are excluded. In Git workspaces, ignored directories named `bin`,
`obj`, `target`, `dist` or `build` also exclude generated output; tracked files override output
and cache exclusions. Without Git, those names alone never hide source. Keep generated
outputs in ignored build directories or recognized cache paths.
File and directory permission modes participate, so removing executable access stales proof.
Runtime inputs include a digest of environment values (excluding terminal/shell bookkeeping),
resolved executables in ledger checks, and installed Python/local dependency file identities.
Changing feature flags, Python paths, runner binaries or installed package files requires new proof.
Runtime/tool metadata, workspace paths and run inputs have separate fingerprint namespaces,
so source names cannot overwrite metadata. Git worktree contents include nested submodules;
repository/submodule HEAD and semantic index changes also stale proof. Staged object IDs,
modes, conflict stages and persistent index flags participate; Git status and index stat-cache
refreshes preserve proof. Directory deliverables compare the same authoritative file selection
recorded in the baseline, so unchanged ignored ordinary files cannot count as newly shipped.
Explicit deliverables in excluded output/cache/private paths are rejected; choose an ordinary
authoritative path, or track the output/cache target before initializing its run baseline.
Initial omitted file/subtree boundaries are also saved in the baseline. Later staging or ignore
rule edits cannot turn those paths into newly shipped work; files recorded in the original baseline
retain their authoritative status. A saved excluded subtree remains excluded for new files below it,
so put new source outside that original boundary. Older baselines without exclusion provenance
conservatively reject unrecorded generated/cache-name targets.
Do not reset an existing run baseline to work around an excluded deliverable.
Environment values themselves are never saved by the fingerprint. Evidence JSON and session
logs are created with private `0600` file permissions, independent of the caller’s umask.
Derived session logs, CSV exports and working review reports do not invalidate measurement
evidence; requirements and tracked test case tables remain authoritative inputs. Standard coverage
outputs (`.coverage`, `.coverage.*`, `coverage.xml`, `junit.xml`) are excluded too. Other generated
outputs should live in Git-ignored build paths or recognized cache directories. FIFOs and devices are
recorded by file type and permissions without opening them.
The fingerprint is a freshness check, not proof that the requirements or tests were correctly
derived. Only a successful **bare, whole-ledger `--verify`** with unchanged inputs records
`last_proof.whole_ledger_verified: true`; completion also requires `proof_stale: false`. Full proof first gates requirement coverage with lint. A ledger
consisting only of signed MANUAL rows (including multiple decisions) or explicit test-first waivers
can pass without mutation. Manual signatures must match the current wording and owner.
Test-first waivers are bound to their current row in verify-waivers.json before the session
fingerprint is taken. After row edits, witness the revised test red and replace the waiver's
reason with a never-used `test-first ... seen red ...` observation describing the new red.
Unchanged lines, measurement, removed rows and handoffs cannot refresh a stale waiver;
the manual-row ratio gate still applies to mixed ledgers;
unwaived checks without breaks fail lint. `--only` and `--verify <ids>` give phase verdicts and
cannot justify completion. A selected check without a break is recorded as `SKIPPED` and
fails subset verification; its preliminary measurement is not proof. After a subset repair,
rerun the whole ledger before claiming done.

The CLI holds a run lock across ownership checks and writes, and a global workspace lock
across source-sensitive operations, including checking whether legacy mode is still eligible. Before lifecycle writes or named engine operations it
recovers **all runs'** pending verify journals under that global lock. Restoration compares
current bytes and saved permission modes to the original or planted fingerprint; conflicting
external edits (including chmod while a defect is planted) refuse
recovery and retain the journal for reconciliation. Planting and restoration write and sync a
temporary file, then atomically replace the target; recovery clears the journal only after restoration. Symlinked or hardlinked
source targets are refused before planting a defect. After a parent crash, an orphan check
process retains the workspace lock until it stops. Normal completion explicitly unlocks the
shared descriptor, so surviving background processes do not keep the lock. Deletion breaks
also compare the current source with the journal before unlinking. `inspect` can still read state.
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

`migrate` copies the existing legacy baseline, ledger, reqs, signatures, waiver bindings, docs-review/testcase
artifacts and root testcases.md into selected run paths, leaves originals untouched and never
retakes the baseline. An existing destination testcase table is refused; reconcile its permanent
IDs before retrying migration. A pending publication journal recovers a tracked table left by
a killed migration; intervening edits are preserved and require reconciliation. Reconcile
pending legacy undo before migration. Once a named run exists,
select `--run` explicitly for engine commands.
