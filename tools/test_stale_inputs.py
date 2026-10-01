#!/usr/bin/env python3
"""tools/test_stale_inputs.py — potrošniki datotek, ki jih piše DRUG workflow, ne smejo
tiho uporabiti včerajšnje datoteke kot današnje.

GitHubov cron zdaj zamuja 5-7 ur in vsak workflow po svoje, zato vrstni red »A ob 01:35,
B ob 05:00« ne drži. Revizija 1. 10. 2026 je našla štiri potrošnike, ki so zaupali
vrstnemu redu: (1) gasilska stran je en mesec kot »danes« kazala nevihtno karto z
31. 8.; (2) jutranji povzetek je imenoval `lead == 1` (jutri) »danes«; (3) članek in
(4) kartica zgodbe sta isto vzela za »jutri«, ko je bila datoteka včerajšnja.
Zaženi:  python3 tools/test_stale_inputs.py
"""
import datetime
import json
import os
import sys
import tempfile
import urllib.error
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CHECKS, FAILS = 0, []


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


TODAY = datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).date()
D = lambda n: (TODAY + datetime.timedelta(days=n)).isoformat()  # noqa: E731


def mos_file(generated_offset):
    """napoved-modela.json, nastal `generated_offset` dni od danes (−1 = včeraj):
    lead 1..3 so dnevi nastanka +1..+3."""
    return {"generated_at": f"{D(generated_offset)}T01:35:00Z", "model_version": "1.0",
            "days": [{"lead": k, "date": D(generated_offset + k), "tmax": 10.0 + k, "tmin": k, "pop": 0.1 * k}
                     for k in (1, 2, 3)]}


def write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


tmp = tempfile.mkdtemp()

print("zgodba: load_mtr_forecast")
import generate_story_card as sc  # noqa: E402
sc.MTR_JSON = os.path.join(tmp, "napoved-modela.json")
write(sc.MTR_JSON, mos_file(0))
r = sc.load_mtr_forecast(D(1))
check(r and r["date"] == D(1) and r["lead"] == 1, "svež file: jutri = lead 1", str(r))
write(sc.MTR_JSON, mos_file(-1))
r = sc.load_mtr_forecast(D(1))
check(r and r["date"] == D(1), "včerajšnji file: jutri je lead 2, ne lead 1 (ki bi bil danes)", str(r))
write(sc.MTR_JSON, mos_file(-5))
check(sc.load_mtr_forecast(D(1)) is None, "pet dni star file: jutrišnjega dne ni — nič")

print("članek: fetch_mtr_forecast")
import generate_daily_post as dp  # noqa: E402
dp.ROOT = tmp
write(os.path.join(tmp, "napoved-modela.json"), mos_file(0))
r = dp.fetch_mtr_forecast()
check(r and r["tmax"] == 11.0, "svež file: jutrišnja napoved", str(r))
write(os.path.join(tmp, "napoved-modela.json"), mos_file(-1))
r = dp.fetch_mtr_forecast()
check(r and r["tmax"] == 12.0, "včerajšnji file: dan z jutrišnjim datumom (lead 2), ne lead 1", str(r))
write(os.path.join(tmp, "napoved-modela.json"), mos_file(-5))
check(dp.fetch_mtr_forecast() is None, "star file: članek izpusti MTR")

print("jutranji povzetek: todays_forecast / build_message")
import send_morning_digest as dg  # noqa: E402
dg.MOS = os.path.join(tmp, "napoved-modela.json")
dg.PENDING = os.path.join(tmp, "pending.json")
write(dg.MOS, mos_file(0))                      # svež file: danes NI v njem (lead 1 = jutri)
if os.path.exists(dg.PENDING):
    os.remove(dg.PENDING)
check(dg.build_message(D(0)) is None, "svež file brez zamrznjene napovedi: ne pošlje jutrišnjih številk kot današnjih")
write(dg.PENDING, [{"target_date": D(0), "meteorec": {"tmax": 21.0, "tmin": 4.0, "pop": 0.3}},
                   {"target_date": D(1), "meteorec": {"tmax": 99.0, "tmin": 9.0, "pop": 0.9}}])
m = dg.build_message(D(0))
check(m and "21°" in m["body"] and "30 %" in m["body"] and "99" not in m["body"], "zamrznjena napoved za današnji dan", str(m))
write(dg.PENDING, [])
write(dg.MOS, mos_file(-1))                      # včerajšnji file: danes = lead 1
m = dg.build_message(D(0))
check(m and "11°" in m["body"], "včerajšnji file vsebuje današnji dan (lead 1)", str(m))

print("gasilska stran: nevihtni potencial")
import generate_gasilec_page as gg  # noqa: E402


def no_wind(*a, **k):
    raise urllib.error.URLError("brez omrežja v testu")


gg.fetch_wind_hourly = no_wind
CAPTURED = {}


def fake_shell(slug, title, desc, inner, extra_head=""):
    # ne piši prave strani (seo.write_page) — samo ujemi vsebino
    CAPTURED["inner"] = inner
    return slug


gg.subpage_shell = fake_shell
gg.STORM_MAP_JSON = os.path.join(tmp, "storm.json")
write(gg.STORM_MAP_JSON, {"date": "2026-08-31", "national_score": 65, "national_level": "EKSTREMNO",
                          "national_hour": "18:00", "national_place": "Nova Gorica"})
gg.build_vreme_intervencije_page()
html = CAPTURED["inner"]
check("EKSTREMNO" not in html and "še ni izdana" in html and "2026-08-31" in html,
      "karta z druge datuma se ne prikaže kot današnja")
write(gg.STORM_MAP_JSON, {"date": gg.TODAY.isoformat(), "national_score": 12, "national_level": "NIZKO",
                          "national_hour": "17:00", "national_place": "Koper"})
gg.build_vreme_intervencije_page()
html = CAPTURED["inner"]
check("NIZKO" in html and "še ni izdana" not in html, "današnja karta se prikaže")

print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
