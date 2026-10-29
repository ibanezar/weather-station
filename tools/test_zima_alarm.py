#!/usr/bin/env python3
"""Test zimskih opozoril na telefon (generate_zima_page.py: zima_ocene, write_zima_ocene, with_alert).
Pragovi ravni, razlogi, usklajenost možnosti obrazca z ravnmi, vstavitev gradnika, veljaven JS, brez notranjih meritev. Brez omrežja."""
import json, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_zima_page as Z  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# ── raven snega in megle ──
check("sneg: pod 0,2 cm = brez snega", Z.sneg_level(0.0) == 0 and Z.sneg_level(0.19) == 0)
check("sneg: mejne vrednosti 0,2 / 1 / 5 cm", [Z.sneg_level(x) for x in (0.2, 0.99, 1.0, 4.9, 5.0, 30)] == [1, 1, 2, 2, 3, 3])
check("sneg: brez podatka = None", Z.sneg_level(None) is None)
check("megla: brez inverzije je 0, tudi če je top_m podan", Z.megla_level(800, False) == 0 and Z.megla_level(None, True) == 0)
check("megla: mejne vrednosti 500 / 900 m", [Z.megla_level(x, True) for x in (400, 499, 500, 899, 900, 1300)] == [1, 1, 2, 2, 3, 3])

# ── ocene iz sintetičnih podatkov ──
data = {
    "black_ice_outlook": {"daily": [{"date": "2026-12-01", "level": "nizko"}, {"date": "2026-12-02", "level": "visoko"}]},
    "freezing_rain": {"daily": [{"date": "2026-12-01", "level": "nizko"}, {"date": "2026-12-02", "level": "srednje"}]},
    "snow_line": {"daily": [{"date": "2026-12-01", "line_m": 1800, "cm_at_station": 0.0},
                             {"date": "2026-12-02", "line_m": 350, "cm_at_station": 3.46},
                             {"date": "2026-12-03", "line_m": 900, "cm_at_station": None}]},
    "fog": {"locations": [{"name": "Rečica ob Savinji", "elevation_m": 366}, {"name": "Solčava", "elevation_m": 644},
                          {"name": "Golte", "elevation_m": 1400}, {"name": "Raduha", "elevation_m": 2062}, {"name": "Smrekovec", "elevation_m": 1577}],
            "daily": [{"date": "2026-12-01", "has_inversion": False, "top_m": None},
                      {"date": "2026-12-02", "has_inversion": True, "top_m": 862},
                      {"date": "2026-12-03", "has_inversion": True, "top_m": 1500}]},
}
o = Z.zima_ocene(data)
check("ocene: poledica in žled po vrstnem redu ravni", [d["lvl"] for d in o["zima-poledica"]] == [0, 2] and [d["lvl"] for d in o["zima-zled"]] == [0, 1])
check("ocene: dan brez podatka o snegu se izpusti", [d["date"] for d in o["zima-sneg"]] == ["2026-12-01", "2026-12-02"])
check("sneg: razlog ima količino in mejo, brez snega ga ni",
      o["zima-sneg"][0]["reasons"] == [] and o["zima-sneg"][1]["reasons"] == ["v dolini po oceni 3,5 cm novega snega", "meja sneženja do 350 m"])
m = o["zima-megla"]
check("megla: raven po meji, razlog našteje samo vrhove nad njo", [d["lvl"] for d in m] == [0, 2, 3]
      and m[1]["reasons"] == ["megla do približno 862 m", "nad njo: Golte, Raduha in Smrekovec"] and m[2]["reasons"] == ["megla do približno 1500 m", "nad njo: Raduha in Smrekovec"])
check("megla: Solčava (644 m) ni med vrhovi", all("Solčava" not in r for d in m for r in d["reasons"]))
check("prazni podatki ne podrejo ocen", all(v == [] for v in Z.zima_ocene({}).values()))

# ── usklajenost možnosti obrazca z ravnmi ──
for slug, c in Z.ZIMA_ALERTS.items():
    vals = [v for v, _ in c["opts"]]
    lv = [int(v[2:]) for v in vals]
    check(f"{slug}: možnosti so ge/le z veljavno ravnjo (< število ravni, ≤ 3)", all(v[:2] in ("ge", "le") for v in vals) and all(0 <= x < len(c["levels"]) and x <= 3 for x in lv))
    check(f"{slug}: največ 4 ravni, naslov in povezava na zimsko stran", len(c["levels"]) <= 4 and c["url"].startswith("/zima/") and bool(c["short"]))

# ── zapis datoteke, ki jo bere worker ──
with tempfile.TemporaryDirectory() as td:
    pth = os.path.join(td, "zima-ocene.json")
    with open(pth, "w") as f:
        f.write('{"generated":"2020-01-01T00:00:00Z","pages":{"stara-stran":{"days":[]}}}')
    n = Z.write_zima_ocene(data, path=pth)
    j = json.load(open(pth, encoding="utf-8"))
    check("zapis: štiri strani, ostanek stare datoteke pobrisan", n == 4 and set(j["pages"]) == set(Z.ZIMA_ALERTS))
    check("zapis: čas UTC in oblika kot v vsakdan-ocene.json", j["generated"].endswith("Z") and all(set(p) == {"naslov", "url", "levels", "days"} for p in j["pages"].values()))
    check("zapis: ravni so indeksi, ne besedila", all(isinstance(d["lvl"], int) for p in j["pages"].values() for d in p["days"]))
    Z.write_zima_ocene({}, path=pth)
    check("zapis: brez podatkov datoteke ni (ne ostane zastarela)", not os.path.exists(pth))

# ── gradnik na straneh ──
wsrc = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker.js"), encoding="utf-8").read()
check("worker bere zimsko datoteko ocen", "https://meteorec.si/data/zima-ocene.json" in wsrc)
body = Z.with_alert('<h1>x</h1>\n  <a class="back-link" href="/zima/">← Nazaj</a>', "zima-poledica")
check("gradnik stoji pred povezavo »Nazaj«", body.index('id="ov-alert"') < body.index('class="back-link"') and "site:'ocene'" in body and "Poledica" in body)
check("gradnik: brez povezave »Nazaj« telo ostane nespremenjeno", Z.with_alert("<p>x</p>", "zima-sneg") == "<p>x</p>")
m2 = re.search(r"<script>\n(\(function\(\)\{.*?)</script>", body, re.S)
ok = False
if m2:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(m2.group(1))
    ok = subprocess.run(["node", "--check", f.name], capture_output=True).returncode == 0
    os.unlink(f.name)
check("skript opozorila je veljaven JS, slug se prenese", ok and 'var SLUG="zima-poledica"' in m2.group(1))
hub = Z.hub_alerts_html()
check("hub: povezave na vse štiri strani s sidrom na gradnik", all(f'href="{c["url"]}#ov-alert"' in hub for c in Z.ZIMA_ALERTS.values()))

# ── generirane strani (če so v repozitoriju) ──
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for slug, c in Z.ZIMA_ALERTS.items():
    pth = os.path.join(root, c["url"].strip("/"), "index.html")
    if os.path.exists(pth):
        h = open(pth, encoding="utf-8").read()
        check(f"{c['url']}: ima gradnik za {slug}", f'var SLUG="{slug}"' in h and 'id="ov-alert"' in h)
        check(f"{c['url']}: brez notranjih meritev", not re.search(r"\bindoor\b|tempinf", h))

sys.exit(1 if fails else 0)
