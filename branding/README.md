# CookDex brand assets

The mark is a chef's toque resting on an open recipe book. Every file here is a
flat vector exported from the CookDex Brand Figma file, which holds the full
style guide: logo usage, color, type, and spacing. Change the logo in Figma and
re-export it. Don't edit these SVGs by hand.

## Logo

| File | Use |
| --- | --- |
| `cookdex-lockup.svg` | Default logo: README, docs header, light backgrounds |
| `cookdex-lockup-dark.svg` | Same lockup for dark backgrounds |
| `cookdex-lockup-stacked.svg` | Square placements, splash screens |
| `cookdex-mark.svg` | The mark alone, full color |
| `cookdex-mark-mono.svg` | One-color mark (ink) |
| `cookdex-mark-white.svg` | White mark for ember or photo backgrounds |
| `cookdex-wordmark.svg`, `cookdex-wordmark-dark.svg` | Wordmark without the mark |
| `cookdex-app-icon.svg` | Ember app tile; source for the favicons in `web/public` |
| `cookdex-social-preview.png` | 1280×640 GitHub social preview |

In the web app the logo is the `BrandLockup` / `BrandMark` component in
`web/src/components/BrandLogo.jsx`. It is inline SVG, so "Cook" follows
`--text` in both themes.

Rules of thumb:

- Keep clear space of at least ¼ of the mark's width around it.
- The mark works down to 16px. Below 24px use the app icon tile.
- Never add glows, gradients, or shadows. Never recolor it outside the palette,
  stretch it, or rotate it.

## Color

`web/src/styles/tokens.css` is the source of truth for colors; the Figma
variables mirror it, with matching CSS names in each variable's code syntax.

- **Ember** `#F47A2A`: the one loud color, used for the mark, focus rings, progress
  bars, and toggles. It is 2.7:1 against white, so it never carries text and is never
  used for text on light surfaces. Use `--accent-strong` (`#C44E1F`, 4.7:1 on white)
  for orange text on light surfaces.
- **Buttons and other fills behind white text** (the selected nav item, chips) use
  `--accent-fill` (ember 700, `#C44E1F`, white text 4.7:1) in both themes, and
  `--accent-fill-hover` (ember 800) on hover.
- **Paper** `#FFF6EC` and **Ink** `#2B2B2B` in light mode; **Cast iron**
  `#171412` and `#F4EEE8` in dark mode.
- Status hues come from the pantry: tomato (danger), saffron (warning),
  basil (success), honey (running).

## Type

- **Bricolage Grotesque** ExtraBold, −3% tracking: the wordmark and display headlines.
- **Inter**: all interface text.
- **Cascadia Code**: logs, paths, and tokens.

The web app bundles all three (the `@fontsource` packages), so nothing is fetched
from a font CDN. Use `var(--font-sans)`, `var(--font-display)` and `var(--font-mono)`
from `web/src/styles/tokens.css`; page titles are Bricolage Grotesque Bold.

In CSS, use the semantic color tokens rather than hex values. The one exception
is the run log, which is always dark and uses the cast-iron and pantry-dark values
directly.

## Voice

Calm, not clever. Exact, not technical. Warm, not cute. Name the recipe, the tag,
and the count, and say what a job will change before it runs.
