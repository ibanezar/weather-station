#!/usr/bin/env python3
"""
tools/generate_gobe_modeli_dez_cards.py — štiri kartice 1080×1350 za FB objavo članka
»Še ena priložnost za gobe? Modeli se ne strinjajo« (17. 10. 2026). Isto številko pokažejo na štiri načine:

  1 razpon   — dež do sobote po ansamblih (P10–P90, mediana), prag jurčka
  2 dnevi    — dež po dnevih torek–sobota: petek in sobota suha
  3 vrste    — delež napovedi, ki preseže sprožilni prag, po vrstah
  4 foto     — okno drugega vala z lastno fotografijo

Številke so iz istega izračuna kot članek (`generate_gobe_modeli_dez_post.analyse`, posnetek v data/).
Piše og/<slug>-kartica-N.jpg. Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_gobe_modeli_dez_cards.py [--out-dir DIR]
"""
import os
import statistics as st
import sys

from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_gobe_modeli_dez_post as art  # noqa: E402
import generate_gobe_po_dezju_card_variants as cv  # noqa: E402

font, hexrgb, text_w = cv.font, cv.hexrgb, cv.text_w
W, H, PAD = cv.W, cv.H, cv.PAD
WHITE, MUTED, DIM, PANEL, LINE, GREEN = cv.WHITE, cv.MUTED, cv.DIM, cv.PANEL, cv.LINE, cv.GREEN
B, R = cv.B, cv.R
SLUG = art.SLUG
mm = art.mm


def footer(d, line, y=1230):
    d.text((PAD, y), line, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), "Modelska napoved z dne 17. 10., ni meritev.", font=font(R, 27), fill=MUTED)
    d.text((PAD, y + 84), "Več in grafi: meteorec.si/blog", font=font(R, 27), fill=MUTED)


def data():
    S = art.load_data()
    A = art.analyse(S)
    pool = {}
    for m in A["full_ens"]:
        for x in S["ens"][m]["members"]:
            for dd in art.EV_DAYS:
                pool.setdefault(dd, []).append(x[dd])
    return S, A, pool


def c1(S, A, pool):
    img, d = cv.canvas()
    cv.header(img, d, "napoved dežja do sobote")
    cv.badge(d, "MODELI SE RAZHAJAJO")
    d.text((PAD, 268), "Dež do sobote:", font=font(B, 92), fill=WHITE)
    d.text((PAD, 368), f"{mm(A['pool'][int(.1 * (len(A['pool']) - 1))])}–{mm(art.pct(A['pool'], .9))} mm", font=font(B, 150), fill=GREEN)
    for k, ln in enumerate(cv.wrap(d, "Dež bo skoraj zagotovo. Koliko ga bo, modeli še ne vedo.", font(R, 38), W - 2 * PAD)):
        d.text((PAD, 560 + k * 52), ln, font=font(R, 38), fill=MUTED)
    px0, px1, mx = 380, W - PAD - 10, 60
    X = lambda v: px0 + min(v, mx) / mx * (px1 - px0)
    y0 = 720
    ytop, ybot = y0 - 14, y0 + 3 * 120
    for v in range(0, mx + 1, 20):
        d.line((X(v), ytop, X(v), ybot), fill=LINE, width=2)
        t = f"{v} mm"
        d.text((X(v) - text_w(d, t, font(R, 24)) / 2, ybot + 8), t, font=font(R, 24), fill=DIM)
    th = A["sp"]["boletus_edulis"]["thr"]
    for yy in range(ytop, ybot, 18):
        d.line((X(th), yy, X(th), yy + 9), fill=(224, 68, 62), width=4)
    d.text((X(th) + 10, ytop - 34), f"prag jurčka {mm(th)} mm", font=font(R, 26), fill=(240, 120, 114))
    for k, m in enumerate(A["full_ens"]):
        e = A["ens"][m]
        y = y0 + k * 120
        col = hexrgb(e["col"])
        d.text((PAD, y + 22), e["lab"].replace("ECMWF ", "ECMWF\n") if False else e["lab"], font=font(R, 27), fill=WHITE)
        d.rounded_rectangle((X(e["p10"]), y + 10, X(e["p90"]), y + 78), radius=14, fill=tuple(int(c * .45) for c in col), outline=col, width=3)
        d.line((X(e["med"]), y + 2, X(e["med"]), y + 86), fill=WHITE, width=6)
        d.text((X(e["med"]) - 6, y + 90), f"mediana {mm(e['med'])}", font=font(R, 24), fill=MUTED)
    footer(d, "Razpon P10–P90 članov ansamblov, 20.–24. 10.", 1218)
    return img


def c2(S, A, pool):
    img, d = cv.canvas()
    cv.header(img, d, "dež po dnevih")
    cv.badge(d, "DEŽ PO DNEVIH")
    d.text((PAD, 268), "Petek in sobota:", font=font(B, 88), fill=WHITE)
    d.text((PAD, 366), "skoraj brez dežja.", font=font(B, 88), fill=GREEN)
    for k, ln in enumerate(cv.wrap(d, "Dež pride v sredo in četrtek. Za gobe je odločilen dež pred koncem tedna.", font(R, 36), W - 2 * PAD)):
        d.text((PAD, 500 + k * 50), ln, font=font(R, 36), fill=MUTED)
    gx0, gx1, gy1, gh, mx = PAD + 60, W - PAD, 1090, 420, 40
    Y = lambda v: gy1 - min(v, mx) / mx * gh
    for v in (0, 10, 20, 30, 40):
        d.line((gx0, Y(v), gx1, Y(v)), fill=LINE, width=2)
        d.text((PAD, Y(v) - 14), str(v), font=font(R, 24), fill=DIM)
    n = len(art.EV_DAYS)
    cw = (gx1 - gx0) / n
    names = ["tor", "sre", "čet", "pet", "sob"]
    for k, dd in enumerate(art.EV_DAYS):
        v = pool[dd]
        med, p10, p90 = st.median(v), art.pct(v, .1), art.pct(v, .9)
        x = gx0 + k * cw + cw * .2
        w = cw * .6
        wet = k in (1, 2)
        col = GREEN if wet else (110, 122, 150)
        d.rounded_rectangle((x, Y(max(med, .6)), x + w, gy1), radius=10, fill=col)
        xc = x + w / 2
        d.line((xc, Y(p90), xc, Y(p10)), fill=WHITE, width=4)
        d.line((xc - 14, Y(p90), xc + 14, Y(p90)), fill=WHITE, width=4)
        t = mm(med)
        d.text((xc - text_w(d, t, font(B, 40)) / 2, Y(max(med, p90)) - 52), t if med >= .5 else "0", font=font(B, 40), fill=WHITE)
        t = f"{names[k]} {art.d_short(dd)}"
        d.text((xc - text_w(d, t, font(R, 25)) / 2, gy1 + 14), t, font=font(R, 25), fill=MUTED)
    footer(d, "Mediana in razpon P10–P90, mm; 133 članov treh ansamblov", 1218)
    return img


def c3(S, A, pool):
    img, d = cv.canvas()
    cv.header(img, d, "gobe po dežju 20.–22. 10.")
    cv.badge(d, "GOBARSKI MODEL")
    d.text((PAD, 268), "Bo še en val gob?", font=font(B, 92), fill=WHITE)
    d.text((PAD, 368), "Odvisno od vrste.", font=font(B, 92), fill=GREEN)
    for k, ln in enumerate(cv.wrap(d, "Delež napovedi, ki doseže prag dežja, da gobe po modelu rastejo:", font(R, 34), W - 2 * PAD)):
        d.text((PAD, 520 + k * 46), ln, font=font(R, 34), fill=MUTED)
    order = ["macrolepiota_procera", "armillaria_mellea", "hydnum_repandum", "boletus_edulis", "cantharellus_cibarius"]
    label = {"macrolepiota_procera": "Marela", "armillaria_mellea": "Štorovka", "hydnum_repandum": "Rumeni ježek",
             "boletus_edulis": "Jurček", "cantharellus_cibarius": "Lisička"}
    colr = {"macrolepiota_procera": "#e0a63a", "armillaria_mellea": "#d98f2b", "hydnum_repandum": "#34d399",
            "boletus_edulis": "#34d399", "cantharellus_cibarius": "#34d399"}
    n = A["n_pool"]
    px0, px1 = 380, W - PAD - 165
    y = 640
    for sid in order:
        r = A["sp"][sid]
        share = r["over_all"] / n
        d.rounded_rectangle((PAD, y, W - PAD, y + 100), radius=20, fill=PANEL, outline=LINE, width=2)
        d.text((PAD + 26, y + 14), label[sid], font=font(B, 32), fill=WHITE)
        d.text((PAD + 26, y + 58), f"prag {mm(r['thr'])} mm", font=font(R, 24), fill=DIM)
        d.rounded_rectangle((px0, y + 30, px1, y + 70), radius=12, fill=(30, 36, 56))
        d.rounded_rectangle((px0, y + 30, px0 + max(24, (px1 - px0) * share), y + 70), radius=12, fill=hexrgb(colr[sid]))
        t = f"{round(100 * share)} %"
        d.text((W - PAD - 24 - text_w(d, t, font(B, 44)), y + 24), t, font=font(B, 44), fill=WHITE)
        y += 114
    footer(d, "Samo sprožilni dež. Indeks upošteva še temperaturo in vlago.", 1228)
    return img


def c4(S, A, pool):
    img, d = cv.canvas(photo=True)
    cv.header(img, d, "gobe po dežju 20.–22. 10.")
    cv.badge(d, "DRUGI VAL")
    d.text((PAD, 268), "Še ena priložnost", font=font(B, 88), fill=WHITE)
    d.text((PAD, 366), "za gobe?", font=font(B, 88), fill=GREEN)
    y = 560
    rows = [("macrolepiota_procera", "marele"), ("cantharellus_cibarius", "lisičke"), ("hydnum_repandum", "rumeni ježki"), ("boletus_edulis", "jurčki")]
    for sid, lab in rows:
        r = A["sp"][sid]
        a, b = r["win"]
        t = f"{int(a[8:])}. {int(a[5:7])}.–{int(b[8:])}. {int(b[5:7])}."
        good = r["over_all"] / A["n_pool"] > .5
        d.ellipse((PAD, y + 14, PAD + 34, y + 48), fill=GREEN if good else (120, 130, 156))
        d.text((PAD + 64, y), t, font=font(B, 62), fill=WHITE)
        d.text((PAD + 64, y + 72), f"{lab}: dovolj dežja v {round(100 * r['over_all'] / A['n_pool'])} % napovedi", font=font(R, 30), fill=MUTED)
        y += 146
    d.text((PAD, y + 6), "Okna, če dež pade 20.–22. 10. Zeleno: več kot polovica napovedi.", font=font(R, 26), fill=MUTED)
    footer(d, "Količina dežja do srede je še negotova.", 1228)
    return img


def main():
    out = sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else os.path.join(art.ROOT, "og")
    os.makedirs(out, exist_ok=True)
    S, A, pool = data()
    for n, fn in enumerate((c1, c2, c3, c4), 1):
        p = os.path.join(out, f"{SLUG}-kartica-{n}.jpg")
        fn(S, A, pool).save(p, quality=92)
        print("✓", p)


if __name__ == "__main__":
    main()
