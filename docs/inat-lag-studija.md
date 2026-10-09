# Zamik med dežjem in opažanjem gob: iNaturalist × Open-Meteo

Posnetek: 2026-10-09, padavine do 2026-10-03. Skript: `tools/study_inat_lag.py`. **Enkratna študija, v model ni vgrajena.** Podrobna metoda in omejitve so na dnu.

## Povzetek po vrstah

DSO = dni od začetka zadnjega dogodka dežja (≥ 20 mm v nekaj dneh) do opažanja. »Model« je privzeti zamik v `species_rules.yaml`. »≤ 7 d« je delež opažanj v tednu po začetku dežja. »V oknu modela« je delež opažanj z DSO znotraj modelovega zamika. Primerjava z vsemi glivami (kontrola) kaže, ali je vrsta nad ali pod povprečjem.

| Vrsta | n | mediana DSO (Q1–Q3) | ≤ 7 d | model | v oknu modela | vse glive: ≤ 7 d |
|---|---|---|---|---|---|---|
| Navadna lisička | 104 | 7 (4–14) d | 54 % | 8–16 d | 29 % | 40 % |
| Jurček | 132 | 10 (4–17) d | 42 % | 8–16 d | 33 % | 40 % |
| Rumeni ježek | 31 | 10 (4–24) d | 42 % | 8–16 d | 19 % | 40 % |
| Kostanjevka | 89 | 8 (3–16) d | 47 % | 8–16 d | 28 % | 40 % |
| Orjaški dežnik (marela) | 283 | 11 (5–16) d | 36 % | 2–8 d | 33 % | 40 % |
| Sivorumena mraznica (štorovka) | 52 | 12 (8–23) d | 23 % | 3–10 d | 27 % | 40 % |

## Porazdelitev po razredih DSO (delež opažanj vrste / vseh gliv)

| Vrsta | 0–2 | 3–5 | 6–8 | 9–12 | 13–16 | 17–21 | 22–30 | 31+ |
|---|---|---|---|---|---|---|---|---|
| **vse glive (kontrola)** | 13 % | 18 % | 13 % | 14 % | 12 % | 12 % | 10 % | 8 % |
| Navadna lisička (n=104) | 17 % | 17 % | 25 % | 15 % | 8 % | 9 % | 3 % | 6 % |
| Jurček (n=132) | 17 % | 16 % | 13 % | 13 % | 16 % | 19 % | 4 % | 3 % |
| Rumeni ježek (n=31) | 13 % | 23 % | 10 % | 13 % | 3 % | 13 % | 16 % | 10 % |
| Kostanjevka (n=89) | 18 % | 24 % | 10 % | 10 % | 13 % | 15 % | 7 % | 3 % |
| Orjaški dežnik (marela) (n=283) | 10 % | 16 % | 13 % | 18 % | 20 % | 13 % | 7 % | 4 % |
| Sivorumena mraznica (štorovka) (n=52) | 10 % | 8 % | 10 % | 23 % | 13 % | 8 % | 25 % | 4 % |

Razmerje (vrsta ÷ vse glive; > 1 pomeni, da je vrsta v tem razredu pogostejša od povprečne glive):

| Vrsta | 0–2 | 3–5 | 6–8 | 9–12 | 13–16 | 17–21 | 22–30 | 31+ |
|---|---|---|---|---|---|---|---|---|
| Navadna lisička | 1.3 | 1.0 | 1.9 | 1.1 | 0.6 | 0.7 | 0.3 | 0.8 |
| Jurček | 1.3 | 0.9 | 1.0 | 0.9 | 1.3 | 1.6 | 0.4 | 0.4 |
| Rumeni ježek | 1.0 | 1.2 | 0.7 | 0.9 | 0.3 | 1.1 | 1.7 | 1.3 |
| Kostanjevka | 1.4 | 1.3 | 0.8 | 0.7 | 1.1 | 1.2 | 0.7 | 0.4 |
| Orjaški dežnik (marela) | 0.8 | 0.9 | 1.0 | 1.3 | 1.7 | 1.1 | 0.7 | 0.5 |
| Sivorumena mraznica (štorovka) | 0.7 | 0.4 | 0.7 | 1.6 | 1.1 | 0.6 | 2.6 | 0.5 |

## Samo po suši (7 dni pred dežjem < 8 mm, kot zdaj)

| Vrsta | n | mediana DSO | ≤ 7 d | v oknu modela |
|---|---|---|---|---|
| Navadna lisička | 30 | 9 d | 47 % | 33 % |
| Jurček | 41 | 10 d | 39 % | 24 % |
| Rumeni ježek | 10 | 6 d | 50 % | 30 % |
| Kostanjevka | 45 | 9 d | 42 % | 36 % |
| Orjaški dežnik (marela) | 96 | 13 d | 30 % | 27 % |
| Sivorumena mraznica (štorovka) | 16 | 16 d | 19 % | 25 % |
| vse glive | 4914 | 11 d | 40 % | — |

## Metoda in omejitve

- **Opažanja:** iNaturalist, Slovenija (okvir z robom sosed), avgust–november 2015–2026, `research`, odprta lokacija, natančnost ≤ 5 km. Shranjena so samo datum in koordinate (zaokrožene na celico 0,25°), ne fotografije in ne uporabniki.
- **Padavine:** Open-Meteo Archive (ERA5), celica 0,25°. ERA5 glaji padavine in zaokroži močne plohe, zato so dogodki bolj mehki, kot jih je videla postaja.
- **DSO** je merjen od začetka ZADNJEGA dogodka. Ob ponavljajočem dežju je zato kratek, čeprav je trosnjake sprožil prejšnji dež. Podskupina »po suši« to zmanjša, a ima malo opažanj.
- **Opažanje ni prvi trosnjak.** Stari trosnjaki (marela, jurček) ostanejo več dni in se še fotografirajo, zato je pravi zamik do prvega trosnjaka verjetno krajši od izmerjenega.
- **Pristranskost opazovalcev:** ljudje hodijo v gozd po dežju, ob vikendih in ob poteh. Kontrola (vse glive) to deloma ujame, a vključuje tudi lišaje in lesne vrste z drugačnim zamikom.
- **Majhni vzorci:** pri vrstah z n < 60 (ježek, štorovka) so razmerja šum. Prag zaupanja v poročilu je n ≥ 30.
- Zaključki so v `docs/inat-lag-studija-zakljucki.md`.
