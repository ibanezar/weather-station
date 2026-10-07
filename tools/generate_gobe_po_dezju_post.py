#!/usr/bin/env python3
"""
tools/generate_gobe_po_dezju_post.py — članek »Gobe po dežju 8.–10. oktobra«.

Ročno zasnovan članek (ne dnevni samodejni), nadaljevanje članka o dežu
(generate_dez_oktober_post.py). Vse številke so izračunane ob zagonu:

  * gobarski model (`gobe_model`): indeks po skupinah in območjih, pragovi sprožilnega dežja
    po vrstah in dnevne padavine Open-Meteo po območjih (ISTI zagon, ki ga vidi tudi stran
    /gobarska-napoved/ — ne drug zajem),
  * ansambel in ARSO iz že objavljenega članka o dežu (JSON, vdelan v stran), da imata oba
    članka ISTE številke.

Članek je POSNETEK ob uri zajema — stran to pove. Notranjih meritev ni nikjer (CLAUDE.md, pravilo
na vrhu). Lektura je izklopljena (CLAUDE.md) — besedilo je treba prebrati ročno.

Usage:
    python3 tools/generate_gobe_po_dezju_post.py [--dry-run] [--wire] [--cache FILE]

`--cache FILE`: zagon modela se shrani v FILE (pickle) in naslednjič prebere od tam — Open-Meteo
ob več zaporednih zagonih vrne 429.
"""
import datetime
import json
import os
import pickle
import re
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import generate_forecast_test_post as ftp  # noqa: E402
import gobe_model as gm  # noqa: E402
from generate_seo_pages import num  # noqa: E402

ROOT = seo.ROOT
YEAR = 2026
SLUG = "gobe-po-dezju-8-10-oktobra-kdaj-in-kje-1007"
RAIN_SLUG = "dez-8-9-oktobra-koliko-ga-bo-padlo-1007"
ECO_ORDER = ["razkrojevalka", "lesna", "mikorizna"]
ECO_NAME = {"razkrojevalka": "Razkrojevalke", "lesna": "Lesne vrste", "mikorizna": "Mikorizne vrste"}
# Vrste, ki jih članek omenja po imenu: (id v species_rules.yaml, skupina je iz modela).
SHOW = ["macrolepiota_procera", "pleurotus_ostreatus", "auricularia_auricula_judae",
        "hydnum_repandum", "boletus_edulis", "cantharellus_cibarius"]
BANDS = [("do 499 m", 0, 500), ("500–799 m", 500, 800), ("800–1099 m", 800, 1100), ("od 1100 m", 1100, 9999)]


def short(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def rng(a, b):
    """»8.–10. 10.« (isti mesec) ali »30. 9.–2. 10.«."""
    da, db = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    if da.month == db.month:
        return f"{da.day}.–{db.day}. {db.month}."
    return f"{da.day}. {da.month}.–{db.day}. {db.month}."


def add_days(iso, n):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=n)).isoformat()


def mm(x):
    return num(x)


def thr_s(x):
    return str(int(x)) if float(x).is_integer() else num(x)


def load_rain_article():
    """Ansambel in ARSO iz objavljenega članka o dežu (JSON med skripto `dez-data`)."""
    path = os.path.join(ROOT, "blog", f"{RAIN_SLUG}.html")
    with open(path, encoding="utf-8") as fh:
        m = re.search(r'id="dez-data">(.*?)</script>', fh.read(), re.S)
    if not m:
        raise SystemExit(f"✗ v {path} ni bloka dez-data")
    return json.loads(m.group(1))


def run_model(cache):
    if cache and os.path.exists(cache):
        with open(cache, "rb") as fh:
            return pickle.load(fh)
    rules = gm.load_rules()
    spots, protected = gm.load_locations(rules)
    locs = gm.fetch_forecast(spots, gm.past_days_needed(rules))
    premium = gm.compute_forecast(rules, spots, locs, gm.load_station_precip(), protected)
    out = (spots, locs, premium)
    if cache:
        with open(cache, "wb") as fh:
            pickle.dump(out, fh)
    return out


def group_mean(loc, day_i, eco, meta):
    v = [s["index"] for s in loc["days"][day_i]["species"] if meta[s["id"]]["ecology"] == eco]
    return st.mean(v)


def build_data(cache):
    R = load_rain_article()
    spots, locs, P = run_model(cache)
    meta = P["species_meta"]
    L = P["locations"]
    home = next(l for l in L if l.get("home"))
    dates = [d["date"] for d in home["days"]]
    ev = R["ev"]
    rain_days = ev["days"]  # 8., 9., 10. 10.
    d1, d3 = rain_days[0], rain_days[-1]

    # dnevne padavine modela v Rečici (isti klic Open-Meteo kot indeks)
    raw = {s["name"]: l for s, l in zip(spots, locs)}
    hd = raw[home["name"]]["daily"]
    hrain = dict(zip(hd["time"], hd["precipitation_sum"]))
    model_mm = round(sum(hrain.get(d) or 0 for d in rain_days), 1)
    extra_day = add_days(d3, 1)
    extra_mm = round(hrain.get(extra_day) or 0, 1)

    # skupine: zamik, vrhovi v Rečici
    eco = {}
    for e in ECO_ORDER:
        sp_ids = [i for i, m in meta.items() if m["ecology"] == e]
        lag = meta[sp_ids[0]]["lag_days"]
        assert all(meta[i]["lag_days"] == lag for i in sp_ids), e
        means = [group_mean(home, i, e, meta) for i in range(len(dates))]
        peak_i = max(range(len(dates)), key=lambda i: means[i])
        best_i = max(range(len(dates)),
                     key=lambda i: max(s["index"] for s in home["days"][i]["species"]
                                       if meta[s["id"]]["ecology"] == e))
        best = max((s for s in home["days"][best_i]["species"] if meta[s["id"]]["ecology"] == e),
                   key=lambda s: s["index"])
        eco[e] = {"lag": lag, "n": len(sp_ids),
                  "win": (add_days(d1, lag[0]), add_days(d3, lag[1])),
                  "mean_now": round(means[0]), "peak_mean": round(means[peak_i]), "peak_date": dates[peak_i],
                  "best": best["index"], "best_date": dates[best_i], "best_name": meta[best["id"]]["name_sl"],
                  "last_mean": round(means[-1])}

    # pragovi sprožilnega dežja po vrstah (iz razlage modela: »… 51.7/40 mm …«)
    thr = {}
    for day in home["days"]:
        for s in day["species"]:
            m = re.search(r"/(\d+(?:\.\d+)?) mm", s["explanation"])
            if m and s["id"] not in thr:
                thr[s["id"]] = float(m.group(1))
    totals = sorted(ev["totals"])
    n = len(totals)
    species_rows = []
    for sid in SHOW:
        if sid not in thr:
            raise SystemExit(f"✗ ni praga za {sid}")
        t = thr[sid]
        species_rows.append({"id": sid, "name": meta[sid]["name_sl"], "eco": meta[sid]["ecology"],
                             "lag": meta[sid]["lag_days"], "thr": t,
                             "share": round(100 * sum(1 for v in totals if v >= t) / n)})

    # višinski pasovi: povprečje skupin ob vrhu lesnih vrst
    dkey = [eco["lesna"]["peak_date"], add_days(eco["lesna"]["peak_date"], -1)]
    di = [dates.index(d) for d in dkey if d in dates]
    bands = []
    for name, lo, hi in BANDS:
        ls = [l for l in L if lo <= l["elev_m"] < hi]
        bands.append({"name": name, "n": len(ls),
                      **{e: round(st.mean(group_mean(l, i, e, meta) for l in ls for i in di)) for e in ECO_ORDER}})

    # območja po dežju modela
    tot = {}
    for s, l in zip(spots, locs):
        d = l["daily"]
        p = dict(zip(d["time"], d["precipitation_sum"]))
        tot[s["name"]] = round(sum(p.get(x) or 0 for x in rain_days), 1)

    def names(items):
        seen, out = set(), []
        for name, v in items:
            base = name.split(" – ")[0].split(" / ")[0]
            if base not in seen:
                seen.add(base)
                out.append((base, v))
        return out

    ranked = sorted(tot.items(), key=lambda kv: -kv[1])
    wet = names(ranked)[:4]
    dry = names(list(reversed(ranked)))[:3]

    best_i = dates.index(eco["lesna"]["peak_date"])
    high = sum(1 for l in L if l["days"][best_i]["overall"] >= 80)
    return {"R": R, "P": P, "home": home, "dates": dates, "today": dates[0], "ev": ev,
            "d1": d1, "d3": d3, "model_mm": model_mm, "extra_day": extra_day, "extra_mm": extra_mm,
            "eco": eco, "species": species_rows, "bands": bands, "wet": wet, "dry": dry,
            "n_loc": len(L), "n_high": high, "high_date": eco["lesna"]["peak_date"],
            "prot": P.get("protected_areas", []), "meta": meta,
            "soil_now": home["days"][0]["soil_moisture_pct"], "model_version": P.get("model_version", "")}


def table(head, rows, wrap=True):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    t = f'<table class="data-table"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'
    return f'<div class="table-scroll" tabindex="0">{t}</div>' if wrap else t


def verdict(rain, thr):
    r = rain / thr
    if r < 0.85:
        return "pod pragom"
    if r <= 1.15:
        return "na meji"
    return "nad pragom"


def build_article(D):
    ev, eco, R = D["ev"], D["eco"], D["R"]
    d1, d3 = D["d1"], D["d3"]
    p50, arso = ev["p50"], ev["arso"]
    mod = D["model_mm"]
    dry = R["dry"]
    lag_all = {e: eco[e]["lag"] for e in ECO_ORDER}
    win = {e: rng(*eco[e]["win"]) for e in ECO_ORDER}
    rr = rng(d1, d3)
    sp = {r["id"]: r for r in D["species"]}
    kuk = eco["razkrojevalka"]
    les = eco["lesna"]
    mik = eco["mikorizna"]
    share_jurcek = sp["boletus_edulis"]["share"]

    lead = (f"Po {dry['days']} suhih dneh in samo {mm(dry['sum'])} mm dežja se Rečici {rr} obeta konec suše. "
            f"Ali bodo zato gobe? Da, a ne vse hkrati in ne takoj. Razkrojevalke in lesne vrste lahko pričakujemo že "
            f"v nekaj dneh po dežju, mikorizne (jurček, lisička, rumeni ježek) pa po zamikih, ki jih uporablja model, šele "
            f"{win['mikorizna']} Hkrati je dež, ki ga napovedujejo ansambli (mediana {mm(p50)} mm), pri nekaterih vrstah "
            f"natanko na meji praga, ki ga uporablja naš gobarski model. Spodaj je, kaj to pomeni po skupinah, po višini "
            f"in po tem, kdaj se splača v gozd.")

    stats = ('<div class="mini-stat-grid">'
             f'<div class="mini-stat"><div class="ms-label">Dež {rr}, ansambel</div><div class="ms-val">{mm(p50)} mm</div><div class="ms-sub">mediana, ARSO {mm(arso)} mm</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Dež v gobarskem modelu</div><div class="ms-val">{mm(mod)} mm</div><div class="ms-sub">en model, Rečica</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Suša pred dežjem</div><div class="ms-val">{dry["days"]} dni</div><div class="ms-sub">{mm(dry["sum"])} mm</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Mikorizne vrste</div><div class="ms-val" style="font-size:1.15rem">{win["mikorizna"]}</div><div class="ms-sub">okno po zamiku</div></div>'
             '</div>')

    # 01 — dež
    sec1 = [
        stats,
        (f"Prvo je treba razčistiti, koliko dežja sploh pričakujemo, ker od tega zavisi vse ostalo. V "
         f"<a href=\"/blog/{RAIN_SLUG}.html\" style=\"color:var(--blue)\">članku o dežu</a> je mediana ansambla ({ev['n']} članov) za "
         f"{rr} {mm(p50)} mm, deset odstotkov članov napoveduje manj kot {mm(ev['p10'])} mm, deset odstotkov več kot "
         f"{mm(ev['p90'])} mm. ARSO napoveduje {mm(arso)} mm."),
        (f"Gobarski model pa ne uporablja ansambla. Za vsako od {D['n_loc']} območij dobi eno napoved Open-Meteo, ki je za Rečico "
         f"za isto obdobje bistveno mokrejša: <strong>{mm(mod)} mm</strong>, torej več kot dvakrat toliko kot mediana ansambla. "
         f"Ta model za {short(D['extra_day'])} napoveduje še {mm(D['extra_mm'])} mm, kar v članku o dežu ni zajeto. "
         f"Indeksi v nadaljevanju so zato <strong>scenarij mokre napovedi</strong>. Če se uresniči ansambelska mediana, bodo "
         f"nižji, predvsem pri vrstah, ki potrebujejo več dežja (glej tabelo praga spodaj)."),
        (f"Pomembna je tudi suša pred dežjem. Tla so danes po modelu skoraj popolnoma suha ({D['soil_now']} % na modelovi lestvici vlažnosti tal), zato prvi "
         f"milimetri dežja najprej namočijo prst in stelje, šele potem se v gozdu začne kaj spreminjati."),
    ]

    # 02 — valovi
    rows = []
    ex = {"razkrojevalka": "orjaški dežnik (marela), poljski kukmak",
          "lesna": "bezgova uhljevka, bukov ostrigar, štorovka",
          "mikorizna": "jurček, lisička, rumeni ježek, kostanjevka"}
    for e in ECO_ORDER:
        c = eco[e]
        rows.append([ECO_NAME[e], ex[e], f"{c['lag'][0]}–{c['lag'][1]} dni", win[e]])
    sec2 = [
        (f"Gobe se na dež ne odzovejo takoj. Vsaka skupina ima v modelu svoj zamik med sprožilnim dežjem in trosnjaki "
         f"(<a href=\"/blog/trije-vali-gob-po-dezju-0911.html\" style=\"color:var(--blue)\">več o tem v septembrskem članku</a>). "
         f"Če računamo od prvega do zadnjega dne dežja ({rr}), so okna taka:"),
        table(["Skupina", "Primeri", "Zamik", "Okno"], rows),
        (f"Model za 7 dni naprej to potrjuje. V Rečici je povprečni indeks razkrojevalk najvišji {short(kuk['peak_date'])} "
         f"({kuk['peak_mean']} %), lesnih vrst {short(les['peak_date'])} ({les['peak_mean']} %), najboljša posamezna vrsta pa je "
         f"{les['best_name'].split(' (')[0].lower()} s {les['best']} % ({short(les['best_date'])}). Pri mikoriznih vrstah povprečni indeks skupine "
         f"v celem obdobju ne preseže {mik['peak_mean']} %, ker je njihovo okno ({win['mikorizna']}) <strong>zunaj sedemdnevnega "
         f"horizonta modela</strong>. Horizont bo začetek tega okna dosegel okoli {short(add_days(eco['mikorizna']['win'][0], -6))}; "
         f"takrat bo model za jurčke in lisičke upošteval dež, ki bo že padel."),
        ("Na kratko: v prvih dneh po dežju ne iščite jurčkov. Prvi pridejo gobe na lesu in na stelji."),
    ]

    # 03 — prag
    prow = []
    for r in D["species"]:
        e = r["eco"]
        prow.append([r["name"].split(" (")[0], ECO_NAME[e].lower(), f"{r['lag'][0]}–{r['lag'][1]} dni", f"{thr_s(r['thr'])} mm",
                     f"{verdict(p50, r['thr'])}", f"{r['share']} %", f"{verdict(mod, r['thr'])}"])
    sec3 = [
        (f"Model za vsako vrsto zahteva določeno količino sprožilnega dežja v njenem oknu. Dež šteje 25 % indeksa, do praga pa "
         f"točke rastejo sorazmerno z dežjem (polovica praga pomeni polovico točk, ne nič). Primerjava za dež "
         f"{rr}:"),
        table(["Vrsta", "Skupina", "Zamik", "Prag", f"Ansambel ({mm(p50)} mm)", "Članov ansambla ≥ prag", f"Model ({mm(mod)} mm)"], prow),
        (f"Pragovi so parametri modela, izpeljani iz baze vrst in še <strong>ne umerjeni na terenu</strong>. Slika je kljub temu "
         f"poučna. Pri mediani ansambla sta bukov ostrigar in marela na meji praga, bezgova uhljevka je pod njim, pri jurčku "
         f"(prag {thr_s(sp['boletus_edulis']['thr'])} mm) pa prag doseže približno {share_jurcek} % članov ansambla. Če se uresniči "
         f"mokrejši scenarij, so vse omenjene vrste nad pragom. Razpon med scenarijema je dovolj velik, da je smiselno počakati "
         f"na meritev na postaji, preden se odpravite daleč."),
    ]

    # 04 — kje
    brow = [[b["name"], str(b["n"]), f"{b['razkrojevalka']} %", f"{b['lesna']} %", f"{b['mikorizna']} %"] for b in D["bands"]]
    wet = ", ".join(f"{n} ({mm(v)} mm)" for n, v in D["wet"])
    dryt = ", ".join(f"{n} ({mm(v)} mm)" for n, v in D["dry"])
    prot = ", ".join(D["prot"][:3]) if D["prot"] else ""
    sec4 = [
        (f"Pri najboljši posamezni vrsti območja ne razlikujemo: {short(D['high_date'])} jo ima {D['n_high']} od {D['n_loc']} območij "
         f"nad 80 %, ker so vrste na lesu in na stelji odvisne predvsem od dežja in temperature. Razlike se pokažejo pri povprečju skupin "
         f"po višini. Povprečje indeksa vseh vrst v skupini za {short(add_days(D['high_date'], -1))} in {short(D['high_date'])}:"),
        table(["Višina", "Območij", "Razkrojevalke", "Lesne vrste", "Mikorizne vrste"], brow),
        ("Po modelu so nižje in srednje lege (do približno 800 m) za prve gobe po dežju ugodnejše kot grebeni nad 1100 m: "
         "tam je hladneje in nekatere vrste so zunaj svojega višinskega območja. Enak vrstni red velja za mikorizne vrste, "
         "čeprav je njihov čas še daleč."),
        (f"Dež po območjih se po tem modelu precej razlikuje. Največ ga je južno od Luč, okoli Lučke Bele, Plahojce in Kašnega vrha: {wet}. "
         f"Najmanj ga je na Solčavskem: {dryt}. Pri tem velja previdnost: gre za en model z mrežo, ki ozkih dolin in grebenov ne "
         f"razločuje, zato je vzorec (več dežja južno od Luč, manj na Solčavskem) zanesljivejši od posameznih številk. Ko bo dež padel, ga primerjajte z "
         f"izmerjenim v svoji dolini."),
        (f"Območij v zaščiti{(' (' + prot + ' …)') if prot else ''} model ne ocenjuje; tam preverite omejitve nabiranja. "
         f"Celotna napoved po območjih je na strani <a href=\"/gobarska-napoved/danes/\" style=\"color:var(--blue)\">Danes po gozdovih</a>."),
    ]

    # 05 — kdaj
    sec5 = [
        (f"Če povzamemo: za razkrojevalke in lesne vrste je najboljši čas po modelu <strong>{rng(kuk['peak_date'], les['peak_date'])}</strong>, "
         f"za mikorizne vrste pa računajte na okno <strong>{win['mikorizna']}</strong>, če bo dežja dovolj. "
         f"Ali ga bo dovolj, bomo vedeli, ko bo dež na postaji izmerjen."),
        ('<div class="callout"><h3>Skratka</h3>'
         f'<p>Dež {rr} konča 18-dnevno sušo, a jurčkov v prvih dneh ne pričakujte. Najprej pridejo gobe na lesu in '
         f'razkrojevalke ({win["razkrojevalka"]}), mikorizne po zamiku {win["mikorizna"]} Pri mediani ansambla ({mm(p50)} mm) jurček doseže okoli {round(100 * p50 / sp["boletus_edulis"]["thr"])} % '
         f'svojega praga, pri mokrejšem scenariju ({mm(mod)} mm) ga presega.</p></div>'),
        ('<div class="disclaimer">Indeks je ocena ugodnosti razmer na podlagi vremena in ni obljuba najdbe. Pred nabiranjem vedno '
         'preverite vrsto z izkušenim nabiralcem ali mikologom – glejte tudi '
         '<a href="/gobarska-napoved/baza-vrst/" style="color:var(--blue)">bazo vrst</a>.</div>'),
    ]

    src = ('<div class="sources"><strong>Viri:</strong><br>'
           f'Dež: ansambel ECMWF ENS, ICON-EU-EPS in GEFS prek <a href="https://open-meteo.com/" target="_blank" rel="noopener" style="color:var(--blue)">Open-Meteo</a> in ARSO, '
           f'<a href="/blog/{RAIN_SLUG}.html" style="color:var(--blue)">članek o dežu</a>.<br>'
           f'Gobarski indeks, zamiki in pragovi po vrstah: model Meteorec (verzija {D["model_version"]}, '
           '<code>species_rules.yaml</code>), vhodni podatki Open-Meteo. Posnetek ob uri zajema, '
           f'današnji izračun je na <a href="/gobarska-napoved/" style="color:var(--blue)">meteorec.si/gobarska-napoved</a>.<br>'
           'Postaja IREICA1, Rečica ob Savinji · <a href="/" style="color:var(--blue)">meteorec.si</a></div>')

    return {
        "title": "Gobe po dežju 8.–10. oktobra: kdaj in kje jih pričakovati",
        "meta_description": (f"Dež {rr} konča {dry['days']} suhih dni. Gobe na lesu pridejo prve ({rng(*les['win'])}), "
                             f"jurčki {win['mikorizna']} Pragovi dežja po vrstah in višini."),
        "tags": ["gobe", "gobarski indeks", "napoved", "dež", "oktober", "2026"],
        "section_label": "Gobarski model",
        "og_photo": "gobe-lastna",
        "og_accent_hex": "#34d399",
        "lead": lead,
        "sources_note": src,
        "sections": [
            {"label": "01 — dež", "heading": "Koliko dežja bodo gobe res dobile", "id": "dez", "paragraphs": sec1},
            {"label": "02 — zamik", "heading": "Kdo pride prvi in kdo šele čez dva tedna", "id": "zamik", "paragraphs": sec2},
            {"label": "03 — prag", "heading": "Dež je pri nekaterih vrstah na meji praga", "id": "prag", "paragraphs": sec3},
            {"label": "04 — kje", "heading": "Kje: višina in količina dežja", "id": "kje", "paragraphs": sec4},
            {"label": "05 — kdaj", "heading": "Kdaj v gozd", "id": "kdaj", "paragraphs": sec5},
        ],
    }


def main():
    dry = "--dry-run" in sys.argv
    wire = "--wire" in sys.argv
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    D = build_data(cache)
    article = build_article(D)
    if dry:
        print("TITLE:", article["title"])
        print("LEAD:", article["lead"])
        for s in article["sections"]:
            print("\n##", s["heading"])
            for p in s["paragraphs"]:
                print(re.sub(r"<[^>]+>", " ", p) if p.lstrip().startswith("<") else p)
        print("\nMETA:", article["meta_description"], len(article["meta_description"]))
        return
    ftp.TODAY = D["today"]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Gobe po dežju\n8.–10. oktobra", meta_note="gobarski model",
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
