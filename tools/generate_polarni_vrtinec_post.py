#!/usr/bin/env python3
"""
tools/generate_polarni_vrtinec_post.py -- »Polarni vrtinec se je ustavil že v začetku novembra« (10. 11. 2026).

Ročno napisan članek ob članku Scientific American (4. 11. 2026). Številke pridejo iz committanih virov:
  - data/stratosfera.json          (naš izračun iz analiz in napovedi NOAA GFS: zonalni veter 10 hPa pri 60 °N,
                                    temperatura polarne kape 60–90 °N),
  - data/stratosfera-klima.json    (isti veter za zime 2021/22–2025/26, vsake 3 dni),
  - data/polarni-vrtinec-1110.json (datumi obratov vetra v našem arhivu; tools/build_polarni_vrtinec_data.py),
  - history.json                   (postaja IREICA1: SAMO zunanja povprečna in najnižja dnevna temperatura).
Zemljevida 10 hPa in video (NASA/JPL-Caltech AIRS) sta v img/blog/<slug>/.

Trditve varujejo assert-i: če se podatki osvežijo in trditev ne drži več, generator pade -- besedilo je treba
prenoviti, ne zaobiti asserta. Članek je posnetek na dan objave. Lektura prek workflowa ni opravljena (lektura.yml
je izklopljena od 2. 10. 2026); slogovni pregled po docs/slog-pisanja.md. Notranjih meritev članek ne uporablja.

Usage:
    python3 tools/generate_polarni_vrtinec_post.py [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "polarni-vrtinec-se-je-ustavil-novembra-1110"
IMG = f"/img/blog/{SLUG}"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-polarni-vrtinec.txt")
PUBLISHED = datetime.date(2026, 11, 10)
NBSP = " "
# Barve serij: reže 1 in 2 preverjene palete (skill dataviz, validate_palette.js, temna podlaga #0a0f1c: vse PASS).
BLUE, ORANGE, GREY = "#3987e5", "#d95926", "#8aa0bd"
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
SEASON0 = datetime.date(2026, 10, 1)
PREV_WINTERS = [2021, 2022, 2023, 2024, 2025]
JAN_2021 = "2021-01-05"          # obrat pred začetkom našega arhiva GFS; datum po Lee (2021, Weather)
WIN = (14, 42)                   # okno po obratu: 2–6 tednov (Met Office)

_MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
        "novembra", "decembra"]
_MES3 = ["", "jan", "feb", "mar", "apr", "maj", "jun", "jul", "avg", "sep", "okt", "nov", "dec"]


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "–\u2060")   # U+2060: minus se ne loči od števke


def sgn(x, d=1):
    return ("+" if x > 0 else "") + num(x, d)


def unit(x, u, d=1):
    return f"{num(x, d)}{NBSP}{u}"


def dlong(d):
    return f"{d.day}.{NBSP}{_MES[d.month]}"


def dm(d):
    return f"{d.day}.{NBSP}{d.month}."


def D(s):
    return datetime.date.fromisoformat(s[:10])


# ───────────────────────── podatki ─────────────────────────

def load():
    s = json.load(open(os.path.join(ROOT, "data", "stratosfera.json"), encoding="utf-8"))
    k = json.load(open(os.path.join(ROOT, "data", "stratosfera-klima.json"), encoding="utf-8"))["u60"]
    e = json.load(open(os.path.join(ROOT, "data", "polarni-vrtinec-1110.json"), encoding="utf-8"))
    H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    return s, k, e, H.get("days", H)


def season(s):
    """Letošnji zapis od 1. 10.: analiza [(datum, u60, t)], napoved [(datum, u60, t)] (brez dni, ki jih analiza že ima)."""
    hist = [(D(d), v["u60"], v.get("t")) for d, v in sorted(s["history"].items()) if D(d) >= SEASON0]
    last = hist[-1][0]
    fc = [(D(x["date"]), x["u60"], x.get("t")) for x in s["forecast"]["steps"] if D(x["date"]) > last]
    return hist, fc


def prev_winters(k):
    """{zima: [(dan od 1. 10., u60)]} za 1. 10.–31. 1.; arhiv ima vsak tretji dan."""
    out = {}
    for y in PREV_WINTERS:
        a, b = datetime.date(y, 10, 1), datetime.date(y + 1, 1, 31)
        out[y] = [((D(d) - a).days, v) for d, v in sorted(k.items()) if a <= D(d) <= b]
    return out


def interp(pts, x):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


def station_after(H, events):
    """Odstopanje povprečne dnevne temperature postaje od njenega povprečja (vsa leta, ±7 dni okoli dneva) v oknu WIN
    po vsakem obratu. Dnevi z reanalizo (src == era5) niso meritev in se ne štejejo."""
    T = {D(d): v for d, v in H.items() if v.get("src") != "era5" and v.get("tempAvg") is not None}
    years = sorted({d.year for d in T})

    def clim(day):
        vals = []
        for y in years:
            base = datetime.date(y, day.month, 28 if (day.month, day.day) == (2, 29) else day.day)
            vals += [T[base + datetime.timedelta(days=j)]["tempAvg"] for j in range(-7, 8)
                     if base + datetime.timedelta(days=j) in T]
        return statistics.mean(vals)

    rows = []
    for e in events:
        e0 = D(e)
        days = [e0 + datetime.timedelta(days=j) for j in range(WIN[0], WIN[1] + 1)]
        days = [d for d in days if d in T]
        assert len(days) >= 25, f"premalo meritev po obratu {e}"
        an = [T[d]["tempAvg"] - clim(d) for d in days]
        lows = [(T[d]["tempLow"], d) for d in days if T[d].get("tempLow") is not None]
        rows.append({"e": e0, "a": days[0], "b": days[-1], "n": len(days), "anom": statistics.mean(an),
                     "cold": sum(1 for x in an if x < 0), "low": min(lows)})
    return rows, (min(T), years)


# ───────────────────────── grafi ─────────────────────────

def _path(pts):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def line_chart(kind, w, hist, fc, prev, today):
    """Statičen SVG (deluje brez JS); JS doda križ in oblaček prek data-box. kind: 'u' (veter) ali 't' (temperatura)."""
    narrow = w < 500
    h = 290 if narrow else 330
    L, R, Tp, B = 36, (14 if narrow else 96), 18, 30
    n_days = 122 if kind == "u" else 60
    y0, y1, step = (-10, 60, 10) if kind == "u" else (-68, -52, 4)
    idx = 1 if kind == "u" else 2

    def X(day):
        return L + (w - L - R) * day / n_days

    def Y(v):
        return Tp + (h - Tp - B) * (y1 - v) / (y1 - y0)

    o = [f'<svg class="pv-svg pv-{"narrow" if narrow else "wide"}" viewBox="0 0 {w} {h}" role="img" data-k="{kind}" '
         f'data-box="{L},{Tp},{w - R},{h - B},{w},{h},{n_days},{y0},{y1}" aria-label="{{aria}}" '
         f'font-family="Inter,system-ui,sans-serif" font-size="12">']
    v = y0
    while v <= y1:
        zero = kind == "u" and v == 0
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{INK if zero else GRID}" '
                 f'stroke-width="{1.2 if zero else 1}" {'stroke-opacity=".55"' if zero else ""}/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="{MUTED}">{str(v).replace("-", "–")}</text>')
        v += step
    ticks = [(0, "1. 10."), (31, "1. 11."), (61, "1. 12."), (92, "1. 1."), (122, "31. 1.")] if kind == "u" else \
            [(0, "1. 10."), (15, "16. 10."), (31, "1. 11."), (46, "16. 11."), (60, "30. 11.")]
    if narrow and kind == "u":
        ticks = ticks[:4]
    for d, lab in ticks:
        o.append(f'<line x1="{X(d):.1f}" x2="{X(d):.1f}" y1="{h - B}" y2="{h - B + 4}" stroke="{MUTED}" stroke-opacity=".5"/>')
        anchor = "end" if d == n_days else ("start" if d == 0 else "middle")
        o.append(f'<text x="{X(d):.1f}" y="{h - 9}" text-anchor="{anchor}" fill="{MUTED}">{lab}</text>')
    unit_lab = "m/s" if kind == "u" else "°C"
    o.append(f'<text x="{L - 30}" y="11" fill="{MUTED}">{unit_lab}</text>')
    if kind == "u":
        o.append('<g class="pv-prev">')
        for y, pts in prev.items():
            o.append(f'<path d="{_path([(X(d), Y(val)) for d, val in pts])}" fill="none" stroke="{GREY}" '
                     f'stroke-width="1.2" stroke-opacity=".5"/>')
        py = statistics.mean(p[-1][1] for p in prev.values())
        if not narrow:
            o.append(f'<text x="{w - R + 8}" y="{Y(py) - 2:.1f}" fill="{MUTED}">prejšnjih</text>')
            o.append(f'<text x="{w - R + 8}" y="{Y(py) + 12:.1f}" fill="{MUTED}">pet zim</text>')
        o.append("</g>")
        o.append(f'<text x="{w - R - 4}" y="{Y(0) + 15:.1f}" text-anchor="end" fill="{MUTED}">pod črto: veter se obrne</text>')
    hp = [((d - SEASON0).days, x[idx - 1]) for d, *x in hist if x[idx - 1] is not None]
    fp = [hp[-1]] + [((d - SEASON0).days, x[idx - 1]) for d, *x in fc if x[idx - 1] is not None]
    o.append(f'<path d="{_path([(X(d), Y(val)) for d, val in hp])}" fill="none" stroke="{BLUE}" stroke-width="2.2" '
             f'stroke-linejoin="round" stroke-linecap="round"/>')
    o.append(f'<path d="{_path([(X(d), Y(val)) for d, val in fp])}" fill="none" stroke="{BLUE}" stroke-width="2" '
             f'stroke-dasharray="2 5" stroke-linecap="round"/>')
    # neposredne oznake: vrh in dno
    hi = max(hp, key=lambda p: p[1]) if kind == "u" else min(hp, key=lambda p: p[1])
    lo = next(p for p in hp if p[1] < 0) if kind == "u" else hp[-1]
    for (d, val), dy, anchor in ((hi, -9 if kind == "u" else 17, "middle"), (lo, 17 if kind == "u" else -9, "middle")):
        day = SEASON0 + datetime.timedelta(days=d)
        o.append(f'<circle cx="{X(d):.1f}" cy="{Y(val):.1f}" r="4.5" fill="{BLUE}" stroke="#0a0f1c" stroke-width="2"/>')
        o.append(f'<text x="{X(d):.1f}" y="{Y(val) + dy:.1f}" text-anchor="{anchor}" fill="{INK}" font-weight="600" '
                 f'paint-order="stroke" stroke="#0a0f1c" stroke-width="3">{num(val)} · {day.day}. {day.month}.</text>')
    ex, ey = X(fp[-1][0]), Y(fp[-1][1])
    o.append(f'<text x="{ex + 6:.1f}" y="{ey + (4 if kind == "u" else 4):.1f}" fill="{MUTED}">napoved</text>')
    o.append(f'<line class="pv-cross" x1="0" x2="0" y1="{Tp}" y2="{h - B}" stroke="{INK}" stroke-opacity=".5" visibility="hidden"/>')
    o.append(f'<circle class="pv-dot" r="5" fill="{BLUE}" stroke="#0a0f1c" stroke-width="2" visibility="hidden"/>')
    o.append("</svg>")
    return "".join(o)


def bar_chart(rows, w=440):
    h, L, R, Tp, B = 300, 34, 8, 22, 46
    y0, y1 = -3.0, 5.0
    bw = (w - L - R) / len(rows)

    def Y(v):
        return Tp + (h - Tp - B) * (y1 - v) / (y1 - y0)

    o = [f'<svg class="pv-svg pv-bars" viewBox="0 0 {w} {h}" role="img" aria-label="{{aria}}" '
         f'font-family="Inter,system-ui,sans-serif" font-size="12">']
    for v in (-2, 0, 2, 4):
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{INK if v == 0 else GRID}" '
                 f'{'stroke-opacity=".55"' if v == 0 else ""}/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="{MUTED}">{sgn(v, 0)}</text>')
    o.append(f'<text x="{L - 28}" y="12" fill="{MUTED}">°C glede na povprečje postaje</text>')
    for i, r in enumerate(rows):
        x = L + bw * i + bw * 0.2
        ww = bw * 0.6
        v = r["anom"]
        top, bot = (Y(v), Y(0)) if v >= 0 else (Y(0), Y(v))
        rr = min(4, (bot - top) / 2)
        if v >= 0:
            d = f"M{x:.1f},{bot:.1f} V{top + rr:.1f} Q{x:.1f},{top:.1f} {x + rr:.1f},{top:.1f} H{x + ww - rr:.1f} Q{x + ww:.1f},{top:.1f} {x + ww:.1f},{top + rr:.1f} V{bot:.1f} Z"
        else:
            d = f"M{x:.1f},{top:.1f} V{bot - rr:.1f} Q{x:.1f},{bot:.1f} {x + rr:.1f},{bot:.1f} H{x + ww - rr:.1f} Q{x + ww:.1f},{bot:.1f} {x + ww:.1f},{bot - rr:.1f} V{top:.1f} Z"
        tip = (f"Obrat {dm(r['e'])} {r['e'].year}|Okno: {dm(r['a'])}–{dm(r['b'])} {r['b'].year}|"
               f"Odstopanje: {sgn(v)} °C|Hladnejših dni: {r['cold']} od {r['n']}|"
               f"Najnižja temperatura: {num(r['low'][0])} °C ({dm(r['low'][1])})")
        o.append(f'<g class="pv-bar" tabindex="0" role="img" aria-label="{tip.replace("|", ", ")}" data-tip="{tip}">'
                 f'<rect x="{L + bw * i:.1f}" y="{Tp}" width="{bw:.1f}" height="{h - Tp - B}" fill="transparent"/>'
                 f'<path d="{d}" fill="{ORANGE if v >= 0 else BLUE}"/></g>')
        o.append(f'<text x="{x + ww / 2:.1f}" y="{(top - 6) if v >= 0 else (bot + 15):.1f}" text-anchor="middle" '
                 f'fill="{INK}" font-weight="600">{sgn(v)}</text>')
        o.append(f'<text x="{x + ww / 2:.1f}" y="{h - 26}" text-anchor="middle" fill="{MUTED}">{_MES3[r["e"].month]}</text>')
        o.append(f'<text x="{x + ww / 2:.1f}" y="{h - 11}" text-anchor="middle" fill="{MUTED}">{r["e"].year}</text>')
    o.append("</svg>")
    return "".join(o)


SCHEME = f"""<svg class="pv-svg pv-scheme" viewBox="0 0 480 236" role="img" aria-label="Shema: levo stabilen polarni vrtinec, ki kroži okoli tečaja in zadržuje mrzel zrak; desno porušen vrtinec, ki je raztegnjen in odmaknjen od tečaja, hladen zrak pa sega proti jugu." font-family="Inter,system-ui,sans-serif" font-size="12">
<defs><marker id="pv-arr" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>
<g>
<circle cx="120" cy="112" r="100" fill="rgba(255,255,255,.03)" stroke="{GRID}"/>
<circle cx="120" cy="112" r="46" fill="{BLUE}" fill-opacity=".38" stroke="{BLUE}" stroke-width="2"/>
<path d="M120,44 A68,68 0 1 1 119,44" fill="none" stroke="{INK}" stroke-width="1.6" stroke-dasharray="1 0" marker-end="url(#pv-arr)" stroke-opacity=".8"/>
<path d="M114,112 h12 M120,106 v12" stroke="{INK}" stroke-width="1.6"/>
<text x="120" y="136" text-anchor="middle" fill="{INK}">mrzel zrak</text>
<text x="120" y="30" text-anchor="middle" fill="{MUTED}">močan zahodni veter</text>
<text x="120" y="230" text-anchor="middle" fill="{INK}" font-weight="600" font-size="13">Stabilen vrtinec</text>
</g>
<g>
<circle cx="360" cy="112" r="100" fill="rgba(255,255,255,.03)" stroke="{GRID}"/>
<ellipse cx="338" cy="128" rx="62" ry="30" transform="rotate(-38 338 128)" fill="{BLUE}" fill-opacity=".38" stroke="{BLUE}" stroke-width="2"/>
<ellipse cx="398" cy="76" rx="30" ry="22" fill="{ORANGE}" fill-opacity=".4" stroke="{ORANGE}" stroke-width="2"/>
<path d="M360,106 v12 M354,112 h12" stroke="{INK}" stroke-width="1.6"/>
<path d="M398,112 C392,150 372,176 344,186" fill="none" stroke="{INK}" stroke-width="1.6" stroke-opacity=".8" marker-end="url(#pv-arr)"/>
<text x="400" y="80" text-anchor="middle" fill="{INK}">toplo</text>
<text x="322" y="146" text-anchor="middle" fill="{INK}">mrzel zrak</text>
<text x="360" y="30" text-anchor="middle" fill="{MUTED}">veter oslabi ali se obrne</text>
<text x="360" y="230" text-anchor="middle" fill="{INK}" font-weight="600" font-size="13">Porušen vrtinec</text>
</g>
</svg>"""


STYLE = """<style>
.pv-fig{margin:1.5rem 0;padding:1rem 1rem .85rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px;position:relative}
.pv-fig figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.7rem}
.pv-fig h3{font-family:'Space Grotesk',sans-serif;font-size:1rem;margin:0 0 .15rem;color:var(--text)}
.pv-sub{color:var(--muted);font-size:.86rem;margin:0 0 .6rem;line-height:1.45}
.pv-svg{display:block;width:100%;height:auto;margin:0 auto;touch-action:pan-y}
.pv-wide{display:none}.pv-bars{max-width:560px}.pv-scheme{max-width:560px}
@media(min-width:640px){.pv-wide{display:block}.pv-narrow{display:none}}
.pv-pane[hidden]{display:none}
.pv-ctl{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.2rem 0 .7rem}
.pv-seg{display:inline-flex;border:1px solid var(--card-border);border-radius:999px;padding:3px;background:rgba(255,255,255,.04)}
.pv-seg button,.pv-chip{font:inherit;font-size:.85rem;min-height:38px;padding:.3rem .9rem;border-radius:999px;border:0;background:none;color:var(--muted);cursor:pointer}
.pv-seg button[aria-pressed="true"]{background:#3987e5;color:#fff;font-weight:600}
.pv-chip{border:1px solid var(--card-border)}
.pv-chip[aria-pressed="true"]{color:var(--text);background:rgba(255,255,255,.08)}
.pv-seg button:focus-visible,.pv-chip:focus-visible,.pv-bar:focus-visible,.pv-range:focus-visible{outline:2px solid #fff;outline-offset:2px}
.pv-leg{display:flex;flex-wrap:wrap;gap:.35rem 1.1rem;font-size:.85rem;color:var(--muted);margin:0 0 .5rem}
.pv-leg i{display:inline-block;width:1.2rem;height:0;border-top:3px solid;margin-right:.4rem;vertical-align:.22rem}
.pv-leg i.dash{border-top-style:dotted}.pv-leg i.sq{width:.8rem;height:.8rem;border:0;border-radius:3px;vertical-align:-.08rem}
.pv-tip{position:absolute;z-index:3;pointer-events:none;background:#0d1424;border:1px solid rgba(255,255,255,.22);border-radius:10px;padding:.5rem .7rem;font-size:.84rem;line-height:1.5;color:var(--text);box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:250px}
.pv-tip b{display:block;font-weight:600}.pv-tip span{display:block;color:var(--muted)}.pv-tip span strong{color:var(--text);font-weight:600}
.pv-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin:1.3rem 0}
.pv-tile{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:.8rem .9rem}
.pv-tile b{display:block;font-family:'Space Grotesk',sans-serif;font-size:1.9rem;line-height:1.05;color:var(--text);font-variant-numeric:tabular-nums}
.pv-tile b small{font-size:.95rem;font-weight:600;color:var(--muted)}
.pv-tile span{display:block;margin-top:.35rem;font-size:.82rem;line-height:1.4;color:var(--muted)}
.pv-short{background:var(--card-bg);border:1px solid var(--card-border);border-left:4px solid #3987e5;border-radius:14px;padding:.9rem 1.1rem;margin:1.2rem 0}
.pv-short h3{font-family:'Space Grotesk',sans-serif;font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 .4rem}
.pv-short ul{margin:0;padding-left:1.1rem}.pv-short li{margin:.3rem 0}
.pv-video{display:block;width:100%;height:auto;border-radius:12px;background:#000;aspect-ratio:4/3}
.pv-cmp{position:relative;max-width:560px;margin:0 auto;display:grid;grid-template-columns:1fr 1fr;gap:.5rem}
.pv-cmp img{display:block;width:100%;height:auto;border-radius:12px}
.pv-cmp.is-on{display:block;aspect-ratio:1/1;border-radius:12px;overflow:hidden}
.pv-cmp.is-on img{position:absolute;inset:0;border-radius:0}
.pv-cmp.is-on .pv-top{clip-path:inset(0 calc(100% - var(--p,50%)) 0 0)}
.pv-cmp.is-on::after{content:"";position:absolute;top:0;bottom:0;left:var(--p,50%);width:2px;margin-left:-1px;background:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.4)}
.pv-range{display:none;width:100%;max-width:560px;margin:.7rem auto 0;min-height:38px;accent-color:#3987e5}
.pv-cmp.is-on+.pv-range{display:block}
.pv-ends{display:none;justify-content:space-between;max-width:560px;margin:0 auto;font-size:.82rem;color:var(--muted)}
.pv-cmp.is-on~.pv-ends{display:flex}
.pv-scale{max-width:560px;margin:.7rem auto 0;font-size:.8rem;color:var(--muted)}
.pv-scale i{display:block;height:10px;border-radius:5px;background:linear-gradient(90deg,#0b0724,#3b0f70,#8c2981,#de4968,#fe9f6d,#fcfdbf)}
.pv-scale div{display:flex;justify-content:space-between;margin-top:.2rem}
.pv-time{list-style:none;margin:1.2rem 0;padding:0;border-left:2px solid var(--card-border)}
.pv-time li{position:relative;padding:.1rem 0 .9rem 1.1rem}
.pv-time li::before{content:"";position:absolute;left:-7px;top:.45rem;width:12px;height:12px;border-radius:50%;background:#3987e5;border:2px solid #0a0f1c}
.pv-time li.pv-open::before{background:#0a0f1c;border-color:#3987e5}
.pv-time b{display:block;color:var(--text)}.pv-time span{color:var(--muted);font-size:.92rem}
.pv-note{color:var(--muted);font-size:.84rem;line-height:1.55;margin:.4rem 0 1.2rem}
.pv-tbl{margin-top:.6rem;font-size:.85rem;color:var(--muted)}
.pv-tbl summary{cursor:pointer;min-height:32px}
.pv-tbl table{border-collapse:collapse;width:100%;margin-top:.4rem;font-variant-numeric:tabular-nums}
.pv-tbl th,.pv-tbl td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid var(--card-border)}
.pv-src li{margin:.35rem 0}
</style>"""

SCRIPT = r"""<script>
(function(){
var el=document.getElementById('pv-data');if(!el)return;var DATA=JSON.parse(el.textContent);
function f(x,d){return x.toFixed(d==null?1:d).replace('.',',').replace('-','–');}
function tip(fig){var t=fig.querySelector('.pv-tip');if(!t){t=document.createElement('div');t.className='pv-tip';t.hidden=true;fig.appendChild(t);}return t;}
function place(t,fig,cx,cy){t.hidden=false;var fr=fig.getBoundingClientRect(),w=t.offsetWidth,h=t.offsetHeight;
var x=cx-fr.left+14;if(x+w>fr.width-6)x=cx-fr.left-w-14;if(x<6)x=6;var y=cy-fr.top-h-12;if(y<6)y=cy-fr.top+18;t.style.left=x+'px';t.style.top=y+'px';}
function dstr(day){var d=new Date(Date.UTC(2026,9,1+day));return d.getUTCDate()+'. '+(d.getUTCMonth()+1)+'. '+d.getUTCFullYear();}
/* črtna grafa */
Array.prototype.forEach.call(document.querySelectorAll('.pv-svg[data-k]'),function(svg){
var fig=svg.closest('.pv-fig'),b=svg.getAttribute('data-box').split(',').map(Number),k=svg.getAttribute('data-k');
var S=DATA[k],cross=svg.querySelector('.pv-cross'),dot=svg.querySelector('.pv-dot'),t=tip(fig);
function hide(){cross.setAttribute('visibility','hidden');dot.setAttribute('visibility','hidden');t.hidden=true;}
function move(e){var r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*b[4];
var day=Math.round((vx-b[0])/(b[2]-b[0])*b[6]);var best=null;
for(var i=0;i<S.pts.length;i++){if(best===null||Math.abs(S.pts[i][0]-day)<Math.abs(best[0]-day))best=S.pts[i];}
if(!best||Math.abs(best[0]-day)>2&&k==='t'){hide();return;}
if(k==='u'&&Math.abs(best[0]-day)>1){best=null;}
var X=b[0]+(b[2]-b[0])*day/b[6];if(day<0||day>b[6]){hide();return;}
cross.setAttribute('x1',X);cross.setAttribute('x2',X);cross.setAttribute('visibility','visible');
var h='<b>'+dstr(day)+'</b>';
if(best){var Y=b[1]+(b[3]-b[1])*(b[8]-best[1])/(b[8]-b[7]);dot.setAttribute('cx',b[0]+(b[2]-b[0])*best[0]/b[6]);dot.setAttribute('cy',Y);dot.setAttribute('visibility','visible');
h+='<span>'+(best[2]?'Napoved GFS':'Letos')+': <strong>'+f(best[1])+' '+S.unit+'</strong></span>';}
else dot.setAttribute('visibility','hidden');
if(k==='u'&&DATA.band[day]&&!fig.classList.contains('pv-noprev'))h+='<span>Prejšnjih pet zim: <strong>'+f(DATA.band[day][0],0)+' do '+f(DATA.band[day][1],0)+' m/s</strong></span>';
t.innerHTML=h;place(t,fig,e.clientX,r.top+r.height*.3);}
svg.addEventListener('pointermove',move);svg.addEventListener('pointerdown',move);svg.addEventListener('pointerleave',hide);});
/* preklop veter / temperatura */
Array.prototype.forEach.call(document.querySelectorAll('.pv-seg button'),function(btn){btn.addEventListener('click',function(){
var fig=btn.closest('.pv-fig');Array.prototype.forEach.call(fig.querySelectorAll('.pv-seg button'),function(x){x.setAttribute('aria-pressed',x===btn?'true':'false');});
Array.prototype.forEach.call(fig.querySelectorAll('.pv-pane'),function(p){p.hidden=p.getAttribute('data-pane')!==btn.getAttribute('data-show');});
var c=fig.querySelector('.pv-chip');if(c)c.hidden=btn.getAttribute('data-show')!=='u';var lp=fig.querySelector('.pv-leg-prev');if(lp)lp.hidden=btn.getAttribute('data-show')!=='u';var t=fig.querySelector('.pv-tip');if(t)t.hidden=true;});});
Array.prototype.forEach.call(document.querySelectorAll('.pv-chip'),function(c){c.hidden=false;c.addEventListener('click',function(){
var on=c.getAttribute('aria-pressed')!=='true';c.setAttribute('aria-pressed',on?'true':'false');var fig=c.closest('.pv-fig');fig.classList.toggle('pv-noprev',!on);
Array.prototype.forEach.call(fig.querySelectorAll('.pv-prev'),function(g){g.style.display=on?'':'none';});});});
Array.prototype.forEach.call(document.querySelectorAll('.pv-ctl'),function(c){c.hidden=false;});
/* stolpci */
Array.prototype.forEach.call(document.querySelectorAll('.pv-bar'),function(g){var fig=g.closest('.pv-fig'),t=tip(fig);
function show(){var p=g.getAttribute('data-tip').split('|');t.textContent='';p.forEach(function(s,i){var n=document.createElement(i?'span':'b');n.textContent=s;t.appendChild(n);});
var r=g.querySelector('path').getBoundingClientRect();place(t,fig,r.left+r.width/2,r.top);}
g.addEventListener('pointerenter',show);g.addEventListener('focus',show);g.addEventListener('click',show);
g.addEventListener('pointerleave',function(){t.hidden=true;});g.addEventListener('blur',function(){t.hidden=true;});});
/* primerjava zemljevidov */
var cmp=document.querySelector('.pv-cmp'),rng=document.querySelector('.pv-range');
if(cmp&&rng&&window.CSS&&CSS.supports('clip-path','inset(0 50% 0 0)')){cmp.classList.add('is-on');
var set=function(){cmp.style.setProperty('--p',rng.value+'%');};rng.addEventListener('input',set);set();
var drag=function(e){var r=cmp.getBoundingClientRect();rng.value=Math.max(0,Math.min(100,(e.clientX-r.left)/r.width*100));set();};
cmp.addEventListener('pointerdown',function(e){drag(e);cmp.setPointerCapture(e.pointerId);cmp.addEventListener('pointermove',drag);});
cmp.addEventListener('pointerup',function(){cmp.removeEventListener('pointermove',drag);});cmp.style.touchAction='pan-y';}
/* video: brez samodejnega predvajanja, če bralec ne želi gibanja */
var v=document.querySelector('.pv-video');if(v&&window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches){v.removeAttribute('autoplay');v.pause();}
})();
</script>"""


def fig(title, sub, inner, caption):
    return (f'<figure class="pv-fig"><h3>{title}</h3>' + (f'<p class="pv-sub">{sub}</p>' if sub else "") +
            f'{inner}<figcaption>{caption}</figcaption></figure>')


def tiles(items):
    return '<div class="pv-tiles">' + "".join(
        f'<div class="pv-tile"><b>{big}{(" <small>" + small + "</small>") if small else ""}</b><span>{text}</span></div>'
        for big, small, text in items) + "</div>"


def a(href, text):
    ext = href.startswith("http")
    return f'<a href="{href}"' + (' target="_blank" rel="noopener"' if ext else "") + f'>{text}</a>'


# ───────────────────────── članek ─────────────────────────

SRC = {
    "sciam": ("https://www.scientificamerican.com/article/the-polar-vortex-is-about-to-go-haywire/",
              "Jackie Flynn Mogensen: The polar vortex is about to go haywire. Scientific American, 4. 11. 2026"),
    "metoffice": ("https://www.metoffice.gov.uk/blog/2026/deep-dive-could-changes-high-above-the-arctic-influence-the-uks-weather",
                  "Met Office: Deep dive: Could changes high above the Arctic influence the UK’s weather?, 4. 11. 2026"),
    "metoffice_ssw": ("https://weather.metoffice.gov.uk/learn-about/weather/types-of-weather/wind/sudden-stratospheric-warming",
                      "Met Office: Sudden Stratospheric Warming (razlaga pojava)"),
    "bbc": ("https://www.bbc.com/weather/articles/cwyvrz09mnd6o",
            "Simon King: Could the earliest weakening of the polar vortex on record bring UK snow? BBC Weather, 6. 11. 2026"),
    "rte": ("https://www.rte.ie/news/a-european-perspective/2026/1109/1598587-polar-vortex/",
            "RTÉ News: Polar vortex weakening, according to data, 9. 11. 2026"),
    "gsdm": ("https://gsdmsolutions.com/blog/ssw-november-2026",
             "GSDM Weather Services: Understanding a Predicted SSW: November 2026, 29. 10. 2026"),
    "cp07": ("https://doi.org/10.1175/jcli3996.1",
             "Charlton in Polvani (2007): A New Look at Stratospheric Sudden Warmings. Journal of Climate"),
    "king": ("https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019JD030480",
             "King in sod. (2019): Observed Relationships Between Sudden Stratospheric Warmings and European Climate Extremes. JGR Atmospheres"),
    "hall": ("https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2020JD033881",
             "Hall in sod. (2021): Tracking the Stratosphere-to-Surface Impact of Sudden Stratospheric Warmings. JGR Atmospheres"),
    "lee": ("https://centaur.reading.ac.uk/97131/1/Lee%202021%20Weather%20Spotlight%20on%20SSW.pdf",
            "Lee (2021): Spotlight: the January 2021 sudden stratospheric warming. Weather"),
}


def build_article(s, k, e, H):
    hist, fc = season(s)
    prev = prev_winters(k)
    assert hist[-1][0] >= datetime.date(2026, 11, 8), "data/stratosfera.json nima analize do 8. 11. 2026"
    assert s["forecast"]["init"].startswith("2026-11-09"), "napoved GFS ni z dne 9. 11. 2026 -- besedilo preglej znova"
    peak = max(hist, key=lambda r: r[1])
    first_neg = next(r for r in hist if r[1] < 0)
    cold = min(hist, key=lambda r: r[2])
    last = hist[-1]
    fc_min = min(fc, key=lambda r: r[1])
    fc_end = fc[-1]
    days_drop = (first_neg[0] - peak[0]).days
    assert peak[0] == datetime.date(2026, 10, 24) and first_neg[0] == datetime.date(2026, 11, 6)
    assert days_drop == 13 and fc_min[1] < 0 < fc_end[1]
    warm = last[2] - cold[2]
    assert 7 < warm < 9
    d6 = (first_neg[0] - SEASON0).days
    prev6 = [interp(p, d6) for p in prev.values()]
    assert min(prev6) > 20, "prejšnje zime 6. 11. niso bile nad 20 m/s"
    # dosedanji najzgodnejši obrat v našem arhivu
    ev = {r["okno"][0][:7]: r["datum"] for r in e["obrati"]}
    assert ev["2025-11"] == "2025-11-28", "lanski obrat v našem arhivu ni 28. 11."
    lead_days = (datetime.date(2026, 11, 28) - first_neg[0]).days
    assert lead_days == 22
    events = [JAN_2021] + [r["datum"] for r in e["obrati"]]
    assert all(events) and len(events) == 7
    rows, (st_from, st_years) = station_after(H, events)
    warm_rows = [r for r in rows if r["anom"] > 0]
    cold_rows = [r for r in rows if r["anom"] < 0]
    assert len(warm_rows) == 6 and len(cold_rows) == 1 and cold_rows[0]["e"] == datetime.date(2025, 11, 28)
    cr = cold_rows[0]
    assert cr["cold"] == 25 and cr["n"] == 29
    w0, w1 = first_neg[0] + datetime.timedelta(days=WIN[0]), first_neg[0] + datetime.timedelta(days=WIN[1])
    zm = e["zemljevida"]

    # podatki za JS
    band = {}
    for day in range(0, 123):
        vals = [interp(p, day) for p in prev.values()]
        vals = [v for v in vals if v is not None]
        if len(vals) == len(prev):
            band[day] = [round(min(vals), 1), round(max(vals), 1)]
    js = {
        "u": {"unit": "m/s", "pts": [[(d - SEASON0).days, u, 0] for d, u, _t in hist] + [[(d - SEASON0).days, u, 1] for d, u, _t in fc]},
        "t": {"unit": "°C", "pts": [[(d - SEASON0).days, t, 0] for d, _u, t in hist] + [[(d - SEASON0).days, t, 1] for d, _u, t in fc]},
        "band": band,
    }
    kmh = peak[1] * 3.6

    aria_u = (f"Zonalni veter na 10 hPa pri 60 stopinjah severne širine od 1. oktobra 2026: vrh {num(peak[1])} m/s "
              f"{dm(peak[0])}, padec na {num(first_neg[1])} m/s {dm(first_neg[0])}; napoved GFS do {dm(fc_end[0])} "
              f"se vrne na {num(fc_end[1])} m/s. V prejšnjih petih zimah je bil veter 6. novembra med "
              f"{num(min(prev6), 0)} in {num(max(prev6), 0)} m/s.")
    aria_t = (f"Temperatura polarne kape na 10 hPa od 1. oktobra 2026: najnižja {num(cold[2])} °C {dm(cold[0])}, "
              f"{dm(last[0])} {num(last[2])} °C.")
    today = PUBLISHED
    charts = (
        '<div class="pv-ctl" hidden><div class="pv-seg" role="group" aria-label="Kaj kaže graf">'
        '<button type="button" data-show="u" aria-pressed="true">Veter</button>'
        '<button type="button" data-show="t" aria-pressed="false">Temperatura</button></div>'
        '<button type="button" class="pv-chip" aria-pressed="true" hidden>Prejšnje zime</button></div>'
        '<p class="pv-leg"><span><i style="border-color:#3987e5"></i>letos (analiza GFS)</span>'
        '<span><i class="dash" style="border-color:#3987e5"></i>napoved GFS z dne 9. 11.</span>'
        f'<span class="pv-leg-prev"><i style="border-color:{GREY};opacity:.7"></i>zime 2021/22–2025/26</span></p>'
        '<div class="pv-pane" data-pane="u">'
        + line_chart("u", 360, hist, fc, prev, today).replace("{aria}", aria_u)
        + line_chart("u", 680, hist, fc, prev, today).replace("{aria}", aria_u) + "</div>"
        '<div class="pv-pane" data-pane="t" hidden>'
        + line_chart("t", 360, hist, fc, prev, today).replace("{aria}", aria_t)
        + line_chart("t", 680, hist, fc, prev, today).replace("{aria}", aria_t) + "</div>")

    tbl = ("<details class=\"pv-tbl\"><summary>Številke v tabeli</summary><table><thead><tr><th>Obrat vetra</th><th>Okno</th>"
           "<th>Odstopanje</th><th>Hladnejših dni</th><th>Najnižja</th></tr></thead><tbody>" + "".join(
               f"<tr><td>{dm(r['e'])} {r['e'].year}</td><td>{dm(r['a'])}–{dm(r['b'])}</td><td>{sgn(r['anom'])}{NBSP}°C</td>"
               f"<td>{r['cold']} od {r['n']}</td><td>{unit(r['low'][0], '°C')}</td></tr>" for r in rows) + "</tbody></table></details>")
    aria_b = ("Odstopanje povprečne temperature v Rečici ob Savinji od 14. do 42. dne po obratu vetra: "
              + "; ".join(f"{dm(r['e'])} {r['e'].year} {sgn(r['anom'])} °C" for r in rows) + ".")

    lead = (f"Štiriindvajsetega oktobra je veter 30{NBSP}km nad Arktiko pihal s hitrostjo {unit(peak[1], 'm/s')}, "
            f"kar je {unit(kmh, 'km/h', 0)}. Trinajst dni pozneje se je ustavil. Tako zgodaj se to v zapisih, "
            "ki segajo v petdeseta leta, še ni zgodilo.")

    s1 = [
        '<div class="pv-short"><h3>Na kratko</h3><ul>'
        f"<li>Polarni vrtinec, pas močnih zahodnih vetrov visoko nad Arktiko, je v začetku novembra skoraj obstal. "
        f"Običajno je v tem času najmočnejše rasti.</li>"
        f"<li>Dosedanji najzgodnejši obrat vetra je bil 28.{NBSP}novembra. Letos je veter po našem izračunu padel pod "
        f"ničlo {dlong(first_neg[0])}, {lead_days} dni prej.</li>"
        "<li>Ali bo dogodek uradno obveljal za »veliko« otoplitev stratosfere, še ni potrjeno. Obrat je šibek in kratek.</li>"
        "<li>Za vreme v Sloveniji to ni napoved mraza. Vpliv, če pride, se pokaže šele po dveh do šestih tednih, "
        "letos pa mu nasprotuje še močan El Niño.</li></ul></div>",
        f"O dogodku je 4.{NBSP}novembra pisal {a(SRC['sciam'][0], 'Scientific American')}. Klimatolog Judah Cohen z MIT "
        "je za revijo dejal, da je dogodek brez primere in da je meteorološka skupnost zaradi njega vsa na nogah. "
        "Andrea Lopez Lang z Univerze Wisconsin–Madison je dodala, da bo do motnje očitno prišlo, kje se bo vse skupaj "
        "postavilo, pa je še odprto.",
        "Ker podatke o stratosferi na Meteorcu vsak dan računam sam, sem preveril, kaj kažejo. Spodaj so številke, "
        "zemljevida in primerjava s tem, kar je po prejšnjih takih dogodkih izmerila postaja v Rečici ob Savinji.",
        tiles([
            (num(peak[1]), "m/s", f"veter na 10{NBSP}hPa pri 60° s. š. {dlong(peak[0])}, najmočnejši to jesen"),
            (num(first_neg[1]), "m/s", f"isti veter {dlong(first_neg[0])}: prvič pod ničlo"),
            (sgn(warm), "°C", f"toliko se je stratosfera nad Arktiko ogrela od {dm(cold[0])} do {dm(last[0])}"),
            (str(lead_days), "dni", f"pred dosedanjim najzgodnejšim obratom (28.{NBSP}november)"),
        ]),
    ]

    s2 = [
        "Polarni vrtinec ni nevihta in ni nekaj, kar bi videli z dvorišča. Je velik krog zahodnih vetrov v stratosferi, "
        f"plasti ozračja od približno 10 do 50{NBSP}km nad tlemi. Nastane vsako jesen, ko Arktika ostane brez sonca in se "
        "zrak nad njo močno ohladi. Decembra in januarja je najmočnejši.",
        "Dokler se vrti hitro, deluje kot ograja: mrzel zrak zadržuje nad tečajem. Cohen ga primerja z vrtavko, ki se "
        "vrti mirno, dokler je hitra.",
        fig("Vrtinec kot vrtavka", "Pogled od zgoraj na severni tečaj (križec). Shema, ne meritev.", SCHEME,
            "Levo: vrtinec kroži okoli tečaja in mrzel zrak ostaja nad Arktiko. Desno: veliki valovi iz spodnjega "
            "ozračja ga odrinejo ali raztegnejo, na drugi strani se stratosfera močno ogreje."),
        "Vrtavko zmotijo veliki valovi v ozračju, ki jim meteorologi pravijo Rossbyjevi valovi. Nastajajo spodaj, kjer "
        "je vreme, ob gorovjih in ob razlikah med kopnim in morjem. Kadar so dovolj močni, sežejo v stratosfero in "
        "vrtinec zavrejo. Ta se lahko odmakne od tečaja, raztegne, razcepi na dva dela ali celo obrne smer.",
        f"Takrat se zrak nad tečajem naglo spušča in segreva. Po opisu {a(SRC['metoffice_ssw'][0], 'britanske meteorološke službe')} "
        f"se stratosfera lahko v nekaj dneh ogreje tudi za 50{NBSP}°C. Od tod ime: nenadna stratosferska otoplitev, v "
        "strokovnih besedilih SSW. Na tleh te toplote ne čutimo, ker se dogaja 30 km nad nami.",
    ]

    video = (f'<video class="pv-video" autoplay muted loop playsinline controls preload="metadata" width="1040" height="780" '
             f'poster="{IMG}/polarni-vrtinec-airs-2019.webp" aria-label="Animacija: mrzel zrak se januarja 2019 v več '
             f'valovih spušča od Arktike nad Severno Ameriko">'
             f'<source src="{IMG}/polarni-vrtinec-airs-2019.mp4" type="video/mp4">'
             f'Vaš brskalnik videa ne predvaja. <a href="{IMG}/polarni-vrtinec-airs-2019.mp4">Odprite datoteko.</a></video>')
    s3 = [
        "Najlaže si to predstavljate ob posnetku. Spodnja animacija je iz januarja 2019, ko se je vrtinec razcepil in "
        "je nad Severno Ameriko v več valovih stekel arktični zrak. Vijolična in modra pomenita mraz.",
        fig("Januar 2019: mrzel zrak zapušča Arktiko", "Temperatura zraka po meritvah satelitskega instrumenta AIRS, "
            "20.–28. januar 2019.", video,
            "Vir: NASA/JPL-Caltech, projekt AIRS. Posnetek kaže dogodek iz leta 2019, ne letošnjega. Posnetek istega "
            "dogodka je ob svojem članku objavil Scientific American."),
        "Tak izid ni pravilo. Takrat je mraz zajel predvsem Severno Ameriko, drugič steče drugam ali nikamor. Kam gre "
        "hladen zrak, je odvisno od tega, kje se pozneje postavijo območja visokega zračnega tlaka.",
    ]

    cmp_html = (
        f'<div class="pv-cmp"><img src="{IMG}/vrtinec-po.webp" width="880" height="880" loading="lazy" decoding="async" '
        f'alt="Zemljevid temperature na 10 hPa nad severno poloblo 6. novembra 2026: hladno jedro vrtinca je odrinjeno proti '
        f'severnemu Atlantiku in Evropi, nad vzhodno Sibirijo je izrazito toplo območje.">'
        f'<img class="pv-top" src="{IMG}/vrtinec-pred.webp" width="880" height="880" loading="lazy" decoding="async" '
        f'alt="Zemljevid temperature na 10 hPa nad severno poloblo 24. oktobra 2026: hladno jedro vrtinca leži skoraj '
        f'simetrično nad tečajem."></div>'
        '<input class="pv-range" type="range" min="0" max="100" value="50" aria-label="Primerjava zemljevidov: levo 24. oktober, desno 6. november">'
        f'<div class="pv-ends"><span>← {dlong(peak[0])}</span><span>{dlong(first_neg[0])} →</span></div>'
        f'<div class="pv-scale"><i></i><div><span>{num(zm["lestvica"][0], 0)}{NBSP}°C</span><span>–50{NBSP}°C</span>'
        f'<span>{num(zm["lestvica"][1], 0)}{NBSP}°C</span></div></div>')
    s4 = [
        "Stanje vrtinca meteorologi merijo z eno številko: s povprečno hitrostjo zahodnega vetra okoli Zemlje na "
        f"višini 10{NBSP}hPa (približno 30{NBSP}km) pri 60. vzporedniku. Pozitivna številka pomeni zahodnik, negativna "
        "vzhodnik. Računam jo iz analiz ameriškega modela GFS, vsak dan ob 00 UTC.",
        fig("Vrtinec bi moral zdaj pospeševati. Letos se je ustavil.",
            "Povprečni zahodni veter na 10 hPa pri 60° s. š. Preklopite na temperaturo nad Arktiko ali se s prstom "
            "pomaknite po grafu.", charts,
            f"Letošnja črta je naš izračun iz analiz GFS ob 00 UTC, pikčasti del je napoved istega modela z dne "
            f"9.{NBSP}11. Sive črte so prejšnjih pet zim iz istega vira (vsak tretji dan). Temperatura je povprečje "
            f"polarne kape od 60° do 90° s. š. na 10{NBSP}hPa. Vir podatkov: NOAA GFS."),
        f"Od {dlong(peak[0])} do {dlong(first_neg[0])} je veter padel z {unit(peak[1], 'm/s')} na {unit(first_neg[1], 'm/s')}. "
        f"V prejšnjih petih zimah je bil na isti dan med {num(min(prev6), 0)} in {unit(max(prev6), 'm/s', 0)}. "
        f"Stratosfera nad Arktiko se je medtem ogrela za {unit(warm, '°C')}, z {unit(cold[2], '°C')} na {unit(last[2], '°C')}, "
        "čeprav bi se morala v tem času ohlajati.",
        "Številka je povprečje okoli vsega vzporednika, zato ne pove, kje je vrtinec. To pokažeta zemljevida.",
        fig("Vrtinec pred motnjo in po njej",
            f"Temperatura (barva) in višina ploskve 10{NBSP}hPa (črte na {num(zm['izohipse_m'], 0)}{NBSP}m). Povlecite drsnik.",
            cmp_html,
            f"{dlong(peak[0]).capitalize()} je hladno jedro ležalo nad tečajem. {dlong(first_neg[0]).capitalize()} je "
            f"odrinjeno proti severnemu Atlantiku in Evropi, nad vzhodno Sibirijo pa je območje, kjer je do "
            f"{unit(zm['po']['t_max_60n'], '°C', 0)} (prej največ {unit(zm['pred']['t_max_60n'], '°C', 0)}). "
            "Zemljevida sta narisana iz analiz NOAA GFS; krogi so vzporedniki 40°, 60° in 80°."),
        f"Da je hladno jedro stratosfere nad Evropo, ne pomeni, da je pri nas mraz. Gre za zrak 30{NBSP}km visoko. "
        "Vreme nastaja v spodnjih desetih kilometrih.",
    ]

    s5 = [
        "Kratek odgovor: zelo verjetno je najzgodnejši, uradno pa še ni potrjen.",
        "Za »veliko« otoplitev stratosfere se mora veter na tej višini obrniti iz zahodnika v vzhodnik, in to med "
        f"novembrom in marcem. Takih dogodkov je v povprečju šest na desetletje ({a(SRC['cp07'][0], 'Charlton in Polvani, 2007')}). "
        "Večina se zgodi januarja in februarja.",
        f"Scientific American kot dosedanji najzgodnejši datum navaja 28.{NBSP}november 1968. {a(SRC['rte'][0], 'RTÉ')} "
        f"navaja tri novembrske primere, vse na isti dan: 1958, 1968 in 2025. {a(SRC['bbc'][0], 'BBC')} piše o letih 1969 "
        "in 2025. Viri se o letnicah torej razhajajo, o datumu pa ne. Lanski primer je tudi v mojem arhivu: veter je pod "
        f"ničlo padel 28.{NBSP}novembra 2025.",
        f"Letos je v mojem izračunu prvič negativen {dlong(first_neg[0])}, in to komaj: {unit(first_neg[1], 'm/s')}. "
        f"Naslednja dva dneva je bil spet rahlo pozitiven. Napoved GFS z dne 9.{NBSP}11. ga {dlong(fc_min[0])} postavi na "
        f"{unit(fc_min[1], 'm/s', 0)}, do {dlong(fc_end[0])} pa nazaj na približno {unit(fc_end[1], 'm/s', 0)}.",
        f"Zato previdnost. Moj izračun je trenutna vrednost enega modela ob polnoči po svetovnem času. Uradni seznami "
        f"nastanejo iz dnevnih povprečij in reanaliz, ki zamujajo nekaj dni. {a(SRC['metoffice'][0], 'Met Office')} je "
        f"4.{NBSP}novembra zapisal, da je pričakovani obrat »razmeroma šibek in kratkotrajen« in da ostaja negotovo, ali "
        "bo izpolnil merilo. Cohen je za Scientific American povedal isto bolj po domače: dogodek je lahko manjši in "
        "bodo vsi pozabili nanj, lahko pa je velik in gre v knjige rekordov.",
        "Manj sporno je nekaj drugega. Tako šibkega vrtinca v začetku novembra po navedbah Met Officea in BBC v 75 letih "
        "opazovanj še ni bilo, ne glede na to, na kateri strani ničle se številka na koncu ustavi.",
    ]

    s6 = [
        "Motnja v stratosferi se lahko v nekaj tednih spusti navzdol in spremeni pot vetrovnega strženja, pasu močnih "
        "vetrov, ki vodi ciklone nad Evropo. Strženj oslabi in se zvije, pogosteje nastanejo obsežna območja visokega "
        "tlaka, ki se dolgo ne premaknejo. Po podatkih Met Officea se to zgodi v dveh do šestih tednih po dogodku.",
        '<ul class="pv-time">'
        f"<li><b>{dlong(peak[0]).capitalize()}</b><span>Vrtinec je najmočnejši to jesen: {unit(peak[1], 'm/s')}.</span></li>"
        f"<li><b>{dlong(first_neg[0]).capitalize()}</b><span>Veter v našem izračunu prvič pade pod ničlo.</span></li>"
        f"<li class=\"pv-open\"><b>Od {dlong(w0)} do {dlong(w1)}</b><span>Okno dveh do šestih tednov, v katerem bi se "
        "vpliv lahko pokazal pri tleh. Ni napoved, da se bo.</span></li>"
        "<li class=\"pv-open\"><b>December in januar</b><span>Vrtinec se po napovedih znova krepi. Ali bo zdržal, bo "
        "odločalo o drugi polovici zime.</span></li></ul>",
        "Zakaj to ni napoved mraza, ima tri razloge.",
        "<ul><li><strong>Vpliv ni zagotovljen.</strong> Met Office izrecno piše, da velika otoplitev stratosfere ne pomeni "
        "samodejno snega ali hudega mraza. Odloča, kje se postavi visok tlak.</li>"
        "<li><strong>Novembra je mrzlega zraka manj.</strong> Severna polobla se šele ohlaja, zato je zaloga mraza "
        "manjša kot januarja.</li>"
        "<li><strong>El Niño vleče v drugo smer.</strong> Letošnji je zelo močan. Analiza "
        f"{a(SRC['gsdm'][0], 'GSDM Weather Services')} kaže, da podaljšana napoved ECMWF za drugo polovico novembra nad "
        "severno Evropo kljub motnji napoveduje toplejše vreme od običajnega.</li></ul>",
        f"In Slovenija? Raziskave o Evropi ({a(SRC['king'][0], 'King in sod., 2019')}) kažejo, da je po takih dogodkih "
        "severna Evropa pogosteje hladnejša in bolj suha, južna pa bolj mokra. Slovenija leži med obema. Zanesljivega "
        "pravila za naše kraje iz tega ne znam izpeljati, zato sem pogledal, kaj je izmerila postaja.",
    ]

    s7 = [
        f"Postaja v Rečici ob Savinji meri od novembra {st_from.year}. V tem času se je veter v stratosferi obrnil "
        f"sedemkrat. Za vsakega od teh obratov sem izračunal, koliko je povprečna dnevna temperatura od 14. do 42. dne po obratu "
        "odstopala od povprečja postaje za iste dni v letu.",
        fig("Po šestih od sedmih obratov je bilo v Rečici topleje kot običajno",
            "Odstopanje povprečne temperature od 14. do 42. dne po obratu vetra. Dotaknite se stolpca za podrobnosti.",
            '<p class="pv-leg"><span><i class="sq" style="background:#d95926"></i>topleje od povprečja</span>'
            '<span><i class="sq" style="background:#3987e5"></i>hladneje od povprečja</span></p>'
            + bar_chart(rows).replace("{aria}", aria_b) + tbl,
            f"Temperatura: postaja IREICA1, zunanji senzor. Povprečje je izračunano iz vseh let meritev "
            f"({st_years[0]}–{st_years[-1]}) v oknu ±7 dni okoli dneva. Datumi obratov: januar 2021 po Lee (2021), "
            "ostali naš izračun iz analiz GFS ob 00 UTC."),
        f"V šestih primerih je bilo to obdobje toplejše od povprečja, za {num(min(r['anom'] for r in warm_rows))} do "
        f"{unit(max(r['anom'] for r in warm_rows), '°C')}. Izjema je en sam primer, in to prav lanski novembrski. Od "
        f"{dlong(cr['a'])} do {dlong(cr['b'])} je bilo {cr['cold']} od {cr['n']} dni hladnejših od povprečja, "
        f"{dlong(cr['low'][1])} pa je postaja izmerila {unit(cr['low'][0], '°C')}.",
        "Kaj iz tega sledi? Predvsem to, da obrat vetra v stratosferi v naši dolini ne prinese mraza sam po sebi. "
        "Sedem primerov je premalo za kaj več. Trije so iz marca, ko se vrtinec tako ali tako poslavlja. Povprečje "
        "postaje je iz sedmih let in vsebuje tudi ta obdobja. In ujemanje ni vzrok: lanski hladni december je lahko "
        "imel druge razloge.",
        "Zanimivo je vseeno, da je edini hladni primer edini, ki se je zgodil zgodaj v zimi. Letošnji je še tri tedne "
        "zgodnejši. To je opažanje, ne napoved.",
    ]

    s8 = [
        "Naslednje tri tedne se splača gledati tri stvari.",
        f"<ul><li><strong>Ali se vrtinec pobere.</strong> Graf vetra in temperature se vsak dan osveži na strani "
        f"{a('/stratosfera/', 'Stratosfera')}.</li>"
        f"<li><strong>Ali se motnja spusti navzdol.</strong> To pokaže indeks arktične oscilacije (AO). Ko je izrazito "
        f"negativen, hladen zrak laže uhaja proti jugu. Spremljate ga na strani {a('/indeksi/', 'Indeksi')}.</li>"
        f"<li><strong>Kje se postavi visok tlak.</strong> To je vidno na {a('/sinopticna/', 'sinoptični karti Evrope')} "
        "za štiri dni naprej.</li></ul>",
        f"Za zimo kot celoto ostaja glavni dejavnik El Niño. O njem sem pisal v članku "
        f"{a('/blog/zima-2026-2027-el-nino-napoved.html', 'Zima 2026/27 in El Niño')}. Napoved za dolino za naslednje dni, "
        f"tudi poskusna ocena možnosti snega, je na {a('/', 'naslovni strani')}, razmere na cestah in v gorah pa na "
        f"strani {a('/zima/', 'Zima')}.",
        "Če vas kdo vpraša, ali bo zaradi polarnega vrtinca huda zima, je pošten odgovor: ne vemo. Vemo, da se je "
        "nad Arktiko zgodilo nekaj, česar tako zgodaj še nismo videli, in da bo zanimivo spremljati, kaj sledi.",
        '<p class="pv-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Meteorec, Filip Eremita) in povezavo na ta članek. Za prepis ali vdelavo grafov in zemljevidov '
        'prej vprašajte. Animacija NASA/JPL-Caltech je v javni lasti.</p>',
        '<h3>Viri</h3><ul class="pv-src">' + "".join(f"<li>{a(u, t)}</li>" for u, t in SRC.values()) + "</ul>",
        f'<script type="application/json" id="pv-data">{json.dumps(js, separators=(",", ":"))}</script>' + SCRIPT,
    ]
    # skript in JSON morata v odstavek, ki ga build_html ne ovije v <p>
    s8[-1] = '<div class="pv-js">' + s8[-1] + "</div>"

    sections = [
        {"id": "kaj-se-dogaja", "label": "01 · Kaj se dogaja", "heading": "Vrtinec, ki bi moral pospeševati, je obstal", "paragraphs": s1},
        {"id": "kaj-je-polarni-vrtinec", "label": "02 · Razlaga", "heading": "Kaj je polarni vrtinec?", "paragraphs": s2},
        {"id": "video", "label": "03 · Video", "heading": "Kako je videti, ko vrtinec popusti", "paragraphs": s3},
        {"id": "podatki", "label": "04 · Podatki", "heading": f"V trinajstih dneh z {num(peak[1], 0)} m/s na ničlo", "paragraphs": s4},
        {"id": "rekord", "label": "05 · Rekord", "heading": "Je to res najzgodnejši obrat doslej?", "paragraphs": s5},
        {"id": "vreme", "label": "06 · Vreme", "heading": "Kaj to pomeni za vreme pri nas?", "paragraphs": s6},
        {"id": "recica", "label": "07 · Lastna analiza", "heading": "Kaj je po prejšnjih obratih izmerila Rečica", "paragraphs": s7},
        {"id": "kaj-spremljati", "label": "08 · Kaj zdaj", "heading": "Kaj spremljati v naslednjih tednih", "paragraphs": s8},
    ]
    title = "Polarni vrtinec se je ustavil že v začetku novembra"
    desc = (f"Veter 30 km nad Arktiko je v 13 dneh padel z {num(kmh, 0)} km/h na ničlo, tri tedne pred dosedanjim rekordom. "
            "Kaj kažejo podatki in kaj to pomeni za zimo pri nas.")
    assert len(title) <= 60, len(title)
    assert len(desc) <= 160, len(desc)
    return {
        "title": title, "meta_description": desc,
        "tags": ["polarni vrtinec", "stratosfera", "zima", "napoved", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "night-fog-valley", "og_accent_hex": "#3987e5",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Podatki: NOAA GFS (analize in napoved, naš izračun vetra na 10 hPa pri 60° s. š. in temperature "
                         "polarne kape; data/stratosfera.json), postaja IREICA1 (zunanja povprečna in najnižja dnevna "
                         "temperatura od 7. 11. 2019). Animacija: NASA/JPL-Caltech, projekt AIRS. Članek je posnetek "
                         "stanja 10. 11. 2026 in se ne osvežuje sam."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<(svg|style|script|video|details).*?</\1>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|figcaption|li|p|div|b|span)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace(NBSP, " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{2,}", "\n", h).strip()
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
    article = build_article(*load())
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
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = PUBLISHED.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, PUBLISHED.year, PUBLISHED.month, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Polarni vrtinec\nse je ustavil", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire or "--og" in sys.argv:
        try:
            from PIL import Image
            import tempfile
            src = Image.open(os.path.join(ROOT, "img", "blog", SLUG, "vrtinec-po.webp")).convert("RGB")
            tmp = os.path.join(tempfile.mkdtemp(), "og-bg.jpg")
            src.crop((40, 150, 840, 570)).resize((1600, 840)).save(tmp, quality=92)   # naš zemljevid kot ozadje
            os.environ["DRIVE_PHOTO_PATH"] = tmp
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as ex:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {ex}")
    if wire:
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml, teme in sorodni članki osveženi.")


if __name__ == "__main__":
    main()
