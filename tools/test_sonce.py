#!/usr/bin/env python3
"""tools/test_sonce.py — sonce v dolini (sonce_horizont, generate_sonce_page, log_solar_5min, eval_sonce) in jutro v dolini
(eval_jutro, winter_engine.compute_warmup_inputs, generate_jutro_page).
Zaženi: python3 tools/test_sonce.py"""
import csv
import datetime
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import sonce_horizont as sh  # noqa: E402
import eval_sonce as es  # noqa: E402
import eval_jutro as ej  # noqa: E402
import generate_sonce_page as gs  # noqa: E402
import generate_jutro_page as gj  # noqa: E402
import log_solar_5min as ls  # noqa: E402
import winter_engine as w  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


# ── Sonce: znane vrednosti ─────────────────────────────────────────────────
# Ljubljana (46,05 N; 14,5 E): koledarski vzhod/zahod 21. 6. 2026 = 5.11 / 20.57 (±2 min), 21. 12. okoli 7.41 / 16.17
p = sh.day_profile(46.05, 14.5, None, datetime.date(2026, 6, 21))
check(abs(p["flat_rise"] - (5 * 60 + 11)) <= 2 and abs(p["flat_set"] - (20 * 60 + 57)) <= 2, "21. 6.: vzhod 5.11, zahod 20.57")
check(abs(p["noon_elev"] - (90 - 46.05 + 23.44)) < 0.3, "opoldanska višina sonca ob solsticiju")
p = sh.day_profile(46.05, 14.5, None, datetime.date(2026, 12, 21))
check(abs(p["flat_rise"] - (7 * 60 + 41)) <= 3, "21. 12.: vzhod ~7.41")
check(p["first"] == p["flat_rise"] and p["last"] == p["flat_set"], "brez obzorja je prvi žarek = koledarski vzhod")

# obzorje: konstanta 10° premakne prvi žarek pozneje, zadnjega prej; večji odmik pomeni manj sonca
hz10 = [10.0] * 360
a = sh.day_profile(46.3, 14.9, hz10, datetime.date(2027, 6, 21))
b = sh.day_profile(46.3, 14.9, None, datetime.date(2027, 6, 21))
check(a["first"] > b["first"] and a["last"] < b["last"], "obzorje 10° skrajša dan z obeh strani")
check(a["sun_min"] < b["sun_min"] and a["segments"] == 1, "en sam odsek sonca čez dan")
lo = sh.day_profile(46.3, 14.9, hz10, datetime.date(2027, 6, 21), offset=-3.0)["sun_min"]
hi = sh.day_profile(46.3, 14.9, hz10, datetime.date(2027, 6, 21), offset=3.0)["sun_min"]
check(lo > a["sun_min"] > hi, "odmik obzorja: nižje obzorje = več sonca")
check(sh.day_profile(46.3, 14.9, [60.0] * 360, datetime.date(2027, 12, 21))["sun_min"] == 0, "obzorje 60° = brez sonca")
check(sh.day_profile(46.3, 14.9, [60.0] * 360, datetime.date(2027, 12, 21))["first"] is None, "brez sonca: prvi žarek None")
check(float(sh.horizon_at([5.0] * 360, 123.4)) == 5.0, "obzorje je konstantno")
hh = [0.0] * 360
hh[10], hh[11] = 4.0, 8.0
check(abs(float(sh.horizon_at(hh, 10.5)) - 6.0) < 1e-9, "linearna interpolacija obzorja")
check(float(sh.horizon_at([-3.0] * 360, 5.0)) == 0.0, "obzorje nikoli pod 0")
check(float(sh.horizon_at(hh, 359.9)) == 0.0 and float(sh.horizon_at(hh, 360.0)) == 0.0, "azimut 360 = 0")
check(sh.hhmm(7 * 60 + 5) == "7.05" and sh.hhmm(None) == "—", "zapis ure s piko")
# preklop ure: 28. 3. 2027 (v zimski čas) — dan ima še vedno 1440 minutnih vzorcev, vzhod ostane razumen
p = sh.day_profile(46.3, 14.9, None, datetime.date(2027, 3, 28))
check(5 * 60 < p["flat_rise"] < 7 * 60 + 30, "preklop ure: vzhod 28. 3. smiseln")

# ── Obzorje iz DEM (committano): oblika in verjetnost ──────────────────────
hz = sh.load_horizons()
check(len(hz["places"]) == 7, "horizons.json: 7 krajev")
for pl in hz["places"]:
    hz_ok = len(pl["horizon"]) == 360 and 0 <= min(pl["horizon"]) and max(pl["horizon"]) < 50
    check(hz_ok, f"obzorje {pl['name']}: 360 vrednosti v razumnem razponu")
    check(abs(pl["dem_m"] - pl["elev"]) < 15, f"višina DEM ~ zapisana višina ({pl['name']})")
byid = {pl["id"]: pl for pl in hz["places"]}
check(sum(byid["solcava"]["horizon"]) > sum(byid["recica"]["horizon"]), "Solčava ima višje obzorje kot Rečica")

# ── zero_runs ──────────────────────────────────────────────────────────────
check(gs.zero_runs([5] * 10) == [], "brez ničel: ni obdobij")
r = gs.zero_runs([0, 0, 5, 5, 0, 0, 0])
check(r == [(4, 1, 5)], f"obdobje čez konec leta je eno: {r}")
check(gs.zero_runs([5, 0, 0, 5, 0, 5]) == [(1, 2, 2), (4, 4, 1)], "dve ločeni obdobji")

# ── generator strani: deterministična, brez notranjih ključev ──────────────
page_path = os.path.join(ROOT, "sonce-v-dolini", "index.html")
json_path = os.path.join(ROOT, "sonce-v-dolini", "dnevi.json")
before_p, before_j = open(page_path, encoding="utf-8").read(), open(json_path, encoding="utf-8").read()
gs.main()
after_p, after_j = open(page_path, encoding="utf-8").read(), open(json_path, encoding="utf-8").read()
check(before_p == after_p and before_j == after_j, "committana stran in dnevi.json so enaki izhodu generatorja")
dj = json.loads(after_j)
check(set(dj["p"]) == {p_["id"] for p_ in hz["places"]}, "dnevi.json: vsi kraji")
check(all(len(v["d"]) == 365 and all(len(row) == 7 for row in v["d"]) for v in dj["p"].values()), "dnevi.json: 365 dni × 7 polj")
for pid, v in dj["p"].items():
    check(all(row[5] >= row[4] >= row[6] for row in v["d"]), f"dnevi.json {pid}: nižje obzorje ≥ sredina ≥ višje obzorje")
check(all(len(v["d"][0]) == 7 for v in dj["p"].values()), "polja")
for txt, nm in ((after_p, "sonce-v-dolini"), (open(os.path.join(ROOT, "data", "horizons.json"), encoding="utf-8").read(), "horizons.json")):
    low = txt.lower()
    check("indoor" not in low and "tempinf" not in low, f"{nm}: brez notranjih meritev")
import re  # noqa: E402
title = re.search(r"<title>(.*?)</title>", after_p).group(1)
check(len(title) <= 60, f"<title> ≤ 60 znakov ({len(title)})")
check("Copernicus" in after_p and "faq" in after_p, "navedba vira in FAQ")

# ── detekcija prvega žarka (eval_sonce) ────────────────────────────────────
def synth(start_min=300, end_min=660, jump_at=515, jump=120.0, diffuse=lambda m: 10 + (m - 300) * 0.05, drop_after=None):
    ser = []
    for m in range(start_min, end_min, 5):
        v = diffuse(m)
        if m >= jump_at:
            v += jump + (m - jump_at) * 0.6
        if drop_after is not None and jump_at <= m < drop_after:
            v -= jump
        ser.append((m, v))
    return ser


s1 = synth()
t = es.detect_first_ray(s1)
check(t is not None and abs(t - 512.5) < 0.01, f"skok ob 8.35 zaznan kot 8.32,5 ({t})")
check(es.detect_first_ray(synth(jump=10.0)) is None, "premajhen skok se ne šteje")
flicker = [(m, 10 + (m - 300) * 0.05 + (120.0 if 515 <= m < 530 else 0.0)) for m in range(300, 660, 5)]  # kratek presek oblakov
check(es.detect_first_ray(flicker) is None, "kratek sij skozi oblak, ki ga zbriše, ni prvi žarek")
check(es.detect_first_ray([(m, 20.0) for m in range(300, 660, 5)]) is None, "brez skoka: None")
ev = [(m, v) for m, v in reversed(synth())]  # zrcalno: zvečer sevanje pade
ev_series = [(1000 + (660 - m), v) for m, v in synth()]  # čas naprej, sevanje pada
t_ev = es.detect_first_ray(sorted(ev_series), reverse=True)
check(t_ev is not None, f"zadnji žarek zvečer zaznan ({t_ev})")

# ── zapis 5-minutnih meritev (log_solar_5min) ──────────────────────────────
day = "2026-10-03"
tz = ls.uh.TZ
def ts(h, m):
    return str(int(datetime.datetime(2026, 10, 3, h, m, tzinfo=tz).timestamp()))
solar_list, temp_list, indoor_list = {}, {}, {}
for hh_ in range(0, 24):
    for mm in range(0, 60, 5):
        solar_list[ts(hh_, mm)] = {"value": 100.0 + hh_}
        temp_list[ts(hh_, mm)] = {"value": 7.5}
        indoor_list[ts(hh_, mm)] = {"value": 99.0}
fake = {"solar_and_uvi": {"solar": {"list": solar_list}}, "outdoor": {"temperature": {"list": temp_list}},
        "indoor": {"temperature": {"list": indoor_list}}}
rows = ls.rows_from_ecowitt(fake, day)
times = [r["time_local"] for r in rows]
fr = sh.day_profile(__import__("generate_seo_pages").LAT, __import__("generate_seo_pages").LON, None, datetime.date(2026, 10, 3))
check(0 < len(rows) < 140, f"samo okni ob vzhodu in zahodu ({len(rows)} točk)")
check(all(r["date"] == day for r in rows), "datum v vsaki vrstici")
mins = [int(t_[:2]) * 60 + int(t_[3:]) for t_ in times]
check(min(mins) >= fr["flat_rise"] - 30 - 5 and max(mins) <= fr["flat_set"] + 30, "okni sta v mejah vzhod − 30 min … zahod + 30 min")
check(not any(fr["flat_rise"] + 270 < mn < fr["flat_set"] - 270 for mn in mins), "sredi dneva ni zapisov")
check(all(r["solar_wm2"] != "" and r["temp_c"] == 7.5 for r in rows), "sevanje in temperatura zapisana")
check(all(99.0 != r["temp_c"] for r in rows), "notranjih meritev ne bere")
check(len(set(times)) == len(times), "en zapis na 5 minut")

# ── eval_jutro ─────────────────────────────────────────────────────────────
def morning(day_tmin=2.0, warm_from=9, wind=1.0, rng_top=18.0):
    """Urna povprečja: noč na tmin, od warm_from rast 2 °C/h do rng_top."""
    hours = {}
    for h in range(24):
        if h < warm_from:
            t_ = day_tmin
        else:
            t_ = min(day_tmin + 2.0 * (h - warm_from + 1), rng_top)
        hours[h] = (t_, wind)
    return hours
m = ej.morning_metrics(morning())
check(m is not None and m[0] == 2.0, "jutranji minimum")
# urna povprečja: ura 9 = 4,0, ura 10 = 6,0 (središči 9.30 in 10.30) → +3 °C (5,0) je na sredini = 10.00 = 600 min
check(m[2] is not None and abs(m[2] - 600) < 1e-6, f"čas dviga +3 °C iz interpolacije ({m[2]})")
check(abs(ej.morning_metrics(morning(warm_from=8))[2] - 540) < 1e-6, "interpolacija: dvig 1 h prej = 540 min")
check(ej.morning_metrics({h: (1.0, 1.0) for h in range(10)}) is None, "premalo ur: dan se ne šteje")
days = {}
d0 = datetime.date(2026, 10, 1)
for k in range(12):
    days[(d0 + datetime.timedelta(days=k)).isoformat()] = morning(warm_from=9)
days["2026-10-20"] = morning(warm_from=9, wind=6.0)           # vetrovno: izključeno
days["2026-10-21"] = morning(warm_from=9, rng_top=8.0)       # razpon < 10: izključeno
rec = byid["recica"]
rows_j = ej.collect(days, rec)
check(len(rows_j) == 12, f"samo jasna, mirna jutra ({len(rows_j)})")
st = ej.month_stats(rows_j)
check(st[10]["n"] == 12, "statistika po mesecih")
lg = ej.lag_for_month({str(k): v for k, v in st.items()}, 10)
check(lg is not None and lg["n"] == 12 and lg["months"] == [9, 10, 11], f"zamik oktobra iz sosednjih mesecev ({lg})")
check(ej.lag_for_month({str(k): v for k, v in st.items()}, 12) is None, "december brez meritev: brez zamika")
check(ej.lag_for_month({"10": {"n": 5, "sum": 7.5, "sumsq": 12.0}}, 10) is None, "pod MIN_N: brez zamika")
pooled = ej.lag_for_month({"9": {"n": 4, "sum": 6.0, "sumsq": 9.2}, "10": {"n": 6, "sum": 9.0, "sumsq": 13.8}}, 10)
check(pooled and abs(pooled["mean_h"] - 1.5) < 1e-9, "združevanje sosednjih mesecev je točno (n-uteženo)")

# ── winter_engine.compute_warmup_inputs ───────────────────────────────────
times = [f"2026-11-0{d}T{h:02d}:00" for d in (3, 4, 5, 6) for h in range(24)]
hourly = {"temperature_2m": [(-2.0 if (i % 24) < 8 else 5.0) for i in range(len(times))],
          "cloud_wind": None,
          "cloud_cover": [10] * len(times), "wind_speed_10m": [2.0] * len(times), "precipitation": [0.0] * len(times)}
out = w.compute_warmup_inputs(hourly, times, 8)  # 3. 11., ura 8 → danes še velja
check(out and out[0]["date"] == "2026-11-03" and len(out) == w.WARMUP_MORNINGS, "jutri in danes dopoldne vključena")
check(out[0]["tmin_c"] == -2.0 and out[0]["cloud_pct"] == 10 and out[0]["wind_kmh"] == 2.0, "povzetki jutra")
out2 = w.compute_warmup_inputs(hourly, times, 14)  # 3. 11., ura 14 → današnje jutro je mimo
check(out2 and out2[0]["date"] == "2026-11-04", "po 10. uri današnje jutro odpade")
check(w.compute_warmup_inputs(hourly, times[:30], 8) is not None, "premalo ur: ne pade")
check(w.compute_warmup_inputs({}, [], None) is None, "brez ure: None")

# ── generate_jutro_page ────────────────────────────────────────────────────
stats = {"meseci": {"10": {"n": 20, "sum": 30.0, "sumsq": 48.0}, "11": {"n": 0, "sum": 0.0, "sumsq": 0.0}}, "min_n": 8}
good = {"date": "2026-11-04", "tmin_c": -2.0, "tmin_hour": 6, "cloud_pct": 10, "wind_kmh": 2.0, "precip_mm": 0.0}
r1 = gj.predict_morning(good, rec, stats)
check("mid" in r1 and r1["lo"] < r1["mid"] < r1["hi"], "jasno, mirno, zamik znan: napoved z razponom")
check(abs(r1["mid"] - (r1["pr"]["first"] + 90)) <= 3, "napoved = prvi žarek + povprečni zamik")
r2 = gj.predict_morning({**good, "cloud_pct": 80}, rec, stats)
check("mid" not in r2 and not r2["clear_calm"], "oblačno: brez napovedi")
r3 = gj.predict_morning({**good, "wind_kmh": 9.0}, rec, stats)
check("mid" not in r3, "vetrovno: brez napovedi")
r4 = gj.predict_morning({**good, "date": "2026-12-15"}, rec, stats)
check("mid" not in r4 and r4["clear_calm"] and r4["lag"] is None, "december brez meritev: brez napovedi")
html_ok = gj.fmt_morning(r1)
check("približno ob" in html_ok and "razpon" in html_ok, "stran pove uro in razpon")
check("še nimam dovolj" in gj.fmt_morning(r4), "stran pove, zakaj ure ni")
check("ne bo jasno in mirno" in gj.fmt_morning(r2), "stran pove, zakaj pravilo ne velja")
# beleženje napovedi: danes se ne beleži, jutri da, zadnja izdaja prepiše
tmp = tempfile.mkdtemp()
gj.PRED_PATH = os.path.join(tmp, "jutro-napovedi.csv")
today = datetime.date(2026, 11, 3)
gj.log_predictions([r1, gj.predict_morning({**good, "date": "2026-11-03"}, rec, stats)], today)
rows_l = list(csv.DictReader(open(gj.PRED_PATH, encoding="utf-8")))
check([r["date"] for r in rows_l] == ["2026-11-04"], "beleži samo jutra po današnjem")
check(rows_l[0]["clear_calm"] == "1" and rows_l[0]["mid_min"] != "", "zapisana napoved")
gj.log_predictions([r2], today)
rows_l = list(csv.DictReader(open(gj.PRED_PATH, encoding="utf-8")))
check(len(rows_l) == 1 and rows_l[0]["clear_calm"] == "0" and rows_l[0]["mid_min"] == "", "novejša izdaja prepiše")
# ocena napovedi proti izmerjenemu dnevu
ej.PRED_PATH = gj.PRED_PATH
with open(gj.PRED_PATH, "w", encoding="utf-8", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=gj.PRED_FIELDS)
    wr.writeheader()
    wr.writerow({"date": "2026-10-01", "issued": "2026-09-30", "first_min": 450, "lo_min": 520, "mid_min": 560, "hi_min": 600,
                 "tmin_fc": 2, "clear_calm": "1"})
ev_res = ej.evaluate_predictions({"2026-10-01": morning(warm_from=9)}, gj.PRED_PATH)
check(ev_res["n"] == 1 and ev_res["v_razponu"] in (0, 1), f"ocena napovedi: {ev_res}")
check(ej.evaluate_predictions({}, gj.PRED_PATH)["n"] == 0, "brez izmerjenega dne ni ocene")

if fails:
    print(f"\n{fails} preverjanj ni uspelo.")
    sys.exit(1)
print("✓ test_sonce: vse OK")
