#!/usr/bin/env python3
"""tools/test_first_snow.py — prva snežna odeja sezone (seo_smart_routine.detect_first_snow).

Postaja IREICA1 snega ne meri; vir je višina odeje ARSO za Gornji Grad. Test zaklene:
prag 1 cm, lokalni datum (ne UTC), okno iskanja, luknjo med arhivom in živimi odčitki
(stran ne sme trditi več, kot ve), da brez zapisa o pokritosti arhiva ni dogodka in da stran
ne pripiše meritve naši postaji. Zaženi: python3 tools/test_first_snow.py
"""
import csv
import datetime
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_smart_routine as m  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


TODAY = datetime.date(2026, 11, 14)
tmp = tempfile.mkdtemp()
HEAD = ["valid_utc", "id", "name", "alt_m", "lat", "lon", "t", "snow_cm", "rr_mm", "tp_12h_mm"]


def live_row(utc, sid, name, alt, snow):
    return [utc, sid, name, alt, "46.3", "14.8", "1.0", snow, "0.0", "0.0"]


def run(rows, archive_days=None, meta_last="2026-10-31", lookback=30):
    p_live = os.path.join(tmp, "live.csv")
    with open(p_live, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    p_arch = os.path.join(tmp, "arch.json")
    json.dump({"fields": ["date", "snow_depth_cm", "new_snow_cm", "precip_mm"],
               "days": archive_days or [["2026-10-30", 0.0, 0.0, 0.0], ["2026-10-31", 0.0, 0.0, 0.0]]},
              open(p_arch, "w"))
    p_meta = os.path.join(tmp, "meta.json")
    if meta_last is not None:
        json.dump({"last_value_date": {"1748": meta_last}}, open(p_meta, "w"))
    elif os.path.exists(p_meta):
        os.remove(p_meta)
    return m.detect_first_snow(lookback_days=lookback, live_csv=p_live, archive=p_arch, meta=p_meta, today=TODAY)


GG = ("GORNJ-GRA_", "Gornji Grad", "428.0")
RAD = ("RADEG-NDA_", "Radegunda", "794.0")

# brez snega
check(run([live_row("2026-11-12T06:10Z", *GG, "0.0")]) == [], "brez snega ni dogodka")
check(run([live_row("2026-11-12T06:10Z", *GG, "0.5")]) == [], "pod pragom 1 cm ni dogodka")
check(run([]) == [], "prazen dnevnik ni napaka")

# sneg v živem viru
ev = run([live_row("2026-11-12T06:10Z", *GG, "0.0"), live_row("2026-11-13T06:10Z", *GG, "2.0")])
check(len(ev) == 1, "sneg ≥ 1 cm se zazna")
e = ev[0] if ev else {}
check(e.get("slug") == "prvi-sneg-2026", "slug nosi začetek sezone")
check(e.get("date") == "2026-11-13" and e.get("value") == 2.0, "datum in višina")
check(e.get("source") == "odčitek" and e.get("clock") == "ob 7.10", "čas po lokalnem času (7.10, ne 6.10 UTC)")
check(e.get("gap") == ["2026-11-01", "2026-11-11"], "luknja: od konca arhiva do prvega odčitka")

# lokalni datum: 23.30 UTC je že naslednji dan po naši uri
ev = run([live_row("2026-11-12T06:10Z", *GG, "0.0"), live_row("2026-11-13T23:30Z", *GG, "3.0")])
check(ev and ev[0]["date"] == "2026-11-14", "datum je lokalni, ne UTC")

# brez luknje, če arhiv sega do prvega odčitka
ev = run([live_row("2026-11-09T06:10Z", *GG, "1.0")], meta_last="2026-11-08")
check(ev and ev[0]["gap"] is None, "brez luknje, ko se arhiv in odčitki stikata")

# brez zapisa o pokritosti arhiva ne trdimo ničesar
check(run([live_row("2026-11-13T06:10Z", *GG, "2.0")], meta_last=None) == [],
      "brez zapisa o pokritosti arhiva ni dogodka")

# arhiv ima sneg prej
arch = [["2026-10-30", 0.0, 0.0, 0.0], ["2026-10-31", 3.0, 3.0, 4.0]]
ev = run([live_row("2026-11-13T06:10Z", *GG, "2.0")], archive_days=arch)
check(ev and ev[0]["source"] == "arhiv" and ev[0]["date"] == "2026-10-31" and ev[0]["gap"] is None,
      "prvi sneg iz arhiva ima prednost in nima luknje")
# …a ne zunaj okna iskanja
check(run([], archive_days=arch, lookback=7) == [], "izven okna iskanja se ne zazna")
# sneg pred 1. oktobrom ne šteje
old = [["2026-09-20", 5.0, 5.0, 1.0], ["2026-10-31", 0.0, 0.0, 0.0]]
check(run([], archive_days=old) == [], "pred 1. oktobrom ne šteje")

# druge postaje istega dne
ev = run([live_row("2026-11-13T06:10Z", *GG, "2.0"), live_row("2026-11-13T06:10Z", *RAD, "6.0"),
          live_row("2026-11-13T06:10Z", "X_", "Brez višine", "", "4.0"),
          live_row("2026-11-12T06:10Z", "Y_", "Včeraj", "500.0", "9.0")])
check(ev and [o["name"] for o in ev[0]["others"]] == ["Radegunda"],
      "druge postaje: samo isti dan, samo z višino, brez glavne")

# izris strani
pages = []
m.write_page = lambda rel, html, force=False: pages.append((rel, html)) or True
ev = run([live_row("2026-11-12T06:10Z", *GG, "0.0"), live_row("2026-11-13T06:10Z", *GG, "2.0"),
          live_row("2026-11-13T06:10Z", *RAD, "6.0")])[0]
m.gen_event_page(ev, {}, [], force=True)
html = pages[-1][1] if pages else ""
tm = re.search(r"<title>([^<]*)</title>", html)
dm = re.search(r'<meta name="description" content="([^"]*)"', html)
check(bool(tm) and len(tm.group(1)) <= 70, f"naslov ni predolg ({len(tm.group(1)) if tm else '?'})")
check(bool(dm) and len(dm.group(1)) <= 160, f"opis ≤ 160 znakov ({len(dm.group(1)) if dm else '?'})")
check("Vir: Agencija Republike Slovenije za okolje" in html, "navedba vira ARSO")
check("snega ne meri" in html, "stran pove, da IREICA1 snega ne meri")
check("ARSO · GORNJI GRAD" in html and "IREICA1 · REČICA" not in html, "hero ne pripiše meritve naši postaji")
check("Luknja v podatkih" in html and "1. novembra 2026" in html and "11. novembra 2026" in html,
      "luknja je izpisana z datumi")
check("glej luknjo spodaj" in html and "podatkih sezone" in (dm.group(1) if dm else ""),
      "z luknjo stran ne trdi brezpogojno, da je sneg prvi")
check("Radegunda (794 m)" in html and "6 cm" in html, "tabela vsebuje druge postaje")
check("indoor" not in html.lower() and "notranj" not in html.lower(), "brez notranjih meritev")
check("2,0" not in html and "2 cm" in html, "cela višina brez decimalke")

# kartica v indeksu
pages.clear()
m.gen_novosti_index([ev], [])
idx = next((h for r, h in pages if r == "novosti/index.html"), "")
check("Prva snežna odeja sezone — 2 cm" in idx and "ARSO · Gornji Grad" in idx and "IREICA1" not in idx.split("novosti-card", 1)[-1].split("</a>")[0],
      "kartica v /novosti/ ima enoto cm in vir ARSO")

if fails:
    print(f"\n✗ {fails} preverjanj ni uspelo")
    sys.exit(1)
print("✓ vsa preverjanja uspešna")
