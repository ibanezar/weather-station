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
    """tisočice s piko od 10.000 naprej (5439, 14.353) — kot v lektoriranem besedilu."""
    n = int(n)
    return f"{n:,}".replace(",", ".") if n >= 10000 else str(n)


_NOM = ["nič", "ena", "dve", "tri", "štiri", "pet", "šest", "sedem", "osem", "devet", "deset", "enajst", "dvanajst"]
_GEN = ["nič", "ene", "dveh", "treh", "štirih", "petih", "šestih", "sedmih", "osmih", "devetih", "desetih",
        "enajstih", "dvanajstih"]


def numw(n):
    """števnik z besedo do 12 (imenovalnik), sicer številka."""
    n = int(n)
    return _NOM[n] if 2 <= n <= 12 else str(n)


def numg(n):
    """števnik z besedo do 12 (rodilnik/mestnik: z dveh, v petih), sicer številka."""
    n = int(n)
    return _GEN[n] if 2 <= n <= 12 else str(n)


def opazw(n):
    """kot opaz(), a z besedo do 12 (srednji spol: dve opažanji, tri opažanja, pet opažanj)."""
    n = int(n)
    return opaz(n).replace(str(n), numw(n), 1) if 2 <= n <= 12 else opaz(n)


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


SRC = {
    "ivr": "https://www.ivr.si/skodljivec/marmorirana-smrdljivka/",
    "bf": "https://www.ivr.si/app/uploads/2024/02/Strokovna-priporocila-za-obvladovanje-marmorirane-smrdljivke-s-CIPom-9.2.2024.pdf",
    "n1": "https://n1info.si/novice/slovenija/zakaj-je-spet-toliko-smrdljivcev-in-ali-jih-je-res-najbolje-kar-posesati/",
    "umd": "https://extension.umd.edu/resource/tips-dealing-brown-marmorated-stink-bugs",
    "krsko": "https://www.vsezamojdan.si/krsko-smrdljivci-smrdljivke-projekt-rezultati/",
}


def a(key, text):
    return f'<a href="{SRC[key]}" style="color:var(--blue)" rel="noopener">{text}</a>'


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
h3.sm-h3,.post-body h3{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;margin:1.6rem 0 .4rem}
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
            '<figcaption>Uhata rusonožka (levo in na sredini) ter rjava usnjatka (desno). Marmorirana smrdljivka, o kateri govori članek, na fotografijah ni prikazana. '
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
    assert cut == "10-10", "besedilo ima datum zaustavitve zapisan z besedo"
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
               f"Levo je prikazano surovo število opažanj, desno pa delež med vsemi opažanji žuželk. Podatki za leto {last} so "
               f"nepopolni in segajo do 10. oktobra. Za vsa leta je uporabljeno enako obdobje. Vir: iNaturalist.")
    rows1 = [(str(y), big(ytd[y]["vse"]), big(ytd[y]["insecta"]), str(ytd[y]["halys"]), big(ytd[y]["penta"]),
              num(per1000(ytd[y]["halys"], ytd[y]["insecta"])),
              num(100 * ytd[y]["penta"] / ytd[y]["insecta"]) + f"{NBSP}%") for y in years]
    tbl1 = table(["Leto", "Vsa opažanja", "Žuželke", "Marmo&shy;rirana smrdljivka", "Vsi smrdljivci", "Marmo&shy;rirana na 1000 žuželk",
                  "Smrdljivci med žuželkami"], rows1, str(last), "Opažanja po letih")

    p1 = [
        "iNaturalist je zbirka opažanj, v katero uporabniki nalagajo fotografije rastlin, živali in drugih organizmov. Vrste "
        "določajo sami opazovalci in skupnost.",
        f"Število opažanj v Sloveniji hitro narašča. Med 1. januarjem in {cut_txt.replace('10. 10.', '10. oktobrom')} jih je bilo leta {years[0]} "
        f"skupaj {big(ytd[years[0]]['vse'])}, letos pa že {big(ytd[last]['vse'])}. Samo s štetjem opažanj smrdljivk bi zato lahko "
        "napačno sklepali, da jih je vse več, tudi če gre v resnici zgolj za večjo dejavnost opazovalcev.",
        "Da bi zmanjšal vpliv te razlike, sem za vsako leto uporabil enako obdobje in marmorirano smrdljivko "
        "(<em>Halyomorpha halys</em>) primerjal z vsemi opažanji žuželk.",
        f"Surovo število opažanj marmorirane smrdljivke se je povečalo z {numg(ytd[years[0]]['halys'])} leta {years[0]} na "
        f"{ytd[last]['halys']} letos. Toda na 1000 opažanj žuželk jih je bilo največ leta {peak_y}, in sicer "
        f"{num(per1000(ytd[peak_y]['halys'], ytd[peak_y]['insecta']))}. Od takrat se delež ni povečal; letos znaša "
        f"{num(per1000(ytd[last]['halys'], ytd[last]['insecta']))}.",
        fig1,
        f"Tudi vsi smrdljivci skupaj (družina <em>Pentatomidae</em>) predstavljajo približno enak delež opažanj žuželk kot v "
        f"prejšnjih letih. Med letoma {years[1]} in {last} je ta delež nihal med {num(min(pen_share[1:]))} in "
        f"{num(max(pen_share[1:]))} %.",
        "Med fotografiranimi žuželkami torej ni videti jasnega dolgoročnega naraščanja deleža smrdljivcev.",
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
    c4 = bar_chart([(MONTHS[i], so[i], f"{mnames[i]}: {num(so[i])} % vseh opažanj drugih smrdljivcev") for i in range(12)],
                   PURPLE, "Drugi smrdljivci: delež opažanj po mesecih", labels=False, w=360, h=200,
                   vfmt=lambda v: num(v), ymax=ymx)
    fig2 = fig("Kdaj med letom jih fotografirajo (vsa leta, v %)",
               '<div class="sm-row"><div>' + legend([("Marmorirana smrdljivka", CYAN)]) + c3 + '</div><div>'
               + legend([("Drugi smrdljivci", PURPLE)]) + c4 + '</div></div>',
               f"Obe skupini sta prikazani na isti lestvici. Višina stolpca pomeni delež vseh opažanj posamezne skupine, zabeleženih v "
               f"tistem mesecu. Za marmorirano smrdljivko je bilo skupaj {big(sum(mh))} opažanj, za druge smrdljivce pa {big(sum(mo))}. "
               "Upoštevana so vsa leta, ne glede na kakovost določitve vrste. Oznake na osi so začetnice mesecev od januarja do decembra.")
    mgen = ["januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra",
            "oktobra", "novembra", "decembra"]
    assert po < ph
    p2 = [
        f"Pri drugih smrdljivcih je največ opažanj zabeleženih {mgen[po]}, ko jih je {num(so[po], 0)} % vseh opažanj te skupine. "
        f"Pri marmorirani smrdljivki je vrhunec pozneje, {mgen[ph]}, ko je zabeleženih {num(sh[ph], 0)} % opažanj. "
        f"{mgen[ph].capitalize()} delež opažanj drugih smrdljivcev že precej upade, na {num(so[ph], 0)} %.",
        f"Zanimiv je tudi zimski del leta. Od novembra do marca je {num(wh, 0)} % opažanj marmorirane smrdljivke, pri drugih "
        f"smrdljivcih pa le {num(wo, 0)} %.",
        "To se ujema z znanim vedenjem marmorirane smrdljivke, ki jeseni pogosto išče zavetje za prezimovanje v stavbah. Tako "
        "vedenje opisujejo tudi " + a("bf", "strokovna priporočila Biotehniške fakultete") + ". Iz podatkov iNaturalist pa ne "
        "moremo razbrati, ali je bila posamezna smrdljivka fotografirana v hiši, na vrtu ali v naravi.",
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
                         ("Drugi smrdljivci", PURPLE, [r[("15", "ostali")]["c"], r[("15", "ostali")]["w"]])],
                        "Opažanja na dan ob hladnejših in toplejših dneh, 1. oktober do 5. november")
    fig3 = fig("Opažanja na dan glede na najvišjo temperaturo dneva v Rečici (1. 10.–5. 11.)",
               legend([("Marmorirana smrdljivka", CYAN), ("Drugi smrdljivci", PURPLE)]) + g15,
               f"Analiza zajema {W['n_days']} dni v obdobju 2020–{last}, {opaz(W['n_obs_halys'])} marmorirane smrdljivke in "
               f"{opaz(W['n_obs_ostali'])} drugih smrdljivcev. Viri: iNaturalist (opažanja raziskovalne kakovosti z odprto "
               "lokacijo) in meritve postaje IREICA1.")

    def rr_txt(x):
        return f"{num(x['rr'])} ({num(x['lo'])}–{num(x['hi'])})"
    rows3 = []
    for thr in ("15", "18"):
        for key, name in (("halys", "Marmorirana"), ("ostali", "Drugi smrdljivci")):
            x = r[(thr, key)]
            rows3.append((f"{thr}{NBSP}°C", name, f"{num(x['c'], 2)} ({x['cn']})", f"{num(x['w'], 2)} ({x['wn']})", rr_txt(x["rr"])))
    tbl3 = table(["Prag", "Skupina", "Hladnejši dnevi", "Toplejši dnevi", "Razmerje"], rows3, None,
                 "Opažanja na dan glede na temperaturo",
                 "Številke prikazujejo povprečno število opažanj na dan, v oklepajih pa je skupno število opažanj. Razmerje primerja "
                 "toplejše in hladnejše dni; v oklepaju je 95-odstotni interval zaupanja.")
    hx, ox = r[("15", "halys")], r[("15", "ostali")]
    assert ox["rr"]["lo"] < 1 < ox["rr"]["hi"] and hx["cn"] >= 5
    o18 = r[("18", "ostali")]["rr"]
    assert o18["lo"] < 1 < o18["hi"]
    p3 = [
        "Vreme lahko pomaga pojasniti, kdaj ljudje smrdljivke pogosteje opazijo in fotografirajo.",
        f"Za obdobje od 1. oktobra do 5. novembra sem dneve razdelil glede na najvišjo dnevno temperaturo, izmerjeno na postaji "
        f"IREICA1. Ob dnevih, ko je temperatura dosegla vsaj 15 °C, je bilo v povprečju {num(hx['w'], 2)} opažanja marmorirane "
        f"smrdljivke na dan. Ob hladnejših dneh jih je bilo {num(hx['c'], 2)}. To pomeni, da so jo ob toplejših dneh zabeležili "
        f"{num(hx['rr']['rr'])}-krat pogosteje. 95-odstotni interval ocene razmerja je od {num(hx['rr']['lo'])} do {num(hx['rr']['hi'])}.",
        f"Pri drugih smrdljivcih zanesljive razlike ni bilo: ob hladnejših dneh je bilo povprečje {num(ox['c'], 2)} opažanja na dan, "
        f"ob toplejših pa {num(ox['w'], 2)}. Razmerje {num(ox['rr']['rr'])} ima interval od {num(ox['rr']['lo'])} do "
        f"{num(ox['rr']['hi'])}, ki vključuje tudi vrednost 1, zato razlika ni statistično prepričljiva.",
        f"Podoben vzorec dobimo, če kot mejo uporabimo 18 °C. Pri marmorirani smrdljivki je bilo opažanj na toplejše dni "
        f"{num(r[('18', 'halys')]['rr']['rr'])}-krat več, pri drugih smrdljivcih pa izrazite razlike ni bilo.",
        fig3,
        "Ob toplejših dneh ljudje praviloma opazijo in fotografirajo več žuželk. Zato sem druge smrdljivce uporabil kot "
        "primerjalno skupino: če bi bila razlika zgolj posledica večje dejavnosti opazovalcev ob toplejšem vremenu, bi "
        "pričakovali podoben vzorec pri obeh skupinah.",
        "Podatki kažejo, da je marmorirana smrdljivka ob toplih jesenskih dneh opažena pogosteje, pri drugih smrdljivcih pa "
        "takšne razlike ni. To je skladno z možnostjo, da se marmorirane smrdljivke v toplejšem vremenu pogosteje zbirajo pred "
        f"prezimovanjem. Vendar je vzorec majhen: ob hladnejših dneh je bilo zabeleženih le {opazw(hx['cn'])} marmorirane smrdljivke.",
        tbl3,
    ]

    # --- razdelek 4: letošnja jesen ---
    ys = [y for y in years if y in sy]
    rows4 = []
    for y in ys:
        rows4.append((str(y), num(sy[y].get("jesen_tmax", float("nan"))) + f"{NBSP}°C", big(sy[y]["gdd"]),
                      str(aut[y]["halys"]), str(aut[y]["halys_observers"]), big(aut[y]["insecta"]),
                      num(per1000(aut[y]["halys"], aut[y]["insecta"]))))
    tbl4 = table(["Leto", "Povpr. najvišja T", "Stopinjski dnevi", "Marmo&shy;rirana smrdljivka", "Opazo&shy;valci", "Opažanja žuželk", "Marmo&shy;rirana na 1000 žuželk"],
                 rows4, str(last), "Jesensko okno po letih",
                 "Obdobje 15. 9.–10. 10. Povprečna najvišja dnevna temperatura, stopinjski dnevi od aprila do septembra (nad 10 °C), "
                 "opažanja marmorirane smrdljivke, število opazovalcev, število opažanj žuželk in število opažanj marmorirane "
                 "smrdljivke na 1000 opažanj žuželk.")
    prev = [y for y in ys if y < last]
    lo_p = min(per1000(aut[y]["halys"], aut[y]["insecta"]) for y in prev)
    hi_p = max(per1000(aut[y]["halys"], aut[y]["insecta"]) for y in prev)
    now_p = per1000(aut[last]["halys"], aut[last]["insecta"])
    warmer = sum(1 for y in prev if sy[y].get("jesen_tmax", 0) < sy[last].get("jesen_tmax", 0))
    warm_y = max(prev, key=lambda y: sy[y].get("jesen_tmax", 0))
    rho = D["spearman_gdd_halys_autumn"]
    gdd_max_y = max(ys, key=lambda y: sy[y]["gdd"])
    assert D["autumn_window"] == ["09-15", "10-10"]
    p4 = [
        f"V podatkih za letošnjo jesen je marmorirana smrdljivka res izstopala. Med 15. septembrom in 10. oktobrom je bilo "
        f"zabeleženih {opaz(now_h)}, lani pa {numw(prev_h)}" + (", kar je bilo do tedaj največ" if prev_h == prev_max
                                                              else f", največ pa {numw(prev_max)}") +
        f". Na 1000 opažanj žuželk to pomeni {num(now_p)} opažanja marmorirane smrdljivke, medtem ko so bile vrednosti v istem "
        f"obdobju v letih {prev[0]}–{prev[-1]} med {num(lo_p, 0)} in {num(hi_p, 0)}.",
        f"Kaj je razlog? Letošnja jesen je bila v tem obdobju toplejša kot v {numg(warmer)} od {numg(len(prev))} predhodnih let. "
        f"Povprečna najvišja dnevna temperatura je znašala {num(sy[last]['jesen_tmax'])} °C. Leta {warm_y} je bilo še topleje, "
        f"s povprečjem {num(sy[warm_y]['jesen_tmax'])} °C, vendar so bila takrat zabeležena le {opazw(aut[warm_y]['halys'])} "
        "marmorirane smrdljivke.",
        f"Tudi vsota stopinjskih dni od aprila do septembra je bila leta {gdd_max_y} največja. Gre za seštevek dnevnih vrednosti, "
        "ki kaže, za koliko je povprečna dnevna temperatura presegla izhodiščno mejo 10 °C.",
        f"Korelacija med to vsoto in jesenskim številom opažanj je pri {numg(rho['n'])} letih znašala {num(rho['rho'], 2)}. "
        "To je premalo, da bi lahko na podlagi teh podatkov sklepali o zanesljivi povezavi.",
        tbl4,
        f"Za letošnjih {now_h} opažanj je zaslužnih {numg(aut[last]['halys_observers'])} različnih opazovalcev. "
        + (f"Tudi lani je bilo {numw(aut[last - 1]['halys_observers'])} opazovalcev, čeprav so skupaj zabeležili {numw(prev_h)} opažanj. "
           if aut[last - 1]["halys_observers"] == aut[last]["halys_observers"]
           else f"Lani je bilo opazovalcev {numw(aut[last - 1]['halys_observers'])}, opažanj pa {numw(prev_h)}. ") +
        "Povečanje torej ni posledica tega, da bi letos smrdljivke fotografiralo več ljudi, temveč tega, da so posamezni "
        "opazovalci zabeležili več opažanj.",
        "Slovenski strokovnjaki za varstvo rastlin omenjajo ugodne vremenske razmere kot enega od možnih razlogov za širjenje "
        "vrste. Po poročanju " + a("n1", "N1") + " z dne 14. oktobra 2025 je večina vprašanih strokovnjakov menila, da so "
        "vremenske razmere prispevale k njenemu širjenju. Jeseni se smrdljivke selijo tudi v urbana okolja, zlasti na sončna "
        "in toplejša mesta (tako N1).",
        a("bf", "Biotehniška fakulteta") + " dodaja, da je vrsta precej odporna proti nizkim temperaturam, vendar je njeno "
        "preživetje pozimi močno odvisno od temperaturnih razmer. To so strokovne ocene, ki jih naši podatki ne potrjujejo in "
        "ne ovržejo.",
        "Iz teh podatkov ne morem ločiti več možnih razlag: vpliva toplega poletja, tople jeseni, večje pozornosti posameznih "
        "opazovalcev ali preprostega naključja pri majhnem vzorcu. Zanesljivo lahko rečem le, da letošnja jesen v teh podatkih izstopa.",
    ]

    p5 = [
        "<ul>"
        "<li><strong>Opažanja niso štetje osebkov.</strong> iNaturalist pokaže, kje in kdaj je nekdo fotografiral smrdljivko, "
        "ne pa, koliko osebkov je bilo dejansko prisotnih.</li>"
        "<li><strong>Opažanja iz hiš so slabo zajeta.</strong> Smrdljivko na zavesi ljudje verjetno redkeje objavijo, zato "
        "iNaturalist obiske smrdljivk v domovih najverjetneje podcenjuje.</li>"
        f"<li><strong>Vzorec je majhen.</strong> V vremenski analizi je le {opaz(W['n_obs_halys'])} marmorirane smrdljivke.</li>"
        "<li><strong>Intervali negotovosti so lahko preozki.</strong> Opažanja istega opazovalca na isti dan niso neodvisna, "
        "zato je dejanska negotovost večja od izračunane.</li>"
        "<li><strong>Ena postaja ne predstavlja vse Slovenije.</strong> Vreme v Rečici ob Savinji ni nujno enako vremenu na "
        "vseh območjih, kjer so smrdljivke fotografirali.</li>"
        "</ul>",
        "<p style=\"margin-top:1rem\">V članku so uporabljeni le združeni podatki. Posameznih opažanj ne objavljam, ker zanje "
        "veljajo različni licenčni pogoji. Zbrane številke so shranjene v "
        '<a href="/data/inat-smrdljivci.json" style="color:var(--blue)">data/inat-smrdljivci.json</a>.</p>',
    ]
    p_znebiti = [
        "Popolne rešitve ni. Strokovnjaki Biotehniške fakultete marmorirano smrdljivko opisujejo kot trdovratnega škodljivca, "
        "ki ga je težko učinkovito obvladovati tudi s fitofarmacevtskimi sredstvi.",
        "Realističen cilj je zato zmanjšati število smrdljivk v hiši in na vrtu, ne pa pričakovati, da bomo vrsto iz okolja "
        "iztrebili. V nadaljevanju povzemam priporočila iz navedenih virov. Podatkov o učinkovitosti posameznih ukrepov nimam, "
        "zato jih ne predstavljam kot zagotovljene rešitve.",
        "<h3>1. Pred njihovim prihodom preprečite vstop</h3>",
        "Po strokovnih priporočilih " + a("bf", "Biotehniške fakultete") + " se odrasle marmorirane smrdljivke pred prezimovanjem "
        "ne parijo, septembra pa se začnejo zbirati in iskati zavetje v hišah, vrtnih lopah ter razpokah v lubju.",
        "Ameriški univerzitetni svetovalci mehansko preprečevanje vstopa opisujejo kot najboljši ukrep. Zatesnite razpoke okoli "
        "oken, vrat, fasadnih oblog in cevi, pa tudi odprtine za dimnikom in pod čelnimi deskami. Uporabite kakovosten silikonski "
        "ali silikonsko-lateksni kit. Poškodovane komarnike popravite ali zamenjajte.",
        "Novogoriška svetovalka za varstvo rastlin priporoča uporabo komarnikov ali podobnih mrež.",
        "Ker se smrdljivke začnejo zbirati že septembra, je smiselno odprtine zatesniti še pred začetkom njihovega jesenskega "
        "iskanja zavetja. To je moj sklep na podlagi opisanega vedenja vrste, ne neposredno priporočilo navedenega vira.",
        "<h3>2. Če so že v hiši, jih posesajte ali ujemite – ne stiskajte</h3>",
        "Večina slovenskih strokovnjakov, ki jih je vprašal " + a("n1", "N1") + ", priporoča, da smrdljivke posesate ali pometete, "
        "jih ujamete v vrečko in zavržete ali pa jih ujamete v posodo z vodo in detergentom.",
        a("umd", "University of Maryland Extension") + " svetuje, da vsebino sesalnika izpraznite v posodo z milnico. Na cev "
        "sesalnika lahko namestite tudi nogavico, ki smrdljivke ujame, še preden dosežejo zbiralnik.",
        "Ne stiskajte jih, saj lahko ob občutku ogroženosti ali stiskanju izločijo močan in neprijeten vonj.",
        "<h3>3. Insekticidi in pasti: priporočila so zadržana</h3>",
        "University of Maryland Extension uporabe pesticidov v hiši in okoli nje na splošno ne priporoča. Meglilniki ne uničijo "
        "vseh smrdljivk, prav tako ne preprečijo vstopa novih osebkov.",
        "Tudi slovenski strokovnjaki so pri uporabi insekticidov proti odraslim smrdljivkam in pri pasteh večinoma zadržani, "
        "zlasti v kmetijskem okolju. Insekticidi so lahko slabo učinkoviti, pasti pa po oceni celjske svetovalke za varstvo "
        "rastlin ne zagotavljajo zadovoljivega učinka.",
        "Eden od strokovnjakov, ki jih je vprašal N1, dopušča uporabo pršil proti žuželkam na prostem, na primer na dvorišču, "
        "ne pa na zaprtem balkonu.",
        "Pri uporabi fitofarmacevtskih sredstev na vrtu vedno upoštevajte navodila na etiketi in informacije na portalu FITO-INFO.",
        "<h3>4. Na vrtu pomagajo mreže in pregledovanje listov</h3>",
        "Po podatkih portala " + a("ivr", "IVR") + " so protiinsektne mreže eden najučinkovitejših in okoljsko sprejemljivih ukrepov. "
        "V sadovnjakih jih namestijo kmalu po cvetenju.",
        "Uporaba takšnih mrež na domačem vrtu je prenos priporočil iz kmetijske prakse, ne neposredno preverjeno navodilo za "
        "vsako vrsto vrta.",
        "Samice marmorirane smrdljivke odlagajo jajčna legla s približno 20–30 jajčeci na spodnjo stran listov, predvsem od "
        "sredine junija do konca septembra. Zato je smiselno občasno pregledati tudi spodnjo stran listov. Tudi to je moj "
        "praktičen sklep iz podatkov o razmnoževanju vrste.",
        "<h3>5. Naravni sovražniki delujejo počasi in niso rešitev za dom</h3>",
        "Parazitske osice, ki odlagajo jajčeca v jajčeca smrdljivk, portal IVR opisuje kot pomembne naravne sovražnike. Med "
        "domorodnimi vrstami sta <em>Anastatus bifasciatus</em> in <em>Trissolcus basalis</em>.",
        "Samurajska osa (<em>Trissolcus japonicus</em>) je v Aziji zelo učinkovit naravni sovražnik marmorirane smrdljivke. "
        "Uporabljajo jo tudi v programih biotičnega varstva v Severni Ameriki in Italiji.",
        "V Krškem od leta 2025 poteka projekt z osico <em>Anastatus bifasciatus</em>, ki naj bi trajal do leta 2029. V prvem "
        "letu so izmerili 28 % parazitiranih jajčec marmorirane smrdljivke, pri zeleni smrdljivki pa 85 %. Dolgoročnega "
        "učinka projekta še ni mogoče oceniti.",
        "Vnos osic poteka strokovno in nadzorovano, zato to ni ukrep za domačo uporabo.",
        "<h3>6. Kaj lahko pričakujete?</h3>",
        "Marmorirane smrdljivke se dobro premikajo, zato noben posamezen ukrep ne zagotavlja, da se ne bodo pojavile. Po oceni "
        "novogoriške svetovalke za varstvo rastlin pa se z osebkom, ki ga odstranite iz hiše jeseni, spomladi ne boste srečali znova.",
    ]
    p_viri = [
        "<ul>"
        "<li>" + a("ivr", "Marmorirana smrdljivka") + ", portal IVR (Modic, Žigon, Devetak, Jančar, Hoblaj; marec 2023).</li>"
        "<li>" + a("bf", "Strokovna priporočila za obvladovanje marmorirane smrdljivke") + ", Univerza v Ljubljani, Biotehniška "
        "fakulteta (Lešnik, Rot, Batistič, Vidrih, Bohinc, Godeša, Trdan; 2024).</li>"
        "<li>" + a("n1", "Zakaj je spet toliko smrdljivcev in ali jih je res najbolje kar posesati?") + ", N1 (Kamenarič, 14. 10. 2025).</li>"
        "<li>" + a("umd", "Tips for Dealing With Brown Marmorated Stink Bugs") + ", University of Maryland Extension (2021). "
        "Ameriška priporočila, ne slovenska.</li>"
        "<li>" + a("krsko", "Krško: projekt obvladovanja smrdljivcev") + ", Vse za moj dan (24. 5. 2026).</li>"
        "</ul>",
    ]
    p6 = [
        'Če marmorirano smrdljivko najdete doma ali na vrtu, jo lahko fotografirate in opažanje vnesete na '
        '<a href="https://www.inaturalist.org/" style="color:var(--blue)" rel="noopener">iNaturalist</a>. Vsako opažanje z datumom '
        'in krajem lahko pomaga izboljšati prihodnje primerjave.',
        f'Dnevne meritve vremenske postaje, uporabljene v članku, so na voljo v '
        f'<a href="{SITE}/vreme/" style="color:var(--blue)">vremenskem arhivu</a>.',
    ]

    title = "Smrdljivcev je čedalje več? Podatki in vreme"
    desc = ("Opažanj marmorirane smrdljivke je jeseni več kot prej, a njen delež med opažanji žuželk ne narašča. "
            "Ob toplih dneh jo ljudje pogosteje opazijo.")
    assert len(desc) <= 160, len(desc)
    lead = "</p>\n<p class=\"lead\">".join([
        f"Kratek odgovor: deloma drži. Med 15. septembrom in 10. oktobrom je bilo na iNaturalist v Sloveniji zabeleženih "
        f"{opaz(now_h)} marmorirane smrdljivke, največ doslej za to obdobje. Lani jih je bilo {numw(prev_h)}.",
        "Toda če pogledamo vse leto, delež marmoriranih smrdljivk med opažanji žuželk ne narašča. Ob toplih jesenskih dneh "
        "jih ljudje sicer pogosteje opazijo, pri drugih smrdljivcih pa se enak vzorec ne pokaže.",
        'Kako zmanjšati število smrdljivk v hiši in na vrtu, pojasnjujem v <a href="#znebiti" style="color:var(--blue)">6. razdelku</a>.'])
    sections = [
        {"label": "01 — opažanja", "heading": "Koliko jih je res?", "id": "opazanja", "paragraphs": p1},
        {"label": "02 — sezona", "heading": "Zakaj ravno jeseni?", "id": "sezona", "paragraphs": p2},
        {"label": "03 — vreme", "heading": "Kdaj jih fotografirajo? Ob toplih dneh", "id": "vreme", "paragraphs": p3},
        {"label": "04 — letos", "heading": "Je letošnja jesen izjemna?", "id": "letos", "paragraphs": p4},
        {"label": "05 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": p5},
        {"label": "06 — zmanjšanje", "heading": "Kako se jih znebiti?", "id": "znebiti", "paragraphs": p_znebiti},
        {"label": "07 — viri", "heading": "Viri", "id": "viri", "paragraphs": p_viri},
        {"label": "08 — kaj lahko storite", "heading": "Vnesite opažanje", "id": "opazanje", "paragraphs": p6},
    ]
    return {
        "title": title, "meta_description": desc,
        "tags": ["smrdljivci", "iNaturalist", "jesen", "podatki", str(last)],
        "section_label": "Podatkovna analiza", "og_photo": "weather-station", "og_accent_hex": "#22d3ee",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": (f"Podatki in metodologija: iNaturalist (API, opažanja v Sloveniji; stanje {D['generated'][8:10].lstrip('0')}. "
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
