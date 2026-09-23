---
name: normalize
description: Rewrites a casual, rambling everyday prompt into a compact engineering prompt — structured sections, imperative instructions, explicit escalation and done criteria — ready to paste into an AI or in front of a slash command like /goalrun. Use when the user says "chuẩn hóa prompt", "viết lại prompt này", "làm prompt cho gọn", "prompt này dài quá", "rewrite this prompt", "turn this into a proper prompt", "clean up my prompt", "make this a technical prompt", "prompt for /goalrun", or pastes a long informal instruction and asks for a version to send to an AI.
allowed-tools: Read
---

# Normalize — everyday prompt → engineering prompt

> Same requirements. Less prose. Shape an AI can execute.

## The rule

**Every line of the output traces to a phrase in the input.** No invented scope, no added
acceptance criteria, no "best practice" section the user never asked for.

Dropping a requirement fails the same way inventing one does. This is a rewrite, not a
redesign — you have no authority to decide the task is bigger or smaller than stated.

Never execute the normalized prompt. The deliverable is the text.

## Workflow

- [ ] 1. Extract — pull every requirement out of the input, verbatim-ish
- [ ] 2. Shape — group into sections, convert each to an imperative
- [ ] 3. Budget — fit the character limit
- [ ] 4. Second pass ⚠️ REQUIRED — diff output against input, both directions
- [ ] 5. Emit — one fenced block, nothing else

## 1. Extract

Read the input twice and answer, in the input's own words:

- **Target** — what file, path, URL, repo, ticket or command is this pointed at? Copy it
  character-for-character. A path is not paraphrasable.
- **Goal** — what state does the user want at the end? Usually one sentence buried in the
  middle of the rambling.
- **Sources of truth** — which folders, docs or systems did they name as authoritative, and
  in what order? Keep any reading order they gave ("trace newest → oldest").
- **Escalation** — what did they say to do when something is unclear? (ask, mark draft,
  widen the search, guess)
- **Done / output** — what artifact proves it, and what format?
- **Meta** — character limit, language, tone, "don't explain, just instruct".

Anything you cannot place in one of these is still a requirement. Give it its own section
rather than dropping it.

## 2. Shape

```
<target line — path, URL, or the command it will follow>

## Goal
<1–3 sentences: the end state>

## Must be true
<one line each: a behaviour, a number, a file that exists, a thing that must not change>

## How to work
<one line each: sources and their order, who to ask, when to stop and report, what to try
first, what to record where while working, the user's hunches>
```

Every line goes in exactly one of the two lists, by one test: **after the work is finished,
could someone check it without having watched the work being done?** Yes → *Must be true*.
No → *How to work*. "Session lasts 8 hours" is checkable afterwards; "check yesterday's logs
first" is not. "No new dependencies" is checkable; "ask before touching the schema" is not.

The first line of *Must be true* is the goal's end state, as a checkable fact — "CSV export
exists on the orders page", not only a sentence under *Goal*.

A sentence carrying both halves splits in two. "Write a reproducing test first, then fix" →
*a reproducing test exists* under *Must be true*, *write it before the fix* under *How to
work*. "Run the benchmark before and after and paste the numbers in the PR" → *the PR has
before and after numbers*, and *run it before and after*.

A hunch stays a hunch: "i think the n+1 is part of it but idk" becomes *"User suspects the N+1
in the product loader (unconfirmed)"* under *How to work* — never a task, never a requirement.

Rewriting rules:

- **Imperative, second person implied.** "Do NOT guess." not "The AI should avoid guessing."
- **One instruction per line.** Split compound sentences.
- **Negative constraints stay negative.** "Do not close a code because the implementation
  looks reasonable" is a guardrail; softening it to "close codes with evidence" loses it.
- **Keep the user's emphasis.** If they wrote it in caps, bold or repeated it, it stays loud.
- **Cut the rationale, keep the rule.** Explanations of *why* are the first thing to go.
- **No preamble, no praise, no "Sure, here is".** The block starts at the first instruction.

## 3. Budget

Default limit: **4000 characters** for the whole block. `--max N` overrides.

Count the block before emitting. Over budget, cut in this order:

1. Explanatory clauses and justifications
2. Examples that repeat an adjacent rule
3. Sub-bullets merged into their parent
4. Section headers merged (two thin sections → one)

Never cut a requirement to fit. If the requirements alone exceed the limit, emit them all and
say in one line after the block that the limit was exceeded and by how much.

## Language

**Mirror the input.** Vietnamese in → Vietnamese out; English in → English out; mixed → the
language of the majority of the instructions. `--en` / `--vi` override.

Never translate: file paths, folder names, filenames, code identifiers, command names,
product/system names, status labels the user quoted (`[Draft]`, `Q&A`, `PROGRESS.html`).

## Flags

| Flag | Effect |
| ---- | ------ |
| `--max N` | Character budget (default 4000) |
| `--for /cmd` | Put `/cmd` on the first line of the block, and shape for that command's style |
| `--en` / `--vi` | Force output language |

## 4. Second pass ⚠️ REQUIRED

Do not emit before this. Walk the *input* sentence by sentence and mark each one:

- **covered** — a line in the output carries it
- **dropped** — not in the output → restore it
- **invented** — a line in the output with no matching input sentence → delete it

A line that only restates the target, the goal, or a section header is not coverage of a
requirement. Rules named once in a throwaway clause ("nhớ update vào progress html nhé") are
requirements; casual phrasing does not make them optional.

Re-count characters after fixing.

## 5. Emit

Output exactly:

1. One fenced code block containing the normalized prompt, and nothing else.
2. One line after it: the character count, and any dropped-requirement warning.

No commentary on how it was rewritten. No offer to run it — the user asked for text.

## Anti-patterns

| Don't | Instead |
| ----- | ------- |
| Add "## Context", "## Background", "## Assumptions" the user never gave | Only sections whose content came from the input |
| Turn a rule into a polite suggestion ("consider checking…") | Keep the imperative force |
| Summarize a list of folders as "the relevant docs" | Keep every path, in the order given |
| Explain the rewrite before or after the block | One char-count line, nothing more |
| Translate `PROGRESS.html` or a path into the output language | Identifiers stay verbatim |
| Pad to look thorough when the input was 3 lines | A short input yields a short prompt |
| Open the target file to "understand it better" | Pure text transform — the target is not read |
