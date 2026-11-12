#!/usr/bin/env python3
"""
tools/generate_sneg_gore_card.py -- kartica 1080×1920 (9:16, zgodba/reel) za članek
»Sneg ta teden: v dolini ne, na višinah nekaj centimetrov« (12. 11. 2026).

Številke so iz ISTEGA izračuna kot članek (`generate_sneg_gore_post.build_article` se zažene, zato veljajo iste varovalke:
če napoved ne podpira več trditve »v dolini ne«, kartica ne nastane). Na FB/IG ne objavlja. Notranjih meritev ne uporablja.
Pomembno za zgodbe: zgoraj ~250 px in spodaj ~340 px prekrije vmesnik aplikacije, zato je vsebina vmes.

Usage:
    python3 tools/generate_sneg_gore_card.py [--out FILE]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_sneg_gore_post as post  # noqa: E402

ROOT = post.ROOT
W, H, PAD = 1080, 1920, 70
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
B, R = "LiberationSans-Bold.ttf", "LiberationSans-Regular.ttf"
BG, WHITE, MUTED, DIM = (5, 6, 14), (255, 255, 255), (200, 210, 228), (150, 160, 182)
PANEL, LINE = (16, 20, 34), (44, 52, 74)
BLUE, BLUE_L, ICE = (57, 135, 229), (74, 98, 140), (147, 197, 253)
OUT = os.path.join(ROOT, "og", f"{post.SLUG}-zgodba.jpg")


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def tw(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def val(v):
    return "0" if v < 0.05 else ("< 1" if v < 1.0 else str(post.rnd(v)))


def main():
    S = post.Snap()
    article = post.build_article(S)          # varovalke: pade, če trditve ne držijo
    rows = [(e, n, S.snow_cm(e), S.snow_cm(e, -post.COLD_SHIFT)) for e, n in post.PLACES]
    rain = S.day_sum("2026-11-12") + S.day_sum("2026-11-13")
    sob = next(d for d in S.raw["mtr"]["days"] if d["date"] == "2026-11-14")

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((84, 84), Image.LANCZOS)
    img.paste(logo, (PAD, 250), logo)
    d.text((PAD + 106, 250), "METEOREC", font=font(B, 40), fill=WHITE)
    d.text((PAD + 108, 296), "napoved snega · 12.–14. 11.", font=font(R, 26), fill=MUTED)

    # naslov
    d.text((PAD, 400), "Sneg v dolini?", font=font(B, 92), fill=WHITE)
    d.text((PAD, 508), "Ne. Višine: odvisno.", font=font(B, 92), fill=ICE)
    sub = ["Ohladitev pride, ko dež že preneha.", f"V Rečici do petka okoli {post.rnd(rain)} mm dežja."]
    for i, t in enumerate(sub):
        d.text((PAD, 650 + i * 44), t, font=font(R, 32), fill=MUTED)

    # panel: sneg po višinah
    y0, y1 = 770, 1385
    d.rounded_rectangle((PAD, y0, W - PAD, y1), radius=28, fill=PANEL, outline=LINE, width=2)
    d.text((PAD + 36, y0 + 28), "Nov sneg do sobote opoldne (cm)", font=font(B, 30), fill=WHITE)
    d.rectangle((PAD + 36, y0 + 82, PAD + 58, y0 + 100), fill=BLUE)
    d.text((PAD + 68, y0 + 76), "osnovni izračun", font=font(R, 25), fill=MUTED)
    d.rectangle((PAD + 330, y0 + 82, PAD + 352, y0 + 100), fill=BLUE_L)
    d.text((PAD + 362, y0 + 76), "zrak 2 °C hladnejši", font=font(R, 25), fill=MUTED)
    lx, x0, x1 = PAD + 300, PAD + 320, W - PAD - 150
    scale = 40.0
    X = lambda v: x0 + min(v, scale) / scale * (x1 - x0)
    for i, (e, n, b, c) in enumerate(rows):
        y = y0 + 130 + i * 62
        lab = f"{n} {e} m" if n else f"{e} m"
        d.text((lx - tw(d, lab, font(R, 28)), y + 6), lab, font=font(R, 28), fill=WHITE)
        if c > 0:
            d.rounded_rectangle((x0, y, X(c), y + 44), radius=6, fill=BLUE_L)
        if b > 0:
            d.rounded_rectangle((x0, y + 9, max(X(b), x0 + 4), y + 35), radius=4, fill=BLUE)
        d.text((X(max(b, c)) + 14, y + 4), f"{val(b)} → {val(c)}", font=font(B, 30), fill=WHITE)
    d.text((PAD + 36, y1 - 40), "Višine so preračunane iz Rečice; model ne pozna pobočij.", font=font(R, 24), fill=DIM)

    # tri številke
    stats = [("0 cm", "snega v Rečici\nin na Črnivcu"), (f"{post.num(sob['tmin'], 0).replace('-', '–')} °C", "sobota zjutraj\n(model MTR)"),
             (f"{post.rnd(sob['p_frost'] * 100)} %", "verjetnost\nzmrzali")]
    cw = (W - 2 * PAD - 2 * 24) // 3
    for i, (big, small) in enumerate(stats):
        x = PAD + i * (cw + 24)
        d.rounded_rectangle((x, 1415, x + cw, 1605), radius=22, fill=PANEL, outline=LINE, width=2)
        d.text((x + 24, 1435), big, font=font(B, 54), fill=WHITE)
        for j, line in enumerate(small.split("\n")):
            d.text((x + 24, 1511 + j * 34), line, font=font(R, 27), fill=MUTED)

    d.text((PAD, 1635), "Izračun Open-Meteo in model MTR. Ni uradno opozorilo.", font=font(R, 26), fill=DIM)
    d.text((PAD, 1673), "Podatki in grafi: meteorec.si/blog", font=font(B, 28), fill=WHITE)

    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT
    img.save(out, quality=92)
    print("✓ kartica:", os.path.relpath(out, ROOT), img.size)


if __name__ == "__main__":
    main()
