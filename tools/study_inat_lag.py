#!/usr/bin/env python3
"""
tools/study_inat_lag.py — kolikšen je zamik med dežjem in opažanjem gobe? (iNaturalist × Open-Meteo)

ENKRATNA študija, ne del cevovoda in ne vklopljena v noben model. Odgovarja na vprašanje bralca
(9. 10. 2026), ali lisičke in druge mikorizne vrste res potrebujejo 8–16 dni po dežju, kot privzeto
računa `species_rules.yaml` (`fruiting_lag_days`, vse »TODO: kalibriraj«).

Metoda
  1. iNaturalist API: opažanja v Sloveniji (okvir), avg–nov, od 2015, `quality_grade=research`,
     odprta lokacija (brez zakritih), natančnost ≤ 5 km. Ključne vrste + KONTROLA: vse glive.
  2. Open-Meteo Archive: dnevne padavine na mreži 0,25° (celica opažanja).
  3. Dogodek dežja = skupina dni ≥ 3 mm (vrzeli ≤ 1 dan) s skupno vsaj 20 mm; začetek = prvi dan.
     DSO = dni od začetka ZADNJEGA dogodka do dneva opažanja. »Po suši« = v 7 dneh pred začetkom
     je padlo < 8 mm (kot zdaj: 18 dni, 1,5 mm).
  4. Razmerje = delež opažanj vrste v razredu DSO / delež vseh gliv v istem razredu. Vsi opazovalci
     radi pohajkujejo po dežju, zato absolutni delež ni merilo; kontrola ujame ta učinek.

Omejitve (zapisane tudi v poročilu): opažanje ni prvi trosnjak (stari trosnjaki se še fotografirajo →
zamik je zgornja ocena), pristranskost po vikendih in poteh, majhni vzorci pri redkih vrstah, ERA5
glajenje padavin. Podatki o opažanjih se NE objavljajo posamično (licence so po opažanju različne):
objavijo se samo agregati.

Usage:
    python3 tools/study_inat_lag.py [--cache-dir DIR] [--out-json F] [--out-md F]
        [--tag T] [--bbox swlat,swlng,nelat,nelng] [--months 8,9,10,11] [--species key,key]

`--tag` loči predpomnilnik in izhod (brez oznake: Slovenija, avg–nov, vse vrste). Razširitev (9. 10. 2026):
  --tag siroko  --bbox 44.6,12.4,47.9,17.6   (jug Avstrije, Slovenija, sever Hrvaške, SV Italije, Z Madžarske)
  --tag poletje --bbox 44.6,12.4,47.9,17.6 --months 5,6,7 --species cantharellus_cibarius,boletus_edulis,...
"""
import collections
import datetime as dt
import json
import math
import os
import statistics as st
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "meteorec-bot/1.0 (+https://meteorec.si/o-postaji.html)"
INAT = "https://api.inaturalist.org/v1"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
BBOX = {"swlat": 45.4, "swlng": 13.3, "nelat": 46.9, "nelng": 16.6}   # Slovenija (in rob sosed)
FIRST_YEAR = 2015
MONTHS = "8,9,10,11"
TAG = ""
CELL = 0.25
DAY_MM, EVENT_MM, GAP, DRY_BEFORE_MM = 3.0, 20.0, 1, 8.0
BINS = [(0, 2), (3, 5), (6, 8), (9, 12), (13, 16), (17, 21), (22, 30), (31, 9999)]
BIN_LABELS = ["0–2", "3–5", "6–8", "9–12", "13–16", "17–21", "22–30", "31+"]
MIN_N = 30
# (ključ, latinsko ime, slovensko ime, model: ekologija, zamik v modelu)
SPECIES = [
    ("cantharellus_cibarius", "Cantharellus cibarius", "Navadna lisička", "mikorizna", (8, 16)),
    ("boletus_edulis", "Boletus edulis", "Jurček", "mikorizna", (8, 16)),
    ("hydnum_repandum", "Hydnum repandum", "Rumeni ježek", "mikorizna", (8, 16)),
    ("imleria_badia", "Imleria badia", "Kostanjevka", "mikorizna", (8, 16)),
    ("macrolepiota_procera", "Macrolepiota procera", "Orjaški dežnik (marela)", "razkrojevalka", (2, 8)),
    ("armillaria_mellea", "Armillaria mellea", "Sivorumena mraznica (štorovka)", "lesna", (3, 10)),
]


def get(url, tries=6):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            wait = 5 * (k + 1) * (3 if "429" in str(e) else 1)
            print(f"  ⚠ {str(e)[:60]} — čakam {wait} s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"✗ ne uspe: {url[:100]}")


def cached(path, fn):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    data = fn()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return data


def taxon_id(name):
    j = get(f"{INAT}/taxa?" + urllib.parse.urlencode({"q": name, "rank": "species", "per_page": 5}))
    for t in j["results"]:
        if t["name"].lower() == name.lower():
            return t["id"]
    raise SystemExit(f"✗ ni taksona {name}")


def fetch_observations(taxon=None, max_pages=400):
    """[[observed_on, lat, lon], …] — samo minimalna polja; ni fotografij, ni uporabnikov."""
    q = {**BBOX, "quality_grade": "research", "geoprivacy": "open", "month": MONTHS, "d1": f"{FIRST_YEAR}-01-01",
         "per_page": 200, "order_by": "id", "order": "asc"}
    q.update({"taxon_id": taxon} if taxon else {"iconic_taxa": "Fungi"})
    out, last = [], 0
    for _ in range(max_pages):
        j = get(f"{INAT}/observations?" + urllib.parse.urlencode({**q, "id_above": last}))
        res = j["results"]
        for o in res:
            last = max(last, o["id"])
            loc, day = o.get("location"), o.get("observed_on")
            acc = o.get("positional_accuracy")
            if not loc or not day or o.get("obscured") or (acc is not None and acc > 5000):
                continue
            lat, lon = (float(x) for x in loc.split(","))
            out.append([day, lat, lon])
        print(f"  … {len(out)} opažanj", end="\r", file=sys.stderr)
        if len(res) < 200:
            break
        time.sleep(1.1)
    print(file=sys.stderr)
    return out


def cell_of(lat, lon):
    return (round(math.floor(lat / CELL) * CELL + CELL / 2, 4), round(math.floor(lon / CELL) * CELL + CELL / 2, 4))


def fetch_rain(cells, end):
    """{ 'lat,lon': {datum: mm} } — Open-Meteo Archive v paketih."""
    cells = sorted(cells)
    out = {}
    for i in range(0, len(cells), 8):
        part = cells[i:i + 8]
        url = ARCHIVE + "?" + urllib.parse.urlencode({
            "latitude": ",".join(str(c[0]) for c in part), "longitude": ",".join(str(c[1]) for c in part),
            "start_date": f"{FIRST_YEAR - 1}-07-01", "end_date": end, "daily": "precipitation_sum",
            "timezone": "Europe/Ljubljana"})
        j = get(url)
        j = j if isinstance(j, list) else [j]
        for c, blk in zip(part, j):
            d = blk["daily"]
            out[f"{c[0]},{c[1]}"] = {t: (v or 0.0) for t, v in zip(d["time"], d["precipitation_sum"])}
        time.sleep(2)
    return out


def events(series):
    """[(začetek, konec, skupaj mm, dry7)] — dogodki dežja iz dnevnih padavin (dict datum→mm)."""
    days = sorted(series)
    idx = {d: i for i, d in enumerate(days)}
    vals = [series[d] for d in days]
    res, i, n = [], 0, len(days)
    while i < n:
        if vals[i] >= DAY_MM:
            j, last, tot = i, i, vals[i]
            k = i + 1
            while k < n and k - last <= GAP + 1:
                if vals[k] >= DAY_MM:
                    last = k
                    tot += vals[k]
                k += 1
            if tot >= EVENT_MM:
                dry7 = sum(vals[max(0, j - 7):j])
                res.append((j, last, tot, dry7 < DRY_BEFORE_MM))
            i = last + 1
        else:
            i += 1
    return days, res


def dso_for(obs_day, days, evs, idx):
    """(DSO, po_suši) za zadnji dogodek z začetkom ≤ dan opažanja; None, če ga ni v 40 dneh."""
    i = idx.get(obs_day)
    if i is None:
        return None
    best = None
    for (s, e, tot, dry) in evs:
        if s <= i:
            best = (i - s, dry)
        else:
            break
    return best if best and best[0] <= 40 else (41, False)


def bin_of(v):
    for k, (a, b) in enumerate(BINS):
        if a <= v <= b:
            return k
    return len(BINS) - 1


def summarize(rows, lag):
    """rows: [(DSO, po_suši)] → agregat."""
    v = [r[0] for r in rows]
    n = len(v)
    cnt = [0] * len(BINS)
    for x in v:
        cnt[bin_of(x)] += 1
    q = st.quantiles(v, n=4) if n >= 4 else [None] * 3
    return {"n": n, "bins": cnt, "share": [c / n if n else 0 for c in cnt],
            "median": st.median(v) if n else None, "q1": q[0], "q3": q[2],
            "le7": sum(1 for x in v if x <= 7) / n if n else None,
            "in_lag": sum(1 for x in v if lag[0] <= x <= lag[1]) / n if n else None}


def main():
    a = sys.argv
    cache = a[a.index("--cache-dir") + 1] if "--cache-dir" in a else "/tmp/inat_lag_cache"
    out_json = a[a.index("--out-json") + 1] if "--out-json" in a else os.path.join(ROOT, "data", "inat-lag-studija.json")
    out_md = a[a.index("--out-md") + 1] if "--out-md" in a else os.path.join(ROOT, "docs", "inat-lag-studija.md")
    os.makedirs(cache, exist_ok=True)
    global BBOX, MONTHS, TAG
    if "--tag" in a:
        TAG = a[a.index("--tag") + 1]
    if "--bbox" in a:
        sw_lat, sw_lng, ne_lat, ne_lng = (float(x) for x in a[a.index("--bbox") + 1].split(","))
        BBOX = {"swlat": sw_lat, "swlng": sw_lng, "nelat": ne_lat, "nelng": ne_lng}
    if "--months" in a:
        MONTHS = a[a.index("--months") + 1]
    wanted = a[a.index("--species") + 1].split(",") if "--species" in a else None
    species = [t for t in SPECIES if wanted is None or t[0] in wanted]
    if "--out-json" not in a and TAG:
        out_json = os.path.join(ROOT, "data", f"inat-lag-studija-{TAG}.json")
    if "--out-md" not in a and TAG:
        out_md = os.path.join(ROOT, "docs", f"inat-lag-studija-{TAG}.md")
    sfx = f"-{TAG}" if TAG else ""

    print(f"Opažanja iNaturalist (okvir {BBOX}, meseci {MONTHS}) …", file=sys.stderr)
    ref = cached(os.path.join(cache, f"fungi{sfx}.json"), lambda: fetch_observations())
    sp_obs = {}
    for key, lat, *_ in species:
        print(f"  {lat}", file=sys.stderr)
        sp_obs[key] = cached(os.path.join(cache, f"{key}{sfx}.json"), lambda l=lat: fetch_observations(taxon_id(l)))

    end = (dt.date.today() - dt.timedelta(days=6)).isoformat()
    allobs = ref + [o for v in sp_obs.values() for o in v]
    cells = {cell_of(o[1], o[2]) for o in allobs if o[0] <= end}
    print(f"Celic: {len(cells)} — padavine …", file=sys.stderr)
    rain = cached(os.path.join(cache, f"rain{sfx}-{end}.json"), lambda: fetch_rain(cells, end))
    ev_cache = {}

    def dso_rows(obs):
        rows = []
        for day, lat, lon in obs:
            if day > end:
                continue
            c = cell_of(lat, lon)
            key = f"{c[0]},{c[1]}"
            if key not in rain:
                continue
            if key not in ev_cache:
                days, evs = events(rain[key])
                ev_cache[key] = (days, evs, {d: i for i, d in enumerate(days)})
            days, evs, idx = ev_cache[key]
            r = dso_for(day, days, evs, idx)
            if r:
                rows.append(r)
        return rows

    ref_rows = dso_rows(ref)
    result = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "rain_end": end,
              "bins": BIN_LABELS, "params": {"region": BBOX, "tag": TAG, "day_mm": DAY_MM, "event_mm": EVENT_MM, "gap": GAP, "dry_before_mm": DRY_BEFORE_MM,
                                             "cell": CELL, "months": MONTHS, "first_year": FIRST_YEAR},
              "reference": {"all": summarize(ref_rows, (0, 0)), "dry": summarize([r for r in ref_rows if r[1]], (0, 0))},
              "species": {}}
    for key, lat, sl, eco, lag in species:
        rows = dso_rows(sp_obs[key])
        dry = [r for r in rows if r[1]]
        result["species"][key] = {"name_lat": lat, "name_sl": sl, "model_ecology": eco, "model_lag": list(lag),
                                  "all": summarize(rows, lag), "dry": summarize(dry, lag)}
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print("✓", out_json)
    write_report(result, out_md)
    print("✓", out_md)


def pct(x):
    return "—" if x is None else f"{100 * x:.0f} %"


def write_report(R, path):
    ref = R["reference"]
    L = ["# Zamik med dežjem in opažanjem gob: iNaturalist × Open-Meteo", "",
         f"Posnetek: {R['generated'][:10]}, padavine do {R['rain_end']}. Okvir: {R['params']['region']}, meseci {R['params']['months']}. "
         f"Skript: `tools/study_inat_lag.py`. "
         "**Enkratna študija, v model ni vgrajena.** Podrobna metoda in omejitve so na dnu.", "",
         "## Povzetek po vrstah", "",
         "DSO = dni od začetka zadnjega dogodka dežja (≥ 20 mm v nekaj dneh) do opažanja. »Model« je privzeti zamik v "
         "`species_rules.yaml`. »≤ 7 d« je delež opažanj v tednu po začetku dežja. »V oknu modela« je delež opažanj z DSO "
         "znotraj modelovega zamika. Primerjava z vsemi glivami (kontrola) kaže, ali je vrsta nad ali pod povprečjem.", "",
         "| Vrsta | n | mediana DSO (Q1–Q3) | ≤ 7 d | model | v oknu modela | vse glive: ≤ 7 d |",
         "|---|---|---|---|---|---|---|"]
    for k, s in R["species"].items():
        a = s["all"]
        med = "—" if a["median"] is None else (f"{a['median']:.0f} ({a['q1']:.0f}–{a['q3']:.0f})" if a["q1"] is not None else f"{a['median']:.0f}")
        L.append(f"| {s['name_sl']} | {a['n']} | {med} d | {pct(a['le7'])} | {s['model_lag'][0]}–{s['model_lag'][1]} d | "
                 f"{pct(a['in_lag'])} | {pct(ref['all']['le7'])} |")
    L += ["", "## Porazdelitev po razredih DSO (delež opažanj vrste / vseh gliv)", "",
          "| Vrsta | " + " | ".join(R["bins"]) + " |", "|---|" + "---|" * len(R["bins"])]
    L.append("| **vse glive (kontrola)** | " + " | ".join(pct(x) for x in ref["all"]["share"]) + " |")
    for k, s in R["species"].items():
        L.append(f"| {s['name_sl']} (n={s['all']['n']}) | " + " | ".join(pct(x) for x in s["all"]["share"]) + " |")
    L += ["", "Razmerje (vrsta ÷ vse glive; > 1 pomeni, da je vrsta v tem razredu pogostejša od povprečne glive):", "",
          "| Vrsta | " + " | ".join(R["bins"]) + " |", "|---|" + "---|" * len(R["bins"])]
    for k, s in R["species"].items():
        cells = []
        for sh, rs in zip(s["all"]["share"], ref["all"]["share"]):
            cells.append("—" if s["all"]["n"] < MIN_N or rs == 0 else f"{sh / rs:.1f}")
        L.append(f"| {s['name_sl']} | " + " | ".join(cells) + " |")
    L += ["", "## Samo po suši (7 dni pred dežjem < 8 mm, kot zdaj)", "",
          "| Vrsta | n | mediana DSO | ≤ 7 d | v oknu modela |", "|---|---|---|---|---|"]
    for k, s in R["species"].items():
        d = s["dry"]
        med = "—" if d["median"] is None else f"{d['median']:.0f}"
        L.append(f"| {s['name_sl']} | {d['n']} | {med} d | {pct(d['le7'])} | {pct(d['in_lag'])} |")
    L.append(f"| vse glive | {ref['dry']['n']} | {ref['dry']['median']:.0f} d | {pct(ref['dry']['le7'])} | — |")
    L += ["", "## Metoda in omejitve", "",
          "- **Opažanja:** iNaturalist, okvir in meseci so v glavi poročila, 2015–2026, `research`, odprta lokacija, "
          "natančnost ≤ 5 km. Shranjena so samo datum in koordinate (zaokrožene na celico 0,25°), ne fotografije in ne uporabniki.",
          "- **Padavine:** Open-Meteo Archive (ERA5), celica 0,25°. ERA5 glaji padavine in zaokroži močne plohe, zato so dogodki bolj mehki, "
          "kot jih je videla postaja.",
          "- **DSO** je merjen od začetka ZADNJEGA dogodka. Ob ponavljajočem dežju je zato kratek, čeprav je trosnjake sprožil "
          "prejšnji dež. Podskupina »po suši« to zmanjša, a ima malo opažanj.",
          "- **Opažanje ni prvi trosnjak.** Stari trosnjaki (marela, jurček) ostanejo več dni in se še fotografirajo, zato je pravi zamik "
          "do prvega trosnjaka verjetno krajši od izmerjenega.",
          "- **Pristranskost opazovalcev:** ljudje hodijo v gozd po dežju, ob vikendih in ob poteh. Kontrola (vse glive) to deloma ujame, "
          "a vključuje tudi lišaje in lesne vrste z drugačnim zamikom.",
          "- **Majhni vzorci:** pri vrstah z n < 60 (ježek, štorovka) so razmerja šum. Prag zaupanja v poročilu je n ≥ 30.",
          "- Zaključki so v `docs/inat-lag-studija-zakljucki.md`."]
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
