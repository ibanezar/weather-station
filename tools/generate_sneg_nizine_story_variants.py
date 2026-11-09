#!/usr/bin/env python3
"""
tools/generate_sneg_nizine_story_variants.py -- tri kartice 1080×1920 (9:16) za FB/IG ZGODBE k članku
»Sneg v nižinah: četrtek še dež, odločitev v noči na soboto« (9. 11. 2026). Zgodbe nimajo podpisa: vse je na sliki.

Zasnovane za ustavljanje drsenja: ena misel, ogromna tipografija, močan kontrast. Pomembno je med y = 250 in y = 1600
(zgoraj in spodaj zgodbo prekrije vmesnik FB/IG).

  1 foto    -- »BO V NIŽINAH SNEG?« čez fotografijo sneženja (Rečica, 5. 1. 2026), 16 % in 59 %
  2 bloki   -- barvni bloki dan za dnem: ČETRTEK dež, PETEK dež, SOBOTA sneg? (16 % / 59 %)
  3 lestev  -- delež članov z vsaj 1 cm snega po višinah 366–1200 m, vprašanje »Na kateri višini živite?«

Številke so iz ISTEGA posnetka kot članek (stats() iz generate_sneg_nizine_card_variants zažene build_article, zato veljajo
iste varovalke: posnetek mora biti današnji in zgodba mora še držati). Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_sneg_nizine_story_variants.py [--out-dir DIR]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_sneg_nizine_card_variants as cards  # noqa: E402

post = cards.post
ROOT = cards.ROOT
W, H, PAD = 1080, 1920, 70
font, text_w = cards.font, cards.text_w
B, R = cards.B, cards.R
BG, WHITE, MUTED, DIM, LINE = cards.BG, cards.WHITE, cards.MUTED, cards.DIM, cards.LINE
CYAN, AMBER, ICE = cards.CYAN, cards.AMBER, cards.ICE
SNOW, MIX, RAIN = cards.SNOW, cards.MIX, cards.RAIN
INK = (10, 14, 28)


def fit(d, t, name, max_w, start, lo=24):
    """Največja velikost pisave (od `start` navzdol), pri kateri se besedilo še prilega v max_w."""
    s = start
    while s > lo and text_w(d, t, font(name, s)) > max_w:
        s -= 2
    return font(name, s), s


def badge(d, text, y=250, fill=CYAN, ink=(2, 24, 32)):
    f = font(B, 28)
    w = text_w(d, text, f) + 48
    d.rounded_rectangle((PAD, y, PAD + w, y + 56), radius=28, fill=fill)
    d.text((PAD + 24, y + 11), text, font=f, fill=ink)


def brand(d, y=1640, light=True):
    col = WHITE if light else INK
    sub = MUTED if light else (60, 70, 92)
    d.text((PAD, y), "METEOREC", font=font(B, 40), fill=col)
    d.text((PAD + text_w(d, "METEOREC", font(B, 40)) + 26, y + 8), "meteorec.si", font=font(R, 30), fill=sub)
    d.text((PAD, y + 56), "143 članov ansamblov (Open-Meteo). Modelska ocena, ni uradno opozorilo.", font=font(R, 24), fill=sub)


def stroke_text(d, xy, t, f, fill, sw=6, sc=(4, 6, 14)):
    d.text(xy, t, font=f, fill=fill, stroke_width=sw, stroke_fill=sc)


# ───────────────────────── zgodba 1: foto ─────────────────────────

def s1(S):
    bg = Image.open(cards.PHOTO).convert("RGB")
    assert bg.size == (1080, 1920), bg.size
    img = bg.filter(ImageFilter.GaussianBlur(0.8))
    ov = Image.new("RGBA", (W, H))
    od = ImageDraw.Draw(ov)
    for y in range(H):
        t = y / H
        if t < 0.46:
            a = 215 - 120 * (t / 0.46)
        else:
            a = 95 + 150 * ((t - 0.46) / 0.54) ** 1.15
        od.line((0, y, W, y), fill=(5, 8, 18, int(min(248, a))))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)
    badge(d, "NAPOVED, NE MERITEV")
    f, _ = fit(d, "BO V NIŽINAH", B, W - 2 * PAD, 110)
    stroke_text(d, (PAD, 352), "BO V NIŽINAH", f, WHITE, 5)
    f, sz = fit(d, "SNEG?", B, W - 2 * PAD, 420)
    stroke_text(d, (PAD - 6, 440), "SNEG?", f, WHITE, 8)
    y = 440 + sz + 40
    d.rounded_rectangle((PAD, y, W - PAD, y + 118), radius=26, fill=CYAN)
    f, _ = fit(d, "ČETRTEK ŠE DEŽ.", B, W - 2 * PAD - 60, 74)
    d.text((PAD + 32, y + 22), "ČETRTEK ŠE DEŽ.", font=f, fill=(2, 24, 32))
    stroke_text(d, (PAD, y + 150), "Odloča se v noči na soboto.", font(B, 46), WHITE, 4)
    # številki
    y0 = 1190
    pn = Image.new("RGBA", (W - 2 * PAD, 400), (8, 12, 26, 232))
    m = Image.new("L", pn.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, pn.width - 1, pn.height - 1), radius=32, fill=255)
    img.paste(pn, (PAD, y0), m)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((PAD, y0, W - PAD, y0 + 400), radius=32, outline=LINE, width=2)
    colw = (W - 2 * PAD) // 2
    for i, (big, col, l1, l2) in enumerate(((f"{S['c1']} %", WHITE, "dno doline", "366 m, Rečica"),
                                           (f"{S['c1_900']} %", ICE, "na 900 m", "višina Črnivca"))):
        x = PAD + 40 + i * colw
        d.text((x, y0 + 24), big, font=font(B, 168), fill=col)
        d.text((x + 4, y0 + 222), l1, font=font(B, 40), fill=WHITE)
        d.text((x + 4, y0 + 274), l2, font=font(R, 32), fill=MUTED)
    d.line((PAD + colw, y0 + 44, PAD + colw, y0 + 330), fill=LINE, width=2)
    d.text((PAD + 44, y0 + 340), "članov napove vsaj 1 cm snega do ponedeljka", font=font(R, 28), fill=MUTED)
    brand(d, 1650)
    d.text((W - PAD - text_w(d, "foto: Rečica, 5. 1. 2026 (arhiv)", font(R, 22)), 1855), "foto: Rečica, 5. 1. 2026 (arhiv)", font=font(R, 22), fill=DIM)
    return img


# ───────────────────────── zgodba 2: bloki ─────────────────────────

def block(img, y0, h, fill, day, word, ink, lines, accent=None, line_cols=None, max_size=210):
    """Barvni blok: dan zgoraj levo, ogromna beseda na osnovni črti, vrstice podnapisa pod njo."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((PAD, y0, W - PAD, y0 + h), radius=36, fill=fill)
    d.text((PAD + 44, y0 + 34), day, font=font(B, 38), fill=accent or ink)
    f, sz = fit(d, word, B, W - 2 * PAD - 88, max_size)
    base = y0 + h - 40 - 46 * len(lines) - 12
    d.text((PAD + 40, base), word, font=f, fill=ink, anchor="ls")
    for i, (t, ff) in enumerate(lines):
        d.text((PAD + 46, base + 18 + 46 * i), t, font=ff, fill=(line_cols or [ink] * len(lines))[i])
    return d


def s2(S):
    img = Image.new("RGB", (W, H), BG)
    for y in range(H):                                              # rahel navpični prelivi
        t = y / H
        ImageDraw.Draw(img).line((0, y, W, y), fill=(int(5 + 6 * t), int(6 + 14 * t), int(14 + 30 * t)))
    d = ImageDraw.Draw(img)
    badge(d, "NAPOVED, NE MERITEV")
    soft = (222, 234, 255)
    y = 336
    block(img, y, 372, RAIN, "ČETRTEK 12. 11.", "DEŽ", WHITE, [("še toplo: nič snega", font(R, 38))], accent=(200, 220, 255), line_cols=[soft])
    y += 372 + 22
    block(img, y, 372, (28, 70, 150), "PETEK 13. 11.", "DEŽ", WHITE, [(f"okoli {S['mm']} mm v dveh dneh", font(R, 38))], accent=(190, 212, 255), line_cols=[soft])
    y += 372 + 22
    h3 = 1560 - y
    block(img, y, h3, SNOW, "SOBOTA 14. 11.", "SNEG?", INK,
          [("odloča se v noči na soboto", font(B, 40)), (f"{S['c1']} % v dolini, {S['c1_900']} % na 900 m", font(R, 38))],
          accent=(30, 70, 120), line_cols=[INK, (40, 52, 78)], max_size=330)
    d = ImageDraw.Draw(img)
    brand(d, 1640)
    return img


# ───────────────────────── zgodba 3: lestev ─────────────────────────

def s3(S):
    img = Image.new("RGB", (W, H), BG)
    for y in range(H):
        t = y / H
        ImageDraw.Draw(img).line((0, y, W, y), fill=(int(5 + 4 * t), int(8 + 18 * t), int(20 + 44 * t)))
    d = ImageDraw.Draw(img)
    badge(d, "NAPOVED, NE MERITEV")
    f, sz = fit(d, "VIŠINA ODLOČA.", B, W - 2 * PAD, 130)
    stroke_text(d, (PAD, 340), "VIŠINA ODLOČA.", f, WHITE, 0)
    d.text((PAD, 340 + sz + 22), "delež članov z vsaj 1 cm snega do ponedeljka", font=font(R, 34), fill=MUTED)
    levels = [(1200, ""), (900, "kot Črnivec"), (700, ""), (500, ""), (366, "Rečica")]
    vals = {e: S["d"]["pooled"][str(e)]["all"]["cm1"] for e, _ in levels}
    y0, rh, gap = 560, 168, 18
    gx0, gx1 = PAD + 270, W - PAD
    for i, (e, note) in enumerate(levels):
        y = y0 + i * (rh + gap)
        v = vals[e]
        low = e == 366
        d.rounded_rectangle((gx0, y, gx1, y + rh), radius=30, fill=(18, 26, 48))
        wfill = max(gx0 + 110, gx0 + (gx1 - gx0) * v / 100)
        d.rounded_rectangle((gx0, y, wfill, y + rh), radius=30, fill=CYAN if low else SNOW)
        d.text((PAD, y + 22), f"{e} m", font=font(B, 58), fill=WHITE)
        if note:
            d.text((PAD + 2, y + 96), note, font=font(R, 32), fill=CYAN if low else MUTED)
        vt = f"{v} %"
        ft, _ = fit(d, vt, B, 220, 112)
        tw = text_w(d, vt, ft)
        if wfill - gx0 >= tw + 60:                                   # dovolj dolg stolpec: številka znotraj, temna
            d.text((wfill - 28 - tw, y + 18), vt, font=ft, fill=(2, 24, 32) if low else INK)
        else:                                                         # kratek stolpec: številka desno od njega, svetla
            d.text((wfill + 26, y + 18), vt, font=ft, fill=CYAN if low else WHITE)
    yq = y0 + 5 * (rh + gap) + 20
    d.text((PAD, yq), "Na kateri višini živite?", font=font(B, 62), fill=CYAN)
    brand(d, 1672)
    return img


def main():
    out = sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else os.path.join(ROOT, "og")
    os.makedirs(out, exist_ok=True)
    S = cards.stats()
    for n, fn in enumerate((s1, s2, s3), 1):
        p = os.path.join(out, f"{post.SLUG}-zgodba-{n}.jpg")
        fn(S).save(p, quality=93)
        print("✓", p)


if __name__ == "__main__":
    main()
