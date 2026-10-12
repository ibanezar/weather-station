#!/usr/bin/env python3
"""
tools/generate_smrdljivci_post.py — »Smrdljivcev je čedalje več? Podatki in vreme« (11. 10. 2026).

Članek po vprašanju bralca. Vse številke v besedilu in grafih pridejo iz
data/inat-smrdljivci.json (tools/study_inat_smrdljivci.py); besedilo nič ne izmišlja in vsaka
številka je v grafu, tabeli ali viru (docs/slog-pisanja.md). Ko se podatki osvežijo, se osvežijo
tudi številke — vendar je članek posnetek na dan objave in se ne prepisuje samodejno.

Ročno napisan članek (ne samodejni generator): po objavi na `main` gre po CLAUDE.md skozi lekturo
(lektura.yml je od 2. 10. 2026 izklopljena — do ponovnega vklopa ostane pregled po slogovnem vodniku).

Usage:
    python3 tools/generate_smrdljivci_post.py [--wire] [--dry-run] [--force]
"""
import datetime
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
DATA = os.path.join(ROOT, "data", "inat-smrdljivci.json")
SLUG = "smrdljivci-inaturalist-vreme-1011"
NBSP = " "
CYAN, PURPLE = "#22d3ee", "#a78bfa"       # marmorirana smrdljivka, ostali smrdljivci (na vsej strani enako)
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
MONTHS = "jfmamjjasond"


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def big(n):
    return f"{int(n):,}".replace(",", NBSP)


def opaz(n):
    """število + oblika samostalnika »opažanje« (1 opažanje, 2 opažanji, 3–4 opažanja, 5+ opažanj)."""
    n = int(n)
    if n % 100 == 1:
        w = "opažanje"
    elif n % 100 == 2:
        w = "opažanji"
    elif n % 100 in (3, 4):
        w = "opažanja"
    else:
        w = "opažanj"
    return f"{n}{NBSP}{w}"


def per1000(a, b):
    return 1000 * a / b if b else 0.0


# ───────────────────────── grafi (inline SVG, brez knjižnic) ─────────────────────────

def nice_max(v):
    for top in (4, 6, 8, 12, 16, 20, 40, 60, 80, 100, 200, 400):
        if v <= top:
            return top
    return v


def bar_chart(items, color, aria, unit="", vfmt=lambda v: str(int(v)), labels=True, w=360, h=220,
              ymax=None):
    """items = [(oznaka, vrednost, opis za miško)]. Ena serija, ena barva; palice 4 px zaobljene na vrhu."""
    pl, pr, pt, pb = 34, 8, 20, 26
    iw, ih = w - pl - pr, h - pt - pb
    top = ymax or nice_max(max(v for _, v, _ in items) or 1)
    n = len(items)
    slot = iw / n
    bw = min(34, slot * 0.62)
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{aria}" xmlns="http://www.w3.org/2000/svg">']
    for i in range(5):
        v = top * i / 4
        y = pt + ih - ih * i / 4
        parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        lab = vfmt(v) if top < 10 else str(int(round(v)))
        parts.append(f'<text x="{pl - 6}" y="{y + 3.5:.1f}" text-anchor="end" font-size="10" fill="{MUTED}">{lab}</text>')
    for i, (lab, v, tip) in enumerate(items):
        cx = pl + slot * (i + 0.5)
        bh = ih * v / top if top else 0
        x0, y0 = cx - bw / 2, pt + ih - bh
        if bh > 0.5:
            r = min(4, bh)
            parts.append(f'<path d="M{x0:.1f},{pt + ih:.1f} V{y0 + r:.1f} Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f} '
                         f'H{x0 + bw - r:.1f} Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + r:.1f} V{pt + ih:.1f} Z" '
                         f'fill="{color}"><title>{tip}</title></path>')
        if labels:
            parts.append(f'<text x="{cx:.1f}" y="{y0 - 5:.1f}" text-anchor="middle" font-size="10.5" '
                         f'font-weight="600" fill="{INK}">{vfmt(v)}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{h - 8}" text-anchor="middle" font-size="10" fill="{MUTED}">{lab}</text>')
    parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{pt + ih}" y2="{pt + ih}" stroke="{MUTED}" stroke-opacity=".5"/>')
    parts.append("</svg>")
    return "".join(parts)


def grouped_chart(groups, series, aria, w=520, h=240):
    """groups = [oznaka skupine]; series = [(ime, barva, [vrednosti po skupinah])]; vrednosti z 2 decimalkama."""
    pl, pr, pt, pb = 40, 8, 24, 40
    iw, ih = w - pl - pr, h - pt - pb
    top = max(v for _, _, vs in series for v in vs) * 1.25
    top = max(0.4, round(top * 10 + 0.49) / 10)
    gslot = iw / len(groups)
    bw = min(44, gslot / (len(series) + 1.2))
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{aria}" xmlns="http://www.w3.org/2000/svg">']
    for i in range(5):
        v = top * i / 4
        y = pt + ih - ih * i / 4
        parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pl - 6}" y="{y + 3.5:.1f}" text-anchor="end" font-size="10" fill="{MUTED}">{num(v, 2)}</text>')
    for gi, g in enumerate(groups):
        gx = pl + gslot * (gi + 0.5)
        for si, (name, color, vs) in enumerate(series):
            v = vs[gi]
            x0 = gx + (si - len(series) / 2) * (bw + 4) + 2
            bh = ih * v / top
            y0 = pt + ih - bh
            r = min(4, bh)
            if bh > 0.5:
                parts.append(f'<path d="M{x0:.1f},{pt + ih:.1f} V{y0 + r:.1f} Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f} '
                             f'H{x0 + bw - r:.1f} Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + r:.1f} V{pt + ih:.1f} Z" '
                             f'fill="{color}"><title>{name}, {g}: {num(v, 2)} opažanja na dan</title></path>')
            parts.append(f'<text x="{x0 + bw / 2:.1f}" y="{y0 - 5:.1f}" text-anchor="middle" font-size="11" '
                         f'font-weight="600" fill="{INK}">{num(v, 2)}</text>')
        parts.append(f'<text x="{gx:.1f}" y="{h - 14}" text-anchor="middle" font-size="11" fill="{MUTED}">{g}</text>')
    parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{pt + ih}" y2="{pt + ih}" stroke="{MUTED}" stroke-opacity=".5"/>')
    parts.append("</svg>")
    return "".join(parts)


def legend(entries):
    return '<p class="sm-leg">' + " ".join(
        f'<span><i style="background:{c}"></i>{n}</span>' for n, c in entries) + "</p>"


STYLE = """<style>
.sm-gal-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}
.sm-gal-grid img{aspect-ratio:2/3;object-fit:cover}
.sm-fig{margin:1.4rem 0;padding:1rem 1rem .8rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px}
.sm-fig figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.6rem}
.sm-fig h3{font-family:'Space Grotesk',sans-serif;font-size:.95rem;margin:0 0 .4rem;color:var(--text)}
.sm-row{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:640px){.sm-row{grid-template-columns:1fr}}
.sm-fig svg{display:block;width:100%;height:auto}
.sm-leg{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-size:.85rem;color:var(--muted);margin:.2rem 0 .6rem}
.sm-leg i{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;margin-right:.4rem;vertical-align:-.1rem}
.sm-tbl{overflow-x:auto;max-width:100%;margin:1rem 0}
.sm-tbl table{border-collapse:collapse;width:100%;font-size:.86rem}
.sm-tbl th,.sm-tbl td{padding:.42rem .5rem;text-align:right;border-bottom:1px solid var(--border)}
.sm-tbl td{white-space:nowrap}
.sm-tbl th{vertical-align:bottom;line-height:1.3}
.sm-note{color:var(--muted);font-size:.82rem;line-height:1.5;margin:-.4rem 0 1.2rem}
.sm-tbl th:first-child,.sm-tbl td:first-child,.sm-tbl th:nth-child(2),.sm-tbl td:nth-child(2){text-align:left}
.sm-tbl thead th{color:var(--muted);font-weight:600;font-size:.76rem}
.sm-tbl tr.sm-now td{font-weight:700;background:rgba(34,211,238,.08)}
</style>"""

# Fotografije so Filipove (img/blog/<slug>/foto-N.jpg, 640 × 960, brez EXIF). Vrste je določil Filip (12. 10. 2026):
# 1 in 2 uhata rusonožka, 3 rjava usnjatka. Na nobeni ni marmorirana smrdljivka, o kateri piše članek.
PHOTOS = [
    ("foto-1.jpg", "Uhata rusonožka z oranžnim vrhom ščitka in črno-oranžnim robom zadka na zelenem listu, pogled od zgoraj."),
    ("foto-2.jpg", "Uhata rusonožka, prekrita z rosnimi kapljicami, na beli cvetni listič, pogled od spredaj."),
    ("foto-3.jpg", "Rjava usnjatka z dolgimi tipalnicami in rombastim zadkom na zelenem listu, pogled od zgoraj."),
]


def gallery_html():
    imgs = "".join(f'<img src="/img/blog/{SLUG}/{f}" alt="{alt}" width="640" height="960">' for f, alt in PHOTOS)
    return (STYLE + f'<figure class="post-photo sm-gal"><div class="sm-gal-grid">{imgs}</div>'
            '<figcaption>Uhata rusonožka (levo in v sredini) in rjava usnjatka (desno). Marmorirane smrdljivke, o kateri piše članek, na teh fotografijah ni. '
            'Foto: Filip Eremita.</figcaption></figure>')


def fig(title, inner, caption):
    return f'<figure class="sm-fig"><h3>{title}</h3>{inner}<figcaption>{caption}</figcaption></figure>'


def table(head, rows, now_label=None, cap="", note=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    body = ""
    for r in rows:
        cls = ' class="sm-now"' if now_label and r[0] == now_label else ""
        body += f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return f'<div class="sm-tbl" tabindex="0" role="region" aria-label="{cap}"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>' + (f'<p class="sm-note">{note}</p>' if note else "")


# ───────────────────────── članek ─────────────────────────

def build_article(D):
    last = D["last_year"]
    cut = D["cutoff"]                      # »10-10«
    cut_txt = f"{int(cut.split('-')[1])}. {int(cut.split('-')[0])}."
    ytd = {int(y): v for y, v in D["ytd"].items()}
    aut = {int(y): v for y, v in D["autumn"].items()}
    years = sorted(ytd)
    sy = {int(y): v for y, v in D["station_years"].items()}
    W = D["weather"]
    now_h = aut[last]["halys"]
    prev_h = aut[last - 1]["halys"]
    prev_max = max(aut[y]["halys"] for y in years if y < last)
    assert now_h >= prev_max, "Naslov in uvod trdita, da je letos največ opažanj — podatki tega ne kažejo."

    # --- razdelek 1: letno ---
    h_counts = [(str(y), ytd[y]["halys"], f"{y}: {opaz(ytd[y]['halys'])}") for y in years]
    h_share = [(str(y), per1000(ytd[y]["halys"], ytd[y]["insecta"]),
                f"{y}: {num(per1000(ytd[y]['halys'], ytd[y]['insecta']))} na 1000 opažanj žuželk") for y in years]
    peak_y = max(years, key=lambda y: per1000(ytd[y]["halys"], ytd[y]["insecta"]))
    pen_share = [100 * ytd[y]["penta"] / ytd[y]["insecta"] for y in years]
    ch1 = bar_chart(h_counts, CYAN, "Opažanja marmorirane smrdljivke v Sloveniji po letih, 1. januar do " + cut_txt,
                    w=360, h=230)
    ch2 = bar_chart(h_share, CYAN, "Marmorirana smrdljivka na 1000 opažanj žuželk po letih",
                    vfmt=lambda v: num(v), w=360, h=230)
    fig1 = fig("Marmorirana smrdljivka v Sloveniji, 1. 1.–" + cut_txt + " vsako leto",
               '<div class="sm-row"><div><p class="sm-leg">Število opažanj</p>' + ch1 + '</div>'
               '<div><p class="sm-leg">Na 1000 opažanj žuželk</p>' + ch2 + '</div></div>',
               f"Levo surovo število, desno delež med vsemi opažanji žuželk. Leto {last} je nepolno (do {cut_txt}); "
               f"vsa leta so primerjana na enako obdobje. Vir: iNaturalist.")
    rows1 = [(str(y), big(ytd[y]["vse"]), big(ytd[y]["insecta"]), str(ytd[y]["halys"]), big(ytd[y]["penta"]),
              num(per1000(ytd[y]["halys"], ytd[y]["insecta"])),
              num(100 * ytd[y]["penta"] / ytd[y]["insecta"]) + f"{NBSP}%") for y in years]
    tbl1 = table(["Leto", "Vsa opažanja", "Žuželke", "Marmo&shy;rirana", "Vsi smrdljivci", "Marm. na 1000 žuželk",
                  "Smrdljivci med žuželkami"], rows1, str(last), "Opažanja po letih")

    p1 = [
        "iNaturalist je zbirka opažanj, ki jih prostovoljci fotografirajo in objavijo, vrsto pa določi skupnost. "
        f"Dejavnost v Sloveniji hitro raste: vseh opažanj od 1. 1. do {cut_txt} je bilo leta {years[0]} skupaj "
        f"{big(ytd[years[0]]['vse'])}, letos pa {big(ytd[last]['vse'])}. Samo štetje smrdljivcev bi zato kazalo rast "
        "tudi tam, kjer je ni.",
        f"Zato sem za vsako leto vzel enako obdobje in marmorirano smrdljivko (<em>Halyomorpha halys</em>) primerjal z vsemi "
        f"opažanji žuželk. Surovo število opažanj je zraslo z {ytd[years[0]]['halys']} v letu {years[0]} na {ytd[last]['halys']} letos. "
        f"Na 1000 opažanj žuželk pa je bilo marmoriranih smrdljivk največ leta {peak_y} ({num(per1000(ytd[peak_y]['halys'], ytd[peak_y]['insecta']))}); "
        f"od tam se delež ni povečal (letos {num(per1000(ytd[last]['halys'], ytd[last]['insecta']))}).",
        fig1,
        f"Vsi smrdljivci skupaj (družina <em>Pentatomidae</em>) ostajajo okoli 2 % opažanj žuželk: med {num(min(pen_share[1:]))} in "
        f"{num(max(pen_share[1:]))} % v letih {years[1]}–{last}. Smrdljivcev je med fotografiranimi "
        "žuželkami torej enako kot pred leti.",
        tbl1,
    ]

    # --- razdelek 2: sezona ---
    mh, mo = D["month"]["halys"], D["month"]["ostali"]
    sh = [100 * v / sum(mh) for v in mh]
    so = [100 * v / sum(mo) for v in mo]
    mnames = ["januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober",
              "november", "december"]
    ph = max(range(12), key=lambda i: sh[i])
    po = max(range(12), key=lambda i: so[i])
    winter = [10, 11, 0, 1, 2]              # nov–mar
    wh = sum(sh[i] for i in winter)
    wo = sum(so[i] for i in winter)
    ymx = math.ceil(max(sh + so) / 4) * 4
    c3 = bar_chart([(MONTHS[i], sh[i], f"{mnames[i]}: {num(sh[i])} % vseh opažanj marmorirane smrdljivke") for i in range(12)],
                   CYAN, "Marmorirana smrdljivka: delež opažanj po mesecih", labels=False, w=360, h=200,
                   vfmt=lambda v: num(v), ymax=ymx)
    c4 = bar_chart([(MONTHS[i], so[i], f"{mnames[i]}: {num(so[i])} % vseh opažanj ostalih smrdljivcev") for i in range(12)],
                   PURPLE, "Ostali smrdljivci: delež opažanj po mesecih", labels=False, w=360, h=200,
                   vfmt=lambda v: num(v), ymax=ymx)
    fig2 = fig("Kdaj med letom jih fotografirajo (vsa leta, v %)",
               '<div class="sm-row"><div>' + legend([("Marmorirana smrdljivka", CYAN)]) + c3 + '</div><div>'
               + legend([("Ostali smrdljivci", PURPLE)]) + c4 + '</div></div>',
               f"Obe skupini imata isto lestvico. Višina palice je delež opažanj skupine v tistem mesecu "
               f"(marmorirana {big(sum(mh))}, ostali {big(sum(mo))} opažanj; vsa leta, ne glede na kakovost določitve). "
               "Oznake na osi so začetnice mesecev, od januarja do decembra.")
    loc = ["januarju", "februarju", "marcu", "aprilu", "maju", "juniju", "juliju", "avgustu", "septembru",
           "oktobru", "novembru", "decembru"]
    p2 = [
        f"Ostali smrdljivci imajo vrh opažanj v {loc[po]} ({num(so[po], 0)} %), marmorirana smrdljivka pa v {loc[ph]} "
        f"({num(sh[ph], 0)} %). V {loc[ph]} je delež ostalih smrdljivcev že precej nižji ({num(so[ph], 0)} %).",
        f"Še bolj zgovoren je zimski del: od novembra do marca je {num(wh, 0)} % opažanj marmorirane smrdljivke, pri ostalih "
        f"smrdljivcih le {num(wo, 0)} %. To je skladno s tem, da marmorirana smrdljivka jeseni pogosto poišče zavetje za "
        "prezimovanje v poslopjih (splošno znana lastnost vrste), vendar iz opažanj ni razvidno, kje je bila fotografirana.",
        fig2,
    ]

    # --- razdelek 3: vreme ---
    T15, T18 = W["thr"]["15"], W["thr"]["18"]

    def rate(g):
        return g["opaz"] / g["dni"]
    def block(T, key):
        return {"hladno": {"dni": T["hladno"]["dni"], "opaz": T["hladno"][key]},
                "toplo": {"dni": T["toplo"]["dni"], "opaz": T["toplo"][key]}}
    r = {}
    for thr, T in (("15", T15), ("18", T18)):
        for key in ("halys", "ostali"):
            b = block(T, key)
            r[(thr, key)] = {"c": rate(b["hladno"]), "w": rate(b["toplo"]), "cn": b["hladno"]["opaz"],
                              "wn": b["toplo"]["opaz"], "rr": T["rr_" + key]}
    g15 = grouped_chart(["pod 15 °C", "15 °C ali več"],
                        [("Marmorirana smrdljivka", CYAN, [r[("15", "halys")]["c"], r[("15", "halys")]["w"]]),
                         ("Ostali smrdljivci", PURPLE, [r[("15", "ostali")]["c"], r[("15", "ostali")]["w"]])],
                        "Opažanja na dan ob hladnejših in toplejših dneh, 1. oktober do 5. november")
    fig3 = fig("Opažanja na dan glede na najvišjo temperaturo dneva v Rečici (1. 10.–5. 11.)",
               legend([("Marmorirana smrdljivka", CYAN), ("Ostali smrdljivci", PURPLE)]) + g15,
               f"{W['n_days']} dni (2020–{last}), {opaz(W['n_obs_halys'])} marmorirane smrdljivke in "
               f"{opaz(W['n_obs_ostali'])} ostalih smrdljivcev. Vir: iNaturalist (raziskovalna kakovost, odprta lokacija), "
               "meritve postaje IREICA1.")

    def rr_txt(x):
        return f"{num(x['rr'])} ({num(x['lo'])}–{num(x['hi'])})"
    rows3 = []
    for thr in ("15", "18"):
        for key, name in (("halys", "Marmorirana"), ("ostali", "Ostali smrdljivci")):
            x = r[(thr, key)]
            rows3.append((f"{thr}{NBSP}°C", name, f"{num(x['c'], 2)} ({x['cn']})", f"{num(x['w'], 2)} ({x['wn']})", rr_txt(x["rr"])))
    tbl3 = table(["Prag", "Skupina", "Hladnejši dnevi", "Toplejši dnevi", "Razmerje"], rows3, None,
                 "Opažanja na dan glede na temperaturo",
                 "Opažanj na dan (v oklepaju skupno število); razmerje toplejši proti hladnejšim dnevom z 95 % intervalom.")
    hx, ox = r[("15", "halys")], r[("15", "ostali")]
    p3 = [
        f"Vreme pa pove, kdaj jih ljudje fotografirajo. Med 1. 10. in 5. 11. sem primerjal dneve glede na najvišjo temperaturo na postaji "
        f"IREICA1. Ob dnevih s 15 °C ali več je bilo na dan {num(hx['w'], 2)} opažanja marmorirane smrdljivke, ob hladnejših "
        f"{num(hx['c'], 2)}: to je {num(hx['rr']['rr'])}-krat pogosteje (95 % interval {num(hx['rr']['lo'])}–{num(hx['rr']['hi'])}).",
        f"Pri ostalih smrdljivcih zanesljive razlike ni: {num(ox['w'], 2)} proti {num(ox['c'], 2)} na dan; razmerje je {num(ox['rr']['rr'])}, "
        f"interval ({num(ox['rr']['lo'])}–{num(ox['rr']['hi'])}) pa vključuje 1. Isti vzorec se pokaže pri pragu 18 °C: "
        f"{num(r[('18', 'halys')]['rr']['rr'])}-krat pri marmorirani in {num(r[('18', 'ostali')]['rr']['rr'])}-krat pri ostalih.",
        fig3,
        "Ob toplih dneh ljudje fotografirajo več žuželk, zato sem ostale smrdljivce vzel za primerjavo: če bi šlo samo za to, "
        "bi se razlika pokazala pri obeh skupinah. Marmorirana smrdljivka je ob toplih jesenskih dneh opažena pogosteje, "
        "pri ostalih smrdljivcih te razlike ni. To je skladno z zbiranjem pred prezimovanjem, ki je za to vrsto znano, vendar je vzorec majhen: "
        f"ob hladnejših dneh je bilo samo {opaz(hx['cn'])}.",
        tbl3,
    ]

    # --- razdelek 4: letošnja jesen ---
    ys = [y for y in years if y in sy]
    rows4 = []
    for y in ys:
        rows4.append((str(y), num(sy[y].get("jesen_tmax", float("nan"))) + f"{NBSP}°C", big(sy[y]["gdd"]),
                      str(aut[y]["halys"]), str(aut[y]["halys_observers"]), big(aut[y]["insecta"]),
                      num(per1000(aut[y]["halys"], aut[y]["insecta"]))))
    tbl4 = table(["Leto", "Najvišja T", "Stop. dnevi", "Marmo&shy;rirana", "Opazo&shy;valcev", "Žuželke", "Na 1000 žuželk"],
                 rows4, str(last), "Jesensko okno po letih",
                 "Okno 15. 9.–10. 10.: povprečna najvišja dnevna temperatura, stopinjski dnevi apr–sep (nad 10 °C), opažanja "
                 "marmorirane smrdljivke in število opazovalcev, opažanja žuželk, marmorirana na 1000 žuželk.")
    prev = [y for y in ys if y < last]
    lo_p = min(per1000(aut[y]["halys"], aut[y]["insecta"]) for y in prev)
    hi_p = max(per1000(aut[y]["halys"], aut[y]["insecta"]) for y in prev)
    now_p = per1000(aut[last]["halys"], aut[last]["insecta"])
    warmer = sum(1 for y in prev if sy[y].get("jesen_tmax", 0) < sy[last].get("jesen_tmax", 0))
    warm_y = max(prev, key=lambda y: sy[y].get("jesen_tmax", 0))
    rho = D["spearman_gdd_halys_autumn"]
    gdd_max_y = max(ys, key=lambda y: sy[y]["gdd"])
    p4 = [
        f"Jesen {last} je v podatkih res izstopajoča. V obdobju 15. 9.–10. 10. je {opaz(now_h)} marmorirane "
        f"smrdljivke; lani jih je bilo {prev_h}" + (", kar je bilo doslej največ" if prev_h == prev_max
                                                     else f", največ pa {prev_max}") +
        f". Na 1000 opažanj žuželk je to {num(now_p)} proti {num(lo_p, 0)}–{num(hi_p, 0)} v letih {prev[0]}–{prev[-1]}.",
        f"Kaj je razlog? Letošnja jesen je bila toplejša (povprečna najvišja dnevna temperatura v tem obdobju {num(sy[last]['jesen_tmax'])} °C) kot "
        f"v {warmer} od {len(prev)} prejšnjih let. Leta {warm_y} je bilo še toplejše ({num(sy[warm_y]['jesen_tmax'])} °C), "
        f"opažanj marmorirane smrdljivke pa le {aut[warm_y]['halys']}. Vsota stopinjskih dni od aprila do septembra (seštevek, za koliko stopinj je bilo "
        f"povprečje dneva nad 10 °C) je bila največja leta {gdd_max_y}. Korelacija med njo in jesenskimi opažanji je pri "
        f"{rho['n']} letih {num(rho['rho'], 2)}, kar za kakršen koli sklep ne zadošča.",
        tbl4,
        f"Za letošnjih {now_h} opažanj stoji {aut[last]['halys_observers']} različnih opazovalcev; lani je bilo {prev_h} opažanj "
        f"in {aut[last - 1]['halys_observers']} opazovalcev. Povečanje torej ni v tem, da bi več ljudi fotografiralo smrdljivce, "
        "ampak v več opažanjih na opazovalca.",
        "Možni razlogi, ki jih iz teh podatkov ne morem ločiti: toplo poletje, topla jesen, večja pozornost posameznih ljudi "
        "do smrdljivcev in naključje majhnega vzorca. Več kot to, da je letošnja jesen v teh podatkih izstopajoča, ne morem trditi.",
    ]

    p5 = [
        "<ul>"
        "<li><strong>Opažanje ni štetje.</strong> iNaturalist pokaže, kje in kdaj je kdo fotografiral, ne koliko osebkov je bilo.</li>"
        "<li><strong>Hišni obiski so slabo pokriti.</strong> Smrdljivca na zavesi ljudje verjetno redko objavijo, zato iNaturalist "
        "hišne obiske najverjetneje podcenjuje.</li>"
        f"<li><strong>Majhni vzorci.</strong> V vremenskem oknu je samo {opaz(W['n_obs_halys'])} marmorirane smrdljivke.</li>"
        "<li><strong>Interval je optimističen.</strong> Opažanja istega opazovalca na isti dan niso neodvisna, pravi interval "
        "je širši od izračunanega.</li>"
        "<li><strong>Ena postaja, vsa Slovenija.</strong> Vreme v Rečici ob Savinji ni vreme vsepovsod, kjer so smrdljivce "
        "fotografirali.</li>"
        "</ul>",
        "<p style=\"margin-top:1rem\">Podatki so samo agregati; posameznih opažanj ne objavljam, ker imajo različne licence. Zbrane številke so v "
        f'<a href="/data/inat-smrdljivci.json" style="color:var(--blue)">data/inat-smrdljivci.json</a>.</p>',
    ]
    p6 = [
        'Če smrdljivca najdete doma ali na vrtu, ga lahko fotografirate in vnesete na '
        '<a href="https://www.inaturalist.org/" style="color:var(--blue)" rel="noopener">iNaturalist</a>: vsako opažanje z datumom '
        'in krajem v prihodnje izboljša takšne primerjave. Dnevne meritve postaje, ki sem jih uporabil, so v '
        f'<a href="{SITE}/vreme/" style="color:var(--blue)">vremenskem arhivu</a>.',
    ]

    title = "Smrdljivcev je čedalje več? Podatki in vreme"
    desc = (f"Marmoriranih smrdljivk je v opažanjih iNaturalist letos jeseni največ doslej, a čez leto njihov delež ne raste. "
            f"Ob toplih jesenskih dneh so pogosteje opažene.")
    lead = (f"Kratek odgovor: deloma drži. Med 15. 9. in 10. 10. je na iNaturalist za Slovenijo {opaz(now_h)} marmorirane smrdljivke, "
            f"največ doslej; lani jih je bilo {prev_h}. Čez vse leto njihov delež med opažanji žuželk ne raste, ob toplih "
            "jesenskih dneh pa so marmorirane smrdljivke opažene pogosteje, drugi smrdljivci pa ne.")
    sections = [
        {"label": "01 — opažanja", "heading": "Koliko jih je res?", "id": "opazanja", "paragraphs": p1},
        {"label": "02 — sezona", "heading": "Zakaj ravno jeseni?", "id": "sezona", "paragraphs": p2},
        {"label": "03 — vreme", "heading": "Kdaj jih fotografirajo: topli dnevi", "id": "vreme", "paragraphs": p3},
        {"label": "04 — letos", "heading": "Je letošnja jesen izjemna?", "id": "letos", "paragraphs": p4},
        {"label": "05 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": p5},
        {"label": "06 — kaj lahko storite", "heading": "Vnesite opažanje", "id": "opazanje", "paragraphs": p6},
    ]
    return {
        "title": title, "meta_description": desc,
        "tags": ["smrdljivci", "iNaturalist", "jesen", "podatki", str(last)],
        "section_label": "Podatkovna analiza", "og_photo": "weather-station", "og_accent_hex": "#22d3ee",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": (f"Viri: iNaturalist (API, opažanja v Sloveniji, stanje {D['generated'][8:10].lstrip('0')}. "
                         f"{int(D['generated'][5:7])}. {D['generated'][:4]}), meritve postaje IREICA1 (Meteorec). "
                         "Podatki: /data/inat-smrdljivci.json."),
    }


def main():
    wire = "--wire" in sys.argv
    dry = "--dry-run" in sys.argv
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
    from generate_daily_post import call_lektor
    final = article
    if os.environ.get("ANTHROPIC_API_KEY"):
        review = call_lektor(article, {"tema": "smrdljivci in vreme"})
        for i in review.get("issues") or []:
            print(f"  lektor: {i}")
        final = review.get("corrected") or article
    else:
        print("  ⚠ ANTHROPIC_API_KEY ni nastavljen -- lektura preskočena.")

    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    # Posodobitev že objavljenega članka (--force): izvirni datum objave ostane, osveži se samo dateModified
    # in polje `updated` v blog.json (touch_existing). Nov članek: današnji datum.
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    pub = re.search(r'"datePublished": "([^"]+)"', old) if old else None
    posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    prev_entry = next((e for e in posts if e.get("slug") == SLUG), None)
    ftp.TODAY = prev_entry["date"] if prev_entry else today.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        final, today.year, today.month, now_utc, slug=SLUG,
        back=("/blog/", "← Vsi članki"), og_title="Smrdljivci\njeseni " + str(today.year),
        meta_note="podatkovna analiza", nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{final["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev galerije"
    html = html.replace(lead, lead + "\n" + gallery_html(), 1)
    if pub:
        iso = now_utc.isoformat()
        html = html.replace(f'"datePublished": "{iso}"', f'"datePublished": "{pub.group(1)}"')
        html = html.replace(f'<meta property="article:published_time" content="{iso}">',
                            f'<meta property="article:published_time" content="{pub.group(1)}">')
        html = re.sub(r'("dateModified":\s*")[^"]*(")', rf'\g<1>{today.isoformat()}\g<2>', html, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html" + (" (posodobitev)" if pub else ""))
    if wire:
        if "--og-photo" in sys.argv:       # original v polni ločljivosti; v repozitorij gre samo 640 × 960
            os.environ["DRIVE_PHOTO_PATH"] = sys.argv[sys.argv.index("--og-photo") + 1]
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
        if prev_entry:
            from generate_monthly_post import touch_existing
            touch_existing(SLUG, wire=True)
        else:
            from generate_monthly_post import wire_all
            wire_all(entry, entry["url"])
            print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
