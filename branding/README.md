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

- **Ember** `#F47A2A`: the one loud color, used for brand, primary actions, and focus.
  It is 2.7:1 on white, so it is never used for body text. Use `--accent-strong`
  (`#C44E1F`, 4.7:1 on white) for orange text on light surfaces.
- **Paper** `#FFF6EC` and **Ink** `#2B2B2B` in light mode; **Cast iron**
  `#171412` and `#F4EEE8` in dark mode.
- Status hues come from the pantry: tomato (danger), saffron (warning),
  basil (success), honey (running).

## Type

- **Bricolage Grotesque** ExtraBold, −3% tracking: the wordmark and display headlines.
- **Inter**: all interface text.
- **Cascadia Code**: logs, paths, and tokens.

## Voice

Calm, not clever. Exact, not technical. Warm, not cute. Name the recipe, the tag,
and the count, and say what a job will change before it runs.
