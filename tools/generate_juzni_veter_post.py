#!/usr/bin/env python3
"""
tools/generate_juzni_veter_post.py -- »Južni veter že drugi dan« (18. 11. 2026).

Ročni podatkovni članek, ne del nobenega workflowa. Številke so izračunane iz posnetka data/juzni-veter-1118.json
(`--fetch`): dnevni povzetki IREICA1 za 17. in 18. 11. (worker /ecowitt-history), trenutna meritev (/ecowitt-current, blok indoor je
izrezan že v workerju, shranjena so samo zunanja polja), primerjalni odčitek Varpolja (IREICA7), meritvi DRSI Črnivec in Gornji Grad,
urna napoved Open-Meteo in MTR (napoved-modela.json). Zgodovina (history.json, brez ERA5) da primerjavo od novembra 2019.

Strukturo zgodbe varujejo assert-i: če se podatki ne ujemajo z besedilom, generator pade -- članek je treba prenoviti, ne zaobiti asserta.
Članek je posnetek na dan objave. Notranjih meritev članek ne uporablja (glej CLAUDE.md).

Usage:
    python3 tools/generate_juzni_veter_post.py --fetch
    python3 tools/generate_juzni_veter_post.py [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_slane_se_ni_post import STYLE as BASE_STYLE, num, fig, tiles, legend  # noqa: E402  (skupni pomočniki, ne podvojeni)

STYLE = BASE_STYLE.replace("</style>", ".jv-m{fill:var(--muted)}.jv-g{stroke:var(--card-border)}"
    ".jv-ph{margin:1.4rem 0}.jv-ph img{display:block;width:100%;height:auto;border-radius:14px;background:#0a0f1c}"
    ".jv-ph figcaption{color:var(--muted);font-size:.88rem;line-height:1.55;margin-top:.5rem}"
    ".jv-pair{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin:1.4rem 0}"
    ".jv-pair .jv-ph{margin:0}"
    ".jv-vid{display:block;width:100%;max-width:300px;height:auto;aspect-ratio:9/16;margin:0 auto;border-radius:14px;background:#000}"
    ".jv-ph.jv-v{max-width:300px;margin:1.4rem auto}"
    "@media(max-width:560px){.jv-pair{grid-template-columns:1fr}}"
    "</style>")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA = "meteorec.si article generator (+https://meteorec.si)"
DATA = os.path.join(ROOT, "data", "juzni-veter-1118.json")
HISTORY = os.path.join(ROOT, "history.json")
MODEL = os.path.join(ROOT, "napoved-modela.json")
SLUG = "juzni-veter-ze-drugi-dan-1118"
IMG = f"/img/blog/{SLUG}"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-juzni-veter.txt")
NBSP = " "
LINK = 'style="color:var(--blue)"'
TODAY = datetime.date(2026, 11, 18)
BAR_T, BAR_W = "#d55181", "#3987e5"        # barve iz preverjene palete semaforja
WIND_HI = 9.8                               # povprečni veter 17. 11. (km/h): prag za primerjavo z zgodovino


def a(href, text):
    return f'<a href="{href}" {LINK}>{text}</a>'


def nbsp(s):
    return re.sub(r"(\d) (°C|%|mm|cm|m\b|km/h|hPa)", lambda m: m.group(1) + NBSP + m.group(2), s)


def temp(x, d=1):
    return f"{num(x, d)}{NBSP}°C".replace("-", "–")


def get(path):
    req = urllib.request.Request(WORKER + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


# ───────────────────────── posnetek ─────────────────────────

def fetch():
    cur = get("/ecowitt-current")["data"]
    assert "indoor" not in cur, "worker je vrnil blok indoor: zasebnost (CLAUDE.md)"
    summ = {s["obsTimeLocal"]: s["metric"] for s in get("/ecowitt-history?start=2026-11-16&end=2026-11-18")["summaries"]}
    vp = get("/varpolje-current")
    vp = {"updated_utc": vp["updated_utc"], **{k: vp["current"].get(k) for k in ("temp_c", "humidity_pct", "wind_speed_kmh", "wind_gust_kmh", "wind_dir_deg")}}
    drsi = get("/crnivec-drsi")
    om = get("/napoved-om")
    mtr = json.load(open(MODEL))
    h = om["hourly"]
    hours19 = [(t, p) for t, p in zip(h["time"], h["precipitation"]) if t.startswith("2026-11-19")]
    out = {
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "ireica1_now": {
            "time_unix": int(cur["outdoor"]["temperature"]["time"]),
            "temp_c": float(cur["outdoor"]["temperature"]["value"]), "humidity_pct": float(cur["outdoor"]["humidity"]["value"]),
            "dew_c": float(cur["outdoor"]["dew_point"]["value"]),
            "wind_kmh": float(cur["wind"]["wind_speed"]["value"]), "gust_kmh": float(cur["wind"]["wind_gust"]["value"]),
            "dir_deg": float(cur["wind"]["wind_direction"]["value"]), "pressure_hpa": float(cur["pressure"]["relative"]["value"]),
        },
        "ireica1_daily": {d: summ[d] for d in ("2026-11-17", "2026-11-18")},
        "varpolje": vp,
        "drsi": {k: drsi["postaje"][k] for k in ("crnivec", "gornji_grad")},
        "om_daily": {d: {"tmax": mx, "tmin": mn} for d, mx, mn in zip(om["daily"]["time"], om["daily"]["temperature_2m_max"], om["daily"]["temperature_2m_min"])},
        "om_rain_19": {"sum_mm": round(sum(p or 0 for _, p in hours19), 1), "hours": [t[11:13] for t, p in hours19 if (p or 0) >= 0.2]},
        "mtr": {"generated_at": mtr["generated_at"], "days": [{k: d[k] for k in ("date", "tmax", "pop", "wind", "gust")} for d in mtr["days"]]},
    }
    json.dump(out, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("✓ posnetek:", os.path.relpath(DATA, ROOT))


# ───────────────────────── podatki ─────────────────────────

def hist_ok():
    H = json.load(open(HISTORY))
    return {k: v for k, v in H.items() if v.get("src") != "era5"}


class Snap:
    def __init__(self):
        self.S = S = json.load(open(DATA, encoding="utf-8"))
        self.fetched = datetime.datetime.fromisoformat(S["fetched_at"])
        assert self.fetched.date() == TODAY, f"posnetek je z dne {self.fetched.date()}; poženi z --fetch"
        self.now = S["ireica1_now"]
        self.d17, self.d18 = S["ireica1_daily"]["2026-11-17"], S["ireica1_daily"]["2026-11-18"]
        self.H = hist_ok()
        assert "2026-11-17" not in self.H, "17. 11. je že v history.json: primerjavo preveri še enkrat"
        self.local_now = datetime.datetime.fromtimestamp(self.now["time_unix"], datetime.timezone(datetime.timedelta(hours=1)))
        assert self.local_now.date() == TODAY and self.local_now.hour < 12, self.local_now   # članek je jutranji posnetek


def hm(dt):
    return f"{dt.hour}.{dt.minute:02d}"


# ───────────────────────── graf ─────────────────────────

def fig_days(S, rows):
    """rows: [(datum, tmin, tmax, veter_povp, delen)]"""
    W, H = 460, 380
    x0, x1 = 40, 440
    yt0, yt1 = 26, 208
    tmin_a, tmax_a = -4.0, 16.0
    yw0, yw1 = 262, 330
    wmax = 12.0
    n = len(rows)
    step = (x1 - x0) / n
    X = lambda k: x0 + step * (k + 0.5)
    YT = lambda t: yt0 + (tmax_a - t) / (tmax_a - tmin_a) * (yt1 - yt0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    out.append(f'<text x="{x0}" y="14" font-size="13" class="jv-m">temperatura: najnižja do najvišja (°C)</text>')
    for t in (0, 5, 10, 15):
        y = YT(t)
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="jv-g" stroke-width="1"/>')
        out.append(f'<text x="{x0 - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="13" class="jv-m">{t}</text>')
    bw = step * 0.46
    for k, (d, lo, hi, w, part) in enumerate(rows):
        op = ".55" if part else "1"
        out.append(f'<rect x="{X(k) - bw / 2:.1f}" y="{YT(hi):.1f}" width="{bw:.1f}" height="{YT(lo) - YT(hi):.1f}" rx="4" fill="{BAR_T}" fill-opacity="{op}"/>')
        out.append(f'<text x="{X(k):.1f}" y="{YT(hi) - 5:.1f}" text-anchor="middle" font-size="12" class="jv-m">{num(hi).replace("-", "–")}</text>')
        out.append(f'<text x="{X(k):.1f}" y="{YT(lo) + 14:.1f}" text-anchor="middle" font-size="12" class="jv-m">{num(lo).replace("-", "–")}</text>')
    out.append(f'<text x="{x0}" y="{yw0 - 12}" font-size="13" class="jv-m">povprečni veter v dnevu (km/h)</text>')
    out.append(f'<line x1="{x0}" y1="{yw1}" x2="{x1}" y2="{yw1}" class="jv-g" stroke-width="1"/>')
    for v in (0, 6, 12):
        y = yw1 - v / wmax * (yw1 - yw0)
        out.append(f'<text x="{x0 - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="13" class="jv-m">{v}</text>')
    for k, (d, lo, hi, w, part) in enumerate(rows):
        hgt = min(w, wmax) / wmax * (yw1 - yw0)
        op = ".55" if part else "1"
        out.append(f'<rect x="{X(k) - bw / 2:.1f}" y="{yw1 - hgt:.1f}" width="{bw:.1f}" height="{hgt:.1f}" rx="3" fill="{BAR_W}" fill-opacity="{op}"/>')
        out.append(f'<text x="{X(k):.1f}" y="{yw1 - hgt - 4:.1f}" text-anchor="middle" font-size="12" class="jv-m">{num(w)}</text>')
        dd = datetime.date.fromisoformat(d)
        out.append(f'<text x="{X(k):.1f}" y="{yw1 + 18}" text-anchor="middle" font-size="12" class="jv-m">{dd.day}. {dd.month}.</text>')
    out.append("</svg>")
    return "".join(out)


def photo(src, alt, cap, cls=""):
    return f'<figure class="jv-ph{cls}"><img src="{IMG}/{src}" alt="{alt}" width="1200" height="900" loading="lazy" decoding="async"><figcaption>{cap}</figcaption></figure>'


# ───────────────────────── članek ─────────────────────────

def build_article(S):
    H, d17, d18, now = S.H, S.d17, S.d18, S.now
    DR = S.S["drsi"]
    VP = S.S["varpolje"]
    OM = S.S["om_daily"]
    MT = {d["date"]: d for d in S.S["mtr"]["days"]}
    t_now = hm(S.local_now)
    drsi_t = datetime.datetime.fromisoformat(DR["crnivec"]["ts"].replace("Z", "+00:00")) + datetime.timedelta(hours=1)
    assert drsi_t.date() == TODAY and drsi_t.hour < 12, drsi_t

    # ── zgodovina: povprečni veter po dnevih (brez ERA5) ──
    winds = {k: v["windspeedAvg"] for k, v in H.items() if v.get("windspeedAvg") is not None}
    n_days = len(winds)
    first_day = min(winds)
    assert first_day == "2019-11-07", first_day
    nov = [w for k, w in winds.items() if k[5:7] == "11"]
    nov_avg = sum(nov) / len(nov)
    w17 = round(d17["windspeedAvg"], 1)
    assert w17 == WIND_HI, w17
    higher = {k: w for k, w in winds.items() if w >= w17}
    assert len(higher) == 21, len(higher)
    assert not any(k[5:7] == "11" for k in higher), "v novembru je že bil enako vetroven dan: besedilo »prvič v novembru« ne drži"
    assert nov_avg < 2.0, nov_avg
    tavg_nov = [v["tempAvg"] for k, v in H.items() if k[5:7] == "11" and v.get("tempAvg") is not None]
    tavg_nov_mean = sum(tavg_nov) / len(tavg_nov)
    assert 5.0 < tavg_nov_mean < 5.8, tavg_nov_mean
    t17avg = round(d17["tempAvg"], 1)
    assert t17avg == 11.1, t17avg
    # lani 15.-16. 11.: podoben dogodek
    y15, y16 = H["2025-11-15"], H["2025-11-16"]
    assert (round(y15["windspeedAvg"], 1), round(y16["windspeedAvg"], 1)) == (8.5, 7.4) and (y15["tempLow"], y16["tempLow"]) == (12.6, 12.9)
    low18 = round(d18["tempLow"], 1)
    assert low18 == 12.6, low18
    nov_lows = sorted((v["tempLow"] for k, v in H.items() if k[5:7] == "11" and v.get("tempLow") is not None), reverse=True)
    assert nov_lows[:2] == [12.9, 12.6], nov_lows[:2]   # do zdaj najtoplejša novembrska minimuma: oba lanska
    low17 = round(d17["tempLow"], 1)
    hi17 = round(d17["tempHigh"], 1)
    assert (low17, hi17) == (1.1, 14.4), (low17, hi17)

    # ── trenutno stanje ──
    assert 12.0 <= now["temp_c"] <= 13.0 and 980 < now["pressure_hpa"] < 1000, now
    assert 190 <= now["dir_deg"] <= 260, now
    cr, gg = DR["crnivec"], DR["gornji_grad"]
    assert cr["vlaga_pct"] >= 95 and cr["temp_c"] < 8, cr
    assert VP["wind_dir_deg"] is not None and 200 <= VP["wind_dir_deg"] <= 280, VP
    diff_gg = gg["temp_c"] - cr["temp_c"]
    assert 4.0 < diff_gg < 5.5, diff_gg

    # ── napoved ──
    rain19 = S.S["om_rain_19"]["sum_mm"]
    assert 15 <= rain19 <= 30 and S.S["om_rain_19"]["hours"], S.S["om_rain_19"]
    rain_from = int(S.S["om_rain_19"]["hours"][0])
    assert 9 <= rain_from <= 14, rain_from
    assert MT["2026-11-19"]["pop"] >= 0.9, MT["2026-11-19"]
    om19 = OM["2026-11-19"]
    assert 6 <= om19["tmax"] <= 10, om19
    mt18 = MT["2026-11-18"]
    assert mt18["wind"] <= 2 and mt18["gust"] <= 20, mt18
    mtr_time = S.S["mtr"]["generated_at"]
    assert mtr_time.startswith("2026-11-17"), mtr_time

    rows = []
    for d in ("2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16"):
        v = H[d]
        rows.append((d, v["tempLow"], v["tempHigh"], v["windspeedAvg"], False))
    rows.append(("2026-11-17", d17["tempLow"], d17["tempHigh"], d17["windspeedAvg"], False))
    rows.append(("2026-11-18", d18["tempLow"], d18["tempHigh"], d18["windspeedAvg"], True))
    w18 = round(d18["windspeedAvg"], 1)
    assert w18 >= 9, w18
    gust_n = now["gust_kmh"]

    aria = (f"Najnižja in najvišja temperatura ter povprečni veter po dnevih od 10. do 18. novembra 2026 v Rečici. Do 16. novembra je veter pod {num(max(r[3] for r in rows[:7]))} km/h, "
            f"17. novembra je povprečje {num(w17)} km/h in najnižja temperatura {num(low17)} °C, 18. novembra je do {t_now} povprečje {num(w18)} km/h in najnižja temperatura {num(low18)} °C.")
    fig1 = fig("Temperatura in veter v Rečici, 10.–18. november",
               fig_days(S, rows).replace("{ARIA}", aria),
               f"Meritve IREICA1. Zadnji stolpec je 18. november samo do {t_now} (bled stolpec): najnižja temperatura je najnižja od polnoči, ne dnevna.")
    leg = legend([("Najnižja do najvišja temperatura", BAR_T, ""), ("Povprečni veter", BAR_W, "")])

    # ── besedilo ──
    lead = (f"V torek je v Rečici pihalo povprečno {num(w17)} km/h. Od 7. novembra 2019 je bilo enako vetrovnih ali vetrovnejših samo {len(higher)} dni od {n_days}, vsi med decembrom in marcem; "
            f"novembra je običajno povprečje {num(nov_avg)} km/h. Južni veter piha tudi danes: ob {t_now} je v dolini {temp(now['temp_c'])}, "
            f"od polnoči pa ni bilo hladneje kot {temp(low18)}.")

    p1 = [
        "<strong>Kratek odgovor:</strong> jug je v dolino pregnal hladen zrak, ki je tu navadno ujet. Zato je veter hkrati prinesel toploto in dvignil nočno temperaturo.",
        f"Dno doline je običajno mirno. Novembra veter v povprečju komaj {num(nov_avg)} km/h, hladen zrak pa se ponoči nabere na tleh. "
        f"V ponedeljek je najnižja temperatura znašala {temp(H['2026-11-16']['tempLow'])}, v torek pa {temp(low17)}, preden je veter prebil v dolino; najvišja torkova je bila {temp(hi17)}. "
        f"Povprečje torka je bilo {temp(t17avg)}, novembrsko povprečje v naših podatkih pa {temp(tavg_nov_mean)}.",
        tiles([
            (num(w17), "km/h", f"povprečni veter v torek. Novembrsko povprečje: {num(nov_avg)} km/h", False),
            (num(low18), "°C", f"najnižja temperatura od polnoči do {t_now} v sredo", True),
            (num(t17avg), "°C", f"povprečna temperatura v torek ({num(tavg_nov_mean)} °C je novembrsko povprečje)", False),
            (num(now["pressure_hpa"], 0), "hPa", f"zračni tlak ob {t_now} (14. 11. povprečje {num(H['2026-11-14']['pressureAvg'], 0)} hPa)", False),
        ]),
    ]
    assert 1020 < H["2026-11-14"]["pressureAvg"] < 1025

    p2 = [
        fig1.replace("<figure", leg + "<figure", 1),
        f"Konec prejšnjega tedna je bilo hladno: v soboto in nedeljo je bila najnižja temperatura {temp(H['2026-11-14']['tempLow'])} in {temp(H['2026-11-15']['tempLow'])}. "
        f"V ponedeljek je veter še komaj dihal (povprečje {num(H['2026-11-16']['windspeedAvg'])} km/h), do torka pa se je obrnil na jug. Najvišja temperatura {temp(hi17)} je za mesec s povprečjem {temp(tavg_nov_mean)} zelo toplo.",
        f"Podoben dogodek je bil lani. 15. in 16. novembra 2025 je povprečni veter znašal {num(y15['windspeedAvg'])} in {num(y16['windspeedAvg'])} km/h, najnižji temperaturi pa {temp(y15['tempLow'])} in {temp(y16['tempLow'])}. "
        f"To sta doslej najtoplejši novembrski noči v našem nizu; današnjih {temp(low18)} je enako kot prva od njiju, a dan še ni končan.",
    ]

    p3 = [
        "Zjutraj je bil ob Menini viden oblak, ki leži čez greben, nad dolino pa je nebo jasno. Podoba je znana: topel vlažen zrak se dviga po južnem pobočju, ob grebenu se ohladi in nastane oblak, na zavetrni strani pa se oblak razkroji.",
        '<div class="jv-pair">'
        + photo("menina-polje.jpg", "Oblak čez greben Menine planine nad hmeljišči in poljem, jasno nebo nad njim", f"Menina z oblakom čez greben, 18. 11. ob 7.25. Nebo nad dolino je jasno.")
        + photo("menina-hala.jpg", "Velika stavba in polje pred Menino, čez greben leži oblak z rožnatimi robovi", "Pogled čez polje proti Menini, 18. 11. ob 7.22. Rožnata barva na robu oblaka je jutranja svetloba.")
        + "</div>",
        photo("oblak-cez-greben.jpg", "Oranžno nebo ob sončnem vzhodu in oblak, ki se preliva čez gozdnat greben nad strehami", "Isti pojav ob sončnem vzhodu, 18. 11. ob 6.55: oblak se preliva čez greben proti dolini."),
        f"Meritve DRSI na Črnivcu (902 m) to potrjujejo. Ob {hm(drsi_t)} je bilo tam {temp(cr['temp_c'])} in {cr['vlaga_pct']} % vlage, rosišče {temp(cr['rosisce_c'])}: zrak je skoraj nasičen, torej je greben v oblaku. "
        f"Veter je pihal {cr['veter_kmh']} km/h s sunki do {cr['sunki_kmh']} km/h. V Gornjem Gradu (428 m) je bilo istočasno {temp(gg['temp_c'])}, v Rečici (IREICA1, 366 m) pa {temp(now['temp_c'])}. "
        f"Razlika med Gornjim Gradom in Črnivcem je {num(diff_gg)} °C na 475 m. Za ta razpon višin je običajna okoli 3 °C (±1,5 °C), danes je torej na zgornji meji.",
        "To je moja razlaga in ne meritev: zrak, ki se v dolini spusti, se ogreje bolj, kot se je na vzponu ohladil, zato je v dolini toplejše kot na enaki višini na drugi strani grebena. Klasičnega fena danes ni, ker zrak v dolini ni suh (vlaga okoli "
        f"{num(now['humidity_pct'], 0)} %).",
    ]

    p4 = [
        f"Smer vetra je v dolini nestanovitna. IREICA1 je ob {t_now} merila {num(now['dir_deg'], 0)}° (jugojugozahod) pri {num(now['wind_kmh'], 0)} km/h s sunki do {num(gust_n, 0)} km/h. "
        f"Za primerjavo: sosednja postaja Varpolje (IREICA7, 1,6 km stran) je istočasno kazala {num(VP['wind_dir_deg'], 0)}° (zahodjugozahod) in {temp(VP['temp_c'])}. "
        "To ni nujno protislovje: v ozki dolini se veter ob pobočjih lomi in vrtinči.",
        f"Zanimiva je še ena številka. Naš napovedni model MTR, ki je umerjen na to postajo, je za današnji dan (izdaja {mtr_time[8:10]}. {mtr_time[5:7]}. ob {int(mtr_time[11:13])}.{mtr_time[14:16]} UTC) napovedal povprečni veter {num(mt18['wind'])} km/h in sunke do {num(mt18['gust'], 0)} km/h. "
        f"Izmerjeno je do {t_now} povprečje {num(w18)} km/h. Verjetno zato, ker je naučen na dolini, kjer je veter večino časa šibek, in prebijanja juga v dolino ni predvidel; "
        "to je moj sklep, ne dokazan vzrok.",
        '<div class="jv-ph jv-v"><video class="jv-vid" autoplay muted loop playsinline controls preload="metadata" width="432" height="768" '
        f'poster="{IMG}/gozd-v-vetru.jpg" aria-label="Vrhovi smrek in jelk se ziblejo v vetru, posnetek 18. novembra 2026 ob 7.32">'
        f'<source src="{IMG}/gozd-v-vetru.mp4" type="video/mp4">'
        f'Vaš brskalnik videa ne predvaja. <a href="{IMG}/gozd-v-vetru.mp4" {LINK}>Odprite datoteko.</a></video>'
        '<figcaption>Krošnje v gozdu v vetru, posnetek 18. 11. ob 7.32 (osem sekund, brez zvoka).</figcaption></div>',
    ]

    p5 = [
        f"Kdaj veter popusti, iz naših podatkov ne morem povedati, napoved vetra po urah nimamo. Vremenska sprememba je napovedana za četrtek: Open-Meteo napoveduje od okoli {rain_from}. ure dež in do polnoči približno {num(rain19, 0)} mm, "
        f"najvišja temperatura pa pade na okoli {num(om19['tmax'], 0)} °C. Naš model MTR za četrtek daje 100 % verjetnost padavin in najvišjo temperaturo {num(MT['2026-11-19']['tmax'], 0)} °C. "
        f"Ko pade toliko dežja, se spremeni tudi Savinja: " + a("/vodostaj-savinje/", "stanje vodostaja") + " je na voljo na posebni strani.",
        "Za petek obe napovedi spet kažeta okoli 14 °C; to je še daleč in se lahko spremeni.",
    ]
    assert OM["2026-11-20"]["tmax"] >= 13 and MT["2026-11-20"]["tmax"] >= 13

    omej = [
        "<ul>"
        f"<li><strong>Dan še ni končan.</strong> Podatki za 18. 11. segajo do {t_now}; najnižja temperatura je najnižja od polnoči in lahko pade, ko se zvečer ohladi.</li>"
        f"<li><strong>Torek še ni v datoteki zgodovine</strong> (history.json), zato je dnevni povzetek vzet neposredno iz postaje.</li>"
        f"<li><strong>Zgodovina je kratka.</strong> Postaja meri od 7. 11. 2019, to je {n_days} dni z meritvami; to je primerjava z našim nizom, ne podnebna statistika.</li>"
        "<li><strong>Razlaga o grebenu in oblaku ni merjena.</strong> Meritve DRSI kažejo, da je greben v oblaku, ostalo je sklep iz oblike pojava.</li>"
        "<li><strong>Smer vetra</strong> je trenutna vrednost enega odčitka, ne povprečje.</li>"
        "<li><strong>Napoved dežja je modelska.</strong> Za ukrepanje ob neurjih in močnem vetru veljajo opozorila ARSO in URSZR.</li>"
        "</ul>",
    ]

    p7 = [
        "Veter ob grebenih je močnejši kot v dolini, v gozdu pa padajo veje; po gozdu hodite previdno. Opozorila za nevihte najdete na strani " + a("/nevihte/", "Nevihte") + ", "
        "meritve v živo na " + a("/vreme-recica-ob-savinji/", "strani za Rečico ob Savinji") + ". Če imate fotografije jutranjega oblaka nad Menino ali gozda v vetru, jih pošljite.",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate samo z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]

    title = "Južni veter že drugi dan: v dolini noč pri 12 °C"
    assert len(title) <= 60, len(title)
    desc = f"Po {num(w17)} km/h povprečnega vetra v torek je tudi v sredo v Rečici najmanj {num(low18, 1)} °C. Zakaj jug pometa dolino in kaj sledi v četrtek."
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Jug je izpodrinil hladen zrak", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — v številkah", "heading": "Torek: prvi tako vetroven novembrski dan v zgodovini postaje", "id": "stevilke", "paragraphs": p2},
        {"label": "03 — Menina", "heading": "Oblak čez greben, jasno v dolini", "id": "menina", "paragraphs": p3},
        {"label": "04 — veter", "heading": "Vetra v dolini model ni videl", "id": "veter", "paragraphs": p4},
        {"label": "05 — kaj sledi", "heading": "Četrtek: dež in ohladitev", "id": "naprej", "paragraphs": p5},
        {"label": "06 — omejitve", "heading": "Česa podatki ne povedo?", "id": "omejitve", "paragraphs": omej},
        {"label": "07 — praktično", "heading": "Kaj lahko naredite?", "id": "prakticno", "paragraphs": p7},
    ]
    lead = nbsp(lead)
    for sec in sections:
        sec["paragraphs"] = [x if ("<svg" in x or "<script" in x or "<figure" in x or "<video" in x or "jv-pair" in x) else nbsp(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["veter", "jug", "Menina", "november", "dolina", "napoved"],
        "section_label": "Vremenski dogodek", "og_photo": "menina-veter-1118", "og_accent_hex": "#fb923c",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: meritve postaje IREICA1 (Ecowitt); sosednja postaja Varpolje (IREICA7), objavlja prijatelj, samo kot primerjava; "
                         "meritvi DRSI na Črnivcu in v Gornjem Gradu (vir: Direkcija RS za infrastrukturo, ceste.si); urna napoved Open-Meteo "
                         f"(prenos {S.fetched.day}. {S.fetched.month}. {S.fetched.year}, CC BY 4.0); model MTR (Meteorec). Fotografije in video: Filip Eremita, 18. 11. 2026. "
                         "Podatki posnetka: data/juzni-veter-1118.json."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<(script|svg|style|video).*?</\1>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|h4|figcaption|li|p|div|b)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace("&shy;", "").replace("&lt;", "<").replace(NBSP, " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        for p in s["paragraphs"]:
            c = clean(p)
            if c:
                out += [c, ""]
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    if "--fetch" in sys.argv:
        fetch()
        return
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    S = Snap()
    article = build_article(S)
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
        og_title="Južni veter\nže drugi dan", meta_note="vremenski dogodek",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html ({round(len(html) / 1024)} kB)")
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
