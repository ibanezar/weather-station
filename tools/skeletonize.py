#!/usr/bin/env python3
"""Placeholderji »Nalaganje…« na naslovni strani -> skeleton bloki (faza 5 redizajna).

Ročno orodje, izhod je commitan; idempotentno (preoblikovanega ne najde več):
    python3 tools/skeletonize.py
Preoblikuje samo čiste placeholderje (vsebina elementa je samo »Nalaganje…«):
  - <div class="clim-loading skel-shimmer">…</div> in <div style="color:var(--muted);…">…</div>
    -> <div class="skel"> trije trakovi + skrito besedilo za bralnike (ostane tudi `textContent`
       z »Nalaganje«, na katerega se opira app.js);
  - elementi z id-jem (why-text, ai-brief-text, clim-content …) -> trakovi znotraj elementa;
  - <span class="chart-range" id="…">Nalaganje…</span> in #status-text -> vrstični trak.
Izvzeto: stanja brez povezave (.duel-offline, .otd-nodata, .omx-sub), <text> v SVG, <td>.
`aria-busy` doda in odstrani app.js (_skelWatch), ne HTML.
"""
import re
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "index.html"

BARS = '<span class="skel-bars" aria-hidden="true"><i></i><i></i><i></i></span>'
def block(text, extra=""):
    return f'<span class="skel{extra}">{BARS}<span class="visually-hidden">{text}</span></span>'
def inline(text):
    return f'<span class="skel-inline" aria-hidden="true"></span><span class="visually-hidden">{text}</span>'

def convert(s):
    n = 0
    def sub(pat, fn, flags=0):
        nonlocal s, n
        s, k = re.subn(pat, fn, s, flags=flags); n += k
    # 1. .clim-loading skel-shimmer
    sub(r'<div class="clim-loading skel-shimmer">(Nalaganje[^<]*)</div>',
        lambda m: f'<div class="skel-wrap">{block(m.group(1))}</div>')
    # 2. gol div s stilom (brez id/class)
    sub(r'<div style="([^"]*)">(Nalaganje[^<]*)</div>',
        lambda m: f'<div class="skel-wrap" style="{re.sub(r"color:[^;]*;?|font-size:[^;]*;?", "", m.group(1))}">{block(m.group(2))}</div>')
    # 3. id-jan blokovni element z vrstico besedila
    BLOCK_IDS = ("why-text","ai-brief-text","pollen-sub","clim-content","an-data-source","prov-stats-wrap",
                 "tri-records","tri-proverb-card","tri-phenom-card","tri-quiz-card","gloss-featured-wrap","elev-lapse")
    def blk(m):
        return f'<div{m.group(1)}>{block(m.group(2))}</div>'
    for i in BLOCK_IDS:
        sub(r'<div((?=[^>]*\bid="' + i + r'")[^>]*)>\s*(Nalaganje[^<]*?)\s*</div>', blk)
    # 4. vrstični trak: chart-range in status-text
    sub(r'<span((?=[^>]*class="chart-range")[^>]*)>(Nalaganje[^<]*)</span>',
        lambda m: f'<span{m.group(1)}>{inline(m.group(2))}</span>')
    sub(r'<span((?=[^>]*\bid="status-text")[^>]*)>(Nalaganje[^<]*)</span>',
        lambda m: f'<span{m.group(1)}>{inline(m.group(2))}</span>')
    return s, n

if __name__ == "__main__":
    out, n = convert(HTML.read_text())
    HTML.write_text(out)
    left = len(re.findall(r'>\s*Nalaganje', out))
    print(f"preoblikovanih: {n}; golih »Nalaganje« še ostane: {left}")
