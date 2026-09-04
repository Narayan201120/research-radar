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

## P5_2-b close-out (2026-09-04)

- Contrast metered: `sage #5F6E64` on `paper #F7F6F1` = 4.97
  (AA pass for normal text). Two 12px action labels
  (`Clear history`, history pills) defaulted to ink anyway —
  interactive text is never quieter than its neighbors.
- Logo redrawn from owner draft `new_logo/logo-v3.svg`:
  palette remapped to tokens (depth filters kept per owner),
  wordmark solid ink Newsreader, descriptor `Every paper, on
  the record.` in sage sentence case. Mark-only cut drops
  the tick ring + inner ring for 32px legibility.
- Favicon note: `logo.png` is a 1600x500 lockup canvas with
  transparent margins (matches old file size contract) —
  suboptimal as a tab icon; a square 180px icon is a
  follow-up if wanted.
- Screenshots now cover: home/detail at 1440 + true-375,
  empty-filtered, empty-saved, error (real app box via
  API-only abort), history-visible (with resolved titles),
  null-abstract (paper 10), 404, home/detail at 768.
- Honestly skipped: `loading` (home SSR streams instantly,
  skeleton never paints — keep the files for slow nets and
  detail navigation), `similar-failed` (server-rendered, so
  its failure UI is byte-identical to the empty case —
  any shot would mislead).
- Bug found by the sweep and fixed: history pills never
  resolved in real browsers because the resolver used
  server-side `fetchPaper` (`http://backend:8000` never
  ships to clients). New `fetchPaperClient` on the public
  base URL; detail page keeps server `fetchPaper`.

## Open items for a future pass

- `Clear filters`, `Export`, pagination numbers have hover
  but no explicit `:focus-visible` beyond the global ring —
  confirm the global ring is visible on the filled signal chip.
- History pills show full title only via tooltip; consider a
  wrapping variant if long titles dominate.
- Square favicon variant (see note above).
