## Remaining Questions / Assumptions

Q-R3        Does "day" in R2/R3 mean calendar day or working day? R3 excludes public
            holidays and nothing mentions weekends. TC-006/013/029 assume every calendar
            day deducts. If weekends are excluded, all three expected values change.
Q-R5        "Unused days expire 3 months after the next anniversary" — the anniversary the
            days were granted at (expiry 2026-07-01) or the following one (2027-07-01)?
            Blocks TC-009; TC-015 was rewritten to be correct under either reading.
Q-R1        Does the annual grant add to or replace an existing balance? R5 presupposes
            days carry over, which only makes sense if grants are additive. TC-027 carries
            the additive value with that rationale named, and TC-033's inequality only has
            content under it — neither is left open, so this is an assumption to confirm,
            not a blocker. Confirming it settles both rows; refuting it removes them.
Q-R6        Is approval exactly on the start date "after the leave start date"? Blocks TC-030.
Q-LIFECYCLE Does a request deduct at submission (R2) or at manager approval (R6)? The spec
            applies both models. Determines whether a Pending request holds balance, what
            TC-032 restores, and what a manager rejection releases.
Q-R6-REJECT Can a direct manager reject a valid, in-balance request? R6 only describes
            approval; no case covers a discretionary rejection.
Q-R2-SLOT   Is the AM/PM slot constrained at the schema/UI layer, or must the request API
            reject an out-of-enum slot? TC-035 assumes the latter.
Q-R6-ERR    R6/R7 never state the error contract for an invalid-state approval or cancel.
            TC-025/026 assume a rejection with the state unchanged.
Q-R1-RUN    R1 describes an automatic grant on the anniversary. TC-018/028 model it as a
            manually re-invocable, idempotent job; that framing is not in the spec.
Q-R3-EMPTY  Is a request whose net deduction is 0 (every day a holiday) created, or rejected
            as empty? R3 says only that a holiday does not deduct. TC-014/020 assert the
            balance and deliberately do not assert the creation outcome.
Q-R5-BATCH  When the balance holds days from two grants with different expiry dates, is the
            oldest batch consumed first, or is the balance one pool? R5's "unused days
            expire" implies per-batch tracking; no case covers consumption order.

FROZEN      Q-R3 is escalated, not open. Reviewers reversed on it across three rounds
            (literal 4.0, then TBD, then literal 4.0) arguing from the same text. The loop
            cannot settle it; the requirement owner decides. TC-006/013/029 carry the
            literal reading with the assumption named, and stop being re-litigated.
Q-R2-UNIT   R2 states the 0.5-day unit but not what happens to a non-conforming request:
            refused, or rounded/truncated? TC-005 assumes refused.
Q-TRANSPORT The spec defines no API or transport layer. TC-010/031 assert an unauthorized
            refusal rather than a specific HTTP status; confirm the surface under test.
Q-R6-WHEN   R6 says "the employee's direct manager" but never fixes when that relationship
            is evaluated: at submission, or at approval? An org change between the two makes
            the readings disagree. Blocks TC-042.
Q-R7-WHO    R7 says a cancelled request restores days but never says who may cancel:
            the employee only, the employee and their direct manager, or anyone with the
            role? R6 restricts approval; nothing restricts cancellation. Three readings need
            two cuts, not one: TC-044 separates "any role holder" from the rest, TC-049
            separates "employee only" from "employee plus direct manager". Blocks both.
Q-R5-ORDER  When a cancel lands on the same day as the expiry cutoff, does expiry run first
            (nothing to restore) or the cancel (days restored, then expired)? R5 and R7 give
            no ordering. The two produce different balances. Blocks TC-016.

Q-DEPS      These questions are not independent. Q-R5 reading A (days expire 3 months after
            the anniversary they were granted at) means no balance ever survives to the next
            anniversary — under which Q-R1 (additive vs replace) and Q-R5-BATCH (consumption
            order across batches) do not arise at all, and TC-027/041 describe states the
            system cannot reach. Both only have content under reading B. Answer Q-R5 first;
            two of the eleven questions below it may dissolve.
Q-R6-AUDIT  R6 defines no approval record, timestamp or counter — only that the direct
            manager approves and that late approval is flagged. TC-025/039 need some
            observable trace to tell an idempotent guard from a silent no-op, since the
            balance does not move under either. Does the system persist an approval record?
            Without one, neither case can distinguish the guard from its absence.
Q-R2-RANGE  No line in R1-R7 addresses date-range ordering. TC-046 assumes end < start is
            refused rather than normalised or treated as a zero-day request.
Q-R7-PARTIAL R7's "unless those days have already expired" is written all-or-nothing. When a
            request's deducted days span an expired batch and a live one, does cancelling
            restore the live portion, refuse entirely, or restore everything? Blocks TC-050.
            Arises only under Q-R5 reading B (see Q-DEPS).
Q-R2-RANGE-SLOT  R2 defines the 0.5 unit and the AM/PM slot, but never how a slot combines
            with a multi-day range. Blocks TC-048.
Q-R4-NET    Is "exceeding the balance" (R4) evaluated against the net deduction after R3's
            holiday exclusion, or the gross range length? TC-036/037 assume net.
Q-R4-OVERLAP Nothing forbids two requests covering the same date, or says whether the shared
            day is deducted twice. Blocks TC-052.
Q-R7-PAST   R7 restricts cancellation by expiry only. May leave already taken still be
            cancelled, restoring its days? Blocks TC-053.
Q-R3-HALFDAY R3 excludes a public holiday from deduction but does not say whether that
            exclusion applies below whole-day granularity. A half-day request falling on a
            holiday deducts 0 under one reading, 0.5 under the other. Blocks TC-020.
Q-R1-LEAP   R1 fires the grant "on the joining anniversary" but never defines that date for
            an employee joined on 29 February, in a non-leap year. Blocks TC-055.
Q-R6-NOMGR  R6 names the direct manager as the only approver but says nothing about an
            employee who has none on record. Blocks TC-060.
Q-R2-WHO    No line restricts who may create a request. R6 restricts approval, Q-R7-WHO
            interrogates cancellation; creation is never addressed. Blocks TC-061.
Q-R4-RETRY  No line addresses a duplicate submission of the same request (a client retry
            after a lost response). TC-062 assumes the create path is idempotent; without
            that, a retry deducts the day twice. Distinct from Q-R4-OVERLAP, which is about
            two different requests sharing a date.
