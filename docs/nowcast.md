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
