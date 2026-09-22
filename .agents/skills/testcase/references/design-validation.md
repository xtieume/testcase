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

Anything the gate blocks becomes `TBD — <what is needed>` for the designer or PM, per rule 5.
Do not invent requirements.

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

## The states a design rarely shows, and always needs

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

## Accessibility — run the tool, do not judge by eye

Each check below is a finding **only** when it comes from the source named. None of them can
be asserted from an image or from Figma: opacity, gradients, overlays and blur all defeat a
sampled colour, and focus, motion and heading order do not exist in a still frame at all.

| Check | Only from |
| ----- | --------- |
| Contrast ≥ 4.5:1 (3:1 large text, and non-text control boundaries) | axe-core / Lighthouse, or computed colours read from the DOM |
| Focus visible on every interactive element, both themes | The running page — keyboard through it |
| Hit target ≥ 24×24 px (≥ 44×44 primary touch) | Computed box from the DOM |
| Meaning not carried by colour alone | The design and the markup together |
| Heading order and landmarks | The DOM |
| `prefers-reduced-motion` respected | The CSS/JS source |

No tool wired up and no DOM access → report accessibility as **not verified**, and say so.
An accessibility finding invented from a screenshot costs a developer a day and costs you the
next report's credibility.

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

One row per discrepancy, in the same `testcases.md` table as everything else:

| Field | Content |
| ----- | ------- |
| Requirement | `D<n>` — the frame's node link and the requirement ID it maps to |
| Steps | How to reach that screen, with the data state that surfaces it |
| Expected | The design value **and its source**: node name, token name |
| Actual | The implemented value, and where it came from (hard-coded, wrong token) |
| Distinguishes from | The wrong implementation this catches — "hard-coded hex that only shows in dark mode" |

Severity comes from `bug-report.md`, with one addition: a purely visual difference no user can
act on wrongly is S4 — unless it breaks a contrast, focus or hit-target rule, which is S2
regardless of how small it looks.
