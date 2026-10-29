# Pristranskost postaje ali modelov? (IREICA1, D+1)

## 1. Modeli proti postaji, D+1, vsi razrešeni dnevi

| Model | n | Tmax pristranskost | Tmax MAE | Tmin pristranskost | Mesecev s Tmax < 0 |
|---|---|---|---|---|---|
| best_match | 882 | -0.84 | 1.37 | +0.93 | 29 od 30 |
| icon_seamless | 882 | -0.84 | 1.37 | +0.89 | 29 od 30 |
| ecmwf_ifs025 | 882 | -1.86 | 2.20 | +1.32 | 30 od 30 |
| gfs_seamless | 882 | -1.33 | 1.95 | +2.59 | 29 od 30 |
| meteofrance_arpege_europe | 882 | -1.14 | 1.90 | +3.14 | 26 od 30 |

best_match, **zimski meseci** (dec–feb, nizko sonce): Tmax pristranskost -1.01 °C, Tmin +0.49 °C (n = 180).

## 2. IREICA1 proti sosednji postaji Varpolje (IREICA7), čez dan

Opoldne (11–15 h): povprečna razlika IREICA1 − Varpolje **+0.27 °C** (n = 59, en zapis na dan, od 2026-08-30 do 2026-10-29).

## 3. ARSO: odmik ali šum?

Dnevi, ko imata ARSO in Open-Meteo napoved: 84.

| | pristranskost | MAE | MAE po odštetem odmiku |
|---|---|---|---|
| ARSO − meritev, Tmax | -4.43 | 4.45 | 1.61 |
| Open-Meteo − meritev, Tmax | -1.23 | 1.64 | 1.28 |
| ARSO − Open-Meteo, Tmax | -3.20 | 3.29 | 1.24 |
| ARSO − meritev, Tmin | +1.62 | 2.49 | 2.15 |
| Open-Meteo − meritev, Tmin | +1.40 | 1.49 | 1.03 |

jasni dnevi (razpon ≥ 12 °C), n = 65: ARSO − meritev Tmax -4.88 °C, Open-Meteo − meritev -1.50 °C.

oblačni dnevi (razpon < 8 °C), n = 9: ARSO − meritev Tmax -3.06 °C, Open-Meteo − meritev -0.29 °C.

## Sklep (29. 10. 2026)

- **Senzor ni topel.** Proti sosednji postaji v istem dnu doline je IREICA1 opoldne le +0,3 °C toplejša (59 dni). Pristranskost Tmax je negativna
  v 29 od 30 mesecev in tudi pozimi (−1,0 °C pri best_match, nizko sonce), kar sevalnega pregrevanja senzorja ne razloži.
- **Modeli podcenjujejo dnevni razpon doline**: Tmax pod, Tmin nad meritvijo pri vseh petih modelih in v vseh mesecih. To je znak mreže, ki ne vidi
  dna doline in nočne inverzije, in je razlog, da MTR (popravek na tej postaji) pri jasnih dneh tako izrazito pomaga.
- **ARSO ima predvsem odmik**: pri Tmax −4,4 °C, a ko ga odštejemo, je napaka ±1,6 °C (Open-Meteo ±1,3). Odmik proti Open-Meteo je ~−3,2 °C vse tri
  mesece in večji ob jasnih dneh (−4,9) kot ob oblačnih (−3,1). Pri Tmin je ARSO šumnejši (±2,2 proti ±1,0).
- **Nerešeno:** zakaj je ARSO 3,2 °C pod Open-Meteo. Kandidata: (a) `txsyn` ni pravi dnevni maksimum (sinoptični termini), (b) napoved je za Ljubno ob
  Savinji (~9 km navzgor), ne za Rečico. Ločiti ju je mogoče samo z branjem ARSO API-ja (`vreme.arso.gov.si/api/1.0/location/`), ki iz oblačnih IP-jev
  ni dosegljiv: primerjaj `txsyn` z največjo vrednostjo `t` v 3-urnih terminih istega dne in z napovedjo za drug kraj (Celje).
- **Omejitve:** Varpolje je en zapis na dan opoldne in samo dva meseca; obe postaji sta v istem dnu doline, zato ne ločita od »dolina je topla proti mreži«.
