# Persistent Goalrun Handoff Implementation Plan

> **For agentic workers:** Execute task-by-task with test-driven development and independent review. Storage implementation and skill pressure tests are delegated; CLI integration and documentation are implemented in the main session.

**Goal:** Separate concurrent goals and preserve unfinished work across agents.

**Architecture:** A versioned run store owns durable identity/checkpoints. A CLI integration module binds the existing measurement engine to explicit run paths and records evidence. Run locks and the existing workspace lock protect cooperating writers; guarded restoration journals recover interrupted verification.

**Tech Stack:** Python standard library, POSIX flock, Markdown skills.

**Spec:** `docs/superpowers/specs/2026-10-03-goalrun-handoff-design.md`

## Global Constraints

- No external runtime dependency or required Git repository.
- Keep the original baseline, human signoffs, REQ and TC IDs across handoff.
- No implicit newest-run selection or inherited proof on changed source.
- No external installation changes; ship repository/plugin source through a PR.

### Task 1: Durable run store

Files: `run_store.py`, `test_run_store.py` under `.agents/skills/goalrun/scripts/`.

- [x] Write failing stdlib tests for exclusive create, two-goal separation, A/release/B continuation, revoked tokens, generation collision, version/workspace mismatch and run-lock contention.
- [x] Run `python3 -m unittest discover -s .agents/skills/goalrun/scripts -p test_run_store.py`; confirm missing implementation failures.
- [x] Implement Store create/inspect/list/resume/require/checkpoint/release and nonblocking lock, atomic JSON writes and path validation.
- [x] Run the same tests green.

### Task 2: Run-aware measurement and recovery

Files: `run_cli.py`, `test_run_cli.py`, existing `goalrun.py`.

- [x] Write CLI subprocess tests for named run baseline/ledger/signoff isolation, persistent checkpoint and evidence, no implicit fallback, migration, schema rejection, and pending-undo recovery before ordinary checks.
- [x] Run `python3 -m unittest discover -s .agents/skills/goalrun/scripts -p test_run_cli.py`; verify unsupported commands/flags fail.
- [x] Route lifecycle commands into Store; bind all engine paths together and keep workspace locking around recovery, checks and mutation.
- [x] Record logs and input fingerprints; preserve retry counts and distinguish measurement, subset proof and full proof.
- [x] Journal original/expected planted bytes before mutation; recover under compare-and-restore guards.
- [x] Run new integration tests and `python3 .agents/skills/goalrun/scripts/test_goalrun.py`.

### Task 3: Cross-skill protocol

Files: goalrun, docs-review and testcase `SKILL.md`, goalrun run-context reference, README files, pressure-test record.

- [x] Record baseline pressure scenario with fresh agent before editing guidance.
- [x] Replace fixed working paths with explicit run context; document standalone skill context, handoff steps, tokens, source drift and manual transfer limits.
- [x] Run the same scenario with a fresh consuming agent; address omissions.
- [x] Run all repository Python and Node checks; check plugin manifest synchronization.

### Task 4: Review and PR

- [x] Independently review correctness, scope, recovery races and skill guidance; fix findings with regression tests.
- [x] Commit and push feature branch; create PR against main with final behavior and validation. PR: https://github.com/xtieume/testcase/pull/28

Validation: 43 run-store/CLI tests, 110 legacy engine checks, three packaging tests, Node document checks and plugin metadata synchronization. Independent code review and before/after consuming-agent pressure tests completed; findings were fixed with regression tests.
