#!/usr/bin/env python3
"""
tools/generate_temperature_gobe_post.py -- »Tla so 7 °C: za jurčka še toplo, za lisičko ne več« (9. 11. 2026).

Ročno napisan podatkovni članek (nadaljevanje članka o slani, `slana-gobarska-sezona-1018`). Vse številke v besedilu,
grafih in tabelah pridejo iz committanih virov:
  - history.json                       (postaja IREICA1: samo zunanja polja tempAvg/tempHigh/tempLow/precipTotal),
  - data/tla-temperatura-dnevna.json   (Open-Meteo archive, ERA5-Land, povprečje plasti 0-7 in 7-28 cm;
                                        `--fetch-tla` ga dopolni do danes -2 dni; samo dnevna povprečja),
  - napoved-modela.json                (MTR, zamrznjena dnevna napoved: najnižja temperatura in verjetnost zmrzali),
  - species_rules.yaml                 (pragovi vrst v gobarskem modelu; isti trapez kot `gobe_model.trapezoid`).
Besedilo nič ne izmišljuje; trditve varujejo assert-i: če se podatki osvežijo in trditev ne drži več, generator pade --
besedilo je treba pregledati, ne zaobiti asserta.

Članek je posnetek na dan objave in se ne prepisuje samodejno. Po CLAUDE.md gre ročni članek skozi lekturo (`lektura.yml`
je od 2. 10. 2026 izklopljena -- do ponovnega vklopa ostane slogovni pregled po docs/slog-pisanja.md in
`python3 tools/lektura_scan.py`). Notranjih meritev postaje članek ne uporablja. Števila opaženih gob (iNaturalist) ne
uporablja: podatkov za zadnje tedne ni mogoče osvežiti, članek pa govori samo o temperaturi.

Usage:
    python3 tools/generate_temperature_gobe_post.py [--fetch-tla] [--dry-run] [--text] [--wire] [--force]
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
TLA = os.path.join(ROOT, "data", "tla-temperatura-dnevna.json")
RULES = os.path.join(ROOT, "species_rules.yaml")
MODEL = os.path.join(ROOT, "napoved-modela.json")
SLUG = "temperature-za-gobe-se-ustrezajo-1109"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-temperature-gobe.txt")
NBSP = " "
LAT, LON = 46.3167, 14.9167                              # Rečica ob Savinji (kot v gobarskem modelu: dno doline)
GREEN, AMBER, CYAN, GREY = "#34d399", "#fbbf24", "#22d3ee", "#8aa0bd"
VIOLET, BLUE = "#a78bfa", "#60a5fa"
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
SURFACE = "#0a0f1c"
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LAST = 2026
THR_HI, THR_LO = 7.5, 3.5                                # 7,5 °C: lisička/marela; 3,5 °C: jurček/sirovka
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


_NOM = ["nič", "ena", "dve", "tri", "štiri", "pet", "šest", "sedem", "osem", "devet", "deset"]
_GEN = ["nič", "ene", "dveh", "treh", "štirih", "petih", "šestih", "sedmih", "osmih", "devetih", "desetih"]


def numw(n):
    return _NOM[int(n)] if 2 <= int(n) <= 10 else str(int(n))


def numg(n):
    return _GEN[int(n)] if 2 <= int(n) <= 10 else str(int(n))


def D(s):
    return datetime.date.fromisoformat(s)


def joined(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " in " + items[-1]


# ───────────────────────── podatki ─────────────────────────

def fetch_tla():
    """Dopolni dnevna povprečja temperature tal (0-7 in 7-28 cm, povprečje obeh) za Rečico od 1. 10. letos do danes -2 dni."""
    import urllib.request
    end = datetime.date.today() - datetime.timedelta(days=2)
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=%s&longitude=%s&start_date=%d-10-01&end_date=%s"
           "&hourly=soil_temperature_0_to_7cm,soil_temperature_7_to_28cm&timezone=Europe%%2FLjubljana" % (LAT, LON, LAST, end))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    h = json.load(urllib.request.urlopen(req, timeout=90))["hourly"]
    day = {}
    for ts, a, b in zip(h["time"], h["soil_temperature_0_to_7cm"], h["soil_temperature_7_to_28cm"]):
        if a is None or b is None:
            continue
        day.setdefault(ts[:10], []).append((a + b) / 2)
    new = {d: round(sum(v) / len(v), 2) for d, v in sorted(day.items()) if len(v) >= 20}
    doc = json.load(open(TLA, encoding="utf-8"))
    doc["dnevi"].update(new)
    doc["dnevi"] = dict(sorted(doc["dnevi"].items()))
    doc["_meta"]["generirano"] = datetime.date.today().isoformat()
    with open(TLA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {os.path.relpath(TLA, ROOT)}: dopolnjenih {len(new)} dni, zadnji {max(new)}")


def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    H = {k: v for k, v in H.items() if v.get("src") != "era5"}          # reanaliza ni meritev postaje
    T = json.load(open(TLA, encoding="utf-8"))
    return H, T["dnevi"], T["_meta"]


def soil_cross(soil, y, thr):
    """Prvi dan od 1. 10., ko je sedemdnevno povprečje temperature tal pod pragom (isto merilo kot v članku o slani)."""
    for d in sorted(k for k in soil if k.startswith(str(y))):
        if d < f"{y}-10-01":
            continue
        x = D(d)
        vals = [soil.get((x - datetime.timedelta(k)).isoformat()) for k in range(7)]
        if None in vals:
            continue
        if sum(vals) / 7 < thr:
            return x
    return None


def mean(vals):
    vals = list(vals)
    return sum(vals) / len(vals)


def rng(y, m1, d1, m2, d2):
    a, b = datetime.date(y, m1, d1), datetime.date(y, m2, d2)
    return [(a + datetime.timedelta(i)).isoformat() for i in range((b - a).days + 1)]


def trapezoid(x, lo, opt_lo, opt_hi, hi):
    """Enako kot gobe_model.trapezoid: 0 pod lo in nad hi, 1 med opt_lo in opt_hi, vmes linearno."""
    if x is None or x <= lo or x >= hi:
        return 0.0
    if x < opt_lo:
        return (x - lo) / (opt_lo - lo)
    if x > opt_hi:
        return (hi - x) / (hi - opt_hi)
    return 1.0


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def windows_chart(rows, w=460):
    """rows = [dict(ime, kind, curve, cur, f)] -- temperaturno okno vrste (svetel trak: od najnižje do najvišje, temen: optimalno)
    in trenutna temperatura (polna oznaka = v razponu, prazna = izven razpona)."""
    pl, pr, pt, pb = 118, 14, 14, 32
    rh = 28
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    lo, hi = -5, 25
    X = lambda t: pl + iw * (t - lo) / (hi - lo)
    base = pt + rh * len(rows)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Temperaturno okno vrst v gobarskem modelu in trenutna temperatura tal oziroma zraka" '
         'xmlns="http://www.w3.org/2000/svg">']
    for t in (-5, 0, 5, 10, 15, 20, 25):
        x = X(t)
        zero = t == 0
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{MUTED if zero else GRID}" stroke-width="{1.4 if zero else 1}"'
                 + (' stroke-dasharray="4 3" stroke-opacity=".7"' if zero else "") + "/>")
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{str(t).replace("-", "–")}{NBSP}°C</text>')
    for i, r in enumerate(rows):
        cy = pt + rh * i + rh / 2
        col = GREEN if r["kind"] == "tla" else CYAN
        lo_, ol, oh, hi_ = r["curve"]
        nm = r["ime"][0].upper() + r["ime"][1:]
        p.append(f'<text x="{pl - 10}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{nm}</text>')
        p.append(f'<rect x="{X(lo_):.1f}" y="{cy - 5:.1f}" width="{X(hi_) - X(lo_):.1f}" height="10" rx="5" fill="{col}" fill-opacity=".20"/>')
        p.append(f'<rect x="{X(ol):.1f}" y="{cy - 5:.1f}" width="{X(oh) - X(ol):.1f}" height="10" rx="3" fill="{col}" fill-opacity=".50"/>')
        inside = r["f"] > 0
        fill, stroke = (INK, SURFACE) if inside else (SURFACE, AMBER)
        tip = (f'{nm}: {"tla" if r["kind"] == "tla" else "zrak"} {num(r["cur"])} °C, razpon {num(lo_)}–{num(hi_)} °C, '
               f'optimalno {num(ol)}–{num(oh)} °C; {"v razponu" if inside else "izven razpona"}').replace(" -", " –")
        x = X(r["cur"])
        if r["kind"] == "tla":
            p.append(f'<circle cx="{x:.1f}" cy="{cy:.1f}" r="6" fill="{fill}" stroke="{stroke}" stroke-width="2"><title>{tip}</title></circle>')
        else:
            p.append(f'<rect x="{x - 5.5:.1f}" y="{cy - 5.5:.1f}" width="11" height="11" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="2"><title>{tip}</title></rect>')
    p.append("</svg>")
    return "".join(p)


def years_chart(rows, w=460):
    """rows = [(leto, tla 1.-7. 11.)] -- stolpec na leto, navpični črti pri pragovih 7,5 in 3,5 °C."""
    pl, pr, pt, pb = 40, 40, 22, 28
    rh = 26
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    top = 14
    X = lambda v: pl + iw * v / top
    base = pt + rh * len(rows)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Povprečna temperatura tal od 1. do 7. novembra po letih in pragova 3,5 in 7,5 stopinje" '
         'xmlns="http://www.w3.org/2000/svg">']
    for t in (0, 4, 8, 12):
        x = X(t)
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{t}{NBSP}°C</text>')
    for thr, col, lab, anchor in ((THR_LO, BLUE, "3,5", "end"), (THR_HI, AMBER, "7,5", "start")):
        x = X(thr)
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt - 6}" y2="{base}" stroke="{col}" stroke-width="1.8" stroke-dasharray="5 3"/>')
        p.append(f'<text x="{x + (-4 if anchor == "end" else 4):.1f}" y="{pt - 9}" text-anchor="{anchor}" font-size="10.5" font-weight="700" fill="{col}">{lab}{NBSP}°C</text>')
    for i, (y, v) in enumerate(rows):
        y0 = pt + rh * i
        now = y == LAST
        p.append(f'<text x="{pl - 8}" y="{y0 + rh / 2 + 4:.1f}" text-anchor="end" font-size="11.5" font-weight="{700 if now else 400}" fill="{INK}">{y}</text>')
        p.append(f'<rect x="{pl}" y="{y0 + 5:.1f}" width="{X(v) - pl:.1f}" height="{rh - 10}" rx="3" fill="{GREEN if now else GREY}" fill-opacity="{1 if now else .65}">'
                 f'<title>{y}: tla 1.–7. 11., povprečje {num(v)} °C</title></rect>')
        p.append(f'<text x="{X(v) + 5:.1f}" y="{y0 + rh / 2 + 4:.1f}" font-size="10.5" font-weight="{700 if now else 400}" fill="{INK}">{num(v)}</text>')
    p.append("</svg>")
    return "".join(p)


def season_chart(H, soil, w=460):
    """Dnevna temperatura tal in povprečna temperatura zraka od 1. 10. do zadnjega dne, pragova 7,5 in 3,5 °C,
    noči z 0 °C ali manj kot rombi na spodnji osi."""
    pl, pr, pt, pb = 40, 14, 14, 34
    h = 230
    iw, ih = w - pl - pr, h - pt - pb
    d0 = datetime.date(LAST, 10, 1)
    dN = D(max(H))
    span = (dN - d0).days
    lo, hi = 0, 17
    X = lambda d: pl + iw * (d - d0).days / span
    Y = lambda t: pt + ih * (1 - (t - lo) / (hi - lo))
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Temperatura tal in zraka v Rečici od 1. oktobra do 8. novembra 2026" '
         'xmlns="http://www.w3.org/2000/svg">']
    for t in (0, 4, 8, 12, 16):
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{pl - 6}" y="{Y(t) + 4:.1f}" text-anchor="end" font-size="10.5" fill="{MUTED}">{t}</text>')
    for m, d, lab in ((10, 1, "1. 10."), (10, 15, "15. 10."), (11, 1, "1. 11.")):
        x = X(datetime.date(LAST, m, d))
        p.append(f'<text x="{x:.1f}" y="{h - 8}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{lab}</text>')
    for thr, col, lab in ((THR_HI, AMBER, "7,5 °C: lisička, marela"), (THR_LO, BLUE, "3,5 °C: jurček, sirovka")):
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(thr):.1f}" y2="{Y(thr):.1f}" stroke="{col}" stroke-width="1.6" stroke-dasharray="5 3"/>')
        p.append(f'<text x="{pl + 4}" y="{Y(thr) - 5:.1f}" font-size="10.5" font-weight="700" fill="{col}">{lab}</text>')
    air = [(D(k), v["tempAvg"]) for k, v in sorted(H.items()) if k >= f"{LAST}-10-01" and v.get("tempAvg") is not None]
    p.append('<polyline fill="none" stroke="%s" stroke-width="1.4" stroke-opacity=".85" stroke-linejoin="round" points="%s"><title>zrak: dnevno povprečje, postaja IREICA1</title></polyline>'
             % (GREY, " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in air)))
    sl = [(D(k), v) for k, v in sorted(soil.items()) if k >= f"{LAST}-10-01"]
    p.append('<polyline fill="none" stroke="%s" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" points="%s"><title>tla: dnevno povprečje, ERA5-Land</title></polyline>'
             % (VIOLET, " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in sl)))
    for k, v in sorted(H.items()):
        if k >= f"{LAST}-10-01" and v.get("tempLow") is not None and v["tempLow"] <= 0:
            x, y = X(D(k)), Y(0)
            p.append(f'<path d="M{x:.1f},{y - 6.5:.1f} L{x + 5.5:.1f},{y:.1f} L{x:.1f},{y + 6.5:.1f} L{x - 5.5:.1f},{y:.1f} Z" fill="{CYAN}" stroke="{SURFACE}" stroke-width="1.5">'
                     f'<title>{dm(D(k))}: najnižja temperatura {temp(v["tempLow"])}</title></path>')
    p.append("</svg>")
    return "".join(p)


def legend(entries):
    out = []
    for n, kind, c in entries:
        cls = {"dia": "vs-dia", "dot": "vs-dot", "ring": "vs-ring", "line": "vs-line", "dash": "vs-dash"}.get(kind, "")
        if kind in ("ring", "dash"):
            sw = f'<i class="{cls}" style="border-color:{c}"></i>'
        elif kind == "hollow":
            sw = f'<i class="vs-dot" style="background:{SURFACE};border:2px solid {c}"></i>'
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
.vs-leg i.vs-line{height:.2rem;border-radius:2px;vertical-align:.2rem;width:1.1rem}
.vs-leg i.vs-dash{height:0;background:none;border:0;border-top:2px dashed;border-radius:0;vertical-align:.25rem;width:1.1rem}
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
.vs-card b{display:block;font-family:'Space Grotesk',sans-serif;font-size:1.45rem;line-height:1.15;color:var(--text);font-weight:700;white-space:nowrap}
.vs-card span{display:block;margin-top:.3rem;font-size:.78rem;line-height:1.35;color:var(--muted)}
.vs-gal{margin:1.4rem 0}
.vs-gal-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem}
.vs-gal-grid img{display:block;width:100%;height:auto;aspect-ratio:3/4;object-fit:cover;border-radius:12px}
.vs-gal figcaption{color:var(--muted);font-size:.85rem;line-height:1.5;margin-top:.6rem}
.vs-more{margin:.6rem 0 1.2rem}
.vs-more summary{cursor:pointer;color:var(--blue);font-size:.9rem}
h3.vs-h3,.post-body h3{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;margin:1.6rem 0 .4rem}
</style>"""


# Fotografije so Filipove (img/blog/<slug>/foto-N.jpg, 720 × 960, brez EXIF; originala 3072 × 4096 v repozitorij ne gresta).
# Datum in kraj posnetka nista znana, zato podpis ju ne navaja.
PHOTOS = [
    ("foto-1.jpg", "Jurček z rjavim klobukom, zelenkasto cevkasto trosovnico in belim betom v dlani, v ozadju jesenski gozd."),
    ("foto-2.jpg", "Gozdna pot, posuta z bukovim listjem, med rumeno obarvanimi drevesi jeseni."),
]


def gallery_html():
    imgs = "".join(f'<img src="/img/blog/{SLUG}/{f}" alt="{alt}" width="720" height="960" loading="lazy">' for f, alt in PHOTOS)
    return (f'<figure class="vs-gal"><div class="vs-gal-grid">{imgs}</div>'
            '<figcaption>Jurček in gozdna pot v jesenskem gozdu. Foto: Filip Eremita.</figcaption></figure>')


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


def stat_cards(items):
    return '<div class="vs-cards">' + "".join(f'<div class="vs-card"><b>{v}</b><span>{lab}</span></div>' for v, lab in items) + "</div>"


# ───────────────────────── članek ─────────────────────────

# (id, ime v besedilu, merilo): sezona v bazi mora zajeti 9. november
SPECIES = [
    ("cantharellus_cibarius", "navadna lisička", "tla"), ("macrolepiota_procera", "marela", "tla"),
    ("imleria_badia", "kostanjevka", "tla"), ("hydnum_repandum", "rumeni ježek", "tla"),
    ("boletus_edulis", "jurček", "tla"), ("lactarius_deliciosus", "užitna sirovka", "tla"),
    ("craterellus_tubaeformis", "lijasta lisička", "tla"), ("hygrophorus_hypothejus", "zimska polževka", "tla"),
    ("tricholoma_portentosum", "zimska kolobarnica", "tla"),
    ("armillaria_mellea", "štorovka", "zrak"), ("pleurotus_ostreatus", "bukov ostrigar", "zrak"),
    ("flammulina_velutipes", "zimska panjevka", "zrak"),
]


def species_rows(soil_now, air_now, today):
    import yaml
    cfg = yaml.safe_load(open(RULES, encoding="utf-8"))
    sp = {s["id"]: s for s in cfg["species"]}
    shoulder = float(cfg["scoring"]["temperature"]["air_shoulder_c"])
    rows = []
    for sid, name, how in SPECIES:
        s = sp[sid]
        assert s.get("verified") is True and s.get("gets_index") is True, sid
        a, b = s["season"]["start"], s["season"]["end"]
        md = f"{today.month:02d}.{today.day:02d}"
        in_season = (a <= md <= b) if a <= b else (md >= a or md <= b)
        assert in_season, (sid, "ni v sezoni", a, b)
        assert (s.get("ecology") == "lesna") == (how == "zrak"), sid       # isto merilo kot v gobe_model.eval_species
        if how == "zrak":
            at = s["air_temp"]
            curve = (at["min"] - shoulder, at["min"], at["max"], at["max"] + shoulder)
            cur = air_now
        else:
            st = s["soil_temp"]
            curve = (st["min"], st["opt_low"], st["opt_high"], st["max"])
            cur = soil_now
        rows.append(dict(id=sid, ime=name, kind=how, curve=tuple(float(x) for x in curve), cur=cur,
                         f=trapezoid(cur, *curve)))
    return rows


def build_article(H, soil):
    last = D(max(H))
    assert last == datetime.date(2026, 11, 8), f"podatki postaje segajo do {last} -- članek je vezan na posnetek 8. 11."
    assert max(soil) == "2026-11-07", f"tla segajo do {max(soil)} -- zaženi z --fetch-tla"
    mdl = json.load(open(MODEL, encoding="utf-8"))

    # ── zrak in tla po letih ──
    yrs = YEARS + [LAST]
    air15 = {y: mean(H[d]["tempAvg"] for d in rng(y, 10, 25, 11, 8)) for y in yrs}
    hi8 = {y: max(H[d]["tempHigh"] for d in rng(y, 11, 1, 11, 8)) for y in yrs}
    lo8 = {y: min(H[d]["tempLow"] for d in rng(y, 11, 1, 11, 8)) for y in yrs}
    s17 = {y: mean(soil[d] for d in rng(y, 11, 1, 11, 7)) for y in yrs}
    for y in yrs:
        assert all(d in H for d in rng(y, 10, 25, 11, 8)), y
    # trditve
    assert air15[LAST] == min(air15.values()) and air15[LAST] < sorted(air15.values())[1], air15
    others = [air15[y] for y in YEARS]
    assert s17[LAST] == min(s17.values()), s17
    assert hi8[LAST] < min(hi8[y] for y in YEARS) and hi8[LAST] == 11.0 and min(hi8[y] for y in YEARS) == 15.4, hi8
    colder_nights = [y for y in YEARS if lo8[y] < lo8[LAST]]
    assert lo8[LAST] == 0.4 and len(colder_nights) == 4, (lo8, colder_nights)
    frost_since = [d for d in sorted(H) if d >= "2026-10-01" and H[d]["tempLow"] is not None and H[d]["tempLow"] <= 0]
    assert frost_since == ["2026-10-23", "2026-10-27", "2026-10-28"], frost_since
    assert H["2026-10-23"]["tempLow"] == -0.1 and H["2026-10-22"]["precipTotal"] == 21.8

    soil_w = mean(soil[d] for d in rng(LAST, 11, 1, 11, 7))
    air_w = mean(H[d]["tempAvg"] for d in rng(LAST, 11, 2, 11, 8))
    assert 3.0 < soil_w - THR_LO and THR_HI - soil_w > 0.3 and 0.5 < soil_w - 6.5 < 1.0, soil_w
    drops = sorted((soil[f"{LAST}-10-{d:02d}"] - soil[f"{LAST}-10-{d - 1:02d}"], d) for d in range(2, 32))
    assert drops[0][1] == 23 and drops[0][0] < -2.5, drops[:2]
    since23 = [soil[d] for d in rng(LAST, 10, 23, 11, 7)]
    assert round(min(since23), 1) == 6.6 and round(max(since23), 1) == 8.9, (min(since23), max(since23))

    # ── mraz v zraku in tla v letih 2024 in 2025 ──
    for y in (2024, 2025):
        assert all(H[d]["tempLow"] <= 0 for d in rng(y, 11, 4, 11, 6)), y
        assert 6.0 < soil[f"{y}-11-07"] < 7.0, (y, soil[f"{y}-11-07"])
    low2425 = {y: min(H[d]["tempLow"] for d in rng(y, 11, 4, 11, 6)) for y in (2024, 2025)}

    # ── preboji pragov ──
    cross = {y: (soil_cross(soil, y, THR_HI), soil_cross(soil, y, THR_LO)) for y in YEARS}
    gaps = {y: (b - a).days for y, (a, b) in cross.items()}
    c26 = soil_cross(soil, LAST, THR_HI)
    assert c26 == datetime.date(2026, 11, 2) and soil_cross(soil, LAST, THR_LO) is None
    assert min(gaps.values()) == 7 and max(gaps.values()) == 27, gaps
    assert all(cross[y][1] >= datetime.date(y, 11, 17) for y in YEARS)
    by29 = [y for y in YEARS if cross[y][1] <= datetime.date(y, 11, 29)]
    assert by29 == [2020, 2021, 2024, 2025], by29

    # ── vrste ──
    rows = species_rows(soil_w, air_w, last + datetime.timedelta(days=1))
    by = {r["ime"]: r for r in rows}
    full = [r["ime"] for r in rows if r["f"] >= 1.0]
    part = [r["ime"] for r in rows if 0 < r["f"] < 1.0]
    none = [r["ime"] for r in rows if r["f"] <= 0]
    assert none == ["navadna lisička", "marela"], none
    assert {"jurček", "užitna sirovka"} <= set(full), full
    assert by["jurček"]["f"] == 1.0 and by["štorovka"]["f"] < 1.0, by["štorovka"]
    chart_rows = sorted([r for r in rows if r["kind"] == "tla"], key=lambda r: -r["curve"][0]) + \
        sorted([r for r in rows if r["kind"] == "zrak"], key=lambda r: -r["curve"][0])

    # ── napoved MTR ──
    fdays = {r["date"]: r for r in mdl["days"]}
    f3 = [fdays[d] for d in ("2026-11-10", "2026-11-11", "2026-11-12")]
    assert all(r["p_frost"] is not None and r["p_frost"] < 0.005 for r in f3)
    fmin, fmax = min(r["tmin"] for r in f3), max(r["tmin"] for r in f3)
    assert (fmin, fmax) == (5.6, 8.9), (fmin, fmax)

    nb = lambda h: re.sub(r"(\d) (°C|%)", lambda m: m.group(1) + NBSP + m.group(2), h)

    cap1 = lambda s: s[0].upper() + s[1:]
    assert all(d.startswith("2026-10-") for d in frost_since)
    frost_days = [f"{int(d[8:])}." for d in frost_since]
    frost_txt = ", ".join(frost_days[:-1]) + " in " + frost_days[-1] + " oktober"

    lead = (f"V prvih sedmih dneh novembra je bila povprečna temperatura tal v Rečici {temp(soil_w)}. "
            "Po temperaturnih pragovih iz baze vrst gobarskega modela Meteorec je to še dovolj za jurčka, užitno sirovko in nekatere zimske vrste, "
            f"ne pa več za navadno lisičko in marelo, katerih spodnji temperaturni prag je {temp(THR_HI)}. "
            f"Tla so za ta čas najhladnejša v zadnjih sedmih letih, vendar so še vedno več kot 3{NBSP}°C nad spodnjim pragom za jurčka ({temp(THR_LO)}).")

    cards = stat_cards([
        (temp(soil_w), "povprečna temperatura tal od 1. do 7. novembra (ERA5-Land)"),
        (temp(air15[LAST]), "povprečna temperatura zraka od 25. oktobra do 8. novembra (postaja IREICA1)"),
        (f"{len(frost_since)} noči", f"število noči z 0{NBSP}°C ali manj od 1. oktobra: {frost_txt}"),
        (temp(lo8[LAST]), "najnižja temperatura zraka od 1. do 8. novembra"),
    ])
    f_win = fig("Pri kateri temperaturi model še dopušča rast",
                legend([("temperatura tal (mikorizne vrste in razkrojevalke)", "dot", GREEN), ("temperatura zraka (lesne vrste)", "sq", CYAN),
                        ("trenutna temperatura je znotraj temperaturnega razpona vrste", "dot", INK), ("temperatura je zunaj razpona vrste", "hollow", AMBER)])
                + windows_chart(chart_rows),
                f"Svetli pas prikazuje temperaturno območje, v katerem model dopušča rast, temni pa optimalno območje. Oznaka prikazuje povprečje zadnjih sedmih dni: "
                f"temperatura tal {temp(soil_w)} (od 1. do 7. novembra), temperatura zraka {temp(air_w)} (od 2. do 8. novembra). "
                "Pri lesnih vrstah odloča temperatura zraka, pri preostalih pa temperatura tal. "
                "Temperaturni razponi in optimalna območja so parametri modela (species_rules.yaml), ne rezultati meritev.")
    ordered = lambda names: [n for n in (r["ime"] for r in chart_rows) if n in names]
    t_full = (f"V optimalnem temperaturnem območju so po modelu {joined(ordered(full))}. "
              f"Pod optimalnim območjem, vendar še nad spodnjo temperaturno mejo, so {joined(ordered(part))}. "
              f"{cap1(joined(ordered(none)))} sta zunaj temperaturnega razpona, v katerem model dopušča rast.")

    p1 = [
        "<strong>Kratek odgovor: za večino poznojesenskih vrst da, za vrste, ki potrebujejo toplejša tla, pa ne.</strong> "
        f"Temperatura tal je že pod spodnjim pragom za navadno lisičko in marelo ({temp(THR_HI)}), "
        f"še vedno pa je nad pragom za jurčka in užitno sirovko ({temp(THR_LO)}).",
        cards,
        f"Jurček je tik nad spodnjo mejo svojega optimalnega temperaturnega območja (6,5{NBSP}°C). Če se tla ohladijo še za več kot pol stopinje, "
        "bo model temperaturo uvrstil pod optimalno območje, vendar bo rast še vedno dopuščal.",
        f_win,
        t_full,
    ]

    t_years = table(["Leto", "Povprečna temperatura zraka, 25. 10.–8. 11.", "Najvišja temperatura zraka, 1.–8. 11.",
                     "Najnižja temperatura zraka, 1.–8. 11.", "Povprečna temperatura tal, 1.–7. 11."],
                    [[str(y), temp(air15[y]), temp(hi8[y]), temp(lo8[y]), temp(s17[y])] for y in yrs],
                    now_label=str(LAST), cap="Temperatura zraka in tal v prvem tednu novembra po letih",
                    note="Podatki o zraku: postaja IREICA1, dnevna povprečja ter najvišje in najnižje dnevne temperature. "
                         "Podatki o tleh: povprečje temperature plasti od 0 do 7 cm in od 7 do 28 cm, Open-Meteo (ERA5-Land).")
    t_years = '<details class="vs-more"><summary>Vse številke po letih (tabela)</summary>' + t_years + '</details>'
    f_years = fig("Temperatura tal v prvem tednu novembra po letih",
                  legend([("pod pragom navadne lisičke in marele (7,5 °C)", "dash", AMBER), ("nad pragom jurčka in sirovke (3,5 °C)", "dash", BLUE)])
                  + years_chart([(y, s17[y]) for y in yrs]),
                  f"Povprečna temperatura tal od 1. do 7. novembra. Letos je znašala {temp(s17[LAST])}, v preostalih šestih letih pa je bila med "
                  f"{num(min(s17[y] for y in YEARS))} in {temp(max(s17[y] for y in YEARS))}. "
                  "To je najnižja vrednost v sedmih letih, vendar je še vedno nad temperaturnim pragom za jurčka.")
    p2 = [
        f"Povprečna temperatura zraka je bila od 25. oktobra do 8. novembra {temp(air15[LAST])}. V preostalih šestih letih je bila v istem obdobju med "
        f"{num(min(others))} in {temp(max(others))}.",
        f"Dnevi so bili hladni: najvišja temperatura je od 1. do 8. novembra dosegla le {temp(hi8[LAST])}, medtem ko je v drugih letih znašala vsaj {temp(min(hi8[y] for y in YEARS))}. "
        f"Noči pa niso bile posebej mrzle. Najnižja temperatura je bila {temp(lo8[LAST])}, v {numg(len(colder_nights))} od preostalih šestih let pa je bila še nižja.",
        f_years,
        t_years,
    ]

    f_season = fig("Temperatura tal in zraka od 1. oktobra",
                   legend([("temperatura tal (dnevno povprečje)", "line", VIOLET), ("temperatura zraka (dnevno povprečje)", "line", GREY),
                           ("noč s temperaturo 0 °C ali manj", "dia", CYAN)]) + season_chart(H, soil),
                   "Ohladitev 23. oktobra je prinesla največji enodnevni padec temperature tal od 1. oktobra.")
    p3 = [
        f"Tla so se najbolj ohladila 23. oktobra: njihova povprečna temperatura je v enem dnevu padla z {num(soil['2026-10-22'])} na {temp(soil['2026-10-23'])}. "
        f"Dan prej je padlo {num(H['2026-10-22']['precipTotal'])} mm dežja, 23. oktobra pa je postaja izmerila {temp(H['2026-10-23']['tempLow'])}. "
        'V <a href="/blog/slana-gobarska-sezona-1018.html" style="color:var(--blue)">članku o slani</a> sem 18. oktobra zapisal, '
        "da prva noč s temperaturo 0 °C ali manj še ni nastopila. Dočakali smo jo pet dni pozneje.",
        f_season,
        f"Od 23. oktobra se temperatura tal ne znižuje več: giblje se med {num(min(since23))} in {temp(max(since23))}. "
        "Zrak se običajno ohladi hitreje kot tla, zato nekaj mrzlih noči še ne pomeni, da so se ohladila tudi tla.",
        f"Leta 2024 in 2025 so bile od 4. do 6. novembra tri zaporedne noči s temperaturo 0 °C ali manj. "
        f"Najnižja temperatura je v teh nočeh znašala {num(low2425[2024])} oziroma {temp(low2425[2025])}, "
        f"tla pa so bila 7. novembra še vedno na {num(soil['2024-11-07'])} oziroma {temp(soil['2025-11-07'])}. "
        "Dve leti sta premalo za oblikovanje pravila, vendar kažeta, da niti tri zaporedne mrzle noči ne ohladijo tal nujno pod temperaturni prag za jurčka.",
    ]

    t_cross = table(["Leto", "Tla pod 7,5 °C", "Tla pod 3,5 °C", "Število dni med datumoma"],
                    [[str(y), dm(cross[y][0]), dm(cross[y][1]), str(gaps[y])] for y in YEARS] + [[str(LAST), dm(c26), "še ne", "–"]],
                    now_label=str(LAST), cap="Kdaj je temperatura tal padla pod pragova",
                    note="Prikazan je prvi dan od 1. oktobra, ko je sedemdnevno povprečje temperature tal padlo pod posamezni prag.")
    p4 = [
        f"Letos je temperatura tal {dlong(c26)} padla pod {temp(THR_HI)}. V preteklih letih je od padca pod ta prag do padca pod prag za jurčka "
        f"minilo od {min(gaps.values())} do {max(gaps.values())} dni. "
        f"Razpon je tako velik, da na podlagi teh podatkov ne morem napovedati, kdaj bodo tla padla pod {temp(THR_LO)}.",
        t_cross,
        "Vem le, da je sedemdnevno povprečje v vseh šestih preteklih letih ostalo nad pragom za jurčka vsaj do 17. novembra. "
        f"V {numg(len(by29))} od šestih let pa je do 29. novembra že padlo pod ta prag.",
    ]

    p5 = [
        f"Model MTR za Rečico za 10., 11. in 12. november napoveduje najnižje temperature med {num(fmin)} in {temp(fmax)}. Verjetnost zmrzali je 0{NBSP}%. "
        "Po tej napovedi temperatura do četrtka za rast gob ne bo omejitev.",
        'Ohladitev je napovedana ob koncu tedna. V <a href="/blog/sneg-v-nizinah-cetrtek-dez-sobota-1109.html" style="color:var(--blue)">članku o snegu v nižinah</a> '
        "sem zapisal, da polovica članov ansamblov za nedeljsko jutro napoveduje temperaturo 0 °C ali manj.",
        "Za četrtek in petek ansambli v istem članku napovedujejo okoli 45 mm dežja (mediana). Če se napoved uresniči, bi se ob upoštevanju časovnega zamika, "
        "ki ga gobarski model uporablja za jurčka (8–16 dni), naslednji val rasti lahko pojavil med 20. in 29. novembrom. "
        "To so zadnji dnevi sezone jurčka po koledarju v bazi vrst modela (do 30. novembra). "
        "Hkrati je to obdobje, ko je sedemdnevno povprečje temperature tal v štirih od šestih preteklih let že padlo pod 3,5 °C.",
        "Za jurčka bo zato pomembnejše vreme v drugi polovici novembra kot pa temperature v tem tednu.",
    ]

    omejitve = [
        "<ul>"
        "<li><strong>Temperatura tal je ocenjena, ne izmerjena.</strong> Podatke za Rečico prevzemam iz Open-Meteo (ERA5-Land), katerega mreža ima celice "
        "velikosti približno 10 km. V gozdu na pobočju, v senci ali na višji nadmorski višini so lahko razmere drugačne. Postaja IREICA1 temperature tal ne meri.</li>"
        "<li><strong>Temperaturni pragovi so parametri modela.</strong> Najnižja temperatura in optimalno temperaturno območje vrste v bazi nista izmerjeni meji rasti. "
        "Model na primer navadno lisičko pri 7,0 °C uvršča zunaj njenega temperaturnega razpona. To pa ne pomeni, da je v gozdu zagotovo ni.</li>"
        "<li><strong>Članek obravnava samo temperaturo.</strong> Ne pove, ali gobe trenutno rastejo. Za rast sta pomembna tudi dež in vlaga. "
        "Zato ne uporabljam števila opaženih gob, podatkov iNaturalista za zadnje tedne pa tudi nisem osvežil.</li>"
        "<li><strong>Sedem let je malo.</strong> Primerjava velja za Rečico in obdobje od leta 2020 do 2026. Razlika med 7,0 in 8,4 °C je razvidna iz teh podatkov, "
        "ne pove pa, da je letošnja jesen v dolgoročnem pogledu izjemna.</li>"
        "<li><strong>Napoved je modelska.</strong> MTR je poskusni lokalni model, ansambelske napovedi pa prikazujejo možne scenarije in njihovo zastopanost, "
        "ne zagotavljajo določenega izida.</li>"
        "</ul>",
    ]
    p7 = [
        "Praktično sporočilo: temperatura v teh dneh večine gob ne bo omejevala, izjema so vrste, ki za rast potrebujejo toplejša tla. Pred odhodom v gozd preverite "
        f'<a href="{SITE}/gobarska-napoved/danes/" style="color:var(--blue)">gobarsko napoved za svoj kraj</a> '
        f'in <a href="{SITE}/gobarska-napoved/valovi/" style="color:var(--blue)">kalkulator rasti po dežju</a>.',
        "Gobe nabirajte samo, če jih zanesljivo poznate. Tudi poznojesenske vrste imajo nevarne zamenjave. Več o njih si lahko preberete na strani "
        f'<a href="{SITE}/gobarska-napoved/strupene-gobe/" style="color:var(--blue)">Strupene gobe</a>.',
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    title = "Tla imajo 7 °C: za jurčka še dovolj toplo, za lisičko ne več"
    assert len(title) <= 60, len(title)
    desc = "Tla v Rečici imajo 7 °C: dovolj za jurčka in sirovko, premalo za lisičko. Primerjava s šestimi leti, zimske vrste in napoved."
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Za jurčka je še dovolj toplo, za lisičko ne več", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — primerjava", "heading": "Dnevi so hladni, noči pa ne posebej", "id": "primerjava", "paragraphs": p2},
        {"label": "03 — tla", "heading": "Tla so se ohladila v enem dnevu, nato pa se je ohlajanje ustavilo", "id": "tla", "paragraphs": p3},
        {"label": "04 — koliko časa še", "heading": "Kdaj bodo tla padla pod temperaturni prag za jurčka?", "id": "koliko", "paragraphs": p4},
        {"label": "05 — prihodnji teden", "heading": "Ta teden temperatura ne bo omejevala rasti, odločala bo druga polovica novembra", "id": "teden", "paragraphs": p5},
        {"label": "06 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
        {"label": "07 — nabiranje", "heading": "Kaj to pomeni za nabiranje?", "id": "nabiranje", "paragraphs": p7},
    ]
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "temperatura", "november", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "gobe-lastna", "og_accent_hex": "#34d399",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: postaja IREICA1 (dnevna povprečja in skrajne vrednosti temperature zraka, zunanji senzor); Open-Meteo (ERA5-Land, temperatura tal, "
                         "točka Rečica ob Savinji, podatki do 7. 11. 2026); model MTR (napoved, izdana 9. 11. 2026); baza vrst gobarskega modela Meteorec. "
                         "Podatki: data/tla-temperatura-dnevna.json, history.json."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</tr>", "\n", h)
        h = re.sub(r"</t[hd]>", " | ", h)
        h = re.sub(r"</?(h3|figcaption|li|p|div|b|span)[^>]*>", "\n", h)
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
    H, soil, _meta = load()
    article = build_article(H, soil)
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
        og_title="Za jurčka še toplo,\nza lisičko ne več", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead + "\n" + gallery_html(), 1)
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
