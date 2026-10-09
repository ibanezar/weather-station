# Zamik med dežjem in opažanjem gob: iNaturalist × Open-Meteo

Posnetek: 2026-10-09, padavine do 2026-10-03. Okvir: {'swlat': 44.6, 'swlng': 12.4, 'nelat': 47.9, 'nelng': 17.6}, meseci 5,6,7. Skript: `tools/study_inat_lag.py`. **Enkratna študija, v model ni vgrajena.** Podrobna metoda in omejitve so na dnu.

## Povzetek po vrstah

DSO = dni od začetka zadnjega dogodka dežja (≥ 20 mm v nekaj dneh) do opažanja. »Model« je privzeti zamik v `species_rules.yaml`. »≤ 7 d« je delež opažanj v tednu po začetku dežja. »V oknu modela« je delež opažanj z DSO znotraj modelovega zamika. Primerjava z vsemi glivami (kontrola) kaže, ali je vrsta nad ali pod povprečjem.

| Vrsta | n | mediana DSO (Q1–Q3) | ≤ 7 d | model | v oknu modela | vse glive: ≤ 7 d |
|---|---|---|---|---|---|---|
| Navadna lisička | 180 | 6 (3–13) d | 58 % | 8–16 d | 26 % | 44 % |
| Jurček | 60 | 8 (3–15) d | 43 % | 8–16 d | 35 % | 44 % |
| Rumeni ježek | 2 | 13 d | 0 % | 8–16 d | 50 % | 44 % |
| Orjaški dežnik (marela) | 60 | 9 (4–16) d | 47 % | 2–8 d | 38 % | 44 % |

## Porazdelitev po razredih DSO (delež opažanj vrste / vseh gliv)

| Vrsta | 0–2 | 3–5 | 6–8 | 9–12 | 13–16 | 17–21 | 22–30 | 31+ |
|---|---|---|---|---|---|---|---|---|
| **vse glive (kontrola)** | 17 % | 17 % | 13 % | 13 % | 9 % | 10 % | 8 % | 13 % |
| Navadna lisička (n=180) | 22 % | 22 % | 19 % | 9 % | 11 % | 5 % | 7 % | 4 % |
| Jurček (n=60) | 15 % | 27 % | 8 % | 10 % | 18 % | 10 % | 10 % | 2 % |
| Rumeni ježek (n=2) | 0 % | 0 % | 50 % | 0 % | 0 % | 50 % | 0 % | 0 % |
| Orjaški dežnik (marela) (n=60) | 15 % | 20 % | 12 % | 17 % | 15 % | 12 % | 5 % | 5 % |

Razmerje (vrsta ÷ vse glive; > 1 pomeni, da je vrsta v tem razredu pogostejša od povprečne glive):

| Vrsta | 0–2 | 3–5 | 6–8 | 9–12 | 13–16 | 17–21 | 22–30 | 31+ |
|---|---|---|---|---|---|---|---|---|
| Navadna lisička | 1.3 | 1.3 | 1.5 | 0.8 | 1.1 | 0.5 | 0.8 | 0.4 |
| Jurček | 0.9 | 1.6 | 0.6 | 0.8 | 1.9 | 1.0 | 1.2 | 0.1 |
| Rumeni ježek | — | — | — | — | — | — | — | — |
| Orjaški dežnik (marela) | 0.9 | 1.2 | 0.9 | 1.3 | 1.6 | 1.2 | 0.6 | 0.4 |

## Samo po suši (7 dni pred dežjem < 8 mm, kot zdaj)

| Vrsta | n | mediana DSO | ≤ 7 d | v oknu modela |
|---|---|---|---|---|
| Navadna lisička | 23 | 8 d | 43 % | 43 % |
| Jurček | 5 | 5 d | 60 % | 20 % |
| Rumeni ježek | 0 | — d | — | — |
| Orjaški dežnik (marela) | 11 | 16 d | 27 % | 27 % |
| vse glive | 3736 | 10 d | 42 % | — |

## Metoda in omejitve

- **Opažanja:** iNaturalist, okvir in meseci so v glavi poročila, 2015–2026, `research`, odprta lokacija, natančnost ≤ 5 km. Shranjena so samo datum in koordinate (zaokrožene na celico 0,25°), ne fotografije in ne uporabniki.
- **Padavine:** Open-Meteo Archive (ERA5), celica 0,25°. ERA5 glaji padavine in zaokroži močne plohe, zato so dogodki bolj mehki, kot jih je videla postaja.
- **DSO** je merjen od začetka ZADNJEGA dogodka. Ob ponavljajočem dežju je zato kratek, čeprav je trosnjake sprožil prejšnji dež. Podskupina »po suši« to zmanjša, a ima malo opažanj.
- **Opažanje ni prvi trosnjak.** Stari trosnjaki (marela, jurček) ostanejo več dni in se še fotografirajo, zato je pravi zamik do prvega trosnjaka verjetno krajši od izmerjenega.
- **Pristranskost opazovalcev:** ljudje hodijo v gozd po dežju, ob vikendih in ob poteh. Kontrola (vse glive) to deloma ujame, a vključuje tudi lišaje in lesne vrste z drugačnim zamikom.
- **Majhni vzorci:** pri vrstah z n < 60 (ježek, štorovka) so razmerja šum. Prag zaupanja v poročilu je n ≥ 30.
- Zaključki so v `docs/inat-lag-studija-zakljucki.md`.
