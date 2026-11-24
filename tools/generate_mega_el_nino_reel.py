#!/usr/bin/env python3
"""
tools/generate_mega_el_nino_reel.py -- pet navpičnih slik 1080×1920 za reel/zgodbo ob članku »Mega El Niño« (24. 11. 2026).

Različice (enostavni jezik, brez strokovnih izrazov; vsaka ima eno sporočilo):
  1 naslov-resnica  »V naslovih 10 °C, v resnici +3,3 °C« (dve veliki številki)
  2 pika-pas        pikčast Pacifik: ozka pika (+10 °C) proti širokemu pasu (+3,3 °C)
  3 drzi            »Kaj drži?«: štiri trditve s kljukico ali križcem
  4 zima            »Kaj to pomeni za našo zimo?«: tehtnica, nagnjena k toplejši zimi
  5 rekord          letošnja črta proti letom 1997 in 2015 ob istem času leta (ONI iz data/el-nino-mega-1124.json)

Vsebina je v varnem območju reela (y 250–1560: zgoraj in spodaj prekrije vmesnik aplikacije). Številke so iz članka:
  +3,3 °C  tedensko odstopanje v Niño 3.4, tradicionalno (OISST, NOAA CPC; teden 15.–21. 11. 2026)
  ≈ +10 °C lokalna konica na dnevnem zemljevidu ECMWF (Ryan Maue, 22. 11. 2026; zemljevida nisem preveril)
  +3,21 °C oktobrsko mesečno odstopanje po ERA5 (Copernicus); +2,46 °C ONI za avg–okt (NOAA CPC)
Risanje je v dvojni ločljivosti in pomanjšano (gladki robovi). Pisava: Inter (/usr/share/fonts/opentype/inter/).

Usage:  python3 tools/generate_mega_el_nino_reel.py
"""
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "og", "reel")
FONT_DIR = "/usr/share/fonts/opentype/inter/"
W, H, K = 1080, 1920, 2
BG, INK, MUTED, DIM = (7, 11, 22), (232, 237, 248), (173, 192, 216), (24, 32, 52)
BLUE, ORANGE, AQUA, GREEN, RED = (57, 135, 229), (217, 89, 38), (25, 158, 112), (30, 170, 90), (230, 90, 90)
LEFT = 72


class Canvas:
    """Risanje v koordinatah 1080×1920; slika je interno K-krat večja."""

    def __init__(self):
        self.img = Image.new("RGB", (W * K, H * K), BG)
        self.d = ImageDraw.Draw(self.img)
        self._f = {}

    def font(self, weight, size):
        key = (weight, size)
        if key not in self._f:
            self._f[key] = ImageFont.truetype(FONT_DIR + f"Inter-{weight}.otf", size * K)
        return self._f[key]

    def text(self, x, y, s, size, weight="Medium", fill=INK, anchor="la"):
        self.d.text((x * K, y * K), s, font=self.font(weight, size), fill=fill, anchor=anchor)

    def width(self, s, size, weight="Medium"):
        return self.d.textlength(s, font=self.font(weight, size)) / K

    def rrect(self, box, r, fill=None, outline=None, width=0):
        self.d.rounded_rectangle([v * K for v in box], radius=r * K, fill=fill, outline=outline, width=width * K)

    def ellipse(self, box, fill=None, outline=None, width=0):
        self.d.ellipse([v * K for v in box], fill=fill, outline=outline, width=width * K)

    def line(self, pts, fill, width, joint="curve"):
        self.d.line([(x * K, y * K) for x, y in pts], fill=fill, width=int(width * K), joint=joint)

    def glow(self, cx, cy, rx, ry, color, strength=1.0, blur=80):
        g = Image.new("RGB", self.img.size, (0, 0, 0))
        ImageDraw.Draw(g).ellipse(((cx - rx) * K, (cy - ry) * K, (cx + rx) * K, (cy + ry) * K), fill=color)
        g = g.filter(ImageFilter.GaussianBlur(blur * K))
        mask = g.convert("L").point(lambda v: min(255, int(v * strength)))
        self.img = Image.composite(g, self.img, mask)
        self.d = ImageDraw.Draw(self.img)

    def save(self, name):
        os.makedirs(OUTDIR, exist_ok=True)
        path = os.path.join(OUTDIR, name)
        self.img.resize((W, H), Image.LANCZOS).save(path, quality=93)
        print("✓", os.path.relpath(path, ROOT))


def frame(c, eyebrow, source):
    c.text(LEFT, 272, eyebrow, 32, "Bold", ORANGE)
    c.text(LEFT, 1500, f"Vir: {source}", 28, "Medium", MUTED)
    c.text(W - LEFT, 1500, "meteorec.si", 28, "Bold", INK, "ra")


def check(c, cx, cy, ok, r=48):
    col = GREEN if ok else RED
    c.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    if ok:
        c.line([(cx - r * .45, cy + r * .02), (cx - r * .1, cy + r * .38), (cx + r * .52, cy - r * .36)], (255, 255, 255), 11)
    else:
        a = r * .36
        c.line([(cx - a, cy - a), (cx + a, cy + a)], (255, 255, 255), 11)
        c.line([(cx - a, cy + a), (cx + a, cy - a)], (255, 255, 255), 11)


def dotmap(c, mask, x0, y0, cell, dot=(84, 102, 134)):
    cols, rows = list(range(100, 120)) + list(range(0, 40)), list(range(17, 37))
    R = mask["rows"]
    for ri, r in enumerate(rows):
        for ci, col in enumerate(cols):
            if R[r][col] == "1":
                x, y = x0 + (ci + .5) * cell, y0 + (ri + .5) * cell
                c.ellipse((x - cell * .27, y - cell * .27, x + cell * .27, y + cell * .27), fill=dot)


# 1 ─────────────────────────────────────────────
def v1(c, d):
    n34 = d["nino_weekly"]["trad"][-1][2]
    assert n34 == 3.3
    frame(c, "EL NIÑO · 24. 11. 2026", "NOAA CPC, ECMWF")
    size = 300
    while max(c.width("10 °C", size, "ExtraBold"), c.width("+3,3 °C", size, "ExtraBold")) > W - 2 * LEFT:
        size -= 10
    cap = lambda by: by + int(size * 1.12) + 24
    c.text(LEFT, 330, "V NASLOVIH", 38, "Bold", MUTED)
    c.text(LEFT - 6, 372, "10 °C", size, "ExtraBold", ORANGE)
    c.text(LEFT, cap(372), "ozek pas vode ob Peruju", 48, "SemiBold", INK)
    c.text(LEFT, cap(372) + 64, "na enem dnevnem zemljevidu", 38, "Medium", MUTED)
    c.line([(LEFT, 868), (W - LEFT, 868)], (40, 52, 80), 3)
    c.text(LEFT, 902, "V RESNICI", 38, "Bold", MUTED)
    c.text(LEFT - 6, 952, "+3,3 °C", size, "ExtraBold", BLUE)
    c.text(LEFT, cap(952), "povprečje čez osrednji Pacifik", 48, "SemiBold", INK)
    c.text(LEFT, cap(952) + 64, "(tedensko, uradni kazalnik)", 38, "Medium", MUTED)
    c.text(LEFT, 1420, "Isti El Niño, drugo merilo.", 40, "Bold", ORANGE)


# 2 ─────────────────────────────────────────────
def v2(c, d, mask):
    frame(c, "EL NIÑO · 24. 11. 2026", "NOAA CPC, ECMWF (po Ryanu Maueju)")
    c.text(LEFT, 340, "Kje je tisti", 104, "ExtraBold")
    c.text(LEFT, 462, "»10 °C«?", 104, "ExtraBold", ORANGE)
    cell, y0 = W / 60, 660
    X = lambda lon: (lon - 120) / 3 * cell
    ey = y0 + 10 * cell
    c.glow(X(269) + 20, ey, 260, 130, (170, 62, 20), 1.3)
    # širok pas (Niño 3.4: 170°–120° Z, 5° S–5° J)
    c.rrect((X(190), ey - 5 / 3 * cell, X(240), ey + 5 / 3 * cell), 10, fill=(30, 66, 120), outline=BLUE, width=5)
    dotmap(c, mask, 0, y0, cell)
    gx = X(269)
    c.ellipse((gx - 40, ey - 40, gx + 40, ey + 40), outline=ORANGE, width=7)
    c.ellipse((gx - 15, ey - 15, gx + 15, ey + 15), fill=ORANGE)
    # razlaga
    c.ellipse((LEFT, 1106, LEFT + 40, 1146), fill=ORANGE)
    c.text(LEFT + 66, 1090, "ozka pika ob Peruju", 46, "Bold")
    c.text(LEFT + 66, 1148, "≈ +10 °C", 66, "ExtraBold", ORANGE)
    c.rrect((LEFT, 1290, LEFT + 70, 1332), 8, fill=(30, 66, 120), outline=BLUE, width=4)
    c.text(LEFT + 96, 1274, "širok pas čez Pacifik", 46, "Bold")
    c.text(LEFT + 96, 1332, "povprečje +3,3 °C", 66, "ExtraBold", BLUE)
    c.text(LEFT, 1440, "Pika ni ni v merilu. Naslovi so pokazali piko, ne pasu.".replace("ni ni", "ni"), 30, "Medium", MUTED)


# 3 ─────────────────────────────────────────────
def v3(c, d):
    frame(c, "EL NIÑO · 24. 11. 2026", "NOAA CPC, Copernicus, BoM")
    c.text(LEFT, 340, "»Mega El Niño«:", 100, "ExtraBold")
    c.text(LEFT, 458, "kaj drži?", 100, "ExtraBold", ORANGE)
    rows = [
        (False, "Ves Pacifik je 10 °C toplejši", "Drži le za ozko točko"),
        (True, "Rekordna temperatura morja", "oktobra +3,21 °C, največ doslej"),
        (False, "»Mega« je uradna stopnja", "Uradno: »zelo močan« El Niño"),
        (True, "Vrh šele pričakujemo", "december ali januar"),
    ]
    for i, (ok, a, b) in enumerate(rows):
        y = 690 + i * 205
        check(c, LEFT + 50, y + 52, ok)
        c.text(LEFT + 130, y, a, 46, "Bold")
        c.text(LEFT + 130, y + 64, b, 38, "Medium", MUTED)


# 4 ─────────────────────────────────────────────
def v4(c, d):
    frame(c, "EL NIÑO · ZIMA 2026/27", "Copernicus C3S, ARSO")
    c.text(LEFT, 340, "Kaj to pomeni", 104, "ExtraBold")
    c.text(LEFT, 462, "za našo zimo?", 104, "ExtraBold", ORANGE)
    x0, x1, y, h = LEFT, W - LEFT, 800, 120
    seg = (x1 - x0) / 3
    cols = [(BLUE, "hladnejša"), ((84, 102, 134), "običajna"), (ORANGE, "toplejša")]
    for i, (col, lab) in enumerate(cols):
        c.rrect((x0 + i * seg + 4, y, x0 + (i + 1) * seg - 4, y + h), 24, fill=col)
        c.text(x0 + i * seg + seg / 2, y + h / 2 - 22, lab, 42, "Bold", (255, 255, 255) if i != 1 else INK, "ma")
    # kazalec, nagnjen k toplejši strani
    mx = x0 + seg * 2.35
    c.d.polygon([(mx * K, (y + h + 18) * K), ((mx - 34) * K, (y + h + 84) * K), ((mx + 34) * K, (y + h + 84) * K)], fill=INK)
    c.text(mx, y + h + 100, "verjetneje", 44, "Bold", INK, "ma")
    c.text(LEFT, 1130, "Toplejša in bolj namočena.", 56, "ExtraBold")
    c.text(LEFT, 1210, "Zagotovljeno pa ni:", 46, "Bold", ORANGE)
    c.text(LEFT, 1270, "hladni vdori in sneg ostajajo mogoči.", 42, "Medium", MUTED)
    c.text(LEFT, 1380, "Tehtnica je nagnjena, ne zaklenjena.", 36, "Medium", MUTED)


# 5 ─────────────────────────────────────────────
def v5(c, d):
    oni = d["oni"]
    A = 8
    assert oni["2026"][A] == 2.46 and oni["1997"][A] < 2.46 and oni["2015"][A] < 2.46
    frame(c, "EL NIÑO · 24. 11. 2026", "NOAA CPC (ONI)")
    c.text(LEFT, 340, "Letos je morje", 100, "ExtraBold")
    c.text(LEFT, 456, "najtoplejše doslej", 100, "ExtraBold", ORANGE)
    c.text(LEFT, 572, "ob istem času leta (od 1950)", 40, "Medium", MUTED)
    gx0, gx1, gy0, gy1 = 140, 960, 690, 1260
    ymin, ymax = -0.5, 3.4
    Xi = lambda i: gx0 + (gx1 - gx0) * i / 14
    Yv = lambda v: gy1 - (gy1 - gy0) * (v - ymin) / (ymax - ymin)
    for v in (0, 1, 2):
        c.line([(gx0, Yv(v)), (gx1, Yv(v))], (46, 58, 86) if v else (120, 132, 160), 2)
        c.text(gx0 - 14, Yv(v) - 18, ("+" if v else "") + str(v), 30, "Medium", MUTED, "ra")
    for i, lab in ((0, "jan"), (4, "maj"), (8, "sep"), (12, "jan")):
        c.text(Xi(i), gy1 + 26, lab, 30, "Medium", MUTED, "ma")
    for y, col, lab in (("1997", ORANGE, "1997"), ("2015", AQUA, "2015")):
        pts = [(Xi(i), Yv(v)) for i, v in enumerate(oni[y][:15])]
        c.line(pts, col, 7)
        c.text(pts[-1][0] + 14, pts[-1][1] - 18, lab, 36, "Bold", col)
    pts = [(Xi(i), Yv(v)) for i, v in enumerate(oni["2026"])]
    c.line(pts, INK, 14)
    ex, ey = pts[-1]
    c.ellipse((ex - 20, ey - 20, ex + 20, ey + 20), fill=INK, outline=BG, width=5)
    c.text(ex - 30, ey - 120, "2026: +2,46 °C", 50, "ExtraBold", INK, "ra")
    c.text(ex - 30, ey - 64, "rekord za ta čas leta", 34, "Medium", MUTED, "ra")
    c.text(LEFT, 1380, "Temperatura morja v osrednjem Pacifiku,", 32, "Medium", MUTED)
    c.text(LEFT, 1422, "nad običajno, v °C (tromesečno povprečje).", 32, "Medium", MUTED)


def main():
    d = json.load(open(os.path.join(ROOT, "data", "el-nino-mega-1124.json"), encoding="utf-8"))
    mask = json.load(open(os.path.join(ROOT, "365-0-game", "src", "data", "worldmask.json"), encoding="utf-8"))
    for name, fn in (("1-naslov-resnica", lambda c: v1(c, d)), ("2-pika-pas", lambda c: v2(c, d, mask)),
                     ("3-drzi", lambda c: v3(c, d)), ("4-zima", lambda c: v4(c, d)), ("5-rekord", lambda c: v5(c, d))):
        c = Canvas()
        fn(c)
        c.save(f"mega-el-nino-1124-{name}.jpg")


if __name__ == "__main__":
    main()
