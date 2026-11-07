# 365-0 — project rules for Claude Code

Read SPEC.md before doing anything. It is the source of truth for product, data, engine, design and delivery. If this file and SPEC.md disagree, SPEC.md wins.

## What this is
365-0 is a mobile-first, portrait, offline-capable web game (wrapped for Android later). Draft 12 world cities, one per month, then watch a real historical year of weather play out. Record format is wins-draws-losses, e.g. 214-91-60. 365-0 would be a year of 365 perfect days and no bad ones.

## Stack and conventions
- Vite + TypeScript (strict). No UI framework. Small hand-written view layer and a state machine.
- The game engine in `src/engine` is pure, deterministic and has zero DOM access. Everything random goes through the seeded RNG.
- CSS: plain CSS with custom properties, OKLCH colour, `light-dark()`, container queries, View Transitions. No Tailwind, no CSS-in-JS.
- All user-facing strings live in `src/i18n/*.json` (en default, sl second). Never hard-code UI copy in components.
- Tests: Vitest for engine and data, Playwright for flows, screenshots and axe accessibility checks.
- Fonts: self-hosted via Fontsource variable packages, latin and latin-ext subsets (Slovene needs latin-ext).

## Working agreements
- Work phase by phase as listed in SPEC.md. Stop at the end of each phase, run the checks, summarise in 3–5 lines, then wait.
- Use plan mode for phases 1, 2 and 4.
- Commit at the end of each phase with a clear message. Never commit raw API caches or secrets.
- Run `npm run check` (typecheck, lint, unit tests, data validation) before saying anything is done.
- Never add dependencies without saying why. Keep the shipped JS under 150 KB gzipped, excluding lazy-loaded data.
- Design rules in SPEC.md section 6 are binding. Do not add gradients, shadows, emoji icons or all-caps labels as decoration.
- Product names are written plainly, with no trademark symbols.
