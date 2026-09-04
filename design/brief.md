# Research Radar — Design Brief (locked)

Source of truth for all Section 4 subagents. Read this file plus
`frontend/tailwind.config.ts` first. Do not invent colors, radii,
shadows, or type values outside the token file. Do not change logic
(see instructions Section 0).

## 1. Subject, audience, anchor

- **Subject:** paper discovery and scanning for CV + LLM research.
- **Audience:** researchers and engineers scanning titles, authors,
  years, citations, and similarity scores at speed.
- **Job:** dense, fast scanning with tool-like credibility. Not marketing.
- **Anchor:** citation ledger. Ruled index rows with rank numerals,
  journal typesetting, tabular figures. Ranked results are a true
  sequence, so numerals encode rank. One radar motif only: a thin
  scan rule in the home header, nowhere else.

## 2. Tokens (locked in `frontend/tailwind.config.ts`)

| Token | Value | Use |
|---|---|---|
| `paper` | `#F7F6F1` | Page ground |
| `paper-deep` | `#ECEAE2` | Row hover wash, wells |
| `ink` | `#1B2431` | Text, wordmark |
| `signal` | `#8C2B2B` | Single accent: saved star, active states, rank numerals |
| `signal-dark` | `#732222` | Accent hover/pressed |
| `sage` | `#5F6E64` | Secondary meta text, quiet labels |
| `rule` | `#DFDCD2` | Hairline dividers and borders |

- No other hues. No gradients as decoration. No shadows for
  hierarchy — hairlines do the structural work. Radius survives
  only on controls, badges, and pills (small), never as the
  row system itself.

## 3. Type roles

- **Display — Newsreader (serif):** wordmark, detail title,
  abstract. Serif body leading `1.7`, measure capped near `68ch`.
- **Body/UI — Inter (grotesk):** result rows, controls, meta.
  Body leading `1.55`. Years, counts, scores always `tnum`
  (tabular figures). Never monospace for data.
- **Scale (px):** `12` meta, `14` body, `16` row title,
  `20` section head, `30` detail title, `34` wordmark.
- **Voice:** sentence case, plain verbs, active voice. Name
  actions by outcome (`Export saved`, not `Submit`). Errors name
  the failure plus the fix. Empty screens invite the next action.

## 4. Layout grid

- Single left-aligned column everywhere, ragged right.
  Home `max-w-5xl`, detail `max-w-4xl`. Numbers right-tabulated
  in rows. Only the 404 centers.
- Home order: compact header (logo mark, wordmark, one-line
  subhead, scan rule), instrument strip (search, year, topic,
  author, three checkboxes, clear), count line, ruled rows,
  pagination. Export/import lives in the strip, quiet.
- Detail order: back link, title + year + bookmark ledger line,
  authors, citation + topic ledger line, publisher link,
  abstract, similar rows.
- Breakpoints to verify: `375`, `768`, `1440`.

## 5. Row-collapse behavior at 375px (B and D build identically)

This is the shared contract for result rows (Subagent B,
`PaperCard`) and similar-paper rows (Subagent D, detail page).
Both render the same collapse so the ledger reads as one system.

- **≥768px (full row):** one flex row —
  `[rank 2ch, signal, tnum]` left, `[title + meta stacked,
  flex-1, min-w-0]` center, `[star button]` + `[year badge /
  score badge]` right cluster. Meta line is a single truncated
  line: authors, then year, then citations. Badges keep pill
  shape. Star hit area minimum `44px` via padding.
- **375px (collapsed):** the row becomes a two-line block.
  Line 1: rank (inline, `12px`, signal, tnum) + title
  (flex-1, 2-line clamp) + star pinned right. Line 2: meta
  (`12px`, sage, single truncate line): authors, then year,
  then citations for result rows; title-adjacent score stays
  right on line 1 for similar rows. The year pill flattens
  into plain meta text — no pill shape below `480px`.
- **Never:** no horizontal scroll at any width; numerals stay
  tabular so columns do not jitter; star never wraps below
  the meta line; truncation is visual only (full text stays
  in the DOM with `title` attr).

```
≥768px
| 01  Attention Is All You Need              ★  [2017] |
|     Vaswani et al. · 6,659 citations                 |

375px
| 01 Attention Is All You Need                 ★       |
|    Vaswani et al. · 2017 · 6,659 citations           |
```

## 6. Shared states (defined once, used by all)

- **Hover:** rows wash `paper-deep`. No lift, no shadow bloom,
  no fade-and-slide entrances.
- **Focus-visible:** `2px` signal ring, `2px` offset, global
  (`globals.css` base). Never remove outlines without this.
- **Disabled:** `opacity-40`, `cursor-not-allowed` (Prev/Next,
  empty-page controls).
- **Active/selected:** checked ranked/hybrid boxes use
  `accent-signal`; active `Saved` filter is a signal-filled
  chip with white text; current page number is signal-filled.
- **Skeleton:** `.skeleton` shimmer from `globals.css`. The one
  deliberate load moment. Disabled under reduced motion.
- **Error:** ink panel copy naming the failure plus the fix;
  signal only on the failing field edge. No all-red boxes.
- **Empty:** centered, sage, directional: name what is empty
  plus the exact next action (`Clear q to see all N saved`).

## 7. Motion policy

- Max one deliberate page-load moment: skeleton shimmer.
- Motion that answers an action is allowed: bookmark fill
  confirms the save. Nothing else animates. No per-card
  hover fades, no scroll reveals.

## 8. A11y floor

- Visible focus everywhere (global ring). Full keyboard path:
  search, filters, cards, bookmark, pagination, detail, back.
- `aria-live="polite"` on the count line. `aria-pressed` on
  the save toggle. `aria-current="page"` on the current page
  number. `aria-label` on Prev/Next. Ellipsis `aria-hidden`.
- Contrast: ink on paper, signal on paper, sage only for
  secondary text at `12px`+ (verify). Reduced motion respected.

## 9. Do / don't (vs Section 1 tells)

- Do rows with rules and numerals. Don't ship uniform
  `rounded-lg` + `shadow-sm` cards.
- Do ink/oxblood/sage/rule. Don't reach for indigo+emerald,
  cream+terracotta, or near-black+neon.
- Do Newsreader + Inter with tabular figures. Don't use the
  default sans stack or monospace data labels.
- Do directional empty/error copy. Don't ship gray shrugs or
  red boxes.
- Do left-aligned density. Don't center content except 404.
- Don't add ALL-CAPS eyebrows, dot-joined meta, em-dash
  labels, or arrow-suffixed links.
