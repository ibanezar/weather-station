#!/usr/bin/env python3
"""
tools/generate_slana_gobe_card_variants.py -- štiri kartice 1080×1350 za FB objavo članka
»Ali prva slana konča gobarsko sezono? Šest let podatkov« (isti slog kot kartice »Vrh opažanj gob«):

  1 štiri od štirih -- leta s prvo slano oktobra: prva noč z mrazom in vrh opažanj gob po njej
  2 prvi teden novembra -- padec pod polovico vrha po letih proti prvi slani
  3 letos -- najnižja temperatura 1. 9.–17. 10. po letih; letos še brez ničelne noči
  4 foto -- lastna fotografija gob, tri številke

Številke so iz ISTEGA izračuna kot članek (`generate_slana_gobe_post.build_article` se zažene, zato veljajo iste
varovalke: če podatki trditve ne podpirajo več, kartica ne nastane). Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_slana_gobe_card_variants.py [--out-dir DIR]
"""
import datetime
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_slana_gobe_post as post  # noqa: E402
import generate_vrh_sezone_card_variants as cv  # noqa: E402   (pisave, platno, glava, značka, panel)

ROOT = post.ROOT
W, H, PAD = cv.W, cv.H, cv.PAD
font, text_w, canvas, header, badge, panel = cv.font, cv.text_w, cv.canvas, cv.header, cv.badge, cv.panel
B, R = cv.B, cv.R
WHITE, MUTED, DIM, PANEL, LINE, GREEN, GREY, BAND = cv.WHITE, cv.MUTED, cv.DIM, cv.PANEL, cv.LINE, cv.GREEN, cv.GREY, cv.BAND
CYAN, AMBER = (34, 211, 238), (251, 191, 36)
YEARS, LAST = post.YEARS, post.LAST
PHOTO_FILE = os.path.join(ROOT, "og", "bg", "vrh-sezone-foto.jpg")          # Filipova fotografija (kot pri članku o vrhu sezone)


def footer(d, line1, y=1214):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), "Fotografije gob na iNaturalistu, ne košare in ne napoved najdbe.", font=font(R, 27), fill=DIM)
    d.text((PAD, y + 84), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)


def diamond(d, cx, cy, r, fill, outline=None, width=0):
    d.polygon([(cx, cy - r), (cx + r * 0.8, cy), (cx, cy + r), (cx - r * 0.8, cy)], fill=fill, outline=outline, width=width)


def stats():
    H_, I, wk, soil, _ = post.load()
    post.build_article(H_, I, wk, soil, _)                 # varovalke: pade, če trditve ne držijo
    D = {}
    for y in YEARS:
        peak, drop = post.peak_and_drop(wk, y)
        D[y] = dict(f0=post.first_night(H_, y, 0.0), peak=peak[0], drop=drop, s35=post.soil_cross(soil, y, 3.5))
    last = datetime.date.fromisoformat(max(H_))
    mins = {}
    for y in YEARS + [LAST]:
        cut = datetime.date(y, last.month, last.day).isoformat()
        vals = [(H_[d]["tempLow"], d) for d in H_ if d.startswith(str(y)) and f"{y}-09-01" <= d <= cut and H_[d].get("tempLow") is not None]
        mins[y] = min(vals)
    return D, mins, last


def day_off(d, y=None):                                    # dnevi od 1. 10.
    return (d - datetime.date(d.year, 10, 1)).days


def axis(d, X, gy1, ticks):
    for off, t in ticks:
        d.text((X(off) - text_w(d, t, font(R, 22)) / 2, gy1 + 22), t, font=font(R, 22), fill=DIM)


def v1(S):
    D, mins, last = S
    early = [y for y in YEARS if D[y]["f0"].month == 10]
    img, d = canvas()
    header(img, d, "prva slana in gobe 2020–2025", thumb=False)
    badge(d, "POSTAJA + iNATURALIST")
    d.text((PAD, 268), "Prva slana", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "ni konec sezone.", font=font(B, 88), fill=GREEN)
    d.text((PAD, 480), "4 od 4", font=font(B, 190), fill=WHITE)
    d.text((PAD, 690), "let s prvo noč z 0 °C ali manj že oktobra:", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), "vrh opažanj gob je bil šele po njej", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 130, W - PAD - 60, y0 + 90, y1 - 80
    X = lambda off: gx0 + (gx1 - gx0) * off / 44
    rh = (gy1 - gy0) / len(early)
    lx = PAD + 34
    diamond(d, lx + 12, y0 + 40, 13, CYAN)
    d.text((lx + 34, y0 + 26), "prva noč z mrazom", font=font(R, 24), fill=MUTED)
    lx += 34 + text_w(d, "prva noč z mrazom", font(R, 24)) + 40
    d.ellipse((lx, y0 + 28, lx + 24, y0 + 52), fill=GREEN)
    d.text((lx + 34, y0 + 26), "teden z največ gobami", font=font(R, 24), fill=MUTED)
    for off, t in ((0, "1. 10."), (14, "15. 10."), (31, "1. 11.")):
        d.line((X(off), gy0 - 10, X(off), gy1), fill=LINE, width=1)
    for i, y in enumerate(early):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 34, cy - 15), str(y), font=font(B, 28), fill=WHITE)
        d.line((gx0, cy, gx1, cy), fill=LINE, width=1)
        diamond(d, X(day_off(D[y]["f0"])), cy, 17, CYAN, PANEL, 3)
        px = X(day_off(D[y]["peak"]) + 3)
        d.ellipse((px - 15, cy - 15, px + 15, cy + 15), fill=GREEN, outline=PANEL, width=3)
    axis(d, X, gy1, ((0, "1. 10."), (14, "15. 10."), (31, "1. 11.")))
    footer(d, "Postaja IREICA1 in opažanja gob na iNaturalistu, 2020–2025")
    return img


def v2(S):
    D, mins, last = S
    img, d = canvas()
    header(img, d, "kdaj se val gob umiri", thumb=False)
    badge(d, "POSTAJA + iNATURALIST")
    d.text((PAD, 268), "Val gob se umiri", font=font(B, 82), fill=WHITE)
    d.text((PAD, 360), "v prvem tednu novembra.", font=font(B, 76), fill=GREEN)
    d.text((PAD, 480), "5 od 6", font=font(B, 190), fill=WHITE)
    d.text((PAD, 690), "let: opažanj gob je manj kot polovica vrha", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), "med 4. in 10. novembrom, ne glede na slano", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 130, W - PAD - 50, y0 + 90, y1 - 80
    X = lambda off: gx0 + (gx1 - gx0) * off / 60
    rh = (gy1 - gy0) / len(YEARS)
    lx = PAD + 34
    diamond(d, lx + 12, y0 + 40, 13, CYAN)
    d.text((lx + 34, y0 + 26), "prva noč z mrazom", font=font(R, 24), fill=MUTED)
    lx += 34 + text_w(d, "prva noč z mrazom", font(R, 24)) + 40
    d.ellipse((lx + 1, y0 + 29, lx + 23, y0 + 51), outline=AMBER, width=4)
    d.text((lx + 34, y0 + 26), "pod polovico vrha", font=font(R, 24), fill=MUTED)
    for off in (0, 14, 31, 45, 60):
        d.line((X(off), gy0 - 10, X(off), gy1), fill=LINE, width=1)
    for i, y in enumerate(YEARS):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 34, cy - 15), str(y), font=font(B, 28), fill=WHITE)
        d.line((gx0, cy, gx1, cy), fill=LINE, width=1)
        diamond(d, X(day_off(D[y]["f0"])), cy, 16, CYAN, PANEL, 3)
        dx = X(day_off(D[y]["drop"]) + 3)
        d.ellipse((dx - 15, cy - 15, dx + 15, cy + 15), outline=AMBER, width=5)
    axis(d, X, gy1, ((0, "1. 10."), (14, "15. 10."), (31, "1. 11."), (45, "15. 11."), (60, "30. 11.")))
    n22 = (D[2022]["f0"] - D[2022]["drop"]).days
    footer(d, f"Leta 2022 je padec prišel {n22} dni pred prvo ničelno nočjo ({D[2022]['f0'].day}. {D[2022]['f0'].month}.)")
    return img


def v3(S):
    D, mins, last = S
    img, d = canvas()
    header(img, d, "letošnja jesen", thumb=False)
    badge(d, "POSTAJA IREICA1")
    d.text((PAD, 268), "Letos prve", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "slane še ni.", font=font(B, 88), fill=GREEN)
    t26 = mins[LAST][0]
    d.text((PAD, 480), f"{post.num(t26)} °C", font=font(B, 150), fill=WHITE)
    d.text((PAD, 660), f"najnižja temperatura od 1. 9. do {last.day}. {last.month}.", font=font(R, 34), fill=MUTED)
    d.text((PAD, 706), f"na postaji v Rečici ({mins[LAST][1][8:].lstrip('0')}. {int(mins[LAST][1][5:7])}.)", font=font(R, 34), fill=MUTED)
    y0, y1 = 770, 1190
    panel(d, y0, y1)
    yrs = YEARS + [LAST]
    lo, hi = -4, 4
    gx0, gx1, gy0, gy1 = PAD + 130, W - PAD - 110, y0 + 40, y1 - 70
    X = lambda t: gx0 + (gx1 - gx0) * (t - lo) / (hi - lo)
    rh = (gy1 - gy0) / len(yrs)
    for t in (-4, -2, 0, 2, 4):
        d.line((X(t), gy0 - 6, X(t), gy1), fill=LINE if t else (120, 130, 150), width=1 if t else 3)
        s = f"{t}".replace("-", "–")
        d.text((X(t) - text_w(d, s, font(R, 22)) / 2, gy1 + 16), s, font=font(R, 22), fill=DIM)
    for i, y in enumerate(yrs):
        cy = gy0 + rh * i + rh / 2
        v = mins[y][0]
        col = GREEN if y == LAST else (CYAN if v <= 0 else GREY)
        d.text((PAD + 34, cy - 15), str(y), font=font(B, 28), fill=WHITE)
        x0, x1 = sorted((X(0), X(v)))
        d.rounded_rectangle((x0, cy - 15, max(x1, x0 + 4), cy + 15), radius=8, fill=col)
        lab = f"{post.num(v)} °C".replace("-", "–")
        d.text((max(x1, X(0)) + 12 if v >= 0 else x0 - 12 - text_w(d, lab, font(B, 24)), cy - 14), lab, font=font(B, 24), fill=WHITE)
    footer(d, f"Modro: leta z ničelno nočjo do {last.day}. {last.month}.")
    return img


def v4(S):
    D, mins, last = S
    img, d = canvas(photo=True, blur=16)
    header(img, d, "prva slana in gobe", thumb=False)
    badge(d, "POSTAJA + iNATURALIST")
    f = font(B, 88)
    d.text((PAD, 268), "Slana ni", font=f, fill=WHITE)
    d.text((PAD, 372), "konec gob.", font=f, fill=GREEN)
    s35 = min((D[y]["s35"] for y in YEARS), key=post.md)
    rows = [("4 od 4", ["let z oktobrsko slano:", "vrh opažanj gob je bil po njej"]),
            ("4.–10. 11.", ["teden, ko opažanj gob pade pod", "polovico vrha (5 od 6 let)"]),
            (f"{s35.day}. {s35.month}.", ["najzgodneje, ko so tla padla", "pod 3,5 °C (jurček)"])]
    ph = Image.open(PHOTO_FILE).convert("RGB").resize((260, 390), Image.LANCZOS)
    mask = Image.new("L", ph.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=22, fill=255)
    img.paste(ph, (W - PAD - ph.width, 620), mask)
    y = 580
    for big, lab in rows:
        d.ellipse((PAD, y + 20, PAD + 34, y + 54), fill=GREEN)
        d.text((PAD + 64, y), big, font=font(B, 76), fill=WHITE)
        for k, ln in enumerate(lab):
            d.text((PAD + 64, y + 88 + 36 * k), ln, font=font(R, 28), fill=MUTED)
        y += 190
    footer(d, "Postaja IREICA1, iNaturalist, Open-Meteo, 2020–2025")
    d.text((W - PAD - 260, 1020), "Foto: Filip Eremita", font=font(R, 22), fill=MUTED)
    return img


def main():
    out = sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else os.path.join(ROOT, "og")
    os.makedirs(out, exist_ok=True)
    S = stats()
    for n, fn in enumerate((v1, v2, v3, v4), 1):
        p = os.path.join(out, f"{post.SLUG}-kartica-{n}.jpg")
        fn(S).save(p, quality=92)
        print("✓", p)


if __name__ == "__main__":
    main()
