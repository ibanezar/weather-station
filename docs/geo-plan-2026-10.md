# GEO načrt (27. 10. 2026)

## Izhodišče (podatki, ne občutek)

- **Panel (22. 10., `data/geo-mentions.json`):** 3 omembe od 21 poskusov (14 %); ChatGPT 2/7, Perplexity 1/7, Gemini 0/7.
  Google AI Overview in Claude nista bila merjena. **Delež glasu 6 %** (ARSO 14×, Windy 4×, Meteoblue 3×).
- **Kje zmagamo:** vprašanja, na katera nihče drug nima odgovora, ker je podatek samo naš: »kateri model je najbolj natančen za
  Rečico« (ChatGPT in Perplexity citirata MTR in analizo IREICA1), »termika Golte« (ChatGPT).
- **Kje izgubimo:** splošna vprašanja, kjer prevladuje uradni ali veliki vir: opozorila ARSO, nevihtna karta, FWI (NRCan), »najboljša
  aplikacija« (ARSO/Windy/Meteoblue/Vreme & Radar).
- **Google AI povzetki (GSC, 3 mesece):** 4 126 prikazov, 88 % Slovenija. Citirani so članki z jasnim odgovorom (gobe po dežju 215 + 183 + 138,
  El Niño 162), naslovna 305, `/gobarska-napoved/` 233, `/vodostaj-savinje/` 155.

**Načelo:** AI povzame stran, ki ima (1) odgovor v prvih dveh stavkih, (2) podatek, ki ga drugje ni, z jasnim virom in datumom,
(3) je v iskalnem indeksu (Google, Bing), (4) je entiteta, ki jo omenjajo tudi drugi. Z ARSO se ne borimo za splošno; lastimo si
**izmerjeno v dolini + primerjavo + razlago**.

## Faza 0 — merjenje (en dan, sprotno)

1. Panel razširi: vsako vprašanje **3× na asistenta** (odgovori variirajo), dodaj **Google AI Overview** in **Claude**. Brez tega je
   6 % šum.
2. Mesečno shrani izvoz GSC »Generative AI Features« (`docs/gsc-YYYY-MM.md` + stolpec citiranih strani). Edini trdi podatek o citiranju.
3. KPI: delež omemb na vprašanjih, za katera **imamo pravo stran** (cilj 14 % → 35 % do konca januarja), in delež glasu (6 % → 15 %).
   Splošna vprašanja (»najboljša aplikacija«) niso KPI strani, ampak blagovne znamke.

## Faza 1 — hitre zmage na obstoječih straneh (1–2 dni)

| # | Ukrep | Zakaj |
|---|---|---|
| 1 | Blok **»Na kratko«** (odgovor v 2 stavkih + datum + vir) na 10 najbolj citiranih straneh: gobarski članki, `/vodostaj-savinje/`, `/nevihte/`, `/gobarska-napoved/`, `/klima/` | Povzetki jemljejo prvi odgovor; nekatere strani ga nimajo |
| 2 | **FWI how-to** na `/meteogasilec/metodologija/`: formula korak za korakom + izračunan primer iz podatkov postaje + opomba, da ni uradna ocena | Izgubljeno vprašanje; NRCan je edini konkurent, slovenskega pojasnila ni |
| 3 | `/nevihte/`: vprašanje »Kje je nevihtna karta Slovenije?« + **rezultat preverjanja karte proti strelam** (to ima samo Meteorec) | Edina enkratna trditev na tej temi |
| 4 | **Vidno »Posodobljeno: datum«** + `dateModified` na vseh ključnih straneh (geo_audit to že preverja za nekaj strani) | Svežina je signal pri vremenu |
| 5 | Zastarele članke (junijski posnetki: El Niño, napovedi) označi z okvirjem »Posodobitev« (kot El Niño 27. 10.) | Stari posnetek, ki ga AI citira, škodi zaupanju |

## Faza 2 — vsebina, ki jo AI citira, ker je edina (1–2 tedna)

1. **»Kateri model je najbolj natančen za Rečico«** je naša zmagovalna tema. Naredi stalno stran z odgovorom v prvem stavku
   (»Za Rečico je v zadnjih N dneh najbolj natančen …, MAE x °C«), tabelo in CSV; osvežuje se samodejno iz `/test-napovedi/`.
2. **Dolinske »prve na svetu« trditve s podatkom:** inverzija (dvoboj Rečica–Varpolje, Črnivec–Rečica), primerjava postaj v dolini
   (vprašanje `primerjava-postaj-dolina`), zmrzal. Vsaka stran: ena številka v naslovu, metoda, omejitve.
3. **Ključna dejstva (»fact sheet«)** `/klima/`: rekordi, normale, povprečja v tabeli z viri; tabele s stabilnimi URL-ji so najpogosteje citirane.
4. **Pozeba in zima** pred sezono (marec, november): `/opozorilo-pred-pozebo/` in `/zima/` imata 0 omemb; pripravi odgovor v prvem stavku.
5. **Ne** poskušaj »kako brati opozorilo ARSO« na splošno (ARSO je vir). Izjema: razlaga z lokalnimi primeri, če ostane čas.

## Faza 3 — entiteta in zunanje omembe (stalno, najpomembnejše za »najboljša aplikacija«)

Za primerjalna vprašanja odloča, ali te omenjajo **drugi** viri. Same strani ne zadostujejo.

1. **Wikidata** vnos za Meteorec / postajo IREICA1 (z uradno spletno stranjo, ustanoviteljem, lokacijo); vključi v `sameAs` (kraj Rečica že ima Q969326).
2. Pošlji podatke ali omembo: občina Rečica ob Savinji, Savinjska turistična organizacija, Inštitut za hmeljarstvo in pivovarstvo (agrometeo), Gorska reševalna/gasilska zveza (MeteoGasilec), Planinska zveza (Golte), lokalni mediji.
3. Gobarske in padalske FB skupine, forumi: odgovori s povezavo na konkretno stran, ne na naslovno (že veljavna praksa pri gobarskih objavah).
4. Avtorska entiteta: stran »O avtorju« z imenom, izkušnjami in `sameAs` (LinkedIn, FB) – preveri, da je `Person` enak na vseh straneh (geo_audit to preverja).

## Faza 4 — tehnika (pol dneva)

1. **Bing**: preveri Bing Webmaster Tools in IndexNow (ChatGPT in Copilot iščeta prek Binga); pošlji sitemap. Tega ne vidim iz repozitorija.
2. `llms.txt` je dober; dodaj `llms-full.txt` (besedilo ključnih strani na enem mestu) in vsakemu vnosu eno vrstico »kdaj uporabiti«.
3. `robots.txt` že dovoljuje vse; ne blokiraj GPTBot, PerplexityBot, Google-Extended, ClaudeBot.
4. Hitrost in dostopnost: strani s kritičnim CSS že obstajajo; preveri, da je ključna vsebina v HTML in ne šele v JS (vreme-recica, vodostaj: prvi odgovor mora biti v statičnem HTML).

## Kaj NE delati

- Ne umetno polnjenje ključnih besed ali podvojene strani (primer `/pojmi/` proti `/slovar/`, 27. 10.).
- Ne objavljaj notranjih meritev (privacy test).
- Ne trdi »najbolj natančen« brez številke in obdobja; ne skrivaj negativnih rezultatov (to je prav naša prednost).
- Ne meri uspeha na enem poskusu: vsak odgovor se razlikuje, zato 3 ponovitve.

## Vrstni red

1. Faza 0 (panel ×3, Google AIO, Claude) — danes.
2. Faza 1 točke 1–4 — ta teden.
3. Faza 4 točka 1 (Bing) — ta teden, 30 minut.
4. Faza 2 točka 1 in 2 — naslednja 2 tedna.
5. Faza 3 — vzporedno, počasi.
6. Ponovno merjenje ob koncu novembra (primerjava z 22. 10.).
