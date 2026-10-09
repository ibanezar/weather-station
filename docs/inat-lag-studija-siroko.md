# Zamik med dežjem in opažanjem gob: iNaturalist × Open-Meteo

Posnetek: 2026-10-09, padavine do 2026-10-03. Okvir: {'swlat': 44.6, 'swlng': 12.4, 'nelat': 47.9, 'nelng': 17.6}, meseci 8,9,10,11. Skript: `tools/study_inat_lag.py`. **Enkratna študija, v model ni vgrajena.** Podrobna metoda in omejitve so na dnu.

## Povzetek po vrstah

DSO = dni od začetka zadnjega dogodka dežja (≥ 20 mm v nekaj dneh) do opažanja. »Model« je privzeti zamik v `species_rules.yaml`. »≤ 7 d« je delež opažanj v tednu po začetku dežja. »V oknu modela« je delež opažanj z DSO znotraj modelovega zamika. Primerjava z vsemi glivami (kontrola) kaže, ali je vrsta nad ali pod povprečjem.

| Vrsta | n | mediana DSO (Q1–Q3) | ≤ 7 d | model | v oknu modela | vse glive: ≤ 7 d |
|---|---|---|---|---|---|---|
| Navadna lisička | 255 | 7 (4–14) d | 51 % | 8–16 d | 31 % | 38 % |
| Jurček | 443 | 10 (4–17) d | 42 % | 8–16 d | 30 % | 38 % |
| Rumeni ježek | 84 | 10 (6–21) d | 44 % | 8–16 d | 21 % | 38 % |
| Kostanjevka | 294 | 10 (4–19) d | 44 % | 8–16 d | 22 % | 38 % |
| Orjaški dežnik (marela) | 651 | 11 (6–17) d | 34 % | 2–8 d | 32 % | 38 % |
| Sivorumena mraznica (štorovka) | 107 | 12 (6–19) d | 25 % | 3–10 d | 34 % | 38 % |

## Porazdelitev po razredih DSO (delež opažanj vrste / vseh gliv)

| Vrsta | 0–2 | 3–5 | 6–8 | 9–12 | 13–16 | 17–21 | 22–30 | 31+ |
|---|---|---|---|---|---|---|---|---|
| **vse glive (kontrola)** | 12 % | 17 % | 13 % | 14 % | 11 % | 12 % | 11 % | 10 % |
| Navadna lisička (n=255) | 16 % | 18 % | 23 % | 14 % | 10 % | 8 % | 4 % | 6 % |
| Jurček (n=443) | 14 % | 17 % | 15 % | 16 % | 11 % | 17 % | 6 % | 5 % |
| Rumeni ježek (n=84) | 8 % | 15 % | 24 % | 11 % | 7 % | 11 % | 17 % | 7 % |
| Kostanjevka (n=294) | 15 % | 23 % | 9 % | 11 % | 8 % | 13 % | 14 % | 7 % |
| Orjaški dežnik (marela) (n=651) | 9 % | 15 % | 14 % | 17 % | 19 % | 15 % | 8 % | 5 % |
| Sivorumena mraznica (štorovka) (n=107) | 9 % | 12 % | 10 % | 22 % | 13 % | 12 % | 16 % | 5 % |

Razmerje (vrsta ÷ vse glive; > 1 pomeni, da je vrsta v tem razredu pogostejša od povprečne glive):

| Vrsta | 0–2 | 3–5 | 6–8 | 9–12 | 13–16 | 17–21 | 22–30 | 31+ |
|---|---|---|---|---|---|---|---|---|
| Navadna lisička | 1.3 | 1.1 | 1.8 | 1.0 | 0.9 | 0.7 | 0.3 | 0.6 |
| Jurček | 1.1 | 1.0 | 1.2 | 1.1 | 1.0 | 1.4 | 0.6 | 0.5 |
| Rumeni ježek | 0.7 | 0.9 | 1.9 | 0.8 | 0.6 | 0.9 | 1.5 | 0.7 |
| Kostanjevka | 1.2 | 1.4 | 0.7 | 0.8 | 0.7 | 1.1 | 1.2 | 0.7 |
| Orjaški dežnik (marela) | 0.7 | 0.9 | 1.1 | 1.2 | 1.7 | 1.2 | 0.7 | 0.5 |
| Sivorumena mraznica (štorovka) | 0.8 | 0.7 | 0.8 | 1.6 | 1.2 | 1.0 | 1.4 | 0.5 |

## Samo po suši (7 dni pred dežjem < 8 mm, kot zdaj)

| Vrsta | n | mediana DSO | ≤ 7 d | v oknu modela |
|---|---|---|---|---|
| Navadna lisička | 71 | 7 d | 52 % | 31 % |
| Jurček | 110 | 10 d | 38 % | 28 % |
| Rumeni ježek | 33 | 7 d | 58 % | 15 % |
| Kostanjevka | 95 | 8 d | 48 % | 28 % |
| Orjaški dežnik (marela) | 231 | 13 d | 28 % | 27 % |
| Sivorumena mraznica (štorovka) | 41 | 13 d | 20 % | 37 % |
| vse glive | 12747 | 10 d | 39 % | — |

## Metoda in omejitve

- **Opažanja:** iNaturalist, okvir in meseci so v glavi poročila, 2015–2026, `research`, odprta lokacija, natančnost ≤ 5 km. Shranjena so samo datum in koordinate (zaokrožene na celico 0,25°), ne fotografije in ne uporabniki.
- **Padavine:** Open-Meteo Archive (ERA5), celica 0,25°. ERA5 glaji padavine in zaokroži močne plohe, zato so dogodki bolj mehki, kot jih je videla postaja.
- **DSO** je merjen od začetka ZADNJEGA dogodka. Ob ponavljajočem dežju je zato kratek, čeprav je trosnjake sprožil prejšnji dež. Podskupina »po suši« to zmanjša, a ima malo opažanj.
- **Opažanje ni prvi trosnjak.** Stari trosnjaki (marela, jurček) ostanejo več dni in se še fotografirajo, zato je pravi zamik do prvega trosnjaka verjetno krajši od izmerjenega.
- **Pristranskost opazovalcev:** ljudje hodijo v gozd po dežju, ob vikendih in ob poteh. Kontrola (vse glive) to deloma ujame, a vključuje tudi lišaje in lesne vrste z drugačnim zamikom.
- **Majhni vzorci:** pri vrstah z n < 60 (ježek, štorovka) so razmerja šum. Prag zaupanja v poročilu je n ≥ 30.
- Zaključki so v `docs/inat-lag-studija-zakljucki.md`.
