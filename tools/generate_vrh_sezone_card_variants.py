#!/usr/bin/env python3
"""
tools/generate_vrh_sezone_card_variants.py -- štiri kartice 1080×1350 za FB objavo članka
»Vrh opažanj gob je oktobra. Šest let podatkov« (isti slog kot kartice »Gobe po dežju«):

  1 šest od šestih -- »6 od 6« + točke tednov vrha po letih
  2 september proti oktobru -- po letih deleža gob, dva stolpca na leto
  3 letos -- tedenski delež gob, letos proti prejšnjim letom (vrh še ni znan)
  4 številke -- tri številke brez grafa

Fotografija (Filip Eremita) je ozadje čez celo kartico. Motiv (muha na gobi) je v zgornji tretjini in ostane viden,
pod njim se fotografija postopoma potemni (`scrim_alpha()`), da so naslov, številke in grafi vedno kontrastni. Vsa
besedila stojijo pod motivom (od y = CONTENT_Y); v glavi (na rahlo potemnjenem robu zgoraj) sta samo logotip in
značka, desno zgoraj, stran od motiva.

Številke so iz ISTEGA izračuna kot članek (`generate_vrh_sezone_post.build_article` se zažene, zato veljajo iste
varovalke: če podatki trditve ne podpirajo več, kartica ne nastane). Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_vrh_sezone_card_variants.py [--out-dir DIR]
"""
import datetime
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_vrh_sezone_post as post  # noqa: E402

ROOT = post.ROOT
W, H, PAD = 1080, 1350, 70
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
B, R = "LiberationSans-Bold.ttf", "LiberationSans-Regular.ttf"
WHITE, MUTED, DIM = (255, 255, 255), (214, 222, 236), (170, 180, 200)
PANEL, LINE, GREEN = (14, 18, 30), (52, 60, 82), (52, 211, 153)
GREY, BAND = (138, 160, 189), (66, 54, 20)
YEARS, LAST = post.YEARS, post.LAST
PHOTO_DY = -100          # fotografija je premaknjena navzgor: motiv (muha, goba) pride v y ≈ 230–510
CONTENT_Y = 560          # od tu naprej stoji besedilo (pod motivom)


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def text_w(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def scrim_alpha(y):
    """0–255: rahlo potemnjen vrh (glava), skoraj nespremenjen motiv, nato gladek prehod v temno."""
    pts = [(0, .58), (150, .22), (430, .20), (720, .90), (H, .94)]
    for (y0, a0), (y1, a1) in zip(pts, pts[1:]):
        if y <= y1:
            t = (y - y0) / (y1 - y0)
            t = t * t * (3 - 2 * t) if y0 >= 430 else t          # glajen (smoothstep) prehod pod motivom
            return int(255 * (a0 + (a1 - a0) * t))
    return int(255 * pts[-1][1])


def canvas():
    ph = Image.open(post.PHOTO_FILE).convert("RGB")
    s = max(W / ph.width, H / ph.height)
    ph = ph.resize((int(ph.width * s) + 1, int(ph.height * s) + 1), Image.LANCZOS)
    img = Image.new("RGB", (W, H), (5, 6, 14))
    img.paste(ph, ((W - ph.width) // 2, PHOTO_DY))
    ov = Image.new("RGBA", (W, H))
    od = ImageDraw.Draw(ov)
    for y in range(H):
        od.line((0, y, W, y), fill=(5, 6, 14, scrim_alpha(y)))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    return img, ImageDraw.Draw(img)


def header(img, d, sub):
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((84, 84), Image.LANCZOS)
    img.paste(logo, (PAD, 50), logo)
    d.text((PAD + 106, 50), "METEOREC", font=font(B, 40), fill=WHITE)
    d.text((PAD + 108, 96), sub, font=font(R, 26), fill=MUTED)
    f = font(B, 24)                                          # značka desno zgoraj (stran od motiva)
    text = "PODATKI iNATURALISTA"
    w = text_w(d, text, f) + 40
    d.rounded_rectangle((W - PAD - w, 62, W - PAD, 108), radius=23, fill=GREEN)
    d.text((W - PAD - w + 20, 71), text, font=f, fill=(4, 20, 14))


def footer(d, line1, y=1214):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), "Fotografije gob na iNaturalistu, ne košare in ne napoved najdbe.", font=font(R, 27), fill=DIM)
    d.text((PAD, y + 84), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)
    cr = "Foto: Filip Eremita"
    d.text((W - PAD - text_w(d, cr, font(R, 22)), 1308), cr, font=font(R, 22), fill=DIM)


def panel(d, y0, y1):
    d.rounded_rectangle((PAD, y0, W - PAD, y1), radius=26, fill=PANEL, outline=LINE, width=2)


def title(d, l1, l2, size=78, y=CONTENT_Y):
    d.text((PAD, y), l1, font=font(B, size), fill=WHITE)
    d.text((PAD, y + int(size * 1.13)), l2, font=font(B, size), fill=GREEN)
    return y + int(size * 2.2)


def stats():
    D, by_year = post.load()
    post.build_article(D, by_year)             # varovalke: pade, če trditve ne držijo
    B_ = D["povzetek"]["basidio"]
    peak = {y: datetime.date.fromisoformat(B_[str(y)]["teden_z_najvec"]["zacetek"]) for y in YEARS}
    cnt = {y: B_[str(y)]["teden_z_najvec"]["stevilo"] for y in YEARS}
    sh = {y: {int(m): v for m, v in B_[str(y)]["delez_po_mesecih"].items()} for y in YEARS}
    w26 = {d.isoformat(): v for d, v in by_year[LAST]}
    return D, by_year, peak, cnt, sh, w26


def off_of(d):
    return (d - datetime.date(d.year, 7, 1)).days


def v1(S):
    D, by_year, peak, cnt, sh, w26 = S
    img, d = canvas()
    header(img, d, "vrh opažanj gob 2020–2025")
    y = title(d, "Vrh opažanj gob", "je oktobra.")
    d.text((PAD, y + 12), "6 od 6", font=font(B, 128), fill=WHITE)
    d.text((PAD + 400, y + 48), "let: teden z največ", font=font(R, 30), fill=MUTED)
    d.text((PAD + 400, y + 86), "opaženimi gobami je bil", font=font(R, 30), fill=MUTED)
    d.text((PAD + 400, y + 124), "7.–27. oktobra", font=font(B, 30), fill=WHITE)
    y0, y1 = 915, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 130, W - PAD - 150, y0 + 52, y1 - 52
    lo, hi = 84, 133
    X = lambda off: gx0 + (gx1 - gx0) * (off - lo) / (hi - lo)
    d.rectangle((X(post.BAND[0]), gy0 - 22, X(post.BAND[1]), gy1 + 4), fill=BAND)
    d.text((X(post.BAND[0]) + 6, gy0 - 22), "7.–27. 10.", font=font(R, 19), fill=MUTED)
    rh = (gy1 - gy0) / len(YEARS)
    for i, yr in enumerate(YEARS):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 34, cy - 14), str(yr), font=font(B, 25), fill=WHITE)
        d.line((gx0, cy, gx1, cy), fill=LINE, width=1)
        cx = X(off_of(peak[yr]) + 3.5)
        d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=GREEN, outline=PANEL, width=3)
        d.text((gx1 + 24, cy - 13), f"{cnt[yr]}", font=font(B, 24), fill=WHITE)
    for off, t in ((92, "1. 10."), (106, "15. 10."), (123, "1. 11.")):
        d.text((X(off) - text_w(d, t, font(R, 20)) / 2, gy1 + 14), t, font=font(R, 20), fill=DIM)
    d.text((gx1 + 24, y0 + 14), "opažanj", font=font(R, 18), fill=DIM)
    footer(d, "Prave gobe (Basidiomycota), Slovenija, 2020–2025")
    return img


def v2(S):
    D, by_year, peak, cnt, sh, w26 = S
    img, d = canvas()
    header(img, d, "september proti oktobru")
    y = title(d, "Oktober je premagal", "september. Vsako leto.", size=70)
    d.text((PAD, y + 6), "Delež gob med vsemi opažanji na iNaturalistu v Sloveniji", font=font(R, 28), fill=MUTED)
    y0, y1 = 780, 1190
    panel(d, y0, y1)
    lx = PAD + 34
    for col, lab in ((GREY, "september"), (GREEN, "oktober")):
        d.rounded_rectangle((lx, y0 + 22, lx + 26, y0 + 48), radius=7, fill=col)
        d.text((lx + 38, y0 + 20), lab, font=font(R, 25), fill=MUTED)
        lx += 38 + text_w(d, lab, font(R, 25)) + 34
    gx0, gx1 = PAD + 130, W - PAD - 110
    gy0, gy1 = y0 + 70, y1 - 18
    top = 50
    rh = (gy1 - gy0) / len(YEARS)
    for i, yr in enumerate(YEARS):
        cy = gy0 + rh * i
        d.text((PAD + 34, cy + rh / 2 - 14), str(yr), font=font(B, 24), fill=WHITE)
        for k, (m, col) in enumerate(((9, GREY), (10, GREEN))):
            v = sh[yr][m]
            by = cy + 3 + k * 25
            d.rounded_rectangle((gx0, by, gx0 + (gx1 - gx0) * v / top, by + 21), radius=7, fill=col)
            d.text((gx0 + (gx1 - gx0) * v / top + 12, by - 1), f"{v} %", font=font(B, 20), fill=WHITE)
    footer(d, f"Oktober {min(sh[yr][10] for yr in YEARS)}–{max(sh[yr][10] for yr in YEARS)} %, "
              f"september {min(sh[yr][9] for yr in YEARS)}–{max(sh[yr][9] for yr in YEARS)} % vseh opažanj")
    return img


def v3(S):
    D, by_year, peak, cnt, sh, w26 = S
    img, d = canvas()
    header(img, d, "letošnja jesen")
    y = title(d, "Letošnji vrh", "še ni znan.", size=82)
    d.text((PAD, y + 14), "7.–27. 10.", font=font(B, 100), fill=WHITE)
    d.text((PAD + 520, y + 50), "tedni vrha v vseh", font=font(R, 28), fill=MUTED)
    d.text((PAD + 520, y + 86), "šestih prejšnjih letih", font=font(R, 28), fill=MUTED)
    y0, y1 = 915, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 70, W - PAD - 36, y0 + 56, y1 - 52
    top = 60
    X = lambda off: gx0 + (gx1 - gx0) * off / post.DOM
    Y = lambda v: gy1 - (gy1 - gy0) * v / top
    d.rectangle((X(post.BAND[0]), gy0 - 24, X(post.BAND[1]), gy1), fill=BAND)
    d.text((X(post.BAND[0]) + 6, gy0 - 24), "7.–27. 10.", font=font(R, 19), fill=MUTED)
    for t in (0, 15, 30, 45, 60):
        d.line((gx0, Y(t), gx1, Y(t)), fill=LINE, width=1)
        d.text((PAD + 20, Y(t) - 11), f"{t}", font=font(R, 18), fill=DIM)
    for off, lab in ((0, "jul"), (31, "avg"), (62, "sep"), (92, "okt"), (123, "nov")):
        d.text((X(off) + 4, gy1 + 12), lab, font=font(R, 20), fill=DIM)

    def line(pts, col, width):
        run = []
        for p in pts + [None]:
            if p is None:
                if len(run) > 1:
                    d.line(run, fill=col, width=width, joint="curve")
                run = []
            else:
                run.append(p)
    for yr in YEARS:
        pts = [(X((dd - datetime.date(yr, 7, 1)).days + 3.5), Y(post.share(v)))
               if v["vse"] >= post.MIN_ALL else None for dd, v in by_year[yr]]
        line(pts, GREY, 3)
    pts26 = [(X((dd - datetime.date(LAST, 7, 1)).days + 3.5), Y(post.share(v)))
             if v["vse"] >= post.MIN_ALL else None for dd, v in by_year[LAST]]
    line(pts26, GREEN, 7)
    last = [p for p in pts26 if p][-1]
    d.ellipse((last[0] - 11, last[1] - 11, last[0] + 11, last[1] + 11), fill=GREEN, outline=PANEL, width=4)
    d.text((last[0] - 128, last[1] - 50), str(LAST), font=font(B, 28), fill=WHITE, stroke_width=4, stroke_fill=PANEL)
    c = w26["2026-09-30"]["basidio"]
    footer(d, f"Do 13. 10. letos: {c} opažanj gob v tednu 30. 9.–6. 10.")
    return img


def v4(S):
    D, by_year, peak, cnt, sh, w26 = S
    img, d = canvas()
    header(img, d, "vrh opažanj gob")
    y = title(d, "Oktobra še ne", "odpišite gob.", size=82)
    oct_lo, oct_hi = min(sh[yr][10] for yr in YEARS), max(sh[yr][10] for yr in YEARS)
    sep_lo, sep_hi = min(sh[yr][9] for yr in YEARS), max(sh[yr][9] for yr in YEARS)
    rows = [("6 od 6", "let z vrhom opažanj med 7. in 27. oktobrom"),
            (f"{oct_lo}–{oct_hi} %", "vseh opažanj so oktobra gobe"),
            (f"{sep_lo}–{sep_hi} %", "vseh opažanj so septembra gobe")]
    yy = y + 30
    for big, lab in rows:
        d.ellipse((PAD, yy + 22, PAD + 32, yy + 54), fill=GREEN)
        d.text((PAD + 60, yy), big, font=font(B, 74), fill=WHITE)
        d.text((PAD + 62, yy + 86), lab, font=font(R, 30), fill=MUTED)
        yy += 142
    footer(d, "Prave gobe (Basidiomycota), Slovenija, 2020–2025")
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
