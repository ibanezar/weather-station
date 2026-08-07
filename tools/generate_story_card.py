#!/usr/bin/env python3
"""
tools/generate_story_card.py — dnevna kartica za Instagram/Facebook zgodbo.

Zjutraj pogleda napoved, trenutne meritve, kakovost zraka, cvetni prah,
gobarski indeks in zgodovino postaje (history.json) za Rečico ob Savinji,
nato izmed ~24 tipov kartic ("tem") izbere tisto, ki je danes najbolj
aktualna -- vsaka tema ima več besedilnih različic (skupaj prek 100), da se
kartica čez čas ne ponavlja.

Teme (razvrščene po prioriteti, višja zmaga, če je več hkrati aktualnih):
  FROST, SNOW              — zmrzal / sneg
  STORM_RISK                — nevihta v napovedi
  HEAT_EXTREME               — vročinski ekstrem (>=33 °C)
  UV_EXTREME                  — zelo visok UV (>=9)
  WINDY                        — močni sunki vetra
  AIR_QUALITY_POOR              — slab zrak
  RAIN_HEAVY, RAIN_TIMING         — izdaten dež / kdaj se začne
  HEAT                              — vroč dan (28-33 °C)
  COLD_MORNING                       — hladno jutro
  FOG_MORNING                         — megla
  UV_HIGH                              — visok UV (7-9)
  HUMID_MUGGY                           — soparno
  POLLEN_HIGH                            — visok cvetni prah
  RECORD_WATCH                            — blizu/nad rekordom za ta dan
  TROPICAL_NIGHT                           — tropska noč za nami
  DROUGHT_DRY_STREAK                        — dolg suh niz
  MUSHROOM                                   — gobarski pogoji
  AIR_QUALITY_GOOD                            — čist zrak
  VS_YESTERDAY                                 — velika sprememba od včeraj
  PRESSURE_TREND                                — hiter padec/dvig tlaka
  SUNRISE_SUNSET                                 — dolžina dneva
  GENERAL                                         — splošni povzetek (fallback)

Zapiše og/story/<YYYY-MM-DD>.jpg (1080x1920) + og/story/latest.json.
Objavita jo tools/post_story_to_facebook.py in post_story_to_instagram.py
prek .github/workflows/daily-story.yml.

POZOR — notranje meritve: fetch_current() spodaj IZBRIŠE blok `indoor` iz
odgovora postaje (glej CLAUDE.md). Na kartico gre samo zunanja temperatura.

Usage:
  python3 tools/generate_story_card.py             # zapiše kartico za danes
  python3 tools/generate_story_card.py --dry-run   # samo izpiše izbrano temo
  python3 tools/generate_story_card.py --list-topics  # izpiše vse teme + št. različic
"""
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "og", "story")
BG_DIR = os.path.join(ROOT, "og", "bg")
SITE = "https://meteorec.si"
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
HISTORY = os.path.join(ROOT, "history.json")
GOBE_JSON = os.path.join(ROOT, "gobarska-napoved", "index.json")

LAT, LON = 46.325779, 14.921137
TZ = ZoneInfo("Europe/Ljubljana")

# Kartico gledajo ljudje zjutraj -- zanima jih preostanek dneva, ne noč za nami.
DAY_START_HOUR = 6

# Koliko starih kartic obdržimo v repozitoriju.
KEEP_DAYS = 14

W, H = 1080, 1920
FONT_DIR = "/usr/share/fonts/truetype/liberation/"

WHITE = (255, 255, 255)
MUTED = (208, 219, 235)
DIM = (168, 182, 203)

# Barvna paleta poudarkov, deljena med temami.
C_BLUE = (96, 165, 250)     # dež
C_ORANGE = (249, 115, 22)   # vročina
C_RED = (244, 63, 94)       # ekstremi/opozorila
C_CYAN = (34, 211, 238)     # splošno/hladno
C_PURPLE = (167, 139, 250)  # nevihta
C_GREEN = (52, 211, 153)    # dober zrak/gobe
C_AMBER = (245, 158, 11)    # UV/cvetni prah/suša

# WMO kode -> kratek slovenski opis (samo tiste, ki jih pri nas res srečamo)
WMO = {
    0: "jasno", 1: "pretežno jasno", 2: "delno oblačno", 3: "oblačno",
    45: "megla", 48: "megla z ivjem",
    51: "rosenje", 53: "rosenje", 55: "močno rosenje",
    61: "rahel dež", 63: "dež", 65: "močan dež",
    71: "rahlo sneženje", 73: "sneženje", 75: "močno sneženje",
    77: "snežna zrna",
    80: "plohe", 81: "plohe", 82: "močne plohe",
    85: "snežne plohe", 86: "močne snežne plohe",
    95: "nevihta", 96: "nevihta s točo", 99: "nevihta s točo",
}
SNOW_CODES = {71, 73, 75, 77, 85, 86}
STORM_CODES = {95, 96, 99}
FOG_CODES = {45, 48}

MES_NOM = {1: "januar", 2: "februar", 3: "marec", 4: "april", 5: "maj",
           6: "junij", 7: "julij", 8: "avgust", 9: "september", 10: "oktober",
           11: "november", 12: "december"}
DNI = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]

# Cvetni prah -- isti pragovi kot na /kakovost-zraka/ (tools/generate_kakovost_zraka_page.py),
# da se izraz "visok cvetni prah" na kartici in na strani ne razideta.
POLLEN_SPECIES = [
    ("grass_pollen", "trave"), ("birch_pollen", "breza"), ("alder_pollen", "jelša"),
    ("mugwort_pollen", "pelin"), ("ragweed_pollen", "ambrozija"),
]
POLLEN_TH = {
    "grass_pollen": (10, 50, 200), "birch_pollen": (10, 100, 1000),
    "alder_pollen": (10, 100, 1000), "mugwort_pollen": (10, 100, 300),
    "ragweed_pollen": (10, 50, 200),
}


# ────────────────────────── pridobivanje podatkov ──────────────────────────

def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "meteorec-story/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_forecast():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&hourly=precipitation,precipitation_probability,temperature_2m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code,"
        "sunrise,sunset,uv_index_max,wind_speed_10m_max,wind_gusts_10m_max,"
        "apparent_temperature_max"
        "&timezone=Europe%2FLjubljana&forecast_days=1&past_days=1"
    )
    return fetch_json(url)


def fetch_air_quality():
    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={LAT}&longitude={LON}"
        "&current=european_aqi,pm2_5,pm10"
        "&hourly=grass_pollen,birch_pollen,alder_pollen,mugwort_pollen,ragweed_pollen"
        "&timezone=Europe%2FLjubljana&forecast_days=1"
    )
    try:
        return fetch_json(url)
    except Exception as e:
        print(f"⚠ Kakovost zraka ni dosegljiva: {e}", file=sys.stderr)
        return None


def fetch_arso():
    """Uradna napoved ARSO za Ljubno ob Savinji (najbližji kraj na njihovem seznamu)."""
    try:
        data = fetch_json(f"{WORKER}/arso-forecast")
        today = datetime.datetime.now(TZ).date().isoformat()
        for day in data.get("days", []):
            if day.get("valid_date") == today:
                return day
    except Exception as e:
        print(f"⚠ ARSO napoved ni dosegljiva: {e}", file=sys.stderr)
    return None


def fetch_current():
    """Trenutne meritve postaje.

    Blok `indoor` se IZBRIŠE takoj ob prevzemu -- notranja temperatura in vlaga
    sta Filipova zasebna stvar in ne smeta iz hiše (CLAUDE.md). Kartica gre na
    FB/IG, zato tu ne sme ostati niti sled notranjih meritev.
    """
    try:
        data = fetch_json(f"{WORKER}/ecowitt-current")
        payload = data.get("data") or {}
        payload.pop("indoor", None)
        return payload
    except Exception as e:
        print(f"⚠ Trenutne meritve niso dosegljive: {e}", file=sys.stderr)
        return {}


def load_history():
    try:
        with open(HISTORY, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠ history.json ni dosegljiv: {e}", file=sys.stderr)
        return {}


def load_gobe_index(today_iso):
    try:
        with open(GOBE_JSON, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today_iso:
            return data
    except Exception as e:
        print(f"⚠ gobarski indeks ni dosegljiv: {e}", file=sys.stderr)
    return None


# ────────────────────────── pomožne funkcije ──────────────────────────

def num_sl(x, d=0):
    if x is None:
        return "–"
    return f"{x:.{d}f}".replace(".", ",")


def variant_index(ctx, name, n):
    """Deterministična (a navidez naključna) izbira besedilne različice --
    isti dan in ista tema vedno dasta isto številko, drug dan drugo."""
    h = hashlib.sha256(f"{ctx['date_iso']}|{name}".encode()).hexdigest()
    return int(h[:8], 16) % n


def pick(ctx, name, variants):
    return variants[variant_index(ctx, name, len(variants))]


def dry_streak(hist, end_date):
    """Št. zaporednih dni s <0,2 mm dežja, ki se konča na `end_date` (vključno)."""
    n = 0
    d = end_date
    while True:
        key = d.isoformat()
        entry = hist.get(key)
        if entry is None or (entry.get("precipTotal") or 0) >= 0.2:
            break
        n += 1
        d -= datetime.timedelta(days=1)
    return n


def calendar_day_record(hist, month, day, exclude_year):
    """Najvišja izmerjena tempHigh za ta koledarski dan (katerokoli leto)."""
    best = None
    for key, entry in hist.items():
        try:
            y, m, d = int(key[:4]), int(key[5:7]), int(key[8:10])
        except ValueError:
            continue
        if m == month and d == day and y != exclude_year:
            th = entry.get("tempHigh")
            if th is not None and (best is None or th > best):
                best = th
    return best


# ────────────────────────── kontekst ──────────────────────────

def build_ctx():
    now = datetime.datetime.now(TZ)
    today = now.date()
    fc = fetch_forecast()
    daily = fc.get("daily", {})
    hourly = fc.get("hourly", {})

    # past_days=1 pomeni 2 vnosa v daily: [0]=včeraj, [1]=danes
    i_today = len(daily.get("time", [])) - 1
    i_yday = i_today - 1

    def d(field, i=i_today):
        arr = daily.get(field) or []
        return arr[i] if 0 <= i < len(arr) else None

    times = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    prob = hourly.get("precipitation_probability", [])
    # samo ure današnjega dne, od DAY_START_HOUR naprej
    idx_today = [i for i, t in enumerate(times)
                 if t.startswith(today.isoformat()) and int(t[11:13]) >= DAY_START_HOUR]

    arso = fetch_arso()
    current = fetch_current()
    aq = fetch_air_quality()
    hist = load_history()
    gobe = load_gobe_index(today.isoformat())

    yday_key = (today - datetime.timedelta(days=1)).isoformat()
    hist_yesterday = hist.get(yday_key)

    return dict(
        now=now, today=today, date_iso=today.isoformat(),
        fc=fc, daily=daily, hourly=hourly,
        tmax=d("temperature_2m_max"), tmin=d("temperature_2m_min"),
        code=d("weather_code"), cond=WMO.get(d("weather_code"), ""),
        sunrise=d("sunrise"), sunset=d("sunset"),
        sunrise_y=d("sunrise", i_yday), sunset_y=d("sunset", i_yday),
        uv_max=d("uv_index_max"), wind_max=d("wind_speed_10m_max"),
        gust_max=d("wind_gusts_10m_max"), apparent_max=d("apparent_temperature_max"),
        times=times, precip=precip, prob=prob, idx_today=idx_today,
        rain_total=sum((precip[i] or 0) for i in idx_today),
        max_prob=max([(prob[i] or 0) for i in idx_today], default=0),
        arso=arso, arso_precip=(arso or {}).get("precip") or 0,
        current=current,
        current_temp=((current.get("outdoor") or {}).get("temperature") or {}).get("value"),
        aq=aq, hist=hist, hist_yesterday=hist_yesterday, gobe=gobe,
    )


# ────────────────────────── registrator tem ──────────────────────────

TOPICS = []


def topic(name, priority):
    def deco(fn):
        TOPICS.append((name, priority, fn))
        return fn
    return deco


def card(ctx, name, headline, big, big_sub, stats, accent, photo, eyebrow="DANES V REČICI"):
    return dict(topic=name, eyebrow=eyebrow, headline=headline, big=big,
                big_sub=big_sub, stats=stats[:3], accent=accent, photo=photo)


# ── FROST ──
@topic("FROST", 95)
def t_frost(ctx):
    if ctx["tmin"] is None or ctx["tmin"] > 0:
        return None
    variants = [
        ("Bo danes\nzmrzovalo?", "pod ničlo ponoči/zjutraj"),
        ("Pozor,\nzmrzal!", "najnižja napovedana temperatura"),
        ("Danes pod\nničlo", "najnižja napovedana temperatura"),
        ("Jutranja\nzmrzal", "termometer pade pod 0 °C"),
        ("Hladna past\nza rastline", "najnižja napovedana temperatura"),
    ]
    headline, big_sub = pick(ctx, "FROST", variants)
    return card(ctx, "FROST", headline, f"{num_sl(ctx['tmin'], 1)} °C", big_sub,
                [("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "jasno"),
                 ("Dežja", f"{num_sl(ctx['rain_total'], 1)} mm")],
                C_CYAN, "night-fog-valley", eyebrow="POZOR DANES")


# ── SNOW ──
@topic("SNOW", 95)
def t_snow(ctx):
    if ctx["code"] not in SNOW_CODES:
        return None
    variants = [
        ("Danes bo\nzapadel sneg", "napovedano sneženje"),
        ("Bel dan\nv dolini?", "napovedano sneženje"),
        ("Pripravi\nlopato", "napovedano sneženje"),
        ("Zima ni\nrekla zadnje", "napovedano sneženje"),
        ("Sneg se\nvrača", "napovedano sneženje"),
    ]
    headline, big_sub = pick(ctx, "SNOW", variants)
    return card(ctx, "SNOW", headline, ctx["cond"].capitalize(), big_sub,
                [("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Najnižja temp.", f"{num_sl(ctx['tmin'], 1)} °C"),
                 ("Padavine", f"{num_sl(ctx['rain_total'], 1)} mm")],
                C_CYAN, "misty-valley", eyebrow="POZOR DANES")


# ── STORM_RISK ──
@topic("STORM_RISK", 92)
def t_storm(ctx):
    if ctx["code"] not in STORM_CODES:
        return None
    start = None
    for i in ctx["idx_today"]:
        if (ctx["precip"][i] or 0) >= 0.2 or (ctx["prob"][i] or 0) >= 50:
            start = int(ctx["times"][i][11:13])
            break
    variants = [
        ("Bo danes\ngrmelo?", "možnost neviht po napovedi"),
        ("Nevihtni dan\nv dolini", "najvišja verjetnost danes"),
        ("Pazi na\nnebo popoldne", "možnost neviht po napovedi"),
        ("Danes lahko\nzagrmi", "možnost neviht po napovedi"),
        ("Nevihtni\nobeti", "možnost neviht po napovedi"),
    ]
    headline, big_sub = pick(ctx, "STORM_RISK", variants)
    photo = "storm-clouds" if variant_index(ctx, "STORM_RISK", 2) == 0 else "nevihta-2019"
    return card(ctx, "STORM_RISK", headline,
                f"ob {start}. uri" if start is not None else "čez dan", big_sub,
                [("Verjetnost", f"{int(ctx['max_prob'])} %"),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Dežja", f"{num_sl(max(ctx['rain_total'], ctx['arso_precip']), 1)} mm")],
                C_PURPLE, photo, eyebrow="POZOR DANES")


# ── HEAT_EXTREME ──
@topic("HEAT_EXTREME", 90)
def t_heat_extreme(ctx):
    if ctx["tmax"] is None or ctx["tmax"] < 33:
        return None
    variants = [
        ("Danes bo\npeklensko vroče", "najvišja napovedana temperatura"),
        ("Vročinski\nvrh danes", "najvišja napovedana temperatura"),
        ("Termometer\nponori", "najvišja napovedana temperatura"),
        ("Ekstremna\nvročina", "najvišja napovedana temperatura"),
        ("Danes se\nkuhamo", "najvišja napovedana temperatura"),
    ]
    headline, big_sub = pick(ctx, "HEAT_EXTREME", variants)
    return card(ctx, "HEAT_EXTREME", headline, f"{num_sl(ctx['tmax'], 1)} °C", big_sub,
                [("Najnižja temp.", f"{num_sl(ctx['tmin'], 1)} °C"),
                 ("UV indeks", f"{num_sl(ctx['uv_max'], 1)}" if ctx["uv_max"] is not None else "–"),
                 ("Dežja", f"{num_sl(ctx['rain_total'], 1)} mm")],
                C_RED, "drought", eyebrow="POZOR DANES")


# ── UV_EXTREME ──
@topic("UV_EXTREME", 88)
def t_uv_extreme(ctx):
    if ctx["uv_max"] is None or ctx["uv_max"] < 9:
        return None
    variants = [
        ("UV je danes\nzelo visok", "vrh UV indeksa"),
        ("Sonce danes\nne odpušča", "vrh UV indeksa"),
        ("Zaščita\nobvezna", "vrh UV indeksa"),
        ("Koža v\nnevarnosti", "vrh UV indeksa"),
        ("Ekstremen\nUV danes", "vrh UV indeksa"),
    ]
    headline, big_sub = pick(ctx, "UV_EXTREME", variants)
    return card(ctx, "UV_EXTREME", headline, num_sl(ctx["uv_max"], 1), big_sub,
                [("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "jasno"),
                 ("Krema+", "obvezna od 11h do 16h")],
                C_AMBER, "spring", eyebrow="POZOR DANES")


# ── WINDY ──
@topic("WINDY", 85)
def t_windy(ctx):
    if ctx["gust_max"] is None or ctx["gust_max"] < 45:
        return None
    variants = [
        ("Danes bo\npihalo", "najmočnejši napovedan sunek"),
        ("Veter se\nkrepi", "najmočnejši napovedan sunek"),
        ("Pridrži\nklobuk", "najmočnejši napovedan sunek"),
        ("Sunkovit\ndan", "najmočnejši napovedan sunek"),
        ("Veter danes\nzagode", "najmočnejši napovedan sunek"),
    ]
    headline, big_sub = pick(ctx, "WINDY", variants)
    return card(ctx, "WINDY", headline, f"{num_sl(ctx['gust_max'])} km/h", big_sub,
                [("Povprečen veter", f"{num_sl(ctx['wind_max'])} km/h"),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "spremenljivo")],
                C_PURPLE, "storm-clouds", eyebrow="POZOR DANES")


# ── AIR_QUALITY_POOR ──
@topic("AIR_QUALITY_POOR", 82)
def t_aq_poor(ctx):
    aqi = ((ctx["aq"] or {}).get("current") or {}).get("european_aqi")
    if aqi is None or aqi < 60:
        return None
    variants = [
        ("Zrak danes\nni najboljši", "evropski indeks kakovosti zraka"),
        ("Danes raje\nokna zaprta", "evropski indeks kakovosti zraka"),
        ("Slab zrak\nv dolini", "evropski indeks kakovosti zraka"),
        ("Pozor,\nonesnaženost", "evropski indeks kakovosti zraka"),
        ("Danes globoko\nne vdihuj zunaj", "evropski indeks kakovosti zraka"),
    ]
    headline, big_sub = pick(ctx, "AIR_QUALITY_POOR", variants)
    cur = ctx["aq"]["current"]
    return card(ctx, "AIR_QUALITY_POOR", headline, f"EAQI {int(aqi)}", big_sub,
                [("PM2,5", f"{num_sl(cur.get('pm2_5'), 1)} µg/m³"),
                 ("PM10", f"{num_sl(cur.get('pm10'), 0)} µg/m³"),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C")],
                C_AMBER, "drought", eyebrow="POZOR DANES")


# ── RAIN_HEAVY ──
@topic("RAIN_HEAVY", 75)
def t_rain_heavy(ctx):
    if ctx["code"] in STORM_CODES:
        return None
    total = max(ctx["rain_total"], ctx["arso_precip"])
    is_rain = ctx["rain_total"] >= 1.0 or ctx["max_prob"] >= 55 or ctx["arso_precip"] >= 5
    if not is_rain or total < 12:
        return None
    variants = [
        ("Danes bo\nzalilo", "napovedana skupna količina"),
        ("Pripravi\ndežnik", "napovedana skupna količina"),
        ("Izdaten dež\nv napovedi", "napovedana skupna količina"),
        ("Danes bo\nmoker dan", "napovedana skupna količina"),
        ("Veliko dežja\ndanes", "napovedana skupna količina"),
    ]
    headline, big_sub = pick(ctx, "RAIN_HEAVY", variants)
    if ctx["arso_precip"]:
        amount_label = "Skupaj · ARSO"
        amount_val = f"{num_sl(ctx['arso_precip'], 1)} mm"
    else:
        amount_label = "Skupaj · Open-Meteo"
        amount_val = f"{num_sl(ctx['rain_total'], 1)} mm"
    return card(ctx, "RAIN_HEAVY", headline, f"{num_sl(total, 1)} mm", big_sub,
                [(amount_label, amount_val),
                 ("Verjetnost · Open-Meteo", f"{int(ctx['max_prob'])} %"),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C")],
                C_BLUE, "rain-overcast")


# ── RAIN_TIMING ──
@topic("RAIN_TIMING", 70)
def t_rain_timing(ctx):
    if ctx["code"] in STORM_CODES:
        return None
    total = max(ctx["rain_total"], ctx["arso_precip"])
    is_rain = ctx["rain_total"] >= 1.0 or ctx["max_prob"] >= 55 or ctx["arso_precip"] >= 5
    if not is_rain or total >= 12:
        return None
    start = None
    for i in ctx["idx_today"]:
        if (ctx["precip"][i] or 0) >= 0.2 or (ctx["prob"][i] or 0) >= 50:
            start = int(ctx["times"][i][11:13])
            break
    if start is None and ctx["idx_today"]:
        start = int(ctx["times"][max(ctx["idx_today"], key=lambda i: ctx["precip"][i] or 0)][11:13])
    variants = [
        ("Kdaj bo danes\nzačelo deževati?", "prvi dež po urni napovedi Open-Meteo"),
        ("Kdaj pride\ndanes dež?", "prvi dež po urni napovedi Open-Meteo"),
        ("Kdaj vzeti\ndežnik?", "prvi dež po urni napovedi Open-Meteo"),
        ("Ura, ko se\nzačne mokro", "prvi dež po urni napovedi Open-Meteo"),
        ("Dež danes\nprihaja", "prvi dež po urni napovedi Open-Meteo"),
    ]
    headline, big_sub = pick(ctx, "RAIN_TIMING", variants)
    if ctx["arso_precip"]:
        amount = ("Dežja · ARSO", f"{num_sl(ctx['arso_precip'], 1)} mm")
    else:
        amount = ("Dežja · Open-Meteo", f"{num_sl(ctx['rain_total'], 1)} mm")
    return card(ctx, "RAIN_TIMING", headline,
                f"ob {start}. uri" if start is not None else "čez dan", big_sub,
                [amount,
                 ("Verjetnost · Open-Meteo", f"{int(ctx['max_prob'])} %"),
                 ("Najvišja temperatura", f"{num_sl(ctx['tmax'], 1)} °C" if ctx["tmax"] is not None else "–")],
                C_BLUE, "rain-overcast")


# ── HEAT ──
@topic("HEAT", 68)
def t_heat(ctx):
    if ctx["tmax"] is None or not (28 <= ctx["tmax"] < 33):
        return None
    variants = [
        ("Kako vroče\nbo danes?", "najvišja napovedana temperatura"),
        ("Danes bo\ngorko", "najvišja napovedana temperatura"),
        ("Poletje\nkaže mišice", "najvišja napovedana temperatura"),
        ("Vroč dan\npred nami", "najvišja napovedana temperatura"),
        ("Danes se\nsegreje", "najvišja napovedana temperatura"),
    ]
    headline, big_sub = pick(ctx, "HEAT", variants)
    return card(ctx, "HEAT", headline, f"{num_sl(ctx['tmax'], 1)} °C", big_sub,
                [("Najnižja temp.", f"{num_sl(ctx['tmin'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "jasno"),
                 ("Dežja", f"{num_sl(ctx['rain_total'], 1)} mm")],
                C_ORANGE, "drought")


# ── COLD_MORNING ──
@topic("COLD_MORNING", 65)
def t_cold_morning(ctx):
    if ctx["tmin"] is None or not (0 < ctx["tmin"] <= 5):
        return None
    variants = [
        ("Hladno jutro\ndanes", "najnižja napovedana temperatura"),
        ("Danes zjutraj\nmrzlo", "najnižja napovedana temperatura"),
        ("Obleci se\ntopleje", "najnižja napovedana temperatura"),
        ("Prvi mraz\nv zraku", "najnižja napovedana temperatura"),
        ("Hladen\nstart dneva", "najnižja napovedana temperatura"),
    ]
    headline, big_sub = pick(ctx, "COLD_MORNING", variants)
    return card(ctx, "COLD_MORNING", headline, f"{num_sl(ctx['tmin'], 1)} °C", big_sub,
                [("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "jasno"),
                 ("Dežja", f"{num_sl(ctx['rain_total'], 1)} mm")],
                C_CYAN, "misty-valley")


# ── FOG_MORNING ──
@topic("FOG_MORNING", 63)
def t_fog(ctx):
    if ctx["code"] not in FOG_CODES:
        return None
    variants = [
        ("Megla nad\ndolino danes", "vremenska napoved za danes"),
        ("Danes je\ndolina pod odejo", "vremenska napoved za danes"),
        ("Vidljivost\nzjutraj nizka", "vremenska napoved za danes"),
        ("Megleno\njutro", "vremenska napoved za danes"),
        ("Dolina v\nmegli", "vremenska napoved za danes"),
    ]
    headline, big_sub = pick(ctx, "FOG_MORNING", variants)
    return card(ctx, "FOG_MORNING", headline, ctx["cond"].capitalize(), big_sub,
                [("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Najnižja temp.", f"{num_sl(ctx['tmin'], 1)} °C"),
                 ("Veter", f"{num_sl(ctx['wind_max'])} km/h")],
                C_CYAN, "megla-recica-lastna")


# ── UV_HIGH ──
@topic("UV_HIGH", 60)
def t_uv_high(ctx):
    if ctx["uv_max"] is None or not (7 <= ctx["uv_max"] < 9):
        return None
    variants = [
        ("Visok UV\ndanes", "vrh UV indeksa"),
        ("Sonce danes\npeče močno", "vrh UV indeksa"),
        ("Ne pozabi\nkreme", "vrh UV indeksa"),
        ("UV indeks\nv rdečem", "vrh UV indeksa"),
        ("Danes previdno\nna soncu", "vrh UV indeksa"),
    ]
    headline, big_sub = pick(ctx, "UV_HIGH", variants)
    return card(ctx, "UV_HIGH", headline, num_sl(ctx["uv_max"], 1), big_sub,
                [("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "jasno"),
                 ("Dežja", f"{num_sl(ctx['rain_total'], 1)} mm")],
                C_AMBER, "spring")


# ── HUMID_MUGGY ──
@topic("HUMID_MUGGY", 58)
def t_muggy(ctx):
    if ctx["tmax"] is None or ctx["apparent_max"] is None or ctx["tmax"] < 22:
        return None
    if ctx["apparent_max"] - ctx["tmax"] < 3.0:
        return None
    variants = [
        ("Danes bo\nsoparno", "občutena temperatura"),
        ("Vlaga danes\nteži", "občutena temperatura"),
        ("Zrak se\nlepi", "občutena temperatura"),
        ("Sparen\ndan", "občutena temperatura"),
        ("Danes se\nobčuti huje", "občutena temperatura"),
    ]
    headline, big_sub = pick(ctx, "HUMID_MUGGY", variants)
    return card(ctx, "HUMID_MUGGY", headline, f"{num_sl(ctx['apparent_max'], 1)} °C", big_sub,
                [("Dejanska temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Razlika", f"+{num_sl(ctx['apparent_max'] - ctx['tmax'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "soparno")],
                C_ORANGE, "rain-overcast")


# ── POLLEN_HIGH ──
@topic("POLLEN_HIGH", 55)
def t_pollen(ctx):
    hourly = (ctx["aq"] or {}).get("hourly")
    if not hourly:
        return None
    best_key, best_ratio, best_val = None, 0, 0
    for key, label in POLLEN_SPECIES:
        vals = hourly.get(key) or []
        if not vals:
            continue
        v = max(vals)
        th = POLLEN_TH[key]
        ratio = v / th[1] if th[1] else 0  # razmerje proti "zmerni" meji
        if ratio > best_ratio:
            best_key, best_ratio, best_val = key, ratio, v
    if best_key is None or best_ratio < 1.0:
        return None
    label = dict(POLLEN_SPECIES)[best_key]
    variants = [
        ("Danes veliko\ncvetnega prahu", "prevladujoča rastlina danes"),
        ("Alergiki,\npozor danes", "prevladujoča rastlina danes"),
        ("Cvetni prah\nv zraku", "prevladujoča rastlina danes"),
        ("Danes se bo\nkihalo", "prevladujoča rastlina danes"),
        ("Visok pelod\ndanes", "prevladujoča rastlina danes"),
    ]
    headline, big_sub = pick(ctx, "POLLEN_HIGH", variants)
    return card(ctx, "POLLEN_HIGH", headline, label.capitalize(), big_sub,
                [("Vrednost", f"{num_sl(best_val, 1)} zrn/m³"),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Vreme", ctx["cond"] or "jasno")],
                C_AMBER, "spring")


# ── RECORD_WATCH ──
@topic("RECORD_WATCH", 48)
def t_record(ctx):
    if ctx["tmax"] is None or not ctx["hist"]:
        return None
    record = calendar_day_record(ctx["hist"], ctx["today"].month, ctx["today"].day, ctx["today"].year)
    if record is None or ctx["tmax"] < record - 1.0:
        return None
    variants = [
        ("Danes lahko\npade rekord", "rekord za ta koledarski dan"),
        ("Zgodovinsko\nvroč dan?", "rekord za ta koledarski dan"),
        ("Danes blizu\nrekorda", "rekord za ta koledarski dan"),
        ("Morda nov\nrekord danes", "rekord za ta koledarski dan"),
        ("Rekord na\nvidiku", "rekord za ta koledarski dan"),
    ]
    headline, big_sub = pick(ctx, "RECORD_WATCH", variants)
    return card(ctx, "RECORD_WATCH", headline, f"{num_sl(ctx['tmax'], 1)} °C", big_sub,
                [("Dosedanji rekord", f"{num_sl(record, 1)} °C"),
                 ("Postaja", "IREICA1"),
                 ("Vreme", ctx["cond"] or "jasno")],
                C_RED, "weather-station")


# ── TROPICAL_NIGHT ──
@topic("TROPICAL_NIGHT", 46)
def t_tropical_night(ctx):
    hy = ctx["hist_yesterday"]
    if not hy or (hy.get("tempLow") or 0) < 20:
        return None
    variants = [
        ("Ponoči ni\nshladilo", "najnižja temperatura sinoči"),
        ("Tropska noč\nza nami", "najnižja temperatura sinoči"),
        ("Termometer\nni padel", "najnižja temperatura sinoči"),
        ("Vroča noč\nna postaji", "najnižja temperatura sinoči"),
        ("Brez hladu\nponoči", "najnižja temperatura sinoči"),
    ]
    headline, big_sub = pick(ctx, "TROPICAL_NIGHT", variants)
    return card(ctx, "TROPICAL_NIGHT", headline, f"{num_sl(hy['tempLow'], 1)} °C", big_sub,
                [("Najvišja temp. danes", f"{num_sl(ctx['tmax'], 1)} °C" if ctx["tmax"] is not None else "–"),
                 ("Postaja", "IREICA1"),
                 ("Vreme", ctx["cond"] or "jasno")],
                C_ORANGE, "night-fog-valley")


# ── DROUGHT_DRY_STREAK ──
@topic("DROUGHT_DRY_STREAK", 44)
def t_drought(ctx):
    if not ctx["hist"]:
        return None
    streak = dry_streak(ctx["hist"], ctx["today"] - datetime.timedelta(days=1))
    if streak < 10:
        return None
    variants = [
        ("Že dolgo\nbrez dežja", "zaporednih suhih dni do včeraj"),
        ("Suša se\nvleče", "zaporednih suhih dni do včeraj"),
        ("Tla so\nžejna", "zaporednih suhih dni do včeraj"),
        ("Dolg suh\nniz", "zaporednih suhih dni do včeraj"),
        ("Dežja že\ndolgo ni", "zaporednih suhih dni do včeraj"),
    ]
    headline, big_sub = pick(ctx, "DROUGHT_DRY_STREAK", variants)
    return card(ctx, "DROUGHT_DRY_STREAK", headline, f"{streak} dni", big_sub,
                [("Danes dežja", f"{num_sl(ctx['rain_total'], 1)} mm"),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C" if ctx["tmax"] is not None else "–"),
                 ("Postaja", "IREICA1")],
                C_AMBER, "drought")


# ── MUSHROOM ──
@topic("MUSHROOM", 42)
def t_mushroom(ctx):
    g = ctx["gobe"]
    if not g or (g.get("index") or 0) < 55:
        return None
    variants = [
        ("Danes dobri\npogoji za gobe", "gobarski indeks za Rečico"),
        ("Čas za v\ngozd po gobe", "gobarski indeks za Rečico"),
        ("Gobe danes\nrastejo", "gobarski indeks za Rečico"),
        ("Gobarski dan\nv dolini", "gobarski indeks za Rečico"),
        ("Pojdi po\ngobe danes", "gobarski indeks za Rečico"),
    ]
    headline, big_sub = pick(ctx, "MUSHROOM", variants)
    photo = "gobe-lastna" if variant_index(ctx, "MUSHROOM", 2) == 0 else "gobe-inverzija"
    return card(ctx, "MUSHROOM", headline, str(g.get("index")), big_sub,
                [("Ocena", g.get("level", "–")),
                 ("Najbolj obetavna", g.get("top_species_sl", "–")),
                 ("Vreme danes", ctx["cond"] or "spremenljivo")],
                C_GREEN, photo)


# ── AIR_QUALITY_GOOD ──
@topic("AIR_QUALITY_GOOD", 40)
def t_aq_good(ctx):
    aqi = ((ctx["aq"] or {}).get("current") or {}).get("european_aqi")
    if aqi is None or aqi > 25:
        return None
    variants = [
        ("Zrak danes\nodličen", "evropski indeks kakovosti zraka"),
        ("Globoko\nvdihni", "evropski indeks kakovosti zraka"),
        ("Čist zrak\nv dolini", "evropski indeks kakovosti zraka"),
        ("Danes diha\nse lepo", "evropski indeks kakovosti zraka"),
        ("Zrak v\nnajboljšem redu", "evropski indeks kakovosti zraka"),
    ]
    headline, big_sub = pick(ctx, "AIR_QUALITY_GOOD", variants)
    cur = ctx["aq"]["current"]
    return card(ctx, "AIR_QUALITY_GOOD", headline, f"EAQI {int(aqi)}", big_sub,
                [("PM2,5", f"{num_sl(cur.get('pm2_5'), 1)} µg/m³"),
                 ("PM10", f"{num_sl(cur.get('pm10'), 0)} µg/m³"),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C" if ctx["tmax"] is not None else "–")],
                C_GREEN, "spring")


# ── VS_YESTERDAY ──
@topic("VS_YESTERDAY", 38)
def t_vs_yesterday(ctx):
    hy = ctx["hist_yesterday"]
    if not hy or ctx["tmax"] is None or hy.get("tempHigh") is None:
        return None
    diff = ctx["tmax"] - hy["tempHigh"]
    if abs(diff) < 4.0:
        return None
    if diff > 0:
        variants = [
            ("Danes bo\ntopleje kot včeraj", "razlika od včerajšnjega vrha"),
            ("Segreva\nse", "razlika od včerajšnjega vrha"),
            ("Toplejši dan\nod včeraj", "razlika od včerajšnjega vrha"),
            ("Termometer\ngre gor", "razlika od včerajšnjega vrha"),
            ("Danes več\nkot včeraj", "razlika od včerajšnjega vrha"),
        ]
    else:
        variants = [
            ("Danes bo\nhladneje kot včeraj", "razlika od včerajšnjega vrha"),
            ("Ohladitev\nje tu", "razlika od včerajšnjega vrha"),
            ("Hladnejši dan\nod včeraj", "razlika od včerajšnjega vrha"),
            ("Termometer\ngre dol", "razlika od včerajšnjega vrha"),
            ("Danes manj\nkot včeraj", "razlika od včerajšnjega vrha"),
        ]
    headline, big_sub = pick(ctx, "VS_YESTERDAY", variants)
    sign = "+" if diff > 0 else "−"
    return card(ctx, "VS_YESTERDAY", headline, f"{sign}{num_sl(abs(diff), 1)} °C", big_sub,
                [("Danes", f"{num_sl(ctx['tmax'], 1)} °C"),
                 ("Včeraj", f"{num_sl(hy['tempHigh'], 1)} °C"),
                 ("Vreme danes", ctx["cond"] or "spremenljivo")],
                C_ORANGE if diff > 0 else C_CYAN, "weather-station")


# ── PRESSURE_TREND ──
@topic("PRESSURE_TREND", 36)
def t_pressure(ctx):
    hy = ctx["hist_yesterday"]
    pres = ((ctx["current"].get("pressure") or {}).get("relative") or {}).get("value")
    if not hy or pres is None or hy.get("pressureAvg") is None:
        return None
    try:
        pres = float(pres)
    except (TypeError, ValueError):
        return None
    diff = pres - hy["pressureAvg"]
    if abs(diff) < 4.0:
        return None
    if diff < 0:
        variants = [
            ("Tlak danes\nhitro pada", "sprememba od včerajšnjega povprečja"),
            ("Sprememba\nvremena prihaja", "sprememba od včerajšnjega povprečja"),
            ("Barometer\npada", "sprememba od včerajšnjega povprečja"),
            ("Zrak se\npremika", "sprememba od včerajšnjega povprečja"),
            ("Tlak v\nupadu", "sprememba od včerajšnjega povprečja"),
        ]
    else:
        variants = [
            ("Tlak danes\nhitro raste", "sprememba od včerajšnjega povprečja"),
            ("Vreme se\numirja", "sprememba od včerajšnjega povprečja"),
            ("Barometer\nraste", "sprememba od včerajšnjega povprečja"),
            ("Stabilnejše\nvreme prihaja", "sprememba od včerajšnjega povprečja"),
            ("Tlak v\nporastu", "sprememba od včerajšnjega povprečja"),
        ]
    headline, big_sub = pick(ctx, "PRESSURE_TREND", variants)
    sign = "+" if diff > 0 else "−"
    return card(ctx, "PRESSURE_TREND", headline, f"{sign}{num_sl(abs(diff), 1)} hPa", big_sub,
                [("Zdaj", f"{num_sl(pres, 1)} hPa"),
                 ("Včeraj povp.", f"{num_sl(hy['pressureAvg'], 1)} hPa"),
                 ("Vreme danes", ctx["cond"] or "spremenljivo")],
                C_PURPLE, "dusk-storm")


# ── SUNRISE_SUNSET ──
@topic("SUNRISE_SUNSET", 34)
def t_daylength(ctx):
    if not (ctx["sunrise"] and ctx["sunset"] and ctx["sunrise_y"] and ctx["sunset_y"]):
        return None

    def to_dt(s):
        return datetime.datetime.fromisoformat(s)

    length_today = (to_dt(ctx["sunset"]) - to_dt(ctx["sunrise"])).total_seconds() / 60
    length_yday = (to_dt(ctx["sunset_y"]) - to_dt(ctx["sunrise_y"])).total_seconds() / 60
    delta = length_today - length_yday
    growing = delta >= 0
    variants = [
        ("Dan se danes\ndaljša" if growing else "Dan se danes\nkrajša", "razlika glede na včeraj"),
        ("Svetlobe je\nvse več" if growing else "Svetlobe je\nvse manj", "razlika glede na včeraj"),
        ("Sonce vstaja\nprej" if growing else "Sonce vstaja\npozneje", "razlika glede na včeraj"),
        ("Dnevi se\npodaljšujejo" if growing else "Dnevi se\nkrajšajo", "razlika glede na včeraj"),
        ("Malo več\nsvetlobe danes" if growing else "Malo manj\nsvetlobe danes", "razlika glede na včeraj"),
    ]
    headline, big_sub = pick(ctx, "SUNRISE_SUNSET", variants)
    sign = "+" if delta >= 0 else "−"
    h, m = divmod(int(abs(delta)), 60)
    delta_str = f"{sign}{m} min" if h == 0 else f"{sign}{h} h {m} min"
    return card(ctx, "SUNRISE_SUNSET", headline, delta_str, big_sub,
                [("Sončni vzhod", to_dt(ctx["sunrise"]).strftime("%H:%M")),
                 ("Sončni zahod", to_dt(ctx["sunset"]).strftime("%H:%M")),
                 ("Najvišja temp.", f"{num_sl(ctx['tmax'], 1)} °C" if ctx["tmax"] is not None else "–")],
                C_AMBER, "spring")


# ── GENERAL (fallback, vedno na voljo) ──
@topic("GENERAL", 10)
def t_general(ctx):
    variants = [
        ("Kakšno bo\ndanes vreme?", "najvišja napovedana temperatura"),
        ("Vreme za\ndanes", "najvišja napovedana temperatura"),
        ("Kaj prinaša\ndanešnji dan?", "najvišja napovedana temperatura"),
        ("Napoved za\ndanes", "najvišja napovedana temperatura"),
        ("Danes v\nRečici", "najvišja napovedana temperatura"),
        ("Kakšen dan\nnas čaka?", "najvišja napovedana temperatura"),
        ("Vremenski\npregled", "najvišja napovedana temperatura"),
        ("Danes pri\nnas", "najvišja napovedana temperatura"),
    ]
    headline, big_sub = pick(ctx, "GENERAL", variants)
    photo = "misty-valley" if variant_index(ctx, "GENERAL", 2) == 0 else "weather-station"
    return card(ctx, "GENERAL", headline,
                f"{num_sl(ctx['tmax'], 1)} °C" if ctx["tmax"] is not None else "–", big_sub,
                [("Najnižja temp.", f"{num_sl(ctx['tmin'], 1)} °C" if ctx["tmin"] is not None else "–"),
                 ("Vreme", ctx["cond"] or "spremenljivo"),
                 ("Dežja", f"{num_sl(ctx['rain_total'], 1)} mm")],
                C_CYAN, photo)


def pick_topic(ctx):
    eligible = []
    for name, priority, fn in TOPICS:
        try:
            result = fn(ctx)
        except Exception as e:
            print(f"⚠ tema {name} je odpovedala: {e}", file=sys.stderr)
            continue
        if result is not None:
            eligible.append((priority, name, result))
    eligible.sort(key=lambda x: -x[0])
    _, name, result = eligible[0]
    variant = variant_index(ctx, name, 5)
    return result, variant, [n for _, n, _ in eligible]


# ────────────────────────── izris ──────────────────────────

def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def fit_crop(im, w, h):
    ratio = im.width / im.height
    target = w / h
    if ratio > target:
        new_h, new_w = h, int(ratio * h)
    else:
        new_w, new_h = w, int(w / ratio)
    im = im.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - w) // 2
    y = (new_h - h) // 3
    return im.crop((x, y, x + w, y + h))


def fit_value_text(draw, text, avail_w):
    """Vrne (besedilo, pisava, širina), ki se prilega `avail_w` -- najprej
    poskusi veliko krepko pisavo (40 pt), nato manjšo (30 pt), nazadnje
    besedilo tudi obreže z » …«. Uporabljeno za desni stolpec v panelu s
    statistiko, kjer vrednost (npr. ime gobje vrste) sicer lahko pade čez
    oznako na levi (glej git zgodovino -- MUSHROOM z dolgim imenom vrste)."""
    for size in (40, 30):
        f = font("LiberationSans-Bold.ttf", size)
        bb = draw.textbbox((0, 0), text, font=f)
        w = bb[2] - bb[0]
        if w <= avail_w:
            return text, f, w
    f = font("LiberationSans-Bold.ttf", 30)
    trimmed = text
    while len(trimmed) > 1:
        trimmed = trimmed[:-1]
        candidate = trimmed.rstrip() + "…"
        bb = draw.textbbox((0, 0), candidate, font=f)
        w = bb[2] - bb[0]
        if w <= avail_w:
            return candidate, f, w
    return "…", f, draw.textbbox((0, 0), "…", font=f)[2]


def render(topic_card, now, current_temp):
    accent = topic_card["accent"]

    bg = Image.open(os.path.join(BG_DIR, topic_card["photo"] + ".jpg")).convert("RGB")
    bg = fit_crop(bg, W, H)
    bg = ImageEnhance.Contrast(bg).enhance(1.1)
    bg = ImageEnhance.Color(bg).enhance(1.1)
    img = bg.convert("RGBA")

    # Gradient: zgoraj rahlo, spodaj skoraj neprozorno -- da je besedilo berljivo
    # tudi na svetli fotografiji.
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for row in range(H):
        t = row / H
        if t < 0.22:
            a = 90 + (t / 0.22) * 30
        elif t < 0.45:
            a = 120 + (t - 0.22) / 0.23 * 70
        else:
            a = 190 + (t - 0.45) / 0.55 * 55
        gd.line([(0, row), (W, row)], fill=(3, 6, 14, int(min(a, 246))))
    img = Image.alpha_composite(img, grad)
    d = ImageDraw.Draw(img)

    f_brand = font("LiberationSans-Bold.ttf", 44)
    f_date = font("LiberationSans-Regular.ttf", 30)
    f_eyebrow = font("LiberationSans-Bold.ttf", 28)
    f_head = font("LiberationSans-Bold.ttf", 84)
    f_big = font("LiberationSans-Bold.ttf", 140)
    f_bigsub = font("LiberationSans-Regular.ttf", 34)
    f_stat_l = font("LiberationSans-Regular.ttf", 27)
    f_cta = font("LiberationSans-Bold.ttf", 34)
    f_foot = font("LiberationSans-Regular.ttf", 26)

    pad = 80
    # Instagram čez zgodbo riše svoj vmesnik: zgoraj profil in napredek,
    # spodaj polje "pošlji sporočilo". Vsebina mora ostati med tema pasovoma,
    # sicer jo aplikacija prekrije.
    safe_top, safe_bot = 200, 1700

    d.rectangle([0, 0, 10, H], fill=accent)

    # ── glava: logo + znamka + datum ──
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA")
    ls = 96
    logo = logo.resize((ls, ls), Image.LANCZOS)
    img.paste(logo, (pad, safe_top), logo)
    d = ImageDraw.Draw(img)
    d.text((pad + ls + 24, safe_top + 4), "METEOREC", font=f_brand, fill=WHITE)
    datum = f"{DNI[now.weekday()]}, {now.day}. {MES_NOM[now.month]}"
    d.text((pad + ls + 26, safe_top + 56), datum, font=f_date, fill=MUTED)

    # ── eyebrow ──
    y = safe_top + ls + 60
    eb = topic_card["eyebrow"]
    tb = d.textbbox((0, 0), eb, font=f_eyebrow)
    d.rounded_rectangle([pad, y, pad + (tb[2] - tb[0]) + 40, y + 52], radius=26, fill=accent)
    d.text((pad + 20, y + 12), eb, font=f_eyebrow, fill=(6, 10, 18))

    # ── glavno vprašanje ──
    y += 110
    for line in topic_card["headline"].split("\n"):
        d.text((pad, y), line, font=f_head, fill=WHITE)
        y += 98

    # ── velika številka ──
    y += 40
    d.text((pad, y), topic_card["big"], font=f_big, fill=accent)
    y += 168
    d.text((pad, y), topic_card["big_sub"], font=f_bigsub, fill=MUTED)

    # ── panel s tremi podatki, zasidran na dno varnega območja ──
    rows = topic_card["stats"]
    row_h = 104
    panel_h = row_h * len(rows) + 48
    foot_h = 108
    panel_top = safe_bot - foot_h - panel_h

    # Prosojne ploskve morajo iti prek alpha_composite na svoji plasti -- če
    # jih rišemo naravnost na RGBA sliko, PIL obstoječe piksle prepiše namesto
    # zmeša in ob pretvorbi v RGB panel postane povsem bel.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([pad, panel_top, W - pad, panel_top + panel_h],
                         radius=24, fill=(255, 255, 255, 20),
                         outline=(255, 255, 255, 48), width=2)
    ry = panel_top + 24
    for i in range(1, len(rows)):
        dy = ry + row_h * i
        od.line([(pad + 28, dy), (W - pad - 28, dy)], fill=(255, 255, 255, 34), width=1)
    img = Image.alpha_composite(img, overlay)
    d = ImageDraw.Draw(img)

    for label, val in rows:
        d.text((pad + 32, ry + 34), label, font=f_stat_l, fill=DIM)
        lb = d.textbbox((0, 0), label, font=f_stat_l)
        # Vrednost sme segati samo do konca vrstice minus prostor, ki ga že
        # zaseda oznaka (+ presledek) -- prej se je merilo proti celotni
        # širini vrstice, zato je dolga vrednost (npr. ime gobje vrste) padla
        # čez oznako namesto da bi se skrajšala.
        avail_w = (W - pad - 32) - (pad + 32 + (lb[2] - lb[0]) + 24)
        text, vf, vw = fit_value_text(d, val, avail_w)
        # Navpično centriranje glede na dejanski bbox izbrane pisave -- ne
        # more biti fiksen zamik, ker fit_value_text lahko vrne 40pt ali 30pt
        # pisavo in bi bil sicer krajši niz videti poravnan drugače od daljšega.
        vb2 = d.textbbox((0, 0), text, font=vf)
        y_off = row_h // 2 - (vb2[3] - vb2[1]) // 2 - vb2[1]
        d.text((W - pad - 32 - vw, ry + y_off), text, font=vf, fill=WHITE)
        ry += row_h

    # ── noga: trenutno stanje na postaji + CTA ──
    foot_y = panel_top + panel_h + 22
    if current_temp is not None:
        d.text((pad, foot_y), f"Zdaj na postaji IREICA1: {str(current_temp).replace('.', ',')} °C",
               font=f_foot, fill=DIM)
    d.text((pad, foot_y + 44), "Vse meritve v živo na meteorec.si", font=f_cta, fill=accent)

    return img.convert("RGB")


def prune_old(today):
    """Pobriše kartice, starejše od KEEP_DAYS -- repozitorij naj ne raste v nedogled."""
    if not os.path.isdir(OUT_DIR):
        return []
    cutoff = today - datetime.timedelta(days=KEEP_DAYS)
    removed = []
    for name in os.listdir(OUT_DIR):
        if not name.endswith(".jpg"):
            continue
        try:
            d = datetime.date.fromisoformat(name[:-4])
        except ValueError:
            continue
        if d < cutoff:
            os.remove(os.path.join(OUT_DIR, name))
            removed.append(name)
    return removed


def count_variants_by_ast():
    """Prešteje `variants = [...]` sezname v izvorni kodi te datoteke -- za
    --list-topics in za teste (preverjajo, da jih je >=100).

    Statična analiza namesto klica vsake funkcije, ker so mnoge teme
    pogojno upravičene (npr. FROST rabi tmin<=0) in bi jih bilo brez
    pravih podatkov za vsak pogoj težko vse poklicati."""
    import ast
    tree = ast.parse(open(__file__, encoding="utf-8").read())
    counts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("t_"):
            # Nekatere teme (VS_YESTERDAY, PRESSURE_TREND) imajo dva ločena
            # `variants = [...]` (topleje/hladneje, raste/pada) v if/else vejah
            # -- oba dejansko pridejo na vrsto ob različnih dnevih, zato ju
            # SEŠTEJEMO namesto da bi drugi tiho prepisal prvega.
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Assign) and isinstance(sub.value, ast.List)
                        and len(sub.targets) == 1
                        and getattr(sub.targets[0], "id", None) == "variants"):
                    counts[node.name] = counts.get(node.name, 0) + len(sub.value.elts)
    return counts


def main():
    dry = "--dry-run" in sys.argv
    list_topics = "--list-topics" in sys.argv

    if list_topics:
        counts = count_variants_by_ast()
        total = 0
        for name, priority, fn in sorted(TOPICS, key=lambda x: -x[1]):
            n = counts.get(fn.__name__, 0)
            total += n
            print(f"{priority:>3}  {name:<20} {n:>2} različic")
        print(f"\nSkupno tem: {len(TOPICS)}   skupno besedilnih različic: {total}")
        return 0

    ctx = build_ctx()
    result, variant, eligible = pick_topic(ctx)

    print(f"predlog: {result['topic']}#{variant} — {result['headline'].replace(chr(10), ' ')} "
          f"[{result['big']}]")
    print(f"   (upravičene teme danes: {', '.join(eligible)})")
    for label, val in result["stats"]:
        print(f"   {label}: {val}")
    if dry:
        print("(--dry-run: nič ni zapisano)")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    img = render(result, ctx["now"], ctx["current_temp"])

    name = f"{ctx['today'].isoformat()}.jpg"
    out = os.path.join(OUT_DIR, name)
    img.save(out, "JPEG", quality=90)
    print(f"✓ zapisano: og/story/{name}")

    removed = prune_old(ctx["today"])
    if removed:
        print(f"✓ pobrisane stare kartice: {', '.join(sorted(removed))}")

    meta = {
        "date": ctx["date_iso"],
        "topic": result["topic"],
        "variant": variant,
        "image": f"{SITE}/og/story/{name}",
        "generated_at": ctx["now"].isoformat(),
    }
    with open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ zapisano: og/story/latest.json ({meta['image']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
