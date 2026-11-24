#!/usr/bin/env python3
"""
tools/generate_mega_el_nino_post.py -- »Mega El Niño: 10 °C je konica, rekordi pa so resnični« (24. 11. 2026).

Ročno napisan članek ob novici New York Posta (23. 11. 2026) o »mega El Niñu«. Številke pridejo iz committanih virov:
  - data/el-nino-mega-1124.json  (posnetek zunanjih podatkov: nizi ONI/RONI iz datotek NOAA CPC, verjetnosti jakosti CPC,
                                  tedenske vrednosti Niño regij, tedenske vrednosti BoM, projekcije Carbon Brief),
  - history.json                 (postaja IREICA1: SAMO zunanja povprečna dnevna temperatura, za zimske povprečja).
Zemljevid kopnega je maska iz igre 365-0 (Natural Earth 110m, javna domena). Trditve v besedilu so vezane na vire v SRC.

Trditve varujejo assert-i: če se podatki osvežijo in trditev ne drži več, generator pade -- besedilo je treba
prenoviti, ne zaobiti asserta. Članek je posnetek na dan objave. Lektura prek workflowa ni opravljena (lektura.yml
je izklopljena od 2. 10. 2026); slogovni pregled po docs/slog-pisanja.md. Notranjih meritev članek ne uporablja.

Usage:
    python3 tools/generate_mega_el_nino_post.py [--dry-run] [--text] [--wire] [--og] [--force]
"""
import datetime
import html as _html
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "mega-el-nino-10-c-je-konica-rekordi-so-resnicni-1124"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-mega-el-nino.txt")
PUBLISHED = datetime.date(2026, 11, 24)
NBSP = " "
# Barve serij: reže 1-4 preverjene palete (skill dataviz, validate_palette.js, temna podlaga: vse PASS).
BLUE, ORANGE, AQUA, YELLOW = "#3987e5", "#d95926", "#199e70", "#c98500"
INK, MUTED, GRID, LAND = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)", "#4a5b78"
SURF = "#0a0f1c"
STOPS = [(0.0, (247, 217, 196)), (3.0, (238, 123, 63)), (6.0, (184, 56, 26))]   # zaporedna lestvica, svetlo -> temno

_MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
        "novembra", "decembra"]
SEAS_SL = {"DJF": "dec–feb", "JFM": "jan–mar", "FMA": "feb–apr", "MAM": "mar–maj", "AMJ": "apr–jun", "MJJ": "maj–jul",
           "JJA": "jun–avg", "JAS": "jul–sep", "ASO": "avg–okt", "SON": "sep–nov", "OND": "okt–dec", "NDJ": "nov–jan"}


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "–⁠")   # U+2060: minus se ne loči od števke


def sgn(x, d=1):
    return ("+" if x > 0 else "") + num(x, d)


def unit(x, u="°C", d=1, plus=False):
    return f"{sgn(x, d) if plus else num(x, d)}{NBSP}{u}"


def esc(s):
    return _html.escape(s, quote=True)


def tip(*lines):
    return esc("|".join(lines))


def a(href, text):
    ext = href.startswith("http")
    return f'<a href="{href}"' + (' target="_blank" rel="noopener"' if ext else "") + f'>{text}</a>'


def ramp(v):
    v = max(STOPS[0][0], min(STOPS[-1][0], v))
    for (v0, c0), (v1, c1) in zip(STOPS, STOPS[1:]):
        if v0 <= v <= v1:
            t = (v - v0) / (v1 - v0)
            return "#%02x%02x%02x" % tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


# ───────────────────────── podatki ─────────────────────────

def load():
    d = json.load(open(os.path.join(ROOT, "data", "el-nino-mega-1124.json"), encoding="utf-8"))
    H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    mask = json.load(open(os.path.join(ROOT, "365-0-game", "src", "data", "worldmask.json"), encoding="utf-8"))
    return d, H.get("days", H), mask


def winters(H, d):
    """Povprečna dnevna temperatura IREICA1 za dec-feb po zimah; samo meritve (src != era5), zunanje polje."""
    T = {datetime.date.fromisoformat(k[:10]): v for k, v in H.items()
         if v.get("src") != "era5" and v.get("tempAvg") is not None}
    # DJF ONI iz uradne datoteke CPC (prebrano 24. 11. 2026): sezona DJF začetnega leta + 1
    djf_oni = {2019: 0.71, 2020: -0.99, 2021: -0.76, 2022: -0.55, 2023: 1.84, 2024: -0.46, 2025: -0.39}
    rows = []
    for y, oni in djf_oni.items():
        days = [t["tempAvg"] for dd, t in T.items() if (dd.year == y and dd.month == 12) or (dd.year == y + 1 and dd.month in (1, 2))]
        assert len(days) >= 85, f"premalo meritev za zimo {y}/{y + 1}: {len(days)}"
        phase = "el" if oni >= 0.5 else ("la" if oni <= -0.5 else "ne")
        rows.append({"y": y, "name": f"{y}/{str(y + 1)[2:]}", "t": statistics.mean(days), "oni": oni, "phase": phase, "n": len(days)})
    return rows


# ───────────────────────── pikčast zemljevid ─────────────────────────

def dots(mask, cols, rows, cell, ox=0.0, oy=0.0, color=LAND):
    """Kopno kot pike: ena pot na zaporedje celic v vrstici, črtkana z dolžino 0 in okroglim koncem (= pika)."""
    R = mask["rows"]
    segs = []
    for ri, r in enumerate(rows):
        y = oy + (ri + .5) * cell
        idx = [ci for ci, c in enumerate(cols) if R[r][c] == "1"]
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
                j += 1
            segs.append(f"M{ox + (idx[i] + .5) * cell:.1f},{y:.1f}H{ox + (idx[j] + .5) * cell:.1f}")
            i = j + 1
    return (f'<path d="{" ".join(segs)}" fill="none" stroke="{color}" stroke-width="{cell * .58:.2f}" '
            f'stroke-linecap="round" stroke-dasharray="0 {cell:.2f}"/>')


def pacific_grid(mask):
    """Lon 120° V .. 60° Z (60 celic po 3°), lat 30° S .. 30° J (20 celic)."""
    assert mask["step"] == 3 and mask["top"] == 81 and mask["cols"] == 120
    cols = list(range(100, 120)) + list(range(0, 40))
    rows = list(range(17, 37))
    return cols, rows


# ───────────────────────── grafi ─────────────────────────

# 1. Deset ravnil
RULERS = [
    ("RONI, avg–okt (3 mesece, relativni)", 1.97, None, "g1",
     ["RONI, avg–okt 2026", "Niño 3.4 minus povprečje tropov (20° S–20° J), 3-mesečno povprečje.", "NOAA CPC, osnova 1991–2020. Z njim NOAA presoja »zgodovinski« dogodek."]),
    ("ONI, avg–okt (3 mesece)", 2.46, None, "g1",
     ["ONI, avg–okt 2026", "Odstopanje v Niño 3.4, 3-mesečno povprečje, tradicionalni indeks.", "NOAA CPC. Najvišja vrednost za to sezono od leta 1950."]),
    ("Niño 3.4, oktober (CPC, relativni)", 2.5, None, "g1",
     ["Niño 3.4, oktober 2026", "Mesečno odstopanje, relativni indeks.", "NOAA CPC, razprava z 12. 11. 2026."]),
    ("Niño 3.4, teden do 22. 11. (BoM, relativni)", 2.67, None, "g1",
     ["Niño 3.4, teden do 22. 11. 2026", "Relativni indeks, tedenska vrednost.", "Avstralski urad za meteorologijo (BoM), 24. 11. 2026. Vrh dogodka doslej: +2,88 °C."]),
    ("Niño 3.4, oktober (ERA5, Copernicus)", 3.21, None, "g1",
     ["Niño 3.4, oktober 2026", "Mesečno odstopanje temperature morja po reanalizi ERA5 (tradicionalno).", "Copernicus C3S, osnova 1991–2020. Rekord vseh mesecev; prejšnji: september, 2,99 °C."]),
    ("Niño 3.4, teden 15.–21. 11. (OISST)", 3.3, None, "g1",
     ["Niño 3.4, teden 15.–21. 11. 2026", "Tedensko odstopanje, tradicionalni indeks (OISST v2.1).", "NOAA CPC, osnova 1991–2020. Relativna lestvica za isti teden: +2,4 °C."]),
    ("Niño 3, teden 15.–21. 11. (OISST)", 4.7, None, "g3",
     ["Niño 3, teden 15.–21. 11. 2026", "Pas 5° S–5° J, 150°–90° Z; tradicionalni indeks.", "NOAA CPC. Najvišja tedenska vrednost v nizu od leta 1981."]),
    ("Niño 1+2, teden 15.–21. 11. (OISST)", 5.7, None, "g3",
     ["Niño 1+2, teden 15.–21. 11. 2026", "Obalni pas ob Peruju in Ekvadorju (0°–10° J, 90°–80° Z); tradicionalni indeks.", "NOAA CPC. Najvišja tedenska vrednost v nizu od leta 1981."]),
    ("Obala Peruja in zahodno od Galápagosa, oktober (ERA5)", 6.0, 7.0, "g2",
     ["Najvišja mesečna odstopanja, oktober 2026", "Po Copernicusu 6–7 °C ob peruanski obali in zahodno od Galápagosa.", "Gre za posamezna območja, ne za povprečje regije."]),
    ("Dnevni zemljevid ECMWF, 22. 11. (Maue)", 10.0, None, "g2",
     ["Lokalna konica na zemljevidu, ki ga je objavil Ryan Maue", "Dnevna analiza ECMWF, +10 °C ob Galápagosu in obali Peruja.", "Zemljevida iz svojega okolja nisem mogel preveriti; vrednost povzemam po medijih."]),
]


def rulers_fig():
    rows = []
    for lab, v, hi, grp, t in RULERS:
        pct = v / 10 * 100
        dec = 1 if abs(v * 10 - round(v * 10)) < 1e-9 else 2
        vtxt = (f"{num(v, 0)}–{num(hi, 0)}" if hi else num(v, dec)) + f"{NBSP}°C"
        if v >= 10:
            vtxt = f"≈{NBSP}10{NBSP}°C"
        bar = f'<i class="ei-b {grp}" style="width:{pct:.1f}%"></i>'
        if hi:
            bar += f'<i class="ei-b {grp} ext" style="width:{(hi - v) / 10 * 100:.1f}%"></i>'
        rows.append(
            f'<div class="ei-row" tabindex="0" role="listitem" data-tip="{tip(*t)}" '
            f'aria-label="{esc(lab)}: {esc(vtxt)}. {esc(t[1])} {esc(t[2])}">'
            f'<div class="ei-lab">{esc(lab)}</div>'
            f'<div class="ei-track"><div class="ei-bar">{bar}</div><span class="ei-val">{vtxt}</span></div></div>')
    leg = ('<p class="ei-leg"><span><i class="g1"></i>kazalnik Niño 3.4</span><span><i class="g3"></i>širši vzhodni Pacifik</span>'
           '<span><i class="g2"></i>lokalna konica</span></p>')
    axis = ('<div class="ei-axis" aria-hidden="true">' + "".join(f"<span>{v}</span>" for v in (0, 2, 4, 6, 8, 10)) +
            '</div><p class="ei-axnote">°C nad povprečjem</p>')
    return leg + '<div class="ei-rows ei-grid" role="list">' + "".join(rows) + "</div>" + axis


# 2. Shema: običajno / El Niño
def schematic():
    def panel(x0, nino):
        warm = (f'<path d="M{x0 + 14},56 H{x0 + 226} V{108 if nino else 76} L{x0 + 14},{112 if nino else 134} Z" '
                f'fill="{ORANGE}" fill-opacity="{.5 if nino else .42}"/>')
        th = (f'<path d="M{x0 + 14},{112 if nino else 134} L{x0 + 226},{108 if nino else 76}" stroke="{INK}" '
              f'stroke-width="1.4" stroke-dasharray="4 4" fill="none" stroke-opacity=".7"/>')
        sea = (f'<rect x="{x0 + 14}" y="56" width="212" height="100" fill="{BLUE}" fill-opacity=".16"/>'
               f'<line x1="{x0 + 14}" x2="{x0 + 226}" y1="56" y2="56" stroke="{INK}" stroke-opacity=".5"/>')
        if nino:
            wind = (f'<path d="M{x0 + 150},34 H{x0 + 112}" stroke="{INK}" stroke-width="1.6" stroke-dasharray="3 4" '
                    f'marker-end="url(#ei-arr)" fill="none"/><text x="{x0 + 120}" y="24" text-anchor="middle" fill="{MUTED}">oslabljeni pasati</text>')
            ups = f'<text x="{x0 + 206}" y="150" text-anchor="end" fill="{INK}">topla voda sega do obale</text>'
            spread = (f'<path d="M{x0 + 60},84 H{x0 + 182}" stroke="{INK}" stroke-width="1.6" marker-end="url(#ei-arr)" '
                      f'fill="none" stroke-opacity=".85"/>')
        else:
            wind = (f'<path d="M{x0 + 206},34 H{x0 + 50}" stroke="{INK}" stroke-width="2" marker-end="url(#ei-arr)" fill="none"/>'
                    f'<text x="{x0 + 128}" y="24" text-anchor="middle" fill="{MUTED}">močni pasati</text>')
            ups = (f'<path d="M{x0 + 200},100 V70" stroke="{INK}" stroke-width="1.6" marker-end="url(#ei-arr)" fill="none" '
                   f'stroke-opacity=".85"/><text x="{x0 + 206}" y="150" text-anchor="end" fill="{INK}">dvigovanje hladne vode</text>')
            spread = ""
        return (f'<g>{sea}{warm}{th}{wind}{ups}{spread}'
                f'<text x="{x0 + 18}" y="172" fill="{MUTED}">Indonezija</text>'
                f'<text x="{x0 + 226}" y="172" text-anchor="end" fill="{MUTED}">Peru</text>'
                f'<text x="{x0 + 120}" y="192" text-anchor="middle" fill="{INK}" font-weight="600" font-size="13">'
                f'{"El Niño" if nino else "Običajno stanje"}</text></g>')
    return (f'<svg class="ei-svg ei-scheme" viewBox="0 0 500 200" role="img" aria-label="Shema prereza ekvatorialnega Pacifika. '
            f'Levo običajno stanje: močni pasati potiskajo toplo vodo proti zahodu, ob obali Peruja se dviguje hladna voda. '
            f'Desno El Niño: pasati oslabijo, topla plast se razširi proti vzhodu in je ob obali Peruja debela." '
            f'font-family="Inter,system-ui,sans-serif" font-size="11">'
            f'<defs><marker id="ei-arr" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>'
            f'{panel(0, False)}<g transform="translate(250 0)">{panel(0, True)}</g></svg>')


# 3. Zemljevid Pacifika z regijami Niño
NINO = [  # id, ime, lon od, lon do (0–360), lat, bar-vrsta
    ("n4", "Niño 4", 160, 210),
    ("n34", "Niño 3.4", 190, 240),
    ("n3", "Niño 3", 210, 270),
    ("n12", "Niño 1+2", 270, 280),
]
NINO_IDX = {"n12": 0, "n3": 1, "n34": 2, "n4": 3}
MONTHLY_REL = {"n34": 2.5, "n3": 3.6, "n12": 4.4}   # CPC razprava, 12. 11. 2026 (oktober, relativni)


def pacific_svg(mask, d, w):
    narrow = w < 500
    cell = w / 60
    cols, rows = pacific_grid(mask)
    mh = cell * 20
    fs = 10 if narrow else 12.5
    rh, gap = (17, 7) if narrow else (22, 9)
    top = mh + (26 if narrow else 30)
    h = top + 4 * (rh + gap) + 6
    last = d["nino_weekly"]["trad"][-1]

    def X(lon):
        return (lon - 120) / 3 * cell
    o = [f'<svg class="ei-svg ei-pac {"ei-narrow" if narrow else "ei-wide"}" viewBox="0 0 {w} {h:.0f}" role="img" '
         f'aria-label="Pikčast zemljevid Tihega oceana med 120° vzhodno in 60° zahodno z mejami regij Niño in vrednostmi odstopanja" '
         f'font-family="Inter,system-ui,sans-serif" font-size="{fs}">']
    o.append(dots(mask, cols, rows, cell))
    for lon, lab in ((120, "120° V"), (180, "180°"), (240, "120° Z"), (300, "60° Z")):
        x = X(lon)
        anchor = "start" if lon == 120 else ("end" if lon == 300 else "middle")
        o.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{mh:.1f}" stroke="{GRID}"/>')
        o.append(f'<text x="{x + (2 if lon == 120 else (-2 if lon == 300 else 0)):.1f}" y="{mh + 14:.1f}" text-anchor="{anchor}" fill="{MUTED}">{lab}</text>')
    o.append(f'<line x1="0" x2="{w}" y1="{mh / 2:.1f}" y2="{mh / 2:.1f}" stroke="{GRID}" stroke-dasharray="3 4"/>')
    # regije kot tanke obrobe na zemljevidu (5° S–5° J; Niño 1+2: 0°–10° J)
    for nid, name, l0, l1 in NINO:
        if nid == "n12":
            y0, y1 = mh / 2, mh / 2 + 10 / 3 * cell
        else:
            y0, y1 = mh / 2 - 5 / 3 * cell, mh / 2 + 5 / 3 * cell
        o.append(f'<rect class="ei-nbox" data-r="{nid}" x="{X(l0):.1f}" y="{y0:.1f}" width="{X(l1) - X(l0):.1f}" '
                 f'height="{y1 - y0:.1f}" fill="none" stroke="{INK}" stroke-opacity=".35" stroke-dasharray="3 3"/>')
    for k, (nid, name, l0, l1) in enumerate(NINO):
        y = top + k * (rh + gap)
        v = last[NINO_IDX[nid]]
        o.append(f'<text x="{X(l0) - 7:.1f}" y="{y + rh * .72:.1f}" text-anchor="end" fill="{INK}">{name}</text>')
        o.append(f'<g class="ei-nrow" data-r="{nid}" tabindex="0" role="img">'
                 f'<rect class="ei-nbar" x="{X(l0):.1f}" y="{y}" width="{X(l1) - X(l0):.1f}" height="{rh}" rx="4" fill="{ramp(v)}"/>'
                 f'<text class="ei-nval" x="{X(l1) + 7:.1f}" y="{y + rh * .72:.1f}" fill="{INK}" font-weight="600">'
                 f'{sgn(v)}{"" if narrow else NBSP + "°C"}</text></g>')
    o.append("</svg>")
    return "".join(o)


def pacific_fig(mask, d):
    last_t, last_r = d["nino_weekly"]["trad"][-1], d["nino_weekly"]["rel"][-1]
    assert [last_r[1], last_r[2], last_r[3], last_r[0]] == [3.9, 2.4, 0.2, 4.9], "relativne vrednosti se ne ujemajo s CPC"
    ramp_bar = ('<div class="ei-scale" aria-hidden="true"><i style="background:linear-gradient(90deg,' +
                ",".join(f"{ramp(v)} {v / 6 * 100:.0f}%" for v in (0, 1.5, 3, 4.5, 6)) +
                '"></i><div><span>0</span><span>2</span><span>4</span><span>6 °C</span></div></div>')
    ctl = ('<div class="ei-ctl" hidden><div class="ei-seg" role="group" aria-label="Lestvica">'
           '<button type="button" data-set="trad" aria-pressed="true">Tradicionalno (teden)</button>'
           '<button type="button" data-set="rel" aria-pressed="false">Relativno (teden)</button>'
           '<button type="button" data-set="mon" aria-pressed="false">Mesec oktober (CPC)</button></div></div>')
    return (ctl + '<div class="ei-pane-map">' + pacific_svg(mask, d, 720) + pacific_svg(mask, d, 360) + "</div>" + ramp_bar)


# 4. Črtni grafi (ONI/RONI in tedenski Niño)
def line_svg(key, w, series, y0, y1, step, xticks, n, hline=None, endlabels=False, ylab="°C", subl=None, aria=""):
    """Statičen SVG (deluje brez JS); JS doda križ in oblaček prek data-box. series: [{id,color,vals,width,dash}]"""
    narrow = w < 500
    h = 300 if narrow else 340
    L, R, Tp, B = 38, (14 if narrow or not endlabels else 78), 16, (46 if subl else 32)

    def X(i):
        return L + (w - L - R) * i / n

    def Y(v):
        return Tp + (h - Tp - B) * (y1 - v) / (y1 - y0)
    o = [f'<svg class="ei-svg ei-ln {"ei-narrow" if narrow else "ei-wide"}" viewBox="0 0 {w} {h}" role="img" data-k="{key}" '
         f'data-box="{L},{Tp},{w - R},{h - B},{w},{h},{n},{y0},{y1}" aria-label="{esc(aria)}" '
         f'font-family="Inter,system-ui,sans-serif" font-size="12">']
    v = y0
    while v <= y1 + 1e-9:
        zero = abs(v) < 1e-9
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{INK if zero else GRID}" '
                 f'stroke-width="{1.2 if zero else 1}"{" stroke-opacity=\".55\"" if zero else ""}/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="{MUTED}">{num(v, 1 if step < 1 else 0)}</text>')
        v += step
    o.append(f'<text x="{L - 34}" y="11" fill="{MUTED}">{ylab}</text>')
    for i, lab in xticks:
        anchor = "start" if i == 0 else ("end" if i == n else "middle")
        o.append(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{h - B}" y2="{h - B + 4}" stroke="{MUTED}" stroke-opacity=".5"/>')
        o.append(f'<text x="{X(i):.1f}" y="{h - B + 17}" text-anchor="{anchor}" fill="{MUTED}">{lab}</text>')
    if subl:
        for (i0, i1), lab in subl:
            xm = (X(i0) + X(i1)) / 2
            o.append(f'<text x="{xm:.1f}" y="{h - 5}" text-anchor="middle" fill="{MUTED}" font-size="11">{lab}</text>')
    if hline:
        hv, hlab = hline
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(hv):.1f}" y2="{Y(hv):.1f}" stroke="{INK}" stroke-opacity=".6" '
                 f'stroke-dasharray="5 4"/>')
        o.append(f'<text x="{L + 6}" y="{Y(hv) - 5:.1f}" fill="{INK}" font-size="11" paint-order="stroke" stroke="{SURF}" '
                 f'stroke-width="3">{hlab}</text>')
    for s in series:
        pts = [(X(i), Y(vv)) for i, vv in enumerate(s["vals"]) if vv is not None]
        dpath = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        o.append(f'<g class="ei-ev" data-ev="{s["id"]}"><path d="{dpath}" fill="none" stroke="{s["color"]}" '
                 f'stroke-width="{s.get("width", 1.9)}" stroke-linejoin="round" stroke-linecap="round"/>')
        if s.get("end"):
            ex, ey = pts[-1]
            o.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{s["color"]}" stroke="{SURF}" stroke-width="2"/>')
            o.append(f'<text x="{ex - 8:.1f}" y="{ey - 9:.1f}" text-anchor="end" fill="{INK}" font-weight="600" '
                     f'paint-order="stroke" stroke="{SURF}" stroke-width="3">{s["end"]}</text>')
        elif s.get("peak"):
            pi = s["vals"].index(max(v for v in s["vals"] if v is not None))
            o.append(f'<circle cx="{X(pi):.1f}" cy="{Y(s["vals"][pi]):.1f}" r="3.5" fill="{s["color"]}" stroke="{SURF}" stroke-width="1.5"/>')
        if endlabels:
            ex, ey = pts[-1]
            o.append(f'<text x="{ex + 8:.1f}" y="{ey + 4:.1f}" fill="{INK}" font-weight="600">{s["name"]}</text>')
        o.append("</g>")
    o.append(f'<line class="ei-cross" x1="0" x2="0" y1="{Tp}" y2="{h - B}" stroke="{INK}" stroke-opacity=".5" visibility="hidden"/>')
    o.append("</svg>")
    return "".join(o)


EV_COLORS = {1982: BLUE, 1997: ORANGE, 2015: AQUA, 2023: YELLOW, 2026: INK}


def traj_fig(d):
    ev = d["events"]
    ch = {}
    panes = []
    for kind, ylab in (("oni", "ONI"), ("roni", "RONI")):
        series = []
        for e in ev:
            vals = d[kind][str(e["y0"])]
            vals = vals + [None] * (24 - len(vals))
            s = {"id": str(e["y0"]), "name": e["name"], "color": EV_COLORS[e["y0"]], "vals": vals,
                 "width": 3.2 if e["y0"] == 2026 else 1.8, "peak": e["y0"] != 2026}
            if e["y0"] == 2026:
                s["end"] = f"2026: {sgn(d[kind]['2026'][-1], 2)}"
            series.append(s)
        ch[kind] = {"unit": "°C", "dec": 2, "x": [f"{SEAS_SL[d['seasons'][i % 12]]} ({d['seasons'][i % 12]})" for i in range(24)],
                    "series": [{"id": s["id"], "name": s["name"], "color": s["color"], "v": s["vals"]} for s in series]}
        hl = (2.5, "NOAA: »zgodovinski« dogodek, RONI ≥ +2,5") if kind == "roni" else None
        xt = [(0, "dec–feb"), (6, "jun–avg"), (12, "dec–feb"), (18, "jun–avg"), (23, "nov–jan")]
        sub = [((0, 11), "leto začetka"), ((12, 23), "naslednje leto")]
        aria = (f"Črtni graf: {ylab} po sezonah za El Niñe 1982/83, 1997/98, 2015/16, 2023/24 in 2026. "
                f"Letošnja črta do avgusta–oktobra doseže {num(d[kind]['2026'][-1], 2)} °C.")
        svgs = "".join(line_svg(kind, w, series, -1.5, 3.0, .5, xt, 23, hline=hl, subl=sub, aria=aria) for w in (680, 360))
        panes.append(f'<div class="ei-pane" data-pane="{kind}"{"" if kind == "oni" else " hidden"}>{svgs}</div>')
    ctl = ('<div class="ei-ctl" hidden><div class="ei-seg" role="group" aria-label="Indeks">'
           '<button type="button" data-show="oni" aria-pressed="true">ONI (tradicionalni)</button>'
           '<button type="button" data-show="roni" aria-pressed="false">RONI (relativni)</button></div></div>')
    chips = ('<p class="ei-leg ei-chips" role="group" aria-label="Dogodki">' + "".join(
        f'<button type="button" class="ei-chip" data-ev="{e["y0"]}" aria-pressed="true">'
        f'<i style="background:{EV_COLORS[e["y0"]]}"></i>{e["name"]}</button>' for e in ev) + "</p>")
    return ctl + chips + "".join(panes), ch


def weeks_fig(d):
    nw = d["nino_weekly"]
    names = [("n12", "Niño 1+2", ORANGE, 0), ("n3", "Niño 3", YELLOW, 1), ("n34", "Niño 3.4", BLUE, 2), ("n4", "Niño 4", AQUA, 3)]
    ch, panes = {}, []
    xt = [(0, nw["weeks"][0].split("–")[0]), (4, "27. 9."), (8, "25. 10."), (11, "15. 11.")]
    for kind in ("trad", "rel"):
        series = [{"id": nid, "name": nm, "color": col, "vals": [row[ix] for row in nw[kind]], "width": 2.4}
                  for nid, nm, col, ix in names]
        ch["w" + kind] = {"unit": "°C", "dec": 1, "x": [f"teden {w}" for w in nw["weeks"]],
                          "series": [{"id": s["id"], "name": s["name"], "color": s["color"], "v": s["vals"]} for s in series]}
        aria = ("Črtni graf: tedenska odstopanja v regijah Niño 4, 3.4, 3 in 1+2 v zadnjih 12 tednih, "
                + ("tradicionalna lestvica." if kind == "trad" else "relativna lestvica."))
        svgs = "".join(line_svg("w" + kind, w, series, -0.5 if kind == "rel" else 0, 6.0, 1.0, xt, 11,
                                endlabels=(w > 500), ylab="°C", aria=aria) for w in (680, 360))
        panes.append(f'<div class="ei-pane" data-pane="{kind}"{"" if kind == "trad" else " hidden"}>{svgs}</div>')
    ctl = ('<div class="ei-ctl" hidden><div class="ei-seg" role="group" aria-label="Lestvica">'
           '<button type="button" data-show="trad" aria-pressed="true">Tradicionalno</button>'
           '<button type="button" data-show="rel" aria-pressed="false">Relativno</button></div></div>')
    leg = ('<p class="ei-leg">' + "".join(f'<span><i style="background:{col}"></i>{nm}</span>' for _, nm, col, _ in names) + "</p>")
    return ctl + leg + "".join(panes), ch


# 5. Verjetnosti CPC
CLS = [("la", "La Niña", BLUE, "#0a0f1c"), ("n", "nevtralno", "#5b6b82", INK), ("w", "šibek", "#f4c7ae", "#0a0f1c"),
       ("m", "zmeren", "#f09a6c", "#0a0f1c"), ("s2", "močan", "#e8703a", "#0a0f1c"), ("vs", "zelo močan", "#c2491a", INK)]
CLS_RANGE = {"la": "≤ −0,5 °C", "n": "od −0,5 do +0,5 °C", "w": "+0,5 do +1,0 °C", "m": "+1,0 do +1,5 °C",
             "s2": "+1,5 do +2,0 °C", "vs": "≥ +2,0 °C"}


def strength_fig(d):
    rows = []
    for s in d["cpc_strength"]["seasons"]:
        tot = sum(s[k] for k, *_ in CLS)
        assert tot == 100, (s["s"], tot)
        segs = []
        for k, nm, col, txtc in CLS:
            if not s[k]:
                continue
            lab = f'{s[k]}{NBSP}%' if s[k] >= 9 else ""
            segs.append(f'<span class="ei-seg-b" tabindex="0" style="flex:{s[k]} 1 0;background:{col};color:{txtc}" '
                        f'data-tip="{tip(f"{s["label"]}: {nm}", f"Verjetnost: {s[k]} %", f"RONI {CLS_RANGE[k]}")}" '
                        f'aria-label="{esc(s["label"])}, {esc(nm)}: {s[k]} %">{lab}</span>')
        very = s["vs"] + s["s2"]
        rows.append(f'<div class="ei-srow" role="listitem"><div class="ei-slab"><b>{s["s"]}</b><span>{s["label"]}</span></div>'
                    f'<div class="ei-stack" aria-label="{esc(s["label"])}: zelo močan {s["vs"]} %, močan {s["s2"]} %">{"".join(segs)}</div></div>')
    leg = '<p class="ei-leg">' + "".join(
        f'<span><i class="sq" style="background:{col}"></i>{nm}</span>' for _, nm, col, _ in CLS) + "</p>"
    return leg + '<div class="ei-srows" role="list">' + "".join(rows) + "</div>"


# 6. Globalna temperatura (Carbon Brief)
def temp_fig(d):
    cb = d["carbon_brief"]
    lo0, hi0 = 1.4, 2.0
    rows = [("2024", "rekord doslej", cb["y2024"], cb["y2024"], cb["y2024"], None, "g1",
             ["2024: najtoplejše leto doslej", "Povprečje šestih naborov: 1,52 °C nad predindustrijsko ravnjo.", "Carbon Brief"]),
            ("2026", "projekcija", cb["y2026"]["mid"], cb["y2026"]["lo"], cb["y2026"]["hi"], cb["y2026"]["p_record"], "g2",
             ["2026: projekcija", "Najboljša ocena 1,52 °C, 90 % razpon 1,50–1,55 °C.", "Verjetnost novega rekorda: 67 % (povprečje šestih naborov)."]),
            ("2027", "projekcija", cb["y2027"]["mid"], cb["y2027"]["lo"], cb["y2027"]["hi"], cb["y2027"]["p_record"], "g2",
             ["2027: projekcija", "Najboljša ocena 1,74 °C, 90 % razpon 1,54–1,95 °C.", "Verjetnost, da bo toplejše od vseh doslej: 96 %."])]
    out = []
    for yr, kind, mid, lo, hi, p, grp, t in rows:
        left = (lo - lo0) / (hi0 - lo0) * 100
        width = max((hi - lo) / (hi0 - lo0) * 100, 0)
        mpos = (mid - lo0) / (hi0 - lo0) * 100
        rng = f'<i class="ei-range {grp}" style="left:{left:.1f}%;width:{width:.1f}%"></i>' if width > 0 else ""
        out.append(f'<div class="ei-row" tabindex="0" role="listitem" data-tip="{tip(*t)}" aria-label="{esc(" ".join(t))}">'
                   f'<div class="ei-lab"><b>{yr}</b> · {kind}</div>'
                   f'<div class="ei-track"><div class="ei-bar ei-rng">{rng}<i class="ei-mid {grp}" style="left:{mpos:.1f}%"></i></div>'
                   f'<span class="ei-val">{num(mid, 2)}{NBSP}°C</span></div></div>')
    ax = ('<div class="ei-axis ei-axis2" aria-hidden="true">' + "".join(f'<span style="left:{(v - lo0) / (hi0 - lo0) * 100:.0f}%">{num(v, 1)}</span>'
                                                                       for v in (1.4, 1.6, 1.8, 2.0)) + '</div><p class="ei-axnote">°C nad predindustrijsko ravnjo</p>')
    return '<div class="ei-rows" role="list">' + "".join(out) + "</div>" + ax


# 7. Zemljevid posledic
CAT = {"wet": ("bolj namočeno", BLUE), "dry": ("bolj suho", ORANGE), "weak": ("šibek ali mešan signal", "#8aa0bd")}
REGIONS = [
    # id, ime, lon0, lon1, lat0, lat1, kat, besedilo, vir
    ("peru", "Obala Peruja in Ekvadorja", -83, -73, -18, 3, "wet",
     "Obalni El Niño (Niño 1+2) traja od marca 2026. Po ENFEN bo od novembra do januarja nadpovprečno padavin na severni in osrednji obali, pretoki rek bodo nad normalo; reka Tumbes je med 16. in 18. novembrom za hip presegla prag nevarnosti 1000 m³/s (SENAMHI).",
     ("ENFEN, SENAMHI", "enfen")),
    ("samerica", "Jugovzhodna Južna Amerika", -63, -47, -36, -22, "wet",
     "Copernicus (10. 11.): verjetnejše je bolj namočeno kot običajno. To je sezonska napoved, ne meritev.", ("Copernicus C3S", "c3sseas")),
    ("usa", "Zahod in jugozahod ZDA", -125, -100, 28, 48, "wet",
     "WMO napoveduje več padavin na severozahodu ZDA, Copernicus pa bolj namočen jugozahod Severne Amerike.", ("WMO, Copernicus", "wmo_oct")),
    ("eafrica", "Vzhodna Afrika", 33, 48, -6, 8, "wet",
     "WMO (26. 10.): v deževni dobi okt–dec so verjetnejše nadpovprečne padavine in poplave.", ("WMO", "wmo_oct")),
    ("easia", "Vzhodna Azija", 105, 125, 22, 38, "wet",
     "Copernicus (10. 11.): verjetnejše je bolj namočeno kot običajno. To je sezonska napoved, ne meritev.", ("Copernicus C3S", "c3sseas")),
    ("safrica", "Južna Afrika", 14, 36, -30, -12, "dry",
     "Pozen začetek deževne dobe, podpovprečne padavine in dolgi suhi nizi; po FEWS NET je tveganje suše veliko. Največ pomoči bo potrebne v sušni sezoni od novembra 2027 do marca 2028. Regionalni forum SARCOF-33 ima visoko zaupanje v podpovprečne padavine do februarja 2027.",
     ("FEWS NET", "fews")),
    ("indonesia", "Indonezija in Jugovzhodna Azija", 95, 128, -10, 10, "dry",
     "CPC: zatrta konvekcija nad Indonezijo. WMO: toplejše razmere in primanjkljaj padavin, večje tveganje požarov in dima.", ("NOAA CPC, WMO", "cpc_disc")),
    ("amazon", "Amazonija in sever Južne Amerike", -75, -50, -8, 8, "dry",
     "WMO (26. 10.): večje tveganje suše v delih Amazonije.", ("WMO", "wmo_oct")),
    ("camerica", "Srednja Amerika in južna Karibi", -92, -77, 7, 17, "dry",
     "WMO (26. 10.): večje tveganje suše v delih Srednje Amerike in južne Karibov.", ("WMO", "wmo_oct")),
    ("india", "Indija", 70, 88, 8, 26, "dry",
     "Izmerjeno: monsun jun–sep je bil 13 % pod normalo, največji primanjkljaj od 2015; prehranska inflacija je oktobra 8,9 %. USDA za 2026/27 napoveduje 4,6 % manj riža.",
     ("Mint (podatki IMD), FEWS NET", "mint")),
    ("australia", "Vzhodna Avstralija", 140, 154, -38, -20, "dry",
     "USDA napoveduje 14 % manj pšenice, avstralska statistična služba 17 %. BoM opozarja, da močan El Niño ne pomeni nujno močnih posledic za Avstralijo.",
     ("FEWS NET, BoM", "fews")),
    ("pacific", "Pacifiški otoki", 130, 180, -25, 12, "dry",
     "WMO (5. 11.): suša od Palauja do Marshallovih otokov in od Papue Nove Gvineje do južne Polinezije; ob ekvatorju od Nauruja do vzhodnega Kiribatija bo mokreje. Močni morski vročinski valovi in beljenje koral pri vzhodnem Kiribatiju do februarja 2027.",
     ("WMO", "wmo_pac")),
    ("europe", "Evropa", -10, 35, 36, 60, "weak",
     "Copernicus (10. 11.): bolj namočena zima skoraj povsod razen na skrajnem severu in jugu; toplo na jugozahodu, na severovzhodu manj zanesljivo. Vpliv El Niña na Evropo je posreden in šibak.",
     ("Copernicus C3S", "c3sseas")),
]


def impact_fig(mask, SRC):
    cell = 6
    cols, rows = list(range(120)), list(range(3, 42))      # lat 72° .. –45°
    w, h = 120 * cell, len(rows) * cell

    def X(lon):
        return (lon + 180) / 3 * cell

    def Y(lat):
        return (72 - lat) / 3 * cell
    o = [f'<svg class="ei-svg ei-world" viewBox="0 0 {w} {h}" role="img" aria-label="Pikčast zemljevid sveta z označenimi območji, '
         f'kjer je običajno bolj namočeno ali bolj suho med močnim El Niñom" font-family="Inter,system-ui,sans-serif">']
    o.append(dots(mask, cols, rows, cell))
    for rid, name, lo0, lo1, la0, la1, cat, text, src in REGIONS:
        col = CAT[cat][1]
        o.append(f'<rect class="ei-reg" data-id="{rid}" x="{X(lo0):.1f}" y="{Y(la1):.1f}" width="{X(lo1) - X(lo0):.1f}" '
                 f'height="{Y(la0) - Y(la1):.1f}" rx="4" fill="{col}" fill-opacity=".30" stroke="{col}" stroke-width="1.6" '
                 f'{"stroke-dasharray=\"4 3\"" if cat == "weak" else ""}/>')
    o.append("</svg>")
    chips = ('<div class="ei-chips2" role="group" aria-label="Območja">' + "".join(
        f'<button type="button" class="ei-chip" data-id="{rid}" aria-pressed="false"><i style="background:{CAT[cat][1]}"></i>{name}</button>'
        for rid, name, _, _, _, _, cat, _, _ in REGIONS) + "</div>")
    leg = '<p class="ei-leg">' + "".join(f'<span><i class="sq" style="background:{c}"></i>{n}</span>' for n, c in CAT.values()) + "</p>"
    panel = '<div class="ei-panel" id="ei-panel" aria-live="polite"><b>Izberite območje</b><span>Dotaknite se okvirja na zemljevidu ali gumba spodaj.</span></div>'
    reg = {rid: {"name": name, "cat": CAT[cat][0], "text": text, "src": src[0], "url": SRC[src[1]][0], "col": CAT[cat][1]}
           for rid, name, _, _, _, _, cat, text, src in REGIONS}
    return leg + o[0] + "".join(o[1:]) + panel + chips, reg


# 8. Zime v Rečici
def recica_svg(rows, w):
    narrow = w < 500
    h = 300 if narrow else 320
    L, R, Tp, B = 34, 8, 24, 58
    y0, y1 = 0.0, 3.5
    bw = (w - L - R) / len(rows)
    COL = {"el": ORANGE, "la": BLUE, "ne": "#6d7f99"}
    NAME = {"el": "El Niño", "la": "La Niña", "ne": "nevtralno"}

    def Y(v):
        return Tp + (h - Tp - B) * (y1 - v) / (y1 - y0)
    o = [f'<svg class="ei-svg ei-rec {"ei-narrow" if narrow else "ei-wide"}" viewBox="0 0 {w} {h}" role="img" '
         f'aria-label="Povprečna temperatura od decembra do februarja na postaji IREICA1 po zimah, obarvana po fazi ENSO" '
         f'font-family="Inter,system-ui,sans-serif" font-size="12">']
    for v in (0, 1, 2, 3):
        o.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{INK if v == 0 else GRID}" '
                 f'{"stroke-opacity=\".55\"" if v == 0 else ""}/>')
        o.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="{MUTED}">{v}</text>')
    o.append(f'<text x="{L - 28}" y="12" fill="{MUTED}">°C, dec–feb</text>')
    for i, r in enumerate(rows):
        x = L + bw * i + bw * .16
        ww = bw * .68
        top = Y(r["t"])
        rr = min(4, (Y(0) - top) / 2)
        d = (f"M{x:.1f},{Y(0):.1f} V{top + rr:.1f} Q{x:.1f},{top:.1f} {x + rr:.1f},{top:.1f} H{x + ww - rr:.1f} "
             f"Q{x + ww:.1f},{top:.1f} {x + ww:.1f},{top + rr:.1f} V{Y(0):.1f} Z")
        t = tip(f"Zima {r['y']}/{r['y'] + 1}", f"Povprečje dec–feb: {num(r['t'], 2)} °C ({r['n']} dni meritev)",
                f"ONI za dec–feb: {sgn(r['oni'], 2)} °C ({NAME[r['phase']]})")
        o.append(f'<g class="ei-bar2" tabindex="0" role="img" aria-label="Zima {r["name"]}: {num(r["t"], 1)} °C, {NAME[r["phase"]]}" data-tip="{t}">'
                 f'<rect x="{L + bw * i:.1f}" y="{Tp}" width="{bw:.1f}" height="{h - Tp - B}" fill="transparent"/>'
                 f'<path d="{d}" fill="{COL[r["phase"]]}"/></g>')
        o.append(f'<text x="{x + ww / 2:.1f}" y="{top - 6:.1f}" text-anchor="middle" fill="{INK}" font-weight="600">{num(r["t"], 1)}</text>')
        o.append(f'<text x="{x + ww / 2:.1f}" y="{h - 38}" text-anchor="middle" fill="{MUTED}">{r["name"] if not narrow else r["name"][2:]}</text>')
        o.append(f'<text x="{x + ww / 2:.1f}" y="{h - 22}" text-anchor="middle" fill="{MUTED}" font-size="11">{sgn(r["oni"], 2)}</text>')
        o.append(f'<text x="{x + ww / 2:.1f}" y="{h - 7}" text-anchor="middle" fill="{COL[r["phase"]] if r["phase"] != "ne" else MUTED}" '
                 f'font-size="10.5" font-weight="600">{"EN" if r["phase"] == "el" else ("LN" if r["phase"] == "la" else "–")}</text>')
    o.append("</svg>")
    return "".join(o)


def recica_fig(rows):
    leg = ('<p class="ei-leg"><span><i class="sq" style="background:' + ORANGE + '"></i>El Niño (ONI ≥ +0,5 °C), EN</span>'
           '<span><i class="sq" style="background:#6d7f99"></i>nevtralno</span>'
           '<span><i class="sq" style="background:' + BLUE + '"></i>La Niña (ONI ≤ −0,5 °C), LN</span></p>')
    return leg + recica_svg(rows, 680) + recica_svg(rows, 360)


# ───────────────────────── slog, skript ─────────────────────────

STYLE = """<style>
.ei-fig{margin:1.5rem 0;padding:1rem 1rem .85rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px;position:relative}
.ei-fig figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.7rem}
.ei-fig h3{font-family:'Space Grotesk',sans-serif;font-size:1rem;margin:0 0 .15rem;color:var(--text)}
.ei-sub{color:var(--muted);font-size:.86rem;margin:0 0 .6rem;line-height:1.45}
.ei-svg{display:block;width:100%;height:auto;margin:0 auto}
.ei-ln{touch-action:pan-y}
.ei-wide{display:none}
@media(min-width:640px){.ei-wide{display:block}.ei-narrow{display:none}}
.ei-pane[hidden]{display:none}
.ei-ctl{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.2rem 0 .7rem}
.ei-seg{display:inline-flex;flex-wrap:wrap;border:1px solid var(--card-border);border-radius:999px;padding:3px;background:rgba(255,255,255,.04)}
.ei-seg button,.ei-chip{font:inherit;font-size:.85rem;min-height:38px;padding:.3rem .9rem;border-radius:999px;border:0;background:none;color:var(--muted);cursor:pointer}
.ei-seg button[aria-pressed="true"]{background:#3987e5;color:#fff;font-weight:600}
.ei-chip{border:1px solid var(--card-border);display:inline-flex;align-items:center;gap:.45rem}
.ei-chip i{display:inline-block;width:.8rem;height:.8rem;border-radius:50%}
.ei-chip[aria-pressed="true"]{color:var(--text);background:rgba(255,255,255,.08)}
.ei-chips .ei-chip[aria-pressed="false"]{opacity:.5}
.ei-seg button:focus-visible,.ei-chip:focus-visible,.ei-row:focus-visible,.ei-seg-b:focus-visible,.ei-bar2:focus-visible,.ei-nrow:focus-visible{outline:2px solid #fff;outline-offset:2px}
.ei-leg{display:flex;flex-wrap:wrap;gap:.35rem 1.1rem;font-size:.85rem;color:var(--muted);margin:0 0 .6rem}
.ei-leg span{display:inline-flex;align-items:center;gap:.4rem}
.ei-leg i{display:inline-block;width:.8rem;height:.8rem;border-radius:3px}
.ei-leg i.g1{background:#3987e5}.ei-leg i.g2{background:#d95926}.ei-leg i.g3{background:#199e70}
.ei-chips{gap:.4rem}.ei-chips2{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.7rem}
.ei-tip{position:absolute;z-index:3;pointer-events:none;background:#0d1424;border:1px solid rgba(255,255,255,.22);border-radius:10px;padding:.5rem .7rem;font-size:.84rem;line-height:1.5;color:var(--text);box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:270px}
.ei-tip b{display:block;font-weight:600}.ei-tip span{display:block;color:var(--muted)}.ei-tip span strong{color:var(--text);font-weight:600}
.ei-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin:1.3rem 0}
.ei-tile{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:.8rem .9rem}
.ei-tile b{display:block;font-family:'Space Grotesk',sans-serif;font-size:1.9rem;line-height:1.05;color:var(--text);font-variant-numeric:tabular-nums}
.ei-tile b small{font-size:.95rem;font-weight:600;color:var(--muted)}
.ei-tile span{display:block;margin-top:.35rem;font-size:.82rem;line-height:1.4;color:var(--muted)}
.ei-short{background:var(--card-bg);border:1px solid var(--card-border);border-left:4px solid #d95926;border-radius:14px;padding:.9rem 1.1rem;margin:1.2rem 0}
.ei-short h3{font-family:'Space Grotesk',sans-serif;font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 .4rem}
.ei-short ul{margin:0;padding-left:1.1rem}.ei-short li{margin:.3rem 0}
.ei-rows{display:flex;flex-direction:column;gap:.55rem}
.ei-row{padding:.15rem 0;border-radius:8px}
.ei-lab{font-size:.84rem;color:var(--muted);line-height:1.3;margin-bottom:.2rem}
.ei-lab b{color:var(--text)}
.ei-track{display:flex;align-items:center;gap:.6rem}
.ei-bar{flex:1;display:flex;height:16px;position:relative;border-radius:4px}
.ei-grid .ei-bar{background-image:linear-gradient(to right,rgba(255,255,255,.10) 1px,transparent 1px);background-size:20% 100%;background-repeat:repeat-x}
.ei-b{display:block;height:100%;border-radius:0 5px 5px 0;min-width:3px}
.ei-b.ext{border-radius:0 5px 5px 0;opacity:.45;margin-left:2px}
.ei-b:not(.ext):not(:last-child){border-radius:0}
.g1{background:#3987e5}.g2{background:#d95926}.g3{background:#199e70}
.ei-val{flex:0 0 5.6rem;font-variant-numeric:tabular-nums;font-weight:600;font-size:.92rem;color:var(--text)}
.ei-axis{display:flex;justify-content:space-between;align-items:baseline;font-size:.78rem;color:var(--muted);margin-top:.5rem;padding-right:6.2rem;position:relative}
.ei-axis2{display:block;height:1.2rem;margin-right:6.2rem;padding-right:0}
.ei-axis2 span{position:absolute;transform:translateX(-50%)}
.ei-axnote{margin:.1rem 0 0;font-size:.78rem;color:var(--muted);text-align:center}
.ei-fig a{color:#8ab4ff;text-decoration:underline;text-underline-offset:2px}
.ei-fig .ei-chip{text-decoration:none}
.ei-rng{background:rgba(255,255,255,.05)}
.ei-range{position:absolute;top:5px;height:6px;border-radius:3px;opacity:.55}
.ei-mid{position:absolute;top:1px;width:14px;height:14px;margin-left:-7px;border-radius:50%;border:2px solid #0a0f1c}
.ei-scale{max-width:420px;margin:.6rem auto 0;font-size:.8rem;color:var(--muted)}
.ei-scale i{display:block;height:10px;border-radius:5px}.ei-scale div{display:flex;justify-content:space-between;margin-top:.2rem}
.ei-nrow{cursor:default}
.ei-srows{display:flex;flex-direction:column;gap:.45rem}
.ei-srow{display:grid;grid-template-columns:7.2rem 1fr;gap:.6rem;align-items:center}
.ei-slab b{display:block;font-size:.9rem;color:var(--text)}.ei-slab span{display:block;font-size:.76rem;color:var(--muted);line-height:1.25}
.ei-stack{display:flex;gap:2px;height:30px}
.ei-seg-b{display:flex;align-items:center;justify-content:center;font-size:.78rem;font-weight:600;border-radius:4px;min-width:3px;overflow:hidden;white-space:nowrap}
.ei-leg i.sq{border-radius:3px}
.ei-reg{cursor:pointer}.ei-reg.on{fill-opacity:.62;stroke-width:3}
.ei-panel{margin-top:.7rem;padding:.8rem 1rem;border:1px solid var(--card-border);border-radius:12px;background:rgba(255,255,255,.04);font-size:.92rem;line-height:1.55;min-height:6.2rem}
.ei-panel b{display:block;color:var(--text);font-size:1rem}.ei-panel span{display:block;color:var(--muted)}
.ei-panel em{display:inline-block;font-style:normal;font-size:.78rem;border:1px solid var(--card-border);border-radius:999px;padding:.05rem .55rem;margin:.2rem 0}
.ei-panel a{color:var(--text)}
.ei-pane-map{margin-top:.2rem}
.ei-time{list-style:none;margin:1.2rem 0;padding:0;border-left:2px solid var(--card-border)}
.ei-time li{position:relative;padding:.1rem 0 .9rem 1.1rem}
.ei-time li::before{content:"";position:absolute;left:-7px;top:.45rem;width:12px;height:12px;border-radius:50%;background:#d95926;border:2px solid #0a0f1c}
.ei-time li.now::before{background:#fff}
.ei-time b{display:block;color:var(--text)}.ei-time span{color:var(--muted);font-size:.92rem}
.ei-note{color:var(--muted);font-size:.84rem;line-height:1.55;margin:.4rem 0 1.2rem}
.ei-src li{margin:.35rem 0}
.ei-scheme{max-width:640px}
</style>"""

SCRIPT = r"""<script>
(function(){
var el=document.getElementById('ei-data');if(!el)return;var DATA=JSON.parse(el.textContent);
function f(x,d){return x.toFixed(d==null?2:d).replace('.',',').replace('-','–');}
function sg(x,d){return (x>0?'+':'')+f(x,d);}
function tip(fig){var t=fig.querySelector('.ei-tip');if(!t){t=document.createElement('div');t.className='ei-tip';t.hidden=true;fig.appendChild(t);}return t;}
function place(t,fig,cx,cy){t.hidden=false;var fr=fig.getBoundingClientRect(),w=t.offsetWidth,h=t.offsetHeight;
var x=cx-fr.left+14;if(x+w>fr.width-6)x=cx-fr.left-w-14;if(x<6)x=6;var y=cy-fr.top-h-12;if(y<6)y=cy-fr.top+18;t.style.left=x+'px';t.style.top=y+'px';}
/* gumbi so skriti brez skripta */
Array.prototype.forEach.call(document.querySelectorAll('.ei-ctl'),function(c){c.hidden=false;});
/* tooltip za elemente z data-tip */
Array.prototype.forEach.call(document.querySelectorAll('[data-tip]'),function(g){var fig=g.closest('.ei-fig'),t=tip(fig);
function show(e){var p=g.getAttribute('data-tip').split('|');t.textContent='';p.forEach(function(s,i){var n=document.createElement(i?'span':'b');n.textContent=s;t.appendChild(n);});
var r=g.getBoundingClientRect();place(t,fig,(e&&e.clientX)||(r.left+r.width/2),r.top);}
g.addEventListener('pointerenter',show);g.addEventListener('pointermove',show);g.addEventListener('focus',show);g.addEventListener('click',show);
g.addEventListener('pointerleave',function(){t.hidden=true;});g.addEventListener('blur',function(){t.hidden=true;});});
/* črtni grafi s križem */
var hidden={};
Array.prototype.forEach.call(document.querySelectorAll('.ei-ln[data-k]'),function(svg){
var fig=svg.closest('.ei-fig'),b=svg.getAttribute('data-box').split(',').map(Number),C=DATA.ch[svg.getAttribute('data-k')],cross=svg.querySelector('.ei-cross'),t=tip(fig);
function hide(){cross.setAttribute('visibility','hidden');t.hidden=true;}
function move(e){var r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*b[4];
var i=Math.round((vx-b[0])/(b[2]-b[0])*b[6]);if(i<0||i>b[6]){hide();return;}
var X=b[0]+(b[2]-b[0])*i/b[6];cross.setAttribute('x1',X);cross.setAttribute('x2',X);cross.setAttribute('visibility','visible');
t.textContent='';var h=document.createElement('b');h.textContent=C.x[i];t.appendChild(h);
C.series.forEach(function(s){if(hidden[s.id]||s.v[i]==null)return;var n=document.createElement('span');var st=document.createElement('strong');st.textContent=sg(s.v[i],C.dec)+' °C';
n.appendChild(document.createTextNode(s.name+': '));n.appendChild(st);n.style.color=s.color==='#e8edf8'?'':s.color;t.appendChild(n);});
place(t,fig,e.clientX,r.top+r.height*.3);}
svg.addEventListener('pointermove',move);svg.addEventListener('pointerdown',move);svg.addEventListener('pointerleave',hide);});
/* preklopi: indeks / lestvica */
Array.prototype.forEach.call(document.querySelectorAll('.ei-seg button[data-show]'),function(btn){btn.addEventListener('click',function(){
var fig=btn.closest('.ei-fig');Array.prototype.forEach.call(fig.querySelectorAll('.ei-seg button'),function(x){x.setAttribute('aria-pressed',x===btn?'true':'false');});
Array.prototype.forEach.call(fig.querySelectorAll('.ei-pane'),function(p){p.hidden=p.getAttribute('data-pane')!==btn.getAttribute('data-show');});
var t=fig.querySelector('.ei-tip');if(t)t.hidden=true;});});
/* dogodki vklop/izklop */
Array.prototype.forEach.call(document.querySelectorAll('.ei-chips .ei-chip'),function(c){c.addEventListener('click',function(){
var on=c.getAttribute('aria-pressed')!=='true';c.setAttribute('aria-pressed',on?'true':'false');var id=c.getAttribute('data-ev');hidden[id]=!on;
Array.prototype.forEach.call(c.closest('.ei-fig').querySelectorAll('.ei-ev[data-ev="'+id+'"]'),function(g){g.style.display=on?'':'none';});});});
/* zemljevid Pacifika: lestvica */
function ramp(v){var S=DATA.ramp;v=Math.max(S[0][0],Math.min(S[S.length-1][0],v));for(var i=0;i<S.length-1;i++){var a=S[i],b=S[i+1];if(v>=a[0]&&v<=b[0]){var t=(v-a[0])/(b[0]-a[0]);
return '#'+[0,1,2].map(function(k){var x=Math.round(a[1][k]+(b[1][k]-a[1][k])*t).toString(16);return x.length<2?'0'+x:x;}).join('');}}}
Array.prototype.forEach.call(document.querySelectorAll('.ei-seg button[data-set]'),function(btn){btn.addEventListener('click',function(){
var fig=btn.closest('.ei-fig'),set=btn.getAttribute('data-set');Array.prototype.forEach.call(fig.querySelectorAll('.ei-seg button'),function(x){x.setAttribute('aria-pressed',x===btn?'true':'false');});
var V=DATA.pac[set];Array.prototype.forEach.call(fig.querySelectorAll('.ei-nrow'),function(g){var r=g.getAttribute('data-r'),v=V[r],narrow=g.closest('.ei-narrow');
var bar=g.querySelector('.ei-nbar'),tx=g.querySelector('.ei-nval');
if(v==null){bar.setAttribute('fill','rgba(255,255,255,.08)');tx.textContent='ni podatka';return;}
bar.setAttribute('fill',ramp(v));tx.textContent=sg(v,1)+(narrow?'':' °C');});});});
/* zemljevid posledic */
var panel=document.getElementById('ei-panel');
function pick(id){var R=DATA.reg[id];if(!R||!panel)return;
Array.prototype.forEach.call(document.querySelectorAll('.ei-reg'),function(r){r.classList.toggle('on',r.getAttribute('data-id')===id);});
Array.prototype.forEach.call(document.querySelectorAll('.ei-chips2 .ei-chip'),function(c){c.setAttribute('aria-pressed',c.getAttribute('data-id')===id?'true':'false');});
panel.textContent='';var b=document.createElement('b');b.textContent=R.name;var e=document.createElement('em');e.textContent=R.cat;
var s=document.createElement('span');s.textContent=R.text;var l=document.createElement('span');l.appendChild(document.createTextNode('Vir: '));
var a=document.createElement('a');a.href=R.url;a.target='_blank';a.rel='noopener';a.textContent=R.src;l.appendChild(a);panel.appendChild(b);panel.appendChild(e);panel.appendChild(s);panel.appendChild(l);}
Array.prototype.forEach.call(document.querySelectorAll('.ei-reg'),function(r){r.addEventListener('click',function(){pick(r.getAttribute('data-id'));});});
Array.prototype.forEach.call(document.querySelectorAll('.ei-chips2 .ei-chip'),function(c){c.addEventListener('click',function(){pick(c.getAttribute('data-id'));});});
})();
</script>"""


def fig(title, sub, inner, caption):
    return (f'<figure class="ei-fig"><h3>{title}</h3>' + (f'<p class="ei-sub">{sub}</p>' if sub else "") +
            f'{inner}<figcaption>{caption}</figcaption></figure>')


def tiles(items):
    return '<div class="ei-tiles">' + "".join(
        f'<div class="ei-tile"><b>{big}{(" <small>" + small + "</small>") if small else ""}</b><span>{text}</span></div>'
        for big, small, text in items) + "</div>"


SRC = {
    "nypost": ("https://nypost.com/2026/11/23/science/mega-el-nino-sees-pacific-region-hit-18-degrees-f-above-average/",
               "Ben Cost: ‘Mega El Niño’ sees Pacific region hit 18 degrees F above average. New York Post, 23. 11. 2026"),
    "dailymail": ("https://www.dailymail.com/sciencetech/article-16314697/Super-El-Nino-MEGA-temperatures-skyrocket.html",
                  "Xantha Leatham: Super El Niño has morphed into a MEGA El Niño. Daily Mail, 23. 11. 2026"),
    "indiatoday": ("https://www.indiatoday.in/science/story/mega-el-nino-pacific-hotspot-galapagos-recrod-warming-wmo-noaa-map-3045621-2026-11-24",
                   "India Today Science Desk: El Niño pushed Pacific Ocean temperatures 10°C past normal, 24. 11. 2026"),
    "geotv": ("https://www.geo.tv/latest/692338-scientists-warn-of-mega-el-nio-as-ocean-temperatures-jump-10c-what-happens-next",
              "Geo.tv: Scientists warn of ‘Mega El Niño’ as ocean temperatures jump 10°C, 23. 11. 2026"),
    "cpc_disc": ("https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml",
                 "NOAA CPC: ENSO Diagnostic Discussion, 12. 11. 2026"),
    "cpc_deck": ("https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/lanina/enso_evolution-status-fcsts-web.pdf",
                 "NOAA CPC: ENSO: Recent Evolution, Current Status and Predictions, 23. 11. 2026"),
    "cpc_oni": ("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", "NOAA CPC: ONI, datoteka oni.ascii.txt (prebrano 24. 11. 2026)"),
    "cpc_roni": ("https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt", "NOAA CPC: RONI, datoteka RONI.ascii.txt (prebrano 24. 11. 2026)"),
    "cpc_probs": ("https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/archives/?month=11&type=strengths&year=2026",
                  "NOAA CPC: Official ENSO Strength Probabilities, november 2026"),
    "bom": ("https://www.bom.gov.au/climate/enso/", "Bureau of Meteorology: Southern hemisphere monitoring, 24. 11. 2026"),
    "c3s": ("https://climate.copernicus.eu/surface-air-temperature-october-2026",
            "Copernicus C3S: Surface air temperature for October 2026 (bilten, 5. 11. 2026)"),
    "c3sseas": ("https://climate.copernicus.eu/seasonal-forecasts", "Copernicus C3S: Seasonal forecasts, 10. 11. 2026"),
    "wmo_sep": ("https://wmo.int/news/media-centre/el-nino-set-become-very-strong-raising-risks-of-extreme-weather-2027",
                "WMO: El Niño set to become very strong, raising risks of extreme weather into 2027, 3. 9. 2026"),
    "wmo_oct": ("https://wmo.int/media/news/wmo-global-seasonal-climate-outlook-informs-humanitarian-action",
                "WMO: Global Seasonal Climate Outlook informs humanitarian action, 26. 10. 2026"),
    "wmo_state": ("https://wmo.int/news/media-centre/state-of-climate-2026-gives-new-meaning-phrase-charts",
                  "WMO: State of the climate in 2026 gives new meaning to phrase ‘off the charts’, november 2026"),
    "wmo_pac": ("https://public.wmo.int/media/news/western-pacific-faces-drier-months-el-nino-strengthens",
                "WMO: Western Pacific faces drier months as El Niño strengthens, 5. 11. 2026"),
    "cb": ("https://www.carbonbrief.org/state-of-the-climate-2026-likely-to-tie-with-2024-as-the-warmest-year-on-record",
           "Carbon Brief: State of the climate: 2026 likely to tie with 2024 as the warmest year on record, oktober 2026"),
    "bbc": ("https://www.bbc.com/weather/articles/c3ekg93vjz9o",
            "BBC Weather: El Niño set to be ‘strongest in living memory’, says Met Office, 21. 8. 2026"),
    "enfen": ("https://enfen.imarpe.gob.pe/download/comunicado-oficial-enfen-n-20-2026/", "ENFEN (Peru): Comunicado Oficial N° 20-2026, 13. 11. 2026"),
    "senamhi_okt": ("https://www.gob.pe/institucion/senamhi/noticias/1461974-el-nino-costero-senamhi-reporta-temperaturas-de-hasta-9-5-c-por-encima-de-lo-normal-en-la-costa-peruana",
                    "SENAMHI (Peru): El Niño Costero, temperature do 9,5 °C nad normalo, 24. 10. 2026"),
    "senamhi_nov": ("https://www.gob.pe/institucion/senamhi/noticias/1475093-altas-temperaturas-y-lluvias-intensas-marcaran-las-proximas-semanas-por-el-nino-advierte-el-senamhi",
                    "SENAMHI (Peru): Altas temperaturas y lluvias intensas marcarán las próximas semanas, 18. 11. 2026"),
    "fews": ("https://fews.net/global/special-report/october-2026", "FEWS NET: 2026–2027 El Niño food security impacts, oktober 2026"),
    "mint": ("https://www.livemint.com/economy/el-nino-india-agriculture-rabi-crop-water-shortage-food-inflation-11795339235210.html",
             "Mint: The El Niño polycrisis, 22. 11. 2026"),
    "floodradar": ("https://www.floodradar.co.uk/el-nino/tracker",
                   "FloodRadar: El Niño live tracker (tedenske vrednosti iz datotek NOAA CPC), 24. 11. 2026"),
    "elninolive": ("https://www.elninolive.com/status", "ElNinoLive: Current El Niño status, 24. 11. 2026"),
    "weatherlinguist": ("https://weatherlinguist.bearblog.dev/winter-202627-in-europe-what-a-record-el-nino-can-and-cannot-tell-us/",
                        "weatherlinguist: Winter 2026/27 in Europe: what a record El Niño can and cannot tell us, 27. 10. 2026 (analiza ERA5, ni recenzirana)"),
    "arso": ("https://siol.net/novice/slovenija/podnebne-spremembe-v-sloveniji-vec-vrocine-manj-snega-703584",
             "Siol.net: Podnebne spremembe v Sloveniji: več vročine, manj snega (pojasnila ARSO), 11. 10. 2026"),
}


# ───────────────────────── članek ─────────────────────────

def build_article(d, H, mask):
    oni, roni = d["oni"], d["roni"]
    A = 8                                    # indeks sezone avg–okt
    assert oni["2026"][A] == 2.46 and all(oni[y][A] < 2.46 for y in ("1982", "1997", "2015", "2023"))
    assert roni["2026"][A] == 1.97 and roni["1997"][A] == 2.07 and all(roni[y][A] < 1.97 for y in ("1982", "2015", "2023"))
    pk_o = {y: max(oni[y]) for y in ("1982", "1997", "2015", "2023")}
    pk_r = {y: max(roni[y]) for y in ("1982", "1997", "2015")}
    assert pk_o["1982"] < 2.46 and pk_o["1997"] < 2.46 < pk_o["2015"], pk_o
    assert all(v > 1.97 for v in pk_r.values())
    assert d["series_max"]["oni"]["value"] == max(max(v) for v in oni.values())
    assert d["series_max"]["roni"]["value"] == max(max(v) for v in roni.values())
    nw = d["nino_weekly"]
    assert nw["rel"][-1] == [4.9, 3.9, 2.4, 0.2] and nw["trad"][-1] == [5.7, 4.7, 3.3, 1.4]
    rows = winters(H, d)
    by_t = sorted(rows, key=lambda r: -r["t"])
    assert {r["phase"] for r in by_t[:2]} == {"el"} and {r["phase"] for r in by_t[-2:]} == {"la"}, "zimska trditev ne drži"
    w1, w2 = by_t[0], by_t[1]
    c1, c2 = by_t[-1], by_t[-2]

    ruler_html = rulers_fig()
    pac_html = pacific_fig(mask, d)
    traj_html, ch1 = traj_fig(d)
    weeks_html, ch2 = weeks_fig(d)
    str_html = strength_fig(d)
    temp_html = temp_fig(d)
    imp_html, reg = impact_fig(mask, SRC)
    rec_html = recica_fig(rows)
    ch = {**ch1, **ch2}
    js = {"ch": ch, "ramp": [[v, list(c)] for v, c in STOPS], "reg": reg,
          "pac": {"trad": {"n12": nw["trad"][-1][0], "n3": nw["trad"][-1][1], "n34": nw["trad"][-1][2], "n4": nw["trad"][-1][3]},
                  "rel": {"n12": nw["rel"][-1][0], "n3": nw["rel"][-1][1], "n34": nw["rel"][-1][2], "n4": nw["rel"][-1][3]},
                  "mon": {"n12": MONTHLY_REL["n12"], "n3": MONTHLY_REL["n3"], "n34": MONTHLY_REL["n34"], "n4": None}}}
    S = lambda k, t: a(SRC[k][0], t)          # povezava na vir

    lead = (f"»Mega El Niño« je vzdevek, ne uradna stopnja, »+10{NBSP}°C« pa ni temperatura Tihega oceana. "
            f"Ryan Maue je 22. novembra na omrežju X objavil dnevni zemljevid ECMWF, na katerem ima ozek pas vode ob obali Peruja in pri Galápagosu "
            f"do 10{NBSP}°C nad povprečjem. Uradni kazalniki za osrednji Pacifik kažejo glede na lestvico in obdobje od +2,0 do +3,3{NBSP}°C, nekateri med njimi pa so res rekordni.")

    short = ('<div class="ei-short"><h3>Na kratko</h3><ul>'
             f'<li><b>Beseda »mega« ni uradna.</b> NOAA ima stanje »El Niño Advisory«, moč dogodka pa označuje kot »zelo močan«.</li>'
             f'<li><b>+10{NBSP}°C je lokalna konica</b> ene dnevne analize. Mesečna konica po Copernicusu je 6–7{NBSP}°C, '
             f'kazalnik Niño 3.4 pa glede na lestvico in obdobje {num(2.0)}–{num(3.3)}{NBSP}°C.</li>'
             f'<li><b>Rekordi so resnični, a ne vsi:</b> mesečno odstopanje v Niño 3.4 po ERA5 je oktobra znašalo +3,21{NBSP}°C, '
             f'ONI za avg–okt je najvišji za to sezono. RONI, po katerem NOAA presoja »zgodovinski« dogodek, pa je bil leta 1997 ob istem času višji.</li>'
             f'<li><b>Vrh še ni mimo:</b> modeli ga pričakujejo decembra ali januarja; NOAA daje okoli 60 % verjetnosti, da bo okt–dec presegel vse od leta 1950.</li>'
             f'<li><b>Za Slovenijo</b> je toplejša in bolj namočena zima verjetnejša, ni pa zagotovljena. Globalno bo najverjetneje najtoplejše leto 2027.</li>'
             '</ul></div>')

    tl = tiles([
        ("+3,21", "°C", "Niño 3.4, oktober po ERA5 (Copernicus): rekord vseh mesecev; prej 2,99 °C (september)"),
        ("+2,46", "°C", "ONI za avg–okt: najvišji za to sezono; 1997: +2,04, 2015: +2,02"),
        ("+1,97", "°C", "RONI za avg–okt: merilo NOAA za »zgodovinski« dogodek; 1997: +2,07"),
        ("≈60", "%", "verjetnost zgodovinskega dogodka (RONI ≥ +2,5 °C) za okt–dec; oktobra 83 %"),
    ])

    s1 = [short, tl,
          f"Izvirnik je objava Ryana Maueja na omrežju X z dne 22. novembra: »+10°C sea surface temperature anomaly near Galapagos and off coast of Peru. "
          f"This is now a Mega El Niño.« Priložil je zemljevid odstopanj temperature morske površine, narejen iz podatkov ECMWF. "
          f"{S('nypost', 'New York Post')} ga je 23. novembra povzel z naslovom o 18{NBSP}°F nad povprečjem, {S('dailymail', 'Daily Mail')} in drugi mediji so sledili.",
          f"Besede »mega« ni uvedla nobena meteorološka služba. {S('geotv', 'Geo.tv')} pravi, da to ni uradna znanstvena razvrstitev, in večina člankov, "
          f"ki ponavljajo »10{NBSP}°C«, v nadaljevanju prizna, da gre za lokalno konico, ne za ves ocean (tako tudi {S('indiatoday', 'India Today')}).",
          f"Dve opombi. Prvič, 10{NBSP}°C je odstopanje, ne temperatura, zato je pravilna pretvorba 18{NBSP}°F in ne 50{NBSP}°F, kot je zapisal Daily Mail. "
          f"Drugič, zemljevida same analize iz svojega okolja nisem mogel preveriti, zato številko povzemam po medijih."]

    s2 = [f"Spodnji graf postavi vse številke, ki so ta teden krožile, na isto lestvico. Razlikujejo se po območju (velika ali majhna regija), "
          f"po času (dan, teden, mesec, tri mesece) in po tem, kaj imajo za »običajno« (večinoma obdobje 1991–2020). "
          f"Zato jih ni mogoče neposredno primerjati, a vsaka je na svojem mestu poštena.",
          fig("Deset številk za isti El Niño", "Odstopanje od povprečja, °C. Dotaknite se vrstice za opis.", ruler_html,
              "Zadnja vrstica je več kot trikrat višja od uradnega kazalnika, a opisuje ozko območje in en dan. "
              f"Viri: {S('cpc_disc', 'NOAA CPC')}, {S('cpc_oni', 'ONI')}, {S('cpc_roni', 'RONI')}, {S('bom', 'BoM')}, {S('c3s', 'Copernicus C3S')}, "
              f"{S('floodradar', 'FloodRadar')} (tedenske vrednosti OISST), {S('nypost', 'New York Post')}."),
          f"Moč El Niña se meri s povprečjem čez veliko območje: Niño 3.4 je pas 5° severno in južno od ekvatorja med 170° in 120° zahodno. "
          f"Konica ob obali pove, kje bo učinek najbolj otipljiv (Peru), ne pa, kako močan je El Niño kot celota.",
          f"Še bolj izrazito je pod površjem. Razprava {S('cpc_disc', 'CPC z 12. novembra')} omenja odstopanja nad +10{NBSP}°C v globini vzhodnega Pacifika. "
          f"»10{NBSP}°C« torej res obstaja, a pod vodo in ne kot temperatura površine."]

    s3 = [f"El Niño nastane, ko oslabijo pasati, ki običajno potiskajo toplo površinsko vodo proti zahodu. Topla plast se razlije proti vzhodu, "
          f"hladno dvigovanje ob obali Južne Amerike pojenja, padavinsko jedro pa se iz Indonezije preseli proti središču Pacifika "
          f"(CPC letos opaža okrepljeno konvekcijo od datumske črte do vzhodnega Pacifika in zatrto nad Indonezijo).",
          fig("Shema: običajno stanje in El Niño", None, schematic(),
              "Shematski prerez ekvatorialnega Pacifika, ni v merilu. Oranžna plast je topla voda, črtkana črta je termoklina."),
          f"Letos se segrevanje stopnjuje proti vzhodu: v regiji Niño 4 je tedensko odstopanje +1,4{NBSP}°C, v Niño 3.4 +3,3{NBSP}°C, v Niño 3 +4,7{NBSP}°C "
          f"in v obalni regiji Niño 1+2 +5,7{NBSP}°C. Na zadnjem zemljevidu lahko preklopite med tremi lestvicami.",
          fig("Odstopanje po regijah Niño", "Tedensko, 15.–21. 11. 2026 (preklopite lestvico)", pac_html,
              f"Pikčast zemljevid kaže kopno; črtkani pravokotniki so regije Niño (Niño 3.4 leži znotraj Niño 3 in deloma Niño 4). "
              f"Relativne tedenske vrednosti so iz {S('cpc_deck', 'predstavitve CPC z 23. 11.')}, tradicionalne po sledilnikih, ki berejo datoteke NOAA "
              f"({S('floodradar', 'FloodRadar')}, {S('elninolive', 'ElNinoLive')}), mesečne za oktober iz {S('cpc_disc', 'razprave CPC')}; "
              f"za Niño 4 mesečne vrednosti v razpravi ni. Najnovejših vrstic datoteke NOAA nisem mogel prebrati sam."),
          f"Razlika med lestvicama je pomembna. Tradicionalni indeks meri samo odstopanje v regiji, relativni (RONI) pa od njega odšteje odstopanje povprečja vseh tropov "
          f"(20° S–20° J). Tropi se zaradi podnebnih sprememb segrevajo povsod, zato tradicionalni indeks sam po sebi raste; relativni natančneje pokaže, koliko je "
          f"ekvatorialni Pacifik toplejši od svoje okolice. NOAA zdaj verjetnosti preverja z RONI, BoM pa je na relativne indekse prešel septembra 2025."]

    tline = ('<ul class="ei-time">' + "".join(f"<li{' class=\"now\"' if now else ''}><b>{t}</b><span>{x}</span></li>" for t, x, now in [
        ("Marec 2026", f"Po ENFEN se začne obalni El Niño (Niño 1+2). Od sredine aprila se segrevanje širi proti središču Pacifika ({S('cpc_deck', 'CPC')}).", False),
        ("Junij 2026", f"NOAA razglasi stanje El Niño Advisory ({a('/blog/el-nino-2026.html', 'naš prvi članek')}).", False),
        ("3. september", f"WMO: skoraj 100 % verjetnost, da bo El Niño trajal do februarja 2027 ({S('wmo_sep', 'WMO')}).", False),
        ("September", f"Dnevno odstopanje v Niño 3.4 preseže rekord iz novembra 2015 in od takrat ostane nad njim ({S('cb', 'Carbon Brief')}). Mesečno: 2,99{NBSP}°C.", False),
        ("Oktober", f"Mesečno odstopanje v Niño 3.4 doseže +3,21{NBSP}°C; peruanska obala je do 6–7{NBSP}°C nad povprečjem ({S('c3s', 'Copernicus')}).", False),
        ("26. oktober", f"WMO: temperatura v tropskem Pacifiku lahko do januarja naraste na 3,8{NBSP}°C nad povprečjem ({S('wmo_oct', 'WMO')}).", False),
        ("12. november", f"NOAA zniža verjetnost »zgodovinskega« dogodka z 83 na okoli 60 % ({S('cpc_disc', 'CPC')}).", False),
        ("22.–23. november", f"Maue objavi zemljevid, New York Post pa naslov o »mega El Niñu« ({S('nypost', 'NY Post')}).", False),
        ("24. november", f"BoM: relativni Niño 3.4 je +2,67{NBSP}°C, vrh dogodka doslej +2,88{NBSP}°C ({S('bom', 'BoM')}).", True),
    ]) + "</ul>")
    s4 = [f"Kako je do tega prišlo, v devetih postankih:", tline]

    s5 = [f"Odgovor je: več rekordov je resničnih, a ne vsi. Po virih:",
          '<ul>'
          f'<li><b>Copernicus (ERA5).</b> Oktobrska povprečna temperatura morja v Niño 3.4 je bila 29,94{NBSP}°C, odstopanje 3,21{NBSP}°C. '
          f'Obe vrednosti presegata vrhove El Niñov 1982/83, 1997/98 in 2015/16; prejšnji rekord meseca je bil september z 2,99{NBSP}°C ({S("c3s", "C3S")}).</li>'
          f'<li><b>Dnevno (Carbon Brief).</b> Od septembra je odstopanje nad rekordom iz novembra 2015; 18. oktobra je bilo okoli 3,5{NBSP}°C, približno 0,4{NBSP}°C nad vrhom iz leta 2015 '
          f'(osnova 1996–2025, {S("cb", "Carbon Brief")}).</li>'
          f'<li><b>Tedensko, vzhod (NOAA).</b> Niño 1+2 (+5,7{NBSP}°C) in Niño 3 (+4,7{NBSP}°C) sta najvišji tedenski vrednosti v nizu od leta 1981. '
          f'Niño 3.4 je 0,1{NBSP}°C pod vrhom dogodka (+3,4{NBSP}°C konec oktobra) ({S("floodradar", "po FloodRadar")}).</li>'
          f'<li><b>BoM.</b> Relativni Niño 3.4 je dosegel +2,88{NBSP}°C, zdaj je +2,67{NBSP}°C; najvišje mesečne vrednosti od leta 1900, ki je iz let 1982/83, še ni presegel ({S("bom", "BoM")}).</li>'
          f'<li><b>ONI (tri mesece).</b> +2,46{NBSP}°C za avg–okt je najvišja vrednost za to sezono doslej (1997: +2,04, 2015: +2,02).</li>'
          '</ul>',
          f"Česa ni: RONI, po katerem NOAA presoja »zgodovinski« dogodek, je za avg–okt +1,97{NBSP}°C, leta 1997 pa je bil ob istem času +2,07{NBSP}°C. "
          f"Tudi na tedenski relativni lestvici je Niño 3.4 (+2,4{NBSP}°C) še pod rekordom iz konca leta 1982 (+2,9{NBSP}°C). "
          f"Verjetnost zgodovinskega dogodka (RONI ≥ +2,5{NBSP}°C v okt–dec) je 12. novembra padla z 83 na okoli 60 %.",
          fig("Tri velikani in letošnje leto", "Tromesečno odstopanje v Niño 3.4 po sezonah. Preklopite med ONI in RONI, izklopite dogodke v legendi.", traj_html,
              f"Od decembra–februarja v letu začetka do novembra–januarja naslednje leto; 2026 se konča z avg–okt, ker novejših sezon še ni. "
              f"Črtkana črta: prag, ki ga NOAA šteje za »zgodovinski« dogodek. Viri: {S('cpc_oni', 'ONI')} in {S('cpc_roni', 'RONI')} (NOAA CPC, prebrano 24. 11. 2026)."),
          f"Pogled na vrhove: ONI je letos že nad vrhom 1997/98 (+{num(pk_o['1997'], 2)}) in 1982/83 (+{num(pk_o['1982'], 2)}); samo vrh 2015/16 (+{num(pk_o['2015'], 2)}) je višji. "
          f"RONI jih še ne dosega: vrhovi so +{num(pk_r['1982'], 2)} (1982/83), +{num(pk_r['1997'], 2)} (1997/98) in +{num(pk_r['2015'], 2)} (2015/16), letošnja vrednost je +{num(roni['2026'][A], 2)}. "
          f"Največja vrednost v celotnih datotekah od leta 1950 je +{num(d['series_max']['oni']['value'], 2)} pri ONI ({d['series_max']['oni']['season']}) in +{num(d['series_max']['roni']['value'], 2)} pri RONI ({d['series_max']['roni']['season']})."]

    s6 = [f"Kratek odgovor: v osrednjem Pacifiku se rast zadnje tedne ustavlja, na vzhodu še narašča, modeli pa vrh pričakujejo decembra ali januarja.",
          fig("Zadnjih 12 tednov v štirih regijah", "Tedensko odstopanje, °C (preklopite lestvico)", weeks_html,
              f"Niño 3.4 in Niño 4 se od začetka oktobra komaj spreminjata, Niño 3 in Niño 1+2 pa sta v zadnjem tednu poskočila. "
              f"Podatki: OISST v2.1, NOAA CPC, osnova 1991–2020, povzeto po {S('floodradar', 'FloodRadar')}; zadnji teden potrjen v {S('cpc_deck', 'predstavitvi CPC')}."),
          f"{S('cpc_deck', 'CPC')} dodaja, da so podpovršinska odstopanja od sredine oktobra manjša in da se hladna voda na zahodu širi proti datumski črti. "
          f"To je znak, da se je dotok toplote upočasnil, ne da bi bil vrh nujno mimo.",
          fig("Uradna verjetnost po razredih moči", "NOAA CPC, napoved z 12. 11. 2026; razredi RONI", str_html,
              f"Odstotki po razredih RONI; seštevek vsake vrstice je 100 %. Razred »zelo močan« je vse nad +2,0{NBSP}°C, zato ne pove, koliko nad. "
              f"Vir: {S('cpc_probs', 'NOAA CPC')}. Naslednja razprava je 10. decembra."),
          f"Modeli. {S('cb', 'Carbon Brief')} je analiziral 656 napovedi 14 modelov: povprečni vrh je okoli 4{NBSP}°C, deset modelov ga postavlja v december, štirje v november. "
          f"WMO je 26. oktobra zapisal, da lahko temperatura v tropskem Pacifiku do januarja naraste na 3,8{NBSP}°C ({S('wmo_oct', 'WMO')}). "
          f"BoM pričakuje vrh decembra ali januarja in relativni Niño 3.4 nad vsem od leta 1950; NOAA oslabitev v začetku 2027. "
          f"Pridržek, ki ga omenja Carbon Brief: napovedani vrh je zunaj niza, na katerem so se modeli učili."]

    s7 = [f"Moč El Niña ne pove, kje in kako hude bodo posledice. WMO poudarja, da učinek določajo tudi Indijski ocean in Atlantik, in da je »zelo močan« El Niño "
          f"lahko tudi z blagimi posledicami v posamezni državi ({S('wmo_sep', 'WMO')}). Zemljevid prikazuje, kje so po napovedih in dosedanjih meritvah običajno bolj suho ali bolj namočeno.",
          fig("Kje El Niño običajno prinese več ali manj padavin", "Dotaknite se pravokotnika ali gumba za podrobnosti in vir", imp_html,
              "Shematsko: pravokotniki so grobe meje območij, ne meje držav in ne natančna območja padavin. Napovedi (WMO, Copernicus, FEWS NET) so sezonske verjetnosti, ne napovedi posameznih dni; "
              "Indija je že izmerjena."),
          '<ul>'
          f'<li><b>Peru.</b> ENFEN pričakuje obalni El Niño »izredne« jakosti do februarja 2027 in šibitev do julija; padavine nad normalo, rekordna temperatura zraka ({S("enfen", "ENFEN")}). '
          f'V drugi dekadi oktobra je bila povprečna najvišja temperatura na osrednji obali 6,8{NBSP}°C nad običajno; leta 1997 2,9{NBSP}°C, leta 2023 2,6{NBSP}°C ({S("senamhi_okt", "SENAMHI")}).</li>'
          f'<li><b>Južna Afrika.</b> Pozen začetek deževja in tveganje suše; največ pomoči bo potrebne v sušni sezoni 2027/28 ({S("fews", "FEWS NET")}).</li>'
          f'<li><b>Indija.</b> Monsun je bil 13 % pod normalo, najslabši od 2015; prehranska inflacija je oktobra 8,9 % ({S("mint", "Mint")}).</li>'
          f'<li><b>Svetovni pridelki.</b> V močnih El Niñih od leta 1980 se je svetovna proizvodnja pšenice, koruze in riža v povprečju malo spremenila, trpijo pa posamezni izvozniki, npr. Južna Afrika (koruza) in Avstralija (pšenica); '
          f'USDA letos napoveduje v Avstraliji 14 % manj pšenice ({S("fews", "FEWS NET")}).</li>'
          f'<li><b>Zdravje.</b> Svetovna zdravstvena organizacija je prvič razglasila pričakovane učinke za zdravstveni izredni dogodek ({S("wmo_state", "WMO")}).</li>'
          '</ul>']

    s8 = [f"Globalne temperature za Pacifikom zaostajajo za približno tri mesece, zato je učinek največji v letu po vrhu. WMO navaja, da El Niño običajno prispeva 0,1–0,2{NBSP}°C k letni globalni temperaturi "
          f"({S('wmo_state', 'WMO')}). Copernicus je oktober 2026 označil za najtoplejši oktober doslej, 1,75{NBSP}°C nad predindustrijsko ravnjo; leto 2026 je skoraj gotovo nad 1,5{NBSP}°C, "
          f"z 80 % verjetnostjo drugo najtoplejše in 20 % verjetnostjo rekorda ali izenačenja ({S('c3s', 'C3S')}).",
          fig("Kje bo 2027", "Globalna temperatura, °C nad predindustrijsko ravnjo; povprečje šestih naborov", temp_html,
              f"Carbon Brief: 2027 bo s 96 % verjetnostjo toplejše od vseh doslej; za 2026 je verjetnost rekorda 67 %. Projekcija predpostavlja, da odnos iz preteklih dogodkov velja tudi za tako močnega; "
              f"če učinek ne bo večji od najmočnejših doslej, bi bila verjetnost rekorda za 2026 blizu 50 %. Met Office je že avgusta ocenil, da bo 2027 »zelo verjetno« najtoplejše leto ({S('bbc', 'BBC')}). Vir: {S('cb', 'Carbon Brief')}.")]

    s9 = [f"Kratek odgovor: verjetnejša je toplejša in bolj namočena zima, zagotovljena ni. {S('c3sseas', 'Copernicus')} je 10. novembra zapisal, da je v večini Evrope verjetna bolj namočena zima "
          f"(razen skrajnega severa in juga), vzorec zračnega tlaka pa spominja na negativno arktično oscilacijo; toplo je zelo verjetno na jugozahodu, drugod verjetneje, na severovzhodu manj zanesljivo.",
          f"ARSO opozarja, da tudi nadpovprečno topla zima ne izključuje mraza: v njej se lahko pojavijo krajša hladna obdobja, izraziti prodori in obilnejše sneženje, uporabnost sezonskih napovedi pa je pri nas omejena "
          f"({S('arso', 'Siol.net po pojasnilih ARSO')}).",
          f"Zgodovina daje podoben, a šibak signal. Neodvisna analiza ERA5 za sedem zim z ONI ≥ +1,5{NBSP}°C od leta 1950 ({S('weatherlinguist', 'weatherlinguist')}, ni recenzirana) kaže za srednjo in vzhodno Evropo "
          f"okoli +1,1 do +1,4{NBSP}°C nad trendom, na severu nekaj več padavin (+5–7 %) in na jugu manj (okoli −17 % v Iberiji, Italiji in na Balkanu); a je bil NAO v petih od sedmih zim pozitiven. "
          f"Slovenija leži na meji med tema vzorcema, zato je tak signal tu težko razbrati (moja razlaga).",
          fig("Zime v Rečici in faza ENSO", "Povprečna temperatura od decembra do februarja, IREICA1", rec_html,
              f"Povprečje dec–feb na postaji (samo zunanja meritev), pod stolpci ONI za isto obdobje. Najtoplejši zimi sta bili zimi z El Niñom ({w1['name']}: {num(w1['t'], 1)}{NBSP}°C, {w2['name']}: {num(w2['t'], 1)}{NBSP}°C), "
              f"najhladnejši pa zimi z La Niño ({c1['name']}: {num(c1['t'], 1)}{NBSP}°C, {c2['name']}: {num(c2['t'], 1)}{NBSP}°C). Sedem zim je premalo za sklep, trend segrevanja pa dviguje novejše zime."),
          f"Za sneg to pomeni: toplejša in vlažnejša zima pogosteje prinese dež namesto snega v nižinah, posamezni hladni vdori pa ostajajo mogoči. "
          f"Podrobnosti so v člankih o {a('/blog/zima-2026-2027-el-nino-napoved.html', 'zimi 2026/27 in El Niñu')}, o {a('/blog/polarni-vrtinec-se-je-ustavil-novembra-1110.html', 'polarnem vrtincu')} "
          f"in {a('/blog/sneg-prihodnji-teden-sreda-cetrtek-1121.html', 'snegu ta teden')}; za konkretne dni gledajte {a('/zima/', 'kratkoročne napovedi')}."]

    s10 = ['<ul>'
           f'<li><b>30. novembra:</b> novo sporočilo ENFEN (Peru).</li>'
           f'<li><b>10. decembra:</b> mesečna razprava NOAA. Ali verjetnost zgodovinskega dogodka ostane okoli 60 %?</li>'
           f'<li><b>Tedensko:</b> BoM in CPC objavljata nove tedenske vrednosti; ključno je, ali se Niño 3.4 spet dvigne nad +3,4{NBSP}°C (tradicionalno).</li>'
           f'<li><b>Januarja:</b> ko bo december končan, bo znan RONI za okt–dec, merilo za »zgodovinski« dogodek.</li>'
           '</ul>',
           f"ONI in Niño 3.4 sproti spremljamo na strani {a('/indeksi/', 'Indeksi AO, NAO in ENSO')}. Članek je posnetek stanja 24. novembra 2026 in se ne osvežuje sam. "
           f"Ne verjemite naslovom, ki ne povedo, katero območje, obdobje in osnovo imajo v mislih: pri El Niñu je to polovica odgovora.",
           '<h3>Viri</h3><ul class="ei-src">' + "".join(f"<li>{a(u, t)}</li>" for u, t in SRC.values()) + "</ul>",
           f'<script type="application/json" id="ei-data">{json.dumps(js, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")}</script>' + SCRIPT]
    s10[-1] = '<div class="ei-js">' + s10[-1] + "</div>"

    sections = [
        {"id": "naslov", "label": "01 · Naslov", "heading": "Od kod je prišlo »+10 °C«", "paragraphs": s1},
        {"id": "stevilke", "label": "02 · Številke", "heading": "Isti ocean, deset različnih ravnil", "paragraphs": s2},
        {"id": "zemljevid", "label": "03 · Zemljevid", "heading": "Segrevanje narašča proti vzhodu", "paragraphs": s3},
        {"id": "casovnica", "label": "04 · Časovnica", "heading": "Kako smo prišli do tu", "paragraphs": s4},
        {"id": "rekordi", "label": "05 · Rekordi", "heading": "Kateri rekord je resničen", "paragraphs": s5},
        {"id": "vrh", "label": "06 · Napoved", "heading": "Ali je vrh že mimo?", "paragraphs": s6},
        {"id": "svet", "label": "07 · Svet", "heading": "Kaj to pomeni po svetu", "paragraphs": s7},
        {"id": "2027", "label": "08 · Podnebje", "heading": "Leto 2027 bo verjetno rekordno", "paragraphs": s8},
        {"id": "slovenija", "label": "09 · Slovenija", "heading": "Kaj to pomeni za našo zimo", "paragraphs": s9},
        {"id": "kaj-spremljati", "label": "10 · Kaj zdaj", "heading": "Kaj spremljati v naslednjih tednih", "paragraphs": s10},
    ]
    title = "Mega El Niño: 10 °C je konica, rekordi pa so resnični"
    desc = ("»Mega El Niño« ni uradna stopnja, +10 °C pa velja za ozko območje. Kaj kažejo NOAA, Copernicus, BoM in WMO ter kaj to pomeni za 2027 in našo zimo.")
    assert len(title) <= 60, len(title)
    assert len(desc) <= 160, len(desc)
    return {
        "title": title, "meta_description": desc,
        "tags": ["el niño", "pacifik", "podnebje", "zima", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "night-fog-valley", "og_accent_hex": "#d95926",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Podatki: NOAA CPC (ONI, RONI, tedenske vrednosti, verjetnosti), BoM, Copernicus C3S, WMO, Carbon Brief, ENFEN in SENAMHI (Peru), "
                         "FEWS NET; postaja IREICA1 (zunanja povprečna dnevna temperatura od 7. 11. 2019). Zemljevid kopnega: Natural Earth (javna domena). "
                         "Članek je posnetek stanja 24. 11. 2026 in se ne osvežuje sam."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<(svg|style|script).*?</\1>", "", h, flags=re.S)
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


def make_og_background(mask, path):
    """OG ozadje: temna podlaga, pikčast Pacifik, oranžen sij na vzhodu. Brez fotografije, brez tuje slike."""
    from PIL import Image, ImageDraw, ImageFilter
    W, H = 1600, 840
    img = Image.new("RGB", (W, H), (7, 11, 22))
    cols, rows = pacific_grid(mask)
    cell = W / 60
    oy = (H - 20 * cell) / 2 + 40
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = (255 - 120) / 3 * cell, oy + 10 * cell
    gd.ellipse((cx - 330, cy - 130, cx + 330, cy + 130), fill=(190, 70, 20))
    gd.ellipse((cx + 150, cy - 40, cx + 330, cy + 90), fill=(240, 120, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L").point(lambda v: min(255, v * 2))), .55)
    d = ImageDraw.Draw(img)
    R = mask["rows"]
    for ri, r in enumerate(rows):
        for ci, c in enumerate(cols):
            if R[r][c] == "1":
                x, y = (ci + .5) * cell, oy + (ri + .5) * cell
                d.ellipse((x - cell * .26, y - cell * .26, x + cell * .26, y + cell * .26), fill=(96, 114, 144))
    img.save(path, quality=92)


def main():
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    d, H, mask = load()
    article = build_article(d, H, mask)
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
        og_title="Mega El Niño:\n10 °C je konica", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html ({len(html) // 1024} kB)")
    if wire or "--og" in sys.argv:
        try:
            import tempfile
            tmp = os.path.join(tempfile.mkdtemp(), "og-bg.jpg")
            make_og_background(mask, tmp)
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
