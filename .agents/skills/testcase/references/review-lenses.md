# Review lenses — step 4

Read at step 4, by the reviewer, not at step 3 by the author.

These were derived from real second-pass findings and they work as questions a reviewer asks
of a finished table. Tried as authoring advice they changed nothing: a measured A/B on the same
spec produced the same defect count with and without them, and the arm carrying them missed
the requirement's largest ambiguity anyway. Give them to the reviewer.

Each reviewer carries the Arithmetic lens plus one other, and these on top.

**Two reviewers naming the same case with different numbers is the most valuable result of the
round, not a tie to break.** Neither is authoritative — the Arithmetic lens miscounts too.
Recompute it yourself from the requirement, by hand or by a one-line script, and record which
reading the number came from. Taking the reviewer you trust more, or the number that matches
your table, throws away the only signal that the value was never derived in the first place.

Tell each reviewer plainly: **an empty round is a valid result.** Every finding cites the requirement line it violates; a finding it cannot cite does not come back. Do not fill a round to avoid returning nothing.

A reviewer suspicion it cannot yet prove ("`10MB` — MB or MiB? no case sits on the exact boundary") is not a finding, but it is not noise either: carry it into `## Remaining Questions / Assumptions` (step 8) instead of dropping it. Only pass-1 reasoning is stripped between rounds, never a reviewer's open question.

**A cell reviewers reverse on between rounds is settled by the requirement owner, not by
another round.** Same lens, same requirement, opposite verdicts means the ambiguity is real and
the loop cannot resolve it — running round five buys a third answer, not agreement. Freeze the
cell, record both readings and who flipped which way under its question in step 8, and stop
re-litigating it. Such a cell does not block convergence; it is escalated, not open.

**When an expected value depends on an unresolved question, assert an invariant true under
every answer.** A balance that is 0 under one reading and 16 under the other is still never 20,
and 20 is what the bug produces — the case runs today, catches what it was written for, and
commits to nothing. Reach for this before `TBD`: the third branch of rule 5 is for a value with
no such invariant, not for every value touched by an open question. The invariant must hold
across **every** open question the case touches: an inequality looks like it has already
hedged, so the second question inside it goes unlooked-for.

**Do not invent a field to make a case discriminate.** When the balance moves identically
whether or not the bug exists, the tempting fix is to assert on an audit row, a timestamp, a
counter — and if the requirement never names one, the case now fails a correct implementation
for a reason unrelated to the rule under test. Nothing lints an invented schema: the row reads
well, traces to a requirement and names a wrong implementation. Assert what the requirement
defines; where that genuinely cannot separate the two behaviours, say so and ask what the
system records, rather than deciding it.

**A `TBD` expected result is never `Automatable: Y`.** There is nothing to assert yet, and a
runnable test written against it hard-codes one reading of an open question into the suite —
the guess rule 5 exists to prevent, arriving through the metadata instead of the cell.

**An open question with three readings needs two cuts, not one.** A question recorded as
"A, B or C" is usually answered with a single case separating C from the rest, because that is
the reading that feels most wrong — and A and B then pass every case in the table identically,
so an implementation drifting between them is invisible. Count the readings, and check that
some case tells each pair apart.

**A boundary has two sides, and the outside one is usually missing.** Every case placing a
holiday inside the requested range tests that it is excluded; none tests that a holiday just
outside the range changes nothing, so an implementation scanning a window wider than the
request passes them all. The same asymmetry appears wherever a rule *removes* something:
build the case that proves it does not remove more.

**Verify `Distinguishes from` by running the case's own input through the implementation it
names.** The column is a claim, not a label, and it is the only part of a case nothing else
checks — a lint sees a filled cell, a reviewer reading for coverage sees a plausible sentence.
Two failures here survived ten rounds: a tier case at a value a year below the threshold where
both operators return the same number, and a balance case where the correct result, the
double-subtraction and the gross check all reject. Pick the input that makes them diverge; if
none does, the case is decoration.

**A row a previous round flagged gets re-derived whole, not just where it was patched.** A
reviewer stops at the first cause it finds; the fix for that cause routinely introduces the
second one in the same cell. In this skill's own trial, three rounds in a row found the new
defect inside the line the previous round's fix had touched. Re-read the whole row — its
preconditions, its arithmetic, the question it cites — before calling it fixed.
