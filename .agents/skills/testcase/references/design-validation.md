# Design validation (Figma / mockup vs implementation)

Read when the requirement is a design — a Figma link, an exported mockup, or a screenshot —
and the question is whether the build matches it.

## The rule

**A design is a requirement like any other: every discrepancy becomes a row in the table, not
a bullet in a chat message.** The output of this pass is test cases carrying their own
requirement IDs (`D1`, `D2`, …), so a visual gap is tracked, re-run and closed the same way a
functional one is.

## What the design is authoritative for

Design authority stops at what the designer actually decided. Beyond that line the
implementation is not wrong, and filing it wastes everyone's afternoon.

| Authoritative | Not authoritative |
| ------------- | ----------------- |
| Spacing, size, color, type scale, radius, elevation — **as tokens** | The exact pixel of a rendered glyph |
| Copy, labels, empty/error/loading text | Placeholder or lorem text left in the frame |
| Which component, which variant, which state | A one-off frame detached from the component |
| States the designer drew (hover, focus, disabled, error) | States the designer never drew — those are questions, not bugs |
| Layout order, grouping, responsive frames provided | Widths between two provided breakpoints |

A frame is a snapshot of one data set. Never read a fixed number from it as a rule: a card
showing "12 items" is not a requirement that the card holds 12.

## Compare tokens, not pixels

Pull the values from the design (Figma MCP, dev mode, or the exported spec) and compare them
against the implementation's **own** tokens — the CSS variable, theme entry or constant.

A hard-coded `#3B82F6` that renders identically to `--color-primary` is still a finding: it
breaks the moment the theme changes, and it is invisible to a screenshot diff. Comparing
rendered screenshots finds the differences that do not matter and misses this one.

Check in this order, stopping at the first that fails — a wrong component makes every
downstream measurement meaningless:

1. **Component identity** — same component and variant from the design system, or a
   re-implementation of it?
2. **Token binding** — values reference tokens, and the same tokens the design used?
3. **Structure** — order, grouping, hierarchy of the elements.
4. **Spacing and size** — gap, padding, dimensions, against the design's spacing scale.
5. **Typography** — family, size, weight, line-height, letter-spacing.
6. **Color** — fill, text, border, in **both** light and dark mode.

## The states a design rarely shows, and always needs

Walk these explicitly; they are where implementation and design diverge without anyone
noticing, because the frame only ever showed the full, happy, English, mid-width case:

- **Empty** — zero rows, no avatar, no results.
- **Loading** — skeleton, spinner, or nothing at all (which is itself a finding).
- **Error** — failed fetch, validation, permission denied.
- **Overflow** — the longest realistic string, a 3-line title, a 10-digit number, a
  translation 2× the English length, an unbroken 60-character token.
- **Interaction** — hover, focus-visible, active, disabled, selected.
- **Responsive** — each breakpoint the design provides, plus the narrowest supported width.
- **Theme** — dark mode, if the product has one.

Any of these the design does not cover is a `TBD` for the designer (rule 5), not a bug and not
a guess.

## Accessibility is part of the match

The design does not override these, and "the mockup looks like that" is not a resolution:

- Text contrast ≥ 4.5:1 (≥ 3:1 for large text), and for the non-text boundary of controls.
- Focus visible on every interactive element, on both themes.
- Hit target ≥ 24×24 CSS px, and ≥ 44×44 for primary touch targets.
- Meaning never carried by color alone — an error state needs text or an icon too.
- Heading order and landmarks reflect the visual hierarchy.
- Motion respects `prefers-reduced-motion`.

## Writing it up

One row per discrepancy, in the same table as everything else:

| Field | Content |
| ----- | ------- |
| Requirement | `D<n>` — the design element and frame |
| Steps | How to reach that screen, with the data state that surfaces it |
| Expected | The design value **and its source**: node/frame name, token name |
| Actual | The implemented value, and where it comes from (hard-coded, wrong token) |
| Distinguishes from | The wrong implementation this catches — e.g. "hard-coded hex that only shows in dark mode" |

Severity comes from `bug-report.md`, with one addition: a purely visual difference that no
user can act on wrongly is S4 — unless it breaks a contrast, focus or hit-target rule above,
which is S2 regardless of how small it looks.
