# Bug reports

Read when a failing case, a review finding, or the user's description becomes a bug to file.

**Your tracker owns the format.** GitHub issue forms, Jira and Linear enforce required fields
with a schema; a markdown template here enforces nothing and drifts from whatever the team
actually uses. Fill their form. What follows is only the judgement their form cannot check.

## The rule

**A bug report is a reproduction, not a complaint.** If a developer cannot reach the wrong
state from your text alone, it is not a report yet — it is a notification that you saw
something.

## Exact values

Every step names the value used, never the class of value.

| Bounced | Files |
| ------- | ----- |
| "Enter an invalid email" | "Enter `a@b`" |
| "Upload a large file" | "Upload a 10.5 MB PNG (`fixtures/large.png`)" |
| "Log in as a user without permission" | "Log in as `qa_viewer` (role: Viewer, no `orders.edit`)" |
| "Wait a while" | "Wait 61 s (token TTL is 60 s)" |

Three more decide whether it is triaged or closed as "works for me":

- **Expected, with its source** — requirement ID, spec line, design node, or "consistent with
  `/orders`". An expectation with no source is an opinion and gets closed as one.
- **Actual, quoted** — the error string, the HTTP status, the rendered value. Not "it breaks".
- **Frequency as a ratio** — `3/3`, `1/10`. Unlabelled intermittence gets closed the first
  time it passes.

## Isolate before filing

Two minutes here save the developer twenty:

- Clean session / fresh seed data — still reproduces?
- Last known-good build. "Regression since `abc123`" is worth more than the rest of the report.
- API as well as UI? That splits frontend from backend before anyone is assigned.
- One bug per report. Three symptoms of one cause is one report; three causes filed as one
  gets partially fixed and closed.

## Severity — our convention

Many teams score severity as impact × likelihood. This skill does not: **severity is impact
alone, frequency belongs to priority.** A rare S1 is still S1 — splitting them keeps a nasty
bug from being downgraded because it is hard to hit. If the project has its own matrix, that
matrix wins; say which one you used.

Impact means impact on the user and the data — never how annoying the bug was to hit, how
long it took to find, or how bad it looks.

| Level | Criterion | Example |
| ----- | --------- | ------- |
| S1 | Data loss or corruption, permission bypass, money wrong, core flow impossible for everyone | Checkout charges the wrong amount; a Viewer can delete orders |
| S2 | Major feature broken with no workaround, or wrong data shown as if correct | Search returns nothing; an order total ignores a refund |
| S3 | Degraded, workaround exists and is discoverable | Filter option missing but the URL parameter works |
| S4 | Cosmetic, no user can act on it wrongly | Label typo; 2 px misalignment |

**Silent wrong data outranks a loud crash.** A crash is noticed; a wrong total is trusted.
Wrong-but-plausible output is S1/S2 even when nothing errors.

Contrast, focus-visible and hit-target violations are S2 however small they look
(`design-validation.md`). You propose severity — priority is the team's call.

## Linking back

The case ID and its requirement ID travel with the bug, so the fix is verified against the
requirement instead of against the symptom. A bug with no case behind it means coverage was
missing: add the case in the same pass.
