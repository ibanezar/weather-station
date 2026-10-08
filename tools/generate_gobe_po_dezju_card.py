#!/usr/bin/env python3
"""
tools/generate_gobe_po_dezju_card.py — kartica za FB/IG objavo članka »Gobe po dežju 8.–10. oktobra«.

Pokončna kartica 1080×1350 (isti slog kot nevihtna karta: temna podlaga, logotip, Liberation Sans).
Številke (okna rasti po skupinah, dež) so iz ISTEGA izračuna kot članek (`generate_gobe_po_dezju_post`),
zato se kartica in stran ne moreta razhajati. Piše og/<slug>-kartica.jpg. Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_gobe_po_dezju_card.py [--cache FILE]
"""
import datetime
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_gobe_po_dezju_post as post  # noqa: E402

ROOT = post.ROOT
W, H = 1080, 1350
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
BG = (5, 6, 14)
WHITE = (255, 255, 255)
MUTED = (200, 210, 228)
DIM = (150, 160, 182)
PANEL = (16, 20, 34)
LINE = (44, 52, 74)
GREEN = (52, 211, 153)


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def text_w(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    D = post.build_data(cache)
    eco, ev, dry = D["eco"], D["ev"], D["R"]["dry"]
    rng, d1, d3 = post.rng, D["d1"], D["d3"]

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pad = 70
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((84, 84), Image.LANCZOS)
    img.paste(logo, (pad, 60), logo)
    d.text((pad + 106, 60), "METEOREC", font=font("LiberationSans-Bold.ttf", 40), fill=WHITE)
    d.text((pad + 108, 106), f"gobe po dežju {rng(d1, d3)}", font=font("LiberationSans-Regular.ttf", 26), fill=DIM)

    f_badge = font("LiberationSans-Bold.ttf", 24)
    badge = "GOBARSKI MODEL"
    bw = text_w(d, badge, f_badge) + 40
    d.rounded_rectangle((pad, 196, pad + bw, 196 + 46), radius=23, fill=GREEN)
    d.text((pad + 20, 205), badge, font=f_badge, fill=(4, 20, 14))

    f_title = font("LiberationSans-Bold.ttf", 84)
    d.text((pad, 268), "Najprej dež,", font=f_title, fill=WHITE)
    d.text((pad, 360), "potem gobe.", font=f_title, fill=GREEN)

    mik = eco["mikorizna"]
    big = rng(*mik["win"])
    d.text((pad, 500), big, font=font("LiberationSans-Bold.ttf", 118), fill=WHITE)
    d.text((pad, 640), "okno za jurčke, lisičke in rumene ježke", font=font("LiberationSans-Regular.ttf", 34), fill=MUTED)

    # časovnica: panel z rain-pasom in tremi pasovi
    px0, py0, px1, py1 = pad, 722, W - pad, 1180
    d.rounded_rectangle((px0, py0, px1, py1), radius=26, fill=PANEL, outline=LINE, width=2)
    span = D["P"]  # noqa: F841 (izvor je isti kot članek)
    first = datetime.date.fromisoformat(d1)
    last = datetime.date.fromisoformat(max(eco[e]["win"][1] for e in post.ECO_ORDER)) + datetime.timedelta(days=1)
    n = (last - first).days + 1
    gx0, gx1 = px0 + 34, px1 - 34
    gy0, gy1 = py0 + 96, py1 - 70

    def X(day):
        return gx0 + (day - first).days / n * (gx1 - gx0)

    r0 = X(datetime.date.fromisoformat(d1))
    r1 = X(datetime.date.fromisoformat(d3) + datetime.timedelta(days=1))
    d.rectangle((r0, gy0 - 52, r1, gy1 + 8), fill=(30, 38, 58))
    f_small = font("LiberationSans-Regular.ttf", 22)
    d.text((r0 + 8, gy0 - 46), "dež", font=f_small, fill=MUTED)

    f_lane = font("LiberationSans-Bold.ttf", 28)
    f_win = font("LiberationSans-Regular.ttf", 26)
    lane_h = (gy1 - gy0) / 3
    for k, e in enumerate(post.ECO_ORDER):
        c = eco[e]
        y = gy0 + k * lane_h
        col = hexrgb(post.COLORS[e])
        a = datetime.date.fromisoformat(c["win"][0])
        b = datetime.date.fromisoformat(c["win"][1]) + datetime.timedelta(days=1)
        d.text((gx0, y + 4), post.ECO_NAME[e], font=f_lane, fill=WHITE)
        label = rng(*c["win"])
        d.text((gx1 - text_w(d, label, f_win), y + 6), label, font=f_win, fill=MUTED)
        d.rounded_rectangle((X(a), y + 48, X(b), y + 48 + 34), radius=12, fill=col)

    for i in range(0, n, 3):
        day = first + datetime.timedelta(days=i)
        t = f"{day.day}. {day.month}."
        x = X(day) + (gx1 - gx0) / n / 2
        d.text((x - text_w(d, t, f_small) / 2, gy1 + 22), t, font=f_small, fill=DIM)

    # noga
    f_foot = font("LiberationSans-Regular.ttf", 27)
    f_foot_b = font("LiberationSans-Bold.ttf", 30)
    d.text((pad, 1210), f"Po {dry['days']} suhih dneh: dež {post.mm(ev['p50'])} mm (ansambel), ARSO {post.mm(ev['arso'])} mm",
           font=f_foot_b, fill=WHITE)
    d.text((pad, 1256), "Modelova ocena ugodnosti razmer, ni obljuba najdbe.", font=f_foot, fill=DIM)
    d.text((pad, 1294), "Grafi, pragovi dežja po vrstah in višina: meteorec.si/blog", font=f_foot, fill=DIM)

    out = os.path.join(ROOT, "og", f"{post.SLUG}-kartica.jpg")
    img.save(out, quality=92)
    print("✓", out)


if __name__ == "__main__":
    main()
