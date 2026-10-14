#!/usr/bin/env python3
"""
tools/generate_vrh_sezone_card_variants.py -- štiri kartice 1080×1350 za FB objavo članka
»Vrh opažanj gob je oktobra. Šest let podatkov« (isti slog kot kartice »Gobe po dežju«):

  1 šest od šestih -- »6 od 6« + točke tednov vrha po letih
  2 september proti oktobru -- po letih deleža gob, dva stolpca na leto
  3 letos -- tedenski delež gob, letos proti prejšnjim letom (vrh še ni znan)
  4 foto -- lastna fotografija gob, tri številke

Številke so iz ISTEGA izračuna kot članek (`generate_vrh_sezone_post.build_article` se zažene, zato veljajo
iste varovalke: če podatki trditve ne podpirajo več, kartica ne nastane). Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_vrh_sezone_card_variants.py [--out-dir DIR]
"""
import datetime
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_vrh_sezone_post as post  # noqa: E402

ROOT = post.ROOT
W, H, PAD = 1080, 1350, 70
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
B, R = "LiberationSans-Bold.ttf", "LiberationSans-Regular.ttf"
BG, WHITE, MUTED, DIM = (5, 6, 14), (255, 255, 255), (200, 210, 228), (150, 160, 182)
PANEL, LINE, GREEN = (16, 20, 34), (44, 52, 74), (52, 211, 153)
GREY, BAND = (138, 160, 189), (58, 48, 20)
YEARS, LAST = post.YEARS, post.LAST


def font(name, size):
    from PIL import ImageFont
    return ImageFont.truetype(FONT_DIR + name, size)


def text_w(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def canvas(photo=False, blur=2):
    if photo:
        bg = Image.open(post.PHOTO_FILE).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1), Image.LANCZOS)
        x, y = (bg.width - W) // 2, (bg.height - H) // 2
        img = bg.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(blur))
        ov = Image.new("RGBA", (W, H))
        od = ImageDraw.Draw(ov)
        for yy in range(H):
            od.line((0, yy, W, yy), fill=(5, 6, 14, min(235, int(120 + 120 * yy / H))))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    else:
        img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def header(img, d, sub, thumb=True):
    if thumb:                                   # Filipova fotografija, sličica zgoraj desno
        ph = Image.open(post.PHOTO_FILE).convert("RGB").resize((148, 222), Image.LANCZOS)
        mask = Image.new("L", ph.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=18, fill=255)
        img.paste(ph, (W - PAD - ph.width, 34), mask)
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((84, 84), Image.LANCZOS)
    img.paste(logo, (PAD, 60), logo)
    d.text((PAD + 106, 60), "METEOREC", font=font(B, 40), fill=WHITE)
    d.text((PAD + 108, 106), sub, font=font(R, 26), fill=MUTED)


def badge(d, text, y=196):
    f = font(B, 24)
    w = text_w(d, text, f) + 40
    d.rounded_rectangle((PAD, y, PAD + w, y + 46), radius=23, fill=GREEN)
    d.text((PAD + 20, y + 9), text, font=f, fill=(4, 20, 14))


def footer(d, line1, y=1214):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), "Fotografije gob na iNaturalistu, ne košare in ne napoved najdbe.", font=font(R, 27), fill=DIM)
    d.text((PAD, y + 84), "Grafi in podatki: meteorec.si/blog", font=font(R, 27), fill=DIM)


def panel(d, y0, y1):
    d.rounded_rectangle((PAD, y0, W - PAD, y1), radius=26, fill=PANEL, outline=LINE, width=2)


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
    badge(d, "PODATKI iNATURALISTA")
    d.text((PAD, 268), "Vrh opažanj gob", font=font(B, 84), fill=WHITE)
    d.text((PAD, 360), "je oktobra.", font=font(B, 84), fill=GREEN)
    d.text((PAD, 480), "6 od 6", font=font(B, 190), fill=WHITE)
    d.text((PAD, 690), "let: teden z največ opaženimi gobami v Sloveniji", font=font(R, 34), fill=MUTED)
    d.text((PAD, 736), "je padel med 7. in 27. oktobrom", font=font(R, 34), fill=MUTED)
    y0, y1 = 810, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 130, W - PAD - 150, y0 + 70, y1 - 70
    lo, hi = 84, 133
    X = lambda off: gx0 + (gx1 - gx0) * (off - lo) / (hi - lo)
    d.rectangle((X(post.BAND[0]), gy0 - 30, X(post.BAND[1]), gy1 + 6), fill=BAND)
    d.text((X(post.BAND[0]) + 6, gy0 - 28), "7.–27. 10.", font=font(R, 21), fill=MUTED)
    rh = (gy1 - gy0) / len(YEARS)
    for i, y in enumerate(YEARS):
        cy = gy0 + rh * i + rh / 2
        d.text((PAD + 34, cy - 15), str(y), font=font(B, 28), fill=WHITE)
        d.line((gx0, cy, gx1, cy), fill=LINE, width=1)
        cx = X(off_of(peak[y]) + 3.5)
        d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=GREEN, outline=PANEL, width=3)
        d.text((gx1 + 24, cy - 14), f"{cnt[y]}", font=font(B, 26), fill=WHITE)
    for off, t in ((92, "1. 10."), (106, "15. 10."), (123, "1. 11.")):
        d.text((X(off) - text_w(d, t, font(R, 22)) / 2, gy1 + 22), t, font=font(R, 22), fill=DIM)
    d.text((gx1 + 24, y0 + 22), "opažanj", font=font(R, 20), fill=DIM)
    footer(d, "Prave gobe (Basidiomycota), Slovenija, tedenska opažanja 2020–2025")
    return img


def v2(S):
    D, by_year, peak, cnt, sh, w26 = S
    img, d = canvas()
    header(img, d, "september proti oktobru")
    badge(d, "PODATKI iNATURALISTA")
    d.text((PAD, 268), "Oktober je premagal", font=font(B, 76), fill=WHITE)
    d.text((PAD, 352), "september. Vsako leto.", font=font(B, 76), fill=GREEN)
    d.text((PAD, 460), "Delež gob med vsemi opažanji na iNaturalistu v Sloveniji", font=font(R, 30), fill=MUTED)
    y0, y1 = 530, 1180
    panel(d, y0, y1)
    # legenda
    lx = PAD + 34
    for col, lab in ((GREY, "september"), (GREEN, "oktober")):
        d.rounded_rectangle((lx, y0 + 28, lx + 28, y0 + 56), radius=7, fill=col)
        d.text((lx + 40, y0 + 26), lab, font=font(R, 26), fill=MUTED)
        lx += 40 + text_w(d, lab, font(R, 26)) + 36
    gx0, gx1 = PAD + 130, W - PAD - 110
    gy0, gy1 = y0 + 90, y1 - 30
    top = 50
    rh = (gy1 - gy0) / len(YEARS)
    for i, y in enumerate(YEARS):
        cy = gy0 + rh * i
        d.text((PAD + 34, cy + rh / 2 - 16), str(y), font=font(B, 28), fill=WHITE)
        for k, (m, col) in enumerate(((9, GREY), (10, GREEN))):
            v = sh[y][m]
            by = cy + 10 + k * 40
            d.rounded_rectangle((gx0, by, gx0 + (gx1 - gx0) * v / top, by + 30), radius=9, fill=col)
            d.text((gx0 + (gx1 - gx0) * v / top + 12, by + 1), f"{v} %", font=font(B, 24), fill=WHITE)
    footer(d, f"Oktober {min(sh[y][10] for y in YEARS)}–{max(sh[y][10] for y in YEARS)} %, "
              f"september {min(sh[y][9] for y in YEARS)}–{max(sh[y][9] for y in YEARS)} % vseh opažanj")
    return img


def v3(S):
    D, by_year, peak, cnt, sh, w26 = S
    img, d = canvas()
    header(img, d, "letošnja jesen")
    badge(d, "PODATKI iNATURALISTA")
    d.text((PAD, 268), "Letošnji vrh", font=font(B, 88), fill=WHITE)
    d.text((PAD, 364), "še ni znan.", font=font(B, 88), fill=GREEN)
    d.text((PAD, 490), "7.–27. 10.", font=font(B, 130), fill=WHITE)
    d.text((PAD, 642), "tedni, v katerih je bil vrh v vseh šestih prejšnjih letih", font=font(R, 31), fill=MUTED)
    y0, y1 = 710, 1190
    panel(d, y0, y1)
    gx0, gx1, gy0, gy1 = PAD + 70, W - PAD - 36, y0 + 70, y1 - 70
    top = 60
    X = lambda off: gx0 + (gx1 - gx0) * off / post.DOM
    Y = lambda v: gy1 - (gy1 - gy0) * v / top
    d.rectangle((X(post.BAND[0]), gy0 - 30, X(post.BAND[1]), gy1), fill=BAND)
    d.text((X(post.BAND[0]) + 6, gy0 - 28), "7.–27. 10.", font=font(R, 21), fill=MUTED)
    for t in (0, 15, 30, 45, 60):
        d.line((gx0, Y(t), gx1, Y(t)), fill=LINE, width=1)
        d.text((PAD + 22, Y(t) - 12), f"{t}", font=font(R, 20), fill=DIM)
    for off, lab in ((0, "jul"), (31, "avg"), (62, "sep"), (92, "okt"), (123, "nov")):
        d.text((X(off) + 4, gy1 + 16), lab, font=font(R, 22), fill=DIM)

    def line(pts, col, width):
        run = []
        for p in pts + [None]:
            if p is None:
                if len(run) > 1:
                    d.line(run, fill=col, width=width, joint="curve")
                run = []
            else:
                run.append(p)
    for y in YEARS:
        pts = [(X((dd - datetime.date(y, 7, 1)).days + 3.5), Y(post.share(v)))
               if v["vse"] >= post.MIN_ALL else None for dd, v in by_year[y]]
        line(pts, GREY, 3)
    pts26 = [(X((dd - datetime.date(LAST, 7, 1)).days + 3.5), Y(post.share(v)))
             if v["vse"] >= post.MIN_ALL else None for dd, v in by_year[LAST]]
    line(pts26, GREEN, 7)
    last = [p for p in pts26 if p][-1]
    d.ellipse((last[0] - 12, last[1] - 12, last[0] + 12, last[1] + 12), fill=GREEN, outline=PANEL, width=4)
    d.text((last[0] - 130, last[1] - 52), str(LAST), font=font(B, 30), fill=WHITE)
    c = w26["2026-09-30"]["basidio"]
    footer(d, f"Do 13. 10. letos: {c} opažanj gob v tednu 30. 9.–6. 10.")
    return img


def v4(S):
    D, by_year, peak, cnt, sh, w26 = S
    img, d = canvas(photo=True, blur=16)
    header(img, d, "vrh opažanj gob", thumb=False)
    badge(d, "PODATKI iNATURALISTA")
    f = font(B, 88)
    d.text((PAD, 268), "Oktobra še ne", font=f, fill=WHITE)
    d.text((PAD, 372), "odpišite gob.", font=f, fill=GREEN)
    oct_lo, oct_hi = min(sh[y][10] for y in YEARS), max(sh[y][10] for y in YEARS)
    sep_lo, sep_hi = min(sh[y][9] for y in YEARS), max(sh[y][9] for y in YEARS)
    rows = [("6 od 6", "let z vrhom opažanj med 7. in 27. oktobrom"),
            (f"{oct_lo}–{oct_hi} %", "vseh opažanj so oktobra gobe"),
            (f"{sep_lo}–{sep_hi} %", "vseh opažanj so septembra gobe")]
    ph = Image.open(post.PHOTO_FILE).convert("RGB").resize((260, 390), Image.LANCZOS)     # ostra fotografija ob številkah
    mask = Image.new("L", ph.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=22, fill=255)
    img.paste(ph, (W - PAD - ph.width, 620), mask)
    y = 580
    for big, lab in rows:
        d.ellipse((PAD, y + 20, PAD + 34, y + 54), fill=GREEN)
        d.text((PAD + 64, y), big, font=font(B, 76), fill=WHITE)
        d.text((PAD + 64, y + 88), lab, font=font(R, 30), fill=MUTED)
        y += 190
    footer(d, "Prave gobe (Basidiomycota), Slovenija, 2020–2025")
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
