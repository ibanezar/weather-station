#!/usr/bin/env python3
"""
tools/gasilec_model.py — požarna ogroženost (Fire Weather Index) za MeteoGasilec.

Ne uvaja novega, na roko uteženega indeksa. Namesto tega v Pythonu ponovi ISTO
kanadsko/EFFIS metodologijo FWI, ki na naslovnici (index.html, kartica
»🔥 Požarna nevarnost – indeks FWI«) že teče v brskalniku
(app.js: _calcOneDayFWI/_fwiClass/fetchFireWeather, ~vrstica 14814 dalje).
Namen te datoteke je narediti isti izračun strežniško, da ga lahko
generate_gasilec_page.py zapiše kot statičen, iskalnikom viden HTML — brez
te podvojitve bi bila stran /meteogasilec/ prazna za vse, ki nimajo JS.

**JS in Python tu namerno računata isto stvar z ločeno kodo** (isto načelo kot
SLO_POLY/buildSloGrid med app.js in generate_storm_map.py) — če spremeniš
formulo ali pragove na eni strani, popravi tudi drugo, sicer se FWI na
naslovnici in na /meteogasilec/ razideta.

Vhodi: Open-Meteo forecast API, isti dnevni parametri in isto okno
(past_days=7, forecast_days=7) kot fetchFireWeather() v app.js — da izračunan
FWI za dani dan na obeh straneh sovpada.

Uporaba:
  python3 tools/gasilec_model.py                 # izpis, zapiše meteogasilec/index.json
  python3 tools/gasilec_model.py --no-write       # samo izpis
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — LAT/LON/ROOT

ROOT = seo.ROOT
LAT, LON = seo.LAT, seo.LON
FREE_JSON_DEFAULT = os.path.join(ROOT, "meteogasilec", "index.json")
MODEL_VERSION = "1.0"

# Le/Lf — dolžina dneva in faktor sušenja po mesecih (januar..december), enaka
# vrstna razporeditev kot v app.js (JS month je 0-indeksiran, tu ga vzamemo
# kot month-1 iz ISO datuma, glej fwi_series()).
_LE = [6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0]
_LF = [-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6]


def calc_one_day_fwi(prev, T, H, W, r, month_idx):
    """Ena dnevna posodobitev kanadskega FWI sistema (FFMC/DMC/DC → ISI/BUI/FWI).
    `prev` je prejšnji dan {ffmc, dmc, dc}; `month_idx` je 0-indeksiran (0=jan).
    Dobesedna preslikava _calcOneDayFWI() iz app.js — glej opombo na vrhu
    datoteke, zakaj sta implementaciji dve."""
    H = max(1.0, min(H, 99.0))
    W = max(0.0, W)
    r = max(0.0, r)
    F0 = prev.get("ffmc", 85.0)
    P0 = prev.get("dmc", 6.0)
    D0 = prev.get("dc", 15.0)

    # FFMC (fine fuel moisture code)
    mo = 147.2 * (101 - F0) / (59.5 + F0)
    mR = mo
    if r > 0.5:
        rf = r - 0.5
        mr = mo + 42.5 * rf * math.exp(-100 / (251 - mo)) * (1 - math.exp(-6.93 / rf))
        if mo > 150:
            mr += 0.0015 * (mo - 150) ** 2 * math.sqrt(rf)
        mR = min(mr, 250)
    Ed = 0.942 * H ** 0.679 + 11 * math.exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - math.exp(-0.115 * H))
    Ew = 0.618 * H ** 0.753 + 10 * math.exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - math.exp(-0.115 * H))
    if mR > Ed:
        kd = 0.424 * (1 - (H / 100) ** 1.7) + 0.0694 * math.sqrt(W) * (1 - (H / 100) ** 8)
        m1 = Ed + (mR - Ed) * math.exp(-2.303 * kd)
    elif mR < Ew:
        kw = 0.424 * (1 - ((100 - H) / 100) ** 1.7) + 0.0694 * math.sqrt(W) * (1 - ((100 - H) / 100) ** 8)
        m1 = Ew - (Ew - mR) * math.exp(-2.303 * kw)
    else:
        m1 = mR
    ffmc = 59.5 * (250 - m1) / (147.2 + m1)

    # DMC (duff moisture code)
    Pr = P0
    if r > 1.5:
        re = 0.92 * r - 1.27
        Mo = 20 + math.exp(5.6348 - P0 / 43.43)
        if P0 <= 33:
            b = 100 / (0.5 + 0.3 * P0)
        elif P0 <= 65:
            b = 14 - 1.3 * math.log(P0)
        else:
            b = 6.2 * math.log(P0) - 17.2
        Mr = Mo + 1000 * re / (48.77 + b * re)
        Pr = max(244.72 - 43.43 * math.log(Mr - 20), 0)
    Le = _LE[month_idx]
    K = 1.894 * (T + 1.1) * (100 - H) * Le * 1e-6
    dmc = max(Pr + 100 * K, 0)

    # DC (drought code)
    Dr = D0
    if r > 2.8:
        rd = 0.83 * r - 1.27
        Qo = 800 * math.exp(-D0 / 400)
        Qr = Qo + 3.937 * rd
        Dr = max(400 * math.log(800 / Qr), 0)
    Lf = _LF[month_idx]
    dc = max(Dr + max(0, 0.36 * (T + 2.8) + Lf) / 2, 0)

    # ISI (initial spread index)
    fW = math.exp(0.05039 * W)
    mF = 147.2 * (101 - ffmc) / (59.5 + ffmc)
    fF = 91.9 * math.exp(-0.1386 * mF) * (1 + mF ** 5.31 / 4.93e7)
    isi = 0.208 * fW * fF

    # BUI (buildup index)
    if dmc <= 0.4 * dc:
        bui = 0.8 * dmc * dc / (dmc + 0.4 * dc)
    else:
        bui = dmc - (1 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)

    # FWI (fire weather index)
    if bui <= 80:
        fD = 0.626 * max(bui, 0) ** 0.809 + 2
    else:
        fD = 1000 / (25 + 108.64 * math.exp(-0.023 * bui))
    B = 0.1 * isi * fD
    fwi = math.exp(2.72 * (0.434 * math.log(B)) ** 0.647) if B > 1 else B

    return {"ffmc": ffmc, "dmc": dmc, "dc": dc, "isi": isi, "bui": bui, "fwi": max(0.0, fwi)}


# Ena resnica za pragove/barve/oznake FWI stopenj — uporabljata jo fwi_class()
# (razvrščanje) in generate_gasilec_page.py (legenda). Isti pragovi kot
# _fwiClass() v app.js — glej opombo na vrhu datoteke. Zgornja meja je None za
# zadnjo (odprto navzgor) stopnjo.
FWI_LEVELS = [
    ("Nizka", "#22c55e", 0, 5.2),
    ("Zmerna", "#84cc16", 5.2, 11.2),
    ("Visoka", "#f59e0b", 11.2, 21.3),
    ("Zelo visoka", "#ef4444", 21.3, 38.0),
    ("Ekstremna", "#7c3aed", 38.0, None),
]


def fwi_class(v):
    for label, color, lo, hi in FWI_LEVELS:
        if hi is None or v < hi:
            return label, color
    return FWI_LEVELS[-1][0], FWI_LEVELS[-1][1]


def fetch_daily(lat=LAT, lon=LON, past_days=7, forecast_days=7):
    """Isti klic kot fetchFireWeather() v app.js: dnevni Tmax, RHmin, veter,
    padavine za past_days nazaj + forecast_days naprej."""
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,relative_humidity_2m_min,windspeed_10m_max,precipitation_sum",
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "Europe/Ljubljana",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fwi_series(daily):
    """Zaporedni dnevni FWI za ves fetch_daily() razpon — vsak dan gradi na
    vlažnostnih kodah prejšnjega (glej prev v _calcOneDayFWI)."""
    dates = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    rhmin = daily.get("relative_humidity_2m_min") or []
    wind = daily.get("windspeed_10m_max") or []
    precip = daily.get("precipitation_sum") or []

    prev = {"ffmc": 85.0, "dmc": 6.0, "dc": 15.0}
    days = []
    for i, date in enumerate(dates):
        T = tmax[i] if i < len(tmax) and tmax[i] is not None else 20.0
        H = rhmin[i] if i < len(rhmin) and rhmin[i] is not None else 50.0
        W = wind[i] if i < len(wind) and wind[i] is not None else 0.0
        r = precip[i] if i < len(precip) and precip[i] is not None else 0.0
        month_idx = dt.date.fromisoformat(date).month - 1
        res = calc_one_day_fwi(prev, T, H, W, r, month_idx)
        prev = res
        label, color = fwi_class(res["fwi"])
        days.append({
            "date": date, "fwi": round(res["fwi"], 1), "isi": round(res["isi"], 1),
            "bui": round(res["bui"]), "ffmc": round(res["ffmc"]),
            "dmc": round(res["dmc"]), "dc": round(res["dc"]),
            "level": label, "color": color,
        })
    return days


def free_payload(days):
    today_iso = dt.date.today().isoformat()
    today = next((d for d in days if d["date"] == today_iso), days[len(days) // 2] if days else None)
    return {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "model_version": MODEL_VERSION,
        "date": today["date"] if today else today_iso,
        "fwi": today["fwi"] if today else None,
        "level": today["level"] if today else None,
        "days": days,
    }


def main():
    ap = argparse.ArgumentParser(description="FWI požarna ogroženost za /meteogasilec/")
    ap.add_argument("--out-free", default=FREE_JSON_DEFAULT)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    print("Pridobivam Open-Meteo dnevno napoved (FWI vhodi) …")
    try:
        data = fetch_daily()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Open-Meteo: {e}", file=sys.stderr)
        sys.exit(1)

    days = fwi_series(data.get("daily") or {})
    if not days:
        print("✗ Open-Meteo ni vrnil dnevnih podatkov", file=sys.stderr)
        sys.exit(1)

    payload = free_payload(days)
    print(f"\n=== FWI požarna ogroženost — Rečica ob Savinji ===")
    for d in days:
        print(f"  {d['date']}  FWI {d['fwi']:5.1f}  ({d['level']})")
    print(f"\nDanes: {payload['fwi']} ({payload['level']})")

    if not args.no_write:
        os.makedirs(os.path.dirname(args.out_free), exist_ok=True)
        with open(args.out_free, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"→ {args.out_free}")


if __name__ == "__main__":
    main()
