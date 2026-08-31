# Review Mode — Auditing Existing Test Cases

Read this when the user hands you an existing test case list and asks to review, improve,
or check it, instead of generating from scratch.

## The trap

Reviewing test cases by reading the test cases finds formatting problems. It cannot find
what is missing, because the gap is invisible from inside the list. Build the coverage map
from the **requirement**, then map the existing cases onto it.

## Steps

**1. Get the requirement.**

If the user did not provide it, ask. Say plainly why: without the requirement you can only
check wording, not coverage. Do not proceed on the assumption that the existing cases
describe the requirement — that assumption is what lets a whole missing dimension survive
the review.

**2. Build the coverage map from the requirement.**

Follow `coverage-map.md` (and `i18n-jp.md` if applicable) exactly as in generation mode.
Do this before reading the existing cases closely.

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

Then the missing cases, as new proposed cases in the standard generation format from
`SKILL.md`. The findings file is a working artifact — write it to `.testcases/testcase/` excluded via
`.git/info/exclude`, never into the project's docs tree and never committed. Number them continuing from the highest existing ID — do not renumber the
user's cases.

**5. Leave good cases alone.**

Do not rewrite a case that is already fine. A review that touches everything is
indistinguishable from a rewrite, and the user loses the ability to see what actually
needed attention.

**6. Lint the merged list.**

Run `scripts/summarize.py` on the combined file to catch duplicate IDs, invalid
priorities, and vague steps mechanically. Add `--requirements` with the requirement IDs from
step 2 — in review mode this is the highest-value check, because a list someone else wrote is
exactly where a whole requirement turns out to have no case at all.

## Reporting

State the coverage verdict per dimension, not just per case:

```text
Boundary:   partially covered — max tested, min and max+1 missing
Permission: not covered — no role-based cases at all
State:      N/A — feature is stateless
```

That table is the deliverable. The per-case verdicts are supporting detail.
