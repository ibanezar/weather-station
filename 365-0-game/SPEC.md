# 365-0 — full build spec

A one-tap, world-weather draft game in the spirit of 82-0. You draft 12 cities, one for each month, then a real historical year of weather plays out. Your record is wins-draws-losses.

Status of decisions: name is 365-0. Platform is a portrait mobile web app first (PWA), then an Android wrap. Languages are English and Slovene.

---

## 1. Product

### 1.1 One-sentence pitch
Pick the right city for every month of the year, then see how many perfect weather days you drafted.

### 1.2 Core loop (about 60–90 seconds)
1. Home: tap Play daily or Play endless.
2. Draft: 12 rounds. Each round is a month. You see 3 cities and tap one.
3. Reveal: the year plays out as a calendar grid of 365 tiles, month by month, with a live record counter.
4. Result: record, grade, best possible record for this seed, shareable image.

### 1.3 Record format
- Win = perfect day. Draw = ok day (dry but not perfect). Loss = bad day (rain, storm, heat, freeze).
- Record is written `W-D-L`, e.g. `214-91-60`. The three numbers always add up to 365.
- The headline goal is `365-0`: a year with zero losses. Say plainly in copy that this is practically impossible, and that the real goal is to beat today's best possible record.

### 1.4 Day types (six, no more)
| id | meaning | counts as |
|---|---|---|
| perfect | warm, dry, calm, not gloomy | win |
| ok | dry but too cold, too warm, too grey or too windy to be perfect | draw |
| rain | wet day | loss |
| storm | thunderstorm, very strong wind or extreme rainfall | loss |
| heat | very hot day | loss |
| freeze | freezing day or snow | loss |

Thresholds live in `src/engine/thresholds.ts` and are used by the data build script. Starting values, to be tuned after reviewing the data:
- storm: weather code 95, 96 or 99, or gusts at least 70 km/h, or precipitation at least 30 mm
- freeze: max temp at most 3 °C, or snowfall at least 1 cm
- heat: max temp at least 34 °C
- rain: precipitation at least 1 mm
- perfect: max temp 19–28 °C, min temp at least 9 °C, precipitation under 1 mm, gusts under 40 km/h, mean cloud cover at most 65 percent (drop this condition if the data source does not provide it)
- ok: everything else
Precedence when several apply: storm, freeze, heat, rain, perfect, ok.

### 1.5 Game modes
- Daily: seeded by date, same 12 rounds for everyone, one attempt per day, local streak. The date used is the player's local date. The seed string is `365-0:daily:YYYY-MM-DD`.
- Endless: random seed, instant replay, local best record.

### 1.6 Draft rules
- Each round offers 3 cities. Cities never repeat within a run.
- The 3 cities in a round must have 3 different climate archetypes and at least 2 different continents.
- The month is fixed in order January to December. Southern and northern hemisphere seasons are the knowledge part of the game.
- Visible on every card: city name, country, climate archetype icon, average temperature for that month in the player's unit (°C or °F, default from locale).
- Hidden until scouted: how many perfect days and how many bad days that city usually has in that month.
- Scout: the player has 3 scouts per run. Tapping Scout on a card flips it to show two 5-step bars (perfect days and bad days). The bars are bucketed, not exact.
- A round may carry a world event (section 1.7), shown as a chip above the cards before the player picks.
- A tap on a card commits the pick. Show a 2-second Undo toast after each pick. Undo is free and only works for the most recent pick.

### 1.7 World events
About 6 of the 12 months get an event, chosen by the seed. Events are shown before the pick so they are strategy, not surprise. Each event affects only cities with matching climate tags. Events can also be good.

Data-driven in `data/events.json`. Each event has: id, name, one-line blurb, affected tags, and transforms. A transform says: for each day of type X in the chosen historical month, convert it to type Y with probability p (seeded).

Starter set:
- Heatwave: converts ok and perfect days to heat, p 0.35. Tags: mediterranean, continental, desert, temperate.
- Polar vortex: converts ok and rain days to freeze, p 0.4. Tags: continental, subarctic, temperate.
- El Niño surge: converts ok days to rain, p 0.3. Tags: pacific-coast, tropical.
- Monsoon surge: converts ok and perfect days to rain, p 0.35. Tags: monsoon, tropical.
- Dust and wind event: converts perfect and ok days to storm, p 0.25. Tags: desert, steppe.
- Winter storm track: converts ok and rain days to storm, p 0.3. Tags: oceanic, maritime.
- Blocking high: converts ok days to perfect, p 0.4. Tags: oceanic, temperate, mediterranean.
- Clear spell: converts ok days to perfect, p 0.25. All tags.

### 1.8 Scoring, grades and "best possible"
- The world is deterministic. For every (seed, round, city) pair the outcome is fixed: a historical year is picked by seeded RNG from that city's 10 stored years for that month, then the event transform is applied by seeded RNG. Other picks never change it. Use a derived RNG per (seed, round, city id), not one shared stream.
- Because outcomes are independent per round, the best possible record for a seed is the sum over rounds of the best option in that round, by perfect days with fewest losses as tiebreak. Compute it at run start and store it. Show it on the result screen as "Best possible today: 241".
- Grade = player perfect days divided by best possible perfect days. Tiers, tunable in `src/engine/grades.ts` and calibrated by `scripts/calibrate.ts`:
  - under 55 percent: Stormbound
  - 55–65: Umbrella carrier
  - 65–75: Drizzle dodger
  - 75–85: Fair-weather friend
  - 85–93: Sun chaser
  - 93–99: Climate sage
  - 99 or more: Perfect forecast (you matched the best possible record)
- `scripts/calibrate.ts` simulates 50,000 random-pick runs over random seeds and prints the grade distribution, so we can check that a random player lands mostly in the bottom three tiers and that the top tier is rare but reachable.

### 1.9 Result screen "what if"
Below the record, an expandable list of the 12 months. Each row shows the city the player picked with the historical year it drew (e.g. "Singapore 2021") and the best option in that round. This is the learning loop. Tapping a row highlights that column in the year grid.

### 1.10 Onboarding
One screen, three lines, no tutorial wall:
- A perfect day is 19–28 °C, dry and calm.
- Bad days are rain, storm, heat and freeze.
- Pick the right city for every month.
The first Play starts the draft directly. Show this screen once, and keep it reachable from Settings.

---

## 2. Data

### 2.1 City list
About 72 cities, curated by hand in `data/cities.seed.json`. Each has: id, name (en and sl where it differs), country code, continent, lat, lon, archetype tags (several allowed), and a `note` for extreme places.

Archetype tags to use: desert, steppe, monsoon, tropical, equatorial, savanna, mediterranean, oceanic, maritime, continental, temperate, subarctic, polar, highland, island, pacific-coast.

Coverage target (adjust freely, but keep it balanced across continents, hemispheres and extremes):
- Africa: Nairobi, Cape Town, Marrakech, Lagos, Cairo, Addis Ababa, Dakar, Windhoek, Dar es Salaam
- Asia: Mawsynram area (use Shillong as the grid point and note it), Yakutsk, Dubai, Manila, Singapore, Tokyo, Mumbai, Kathmandu, Ulaanbaatar, Hanoi, Seoul, Istanbul, Tbilisi, Riyadh, Colombo, Denpasar, Almaty
- Europe: Reykjavik, Ljubljana, Lisbon, Athens, Tromsø, Edinburgh, Seville, Moscow, Bergen, Longyearbyen, Zermatt area
- North America: Phoenix, Miami, Anchorage, Honolulu, Vancouver, Mexico City, Denver, New Orleans, Yellowknife, Havana
- South America: Lima, Arica, Rio de Janeiro, Quito, Ushuaia, Buenos Aires, Bogotá, Manaus, La Paz
- Oceania and polar: Sydney, Auckland, Perth, Darwin, Hobart, Suva, McMurdo Station

Note on resolution: reanalysis data is gridded (about 25 km), so micro-climates such as Mawsynram or Zermatt are approximated. Choose the nearest representative point and write that in the city `note`. Never claim station-level accuracy in the UI.

### 2.2 Data source and build script
`scripts/build-data.ts` (run with `npm run data`):
1. For each city, fetch daily history for the 10 full years 2016–2025 from the Open-Meteo Historical Weather API (`https://archive-api.open-meteo.com/v1/archive`). Daily variables: `temperature_2m_max`, `temperature_2m_min`, `precipitation_sum`, `snowfall_sum`, `wind_gusts_10m_max`, `weather_code`, `cloud_cover_mean`. Confirm exact variable names in the current API documentation first, and drop any that are unavailable. Use `timezone=auto`.
2. Cache raw responses in `scripts/.cache/` (gitignored). Chunk by year, add a delay and retry with backoff to respect rate limits.
3. Classify each day with the thresholds in 1.4.
4. For each city and month, store the 10 years as 10 strings of one character per day (p, o, r, s, h, f for perfect, ok, rain, storm, heat, freeze). Drop 29 February so February always has 28 characters.
5. Also store per city and month: mean temperature in °C (for the card), and bucketed scout values computed from the 10 years (perfect days 0–4, bad days 0–4, each bucket by quintile of the share of days across all cities for that month, so the 5 steps are meaningful).
6. Write `public/data/world.v1.json` (lazy-loaded) and `src/data/cities.index.json` (small, bundled: names, tags, coordinates, for the first paint).
7. Print a report: file size gzipped, per-city perfect-day share by month, cities with suspicious values (for example a city with no perfect days in any month, or more than 40 perfect days in every month).

Size budget: world data under 120 KB gzipped. If it is larger, pack day strings as 2-bit values or run-length encode.

Licence check (do this before shipping, and write the result in `docs/data-licence.md`): confirm the current Open-Meteo terms for the way the game will be distributed, in particular any restriction on commercial use or requirement for a paid plan or attribution. If the terms do not fit, switch the script to another open source of reanalysis data and keep the same output format. Add a visible attribution line in Settings and on the About screen.

### 2.3 Validation
`npm run data:validate` fails the build if any of these are false: every city has 12 months with 10 strings each, string lengths match the month length, only the six allowed characters appear, scout buckets are integers from 0 to 4, tags are from the allowed list, city ids are unique, and each continent has at least 6 cities.

---

## 3. Engine (src/engine, pure TypeScript)

Files and responsibilities:
- `rng.ts`: `xmur3(seedString)` into `sfc32`. Provide `makeRng(...parts)` that hashes its parts into a new independent generator, so `makeRng(seed, round, cityId)` is stable.
- `draft.ts`: `generateDraft(seed, world)` returns 12 rounds, each with 3 city ids and an optional event id. Enforce the rules in 1.6. Must be deterministic.
- `outcome.ts`: `resolve(seed, round, cityId, month, event?)` returns `{ year, days: DayType[] }`. Picks a stored year with the per-(seed, round, city) RNG, then applies the event transform.
- `score.ts`: `record(days)` returns `{w, d, l}`. `bestPossible(seed, draft)` returns the best record and best city per round.
- `grades.ts`: grade from ratio.
- `run.ts`: state machine for a run: `idle, drafting, revealing, done`, with `pick`, `undo`, `scout`, `finish`.
- `share.ts`: build the share text and the data needed by the image renderer.

Tests required (Vitest):
- Same seed gives identical draft, outcomes and record, across 1,000 random seeds.
- Changing one pick never changes the outcome of any other round.
- Record always sums to 365.
- Best possible is greater than or equal to any achievable record, checked by brute force on 200 seeds.
- Draft rules in 1.6 hold across 5,000 random seeds.
- Event transforms never produce an unknown day type and respect their probabilities within tolerance over many samples.

---

## 4. Screens and flow

Baseline viewport is 390 × 844 portrait. Support 360 × 640 up to 430 × 932, and tablets by capping content width at 480 px and centring. Landscape: keep the portrait layout centred, do not show a "please rotate" wall.

1. Home: title, today's seed date, streak, two buttons (Play daily, Play endless), small Settings and How it works links. If today's daily is already done, Play daily becomes "See today's result".
2. Draft: described in 6.5.
3. Reveal: described in 6.6.
4. Result: described in 6.7.
5. Settings: units (°C or °F), language, theme (system, light, dark), reduce motion override, pattern mode for colour-blind users, haptics, sound (default off), data attribution, privacy, reset progress.

Navigation uses same-document View Transitions between screens, with a plain fallback when unsupported.

---

## 5. Persistence, analytics, privacy
- Store everything in one versioned localStorage key, `365-0:v1`: settings, best endless record, daily results by date, streak. Wrap every read and write in try/catch and keep the game fully playable if storage is unavailable.
- No accounts. No tracking in v1.
- If analytics are added later, use a privacy-friendly, cookieless tool and ask for consent where required in the EU. Event names if added: `run_start`, `pick`, `scout_used`, `run_complete` (with record and grade), `share_tap`.
- Provide a short privacy page that says what is stored on the device.

---

## 6. Design system

### 6.1 Design brief
- Subject: world weather turned into a year-long scoreboard.
- Audience: casual mobile players who like Wordle, 82-0 and quick quizzes. Many are Slovene or English speakers, on mid-range Android phones, in 60-second sessions.
- Primary job: make the choice instant, make the reveal satisfying, make the result worth sharing.

### 6.2 Concept
The one memorable thing is the year grid: 365 tiles, twelve columns (one per month), each tile coloured by its day type. It is the hero of the Reveal, the thumbnail on Result, and the image people share. Everything else stays quiet and flat so the grid is the only place with colour energy.

Voice of the typography is a stadium scoreboard: condensed heavy numerals for records and months, a clear friendly grotesque for everything else.

Principles:
1. The grid is the product. Colour belongs to data, not to decoration.
2. Numerals do the talking. Large, tabular, high contrast.
3. Flat surfaces, thin borders, one lifted state. No decorative shadows or gradients.
4. One orchestrated moment (the reveal). Other motion only answers a tap.
5. Copy is plain, specific and short.

### 6.3 Colour tokens
Define as CSS custom properties on `:root` using OKLCH, with `light-dark()` for theme, and a `data-theme` attribute that overrides the system theme. The hex values below are the design targets; convert them to OKLCH in code and keep a table of both in `docs/tokens.md`.

Surfaces and text:
- surface: light #EDF1F4, dark #0E1624
- raised: light #FFFFFF, dark #17233A
- ink: light #14202E, dark #E8EEF5
- ink-muted: light #5A6B7C, dark #93A3B5
- border: ink at 12 percent

Day types (used as tile fills and in legends; never as text colour on the surface):
- perfect: #FFB703
- ok: #B8C4CF (dark theme #3B4A5E)
- rain: #2F6FDE
- storm: #6A3DC8
- heat: #F0502A
- freeze: #5CC8E8

Interaction:
- accent: perfect gold for primary buttons. Button label is ink on gold (check at least 4.5:1).
- focus ring: 3 px, ink, 2 px offset. Always visible on keyboard focus.

Rules:
- Verify every text and icon pair meets WCAG 2.2 AA (4.5:1 text, 3:1 for large text and graphical objects). Add a script `npm run contrast` that fails the build if a token pair drops below the limit.
- Run the six day-type colours through a colour-blindness simulation (protanopia, deuteranopia, tritanopia) and adjust lightness until each pair stays distinguishable. Record the results in `docs/tokens.md`.
- Pattern mode (setting, and automatic when `prefers-contrast: more`): each loss type gets a fine pattern overlay on its tile (rain diagonal lines, storm crosshatch, heat dots, freeze vertical lines), so meaning never depends on colour alone.
- Do not use warm cream backgrounds with terracotta accents, do not use near-black with neon green, do not use stacked identical rounded cards with soft grey shadows and gradient washes. These are the default looks to avoid.

### 6.4 Type, spacing, shape
- Display: Big Shoulders Display (weights 700–900). Used for the record, month names, grade title and the logo wordmark.
- UI and body: Instrument Sans (variable). Use `font-variant-numeric: tabular-nums` wherever numbers update.
- Self-host both with Fontsource variable packages. Subsets: latin and latin-ext. Preload only the display font and the UI regular weight. `font-display: swap` with a metric-compatible fallback stack to avoid layout shift.
- Scale (px, mobile): 13 caption, 15 small, 17 body, 20 title, 28 heading, 44 display, record numerals `clamp(72px, 22vw, 120px)`. Line height 1.5 for body, 1.05 for display.
- Sentence case everywhere. No all-caps labels, no eyebrow labels above headings, no middle-dot meta strings, no arrows appended to buttons.
- Spacing: 4 px base, steps 4, 8, 12, 16, 24, 32, 48.
- Shape: radius hierarchy (not one radius for all): tiles 3 px, chips 999 px, buttons 16 px, city cards 20 px, sheets 28 px.
- Elevation: none by default. Borders of 1 px for structure. A single lifted state for the card the player is pressing (scale 1.02 and a stronger border), no blur shadows.
- Icons: a custom SVG set on a 24 px grid, 2 px rounded strokes, `currentColor`. Needed: six day types, climate archetypes (desert, monsoon, tropical, mediterranean, oceanic, continental, subarctic, polar, highland, island), scout, undo, share, settings, check, streak. No emoji in the UI (they render inconsistently across Android versions). Emoji squares are used only in the plain-text share message.

### 6.5 Draft screen
```
+--------------------------------+
| progress: 12 steps       scouts 3 |
|                                  |
| July                             |  display type, left aligned
| Heatwave: hot places run hotter  |  event chip, only when present
|                                  |
|  year grid preview (Jan–Jun filled,
|  remaining months empty outlines) |
|                                  |
| +------------------------------+ |
| | Reykjavik, Iceland     11°   | |  city card, min height 88 px
| | oceanic icon        Scout    | |
| +------------------------------+ |
| | Singapore, Singapore   28°   | |
| +------------------------------+ |
| | Phoenix, United States 41°   | |
| +------------------------------+ |
+--------------------------------+
```
- Progress is a 12-step indicator (the months really are a sequence, so numbering is justified). Left aligned, with scouts remaining to the right.
- Cards live in the lower half of the screen, inside the thumb zone. Minimum tap target 56 px tall, full width, 12 px gap.
- Pick feedback: card presses in, the pick slides into its month column of the grid preview using a View Transition, light haptic. Under 250 ms.
- Scout feedback: card flips (200 ms) to show the two 5-step bars, medium haptic.
- The grid preview shows picked months in full and future months as empty outlines.

### 6.6 Reveal screen (the one orchestrated moment)
- The full 12 × 31 grid sits in the middle. Each month column has the city abbreviation on top.
- Above the grid, the live record counter in display numerals counts up as tiles resolve.
- Sequence: months resolve left to right. Within a month, tiles resolve top to bottom with an 8 ms stagger and a short flip. Total length about 6 seconds. Perfect tiles get a small gold flash.
- A tap anywhere skips to the end state. Under `prefers-reduced-motion` (or the in-app override) there is no animation: the grid appears at once and the record is announced once.
- Render the grid on a single canvas or with CSS grid and transforms only (opacity and transform, no layout animation). Hold 60 fps on a mid-range Android phone.
- End: the record settles with a haptic notification pattern, then the grade title appears.

### 6.7 Result screen
- Top: record in display numerals (W-D-L), with small legend chips for win, draw, loss.
- Grade title and one line of copy, e.g. "Sun chaser: you drafted 91 percent of the perfect days available today."
- "Best possible today: 241" with the player's number next to it.
- Primary button: Share result. Secondary: Play endless (or See tomorrow's countdown if daily).
- Expandable "What if" list (section 1.9).
- Streak shown as a small number with its icon, only if streak is 2 or more.

### 6.8 Share
- Image: 1080 × 1350 (4:5) rendered on a canvas: the year grid, the record, grade, date and mode, and the game URL at the bottom (use `{GAME_URL}` placeholder until a domain exists). Offer a 1080 × 1920 story version from the share sheet when it is easy to add.
- Text for platforms that only take text, with line breaks (no decorative separators):
```
365-0 daily 2026-11-06
Record 214-91-60 (Sun chaser)
12 coloured squares, one per month, by dominant day type
{GAME_URL}
```
- Use the Web Share API with files where supported, and fall back to copying the text and offering a download of the image.

### 6.9 Motion tokens
- Durations: instant 80 ms, quick 160 ms, base 240 ms, reveal tile 120 ms.
- Easing: define a springy curve with the CSS `linear()` function for presses and flips, and a standard ease-out for fades.
- Only animate `transform` and `opacity`.
- Respect `prefers-reduced-motion` globally with a single switch, plus an in-app override.

### 6.10 Copy rules
- Active voice, plain verbs, sentence case. Buttons say exactly what they do: Play daily, Share result, Scout, Undo.
- The same action keeps the same name everywhere (the Share result button leads to a confirmation that says "Shared").
- Errors say what happened and what to do, with no apology and no jokes. Example: "Could not load world data. Check your connection and try again."
- Empty states invite action. Example (no streak): "Play today's daily to start a streak."
- Weather-flavoured humour is allowed only in grade titles and in the one-line result copy.

### 6.11 Modern web standards to use (with fallbacks)
- Layout and CSS: `dvh` and `svh` units, `env(safe-area-inset-*)`, container queries for the card component, `:has()` for state styling, `text-wrap: balance` on headings, `@property` for animated tokens, `color-mix()` for tints, `light-dark()` plus OKLCH for theming, `@starting-style` for entry states.
- Navigation: same-document View Transitions.
- Interaction: pointer events with 56 px minimum targets (WCAG 2.2 target size minimum is 24 px; we exceed it), `touch-action: manipulation`, no hover-only affordances, visible focus.
- Accessibility: semantic HTML, one `h1` per screen, cards as real buttons, an `aria-live="polite"` region that announces the final record and grade once, the grid exposed as an image with a text alternative that summarises the year ("214 perfect days, 91 ok days, 60 bad days") and a month-by-month text table available behind a "Show as list" toggle. Full keyboard operation. Screen reader labels for every icon.
- Performance: aim for LCP under 2 s on a mid-range phone on 4G, INP under 200 ms, no layout shift. Lazy-load the world data and prefetch it on Home during idle time.
- Android: handle the system back gesture (go back one step in the draft, confirm before abandoning a run), draw edge to edge with safe-area padding, and match the status bar to the theme.

---

## 7. Internationalisation
- `src/i18n/en.json` and `sl.json`. Keys, not sentences, in code. Pluralisation through `Intl.PluralRules`. Slovene has dual forms, so do not assume two plural forms.
- Month and country names through `Intl.DateTimeFormat` and `Intl.DisplayNames`. City names from the data file (provide `name.sl` where different, e.g. Moskva, Atene, Lizbona, Dunaj-style exonyms where they exist).
- Default language from the browser, overridable in Settings. Check that every screen fits the longer Slovene strings.

---

## 8. Project structure
```
365-0/
  CLAUDE.md
  SPEC.md
  data/            cities.seed.json, events.json
  docs/            tokens.md, data-licence.md
  public/          data/world.v1.json, icons/, manifest.webmanifest
  scripts/         build-data.ts, validate-data.ts, calibrate.ts, contrast.ts
  src/
    engine/        rng, draft, outcome, score, grades, run, share, thresholds
    data/          cities.index.json
    i18n/          en.json, sl.json
    styles/        tokens.css, base.css, components/*.css
    ui/            screens/, components/, icons/, canvas/ (grid renderer, share image)
    main.ts
  tests/           unit/, e2e/
```

---

## 9. Build phases
Stop after each phase, run `npm run check`, summarise, and wait for approval. Commit per phase.

Phase 0, scaffold. Vite + TypeScript strict, ESLint, Prettier, Vitest, Playwright, Fontsource packages, `npm run check`, CI workflow, CLAUDE.md in place. Done when: an empty app builds and the check passes.

Phase 1, data. Curate `cities.seed.json`, write `build-data.ts` and `validate-data.ts`, run them, produce the report. Done when: validation passes, size budget is met, and the report shows no suspicious cities (or they are explained). Write `docs/data-licence.md`.

Phase 2, engine. Implement everything in section 3 with the listed tests, plus `calibrate.ts`. Done when: all tests pass and the calibration output matches the intent in 1.8. Show the grade distribution table.

Phase 3, design system. Tokens, fonts, icon set, components (button, chip, city card, progress, grid renderer, toast) and a `/styleguide` route that shows them in light and dark, pattern mode, and at 360 and 430 px widths. Done when: contrast and colour-blindness checks pass and screenshots are reviewed.

Phase 4, screens. Home, Draft, Reveal, Result, Settings, onboarding, with View Transitions and the reveal sequence. Done when: a full run works on a 390 × 844 viewport, reduced motion works, and Playwright covers a complete daily run and a complete endless run.

Phase 5, share, daily, persistence. Share image and text, daily lock, streak, storage, i18n in both languages. Done when: the share image renders correctly for several records and both languages.

Phase 6, quality pass. PWA (manifest, maskable icons, service worker with offline support, install prompt handling), performance budget, axe checks with zero serious or critical issues, Lighthouse scores of 95 or more for performance, accessibility and best practices, keyboard-only run-through.

Phase 7, Android. Wrap with Capacitor (`@capacitor/core`, `@capacitor/cli`, `@capacitor/android`, plus haptics, share, status bar, app plugins), adaptive icon, splash, back gesture handling, signed release build instructions, store listing text in English and Slovene, a data safety summary and a privacy policy page. Verify the current Google Play target API level and edge-to-edge requirements before building. Done when: a debug build runs on an emulator and the release steps are documented.

Phase 8, optional. Global daily leaderboard and percentile ("better than 82 percent of players today") using a small serverless backend with an anonymous device id, rate limiting and no personal data. Only after phases 0–7 are done and the game feels fun.

---

## 10. Acceptance checklist
- A full daily run takes under 90 seconds and needs no instructions beyond the onboarding screen.
- Same seed gives the same game and the same result on every device.
- The result screen always shows best possible, and the player can never beat it.
- Works fully offline after the first load.
- Light, dark, pattern mode and reduced motion all verified.
- Slovene and English both complete, no truncated text at 360 px wide.
- No console errors, no layout shift, no dead buttons.
- Shipped JS under 150 KB gzipped, world data under 120 KB gzipped.
