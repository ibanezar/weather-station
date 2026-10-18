#!/usr/bin/env python3
"""
tools/generate_slana_gobe_post.py -- »Ali prva slana konča gobarsko sezono? Šest let podatkov« (18. 10. 2026).

Ročno napisan podatkovni članek (nadaljevanje članka o vrhu gobarske sezone). Vse številke v besedilu, grafih
in tabelah pridejo iz treh committanih virov:
  - history.json                       (postaja IREICA1: najnižja dnevna temperatura, samo zunanja meritev),
  - data/inat-glive-po-tednih.json     (iNaturalist, število opažanj po tednih; tools/study_inat_glive_po_tednih.py),
  - data/tla-temperatura-dnevna.json   (Open-Meteo archive, ERA5-Land, povprečje plasti 0-7 in 7-28 cm;
                                        `--fetch-tla` ga osveži; samo dnevna povprečja)
ter iz species_rules.yaml (pragovi vrst v gobarskem modelu). Besedilo nič ne izmišlja; trditve varujejo
assert-i: če se podatki osvežijo in trditev ne drži več, generator pade -- besedilo je treba pregledati,
ne zaobiti asserta.

Članek je posnetek na dan objave in se ne prepisuje samodejno. Po CLAUDE.md gre ročni članek skozi lekturo
(`lektura.yml` je od 2. 10. 2026 izklopljena -- do ponovnega vklopa ostane slogovni pregled po
docs/slog-pisanja.md). Notranjih meritev postaje članek ne uporablja (samo `tempLow` zunanjega senzorja).

Usage:
    python3 tools/generate_slana_gobe_post.py [--fetch-tla] [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
HISTORY = os.path.join(ROOT, "history.json")
INAT = os.path.join(ROOT, "data", "inat-glive-po-tednih.json")
TLA = os.path.join(ROOT, "data", "tla-temperatura-dnevna.json")
RULES = os.path.join(ROOT, "species_rules.yaml")
MODEL = os.path.join(ROOT, "napoved-modela.json")
INDEX_HIST = os.path.join(ROOT, "gobarska-napoved", "indeks-zgodovina.json")
SLUG = "slana-gobarska-sezona-1018"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-slana-gobe.txt")
NBSP = " "
LAT, LON = 46.3167, 14.9167                              # Rečica ob Savinji (kot v gobarskem modelu: dno doline)
GREEN, AMBER, CYAN, GREY = "#34d399", "#fbbf24", "#22d3ee", "#8aa0bd"
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
SURFACE = "#0a0f1c"
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LAST = 2026
SOIL_THR = (7.5, 3.5)                                    # 7,5 °C: lisička/marela/črna trobenta; 3,5 °C: jurček/sirovka
USER_AGENT = "meteorec.si analiza (filip.eremita@gmail.com)"


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def temp(x, d=1):
    return f"{num(x, d)}{NBSP}°C".replace("-", "–")


def dm(d):
    return f"{d.day}. {d.month}."


_MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
        "novembra", "decembra"]


def dlong(d):
    return f"{d.day}. {_MES[d.month]}"


_MES_OR = ["", "januarjem", "februarjem", "marcem", "aprilom", "majem", "junijem", "julijem", "avgustom", "septembrom", "oktobrom",
           "novembrom", "decembrom"]


def dmed(d):
    """datum v orodniku za »med 17. novembrom in 14. decembrom«."""
    return f"{d.day}. {_MES_OR[d.month]}"


def md(d):
    return (d.month, d.day)


def week_label(start):
    e = start + datetime.timedelta(6)
    if start.month == e.month:
        return f"{start.day}.–{e.day}. {e.month}."
    return f"{start.day}. {start.month}.–{e.day}. {e.month}."


_NOM = ["nič", "ena", "dve", "tri", "štiri", "pet", "šest", "sedem", "osem", "devet", "deset"]
_GEN = ["nič", "ene", "dveh", "treh", "štirih", "petih", "šestih", "sedmih", "osmih", "devetih", "desetih"]


def numw(n):
    return _NOM[int(n)] if 2 <= int(n) <= 10 else str(int(n))


def numg(n):
    return _GEN[int(n)] if 2 <= int(n) <= 10 else str(int(n))


# ───────────────────────── podatki ─────────────────────────

def fetch_tla():
    """Dnevna povprečja temperature tal (0-7 in 7-28 cm, povprečje obeh) za Rečico, 1. 9.–31. 12. 2020–2026."""
    import urllib.request
    end = min(datetime.date.today() - datetime.timedelta(days=2), datetime.date(LAST, 12, 31))
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=%s&longitude=%s&start_date=2020-09-01&end_date=%s"
           "&hourly=soil_temperature_0_to_7cm,soil_temperature_7_to_28cm&timezone=Europe%%2FLjubljana" % (LAT, LON, end))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    j = json.load(urllib.request.urlopen(req, timeout=90))
    h = j["hourly"]
    day = {}
    for ts, a, b in zip(h["time"], h["soil_temperature_0_to_7cm"], h["soil_temperature_7_to_28cm"]):
        if a is None or b is None:
            continue
        day.setdefault(ts[:10], []).append((a + b) / 2)
    out = {d: round(sum(v) / len(v), 2) for d, v in sorted(day.items())
           if len(v) >= 20 and "09-01" <= d[5:] <= "12-31"}
    doc = {"_meta": {"vir": "Open-Meteo archive API (ERA5-Land), povprečje plasti 0-7 in 7-28 cm",
                     "tocka": [LAT, LON], "generirano": datetime.date.today().isoformat(),
                     "opomba": "dnevna povprečja (vsaj 20 ur podatkov), 1. 9.–31. 12."},
           "dnevi": out}
    with open(TLA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {os.path.relpath(TLA, ROOT)}: {len(out)} dni")


def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    I = json.load(open(INAT, encoding="utf-8"))
    T = json.load(open(TLA, encoding="utf-8"))
    wk = {datetime.date.fromisoformat(k): v for k, v in sorted(I["tedni"].items())}
    soil = {k: v for k, v in T["dnevi"].items()}
    return H, I, wk, soil, T["_meta"]


def first_night(H, y, thr):
    """Prva noč od 1. 9. z najnižjo dnevno temperaturo <= thr (postaja IREICA1, zunanji senzor)."""
    for d in sorted(H):
        if d.startswith(str(y)) and d[5:] >= "09-01" and H[d].get("tempLow") is not None and H[d]["tempLow"] <= thr:
            return datetime.date.fromisoformat(d)
    return None


def soil_cross(soil, y, thr):
    """Prvi dan od 1. 10., ko je sedemdnevno povprečje temperature tal pod pragom."""
    days = sorted(d for d in soil if d.startswith(str(y)))
    for d in days:
        if d < f"{y}-10-01":
            continue
        x = datetime.date.fromisoformat(d)
        vals = [soil.get((x - datetime.timedelta(k)).isoformat()) for k in range(7)]
        if None in vals:
            continue
        if sum(vals) / 7 < thr:
            return x
    return None


def peak_and_drop(wk, y):
    ser = [(s, v["basidio"]) for s, v in wk.items() if datetime.date(y, 9, 1) <= s <= datetime.date(y, 12, 10)]
    peak = max(ser, key=lambda x: x[1])
    drop = next((s for s, c in ser if s > peak[0] and c < 0.5 * peak[1]), None)
    return peak, drop


def window_change(wk, y, key):
    A = [v[key] for s, v in wk.items() if datetime.date(y, 10, 13) <= s <= datetime.date(y, 10, 29)]
    B = [v[key] for s, v in wk.items() if datetime.date(y, 11, 3) <= s <= datetime.date(y, 11, 19)]
    assert len(A) == 3 and len(B) == 3, (y, len(A), len(B))
    return sum(A), sum(B)


def share_window(wk, y):
    ga, gb = window_change(wk, y, "basidio")
    va, vb = window_change(wk, y, "vse")
    return 100 * ga / va, 100 * gb / vb


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def timeline_chart(rows, w=460):
    """rows = [{leto, frost0, frost2, peak, drop}]; x = dnevi od 1. 10. (0 = 1. 10., 60 = 30. 11.)."""
    pl, pr, pt, pb = 40, 14, 22, 32
    rh = 38
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    X = lambda d: pl + iw * (d - datetime.date(d.year, 10, 1)).days / 60
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Prva ničelna noč, prva noč pod –2 °C, vrh opažanj gob in padec pod polovico vrha po letih" '
         'xmlns="http://www.w3.org/2000/svg">']
    base = pt + rh * len(rows)
    for off, lab in ((0, "1. 10."), (14, "15. 10."), (31, "1. 11."), (45, "15. 11."), (60, "30. 11.")):
        x = pl + iw * off / 60
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{lab}</text>')
    for i, r in enumerate(rows):
        y = r["leto"]
        cy = pt + rh * i + rh / 2
        p.append(f'<text x="{pl - 8}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{y}</text>')
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        # prva noč pod –2 °C (obrisan romb)
        d2 = r["frost2"]
        if d2:
            x = X(d2)
            p.append(f'<path d="M{x:.1f},{cy - 8:.1f} L{x + 7:.1f},{cy:.1f} L{x:.1f},{cy + 8:.1f} L{x - 7:.1f},{cy:.1f} Z" '
                     f'fill="{SURFACE}" stroke="{CYAN}" stroke-width="2"><title>{y}: prva noč pod –2 °C, {dm(d2)}</title></path>')
        # prva ničelna noč (poln romb)
        d0 = r["frost0"]
        if d0:
            x = X(d0)
            p.append(f'<path d="M{x:.1f},{cy - 6.5:.1f} L{x + 5.5:.1f},{cy:.1f} L{x:.1f},{cy + 6.5:.1f} L{x - 5.5:.1f},{cy:.1f} Z" '
                     f'fill="{CYAN}" stroke="{SURFACE}" stroke-width="1.5"><title>{y}: prva noč z 0 °C ali manj, {dm(d0)}</title></path>')
        # padec pod polovico vrha (obroč)
        dd = r["drop"]
        if dd:
            x = X(dd + datetime.timedelta(3))
            p.append(f'<circle cx="{x:.1f}" cy="{cy - 13:.1f}" r="5.5" fill="none" stroke="{AMBER}" stroke-width="2.2">'
                     f'<title>{y}: prvi teden pod polovico vrha, {week_label(dd)}</title></circle>')
        # teden z največ opaženimi gobami (zelena pika)
        dp = r["peak"]
        x = X(dp + datetime.timedelta(3))
        p.append(f'<circle cx="{x:.1f}" cy="{cy - 13:.1f}" r="5.5" fill="{GREEN}" stroke="{SURFACE}" stroke-width="1.8">'
                 f'<title>{y}: teden z največ opaženimi gobami, {week_label(dp)}</title></circle>')
    p.append("</svg>")
    return "".join(p)


def change_chart(rows, w=460):
    """rows = [(leto, upad_gobe_%, upad_vse_%)] -- dve vodoravni vrstici na leto (zelena: gobe, siva: vsa opažanja)."""
    pl, pr, pt, pb = 40, 44, 14, 28
    rh = 36
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    top = 100
    X = lambda v: pl + iw * v / top
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Upad števila opažanj od druge polovice oktobra do novembra: gobe in vsa opažanja" '
         'xmlns="http://www.w3.org/2000/svg">']
    base = pt + rh * len(rows)
    for t in (0, 25, 50, 75, 100):
        x = X(t)
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{t}{NBSP}%</text>')
    for i, (y, g, a) in enumerate(rows):
        y0 = pt + rh * i
        p.append(f'<text x="{pl - 8}" y="{y0 + rh / 2 + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{y}</text>')
        for j, (v, col, nm) in enumerate(((g, GREEN, "gobe"), (a, GREY, "vsa opažanja"))):
            by = y0 + 5 + j * 13
            p.append(f'<rect x="{pl}" y="{by:.1f}" width="{max(X(v) - pl, 1):.1f}" height="10" rx="2" fill="{col}">'
                     f'<title>{y}: {nm}, upad {round(v)} %</title></rect>')
            p.append(f'<text x="{X(v) + 5:.1f}" y="{by + 8.5:.1f}" font-size="10.5" fill="{INK}">{round(v)}{NBSP}%</text>')
    p.append("</svg>")
    return "".join(p)


VIOLET, BLUE = "#a78bfa", "#60a5fa"


def soil_chart(rows, w=460):
    """rows = [{leto, s75, s35, drop}]; x = dnevi od 1. 10. (0 = 1. 10., 75 = 15. 12.)."""
    pl, pr, pt, pb = 40, 14, 14, 32
    rh = 36
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    X = lambda d: pl + iw * (d - datetime.date(d.year, 10, 1)).days / 75
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Kdaj so tla padla pod 7,5 in 3,5 °C in kdaj je število opažanj gob upadlo pod polovico vrha" '
         'xmlns="http://www.w3.org/2000/svg">']
    base = pt + rh * len(rows)
    for off, lab in ((0, "1. 10."), (31, "1. 11."), (61, "1. 12.")):
        x = pl + iw * off / 75
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{lab}</text>')
    for i, r in enumerate(rows):
        y = r["leto"]
        cy = pt + rh * i + rh / 2
        p.append(f'<text x="{pl - 8}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{y}</text>')
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        x75, x35 = X(r["s75"]), X(r["s35"])
        p.append(f'<line x1="{x75:.1f}" x2="{x35:.1f}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{BLUE}" stroke-opacity=".35" stroke-width="6" stroke-linecap="round"/>')
        p.append(f'<circle cx="{x75:.1f}" cy="{cy:.1f}" r="6" fill="{VIOLET}" stroke="{SURFACE}" stroke-width="1.8"><title>{y}: tla pod 7,5 °C, {dm(r["s75"])}</title></circle>')
        p.append(f'<rect x="{x35 - 5.5:.1f}" y="{cy - 5.5:.1f}" width="11" height="11" rx="2" fill="{BLUE}" stroke="{SURFACE}" stroke-width="1.8">'
                 f'<title>{y}: tla pod 3,5 °C, {dm(r["s35"])}</title></rect>')
        xd = X(r["drop"] + datetime.timedelta(3))
        p.append(f'<circle cx="{xd:.1f}" cy="{cy:.1f}" r="8.5" fill="none" stroke="{AMBER}" stroke-width="2.4">'
                 f'<title>{y}: prvi teden pod polovico vrha, {week_label(r["drop"])}</title></circle>')
    p.append("</svg>")
    return "".join(p)


def species_chart(sp_rows, w=460):
    """sp_rows = [(ime, merilo, temp, sezona)] -- termometer: pika = najnižja temperatura, trak = ustrezna območja nad njo."""
    short = {"Orjaški dežnik (marela)": "Marela", "Štorovka (sivorumena mraznica)": "Štorovka"}
    rows = sorted(sp_rows, key=lambda r: -r[2])
    pl, pr, pt, pb = 118, 14, 14, 32
    rh = 30
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    lo, hi = -3, 9
    X = lambda t: pl + iw * (t - lo) / (hi - lo)
    base = pt + rh * len(rows)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Najnižja temperatura, pri kateri baza vrst dopušča rast, po vrstah" xmlns="http://www.w3.org/2000/svg">']
    for t in (-2, 0, 2, 4, 6, 8):
        x = X(t)
        dash = "" if t else ' stroke-dasharray="4 3" stroke-opacity=".7"'
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID if t else MUTED}" stroke-width="{1 if t else 1.6}"{dash}/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{str(t).replace("-", "–")}{NBSP}°C</text>')
    for i, (name, how, t, season) in enumerate(rows):
        cy = pt + rh * i + rh / 2
        nm = short.get(name, name)
        p.append(f'<text x="{pl - 10}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{nm}</text>')
        col = GREEN if how == "tla" else CYAN
        p.append(f'<rect x="{X(t):.1f}" y="{cy - 5:.1f}" width="{X(hi) - X(t):.1f}" height="10" rx="5" fill="{col}" fill-opacity=".22"/>')
        tip = f'{name}: najnižja temperatura {num(t)} °C ({"tla" if how == "tla" else "zraka"}), sezona v bazi {season}'
        if how == "tla":
            p.append(f'<circle cx="{X(t):.1f}" cy="{cy:.1f}" r="6.5" fill="{col}" stroke="{SURFACE}" stroke-width="1.8"><title>{tip}</title></circle>')
        else:
            p.append(f'<rect x="{X(t) - 6:.1f}" y="{cy - 6:.1f}" width="12" height="12" rx="2" fill="{col}" stroke="{SURFACE}" stroke-width="1.8"><title>{tip}</title></rect>')
        lab = f"{num(t)}".replace("-", "–")
        p.append(f'<text x="{X(t) + 11:.1f}" y="{cy + 4:.1f}" font-size="10.5" font-weight="700" fill="{INK}" stroke="{SURFACE}" stroke-width="3" paint-order="stroke">{lab}</text>')
    p.append("</svg>")
    return "".join(p)


def year_cards(data):
    out = []
    for y in YEARS:
        d = data[y]
        after = d["peak"] > d["f0"]
        chip = ('<span class="vs-chip vs-chip-on">vrh gob po slani</span>' if after else '<span class="vs-chip">vrh gob pred slano</span>')
        out.append(
            f'<div class="vs-card"><div class="vs-card-top"><strong>{y}</strong>{chip}</div>'
            f'<p><i class="vs-dia" style="background:{CYAN}"></i>prva noč z mrazom<b>{dm(d["f0"])}</b></p>'
            f'<p><i class="vs-dot" style="background:{GREEN}"></i>vrh opažanj gob<b>{week_label(d["peak"])}</b></p>'
            f'<p><i class="vs-ring" style="border-color:{AMBER}"></i>pod polovico vrha<b>{week_label(d["drop"])}</b></p></div>')
    return '<div class="vs-cards">' + "".join(out) + "</div>"


def legend(entries):
    out = []
    for n, kind, c in entries:
        cls = {"dia": "vs-dia", "diaring": "vs-diaring", "dot": "vs-dot", "ring": "vs-ring"}.get(kind, "")
        if kind == "diaring":
            sw = f'<i class="{cls}" style="border-color:{c}"></i>'
        elif kind == "ring":
            sw = f'<i class="{cls}" style="border-color:{c}"></i>'
        elif cls:
            sw = f'<i class="{cls}" style="background:{c}"></i>'
        else:
            sw = f'<i style="background:{c}"></i>'
        out.append(f"<span>{sw}{n}</span>")
    return '<p class="vs-leg">' + " ".join(out) + "</p>"


STYLE = """<style>
.vs-fig{margin:1.4rem 0;padding:1rem 1rem .8rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px}
.vs-fig figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.6rem}
.vs-fig h3{font-family:'Space Grotesk',sans-serif;font-size:.95rem;margin:0 0 .4rem;color:var(--text)}
.vs-fig svg{display:block;width:100%;height:auto;max-width:560px;margin:0 auto}
.vs-leg{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-size:.85rem;color:var(--muted);margin:.2rem 0 .6rem}
.vs-leg i{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;margin-right:.4rem;vertical-align:-.1rem}
.vs-leg i.vs-dot{border-radius:50%}
.vs-leg i.vs-ring{border-radius:50%;background:none;border:2px solid}
.vs-leg i.vs-dia{border-radius:2px;transform:rotate(45deg) scale(.85)}
.vs-leg i.vs-diaring{border-radius:2px;background:none;border:2px solid;transform:rotate(45deg) scale(.85)}
.vs-tbl{overflow-x:auto;max-width:100%;margin:1rem 0}
.vs-tbl table{border-collapse:collapse;width:100%;font-size:.86rem}
.vs-tbl th,.vs-tbl td{padding:.42rem .5rem;text-align:right;border-bottom:1px solid var(--border)}
.vs-tbl td{white-space:nowrap}
.vs-tbl th{vertical-align:bottom;line-height:1.3;color:var(--muted);font-weight:600;font-size:.76rem}
.vs-tbl th:first-child,.vs-tbl td:first-child{text-align:left}
.vs-tbl tr.vs-now td{font-weight:700;background:rgba(52,211,153,.08)}
.vs-note{color:var(--muted);font-size:.82rem;line-height:1.5;margin:-.4rem 0 1.2rem}
.vs-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.6rem;margin:1.2rem 0}
.vs-card{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:.7rem .8rem}
.vs-card-top{display:flex;flex-wrap:wrap;align-items:center;gap:.3rem .5rem;margin-bottom:.45rem}
.vs-card-top strong{font-family:'Space Grotesk',sans-serif;font-size:1.25rem}
.vs-chip{font-size:.7rem;padding:.15rem .5rem;border-radius:99px;background:rgba(138,160,189,.18);color:var(--muted);white-space:nowrap}
.vs-chip-on{background:rgba(52,211,153,.18);color:#34d399}
.vs-card p{display:block;position:relative;padding-left:1.1rem;margin:.4rem 0;font-size:.78rem;line-height:1.25;color:var(--muted)}
.vs-card p b{display:block;color:var(--text);font-weight:600;font-size:.88rem;white-space:nowrap}
.vs-card i{position:absolute;left:0;top:.18rem;display:block;width:.7rem;height:.7rem}
.vs-card i.vs-dot{border-radius:50%}
.vs-card i.vs-ring{border-radius:50%;background:none;border:2px solid}
.vs-card i.vs-dia{transform:rotate(45deg) scale(.8);border-radius:2px}
.vs-more{margin:.6rem 0 1.2rem}
.vs-more summary{cursor:pointer;color:var(--blue);font-size:.9rem}
h3.vs-h3,.post-body h3{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;margin:1.6rem 0 .4rem}
</style>"""


def fig(title, inner, caption):
    return f'<figure class="vs-fig"><h3>{title}</h3>{inner}<figcaption>{caption}</figcaption></figure>'


def table(head, rows, now_label=None, cap="", note=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    body = ""
    for r in rows:
        cls = ' class="vs-now"' if now_label and r[0] == now_label else ""
        body += f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return (f'<div class="vs-tbl" tabindex="0" role="region" aria-label="{cap}"><table><thead><tr>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>' + (f'<p class="vs-note">{note}</p>' if note else ""))


# ───────────────────────── članek ─────────────────────────

def species_rows():
    import yaml
    sp = {s["id"]: s for s in yaml.safe_load(open(RULES, encoding="utf-8"))["species"]}
    spec = [  # (id, ime v besedilu, merilo)
        ("cantharellus_cibarius", "Lisička", "tla"), ("macrolepiota_procera", "Orjaški dežnik (marela)", "tla"),
        ("hydnum_repandum", "Rumeni ježek", "tla"), ("boletus_edulis", "Jurček", "tla"),
        ("lactarius_deliciosus", "Užitna sirovka", "tla"), ("tricholoma_portentosum", "Zimska kolobarnica", "tla"),
        ("hygrophorus_hypothejus", "Zimska polževka", "tla"),
        ("armillaria_mellea", "Štorovka (sivorumena mraznica)", "zrak"), ("pleurotus_ostreatus", "Bukov ostrigar", "zrak"),
        ("flammulina_velutipes", "Zimska panjevka", "zrak"),
    ]
    rows = []
    for sid, name, how in spec:
        s = sp[sid]
        assert s.get("verified") is True and s.get("gets_index") is True, sid
        t = s["soil_temp"]["min"] if how == "tla" else s["air_temp"]["min"]
        a, b = s["season"]["start"], s["season"]["end"]
        rows.append((name, "tla" if how == "tla" else "zrak", t, f"{int(a[3:])}. {int(a[:2])}.–{int(b[3:])}. {int(b[:2])}."))
    return rows


def build_article(H, I, wk, soil, soil_meta):
    P = I["povzetek"]["basidio"]
    last_day = max(H)
    last = datetime.date.fromisoformat(last_day)
    rows, data = [], {}
    for y in YEARS:
        peak, drop = peak_and_drop(wk, y)
        assert peak[0].isoformat() == P[str(y)]["teden_z_najvec"]["zacetek"], y
        f0, f2 = first_night(H, y, 0.0), first_night(H, y, -2.0)
        s75, s35 = soil_cross(soil, y, SOIL_THR[0]), soil_cross(soil, y, SOIL_THR[1])
        g = window_change(wk, y, "basidio")
        a = window_change(wk, y, "vse")
        sh = share_window(wk, y)
        data[y] = dict(peak=peak[0], peak_n=peak[1], drop=drop, f0=f0, f2=f2, s75=s75, s35=s35,
                       dg=100 * (1 - g[1] / g[0]), da=100 * (1 - a[1] / a[0]), sh=sh, g=g, a=a)
        rows.append({"leto": y, "frost0": f0, "frost2": f2, "peak": peak[0], "drop": drop})

    # --- trditve članka: če podatki tega ne kažejo več, generator pade ---
    early = [y for y in YEARS if data[y]["f0"] and data[y]["f0"].month == 10]
    late = [y for y in YEARS if y not in early]
    assert early == [2020, 2021, 2023, 2025], early
    assert late == [2022, 2024] and data[2022]["f0"] == datetime.date(2022, 11, 20) and data[2024]["f0"] == datetime.date(2024, 11, 4)
    for y in early:                                           # vrh opažanj gob je bil po prvi ničelni noči
        assert data[y]["peak"] > data[y]["f0"], y
    for y in late:                                            # ... in pri poznih slanah pred njo
        assert data[y]["peak"] < data[y]["f0"], y
    drops = {y: data[y]["drop"] for y in YEARS}
    n_nov4 = sum(1 for y in YEARS if (drops[y].month, drops[y].day) == (11, 4))
    assert n_nov4 == 5 and (drops[2021].month, drops[2021].day) == (10, 28), drops
    assert data[2022]["f0"] > data[2022]["drop"] + datetime.timedelta(days=14)    # 2022: padec brez slane
    assert (data[2025]["drop"] - data[2025]["f0"]).days >= 28                    # 2025: slana mesec prej
    cold_before_nov = [y for y in YEARS if data[y]["f2"] and data[y]["f2"].month == 10]
    assert cold_before_nov == [2021], cold_before_nov
    for y in YEARS:                                           # splošen upad v drugi polovici novembra
        assert data[y]["dg"] > 30 and data[y]["da"] > 30, y
    n_share_down = sum(1 for y in YEARS if data[y]["sh"][1] < data[y]["sh"][0])
    assert n_share_down == 5, n_share_down
    for y in YEARS:                                           # tla niso pod 3,5 °C pred sredino novembra
        assert data[y]["s35"] >= datetime.date(y, 11, 17), (y, data[y]["s35"])
    assert data[2021]["s75"] == datetime.date(2021, 10, 29)
    for y in YEARS:
        if y != 2021:
            assert data[y]["s75"] >= datetime.date(y, 11, 10), (y, data[y]["s75"])
    assert data[2021]["f2"].month == 10 and data[2021]["f2"] == datetime.date(2021, 10, 14)

    for y in YEARS:                                           # »do istega datuma« v letosnjem odstavku
        cut = datetime.date(y, last.month, last.day)
        assert (data[y]["f0"] is not None and data[y]["f0"] <= cut) == (y in early), (y, cut)
    assert [y for y in YEARS if y in late] == [2022, 2024]
    this_f0 = first_night(H, LAST, 0.0)
    assert this_f0 is None, "letos je že bila ničelna noč -- odstavek »letos« in naslov je treba predelati"
    this_min = min((H[d]["tempLow"], d) for d in H if d.startswith(str(LAST)) and "09-01" <= d[5:] and H[d].get("tempLow") is not None)
    soil_last_d = max(d for d in soil if d.startswith(str(LAST)))
    soil_last = soil[soil_last_d]
    mdl = json.load(open(MODEL, encoding="utf-8"))
    fdays = [r for r in (mdl.get("days") or mdl.get("napoved") or []) if r.get("date") and r.get("p_frost") is not None]
    ih = json.load(open(INDEX_HIST, encoding="utf-8"))
    idx_last = ih[-1]
    gen = I["_meta"]["generirano"]

    pw = lambda lst: ", ".join(str(y) for y in lst)
    lead = (f"V {numg(len(early))} od {numg(len(YEARS))} jeseni med letoma 2020 in 2025 je postaja v Rečici prvič izmerila 0{NBSP}°C ali manj že oktobra. "
            f"V vseh {numg(len(early))} primerih je bil teden z največ opaženimi gobami v Sloveniji šele po tej noči. "
            "Prva slana torej ne konča gobarske sezone. Podatki sicer pokažejo, kdaj se val gob umiri, vendar se to ne zgodi ob prvi slani.")

    t1 = (year_cards(data) + '<p class="vs-note">Temperatura: postaja IREICA1, najnižja dnevna vrednost od 1. 9. Opažanja: iNaturalist, Slovenija, '
          'deblo Basidiomycota. Tedni se začnejo 1. 7. in si sledijo v sedemdnevnih intervalih.</p>')
    f_timeline = fig("Kdaj je bila prva slana in kdaj je nastopil vrh opažanj gob?",
                     legend([("prva noč z 0 °C ali manj", "dia", CYAN), ("prva noč z –2 °C ali manj", "diaring", CYAN),
                             ("teden z največ opaženimi gobami", "dot", GREEN),
                             ("prvi teden, v katerem je bilo opažanj manj kot polovico vrha", "ring", AMBER)])
                     + timeline_chart(rows),
                     "Zelena pika označuje sredino tedna z največ opaženimi gobami, oranžni obroč pa sredino prvega tedna po vrhu, ko je bilo opažanj "
                     "manj kot polovico vršnega števila. Modra romba označujeta prvi noči, ko je postaja izmerila navedeni temperaturi.")

    t2 = table(["Leto", "Opažanja gob, 13.–29. 10.", "Opažanja gob, 3.–19. 11.", "Upad opažanj gob", "Upad vseh opažanj", "Delež gob prej → pozneje"],
               [[str(y), str(data[y]["g"][0]), str(data[y]["g"][1]), f"{round(data[y]['dg'])}{NBSP}%", f"{round(data[y]['da'])}{NBSP}%",
                 f"{round(data[y]['sh'][0])} → {round(data[y]['sh'][1])}{NBSP}%"] for y in YEARS],
               cap="Število opažanj gob in vseh opažanj v drugi polovici oktobra in v novembru",
               note="Vsota opažanj v treh tednih, ki se začnejo med 13. in 29. oktobrom oziroma med 3. in 19. novembrom. "
                    "Delež pomeni odstotek opažanj gob med vsemi opažanji.")
    t2 = '<details class="vs-more"><summary>Vse številke po letih (tabela)</summary>' + t2 + '</details>'
    f_change = fig("Upad opažanj od druge polovice oktobra do novembra",
                   legend([("gobe", "sq", GREEN), ("vsa opažanja (rastline, žuželke, ptice in druge skupine)", "sq", GREY)])
                   + change_chart([(y, data[y]["dg"], data[y]["da"]) for y in YEARS]),
                   "Graf primerja vsoto opažanj v treh tednih v drugi polovici oktobra z vsoto v treh tednih novembra. V petih od šestih let je zelena "
                   "vrstica daljša od sive, kar pomeni, da je število opažanj gob upadlo bolj kot število vseh opažanj.")

    f_soil = fig("Kdaj so se ohladila tla in kdaj je val gob upadel?",
                 legend([("tla pod 7,5 °C", "dot", VIOLET), ("tla pod 3,5 °C", "sq", BLUE),
                         ("prvi teden pod polovico vrha opažanj gob", "ring", AMBER)])
                 + soil_chart([{"leto": y, "s75": data[y]["s75"], "s35": data[y]["s35"], "drop": data[y]["drop"]} for y in YEARS]),
                 "Prvi dan od 1. oktobra, ko je sedemdnevno povprečje temperature tal padlo pod prag. Temperatura tal je povprečje plasti od 0 do 7 cm "
                 "in od 7 do 28 cm; vir je Open-Meteo oziroma reanaliza ERA5-Land za Rečico.")

    sp_rows = species_rows()
    f_species = fig("Pri kateri temperaturi baza vrst še dopušča rast",
                    legend([("tla (mikorizne vrste in razkrojevalke)", "dot", GREEN), ("zrak (lesne vrste)", "sq", CYAN)])
                    + species_chart(sp_rows),
                    "Pika je najnižja temperatura, pri kateri baza vrst gobarskega modela Meteorec (species_rules.yaml) še dopušča rast, blag trak pa temperature nad njo. "
                    "Pri lesnih vrstah je merilo temperatura zraka, pri ostalih temperatura tal. To so parametri modela, ne rezultati laboratorijskih meritev.")

    nums_f = [r for r in fdays][:3]
    fc_txt = ""
    if nums_f:
        mx = max(r["p_frost"] for r in nums_f)
        d0 = datetime.date.fromisoformat(nums_f[0]["date"])
        d1 = datetime.date.fromisoformat(nums_f[-1]["date"])
        assert mx < 0.005 and d0.month == d1.month, "napoved zmrzali ni več 0 % -- odstavek je treba predelati"
        fc_txt = (f"Napoved modela MTR za Rečico za obdobje od {d0.day}. do {dlong(d1)} ni kazala možnosti zmrzali; "
                  f"napovedana verjetnost je bila 0{NBSP}%.")

    s35_lo = min((data[y]["s35"] for y in YEARS), key=md)
    s35_hi = max((data[y]["s35"] for y in YEARS), key=md)
    s75_lo = min((data[y]["s75"] for y in YEARS), key=md)
    s75_hi = max((data[y]["s75"] for y in YEARS), key=md)
    s75_min_other = min((data[y]["s75"] for y in YEARS if y != 2021), key=md)
    low2021 = H[data[2021]["f2"].isoformat()]["tempLow"]

    p1 = [
        "<strong>Kratek odgovor: ne.</strong> V vseh štirih letih, ko je bila prva noč z 0 °C ali manj že oktobra (2020, 2021, 2023 in 2025), je bil teden "
        "z največ opaženimi gobami šele po njej. V letih 2022 in 2024, ko je temperatura prvič padla na 0 °C ali manj šele novembra, pa je bil vrh pred prvo "
        "tako hladno nočjo.",
        t1,
        f_timeline,
        "Pomembna je razlika med <strong>slano na postaji in slano na travi</strong>. Postaja meri temperaturo zraka, trava in tla pa se ob jasnih nočeh "
        "lahko ohladijo precej bolj. Zakaj se trava lahko pobeli, čeprav postaja kaže še nad ničlo, sem pojasnil "
        '<a href="/blog/slana-pri-1-7-c-zakaj-trava-pobeli-prej-kot-postaja-1004.html" style="color:var(--blue)">v članku o slani pri 1,7 °C</a>. '
        "V tej analizi upoštevam samo noči, ko je postaja izmerila 0 °C ali manj.",
    ]
    p2 = [
        "Kdaj se torej gobarski val umiri? Skoraj vsako leto se je število opaženih gob zmanjšalo na manj kot polovico vrha v istem tednu: "
        "<strong>med 4. in 10. novembrom v petih od šestih let</strong>. Izjema je bilo leto 2021, ko se je to zgodilo teden prej, med 28. oktobrom in 3. novembrom.",
        f"Posebej zanimivi sta dve leti. Leta 2022 postaja do 20. novembra ni izmerila niti ene noči z 0 °C ali manj, a je število opažanj gob "
        f"v tednu od 4. do 10. novembra kljub temu padlo z {wk[datetime.date(2022, 10, 28)]['basidio']} na {wk[datetime.date(2022, 11, 4)]['basidio']}. "
        f"Leta 2025 pa je bila prva noč z 0 °C ali manj že {dlong(data[2025]['f0'])}, vendar je gobarski val vztrajal še več kot mesec dni. "
        f"V tednu od 21. do 27. oktobra so zabeležili {wk[datetime.date(2025, 10, 21)]['basidio']} opažanj, kar je bil vrh tistega leta.",
        f_change,
        t2,
        "Poudariti je treba, da se <strong>novembra ne zmanjša samo število opažanj gob</strong>, temveč tudi število vseh opažanj rastlin, žuželk, ptic, gliv "
        "in drugih organizmov. "
        f"Število opažanj gob je upadlo za {round(min(data[y]['dg'] for y in YEARS))}–{round(max(data[y]['dg'] for y in YEARS))}{NBSP}%, "
        f"število vseh opažanj pa za {round(min(data[y]['da'] for y in YEARS))}–{round(max(data[y]['da'] for y in YEARS))}{NBSP}%.",
        "Upad opažanj gob je bil praviloma večji. Njihov delež med vsemi opažanji se je zmanjšal v petih od šestih let. Iz teh podatkov ne morem ugotoviti, zakaj. "
        "V gozdu je lahko dejansko manj gob, lahko pa je tudi manj ljudi, ki se novembra odpravijo v gozd in svoja opažanja objavijo na iNaturalistu.",
    ]
    p3 = [
        "V gobarskem modelu je pri večini vrst pomembnejša temperatura tal kot temperatura zraka. Zrak se lahko ponoči hitro ohladi pod ničlo, "
        "tla pod gozdno steljo pa se praviloma ohlajajo počasneje.",
        f"Po podatkih v bazi vrst gobarskega modela jurček in užitna sirovka potrebujeta temperaturo tal nad 3,5{NBSP}°C, lisička, marela in črna trobenta pa nad 7,5{NBSP}°C. "
        f"V šestih analiziranih letih so tla v Rečici pod 3,5{NBSP}°C padla šele med {dmed(s35_lo)} in {dmed(s35_hi)}, "
        f"pod 7,5{NBSP}°C pa med {dmed(s75_lo)} in {dmed(s75_hi)}.",
        f_soil,
        f"V petih od šestih let so tla ostala toplejša od 7,5{NBSP}°C vsaj do {dlong(s75_min_other)}, število opaženih gob pa je začelo izraziteje upadati že v tednu "
        "od 4. novembra. V teh letih upada torej ne moremo neposredno povezati niti s prvo slano niti s prehladnimi tlemi. Bolj se ujema s koledarskim obdobjem.",
        f"Izjema je leto 2021. Takrat je bila temperatura zraka pod –2{NBSP}°C že oktobra: {dlong(data[2021]['f2'])} so izmerili {temp(low2021)}. "
        f"Tla so pod 7,5{NBSP}°C padla že {dlong(data[2021]['s75'])}, gobarski val pa se je umiril teden prej kot v drugih letih.",
        "Ena sama jesen je premalo za zanesljiv sklep, da huda slana ustavi rast gob. Kaže pa, da vzorca »vedno prvi teden novembra« ne morem posplošiti "
        "na hladnejša leta.",
    ]
    p4 = [
        "Ko jesenska gobarska sezona slabi, se začnejo pojavljati tudi vrste, ki jim ustrezajo nižje temperature. V bazi vrst gobarskega modela je več vrst "
        "z nižjimi temperaturnimi pragovi kot pri lisički ali mareli.",
        f_species,
        "Sezona zimske kolobarnice in zimske polževke po podatkih modela sega do konca leta, bukov ostrigar ima sezono do konca januarja, zimska panjevka pa do konca marca. "
        f"Zimska panjevka ima v bazi najnižji prag: po podatkih modela lahko raste tudi pri –2{NBSP}°C.",
        "To seveda ne pomeni, da so vse gobe, ki jih najdemo pozimi, užitne. Nabirajte jih samo, če jih zanesljivo poznate, saj imajo tudi zimske vrste nevarne zamenjave.",
    ]
    letos = [
        f"Od 1. septembra do {dlong(last)} je bila najnižja temperatura na postaji {temp(this_min[0])}, izmerjena {dlong(datetime.date.fromisoformat(this_min[1]))}. "
        f"Prve noči z 0{NBSP}°C ali manj torej še ni bilo. Do istega datuma je ni bilo niti v letih 2022 in 2024, v preostalih štirih letih ({pw(early)}) "
        "pa je bila do tega datuma prva taka noč že za nami.",
        f"Povprečna temperatura tal je bila {dlong(datetime.date.fromisoformat(soil_last_d))} {temp(soil_last)}. Podatek temelji na povprečju plasti "
        f"od 0 do 7 cm in od 7 do 28 cm po viru Open-Meteo. Gobarski indeks za Rečico je {dlong(datetime.date.fromisoformat(idx_last['date']))} "
        f"znašal {idx_last['index']} od 100. " + fc_txt,
        'Padavine, napovedane za sredo in četrtek, sem podrobneje obravnaval <a href="/blog/gobe-se-ena-priloznost-modeli-dez-1017.html" style="color:var(--blue)">v članku z dne 17. oktobra</a>.',
    ]
    omejitve = [
        "<ul>"
        "<li><strong>Fotografije niso košare.</strong> Opažanje gobe ne pomeni, da jo je nekdo nabral, še manj pa, da je užitna. "
        "Analiza temelji na fotografijah gob, ki so jih ljudje objavili na iNaturalistu, ne na štetju gob v gozdu.</li>"
        "<li><strong>Šest let je malo.</strong> Rezultati veljajo za analizirana leta in Slovenijo kot celoto. V Rečici ali na višjih legah je lahko potek sezone drugačen.</li>"
        "<li><strong>Prva slana na postaji ni nujno prva slana v okolici.</strong> Postaja meri temperaturo zraka na eni lokaciji v dolini. "
        "Na travi, v gozdu ali na višjih legah se lahko slana pojavi prej.</li>"
        "<li><strong>Letošnje leto še ni končano.</strong> Podatki zadnjega tedna so zaradi zamude pri objavljanju opažanj podcenjeni, "
        "zato letošnjega gobarskega vala ne vključujem v primerjavo.</li>"
        "<li><strong>Temperatura tal je ocenjena, ne neposredno izmerjena.</strong> Podatke za Rečico prevzemam iz Open-Meteo (ERA5-Land), katerega mreža ima celice "
        "velike okoli 10 km. Dejanska temperatura gozdnih tal se lahko razlikuje.</li>"
        "<li><strong>Temperaturni prag v bazi vrst ni izmerjena meja rasti.</strong> Gre za parameter gobarskega modela, zato ga je treba razumeti kot del ocene, "
        "ne kot absolutno biološko pravilo.</li>"
        "<li><strong>Objavljeni so samo združeni podatki.</strong> Posameznih opažanj ne objavljam, ker zanje veljajo različni licenčni pogoji. "
        'Zbrane številke so na voljo v datoteki <a href="/data/inat-glive-po-tednih.json" style="color:var(--blue)">data/inat-glive-po-tednih.json</a>.</li>'
        "</ul>",
    ]
    p6 = [
        "Praktično sporočilo je preprosto: prve slane ne jemljite kot znak, da je gobarske sezone konec. Pred odhodom v gozd preverite "
        f'<a href="{SITE}/gobarska-napoved/danes/" style="color:var(--blue)">gobarsko napoved za svoj kraj</a> '
        f'in <a href="{SITE}/gobarska-napoved/valovi/" style="color:var(--blue)">kalkulator rasti po dežju</a>. '
        'O vrhu opažanj gob sem pisal tudi <a href="/blog/vrh-gobarske-sezone-oktober-1014.html" style="color:var(--blue)">v prejšnjem članku</a>.',
        "Gobe nabirajte samo, če jih zanesljivo poznate. Več o nevarnih zamenjavah si lahko preberete na strani "
        f'<a href="{SITE}/gobarska-napoved/strupene-gobe/" style="color:var(--blue)">Strupene gobe</a>.',
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    title = "Ali prva slana konča gobarsko sezono? Šest let podatkov"
    assert len(title) <= 60, len(title)
    desc = ("V vseh štirih letih, ko je bila prva noč z mrazom oktobra, je bil vrh opažanj gob po njej. Slana ni konec sezone. Podatki 2020–2025.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Prva slana ni konec sezone", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — november", "heading": "Val se umiri v prvem tednu novembra", "id": "november", "paragraphs": p2},
        {"label": "03 — tla", "heading": "Tla se ohladijo pozneje kot zrak", "id": "tla", "paragraphs": p3},
        {"label": "04 — zimske vrste", "heading": "Po jeseni pridejo zimske vrste", "id": "zimske", "paragraphs": p4},
        {"label": "05 — letos", "heading": "Kaj kaže letošnja jesen?", "id": "letos", "paragraphs": letos},
        {"label": "06 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
        {"label": "07 — nabiranje", "heading": "Kaj to pomeni za nabiranje?", "id": "nabiranje", "paragraphs": p6},
    ]

    def nb(h):                                    # »0 °C«, »38 %« se ne smeta prelomiti čez vrstico
        return re.sub(r"(\d) (°C|%)", lambda m: m.group(1) + NBSP + m.group(2), h)
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "slana", "iNaturalist", "oktober", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "gobe-lastna", "og_accent_hex": "#34d399",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": (f"Viri: postaja IREICA1 (najnižja dnevna temperatura, zunanji senzor, od 7. 11. 2019); iNaturalist (API, število opažanj po tednih v Sloveniji; "
                         f"deblo Basidiomycota; stanje {int(gen[8:10])}. {int(gen[5:7])}. {gen[:4]}); Open-Meteo (ERA5-Land, temperatura tal, točka Rečica ob Savinji); "
                         "baza vrst gobarskega modela Meteorec. Podatki: data/inat-glive-po-tednih.json, data/tla-temperatura-dnevna.json."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</tr>", "\n", h)
        h = re.sub(r"</t[hd]>", " | ", h)
        h = re.sub(r"</?(h3|figcaption|li|p)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace("&shy;", "").replace(NBSP, " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        for p in s["paragraphs"]:
            out.append(clean(p))
            out.append("")
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    if "--fetch-tla" in sys.argv:
        fetch_tla()
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    H, I, wk, soil, soil_meta = load()
    article = build_article(H, I, wk, soil, soil_meta)
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
        og_title="Ali prva slana\nkonča gobe?", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
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
