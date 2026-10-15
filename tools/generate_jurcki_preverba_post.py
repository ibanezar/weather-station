#!/usr/bin/env python3
"""
tools/generate_jurcki_preverba_post.py — članek o preverbi napovedi za jurčke (15. 10. 2026)

Nadaljevanje članka »Zakaj po 120 mm dežja v gozdu ni jurčkov« (18. 9. 2026), ki je obljubil preverbo
(»Če se to ne zgodi, bo to zapisano v naslednjem članku«). Ročno zasnovan članek, ne samodejni.

Kaj članek primerja:
  * napoved z dne 18. 9. — številke so prepisane iz objavljenega članka (FORECAST_18_9); dnevne napovedi
    gobarskega modela se ne arhivirajo, zato drugega vira za to ni;
  * izračun ISTEGA modela (`gobe_model.eval_species`, jurček = `boletus_edulis`) z vremenom, kot se je
    zgodilo (Open-Meteo, za Rečico postajni dež iz history.json) — razlika proti napovedi je torej
    napaka napovedi vremena, ne modela;
  * javna opažanja jurčkov (`/gobe/opazovanja` na Workerju): datum, območje, količina. Vnosi so javni in
    NEPREVERJENI; negativnih podatkov (»iskal sem, nisem našel«) ni, zato se napačnih alarmov ne da šteti.

Izhod Open-Meteo in opažanj se shrani v data/gobe-preverba-jurcki-2026-10.json (posnetek na dan zajema),
da je članek ponovljiv in da ponovni zagon ne obremenjuje API-ja. `--refresh` zajame znova.

Notranjih meritev ni nikjer (CLAUDE.md, pravilo na vrhu). Lektura je izklopljena — besedilo je treba
prebrati ročno (docs/slog-pisanja.md).

Usage:
    python3 tools/generate_jurcki_preverba_post.py [--dry-run] [--wire] [--refresh]
"""
import datetime
import json
import os
import re
import statistics as st
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import generate_forecast_test_post as ftp  # noqa: E402
import gobe_model as gm  # noqa: E402
from generate_seo_pages import num  # noqa: E402

ROOT = seo.ROOT
YEAR = 2026
SLUG = "jurcki-preverba-napovedi-1015"
SITE = "https://meteorec.si"
SNAPSHOT = os.path.join(ROOT, "data", "gobe-preverba-jurcki-2026-10.json")
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
SPECIES_ID = "boletus_edulis"
NB = " "

RAIN_DAYS = ("2026-09-10", "2026-09-11")      # sprožilni dež
FORECAST_DATE = "2026-09-18"                  # dan objave napovedi
PRED_WINDOW = ("2026-09-23", "2026-09-30")    # »okno se odpre 23. septembra in traja do konca meseca«
START, END = "2026-09-10", "2026-10-14"
HOME = "Rečica ob Savinji"
CHART_AREAS = [(HOME, "dno doline, 400 m", "#199e70"),
               ("Gozdovi nad Ljubnim", "700 m, kisla podlaga", "#8e6fd8"),
               ("Pod Smrekovcem, južni gozd", "1225 m", "#d95926")]
# Številke iz članka z dne 18. 9. 2026 (blog/zakaj-po-120-mm-dezja-ni-jurckov-0918.html, razdelek »08 – napoved«).
FORECAST_18_9 = [(HOME, "2026-09-21", 42), (HOME, "2026-09-22", 57), (HOME, "2026-09-23", 66),
                 (HOME, "2026-09-24", 71), ("Gozdovi nad Ljubnim", "2026-09-22", 99)]

CSS = """<style>
.data-table{width:100%;border-collapse:collapse;font-size:.92rem;margin:.2rem 0}
.data-table th{text-align:left;font-weight:600;font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);padding:.5rem .7rem;border-bottom:1px solid var(--card-border);white-space:nowrap}
.data-table td{padding:.62rem .7rem;border-bottom:1px solid rgba(255,255,255,.06)}
.data-table tr:last-child td{border-bottom:0}
.table-scroll{overflow-x:auto;margin:1.2rem 0 1.6rem;border:1px solid var(--card-border);border-radius:12px;background:var(--card-bg)}
.mini-stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.4rem 0 2rem}
.mini-stat{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:.9rem .8rem;text-align:center}
.ms-label{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-family:'JetBrains Mono',monospace}
.ms-val{font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:1.4rem;line-height:1.1;margin:.18rem 0 .1rem;color:var(--cyan)}
.ms-sub{font-size:.72rem;color:var(--muted)}
@media(max-width:640px){.mini-stat-grid{grid-template-columns:repeat(2,1fr)}}
.sg-fig{position:relative;margin:1.4rem 0 .4rem}
.sg-fig svg{width:100%;height:auto;display:block}
.sg-fig text{font-family:'Inter',system-ui,sans-serif;font-size:13px;fill:var(--muted)}
.sg-fig .sg-t{font-size:15px;font-weight:700;fill:var(--text,#e8ecef)}
.sg-fig .sg-v{font-size:13px;font-weight:700;fill:var(--text,#e8ecef);paint-order:stroke;stroke:var(--bg,#0a0f1c);stroke-width:4px;stroke-linejoin:round}
.sg-cap{font-size:.8rem;color:var(--muted);margin:.2rem 0 1.4rem}
.disclaimer{background:rgba(239,68,68,.06);border:1px solid var(--card-border);border-radius:10px;padding:.8rem 1rem;margin:1.2rem 0;font-size:.85rem;color:var(--muted)}
.sources{font-size:.82rem;color:var(--muted);border-top:1px solid rgba(255,255,255,.07);margin-top:2.2rem;padding-top:1rem;line-height:1.7}
</style>"""


# ── pomožne funkcije ─────────────────────────────────────────────────────────

def d_short(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def d_long(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {seo.MES_GEN[d.month]}"


def d_add(iso, n):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=n)).isoformat()


def d_between(a, b):
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


def drange(a, b):
    d = a
    while d <= b:
        yield d
        d = d_add(d, 1)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": WORKER_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="table-scroll" tabindex="0"><table class="data-table"><thead><tr>{th}</tr></thead>'
            f'<tbody>{tr}</tbody></table></div>')


# ── podatki ──────────────────────────────────────────────────────────────────

def is_porcino(name):
    n = name.lower()
    return "jurček" in n or "jurcek" in n or "goban" in n


def fetch_snapshot():
    rules = gm.load_rules()
    spots, _ = gm.load_locations(rules)
    byname = {s["name"]: s for s in spots}
    obs_all = get_json(PROXY + "/gobe/opazovanja?dni=120")["opazovanja"]
    obs = sorted(({"date": o["ts"][:10], "area": o["obmocje"], "qty": o["kolicina"]}
                  for o in obs_all if is_porcino(o["vrsta"])), key=lambda x: (x["date"], x["area"]))
    missing = {o["area"] for o in obs if o["area"] not in byname}
    if missing:
        raise SystemExit(f"opažanje na območju, ki ga model ne pozna: {sorted(missing)}")
    areas = sorted({o["area"] for o in obs} | {a for a, _, _ in CHART_AREAS})
    sub = [byname[a] for a in areas]
    locs = gm.fetch_forecast(sub, 60)
    sp = next(x for x in rules["species"] if x["id"] == SPECIES_ID)
    hist = gm.load_station_precip()
    hind = {}
    for spot, loc in zip(sub, locs):
        series = gm.build_series(loc, hist if spot.get("home") else None)
        row = {}
        for i, d in enumerate(series["dates"]):
            if START <= d <= END:
                r = gm.eval_species(sp, series, i, datetime.date.fromisoformat(d), spot, rules)
                row[d] = {"idx": r["index"], "comp": r["components"],
                          "soil": None if series["soil_temp"][i] is None else round(series["soil_temp"][i], 1),
                          "tmin": series["tmin"][i]}
        hind[spot["name"]] = {"elev": spot["elev_m"], "terrain": spot.get("terrain"), "days": row}
    rain = {d: gm.load_station_precip().get(d) for d in RAIN_DAYS}
    snap = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "model_version": gm.MODEL_VERSION, "obs_total": len(obs_all), "obs": obs, "hind": hind,
            "rain": rain, "lag": [int(sp["fruiting_lag_days"]["min"]), int(sp["fruiting_lag_days"]["max"])],
            "rain_min": float(sp["rain_7d_min"])}
    with open(SNAPSHOT, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    return snap


def load_data():
    if "--refresh" in sys.argv or not os.path.exists(SNAPSHOT):
        return fetch_snapshot()
    return json.load(open(SNAPSHOT, encoding="utf-8"))


TERRAIN = {"kisla": "kisla podlaga", "bazicna": "bazična podlaga", "vlazna": "vlažna tla", None: "podlaga ni določena"}


def analyse(S):
    H = S["hind"]
    idx = lambda a, d: H[a]["days"][d]["idx"]
    rows = []
    for o in S["obs"]:
        a, d = o["area"], o["date"]
        rows.append({**o, "elev": H[a]["elev"], "terrain": H[a]["terrain"], "idx": idx(a, d),
                     "lvl": gm.level(idx(a, d)), "since": d_between(RAIN_DAYS[0], d),
                     "comp": H[a]["days"][d]["comp"], "soil": H[a]["days"][d]["soil"]})
    good = [r for r in rows if r["idx"] >= 55]
    on = [r["idx"] for r in rows]
    areas = {r["area"] for r in rows}
    allv = [v["idx"] for a in areas for d, v in H[a]["days"].items() if START <= d <= END]
    cmp = [(a, d, p, idx(a, d), idx(a, d) - p) for a, d, p in FORECAST_18_9]
    return {"rows": rows, "good": good, "bad": [r for r in rows if r["idx"] < 55], "med_on": st.median(on),
            "med_all": st.median(allv), "share_all": round(100 * sum(v >= 55 for v in allv) / len(allv)),
            "n_all": len(allv), "cmp": cmp, "max_diff": max(abs(c[4]) for c in cmp)}


# ── graf ─────────────────────────────────────────────────────────────────────

def chart(S, A):
    """Indeks jurčka po dnevih za tri območja; senčeno napovedano okno; krogi = opažanja (indeks območja, kjer je bilo vneseno)."""
    W, Hh = 900, 400
    l, r, t, b = 54, 150, 34, 46
    days = list(drange(START, END))
    n = len(days)
    x = lambda d: l + (W - l - r) * days.index(d) / (n - 1)
    y = lambda v: t + (Hh - t - b) * (1 - v / 100)
    H = S["hind"]
    out = [f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="Indeks jurčka po dnevih od 10. septembra do 14. oktobra za tri območja, '
           f'napovedano okno in opažanja bralcev">']
    out.append('<title>Indeks jurčka po dnevih in opažanja bralcev</title>')
    out.append(f'<text class="sg-t" x="{l}" y="20">Indeks jurčka po dnevih, izračun z dejanskim vremenom</text>')
    # pas »Dobro« (≥ 55)
    out.append(f'<rect x="{l}" y="{y(100):.1f}" width="{W - l - r}" height="{y(55) - y(100):.1f}" fill="rgba(255,255,255,.03)"/>')
    for v in (0, 35, 55, 75, 100):
        out.append(f'<line x1="{l}" x2="{W - r}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="rgba(255,255,255,.09)"/>')
        out.append(f'<text x="{l - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>')
    # napovedano okno
    x0, x1 = x(PRED_WINDOW[0]), x(PRED_WINDOW[1])
    out.append(f'<rect x="{x0:.1f}" y="{t}" width="{x1 - x0:.1f}" height="{Hh - t - b}" fill="rgba(52,211,153,.10)"/>')
    out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{t + 14}" text-anchor="middle">napovedano okno</text>')
    # osi: datumi vsakih 5 dni
    for d in days:
        dd = datetime.date.fromisoformat(d)
        if dd.day in (10, 15, 20, 25, 30) or d == END:
            out.append(f'<text x="{x(d):.1f}" y="{Hh - b + 20}" text-anchor="middle">{dd.day}. {dd.month}.</text>')
            out.append(f'<line x1="{x(d):.1f}" x2="{x(d):.1f}" y1="{Hh - b}" y2="{Hh - b + 5}" stroke="rgba(255,255,255,.3)"/>')
    # črte
    for name, lab, col in CHART_AREAS:
        pts = [(d, H[name]["days"][d]["idx"]) for d in days if d in H[name]["days"]]
        path = " ".join(f"{'M' if i == 0 else 'L'}{x(d):.1f},{y(v):.1f}" for i, (d, v) in enumerate(pts))
        out.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="2.4" stroke-linejoin="round"/>')
        d_last, v_last = pts[-1]
        out.append(f'<text class="sg-v" x="{x(d_last) + 8:.1f}" y="{y(v_last) + 4:.1f}" style="fill:{col}">{lab.split(",")[0] if name == HOME else name.split(",")[0].replace("Gozdovi nad ", "nad ").replace("Pod ", "pod ")}</text>')
    # opažanja
    for o in A["rows"]:
        cx, cy = x(o["date"]), y(o["idx"])
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="var(--bg,#0a0f1c)" stroke="#fff" stroke-width="2">'
                   f'<title>{d_short(o["date"])}: {o["area"]}, indeks {o["idx"]}</title></circle>')
    out.append('</svg>')
    leg = ('<p class="sg-cap">Barvne črte: ' + ", ".join(f'<span style="color:{c}">■</span> {a} ({lab})' for a, lab, c in CHART_AREAS) +
           '. Beli krogi so opažanja jurčka bralcev, narisana pri indeksu območja, na katerem so bila vnesena (ne nujno na eni od treh črt). '
           'Senčen pas je okno, napovedano 18. septembra. Indeks je izračun gobarskega modela z dejanskim vremenom (Open-Meteo, za Rečico dež s postaje), ne meritev.</p>')
    return f'<div class="sg-fig">{"".join(out)}</div>{leg}'


# ── članek ───────────────────────────────────────────────────────────────────

def build_article(S):
    A = analyse(S)
    rows = A["rows"]
    H = S["hind"]
    n = len(rows)
    ng, nb = len(A["good"]), len(A["bad"])
    rain_sum = round(sum(S["rain"].values()), 1)
    days_since = d_between(FORECAST_DATE, S["generated"][:10])
    w_open = PRED_WINDOW[0]

    NUMW = {1: "eno", 2: "dve", 3: "tri", 4: "štiri", 5: "pet", 6: "šest", 7: "sedem", 8: "osem"}
    NUMW_G = {1: "enem", 2: "dveh", 3: "treh", 4: "štirih", 5: "petih", 6: "šestih", 7: "sedmih", 8: "osmih"}

    n_early = "dve"
    assert sum(r["date"] < w_open for r in A["rows"]) == 2
    lead = (f"Pred {days_since} dnevi sem napovedal, da se okno za jurčke v Zgornji Savinjski dolini odpre {d_long(w_open)} in traja "
            f"do konca meseca. Do 14. oktobra so bralci vnesli {NUMW[n]} opažanj jurčka. Pri {NUMW_G[ng]} je model za to območje "
            f"na dan najdbe kazal 55 ali več (»Dobro« ali »Odlično«), pri {NUMW_G[nb]} pa manj ({' in '.join(str(r['idx']) for r in A['bad'])}, »Zmerno«). "
            f"{n_early[0].upper() + n_early[1:]} najdbi sta bili pred napovedanim oknom. "
            f"Napovedani indeks se od izračuna z dejanskim vremenom razlikuje za največ {A['max_diff']} točk.")

    stats = ('<div class="mini-stat-grid">'
             f'<div class="mini-stat"><div class="ms-label">Opažanj jurčka</div><div class="ms-val">{n}</div><div class="ms-sub">20. 9.–14. 10.</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Indeks ≥ 55</div><div class="ms-val">{ng} od {n}</div><div class="ms-sub">na dan najdbe</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Mediana na dan najdbe</div><div class="ms-val">{A["med_on"]:.0f}</div><div class="ms-sub">vsi dnevi teh območij: {A["med_all"]:.0f}</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Največja razlika</div><div class="ms-val">{A["max_diff"]} točk</div><div class="ms-sub">napoved proti izračunu</div></div>'
             '</div>')

    sec1 = [
        ("V članku z dne 18. septembra sem osmi dan po dežju, ko jurčkov v gozdu še ni bilo, zapisal tri trditve, ki jih je mogoče preveriti:"),
        ("<ul>"
         f"<li>Okno za jurčke se odpre <strong>{d_long(w_open)}</strong> in traja do konca meseca.</li>"
         "<li>Indeks jurčka v Rečici naraste na 42 (21. 9.), 57 (22. 9.), 66 (23. 9.) in 71 (24. 9.).</li>"
         "<li>Najprej bodo jurčki rasli nad 600 metri na kisli podlagi: v Gozdovih nad Ljubnim naj bi indeks že 22. septembra dosegel 99.</li>"
         "</ul>"),
        (f"Napoved je temeljila na dveh pogojih: na dežju z {d_long(RAIN_DAYS[0])} in {d_long(RAIN_DAYS[1])} ({num(rain_sum)} mm na postaji IREICA1), "
         f"ki mora biti za mikorizne vrste star {S['lag'][0]} do {S['lag'][1]} dni, in na nočni ohladitvi, ki jo jurček v modelu zahteva "
         "(najnižja temperatura vsaj 3 °C pod povprečjem prejšnjih petih noči). Prvi pogoj je bil takrat že znan, drugi pa je bil odvisen od vremena v naslednjih dneh. "
         "Napoved je bilo zato mogoče preveriti: zadostovalo je počakati."),
    ]

    cmp_rows = []
    for a, d, p, v, diff in A["cmp"]:
        cmp_rows.append([d_short(d), "dno doline (Rečica)" if a == HOME else a, str(p), str(v), f"{diff:+d}".replace("-", "–")])
    sec2 = [
        (f"Napoved z dne 18. septembra je uporabila napoved vremena. Zdaj sem isti model (različica {S['model_version']}) pognal z vremenom, "
         "kakršno je dejansko bilo: Open-Meteo za temperature in vlago tal, za Rečico pa dež s postaje. Razlika med napovedjo in tem izračunom je zato "
         "napaka napovedi vremena, ne modela."),
        table(["Datum", "Območje", "Napoved 18. 9.", "Izračun z dejanskim vremenom", "Razlika"], cmp_rows),
        (f"Razlike so do {A['max_diff']} točk. Največja je 22. septembra v Rečici: izračun z dejanskim vremenom ima nočno ohladitev aktivno že ta dan, napoved pa jo je predvidela šele za 23. september. "
         "Majhna razlika pove, da je bila napoved vremena dobra, ne pa, da model ustreza gozdu. To pokažejo šele najdbe v naslednjem razdelku."),
    ]

    obs_rows = []
    for r in rows:
        obs_rows.append([d_short(r["date"]), r["area"].split(" – ")[0].split(",")[0], f"{r['elev']} m", TERRAIN.get(r["terrain"], "") ,
                         str(r["since"]), f"{r['idx']} ({r['lvl'].lower()})", r["qty"]])
    sec3 = [
        stats,
        (f"Gobarji lahko na strani Danes po gozdovih vnesejo opažanje: vrsto, območje (ne koordinat) in količino. Od 20. septembra do 14. oktobra je bilo "
         f"{S['obs_total']} vnosov, od tega {n} jurčkov. Vnosi so javni in neovereni. Spodaj je za vsak jurček indeks, ki ga je model za to območje izračunal na dan vnosa."),
        table(["Datum vnosa", "Območje", "Višina", "Podlaga", "Dni od dežja", "Indeks (ocena)", "Količina"], obs_rows),
        chart(S, A),
        (f"Na dan najdbe je bila mediana indeksa {A['med_on']:.0f}. Na vseh dneh istih območij med 10. septembrom in 14. oktobrom je bila {A['med_all']:.0f}, "
         f"delež dni z oceno »Dobro« ali boljšo pa {A['share_all']} % ({A['n_all']} območno-dnevov). Razlika obstaja, a ni velika. Model je bil od 22. do 27. septembra "
         "skoraj povsod visoko, zato bi večino najdb v tem času zadel tudi slab model. Zaupanje v ta rezultat zato ne sme biti večje, kot ga dopušča sedem vnosov."),
        (f"V smeri, ki sem jo napovedal, so najdbe šle: tri od sedmih so nad 1100 metri ({', '.join(d_short(r['date']) for r in rows if r['elev'] > 1100)}), "
         f"vse z indeksom {min(r['idx'] for r in rows if r['elev'] > 1100)} ali več. Dno doline (350 m) je imelo dve najdbi, 20. in 25. septembra."),
    ]

    r20 = next(r for r in rows if r["date"] == "2026-09-20")
    r13 = next(r for r in rows if r["date"] == "2026-10-13")
    sec4 = [
        ("Najbolj poučni sta najdbi, pri katerih je bil model proti:"),
        ("<ul>"
         f"<li><strong>{d_long(r20['date'])}, {r20['area'].split(' – ')[0]} ({r20['elev']} m), indeks {r20['idx']}.</strong> "
         f"{r20['since']} dni po dežju, torej v oknu 8–16 dni, a pred ohladitvijo. Tla so bila po modelu topla ({num(r20['soil'])} °C), "
         "jurčkov strop v modelu je 16,5 °C (optimum 6,5–13,5 °C), nočne ohladitve pa še ni bilo. Model je zato dal nizko oceno, jurček pa je bil vseeno najden. "
         "Najdba z dna doline pri toplih tleh je ena sama, a pokaže, da je temperaturni del modela za dno doline morda prestrog.</li>"
         f"<li><strong>{d_long(r13['date'])}, {r13['area'].split(' – ')[0]} ({r13['elev']} m), indeks {r13['idx']}.</strong> "
         f"{r13['since']} dni po dežju. Sprožilni dež je bil takrat že zunaj okna, zato je njegov delež v modelu skoraj ničen. "
         "Model šteje, kdaj je rast lahko sprožena, ne pa, kako dolgo trosnjaki ostanejo. Pozna najdba je lahko starejši trosnjak.</li>"
         "</ul>"),
        ("Po dveh vnosih modela ne bom spreminjal. Zapišem ju kot vprašanji, ki ju bo treba preveriti z več podatki."),
    ]

    sec5 = [
        ("<ul>"
         "<li><strong>Negativnih podatkov ni.</strong> Nihče ne vnese, da je iskal in ničesar našel. Zato ne morem šteti napačnih alarmov: dni, ko je model kazal »Odlično«, v gozdu pa ni bilo nič.</li>"
         f"<li><strong>Sedem vnosov je malo.</strong> Večina jih je iz enega tedna ({d_short(rows[0]['date'])}–{d_short(next(r for r in rows if r['date'] >= '2026-09-26')['date'])}), ko je bil indeks povsod visok.</li>"
         "<li><strong>Vnosi so neovereni.</strong> Ime vrste je prosto besedilo, datum pa je datum vnosa, ne najdbe.</li>"
         "<li><strong>Izračun ni napoved.</strong> Preverjam, ali model z dejanskim vremenom ustreza najdbam, ne, ali bi bil enako dober pri napovedi.</li>"
         "</ul>"),
    ]

    nxt_open = d_add("2026-10-08", 8)
    nxt_close = d_add("2026-10-08", 16)
    sec6 = [
        (f"Nova priložnost za preverbo je že tu. Dež z 8. oktobra (9,9 mm) po modelu odpira okno za jurčke od {d_long(nxt_open)} do {d_long(nxt_close)}, "
         "a je dosegel manj kot polovico praga, ki ga model zahteva za jurčka (25 mm na 7 dni). Če bodo bralci vnesli jurčke, bo to opozorilo, da je prag prestrog. "
         "Če vnosov ne bo, to ni dokaz, da jurčkov ni: negativnih podatkov, kot rečeno, ni."),
        (f'Če greste v gozd, vnesite opažanje na strani <a href="{SITE}/gobarska-napoved/danes/" style="color:var(--blue)">Danes po gozdovih</a>. '
         "Zadošča območje, natančne lokacije najdb ni treba razkrivati."),
        (f'Gobe nabirajte le, če jih zanesljivo poznate. Informacije o nevarnih zamenjavah in strupenih vrstah najdete na strani '
         f'<a href="{SITE}/gobarska-napoved/strupene-gobe/" style="color:var(--blue)">Strupene gobe</a>.'),
        ('<p class="sg-cap" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
         'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov, izračunov in modelskih '
         'parametrov se predhodno dogovorite z avtorjem.</p>'),
    ]

    src = ('<div class="sources"><strong>Viri:</strong> napoved: članek <a href="/blog/zakaj-po-120-mm-dezja-ni-jurckov-0918.html" style="color:var(--blue)">'
           'Zakaj po 120 mm dežja v gozdu ni jurčkov</a> (18. 9. 2026); izračun: gobarski model Meteorec (<code>species_rules.yaml</code>, '
           f'različica {S["model_version"]}), vremenski podatki Open-Meteo, dež za Rečico s postaje IREICA1; opažanja: javni vnosi bralcev '
           f'(<code>/gobe/opazovanja</code>), zajem {d_long(S["generated"][:10])}. Posnetek podatkov: <code>data/gobe-preverba-jurcki-2026-10.json</code>.'
           '<br><em>Indeks je ocena ugodnosti razmer na podlagi vremena in ni obljuba najdbe. Opažanja niso overjena.</em></div>')

    title = f"Jurčki: {NUMW[ng]} od {NUMW_G[n]} najdb ob dobrem indeksu"
    assert len(title) <= 60, len(title)
    desc = (f"Napoved okna za jurčke {d_long(w_open)} proti {n} opažanjem bralcev: {ng} najdb na dnevih z indeksom 55 ali več, "
            f"napoved vremena je zgrešila indeks za največ {A['max_diff']} točk.")
    assert len(desc) <= 160, len(desc)
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "gobarski indeks", "jurčki", "preverba", "2026"],
        "section_label": "Gobarski model", "og_photo": "gobe-lastna", "og_accent_hex": "#34d399",
        "lead": lead, "sources_note": CSS + src,
        "sections": [
            {"label": "01 — napoved", "heading": "Kaj sem napovedal 18. septembra", "id": "napoved", "paragraphs": sec1},
            {"label": "02 — izračun", "heading": "Napoved proti izračunu z dejanskim vremenom", "id": "izracun", "paragraphs": sec2},
            {"label": "03 — najdbe", "heading": "Kaj so našli bralci", "id": "najdbe", "paragraphs": sec3},
            {"label": "04 — razhajanja", "heading": "Dve najdbi, ki ju model ni videl", "id": "razhajanja", "paragraphs": sec4},
            {"label": "05 — omejitve", "heading": "Česa ta preverba ne zmore", "id": "omejitve", "paragraphs": sec5},
            {"label": "06 — naprej", "heading": "Kaj sledi", "id": "naprej", "paragraphs": sec6},
        ],
    }, A


def main():
    dry = "--dry-run" in sys.argv
    wire = "--wire" in sys.argv
    S = load_data()
    article, A = build_article(S)
    if dry:
        print("TITLE:", article["title"], len(article["title"]))
        print("\nLEAD:", article["lead"])
        for s in article["sections"]:
            print("\n##", s["heading"])
            for p in s["paragraphs"]:
                if 'class="table-scroll"' in p:
                    for r in re.findall(r"<tr>(.*?)</tr>", p, re.S):
                        print("  | " + " | ".join(re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[hd]>(.*?)</t[hd]>", r, re.S)))
                elif p.startswith('<div class="sg-fig"'):
                    print("  [GRAF]")
                else:
                    print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip())
        print("\nMETA:", article["meta_description"], len(article["meta_description"]))
        return
    ftp.TODAY = datetime.date.today().isoformat()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Jurčki: preverba\nnapovedi", meta_note="gobarski model",
        nav_label="O postaji", nav_href="/o-postaji.html")
    with open(os.path.join(ROOT, "blog", f"{slug}.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
