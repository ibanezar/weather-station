# Poplave 3.–6. avgusta 2023: analiza iz podatkov postaje IREICA1

Interna raziskava, pripravljena 30. julija 2026. Vse številke ponovi
`python3 tools/analiza_poplave_2023.py`.

> **Opomba:** to ni blog članek in ni objavljen. Če se karkoli od tega prenese v
> objavo, mora skozi lekturo po pravilu iz `CLAUDE.md`.

---

## 1. Glavna ugotovitev: vrzel v nizu je mogoče zapolniti

`history.json` za **3., 4., 5. in 6. avgust 2023 nima zapisov**. Poizvedba na
Ecowitt `device/history` za 2.–7. avgust 2023 vrne natanko dva zapisa (2. in 7.
avgusta) — ne pri `cycle_type=auto` ne pri `30min`. Postaja štiri dni ni
pošiljala podatkov; to je bilo v času, ko je bilo po Sloveniji brez elektrike
okoli 16.000 gospodinjstev.

Konzola pa se ni ponastavila. Kumulativni števci dežemera so tekli naprej:

| Števec | 2. 8. 2023 | 7. 8. 2023 | prirast |
|---|---:|---:|---:|
| mesečni | 31,0 mm | 288,3 mm | **257,3 mm** |
| letni | 5126,3 mm | 5383,6 mm | **257,3 mm** |

Dva neodvisna števca se ujemata na 0,0 mm. Ker je 7. avgusta padlo 0,3 mm:

* **3.–6. avgust 2023 = 257,0 mm**

Tedenski števec se v nizu postaje ponastavi ob sobotah (300 od 303 ponastavitev
pade na soboto). 5. avgust 2023 je bila sobota, zato tedenska vrednost 7.
avgusta (4,1 mm) pokriva 5.–7. avgust. Od tod:

* 5.–6. avgust = 3,8 mm
* **3.–4. avgust = 253,2 mm**

Razdelitev znotraj obdobja ima negotovost okoli ±1 mm, ker se posnetek števcev
vzame okoli 2. ure zjutraj. Skupnih 257,0 mm to ne zadeva.

### Posledice za izpeljane vrednosti

| Vrednost | brez rekonstrukcije | z rekonstrukcijo |
|---|---:|---:|
| avgust 2023 | 95,8 mm | **352,8 mm** |
| leto 2023 | 1710,7 mm | **1967,7 mm** |

352,8 mm naredi avgust 2023 za najbolj moker mesec v celotnem nizu postaje —
pred septembrom 2022 (292,9 mm) in julijem 2023 (290,7 mm).

### Zunanje kontrole

* **Okoliške postaje, avgust 2023:** Luče 358,5 mm, Gornji Grad 383,5 mm
  (Meteoinfo Slovenija). 352,8 mm v Rečici se ujema.
* **ARSO** za Savinjo navaja 156 mm povprečja porečja za 4.–6. avgust, z
  opozorilom, da je v zgornjem delu porečja padlo »dvakrat toliko ali še več«.
* **ERA5 (Open-Meteo archive)** za to lokacijo da le 106 mm za 3.–6. avgust —
  41 % izmerjenega, s časovnim vrhom, zamaknjenim za en dan. Model z
  ločljivostjo okoli 30 km orografsko okrepljenega pasu ne razreši.

---

## 2. Vremenski scenarij (ARSO, preliminarno poročilo)

Vir: ARSO, *Nalivi in obilne padavine od 3. do 6. avgusta 2023*.

1. **Zastala višinska dolina.** 3. avgusta se višinska dolina s hladnim
   atlantskim zrakom pomakne z zahodne Evrope proti jugu nad zahodno
   Sredozemlje; fronta valovi prek Alp. 4. avgusta višinska dolina zajame še
   severno in osrednje Sredozemlje, nad severnim Sredozemljem nastane plitvo
   ciklonsko območje. **Fronta se nad Slovenijo zadržuje skoraj 36 ur.**
   ARSO: situacija je za sredino poletja nenavadna, bolj značilna za jesen ali
   zimo.
2. **Zelo vlažen dotok z nadpovprečno toplega morja.** HYSPLIT kaže 120-urno
   pot zračne mase nad Sredozemskim morjem, ki je bilo večinoma toplejše od
   dolgoletnega povprečja. Radiosondaža nad Vidmom sredi noči s 3. na 4.
   avgust: **47 mm vodnega stolpca**, zmerna nestabilnost, zelo močno striženje
   jugozahodnika z višino (pri tleh šibko, 6 km nad tlemi okoli 26 m/s).
3. **Obnavljanje nalivov na alpsko-dinarski pregradi.** 3. avgusta med 19. in
   22. uro izrazit padavinski pas prečka severno polovico Slovenije; sredi noči
   se proženje zgosti od Trnovskega gozda prek Gorenjske do Kamniško-Savinjskih
   Alp, kjer se nalivi obnavljajo več ur zapored. **Glavnina padavin pade v manj
   kot šestih urah.** Umirjanje šele okoli 7. ure 4. avgusta.

**Česa ni bilo:** to ni bilo neurje z vetrom. Najmočnejši sunek na postaji v
dneh okoli ujme je 25,6 km/h (2. avgusta), tlak je ostal med približno 1004 in
1013 hPa. Plitvo ciklonsko območje, ne globok ciklon.

### Povratne dobe v okolici (ARSO, preglednica 1)

| Merilno mesto | Padavine | Interval | Konec | Povratna doba | Opomba |
|---|---:|---:|---|---:|---|
| Luče | 145 mm | 7 h 59 min | 4. 8., 4.00 | > 100 let | izpad meritev, verjetno precej več |
| Logarska Dolina | 130 mm | 7 h 20 min | 4. 8., 3.20 | > 100 let | izpad meritev, verjetno precej več |
| Zavodnje | 160 mm | 10 h 15 min | 4. 8., 7.00 | > 100 let | — |
| Radegunda | 136 mm | 8 h 55 min | 4. 8., 5.40 | > 100 let | izpad meritev |
| Gornji Grad | 97 mm | 7 h 30 min | 4. 8., 4.40 | 25 let | izpad meritev, verjetno precej več |
| Pasja ravan | 213 mm | 9 h 30 min | 4. 8., 5.35 | > 100 let | najbolj izjemna v državi |

V Zgornji Savinjski dolini uradna mreža tiste noči **ni imela popolnih
podatkov**. 257,0 mm z dežemera v Rečici je zato eden redkih nepretrganih
seštevkov s tega območja.

---

## 3. Zakaj je bilo tako hudo: predhodna namočenost

Julij 2023 je bil na postaji z 290,7 mm najbolj moker julij v nizu. Od 1. junija
do 7. avgusta 2023 je skupaj padlo **739,8 mm**.

Padavine v 30 dneh pred 3. avgustom, po letih (za 2026 obdobje do 29. julija,
ker novejših meritev v nizu še ni):

| Leto | 7 dni | 14 dni | 30 dni | 60 dni | 90 dni | API |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 19,6 | 44,2 | 135,9 | 367,1 | 465,6 | 55,2 |
| 2021 | 48,7 | 52,3 | 206,5 | 259,4 | 475,1 | 72,1 |
| 2022 | 25,2 | 28,5 | 91,5 | 174,7 | 299,5 | 32,4 |
| **2023** | 53,1 | **205,2** | **289,5** | **444,4** | **635,4** | **140,3** |
| 2024 | 19,5 | 56,1 | 115,1 | 236,6 | 442,2 | 48,1 |
| 2025 | 72,1 | 102,6 | 203,9 | 233,8 | 346,1 | 80,3 |
| **2026** | **0,2** | 20,6 | **49,8** | 216,1 | 339,6 | **19,2** |

API = indeks predhodne namočenosti, vsota padavin zadnjih 120 dni z
eksponentnim upadanjem (k = 0,92 na dan).

ARSO isto ugotavlja za širše območje: h katastrofalnim posledicam je pripomogla
»nenavadno velika namočenost tal po zelo mokrem juliju«. Na Ravnah na Koroškem
je od 1. junija do 7. avgusta padlo 662 mm (prejšnji rekord 550 mm, 1956), na
Letališču JP Ljubljana 671 mm.

---

## 4. Merilo dogodka v nizu postaje

Največje dvodnevne vsote 2020–2026 (brez prekrivajočih se parov):

| Obdobje | Vsota |
|---|---:|
| **3.–4. 8. 2023** | **253,2 mm** * |
| 12.–13. 9. 2024 | 105,4 mm |
| 2.–3. 10. 2024 | 99,3 mm |
| 1.–2. 12. 2023 | 86,1 mm |
| 16.–17. 9. 2022 | 85,6 mm |
| 4.–5. 7. 2021 | 81,0 mm |
| 24.–25. 7. 2023 | 80,3 mm |
| 7.–8. 7. 2025 | 77,2 mm |

\* rekonstruirano iz kumulativnih števcev

Ujma je **2,4-krat** večja od najmočnejšega drugega dvodnevnega dogodka v
sedmih letih meritev.

Šest od osmih najmočnejših **dnevnih** padavin v nizu je padlo med septembrom in
novembrom — po dosedanjih meritvah je jesen v tej dolini bolj izpostavljen del
leta kot avgust.

---

## 5. Primerjava z letom 2026

Do 29. julija 2026 je padlo 554,5 mm — 26 % pod povprečjem 2020–2025 (750,3 mm)
in drugo najbolj suho leto v nizu, za 2022 (503,5 mm).

| Mesec | 2023 | 2026 | Povpr. 2020–25 | 2026 / povpr. |
|---|---:|---:|---:|---:|
| jan | 160,3 | 63,0 | 83,3 | 76 % |
| feb | 24,6 | 97,8 | 56,3 | 174 % |
| mar | 78,0 | 19,9 | 88,0 | 23 % |
| apr | 90,0 | 34,2 | 81,1 | 42 % |
| maj | 171,1 | 125,0 | 161,0 | 78 % |
| jun | 160,8 | 164,8 | 110,1 | 150 % |
| jul | 290,7 | 49,8 | 176,4 | 28 % |
| avg | 352,8 | — | 97,7 | — |

Stanje pred avgustom 2026:

* **Julij 2026 je najbolj suh julij v nizu** — 49,8 mm, 28 % povprečja postaje
  in 17 % julija 2023.
* Zadnji dan z ≥ 20 mm: **15. junij** (44 dni pred 29. julijem). Zadnji dan z
  ≥ 10 mm: 18. julij.
* Junij je bil moker (164,8 mm, 150 % povprečja), a je bil ta dež porabljen:
  60-dnevna vsota (216,1 mm) je videti spodobna, **API pa je z 19,2 najnižji v
  celotnem nizu**.
* Tudi pomlad je bila suha: marec 23 % povprečja, april 42 %. Dva niza brez
  dežja po 19 oziroma 18 dni.
* Dež je bil letos tudi šibkejši: 6,52 mm na deževni dan, najmanj v nizu
  (2020–2025: 6,70–8,75 mm).
* Julij 2026 je bil najšibkejši julij po vetru v nizu — največji sunek 34,9 km/h
  (2023 in 2024: 48,0 km/h).

Vlaga je edina sestavina, ki je letos primerljiva: julijsko rosišče 16,3 °C in
vlaga 76,5 %, proti 17,3 °C in 82,2 % julija 2023.

---

## 6. Sinteza: kaj bi se moralo zgoditi za ponovitev

| Sestavina | 2023 | 2026 |
|---|---|---|
| Nasičena tla | 289,5 mm v 30 dneh, API 140,3 | 49,8 mm, API 19,2 — najnižji v nizu; ARSO je sredi julija dolino uvrstil med območja z zmerno sušo |
| Zastala fronta nad pregrado | skoraj 36 ur | sinoptična sestavina, iz podatkov postaje je ni mogoče napovedati |
| Vlažen dotok s toplega morja | 47 mm vodnega stolpca, rosišče 17,3 °C | rosišče 16,3 °C — nekoliko nižje, a v istem razredu |
| Obnavljajoči se nalivi | glavnina v manj kot 6 urah | letos krajše in bolj razpršene nevihte, 6,52 mm na deževni dan |

**Kar suha tla ne odpravijo.** Suša zmanjša tveganje za obsežno poplavo iz
nasičenih porečij, ne zmanjša pa tveganja za hudournik in plaz — 253 mm v pol
dneva odteče po površju ne glede na stanje tal, presušena in strjena tla vodo
sprva celo slabše vpijajo.

---

## 7. Omejitve

* Rekonstrukcija 257,0 mm sloni na tem, da se konzola med izpadom ni
  ponastavila. Potrjujeta jo dva neodvisna števca, ni pa je bilo mogoče
  preveriti z drugim dežemerom na istem mestu.
* Niz postaje obsega sedem let. Za oceno povratnih dob je prekratek — vse
  trditve o izjemnosti veljajo znotraj tega okna, ne klimatološko.
* Podatki za 2026 se končajo 29. julija; primerjave predhodne namočenosti so za
  to leto narejene na ta datum, za druga leta pa na 2. avgust.

## Viri

* ARSO — *Nalivi in obilne padavine od 3. do 6. avgusta 2023* (preliminarno
  poročilo): sinoptična analiza, preglednica povratnih dob, preglednica dnevnih
  vsot, povprečja po porečjih.
* Meteoinfo Slovenija — padavine v avgustu 2023 (mesečne vsote po postajah).
* Open-Meteo Archive (ERA5) — primerjalna reanaliza za lokacijo postaje.
* Ecowitt `device/history` API — kumulativni števci dežemera.
* `history.json` — dnevni povzetki postaje IREICA1, 2019–2026.
