---
name: req-audit
description: Use when the user asks to audit a spec against the code and tests, wants a requirement or coverage status report, a traceability matrix, a gap analysis of what is implemented and tested, wants an existing audit rebuilt with new results, or asks to attach screenshot evidence to one.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Requirement audit

**IRON LAW: build the report and hand over its path before evidence is ever mentioned. Never start
capturing images unasked.**

Data lives in JSONL, rendering lives in a script. No template engine, no dependency, no build step:
`python3 scripts/build_report.py <dir>` writes one self-contained HTML file that opens in a browser.

Generation is deterministic Python — same data in, same report out, no model involved. What costs
effort is the data: requirements extracted from a spec and checked against code and tests. If that
list already exists as a flat `reqs.txt`, import it and the whole report needs no model at all.

## Three steps

### 1. Build from the data you already have

The commands run from the project, not from here, so anchor them on this skill's own base
directory — the path given to you when this skill loaded:

```bash
SKILL=<base directory of this skill>          # .../.agents/skills/req-audit
DIR=<project>/.testcases/req-audit/<slug>

mkdir -p "$DIR/data"
cp "$SKILL/assets/report.json" "$DIR/report.json"
# then either import an existing flat list …
python3 "$SKILL/scripts/build_report.py" "$DIR" --from-reqs <path>/reqs.txt
# … or write $DIR/data/reqs-*.jsonl yourself and build
python3 "$SKILL/scripts/build_report.py" "$DIR"
```

#### Deriving the rows

This is the part that costs real effort, and the part a rendering script cannot do for you.

One row is **one behaviour, condition, validation or edge case** — not one paragraph of the spec. A
paragraph saying "khi hết hạn thì trả 409 và không trừ tồn kho" is two rows: the status code and the
inventory side effect can fail independently, and a single row hides which one did.

Every row carries the `file:line` it came from. A requirement you cannot point at is one you
invented; drop it or raise it as a question. When the spec is silent on something the code decides,
that is not a gap in the code — it is a `CONFIRM` row with the question written in `qa`, because
guessing here is how an audit launders an assumption into a fact.

Assign `status` only after opening the implementation and the test. The spec tells you what should
be true; only the code and its tests tell you what is. Recording PASS from a spec reading is the
single fastest way to make this whole report worthless.

If a requirement list already exists — a `goalrun` `reqs.txt`, a coverage map from the `testcase`
skill — import it instead of re-deriving it.

Read `references/schema.md` before writing the first JSONL line. Adjust `columns` and `status` in
`report.json` to fit the work. The build fails loudly on bad data (duplicate ids, undeclared status,
references to unknown ids) — fix the data, not the script.

Hand the user the `REQ-AUDIT.html` path **here**. The report is already usable.

### 2. Ask

> Do you want screenshot evidence?

No → stop. Yes → step 3. Do not start capturing unasked: the evidence pass costs many times more
than step 1, and plenty of reports never need images.

### 3. Evidence pass

Read `references/evidence.md` for the file contract, then track these:

```
Evidence pass:
- [ ] Split requirements by group, one batch name per agent
- [ ] Agents capture and write <batch>.manifest.jsonl + <batch>.reqs.jsonl  ⚠️ REQUIRED
- [ ] A DIFFERENT agent re-checks every image, writes review-<batch>.jsonl  ⛔ BLOCKING
- [ ] Rebuild and report the new Evidence percentage
```

Rebuilding is idempotent: images attach themselves and the Evidence bar moves.

## Updating an existing report

- Human verdicts: append to `data/overrides.jsonl`, never edit `reqs-*.jsonl`. That keeps the line
  between what was derived and what a person concluded.
- Fresh E2E results: replace `data/e2e-results.jsonl` and rebuild.
- Progress since last time: fill `baseline` in `report.json` with the previous build's numbers to get
  the "Before → Now" table.

## Honest status

Two rules in `report.json` stop the report flattering itself: `demote_pass_without_test` downgrades
any requirement marked PASS with no test behind it, and `e2e_fail_status` forces anything with a
failing E2E run to deviation. Do not remove them to make the table look better.

Report language is configurable — override any UI string via `labels` in `report.json`.

## Anti-patterns

- Editing `data/reqs-*.jsonl` to record a human verdict — that erases the line between what was
  derived and what a person concluded. Append to `data/overrides.jsonl`.
- Letting the agent that captured a batch also review it. It will pass its own work.
- Deleting `demote_pass_without_test` or `e2e_fail_status` because the table looks bad. The table
  looks bad because the work is not done.
- Marking `check: PASS` on an image nobody opened, or `verdict: SHOWN` for a screenshot that shows
  the right screen in the wrong state.
- Adding columns because the data has fields. Thirteen columns leave ~95px each; drop what nobody
  reads.

## Self-check

```bash
python3 "$SKILL/scripts/test_build_report.py"
```
