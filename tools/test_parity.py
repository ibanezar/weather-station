#!/usr/bin/env python3
"""tools/test_parity.py — preverja, da se NAMERNE podvojitve ne razidejo.

Repozitorij ima zavestno kopije iste logike v Pythonu in JS (generator strani
proti brskalniku, worker proti klientu). CLAUDE.md pri vsaki pravi »če
spremeniš eno, spremeni drugo« — to je dogovor, ki ga nič ne preverja. Ta
skript ga preverja: JS funkcije se IZREŽEJO iz pravih datotek (app.js,
worker.js, gasilec.js, generirane strani) in poženejo na istih vhodih kot
Python kopija. Ob razhajanju test pade z vhodom, pri katerem se kopiji ločita.

Zaženi:  python3 tools/test_parity.py [-k podniz]
Zahteva node (v CI ga imajo vsi delavni toki, ki že poganjajo test_*.mjs).
"""
import json
import math
import os
import random
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FAILS = []
CHECKS = 0


def js(file, names, calls, prelude=""):
    """Izvede klice v JS kodi, izrezani iz `file`; vrne seznam rezultatov."""
    p = subprocess.run(
        ["node", os.path.join(HERE, "_parity_js.mjs")],
        input=json.dumps({"file": file, "names": names, "calls": calls, "prelude": prelude}),
        capture_output=True, text=True, cwd=ROOT, timeout=120)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        raise RuntimeError(f"node: {p.stdout[:200]} {p.stderr[:400]}")
    if "error" in out:
        raise RuntimeError(f"{file}: {out['error']}")
    return out["results"]


def js_src(file):
    with open(os.path.join(ROOT, file), encoding="utf-8") as f:
        return f.read()


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if ok:
        return
    FAILS.append((name, detail))
    print(f"  ✗ {name}  {detail}"[:int(os.environ.get("PARITY_MAXLEN", 400))])


def close(a, b, tol=1e-9):
    if a is None or b is None:
        return a is b
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ── FWI: app.js ↔ meteogasilec/gasilec.js ↔ tools/gasilec_model.py ───────────
@test
def fwi():
    """Tri kopije kanadskega FWI (glej opombo na vrhu gasilec_model.py)."""
    import gasilec_model as gm
    rnd = random.Random(7)
    series = []
    for _ in range(60):  # 60 zaporednih dni z naključnim vremenom, skozi vse mesece
        series.append((rnd.uniform(-8, 36), rnd.uniform(15, 100), rnd.uniform(0, 45),
                       rnd.choice([0, 0, 0, rnd.uniform(0, 4), rnd.uniform(0, 40)])))
    cases = []
    prev = {"ffmc": 85.0, "dmc": 6.0, "dc": 15.0}
    for i, (T, H, W, r) in enumerate(series):
        month = (i * 5 // 2) % 12
        res = gm.calc_one_day_fwi(prev, T, H, W, r, month)
        cases.append((dict(prev), T, H, W, r, month, res))
        prev = res
    # Robni primer: DMC = DC = 0 (mraz po močnem dežju). Python je tu metal
    # ZeroDivisionError, JS pa vračal NaN (popravljeno 1. 10. 2026).
    zero = {"ffmc": 40.0, "dmc": 0.0, "dc": 0.0}
    cases.append((zero, -6.0, 60.0, 10.0, 0.0, 0, gm.calc_one_day_fwi(zero, -6.0, 60.0, 10.0, 0.0, 0)))
    check(all(math.isfinite(v) for v in cases[-1][6].values()), "FWI DMC=DC=0 je končen", str(cases[-1][6]))
    calls = [{"fn": "_calcOneDayFWI", "args": [c[0], c[1], c[2], c[3], c[4], c[5]]} for c in cases]
    app = js("app.js", ["_calcOneDayFWI"], calls)
    gas = js("meteogasilec/gasilec.js", ["calcOneDayFWI"],
             [{"fn": "calcOneDayFWI", "args": c[:6]} for c in cases])
    for name, got in (("app.js", app), ("gasilec.js", gas)):
        for i, (c, g) in enumerate(zip(cases, got)):
            for k in ("ffmc", "dmc", "dc", "isi", "bui", "fwi"):
                check(close(c[6][k], g[k], 1e-9), f"FWI {name} {k}",
                      f"dan {i}: py={c[6][k]} js={g[k]} vhod={c[:6]}")
    # Stopnje: pragovi in oznake
    vals = [0, 5.19, 5.2, 11.19, 11.2, 21.29, 21.3, 37.99, 38.0, 80]
    a = js("app.js", ["_fwiClass"], [{"fn": "_fwiClass", "args": [v]} for v in vals])
    g = js("meteogasilec/gasilec.js", ["fwiClass"], [{"fn": "fwiClass", "args": [v]} for v in vals])
    for v, x, y in zip(vals, a, g):
        label, color = gm.fwi_class(v)
        check(x["label"] == label and x["col"] == color, "FWI razred app.js", f"{v}: py={label} js={x}")
        check(y["label"] == label and y["col"] == color, "FWI razred gasilec.js", f"{v}: py={label} js={y}")


# ── Vodostaj: app.js riverStationStatus ↔ generate_vodostaj_page.station_* ───
@test
def vodostaj():
    """Stanje vodomerne postaje po pragovih ARSO (klient ↔ generator strani)."""
    import generate_vodostaj_page as gv
    rnd = random.Random(11)
    stations = [
        {"vv1": 50, "vv2": 80, "vv3": 100, "znacilni": "mali pretok"},   # kot Solčava
        {"vv1": 120, "vv2": 250, "vv3": 450, "znacilni": ""},
        {"vv1": 30, "vv2": None, "vv3": None, "znacilni": "srednji pretok"},
        {"vv1": None, "vv2": None, "vv3": None},                          # kot Medlog
        {},
    ]
    cases = []
    for st in stations:
        for q in [None, 0, 0.5, 29.9, 30, 49.99, 50, 79.99, 80, 99, 100, 119.9, 120, 199.99, 200,
                  399.99, 400, 900] + [rnd.uniform(0, 500) for _ in range(20)]:
            cases.append((q, st))
    calls = [{"fn": "riverStationStatus", "args": [{**st, "pretok": q}]} for q, st in cases]
    got = js("app.js", ["_RIVER_THRESHOLDS", "riverStationStatus"], calls)
    cls = ["normal", "raised", "warning", "alarm"]
    for (q, st), g in zip(cases, got):
        lvl = gv.station_level(q, st)
        want_cls = "normal" if lvl is None else cls[lvl]
        txt = gv.station_status(q, st)
        check(g["cls"] == want_cls, "vodostaj raven", f"q={q} st={st}: py={want_cls} js={g['cls']}")
        check(g["txt"] == txt, "vodostaj oznaka", f"q={q} st={st}: py={txt!r} js={g['txt']!r}")
    th = js("app.js", ["_RIVER_THRESHOLDS"], [{"expr": "_RIVER_THRESHOLDS"}])[0]
    check(all(th[k] == gv.THRESHOLDS[k] for k in ("raised", "warning", "alarm")),
          "vodostaj približni pragovi", f"js={th} py={gv.THRESHOLDS}")


# ── Črnivec: Python (winter_engine, generate_crnivec_page) ↔ JS na strani ────
CRN_NAMES = ["LIVE_LAPSE_RATE", "LIVE_SNOW_OFFSET", "snowFractionLive", "groundTempLive", "blackIceLive",
             "cestaVrstica", "NEXT_BIAS_HOURS", "LEVEL_RANK", "tempNivo", "numSlLive", "padavineBesedilo",
             "oceniUro", "povzemiOkno", "fnv1a"]
CRN_PRELUDE = "var PASS = {elev: 902};"


# Padavine so v korakih 0,1 mm (kot Open-Meteo): vsota ne pade na izenačenje pri zaokroževanju,
# kjer se Python round() in JS Math.round() razlikujeta (0,25 → 0,2 proti 0,3).
def _crn_cases(n, seed):
    rnd = random.Random(seed)

    def maybe(x, p=0.12):
        return None if rnd.random() < p else x
    out = []
    for _ in range(n):
        out.append({
            "temp": maybe(round(rnd.uniform(-9, 14), 1), 0.05), "cloud": maybe(rnd.uniform(0, 100)),
            "wind": maybe(rnd.uniform(0, 40)), "dew": maybe(round(rnd.uniform(-12, 14), 1)),
            "p": maybe(rnd.choice([0, 0, 0.1, 0.2, 1.4])), "pPrev": maybe(rnd.choice([0, 0, 0.1, 0.11, 2.0])),
            "p3": maybe(rnd.choice([0, 0.1, 0.2, 0.3, 4.0])), "s3": maybe(rnd.choice([0, 0, 0.4, 0.5, 2.0])),
            "frac": rnd.choice([0, 0.3, 0.5, 0.7, 1]), "h": rnd.choice([1, 2, 3, 4, 5, 6, 7, 8]),
            "bias": rnd.choice([0, 0, 1.2, -2.4, 3.2])  # sode desetinke: brez izenačenj pri zaokroževanju (Python round ≠ Math.round pri x.x5),
        })
    return out


@test
def crnivec_poledica():
    """Ocena poledice, vozišča in ure: black_ice_category/road_row/eval_hour ↔ JS strani."""
    import winter_engine as we
    import generate_crnivec_page as gc
    cases = _crn_cases(400, 3)
    # robni primeri ob pragovih tal. temp. 0,5 / 1,5 in rosišča g-1
    for t, dew in [(0.5, -0.5), (0.5, -0.6), (1.5, 0.5), (1.5, 0.4), (3.5, 2.4), (-0.0, None), (2.0, 5.0)]:
        cases.append({"temp": t, "cloud": 0, "wind": 0, "dew": dew, "p": 0, "pPrev": 0, "p3": 0, "s3": 0,
                      "frac": 0, "h": 1, "bias": 0})
    src = "crnivec-site/index.html"
    calls = []
    for c in cases:
        calls.append({"fn": "groundTempLive", "args": [c["temp"], c["cloud"], c["wind"]]})
        calls.append({"fn": "blackIceLive", "args": [c["temp"], c["cloud"], c["wind"], c["dew"], c["p"], c["pPrev"]]})
        calls.append({"fn": "oceniUro", "args": [{"h": c["h"], "time": "07:00", "date": "2026-10-02", "temp": c["temp"],
                                                  "cloud": c["cloud"], "wind": c["wind"], "dew": c["dew"], "p": c["p"],
                                                  "pPrev": c["pPrev"], "p3": c["p3"], "s3": c["s3"], "frac": c["frac"]},
                                                 c["bias"]]})
    res = js(src, CRN_NAMES, calls, CRN_PRELUDE)
    for i, c in enumerate(cases):
        g_js, bi_js, hr_js = res[3 * i], res[3 * i + 1], res[3 * i + 2]
        g_py = we.ground_temp_c(c["temp"], c["cloud"], c["wind"])
        check(close(g_py, g_js, 1e-9), "tla: temperatura", f"{c}: py={g_py} js={g_js}")
        bi_py = we.black_ice_category(c["temp"], c["cloud"], c["wind"], c["dew"], c["p"], c["pPrev"])
        bi_py = bi_py[0] if bi_py else None
        check(bi_py == bi_js, "poledica", f"{c}: py={bi_py} js={bi_js}")
        e = {"h": c["h"], "time": "2026-10-02T07:00", "temp_c": c["temp"], "cloud_pct": c["cloud"],
             "wind_kmh_valley": c["wind"], "dew_c_valley": c["dew"], "precip_mm": c["p"],
             "precip_mm_prev": c["pPrev"], "precip_mm_3h": c["p3"], "snow_cm_3h": c["s3"], "snow_frac": c["frac"]}
        hp = gc.eval_hour(e, c["bias"])
        check(close(hp["temp"], hr_js["temp"], 1e-9), "ura: temperatura", f"{c}: py={hp['temp']} js={hr_js['temp']}")
        check(hp["road"]["level"] == hr_js["road"]["level"] and hp["road"]["value"] == hr_js["road"]["value"],
              "ura: vozišče", f"{c}: py={hp['road']} js={hr_js['road']}")
        check(hp["level"] == hr_js["level"] and hp["temp_level"] == hr_js["tempLevel"], "ura: raven",
              f"{c}: py={hp['level']}/{hp['temp_level']} js={hr_js['level']}/{hr_js['tempLevel']}")
    # konstante modela
    k = js(src, CRN_NAMES, [{"expr": "[LIVE_LAPSE_RATE, LIVE_SNOW_OFFSET, NEXT_BIAS_HOURS]"}], CRN_PRELUDE)[0]
    import seo_audit as seo
    check(k[0] == we.seo.LAPSE_RATE_C_PER_100M, "gradient temperature", f"js={k[0]} py={we.seo.LAPSE_RATE_C_PER_100M}")
    check(k[1] == we.SNOW_LEVEL_OFFSET_M, "odmik meje sneženja", f"js={k[1]} py={we.SNOW_LEVEL_OFFSET_M}")
    check(k[2] == gc.NEXT_BIAS_HOURS, "izzvenevanje popravka", f"js={k[2]} py={gc.NEXT_BIAS_HOURS}")


@test
def crnivec_sneg_okna_rek():
    """snow_fraction, povzetek termina in izbira »Črnivec pravi«: Python ↔ JS strani."""
    import winter_engine as we
    import generate_crnivec_page as gc
    src = "crnivec-site/index.html"
    rnd = random.Random(5)
    # delež snega
    pairs = [(902, fl) for fl in [None, 300, 500, 650, 700, 750, 800, 900, 1000, 1200, 1800]]
    pairs += [(rnd.choice([500, 723, 902, 1200]), rnd.uniform(0, 2500)) for _ in range(80)]
    got = js(src, CRN_NAMES, [{"fn": "snowFractionLive", "args": list(p)} for p in pairs], CRN_PRELUDE)
    for p, g in zip(pairs, got):
        want = we.snow_fraction(*p)
        check(close(want, g, 1e-9), "meja sneženja", f"{p}: py={want} js={g}")
    # povzetek termina (6:00-8:00): skupaj z oceno ure
    for k in range(60):
        n = rnd.choice([1, 2, 3])
        start = rnd.choice([6, 14])
        raw = []
        for j in range(n):
            c = _crn_cases(1, 100 + 7 * k + j)[0]
            raw.append(c)
        bias = rnd.choice([0, 1.2, -2.0])
        js_hours = [{"h": rnd.choice([1, 2, 3]), "time": f"{start + j:02d}:00", "date": "2026-10-02", "temp": c["temp"],
                     "cloud": c["cloud"], "wind": c["wind"], "dew": c["dew"], "p": c["p"], "pPrev": c["pPrev"],
                     "p3": c["p3"], "s3": c["s3"], "frac": c["frac"]} for j, c in enumerate(raw)]
        py_hours = [gc.eval_hour({"h": e["h"], "time": f"2026-10-02T{e['time']}", "temp_c": e["temp"],
                                  "cloud_pct": e["cloud"], "wind_kmh_valley": e["wind"], "dew_c_valley": e["dew"],
                                  "precip_mm": e["p"], "precip_mm_prev": e["pPrev"], "precip_mm_3h": e["p3"],
                                  "snow_cm_3h": e["s3"], "snow_frac": e["frac"]}, bias) for e in js_hours]
        sm_py = gc.summarize_window(py_hours)
        sm_js = js(src, CRN_NAMES, [{"expr": "povzemiOkno(" + json.dumps(js_hours) + ".map(function(e){return oceniUro(e,"
                                              + json.dumps(bias) + ");}))"}], CRN_PRELUDE)[0]
        check(sm_py["level"] == sm_js["level"] and close(sm_py["tmin"], sm_js["tmin"], 1e-9)
              and sm_py["road"]["value"] == sm_js["road"]["value"] and sm_py["precip_txt"] == sm_js["precipTxt"],
              "povzetek termina", f"vhod={js_hours} bias={bias}\n    py={sm_py}\n    js={sm_js}")
    # FNV-1a (mora dati isti indeks v obeh jezikih)
    texts = ["2026-10-02|sonce", "2026-01-01|megla", "2026-12-31|spolzko", "x", "", "čšž|nekaj", "2026-10-02|verige"]
    got = js(src, CRN_NAMES, [{"fn": "fnv1a", "args": [t]} for t in texts], CRN_PRELUDE)
    for t, g in zip(texts, got):
        check(gc.fnv1a(t) == g, "FNV-1a", f"{t!r}: py={gc.fnv1a(t)} js={g}")
    say_js = js(src, ["SAYS"], [{"expr": "SAYS"}])[0]
    check(say_js == gc.CRNIVEC_SAYS, "besedila »Črnivec pravi«",
          "SAYS v strani se razlikuje od CRNIVEC_SAYS (stran ni regenerirana ali je kopija zdrsnila)")


# ── /napovej/: worker.js točkovanje ↔ napovej/napovej.js ─────────────────────
@test
def napovej():
    """Ocena napovedi igralca: worker (_napovejSkupaj) ↔ napovej.js (oceni) in prag mokrega dne."""
    rnd = random.Random(21)
    cases = []
    for _ in range(300):
        def tv():
            return round(rnd.uniform(-15, 38), 1)
        # Samo polni vnosi: ob manjkajoči eni temperaturi worker ne oceni (null), napovej.js pa
        # oceni po preostali — razlika je znana, a v praksi nedosegljiva (igralec odda obe
        # vrednosti, forecast_verification ima vedno obe meritvi).
        cases.append(({"tmax": tv(), "tmin": tv()}, {"tmax": tv(), "tmin": tv(), "dez": 0}))
    # robovi: napaka natanko toleranca / nič / polovica
    for d in (0, 0.1, 2.5, 4.9, 5, 5.1, 12):
        cases.append(({"tmax": 20 + d, "tmin": 10 - d}, {"tmax": 20, "tmin": 10, "dez": 0}))
    cl = js("napovej/napovej.js", ["TOL_T", "napaka", "tocke", "mokro", "MOKER_MM", "TOL_DEZ", "oceni"],
            [{"fn": "oceni", "args": list(c)} for c in cases])
    wk = js("worker.js", ["NAPOVEJ_TOL_T", "_napovejSkupaj"],
            [{"fn": "_napovejSkupaj", "args": list(c)} for c in cases])
    for c, a, b in zip(cases, cl, wk):
        check(a["skupaj"] == b, "napovej: skupaj", f"{c}: napovej.js={a['skupaj']} worker={b}")
    tol_js = js("napovej/napovej.js", ["TOL_T"], [{"expr": "TOL_T"}])[0]
    tol_wk = js("worker.js", ["NAPOVEJ_TOL_T"], [{"expr": "NAPOVEJ_TOL_T"}])[0]
    check(tol_js == tol_wk, "napovej: toleranca", f"napovej.js={tol_js} worker={tol_wk}")
    # prag mokrega dne: napovej.js ↔ verify_forecasts.py ↔ train_recica_mos.py
    import verify_forecasts as vf
    import train_recica_mos as tr
    moker = js("napovej/napovej.js", ["MOKER_MM"], [{"expr": "MOKER_MM"}])[0]
    check(moker == vf.WET_DAY_MM == tr.WET_DAY_MM, "prag mokrega dne (0,2 mm)",
          f"napovej.js={moker} verify_forecasts={vf.WET_DAY_MM} train_recica_mos={tr.WET_DAY_MM}")


# ── Konstante, podvojene med worker.js in preostankom ────────────────────────
@test
def konstante_workerja():
    """IGRA_KORIDORJI_KM, CRN_IGRA_MIN_S, KOLICINE: worker.js ↔ podatki, ki jih strežnik ne more brati."""
    # Termika: dolžine koridorjev
    km = js("worker.js", ["IGRA_KORIDORJI_KM"], [{"expr": "IGRA_KORIDORJI_KM"}])[0]
    with open(os.path.join(ROOT, "igra", "koridorji.json"), encoding="utf-8") as f:
        kor = {k["id"]: k["konec_km"] for k in json.load(f)["koridorji"]}
    check(km == kor, "Termika: IGRA_KORIDORJI_KM", f"worker={km} koridorji.json={kor}")
    # Črnivec igra: spodnja meja časa = L / VMAX z rezervo
    with open(os.path.join(ROOT, "crnivec-igra", "proga.json"), encoding="utf-8") as f:
        proga = json.load(f)
    L = len(proga["k"]) - 1
    vmax = js("crnivec-igra/voznja.js", ["VMAX"], [{"expr": "VMAX"}])[0]
    min_s = js("worker.js", ["CRN_IGRA_MIN_S"], [{"expr": "CRN_IGRA_MIN_S"}])[0]
    teor = L / vmax
    check(0.85 * teor <= min_s <= teor, "Črnivec igra: CRN_IGRA_MIN_S",
          f"worker={min_s} s; najhitrejša možna vožnja L/VMAX = {L}/{vmax} = {teor:.1f} s (pričakovano 0,85–1,0 tega)")
    # opažanja gob: količine
    kol = js("worker.js", ["KOLICINE"], [{"expr": "KOLICINE"}])[0]
    html = js_src("tools/generate_gobe_page.py")
    opts = set(re.findall(r'<option value="(posamezno|nekaj|obilo|[a-z]+)">(?:Par kosov|Kar nekaj|Obilo)', html))
    js_map = set(re.findall(r'KOLICINE=\{([^}]*)\}', html)[0].replace('"', "").split(","))
    js_keys = {x.split(":")[0] for x in js_map}
    check(set(kol) == opts == js_keys, "gobe: KOLICINE",
          f"worker={kol} meni={sorted(opts)} prikaz={sorted(js_keys)}")


# ── Gobarski indeks: pragovi (gobe_model ↔ JS na strani) ─────────────────────
@test
def gobe_pragovi():
    """level()/level_class: gobe_model.py ↔ levelWord/levelClass na gobarska-napoved/."""
    import gobe_model as gm
    ps = list(range(0, 101)) + [17.99, 18.01, 34.99, 35.01, 54.99, 55.01, 74.99, 75.01]
    got = js("gobarska-napoved/index.html", ["levelWord", "levelClass"],
             [{"fn": "levelWord", "args": [p]} for p in ps] + [{"fn": "levelClass", "args": [p]} for p in ps])
    n = len(ps)
    cls_py = lambda v: "gp-pct-hi" if v >= 55 else "gp-pct-mid" if v >= 35 else "gp-pct-low" if v >= 18 else "gp-pct-none"
    for i, p in enumerate(ps):
        check(got[i] == gm.level(p), "gobe: levelWord", f"{p}: py={gm.level(p)} js={got[i]}")
        check(got[n + i] == cls_py(p), "gobe: levelClass", f"{p}: py={cls_py(p)} js={got[n + i]}")


# ── Nevihtna karta: app.js ↔ generate_storm_map.py ───────────────────────────
@test
def nevihtna_karta():
    """Obris, mreža, mesta, barvna lestvica in stopnje karte Slovenije (JS ↔ Python)."""
    import generate_storm_map as sm
    names = ["SLO_POLY", "sloPointIn", "SLO_CITIES", "buildSloGrid", "sloScoreColor", "sloScoreLevel"]
    got = js("app.js", names, [{"expr": "SLO_POLY"}, {"expr": "SLO_CITIES"}, {"expr": "buildSloGrid()"}])
    poly, cities, grid = got
    check([list(map(float, p)) for p in sm.SLO_POLY] == poly, "karta: obris Slovenije",
          f"py {len(sm.SLO_POLY)} točk, js {len(poly)} točk")
    py_cities = [{"n": c["n"], "la": c["la"], "lo": c["lo"]} for c in sm.SLO_CITIES] + [sm.STATION]
    check(py_cities == cities, "karta: mesta", f"py={py_cities}\n    js={cities}")
    check(sm.build_grid() == grid, "karta: mreža točk", f"py {len(sm.build_grid())} točk, js {len(grid)} točk")
    ss = list(range(-5, 101)) + [7.5, 22.5, 39.5, 59.5, 77.9]
    cols = js("app.js", names, [{"fn": "sloScoreColor", "args": [s]} for s in ss] +
              [{"fn": "sloScoreLevel", "args": [s]} for s in ss])
    for i, sc in enumerate(ss):
        want = list(sm.score_color(sc))
        # ±1: Python round() zaokroži x.5 na sodo, JS Math.round navzgor — na sliki ni vidno
        check(all(abs(a - b) <= 1 for a, b in zip(cols[i], want)), "karta: barva", f"ocena {sc}: py={want} js={cols[i]}")
        check(cols[len(ss) + i].upper() == sm.score_level(sc).upper() or
              (cols[len(ss) + i] == "Zelo visoko" and sm.score_level(sc) == "VISOKO") or
              (cols[len(ss) + i] == "Ekstremno" and sm.score_level(sc) == "EKSTREMNO"),
              "karta: stopnja", f"ocena {sc}: py={sm.score_level(sc)} js={cols[len(ss) + i]}")


# ── Smeri vetra in Blitzortung dekoder ───────────────────────────────────────
@test
def smeri_in_strele():
    """16 smeri (worker, gasilec.js, Python) in LZW dekodiranje strel (app.js ↔ worker.js)."""
    import generate_gasilec_page as gg
    degs = list(range(0, 361))
    wk = js("worker.js", ["_smerBesedilo"], [{"fn": "_smerBesedilo", "args": [d]} for d in degs])
    gj = js("meteogasilec/gasilec.js", ["GASILEC_DIRS"], [{"expr": "GASILEC_DIRS"}])[0]
    check(gj == gg._DIRS, "smeri: gasilec.js ↔ _DIRS", f"js={gj} py={gg._DIRS}")
    for d, w in zip(degs, wk):
        check(w == gg._dir_label(d), "smeri: worker ↔ Python", f"{d}°: worker={w} py={gg._dir_label(d)}")
    # LZW: koder iz Blitzortung lbr.js (v preludiju), dekoder iz obeh datotek
    prelude = r"""
    function encode(b){var a,c={},d=(b+"").split(""),e=[],f=d[0],g=256;for(var i=1;i<d.length;i++){a=d[i];
      null!=c[f+a]?f+=a:(e.push(1<f.length?c[f]:f.charCodeAt(0)),c[f+a]=g,g++,f=a)}
      e.push(1<f.length?c[f]:f.charCodeAt(0));for(i=0;i<e.length;i++)e[i]=String.fromCharCode(e[i]);return e.join("")}
    var _s = 12345; function rnd(){ _s = (_s * 1103515245 + 12345) & 0x7fffffff; return _s / 0x7fffffff; }
    var MSGS = []; for (var i = 0; i < 200; i++) {
      MSGS.push(JSON.stringify({time: 1.7e18 + Math.floor(rnd()*1e12), lat: 40 + rnd()*12, lon: 5 + rnd()*20,
        alt: 0, pol: 0, mds: Math.floor(rnd()*9000), mcg: Math.floor(rnd()*200), status: 0,
        region: Math.floor(rnd()*5), sig: [{sta: Math.floor(rnd()*5000), time: Math.floor(rnd()*1e6), lat: rnd()*50, lon: rnd()*20}]}));
    }
    var ENC = MSGS.map(encode);
    """
    calls = [{"expr": "ENC.map(_ltgDecode)"}, {"expr": "MSGS"}]
    app, orig = js("app.js", ["_ltgDecode"], calls, prelude)
    work, _ = js("worker.js", ["_ltgDecode"], calls, prelude)
    check(app == orig, "strele: app.js dekodira kot izvirnik", "dekodirano besedilo se razlikuje od vhodnega")
    check(work == orig, "strele: worker.js dekodira kot izvirnik", "dekodirano besedilo se razlikuje od vhodnega")


# ── Termika: opis dneva (Python) ↔ dayRating() (igra.js) ─────────────────────
@test
def igra_ocena_dneva():
    """Kategorija dneva: opis_dneva() na strani ↔ dayRating() v igri (isti pogoji, isti vrstni red)."""
    import generate_igra_page as gi
    with open(os.path.join(ROOT, "igra", "nivo.json"), encoding="utf-8") as f:
        base = json.load(f)
    cats = [("Megla.", "Megla"), ("Konvekcija seže", "Nizek strop"), ("Dežuje.", "Dežuje"),
            ("Mrtev zrak", "Mrtev zrak"), ("Šibek dan", "Šibek dan"), ("Soliden dan", "Soliden dan"),
            ("Dober dan", "Dober dan"), ("Odličen dan", "Odličen dan")]
    rnd = random.Random(9)
    levels = []
    for _ in range(400):
        levels.append({"koda_vremena": rnd.choice([0, 1, 3, 45, 48, 61]),
                       "strop_m": rnd.choice([900, 1300, 1399, 1400, 1800, 2400, 3000]),
                       "termika_ms": rnd.choice([0.5, 1.2, 1.5, 1.8, 2.3, 2.6, 2.9, 3.4, 4.5]),
                       "padavine_mm": rnd.choice([0, 0, 0.5, 1.2, 1.3, 4.0])})
    # JS: sim.ceilASL = strop; spust pri kroženju iz sinkAt() * BANK_PENALTY
    prelude = """
    var V_CIRCLE = 8.5, BANK_PENALTY = 1.35;
    function sinkAt(v) { return 0.95 + 0.0279 * (v - 8.5) * (v - 8.5); }
    var sim = {};
    function rate(l, strop) { sim = { level: l, ceilASL: strop }; return dayRating().title; }
    """
    res = js("igra/igra.js", ["fmt", "dayRating"],
             [{"expr": f"rate({json.dumps({**l, 'veter_180_ms': 0})}, {l['strop_m']})"} for l in levels], prelude)
    for l, title in zip(levels, res):
        lv = {**base, **l, "veter_180_ms": 0, "baza_m": 2000}
        opis = gi.opis_dneva(lv)
        py = next((c[1] for c in cats if opis.startswith(c[0])), None)
        check(py == title, "Termika: ocena dneva", f"{l}: stran={py!r} igra={title!r}")
    # spust pri kroženju: Python 1,28 proti sinkAt(V_CIRCLE) * BANK_PENALTY
    sink = js("igra/igra.js", ["sinkAt"], [{"expr": "sinkAt(8.5) * 1.35"}])[0]
    check(abs(sink - 1.28) < 0.01, "Termika: spust pri kroženju", f"igra={sink} stran=1.28")


def main():
    only = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv else None
    for t in TESTS:
        if only and only not in t.__name__:
            continue
        before = len(FAILS)
        print(f"\n{t.__name__} — {(t.__doc__ or '').strip().splitlines()[0] if t.__doc__ else ''}")
        try:
            t()
        except Exception as e:  # noqa: BLE001 — test, ki se ne zažene, je napaka
            FAILS.append((t.__name__, f"izjema: {e!r}"))
            print(f"  ✗ izjema: {e!r}")
            continue
        if len(FAILS) == before:
            print("  ✓ kopije so usklajene")
    print(f"\n{CHECKS} preverjanj, {len(FAILS)} razhajanj")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
