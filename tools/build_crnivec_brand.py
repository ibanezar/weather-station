#!/usr/bin/env python3
"""Znamka crnivec.si — logotip, favicon, ikone PWA in slike za FB stran.

Piše izvorne SVG v crnivec-brand/. Rastrske datoteke (PNG, ICO) iz njih
naredi tools/render_crnivec_brand.mjs (Chromium prek Playwrighta), ki jih
tudi skopira v crnivec-site/. Oba koraka sta ROČNA — znamka se ne spreminja
ob vsakem teku generatorja strani; generator (write_site_files()) samo
skopira že narejene datoteke iz crnivec-brand/.

    python3 tools/build_crnivec_brand.py
    NODE_PATH=$(npm root -g) node tools/render_crnivec_brand.mjs

Znak je ista gora kot maskota na strani (mountain_icon_svg() v
generate_crnivec_page.py): dva vrha s snegom in cik-cak klanec. Barve so
barve strani: rdeča #dc2626 (theme_color), smetanova #fdf6e3 (ozadje),
rumena #fef08a (znak »pozor«), črn obris #111.

Besedilo je v SVG OBRISANO v poti (fontTools), ne <text> — logotip mora
biti enak ne glede na to, katere pisave ima pregledovalnik. Pisavi sta isti
kot na strani: Space Grotesk 700 (fonts/) in Inter (variabilna, iz nje se
naredi primerek želene debeline).
"""
import io
import os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "crnivec-brand")

RED, CREAM, YELLOW, INK, WHITE = "#dc2626", "#fdf6e3", "#fef08a", "#111", "#fff"


# ── Pisave ─────────────────────────────────────────────────────────────────
def _load(name, wght=None):
    fonts = []
    for sub in ("latin", "latin-ext"):
        t = TTFont(os.path.join(ROOT, "fonts", f"{name}-{sub}-normal-{'700' if name == 'SpaceGrotesk' else '400'}.woff2"))
        if wght is not None and "fvar" in t:
            t = instancer.instantiateVariableFont(t, {"wght": wght, "opsz": 32})
            buf = io.BytesIO()
            t.flavor = None
            t.save(buf)
            buf.seek(0)
            t = TTFont(buf)
        fonts.append(t)
    return fonts


GROTESK = _load("SpaceGrotesk")
INTER_800 = _load("Inter", 800)
INTER_600 = _load("Inter", 600)


def text_path(text, fonts, size, x=0.0, y=0.0, anchor="start", tracking=0.0):
    """Vrne (d, širina) za besedilo, obrisano v pot. y je osnovnica."""
    upm = fonts[0]["head"].unitsPerEm
    s = size / upm
    glyphs = []
    width = 0.0
    for ch in text:
        for f in fonts:
            cmap = f.getBestCmap()
            if ord(ch) in cmap:
                gname = cmap[ord(ch)]
                glyphs.append((f, gname, width))
                width += f["hmtx"][gname][0] * s + tracking
                break
        else:
            raise ValueError(f"znaka {ch!r} ni v pisavi")
    width -= tracking
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    parts = []
    for f, gname, gx in glyphs:
        pen = SVGPathPen(f.getGlyphSet())
        tpen = TransformPen(pen, (s, 0, 0, -s, x + gx, y))
        f.getGlyphSet()[gname].draw(tpen)
        d = pen.getCommands()
        if d:
            parts.append(d)
    return " ".join(parts), width


def tp(text, fonts, size, x, y, fill, anchor="start", tracking=0.0, extra=""):
    d, _ = text_path(text, fonts, size, x, y, anchor, tracking)
    return f'<path d="{d}" fill="{fill}"{extra}/>'


def tw(text, fonts, size, tracking=0.0):
    return text_path(text, fonts, size, tracking=tracking)[1]


# ── Gora (iz maskote, viewBox 200×180) ─────────────────────────────────────
def mountain(detail=True, sign=False):
    """Gora maskote v koordinatah 200×180. Brez `detail` (favicon) samo
    silhueta in klanec — sneg in črtkana sredinska črta se pri 16 px zlijeta."""
    # Brez `detail` gora nima obrisa: pri 16 px bi se črn rob zlil s klancem,
    # smetanova na rdeči pa ima kontrasta dovolj sama.
    outline = f' stroke="{INK}" stroke-width="7" stroke-linejoin="round"' if detail else ""
    g = [f'<path d="M10 168 L82 22 L108 64 L134 18 L192 168 Z" fill="{CREAM}"{outline}/>']
    if detail:
        g += [f'<path d="M134 18 L152 48 L138 44 L128 55 L116 46 Z" fill="{WHITE}" stroke="{INK}" '
              f'stroke-width="4.5" stroke-linejoin="round"/>',
              f'<path d="M82 22 L96 46 L84 43 L74 52 L64 44 Z" fill="{WHITE}" stroke="{INK}" '
              f'stroke-width="4.5" stroke-linejoin="round"/>']
    road = "M108 68 L78 92 L112 108 L80 134 L104 150 L92 168"
    g.append(f'<path d="{road}" fill="none" stroke="{INK}" stroke-width="{10 if detail else 16}" '
             f'stroke-linecap="round" stroke-linejoin="round"/>')
    if detail:
        g.append(f'<path d="{road}" fill="none" stroke="{WHITE}" stroke-width="4" stroke-dasharray="1 11" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')
    if sign:
        g.append(f'<g transform="translate(38,150) rotate(-8)">'
                 f'<path d="M0 -20 L18 14 L-18 14 Z" fill="{YELLOW}" stroke="{RED}" stroke-width="5" '
                 f'stroke-linejoin="round"/>'
                 f'<rect x="-2.2" y="-8" width="4.4" height="12" rx="2" fill="{INK}"/>'
                 f'<circle cx="0" cy="8.6" r="2.4" fill="{INK}"/></g>')
    return "".join(g)


def halftone(pid, color=INK, step=16, r=1.3, opacity=1.0):
    return (f'<pattern id="{pid}" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
            f'<circle cx="{step / 2}" cy="{step / 2}" r="{r}" fill="{color}" fill-opacity="{opacity}"/></pattern>')


def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'{f"<defs>{defs}</defs>" if defs else ""}{body}</svg>\n')


# ── Znak ───────────────────────────────────────────────────────────────────
def mark(size=512, detail=True, maskable=False, rounded=True):
    """Znak: gora na rdeči podlagi. Gora sega do spodnjega roba in jo
    podlaga obreže — tako je pri majhni velikosti čim večja.

    maskable: podlaga čez cel kvadrat, gora v varnem krogu (80 %), brez obrisa
    (Android sam obreže v krog/kapljico)."""
    S = 512
    if maskable:
        # varna cona je krog s premerom 0,8·S; gora v kvadratu ~0,56·S
        sc, tx, ty = 1.46, 110, 132
        bg = f'<rect width="{S}" height="{S}" fill="{RED}"/>'
        clip, border = "", ""
        inner = f'<g transform="translate({tx},{ty}) scale({sc})">{mountain(detail)}</g>'
        return svg(S, S, bg + inner).replace(f'width="{S}" height="{S}">', f'width="{size}" height="{size}">', 1)
    bw = 26 if detail else 34                     # obris podlage (favicon debelejši, da pri 16 px ostane)
    rx = 112 if rounded else 0
    half = bw / 2
    box = f'x="{half}" y="{half}" width="{S - bw}" height="{S - bw}" rx="{rx}"'
    if detail:
        sc, tx, ty = 2.34, 22, 110
    else:
        sc, tx, ty = 2.5, 6, 88
    defs = f'<clipPath id="c"><rect {box}/></clipPath>'
    body = (f'<rect {box} fill="{RED}"/>'
            f'<g clip-path="url(#c)"><g transform="translate({tx},{ty}) scale({sc})">{mountain(detail)}</g></g>'
            f'<rect {box} fill="none" stroke="{INK}" stroke-width="{bw}"/>')
    out = svg(S, S, body, defs)
    return out.replace(f'width="{S}" height="{S}">', f'width="{size}" height="{size}">', 1)


# ── Logotip: znak + »crnivec.si« ───────────────────────────────────────────
def wordmark_parts(size):
    w1 = tw("crnivec", GROTESK, size, tracking=-size * 0.02)
    w2 = tw(".si", GROTESK, size, tracking=-size * 0.02)
    return w1, w2


def logo(dark=False):
    """Vodoravni logotip: znak 200×200, desno »crnivec.si« (».si« rdeče).
    `dark` za temno podlago (črke smetanove)."""
    ink = CREAM if dark else INK
    fs = 150
    w1, w2 = wordmark_parts(fs)
    gap = 36
    tx = 200 + gap
    W = int(tx + w1 + w2 + 12)
    H = 200
    base = 146
    m = mark(200).split(">", 1)[1].rsplit("</svg>", 1)[0]   # notranjost znaka
    body = (f'<svg x="0" y="0" width="200" height="200" viewBox="0 0 512 512">{m}</svg>'
            + tp("crnivec", GROTESK, fs, tx, base, ink, tracking=-fs * 0.02)
            + tp(".si", GROTESK, fs, tx + w1 - fs * 0.02, base, RED, tracking=-fs * 0.02))
    return svg(W, H, body)


# ── Facebook ───────────────────────────────────────────────────────────────
def fb_profile():
    """Profilna slika 1080×1080. FB jo obreže v krog in kaže tudi pri 40 px,
    zato samo znak: gora z znakom »pozor«, brez besedila."""
    S = 1080
    body = (f'<rect width="{S}" height="{S}" fill="{RED}"/>'
            f'<rect width="{S}" height="{S}" fill="url(#ht)"/>'
            # gora v krogu: širina ~66 % premera, spodnji rob tik pod središčem kroga + 30 %
            f'<g transform="translate(170,165) scale(3.72)">{mountain(True, sign=True)}</g>')
    defs = halftone("ht", "#7f1d1d", step=28, r=2.6, opacity=0.35)
    return svg(S, S, body, defs)


def chip(x, y, text, fonts, fs, fill, ink=INK, padx=26, h=None, shadow=6):
    w = tw(text, fonts, fs)
    h = h or fs * 1.9
    wbox = w + 2 * padx
    return (f'<rect x="{x + shadow}" y="{y + shadow}" width="{wbox}" height="{h}" rx="{h / 2}" fill="{INK}"/>'
            f'<rect x="{x}" y="{y}" width="{wbox}" height="{h}" rx="{h / 2}" fill="{fill}" stroke="{INK}" stroke-width="5"/>'
            + tp(text, fonts, fs, x + padx, y + h / 2 + fs * 0.36, ink)), wbox


def fb_cover():
    """Naslovnica 1640×624 (FB: namizje 820×312 pri 2×, telefon obreže
    stranice na ~1110×624 v sredini). Vse bistveno je zato v sredinskem pasu
    x 265–1375; levi spodnji kot na namizju prekrije profilna slika."""
    W, H = 1640, 624
    defs = halftone("ht", INK, step=18, r=1.5, opacity=0.9)
    parts = [f'<rect width="{W}" height="{H}" fill="{CREAM}"/>',
             f'<rect width="{W}" height="{H}" fill="url(#ht)" opacity=".16"/>']
    # Sonce + velika gora desno (sega čez spodnji rob)
    parts.append(f'<circle cx="1505" cy="250" r="62" fill="{YELLOW}" stroke="{INK}" stroke-width="7"/>')
    parts.append(f'<g transform="translate(905,58) scale(3.4)">{mountain(True, sign=False)}</g>')
    # »902 m« zastavica na desnem vrhu
    fx, fy = 1360, 108
    parts.append(f'<path d="M{fx} {fy} L{fx} {fy - 70}" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>')
    parts.append(f'<path d="M{fx} {fy - 70} L{fx + 96} {fy - 56} L{fx} {fy - 40} Z" fill="{RED}" stroke="{INK}" '
                 f'stroke-width="5" stroke-linejoin="round"/>')
    # Besedilo levo-sredinsko (od x=300)
    x0 = 300
    eyebrow, _ = chip(x0, 86, "PRELAZ ČRNIVEC · 902 m", INTER_800, 30, YELLOW)
    parts.append(eyebrow)
    fs = 128
    parts.append(tp("Kako je čez", GROTESK, fs, x0 + 5, 290 + 5, INK, tracking=-fs * 0.025))
    parts.append(tp("Kako je čez", GROTESK, fs, x0, 290, INK, tracking=-fs * 0.025))
    # »Črnivec?« rdeče z obrisom in trdo senco
    d, _ = text_path("Črnivec?", GROTESK, fs, x0, 410, tracking=-fs * 0.025)
    d2, _ = text_path("Črnivec?", GROTESK, fs, x0 + 7, 417, tracking=-fs * 0.025)
    parts.append(f'<path d="{d2}" fill="{INK}"/>')
    parts.append(f'<path d="{d}" fill="{RED}" stroke="{INK}" stroke-width="5" stroke-linejoin="round" paint-order="stroke"/>')
    # Čipi
    cx = x0
    for t in ("Kamera", "Vreme", "Stanje ceste"):
        c, w = chip(cx, 462, t, INTER_800, 30, WHITE)
        parts.append(c)
        cx += w + 18
    # crnivec.si spodaj desno od čipov
    fsu = 44
    parts.append(tp("crnivec", GROTESK, fsu, x0 + 2, 580, INK, tracking=-1))
    parts.append(tp(".si", GROTESK, fsu, x0 + 2 + tw("crnivec", GROTESK, fsu, -1) - 1, 580, RED, tracking=-1))
    return svg(W, H, "".join(parts), defs)


def main():
    os.makedirs(OUT, exist_ok=True)
    files = {
        "mark.svg": mark(512, detail=True),
        "favicon.svg": mark(64, detail=False),
        "mark-maskable.svg": mark(512, detail=True, maskable=True),
        "logo-crnivec.svg": logo(),
        "logo-crnivec-dark.svg": logo(dark=True),
        "fb-profile.svg": fb_profile(),
        "fb-cover.svg": fb_cover(),
    }
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  → crnivec-brand/{name}")


if __name__ == "__main__":
    main()
