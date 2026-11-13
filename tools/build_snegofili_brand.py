#!/usr/bin/env python3
"""Znamka /snegofili/ — znak, favicon, logotip in slika za deljenje.

Piše izvorne SVG v snegofili/brand/. PNG iz njih naredi tools/render_snegofili_brand.mjs (Chromium).
Oba koraka sta ROČNA (znamka se ne spreminja ob vsakem teku); generator strani samo kaže na datoteke.

    python3 tools/build_snegofili_brand.py
    NODE_PATH=$(npm root -g) node tools/render_snegofili_brand.mjs

ZNAK: snežinka, katere šest krakov se konča z »točkami« s karte strani: polna kroga različnih velikosti
(koliko je zapadlo), črtkan obroč (moker sneg), prazen obroč (brez novega snega) in zgoraj bel romb, kot
Rečica na karti. Snežinka torej vzorči Alpe, tako kot stran. Barve so barve karte (lestvica snega je
validirana: --ordinal na #0a1426), podlaga je hero strani (#0a1426).

Besedilo je v SVG OBRISANO v poti (fontTools), ne <text>: logotip mora biti enak ne glede na pisave.
Pisavi sta isti kot drugod: Space Grotesk 700 in Inter 600 (iz fonts/).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_crnivec_brand import GROTESK, INTER_600, tp, tw  # noqa: E402  (pisave in obrisano besedilo)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "snegofili", "brand")

BG, BG2 = "#0a1426", "#18305c"
ICE, WHITE = "#85b9f3", "#f4f9ff"
RAMP = ["#3d73b5", "#5a97dd", "#85b9f3", "#b9d9ff", "#f4f9ff"]
RING = "#7d8da8"


def pol(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def flake(cx=256, cy=256, L=150, sw=15, detail=True):
    """Šest krakov (zgoraj začne z rombom), stranske veje in vozlišča-točke na koncih."""
    g = []
    angles = [-90, -30, 30, 90, 150, 210]
    for i, a in enumerate(angles):
        x1, y1 = pol(cx, cy, L, a)
        g.append(f'<path d="M{cx} {cy}L{x1:.1f} {y1:.1f}" stroke="{ICE}" stroke-width="{sw}" stroke-linecap="round"/>')
        if detail:
            for frac, ln in ((0.46, 0.30), (0.72, 0.20)):
                bx, by = pol(cx, cy, L * frac, a)
                for s in (-1, 1):
                    ex, ey = pol(bx, by, L * ln, a + s * 58)
                    g.append(f'<path d="M{bx:.1f} {by:.1f}L{ex:.1f} {ey:.1f}" stroke="{ICE}" '
                             f'stroke-width="{sw * 0.8:.1f}" stroke-linecap="round"/>')
    # vozlišča (točke s karte): romb = Rečica, polni krogi po količini snega, črtkan in prazen obroč
    nodes = [(-90, "diamond", 0), (-30, "dot", (RAMP[1], 21)), (30, "dot", (RAMP[3], 15)),
             (90, "ring", 0), (150, "dot", (RAMP[0], 27)), (210, "dash", 0)]
    for a, kind, spec in nodes:
        x, y = pol(cx, cy, L + 4, a)
        if kind == "diamond":
            g.append(f'<path d="M{x:.1f} {y - 27:.1f}l24 27l-24 27l-24 -27z" fill="{WHITE}" stroke="{BG}" stroke-width="6" stroke-linejoin="round"/>')
        elif kind == "dot":
            col, r = spec
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}" stroke="{BG}" stroke-width="6"/>')
        elif kind == "ring":
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="{BG}" stroke="{RING}" stroke-width="7"/>')
        else:
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="19" fill="{BG}" stroke="{WHITE}" stroke-width="6.5" stroke-dasharray="9 6"/>')
    g.append(f'<circle cx="{cx}" cy="{cy}" r="22" fill="{WHITE}" stroke="{BG}" stroke-width="6"/>')
    return "".join(g)


def defs():
    return (f'<defs><radialGradient id="g" cx="82%" cy="-8%" r="120%"><stop offset="0" stop-color="{BG2}"/>'
            f'<stop offset=".62" stop-color="{BG}"/></radialGradient></defs>')


def mark(rounded=True):
    r = 112 if rounded else 0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" '
            f'aria-label="Snegofili">{defs()}<rect width="512" height="512" rx="{r}" fill="url(#g)"/>{flake()}</svg>')


def maskable():
    # varno območje: znak na 80 %
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">{defs()}'
            f'<rect width="512" height="512" fill="url(#g)"/><g transform="translate(51.2 51.2) scale(.8)">{flake()}</g></svg>')


def favicon():
    # pri 16 px brez stranskih vej; debelejši kraki in večja vozlišča
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">{defs()}'
            f'<rect width="512" height="512" rx="112" fill="{BG}"/>{flake(L=140, sw=34, detail=False)}</svg>')


def logo():
    """Vodoravni logotip na prozorni podlagi: znak (zaobljen kvadrat) + besedilo."""
    size = 120
    w1 = tw("Sneg", GROTESK, size, 0)
    tx = 232
    t = tp("Sneg", GROTESK, size, tx, 150, WHITE) + tp("ofili", GROTESK, size, tx + w1, 150, ICE)
    sub = tp("KJE JE ZDAJ SNEG · ALPSKI LOK", INTER_600, 20, tx + 4, 196, "#9fb2d4", tracking=3.2)
    total = tx + w1 + tw("ofili", GROTESK, size, 0) + 24
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total:.0f} 240" width="{total:.0f}" height="240" '
            f'role="img" aria-label="Snegofili">{defs()}<g transform="translate(0 20) scale(.4)">'
            f'<rect width="512" height="512" rx="112" fill="url(#g)"/>{flake()}</g>{t}{sub}</svg>')


def og():
    """Slika za deljenje 1200×630."""
    big = tp("Snegofili", GROTESK, 132, 520, 300, WHITE)
    s1 = tp("Kje je zdaj sneg po Alpah:", INTER_600, 38, 524, 372, "#c9d6ee")
    s2 = tp("karta, prerez, drsnik in kamere", INTER_600, 38, 524, 424, "#c9d6ee")
    s3 = tp("METEOREC.SI/SNEGOFILI", INTER_600, 24, 524, 540, ICE, tracking=4)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">{defs()}'
            f'<rect width="1200" height="630" fill="url(#g)"/>'
            f'<g transform="translate(40 55) scale(.9)">{flake()}</g>{big}{s1}{s2}{s3}</svg>')


def main():
    os.makedirs(OUT, exist_ok=True)
    files = {"mark.svg": mark(), "mark-maskable.svg": maskable(), "favicon.svg": favicon(),
             "logo-snegofili.svg": logo(), "og.svg": og()}
    for name, svg in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("  →", os.path.relpath(os.path.join(OUT, name), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
