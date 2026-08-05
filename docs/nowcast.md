# Nowcasting neviht in toče

Kaj pride nad izbrano vas v naslednjih ~45 minutah, izračunano iz **radarske
slike ARSO**, ne iz modelske napovedi. Zato "nowcast" in ne "napoved".

```
ARSO si0-rm-anim.gif ──▶ Worker (cron /5 min) ──▶ R2: nowcast/latest.json
   19 posnetkov, 5 min          dekodiranje GIF          │
                                ocena premika celic      ├─▶ GET /nowcast (stran)
                                ETA po vaseh             └─▶ web push (po vaseh)
```

Vse skupaj je v `worker.js` (razdelek "Nowcasting neviht in toče"), izbirnik
vasi pa v `app.js` (`initNowcast` / `loadNowcast`).

## Vir

`https://meteo.arso.gov.si/uploads/probase/www/observ/radar/si0-rm-anim.gif`

- 821 × 660 px, 32-barvna globalna paleta, brez lokalnih palet
- 23 okvirjev, od tega **19 različnih** — zadnji štirje so podvojeni, ker se
  animacija na koncu ustavi. Ločimo jih po vžganem časovnem žigu, ne po
  vsebini: padavine se med posnetkoma lahko slučajno ne spremenijo, žig pa se
  vedno.
- **prvi okvir je prepleten** (interlaced), ostali niso
- disposal = 1 (okvirji se seštevajo), prosojni indeks se med okvirji
  **spreminja in zavzame tudi barve padavin** (15, 16, 17) — brati ga je treba
  iz vsakega GCE posebej, sicer si pokvariš prav najmočnejša jedra
- nov posnetek vsakih 5 minut (`cache-control: max-age=300`); svežino
  preverjamo prek glave `last-modified` in slike, starejše od 20 minut, ne
  uporabimo

ARSO zavrača zahteve z oblačnih IP-jev, Cloudflare pa spusti skozi — isti
razlog, kot ga ima `tools/generate_toca_page.py` za klic prek Workerja.

## Lestvica

Legenda na sliki je **MAX RAINFALL RATE v mm/h**, ne dBZ. 15 stopenj, od
temno modre do vijolične. Odčitano neposredno iz barvne skale v sliki
(y = 33, x = 602–810); oznake `.5 1 2 5 15 50 100` ležijo na vsakem drugem
polju (2, 4, 6, 8, 10, 12, 14), vmesna polja so geometrijska sredina sosedov.

| stopnja | mm/h | uporaba |
|---|---|---|
| 6  | 2   | `RADAR_L_RAIN` — dež |
| 10 | 15  | `RADAR_L_STORM` — nevihta |
| 12 | 50  | `RADAR_L_CORE` — jedro, ki zmore točo |

Paleto preslikamo prek RGB in ne prek fiksnih indeksov, da preživimo
morebitno prerazporeditev barvne tabele pri ARSO.

## Georeferenca

Navadna enakopravokotna projekcija — `x = 153.013374·lon − 1849.035845`,
`y = −222.729262·lat + 10607.713236`.

Umerjeno na 14 mest, katerih oznake so vrisane v sliko (Ljubljana, Maribor,
Ptuj, Slovenj Gradec, Jesenice, Beljak, Celovec, Lienz, Bovec, Varaždin,
Trbovlje, Videm, Idrija, Pordenone). Mesta so označena s **kolobarjem
polmera 2 px** v barvi (96, 96, 96), kar jih da samodejno poiskati.

RMS napake je **1,7 px ≈ 0,85 km**, ločljivost pa ~0,50 km/px v obeh oseh —
kar se ujema s 500-metrsko mrežo, na kateri tak kompozit običajno stoji, in
je neodvisna potrditev, da je prilagoditev pravilna.

Naslovna vrstica z legendo (prvih 44 vrstic) ni padavina in jo pobrišemo.

## Ocena premika

Ničelno-povprečna navzkrižna korelacija med posnetkoma, najprej na 4× zmanjšani
mreži (iskanje ±10), nato izostritev pri polni ločljivosti (±3).

Dve stvari, ki nista očitni:

1. **Osnova mora biti ~15-minutna, ne 5-minutna.** V 5 minutah se celica
   premakne dober piksel, kar je pod ločljivostjo mreže, in iskanje vrne
   ničelni zamik.
2. **Vsota kvadratov razlik ne deluje.** Ob rasti celic (tipično za poletno
   konvekcijo) potisne najboljši zadetek na ničelni zamik. Korelacija z
   odštetim povprečjem je na rast in upadanje odporna.

## Kaj pride nad vas

Kar bo ob času *t* nad vasjo, je zdaj na legi `vas − hitrost·t`. Vzorčimo
največjo stopnjo v okencu ~3 km okoli te točke (`RADAR_NEAR_PX`), kar dopusti
napako lege in nihanje celice. Ker okence meri območje in ne točke, se
opozorilo sproži, ko **čelo** celice doseže okolico vasi — torej nekaj minut
prej, kot bi celica zadela središče vasi. To je namerno: pri opozorilu je
zgodaj varna smer.

Toča = jedro ≥ 50 mm/h na površini vsaj ~1,5 km² **in** ugodno okolje
(CAPE ≥ 700 J/kg, indeks dviga ≤ −3 iz Open-Meteo, en klic za celotno dolino —
zračna masa je na 30 km praktično enaka). Radar sam po sebi toče od močnega
naliva ne loči; pogoj okolja je tu zato, da odreže najbolj očitne lažne alarme.

## Kaj kaže preverjanje

Hindcast na primeru 26. 7. 2026 (napoved iz starejših posnetkov, ocenjena proti
temu, kar se je dejansko zgodilo), na 10-km okolici vasi:

| obzorje | prag | POD | FAR |
|---|---|---|---|
| 30 min | dež ≥ 2 mm/h | 0,73 | 0,20 |
| 30 min | nevihta ≥ 15 | 0,61 | 0,33 |
| 30 min | jedro ≥ 50 | 0,42 | 0,40 |
| 45 min | jedro ≥ 50 | 0,26 | 0,60 |

Iz tega sledita dve odločitvi, vgrajeni v kodo:

- **obzorje za nevihto in točo je 30 minut**, za dež 45 (`RADAR_HORIZON_*`).
  Pri 45 minutah signal za jedro razpade (FAR 0,60).
- **zahtevamo najmanjšo površino jedra** (`RADAR_CORE_MIN_PX` = 6 px ≈
  1,5 km²). FAR pade z 0,435 na 0,396 brez izgube CSI — odreže posamezne
  šumne piksle.

Pomembna opozorila k tem številkam:

- To je **en dan in ena vremenska situacija** (počasna, hitro rastoča
  konvekcija). Jemlji jih kot red velikosti, ne kot oceno kakovosti storitve.
- Na piksel natančno je advekcija komaj boljša od persistence, pri 45 minutah
  pa slabša. Smiselna je šele na ravni **okolice vasi**, kar je tudi vprašanje,
  na katerega storitev odgovarja.
- Vsak drugi ali tretji alarm za točo bo lažen. To je vgrajena lastnost
  posrednega sklepanja iz enopolarizacijskega kompozita, ne napaka v kodi —
  zato je besedilo obvestila zadržano ("pripravi se, a ne paniči") in zato ima
  toča ločen, strožji prag od nevihte.

## Vasi in zasebnost

Seznam vasi je v `NOWCAST_VASI` v `worker.js` in je edini vir resnice; stran ga
dobi prek `GET /nowcast/vasi`. Vsak vnos ima tudi `loc` (mestnik), da so
obvestila slovnično pravilna — vsi stavki so grajeni z mestnikom, ker se
edini ujema z vsemi imeni na seznamu ("v Mozirju", "na Polzeli", "v Lučah").

Hranimo **samo izbrano vas s seznama, nikoli GPS**. Dokler uporabnik ne vklopi
obvestil, izbira ostane v `localStorage` in se na strežnik sploh ne pošlje.
Naročnine od prej vasi nimajo — zanje privzeto velja Rečica, sicer bi po
uvedbi tiho nehale dobivati napovedna obvestila.

## Vzdrževanje

Kar se lahko pokvari, če ARSO spremeni sliko:

- **druge barve** → `_radLut` ne najde ujemanja in vse stopnje so 0
  (nowcast tiho utihne). Popravek: osveži `RADAR_LEVEL_RGB` iz legende.
- **druga velikost ali izsek** → georeferenca se premakne. Popravek: znova
  poišči kolobarje mest in prilagodi `RAD_AX/BX/AY/BY`.
- **drug razmik posnetkov** → `RAD_STEP_MIN`. Preveri žig v sliki
  (x = 86, 93 za uro; 107, 114 za minute; pisava 6 × 10 px, korak 7 px).

Modelski `_cronCheckPrecipNowcast` ostaja kot rezerva: požene se le, kadar
radar odpove, sicer bi za isti dogodek poslali dve obvestili.

# ICON napoved in sledenje nevihtnim celicam

Dve ločeni razširitvi lastnega kompozitnega radarja ("Lasten radar padavin",
worker.js razdelek za `COMP_*`/`_radarComposite*`, ne zgornji ARSO-GIF
nowcast). Obe delita cel del kode s kompozitom in obe tečejo v istem
5-minutnem cronu (`_cronRenderRadarComposite`).

## ICON — nadaljevanje časovnice po zadnji uri radarja

Kartica "Lasten radar padavin" pred tem ni imela nowcast-segmenta — animacija
je pokrivala samo pretekle posnetke zadnje ure. Po zadnji uri radarja se zdaj
na pogledu **"savinja"** (Zgornja Savinjska dolina) nadaljuje s 6 urami
napovedi modela ICON (DWD, ~2 km), izrisane po isti barvni lestvici kot
radar, tako da je prehod viden kot en trak, ne dva ločena vira.

```
Open-Meteo /v1/forecast (batch, 48 točk, ICON-D2) ──▶ _iconCached (cron, ~urno)
                                                          │
                                          R2: icon/frame-*.png, icon/latest.json
                                                          │
                     GET /radar-composite.json → napoved  ├─▶ GET /icon-precip (PNG okvir)
```

**Zakaj ICON, ne AROME.** Prvotni predlog je bil Météo-France AROME (bliže
ARSO-jevemu ALADIN-u po družini modela). Preverjeno neposredno pred pisanjem
kode: `models=meteofrance_arome_france_hd` in `..._france` za Rečico
(46,3258, 14,9211) oba vrneta prazne/napačne odgovore — Slovenija je izven
dosega obeh AROME domen prek Open-Meteo. `icon_d2` vrača prave vrednosti,
zato je primarni model; `icon_eu` (širši, grobejši) je rezerva, če
`icon_d2` kdaj odpove.

**Mreža in izris.** Open-Meteo nima gotovega polja, samo točkovni API — zato
`_iconGrid` vzorči 8×6 točk enakomerno čez pogled "savinja" (rahlo znotraj
robov, brez ekstrapolacije), `_iconFetchModel` jih prenese v **enem** batch
klicu (vejico ločen `latitude=`/`longitude=`, potrjeno na dejanski
Open-Meteo API: odgovor je array, en objekt na točko, vsak s svojima
`latitude`/`longitude`). Ujemanje nazaj na zahtevano točko je po najbližji
razdalji, ne po vrstnem redu — Open-Meteo vrstnega reda batcha ne
dokumentira. `_iconFrame` bilinearno interpolira to grobo mrežo v PNG,
enako kot `_arsoSample`, in gre skozi isto `_compLevel`/`_COMP_SCALE`
paleto kot kompozit.

**Osveževanje.** Worker nima zanesljivega vpogleda v urnik ICON-D2 teka, zato
`_iconCached` samo preveri, ali je manifest za trenutno UTC uro (`runStamp`)
že svež; če je, cron te ure ne naredi ničesar (poceni no-op na večini
petminutnih tikov). Vsak nov urni tek v celoti nadomesti prejšnjega, zato
`_iconPrune` nima časovnega cutoffa kot `_radarCompositePrune` — zbriše
preprosto vse, kar ni trenutni `runStamp`.

**Gladek propad.** Če `_iconFetchModel` ne vrne uporabnih podatkov (oba
modela), cron manifesta ne posodobi in ne vrže napake. `/radar-composite.json`
vrne `napoved: null`, če manifesta ni ali je starejši od 90 minut — časovnica
se v tem primeru tiho skrči nazaj na samo pretekli radar, brez vidne napake.

## Sledenje nevihtnim celicam

Nowcast zgoraj oceni **en skupen premik za celotno polje** in ga uporabi na
oknu okoli vsake vasi. To je nekaj drugega: prepozna **posamezne** konvektivne
celice kot povezana območja nad pragom nevihte in jim sledi med posnetki —
vsaka dobi svoj id, lego, površino, jakost, smer in hitrost. Endpoint
`GET /radar-cells.json`.

**Cron: lasten, zamaknjen urnik.** Sprva je `_cronRenderRadarCells` tekel
znotraj istega 5-minutnega cron tika kot ICON (glej zgoraj) in kompozitni
izris, delil OPERA/ARSO prenos s slednjim, da se ne podvoji. V produkciji se
zaradi tega **ni nikoli izvedel do konca** — vsi `ctx.waitUntil()` znotraj ene
`scheduled()` invokacije si delijo en časovni/CPU proračun, in kot zadnja
dodatka v vrsti (za pragovnim alarmom, nowcastom, dežjem, aurora in
kompozitom) preprosto nista dobila priložnosti. Rešitev: `_cronRenderIcon` in
sledenje celicam zdaj tečeta na **lastnem, za 2 minuti zamaknjenem** cron
urniku (`"2-59/5 * * * *"`, `wrangler.toml`, ločen od `"*/5 * * * *"` zgoraj;
`scheduled()` loči po `event.cron`). Cena: OPERA/ARSO za "sirok" se zdaj
prenese neodvisno namesto deljeno s kompozitnim izrisom — sprejemljivo, ker
gre prek istega `cf:{cacheTtl}` robnega predpomnilnika, torej brez dodatne
obremenitve izvora.

**Polje in projekcija.** Zaznavanje teče na lastni, enakomerni lon/lat mreži
(`CELL_GRID_DEG`, privzeto 0,015° ≈ 420×230 čez cel "sirok" izsek) — ne na
Web Mercator piksel-prostoru izrisa, kjer km/piksel ni enakomeren — da
sledenje deluje neodvisno od tega, kateri pogled ima obiskovalec odprt.
`_cellSample` vzorči OPERA in ARSO po isti projekciji in prioritetnem pravilu
kot `_radarComposite`-jeva izrisna zanka (ARSO znotraj `COMP_R_JEDRO`, OPERA
sicer), a po eni točki namesto po vrstici. **Koda je namerno vzporedna, ne
deljena** s tisto zanko, da izris kompozita ostane nedotaknjen — če se
prioritetno pravilo tam kdaj spremeni, uskladi tudi tu.

**Prag in oznaka celice.** `CELL_STORM_MMH = 15` in `CELL_CORE_MMH = 50` sta
isti mm/h vrednosti kot `RADAR_LEVEL_MMH[RADAR_L_STORM-1]` in
`[RADAR_L_CORE-1]` zgoraj, samo izpisani eksplicitno — `RADAR_L_STORM`/`_CORE`
sta indeksa v ARSO-GIF-ovi lastni 15-stopenjski lestvici in ne veljata na tej
mreži. `_cellLabel` je iterativno (eksplicit sklad, ne rekurzija — globina
klicnega sklada je resnično tveganje na ~420×230 mreži) 8-povezano
flood-fill; `CELL_MIN_AREA_KM2 = 1,5` (isti koncept kot `RADAR_CORE_MIN_PX`,
samo prenešen na to ločljivost mreže) odreže posamezne šumne piksle.

**Sledenje med posnetki.** Pohlepno ujemanje najbližjega centroida znotraj
`CELL_MATCH_RADIUS_KM = 20` (dovolj za nevihtno hitrost pri 5-minutnem
koraku), brez napovedi premika. Prvotna zamisel je bila uporabiti obstoječo
`_radMotion` kot napovedni prior — opuščeno, ker `_radMotion`-ova pretvorba
v km/smer uporablja `RAD_KM_X/Y` (km na piksel ARSO-GIF-ove lastne mreže) in
bi na tej, drugačni mreži vrnila napačne vrednosti brez prilagoditve; pri
5-minutnem koraku sam iskalni polmer zadošča. To **ni** Madžarski algoritem,
samo "dovolj dobro, dokumentirana omejitev" — enako kot že drugod v tem
cevovodu. Znane omejitve: brez ponovne identifikacije po popolni zakritvi
(celica, ki izgine za >`CELL_MAX_MISSES` posnetkov, ob vrnitvi dobi nov id),
brez logike za cepitev/združitev celic (celica, ki se razcepi na dve, obdrži
en id in požene eno novo, ali pa obe zgrešita ujemanje in dobita novi id-ji,
odvisno od premika centroida).

**Smer.** `smer` je kompasni azimut (0 = sever, urni kazalec), izračunan iz
resničnega geografskega premika centroida (`atan2(vzhod_km, sever_km)`) — za
razliko od `_radMotion`, kjer je zaradi ARSO-pikslovega obrnjenega predznaka
(piksel Y raste proti jugu) v formuli negacija; tu je ni, ker sta `dx`/`dy`
že prava geografska km.

**ETA do postaje.** `_cellEta` za vsako celico s poznano smerjo/hitrostjo
izračuna najbližji prehod (closest point of approach) njene premočrtne
trajektorije mimo postaje — standardna CPA formula `t_cpa = -(V·C0)/|V|²`,
kjer je `C0` lega celice relativno na postajo (vzhod/sever, km) in `V`
hitrostni vektor iz istega `smer`/`kmh`. `t_cpa ≤ 0` pomeni, da se celica že
oddaljuje (najbližji prehod je v preteklosti) — brez ETA. Poroča se samo, če
je napovedan najbližji prehod znotraj `CELL_ETA_RADIUS_KM` (15 km, "gre proti
dolini") in `CELL_ETA_MAX_MIN` (90 min — dlje linearna ekstrapolacija ni
zanesljiva, glej "Ocena premika" zgoraj) ter je hitrost nad `CELL_ETA_MIN_KMH`
(3 km/h — pod tem je smer preveč šumna). Najbolj nujna celica (najkrajši ETA)
gre v `prihaja` na vrhu odgovora `/radar-cells.json` — namerno **ne**
`opozorilo`, ker to ime že uporablja mehek odpovedni odgovor (niz z
razlogom), različna oblika bi zmedla odjemalca. Frontend (`renderCellEtaBanner`,
app.js) prikaže pasico nad radarsko karto, ko `prihaja` ni `null`.
