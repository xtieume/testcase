# Design validation (Figma / mockup vs implementation)

Read when the requirement is a design — a Figma link, an exported mockup, or a screenshot —
and the question is whether the build matches it.

## The rule

**A design is a requirement only when it is named, versioned, approved and mapped.** A Figma
file also holds exploration, abandoned variants, stale components, placeholder copy,
annotations designers wrote to each other, and states nobody signed off. Everything else in
it is reference material.

Validating against the wrong frame does not produce a missed finding — it produces confident
noise: a `D3` row sent to a developer, traceable and lint-clean, for a decision nobody made.

## Gate: authority and access

Establish all of this **before comparing anything**. The pass does not run on assumption.

| Establish | Missing → |
| --------- | --------- |
| The exact node — a link to the frame, not to the file | Ask which frame. Do not pick one |
| Version: named version, branch, or last-modified vs the build under test | Frame newer than the build means comparing against a future. Stop |
| Approval — who signed off, and where (ticket, Figma comment, "Ready for dev") | The pass emits questions, not findings |
| Mapping: frame ↔ requirement ID | An unmapped frame is not a requirement |
| Page convention — Exploration / WIP / Archive pages | Out of scope by default |
| Annotations and redlines: requirement, or a note between designers? | Ask. Never interpret |
| Access to the values: Figma MCP, Dev Mode, or an exported spec | See below |
| Access to the implementation's source (tokens, CSS, DOM) | See below |

**Values are read, never estimated.** Every number in a finding comes from the design's own
spec and from the implementation's own source. A value inferred from an image — a hex sampled
from a screenshot, a gap measured in pixels — is a guess: anti-aliasing, colour profile,
compression and retina downscaling all move it, and `#3B82F6` reads back as `#4189F0`.

With only a screenshot and no access, this pass produces **structural findings only** —
missing element, wrong order, wrong state, obviously wrong component — and says in the report
that values were not verifiable. Never a finding about a number you did not read.

The eight are not equal. Treat them in three tiers, or the gate blocks the common case and
gets routed around:

- **Blocks** — no exact node, or the frame sits on an Exploration/WIP/Archive page. Nothing
  below it means anything. Stop and ask.
- **Downgrades** — no approval, or no version to compare against. The pass runs, every finding
  is marked `provisional`, and the report says the frame was not confirmed as a decision.
- **Limits** — no MCP/Dev Mode/spec, or no source access. Structural findings only, values
  reported as unverifiable.

Anything blocked becomes `TBD — <what is needed>` for the designer or PM, per rule 5. Do not
invent requirements.

## When the design and the written spec disagree

Both approved and contradicting each other is the normal case, not an edge case. Do not pick
one.

- The **written spec wins by default** for behaviour, rules, data and permissions; the design
  wins for presentation. A frame showing a button a Viewer should not have is a design that
  was not updated, not a new permission rule.
- Where they collide on the same axis, the pass produces **one `TBD` naming both sources and
  their dates**, and no `D<n>` finding. Whoever owns the requirement decides; you record which
  they chose.
- A design that is newer than the spec is not automatically the newer decision — designs are
  edited without review. Date is evidence, not authority.

## What an approved frame is authoritative for

| Authoritative | Not authoritative |
| ------------- | ----------------- |
| Spacing, size, colour, type scale, radius, elevation — **as tokens** | The exact pixel of a rendered glyph |
| Copy, labels, empty/error/loading text | Placeholder or lorem text left in the frame |
| Which component, which variant, which state | A one-off frame detached from the component |
| States the designer drew (hover, focus, disabled, error) | States never drawn — those are questions, not bugs |
| Layout order, grouping, responsive frames provided | Widths between two provided breakpoints |

A frame is a snapshot of one data set. Never read a fixed number from it as a rule: a card
showing "12 items" is not a requirement that the card holds 12.

## Compare tokens, not pixels

Compare the design's values against the implementation's **own** tokens — the CSS variable,
theme entry or constant in the source.

A hard-coded `#3B82F6` that renders identically to `--color-primary` is still a finding: it
breaks the moment the theme changes, and no screenshot diff can see it.

Check in this order, stopping at the first failure — a wrong component makes every downstream
measurement meaningless:

1. **Component identity** — the design system's component and variant, or a re-implementation?
2. **Token binding** — values reference tokens, and the same tokens the design used?
3. **Structure** — order, grouping, hierarchy.
4. **Spacing and size** — against the design's spacing scale.
5. **Typography** — family, size, weight, line-height, letter-spacing.
6. **Colour** — fill, text, border, in **both** light and dark mode.

## The states a design rarely shows

These are **questions to put to the designer**, not a list to file findings against. A state
the product does not have is not a gap: absent a requirement asking for it, "no dark mode on
this screen" is an observation, not a defect. File one only where the requirement, the design
or the code shows the state is meant to exist.

The frame only ever showed the full, happy, English, mid-width case:

- **Empty** — zero rows, no avatar, no results.
- **Loading** — skeleton, spinner, or nothing at all (itself a finding).
- **Error** — failed fetch, validation, permission denied.
- **Overflow** — the longest realistic string, a 3-line title, a 10-digit number, a
  translation 2× the English length, an unbroken 60-character token.
- **Interaction** — hover, focus-visible, active, disabled, selected.
- **Responsive** — each breakpoint provided, plus the narrowest supported width.
- **Theme** — dark mode, if the product has one.

Any of these the design does not cover is a `TBD` for the designer, not a bug and not a guess.

**A real defect in the code you are reading is still reported, even when it is not a design
discrepancy.** Scope keeps you from inventing findings; it does not make you walk past a
crash. A missing import in the file you opened to compare tokens goes in the report.

## Accessibility — from the tool, never by eye

Opacity, gradients and blur defeat a sampled colour; focus, motion and heading order do not
exist in a still frame. Each check is a finding **only** from its source:

| Check | Only from |
| ----- | --------- |
| Contrast, hit target, heading order, landmarks | axe-core / Lighthouse, or the DOM |
| Focus visible, both themes | The running page — keyboard through it |
| `prefers-reduced-motion` | The CSS/JS source |
| Meaning not by colour alone | Design and markup together |

No tool and no DOM → report accessibility **not verified**. An invented contrast finding costs
a developer a day and costs you the next report's credibility. **Native** (React Native,
SwiftUI, Compose) is not exempt: read the accessibility tree or the framework's own props.

## Use the real tool where one exists

This pass is judgement, not measurement. Where a tool measures, the tool wins:

| For | Use |
| --- | --- |
| Pixel regression between builds | Playwright visual comparisons, Percy, Chromatic |
| Accessibility audit | axe-core, Lighthouse, Pa11y |
| Design ↔ code token diff | Figma Dev Mode, the design system's own token export |

What no tool decides, and this pass does: whether a discrepancy is a decision or a defect,
where design authority stops, which unfired states the design never answered, and whether the
frame was a requirement at all.

## Writing it up

Use the step-3 table, all ten columns, `Req` = `D<n>`. A five-column "design table" does not
parse. Keep the node link beside the `D<n>` list, not in the cell.

**Categorise by what the case exercises, not by "it is visual".** `summarize.py` counts only
`Negative / Boundary / Validation / Error / Permission` as risk coverage — `State` and `UI` do
not. So an empty state is `Boundary` (zero is a boundary), a failed fetch is `Error`, an
element only some roles see is `Permission`. A `D<n>` with genuinely no risk case takes a
`coverage-ok` comment naming the reason.

A contrast, focus or hit-target failure is never cosmetic, however small it looks.
