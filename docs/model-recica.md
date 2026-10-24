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
- **verjetnost, da dnevna vsota doseže 1 oz. 5 mm** (`pop1`, `pop5`, 21. 10. 2026): isti vhodi in ista
  logistična regresija kot `pop`, drug cilj (`POP_THRESHOLDS` v `train_recica_mos.py`). Koeficienti se
  zapišejo samo, če je pozitivnih dni ≥ 30 in je veščina proti klimatologiji (izpuščanje celega leta)
  pozitivna; sicer polje v napovedi ostane `null` in kartica vrstice ne pokaže. Prototip na arhivu
  šestih virov (`tools/ai/eval_pop_thresholds.py --csv`, 874 dni, manj značilk): Brier D+1 0,085 (1 mm) in
  0,064 (5 mm) proti klimatologiji 0,206 / 0,137, zanesljivost dobra. **Številke s pravim `pop_vector` še
  niso izmerjene** — prvo učenje (`mos-train.yml`) jih zapiše v `skill.pop1/pop5`; preveri, preden
  jih kje navedeš.
- **grobo pričakovana količina (`mm`, 22. 10. 2026)** je povprečje petih virov (best_match + `MULTI_MODELS`),
  ne naučen popravek (`mean_precip` v `predict_recica_mos.py`; `mm_n` = število virov, pod 4 se ne objavi).
  Na 875 dneh (`tools/ai/eval_precip_amount.py`, izpuščanje leta) je boljše od surovega best_match:
  MAE D+1 1,96 proti 2,30 mm, D+2 2,26 proti 2,40, D+3 2,49 proti 2,62; RMSE 4,78 / 5,48 / 5,80 proti
  6,04 / 5,97 / 6,44. Grebenska regresija na sqrt(mm) s temi vhodi ni dala nič več od povprečja (D+1 2,10).
  Napaka na dneh ≥ 1 mm ostaja 5,5–6,9 mm, razred (<1 / 1–5 / 5–15 / >15 mm) zadene v 69–76 %,
  zato je na straneh vedno »~« in »grobo«. Zamrzne se tudi v `today`.
- **naučene količine padavin še vedno ni.** Poskus je dal ~5 % izboljšave, kar je v
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

## Poskusi, ki MTR v1 niso izboljšali (6. 10. 2026)

Vsi so walk-forward po mesecih, okno 2025-10 → 2026-10 (366 dni), primerjava z MTR v1 na istih
dneh, razlika preverjena z uparjenim blokovnim bootstrapom (`tools/ai/eval_significance.py`).
Skripte so v `tools/ai/` in niso v nobenem workflowu.

| Poskus | Rezultat |
|---|---|
| LightGBM nad dnevnim arhivom več modelov (`eval_mtr2.py`) | slabši od v1 (Tmin D+2 1,40 proti 1,27 °C) |
| LightGBM / ridge na značilkah v1 + Tmax/Tmin drugih modelov (`eval_mtr2_hourly.py`) | **Tmax D+2 −0,08 °C, D+3 −0,12 °C resnično** (CI95 brez ničle); Tmax D+1 in vsi Tmin šum |
| Predhodno učenje lokalnega odstopanja na 7 letih ERA5 (`eval_mtr2_models.py`) | brez dobitka (≤ 0,007 °C čez prejšnjo vrstico) |
| Kazalnik zaupanja iz razhajanja modelov (`eval_confidence.py`) | Spearman 0,04–0,19; pri Tmin D+1/D+3 brez učinka → ne objavljaj |
| Verjetnost padavin: LightGBM / povprečje z v1 (`eval_mtr_calibration.py`) | D+1 Brier 0,172 → 0,165; D+2, D+3 brez dobitka |

Edino ponovljivo izboljšanje je več-modelni Tmax pri D+2 in D+3 (~0,1 °C). **Vgrajeno 6. 10. 2026**
kot `--multi-tmax` v `train_recica_mos.py` (glej razdelek spodaj); za tmin ni vklopljeno.
Ko bodo na voljo urni arhivi vseh modelov in dovolj zbranih ansamblov, ponovi `eval_mtr2_models.py`
(značilke HM še niso preizkušene — urni podatki po modelih se zaradi omejitev Open-Meteo niso prenesli).

## `--multi-tmax`: Tmax drugih modelov kot značilke (6. 10. 2026)

Za model tmax se k 16 osnovnim značilkam (in cond/bias, če so vklopljeni) dodajo `MULTI_FEATURES`:
razlika Tmax modelov IFS, GFS, ICON, ARPEGE do privzetega Open-Meteo, razlika njihovega povprečja
in razpršenost vseh vhodov. Vir pri učenju je `data/forecast-archive.csv` (po vodilnem času in
datumu), pri napovedi živi klic Open-Meteo `models=<id>` za vsak model
(`predict_recica_mos.fetch_live_multi`, dnevni ekstrem iz urnih vrednosti po lokalnem času, enako kot
arhiv). Manjkajoč model je nevtralen (razlika 0); pri < 2 modelih za dan se dan preskoči, pri
nobenem dosegljivem pa se napoved ne osveži (stara ostane, kot pri pristranskosti).
Učni vzorci za tmax so omejeni na dneve z arhivom (od 2024-05-26); tmin ostaja pri
prvotnem oknu. Meritev v okviru lastnega walk-forward (`train_recica_mos.py --report`, isto
okno 2024-05-26 → 2026-10-05, `--use-bias-tmin --use-cond-tmin`):

| Tmax | brez | z `--multi-tmax` |
|---|---|---|
| D+1 | 1,11 °C | 1,04 °C |
| D+2 | 1,34 °C | 1,24 °C |
| D+3 | 1,53 °C | 1,40 °C |

`model/recica-mos.json` nosi `uses_multi_features` in `multi_models`; model, naučen brez zastavice,
deluje kot prej. Test: `tools/test_mtr_extras.py`.

## Poskusi 23. 10. 2026: značilke po režimu noči in pas negotovosti

Isti walk-forward po mesecih kot v produkciji (okno 2025-10 → 2026-10, 383 dni, produkcijske zastavice: Tmin
`--use-bias-tmin --use-cond-tmin`, Tmax `--multi-tmax`), uparjen blokovni bootstrap (7-dnevni bloki).
Skripti: `tools/ai/eval_mtr3.py` (značilke), `tools/ai/eval_mtr_sd.py` (sd).

**Značilke: nič ni resnično.** Mehka utež »jasna in mirna noč« (`regime`: utež, utež × razlika temperature
in rosišča, utež × Tmin, utež × tlak), razredna obravnava mokrih dni (`wet`: ure z dežjem, interakcija s
temperaturo), razlika temperatura − rosišče (`dp`) in kombinacija so pri vseh šestih celicah (Tmax/Tmin × D+1..D+3)
v šumu: razlike MAE od −0,023 do +0,013 °C, vsak interval zaupanja zajema 0. Tmin D+1: osnova 1,234,
`regime` 1,231, `dp` 1,234. **Ne dodajaj teh značilk**; ostanek napake ob jasnih nočeh ni linearen v teh
vhodih. Preostane urni model (potrebuje urne meritve, glej `data/hourly-observations.csv`).

**sd po režimu noči: pri Tmax pomaga, pri Tmin ne.** Ena sama sd je pri Tmax preširoka ob jasnih nočeh
(pokritost P10–P90 89–92 % namesto 80 %) in preozka ob oblačnih (74–75 %). Z ločeno sd po razredu
(`night_regime`) je 72–81 % v vseh razredih in logaritemska ocena je pri D+1/D+2/D+3 boljša
(1,739→1,735, 1,897→1,875, 2,017→1,999). Pri Tmin in `p_frost` razlike ni (Brier zmrzali 0,0632 / 0,0631),
zato ostane tam globalna sd. **Vgrajeno**: `residual_sd_by_regime()` v `train_recica_mos.py` zapiše
`residual_sd_regime.tmax` (razred z < 40 dnevi ga nima), `predict_day` ga uporabi za pas na kartici; brez njega
velja globalna sd, stari modeli delujejo nespremenjeno. Pokritost 72 % ob jasnih nočeh pri D+3 je še vedno
pod nominalnimi 80 %: razred ima le 74 dni. Ponovi, ko se nabere več.

## Poskusi 24. 10. 2026: višinski nivoji, sloji oblačnosti, sneg, mejna plast, sonce

Skripti: `tools/ai/fetch_profile_cache.py` (zajem), `tools/ai/eval_mtr4.py` (isti walk-forward po mesecih in
uparjeni blokovni bootstrap kot `eval_mtr3.py`; okno 2025-10 → 2026-10, n = 384 dni na celico).

**Za večino teh spremenljivk pošten arhiv ne obstaja.** Open-Meteo nima `*_previous_dayN` za višinske nivoje
(T925/T850; HTTP 400) ter za oblačnost po slojih, višino snega, vlago tal in mejno plast (same vrednosti `null`,
preverjeno na `historical-forecast-api` in `previous-runs-api`). Dobiti jih je mogoče samo kot zlepljeno serijo
najsvežejšega teka, ki je blizu analize. Zato je eval nad njimi **zgornja meja in ne napoved**. Edino
`sunshine_duration` ima pravi `previous_dayN`.

| kandidat | rezultat |
|---|---|
| `sun` (sončni čas, **prava napoved**) | šum pri vseh šestih celicah (Tmin D+1 celo −0,004, CI [−0,009; −0,000]). **Mrtvo.** |
| `blh` (mejna plast) | šum / Tmin D+2 −0,004. **Mrtvo, tudi kot zgornja meja.** |
| `snow` (višina snega + vlaga tal) | šum povsod; v vzorcu je samo **20 dni s snegom > 1 cm** od 779, torej **ni preizkušljivo**, ne ovrženo. |
| `prof`, `cloud3`, `stab` | dobitek, ki narašča z vodilnim časom (Tmax `prof` 0,03 → 0,17 → 0,30 °C) — podpis uhajanja. |

**Kontrola uhajanja (`ctrl`).** Namesto profila model dobi zlepljeni Tmax/Tmin istega dne iz iste serije
(čisti »nowcast«, brez kakršne koli informacije o profilu). Pri Tmax `ctrl` premaga `prof` v vseh treh vodilnih
časih (0,145 / 0,316 / 0,451 proti 0,030 / 0,168 / 0,301 °C): **dobitek profila pri Tmax je ves razložen z
uhajanjem, dokaza o resnični informaciji ni.** Pri Tmin je `stab` (T925 − T2m ponoči, T850 − T2m podnevi) pri
D+2/D+3 dosegel 0,157/0,166 °C proti `ctrl` 0,223/0,304 — pod stropom uhajanja, zato **ne moremo ločiti**
informacije od uhajanja (pozimi 0,23–0,29 °C, ena zima). To je edini kandidat s fizikalnim razlogom (inverzija).

**Kaj to pomeni.** Brez arhiva napovedi se vprašanje »ali stabilnost iz višinskih nivojev izboljša Tmin« ne da
odločiti. Pošten odgovor zahteva, da od zdaj sproti beležimo prave napovedi izpred 1–3 dni (T925/T850, sloji
oblačnosti, sneg) in ponovimo eval po zimi (ni narejeno; prva prava zima s tem arhivom je 2026/27).
**Ne dodajaj teh značilk v produkcijski model, dokler niso izmerjene na pravih napovedih.**

**Beleženje pravih napovedi teče od 24. 10. 2026** (`tools/log_profile_forecasts.py`, korak v
`test-napovedi-daily.yml`, `continue-on-error`): za D+1..D+3 zapiše dnevne stolpce (`inv_n`, `lapse_d`, `t850_d`,
`w925_n`, sloji oblačnosti, `snow_max`, `soil_mean`, `blh_max`) v `data/profile-forward-log.csv`. Agregacija je ena
funkcija, `daily_columns()`; `eval_mtr4.py` jo uvaža (`groups_from_columns()` preslika stolpce v skupine kandidatov),
tako da učenje in napoved nikoli ne dobita različnih vhodov (preverjeno: izhod za vseh 881 dni enak staremu).
Test: `tools/test_profile_log.py` (v `parity.yml`). Izdaja je ob uri teka workflowa (GitHubov cron zamuja ure), zato je
lahko naslednji tek modela že vključen — razlika do arhiva `previous_dayN`, ki jo je treba imeti v mislih.
**Še ni narejeno:** eval, ki bere ta dnevnik (potrebuje meritve IREICA1 za iste dneve, `build_samples`); smiselno ga je
napisati po zimi 2026/27, ko bo vsaj ~120 zimskih dni. Do takrat ne objavljaj nobene številke o koristi profila.

## Dnevnik živih osvežitev (24. 10. 2026)

Model je naučen na jutranjem zajemu D+1; kartice pa od 23. 10. berejo živo osvežitev (4 termini na dan), katere točnosti
nismo merili. `predict_recica_mos.py --live` zato vsako osvežitev doda v `data/mtr-live-log.csv` (na semafor ne gre, ta
še naprej meri zamrznjeno jutranjo napoved). `tools/ai/eval_live_refresh.py` združi dnevnik z meritvijo in zamrznjeno
napovedjo iz `forecast_verification.json` ter za vsak razred `hours_before` izpiše MAE in uparjeno razliko z blokovnim
bootstrapom. **Rezultata še ni**: potrebuje vsaj 20 razrešenih dni na razred (~3 tedne). Pozor na razred »že teče«:
osvežitev ob 22:40 UTC je že po lokalni polnoči in vključuje del dneva, zato ni poštena primerjava z jutranjo.
