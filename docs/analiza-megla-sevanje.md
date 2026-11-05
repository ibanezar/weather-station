# Ali sevanje IREICA1 pove, kdaj se megla dvigne? (5. 11. 2026) — NEGATIVEN REZULTAT

**Sklep: ne.** Čas, ko sevanje na IREICA1 doseže določen delež sevanja jasnega neba, **ni povezan** s časom, ko se konča nasičenost zraka (rosišče), in ne loči meglenih jutr od nemeglenih. Članek o jutranji megli zato ostane pri »nasičenem zraku«; metode »dvig megle po sevanju« ne uvajamo, članka ne dopolnjujemo.

## Kaj smo preizkusili

Ideja: ko se megla dvigne, sevanje skoči; imamo 5-minutno jutranje sevanje (`data/solar-5min.csv`, od 10. 8. 2026), torej bi lahko dobili izmerjen, ne ocenjen čas dviga.
`tools/ai/eval_megla_sevanje.py`: k(t) = izmerjeno sevanje / sevanje jasnega neba (Haurwitz, položaj sonca iz `sonce_horizont`); »sevanje prebije« = prvi trenutek, ko je k ≥ prag šest zaporednih točk (30 min), samo pri višini sonca ≥ 5° in na jutrih, ko k kadar koli doseže ≥ 0,6. Primerjava z urnim koncem nasičenosti (temperatura − rosišče ≤ 0,5 °C, kot v članku) na jutrih z meglo ob 7. uri (nasičeno in veter < 3 km/h).

## Rezultat (84 dni z obema zapisoma, 67 jutr z meglo ob 7. uri)

| razlika | prag k | meglena jutra z obema časoma | sevanje prebije | konec nasičenosti | razlika (min) | MAD | Spearman |
|---|---|---|---|---|---|---|---|
| vse, od 10. 8. | 0,3 | 47 | 9.05 | 9.00 | +25 | 55 | −0,12 |
| vse, od 10. 8. | 0,5 | 31 | 9.50 | 9.00 | +45 | 50 | 0,25 |
| vse, od 10. 8. | 0,7 | 17 | 10.25 | 9.00 | +75 | 40 | 0,08 |
| od 15. 9. | 0,5 | 20 | 10.05 | 10.00 | +37,5 | 52,5 | 0,01 |
| od 1. 10. | 0,5 | 17 | 10.05 | 10.00 | +35 | 55 | −0,01 |

Zakaj je to negativno:
1. **Povezave ni**: Spearman med časom konca nasičenosti in časom preboja sevanja je med −0,12 in 0,25 (pri n = 17–47; za značilnost bi pri n = 31 potrebovali ≥ 0,35).
2. **Čas preboja je odvisen od praga, ne od megle**: pri pragu 0,3 → 0,7 se pomakne za 1 h 20 min (9.05 → 10.25). Dvig megle bi bil oster skok, ne počasno naraščanje.
3. **Referenca brez megle prebije ob istem času ali pozneje**: jeseni (od 15. 9.) je preboj nemeglenih jutr ob 10.30, meglenih ob 10.05. Čas določata višina sonca in senca pred senzorjem (domneva iz CLAUDE.md, »Sonce v dolini«: sonce na IREICA1 pride mediano ~2 h po izračunanem prvem žarku), ne megla.

## Omejitve (zato je rezultat »ne tukaj«, ne »nikoli«)

- Rosišče je urno (±30 min dvoumnost, kdaj se ura konča); nasičenost ≠ megla (vidljivosti nihče ne meri).
- Vzorec je poletje–jesen 2026; zime ni (sonce nizko, megla pogostejša, senca še dalj). Ponovi po zimi.
- Prag 0,5 in 30-minutno držanje sta moja izbira; rezultat se ne obrne pri 0,3 ali 0,7, torej ni stvar praga.
- Če se pokaže, da sevanje na IREICA1 ne vidi sonca zaradi sence (`data/sonce-varpolje.json`, `razsodba`), je to druga postaja za isto analizo, ne popravek te: na Varpolju bi bil preizkus smiseln, ko bo imelo sevanje 5-minutni zapis za dovolj jutr.

## Ponovitev

```bash
python3 tools/ai/eval_megla_sevanje.py --k 0.5            # vse
python3 tools/ai/eval_megla_sevanje.py --k 0.5 --from 2026-09-15 --md /tmp/megla.md
```
