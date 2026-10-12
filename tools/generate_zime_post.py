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
    ]
    p3 = [
        f"Moja postaja IREICA1 meri od novembra 2019, to je {n_own} zim. Za trend je premalo, za sliko današnje doline pa zadošča. "
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
        "Pri odraslih deluje obratno: spomin hrani izjeme, ne povprečja. Zima z 80 dnevi snega se vtisne; zima s 13 dnevi ne. "
        "To je moja razlaga, ne meritev: o spominu na zime nimam podatkov, zato je ne trdim kot dejstvo.",
        "Po mojem opažanju vrtci in šole še vedno opevajo zimo, v kateri sneg leži tri mesece. Domnevam, da se kultura prilagaja počasneje "
        "kot vreme, a to je domneva. Raziskave o tem, kako otroci v Sloveniji doživljajo zimo, nisem našel.",
        "Pesem o skoraj treh mesecih snega torej ni izmišljena: take zime so bile, v zadnjih desetih zimah v Ljubljani pa nobene. "
        "Otrok jo zato pozna predvsem iz pesmi. Hkrati pa tudi nekoč ni bila vsaka zima taka.",
    ]
    p5 = [
        "<ul>"
        "<li><strong>Ljubljana ni Rečica.</strong> Bežigrad je mestna postaja na 299 m, Šmartno kotlina na 444 m. Zgornja Savinjska dolina je med njima "
        "in ni nobena od njiju.</li>"
        "<li><strong>Sneg je samo iz Ljubljane.</strong> GHCN za Ljubljano hrani le dneve z odejo, ničle ne. Dan brez zapisa štejem za dan brez odeje; "
        "zimi 2004/05 ni nobenega zapisa, zato je nisem upošteval. Pred letom 1995 ni snežnih podatkov, zato se mojih osemdesetih let "
        "po snegu ne da preveriti, po temperaturi pa.</li>"
        "<li><strong>Podatki o temperaturi segajo do zime 2022/23.</strong> Kasnejših zim v teh virih ni.</li>"
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
        f"Spomin pa je pogosto lepši od povprečja: tudi med letoma 1995 in 2003 sta bili dve zimi z manj kot tremi tedni snega. "
        "Spodaj so podatki, omejitve in misli o tem, kako zimo vidi otrok, ki starih zim ni poznal.",
    ])
    sections = [
        {"label": "01 — mraz", "heading": "Mraza je manj, ledenih dni še posebej", "id": "mraz", "paragraphs": p1},
        {"label": "02 — sneg", "heading": "Sneg: krajši in manj zanesljiv", "id": "sneg", "paragraphs": p2},
        {"label": "03 — Rečica", "heading": "Kaj kaže postaja v Rečici?", "id": "recica", "paragraphs": p3},
        {"label": "04 — otroci", "heading": "Zima, ki je otrok ne pozna", "id": "otroci", "paragraphs": p4},
        {"label": "05 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": p5},
        {"label": "06 — viri", "heading": "Viri", "id": "viri", "paragraphs": p_viri},
        {"label": "07 — kaj lahko storite", "heading": "Zapišite svojo zimo", "id": "zapisite", "paragraphs": p6},
    ]
    return {
        "title": title, "meta_description": desc,
        "tags": ["zima", "sneg", "podnebje", "otroci", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "weather-station", "og_accent_hex": "#22d3ee",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Podatki in metodologija: NOAA GHCN-Daily (Ljubljana, Šmartno), meritve postaje IREICA1 (Meteorec). "
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
