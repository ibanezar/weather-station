#!/usr/bin/env python3
"""tools/test_dolina_v_tednu.py — izračun tedenskega povzetka, e-pošta in pošiljalec (generate_/send_dolina_v_tednu.py)."""
import datetime as dt
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_dolina_v_tednu as G  # noqa: E402
import send_dolina_v_tednu as S  # noqa: E402

fails = 0


def check(cond, msg):
    global fails
    if not cond:
        fails += 1
        print("✗", msg)
    else:
        print("✓", msg)


D = dt.date
START = D(2026, 11, 9)                      # ponedeljek


def make(week=None, prior_years=(2022, 2023, 2024, 2025), base=(6.0, 1.0, 0.0)):
    """Umetni dnevi: prejšnja leta vsak dan tempAvg 6, Tmin 1, padavine 0,5 (običajno ~3,5 mm/teden); izbran teden po `week`."""
    days = {}
    for y in prior_years:
        for i in range(-10, 20):
            d = START.replace(year=y) + dt.timedelta(i)
            days[d] = {"tempHigh": 10, "tempLow": 1, "tempAvg": 6, "precipTotal": 0.5, "windgustHigh": 20}
    for i in range(7):
        d = START + dt.timedelta(i)
        days[d] = dict({"tempHigh": 10, "tempLow": 1, "tempAvg": 6, "precipTotal": 0.5, "windgustHigh": 20}, **(week[i] if week else {}))
    return days


# ── pomožne funkcije
check(G.dni(1) == "1 dan" and G.dni(2) == "2 dneva" and G.dni(3) == "3 dni" and G.dni(5) == "5 dni", "dni: slovnica")
check(G.noci(1) == "1 noč" and G.noci(2) == "2 noči" and G.noci(4) == "4 noči", "noci: slovnica")
check(G.v_dneh(1) == "1 dnevu" and G.v_dneh(2) == "2 dneh" and G.v_dneh(6) == "6 dneh", "v_dneh: mestnik")
check(G.num(-2.7) == "–2,7" and G.temp(1.25).endswith(" °C") and "," in G.temp(1.5), "zapis: decimalna vejica, pomišljaj, nelomljiv presledek")
check(G.last_full_week(D(2026, 11, 15)) == D(2026, 11, 9) and G.last_full_week(D(2026, 11, 16)) == D(2026, 11, 9)
      and G.last_full_week(D(2026, 11, 14)) == D(2026, 11, 2) and G.last_full_week(D(2026, 11, 22)) == D(2026, 11, 16), "last_full_week: nedelja zaključi teden, ponedeljek je že naslednji")

# ── scenariji
wet = G.compute(make([{"precipTotal": 20}] + [{}] * 6), START)
check(wet["headline"].startswith("Moker teden") and wet["stat"]["rain_mm"] == 23.0 and wet["subject"].endswith("moker teden"), "moker teden (23 mm proti ~3,5 mm)")
# običajno 3,5 mm (< 5): suh teden še ni »skoraj suh«; z večjimi običajnimi padavinami pa je
quiet = G.compute(make([{"precipTotal": 0}] * 7), START)
check(not quiet["headline"].startswith("Skoraj suh") and quiet["stat"]["rain_norm_mm"] == 3.5, "suh teden pri majhnih običajnih padavinah (3,5 mm) ni »skoraj suh«")
days = make([{"precipTotal": 0}] * 7)
for d in list(days):
    if d.year != 2026:
        days[d]["precipTotal"] = 2.0
dry = G.compute(days, START)
check(dry["headline"].startswith("Skoraj suh teden") and dry["stat"]["rain_mm"] == 0 and dry["stat"]["rain_norm_mm"] == 14.0, "skoraj suh teden (0 mm proti ~14 mm)")
warm = G.compute(make([{"tempAvg": 9.5, "tempHigh": 13, "tempLow": 6}] * 7), START)
check(warm["headline"].startswith("Teden je bil za 3,5") and "toplejši" in warm["headline"] and warm["subject"].endswith("toplejši teden"), "toplejši teden (+3,5 °C)")
cold = G.compute(make([{"tempAvg": 2, "tempHigh": 4, "tempLow": 0}] * 7), START)
check("hladnejši" in cold["headline"] and abs(cold["stat"]["t_avg"] - 2) < 1e-9, "hladnejši teden")
frost = G.compute(make([{"tempLow": -1}] * 4 + [{}] * 3), START)
frost = G.compute(make([{"tempLow": -1}] * 4 + [{}] * 3), START)
check(frost["headline"].startswith("4 noči z zmrzaljo") and frost["subject"].endswith("4 noči z zmrzaljo"), "zmrzal: 4 noči → naslov tedna")
check(frost["stat"]["frost_nights"] == 4 and any("4 noči z najnižjo temperaturo" in l for l in frost["lines"]), "zmrzal: štetje noči v vrstici")
windy = G.compute(make([{"windgustHigh": 62}] + [{}] * 6), START)
check(windy["headline"].startswith("Vetroven teden") and "62" in windy["headline"], "vetroven teden")
few = G.compute(make(prior_years=(2024, 2025)), START)
check(few["stat"]["t_norm"] is None and few["stat"]["rain_norm_mm"] is None and not any("običajno" in l for l in few["lines"]), "pod 3 prejšnja leta: primerjave ni")
sparse = make()
for i in range(2, 7):
    del sparse[START + dt.timedelta(i)]
check(G.compute(sparse, START) is None, "manj kot 6 dni podatkov: tedna ni")
five = make()
del five[START + dt.timedelta(3)]
check(G.compute(five, START) is not None and G.compute(five, START)["n_days"] == 6, "6 dni podatkov še zadošča")

# ── novosti, blog, napoved
nov = [{"slug": "a", "date": "2026-11-10", "label": "Rekord"}, {"slug": "b", "date": "2026-11-16", "label": "Naslednji teden"}, {"slug": "c", "date": "2026-11-08", "label": "Prejšnji"}]
blog = [{"title": "Članek <b>1</b>", "slug": "x", "url": "/blog/x.html", "date": "2026-11-12"}, {"title": "Star", "slug": "y", "date": "2026-11-01"}]
mos = {"generated_at": "2026-11-16T01:35:00Z", "days": [
    {"date": "2026-11-15", "tmax": 1, "tmin": 1}, {"date": "2026-11-17", "tmax": 9.4, "tmin": 2.6, "p_frost": 0.42}, {"date": "2026-11-18", "tmax": 12, "tmin": 5, "p_frost": 0.0}, {"date": "2026-11-25", "tmax": 3, "tmin": 3}]}
rec = G.compute(make(), START, nov, blog, mos, today=D(2026, 11, 16))
check([n["url"] for n in rec["novosti"]] == ["/novosti/a/"], "novosti: samo dogodki tega tedna")
check([b["url"] for b in rec["blog"]] == ["/blog/x.html"], "blog: samo članki tega tedna")
check(len(rec["napoved"]) == 2 and rec["napoved"][0].startswith("17. novembra: najvišja okoli 9") and "zmrzal 40" in rec["napoved"][0], "napoved: samo dnevi po koncu tedna do +4, zmrzal zaokrožena na 5 %")
check(G.compute(make(), START, nov, blog, dict(mos, generated_at="2026-11-10T01:35:00Z"), today=D(2026, 11, 16))["napoved"] == [], "napoved: starejša od 2 dni se ne uporabi")
check(G.compute(make(), START, nov, blog, None)["napoved"] == [], "napoved: brez datoteke ni vrstic")

# ── e-pošta
html = G.email_html(rec)
check("{{ODJAVA}}" in html and rec["headline"].split(":")[0] in html and "&lt;b&gt;1&lt;/b&gt;" in html and "<b>1</b>" not in html, "e-pošta: povezava za odjavo, naslov, naslovi členov so ubežani")
check("indoor" not in html.lower() and "meteorec.si/novosti/a/" in html and "Kaj prihaja" in html, "e-pošta: brez notranjih meritev, absolutne povezave, razdelek napovedi")

# ── zapis zapisov
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "x.json")
    G.update_data(rec, p)
    older = dict(rec, week_start="2026-11-02", week_end="2026-11-08")
    G.update_data(older, p)
    G.update_data(dict(rec, headline="nov"), p)
    data = json.load(open(p, encoding="utf-8"))
    check([r["week_start"] for r in data] == ["2026-11-09", "2026-11-02"] and data[0]["headline"] == "nov", "update_data: en zapis na teden, najnovejši prvi, ponovni zagon prepiše")

    # pošiljalec
    p2 = os.path.join(d, "y.json")
    G.update_data(rec, p2)
    check(S.latest_record(p2, today=D(2026, 11, 16))["week_start"] == "2026-11-09", "send: zadnji zapis")
    try:
        S.latest_record(p2, today=D(2026, 12, 20))
        check(False, "send: star zapis se ne pošlje")
    except SystemExit:
        check(True, "send: star zapis se ne pošlje")
    pl = S.payload(rec, "s", force=True)
    check(pl["week"] == "2026-11-09" and pl["force"] is True and "{{ODJAVA}}" in pl["html"] and "secret" in pl, "send: vsebina zahtevka")

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"ok": true, "sent": 3}'
    seen = {}
    def fake(req, timeout=None):
        seen["ua"] = req.get_header("User-agent"); seen["url"] = req.full_url
        return Resp()
    status, body = S.post(pl, opener=fake)
    check(status == 200 and body["sent"] == 3 and seen["ua"] == S.WORKER_UA and seen["url"].endswith("/tedenski/poslji"), "send: POST z User-Agent")

# ── prave meritve (samo da izračun ne pade)
real = G.compute(G.load_days(), G.last_full_week(max(G.load_days())))
check(real is not None and real["headline"] and real["lines"] and real["n_days"] >= 6, "prave meritve: zadnji popolni teden se izračuna")
sys.exit(1 if fails else 0)
