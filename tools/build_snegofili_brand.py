#!/usr/bin/env python3
"""Znamka /snegofili/ (smer »Powder«, 19. 11. 2026) — znak, favicon, logotipa in slika za deljenje.

Piše izvorne SVG v snegofili/brand/. PNG iz njih naredi tools/render_snegofili_brand.mjs (Chromium).
Oba koraka sta ROČNA (znamka se ne spreminja ob vsakem teku); generator strani samo kaže na datoteke.

    pip install fonttools brotli
    python3 tools/build_snegofili_brand.py
    NODE_PATH=$(npm root -g) node tools/render_snegofili_brand.mjs

ZNAK: azurna zaobljena ikona z dvema vrhovoma (osenčena in osvetljena stran), snežno kapo, snežinkami in oranžnim
»beaconom« (kot snežni žarilnik): oranžna je v celi podobi barva »tu zdaj sneži«. Prejšnja znamka (snežinka na
temni podlagi) je zamenjana; stran ima zdaj svetlo podobo z majhnimi temnimi »okni s podatki« (karta, prerez, toplotna karta).

Besedilo je v SVG OBRISANO v poti (fontTools): logotip mora biti enak ne glede na pisave.
Pisava: Bricolage Grotesque 800 (podjetja/fonts, spremenljiva os wght) — ista kot naslovi na strani (snegofili/fonts/).
"""
import io
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_crnivec_brand import INTER_600, tp, tw  # noqa: E402  (obrisano besedilo, Inter za podnapis)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "snegofili", "brand")

AZURE, AZURE_D, POWDER, SNOW, INK, BEACON = "#1b6ef3", "#1560de", "#bfe3ff", "#f7fbff", "#0b1b33", "#ff5a1f"
SHADE = "#a9d3ff"


def _bricolage(wght):
    fonts = []
    for sub in ("latin", "latin-ext"):
        t = TTFont(os.path.join(ROOT, "podjetja", "fonts", f"Bricolage-{sub}.woff2"))
        t = instancer.instantiateVariableFont(t, {"wght": wght})
        buf = io.BytesIO()
        t.flavor = None
        t.save(buf)
        buf.seek(0)
        fonts.append(TTFont(buf))
    return fonts


BRICO = _bricolage(800)
TRACK = -0.035  # razmik črk v em


def peaks(simple=False):
    """Gore v mreži 120×120. simple = brez snežne kape in snežink (favicon)."""
    g = [
        # zadnji vrh (desno): osenčena in osvetljena stran
        f'<path d="M56 94L80 48L82 94Z" fill="{SHADE}"/><path d="M80 48L110 94H82Z" fill="#fff"/>',
        # sprednji vrh (levo)
        f'<path d="M10 94L48 32L50 94Z" fill="{SHADE}"/><path d="M48 32L88 94H50Z" fill="#fff"/>',
    ]
    if not simple:
        # snežna kapa z valovitim robom čez osenčeno stran
        g.append('<path d="M48 32L36 52Q40 58 44 52Q48 59 52 52Q55 56 58 51Z" fill="#fff"/>')
        g.append('<path d="M80 48L73 60Q76 64 79 60Q82 65 85 60Z" fill="#fff"/>')
        for x, y, r, o in ((22, 30, 3, 1), (34, 17, 2.2, .85), (60, 21, 2.6, 1), (104, 62, 2, .85), (18, 52, 2, .7), (70, 12, 1.8, .7)):
            g.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" opacity="{o}"/>')
    g.append(f'<circle cx="93" cy="27" r="{8 if not simple else 10}" fill="{BEACON}"/>')
    if not simple:
        g.append(f'<circle cx="93" cy="27" r="14.5" fill="none" stroke="{BEACON}" stroke-width="2"/>')
    return "".join(g)


def mark_inner(simple=False):
    return f'<g transform="scale(4.2667)">{peaks(simple)}</g>'


def defs():
    return (f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f80ff"/>'
            f'<stop offset="1" stop-color="{AZURE_D}"/></linearGradient></defs>')


def mark(rounded=True):
    r = 112 if rounded else 0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" '
            f'aria-label="Snegofili">{defs()}<rect width="512" height="512" rx="{r}" fill="url(#g)"/>{mark_inner()}</svg>')


def maskable():
    # varno območje: znak na 80 %
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">{defs()}'
            f'<rect width="512" height="512" fill="url(#g)"/><g transform="translate(51.2 51.2) scale(.8)">{mark_inner()}</g></svg>')


def favicon():
    # pri 16 px brez snežinke in kape; večji beacon
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            f'<rect width="512" height="512" rx="112" fill="{AZURE}"/>{mark_inner(simple=True)}</svg>')


def wordmark(x, base, size, c1, c2):
    tr = size * TRACK
    w1 = tw("sneg", BRICO, size, tr)
    return (tp("sneg", BRICO, size, x, base, c1, tracking=tr) +
            tp("ofili", BRICO, size, x + w1 + tr, base, c2, tracking=tr)), w1 + tr + tw("ofili", BRICO, size, tr)


def logo(reverse=False, tagline=True):
    """Vodoravni logotip na prozorni podlagi: znak + besedilo. reverse = svetlo besedilo za temne podlage;
    tagline=False = brez podnapisa (hero: podnapis bi bil pri višini 72 px nečitljiv)."""
    size, tx = 150, 262
    wm, w = wordmark(tx, 176, size, "#fff" if reverse else INK, POWDER if reverse else AZURE)
    sub = tp("KJE JE ZDAJ SNEG · ALPSKI LOK", INTER_600, 22, tx + 6, 222, "#d7ebff" if reverse else "#3f5a80", tracking=3.4) if tagline else ""
    h = 260 if tagline else 232
    total = tx + w + 30
    stroke = ' stroke="#fff" stroke-opacity=".45" stroke-width="10"' if reverse else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total:.0f} {h}" width="{total:.0f}" height="{h}" '
            f'role="img" aria-label="Snegofili">{defs()}<g transform="translate(0 {30 if tagline else 4}) scale(.4375)">'
            f'<rect width="512" height="512" rx="112" fill="url(#g)"{stroke}/>{mark_inner()}</g>'
            f'<g transform="translate(0 {0 if tagline else -26})">{wm}{sub}</g></svg>')


def og():
    """Slika za deljenje 1200×630: azurno nebo, sneg, znak, besedna znamka in tri podatkovne ploščice."""
    flakes = "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" opacity="{o}"/>'
        for x, y, r, o in ((90, 70, 5, .9), (210, 130, 3, .7), (330, 50, 4, .8), (470, 110, 6, .9), (640, 60, 3, .7), (760, 150, 4, .8),
                           (900, 70, 5, .9), (1010, 130, 3, .7), (1120, 50, 6, .85), (1170, 190, 3, .7), (60, 220, 3, .6), (1090, 270, 4, .7)))
    wm, _ = wordmark(100, 330, 168, "#fff", POWDER)
    s1 = tp("Kje je zdaj sneg po Alpah", INTER_600, 40, 106, 408, "#e8f3ff")
    s2 = tp("karta · kamere · 96 ur · kam peljem", INTER_600, 28, 106, 456, "#cfe6ff")
    url = tp("METEOREC.SI/SNEGOFILI", INTER_600, 26, 106, 560, "#fff", tracking=4.6)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">'
            f'<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a62dc"/>'
            f'<stop offset="1" stop-color="#3d8bff"/></linearGradient></defs>'
            f'<rect width="1200" height="630" fill="url(#s)"/>{flakes}'
            f'<path d="M880 630L1010 350L1060 630Z" fill="{SHADE}" opacity=".55"/>'
            f'<path d="M940 630L1075 400L1115 470L1160 380L1200 440V630Z" fill="#fff" opacity=".95"/>'
            f'<circle cx="1090" cy="190" r="30" fill="{BEACON}"/><circle cx="1090" cy="190" r="50" fill="none" stroke="{BEACON}" stroke-width="6"/>'
            f'{wm}{s1}{s2}{url}</svg>')


def main():
    os.makedirs(OUT, exist_ok=True)
    files = {"mark.svg": mark(), "mark-maskable.svg": maskable(), "favicon.svg": favicon(),
             "logo-snegofili.svg": logo(), "logo-snegofili-bela.svg": logo(reverse=True), "logo-hero.svg": logo(reverse=True, tagline=False),
             "og.svg": og()}
    for name, svg in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("  →", os.path.relpath(os.path.join(OUT, name), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
