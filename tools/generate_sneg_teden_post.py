#!/usr/bin/env python3
"""
tools/generate_sneg_teden_post.py -- »Sneg prihodnji teden: v dolini kaže na sredo in četrtek« (21. 11. 2026).

Ročni podatkovni članek, nadaljevanje člankov z 9. in 12. 11. Vse številke so izračunane iz posnetka
data/sneg-teden-1121.json (prenese ga tools/sneg_teden_data.py: ansambli ECMWF ENS, ICON-EPS, GEFS, GEM ENS in
determinični modeli prek Open-Meteo, za Rečico na 366, 700, 1000 in 1400 m), iz napoved-modela.json (MTR),
napoved-snega.json (MTR sneg), arhiva ARSO za Gornji Grad (klimatologija prvega snega) in odčitkov ARSO.
Strukturo zgodbe varujejo assert-i: če se napoved obrne (npr. sneg v dolini ni več verjeten), generator pade --
članek je treba prenoviti, ne zaobiti asserta.

Članek je posnetek na dan objave. Postaja IREICA1 snega ne meri; notranjih meritev članek ne uporablja (glej CLAUDE.md).
Meja dež/sneg je naša poenostavitev (kot v članku z 9. 11.), 1 mm padavin = 1 cm snega.

Usage:
    python3 tools/sneg_teden_data.py                       # osveži posnetek (omrežje)
    python3 tools/generate_sneg_teden_post.py [--dry-run] [--text] [--wire] [--force]
"""
import csv
import datetime
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_slane_se_ni_post import STYLE as BASE_STYLE, num, fig, tiles  # noqa: E402  (skupni pomočniki, ne podvojeni)

STYLE = BASE_STYLE.replace("</style>", ".sg-m{fill:var(--muted)}.sg-i{fill:var(--text)}.sg-g{stroke:var(--card-border)}.sg-z{stroke:var(--text)}"
    ".tn-wrap{overflow-x:auto;margin:.2rem 0 .6rem}.tn-tbl{border-collapse:collapse;width:100%;min-width:440px;font-size:.9rem;font-variant-numeric:tabular-nums}"
    ".tn-tbl th,.tn-tbl td{padding:.45rem .6rem;border-bottom:1px solid var(--card-border);text-align:right;color:var(--text)}"
    ".tn-tbl th:first-child,.tn-tbl td:first-child{text-align:left}.tn-tbl th{font-weight:600;color:var(--muted);font-size:.8rem}"
    ".tn-tbl .tn-na{color:var(--muted)}.tn-photo-v{max-width:440px;margin-left:auto;margin-right:auto}</style>")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "sneg-teden-1121.json")
SLUG = "sneg-prihodnji-teden-sreda-cetrtek-1121"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-sneg-teden.txt")
NBSP = " "
LINK = 'style="color:var(--blue)"'
SNOW, MIX, RAIN = "#3987e5", "#9085e9", "#199e70"    # barve iz preverjene palete semaforja (isti kot v članku z 12. 11.)

DAYS = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
DAN_V = ["v ponedeljek", "v torek", "v sredo", "v četrtek", "v petek", "v soboto", "v nedeljo"]
MES_R = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra", "novembra", "decembra"]
START = datetime.datetime(2026, 11, 22, 0)
D = {n: f"2026-11-{n}" for n in range(22, 30)}   # D[25] = "2026-11-25"


# Fotografije so Filipove (Nikon D610, posneto 20. 1. 2019; originali ne gredo v repozitorij, v datotekah ni EXIF). Lokacije v podpisu ne navajam: ni znana.
# Niso posnete ta teden in to piše v podpisu (sicer bi bralec mislil, da prikazujejo napovedani sneg).
PHOTOS = {
    "road": ("foto-1.jpg", 880, 1318, "Cesta, prekrita s snegom, med zasnežennimi smrekami; v daljavi stoji oseba, nizko sonce obarva krošnje oranžno.",
             "Arhivska fotografija (20. 1. 2019), ilustracija: ne prikazuje letošnjega snega. Foto: Filip Eremita.", "tn-photo-v"),
    "lift": ("foto-2.jpg", 1400, 935, "Sedežnica in zasnežene smreke nad morjem megle ob sončnem zahodu, v ospredju sled smuči v sveži snežni odeji.",
             "Arhivska fotografija (20. 1. 2019): sneg nad meglenim morjem. Ilustracija, ne prikazuje letošnjega snega. Foto: Filip Eremita.", ""),
}


def photo(key):
    f, w, h, alt, cap, cls = PHOTOS[key]
    return (f'<figure class="post-photo{(" " + cls) if cls else ""}"><img src="/img/blog/{SLUG}/{f}" alt="{alt}" width="{w}" height="{h}" loading="lazy">'
            f'<figcaption>{cap}</figcaption></figure>')


def a(href, text):
    return f'<a href="{href}" {LINK}>{text}</a>'


def nbsp(s):
    return re.sub(r"(\d) (°C|%|mm|cm|m\b)", lambda m: m.group(1) + NBSP + m.group(2), s)


def temp(x, d=0):
    return f"{num(x, d)}{NBSP}°C".replace("-", "–")


def rnd(x):
    return int(x + 0.5)


def pc(x):
    return f"{int(x)}{NBSP}%"


def hour_in(h):
    """Ura v posnetku -> "2. uro v sredo" (za »med 2. uro v sredo in 1. uro v četrtek«)."""
    t = START + datetime.timedelta(hours=h)
    return f"{t.hour}. uro {DAN_V[t.weekday()]}"


def when(h):
    """Ura v posnetku (od nedelje 0.00) -> "v sredo ob 15. uri"."""
    t = START + datetime.timedelta(hours=h)
    return f"{DAN_V[t.weekday()]} ob {t.hour}. uri"


class Snap:
    def __init__(self):
        S = json.load(open(DATA, encoding="utf-8"))
        self.S = S
        self.fetched = datetime.datetime.fromisoformat(S["fetched_at"])
        assert self.fetched.date() == datetime.date.today(), f"posnetek je z dne {self.fetched.date()}; poženi tools/sneg_teden_data.py"
        assert S["start"] == START.isoformat(timespec="minutes") and S["n_hours"] == 192 and S["elevs"] == [366, 700, 1000, 1400]
        self.E = S["ens"]
        assert S["members"] == {"ecmwf_ifs025": 51, "icon_seamless": 40, "gfs025": 31, "gem_global": 21}
        self.n = sum(S["members"].values())

    def day(self, el, n):
        return self.E["days"][str(el)][D[n]]

    def win(self, el, key):
        return self.E["windows"][str(el)][key]

    def hourly(self, el):
        return self.E["hourly"][str(el)]


# ───────────────────────── grafi ─────────────────────────

def fig_days(S):
    """Delež članov z vsaj 1 in vsaj 5 cm snega po dnevih, Rečica (366 m), ponedeljek-nedelja."""
    W, H = 460, 270
    x0, x1, y0, y1 = 62, 452, 30, 196
    ds = list(range(23, 30))
    slot = (x1 - x0) / len(ds)
    Y = lambda v: y1 - v / 100 * (y1 - y0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    for v in (0, 50, 100):
        out.append(f'<line x1="{x0}" y1="{Y(v):.1f}" x2="{x1}" y2="{Y(v):.1f}" class="sg-g" stroke-width="1"/>')
        out.append(f'<text x="{x0 - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" font-size="13" class="sg-m">{v}{NBSP}%</text>')
    for k, n in enumerate(ds):
        d = S.day(366, n)
        cx = x0 + slot * (k + .5)
        bw = slot * .62
        h1 = d["cm1"]
        out.append(f'<rect x="{cx - bw / 2:.1f}" y="{Y(h1):.1f}" width="{bw:.1f}" height="{max(y1 - Y(h1), 0):.1f}" rx="2" fill="{SNOW}" fill-opacity=".38"/>')
        out.append(f'<rect x="{cx - bw / 2:.1f}" y="{Y(d["cm5"]):.1f}" width="{bw:.1f}" height="{max(y1 - Y(d["cm5"]), 0):.1f}" rx="2" fill="{SNOW}"/>')
        out.append(f'<text x="{cx:.1f}" y="{Y(h1) - 6:.1f}" text-anchor="middle" font-size="13" font-weight="600" class="sg-i">{h1}</text>')
        t = datetime.date(2026, 11, n)
        out.append(f'<text x="{cx:.1f}" y="{y1 + 18}" text-anchor="middle" font-size="13" class="sg-i">{DAYS[t.weekday()]} {n}.</text>')
        med = d["med"]
        lab = "0" if med < 0.05 else ("&lt;" + NBSP + "1" if med < 1 else str(rnd(med)))
        out.append(f'<text x="{cx:.1f}" y="{y1 + 38}" text-anchor="middle" font-size="12" class="sg-m">{lab}{NBSP}cm</text>')
    out.append(f'<text x="{x0}" y="16" font-size="13" class="sg-m">delež članov ansamblov (%)</text>')
    out.append(f'<text x="{x0 - 6}" y="{y1 + 38}" text-anchor="end" font-size="12" class="sg-m">mediana</text>')
    out.append("</svg>")
    return "".join(out)


def fig_hours(S):
    """Rečica, od torka 12.00 do petka 12.00: temperatura (mediana in 10.-90. percentil) in delež članov po vrsti padavin."""
    lo, hi = 60, 133     # torek 12.00 .. petek 12.00
    hh = S.hourly(366)
    n = hi - lo
    W, H = 460, 400
    x0, x1 = 40, 440
    yt0, yt1 = 26, 196
    tmax, tmin = 6.0, -6.0
    yp0, yp1 = 252, 346
    X = lambda k: x0 + k / (n - 1) * (x1 - x0)
    YT = lambda t: yt0 + (tmax - t) / (tmax - tmin) * (yt1 - yt0)
    YP = lambda v: yp1 - v / 100 * (yp1 - yp0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    for t in (-4, 0, 4):
        y = YT(t)
        z = t == 0
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="{"sg-z" if z else "sg-g"}" stroke-opacity="{.7 if z else 1}" stroke-width="1"{" stroke-dasharray=\"5 4\"" if z else ""}/>')
        out.append(f'<text x="{x0 - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="13" class="sg-m">{str(t).replace("-", "–")}</text>')
    out.append(f'<text x="{x0}" y="14" font-size="13" class="sg-m">temperatura zraka (°C): mediana in razpon 10.–90. percentila</text>')
    up = " ".join(f"{X(k):.1f},{YT(min(max(hh['t90'][lo + k], tmin), tmax)):.1f}" for k in range(n))
    dn = " ".join(f"{X(k):.1f},{YT(min(max(hh['t10'][lo + k], tmin), tmax)):.1f}" for k in reversed(range(n)))
    out.append(f'<polygon points="{up} {dn}" fill="#7fb0f0" fill-opacity=".22"/>')
    med = " ".join(f"{X(k):.1f},{YT(hh['t50'][lo + k]):.1f}" for k in range(n))
    out.append(f'<polyline points="{med}" fill="none" stroke="{SNOW}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>')
    # delež članov po vrsti padavin (sneg spodaj, dež s snegom, dež)
    out.append(f'<text x="{x0}" y="{yp0 - 12}" font-size="13" class="sg-m">delež članov: sneg, dež s snegom, dež</text>')
    out.append(f'<line x1="{x0}" y1="{yp1}" x2="{x1}" y2="{yp1}" class="sg-g" stroke-width="1"/>')
    for v in (0, 50, 100):
        out.append(f'<text x="{x0 - 6}" y="{YP(v) + 4:.1f}" text-anchor="end" font-size="13" class="sg-m">{v}</text>')
    bw = (x1 - x0) / (n - 1) * 0.86
    for k in range(n):
        base = 0.0
        for key, col in (("snow", SNOW), ("mix", MIX), ("rain", RAIN)):
            v = hh[key][lo + k] or 0
            if v <= 0:
                continue
            out.append(f'<rect x="{X(k) - bw / 2:.1f}" y="{YP(base + v):.1f}" width="{bw:.1f}" height="{(YP(base) - YP(base + v)):.1f}" fill="{col}"/>')
            base += v
    for k in range(n):
        t = START + datetime.timedelta(hours=lo + k)
        if t.hour in (0, 12):
            xl = X(k)
            out.append(f'<line x1="{xl:.1f}" y1="{yt0}" x2="{xl:.1f}" y2="{yp1 + 5}" class="sg-g" stroke-width="1" stroke-opacity=".6"/>')
            anchor = "start" if k == 0 else ("end" if k == n - 1 else "middle")
            lab = f"{DAYS[t.weekday()]} 0.00" if t.hour == 0 else "12.00"
            if k == 0:
                lab = "12.00"      # dan (torek) je očiten iz naslednje oznake; polna oznaka bi se prekrila z »sre 0.00«
            out.append(f'<text x="{xl:.1f}" y="{yp1 + 22}" text-anchor="{anchor}" font-size="13" class="sg-m">{lab}</text>')
    out.append("</svg>")
    return "".join(out)


def fig_elev(S, rows):
    """Za vsako višino: mediana novega snega med sredo in četrtkom (stolpec) in razpon 10.-90. percentila (črta)."""
    row_h = 38
    W, H = 460, 34 + row_h * len(rows)
    lx, x0, x1 = 112, 120, 330
    scale = 40.0
    X = lambda v: x0 + min(v, scale) / scale * (x1 - x0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    for v in (0, 10, 20, 30, 40):
        out.append(f'<line x1="{X(v):.1f}" y1="4" x2="{X(v):.1f}" y2="{H - 26}" class="sg-g" stroke-width="1"/>')
        out.append(f'<text x="{X(v):.1f}" y="{H - 8}" text-anchor="middle" font-size="13" class="sg-m">{v}</text>')
    for k, (el, name, w) in enumerate(rows):
        y = 8 + k * row_h
        label = f"{name} · {el}{NBSP}m" if name else f"{el}{NBSP}m"
        out.append(f'<text x="{lx}" y="{y + 18}" text-anchor="end" font-size="13" class="sg-i">{label}</text>')
        out.append(f'<rect x="{x0}" y="{y + 4}" width="{max(X(w["med"]) - x0, 2):.1f}" height="16" rx="2" fill="{SNOW}"/>')
        ly = y + 12
        out.append(f'<line x1="{X(w["p10"]):.1f}" y1="{ly}" x2="{X(w["p90"]):.1f}" y2="{ly}" class="sg-z" stroke-width="1.6"/>')
        for v in (w["p10"], w["p90"]):
            out.append(f'<line x1="{X(v):.1f}" y1="{ly - 6}" x2="{X(v):.1f}" y2="{ly + 6}" class="sg-z" stroke-width="1.6"/>')
        out.append(f'<text x="{x1 + 22}" y="{y + 17}" font-size="13" font-weight="600" class="sg-i">{rnd(w["med"])}{NBSP}cm</text>')
    out.append("</svg>")
    return "".join(out)


def table(cap, head, rows):
    h = "".join(f"<th scope=\"col\">{x}</th>" for x in head)
    b = "".join("<tr>" + "".join((f"<th scope=\"row\" style=\"color:var(--text);font-weight:500\">{c}</th>" if i == 0 else f"<td>{c}</td>") for i, c in enumerate(r)) + "</tr>" for r in rows)
    return (f'<div class="tn-wrap" role="region" aria-label="{cap}" tabindex="0"><table class="tn-tbl"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>')


# ───────────────────────── viri izven posnetka ─────────────────────────

def climatology():
    rows = json.load(open(os.path.join(ROOT, "data", "arso-sneg-postaje", "daily-1748.json"), encoding="utf-8"))["days"]
    out = []
    for y in range(2019, 2026):
        lo, hi = f"{y}-10-01", f"{y + 1}-07-01"
        season = [r for r in rows if lo <= r[0] < hi]
        assert sum(1 for r in season if r[1] is not None) >= 0.95 * len(season), (y, "arhiv ima luknje")
        first = next((r[0] for r in season if r[1] is not None and r[1] >= 1.0), None)
        assert first, y
        out.append(datetime.date.fromisoformat(first))
    return out


def live_gg():
    """ARSO Gornji Grad: število odčitkov in največja višina odeje od 9. 11. (naši odčitki, data/arso-snow-live.csv)."""
    vals, last = [], None
    with open(os.path.join(ROOT, "data", "arso-snow-live.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["id"] == "GORNJ-GRA_":
                try:
                    vals.append(float(r["snow_cm"]))
                    last = r["valid_utc"]
                except (TypeError, ValueError):
                    pass
    return len(vals), max(vals), last


# ───────────────────────── članek ─────────────────────────

def build_article(S):
    today = datetime.date.today()
    assert today.weekday() == 5 and today == datetime.date(2026, 11, 21), "članek je posnetek za soboto, 21. 11. 2026"

    d = {n: S.day(366, n) for n in range(22, 30)}
    # --- trditve, na katerih stoji zgodba ---
    assert d[23]["cm1"] <= 10 and d[24]["cm1"] <= 10, (d[23], d[24])               # ponedeljek in torek v dolini suha
    assert 50 <= d[25]["cm1"] < d[26]["cm1"], (d[25], d[26])                         # sreda verjetna, četrtek bolj
    assert d[26]["cm1"] >= 80 and d[26]["med"] >= 5, d[26]
    w2 = S.win(366, "sre_cet")
    assert w2["cm1"] >= 85 and w2["med"] >= 8 and w2["cm10"] >= 40, w2
    assert 20 <= d[27]["cm1"] <= 55 and d[28]["cm1"] <= 40, (d[27], d[28])           # od petka naprej razpršeno
    first = S.E["first"]
    assert first["with_snow"] / first["n"] >= 0.9 and 3 * 24 + 8 <= first["h50"] <= 3 * 24 + 20, first
    # višine: z višino se mediana ne zmanjšuje
    meds = [S.win(el, "sre_cet")["med"] for el in (366, 700, 1000, 1400)]
    assert meds == sorted(meds) and S.win(700, "sre_cet")["cm1"] >= 95, meds
    # nedelja: na 1400 m sneg, v dolini dež
    assert S.day(1400, 22)["cm1"] >= 90 and d[22]["cm1"] <= 5
    # pregled sistemov
    sysd = S.E["systems"]["366"]
    for mid, v in sysd.items():
        assert v["days"][D[26]]["cm1"] >= 70, (mid, v["days"][D[26]])

    # --- MTR in MTR sneg ---
    mtr = json.load(open(os.path.join(ROOT, "napoved-modela.json"), encoding="utf-8"))
    assert mtr["generated_at"].startswith("2026-11-21"), mtr["generated_at"]
    mt = {x["date"]: x for x in mtr["days"]}
    tue = mt[D[24]]
    assert tue["tmin"] <= -5 and tue["p_frost"] >= 0.9 and tue["night_regime"] == "clear_calm", tue
    sn = json.load(open(os.path.join(ROOT, "napoved-snega.json"), encoding="utf-8"))
    assert sn["generated_at"].startswith(("2026-11-20", "2026-11-21")), sn["generated_at"]
    sdays = {x["date"]: x for x in sn["days"]}
    assert max(sdays) == D[25], "MTR sneg sega do srede, 25. 11."
    wed_sn = sdays[D[25]]
    assert wed_sn["p_snow"] <= 0.25, wed_sn

    # --- zgodovina in dozdajšnje stanje ---
    firsts = climatology()
    assert [f.isoformat() for f in firsts] == ["2019-12-13", "2020-12-03", "2021-11-27", "2022-12-02", "2023-11-30", "2024-11-22", "2025-12-25"], firsts
    doys = sorted(datetime.date(2000 + (0 if f.month >= 10 else 1), f.month, f.day) for f in firsts)
    med_first = doys[len(doys) // 2]
    earlier_or_eq_26 = sum(1 for f in firsts if (f.month, f.day) <= (11, 26))
    assert earlier_or_eq_26 == 1 and (med_first.month, med_first.day) == (12, 2)
    ug = json.load(open(os.path.join(ROOT, "data", "sneg-ugibalnik.json"), encoding="utf-8"))
    assert ug["prvi_sneg"] is None and not ug["brez_snega"], ug
    n_live, max_live, last_live = live_gg()
    assert n_live >= 15 and max_live == 0.0, (n_live, max_live)

    # --- determinični modeli ---
    det = S.S["det"]
    both = {}
    for mid, v in det.items():
        e = v["elev"]["366"]
        if e.get(D[25]) and e.get(D[26]):
            both[mid] = (v["label"], e[D[25]], e[D[26]])
    cm2 = {mid: x[1]["cm"] + x[2]["cm"] for mid, x in both.items()}
    mm2 = {mid: x[1]["mm"] + x[2]["mm"] for mid, x in both.items()}
    assert len(both) >= 5, both
    n_ge5 = sum(1 for v in cm2.values() if v >= 5)
    assert n_ge5 >= len(both) - 1, cm2
    best = cm2.get("best_match")
    assert best is not None and best < min(v for k, v in cm2.items() if k != "best_match"), cm2   # osnovni model strani je najbolj zadržan

    # --- številke za besedilo ---
    w700, w1000, w1400 = S.win(700, "sre_cet"), S.win(1000, "sre_cet"), S.win(1400, "sre_cet")
    h10, h50, h90 = first["h10"], first["h50"], first["h90"]
    share_first = rnd(100 * first["with_snow"] / first["n"])
    sun1400 = S.day(1400, 22)
    thu_mm, wed_mm = d[26]["mm50"], d[25]["mm50"]
    tmax_wed, tmax_thu = d[25]["tmax50"], d[26]["tmax50"]
    tue_ens = d[24]["tmin50"]
    sys_names = {"ecmwf_ifs025": "ECMWF ENS", "icon_seamless": "ICON-EPS", "gfs025": "GEFS", "gem_global": "GEM ENS"}

    # --- grafi ---
    aria1 = ("Graf: delež članov ansamblov z vsaj 1 cm in vsaj 5 cm novega snega v Rečici po dnevih od ponedeljka do nedelje. "
             + "; ".join(f"{DAYS[datetime.date(2026, 11, n).weekday()]} {n}. 11.: {d[n]['cm1']} % in {d[n]['cm5']} %" for n in range(23, 30)) + ".")
    f1 = fig("Kateri dan sneži v dolini",
             '<div class="vs-leg"><span><i style="background:#3987e5;opacity:.45"></i>vsaj 1 cm snega</span><span><i style="background:#3987e5"></i>vsaj 5 cm</span></div>'
             + fig_days(S).replace("{ARIA}", aria1),
             f"Delež od {S.n} članov štirih ansamblov (za nedeljo 29. 11. ICON-EPS nima podatka, zato je tam {d[29]['n']} članov). Pod dnevom je mediana novega snega. "
             "Nov sneg = padavine pri temperaturi do 0,5 °C v celoti, nad 2,5 °C nič, vmes sorazmerno; 1 mm = 1 cm. To je izračun, ne napoved debeline snežne odeje.")

    hh = S.hourly(366)
    aria2 = (f"Graf: temperatura zraka v Rečici in delež članov po vrsti padavin od torka opoldne do petka opoldne. Mediana temperature je v sredo opoldne "
             f"{temp(hh['t50'][84], 1)}, v četrtek opoldne {temp(hh['t50'][108], 1)}. Prvi sneg se pojavi {when(h50)} (mediana).")
    f2 = fig("Ura za uro: temperatura ostane blizu ničle",
             '<div class="vs-leg"><span><i style="background:#3987e5"></i>sneg</span><span><i style="background:#9085e9"></i>dež s snegom</span><span><i style="background:#199e70"></i>dež</span></div>'
             + fig_hours(S).replace("{ARIA}", aria2),
             "Rečica, 366 m. Zgoraj mediana temperature članov in razpon med 10. in 90. percentilom, spodaj delež članov, pri katerih v tej uri pada sneg, dež s snegom (delež snega med 0 in 1) ali dež. "
             "Kjer stolpca ni, je pri večini članov suho.")

    rows = [(366, "Rečica", S.win(366, "sre_cet")), (700, "", w700), (1000, "", w1000), (1400, "Golte", w1400)]
    aria3 = ("Graf: mediana novega snega med sredo in četrtkom po višinah, z razponom od 10. do 90. percentila članov ansamblov. "
             + "; ".join(f"{el} m: {rnd(w['med'])} cm (od {rnd(w['p10'])} do {rnd(w['p90'])} cm)" for el, _, w in rows) + ".")
    f3 = fig("Koliko snega med sredo in četrtkom",
             fig_elev(S, rows).replace("{ARIA}", aria3),
             "Stolpec je mediana, črta razpon od 10. do 90. percentila članov (25.–26. 11., skupaj). "
             "Temperatura je izračunana za izbrano višino, ne izmerjena. Nad 700 m je skoraj vsa padavina sneg, zato se višine med seboj malo razlikujejo.")

    # --- ploščice ---
    tl = tiles([
        (pc(w2["cm1"]), "", f"članov ansamblov napoveduje v Rečici vsaj 1 cm snega med sredo in četrtkom", False),
        (f"{rnd(w2['med'])}", "cm", f"mediana novega snega med sredo in četrtkom (razpon 10.–90. percentila: {rnd(w2['p10'])}–{rnd(w2['p90'])} cm)", False),
        (f"{DAYS[(START + datetime.timedelta(hours=h50)).weekday()]} {(START + datetime.timedelta(hours=h50)).hour}.00", "", "mediana ure, ko v Rečici prvič zasneži", False),
        (temp(tue["tmin"], 0).replace(NBSP + "°C", ""), "°C", f"najnižja temperatura v torek zjutraj po modelu MTR; zmrzal z verjetnostjo {rnd(tue['p_frost'] * 100)} %", False),
    ])

    lead = (f"Da: po današnjih izračunih bo v Rečici prihodnji teden snežilo, najverjetneje od srede popoldne do četrtka. "
            f"Vsaj 1 cm snega med sredo in četrtkom napoveduje {pc(w2['cm1'])} od {S.n} članov ansamblov, mediana je {rnd(w2['med'])} cm. V ponedeljek in torek sneg v dolini ni verjeten.")

    p1 = [
        f"<strong>Kratek odgovor:</strong> v ponedeljek in torek snega v dolini ne pričakujem, v sredo popoldne začne snežiti, v četrtek pade največ, "
        f"od petka naprej pa se napoved razide. Na 700 m je sneg med sredo in četrtkom po izračunih skoraj gotov ({pc(w700['cm1'])} članov), v Rečici (366 m) {pc(w2['cm1'])}.",
        tl,
        f"V članku z 12. novembra " + a("/blog/sneg-dolina-in-gore-petek-sobota-1112.html", "»Sneg ta teden: v dolini ne, na višinah nekaj centimetrov«") +
        f" sem zapisal, da snega v dolini ne bo. Tako je tudi bilo: ARSO v Gornjem Gradu (428 m, 9 km od Rečice) od 9. novembra do {int(last_live[8:10])}. {int(last_live[5:7])}. "
        f"v {n_live} odčitkih ni izmeril nobene snežne odeje. V dolini prve snežne odeje letos torej še ni bilo.",
    ]

    p2 = [
        f"V nedeljo (22. 11.) v dolini še dežuje; sneg je verjeten šele nad približno 1000 m (na 1000 m vsaj 1 cm napoveduje {pc(S.day(1000, 22)['cm1'])} članov, v Rečici {pc(d[22]['cm1'])}). "
        f"V ponedeljek in torek je padavin malo (vsaj 1 cm snega ima {pc(d[23]['cm1']) if d[23]['cm1'] == d[24]['cm1'] else pc(d[23]['cm1']) + ' oziroma ' + pc(d[24]['cm1'])} članov{' v vsakem od obeh dni' if d[23]['cm1'] == d[24]['cm1'] else ''}), je pa mrzlo: ansambli kažejo v torek zjutraj v Rečici mediano {temp(tue_ens, 1)}, "
        f"poskusni model MTR, ki popravlja za dno doline, pa {temp(tue['tmin'], 1)}. Razlika je običajna za jasne, mirne noči: modeli so takrat v dolini običajno pretopli.",
        f1,
        f"Prvi sneg se v Rečici pojavi po ansamblih {when(h50)} (mediana). Pri {pc(share_first)} članov do četrtka opoldne vsaj enkrat sneži, pri 80 % članov med {hour_in(h10)} in {hour_in(h90)}. "
        f"V sredo pade po mediani {num(wed_mm, 1)} mm padavin, v četrtek {num(thu_mm, 1)} mm; mediana najvišje dnevne temperature je v sredo {temp(tmax_wed, 1)}, v četrtek {temp(tmax_thu, 1)}.",
        f2,
        f"V petek je v Rečici vsaj 1 cm snega še pri {pc(d[27]['cm1'])} članov, v soboto pri {pc(d[28]['cm1'])}, v nedeljo pri {pc(d[29]['cm1'])}. Teh dni zaradi razhajanja med modeli ne bi jemal kot napoved. "
        f"Osnovna napoved Open-Meteo za soboto sicer kaže {num(det['best_match']['elev']['366'][D[28]]['mm'], 0)} mm padavin, a je mediana ansamblov {num(d[28]['mm50'], 0)} mm: ta dan je nezanesljiv.",
    ]

    p3 = [
        f3,
        photo("lift"),
        f"Na 700 m je mediana {rnd(w700['med'])} cm, na 1000 m {rnd(w1000['med'])} cm, na Golteh (1400 m) {rnd(w1400['med'])} cm. "
        f"Razlika med 700 in 1400 m je majhna, ker je že na 700 m skoraj vsa padavina sneg. V Rečici je mediana {rnd(w2['med'])} cm, le nekaj centimetrov nižja, razpon pa širši in pomaknjen navzdol "
        f"({rnd(w2['p10'])}–{rnd(w2['p90'])} cm): odločilno je, ali je temperatura v urah padavin pod ali nad 0,5 °C.",
        "Ocena pri 1 mm = 1 cm je za mokri sneg blizu 0 °C lahko previsoka (mokri sneg je gostejši, torej je ob istem številu milimetrov manj centimetrov). "
        "Številke jemljite kot zgornji del verjetnega območja, ne kot napoved debeline odeje.",
    ]

    names = {"ecmwf_ifs025": "ECMWF IFS", "ecmwf_aifs025_single": "ECMWF AIFS", "icon_eu": "ICON-EU", "gfs_seamless": "GFS", "arpege_europe": "ARPEGE",
             "ukmo_seamless": "UKMO", "gem_seamless": "GEM", "best_match": "Open-Meteo (osnovni model strani)"}
    dash = '<span class="tn-na">–</span>'
    ens_rows = []
    for mid, v in sysd.items():
        dd = v["days"]
        ens_rows.append([f"{sys_names[mid]} ({S.S['members'][mid]} članov)", pc(dd[D[25]]["cm1"]), pc(dd[D[26]]["cm1"]), f"{rnd(dd[D[26]]['med'])}{NBSP}cm"])
    det_rows = []
    for mid in ("ecmwf_ifs025", "ecmwf_aifs025_single", "icon_eu", "gfs_seamless", "ukmo_seamless", "gem_seamless", "best_match"):
        e = det[mid]["elev"]["366"]
        f_ = lambda x: dash if x is None else f"{num(x['cm'], 1)}{NBSP}cm"
        tot = dash if (e.get(D[25]) is None or e.get(D[26]) is None) else f"{num(e[D[25]]['mm'] + e[D[26]]['mm'], 1)}{NBSP}mm"
        det_rows.append([names[mid], f_(e.get(D[25])), f_(e.get(D[26])), tot])
    t1 = table("Ansambli: delež članov z vsaj 1 cm snega v Rečici", ["Ansambel", "Sreda ≥ 1 cm", "Četrtek ≥ 1 cm", "Četrtek, mediana"], ens_rows)
    t2 = table("Determinični modeli: nov sneg in padavine v Rečici", ["Model", "Sreda, sneg", "Četrtek, sneg", "Padavine sre–čet"], det_rows)
    n_det = len(both)
    lo_cm, hi_cm = min(v for k, v in cm2.items() if k != "best_match"), max(cm2.values())
    p4 = [
        f"Vsi štirje ansambli v četrtek soglašajo: vsaj 1 cm snega napoveduje {min(v['days'][D[26]]['cm1'] for v in sysd.values())}–{max(v['days'][D[26]]['cm1'] for v in sysd.values())} % članov. "
        f"V sredo so razlike večje ({min(v['days'][D[25]]['cm1'] for v in sysd.values())}–{max(v['days'][D[25]]['cm1'] for v in sysd.values())} %): vprašanje je, ali se sneženje začne že popoldne ali šele zvečer. Ansambel je isti model, zagnan 20- do 50-krat z rahlo spremenjenimi začetnimi pogoji; "
        "če jih večina kaže isto, je izid verjetnejši, ni pa gotov.",
        t1,
        f"{ {5: 'Pet'}[n_det - 1] } determinističnih modelov (eden zagon, brez razpona), ki segajo do četrtka, daje v Rečici med sredo in četrtkom skupaj {rnd(lo_cm)}–{rnd(hi_cm)} cm snega; razlikujejo se v tem, kateri dan ga pade več. "
        f"Najbolj zadržan je Open-Meteo osnovni model, na katerem temelji moja stran " + a("/zima/", "Zima") + f" ({rnd(best)} cm). Zato naj vas ne zmede, če ta stran kaže manj snega kot ta članek: "
        "tu je merilo ansambel, ne ena napoved.",
        t2,
        '<p class="vs-note">Pomišljaj (–) pomeni, da napoved modela za ta dan ne seže (ICON-EU seže do srede). Sneg je izračunan enako kot v grafih (1 mm = 1 cm, meja 0,5–2,5 °C).</p>',
    ]

    snow_pct_wed = rnd(wed_sn["p_snow"] * 100)
    rad_pct = rnd(wed_sn["stations"]["Radegunda"] * 100)
    p5 = [
        photo("road"),
        "<strong>Sneži ni isto kot obleži.</strong> Ansambli povedo, kaj pada, ne, kaj ostane. "
        f"Za obležanje je ugodno, da je najvišja temperatura v sredo in četrtek po mediani le {temp(tmax_wed, 1)} in {temp(tmax_thu, 1)} in da bo po mrzli torkovi noči podlaga hladna. "
        "Neugodno je, da je blizu 0 °C: mokri sneg se na cestah hitro stopi, zlasti ob prometu in soli, na travi in strehah pa obleži laže. "
        "To je moja ocena, ne izračun.",
        f"Dva vira, ki ju uporabljam, se pri tem ne ujemata, in to je pošteno povedati. Poskusni model " + a("/zima/", "MTR sneg") + f" je naučen na opazovanjih ARSO in ocenjuje možnost merljivega snega "
        f"(vsaj 1 cm ob jutranjem odčitku) v Gornjem Gradu: za sredo kaže {snow_pct_wed} %, v Radegundi (794 m) {rad_pct} %. Za četrtek ocene še nima (seže do srede). "
        f"Je strožji: gleda povprečno dnevno temperaturo (za sredo {num(wed_sn['tavg'], 1)} °C) in sneg, ki ob odčitku že leži; ansambli pa štejejo vsako uro snega. "
        "Vprašanji sta različni, zato sta različna tudi odgovora; pravilno bo kazalo šele izmerjeno.",
        f"Po torkovem jutru z okoli {temp(tue['tmin'], 0)} (MTR) bo podlaga hladna, kar ob začetku sneženja pomaga, da sneg hitreje obleži. To velja le, če se sneženje res začne v sredo popoldne ali zvečer in ne kot dež.",
    ]

    first_s = ", ".join(f"{f.day}. {f.month}." for f in sorted(firsts, key=lambda x: (x.month < 10, x.month, x.day)))
    p6 = [
        f"V sedmih zimah (2019/20–2025/26) je v Gornjem Gradu prva snežna odeja vsaj 1 cm (ARSO) nastala na te dni: {first_s} (po datumu). Mediana je 2. 12., najzgodneje 22. 11. (2024). "
        f"Če bi prvi sneg padel v sredo ali četrtek, bi bil to eden zgodnejših v sedmih zimah: prej kot 26. 11. se je to zgodilo le v eni (22. 11. 2024). "
        "Za dolino bi bil torej zgoden, a ne rekordno zgodnji.",
        "Če ste na " + a("/zima/sneg-ugibalnik/", "ugibalniku prvega snega") + " že oddali datum, merilo ostaja isto: višina snežne odeje vsaj 1 cm na ARSO postaji Gornji Grad.",
    ]

    omej = [
        "<ul>"
        f"<li><strong>Modeli ne vidijo doline.</strong> Mreža ansamblov (okoli 25 do 50 km) je veliko grobejša od doline, zato lokalne podrobnosti (hladen zrak na dnu doline) izgubijo. "
        "Temperatura se na izbrano višino preračuna, inverzij pa ta preračun ne pozna.</li>"
        "<li><strong>Meja dež/sneg je poenostavljena.</strong> Gledam temperaturo zraka na 2 m (ne temperature mokrega termometra); pri 1–3 °C je lahko razlika med dežjem in snegom odvisna od vlage in intenzitete padavin.</li>"
        f"<li><strong>Posnetek ob {S.fetched.day}. {S.fetched.month}. ob {S.fetched.hour + 1}. uri.</strong> Modeli se osvežujejo večkrat na dan; do srede se bo napoved še premaknila, zlasti čas začetka.</li>"
        "<li><strong>Postaja IREICA1 snega ne meri.</strong> Za izmerjeno snežno odejo so merodajne ARSO postaje v dolini (Gornji Grad, Luče, Radegunda).</li>"
        "<li><strong>To ni uradno opozorilo.</strong> Za ukrepanje veljata ARSO in URSZR.</li>"
        "</ul>",
    ]
    p7 = [
        "<strong>Če se napoved obdrži, računajte v sredo zvečer in v četrtek zjutraj na sneg in poledico.</strong> Če vozite v dolini, poskrbite za zimsko opremo (pravila preverite pri AMZS; "
        "o času menjave gum sem pisal v članku " + a("/blog/kdaj-menjati-zimske-gume-recica-1027.html", "»Kdaj menjati zimske gume v Rečici«") + "). Za prelaz Črnivec je merodajna izmerjena postaja DRSI na " + a("https://crnivec.si/", "crnivec.si") +
        ", za ocene poledice " + a("/zima/poledica/", "stran o poledici") + ", za meje sneženja " + a("/zima/meja-snezenja/", "meja sneženja") + " in " + a("/zima/snezna-karta/", "snežna karta") + ".",
        "Ko sneg pade, lahko pomagate z opazovanjem: " + a("/zima/sneg-porocila/", "javite stanje v svoji regiji in višinskem pasu") + " (en dotik, brez prostega besedila in brez lokacije). "
        "Poročilo je neverificirano opažanje, ne meritev, a dopolni ARSO postaje, ki jih je v dolini malo.",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate samo z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]

    title = "Sneg prihodnji teden: v dolini kaže na sredo in četrtek"
    assert len(title) <= 60, len(title)
    desc = (f"Bo prihodnji teden sneg? Po ansamblih ga v Rečici napoveduje {w2['cm1']} % članov za sredo in četrtek; kdaj, koliko in na katerih višinah.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Da: v sredo popoldne in v četrtek", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — kdaj", "heading": "Najprej dva mirna dneva, nato sneg", "id": "kdaj", "paragraphs": p2},
        {"label": "03 — višine", "heading": "Koliko snega, kje", "id": "visine", "paragraphs": p3},
        {"label": "04 — modeli", "heading": "Ali se modeli strinjajo?", "id": "modeli", "paragraphs": p4},
        {"label": "05 — obleži", "heading": "Sneži, a ali obleži?", "id": "obleze", "paragraphs": p5},
        {"label": "06 — zgodovina", "heading": "Za dolino bi bil zgoden", "id": "zgodovina", "paragraphs": p6},
        {"label": "07 — omejitve", "heading": "Česa izračun ne pove?", "id": "omejitve", "paragraphs": omej},
        {"label": "08 — praktično", "heading": "Kaj lahko naredite?", "id": "prakticno", "paragraphs": p7},
    ]
    lead = nbsp(lead)
    for sec in sections:
        sec["paragraphs"] = [x if ("<svg" in x or "<script" in x or "<table" in x) else nbsp(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["sneg", "nižine", "Golte", "napoved", "november", "ansambli"],
        "section_label": "Podatkovna analiza", "og_photo": "misty-valley", "og_accent_hex": "#93c5fd",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": (f"Viri: Open-Meteo (ansambli ECMWF ENS, ICON-EPS, GEFS in GEM ENS ter determinični modeli ECMWF IFS, AIFS, ICON-EU, GFS, UKMO, GEM za Rečico, prenos z dne "
                         f"{S.fetched.day}. {S.fetched.month}. {S.fetched.year}), model MTR in MTR sneg (Meteorec), opazovanja ARSO v Gornjem Gradu (Vir: Agencija Republike Slovenije za okolje). "
                         "Weather data by Open-Meteo.com (CC BY 4.0). Podatki posnetka: data/sneg-teden-1121.json."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<script.*?</script>", "", h, flags=re.S)
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</(tr|h3|h4|figcaption|li|p|div)>", "\n", h)
        h = re.sub(r"</t[hd]>", " | ", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace("&shy;", "").replace("&lt;", "<").replace(NBSP, " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        for p in s["paragraphs"]:
            c = clean(p)
            if c:
                out += [c, ""]
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    S = Snap()
    article = build_article(S)
    if "--text" in sys.argv:
        open(TEXT_OUT, "w", encoding="utf-8").write(plain_text(article))
        print("✓ besedilo za lekturo:", os.path.relpath(TEXT_OUT, ROOT))
    if dry:
        print(plain_text(article))
        return
    path = os.path.join(ROOT, "blog", f"{SLUG}.html")
    if os.path.exists(path) and not force:
        print(f"blog/{SLUG}.html že obstaja -- brez ponovne objave (--force za prepis).")
        return
    import generate_forecast_test_post as ftp
    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = today.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, today.year, today.month, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Sneg prihodnji teden:\nsreda in četrtek", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html ({round(len(html) / 1024)} kB)")
    if wire or "--og" in sys.argv:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
    if wire:
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml, teme in sorodni članki osveženi.")


if __name__ == "__main__":
    main()
