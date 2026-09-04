# Fix Mode — Applying the Audit to the Documents

Read this only when the user passes `--fix` or asks you to fix / update the documents.
Never enter fix mode on your own initiative: an audit changes nothing, and the user decides
when it starts changing their documentation.

**Fix mode runs after the full audit, including the review loop.** Fixing findings from an
unreviewed pass means editing documents based on the gaps you happened to notice first.

## What fix mode edits

It edits **the documents that were audited** — the output artifact the audit was run against.
Never the spec: the spec is the standard being checked against, and a fix that edits the
standard to match the output makes every verdict trivially `Covered`. A genuine problem in the
spec is an `Undecided` row and a question for its owner.

Which document that is depends on what the audit was run on, and the difference changes what
may be applied:

| The audited document is… | Then |
| ------------------------ | ---- |
| **A deliverable being produced** — a design doc, a spec write-up, a report, a handover document that the team is still drafting from the requirement | The requirement is authoritative. Apply `Missing`, `Partial`, `Stale` **and** `Contradict` fixes: the document is supposed to say what the requirement says, and nothing about it describes a shipped system yet. |
| **Documentation of a running system** — a user manual, a runbook, an API reference for something already deployed | Apply only `Missing`, `Partial`, `Stale`. `Contradict` about behavior gets proposed, not applied — see the trap below. |

If you cannot tell which case you are in, ask. The answer decides whether a `Contradict` row
gets rewritten or escalated, and getting it wrong in the second case puts a false statement
into the documentation of a live system.

## What may be fixed automatically

The audit says what is wrong. It does not always say what is true. Only the first group is
safe to edit:

| Verdict | Action |
| ------- | ------ |
| `Missing` | Add the missing statement to the document the audit names, **only if the spec states the content in full**. If the spec is vague about it, it is not a fix — it is authorship. |
| `Partial` | Complete the existing statement with the condition, value, or case the spec names. Edit the sentence in place; do not rewrite the section. |
| `Stale` | Update the superseded value or name to the spec's current one, and update the document's revision line. |
| `Contradict` | In a deliverable being drafted: apply — the requirement is authoritative. In documentation of a running system: **propose, do not apply**, unless the contradiction is a value the spec unambiguously owns (a limit, format, ID pattern, cutoff time). |
| `Conflict` | **Propose, do not apply.** Two documents disagreeing means someone has to decide which is right; the spec may be the stale one. |
| `Unspecified` | **Never fix.** The document says something the spec is silent on. Deleting it may delete real behavior; keeping it may bless a drifted doc. That is the spec owner's call. |
| `Undecided` | Never fix. The spec is ambiguous — that is a question for its owner. |

**The trap in `Contradict`, for documentation of a running system:** a document describing
behavior the spec explicitly puts out of scope may be describing what the system actually does.
(Behavior the spec is merely silent on is `Unspecified`, not `Contradict`.) Deleting that paragraph makes the documentation match
the spec and stop matching reality. When a `Contradict` row is about behavior rather than a
stated value, write the proposed edit into the report and stop.

## Rules for the edits themselves

1. **One requirement, one edit.** Every change traces to a `Req ID`. A change that traces to
   nothing does not belong in this run, however obviously right it looks.
2. **Minimal diff.** Edit the sentence, not the section. Do not reformat, re-order, re-word,
   or "improve" surrounding text — the reviewer must be able to see what the audit changed.
3. **Match the document's voice.** Same tense, terminology, and heading style as the file you
   are editing. A document with one paragraph in your register reads as an error.
4. **Use the document's own vocabulary,** not the spec's, when the document already has a term
   for the concept. Introducing the spec's wording alongside the document's creates the next
   audit's `Conflict` row.
5. **Never invent a value.** If the fix needs a number, name, or behavior the spec does not
   state, it is unfixable — list it, do not guess.
6. **Never delete content to close a gap.** Deleting the contradicting paragraph is not a
   documentation fix unless the user decided that paragraph is wrong.

## Before editing

1. Check the working tree is clean (`git status`). If it is not, say so and ask before
   touching files — your edits must be separable from work already in progress.
2. If the documents are not in version control, say so explicitly and list the files you are
   about to change before changing them.

Do not commit. The user commits, unless they asked otherwise. If they do ask you to commit,
stage only the documents you edited — never the review report, which is a working artifact.

## After editing

1. **Re-verify each fixed row** against the edited document: re-read the section and confirm
   the verdict now holds. A fix believed rather than checked is the failure this whole skill
   exists to prevent.
2. Update the row's verdict to `Covered`, with the new citation and quote from the edited file.
3. Add a `## Fixes applied` section:

   | Req ID | Document | Old verdict | Change made | New verdict |

4. Add a `## Proposed, not applied` section for every `Contradict`, `Conflict`, `Undecided`,
   and unfixable `Missing` — each with the exact edit you would make and the decision needed
   before it can be made. This section is the deliverable of fix mode as much as the edits are.
5. Re-run `scripts/check_report.py` on the report.

## Reporting

Lead with the counts: rows fixed, rows proposed, rows left. Then the two sections above, then
the file-by-file list of what changed. Never report "documentation updated" without naming
what was left undecided — the unfixed rows are the ones that need a human.
