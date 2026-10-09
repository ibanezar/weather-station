#!/usr/bin/env python3
"""
tools/generate_gobe_suha_tla_post.py — članek »Padlo je 10 mm na suha tla. Zakaj jurčki še počakajo?«

Ročno zasnovan članek (ne dnevni samodejni). Vse številke so izračunane ob zagonu:

  * dež: IREICA1 (history.json za pretekle dni, Worker /hourly za dan, ki ga history.json še nima),
  * pragovi in zamiki vrst: species_rules.yaml (isti kot gobarski model),
  * vlaga tal: Open-Meteo `soil_moisture_3_to_9cm` za domače območje — MODELSKA OCENA, postaja je ne meri.
    Preračun na lestvico 0–100 % je isti kot v gobe_model (scoring.soil_moisture dry/full).

Članek je POSNETEK ob uri zajema — stran to pove. Notranjih meritev ni nikjer (CLAUDE.md, pravilo na
vrhu). Lektura je izklopljena (CLAUDE.md) — besedilo je treba prebrati ročno.

Usage:
    python3 tools/generate_gobe_suha_tla_post.py [--dry-run] [--wire] [--rain-day 2026-10-08]
"""
import datetime
import json
import os
import re
import statistics as st
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import generate_forecast_test_post as ftp  # noqa: E402
from generate_seo_pages import num  # noqa: E402
import yaml  # noqa: E402

ROOT = seo.ROOT
YEAR = 2026
SLUG = "padlo-10-mm-na-suha-tla-zakaj-jurcki-pocakajo-1009"
RAIN_DAY = "2026-10-08"
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
SPECIES_SHOW = [("boletus_edulis", "Jurček"), ("cantharellus_cibarius", "Lisička"),
                ("macrolepiota_procera", "Orjaški dežnik (marela)"),
                ("hydnum_repandum", "Rumeni ježek"), ("pleurotus_ostreatus", "Bukov ostrigar")]
ECO_ROWS = [("razkrojevalka", "Razkrojevalke stelje in travinja", "marela, kukmaki"),
            ("lesna", "Lesne vrste", "bukov ostrigar, bezgova uhljevka"),
            ("mikorizna", "Mikorizne vrste", "jurček, lisička, rumeni ježek")]
CSS = """<style>
.mini-stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.4rem 0 2rem}
.mini-stat{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:.9rem .8rem;text-align:center}
.ms-label{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-family:'JetBrains Mono',monospace}
.ms-val{font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:1.4rem;line-height:1.1;margin:.18rem 0 .1rem;color:var(--cyan)}
.ms-sub{font-size:.72rem;color:var(--muted)}
@media(max-width:640px){.mini-stat-grid{grid-template-columns:repeat(2,1fr)}}
.disclaimer{background:rgba(239,68,68,.06);border:1px solid var(--card-border);border-radius:10px;padding:.8rem 1rem;margin:1.2rem 0;font-size:.85rem;color:var(--muted)}
.sources{font-size:.82rem;color:var(--muted);border-top:1px solid rgba(255,255,255,.07);margin-top:2.2rem;padding-top:1rem;line-height:1.7}
</style>"""


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": WORKER_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def cached_open_meteo(url):
    """Open-Meteo ob več zaporednih zagonih vrne 429: odgovor se shrani v --cache FILE in ob
    ponovnem zagonu prebere od tam; sicer ponovni poskusi z zamikom."""
    import time
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    if cache and os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    last = None
    for delay in (0, 15, 45, 90):
        if delay:
            print(f"Open-Meteo: čakam {delay}s …")
            time.sleep(delay)
        try:
            data = get_json(url)
            if cache:
                json.dump(data, open(cache, "w", encoding="utf-8"))
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
    raise last


def d_short(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def d_long(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {seo.MES_GEN[d.month]}"


def d_add(iso, n):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=n)).isoformat()


def d_rng(a, b):
    da, db = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    if da.month == db.month:
        return f"{da.day}.–{db.day}. {db.month}."
    return f"{da.day}. {da.month}.–{db.day}. {db.month}."


WEEKDAY = ["ponedeljek", "torek", "sredo", "četrtek", "petek", "soboto", "nedeljo"]
WEEKDAY_NOM = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]


def dni(n):
    return "dan" if n == 1 else "dni"


def build_data(rain_day):
    hist = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    rules = yaml.safe_load(open(os.path.join(ROOT, "species_rules.yaml"), encoding="utf-8"))
    home = next(l for l in rules["locations"] if l.get("home"))
    smc = rules["scoring"]["soil_moisture"]
    dry_v, full_v = float(smc["dry"]), float(smc["full"])

    # ── dež na postaji: history.json za pretekle dni, /hourly za dan dežja ──
    rain = {k: v["precipTotal"] for k, v in hist.items()
            if v.get("precipTotal") is not None and k < rain_day}
    hourly = get_json(PROXY + "/hourly")["observations"]
    vals = [o["metric"]["precipTotal"] for o in hourly
            if o["obsTimeLocal"][:10] == rain_day and o.get("metric", {}).get("precipTotal") is not None]
    if not vals:
        raise SystemExit(f"/hourly nima meritev za {rain_day} — ne izmišljam številke.")
    rain_mm = max(vals)
    event_mm = None
    try:
        cur = get_json(PROXY + "/ecowitt-current")
        event_mm = cur["data"]["rainfall"]["event"]["value"]
    except Exception:  # noqa: BLE001  (dopolnilna številka, ni nujna)
        pass

    pre14 = round(sum(rain.get(d_add(rain_day, -i), 0.0) for i in range(1, 15)), 1)
    # suha serija: dnevi pred dežjem brez ≥ 1 mm
    n_dry, d = 0, d_add(rain_day, -1)
    while d in rain and rain[d] < 1.0:
        n_dry += 1
        d = d_add(d, -1)
    last_wet = d
    last_wet_mm = rain.get(d)
    sept = {k: rain[k] for k in ("2026-09-10", "2026-09-11") if k in rain}
    sept_sum = round(sum(sept.values()), 1)

    # ── vlaga tal (model) ──
    q = urllib.parse.urlencode({
        "latitude": home["lat"], "longitude": home["lon"],
        "hourly": "soil_moisture_3_to_9cm,soil_moisture_9_to_27cm", "daily": "precipitation_sum",
        "past_days": 35, "forecast_days": 4, "timezone": "Europe/Ljubljana"}, safe=",")
    om = cached_open_meteo("https://api.open-meteo.com/v1/forecast?" + q)
    t = om["hourly"]["time"]
    days = {}
    for i, x in enumerate(t):
        days.setdefault(x[:10], []).append((om["hourly"]["soil_moisture_3_to_9cm"][i],
                                            om["hourly"]["soil_moisture_9_to_27cm"][i]))

    def mean(ix, day):
        v = [p[ix] for p in days.get(day, []) if p[ix] is not None]
        return st.mean(v) if v else None

    def pct(v):
        return None if v is None else round(100 * max(0.0, min(1.0, (v - dry_v) / (full_v - dry_v))))

    om_rain = dict(zip(om["daily"]["time"], om["daily"]["precipitation_sum"])).get(rain_day)
    today = datetime.date.today().isoformat()
    soil = {day: {"top": mean(0, day), "deep": mean(1, day)} for day in sorted(days)}
    for day, s in soil.items():
        s["pct"] = pct(s["top"])
    peak_sept = max((dd for dd in soil if "2026-09-09" <= dd < rain_day and soil[dd]["pct"] is not None),
                    key=lambda dd: soil[dd]["top"])
    before = d_add(rain_day, -1)
    after = [dd for dd in soil if dd >= rain_day and soil[dd]["pct"] is not None][:4]
    peak_after = max(after, key=lambda dd: soil[dd]["pct"])
    nxt = d_add(peak_after, 1)

    # ── pragovi in zamiki ──
    sp = {s["id"]: s for s in rules["species"]}
    thr = {sid: float(sp[sid]["rain_7d_min"]) for sid, _ in SPECIES_SHOW}
    lags = {}
    for s in rules["species"]:
        lags.setdefault(s["ecology"], set()).add((int(s["fruiting_lag_days"]["min"]),
                                                  int(s["fruiting_lag_days"]["max"])))
    for e, v in lags.items():
        assert len(v) == 1, f"zamik skupine {e} ni enoten: {v}"
        lags[e] = next(iter(v))

    return {
        "today": today, "rain_day": rain_day, "rain_mm": rain_mm, "event_mm": event_mm,
        "pre14": pre14, "n_dry": n_dry, "last_wet": last_wet, "last_wet_mm": last_wet_mm,
        "sept_sum": sept_sum, "home": home["name"], "dry_v": dry_v, "full_v": full_v,
        "soil": soil, "peak_sept": peak_sept, "before": before, "after": after,
        "peak_after": peak_after, "nxt": nxt, "om_rain": om_rain, "rain_hist": rain, "thr": thr, "lags": lags,
    }


def table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    t = f'<table class="data-table"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'
    return f'<div class="table-scroll" tabindex="0">{t}</div>'


def build_article(D):
    S = D["soil"]
    rd = D["rain_day"]
    rain = D["rain_mm"]
    wd = WEEKDAY_NOM[datetime.date.fromisoformat(rd).weekday()]
    wd_acc = WEEKDAY[datetime.date.fromisoformat(rd).weekday()]
    thr_j = D["thr"]["boletus_edulis"]
    share_j = round(100 * rain / thr_j)
    s_before = S[D["before"]]["pct"]
    s_peak_sept = S[D["peak_sept"]]["pct"]
    s_peak = S[D["peak_after"]]["pct"]
    last_day = D["after"][-1]
    s_last = S[last_day]["pct"]
    peak_days = [dd for dd in D["after"] if S[dd]["pct"] == s_peak]
    peak_txt = (d_short(peak_days[0]) if len(peak_days) == 1
                else d_rng(peak_days[0], peak_days[-1]))
    deep_pct = round(100 * max(0.0, min(1.0, (S[D["peak_after"]]["deep"] - D["dry_v"]) / (D["full_v"] - D["dry_v"]))))
    gap_days = (datetime.date.fromisoformat(D["before"]) - datetime.date.fromisoformat(D["peak_sept"])).days
    between = round(sum(v for k, v in D["rain_hist"].items() if D["peak_sept"] < k <= D["before"]), 1)
    deep_b, deep_a = S[D["before"]]["deep"], S[D["peak_after"]]["deep"]
    need = max(0.0, thr_j - rain)
    L = D["lags"]
    win = {e: d_rng(d_add(rd, L[e][0]), d_add(rd, L[e][1])) for e in L}

    lead = (f"{wd.capitalize()}, {d_long(rd)}, je bil na postaji IREICA1 prvi pravi dež po {D['n_dry']} dneh: "
            f"padlo je {num(rain)} mm (zaokroženo 10). V prejšnjih 14 dneh skupaj le {num(D['pre14'])} mm. Gobarski model za jurčka "
            f"šteje 25 mm v sedmih dneh, torej je padlo {share_j} % praga. A število milimetrov ni cela zgodba: "
            f"po modelski oceni so bila tla pred dežjem skoraj povsem suha ({s_before} % na lestvici modela), "
            f"tak dež pa zmoči predvsem vrhnjo plast. Zato jurčki in lisičke še počakajo.")

    stats = ('<div class="mini-stat-grid">'
             f'<div class="mini-stat"><div class="ms-label">Padlo {d_short(rd)}</div><div class="ms-val">{num(rain)} mm</div><div class="ms-sub">postaja IREICA1</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Prej 14 dni</div><div class="ms-val">{num(D["pre14"])} mm</div><div class="ms-sub">skupaj</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Prag za jurčka</div><div class="ms-val">{int(thr_j)} mm</div><div class="ms-sub">v 7 dneh</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Vlaga tal pred dežjem</div><div class="ms-val">{s_before} %</div><div class="ms-sub">modelska ocena</div></div>'
             '</div>')

    rows1 = []
    for sid, name in SPECIES_SHOW:
        t = D["thr"][sid]
        rows1.append([name, f"{int(t)} mm", f"{num(rain)} mm", f"{round(100 * rain / t)} %"])
    ev = ""
    sec1 = [
        stats,
        (f"V gobarskem modelu mora v sedmih dneh pasti vsaj toliko dežja, kot zahteva vrsta. Jurček potrebuje {int(thr_j)} mm, "
         f"lisička {int(D['thr']['cantharellus_cibarius'])} mm, marela {int(D['thr']['macrolepiota_procera'])} mm. "
         f"Dež {d_short(rd)} je tako izpolnil od tretjine do polovice teh pragov.{ev}"),
        table(["Vrsta", "Prag (7 dni)", f"Padlo do {d_short(rd)}", "Delež praga"], rows1),
        (f"Za primerjavo: 10. in 11. septembra je padlo {num(D['sept_sum'])} mm, kar je skoraj petkrat prag za jurčka. "
         f"Prej je zadnjih {D['n_dry']} {dni(D['n_dry'])} vsak dan padlo manj kot 1 mm "
         f"(zadnji večji dež: {d_short(D['last_wet'])}, {num(D['last_wet_mm'])} mm)."),
    ]

    ROWS_SOIL = []
    picks = [D["peak_sept"], d_add(D["peak_sept"], 16), D["before"]] + D["after"]
    seen = set()
    for dd in picks:
        if dd in seen or dd not in S or S[dd]["pct"] is None:
            continue
        seen.add(dd)
        note = ""
        if dd == D["peak_sept"]:
            note = "vrh po septembrskem nalivu"
        elif dd == D["before"]:
            note = "dan pred dežjem"
        elif dd == rd:
            note = "dan dežja"
        elif dd > D["today"]:
            note = "napoved modela"
        elif dd == D["today"]:
            note = "danes (deloma napoved)"
        ROWS_SOIL.append([d_short(dd), f"{S[dd]['pct']} %", f"{S[dd]['top']:.3f}".replace(".", ","), note])

    sec2 = [
        (f"Postaja vlage tal ne meri. Spodnje številke so <strong>modelska ocena</strong> Open-Meteo za plast 3–9 cm "
         f"na območju {D['home']}, preračunana na lestvico gobarskega modela: 0 % pomeni {num(D['dry_v'], 2)} m³/m³ "
         f"ali manj, 100 % pa {num(D['full_v'], 2)} m³/m³ ali več."),
        table(["Datum", "Vlaga tal", "m³/m³", "Opomba"], ROWS_SOIL),
        (f"Po septembrskem nalivu je bila vrhnja plast po modelu povsem namočena ({s_peak_sept} %). Do dneva pred dežjem "
         f"je v {gap_days} dneh, ko je padlo skupaj le {num(between)} mm, upadla na <strong>{s_before} %</strong>. Dež {d_short(rd)} jo je "
         f"po modelu dvignil na {s_peak} % ({peak_txt}), "
         + (f"do {d_short(last_day)} pa naj bi spet padla na {s_last} %." if s_last is not None and s_last < s_peak else
            "kar se do konca napovednega okna ne spremeni.")),
        (f"Globlja plast (9–27 cm) skoraj ne reagira: {num(deep_b, 3)} → {num(deep_a, 3)} m³/m³. Na isti lestvici je to {deep_pct} %: takle dež se vpije v prvih "
         f"centimetrih. Mikorizni micelij seže globlje od zgornjih nekaj centimetrov, zato je za jurčke pomembno, "
         f"koliko vode pride globlje, ne samo ali je zgornja plast kratko mokra."),
        ('<div class="disclaimer">Vlaga tal je model, ne meritev.'
         + (f' Open-Meteo je za {d_long(rd)} ocenil {num(D["om_rain"])} mm dežja, postaja pa jih je izmerila {num(rain)}, '
            'zato so vrednosti po dežju lahko preoptimistične.' if D["om_rain"] is not None and D["om_rain"] - rain >= 2 else '')
         + ' Gobarski indeks na strani uporablja isto vlago tal.</div>'),
    ]

    rows3 = []
    for e, name, ex in ECO_ROWS:
        a, b = L[e]
        rows3.append([name, ex, f"{a}–{b} dni", win[e]])
    sec3 = [
        (f"Gobe ne zrastejo naslednji dan: vsaka skupina potrebuje čas od dežja do trosnjaka. Model zamike bere "
         f"iz pravil vrst (<code>species_rules.yaml</code>)."),
        table(["Skupina", "Primeri", "Zamik po dežju", f"Okno po dežju {d_short(rd)}"], rows3),
        (f"Okno pomeni, da je dež trosnjak <em>lahko</em> sprožil, ne da je ta zrasel. Pri mikoriznih vrstah je okno "
         f"{win['mikorizna']}, torej se ne odpre pred {d_long(d_add(rd, L['mikorizna'][0]))}. Pri razkrojevalkah je zamik krajši "
         f"({L['razkrojevalka'][0]}–{L['razkrojevalka'][1]} dni), a tudi tam pomaga le, če so tla dovolj vlažna za rast."),
    ]

    sec4 = [
        (f"Po modelu in izmerjenem dežju je slika taka:"),
        ("<ul>"
         f"<li><strong>Marela, ostrigarji in druge vrste s krajšim zamikom:</strong> v oknu {win['razkrojevalka']} (razkrojevalke) "
         f"in {win['lesna']} (lesne vrste) je okno odprto. Vrhnja plast tal je po modelu po dežju deloma namočena ({s_peak} %), a model je dež ocenil višje od meritve, zato je rast verjetnejša tam, kjer se vlaga dlje drži: v senci, ob potokih, na severnih pobočjih.</li>"
         f"<li><strong>Jurčki in lisičke:</strong> ne prej kot {d_long(d_add(rd, L['mikorizna'][0]))}. Dež je izpolnil le "
         f"{share_j} % praga za jurčka in globlja plast tal ostaja suha ({deep_pct} % na lestvici modela), zato po modelu ni razloga za veliko rast, razen če pride še dež.</li>"
         f"<li><strong>Kaj bi sliko spremenilo:</strong> še vsaj {int(round(need))} mm v sedmih dneh bi jurčku pripeljalo prag. "
         "Napovedi dežja so negotove, zato glej tekoči indeks.</li>"
         "</ul>"),
        ('Današnji indeks po vrstah in območjih je na <a href="/gobarska-napoved/danes/" style="color:var(--blue)">'
         'meteorec.si/gobarska-napoved/danes</a>. Če greš v gozd, nam lahko pustiš opažanje (območje, ne točne lokacije), '
         'saj brez tvojih najdb ne vemo, ali model drži.'),
    ]

    src = ('<div class="sources">Viri: postaja IREICA1, Rečica ob Savinji (dež: <code>history.json</code> in urni podatki); '
           'gobarski model (praga in zamiki: <code>species_rules.yaml</code>); vlaga tal: Open-Meteo, modelska ocena za '
           f'območje {D["home"]}. Posnetek ob uri zajema, današnji izračun je na '
           '<a href="/gobarska-napoved/" style="color:var(--blue)">meteorec.si/gobarska-napoved</a>.<br>'
           'Postaja IREICA1, Rečica ob Savinji · <a href="/" style="color:var(--blue)">meteorec.si</a></div>')

    return {
        "title": "Padlo je 10 mm na suha tla. Zakaj jurčki še počakajo?",
        "meta_description": (f"{num(rain)} mm dežja po {D['n_dry']} suhih dneh je bilo {share_j} % praga za jurčka. "
                             f"Vlaga tal pred dežjem: {s_before} % (model). Jurčki najprej {d_long(d_add(rd, L['mikorizna'][0]))}."),
        "tags": ["gobe", "gobarski indeks", "dež", "vlaga tal", "oktober", "2026"],
        "section_label": "Gobarski model",
        "og_photo": "gobe-lastna",
        "og_accent_hex": "#34d399",
        "lead": lead,
        "sources_note": CSS + src,
        "sections": [
            {"label": "01 — dež", "heading": "Koliko je padlo in koliko bi moralo", "id": "dez", "paragraphs": sec1},
            {"label": "02 — tla", "heading": "Tla so bila pred dežjem skoraj suha", "id": "tla", "paragraphs": sec2},
            {"label": "03 — zamik", "heading": "Kdo pride prvi in kdo šele čez dva tedna", "id": "zamik", "paragraphs": sec3},
            {"label": "04 — nabiranje", "heading": "Kaj to pomeni za v gozd", "id": "gozd", "paragraphs": sec4},
        ],
    }


def main():
    dry = "--dry-run" in sys.argv
    wire = "--wire" in sys.argv
    rd = sys.argv[sys.argv.index("--rain-day") + 1] if "--rain-day" in sys.argv else RAIN_DAY
    D = build_data(rd)
    article = build_article(D)
    if dry:
        print("TITLE:", article["title"])
        print("\nLEAD:", article["lead"])
        for s in article["sections"]:
            print("\n##", s["heading"])
            for p in s["paragraphs"]:
                if p.lstrip().startswith("<table") or 'class="table-scroll"' in p:
                    rows = re.findall(r"<tr>(.*?)</tr>", p, re.S)
                    for r in rows:
                        cells = re.findall(r"<t[hd]>(.*?)</t[hd]>", r, re.S)
                        print("  | " + " | ".join(re.sub(r"<[^>]+>", "", c) for c in cells))
                else:
                    print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip())
        print("\nMETA:", article["meta_description"], len(article["meta_description"]))
        return
    ftp.TODAY = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Padlo je 10 mm\nna suha tla", meta_note="gobarski model",
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
