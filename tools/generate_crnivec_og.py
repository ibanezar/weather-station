#!/usr/bin/env python3
"""
tools/generate_crnivec_og.py — dnevna OG kartica za /crnivec/ (1200×630).

Do zdaj je stran za deljenje uporabljala splošno og-image.jpg, ki o vsebini
strani ni povedala nič — kdor je delil povezavo na FB, v predogledu ni videl,
katera cona velja danes. Ta kartica nariše isto stripovsko, svetlo temo kot
stran sama (glej CSS v generate_crnivec_page.py) — namerno DRUGAČNA paleta od
preostalih dnevnih OG kartic na strani (igra, nevihtna karta), ki so temne,
ker je tudi sama stran /crnivec/ namenoma vizualno ločena od preostale strani
(glej opombo na vrhu generate_crnivec_page.py).

Kliče jo generate_crnivec_page.py takoj po tem, ko izbere cono/citat/suh niz
(isti vzorec kot generate_igra_og.py, poklican iz generate_igra_page.py) —
slika in stran zato nikoli nista iz različnih dni. Sprejme že RAZREŠENE
podatke (cono, vreme, citat, suh niz), ne bere data/winter-data.json sama:
pravilo za izbiro cone (pick_zone) ostane na enem mestu
(generate_crnivec_page.py), ne podvojeno tu.

Piše og/crnivec/<datum>.jpg; stare (>14 dni) pobriše sama, isto kot dnevna
zgodba, nevihtna karta in OG kartica igre.

Uporaba: uvozi se in pokliče zapisi(zone, weather, quote, streak, now) — ni
samostojnega ukaznega vmesnika (glej opombo zgoraj — brez že razrešenih
podatkov bi CLI moral podvojiti pick_zone).
"""
import datetime
import os
import re

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "og", "crnivec")
SITE = "https://meteorec.si"
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
KEEP_DAYS = 14

W, H = 1200, 630
PAD = 56
BAR_H = 96

CREAM = (253, 246, 227)
INK = (17, 17, 17)
WHITE = (255, 255, 255)
MUTED = (107, 114, 128)

MES_RODILNIK = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija",
                "julija", "avgusta", "septembra", "oktobra", "novembra", "decembra"]
DNI = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def num_sl(x, d=1):
    if x is None:
        return "–"
    return f"{x:.{d}f}".replace(".", ",")


def wrap(draw, text, fnt, max_w, max_lines=2):
    """Prelomi `text` na `max_lines` vrstic, ki se prilegajo `max_w`; presežek
    zadnje vrstice odreže z "…" (isto načelo kot wrapText() v klientskem
    "Deli kot sliko" -- glej SHARE_JS_TEMPLATE v generate_crnivec_page.py --
    samo tu za PIL namesto canvas 2D)."""
    words = text.split(" ")
    lines, line = [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if line and draw.textlength(test, font=fnt) > max_w:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    last = kept[-1]
    while last and draw.textlength(last + "…", font=fnt) > max_w:
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
    kept[-1] = (last or kept[-1]) + "…"
    return kept


def fit_font(draw, text, name, start, min_size, max_w):
    """Zmanjšuje velikost pisave, dokler `text` ne pade pod `max_w` -- varovalka
    za dolge nalepke con (npr. »SPOLZKO, PAZI«), ne redno orodje: pri
    trenutnih štirih nalepkah se pri `start` skoraj vedno prilega."""
    size = start
    while size > min_size:
        f = font(name, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return font(name, min_size)


def render(zone, weather, quote, streak, now=None):
    now = now or datetime.datetime.now()
    accent = hex_rgb(zone["color"])

    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # Halftone pikčasta podlaga -- ista tekstura kot .crn-wrap na sami strani
    # (glej CSS v generate_crnivec_page.py: radial-gradient #111 1px na 16px
    # mreži), tu prepisana v PIL piko-za-piko.
    for y in range(4, H - BAR_H, 20):
        for x in range(4, W, 20):
            d.ellipse([x, y, x + 2, y + 2], fill=INK)

    f_brand = font("LiberationSans-Bold.ttf", 22)
    f_chip = font("LiberationSans-Bold.ttf", 16)
    f_date = font("LiberationSans-Regular.ttf", 20)
    f_sub = font("LiberationSans-Regular.ttf", 28)
    f_quote = font("LiberationSans-Regular.ttf", 26)
    f_lab = font("LiberationSans-Bold.ttf", 15)
    f_val = font("LiberationSans-Bold.ttf", 26)
    f_url = font("LiberationSans-Bold.ttf", 22)

    # ── glava: znamka + oznaka, datum desno ──
    d.text((PAD, 34), "METEOREC", font=f_brand, fill=INK)
    bx = PAD + d.textlength("METEOREC", font=f_brand) + 18
    chip = "KAKO JE ČEZ ČRNIVEC?"
    cw = d.textlength(chip, font=f_chip)
    d.rounded_rectangle([bx, 32, bx + cw + 26, 62], radius=15, fill=INK)
    d.text((bx + 13, 39), chip, font=f_chip, fill=WHITE)

    datum = f"{DNI[now.weekday()]}, {now.day}. {MES_RODILNIK[now.month]}"
    tb = d.textbbox((0, 0), datum, font=f_date)
    d.text((W - PAD - (tb[2] - tb[0]), 38), datum, font=f_date, fill=MUTED)

    # ── velik naslov: DANAŠNJA OCENA, ne generičen naslov strani -- to je
    # tisto, kar bralec v FB/Twitter predogledu vidi prvo. ──
    f_head = fit_font(d, zone["label"], "LiberationSans-Bold.ttf", 78, 40, W - 2 * PAD)
    hy = 140
    d.text((PAD, hy), zone["label"], font=f_head, fill=accent,
            stroke_width=6, stroke_fill=INK)
    hb = d.textbbox((PAD, hy), zone["label"], font=f_head, stroke_width=6)
    y = hb[3] + 30

    for line in wrap(d, zone["desc"], f_sub, W - 2 * PAD, max_lines=2):
        d.text((PAD, y), line, font=f_sub, fill=INK)
        y += 36
    y += 14

    # ── citat dneva v rumenem oblačku (isti vizualni jezik kot .crn-quote) ──
    qtext = f"“{quote}”"
    qlines = wrap(d, qtext, f_quote, W - 2 * PAD - 40, max_lines=2)
    qh = 26 + len(qlines) * 34
    qy = y
    d.rounded_rectangle([PAD + 6, qy + 6, W - PAD + 6, qy + qh + 6], radius=14, fill=INK)
    d.rounded_rectangle([PAD, qy, W - PAD, qy + qh], radius=14, fill=(254, 240, 138),
                         outline=INK, width=3)
    for i, line in enumerate(qlines):
        d.text((PAD + 22, qy + 16 + i * 34), line, font=f_quote, fill=INK)

    # ── spodnji pas: statistika + URL, isti vzorec kot generate_igra_og.py ──
    d.rectangle([0, H - BAR_H, W, H], fill=INK)
    d.rectangle([0, H - BAR_H, W, H - BAR_H + 4], fill=accent)
    temp_txt = (f"{num_sl(weather.get('temp_c'), 1)} °C"
                if weather.get("temp_c") is not None else "–")
    snow_txt = (f"{num_sl(weather.get('expected_snow_cm_24h'), 1)} cm"
                if weather.get("expected_snow_cm_24h") is not None else "–")
    temp_lab = "IZMERJENO (DRSI)" if weather.get("temp_src") == "izmerjeno" else "NA PRELAZU"
    stats = [(temp_lab, temp_txt), ("SNEG / 24H", snow_txt),
             ("SUH NIZ (DOLINA)", f"{streak} dni")]
    x = PAD
    for lab, val in stats:
        d.text((x, H - BAR_H + 18), lab, font=f_lab, fill=MUTED)
        d.text((x, H - BAR_H + 38), val, font=f_val, fill=WHITE)
        x += 236
    url = "meteorec.si/crnivec"
    tb = d.textbbox((0, 0), url, font=f_url)
    d.text((W - PAD - (tb[2] - tb[0]), H - BAR_H + 34), url, font=f_url, fill=accent)

    return img


def pocisti_stare(danes):
    """Kartice, starejše od KEEP_DAYS, pobriši -- isto kot og/story, og/igra
    in og/storm-map. Objavljena povezava kaže na današnjo, stare nihče ne bere."""
    odstranjene = []
    if not os.path.isdir(OUT_DIR):
        return odstranjene
    meja = danes - datetime.timedelta(days=KEEP_DAYS)
    for name in os.listdir(OUT_DIR):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.jpg", name)
        if not m:
            continue
        try:
            if datetime.date.fromisoformat(m.group(1)) < meja:
                os.remove(os.path.join(OUT_DIR, name))
                odstranjene.append(name)
        except (ValueError, OSError):
            continue
    return odstranjene


def zapisi(zone, weather, quote, streak, now=None):
    """Nariše in shrani dnevno kartico. Vrne absolutni URL slike."""
    now = now or datetime.datetime.now()
    os.makedirs(OUT_DIR, exist_ok=True)
    img = render(zone, weather, quote, streak, now)
    name = f"{now.date().isoformat()}.jpg"
    img.save(os.path.join(OUT_DIR, name), "JPEG", quality=88, optimize=True)
    try:
        pocisti_stare(now.date())
    except ValueError:
        pass
    return f"{SITE}/og/crnivec/{name}"
