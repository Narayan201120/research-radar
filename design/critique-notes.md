# Research Radar — Critique Notes (redesign pass 1)

## What was tried

- Ruled ledger rows with rank numerals replaced the uniform card grid
  on home and detail similar lists. Numerals are signal + tabular;
  they encode rank, which is real sequence information.
- Citation-ledger anchor: Newsreader display + Inter body, ink /
  oxblood / sage / rule palette, hairlines instead of shadows.
- Single radar motif: thin scan rule with signal tick in the home
  header, nowhere else.
- Abstract promoted to premier reading surface (serif, ~68ch,
  leading 1.7). Topic pills flattened to outline pills.
- Publisher link de-suffixed (plain signal text, no arrow).
- Import file trigger converted from `span[role=button]` in a
  label to a real `<button>` plus hidden input.
- New `app/loading.tsx` + `app/papers/[id]/loading.tsx` skeletons
  using the single shimmer utility (reduced-motion safe).
- Pagination moved left-aligned with `aria-current`, labeled
  Prev/Next, hidden ellipsis.

## What was cut (restraint rule)

- Card shadows and per-card radius (whole system).
- Emerald topic fills (outline pills instead).
- The `↗` on the publisher link.
- A second radar motif on the detail page (header rule only).
- Entrance animations and card hover fades (hover is a flat
  `paper-deep` wash only).
- A third typeface for scores (tabular Inter instead).

## Integration fixes by lead

- `app/page.tsx` shell still had `bg-slate-50` — re-tokened to
  `bg-paper text-ink` (only hardcoded palette drift found).
- Wired `rank={(page-1)*PAGE_SIZE + idx + 1}` into `PaperCard`
  (Subagent B added the prop, Subagent A did not know it).
- No CSS specificity collisions possible: base layer holds only
  `body`, `::selection`, `:focus-visible`, `.tnum`, `.skeleton`.

## Screenshots (captured, `design/screenshots/`)

- `home-1440.png`, `home-375.png`, `detail-1440.png`,
  `detail-375.png` — headless Chrome against live `localhost`.
- True-375 renders were verified via puppeteer viewport plus
  DOM measurement (`scrollWidth == innerWidth == 375`, 20 star
  buttons present). The 375 collapse matches `brief.md` §5:
  rank + title + star on line 1, meta with flattened year on
  line 2, no horizontal scroll.
- Tooling note: Chrome CLI `--window-size=375` screenshots
  showed false overflow (old/new headless enforce a wider
  minimum window, then crop). Trust puppeteer viewports, not
  CLI flags, for narrow widths.

## Open items for a future pass

- Remaining states not yet shot: loading, empty-saved,
  empty-filtered, error, history-visible, null-abstract,
  similar-failed, 404. Same puppeteer setup works.
- 768px breakpoint not yet shot.
- Contrast check on `sage #5F6E64` at 12px should be metered;
  it is secondary-only by construction, but verify.
- `Clear filters`, `Export`, pagination numbers have hover
  but no explicit `:focus-visible` beyond the global ring —
  confirm the global ring is visible on the filled signal chip.
- History pills show full title only via tooltip; consider a
  wrapping variant if long titles dominate.
- Logo mark (`logo-mark.svg`) still carries the old blue/ink
  artwork — a ledger-redrawn mark would complete the identity.
