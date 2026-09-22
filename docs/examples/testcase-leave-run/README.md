# Worked example — the `testcase` skill on a written spec

A real run of the skill against `spec.md`, a seven-line leave-deduction requirement with no
UI and no design. The three files are what the skill produces:

| File | What it is |
| ---- | ---------- |
| `spec.md` | The requirement, 7 statements, R1–R7 |
| `testcases.md` | The table, 61 live cases + 1 retired, `summarize.py` clean |
| `questions.md` | 26 questions for the requirement owner, with their dependencies |

## What the run showed

Pass 1 produced 12 cases. `summarize.py` accepted them once two coverage gaps were closed —
and the table was still wrong: two expected values assumed weekends are not deducted, a rule
the requirement never states. Both second-pass reviewers found that independently, on a table
the lint called clean. That is the line between the two mechanisms: the script checks
structure and coverage, the second pass checks whether the number is right.

Eighteen rounds followed, two independent reviewers each. Coverage converged at round four —
from there every round opened with *no uncovered requirement, no duplicates*. What kept
appearing was undisclosed assumptions, and their source was almost always the previous round's
own fix: six consecutive rounds found the new defect inside the line the last patch had
touched. A patch is a fresh decision nobody has reviewed yet, so each one buys another round.

The loop ended where the skill says it should — when only labels and tracking notes remained.

## What it cannot fix

Twenty-six questions are still open, and two of them dissolve depending on how a third is
answered (`Q-DEPS`). No number of rounds closes those: they are the requirement owner's to
answer. A table built on an under-specified requirement converges to *every assumption named*,
not to *every answer known*. The questions file is the deliverable that gets someone unblocked;
the table is what becomes trustworthy once they reply.
