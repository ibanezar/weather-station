#!/usr/bin/env python3
"""
tools/generate_temperature_gobe_card.py -- fotografska kartica 1080×1350 za FB/IG objavo članka
»Tla imajo 7 °C: za jurčka še dovolj toplo, za lisičko ne več« (9. 11. 2026).

Fotografija (Filipov jurček, `img/blog/<slug>/foto-1.jpg`) je glavna, ob njej tri številke. Številke so iz ISTEGA izračuna
kot članek (`generate_temperature_gobe_post.build_article` se zažene, zato veljajo iste varovalke: če podatki trditve
ne podpirajo več, kartica ne nastane). Slog po docs/slog-pisanja.md (razdelek 7): en naslov, ena fotografija, malo besed,
vir v nogi. Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_temperature_gobe_card.py [--out-dir DIR]
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_temperature_gobe_post as post  # noqa: E402
import generate_vrh_sezone_card_variants as cv  # noqa: E402   (pisave, platno, glava, značka)

ROOT = post.ROOT
W, H, PAD = cv.W, cv.H, cv.PAD
font, text_w, canvas, header, badge = cv.font, cv.text_w, cv.canvas, cv.header, cv.badge
B, R = cv.B, cv.R
WHITE, MUTED, DIM, GREEN = cv.WHITE, cv.MUTED, cv.DIM, cv.GREEN
AMBER = (251, 191, 36)
PHOTO = os.path.join(ROOT, "img", "blog", post.SLUG, "foto-1.jpg")
OUT = os.path.join(ROOT, "og", f"{post.SLUG}-kartica.jpg")


def fit(d, text, size, maxw, bold=True):
    while text_w(d, text, font(B if bold else R, size)) > maxw and size > 40:
        size -= 2
    return font(B if bold else R, size)


def build():
    Hh, soil, _ = post.load()
    post.build_article(Hh, soil)                          # varovalke: pade, če trditve ne držijo
    soil_w = post.mean(soil[d] for d in post.rng(post.LAST, 11, 1, 11, 7))
    assert soil_w - post.THR_LO > 3 and soil_w < post.THR_HI
    img, d = canvas()
    header(img, d, "temperatura tal in gobe", thumb=False)
    badge(d, "POSTAJA IREICA1 + ERA5-LAND")
    f1 = fit(d, "Za jurčka še dovolj.", 88, W - 2 * PAD)
    d.text((PAD, 268), f"Tla imajo {post.num(soil_w, 0)} °C.", font=font(B, 88), fill=WHITE)
    d.text((PAD, 372), "Za jurčka še dovolj.", font=f1, fill=GREEN)

    ph = Image.open(PHOTO).convert("RGB").resize((500, 667), Image.LANCZOS)
    mask = Image.new("L", ph.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=26, fill=255)
    py = 500
    img.paste(ph, (PAD, py), mask)
    cf = font(R, 22)
    cw = text_w(d, "Foto: Filip Eremita", cf)
    d.rounded_rectangle((PAD + 14, py + ph.height - 46, PAD + 14 + cw + 24, py + ph.height - 14), radius=16, fill=(5, 6, 14))
    d.text((PAD + 26, py + ph.height - 42), "Foto: Filip Eremita", font=cf, fill=WHITE)

    x0 = PAD + 500 + 44
    rows = [(f"{post.num(soil_w)} °C", ["tla v Rečici, povprečje", "od 1. do 7. novembra"], WHITE),
            (f"{post.num(post.THR_LO)} °C", ["prag jurčka: do njega", "še več kot 3 °C"], GREEN),
            (f"{post.num(post.THR_HI)} °C", ["prag lisičke in marele:", "tla so pod njim"], AMBER)]
    y = py + 10
    for big, lab, col in rows:
        d.rounded_rectangle((x0, y + 6, x0 + 8, y + 150), radius=4, fill=col)
        d.text((x0 + 28, y), big, font=font(B, 66), fill=WHITE)
        for k, ln in enumerate(lab):
            d.text((x0 + 28, y + 84 + 34 * k), ln, font=font(R, 26), fill=MUTED)
        y += 218

    d.text((PAD, 1214), "Prag je parameter modela, ne izmerjena meja rasti.", font=font(B, 30), fill=WHITE)
    d.text((PAD, 1260), "Tla: Open-Meteo (ERA5-Land), povprečje plasti 0–28 cm.", font=font(R, 27), fill=DIM)
    d.text((PAD, 1298), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)
    return img


def main():
    out = OUT
    if "--out-dir" in sys.argv:
        out = os.path.join(sys.argv[sys.argv.index("--out-dir") + 1], os.path.basename(OUT))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build().save(out, quality=92)
    print("✓", out)


if __name__ == "__main__":
    main()
