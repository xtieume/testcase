# What was measured

Two versions of `testcase` were run against the same inputs, blind-judged.

**A logic-only spec.** Two agents wrote a first-pass table, one per version.
Defect counts came out level (7 vs 7–8). The longer version's table was the
narrower one: it missed the requirement's largest ambiguity without logging it
as a question, applied a rounding convention it never disclosed, and wrote a
permission case that could not separate a UI check from a server-side one —
the three things its extra rules were about. Both broke a rule the shorter
version already had. Those rules were removed.

**A design review, with the same screen and export.** The version carrying
`design-validation.md` picked the right baseline — the only signed, pre-build
frame, not the newest one — and declined to file anything resting on a value
the export itself hedged. The version without it read the newest frame as
canonical, quoted two estimated values as evidence, and turned a designer's
note to a colleague into a medium-severity defect. False positives: 1 vs 2,
and the baseline question answered vs declined. That reference stayed.

**A full run — logic, design and bug write-ups.** Same token cost either way
(290k vs 289k; the references load only when the task needs them). Real
defects found 7 vs 2, misses 0 vs 4, false positives 1 vs 0. A team lead
would rather receive the newer one; its single flaw was asserting a disputed
reading as a confirmed bug while its own questions file still asked about it.

The rule that came out of this: **add knowledge, not discipline.** Guidance
that tells the model to be careful changes nothing measurable. Guidance that
answers a question it cannot derive — which frame is the requirement — does.
