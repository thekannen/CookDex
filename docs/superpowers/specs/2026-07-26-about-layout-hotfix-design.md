# About Layout Hotfix Design

## Goal

Remove the large empty gap on the About page that appears when the four cards
flow through a three-column CSS grid.

## Root Cause

The About page currently places every card directly into one auto-fitting grid.
At widths that produce three columns, the tall **Privacy & Data** card sets the
height of the first grid row. **Project Links** then starts in the second row
after that height, leaving a large empty area below the shorter CookDex card.

## Approved Layout

At desktop widths, use three independent columns:

1. CookDex metadata with Project Links immediately below it.
2. Privacy & Data.
3. Also from Knownframe.

The left column is a small nested grid, so its two cards stack according to
their own heights instead of sharing row sizing with the taller Privacy card.
At the existing `1180px` responsive breakpoint, the three columns collapse to
one column. The single-column order is CookDex metadata, Project Links, Privacy
& Data, and Also from Knownframe.

No copy, links, colors, card styling, or application behavior changes.

## Verification

Extend the rendered About-page test with a real Chromium layout check. At a
desktop viewport with an About-grid width that produces the reported
three-column state, assert:

- CookDex metadata, Privacy & Data, and Also from Knownframe share the same top
  position.
- Project Links begins one normal grid gap below the CookDex metadata card.

At a narrow viewport, assert that all four cards occupy one column without
horizontal overflow.

Run the focused test before implementation to prove it fails on the current
layout, then again after implementation. Use Playwright browser inspection at
wide and narrow dark-mode viewports for final rendered validation. Per the
user's request, do not capture or update screenshots.

## Release

Fold the fix into `v2026.7.2`. Because that tag was created before the visual
regression was reported, move it to the corrected protected-branch merge commit
and republish the release image.
