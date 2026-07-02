#!/usr/bin/env python3
"""
tools/prerender_wave1.py — Pre-render live data into the three Wave 1 SEO
spoke pages (gobarska-napoved/, vodostaj-savinje/, cvetni-prah/).

Each page's homepage widget already fetches this data client-side (see
app.js: initGobe/_gobeScore, fetchSavinjaRiver, fetchPollen). Search engines
never see those values because they arrive after JS runs. This script
fetches the same public APIs used by the client widgets and injects a
static, crawlable summary between marker comments in each page, exactly
like tools/inject_current_weather.py does for the homepage hero.

Wired into: .github/workflows/prerender-wave1.yml (every 3h + manual)

Usage:
  python3 tools/prerender_wave1.py
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
LAT, LON = 46.325779, 14.921137

GOBE_SPOTS = [
    {"name": "Rečica ob Savinji", "lat": 46.326, "lon": 14.921, "elev": "≈400 m"},
    {"name": "Dobrovlje – Čreta", "lat": 46.300, "lon": 14.860, "elev": "≈900 m"},
    {"name": "Logarska dolina", "lat": 46.392, "lon": 14.628, "elev": "≈750 m"},
    {"name": "Golte", "lat": 46.348, "lon": 14.840, "elev": "≈1300 m"},
    {"name": "Smrekovško pogorje", "lat": 46.430, "lon": 14.860, "elev": "≈1300 m"},
]

POLLEN_TYPES = [
    {"key": "alder_pollen", "icon": "🌳", "name": "Jelša", "low": 5, "mod": 25, "high": 50},
    {"key": "birch_pollen", "icon": "🌲", "name": "Breza", "low": 5, "mod": 25, "high": 90},
    {"key": "grass_pollen", "icon": "🌾", "name": "Trave", "low": 5, "mod": 20, "high": 50},
    {"key": "mugwort_pollen", "icon": "🌿", "name": "Pelin", "low": 5, "mod": 15, "high": 50},
    {"key": "ragweed_pollen", "icon": "🪴", "name": "Ambrozija", "low": 5, "mod": 15, "high": 50},
]

RIVER_THRESHOLDS = {"normal": 30, "raised": 80, "warning": 200, "alarm": 400}

MES_GEN = {1: "januarja", 2: "februarja", 3: "marca", 4: "aprila", 5: "maja",
           6: "junija", 7: "julija", 8: "avgusta", 9: "septembra", 10: "oktobra",
           11: "novembra", 12: "decembra"}


def fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (meteorec.si prerender)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def now_local_str():
    dt = datetime.now()
    return f"{dt.day}. {MES_GEN[dt.month]} {dt.year} ob {dt.strftime('%H:%M')}"


def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def replace_block(path, start, end, block):
    html = open(path, encoding="utf-8").read()
    if start not in html or end not in html:
        print(f"ERROR: markers not found in {path}", file=sys.stderr)
        return False
    wrapped = f"{start}\n{block}\n    {end}"
    new = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: wrapped, html, flags=re.S)
    if new != html:
        open(path, "w", encoding="utf-8").write(new)
        print(f"{path}: posodobljeno.")
    else:
        print(f"{path}: brez sprememb.")
    return True


# ═══ 1. Gobarski indeks ════════════════════════════════════════════════
def gobe_score(ar, sm, st, rh, tmean):
    s = 0
    if ar >= 60: s += 34
    elif ar >= 35: s += 27
    elif ar >= 20: s += 18
    elif ar >= 10: s += 9
    elif ar >= 4: s += 3
    if sm is not None:
        if sm >= 0.32: s += 24
        elif sm >= 0.26: s += 18
        elif sm >= 0.20: s += 11
        elif sm >= 0.15: s += 4
    if st is not None:
        if 10 <= st <= 18: s += 18
        elif (7 <= st < 10) or (18 < st <= 21): s += 10
        elif 4 <= st <= 24: s += 4
    if rh is not None:
        if rh >= 85: s += 12
        elif rh >= 75: s += 8
        elif rh >= 65: s += 4
    if tmean is not None:
        if tmean < 2: s -= 22
        elif tmean < 5: s -= 8
        elif tmean > 26: s -= 10
    return max(0, min(100, round(s)))


def gobe_level(pct):
    if pct >= 75: return "ODLIČNA", "suit-excellent"
    if pct >= 55: return "DOBRA", "suit-good"
    if pct >= 35: return "ZMERNA", "suit-fair"
    if pct >= 18: return "SLABA", "suit-poor"
    return "BREZ", "suit-bad"


def build_gobe():
    lats = ",".join(str(s["lat"]) for s in GOBE_SPOTS)
    lons = ",".join(str(s["lon"]) for s in GOBE_SPOTS)
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
           "&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
           "&hourly=soil_moisture_3_to_9cm,soil_temperature_6cm,relative_humidity_2m"
           "&past_days=14&forecast_days=1&timezone=Europe%2FLjubljana")
    data = fetch_json(url)
    locs = data if isinstance(data, list) else [data]

    rows = []
    for spot, loc in zip(GOBE_SPOTS, locs):
        daily = loc.get("daily", {})
        hourly = loc.get("hourly", {})
        times = daily.get("time", [])
        today = times[-1] if times else None
        i = len(times) - 1
        rain = daily.get("precipitation_sum", [])
        ar = sum((rain[k] or 0) for k in range(max(0, i - 12), i - 3) if 0 <= k < len(rain))
        tmax = daily.get("temperature_2m_max", [None] * len(times))[i] if times else None
        tmin = daily.get("temperature_2m_min", [None] * len(times))[i] if times else None
        tmean = ((tmax + tmin) / 2) if (tmax is not None and tmin is not None) else (tmax if tmax is not None else tmin)

        hd = hourly.get("time", [])
        sm_sum = sm_n = st_sum = st_n = rh_sum = rh_n = 0
        for k, t in enumerate(hd):
            if today and t[:10] != today:
                continue
            sm = hourly.get("soil_moisture_3_to_9cm", [None] * len(hd))[k]
            st = hourly.get("soil_temperature_6cm", [None] * len(hd))[k]
            rh = hourly.get("relative_humidity_2m", [None] * len(hd))[k]
            if sm is not None: sm_sum += sm; sm_n += 1
            if st is not None: st_sum += st; st_n += 1
            if rh is not None: rh_sum += rh; rh_n += 1
        sm = sm_sum / sm_n if sm_n else None
        st = st_sum / st_n if st_n else None
        rh = rh_sum / rh_n if rh_n else None

        pct = gobe_score(ar, sm, st, rh, tmean)
        lvl, cls = gobe_level(pct)
        rows.append({"name": spot["name"], "elev": spot["elev"], "pct": pct, "lvl": lvl, "cls": cls})

    best = max(rows, key=lambda r: r["pct"])
    rows_sorted = sorted(rows, key=lambda r: -r["pct"])

    table_rows = "\n".join(
        f'    <tr><td>{r["name"]}</td><td class="muted">{r["elev"]}</td>'
        f'<td><span class="gobe-pct {r["cls"]}">{r["pct"]} %</span></td><td>{r["lvl"]}</td></tr>'
        for r in rows_sorted
    )
    best_lvl_txt = {"suit-excellent": "odlične", "suit-good": "dobre", "suit-fair": "zmerne",
                    "suit-poor": "slabe", "suit-bad": "ničelne"}[best["cls"]]

    text = (f'Trenutno najboljše razmere za nabiranje gob v Zgornji Savinjski dolini so na lokaciji '
            f'<strong>{best["name"]}</strong> ({best["elev"]}) — gobarski indeks {best["pct"]} % '
            f'({best_lvl_txt}). Ocena temelji na vlagi in temperaturi tal ter sprožilnem dežju zadnjih '
            f'5–12 dni na 5 lokacijah po dolini.')

    block = (f'<p class="hub-intro">{text} Podatki posodobljeni {now_local_str()}.</p>\n'
             '    <table class="hub-table">\n'
             '      <thead><tr><th>Lokacija</th><th>Nadm. višina</th><th>Indeks</th><th>Ocena</th></tr></thead>\n'
             '      <tbody>\n' + table_rows + '\n      </tbody>\n    </table>')
    return block


# ═══ 2. Vodostaj Savinje ════════════════════════════════════════════════
def river_status(q):
    t = RIVER_THRESHOLDS
    if q is None:
        return "—", "muted"
    if q >= t["alarm"]:
        return "ALARM — poplavna nevarnost", "alarm"
    if q >= t["warning"]:
        return "Opozorilo — zvišan pretok", "hot"
    if q >= t["raised"]:
        return "Povečan pretok", "rain"
    return "Normalen pretok", ""


def build_vodostaj():
    stations_txt = None
    try:
        wdata = fetch_json(f"{PROXY}/arso-water")
        stations = wdata.get("stations", [])
    except Exception as e:
        print(f"arso-water ni dosegljiv ({e})", file=sys.stderr)
        stations = []

    savinja = [s for s in stations if "savinj" in (s.get("properties", {}).get("reka") or "").lower()]
    savinja = savinja or stations

    todayQ = None
    try:
        fdata = fetch_json(
            f"https://flood-api.open-meteo.com/v1/flood?latitude={LAT}&longitude={LON}"
            "&daily=river_discharge&forecast_days=1&past_days=0")
        flows = fdata.get("daily", {}).get("river_discharge", [])
        todayQ = flows[0] if flows else None
    except Exception as e:
        print(f"flood-api ni dosegljiv ({e})", file=sys.stderr)

    status_txt, status_cls = river_status(todayQ)

    rows = []
    for s in savinja[:6]:
        p = s.get("properties", {})
        vod = p.get("vodostaj")
        rows.append(
            f'    <tr><td>{p.get("postaja") or p.get("merilno_mesto") or "—"}</td>'
            f'<td>{round(vod) if vod is not None else "—"} cm</td>'
            f'<td>{num(p.get("pretok"), 2)} m³/s</td>'
            f'<td>{num(p.get("temperatura"), 1)} °C</td>'
            f'<td class="muted">{p.get("datum") or "—"}</td></tr>'
        )
    table_rows = "\n".join(rows) if rows else '    <tr><td colspan="5" class="muted">Podatki trenutno niso dosegljivi.</td></tr>'

    q_txt = f'{todayQ:.1f} m³/s'.replace(".", ",") if todayQ is not None else "—"
    text = (f'Modelirani pretok Savinje pri Rečici ob Savinji je danes <strong>{q_txt}</strong> '
            f'(GloFAS) — <span class="{status_cls}">{status_txt.lower()}</span>. '
            f'Spodaj so zadnje meritve uradnih ARSO vodomernih postaj vzdolž Savinje.')

    block = (f'<div class="event-hero"><div class="ev-label">Stanje danes</div>'
             f'<div class="ev-value {status_cls}">{q_txt}</div>'
             f'<div class="ev-date">{status_txt} · GloFAS napoved pri Rečici ob Savinji</div></div>\n'
             f'    <p class="hub-intro">{text} Podatki posodobljeni {now_local_str()}.</p>\n'
             '    <table class="hub-table">\n'
             '      <thead><tr><th>Postaja</th><th>Vodostaj</th><th>Pretok</th><th>Temp. vode</th><th>Meritev</th></tr></thead>\n'
             '      <tbody>\n' + table_rows + '\n      </tbody>\n    </table>')
    return block


# ═══ 3. Cvetni prah ═════════════════════════════════════════════════════
def pollen_level(val, p):
    if val < p["low"]: return "nizko", "pollen-low"
    if val < p["mod"]: return "zmerno", "pollen-mod"
    if val < p["high"]: return "visoko", "pollen-high"
    return "zelo viš.", "pollen-extreme"


def build_pollen():
    keys = ",".join(p["key"] for p in POLLEN_TYPES)
    url = (f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}"
           f"&hourly={keys}&timezone=Europe%2FLjubljana&forecast_days=1")
    data = fetch_json(url)
    hourly = data.get("hourly", {})
    hour_now = datetime.now().hour
    items = []
    for p in POLLEN_TYPES:
        arr = hourly.get(p["key"], [])
        val = arr[hour_now] if hour_now < len(arr) else None
        if val is None:
            val = next((v for v in arr if v is not None), None)
        if val is None:
            continue
        lvl, cls = pollen_level(val, p)
        items.append({**p, "val": val, "lvl": lvl, "cls": cls})

    if not items:
        block = '<p class="hub-intro">Trenutno ni zaznanega peloda (izven sezone). Podatki: Open-Meteo CAMS Europe.</p>'
        return block

    worst = max(items, key=lambda x: x["val"])
    text = (f'Trenutno je v Zgornji Savinjski dolini najbolj zastopan pelod <strong>{worst["name"]}</strong> '
            f'({worst["lvl"]}, {round(worst["val"])} zrn/m³). Vrednosti spodaj se posodabljajo iz Open-Meteo CAMS Europe.')

    grid = "\n".join(
        f'      <div class="pollen-item"><div class="pollen-icon">{p["icon"]}</div>'
        f'<div class="pollen-name">{p["name"]}</div>'
        f'<div class="pollen-val">{round(p["val"])}</div>'
        f'<div class="pollen-level {p["cls"]}">{p["lvl"]}</div></div>'
        for p in items
    )

    block = (f'<p class="hub-intro">{text} Podatki posodobljeni {now_local_str()}.</p>\n'
             f'    <div class="pollen-grid">\n{grid}\n    </div>')
    return block


def main():
    ok = True
    ok &= replace_block(
        os.path.join(ROOT, "gobarska-napoved", "index.html"),
        "<!-- WAVE1:GOBE:START -->", "<!-- WAVE1:GOBE:END -->", build_gobe())
    ok &= replace_block(
        os.path.join(ROOT, "vodostaj-savinje", "index.html"),
        "<!-- WAVE1:VODOSTAJ:START -->", "<!-- WAVE1:VODOSTAJ:END -->", build_vodostaj())
    ok &= replace_block(
        os.path.join(ROOT, "cvetni-prah", "index.html"),
        "<!-- WAVE1:POLLEN:START -->", "<!-- WAVE1:POLLEN:END -->", build_pollen())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
