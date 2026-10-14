# Osnutek: gobe in vikend (idea 2)

Stanje: **osnutek za Filipa**, ni objavljen, ni v `blog.json`, brez lekture (`lektura.yml` je izklopljena od 2. 10. 2026). Pisano po `docs/slog-pisanja.md`: vikanje, avtor v ednini, kratek odgovor najprej, naslov do 60 znakov.

Izvirna ideja je bila »Zakaj gobe vedno rastejo, ko ste na dopustu?«. Tega podatki ne morejo preveriti (dopusta ne merimo, indeks pa ima v repozitoriju samo 30 dni zgodovine). Zato je kot članek obrnjena v obliko, ki jo **lahko preverimo**: koledarski račun zamika po dežju in 52 pravih dogodkov z dežjem iz postaje.

## Naslov (izbira)

1. **Prvi vikend po dežju je za jurčke prezgodaj** (43 znakov), priporočam, ker je trditev in jo članek izpolni.
2. **Gobe ne zrastejo, ko ste na dopustu. Šli ste prezgodaj** (54), provokativnejši, a očitek bralcu (vodnik: ne »niste nabirali«).
3. **Jurčki po dežju: zakaj prvi vikend ne šteje?** (44), nevtralen.

**Meta opis (≤ 160 znakov):** V petek dežuje, v soboto greste v gozd, pa ni nič. Po modelu je prvi vikend za jurčke vedno prezgodaj, za lisičke pogosto ravno prav.

---

## Besedilo

**Kratek odgovor: prvi vikend po dežju je za jurčka po našem modelu vedno prezgodaj.** Ni slaba sreča in ni sosedova skrivnost, ampak koledar. Drugi vikend pa je skoraj vedno ravno prav.

Poznate takšen teden? V petek vsa dolina dežuje, v soboto zjutraj greste v gozd, pa so tla mokra in klobukov ni. V torek vas sosed vpraša, ali ste že bili, v soboto pa se pohvali s košaro. Zgleda, kot da gobe rastejo takrat, ko ste v službi ali drugje.

### 01 — Koledar

Model za mikorizne vrste računa, da po sprožilnem dežju mine 8–16 dni, preden zraste trosnjak (jurček), za lisičko pa 4–14 dni. Okno je torej 9 oziroma 11 dni dolgo in vedno vsebuje vsaj en cel vikend. Gobe torej ne rastejo mimo vas. Prvi vikend po dežju pa pade v prvih 1–8 dneh, zato je pri jurčku vedno pred oknom:

| Zadnji deževni dan | Prvi vikend (dan po dežju) | Drugi vikend (dan po dežju) | Prvi vikend v oknu lisičke (4–14) | Drugi vikend v oknu jurčka (8–16) |
|---|---|---|---|---|
| pon | 5., 6. | 12., 13. | da | da |
| tor | 4., 5. | 11., 12. | da | da |
| sre | 3., 4. | 10., 11. | deloma (nedelja) | da |
| čet | 2., 3. | 9., 10. | ne | da |
| pet | 1., 2. | 8., 9. | ne | da |
| sob | 1. (ned), 7. (sob) | 8., 14. | deloma (sobota) | da |
| ned | 6., 7. | 13., 14. | da | da |

*[Tabela naj bo v članku lepo razvrščena in obarvana. Podlaga je čist koledarski račun, brez podatkov postaje.]*

### 02 — Primer: september 2026

V Rečici je 10. septembra padlo 85,1 mm, 11. septembra še 35,6 mm, skupaj 120,7 mm. Zadnji deževni dan je bil petek. Prvi vikend (12. in 13. septembra) je bil 1. in 2. dan po dežju, za jurčka torej močno prezgodaj. Okno jurčka je po modelu trajalo od 19. do 27. septembra in vsebovalo oba naslednja vikenda (19.–20. in 26.–27. septembra). O tem, zakaj jurčkov kljub 120 mm vseeno ni bilo, piše [prejšnji članek](/blog/zakaj-po-120-mm-dezja-ni-jurckov-0918.html).

### 03 — Kaj pravijo padavine postaje

Pregledal sem padavine postaje IREICA1 od avgusta do novembra v letih 2020–2026. Dogodek dežja je skupina dni z vsaj 3 mm (vrzel največ en dan), skupaj vsaj 20 mm. Takih dogodkov je bilo 52. Pri vsakem sem preveril, kje po zadnjem deževnem dnevu pade prvi vikend.

- Pri **jurčku** prvi vikend v oknu 8–16 dni ni bil v nobenem od 52 dogodkov. Drugi vikend je bil v oknu v vseh 52. To sicer sledi iz koledarja, a vidno je tudi, da se gobar brez tega znanja ob vsakem dežju odpravi prvi vikend.
- Pri **lisički** je bil prvi vikend v oknu 4–14 dni v 37 od 52 dogodkov, torej v okoli sedmih od desetih. Pri petkovem ali četrtkovem dežju je prezgodaj.

Dež sam na dan v tednu ne gleda. Dogodki so se začeli v vseh dnevih, najpogosteje med tednom (četrtek 12, sreda 9 od 52).

### 04 — Česa ne vemo

- Zamiki (8–16 dni za jurčka, 4–14 za lisičko) so **modelska ocena**, v bazi označena kot nekalibrirana. Za lisičko jih podpira analiza iNaturalista, ki kaže mediano 6–7 dni po začetku dežja, za jurčka je podpora šibkejša.
- Opažanje ni prvi trosnjak: stari trosnjaki se fotografirajo še dolgo, zato je zamik v opažanjih zgornja ocena.
- Dopusta ne merimo. Članek ne trdi, da gobe ne rastejo, ko ste v službi, ampak da je vzorec delno posledica koledarja.
- Model ne pozna vašega gozda. Višina, tla in suša pred dežjem lahko okno premaknejo za več dni ([kalkulator](/gobarska-napoved/valovi/) vzame nekaj tega v račun).

### 05 — Kaj naj naredite

Če dežuje v četrtek ali petek, **prvi vikend preskočite** (za lisičke ga lahko izkoristite). Pojdite drugi vikend, ko je jurček po modelu v oknu. V [kalkulator rasti po dežju](/gobarska-napoved/valovi/) vpišite datum dežja in količino, pa vam pokaže okna po vrstah.

Gobe nabirajte samo, če jih zanesljivo poznate. Dvojnice jurčka in druge strupene vrste so na strani [strupene gobe](/gobarska-napoved/strupene-gobe/).

*Podatki: postaja IREICA1 (history.json, avgust–november 2020–2026), model Meteorec (zamiki po skupinah), iNaturalist × Open-Meteo (analiza zamika lisičke).*

---

## Opombe za Filipa (ne gredo v članek)

- **Prekrivanje:** na blogu so že štirje članki o zamiku po dežju (»Zakaj po dežju gobe ne zrastejo takoj« 21. 7., »Kdaj po tednu dežja zrastejo gobe« 22. 8., »Trije valovi« 11. 9., »Koliko dni po dežju rastejo gobe« 9. 10.). Novo je samo vikend kot zorni kot, zato je smiselno kratko besedilo in tabela, ne še ena razlaga zamika. Če ti je zamika dovolj, ga prihrani za pomlad.
- **Koledarski del je aritmetika**, ne odkritje. Zato je v tekstu rečeno tako. Pravi podatek sta 52 dogodkov (postaja) in primer 10.–11. 9.; številka 37 od 52 za lisičko je odvisna od definicije dogodka in se ob drugi definiciji (začetek namesto konca dogodka) spremeni na 33. Pustil sem koncem dogodka, v članku pa je definicija napisana.
- **Nič ni izmišljeno**: 120,7 mm = 85,1 + 35,6 (history.json), 52/37 iz history.json, tabela iz koledarja. Skript je bil enkraten in ni commitan.
- **Okno 8–16 za jurčka** je v `species_rules.yaml` označeno »TODO: kalibriraj«. Pred objavo preveri, ali je kalibracija vmes narejena.
- **Pod besedilom** mora biti vrstica »Uporaba vsebine« (CLAUDE.md, ročni analitični članek). Pred objavo poženi `seo-preflight`.
- **Vrstica v tabeli »sre«/»sob«** je poenostavljena (»deloma«); pri objavi preveri, da se ujema z računom: sreda → vikend 3., 4. dan (lisička 4–14: samo nedelja), sobota → 1. in 7. dan.
