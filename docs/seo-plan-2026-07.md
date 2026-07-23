# SEO plan — Meteorec (meteorec.si)

**Obdobje:** 7. julij – 6. avgust 2026 (30 dni)
**Postaja:** IREICA1, Rečica ob Savinji, Zgornja Savinjska dolina
**Pripravljeno:** 2026-07-07

---

## 1. Cilj cikla

Utrditi meteorec.si kot **primarni vremenski in klimatološki vir za Zgornjo Savinjsko dolino**
v vročinsko-nevihtni sezoni, ko iskalno povpraševanje za dolino vrhunec doseže pri:
vročinskih valovih, nevihtah/toči, vodostaju Savinje, kakovosti zraka (ozon) in
kmetijstvu (hmelj, suša). Poudarek je na **sezonsko relevantni vsebini iz lastnih meritev**
in na **tehnični brezhibnosti** (pokritost sitemapa, hitro indeksiranje).

### KPI (spremljaj v Search Console + GA4, G-LE8PJ1HR8B)
- **Impresije** krajevnih poizvedb ("vreme Mozirje/Nazarje/Ljubno/Rečica", "vodostaj Savinje", "nevihte Savinjska dolina") — cilj +15 %.
- **Indeksiranih strani**: vse ključne strani + vse blog objave pokrite in indeksirane (0 vrzeli).
- **Blog**: ≥ 8 novih objav v ciklu, vsaka iz lastnih podatkov (ne posplošene napovedi).
- **CTR** na hub strani apps (nevihte, agrometeo, kakovost-zraka, vodostaj) v vročinskem obdobju.
- **Lighthouse SEO/Performance** ostane ≥ 95 (workflow `lighthouse.yml`).

---

## 2. Kaj že teče samodejno (ne podvajaj ročno)

| Kadenca | Workflow | Kaj naredi |
|---|---|---|
| Dnevno 04:00 UTC | `generate-seo-pages.yml` | Programatske strani: `/vreme/`, `/rekord/`, `/pojavi/`, sezone; `sitemap-weather.xml` |
| Dnevno | `agrometeo`, `nevihte`, `kakovost-zraka`, `padalci`, `gobe`, `vodostaj` forecast | Osveži napovedne hub strani |
| Dnevno | `prerender-current.yml` | Predrenderira trenutne meritve za SEO/social |
| Tedensko (pon 05:30 UTC) | `seo-smart-routine.yml` | Hub strani (`/klima/`, `/padavine/`, `/temperatura/`, `/teden/`), zaznava dogodkov → `/novosti/`, `sitemap-seo.xml` |
| **Tedensko (ned 04:40 UTC)** | **`seo-audit.yml`** | Sinhronizira `sitemap.xml` (blog + ključne strani), on-page pregled, osirotele hub strani, IndexNow |
| Mesečno (1. ob 03:00 UTC) | `monthly-post.yml` | Blog: mesečni povzetek + IndexNow + obvestilo naročnikom |
| Ob push (main) | `indexnow.yml` | IndexNow ping za spremenjene HTML/sitemap |
| Nadzor | `arso-alerts.yml`, `station-monitor.yml`, `update-history.yml`, `lighthouse.yml` | Opozorila, monitoring postaje, arhiv, kakovost |

> **Posledica:** ročno delo v tem ciklu je predvsem **pisanje blog vsebine** in **občasni tehnični popravki**. Vse ostalo je avtomatizirano.

---

## 3. Kaj je novo v tem ciklu (že narejeno danes)

1. **Popravljena vrzel v sitemapu:** `/trendi/` (interaktivni dolgoletni grafi) doslej ni bil v **nobenem** sitemapu → dodan v `sitemap.xml`.
2. **Osvežen `<lastmod>`** domače strani in `/blog/` (bil 2026-07-01, sedaj sinhroniziran z zadnjo objavo).
3. **`tools/seo_audit.py` + `.github/workflows/seo-audit.yml`** — tedenski samodejni SEO audit:
   - preveri, da je **vsaka ključna stran** v vsaj enem sitemapu (ujame prihodnje vrzeli tipa `/trendi/`),
   - preveri, da je **vsaka blog objava** iz `blog.json` v `sitemap.xml` (odpravi ročno dodajanje),
   - preveri, da **ni mrtvih povezav** v `sitemap.xml`,
   - on-page pregled ključnih strani (title, meta description, canonical, og:image, JSON-LD),
   - `--fix` aditivno popravi sitemap in osveži lastmod; nato IndexNow ping.
4. **(23.7.) Samodejno zaznavanje osirotelih hub strani** — `seo_audit.py` zdaj vsak teden
   preveri, da ima vsaka hub stran iz `CORE` (razen domače in `/blog/`) vsaj eno vhodno
   interno povezavo iz vsebine (blog, `/novosti/`, `/slovar/`) ali skupnega hub footerja;
   trenutno stanje: 0 osirotelih od 21 preverjenih. Odpravlja ročno preverjanje, omenjeno
   spodaj v razdelku 6 ("Osiroteli hub-i").

---

## 4. Tedenski načrt

### Teden 1 — 7.–13. julij · Tehnična higiena + vročinski vrh
**Tema:** vročina, ozon, voda. Iskanja: "vročinski val", "kakovost zraka ozon", "vodostaj Savinje".

- **Tehnika**
  - [x] `/trendi/` v sitemap; audit workflow postavljen.
  - [ ] V Search Console preveri **Coverage/Pages** — potrdi indeksiranost `/trendi/`, `/vreme-recica-ob-savinji/`, `/slovar/`.
  - [ ] Ročni sprožilec `seo-audit.yml` (workflow_dispatch), potrdi zelen tek in commit.
  - [x] Interna povezanost: povezava na `/trendi/` dodana v skupni footer (`seo_smart_routine.py`) → pojavi se na vseh generiranih hub straneh ob naslednjem tedenskem teku (pon 13.7.). `/trendi/` ni več "siroti".
- **Vsebina (blog)**
  - [x] **Objavljeno 7.7.**: [*Poletni ozon v Zgornji Savinjski dolini*](/blog/poletni-ozon-kakovost-zraka-savinjska-dolina.html) — podatkovni razlagalec (meritve UV/sonce/veter s postaje), povezan na `/kakovost-zraka/` in 3 pojme v `/slovar/`; keyword: **kakovost zraka Savinjska dolina**, **prizemni ozon**.
  - [ ] Samodejno: `seo-smart-routine` (pon 13.7.) osveži hub + morebiten dogodek v `/novosti/`.

### Teden 2 — 14.–20. julij · Nevihte, toča, hudourniki
**Tema:** nevihtna sezona. Iskanja: "nevihta napoved Savinjska dolina", "toča", "hudournik Rečica".

- **Tehnika**
  - [ ] Potrdi, da `nevihte-forecast` in `arso-alerts` tečeta med nevihtami; preveri OG slike (`og/`).
  - [ ] Audit (ned 19.7.) — potrdi 0 napak.
- **Vsebina (blog)**
  - [x] **Objavljeno 7.7. (predčasno)**: [*Kako brati nevihtno napoved: CAPE, indeks dviga in striženje vetra*](/blog/kako-brati-nevihtno-napoved-cape-striz-vetra.html) — evergreen razlaga z mejnimi vrednostmi, usklajenimi z modelom `/nevihte/`; povezana na `/nevihte/`, 6 pojmov v `/slovar/` in objavo »Anatomija poletne nevihte«; keyword: **CAPE nevihta**, **kako brati nevihtno napoved**.
  - [ ] Event-driven: če nastopi neurje/toča, hitri podatkovni zapis (glej `/novosti/`) + IndexNow (avtomatsko ob push).

### Teden 3 — 21.–27. julij · Kmetijstvo, hmelj, suša, voda
**Tema:** agrometeo. Savinjska dolina = hmeljarstvo. Iskanja: "hmelj vreme", "suša Savinjska dolina", "GDD".

- **Tehnika**
  - [x] Preveri `agrometeo` napoved (GDD, škropilna okna, vodna bilanca) — **odkrita in odpravljena napaka**: fenologija hmelja je bila vezana na GDD₅ in je hmelj 7.7. napačno postavljala v »obiranje«; prekalibrirano na GDD₁₀ (baza 10 °C), umerjeno na večletno akumulacijo postaje → zdaj pravilno »cvetenje«, obiranje ~september. Živa stran `/agrometeo/` regenerirana.
  - [ ] Audit (ned 26.7.).
- **Vsebina (blog)**
  - [x] **Objavljeno 7.7. (predčasno)**: [*Hmelj in vreme julija: rastne stopinje in vodna bilanca*](/blog/hmelj-vreme-julij-rastne-stopinje-vodna-bilanca.html) — iz `/agrometeo/` (GDD₁₀ 610 → cvetenje, obiranje ~september, vodna bilanca); keyword: **hmelj vreme**, **GDD hmelj**, **rastne stopinje**.
  - [ ] *"Suša 2026: koliko dni brez dežja in kaj pravi arhiv"* — iz `history.json`/`/pojavi/`; keyword: **suša 2026 Slovenija**.

### Teden 4 — 28. julij–3. avgust · Mesečni prehod + gobe/paglajivci
**Tema:** zaključek julija, začetek gobarske in avgustovske sezone.

- **Tehnika**
  - [ ] **1.8.**: `monthly-post.yml` samodejno objavi *Vremenski povzetek — julij 2026* (+ IndexNow + naročniki). **Preveri, da je tekel** in da je objava v `blog.json` + sitemap.
  - [ ] Audit (ned 2.8.) — potrdi pokritost nove julijske objave.
  - [ ] Osveži `llms.txt`, če so nove pomembne strani (npr. novi evergreen blogi).
- **Vsebina (blog)**
  - [ ] *"Julij 2026 v številkah"* — ročni highlight ob samodejnem povzetku (deli na social).
  - [x] **Objavljeno 7.7. (predčasno)**: [*Kje v Zgornji Savinjski dolini rastejo gobe zdaj*](/blog/gobarska-sezona-julij-2026-kje-nabirati.html) — pošten podatkovni pogled: dno doline zaostaja (indeks 7 %) zaradi vročine/suše, Logarska dolina vodi (39 %); primerjava petih območij, model in 7-dnevna napoved; keyword: **gobe Savinjska dolina**, **kje nabirati gobe**.

### Zaključni dnevi — 4.–6. avgust · Pregled + priprava naslednjega cikla
- [ ] Search Console: primerjaj impresije/CTR z začetkom cikla; zabeleži zmagovalne poizvedbe.
- [ ] Preglej `seo-audit` in `lighthouse` tedenska poročila; odpravi morebitna opozorila.
- [ ] Pripravi osnutek plana za avgust (obletnica poplav 2023 — 4.–6.8. je močna sezonska tema; `/blog/poplave-2023.html` osveži in interno poveži).

---

## 5. Vsebinske / keyword priložnosti (slovenščina)

Krajevne (visok namen, nizka konkurenca — lastna prednost):
- vreme Rečica ob Savinji / Mozirje / Nazarje / Ljubno ob Savinji
- vodostaj Savinje (živo), pretok Savinje
- nevihte / toča Zgornja Savinjska dolina
- kakovost zraka / ozon / cvetni prah Savinjska dolina
- hmelj vreme, GDD hmelj (agrometeo)
- gobarska napoved Savinjska dolina
- vreme za padalce / termika Golte

Klimatske / evergreen (grade avtoriteto):
- temperaturni trend / segrevanje doline (poveži `/trendi/`)
- temperaturna inverzija / tropske noči Savinjska dolina
- rekordi postaje IREICA1

> Vsak blog naj cilja **eno primarno krajevno ali klimatsko poizvedbo**, temelji na **lastnih meritvah** (ne generični napovedi) in interno povezuje na ustrezno hub stran + 1–2 pojma iz `/slovar/`.

---

## 6. Tehnični SEO — stalna pravila

- **Vsaka nova stran** → v ustrezen sitemap (blog gre samodejno prek `seo-audit`), canonical, meta description, JSON-LD, og:image.
- **Interno povezovanje**: nova objava naj bo povezana iz ≥ 1 obstoječe relevantne strani (ne le iz seznama blogov).
- **IndexNow**: samodejno ob push (`indexnow.yml`) — ni ročnega dela.
- **Osiroteli hub-i**: `/trendi/` je bil siroti; od 23.7. `seo-audit.yml` samodejno tedensko preveri, da imajo vse hub strani vsaj eno vhodno interno povezavo iz vsebine (ni več ročno delo).
- **llms.txt**: posodobi ob dodajanju pomembnih evergreen strani (za LLM/AI iskalnike).

---

## 7. Backlog / ideje (ne nujno ta cikel)

- Sitemap **index** datoteka (`sitemap-index.xml`) namesto treh ločenih v robots — čistejše za GSC.
- Strukturirani podatki `Dataset` (schema.org) za `/vreme/` in `history.json` (CC BY 4.0 je že naveden) — priložnost za Google Dataset Search.
- `FAQPage` JSON-LD na `/o-postaji.html` in hub straneh z FAQ.
- Krajevne strani (`vreme-*`) obogati s tedenskim mini-povzetkom iz `seo-smart-routine`.
- `BreadcrumbList` JSON-LD za globlje strani (`/vreme/YYYY/MM/DD/`).

---

## 8. Kontrolni seznam cikla

- [x] Sitemap vrzel `/trendi/` odpravljena
- [x] Samodejni tedenski SEO audit postavljen (`seo-audit.yml`)
- [x] Interna povezava na `/trendi/` dodana v skupni footer generatorja (aktivira se pon 13.7.)
- [ ] ≥ 8 blog objav (podatkovno utemeljenih) objavljenih — **4/8** (poletni ozon; nevihtni indeksi; hmelj/agrometeo; gobarska sezona — vse 7.7.)
- [ ] Julijski mesečni povzetek (1.8.) potrjen kot objavljen + indeksiran
- [ ] GSC pregled na koncu cikla + osnutek avgustovskega plana
