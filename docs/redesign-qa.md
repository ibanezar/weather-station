# Redizajn meteorec.si: QA pred/po (21. 10. 2026)

Primerjava izhodišča (commit `f462675`, faza 0 = stran pred redizajnom) z vejo `ccr-af309e71-sjhsj1` (faze 1–7; faza 8, pod-brandi, je po odločitvi uporabnika izpuščena). Vse meritve lokalno (strežnik `python3 -m http.server`, Lighthouse 12 + Chromium iz `/opt/pw-browsers`, mobilni profil), zato absolutne vrednosti performansa niso merilo (glej CLAUDE.md, »Lighthouse na lokalnem strežniku ni merilo za LCP«); pomembna je primerjava.

## Lighthouse (mobilni profil, 2 teka vsak)
| | Prej | Potem |
|---|---|---|
| Performance | 34 / 39 | 36 / 39 (35 po zadnji gradnji) |
| Accessibility | 100 / 100 | 97 → **100** (po popravku kontrasta, glej spodaj) |
| Best practices | 77 | 77 |
| SEO | 100 | 100 |
| CLS | 0,02 | 0,019 |
| LCP (lokalno, nezanesljivo) | 9,7–10,9 s | 11,0–11,1 s |
| TBT | 950–1500 ms | 960–1180 ms |

Rezultat performansa ni slabši znotraj šuma. LCP/FCP je na lokalnem strežniku dominiran z zunanjimi skripti; pravo merilo je `lighthouse.yml` na živi strani po objavi (ni v moči peskovnika).

## Dostopnost
- Lighthouse je po fazi 7 padel s 100 na 97: **42 vozlišč `color-contrast`**. Vzrok: predlagana temna `Bledo besedilo` `#9DB0A4` je pri `opacity .6–.7` (uporabljena na ~40 mestih) pod 4,5:1. Popravek: temna `--c-ink-soft` `#C0CFC5` (4,58:1 pri opacity .6), temna `--red` `#fb8a8a`, `.mtr-chip.up` na `var(--red)`. Rezultat: 100.
- axe-core 4 (wcag2a+aa), naslovna, 1280 px:
  - prej: temna brez kršitev, svetla `color-contrast` ×107
  - potem: temna brez kršitev, svetla `color-contrast` ×9
- axe `best-practice` (informativno): `region` (116), `landmark-one-main` (stran nima `<main>`; glava in noga sta znotraj `.wrap`), obstajalo že prej.
- Tipkovnica (Playwright): prvi Tab = skip link; Enter → `#main-content`; ArrowDown odpre meni (`aria-expanded`), Escape zapre in vrne fokus; `aria-current` sledi `switchTab`.
- `prefers-reduced-motion: reduce`: 0 aktivnih `skel-shimmer`, štetje števil takoj, grafi brez razkritja.

## SEO in pre-render
Primerjava `index.html` prej/potem: `<title>`, `canonical`, JSON-LD, `h1` in vsi `meta` **enaki**; razlikuje se samo `theme-color` (`#2563eb` → `#0F1713`). `inject_current_weather.py` še prime vse vzorce (preizkušeno v fazi 3, rezultat razveljavljen). `test_privacy` 41/41, `test_parity` 6820/6820, `test_freshness` 62/62, `test_om_fetch` 11/11.

## PWA / TWA
- Service worker aktiven; **ponovno nalaganje brez povezave** (offline) naloži naslovno stran iz predpomnilnika (`naslov` in predrenderirana temperatura prisotna).
- `manifest.json`: `theme_color` `#2F6B4F`, `background_color` `#0F1713`. Konfiguracije TWA (PWABuilder) v repozitoriju ni: ob naslednji gradnji paketa uskladi `theme-color`/barvo statusne vrstice z manifestom.
- `sw.js` nespremenjen (`vreme-static-v17`); CSS in JS ostajata na stale-while-revalidate, zato obiskovalci novo različico dobijo ob drugem nalaganju.

## Posnetki zaslona
360/390/768/1280 px × svetla/temna × napredni/preprosti pogled in `reduce` varianta: v scratchpadu seje (`f9/`, `f9r/`), niso v repozitoriju. Brez vodoravnega drsenja (`overflowX` 0 pri vseh šestih kombinacijah).

## Znane omejitve in predlogi
1. **Faza 8 (pod-brandi) ni izvedena**; `blog.css`/`fonts.css` nespremenjena, zato Gobar, Zima, Gasilec in Črnivec ostajajo v starih barvah.
2. Preostalih 9 `color-contrast` v svetli temi in `region`/`main` landmarki: zahtevajo ločen pregled (trdo kodirane barve v JS grafih in `.simple-keep`).
3. `.mtr-chip.down` uporablja `var(--blue)`, ki je zdaj akcent (zelen): semantika »pod napovedjo = modro« je izgubljena; potreben je namenski token.
4. Pravi LCP/INP/CLS s pravimi podatki: preveri `lighthouse.yml` po objavi (peskovnik nima zunanjih API-jev).
5. Globlje kartice z grafi še niso v bento mreži (JS jih riše po `clientWidth`).

## Dopolnitev (po mergu, 21. 10. 2026)
- **Živi Lighthouse po mergu** (`lighthouse.yml`, 1 tek vsak): mobilni performance 0,42 → 0,48, desktop 0,28 → 0,26 (znotraj šuma). Vsi workflowi po mergu zeleni (minify, smoke, parity, privacy, Pages, IndexNow).
- **`--c-cool`** (semantična »hladno/voda« modra, ločena od akcenta): `.mtr-chip.down`, `.ds-low`, ploščici vlage in dežja. Prej so po preslikavi `--blue` → akcent postale zelene.
- **Kontrast v svetli temi: 0 kršitev axe** (prej 9) pri 1280 in 390 px, temna tema 0: oznake `.past-days-hdr-lbl`/`.section-fold-lbl` (`--c-ink`), `.pd-meta` placeholderji (brez `opacity .7`), `#aqi-val` (temnejša lestvica prek `data-aqi`, odziva se tudi na menjavo teme), `.sub-btn` (`--c-on-accent`), `.ft-donate-link` (`--c-accent`). Pozor: `#visitor-counter` axe javi samo med 0,4 s animacijo `vc-in`; po koncu je v redu (merimo po 7 s).
- **Bento za globlje kartice:** v par (`card--wide` + `card--wide`, 2 × 2 stolpca) sta šla le kartici »Padavinske norme« in »Sončne ure« (obe imata notranjo mrežo ploščic; pri 1280 px po 552 px, 3 ploščice se prilegajo; pod 1024 px sta ena pod drugo, brez vodoravnega drsenja). **Grafi (`.chart-card`) ostanejo čez celo širino**: `viewBox` je 880 px širok, v polovični širini bi se pisava osi pomanjšala na ~63 % (≈ 7 px), kar je neberljivo. `ResizeObserver` zato ni potreben (SVG se skalira sam); če bi grafe vseeno parili, jih je treba najprej izrisati z drugačnim `viewBox`.

## Preostalo (po mergu, 21. 10. 2026)
- **`<main>` landmark:** vsebina med `</header>` in `<footer>` je zdaj v `<main id="main-content" tabindex="-1">` (skip link vodi vanj); `.wrap` ostane `div`. axe (wcag2a/aa + best-practice) pri 1280/390 px (napredni in preprosti pogled): **0 kršitev** (`landmark-one-main` 0, `region` 116 → 0: `#bg` je `aria-hidden`, `#toast` `role="status"`). Tri vodoravni drsniki (`cu-hourly`, `cu-days`, `twh-grid-wrap`) imajo `tabindex="0"`, `role="group"` in `aria-label` (`scrollable-region-focusable`).
- **Spodnja vrstica:** samo CSS (`scroll-snap`, mehek rob na desni kot namig za drsenje, aktivni cilj z `--c-accent` in zgornjo črto); struktura in vrstni red nespremenjena.
- **Delo glavne niti (TBT ~1 s):** profil lokalnega Lighthouse (6× CPU) pokaže, da je skript samo 1,8 s od 15 s; prevladujeta »Other« (6,2 s), Style & Layout (3,5 s) in Rendering (3,0 s), torej velik DOM, ne JS. Ukrep: `content-visibility:auto` + `contain-intrinsic-size:auto 420px` na kartice pod pregibom v `#tab-current` (brez `.chart-card`): Style & Layout 3,5 s → ~2,6 s, Rendering 3,0 s → ~1,6 s (2 teka, TBT v šumu, a11y 100). `.chart-card` je izvzet, ker njihovi vodoravni drsniki dobijo `tabindex` šele ob prikazu in bi `scrollable-region-focusable` padla. Delitev `app.js` v nove lene pakete ni upravičena: skript ni ozko grlo.
- **TWA (PWABuilder):** konfiguracije ni v repozitoriju. Ob naslednji gradnji paketa nastavi `theme color` na `#2F6B4F`, `navigation bar color`/`status bar` na `#0F1713` in `background color` na `#0F1713` (enako kot `manifest.json`).
- **Pod-brandi (faza 8):** namerno izpuščeno po odločitvi uporabnika.
