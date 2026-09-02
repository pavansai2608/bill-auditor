# The landing page design

## Stitch was not available

The brief asked for this to be designed in Stitch first. **No Stitch MCP server
is connected to this repository**, so none of it came from Stitch. The only
design server available is `DesignSync` (claude.ai/design), which is a
different product and syncs a component library rather than generating a page.
This is the same wall as **B-05** in `BLOCKED.md`, which recorded Stitch as
unavailable during Phase 9 as well.

So the page was designed directly against the tokens already in the repo. If
Stitch is connected later, the thing to compare against is `tokens.json` one
directory up - not this file.

## Which palette was kept, and why

**One palette, extended - not a second one.** `frontend/design/tokens.json`
stays the single source for every screen. The visual pass that brought in the
serif and the paper ground added six tokens **to that file**, and `styles.css`
mirrors each: `--colour-paper` `#FAF9F7`, `--colour-paper-raised`,
`--colour-paper-sunken`, `--colour-hairline` (10%) and `--colour-hairline-strong`
(16%), plus `--font-display`, `--text-display-lg`, `--text-display-md` and
`--motion-reveal`. The accent, the ink, the spacing steps and the radii are
untouched. `landing.css` contains no `var(--x, fallback)` at all - every value
resolves to a token or it does not render.

**Ground: warm paper, not dark.** Both grounds were on the table. The audit
screen is one click away and is light; a dark landing would make pressing the
button feel like leaving the product, and the page still has to read as
something a hospital or a regulator could have published. Paper plus a serif
gets the considered look without that break.

**Type.** Instrument Serif for display, Inter for body, from Google Fonts with
Georgia and the system sans as real fallbacks. Loaded with a `<link>` in
`index.html` rather than `@import`, so the request starts with the document.
Note the consequence: a machine with no network gets Georgia. Everything else
in the container is self-contained.

**The audit screen now inherits all of it** - same ground, same display serif
on its heading, same hairlines - and its two heavy white cards are gone. A form
is one thing a person works down; a box around each half made it read as two.

Two divergences between `tokens.json` and the stylesheet were found on the way
and closed rather than left:

- `--leading-tight` and its two siblings are in `tokens.json` but had never
  been written into `styles.css`, so `var(--leading-tight, 1.15)` was silently
  using its own fallback and the file that claims to mirror the tokens
  "one-for-one" did not. The three variables are now in the stylesheet, and the
  hero uses the token's 1.2.
- The landing page's own fallbacks are gone, so a missing token now shows up as
  a broken style instead of a plausible-looking guess.

## Motion

Sections rise 14px and fade in the first time they are seen, 520ms, staggered
70ms within a section, and never again - a reader scrolling back up has already
seen it. The room-rent figure counts up when the example enters.
`prefers-reduced-motion` gets the final state immediately, in the hook and
independently in the stylesheet.

One thing this got wrong first, worth keeping written down: the hidden state
lived in plain CSS, so any section the observer had not reached rendered as
nothing at all. Content withheld pending JavaScript is content lost when
JavaScript does not run. Only an element the hook has **armed** hides now.

## The one deliberate departure

`.landing-cta` is **52px** tall, where `--control-height` is 42px. A landing
page has exactly one thing to press and it is the only interactive element
above the fold; the audit form has a dozen controls that should not shout. It
is a size, not a colour, and it now lives in `tokens.json` as
`layout.cta-height` with the rest.

## What the page is made of

| Section | Why it is where it is |
| --- | --- |
| Hero | One sentence on what it does, one on why it matters, one button. No email capture. |
| The worked example | Second, because a real bill with real figures answers "what is this" faster than a paragraph. It carries an expanded deduction with the clause and the arithmetic. |
| How it works | Four steps, one line each. The third says the model never does arithmetic, because that is the design decision the rest depends on. |
| What it does not do | Fourth, and the reason to believe the other four. Cashless denials, settlement delays, treatment disputes, hospital rates. |
| Results | Every row carries its bill count. |
| Footer | Repo link, and that it is a personal project and not advice. |

## Every number on the page is real

- The worked example is an actual audit of `eval/bills/B01.json` through the
  running stack: room rent Rs 40,000 charged, Rs 25,000 allowed under
  `star_health II.1`, surgical gloves nil under `IRDAI-List-I`, medicines paid
  in full, disposable syringes flagged.
- The results table is read from `eval/results.md`.

Two things about that table, both deliberate:

- **There are no v1, v2 or v3 rows because `results.md` has none.** It holds
  five sections - v0, v4, v5 and v5-full twice. The v2 51.2% and v3 54.9%
  figures quoted in `CLAUDE.md` are not in the results file, so they are not on
  the page.
- **Both v5 rows are shown**, the ten-bill run at 68.3% and the full 44-bill
  run at 59.5%, each labelled with its bill count. Showing only 68.3% while a
  full run says 59.5% would be the kind of quiet dishonesty the "what it does
  not do" section exists to rule out.

## The audit screen's usability pass

Visual parity was half of it. The rest:

- **"Try it with an example"** loads B01 from the eval set and fills every
  matching field. A first-time visitor had nothing to paste and no idea what a
  valid bill looked like. `frontend/src/lib/exampleBill.ts` is generated from
  the fixture and `tests/test_example_bill.py` fails if the two drift.
- **The submit button says why it is disabled**, live, under itself.
- **The room limit help** is one line plus a "why?" that expands.
- **A start date after the admission date is caught in the form**, not by the
  backend, where it would come back as a nonsense audit rather than a typo.
- **What was sent stays on screen** while the audit runs, one line, expandable.
  The form used to vanish, leaving no way to answer "what did I give it?"
- **The dropzone is the control.** The native file input is stretched invisibly
  across the whole area, so there is no "No file chosen" and no small grey
  button.

## Dark variant

Not built. The app has no dark mode, and shipping one on the landing page alone
would give the product two different answers to the same question. If it is
wanted, it belongs in `tokens.json` as a second set of colour values behind
`prefers-color-scheme`, applied to both screens at once.

## Accessibility

Heading order runs `h1` once in the hero, `h2` per section, `h3` inside. A skip
link precedes the masthead. Both tables carry a caption and `scope` on every
header. The single decorative mark is `aria-hidden`. Focus is a 2px accent
outline with an offset, never removed. There are no images, so there is no alt
text to get wrong - the bill is real text in a `<pre>` with a label.

## Screenshots

`frontend/design/screenshots/screen-0-landing-1440.png` and `-390.png`,
captured from the built container by `tests/e2e/capture_screenshots.py`.
