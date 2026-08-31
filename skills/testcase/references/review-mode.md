# Review Mode — Auditing Existing Test Cases

Read this when the user hands you an existing test case list to review, improve, or check.

## The trap

Reading the test cases finds formatting problems; it cannot find what is missing — the gap is invisible from inside the list. Build the coverage map from the **requirement**, then map the cases onto it.

## Steps

**1. Get the requirement.**

Not provided → ask, saying why: without it you can only check wording, not coverage. Never assume the existing cases describe the requirement — that assumption is what lets a missing dimension survive review.

**2. Build the coverage map from the requirement.**

Follow `coverage-map.md` (+ `i18n-jp.md` if applicable) as in generation mode, before reading the existing cases closely.

**3. Map each existing case onto the map.**

Classify every case:

| Verdict | Meaning |
| ------- | ------- |
| `OK` | Verifies a distinct real risk, steps are concrete, expected result is testable |
| `weak` | Vague steps ("enter a valid value"), missing expected result, untestable expected result, no traceability |
| `duplicate` | Verifies the same behavior as another case |
| `wrong` | Expected result contradicts the requirement |

**4. Output findings first, then the gaps.**

Findings table:

| ID | Verdict | Problem | Suggested fix |
| -- | ------- | ------- | ------------- |

Then the missing cases, in the standard generation format from `SKILL.md`, numbered from the highest existing ID — never renumber the user's cases. The findings file is a working artifact: write it to `.testcases/testcase/` (excluded via `.git/info/exclude`), never into the docs tree, never committed.

**5. Leave good cases alone.**

Do not rewrite a case that is fine. A review touching everything is indistinguishable from a rewrite — the user loses sight of what actually needed attention.

**6. Lint the merged list.**

Run `scripts/summarize.py` on the combined file. Add `--requirements` with the step-2 IDs — the highest-value check in review mode: a list someone else wrote is exactly where a whole requirement has no case at all.

## Reporting

Verdict per dimension, not just per case:

```text
Boundary:   partially covered — max tested, min and max+1 missing
Permission: not covered — no role-based cases at all
State:      N/A — feature is stateless
```

That table is the deliverable; per-case verdicts are supporting detail.
