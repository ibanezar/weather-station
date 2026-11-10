#!/usr/bin/env python3
"""
tools/test_sneg_mos.py -- MTR sneg (proksi): značilke, učenje, napoved, sezona, dnevnik, preverjanje.

Brez omrežja: Open-Meteo nadomestijo lažni vnosi. Model v repozitoriju se preveri samo po obliki.
"""
import csv
import datetime as dt
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import predict_sneg_mos as ps  # noqa: E402
import train_sneg_mos as tsm   # noqa: E402
import verify_sneg as vs       # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✓ " if ok else "  ✗ ") + name)
    fails += 0 if ok else 1


# --- proksi
check("proksi: mokro in hladno = 1", tsm.is_snow_day(3.0, 0.5) == 1)
check("proksi: suho in hladno = 0", tsm.is_snow_day(0.0, -5.0) == 0)
check("proksi: mokro in toplo = 0", tsm.is_snow_day(10.0, 6.0) == 0)
check("proksi: mejni prag 0,2 mm in 1,0 °C šteje", tsm.is_snow_day(0.2, 1.0) == 1 and tsm.is_snow_day(0.1, 1.0) == 0)

# --- značilke
f = tsm.day_features({"best_match": (2.0, -2.0, 4.0), "ecmwf_ifs025": (4.0, 0.0, 2.0),
                      "gfs_seamless": (6.0, 2.0, 0.0), "icon_seamless": (0.0, -4.0, 6.0)})
check("značilke: povprečje T in padavin čez modele", abs(f["tavg"] - 1.0) < 1e-9 and abs(f["prec"] - 3.0) < 1e-9)
check("značilke: delež mokrih modelov", abs(f["wetfrac"] - 0.75) < 1e-9)
check("značilke: premalo modelov -> None", tsm.day_features({"best_match": (1.0, 0.0, 1.0)}) is None)
check("značilke: manjkajoča vrednost izloči model",
      tsm.day_features({"best_match": (1.0, 0.0, None), "ecmwf_ifs025": (1.0, 0.0, 1.0),
                        "gfs_seamless": (1.0, 0.0, 1.0)}) is None)
check("značilke: neznan model se ne šteje",
      tsm.day_features({"best_match": (1.0, 0.0, 1.0), "ecmwf_ifs025": (1.0, 0.0, 1.0),
                        "neznan": (1.0, 0.0, 1.0)}) is None)

# --- matematika
rng = np.random.default_rng(1)
X = np.column_stack([np.ones(400), rng.normal(0, 1, 400)])
y = (rng.random(400) < 1 / (1 + np.exp(-(0.5 + 2.0 * X[:, 1])))).astype(float)
w = tsm.fit_logit(X, y, ridge=0.1)
check("logit: obnovi smer in približno velikost koeficienta", 1.2 < w[1] < 3.0 and -0.3 < w[0] < 1.3)
a, b = tsm.fit_calibration(X @ w * 3.0, y)     # prevelik logit -> naklon b < 1
check("kalibracija: preveč samozavesten logit dobi b < 1", b < 0.8)
a2, b2 = tsm.fit_calibration(X @ w, y)
check("kalibracija: dober logit ostane blizu b = 1", 0.7 < b2 < 1.3)
check("AUC: popoln razvrstitev = 1", tsm.auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0)

# --- učenje na sintetičnih podatkih: več dni, mokro in hladno -> sneg
truth, by = {}, {lead: {} for lead in tsm.LEADS}
start = dt.date(2024, 10, 1)
for i in range(700):
    d = start + dt.timedelta(days=i)
    if d.month not in tsm.SEASON:
        continue
    t = 4 * np.sin((d.timetuple().tm_yday + 80) / 58.0) + rng.normal(0, 3)
    p = max(0.0, rng.normal(0.5, 3))
    iso = d.isoformat()
    truth[iso] = (p, t, tsm.is_snow_day(p, t))
    for lead in tsm.LEADS:
        by[lead][iso] = {m: (t + 3 + rng.normal(0, .5), t - 3 + rng.normal(0, .5), max(0.0, p + rng.normal(0, .3)))
                         for m in tsm.MODELS}
by = {k: v for k, v in by.items()}
model = tsm.train(truth, by, observed={})
check("učenje: naučil je vse vodilne čase", set(model["leads"]) == {"1", "2", "3", "4", "5"})
e = model["leads"]["1"]
cold_wet = tsm.day_features({m: (-1.0, -5.0, 5.0) for m in tsm.MODELS})
warm_wet = tsm.day_features({m: (12.0, 6.0, 5.0) for m in tsm.MODELS})
cold_dry = tsm.day_features({m: (-1.0, -5.0, 0.0) for m in tsm.MODELS})
pw, pwarm, pdry = tsm.predict_p(e, cold_wet), tsm.predict_p(e, warm_wet), tsm.predict_p(e, cold_dry)
check("napoved: mokro in mrzlo >> toplo in mokro", pw > 0.5 and pwarm < 0.1)
check("napoved: mrzlo a suho < mrzlo in mokro", pdry < pw)
check("opazovanja: brez obs_pp predict_obs vrne None", tsm.predict_obs(e, cold_wet) is None and tsm.predict_obs_stations(e, cold_wet) == {})
check("napoved: verjetnost je v [0, 1]", all(0.0 <= v <= 1.0 for v in (pw, pwarm, pdry)))
check("model: cilj in opozorilo o proksiju sta zapisana",
      "proksi" in model["target"]["name"] and "ne meri" in model["target"]["caveat"])

# --- preslikava meritev v sneg na postaji (sintetična postaja: sneg >= 1 cm, kadar je dan hladen in moker, v polovici primerov)
observed = {"1748": {d: (3.0 if truth[d][2] and rng.random() < 0.5 else 0.0) for d in truth}}
check("obs_x: opazovan mokri dan = vector z deležem mokrih modelov 1", tsm.obs_x(5.0, -2.0) == tsm.vector({"tavg": -2.0, "prec": 5.0, "wetfrac": 1.0})
      and tsm.obs_x(0.0, -2.0)[3] == 0.0)
pp = tsm.fit_obs_pp(observed["1748"], truth)
check("fit_obs_pp: koeficienti za vse značilke, dogodki in zime so zapisani", pp is not None and len(pp["coefficients"]) == 4 and pp["events"] >= 10 and pp["winters"])
check("fit_obs_pp: brez dogodkov None", tsm.fit_obs_pp({d: 0.0 for d in truth}, truth) is None)
rows1 = tsm.samples_for(1, truth, by)
cv = tsm.obs_pp_cv(observed["1748"], truth, rows1)
check("obs_pp_cv: zima izpuščena na napovedanih vhodih, skill in AUC sta zapisana", cv and cv["skill"] is not None and cv["auc"] > 0.7 and cv["events"] > 0)
mod_obs = tsm.train(truth, by, observed=observed)
check("train: obs_pp je zapisan po vodilnih časih z imenom postaje",
      all(v["obs_pp"]["1748"]["name"] == "Gornji Grad" for v in mod_obs["leads"].values()))
check("train: observed_target ima glavno postajo in njeno ime", mod_obs["observed_target"]["primary"] == "1748"
      and mod_obs["observed_target"]["stations"]["1748"]["name"] == "Gornji Grad")
e_obs = mod_obs["leads"]["1"]
po_wet, po_warm = tsm.predict_obs(e_obs, cold_wet), tsm.predict_obs(e_obs, warm_wet)
check("opazovanja: merljiv sneg sledi vremenu (mrzlo in mokro >> toplo in mokro)", po_wet > 0.2 and po_warm < 0.05 and po_wet > po_warm)
check("opazovanja: predict_obs_stations vrne vse naučene postaje", set(tsm.predict_obs_stations(e_obs, cold_wet)) == {"1748"})
check("train: brez opazovanj obs_pp ni", all("obs_pp" not in v for v in model["leads"].values()))
check("postaje: glavna je Gornji Grad, višini sta samo preverjeni", tsm.VALLEY_STATIONS[tsm.OBS_PRIMARY]["name"] == "Gornji Grad"
      and tsm.VALLEY_STATIONS["1748"]["alt_m"] == 428 and tsm.VALLEY_STATIONS["1747"]["alt_m"] == 794
      and tsm.VALLEY_STATIONS["1749"]["alt_m"] is None)
check("shrink_logit: shrink 1 ohrani logit, shrink 0 da klimatologijo", abs(tsm.shrink_logit(1.3, 1.0, 0.05) - 1.3) < 1e-12
      and abs(tsm.shrink_logit(1.3, 0.0, 0.05) - np.log(0.05 / 0.95)) < 1e-12)
check("shrink_logit: shrink 0,5 je med logitom in klimatologijo", np.log(0.05 / 0.95) < tsm.shrink_logit(1.3, 0.5, 0.05) < 1.3)
check("train: krčenje je naklon kalibracije osnovnega modela, omejen na (0,3 .. 1)",
      all(0.3 <= v["obs_pp"]["1748"]["shrink"] <= 1.0 for v in mod_obs["leads"].values()))
a_fit, b_fit = tsm.fit_obs_calibration(np.array([0.0] * 100), np.array([1.0] * 5 + [0.0] * 95))
check("legacy: fit_obs_calibration (eval_snowfall) deluje še naprej", abs(a_fit - np.log(0.05 / 0.95)) < 1e-3 and b_fit == 1.0)

# --- model v repozitoriju (oblika)
try:
    real = json.load(open(tsm.MODEL_PATH, encoding="utf-8"))
    ok = all(len(v["coefficients"]) == len(vec) for v in real["leads"].values()
             for vec in [tsm.vector({"tavg": 0, "prec": 0, "wetfrac": 0})])
    check("model/sneg-mos.json: število koeficientov = število značilk", ok and real["leads"])
    check("model/sneg-mos.json: cilj je označen kot proksi", "proksi" in real["target"]["name"])
    check("model/sneg-mos.json: vsak vodilni čas ima model snega za glavno postajo (Gornji Grad)",
          all(len(v.get("obs_pp", {}).get("1748", {}).get("coefficients", [])) == 4 for v in real["leads"].values()))
    check("model/sneg-mos.json: opazovani cilj ima glavno postajo, imena postaj in opozorilo o legi",
          real["observed_target"]["primary"] == "1748" and real["observed_target"]["stations"]["1748"]["name"] == "Gornji Grad"
          and "Rečici" in real["observed_target"]["caveat"])
    check("model/sneg-mos.json: veščina na napovedanih vhodih je pri D+1..D+3 pozitivna (Gornji Grad)",
          all(real["leads"][k]["obs_pp"]["1748"]["cv"].get("skill", -1) > 0 for k in ("1", "2", "3")))
except FileNotFoundError:
    check("model/sneg-mos.json obstaja", False)

# --- napoved z lažnimi vnosi
today = dt.date(2026, 11, 10)
per_day = {(today + dt.timedelta(days=l)).isoformat(): {m: (-1.0, -5.0, 5.0) for m in tsm.MODELS} for l in (1, 2, 3, 4, 5)}
days = ps.predict_days(real, per_day, today)
check("predict_days: pet dni v sezoni", [d["lead"] for d in days] == [1, 2, 3, 4, 5])
check("predict_days: ob mrazu in padavinah je p_proxy visok, p_snow (merljiv sneg) manjši a nad 5 %",
      all(d["p_proxy"] > 0.3 and 0.05 < d["p_snow"] < d["p_proxy"] for d in days))
check("predict_days: osnova je opazovanje (preslikava je v modelu)", all(d["basis"] == "observed" for d in days))
check("predict_days: p_snow se z vodilnim časom krči proti klimatologiji (D+1 > D+5 pri enakih vhodih)", days[0]["p_snow"] > days[4]["p_snow"])
check("predict_days: višja Radegunda ima ob mrazu in dežju večjo možnost snega kot Gornji Grad", all(d["stations"]["Radegunda"] > d["stations"]["Gornji Grad"] for d in days))
check("predict_days: poleg glavne postaje so napovedane druge postaje v dolini po imenu",
      all(set(d["stations"]) == {"Gornji Grad", "Luče", "Radegunda", "Solčava"} and d["stations"]["Gornji Grad"] == d["p_snow"] for d in days))
days_apr = ps.predict_days(real, {(dt.date(2027, 4, 29) + dt.timedelta(days=l)).isoformat():
                                  {m: (-1.0, -5.0, 5.0) for m in tsm.MODELS} for l in (1, 2, 3, 4, 5)}, dt.date(2027, 4, 29))
check("predict_days: dnevi zunaj sezone (maj) izpadejo", [d["lead"] for d in days_apr] == [1])
check("predict_days: premalo modelov -> dan izpade",
      ps.predict_days(real, {(today + dt.timedelta(days=1)).isoformat(): {"best_match": (0.0, -3.0, 2.0)}}, today) == [])

# --- dnevnik
tmp = tempfile.mkdtemp()
log = os.path.join(tmp, "data", "log.csv")
payload = ps.build_payload(real, days, True, dt.datetime(2026, 11, 10, 4, 40, tzinfo=dt.timezone.utc))
# --- podatki za podrobnosti dneva na kartici (station_meta: višina samo, kjer je preverjena)
check("payload: glavna postaja in meta postaj za kartico", payload["main_station"] == "Gornji Grad"
      and payload["station_meta"]["Gornji Grad"]["alt_m"] == 428 and payload["station_meta"]["Radegunda"]["alt_m"] == 794
      and payload["station_meta"]["Luče"]["alt_m"] is None and payload["station_meta"]["Solčava"]["alt_m"] is None)

n1 = ps.append_log(payload, log)
n2 = ps.append_log(payload, log)
rows = list(csv.DictReader(open(log, encoding="utf-8")))
check("dnevnik: prvi zapis doda 5 vrstic, ponovni nič", n1 == 5 and n2 == 0 and len(rows) == 5)
check("dnevnik: stolpca p_snow in p_proxy sta zapisana", all(r["p_proxy"] != "" and r["p_snow"] != "" for r in rows))
hb = {int(r["lead_days"]): float(r["hours_before"]) for r in rows}
check("dnevnik: hours_before = ure do začetka ciljnega dne (lokalni čas)", 18.0 < hb[1] < 20.0 and abs(hb[2] - hb[1] - 24) < 1.1)
check("dnevnik: izdana datoteka ne vsebuje notranjih meritev", "indoor" not in json.dumps(payload).lower())

# stara datoteka brez stolpca p_proxy se preseli, nič ne izgine
old_log = os.path.join(tmp, "data", "old.csv")
with open(old_log, "w", encoding="utf-8", newline="") as f:
    f.write("issued_at,valid_at,lead_days,hours_before,p_snow,tavg,prec_mm,n_models,model_version\n2026-11-09T04:40:00Z,2026-11-10,1,19.3,0.1,5.0,2.0,4,0.2\n")
ps.append_log(payload, old_log)
mig = list(csv.DictReader(open(old_log, encoding="utf-8")))
check("dnevnik: migracija doda stolpec p_proxy in ohrani stare vrstice", len(mig) == 6 and mig[0]["p_proxy"] == "" and mig[0]["p_snow"] == "0.1")

# --- utrip zunaj sezone
hb_path = os.path.join(tmp, "napoved.json")
check("utrip: brez datoteke je zapis potreben", ps.heartbeat_due(hb_path, "2026-07-01"))
json.dump({"in_season": False, "generated_at": "2026-07-01T04:40:00Z"}, open(hb_path, "w"))
check("utrip: isti dan ne ponovi", not ps.heartbeat_due(hb_path, "2026-07-01"))
check("utrip: naslednji dan ponovi", ps.heartbeat_due(hb_path, "2026-07-02"))

# --- preverjanje naprej v času
rows_v = [
    {"issued_at": "a", "valid_at": "2026-12-05", "hours_before": "42.0", "p_snow": "0.1", "p_proxy": "0.8"},   # D+2, zgodnejša
    {"issued_at": "b", "valid_at": "2026-12-05", "hours_before": "30.0", "p_snow": "0.1", "p_proxy": "0.2"},   # D+2, poznejša (ignoriraj)
    {"issued_at": "c", "valid_at": "2026-12-05", "hours_before": "18.0", "p_snow": "0.1", "p_proxy": "0.9"},   # D+1
    {"issued_at": "d", "valid_at": "2026-12-05", "hours_before": "-3.0", "p_snow": "0.1", "p_proxy": "0.9"},
    {"issued_at": "e", "valid_at": "2026-12-06", "hours_before": "18.0", "p_snow": "0.1"},   # stara vrstica brez p_proxy   # dan že teče
]
best = vs.pick_issues(rows_v)
check("verify: izbere najzgodnejšo izdajo v razredu vodilnega časa",
      best[("2026-12-05", 2)][1] == 0.8 and best[("2026-12-05", 1)][1] == 0.9)
check("verify: dan, ki že teče, se ne šteje", all(k[1] in (1, 2) for k in best))
check("verify: vrstica brez p_proxy (pred v0.3) se preskoči", ("2026-12-06", 1) not in best)
res = vs.evaluate(best, {"2026-12-05": (3.0, -1.0, 1)}, real)
check("verify: Brier D+1 = (0,9 - 1)^2", abs(res["1"]["brier"] - 0.01) < 1e-9)
check("verify: malo dogodkov = zgodno", res["1"]["preliminary"] and res["1"]["events"] == 1)
check("verify: vodilni čas brez podatkov ima n = 0", res["3"]["n"] == 0)

# --- preverjanje p_snow proti snegu na Gornjem Gradu (samo različica >= 0,4)
rows_s = [
    {"issued_at": "a", "valid_at": "2026-12-05", "hours_before": "18.0", "p_snow": "0.6", "p_proxy": "0.8", "model_version": "0.4"},   # D+1, sneg 3 cm
    {"issued_at": "b", "valid_at": "2026-12-06", "hours_before": "18.0", "p_snow": "0.2", "p_proxy": "0.5", "model_version": "0.4"},   # D+1, brez snega
    {"issued_at": "c", "valid_at": "2026-12-07", "hours_before": "18.0", "p_snow": "0.9", "p_proxy": "0.9", "model_version": "0.3"},   # stara različica: preskoči
    {"issued_at": "d", "valid_at": "2026-12-08", "hours_before": "18.0", "p_snow": "0.4", "p_proxy": "0.6", "model_version": "0.4"},   # arhiv še nima dneva
]
best_s = vs.pick_issues(rows_s)
gg_series = {"2026-12-05": 3.0, "2026-12-06": 0.0, "2026-12-07": 5.0}
snow_model = {"leads": {"1": {"obs_pp": {tsm.OBS_PRIMARY: {"prevalence": 0.1}}}}}
ev_s = vs.evaluate_snow(best_s, gg_series, snow_model)
check("verify snow: upošteva samo različico >= 0,4 in dneve, ki jih arhiv že ima", ev_s["1"]["n"] == 2 and ev_s["1"]["events"] == 1)
check("verify snow: Brier D+1 = ((0,6 - 1)^2 + 0,2^2) / 2", abs(ev_s["1"]["brier"] - ((0.4 ** 2 + 0.2 ** 2) / 2)) < 1e-4)
check("verify snow: klimatologija iz modela in veščina", ev_s["1"]["brier_clim"] == round(((0.1 - 1) ** 2 + 0.1 ** 2) / 2, 4) and ev_s["1"]["skill"] is not None)
check("verify snow: malo dogodkov = zgodno, vodilni čas brez podatkov n = 0", ev_s["1"]["preliminary"] and ev_s["3"]["n"] == 0)
check("verify snow: stolpec model_version manjka -> vrstica se preskoči", vs.evaluate_snow(vs.pick_issues([
    {"issued_at": "z", "valid_at": "2026-12-05", "hours_before": "18.0", "p_snow": "0.6", "p_proxy": "0.8"}]), gg_series, snow_model)["1"]["n"] == 0)

print("\n" + ("VSE V REDU" if not fails else f"{fails} NAPAK"))
sys.exit(1 if fails else 0)
