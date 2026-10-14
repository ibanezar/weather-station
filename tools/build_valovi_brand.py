#!/usr/bin/env python3
"""Znamka kalkulatorja »Gobji valovi« (/gobarska-napoved/valovi/): logotip, favicon in OG slika.

ENKRATNO / ROČNO (izhod je commitan, ne teče v nobenem workflowu). Znak: trije koncentrični
valovi v barvah skupin gob (razkrojevalke = turkizna, lesne = jantarna, mikorizne = vijolična),
ki tvorijo klobuk gobe, in kaplji dežja nad njim. Barve so iste kot v VALOVI_GROUPS.

    python3 tools/build_valovi_brand.py          # SVG-ji + og/valovi.html
    node tools/render_valovi_brand.mjs           # og/valovi.jpg (Chromium)
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "gobarska-napoved", "valovi")
TEAL, AMBER, VIOLET = "#2dd4bf", "#c17f3e", "#a78bfa"

DROP = ('<path d="M{x} {y}c-2.6 3.4-4 5.6-4 7.6a4 4 0 0 0 8 0c0-2-1.4-4.2-4-7.6z" fill="{c}"/>')


def logo_svg(drops=True, w=4.6):
    d = (DROP.format(x=47, y=8, c=TEAL) + DROP.format(x=17, y=11, c=VIOLET)) if drops else ""
    return f'''<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Gobji valovi">
  <defs><linearGradient id="vb" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#0e3340"/><stop offset="100%" stop-color="#06141a"/></linearGradient></defs>
  <rect width="64" height="64" rx="14" fill="url(#vb)"/>
  <path d="M10 44A22 22 0 0 1 54 44" fill="none" stroke="{VIOLET}" stroke-width="{w}" stroke-linecap="round"/>
  <path d="M16 44A16 16 0 0 1 48 44" fill="none" stroke="{AMBER}" stroke-width="{w}" stroke-linecap="round"/>
  <path d="M22 44A10 10 0 0 1 42 44" fill="none" stroke="{TEAL}" stroke-width="{w}" stroke-linecap="round"/>
  <rect x="28" y="40" width="8" height="15" rx="3.5" fill="#f1e6cf"/>
  {d}
</svg>
'''


def og_html():
    return f'''<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;width:1200px;height:630px;background:radial-gradient(900px 500px at 15% 20%,#0e3340,#06141a);
font-family:Inter,Arial,sans-serif;color:#e8f4f3;overflow:hidden}}
.w{{display:flex;align-items:center;gap:56px;padding:0 80px;height:100%}}
.w svg{{width:300px;height:300px;flex:none}}
.k{{font-size:26px;letter-spacing:.14em;text-transform:uppercase;color:{TEAL};font-weight:700}}
h1{{font-size:96px;line-height:1;margin:14px 0 20px;font-weight:800}} h1 em{{font-style:normal;color:{TEAL}}}
p{{font-size:34px;margin:0 0 28px;color:#a9c4c7}}
.c{{display:flex;gap:14px}} .c span{{font-size:26px;font-weight:700;padding:10px 22px;border-radius:999px}}
</style><div class="w">{logo_svg().replace('<svg ', '<svg ', 1)}
<div><div class="k">MeteoGobar · Rečica ob Savinji</div><h1>Gobji <em>valovi</em></h1>
<p>Kdaj po dežju zrastejo gobe?</p>
<div class="c"><span style="background:{TEAL}26;color:{TEAL}">2–8 dni</span>
<span style="background:{AMBER}33;color:#e0a458">3–10 dni</span>
<span style="background:{VIOLET}26;color:{VIOLET}">4–16 dni</span></div></div></div>'''


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, svg in (("logo-valovi.svg", logo_svg()), ("favicon.svg", logo_svg(False, 6))):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
    os.makedirs(os.path.join(ROOT, "og", "valovi-src"), exist_ok=True)
    with open(os.path.join(ROOT, "og", "valovi-src", "valovi.html"), "w", encoding="utf-8") as f:
        f.write(og_html())
    print("ok")


if __name__ == "__main__":
    main()
