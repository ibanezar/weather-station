#!/usr/bin/env python3
"""
tools/generate_sneg_nizine_card_variants.py -- tri kartice 1080×1350 za FB objavo članka
»Sneg v nižinah: četrtek še dež, odločitev v noči na soboto« (9. 11. 2026; isti slog kot kartice »16 noči pod 5 °C«):

  1 foto     -- fotografija sneženja v Rečici (5. 1. 2026), »Bo v nižinah sneg?«, 16 % v dolini in 59 % na 900 m   (besedilo A)
  2 modeli   -- ansambli se ne strinjajo: delež članov z vsaj 1 cm snega v dolini po ansamblih (ECMWF 29 %, ICON 2 %)  (besedilo B)
  3 mraz     -- ura za uro v Rečici (temperatura, dež/sneg) in 50 % članov z 0 °C ali manj v nedeljo zjutraj      (besedilo C)

Številke so iz ISTEGA posnetka in izračuna kot članek (`generate_sneg_nizine_post.build_article` se zažene, zato veljajo iste
varovalke: posnetek mora biti današnji in zgodba mora še držati, sicer kartica ne nastane). Na FB/IG ne objavlja.
Notranjih meritev ne uporablja.

Usage:
    python3 tools/generate_sneg_nizine_card_variants.py [--out-dir DIR]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_sneg_nizine_post as post  # noqa: E402
import generate_vrh_sezone_card_variants as cv  # noqa: E402   (pisave, glava, plošča)

ROOT = post.ROOT
W, H, PAD = cv.W, cv.H, cv.PAD
font, text_w, header, panel = cv.font, cv.text_w, cv.header, cv.panel
B, R = cv.B, cv.R
BG, WHITE, MUTED, DIM, PANEL, LINE, GREY = cv.BG, cv.WHITE, cv.MUTED, cv.DIM, cv.PANEL, cv.LINE, cv.GREY
CYAN, AMBER, ICE = (34, 211, 238), (251, 191, 36), (147, 197, 253)
SNOW, MIX, RAIN = (241, 245, 249), (196, 181, 253), (47, 111, 214)
PHOTO = os.path.join(ROOT, "og", "bg", "sneg-recica-2026-01-05.jpg")
SYS_RGB = {"ecmwf_ifs025": (57, 135, 229), "icon_seamless": (213, 81, 129), "gfs025": (144, 133, 233), "gem_global": (25, 158, 112)}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def badge(d, text, y=196):
    f = font(B, 24)
    w = text_w(d, text, f) + 40
    d.rounded_rectangle((PAD, y, PAD + w, y + 46), radius=23, fill=CYAN)
    d.text((PAD + 20, y + 9), text, font=f, fill=(2, 24, 32))


def footer(d, line1, line2="143 članov ansamblov (Open-Meteo). Modelska ocena, ni uradno opozorilo.", y=1214):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), line2, font=font(R, 27), fill=DIM)
    d.text((PAD, y + 84), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)


def stats():
    S = post.Snap()
    post.build_article(S)                                   # varovalke: pade, če trditve ne držijo
    d = S.d
    pooled = d["pooled"]
    out = {"S": S, "d": d}
    out["mm"] = pooled["366"]["thufri"]["mm50"]
    out["c1"] = pooled["366"]["all"]["cm1"]
    out["c1_900"] = pooled["900"]["all"]["cm1"]
    out["frost"] = pooled["366"]["sun"]["frost"]
    out["c1_by"] = {sid: d["systems"]["366"][sid]["all"]["cm1"] for sid in S.ids}
    out["n_by"] = {sid: d["systems"]["366"][sid]["all"]["n"] for sid in S.ids}
    out["hour"] = d["hourly"]["366"]["all"]
    return out


# ───────────────────────── kartica 1: foto ─────────────────────────

def v1(S):
    bg = Image.open(PHOTO).convert("RGB")
    s = W / bg.width
    bg = bg.resize((W, int(bg.height * s)), Image.LANCZOS)
    top = 250
    img = bg.crop((0, top, W, top + H)).filter(ImageFilter.GaussianBlur(1.2))
    ov = Image.new("RGBA", (W, H))
    od = ImageDraw.Draw(ov)
    for y in range(H):
        t = y / H
        a = 225 - 175 * min(1, t / 0.42) if t < 0.42 else 50 + 190 * ((t - 0.42) / 0.58) ** 1.3
        od.line((0, y, W, y), fill=(5, 8, 18, int(min(245, a))))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)
    header(img, d, "sneg v nižinah, 12.–16. november", thumb=False)
    badge(d, "NAPOVED, NE MERITEV")
    d.text((PAD, 268), "Bo v nižinah", font=font(B, 98), fill=WHITE)
    d.text((PAD, 378), "sneg?", font=font(B, 98), fill=WHITE)
    d.text((PAD, 508), "Četrtek še dež.", font=font(B, 50), fill=CYAN)
    d.text((PAD, 574), "Odloča se v noči na soboto.", font=font(R, 40), fill=MUTED)
    # spodnja plošča z dvema številkama
    y0, y1 = 800, 1190
    pn = Image.new("RGBA", (W - 2 * PAD, y1 - y0), (10, 14, 28, 222))
    m = Image.new("L", pn.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, pn.width - 1, pn.height - 1), radius=26, fill=255)
    img.paste(pn, (PAD, y0), m)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((PAD, y0, W - PAD, y1), radius=26, outline=LINE, width=2)
    colw = (W - 2 * PAD) // 2
    for i, (big, col, l1, l2) in enumerate((
            (f"{S['c1']} %", WHITE, "dno doline", "366 m, Rečica"),
            (f"{S['c1_900']} %", ICE, "na 900 m", "višina Črnivca"))):
        x = PAD + 34 + i * colw
        d.text((x, y0 + 34), big, font=font(B, 156), fill=col)
        d.text((x + 4, y0 + 218), l1, font=font(B, 34), fill=WHITE)
        d.text((x + 4, y0 + 262), l2, font=font(R, 30), fill=MUTED)
    d.line((PAD + colw, y0 + 40, PAD + colw, y1 - 120), fill=LINE, width=2)
    d.text((PAD + 38, y0 + 318), "članov ansamblov napove vsaj 1 cm snega do ponedeljka", font=font(R, 28), fill=MUTED)
    footer(d, f"Dež v četrtek in petek: okoli {S['mm']} mm. Sneg pride ob koncu padavin.")
    d.text((W - PAD - text_w(d, "foto: Rečica, 5. 1. 2026 (arhiv)", font(R, 22)), 1304), "foto: Rečica, 5. 1. 2026 (arhiv)", font=font(R, 22), fill=DIM)
    return img


# ───────────────────────── kartica 2: modeli ─────────────────────────

def v2(S):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(img, d, "ansambli se ne strinjajo", thumb=False)
    badge(d, "NAPOVED, NE MERITEV")
    by = S["c1_by"]
    order = sorted(by, key=lambda k: -by[k])
    hi, lo = order[0], order[-1]
    d.text((PAD, 268), "Ali bo v dolini sneg?", font=font(B, 80), fill=WHITE)
    d.text((PAD, 366), "Odvisno, koga vprašate.", font=font(B, 66), fill=CYAN)
    d.text((PAD, 470), f"{by[hi]} % : {by[lo]} %", font=font(B, 176), fill=WHITE)
    d.text((PAD, 690), f"vsaj 1 cm snega v dolini do ponedeljka ({post.SYS_NAME[hi].split()[0]} proti {post.SYS_NAME[lo].split('-')[0]})", font=font(R, 30), fill=MUTED)
    d.text((PAD, 732), "Razlika: kdaj pride mraz in koliko padavin še ostane za njim", font=font(R, 30), fill=MUTED)
    y0, y1 = 800, 1190
    panel(d, y0, y1)
    gx0, gx1 = PAD + 270, W - PAD - 110
    vmax = 50.0
    X = lambda v: gx0 + (gx1 - gx0) * v / vmax
    gy0, gy1 = y0 + 70, y1 - 66
    for t in (0, 10, 20, 30, 40, 50):
        d.line((X(t), gy0 - 14, X(t), gy1), fill=LINE, width=1)
        d.text((X(t) - text_w(d, str(t), font(R, 22)) / 2, gy1 + 12), str(t) + (" %" if t == 50 else ""), font=font(R, 22), fill=DIM)
    rh = (gy1 - gy0) / len(order)
    for i, sid in enumerate(order):
        cy = gy0 + rh * i + rh / 2
        v = by[sid]
        d.text((PAD + 30, cy - 28), post.SYS_NAME[sid], font=font(B, 30), fill=WHITE)
        d.text((PAD + 30, cy + 6), f"{S['n_by'][sid]} članov", font=font(R, 22), fill=DIM)
        d.rounded_rectangle((gx0, cy - 20, max(X(v), gx0 + 6), cy + 20), radius=10, fill=SYS_RGB[sid])
        d.text((X(v) + 14, cy - 18), f"{v} %", font=font(B, 30), fill=WHITE)
    # skupni delež
    xa = X(S["c1"])
    for yy in range(int(gy0 - 14), int(gy1), 14):
        d.line((xa, yy, xa, yy + 7), fill=SNOW, width=3)
    lab = f"vsi {S['c1']} %"
    d.text((xa + 8, y0 + 20), lab, font=font(B, 24), fill=SNOW)
    footer(d, "Delež članov z vsaj 1 cm snega, Rečica, do ponedeljka")
    return img


# ───────────────────────── kartica 3: mraz ─────────────────────────

def hourly_chart(S, pw, ph):
    """Ura za uro: temperatura (mediana in razpon) in delež članov s snegom / dežjem s snegom / dežjem. Nariše se v 2× in pomanjša."""
    k = 2
    img = Image.new("RGBA", (pw * k, ph * k), PANEL + (255,))
    d = ImageDraw.Draw(img)
    r = S["hour"]
    n = S["S"].n
    L, R_, yT, hT, yB, hB = 64, 22, 64, 148, 240, 70
    X = lambda h: (L + (h + 0.5) * (pw - L - R_) / n) * k
    cw = (pw - L - R_) / n
    lo = (int(min(min(r["t10"]), -1) // 4)) * 4
    hi = -(-int(max(r["t90"]) + 1) // 4) * 4
    Y = lambda t: (yT + hT * (hi - t) / (hi - lo)) * k
    S0 = S["S"]
    h42 = next(h for h in range(n) if S0.hr(h).weekday() == 4 and S0.hr(h).hour == 18)
    h56 = next(h for h in range(n) if S0.hr(h).weekday() == 5 and S0.hr(h).hour == 8)
    d.rectangle((X(h42) - cw * k / 2, (yT - 8) * k, X(h56) + cw * k / 2, (yB + hB) * k), fill=(30, 52, 86, 255))
    # mreža temperature
    step = 4 if hi - lo <= 24 else 8
    for t in range(lo, hi + 1, step):
        d.line((L * k, Y(t), (pw - R_) * k, Y(t)), fill=(130, 140, 160, 255) if t == 0 else LINE + (255,), width=(3 if t == 0 else 1) * k)
        s = str(t).replace("-", "–")
        d.text(((L - 10) * k - text_w(d, s, font(R, 22 * k)), Y(t) - 13 * k), s, font=font(R, 22 * k), fill=DIM if t else WHITE)
    # pas in mediana
    up = [(X(h), Y(r["t90"][h])) for h in range(n)]
    dn = [(X(h), Y(r["t10"][h])) for h in range(n - 1, -1, -1)]
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).polygon(up + dn, fill=AMBER + (64,))
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img)
    d.line([(X(h), Y(r["t50"][h])) for h in range(n)], fill=AMBER, width=5 * k, joint="curve")
    # stolpci
    base = (yB + hB) * k
    d.line((L * k, base, (pw - R_) * k, base), fill=(110, 120, 140, 255), width=k)
    for h in range(n):
        x0 = (L + h * cw) * k
        y = base
        for key, col in (("snow", SNOW), ("mix", MIX), ("rain", RAIN)):
            v = (r[key][h] or 0) / 100 * hB * k
            if v > 0.4:
                d.rectangle((x0, y - v, x0 + cw * k + 0.6, y), fill=col)
                y -= v
    # dnevi
    for dd in range(0, n + 1, 24):
        x = (L + dd * cw) * k
        d.line((x, 40 * k, x, base), fill=(120, 130, 150, 120), width=k)
        if dd < n:
            t = S0.hr(dd)
            lab = f"{post._DAN_SH[t.weekday()]} {t.day}."
            d.text(((L + (dd + 12) * cw) * k - text_w(d, lab, font(B, 24 * k)) / 2, 8 * k), lab, font=font(B, 24 * k), fill=WHITE)
    lab = "noč na soboto"
    d.text((X((h42 + h56) / 2) - text_w(d, lab, font(R, 21 * k)) / 2, 40 * k), lab, font=font(R, 21 * k), fill=ICE)
    # legenda
    lx = L * k
    ly = (yB + hB + 22) * k
    for lab, col in (("sneg", SNOW), ("dež s snegom", MIX), ("dež", RAIN), ("temperatura (mediana, razpon)", AMBER)):
        d.rounded_rectangle((lx, ly + 3 * k, lx + 18 * k, ly + 21 * k), radius=4 * k, fill=col)
        d.text((lx + 26 * k, ly), lab, font=font(R, 22 * k), fill=MUTED)
        lx += (26 + 22) * k + text_w(d, lab, font(R, 22 * k))
    return img.resize((pw, ph), Image.LANCZOS).convert("RGB")


def v3(S):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(img, d, "ura za uro, Rečica 366 m", thumb=False)
    badge(d, "NAPOVED, NE MERITEV")
    d.text((PAD, 268), "Če sneg ne pride,", font=font(B, 88), fill=WHITE)
    d.text((PAD, 366), "pride mraz.", font=font(B, 88), fill=CYAN)
    d.text((PAD, 480), f"{S['frost']} %", font=font(B, 190), fill=WHITE)
    d.text((PAD, 690), "članov ansamblov: v nedeljo zjutraj v dolini", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), "0 °C ali manj, na mokrih cestah poledica", font=font(R, 34), fill=MUTED)
    y0, y1 = 800, 1190
    panel(d, y0, y1)
    ch = hourly_chart(S, W - 2 * PAD - 8, y1 - y0 - 16)
    img.paste(ch, (PAD + 4, y0 + 8))
    d = ImageDraw.Draw(img)
    footer(d, "Četrtek in petek dež, od sobote hladneje (12.–16. 11.)")
    return img


def main():
    out = sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else os.path.join(ROOT, "og")
    os.makedirs(out, exist_ok=True)
    S = stats()
    for n, fn in enumerate((v1, v2, v3), 1):
        p = os.path.join(out, f"{post.SLUG}-kartica-{n}.jpg")
        fn(S).save(p, quality=92)
        print("✓", p)


if __name__ == "__main__":
    main()
