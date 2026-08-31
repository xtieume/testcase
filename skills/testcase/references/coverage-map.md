# Coverage Map

Work through these dimensions **before** writing any case — not to produce a case per bullet, but so every real risk is consciously accepted or rejected.

Per dimension, decide one of:

* **Covered** — a case exists
* **N/A** — does not apply, and you can say why
* **Blocked** — needs a requirement answer (record it under Remaining Questions)

If the system handles Japanese text, also read `i18n-jp.md`.

---

## A. Happy path

* Normal valid input
* Expected successful operation
* Default values
* Typical user flow
* Multiple valid values
* First-time operation
* Repeated successful operation

---

## B. Input validation

* Empty / null / missing value
* Minimum, maximum, exact boundary
* Below minimum, above maximum
* Invalid format, wrong type
* Special characters, spaces, leading/trailing spaces
* Duplicate value
* Very long input
* Unexpected input

**Security-relevant inputs** — always try these on free-text fields:

| Input | |
| ----- | -- |
| `<script>alert(1)</script>` | HTML/script injection |
| `' OR 1=1 --` | SQL-looking string |
| `../../etc/passwd` | Path traversal-looking string |
| 10,000+ char string | Length overflow |

Expected: the input is safely stored/escaped, or rejected with a clear validation error.
Never executed. Never a 500.

---

## C. Boundary conditions

For every numeric, string, date, quantity, or collection constraint:

```text
minimum - 1
minimum
minimum + 1

maximum - 1
maximum
maximum + 1
```

Lists / collections:

```text
0 items
1 item
normal number of items
maximum allowed
maximum + 1
```

Dates:

```text
before allowed date
first allowed date
normal date
last allowed date
after allowed date
```

Skip combinations that carry no real risk.

---

## D. State transitions

Identify the states the feature/data can hold:

```text
Draft → Submitted → Approved → Completed
```

Then ask:

* Can every transition actually happen?
* Can the user perform the action in each state?
* What happens when the action is attempted in an invalid state?
* Can the transition happen twice?
* Can the user go backward?
* What happens after refresh? After reopening the page?
* What happens if another user changes the state concurrently?

The single most frequently missed area — mandatory review.

---

## E. Permission / role

Fill the matrix for every relevant role — do not assume permissions:

| Role | View | Create | Edit | Delete | Execute |
| ---- | ---- | ------ | ---- | ------ | ------- |
| Admin | | | | | |
| Normal user | | | | | |
| Read only | | | | | |

Check:

* Unauthorized access
* Read-only access
* Permission changed mid-operation
* Direct URL / API access despite hidden UI
* Access to another user's data

Unspecified permission behavior is a question, not an invention.

---

## F. Error & failure

> "What happens when this operation fails?"

* API error, API timeout
* Network disconnected
* Server error, database error
* Validation error
* Partial failure
* Duplicate request (double submit)
* Session expiration
* Permission failure
* Unexpected backend response
* Missing data, corrupted/invalid data

For every important backend operation, identify both the success and the failure case.

---

## G. Data consistency

For persistent data, *"value changed on screen"* is not finished. Also verify:

* UI value vs database value vs API response
* Reopen / reload behavior
* Save, cancel, refresh behavior
* Navigate away and back
* Related records
* Duplicate records
* Old data compatibility

> "Is the correct value actually persisted, and still correct after reload?"

---

## H. UI interaction

* Initial display, default state
* Dropdown options, selection, deselection
* Keyboard interaction, mouse interaction
* Disabled controls
* Loading state, error state, empty state
* Long text, overflow
* Multiple clicks, double click, rapid interaction
* Refresh, browser back/forward
* Modal open/close, cancel, save
* Unsaved changes warning

Do not test visual details unless the requirement makes them relevant.

**Non-functional** — add only when the requirement makes them a real risk:

* Performance: large data volume (1,000+ / 10,000+ rows), slow response on heavy operations
* Accessibility: keyboard-only operation, focus order — when the requirement targets
  accessibility, or on form-heavy screens

---

## I. Combinations

When multiple variables interact (`Role × Status × Type × Permission`), do not test the
full Cartesian product. Instead:

1. Identify high-risk combinations
2. Identify combinations that change business behavior
3. Use pairwise thinking where appropriate
4. Explicitly test combinations that could expose authorization or state bugs

---

## J. Integration / dependency

```text
UI → API → Service → Database
```

For each dependency:

* Succeeds
* Fails
* Returns empty data
* Returns unexpected data
* Is slow
* Is unavailable
* Data changes between requests
* Concurrent updates

---

## K. Regression

> "What existing functionality could this change break?"

* Existing features using the same component
* Existing data
* Existing APIs
* Related screens and workflows
* Shared validation, shared permissions
* Existing reports / exports
* Existing calculations
* Existing integrations

Only where the risk is realistic — not everything the code touches.

---

## Worked example

Requirement:

> User can change 工種コード using a dropdown. The selected value should immediately be
> reflected in L1.

**Wrong output** — one case:

```text
1. Open dropdown
2. Select 工種コード
3. Verify L1
```

**Right approach** — first enumerate the variables:

```text
Current 工種コード, new 工種コード, dropdown options,
L1 current value, user permission, save state, backend persistence
```

Then walk the map:

| Dimension | Cases |
| --------- | ----- |
| Positive | Select each valid option; change A → B; change B → C |
| Boundary | First option; last option; no selection (if allowed) |
| UI | Open/close dropdown; repeated changes; rapid changes |
| State | Before save; after save; after reload; cancel |
| Permission | Editable user; read-only user |
| Error | Update API failure; timeout; invalid backend response |
| Data | L1 reflects correct value; persisted value still correct after reload |
| Regression | Existing records; other fields depending on 工種コード |
| i18n | Option labels with 全角 characters; see `i18n-jp.md` |

Not every row must become a case — but no important risk goes unconsidered.
