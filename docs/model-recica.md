# MTR — lastni napovedni model za Rečico (MOS)

**MTR (Meteorec)** je ime tega modela: napoved za dno doline, izračunana iz
Open-Meteo in **popravka, naučenega na meritvah te postaje**. Zato "MOS"
(Model Output Statistics) in ne "svoj model vremena": sinoptiko — kje je
fronta, kakšna zračna masa priteka — prispeva Open-Meteo, MTR popravi tisto,
česar globalna mreža za to lego ne zna.

Prikazana različica (»MTR v1« ipd.) je izpeljana iz `model_version` v
`model/recica-mos.json` — glavna števika pred piko. Nikjer je ne zapisujemo
trdo, da se sama dvigne, ko se model kdaj znova nauči pod novo verzijo.

```
historical-forecast-api (*_previous_day1..3) ─┐
history.json (meritve postaje)               ─┴─▶ train_recica_mos.py
                                                        │  mesečno
                                                        ▼
                                              model/recica-mos.json
                                                        │
api.open-meteo.com (živa napoved) ─────────────────────┤ dnevno
                                                        ▼
                                              predict_recica_mos.py
                                                        │
                            ┌───────────────────────────┼──────────────────┐
                            ▼                           ▼                  ▼
                   napoved-modela.json        verify_forecasts.py     kartica
                                              (/tocnost-napovedi/)    (app.js)
```

## Zakaj sploh deluje

Postaja stoji na dnu ozke doline na 360 m. Open-Meteo za to točko računa na
mreži, ki doline ne razreši, in razlika ni naključna:

| razmere | postaja proti modelu |
|---|---|
| dnevni maksimum, vse leto | **+0,82 °C** |
| nočni minimum, vse leto | **−0,94 °C** |
| nočni minimum ob jasni in mirni noči (n = 192) | **−1,55 °C** |

Ponoči se na dnu doline nabere hladen zrak; ob jasnem nebu in brez vetra ga nič
ne premeša, zato je odstopanje takrat največje. To je ponovljiv vzorec, ki ga je
mogoče izračunati iz značilk, ki jih Open-Meteo napove — oblačnosti in vetra
ponoči. Prav to počne značilka `coldpool`.

## Vhod

**Učenje:** `historical-forecast-api.open-meteo.com`, spremenljivke
`*_previous_dayN` — napoved, kakršna je resnično bila N dni prej. To je edini
pošten vir. ERA5 arhiv (`archive-api`) bi modelu povedal, kakšno je vreme *bilo*,
in bi veščino močno precenil: naučili bi se popravljati analizo, uporabljali pa
napoved. Te spremenljivke segajo do **~2024-01**, ne dlje — od tod velikost učne
množice.

**Oznake:** `history.json`, samo dnevi s `src` `station` ali `wu`. Dnevi `era5`
so modelska ocena in bi model učili njegovega lastnega vhoda.

**Napoved:** `api.open-meteo.com/v1/forecast`, iste urne spremenljivke.

Značilke gradi **ena sama funkcija** — `daily_features()` v
`train_recica_mos.py`, ki jo napovedovalnik uvozi. Dva prepisa bi se prej ali
slej razšla in model bi tiho dobival druge vhode, kot jih pozna.

## Model

- **temperatura** — grebenska regresija (λ = 2) za `tmax` in `tmin`, posebej za
  vsak vodilni čas D+1..D+3. 16 značilk: napovedani Tmax/Tmin, oblačnost, veter,
  vlaga, tlak, obsevanje in padavine (vsaka tudi nočno povprečje, kjer je
  smiselno), letni hod prek `sin`/`cos` dneva v letu, člen hladne kotanje ter
  dve sezonski interakciji.
- **padavine** — logistična regresija za verjetnost mokrega dne (≥ 0,2 mm).
- **količine padavin ne napovedujemo.** Poskus je dal ~5 % izboljšave, kar je v
  okviru šuma; količina, ki jo objavimo, je surova vrednost Open-Meteo in je
  tako tudi označena.
- **persistence (včerajšnja meritev) ni v modelu.** Preizkušena je bila in ni
  prispevala nič (1,10 proti 1,11 °C). Model je brez nje preprostejši in ni
  odvisen od tega, ali je arhiv postaje že osvežen.
- **ECMWF AIFS kot drugi vhod je preizkušen in za zdaj izklopljen** — glej
  spodnji razdelek.

Vse je čisti Python iz standardne knjižnice: pri 16 značilkah in ~900 vzorcih se
normalne enačbe rešijo z Gauss-Jordanovo eliminacijo v milisekundah, logistična
regresija pa po Newtonu (IRLS), kjer je vsak korak ena utežena grebenska
regresija. Nobeno drugo orodje v tem repozitoriju nima numpy in ga tudi to ne
potrebuje.

## Kaj kaže preverjanje

Veščina se meri z **izpuščanjem celega leta**: model se nauči na vseh letih razen
enem in oceni na izpuščenem. Naključna delitev bi tu lagala — vreme je iz dneva v
dan močno odvisno, zato bi imel testni dan skoraj vedno svojega soseda v učni
množici.

Trenutne številke so v `model/recica-mos.json` pod `leads.<N>.skill`; izpiše jih
tudi `python3 tools/train_recica_mos.py --report`. Ob uvedbi (učna množica
2024-01 → 2026-08, ~920 dni):

| | Open-Meteo | MTR | izboljšanje |
|---|---|---|---|
| Tmax D+1 | 1,38 °C | 1,10 °C | 20 % |
| Tmin D+1 | 1,58 °C | 1,24 °C | 21 % |
| Tmax D+2 | 1,68 °C | 1,26 °C | 25 % |
| Tmin D+2 | 2,47 °C | 1,33 °C | 46 % |
| Tmax D+3 | 1,84 °C | 1,45 °C | 21 % |
| Tmin D+3 | 2,47 °C | 1,44 °C | 42 % |

Verjetnost padavin, Brierjeva ocena (manjše je bolje, klimatologija 0,254):
0,159 pri D+1, 0,172 pri D+2, 0,179 pri D+3.

Popravki, ki jih model dela, so omejeni in ne bežijo: Tmax od −1,7 do +2,3 °C
(povprečno +0,82), Tmin od −4,4 do +1,5 °C (povprečno −0,93). To je približno
tisto, kar pove tabela pristranskosti zgoraj — model ni iznašel ničesar novega,
le sistematično uporabi znano razliko.

Pomembna opozorila k tem številkam:

- To je **hindcast**, ne obljuba. Živo oceno daje `/tocnost-napovedi/`, kjer se
  model meri po istem pravilu kot ARSO in Open-Meteo in kjer lahko tudi izgubi.
  Šele ~30 razrešenih dni pove, ali se hindcast potrjuje.
- **Skok napake Open-Meteo pri Tmin z D+1 na D+2 (1,58 → 2,47 °C) je bil
  preverjen** — na videz je prevelik za en dan razlike. Dve razlagi sta bili
  izključeni: (1) zamik serije `previous_day2` za dan — navzkrižna korelacija z
  analizo ima vrh pri zamiku 0 (0,965), sosednja vrhova sta pri ±24 h bistveno
  nižja (0,83); (2) manjkajoče jutranje ure, ki bi minimum pobrale iz toplejšega
  dela dneva — pokritost je enaka, 365/365 dni s polnimi 24 urami in polnimi
  urami 00–05. Skok je torej resničen: nočni minimum v dolini je odvisen od
  tega, ali bo sevalna noč, in ta pogoj model na dva dni ujame slabše.
  Če se `previous_dayN` kdaj obnaša drugače, ponovi ta dva testa.
- Model je **poskusen** in tako tudi označen povsod, kjer se prikaže.

## Poskus: ECMWF AIFS kot drugi vhod (`--aifs`)

AIFS je AI model ECMWF, ki ga Windy prikazuje kot 15-dnevni podaljšek modela
ECMWF; prek Open-Meteo je dosegljiv kot `models=ecmwf_aifs025_single`. Na
`/tocnost-napovedi/` teče kot samostojen tekmovalec in tam **izgublja** — pri
maksimalni temperaturi se moti za ±3,0 °C proti ±1,4 °C pri Open-Meteo.

Zanimivo je, **zakaj** izgublja. Napaka je skoraj čista pristranskost, ne
razpršenost (26 dni, julij–avgust 2026):

| | povprečni odklon | razpršenost |
|---|---|---|
| Open-Meteo, Tmax | −1,05 °C | 1,33 °C |
| AIFS, Tmax | −3,02 °C | **1,11 °C** |
| Open-Meteo, Tmin | +1,14 °C | 1,50 °C |
| AIFS, Tmin | +3,20 °C | 1,82 °C |

Mreža 0,25° dnevni razpon stisne za dobrih 6 °C — natanko tista vrsta
sistematičnega premika, ki jo MOS odstrani. Pri Tmax je AIFS iz dneva v dan celo
**bolj dosleden** od Open-Meteo. Zato poskus: AIFS ne kot zamenjava vhoda, ampak
kot dodatne značilke (`AIFS_TEMP_FEATURES`, `AIFS_POP_FEATURES`) — njegova
Tmax/Tmin in razlika do privzetega modela.

Izmerjeno na **istih dnevih** (2025-02-20 → 2026-08-09, presek datumov, isto
izpuščanje celega leta):

| | MTR brez AIFS | MTR z AIFS | |
|---|---|---|---|
| Tmax D+1 | 1,34 °C | 1,30 °C | −3 % |
| Tmax D+2 | 1,77 °C | 1,60 °C | −10 % |
| Tmax D+3 | 1,96 °C | 1,83 °C | −7 % |
| Tmin D+1 | 1,26 °C | 1,16 °C | −8 % |
| Tmin D+2 | 1,43 °C | 1,27 °C | −11 % |
| Tmin D+3 | 1,46 °C | 1,35 °C | −8 % |
| Brier D+1..3 | 0,158 / 0,173 / 0,175 | 0,157 / 0,169 / 0,168 | |

Izboljšanje je majhno, a **dosledno v vseh 12 celicah po letih** — ne šum. Največ
prispeva razlika med modeloma: kadar se AIFS in Open-Meteo razideta, je
negotovost večja.

**Zakaj kljub temu ni vklopljeno.** Arhiv AIFS se začne 2025-02-20, zato se učna
množica skrči z ~930 na ~530 dni. Na tako kratkem oknu se popravek za Tmax ne
posploši — brez cele jeseni in zime v učni množici je osnova na tem oknu celo
slabša od surovega Open-Meteo (−1,2 % pri D+1). Primerjava tistega, kar je
dejansko mogoče objaviti:

| D+1 | Tmax | Tmin |
|---|---|---|
| produkcija (dolgo okno, brez AIFS) | **1,10 °C** | 1,24 °C |
| kratko okno z AIFS | 1,30 °C | **1,16 °C** |

Pri Tmin bi AIFS že zdaj zmagal, pri Tmax pa izguba učnih podatkov odtehta.
Zato ostane produkcija pri MTR v1, poskus pa je ohranjen za ponovitev, ko bo
arhiv AIFS dolg ~3 leta (predvidoma pomlad 2028 za tri cele sezone; smiselno ga
je ponoviti že po naslednji zimi).

Ponovitev:

```
python3 tools/train_recica_mos.py --from 2025-02-20 --report          # osnova
python3 tools/train_recica_mos.py --from 2025-02-20 --aifs --report   # z AIFS
```

Ob vklopu se `uses_aifs` zapiše v `model/recica-mos.json` in
`predict_recica_mos.py` sam pobere še živo napoved AIFS — drugih posegov ni.

## Vzdrževanje

Kar se lahko pokvari:

- **Open-Meteo preimenuje ali umakne spremenljivko** → zajem vrne prazne serije,
  `daily_features()` vrne `None`, učenje javi premalo vzorcev. Popravek:
  uskladi `HOURLY_VARS` v `train_recica_mos.py` (napovedovalnik jih uvozi).
- **`*_previous_dayN` se preneha objavljati** → modela ni več mogoče znova
  naučiti; obstoječi koeficienti delujejo naprej, a se ne osvežujejo.
- **Postaja izpade za dlje časa** → manj učnih vzorcev, veščina pade. Pod 200
  vzorci se vodilni čas sam izpusti.
- **`model/recica-mos.json` se nikoli ne ureja ročno.** Nastane samo iz učenja.

## Zasebnost

Model se uči izključno iz `history.json` (zunanje meritve) in Open-Meteo.
Nobenih notranjih meritev. Datoteka `all_Rečiškapstaja(...).xlsx` ima stolpce
`Indoor` in se v tem cevovodu **ne uporablja**; če bi jo kdaj kdo vključil, mora
te stolpce zavreči.
