# AGENTS.md

Instructions for AI coding agents working in this repository.

## Repository purpose

This is the personal portfolio site for Dicky Abdurachman: a lightweight static website built with plain HTML, CSS, and JavaScript. It is designed to present the personal brand, career history, projects, and contact information.

## App structure

```text
index.html          — page structure and content
styles.css          — all visual styling, layout, responsive behavior, and animations
script.js           — interactions such as progress bar, menu toggle, and dynamic footer year
assets/             — images and static media used by the site
site.webmanifest    — PWA manifest
favicon assets      — browser favicon variants
README.md           — project notes and deployment references
```

## Working with this repo

- Keep the site lightweight and fast: prefer small CSS changes and lightweight assets.
- Preserve the visual identity and spacing system already defined in `styles.css`.
- If editing markup, keep semantic HTML and accessibility in mind.
- Test changes in a browser after updates, especially for responsive layout and marquee behavior.
- Avoid adding unnecessary dependencies or frameworks for a simple static site.

## Git workflow

- Never commit directly to `main`.
- Start every change from a new branch based off `main`.
- Use required branch prefixes:
  - `feature/*` for new features or design updates
  - `bug/*` for fixes, layout corrections, or content issues
- Keep commits focused and descriptive.
- Before merging, verify the site looks correct in a browser and that no broken assets or layout issues were introduced.
- Open a PR from the feature/bug branch into `main`.
- If a staging environment exists, test there before the final PR to `main`.
- Do not merge staging directly into `main` unless the project explicitly requires it.

## Content and design expectations

- Keep the tone professional and personal-brand consistent.
- Preserve existing branding: dark neutral base, warm accent orange, clean typography, and modern editorial layout.
- When changing the hero, sections, or marquee timing, verify the result is consistent across desktop and mobile widths.
- When changing links, metadata, Open Graph tags, or favicon assets, keep the published site identity coherent.
