#!/usr/bin/env python3
"""
tools/generate_slane_se_ni_card_variants.py -- štiri kartice 1080×1350 za FB objavo članka
»16 noči pod 5 °C, temperature pod ničlo pa še ni bilo« (21. 10. 2026; isti slog kot kartice »Prva slana in gobe«):

  1 16 noči       -- število noči pod 5 °C od 1. 9. do 20. 10. po letih (letos največ)
  2 1,7 °C        -- najnižja temperatura vsake noči od 1. 9. + napoved MTR za 22.–24. 10.
  3 petek         -- MTR 0,1 °C, Open-Meteo 2,6 °C, WeatherNext 2 mediana 3,5 °C (modeli se ne strinjajo)
  4 50 dni        -- dni od 1. 9. do prve noči z 0 °C ali manj po letih; letos še brez

Številke so iz ISTEGA izračuna kot članek (`generate_slane_se_ni_post.build_article` se zažene, zato veljajo iste
varovalke: če podatki trditve ne podpirajo več -- postaja je izmerila ničlo ali napoved ni današnja -- kartica ne nastane).
Na FB/IG ne objavlja. Notranjih meritev ne uporablja (samo zunanji `tempLow`).

Usage:
    python3 tools/generate_slane_se_ni_card_variants.py [--out-dir DIR]
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_slane_se_ni_post as post  # noqa: E402
import generate_vrh_sezone_card_variants as cv  # noqa: E402   (pisave, platno, glava, panel)

ROOT = post.ROOT
W, H, PAD = cv.W, cv.H, cv.PAD
font, text_w, canvas, header, panel = cv.font, cv.text_w, cv.canvas, cv.header, cv.panel
B, R = cv.B, cv.R
WHITE, MUTED, DIM, PANEL, LINE, GREY = cv.WHITE, cv.MUTED, cv.DIM, cv.PANEL, cv.LINE, cv.GREY
CYAN, AMBER = (34, 211, 238), (251, 191, 36)
YEARS, LAST = post.YEARS, post.LAST


def badge(d, text, y=196):
    f = font(B, 24)
    w = text_w(d, text, f) + 40
    d.rounded_rectangle((PAD, y, PAD + w, y + 46), radius=23, fill=CYAN)
    d.text((PAD + 20, y + 9), text, font=f, fill=(2, 24, 32))


def footer(d, line1, line2="Postaja IREICA1, zunanji senzor. Ni uradno opozorilo.", y=1214):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), line2, font=font(R, 27), fill=DIM)
    d.text((PAD, y + 84), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)


def diamond(d, cx, cy, r, fill=None, outline=None, width=0):
    d.polygon([(cx, cy - r), (cx + r * 0.8, cy), (cx, cy + r), (cx - r * 0.8, cy)], fill=fill, outline=outline, width=width)


def stats():
    Hh = post.load()
    post.build_article(Hh)                                  # varovalke: pade, če trditve ne držijo
    S = {"H": Hh}
    S["cold"] = {y: sum(1 for _, t in post.nights(Hh, y) if t < post.COLD) for y in YEARS + [LAST]}
    S["ff"] = {y: post.first_freeze(Hh, y) for y in YEARS}
    S["ns"] = post.nights(Hh, LAST)
    S["min"] = min(S["ns"], key=lambda r: r[1])
    mdl = json.load(open(post.MODEL, encoding="utf-8"))
    fd = {r["date"]: r for r in mdl["days"]}
    S["fc"] = [(datetime.date.fromisoformat(k), fd[k]["tmin"]) for k in ("2026-10-22", "2026-10-23", "2026-10-24")]
    S["fri"] = fd["2026-10-23"]
    return S


def v1(S):
    cold = S["cold"]
    img, d = canvas()
    header(img, d, "hladne noči letošnje jeseni", thumb=False)
    badge(d, "POSTAJA IREICA1")
    d.text((PAD, 268), "Hladnih noči veliko,", font=font(B, 76), fill=WHITE)
    d.text((PAD, 360), "ničle pa še ni.", font=font(B, 76), fill=CYAN)
    d.text((PAD, 470), "16 noči", font=font(B, 170), fill=WHITE)
    d.text((PAD, 676), "s temperaturo zraka pod 5 °C od 1. 9. do 20. 10.", font=font(R, 34), fill=MUTED)
    d.text((PAD, 722), "To je več kot v kateri koli od prejšnjih šestih jeseni", font=font(R, 34), fill=MUTED)
    y0, y1 = 790, 1190
    panel(d, y0, y1)
    yrs = YEARS + [LAST]
    gx0, gx1, gy0, gy1 = PAD + 130, W - PAD - 90, y0 + 36, y1 - 40
    X = lambda v: gx0 + (gx1 - gx0) * v / 18
    rh = (gy1 - gy0) / len(yrs)
    for i, y in enumerate(yrs):
        cy = gy0 + rh * i + rh / 2
        v = cold[y]
        d.text((PAD + 34, cy - 15), str(y), font=font(B, 28), fill=WHITE)
        d.rounded_rectangle((gx0, cy - 17, max(X(v), gx0 + 4), cy + 17), radius=8, fill=CYAN if y == LAST else GREY)
        d.text((X(v) + 12, cy - 15), str(v), font=font(B, 28), fill=WHITE)
    footer(d, "Noči s temperaturo zraka pod 5 °C, 1. 9.–20. 10.", "Prag 5 °C je naša izbira za primerjavo med leti.")
    return img


def v2(S):
    ns, fc = S["ns"], S["fc"]
    mn = S["min"]
    img, d = canvas()
    header(img, d, "letošnja jesen v Rečici", thumb=False)
    badge(d, "POSTAJA IREICA1")
    d.text((PAD, 268), "Do ničle je", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "manjkalo 1,7 stopinje.", font=font(B, 80), fill=CYAN)
    d.text((PAD, 480), f"{post.num(mn[1])} °C", font=font(B, 170), fill=WHITE)
    d.text((PAD, 690), f"najnižja temperatura zraka letos ({mn[0].day}. {mn[0].month}.)", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), "Na travi je slana že bila, na termometru ne", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    d0 = ns[0][0]
    slots = (fc[-1][0] - d0).days + 1
    gx0, gx1, gy0, gy1 = PAD + 60, W - PAD - 30, y0 + 70, y1 - 70
    lo, hi = -2.0, 16.0
    Y = lambda t: gy0 + (gy1 - gy0) * (hi - t) / (hi - lo)
    bw = (gx1 - gx0) / slots
    for t in (0, 5, 10, 15):
        col = CYAN if t == 0 else LINE
        d.line((gx0, Y(t), gx1, Y(t)), fill=col, width=3 if t == 0 else 1)
        d.text((PAD + 14, Y(t) - 12), str(t), font=font(R, 22), fill=DIM)
    for dd, t in ns:
        x = gx0 + (dd - d0).days * bw
        d.rectangle((x + 1, min(Y(t), Y(0)), x + bw - 2, max(Y(t), Y(0))), fill=CYAN if t < post.COLD else GREY)
    for dd, t in fc:
        x = gx0 + (dd - d0).days * bw
        d.rectangle((x + 1, min(Y(t), Y(0)), x + bw - 2, max(Y(t), Y(0)) + 2), outline=AMBER, width=3)
    for lab_d in (datetime.date(LAST, 9, 1), datetime.date(LAST, 9, 15), datetime.date(LAST, 10, 1), datetime.date(LAST, 10, 15)):
        x = gx0 + (lab_d - d0).days * bw
        t = post.dm(lab_d)
        d.text((x - text_w(d, t, font(R, 22)) / 2 + bw / 2, gy1 + 16), t, font=font(R, 22), fill=DIM)
    d.text((gx0 + 6, y0 + 20), "temperatura zraka ob vsaki noči", font=font(R, 24), fill=MUTED)
    d.text((gx1 - text_w(d, "napoved MTR", font(R, 24)), y0 + 20), "napoved MTR", font=font(B, 24), fill=AMBER)
    footer(d, "Najnižja temperatura vsake noči od 1. 9. do 20. 10. 2026", "Črtkani stolpci: poskusni model MTR za 22.–24. 10.")
    return img


def v3(S):
    f = S["fri"]
    img, d = canvas()
    header(img, d, "petek, 23. oktober", thumb=False)
    badge(d, "NAPOVED, NE MERITEV")
    d.text((PAD, 268), "Petkovo jutro:", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "ničla ali ne?", font=font(B, 88), fill=CYAN)
    d.text((PAD, 480), f"{round(f['p_frost'] * 100)} %", font=font(B, 190), fill=WHITE)
    d.text((PAD, 690), "verjetnost temperature zraka pod ničlo", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), "po poskusnem modelu MTR (napoved z 21. 10.)", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    lo, hi = -1.0, 6.0
    gx0, gx1 = PAD + 250, W - PAD - 50
    X = lambda t: gx0 + (gx1 - gx0) * (t - lo) / (hi - lo)
    rows = [("MTR", f["tmin"], AMBER, None), ("Open-Meteo", f["om_tmin"], GREY, None),
            ("WeatherNext 2", f["wn2"]["tmin"]["p50"], CYAN, (f["wn2"]["tmin"]["p10"], f["wn2"]["tmin"]["p90"]))]
    gy0, gy1 = y0 + 60, y1 - 80
    for t in range(-1, 7):
        s = str(t).replace("-", "–")
        d.line((X(t), gy0 - 10, X(t), gy1), fill=LINE if t else (120, 130, 150), width=1 if t else 3)
        d.text((X(t) - text_w(d, s, font(R, 22)) / 2, gy1 + 14), s + " °C" if t in (-1, 0, 6) else s, font=font(R, 22), fill=DIM)
    rh = (gy1 - gy0) / len(rows)
    for i, (nm, v, col, rng) in enumerate(rows):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 30, cy - 15), nm, font=font(B, 28), fill=WHITE)
        if rng:
            d.rounded_rectangle((X(rng[0]), cy - 9, X(rng[1]), cy + 9), radius=9, fill=(24, 90, 104))
        d.ellipse((X(v) - 17, cy - 17, X(v) + 17, cy + 17), fill=col, outline=PANEL, width=3)
        lab = f"{post.num(v)} °C".replace("-", "–")
        d.text((X(v) + 26, cy - 40), lab, font=font(B, 26), fill=WHITE)
    footer(d, "Tri modeli, tri različne številke za isto jutro", "MTR: poskusni model. Ni uradno opozorilo; za opozorila velja ARSO.")
    return img


def v4(S):
    ff = S["ff"]
    last = datetime.date(LAST, 10, 20)
    n26 = (last - datetime.date(LAST, 9, 1)).days + 1
    img, d = canvas()
    header(img, d, "čakanje na prvo ničelno noč", thumb=False)
    badge(d, "POSTAJA IREICA1")
    d.text((PAD, 268), "Prva ničla", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "letos še čaka.", font=font(B, 88), fill=CYAN)
    d.text((PAD, 480), f"{n26} dni", font=font(B, 170), fill=WHITE)
    d.text((PAD, 690), "od 1. 9. brez noči z 0 °C ali manj", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), "Leta 2022 in 2024 je bilo čakanje daljše", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    yrs = YEARS + [LAST]
    gx0, gx1, gy0, gy1 = PAD + 130, W - PAD - 110, y0 + 50, y1 - 70
    base = datetime.date(2001, 9, 1)
    X = lambda dt: gx0 + (gx1 - gx0) * (datetime.date(2001, dt.month, dt.day) - base).days / 85
    rh = (gy1 - gy0) / len(yrs)
    for lab_d in (datetime.date(LAST, 9, 1), datetime.date(LAST, 10, 1), datetime.date(LAST, 10, 15), datetime.date(LAST, 11, 1), datetime.date(LAST, 11, 15)):
        d.line((X(lab_d), gy0 - 10, X(lab_d), gy1), fill=LINE, width=1)
        t = post.dm(lab_d)
        d.text((X(lab_d) - text_w(d, t, font(R, 22)) / 2, gy1 + 16), t, font=font(R, 22), fill=DIM)
    for i, y in enumerate(yrs):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 34, cy - 15), str(y), font=font(B, 28), fill=WHITE)
        if y == LAST:
            d.rounded_rectangle((X(datetime.date(LAST, 9, 1)), cy - 8, X(last), cy + 8), radius=8, fill=AMBER)
            d.text((X(last) + 14, cy - 15), "še brez", font=font(B, 26), fill=AMBER)
        else:
            dt = ff[y]
            d.rounded_rectangle((X(datetime.date(LAST, 9, 1)), cy - 8, X(dt), cy + 8), radius=8, fill=(70, 80, 104))
            d.ellipse((X(dt) - 14, cy - 14, X(dt) + 14, cy + 14), fill=CYAN, outline=PANEL, width=3)
            d.text((X(dt) + 22, cy - 15), post.dm(dt), font=font(B, 24), fill=WHITE)
    footer(d, "Prva noč z 0 °C ali manj po letih, 2020–2025", "Slana na travi se pojavi tudi pri temperaturi zraka nad ničlo.")
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
