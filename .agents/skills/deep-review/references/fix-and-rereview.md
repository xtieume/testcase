# Fix mode

`--fix` or an explicit request to fix authorizes implementation of verified, in-scope defects.
Do not ask again whether to fix them. User restrictions such as "P0/P1 only" narrow this scope.

1. Finish candidate verification before edits. Repair confirmed P0–P3 defects in severity
   order. Do not automatically implement optional refactors, speculative candidates, or
   unrelated pre-existing defects. Never weaken tests or contracts to make a finding disappear.
2. Confirm the editable checkout matches the reviewed target. If a PR is remote-only, use a
   separate checkout/worktree where supported; do not overwrite dirty user work. If the target
   cannot be obtained, deliver the review with the precise blocker to fixing.
3. Make the smallest coherent repair, including other in-scope instances of the same root
   cause. If expected behavior is genuinely ambiguous, ask about that behavior; continue
   independent fixes. Do not invent product requirements to avoid a question.
4. Add or run a targeted regression check when useful for the defect. Prefer tests that fail
   on the faulty behavior and pass after repair. Run applicable required checks; record actual
   outputs. Use isolated scratch artifacts for reproductions when no committed test is needed.
5. Have a fresh-context verifier inspect the repair delta, original findings, and affected
   contracts. Revalidate findings and checks at the final snapshot. Preserve IDs and reject
   newly disproved findings with reasons. Keep rejected/deferred dispositions unless new
   evidence changes them.
   If delegation is unavailable or fails, run the inline challenge pass on the repair delta and
   mark passing fixes `fixed (inline-verified)`. Disclose missing independent verification and do
   not issue APPROVE.
6. Fixes made in a round do not increment the round count. The re-review of that repair
   delta is the next review round. Finish within three review rounds per target, including
   the initial pass and prior rounds. On round 3, do not edit; report the remaining work.
   Fixes without passing verification remain open/unverified, not fixed.

Final output uses the standard report, includes changed files and check results, and says
what remains. `--fix` does not promise APPROVE; missing checks or unresolved findings retain
COMMENT/REQUEST_CHANGES. Do not commit, push, or submit a remote review without authorization.
