# Report format and verdicts

## Severity

| Level | Meaning |
| --- | --- |
| P0 — Critical | Catastrophic impact such as destructive data loss or broad security compromise; immediate action required. |
| P1 — High | Serious functional, security, or reliability regression; fix before merge. |
| P2 — Medium | Concrete localized defect or material maintainability problem; fix or explicitly track follow-up. |
| P3 — Low | Minor actionable issue or explicit convention violation with limited impact. |

Do not elevate a SOLID smell to P1 without corresponding impact. Rare catastrophic failures
can still be P0. Keep optional stylistic preferences outside the defect count.

## Verdict rules

- `REQUEST_CHANGES`: an unresolved confirmed P0/P1, another confirmed defect that violates an
  explicit merge requirement, or a relevant required check demonstrably fails on this change.
- `COMMENT`: no established blocker, but unresolved candidates, material coverage gaps,
  missing independent verification, unavailable/pending required checks, or P2/P3 findings
  needing a disposition prevent approval.
- `APPROVE`: scope and independent review are complete, relevant required checks have current
  passing evidence (or are explicitly not applicable), and no unresolved findings remain.
  Nonblocking P2/P3 may be deferred only with an explicit user/owner disposition recorded.

These are report assessments, not GitHub review submissions or replacements for required
human approval. An untouched baseline failure is a limitation, not a new defect; it prevents
claiming passing checks but does not by itself prove the change should be rejected.

## Output template

```markdown
## Deep review

**Verdict:** APPROVE | REQUEST_CHANGES | COMMENT
**Findings:** N confirmed — P0: n · P1: n · P2: n · P3: n
**Remaining:** N open · N fixed · N deferred
**Target:** base/head SHAs or local snapshot; scope and risk
**Review:** round N/3; independent verification performed or limitation

### Findings

#### DR-001 — [P1] Concrete failure
- Location: file:line at the reviewed snapshot; responsible change and caller if different
- Trigger and impact: inputs/state → actual outcome versus required outcome
- Evidence: code path, contract, or reproduction; independent verification result
- Fix: smallest correction addressing the root cause
- Disposition: open | fixed (proof) | deferred (owner decision and follow-up)

### Verification and coverage
- Checks actually run: command, result, snapshot; relevant current CI links if used
- Areas inspected; exclusions, unavailable checks, unresolved questions

### Other observations
- Pre-existing defects, rejected candidate IDs/reasons for re-review, optional improvements
```

Omit empty sections. Say explicitly when there are zero confirmed findings. Do not list
rejected hypotheses as defects. Preserve IDs across rounds and report final remaining counts;
fixed findings remain in the history but do not block the final verdict. Cite exact locations;
for remote code links use the full reviewed SHA, not a moving branch name.
