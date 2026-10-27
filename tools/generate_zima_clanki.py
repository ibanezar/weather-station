#!/usr/bin/env python3
"""
tools/generate_zima_clanki.py -- niz zimskih člankov (27. 10. 2026), zasnovan po analizi iskalnih izrazov.

Osem ročno napisanih podatkovnih člankov (slugi so v ARTICLES). Številke pridejo iz committanih virov:
  - history.json            (postaja IREICA1: samo zunanja dnevna temperatura, vlaga, padavine),
  - data/hourly-observations.csv (urni zapis zunanjega senzorja: temperatura, rosišče, veter),
  - data/crnivec-arso.json  (padavinska postaja ARSO Črnivec, 848 m: snežna odeja, nov sneg),
  - data/winter-data.json   (modelski posnetek: meja sneženja, gore, žled -- samo kot stanje na dan objave).
Besedilo nič ne izmišlja; trditve varujejo assert-i, ki pri spremenjenih podatkih generator ustavijo (članek je
treba prenoviti, ne zaobiti asserta). Članki so posnetek na dan objave in se ne prepisujejo samodejno.
Notranjih meritev postaje članki ne uporabljajo (glej CLAUDE.md).

Ročni članek po CLAUDE.md gre skozi lekturo (`lektura.yml` je od 2. 10. 2026 izklopljena -- do ponovnega vklopa
ostane slogovni pregled po docs/slog-pisanja.md).

Usage:
    python3 tools/generate_zima_clanki.py [--only SLUG] [--dry-run] [--text] [--wire] [--force]
"""
import csv
import datetime
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_slane_se_ni_post import (  # noqa: E402  (skupni pomočniki, ne podvojeni)
    CYAN, AMBER, GREEN, GREY, INK, MUTED, GRID, SURFACE, NBSP, STYLE as BASE_STYLE,
    num, temp, dm, dlong, fig, tiles, legend)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
TODAY_FIXED = datetime.date(2026, 10, 27)
LINK = 'style="color:var(--blue)"'
RED = "#f87171"

STYLE = BASE_STYLE.replace("</style>", """.zt{overflow-x:auto;margin:1.2rem 0}
.zt table{width:100%;border-collapse:collapse;font-size:.9rem;min-width:420px}
.zt th{text-align:left;color:var(--muted);font-weight:600;font-size:.78rem;padding:.4rem .5rem;border-bottom:1px solid var(--card-border)}
.zt td{padding:.45rem .5rem;border-bottom:1px solid var(--card-border);color:var(--text)}
.zt tr:last-child td{border-bottom:none}
.zt-note{color:var(--muted);font-size:.82rem;line-height:1.5;margin:-.6rem 0 1.2rem}
</style>""")

_MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra",
        "oktobra", "novembra", "decembra"]
USE_NOTE = ('<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko '
            'povzemate samo z navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali '
            'vdelavo grafov in izračunov se predhodno dogovorite z avtorjem.</p>')


def a(href, text):
    return f'<a href="{href}" {LINK}>{text}</a>'


def pct(n, d):
    return round(100 * n / d)


# ───────────────────────── podatki ─────────────────────────

class Ctx:
    def __init__(self):
        H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
        H = H.get("days", H)
        self.H = {d: v for d, v in H.items() if v.get("src") != "era5"}
        c = json.load(open(os.path.join(ROOT, "data", "crnivec-arso.json"), encoding="utf-8"))
        self.C = {r[0]: r for r in c["days"]}
        self.C_elev = c["elevation_m"]
        self.W = json.load(open(os.path.join(ROOT, "data", "winter-data.json"), encoding="utf-8"))
        self.hourly = [r for r in csv.DictReader(open(os.path.join(ROOT, "data", "hourly-observations.csv"), encoding="utf-8"))
                       if r["quality_flag"] == "ok" and r["temp_c"] and r["dewpoint_c"]]
        self.last = datetime.date.fromisoformat(max(self.H))
        assert self.last == datetime.date(2026, 10, 26), f"zadnji dan v history.json je {self.last}; članki so napisani za 26. 10."
        assert self.W["snowpack"]["updated"] == "2026-10-27", "winter-data.json ni z dne 27. 10. -- modelski posnetek v člankih je treba prenoviti"

    def days(self, a_, b_):
        return [d for d in sorted(self.H) if a_ <= datetime.date.fromisoformat(d) <= b_]

    def val(self, d, k):
        return self.H.get(d, {}).get(k)


def D(s):
    return datetime.date.fromisoformat(s)


def mean7_first_below(c, y, thr=7.0):
    ds = [d for d in c.days(datetime.date(y, 9, 1), datetime.date(y, 12, 31)) if c.val(d, "tempAvg") is not None]
    for i in range(6, len(ds)):
        if statistics.mean(c.val(x, "tempAvg") for x in ds[i - 6:i + 1]) < thr:
            return D(ds[i])
    return None


def mean7_spring_sustained(c, y, thr=7.0):
    ds = [d for d in c.days(datetime.date(y, 3, 1), datetime.date(y, 5, 31)) if c.val(d, "tempAvg") is not None]
    m = [statistics.mean(c.val(x, "tempAvg") for x in ds[i - 6:i + 1]) if i >= 6 else None for i in range(len(ds))]
    for i in range(6, len(ds)):
        if all(x >= thr for x in m[i:]):
            return D(ds[i])
    return None


def first_freeze(c, y):
    return next((D(d) for d in c.days(datetime.date(y, 9, 1), datetime.date(y, 12, 31))
                 if c.val(d, "tempLow") is not None and c.val(d, "tempLow") <= 0), None)


def last_freeze_spring(c, y):
    ds = [d for d in c.days(datetime.date(y, 1, 1), datetime.date(y, 6, 30)) if c.val(d, "tempLow") is not None and c.val(d, "tempLow") <= 0]
    return D(ds[-1])


def cold_precip(c, d):
    """Hladen padavinski dan: padavine vsaj 0,2 mm in povprečna dnevna temperatura do 1 °C (približek, ne meritev snega)."""
    v = c.H.get(d)
    return bool(v) and (v.get("precipTotal") or 0) >= 0.2 and v.get("tempAvg") is not None and v["tempAvg"] <= 1.0


def crn_winter(c, y):
    """Vrstice ARSO Črnivec od 1. 7. y do 30. 6. y+1."""
    return [r for d, r in sorted(c.C.items()) if datetime.date(y, 7, 1) <= D(d) <= datetime.date(y + 1, 6, 30)]


def crn_first_snow(c, y):
    return next(D(r[0]) for r in crn_winter(c, y) if r[2] and r[2] > 0)


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def _ref(d):
    y = 2001 if d.month >= 7 else 2002
    try:
        return datetime.date(y, d.month, d.day)
    except ValueError:
        return datetime.date(y, d.month, 28)


def dots_chart(rows, start, end, ticks, label, vlines=(), w=460, rowh=34, lw=62):
    """Vrstice s pikami na časovni osi. rows = [(oznaka, krepko, [(datum, barva, naslov, zgoraj_ali_spodaj)])];
    start/end/ticks so datumi v referenčnem letu (2001 za jesen, 2002 za pomlad)."""
    pr, pt, pb = 40, 22, 30
    h = pt + pb + rowh * len(rows)
    iw = w - lw - pr
    span = (end - start).days
    X = lambda d: lw + iw * (_ref(d) - start).days / span
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" xmlns="http://www.w3.org/2000/svg">']
    base = pt + rowh * len(rows)
    for t in ticks:
        x = lw + iw * (t - start).days / span
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt - 6}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{dm(t)}</text>')
    for vd, vl, vc in vlines:
        x = lw + iw * (vd - start).days / span
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt - 6}" y2="{base}" stroke="{vc}" stroke-width="1.5" stroke-dasharray="4 3"/>')
        p.append(f'<text x="{x:.1f}" y="{pt - 10}" text-anchor="middle" font-size="10.5" font-weight="700" fill="{vc}">{vl}</text>')
    for i, (lab, bold, pts) in enumerate(rows):
        cy = pt + rowh * i + rowh / 2
        p.append(f'<text x="{lw - 8}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" font-weight="{700 if bold else 400}" fill="{INK}">{lab}</text>')
        p.append(f'<line x1="{lw}" x2="{w - pr}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{GREY}" stroke-opacity=".25" stroke-width="5" stroke-linecap="round"/>')
        for d, col, ttl, pos in pts:
            x = X(d)
            p.append(f'<circle cx="{x:.1f}" cy="{cy:.1f}" r="6.2" fill="{col}" stroke="{SURFACE}" stroke-width="1.8"><title>{ttl}</title></circle>')
            ty = cy - 10 if pos == "up" else cy + 19
            p.append(f'<text x="{x:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="10" font-weight="700" fill="{INK}" '
                     f'stroke="{SURFACE}" stroke-width="3" paint-order="stroke">{dm(d)}</text>')
    p.append("</svg>")
    return "".join(p)


def bars_chart(cats, series, ymax, label, ticks=None, fmt=None, w=460, h=230, hl=None):
    """Navpični stolpci, skupine po kategorijah. series = [(ime, barva, [vrednosti])]; hl = indeks kategorije za poudarek."""
    pl, pr, pt, pb = 38, 10, 22, 34
    ih = h - pt - pb
    iw = w - pl - pr
    fmt = fmt or (lambda v: f"{v:.0f}")
    ticks = ticks or [0, ymax / 2, ymax]
    gw = iw / len(cats)
    bw = gw * 0.72 / len(series)
    Y = lambda v: pt + ih * (1 - v / ymax)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" xmlns="http://www.w3.org/2000/svg">']
    for t in ticks:
        y = Y(t)
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{pl - 6}" y="{y + 3.5:.1f}" text-anchor="end" font-size="10.5" fill="{MUTED}">{fmt(t)}</text>')
    for i, cat in enumerate(cats):
        gx = pl + gw * i + gw * 0.14
        for j, (name, col, vals) in enumerate(series):
            v = vals[i]
            x = gx + bw * j
            y = Y(v)
            op = 1 if hl is None or hl == i else .55
            p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw - 1.5:.1f}" height="{max(Y(0) - y, 0):.1f}" rx="2" fill="{col}" fill-opacity="{op}">'
                     f'<title>{cat}, {name}: {fmt(v)}</title></rect>')
            p.append(f'<text x="{x + (bw - 1.5) / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="{10 if len(series) == 1 else 9}" '
                     f'font-weight="700" fill="{INK}">{fmt(v)}</text>')
        p.append(f'<text x="{pl + gw * i + gw / 2:.1f}" y="{h - 12}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{cat}</text>')
    p.append("</svg>")
    return "".join(p)


def table(head, rows, label, note=None):
    th = "".join(f"<th>{x}</th>" for x in head)
    tr = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows)
    out = f'<div class="zt" tabindex="0" role="region" aria-label="{label}"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'
    if note:
        out += f'<p class="zt-note">{note}</p>'
    return out


def nb(h):
    return re.sub(r"(\d) (°C|%|mm|cm|m\b)", lambda m: m.group(1) + NBSP + m.group(2), h)


def ul(items):
    return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


# ───────────────────────── 1. zimske gume ─────────────────────────

def art_gume(c):
    YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
    fb = {y: mean7_first_below(c, y) for y in YEARS}
    assert {y: (d.month, d.day) for y, d in fb.items()} == {2020: (11, 9), 2021: (10, 15), 2022: (11, 20), 2023: (11, 12), 2024: (11, 6), 2025: (11, 9)}, fb
    assert mean7_first_below(c, 2026) is None, "letos je 7-dnevno povprečje že pod 7 °C -- prenovi članek"
    m7 = statistics.mean(c.val(d, "tempAvg") for d in sorted(c.H)[-7:])
    assert abs(m7 - 8.7) < .05, m7

    mon = {}
    for m in (10, 11, 12, 1, 2, 3, 4):
        ds = [v for d, v in c.H.items() if D(d).month == m and v.get("tempLow") is not None and v.get("tempAvg") is not None]
        mon[m] = (len(ds), sum(v["tempLow"] < 7 for v in ds), sum(v["tempLow"] <= 0 for v in ds), sum(v["tempAvg"] < 7 for v in ds))
    assert mon[10][0] == 212 and pct(mon[10][1], 212) == 58 and mon[10][2] == 12
    assert pct(mon[11][1], mon[11][0]) == 92 and pct(mon[11][2], mon[11][0]) == 40
    assert all(95 <= pct(mon[m][1], mon[m][0]) <= 98 for m in (12, 1, 2, 3))

    ff = {y: first_freeze(c, y) for y in YEARS + [2026]}
    exp = {2020: (10, 14), 2021: (10, 13), 2022: (11, 20), 2023: (10, 17), 2024: (11, 4), 2025: (10, 3), 2026: (10, 23)}
    assert {y: (d.month, d.day) for y, d in ff.items()} == exp, ff
    before = sum(1 for y, d in ff.items() if d < datetime.date(y, 11, 15))
    assert before == 6
    assert c.val("2026-10-23", "tempLow") == -0.1

    sp = {y: mean7_spring_sustained(c, y) for y in YEARS}
    lf = {y: last_freeze_spring(c, y) for y in YEARS}
    assert {y: (d.month, d.day) for y, d in sp.items()} == {2020: (4, 9), 2021: (4, 22), 2022: (4, 8), 2023: (4, 16), 2024: (4, 29), 2025: (3, 25)}, sp
    assert {y: (d.month, d.day) for y, d in lf.items()} == {2020: (5, 7), 2021: (4, 24), 2022: (4, 21), 2023: (4, 11), 2024: (4, 23), 2025: (4, 11)}, lf
    assert all(d > datetime.date(y, 3, 15) for y, d in sp.items()) and all(d > datetime.date(y, 3, 15) for y, d in lf.items())
    assert abs(statistics.mean(c.val(d, "tempHigh") for d in c.days(datetime.date(2022, 11, 1), datetime.date(2022, 11, 14))) - 15.0) < .05

    rows = [(str(y), False, [(fb[y], CYAN, f"{y}: 7-dnevno povprečje prvič pod 7 °C, {dm(fb[y])}", "up")]) for y in YEARS]
    rows.append(("2026", True, [(datetime.date(2026, 10, 26), AMBER, "2026: do 26. 10. povprečje še ni pod 7 °C (8,7 °C)", "up")]))
    f_avg = fig("Kdaj je 7-dnevno povprečje prvič padlo pod 7 °C",
                dots_chart(rows, datetime.date(2001, 10, 1), datetime.date(2001, 11, 30),
                           [datetime.date(2001, 10, 1), datetime.date(2001, 10, 15), datetime.date(2001, 11, 1), datetime.date(2001, 11, 15), datetime.date(2001, 11, 30)],
                           "Datum, ko je 7-dnevno povprečje dnevne temperature prvič padlo pod 7 °C, po letih",
                           vlines=[(datetime.date(2001, 11, 15), "15. 11.", RED)]),
                "Vsaka pika je prvi dan, ko je povprečje dnevnih povprečij temperature v zadnjih sedmih dneh v Rečici padlo pod 7 °C. "
                "Rdeča črta je zakonski začetek obvezne zimske opreme. Oranžna pika je letošnje stanje: do 26. oktobra povprečje še ni pod 7 °C.")
    cats = ["okt.", "nov.", "dec.", "jan.", "feb.", "mar.", "apr."]
    ms = (10, 11, 12, 1, 2, 3, 4)
    f_mon = fig("Delež dni pod 7 °C po mesecih",
                legend([("najnižja dnevna temperatura pod 7 °C", CYAN, ""), ("povprečna dnevna temperatura pod 7 °C", AMBER, "")])
                + bars_chart(cats, [("najnižja", CYAN, [pct(mon[m][1], mon[m][0]) for m in ms]),
                                    ("povprečna", AMBER, [pct(mon[m][3], mon[m][0]) for m in ms])],
                             100, "Delež dni z najnižjo oziroma povprečno temperaturo pod 7 °C po mesecih",
                             ticks=[0, 50, 100], fmt=lambda v: f"{v:.0f}"),
                "Odstotki dni v mesecu med letoma 2019 (november) in 2026 (do 26. oktobra). Jutro je hladnejše od dneva, zato je modri stolpec "
                "pri vsakem mesecu višji od oranžnega.")

    t_tiles = tiles([
        ("58", "%", "oktobrskih jutr je imelo najnižjo temperaturo pod 7 °C. Zakonski začetek je šele 15. novembra.", False),
        ("92", "%", "novembrskih jutr je pod 7 °C, 40 % pa jih je na 0 °C ali pod njo.", False),
        ("6 od 7", "", "jeseni, v katerih je prva noč z 0 °C ali manj nastopila pred 15. novembrom.", True),
    ])
    lead = ("Zimska oprema je v Sloveniji obvezna od <strong>15. novembra</strong>, jutra v Rečici ob Savinji pa so hladna precej prej: "
            "v oktobrih med letoma 2020 in 2026 je bila najnižja dnevna temperatura pod 7 °C v <strong>58 %</strong> dni. "
            "Sedemdnevno povprečje dnevne temperature je v zadnjih šestih jeseni prvič padlo pod 7 °C med 15. oktobrom in 20. novembrom, najpogosteje okoli 9. novembra. "
            "Za dolino je zakonski datum torej razumen za povprečen dan, za zgodnja jutra pa je pozen.")
    s1 = [
        "<strong>Kratek odgovor:</strong> po podatkih iz Rečice je 15. november dober datum za povprečen dan, za jutra pa prepozen. "
        "Če se pogosto vozite zgodaj zjutraj ali v hribe, po mojem branju podatkov ni razloga čakati do tega datuma.",
        "Pravilo in priporočilo sta dve različni stvari. Zimska oprema je obvezna od 15. novembra do 15. marca, v zimskih razmerah (sneg, led, žled) pa tudi zunaj tega obdobja. "
        "Priporočilo, da gume zamenjate, ko se temperatura stalno spusti pod 7 °C, je splošno praktično pravilo, ne zakonska meja. "
        "Natančna pravila preverite pri AMZS ali v veljavnih predpisih.",
        t_tiles,
    ]
    s2 = [
        f_avg,
        f"Za povprečno dnevno temperaturo sem uporabil sedemdnevno drseče povprečje, ker en hladen dan še ne pomeni jeseni. "
        f"Sedemdnevno povprečje je padlo pod 7 °C {dlong(fb[2021])} 2021, {dlong(fb[2024])} 2024, {dlong(fb[2020])} 2020 in 2025, {dlong(fb[2023])} 2023 ter {dlong(fb[2022])} 2022.",
        "Do 15. novembra se je to zgodilo v petih od šestih let. Izjema je jesen 2022, ki je bila tako topla, da je bila povprečna najvišja dnevna temperatura v prvih 14 novembrskih dneh 15,0 °C.",
        f"Letos je sedemdnevno povprečje do 26. oktobra {num(m7)} °C, torej še ni pod 7 °C.",
    ]
    s3 = [
        f_mon,
        f"Povprečje prikrije jutra: za najnižjo temperaturo pod 7 °C zadošča že jasna noč. V oktobru je takih jutr 58 %, v novembru 92 %, od decembra do marca pa 95–98 %.",
        f"Prva noč z 0 °C ali manj je nastopila {dlong(ff[2025])} 2025, {dlong(ff[2021])} 2021, {dlong(ff[2020])} 2020, {dlong(ff[2023])} 2023, {dlong(ff[2026])} 2026 (izmerjenih –0,1 °C), "
        f"{dlong(ff[2024])} 2024 in {dlong(ff[2022])} 2022. Pred 15. novembrom je nastopila v šestih od sedmih jeseni.",
        "Če vozite zgodaj zjutraj, so ti datumi za vas bolj merodajni kot povprečje celega dne. Napoved poledice za dolino je na strani "
        + a("/zima/poledica/", "Poledica") + ".",
    ]
    tbl = table(["Leto", "Sedemdnevno povprečje trajno nad 7 °C od", "Zadnje jutro z 0 °C ali manj"],
                [[str(y), dlong(sp[y]), dlong(lf[y])] for y in YEARS],
                "Spomladanski datumi po letih", "Povprečje je trajno nad 7 °C, če od tega dne do konca maja nobeno sedemdnevno povprečje ni nižje.")
    s4 = [
        tbl,
        "V nobenem od šestih let sedemdnevno povprečje do 15. marca ni bilo trajno nad 7 °C. Najbolj zgodaj je to postalo 25. marca 2025. "
        "Tudi jutra z 0 °C ali manj so se v vseh letih pojavila še po 15. marcu: zadnje je bilo najprej 11. aprila, najpozneje pa 7. maja 2020.",
        "Zakonska obveznost se torej konča sredi marca, hladna jutra v dolini pa še ne. Po podatkih je v aprilu zamenjava varnejša kot sredi marca, "
        "v hribih in na prelazih pa lahko zimske razmere trajajo še dlje.",
    ]
    s5 = [
        ul([
            "<strong>Jesen:</strong> po teh podatkih je zamenjava med drugo polovico oktobra in začetkom novembra smiselna, 15. november pa je skrajni rok. Kdor vozi zgodaj zjutraj ali v hribe, naj ne čaka na prvi sneg. Napoved najnižje temperature in verjetnost poledice najdete na strani "
            + a("/zima/poledica/", "Poledica") + ".",
            "<strong>Pot čez prelaz:</strong> na Črnivcu je hladneje kot v dolini. Trenutne razmere in izmerjeno temperaturo prikazuje " + a("https://crnivec.si/", "crnivec.si") +
            ", uradno stanje ceste pa " + a("https://www.promet.si/", "promet.si") + ". Pregled prelazov je na " + a("/zima/prevoznost-prelazov/", "strani o prevoznosti prelazov") + ".",
            "<strong>Pomlad:</strong> ne hitite s snemanjem takoj po 15. marcu. Poglejte napoved najnižje temperature za naslednje dni.",
        ]),
    ]
    s6 = [
        ul([
            "<strong>Šest let je malo.</strong> Postaja meri od novembra 2019, zato primerjam jeseni 2020–2025 in letošnjo do 26. oktobra. Razlike med leti niso trend.",
            "<strong>Ena postaja v dolini.</strong> Postaja stoji na dnu doline v Rečici ob Savinji. V hribih in mraziščih je hladneje.",
            "<strong>Sedemdnevno povprečje in prag 7 °C sta moja izbira.</strong> Ne pomenita pravne ali tehnične meje, ampak le način primerjave med leti.",
            "<strong>To ni nasvet strokovnjaka za pnevmatike.</strong> Obraba, vrsta gume in način vožnje se razlikujejo od vozila do vozila.",
        ]),
        USE_NOTE,
    ]
    title = "Kdaj menjati zimske gume? Podatki iz Rečice"
    desc = "Zimska oprema je obvezna od 15. novembra, jutra pod 7 °C pa so v Rečici že oktobra. Podatki postaje IREICA1 za šest jeseni in pomladi."
    return dict(
        slug="kdaj-menjati-zimske-gume-recica-1027", title=title, desc=desc, og_title="Kdaj menjati\nzimske gume?",
        tags=["zimske gume", "zima", "temperatura", "podatki", "Rečica"], og_photo="weather-station", accent="#22d3ee", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Zakonski datum je za jutra pozen, za povprečen dan pa ustrezen", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — povprečje", "heading": "Kdaj povprečje pade pod 7 °C", "id": "povprecje", "paragraphs": s2},
            {"label": "03 — jutra", "heading": "Jutra so hladna že v oktobru", "id": "jutra", "paragraphs": s3},
            {"label": "04 — pomlad", "heading": "Kdaj snemati zimske gume: 15. marec je prezgodaj", "id": "pomlad", "paragraphs": s4},
            {"label": "05 — praktično", "heading": "Kaj naj naredite", "id": "prakticno", "paragraphs": s5},
            {"label": "06 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": s6},
        ],
        sources="Viri: postaja IREICA1 (dnevna najnižja, najvišja in povprečna temperatura zunanjega senzorja od 7. 11. 2019 do 26. 10. 2026). Pravila o zimski opremi: preverite pri AMZS.")


# ───────────────────────── 2. prvi sneg v dolini ─────────────────────────

def art_sneg(c):
    WY = list(range(2019, 2026))
    rec = {}
    for y in WY:
        rec[y] = next(D(d) for d in c.days(datetime.date(y, 10, 1), datetime.date(y + 1, 4, 30)) if cold_precip(c, d))
    assert {y: (d.month, d.day) for y, d in rec.items()} == {2019: (12, 1), 2020: (11, 23), 2021: (11, 25), 2022: (12, 11), 2023: (12, 3), 2024: (11, 21), 2025: (11, 19)}, rec
    assert not any(cold_precip(c, d) for d in c.days(datetime.date(2026, 10, 1), c.last)), "letos je že bil hladen padavinski dan"
    crn = {y: crn_first_snow(c, y) for y in range(2021, 2026)}
    assert {y: (d.month, d.day) for y, d in crn.items()} == {2021: (11, 27), 2022: (11, 23), 2023: (11, 30), 2024: (11, 22), 2025: (11, 18)}, crn
    med = sorted(rec.values(), key=lambda d: _ref(d))[3]
    assert (med.month, med.day) == (11, 25)
    near = sum(1 for y in range(2021, 2026) if abs((rec[y] - crn[y]).days) <= 3)
    assert near == 4 and (rec[2022] - crn[2022]).days == 18

    sl = c.W["snow_line"]["daily"]
    assert sl[-1]["date"] == "2026-11-02" and sl[-1]["line_m"] == 1210 and all(x["cm_at_station"] == 0 for x in sl)
    golte = next(p for p in c.W["mountains"]["peaks"] if p["name"] == "Golte")
    g31 = next(x for x in golte["daily"] if x["date"] == "2026-10-31")
    assert g31["snow_cm"] == 1.3

    rows = []
    for y in WY:
        pts = [(rec[y], CYAN, f"Rečica {y}/{str(y + 1)[2:]}: prvi hladen padavinski dan, {dm(rec[y])}", "up")]
        if y in crn:
            pts.append((crn[y], AMBER, f"Črnivec {y}/{str(y + 1)[2:]}: prvi nov sneg, {dm(crn[y])}", "down"))
        rows.append((f"{y}/{str(y + 1)[2:]}", False, pts))
    f_dots = fig("Prva hladna padavina po zimah",
                 legend([("Rečica: hladen padavinski dan (približek)", CYAN, ""), ("Črnivec, 848 m: izmerjen nov sneg", AMBER, "")])
                 + dots_chart(rows, datetime.date(2001, 11, 10), datetime.date(2001, 12, 20),
                              [datetime.date(2001, 11, 15), datetime.date(2001, 12, 1), datetime.date(2001, 12, 15)],
                              "Prvi hladen padavinski dan v Rečici in prvi izmerjeni nov sneg na Črnivcu po zimah", rowh=44, lw=66),
                 "Modre pike: prvi dan od 1. oktobra z vsaj 0,2 mm padavin in povprečno dnevno temperaturo do 1 °C v Rečici. To ni meritev snega, ampak približek. "
                 "Oranžne pike: prvi dan z novim snegom, ki ga je izmerila padavinska postaja ARSO Črnivec (848 m). Za Črnivec imam podatke od aprila 2021.")
    tl = tiles([
        ("25. 11.", "", "mediana prvega hladnega padavinskega dne v Rečici v zadnjih sedmih zimah. Razpon je od 19. 11. do 11. 12.", False),
        ("18.–30. 11.", "", "izmerjen prvi nov sneg na Črnivcu v petih zimah. Prej ali pozneje ga v teh zimah ni bilo.", False),
        ("23. 10.", "", "letošnja prva noč z 0 °C ali manj (–0,1 °C). Hladnega padavinskega dne letos še ni bilo.", True),
    ])
    lead = ("Postaja v Rečici ob Savinji snega ne meri, hladne padavine pa so vidne v podatkih. "
            "Prvi dan s padavinami in povprečno dnevno temperaturo do 1 °C je v zadnjih sedmih zimah nastopil med <strong>19. novembrom in 11. decembrom</strong>, mediana je 25. november. "
            "Na Črnivcu, na 848 m, je ARSO prvi nov sneg v petih zimah izmeril med 18. in 30. novembrom. Hladne padavine v dolini torej običajno pridejo ob koncu novembra, datum pa niha za do tri tedne.")
    s1 = [
        "<strong>Kratek odgovor:</strong> prvi sneg v dolini je po podatkih zadnjih sedmih zim običajno ob koncu novembra. "
        "V štirih od sedmih zim se je prvi hladen padavinski dan zgodil pred 1. decembrom, v treh pozneje, enkrat šele 11. decembra.",
        tl,
        "Pri razlagi je potrebna previdnost. Padavine ob povprečni temperaturi do 1 °C so lahko sneg, dež s snegom ali podhlajen dež. "
        "Postaja ne razlikuje vrste padavin in ne meri višine snežne odeje. Zato rečem »hladen padavinski dan«, ne »prvi sneg«.",
    ]
    s2 = [
        f_dots,
        f"Na Črnivcu, kjer padavinska postaja ARSO meri sneg, je v petih zimah nov sneg prvič padel {dlong(crn[2025])} 2025, {dlong(crn[2024])} 2024, {dlong(crn[2022])} 2022, "
        f"{dlong(crn[2021])} 2021 in {dlong(crn[2023])} 2023.",
        f"V Rečici sem v istih petih zimah našel prvi hladen padavinski dan {dlong(rec[2025])} 2025, {dlong(rec[2024])} 2024, {dlong(rec[2022])} 2022, {dlong(rec[2021])} 2021 in {dlong(rec[2023])} 2023. "
        "Razlika do Črnivca je v štirih od petih zim največ tri dni. Izjema je zima 2022/23: na Črnivcu je sneg padel 23. novembra, v dolini pa je bila prva hladna padavina šele 11. decembra, 18 dni pozneje.",
        "Dolina in postaja, ki leži skoraj 500 m više, torej prvi hladen val pogosto doživita skoraj hkrati. Zakaj je bilo pozimi 2022/23 drugače, iz teh podatkov ne morem reči.",
    ]
    s3 = [
        f"Letos je 23. oktobra postaja prvič izmerila temperaturo pod ničlo: –0,1 °C. Hladnega padavinskega dne od 1. oktobra še ni bilo. "
        "O napovedi te noči sem pisal v članku o " + a("/blog/16-noci-pod-5-c-slane-se-ni-1021.html", "šestnajstih nočeh pod 5 °C") + ".",
        "Modelski posnetek z dne 27. oktobra (Open-Meteo, ne meritev): meja sneženja naj bi se do 2. novembra spustila z 2660 na 1210 m. "
        "Pričakovani nov sneg na višini postaje (366 m) je v vseh sedmih dneh 0 cm. Na Goltah (1400 m) model 31. oktobra napoveduje približno 1,3 cm snega.",
        "V naslednjih sedmih dneh sneg v dolini po modelu ni pričakovan, v visokih legah pa se približuje. Za sprotno sliko spremljajte "
        + a("/zima/meja-snezenja/", "mejo sneženja") + " in " + a("/zima/snezna-karta/", "snežno karto") + ". Več o višjih legah je v članku o "
        + a("/blog/prvi-sneg-golte-solcava-menina-1027.html", "prvem snegu na Goltah in v Solčavi") + ".",
    ]
    s4 = [
        ul([
            "<strong>Če vozite:</strong> prve hladne padavine v dolini ob koncu novembra pomenijo, da morate imeti zimsko opremo nameščeno prej. O terminu pišem v članku "
            + a("/blog/kdaj-menjati-zimske-gume-recica-1027.html", "Kdaj menjati zimske gume") + ".",
            "<strong>Če iščete bel božič:</strong> prvi sneg je le začetek. Kako pogosto je na božični dan res sneg, preverjam v članku "
            + a("/blog/bela-bozic-zgornja-savinjska-dolina-1027.html", "Bel božič v Savinjski dolini") + ".",
            "<strong>Napoved zime:</strong> splošno sliko o zimi 2026/27 najdete v članku " + a("/blog/zima-2026-2027-el-nino-napoved.html", "o El Niñu in zimi") + ".",
        ]),
    ]
    s5 = [
        ul([
            "<strong>Sedem zim je malo.</strong> Postaja meri od novembra 2019. Zima 2019/20 je nepopolna na začetku (podatki od 7. novembra), vendar prvi hladen padavinski dan v tej zimi nastopi šele 1. decembra, zato je ocena veljavna.",
            "<strong>Hladen padavinski dan ni sneg.</strong> Prag 1 °C in 0,2 mm sta moja izbira za primerjavo med leti. Brez meritve vrste padavin je to najbližji približek, ki ga imam.",
            "<strong>Črnivec ni dolina.</strong> Padavinska postaja ARSO stoji na 848 m, arhiv ARSO zaostaja za nekaj tednov (zadnji vnos v mojem zapisu je 30. 9. 2026).",
            "<strong>Modelski podatki niso uradna napoved.</strong> Za opozorila spremljajte " + a("https://vreme.arso.gov.si/napoved", "ARSO") + ".",
        ]),
        USE_NOTE,
    ]
    title = "Kdaj pade prvi sneg v dolini? Sedem zim v Rečici"
    desc = "Prvi hladen padavinski dan v Rečici je v sedmih zimah nastopil med 19. 11. in 11. 12., prvi sneg na Črnivcu pa med 18. in 30. novembrom."
    return dict(
        slug="kdaj-pade-prvi-sneg-v-dolini-recica-1027", title=title, desc=desc, og_title="Kdaj pade\nprvi sneg v dolini?",
        tags=["sneg", "prvi sneg", "zima", "Črnivec", "podatki"], og_photo="misty-valley", accent="#22d3ee", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Prvi sneg v dolini je običajno ob koncu novembra", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — primerjava", "heading": "Dolina in Črnivec: razlika je pogosto le nekaj dni", "id": "primerjava", "paragraphs": s2},
            {"label": "03 — letos", "heading": "Letos: ničla je že bila, sneg še ne", "id": "letos", "paragraphs": s3},
            {"label": "04 — praktično", "heading": "Kaj naj naredite", "id": "prakticno", "paragraphs": s4},
            {"label": "05 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": s5},
        ],
        sources="Viri: postaja IREICA1 (padavine in povprečna dnevna temperatura); padavinska postaja ARSO Črnivec (848 m, arhiv do 30. 9. 2026); modelski posnetek Open-Meteo z dne 27. 10. 2026.")


# ───────────────────────── 3. bel božič ─────────────────────────

def art_bozic(c):
    Y = list(range(2019, 2026))
    info = {}
    for y in Y:
        ds = [f"{y}-12-{x}" for x in (24, 25, 26)]
        assert all(d in c.H for d in ds), y
        info[y] = dict(lo=min(c.val(d, "tempLow") for d in ds), hi=max(c.val(d, "tempHigh") for d in ds),
                       mm=sum(c.val(d, "precipTotal") or 0 for d in ds), cp=any(cold_precip(c, d) for d in ds))
    n_cp = sum(1 for y in Y if info[y]["cp"])
    assert n_cp == 2 and info[2021]["cp"] and info[2025]["cp"] and not info[2020]["cp"]
    warm = [y for y in Y if info[y]["hi"] >= 10]
    assert warm == [2019, 2020, 2022, 2023]
    crn = {y: [c.C[f"{y}-12-{x}"][1] for x in (24, 25, 26)] for y in range(2021, 2026)}
    assert crn == {2021: [0.0] * 3, 2022: [0.0] * 3, 2023: [0.0] * 3, 2024: [14.0, 4.0, 0.0], 2025: [4.0, 15.0, 12.0]}, crn
    assert c.val("2025-12-24", "tempHigh") == 1.5 and c.val("2025-12-26", "tempHigh") == 2.5

    rows = []
    for y in Y:
        i = info[y]
        crn_txt = " / ".join(f"{x:.0f}" for x in crn[y]) if y in crn else "ni podatkov"
        rows.append([str(y), f"{temp(i['lo'])} do {temp(i['hi'])}", f"{num(i['mm'])} mm", "da" if i["cp"] else "ne", crn_txt])
    tbl = table(["Leto", "Rečica: najnižja do najvišja, 24.–26. 12.", "Rečica: padavine", "Hladen padavinski dan", "Črnivec: snežna odeja 24. / 25. / 26. 12. (cm)"],
                rows, "Božič v Rečici in na Črnivcu po letih",
                "Hladen padavinski dan: vsaj 0,2 mm padavin in povprečna dnevna temperatura do 1 °C (približek, ne meritev snega). Pri Črnivcu je postaja ARSO na 848 m; zapis imam od aprila 2021.")
    tl = tiles([
        ("2 od 5", "", "božičev na Črnivcu (848 m) je imelo na božični dan snežno odejo: 2024 (4 cm) in 2025 (15 cm).", False),
        ("2 od 7", "", "božičev v Rečici je imelo hladen padavinski dan med 24. in 26. decembrom: 2021 in 2025.", False),
        ("4 od 7", "", "božičev v Rečici je imelo v teh treh dneh vsaj en dan z najvišjo temperaturo 10 °C ali več.", True),
    ])
    lead = ("Bel božič v dolini je v zadnjih sedmih letih prej izjema kot pravilo. Na Črnivcu (848 m) je bila na božični dan snežna odeja v <strong>dveh od petih</strong> let, "
            "v Rečici ob Savinji pa je bil hladen padavinski dan med 24. in 26. decembrom v dveh od sedmih. "
            "V štirih od sedmih let je temperatura v teh treh dneh dosegla vsaj 10 °C.")
    s1 = [
        "<strong>Kratek odgovor:</strong> v dolini je bel božič redek, na Črnivcu (848 m) je bil v dveh od petih let. Rečica snežne odeje ne meri, zato za dolino uporabljam približek, za višje lege pa izmerjene podatke ARSO s Črnivca. Obeh številk ne smete neposredno primerjati: merita različni stvari.",
        tl,
        tbl,
    ]
    s2 = [
        "Božič 2025 je bil najbolj zimski: od 24. do 26. decembra 2025 je v Rečici padlo skupaj 13,5 mm padavin, najvišja dnevna temperatura pa je bila med 1,5 in 2,5 °C, najnižja med –0,3 in –0,2 °C. "
        "Na Črnivcu je ARSO izmeril snežno odejo: 4 cm na sveti večer, 15 cm na božič in 12 cm na štefanovo.",
        "Leta 2024 je bila slika drugačna: na Črnivcu je 24. decembra ležalo 14 cm snega, v dolini pa je bilo suho in hladno (najnižja dnevna temperatura je od 24. do 26. decembra padla z 2,4 °C na –7,3 °C). "
        "Za dolino je to pomenilo mraz brez snega, za višje lege bel božič.",
        "Med najtoplejšimi so bili božiči 2019, 2022 in 2023, ko se je temperatura čez dan dvignila na 11–14 °C. Takrat sneg ni bil blizu.",
    ]
    s3 = [
        "Za napoved božiča je še prezgodaj, tudi za modele. Nobeden vir danes ne more zanesljivo napovedati, ali bo 25. decembra sneg. "
        "Splošni sezonski signal za zimo 2026/27 sem opisal v članku " + a("/blog/zima-2026-2027-el-nino-napoved.html", "o El Niñu") +
        ": kaže na nadpovprečno toplo zimo, kar snegu v dolini ne daje prednosti. Najbližji lokalni analog, zima 2023/24, je bil topel in mokar.",
        "Smiselno je spremljati napoved približno teden dni pred božičem. Takrat bodo uporabni " + a("/zima/meja-snezenja/", "meja sneženja") + ", " + a("/zima/snezna-odeja/", "ocena snežne odeje") +
        " in " + a("/zima/snezna-karta/", "snežna karta") + ".",
        "Za primerjavo z daljšimi nizi: v Ljubljani so se ledeni dnevi in snežna odeja v zadnjih desetletjih močno zmanjšali, kot sem pokazal v članku "
        + a("/blog/zime-nekoc-in-zdaj-1012.html", "So zime še takšne, kot so bile nekoč") + ".",
    ]
    s4 = [
        ul([
            "<strong>Sedem božičev je malo</strong> za oceno verjetnosti. Podatki kažejo, kaj se je dogajalo, ne kaj se bo.",
            "<strong>Hladen padavinski dan ni sneg.</strong> Če je bila temperatura okoli 1 °C, je lahko padal tudi dež s snegom.",
            "<strong>Črnivec ni dolina.</strong> Arhiv ARSO imam od aprila 2021, zato sta v primerjavi samo dva božiča s snegom in tri brez.",
            "<strong>Bel božič nima enotne definicije.</strong> Tu štejem snežno odejo (Črnivec) ali hladne padavine (Rečica), ne snega, ki je padel in se stopil.",
        ]),
        USE_NOTE,
    ]
    title = "Bel božič v Savinjski dolini: kako pogost je?"
    desc = "Na Črnivcu je bil sneg na božič v 2 od 5 let, v Rečici je bil hladen padavinski dan v 2 od 7. Podatki postaje in ARSO za zadnje božiče."
    return dict(
        slug="bela-bozic-zgornja-savinjska-dolina-1027", title=title, desc=desc, og_title="Bel božič\nv Savinjski dolini",
        tags=["bel božič", "božič", "sneg", "zima", "podatki"], og_photo="misty-valley", accent="#22d3ee", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Bel božič: v dolini redek, na Črnivcu v dveh od petih let", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — primeri", "heading": "Trije božiči, tri različne zgodbe", "id": "primeri", "paragraphs": s2},
            {"label": "03 — letos", "heading": "Ali bo letos bel božič?", "id": "letos", "paragraphs": s3},
            {"label": "04 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": s4},
        ],
        sources="Viri: postaja IREICA1 (temperatura in padavine 24.–26. 12. za leta 2019–2025); padavinska postaja ARSO Črnivec (848 m, snežna odeja, arhiv od aprila 2021).")


# ───────────────────────── 5. žled ali poledica ─────────────────────────

def zled_schema():
    w, h = 460, 210
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Shema nastanka žleda: topla plast v višini, hladna plast pri tleh, dež zmrzne ob stiku s tlemi" xmlns="http://www.w3.org/2000/svg">']
    p.append(f'<rect x="20" y="14" width="300" height="46" rx="6" fill="{GREY}" fill-opacity=".25"/>')
    p.append(f'<text x="30" y="34" font-size="11.5" font-weight="700" fill="{INK}">oblak, padavine</text>')
    p.append(f'<text x="30" y="50" font-size="10.5" fill="{MUTED}">sneg ali dež</text>')
    p.append(f'<rect x="20" y="64" width="300" height="52" rx="6" fill="{AMBER}" fill-opacity=".22" stroke="{AMBER}" stroke-width="1"/>')
    p.append(f'<text x="30" y="84" font-size="11.5" font-weight="700" fill="{INK}">topla plast (nad 0 °C)</text>')
    p.append(f'<text x="30" y="101" font-size="10.5" fill="{MUTED}">sneg se stopi v dež</text>')
    p.append(f'<rect x="20" y="120" width="300" height="52" rx="6" fill="{CYAN}" fill-opacity=".22" stroke="{CYAN}" stroke-width="1"/>')
    p.append(f'<text x="30" y="140" font-size="11.5" font-weight="700" fill="{INK}">hladna plast pri tleh (0 °C ali manj)</text>')
    p.append(f'<text x="30" y="157" font-size="10.5" fill="{MUTED}">kaplje se podhladijo</text>')
    p.append(f'<rect x="20" y="176" width="300" height="12" rx="3" fill="{INK}" fill-opacity=".8"/>')
    p.append(f'<text x="330" y="186" font-size="10.5" font-weight="700" fill="{INK}">tla: ledena skorja</text>')
    for x in (200, 240, 280):
        p.append(f'<line x1="{x}" x2="{x}" y1="22" y2="172" stroke="{INK}" stroke-opacity=".5" stroke-width="1.4" stroke-dasharray="2 5"/>')
    p.append(f'<text x="330" y="94" font-size="10.5" fill="{MUTED}">ni ledu v zraku</text>')
    p.append(f'<text x="330" y="150" font-size="10.5" fill="{MUTED}">tekoči dež, ki</text><text x="330" y="164" font-size="10.5" fill="{MUTED}">zmrzne ob stiku</text>')
    p.append("</svg>")
    return "".join(p)


def art_zled(c):
    fr = c.W["freezing_rain"]
    assert fr["level"] == "nizko" and all(x["level"] == "nizko" for x in fr["daily"]), "žled: modelski posnetek se je spremenil"
    tbl = table(["", "Žled", "Poledica"],
                [["Kaj je", "Dež ali pršenje, ki zmrzne ob stiku s površino", "Led na cestišču ali poti, ki ga povzroči kateri koli vzrok"],
                 ["Vzrok", "Topla plast v višini nad hladnim zrakom pri tleh", "Ohladitev površine pod 0 °C: jasna noč, mraz, zmrznjena mokra cesta"],
                 ["Padavine", "Da, dež ali pršenje", "Ni nujno; vreme je lahko suho"],
                 ["Posledica zunaj ceste", "Ledena skorja na vejah, žicah in avtomobilih", "Običajno samo tla in mostovi"],
                 ["Pri nas", a("/zima/zled/", "Žled"), a("/zima/poledica/", "Poledica")]],
                "Primerjava žleda in poledice")
    lead = ("Žled in poledica imata podobno posledico, drsno površino, a nastaneta drugače. "
            "<strong>Žled je dež, ki zmrzne ob stiku s hladnimi tlemi</strong>, poledica pa je led na cesti ali poti, ki lahko nastane tudi brez dežja, na primer ob jasni noči po mokrem dnevu. "
            "Žled je redkejši, a zaradi njega lahko ostanejo brez elektrike cela naselja in cestišča postanejo neprevozna.")
    s1 = [
        "<strong>Kratek odgovor:</strong> žled je pojav v ozračju (podhlajen dež), poledica je stanje površine. Žled povzroči poledico, poledica pa ni nujno žled.",
        tbl,
    ]
    s2 = [
        zled_schema() and fig("Kako nastane žled", zled_schema(),
                             "Sneg v oblaku se na poti navzdol stopi v topli plasti, nato pa dež pada v plast zraka s temperaturo 0 °C ali manj. Kaplje se podhladijo in zmrznejo šele ob stiku s tlemi ali predmeti."),
        "Žled nastane, kadar je v višini toplejša plast zraka (nad 0 °C), pri tleh pa hladnejša (0 °C ali manj). Kaplje skozi hladno plast padejo prehitro, da bi zmrznile v zraku. "
        "Zmrznejo šele, ko zadenejo tla, žico ali vejo, in tam naredijo prozorno ledeno skorjo.",
        "Taka razporeditev je mogoča, kadar se topel zrak pomika nad dolino, v kateri se je zadržal mrzel zrak. Žled je kljub temu redek pojav.",
        "Modelski pokazatelj na strani " + a("/zima/zled/", "Žled") + " označi uro kot možen žled, kadar so hkrati izpolnjeni trije pogoji: temperatura pri tleh 0 °C ali manj, "
        "temperatura vsaj 0,5 °C na višini 925 ali 850 hPa in vsaj 0,1 mm padavin na uro. Od 0,5 mm na uro naprej je tveganje označeno kot visoko.",
    ]
    s3 = [
        "Žled je nevaren, ker ne povzroča samo drsnih cest. Led obtežuje veje in žice. Konec januarja in v začetku februarja 2014 je žled prekril velik del Slovenije in povzročil obsežno škodo na gozdovih in električnem omrežju.",
        "Poledica je pogostejša od žleda. Pojavlja se tam, kjer se cesta najhitreje ohladi: na mostovih, v senčnih odsekih, ob gozdu in v mraziščih. Sevalno ohlajanje je pogost razlog, da je poledica možna že pri pozitivni temperaturi zraka.",
    ]
    s4 = [
        ul([
            "<strong>Žled:</strong> dež pada, ko je zunaj okoli 0 °C ali manj, površine se bleščijo kot steklo, veje in avtomobili so prekriti z ledom. Če je zunaj žled, se vožnji izognite. Nevarna je že hoja po dvorišču.",
            "<strong>Poledica:</strong> vreme je suho ali vlažno, jutro pa jasno, zrak pri tleh pa blizu ničle. Cesta je lahko drsna, čeprav je temperatura zraka nad 0 °C. Mostovi zmrznejo prej kot cesta.",
            "<strong>Če pride do nesreče</strong> ali nevarnega stanja na cesti, pokličite 112.",
        ]),
    ]
    s5 = [
        f"Modelski posnetek (izračun {fr['generated_at_local']}): raven možnosti žleda je za vseh sedem dni <strong>nizka</strong>, nobena ura ne izpolnjuje vseh treh pogojev. "
        "Posnetek se vsak dan spremeni, zato za sprotno sliko odprite " + a("/zima/zled/", "stran Žled") + ".",
        "Za poledico je namenjena stran " + a("/zima/poledica/", "Poledica") + ", za razmere na prelazih pa " + a("/zima/prevoznost-prelazov/", "Prevoznost prelazov") + ".",
    ]
    s6 = [
        ul([
            "<strong>Modelski pokazatelj ni napoved žleda.</strong> Ne pove debeline ledu in ne zajame lokalnih razlik v dolini. Za uradna opozorila spremljajte " + a("https://vreme.arso.gov.si/napoved", "ARSO") + ".",
            "<strong>Brez meritve.</strong> Postaja v Rečici ne razlikuje dežja od podhlajenega dežja, zato v članku ne štejem zgodovinskih primerov žleda.",
            "<strong>Žledolom leta 2014 omenjam le kot ozadje.</strong> Podrobnosti in obseg škode so v uradnih poročilih, ki jih nisem povzemal.",
        ]),
        USE_NOTE,
    ]
    title = "Žled ali poledica: kakšna je razlika?"
    desc = "Žled je dež, ki zmrzne ob stiku s tlemi, poledica pa led na cesti. Kako nastaneta, kako ju ločiti in kje spremljati razmere v Savinjski dolini."
    return dict(
        slug="zled-ali-poledica-razlika-1027", title=title, desc=desc, og_title="Žled ali poledica:\nkakšna je razlika?",
        tags=["žled", "poledica", "zima", "led", "pojasnilo"], og_photo="rain-overcast", accent="#22d3ee", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Žled je pojav, poledica je stanje", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — nastanek", "heading": "Kako nastane žled", "id": "nastanek", "paragraphs": s2},
            {"label": "03 — nevarnost", "heading": "Zakaj je nevaren", "id": "nevarnost", "paragraphs": s3},
            {"label": "04 — na terenu", "heading": "Kako ju ločite", "id": "teren", "paragraphs": s4},
            {"label": "05 — zdaj", "heading": "Kaj kaže modelski pokazatelj danes", "id": "zdaj", "paragraphs": s5},
            {"label": "06 — omejitve", "heading": "Česa članek ne pove", "id": "omejitve", "paragraphs": s6},
        ],
        sources="Viri: pogoji pokazatelja žleda iz modela Open-Meteo (strani /zima/zled/), modelski posnetek z dne 27. 10. 2026. Splošna razlaga pojavov je avtorjeva; podatkov o zgodovini žleda v Rečici ni.")


# ───────────────────────── 6. Črnivec pozimi ─────────────────────────

def art_crnivec(c):
    WY = list(range(2021, 2026))
    fs = {y: crn_first_snow(c, y) for y in WY}
    cover = {}
    mxs = {}
    newsn = {}
    last_cover = {}
    for y in WY:
        w = crn_winter(c, y)
        cover[y] = sum(1 for r in w if r[1] and r[1] > 0)
        mxs[y] = max(w, key=lambda r: r[1] or 0)
        newsn[y] = round(sum(r[2] or 0 for r in w))
        last_cover[y] = D(max(r[0] for r in w if r[1] and r[1] > 0))
    assert cover == {2021: 30, 2022: 57, 2023: 22, 2024: 27, 2025: 32}, cover
    assert {y: (mxs[y][1], mxs[y][0]) for y in WY} == {2021: (25.0, "2021-11-29"), 2022: (65.0, "2023-01-24"), 2023: (23.0, "2024-01-20"), 2024: (25.0, "2025-02-14"), 2025: (19.0, "2026-01-07")}
    assert newsn == {2021: 102, 2022: 175, 2023: 79, 2024: 97, 2025: 86}, newsn
    med = statistics.median(cover.values())
    assert med == 30
    # delež dni s snežno odejo po mesecih (vsi dnevi z zapisom v zimah 2021/22-2025/26)
    mons = (11, 12, 1, 2, 3, 4)
    tot = {m: 0 for m in mons}
    snow = {m: 0 for m in mons}
    for y in WY:
        for r in crn_winter(c, y):
            m = D(r[0]).month
            if m in mons:
                tot[m] += 1
                snow[m] += 1 if (r[1] and r[1] > 0) else 0
    assert all(snow[m] == v for m, v in zip(mons, (17, 48, 43, 38, 11, 11))), snow
    share = {m: pct(snow[m], tot[m]) for m in mons}
    assert (share[12], share[1], share[2]) == (31, 28, 27) and share[3] <= 11 and share[4] <= 11, share
    assert not any(D(r[0]).month in (5, 6, 7, 8, 9, 10) and r[1] and r[1] > 0 for y in WY for r in crn_winter(c, y))

    rows = [(f"{y}/{str(y + 1)[2:]}", False, [(fs[y], CYAN, f"{y}/{str(y + 1)[2:]}: prvi nov sneg, {dm(fs[y])}", "up")]) for y in WY]
    f_first = fig("Prvi nov sneg na Črnivcu (848 m)",
                  dots_chart(rows, datetime.date(2001, 11, 10), datetime.date(2001, 12, 5),
                             [datetime.date(2001, 11, 15), datetime.date(2001, 11, 20), datetime.date(2001, 11, 25), datetime.date(2001, 11, 30)],
                             "Datum prvega novega snega na Črnivcu po zimah", rowh=34),
                  "Vsaka pika je prvi dan v zimi, ko je padavinska postaja ARSO Črnivec izmerila nov sneg. Podatki so za pet zim, od 2021/22 do 2025/26.")
    f_months = fig("Delež dni s snežno odejo po mesecih",
                   bars_chart(["nov.", "dec.", "jan.", "feb.", "mar.", "apr."], [("delež dni", CYAN, [share[m] for m in mons])], 50,
                              "Delež dni s snežno odejo na Črnivcu po mesecih", ticks=[0, 25, 50], fmt=lambda v: f"{v:.0f} %".replace(" ", NBSP), hl=1),
                   "Delež dni v mesecu, ko je na postaji Črnivec ležalo vsaj nekaj snega. Sešteti so vsi dnevi zim od 2021/22 do 2025/26. V oktobru in maju snega v teh petih zimah ni bilo.")
    t_tiles = tiles([
        ("18.–30. 11.", "", "izmerjen prvi nov sneg v petih zimah.", False),
        ("22–57", "dni", f"snežne odeje v zimi (mediana {int(med)} dni). Najdlje je ležala pozimi 2022/23.", False),
        ("65", "cm", "največja izmerjena višina snega: 24. januarja 2023.", True),
    ])
    lead = ("Na Črnivcu, na 848 m, je ARSO v petih zimah prvi nov sneg izmeril med <strong>18. in 30. novembrom</strong>. "
            "Snežne odeje je bilo v zimi 22–57 dni, največ snega pa je ležalo 24. januarja 2023: 65 cm. "
            "Zimske razmere na prelazu torej običajno nastopijo ob koncu novembra, najbolj zanesljivo pa trajajo od decembra do februarja.")
    s1 = [
        "<strong>Kratek odgovor:</strong> na Črnivcu sneg v petih zimah ni padel pred 18. novembrom, v oktobru pa ga sploh ni bilo. Najbolj zasnežen je december (31 % dni s snežno odejo), nato januar (28 %) in februar (27 %). Marca in aprila je odeja redka.",
        t_tiles, f_first,
    ]
    s2 = [
        f_months,
        f"Zime se močno razlikujejo. Pozimi 2022/23 je odeja ležala {cover[2022]} dni in pozimi 2023/24 le {cover[2023]} dni. Skupni nov sneg v zimi (seštevek dnevnih meritev ARSO) je od {min(newsn.values())} do {max(newsn.values())} cm.",
        "Največja višina snega je bila v štirih zimah 19–25 cm, v eni pa 65 cm, torej so velike odeje redke.",
    ]
    s3 = [
        "Prelaz Črnivec leži okoli 900 m, torej nekoliko više kot padavinska postaja. Temperatura je tam običajno nižja kot v dolini, zato se sneg začne in obleži prej.",
        ul([
            "Zimska oprema je v Sloveniji obvezna od 15. novembra do 15. marca, ob snegu in ledu pa tudi zunaj tega obdobja. Verige morate imeti s seboj ali namestiti tam, kjer to določa prometni znak ali stanje na cesti. Natančna pravila preverite pri AMZS ali v predpisih.",
            "Stanje ceste in zapore: " + a("https://www.promet.si/", "promet.si") + ". To je uradni vir; moji podatki so informativni.",
            "Izmerjena temperatura na prelazu, ocena vozišča in kamera: " + a("https://crnivec.si/", "crnivec.si") + ". Temperatura in veter sta izmerjena na postaji DRSI na prelazu, stanje vozišča pa je ocena in ne meritev.",
            "Pregled prelazov v regiji: " + a("/zima/prevoznost-prelazov/", "Prevoznost prelazov") + ".",
        ]),
    ]
    s4 = [
        ul([
            "<strong>Pet zim je malo.</strong> Postaja ARSO Črnivec ima podatke od aprila 2021, zato ne vem, kako običajne so te zime v daljšem obdobju.",
            "<strong>Postaja ni prelaz.</strong> Padavinska postaja ARSO stoji na 848 m, prelaz je okoli 900 m. Na prelazu lahko leži več ali manj snega, kot ga izmeri postaja.",
            "<strong>Arhiv zaostaja.</strong> Arhiv ARSO zaostaja za nekaj tednov (zadnji vnos v mojem zapisu je 30. 9. 2026), zato letošnje zime še ni v podatkih.",
            "<strong>Snežna odeja ni prevoznost.</strong> Cesta je lahko očiščena, čeprav sneg leži ob robu, ali drsna, čeprav snega ni. Odločitev o poti naj temelji na uradnih podatkih.",
        ]),
        USE_NOTE,
    ]
    title = "Črnivec pozimi: kdaj sneg, kdaj verige"
    desc = "Na Črnivcu (848 m) je prvi sneg v petih zimah padel med 18. in 30. novembrom. Snežna odeja, razmere in kje preveriti stanje ceste."
    return dict(
        slug="crnivec-pozimi-sneg-verige-1027", title=title, desc=desc, og_title="Črnivec pozimi:\nkdaj sneg, kdaj verige",
        tags=["Črnivec", "sneg", "verige", "prelaz", "zima"], og_photo="misty-valley", accent="#22d3ee", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Sneg na Črnivcu: od konca novembra do februarja", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — zime", "heading": "Koliko snega in koliko dni", "id": "zime", "paragraphs": s2},
            {"label": "03 — praktično", "heading": "Kje preveriti stanje pred vožnjo", "id": "prakticno", "paragraphs": s3},
            {"label": "04 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": s4},
        ],
        sources="Viri: padavinska postaja ARSO Črnivec (id 3391, 848 m; dnevna višina snežne odeje, nov sneg; arhiv do 30. 9. 2026). Pravila o zimski opremi: AMZS. Živi podatki: DRSI prek crnivec.si, promet.si.")


# ───────────────────────── 7. prvi sneg v hribih ─────────────────────────

def art_hribi(c):
    crn = {y: crn_first_snow(c, y) for y in range(2021, 2026)}
    assert min(map(_ref, crn.values())) == datetime.date(2001, 11, 18) and max(map(_ref, crn.values())) == datetime.date(2001, 11, 30)
    sl = c.W["snow_line"]
    assert sl["daily"][0]["line_m"] == 2660 and sl["daily"][-1]["line_m"] == 1210
    peaks = {p["name"]: p for p in c.W["mountains"]["peaks"]}
    rows = []
    for nm in ("Golte", "Menina planina", "Smrekovec", "Raduha"):
        p = peaks[nm]
        ds = [x for x in p["daily"] if "2026-10-27" <= x["date"] <= "2026-10-31"]
        assert len(ds) == 5
        rows.append([nm, f"{p['elevation_m']} m", temp(min(x["tmin_c"] for x in ds)), f"{num(sum(x['snow_cm'] for x in ds))} cm"])
    assert rows[0][2] == temp(-5.0) and rows[0][3] == "1,3 cm"
    tbl = table(["Vrh", "Višina", "Najnižja temperatura 27.–31. 10.", "Pričakovan nov sneg 27.–31. 10."], rows,
                "Modelska ocena za višje lege od 27. do 31. oktobra 2026",
                "Modelski posnetek z dne 27. oktobra (Open-Meteo), temperatura na višini je preračunana iz doline z gradientom. To ni meritev in ni uradna gorska napoved.")
    be = {b["elevation_m"]: b["new_snow_7d_cm"] for b in c.W["snowpack"]["by_elevation"]}
    assert be == {366: 0.0, 600: 0.0, 900: 0.0, 1200: 0.7, 1600: 3.3}, be
    tl = tiles([
        ("1210", "m", "višina, na katero naj bi se do 2. novembra spustila meja sneženja (27. oktobra je bila na 2660 m).", False),
        ("1,3", "cm", "novega snega na Goltah 31. oktobra po modelu.", False),
        ("0", "cm", "novega snega do 900 m v naslednjih sedmih dneh.", True),
    ])
    lead = ("Sneg v hribih nad Zgornjo Savinjsko dolino se približuje: model za <strong>31. oktobra</strong> napoveduje prve centimetre na Goltah (1,3 cm), "
            "meja sneženja pa naj bi se do 2. novembra spustila z 2660 na 1210 m. Do 900 m, tudi v Solčavi in Logarski dolini, model v naslednjem tednu ne napoveduje snega. "
            "Na najbližji izmerjeni točki, Črnivcu (848 m), je ARSO prvi nov sneg v petih zimah izmeril med 18. in 30. novembrom.")
    s1 = [
        "<strong>Kratek odgovor:</strong> prvi sneg na Goltah in Menini planini je po modelu pričakovan v zadnjih dneh oktobra ali v začetku novembra. Za Solčavo (644 m) in Logarsko dolino (okoli 800 m) nimam izmerjenega datuma prvega snega. Ležita nekoliko nižje od Črnivca, zato bi lahko pričakovali podobne ali nekoliko poznejše datume (Črnivec: 18.–30. 11.), a to je sklep, ne meritev.",
        tl,
        tbl,
    ]
    s2 = [
        "Za višje lege nimam izmerjenih podatkov. Najbližja izmerjena točka je padavinska postaja ARSO Črnivec na 848 m. Prvi nov sneg so tam izmerili 18. novembra 2025, "
        f"22. novembra 2024, 23. novembra 2022, 27. novembra 2021 in 30. novembra 2023.",
        "Golte in Menina planina ležijo na 1400 m in več, zato sneg tam običajno pride prej kot na Črnivcu. Koliko prej, iz teh meritev ne vem, zato ne trdim številk.",
        "Meja sneženja je približek: višina ničte izoterme, zmanjšana za 250 m. Kaže, kje bi dež prešel v sneg, ne pove pa, ali bo sneg obležal.",
    ]
    s3 = [
        ul([
            "<strong>Golte:</strong> o obratovanju smučišča in stanju prog se pozanimajte pri upravljavcu. Iz teh podatkov tega ne morem reči.",
            "<strong>Veter in občutek mraza:</strong> na grebenu je hladneje, kot kaže temperatura zraka. Ocene so na strani " + a("/vreme-v-gorah/", "Vreme v gorah") + ".",
            "<strong>Solčava in Logarska dolina:</strong> sproti spremljajte " + a("/vreme-solcava/", "vreme v Solčavi") + " in " + a("/zima/snezna-karta/", "snežno karto") + ".",
            "<strong>Za osnove:</strong> razlago razmer na Goltah najdete v članku " + a("/blog/vreme-golte-sneg-razmere.html", "Vreme na Golteh") + ".",
        ]),
    ]
    s4 = [
        ul([
            "<strong>Modelski posnetek.</strong> Podatki so z dne 27. oktobra in se vsak dan spremenijo. Za sprotno stanje glejte " + a("/zima/meja-snezenja/", "mejo sneženja") + ".",
            "<strong>Brez meritev na višini.</strong> Temperature na Goltah in drugih vrhovih so preračunane iz doline. Ne pomenijo, da je tam res tako hladno.",
            "<strong>Ni uradna gorska napoved.</strong> Za razmere v gorah in nevarnost snega spremljajte ARSO in lokalne službe.",
        ]),
        USE_NOTE,
    ]
    title = "Prvi sneg na Goltah in v Solčavi: kdaj ga pričakovati"
    desc = "Model za 31. oktobra napoveduje prvi sneg na Goltah (1,3 cm). Za Solčavo ni meritev; na Črnivcu je prvi sneg padel med 18. in 30. novembrom."
    return dict(
        slug="prvi-sneg-golte-solcava-menina-1027", title=title, desc=desc, og_title="Prvi sneg na Goltah\nin v Solčavi",
        tags=["Golte", "Solčava", "Logarska dolina", "sneg", "zima"], og_photo="misty-valley", accent="#22d3ee", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Prvi sneg v hribih: najprej na Goltah", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — meritve", "heading": "Kaj vemo iz meritev", "id": "meritve", "paragraphs": s2},
            {"label": "03 — praktično", "heading": "Kaj lahko spremljate", "id": "prakticno", "paragraphs": s3},
            {"label": "04 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": s4},
        ],
        sources="Viri: padavinska postaja ARSO Črnivec (848 m, arhiv do 30. 9. 2026); modelski posnetek Open-Meteo z dne 27. 10. 2026 (meja sneženja, ocena za višje lege).")


# ───────────────────────── 8. stopinjski dnevi ─────────────────────────

def hdd(c, d, base=12.0, room=20.0):
    t = c.val(d, "tempAvg")
    return None if t is None else (room - t if t < base else 0.0)


def art_hdd(c):
    S = list(range(2020, 2025))
    season = {}
    month = {}
    heat_days = {}
    for y in S + [2025]:
        ds = [d for d in c.days(datetime.date(y, 10, 1), datetime.date(y + 1, 4, 30)) if c.val(d, "tempAvg") is not None]
        season[y] = round(sum(hdd(c, d) for d in ds))
        heat_days[y] = sum(1 for d in ds if c.val(d, "tempAvg") < 12)
        month[y] = {m: sum(hdd(c, d) for d in ds if D(d).month == m) for m in (10, 11, 12, 1, 2, 3, 4)}
    assert [season[y] for y in S] == [3156, 3281, 2781, 2565, 2817], season
    assert season[2025] == 2877
    mean5 = round(statistics.mean(season[y] for y in S))
    assert mean5 == 2920
    spread = round(100 * (max(season[y] for y in S) / min(season[y] for y in S) - 1))
    assert spread == 28
    oct26 = {y: round(sum(hdd(c, d) for d in c.days(datetime.date(y, 10, 1), datetime.date(y, 10, 26)))) for y in range(2020, 2027)}
    assert oct26 == {2020: 171, 2021: 234, 2022: 63, 2023: 53, 2024: 132, 2025: 239, 2026: 212}, oct26
    rank = 1 + sum(1 for y in range(2020, 2026) if oct26[y] > oct26[2026])
    assert rank == 3
    mavg = {m: round(statistics.mean(month[y][m] for y in S)) for m in (10, 11, 12, 1, 2, 3, 4)}

    cats = [f"{y}/{str(y + 1)[2:]}" for y in S]
    f_season = fig("Stopinjski dnevi po kurilnih sezonah (1. 10.–30. 4.)",
                   bars_chart(cats, [("stopinjski dnevi", CYAN, [season[y] for y in S])], 3500, "Stopinjski dnevi po kurilnih sezonah v Rečici",
                              ticks=[0, 1000, 2000, 3000], hl=1, w=460),
                   "Za vsak dan s povprečno temperaturo pod 12 °C sem seštel razliko do 20 °C. Povprečje petih sezon je 2920, najtoplejša je bila 2023/24 (2565), najhladnejša 2021/22 (3281).")
    mons = (10, 11, 12, 1, 2, 3, 4)
    f_mon = fig("Povprečni stopinjski dnevi po mesecih",
                bars_chart(["okt.", "nov.", "dec.", "jan.", "feb.", "mar.", "apr."], [("stopinjski dnevi", AMBER, [mavg[m] for m in mons])], 700,
                           "Povprečni stopinjski dnevi po mesecih kurilne sezone v Rečici", ticks=[0, 350, 700]),
                "Povprečje petih sezon od 2020/21 do 2024/25. Največ ogrevanja pade na december in januar.")
    ex = round(100 * (season[2021] / season[2024] - 1))
    assert ex == 16
    t_tiles = tiles([
        ("2920", "", "povprečno število stopinjskih dni v petih kurilnih sezonah v Rečici.", False),
        ("28", "%", "več stopinjskih dni je imela najhladnejša sezona (3281) kot najtoplejša (2565).", False),
        ("3. od 7", "", "po hladnosti: letošnji oktober do 26. 10. (212 stopinjskih dni). Hladnejša sta bila le 2025 (239) in 2021 (234).", True),
    ])
    lead = ("V zadnjih petih kurilnih sezonah (1. oktober–30. april) je Rečica imela v povprečju <strong>2920 stopinjskih dni</strong>, "
            "najhladnejša sezona (2021/22) jih je imela 28 % več kot najtoplejša (2023/24). "
            "Če je vaša poraba sorazmerna z ogrevanjem, takšno razliko med zimama opazite na računu ali na skladovnici drv.")
    s1 = [
        "<strong>Kratek odgovor:</strong> najhladnejša sezona je imela 28 % več stopinjskih dni kot najtoplejša. Največ ogrevanja je decembra in januarja, najmanj oktobra in aprila.",
        t_tiles, f_season,
    ]
    s2 = [
        "Stopinjski dnevi povedo, kako hladno je bilo. Uporabljam eno od običajnih definicij: za vsak dan s povprečno dnevno temperaturo pod 12 °C seštejem razliko do 20 °C. "
        "Dan s povprečno temperaturo 2 °C prispeva 18 stopinjskih dni, dan s povprečjem 13 °C nič.",
        "Mejna in sobna temperatura se po virih razlikujejo, zato moji izračuni niso primerni za obračun toplote. Za račune veljajo pravila vašega distributerja oziroma upravljavca.",
        f_mon,
    ]
    s3 = [
        "Če poznate lanskoletno porabo, jo lahko grobo prilagodite. Poraba je približno sorazmerna s številom stopinjskih dni: "
        f"<strong>poraba letos ≈ poraba lani × (stopinjski dnevi letos / stopinjski dnevi lani)</strong>.",
        f"Primer, ne meritev: če ste v sezoni 2024/25 ({season[2024]} stopinjskih dni) porabili 10 enot, bi v sezoni, kakršna je bila 2021/22 ({season[2021]}), po tem računu porabili približno {num(10 * season[2021] / season[2024], 0)} enot, "
        f"torej {ex} % več.",
        "Račun velja le, če se hiša, način ogrevanja in navade niso spremenili. Je grob: poraba ni natančno sorazmerna z vremenom.",
        f"Od 1. do 26. oktobra je letos nabralo {oct26[2026]} stopinjskih dni. To je tretji najhladnejši oktober od sedmih (2020–2026); hladnejša sta bila 2025 ({oct26[2025]}) in 2021 ({oct26[2021]}). "
        "Oktober je majhen del sezone, zato iz njega ne morem sklepati o vsej zimi.",
    ]
    s4 = [
        "Vprašanje, kdaj kuriti, je drugo: pri temperaturni inverziji dim ostane v dolini. Dnevno oceno prevetrenosti za Zgornjo Savinjsko dolino pokaže " + a("/zima/kurilni-semafor/", "kurilni semafor") + ".",
        "Splošna slika za zimo 2026/27 (topla ali hladna) je v članku " + a("/blog/zima-2026-2027-el-nino-napoved.html", "o El Niñu in zimi") + ".",
    ]
    s5 = [
        ul([
            "<strong>Pet popolnih sezon je malo.</strong> Postaja meri od novembra 2019, sezona 2019/20 je nepopolna, v sezoni 2025/26 pa manjkajo 4 dnevi od 212 (2877 stopinjskih dni), zato ni vključena v povprečje.",
            "<strong>Poraba ni samo vreme.</strong> Odvisna je od hiše, ogrevanja, števila ljudi doma in navad. Stopinjski dnevi pojasnijo le vreme, ne pa vsega.",
            "<strong>Definicija in meje so moja izbira.</strong> Za obračun toplote ali energetske izračune uporabite metodologijo, ki jo zahteva dobavitelj ali predpis.",
        ]),
        USE_NOTE,
    ]
    title = "Koliko kuriti? Stopinjski dnevi zadnjih zim v Rečici"
    desc = "V petih kurilnih sezonah je Rečica imela povprečno 2920 stopinjskih dni; najhladnejša zima jih je imela 28 % več kot najtoplejša."
    return dict(
        slug="stopinjski-dnevi-recica-koliko-kuriti-1027", title=title, desc=desc, og_title="Koliko kuriti?\nStopinjski dnevi Rečice",
        tags=["stopinjski dnevi", "kurjenje", "zima", "ogrevanje", "podatki"], og_photo="weather-station", accent="#fbbf24", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Zime se po ogrevanju razlikujejo za več kot četrtino", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — metoda", "heading": "Kaj je stopinjski dan", "id": "metoda", "paragraphs": s2},
            {"label": "03 — račun", "heading": "Kako ocenite letošnjo porabo", "id": "racun", "paragraphs": s3},
            {"label": "04 — kurjenje", "heading": "Kdaj kuriti in kdaj počakati", "id": "kurjenje", "paragraphs": s4},
            {"label": "05 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": s5},
        ],
        sources="Viri: postaja IREICA1 (povprečna dnevna temperatura zunanjega senzorja, kurilne sezone 1. 10.–30. 4. od 2020/21 do 2024/25; 2025/26 za primerjavo).")


# ───────────────────────── 9. jutranja megla ─────────────────────────

def art_megla(c):
    by = {}
    for r in c.hourly:
        t = datetime.datetime.fromisoformat(r["valid_at_local"])
        by.setdefault(t.date(), {})[t.hour] = r
    sat = lambda r: float(r["temp_c"]) - float(r["dewpoint_c"]) <= 0.5
    mon = {7: [], 8: [], 9: [], 10: []}
    for d, h in sorted(by.items()):
        if len(h) < 22 or d.month not in mon or 7 not in h or 5 not in h:
            continue
        at7 = sat(h[7]) and float(h[7]["wind_kmh"] or 0) < 3
        last = None
        if sat(h[5]):
            hr = 5
            while hr + 1 <= 12 and hr + 1 in h and sat(h[hr + 1]):
                hr += 1
            last = hr
        mon[d.month].append((d, at7, last))
    n = {m: len(v) for m, v in mon.items()}
    k = {m: sum(1 for x in v if x[1]) for m, v in mon.items()}
    assert n == {7: 19, 8: 30, 9: 28, 10: 25} and k == {7: 6, 8: 12, 9: 27, 10: 23}, (n, k)
    med = {m: statistics.median([x[2] for x in v if x[1] and x[2] is not None]) for m, v in mon.items()}
    assert med == {7: 7, 8: 7.5, 9: 8, 10: 9}, med
    oct_lasts = sorted(x[2] for x in mon[10] if x[1] and x[2] is not None)
    assert oct_lasts[0] == 8 and oct_lasts[-1] == 12 and oct_lasts.count(12) == 2, oct_lasts
    inv = c.W["fog"]
    assert inv["morning_date"] == "2026-10-28" and inv["has_inversion"] and inv["top_m"] == 1528

    cats = ["jul.", "avg.", "sep.", "okt."]
    f_share = fig("Delež jutr z nasičenim zrakom ob 7. uri",
                  bars_chart(cats, [("delež", CYAN, [pct(k[m], n[m]) for m in (7, 8, 9, 10)])], 100, "Delež dni z nasičenim zrakom ob 7. uri po mesecih",
                             ticks=[0, 50, 100], fmt=lambda v: f"{v:.0f} %".replace(" ", NBSP)),
                  "Nasičen zrak: temperatura se od rosišča razlikuje za 0,5 °C ali manj ob mirnem vetru (pod 3 km/h). Julij je nepopoln (podatki od 13. 7.).")
    f_end = fig("Do katere ure je zrak ostal nasičen",
                bars_chart(cats, [("mediana", AMBER, [med[m] for m in (7, 8, 9, 10)])], 12, "Mediana zadnje ure z nasičenim zrakom po mesecih",
                           ticks=[0, 6, 12], fmt=lambda v: num(v, 1 if abs(v - round(v)) > .01 else 0)),
                "Mediana zadnje ure (do poldneva), ko je bil zrak še nasičen, na dneh z nasičenim zrakom ob 7. uri. Ura se nanaša na lokalni čas (po 25. oktobru je zimski čas).")
    t_tiles = tiles([
        ("92", "%", "oktobrskih jutr je imelo ob 7. uri nasičen zrak (23 od 25 dni).", False),
        ("9", "", "mediana zadnje ure z nasičenim zrakom v oktobru (julija 7).", False),
        ("2", "dni", "je bil zrak še ob 12. uri nasičen (9. in 24. oktobra). Merim samo do poldneva.", True),
    ])
    lead = ("Oktobra 2026 je bil zrak v Rečici ob 7. uri v <strong>23 od 25 dni</strong> nasičen z vlago (razlika med temperaturo in rosiščem 0,5 °C ali manj). "
            "Mediana ure, do katere je nasičenost trajala, se je od julija do oktobra pomaknila s 7. na 9. uro. "
            "Jutra z nasičenim zrakom se jeseni podaljšujejo; kako bo pozimi, urni zapis še ne pove.")
    s1 = [
        "<strong>Kratek odgovor:</strong> v oktobru se zrak v Rečici običajno posuši okoli 9. ali 10. ure. Izjemi sta bila 9. in 24. oktobra, ko je bil zrak nasičen še ob 12. uri.",
        "Pomembno: nasičen zrak ni nujno megla. To je pogoj za meglo ali roso, postaja pa vidljivosti ne meri. Če je zrak pri tleh nasičen in vreme mirno, je megla zelo verjetna, a to potrdi šele pogled skozi okno ali kamera.",
        t_tiles,
        f_share,
    ]
    s2 = [
        f_end,
        f"Od julija do oktobra je delež jutr z nasičenim zrakom ob 7. uri narasel z {pct(k[7], n[7])} % (julij) na {pct(k[8], n[8])} % (avgust), nato na {pct(k[9], n[9])} % (september) in {pct(k[10], n[10])} % (oktober). "
        "Pozneje se je tudi končala nasičenost: mediana zadnje nasičene ure je julija 7, avgusta 7 ali 8 (7,5), septembra 8 in oktobra 9.",
        "Razlogi so znani: noči so daljše, sonce je nižje in tla se zjutraj počasneje segrejejo. Natančnega deleža posameznih vzrokov iz teh podatkov ne morem oceniti.",
    ]
    s3 = [
        f"Če je nad dolino temperaturna inverzija, je nad plastjo megle pogosto jasno. Modelska ocena za jutro 28. oktobra 2026 kaže zgornjo mejo inverzije okoli {inv['top_m']} m: "
        "do te višine temperatura z višino ne pada. Smrekovec in Raduha ležita nad njo, Golte pa pod njo.",
        "Sprotno oceno vidite na strani " + a("/zima/nad-meglo/", "Nad meglo") + ", oceno prevetrenosti za kurjenje pa na " + a("/zima/kurilni-semafor/", "kurilnem semaforju") + ".",
        "Kako nastane inverzija, sem opisal v članku " + a("/blog/reke-megle-temperaturna-inverzija-recica-savinji.html", "Reke megle nad dolino") + ".",
    ]
    s4 = [
        ul([
            "<strong>Samo ena jesen.</strong> Urni zapis imam od 13. julija 2026. Zimskih mesecev v njem še ni, zato ne trdim, kdaj se megla dviguje pozimi.",
            "<strong>Nasičen zrak ni megla.</strong> Razlika med temperaturo in rosiščem 0,5 °C ali manj je približek, ki ga ugotavljam ob celih urah. Vidljivosti in debeline megle ne merim.",
            "<strong>Ena postaja.</strong> Postaja stoji na dnu doline. Na pobočjih in v višjih legah je lahko drugače.",
            "<strong>Modelska ocena inverzije je napoved.</strong> Ocena za jutro 28. oktobra velja na dan objave in se z novimi teki modela spreminja.",
        ]),
        USE_NOTE,
    ]
    title = "Kdaj se dvigne jutranja megla v dolini? Izmerjeno"
    desc = "Oktobra je bil zrak v Rečici ob 7. uri nasičen v 23 od 25 dni, nasičenost pa je običajno trajala do 9. ure. Urne meritve od julija."
    return dict(
        slug="kdaj-se-dvigne-jutranja-megla-dolina-1027", title=title, desc=desc, og_title="Kdaj se dvigne\njutranja megla?",
        tags=["megla", "inverzija", "dolina", "jesen", "podatki"], og_photo="night-fog-valley", accent="#22d3ee", lead=lead,
        sections=[
            {"label": "01 — odgovor", "heading": "Oktobra se zrak posuši okoli 9. ure", "id": "odgovor", "paragraphs": s1},
            {"label": "02 — spreminjanje", "heading": "Od julija do oktobra se jutra podaljšujejo", "id": "spreminjanje", "paragraphs": s2},
            {"label": "03 — nad meglo", "heading": "Kje je jasno, ko je v dolini megla", "id": "nadmeglo", "paragraphs": s3},
            {"label": "04 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": s4},
        ],
        sources="Viri: postaja IREICA1 (urni zapis temperature, rosišča in vetra zunanjega senzorja od 13. 7. do 26. 10. 2026); modelski posnetek Open-Meteo z dne 27. 10. 2026 (inverzija).")


# ───────────────────────── gradnja ─────────────────────────

ARTICLES = {f.__name__.replace("art_", ""): f for f in (art_gume, art_sneg, art_bozic, art_zled, art_crnivec, art_hribi, art_hdd, art_megla)}


def finalize(art):
    assert len(art["title"]) <= 60, (art["slug"], len(art["title"]))
    assert len(art["desc"]) <= 160, (art["slug"], len(art["desc"]))
    a_ = {
        "title": art["title"], "meta_description": art["desc"], "tags": art["tags"],
        "section_label": "Podatkovna analiza", "og_photo": art["og_photo"], "og_accent_hex": art["accent"],
        "lead": nb(art["lead"]), "callout": None, "sources_note": art["sources"],
        "sections": [dict(s, paragraphs=[nb(x) for x in s["paragraphs"]]) for s in art["sections"]],
    }
    return a_


def plain_text(article):
    def clean(h):
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"</(tr|li|p|div|h3|figcaption)>", "\n", h)
        h = re.sub(r"</t[dh]>", " | ", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace(NBSP, " ")
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        out += [clean(p) + "\n" for p in s["paragraphs"]]
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    args = sys.argv[1:]
    only = args[args.index("--only") + 1] if "--only" in args else None
    dry, wire, force = "--dry-run" in args, "--wire" in args, "--force" in args
    c = Ctx()
    for key, fn in ARTICLES.items():
        art = fn(c)
        if only and only not in (key, art["slug"]):
            continue
        article = finalize(art)
        slug = art["slug"]
        if "--text" in args or dry:
            txt = plain_text(article)
            if dry:
                print("=" * 100 + f"\n{slug}\n" + txt)
            else:
                open(os.path.join(ROOT, "docs", f"lektura-{key}.txt"), "w", encoding="utf-8").write(txt)
        if dry:
            continue
        path = os.path.join(ROOT, "blog", f"{slug}.html")
        if os.path.exists(path) and not force:
            print(f"blog/{slug}.html že obstaja -- brez ponovne objave (--force za prepis).")
            continue
        import generate_forecast_test_post as ftp
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        today = datetime.date.today()
        ftp.TODAY = today.isoformat()
        s_, html, entry, og_meta = ftp.build_html(
            article, today.year, today.month, now_utc, slug=slug, back=("/blog/", "← Vsi članki"),
            og_title=art["og_title"], meta_note="podatkovna analiza", nav_label="O postaji", nav_href="/o-postaji.html")
        lead = f'<p class="lead">{article["lead"]}</p>'
        assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
        html = html.replace(lead, STYLE + "\n" + lead, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✓ zapisano: blog/{slug}.html")
        if wire:
            try:
                from generate_og_images import make_og
                make_og({"slug": slug, **og_meta})
                print(f"✓ OG slika: og/{slug}.jpg")
            except Exception as e:  # noqa: BLE001
                print(f"⚠ OG slika preskočena: {e}")
            from generate_monthly_post import wire_all
            wire_all(entry, entry["url"])
            print("✓ wire_all: blog.json, blog/index.html, sitemap.xml, rss, teme, sorodni članki.")


if __name__ == "__main__":
    main()
