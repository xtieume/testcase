# Persistent goalrun handoff

Approved scope: isolate unfinished work in the same source tree and let another agent/session/host continue it. Work identity survives the agent. No dependence on proprietary session IDs, chat memory, or installed skill paths.

Each explicitly selected run lives in `.testcases/runs/<run-id>/`, with versioned manifest, atomic checkpoint with canonical handoff field, evidence, and isolated goalrun/docs-review/testcase working artifacts. Case tables remain tracked deliverables at `docs/testcases/<run-id>/testcases.md`; runnable tests stay in the project's framework. The original baseline and requirement/case IDs survive handoff. Decisions first received in chat must be persisted in the spec.

CLI supports init, list, inspect, resume, checkpoint, release, and explicit migration of the legacy artifact set. Resume acquires a durable writer token. Release revokes it; takeover requires the observed generation and never happens merely because time elapsed. A run flock serializes ownership validation and writes. A separate workspace flock serializes checks and temporary source mutations across runs. These protect cooperating tools, not arbitrary editor writes.

Engine commands require explicit run and current token. Legacy CLI remains usable in workspaces without named runs; once named runs exist, implicit legacy writes are refused. Schema versions and canonical workspace identity must match before writes. No automatic baseline reset, newest-run selection, or PASS reuse on changed inputs.

Persist command logs, actual exit codes, input fingerprints, row failures, and explicit phase/next action. Inspection marks evidence stale when source/spec/ledger/testcase inputs change; resume requires inspection and a fresh measurement before completion. A phase-only verify is not whole-ledger completion. Proof is bound to the ownership epoch, so a newly resumed controller must verify again even without source changes. Fully signed manual-only and explicitly test-first-waived ledgers can complete without planting defects after full coverage lint.

Write restoration journals before planting defects. Every run checks pending journals across the workspace under the workspace lock. Recovery restores only unchanged planted bytes (or recognizes already restored bytes); ambiguous or externally changed files are refused for manual reconciliation. Atomic replacement protects persisted state from torn JSON writes. SIGKILL may leave a pending journal but must not silently corrupt another run.

Portability: an agent on the same workspace uses the same run regardless of its installed skill location. Copying to another machine/worktree requires deliberate transfer of artifacts AND the exact unfinished source changes; automatic relocation is out of scope. Git clone alone omits ignored working artifacts. The script is POSIX-only.

Validation covers two runs, separate subprocess agents taking over mid-phase, revoked tokens, generation races, schema/workspace incompatibility, source drift, manual signoff isolation, global check contention, killed verify recovery, safe refusal after intervening edits, and legacy migration. Pressure-test the consuming agents' choices before and after guidance.
