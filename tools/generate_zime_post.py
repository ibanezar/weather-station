#!/usr/bin/env python3
"""
tools/generate_zime_post.py — »So zime še kar so bile? Podatki in spomin« (12. 10. 2026).

Ročno pognan članek po vprašanju: so bile zime v letih 1980–2002 res bolj zimske in kaj to pomeni za
današnje otroke. Vse številke v besedilu, tabelah in grafih pridejo iz data/zime.json
(tools/study_zime.py); besedilo ničesar ne izmišlja (docs/slog-pisanja.md). Članek je posnetek na dan
objave. Lektura (lektura.yml) je od 2. 10. 2026 izklopljena — pregled po slogovnem vodniku.

Usage: python3 tools/generate_zime_post.py [--wire] [--dry-run] [--force]
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
DATA = os.path.join(ROOT, "data", "zime.json")
SLUG = "zime-nekoc-in-zdaj-1012"
CYAN, PURPLE = "#22d3ee", "#a78bfa"       # starejše zime (do 2003), novejše
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"


def num(x, d=1):
    x = round(x, d) + 0.0                 # brez »–0,0«
    return f"{x:.{d}f}".replace(".", ",").replace("-", "–")


def dni(x):
    """število + oblika »dan« (cela: 1 dan, 2 dneva, 3–4 dni, 5+ dni; necela: rodilnik ednine)."""
    if abs(x - round(x)) > 1e-9:
        return f"{num(x)} dneva"
    n = int(round(x))
    w = "dan" if n % 100 == 1 else "dneva" if n % 100 == 2 else "dni"
    return f"{n} {w}"


_W = ["nič", "ena", "dve", "tri", "štiri", "pet", "šest", "sedem", "osem", "devet", "deset"]


def ledeni(n):
    """število + oblika »ledeni dan« (1 ledeni dan, 2 ledena dneva, 3–4 ledeni dnevi, 5+ ledenih dni)."""
    n = int(n)
    r = n % 100
    w = "ledeni dan" if r == 1 else "ledena dneva" if r == 2 else "ledeni dnevi" if r in (3, 4) else "ledenih dni"
    return f"{n} {w}"


def numw(n):
    return _W[n] if 0 <= n <= 10 else str(n)


_GEN = ["nič", "enega", "dveh", "treh", "štirih", "petih", "šestih", "sedmih", "osmih", "devetih", "desetih"]


def numg(n):
    """števnik z besedo v rodilniku/mestniku do 10 (od enega do šestih, v sedmih), sicer številka."""
    return _GEN[n] if 0 <= n <= 10 else str(n)


def zs(x):
    """predlog z/s pred številom, kot se prebere (s 17, z 21,1, z –1,1)."""
    if x < 0:
        return "z"
    n = int(abs(x))
    for lim, first in ((100, "s"), (90, "z"), (80, "z"), (30, "s"), (20, "z")):
        if n >= lim:
            return first
    return "s" if n in (3, 4, 5, 6, 7, 13, 14, 15, 16, 17) else "z"


def mean(vals):
    vals = list(vals)
    return st.mean(vals) if vals else 0.0


SRC = {
    "ghcn": "https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily",
    "pauly": "https://doi.org/10.1016/S0169-5347(00)89171-5",
    "rosy": "https://doi.org/10.1006/jesp.1997.1333",
    "crnivec": "https://crnivec.si/",
}


def a(key, text):
    return f'<a href="{SRC[key]}" style="color:var(--blue)" rel="noopener">{text}</a>'


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def bars(items, aria, w=360, h=230, labels=True, every=1, top=None):
    """items = [(oznaka, vrednost, barva, opis za miško)]."""
    pl, pr, pt, pb = 34, 8, 20, 26
    iw, ih = w - pl - pr, h - pt - pb
    top = top or max(4, int(max(v for _, v, _, _ in items) * 1.15 / 4 + 1) * 4)
    slot = iw / len(items)
    bw = min(34, slot * 0.7)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{aria}" xmlns="http://www.w3.org/2000/svg">']
    for i in range(5):
        y = pt + ih - ih * i / 4
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        p.append(f'<text x="{pl - 6}" y="{y + 3.5:.1f}" text-anchor="end" font-size="10" fill="{MUTED}">{int(round(top * i / 4))}</text>')
    for i, (lab, v, col, tip) in enumerate(items):
        cx = pl + slot * (i + 0.5)
        bh = ih * v / top
        x0, y0 = cx - bw / 2, pt + ih - bh
        if bh > 0.5:
            r = min(3, bh)
            p.append(f'<path d="M{x0:.1f},{pt + ih:.1f} V{y0 + r:.1f} Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f} '
                     f'H{x0 + bw - r:.1f} Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + r:.1f} V{pt + ih:.1f} Z" '
                     f'fill="{col}"><title>{tip}</title></path>')
        if labels:
            p.append(f'<text x="{cx:.1f}" y="{y0 - 5:.1f}" text-anchor="middle" font-size="10.5" font-weight="600" fill="{INK}">{num(v) if v % 1 else int(v)}</text>')
        if i % every == 0:
            p.append(f'<text x="{cx:.1f}" y="{h - 8}" text-anchor="middle" font-size="10" fill="{MUTED}">{lab}</text>')
    p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{pt + ih}" y2="{pt + ih}" stroke="{MUTED}" stroke-opacity=".5"/>')
    p.append("</svg>")
    return "".join(p)


def bars_signed(items, aria, w=520, h=240, every=1, step=1.0):
    """Stolpci okoli ničle (temperature). items = [(oznaka, vrednost, barva, opis)]."""
    pl, pr, pt, pb = 36, 8, 18, 26
    iw, ih = w - pl - pr, h - pt - pb
    lo = min(0.0, min(v for _, v, _, _ in items))
    hi = max(0.0, max(v for _, v, _, _ in items))
    lo, hi = step * int(lo / step - (lo % step > 0)), step * (int(hi / step) + 1)
    y_of = lambda v: pt + ih * (hi - v) / (hi - lo)
    slot = iw / len(items)
    bw = min(30, slot * 0.7)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{aria}" xmlns="http://www.w3.org/2000/svg">']
    t = lo
    while t <= hi + 1e-9:
        y = y_of(t)
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        p.append(f'<text x="{pl - 6}" y="{y + 3.5:.1f}" text-anchor="end" font-size="10" fill="{MUTED}">{num(t, 0)}</text>')
        t += step
    for i, (lab, v, col, tip) in enumerate(items):
        cx = pl + slot * (i + 0.5)
        y0, y1 = sorted((y_of(0), y_of(v)))
        if y1 - y0 > 0.5:
            p.append(f'<rect x="{cx - bw / 2:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{y1 - y0:.1f}" rx="2" fill="{col}"><title>{tip}</title></rect>')
        ty = y_of(v) - 5 if v >= 0 else y_of(v) + 12
        p.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="10" font-weight="600" fill="{INK}">{num(v)}</text>')
        if i % every == 0:
            p.append(f'<text x="{cx:.1f}" y="{h - 8}" text-anchor="middle" font-size="10" fill="{MUTED}">{lab}</text>')
    p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y_of(0):.1f}" y2="{y_of(0):.1f}" stroke="{MUTED}" stroke-opacity=".6"/>')
    p.append("</svg>")
    return "".join(p)


def legend(entries):
    return '<p class="zm-leg">' + " ".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in entries) + "</p>"


STYLE = """<style>
.zm-fig{margin:1.4rem 0;padding:1rem 1rem .8rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px}
.zm-fig figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.6rem}
.zm-fig h3{font-family:'Space Grotesk',sans-serif;font-size:.95rem;margin:0 0 .4rem;color:var(--text)}
.zm-fig svg{display:block;width:100%;height:auto}
.zm-row{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:640px){.zm-row{grid-template-columns:1fr}}
.zm-leg{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-size:.85rem;color:var(--muted);margin:.2rem 0 .6rem}
.zm-leg i{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;margin-right:.4rem;vertical-align:-.1rem}
.zm-tbl{overflow-x:auto;max-width:100%;margin:1rem 0}
.zm-tbl table{border-collapse:collapse;width:100%;font-size:.86rem}
.zm-tbl th,.zm-tbl td{padding:.42rem .5rem;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
.zm-tbl th:first-child,.zm-tbl td:first-child{text-align:left}
.zm-tbl thead th{color:var(--muted);font-weight:600;font-size:.76rem;vertical-align:bottom;line-height:1.3}
.post-body h3{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;margin:1.6rem 0 .4rem}
.zm-note{color:var(--muted);font-size:.82rem;line-height:1.5;margin:-.4rem 0 1.2rem}
</style>"""


def fig(title, inner, caption):
    return f'<figure class="zm-fig"><h3>{title}</h3>{inner}<figcaption>{caption}</figcaption></figure>'


def table(head, rows, cap, note=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="zm-tbl" tabindex="0" role="region" aria-label="{cap}"><table><thead><tr>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>' + (f'<p class="zm-note">{note}</p>' if note else ""))


# ───────────────────────── članek ─────────────────────────

PERIODS = [("1961–1980", 1961, 1980), ("1981–2002", 1981, 2002), ("2003–2012", 2003, 2012), ("2013–2022", 2013, 2022)]


def period_stats(W, lo, hi):
    ys = [y for y in W if lo <= y <= hi]
    return {k: mean(W[y][k] for y in ys) for k in ("tmean", "frost", "ice", "hard")} | {"n": len(ys)}


def build_article(D):
    LJ = {int(y): v for y, v in D["stations"]["ljubljana"]["winters"].items()}
    SM = {int(y): v for y, v in D["stations"]["smartno"]["winters"].items()}
    SN = {int(y): v for y, v in D["snow_ljubljana"].items()}
    OWN = {int(y): v for y, v in D["own"].items()}
    lj = {p: period_stats(LJ, lo, hi) for p, lo, hi in PERIODS}
    sm = {p: period_stats(SM, lo, hi) for p, lo, hi in PERIODS}
    old_p, new_p = "1981–2002", "2013–2022"
    assert lj[old_p]["ice"] > lj[new_p]["ice"] and sm[old_p]["ice"] > sm[new_p]["ice"], "trditev o ledenih dneh ne drži"

    SNOW_OLD = "1996/97–2003/04"         # zapisi se začnejo 1. 1. 1996; 1995/96 je okrnjena (snow_ljubljana_partial)
    s_old = [SN[y] for y in range(1996, 2004) if y in SN]
    P95, SP = next((int(y), v) for y, v in D["snow_ljubljana_partial"].items())
    s_mid = [SN[y] for y in range(2005, 2015) if y in SN]
    s_new = [SN[y] for y in range(2015, 2025) if y in SN]
    d_old, d_new = mean(s["days"] for s in s_old), mean(s["days"] for s in s_new)
    d_mid = mean(s["days"] for s in s_mid)
    long60_old = sum(s["days"] >= 60 for s in s_old)
    long60_new = sum(s["days"] >= 60 for s in s_new)
    short_old = sum(s["days"] <= 20 for s in s_old)
    short_new = sum(s["days"] <= 20 for s in s_new)
    kid_years = [SN[y]["days"] for y in range(2018, 2025) if y in SN]
    gap_old = sorted((y, SN[y]["days"]) for y in range(1996, 2004) if SN[y]["days"] <= 20)
    assert min(SN) == 1996 and 1995 not in SN and SP["longest"] > max(s["longest"] for s in SN.values())
    assert d_old > d_new and long60_new == 0 and len(gap_old) == 2 and gap_old[0][1] == gap_old[1][1]

    # --- grafi ---
    def ice_items(P):
        return [(p.replace("–", "–"), P[p]["ice"], CYAN if i < 2 else PURPLE,
                 f"{p}: povprečno {dni(P[p]['ice'])} z najvišjo temperaturo pod 0 °C") for i, p in enumerate(P)]
    ch_lj = bars(ice_items(lj), "Ledeni dnevi v zimi (dec.–feb.), Ljubljana Bežigrad, po obdobjih", every=1)
    ch_sm = bars(ice_items(sm), "Ledeni dnevi v zimi (dec.–feb.), Šmartno pri Slovenj Gradcu, po obdobjih", every=1)
    snow_items = [(str(y)[2:], SN[y]["days"], CYAN if y <= 2003 else PURPLE,
                   f"zima {y}/{str(y + 1)[2:]}: {dni(SN[y]['days'])} snežne odeje, najdaljše strnjeno obdobje {dni(SN[y]['longest'])}")
                  for y in sorted(SN)]
    ch_snow = bars(snow_items, "Dnevi s snežno odejo od novembra do marca, Ljubljana Bežigrad, po zimah", w=700, h=250,
                   labels=False, every=2)

    fig1 = fig("Ledeni dnevi v zimi (december–februar): koliko dni se temperatura ves dan ni dvignila nad 0 °C?",
               f'<div class="zm-row"><div><p class="zm-note" style="margin:0 0 .3rem">Ljubljana Bežigrad (299 m)</p>{ch_lj}</div>'
               f'<div><p class="zm-note" style="margin:0 0 .3rem">Šmartno pri Slovenj Gradcu (444 m)</p>{ch_sm}</div></div>'
               + legend([("1961–2002", CYAN), ("po letu 2002", PURPLE)]),
               "Povprečno število ledenih dni na zimo po obdobjih. Ledeni dan je dan, ko je najvišja dnevna temperatura pod 0 °C. "
               "Vir: GHCN-Daily (ARSO). Zima 2022/23 je zadnja v podatkovnem nizu.")
    fig2 = fig("Dnevi s snežno odejo od novembra do marca v Ljubljani po posameznih zimah",
               ch_snow + legend([(SNOW_OLD, CYAN), ("2005/06–2024/25", PURPLE)]),
               "Oznaka pomeni leto, v katerem se zima začne; oznaka 96 tako predstavlja zimo 1996/97. Zime 2004/05 v podatkih ni, "
               "zima 1995/96 pa ni prikazana, ker se zapisi začnejo šele 1. januarja 1996. Vir: GHCN-Daily (ARSO), višina snežne odeje.")

    # --- tabele ---
    t1 = table(["Obdobje (zime)", "Povprečna temperatura dec.–feb.", "Dnevi z zmrzaljo", "Ledeni dnevi", "Dnevi pod –10 °C"],
               [[f"{p} (Ljubljana)", f"{num(lj[p]['tmean'])} °C", num(lj[p]["frost"]), num(lj[p]["ice"]), num(lj[p]["hard"])]
                for p in lj]
               + [[f"{p} (Šmartno)", f"{num(sm[p]['tmean'])} °C", num(sm[p]["frost"]), num(sm[p]["ice"]), num(sm[p]["hard"])]
                  for p in sm],
               "Zimski kazalniki po obdobjih za Ljubljano in Šmartno pri Slovenj Gradcu",
               "Povprečja na zimo. Dan z zmrzaljo: najnižja temperatura pod 0 °C; ledeni dan: najvišja temperatura pod 0 °C; dan pod "
               "–10 °C: najnižja temperatura –10 °C ali manj. Zima zajema obdobje december–februar in nosi letnico decembra (obdobje "
               "1981–2002 so zime od 1981/82 do 2002/03). Upoštevane so zime, za katere je na voljo vsaj 95 % meritev obeh "
               "temperaturnih vrednosti.")
    t2 = table(["Obdobje", "Zim", "Dni s snežno odejo (nov.–mar.)", "Najdaljše strnjeno obdobje", "Zim z vsaj 60 dnevi", "Zim z največ 20 dnevi"],
               [[lbl, str(len(g)), num(mean(s["days"] for s in g), 0), num(mean(s["longest"] for s in g), 0), str(sum(s["days"] >= 60 for s in g)),
                 str(sum(s["days"] <= 20 for s in g))]
                for lbl, g in ((SNOW_OLD, s_old), ("2005/06–2014/15", s_mid), ("2015/16–2024/25", s_new))],
               "Snežna odeja v Ljubljani po obdobjih zim",
               "Povprečja na zimo. Podatki o snežni odeji so za Ljubljano, ne za Zgornjo Savinjsko dolino.")
    ov = [y for y in (2019, 2020, 2021, 2022) if y in OWN and y in LJ and y in SM]
    t3 = table(["Zima", "Rečica ob Savinji (IREICA1)", "Ljubljana", "Šmartno"],
               [[f"{y}/{str(y + 1)[2:]}",
                 f"{num(OWN[y]['tmean'])} °C · {ledeni(OWN[y]['ice'])}",
                 f"{num(LJ[y]['tmean'])} °C · {ledeni(LJ[y]['ice'])}",
                 f"{num(SM[y]['tmean'])} °C · {ledeni(SM[y]['ice'])}"] for y in ov],
               "Primerjava zim 2019/20 do 2022/23: Rečica, Ljubljana in Šmartno",
               "Povprečna temperatura je izračunana iz dnevnih najvišjih in najnižjih temperatur za obdobje od decembra do februarja.")
    # --- sto let v Ljubljani ---
    decades = []
    for d0 in range(1900, 2030, 10):
        ys = [y for y in LJ if d0 <= y < d0 + 10]
        if ys:
            decades.append((d0, mean(LJ[y]["tmean"] for y in ys), len(ys)))
    dec = {d0: t for d0, t, _ in decades}
    early = [t for d0, t, _ in decades if d0 < 1970]
    assert max(early) < 0.6 and min(early) > -0.6 and dec[1980] < dec[1970] and dec[1980] < dec[1990]
    assert all(t > 1 for d0, t, _ in decades if d0 >= 1990) and dec[1980] < 1
    missing = [y for y in range(1901, 2023) if y not in LJ]
    by_t = sorted(LJ, key=lambda y: LJ[y]["tmean"])
    cold3 = by_t[:3]
    warmest = by_t[-1]
    warm_next = [y for y in by_t[::-1][1:] if LJ[y]["tmean"] >= LJ[by_t[-2]]["tmean"] - 0.05]
    assert len(warm_next) >= 2
    wl = lambda y: f"{y}/{str(y + 1)[2:]}"
    coldest_mine = min((y for y in LJ if 1981 <= y <= 2002), key=lambda y: LJ[y]["tmean"])
    last_d, last_t, last_n = decades[-1]
    ch_dec = bars_signed([(f"{d0}" if n == 10 else f"{d0}*", t, CYAN if d0 in (1980, 1990) else PURPLE,
                           f"{d0}–{d0 + 9}: povprečna zima {num(t)} °C ({n} zim)") for d0, t, n in decades],
                         "Povprečna temperatura zime (december–februar) v Ljubljani po desetletjih, od 1901", every=2)
    ice_w = [y for y in range(1951, 2023) if y in LJ]
    ch_icew = bars([(str(y), LJ[y]["ice"], CYAN if 1981 <= y <= 2002 else PURPLE,
                     f"zima {wl(y)}: {dni(LJ[y]['ice'])} ves dan pod 0 °C") for y in ice_w],
                   "Ledeni dnevi v Ljubljani po zimah, 1951/52–2022/23", w=700, h=240, labels=False, every=10, top=60)
    lj20_old = sum(LJ[y]["ice"] >= 20 for y in LJ if 1981 <= y <= 2002)
    lj20_new = [y for y in LJ if y >= 2013 and LJ[y]["ice"] >= 20]
    sm20_old = sum(SM[y]["ice"] >= 20 for y in SM if 1981 <= y <= 2002)
    sm20_new = sum(SM[y]["ice"] >= 20 for y in SM if y >= 2013)
    assert len(lj20_new) == 1 and sm20_new == 0
    lj80, lj90 = period_stats(LJ, 1981, 1990), period_stats(LJ, 1991, 2002)
    lj80_10 = lj80["tmean"]
    rolls = [(s0, mean(LJ[y]["tmean"] for y in range(s0, s0 + 10))) for s0 in range(1951, 2014)
             if all(y in LJ for y in range(s0, s0 + 10))]
    roll_start, roll_t = [r for r in rolls if r[1] < 1][-1]
    assert lj80_10 < 1 and all(t >= 1 for s0, t in rolls if s0 > roll_start)
    sm80, sm90 = period_stats(SM, 1981, 1990), period_stats(SM, 1991, 2002)
    fig_dec = fig("Povprečna zima v Ljubljani po desetletjih, 1901–2022",
                  ch_dec + legend([("osemdeseta in devetdeseta", CYAN), ("ostala desetletja", PURPLE)]),
                  f"Povprečna temperatura od decembra do februarja. Oznaka predstavlja prvo leto desetletja; oznaka 1980 tako zajema zime "
                  f"od 1980/81 do 1989/90. Z zvezdico je označeno desetletje z manj kot desetimi zimami v podatkih; zadnje obdobje "
                  f"vključuje le {numw(last_n)} zime. Vir: GHCN-Daily (ARSO).")
    fig_icew = fig("Ledeni dnevi v Ljubljani po zimah, 1951/52–2022/23",
                   ch_icew + legend([("zime 1981/82–2002/03", CYAN), ("druge zime", PURPLE)]),
                   "Število dni, ko se temperatura ves dan ni dvignila nad 0 °C, v obdobju od decembra do februarja. Oznaka pomeni leto, "
                   "v katerem se zima začne. Vir: GHCN-Daily (ARSO).")

    # --- odjuga ---
    def mild(P):
        return {p: mean(P[y]["mild"] for y in P if lo <= y <= hi) for p, lo, hi in PERIODS}

    def month(P, m):
        return {p: mean(P[y]["months"][m] for y in P if lo <= y <= hi) for p, lo, hi in PERIODS}
    lj_m, sm_m = mild(LJ), mild(SM)
    t_months = table(["Obdobje (zime)", "December", "Januar", "Februar", "Dni z vsaj 5 °C"],
                     [[f"{p} (Ljubljana)"] + [f"{num(month(LJ, m)[p])} °C" for m in ("12", "01", "02")] + [num(lj_m[p], 0)] for p, _, _ in PERIODS]
                     + [[f"{p} (Šmartno)"] + [f"{num(month(SM, m)[p])} °C" for m in ("12", "01", "02")] + [num(sm_m[p], 0)] for p, _, _ in PERIODS],
                     "Povprečne mesečne temperature in dnevi odjuge po obdobjih",
                     "Povprečna mesečna temperatura je izračunana iz dnevnih najvišjih in najnižjih temperatur. Število dni z vsaj 5 °C "
                     "pomeni povprečno število dni na zimo, ko je najvišja temperatura od decembra do februarja dosegla vsaj 5 °C.")
    lj_feb, sm_feb = month(LJ, "02"), month(SM, "02")
    lj_dec, lj_jan = month(LJ, "12"), month(LJ, "01")
    assert lj_feb[new_p] - lj_feb[old_p] > max(lj_dec[new_p] - lj_dec[old_p], lj_jan[new_p] - lj_jan[old_p])

    # --- Črnivec ---
    CR = {int(y): v for y, v in D["crnivec"].items()}
    t_crn = table(["Zima", "Dni s snežno odejo (nov.–mar.)", "Najdaljše strnjeno obdobje", "Največja odeja", "Novi sneg skupaj"],
                  [[wl(y), str(CR[y]["days"]), dni(CR[y]["longest"]), f"{int(CR[y]['max_cm'])} cm", f"{int(CR[y]['new_cm'])} cm"] for y in sorted(CR)],
                  "Snežna odeja na Črnivcu (ARSO, 848 m) po zimah",
                  "Vir: ARSO, arhiv meritev na padavinski postaji Črnivec (848 m). Postaja meri od leta 2021.")
    crn_max = max(CR, key=lambda y: CR[y]["days"])
    crn_run = max(CR, key=lambda y: CR[y]["longest"])
    assert max(CR[y]["days"] for y in CR) < 90 and crn_max == crn_run
    kid_runs = [SN[y]["longest"] for y in range(2018, 2025) if y in SN]
    own_frost = [OWN[y]["frost"] for y in sorted(OWN)]
    assert min(OWN) == 2019 and max(OWN) == 2025

    own_ice = [OWN[y]["ice"] for y in sorted(OWN)]
    own_t = [OWN[y]["tmean"] for y in sorted(OWN)]
    n_own = len(OWN)

    # --- besedilo (lektorirano 12. 10. 2026; številke ostajajo izračunane) ---
    lead = "</p>\n<p class=\"lead\">".join([
        f"Kratek odgovor: deloma drži. V Ljubljani je bilo v zimah {old_p} povprečno {num(lj[old_p]['ice'], 0)} ledenih dni, ko se temperatura "
        f"ves dan ni dvignila nad 0 °C. V zadnjih desetih zimah jih je bilo le še {numw(round(lj[new_p]['ice']))}. Snežna odeja je v Ljubljani "
        f"nekoč vztrajala povprečno {dni(round(d_old))} na zimo, danes pa le še {dni(round(d_new))}.",
        f"Toda spomin je pogosto lepši od povprečja. Tudi v zimah {SNOW_OLD} sta bili dve zimi z manj kot tremi tedni snežne odeje. "
        "Zime osemdesetih let (od 1980/81 do 1989/90) pa so bile zadnje desetletje, v katerem je bila povprečna zima v Ljubljani hladnejša od 1 °C.",
        "Spodaj so podatki od leta 1901 naprej, primerjava odjug po mesecih, podatki o snegu v Ljubljani in na Črnivcu, meritve iz Rečice "
        "ob Savinji, nekaj razlage o spominu ter predlogi, kako zimo približati otrokom, ki starih zim niso poznali.",
    ])
    p1 = [
        f"Začnimo z mrazom. Ledeni dan je dan, ko se temperatura ne dvigne nad 0 °C. V Ljubljani je bilo v zimah {old_p} povprečno "
        f"{num(lj[old_p]['ice'])} ledenega dne na zimo, v zadnjih desetih zimah ({new_p}) pa le še {num(lj[new_p]['ice'])}. "
        f"V Šmartnem pri Slovenj Gradcu, ki leži v hladnejši kotlini, je povprečje padlo {zs(sm[old_p]['ice'])} {num(sm[old_p]['ice'])} "
        f"na {num(sm[new_p]['ice'])} dneva.",
        f"Povprečna zimska temperatura, izračunana za obdobje od decembra do februarja, se je v Ljubljani zvišala {zs(lj[old_p]['tmean'])} "
        f"{num(lj[old_p]['tmean'])} °C na {num(lj[new_p]['tmean'])} °C, v Šmartnem pa {zs(sm[old_p]['tmean'])} {num(sm[old_p]['tmean'])} °C "
        f"na {num(sm[new_p]['tmean'])} °C. V obeh krajih je to približno 2 °C več.",
        fig1, t1,
        f"Dni z zmrzaljo, ko najnižja temperatura pade pod 0 °C, je sicer tudi manj, vendar je upad precej manjši. V Šmartnem je bilo nekoč "
        f"povprečno {num(sm[old_p]['frost'], 0)} takšnih dni na zimo, zdaj pa {num(sm[new_p]['frost'], 0)}. Noči so v kotlinah še vedno mrzle. "
        "Izginjajo predvsem dnevi, ko mraz ne popusti niti opoldne.",
        f"Zanimivo je, da obdobje 1981–2002 ni bilo enotno. Osemdeseta leta so bila opazno hladnejša od devetdesetih. V Ljubljani je bila "
        f"povprečna zimska temperatura v zimah od 1981/82 do 1990/91 {num(lj80['tmean'])} °C, v zimah od 1991/92 do 2002/03 pa "
        f"{num(lj90['tmean'])} °C. Število ledenih dni je bilo v teh obdobjih {num(lj80['ice'])} oziroma {num(lj90['ice'])} na zimo, "
        f"v Šmartnem pa {num(sm80['ice'])} oziroma {num(sm90['ice'])}.",
        "Kdor je otroštvo preživel v osemdesetih letih, je torej doživljal hladnejše zime kot nekdo, ki je odraščal v devetdesetih.",
    ]
    p_sto = [
        "Meteorološka postaja Ljubljana Bežigrad meri od leta 1901, zato lahko pogledamo precej dlje v preteklost.",
        f"V uporabljenem viru ni podatkov za zime {', '.join(wl(y) for y in missing[:-1])} in {wl(missing[-1])}. Vse druge razpoložljive "
        "zime so prikazane na grafu.",
        fig_dec,
        f"Do sedemdesetih let se povprečna zimska temperatura po desetletjih ni bistveno spreminjala. Gibala se je med {num(min(early))} in "
        f"{num(max(early))} °C. Zime osemdesetih let (od 1980/81 do 1989/90) s povprečjem {num(dec[1980])} °C so bile zadnje desetletje, "
        "v katerem je povprečna zimska temperatura ostala pod 1 °C.",
        f"To velja tudi, če desetletje štejemo drugače: zime od 1981/82 do 1990/91 so imele povprečno {num(lj80_10)} °C. Zadnjih deset "
        f"zaporednih zim s povprečjem pod 1 °C se je začelo z zimo {wl(roll_start)} in končalo z zimo {wl(roll_start + 9)} ({num(roll_t)} °C).",
        f"Nato so sledila devetdeseta leta s povprečjem {num(dec[1990])} °C, prvo desetletje novega tisočletja {zs(dec[2000])} "
        f"{num(dec[2000])} °C in obdobje 2010–2019 {zs(dec[2010])} {num(dec[2010])} °C. Zadnje obdobje ima le {numw(last_n)} zime, njihovo "
        f"povprečje pa je {num(last_t)} °C, zato ga ne moremo enakovredno primerjati z drugimi desetletji.",
        f"Najhladnejše zime v tem nizu so bile {wl(cold3[0])} ({num(LJ[cold3[0]]['tmean'])} °C), {wl(cold3[1])} "
        f"({num(LJ[cold3[1]]['tmean'])} °C) in {wl(cold3[2])} ({num(LJ[cold3[2]]['tmean'])} °C). Najtoplejša je bila zima {wl(warmest)} "
        f"s povprečjem {num(LJ[warmest]['tmean'])} °C. Sledijo zime {', '.join(wl(y) for y in warm_next[:-1])} in {wl(warm_next[-1])} "
        f"s približno {num(LJ[warm_next[0]]['tmean'])} °C.",
        f"Najhladnejša zima v obdobju 1981–2002 je bila {wl(coldest_mine)}. Povprečna temperatura je znašala "
        f"{num(LJ[coldest_mine]['tmean'])} °C, zabeležili pa so {LJ[coldest_mine]['ice']} ledenih dni.",
        fig_icew,
        f"Graf ledenih dni po posameznih zimah pokaže, kako različne so bile zime že nekoč. Od 22 zim v obdobju 1981–2002 jih je imelo "
        f"v Ljubljani {numw(lj20_old)} vsaj 20 ledenih dni. V zadnjih desetih obravnavanih zimah, od 2013 do 2022, je bila takšna le ena: "
        f"{wl(lj20_new[0])}.",
        f"V Šmartnem je bilo v starejšem obdobju takšnih zim {sm20_old}, v zadnjih desetih pa nobena.",
    ]
    p_odjuga = [
        "Sneg pade, nato pa pride odjuga. Takšen je pogosto občutek ob zadnjih zimah. Za odjugo sem v tej analizi štel dneve, ko najvišja "
        "dnevna temperatura doseže vsaj 5 °C.",
        f"V Ljubljani je bilo v zimah {old_p} povprečno {num(lj_m[old_p], 0)} takšnih dni na zimo, v obdobju {new_p} pa "
        f"{num(lj_m[new_p], 0)} od približno 90 zimskih dni. V Šmartnem se je povprečje povečalo {zs(sm_m[old_p])} {num(sm_m[old_p], 0)} "
        f"na {num(sm_m[new_p], 0)} dni.",
        t_months,
        f"Najizrazitejša sprememba je bila februarja. V Ljubljani je bila povprečna februarska temperatura v zimah {old_p} "
        f"{num(lj_feb[old_p])} °C, v obdobju {new_p} pa {num(lj_feb[new_p])} °C. V Šmartnem se je zvišala {zs(sm_feb[old_p])} "
        f"{num(sm_feb[old_p])} °C na {num(sm_feb[new_p])} °C.",
        "Desetletno obdobje je razmeroma kratko, zato je lahko del te razlike posledica nekaj zelo toplih februarjev. Smer spremembe pa je "
        "podobna tudi decembra in januarja.",
        "To je pomembno tudi za snežno odejo. V dolini se sneg pri temperaturah precej nad ničlo, zlasti ob dežju, navadno hitro tali. "
        "Več toplih dni pomeni, da tudi sneg, ki pade, pogosto ne zdrži dolgo.",
    ]
    p2 = [
        f"Sneg je zgodba zase, saj potrebuje dvoje: dovolj nizko temperaturo in padavine. Zapisi o snežni odeji v Ljubljani, ki jih imam "
        f"na voljo, se začnejo 1. januarja 1996. V zimah {SNOW_OLD} je snežna odeja od novembra do marca vztrajala povprečno "
        f"{dni(round(d_old))}, v zimah 2015/16–2024/25 pa le še {dni(round(d_new))}.",
        fig2, t2,
        f"Toda tudi nekoč niso bile vse zime zasnežene. Od {numg(len(s_old))} zim v obdobju {SNOW_OLD} jih je imelo {numw(long60_old)} "
        f"vsaj 60 dni s snežno odejo, dve pa največ 20 dni. V zimah {wl(gap_old[0][0])} in {wl(gap_old[1][0])} je snežna odeja vztrajala "
        f"le po {gap_old[0][1]} dni.",
        f"V zadnjih desetih zimah ni bilo nobene s 60 ali več dnevi snežne odeje, v {numg(short_new)} pa je snežna odeja vztrajala "
        "največ 20 dni.",
        f"Najdaljša zima s snežno odejo v tem nizu je bila {wl(P95)}. Ko se zapisi 1. januarja 1996 začnejo, je na tleh že "
        f"{num(SP['depth_first_cm'], 0)} cm snega, odeja pa od tega dne leži {dni(SP['longest'])} zapored, torej skupno vsaj 80 dni. Ker november in december 1995 "
        "v podatkih manjkata, te zime ne štejem v povprečja. Takšna zima se človeku vtisne v spomin. Zima s samo 13 dnevi snežne odeje "
        "pa precej manj.",
        "<h3>In višje? Črnivec na 848 metrih</h3>",
        "ARSO meri snežno odejo tudi na Črnivcu na nadmorski višini 848 m, o katerem pišem na " + a("crnivec", "crnivec.si") + ". Meritve "
        "tam potekajo šele od leta 2021, zato primerjave z daljno preteklostjo niso mogoče.",
        f"Podatki pa kažejo, da tudi na tej višini sneg v zadnjih zimah ni vztrajal tri mesece. Največ dni s snežno odejo so izmerili "
        f"pozimi {wl(crn_max)}, in sicer {CR[crn_max]['days']}. V isti zimi je trajalo tudi najdaljše strnjeno obdobje s snežno odejo: "
        f"{dni(CR[crn_run]['longest'])}.",
        t_crn,
    ]
    p3 = [
        f"Moja vremenska postaja IREICA1 meri od novembra 2019. Za ugotavljanje dolgoročnih trendov je {numw(n_own)} zim premalo, za opis "
        "razmer v dolini v zadnjih letih pa so podatki vseeno zanimivi.",
        f"V vseh {numg(n_own)} zimah je bilo v Rečici od{numg(min(own_ice))} do {numg(max(own_ice))} ledenih dni. Povprečna temperatura od decembra do "
        f"februarja se je gibala med {num(min(own_t))} in {num(max(own_t))} °C. Snežne odeje postaja ne meri, zato za Rečico nimam podatkov "
        "o številu dni s snegom.",
        t3,
        "Rečice ne moremo enačiti ne z Ljubljano ne s Šmartnim. Postaja stoji na dnu doline, kjer se zaradi lokalnih razmer oblikuje "
        "lastna mikroklima.",
        "V vseh štirih skupnih zimah je bila povprečna temperatura v Rečici med vrednostmi za Ljubljano in Šmartno. Po številu ledenih dni "
        "pa je bila Rečica večinoma bližje Ljubljani.",
    ]
    p4 = [
        f"Otrok, rojen leta 2018, je do zdaj doživel zime {zs(kid_years[0])} {', '.join(str(v) for v in kid_years[:-1])} in {kid_years[-1]} "
        f"dnevi snežne odeje. Gre za podatke za Ljubljano v zimah 2018/19–2024/25, kar pomeni povprečno {num(mean(kid_years), 0)} dni na zimo.",
        "Zanj je to običajna zima.",
        "Ribiški biolog Daniel Pauly je leta 1995 opisal pojav, imenovan " + a("pauly", "sindrom premikajoče se osnove") + " (shifting "
        "baseline syndrome). Vsaka generacija za normalno vzame stanje, ki ga je poznala na začetku svojega življenja, zato počasne "
        "spremembe težje opazi. Pauly je ta pojav opisal pri ribištvu, vendar se podobno načelo lahko pokaže tudi pri našem dojemanju zime.",
        "<h3>Zakaj se odrasli zim spominjamo drugače?</h3>",
        "Pri odraslih se lahko zgodi ravno nasprotno. Psihologi so ugotovili, da se ljudje, starejši od približno 40 let, nesorazmerno "
        "pogosto spominjajo dogodkov iz obdobja med približno 10. in 30. letom starosti. Ta pojav se imenuje reminiscenčni vrh (Rubin, "
        "Wetzler in Nebes, 1986).",
        "Za marsikoga med nami so bile zime med letoma 1980 in 2002 prav del tega življenjskega obdobja.",
        "Drugi pojav je tako imenovani »rožnati pogled nazaj«. V raziskavi o počitnicah in izletih so udeleženci iste dogodke pozneje "
        "ocenili bolj pozitivno, kot so jih doživljali med samim dogodkom (" + a("rosy", "Mitchell in sodelavci, 1997") + "). "
        "Neprijetnosti sčasoma zbledijo, lepi trenutki pa ostanejo.",
        f"Tretji razlog je preprost: v spominu ostanejo izjeme, ne povprečja. Zima z vsaj {SP['longest']} dnevi snežne odeje "
        "se vtisne v spomin, zima s 13 dnevi pa precej manj. Zato je naš spomin na zime najverjetneje bolj zasnežen, kot so bile zime "
        "v povprečju.",
        "To je moja razlaga, ki se ujema z omenjenimi raziskavami. Raziskav, ki bi posebej merile spomin na zime, nisem našel.",
        "<h3>Kultura zime</h3>",
        "Po mojem opažanju vrtci in šole še vedno opevajo zimo, v kateri sneg leži tri mesece. Domnevam, da se kultura prilagaja počasneje "
        "kot vreme, vendar je to za zdaj le domneva. Raziskave o tem, kako otroci v Sloveniji doživljajo zimo, nisem našel.",
        "Pesem o zimi s skoraj tremi meseci snega torej ni izmišljena. Takšne zime so obstajale, v zadnjih desetih obravnavanih zimah "
        "v Ljubljani pa ni bilo nobene. Otroci danes takšno zimo zato pogosto poznajo predvsem iz pesmi in pripovedovanja.",
        "Hkrati pa tudi nekoč ni bila vsaka zima takšna.",
        "Ali so otroci zaradi tega za kaj prikrajšani? Tega ne vem. To je vprašanje za psihologe in pedagoge, ne za vremensko postajo.",
    ]
    p_starsi = [
        "Nekaj predlogov, ki izhajajo iz podatkov v tem članku. To so moje zamisli, ne strokovni pedagoški nasveti.",
        "<h3>1. Zima ni samo sneg</h3>",
        f"V Rečici je bilo v zimah 2019/20–2025/26 od {min(own_frost)} do {max(own_frost)} dni z zmrzaljo. Slana, zamrznjene luže, megla in "
        "ivje na drevju so prav tako del zime, ki jo naša dolina še pozna.",
        "Tudi o teh pojavih se lahko pogovarjamo, jih opazujemo, fotografiramo in o njih pojemo pesmi.",
        "<h3>2. Ko zapade sneg, ga izkoristite</h3>",
        f"V zimah 2018/19–2024/25 je najdaljše neprekinjeno obdobje s snežno odejo v Ljubljani trajalo od {min(kid_runs)} do "
        f"{dni(max(kid_runs))}. Če snega ne izkoristite v prvih dneh, ga morda kmalu ne bo več.",
        "<h3>3. Izmerite ga</h3>",
        "Dovolj so ravnilo, zapisan datum in podatek o višini snega. Otrok, ki tri zime zapored meri snežno odejo, si bo ustvaril lastno "
        "primerjavo in ne bo odvisen le od pripovedi odraslih.",
        "V vrtcu ali šoli lahko meritve primerjajo s tem, kar o nekdanjih zimah pripovedujejo stari starši.",
        "<h3>4. Pesmi ni treba opustiti</h3>",
        "Pesem o zimi, v kateri sneg leži tri mesece, je lahko izhodišče za pogovor. Kakšne zime so poznali dedki in babice? Kakšne so "
        "danes? Zakaj se spreminjajo?",
        "Podatki v tem članku so lahko preprosto izhodišče za takšen pogovor.",
    ]
    p5 = [
        "<ul>"
        "<li><strong>Ljubljana ni Rečica.</strong> Ljubljana Bežigrad je mestna postaja na nadmorski višini 299 m, Šmartno pa leži "
        "v kotlini na 444 m. Zgornja Savinjska dolina ima svoje lokalne razmere in ni enaka nobenemu od teh krajev.</li>"
        "<li><strong>Podatki o snegu so samo za Ljubljano.</strong> GHCN za Ljubljano hrani podatke o dnevih s snežno odejo, ne pa tudi "
        "izrecnih ničel. Dan brez zapisa sem štel kot dan brez snežne odeje. To sem preveril: odeja se v zapisih skoraj vedno konča pri "
        "1–3 cm, torej postopoma skopni, vrzeli sredi debelejše odeje pa so v 30 letih le štiri. Zapisi se začnejo 1. januarja 1996, "
        "zato zime 1995/96 nisem vključil v povprečja, prav tako ne zime 2004/05, za katero ni nobenega zapisa. Vrednosti, ki jih vir "
        "označuje kot sumljive, sem izpustil. Ker pred letom 1996 ni podatkov o snegu, trditve o zimah v osemdesetih glede snežne "
        "odeje ne morem preveriti. Za primerjavo temperatur pa podatki obstajajo.</li>"
        "<li><strong>Temperaturni podatki segajo do zime 2022/23.</strong> V uporabljenem viru ni podatkov za poznejše zime, manjkajo "
        "pa tudi podatki za šest zim med letoma 1918 in 1928.</li>"
        "<li><strong>Črnivec ima le nekaj let meritev.</strong> Pet zim ni dovolj za sklepanje o dolgoročnem trendu. Podatki kažejo "
        "samo, kakšne so bile zadnje zime na nadmorski višini 848 m.</li>"
        "<li><strong>Prag odjuge je moja izbira.</strong> Za odjugo sem določil mejo 5 °C, ker uradne opredelitve s takšnim temperaturnim "
        "pragom nisem našel. Pri drugačnem pragu bi bile številke drugačne.</li>"
        "<li><strong>Psihološki del temelji na splošnih raziskavah spomina.</strong> Nobena od navedenih raziskav ni posebej obravnavala "
        "spomina na zime ali doživljanja zime pri otrocih v Sloveniji.</li>"
        "<li><strong>Obdobja primerjave so izbrana za potrebe analize.</strong> Obdobje 1981–2002 sem izbral zato, ker zajema del mojega "
        "osebnega spomina, obdobje 2013–2022 pa predstavlja zadnjih deset zim z razpoložljivimi podatki. Zima nosi letnico decembra: "
        "obdobje 1981–2002 torej zajema zime od 1981/82 do 2002/03. Pri drugačni razdelitvi bi bile številke drugačne, glavna smer "
        "sprememb pa ostaja enaka.</li>"
        "<li><strong>Zimski občutek ni odvisen samo od temperature in snega.</strong> Pomembni so tudi megla, oblačnost, veter in dolžina "
        "dneva. V tej analizi jih ne obravnavam.</li></ul>",
    ]
    p_viri = [
        "<ul>"
        "<li>" + a("ghcn", "Global Historical Climatology Network – Daily") + ", NOAA NCEI: Ljubljana Bežigrad (SIM00014015) in "
        "Šmartno pri Slovenj Gradcu (SIE00115136). Podatki ARSO prek ECA&amp;D. Prenos: 12. 10. 2026.</li>"
        "<li>Meritve postaje IREICA1 (Meteorec), od novembra 2019. Notranjih meritev v tej analizi nisem uporabil.</li>"
        "<li>ARSO, arhiv meritev: padavinska postaja Črnivec (848 m), podatki o snežni odeji in novem snegu od leta 2021.</li>"
        "<li>Rubin, D. C., Wetzler, S. E., Nebes, R. D. (1986): Autobiographical memory across the lifespan. V: Rubin, D. C. (ur.), "
        "Autobiographical Memory, Cambridge University Press, str. 202–221.</li>"
        "<li>Mitchell, T. R., Thompson, L., Peterson, E., Cronk, R. (1997): " + a("rosy", "Temporal adjustments in the evaluation of "
        "events: The »rosy view«") + ". Journal of Experimental Social Psychology 33(4): 421–448.</li>"
        "<li>Pauly, D. (1995): " + a("pauly", "Anecdotes and the shifting baseline syndrome of fisheries") + ". Trends in Ecology "
        "&amp; Evolution 10(10): 430.</li>"
        "</ul>",
        "<strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z navedbo avtorja (Filip Eremita, Meteorec) in "
        "neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se predhodno dogovorite z avtorjem.",
    ]
    p6 = [
        f'Zimo v naši dolini spremljamo na strani <a href="{SITE}/zima/" style="color:var(--blue)">Zima</a>, vse dnevne meritve postaje '
        f'pa so na voljo v <a href="{SITE}/vreme/" style="color:var(--blue)">vremenskem arhivu</a>.',
        "Ko bo naslednjič zapadel sneg, si zapišite datum in koliko dni se je obdržal. Čez nekaj let boste imeli svoje podatke, na katere "
        "se boste lahko oprli namesto zgolj na spomin.",
    ]

    title = "So zime še takšne, kot so bile nekoč? Podatki in spomin"
    assert len(title) <= 60, len(title)
    desc = ("Ledenih dni je v Ljubljani za dve tretjini manj kot v letih 1981–2002, snežne odeje več kot pol manj. "
            "Kaj to pomeni za otroke, ki poznajo le današnje zime?")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — mraz", "heading": "Mraza je manj, ledenih dni še posebej", "id": "mraz", "paragraphs": p1},
        {"label": "02 — sto let", "heading": "Sto dvajset let zim v Ljubljani", "id": "sto-let", "paragraphs": p_sto},
        {"label": "03 — odjuga", "heading": "Odjuga: več toplih dni, zlasti februarja", "id": "odjuga", "paragraphs": p_odjuga},
        {"label": "04 — sneg", "heading": "Sneg: krajši in manj zanesljiv", "id": "sneg", "paragraphs": p2},
        {"label": "05 — Rečica", "heading": "Kaj kaže postaja v Rečici?", "id": "recica", "paragraphs": p3},
        {"label": "06 — otroci", "heading": "Zima, ki je otrok ne pozna", "id": "otroci", "paragraphs": p4},
        {"label": "07 — starši in šole", "heading": "Kaj lahko storijo starši, vrtci in šole?", "id": "starsi", "paragraphs": p_starsi},
        {"label": "08 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": p5},
        {"label": "09 — viri", "heading": "Viri", "id": "viri", "paragraphs": p_viri},
        {"label": "10 — kaj lahko storite", "heading": "Zapišite svojo zimo", "id": "zapisite", "paragraphs": p6},
    ]
    return {
        "title": title, "meta_description": desc,
        "tags": ["zima", "sneg", "podnebje", "otroci", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "weather-station", "og_accent_hex": "#22d3ee",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Podatki in metodologija: NOAA GHCN-Daily (Ljubljana, Šmartno), ARSO (Črnivec), meritve postaje IREICA1 (Meteorec). "
                         "Podatki: /data/zime.json."),
    }


def main():
    wire, dry = "--wire" in sys.argv, "--dry-run" in sys.argv
    D = json.load(open(DATA, encoding="utf-8"))
    article = build_article(D)
    if dry:
        print(json.dumps(article, ensure_ascii=False, indent=2))
        return
    path = os.path.join(ROOT, "blog", f"{SLUG}.html")
    if os.path.exists(path) and "--force" not in sys.argv:
        print(f"blog/{SLUG}.html že obstaja — brez ponovne objave (--force za prepis).")
        return
    import generate_forecast_test_post as ftp
    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = today.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, today.year, today.month, now_utc, slug=SLUG,
        back=("/blog/", "← Vsi članki"), og_title="So zime še takšne,\nkot so bile nekoč?",
        meta_note="podatkovna analiza", nav_label="O postaji", nav_href="/o-postaji.html")
    html = html.replace('<p class="lead">', STYLE + '\n<p class="lead">', 1)
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
