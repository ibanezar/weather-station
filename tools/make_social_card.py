#!/usr/bin/env python3
"""
tools/make_social_card.py — kvadratna kartica 1080x1080 za objave na FB/IG,
ki NISO članek.

OG slike člankov (tools/generate_og_images.py) so 1200x630 — Instagram jih
obreže na kvadrat in pri tem odreže naslov. Samostojne dnevne objave (dnevno
dejstvo, kasneje lahko še pragovi/gobe/nevihte) zato dobijo svojo kvadratno
kartico, ki je zasnovana za obrez na kvadrat od začetka.

Ozadje je VEDNO Filipova fotografija: najprej rotacija z Google Drive prek
DRIVE_PHOTO_PATH (tools/fetch_drive_photo.py, ~144 fotografij), ob odpovedi
prenosa pa njegov arhiv v og/bg/ (OWN_PHOTOS). Unsplash stock fotke, ki so
prav tako v og/bg/, so tu prepovedane — objava na FB/IG gre pod njegovim
imenom in mora biti njegova. Obrez `smart_crop` je skupen z OG generatorjem.

Uporaba kot modul:
  from make_social_card import make_card
  make_card("og/social/dejstvo-2026-07-29.jpg", headline="...", badge="...",
            stats=[("Najvišja", "34,5 °C"), ...], accent=(245,158,11),
            photo="drought")

Uporaba iz ukazne vrstice (test):
  python3 tools/make_social_card.py out.jpg "Naslov kartice" "OZNAKA"
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_og_images import smart_crop  # noqa: E402  (rabi pot zgoraj)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
BG_DIR = os.path.join(ROOT, "og", "bg")
OUT_DIR = os.path.join(ROOT, "og", "social")

FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

S = 1080          # stranica kvadrata
PAD = 72
STATION = "IREICA1 · Rečica ob Savinji · 366 m n. m."

# Filipove fotografije v og/bg/ — SAMO te smejo na kartico za FB/IG.
# og/bg/ vsebuje tudi osem Unsplash stock fotk (seznam z URL-ji je na vrhu
# tools/generate_og_images.py); tu so prepovedane, ker gre objava ven pod
# Filipovim imenom. Če dodaš novo lastno fotko v og/bg/, jo dopiši sem.
OWN_PHOTOS = {
    "gobe-inverzija",        # jutranja inverzija nad dolino, oranžen vzhod
    "gobe-lastna",           # gozdna tla
    "istra-nevihta-lastna",  # kopasti oblak nad vasjo, modro nebo
    "megla-recica-lastna",   # reke megle nad Rečico
    "nevihta-2019",          # strela nad dolino
}


def font(path, size):
    return ImageFont.truetype(path, size)


def dark_overlay(img):
    """Temna prevleka — močnejša zgoraj in spodaj, da sta blagovna znamka in
    vrstica meritev berljivi tudi na svetli fotografiji."""
    ov = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for row in range(S):
        t = row / S
        edge = abs(t - 0.5) * 2
        d.line([(0, row), (S, row)], fill=(0, 0, 0, int(120 + edge * 95)))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def load_background(photo):
    """Filipova fotka z Drive, če jo je prejšnji korak workflowa naložil,
    sicer njegova arhivska fotka iz og/bg/ (nikoli stock)."""
    if photo not in OWN_PHOTOS:
        raise ValueError(
            f"{photo!r} ni Filipova fotografija — na kartico za FB/IG smejo samo "
            f"{sorted(OWN_PHOTOS)} ali fotka z Drive rotacije."
        )
    drive_photo = os.environ.get("DRIVE_PHOTO_PATH")
    is_drive = bool(drive_photo and os.path.isfile(drive_photo))
    path = drive_photo if is_drive else os.path.join(BG_DIR, f"{photo}.jpg")
    bg = smart_crop(Image.open(path).convert("RGB"), S, S)
    if is_drive:
        # Enak popravek kot pri OG karticah: surove fotografije so temnejše in
        # manj kontrastne od kuriranega kataloga.
        bg = ImageEnhance.Contrast(bg).enhance(1.25)
        bg = ImageEnhance.Color(bg).enhance(1.2)
        bg = ImageEnhance.Brightness(bg).enhance(1.15)
    return bg


def wrap_lines(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_headline(draw, text, max_w, max_h, start=54, minimum=30):
    """Največja velikost pisave, pri kateri se ovito besedilo še vedno
    prilega — dolžina dejstva niha od ~90 do ~260 znakov."""
    size = start
    while size > minimum:
        fnt = font(FONT_BOLD, size)
        lines = wrap_lines(draw, text, fnt, max_w)
        if len(lines) * (size + 14) <= max_h:
            return fnt, lines
        size -= 2
    fnt = font(FONT_BOLD, minimum)
    return fnt, wrap_lines(draw, text, fnt, max_w)


def outlined(draw, xy, text, fnt, fill=(255, 255, 255)):
    x, y = xy
    for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3), (3, 0), (-3, 0), (0, -3)):
        draw.text((x + dx, y + dy), text, font=fnt, fill=(0, 0, 0))
    draw.text((x, y), text, font=fnt, fill=fill)


def make_card(out_path, headline, badge, stats, accent, photo):
    """Nariše kartico in jo shrani kot JPEG.

    headline — golo besedilo dejstva (brez HTML)
    badge    — oznaka zgoraj levo, npr. "DNEVNO DEJSTVO · 29. JULIJ"
    stats    — seznam parov (oznaka, vrednost) v vrstici na dnu
    accent   — RGB poudarek
    photo    — ime fotke iz og/bg/ (brez .jpg)
    """
    img = dark_overlay(load_background(photo))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 8, S], fill=accent)

    # Blagovna znamka zgoraj levo
    draw.text((PAD, PAD), "Meteorec", font=font(FONT_BOLD, 38),
              fill=tuple(min(255, c + 60) for c in accent))
    draw.text((PAD, PAD + 48), "meteorec.si", font=font(FONT_REGULAR, 26),
              fill=(210, 225, 245))

    # Oznaka pod znamko
    fnt_badge = font(FONT_BOLD, 24)
    bx, by = PAD, PAD + 100
    bb = draw.textbbox((0, 0), badge, font=fnt_badge)
    draw.rounded_rectangle([bx, by, bx + bb[2] + 32, by + bb[3] + 20], radius=8,
                           fill=(*accent, 55), outline=(*accent, 215))
    draw.text((bx + 16, by + 8), badge, font=fnt_badge, fill=(255, 255, 255))

    # Dejstvo — levo poravnano, navpično centrirano med oznako in vrstico meritev
    top = by + 130
    bottom = S - PAD - 150
    fnt_head, lines = fit_headline(draw, headline, S - 2 * PAD, bottom - top)
    line_h = fnt_head.size + 14
    y = top + max(0, (bottom - top - len(lines) * line_h) // 2)
    for line in lines:
        outlined(draw, (PAD, y), line, fnt_head)
        y += line_h

    # Vrstica meritev na dnu
    if stats:
        fnt_val = font(FONT_BOLD, 38)
        fnt_lab = font(FONT_REGULAR, 22)
        col_w = (S - 2 * PAD) // len(stats)
        base = S - PAD - 118
        draw.line([(PAD, base - 26), (S - PAD, base - 26)], fill=(*accent, 160), width=2)
        for i, (label, value) in enumerate(stats):
            x = PAD + i * col_w
            draw.text((x, base), label.upper(), font=fnt_lab, fill=(196, 214, 235))
            outlined(draw, (x, base + 30), value, fnt_val)

    # Postaja na dnu
    fnt_stn = font(FONT_REGULAR, 22)
    sw = draw.textbbox((0, 0), STATION, font=fnt_stn)[2]
    draw.text(((S - sw) // 2, S - PAD + 14), STATION, font=fnt_stn, fill=(190, 210, 230))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, "JPEG", quality=86, optimize=True)
    print(f"Kartica: {out_path}")
    return out_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT_DIR, "test.jpg")
    head = sys.argv[2] if len(sys.argv) > 2 else "Testna kartica za družbena omrežja."
    lab = sys.argv[3] if len(sys.argv) > 3 else "TEST"
    make_card(out, headline=head, badge=lab,
              stats=[("Najvišja", "34,5 °C"), ("Najnižja", "14,1 °C"), ("Padavine", "0,0 mm")],
              accent=(245, 158, 11), photo="gobe-inverzija")
