#!/usr/bin/env python3
"""tools/test_gobe_observations.py — opažanja bralcev kot signal »vrsta je na območju že aktivna«.

Preverja gobe_model.active_species_areas() (strogost signala: najmanj 3 opažanja, 2 različna dneva,
v zadnjih 21 dneh, samo znane vrste) in eval_species(active=…): skrajšan zamik mikoriznih vrst
dvigne indeks, ko je dež padel pred 3–5 dnevi, ne vpliva na vrste, ki jim zamika ne skrajša, in brez
stikala je rezultat enak. Mrežo (Open-Meteo) ne kliče — vhod je sintetičen.
Zaženi:  python3 tools/test_gobe_observations.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gobe_model as gm  # noqa: E402

rules = gm.load_rules()
sp_by = {s["id"]: s for s in rules["species"]}
JUR = sp_by["boletus_edulis"]
TODAY = dt.date(2026, 10, 20)
fails = []


def check(name, cond):
    print(("  ✓ " if cond else "  ✗ ") + name)
    if not cond:
        fails.append(name)


def obs(vrsta, obmocje, days_ago, i=0):
    ts = dt.datetime.combine(TODAY - dt.timedelta(days=days_ago), dt.time(10, 0, i), dt.timezone.utc)
    return {"id": f"x{days_ago}{i}", "ts": ts.isoformat(), "vrsta": vrsta, "obmocje": obmocje, "kolicina": "nekaj"}


N = JUR["name_sl"]
A = "Golte"
base = [obs(N, A, 1), obs(N, A, 3), obs(N, A, 5)]
print("— active_species_areas")
check("3 opažanja na 3 dneh → aktivna", gm.active_species_areas(base, rules, TODAY) == {("boletus_edulis", A)})
check("ujemanje imena brez razlike velikosti črk", gm.active_species_areas(
    [obs(N.upper(), A, 1), obs(N.lower(), A, 2), obs(N, A, 3)], rules, TODAY) == {("boletus_edulis", A)})
check("vpisano »Jurček« (del v oklepaju) se prepozna", gm.active_species_areas(
    [obs("Jurček", A, 1), obs("jurček", A, 3), obs(" Jurček ", A, 5)], rules, TODAY) == {("boletus_edulis", A)})
check("latinsko ime se prepozna", gm.active_species_areas(
    [obs(JUR["name_lat"], A, 1), obs(JUR["name_lat"], A, 3), obs(JUR["name_lat"], A, 5)], rules, TODAY) == {("boletus_edulis", A)})
al = gm.species_aliases(rules)
check("dvoumno ime ni v preslikavi", all(sum(1 for s in rules["species"] if s.get("gets_index") and n in
    {s["name_sl"].strip().casefold(), s["name_sl"].partition("(")[0].strip().casefold(), s["name_lat"].strip().casefold()}) <= 1
    or n not in al for n in al))
check("2 opažanji → ne", gm.active_species_areas(base[:2], rules, TODAY) == set())
check("3 opažanja istega dne → ne (en vnašalec)", gm.active_species_areas(
    [obs(N, A, 2, 0), obs(N, A, 2, 1), obs(N, A, 2, 2)], rules, TODAY) == set())
check("starejše od 21 dni se ne štejejo", gm.active_species_areas(
    [obs(N, A, 1), obs(N, A, 2), obs(N, A, 30)], rules, TODAY) == set())
check("različna območja se ne seštevajo", gm.active_species_areas(
    [obs(N, A, 1), obs(N, "Menina planina", 2), obs(N, A, 3)], rules, TODAY) == set())
check("neznana vrsta se preskoči", gm.active_species_areas(
    [obs("Izmišljena goba", A, 1), obs("Izmišljena goba", A, 2), obs("Izmišljena goba", A, 3)], rules, TODAY) == set())
check("pokvarjen vnos ne podre izračuna", gm.active_species_areas(
    base + [{"vrsta": N}, {"ts": "ni datum", "vrsta": N, "obmocje": A}, None, 5], rules, TODAY) == {("boletus_edulis", A)})
check("brez opažanj (None) → prazno", gm.active_species_areas(None, rules, TODAY) == set())


def synth(rain_idx):
    n = 45
    d0 = dt.date(2026, 9, 5)
    dates = [(d0 + dt.timedelta(days=k)).isoformat() for k in range(n)]
    precip = [0.0] * n
    for k in rain_idx:
        precip[k] = 15.0
    return {"dates": dates, "precip": precip, "tmin": [6.0] * n, "soil_temp": [11.0] * n,
            "soil_moisture": [0.35] * n, "rh": [85.0] * n, "dewpoint": [9.0] * n, "tair": [11.0] * n}


print("— eval_species")
spot = {"name": A, "elev_m": 900, "terrain": "kisla"}
series = synth([30, 31, 32])      # dež 5.–7. 10.
i = 36                            # 11. 10.: 4–6 dni po dežju
day = dt.date.fromisoformat(series["dates"][i])
off = gm.eval_species(JUR, series, i, day, spot, rules)
default = gm.eval_species(JUR, series, i, day, spot, rules, active=False)
on = gm.eval_species(JUR, series, i, day, spot, rules, active=True)
check("brez stikala je rezultat enak privzetemu klicu", off == default)
check("jurček: skrajšan zamik dvigne indeks, ko je dež star 4–6 dni", on["index"] > off["index"] + 15)
check("razlaga pove, da je zamik skrajšan", "zamik skrajšan" in on["explanation"] and "zamik skrajšan" not in off["explanation"])
check("sprožilni dež v razlagi kaže skrajšano okno (3–10)", "pred 3–10 dnevi" in on["explanation"] and "pred 8–16 dnevi" in off["explanation"])

# vrsta, ki ji zamika ne skrajša (lesna 3–10 ostane enaka, razkrojevalka 2–8 se ne podaljša)
for sid in ("auricularia_auricula_judae", "macrolepiota_procera"):
    sp = sp_by[sid]
    a = gm.eval_species(sp, series, i, day, spot, rules, active=False)
    b = gm.eval_species(sp, series, i, day, spot, rules, active=True)
    check(f"{sid}: aktivnost ne spremeni indeksa (ni mikorizna)", a["index"] == b["index"])

# zamik se ne podaljša nikoli
short = dict(JUR, fruiting_lag_days={"min": 2, "max": 6})
a = gm.eval_species(short, series, i, day, spot, rules, active=False)
b = gm.eval_species(short, series, i, day, spot, rules, active=True)
check("mikorizna vrsta s še krajšim zamikom se ne podaljša", a["index"] == b["index"])

# aktivna vrsta ob suši: skrajšan zamik ne ustvari dežja iz nič
dry = synth([])
a = gm.eval_species(JUR, dry, i, day, spot, rules, active=True)
b = gm.eval_species(JUR, dry, i, day, spot, rules, active=False)
check("brez dežja aktivnost indeksa ne dvigne", a["index"] == b["index"])

print(f"\n{len(fails)} neuspelih")
sys.exit(1 if fails else 0)
