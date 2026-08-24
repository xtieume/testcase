# Mode B — Investigation Without a Spec

Read this when the user gives documents and a question but no spec to audit against.

## The trap

With no spec, the natural move is to read the documents and report what they say. That
produces a summary shaped by whatever the documents happened to cover, and the reader cannot
tell the difference between "the answer is X" and "nobody wrote about X."

The fix: derive the checklist from the **question**, not from the documents. What would a
complete answer have to contain? Write that list first, then go looking.

## Steps

**1. Restate the question as sub-questions.**

Break it into the atomic questions a complete answer must resolve. Use
`dimensions.md` as the prompt — a question about a feature still has behavior, data, error,
permission, and operational sides.

| Q ID | Sub-question | Why it matters to the answer |

Show this list to the user before the findings. If the question is too vague to decompose,
ask — a vague question guarantees a vague audit.

**2. Inventory the sources.**

Same as Mode A step 1. Say what you could not read.

**3. Answer each sub-question from the documents.**

| Q ID | Sub-question | Answer | Confidence | Evidence (doc + section) | Quote |

**Confidence**:

| | Meaning |
| -- | ------- |
| `Stated` | A document says it directly — quote it |
| `Inferred` | Assembled from several documents — show the pieces and the inference |
| `Conflicting` | Documents disagree — quote both, do not pick a winner silently |
| `Absent` | No document answers it — record the search terms and files you checked |

`Inferred` and `Absent` are the load-bearing rows. Never upgrade an inference to a fact
because it seems obvious.

**4. Run the review loop.**

Return to `SKILL.md` step 4. Give the subagent the question, the document paths, and the
report — not your reasoning. It re-derives the sub-questions from the question alone and
checks: sub-questions you missed, answers not supported by their quote, `Absent` rows whose
answer exists elsewhere, and conflicts reported as agreement.

**5. Report.**

Lead with the direct answer to the original question, then the sub-question table, then
`## What the documents do not say` — the `Absent` and `Conflicting` rows collected together.
That section is the deliverable the user cannot get from reading the docs themselves.

Write it to `.testcases/docs-review/docs-review.md` (unless the user names a path), not only to
chat, and match the language of the question unless the user asks otherwise. Same rule as Mode A:
the report is a working artifact — the directory is excluded via `.git/info/exclude` and the
report is never committed.

Then lint it:

```bash
python3 scripts/check_report.py .testcases/docs-review/docs-review.md --mode b
```
