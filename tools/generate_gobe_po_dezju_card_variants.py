#!/usr/bin/env python3
"""
tools/generate_gobe_po_dezju_card_variants.py — pet variacij kartice 1080×1350 za objavo članka
»Gobe po dežju 8.–10. oktobra« (ista številka, različna sporočila):

  1 suša    — »18 dni« kot kavelj, tri skupine kot vrstice
  2 vprašanje — »Kdaj po dežju v gozd?«, stopnice po skupinah
  3 dež     — ansambel proti modelu in pragovi dežja po vrstah
  4 koledar — oktober v mreži, dež in okna rasti
  5 foto    — lastna fotografija gob, tri datumi

Podatki so iz istega izračuna kot članek (generate_gobe_po_dezju_post.build_data).

Usage:
    python3 tools/generate_gobe_po_dezju_card_variants.py [--cache FILE] [--out-dir DIR]
"""
import calendar
import datetime
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_gobe_po_dezju_post as post  # noqa: E402
import generate_gobe_po_dezju_card as base  # noqa: E402

font, hexrgb, text_w = base.font, base.hexrgb, base.text_w
W, H, PAD = base.W, base.H, 70
BG, WHITE, MUTED, DIM, PANEL, LINE, GREEN = base.BG, base.WHITE, base.MUTED, base.DIM, base.PANEL, base.LINE, base.GREEN
B, R = "LiberationSans-Bold.ttf", "LiberationSans-Regular.ttf"
ROOT = post.ROOT


def wrap(d, text, f, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if text_w(d, t, f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def canvas(photo=False):
    if photo:
        bg = Image.open(os.path.join(ROOT, "og", "bg", "gobe-lastna.jpg")).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1), Image.LANCZOS)
        x, y = (bg.width - W) // 2, (bg.height - H) // 2
        img = bg.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(2))
        ov = Image.new("RGBA", (W, H))
        od = ImageDraw.Draw(ov)
        for yy in range(H):
            a = int(120 + 120 * yy / H)
            od.line((0, yy, W, yy), fill=(5, 6, 14, min(235, a)))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    else:
        img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def header(img, d, sub):
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((84, 84), Image.LANCZOS)
    img.paste(logo, (PAD, 60), logo)
    d.text((PAD + 106, 60), "METEOREC", font=font(B, 40), fill=WHITE)
    d.text((PAD + 108, 106), sub, font=font(R, 26), fill=MUTED)


def badge(d, text, y=196, fill=GREEN, ink=(4, 20, 14)):
    f = font(B, 24)
    w = text_w(d, text, f) + 40
    d.rounded_rectangle((PAD, y, PAD + w, y + 46), radius=23, fill=fill)
    d.text((PAD + 20, y + 9), text, font=f, fill=ink)


def footer(d, line1, y=1210):
    d.text((PAD, y), line1, font=font(B, 30), fill=WHITE)
    d.text((PAD, y + 46), "Modelova ocena ugodnosti razmer, ni obljuba najdbe.", font=font(R, 27), fill=MUTED)
    d.text((PAD, y + 84), "Grafi, pragovi dežja po vrstah in višina: meteorec.si/blog", font=font(R, 27), fill=MUTED)


EX = {"razkrojevalka": "marela, poljski kukmak", "lesna": "bezgova uhljevka, bukov ostrigar", "mikorizna": "jurček, rumeni ježek",
      "cantharellus_cibarius": "navadna lisička"}
LABEL = {"razkrojevalka": "Razkrojevalke", "lesna": "Lesne vrste", "mikorizna": "Jurček, ježek", "cantharellus_cibarius": "Lisička"}


def entries(D):
    """Skupine in vrste z umerjenim zamikom (lisička), po začetku okna."""
    out = [{"key": e, "name": LABEL[e], "ex": EX[e], "color": post.COLORS[e], "win": D["eco"][e]["win"], "lag": D["eco"][e]["lag"],
            "slug": e} for e in post.ECO_ORDER]
    for x in D["special"]:
        out.append({"key": x["id"], "name": LABEL.get(x["id"], x["name"]), "ex": EX.get(x["id"], x["name"]), "color": post.COLORS[x["eco"]],
                    "win": x["win"], "lag": x["lag"], "slug": x["id"]})
    return sorted(out, key=lambda t: t["win"][0])


def info(D):
    eco, ev, dry = D["eco"], D["ev"], D["R"]["dry"]
    return eco, ev, dry, post.rng(D["d1"], D["d3"])


def v1(D):
    eco, ev, dry, rr = info(D)
    img, d = canvas()
    header(img, d, f"gobe po dežju {rr} 10.".replace("10. 10.", "10."))
    badge(d, "GOBARSKI MODEL")
    d.text((PAD, 250), f"{dry['days']} dni", font=font(B, 230), fill=WHITE)
    y = 520
    for ln in wrap(d, f"brez dežja ({post.mm(dry['sum'])} mm). Zdaj pride dež, a gobe ne takoj.", font(R, 38), W - 2 * PAD):
        d.text((PAD, y), ln, font=font(R, 38), fill=MUTED)
        y += 52
    y = 640
    for en in entries(D):
        col = hexrgb(en["color"])
        d.rounded_rectangle((PAD, y, W - PAD, y + 120), radius=22, fill=PANEL, outline=LINE, width=2)
        d.rounded_rectangle((PAD, y, PAD + 16, y + 120), radius=8, fill=col)
        d.text((PAD + 44, y + 16), en["name"], font=font(B, 34), fill=WHITE)
        d.text((PAD + 44, y + 68), en["ex"], font=font(R, 26), fill=DIM)
        t = post.rng(*en["win"])
        d.text((W - PAD - 28 - text_w(d, t, font(B, 44)), y + 14), t, font=font(B, 44), fill=WHITE)
        z = f"zamik {en['lag'][0]}–{en['lag'][1]} dni"
        d.text((W - PAD - 28 - text_w(d, z, font(R, 25)), y + 72), z, font=font(R, 25), fill=DIM)
        y += 134
    footer(d, f"Dež {rr}: {post.mm(ev['p50'])} mm (ansambel), ARSO {post.mm(ev['arso'])} mm", 1214)
    return img


def v2(D):
    eco, ev, dry, rr = info(D)
    img, d = canvas()
    header(img, d, "kdaj po dežju v gozd")
    badge(d, "GOBARSKI MODEL")
    f = font(B, 92)
    d.text((PAD, 270), "Kdaj po dežju", font=f, fill=WHITE)
    d.text((PAD, 370), "v gozd?", font=f, fill=GREEN)
    labs = ["PRVI", "NATO", "POTEM", "NAZADNJE"]
    y = 530
    for i, en in enumerate(entries(D)):
        x0 = PAD + i * 44
        col = hexrgb(en["color"])
        hi = en["key"] == "mikorizna"
        d.rounded_rectangle((x0, y, W - PAD, y + 148), radius=24, fill=PANEL, outline=GREEN if hi else LINE, width=4 if hi else 2)
        d.text((x0 + 28, y + 14), labs[min(i, 3)], font=font(B, 22), fill=col)
        d.text((x0 + 28, y + 42), post.rng(*en["win"]), font=font(B, 52), fill=WHITE)
        d.text((x0 + 28, y + 108), en["name"] + ": " + en["ex"], font=font(R, 25), fill=MUTED)
        y += 162
    footer(d, f"Dež {rr}, po {dry['days']} suhih dneh. Jurčki: zamik 8–16 dni.", 1214)
    return img


def v3(D):
    eco, ev, dry, rr = info(D)
    img, d = canvas()
    header(img, d, f"dež {rr}")
    badge(d, "ANSAMBEL PROTI MODELU")
    d.text((PAD, 268), "Dva dežja,", font=font(B, 92), fill=WHITE)
    d.text((PAD, 368), "ena napoved.", font=font(B, 92), fill=GREEN)
    cw = (W - 2 * PAD - 30) // 2
    for k, (num, cap) in enumerate([(post.mm(ev["p50"]), "ansambel (mediana)"), (post.mm(D["model_mm"]), "gobarski model")]):
        x0 = PAD + k * (cw + 30)
        d.rounded_rectangle((x0, 520, x0 + cw, 720), radius=24, fill=PANEL, outline=LINE, width=2)
        d.text((x0 + 28, 548), num, font=font(B, 92), fill=WHITE)
        d.text((x0 + 28 + text_w(d, num, font(B, 92)) + 10, 600), "mm", font=font(R, 36), fill=MUTED)
        d.text((x0 + 28, 664), cap, font=font(R, 30), fill=MUTED)
    # pragovi
    px0, px1 = 400, W - PAD - 170
    mx = D["R"] and max(70, int(D["model_mm"] // 10 * 10 + 10))

    def X(v):
        return px0 + v / mx * (px1 - px0)
    y0 = 790
    rows = [r for r in D["species"] if r["id"] in ("pleurotus_ostreatus", "boletus_edulis", "cantharellus_cibarius", "auricularia_auricula_judae")]
    for k, r in enumerate(rows):
        y = y0 + k * 66
        col = hexrgb(post.COLORS[r["eco"]])
        d.text((PAD, y + 4), post.SHORT[r["id"]], font=font(R, 30), fill=WHITE)
        d.rounded_rectangle((px0, y, X(r["thr"]), y + 36), radius=10, fill=col)
        d.text((X(r["thr"]) + 12, y + 2), f"prag {post.thr_s(r['thr'])}", font=font(R, 26), fill=MUTED)
    ytop, ybot = y0 - 12, y0 + len(rows) * 66
    d.line((X(ev["p50"]), ytop, X(ev["p50"]), ybot), fill=WHITE, width=4)
    for yy in range(ytop, ybot, 16):
        d.line((X(D["model_mm"]), yy, X(D["model_mm"]), yy + 8), fill=WHITE, width=3)
    for v in range(0, mx + 1, 10):
        t = str(v)
        d.text((X(v) - text_w(d, t, font(R, 22)) / 2, ybot + 8), t, font=font(R, 22), fill=DIM)
    d.text((PAD, ybot + 40), "mm dežja 8.–10. 10.   │ polna črta: ansambel · črtkana: model", font=font(R, 22), fill=DIM)
    footer(d, "Prag dežja po vrstah: parameter modela, ni umerjen na terenu.", 1214)
    return img


def v4(D):
    eco, ev, dry, rr = info(D)
    img, d = canvas()
    header(img, d, "oktober v gozdu")
    badge(d, "GOBARSKI MODEL")
    d.text((PAD, 268), "Jurčki po dežju?", font=font(B, 84), fill=WHITE)
    d.text((PAD, 366), "Počakajte 8–16 dni.", font=font(B, 84), fill=GREEN)
    first = datetime.date(2026, 10, 1)
    start = first - datetime.timedelta(days=first.weekday())
    gx0, gy0 = PAD, 560
    cw, ch = (W - 2 * PAD) // 7, 112
    for i, n in enumerate(["pon", "tor", "sre", "čet", "pet", "sob", "ned"]):
        d.text((gx0 + i * cw + cw // 2 - text_w(d, n, font(R, 24)) / 2, gy0 - 36), n, font=font(R, 24), fill=DIM)
    wins = {e: tuple(datetime.date.fromisoformat(x) for x in eco[e]["win"]) for e in post.ECO_ORDER}
    lis = [x for x in D["special"] if x["id"] == "cantharellus_cibarius"]
    if lis:
        wins["lisicka"] = tuple(datetime.date.fromisoformat(x) for x in lis[0]["win"])
    r0, r1 = (datetime.date.fromisoformat(D["d1"]), datetime.date.fromisoformat(D["d3"]))
    days = calendar.monthrange(2026, 10)[1]
    for k in range(35):
        day = start + datetime.timedelta(days=k)
        x, y = gx0 + (k % 7) * cw, gy0 + (k // 7) * ch
        inm = day.month == 10
        fill = PANEL
        if r0 <= day <= r1:
            fill = (40, 52, 82)
        if wins["mikorizna"][0] <= day <= wins["mikorizna"][1]:
            fill = (16, 92, 66)
        d.rounded_rectangle((x + 4, y + 4, x + cw - 4, y + ch - 4), radius=14, fill=fill if inm else BG, outline=LINE if inm else BG, width=1)
        if not inm:
            continue
        t = str(day.day)
        d.text((x + 16, y + 12), t, font=font(B, 32), fill=WHITE)
        for j, e in enumerate(("razkrojevalka", "lesna", "lisicka")):
            if e in wins and wins[e][0] <= day <= wins[e][1]:
                d.rounded_rectangle((x + 14, y + 64 + j * 13, x + cw - 14, y + 71 + j * 13), radius=3,
                                    fill=hexrgb(post.COLORS["mikorizna" if e == "lisicka" else e]))
        if day in (r0, r1) or day == r0 + datetime.timedelta(days=1):
            d.text((x + 62, y + 20), "dež", font=font(R, 22), fill=MUTED)
    ly = gy0 + 5 * ch + 24
    items = [((40, 52, 82), "dež 8.–10."), (hexrgb(post.COLORS["razkrojevalka"]), "razkrojevalke"), (hexrgb(post.COLORS["lesna"]), "lesne"), (hexrgb(post.COLORS["mikorizna"]), "lisička"), ((16, 92, 66), "jurček, ježek")]
    x = PAD
    for col, lab in items:
        d.rounded_rectangle((x, ly, x + 28, ly + 28), radius=7, fill=col)
        d.text((x + 38, ly - 2), lab, font=font(R, 26), fill=MUTED)
        x += 38 + text_w(d, lab, font(R, 26)) + 30
    footer(d, f"Po {dry['days']} suhih dneh: dež {post.mm(ev['p50'])} mm (ansambel), ARSO {post.mm(ev['arso'])} mm", 1214)
    return img


def v5(D):
    eco, ev, dry, rr = info(D)
    img, d = canvas(photo=True)
    header(img, d, "gobe po dežju")
    badge(d, "GOBARSKI MODEL")
    f = font(B, 96)
    d.text((PAD, 268), "Dež pride prvi.", font=f, fill=WHITE)
    d.text((PAD, 376), "Gobe za njim.", font=f, fill=GREEN)
    y = 580
    lab5 = {"razkrojevalka": "razkrojevalke", "lesna": "lesne vrste", "cantharellus_cibarius": "lisičke", "mikorizna": "jurčki in ježki"}
    for en in entries(D):
        col = hexrgb(en["color"])
        d.ellipse((PAD, y + 12, PAD + 34, y + 46), fill=col)
        d.text((PAD + 64, y), post.rng(*en["win"]), font=font(B, 62), fill=WHITE)
        d.text((PAD + 64, y + 72), lab5.get(en["key"], en["name"]), font=font(R, 30), fill=MUTED)
        y += 148
    footer(d, f"Po {dry['days']} suhih dneh: dež {post.mm(ev['p50'])} mm (ansambel), ARSO {post.mm(ev['arso'])} mm", 1214)
    return img


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    out = sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else os.path.join(ROOT, "og")
    os.makedirs(out, exist_ok=True)
    D = post.build_data(cache)
    for n, fn in enumerate((v1, v2, v3, v4, v5), 1):
        p = os.path.join(out, f"{post.SLUG}-kartica-{n}.jpg")
        fn(D).save(p, quality=92)
        print("✓", p)


if __name__ == "__main__":
    main()
