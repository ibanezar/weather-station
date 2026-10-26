#!/usr/bin/env python3
"""
tools/test_mtr_wind.py — veter in sunki v MTR (24. 10. 2026): dnevni stolpci, skala povprečnega vetra, ridge sunkov,
walk-forward veščina, predict_day, živa pot (dodatne spremenljivke samo, kadar jih model rabi) in izris kartice
(prava koda renderMtrWind iz app.js, izrezana s tools/_parity_js.mjs).
"""
import csv, datetime as dt, json, math, os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import train_recica_mos as mos  # noqa: E402
import predict_recica_mos as pm  # noqa: E402

fails = []


def check(ok, name):
    if not ok:
        fails.append(name)
        print("  ✗", name)


def close(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol


# ── wind_columns ───────────────────────────────────────────────────────────────
def day_series(speed_n=2.0, speed_d=6.0, gust_n=4.0, gust_d=12.0, direction=90.0, hours=24):
    sp = [(h, speed_n if h <= 8 else speed_d) for h in range(hours)]
    gu = [(h, gust_n if h <= 8 else gust_d) for h in range(hours)]
    di = [(h, direction) for h in range(hours)]
    return {"wind_speed_10m": sp, "wind_gusts_10m": gu, "wind_direction_10m": di}


c = mos.wind_columns(day_series())
check(c is not None and close(c["wmean"], (9 * 2 + 15 * 6) / 24) and c["wmax"] == 6.0, "wind_columns: povprečje in največ")
check(close(c["wn"], 2.0) and close(c["wd"], 6.0) and c["gmax"] == 12.0 and close(c["gmean_d"], 12.0), "wind_columns: noč/dan/sunki")
check(close(c["ex"], 1.0) and abs(c["ey"]) < 1e-9, "wind_columns: smer 90° = vzhod (ex=1, ey=0)")
check(mos.wind_columns(day_series(hours=19)) is None, "wind_columns: premalo ur → None")
check(mos.wind_columns({k: v for k, v in day_series().items() if k != "wind_gusts_10m"}) is None, "wind_columns: brez sunkov → None")
no_dir = {k: v for k, v in day_series().items() if k != "wind_direction_10m"}
cn = mos.wind_columns(no_dir)
check(cn is not None and cn["ex"] == 0.0 and cn["ey"] == 0.0, "wind_columns: brez smeri ex=ey=0, ne None")
as_lists = {k: [[h, v] for h, v in vs] for k, vs in day_series().items()}
check(mos.wind_columns(as_lists)["wmean"] == c["wmean"], "wind_columns: sprejme tudi sezname [[ura, v]] iz predpomnilnika")

f_stub = {"cloud": 50.0, "cloud_n": 20.0, "rad": 300.0, "pres": 1013.0, "sin_doy": 0.0, "cos_doy": 1.0}
v = mos.wind_vector(c, f_stub)
check(len(v) == len(mos.WIND_FEATURES) == 15 and v[0] == 1.0 and close(v[1], math.log1p(c["wmean"])), "wind_vector: dolžina in prvi stolpci")

# ── skala, sunki, walk-forward (sintetični podatki: postaja = 0,5 × model, sunek = 0,6 × največji modelski sunek)
rng = random.Random(1)
samples = []
d0 = dt.date(2024, 6, 1)
for i in range(700):
    day = d0 + dt.timedelta(days=i)
    wm = rng.uniform(1.0, 9.0)
    gm = wm * rng.uniform(2.0, 3.5)
    col = {"wmean": wm, "wmax": wm * 1.6, "wn": wm * 0.7, "wd": wm * 1.2, "gmax": gm, "gmean_d": gm * 0.8,
           "ex": rng.uniform(-1, 1), "ey": rng.uniform(-1, 1)}
    doy = day.timetuple().tm_yday
    f = {"cloud": rng.uniform(0, 100), "cloud_n": rng.uniform(0, 100), "rad": rng.uniform(0, 500),
         "pres": 1013 + rng.uniform(-15, 15), "sin_doy": math.sin(2 * math.pi * doy / 365.25),
         "cos_doy": math.cos(2 * math.pi * doy / 365.25)}
    samples.append({"date": day.isoformat(), "f": f, "c": col, "mean": 0.5 * wm, "gust": 0.6 * gm})

check(close(mos.fit_wind_ratio(samples), 0.5), "fit_wind_ratio: ~0,5")
low = [dict(s, c=dict(s["c"], wmean=0.2), mean=5.0) for s in samples[:50]]    # pod pragom: ne šteje
check(close(mos.fit_wind_ratio(samples + low), 0.5), "fit_wind_ratio: dnevi z vetrom pod WIND_MIN_OM se ne štejejo")
co, lam = mos.fit_wind_gust(samples)
err = sum(abs(mos.predict_wind_gust(co, s["c"], s["f"]) - s["gust"]) for s in samples) / len(samples)
check(err < 0.6 and lam in mos.WIND_LAMBDA_GRID, f"fit_wind_gust: MAE {err:.2f} km/h na sintetičnih podatkih")
check(mos.predict_wind_gust([-50.0] + [0.0] * 14, samples[0]["c"], samples[0]["f"]) == 0.0, "predict_wind_gust: nikoli pod 0")
sk = mos.walk_forward_wind(samples, "gust")
check(sk and sk["mae_meteorec"] < sk["mae_open_meteo"] * 0.5 and sk["improvement_pct"] > 50 and sk["n"] > 100,
      f"walk_forward_wind(gust): {sk}")
skm = mos.walk_forward_wind(samples, "mean")
check(skm and abs(skm["mae_meteorec"] - skm["mae_scalar"]) < 1e-9 and skm["mae_meteorec"] < 0.05
      and abs(skm["bias_meteorec"]) < 0.05 and skm["bias_open_meteo"] > 1.0, f"walk_forward_wind(mean): {skm}")
check(mos.walk_forward_wind(samples[:60], "gust") is None, "walk_forward_wind: premalo mesecev → None")

# build_wind_samples: dan brez meritve ali brez stolpcev odpade
base = [{"date": "2026-01-01", "f": f_stub}, {"date": "2026-01-02", "f": f_stub}, {"date": "2026-01-03", "f": f_stub}]
hist = {"2026-01-01": {"windspeedAvg": 1.0, "windgustHigh": 8.0},
        "2026-01-02": {"windspeedAvg": 1.0},                      # brez sunka
        "2026-01-03": {"windspeedAvg": 1.0, "windgustHigh": 9.0}}
merged = {"2026-01-01": day_series(), "2026-01-02": day_series()}   # 3. dan brez serij
ws = mos.build_wind_samples(base, merged, hist)
check([w["date"] for w in ws] == ["2026-01-01"] and ws[0]["gust"] == 8.0 and ws[0]["mean"] == 1.0,
      "build_wind_samples: odpadeta dan brez sunka in dan brez serij")

# ── predict_day ──────────────────────────────────────────────────────────────────
def full_day_series():
    s = {"temperature_2m": [(h, 5.0 + (h % 12)) for h in range(24)],
         "precipitation": [(h, 0.0) for h in range(24)],
         "cloud_cover": [(h, 40.0) for h in range(24)],
         "relative_humidity_2m": [(h, 80.0) for h in range(24)],
         "pressure_msl": [(h, 1015.0) for h in range(24)],
         "shortwave_radiation": [(h, 200.0 if 8 <= h <= 17 else 0.0) for h in range(24)]}
    s.update(day_series())
    return s


series = full_day_series()
feats = mos.daily_features(series, "2026-10-25")
check(feats is not None, "daily_features ne potrebuje sunkov (temperaturni model je neodvisen)")
feats["wind_c"] = mos.wind_columns(series)
nt = len(mos.temp_vector(feats, "tmax"))
npop = len(mos.pop_vector(feats, False))
wentry = {"mean": {"method": "scalar", "ratio": 0.5,
                   "skill": {"mae_open_meteo": 2.2, "mae_meteorec": 0.6}},
          "gust": {"method": "ridge_log1p", "coefficients": [round(x, 6) for x in co], "lambda": lam,
                   "skill": {"mae_open_meteo": 7.1, "mae_meteorec": 3.9}}}
model = {"leads": {"1": {"coefficients": {"tmax": [0.0] * nt, "tmin": [0.0] * nt, "pop": [0.0] * npop},
                         "residual_sd": {"tmax": 1.0, "tmin": 1.0}, "skill": {}, "wind": wentry}}}
out = pm.predict_day(model, 1, feats)
check(out and out["om_wind"] == round(feats["wind_c"]["wmean"], 1) and out["wind"] == round(0.5 * feats["wind_c"]["wmean"], 1),
      f"predict_day: povprečni veter = skala × Open-Meteo ({out and (out['wind'], out['om_wind'])})")
check(out["gust"] == round(mos.predict_wind_gust(co, feats["wind_c"], feats), 1) and out["om_gust"] == 12.0,
      "predict_day: sunki iz ridge, om_gust = največji modelski sunek")
check(out["gust_mae"] == 3.9 and out["gust_mae_om"] == 7.1, "predict_day: napaka sunkov za kartico")
nogust = json.loads(json.dumps(model))
del nogust["leads"]["1"]["wind"]["gust"]
o2 = pm.predict_day(nogust, 1, feats)
check(o2["wind"] is not None and o2["gust"] is None and o2["gust_mae"] is None, "predict_day: brez modela sunkov ostane samo veter")
feats_nw = dict(feats, wind_c=None)
o3 = pm.predict_day(model, 1, feats_nw)
check(all(o3[k] is None for k in ("wind", "gust", "om_wind", "om_gust", "gust_mae", "gust_mae_om")),
      "predict_day: brez sunkov v živi napovedi so vsa polja vetra None (kartica jih skrije)")
nowind = json.loads(json.dumps(model))
del nowind["leads"]["1"]["wind"]
check(pm.predict_day(nowind, 1, feats)["wind"] is None, "predict_day: model brez vetra (stari model) deluje kot prej")

# ── živa pot: dodatne spremenljivke samo, kadar jih model rabi ───────────────────
tmp = tempfile.mkdtemp()
pm.OUT_PATH, pm.LIVE_PATH, pm.LIVE_LOG_PATH = (os.path.join(tmp, "n.json"), os.path.join(tmp, "l.json"),
                                               os.path.join(tmp, "log.csv"))
calls = []
today = dt.date.today()


def fake_live(model_id=None, variables=None):
    calls.append(variables)
    rows = {}
    for l in range(0, 4):
        rows[(today + dt.timedelta(days=l)).isoformat()] = full_day_series()
    return rows


pm.fetch_live_forecast = fake_live
pm.fetch_wn2_spread = lambda: {}
sys.argv = ["predict_recica_mos.py", "--live"]
for l in ("2", "3"):
    model["leads"][l] = model["leads"]["1"]
pm.load_model = lambda: model
check(pm.main() == 0, "živa pot: izhod 0 z modelom z vetrom")
check(calls and calls[0] == mos.HOURLY_VARS + mos.WIND_EXTRA_VARS, f"živa pot: zahteva dodatne spremenljivke ({calls[:1]})")
live = json.load(open(pm.LIVE_PATH, encoding="utf-8"))
check(len(live["days"]) == 3 and all(d["wind"] is not None and d["gust"] is not None for d in live["days"]),
      "živa pot: dnevi nosijo veter in sunke")
calls.clear()
model_nw = {"leads": {l: {k: v for k, v in e.items() if k != "wind"} for l, e in model["leads"].items()}}
pm.load_model = lambda: model_nw
os.remove(pm.LIVE_PATH)
check(pm.main() == 0 and calls and calls[0] is None, f"živa pot: model brez vetra kliče kot prej, brez novih spremenljivk ({calls[:1]})")
live2 = json.load(open(pm.LIVE_PATH, encoding="utf-8"))
check(all(d["wind"] is None and d["gust"] is None for d in live2["days"]), "živa pot: model brez vetra → polja vetra None")

# ── kartica (prava koda iz app.js) ──────────────────────────────────────────────
days = [{"date": "2026-10-25", "lead": 1, "wind": 1.1, "gust": 10.5, "om_wind": 2.3, "om_gust": 10.8,
         "gust_mae": 3.9, "gust_mae_om": 7.1},
        {"date": "2026-10-26", "lead": 2, "wind": 0.3, "gust": 4.2, "om_wind": 3.2, "om_gust": 12.6,
         "gust_mae": 4.4, "gust_mae_om": 8.4},
        {"date": "2026-10-27", "lead": 3, "wind": None, "gust": None, "om_wind": None, "om_gust": None}]
prelude = ("var EL={hidden:true,innerHTML:''};var document={getElementById:function(id){return id==='mos-wind'?EL:null;}};"
           "var MTR_CC={mtr:'#059669',om:'#a855f7'};"
           "function _mtrDayName(d){return d.lead===1?'jutri':'pojutrišnjem';}"
           "var _mtrState={days:" + json.dumps(days) + "};")


def render(prel):
    p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")], capture_output=True, text=True, cwd=ROOT, timeout=60,
                       input=json.dumps({"file": "app.js", "names": ["renderMtrWind"], "prelude": prel,
                                         "calls": [{"expr": "renderMtrWind('mos-'),[EL.hidden,EL.innerHTML]"}]}))
    out = json.loads(p.stdout)
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["results"][0]


hidden, html = render(prelude)
check(hidden is False and 'wb-v">1<small>km/h</small><em>surov 2</em>' in html and 'wb-v">11<small>km/h</small><em>surov 11</em>' in html,
      "kartica: jutri veter 1 (surov 2), sunki 11 (surov 11) km/h")
check(html.count('<u class="wb-om"') == 4 and "surov Open-Meteo" in html and "umerjeno na postajo" in html,
      "kartica: oznaka surovega Open-Meteo ob vsakem stolpcu in legenda umerjeno")
check("wb-bar" in html and html.count('class="wb-axis"') == 1, "kartica: stolpci in ena skupna os")
check('wb-v">&lt;' in html or 'wb-v"><' in html or "veter< 1<span>" in html, "kartica: veter pod 0,5 km/h se izpiše kot < 1")
check(html.count("mtr-wind-row") == 2, "kartica: dan brez vetra in sunkov nima vrstice")
check("~4 km/h (surov model ~7 km/h)" in html, "kartica: napaka sunka iz prvega dne s podatkom")
hidden2, html2 = render(prelude.replace(json.dumps(days), json.dumps([days[2]])))
check(hidden2 is True and html2 == "", "kartica: brez podatkov je skrita")
hidden3, html3 = render(prelude.replace('"gust_mae": 3.9, "gust_mae_om": 7.1', '"gust_mae": null').replace(
    '"gust_mae": 4.4, "gust_mae_om": 8.4', '"gust_mae": null'))
check(hidden3 is False and "Napaka največjega sunka" not in html3, "kartica: brez gust_mae stavka o napaki ni")

print("OK" if not fails else f"{len(fails)} FAIL")
sys.exit(1 if fails else 0)
