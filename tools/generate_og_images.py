"""Generate per-article OG images (1200x630) for Meteorec blog articles.

Background photos sourced from Unsplash (free to use, no attribution required).
Source photos stored in og/bg/. Run this script to regenerate all OG images.
"""
from PIL import Image, ImageDraw, ImageFont
import os

FONT_BOLD    = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'

W, H = 1200, 630
SCRIPT_DIR = os.path.dirname(__file__)
BG_DIR  = os.path.join(SCRIPT_DIR, '..', 'og', 'bg')
OUT_DIR = os.path.join(SCRIPT_DIR, '..', 'og')
os.makedirs(OUT_DIR, exist_ok=True)

# Background photos: og/bg/{key}.jpg — sourced from Unsplash (CC0)
# storm-clouds:    unsplash.com/photos/98mac9dxVfM
# misty-valley:    unsplash.com/photos/RFrA46eVE9A
# flood-river:     unsplash.com/photos/dNIAzWFA7iQ
# drought:         unsplash.com/photos/jKPU-Ph1irs
# ocean-storm:     unsplash.com/photos/Cc9IPYJ_BSY
# rain-overcast:   unsplash.com/photos/gih3eKh2cKA
# spring:          unsplash.com/photos/premium_photo-1661878589476
# weather-station: unsplash.com/photos/1598287504038

ARTICLES = [
    {
        'slug': 'vremenski-povzetek-maj-2026',
        'title': 'Vremenski povzetek\nmaj 2026',
        'subtitle': 'Rečica ob Savinji · IREICA1',
        'section': 'Vremenski povzetki',
        'accent': (14, 165, 233),
        'photo': 'spring',
    },
    {
        'slug': 'vremenski-povzetek-april-2026',
        'title': 'Vremenski povzetek\napril 2026',
        'subtitle': 'Rečica ob Savinji · IREICA1',
        'section': 'Vremenski povzetki',
        'accent': (14, 165, 233),
        'photo': 'rain-overcast',
    },
    {
        'slug': 'padavinski-vzorci-savinjske-doline',
        'title': 'Padavinski vzorci\nSavinjske doline',
        'subtitle': 'Analiza 6 let meritev · IREICA1',
        'section': 'Analize',
        'accent': (99, 102, 241),
        'photo': 'misty-valley',
    },
    {
        'slug': 'el-nino-2026',
        'title': 'El Niño 2026',
        'subtitle': 'Super El Niño v zimi 2026/27?',
        'section': 'Analize',
        'accent': (239, 68, 68),
        'photo': 'ocean-storm',
    },
    {
        'slug': 'poplave-2023',
        'title': 'Poplave avgusta 2023\nv Savinjski dolini',
        'subtitle': 'Najhujša naravna nesreča v zgodovini',
        'section': 'Analize',
        'accent': (59, 130, 246),
        'photo': 'flood-river',
    },
    {
        'slug': 'vrocinski-val-junij-2026',
        'title': 'Vročinski val\njunija 2026',
        'subtitle': 'Se obeta nov junijski rekord?',
        'section': 'Analize',
        'accent': (245, 158, 11),
        'photo': 'drought',
    },
    {
        'slug': 'max-temperatura-28-junij-2026',
        'title': '36,2 °C — nov\njunijski rekord',
        'subtitle': '28. junij 2026 · IREICA1',
        'section': 'Analize',
        'accent': (239, 68, 68),
        'photo': 'drought',
    },
    {
        'slug': 'nevihte-toca-hudourniki-julij-2026',
        'title': 'Nevihte, toča in\nhudourniki',
        'subtitle': 'Preobrat 1.–2. julija 2026 · IREICA1',
        'section': 'Napoved',
        'accent': (59, 130, 246),
        'photo': 'storm-clouds',
    },
    {
        'slug': 'topoklima-savinjska-dolina-ireica1',
        'title': 'Topoklimatologija\nSavinjske doline',
        'subtitle': 'Inverzije, vetrovi, vročina · IREICA1',
        'section': 'Analize',
        'accent': (99, 102, 241),
        'photo': 'misty-valley',
    },
    {
        'slug': 'tropske-noci-inverzija-savinjska-dolina',
        'title': 'Tropske noči in\ninverzija v Savinjski dolini',
        'subtitle': 'Zakaj je tvoja noč topla · IREICA1',
        'section': 'Analize',
        'accent': (245, 158, 11),
        'photo': 'night-fog-valley',
    },
    {
        'slug': 'junij-2026-dvoglavi-mesec',
        'title': 'Junij 2026:\ndvoglavi mesec',
        'subtitle': '162 mm dežja in 30,1 °C · IREICA1',
        'section': 'Analize',
        'accent': (77, 159, 248),
        'photo': 'storm-clouds',
    },
    {
        'slug': 'vremenski-povzetek-junij-2026',
        'title': 'Vremenski povzetek\njunij 2026',
        'subtitle': 'Rečica ob Savinji · IREICA1',
        'section': 'Vremenski povzetki',
        'accent': (14, 165, 233),
        'photo': 'rain-overcast',
    },
    {
        'slug': 'junijski-rekord-ireica1-vrocinski-val-2026',
        'title': 'Junijski rekord\nIREICA1',
        'subtitle': 'Vročinski val junija 2026',
        'section': 'Analize',
        'accent': (239, 68, 68),
        'photo': 'drought',
    },
    {
        'slug': 'ekoloska-tveganja-pozarna-ogrozenost-vetrolomi',
        'title': 'Požarna ogroženost\nin vetrolomi',
        'subtitle': 'Ekološka in okoljska tveganja · IREICA1',
        'section': 'Analize',
        'accent': (249, 115, 22),
        'photo': 'drought',
    },
    {
        'slug': 'anatomija-poletne-nevihte-recica-savinji',
        'title': 'Anatomija\npoletne nevihte',
        'subtitle': 'Downburst, rosišče, 16,5 mm dežja · IREICA1',
        'section': 'Analize',
        'accent': (59, 130, 246),
        'photo': 'storm-clouds',
    },
    {
        'slug': 'najhladnejsa-julijska-jutra-recica',
        'title': 'Najhladnejša\njulijska jutra',
        'subtitle': 'Rekord 7,5 °C (14. jul. 2020) · IREICA1',
        'section': 'Analize',
        'accent': (34, 211, 238),
        'photo': 'misty-valley',
    },
    {
        'slug': 'polletni-pregled-2026-ireica1',
        'title': 'Prvo polletje 2026\nna postaji IREICA1',
        'subtitle': 'Pol leta v dveh obrazih · IREICA1',
        'section': 'Analize',
        'accent': (99, 102, 241),
        'photo': 'misty-valley',
    },
    {
        'slug': 'blog',
        'title': 'Blog Meteorec',
        'subtitle': 'Vremenski povzetki in analize · IREICA1',
        'section': 'Blog',
        'accent': (34, 197, 94),
        'photo': 'misty-valley',
    },
    {
        'slug': 'o-postaji',
        'title': 'O postaji IREICA1',
        'subtitle': 'Rečica ob Savinji · 366 m n.m.',
        'section': 'O postaji',
        'accent': (168, 85, 247),
        'photo': 'weather-station',
    },
]


def smart_crop(img, w, h):
    ratio = img.width / img.height
    target = w / h
    if ratio > target:
        new_h, new_w = h, int(ratio * h)
    else:
        new_w, new_h = w, int(w / ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - w) // 2
    y = (new_h - h) // 3  # crop slightly above center
    return img.crop((x, y, x + w, y + h))


def dark_overlay(img):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for row in range(H):
        t = row / H
        center_dist = abs(t - 0.5) * 2
        alpha = int(110 + center_dist * 100)
        d.line([(0, row), (W, row)], fill=(0, 0, 0, alpha))
    result = img.convert('RGBA')
    result = Image.alpha_composite(result, ov)
    return result.convert('RGB')


def make_og(article):
    photo_path = os.path.join(BG_DIR, article['photo'] + '.jpg')
    bg = Image.open(photo_path).convert('RGB')
    bg = smart_crop(bg, W, H)
    img = dark_overlay(bg)
    draw = ImageDraw.Draw(img)

    accent = article['accent']
    pad = 52

    # Accent bar left edge
    draw.rectangle([0, 0, 6, H], fill=accent)

    # Branding top-left
    font_brand  = ImageFont.truetype(FONT_BOLD, 28)
    font_domain = ImageFont.truetype(FONT_REGULAR, 20)
    draw.text((pad, pad), 'Meteorec', font=font_brand,
              fill=tuple(min(255, c + 60) for c in accent))
    draw.text((pad, pad + 36), 'meteorec.si', font=font_domain,
              fill=(210, 225, 245))

    # Article title centered
    lines = article['title'].split('\n')
    n = len(lines)
    font_size = 72 if (n == 1 or max(len(l) for l in lines) > 22) else 82
    font_title = ImageFont.truetype(FONT_BOLD, font_size)
    line_h = font_title.size + 12
    total_h = n * line_h
    y_start = (H - total_h) // 2 + 8

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        y = y_start + i * line_h
        for dx, dy in [(-2,-2),(2,-2),(-2,2),(2,2),(0,3),(3,0),(-3,0),(0,-3)]:
            draw.text((x+dx, y+dy), line, font=font_title, fill=(0, 0, 0))
        draw.text((x, y), line, font=font_title, fill=(255, 255, 255))

    # Subtitle
    font_sub = ImageFont.truetype(FONT_REGULAR, 28)
    sub = article['subtitle']
    bbox = draw.textbbox((0, 0), sub, font=font_sub)
    sw = bbox[2] - bbox[0]
    draw.text(((W - sw) // 2, y_start + n * line_h + 18), sub,
              font=font_sub, fill=(210, 230, 255))

    # Section badge bottom-left
    font_badge = ImageFont.truetype(FONT_BOLD, 20)
    badge_text = article['section'].upper()
    bx, by = pad, H - pad - 8
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox[2] - bbox[0] + 28
    bh = bbox[3] - bbox[1] + 14
    draw.rounded_rectangle([bx, by - bh, bx + bw, by], radius=6,
                           fill=(*accent, 50), outline=(*accent, 210))
    draw.text((bx + 14, by - bh + 7), badge_text, font=font_badge, fill=(255, 255, 255))

    # Station badge bottom-right
    font_stn = ImageFont.truetype(FONT_REGULAR, 20)
    stn_text = 'IREICA1 · 366 m n.m.'
    bbox = draw.textbbox((0, 0), stn_text, font=font_stn)
    sw2 = bbox[2] - bbox[0]
    draw.text((W - pad - sw2, H - pad + 4), stn_text,
              font=font_stn, fill=(190, 210, 230))

    out_path = os.path.join(OUT_DIR, f"{article['slug']}.jpg")
    img.save(out_path, 'JPEG', quality=92)
    print(f'  ✓ {out_path}')


if __name__ == '__main__':
    print('Generating OG images...')
    for a in ARTICLES:
        make_og(a)
    print('Done.')
