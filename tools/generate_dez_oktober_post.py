#!/usr/bin/env python3
"""
tools/generate_dez_oktober_post.py — članek »Dež 8.–10. oktobra« z interaktivnimi grafi.

Ročno zasnovan članek (ne dnevni samodejni). Podatke pobere ob zagonu:
  * Open-Meteo, urne padavine šestih determinističnih modelov (ECMWF IFS, ECMWF AIFS,
    ICON-D2, ICON-EU, GFS, ARPEGE),
  * Open-Meteo Ensemble: ECMWF ENS, ICON-EU-EPS, GEFS (skupaj ~130 članov),
  * ARSO napoved prek workerja (/arso-forecast, najbližja točka je Ljubno ob Savinji),
  * MTR (napoved-modela.json) samo za verjetnost padavin,
  * meritve postaje IREICA1 iz history.json (samo zunanje padavine) za primerjave.
Vse vrednosti vgradi v stran kot JSON; JS jih samo izriše, tako da imata besedilo in
grafi ENE izračun. Članek je POSNETEK ob uri zajema — stran to pove.

Notranjih meritev ni nikjer (CLAUDE.md, pravilo na vrhu). Lektura je izklopljena
(CLAUDE.md) — besedilo je treba prebrati ročno.

Usage:
    python3 tools/generate_dez_oktober_post.py [--dry-run] [--wire]
"""
import datetime
import json
import os
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import generate_forecast_test_post as ftp  # noqa: E402
from generate_seo_pages import num  # noqa: E402

ROOT = seo.ROOT
LAT, LON = 46.325779, 14.921137  # IREICA1
TZ = ZoneInfo("Europe/Ljubljana")
YEAR = 2026
SLUG = "dez-8-9-oktobra-koliko-ga-bo-padlo-1007"
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
DNEVI = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
DNEVI_K = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

MODELS = [  # (ključ Open-Meteo, ime na strani)
    ("ecmwf_ifs025", "ECMWF IFS"),
    ("ecmwf_aifs025_single", "ECMWF AIFS"),
    ("icon_d2", "ICON-D2"),
    ("icon_eu", "ICON-EU"),
    ("gfs_seamless", "GFS"),
    ("arpege_europe", "ARPEGE"),
]
ENSEMBLES = [  # (predpona ključa, ime, št. članov se prešteje)
    ("ecmwf_ifs025_ensemble", "ECMWF ENS"),
    ("icon_eu_eps", "ICON-EU-EPS"),
    ("ncep_gefs025", "GEFS"),
]
THRESH = [10, 20, 30, 50]


def fetch_json(url, tries=5):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 3 * k)
    raise SystemExit(f"✗ {url[:70]}…: {last}")


def pct(sorted_vals, p):
    """Percentil po metodi najbližjega ranga (0–100)."""
    n = len(sorted_vals)
    i = min(n - 1, max(0, int(round(p / 100 * (n - 1)))))
    return sorted_vals[i]


def short(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def fdate(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}"


def dlong(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{DNEVI[d.weekday()]}, {d.day}. {d.month}."


def dgen(iso):
    """»v četrtek« / »v petek« ... (tožilnik za dan v tednu)."""
    d = datetime.date.fromisoformat(iso).weekday()
    return ["v ponedeljek", "v torek", "v sredo", "v četrtek", "v petek", "v soboto", "v nedeljo"][d]


# ----------------------------------------------------------------------------- podatki


def load_forecasts(today):
    om = fetch_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&hourly=precipitation"
                    "&models=%s&forecast_days=7&timezone=Europe%%2FLjubljana"
                    % (LAT, LON, ",".join(k for k, _ in MODELS)))
    ens = fetch_json("https://ensemble-api.open-meteo.com/v1/ensemble?latitude=%s&longitude=%s&hourly=precipitation"
                     "&models=ecmwf_ifs025,icon_eu,gfs025&forecast_days=7&timezone=Europe%%2FLjubljana" % (LAT, LON))
    arso = fetch_json(f"{WORKER}/arso-forecast")
    return om, ens, arso


def build_data():
    today = os.environ.get("POST_DATE") or datetime.date.today().isoformat()
    om, ens, arso = load_forecasts(today)
    times = om["hourly"]["time"]
    assert times == ens["hourly"]["time"], "časovni osi se ne ujemata"
    n = len(times)
    t0 = times.index(f"{today}T00:00")
    if t0 != 0:
        raise SystemExit("pričakujem, da napoved začne danes ob 00:00")
    days = sorted({t[:10] for t in times})

    # --- deterministični modeli, urno
    mh = {}
    for key, name in MODELS:
        arr = om["hourly"].get(f"precipitation_{key}")
        if arr is None:
            continue
        mh[name] = [None if v is None else round(v, 1) for v in arr]

    # --- ansambli: člani
    members, groups = [], {}
    for pre, name in ENSEMBLES:
        ks = [k for k in ens["hourly"] if k.startswith(f"precipitation_member") and k.endswith(pre)]
        if not ks:  # ECMWF: precipitation_member01_ecmwf_ifs025_ensemble
            ks = [k for k in ens["hourly"] if "member" in k and pre in k]
        arrs = [[(v or 0.0) for v in ens["hourly"][k]] for k in ks]
        groups[name] = arrs
        members += arrs
    if len(members) < 60:
        raise SystemExit(f"premalo članov ansambla: {len(members)}")

    cum_members = []
    for a in members:
        c, s = [], 0.0
        for v in a:
            s += v
            c.append(s)
        cum_members.append(c)

    def band(mat, p):
        return [round(pct(sorted(row[i] for row in mat), p), 2) for i in range(n)]

    rate = {f"p{p}": band(members, p) for p in (10, 50, 90)}
    cum = {f"p{p}": band(cum_members, p) for p in (10, 50, 90)}

    # --- dnevne vsote po virih
    def day_sum(arr, d):
        vals = [arr[i] for i, t in enumerate(times) if t[:10] == d]
        if any(v is None for v in vals):
            return None
        return round(sum(vals), 1)

    src_days = {}
    for name, arr in mh.items():
        src_days[name] = [day_sum(arr, d) for d in days]
    a_by = {x["valid_date"]: x for x in arso["days"]}
    src_days["ARSO"] = [a_by[d]["precip"] if d in a_by else None for d in days]
    ens_days = {"p10": [], "p50": [], "p90": []}
    for d in days:
        ix = [i for i, t in enumerate(times) if t[:10] == d]
        tot = sorted(sum(a[i] for i in ix) for a in members)
        for p in (10, 50, 90):
            ens_days[f"p{p}"].append(round(pct(tot, p), 1))

    # --- okno dogodka: 8.–10. oktobra (trije dnevi od jutri)
    ev_days = days[1:4]
    ev_ix = [i for i, t in enumerate(times) if t[:10] in ev_days]
    totals = sorted(round(sum(a[i] for i in ev_ix), 1) for a in members)
    ev = {
        "days": ev_days, "n": len(totals), "totals": totals,
        "p10": pct(totals, 10), "p50": pct(totals, 50), "p90": pct(totals, 90),
        "min": totals[0], "max": totals[-1],
        "prob": {str(t): round(100 * sum(x >= t for x in totals) / len(totals)) for t in THRESH},
        "groups": {},
    }
    for name, arrs in groups.items():
        g = sorted(round(sum(a[i] for i in ev_ix), 1) for a in arrs)
        ev["groups"][name] = {"n": len(g), "p10": pct(g, 10), "p50": pct(g, 50), "p90": pct(g, 90),
                              "p20": round(100 * sum(x >= 20 for x in g) / len(g))}
    ev["det"] = {}
    for name, arr in mh.items():
        vals = [arr[i] for i in ev_ix]
        ev["det"][name] = None if any(v is None for v in vals) else round(sum(vals), 1)
    ev["arso"] = round(sum(a_by[d]["precip"] for d in ev_days if d in a_by), 1)

    # --- MTR: samo verjetnost padavin
    pop = {}
    try:
        mtr = json.load(open(os.path.join(ROOT, "napoved-modela.json"), encoding="utf-8"))
        for x in mtr["days"]:
            pop[x["date"]] = round(100 * x["pop"])
    except Exception:  # noqa: BLE001
        pop = {}

    # --- zgodovina postaje (samo zunanje padavine)
    hist = seo.load_history()
    keys = sorted(k for k, v in hist.items() if v.get("precipTotal") is not None
                  and v.get("src") in (None, "station", "wu"))
    rain = {k: hist[k]["precipTotal"] for k in keys}
    first, last = keys[0], keys[-1]
    # 3-dnevna drseča okna samo čez zaporedne dni
    wins = []
    for k in keys:
        d = datetime.date.fromisoformat(k)
        ds = [(d + datetime.timedelta(i)).isoformat() for i in range(3)]
        if all(x in rain for x in ds):
            wins.append((round(sum(rain[x] for x in ds), 1), k))
    vals = sorted(w[0] for w in wins)
    exceed = [round(100 * sum(v >= x for v in vals) / len(vals), 2) for x in range(0, 121)]
    top, taken = [], []
    for v, k in sorted(wins, reverse=True):
        d = datetime.date.fromisoformat(k)
        if all(abs((d - t).days) >= 3 for t in taken):
            taken.append(d)
            top.append((v, k))
        if len(top) >= 8:
            break
    octs = {}
    for y in range(2020, YEAR):
        ks = [k for k in keys if k.startswith(f"{y}-10")]
        if len(ks) == 31:
            octs[str(y)] = round(sum(rain[k] for k in ks), 1)
    oct_mean = round(sum(octs.values()) / len(octs), 1)
    dry_since = max((k for k in keys if rain[k] >= 1.0), default=None)
    after = [k for k in keys if dry_since and k > dry_since]
    dry = {"last_wet": dry_since, "days": len(after), "sum": round(sum(rain[k] for k in after), 1),
           "archive_end": last}
    sep = round(sum(rain[k] for k in keys if k.startswith("2026-09")), 1)
    sep10 = rain.get("2026-09-10")
    return {
        "today": today, "generated": datetime.datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"),
        "t": times, "days": days,
        "mh": mh, "rate": rate, "cum": cum,
        "src_days": src_days, "ens_days": ens_days, "ev": ev, "pop": pop,
        "hist": {"first": first, "last": last, "n_win": len(vals), "exceed": exceed,
                 "top": top, "octs": octs, "oct_mean": oct_mean, "sep": sep, "sep10": sep10,
                 "max_day": max((rain[k], k) for k in keys), "n_days": len(keys)},
        "dry": dry,
        "arso_loc": arso.get("location", {}).get("name", ""),
        "arso_txt": {x["valid_date"]: x.get("shortFcst_sl", "") for x in arso["days"]},
        "n_members": {k: len(v) for k, v in groups.items()},
    }


# ----------------------------------------------------------------------------- besedilo


def rank_of(D, mm):
    """Delež 3-dnevnih obdobij na postaji, v katerih je padlo vsaj mm (vrednost 0–100)."""
    ex = D["hist"]["exceed"]
    return ex[min(120, max(0, int(round(mm))))]


def build_article(D):
    ev, H, dry = D["ev"], D["hist"], D["dry"]
    days = D["days"]
    d1, d2, d3 = ev["days"]
    sd = D["src_days"]
    ix = {d: i for i, d in enumerate(days)}
    # dan z največ dežja po mediani ansambla
    wet_i = max(range(len(days)), key=lambda i: D["ens_days"]["p50"][i])
    wet_d = days[wet_i]
    det_vals = [v for v in ev["det"].values() if v is not None]
    lo_det, hi_det = min(det_vals), max(det_vals)
    arso = ev["arso"]
    p50 = ev["p50"]
    pct_oct = round(100 * p50 / H["oct_mean"])
    pr = ev["prob"]
    rk = rank_of(D, p50)
    ngrp = D["n_members"]

    lead = (f"Po zadnjem pravem dežju {short(dry['last_wet'])} je do {short(dry['archive_end'])} na naši postaji padlo skupaj le "
            f"{num(dry['sum'])} mm padavin. Zdaj se Rečici ob Savinji {dgen(d1)} in {dgen(d2)} obeta konec suše. "
            f"Koliko dežja bo padlo, pa modeli ne vedo povsem enako: posamezne napovedi za obdobje {short(d1)}–{short(d3)} "
            f"segajo od {num(lo_det)} do {num(hi_det)} mm. ARSO napoveduje {num(arso)} mm, mediana ansambla s {ev['n']} člani "
            f"pa je {num(p50)} mm. Deset odstotkov članov napoveduje manj kot {num(ev['p10'])} mm, deset odstotkov pa več kot "
            f"{num(ev['p90'])} mm. Spodaj so grafi, po katerih lahko pogledate sami: kdaj bo padalo, kako verjetne so posamezne "
            f"količine in kako se napoved ujema z meritvami naše postaje.")

    d3_s = short(d3).rstrip(".")
    fig1 = fig("dz-fig1", "", "Izberite dan s klikom ali tipkama ← →. Pike predstavljajo vrednosti posameznih virov, moder pas "
               "razpon ansambla od 10. do 90. percentila, črta v njem pa mediano. Podatki veljajo za točko postaje IREICA1.", "day")
    fig2_ctl = ('<div class="dz-ctl" role="group" aria-label="Prikaz"><button type="button" data-m="rate" aria-pressed="true">'
                'Dež na uro</button><button type="button" data-m="cum" aria-pressed="false">Seštevek od jutra danes</button></div>'
                '<div class="dz-ctl" role="group" aria-label="Primerjava z modelom" id="dz-models"></div>')
    fig2 = fig("dz-fig2", fig2_ctl, "Premaknite kazalec po času ali uporabite ← → (PageUp/PageDown: 6 ur). "
               "Gumbi pod prikazom dodajo črto posameznega modela. Ansambel združuje " +
               ", ".join(f"{k} ({v})" for k, v in ngrp.items()) + ".", "hour")
    fig3_ctl = ('<div class="dz-ctl dz-slide"><label for="dz-thr">Prag: vsaj <b id="dz-thr-v">20</b> mm</label>'
                '<input type="range" id="dz-thr" min="0" max="80" step="1" value="20" '
                'aria-describedby="dz-thr-out"></div>')
    fig3 = fig("dz-fig3", fig3_ctl, f"Stolpci kažejo, koliko članov ansambla (skupaj {ev['n']}) napoveduje posamezno količino; "
               f"seštevek velja za obdobje od {short(d1)} do konca {d3_s}. Drsnik premika prag.", "thr")
    fig4 = fig("dz-fig4", "", "Stolpci predstavljajo oktobrske vsote padavin na postaji IREICA1, prekinjena črta pa povprečje "
               f"({num(H['oct_mean'])} mm). Moder stolpec je mediana napovedanega dežja za obdobje {short(d1)}–{short(d3)}, "
               "temnejši nastavek pa sega do 90. percentila.", "oct")
    fig5_ctl = ('<div class="dz-ctl dz-slide"><label for="dz-cmp">Količina v treh dneh: <b id="dz-cmp-v">'
                f'{int(round(p50))}</b> mm</label><input type="range" id="dz-cmp" min="0" max="120" step="1" '
                f'value="{int(round(p50))}"></div>')
    fig5 = fig("dz-fig5", fig5_ctl, "Krivulja kaže, v kolikšnem deležu trodnevnih obdobij je na postaji padlo vsaj toliko dežja. "
               "Navpične črte predstavljajo napovedani P10, mediano in P90.", "cmp")

    pop_txt = ""
    if D["pop"].get(d1) is not None and D["pop"].get(d2) is not None:
        pop_txt = (f"Naš model MTR količine dežja ne napoveduje, verjetnost padavin pa ocenjuje kot visoko: "
                   f"{dgen(d1)} {D['pop'][d1]} %, {dgen(d2)} {D['pop'][d2]} %.")

    sec1 = [
        fig1,
        f"Največ dežja se obeta {dgen(wet_d)}, {short(wet_d)}: mediana ansambla je {num(D['ens_days']['p50'][wet_i])} mm, "
        f"posamezni modeli pa segajo od {num(min(v[wet_i] for k, v in sd.items() if k != 'ARSO' and v[wet_i] is not None))} do "
        f"{num(max(v[wet_i] for k, v in sd.items() if k != 'ARSO' and v[wet_i] is not None))} mm. "
        f"ARSO za točko {D['arso_loc'] or 'v dolini'} napoveduje {num(sd['ARSO'][ix[d1]])} mm {dgen(d1)} in "
        f"{num(sd['ARSO'][ix[d2]])} mm {dgen(d2)}.",
        pop_txt,
        "Razlike med modeli niso napaka, ampak značilnost napovedovanja padavin. Če se pas dežja pomakne le nekaj kilometrov "
        "vzhodneje ali zahodneje, se lahko skupna količina za določen kraj večkrat spremeni. Zato je ansambel – torej veliko "
        "zagonov z nekoliko različnimi začetnimi pogoji – bolj pošteno merilo negotovosti kot katera koli posamezna napoved.",
    ]
    sec1 = [x for x in sec1 if x]
    sec2 = [
        fig2,
        "Prvi graf kaže, kdaj naj bi padalo: pas predstavlja razpon ansambla, črta pa mediano. Preklopite na seštevek, "
        "da vidite, koliko dežja se nabere do posamezne ure, in dodajte posamezen model – tako lahko vidite, kje se z "
        "ansamblom ujema in kje izstopa iz njegovega razpona.",
        "Ker mediana ansambla ni nujno enaka nobenemu posameznemu članu, črta v pasu ne predstavlja ene od možnih različic "
        "vremena, ampak sredino številnih. Posamezen model je lahko bližje resnici kot mediana, vendar vnaprej ne vemo, kateri.",
    ]
    g = ev["groups"]
    grp_rows = "".join(
        f"<tr><td>{k}</td><td>{v['n']}</td><td>{num(v['p10'])}</td><td>{num(v['p50'])}</td><td>{num(v['p90'])}</td>"
        f"<td>{v['p20']} %</td></tr>" for k, v in g.items())
    grp_rows += (f"<tr><td><b>Skupaj</b></td><td><b>{ev['n']}</b></td><td><b>{num(ev['p10'])}</b></td>"
                 f"<td><b>{num(p50)}</b></td><td><b>{num(ev['p90'])}</b></td><td><b>{pr['20']} %</b></td></tr>")
    tbl = ('<div class="table-scroll" tabindex="0"><table class="data-table"><thead><tr><th>Ansambel</th><th>Članov</th>'
           '<th>P10 (mm)</th><th>Mediana (mm)</th><th>P90 (mm)</th><th>Verjetnost ≥ 20 mm</th></tr></thead><tbody>'
           + grp_rows + '</tbody></table></div>')
    sec3 = [
        fig3,
        f"Mediana vsote za obdobje {short(d1)}–{short(d3)} je v ansamblu {num(p50)} mm, vendar je razpršenost velika: "
        f"verjetnost za vsaj 10 mm je {pr['10']} %, za vsaj 20 mm {pr['20']} %, za vsaj 30 mm {pr['30']} % in za vsaj 50 mm "
        f"{pr['50']} %. Najbolj moker član je napovedal {num(ev['max'])} mm, najbolj suh {num(ev['min'])} mm.",
        "Tri družine ansamblov se ne strinjajo povsem:",
        tbl,
        "Pri tolmačenju verjetnosti pazite: to je delež članov ansambla, ki so dosegli določen prag, ne izmerjena pogostost dogodka. "
        "Ansambli so pogosto preozko razpršeni, zato lahko dejansko negotovost nekoliko podcenjujejo.",
    ]
    top_rows = "".join(f"<tr><td>{short(k)}{k[:4] if k[:4] != str(YEAR) else ''}</td><td>{num(v)}</td></tr>"
                       for v, k in H["top"])
    top_rows = "".join(
        f"<tr><td>{datetime.date.fromisoformat(k).day}. {datetime.date.fromisoformat(k).month}. "
        f"{k[:4]}</td><td>{num(v)}</td></tr>" for v, k in H["top"])
    tbl2 = ('<div class="table-scroll" tabindex="0"><table class="data-table"><thead><tr><th>Začetek trodnevnega obdobja</th>'
            '<th>Padavine v treh dneh (mm)</th></tr></thead><tbody>' + top_rows + '</tbody></table></div>')
    md_v, md_k = H["max_day"]
    sec4 = [
        fig4,
        f"Postaja IREICA1 je v oktobrih {min(H['octs'])}–{max(H['octs'])} izmerila povprečno {num(H['oct_mean'])} mm padavin, "
        f"razpon pa je bil od {num(min(H['octs'].values()))} do {num(max(H['octs'].values()))} mm. Mediana napovedanega dežja "
        f"za obdobje {short(d1)}–{short(d3)} je torej okoli {pct_oct} % povprečne oktobrske količine, pri 90. percentilu "
        f"({num(ev['p90'])} mm) pa približno {round(100 * ev['p90'] / H['oct_mean'])} %.",
        fig5,
        f"Na drugem grafu je napoved postavljena ob vsa trodnevna obdobja v arhivu postaje "
        f"({H['n_win']} obdobij od {fdate(H['first'])}). Mediana napovedi ({num(p50)} mm) je bila presežena "
        f"v približno {num(rk)} % obdobij.",
        "Dež bo torej po tej primerjavi bolj izrazit od običajnega, vendar ne izjemen.",
        f"Za občutek: 10. septembra letos je v enem dnevu padlo {num(H['sep10'])} mm, ves september pa {num(H['sep'])} mm. "
        f"Absolutni dnevni rekord arhiva znaša {num(md_v)} mm in je bil izmerjen "
        f"{datetime.date.fromisoformat(md_k).day}. {datetime.date.fromisoformat(md_k).month}. {md_k[:4]}.",
        "Najmočnejših osem trodnevnih obdobij v arhivu:",
        tbl2,
    ]
    sec5 = [
        "Po tako suhem obdobju bodo tla prvi dež verjetno deloma vpila, zato odtok ne bo tolikšen kot po mokrem septembru. "
        "Pri količinah okoli 30 mm in več v kratkem času pa postane odtok bolj verjeten.",
        "Tekoče stanje Savinje spremljajte na <a href=\"/vodostaj-savinje/\">strani Vodostaj</a>, morebitna uradna opozorila "
        "pa na <a href=\"/nevihte/\">strani Nevihte</a> in pri ARSO.",
        "Za gobarje: po dolgem suhem obdobju dež sam po sebi ne bo povzročil rasti gob. Mikorizne vrste potrebujejo po dežju "
        "več časa – naš gobarski model računa zamik 8–16 dni –, zato morebitni učinek ne bo viden prej kot v drugi polovici oktobra.",
        "Dnevni indeks je na <a href=\"/gobarska-napoved/\">gobarski napovedi</a>.",
    ]
    hh, mm_ = D["generated"][11:].split(":")
    sec6 = [
        f"Napoved je posnetek stanja ob {int(hh)}.{mm_} ({short(D['today'])}). Modeli se osvežujejo večkrat na dan, zato se bodo "
        f"številke do prihoda dežja še spremenile. Za ukrepanje veljata ARSO in uradna opozorila.",
        "Deterministične napovedi so urne količine padavin Open-Meteo (ECMWF IFS, ECMWF AIFS, ICON-D2, ICON-EU, GFS, ARPEGE) "
        "za točko postaje. ICON-D2 in ARPEGE segata le nekaj dni naprej, zato imata za kasnejše dni vrzeli.",
        "V ansamblu (ECMWF ENS, ICON-EU-EPS, GEFS) štejem vsakega člana enako, ne glede na ločljivost. Mreža ni zelo natančna "
        "(od nekaj kilometrov do 25 km), zato dolina in pobočja niso razločeni. Količina padavin tudi ni popravljena z MTR – "
        "MTR popravlja le temperature.",
        "ARSO napoved je za najbližjo točko, Ljubno ob Savinji, zato ni neposredno primerljiva z napovedjo za našo postajo.",
        f"Primerjave s preteklostjo temeljijo na meritvah zunanjega dežemera IREICA1 ({H['n_days']} dni, od {fdate(H['first'])} do "
        f"{fdate(H['last'])}). Arhiv ima nekaj lukenj, zato so v krivuljo vključena le trodnevna obdobja, pri katerih so na voljo "
        "vsi trije dnevi.",
        "Drseča trodnevna obdobja se prekrivajo, zato niso neodvisni dogodki.",
    ]
    data_json = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
    sec6.append(f'<div><script type="application/json" id="dez-data">{data_json}</script>{CSS}{JS}</div>')

    return {
        "title": "Dež 8.–10. oktobra: koliko ga bo padlo v Rečici?",
        "meta_description": (f"Po {dry['days']} suhih dneh dež: mediana ansambla {num(p50)} mm do {short(d3)} "
                             f"(P10–P90 {num(ev['p10'])}–{num(ev['p90'])} mm), ARSO {num(arso)} mm. Interaktivni grafi in primerjava s postajo."),
        "tags": ["napoved", "padavine", "oktober", "2026", "analiza"],
        "section_label": "Napoved",
        "og_photo": "weather-station",
        "og_accent_hex": "#3987e5",
        "lead": lead,
        "sections": [
            {"label": "01 — viri", "heading": "Koliko dežja kažejo posamezni viri", "id": "viri", "paragraphs": sec1},
            {"label": "02 — čas", "heading": "Kdaj bo padalo", "id": "cas", "paragraphs": sec2},
            {"label": "03 — verjetnost", "heading": "Kako verjetne so posamezne količine", "id": "verjetnost", "paragraphs": sec3},
            {"label": "04 — primerjava", "heading": "Koliko je to v primerjavi z našo postajo", "id": "primerjava", "paragraphs": sec4},
            {"label": "05 — pomen", "heading": "Kaj to pomeni v dolini", "id": "pomen", "paragraphs": sec5},
            {"label": "06 — metodologija", "heading": "Od kod številke in kaj ne drži povsem", "id": "metodologija", "paragraphs": sec6},
        ],
        "callout": None,
        "sources_note": "Vir: Open-Meteo (modeli in ansambli), ARSO, meritve postaje IREICA1 (Meteorec).",
    }


def fig(fid, ctl, hint, kind):
    return (f'<div class="chart-card dz-fig" id="{fid}" data-kind="{kind}">{ctl}<div class="dz-ro" role="status"></div>'
            f'<div class="dz-plot" tabindex="0" role="group" aria-label="Graf. Puščici levo in desno premakneta kazalec."></div>'
            f'<p class="dz-hint">{hint}</p></div>')


CSS = """<style>
.dz-fig{margin:1rem 0 1.8rem}
.dz-fig .dz-ctl{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.7rem;align-items:center}
.dz-fig .dz-ctl button{font:inherit;font-size:.82rem;color:var(--text);background:transparent;border:1px solid var(--card-border);border-radius:999px;padding:.35rem .85rem;cursor:pointer}
.dz-fig .dz-ctl button[aria-pressed="true"]{background:rgba(57,135,229,.22);border-color:#3987e5}
.dz-fig .dz-ctl button:focus-visible,.dz-fig .dz-plot:focus-visible,.dz-fig input:focus-visible{outline:2px solid #3987e5;outline-offset:2px}
.dz-fig .dz-slide{gap:.8rem}.dz-fig .dz-slide input{flex:1 1 220px;min-width:160px;accent-color:#3987e5}
.dz-fig .dz-ro{font-size:.92rem;line-height:1.55;min-height:3.4em;margin:.2rem 0 .6rem}
.dz-fig .dz-plot{touch-action:pan-y;outline-offset:4px;border-radius:8px}
.dz-fig svg{display:block;width:100%;height:auto;user-select:none;-webkit-user-select:none}
.dz-fig .dz-hint{color:var(--muted);font-size:.8rem;margin-top:.4rem}
</style>"""

JS = r"""<script>
(function(){
var D=JSON.parse(document.getElementById('dez-data').textContent);
var DN=['ned','pon','tor','sre','čet','pet','sob'];
var BLUE='#3987e5',ORANGE='#d95926',INK='#e8edf8',MUTED='#adc0d8',SURF='#0a0f1c',GRID='rgba(255,255,255,.10)';
function f1(x){return (Math.round(x*10)/10).toFixed(1).replace('.',',');}
function f0(x){return String(Math.round(x));}
function dl(iso){var p=iso.split('-'),d=new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));return DN[d.getUTCDay()]+', '+(+p[2])+'. '+(+p[1])+'.';}
function hl(t){var h=t.slice(11,13);return dl(t.slice(0,10))+' '+h+':00';}
function el(id){return document.getElementById(id);}
function W(plot){return Math.max(300,Math.min(780,plot.clientWidth||600));}
function wrap(fid,build,place,n,start){
  var root=el(fid);if(!root)return;
  var plot=root.querySelector('.dz-plot'),ro=root.querySelector('.dz-ro'),cur=start||0,geo=null,svg=null;
  function draw(){var r=build(W(plot));geo=r;plot.innerHTML=r.svg;svg=plot.querySelector('svg');put(cur);}
  function put(i){cur=Math.max(0,Math.min(n()-1,Math.round(i)));var r=place(cur,geo,svg);if(r!==undefined)ro.innerHTML=r;}
  function ev(e){var b=svg.getBoundingClientRect(),px=(e.clientX-b.left)*(geo.w/b.width);return geo.inv(px);}
  var down=false;
  plot.addEventListener('pointerdown',function(e){down=true;put(ev(e));});
  plot.addEventListener('pointermove',function(e){if(e.pointerType==='mouse'||down)put(ev(e));});
  window.addEventListener('pointerup',function(){down=false;});
  plot.addEventListener('keydown',function(e){var st={ArrowLeft:-1,ArrowRight:1,PageDown:-(geo.big||1),PageUp:(geo.big||1)}[e.key];
    if(st){put(cur+st);e.preventDefault();}else if(e.key==='Home'){put(0);e.preventDefault();}else if(e.key==='End'){put(n()-1);e.preventDefault();}});
  var rt;window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(function(){if(Math.abs((plot.clientWidth||0)-geo.w)>2)draw();},120);});
  draw();
  return {redraw:draw,put:put,cur:function(){return cur;}};
}
function axisY(s,L,R,w,Y,ticks,fmt){ticks.forEach(function(t){var y=Y(t);s+='<line x1="'+L+'" x2="'+(w-R)+'" y1="'+y+'" y2="'+y+'" stroke="'+GRID+'"/><text x="'+(L-6)+'" y="'+(y+4)+'" text-anchor="end" font-size="12" fill="'+MUTED+'">'+(fmt?fmt(t):t)+'</text>';});return s;}
function nice(max){var st=[1,2,5,10,20,25,50,100],k=0;while(k<st.length-1&&max/st[k]>5)k++;var s=st[k],t=[];for(var v=0;v<=max+s*0.01;v+=s)t.push(v);return {top:t[t.length-1]>=max?t[t.length-1]:t[t.length-1]+s,ticks:t};}

/* ---- 1: dnevne vsote po virih ---- */
(function(){
  var dayIdx=[];D.days.forEach(function(d,i){if(i>=1)dayIdx.push(i);});
  var names=Object.keys(D.src_days);
  var mx=0;dayIdx.forEach(function(i){names.forEach(function(k){var v=D.src_days[k][i];if(v!=null&&v>mx)mx=v;});if(D.ens_days.p90[i]>mx)mx=D.ens_days.p90[i];});
  var sc=nice(mx*1.05);
  wrap('dz-fig1',function(w){
    var L=40,R=12,T=10,B=26,H=230,n=dayIdx.length,ph=H-T-B;
    function X(k){return L+(k+.5)/n*(w-L-R);}function Y(v){return T+ph-v/sc.top*ph;}
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Dnevne količine padavin po virih za naslednjih šest dni" font-family="inherit">';
    s=axisY(s,L,R,w,Y,sc.ticks,function(t){return t;});
    s+='<text x="'+L+'" y="'+(T-1)+'" font-size="12" fill="'+MUTED+'" dy="2">mm na dan</text>';
    var bw=(w-L-R)/n*.5;
    dayIdx.forEach(function(di,k){
      var x=X(k);
      s+='<rect x="'+(x-bw/2)+'" y="'+Y(D.ens_days.p90[di])+'" width="'+bw+'" height="'+Math.max(1,Y(D.ens_days.p10[di])-Y(D.ens_days.p90[di]))+'" fill="'+BLUE+'" fill-opacity=".22"/>';
      s+='<line x1="'+(x-bw/2)+'" x2="'+(x+bw/2)+'" y1="'+Y(D.ens_days.p50[di])+'" y2="'+Y(D.ens_days.p50[di])+'" stroke="'+BLUE+'" stroke-width="2.5"/>';
      names.forEach(function(nm,j){var v=D.src_days[nm][di];if(v==null)return;
        var xx=x+(j-(names.length-1)/2)*(bw/names.length*0.9);
        s+='<circle cx="'+xx+'" cy="'+Y(v)+'" r="'+(nm==='ARSO'?5:3.6)+'" fill="'+(nm==='ARSO'?ORANGE:INK)+'" fill-opacity="'+(nm==='ARSO'?1:.8)+'" stroke="'+SURF+'" stroke-width="1.5"/>';});
      s+='<text x="'+x+'" y="'+(H-8)+'" text-anchor="middle" font-size="12" fill="'+MUTED+'">'+DN[new Date(D.days[di]+'T12:00:00Z').getUTCDay()]+' '+(+D.days[di].slice(8))+'.</text>';
    });
    s+='<g class="cur"></g></svg>';
    return {svg:s,w:w,X:X,Y:Y,big:1,inv:function(px){return Math.floor((px-L)/(w-L-R)*n);},H:H,T:T,ph:ph,L:L,R:R,n:n};
  },function(k,g,svg){
    var di=dayIdx[k],x=g.X(k);
    svg.querySelector('.cur').innerHTML='<rect x="'+(x-(g.w-g.L-g.R)/g.n/2)+'" y="'+g.T+'" width="'+((g.w-g.L-g.R)/g.n)+'" height="'+g.ph+'" fill="none" stroke="rgba(255,255,255,.55)"/>';
    var rows=names.map(function(nm){var v=D.src_days[nm][di];return '<span style="white-space:nowrap">'+nm+(nm==='ARSO'?' <small>(Ljubno)</small>':'')+' <b>'+(v==null?'—':f1(v))+'</b></span>';}).join(' · ');
    return '<b>'+dl(D.days[di])+'</b> · ansambel: mediana <b>'+f1(D.ens_days.p50[di])+' mm</b> (P10–P90 '+f1(D.ens_days.p10[di])+'–'+f1(D.ens_days.p90[di])+')<br>'+rows+' <small>(mm)</small>';
  },function(){return dayIdx.length;},1);
})();

/* ---- 2: po urah / seštevek ---- */
(function(){
  var mode='rate',sel=null,N=D.t.length,x0=0,x1=N-1;
  var mnames=Object.keys(D.mh);
  var host=el('dz-models');
  if(host){var b0=document.createElement('button');b0.type='button';b0.textContent='brez modela';b0.setAttribute('aria-pressed','true');b0.dataset.k='';host.appendChild(b0);
    mnames.forEach(function(nm){var b=document.createElement('button');b.type='button';b.textContent=nm;b.setAttribute('aria-pressed','false');b.dataset.k=nm;host.appendChild(b);});}
  function series(nm){var a=D.mh[nm],o=[],s=0;for(var i=0;i<N;i++){if(a[i]==null){o.push(null);continue;}s+=a[i];o.push(mode==='rate'?a[i]:s);}return o;}
  function bandOf(){return mode==='rate'?D.rate:D.cum;}
  var fig=wrap('dz-fig2',function(w){
    var L=40,R=12,T=14,B=30,H=250,ph=H-T-B,b=bandOf(),mx=0,i;
    for(i=0;i<N;i++){if(b.p90[i]>mx)mx=b.p90[i];}
    if(sel){series(sel).forEach(function(v){if(v!=null&&v>mx)mx=v;});}
    var sc=nice(Math.max(mx*1.05,mode==='rate'?1:5));
    function X(i){return L+(i-x0)/(x1-x0)*(w-L-R);}function Y(v){return T+ph-v/sc.top*ph;}
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Napoved padavin po urah" font-family="inherit">';
    s=axisY(s,L,R,w,Y,sc.ticks,function(t){return t;});
    s+='<text x="'+L+'" y="'+(T-3)+'" font-size="12" fill="'+MUTED+'">'+(mode==='rate'?'mm na uro':'mm skupaj')+'</text>';
    for(i=0;i<N;i+=24){var xx=X(i);s+='<line x1="'+xx+'" x2="'+xx+'" y1="'+T+'" y2="'+(T+ph+4)+'" stroke="rgba(255,255,255,.18)"/><text x="'+(xx+4)+'" y="'+(H-10)+'" font-size="12" fill="'+MUTED+'">'+dl(D.t[i].slice(0,10))+'</text>';}
    var up='',dn='';for(i=0;i<N;i++){up+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(b.p90[i]).toFixed(1);}
    for(i=N-1;i>=0;i--){dn+='L'+X(i).toFixed(1)+' '+Y(b.p10[i]).toFixed(1);}
    s+='<path d="'+up+dn+'Z" fill="'+BLUE+'" fill-opacity=".22" stroke="none"/>';
    var md='';for(i=0;i<N;i++){md+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(b.p50[i]).toFixed(1);}
    s+='<path d="'+md+'" fill="none" stroke="'+BLUE+'" stroke-width="2.2" stroke-linejoin="round"/>';
    if(sel){var sv=series(sel),d='',pen=false;for(i=0;i<N;i++){if(sv[i]==null){pen=false;continue;}d+=(pen?'L':'M')+X(i).toFixed(1)+' '+Y(sv[i]).toFixed(1);pen=true;}
      s+='<path d="'+d+'" fill="none" stroke="'+ORANGE+'" stroke-width="2" stroke-linejoin="round" stroke-dasharray="5 3"/>';}
    s+='<g class="cur"></g></svg>';
    return {svg:s,w:w,X:X,Y:Y,big:6,inv:function(px){return x0+(px-L)/(w-L-R)*(x1-x0);},T:T,ph:ph};
  },function(i,g,svg){
    var b=bandOf(),x=g.X(i),h='<line x1="'+x+'" x2="'+x+'" y1="'+g.T+'" y2="'+(g.T+g.ph)+'" stroke="rgba(255,255,255,.6)"/>'
      +'<circle cx="'+x+'" cy="'+g.Y(b.p50[i])+'" r="4.5" fill="'+BLUE+'" stroke="'+SURF+'" stroke-width="2"/>';
    var sv=sel?series(sel):null;
    if(sv&&sv[i]!=null)h+='<circle cx="'+x+'" cy="'+g.Y(sv[i])+'" r="4.5" fill="'+ORANGE+'" stroke="'+SURF+'" stroke-width="2"/>';
    svg.querySelector('.cur').innerHTML=h;
    var unit=mode==='rate'?' mm/h':' mm';
    var r='<b>'+hl(D.t[i])+'</b> · ansambel: mediana <b>'+f1(b.p50[i])+unit+'</b> (P10–P90 '+f1(b.p10[i])+'–'+f1(b.p90[i])+')';
    if(sel)r+='<br><span style="color:'+ORANGE+'">&#9632;</span> '+sel+': <b>'+(sv[i]==null?'ni podatka':f1(sv[i])+unit)+'</b>';
    var c=D.cum;r+='<br><small>skupaj do te ure: mediana '+f1(c.p50[i])+' mm, razpon P10–P90 '+f1(c.p10[i])+'–'+f1(c.p90[i])+' mm</small>';
    return r;
  },function(){return N;},34);
  var root=el('dz-fig2');
  Array.prototype.forEach.call(root.querySelectorAll('[data-m]'),function(b){b.addEventListener('click',function(){
    mode=b.dataset.m;Array.prototype.forEach.call(root.querySelectorAll('[data-m]'),function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});fig.redraw();});});
  if(host)host.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;sel=b.dataset.k||null;
    Array.prototype.forEach.call(host.querySelectorAll('button'),function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});fig.redraw();});
})();

/* ---- 3: porazdelitev članov + prag ---- */
(function(){
  var tot=D.ev.totals,n=tot.length,thr=20,mx=Math.max(tot[n-1],40);
  var sc=nice(mx);var inp=el('dz-thr');if(inp){inp.max=sc.top;}
  var fig=wrap('dz-fig3',function(w){
    var L=40,R=12,T=14,B=30,H=190,ph=H-T-B,bins=Math.min(40,Math.floor((w-L-R)/16)),bw=sc.top/bins,cnt=[],i;
    for(i=0;i<bins;i++)cnt.push(0);tot.forEach(function(v){cnt[Math.min(bins-1,Math.floor(v/bw))]++;});
    var cm=Math.max.apply(null,cnt);function X(v){return L+v/sc.top*(w-L-R);}function Y(c){return T+ph-c/cm*ph;}
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Porazdelitev napovedanega seštevka padavin v ansamblu" font-family="inherit">';
    s+='<text x="'+L+'" y="'+(T-3)+'" font-size="12" fill="'+MUTED+'">število članov</text>';
    for(i=0;i<bins;i++){var a=i*bw,b=(i+1)*bw,ex=a>=thr;
      s+='<rect x="'+(X(a)+1)+'" y="'+Y(cnt[i])+'" width="'+Math.max(1,X(b)-X(a)-2)+'" height="'+(T+ph-Y(cnt[i]))+'" rx="2" fill="'+BLUE+'" fill-opacity="'+(ex?.85:.28)+'"/>';}
    s+='<line x1="'+L+'" x2="'+(w-R)+'" y1="'+(T+ph)+'" y2="'+(T+ph)+'" stroke="rgba(255,255,255,.3)"/>';
    sc.ticks.forEach(function(t){s+='<text x="'+X(t)+'" y="'+(H-10)+'" text-anchor="middle" font-size="12" fill="'+MUTED+'">'+t+' mm</text>';});
    s+='<g class="cur"></g></svg>';
    return {svg:s,w:w,X:X,T:T,ph:ph,inv:function(px){return 0;},big:1};
  },function(k,g,svg){
    var c=tot.filter(function(v){return v>=thr;}).length,p=Math.round(100*c/n),xl=g.X(thr);
    el('dz-thr-v').textContent=thr;
    svg.querySelector('.cur').innerHTML='<line x1="'+xl+'" x2="'+xl+'" y1="'+g.T+'" y2="'+(g.T+g.ph)+'" stroke="'+ORANGE+'" stroke-width="2" stroke-dasharray="5 3"/>';
    return 'Vsaj <b>'+thr+' mm</b> do konca '+dl(D.ev.days[2])+' napoveduje <b>'+c+' od '+n+'</b> članov ansambla (<b>'+p+' %</b>). Mediana je '+f1(D.ev.p50)+' mm.';
  },function(){return 1;},0);
  if(inp){inp.addEventListener('input',function(){thr=+inp.value;fig.redraw();});}
})();

/* ---- 4: oktobri po letih ---- */
(function(){
  var ys=Object.keys(D.hist.octs),ev=D.ev;
  var mx=Math.max.apply(null,ys.map(function(y){return D.hist.octs[y];}).concat([D.hist.oct_mean+ev.p90]));
  var sc=nice(mx*1.05);
  wrap('dz-fig4',function(w){
    var L=40,R=12,T=10,B=26,H=230,ph=H-T-B,n=ys.length+1;
    function X(k){return L+(k+.5)/n*(w-L-R);}function Y(v){return T+ph-v/sc.top*ph;}
    var bw=(w-L-R)/n*.55;
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Oktobrske vsote padavin po letih in napovedani dež" font-family="inherit">';
    s=axisY(s,L,R,w,Y,sc.ticks,function(t){return t;});
    s+='<text x="'+L+'" y="'+(T-1)+'" font-size="12" fill="'+MUTED+'" dy="2">mm v mesecu</text>';
    ys.forEach(function(y,k){var v=D.hist.octs[y];s+='<rect x="'+(X(k)-bw/2)+'" y="'+Y(v)+'" width="'+bw+'" height="'+(T+ph-Y(v))+'" rx="3" fill="'+MUTED+'" fill-opacity=".45"/>';
      s+='<text x="'+X(k)+'" y="'+(H-8)+'" text-anchor="middle" font-size="12" fill="'+MUTED+'">'+y+'</text>';});
    var k2=ys.length;
    s+='<rect x="'+(X(k2)-bw/2)+'" y="'+Y(ev.p90)+'" width="'+bw+'" height="'+(T+ph-Y(ev.p90))+'" rx="3" fill="'+BLUE+'" fill-opacity=".25"/>';
    s+='<rect x="'+(X(k2)-bw/2)+'" y="'+Y(ev.p50)+'" width="'+bw+'" height="'+(T+ph-Y(ev.p50))+'" rx="3" fill="'+BLUE+'"/>';
    s+='<text x="'+X(k2)+'" y="'+(H-8)+'" text-anchor="middle" font-size="12" fill="'+INK+'">napoved</text>';
    var ym=Y(D.hist.oct_mean);s+='<line x1="'+L+'" x2="'+(w-R)+'" y1="'+ym+'" y2="'+ym+'" stroke="'+ORANGE+'" stroke-dasharray="5 3" stroke-width="1.5"/>';
    s+='<text x="'+(L+4)+'" y="'+(ym-5)+'" font-size="12" fill="'+INK+'">povprečje '+f1(D.hist.oct_mean)+' mm</text>';
    s+='<g class="cur"></g></svg>';
    return {svg:s,w:w,X:X,Y:Y,T:T,ph:ph,inv:function(px){return Math.floor((px-L)/(w-L-R)*n);},big:1,bw:bw};
  },function(k,g,svg){
    var x=g.X(k);svg.querySelector('.cur').innerHTML='<rect x="'+(x-g.bw*0.65)+'" y="'+g.T+'" width="'+(g.bw*1.3)+'" height="'+g.ph+'" fill="none" stroke="rgba(255,255,255,.55)"/>';
    if(k<ys.length){var v=D.hist.octs[ys[k]];return '<b>oktober '+ys[k]+'</b>: <b>'+f1(v)+' mm</b> ('+Math.round(100*v/D.hist.oct_mean)+' % povprečja)';}
    return '<b>napoved '+dl(ev.days[0])+' – '+dl(ev.days[2])+'</b>: mediana <b>'+f1(ev.p50)+' mm</b> ('+Math.round(100*ev.p50/D.hist.oct_mean)+' % povprečnega oktobra), P90 <b>'+f1(ev.p90)+' mm</b> ('+Math.round(100*ev.p90/D.hist.oct_mean)+' %).';
  },function(){return ys.length+1;},ys.length);
})();

/* ---- 5: krivulja preseganja (log. os) ---- */
(function(){
  var ex=D.hist.exceed,ev=D.ev,cmp=el('dz-cmp'),XM=120,cur=Math.round(ev.p50),YMIN=.05;
  function pv(mm){return Math.max(ex[Math.max(0,Math.min(XM,mm))],YMIN);}
  var fig=wrap('dz-fig5',function(w){
    var L=46,R=12,T=10,B=30,H=220,ph=H-T-B,lg0=Math.log(YMIN),lg1=Math.log(100);
    function X(v){return L+v/XM*(w-L-R);}function Y(p){return T+ph-(Math.log(Math.max(p,YMIN))-lg0)/(lg1-lg0)*ph;}
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Delež trodnevnih obdobij na postaji z vsaj toliko dežja" font-family="inherit">';
    [.1,1,10,100].forEach(function(t){var y=Y(t);s+='<line x1="'+L+'" x2="'+(w-R)+'" y1="'+y+'" y2="'+y+'" stroke="'+GRID+'"/><text x="'+(L-6)+'" y="'+(y+4)+'" text-anchor="end" font-size="12" fill="'+MUTED+'">'+String(t).replace('.',',')+' %</text>';});
    [0,20,40,60,80,100,120].forEach(function(t){s+='<text x="'+X(t)+'" y="'+(H-10)+'" text-anchor="middle" font-size="12" fill="'+MUTED+'">'+t+'</text>';});
    var d='';for(var m=0;m<=XM;m++){d+=(m?'L':'M')+X(m).toFixed(1)+' '+Y(pv(m)).toFixed(1);}
    [['P10',ev.p10],['mediana',ev.p50],['P90',ev.p90]].forEach(function(q,k){var xx=X(q[1]);
      s+='<line x1="'+xx+'" x2="'+xx+'" y1="'+T+'" y2="'+(T+ph)+'" stroke="'+BLUE+'" stroke-dasharray="4 3"/><text x="'+(xx+(k===2?4:-4))+'" y="'+(T+12+k*0)+'" text-anchor="'+(k===2?'start':'end')+'" font-size="12" fill="'+INK+'">'+q[0]+'</text>';});
    s+='<path d="'+d+'" fill="none" stroke="'+MUTED+'" stroke-width="2.2" stroke-linejoin="round"/>';
    s+='<text x="'+(w-R)+'" y="'+(H-22)+'" text-anchor="end" font-size="12" fill="'+MUTED+'" style="display:none"></text><g class="cur"></g></svg>';
    return {svg:s,w:w,X:X,Y:Y,T:T,ph:ph,inv:function(px){return (px-L)/(w-L-R)*XM;},big:5};
  },function(k,g,svg){
    var p=pv(cur),x=g.X(cur);
    svg.querySelector('.cur').innerHTML='<line x1="'+x+'" x2="'+x+'" y1="'+g.T+'" y2="'+(g.T+g.ph)+'" stroke="rgba(255,255,255,.6)"/><circle cx="'+x+'" cy="'+g.Y(p)+'" r="4.5" fill="'+ORANGE+'" stroke="'+SURF+'" stroke-width="2"/>';
    if(cmp){cmp.value=cur;el('dz-cmp-v').textContent=cur;}
    var real=ex[Math.min(XM,cur)];
    var s='V <b>'+(real<.05?'manj kot 0,05':real<1?String(Math.round(real*100)/100).replace('.',','):String(Math.round(real*10)/10).replace('.',','))+' %</b> trodnevnih obdobij na postaji je padlo vsaj <b>'+cur+' mm</b>';
    if(real>0)s+=' (približno 1 obdobje od '+Math.max(1,Math.round(100/real))+')';
    return s+'. Napoved: P10 '+f1(ev.p10)+', mediana '+f1(ev.p50)+', P90 '+f1(ev.p90)+' mm.';
  },function(){return XM+1;},cur);
  function set(v){cur=Math.max(0,Math.min(XM,Math.round(v)));fig.put(0);}
  if(cmp){cmp.addEventListener('input',function(){cur=+cmp.value;fig.put(0);});}
  var plot=el('dz-fig5').querySelector('.dz-plot');
  plot.addEventListener('pointerdown',function(e){var g=plot.querySelector('svg').getBoundingClientRect();});
})();
})();
</script>"""


def main():
    dry = "--dry-run" in sys.argv
    wire = "--wire" in sys.argv
    D = build_data()
    article = build_article(D)
    if dry:
        for s in article["sections"]:
            print("\n##", s["heading"])
            for p in s["paragraphs"]:
                if not p.lstrip().startswith("<"):
                    print(p)
        print("\nLEAD:", article["lead"])
        print("META:", article["meta_description"])
        return
    ftp.TODAY = D["today"]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Dež 8.–10. oktobra", meta_note="napoved",
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
