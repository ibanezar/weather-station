#!/usr/bin/env python3
"""
tools/generate_gobe_suha_tla_card.py — kartica za FB objavo članka »Padlo je 10 mm na suha tla. Zakaj jurčkov še ni?«

Pokončna kartica 1080×1350, isti slog kot kartica »Gobe po dežju« (temna podlaga, logotip, Liberation Sans).
Številke so iz ISTEGA izračuna kot članek (`generate_gobe_suha_tla_post.build_data`), zato se kartica in
stran ne moreta razhajati. Piše og/<slug>-kartica.jpg. Na FB/IG ne objavlja (ročno, kot kartice drugih člankov).
Notranjih meritev ni nikjer.

Usage:
    python3 tools/generate_gobe_suha_tla_card.py [--cache FILE]
"""
import datetime
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_gobe_suha_tla_post as post  # noqa: E402

ROOT = post.ROOT
W, H = 1080, 1350
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
BG = (5, 6, 14)
WHITE = (255, 255, 255)
MUTED = (200, 210, 228)
DIM = (150, 160, 182)
PANEL = (16, 20, 34)
LINE = (44, 52, 74)
TRACK = (34, 42, 64)
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
    rd = post.RAIN_DAY
    D = post.build_data(rd)
    rain = D["rain_mm"]
    S = D["soil"]
    L = D["lags"]
    thr = D["thr"]
    s_before = S[D["before"]]["pct"]
    share = round(100 * rain / thr["boletus_edulis"])
    lis = D["lag_lis"]
    win_lis = post.d_rng(post.d_add(rd, lis[0]), post.d_add(rd, lis[1]))
    win_jur = post.d_rng(post.d_add(rd, L["mikorizna"][0]), post.d_add(rd, L["mikorizna"][1]))

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pad = 70
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA").resize((84, 84), Image.LANCZOS)
    img.paste(logo, (pad, 60), logo)
    d.text((pad + 106, 60), "METEOREC", font=font("LiberationSans-Bold.ttf", 40), fill=WHITE)
    d.text((pad + 108, 106), f"dež {post.d_short(rd)} · postaja IREICA1", font=font("LiberationSans-Regular.ttf", 26), fill=DIM)

    f_badge = font("LiberationSans-Bold.ttf", 24)
    badge = "GOBARSKI MODEL"
    bw = text_w(d, badge, f_badge) + 40
    d.rounded_rectangle((pad, 196, pad + bw, 196 + 46), radius=23, fill=GREEN)
    d.text((pad + 20, 205), badge, font=f_badge, fill=(4, 20, 14))

    f_title = font("LiberationSans-Bold.ttf", 84)
    d.text((pad, 268), f"Padlo je 10 mm", font=f_title, fill=WHITE)
    d.text((pad, 360), "na suha tla.", font=f_title, fill=GREEN)

    f_sub = font("LiberationSans-Regular.ttf", 32)
    d.text((pad, 470), f"Prvi pravi dež po {D['n_dry']} dneh. Za jurčka je to {share} % praga.", font=f_sub, fill=MUTED)

    # ── tabela ──
    px0, py0, px1, py1 = pad, 540, W - pad, 925
    d.rounded_rectangle((px0, py0, px1, py1), radius=26, fill=PANEL, outline=LINE, width=2)
    f_h = font("LiberationSans-Bold.ttf", 22)
    f_name = font("LiberationSans-Bold.ttf", 32)
    f_val = font("LiberationSans-Regular.ttf", 30)
    f_pct = font("LiberationSans-Bold.ttf", 30)
    cx_name, cx_thr, cx_bar0, cx_bar1, cx_win = px0 + 32, px0 + 330, px0 + 372, px0 + 560, px1 - 32
    hy = py0 + 28
    d.text((cx_name, hy), "VRSTA", font=f_h, fill=DIM)
    d.text((cx_thr - text_w(d, "PRAG", f_h), hy), "PRAG", font=f_h, fill=DIM)
    d.text((cx_bar0, hy), "DELEŽ PRAGA", font=f_h, fill=DIM)
    d.text((cx_win - text_w(d, "OKNO RASTI", f_h), hy), "OKNO RASTI", font=f_h, fill=DIM)
    d.line((px0 + 24, hy + 40, px1 - 24, hy + 40), fill=LINE, width=2)
    rows = [("Jurček", "boletus_edulis", post.C_GROUP["mikorizna"], win_jur),
            ("Lisička", "cantharellus_cibarius", post.C_GROUP["mikorizna"], win_lis),
            ("Marela", "macrolepiota_procera", post.C_GROUP["razkrojevalka"],
             post.d_rng(post.d_add(rd, L["razkrojevalka"][0]), post.d_add(rd, L["razkrojevalka"][1])))]
    y = hy + 62
    for name, sid, col, win in rows:
        t = thr[sid]
        frac = min(1.0, rain / t)
        d.text((cx_name, y + 14), name, font=f_name, fill=WHITE)
        tt = f"{int(t)} mm"
        d.text((cx_thr - text_w(d, tt, f_val), y + 16), tt, font=f_val, fill=MUTED)
        d.rounded_rectangle((cx_bar0, y + 22, cx_bar1, y + 52), radius=10, fill=TRACK)
        d.rounded_rectangle((cx_bar0, y + 22, cx_bar0 + (cx_bar1 - cx_bar0) * frac, y + 52), radius=10, fill=hexrgb(col))
        d.text((cx_bar1 + 14, y + 14), f"{round(100 * frac)} %", font=f_pct, fill=WHITE)
        d.text((cx_win - text_w(d, win, f_val), y + 16), win, font=f_val, fill=WHITE)
        y += 94
        if sid != rows[-1][1]:
            d.line((px0 + 24, y - 6, px1 - 24, y - 6), fill=(28, 34, 54), width=1)

    # ── graf: vlaga tal (model) ──
    gx0, gy0, gx1, gy1 = pad, 945, W - pad, 1225
    d.rounded_rectangle((gx0, gy0, gx1, gy1), radius=26, fill=PANEL, outline=LINE, width=2)
    d.text((gx0 + 32, gy0 + 22), "Vlaga tal 3–9 cm (modelska ocena)", font=font("LiberationSans-Bold.ttf", 26), fill=WHITE)
    first = post.d_add(rd, -27)
    last = D["after"][-1]
    days = []
    dd = first
    while dd <= last:
        days.append(dd)
        dd = post.d_add(dd, 1)
    ax0, ax1 = gx0 + 60, gx1 - 40
    ay0, ay1 = gy0 + 104, gy1 - 46
    X = lambda i: ax0 + i * (ax1 - ax0) / (len(days) - 1)
    Y = lambda v: ay1 - (ay1 - ay0) * v / 100.0
    f_ax = font("LiberationSans-Regular.ttf", 22)
    for v in (0, 50, 100):
        d.line((ax0, Y(v), ax1, Y(v)), fill=(34, 42, 64), width=1)
        d.text((ax0 - 10 - text_w(d, f"{v}", f_ax), Y(v) - 13), f"{v}", font=f_ax, fill=DIM)
    pts = [(i, S[x]["pct"]) for i, x in enumerate(days) if x in S and S[x]["pct"] is not None]
    solid = [(i, v) for i, v in pts if days[i] < D["today"]]
    fut = [solid[-1]] + [(i, v) for i, v in pts if days[i] >= D["today"]]
    ir = days.index(rd)
    d.line((X(ir), ay0 - 6, X(ir), ay1), fill=DIM, width=2)
    lbl = f"dež {post.d_short(rd)}"
    d.text((X(ir) - 10 - text_w(d, lbl, f_ax), ay0 - 8), lbl, font=f_ax, fill=DIM)
    d.line([(X(i), Y(v)) for i, v in solid], fill=(232, 236, 239), width=5, joint="curve")
    d.line([(X(i), Y(v)) for i, v in fut], fill=(150, 160, 182), width=5, joint="curve")
    def dot(day, dx, dy):
        i = days.index(day)
        v = S[day]["pct"]
        d.ellipse((X(i) - 8, Y(v) - 8, X(i) + 8, Y(v) + 8), fill=WHITE, outline=PANEL, width=3)
        t = f"{v} %"
        d.text((X(i) + dx - (text_w(d, t, f_pct) if dx < 0 else 0), Y(v) + dy), t, font=f_pct, fill=WHITE)
    dot(D["peak_sept"], 18, -40)
    dot(D["before"], -16, -46)
    dot(D["peak_after"], 0, -46)
    d.text((ax0, ay1 + 8), post.d_short(first), font=f_ax, fill=DIM)
    d.text((ax1 - text_w(d, post.d_short(last), f_ax), ay1 + 8), post.d_short(last), font=f_ax, fill=DIM)

    f_foot = font("LiberationSans-Regular.ttf", 25)
    d.text((pad, 1252), "Dež: meritev postaje. Vlaga tal (siva črta = napoved) in okna rasti: model,", font=f_foot, fill=DIM)
    d.text((pad, 1286), "ni obljuba najdbe. Grafi in razlaga: meteorec.si/blog", font=f_foot, fill=DIM)

    out = os.path.join(ROOT, "og", f"{post.SLUG}-kartica.jpg")
    img.save(out, quality=92)
    print("✓", out)


if __name__ == "__main__":
    main()
