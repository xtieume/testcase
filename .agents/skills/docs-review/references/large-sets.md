# Large Document Sets — Index, Shard, Sweep

Read this when the measurement in `SKILL.md` step 1 says the set is large. The single-pass
workflow does not degrade gracefully at this size: it produces `Missing` verdicts that are
really search failures, and review rounds that return nothing because the reviewer silently
sampled. Both read exactly like a clean audit. This file replaces steps 2–4 of `SKILL.md`
with a sharded version; steps 1, 5 and 6 stay as written.

## 1. Index pass — build the document map first

Before any checklist work, map what the documents actually contain. Split the set across
subagents (roughly 10 documents each) and have each return one row per document:

| Doc ID | Path | Sections (headings) | Key terms used | Values asserted | Version / date |

* **Key terms used** — the vocabulary *the document* uses, not the spec's. This column is the
  whole point of the pass.
* **Values asserted** — every number, limit, threshold, state name, role name, time, format,
  and ID pattern the document states. Copy them verbatim with their section.

Write the map to `.testcases/docs-review/docs-index.md` — a working artifact like the report:
never in the docs tree, never committed. It is an input to every later step and to the conflict
sweep.

**Why this comes first:** a requirement written as "second approver" in the spec and
"dual sign-off" in the manual is invisible to a spec-term grep. Without the index, that
becomes a confident `Missing`.

## 2. Expand search terms before every `Missing`

For each requirement, the search term set is: the spec's wording **plus** every synonym,
abbreviation, and field name for the same concept that appears in `docs-index.md`'s Key terms
column. Search all of them. A `Missing` verdict records the full expanded term list in its
Note — not just the spec's phrase.

If the index shows a document section whose topic matches the requirement but whose wording
does not, read that section rather than trusting the grep.

## 3. Shard by spec section

Build the requirement checklist per spec chapter (`references/dimensions.md` applies
unchanged), then dispatch one subagent per shard. Each shard subagent gets:

* its chapter of the spec
* its slice of the checklist
* `docs-index.md` (the whole map — cross-references live outside the shard)
* the candidate document paths its rows point at, plus permission to open any other document
  the index suggests

Each shard returns two things:

1. Its verdict rows, in the standard `SKILL.md` step 3 format, written to its own file
   (`.testcases/docs-review/shard-<chapter>.md`, alongside the index). Never have shards edit
   one shared table.
2. A **coverage declaration**:

   | Doc ID | Read | What was read |
   | ------ | ---- | ------------- |

   `Read` is `full`, `searched` (grep hits plus surrounding sections), or `not-accessed`.

The main agent concatenates the shard files into the report. Concatenation, not hand-editing —
a 200-row table edited by hand loses rows.

## 4. Conflict sweep — a separate pass

Doc-vs-doc disagreement does not surface from per-requirement lookup at this scale, because
the two documents rarely land under the same row. Run one dedicated pass over the
**Values asserted** column of `docs-index.md`: group every asserted value by what it describes
(batch limit, retry count, state name, role, cutoff time, format), then flag every group whose
members disagree.

Each disagreement becomes a `Conflict` row citing both documents — including the ones the spec
says nothing about, which are exactly the ones no requirement row would ever have caught.

## 5. Review loop, sharded

Run the `SKILL.md` step 4 loop **per shard**, on the shard's own rows and chapter. Rules unchanged:
the reviewer gets no reasoning and no prior round notes.

Shard rounds cap at **2 per shard** — sharding already buys independent eyes, and a third round
inside one chapter costs more than the cross-shard round that follows. Shard rounds do not count
toward the 5-round ceiling in `SKILL.md`; the cross-shard rounds do. A shard whose round 2 still
returns material findings is reported by name as unconverged rather than merged silently.

Then run **one cross-shard round** over the merged report, looking only for what shard
boundaries hide:

1. Requirements that fall between chapters and landed in no shard
2. The same requirement audited twice with different verdicts
3. `Conflict` rows the sweep found that no shard reflected
4. Shards whose coverage declaration is weaker than their verdicts imply

**An empty round only counts as clean if the shard's coverage declaration is `full` for the
documents its verdicts depend on.** An empty round over a `searched`-only shard means the
reviewer searched the same way you did and missed the same things. Say that in the report
rather than calling the shard clean.

## 6. When the budget runs out

Deliver fewer shards audited completely. Never audit every shard partially — a report where
each chapter is half-checked cannot be distinguished from a finished one by the person reading
it. Unaudited shards are listed in the source inventory as `NOT AUDITED`, by name, with the
chapters they cover.
