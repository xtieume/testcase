# Persistent run context

Read before creating outputs, resuming, or dispatching a child skill. One run is one piece of
work. It survives agent changes, compaction and host restarts. Select its ID explicitly. Never
use the newest directory or report as the active run.

## Start and select

From the workspace root, `GOALRUN` is the installed `scripts/goalrun.py`. IDs are 1–80 letters,
digits, underscores or hyphens, and start with a letter or digit.

```bash
RUN=export-v1
python3 "$GOALRUN" init "$RUN" --goal "Ship CSV export" --spec spec.md
python3 "$GOALRUN" resume "$RUN" --owner controller-a
python3 "$GOALRUN" inspect "$RUN"
python3 "$GOALRUN" list
```

- `init` **before any edits**: unowned; refuse duplicate IDs; stage baseline and migration
  payload before visible. Failed preparation leaves the ID retryable.
- Copy `resume`'s top-level `token` to `TOKEN` (this owner). `inspect` and `list` are read-only;
  no token.
- Read goal, spec, checkpoint, handoff, generation, evidence. Resume never resets baseline,
  requirements, permanent IDs, failure counts, or decisions.

Use absolute `paths` from the run JSON:

| Key | Use |
| --- | --- |
| `run_dir` | `.testcases/runs/<id>/`: manifest, checkpoint, evidence |
| `goalrun_dir` | ledger.tsv, reqs.txt, baseline.json, signoff.tsv, verify-waivers.json, guarded undo/ |
| `docs_review_dir` | this run's reports and review artifacts |
| `testcase_dir` | this run's CSV, previous table, coverage map, review artifacts |
| `testcases` | `.testcases/runs/<id>/testcase/testcases.md` |
| `checkpoint` / `handoff` | same checkpoint.json; handoff field is canonical |

- `GOAL_DIR`, `DOCS_REVIEW_DIR`, `TESTCASE_DIR`, `TESTCASES`: values, not flags. Report scripts
  stay in skill `scripts/`.
- Exclude `.testcases/`. Runnable tests belong in the repo, not ignored artifacts.
- `paths.testcases` stays private unless the user explicitly asks for a path. Editing it
  invalidates proof (run input).
- Explicit path wins: record in spec and handoff, pass to every child, do not mix with the
  default.

## Ownership and handoff

```bash
python3 "$GOALRUN" checkpoint "$RUN" --token "$TOKEN" --phase build \
  --next "Fix rounding" --failure inline-ROUND --note "Delegated inline test failed; log in handoff"
python3 "$GOALRUN" release "$RUN" --token "$TOKEN" --note "Continue at TC-EXP-004"
python3 "$GOALRUN" resume "$RUN" --owner controller-b --expected-generation 7
```

- Checkpoint: phase, next action, decisions already in the spec, paths, evidence next.
- Engine persists row and proof failures. `--failure` once, only unrecorded inline or delegated.
  Counts survive agent changes.
- `release`: revoke token, clear ownership, increment generation, atomic handoff+checkpoint. No
  `handoff.md`.
- Old token cannot checkpoint, release, sign, or run the engine. **No TTL**.
- Crash: inspect; confirm agent and check processes stopped; deliberate takeover (replace `7`).
  Stale generations refuse. Old, quiet, or another host never grants permission.
- Controller holds the token. Subagent: run ID, canonical workspace, schema version, spec, exact
  input/output paths, `delegated writer: tests/test_export.py` or `read-only reviewer`.
- Assigned files only; return evidence; never resume, release, or take over. Controller
  checkpoints merged results. Omit controller reasoning and earlier findings.

## Execute and trust current evidence

```bash
python3 "$GOALRUN" --run "$RUN" --token "$TOKEN" --lint-ledger
python3 "$GOALRUN" --run "$RUN" --token "$TOKEN" --only EXPORT,ROUND
python3 "$GOALRUN" --run "$RUN" --token "$TOKEN" --verify
```

- Named commands bind the run. No `--ledger` or `--requirements` (lint uses reqs.txt). Refuse
  `--baseline` and `--reset`: `init` owns the one baseline.
- `--sign` needs `--run` and `--token`; record only the human answer received.
- Evidence: commands, outputs, exits, run log, fingerprint, epoch. `inspect`:
  `last_evidence`/`evidence_stale`, `last_proof`/`proof_stale`, and `proof_stale_because`
  (`runtime`, `source`, `run-inputs`, `spec`, `ownership`, `invalidated`, `missing`, `format`).
- JSON and session logs `0600`, independent of umask. Fingerprint stores no environment values.

### Durability per check

- Checkpoint after each observed check and finalized row, before the next.
- `last_evidence`: `state: "unfinished"` (null exit) or `state: "completed"`.
- Witnessed failure invalidates proof, once per row, even after SIGKILL or takeover.
- Publish `HOLLOW`/`STUCK` before the blast sweep. Mid-sweep kill: failure stays counted; prior
  proof stays invalid.
- Planted failure waits for the sweep (not a regression). Phase `measurement`, `mutation`,
  `blast`: not a production regression.
- Keep the raw exit. Silent or no match → `passed: false` at exit 0.
- Replace the private Python bytecode cache on plant or restore so other-version same-second
  bytecode cannot shadow source.

### What stales a proof

- Measure or lint success keeps proof. A later failure invalidates it until whole verification
  passes.
- New ownership epoch: whole-ledger rerun before completion even if source is unchanged.
  Previous proof is not current proof.
- **Source files.** Ordinary ignored files (`.env`, pre-existing schema deliverables), empty
  directories; init records that set. Symlink identity and target; follow directory links;
  detect cycles. Spec directory read through, linked or not: add, edit, or remove a requirement
  file and proof stales. Modes count; removing executable access stales proof. Tests and spec
  stale proof.
- **Runtime/env.** Env digest except terminal, SSH/tmux session and per-step CI bookkeeping
  (`SESSION_VARIABLES` in `run_cli.py`); run `inspect` in the environment the checks ran in;
  resolved check executables;
  installed Python and local dependency files. New proof: feature flags, Python paths, runner
  binaries, installed packages, tool version. Separate namespaces: runtime/tool metadata,
  workspace paths, run inputs.
- **Git state.** Nested submodules; repository/submodule HEAD; symbolic branch; semantic index
  changes. Resolved HEAD alone cannot tell a switch. Staged object IDs, modes, conflict stages,
  persistent index flags. Git status and index stat-cache refresh preserve proof.
- **Run inputs.** Requirements, ledger, baseline, signatures, waiver bindings, test case table.
  Derived session logs, CSV exports, working review reports do not stale measurement. FIFOs and
  devices: type and permissions only; do not open them.

### Exclusions and deliverables

- Excluded: known dependency, cache, private-run dirs; `.coverage`, `.coverage.*`,
  `coverage.xml`, `junit.xml`.
- Git-ignored `bin`, `obj`, `target`, `dist`, `build` exclude generated output; tracked files
  override. Without Git those names never hide source. Keep output in a Git-ignored build path
  or a recognized cache.
- Directory deliverable: baseline authoritative files. An unchanged ignored ordinary file is not
  shipped.
- No deliverable under an excluded output, cache, or private path. Ordinary authoritative path,
  or track it before `init`. Do not reset the baseline.
- Init saves omitted file/subtree boundaries. Later staging or ignore edits are not new work.
  Recorded files stay authoritative. Excluded subtree stays excluded; new source outside it.
- Init saves ignore rules then in effect. A later file under an ignored output dir, or a
  dependency/cache name, stays excluded if force-added or the rule goes. Older baselines without
  that provenance reject unrecorded generated/cache-name targets.

### What counts as completion

- Fingerprint is freshness, not derivation. Bare whole-ledger `--verify` on unchanged inputs
  sets `last_proof.whole_ledger_verified: true` and `proof_stale: false`. Lint gates coverage
  first.
- Signed `MANUAL` only (one or many) or test-first waivers may pass with no mutation. Signature
  matches current wording and owner.
- Bind the current row in verify-waivers.json before the session fingerprint. After an edit:
  witness the new red; unused `test-first ... seen red ...`. Unchanged lines, measurement,
  removed rows, handoffs do not refresh it.
- Mixed ledgers: manual-row ratio gate. No break and no waiver fails lint.
- `--only` and `--verify <ids>` are not completion. No break: `SKIPPED`, subset fails, not
  proof. After a subset repair, rerun the whole ledger before claiming done.

### Locks and recovery

- Run lock: ownership checks and writes. Workspace lock: source-sensitive ops, including
  legacy-mode eligibility.
- Before a lifecycle write or named engine operation, recover **all runs'** pending verify
  journals under the workspace lock. Unreadable manifest or checkpoint: `error`, block until
  reconciled (journals unchecked).
- Match bytes and saved permission modes to the original or planted fingerprint. Conflict,
  including chmod while planted: refuse recovery, keep the journal.
- Sync a temp file, then atomically replace; clear the journal only after restore. Refuse
  symlink or hardlink sources. Deletion compares to the journal before unlink.
- Orphan check after a parent crash holds the workspace lock until it stops. Completion unlocks
  the shared descriptor so survivors do not. `inspect` still reads. Cooperating edits follow the
  delegation contract. Locks are not OS access control. External editors and builds do not take
  them.

## Portability and legacy state

- Schema `1`. Unknown versions refuse until explicit migration. Workspace is the canonical real
  path, not the skill path or host name. Another host may resume the **same workspace**.
- Clone or moved worktree: transfer matching source and ignored state, then explicit workspace
  migration. No automatic relocation. Never copy only a token. Never assume a clone contains
  `.testcases/`.
- Legacy commands only while no named run exists:

```bash
python3 "$GOALRUN" migrate export-v1 --goal "Ship CSV export" --spec spec.md
python3 "$GOALRUN" resume export-v1 --owner controller-a
```

- `migrate` copies baseline, ledger, reqs, signatures, waiver bindings, docs-review/testcase
  artifacts, root testcases.md; originals stay; baseline not retaken. Reconcile pending legacy
  undo first. Then `--run`.
