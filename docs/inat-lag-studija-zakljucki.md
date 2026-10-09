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

---

# Razširitev (9. 10. 2026): širše območje in zgodnja sezona

Tabele: `docs/inat-lag-studija-siroko.md` (jug Avstrije, Slovenija, sever Hrvaške, SV Italija, Z Madžarska, avgust–november, ~37.000 opažanj gliv za kontrolo)
in `docs/inat-lag-studija-poletje.md` (isto območje, maj–julij, za lisičko, jurčka, ježka, marelo). Vzorec je okoli 2,5× večji.
Test |z| ≥ 2,5 je grob (opažanja niso neodvisna), zato ga beri kot smer, ne kot dokaz.

| Vrsta | n (SI → široko) | Mediana DSO (Q1–Q3), široko | Jasno odstopanje (široko) | Model | Sklep |
|---|---|---|---|---|---|
| Navadna lisička | 104 → **255** | 7 (4–14) | 6–8 d: 1,8× (z = 4,8); 22–30 d: 0,3× (z = −3,7) | 8–16 d | **Potrjeno.** Isti vzorec kot v Sloveniji, jasneje. |
| Lisička, maj–jul | **180** | 6 (3–13) | 6–8 d: 1,5× (z = 2,6); 31+ d: 0,4× | 8–16 d | **Še krajši zamik poleti.** |
| Jurček | 132 → **443** | 10 (4–17) | 17–21 d: 1,4× (z = 2,9); po 22 d manj | 8–16 d | Skladno z modelom, razpon širši. |
| Rumeni ježek | 31 → **84** | 10 (6–21) | 6–8 d: 1,9× (z = 3,0) | 8–16 d | Kaže na krajši zamik kot model, vendar je n še majhen. |
| Kostanjevka | 89 → **294** | 10 (4–19) | 3–5 d: 1,4× (z = 2,9) | 8–16 d | Zgodnejša od modela, vendar zadržano. |
| Orjaški dežnik (marela) | 283 → **651** | 11 (6–17) | **13–16 d: 1,7× (z = 6,4)**; 0–2 d: 0,7× | 2–8 d | **Potrjeno: po opažanjih NI hitra.** |
| Sivorumena mraznica | 52 → **107** | 12 (6–19) | 9–12 d: 1,6× (z = 2,6) | 3–10 d | Pozneje od modela, rahlo. |

## Kaj se je spremenilo

- **Lisička je zdaj najbolje podprta ugotovitev.** Pri n = 255 (jesen) in n = 180 (poletje) je vrh pri 6–8 dneh in opazen upad po ~3 tednih. Zamik 8–16 dni v modelu se ne ujema z nobenim od obeh.
  **Predlog: `fruiting_lag_days` iz 8–16 v 4–14** (jesen Q1–Q3 = 4–14, poletje 3–13). Ni uvedeno.
- **Marela ni »takoj«.** Pri n = 651 je razmerje v razredu 0–2 dni 0,7×, v razredu 13–16 dni 1,7×. Model (2–8 d) in komentar bralca (»marele so takoj«) se v podatkih ne potrdita. Opomba o starih trosnjakih ostaja: klobuki ostanejo več dni, zato je to zgornja ocena.
- **Jurček ostane.** Mediana 10 dni je znotraj 8–16, večji vzorec ne spremeni slike.
- **Po suši** (7 dni pred dežjem < 8 mm): lisička n = 71, mediana 7 d (jesen), n = 23, 8 d (poletje); v oknu modela 31 % in 43 %. Brez jasne razlike od običajnega vzorca.

## Previdnost (nespremenjeno)

DSO je merjen od zadnjega dogodka dežja, opažanje ni prvi trosnjak, kontrola vključuje tudi lišaje in lesne vrste, ERA5 glaji padavine, in območje je širše od najine doline (sosednje podnebje). Zaključki veljajo za regijo, ne za Rečico.

## Predlog (ni uveden)

1. `CALIBRATION` za **lisičko**: `fruiting_lag_days` 4–14, razlog: »iNaturalist 2015–2026, n = 255 (avg–nov) in 180 (maj–jul), mediana 6–7 d, Q1–Q3 3–14«. Pred uvedbo backtest gobarskega indeksa.
2. Jurčka, ježka in kostanjevke ne spreminjati; pri ježku in kostanjevki počakati na večji vzorec ali opažanja iz najine doline.
3. Marele (2–8 d) ne spreminjati samo po tej študiji, ampak razmisliti o razmerju med »prvim trosnjakom« in »opaženo gobo«; za oceno potrebuje opažanja mladih trosnjakov.
