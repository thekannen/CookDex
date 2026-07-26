# Forked Cross-Promotion Design

## Goal

Help CookDex users discover Forked, a related Knownframe app that benefits from
the clean, well-organized Mealie libraries CookDex produces.

The placement should feel like product provenance rather than an advertisement.

## Scope

Add exactly two placements:

1. A Forked card on CookDex's About page.
2. A brief Forked mention near the top of the README.

No banners, modals, onboarding prompts, badges, analytics, or additional
cross-promotion surfaces are included.

## About Page

Add a standard card between the existing **Privacy & Data** and **Project Links**
cards. It uses the existing card, icon, paragraph, and link-button patterns, with
no Forked-specific artwork, animation, or accent styling.

The card content is:

> ### Also from Knownframe
>
> **Forked** — a native iOS app for deciding what to cook from your Mealie
> library. Swipe-based discovery, dietary filtering, meal plans, and one
> persistent shopping list.
>
> Free on the App Store. A clean, well-tagged library makes it noticeably
> better.
>
> View on the App Store

The call to action opens Forked's public App Store listing in a new tab:

`https://apps.apple.com/us/app/forked-recipes/id6760947117`

This wording describes the benefit of using the products together without
implying that either product depends on the other.

## README

Add the following brief mention immediately after the two-paragraph
introduction:

> A clean library also makes native Mealie clients better.
> [Forked](https://apps.apple.com/us/app/forked-recipes/id6760947117), also from
> Knownframe, turns your recipes into swipe-based discovery, meal plans, and one
> persistent shopping list.

The sentence stays in the introductory context and does not create a separate
promotional section.

## Implementation Boundaries

The About-page placement is static presentation content in
`web/src/pages/about/AboutPage.jsx`. It does not require new props, API data,
backend configuration, assets, or application state.

The README placement is a normal Markdown link. Both destinations use the same
verified public App Store URL.

## Accessibility and Failure Behavior

The card retains semantic heading, paragraph, and anchor elements. Its external
link uses the project's existing `target="_blank"` and `rel="noreferrer"`
pattern. The content remains readable if the destination is temporarily
unavailable; no runtime error handling is necessary for a static external link.

## Verification

Add a rendered-component regression test that confirms the About page contains
the Knownframe heading, Forked description, call to action, exact App Store URL,
and intended card ordering. Review the human-facing README prose directly
rather than pinning it with a brittle source-text test.

Also confirm:

- The web application builds successfully.
- The existing Python test suite remains green.
