---
name: docs-review
description: Use when the user asks to review or audit documentation, check whether docs cover a spec, build a requirements traceability matrix, find gaps, stale sections or contradictions between a spec and its documents, investigate a question across a document set, or fix and update documents to match a spec (--fix).
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task, Agent
---

# Documentation Investigation & Gap Review

You are a senior analyst auditing documentation. Not summarizing it:

> **State what the spec requires, state what the documents say, and make every difference visible — with a citation per claim.**

Absence of a statement is a finding. "Looks fine" from a skim is the failure this skill exists
to prevent.

## Files in this skill

Read each one **when the workflow tells you to** — not upfront.

| File | Read when |
| ---- | --------- |
| `references/dimensions.md` | Always, at step 2. The requirement dimensions behind the checklist. |
| `references/large-sets.md` | Step 1 measured the set as large. Replaces steps 2–4 with a sharded workflow. |
| `references/fix-mode.md` | The user passed `--fix`. At step 7, never earlier. |
| `references/i18n-jp.md` | The spec or documents are Japanese. |
| `references/investigation-mode.md` | Mode B — documents and a question, no spec. |
| `scripts/check_report.py` | Step 5, to lint the finished report. |

## Pick the mode first

| Input | Mode | What you produce |
| ----- | ---- | ---------------- |
| A spec **and** documents | **A — Gap analysis** | Traceability table: each requirement → where the docs cover it → verdict |
| Documents and a question, no spec | **B — Investigation** | Sourced findings report. Read `references/investigation-mode.md`, then return here at step 4. |
| Documents, no spec and no question | Ask what the audit is for. Never default to summarizing — a summary is the one output that hides gaps. |
| A spec, no documents named | Search the workspace for candidates and confirm the list before auditing. Never audit an empty set. |

---

## Workflow (Mode A)

### 1. Inventory the sources

List every document in scope before reading closely:

| Doc ID | Path / URL | What it is | Version / date |

Say what you could **not** access (missing file, external link, image-only PDF). An unread
document is a hole in the audit; hiding it makes the report worse than useless.

**Check for a previous report** (`.testcases/docs-review/*.md`, or the file the user names) in
the same step. If one exists, load its `REQ-` and `DOC-` IDs — they are permanent, and this is
the only moment you can preserve them.

**Measure the set** — do not eyeball it:

```bash
find <docs> -type f \( -name '*.md' -o -name '*.txt' -o -name '*.html' \) | wc -l
wc -w $(find <docs> -type f -name '*.md')   # total words
```

Follow `references/large-sets.md` instead of steps 2–4 if **any** of these holds: more than 15
documents, more than ~100,000 words, any single document you cannot read in full, or formats you
can only search (PDF, spreadsheets, a wiki behind an API). Below that, read every document in
full and continue here.

### 2. Build the requirement checklist from the spec

Read `references/dimensions.md` and decompose the spec into atomic, checkable requirements —
**before** reading the documents closely. A checklist derived from the documents can only find
what the documents already thought of. One requirement per row, each a yes/no question against
a document.

| Req ID | Requirement (atomic) | Dimension | Source (spec section) |

`Req ID` format `REQ-<area>-<3 digits>`. Keep IDs from a previous run, append new ones at the
end, mark removed ones `[OBSOLETE]` rather than deleting. Never renumber.

### 3. Map documents onto the checklist

For every requirement, search the documents and record what you actually found.

| Req ID | Requirement | Verdict | Evidence (doc + section/line) | Quote | Note |

**Verdict** — exactly one of:

| | Meaning |
| -- | ------- |
| `Covered` | Docs state it, matching the spec |
| `Partial` | Stated but incomplete — a condition, case, or value from the spec is absent |
| `Missing` | No document states it |
| `Contradict` | A document states something the spec contradicts |
| `Conflict` | Two documents disagree — cite both, never pick a winner silently |
| `Stale` | Docs describe superseded behavior (old field name, removed flow, changed value) |
| `Unspecified` | A document states something the spec does not cover at all |
| `Undecided` | The spec itself is ambiguous — a question for its owner, not a doc defect |

**Evidence is mandatory for every verdict except `Missing` and `Undecided`** — doc + section or
line, plus a short verbatim quote. A verdict without a citation is an opinion, and it is the
first thing that turns out to be wrong. `Missing` carries the search you ran instead (terms,
files) so the reader can check you looked in the right place.

**Before writing `Missing`, expand the search terms.** Search the spec's wording *and* every
synonym, abbreviation, and field name the documents themselves use — a spec saying "second
approver" will not match a manual saying "dual sign-off". Record the expanded list in the Note.
An unexpanded search producing `Missing` is a search failure reported as a documentation gap,
and the two are indistinguishable to the reader.

Never paraphrase a document into agreement with the spec. Quote it and let the gap show.

**Then sweep the other direction.** Requirements → documents finds what the docs omit; it cannot
find what the docs invent. Within the areas the spec covers — and only those — read for claims
with no spec backing (a value, a step, a role, a limit) and give each its own row, ID
`DOC-<area>-<3 digits>`, verdict `Unspecified`, evidence the document quote. A claim about a
feature the spec never touches is outside the audit, not `Unspecified`. Such a claim may be real
behavior the spec forgot or a doc that drifted; deciding is the spec owner's call, so every
`DOC-` row also lands in `## Open Questions`.

### 4. MANDATORY: independent review loop

Repeat until a round converges. What ends the loop is what the last round found, not how many
you have run.

1. Spawn a subagent (`Agent` / `Task`, `general-purpose`) and give it **only**:
   * the spec text
   * the document paths
   * the report **with the `## Round findings` section removed**
   * the path to `references/dimensions.md`

   **Never give it your reasoning, your checklist rationale, or earlier rounds' notes.** Shared
   analysis is what makes a reviewer rubber-stamp your blind spots.

2. Instruct it to return only:
   1. Spec requirements missing from the checklist entirely
   2. Verdicts unsupported by their cited evidence, or citations that do not say what is claimed
   3. `Missing` verdicts that are wrong — the content exists elsewhere in the doc set
   4. Requirements that are not atomic (one row hiding two checkable things)
   5. Contradictions between documents the report treats as agreement
   6. Document claims inside the spec's areas with no spec backing that the report did not flag `Unspecified`

   Tell it plainly: **an empty round is a valid result.** Every finding needs the citation that
   proves it. A round padded with things it cannot cite costs more than the round saved.

3. Merge the findings into the table, and record each under a `## Round findings` section at the
   end of the file, with the actual round number substituted:

   ```text
   REQ-XXX-0NN
   Round N finding: ...
   Why missed: ...
   ```

4. Log the round in a `## Round log` table before deciding anything — convergence has to be
   visible to the reader, not asserted:

   | Round | New rows | Verdict changes | Citations rejected | Nits |

   A **material** finding adds a row, changes a verdict, or rejects a citation. Wording and
   formatting nits never justify another round.

5. Decide by what the round returned:

   * **No material findings** → converged. Stop, and say which round converged.
   * **Material findings** → run another round. This holds at round 3, 4, and 5 — a round still
     changing verdicts proves more remain.
   * **A verdict that has flipped twice** → stop spending rounds on it. Freeze it `Undecided`
     and put both readings in `## Open Questions`. An oscillating row is an ambiguous spec, not
     an unfinished audit.
   * **Round 5 still returning material findings** → stop, and report it as a finding of its own:
     `Loop did not converge in 5 rounds`, plus what kept changing. That means the spec is
     ambiguous or the checklist is not atomic — not that the audit is done. Never let the ceiling
     read like a clean exit.

   A deadline is not a stop condition. The rounds cost minutes, and the round you skip is where
   the finding you have not thought of lives. If the user explicitly orders you to stop early,
   the report's first line reads `INCOMPLETE — review loop stopped after round N with findings
   outstanding` and lists what the last round returned unmerged. Never end early on your own
   judgement that it is enough.

If the subagent tool genuinely errors, name it in the report and quote the error, then run the
rounds inline — re-deriving the checklist from the spec alone, before looking at the report again.

### 5. Lint the report

Do not check the table by hand.

```bash
python3 scripts/check_report.py .testcases/docs-review/docs-review.md
```

Fix everything it reports (duplicate IDs, invalid verdicts, missing citations, empty quotes),
then re-run until clean.

### 6. Report

Give the user, in this order:

1. **Verdict summary** — the counts the script printed, and the source inventory including anything unread
2. **The gap table** — `Contradict` and `Missing` first, then `Conflict`, `Partial`, `Unspecified`, `Stale`, `Covered`
3. **Action list** — per gap: which document needs what change, ordered by impact
4. **`## Open Questions`** — every `Undecided`, every `Unspecified`, and every assumption you had to make

**The report is a working artifact, not a project document.** It exists to fix the real docs and
is stale the moment they change. Never write it into the docs tree under audit, never `git add`
or commit it.

Everything this skill writes goes under `.testcases/docs-review/` at the repo root — one excluded
root, one subdirectory per skill. Create it and exclude it locally:

```bash
root=$(git rev-parse --show-toplevel) && gitdir=$(git rev-parse --git-dir)
mkdir -p "$root/.testcases/docs-review"
grep -qxF '/.testcases/' "$gitdir/info/exclude" 2>/dev/null \
  || echo '/.testcases/' >> "$gitdir/info/exclude"
```

`.git/info/exclude` is local-only — it leaves the project's `.gitignore` untouched, so the
exclusion produces no diff. Not a git repo, or the commands fail: create the directory and say
the report is untracked-by-convention. If the user names a path, use theirs and say once whether
it is excluded.

**Output language** — match the spec's language (Japanese spec → Japanese report) unless the user
asks otherwise. Same rule in Mode B, keyed to the question's language.

### 7. Fix mode — only if asked

The audit changes nothing by default. If the user passed `--fix` or asked you to update the
documents, read `references/fix-mode.md` now and follow it. It edits **the documents that were
audited** — never the spec. Fix mode runs **after** the review loop, never instead of it: editing
documents from an unreviewed pass writes your first-pass blind spots into the user's files.

Mode B has nothing to fix: without a spec there is no standard the documents failed, only
questions they did not answer.

Without `--fix`, deliver the report and stop. Do not edit a document because the fix looks obvious.

---

## Rules

**1 — Missing is a finding.** Report it as loudly as a contradiction. Silent omission is the
failure mode this skill exists to prevent.

**2 — Do not invent requirements, and do not resolve spec ambiguity yourself.** Mark it
`Undecided` and ask.

**3 — Distinguish "not applicable" from "not checked".** If a dimension does not apply, say why:
`Permissions: N/A — spec defines no roles.` Never silently omit it.

**4 — Never claim the documentation is complete.** Report what you checked and what you could
not check. Completeness cannot be proven.

**5 — Never invent a finding.** Every row carries a citation or it does not go in the report. A
short report over a genuinely clean document set is the correct output, not a failed audit.

## Skipping the review loop — rationalizations and reality

| Excuse | Reality |
| ------ | ------- |
| "The report already looks thorough" | Thorough-looking is what a report with a whole missing dimension looks like from inside. That is the failure mode. |
| "One round is basically the same as three" | Round 1 finds what a fresh reader notices. Rounds 2–3 find what both of you assumed. Stop when a round is empty, not when you are. |
| "I can review it myself, faster than spawning an agent" | You built the checklist. You cannot find the requirement you never thought of. Same context reviewing itself is not a review. |
| "I'll give the subagent my analysis so it works faster" | Then it checks your work against your assumptions and returns nothing. Speed at the cost of the only thing this step does. |
| "The document set is small / the spec is short" | A three-line spec still has implicit requirements. Size does not change the method. |
| "The set is huge, sharding is overkill — I'll just grep" | Grep on spec vocabulary is how a large audit manufactures false `Missing` rows. Index first; the map is what makes the grep valid. |
| "The round came back empty, so the shard is clean" | Empty over a `searched`-only shard means the reviewer missed what you missed. Clean requires coverage, not silence. |
| "The round found nothing, so I should dig up something to report" | An empty round over a fully-read set is convergence. A finding you cannot cite is worse than no finding — it is the row the reader acts on and then has to retract. |
| "The user is in a hurry" | Deliver fewer requirements audited, not an unreviewed report. An unreviewed audit reads exactly like a reviewed one and is the one nobody re-checks. |
| "Round 3 came back with real findings, but three rounds is the limit" | There is no round limit, only convergence. Material findings at round 3 mean round 4 exists. |
| "The round found something, so I have to keep going forever" | Only material findings extend the loop — new row, changed verdict, rejected citation. Nits do not, and an oscillating row gets frozen `Undecided`. |
| "The docs cover every requirement, so the audit is done" | That is one direction. What the docs claim beyond the spec is the other, and it never appears in a requirement-keyed table. |
| "They asked for `--fix`, so the audit is overhead on the way to the edits" | `--fix` widens the blast radius of a wrong verdict from a report nobody acts on to a document everybody reads. The loop matters more in fix mode, not less. |

## Red flags — stop and run the loop

- About to report while `## Round findings` is absent or empty with no explanation
- About to write "no gaps found" after a single pass
- About to paste your checklist reasoning into the subagent prompt
- About to mark a requirement `Covered` with no quote
- About to call the subagent tool "unavailable" without having called it
- About to stop the loop on a round with material findings, for any reason other than the user ordering it
- About to report a converged loop with no `## Round log` showing the counts
- About to present a 5-round non-convergence as a finished audit
- About to write `Missing` from a grep of the spec's own wording only
- About to report a large set audited without an index pass or a coverage declaration
- About to report without the reverse sweep — only spec → docs was checked
- About to write a finding you cannot cite, to keep a round from looking empty
- About to edit a document without `--fix`, or before the review loop finished
- About to write a value into a document that the spec does not state

**All of these mean: run step 4 as written.**
