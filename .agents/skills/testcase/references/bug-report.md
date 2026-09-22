# Bug reports

Read when a failing case, a review finding, or the user's description becomes a bug to file.

You already know the shape of a bug report. What follows is only the part that gets reports
bounced back — and unlike the test case table, nothing lints it. These rules hold because you
apply them, not because a script fails.

## The rule

**A bug report is a reproduction, not a complaint.** If a developer cannot reach the wrong
state from your text alone, it is not a report yet — it is a notification that you saw
something.

## Fields, in this order

The order is the spec: same shape every time, importable, and each field answerable from the
ones above it. Severity sits after Workaround because S2 and S3 are told apart by it.

| Field | Rule |
| ----- | ---- |
| Title | `[Area] <what goes wrong> when <condition>` — searchable |
| Summary | One line for the triager |
| Type | Functional / UI / Performance / Security — this is what routes it |
| User impact | Who, roughly how many: "all buyers using a coupon", "admins only, ~5 staff" |
| Workaround | What a user or support can do today, or `None found` |
| Environment | Build/commit, role, plus only what changes the outcome: browser/device if rendering matters, data state, feature flags |
| Steps | Numbered, **exact values** — see below |
| Expected | The value, **and its source**: requirement ID, spec line, design node, or "consistent with `/orders`". No source = an opinion, closed as one |
| Actual | Quoted: the error string, the HTTP status, the rendered value. Not "it breaks" |
| Frequency | A ratio — `3/3`, `1/10`. Unlabelled intermittence gets closed the first time it passes |
| Isolation | The four checks below, or `Not isolated — <why>` |
| Evidence | Console errors, the failing request/response, the server log line. Full-viewport screenshot, never the crop that assumes the diagnosis. Screen recording when the evidence is *when* things happened: animation, drag, race, hang |
| Severity | S1–S4 proposed, with the criterion it came from |
| Links | Case ID, requirement ID, related ticket, design node |

Blank is not an answer — it reads as "not checked" and the report comes back. `None found`
and `Not isolated — <why>` are answers.

**User impact is what priority is set from.** You propose severity; the team sets priority,
and cannot without this field.

## Exact values

Every step names the value used, never the class of value.

| Bounced | Files |
| ------- | ----- |
| "Enter an invalid email" | "Enter `a@b`" |
| "Upload a large file" | "Upload a 10.5 MB PNG (`fixtures/large.png`)" |
| "Log in as a user without permission" | "Log in as `qa_viewer` (role: Viewer, no `orders.edit`)" |
| "Wait a while" | "Wait 61 s (token TTL is 60 s)" |

## Isolate before filing

Two minutes here save the developer twenty:

- Clean session / incognito / fresh seed data — still reproduces?
- Last known-good build. "Regression since `abc123`" is worth more than the rest of the report.
- API as well as UI? That splits frontend from backend before anyone is assigned.
- One bug per report. Three symptoms of one cause is one report; three causes filed as one
  gets partially fixed and closed.

## Severity

Impact on the user and the data — never how annoying it was to hit, how long it took to find,
or how bad it looks.

| Level | Criterion | Example |
| ----- | --------- | ------- |
| S1 | Data loss or corruption, permission bypass, money wrong, core flow impossible for everyone | Checkout charges the wrong amount; a Viewer can delete orders |
| S2 | Major feature broken with no workaround, or wrong data shown as if correct | Search returns nothing; an order total ignores a refund |
| S3 | Degraded, workaround exists and is discoverable | Filter option missing but the URL parameter works |
| S4 | Cosmetic, no user can act on it wrongly | Label typo; 2 px misalignment |

Two rules override the table:

- **Silent wrong data outranks a loud crash.** A crash is noticed; a wrong total is trusted.
  Wrong-but-plausible output is S1/S2 even when nothing errors.
- **Frequency is not severity.** A rare S1 is still S1. Frequency belongs to priority.

Contrast, focus-visible and hit-target violations are S2 however small they look
(`design-validation.md`).

## Linking back

The case ID and its requirement ID travel with the bug — that is what lets the fix be verified
against the requirement instead of against the symptom. A bug with no case behind it means
coverage was missing: add the case in the same pass.
