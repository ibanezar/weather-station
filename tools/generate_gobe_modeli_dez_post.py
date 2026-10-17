#!/usr/bin/env python3
"""
tools/generate_gobe_modeli_dez_post.py — članek »Še ena priložnost za gobe? Modeli se ne strinjajo« (17. 10. 2026)

Ročno zasnovan članek, ne samodejni. Vprašanje bralca: ali bodo gobe do petka/sobote naslednji teden dobile še
eno priložnost, glede na to, koliko se modeli razlikujejo pri napovedi dežja.

Kaj članek primerja (vse za mrežno celico Rečice, vir Open-Meteo, zajem na dan objave):
  * determinističen tek 8 modelov (ICON-D2, ICON-EU, ECMWF IFS, ECMWF AIFS, GFS, GEM, UKMO, ARPEGE);
    model, ki ne sega do sobote, je v tabeli označen in se v vsoto ne šteje;
  * ansambli ECMWF IFS ENS (51 članov), ECMWF AIFS ENS (51), ICON-EU-EPS (40) in GEFS (31): razpon P10–P90;
  * prag sprožilnega dežja gobarskega modela po vrstah (`species_rules.yaml`: rain_7d_min × dolžina okna / 7).
    To je SAMO sprožilni dež, ne indeks vrste (ta potrebuje še temperaturo tal, vlago, zalogo vode in teren).

Posnetek (data/gobe-modeli-dez-2026-10-17.json) je shranjen, da je članek ponovljiv; `--refresh` zajame znova.
Notranjih meritev ni nikjer (CLAUDE.md, pravilo na vrhu). Lektura je izklopljena — besedilo je treba prebrati
ročno (docs/slog-pisanja.md).

Usage:
    python3 tools/generate_gobe_modeli_dez_post.py [--dry-run] [--wire] [--refresh]
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
from generate_jurcki_preverba_post import CSS, table, d_short, d_long, d_add, drange, get_json as _get_json  # noqa: E402


def get_json(url, tries=4):
    """Open-Meteo občasno prekine TLS; kot pri gobe_model.fetch_forecast počaka in poskusi znova."""
    import time
    for i in range(tries):
        try:
            return _get_json(url)
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(5 * 3 ** i)


ROOT = seo.ROOT
YEAR = 2026
SLUG = "gobe-se-ena-priloznost-modeli-dez-1017"
SITE = "https://meteorec.si"
SNAPSHOT = os.path.join(ROOT, "data", "gobe-modeli-dez-2026-10-17.json")
LAT, LON = 46.325779, 14.921137  # IREICA1 (isto kot generate_primerjava_modelov_page.py)
TODAY = "2026-10-17"
EV = ("2026-10-20", "2026-10-24")      # dež, o katerem govori članek: torek–sobota
EV_DAYS = list(drange(*EV))
RAIN_DAYS_OLD = ("2026-10-08", "2026-10-12")  # prejšnji val dežja na postaji

DET = [("icon_d2", "ICON-D2 (2 km)"), ("icon_eu", "ICON-EU (7 km)"), ("ecmwf_ifs025", "ECMWF IFS"),
       ("ecmwf_aifs025_single", "ECMWF AIFS (umetna inteligenca)"), ("gfs_seamless", "GFS"),
       ("gem_seamless", "GEM (Kanada)"), ("ukmo_seamless", "UKMO"), ("meteofrance_arpege_europe", "ARPEGE")]
ENS = [("ecmwf_ifs025", "ECMWF IFS ENS", 51, "#199e70"), ("ecmwf_aifs025", "ECMWF AIFS ENS", 51, "#8e6fd8"),
       ("icon_eu", "ICON-EU-EPS", 40, "#d95926"), ("gfs025", "GEFS", 31, "#3b82f6")]
# vrste in zamiki: iz species_rules.yaml, sprožilni prag = rain_7d_min × (max − min + 1) / 7
SPECIES = [("armillaria_mellea", "štorovka"), ("macrolepiota_procera", "marela"), ("hydnum_repandum", "rumeni ježek"),
           ("boletus_edulis", "jurček"), ("cantharellus_cibarius", "lisička")]
WD = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]


def wd(iso):
    return WD[datetime.date.fromisoformat(iso).weekday()]


def pct(v, p):
    v = sorted(v)
    k = (len(v) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


# ── podatki ──────────────────────────────────────────────────────────────────

def daily(times, vals, agg):
    by = {}
    for t, v in zip(times, vals):
        by.setdefault(t[:10], []).append(v)
    out = {}
    for d, xs in by.items():
        if len(xs) == 24 and all(x is not None for x in xs):   # samo polni dnevi
            out[d] = round(agg(xs), 2)
    return out


def fetch_snapshot():
    base = (f"latitude={LAT}&longitude={LON}&timezone=Europe%2FLjubljana&forecast_days=10")
    det_raw = get_json("https://api.open-meteo.com/v1/forecast?hourly=precipitation&models="
                       + ",".join(m for m, _ in DET) + "&" + base)
    t = det_raw["hourly"]["time"]
    det, det_last = {}, {}
    for m, _ in DET:
        v = det_raw["hourly"][f"precipitation_{m}"]
        det[m] = daily(t, v, sum)
        nn = [ti for ti, x in zip(t, v) if x is not None]
        det_last[m] = nn[-1] if nn else None
    ens = {}
    for m, _, n, _ in ENS:
        raw = get_json(f"https://ensemble-api.open-meteo.com/v1/ensemble?hourly=precipitation&models={m}&" + base)
        h = raw["hourly"]
        keys = [k for k in h if k.startswith("precipitation")]
        ens[m] = {"grid": [raw["latitude"], raw["longitude"]], "members": [daily(h["time"], h[k], sum) for k in keys]}
    traw = get_json("https://ensemble-api.open-meteo.com/v1/ensemble?hourly=temperature_2m&models=ecmwf_ifs025&" + base)
    th = traw["hourly"]
    tmin = [daily(th["time"], th[k], min) for k in th if k.startswith("temperature_2m")]
    hist = gm.load_station_precip()
    rules = gm.load_rules()
    sp = {}
    for sid, _ in SPECIES:
        s = next(x for x in rules["species"] if x["id"] == sid)
        sp[sid] = {"ecology": s["ecology"], "lag": [int(s["fruiting_lag_days"]["min"]), int(s["fruiting_lag_days"]["max"])],
                   "rain_7d_min": float(s["rain_7d_min"]), "rain_14d_min": float(s["rain_14d_min"])}
    snap = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "today": TODAY,
            "det": det, "det_last": det_last, "ens": ens, "tmin_ens": tmin, "species": sp,
            "station": {d: hist[d] for d in drange(RAIN_DAYS_OLD[0], "2026-10-16") if d in hist}}
    hj = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    cl = [r for d, r in hj.items() if "10-28" <= d[5:] <= "11-07" and "2020" <= d[:4] <= "2025"]
    snap["clim"] = {"days": len(cl), "frost_days": sum(r["tempLow"] <= 0 for r in cl),
                    "mean": round(st.mean(r["tempAvg"] for r in cl), 1)}
    with open(SNAPSHOT, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    return snap


def load_data():
    if "--refresh" in sys.argv or not os.path.exists(SNAPSHOT):
        return fetch_snapshot()
    return json.load(open(SNAPSHOT, encoding="utf-8"))


def ens_total(mem, days):
    return sum(mem[d] for d in days)


def analyse(S):
    A = {"ens": {}, "det": {}}
    allm = []
    for m, lab, n, col in ENS:
        mem = S["ens"][m]["members"]
        assert len(mem) == n, (m, len(mem))
        # dan šteje samo, če ga imajo vsi člani v celoti (ICON-EU-EPS sega le do četrtka zjutraj)
        ok = [d for d in EV_DAYS if all(d in x for x in mem)]
        full = len(ok) == len(EV_DAYS)
        tot = sorted(ens_total(x, EV_DAYS) for x in mem) if full else None
        tot2 = sorted(ens_total(x, EV_DAYS[:2]) for x in mem)     # torek + sreda: vsi štirje ansambli
        if full:
            allm += tot
        perday = {}
        for d in EV_DAYS:
            if d not in ok:
                perday[d] = None
                continue
            v = [x[d] for x in mem]
            perday[d] = {"med": st.median(v), "p10": pct(v, .1), "p90": pct(v, .9), "ge10": sum(x >= 10 for x in v)}
        e = {"lab": lab, "n": n, "col": col, "full": full, "ok": ok, "perday": perday,
             "tot": tot, "tot2": tot2, "med2": st.median(tot2), "max2": tot2[-1]}
        if full:
            e.update({"p10": pct(tot, .1), "med": st.median(tot), "p90": pct(tot, .9), "min": tot[0], "max": tot[-1],
                      "fri_sat_ge10": sum(ens_total(x, EV_DAYS[3:]) >= 10 for x in mem),
                      "fri_sat_med": st.median([ens_total(x, EV_DAYS[3:]) for x in mem])})
        A["ens"][m] = e
    A["pool"] = sorted(allm)
    A["n_pool"] = len(allm)
    A["full_ens"] = [m for m, _, _, _ in ENS if A["ens"][m]["full"]]
    for m, lab in DET:
        dd = S["det"][m]
        have = [d for d in EV_DAYS if d in dd]
        full = len(have) == len(EV_DAYS)
        A["det"][m] = {"lab": lab, "days": {d: dd.get(d) for d in EV_DAYS}, "full": full,
                       "tot": sum(dd[d] for d in EV_DAYS) if full else None,
                       "last": S["det_last"][m], "have": have}
    full = [v["tot"] for v in A["det"].values() if v["full"]]
    A["det_min"], A["det_max"] = min(full), max(full)
    A["det_full_n"] = len(full)
    # prag po vrstah
    A["sp"] = {}
    for sid, name in SPECIES:
        s = S["species"][sid]
        lo, hi = s["lag"]
        thr = s["rain_7d_min"] * (hi - lo + 1) / 7
        row = {"name": name, "lag": s["lag"], "thr": thr, "eco": s["ecology"]}
        row["win"] = (d_add(EV[0], lo), d_add("2026-10-22", hi))   # od prvega dne dežja + min do zadnjega + max
        row["over"] = {m: sum(x >= thr for x in A["ens"][m]["tot"]) for m in A["full_ens"]}
        row["over_all"] = sum(x >= thr for x in A["pool"])
        A["sp"][sid] = row
    # temperatura: najnižja po dnevih (ECMWF ENS)
    tm = S["tmin_ens"]
    A["tmin"] = {d: {"med": st.median([x[d] for x in tm if d in x]), "frost": sum(x[d] <= 0 for x in tm if d in x), "n": len(tm)}
                 for d in drange("2026-10-20", "2026-10-26")}
    A["old_rain"] = round(sum(S["station"][d] for d in drange(*RAIN_DAYS_OLD) if d in S["station"]), 1)
    return A


# ── grafi ────────────────────────────────────────────────────────────────────

def chart(S, A):
    """Razpon P10–P90 skupne količine dežja 20.–24. 10. po ansamblih; mediana kot oznaka; romb = determinističen tek;
    navpični črti = sprožilni prag ježka in jurčka."""
    W, Hh = 900, 380
    l, r, t, b = 150, 40, 56, 48
    rows = [(m, A["ens"][m]) for m in A["full_ens"]]
    vmax = 80
    x = lambda v: l + (W - l - r) * min(v, vmax) / vmax
    rowh = (Hh - t - b) / len(rows)
    yc = lambda i: t + rowh * (i + .5)
    out = [f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="Skupna količina dežja od 20. do 24. oktobra po ansamblih: razpon od 10. do 90. '
           f'percentila, mediana in prag sprožilnega dežja za ježka in jurčka">',
           '<title>Dež 20.–24. 10. po ansamblih do sobote</title>',
           f'<text class="sg-t" x="{l}" y="22">Dež 20.–24. 10. za Rečico: razpon P10–P90 članov ansambla</text>']
    for v in range(0, vmax + 1, 20):
        out.append(f'<line x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{t}" y2="{Hh - b}" stroke="rgba(255,255,255,.09)"/>')
        out.append(f'<text x="{x(v):.1f}" y="{Hh - b + 20}" text-anchor="middle">{v} mm</text>')
    for sid, col, dy in (("hydnum_repandum", "#d99a00", "end"), ("boletus_edulis", "#e0443e", "start")):
        th = A["sp"][sid]["thr"]
        out.append(f'<line x1="{x(th):.1f}" x2="{x(th):.1f}" y1="{t}" y2="{Hh - b}" stroke="{col}" stroke-width="1.6" stroke-dasharray="5 4"/>')
        out.append(f'<text class="sg-v" x="{x(th) + (-5 if dy == "end" else 5):.1f}" y="{t - 8}" text-anchor="{dy}" style="fill:{col}">prag: {A["sp"][sid]["name"]} {mm(th)} mm</text>')
    for i, (m, e) in enumerate(rows):
        y = yc(i)
        out.append(f'<text x="{l - 10}" y="{y + 4:.1f}" text-anchor="end">{e["lab"]}</text>')
        out.append(f'<rect x="{x(e["p10"]):.1f}" y="{y - 11:.1f}" width="{x(e["p90"]) - x(e["p10"]):.1f}" height="22" rx="4" fill="{e["col"]}" fill-opacity=".35" stroke="{e["col"]}"/>')
        out.append(f'<line x1="{x(e["med"]):.1f}" x2="{x(e["med"]):.1f}" y1="{y - 14:.1f}" y2="{y + 14:.1f}" stroke="{e["col"]}" stroke-width="3.2"/>')
        out.append(f'<text class="sg-v" x="{x(e["p90"]) + 8:.1f}" y="{y + 4:.1f}">mediana {mm(e["med"])} mm</text>')
    # determinističen tek (tistih, ki segajo do sobote) kot romb na vrstici izbranih ansamblov istega modela
    for dm, em in (("ecmwf_ifs025", "ecmwf_ifs025"), ("ecmwf_aifs025_single", "ecmwf_aifs025"), ("gfs_seamless", "gfs025")):
        d = A["det"][dm]
        ei = A["full_ens"].index(em)
        if d["full"]:
            cx, cy = x(d["tot"]), yc(ei) + 17
            out.append(f'<path d="M{cx:.1f},{cy - 6:.1f} l6,6 l-6,6 l-6,-6 z" fill="var(--text,#e8ecef)" stroke="var(--bg,#0a0f1c)" stroke-width="1.5"><title>{d["lab"]}, determinističen tek: {mm(d["tot"])} mm</title></path>')
    out.append('</svg>')
    cap = ('<p class="sg-cap">Barvni pas je razpon od 10. do 90. percentila članov ansambla, debela črta mediana. Romb je determinističen tek istega modela '
           '(en sam izračun, brez razpona). Črtkani črti sta sprožilna praga gobarskega modela za rumenega ježka in jurčka v oknu, ki ga odpre ta dež. '
           'Vir: Open-Meteo (ensemble-api), mreža 0,25°, zajem 17. oktobra 2026. Vse je napoved, ne meritev.</p>')
    return f'<div class="sg-fig">{"".join(out)}</div>{cap}'


# ── članek ───────────────────────────────────────────────────────────────────

def mm(v):
    """Napoved je cela števila (docs/slog-pisanja.md, razdelek 8)."""
    return str(int(round(v)))


WD_TOZ = {"torek": "torek", "sreda": "sredo", "četrtek": "četrtek", "petek": "petek", "sobota": "soboto"}


def build_article(S):
    A = analyse(S)
    E = A["ens"]
    FE = [E[m] for m in A["full_ens"]]       # ansambli, ki segajo do sobote
    ie_e = E["icon_eu"]
    pool = A["pool"]
    np_ = A["n_pool"]
    p10, med, p90 = pct(pool, .1), st.median(pool), pct(pool, .9)
    sp = A["sp"]
    fs_ge10 = sum(e["fri_sat_ge10"] for e in FE)
    fs_med = max(e["fri_sat_med"] for e in FE)
    fs_who = [e["lab"] for e in sorted(FE, key=lambda e: -e["fri_sat_ge10"]) if e["fri_sat_ge10"]]
    ge9 = sum(x >= 9 for x in pool)
    meds = sorted(FE, key=lambda e: e["med"])
    dry_e, wet_e = meds[0], meds[-1]
    full = [m for m, _ in DET if A["det"][m]["full"]]
    peak = {m: max(EV_DAYS, key=lambda d: A["det"][m]["days"][d]) for m in full}
    n_wed = sum(peak[m] == "2026-10-21" for m in full)
    n_thu = sum(peak[m] == "2026-10-22" for m in full)
    dmin, dmax = A["det_min"], A["det_max"]
    ens_of = {"ecmwf_ifs025": "ecmwf_ifs025", "ecmwf_aifs025_single": "ecmwf_aifs025", "gfs_seamless": "gfs025"}
    wetter = [m for m in ens_of if A["det"][m]["full"] and A["det"][m]["tot"] > E[ens_of[m]]["med"]]
    cl = S["clim"]

    lead = (f"Dež prihodnji teden bo skoraj zagotovo padel ({ge9} od {np_} članov ansamblov do sobote napoveduje 9 mm ali več), a se modeli razhajajo v količini: "
            f"od torka do sobote napovedujejo za Rečico med {mm(p10)} in {mm(p90)} mm (razpon P10–P90). "
            f"Petek in sobota sta po večini napovedi suha, odločilna sta sreda in četrtek. "
            f"Za gobe to pomeni priložnost, ki je odvisna od vrste: marele, štorovke in rumeni ježek bodo po naših pragovih dobili dovolj dežja v več kot polovici napovedi, "
            f"jurček in lisička pa le v mokrejši tretjini oziroma desetini.")

    # --- 01 kratek odgovor + tabela dnevov
    pd_rows = []
    for d in EV_DAYS:
        row = [f"{wd(d)}, {d_short(d)}"]
        for m, lab, n, col in ENS:
            p = E[m]["perday"][d]
            row.append("–" if p is None else f"{mm(p['med'])} ({mm(p['p10'])}–{mm(p['p90'])})")
        pd_rows.append(row)
    stats = ('<div class="mini-stat-grid">'
             f'<div class="mini-stat"><div class="ms-label">Dež 20.–24. 10.</div><div class="ms-val">{mm(med)} mm</div><div class="ms-sub">mediana {np_} članov do sobote</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Razpon P10–P90</div><div class="ms-val">{mm(p10)}–{mm(p90)}</div><div class="ms-sub">mm, ansambli do sobote</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Determ. teki</div><div class="ms-val">{mm(dmin)}–{mm(dmax)}</div><div class="ms-sub">mm, {A["det_full_n"]} modeli do sobote</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Petek in sobota</div><div class="ms-val">{fs_ge10} od {np_}</div><div class="ms-sub">članov z ≥ 10 mm</div></div>'
             '</div>')
    sec1 = [
        (f"Kratek odgovor: <strong>da, a ne za vse vrste enako</strong>. Mediana ansamblov ({mm(med)} mm) je nad sprožilnimi pragovi gobarskega modela za marelo, štorovko in rumenega ježka "
         f"({mm(sp['macrolepiota_procera']['thr'])}–{mm(sp['hydnum_repandum']['thr'])} mm), pod pragom za jurčka ({mm(sp['boletus_edulis']['thr'])} mm) in daleč pod pragom za lisičko ({mm(sp['cantharellus_cibarius']['thr'])} mm). "
         "Jurček in lisička bosta dobila dovolj dežja le v mokrejšem delu napovedi. "
         "Vsi ansambli kažejo glavnino dežja v sredo in četrtek (ICON-EU-EPS sega le do četrtka zjutraj, zato njegovih številk za četrtek, petek in soboto ni). "
         "Razlikujejo se v količini in v tem, kateri od teh dveh dni bo mokrejši."),
        stats,
        ("Dež po dnevih (mediana ansambla in razpon P10–P90, mm; pomišljaj pomeni, da ansambel do tja ne sega):"),
        table(["Dan"] + [lab for _, lab, _, _ in ENS], pd_rows),
        (f"Petek in sobota sta v vseh treh ansamblih, ki sežejo do sobote, skoraj suha: najvišja mediana za ta dva dneva skupaj je {mm(fs_med)} mm. "
         f"Dež z 10 mm ali več v teh dveh dneh ima {fs_ge10} od {np_} članov ({', '.join(fs_who)}). Za gobe pa petek in sobota nista odločilna: "
         "dež, ki sproži rast, pade pred njima."),
    ]

    # --- 02 modeli: deterministični
    det_rows = []
    for m, lab in DET:
        d = A["det"][m]
        cells = [lab]
        for dd in EV_DAYS:
            v = d["days"][dd]
            cells.append("–" if v is None else mm(v))
        if d["full"]:
            cells.append(f"<strong>{mm(d['tot'])}</strong>")
            cells.append("")
        else:
            ld = datetime.date.fromisoformat(d["last"][:10]) if d["last"] else None
            cells.append("–")
            cells.append(f"napoved sega do {ld.day}. {ld.month}." if ld else "ni podatkov")
        det_rows.append(cells)
    ie = A["det"]["icon_eu"]
    ie_peak = max(EV_DAYS, key=lambda d: ie["days"].get(d) or 0)
    ie_other = [A["det"][m]["days"][ie_peak] for m in full]
    sec2 = [
        ("Najprej deterministični teki, torej en sam izračun vsakega modela. Tabela kaže dež po dnevih; pomišljaj pomeni, da model do tega "
         "dne ali do konca tega dne še ne sega, zato dneva ne smemo brati kot »suh«."),
        table(["Model"] + [f"{wd(d)[:3]}. {d_short(d)}" for d in EV_DAYS] + ["Skupaj", "Opomba"], det_rows),
        (f"Štirje modeli, ki segajo do sobote, se v vsoti ne razlikujejo veliko ({mm(dmin)}–{mm(dmax)} mm), a se razlikujejo v dnevu: pri {n_wed} je vrh v sredo, pri {n_thu} v četrtek. "
         f"Posebej izstopa ICON-EU, ki za {WD_TOZ[wd(ie_peak)]}, {d_short(ie_peak)} napoveduje {mm(ie['days'][ie_peak])} mm v enem dnevu; ostali modeli imajo za ta dan {mm(min(ie_other))}–{mm(max(ie_other))} mm. "
         f"ICON-EU je za torek in sredo skupaj napovedal {mm(sum(ie['days'][d] for d in EV_DAYS[:2]))} mm, najmokrejši član njegovega ansambla ICON-EU-EPS pa {mm(ie_e['max2'])} mm (mediana {mm(ie_e['med2'])} mm). "
         f"Pri {len(wetter)} od treh modelov, ki imajo ansambel in segajo do sobote, je determinističen tek mokrejši od mediane njegovega ansambla; en izračun torej lahko dež precenjuje."),
        ("Poštenejša slika so ansambli: pokažejo razpon možnosti, ne ene številke. Pas P10–P90 spodaj kaže skupno količino dežja za vseh pet dni; "
         "ICON-EU-EPS ni vključen, ker ne sega do konca tedna."),
        chart(S, A),
        (f"Mediane treh ansamblov so med {mm(dry_e['med'])} mm ({dry_e['lab']}) in {mm(wet_e['med'])} mm ({wet_e['lab']}). "
         f"Za torek in sredo skupaj, do kamor sežejo vsi štirje, so mediane med {mm(min(e['med2'] for e in E.values()))} in {mm(max(e['med2'] for e in E.values()))} mm; "
         f"ICON-EU-EPS ima {mm(ie_e['med2'])} mm. Ansambli imajo mrežo 0,25° (ICON-EU-EPS drugačno celico, nekoliko severovzhodno) in doline ne razločijo, "
         "zato so to ocene za širšo okolico Rečice."),
    ]

    # --- 03 prag
    sp_rows = []
    for sid, _ in SPECIES:
        r = sp[sid]
        lo, hi = r["lag"]
        sp_rows.append([r["name"], f"{lo}–{hi} dni", f"{d_short(r['win'][0])}–{d_short(r['win'][1])}",
                        f"{mm(r['thr'])} mm", f"{round(100 * min(med / r['thr'], 1))} %",
                        f"{r['over_all']} od {np_} ({round(100 * r['over_all'] / np_)} %)"])
    sec3 = [
        ("Gobarski model ne gleda skupnega dežja, ampak <strong>dež v zamiku</strong>: za vsako vrsto šteje samo dež, ki je padel v oknu "
         "med toliko in toliko dnevi pred dnem napovedi (več o tem v članku "
         '<a href="/blog/koliko-dni-po-dezju-rastejo-gobe.html" style="color:var(--blue)">Koliko dni po dežju rastejo gobe</a>). '
         "Če dež pade od torka do četrtka (20.–22. 10.), se okna odprejo takole:"),
        table(["Vrsta", "Zamik", "Okno", "Sprožilni prag", "Mediana dežja kot delež praga", "Članov, ki prag presežejo*"], sp_rows),
        ('<p class="sg-cap">* Seštevek dežja 20.–24. 10. proti pragu, ki ga model za vrsto uporablja v oknu te dolžine '
         '(<code>rain_7d_min</code> × dolžina okna / 7). Pod pragom model dež šteje sorazmerno (polovica praga = polovica ocene dežja), nad pragom je ocena polna. '
         'Upoštevani so ansambli, ki sežejo do sobote (ECMWF IFS ENS, ECMWF AIFS ENS, GEFS). Je samo sprožilni dež; indeks vrste potrebuje še temperaturo tal, vlago, zalogo vode in teren. '
         'Člani treh ansamblov niso neodvisni, zato je delež ocena, ne verjetnost.</p>'),
        (f"Pri vrstah z nižjim pragom (marela {mm(sp['macrolepiota_procera']['thr'])} mm, štorovka {mm(sp['armillaria_mellea']['thr'])} mm, rumeni ježek {mm(sp['hydnum_repandum']['thr'])} mm) prag preseže "
         f"{round(100 * sp['macrolepiota_procera']['over_all'] / np_)} %, {round(100 * sp['armillaria_mellea']['over_all'] / np_)} % oziroma {round(100 * sp['hydnum_repandum']['over_all'] / np_)} % članov, torej več kot polovica. "
         f"Pri jurčku ({mm(sp['boletus_edulis']['thr'])} mm) jih je {round(100 * sp['boletus_edulis']['over_all'] / np_)} %, pri lisički "
         f"({mm(sp['cantharellus_cibarius']['thr'])} mm) pa {round(100 * sp['cantharellus_cibarius']['over_all'] / np_)} %. "
         f"Mediani dež bi jurčku dal približno {round(100 * min(med / sp['boletus_edulis']['thr'], 1))} % sprožilne ocene, lisički {round(100 * min(med / sp['cantharellus_cibarius']['thr'], 1))} %. "
         "<strong>Druga priložnost je torej verjetna za vrste z nižjim pragom, za jurčka mogoča, za lisičko šibka</strong>, razen če se uresniči mokrejši del napovedi."),
    ]

    # --- 04 prejšnji val + temperatura
    t = A["tmin"]
    cold = min(t, key=lambda d: t[d]["med"])
    cold_txt = ("noben član ne napoveduje temperature pod 0 °C" if t[cold]["frost"] == 0
                else f"{t[cold]['frost']} od {t[cold]['n']} članov napoveduje 0 °C ali manj")
    sec4 = [
        (f"Prvi val dežja je že mimo: od {d_short(RAIN_DAYS_OLD[0])} do {d_short(RAIN_DAYS_OLD[1])} je postaja IREICA1 izmerila {num(A['old_rain'])} mm. "
         f"Okno mikoriznih vrst za ta dež (8–16 dni) se zaključi okoli 28. oktobra, drugo okno pa se začne približno takrat. "
         f"Če dež doseže prag, bi se sezona jurčkov, ježkov in lisičk podaljšala v prve dni novembra."),
        (f"Temperatura do 26. oktobra ne kaže ovire. Mediana najnižje temperature članov ECMWF IFS ENS je od {num(round(min(x['med'] for x in t.values()), 1))} °C do "
         f"{num(round(max(x['med'] for x in t.values()), 1))} °C; najhladnejša je noč na {d_short(cold)}, ko {cold_txt}. "
         f"Okno drugega vala (28. 10.–7. 11.) je zunaj dosega napovedi, zato sem pogledal postajo: od 28. oktobra do 7. novembra 2020–2025 je bilo {cl['frost_days']} od {cl['days']} dni "
         f"({round(100 * cl['frost_days'] / cl['days'])} %) z najnižjo temperaturo pod ničlo, povprečna dnevna temperatura pa je bila {num(cl['mean'])} °C. "
         "To je klimatologija šestih let, ne napoved."),
    ]

    th_j, th_l = sp["boletus_edulis"]["thr"], sp["cantharellus_cibarius"]["thr"]
    sec5 = [
        ("<ul>"
         f"<li><strong>Količina dežja je odločilna.</strong> Pod približno {mm(sp['macrolepiota_procera']['thr'])} mm ni polne ocene dežja pri nobeni od teh vrst; "
         f"nad {mm(th_j)} mm jo ima jurček, nad {mm(th_l)} mm tudi lisička. Razpon P10–P90 ({mm(p10)}–{mm(p90)} mm) pokrije oba konca.</li>"
         "<li><strong>Čas je pomemben, a manj.</strong> Sreda ali četrtek za dan premakne okno, ne spremeni pa bistva.</li>"
         "<li><strong>Za gobe petek in sobota nista več odločilna.</strong> Šteje dež do četrtka; kar pade pozneje, je v večini napovedi majhno.</li>"
         "<li><strong>Napoved se bo do srede še spreminjala.</strong> Ansambli se običajno zožijo, ko se dogodek približa; ta članek je posnetek 17. oktobra in napovedi ne osvežuje.</li>"
         "<li><strong>Dež ni vse.</strong> Prag je samo en del indeksa. Temperatura tal, vlaga in teren lahko oceno vrste še znižajo.</li>"
         "</ul>"),
    ]

    sec6 = [
        (f'Dež in indeks po območjih spremljajte na strani <a href="{SITE}/gobarska-napoved/" style="color:var(--blue)">Gobarska napoved</a>, '
         f'dež iz svojega kraja pa vnesite v <a href="{SITE}/gobarska-napoved/valovi/" style="color:var(--blue)">kalkulator gobjih valov</a>, '
         "ki zna napoved dežja vključiti v izračun okna. Če boste v gozdu, vnesite opažanje na strani "
         f'<a href="{SITE}/gobarska-napoved/danes/" style="color:var(--blue)">Danes po gozdovih</a> – tudi to, da ste iskali in ničesar našli.'),
        (f'Gobe nabirajte le, če jih zanesljivo poznate. Informacije o nevarnih zamenjavah in strupenih vrstah najdete na strani '
         f'<a href="{SITE}/gobarska-napoved/strupene-gobe/" style="color:var(--blue)">Strupene gobe</a>.'),
        ('<p class="sg-cap" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
         'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov, izračunov in modelskih '
         'parametrov se predhodno dogovorite z avtorjem.</p>'),
    ]

    src = ('<div class="sources"><strong>Viri:</strong> napoved dežja za mrežno celico Rečice (46,33° N, 14,92° E): Open-Meteo '
           '(forecast API: ICON-D2, ICON-EU, ECMWF IFS in AIFS, GFS, GEM, UKMO, ARPEGE; ensemble API: ECMWF IFS ENS, ECMWF AIFS ENS, ICON-EU-EPS, GEFS), '
           f'zajem {d_long(TODAY)} 2026; sprožilni pragovi: gobarski model Meteorec (<code>species_rules.yaml</code>, različica {gm.MODEL_VERSION}); '
           'dež in temperatura preteklosti: postaja IREICA1 (<code>history.json</code>). Posnetek podatkov: <code>data/gobe-modeli-dez-2026-10-17.json</code>.'
           '<br><em>Vse količine za prihodnost so modelska napoved in ne meritev. Indeks gob je ocena ugodnosti razmer in ni obljuba najdbe.</em></div>')

    title = "Še ena priložnost za gobe? Modeli se ne strinjajo"
    assert len(title) <= 60, len(title)
    desc = (f"Dež 20.–24. 10.: ansambli {mm(p10)}–{mm(p90)} mm, petek in sobota skoraj suha. Kaj to pomeni za drugi val jurčkov, lisičk in drugih gob?")
    assert len(desc) <= 160, len(desc)
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "gobarski indeks", "napoved dežja", "ansambli", "2026"],
        "section_label": "Gobarski model", "og_photo": "gobe-lastna", "og_accent_hex": "#34d399",
        "lead": lead, "sources_note": CSS + src,
        "sections": [
            {"label": "01 — odgovor", "heading": "Dež bo, vprašanje je koliko", "id": "odgovor", "paragraphs": sec1},
            {"label": "02 — modeli", "heading": "Kje se modeli razhajajo", "id": "modeli", "paragraphs": sec2},
            {"label": "03 — prag", "heading": "Kdo bo dobil dovolj dežja", "id": "prag", "paragraphs": sec3},
            {"label": "04 — okno", "heading": "Drugi val se začne, ko se prvi konča", "id": "okno", "paragraphs": sec4},
            {"label": "05 — negotovost", "heading": "Kaj še ni znano", "id": "negotovost", "paragraphs": sec5},
            {"label": "06 — naprej", "heading": "Kaj naj naredite", "id": "naprej", "paragraphs": sec6},
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
    ftp.TODAY = TODAY
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Še ena priložnost\nza gobe?", meta_note="gobarski model",
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
