# MeteoHmeljar v0.1 — podatkovni model in pravila enginea

## PIVOT (28. 8. 2026) — beri to najprej

Ta dokument je bil sprva napisan za "eno gospodarstvo, znane parcele" (glej
§1.1, §7, §9 spodaj) — v0.1 je bil tako tudi zgrajen (checked-in
`data/hmeljar_parcele.yaml`, urni cron `generate_hmeljar_page.py`, statične
strani na parcelo). Izkazalo se je, da to ni bil cilj: MeteoHmeljar je
mišljen za **vse hmeljarje v dolini** — obiskovalec klikne poljubno parcelo na
karti, brez prijave, brez vnaprej znanega seznama.

To je spremenilo arhitekturo, formule (§2–§6 spodaj) pa ostajajo veljavne:

- **Ni več `data/hmeljar_parcele.yaml`, ni cron generatorja, ni statične
  strani na parcelo.** `/meteohmeljar/` je ena sama, POVSEM statična stran z
  Leaflet karto (isti vzorec/SRI kot `/meteogasilec/karta/`), ki prikaže
  hmeljiške parcele iz uradnega **MKGP GIS sloja RABA** (`RABA_ID=1160`,
  `geohub.gov.si`) za Zgornjo Savinjsko dolino, prek novega Worker proxyja
  `/hmeljar-raba` (geohub ne pošilja CORS glave — isto načelo kot
  `/varpolje-current`).
- **Ves engine (§2–§6) zdaj teče CLIENT-SIDE**, v `meteohmeljar/hmeljar.js`
  (ročno pisana datoteka, ni generirana — isto vlogo ima `gasilec.js` za
  MeteoGasilca). `tools/hmeljar_model.py` ostaja kot referenčna
  implementacija/specifikacija formul (berljiva, testabilna), ne teče več v
  produkciji — ni več generatorja, ki bi ga klical za znano parcelo, ker
  parcela ni znana vnaprej.
- **Posledica za WaterBalance**: brez cron teka na kliknjeno točko ni
  vztrajnega dnevnika, zato `cumulativeDeficit` v JS različici ni več pravi
  tekoč seštevek (glej §4) — namesto tega se izračuna iz enega daljšega
  Open-Meteo okna (60 pretečenih dni, resetira se ob dnevu z ≥15mm dežja
  znotraj tega okna). Dovolj natančno za večino primerov, manj natančno v
  suši, daljši od 60 dni brez resetnega dežja.
- **Posledica za PeronosporaRisk/PepelovkaRisk**: dnevni trend (»22→38→67→81«)
  in "preskok" v Decision Engineu (§6) v v0.1-karta izvedbi **ne delujeta** —
  potrebovala bi včerajšnjo vrednost, ki je brez strežniškega stanja nima kje
  čakati. Decision Engine v v0.1-karta prikazuje samo nevarnost/škropilno
  okno/vodni primanjkljaj (postavki 1, 2, 4 iz §6 — brez postavke 3).
- RABA sloj je **evidenca rabe tal, ne lastništva** — pove mejo/tip rabe, ne
  pove, čigava je parcela. To ostaja jasno izpisano na strani.

Ostanek dokumenta (§1–§9) je izvirna specifikacija — beri jo kot **formule in
razloge zanje** (še vedno točne), ne kot dejansko datotečno postavitev (§1.1,
§7 sta zastarela glede YAML/cron dela).

---

Status (izvirno besedilo, glej PIVOT zgoraj za trenutno stanje): specifikacija
za implementacijo. Piše se za eno gospodarstvo (Filip, znane parcele), brez
baze/prijave — checked-in config po vzorcu `species_rules.yaml` /
`HYDRANT_OVERRIDES`. Nov razdelek v `weather-station`, tehnično po vzorcu
`/meteogasilec/` (samostojne strani, lasten `worker.js` proxy kjer je treba,
cron generator).

Relacija do `/agrometeo/`: ta stran ostane (dolinski povzetek za splošno kmetijstvo:
hmelj, koruza, krompir, pšenica, trava). MeteoHmeljar je **ločen generator**
(`tools/hmeljar_model.py`, `tools/generate_hmeljar_page.py`) — parcelno natančen,
samo hmelj, z decision enginom. Formule se ne uvažajo med njima (isto načelo kot
FWI kopije v `app.js`/`gasilec_model.py`/`gasilec.js`); kjer sta formuli namerno
enaki (npr. ETo), naj to piše kot komentar, ne kot `import`.

---

## 1. Podatkovni model

### 1.1 Parcela — `data/hmeljar_parcele.yaml`

```yaml
parcele:
  - id: parcela-3
    naziv: "Spodnja Savinjska – Parcela 3"
    lat: 46.XXXX
    lon: 14.XXXX
    povrsina_ha: 4.8
    sorta: "Aurora"
    namakanje: kapljicno   # kapljicno | razprsevanje | brez
    aktivna: true
    operation_profile: hmelj_standard   # ključ v operation_profiles spodaj, override po parceli je opcijski
  - id: parcela-7
    ...

operation_profiles:
  hmelj_standard:
    wind_optimal_kmh: 2
    wind_max_kmh: 8
    gust_max_kmh: 15
    temperature_min_c: 8
    temperature_max_c: 25
    temperature_shoulder_low_c: 12   # znotraj [shoulder_low, shoulder_high] = 100 %
    temperature_shoulder_high_c: 22
    rainfree_hours_required: 4
    rh_wet_leaf_pct: 95              # nad tem = trdi izpad (rosa/mokro listje)
    rh_taper_start_pct: 70           # nad tem se komponenta začne nižati
    wet_leaf_allowed: false
```

`tip tal`, `senzor vlage tal`, `zadnje škropljenje`, `zgodovina posegov` **niso** v
v0.1 (uporabnikov seznam "kasneje") — polj sploh ni v shemi, ne prazna polja, da
shema ne laže o tem, kaj engine dejansko uporablja.

`fenološka faza` **ni ročno polje** — izpelje se iz GDD₁₀ (glej §1.2), ista tabela
kot `HOP_STAGES` v `generate_agrometeo_page.py`, a lastna kopija (drug generator).
Razlog, da ni ročni vnos: fenologija mora slediti dejanski akumulaciji temperatur
na lokaciji parcele, ne spominu uporabnika, in mora biti na voljo brez interakcije
(cron generator, brez UI).

### 1.2 Izpeljano stanje parcele (računa se vsak tek)

```
gdd10          — vsota efektivnih temperatur, baza 10 °C, od 1. jan., ista formula kot agrometeo
fenoloska_faza — iz gdd10 prek lokalne kopije HOP_STAGES
```

### 1.3 Vremenski vhod — vir podatkov

**Namerna odločitev:** trailing/opazovalni del (PeronosporaRisk, WaterBalance
zgodovina) se **ne** jemlje iz `history.json` (postaja IREICA1), ampak iz
Open-Meteo urnega arhiva **za točne koordinate parcele**. Razlog: parcele so na
različnih razdaljah od postaje, in mešanje "postaja za eno parcelo, Open-Meteo za
drugo" bi dalo neprimerljive rezultate med parcelami. `history.json` ostaja
rezerviran za MTR/`tocnost-napovedi` cevovod (glej CLAUDE.md — "IREICA1 ostaja
edina referenca" velja za to učno/verifikacijsko os, ne za splošno ponovno rabo).

Za vsako parcelo, vsak tek:

| Klic | Polja | Uporaba |
|---|---|---|
| Open-Meteo `forecast` (hourly, 7 dni) | temperature_2m, relative_humidity_2m, dew_point_2m, precipitation, precipitation_probability, wind_speed_10m, wind_gusts_10m, is_day, cape | SprayScore, PeronosporaRisk (forward), StormRisk |
| Open-Meteo `forecast` (daily, 7 dni) | et0_fao_evapotranspiration, precipitation_sum | WaterBalance |
| Open-Meteo `archive`/pretekli hourly (zadnjih 24 h) | isto kot zgoraj | PeronosporaRisk (trailing) |
| Worker `/arso-warning` (obstoječ endpoint, glej `/nevihte/` WX-ARSO) | aktivna opozorila po območju | StormRisk floor |

Ob nedosegljivem viru: **obdrži zadnji zapis, konča z 0** — isto načelo kot
`inject_forecast.py`/`fetch_hydrants.py`. Brez markerjev/vhoda javi napako, konča
z 1.

---

## 2. SprayScore (0–100, po uri, 7 dni naprej)

### 2.1 Trdi izpadi (hard gates) — če karkoli od tega velja, `SprayScore = 0`

1. `wind_speed_10m > wind_max_kmh`
2. `wind_gusts_10m > gust_max_kmh`
3. `precipitation > 0.1 mm` **ali** `precipitation_probability > 50 %` (ta ura)
4. `temperature < temperature_min_c` **ali** `> temperature_max_c`
5. `wet_leaf_allowed == false` **in** `relative_humidity >= rh_wet_leaf_pct`

Vse meje pridejo iz `operation_profile` parcele — **nič od tega ni trdo
kodirano** v engineu, kot je bilo dogovorjeno.

### 2.2 Mehke komponente (0–100 vsaka), samo če je uro prestala vse trde izpade

```
WindComponent(wind):
    100                                                    če wind <= wind_optimal
    100 * (wind_max - wind) / (wind_max - wind_optimal)    če wind_optimal < wind <= wind_max

TempComponent(t):
    100                                                              če shoulder_low <= t <= shoulder_high
    100 * (t - temperature_min) / (shoulder_low - temperature_min)   če temperature_min <= t < shoulder_low
    100 * (temperature_max - t) / (temperature_max - shoulder_high)  če shoulder_high < t <= temperature_max

RHComponent(rh):
    100                                                          če rh <= rh_taper_start_pct
    100 * (rh_wet_leaf_pct - rh) / (rh_wet_leaf_pct - rh_taper_start_pct)   sicer

RainfreeComponent(hours_to_next_rain):
    # hours_to_next_rain = koliko ur od TE ure naprej do prve ure z
    # precipitation_probability > precip_prob_taper_pct (privzeto 40 %)
    0                                                                        če < rainfree_hours_required
    100 * min(1, (hours_to_next_rain - rainfree_hours_required)
                 / (0.5 * rainfree_hours_required))                          sicer, strop 100
```

`SprayScore = min(WindComponent, TempComponent, RHComponent, RainfreeComponent)`
— **min, ne povprečje**: en sam slab dejavnik (npr. veter) mora pokvariti okno,
ne se razredčiti med štirimi. To ustreza mentalnemu modelu iz maketa zaslona
(vsak dejavnik svoj 🟢/🟡/🔴).

### 2.3 Iskanje oken — barvna vrstica + "najboljše okno"

Vsaka ura dobi nivo: 🟢 `score >= 70`, 🟡 `40 <= score < 70`, 🔴 `score < 40`.
Vrstica na zaslonu je zaporedje teh nivojev po urah (točno maketa iz prošnje —
`05:30 ━━ 🟢 ━━ 10:30 ━━ 🟡 ━━ 13:00 ━━ 🔴 ━━`). Segmentacija je **strogo
zaporedna** (brez premoščanja vrzeli) — to je namerno, ker maketa sama kaže trdo
mejo ("Po 13:00: 🔴 neprimerno"), ne zamegljeno prehodno cono.

"Najboljše okno" = najdaljši 🟢-zaporedni niz v naslednjih 24 h; pri enaki dolžini
zmaga zgodnejši (jutranji veter je praviloma šibkejši, temperatura nižja —
agronomsko boljše). Poroča se `start–end` in razlog zapiranja (katera komponenta
je na robni uri padla pod 70 — "veter se okrepi" / "možne padavine" / …).

---

## 3. PeronosporaRisk (0–100)

Sledi APS modelu (24–48 h infekcijska okna, RH>80 %, omočenost, nočna
temperatura) — pragi spodaj so **prvi približek iz literature, ne validiran na
slovenskih podatkih**. Isto opozorilo kot uporabnikovo lastno za Pepelovko: pred
"napoved tveganja bolezni" mora iti skozi validacijo na dejanskih pojavih na
parceli/IHPS. V0.1 je zato "meteorološka ugodnost", ne diagnoza.

### 3.1 Trailing (zadnjih 24 h, opazovano)

```
ur_rh80          = št. ur v zadnjih 24h z relative_humidity >= 80 %
wet_hours        = ure kjer (relative_humidity >= 90 %) ALI (precipitation > 0)
wet_degree_hours = vsota temperature_2m čez wet_hours, štetih samo če je
                    10 °C <= temperature_2m <= 25 °C v tisti uri (infekcijsko
                    kompetenten razpon)
night_avg_temp   = povprečje temperature_2m čez ure z is_day == 0

RH80Score        = min(100, ur_rh80 / 16 * 100)
WetScore         = min(100, wet_degree_hours / 150 * 100)   # KALIBRACIJA — placeholder
NightTempScore   = 100                                       če 12 <= night_avg_temp <= 20
                    linearno pada na 0 pri <=5 ali >=27       sicer

Trailing = 0.4*RH80Score + 0.4*WetScore + 0.2*NightTempScore
```

### 3.2 Forward (naslednjih 24–48 h, napoved)

Ista formula kot §3.1, na napovednih urnih poljih namesto opazovanih.

```
PeronosporaRisk = round(0.6 * Trailing + 0.4 * Forward)
```

Trailing tehta več, ker je izmerjen (gotov), forward je smerni (za trend puščico).

Nivoji: `<30` Nizko, `30–60` Zmerno, `>=60` Visoko — ista poimenovanja kot obstoječi
`risk_label()` v agrometeu (konsistenca po strani), a lastna implementacija.

**Trend** (`22 → 38 → 67 → 81` iz makete) potrebuje dnevni dnevnik: vsak tek ob
istem času (npr. 06:00) doda današnji `PeronosporaRisk` v
`data/meteohmeljar/<parcela-id>-log.json`, obreže na zadnjih 14 vnosov — isti
vzorec kot `.story_state.json`. "Preskok" (nizko→visoko) v Decision Engineu
(§6) primerja zadnja dva vnosa.

**PepelovkaRisk** ni podrobno specificiran tu (v tvojem seznamu je zunaj štirih,
ki si jih naštel) — dobi isti skelet (trailing+forward, 0–100, log), le pragi po
Oregon modelu (6+ zaporednih ur 16–27 °C dviguje, >28 °C ali dovolj padavin
niža). Enak status: heuristika do validacije.

---

## 4. WaterBalance

**Core (v0.1) — samo meteorološka bilanca, brez tal/Kc**, kot si zahteval.

```
dnevna_bilanca(dan) = precipitation_sum(dan) - et0_fao_evapotranspiration(dan)

balance_7d      = vsota dnevna_bilanca za zadnjih 7 dni (vključno danes)
balance_3d_fwd  = vsota dnevna_bilanca (napoved) za naslednje 3 dni

cumulative_deficit:
    cd[danes] = min(0, cd[včeraj] + dnevna_bilanca(danes))
    # RESET: če je today_rain >= 15 mm (en dogodek, aproksimacija napolnitve
    # talnega profila), cd[danes] = 0 ne glede na formulo zgoraj
```

`cumulative_deficit` ne sme iti pozitivno (presežek vode se v tleh ne "banči" v
neskončnost) — zato `min(0, ...)`, resetira pa ga samo pravi dogodek dežja, ne
sam predznak dnevne bilance.

**Trend** (🟢 izboljšuje se / primerja se s `balance_7d` izpred 3 dni iz istega
log-a kot §3.2; `|Δ| < 3 mm` = stabilno, sicer smer delte).

**Kje se v0.1 ustavi**: `ETc = ETo × Kc` in vlaga tal so v specifikaciji izven
obsega, a kljukica za v0.2 je že v podatkovnem modelu — `Kc` po fenološki fazi
lahko visi na isti `fenoloska_faza` (§1.2), ki je izpeljana in ne ročna, torej se
ob prehodu na Kc ne spreminja podatkovni model, samo doda nova tabela
`HOP_KC_BY_STAGE` v `hmeljar_model.py`.

---

## 5. StormRisk

Filozofija je namerna kopija `storm_threat_score()` (`generate_nevihte_page.py`)
— **ne uvožena** (drug generator, isto pravilo kot FWI), a prilagojena parceli:
6–12 h naprej, ne nacionalna mreža.

```
GustRisk:    0 pri gust < 40 km/h, linearno do 100 pri gust >= 90 km/h
             (trelis/konstrukcija — 90 km/h je PRVI PRIBLIŽEK, ne agro-inženirsko
             validirano; potrebna lokalna kalibracija)
PrecipRisk:  0 pri intenziteta < 2 mm/h, linearno do 100 pri >= 20 mm/h
ThunderRisk: če je na voljo CAPE: 0 pri cape<500, linearno do 100 pri cape>=2500
             sicer (fallback brez CAPE): 100 če (precipitation_probability > 60 %
             IN precipitation napovedan > 5 mm), sicer 0  — heuristika, jasno
             označena v UI kot posredna ocena

StormRisk = max(GustRisk, PrecipRisk, ThunderRisk)

# Uradno opozorilo ARSO za območje parcele vedno POVIŠA (nikoli ne zniža):
if aktivno_opozorilo(obmocje, nivo="oranžna" ali "rdeča"):
    StormRisk = max(StormRisk, 80)
```

`time_to_event` = prva ura v naslednjih 12 h, kjer `StormRisk >= 50`, poroča se
"čez ~X min/h" + prevladujoča komponenta ("Glavno tveganje: močan veter" /
"naliv" / "nevihta"). Uradna opozorila ARSO se prikažejo **ločeno** od te ocene
(isti vzorec kot MeteoGasilec — lastna ocena vs. uradno opozorilo, nikoli
zlito v eno število).

---

## 6. Decision Engine

**Deterministično, predlogno — brez LLM klica.** Ista logika kot
`generate_forecast_test_post.py`/`invasive_watch.py` (izračunane številke v
predlogo), ne `call_claude()` — to je operativno orodje, osveženo vsako uro;
zanesljivost/latenca/strošek LLM klica tu niso sprejemljivi, poleg tega mora
biti sestavek reproducibilen in testabilen.

Prednostni vrstni red (največ 3 postavke prikazane, v tem vrstnem redu):

1. `StormRisk >= 70` v naslednjih 12h → vedno prikazano, ne glede na ostalo (varnost).
2. Dobro škropilno okno (🟢 niz >= 3h) znotraj naslednjih 24h → prikazano z uro
   zapiranja, če se okno konča zaradi poslabšanja znotraj samega niza.
3. Preskok bolezenskega nivoja od zadnjega dnevnika (§3.2) — nizko→zmerno,
   zmerno→visoko (v obe smeri, ne le navzgor).
4. `cumulative_deficit` prečka konfigurirani prag (privzeto **-30 mm**) → prikazano.

Vsaka postavka ima predlogo besedila (primer za #2+#3 skupaj, kot v maketi):

```
"Danes {čas_okna} je dobro škropilno okno. {bolezen_stavek} {padavine_stavek}"
```

kjer se `bolezen_stavek`/`padavine_stavek` sestavita samo, če sta relevantna
(prag prečkan oz. StormRisk nad opozorilnim nivojem) — prazen niz sicer, ne
placeholder besedilo.

---

## 7. Postavitev datotek

```
data/hmeljar_parcele.yaml         — parcele + operation_profiles (ročno urejano)
data/meteohmeljar/<id>-log.json   — dnevni log na parcelo (PeronosporaRisk, PepelovkaRisk,
                                     balance_7d) — piše ga generator, obreže na 14 vnosov

tools/hmeljar_model.py            — čiste funkcije: spray_score(), peronospora_risk(),
                                     water_balance(), storm_risk(), decide()
                                     (brez I/O — testabilno, po vzorcu gasilec_model.py)
tools/generate_hmeljar_page.py    — fetch (Open-Meteo + Worker /arso-warning),
                                     kliče hmeljar_model, izriše statične strani,
                                     piše log

meteohmeljar/index.html           — pregled vseh aktivnih parcel
meteohmeljar/<parcela-id>/index.html — operativni zaslon parcele (maketa iz #11)
meteohmeljar/<parcela-id>/data.json  — JSON posnetek (za bodočo klientsko rabo)

.github/workflows/hmeljar-forecast.yml — urni cron, commita samo ob spremembi
```

**Sveže podatke** (`renderFreshness` vzorec iz gasilca) prikazuj s krajšimi pragi
kot pri gasilcu (tam dnevno, tu urno): 🟢 `<2h`, 🟡 `2–4h`, 🔴 `>4h` od
`data-generated`.

Nova `/meteohmeljar/*` pot gre tudi v `CORE` (`tools/seo_audit.py`) — isto pravilo
kot za vse ostale podstrani v tem repozitoriju.

---

## 8. Izven obsega v0.1 (potrjeno zgoraj)

Priporočila konkretnih FFS/odmerkov, avtomatska diagnoza, evidenca škropljenj,
satelitski indeksi, yield prediction, IoT/senzorji, avtomatsko namakanje — vse po
tvojem seznamu. Dodatno, glede na "eno gospodarstvo" odgovor:

- **Push obvestila** (§13 tvojega predloga, "obvesti me ko...") niso v v0.1 —
  ni infrastrukture za naročnino/dostavo (edini obstoječi vzorec je e-poštni
  seznam za jutranje predloge `daily-post.yml`, ki ni splošen mehanizem
  obveščanja). Prva verzija je zaslon, ki ga pogledaš, ne push kanal.
- UI za urejanje parcel ne obstaja — nova/spremenjena parcela je ročni PR na
  `data/hmeljar_parcele.yaml`, po vzorcu `CALIBRATION`/`HYDRANT_OVERRIDES`.

## 9. Kar potrebujem od tebe, preden začnem implementirati

1. **Prave koordinate + osnovni podatki za vsaj eno parcelo** (id, lat/lon,
   površina, sorta, namakanje) za `data/hmeljar_parcele.yaml` — brez tega ni kaj
   generirati.
2. **Privzete meje v `operation_profile`** (§1.1) so moj prvi približek
   (veter 8 km/h maks., sunki 15 km/h, 8–25 °C, 4h brez dežja) — so v redu kot
   izhodišče za v0.1, dokler jih ne preveriš/popraviš iz izkušenj?

Ko sta ti dve stvari potrjeni, grem naravnost v `tools/hmeljar_model.py` +
`tools/generate_hmeljar_page.py`.
