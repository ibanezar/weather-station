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
    cur.pop("indoor", None)   # zasebnost (CLAUDE.md): worker bloka že reže, tu še enkrat; shranimo samo izbrana zunanja polja
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
    # dnevni povzetek postaje (12,6) je grobejši od trenutne meritve ob 7.42 (12,2): za najnižjo vrednost od polnoči vzamemo nižjo
    low18_summary = round(d18["tempLow"], 1)
    low18 = round(min(d18["tempLow"], now["temp_c"]), 1)
    assert low18_summary == 12.6 and low18 == 12.2, (low18_summary, low18)
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
    rows.append(("2026-11-18", low18, d18["tempHigh"], d18["windspeedAvg"], True))
    w18 = round(d18["windspeedAvg"], 1)
    assert w18 >= 9, w18
    gust_n = now["gust_kmh"]

    aria = (f"Najnižja in najvišja temperatura ter povprečni veter po dnevih od 10. do 18. novembra 2026 v Rečici. Do 16. novembra je veter pod {num(max(r[3] for r in rows[:7]))} km/h, "
            f"17. novembra je povprečje {num(w17)} km/h in najnižja temperatura {num(low17)} °C, 18. novembra je do {t_now} povprečje {num(w18)} km/h in najnižja temperatura {num(low18)} °C.")
    fig1 = fig("Temperatura in veter v Rečici, 10.–18. november",
               fig_days(S, rows).replace("{ARIA}", aria),
               f"Meritve postaje IREICA1. Zadnji stolpec prikazuje 18. november le do {t_now} in je zato svetlejši. Najnižja temperatura je najnižja vrednost od polnoči, ne pa končna dnevna vrednost.")
    leg = legend([("Najnižja do najvišja temperatura", BAR_T, ""), ("Povprečni veter", BAR_W, "")])

    # ── besedilo (jezikovno in slogovno urejeno, Filip, 18. 11. 2026) ──
    lead = (f"V torek je v Rečici pihal veter s povprečno hitrostjo {num(w17)} km/h. Od 7. novembra 2019 je bilo enako vetrovnih ali še vetrovnejših le {len(higher)} od {n_days} dni, vsi med decembrom in marcem. "
            f"Novembrsko povprečje znaša le {num(nov_avg)} km/h. Južni veter piha tudi danes. Ob {t_now} je bilo v dolini {temp(now['temp_c'])}, "
            f"kar je hkrati najnižja zabeležena vrednost od polnoči.")

    p1 = [
        "<strong>Kratek odgovor:</strong> južni veter je v dolino prinesel toplejši zrak in izpodrinil hladnega, ki se tu običajno zadržuje pri tleh. Zato je veter hkrati prinesel toploto in preprečil običajno nočno ohlajanje.",
        f"Dno doline je sicer večinoma mirno. Novembra povprečna hitrost vetra znaša komaj {num(nov_avg)} km/h, hladen zrak pa se ponoči nabira pri tleh. "
        f"V ponedeljek je najnižja temperatura znašala {temp(H['2026-11-16']['tempLow'])}, v torek pa {temp(low17)}, preden je veter prodrl v dolino. Najvišja torkova temperatura je bila {temp(hi17)}. "
        f"Povprečna temperatura v torek je znašala {temp(t17avg)}, medtem ko je novembrsko povprečje v naših podatkih {temp(tavg_nov_mean)}.",
        tiles([
            (num(w17), "km/h", f"povprečna hitrost vetra v torek. Novembrsko povprečje: {num(nov_avg)} km/h.", False),
            (num(low18), "°C", f"najnižja zabeležena temperatura od polnoči do {t_now} v sredo.", True),
            (num(t17avg), "°C", f"povprečna temperatura v torek. Novembrsko povprečje: {num(tavg_nov_mean)} °C.", False),
            (num(now["pressure_hpa"], 0), "hPa", f"zračni tlak ob {t_now} (trenutna vrednost). Povprečje 14. novembra: {num(H['2026-11-14']['pressureAvg'], 0)} hPa.", False),
        ]),
    ]
    assert 1020 < H["2026-11-14"]["pressureAvg"] < 1025

    p2 = [
        fig1.replace("<figure", leg + "<figure", 1),
        f"Konec prejšnjega tedna je bilo hladno. V soboto je najnižja temperatura znašala {temp(H['2026-11-14']['tempLow'])}, v nedeljo pa {temp(H['2026-11-15']['tempLow'])}. "
        f"V ponedeljek je veter še komaj pihal, njegovo povprečje je znašalo {num(H['2026-11-16']['windspeedAvg'])} km/h. Do torka se je obrnil na jug. "
        f"Najvišja temperatura {temp(hi17)} je glede na novembrsko povprečje {temp(tavg_nov_mean)} zelo visoka.",
        f"Podoben dogodek smo imeli že lani. 15. in 16. novembra 2025 je povprečna hitrost vetra znašala {num(y15['windspeedAvg'])} oziroma {num(y16['windspeedAvg'])} km/h, najnižji temperaturi pa {temp(y15['tempLow'])} in {temp(y16['tempLow'])}. "
        f"To sta doslej najtoplejši novembrski noči v našem nizu meritev. Današnjih {temp(low18)} je nekoliko manj, vendar je to najnižja zabeležena vrednost do {t_now} in današnji dan še ni končan.",
    ]

    p3 = [
        "Zjutraj je bilo ob Menini mogoče opaziti oblak, ki se je raztezal čez greben, medtem ko je bilo nad dolino nebo jasno. Gre za značilen pojav: topel in vlažen zrak se ob južnem pobočju dviga, ob grebenu ohlaja in kondenzira v oblak. Na zavetrni strani se oblak nato razkroji.",
        '<div class="jv-pair">'
        + photo("menina-polje.jpg", "Oblak čez greben Menine planine nad hmeljišči in poljem, jasno nebo nad njim", "Menina z oblakom čez greben, 18. 11. ob 7.25. Nad dolino je nebo jasno.")
        + photo("menina-hala.jpg", "Velika stavba in polje pred Menino, čez greben leži oblak z rožnatimi robovi", "Pogled čez polje proti Menini, 18. 11. ob 7.22. Rožnata barva na robu oblaka je posledica jutranje svetlobe.")
        + "</div>",
        photo("oblak-cez-greben.jpg", "Oranžno nebo ob sončnem vzhodu in oblak, ki se preliva čez gozdnat greben nad strehami", "Isti pojav ob sončnem vzhodu, 18. 11. ob 6.55: oblak se preliva čez greben proti dolini."),
        f"Meritve DRSI na Črnivcu (902 m) ta pojav dodatno osvetljujejo. Ob {hm(drsi_t)} je bilo tam {temp(cr['temp_c'])}, relativna vlažnost zraka pa {cr['vlaga_pct']} %. "
        f"Rosišče je znašalo {temp(cr['rosisce_c'])}, kar pomeni, da je bil zrak skoraj nasičen z vlago. To je skladno z opažanjem, da je bil greben v oblaku. "
        f"Veter je pihal s hitrostjo {cr['veter_kmh']} km/h, sunki pa so dosegali {cr['sunki_kmh']} km/h.",
        f"V Gornjem Gradu (428 m) je bilo ob istem času {temp(gg['temp_c'])}, v Rečici (IREICA1, 366 m) pa {temp(now['temp_c'])}. "
        f"Temperaturna razlika med Gornjim Gradom in Črnivcem je tako znašala {num(diff_gg)} °C na višinski razliki 475 m. "
        "Običajna razlika za ta razpon višin je okoli 3 °C (±1,5 °C), današnja vrednost pa je torej na zgornji meji tega razpona. To je odstopanje, ne dokaz fenskega pojava.",
        "To je moja razlaga, ne neposredna meritev: zrak, ki se spušča proti dolini, se pri spuščanju segreva. Tako je lahko v dolini topleje kot na primerljivi nadmorski višini na drugi strani grebena. "
        f"Za klasični fen danes ne gre, saj zrak v dolini ni suh – relativna vlažnost je okoli {num(now['humidity_pct'], 0)} %.",
    ]

    p4 = [
        f"Smer vetra v dolini je precej nestanovitna. Postaja IREICA1 je ob {t_now} izmerila smer {num(now['dir_deg'], 0)}° (južna do jugojugozahodna smer) in hitrost {num(now['wind_kmh'], 0)} km/h, sunki pa so dosegali {num(gust_n, 0)} km/h.",
        f"Za primerjavo: sosednja postaja Varpolje (IREICA7), oddaljena 1,6 km, je ob istem času kazala veter iz smeri {num(VP['wind_dir_deg'], 0)}° (zahodjugozahod) in temperaturo {temp(VP['temp_c'])}. "
        "Različna podatka o smeri vetra nista nujno protislovna. V ozki dolini se veter ob pobočjih preusmerja in vrtinči, zato se lahko smer že na kratki razdalji precej razlikuje.",
        f"Zanimiva je še ena primerjava. Naš napovedni model MTR, ki je umerjen na meritve te postaje, je za današnji dan (napoved, izdana {int(mtr_time[8:10])}. {int(mtr_time[5:7])}. ob {int(mtr_time[11:13])}.{mtr_time[14:16]} UTC) napovedal povprečno hitrost vetra {num(mt18['wind'])} km/h in sunke do {num(mt18['gust'], 0)} km/h. "
        f"Do {t_now} je bila izmerjena povprečna hitrost vetra {num(w18)} km/h. Primerjava je le okvirna, ker napoved velja za cel dan, meritev pa za prvih nekaj ur.",
        "Verjetno je razlog v tem, da je model naučen na razmerah v dolini, kjer je veter večino časa šibek, zato preboja južnega vetra v dolino ni predvidel. To je moja razlaga, ne dokazan vzrok odstopanja.",
        '<div class="jv-ph jv-v"><video class="jv-vid" autoplay muted loop playsinline controls preload="metadata" width="432" height="768" '
        f'poster="{IMG}/gozd-v-vetru.jpg" aria-label="Vrhovi smrek in jelk se ziblejo v vetru, posnetek 18. novembra 2026 ob 7.32">'
        f'<source src="{IMG}/gozd-v-vetru.mp4" type="video/mp4">'
        f'Vaš brskalnik videa ne predvaja. <a href="{IMG}/gozd-v-vetru.mp4" {LINK}>Odprite datoteko.</a></video>'
        '<figcaption>Krošnje v gozdu v vetru, posnetek 18. 11. ob 7.32 (osem sekund, brez zvoka).</figcaption></div>',
    ]

    p5 = [
        "Kdaj bo veter popustil, iz razpoložljivih podatkov ne morem napovedati, saj nimamo urne napovedi vetra.",
        f"Vremenska sprememba je napovedana za četrtek. Open-Meteo napoveduje začetek dežja okoli {rain_from}. ure, do polnoči pa naj bi padlo približno {num(rain19, 0)} mm padavin. "
        f"Najvišja temperatura naj bi se spustila na okoli {num(om19['tmax'], 0)} °C. Tudi naš model MTR za četrtek napoveduje 100-odstotno verjetnost padavin in najvišjo temperaturo {num(MT['2026-11-19']['tmax'], 0)} °C.",
        "Ob večji količini dežja se lahko spremeni tudi pretok Savinje. Trenutno stanje lahko spremljate na strani " + a("/vodostaj-savinje/", "Vodostaj Savinje") + ".",
        "Za petek obe napovedi znova kažeta okoli 14 °C, vendar je do takrat še precej časa, zato se napoved lahko spremeni.",
    ]
    assert OM["2026-11-20"]["tmax"] >= 13 and MT["2026-11-20"]["tmax"] >= 13

    omej = [
        "<ul>"
        f"<li><strong>Dan še ni končan.</strong> Podatki za 18. november segajo do {t_now}. Najnižja temperatura je najnižja vrednost od polnoči in se lahko do konca dneva še spremeni, zlasti če se bo zvečer ohladilo.</li>"
        f"<li><strong>Najnižja temperatura je zabeležena z dvema odčitkoma.</strong> Dnevni povzetek postaje kaže {temp(low18_summary)}, trenutna meritev ob {t_now} pa {temp(now['temp_c'])}. Za najnižjo vrednost od polnoči smo vzeli nižjo.</li>"
        "<li><strong>Torkovih podatkov še ni v zgodovinski datoteki.</strong> Podatki za torek še niso vključeni v history.json, zato je dnevni povzetek vzet neposredno iz meritev postaje.</li>"
        f"<li><strong>Zgodovina meritev je kratka.</strong> Postaja meri od 7. novembra 2019, kar pomeni {n_days} dni meritev. Gre za primerjavo z našim nizom podatkov, ne za podnebno statistiko.</li>"
        "<li><strong>Razlaga dogajanja ob grebenu ni neposredno izmerjena.</strong> Meritve DRSI kažejo, da je bil greben v oblaku, preostala razlaga pa temelji na opazovanju pojava.</li>"
        "<li><strong>Smer vetra je trenutna vrednost.</strong> Gre za en sam odčitek, ne za povprečno smer vetra.</li>"
        "<li><strong>Primerjava z modelom MTR je okvirna.</strong> Napovedano povprečje velja za cel dan, izmerjeno pa samo do jutra.</li>"
        "<li><strong>Napoved dežja temelji na modelih.</strong> Pri ukrepanju ob neurjih in močnem vetru upoštevajte uradna opozorila ARSO in URSZR.</li>"
        "</ul>",
    ]

    p7 = [
        "Veter je ob grebenih močnejši kot v dolini, v gozdu pa lahko zaradi sunkov padajo veje. Pri hoji po gozdu bodite zato previdni. Opozorila pred nevihtami najdete na strani " + a("/nevihte/", "Nevihte") + ", "
        "meritve v živo pa na " + a("/vreme-recica-ob-savinji/", "strani za Rečico ob Savinji") + ".",
        "Če imate fotografije jutranjega oblaka nad Menino ali gozda v vetru, jih pošljite.",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le ob navedbi avtorja (Filip Eremita, Meteorec) in neposredne povezave na ta članek. '
        'Za prepis ali vdelavo grafov in izračunov se predhodno dogovorite z avtorjem.</p>',
    ]

    title = "Južni veter že drugi dan: v dolini noč pri 12 °C"
    assert len(title) <= 60, len(title)
    desc = "Po povprečno 9,8 km/h vetra v torek je tudi v sredo v Rečici toplo: od polnoči ni bilo pod 12 °C. Zakaj južni veter prepiha dolino in kaj sledi v četrtek?"
    assert f"{num(w17)}" in desc and low18 >= 12.0
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Južni veter je izpodrinil hladen zrak", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — v številkah", "heading": "Torek: najbolj vetroven novembrski dan v zgodovini postaje", "id": "stevilke", "paragraphs": p2},
        {"label": "03 — Menina", "heading": "Oblak se preliva čez greben, nad dolino pa je jasno", "id": "menina", "paragraphs": p3},
        {"label": "04 — veter", "heading": "Vetrovnih razmer v dolini model ni zaznal", "id": "veter", "paragraphs": p4},
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
        "sources_note": ("Meritve postaje IREICA1 (Ecowitt); sosednja postaja Varpolje (IREICA7), ki jo objavlja prijatelj, uporabljena zgolj za primerjavo; "
                         "meritve DRSI na Črnivcu in v Gornjem Gradu (vir: Direkcija Republike Slovenije za infrastrukturo, ceste.si); urna napoved Open-Meteo "
                         f"(prenos {S.fetched.day}. {S.fetched.month}. {S.fetched.year}, CC BY 4.0); model MTR (Meteorec). Fotografije in video: Filip Eremita, 18. 11. 2026. "
                         "Podatki za članek: data/juzni-veter-1118.json."),
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
