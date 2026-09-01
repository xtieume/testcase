# Requirement Dimensions — Decomposing a Spec into a Checklist

Read at step 2. Walk every dimension and ask: does the spec say something here, and is it
checkable against a document? Write down the dimensions that do not apply and why — an
omitted dimension is indistinguishable from an overlooked one.

## Dimensions

| Dimension | What to extract from the spec |
| --------- | ----------------------------- |
| **Scope** | What is in scope, what is explicitly out. Out-of-scope statements are requirements too — docs that describe them are `Contradict`. |
| **Behavior** | Each described flow, step, and outcome. One row per branch, not one per feature. |
| **Business rules** | Calculations, thresholds, rounding, priority order, eligibility conditions. Every constant is a checkable value. |
| **Data** | Fields, types, required/optional, defaults, formats, units, allowed values, retention. |
| **States & transitions** | Every state and every legal/illegal transition the spec names. |
| **Roles & permissions** | Who may do what, and what each role sees. |
| **Errors** | Named error conditions, messages, codes, recovery paths. |
| **Interfaces** | API endpoints, parameters, responses, external systems, contracts, versions. |
| **Non-functional** | Performance targets, limits, availability, security, audit/logging obligations. |
| **Operations** | Setup, configuration, migration, rollback, monitoring the spec requires documenting. |
| **Compliance & legal** | Anything mandated by regulation, contract, or internal policy. |
| **Terminology** | Terms the spec defines. Docs using a different term for the same thing is `Partial`, not style. |
| **Audience** | Who each document is for. A correct statement in the wrong document is still a gap for its reader. |
| **Currency** | Version, date, and superseded material. Docs matching an older spec revision are `Stale`. |

## Making a requirement atomic

A row is atomic when a reviewer can answer it yes/no against one place in one document.

Not atomic:

> The system must validate the amount and show an error.

Atomic:

* `REQ-AMT-001` Amount rejects values below 0
* `REQ-AMT-002` Amount rejects values above 1,000,000
* `REQ-AMT-003` Rejected amount shows message `金額が不正です`

Splitting is what surfaces `Partial`: docs frequently cover the first half and drop the rest.

## Implicit requirements

The spec rarely states these; the documents still owe them. Add them explicitly and mark
their source `implicit`:

* What happens to existing data / users when the change ships
* Behavior at the boundary of every stated limit
* Behavior when a named dependency is unavailable
* The failure path of every success path the spec describes
* Whether the change is reversible

When the spec or documents are Japanese, also read `i18n-jp.md`.
