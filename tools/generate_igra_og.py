#!/usr/bin/env python3
"""
tools/generate_igra_og.py — dnevna OG kartica za /igra/ (1200×630).

Zakaj svoja slika: igra ima vgrajeno deljenje rezultata (`shareText()` v
igra/igra.js) in celoten smisel te funkcije je, da povezava pristane na
Facebooku ali v Messengerju. Do zdaj je zraven šla splošna og-image.jpg, ki o
igri ni povedala nič — nihče ni videl, kakšen dan je danes v dolini.

Kartica ni fotografija z besedilom čez (tako so narejene kartice za zgodbe v
generate_story_card.py), ampak **narisan profil današnjega koridorja**: nebo,
strop termike, silhueta terena od Golt do končnega mejnika, mejniki po poti in
nakazana pot preleta. Slika se torej z vremenom in izbrano smerjo res
spreminja — to je poanta, ne okras.

Piše og/igra/<datum>.jpg; stare (>14 dni) pobriše sama, isto kot dnevna zgodba
in nevihtna karta. Datirano ime je namerno: Facebook si sliko za URL
predpomni, zato bi stalno ime pomenilo, da vsak dan deli včerajšnjo sliko.

Kliče jo tools/generate_igra_page.py takoj po tem, ko sestavi nivo — v istem
teku, da slika in `og:image` na strani nikoli nista narazen. Če Pillow ni na
voljo ali risanje odpove, stran pade nazaj na splošno og-image.jpg in nivo se
vseeno objavi (slika ni vredna tega, da bi zaradi nje izostal nivo dneva).

Uporaba:
  python3 tools/generate_igra_og.py [--dry-run]   # bere igra/nivo.json
"""
import datetime
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "og", "igra")
NIVO_JSON = os.path.join(ROOT, "igra", "nivo.json")
SITE = "https://meteorec.si"
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
KEEP_DAYS = 14

W, H = 1200, 630
PAD = 48
BAR_H = 92
HEAD_H = 150                  # pas z znamko, naslovom in datumom
GROUND_Y = H - BAR_H          # nadmorska višina 0 m
SKY_TOP = HEAD_H              # nadmorska višina `maxalt`
GLIDE = 9.0                   # najboljše drsenje padala (~9:1) — za nakazano pot

WHITE = (255, 255, 255)
MUTED = (176, 190, 209)
DARK = (6, 10, 18)

MES_RODILNIK = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija",
                "julija", "avgusta", "septembra", "oktobra", "novembra", "decembra"]
DNI = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]

# Megla in dež ne smeta dati istega neba kot sončen dan — kartica bi lagala.
FOG_CODES = (45, 48)


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def num_sl(x, d=0):
    if x is None:
        return "–"
    return f"{x:.{d}f}".replace(".", ",")


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


def teren_h(l, km):
    """Višina terena na kilometrini — linearna interpolacija po `teren.h`.
    Namerno lokalna (in ne uvožena iz generate_igra_page): ta skript bere samo
    že zapisan nivo.json in ne sme uvažati generatorja, ki njega kliče."""
    t = l["teren"]
    h = t["h"]
    f = (km - t.get("od_km", 0)) / (t["korak_m"] / 1000.0)
    if f <= 0:
        return float(h[0])
    if f >= len(h) - 1:
        return float(h[-1])
    i = int(f)
    return float(h[i]) + (float(h[i + 1]) - float(h[i])) * (f - i)


def poudarek(l):
    """Barva poudarka po tem, koliko dan sploh nosi. `termika_ms` je dvig v
    jedru, 1,28 m/s pa spuščanje padala med kroženjem — razlika je to, kar
    igralec vidi na variu."""
    dvig = (l.get("termika_ms") or 0) - 1.28
    if l.get("koda_vremena") in FOG_CODES or dvig < 0.3:
        return (148, 163, 184)      # siva — mrtev zrak
    if dvig < 1.0:
        return (249, 115, 22)       # oranžna — šibko
    if dvig < 2.0:
        return (245, 158, 11)       # jantarna — soliden dan
    if dvig < 3.0:
        return (163, 230, 53)       # limeta — dober dan
    return (52, 211, 153)           # zelena — odličen dan


def nebo_barve(l):
    """Trije odtenki neba (vrh, sredina, obzorje). Ob megli in dežju sivo."""
    top, mid, low = (13, 32, 68), (44, 96, 158), (168, 206, 236)
    if l.get("koda_vremena") in FOG_CODES:
        f = 0.75
    elif (l.get("padavine_mm") or 0) > 0.5:
        f = 0.55
    else:
        f = 0.0
    if f:
        grey = (110, 118, 128)
        top, mid, low = mix(top, grey, f), mix(mid, grey, f), mix(low, grey, f * 0.8)
    return top, mid, low


def y_alt(alt, maxalt):
    return GROUND_Y - (alt / maxalt) * (GROUND_Y - SKY_TOP)


def x_km(km, dolzina):
    return (km / dolzina) * W


def pot_preleta(l, dolzina, ceil, korak=0.2):
    """Nakazana pot preleta: strmi vzponi v stebrih, dolgi položni prehodi.
    Dekorativna, a iz današnjih številk — drsenje 9:1, strop dneva, teren
    koridorja. Konča se, ko zmanjka višine."""
    alt = teren_h(l, 0.0)
    vzpon = 1200.0            # m višine na km horizontalno (kroženje je skoraj na mestu)
    pts, km, gor = [(0.0, alt)], 0.0, False
    while km < dolzina:
        km += korak
        t = teren_h(l, km)
        if gor:
            alt += vzpon * korak
            if alt >= ceil:
                alt, gor = ceil, False
        else:
            alt -= (1000.0 / GLIDE) * korak
            # Prvih par kilometrov je spust z vzletišča ob grebenu (v profilu
            # koridorja je ta del vrisan, glej build_igra_corridors.py) — tam
            # se ne kroži, zato pot začne krožiti šele, ko se dolina odpre.
            if km >= 2.5 and alt <= t + 220:
                gor = True
        if alt < t + 30:
            pts.append((km, max(alt, t + 30)))
            break
        pts.append((km, alt))
    return pts


def narisi_nebo(img, l, maxalt, ceil):
    d = ImageDraw.Draw(img)
    top, mid, low = nebo_barve(l)
    for y in range(0, GROUND_Y):
        t = y / GROUND_Y
        c = mix(top, mid, t / 0.55) if t < 0.55 else mix(mid, low, (t - 0.55) / 0.45)
        d.line([(0, y), (W, y)], fill=c)

    # Sonce približno tam, kjer je ura vrhunca termike — zjutraj levo, popoldne desno.
    ura = l.get("ura") or "13:00"
    try:
        h = int(ura[:2]) + int(ura[3:5]) / 60.0
    except (ValueError, IndexError):
        h = 13.0
    fx = min(0.88, max(0.14, (h - 8.0) / 11.0))
    sx, sy = fx * W, SKY_TOP + 48
    if l.get("koda_vremena") not in FOG_CODES and (l.get("padavine_mm") or 0) <= 0.5:
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        # Veliko drobnih korakov s padajočo prosojnostjo — enakomerni obroči bi
        # dali vidno krožnico tam, kjer se sij konča.
        n = 60
        for k in range(n, 0, -1):
            r = 22 + k * 3.4
            gd.ellipse([sx - r, sy - r, sx + r, sy + r],
                       fill=(255, 236, 186, max(1, int(26 * (1 - k / float(n)) ** 2))))
        gd.ellipse([sx - 22, sy - 22, sx + 22, sy + 22], fill=(255, 246, 214, 235))
        img.alpha_composite(glow)
        d = ImageDraw.Draw(img)

    # Kumulusi na bazi — samo, če jih nivo res napove (sicer je »moder dan«).
    baza = l.get("baza_m")
    if baza:
        yb = y_alt(baza, maxalt)
        cl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cl)
        for i in range(9):
            cx = 46 + i * 136 + ((i * 5) % 4) * 22
            sc = 0.55 + 0.5 * ((i * 3) % 5) / 4.0
            w2, h2 = 58 * sc, 24 * sc
            cd.ellipse([cx - w2, yb - h2 * 1.7, cx + w2, yb + h2 * 0.15], fill=(244, 249, 255, 220))
            cd.ellipse([cx - w2 * 0.5, yb - h2 * 2.5, cx + w2 * 0.4, yb - h2 * 0.5],
                       fill=(255, 255, 255, 232))
            cd.rectangle([cx - w2, yb - 3, cx + w2, yb + 3], fill=(190, 204, 222, 210))
        img.alpha_composite(cl)
        d = ImageDraw.Draw(img)

    # Strop termike — črtkano, z oznako desno.
    yc = y_alt(ceil, maxalt)
    for x in range(0, W, 26):
        d.line([(x, yc), (x + 14, yc)], fill=(255, 255, 255, 255), width=2)
    return yc


def narisi_teren(img, l, dolzina, maxalt, accent):
    """Silhueta koridorja: zapolnjen profil + osvetljen greben."""
    t = l["teren"]
    korak_km = t["korak_m"] / 1000.0
    pts = []
    km = 0.0
    while km <= dolzina + korak_km:
        pts.append((x_km(min(km, dolzina), dolzina), y_alt(teren_h(l, km), maxalt)))
        km += korak_km

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.polygon(pts + [(W, H), (0, H)], fill=(48, 72, 70, 255))
    # Navpičen preliv čez zapolnjeno ploskev, da dno doline potone v temo.
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(SKY_TOP, H):
        a = int(min(125, max(0, (y - SKY_TOP) / (H - SKY_TOP) * 150)))
        gd.line([(0, y), (W, y)], fill=(5, 10, 16, a))
    mask = layer.split()[3]
    grad.putalpha(Image.composite(grad.split()[3], Image.new("L", (W, H), 0), mask))
    layer.alpha_composite(grad)
    img.alpha_composite(layer)

    # Greben hladno svetel, pot preleta (spodaj) topla in črtkana — sicer bi
    # bili na kartici dve podobni črti in bralec ne bi vedel, katera je teren.
    d = ImageDraw.Draw(img)
    d.line(pts, fill=(196, 214, 206), width=2, joint="curve")
    return pts


def narisi_pot(img, l, dolzina, maxalt, ceil, accent):
    pts = [(x_km(km, dolzina), y_alt(alt, maxalt)) for km, alt in pot_preleta(l, dolzina, ceil)]
    if len(pts) < 2:
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    # Temno ohišje za kontrast proti nebu, nato črtkana črta v barvi dneva:
    # pot je nakazana, ne izmerjena sled.
    ld.line(pts, fill=(4, 8, 16, 120), width=8, joint="curve")
    for i in range(0, len(pts) - 1, 2):
        ld.line([pts[i], pts[i + 1]], fill=accent + (255,), width=4)
    img.alpha_composite(layer)
    x, y = pts[-1]
    x = min(max(x, 10), W - 10)
    d = ImageDraw.Draw(img)
    d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=WHITE)
    d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=accent)


def zatemni(img):
    """Pas z glavo: skoraj neprozoren na vrhu, mehko izteče na SKY_TOP. Tako
    naslov nikoli ne pade na svetlo nebo ali na vrh Golt — teren se pod tem
    pasom sploh ne začne, ker je `maxalt` preslikan šele od tu navzdol."""
    sc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sc)
    konec = SKY_TOP + 150
    for y in range(0, konec):
        t = y / float(konec)
        sd.line([(0, y), (W, y)], fill=(4, 8, 16, int(236 * (1 - t) ** 2.4)))
    img.alpha_composite(sc)


def render(l, now=None):
    """Nivo dneva → PIL slika 1200×630."""
    kor = l.get("koridor") or {}
    dolzina = float(kor.get("dolzina_km") or 40.0)
    ceil = float(l.get("strop_m") or 1500)
    teren_max = max(float(v) for v in l["teren"]["h"])
    maxalt = max(ceil, teren_max) + 250.0
    accent = poudarek(l)

    img = Image.new("RGBA", (W, H), DARK + (255,))
    narisi_nebo(img, l, maxalt, ceil)
    narisi_teren(img, l, dolzina, maxalt, accent)
    narisi_pot(img, l, dolzina, maxalt, ceil, accent)
    zatemni(img)
    d = ImageDraw.Draw(img)

    f_brand = font("LiberationSans-Bold.ttf", 24)
    f_chip = font("LiberationSans-Bold.ttf", 18)
    f_head = font("LiberationSans-Bold.ttf", 50)
    f_sub = font("LiberationSans-Regular.ttf", 22)
    f_ceil = font("LiberationSans-Bold.ttf", 19)
    f_mile = font("LiberationSans-Regular.ttf", 17)
    f_lab = font("LiberationSans-Bold.ttf", 16)
    f_val = font("LiberationSans-Bold.ttf", 33)
    f_url = font("LiberationSans-Bold.ttf", 24)

    # ── glava: znamka + oznaka v eni vrstici, naslov pod njo ──
    try:
        logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((40, 40),
                                                                                    Image.LANCZOS)
        img.paste(logo, (PAD, 26), logo)
        d = ImageDraw.Draw(img)
        bx = PAD + 40 + 14
    except OSError:
        bx = PAD
    d.text((bx, 32), "METEOREC", font=f_brand, fill=WHITE)
    bx += d.textlength("METEOREC", font=f_brand) + 20

    chip = "IGRA · NIVO DNEVA"
    cw = d.textlength(chip, font=f_chip)
    d.rounded_rectangle([bx, 28, bx + cw + 28, 62], radius=17, fill=accent)
    d.text((bx + 14, 35), chip, font=f_chip, fill=DARK)

    kratko = kor.get("kratko") or "po dolini"
    d.text((PAD, 82), f"Danes {kratko}", font=f_head, fill=WHITE)

    # Datum in dolžina poti desno — naslov levo tako nikoli ne trči vanju.
    zadnji = (l.get("mejniki") or [{}])[-1].get("ime") or "dolina"
    vrstice = [f"Golte → {zadnji} · {num_sl(dolzina, 1)} km"]
    if now is not None:
        vrstice.insert(0, f"{DNI[now.weekday()]}, {now.day}. {MES_RODILNIK[now.month]}")
    for i, vr in enumerate(vrstice):
        d.text((W - PAD - d.textlength(vr, font=f_sub), 84 + i * 32), vr,
               font=f_sub, fill=MUTED)

    # ── oznaka stropa (desno, da ne trči z naslovom) ──
    yc = y_alt(ceil, maxalt)
    lab = f"STROP {num_sl(ceil)} m"
    tb = d.textbbox((0, 0), lab, font=f_ceil)
    lw = tb[2] - tb[0]
    lx = W - PAD - lw - 22
    ly = max(SKY_TOP - 4, yc - 34)
    d.rounded_rectangle([lx, ly, lx + lw + 22, ly + 30], radius=15, fill=(6, 10, 18, 210))
    d.text((lx + 11, ly + 6), lab, font=f_ceil, fill=WHITE)

    # ── mejniki po poti ──
    my = GROUND_Y - 36
    prev_end = -1e9
    for m in (l.get("mejniki") or []):
        km = float(m.get("km") or 0)
        if km > dolzina + 0.01:
            continue
        x = min(max(x_km(km, dolzina), 2), W - 2)
        d.line([(x, my + 26), (x, GROUND_Y)], fill=(255, 255, 255, 140), width=2)
        ime = m.get("ime") or ""
        tw = d.textlength(ime, font=f_mile)
        tx = min(max(x - tw / 2, PAD * 0.3), W - tw - PAD * 0.3)
        if tx < prev_end + 14:      # imena se ne smejo prekrivati
            continue
        prev_end = tx + tw
        d.rounded_rectangle([tx - 10, my - 4, tx + tw + 10, my + 24], radius=14,
                            fill=(6, 10, 18, 205))
        d.text((tx, my), ime, font=f_mile, fill=WHITE)

    # ── spodnji pas s številkami dneva ──
    d.rectangle([0, GROUND_Y, W, H], fill=DARK)
    d.rectangle([0, GROUND_Y, W, GROUND_Y + 3], fill=accent)
    hrb = kor.get("hrbtnik_kmh")
    stats = [
        ("STROP", f"{num_sl(ceil)} m"),
        ("DVIGI", f"{num_sl(l.get('termika_ms'), 1)} m/s"),
        ("HRBTNIK", "–" if hrb is None else f"{'+' if hrb >= 0 else '−'}{abs(int(hrb))} km/h"),
    ]
    x = PAD
    for lab_t, val in stats:
        d.text((x, GROUND_Y + 20), lab_t, font=f_lab, fill=MUTED)
        d.text((x, GROUND_Y + 42), val, font=f_val, fill=WHITE)
        x += 230
    url = "meteorec.si/igra"
    tb = d.textbbox((0, 0), url, font=f_url)
    d.text((W - PAD - (tb[2] - tb[0]), GROUND_Y + 34), url, font=f_url, fill=accent)

    return img.convert("RGB")


def pocisti_stare(danes):
    """Kartice, starejše od KEEP_DAYS, pobriši — isto kot og/story in
    og/storm-map. Objavljena povezava kaže na današnjo, stare nihče ne bere."""
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


def zapisi(l, now=None):
    """Nariše in shrani kartico za nivo `l`. Vrne absolutni URL slike."""
    datum = l.get("datum") or datetime.date.today().isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    img = render(l, now)
    name = f"{datum}.jpg"
    img.save(os.path.join(OUT_DIR, name), "JPEG", quality=88, optimize=True)
    try:
        pocisti_stare(datetime.date.fromisoformat(datum))
    except ValueError:
        pass
    return f"{SITE}/og/igra/{name}"


def main():
    dry = "--dry-run" in sys.argv[1:]
    with open(NIVO_JSON, encoding="utf-8") as f:
        l = json.load(f)
    if dry:
        print(f"(--dry-run) nivo {l.get('datum')} — kartica ni zapisana")
        return 0
    try:
        now = datetime.date.fromisoformat(l["datum"])
        now = datetime.datetime(now.year, now.month, now.day)
    except (KeyError, ValueError):
        now = datetime.datetime.now()
    url = zapisi(l, now)
    print(f"✓ {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
