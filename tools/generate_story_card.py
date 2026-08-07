#!/usr/bin/env python3
"""
tools/generate_story_card.py — dnevna kartica za Instagram/Facebook zgodbo.

Zjutraj pogleda napoved za Rečico ob Savinji in glede na to, kaj dan prinaša,
izbere enega od treh predlogov:

  DEZ      — napovedan je dež: "Kdaj bo danes začelo deževati?" + ura začetka
  VROCINA  — jasno in vroče:   "Kako vroče bo danes?"          + najvišja temperatura
  SPLOSNO  — vse ostalo:       "Kakšno bo danes vreme?"        + najvišja temperatura

Zapiše og/story/<YYYY-MM-DD>.jpg v formatu zgodbe (1080x1920) in
og/story/latest.json z metapodatki (predlog, URL slike) za objavljalna skripta.

Objavita jo tools/post_story_to_facebook.py in post_story_to_instagram.py
prek workflowa .github/workflows/daily-story.yml.

POZOR — notranje meritve: fetch_current() spodaj IZBRIŠE blok `indoor` iz
odgovora postaje (glej CLAUDE.md). Na kartico gre samo zunanja temperatura.

Usage:
  python3 tools/generate_story_card.py            # zapiše kartico za danes
  python3 tools/generate_story_card.py --dry-run  # samo izpiše izbrani predlog
"""
import datetime
import json
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "og", "story")
BG_DIR = os.path.join(ROOT, "og", "bg")
SITE = "https://meteorec.si"
WORKER = "https://weatherireica1.filip-eremita.workers.dev"

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

# WMO kode -> kratek slovenski opis (samo tiste, ki jih pri nas res srečamo)
WMO = {
    0: "jasno", 1: "pretežno jasno", 2: "delno oblačno", 3: "oblačno",
    45: "megla", 48: "megla z ivjem",
    51: "rosenje", 53: "rosenje", 55: "močno rosenje",
    61: "rahel dež", 63: "dež", 65: "močan dež",
    71: "rahlo sneženje", 73: "sneženje", 75: "močno sneženje",
    80: "plohe", 81: "plohe", 82: "močne plohe",
    95: "nevihta", 96: "nevihta s točo", 99: "nevihta s točo",
}


def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "meteorec-story/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_forecast():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&hourly=precipitation,precipitation_probability,temperature_2m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
        "&timezone=Europe%2FLjubljana&forecast_days=1"
    )
    return fetch_json(url)


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


def num_sl(x, d=0):
    return f"{x:.{d}f}".replace(".", ",")


def pick_topic(fc, arso):
    """Iz napovedi izbere predlog kartice + vrednosti, ki gredo nanjo."""
    hourly = fc.get("hourly", {})
    times = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    prob = hourly.get("precipitation_probability", [])
    daily = fc.get("daily", {})

    tmax = (daily.get("temperature_2m_max") or [None])[0]
    tmin = (daily.get("temperature_2m_min") or [None])[0]
    code = (daily.get("weather_code") or [None])[0]
    cond = WMO.get(code, "")

    # Samo preostanek dneva -- zjutraj ob 6h nikogar ne zanima nočni dež.
    idx = [i for i, t in enumerate(times)
           if int(t[11:13]) >= DAY_START_HOUR]
    rain_total = sum((precip[i] or 0) for i in idx)
    max_prob = max([(prob[i] or 0) for i in idx], default=0)

    # ARSO ima pogosto bolj pogumno (in za dolino bolj realno) padavinsko
    # številko kot globalni modeli -- če napoveduje dež, mu pustimo glas.
    arso_precip = (arso or {}).get("precip") or 0

    is_rain = rain_total >= 1.0 or max_prob >= 55 or arso_precip >= 5

    if is_rain:
        start = None
        for i in idx:
            if (precip[i] or 0) >= 0.2 or (prob[i] or 0) >= 50:
                start = int(times[i][11:13])
                break
        if start is None and idx:
            start = int(times[max(idx, key=lambda i: precip[i] or 0)][11:13])
        # Vsak podatek nosi svoj vir: ARSO in Open-Meteo se pri padavinah
        # pogosto močno razideta, zato ju NE mešamo v eno številko -- sicer
        # bi na kartici stalo npr. "31,8 mm" poleg "23 %", kar je videti
        # kot ena napoved, v resnici pa sta to dva različna modela.
        if arso_precip:
            amount = ("Dežja danes · ARSO", f"{num_sl(arso_precip, 1)} mm")
        else:
            amount = ("Dežja danes · Open-Meteo", f"{num_sl(rain_total, 1)} mm")
        return {
            "topic": "DEZ",
            "eyebrow": "DANES V REČICI",
            "headline": "Kdaj bo danes\nzačelo deževati?",
            "big": f"ob {start}. uri" if start is not None else "čez dan",
            "big_sub": "prvi dež po urni napovedi Open-Meteo",
            "accent": (96, 165, 250),
            "photo": "rain-overcast",
            "stats": [
                amount,
                ("Verjetnost · Open-Meteo", f"{int(max_prob)} %"),
                ("Najvišja temperatura", f"{num_sl(tmax)} °C" if tmax is not None else "–"),
            ],
        }

    if tmax is not None and tmax >= 28:
        return {
            "topic": "VROCINA",
            "eyebrow": "DANES V REČICI",
            "headline": "Kako vroče\nbo danes?",
            "big": f"{num_sl(tmax)} °C",
            "big_sub": "najvišja napovedana temperatura",
            "accent": (249, 115, 22),
            "photo": "drought",
            "stats": [
                ("Najnižja temp.", f"{num_sl(tmin)} °C" if tmin is not None else "–"),
                ("Vreme", cond or "jasno"),
                ("Dežja", f"{num_sl(rain_total, 1)} mm"),
            ],
        }

    return {
        "topic": "SPLOSNO",
        "eyebrow": "DANES V REČICI",
        "headline": "Kakšno bo\ndanes vreme?",
        "big": f"{num_sl(tmax)} °C" if tmax is not None else "–",
        "big_sub": "najvišja napovedana temperatura",
        "accent": (34, 211, 238),
        "photo": "misty-valley",
        "stats": [
            ("Najnižja temp.", f"{num_sl(tmin)} °C" if tmin is not None else "–"),
            ("Vreme", cond or "spremenljivo"),
            ("Dežja", f"{num_sl(rain_total, 1)} mm"),
        ],
    }


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


def render(topic, now, current):
    accent = topic["accent"]

    bg = Image.open(os.path.join(BG_DIR, topic["photo"] + ".jpg")).convert("RGB")
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
    f_head = font("LiberationSans-Bold.ttf", 92)
    f_big = font("LiberationSans-Bold.ttf", 150)
    f_bigsub = font("LiberationSans-Regular.ttf", 34)
    f_stat_l = font("LiberationSans-Regular.ttf", 27)
    f_stat_v = font("LiberationSans-Bold.ttf", 44)
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
    dni = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
    mes = ["januar", "februar", "marec", "april", "maj", "junij", "julij",
           "avgust", "september", "oktober", "november", "december"]
    datum = f"{dni[now.weekday()]}, {now.day}. {mes[now.month - 1]}"
    d.text((pad + ls + 26, safe_top + 56), datum, font=f_date, fill=MUTED)

    # ── eyebrow ──
    y = safe_top + ls + 60
    eb = topic["eyebrow"]
    tb = d.textbbox((0, 0), eb, font=f_eyebrow)
    d.rounded_rectangle([pad, y, pad + (tb[2] - tb[0]) + 40, y + 52], radius=26, fill=accent)
    d.text((pad + 20, y + 12), eb, font=f_eyebrow, fill=(6, 10, 18))

    # ── glavno vprašanje ──
    y += 110
    for line in topic["headline"].split("\n"):
        d.text((pad, y), line, font=f_head, fill=WHITE)
        y += 106

    # ── velika številka / ura ──
    y += 40
    d.text((pad, y), topic["big"], font=f_big, fill=accent)
    y += 178
    d.text((pad, y), topic["big_sub"], font=f_bigsub, fill=MUTED)

    # ── panel s tremi podatki, zasidran na dno varnega območja ──
    rows = topic["stats"]
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
        vb = d.textbbox((0, 0), val, font=f_stat_v)
        d.text((W - pad - 32 - (vb[2] - vb[0]), ry + 26), val, font=f_stat_v, fill=WHITE)
        ry += row_h

    # ── noga: trenutno stanje na postaji + CTA ──
    temp = ((current.get("outdoor") or {}).get("temperature") or {}).get("value")
    foot_y = panel_top + panel_h + 22
    if temp is not None:
        d.text((pad, foot_y), f"Zdaj na postaji IREICA1: {str(temp).replace('.', ',')} °C",
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


def main():
    dry = "--dry-run" in sys.argv
    now = datetime.datetime.now(TZ)
    today = now.date()

    fc = fetch_forecast()
    arso = fetch_arso()
    topic = pick_topic(fc, arso)

    print(f"predlog: {topic['topic']} — {topic['headline'].replace(chr(10), ' ')} "
          f"[{topic['big']}]")
    for label, val in topic["stats"]:
        print(f"   {label}: {val}")
    if dry:
        print("(--dry-run: nič ni zapisano)")
        return 0

    current = fetch_current()
    os.makedirs(OUT_DIR, exist_ok=True)
    img = render(topic, now, current)

    name = f"{today.isoformat()}.jpg"
    out = os.path.join(OUT_DIR, name)
    img.save(out, "JPEG", quality=90)
    print(f"✓ zapisano: og/story/{name}")

    removed = prune_old(today)
    if removed:
        print(f"✓ pobrisane stare kartice: {', '.join(sorted(removed))}")

    meta = {
        "date": today.isoformat(),
        "topic": topic["topic"],
        "image": f"{SITE}/og/story/{name}",
        "generated_at": now.isoformat(),
    }
    with open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ zapisano: og/story/latest.json ({meta['image']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
