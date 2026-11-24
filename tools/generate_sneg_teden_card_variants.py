#!/usr/bin/env python3
"""
tools/generate_sneg_teden_card_variants.py -- štiri kartice 1080×1350 za FB/IG objavo članka
»Sneg prihodnji teden: v dolini kaže na sredo in četrtek« (21. 11. 2026; isti slog kot »16 noči pod 5 °C«):

  1 91 %        -- delež članov ansamblov z vsaj 1 cm novega snega med sredo in četrtkom + dnevni stolpci
  2 sre 15.00   -- mediana ure prvega snega v Rečici + ura za uro (sneg, dež s snegom, dež)
  3 12 cm       -- mediana novega snega po višinah (366, 700, 1000, 1400 m) z razponom 10.–90. percentila
  4 2. 12.      -- prvi sneg ≥ 1 cm v Gornjem Gradu po zimah (ARSO) in napovedani termin

Številke so iz ISTEGA izračuna kot članek (`generate_sneg_teden_post.build_article` se zažene, zato veljajo iste
varovalke: če posnetek ni današnji ali napoved ne podpira več trditev, kartica ne nastane).
Na FB/IG ne objavlja. Notranjih meritev ne uporablja.

Usage:
    python3 tools/generate_sneg_teden_card_variants.py [--out-dir DIR]
"""
import datetime
import os
import sys

from PIL import Image  # noqa: F401  (cv uporablja isti paket; uvoz preveri, da je nameščen)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_sneg_teden_post as post  # noqa: E402
import generate_vrh_sezone_card_variants as cv  # noqa: E402   (pisave, platno, glava, panel)

ROOT = post.ROOT
W, H, PAD = cv.W, cv.H, cv.PAD
font, text_w, canvas, header, panel = cv.font, cv.text_w, cv.canvas, cv.header, cv.panel
B, R = cv.B, cv.R
WHITE, MUTED, DIM, PANEL, LINE, GREY = cv.WHITE, cv.MUTED, cv.DIM, cv.PANEL, cv.LINE, cv.GREY
SNOW, ICE, MIXC, RAINC, AMBER = (57, 135, 229), (127, 176, 240), (144, 133, 233), (25, 158, 112), (251, 191, 36)
SNOW_DK = (30, 62, 110)
DAYS = post.DAYS


def badge(d, text, y=196):
    f = font(B, 24)
    w = text_w(d, text, f) + 40
    d.rounded_rectangle((PAD, y, PAD + w, y + 46), radius=23, fill=ICE)
    d.text((PAD + 20, y + 9), text, font=f, fill=(6, 18, 36))


def footer(d, line1, line2, y=1214):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), line2, font=font(R, 27), fill=DIM)
    d.text((PAD, y + 84), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)


def stats():
    S = post.Snap()
    post.build_article(S)                                   # varovalke: pade, če trditve ne držijo
    return S


def v1(S):
    d_ = {n: S.day(366, n) for n in range(23, 30)}
    w2 = S.win(366, "sre_cet")
    img, d = canvas()
    header(img, d, "napoved za Rečico", thumb=False)
    badge(d, "NAPOVED, NE MERITEV")
    d.text((PAD, 268), f"Sneg {post.teden_word()}:", font=font(B, 76), fill=WHITE)
    d.text((PAD, 360), "sreda in četrtek.", font=font(B, 76), fill=ICE)
    d.text((PAD, 470), f"{w2['cm1']} %", font=font(B, 190), fill=WHITE)
    d.text((PAD, 690), "članov ansamblov napoveduje v Rečici vsaj 1 cm", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), f"novega snega med sredo in četrtkom (mediana {post.rnd(w2['med'])} cm)", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 80, W - PAD - 30, y0 + 70, y1 - 90
    ds = list(range(23, 30))
    slot = (gx1 - gx0) / len(ds)
    Y = lambda v: gy1 - (gy1 - gy0) * v / 100
    for v in (0, 50, 100):
        d.line((gx0, Y(v), gx1, Y(v)), fill=LINE, width=1)
        d.text((PAD + 20, Y(v) - 12), f"{v}", font=font(R, 22), fill=DIM)
    for k, n in enumerate(ds):
        cx = gx0 + slot * (k + .5)
        bw = slot * .6
        v1_, v5 = d_[n]["cm1"], d_[n]["cm5"]
        d.rounded_rectangle((cx - bw / 2, Y(v1_), cx + bw / 2, gy1), radius=6, fill=SNOW_DK)
        if v5 > 0:
            d.rounded_rectangle((cx - bw / 2, Y(v5), cx + bw / 2, gy1), radius=6, fill=SNOW)
        s = str(v1_)
        d.text((cx - text_w(d, s, font(B, 26)) / 2, Y(v1_) - 36), s, font=font(B, 26), fill=WHITE)
        t = f"{DAYS[datetime.date(2026, 11, n).weekday()]} {n}."
        d.text((cx - text_w(d, t, font(R, 22)) / 2, gy1 + 14), t, font=font(R, 22), fill=DIM)
    d.text((gx0 + 6, y0 + 22), "delež članov z vsaj 1 cm (svetlo: vsaj 5 cm) po dnevih", font=font(R, 24), fill=MUTED)
    footer(d, f"Delež od {S.n} članov štirih ansamblov, Rečica 366 m", "Sneži ni isto kot obleži. Izračun, ne uradno opozorilo.")
    return img


def v2(S):
    hh = S.hourly(366)
    first = S.E["first"]
    t_first = post.START + datetime.timedelta(hours=first["h50"])
    img, d = canvas()
    header(img, d, "kdaj začne snežiti", thumb=False)
    badge(d, "NAPOVED, NE MERITEV")
    d.text((PAD, 268), "Prvi sneg v dolini:", font=font(B, 84), fill=WHITE)
    d.text((PAD, 360), f"v sredo {post.part(t_first.hour)}.", font=font(B, 84), fill=ICE)
    d.text((PAD, 480), f"{DAYS[t_first.weekday()]} {t_first.hour}.00", font=font(B, 160), fill=WHITE)
    d.text((PAD, 690), "mediana ure, ko v Rečici prvič zasneži", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), f"80 % članov: {post.span(first['h10'], first['h90'])}", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    lo, hi = 60, 133
    n = hi - lo
    gx0, gx1, gy0, gy1 = PAD + 70, W - PAD - 30, y0 + 90, y1 - 80
    X = lambda k: gx0 + (gx1 - gx0) * k / n
    Y = lambda v: gy1 - (gy1 - gy0) * v / 100
    for v in (0, 50, 100):
        d.line((gx0, Y(v), gx1, Y(v)), fill=LINE, width=1)
        d.text((PAD + 20, Y(v) - 12), f"{v}", font=font(R, 22), fill=DIM)
    bw = (gx1 - gx0) / n
    for k in range(n):
        base = 0
        for key, col in (("snow", SNOW), ("mix", MIXC), ("rain", RAINC)):
            v = hh[key][lo + k] or 0
            if v <= 0:
                continue
            d.rectangle((X(k) + 0.5, Y(base + v), X(k) + bw - 0.5, Y(base)), fill=col)
            base += v
    for k in range(n):
        t = post.START + datetime.timedelta(hours=lo + k)
        if t.hour in (0, 12):
            lab = "12.00" if k == 0 else (f"{DAYS[t.weekday()]} 0.00" if t.hour == 0 else "12.00")
            d.line((X(k), gy1, X(k), gy1 + 8), fill=DIM, width=2)
            d.text((X(k) - text_w(d, lab, font(R, 22)) / 2 + (28 if k == 0 else 0), gy1 + 14), lab, font=font(R, 22), fill=DIM)
    lx = gx0
    for nm, col in (("sneg", SNOW), ("dež s snegom", MIXC), ("dež", RAINC)):
        d.rounded_rectangle((lx, y0 + 26, lx + 22, y0 + 48), radius=5, fill=col)
        d.text((lx + 32, y0 + 22), nm, font=font(R, 24), fill=MUTED)
        lx += 32 + text_w(d, nm, font(R, 24)) + 36
    d.text((gx0, y0 + 58), "delež članov po vrsti padavin, ura za uro", font=font(R, 22), fill=DIM)
    footer(d, "Rečica 366 m, torek opoldne do petek opoldne", "Največ snega naj bi bilo v četrtek; za petek in vikend se modeli razidejo.")
    return img


def v3(S):
    rows = [(366, "Rečica"), (700, ""), (1000, ""), (1400, "Golte")]
    w2 = S.win(366, "sre_cet")
    img, d = canvas()
    header(img, d, "nov sneg po višinah", thumb=False)
    badge(d, "NAPOVED, NE MERITEV")
    d.text((PAD, 268), "Koliko snega", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "pade v sredo in četrtek?", font=font(B, 80), fill=ICE)
    d.text((PAD, 480), f"{post.rnd(w2['med'])} cm", font=font(B, 170), fill=WHITE)
    d.text((PAD, 690), f"mediana novega snega v Rečici (razpon {post.rnd(w2['p10'])}–{post.rnd(w2['p90'])} cm)", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), f"Na Golteh {post.rnd(S.win(1400, 'sre_cet')['med'])} cm, na 700 m {post.rnd(S.win(700, 'sre_cet')['med'])} cm", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 250, W - PAD - 120, y0 + 60, y1 - 90
    scale = 40.0
    X = lambda v: gx0 + (gx1 - gx0) * min(v, scale) / scale
    for v in (0, 10, 20, 30, 40):
        d.line((X(v), gy0 - 10, X(v), gy1), fill=LINE, width=1)
        d.text((X(v) - text_w(d, str(v), font(R, 22)) / 2, gy1 + 14), str(v), font=font(R, 22), fill=DIM)
    rh = (gy1 - gy0) / len(rows)
    for i, (el, nm) in enumerate(rows):
        w = S.win(el, "sre_cet")
        cy = gy0 + rh * i + rh / 2
        lab = f"{nm} · {el} m" if nm else f"{el} m"
        d.text((PAD + 30, cy - 15), lab, font=font(B, 26), fill=WHITE)
        d.rounded_rectangle((gx0, cy - 22, max(X(w["med"]), gx0 + 4), cy + 22), radius=8, fill=SNOW)
        d.line((X(w["p10"]), cy, X(w["p90"]), cy), fill=WHITE, width=3)
        for v in (w["p10"], w["p90"]):
            d.line((X(v), cy - 11, X(v), cy + 11), fill=WHITE, width=3)
        d.text((X(w["p90"]) + 16, cy - 15), f"{post.rnd(w['med'])} cm", font=font(B, 26), fill=WHITE)
    footer(d, "Stolpec: mediana. Črta: razpon 10.–90. percentila članov", "1 mm = 1 cm snega; pri mokrem snegu manj. Ni uradno opozorilo.")
    return img


def v4(S):
    firsts = post.climatology()
    n_live, _, last_live = post.live_gg()
    img, d = canvas()
    header(img, d, "prvi sneg v dolini", thumb=False)
    badge(d, "POSTAJA ARSO GORNJI GRAD")
    d.text((PAD, 268), "Prvi sneg v dolini", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "bi bil zgoden.", font=font(B, 88), fill=ICE)
    d.text((PAD, 480), "2. 12.", font=font(B, 170), fill=WHITE)
    d.text((PAD, 690), "mediana prvega dne z vsaj 1 cm snežne odeje", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), f"v sedmih zimah; letos do {int(last_live[8:10])}. 11. še ni bilo", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    base = datetime.date(2026, 11, 15)
    gx0, gx1, gy0, gy1 = PAD + 150, W - PAD - 60, y0 + 70, y1 - 70
    X = lambda dt: gx0 + (gx1 - gx0) * (dt - base).days / 46
    rh = (gy1 - gy0) / len(firsts)
    for lab_d in (datetime.date(2026, 11, 15), datetime.date(2026, 12, 1), datetime.date(2026, 12, 15), datetime.date(2026, 12, 31)):
        d.line((X(lab_d), gy0 - 10, X(lab_d), gy1), fill=LINE, width=1)
        t = post.dm(lab_d) if hasattr(post, "dm") else f"{lab_d.day}. {lab_d.month}."
        d.text((X(lab_d) - text_w(d, t, font(R, 22)) / 2, gy1 + 14), t, font=font(R, 22), fill=DIM)
    d.rounded_rectangle((X(datetime.date(2026, 11, 25)), gy0 - 10, X(datetime.date(2026, 11, 27)), gy1), radius=6, fill=(70, 56, 20))
    d.text((X(datetime.date(2026, 11, 25)) - 10, y0 + 22), "napoved: 25.–26. 11.", font=font(B, 24), fill=AMBER)
    for i, f in enumerate(firsts):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 30, cy - 15), f"{f.year}/{str(f.year + 1)[2:]}", font=font(B, 26), fill=WHITE)
        pos = X(datetime.date(2026, f.month, f.day))
        d.line((X(base), cy, pos, cy), fill=(70, 80, 104), width=4)
        d.ellipse((pos - 13, cy - 13, pos + 13, cy + 13), fill=ICE, outline=PANEL, width=3)
        lab = f"{f.day}. {f.month}."
        tw = text_w(d, lab, font(B, 24))
        d.text((pos + 22 if pos + 22 + tw < W - PAD - 6 else pos - 22 - tw, cy - 15), lab, font=font(B, 24), fill=WHITE)
    footer(d, "Prvi dan z višino snežne odeje vsaj 1 cm, Gornji Grad (428 m)", "Vir: Agencija Republike Slovenije za okolje (ARSO).")
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
