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


def numw(n):
    return _W[n] if 0 <= n <= 10 else str(n)


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

    s_old = [SN[y] for y in range(1995, 2004) if y in SN]
    s_mid = [SN[y] for y in range(2005, 2015) if y in SN]
    s_new = [SN[y] for y in range(2015, 2025) if y in SN]
    d_old, d_new = mean(s["days"] for s in s_old), mean(s["days"] for s in s_new)
    d_mid = mean(s["days"] for s in s_mid)
    long60_old = sum(s["days"] >= 60 for s in s_old)
    long60_new = sum(s["days"] >= 60 for s in s_new)
    short_old = sum(s["days"] <= 20 for s in s_old)
    short_new = sum(s["days"] <= 20 for s in s_new)
    kid_years = [SN[y]["days"] for y in range(2018, 2025) if y in SN]
    best_old = max(SN[y]["days"] for y in range(1995, 2004))
    gap_old = sorted((y, SN[y]["days"]) for y in range(1995, 2004) if SN[y]["days"] <= 20)
    assert d_old > d_new and long60_old == 5 and long60_new == 0 and len(gap_old) == 2

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

    fig1 = fig("Ledeni dnevi v zimi (december–februar): koliko dni je bilo ves dan pod 0 °C?",
               f'<div class="zm-row"><div><p class="zm-note" style="margin:0 0 .3rem">Ljubljana Bežigrad (299 m)</p>{ch_lj}</div>'
               f'<div><p class="zm-note" style="margin:0 0 .3rem">Šmartno pri Slovenj Gradcu (444 m)</p>{ch_sm}</div></div>'
               + legend([("1961–2002", CYAN), ("po letu 2002", PURPLE)]),
               "Povprečje ledenih dni (najvišja dnevna temperatura pod 0 °C) na zimo po obdobjih. Vir: GHCN-Daily (ARSO). "
               "Zima 2022/23 je zadnja v podatkih.")
    fig2 = fig("Dnevi s snežno odejo od novembra do marca, Ljubljana, po zimah",
               ch_snow + legend([("1995/96–2003/04", CYAN), ("2005/06–2024/25", PURPLE)]),
               "Označeno je leto, v katerem zima začne (95 = zima 1995/96). Zime 2004/05 v podatkih ni. "
               "Vir: GHCN-Daily (ARSO), višina snežne odeje.")

    # --- tabele ---
    t1 = table(["Obdobje (zime)", "Povprečna temperatura dec.–feb.", "Dnevi z zmrzaljo", "Ledeni dnevi", "Dnevi pod –10 °C"],
               [[f"{p} (Ljubljana)", f"{num(lj[p]['tmean'])} °C", num(lj[p]["frost"]), num(lj[p]["ice"]), num(lj[p]["hard"])]
                for p in lj]
               + [[f"{p} (Šmartno)", f"{num(sm[p]['tmean'])} °C", num(sm[p]["frost"]), num(sm[p]["ice"]), num(sm[p]["hard"])]
                  for p in sm],
               "Zimski kazalniki po obdobjih za Ljubljano in Šmartno pri Slovenj Gradcu",
               "Povprečja na zimo. Dan z zmrzaljo: najnižja temperatura pod 0 °C; ledeni dan: najvišja pod 0 °C; "
               "dan pod –10 °C: najnižja –10 °C ali manj. Zima je december–februar in velja, če ima vsaj 95 % dni obeh meritev.")
    t2 = table(["Obdobje", "Zim", "Dni s snežno odejo (nov.–mar.)", "Najdaljše strnjeno obdobje", "Zim z vsaj 60 dnevi", "Zim z največ 20 dnevi"],
               [[lbl, str(len(g)), num(mean(s["days"] for s in g), 0), num(mean(s["longest"] for s in g), 0), str(sum(s["days"] >= 60 for s in g)),
                 str(sum(s["days"] <= 20 for s in g))]
                for lbl, g in (("1995/96–2003/04", s_old), ("2005/06–2014/15", s_mid), ("2015/16–2024/25", s_new))],
               "Snežna odeja v Ljubljani po obdobjih zim",
               "Povprečja na zimo. Podatki o snegu so iz Ljubljane, ne iz Zgornje Savinjske doline.")
    ov = [y for y in (2019, 2020, 2021, 2022) if y in OWN and y in LJ and y in SM]
    t3 = table(["Zima", "Rečica ob Savinji (IREICA1)", "Ljubljana", "Šmartno"],
               [[f"{y}/{str(y + 1)[2:]}",
                 f"{num(OWN[y]['tmean'])} °C · {OWN[y]['ice']} ledenih dni",
                 f"{num(LJ[y]['tmean'])} °C · {LJ[y]['ice']} ledenih dni",
                 f"{num(SM[y]['tmean'])} °C · {SM[y]['ice']} ledenih dni"] for y in ov],
               "Primerjava zim 2019/20 do 2022/23: Rečica, Ljubljana in Šmartno",
               "Povprečna temperatura je povprečje dnevnih najvišjih in najnižjih vrednosti (dec.–feb.).")
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
    sm80, sm90 = period_stats(SM, 1981, 1990), period_stats(SM, 1991, 2002)
    fig_dec = fig("Povprečna zima v Ljubljani po desetletjih, 1901–2022",
                  ch_dec + legend([("osemdeseta in devetdeseta", CYAN), ("ostala desetletja", PURPLE)]),
                  f"Povprečna temperatura od decembra do februarja. Oznaka je prvo leto desetletja (1980 = zime 1980/81–1989/90). "
                  f"Z zvezdico je desetletje z manj kot desetimi zimami v podatkih (zadnje: {last_n} zime). Vir: GHCN-Daily (ARSO).")
    fig_icew = fig("Ledeni dnevi v Ljubljani po zimah, 1951/52–2022/23",
                   ch_icew + legend([("zime 1981/82–2002/03", CYAN), ("druge zime", PURPLE)]),
                   "Število dni, ko se temperatura ves dan ni dvignila nad 0 °C (december–februar). Oznaka je leto, v katerem se zima začne. "
                   "Vir: GHCN-Daily (ARSO).")

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
                     "Povprečna temperatura meseca je povprečje dnevnih najvišjih in najnižjih vrednosti. "
                     "»Dni z vsaj 5 °C«: dnevi od decembra do februarja, ko je najvišja temperatura dosegla vsaj 5 °C (povprečje na zimo, od približno 90 dni).")
    lj_feb, sm_feb = month(LJ, "02"), month(SM, "02")
    lj_dec, lj_jan = month(LJ, "12"), month(LJ, "01")
    assert lj_feb[new_p] - lj_feb[old_p] > max(lj_dec[new_p] - lj_dec[old_p], lj_jan[new_p] - lj_jan[old_p])

    # --- Črnivec ---
    CR = {int(y): v for y, v in D["crnivec"].items()}
    t_crn = table(["Zima", "Dni s snežno odejo (nov.–mar.)", "Najdaljše strnjeno obdobje", "Največja odeja", "Novi sneg skupaj"],
                  [[wl(y), str(CR[y]["days"]), dni(CR[y]["longest"]), f"{int(CR[y]['max_cm'])} cm", f"{int(CR[y]['new_cm'])} cm"] for y in sorted(CR)],
                  "Snežna odeja na Črnivcu (ARSO, 848 m) po zimah",
                  "Vir: ARSO, padavinska postaja Črnivec (848 m), arhiv meritev. Postaja meri od leta 2021.")
    crn_max = max(CR, key=lambda y: CR[y]["days"])
    crn_run = max(CR, key=lambda y: CR[y]["longest"])
    assert max(CR[y]["days"] for y in CR) < 90 and crn_max == crn_run
    kid_runs = [SN[y]["longest"] for y in range(2018, 2025) if y in SN]
    own_frost = [OWN[y]["frost"] for y in sorted(OWN)]
    assert min(OWN) == 2019 and max(OWN) == 2025

    own_ice = [OWN[y]["ice"] for y in sorted(OWN)]
    own_t = [OWN[y]["tmean"] for y in sorted(OWN)]
    n_own = len(OWN)

    # --- besedilo ---
    p1 = [
        f"Začnimo z mrazom. Ledeni dan je dan, ko se temperatura ves dan ne dvigne nad 0 °C. Njihovo število na zimo je bilo v Ljubljani v zimah "
        f"{old_p} povprečno {num(lj[old_p]['ice'])}, v zadnjih desetih zimah ({new_p}) pa {num(lj[new_p]['ice'])}. "
        f"V Šmartnem pri Slovenj Gradcu, ki je hladnejša kotlina, je bilo prej {num(sm[old_p]['ice'])}, zdaj {num(sm[new_p]['ice'])}.",
        f"Povprečna temperatura zime (december–februar) je v Ljubljani zrasla z {num(lj[old_p]['tmean'])} °C na {num(lj[new_p]['tmean'])} °C, "
        f"v Šmartnem z {num(sm[old_p]['tmean'])} °C na {num(sm[new_p]['tmean'])} °C. V obeh primerih je to približno 2 °C več.",
        fig1, t1,
        f"Dni z zmrzaljo (najnižja temperatura pod 0 °C) je sicer tudi manj, a upad je precej manjši: v Šmartnem je bilo povprečno {num(sm[old_p]['frost'], 0)} na zimo, zdaj {num(sm[new_p]['frost'], 0)}. "
        "Noči so v kotlinah še vedno mrzle. Izginjajo predvsem dnevi, ko mraz ne popusti niti opoldne.",
        f"Zanimivo je, da obdobje 1981–2002 ni enotno. Osemdeseta so bila opazno hladnejša od devetdesetih: v Ljubljani je imela zima v letih "
        f"1981–1990 povprečno {num(lj80['tmean'])} °C, v letih 1991–2002 pa {num(lj90['tmean'])} °C. Število ledenih dni je bilo {num(lj80['ice'])} "
        f"oziroma {num(lj90['ice'])}, v Šmartnem {num(sm80['ice'])} oziroma {num(sm90['ice'])}. Kdor je otroštvo preživel v osemdesetih, je torej "
        "doživljal hladnejše zime kot nekdo, ki je odraščal v devetdesetih.",
    ]
    p_sto = [
        f"Ljubljana Bežigrad meri od leta 1901, zato lahko pogledamo širše. V viru ni podatkov za zime "
        f"{', '.join(wl(y) for y in missing[:-1])} in {wl(missing[-1])}; vse ostale so na grafu.",
        fig_dec,
        f"Do sedemdesetih let se povprečna zima po desetletjih ni bistveno spreminjala: nihala je med {num(min(early))} in {num(max(early))} °C. "
        f"Osemdeseta ({num(dec[1980])} °C) so bila zadnje desetletje s povprečjem pod 1 °C. Sledila so devetdeseta z {num(dec[1990])} °C, "
        f"prvo desetletje novega tisočletja z {num(dec[2000])} °C in desetletje 2010–2019 z {num(dec[2010])} °C. Zadnji stolpec ima le {last_n} zime "
        f"({num(last_t)} °C), zato ga ne primerjam enakovredno z ostalimi.",
        f"Najhladnejše zime v tej vrsti so bile {wl(cold3[0])} ({num(LJ[cold3[0]]['tmean'])} °C), {wl(cold3[1])} ({num(LJ[cold3[1]]['tmean'])} °C) "
        f"in {wl(cold3[2])} ({num(LJ[cold3[2]]['tmean'])} °C). Najtoplejša je bila {wl(warmest)} ({num(LJ[warmest]['tmean'])} °C), sledijo "
        f"{', '.join(wl(y) for y in warm_next[:-1])} in {wl(warm_next[-1])} z okoli {num(LJ[warm_next[0]]['tmean'])} °C. Najhladnejša zima obdobja 1981–2002 je bila {wl(coldest_mine)} "
        f"({num(LJ[coldest_mine]['tmean'])} °C, {LJ[coldest_mine]['ice']} ledenih dni).",
        fig_icew,
        f"Graf ledenih dni po zimah pokaže, kako različne so bile zime tudi nekoč. Od 22 zim v letih 1981–2002 jih je imelo v Ljubljani "
        f"{lj20_old} vsaj 20 ledenih dni, v zimah 2013–2022 le ena ({wl(lj20_new[0])}). V Šmartnem je bilo takih zim prej {sm20_old}, "
        "v zadnjih desetih nobena.",
    ]
    p_odjuga = [
        "Sneg pade, nato pride odjuga – tak je občutek zadnjih zim. Za odjugo sem štel dneve, ko najvišja temperatura doseže vsaj 5 °C. "
        f"V Ljubljani je bilo takih dni v zimah {old_p} povprečno {num(lj_m[old_p], 0)}, v zimah {new_p} pa {num(lj_m[new_p], 0)} od približno 90 "
        f"zimskih dni, v Šmartnem pa {num(sm_m[old_p], 0)} proti {num(sm_m[new_p], 0)}.",
        t_months,
        f"Najbolj se je spremenil februar. V Ljubljani je bil v zimah {old_p} povprečno {num(lj_feb[old_p])} °C, v zimah {new_p} pa "
        f"{num(lj_feb[new_p])} °C; v Šmartnem {num(sm_feb[old_p])} °C proti {num(sm_feb[new_p])} °C. Desetletje je kratko obdobje, zato je lahko "
        "ta razlika deloma posledica nekaj zelo toplih februarjev; smer pa se ujema z decembrom in januarjem.",
        "Za sneg je to pomembno. Nizka snežna odeja v dolini ob dnevih z več stopinjami nad ničlo in ob dežju navadno hitro skopni. "
        "Več toplih dni pomeni, da tudi sneg, ki pade, krajši čas ostane.",
    ]
    p2 = [
        f"Sneg je zgodba zase, ker potrebuje mraz in padavine hkrati. Podatki o snežni odeji v Ljubljani, ki jih imam, segajo samo do leta 1995 nazaj. "
        f"V zimah 1995/96–2003/04 je snežna odeja od novembra do marca ležala povprečno {dni(round(d_old))}, v zimah 2015/16–2024/25 pa {dni(round(d_new))}.",
        fig2, t2,
        f"Ni pa res, da so bile vse zime nekoč take. Od devetih zim 1995/96–2003/04 jih je imelo pet vsaj 60 dni snega, "
        f"dve pa največ 20 (zimi {gap_old[0][0]}/{str(gap_old[0][0] + 1)[2:]} in {gap_old[1][0]}/{str(gap_old[1][0] + 1)[2:]}: po {dni(gap_old[0][1])}). "
        f"V zadnjih desetih zimah ni bilo nobene z vsaj 60 dnevi, {numw(short_new)} pa jih je imelo največ 20.",
        f"Najdaljša snežna zima v teh podatkih je 1995/96: odeja je ležala {dni(best_old)} zapored (največ 36 cm). Takšna zima se spominu vtisne; "
        "tiste s 13 dnevi snega pa ne.",
        "<h3>In višje? Črnivec na 848 m</h3>",
        f"ARSO meri sneg tudi na Črnivcu (848 m), o katerem pišem na " + a("crnivec", "crnivec.si") + ". "
        f"Meri šele od leta 2021, zato primerjave z nekoč ne omogoča. Pove pa, da tudi pol kilometra višje od dna doline sneg zadnje zime "
        f"ni ležal tri mesece: največ {dni(CR[crn_max]['days'])} snežne odeje je bilo v zimi {wl(crn_max)}, ko je bilo tudi "
        f"najdaljše strnjeno obdobje, {dni(CR[crn_run]['longest'])}.",
        t_crn,
    ]
    p3 = [
        f"Moja postaja IREICA1 meri od novembra 2019, to je {numw(n_own)} zim. Za trend je premalo, za sliko današnje doline pa zadošča. "
        f"V teh zimah je bilo v Rečici od {min(own_ice)} do {max(own_ice)} ledenih dni, povprečna temperatura od decembra do februarja pa "
        f"od {num(min(own_t))} do {num(max(own_t))} °C. Snežne odeje postaja ne meri, zato za Rečico podatka o snegu nimam.",
        t3,
        "Rečice ne smemo enačiti z nobeno od teh postaj: stoji na dnu doline in ima svojo mikroklimo. Povprečna temperatura je bila v vseh štirih skupnih "
        "zimah med ljubljansko in šmarško, po številu ledenih dni pa je bila večinoma bliže Ljubljani.",
    ]
    p4 = [
        f"Otrok, ki je rojen leta 2018, je do zdaj doživel zime z {', '.join(str(v) for v in kid_years[:-1])} in {kid_years[-1]} dnevi snežne odeje "
        f"(Ljubljana, zime 2018/19–2024/25; povprečno {num(mean(kid_years), 0)} dni). Zanj je to zima. Ribiški biolog Daniel Pauly je leta 1995 "
        f"opisal tako imenovani " + a("pauly", "sindrom premikajoče se osnove") + " (shifting baseline syndrome): vsaka generacija za normalno "
        "vzame stanje, ki ga je videla na začetku, in počasnih sprememb ne opazi. Pauly je to opisal za ribolov, a načelo velja tudi za zimo.",
        "<h3>Zakaj se odrasli spomnimo drugače</h3>",
        "Pri odraslih deluje ravno obratno. Psihologi so opazili, da se odrasli, starejši od približno 40 let, največ osebnih spominov "
        "spomnijo iz obdobja med približno 10. in 30. letom starosti. Pojav se imenuje reminiscenčni vrh (Rubin, Wetzler in Nebes, 1986). Zime iz let 1980–2002 so za mnoge "
        "med nami ravno to obdobje.",
        "Drugi pojav je »rožnati pogled nazaj«. V raziskavi o počitnicah in izletih so udeleženci iste dogodke pozneje ocenili bolje, kot so "
        "jih ocenjevali med samim dogodkom (" + a("rosy", "Mitchell in sodelavci, 1997") + "). Neprijetnosti zbledijo, lepi trenutki ostanejo.",
        "Tretje je preprosto: spomin hrani izjeme, ne povprečij. Zima z 80 dnevi snega se vtisne, zima s 13 dnevi ne. Naš spomin na zime "
        "je zato najverjetneje bolj zasnežen, kot so bile zime v povprečju. To je moja razlaga, ki se ujema z omenjenimi raziskavami; "
        "posebej o spominu na zime ni nihče meril.",
        "<h3>Kultura zime</h3>",
        "Po mojem opažanju vrtci in šole še vedno opevajo zimo, v kateri sneg leži tri mesece. Domnevam, da se kultura prilagaja počasneje "
        "kot vreme, a to je domneva. Raziskave o tem, kako otroci v Sloveniji doživljajo zimo, nisem našel.",
        "Pesem o skoraj treh mesecih snega torej ni izmišljena: take zime so bile, v zadnjih desetih zimah v Ljubljani pa nobene. "
        "Otrok jo zato pozna predvsem iz pesmi. Hkrati pa tudi nekoč ni bila vsaka zima taka.",
        "Ali to otroke za kaj prikrajša, ne vem. To je vprašanje za psihologe in pedagoge, ne za vremensko postajo.",
    ]
    p_starsi = [
        "Nekaj predlogov, ki izhajajo iz podatkov v tem članku. So moji, ne pedagoški nasveti.",
        "<h3>1. Zima ni samo sneg</h3>",
        f"V Rečici je bilo v zimah 2019/20–2025/26 od {min(own_frost)} do {max(own_frost)} dni z zmrzaljo. Slana, zamrznjene luže, megla in "
        "ivje na drevju so zima, ki jo naša dolina še ima. Tudi o tem se da peti in pripovedovati.",
        "<h3>2. Ko sneg pade, ga izkoristite takoj</h3>",
        f"V zimah 2018/19–2024/25 je najdaljše strnjeno obdobje snežne odeje v Ljubljani trajalo od {min(kid_runs)} do {dni(max(kid_runs))}. "
        "Če snega ne izkoristite v prvih dneh, ga morda ne boste več.",
        "<h3>3. Izmerite ga</h3>",
        "Ravnilo, zapisan datum in višina snega. Otrok, ki tri zime zapored meri sneg, bo imel svojo primerjavo, ne le spomina odraslih. "
        "V vrtcu ali šoli se meritve lahko primerjajo s tem, kar pripovedujejo stari starši.",
        "<h3>4. Pesmi ni treba opustiti</h3>",
        "Pesem o zimi s tremi meseci snega je lahko izhodišče za pogovor: kakšne zime so poznali dedki in babice, kakšne so danes in zakaj. "
        "Podatki v tem članku so za to dovolj preprosti.",
    ]
    p5 = [
        "<ul>"
        "<li><strong>Ljubljana ni Rečica.</strong> Bežigrad je mestna postaja na 299 m, Šmartno kotlina na 444 m. Zgornja Savinjska dolina je med njima "
        "in ni nobena od njiju.</li>"
        "<li><strong>Sneg je samo iz Ljubljane.</strong> GHCN za Ljubljano hrani le dneve z odejo, ničle ne. Dan brez zapisa štejem za dan brez odeje; "
        "zimi 2004/05 ni nobenega zapisa, zato je nisem upošteval. Pred letom 1995 ni snežnih podatkov, zato se mojih osemdesetih let "
        "po snegu ne da preveriti, po temperaturi pa.</li>"
        "<li><strong>Podatki o temperaturi segajo do zime 2022/23.</strong> Kasnejših zim v teh virih ni, manjka tudi šest zim iz let 1918–1928.</li>"
        "<li><strong>Črnivec meri šele pet zim.</strong> To ni trend, ampak slika zadnjih let na 848 m.</li>"
        "<li><strong>Prag odjuge (5 °C) je moj izbor.</strong> Uradne opredelitve odjuge s pragom nisem našel; drugačen prag da druge številke.</li>"
        "<li><strong>Psihološki del je povzetek splošnih raziskav o spominu.</strong> Nobena od njih ni merila spomina na zime ali otrok v Sloveniji.</li>"
        "<li><strong>Obdobja so poljubno izbrana.</strong> 1981–2002 je obdobje mojega spomina, 2013–2022 zadnjih deset zim s podatki; druga razdelitev da druge "
        "številke, a smer ostane ista.</li>"
        "<li><strong>Zimski občutek ni samo temperatura in sneg.</strong> Megla, oblačnost, veter in dolžina dneva so v zimi prav tako pomembni; "
        "tu jih ne merimo.</li></ul>",
    ]
    p_viri = [
        "<ul>"
        "<li>" + a("ghcn", "Global Historical Climatology Network – Daily") + ", NOAA NCEI: Ljubljana Bežigrad (SIM00014015), "
        "Šmartno pri Slovenj Gradcu (SIE00115136). Podatki ARSO prek ECA&amp;D. Prenos 12. 10. 2026.</li>"
        "<li>Meritve postaje IREICA1 (Meteorec), od novembra 2019. Notranjih meritev nisem uporabil.</li>"
        "<li>ARSO, arhiv meritev: padavinska postaja Črnivec (848 m), snežna odeja in novi sneg, od leta 2021.</li>"
        "<li>Rubin, D. C., Wetzler, S. E., Nebes, R. D. (1986): Autobiographical memory across the lifespan. V: Rubin, D. C. (ur.), "
        "Autobiographical Memory, Cambridge University Press, str. 202–221.</li>"
        "<li>Mitchell, T. R., Thompson, L., Peterson, E., Cronk, R. (1997): " + a("rosy", "Temporal adjustments in the evaluation of events: "
        "The »rosy view«") + ". Journal of Experimental Social Psychology 33(4): 421–448.</li>"
        "<li>Pauly, D. (1995): " + a("pauly", "Anecdotes and the shifting baseline syndrome of fisheries") + ". Trends in Ecology &amp; Evolution 10(10): 430.</li>"
        "</ul>",
        "<strong>Uporaba vsebine.</strong> Besedilo, grafe in podatke lahko povzamete le z navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo "
        "na ta članek. Za prepis ali vdelavo grafov in izračunov prosim vprašajte vnaprej.",
    ]
    p6 = [
        f'Zimo v naši dolini spremljamo na strani <a href="{SITE}/zima/" style="color:var(--blue)">Zima</a>, vse dnevne meritve postaje pa so v '
        f'<a href="{SITE}/vreme/" style="color:var(--blue)">vremenskem arhivu</a>. Ko bo naslednjič padel sneg, si zapišite datum in koliko dni je ležal: '
        'čez nekaj let boste imeli svoje podatke namesto spomina.',
    ]

    title = "So zime še kar so bile? Podatki in spomin"
    assert len(title) <= 60
    desc = (f"Ledenih dni je v Ljubljani za dve tretjini manj kot v letih 1981–2002, snega pa več kot polovico manj. "
            "Kaj to pomeni za otroke, ki poznajo samo današnje zime?")
    assert len(desc) <= 160, len(desc)
    lead = "</p>\n<p class=\"lead\">".join([
        f"Kratek odgovor: deloma drži. V Ljubljani je bilo v zimah {old_p} povprečno {num(lj[old_p]['ice'], 0)} ledenih dni (ves dan pod 0 °C), "
        f"v zadnjih desetih zimah pa {num(lj[new_p]['ice'], 0)}. Snežna odeja je v Ljubljani nekoč ležala povprečno {dni(round(d_old))} na zimo, zdaj {dni(round(d_new))}.",
        f"Spomin pa je pogosto lepši od povprečja: tudi med letoma 1995 in 2003 sta bili dve zimi z manj kot tremi tedni snega, osemdeseta pa so "
        "bila zadnje desetletje, ko je bila povprečna zima v Ljubljani hladnejša od 1 °C.",
        "Spodaj so podatki od leta 1901 naprej, odjuga po mesecih, sneg v Ljubljani in na Črnivcu, meritve v Rečici, nekaj psihologije spomina "
        "in predlogi, kako zimo približati otrokom, ki starih zim niso poznali.",
    ])
    sections = [
        {"label": "01 — mraz", "heading": "Mraza je manj, ledenih dni še posebej", "id": "mraz", "paragraphs": p1},
        {"label": "02 — sto let", "heading": "Sto dvajset let zim v Ljubljani", "id": "sto-let", "paragraphs": p_sto},
        {"label": "03 — odjuga", "heading": "Odjuga: več toplih dni, najbolj februarja", "id": "odjuga", "paragraphs": p_odjuga},
        {"label": "04 — sneg", "heading": "Sneg: krajši in manj zanesljiv", "id": "sneg", "paragraphs": p2},
        {"label": "05 — Rečica", "heading": "Kaj kaže postaja v Rečici?", "id": "recica", "paragraphs": p3},
        {"label": "06 — otroci", "heading": "Zima, ki je otrok ne pozna", "id": "otroci", "paragraphs": p4},
        {"label": "07 — starši in šole", "heading": "Kaj lahko naredimo starši, vrtci in šole?", "id": "starsi", "paragraphs": p_starsi},
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
        back=("/blog/", "← Vsi članki"), og_title="So zime\nše kar so bile?",
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
