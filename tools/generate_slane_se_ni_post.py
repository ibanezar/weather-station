#!/usr/bin/env python3
"""
tools/generate_slane_se_ni_post.py -- »16 noči pod 5 °C, prave slane pa še ni« (21. 10. 2026).

Ročno napisan podatkovni članek, brez tabel (dva grafa + kratke ploščice). Številke pridejo iz committanih virov:
  - history.json         (postaja IREICA1: samo zunanja najnižja/najvišja dnevna temperatura in padavine),
  - napoved-modela.json  (MTR, Open-Meteo, WeatherNext 2 za jutri in naslednja dva dneva; mora biti današnja).
Besedilo nič ne izmišlja; trditve varujejo assert-i: če se podatki spremenijo (npr. postaja izmeri prvo ničelno noč,
napoved ni več današnja), generator pade -- članek je treba prenoviti, ne zaobiti asserta.

Članek je posnetek na dan objave in se ne prepisuje samodejno. Ročni članek po CLAUDE.md gre skozi lekturo
(`lektura.yml` je od 2. 10. 2026 izklopljena -- do ponovnega vklopa ostane slogovni pregled po docs/slog-pisanja.md).
Notranjih meritev postaje članek ne uporablja.

Usage:
    python3 tools/generate_slane_se_ni_post.py [--dry-run] [--text] [--wire] [--force]
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
MODEL = os.path.join(ROOT, "napoved-modela.json")
SLUG = "16-noci-pod-5-c-slane-se-ni-1021"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-slane-se-ni.txt")
NBSP = " "
GREEN, AMBER, CYAN, GREY = "#34d399", "#fbbf24", "#22d3ee", "#8aa0bd"
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
SURFACE = "#0a0f1c"
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LAST = 2026
FROM = "09-01"                                            # od 1. septembra
COLD = 5.0                                                # »hladna noč« = najnižja temperatura pod 5 °C

_MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
        "novembra", "decembra"]
_DAN = ["ponedeljek", "torek", "sredo", "četrtek", "petek", "soboto", "nedeljo"]
_DAN_NOM = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def temp(x, d=1):
    return f"{num(x, d)}{NBSP}°C".replace("-", "–")


def dm(d):
    return f"{d.day}. {d.month}."


def dlong(d):
    return f"{d.day}. {_MES[d.month]}"


# ───────────────────────── podatki ─────────────────────────

def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    return H.get("days", H)


def nights(H, y, upto=None):
    """[(datum, najnižja temperatura)] od 1. 9. do vključno `upto` (mm-dd) v letu y; zunanji senzor postaje."""
    upto = upto or "10-20"
    return [(datetime.date.fromisoformat(d), H[d]["tempLow"]) for d in sorted(H)
            if d.startswith(str(y)) and FROM <= d[5:] <= upto and H[d].get("tempLow") is not None]


def first_freeze(H, y):
    for d in sorted(H):
        if d.startswith(str(y)) and d[5:] >= FROM and H[d].get("tempLow") is not None and H[d]["tempLow"] <= 0:
            return datetime.date.fromisoformat(d)
    return None


def oct_stats(H, y):
    """Povprečje 1.–20. oktobra: najvišja, najnižja, razpon in vsota padavin."""
    ds = [d for d in sorted(H) if d.startswith(str(y)) and "10-01" <= d[5:] <= "10-20"
          and H[d].get("tempLow") is not None and H[d].get("tempHigh") is not None]
    assert len(ds) == 20, (y, len(ds))
    hi = sum(H[d]["tempHigh"] for d in ds) / 20
    lo = sum(H[d]["tempLow"] for d in ds) / 20
    rain = sum(H[d].get("precipTotal") or 0 for d in ds)
    return dict(hi=hi, lo=lo, rng=hi - lo, rain=rain)


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def nights_chart(ns, fc, w=460):
    """Stolpci: najnižja temperatura vsake noči od 1. 9. do 20. 10.; osenčeni stolpci: napoved MTR za 22.–24. 10."""
    pl, pr, pt, pb = 34, 10, 26, 30
    h = 250
    ih = h - pt - pb
    iw = w - pl - pr
    d0 = ns[0][0]
    last = fc[-1][0]
    slots = (last - d0).days + 1
    lo, hi = -2.0, 16.0
    Y = lambda t: pt + ih * (hi - t) / (hi - lo)
    X = lambda d: pl + iw * ((d - d0).days) / slots
    bw = iw / slots * 0.74
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Najnižja temperatura vsake noči od 1. septembra do 20. oktobra in napoved modela MTR za 22. do 24. oktobra" '
         'xmlns="http://www.w3.org/2000/svg">']
    for t in (0, 5, 10, 15):
        y = Y(t)
        dash = ' stroke-dasharray="4 3"' if t == 0 else ""
        col = CYAN if t == 0 else GRID
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="{1.5 if t == 0 else 1}"{dash}/>')
        p.append(f'<text x="{pl - 6}" y="{y + 3.5:.1f}" text-anchor="end" font-size="10.5" fill="{MUTED}">{t}</text>')
    p.append(f'<text x="{pl + 2}" y="{Y(0) + 13:.1f}" font-size="10" fill="{CYAN}">0{NBSP}°C = zmrzal</text>')
    for lab_d in (datetime.date(LAST, 9, 1), datetime.date(LAST, 9, 15), datetime.date(LAST, 10, 1), datetime.date(LAST, 10, 15)):
        x = X(lab_d) + bw / 2
        p.append(f'<text x="{x:.1f}" y="{h - 10}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{dm(lab_d)}</text>')
    base = Y(0)
    for d, t in ns:
        x = X(d)
        if t < 3:
            col, op = CYAN, 1
        elif t < COLD:
            col, op = CYAN, .5
        else:
            col, op = GREY, .38
        y = Y(t)
        p.append(f'<rect x="{x:.1f}" y="{min(y, base):.1f}" width="{bw:.1f}" height="{abs(y - base):.1f}" rx="1.5" fill="{col}" fill-opacity="{op}">'
                 f'<title>{dm(d)}: najnižja {temp(t)}</title></rect>')
    for d, t in fc:
        x = X(d)
        y = Y(t)
        p.append(f'<rect x="{x:.1f}" y="{min(y, base):.1f}" width="{bw:.1f}" height="{max(abs(y - base), 1.5):.1f}" rx="1.5" fill="{AMBER}" fill-opacity=".18" '
                 f'stroke="{AMBER}" stroke-width="1.4" stroke-dasharray="3 2"><title>{dm(d)}: napoved MTR {temp(t)}</title></rect>')
    # oznake
    mn = min(ns, key=lambda r: r[1])
    mx_ = X(mn[0]) + bw / 2
    p.append(f'<text x="{mx_:.1f}" y="{Y(mn[1]) - 16:.1f}" text-anchor="middle" font-size="10.5" font-weight="700" fill="{INK}" stroke="{SURFACE}" stroke-width="3" paint-order="stroke">{num(mn[1])}</text>')
    p.append(f'<text x="{mx_:.1f}" y="{Y(mn[1]) - 5:.1f}" text-anchor="middle" font-size="9.5" fill="{MUTED}" stroke="{SURFACE}" stroke-width="3" paint-order="stroke">{dm(mn[0])}</text>')
    fri = next(r for r in fc if r[0].weekday() == 4)
    fx = X(fri[0]) + bw / 2
    p.append(f'<text x="{fx - 2:.1f}" y="{pt - 12}" text-anchor="end" font-size="10.5" font-weight="700" fill="{AMBER}">petek, napoved {num(fri[1])}</text>')
    p.append(f'<line x1="{fx:.1f}" x2="{fx:.1f}" y1="{pt - 8}" y2="{Y(fri[1]) - 3:.1f}" stroke="{AMBER}" stroke-width="1" stroke-opacity=".7"/>')
    p.append("</svg>")
    return "".join(p)


def wait_chart(rows, today, fri, w=460):
    """rows = [(leto, datum prve ničelne noči)]; zadnja vrstica (LAST) je še brez nje -- črta do `today`, nato napoved za `fri`."""
    pl, pr, pt, pb = 40, 16, 24, 32
    rh = 32
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    span = 85                                             # od 1. 9. do 25. 11.
    X = lambda d: pl + iw * (datetime.date(LAST, d.month, d.day) - datetime.date(LAST, 9, 1)).days / span
    base = pt + rh * len(rows)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Datum prve noči z 0 °C ali manj po letih in letošnje čakanje" xmlns="http://www.w3.org/2000/svg">']
    for lab_d in (datetime.date(LAST, 9, 1), datetime.date(LAST, 10, 1), datetime.date(LAST, 10, 15), datetime.date(LAST, 11, 1), datetime.date(LAST, 11, 15)):
        x = X(lab_d)
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt - 6}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{dm(lab_d)}</text>')
    for i, (y, d) in enumerate(rows):
        cy = pt + rh * i + rh / 2
        now = y == LAST
        p.append(f'<text x="{pl - 8}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" font-weight="{700 if now else 400}" fill="{INK}">{y}</text>')
        x0 = X(datetime.date(LAST, 9, 1))
        if not now:
            x = X(d)
            p.append(f'<line x1="{x0:.1f}" x2="{x:.1f}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{GREY}" stroke-opacity=".45" stroke-width="7" stroke-linecap="round"/>')
            p.append(f'<circle cx="{x:.1f}" cy="{cy:.1f}" r="6.5" fill="{CYAN}" stroke="{SURFACE}" stroke-width="1.8"><title>{y}: prva noč z 0 °C ali manj, {dm(d)}</title></circle>')
            p.append(f'<text x="{x + 11:.1f}" y="{cy + 4:.1f}" font-size="10.5" font-weight="700" fill="{INK}" stroke="{SURFACE}" stroke-width="3" paint-order="stroke">{dm(d)}</text>')
        else:
            x = X(today)
            xf = X(fri)
            p.append(f'<line x1="{x0:.1f}" x2="{x:.1f}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{AMBER}" stroke-width="7" stroke-linecap="round"/>')
            p.append(f'<line x1="{x:.1f}" x2="{xf:.1f}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{AMBER}" stroke-opacity=".6" stroke-width="2" stroke-dasharray="3 3"/>')
            p.append(f'<path d="M{xf:.1f},{cy - 7:.1f} L{xf + 6:.1f},{cy:.1f} L{xf:.1f},{cy + 7:.1f} L{xf - 6:.1f},{cy:.1f} Z" fill="{SURFACE}" stroke="{AMBER}" stroke-width="2">'
                     f'<title>napoved MTR za petek, {dm(fri)}: 48 % verjetnost mraza</title></path>')
            p.append(f'<text x="{xf + 11:.1f}" y="{cy + 4:.1f}" font-size="10.5" font-weight="700" fill="{AMBER}">še brez ničle</text>')
    p.append("</svg>")
    return "".join(p)


def legend(entries):
    out = []
    for n, c, style in entries:
        if style == "dash":
            sw = f'<i style="background:none;border:1.5px dashed {c}"></i>'
        else:
            sw = f'<i style="background:{c};{"opacity:.5" if style == "op" else ""}"></i>'
        out.append(f"<span>{sw}{n}</span>")
    return '<p class="vs-leg">' + " ".join(out) + "</p>"


STYLE = """<style>
.vs-fig{margin:1.4rem 0;padding:1rem 1rem .8rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px}
.vs-fig figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.6rem}
.vs-fig h3{font-family:'Space Grotesk',sans-serif;font-size:.95rem;margin:0 0 .4rem;color:var(--text)}
.vs-fig svg{display:block;width:100%;height:auto;max-width:560px;margin:0 auto}
.vs-leg{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-size:.85rem;color:var(--muted);margin:.2rem 0 .6rem}
.vs-leg i{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;margin-right:.4rem;vertical-align:-.1rem}
.sn-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin:1.3rem 0}
.sn-tile{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:.8rem .9rem}
.sn-tile b{display:block;font-family:'Space Grotesk',sans-serif;font-size:2rem;line-height:1.05;color:var(--text)}
.sn-tile b small{font-size:1rem;font-weight:600;color:var(--muted)}
.sn-tile span{display:block;margin-top:.35rem;font-size:.82rem;line-height:1.4;color:var(--muted)}
.sn-tile.sn-warn b{color:#fbbf24}
.vs-note{color:var(--muted);font-size:.82rem;line-height:1.5;margin:-.4rem 0 1.2rem}
</style>"""


def fig(title, inner, caption):
    return f'<figure class="vs-fig"><h3>{title}</h3>{inner}<figcaption>{caption}</figcaption></figure>'


def tiles(items):
    out = []
    for big, small, text, warn in items:
        out.append(f'<div class="sn-tile{" sn-warn" if warn else ""}"><b>{big}{(" <small>" + small + "</small>") if small else ""}</b><span>{text}</span></div>')
    return '<div class="sn-tiles">' + "".join(out) + "</div>"


# ───────────────────────── članek ─────────────────────────

def build_article(H):
    today = datetime.date.today()
    last_day = max(H)
    last = datetime.date.fromisoformat(last_day)
    assert last == datetime.date(LAST, 10, 20), f"zadnji dan v history.json je {last_day}; članek je napisan za 20. 10."

    # --- letošnja jesen ---
    ns = nights(H, LAST)
    assert len(ns) == 50 and ns[0][0] == datetime.date(LAST, 9, 1) and ns[-1][0] == last
    assert first_freeze(H, LAST) is None, "letos je že bila ničelna noč -- članek je treba prenoviti"
    n_cold = {y: sum(1 for _, t in nights(H, y) if t < COLD) for y in YEARS + [LAST]}
    assert n_cold[LAST] == 16 and all(n_cold[y] < 16 for y in YEARS), n_cold
    coldest = sorted(ns, key=lambda r: r[1])[:3]
    assert [(d.month, d.day, t) for d, t in coldest] == [(10, 4, 1.7), (10, 6, 1.8), (10, 13, 2.1)], coldest
    n_cold_vals = sorted(n_cold[y] for y in YEARS)
    assert (n_cold[2020], n_cold[2023], n_cold[2024]) == (14, 3, 4), n_cold

    # --- topli popoldnevi, mrzla jutra ---
    S = {y: oct_stats(H, y) for y in YEARS + [LAST]}
    assert S[LAST]["rng"] > max(S[y]["rng"] for y in YEARS), "razpon letos ni več največji"
    hi_rank = 1 + sum(1 for y in YEARS if S[y]["hi"] > S[LAST]["hi"])
    assert hi_rank == 3, hi_rank                           # tretja najvišja najvišja temperatura (2023, 2022 višji)
    assert abs(S[LAST]["hi"] - 19.7) < .05 and abs(S[LAST]["lo"] - 5.7) < .06 and abs(S[LAST]["rng"] - 14.0) < .06, S[LAST]
    assert S[2020]["rain"] > 170 and S[2024]["rain"] > 170 and abs(S[LAST]["rain"] - 23.4) < .06, S

    # --- prva ničelna noč po letih ---
    ff = {y: first_freeze(H, y) for y in YEARS}
    exp = {2020: (10, 14), 2021: (10, 13), 2022: (11, 20), 2023: (10, 17), 2024: (11, 4), 2025: (10, 3)}
    assert {y: (d.month, d.day) for y, d in ff.items()} == exp, ff
    early = [y for y in YEARS if ff[y] <= datetime.date(y, 10, 20)]
    assert early == [2020, 2021, 2023, 2025]

    # --- napoved (mora biti današnja: čas izdelave modela je današnji datum) ---
    mdl = json.load(open(MODEL, encoding="utf-8"))
    gen = datetime.datetime.fromisoformat(mdl["generated_at"].replace("Z", "+00:00"))
    assert gen.date() == today, f"napoved modela ni današnja ({gen.date()}); osveži jo ali prenovi članek"
    assert today == datetime.date(LAST, 10, 21), "članek je napisan za 21. 10. 2026"
    fd = {r["date"]: r for r in mdl["days"]}
    fri_d = datetime.date(LAST, 10, 23)
    sat_d = datetime.date(LAST, 10, 24)
    assert fri_d.weekday() == 4 and sat_d.weekday() == 5
    fri, sat, thu = fd[fri_d.isoformat()], fd[sat_d.isoformat()], fd["2026-10-22"]
    assert fri["tmin"] == 0.1 and abs(fri["p_frost"] - .48) < .005 and fri["om_tmin"] == 2.6 and fri["d_tmin"] == -2.5, fri
    assert fri["wn2"]["tmin"]["p50"] == 3.5 and fri["wn2"]["tmin"]["p10"] == 1.9 and fri["wn2"]["tmin"]["p90"] == 4.9, fri["wn2"]
    assert sat["om_precip"] > 30 and 8 <= sat["tmax"] <= 9, sat
    fc = [(datetime.date.fromisoformat(r), fd[r]["tmin"]) for r in ("2026-10-22", "2026-10-23", "2026-10-24")]

    # --- grafi ---
    f_nights = fig("Najnižja temperatura vsake noči od 1. septembra",
                   legend([("pod 3 °C", CYAN, ""), ("od 3 do 5 °C", CYAN, "op"), ("5 °C ali več", GREY, "op"),
                           ("napoved MTR (22.–24. 10.)", AMBER, "dash")])
                   + nights_chart(ns, fc),
                   "Vsak stolpec je ena noč: najnižja temperatura zraka, ki jo je izmerila postaja IREICA1 (zunanji senzor). Črtkani stolpci so napoved modela MTR "
                   "za naslednje tri dni; za današnji dan podatka še ni. Črtkana črta pri 0 °C je meja, ki jo šteje ta članek.")
    wrows = [(y, ff[y]) for y in YEARS] + [(LAST, None)]
    f_wait = fig("Kdaj je postaja prvič izmerila 0 °C ali manj",
                 wait_chart(wrows, today - datetime.timedelta(days=1), fri_d),
                 "Siva črta pomeni čakanje od 1. septembra, moder krog prvo noč z 0 °C ali manj. Oranžna črta je letošnje čakanje do 20. oktobra, "
                 "prazen romb pa petek, ko model MTR kaže 0,1 °C.")

    t_tiles = tiles([
        ("16", "noči", "pod 5 °C od 1. 9. do 20. 10. Najbolj od vseh šestih prejšnjih jeseni.", False),
        (num(coldest[0][1]), "°C", f"najnižja letošnja temperatura ({dm(coldest[0][0])}). Do ničle je zmanjkalo 1,7 stopinje.", False),
        ("48", "%", f"verjetnost mraza v petek zjutraj po modelu MTR; napovedana najnižja temperatura {temp(fri['tmin'])}.", True),
    ])

    lead = (f"Od 1. septembra do 20. oktobra je postaja v Rečici <strong>16-krat</strong> izmerila manj kot 5 °C. Toliko hladnih noči v istem obdobju "
            "ni bilo v nobeni od prejšnjih šestih jeseni. A niti ena noč ni padla pod ničlo: najbližje je bila 4. oktobra z 1,7 °C. "
            "Prva prava slana, pri kateri se tudi termometer spusti do ničle ali pod njo, torej še ni bila. "
            f"Napoved modela MTR za <strong>petek zjutraj</strong> pa kaže {temp(fri['tmin'])}.")

    p1 = [
        "<strong>Kratek odgovor: slana na travi je že bila, prave zmrzali na termometru pa še ni.</strong> "
        "Postaja meri temperaturo zraka na višini približno 1,5–2 m. Ko tu piše 0 °C ali manj, ji pravim prva ničelna noč, in to število lahko primerjam med leti.",
        t_tiles,
        f_nights,
        f"Najhladnejše noči so bile 4. oktobra ({temp(1.7)}), 6. oktobra ({temp(1.8)}) in 13. oktobra ({temp(2.1)}). "
        f"Za primerjavo: največ hladnih noči v istem obdobju je bilo doslej leta 2020 ({n_cold[2020]}), najmanj pa leta 2023 ({n_cold[2023]}) in 2024 ({n_cold[2024]}). "
        "Prag 5 °C sem izbral sam; je zgolj merilo za to primerjavo, ne uradna meja.",
    ]
    p2 = [
        "Hladnih noči ne pojasni hladna jesen. Med 1. in 20. oktobrom je bila povprečna najvišja dnevna temperatura "
        f"<strong>{temp(S[LAST]['hi'])}</strong>, kar je tretja najvišja vrednost od šestih let.",
        f"Razlika med popoldnevom in jutrom je v povprečju znašala <strong>{temp(S[LAST]['rng'])}</strong>, največ v teh letih. "
        f"Lani je bila {temp(S[2025]['rng'])}, leta 2024 samo {temp(S[2024]['rng'])}. Tak vzorec – topli popoldnevi in hladna jutra – "
        "je značilen za jasno in mirno vreme: ponoči tla oddajajo toploto proti nebu, čez dan pa jih sonce spet ogreje. "
        'Kako to deluje, sem pojasnil <a href="/blog/2-1-c-najhladnejse-jesensko-jutro-kdaj-prva-slana-0923.html" style="color:var(--blue)">že 23. septembra</a>.',
        f"Oktober je bil tudi suh: do 20. oktobra je padlo {num(S[LAST]['rain'])} mm padavin. Leta 2020 in 2024 je v istem obdobju padlo več kot 170 mm. "
        "Zakaj tudi take noči niso prišle do ničle, iz teh podatkov ne morem reči zanesljivo. Verjetno je manjkalo še nekaj stopinj hladnejše zračne mase: "
        "jasna noč ohladi zrak ob tleh, vendar le do mere, ki jo dovoli zračna masa nad dolino.",
    ]
    p3 = [
        "Na travniku v Nizki je bila 4. oktobra ob 8.35 trava bela od slane, postaja pa je kazala 1,7 °C. "
        'O tem sem pisal <a href="/blog/slana-pri-1-7-c-zakaj-trava-pobeli-prej-kot-postaja-1004.html" style="color:var(--blue)">v članku o slani pri 1,7 °C</a>. '
        "To ni protislovje, ker slana in zmrzal nista isto.",
        "<ul>"
        "<li><strong>Slana</strong> je led, ki se nabere na hladni površini, na primer na travi, avtu ali strehi. Pojavi se lahko že, ko je zrak še nekaj stopinj nad ničlo.</li>"
        "<li><strong>Zmrzal</strong> pomeni 0 °C ali manj v zraku na višini merjenja. Samo to štejem v tem članku.</li>"
        "</ul>",
        "Na odprtem travniku ali v mrazišču je ob jasni noči lahko hladneje kot na postaji. Če imate vrt, je zato dobro misliti na jasno in mirno jutro, "
        "tudi ko številka v napovedi še ni ničla.",
    ]
    p4 = [
        f_wait,
        "V šestih letih je prva ničelna noč prišla 3. oktobra (2025), 13. oktobra (2021), 14. oktobra (2020), 17. oktobra (2023), 4. novembra (2024) in 20. novembra (2022). "
        "Tri leta je torej prišla do 14. oktobra, tri leta po 17. oktobru. Letos smo 20. oktobra še brez nje. To ni rekord: leta 2022 in 2024 je bilo čakanje daljše.",
        f"<strong>Petek, 23. oktobra.</strong> Napoved z 21. oktobra: model MTR pričakuje {temp(fri['tmin'])} in ocenjuje {round(fri['p_frost'] * 100)}-odstotno verjetnost zmrzali. "
        f"Surovi model Open-Meteo kaže {temp(fri['om_tmin'])}, ansambel Google WeatherNext 2 pa mediano {temp(fri['wn2']['tmin']['p50'])} "
        f"(razpon od {num(fri['wn2']['tmin']['p10'])} do {temp(fri['wn2']['tmin']['p90'])}). "
        f"Modeli se torej ne strinjajo. MTR je naučen na meritvah postaje in zna upoštevati dno doline, zato tokrat surovo vrednost popravi za {num(abs(fri['d_tmin']))} °C navzdol.",
        "MTR je poskusen model in se lahko moti v obe smeri. V preizkusu na 366 preteklih dneh je bila zmrzal pri napovedih med 30 in 70 % pogostejša od napovedane. "
        "To ni zagotovilo za petek, je pa razlog, da 0,1 °C ne jemljem kot zanesljivo številko.",
        f"V soboto sledi ohladitev in dež: najvišja temperatura okoli {num(sat['tmax'], 0)} °C, po Open-Meteo okoli {num(sat['om_precip'], 0)} mm padavin "
        "(količin MTR ne popravlja).",
    ]
    letos = [
        "<ul>"
        "<li><strong>Vrt in balkon:</strong> če imate še kaj, kar mraza ne prenese, je petkovo jutro razlog, da rastline pokrijete ali vnesete v hišo. "
        "Na travniku ali v mrazišču je lahko hladneje kot na postaji.</li>"
        "<li><strong>Gobarji:</strong> prva slana gobarske sezone ne konča. V vseh štirih letih, ko je prva ničelna noč prišla oktobra, je bil vrh opažanj gob šele po njej. "
        'Več v <a href="/blog/slana-gobarska-sezona-1018.html" style="color:var(--blue)">članku o slani in gobah</a>.</li>'
        f'<li><strong>Preizkusite sami:</strong> v igri <a href="{SITE}/napovej/" style="color:var(--blue)">Prehiti model</a> napovejte jutrišnjo najnižjo temperaturo '
        "in jo primerjajte z modeli in meritvijo postaje.</li>"
        f'<li><strong>Spremljajte v živo:</strong> trenutna meritev je na <a href="{SITE}/" style="color:var(--blue)">naslovni strani</a>.'
        "</li>"
        "</ul>",
    ]
    omejitve = [
        "<ul>"
        "<li><strong>Šest let je malo.</strong> Postaja meri od novembra 2019, zato so primerjave samo med jesenmi 2020–2025. Če sta dve leti poznejši od ostalih, to še ni trend.</li>"
        "<li><strong>Ena postaja, ena točka.</strong> Postaja stoji na dnu doline v Rečici ob Savinji. Na travi, v mrazišču ali na višjih legah je lahko hladneje.</li>"
        "<li><strong>Napoved ni meritev.</strong> Stanje je z dne 21. oktobra, ko je bil model MTR izdan; do petka se lahko spremeni. MTR je poskusen model, Open-Meteo in WeatherNext 2 sta tuja modela in nobeden ni uradno opozorilo. "
        'Za uradna opozorila velja <a href="https://vreme.arso.gov.si/napoved" style="color:var(--blue)">ARSO</a>.</li>'
        "<li><strong>Prag 5 °C je moja izbira.</strong> Namenjen je primerjavi med leti.</li>"
        "<li><strong>Članek je posnetek na dan objave.</strong> Po prvi ničelni noči se samodejno ne spremeni.</li>"
        "</ul>",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    title = "16 noči pod 5 °C, prave slane pa še ni"
    assert len(title) <= 60, len(title)
    desc = ("Do 20. oktobra je bilo v Rečici 16 noči pod 5 °C, a nobene z mrazom. Model MTR za petek kaže 0,1 °C. Kaj kažejo podatki šestih jeseni?")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — noči", "heading": "Šestnajst hladnih noči, nobene ničle", "id": "noci", "paragraphs": p1},
        {"label": "02 — razlog", "heading": "Topli popoldnevi, mrzla jutra", "id": "razlog", "paragraphs": p2},
        {"label": "03 — trava", "heading": "Na travi je slana že bila, na termometru ne", "id": "trava", "paragraphs": p3},
        {"label": "04 — kdaj", "heading": "Kdaj bo prva ničla? Morda že v petek", "id": "kdaj", "paragraphs": p4},
        {"label": "05 — praktično", "heading": "Kaj lahko naredite", "id": "prakticno", "paragraphs": letos},
        {"label": "06 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
    ]

    def nb(h):                                    # »0 °C«, »48 %« se ne smeta prelomiti čez vrstico
        return re.sub(r"(\d) (°C|%|mm)", lambda m: m.group(1) + NBSP + m.group(2), h)
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["slana", "zmrzal", "oktober", "napoved", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "night-fog-valley", "og_accent_hex": "#22d3ee",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: postaja IREICA1 (najnižja in najvišja dnevna temperatura, padavine, zunanji senzor, od 7. 11. 2019); "
                         "model MTR (napoved-modela.json, izdan 21. 10. 2026); Open-Meteo; Google WeatherNext 2 (ansambel, prek Open-Meteo)."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|figcaption|li|p|div)[^>]*>", "\n", h)
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
    article = build_article(load())
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
        og_title="16 noči pod 5 °C,\nslane pa še ni", meta_note="podatkovna analiza",
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
