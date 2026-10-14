# Osnutek: gobe in višina (idea 1)

Stanje: **osnutek za Filipa**, ni objavljen, ni v `blog.json`, ni šel skozi lekturo (`lektura.yml` je izklopljena od 2. 10. 2026). Besedilo sem pisal po `docs/slog-pisanja.md`: vikanje, avtor v ednini, kratek odgovor najprej, naslov do 60 znakov, slovenski narekovaji, decimalna vejica.

## Naslov (izbira)

1. **Isti dež, isti hrib. Zakaj gobe 300 m više zamujajo?** (53 znakov, vendar vsebuje domnevo, ki je ne dokazujemo; glej opombe spodaj)
2. **Sosed hodi 300 m više. Zato najde več gob?** (44, vprašanje, ne trditev)
3. **Vaš gozd ni v dolini. Ali to res šteje?** (39, najbolj nevtralen)

Priporočam 2. Je prizor iz članka o sosedu in ostane vprašanje, ki ga članek pošteno obdela.

**Meta opis (≤ 160 znakov):** Po dežju ni vsak gozd enako daleč. Višina spremeni temperaturo, temperatura pa čas. Kaj o tem vemo in česa ne, na podatkih postaje in iNaturalista.

---

## Besedilo

**Kratek odgovor: verjetno deloma, dokaza pa še nimamo.** Z višino se zrak ohlaja za približno 0,65 °C na 100 m, jurček pa raste v ozkem temperaturnem oknu. Zato se razmere za rast v dolini in 500 m više ne začnejo in ne končajo istočasno. Koliko dni je razlike, iz današnjih podatkov ne moremo izračunati.

Poznate takšnega gobarja? V petek je v dolini našel jurčke, v nedeljo ste vi šli 300 m više po istem makadamu in ste našli travo. Naslednji teden je sosed s tiste višine prinesel košaro.

### 01 — Temperatura

Rečica leži na 366 m, Črnivec na 903 m. Razlika je 537 m, po običajnem gradientu 0,65 °C na 100 m torej okoli 3,5 °C. Za primerjavo: crnivec.si med Črnivcem in Gornjim Gradom (475 m) pričakuje razliko okoli 3,1 °C, v inverziji pa je lahko manjša ali celo obrnjena.

Jurček v našem modelu potrebuje temperaturo tal 3,5–16,5 °C, najbolje 6,5–13,5 °C. Če je v dolini še 15 °C, je 500 m više okoli 12 °C. Isti dan sta torej lahko eno območje v oknu, drugo pa ne. Katero je to, se čez jesen menja.

*[Tu naj stoji drsnik ali preprost graf: izberite višino in poglejte pričakovano temperaturo glede na Rečico. Podlaga je isti gradient, ki ga uporablja stran za Črnivec. Označeno kot ocena, ne meritev.]*

### 02 — Kaj kažejo opažanja

Pogledal sem opažanja jurčka (*Boletus edulis*) v Sloveniji na iNaturalistu: 46 opažanj z oceno »research grade«, natančnost lokacije do 1 km, višina iz DEM (Open-Meteo Elevation). Mediana višine v septembru je 674 m (18 opažanj), v oktobru 466 m (23 opažanj).

Videti je, kot da se jurčki jeseni selijo navzdol, kar bi se ujemalo s hladom. Ampak: 18 in 23 opažanj je premalo za sklep, opazovalci pa hodijo tja, kjer je lažje parkirati, in ne enakomerno po višinah. To je **namig, ne dokaz.** Za lisičke (103 opažanj) tega vzorca ne vidim: od maja do oktobra mediana ostane med 350 in 490 m.

### 03 — Česa ne vemo

- Višinski pasovi vrst v modelu (za jurčka 300–1600 m) so v bazi označeni kot **nekalibrirani**. Model izven pasu zniža indeks za 30 %, vrste pa ne izključi. Pasovi so ocena, ne rezultat meritev.
- Nimamo izmerjenih temperatur tal na različnih višinah v naši dolini, samo zrak (postaja, DRSI na Črnivcu).
- Padavine rastejo z višino, zaradi česar višje po istem dežju lahko pade več. Tega v modelu ne upoštevamo.
- Ne vemo, ali je jesen 2026 tipična.

### 04 — Kaj naj naredite

Ne hitite po vrsti na isto višino. Če je en teden v dolini mimo, poskusite nekaj sto metrov više. Če je pri vas prevroče, počakajte na prvo hladno jutro. Preglejte [gobarsko napoved po območjih](/gobarska-napoved/danes/) in [kalkulator rasti po dežju](/gobarska-napoved/valovi/), kjer se zamiki po vrstah računajo posebej.

Gobe nabirajte samo, če jih zanesljivo poznate. Strupene dvojnice jurčka so opisane na strani [strupene gobe](/gobarska-napoved/strupene-gobe/). Pri dvomu vprašajte mikološko svetovalnico.

*Podatki: postaja IREICA1, DRSI Črnivec, iNaturalist (Slovenija, od 2015 do 14. 10. 2026), Open-Meteo Elevation. Model je ocena in ne napoved najdbe.*

---

## Opombe za Filipa (ne gredo v članek)

- **Prekrivanje:** članek o sosedu ima že razdelek »02 — višina« in članek »meje megle« obravnava višino ob megli. Ta bi bil tretji o višini v štirih dneh. Predlagam, da ga objaviš šele, ko dobiš kaj novega (npr. izmerjene temperature na višini), ali ga združiš v nadaljevanje članka o sosedu.
- **Ni izmišljenih številk.** 3,5 °C je račun (537 m × 0,65 °C), 46/18/23 so iz iNaturalista (skript je bil za enkratno rabo, ni commitan), vse ostalo je iz `species_rules.yaml` in `CLAUDE.md`.
- **Trditev v naslovu 1 (»zamujajo«) podatki ne podpirajo**, zato ga ne priporočam.
- **Za pravo trditev bi bilo treba:** zgodovino meritev DRSI s Črnivca (zdaj je samo živo) ali meritve temperature tal v dveh gozdovih, in širši iNaturalist vzorec (Avstrija, Hrvaška, kot v `inat-lag-studija-siroko.json`).
- **»Uporaba vsebine«:** po `CLAUDE.md` mora ročni analitični članek dobiti tudi to vrstico pod besedilom.
- Pred objavo: `seo_title()`, `geo_audit.py` (skill `seo-preflight`) in, če lektura ostane izklopljena, ročni pregled.
