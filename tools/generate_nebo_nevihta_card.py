#!/usr/bin/env python3
"""
tools/generate_nebo_nevihta_card.py -- štiri kartice 1080×1350 za FB/IG objavo članka »Nevihta za gorami, nebo v ognju nad Rečico« (18. 11. 2026).

Fotografija (Filip Eremita) je glavna, spodaj naslov in dve številki. Številke so iz ISTEGA izračuna kot članek
(`generate_nebo_nevihta_post.build_article` se zažene, zato veljajo iste varovalke). Notranjih meritev ne uporablja.
Z `--story` nastanejo kartice 1080×1920 (9:16): zgoraj ~250 px in spodaj ~340 px prekrije vmesnik aplikacije.

Usage:
    python3 tools/generate_nebo_nevihta_card.py [--story] [--variant N]     (privzeto vse štiri)
"""
import datetime
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_nebo_nevihta_post as post  # noqa: E402

ROOT = post.ROOT
STORY = "--story" in sys.argv
W, H, PAD = 1080, (1920 if STORY else 1350), 64
Y0 = 330 if STORY else 0
PH = 810
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
B, R = "LiberationSans-Bold.ttf", "LiberationSans-Regular.ttf"
BG, WHITE, MUTED, DIM = (8, 11, 20), (255, 255, 255), (200, 210, 228), (150, 160, 182)
ORANGE = (251, 146, 60)


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def variants(S):
    """(fotografija, naslov, podnaslov, [(velika številka, opis), (…)]) -- vse številke izračunane iz posnetka"""
    half = {}
    for b in S.bins:
        k = b["t"].replace(minute=b["t"].minute // 30 * 30)
        half[k] = half.get(k, 0) + b["n"]
    peak_t, peak_n = max(half.items(), key=lambda x: x[1])
    pe = peak_t + datetime.timedelta(minutes=30)
    tr = S.track()
    (ta, da), (tb, db) = tr[0], tr[-1]
    speed = (da - db) / ((tb - ta).total_seconds() / 3600 + 1 / 6)
    ss, _ = post.sunset_local(post.TODAY)
    last = S.bins[-1]["t"] + datetime.timedelta(minutes=10)
    nb = post.NBSP
    total = post.big(S.total).replace(nb, " ")
    rain = S.now["rain_today_mm"]
    assert rain == 0
    return {
        1: ("mamatus.jpg", "Nevihta 30 km stran\nje naslikala izjemno nebo", "Oblak je segel nad dolino, dežemer pa ni zabeležil ničesar.",
            [(f"{total} strel", f"v krogu 200 km, od {post.hm(S.bins[0]['t'].replace(minute=50))} do {post.hm(last)}\n(Blitzortung)"),
             (f"{post.num(S.closest, 0)} km", "najbližja strela od postaje\n(dan še ni končan)")]),
        2: ("rdece-nebo.jpg", "Dežemer 0 mm, nebo pa gori", "Padlo je le nekaj kapelj, nič izmerljivega.",
            [("0 mm", f"izmerjenega dežja v Rečici\ndo {post.hm(S.fetched)} (dan še ni končan)"),
             (f"{post.num(S.closest, 0)} km", "najbližja strela od postaje")]),
        3: ("nakovalo.jpg", "Nakovalo nad dolino", "Visok oblak nevihte se je razširil nad Rečico.",
            [(f"{peak_n}", f"strel v najbolj dejavni pol ure\n({post.hm(peak_t)}–{post.hm(pe)})"),
             (f"≈ {post.num(speed, 0)} km/h", "približevanje zahodne celice\n(groba ocena)")]),
        4: ("somrak.jpg", "Zakaj je nebo gorelo?", "Sonce je že zašlo, visok oblak pa je še žarel.",
            [(post.hm(ss), "geometrijski sončni zahod\nv Rečici"),
             ("≈ 3°", "pod obzorjem še ujame sonce\noblak na višini 9 km")]),
    }


def render(S, n, spec):
    photo, title, sub, items = spec
    img = Image.new("RGB", (W, H), BG)
    ph = Image.open(os.path.join(ROOT, "img", "blog", post.SLUG, photo)).convert("RGB").resize((W, PH), Image.LANCZOS)
    img.paste(ph, (0, Y0))
    d = ImageDraw.Draw(img)
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
    ly = 250 if STORY else 40
    img.paste(logo, (PAD, ly), logo)
    d.text((PAD + 80, ly + 12), "METEOREC", font=font(B, 34), fill=WHITE)
    T = Y0 + PH
    lines = title.split("\n")
    for k, ln in enumerate(lines):
        d.text((PAD, T + 28 + k * 66), ln, font=font(B, 60 if len(lines) > 1 else 66), fill=WHITE)
        assert d.textlength(ln, font=font(B, 60 if len(lines) > 1 else 66)) < W - 2 * PAD, ln
    T += 66 * (len(lines) - 1)
    d.text((PAD, T + 118), sub, font=font(R, 32), fill=MUTED)
    assert d.textlength(sub, font=font(R, 32)) < W - 2 * PAD, sub
    cw = (W - 2 * PAD - 28) // 2
    for i, (big, small) in enumerate(items):
        x = PAD + i * (cw + 28)
        d.rounded_rectangle((x, T + 178, x + cw, T + 178 + 150), radius=22, fill=(18, 23, 38), outline=(44, 52, 74), width=2)
        d.text((x + 24, T + 190), big, font=font(B, 52), fill=ORANGE)
        for j, line in enumerate(small.split("\n")):
            d.text((x + 24, T + 258 + j * 30), line, font=font(R, 24), fill=MUTED)
            assert d.textlength(line, font=font(R, 24)) < cw - 40, line
    d.text((PAD, T + 356 if STORY else H - 40), "Postaja IREICA1 · meteorec.si/blog", font=font(R, 24), fill=DIM)
    out = os.path.join(ROOT, "og", f"{post.SLUG}-{'zgodba' if STORY else 'kartica'}-{n}.jpg")
    img.save(out, quality=92)
    print("✓", os.path.relpath(out, ROOT), img.size)


def main():
    S = post.Snap()
    post.build_article(S)                  # varovalke: pade, če trditve ne držijo
    V = variants(S)
    only = int(sys.argv[sys.argv.index("--variant") + 1]) if "--variant" in sys.argv else None
    for n, spec in V.items():
        if only in (None, n):
            render(S, n, spec)


if __name__ == "__main__":
    main()
