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

**A full run — logic, design and bug write-ups.** Token cost level on that
spec (290k vs 289k) — five specs later put it at +15%. Real
defects found 7 vs 2, misses 0 vs 4, false positives 1 vs 0. A team lead
would rather receive the newer one; its single flaw was asserting a disputed
reading as a confirmed bug while its own questions file still asked about it.

**Rule 5's wording, three reps per arm.** Given a spec line two readings can
be taken from, and code that satisfies one of them: with no guidance, 3 of 3
filed a confirmed bug against a reading the text does not compel. Compressed
to a two-line decision, 2 of 3. At its current length, 1 of 3. Short forms fit
rules that pick a branch; this one states what an output must contain, and
shortening it halved what it bought.

**The bug-report reference, three reps each.** On a loud deterministic crash
and a silently wrong total that was intermittent and slow to catch: without it,
all three runs rated the silent total above the crash. With its severity table,
one tied them and one inverted them, quoting the table and then overriding it.
The table went. The same runs showed the reference lifting exact values, cited
expectations, frequency ratios and isolation — isolation from 0 of 3 to 3 of
3 — so those stayed.

**Five specs, full runs, blind-judged.** Hotel cancellation, login lockout,
stock reservation, payroll overtime and seat holds, each with a written spec,
a design export and code carrying defects that contradict a specific line. One
agent per version per spec, one judge per spec seeing both deliverables under
random labels, building its own ground truth before reading either.

|                    | before | after |
| ------------------ | ------ | ----- |
| real defects found | 11     | 27    |
| missed             | 17     | 1     |
| false positives    | 1      | 6     |
| right design frame | 1 / 5  | 5 / 5 |
| bug report quality | 2.9    | 4.5   |
| tokens             | 958k   | 1.10M |

Recall 39% to 96% for 15% more tokens. In three of five runs the earlier
version declared code and design out of scope and filed nothing, and one judge
found it had read the code — its test cases named internal functions the spec
never mentions — without reporting what it saw.

All six false positives shared two causes, both lines this branch had added:
robustness gaps no requirement asks about filed as bugs, and hard-coded values
that match the approved frame filed as token-binding defects. Narrowed and
re-measured with three independent agents per arm: false positives 2 of 3 to 0
of 3, real defects 5.0 to 5.3 of 6.

**A method note.** Several earlier checks here ran three repetitions inside
one agent. Those are not independent — they agreed with each other every
time — so each counts as roughly one sample. Single-agent results suggested
the narrowing had cost three real defects; independent agents showed all
three were noise.

The rule that came out of this: **add knowledge, not discipline.** Guidance
that tells the model to be careful changes nothing measurable. Guidance that
answers a question it cannot derive — which frame is the requirement — does.
