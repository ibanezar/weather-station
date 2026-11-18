#!/usr/bin/env python3
"""
tools/generate_juzni_veter_card.py -- kartica 1080×1350 za FB/IG objavo članka »Južni veter že drugi dan« (18. 11. 2026).

Fotografija (Menina z oblakom čez greben, Filip Eremita) je glavna, spodaj ena trditev in dve številki. Številke so iz ISTEGA izračuna kot članek
(`generate_juzni_veter_post.build_article` se zažene, zato veljajo iste varovalke). Notranjih meritev ne uporablja.

Z `--story` nastane kartica 1080×1920 (9:16) za zgodbo FB/IG: zgoraj ~250 px in spodaj ~340 px prekrije vmesnik aplikacije, zato je vsebina vmes.

Usage:
    python3 tools/generate_juzni_veter_card.py [--story] [--out FILE]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_juzni_veter_post as post  # noqa: E402

ROOT = post.ROOT
STORY = "--story" in sys.argv
W, H, PAD = 1080, (1920 if STORY else 1350), 64
Y0 = 330 if STORY else 0                   # zgornji rob fotografije (zgodba: pod prekritim pasom)
PH = 810                                   # višina fotografije (1200×900 → 1080×810, brez povečave)
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
B, R = "LiberationSans-Bold.ttf", "LiberationSans-Regular.ttf"
BG, WHITE, MUTED, DIM = (8, 11, 20), (255, 255, 255), (200, 210, 228), (150, 160, 182)
ORANGE = (251, 146, 60)
STORY = "--story" in sys.argv
OUT = os.path.join(ROOT, "og", f"{post.SLUG}-{'zgodba' if STORY else 'kartica'}.jpg")


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def main():
    S = post.Snap()
    post.build_article(S)                  # varovalke: pade, če trditve ne držijo
    w17 = round(S.d17["windspeedAvg"], 1)
    H_ = S.H
    nov = [v["windspeedAvg"] for k, v in H_.items() if k[5:7] == "11" and v.get("windspeedAvg") is not None]
    nov_avg = sum(nov) / len(nov)
    low = round(min(S.d18["tempLow"], S.now["temp_c"]), 1)

    img = Image.new("RGB", (W, H), BG)
    ph = Image.open(os.path.join(ROOT, "img", "blog", post.SLUG, "menina-polje.jpg")).convert("RGB").resize((W, PH), Image.LANCZOS)
    img.paste(ph, (0, Y0))
    d = ImageDraw.Draw(img)
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
    ly = 250 if STORY else 40
    img.paste(logo, (PAD, ly), logo)
    d.text((PAD + 80, ly + 12), "METEOREC", font=font(B, 34), fill=WHITE)

    T = Y0 + PH                            # zgornji rob besedilnega dela
    d.text((PAD, T + 36), "Južni veter že drugi dan", font=font(B, 66), fill=WHITE)
    d.text((PAD, T + 118), "Oblak čez Menino, v dolini pa toplo.", font=font(R, 34), fill=MUTED)

    cw = (W - 2 * PAD - 28) // 2
    items = [(f"{post.num(w17)} km/h", f"torkov veter v povprečju\n(novembra običajno {post.num(nov_avg)} km/h)"),
             (f"{post.num(low)} °C", f"najnižja temperatura od\npolnoči do {post.hm(S.local_now)} v Rečici")]
    for i, (big, small) in enumerate(items):
        x = PAD + i * (cw + 28)
        d.rounded_rectangle((x, T + 178, x + cw, T + 178 + 150), radius=22, fill=(18, 23, 38), outline=(44, 52, 74), width=2)
        d.text((x + 24, T + 190), big, font=font(B, 52), fill=ORANGE)
        for j, line in enumerate(small.split("\n")):
            d.text((x + 24, T + 258 + j * 30), line, font=font(R, 24), fill=MUTED)
    d.text((PAD, T + 356 if STORY else H - 40), "Postaja IREICA1 · meteorec.si/blog", font=font(R, 24), fill=DIM)

    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT
    img.convert("RGB").save(out, quality=92)
    print("✓ kartica:", os.path.relpath(out, ROOT), img.size)


if __name__ == "__main__":
    main()
