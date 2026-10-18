#!/usr/bin/env python3
"""
tools/generate_slana_gobe_post.py -- »Ali prva slana konča gobarsko sezono? Šest let podatkov« (18. 10. 2026).

Ročno napisan podatkovni članek (nadaljevanje članka o vrhu gobarske sezone). Vse številke v besedilu, grafih
in tabelah pridejo iz treh committanih virov:
  - history.json                       (postaja IREICA1: najnižja dnevna temperatura, samo zunanja meritev),
  - data/inat-glive-po-tednih.json     (iNaturalist, število opažanj po tednih; tools/study_inat_glive_po_tednih.py),
  - data/tla-temperatura-dnevna.json   (Open-Meteo archive, ERA5-Land, povprečje plasti 0-7 in 7-28 cm;
                                        `--fetch-tla` ga osveži; samo dnevna povprečja)
ter iz species_rules.yaml (pragovi vrst v gobarskem modelu). Besedilo nič ne izmišlja; trditve varujejo
assert-i: če se podatki osvežijo in trditev ne drži več, generator pade -- besedilo je treba pregledati,
ne zaobiti asserta.

Članek je posnetek na dan objave in se ne prepisuje samodejno. Po CLAUDE.md gre ročni članek skozi lekturo
(`lektura.yml` je od 2. 10. 2026 izklopljena -- do ponovnega vklopa ostane slogovni pregled po
docs/slog-pisanja.md). Notranjih meritev postaje članek ne uporablja (samo `tempLow` zunanjega senzorja).

Usage:
    python3 tools/generate_slana_gobe_post.py [--fetch-tla] [--dry-run] [--text] [--wire] [--force]
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
INAT = os.path.join(ROOT, "data", "inat-glive-po-tednih.json")
TLA = os.path.join(ROOT, "data", "tla-temperatura-dnevna.json")
RULES = os.path.join(ROOT, "species_rules.yaml")
MODEL = os.path.join(ROOT, "napoved-modela.json")
INDEX_HIST = os.path.join(ROOT, "gobarska-napoved", "indeks-zgodovina.json")
SLUG = "slana-gobarska-sezona-1018"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-slana-gobe.txt")
NBSP = " "
LAT, LON = 46.3167, 14.9167                              # Rečica ob Savinji (kot v gobarskem modelu: dno doline)
GREEN, AMBER, CYAN, GREY = "#34d399", "#fbbf24", "#22d3ee", "#8aa0bd"
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"
SURFACE = "#0a0f1c"
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LAST = 2026
SOIL_THR = (7.5, 3.5)                                    # 7,5 °C: lisička/marela/črna trobenta; 3,5 °C: jurček/sirovka
USER_AGENT = "meteorec.si analiza (filip.eremita@gmail.com)"


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def temp(x, d=1):
    return f"{num(x, d)}{NBSP}°C".replace("-", "–")


def dm(d):
    return f"{d.day}. {d.month}."


_MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
        "novembra", "decembra"]


def dlong(d):
    return f"{d.day}. {_MES[d.month]}"


def md(d):
    return (d.month, d.day)


def week_label(start):
    e = start + datetime.timedelta(6)
    if start.month == e.month:
        return f"{start.day}.–{e.day}. {e.month}."
    return f"{start.day}. {start.month}.–{e.day}. {e.month}."


_NOM = ["nič", "ena", "dve", "tri", "štiri", "pet", "šest", "sedem", "osem", "devet", "deset"]
_GEN = ["nič", "ene", "dveh", "treh", "štirih", "petih", "šestih", "sedmih", "osmih", "devetih", "desetih"]


def numw(n):
    return _NOM[int(n)] if 2 <= int(n) <= 10 else str(int(n))


def numg(n):
    return _GEN[int(n)] if 2 <= int(n) <= 10 else str(int(n))


# ───────────────────────── podatki ─────────────────────────

def fetch_tla():
    """Dnevna povprečja temperature tal (0-7 in 7-28 cm, povprečje obeh) za Rečico, 1. 9.–31. 12. 2020–2026."""
    import urllib.request
    end = min(datetime.date.today() - datetime.timedelta(days=2), datetime.date(LAST, 12, 31))
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=%s&longitude=%s&start_date=2020-09-01&end_date=%s"
           "&hourly=soil_temperature_0_to_7cm,soil_temperature_7_to_28cm&timezone=Europe%%2FLjubljana" % (LAT, LON, end))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    j = json.load(urllib.request.urlopen(req, timeout=90))
    h = j["hourly"]
    day = {}
    for ts, a, b in zip(h["time"], h["soil_temperature_0_to_7cm"], h["soil_temperature_7_to_28cm"]):
        if a is None or b is None:
            continue
        day.setdefault(ts[:10], []).append((a + b) / 2)
    out = {d: round(sum(v) / len(v), 2) for d, v in sorted(day.items())
           if len(v) >= 20 and "09-01" <= d[5:] <= "12-31"}
    doc = {"_meta": {"vir": "Open-Meteo archive API (ERA5-Land), povprečje plasti 0-7 in 7-28 cm",
                     "tocka": [LAT, LON], "generirano": datetime.date.today().isoformat(),
                     "opomba": "dnevna povprečja (vsaj 20 ur podatkov), 1. 9.–31. 12."},
           "dnevi": out}
    with open(TLA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {os.path.relpath(TLA, ROOT)}: {len(out)} dni")


def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    I = json.load(open(INAT, encoding="utf-8"))
    T = json.load(open(TLA, encoding="utf-8"))
    wk = {datetime.date.fromisoformat(k): v for k, v in sorted(I["tedni"].items())}
    soil = {k: v for k, v in T["dnevi"].items()}
    return H, I, wk, soil, T["_meta"]


def first_night(H, y, thr):
    """Prva noč od 1. 9. z najnižjo dnevno temperaturo <= thr (postaja IREICA1, zunanji senzor)."""
    for d in sorted(H):
        if d.startswith(str(y)) and d[5:] >= "09-01" and H[d].get("tempLow") is not None and H[d]["tempLow"] <= thr:
            return datetime.date.fromisoformat(d)
    return None


def soil_cross(soil, y, thr):
    """Prvi dan od 1. 10., ko je sedemdnevno povprečje temperature tal pod pragom."""
    days = sorted(d for d in soil if d.startswith(str(y)))
    for d in days:
        if d < f"{y}-10-01":
            continue
        x = datetime.date.fromisoformat(d)
        vals = [soil.get((x - datetime.timedelta(k)).isoformat()) for k in range(7)]
        if None in vals:
            continue
        if sum(vals) / 7 < thr:
            return x
    return None


def peak_and_drop(wk, y):
    ser = [(s, v["basidio"]) for s, v in wk.items() if datetime.date(y, 9, 1) <= s <= datetime.date(y, 12, 10)]
    peak = max(ser, key=lambda x: x[1])
    drop = next((s for s, c in ser if s > peak[0] and c < 0.5 * peak[1]), None)
    return peak, drop


def window_change(wk, y, key):
    A = [v[key] for s, v in wk.items() if datetime.date(y, 10, 13) <= s <= datetime.date(y, 10, 29)]
    B = [v[key] for s, v in wk.items() if datetime.date(y, 11, 3) <= s <= datetime.date(y, 11, 19)]
    assert len(A) == 3 and len(B) == 3, (y, len(A), len(B))
    return sum(A), sum(B)


def share_window(wk, y):
    ga, gb = window_change(wk, y, "basidio")
    va, vb = window_change(wk, y, "vse")
    return 100 * ga / va, 100 * gb / vb


# ───────────────────────── grafi (inline SVG) ─────────────────────────

def timeline_chart(rows, w=460):
    """rows = [{leto, frost0, frost2, peak, drop}]; x = dnevi od 1. 10. (0 = 1. 10., 60 = 30. 11.)."""
    pl, pr, pt, pb = 40, 14, 22, 32
    rh = 38
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    X = lambda d: pl + iw * (d - datetime.date(d.year, 10, 1)).days / 60
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Prva ničelna noč, prva noč pod –2 °C, vrh opažanj gob in padec pod polovico vrha po letih" '
         'xmlns="http://www.w3.org/2000/svg">']
    base = pt + rh * len(rows)
    for off, lab in ((0, "1. 10."), (14, "15. 10."), (31, "1. 11."), (45, "15. 11."), (60, "30. 11.")):
        x = pl + iw * off / 60
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{lab}</text>')
    for i, r in enumerate(rows):
        y = r["leto"]
        cy = pt + rh * i + rh / 2
        p.append(f'<text x="{pl - 8}" y="{cy + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{y}</text>')
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        # prva noč pod –2 °C (obrisan romb)
        d2 = r["frost2"]
        if d2:
            x = X(d2)
            p.append(f'<path d="M{x:.1f},{cy - 8:.1f} L{x + 7:.1f},{cy:.1f} L{x:.1f},{cy + 8:.1f} L{x - 7:.1f},{cy:.1f} Z" '
                     f'fill="{SURFACE}" stroke="{CYAN}" stroke-width="2"><title>{y}: prva noč pod –2 °C, {dm(d2)}</title></path>')
        # prva ničelna noč (poln romb)
        d0 = r["frost0"]
        if d0:
            x = X(d0)
            p.append(f'<path d="M{x:.1f},{cy - 6.5:.1f} L{x + 5.5:.1f},{cy:.1f} L{x:.1f},{cy + 6.5:.1f} L{x - 5.5:.1f},{cy:.1f} Z" '
                     f'fill="{CYAN}" stroke="{SURFACE}" stroke-width="1.5"><title>{y}: prva noč z 0 °C ali manj, {dm(d0)}</title></path>')
        # padec pod polovico vrha (obroč)
        dd = r["drop"]
        if dd:
            x = X(dd + datetime.timedelta(3))
            p.append(f'<circle cx="{x:.1f}" cy="{cy - 13:.1f}" r="5.5" fill="none" stroke="{AMBER}" stroke-width="2.2">'
                     f'<title>{y}: prvi teden pod polovico vrha, {week_label(dd)}</title></circle>')
        # teden z največ opaženimi gobami (zelena pika)
        dp = r["peak"]
        x = X(dp + datetime.timedelta(3))
        p.append(f'<circle cx="{x:.1f}" cy="{cy - 13:.1f}" r="5.5" fill="{GREEN}" stroke="{SURFACE}" stroke-width="1.8">'
                 f'<title>{y}: teden z največ opaženimi gobami, {week_label(dp)}</title></circle>')
    p.append("</svg>")
    return "".join(p)


def change_chart(rows, w=460):
    """rows = [(leto, upad_gobe_%, upad_vse_%)] -- dve vodoravni vrstici na leto (zelena: gobe, siva: vsa opažanja)."""
    pl, pr, pt, pb = 40, 44, 14, 28
    rh = 36
    h = pt + pb + rh * len(rows)
    iw = w - pl - pr
    top = 100
    X = lambda v: pl + iw * v / top
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Upad števila opažanj od druge polovice oktobra do novembra: gobe in vsa opažanja" '
         'xmlns="http://www.w3.org/2000/svg">']
    base = pt + rh * len(rows)
    for t in (0, 25, 50, 75, 100):
        x = X(t)
        p.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pt}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{base + 16}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{t}{NBSP}%</text>')
    for i, (y, g, a) in enumerate(rows):
        y0 = pt + rh * i
        p.append(f'<text x="{pl - 8}" y="{y0 + rh / 2 + 4:.1f}" text-anchor="end" font-size="11.5" fill="{INK}">{y}</text>')
        for j, (v, col, nm) in enumerate(((g, GREEN, "gobe"), (a, GREY, "vsa opažanja"))):
            by = y0 + 5 + j * 13
            p.append(f'<rect x="{pl}" y="{by:.1f}" width="{max(X(v) - pl, 1):.1f}" height="10" rx="2" fill="{col}">'
                     f'<title>{y}: {nm}, upad {round(v)} %</title></rect>')
            p.append(f'<text x="{X(v) + 5:.1f}" y="{by + 8.5:.1f}" font-size="10.5" fill="{INK}">{round(v)}{NBSP}%</text>')
    p.append("</svg>")
    return "".join(p)


def legend(entries):
    out = []
    for n, kind, c in entries:
        cls = {"dia": "vs-dia", "diaring": "vs-diaring", "dot": "vs-dot", "ring": "vs-ring"}.get(kind, "")
        if kind == "diaring":
            sw = f'<i class="{cls}" style="border-color:{c}"></i>'
        elif kind == "ring":
            sw = f'<i class="{cls}" style="border-color:{c}"></i>'
        elif cls:
            sw = f'<i class="{cls}" style="background:{c}"></i>'
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
.vs-leg i.vs-dot{border-radius:50%}
.vs-leg i.vs-ring{border-radius:50%;background:none;border:2px solid}
.vs-leg i.vs-dia{border-radius:2px;transform:rotate(45deg) scale(.85)}
.vs-leg i.vs-diaring{border-radius:2px;background:none;border:2px solid;transform:rotate(45deg) scale(.85)}
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

def species_rows():
    import yaml
    sp = {s["id"]: s for s in yaml.safe_load(open(RULES, encoding="utf-8"))["species"]}
    spec = [  # (id, ime v besedilu, merilo)
        ("cantharellus_cibarius", "Lisička", "tla"), ("macrolepiota_procera", "Orjaški dežnik (marela)", "tla"),
        ("hydnum_repandum", "Rumeni ježek", "tla"), ("boletus_edulis", "Jurček", "tla"),
        ("lactarius_deliciosus", "Užitna sirovka", "tla"), ("tricholoma_portentosum", "Zimska kolobarnica", "tla"),
        ("hygrophorus_hypothejus", "Zimska polževka", "tla"),
        ("armillaria_mellea", "Štorovka (sivorumena mraznica)", "zrak"), ("pleurotus_ostreatus", "Bukov ostrigar", "zrak"),
        ("flammulina_velutipes", "Zimska panjevka", "zrak"),
    ]
    rows = []
    for sid, name, how in spec:
        s = sp[sid]
        assert s.get("verified") is True and s.get("gets_index") is True, sid
        t = s["soil_temp"]["min"] if how == "tla" else s["air_temp"]["min"]
        a, b = s["season"]["start"], s["season"]["end"]
        rows.append((name, "tla" if how == "tla" else "zrak", t, f"{int(a[3:])}. {int(a[:2])}.–{int(b[3:])}. {int(b[:2])}."))
    return rows


def build_article(H, I, wk, soil, soil_meta):
    P = I["povzetek"]["basidio"]
    last_day = max(H)
    last = datetime.date.fromisoformat(last_day)
    rows, data = [], {}
    for y in YEARS:
        peak, drop = peak_and_drop(wk, y)
        assert peak[0].isoformat() == P[str(y)]["teden_z_najvec"]["zacetek"], y
        f0, f2 = first_night(H, y, 0.0), first_night(H, y, -2.0)
        s75, s35 = soil_cross(soil, y, SOIL_THR[0]), soil_cross(soil, y, SOIL_THR[1])
        g = window_change(wk, y, "basidio")
        a = window_change(wk, y, "vse")
        sh = share_window(wk, y)
        data[y] = dict(peak=peak[0], peak_n=peak[1], drop=drop, f0=f0, f2=f2, s75=s75, s35=s35,
                       dg=100 * (1 - g[1] / g[0]), da=100 * (1 - a[1] / a[0]), sh=sh, g=g, a=a)
        rows.append({"leto": y, "frost0": f0, "frost2": f2, "peak": peak[0], "drop": drop})

    # --- trditve članka: če podatki tega ne kažejo več, generator pade ---
    early = [y for y in YEARS if data[y]["f0"] and data[y]["f0"].month == 10]
    late = [y for y in YEARS if y not in early]
    assert early == [2020, 2021, 2023, 2025], early
    assert late == [2022, 2024] and data[2022]["f0"] == datetime.date(2022, 11, 20) and data[2024]["f0"] == datetime.date(2024, 11, 4)
    for y in early:                                           # vrh opažanj gob je bil po prvi ničelni noči
        assert data[y]["peak"] > data[y]["f0"], y
    for y in late:                                            # ... in pri poznih slanah pred njo
        assert data[y]["peak"] < data[y]["f0"], y
    drops = {y: data[y]["drop"] for y in YEARS}
    n_nov4 = sum(1 for y in YEARS if (drops[y].month, drops[y].day) == (11, 4))
    assert n_nov4 == 5 and (drops[2021].month, drops[2021].day) == (10, 28), drops
    assert data[2022]["f0"] > data[2022]["drop"] + datetime.timedelta(days=14)    # 2022: padec brez slane
    assert (data[2025]["drop"] - data[2025]["f0"]).days >= 28                    # 2025: slana mesec prej
    cold_before_nov = [y for y in YEARS if data[y]["f2"] and data[y]["f2"].month == 10]
    assert cold_before_nov == [2021], cold_before_nov
    for y in YEARS:                                           # splošen upad v drugi polovici novembra
        assert data[y]["dg"] > 30 and data[y]["da"] > 30, y
    n_share_down = sum(1 for y in YEARS if data[y]["sh"][1] < data[y]["sh"][0])
    assert n_share_down == 5, n_share_down
    for y in YEARS:                                           # tla niso pod 3,5 °C pred sredino novembra
        assert data[y]["s35"] >= datetime.date(y, 11, 17), (y, data[y]["s35"])
    assert data[2021]["s75"] == datetime.date(2021, 10, 29)
    for y in YEARS:
        if y != 2021:
            assert data[y]["s75"] >= datetime.date(y, 11, 10), (y, data[y]["s75"])
    assert data[2021]["f2"].month == 10 and data[2021]["f2"] == datetime.date(2021, 10, 14)

    for y in YEARS:                                           # »do istega datuma« v letosnjem odstavku
        cut = datetime.date(y, last.month, last.day)
        assert (data[y]["f0"] is not None and data[y]["f0"] <= cut) == (y in early), (y, cut)
    assert [y for y in YEARS if y in late] == [2022, 2024]
    this_f0 = first_night(H, LAST, 0.0)
    assert this_f0 is None, "letos je že bila ničelna noč -- odstavek »letos« in naslov je treba predelati"
    this_min = min((H[d]["tempLow"], d) for d in H if d.startswith(str(LAST)) and "09-01" <= d[5:] and H[d].get("tempLow") is not None)
    soil_last_d = max(d for d in soil if d.startswith(str(LAST)))
    soil_last = soil[soil_last_d]
    mdl = json.load(open(MODEL, encoding="utf-8"))
    fdays = [r for r in (mdl.get("days") or mdl.get("napoved") or []) if r.get("date") and r.get("p_frost") is not None]
    ih = json.load(open(INDEX_HIST, encoding="utf-8"))
    idx_last = ih[-1]
    gen = I["_meta"]["generirano"]

    pw = lambda lst: ", ".join(str(y) for y in lst)
    lead = (f"V {numg(len(early))} od {numg(len(YEARS))} jeseni, 2020–2025, je bila na postaji v Rečici prva noč z 0{NBSP}°C ali manj že oktobra. "
            f"V vseh {numg(len(early))} je bil teden z največ opaženimi gobami v Sloveniji šele po njej. "
            "Prva slana torej ne konča gobarske sezone. Podatki sicer pokažejo, kdaj se val gob umiri, a to ni takrat, ko pade prva slana.")

    # tabela 1: leto | prva noč ≤0 | ≤-2 | vrh | padec
    t1 = table(["Leto", "Prva noč ≤ 0 °C", "Prva noč ≤ –2 °C", "Teden z največ gobami", "Prvi teden pod polovico vrha"],
               [[str(y), dm(data[y]["f0"]), dm(data[y]["f2"]), week_label(data[y]["peak"]), week_label(data[y]["drop"])] for y in YEARS],
               cap="Prva noč z mrazom, vrh opažanj gob in padec pod polovico vrha po letih",
               note="Temperatura: postaja IREICA1, najnižja dnevna vrednost od 1. 9. Opažanja: iNaturalist, Slovenija, deblo Basidiomycota; "
                    "teden se začne 1. 7. in teče po sedem dni.")
    f_timeline = fig("Kdaj je padla slana in kdaj je bil vrh gob",
                     legend([("prva noč z 0 °C ali manj", "dia", CYAN), ("prva noč pod –2 °C", "diaring", CYAN),
                             ("teden z največ opaženimi gobami", "dot", GREEN), ("prvi teden pod polovico vrha", "ring", AMBER)])
                     + timeline_chart(rows),
                     "Zelena pika je sredina tedna z največ opaženimi gobami, oranžni obroč sredina prvega tedna po vrhu, ko je bilo gob manj kot polovica vrha. "
                     "Modra romba sta prvi noči z mrazom na postaji.")

    # tabela 2: padec
    t2 = table(["Leto", "Gobe 13.–29. 10.", "Gobe 3.–19. 11.", "Upad gob", "Upad vseh opažanj", "Delež gob prej → pozneje"],
               [[str(y), str(data[y]["g"][0]), str(data[y]["g"][1]), f"{round(data[y]['dg'])}{NBSP}%", f"{round(data[y]['da'])}{NBSP}%",
                 f"{round(data[y]['sh'][0])} → {round(data[y]['sh'][1])}{NBSP}%"] for y in YEARS],
               cap="Število opažanj gob in vseh opažanj v drugi polovici oktobra in v novembru",
               note="Vsota treh tednov, ki se začnejo med 13. in 29. 10. oziroma med 3. in 19. 11. Delež = opažanja gob med vsemi opažanji.")
    f_change = fig("Upad opažanj od druge polovice oktobra do novembra",
                   legend([("gobe", "sq", GREEN), ("vsa opažanja (rastline, žuželke, ptice …)", "sq", GREY)])
                   + change_chart([(y, data[y]["dg"], data[y]["da"]) for y in YEARS]),
                   "Primerjava vsote treh tednov v drugi polovici oktobra z vsoto treh tednov v novembru. V petih od šestih let je zelena vrstica daljša od sive: gobe upadejo bolj kot vsa opažanja.")

    # tabela 3: tla
    def d_or_dash(d):
        return dm(d) if d else "še ne"
    t3 = table(["Leto", f"Tla pod 7,5{NBSP}°C", f"Tla pod 3,5{NBSP}°C", "Teden z največ gobami"],
               [[str(y), d_or_dash(data[y]["s75"]), d_or_dash(data[y]["s35"]), week_label(data[y]["peak"])] for y in YEARS],
               cap="Kdaj so tla v dolini padla pod pragova vrst, in vrh opažanj gob",
               note="Prvi dan od 1. 10., ko je sedemdnevno povprečje temperature tal (povprečje plasti 0–7 in 7–28 cm, Open-Meteo, reanaliza ERA5-Land za Rečico) pod pragom.")

    sp_rows = species_rows()
    t4 = table(["Vrsta", "Merilo", "Najnižja temperatura v bazi vrst", "Sezona v bazi"],
               [[n, m, temp(t, 1), s] for n, m, t, s in sp_rows],
               cap="Najnižja temperatura, pri kateri baza vrst gobarskega modela še dopušča rast",
               note="Vir: baza vrst gobarskega modela Meteorec (species_rules.yaml). Za mikorizne vrste je merilo temperatura tal, za lesne vrste temperatura zraka. "
                    "To so parametri modela, ne laboratorijske meritve.")

    nums_f = [r for r in fdays][:3]
    fc_txt = ""
    if nums_f:
        mx = max(r["p_frost"] for r in nums_f)
        d0 = datetime.date.fromisoformat(nums_f[0]["date"])
        d1 = datetime.date.fromisoformat(nums_f[-1]["date"])
        assert mx < 0.005 and d0.month == d1.month, "napoved zmrzali ni več 0 % -- odstavek je treba predelati"
        fc_txt = f"Napoved modela MTR za Rečico za {d0.day}.–{d1.day}. {d1.month}. zmrzali ne vidi (verjetnost 0{NBSP}%)."

    p1 = [
        "<strong>Kratek odgovor: ne.</strong> V vseh štirih letih, ko je prva ničelna noč padla oktobra (2020, 2021, 2023 in 2025), je bil teden z največ opaženimi gobami "
        "po njej. V letih 2022 in 2024, ko je prva slana prišla šele novembra, je bil vrh pred njo.",
        t1,
        f_timeline,
        "Pazite na razliko: <strong>prva slana na postaji ni isto kot slana na travi</strong>. Postaja meri temperaturo zraka, trava in tla pa ob jasni noči "
        'ohlajata hitreje. Zakaj se trava pobeli, ko postaja kaže še nad ničlo, sem razložil <a href="/blog/slana-pri-1-7-c-zakaj-trava-pobeli-prej-kot-postaja-1004.html" '
        'style="color:var(--blue)">v članku o slani pri 1,7 °C</a>. Tukaj štejem samo noči, ko je postaja izmerila 0 °C ali manj.',
    ]
    p2 = [
        f"Kdaj se potem val umiri? Število opaženih gob je padlo pod polovico vrha skoraj vsako leto v istem tednu: <strong>od 4. do 10. novembra v petih od šestih let</strong> "
        f"(leta 2021 teden prej, od 28. oktobra do 3. novembra).",
        f"Pozorni bodite na dve leti. Leta 2022 postaja do 20. novembra ni izmerila nobene noči z 0 °C ali manj, pa je število opaženih gob "
        f"v tednu od 4. novembra padlo z {wk[datetime.date(2022, 10, 28)]['basidio']} na {wk[datetime.date(2022, 11, 4)]['basidio']}. "
        f"Leta 2025 je bila prva ničelna noč že {dlong(data[2025]['f0'])}, val pa je zdržal še več kot mesec dni: "
        f"v tednu od 21. oktobra je bilo {wk[datetime.date(2025, 10, 21)]['basidio']} opažanj, to je bil vrh tistega leta.",
        f_change,
        t2,
        "Treba je poudariti, da <strong>novembra upade število vseh opažanj</strong> (rastline, žuželke, ptice, glive), ne samo gob. "
        f"Gobe so upadle za {round(min(data[y]['dg'] for y in YEARS))}–{round(max(data[y]['dg'] for y in YEARS))}{NBSP}%, vsa opažanja za "
        f"{round(min(data[y]['da'] for y in YEARS))}–{round(max(data[y]['da'] for y in YEARS))}{NBSP}%. "
        f"Gobe upadejo nekoliko bolj: njihov delež med vsemi opažanji je upadel v petih od šestih let. Zakaj, iz teh podatkov ne morem ločiti: "
        "lahko gre za manj gob v gozdu, lahko za manj ljudi, ki gredo novembra s telefonom v gozd.",
    ]
    p3 = [
        "V gobarskem modelu za večino vrst odloča temperatura tal, ne zraka. Zrak ponoči pade pod ničlo hitro, tla pod gozdno steljo se običajno ohlajajo počasneje.",
        f"Po bazi vrst gobarskega modela jurček in užitna sirovka potrebujeta tla toplejša od {num(3.5)}{NBSP}°C, lisička, marela in črna trobenta pa od {num(7.5)}{NBSP}°C. "
        f"V šestih letih so tla v Rečici (povprečje plasti 0–7 in 7–28 cm) padla pod 3,5{NBSP}°C šele v razponu od "
        f"{dlong(min((data[y]['s35'] for y in YEARS), key=md))} do {dlong(max((data[y]['s35'] for y in YEARS), key=md))}, pod 7,5{NBSP}°C pa v razponu od "
        f"{dlong(min((data[y]['s75'] for y in YEARS), key=md))} do {dlong(max((data[y]['s75'] for y in YEARS), key=md))}.",
        t3,
        f"V petih od šestih let so tla ostala nad 7,5{NBSP}°C vsaj do {dlong(min((data[y]['s75'] for y in YEARS if y != 2021), key=md))}, padec števila opaženih gob pa je prišel že 4. novembra. "
        "V teh letih se padec torej ne ujema ne s prvo slano ne s prehladnimi tlemi. Ujema se s koledarjem.",
        f"Izjema je leto 2021. Edino takrat je bila noč pod –2{NBSP}°C že oktobra ({temp(H[data[2021]['f2'].isoformat()]['tempLow'])}, {dlong(data[2021]['f2'])}), "
        f"tla so padla pod 7,5{NBSP}°C že {dlong(data[2021]['s75'])} in val je upadel teden dni prej kot v drugih letih. "
        "Ena jesen je premalo za sklep, zato ne trdim, da huda slana gobe ustavi. Pove le, da vzorca »vedno prvi teden novembra« ne smem razširiti na hladna leta.",
    ]
    p4 = [
        "Ko se jesenska sezona umirja, se začenja zimska. Baza vrst gobarskega modela ima več vrst, ki rastejo pri precej nižjih temperaturah kot lisička ali marela:",
        t4,
        "Zimska kolobarnica in zimska polževka sta v bazi označeni s sezono, ki sega do konca leta. Bukov ostrigar in zimska panjevka rasteta tudi, ko zrak ponoči pade pod ničlo. "
        "Gobe nabirajte samo, če jih zanesljivo poznate: tudi zimske vrste imajo nevarne zamenjave.",
    ]
    letos = [
        f"Letos je bila najnižja temperatura od 1. septembra do {dlong(last)} na postaji {temp(this_min[0])} "
        f"({dlong(datetime.date.fromisoformat(this_min[1]))}). Prve noči z 0{NBSP}°C ali manj torej še ni. Do istega datuma je ni bilo tudi leta 2022 in 2024, "
        f"v ostalih štirih letih ({pw(early)}) pa je do tega datuma že padla.",
        f"Tla so bila {dlong(datetime.date.fromisoformat(soil_last_d))} v povprečju {temp(soil_last)} (Open-Meteo, povprečje plasti 0–7 in 7–28 cm). "
        f"Gobarski indeks za Rečico je bil {dlong(datetime.date.fromisoformat(idx_last['date']))} {idx_last['index']} od 100. "
        + fc_txt,
        'Dež, ki ga napovedujejo za sredo in četrtek, sem obdelal <a href="/blog/gobe-se-ena-priloznost-modeli-dez-1017.html" style="color:var(--blue)">v članku od 17. oktobra</a>.',
    ]
    omejitve = [
        "<ul>"
        "<li><strong>Fotografije niso košare.</strong> Opažanje gobe ne pomeni, da jo je nekdo nabral, in tudi ne, da je užitna. "
        "Poleg tega gre za fotografije gob, ki so jih ljudje naložili na iNaturalist, ne za število gob v gozdu.</li>"
        "<li><strong>Šest let je malo.</strong> Rezultat velja za ta leta in za Slovenijo kot celoto. V Rečici in na višjih legah je lahko drugače.</li>"
        "<li><strong>Prva slana na postaji.</strong> Postaja meri temperaturo zraka na enem mestu v dolini. Slana v gozdu ali na višjih legah je lahko prej.</li>"
        "<li><strong>Letošnje leto je še v teku.</strong> Podatki zadnjega tedna so zaradi zamude pri nalaganju opažanj podcenjeni, zato letošnjega vala ne uvrščam v primerjavo.</li>"
        "<li><strong>Tla so reanaliza, ne meritev.</strong> Temperaturo tal za Rečico prevzemam iz Open-Meteo (ERA5-Land, mreža nekaj kilometrov). Gozdna tla so lahko drugačna.</li>"
        "<li><strong>Prag v bazi vrst ni izmerjena meja rasti.</strong> Gre za parametre modela, zato jih berite kot oceno.</li>"
        "</ul>",
        "V članku uporabljam samo združene podatke. Posameznih opažanj ne objavljam, ker zanje veljajo različni licenčni pogoji. "
        'Zbrane številke so v <a href="/data/inat-glive-po-tednih.json" style="color:var(--blue)">data/inat-glive-po-tednih.json</a>.',
    ]
    p6 = [
        "Praktično sporočilo: prve slane ne jemljite kot konec sezone. Pred odhodom v gozd poglejte "
        f'<a href="{SITE}/gobarska-napoved/danes/" style="color:var(--blue)">gobarsko napoved za danes</a> '
        f'in <a href="{SITE}/gobarska-napoved/valovi/" style="color:var(--blue)">kalkulator rasti po dežju</a>. '
        'O vrhu opažanj gob sem pisal <a href="/blog/vrh-gobarske-sezone-oktober-1014.html" style="color:var(--blue)">v prejšnjem članku</a>.',
        "Gobe nabirajte le, če jih zanesljivo poznate. Nevarne zamenjave najdete na strani "
        f'<a href="{SITE}/gobarska-napoved/strupene-gobe/" style="color:var(--blue)">Strupene gobe</a>.',
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    title = "Ali prva slana konča gobarsko sezono? Šest let podatkov"
    assert len(title) <= 60, len(title)
    desc = ("V vseh štirih letih, ko je prva noč z mrazom padla oktobra, je bil vrh opažanj gob po njej. Slana ni konec sezone. "
            "Podatki postaje in iNaturalista 2020–2025.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Prva slana ni konec sezone", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — november", "heading": "Val se umiri v prvem tednu novembra", "id": "november", "paragraphs": p2},
        {"label": "03 — tla", "heading": "Tla se ohladijo pozneje kot zrak", "id": "tla", "paragraphs": p3},
        {"label": "04 — zimske vrste", "heading": "Po jeseni pridejo zimske vrste", "id": "zimske", "paragraphs": p4},
        {"label": "05 — letos", "heading": "Kaj kaže letošnja jesen?", "id": "letos", "paragraphs": letos},
        {"label": "06 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
        {"label": "07 — nabiranje", "heading": "Kaj to pomeni za nabiranje?", "id": "nabiranje", "paragraphs": p6},
    ]
    def nb(h):                                    # »0 °C«, »38 %« se ne smeta prelomiti čez vrstico
        return re.sub(r"(\d) (°C|%)", lambda m: m.group(1) + NBSP + m.group(2), h)
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "slana", "iNaturalist", "oktober", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "gobe-lastna", "og_accent_hex": "#34d399",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": (f"Viri: postaja IREICA1 (najnižja dnevna temperatura, zunanji senzor, od 7. 11. 2019); iNaturalist (API, število opažanj po tednih v Sloveniji; "
                         f"deblo Basidiomycota; stanje {int(gen[8:10])}. {int(gen[5:7])}. {gen[:4]}); Open-Meteo (ERA5-Land, temperatura tal, točka Rečica ob Savinji); "
                         "baza vrst gobarskega modela Meteorec. Podatki: data/inat-glive-po-tednih.json, data/tla-temperatura-dnevna.json."),
    }


def plain_text(article):
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
    if "--fetch-tla" in sys.argv:
        fetch_tla()
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    H, I, wk, soil, soil_meta = load()
    article = build_article(H, I, wk, soil, soil_meta)
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
        og_title="Ali prva slana\nkonča gobe?", meta_note="podatkovna analiza",
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
