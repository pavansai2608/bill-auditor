# Design

Two screens, desktop-first, stacking to cards on mobile. `tokens.json` is the
source of every colour, size and space; `src/styles.css` mirrors those keys as
CSS variables and nothing in the components hardcodes a value.

> Stitch was not reachable from the workspace this was built in — see B-05 in
> `BLOCKED.md`. This document is the design specification it would have
> produced, written to the same brief, and the screenshots in `screenshots/`
> are of the built interface rather than of a mockup.

## Principles

The screen tells someone they are about to lose money. It has to read as
precise and honest rather than playful.

- **One accent** — teal `#0E7C7B`. Used for the primary action, focus rings and
  the clause chips. Nothing else competes with it.
- **Deduction is the emotional centre.** On the report, "deducted" is set at the
  display size (3rem) in the deduct colour; charged and payable sit beside it at
  a third of that weight. The eye lands on the number that matters.
- **Flagged is amber, not red.** A flagged line is not an error — it is the
  system refusing to guess. Amber tint, amber left border, plain language.
  Red is reserved for the deducted figure.
- **No gradients, no hero image, no marketing voice.**

## Type scale

| Token | Size | Used for |
|---|---|---|
| `display` | 3rem | the deducted figure |
| `figure` | 2rem | the other summary figures |
| `title` | 1.75rem | screen heading |
| `heading` | 1.375rem | panel heading |
| `lead` | 1.0625rem | the one-line explainer |
| `body` | 0.9375rem | everything else |
| `small` | 0.8125rem | reasons, helper text |
| `caption` | 0.75rem | labels, table headers |

## Spacing

A 4px base: 4, 8, 12, 16, 24, 32, 48, 64. Panels use `space-5` (24px) padding,
sections are separated by `space-6` (32px).

## Screen 1 — Audit a bill

```
┌──────────────────────────────────────────────────────┐
│ Bill Auditor                                          │
│ Check a hospital bill against the policy that pays it │  <- one-line explainer
├──────────────────────────────────────────────────────┤
│ ┌── Your bill ─────────────────────────────────────┐ │
│ │  [ dropzone: drag a bill, or choose a file ]     │ │
│ │  or paste it instead  ->  [ textarea ]           │ │  <- toggle, not both
│ └──────────────────────────────────────────────────┘ │
│ ┌── Your policy ───────────────────────────────────┐ │
│ │  Insurer [v]        Sum insured [v]              │ │
│ │  Policy start [date]   Admission [date]          │ │
│ │  Room limit per day (optional)  [        ]       │ │
│ │  Leaving this blank is fine — the audit will say  │ │
│ │  so rather than assume a limit.                   │ │
│ └──────────────────────────────────────────────────┘ │
│                                  [ Audit this bill ]  │
└──────────────────────────────────────────────────────┘
```

- The dropzone and the textarea are a toggle, so it is never ambiguous which
  one will be sent.
- The insurer list includes "upload my own policy", which reveals a PDF picker
  and posts to `POST /policies/upload`.
- Sum insured options come from the API per policy, because star_health prices
  its room limit by sum insured and the others do not.
- The optional room limit carries its helper text permanently, not on hover.

## Screen 2 — Audit report

```
┌──────────────────────────────────────────────────────┐
│  CHARGED        DEDUCTED          PAYABLE   FLAGGED   │
│  ₹2,40,000      ₹1,46,000         ₹94,000   1 line    │  <- deducted is 3rem
├──────────────────────────────────────────────────────┤
│  Assumptions (always visible, never behind a toggle)  │
│  • assumed the hospital follows differential billing  │
│    because … clause II.1                              │
├──────────────────────────────────────────────────────┤
│  item            charged   allowed   clause   why     │
│  room rent       40,000    25,000    II.1     …   [v] │  <- row expands
│  syringes        1,200     flagged   —        …   [v] │  <- amber
├──────────────────────────────────────────────────────┤
│  [ Compare with other policies ]   [ Download CSV ]   │
└──────────────────────────────────────────────────────┘
```

- Every row expands to a trace panel showing the nodes that decided that line:
  which queries ran, what was retrieved, what the judge said, what the
  guardrails did.
- The clause id is a chip in the accent colour. It is the whole point of the
  product, so it is never truncated.

## States

| State | What it looks like |
|---|---|
| Empty | Screen 1 with the explainer line and a disabled submit until a bill is present |
| Loading | Skeleton summary band and six shimmering table rows, plus "checked 3 of 7 lines" and a progress bar |
| Error | A panel in the flag colour with the API's own message, and a "start again" button. Never a bare stack trace |
| Timed out | After five minutes: "the model has probably stopped responding — check that Ollama is up" |

## Accessibility

- Every control has a visible `<label>`; the room-limit helper text is tied to
  its input with `aria-describedby`.
- The table is a real `<table>` with `<caption>`, `scope="col"` headers, and
  `aria-expanded` on the row toggles.
- Focus is a 2px accent ring with a 2px offset, never removed.
- Progress uses `role="progressbar"` with `aria-valuenow`/`aria-valuemax`, and
  the status line is an `aria-live="polite"` region so a screen reader hears
  each update.
- Under 760px the table becomes stacked cards, each cell labelled by its column
  name through a `data-label` attribute.
