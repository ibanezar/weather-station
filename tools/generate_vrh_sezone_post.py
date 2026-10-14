#!/usr/bin/env python3
"""
tools/generate_vrh_sezone_post.py -- »Vrh gobarske sezone je oktobra. Šest let podatkov« (14. 10. 2026).

Ročno napisan podatkovni članek. Vse številke v besedilu, grafih in tabelah pridejo iz
`data/inat-glive-po-tednih.json` (tools/study_inat_glive_po_tednih.py; samo agregati opažanj po tednih)
in `gobarska-napoved/trend.json` (mesečno povprečje indeksa); besedilo nič ne izmišljuje. Trditve v
besedilu varujejo assert-i: če se podatki osvežijo in trditev ne drži več, generator pade -- besedilo je
treba pregledati, ne zaobiti asserta.

Članek je posnetek na dan objave in se ne prepisuje samodejno. Po CLAUDE.md gre ročni članek skozi lekturo
(`lektura.yml` je od 2. 10. 2026 izklopljena -- do ponovnega vklopa ostane slogovni pregled po
docs/slog-pisanja.md). `--text` zapiše čisto besedilo za lekturo v docs/lektura-vrh-sezone-oktober.txt.

Usage:
    python3 tools/generate_vrh_sezone_post.py [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import os
import re
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
DATA = os.path.join(ROOT, "data", "inat-glive-po-tednih.json")
TREND = os.path.join(ROOT, "gobarska-napoved", "trend.json")
SLUG = "vrh-gobarske-sezone-oktober-1014"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-vrh-sezone-oktober.txt")
NBSP = " "
GREEN, GREY, AMBER = "#34d399", "#8aa0bd", "#fbbf24"   # poudarek (letos), umirjeno ozadje (prejšnja leta), pas vrha
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
SURFACE = "#0a0f1c"                                      # ozadje kartice (obroba označb)
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LAST = 2026
JUL1 = lambda y: datetime.date(y, 7, 1)
MIN_ALL = 150                                            # teden z manj vsemi opažanji se v črti izpusti
BAND = (98, 119)                                         # 7. 10.–27. 10. kot dnevi od 1. 7. (konec 27. 10. = 119)
DOM = 154                                                # 22 tednov od 1. 7.


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=0):
    return num(x, d) + f"{NBSP}%"


def dm(d):
    return f"{d.day}. {d.month}."


def opaz(n):
    """število + oblika »opažanje« (1 opažanje, 2 opažanji, 3–4 opažanja, 5+ opažanj)."""
    n = int(n)
    w = {1: "opažanje", 2: "opažanji", 3: "opažanja", 4: "opažanja"}.get(n % 100, "opažanj") if n % 100 < 5 else "opažanj"
    return f"{n}{NBSP}{w}"


def week_label(start):
    """»7.–13. 10.« ali »28. 10.–3. 11.«."""
    e = start + datetime.timedelta(6)
    if start.month == e.month:
        return f"{start.day}.–{e.day}. {e.month}."
    return f"{start.day}. {start.month}.–{e.day}. {e.month}."


# ───────────────────────── podatki ─────────────────────────

def load():
    D = json.load(open(DATA, encoding="utf-8"))
    weeks = D["tedni"]
    by_year = {}
    for k, v in weeks.items():
        d = datetime.date.fromisoformat(k)
        by_year.setdefault(d.year, []).append((d, v))
    for y in by_year:
        by_year[y].sort(key=lambda x: x[0])
    return D, by_year


def share(v, g="basidio"):
    return 100 * v[g] / v["vse"]


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def _axes_frame(w, h, pl, pr, pt, pb, ymax, ticks, yfmt):
    iw, ih = w - pl - pr, h - pt - pb
    parts = []
    for t in ticks:
        y = pt + ih - ih * t / ymax
        parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pl - 6}" y="{y + 3.5:.1f}" text-anchor="end" font-size="11" fill="{MUTED}">{yfmt(t)}</text>')
    return parts


def season_line_chart(series, ymax, ticks, yfmt, aria, band=True, w=440, h=300):
    """series = [{name, color, width, pts:[(offset_dni, vrednost|None, opis)], hl}]; x = dnevi od 1. 7. (sredina tedna)."""
    pl, pr, pt, pb = 40, 14, 22, 30
    iw, ih = w - pl - pr, h - pt - pb
    X = lambda off: pl + iw * off / DOM
    Y = lambda v: pt + ih - ih * v / ymax
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{aria}" xmlns="http://www.w3.org/2000/svg">']
    if band:
        p.append(f'<rect x="{X(BAND[0]):.1f}" y="{pt}" width="{X(BAND[1]) - X(BAND[0]):.1f}" height="{ih}" '
                 f'fill="{AMBER}" fill-opacity=".13"><title>7.–27. oktober</title></rect>')
        p.append(f'<text x="{(X(BAND[0]) + X(BAND[1])) / 2:.1f}" y="{pt - 7}" text-anchor="middle" font-size="10.5" '
                 f'fill="{MUTED}">7.–27. 10.</text>')
    p += _axes_frame(w, h, pl, pr, pt, pb, ymax, ticks, yfmt)
    for off, lab in ((0, "jul"), (31, "avg"), (62, "sep"), (92, "okt"), (123, "nov")):
        p.append(f'<line x1="{X(off):.1f}" x2="{X(off):.1f}" y1="{pt + ih}" y2="{pt + ih + 4}" stroke="{MUTED}" stroke-opacity=".6"/>')
        p.append(f'<text x="{X(off) + 3:.1f}" y="{h - 9}" font-size="11" fill="{MUTED}">{lab}</text>')
    p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{pt + ih}" y2="{pt + ih}" stroke="{MUTED}" stroke-opacity=".5"/>')
    for s in series:
        run = []
        runs = []
        for off, v, tip in s["pts"]:
            if v is None:
                if run:
                    runs.append(run)
                run = []
            else:
                run.append((off, v))
        if run:
            runs.append(run)
        for r in runs:
            if len(r) > 1:
                d = "M" + " L".join(f"{X(o):.1f},{Y(v):.1f}" for o, v in r)
                op = "1" if s.get("hl") else ".8"
                p.append(f'<path d="{d}" fill="none" stroke="{s["color"]}" stroke-width="{s["width"]}" '
                         f'stroke-linejoin="round" stroke-linecap="round" opacity="{op}"/>')
        for off, v, tip in s["pts"]:
            if v is not None:
                p.append(f'<circle cx="{X(off):.1f}" cy="{Y(v):.1f}" r="7" fill="transparent"><title>{tip}</title></circle>')
        if s.get("hl"):
            pts = [(o, v) for o, v, _ in s["pts"] if v is not None]
            o, v = pts[-1]
            p.append(f'<circle cx="{X(o):.1f}" cy="{Y(v):.1f}" r="4.5" fill="{s["color"]}" stroke="{SURFACE}" stroke-width="2"/>')
            p.append(f'<text x="{X(o) - 8:.1f}" y="{Y(v) - 8:.1f}" text-anchor="end" font-size="11.5" font-weight="700" '
                     f'fill="{INK}" stroke="{SURFACE}" stroke-width="3.5" paint-order="stroke" stroke-linejoin="round">{s["name"]}</text>')
    p.append("</svg>")
    return "".join(p)


def peak_dot_chart(rows, w=440):
    """rows = [(leto, off_vrha_stevilo, stevilo, off_vrha_delez, tip1, tip2)]; x = dnevi od 1. 7. (začetek tedna + 3,5)."""
    pl, pr, pt, pb = 44, 70, 24, 30
    rh = 34
    h = pt + pb + rh * len(rows)
    lo, hi = 84, 133
    iw = w - pl - pr
    X = lambda off: pl + iw * (off - lo) / (hi - lo)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Teden z največ opaženimi gobami po letih" xmlns="http://www.w3.org/2000/svg">']
    p.append(f'<rect x="{X(BAND[0]):.1f}" y="{pt - 4}" width="{X(BAND[1]) - X(BAND[0]):.1f}" height="{rh * len(rows) + 8}" '
             f'fill="{AMBER}" fill-opacity=".13"><title>7.–27. oktober</title></rect>')
    p.append(f'<text x="{(X(BAND[0]) + X(BAND[1])) / 2:.1f}" y="{pt - 9}" text-anchor="middle" font-size="10.5" fill="{MUTED}">7.–27. 10.</text>')
    base = pt + rh * len(rows)
    for off, lab in ((92, "1. 10."), (106, "15. 10."), (123, "1. 11.")):
        p.append(f'<line x1="{X(off):.1f}" x2="{X(off):.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{X(off):.1f}" y="{base + 16}" text-anchor="middle" font-size="11" fill="{MUTED}">{lab}</text>')
    for i, (y, off_n, n, off_s, tip1, tip2) in enumerate(rows):
        cy = pt + rh * i + rh / 2
        p.append(f'<text x="{pl - 8}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{y}</text>')
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<circle cx="{X(off_s):.1f}" cy="{cy:.1f}" r="8" fill="none" stroke="{GREY}" stroke-width="2"><title>{tip2}</title></circle>')
        p.append(f'<circle cx="{X(off_n):.1f}" cy="{cy:.1f}" r="6" fill="{GREEN}" stroke="{SURFACE}" stroke-width="2"><title>{tip1}</title></circle>')
        p.append(f'<text x="{w - pr + 8}" y="{cy + 4:.1f}" font-size="11" fill="{MUTED}">{n} opaž.</text>')
    p.append("</svg>")
    return "".join(p)


def month_range_chart(items, w=440, h=250):
    """items = [(oznaka, mediana, min, max, opis)] -- stolpec = mediana čez leta, ročaj = najmanjše/največje leto."""
    pl, pr, pt, pb = 40, 12, 20, 28
    iw, ih = w - pl - pr, h - pt - pb
    top = 60
    slot = iw / len(items)
    bw = min(46, slot * 0.6)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Delež gob med vsemi opažanji po mesecih, mediana in razpon let" xmlns="http://www.w3.org/2000/svg">']
    p += _axes_frame(w, h, pl, pr, pt, pb, top, (0, 15, 30, 45, 60), lambda t: f"{int(t)}{NBSP}%")
    for i, (lab, med, lo, hi, tip) in enumerate(items):
        cx = pl + slot * (i + 0.5)
        x0 = cx - bw / 2
        bh = ih * med / top
        y0 = pt + ih - bh
        r = min(4, bh)
        p.append(f'<path d="M{x0:.1f},{pt + ih:.1f} V{y0 + r:.1f} Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f} H{x0 + bw - r:.1f} '
                 f'Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + r:.1f} V{pt + ih:.1f} Z" fill="{GREEN}"><title>{tip}</title></path>')
        ylo, yhi = pt + ih - ih * lo / top, pt + ih - ih * hi / top
        p.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{ylo:.1f}" y2="{yhi:.1f}" stroke="{INK}" stroke-width="1.6"/>')
        for yy in (ylo, yhi):
            p.append(f'<line x1="{cx - 6:.1f}" x2="{cx + 6:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{INK}" stroke-width="1.6"/>')
        p.append(f'<text x="{cx:.1f}" y="{h - 9}" text-anchor="middle" font-size="11" fill="{MUTED}">{lab}</text>')
    p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{pt + ih}" y2="{pt + ih}" stroke="{MUTED}" stroke-opacity=".5"/>')
    p.append("</svg>")
    return "".join(p)


def legend(entries):
    out = []
    for n, kind, c in entries:
        if kind == "line":
            sw = f'<i class="vs-ln" style="background:{c}"></i>'
        elif kind == "ring":
            sw = f'<i class="vs-ring" style="border-color:{c}"></i>'
        elif kind == "dot":
            sw = f'<i class="vs-dot" style="background:{c}"></i>'
        elif kind == "band":
            sw = f'<i class="vs-band" style="background:{c}"></i>'
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
.vs-leg i.vs-ln{height:3px;border-radius:2px;width:1.1rem;vertical-align:.25rem}
.vs-leg i.vs-dot{border-radius:50%}
.vs-leg i.vs-ring{border-radius:50%;background:none;border:2px solid}
.vs-tbl{overflow-x:auto;max-width:100%;margin:1rem 0}
.vs-tbl table{border-collapse:collapse;width:100%;font-size:.86rem}
.vs-tbl th,.vs-tbl td{padding:.42rem .5rem;text-align:right;border-bottom:1px solid var(--border)}
.vs-tbl td{white-space:nowrap}
.vs-tbl th{vertical-align:bottom;line-height:1.3;color:var(--muted);font-weight:600;font-size:.76rem}
.vs-tbl th:first-child,.vs-tbl td:first-child{text-align:left}
.vs-tbl tr.vs-now td{font-weight:700;background:rgba(52,211,153,.08)}
.vs-note{color:var(--muted);font-size:.82rem;line-height:1.5;margin:-.4rem 0 1.2rem}
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

def build_article(D, by_year):
    P = D["povzetek"]
    B, A, F = P["basidio"], P["agarico"], P["fungi"]
    base = datetime.date(2020, 7, 1)

    def off_of(d):                       # dnevi od 1. 7. istega leta
        return (d - JUL1(d.year)).days

    # --- trditve članka: če podatki tega ne kažejo več, generator pade ---
    peak_start = {y: datetime.date.fromisoformat(B[str(y)]["teden_z_najvec"]["zacetek"]) for y in YEARS}
    for y in YEARS:
        assert (peak_start[y].month, peak_start[y].day) in ((10, 7), (10, 14), (10, 21)), \
            f"{y}: vrh ni v 7.–27. oktobru -- naslov in uvod trdita drugače"
        for G in (A, F):                 # enak teden pri klobučnicah in pri kraljestvu
            assert G[str(y)]["teden_z_najvec"]["zacetek"] == B[str(y)]["teden_z_najvec"]["zacetek"]
    sh = {y: {int(m): v for m, v in B[str(y)]["delez_po_mesecih"].items()} for y in YEARS}
    for y in YEARS:
        assert sh[y][10] > sh[y][9], f"{y}: oktober ni višji od septembra"
    nov_lower = [y for y in YEARS if sh[y][11] < sh[y][10]]
    assert len(nov_lower) == 5 and 2020 not in nov_lower, "odstavek o novembru zapisan za 5 od 6 let (izjema 2020)"
    sep_lo, sep_hi = min(sh[y][9] for y in YEARS), max(sh[y][9] for y in YEARS)
    oct_lo, oct_hi = min(sh[y][10] for y in YEARS), max(sh[y][10] for y in YEARS)
    assert (sep_lo, sep_hi, oct_lo, oct_hi) == (10, 32, 25, 44)
    sp = [datetime.date.fromisoformat(B[str(y)]["teden_z_najvecjim_delezem"]["zacetek"]) for y in YEARS]
    md = [d.replace(year=2000) for d in sp]
    assert min(md) == datetime.date(2000, 9, 30) and max(md) + datetime.timedelta(6) == datetime.date(2000, 11, 3), \
        "razpon vrha po deležu (30. 9.–3. 11.) ne drži več"
    tr = json.load(open(TREND, encoding="utf-8"))["years"]
    idx = {y: (tr[str(y)]["monthly_avg"]["09"], tr[str(y)]["monthly_avg"]["10"]) for y in (2022, 2023, 2024, 2025)}
    higher = [y for y, (s, o) in idx.items() if o > s]
    assert higher == [2023, 2024, 2025]

    # --- podatki za grafe ---
    weeks = {y: by_year[y] for y in YEARS + [LAST]}
    share_series, count_series = [], []
    for y in YEARS + [LAST]:
        hl = y == LAST
        sp, cp = [], []
        for d, v in weeks[y]:
            if d.month > 11 or (d.month == 7 and False):
                continue
            off = off_of(d) + 3.5
            lab = week_label(d)
            ok = v["vse"] >= MIN_ALL
            sp.append((off, share(v) if ok else None,
                       f"{y}, {lab}: {num(share(v))}{NBSP}% ({v['basidio']} od {v['vse']} opažanj)"))
            cp.append((off, v["basidio"], f"{y}, {lab}: {opaz(v['basidio'])} gob"))
        style = dict(name=str(y) if hl else f"{y}", color=GREEN if hl else GREY, width=2.6 if hl else 1.5, hl=hl)
        share_series.append({**style, "pts": sp})
        count_series.append({**style, "pts": cp})
    # prejšnja leta spodaj, letos zadnje (na vrhu)
    share_ch = season_line_chart(share_series, 60, (0, 15, 30, 45, 60), lambda t: f"{int(t)}{NBSP}%",
                                 "Delež gob med vsemi opažanji iNaturalista v Sloveniji po tednih, julij–november, 2020–2026")
    count_ch = season_line_chart(count_series, 450, (0, 150, 300, 450), lambda t: str(int(t)),
                                 "Število opažanj gob v Sloveniji po tednih, julij–november, 2020–2026")
    rows_dots = []
    for y in YEARS:
        n_start = peak_start[y]
        s_start = datetime.date.fromisoformat(B[str(y)]["teden_z_najvecjim_delezem"]["zacetek"])
        rows_dots.append((y, off_of(n_start) + 3.5, B[str(y)]["teden_z_najvec"]["stevilo"], off_of(s_start) + 3.5,
                          f"{y}: največ opažanj {week_label(n_start)} ({B[str(y)]['teden_z_najvec']['stevilo']})",
                          f"{y}: največji delež {week_label(s_start)} ({B[str(y)]['teden_z_najvecjim_delezem']['delez']}{NBSP}%)"))
    dot_ch = peak_dot_chart(rows_dots)
    months = [(7, "jul"), (8, "avg"), (9, "sep"), (10, "okt"), (11, "nov")]
    mitems = []
    for m, lab in months:
        vals = [sh[y][m] for y in YEARS]
        mitems.append((lab, st.median(vals), min(vals), max(vals),
                       f"{lab}: mediana {num(st.median(vals), 0)}{NBSP}%, od {min(vals)}{NBSP}% do {max(vals)}{NBSP}% (2020–2025)"))
    month_ch = month_range_chart(mitems)
    mnames = {"jul": "julij", "avg": "avgust", "sep": "september", "okt": "oktober", "nov": "november"}
    tbl_m = table(["Mesec", "Mediana", "Najmanj", "Največ"],
                  [(mnames[l], pct(med), pct(lo), pct(hi)) for l, med, lo, hi, _ in mitems], None,
                  "Delež gob po mesecih", "Delež gob med vsemi opažanji v mesecu, 2020–2025: mediana in razpon šestih let.")

    leg_line = legend([("2020–2025, vsako leto ena črta", "line", GREY), (str(LAST) + " (do 13. 10.)", "line", GREEN),
                       ("7.–27. oktober", "band", AMBER)])

    fig_dots = fig("Teden z največ opaženimi gobami",
                   legend([("največ opažanj v tednu", "dot", GREEN), ("največji delež med vsemi opažanji", "ring", GREY),
                           ("7.–27. oktober", "band", AMBER)]) + dot_ch,
                   "Vsak teden traja sedem dni; piko vrišem na sredino tedna. Desno je število opažanj gob v tem tednu. "
                   "Obroč pokaže teden z največjim deležem gob, če je bilo v tednu vsaj 150 vseh opažanj. Vir: iNaturalist.")
    fig_share = fig("Delež gob med vsemi opažanji v Sloveniji, po tednih", leg_line + share_ch,
                    "Vsak teden je ena točka. Teden z manj kot 150 vsemi opažanji je izpuščen, ker bi bil delež preveč naključen. "
                    "Zadnji teden letošnje črte je podcenjen, ker opazovalci opažanja nalagajo z zamudo. Vir: iNaturalist.")
    fig_month = fig("Delež gob med vsemi opažanji po mesecih (2020–2025)", month_ch,
                    "Stolpec je mediana šestih let, navpična črta pa razpon od najmanjše do največje vrednosti. "
                    "Višina pomeni delež vseh opažanj v tistem mesecu, ki so gobe. Vir: iNaturalist.")
    fig_count = fig("Število opažanj gob po tednih", leg_line + count_ch,
                    "Absolutna števila med leti niso primerljiva, ker je opazovalcev vsako leto več. Primerljiv je čas vrha, "
                    "ne višina. Vir: iNaturalist.")

    # --- tabele ---
    rows1 = []
    for y in YEARS + [LAST]:
        ps = datetime.date.fromisoformat(B[str(y)]["teden_z_najvec"]["zacetek"])
        s = {int(m): v for m, v in B[str(y)]["delez_po_mesecih"].items()}
        rows1.append((str(y), week_label(ps) if y != LAST else f"{week_label(ps)} (do zdaj)", str(B[str(y)]["teden_z_najvec"]["stevilo"]),
                      pct(s.get(9, float("nan"))) if 9 in s else "–", pct(s[10]) if 10 in s else "–",
                      pct(s[11]) if 11 in s else "–"))
    tbl1 = table(["Leto", "Teden z največ opažanji", "Število", "Delež, september", "oktober", "november"], rows1, str(LAST),
                 "Vrh po letih",
                 "Za leto 2026 so oktober in november še nepopolna (podatki do 13. 10.), vrh pa je za zdaj 30. 9.–6. 10.")
    rows2 = []
    for y in YEARS:
        ps = B[str(y)]["teden_z_najvec"]["zacetek"]
        rows2.append((str(y), week_label(datetime.date.fromisoformat(ps)),
                      str(B[str(y)]["teden_z_najvec"]["stevilo"]), str(A[str(y)]["teden_z_najvec"]["stevilo"]),
                      str(F[str(y)]["teden_z_najvec"]["stevilo"])))
    tbl2 = table(["Leto", "Teden z največ opažanji (isti v vseh treh skupinah)", "Prave gobe", "Klobučnice", "Vse glive"], rows2, None,
                 "Tri skupine", "Število opažanj v tednu vrha po skupinah.")

    summer = {}
    for y in YEARS:
        cand = [(d, v["basidio"]) for d, v in weeks[y] if d < datetime.date(y, 9, 1)]
        summer[y] = max(cand, key=lambda x: x[1])
    y23 = summer[2023]
    peak23 = B["2023"]["teden_z_najvec"]["stevilo"]
    assert y23[0] == datetime.date(2023, 7, 29) and y23[1] == 371 and peak23 == 413, "opomba o poletnem valu 2023 ne drži več"
    others = [y for y in YEARS if y != 2023]
    assert all(summer[y][1] < 0.65 * B[str(y)]["teden_z_najvec"]["stevilo"] for y in others)
    w26 = {d.isoformat(): v for d, v in weeks[LAST]}
    c26 = [w26[k] for k in ("2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07")]
    nums26 = [v["basidio"] for v in c26]
    sep26 = int(B[str(LAST)]["delez_po_mesecih"]["9"])
    assert 10 <= sep26 <= 32

    # --- besedilo ---
    lead = "</p>\n<p class=\"lead\">".join([
        f"Kratek odgovor: po fotografijah gob v Sloveniji je vrh oktobra, ne septembra. V vsakem od šestih let, 2020–2025, je teden "
        f"z največ opaženimi gobami padel med 7. in 27. oktobrom. Oktobra so bile gobe {oct_lo}–{oct_hi} {NBSP}% vseh opažanj na iNaturalistu "
        f"v Sloveniji, septembra {sep_lo}–{sep_hi} {NBSP}%.".replace(f" {NBSP}%", f"{NBSP}%"),
        "Poznate občutek, da je gobarske sezone konec, ko mine septembrski vrh? Podatki iz šestih let tega ne podpirajo."])
    p1 = [
        "iNaturalist je spletna zbirka opažanj narave, v katero uporabniki nalagajo fotografije rastlin, živali in gliv. "
        "Vrste določajo opazovalci in skupnost.",
        "Za vsak teden od julija do novembra sem prešteval, koliko opažanj v Sloveniji je pravih gob in koliko je vseh opažanj "
        "(rastline, žuželke, ptice …). Prave gobe so tu deblo <em>Basidiomycota</em>: klobučnice (jurčki, lisičke, mušnice …), "
        "pa tudi trdoživke na lesu, želatinaste glive in rje. Ne vsebuje zaprtotrosnic (smrčki, tartufi) in plesni, lišajev pa skoraj nič. "
        "Preštel sem samo skupna števila, posameznih opažanj nisem bral. Teden se začne 1. julija in teče po sedem dni.",
        "Absolutna števila med leti niso primerljiva: opazovalcev je vsako leto več. Zato gledam <strong>kdaj</strong> je vrh in "
        "<strong>kolikšen delež</strong> vseh opažanj so gobe.",
    ]
    p2 = [
        "V vseh šestih letih je teden z največ opaženimi gobami padel med 7. in 27. oktobrom:",
        fig_dots,
        "Tudi če namesto števila gledam teden z največjim deležem gob, pade vrh med 30. septembrom in 3. novembrom. "
        "Pri klobučnicah in pri celotnem kraljestvu gliv je teden z največ opažanji isti (glej razdelek 05).",
        tbl1,
        "Poteki po tednih kažejo isto zgodbo. Delež gob je julija majhen, septembra začne rasti, oktobra doseže vrh:",
        fig_share,
    ]
    p3 = [
        f"Oktober je v vseh šestih letih višji od septembra. Gobe so bile oktobra {oct_lo}–{oct_hi}{NBSP}% vseh opažanj, "
        f"septembra {sep_lo}–{sep_hi}{NBSP}%. Novembra delež v petih od šestih let spet pade (izjema je 2020).",
        fig_month,
        tbl_m,
        "To ni v nasprotju z našim gobarskim modelom, a ni isto. Gobarski indeks za Rečico ob Savinji je bil v oktobru višji kot v septembru "
        f"v treh od štirih celih let ({'; '.join(f'{y}: {num(idx[y][1])} proti {num(idx[y][0])}' for y in (2023, 2024, 2025))}). "
        f"Leta 2022 je bilo obratno ({num(idx[2022][1])} proti {num(idx[2022][0])}). Indeks je modelska ocena in zajema tudi "
        "celoletne vrste, zato ni dokaz.",
    ]
    p4 = [
        "Delež ima svojo past: novembra upade opazovanje žuželk in rastlin, zato se delež gob poveča, tudi če jih ni več. Zato sem "
        "pogledal tudi absolutno število opažanj. Tudi tam je vrh oktobra:",
        fig_count,
    ]
    p5 = [
        "Kaj pa, če za gobe vzamem le klobučnice (<em>Agaricomycetes</em>), ali če vzamem vse glive? Teden z največ opažanji je v "
        "vseh treh skupinah v vsakem od šestih let isti, števila pa se razlikujejo za nekaj odstotkov:",
        tbl2,
        "Razlika pri vrhu po deležu je samo ena: leta 2024 pade pri pravih gobah na 14. oktober, pri klobučnicah in pri kraljestvu "
        "gliv pa na 4. november.",
    ]
    p6 = [
        f"Letos so bila do 13. oktobra v posameznih tednih opažanja gob: {nums26[0]} (9. septembra), {nums26[1]} (16. septembra), "
        f"{nums26[2]} (23. septembra), {nums26[3]} (30. septembra) in {nums26[4]} (7.–13. oktobra). Delež gob je septembra "
        f"znašal {sep26}{NBSP}%, kar je v običajnem razponu ({sep_lo}–{sep_hi}{NBSP}%).",
        "Zadnja številka je še podcenjena, ker opazovalci opažanja nalagajo z zamudo. Ali bo letos vrh oktobra, še ne vemo. "
        "V prejšnjih letih je padel prav v tedne od 7. do 27. oktobra.",
    ]
    p7 = [
        "<ul>"
        "<li><strong>To so fotografije, ne košare.</strong> Opažanje gobe ni nabirka in ne pove, ali je goba užitna. Vključene so "
        "tudi nejestne vrste in trdoživke na lesu.</li>"
        "<li><strong>Šest let je malo.</strong> Šest od šestih je zanimivo, ni pa zakon.</li>"
        f"<li><strong>Oktober ni edini vrh.</strong> Leta 2023 je bil že teden od 29. julija do 4. avgusta (<strong>{y23[1]}</strong> opažanj) skoraj tako "
        f"visok kot oktobrski vrh ({peak23}). V drugih letih je bil poletni vrh najmanj tretjino nižji od oktobrskega. "
        "Razloga iz teh podatkov ne morem ugotoviti.</li>"
        "<li><strong>To je Slovenija kot celota.</strong> Rečica in višje lege imajo lahko drugačen vrh.</li>"
        "<li><strong>Opazovalci niso nabiralci.</strong> Gobe fotografira drugačna skupina ljudi, kot jih nabira. Pomembno je tudi, "
        "kdaj imajo ljudje čas in kakšno je vreme.</li>"
        "<li><strong>Opažanja se nalagajo z zamudo.</strong> Zadnji teden je zato vedno podcenjen.</li>"
        "<li><strong>O dežju ne trdim ničesar.</strong> Povezave med dežjem in deležem gob v tem članku ne obravnavam. "
        "To bi zahtevalo ločeno analizo.</li>"
        "</ul>",
        "<p style=\"margin-top:1rem\">V članku so uporabljeni samo združeni podatki. Posameznih opažanj ne objavljam, ker zanje veljajo "
        "različni licenčni pogoji. Zbrane številke so v "
        '<a href="/data/inat-glive-po-tednih.json" style="color:var(--blue)">data/inat-glive-po-tednih.json</a>.</p>',
    ]
    p8 = [
        "Podatki ne povedo, kje je goba, ampak kdaj jih ljudje v Sloveniji najpogosteje fotografirajo. Prva praktična posledica je "
        "preprosta: ne odpišite oktobra. Poglejte "
        f'<a href="{SITE}/gobarska-napoved/danes/" style="color:var(--blue)">gobarsko napoved za danes</a> in '
        f'<a href="{SITE}/gobarska-napoved/valovi/" style="color:var(--blue)">kalkulator rasti po dežju</a>, ki upošteva, kdaj je deževalo.',
        "Gobe nabirajte samo, če jih zanesljivo poznate. Dvojnice in strupene vrste so na strani "
        f'<a href="{SITE}/gobarska-napoved/strupene-gobe/" style="color:var(--blue)">strupene gobe</a>.',
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine.</strong> Besedilo, grafe in podatke lahko povzamete le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov '
        'prosim vprašajte vnaprej.</p>',
    ]
    title = "Vrh gobarske sezone je oktobra. Šest let podatkov"
    assert len(title) <= 60
    desc = ("V vsakem od šestih let (2020–2025) je bil teden z največ opaženimi gobami v Sloveniji med 7. in 27. oktobrom, "
            "ne septembra. Podatki iNaturalista.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — podatki", "heading": "Kaj sem prešteval", "id": "podatki", "paragraphs": p1},
        {"label": "02 — vrh", "heading": "Kdaj je vrh?", "id": "vrh", "paragraphs": p2},
        {"label": "03 — meseci", "heading": "Oktober je višji od septembra", "id": "meseci", "paragraphs": p3},
        {"label": "04 — število", "heading": "Tudi število opažanj vrhuni oktobra", "id": "stevilo", "paragraphs": p4},
        {"label": "05 — skupine", "heading": "Prave gobe, klobučnice ali vse glive?", "id": "skupine", "paragraphs": p5},
        {"label": "06 — letos", "heading": "Kaj kaže letošnja jesen", "id": "letos", "paragraphs": p6},
        {"label": "07 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": p7},
        {"label": "08 — nabiranje", "heading": "Kaj to pomeni za nabiranje", "id": "nabiranje", "paragraphs": p8},
    ]
    gen = D["_meta"]["generirano"]
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "iNaturalist", "oktober", "sezona", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "gobe-lastna", "og_accent_hex": "#34d399",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": (f"Viri: iNaturalist (API, število opažanj po tednih v Sloveniji, deblo Basidiomycota, razred Agaricomycetes in "
                         f"kraljestvo Fungi; stanje {int(gen[8:10])}. {int(gen[5:7])}. {gen[:4]}), gobarski model Meteorec "
                         "(mesečno povprečje indeksa za Rečico ob Savinji). Podatki: /data/inat-glive-po-tednih.json."),
    }


def plain_text(article):
    """Čisto besedilo za lekturo (brez SVG; tabele kot vrstice)."""
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
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    D, by_year = load()
    article = build_article(D, by_year)
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
        og_title="Vrh gobarske\nsezone", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
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
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
