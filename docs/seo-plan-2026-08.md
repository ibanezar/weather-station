# SEO plan — Meteorec (meteorec.si)

**Obdobje:** 31. avgust – 27. september 2026 (4 tedne)
**Postaja:** IREICA1, Rečica ob Savinji, Zgornja Savinjska dolina
**Pripravljeno:** 2026-08-30
**Prejšnji cikel:** `docs/seo-plan-2026-07.md` (7.7.–6.8.2026)

---

## 1. Zakaj ta cikel drugačen od prejšnjega

Od prejšnjega plana (7.7.) je izšlo **pet novih produktov/prenov**, vsi v zadnjih 6 dneh
(24.–30.8.): MeteoGasilec (nova podstran s sedmimi URL-ji), prenova Agrometeo (poštenejše
besedilo, ne nova stran), prenova gobarske napovedi (4 skupine namesto 13 enakovrednih
kartic), MeteoHmeljar (nov interaktivni zemljevid hmeljišč) in `/makro/` (osebni foto arhiv,
namenoma izven SEO cilja). Tehnična pokritost (sitemap) je za vse že urejena — `CORE` v
`tools/seo_audit.py` jih vsebuje. **Vrzel ta cikel ni tehnična, je vsebinska in povezovalna:**
noben od novih produktov (razen MeteoGasilca deloma) še nima lastnega blog članka, `llms.txt`
jih ne omenja, MeteoHmeljar pa je trenutno **popolna sirota** (glej §3.1).

### KPI (spremljaj v Search Console + GA4, G-LE8PJ1HR8B)
- **MeteoHmeljar preneha biti sirota** in dobi prve impresije v GSC do konca cikla.
- **Impresije** za nove krajevne/nišne poizvedbe: "meteorološko orodje za gasilce", "hmeljišča
  zemljevid", "gobarska napoved september" — merljivo v Search Console od tedna 2 naprej.
- **Blog**: ≥ 4 nove objave, vsaka vezana na en od petih novih produktov ali na sezonski vrh
  (gobarska, hmeljeva trgatev).
- **`llms.txt`** vsebuje vseh pet novih produktov do konca tedna 1.
- **0 novih sirotnih strani** — vsaka nova stran, dodana v ta cikel, ima ob objavi ≥ 1 vhodno
  povezavo iz obstoječe strani.
- Lighthouse SEO/Performance ostane ≥ 95 (`lighthouse.yml`) — nespremenjeno merilo.

---

## 2. Kaj že teče samodejno (ne podvajaj ročno)

| Kadenca | Workflow | Kaj naredi |
|---|---|---|
| Dnevno 04:00 UTC | `generate-seo-pages.yml` | Programatske strani: `/vreme/`, `/rekord/`, `/pojavi/`, sezone; `sitemap-weather.xml` |
| Dnevno 04:40–05:45 UTC | `agrometeo-forecast.yml`, `gasilec-forecast.yml`, `gobe-forecast.yml`, `nevihte-forecast`, `kakovost-zraka`, `padalci`, `vodostaj` | Osvežijo napovedne hub strani (verižno, glej komentarje v cron poljih) |
| Dnevno 08:00/09:00 UTC + gate | `storm-map.yml` (`storm_map_gate.py`) | Lastna nevihtna karta Slovenije na `/nevihte/`; FB/IG samo ob oceni ≥ zmerno |
| Dnevno | `prerender-current.yml` | Predrenderira trenutne meritve (WX-STATIC) za SEO/social |
| Dnevno 01:50 UTC | `test-napovedi-daily.yml` | Zajem 5 Open-Meteo virov v `data/forecast-archive.csv` |
| Dnevno | `makro-daily.yml` | Nova makro fotka + `/makro/` hub (ni SEO-gonjen, glej §3.5) |
| Tedensko (pon 05:30 UTC) | `seo-smart-routine.yml` | Hub strani (`/klima/`, `/padavine/`, `/temperatura/`, `/teden/`), zaznava dogodkov → `/novosti/`, `sitemap-seo.xml` |
| Tedensko (ned 04:40 UTC) | `seo-audit.yml` | Sinhronizira `sitemap.xml`, on-page pregled, IndexNow |
| Mesečno (1. ob 03:00/05:15 UTC) | `monthly-post.yml`, `test-napovedi-monthly.yml` | Mesečni povzetki + IndexNow |
| Ob push (main) | `indexnow.yml` | IndexNow ping za spremenjene HTML/sitemap |
| Nadzor | `arso-alerts.yml`, `station-monitor.yml`, `update-history.yml`, `lighthouse.yml` | Opozorila, monitoring, arhiv, kakovost |

> **Ni samodejnega delavnega toka za `generate_hmeljar_page.py`.** Zemljevid je klientsko
> interaktiven (MKGP RABA podatki se preračunajo v brskalniku), zato stran ne rabi dnevne
> osvežitve — a to pomeni tudi, da je vsak ročni popravek strani (npr. dodajanje interne
> povezave, glej §3.1) potreben ponoven `python3 tools/generate_hmeljar_page.py` + push, ni
> samodejen kot pri drugih hub straneh.

---

## 3. Kaj je novo od zadnjega cikla — najdbe in prioritete

### 3.1 MeteoHmeljar je sirota — popravi prvo (kritično)

`grep` po celotnem repozitoriju za `href="...meteohmeljar/"` izven same strani vrne **0
zadetkov**. Stran je v `CORE` (torej v sitemapu) in torej indeksljiva, a nanjo ne kaže noben
notranji povezovalec — enak vzorec napake kot pri `/trendi/` iz julijskega cikla, ki ga je
prejšnji plan izrecno poimenoval kot nevarnost, ki se ponavlja. Slabše od `/trendi/`: to je
edini interaktivni zemljevid hmeljišč doline in izide točno v hmeljevi trgatvi (september).

- [ ] Dodaj povezavo na `/meteohmeljar/` v `/agrometeo/` (najbolj naravno mesto — kmetijska
  tema) in v skupno navigacijo/footer, kjer so že `/gobarska-napoved/`, `/meteogasilec/`.
- [ ] Po popravku ponovno poženi `generate_hmeljar_page.py` (ni v nobenem workflowu, glej §2).

### 3.2 `llms.txt` je šest tednov zastarel

Trenutna vsebina (`llms.txt`, 45 vrstic) ne omenja **nobenega** od petih novih produktov:
MeteoGasilec, Agrometeo, MeteoHmeljar, Test napovedi, nevihtna karta. CLAUDE.md izrecno
pravi "posodobi ob dodajanju pomembnih evergreen strani" — to pravilo šest tednov ni bilo
upoštevano, ker nobena od teh objav ni šla skozi ta korak ročno.

- [ ] Dodaj razdelke: `## Za gasilce (MeteoGasilec)`, `## Kmetijstvo (agrometeo, hmeljar)`,
  `## Test napovedi` — z 2–3 povezavami vsak, po vzorcu obstoječih razdelkov.

### 3.3 Nič blog vsebine za tri od petih novih produktov

`blog.json` (96 objav) nima **nobene** objave, ki bi omenjala "gasilec", "hmeljar" ali
"meteohmeljar" v slugu/naslovu. Agrometeo ima eno objavo (7.7., *Hmelj in vreme julija*) —
napisana **pred** popravkom besedila 28.8. (GDD-zrelost → IHPS status ločeno, glej CLAUDE.md).
Gobarska napoved ima dve objavi (7.7., 15.7.) — obe pred prenovo strani 24.8. na 4 skupine.
Test napovedi ima eno objavo (25.8., julijski povzetek) — ta je v redu, sveža.

- Prioriteta ni "napiši pet objav", ampak: **vsak nov produkt ob prvi omembi v blogu mora
  odražati trenutno stanje strani**, ne stanje izpred prenove.

### 3.4 Gobarska sezona vrh — september, stran spremenjena, vsebina ne

Gobarski indeks je bil sredi julija nizek (7 % v dolini zaradi vročine/suše — glej objavo
7.7.). September je klimatološki vrh gobarske sezone v dolini; stran se je medtem
strukturno spremenila (4 skupine namesto ploskega seznama, nove podstrani `danes/`,
`tereni/`, `nasveti/`, `dnevnik/` — vse že v `CORE`, torej tehnično pokrite). Julijski članki
kažejo na staro strukturo strani in nizek sezonski indeks — ne najboljša vstopna točka za
bralca, ki zdaj išče "kje nabirati gobe zdaj".

### 3.5 `/makro/` — namenoma izven tega plana

Koda sama pove: *"Ni skrbno kurirana SEO stran, ampak dnevnik"* (`INTRO` v
`generate_makro_page.py`). Ima svoj `sitemap-makro.xml`, kar zadošča za tehnično
indeksiranost. **Ne cilja ključnih besed, ne dobiva blog objav v tem planu** — edino, kar
velja preveriti, je da `makro-daily.yml` teče brez napak (tehnični nadzor, ne vsebinsko delo).

### 3.6 Kar je narejeno pravilno in ne rabi popravka

- **CORE pokritost**: vseh sedem `/meteogasilec/*` URL-jev, `/meteohmeljar/`, `/test-napovedi/`
  in `/makro/` so že v `tools/seo_audit.py` CORE oz. lastnem sitemapu — noben od novih produktov
  ni ponovil `/trendi/`-napake na ravni sitemapa.
- **Notranja veljavnost agrometeo popravka**: honest-framing sprememba (28.8.) zmanjšuje
  tveganje, da Google kakovostni pregledovalec stran oceni kot medicinsko/agronomsko
  zavajajočo (YMYL-sorodna vsebina) — to je SEO-pozitivna sprememba, ne le UX.
  `IHPS_STATUS` (ročno vzdrževana tabela) je edina obveznost naprej: **vsaka nova objava na
  ihps.si o zrelosti hmelja gre v to tabelo**, sicer stran spet zaostane za resničnostjo, kar je
  bil izvirni razlog za bralčevo pripombo.
- **Test napovedi**: FB/IG namerno izklopljen (nova vrsta vsebine, glej CLAUDE.md) — to ni
  napaka, samo pomeni, da bo doseg izključno prek organskega iskanja in notranjih povezav;
  preveri, da je `/test-napovedi/` povezan iz `/tocnost-napovedi/` (sorodna tema, drugi bralci).

---

## 4. Tedenski načrt

### Teden 1 — 31.8.–6.9. · Popravi sirote in zastarelo, MeteoGasilec vstop
**Tema:** tehnična higiena novih produktov + uvod za gasilsko občinstvo.

- **Tehnika**
  - [ ] §3.1: notranja povezava na `/meteohmeljar/` (agrometeo stran + footer/nav) + regen.
  - [ ] §3.2: `llms.txt` posodobljen z vsemi petimi produkti.
  - [ ] Ročni sprožilec `seo-audit.yml`, potrdi zelen tek po zgornjih popravkih.
- **Vsebina (blog)**
  - [ ] *"MeteoGasilec: kaj FWI, obrat vetra in operativna karta povedo gasilcem v dolini"* —
    predstavitveni podatkovni članek, ciljno občinstvo tudi lokalni PGD-ji (Rečica, Mozirje,
    Nazarje, Ljubno, Gornji Grad — realna priložnost za povratno povezavo z občinskih/PGD
    strani, ne samo iskalno prometa); keyword: **meteorološko opozorilo gasilci**, **FWI
    indeks Slovenija**, **požarna ogroženost Rečica ob Savinji**. Povezava na `/meteogasilec/`
    in `/opozorilo-pred-pozebo/` (sorodna varnostna tema).

### Teden 2 — 7.–13.9. · Gobarski vrh, prenovljena stran
**Tema:** sezonski vrh iskanja "gobe", stran že prenovljena (24.8.), vsebina naj sledi.

- **Tehnika**
  - [ ] Preveri, da `/gobarska-napoved/danes/`, `/tereni/` kažeta smiselne septembrske podatke.
  - [ ] Audit (ned 13.9.).
- **Vsebina (blog)**
  - [ ] *"Gobarska napoved september 2026: kje v dolini zdaj"* — sveža različica julijskega
    formata (5 območij, model, 7-dnevna napoved), tokrat z izrecno povezavo na novo strukturo
    strani (`danes/`, `tereni/`, `baza-vrst/uzitne/`); keyword: **gobarska napoved september**,
    **kje nabirati gobe zdaj**.
  - [ ] Če model med tednom pokaže izrazit skok indeksa po dežju (>2× teden prej): kratek
    event-driven zapis, isti vzorec kot obstoječi avgustovski "koliko dežja …" članki.

### Teden 3 — 14.–20.9. · Hmeljeva trgatev, MeteoHmeljar vstop
**Tema:** trgatev hmelja v dolini je dobesedno zdaj — časovno najbolj natančno ujemajoč se
produkt v tem ciklu.

- **Tehnika**
  - [ ] Potrdi, da je `/meteohmeljar/` (po §3.1 popravku) viden v GSC Coverage.
- **Vsebina (blog)**
  - [ ] *"Kje so hmeljišča Zgornje Savinjske doline: nov interaktivni zemljevid"* — predstavi
    MeteoHmeljar (MKGP RABA podatki, klientski preračun), poveže z agrometeo GDD/IHPS stanjem
    ob trgatvi; keyword: **hmeljišča zemljevid Savinjska dolina**, **kje so hmeljišča**. Realna
    priložnost za povratno povezavo od hmeljarske zadruge/IHPS, če stran omenijo.
  - [ ] Osveži `IHPS_STATUS` tabelo (§3.6), če je ihps.si medtem objavil status trgatve.

### Teden 4 — 21.–27.9. · Jesenski prehod + mesečni pregled
**Tema:** enakonočje, prvi znaki jeseni, avgustovski mesečni povzetek (izšel 1.9. samodejno).

- **Tehnika**
  - [ ] Preveri, da je `monthly-post.yml` (1.9.) objavil avgustovski povzetek in je indeksiran.
  - [ ] Audit (ned 27.9.) — potrdi 0 napak, 0 novih sirot.
- **Vsebina (blog)**
  - [ ] Sezonski prehod (prva jesenska fronta / padec temperature) — event-driven, iz
    `history.json` primerjava z lanskim letom; keyword: **konec poletja Savinjska dolina**.

### Zaključni dnevi — 28.–29.9. · Pregled + priprava oktobrskega cikla
- [ ] Search Console: impresije/CTR za nove poizvedbe iz §KPI, primerjaj s stanjem 30.8.
- [ ] Potrdi: MeteoHmeljar ni več sirota (interna povezava + GSC Coverage), `llms.txt` posodobljen.
- [ ] Pripravi osnutek oktobrskega plana — tema: prva pozeba (`/opozorilo-pred-pozebo/`,
  sezonsko relevantno od sredine oktobra), konec gobarske sezone, MeteoGasilec skozi jesenski
  dež (poplavna nevarnost bolj kot požarna — preveri, ali `/meteogasilec/vodotoki/` rabi
  sezonski poudarek namesto požarnega).

---

## 5. Vsebinske / keyword priložnosti (slovenščina)

Nove, iz produktov tega cikla (visok namen, ~0 obstoječe vsebine — lastna prednost):
- meteorološko opozorilo gasilci, FWI indeks Slovenija, požarna ogroženost Rečica ob Savinji
- hmeljišča zemljevid, kje so hmeljišča Savinjska dolina
- gobarska napoved september, užitne gobe seznam, strupene gobe Slovenija, dvojnice gob
- primerjava vremenskih modelov (ECMWF, ICON, GFS, ARPEGE) — iz `/test-napovedi/`
- nevihtna karta Slovenije danes

Krajevne, evergreen (iz julijskega plana, še vedno veljavne, nedokončane):
- vodostaj Savinje, nevihte/toča Zgornja Savinjska dolina
- temperaturni trend / segrevanje doline (`/trendi/`)
- rekordi postaje IREICA1

> Vsak blog naj cilja **eno primarno poizvedbo**, temelji na **lastnih meritvah/modelih** (ne
> generični napovedi) in interno povezuje na ustrezno hub stran + `/slovar/`, kjer je smiselno.

---

## 6. Tehnični SEO — stalna pravila (nespremenjeno + eno novo)

- **Vsaka nova stran** → v ustrezen sitemap (že samodejno prek `seo-audit`/CORE), canonical,
  meta description, JSON-LD, og:image.
- **Interno povezovanje**: nova stran ali objava naj bo povezana iz ≥ 1 obstoječe relevantne
  strani **pred** ali **ob** objavi — ne kasneje odkrita kot sirota. To je bila enaka napaka
  dvakrat (`/trendi/` julija, `/meteohmeljar/` zdaj); vredno vprašanje ob vsaki novi podstrani:
  "od kje bo nanjo prišel bralec ali crawler?"
- **`llms.txt`**: posodobi **ob** dodajanju nove hub strani, ne šele naslednji cikel.
- **IndexNow**: samodejno ob push (`indexnow.yml`) — ni ročnega dela.

---

## 7. Backlog / ideje (ne nujno ta cikel)

- Sitemap **index** datoteka (`sitemap-index.xml`) namesto štirih ločenih (`sitemap.xml`,
  `sitemap-seo.xml`, `sitemap-weather.xml`, `sitemap-makro.xml`) v robots — čistejše za GSC.
- `Dataset` strukturirani podatki (schema.org) za `/vreme/` in `history.json`.
- `FAQPage` JSON-LD širše (že na `/gobarska-napoved/`) — kandidat: `/meteogasilec/`.
- Zunanje povratne povezave: lokalni PGD-ji in Občina Rečica ob Savinji za MeteoGasilec,
  hmeljarska zadruga/IHPS za MeteoHmeljar — vredno ročnega e-poštnega dosega, ne SEO-avtomatike.

---

## 8. Kontrolni seznam cikla

- [ ] MeteoHmeljar ni več sirota (notranja povezava + regen strani)
- [ ] `llms.txt` posodobljen z vsemi petimi novimi produkti
- [ ] ≥ 4 nove blog objave, vsaka vezana na nov produkt ali sezonski vrh
- [ ] Avgustovski mesečni povzetek (1.9.) potrjen kot objavljen + indeksiran
- [ ] GSC pregled na koncu cikla + osnutek oktobrskega plana
