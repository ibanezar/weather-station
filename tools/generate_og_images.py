"""Generate per-article OG images (1200x630) for Meteorec blog articles."""
from PIL import Image, ImageDraw, ImageFont
import os, math

FONT_BOLD    = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
FONT_REGULAR = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'

W, H = 1200, 630
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'og')
os.makedirs(OUT_DIR, exist_ok=True)

ARTICLES = [
    {
        'slug': 'vremenski-povzetek-maj-2026',
        'title': 'Vremenski povzetek\nmaj 2026',
        'subtitle': 'Rečica ob Savinji · IREICA1',
        'section': 'Vremenski povzetki',
        'accent': (14, 165, 233),
    },
    {
        'slug': 'vremenski-povzetek-april-2026',
        'title': 'Vremenski povzetek\napril 2026',
        'subtitle': 'Rečica ob Savinji · IREICA1',
        'section': 'Vremenski povzetki',
        'accent': (14, 165, 233),
    },
    {
        'slug': 'padavinski-vzorci-savinjske-doline',
        'title': 'Padavinski vzorci\nSavinjske doline',
        'subtitle': 'Analiza 6 let meritev · IREICA1',
        'section': 'Analize',
        'accent': (99, 102, 241),
    },
    {
        'slug': 'el-nino-2026',
        'title': 'El Niño 2026',
        'subtitle': 'Super El Niño v zimi 2026/27?',
        'section': 'Analize',
        'accent': (239, 68, 68),
    },
    {
        'slug': 'poplave-2023',
        'title': 'Poplave avgusta 2023\nv Savinjski dolini',
        'subtitle': 'Najhujša naravna nesreča v zgodovini',
        'section': 'Analize',
        'accent': (59, 130, 246),
    },
    {
        'slug': 'vrocinski-val-junij-2026',
        'title': 'Vročinski val\njunija 2026',
        'subtitle': 'Se obeta nov junijski rekord?',
        'section': 'Analize',
        'accent': (245, 158, 11),
    },
    {
        'slug': 'blog',
        'title': 'Blog Meteorec',
        'subtitle': 'Vremenski povzetki in analize · IREICA1',
        'section': 'Blog',
        'accent': (34, 197, 94),
    },
    {
        'slug': 'o-postaji',
        'title': 'O postaji IREICA1',
        'subtitle': 'Rečica ob Savinji · 366 m n.m.',
        'section': 'O postaji',
        'accent': (168, 85, 247),
    },
]


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def make_og(article):
    img = Image.new('RGB', (W, H), (10, 22, 40))
    draw = ImageDraw.Draw(img)

    # Background gradient (dark navy → slightly lighter at bottom)
    bg_top = (10, 22, 40)
    bg_bot = (15, 33, 58)
    for y in range(H):
        t = y / H
        color = lerp_color(bg_top, bg_bot, t)
        draw.line([(0, y), (W, y)], fill=color)

    # Accent bar — left edge
    accent = article['accent']
    bar_w = 8
    draw.rectangle([0, 0, bar_w, H], fill=accent)

    # Subtle accent glow bottom-right
    glow_r = 350
    glow_cx, glow_cy = W - 80, H + 40
    for r in range(glow_r, 0, -4):
        alpha = int(18 * (1 - r / glow_r))
        layer = Image.new('RGB', (W, H), (0, 0, 0))
        ldraw = ImageDraw.Draw(layer)
        ldraw.ellipse(
            [glow_cx - r, glow_cy - r, glow_cx + r, glow_cy + r],
            fill=tuple(min(255, c + 20) for c in accent)
        )
        img = Image.blend(img, layer, alpha / 255)
        draw = ImageDraw.Draw(img)

    # ── Branding top-left ──
    pad = 56
    font_brand  = ImageFont.truetype(FONT_BOLD, 30)
    font_domain = ImageFont.truetype(FONT_REGULAR, 22)
    draw.text((pad + bar_w + 16, pad), 'Meteorec', font=font_brand,
              fill=tuple(min(255, c + 60) for c in accent))
    draw.text((pad + bar_w + 16, pad + 38), 'meteorec.si', font=font_domain,
              fill=(120, 150, 180))

    # ── Article title (centered vertically) ──
    lines = article['title'].split('\n')
    n = len(lines)
    if n == 1 or max(len(l) for l in lines) > 22:
        font_title = ImageFont.truetype(FONT_BOLD, 72)
    else:
        font_title = ImageFont.truetype(FONT_BOLD, 80)

    line_h = font_title.size + 14
    total_h = n * line_h
    y_start = (H - total_h) // 2 + 10

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        y = y_start + i * line_h
        # subtle shadow
        draw.text((x + 3, y + 3), line, font=font_title, fill=(0, 0, 0, 100))
        draw.text((x, y), line, font=font_title, fill=(240, 248, 255))

    # ── Subtitle ──
    font_sub = ImageFont.truetype(FONT_REGULAR, 28)
    sub = article['subtitle']
    bbox = draw.textbbox((0, 0), sub, font=font_sub)
    sw = bbox[2] - bbox[0]
    draw.text(((W - sw) // 2, y_start + n * line_h + 20), sub,
              font=font_sub, fill=(140, 170, 200))

    # ── Section badge bottom-left ──
    font_badge = ImageFont.truetype(FONT_BOLD, 22)
    badge_text = article['section'].upper()
    bx, by = pad + bar_w + 16, H - pad - 10
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox[2] - bbox[0] + 32
    bh = bbox[3] - bbox[1] + 16
    draw.rounded_rectangle([bx, by - bh, bx + bw, by],
                           radius=6,
                           fill=(*accent, 40),
                           outline=(*accent, 120))
    draw.text((bx + 16, by - bh + 8), badge_text, font=font_badge, fill=accent)

    # ── Station badge bottom-right ──
    font_stn = ImageFont.truetype(FONT_REGULAR, 22)
    stn_text = 'IREICA1 · 366 m n.m.'
    bbox = draw.textbbox((0, 0), stn_text, font=font_stn)
    sw2 = bbox[2] - bbox[0]
    draw.text((W - pad - sw2, H - pad + 2), stn_text,
              font=font_stn, fill=(80, 110, 140))

    out_path = os.path.join(OUT_DIR, f"{article['slug']}.jpg")
    img.save(out_path, 'JPEG', quality=92)
    print(f'  ✓ {out_path}')


if __name__ == '__main__':
    print('Generating OG images...')
    for a in ARTICLES:
        make_og(a)
    print('Done.')
