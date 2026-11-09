#!/usr/bin/env python3
"""
tools/generate_sneg_nizine_story_video.py -- animirana zgodba 1080×1920 (MP4, ~10,5 s, 30 sl./s) k članku
»Sneg v nižinah: četrtek še dež, odločitev v noči na soboto« (isti motiv kot statična zgodba 2: bloki dan za dnem).

Časovnica:
  0,0 s  udarni naslov »BO V NIŽINAH SNEG?« (že v prvem kadru, da je predogled poln), v ozadju sneži
  1,4 s  naslov odide (poveča se in zbledi), zgoraj ga nadomesti ozka vrstica
  1,9 s  blok ČETRTEK drsi z desne, v njem dež
  3,4 s  blok PETEK drsi z leve, dež; »okoli N mm« se naštete
  5,0 s  blok SOBOTA se dvigne, »SNEG?« ob sprejemu udari in dvakrat utripne, v bloku sneži
  6,4 s  številki 16 % in 59 % se naštejeta
  7,6 s  znamka in opozorilo; do 10,5 s obdržano

Številke so iz ISTEGA posnetka kot članek in kartice (stats() zažene build_article, zato veljajo iste varovalke).
Zgodbe nimajo podpisa: vse je na sliki. Zvoka ni (tihi AAC zapis je zaradi združljivosti). Na FB/IG ne objavlja.

Usage:
    python3 tools/generate_sneg_nizine_story_video.py [--out FILE] [--poster]
"""
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_sneg_nizine_story_variants as st  # noqa: E402

cards = st.cards
post = st.post
ROOT = st.ROOT
W, H, PAD = st.W, st.H, st.PAD
font, text_w, fit = st.font, st.text_w, st.fit
B, R = st.B, st.R
BG, WHITE, INK, SNOW, RAIN, CYAN = st.BG, st.WHITE, st.INK, st.SNOW, st.RAIN, st.CYAN
FPS, DUR = 30, 10.5
BW = W - 2 * PAD
LAYOUT = {"b1": (520, 280), "b2": (820, 280), "b3": (1120, 440)}


# ───────────────────────── gibanje ─────────────────────────

def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 3 * x * x - 2 * x ** 3


def back_out(x):
    x = clamp01(x)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def seg(t, a, b):
    return clamp01((t - a) / (b - a))


def bump(t, t0, d=0.5):
    return math.sin(math.pi * (t - t0) / d) if t0 <= t <= t0 + d else 0.0


# ───────────────────────── ozadje in delci ─────────────────────────

def make_bg():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(int(5 + 6 * t), int(6 + 14 * t), int(14 + 30 * t)))
    return img


class Flakes:
    def __init__(self, n, w, h, seed, rmin=2.0, rmax=6.0, vmin=70, vmax=190):
        r = random.Random(seed)
        self.w, self.h = w, h
        self.f = [(r.random() * w, r.random() * h, r.uniform(vmin, vmax), r.uniform(rmin, rmax), r.random() * 6.28, r.uniform(8, 34)) for _ in range(n)]

    def draw(self, d, t, col_fn):
        for x0, y0, v, rad, ph, amp in self.f:
            y = (y0 + v * t) % (self.h + 20) - 10
            x = (x0 + amp * math.sin(t * 1.3 + ph)) % self.w
            d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=col_fn(rad))


def snow_col(rad):
    op = 0.35 + 0.65 * (rad - 2.0) / 4.0
    c = int(30 + 215 * op)
    return (c, min(255, c + 6), min(255, c + 14))


# ───────────────────────── sloji ─────────────────────────

def hero_layer():
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    f1, s1 = fit(d, "BO V NIŽINAH", B, BW, 112)
    f2, s2 = fit(d, "SNEG?", B, BW, 430)
    lh1, lh2 = int(s1 * 1.2), int(s2 * 1.05)
    img = Image.new("RGBA", (BW + 40, lh1 + lh2 + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((20, 0), "BO V NIŽINAH", font=f1, fill=WHITE)
    d.text((14, lh1 - int(s2 * 0.08)), "SNEG?", font=f2, fill=WHITE)
    return img


def title_layer():
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    f, s = fit(d, "BO V NIŽINAH SNEG?", B, BW, 96)
    img = Image.new("RGBA", (BW, int(s * 1.3)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((0, 0), "BO V NIŽINAH SNEG?", font=f, fill=WHITE)
    return img


def rounded_mask(w, h, r=36):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return m


RAIN_FX = [(random.Random(3).random(), 0) for _ in range(1)]


def rain_fx(w, h, t, seed):
    r = random.Random(seed)
    fx = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)
    for _ in range(64):
        x0, y0, v = r.random() * (w + 60), r.random() * (h + 80), r.uniform(560, 1000)
        y = (y0 + v * t) % (h + 80) - 40
        x = (x0 - 0.22 * v * t) % (w + 60)
        d.line((x, y, x - 10, y + 38), fill=(170, 205, 255, 120), width=3)
    return fx


def snow_fx(w, h, t):
    fx = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)
    for x0, y0, v, rad, ph, amp in SNOWBLOCK.f:
        y = (y0 + 0.55 * v * t) % (h + 20) - 10
        x = (x0 + amp * math.sin(t * 1.4 + ph)) % w
        rr = rad * 1.5
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(120, 165, 225, 150))
    return fx


SNOWBLOCK = Flakes(46, BW, 440, 11, 2.2, 6.0, 50, 140)
BGFLAKES = Flakes(150, W, H, 5)


def block_layer(kind, S, t):
    """Blok v lokalnem koordinatnem sistemu (BW×h), glede na čas t (sekunde od začetka animacije)."""
    y0, h = LAYOUT[kind]
    img = Image.new("RGBA", (BW, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    mask = rounded_mask(BW, h)
    fill = {"b1": RAIN, "b2": (28, 70, 150), "b3": SNOW}[kind]
    d.rounded_rectangle((0, 0, BW - 1, h - 1), radius=36, fill=fill)
    if kind in ("b1", "b2"):
        fx = rain_fx(BW, h, t, 21 if kind == "b1" else 22)
    else:
        fx = snow_fx(BW, h, t)
    fx.putalpha(ImageChops.multiply(fx.getchannel("A"), mask))
    img.alpha_composite(fx)
    d = ImageDraw.Draw(img)
    soft = (222, 234, 255)
    if kind == "b1":
        d.text((44, 30), "ČETRTEK 12. 11.", font=font(B, 36), fill=(200, 220, 255))
        f, sz = fit(d, "DEŽ", B, BW - 88, 150)
        d.text((40, h - 72), "DEŽ", font=f, fill=WHITE, anchor="ls")
        a = ease_out(seg(t, 2.6, 3.1))
        if a > 0:
            c = tuple(int(BG_BLOCK1[i] + (soft[i] - BG_BLOCK1[i]) * a) for i in range(3))
            d.text((46, h - 54), "še toplo: nič snega", font=font(R, 38), fill=c)
    elif kind == "b2":
        d.text((44, 30), "PETEK 13. 11.", font=font(B, 36), fill=(190, 212, 255))
        f, sz = fit(d, "DEŽ", B, BW - 88, 150)
        d.text((40, h - 72), "DEŽ", font=f, fill=WHITE, anchor="ls")
        n = int(round(S["mm"] * ease_out(seg(t, 4.0, 4.9))))
        d.text((46, h - 54), f"okoli {n} mm v dveh dneh", font=font(R, 38), fill=soft)
    else:
        d.text((44, 30), "SOBOTA 14. 11.", font=font(B, 36), fill=(30, 70, 120))
        f0, sz0 = fit(d, "SNEG?", B, 800, 300)
        k = 1 + 0.055 * (bump(t, 5.8) + bump(t, 8.6))
        f = font(B, int(sz0 * k))
        d.text((40, 90 + int(sz0 * 0.74)), "SNEG?", font=f, fill=INK, anchor="ls")
        yb = 90 + int(sz0 * 0.74)
        a = ease_out(seg(t, 5.9, 6.4))
        if a > 0:
            c = tuple(int(SNOW[i] + (INK[i] - SNOW[i]) * a) for i in range(3))
            d.text((46, yb + 22), "odloča se v noči na soboto", font=font(B, 40), fill=c)
        e = ease_out(seg(t, 6.4, 7.6))
        if e > 0:
            c = tuple(int(SNOW[i] + ((40, 52, 78)[i] - SNOW[i]) * clamp01(e * 3)) for i in range(3))
            d.text((46, yb + 74), f"{int(round(S['c1'] * e))} % v dolini, {int(round(S['c1_900'] * e))} % na 900 m", font=font(R, 40), fill=c)
    return img


BG_BLOCK1 = RAIN


# ───────────────────────── kader ─────────────────────────

def frame(t, S, bg, hero, title):
    img = bg.copy()
    d = ImageDraw.Draw(img)
    BGFLAKES.draw(d, t, snow_col)
    st.badge(d, "NAPOVED, NE MERITEV")
    # junak: udari v prvih 0,5 s, med 1,4 in 1,9 s odide
    exit_p = ease_in_out(seg(t, 1.4, 1.95))
    if exit_p < 1:
        pop = 1 + 0.07 * (1 - ease_out(seg(t, 0, 0.5)))
        sc = pop * (1 + 0.22 * exit_p)
        lw, lh = int(hero.width * sc), int(hero.height * sc)
        lay = hero.resize((lw, lh), Image.BILINEAR)
        if exit_p > 0:
            lay.putalpha(lay.getchannel("A").point(lambda a: int(a * (1 - exit_p))))
        img.paste(lay, ((W - lw) // 2, 800 - lh // 2), lay)
    # ozka vrstica naslova
    tp = ease_out(seg(t, 1.8, 2.35))
    if tp > 0:
        lay = title.copy()
        lay.putalpha(lay.getchannel("A").point(lambda a: int(a * tp)))
        img.paste(lay, (PAD, int(350 - 30 * (1 - tp))), lay)
    # bloki
    for kind, t0, mode in (("b1", 1.9, "right"), ("b2", 3.4, "left"), ("b3", 5.0, "up")):
        p = seg(t, t0, t0 + 0.65)
        if p <= 0:
            continue
        y0, h = LAYOUT[kind]
        lay = block_layer(kind, S, t)
        if mode == "right":
            dx, dy = int((1 - ease_out(p)) * (W - PAD)), 0
        elif mode == "left":
            dx, dy = -int((1 - ease_out(p)) * (W)), 0
        else:
            dx, dy = 0, int((1 - back_out(p)) * 900)
        img.paste(lay, (PAD + dx, y0 + dy), lay)
    # znamka in opozorilo
    bp = ease_out(seg(t, 7.6, 8.1))
    if bp > 0:
        ov = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
        st.brand(ImageDraw.Draw(ov), 0)
        ov.putalpha(ov.getchannel("A").point(lambda a: int(a * bp)))
        img.paste(ov, (0, 1640), ov)
    return img


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "og", f"{post.SLUG}-zgodba-animirana.mp4")
    S = cards.stats()
    bg, hero, title = make_bg(), hero_layer(), title_layer()
    n = int(DUR * FPS)
    if "--poster" in sys.argv:
        p = out.replace(".mp4", ".jpg")
        frame(0.0, S, bg, hero, title).save(p, quality=92)
        print("✓", p)
        return
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
           "-c:a", "aac", "-b:a", "32k", "-movflags", "+faststart", "-map_metadata", "-1", out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        pr.stdin.write(frame(i / FPS, S, bg, hero, title).tobytes())
    pr.stdin.close()
    pr.wait()
    print("✓", out, round(os.path.getsize(out) / 1024), "kB")


if __name__ == "__main__":
    main()
