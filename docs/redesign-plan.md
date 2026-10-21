# Redizajn meteorec.si: faza 0 (pregled) in načrt

## Kontekst
Naloga je redizajn naslovne strani (hierarhija, hitrost, enotna identiteta) v 9 fazah. Faza 0 je samo pregled. Po odobritvi ta načrt zapišem v `docs/redesign-plan.md` in se ustavim, preden začnem s fazo 1. Po fazi 3 se ustavim še enkrat in pokažem posnetke.

## Ugotovitve pregleda (izhodišče)
- **Datoteke.** `index.html` 3923 vrstic (305 KB), `style.css` 3273 vrstic (281 KB), `app.js` 20759 vrstic (1,25 MB). Minificirane različice (`style.min.css`, `app.min.js`, `app-lazy.min.js`) in kritični CSS (`index.html:314–316`, ~51 KB) nastanejo iz njih z `npm run minify` in `node tools/critical_css.mjs`. Urejam samo vire.
- **Teme.** `:root` je svetla tema, `[data-theme="dark"]` jo preglasi (`style.css:6`, `:40`). Privzeta je temna (`<html data-theme="dark">`), `setTheme()` je v `app.js:120`, shranjuje v `localStorage 'wx-theme'`. **`prefers-color-scheme` ni nikjer.**
- **theme-color.** Statično `#2563eb` (`index.html:42`, `manifest.json`). `app.js:10004` ga ob nalaganju prepiše glede na vreme.
- **Pisave.** Inter 400 (normal, italic, podmnožica `sl`), Space Grotesk 700 samo za `h1`, JetBrains Mono. Vse lokalno, `font-display: swap`. Inter ima ročno izdelano slovensko podmnožico in `Inter Fallback`, ki je vezana na CLS.
- **Zavihki in meni.** 25 panelov `#tab-*`, `switchTab()` na `app.js:3378`, zavihki v `.tab-nav` (`index.html:491–591`), 9-točkovni `nav.quick-nav` ("Meni") in tri pill povezave (MeteoGobar, Črnivec, MeteoZima). Zavihki že imajo SVG ikone.
- **Preprost/napredni pogled.** Skripta v `<head>` (`index.html:9–16`), `setWxMode`/`chooseWxMode`/`runAdvancedOnly` (`app.js:152–199`), CSS na `style.css:3158–3253` (allowlist `.simple-keep`).
- **Emojiji.** HTML ~423 vrstic (437 emojijev, 149 različnih), `app.js` ~959 vrstic (1308 emojijev, 262 različnih). V JS so predvsem tabele (vremenske kode, fenologija, cvetovi) in predloge nizov, ne le krom.
- **Nalaganje.** `init()` (`app.js:16747`) naloži podatke v valovih (0, 0,8, 2,5, 4, 6 s). Težji deli so že za `runAdvancedOnly`, del kode je v lenem paketu (`@@LAZY-PACK`, `app.js:19074`). "Nalaganje" je 83-krat v HTML, "—" 158-krat. Skeleton `.skel-shimmer` že obstaja na 55 elementih.
- **Hero.** `index.html:655–760`, JS piše v ~50 id-jev (`temp-val`, `hs-*`, `hm-*`, …). Naslovna ima 41 `.card` v `#tab-current` in 172 v celi datoteki.
- **Pre-render.** `inject_current_weather.py` piše v `temp-val`, `feels-val`, `dewpt-hero`, `hs-humidity/pressure/wind/gust/rain-today/uv`, `day-*` z regexom, ki zamenja besedilo do prvega `<`. Prvi otrok mora ostati golo besedilo, enote v otroških `span`. `hs-rain-rate` mora ostati `<span id=…>`. Ostajajo tudi markerji `WX-STATIC`, `WX-DAILY-FACT`, `WX-RECORD-WATCH` in zapis vrstic v `#history-tbody`.
- **Spodnja navigacija.** Na naslovni je ni. `/gobarska-napoved/` jo ima (`bottom_nav_html()` v `generate_gobe_page.py:3167`, 5 ciljev, višina `--gp-bnh`), kar je vzorec za ponovno uporabo.
- **Podbrandi.** `/gobarska-napoved/`, `/zima/`, `/meteogasilec/` ne uporabljajo `style.css`, ampak `blog/blog.css`, `vreme/vreme.css`, `fonts/fonts.css`, vsak z lastnim akcentom v inline CSS (npr. Gobar `--blue:#6fae55`). Spremembe `blog.css`/`fonts.css` zadenejo tisoče strani.
- **Orodja.** Node 22, Playwright in Chromium sta nameščena. Lighthouse ni; potreben je omrežni dostop do `npx lighthouse`/`@lhci/cli` (sicer ostane samo `lighthouse.yml` na živi strani). `check_mobile_overflow.mjs` in lokalni strežnik (`python3 -m http.server 8765`) delujeta za posnetke. Repo nima `node_modules`, zato potrebuje `npm ci`.

## Konflikti z navodili, ki jih je treba rešiti pred fazo 1
1. **Privzeti pogled (faza 4).** Navodilo hoče preprost pogled kot privzeti. `CLAUDE.md` pravi nasprotno: privzeto je napredno, ker preprost pogled skriva večino vsebine in bi osiromašil stran za iskalnike in pajke. Ne bom ga obrnil brez tvoje izrecne odločitve.
2. **Faza 4 je že delno narejena.** Lenih init-ov in `runAdvancedOnly` je že veliko. Preostali delež bo zožen na `IntersectionObserver` za napredne zavihke, ki se še nalagajo zgodaj (wave 3/4).
3. **Meni in zavihki (faza 6).** Poenostavitev v eno navigacijo ne sme odstraniti povezav, ki jih potrebuje SEO (14 `/vreme-*/` povezav v "Kraji", noga strani). Ostanejo v bottom sheetu "Več" in v nogi.
4. **Ikone (faza 2).** `CLAUDE.md` že prepoveduje emoji v gobarskih karticah. Na naslovni zamenjam UI emojije (naslovi, gumbi, meni); emojije v tabelah vremenskih kod, vsebini in uporabniških vnosih pustim. Dolžina dela je velika (~1400 vrstic), zato po skupinah.
5. **theme-color (faza 1).** JS ga ob nalaganju prepiše glede na vreme. Faza 7 in faza 1 morata imeti isto pot: statični `media` pari za barvno shemo, JS samo za dinamično vreme.
6. **prefers-color-scheme.** Zdaj ga ni. Dodam ga tako, da nastavitev v `localStorage` zmaga, brez nje velja sistem. To spremeni privzetek temnega za del obiskovalcev; to je potrebno potrditi.

## Predlagani potek
- **Faza 0 (zdaj).** Po potrditvi zapišem `docs/redesign-plan.md` s tem povzetkom, posnamem izhodišče (Playwright posnetki na 360/390/768/1280 px, svetla in temna tema; Lighthouse, če ga je možno namestiti) in se ustavim.
- **Faza 1.** Tokeni v `style.css` (na vrhu `:root` + `[data-theme]` + `prefers-color-scheme`), naturalistična paleta (kontrast programsko preverim po skillu `dataviz` `validate_palette.js` in z lastnim WCAG skriptom), preklopnik teme z `try/catch`, `theme-color` z `media`, ena variabilna pisava (woff2, lokalno), `clamp()` velikosti. Preslikava stare palete (`--blue`, `--cyan` …) v nove tokene in ne množično preimenovanje. Po fazi: `npm run minify`, `critical_css.mjs`, ponovni testi (`test_privacy.py`, `test_parity.py`).
- **Faza 2.** SVG sprite, `docs/ikone.md`, `aria-hidden`/`aria-label`.
- **Faza 3.** Hero (ohrani vse id-je in regex-kompatibilno HTML) in bento mreža (`card--sm/wide/tall`). **Ustavitev: posnetki zaslona.**
- **Faze 4–9.** Kot v navodilu, z zgornjimi popravki. Zadnja faza doda `docs/redesign-qa.md`.
- En commit na fazo na veji `ccr-af309e71-sjhsj1`; brez PR, dokler ga ne zahtevaš.

## Verifikacija
Playwright posnetki, `check_mobile_overflow.mjs`, `critical_css.mjs` (12 stanj), `test_parity.py`, `test_privacy.py`, `seo-preflight` (naslovi, meta, kanonične povezave in JSON-LD nespremenjeni), CLS z omrežno omejitvijo (kot v CLAUDE.md), Lighthouse vsaj v CI (`lighthouse.yml`) ali lokalno, če bo omrežje dopuščalo.

## Izhodišče (21. 10. 2026, lokalno, brez zunanjih klicev)
- CLS (Playwright, brez omrežne omejitve): 360 px svetla 0,012; vse ostalo ≤ 0,001.
- Posnetki 360/390/768/1280 px × svetla/temna so bili posneti v scratchpadu seje (niso v repozitoriju).
- Lighthouse lokalno ni na voljo; merilo za LCP/INP ostaja `lighthouse.yml` na živi strani.
