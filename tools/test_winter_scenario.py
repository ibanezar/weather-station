#!/usr/bin/env python3
"""tools/test_winter_scenario.py — generalka zimskega cevovoda na SINTETIČNI zimi.

Zakaj: snežna karta, žled in vreme v gorah so bili pisani poleti in jih še nikoli ni poganjal pravi sneg.
Test v začasni KOPIJI repozitorija podtakne winter_engine.fetch_open_meteo() sintetično napoved
(topel začetek -> hladna fronta s snegom -> žled s toplo plastjo nad mrazom), požene pravi
`winter_engine.main()` in nato generatorje strani nad dobljenim `data/winter-data.json`. Preveri, da:
  - noben izračun ne pade, v podatkih ni NaN/None tam, kjer scenarij zahteva vrednost,
  - sneg, meja sneženja, žled, poledica, kurilni semafor in gore dajo pričakovano smer,
  - generirane strani ne vsebujejo "None", "nan", "undefined", "{{" in so neprazne.
Brez omrežja. Zaženi: python3 tools/test_winter_scenario.py
"""
import datetime
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


def copy_repo(dst):
    skip = shutil.ignore_patterns(".git", "node_modules", "img", "photos", "__pycache__", "*.jpg", "*.png", "*.webp", "*.woff2", "*.pdf")
    shutil.copytree(REPO, dst, ignore=skip)


def synthetic(now_local):
    """Urna napoved v obliki Open-Meteo: 1 dan nazaj + 8 dni naprej. Dan 0-1 topel, dan 2-3 snežna fronta, dan 4 žled."""
    start = (now_local - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    n = 24 * 9
    H = {k: [] for k in ["time", "temperature_2m", "dew_point_2m", "cloud_cover", "wind_speed_10m", "precipitation",
                         "freezing_level_height", "precipitation_probability"]}
    for hpa in (925, 850, 700):
        for k in (f"temperature_{hpa}hPa", f"geopotential_height_{hpa}hPa", f"wind_speed_{hpa}hPa"):
            H[k] = []
    geo = {925: 760.0, 850: 1500.0, 700: 3000.0}
    for i in range(n):
        t = start + datetime.timedelta(hours=i)
        d = (t.date() - now_local.date()).days          # -1 .. 7
        h = t.hour
        diurnal = 3.0 * math.sin((h - 9) / 24 * 2 * math.pi)
        if d <= 1:       # topel začetek
            t2, fl, pr, t925, t850, cloud = 9 + diurnal, 2600, 0.0, 7, 3, 40
        elif d <= 3:     # hladna fronta s snegom
            t2, fl, pr, t925, t850, cloud = -2.5 + diurnal * .6, 350, (1.4 if 4 <= h <= 20 else 0.2), -4, -8, 95
        elif d == 4:     # žled: toplejša plast nad mrzlo dolino
            t2, fl, pr, t925, t850, cloud = -1.8, 1900, (0.8 if 2 <= h <= 14 else 0.0), 1.8, 2.5, 100
        else:            # jasno in mrzlo
            t2, fl, pr, t925, t850, cloud = -6 + diurnal, 500, 0.0, -2, -7, 5
        H["time"].append(t.strftime("%Y-%m-%dT%H:%M"))
        H["temperature_2m"].append(round(t2, 1))
        H["dew_point_2m"].append(round(t2 - (0.4 if pr else 2.5), 1))
        H["cloud_cover"].append(cloud)
        H["wind_speed_10m"].append(4.0 if cloud > 90 else 12.0)
        H["precipitation"].append(pr)
        H["freezing_level_height"].append(float(fl))
        H["precipitation_probability"].append(90 if pr else 5)
        for hpa, tv in ((925, t925), (850, t850), (700, t850 - 6)):
            H[f"temperature_{hpa}hPa"].append(float(tv))
            H[f"geopotential_height_{hpa}hPa"].append(geo[hpa])
            H[f"wind_speed_{hpa}hPa"].append({925: 20.0, 850: 35.0, 700: 60.0}[hpa])
    return {"hourly": H}


def bad_text(html):
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", body)
    out = []
    for pat in (r"\bNone\b", r"\bnan\b", r"\bundefined\b", r"\{\{", r"\bNaN\b"):
        if re.search(pat, text):
            out.append(pat)
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="winter-scn-")
    work = os.path.join(tmp, "repo")
    try:
        copy_repo(work)
        runner = os.path.join(tmp, "run_scenario.py")
        open(runner, "w", encoding="utf-8").write(
            "import sys, datetime, importlib.util\n"
            f"sys.path.insert(0, {os.path.join(work, 'tools')!r})\n"
            f"spec = importlib.util.spec_from_file_location('scn', {os.path.join(work, 'tools', 'test_winter_scenario.py')!r})\n"
            "scn = importlib.util.module_from_spec(spec); spec.loader.exec_module(scn)\n"
            "import winter_engine as w\n"
            "now = datetime.datetime.now(w.LOCAL_TZ)\n"
            "w.fetch_open_meteo = lambda: scn.synthetic(now)\n"
            "w.compute_pass_calibration = lambda *a, **k: None   # DRSI ni dosegljiv brez omrežja\n"
            "sys.exit(w.main())\n")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        r = subprocess.run([sys.executable, "-I", runner], cwd=work, capture_output=True, text=True, env=env, timeout=300)
        check(r.returncode == 0, "winter_engine.main() na sintetični zimi ne pade\n" + r.stderr[-800:])
        p = os.path.join(work, "data", "winter-data.json")
        check(os.path.exists(p), "winter-data.json nastane")
        if not os.path.exists(p):
            return
        D = json.load(open(p, encoding="utf-8"))
        print("  winter-data:", D["generated_at_local"], "meja", D["snow_line"]["current_line_m"], "cm/dan", [d["cm_at_station"] for d in D["snow_line"]["daily"]])

        # ── smer izračunov ──
        sl = D["snow_line"]
        check(sl["daily"][2]["line_m"] is not None and sl["daily"][2]["line_m"] < 700, "meja sneženja na dan fronte pade pod 700 m")
        check(sl["daily"][0]["line_m"] > 2000, "topel dan: meja sneženja visoko")
        check(sl["daily"][2]["cm_at_station"] > 5, "snežni dan: na postaji več kot 5 cm novega snega (%s)" % sl["daily"][2]["cm_at_station"])
        check(sl["daily"][0]["cm_at_station"] == 0, "topel dan brez padavin: 0 cm")
        by = {b["elevation_m"]: b["cm"] for b in sl["expected_cm_by_elevation"]}
        check(all(by[a] <= by[b] + 1e-9 for a, b in zip(sorted(by), sorted(by)[1:])), "več snega više")
        snow48 = D["snowpack"]["by_elevation"]
        check(all(b["new_snow_7d_cm"] >= 0 for b in snow48) and snow48[-1]["new_snow_7d_cm"] > 10, "napoved novega snega 7 dni na 1600 m je pomembna")

        fr = D["freezing_rain"]
        hours = fr.get("hours") or fr.get("hours_48") or []
        days = fr.get("daily") or []
        check(bool(days), "žled: dnevni pregled obstaja")
        lvl = [d.get("level") for d in days]
        check("visoko" in lvl or "srednje" in lvl, "žled: dan s toplo plastjo nad mrazom zazna (%s)" % lvl)
        check(lvl[0] == "nizko", "žled: topel dan je brez žleda")

        bi = D["black_ice_outlook"]["daily"]
        check(len(bi) >= 5, "poledica: sedemdnevni pregled")
        print("  poledica:", [d.get("level") or d.get("risk_level") for d in bi], "keys", sorted(bi[0]))

        check(D["heating_index"]["level"] is not None, "kurilni semafor ima raven")
        peaks = D["mountains"]["peaks"]
        check(len(peaks) == 4, "gore: štirje vrhovi")
        raduha = peaks[-1]
        check(raduha["daily"][2]["snow_cm"] > D["mountains"]["peaks"][0]["daily"][0]["snow_cm"], "gore: sneg na dan fronte")
        check(raduha["now"]["temp_c"] is not None, "gore: temperatura zdaj")
        for pk in peaks:
            for d in pk["daily"]:
                for k, v in d.items():
                    if isinstance(v, float):
                        check(not math.isnan(v), f"gore: {pk['name']} {k} ni NaN")
        for pas in D["passes"]:
            wx = pas["weather"]
            check(wx is not None and wx.get("now") is not None, f"prelaz {pas['id']}: izračun obstaja")

        def no_nan(o, path=""):
            if isinstance(o, float) and math.isnan(o):
                check(False, f"NaN v winter-data.json: {path}")
            elif isinstance(o, dict):
                for k, v in o.items():
                    no_nan(v, path + "/" + k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    no_nan(v, path + f"[{i}]")
        no_nan(D)

        # ── generatorji strani nad sintetičnimi podatki ──
        for gen, outs in (("generate_zima_page.py", ["zima/index.html", "zima/meja-snezenja/index.html", "zima/poledica/index.html",
                                                     "zima/zled/index.html", "zima/snezna-odeja/index.html", "zima/kurilni-semafor/index.html"]),
                          ("generate_gore_page.py", ["vreme-v-gorah/index.html"]),
                          ("generate_snezna_karta_page.py", ["zima/snezna-karta/index.html"])):
            r = subprocess.run([sys.executable, "-I", os.path.join(work, "tools", gen)], cwd=work, capture_output=True, text=True, env=env, timeout=300)
            check(r.returncode == 0, f"{gen} ne pade\n{r.stderr[-600:]}")
            for o in outs:
                f = os.path.join(work, o)
                if not os.path.exists(f):
                    check(False, f"{o} nastane")
                    continue
                html = open(f, encoding="utf-8").read()
                check(len(html) > 3000, f"{o} ni prazna")
                b = bad_text(html)
                check(not b, f"{o} brez None/NaN/undefined v besedilu {b}")
        zima = open(os.path.join(work, "zima/index.html"), encoding="utf-8").read() if os.path.exists(os.path.join(work, "zima/index.html")) else ""
        check("indoor" not in zima.lower(), "zima/: brez notranjih meritev")
        zl = open(os.path.join(work, "zima/zled/index.html"), encoding="utf-8").read() if os.path.exists(os.path.join(work, "zima/zled/index.html")) else ""
        check(bool(re.search(r"(visok|srednj)", zl, re.I)), "stran Žled omeni dvignjeno raven")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nzimski scenarij: {fails} razhajanj")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
