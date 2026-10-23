# Evaluate reviewer behavior

Based on [Solving code review at Anthropic](https://claude.dev/blog/solving-code-review-at-anthropic/).

Use isolated repositories and fresh evaluator contexts. Give an evaluator the skill, realistic
request, target diff, and raw repository sources. Keep expected answers in a separate scoring
context; do not reveal the bug or desired verdict to the reviewer. No live PR mutation is needed.

Start with these cases and add confirmed real incidents and clean PRs over time:

| Case | Observable behavior to score |
| --- | --- |
| Changed helper breaks an unchanged caller | Finds the regression and cites both the responsible change and caller. |
| Tenant guard removed | Confirms the reachable isolation failure; severity follows impact. |
| Suspicious input is guarded upstream | Checks the guard and rejects the false positive. |
| Intentional API change with updated callers | Respects intent instead of demanding old behavior. |
| Clean diff with tempting SOLID refactor | Produces no invented blocker and no style or refactor findings. |
| Staged, unstaged, and untracked changes | Covers all requested local changes. |
| No diff | Requests a target instead of claiming a clean review. |
| Missing checks or verifier failure | Reports the limitation; does not issue unsupported APPROVE. |
| --fix with a confirmed regression | Repairs without re-asking authorization; verifies behavior and preserves unrelated edits. |
| Repeat review with resolved and new issues | Preserves IDs, avoids repeats, follows the new delta and affected contracts. |
| Defects remain after round three | Stops with outstanding findings instead of claiming convergence. |

Measure confirmed bugs caught / known bugs, false positives on clean changes, harmful proposed
fixes, rounds to pass, and tool/token cost when available. Compare against the previous skill on the
same cases and model configuration; do not claim improved accuracy from prompt inspection.
Record actual outcomes and limitations, not just a checklist marked passed. A small smoke run
is behavioral evidence, not a benchmark or proof of general reliability.

On real use, classify each reported finding by the author's response: fixed, called wrong,
called intentional, or judged not to matter. The last three are noise; drive them down without
losing recall.

CI enforcement, branch protection, merge queues, and rollback remain repository infrastructure,
not guarantees made by this skill; do not score the reviewer on them.
