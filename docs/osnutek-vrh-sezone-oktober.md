# Osnutek: kdaj je vrh gobarske sezone (iNaturalist, 2020–2025)

Stanje: **osnutek za Filipa**, ni objavljen, ni v `blog.json`, brez lekture (`lektura.yml` je izklopljena od 2. 10. 2026). Pisano po `docs/slog-pisanja.md`.

**Podatki so že izračunani in preverjeni pred pisanjem** (`tools/study_inat_glive_po_tednih.py` → `data/inat-glive-po-tednih.json`, samo agregati po tednih; 147 tednov, 2020–2026). **Popravek 14. 10. 2026:** v prvi različici sem skupino 47169 imel za »Fungi«, v resnici je to Basidiomycota (prave gobe). Zdaj so ločeno šteti Basidiomycota, klobučnice (Agaricomycetes) in celo kraljestvo gliv. Vrh je v vseh treh enak, zato je zaključek isti, opis pa je popravljen. Dve prejšnji hipotezi (povezava deleža gliv z dežjem v zadnjih treh tednih, upad po prvi slani) sem preveril in ju **zavrgel**, ker nista dali čistega rezultata; ta članek stoji samo na tem, kar je preverjeno.

## Naslov (izbira)

1. **Vrh gobarske sezone je oktobra. Šest let podatkov** (46), priporočam
2. **Kdaj je v Sloveniji vrh gobarske sezone?** (40), nevtralnejši
3. **Ste mislili, da je gobe konec? Oktober pravi drugače** (48), provokativnejši

**Meta opis (≤ 160 znakov):** V vsakem od šestih let (2020–2025) je bil teden z največ opaženimi gobami v Sloveniji med 7. in 27. oktobrom, ne septembra. Podatki iNaturalista.

---

## Besedilo

**Kratek odgovor: po fotografijah gob v Sloveniji je vrh oktobra, ne septembra.** V vsakem od šestih let, 2020–2025, je teden z največ opaženimi gobami padel med 7. in 27. oktobrom. Oktobra so bile gobe 25–44 % vseh opažanj na iNaturalistu v Sloveniji, septembra 10–32 %.

Poznate občutek, da je gobarske sezone konec, ko mine septembrski vrh? Podatki iz šestih let tega ne podpirajo.

### 01 — Kaj smo prešteli

Na iNaturalistu, spletni zbirki opažanj narave, sem za vsak teden od julija do novembra prešteval, koliko opažanj v Sloveniji je pravih gob in koliko je vseh opažanj (rastline, žuželke, ptice …). Prave gobe so tu deblo *Basidiomycota*: klobučnice (jurčki, lisičke, mušnice …), pa tudi trdoživke na lesu, želatinaste glive in rje. Ne vsebuje zaprtotrosnic (smrčki, tartufi) in plesni, lišajev pa skoraj nič. Skoraj vse so klobučnice (*Agaricomycetes*): njihov vrh je v istih tednih. Preštel sem samo skupna števila, posameznih opažanj nisem bral. Teden se začne 1. julija in teče po sedem dni.

Absolutna števila med leti niso primerljiva: opazovalcev je vsako leto več. Zato gledam **kdaj** je vrh in **kolikšen delež** vseh opažanj so gobe.

### 02 — Kdaj je vrh

| Leto | Teden z največ opaženimi gobami | Število opažanj v tem tednu | Delež gob: september | oktober | november |
|---|---|---|---|---|---|
| 2020 | 21.–27. 10. | 221 | 16 % | 41 % | 44 % |
| 2021 | 14.–20. 10. | 144 | 10 % | 25 % | 17 % |
| 2022 | 7.–13. 10. | 361 | 32 % | 44 % | 26 % |
| 2023 | 21.–27. 10. | 413 | 10 % | 39 % | 32 % |
| 2024 | 7.–13. 10. | 238 | 13 % | 30 % | 21 % |
| 2025 | 21.–27. 10. | 395 | 16 % | 26 % | 16 % |

Tudi če namesto števila gledam teden z največjim deležem gob, pade vrh med 30. septembrom in 3. novembrom. Oktober je v vseh šestih letih višji od septembra. Novembra delež v petih od šestih let spet pade (izjema je 2020). Enako velja, če štejem samo klobučnice, ali če vzamem celo kraljestvo gliv: teden z največ opažanji je v vseh treh skupinah isti, v vseh šestih letih.

*[Tu naj stoji graf: tedenski delež gob po tednih, vsako leto ena črta, z označenim oktobrom. Barve naj gredo skozi validator (skill `dataviz`).]*

### 03 — Se ujema z modelom?

Ne gre za isto stvar, a ni v nasprotju: naš gobarski indeks za Rečico je bil v oktobru višji kot v septembru v 3 od 4 celih let (2023: 81,0 proti 77,6; 2024: 91,3 proti 79,5; 2025: 86,9 proti 83,1). Leta 2022 je bil obratno (82,7 proti 89,3). Indeks je modelska ocena in zajema tudi celoletne vrste, zato ni dokaz.

### 04 — Letošnja jesen

Letos je bilo do 13. oktobra v posameznih tednih opaženih 136 (9. septembra), 221 (16. septembra), 195 (23. septembra) in 236 (30. septembra) gob. Delež v septembru je znašal 14 %, kar je v običajnem razponu (10–32 %). Teden 7.–13. oktobra ima za zdaj 142 opažanj, a je ta številka še podcenjena, ker opazovalci opažanja nalagajo z zamudo. Ali bo letos vrh v oktobru, še ne vemo. V prejšnjih letih je padel prav v teh tednih (7.–27. oktober).

### 05 — Česa ne vemo

- **To so fotografije, ne košare.** Opažanje gobe ni nabirka in ne pove, ali je goba užitna. Vključene so tudi nejestne vrste in trdoživke na lesu.
- **Delež ima svojo past.** Novembra upade opazovanje žuželk in rastlin, zato se delež gob poveča, tudi če jih ni več. Zato sem pogledal tudi absolutno število in vrh je tudi tam v oktobru.
- **Šest let je malo.** Zaključka »vedno oktobra« ne smemo povleči. Šest od šestih je zanimivo, ni pa zakon.
- **To je Slovenija kot celota.** Rečica in višje lege imajo lahko drugačen vrh. O višini piše [prejšnji članek](/blog/zakaj-sosed-vedno-najde-gobe.html).
- **Jurček posebej** je predrobno za sklep: v Sloveniji je od 2015 le 46 opažanj z natančno lokacijo, 18 v septembru in 23 v oktobru.
- **Povezave z dežjem** v teh podatkih ne bom trdil. Preverili smo, ali se delež gob povezuje z dežjem zadnjih treh tednov, in je povezava šibka (korelacija 0,28), brez jasnih pragov.

### 06 — Kaj naj naredite

Ne odpišite oktobra. Poglejte [gobarsko napoved za danes](/gobarska-napoved/danes/) in [kalkulator rasti po dežju](/gobarska-napoved/valovi/), ki upošteva, kdaj je deževalo. Gobe nabirajte samo, če jih zanesljivo poznate. Dvojnice in strupene vrste so na strani [strupene gobe](/gobarska-napoved/strupene-gobe/).

*Podatki: iNaturalist (Slovenija, deblo Basidiomycota, število opažanj po tednih, 1. 7.–30. 11. 2020–2025, 2026 do 13. 10.), postaja IREICA1 (dež), gobarski model Meteorec.*

---

## Opombe za Filipa (ne gredo v članek)

- **Zakaj ta ideja drži:** preverjeno pred pisanjem. 6 od 6 let ima vrh po številu v 7.–27. oktobru (za Basidiomycota, klobučnice in celo kraljestvo); razpon deležev po mesecih je iz agregatov v JSON-u; novembrski upad v 5 od 6.
- **Zavrnjeno med preverjanjem (nič v članku, razen ene opombe):** delež gob ~ dež zadnjih 3 tednov (Spearman 0,28, bootstrap po letih 0,07–0,44, binov ni mogoče razločiti), upad po prvi slani (3 od 6 let), višina in vikend (prejšnji osnutki).
- **Neprijetno za priznati:** to je tudi odgovor na »kdaj je vrh«, ne »kako se pripraviti«. Praktični nasvet je skromen (ne odpišite oktobra). Če ti je to premalo, članek lahko ostane kratka objava na FB z grafom.
- **iNaturalist ≠ gobarji.** Fotografira jih drugačna skupina kot nabira. Opozorilo je v članku, pred objavo preveri ton.
- **Taksoni (preverjeno):** Basidiomycota (47169), Agaricomycetes (50814) in celo kraljestvo Fungi (47170) imajo vrh v istih tednih; deleži po mesecih so skoraj enaki (npr. oktober 2025: 26 %, 26 %, 28 %). Razlika je samo pri vrhu po deležu v 2024 (Basidiomycota 14. 10., klobučnice in kraljestvo 4. 11.). V tabeli članka so Basidiomycota.
- **Prekrivanje z objavljenimi članki:** »Jesenski vrh gob 2026« (22. 9.) primerja samo septembre po modelu in ne trdi, da je vrh septembra; ta članek ga dopolnjuje in z njim ni v nasprotju.
- **Pred objavo:** vrstica »Uporaba vsebine«, `seo-preflight`, graf po `dataviz`, ročni pregled slovnice (lektura izklopljena).
