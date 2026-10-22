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

## A1: dolinski prerez v herou (22. 10. 2026)
- **Kaj je:** v **lastni kartici »Dolina zdaj«** (`#valley-card`, takoj za dnevnim povzetkom; najprej je bil v herou, uporabnik je položaj zavrnil kot premalo pomemben za hero) je shematski prerez doline Rečica (366 m) → Gornji Grad (428 m) → Črnivec (903 m). Stolpec zraka je obarvan z **izmerjenimi** temperaturami treh postaj (IREICA1 + DRSI prek `/crnivec-drsi`, isti vir kot dolinski profil pri dvoboju): linearno med postajami, nad Črnivcem standardni gradient −0,65 °C/100 m, pod Rečico ista temperatura. Črta 0 °C je ocena iz iste krivulje in tako tudi označena (»(ocena)«, kadar je zunaj izmerjenega razpona višin). Podnaslov pove vrsto gradienta (inverzija / šibek / običajen / strm).
- **Koda:** čiste funkcije `valleyTempAt`, `valleyZeroHeight`, `hvColor`, `heroValleySvg` v `app.js` (`_vpPoints()` je skupen z dvobojem); `fetchHeroValley()` v valu 2 (samo napredni pogled) in na 5 min; CSS `.valley-card`; v preprostem pogledu skrito (kartica ni `simple-keep`). Testi: `tools/test_valley_profile.py` (34 preverjanj, med njimi robni primeri 0 °C, ozek/širok zaslon, brez NaN).
- **Rezervirana višina:** `aspect-ratio` vsebnika sovpada z viewBox (640:190 na telefonu, 1:0,18 od 760 px); višina pred/po prihodu podatkov enaka, podnaslov ima `min-height` za 2 vrstici.
- **Pozor (Playwright):** service worker prestreže API klice, zato `route()` mock deluje šele z `serviceWorkers:'block'`. `tools/_parity_js.mjs` ne prenese regex literala `/"/g` v funkciji (zmede sledenje narekovajem): zamenjano z `split('"').join('&quot;')`.
- **Ni v tej verziji:** animacija po urah (drsnik −6…+24 h; izmerjenih višinskih podatkov za napoved ni), megleni pas (ocena `data["fog"]` še ni povezana).

## PM2,5 (Varpolje) v herou (22. 10. 2026)
- **Vir:** `varpolje.si/station.json` prek obstoječega workerja `/varpolje-current` (CORS, blok `indoor` se reže pri viru; `pm25_ugm3`, `pm25_24h_avg_ugm3`, `pm25_agreement`). IREICA1 PM ne meri, zato je ploščica vedno označena »PM₂,₅ · Varpolje« (tooltip: sosednja postaja, ~1,6 km); sosed ostane gost (CLAUDE.md), nič ne gre v `history.json`, MTR ali semafor.
- **Prikaz:** sekundarna ploščica v `.hero-metrics` (zdaj mreža 12 stolpcev: 4 primarne × span 3, 3 sekundarne × span 4; telefon 2 stolpca), vrednost v µg/m³, razred in 24 h povprečje v podnapisu. Samo napredni pogled (v preprostem skrita). Osveži se na 5 min (`fetchHeroPm()`, val 2).
- **Razredi** (`pmBand()`): urna lestvica EAQI za PM2,5, kot jo uporablja Open-Meteo `european_aqi` (kartica »Kakovost zraka«): ≤ 10 zelo dobro, ≤ 20 dobro, ≤ 25 zmerno, ≤ 50 slabo, ≤ 75 zelo slabo, nad tem nevarno. **Meje nisem mogel potrditi pri EEA** (iskanje je vrnilo samo letne kategorije mest); preveri jih pred javno objavo.
- **Svežina:** posnetek starejši od 45 min (`PM_MAX_AGE_MIN`) ali `pm25 = null` se ne prikaže kot vrednost (»—« + razlog), ne skrije se tiho.
- **Barve v svetli temi:** temnejši odtenki prek `data-pm` (axe `color-contrast` 0 pri vseh šestih razredih).
- Test: `tools/test_pm_tile.py` (10 preverjanj; v `parity.yml`). Višina hera pred/po prihodu podatkov enaka (739 px namizje, 845 px telefon).
