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
    stranice na ~1110×624 v sredini, zato je vse bistveno v pasu x 265–1375).

    V novem videzu strani FB profilno sliko postavi NA SREDINO, čez spodnji
    rob naslovnice. Spodnja sredina (x ~520–1120, y > ~330) mora zato ostati
    prazna: besedilo je zgoraj na sredini, gori pa levo in desno, tako da
    profilna sede v sedlo med njima."""
    W, H = 1640, 624
    CX = W / 2
    defs = halftone("ht", INK, step=18, r=1.5, opacity=0.9)
    parts = [f'<rect width="{W}" height="{H}" fill="{CREAM}"/>',
             f'<rect width="{W}" height="{H}" fill="url(#ht)" opacity=".16"/>']

    # Sonce za desno goro, gori levo in desno (desna zrcaljena), segata čez spodnji rob
    parts.append(f'<circle cx="1405" cy="300" r="56" fill="{YELLOW}" stroke="{INK}" stroke-width="7"/>')
    parts.append(f'<g transform="translate(118,258) scale(2.2)">{mountain(True, sign=True)}</g>')
    parts.append(f'<g transform="translate(1522,258) scale(-2.2,2.2)">{mountain(True)}</g>')
    # zastavica na višjem (desnem) vrhu leve gore
    fx, fy = 118 + 134 * 2.2, 258 + 18 * 2.2
    parts.append(f'<path d="M{fx} {fy} L{fx} {fy - 64}" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>')
    parts.append(f'<path d="M{fx} {fy - 64} L{fx + 80} {fy - 52} L{fx} {fy - 38} Z" fill="{RED}" stroke="{INK}" '
                 f'stroke-width="5" stroke-linejoin="round"/>')

    def chip_c(y, text, fonts, fs, fill, padx=26):
        w = tw(text, fonts, fs) + 2 * padx
        return chip(CX - w / 2, y, text, fonts, fs, fill, padx=padx)[0]

    parts.append(chip_c(38, "PRELAZ ČRNIVEC · 902 m", INTER_800, 28, YELLOW))

    # »Kako je čez Črnivec?« v eni vrstici, sredinsko; »Črnivec?« rdeče z obrisom
    fs, tr, base = 100, -100 * 0.025, 200
    w1 = tw("Kako je čez ", GROTESK, fs, tr)
    w2 = tw("Črnivec?", GROTESK, fs, tr)
    x0 = CX - (w1 + w2) / 2
    parts.append(tp("Kako je čez", GROTESK, fs, x0 + 5, base + 5, INK, tracking=tr))
    parts.append(tp("Kako je čez", GROTESK, fs, x0, base, INK, tracking=tr))
    d, _ = text_path("Črnivec?", GROTESK, fs, x0 + w1, base, tracking=tr)
    d2, _ = text_path("Črnivec?", GROTESK, fs, x0 + w1 + 6, base + 6, tracking=tr)
    parts.append(f'<path d="{d2}" fill="{INK}"/>')
    parts.append(f'<path d="{d}" fill="{RED}" stroke="{INK}" stroke-width="5" stroke-linejoin="round" '
                 f'paint-order="stroke"/>')

    # Čipi v vrsti pod naslovom
    labels = ("Kamera", "Vreme", "Stanje ceste")
    fsc, gap = 28, 16
    widths = [tw(t, INTER_800, fsc) + 52 for t in labels]
    cx = CX - (sum(widths) + gap * (len(labels) - 1)) / 2
    for t, w in zip(labels, widths):
        parts.append(chip(cx, 238, t, INTER_800, fsc, WHITE)[0])
        cx += w + gap

    # crnivec.si na tabli ob desni gori (v pasu, ki ga telefon še pokaže)
    parts.append(chip(1112, 540, "crnivec.si", GROTESK, 40, WHITE, padx=28)[0])
    return svg(W, H, "".join(parts), defs)


def fb_launch(W, H):
    """Objava ob odprtju crnivec.si: 1080×1080 (feed) ali 1080×1920 (zgodba).

    Zgodba ima zgoraj ~250 px in spodaj ~340 px pod gumbi FB/IG, zato je tam
    vsebina med tema pasovoma. Trditve na kartici so samo to, kar stran res
    ima (glej CLAUDE.md, razdelek Črnivec): meritev DRSI, ocena vozišča,
    napoved po urah in 7 dni, termina voženj, kamera."""
    story = H > W
    CX = W / 2
    M = 70
    defs = halftone("ht", INK, step=18, r=1.5, opacity=0.9)
    parts = [f'<rect width="{W}" height="{H}" fill="{CREAM}"/>',
             f'<rect width="{W}" height="{H}" fill="url(#ht)" opacity=".16"/>']

    def chip_c(y, text, fonts, fs, fill, padx=26):
        w = tw(text, fonts, fs) + 2 * padx
        return chip(CX - w / 2, y, text, fonts, fs, fill, padx=padx)[0]

    y = 250 if story else 58
    fs_chip = 34 if story else 30
    parts.append(chip_c(y, "NOVO · PRELAZ ČRNIVEC · 902 m", INTER_800, fs_chip, YELLOW))

    # Naslov v dveh vrsticah, »Črnivec?« rdeče z obrisom (isto kot naslovnica)
    fs = 172 if story else 136
    tr = -fs * 0.025
    lh = fs * 1.02
    b1 = y + fs_chip * 1.9 + fs * 1.02
    parts.append(tp("Kako je čez", GROTESK, fs, CX + 5, b1 + 5, INK, "middle", tr))
    parts.append(tp("Kako je čez", GROTESK, fs, CX, b1, INK, "middle", tr))
    b2 = b1 + lh
    d2, _ = text_path("Črnivec?", GROTESK, fs, CX + 7, b2 + 7, "middle", tr)
    d, _ = text_path("Črnivec?", GROTESK, fs, CX, b2, "middle", tr)
    parts.append(f'<path d="{d2}" fill="{INK}"/>')
    parts.append(f'<path d="{d}" fill="{RED}" stroke="{INK}" stroke-width="6" stroke-linejoin="round" '
                 f'paint-order="stroke"/>')

    # Podnaslov
    fs_sub = 40 if story else 34
    ys = b2 + fs_sub * (2.1 if story else 1.8)
    parts.append(tp("Odločitev v 5 sekundah, preden se odpraviš.", INTER_600, fs_sub, CX, ys, INK, "middle"))

    # Seznam: kaj je na strani
    if story:
        rows = [("Meritev s prelaza", "temperatura, veter, padavine · DRSI na 10 min"),
                ("Ocena vozišča", "suho, mokro, poledica ali sneg"),
                ("Naslednjih 6 ur in 7 dni", "vreme na 902 m, ne v dolini"),
                ("Pot v službo in domov", "6.00–8.00 in 14.00–16.00, 4 dni"),
                ("Kamera v živo", "in povezava na uradno stanje ceste")]
        fs_t, fs_s, rh = 44, 30, 110
    else:
        rows = [("Meritev s prelaza (DRSI)", None),
                ("Ocena vozišča", None),
                ("Napoved za 6 ur in 7 dni", None),
                ("Kamera v živo", None)]
        fs_t, fs_s, rh = 36, 0, 64
    pad = 26 if story else 24
    top = ys + (50 if story else 36)
    ch = pad * 2 + rh * len(rows)
    cw = W - 2 * M
    parts.append(f'<rect x="{M + 8}" y="{top + 8}" width="{cw}" height="{ch}" rx="28" fill="{INK}"/>')
    parts.append(f'<rect x="{M}" y="{top}" width="{cw}" height="{ch}" rx="28" fill="{WHITE}" '
                 f'stroke="{INK}" stroke-width="5"/>')
    r = 26 if story else 21
    for i, (t, s) in enumerate(rows):
        ry = top + pad + rh * i + rh / 2           # sredina vrstice
        cx0 = M + pad + r
        parts.append(f'<circle cx="{cx0}" cy="{ry}" r="{r}" fill="{RED}" stroke="{INK}" stroke-width="4"/>')
        k = r / 26
        parts.append(f'<path d="M{cx0 - 11 * k} {ry + 1 * k} L{cx0 - 3 * k} {ry + 9 * k} L{cx0 + 12 * k} {ry - 8 * k}" '
                     f'fill="none" stroke="{WHITE}" stroke-width="{6 * k}" stroke-linecap="round" '
                     f'stroke-linejoin="round"/>')
        tx = cx0 + r + 26
        if s:
            parts.append(tp(t, INTER_800, fs_t, tx, ry - 4, INK))
            parts.append(tp(s, INTER_600, fs_s, tx, ry + fs_s + 6, "#555"))
        else:
            parts.append(tp(t, INTER_800, fs_t, tx, ry + fs_t * 0.36, INK))
        if i:
            ly = top + pad + rh * i
            parts.append(f'<path d="M{tx} {ly} L{M + cw - pad} {ly}" stroke="{INK}" stroke-opacity=".12" '
                         f'stroke-width="2"/>')

    # Spodaj: gori v kotih (kot na naslovnici), med njima naslov strani
    sc = 1.9 if story else 1.45
    gy = H - 168 * sc
    parts.append(f'<g transform="translate({-30},{gy}) scale({sc})">{mountain(True, sign=True)}</g>')
    parts.append(f'<g transform="translate({W + 30},{gy}) scale({-sc},{sc})">{mountain(True)}</g>')
    fs_url = 84 if story else 72
    wu = tw("crnivec.si", GROTESK, fs_url) + 2 * 40
    hu = fs_url * 1.6
    # zgodba: tik pod seznamom, nad spodnjim pasom z gumbi; feed: ob spodnjem robu
    yu = top + ch + 56 if story else H - hu - 48
    parts.append(chip(CX - wu / 2, yu, "crnivec.si", GROTESK, fs_url, YELLOW, padx=40, h=hu, shadow=8)[0])
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
        "fb-launch-1x1.svg": fb_launch(1080, 1080),
        "fb-launch-9x16.svg": fb_launch(1080, 1920),
    }
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  → crnivec-brand/{name}")


if __name__ == "__main__":
    main()
