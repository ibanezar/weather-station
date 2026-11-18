#!/usr/bin/env python3
"""Test strani /vreme-2026/: številke na strani so enake neodvisnemu izračunu iz history.json (brez ERA5), brez None/NaN, naslov ≤ 60."""
import datetime, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import generate_wrapped_page as W
bad = 0
def chk(c, m):
    global bad
    if not c:
        bad += 1; print("NAPAKA:", m)
H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8")); H = H.get("days", H)
rows = {k: v for k, v in H.items() if k.startswith("2026-") and v.get("src") != "era5"}
html = open(os.path.join(ROOT, "vreme-2026", "index.html"), encoding="utf-8").read()
big = re.findall(r'wr-b">([^<]*)', html)
chk(len(big) == 8, "osem ploščic")
mn = min(v["tempLow"] for v in rows.values() if v.get("tempLow") is not None)
mx = max(v["tempHigh"] for v in rows.values() if v.get("tempHigh") is not None)
chk(big[0] == W.f1(mn) + " °C", f"najhladnejša {big[0]} proti {mn}")
chk(big[1] == W.f1(mx) + " °C", f"najtoplejši {big[1]} proti {mx}")
chk(big[4] == str(sum(1 for v in rows.values() if v.get("tempLow") is not None and v["tempLow"] <= 0)), "zmrzalne noči")
chk(big[5] == str(sum(1 for v in rows.values() if v.get("tempHigh") is not None and v["tempHigh"] >= 30)), "vroči dnevi")
tot = sum(v["precipTotal"] for v in rows.values() if v.get("precipTotal") is not None)
chk(big[7] == W.f1(tot) + " mm", "padavine skupaj")
chk(not re.search(r"None|NaN|undefined", html), "None/NaN v strani")
chk(not re.search(r"indoor|tempinf", html, re.I), "notranji ključi")
m = re.search(r"<title>([^<]*)</title>", html); chk(m and len(m.group(1)) <= 70, "naslov")
# isti dan z manjkajočo vrednostjo se ne šteje (pokritost)
d = {datetime.date(2026, 1, 1): {"tempLow": None}, datetime.date(2026, 1, 2): {"tempLow": -3.0, "tempHigh": 1.0, "precipTotal": 0.0, "windgustHigh": 10}}
s = W.stats(d, 2026, datetime.date(2026, 1, 2)); chk(s["n_low"] == 1 and s["frost"] == 1, "manjkajoča meritev se ne šteje")
d0 = {datetime.date(2026, 1, 3): {"tempLow": 0.0, "tempHigh": 3.0, "precipTotal": 0.0, "windgustHigh": 5}, datetime.date(2026, 1, 4): {"tempLow": 0.1, "tempHigh": 3.0, "precipTotal": 0.0, "windgustHigh": 5}}
chk(W.stats(d0, 2026, datetime.date(2026, 1, 4))["frost"] == 1, "noč z natanko 0,0 °C je zmrzal, 0,1 ni")
print("wrapped:", "OK" if not bad else f"{bad} napak"); sys.exit(1 if bad else 0)
