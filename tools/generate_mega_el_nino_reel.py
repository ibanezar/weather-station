#!/usr/bin/env python3
"""
tools/generate_mega_el_nino_reel.py -- navpična slika 1080×1920 za reel/zgodbo ob članku »Mega El Niño« (24. 11. 2026).

Ena grafika (dve vodoravni vrstici na skupni lestvici) + naslov, vir v nogi; do 20 besed po slogovnem vodniku.
Vsebina je v varnem območju reela (y 250–1560: zgoraj in spodaj prekrije vmesnik aplikacije). Številki sta iz članka:
  +3,3 °C  Niño 3.4, tedensko, tradicionalno (OISST, NOAA CPC; teden 15.–21. 11. 2026) -- data/el-nino-mega-1124.json
  ≈ +10 °C lokalna konica na dnevnem zemljevidu ECMWF (Ryan Maue, 22. 11. 2026; zemljevida nisem preveril)
Ozadje: pikčast Pacifik (maska kopnega iz igre 365-0) z oranžnim sijem na vzhodu.

Usage:  python3 tools/generate_mega_el_nino_reel.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "og", "reel", "mega-el-nino-1124.jpg")
FONT_DIR = "/usr/share/fonts/opentype/inter/"
W, H = 1080, 1920
BG, INK, MUTED = (7, 11, 22), (232, 237, 248), (173, 192, 216)
BLUE, ORANGE = (57, 135, 229), (217, 89, 38)


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def main():
    data = json.load(open(os.path.join(ROOT, "data", "el-nino-mega-1124.json"), encoding="utf-8"))
    nino34 = data["nino_weekly"]["trad"][-1][2]
    assert nino34 == 3.3, "številka na sliki ne ustreza podatkom"
    mask = json.load(open(os.path.join(ROOT, "365-0-game", "src", "data", "worldmask.json"), encoding="utf-8"))
    cols = list(range(100, 120)) + list(range(0, 40))
    rows = list(range(17, 37))
    cell = W / 60
    map_y = 640

    img = Image.new("RGB", (W, H), BG)
    # sij na vzhodu Pacifika (Peru, Galápagos), pod pikami
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = (265 - 120) / 3 * cell, map_y + 10.5 * cell
    gd.ellipse((cx - 330, cy - 150, cx + 330, cy + 150), fill=(150, 55, 18))
    gd.ellipse((cx + 60, cy - 60, cx + 300, cy + 110), fill=(235, 110, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img = Image.composite(glow, img, glow.convert("L").point(lambda v: min(255, int(v * 1.4)))).convert("RGB")
    d = ImageDraw.Draw(img)
    R = mask["rows"]
    for ri, r in enumerate(rows):
        for ci, c in enumerate(cols):
            if R[r][c] == "1":
                x, y = (ci + .5) * cell, map_y + (ri + .5) * cell
                d.ellipse((x - cell * .27, y - cell * .27, x + cell * .27, y + cell * .27), fill=(84, 102, 134))
    # obrisi regij Niño 3.4 (190°–240° vzhodno = 170°–120° zahodno, 5° S–5° J)
    def X(lon):
        return (lon - 120) / 3 * cell
    ey = map_y + 10 * cell
    for lon0, lon1, col in ((190, 240, BLUE),):
        d.rounded_rectangle((X(lon0), ey - 5 / 3 * cell, X(lon1), ey + 5 / 3 * cell), radius=8, outline=col, width=4)
    fl = font("Inter-SemiBold.otf", 28)
    d.text((X(190), ey + 5 / 3 * cell + 14), "Niño 3.4", font=fl, fill=BLUE)
    # lokalna konica: Galápagos (okoli 91° Z = 269° V), oranžen obroč
    gx, gy = X(269), ey
    d.ellipse((gx - 34, gy - 34, gx + 34, gy + 34), outline=ORANGE, width=6)
    d.ellipse((gx - 11, gy - 11, gx + 11, gy + 11), fill=ORANGE)
    d.text((gx, gy + 52), "Galápagos", font=fl, fill=ORANGE, anchor="ma")

    # naslov
    d.text((72, 290), "EL NIÑO · 24. 11. 2026", font=font("Inter-Bold.otf", 34), fill=ORANGE)
    f_h = font("Inter-ExtraBold.otf", 112)
    d.text((72, 350), "»Mega El Niño«:", font=f_h, fill=INK)
    d.text((72, 478), "10 °C je konica", font=f_h, fill=INK)

    # ena grafika: dve vrstici na skupni lestvici 0–10 °C
    x0, wbar, bh = 72, W - 144, 64
    f_lab, f_val = font("Inter-Medium.otf", 38), font("Inter-ExtraBold.otf", 66)
    y1, y2 = 1070, 1300
    for y, lab, v, col in ((y1, "Povprečje osrednjega Pacifika", nino34, BLUE), (y2, "Lokalna konica na dnevni karti", 10.0, ORANGE)):
        d.text((x0, y), lab, font=f_lab, fill=MUTED)
        d.rounded_rectangle((x0, y + 62, x0 + wbar, y + 62 + bh), radius=bh // 2, fill=(24, 32, 52))
        d.rounded_rectangle((x0, y + 62, x0 + max(bh, wbar * v / 10), y + 62 + bh), radius=bh // 2, fill=col)
        txt = (f"+{v:.1f}".replace(".", ",") + " °C") if v < 10 else "≈ +10 °C"
        tw = d.textlength(txt, font=f_val)
        d.text((x0 + wbar - tw - 30 if v >= 10 else x0 + max(bh, wbar * v / 10) + 22, y + 62 + bh / 2 - 40), txt, font=f_val,
               fill=INK)
    # skupna lestvica
    for t in (0, 5, 10):
        xx = x0 + wbar * t / 10
        d.text((xx, 1450), f"{t}", font=font("Inter-Medium.otf", 28), fill=MUTED, anchor="ma")

    # noga: vir
    d.text((72, 1520), "Vir: NOAA CPC, Copernicus, ECMWF · meteorec.si", font=font("Inter-Medium.otf", 30), fill=MUTED)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, quality=92)
    print("✓", os.path.relpath(OUT, ROOT), img.size)


if __name__ == "__main__":
    main()
