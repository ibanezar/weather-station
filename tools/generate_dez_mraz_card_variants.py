#!/usr/bin/env python3
"""
tools/generate_dez_mraz_card_variants.py -- tri kartice 1080×1350 za FB/IG objavo članka
»82 mm dežja v dveh dneh, v nedeljo pa mraz« (14. 11. 2026; isti slog kot kartice »16 noči pod 5 °C«):

  1 82,5 mm   -- dnevne padavine 1.-13. 11., 12. in 13. poudarjena
  2 79,5 mm   -- napoved količine dan prej: MTR (povprečje petih virov), Open-Meteo, AIFS, WeatherNext 2 proti izmerjenemu
  3 –2,5 °C   -- napoved najnižje temperature za nedeljo 15. 11. po petih virih

Številke so iz ISTEGA izračuna kot članek (`generate_dez_mraz_post.build_article` se zažene, zato veljajo iste varovalke:
če napoved ni več današnja ali postaja v noči na nedeljo izmeri ničlo, kartice ne nastanejo). Notranjih meritev ne uporablja.
Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_dez_mraz_card_variants.py [--out-dir DIR]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_dez_mraz_post as post  # noqa: E402
import generate_vrh_sezone_card_variants as cv  # noqa: E402

ROOT = post.ROOT
W, H, PAD = cv.W, cv.H, cv.PAD
font, text_w, canvas, header, panel = cv.font, cv.text_w, cv.canvas, cv.header, cv.panel
B, R = cv.B, cv.R
WHITE, MUTED, DIM, PANEL, LINE, GREY = cv.WHITE, cv.MUTED, cv.DIM, cv.PANEL, cv.LINE, cv.GREY
CYAN, AMBER = (34, 211, 238), (251, 191, 36)
BLUE, PINK, VIOLET, GREEN = (57, 135, 229), (213, 81, 129), (144, 133, 233), (25, 158, 112)


def badge(d, text, col=CYAN, y=196):
    f = font(B, 24)
    w = text_w(d, text, f) + 40
    d.rounded_rectangle((PAD, y, PAD + w, y + 46), radius=23, fill=col)
    d.text((PAD + 20, y + 9), text, font=f, fill=(2, 24, 32))


def footer(d, line1, line2, y=1214):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), line2, font=font(R, 27), fill=DIM)
    d.text((PAD, y + 84), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)


def stats():
    post.build_article()                                    # varovalke: pade, če trditve ne držijo
    H_ = json.load(open(post.HISTORY, encoding="utf-8"))
    H_ = H_.get("days", H_)
    S = {k: v for k, v in H_.items() if v.get("src") != "era5"}
    V = json.load(open(post.VERIF, encoding="utf-8"))
    f12, f13 = V["2026-11-12"], V["2026-11-13"]
    two = round(S["2026-11-12"]["precipTotal"] + S["2026-11-13"]["precipTotal"], 1)
    mt = round(post.mtr_mm_day_before("2026-11-12") + post.mtr_mm_day_before("2026-11-13"), 1)
    src = {"Open-Meteo": f12["open_meteo"]["precip"] + f13["open_meteo"]["precip"], "ECMWF AIFS": f12["aifs"]["precip"] + f13["aifs"]["precip"],
           "WeatherNext 2": f12["wn2"]["precip"] + f13["wn2"]["precip"]}
    mdl = json.load(open(post.MODEL, encoding="utf-8"))
    sun = {r["date"]: r for r in mdl["days"]}["2026-11-15"]
    pend = {x["target_date"]: x for x in json.load(open(post.PENDING, encoding="utf-8"))}["2026-11-15"]
    return {"S": S, "two": two, "mt": mt, "src": {k: round(v, 1) for k, v in src.items()}, "sun": sun, "pend": pend,
            "nov": round(sum(v["precipTotal"] for k, v in S.items() if k.startswith("2026-11") and v.get("precipTotal") is not None), 1)}


def v1(X):
    S = X["S"]
    img, d = canvas()
    header(img, d, "dež 12. in 13. novembra", thumb=False)
    badge(d, "POSTAJA IREICA1")
    d.text((PAD, 268), "Dva dni, en dogodek.", font=font(B, 80), fill=WHITE)
    d.text((PAD, 364), "Šesti največji od 2019.", font=font(B, 66), fill=CYAN)
    d.text((PAD, 470), f"{post.num(X['two'])} mm", font=font(B, 170), fill=WHITE)
    d.text((PAD, 676), "dežja v Rečici, 86 % vsega letošnjega novembra", font=font(R, 34), fill=MUTED)
    d.text((PAD, 722), "Med dvodnevnimi seštevki od novembra 2019", font=font(R, 34), fill=MUTED)
    y0, y1 = 790, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 70, W - PAD - 30, y0 + 70, y1 - 70
    days = list(range(1, 14))
    bw = (gx1 - gx0) / len(days)
    Y = lambda v: gy1 - (gy1 - gy0) * v / 60
    for t in (0, 20, 40, 60):
        d.line((gx0, Y(t), gx1, Y(t)), fill=LINE, width=1)
        d.text((PAD + 20, Y(t) - 12), str(t), font=font(R, 22), fill=DIM)
    d.text((gx0 + 6, y0 + 18), "mm na dan, 1.–13. november", font=font(R, 24), fill=MUTED)
    for i, dd in enumerate(days):
        v = S[f"2026-11-{dd:02d}"]["precipTotal"]
        big = dd in (12, 13)
        x = gx0 + i * bw
        d.rectangle((x + 5, Y(v), x + bw - 5, gy1), fill=BLUE if big else (60, 96, 150))
        if big:
            d.text((x + bw / 2 - text_w(d, post.num(v), font(B, 26)) / 2, Y(v) - 36), post.num(v), font=font(B, 26), fill=WHITE)
        if dd % 2 == 1 or big:
            d.text((x + bw / 2 - text_w(d, f"{dd}.", font(R, 22)) / 2, gy1 + 14), f"{dd}.", font=font(R, 22), fill=DIM)
    footer(d, "Dnevne padavine, meritev dežemera postaje", "Dogodki, ki se prekrivajo, so šteti enkrat.")
    return img


def v2(X):
    img, d = canvas()
    header(img, d, "napoved količine padavin", thumb=False)
    badge(d, "NAPOVED DAN PREJ PROTI MERITVI")
    d.text((PAD, 268), "Modeli so podcenili.", font=font(B, 80), fill=WHITE)
    d.text((PAD, 364), "Povprečje je bilo najbliže.", font=font(B, 66), fill=CYAN)
    d.text((PAD, 470), f"{post.num(X['mt'])} mm", font=font(B, 170), fill=WHITE)
    d.text((PAD, 676), f"napoved MTR za oba dneva, izmerjeno {post.num(X['two'])} mm", font=font(R, 34), fill=MUTED)
    d.text((PAD, 722), "MTR = povprečje petih virov, ne naučen popravek", font=font(R, 34), fill=MUTED)
    y0, y1 = 790, 1190
    panel(d, y0, y1)
    rows = [("Izmerjeno", X["two"], WHITE), ("MTR", X["mt"], GREEN), ("Open-Meteo", X["src"]["Open-Meteo"], BLUE),
            ("ECMWF AIFS", X["src"]["ECMWF AIFS"], PINK), ("WeatherNext 2", X["src"]["WeatherNext 2"], VIOLET)]
    gx0, gx1 = PAD + 250, W - PAD - 110
    gy0, gy1 = y0 + 50, y1 - 50
    rh = (gy1 - gy0) / len(rows)
    for i, (nm, v, col) in enumerate(rows):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 30, cy - 15), nm, font=font(B, 28), fill=WHITE)
        d.rounded_rectangle((gx0, cy - 20, gx0 + (gx1 - gx0) * v / 90, cy + 20), radius=8, fill=col)
        d.text((gx0 + (gx1 - gx0) * v / 90 + 14, cy - 15), post.num(v), font=font(B, 28), fill=WHITE)
    footer(d, "Napoved, izdana dan pred dogodkom, 12. + 13. 11. (mm)", "En dogodek ne dokazuje, kateri vir je boljši.")
    return img


def v3(X):
    sun, pend = X["sun"], X["pend"]
    img, d = canvas()
    header(img, d, "nedelja, 15. november", thumb=False)
    badge(d, "NAPOVED, NE MERITEV", AMBER)
    d.text((PAD, 268), "Po dežju pride mraz.", font=font(B, 80), fill=WHITE)
    d.text((PAD, 364), "Nedeljsko jutro pod ničlo.", font=font(B, 64), fill=CYAN)
    d.text((PAD, 470), f"{post.num(sun['tmin'])} °C".replace("-", "–"), font=font(B, 170), fill=WHITE)
    d.text((PAD, 676), f"najnižja temperatura po modelu MTR, verjetnost zmrzali {round(sun['p_frost'] * 100)} %", font=font(R, 34), fill=MUTED)
    d.text((PAD, 722), "Doslej letos najnižje –1,7 °C (9. 11.)", font=font(R, 34), fill=MUTED)
    y0, y1 = 790, 1190
    panel(d, y0, y1)
    lo, hi = -5.0, 1.0
    gx0, gx1 = PAD + 270, W - PAD - 60
    Xp = lambda t: gx0 + (gx1 - gx0) * (t - lo) / (hi - lo)
    rows = [("ARSO (Ljubno)", pend["arso"]["tmin"], AMBER), ("Open-Meteo", pend["open_meteo"]["tmin"], BLUE), ("MTR", sun["tmin"], GREEN),
            ("WeatherNext 2", pend["wn2"]["tmin"], VIOLET), ("ECMWF AIFS", pend["aifs"]["tmin"], PINK)]
    gy0, gy1 = y0 + 50, y1 - 80
    for t in range(-5, 2):
        s = str(t).replace("-", "–")
        d.line((Xp(t), gy0 - 6, Xp(t), gy1), fill=LINE if t else (120, 130, 150), width=1 if t else 3)
        d.text((Xp(t) - text_w(d, s, font(R, 22)) / 2, gy1 + 14), s + " °C" if t in (-5, 0) else s, font=font(R, 22), fill=DIM)
    rh = (gy1 - gy0) / len(rows)
    for i, (nm, v, col) in enumerate(rows):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 30, cy - 15), nm, font=font(B, 28), fill=WHITE)
        d.ellipse((Xp(v) - 17, cy - 17, Xp(v) + 17, cy + 17), fill=col, outline=PANEL, width=3)
        d.text((Xp(v) + 26, cy - 40), post.num(v).replace("-", "–"), font=font(B, 26), fill=WHITE)
    footer(d, "Pet virov, vsi pod ničlo, razpon skoraj tri stopinje", "Ni uradno opozorilo; za opozorila velja ARSO.")
    return img


def main():
    out = sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else os.path.join(ROOT, "og")
    os.makedirs(out, exist_ok=True)
    X = stats()
    for n, fn in enumerate((v1, v2, v3), 1):
        p = os.path.join(out, f"{post.SLUG}-kartica-{n}.jpg")
        fn(X).save(p, quality=92)
        print("✓", p)


if __name__ == "__main__":
    main()
