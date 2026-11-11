#!/usr/bin/env python3
"""
tools/generate_martinovo_post.py -- »Ali je Martinovo res toplo? Šest let podatkov« (11. 11. 2026).

Ročno napisan podatkovni članek ob Martinovem. Vse številke v besedilu, grafih in tabelah pridejo iz committanih virov:
  - history.json              (postaja IREICA1: samo zunanja polja tempHigh/tempLow/tempAvg/precipTotal; dnevi z src == "era5" so izpuščeni),
  - napoved-modela-live.json  (MTR, živa osvežitev: najvišja/najnižja temperatura in verjetnost zmrzali za 12.–14. 11.).
Besedilo nič ne izmišljuje; trditve varujejo assert-i: če se podatki osvežijo in trditev ne drži več, generator pade --
besedilo je treba pregledati, ne zaobiti asserta.

Članek je posnetek na dan objave (11. 11. 2026) in se ne prepisuje samodejno (`--allow-date` dovoli ponovni zagon drug dan).
Po CLAUDE.md gre ročni članek skozi lekturo (`lektura.yml` je od 2. 10. 2026 izklopljena -- do ponovnega vklopa ostane slogovni
pregled po docs/slog-pisanja.md in `python3 tools/lektura_scan.py`). Notranjih meritev postaje članek ne uporablja.
Reki o snegu na Martinovo se s postajo ne dajo preveriti (postaja snega ne meri), zato jih članek ne trdi.

Usage:
    python3 tools/generate_martinovo_post.py [--dry-run] [--text] [--wire] [--force] [--allow-date]
"""
import datetime
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
HISTORY = os.path.join(ROOT, "history.json")
LIVE = os.path.join(ROOT, "napoved-modela-live.json")
SLUG = "martinovo-vreme-recica-sest-let-1111"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-martinovo.txt")
SNAPSHOT_DATE = "2026-11-11"
NBSP = " "
GREEN, AMBER, CYAN, GREY = "#34d399", "#fbbf24", "#22d3ee", "#8aa0bd"
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
SURFACE = "#0a0f1c"
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LAST = 2026
WARM = 15.0                                              # »topel dan«: najvišja temperatura vsaj 15 °C (moja izbira, ne uradna meja)


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def temp(x, d=1):
    return f"{num(x, d)}{NBSP}°C".replace("-", "–")


def n1(x):
    return num(x).replace("-", "–")


def dm(d):
    return f"{d.day}. {d.month}."


_GEN = ["nič", "ene", "dveh", "treh", "štirih", "petih", "šestih", "sedmih", "osmih", "devetih", "desetih"]


def numg(n):
    return _GEN[int(n)] if 2 <= int(n) <= 10 else str(int(n))


def D(s):
    return datetime.date.fromisoformat(s)


# ───────────────────────── podatki ─────────────────────────

def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    H = {k: v for k, v in H.items() if v.get("src") != "era5"}
    return H, json.load(open(LIVE, encoding="utf-8"))


def full(H, y, a, b):
    return all(f"{y}-11-{k:02d}" in H for k in range(a, b + 1))


def mean(vals):
    vals = list(vals)
    return sum(vals) / len(vals)


def window(H, y, a, b):
    return [H[f"{y}-11-{k:02d}"] for k in range(a, b + 1)]


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def week_chart(rows, w=360):
    """rows = [(leto, lo, hi, d11, oznaka)] -- razpon najvišjih dnevnih temperatur 8.–14. 11. (trak), Martinovo (romb), prag 15 °C."""
    pl, pr, pt, pb = 44, 14, 24, 32
    rh = 30
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    X = lambda t: pl + iw * t / 20
    base = pt + rh * len(rows)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Razpon najvišjih dnevnih temperatur od 8. do 14. novembra po letih, Martinovo in prag 15 stopinj" '
         'xmlns="http://www.w3.org/2000/svg">']
    for t in (0, 5, 10, 15, 20):
        x = X(t)
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 17}" text-anchor="middle" font-size="13" fill="{MUTED}">{t}{NBSP}°C</text>')
    xw = X(WARM)
    p.append(f'<line x1="{xw:.1f}" x2="{xw:.1f}" y1="{pt - 8}" y2="{base}" stroke="{AMBER}" stroke-width="1.8" stroke-dasharray="5 3"/>')
    for i, (y, lo, hi, d11, tag) in enumerate(rows):
        cy = pt + rh * i + rh / 2
        now = y == LAST
        p.append(f'<text x="{pl - 8}" y="{cy + 4.5:.1f}" text-anchor="end" font-size="13" font-weight="{700 if now else 400}" fill="{INK}">{y}</text>')
        p.append(f'<rect x="{X(lo):.1f}" y="{cy - 6:.1f}" width="{max(X(hi) - X(lo), 3):.1f}" height="12" rx="3" fill="{GREEN if now else GREY}" '
                 f'fill-opacity="{1 if now else .7}"><title>{y}{tag}: najvišje dnevne temperature od {n1(lo)} do {n1(hi)} °C</title></rect>')
        if d11 is not None:
            x = X(d11)
            p.append(f'<path d="M{x:.1f},{cy - 9:.1f} L{x + 7:.1f},{cy:.1f} L{x:.1f},{cy + 9:.1f} L{x - 7:.1f},{cy:.1f} Z" fill="{INK}" stroke="{SURFACE}" stroke-width="2">'
                     f'<title>{y}: Martinovo, najvišja temperatura {n1(d11)} °C</title></path>')
        lab = f"{n1(lo)}–{n1(hi)}"
        lw = 7.6 * len(lab)
        if X(hi) + 12 + lw < w - 2:
            p.append(f'<text x="{X(hi) + 12:.1f}" y="{cy + 4.5:.1f}" font-size="13" fill="{INK}">{lab}</text>')
        else:
            p.append(f'<text x="{X(lo) - 12:.1f}" y="{cy + 4.5:.1f}" text-anchor="end" font-size="13" fill="{INK}">{lab}</text>')
    p.append("</svg>")
    return "".join(p)


def trend_chart(shares, hi_start=8, w=360):
    """shares = {začetek_tedna: (število_let_z_toplim_dnem, število_let)} -- delež let z vsaj enim toplim dnevom v sedmih dneh, ki se začnejo na ta datum."""
    pl, pr, pt, pb = 50, 10, 14, 34
    h = 220
    iw, ih = w - pl - pr, h - pt - pb
    starts = sorted(shares)
    n = len(starts)
    step = iw / n
    bw = step * 0.68
    Y = lambda v: pt + ih * (1 - v / 100)
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Delež let z vsaj enim dnevom s 15 stopinjami ali več v sedmih dneh, ki se začnejo na dani datum v novembru" '
         'xmlns="http://www.w3.org/2000/svg">']
    for v in (0, 50, 100):
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{pl - 6}" y="{Y(v) + 4.5:.1f}" text-anchor="end" font-size="13" fill="{MUTED}">{v}{NBSP}%</text>')
    for s in starts:
        i = starts.index(s)
        x = pl + step * i + (step - bw) / 2
        k, m = shares[s]
        v = 100 * k / m
        col = GREEN if s == hi_start else GREY
        p.append(f'<rect x="{x:.1f}" y="{Y(v):.1f}" width="{bw:.1f}" height="{max(Y(0) - Y(v), 0.5):.1f}" rx="2" fill="{col}" fill-opacity="{1 if s == hi_start else .7}">'
                 f'<title>Teden od {s}. 11.: vsaj en dan s 15 °C ali več v {k} od {m} let ({round(v)} %)</title></rect>')
    for s in (1, 8, 15, 22):
        i = starts.index(s)
        x = pl + step * i + step / 2
        p.append(f'<text x="{x:.1f}" y="{h - 10}" text-anchor="middle" font-size="13" fill="{MUTED}">{s}. 11.</text>')
    p.append("</svg>")
    return "".join(p)


def legend(entries):
    out = []
    for n, kind, c in entries:
        if kind == "dash":
            sw = f'<i class="vs-dash" style="border-color:{c}"></i>'
        elif kind == "dia":
            sw = f'<i class="vs-dia" style="background:{c}"></i>'
        else:
            sw = f'<i style="background:{c}"></i>'
        out.append(f"<span>{sw}{n}</span>")
    return '<p class="vs-leg">' + " ".join(out) + "</p>"


STYLE = """<style>
.vs-fig{margin:1.4rem 0;padding:1rem 1rem .8rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px}
.vs-fig figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.6rem}
.vs-fig h3{font-family:'Space Grotesk',sans-serif;font-size:.95rem;margin:0 0 .4rem;color:var(--text)}
.vs-fig svg{display:block;width:100%;height:auto;max-width:460px;margin:0 auto}
.vs-leg{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-size:.85rem;color:var(--muted);margin:.2rem 0 .6rem}
.vs-leg i{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;margin-right:.4rem;vertical-align:-.1rem}
.vs-leg i.vs-dia{border-radius:2px;transform:rotate(45deg) scale(.85)}
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
.vs-more{margin:.6rem 0 1.2rem}
.vs-more summary{cursor:pointer;color:var(--blue);font-size:.9rem}
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


def stat_cards(items):
    return '<div class="vs-cards">' + "".join(f'<div class="vs-card"><b>{v}</b><span>{lab}</span></div>' for v, lab in items) + "</div>"


# ───────────────────────── članek ─────────────────────────

def build_article(H, live):
    # ── podatki po letih ──
    d11 = {y: H[f"{y}-11-11"] for y in YEARS}
    wk = {y: window(H, y, 8, 14) for y in YEARS}
    for y in YEARS:
        assert full(H, y, 1, 14), y
    hi11 = [d11[y]["tempHigh"] for y in YEARS]
    mean11 = mean(hi11)
    nov_all = [H[k]["tempHigh"] for k in H if k[5:7] == "11" and int(k[:4]) in YEARS]
    mean_nov = mean(nov_all)
    assert (min(hi11), max(hi11)) == (5.0, 17.0) and round(mean11, 1) == 10.5 and round(mean_nov, 1) == 10.6, (min(hi11), max(hi11), mean11, mean_nov)
    assert d11[2024]["tempHigh"] == 5.0 and d11[2025]["tempHigh"] == 17.0
    assert round(d11[2025]["tempLow"], 1) == -2.1 and round(d11[2025]["tempHigh"] - d11[2025]["tempLow"], 1) == 19.1

    warm_wk = {y: sum(1 for x in wk[y] if x["tempHigh"] >= WARM) for y in YEARS}
    n_warm_years = sum(1 for y in YEARS if warm_wk[y] > 0)
    assert n_warm_years == 4 and [y for y in YEARS if warm_wk[y] == 0] == [2021, 2024], warm_wk
    frost_wk = {y: sum(1 for x in wk[y] if x["tempLow"] <= 0) for y in YEARS}
    assert sum(1 for y in YEARS if frost_wk[y] >= 2) == 5 and frost_wk[2022] == 0 and frost_wk[2025] == 6, frost_wk
    wet11 = [y for y in YEARS if d11[y]["precipTotal"] >= 0.2]
    assert wet11 == [2022, 2023, 2025] and [y for y in YEARS if d11[y]["precipTotal"] > 1.0] == [2023] and d11[2023]["precipTotal"] == 9.2

    # ── kontrola: vsa sedemdnevna okna novembra ──
    shares, tot, hit = {}, 0, 0
    for s in range(1, 25):
        yrs = [y for y in YEARS if full(H, y, s, s + 6)]
        k = sum(1 for y in yrs if max(x["tempHigh"] for x in window(H, y, s, s + 6)) >= WARM)
        shares[s] = (k, len(yrs))
        tot += len(yrs)
        hit += k
    assert (hit, tot) == (60, 134), (hit, tot)
    assert shares[1] == (6, 6) and shares[2] == (6, 6) and shares[8] == (4, 6) and shares[7] == (3, 6) and shares[9] == (3, 6), shares
    assert all(shares[s][0] == 0 for s in (22, 23, 24)), shares
    assert [s for s in range(1, 25) if shares[s][1] == 5] == list(range(14, 24)), "okna brez leta 2025"
    wk1 = {y: mean(x["tempAvg"] for x in window(H, y, 1, 7)) for y in YEARS}
    wk2 = {y: mean(x["tempAvg"] for x in window(H, y, 8, 14)) for y in YEARS}
    colder = [y for y in YEARS if wk2[y] < wk1[y]]
    m1, m2 = mean(wk1.values()), mean(wk2.values())
    assert len(colder) == 6 and (round(m1, 1), round(m2, 1)) == (8.6, 5.5), (colder, m1, m2)

    # ── letos ──
    t26 = {d: H[f"2026-11-{d:02d}"] for d in (8, 9, 10)}
    assert [t26[d]["tempHigh"] for d in (8, 9, 10)] == [11.0, 12.7, 14.3] and t26[9]["tempLow"] == -1.7
    assert "2026-11-11" not in H, "11. 11. je v history.json -- članek je posnetek do 10. 11."
    assert max(t26[d]["tempHigh"] for d in (8, 9, 10)) < WARM
    ld = {r["date"]: r for r in live["days"]}
    f12, f13, f14 = ld["2026-11-12"], ld["2026-11-13"], ld["2026-11-14"]
    assert f12["tmax"] < WARM and f13["tmax"] < WARM and f14["tmin"] < 0 and f14["p_frost"] >= 0.5, (f12, f13, f14)
    pf = int(round(f14["p_frost"] * 100 / 5.0)) * 5

    nb = lambda h: re.sub(r"(\d) (°C|%)", lambda m: m.group(1) + NBSP + m.group(2), h)

    lead = (f"Na Martinovo je bila v Rečici v zadnjih šestih letih najvišja temperatura med {temp(min(hi11))} in {temp(max(hi11))}, v povprečju {temp(mean11)}. "
            f"To je skoraj natanko povprečje vseh novembrskih dni ({temp(mean_nov)}). "
            f"Dan s 15{NBSP}°C ali več je bil v tednu od 8. do 14. novembra v {numg(n_warm_years)} od šestih let, vendar so bili taki dnevi še pogostejši v prvem tednu novembra.")

    cards = stat_cards([
        (temp(mean11), "povprečna najvišja temperatura 11. novembra, leta 2020–2025"),
        (temp(mean_nov), "povprečna najvišja temperatura vseh novembrskih dni v istih letih"),
        (f"{n_warm_years} od 6", f"let z vsaj enim dnevom s 15{NBSP}°C ali več v tednu od 8. do 14. 11."),
        (f"{round(100 * hit / tot)}{NBSP}%", f"vseh sedemdnevnih oken v novembru z vsaj enim takim dnevom ({hit} od {tot})"),
    ])
    rows = [(y, min(x["tempHigh"] for x in wk[y]), max(x["tempHigh"] for x in wk[y]), d11[y]["tempHigh"], "") for y in YEARS]
    rows.append((LAST, min(t26[d]["tempHigh"] for d in (8, 9, 10)), max(t26[d]["tempHigh"] for d in (8, 9, 10)), None, " (do 10. 11.)"))
    f_week = fig("Najvišje dnevne temperature v Martinovem tednu",
                 legend([("razpon od 8. do 14. 11.", "sq", GREY), ("letos, od 8. do 10. 11.", "sq", GREEN),
                         ("Martinovo, 11. 11.", "dia", INK), ("15 °C", "dash", AMBER)]) + week_chart(rows),
                 "Trak kaže najnižjo in najvišjo dnevno najvišjo temperaturo od 8. do 14. novembra, romb Martinovo. Letošnji trak je krajši, ker se podatki končajo 10. novembra.")
    p1 = [
        "<strong>Kratek odgovor: Martinovo ni posebej toplo, topli dnevi pa se v novembru res pojavljajo.</strong> "
        f"Martinovo je bilo v šestih letih zelo različno: od mrzlega dne s {temp(d11[2024]['tempHigh'])} (2024) do {temp(d11[2025]['tempHigh'])} (2025).",
        cards,
        f_week,
        "Za topel čas okoli 11. novembra se včasih uporablja ime »martinovo poletje«. Za ta članek sem ga opredelil po svoje: dan z najvišjo temperaturo 15 °C ali več. "
        "Prag je moja izbira in ne uradna meja.",
    ]

    f_trend = fig("Kdaj v novembru je bil vsaj en topel dan?",
                  legend([("teden, ki se začne na ta datum", "sq", GREY), ("Martinov teden, začetek 8. 11.", "sq", GREEN)])
                  + trend_chart(shares),
                  f"Za vsak začetek tedna od 1. do 24. novembra: v kolikšnem deležu let je bil v sedmih dneh vsaj en dan z najvišjo temperaturo 15{NBSP}°C ali več. "
                  "Tedni, ki se začnejo od 14. do 23. novembra, imajo samo pet let, ker leta 2025 manjkajo dnevi od 20. do 23. 11.")
    p2 = [
        "Martinov teden sem primerjal z vsemi drugimi tedni novembra. Vprašanje je pri vsakem enako: ali je bil v sedmih zaporednih dneh vsaj en dan s 15 °C ali več? "
        "Za tedne, ki se začnejo 1. ali 2. novembra, je odgovor v vseh šestih letih »da«, za tedne od 22. novembra naprej pa v vseh letih »ne«.",
        f_trend,
        f"Martinov teden ({shares[8][0]} od {shares[8][1]} let) leži na tej padajoči črti. Tedna, ki se začneta 7. in 9. novembra, imata po {shares[7][0]} od {shares[7][1]} let. "
        "Razlika je v enem letu, zato Martinovemu tednu ne morem pripisati nič posebnega.",
        f"Pada tudi povprečna dnevna temperatura: od {temp(m1)} v prvem tednu novembra na {temp(m2)} v tednu od 8. do 14. novembra. "
        f"V vseh šestih letih je bil Martinov teden hladnejši od prvega tedna. To je običajno ohlajanje jeseni, ne posebnost Martinovega.",
    ]

    t_years = table(["Leto", "11. 11. najvišja", "11. 11. najnižja", "11. 11. padavine", "8.–14. 11. najvišja", "Dni s 15 °C ali več", "Noči z 0 °C ali manj", "8.–14. 11. padavine"],
                    [[str(y), temp(d11[y]["tempHigh"]), temp(d11[y]["tempLow"]), f"{num(d11[y]['precipTotal'])} mm",
                      temp(max(x["tempHigh"] for x in wk[y])), str(warm_wk[y]), str(frost_wk[y]),
                      f"{num(sum(x['precipTotal'] for x in wk[y]))} mm"] for y in YEARS],
                    cap="Martinovo in Martinov teden po letih",
                    note="Postaja IREICA1, zunanji senzor, dnevne vrednosti. Padavine: vsota dneva oziroma tedna.")
    t_years = '<details class="vs-more"><summary>Vse številke po letih (tabela)</summary>' + t_years + '</details>'
    p3 = [
        f"Najbolj izrazit primer je Martinovo 2025: najnižja temperatura {temp(d11[2025]['tempLow'])}, najvišja {temp(d11[2025]['tempHigh'])}. "
        f"Razlika znaša {temp(d11[2025]['tempHigh'] - d11[2025]['tempLow'])} v enem dnevu. V istem tednu je bilo {frost_wk[2025]} noči z 0{NBSP}°C ali manj.",
        f"Mraz v Martinovem tednu ni redkost: v petih od šestih let je bilo vsaj dve noči z 0{NBSP}°C ali manj. Izjema je leto 2022, ko je bila najnižja temperatura tega tedna {temp(min(x['tempLow'] for x in wk[2022]))}.",
        f"Dež na sam Martinov dan je bil bolj izjema kot pravilo: vsaj 0,2 mm je padlo v {numg(len(wet11))} od šestih let, več kot 1 mm samo leta 2023 ({num(d11[2023]['precipTotal'])} mm).",
        t_years,
    ]

    letos = [
        f"Letos je bila najvišja temperatura od 8. do 10. novembra {temp(t26[8]['tempHigh'])}, {temp(t26[9]['tempHigh'])} in {temp(t26[10]['tempHigh'])}. "
        f"Prag 15{NBSP}°C do 10. novembra torej ni bil dosežen. Postaja je 9. novembra izmerila {temp(t26[9]['tempLow'])}.",
        "Danes, 11. novembra, dan še teče: najvišjo temperaturo si oglejte na <a href=\"/\" style=\"color:var(--blue)\">živi kartici</a>.",
        f"Model MTR za četrtek in petek napoveduje najvišjo temperaturo {temp(f12['tmax'])} in {temp(f13['tmax'])} ob dežju. "
        f"V soboto, 14. novembra, naj bi bila najvišja {temp(f14['tmax'])}, najnižja {temp(f14['tmin'])}, verjetnost zmrzali pa {pf}{NBSP}%. "
        "To je modelska napoved in ne uradno opozorilo. Podrobnosti o možnosti snega ob koncu tedna sem zapisal "
        '<a href="/blog/sneg-v-nizinah-cetrtek-dez-sobota-1109.html" style="color:var(--blue)">v članku o snegu v nižinah</a>.',
    ]

    omejitve = [
        "<ul>"
        "<li><strong>Šest let je malo.</strong> Primerjava velja za Rečico in leta od 2020 do 2025. Razlika v enem letu spremeni »4 od 6« v »3 od 6«, zato iz tega ni mogoče sklepati na dolgoročno pravilo.</li>"
        "<li><strong>Merilo je moja izbira.</strong> Prag 15 °C in sedemdnevno okno nista uradni opredelitvi »Martinovega poletja«. Z drugim pragom bi bile številke drugačne.</li>"
        "<li><strong>Snega postaja ne meri.</strong> Zato se reki o snegu na Martinovo s temi podatki ne dajo preveriti in jih članek ne trdi ne zanika.</li>"
        "<li><strong>Ena postaja na dnu doline.</strong> V gozdovih in na višjih legah je lahko drugače.</li>"
        "<li><strong>Manjkajoči dnevi.</strong> Leta 2025 v arhivu postaje manjkajo dnevi od 20. do 23. novembra. Martinovega tedna to ne zadeva, tedne od 14. do 23. 11. pa računam samo iz petih let.</li>"
        "<li><strong>Napoved je modelska.</strong> MTR je poskusni lokalni model in se spreminja z vsakim tekom.</li>"
        "</ul>",
    ]
    p6 = [
        "Praktično sporočilo: za Martinovo se ne zanašajte na topel dan, a tudi ne na zimo. Aktualno napoved za Rečico najdete na "
        f'<a href="{SITE}/vreme-recica-ob-savinji/" style="color:var(--blue)">strani z vremenom za Rečico ob Savinji</a>.',
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    title = "Ali je Martinovo res toplo? Šest let podatkov"
    assert len(title) <= 60, len(title)
    desc = f"Martinovo v Rečici: najvišja temperatura od {n1(min(hi11))} do {n1(max(hi11))} °C, povprečno {n1(mean11)} °C, kot običajen november. Šest let podatkov."
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Martinovo ni toplejše od običajnega novembra", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — kontrola", "heading": "Topli dnevi se redčijo skozi ves november", "id": "kontrola", "paragraphs": p2},
        {"label": "03 — po letih", "heading": "Zjutraj mraz, popoldne skoraj poletje", "id": "leta", "paragraphs": p3},
        {"label": "04 — letos", "heading": "Letos: včeraj 14,3 °C, ob koncu tedna po napovedi mraz", "id": "letos", "paragraphs": letos},
        {"label": "05 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
        {"label": "06 — kaj naprej", "heading": "Kaj to pomeni za Martinovo?", "id": "naprej", "paragraphs": p6},
    ]
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["martinovo", "temperatura", "november", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "weather-station", "og_accent_hex": "#34d399",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: postaja IREICA1 (dnevne najvišje, najnižje in povprečne temperature ter padavine, zunanji senzor, 2020–2026, podatki do 10. 11. 2026); "
                         "model MTR (napoved za 12.–14. 11. 2026, živa osvežitev 11. 11. 2026). Podatki: history.json."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"<script.*?</script>", "", h, flags=re.S)
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
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    if "--allow-date" not in sys.argv:
        assert datetime.date.today().isoformat() == SNAPSHOT_DATE, \
            f"članek je posnetek za {SNAPSHOT_DATE}; drug dan besedilo (»danes«) ne drži -- uporabi --allow-date samo po pregledu"
    H, live = load()
    article = build_article(H, live)
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
        og_title="Je Martinovo\nres toplo?", meta_note="podatkovna analiza",
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
