# Bug reports

Read when a failing case, a review finding, or the user's description becomes a bug to file.

You already know the shape of a bug report. What follows is only the part that gets reports
bounced back.

## The rule

**A bug report is a reproduction, not a complaint.** If a developer cannot reach the wrong
state from your text alone, it is not a report yet — it is a notification that you saw
something.

## Reproduction

Every step names the exact value used, never the class of value.

| Bounced | Files |
| ------- | ----- |
| "Enter an invalid email" | "Enter `a@b`" |
| "Upload a large file" | "Upload a 10.5 MB PNG (`fixtures/large.png`)" |
| "Log in as a user without permission" | "Log in as `qa_viewer` (role: Viewer, no `orders.edit`)" |
| "Wait a while" | "Wait 61 s (token TTL is 60 s)" |

Then state the three lines that decide whether it is triaged or closed as "works for me":

- **Expected** — and *where that expectation comes from*: requirement ID, spec line, design
  link, or "consistent with `/orders` which does X". An expectation with no source is an
  opinion, and gets closed as one.
- **Actual** — what the system did, quoted: the error string, the HTTP status, the rendered
  value. Not "it breaks".
- **Frequency** — how many of how many attempts (`3/3`, `1/10`). A bug nobody labelled as
  intermittent gets closed the first time it passes.

Environment carries only what could change the outcome: build/commit, role, browser/device if
rendering matters, data state, feature flags. Everything else is noise.

## Evidence

Attach console errors, the failing request/response, and the server log line — a screenshot
alone shows the symptom and hides the cause. Screenshot the whole viewport, not the crop that
already assumes the diagnosis.

## Isolate before filing

Spend the two minutes that save the developer twenty:

- Does it reproduce on a clean session / incognito / fresh seed data?
- Is it the last build only? Name the last known-good build — "regression since `abc123`" is
  worth more than the rest of the report.
- Does it reproduce through the API as well as the UI? That splits frontend from backend
  before anyone is assigned.
- One bug per report. Three symptoms with one cause is one report; three causes filed as one
  gets partially fixed and closed.

## Severity

Severity is **impact on the user and the data**, decided from the table below — never from how
annoying it was to hit, how long it took to find, or how bad it looks.

| Level | Criterion |
| ----- | --------- |
| S1 | Data loss or corruption, security/permission bypass, money wrong, core flow impossible for everyone |
| S2 | Major feature broken with no workaround, or wrong data shown as if correct |
| S3 | Feature degraded, workaround exists and is discoverable |
| S4 | Cosmetic, or an edge case a real user is unlikely to reach |

Two rules that override the table:

- **Silent wrong data outranks a loud crash.** A crash is noticed; a wrong total is trusted.
  Wrong-but-plausible output is S1/S2 even when nothing errors.
- **Frequency is not severity.** A rare S1 is still S1 — it goes in *priority*, which is the
  team's call, not yours. Propose severity; never assign priority for them.

## Linking back

Every bug filed from a test case carries the case ID, and the case's requirement ID with it —
that is what lets the fix be verified against the requirement instead of against the symptom.
A bug with no case behind it means coverage was missing: add the case in the same pass, so the
next run catches it before a human does.
