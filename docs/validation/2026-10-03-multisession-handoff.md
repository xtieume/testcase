# Executed multi-session handoff simulation

Date: 2026-10-03. This is an executed fixture test of isolation and continuation, not a claim
that the full independent docs-review/testcase review process was certified.

## Setup and execution

A separate workspace contained three Python modules initially raising NotImplementedError,
three specs, three placeholder documents and an existing stdlib unittest framework. All three
runs were initialized before any implementation edit. Three fresh-context agent controllers
then used actual CLI list/inspect to identify their work by goal/spec; their prompts did not
provide run IDs or tokens. They independently generated requirements, cited docs-review
reports, ten-column testcase tables, executable tests and ledgers in the same source tree.

Each spec deliberately used the same local IDs REQ-001 and REQ-002:

| Run | Spec | Requirement behavior | Test cases |
| --- | --- | --- | --- |
| run-amber | pricing.md | HALF_UP ties 2.665/2.675; reject negative values, accept zero | 8 |
| run-blue | login.md | Lock at >=3 failures; reject negative failures, accept zero | 6 |
| run-coral | export.md | Preserve ordinary fields; quote commas/quotes/newlines and double quotes | 7 |

The initial agent turns were interrupted by service usage limits. Continuation reused their
existing on-disk state; no run was reinitialized and no baseline was reset.

Session A deliberately left pricing's negative-value rejection failing. Its actual phase
measurement exited 1, saved NEGATIVE:1, checkpointed build-negative and released ownership.
Session D was then spawned with fresh context and only the goal/spec identity. It located the
run via list/inspect, read the saved next action, resumed under a new owner, and fixed only the
missing behavior. It preserved spec, requirements, testcase table, ledger, report, tests and
baseline byte-for-byte. Its attempt to checkpoint with A's former token exited 2. NEGATIVE:1
remained 1 after successful continuation.

## Stable-workspace observer checks

After every writing session had released ownership, an observer independently resumed and
verified each run sequentially. Each new owner first saw inherited evidence as stale. The
observer compared artifact hashes before/after and checked each baseline still contained the
original three unimplemented modules; it did not merely trust agent summaries.

| Run | Whole verify exit | Testcase lint exit | Report lint exit | whole_ledger_verified | evidence_stale |
| --- | --- | --- | --- | --- | --- |
| run-amber | 0 | 0 | 0 | true | false |
| run-blue | 0 | 0 | 0 | true | false |
| run-coral | 0 | 0 | 0 | true | false |

All original baselines have SHA256
`86a1a1ab38315304dc829bd33c0ffeb66979c7f5099b01a9e3dfd5539e36cc25` because they snapshot the same
initial source. They are separate files under separate run paths. Each report retains its own
spec-specific findings and each testcase table retains its own cases despite overlapping IDs.
There is no root testcases.md or shared legacy goalrun/docs-review/testcase artifact directory.

The docs fixture intentionally contains only 'Implementation pending' links. Each generated
audit therefore records two Missing verdicts. Report lint validates that these are visible,
sourced findings; it does not turn them into Covered or certify independent review.

## Bugs exposed and corrected

1. Derived session logs/CSV exports originally participated in the input fingerprint, so
   writing a completion log made a valid proof falsely stale. Fingerprints now include actual
   source/tests/tracked testcase tables, local spec, runtime/tool and authoritative run
   requirements/ledger/baseline/signoff, while excluding derived run working outputs. A new
   regression failed before the fix and passes after it; changing requirements still stales
   proof.
2. docs-review's linter silently skipped imported REQ-001 IDs, reporting zero verdict rows.
   It now applies the same validation to these IDs without renumbering them. Its selfcheck
   failed before the fix and passes after it; all three real reports now lint with Missing=2.

Changing another goal's source during a proof can legitimately stale an earlier proof because
source is shared. The observer waited for all writers to stop before final verification. This
simulation does not establish that arbitrary external editors participate in tool locks, nor
that moving ignored state to another machine automatically works.

## Retained evidence and regression checks

Fixture workspace retained on the executing machine:
`/private/var/folders/k5/5gm0_y697wb7z14mms4d4hm00000gn/T/testcase-multisession-dq1zm1nr`.

- `.testcases/simulation-observer/results.json`: actual exits, proof flags and preserved hashes.
- `.testcases/simulation-observer/run-*-verify.log`: final engine output for each run.
- `.testcases/simulation-observer/run-*-final.json`: redacted final inspections.
- `.testcases/runs/run-amber/testcase/session-d-summary.json`: inherited phase, failure count,
  baseline hashes, retained artifact hashes and old-token exit.
- Each run's testcase directory: actual red/green tests, summarize, lint and session logs.
- `docs/testcases/<run-id>/testcases.md` and `tests/test_*.py`: generated deliverables.

Private token files remain in the fixture with mode 0600 and are not copied into this report.

Repository validation after the fixes:

```bash
python3 -m unittest discover -s .agents/skills/goalrun/scripts -p 'test_run*.py'
python3 .agents/skills/goalrun/scripts/test_goalrun.py
python3 .agents/skills/docs-review/scripts/check_report.py --selfcheck
python3 -m unittest discover -s tests
python3 scripts/sync_plugins.py --check
node .agents/skills/playwright-cdp/scripts/test-doc.mjs
```

The 44 lifecycle/storage tests, 110 legacy goalrun checks, docs-review selfcheck, packaging
checks and Node checks pass. The simulation fixes and retained evidence received an independent
read-only review with no important findings.
