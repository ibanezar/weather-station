# Zaključki študije zamika (iNaturalist × Open-Meteo), 9. 10. 2026

Podatki in tabele: `docs/inat-lag-studija.md`, `data/inat-lag-studija.json`, skript `tools/study_inat_lag.py`.
**Model (`species_rules.yaml`) ni spremenjen.** Spodaj je, kaj podatki dopuščajo in česa ne.

## Kaj podatki kažejo

Primerjava je z deležem VSEH gliv v istem razredu dni od začetka dežja (DSO). Test z |z| ≥ 2 je grob:
ne upošteva, da opažanja istega dne ali kraja niso neodvisna, zato precenjuje značilnost.

| Vrsta | n | Mediana DSO (Q1–Q3) | Razred z jasnim odstopanjem | Model | Ocena |
|---|---|---|---|---|---|
| Navadna lisička | 104 | 7 (4–14) | **6–8 d: 1,9× več** (z = 3,6), 22–30 d: manj | 8–16 d | **Zamik je verjetno krajši od 8–16.** |
| Jurček | 132 | 10 (4–17) | 17–21 d: 1,6× več, 22–30 d: manj | 8–16 d | Skladno z modelom, razpon širši (do ~21 d). |
| Orjaški dežnik (marela) | 283 | 11 (5–16) | **13–16 d: 1,7× več** (z = 4,1) | 2–8 d | **Podatki ne podpirajo »takoj«.** Glej opombo o starih trosnjakih. |
| Sivorumena mraznica | 52 | 12 (8–23) | 22–30 d: 2,6× več | 3–10 d | Kaže pozneje, a n je majhen. |
| Rumeni ježek | 31 | 10 (4–24) | brez | 8–16 d | Premalo podatkov. |
| Kostanjevka | 89 | 8 (3–16) | brez | 8–16 d | Ni razlike od povprečne glive. |

Vse glive skupaj: mediana DSO okoli 10 dni, 40 % opažanj v tednu po začetku dežja.

## Kaj iz tega sledi

1. **Zamik je širok, ne oster.** Pri vseh vrstah je medkvartilni razpon 10–17 dni. Model z oknom »8–16 dni« je natančnejši, kot dopuščajo podatki.
2. **Lisička je edina vrsta z jasno drugačnim vzorcem od mikoriznega privzetka.** Vrh pri 6–8 dneh in manjšanje po 12 dneh kažeta na zamik približno 4–14 dni. To podpira pripombo bralca, da lisičke niso tako počasne, vendar ne podpira »takoj« (17 % v 0–2 dneh je le malo nad povprečjem).
3. **Jurčka ne spreminjati.** Mediana 10 dni je znotraj 8–16.
4. **Marela v modelu (2–8 d) ni potrjena.** Opažanja so pozneje, vendar je to verjetno deloma pristranskost: veliki klobuki marel ostanejo več dni in se še fotografirajo, zato je izmerjeni zamik zgornja ocena.
5. **Po suši** (kot zdaj) so vzorci majhni (n = 10–45) in se od povprečne glive ne ločijo (jurček mediana 10 d, lisička 9 d). Na tem podatku ne moremo trditi, da je po suši drugače.

## Česa študija NE dokazuje

- Ne meri začetka rasti, ampak čas, ko je gobo kdo opazil in objavil.
- Kontrola (vse glive) je groba. Vključuje lišaje in lesne vrste.
- ERA5 glaji padavine; zadnji dogodek dežja ni nujno tisti, ki je sprožil rast.
- Slovenija v celoti, ne samo Zgornja Savinjska dolina.

## Predlog (ni uveden)

- `CALIBRATION` za lisičko: `fruiting_lag_days` iz 8–16 v **4–14**, z razlogom »iNaturalist 2015–2026, n = 104, mediana 7 d, Q1–Q3 4–14«.
  Pred uvedbo preveriti učinek na backtestu gobarskega indeksa.
- Jurčka, ježka in kostanjevke ne spreminjati.
- Marele in štorovke ne spreminjati na podlagi te študije; za oceno potrebujemo opažanja prvega trosnjaka (npr. iz obrazca z opombo »mlad trosnjak«).
- Če želiš večji vzorec: razširiti na Avstrijo in Hrvaško ter pridobiti opažanja za 2015–2026 po mesecih (maj–julij za lisičko).
