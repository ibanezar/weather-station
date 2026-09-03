#!/usr/bin/env python3
"""
tools/generate_gasilec_page.py — MeteoGasilec: požarna ogroženost in vreme za
intervencije.

Renders /meteogasilec/ (landing) + tri podstrani. Samostojen generator (isto
načelo kot pri generate_gobe_page.py — generatorji strani si ne delijo
knjižnic): uvaža samo skupne predloge iz generate_seo_pages (`seo`) in svoj
model iz gasilec_model.py (`fm`).

Vsebina:
  * Hero — današnji FWI (kanadska/EFFIS metodologija, isti izračun kot na
    naslovnici, glej gasilec_model.py) + 7-dnevni graf.
  * NASA FIRMS — dejansko zaznane toplotne anomalije v bližini (isti Worker
    endpoint /pozari kot na naslovnici, klican na novo od tu).
  * Sedem podstrani: intervencija/ (hiter operativni pogled — GPS lokacija,
    grafičen veter, detektor obrata vetra, lokalni FWI ko je GPS >2 km od
    Rečice, veter+teren prek Open-Meteo Elevation API, kopiraj briefing;
    klientska logika je v meteogasilec/gasilec.js, deljena med vsemi
    /meteogasilec/* stranmi), karta/ (Leaflet + OSM ploščice —
    hidranti/odvzemna mesta iz meteogasilec/hidranti.json,
    tools/fetch_hydrants.py, + FIRMS požarišča), kalkulator/ (cisterna,
    penilo, statični tlak), vodotoki/ (najbližje ARSO hidro postaje ob
    Savinji, uvožene iz generate_vodostaj_page.py), vreme-intervencije/
    (lokalni veter + nacionalni nevihtni potencial iz že objavljenega
    og/storm-map/latest.json), nasveti/ (kurjenje v naravi, kontakti),
    metodologija/ (razlaga FWI, viri, omejitve).

Usage:
  python3 tools/generate_gasilec_page.py
"""
import datetime as _dt
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo   # noqa: E402 — shared template helpers
import gasilec_model as fm         # noqa: E402 — FWI model
import generate_vodostaj_page as vod  # noqa: E402 — ARSO hidro postaje (ne podvajaj fetch_arso_stations)
from generate_arso_newsjack_post import fetch_alerts as fetch_arso_alerts  # noqa: E402 — isti Worker klic, ne podvajaj

ROOT = seo.ROOT
TODAY = seo.TODAY
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"
STORM_MAP_JSON = os.path.join(ROOT, "og", "storm-map", "latest.json")


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


BRAND_SWAP = '''<script>(function(){
  var img=document.querySelector(".site-head .brand-logo");
  var nm=document.querySelector(".site-head .brand-name");
  if(img){img.src="/meteogasilec/logo-gasilec.svg";img.alt="MeteoGasilec";}
  if(nm){nm.innerHTML="Meteo<em>Gasilec</em>";}
})();</script>'''

PAGE_CSS = """<style>
[hidden]{display:none!important}
body{
  --blue:#f59e0b; --cyan:#ef4444;
  --gf-sp-3:.75rem; --gf-sp-4:1rem; --gf-sp-6:1.5rem;
}
.gf-hero{position:relative;overflow:hidden;border:1px solid var(--card-border);border-radius:1.1rem;
  padding:1.5rem;margin:.6rem 0 1.4rem;box-shadow:var(--card-shadow);
  background:linear-gradient(200deg,rgba(10,6,4,.55) 0%,rgba(8,5,4,.78) 55%,rgba(8,5,4,.93) 100%),
    url('/og/bg/drought.jpg') center 40%/cover}
.gf-hero-top{display:flex;align-items:center;gap:1.3rem;flex-wrap:wrap}
.gf-gauge-wrap{position:relative;width:112px;height:112px;flex:0 0 auto}
.gf-ring{display:block;width:100%;height:100%}
.gf-ring-bg{fill:none;stroke:rgba(255,255,255,.12);stroke-width:10}
.gf-ring-fg{fill:none;stroke-width:10;stroke-linecap:round;transform:rotate(-90deg);transform-origin:56px 56px}
.gf-gauge-num{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;line-height:1}
.gf-gauge-num .num{font-family:'JetBrains Mono',monospace;font-size:1.9rem;font-weight:800;color:#fff}
.gf-gauge-num small{display:block;margin-top:.15rem;font-size:.62rem;color:rgba(255,255,255,.7);font-weight:600}
.gf-hero-sub{font-size:.72rem;color:var(--muted);margin-top:.2rem}
.gf-kicker{display:inline-block;font-size:.68rem;font-weight:800;letter-spacing:.04em;
  text-transform:uppercase;margin:0 0 .5rem}
.gf-hero-body{flex:1;min-width:220px}
.gf-badge{display:inline-block;padding:.28rem .8rem;border-radius:999px;font-size:.8rem;
  font-weight:700;margin-bottom:.4rem}
.gf-hero-note{font-size:.78rem;color:rgba(255,255,255,.75);margin-top:.6rem;line-height:1.5}
.gf-hero-note a{color:#fff}
.gf-bars{display:flex;gap:4px;align-items:flex-end;height:80px;margin-top:1.1rem}
.gf-bar-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px}
.gf-bar{width:100%;max-width:22px;border-radius:3px 3px 0 0}
.gf-bar-lbl{font-size:.55rem;color:rgba(255,255,255,.65)}
.gf-legend{display:flex;flex-wrap:wrap;gap:.6rem .9rem;font-size:.74rem;color:rgba(255,255,255,.8);
  margin:.9rem 0 0;padding-top:.8rem;border-top:1px solid rgba(255,255,255,.14)}
.gf-legend span{display:inline-flex;align-items:center;gap:.35rem}
.gf-legend i{width:.8rem;height:.8rem;border-radius:3px;display:inline-block}
.gf-feat-group{margin:1.6rem 0}
.gf-feat-group h3{font-size:1rem;margin:0 0 .6rem}
.gf-feat{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.8rem}
.gf-feat-card{position:relative;display:flex;flex-direction:column;gap:.4rem;overflow:hidden;
  border:1px solid var(--card-border);border-radius:.9rem;
  padding:1rem 1.1rem 1.1rem;background:var(--card-bg);box-shadow:var(--card-shadow);
  text-decoration:none;color:var(--text);
  transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease}
.gf-feat-card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--fa)}
.gf-feat-card:hover{transform:translateY(-2px);border-color:var(--fa);
  box-shadow:0 10px 24px -12px var(--fa)}
.gf-feat-ic{display:inline-flex;align-items:center;justify-content:center;width:2.5rem;height:2.5rem;
  flex:0 0 auto;border-radius:12px;background:var(--fa-soft);color:var(--fa)}
.gf-feat-ic svg{width:1.5rem;height:1.5rem;display:block}
.gf-feat-title{display:block;font-weight:700;margin:.3rem 0 .2rem}
.gf-feat-sub{display:block;font-size:.78rem;color:var(--muted);line-height:1.4}
.gf-firms{border:1px solid var(--card-border);border-radius:.9rem;padding:1rem;
  background:var(--card-bg);margin:1.4rem 0}
.gf-note{font-size:.78rem;color:var(--muted);line-height:1.6;margin-top:.5rem}
.gf-tbl{width:100%;border-collapse:collapse;font-size:.82rem;margin:.8rem 0}
.gf-tbl th,.gf-tbl td{padding:.4rem .5rem;border-bottom:1px solid var(--card-border);text-align:left}
.gf-back{display:inline-block;margin-top:1.4rem;font-size:.85rem}
.gf-fresh{display:inline-flex;align-items:center;gap:.3rem;font-size:.74rem;color:var(--muted)}
.gf-interv-banner{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;
  border:1px solid #ef444455;border-radius:1rem;padding:1rem 1.2rem;margin:.8rem 0 1.2rem;
  background:linear-gradient(120deg,#ef444422,#ef444408)}
.gf-interv-banner h2{margin:0 0 .2rem;font-size:1.05rem}
.gf-interv-banner p{margin:0;font-size:.8rem;color:var(--muted)}
.gf-btn{display:inline-flex;align-items:center;gap:.4rem;padding:.6rem 1.1rem;border-radius:.7rem;
  font-weight:700;font-size:.88rem;text-decoration:none;border:none;cursor:pointer;
  background:#ef4444;color:#fff;white-space:nowrap}
.gf-btn:hover{background:#dc2626}
.gf-btn.secondary{background:var(--card-bg);color:var(--text);border:1px solid var(--card-border)}
.gf-btn.secondary:hover{border-color:#ef4444}
.gf-interv-card{border:1px solid var(--card-border);border-radius:1rem;padding:1.2rem;
  background:var(--card-bg);box-shadow:var(--card-shadow);margin:1rem 0}
.gf-interv-loc{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.6rem;
  margin-bottom:.8rem;padding-bottom:.7rem;border-bottom:1px solid var(--card-border)}
.gf-interv-loc b{font-size:.92rem}
.gf-interv-body{display:flex;gap:1.2rem;flex-wrap:wrap;align-items:center}
.gf-compass-wrap{flex:0 0 auto;text-align:center;color:var(--text)}
.gf-compass-lbl{font-size:.72rem;color:var(--muted);margin-top:.2rem}
.gf-interv-stats{flex:1;min-width:220px;display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem .9rem}
.gf-stat{display:flex;flex-direction:column}
.gf-stat b{font-family:'JetBrains Mono',monospace;font-size:1.15rem}
.gf-stat span{font-size:.7rem;color:var(--muted)}
.gf-shift-warn{margin-top:1rem;padding:.8rem 1rem;border-radius:.8rem;background:#f59e0b22;
  border:1px solid #f59e0b66;font-size:.85rem;line-height:1.5}
.gf-shift-warn b{display:block;margin-bottom:.2rem}
.gf-briefing{margin-top:1.2rem;padding-top:1rem;border-top:1px solid var(--card-border)}
.gf-briefing pre{white-space:pre-wrap;font-family:'JetBrains Mono',monospace;font-size:.76rem;
  background:var(--bg-alt,rgba(127,127,127,.08));border-radius:.6rem;padding:.8rem;margin:.6rem 0}
.gf-briefing-actions{display:flex;gap:.6rem;flex-wrap:wrap}
.gf-calc-row{display:flex;gap:1rem;flex-wrap:wrap;margin:.6rem 0}
.gf-calc-row label{display:flex;flex-direction:column;gap:.3rem;font-size:.78rem;color:var(--muted);flex:1;min-width:160px}
.gf-calc-row input[type=number]{background:var(--card-bg);border:1px solid var(--card-border);border-radius:.5rem;
  padding:.5rem .6rem;color:var(--text);font-family:'JetBrains Mono',monospace;font-size:.9rem}
.gf-calc-result{font-family:'JetBrains Mono',monospace;font-size:1.05rem;font-weight:700;margin:.6rem 0 0}
.gf-arso{border:1px solid var(--card-border);border-top:3px solid #2563eb;border-radius:.9rem;padding:1rem;
  background:var(--card-bg);box-shadow:var(--card-shadow);margin:1.4rem 0}
.gf-arso-list{display:flex;flex-direction:column;gap:.5rem}
.gf-arso-item{padding:.5rem .7rem;border-radius:.5rem;font-size:.85rem;border-left:3px solid #eab308;
  background:rgba(234,179,8,.08)}
.gf-arso-item.gf-arso-orange{border-left-color:#f97316;background:rgba(249,115,22,.08)}
.gf-arso-item.gf-arso-red{border-left-color:#ef4444;background:rgba(239,68,68,.08)}
.gf-terrain{margin:1rem 0;padding-top:.9rem;border-top:1px solid var(--card-border)}
.gf-status-banner{display:flex;align-items:center;gap:.7rem;padding:.9rem 1.1rem;border-radius:.9rem;
  margin:.8rem 0 1.2rem;font-size:.92rem;font-weight:600}
.gf-status-banner .emoji{font-size:1.4rem;flex:0 0 auto}
.gf-tip-grid,.gf-contact-grid,.gf-station-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
  gap:.8rem;margin:.8rem 0 1.2rem}
.gf-tip-card{position:relative;overflow:hidden;display:flex;gap:.7rem;align-items:flex-start;
  border:1px solid var(--card-border);border-radius:.8rem;padding:.9rem 1rem;background:var(--card-bg)}
.gf-tip-card::before{content:"";position:absolute;top:0;left:0;bottom:0;width:3px;background:var(--fa,#84cc16)}
.gf-tip-ic{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;width:2.1rem;height:2.1rem;
  border-radius:9px;background:var(--fa-soft,rgba(132,204,22,.16));color:var(--fa,#84cc16)}
.gf-tip-ic svg{width:1.25rem;height:1.25rem;display:block}
.gf-tip-card p{margin:0;font-size:.84rem;line-height:1.45}
.gf-contact-card{display:flex;align-items:center;gap:.7rem;border:1px solid var(--card-border);border-radius:.8rem;
  padding:.8rem 1rem;background:var(--card-bg);text-decoration:none;color:var(--text);transition:border-color .15s}
.gf-contact-card:hover{border-color:var(--fa,#84cc16)}
.gf-contact-ic{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;width:2.3rem;height:2.3rem;
  border-radius:50%;background:var(--fa-soft,rgba(132,204,22,.16));color:var(--fa,#84cc16)}
.gf-contact-ic svg{width:1.3rem;height:1.3rem;display:block}
.gf-contact-card b{display:block;font-size:.88rem}
.gf-contact-card span{display:block;font-size:.74rem;color:var(--muted)}
.gf-component-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.7rem;margin:.8rem 0 1.2rem}
.gf-component-card{border:1px solid var(--card-border);border-radius:.8rem;padding:.8rem;background:var(--card-bg);
  text-align:center}
.gf-component-card b{display:block;font-family:'JetBrains Mono',monospace;font-size:1.3rem}
.gf-component-card span{display:block;font-size:.72rem;color:var(--muted);margin-top:.15rem}
.gf-station-card{border:1px solid var(--card-border);border-radius:.9rem;padding:1rem;background:var(--card-bg);
  box-shadow:var(--card-shadow)}
.gf-station-card h3{margin:0 0 .5rem;font-size:.95rem}
.gf-station-stats{display:flex;gap:1.2rem;margin-bottom:.6rem}
.gf-station-stats div{flex:1}
.gf-station-stats b{display:block;font-family:'JetBrains Mono',monospace;font-size:1.15rem}
.gf-station-stats span{display:block;font-size:.7rem;color:var(--muted)}
.gf-status-chip{display:inline-flex;align-items:center;gap:.35rem;padding:.22rem .7rem;border-radius:999px;
  font-size:.76rem;font-weight:700}
@media (max-width:480px){
  .gf-feat{grid-template-columns:repeat(2,1fr)}
  .gf-feat-card{padding:.8rem .85rem .9rem}
  .gf-feat-ic{width:2.2rem;height:2.2rem;border-radius:10px}
  .gf-feat-ic svg{width:1.35rem;height:1.35rem}
  .gf-feat-title{font-size:.88rem}
  .gf-feat-sub{display:none}
}
</style>"""


def _rgba(hex_color, alpha):
    """#rrggbb → rgba(r,g,b,alpha) — mehka podlaga ikone iz istega poudarka
    (ista tehnika kot _rgba() v generate_gobe_page.py, lokalna kopija)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# FWI teoretično ni navzgor omejen, praktično pa se za to lego giblje do ~45-50
# — kapiramo na GAUGE_MAX zgolj za berljiv obroč. To NI odstotek FWI, samo
# vizualna lestvica (ista disciplina kot drugod na strani: število se ne sme
# napačno brati kot %).
GAUGE_MAX = 45.0


def gauge_svg(fwi, color):
    r = 46
    circ = 2 * math.pi * r
    pct = max(0.0, min(1.0, fwi / GAUGE_MAX))
    off = circ * (1 - pct)
    return (f'<svg viewBox="0 0 112 112" class="gf-ring" aria-hidden="true">'
            f'<circle cx="56" cy="56" r="{r}" class="gf-ring-bg"/>'
            f'<circle cx="56" cy="56" r="{r}" class="gf-ring-fg" stroke="{color}" '
            f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{off:.1f}"/></svg>')


def legend_html():
    chips = []
    for label, color, lo, hi in fm.FWI_LEVELS:
        rng = f"{lo:g}–{hi:g}" if hi is not None else f"{lo:g}+"
        chips.append(f'<span><i style="background:{color}"></i>{_esc(label)} ({rng})</span>')
    return f'  <div class="gf-legend">{"".join(chips)}</div>'


def _bars_svg_html(days):
    if not days:
        return ""
    max_fwi = max((d["fwi"] for d in days), default=5) or 5
    dn = ["Ned", "Pon", "Tor", "Sre", "Čet", "Pet", "Sob"]
    today_iso = TODAY.isoformat()
    cols = []
    for d in days:
        h = max(4, round((d["fwi"] / max_fwi) * 64))
        is_today = d["date"] == today_iso
        wd = dn[(_dt.date.fromisoformat(d["date"]).weekday() + 1) % 7]
        outline = "outline:2px solid var(--text);outline-offset:1px;" if is_today else ""
        cols.append(
            f'<div class="gf-bar-col"><div class="gf-bar" style="height:{h}px;background:{d["color"]};'
            f'opacity:{1 if is_today else .6};{outline}" title="{d["date"]}: FWI {d["fwi"]} ({d["level"]})">'
            f'</div><span class="gf-bar-lbl">{wd}</span></div>'
        )
    return f'  <div class="gf-bars">{"".join(cols)}</div>'


def build_hero(payload):
    today = payload
    color = next((d["color"] for d in payload["days"] if d["date"] == payload["date"]), "#f59e0b")
    return f'''  <div class="gf-hero" data-generated="{_esc(payload.get("generated"))}">
    <span class="gf-kicker" style="color:rgba(255,255,255,.65)">📊 Lokalni meteorološki indeks · model MeteoGasilec</span>
    <div class="gf-hero-top">
      <div class="gf-gauge-wrap">
        {gauge_svg(today["fwi"], color)}
        <div class="gf-gauge-num"><span class="num">{today["fwi"]:.1f}</span><small>FWI danes</small></div>
      </div>
      <div class="gf-hero-body">
        <span class="gf-badge" style="background:{color}33;border:1px solid {color};color:#fff">{_esc(today["level"])}</span>
        <p style="margin:.3rem 0 0;font-size:.88rem;color:rgba(255,255,255,.82)"><strong>Ni uradna ocena ARSO ali
        URSZR</strong> — kanadski/EFFIS indeks požarne ogroženosti za Rečico ob Savinji, izračunan iz napovedi
        Open-Meteo. Uradni status je zgoraj — glej <a href="/meteogasilec/metodologija/">metodologijo</a>.</p>
      </div>
    </div>
{_bars_svg_html(payload["days"])}
{legend_html()}
    <p class="gf-hero-note">🔥 Ista metodologija kot na naslovnici (kartica »Požarna nevarnost – indeks FWI«) — tu preračunana strežniško, da je vidna tudi iskalnikom in brez JS.</p>
    <p class="gf-hero-note gf-fresh" id="gf-fresh">posodobljeno {_esc(TODAY.isoformat())}</p>
  </div>'''


_FI_OGROZENOST = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 3.6c-3.4 0-6 2.8-6 6.6 0 3.2 2 4.6 2 7a4 4 0 0 0 8 0c0-2.4 2-3.8 2-7 0-3.8-2.6-6.6-6-6.6Z" '
    'fill="currentColor" fill-opacity=".2" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="M12 9c-1.4 1.6-1.8 3-.8 4.4 1 1.4-.2 2.2-1 1.6" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round"/></svg>')
_FI_VETER = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M3 8.6h11.5a2.7 2.7 0 1 0-2.6-3.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M3 13h15a2.9 2.9 0 1 1-2.8 3.7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M3 17.4h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".7"/></svg>')
_FI_NASVETI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="4" y="2.8" width="16" height="18.4" rx="2.6" fill="currentColor" fill-opacity=".14" '
    'stroke="currentColor" stroke-width="1.6"/>'
    '<path d="m7.4 8 1.5 1.5 2.6-2.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
    'stroke-linejoin="round"/>'
    '<path d="M13.6 8.2h3.2M7.4 13.4h9.2M7.4 17.4h9.2" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round" opacity=".7"/></svg>')

_FI_INTERV = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 2.6c-3.7 0-6.4 2.9-6.4 6.5 0 4.5 5.1 10.4 6 11.4a.6.6 0 0 0 .8 0c.9-1 6-6.9 6-11.4 '
    '0-3.6-2.7-6.5-6.4-6.5Z" fill="currentColor" fill-opacity=".18" stroke="currentColor" stroke-width="1.6" '
    'stroke-linejoin="round"/><circle cx="12" cy="9.2" r="2.3" fill="currentColor"/></svg>')
_FI_KARTA = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M9 4 4 6v14l5-2 6 2 5-2V4l-5 2-6-2Z" fill="currentColor" fill-opacity=".14" '
    'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="M9 4v14M15 6v14" stroke="currentColor" stroke-width="1.4" opacity=".6"/>'
    '<circle cx="12" cy="11" r="2.1" fill="currentColor"/></svg>')
_FI_KALK = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="4.5" y="2.8" width="15" height="18.4" rx="2.4" fill="currentColor" fill-opacity=".14" '
    'stroke="currentColor" stroke-width="1.6"/>'
    '<rect x="7" y="5.4" width="10" height="3.4" rx="0.8" stroke="currentColor" stroke-width="1.4"/>'
    '<circle cx="8" cy="12.6" r="1.05" fill="currentColor"/><circle cx="12" cy="12.6" r="1.05" fill="currentColor"/>'
    '<circle cx="16" cy="12.6" r="1.05" fill="currentColor"/><circle cx="8" cy="16.6" r="1.05" fill="currentColor"/>'
    '<circle cx="12" cy="16.6" r="1.05" fill="currentColor"/><circle cx="16" cy="16.6" r="1.05" fill="currentColor"/>'
    '</svg>')
_FI_VODA = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 3.2c2.6 3.6 5.6 7.6 5.6 11a5.6 5.6 0 1 1-11.2 0c0-3.4 3-7.4 5.6-11Z" '
    'fill="currentColor" fill-opacity=".18" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="M8.8 15.4a3.2 3.2 0 0 0 3.2 3.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'
    '</svg>')

# ── ikone za nasveti/ (kurjenje, kontakti) ───────────────────────────────────
_FI_CIGARETTE = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="3" y="10.6" width="14" height="4.2" rx="1" fill="currentColor" fill-opacity=".16" '
    'stroke="currentColor" stroke-width="1.5"/>'
    '<rect x="14.4" y="10.6" width="3" height="4.2" fill="currentColor" fill-opacity=".4"/>'
    '<path d="M18 8.6c1 .9 1 2.1 0 3M20.2 7c1.6 1.4 1.6 3.4 0 4.8" stroke="currentColor" stroke-width="1.4" '
    'stroke-linecap="round"/><path d="M4 18.4h16" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
    'opacity=".5"/></svg>')
_FI_WATCHFIRE = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 3.6c-3.4 0-6 2.8-6 6.6 0 3.2 2 4.6 2 7a4 4 0 0 0 8 0c0-2.4 2-3.8 2-7 0-3.8-2.6-6.6-6-6.6Z" '
    'fill="currentColor" fill-opacity=".18" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="m9.3 12.6 1.8 1.8 3.6-3.9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
    'stroke-linejoin="round"/></svg>')
_FI_PHONE = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M5.5 4h3l1.5 4-2 1.5a11 11 0 0 0 5.5 5.5l1.5-2 4 1.5v3a1.5 1.5 0 0 1-1.6 1.5A15.5 15.5 0 0 1 4 5.6 1.5 1.5 0 0 1 5.5 4Z" '
    'fill="currentColor" fill-opacity=".18" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>')
_FI_SHIELD = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 3.4 19 6v5.4c0 4.6-3 7.8-7 9.2-4-1.4-7-4.6-7-9.2V6l7-2.6Z" fill="currentColor" fill-opacity=".16" '
    'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="m9 12 2 2 4-4.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>')

FEATURES = [
    ("/meteogasilec/intervencija/", _FI_INTERV, "#ef4444", "Intervencija zdaj",
     "Tvoja lokacija (GPS): veter, obrat vetra, FWI in kopiraj briefing."),
    ("/meteogasilec/karta/", _FI_KARTA, "#0ea5e9", "Operativna karta in hidranti",
     "Hidranti, odvzemna mesta in zaznana požarišča (FIRMS) na eni interaktivni karti."),
    ("/meteogasilec/metodologija/", _FI_OGROZENOST, "#f59e0b", "Kako se izračuna FWI",
     "Sestavine kanadskega indeksa (FFMC/DMC/DC/ISI/BUI) in kaj indeks ni."),
    ("/nevihte/", _FI_OGROZENOST, "#eab308", "Aktivna opozorila ARSO",
     "Vključno s kategorijo »požarna ogroženost«, sproti vsakih 15 minut."),
    ("/meteogasilec/vreme-intervencije/", _FI_VETER, "#22d3ee", "Vreme za intervencije",
     "Veter, sunki in nacionalni nevihtni potencial za danes."),
    ("/meteogasilec/kalkulator/", _FI_KALK, "#a855f7", "Gasilski kalkulator",
     "Praznjenje cisterne, penilo in statični tlak iz višinske razlike."),
    ("/meteogasilec/vodotoki/", _FI_VODA, "#0891b2", "Vodotoki",
     "Najbližje merilne postaje ARSO ob Savinji — vodostaj in pretok."),
    ("/meteogasilec/nasveti/", _FI_NASVETI, "#84cc16", "Kurjenje v naravi in kontakti",
     "Kdaj sme in kdaj ne sme, 112, URSZR, Gasilska zveza Slovenije."),
]


def interv_banner_html():
    return '''  <div class="gf-interv-banner">
    <div>
      <h2>🚨 Intervencija zdaj</h2>
      <p>Tvoja lokacija (GPS): veter, obrat vetra in FWI v nekaj sekundah, plus gumb za briefing.</p>
    </div>
    <a class="gf-btn" href="/meteogasilec/intervencija/">📍 Odpri</a>
  </div>'''


def feature_cards_html():
    cards = []
    for href, icon, accent, title, sub in FEATURES:
        cards.append(
            f'    <a class="gf-feat-card" href="{href}" style="--fa:{accent};--fa-soft:{_rgba(accent, ".16")}">'
            f'<span class="gf-feat-ic" aria-hidden="true">{icon}</span>'
            f'<span class="gf-feat-title">{_esc(title)}</span>'
            f'<span class="gf-feat-sub">{_esc(sub)}</span></a>'
        )
    return ('  <h2>🧭 Orodja za gasilce</h2>\n'
            '  <div class="gf-feat">\n' + "\n".join(cards) + '\n  </div>')


def firms_widget_html():
    return f'''  <div class="gf-firms">
    <h2 style="margin-top:0">🛰 Aktivna požarišča (NASA FIRMS)</h2>
    <div id="gf-firms-body">Nalaganje…</div>
    <p class="gf-note">Sateliti (MODIS/VIIRS) zaznavajo toplotne anomalije, med katere sodi tudi kmetijsko sežiganje —
    zaznava sama po sebi ni potrjen gozdni požar.</p>
  </div>
  <script>(function(){{
    var el=document.getElementById('gf-firms-body');
    fetch('{WORKER_BASE}/pozari').then(function(r){{return r.json();}}).then(function(d){{
      if(!d||d.configured===false){{el.innerHTML='<p class="gf-note">Vir trenutno ni na voljo.</p>';return;}}
      if(!d.total){{el.innerHTML='<p style="margin:0">✅ V zadnjih '+d.days+' dneh nad Slovenijo ni zaznanih toplotnih anomalij.</p>';return;}}
      var rows=(d.fires||[]).slice(0,8).map(function(it){{
        var t=(it.time||'').padStart(4,'0');
        return '<tr><td>'+(it.dist!=null?it.dist+' km':'—')+'</td><td>'+(t?t.slice(0,2)+':'+t.slice(2)+' UTC':'—')+'</td>'
          +'<td>'+(it.conf||'—')+'</td><td>'+(it.frp!=null?it.frp.toFixed(0):'—')+'</td></tr>';
      }}).join('');
      el.innerHTML='<p style="margin:0 0 .5rem"><b>'+d.total+'</b> zaznav v zadnjih '+d.days+' dneh, '+d.within50+' znotraj 50 km.</p>'
        +'<table class="gf-tbl"><thead><tr><th>Razdalja</th><th>Čas</th><th>Zaupanje</th><th>FRP (MW)</th></tr></thead>'
        +'<tbody>'+rows+'</tbody></table>';
    }}).catch(function(){{el.innerHTML='<p class="gf-note">Vir trenutno ni na voljo.</p>';}});
  }})();</script>'''


_ARSO_EMOJI = {"red": "🔴", "orange": "🟠", "yellow": "🟡"}


def _arso_alerts_body_html(alerts, fetch_ok, compact):
    """Isti HTML kot uspešna/neuspešna veja Gasilec.renderArsoWidget() v
    gasilec.js (glej opombo tam) — tako se ob nalaganju JS ne vidi vizualni
    skok, ko klientski živi podatek povozi ta strežniški posnetek.

    `fetch_ok=False` NIKOLI ne izpiše "ni aktivnih opozoril" — to bi bila
    varnostno nevarna napačno-negativna trditev (nismo preverili, ne da jih
    ni). Namesto tega pove, da preverjanje ni uspelo, in usmeri na uradno
    stran ARSO."""
    if not fetch_ok:
        return ('<p class="gf-note" style="margin:0">⚠ Uradnih opozoril trenutno ni bilo mogoče preveriti — '
                'poskusi znova čez nekaj minut ali preveri neposredno na '
                '<a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank" rel="noopener">'
                'strani ARSO</a>.</p>')
    if not alerts:
        msg = "Ni aktivnih uradnih opozoril ARSO." if compact else "Trenutno ni aktivnih uradnih opozoril ARSO za to območje."
        return f'<p class="gf-note" style="margin:0">✅ {msg}</p>'
    items = []
    for a in alerts:
        level = a.get("level") or "yellow"
        emoji = _ARSO_EMOJI.get(level, "⚠️")
        text = _esc(a.get("text") or a.get("desc") or "Opozorilo")
        items.append(f'<div class="gf-arso-item gf-arso-{level}">{emoji} <b>{text}</b></div>')
    return f'<div class="gf-arso-list">{"".join(items)}</div>'


def arso_widget_html(alerts, fetch_ok, checked_at, compact=False):
    """Uradna opozorila ARSO — isti Worker endpoint kot
    generate_arso_newsjack_post.py/fetch_alerts() in /nevihte/ WX-ARSO.

    Za razliko od prejšnje različice (samo "Preverjam …", brez vsebine dokler
    JS ne odgovori) je zdaj strežniško izrisan zadnji znan posnetek — MeteoGasilec
    je varnostno-kritično orodje in nalagajoč se placeholder ne sme delovati kot
    odgovor, če je JS počasen ali ne steče. Klientski Gasilec.renderArsoWidget()
    ta posnetek na nalaganju osveži z živimi podatki (opozorilo je stanje, ne
    novica — enkrat-dnevni posnetek bi v urah zastaral, glej CLAUDE.md); če
    osvežitev spodleti, gasilec.js pusti ta posnetek namesto da ga izbriše."""
    body_id = "gf-arso-compact" if compact else "gf-arso-body"
    body = _arso_alerts_body_html(alerts, fetch_ok, compact)
    if compact:
        return (f'  <p class="gf-note" style="margin:0 0 .3rem;font-weight:700">🏛 Uradna opozorila ARSO</p>\n'
                f'  <div id="{body_id}">{body}</div>')
    return f'''  <div class="gf-arso">
    <span class="gf-kicker" style="color:#2563eb">🏛 Uradni vir · Agencija RS za okolje</span>
    <h2 style="margin:.1rem 0 0">Uradna opozorila</h2>
    <div id="{body_id}">{body}</div>
    <p class="gf-note">Uradna vremenska opozorila ARSO — ločeno od MeteoGasilec lastnih ocen (FWI, obrat vetra)
    spodaj na tej strani. Preverjeno {_esc(checked_at)}, sproti se osvežuje v brskalniku. Vsa opozorila za Slovenijo:
    <a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank" rel="noopener">stran ARSO</a>.</p>
  </div>'''


def subpage_shell(slug, title, desc, inner_html, extra_head=""):
    url = f"/meteogasilec/{slug}/"
    crumbs = [("Meteorec", "/"), ("MeteoGasilec", "/meteogasilec/"), (title, None)]
    schema = "\n".join([seo.webpage_schema(url, title, desc), seo.crumbs_schema(crumbs)])
    head_extras = schema + "\n" + PAGE_CSS + ("\n" + extra_head if extra_head else "")
    body = f'''{BRAND_SWAP}
{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">{title}</h1>
{inner_html}
  <a class="gf-back" href="/meteogasilec/">← Nazaj na MeteoGasilec</a>'''
    html = seo.page_shell(f"{title} — MeteoGasilec", desc, url, head_extras, body)
    seo.write_page(f"meteogasilec/{slug}/index.html", html, force=True)
    return url


# ── veter za intervencije ────────────────────────────────────────────────────

def fetch_wind_hourly():
    params = urllib.parse.urlencode({
        "latitude": fm.LAT, "longitude": fm.LON,
        "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
        "forecast_days": 2, "timezone": "Europe/Ljubljana",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


_DIRS = ["S", "SSV", "SV", "VSV", "V", "VJV", "JV", "JJV", "J", "JJZ", "JZ", "ZJZ", "Z", "ZSZ", "SZ", "SSZ"]


def _dir_label(deg):
    return _DIRS[round(deg / 22.5) % 16]


def load_storm_map():
    try:
        with open(STORM_MAP_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def build_vreme_intervencije_page():
    rows_html = "<tr><td colspan='4'>Vetrovna napoved trenutno ni na voljo.</td></tr>"
    try:
        data = fetch_wind_hourly()
        h = data.get("hourly") or {}
        times = h.get("time") or []
        spd = h.get("wind_speed_10m") or []
        gust = h.get("wind_gusts_10m") or []
        wdir = h.get("wind_direction_10m") or []
        now_iso = _dt.datetime.now().strftime("%Y-%m-%dT%H:00")
        start = next((i for i, t in enumerate(times) if t >= now_iso), 0)
        rows = []
        for i in range(start, min(start + 24, len(times)), 3):
            t = times[i]
            hh = t[11:16]
            day = "danes" if t[:10] == TODAY.isoformat() else "jutri"
            rows.append(
                f"<tr><td>{day} {hh}</td><td>{spd[i]:.0f} km/h</td>"
                f"<td>{gust[i]:.0f} km/h</td><td>{_dir_label(wdir[i])}</td></tr>"
            )
        rows_html = "\n".join(rows)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  ⚠ veter: {e}", file=sys.stderr)

    storm = load_storm_map()
    storm_html = ""
    if storm:
        storm_html = f'''  <h2>🌩 Nacionalni nevihtni potencial danes</h2>
  <p>Najvišja pričakovana ocena danes v Sloveniji: <b>{storm.get("national_score")} ({storm.get("national_level")})</b>,
  okoli {storm.get("national_hour")} pri kraju {_esc(storm.get("national_place"))}.
  Ocena je izpeljana iz CAPE, striga vetra in indeksov nestabilnosti — <a href="/nevihte/">celotna karta in razlaga →</a></p>'''

    inner = f'''  <p class="post-meta">Veter, sunki in nevihtni potencial za naslednjih 24 ur — dopolnilo k požarnemu
  indeksu za presojo širjenja ognja in varnosti med intervencijo.</p>
  <h2>🌬 Veter — Rečica ob Savinji</h2>
  <table class="gf-tbl">
    <thead><tr><th>Čas</th><th>Hitrost</th><th>Sunki</th><th>Smer</th></tr></thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
{storm_html}
  <h2>⚡ Strele in radar v živo</h2>
  <p>Trenutne strele (Blitzortung) in radarska slika sta na voljo na <a href="/">naslovnici</a> (zavihek »Lovec na nevihte«).</p>'''
    return subpage_shell("vreme-intervencije", "Vreme za intervencije",
                          "Veter, sunki vetra in nacionalni nevihtni potencial za Rečico ob Savinji — "
                          "podatki v pomoč gasilskim intervencijam.", inner)


# ── intervencija zdaj (GPS) ──────────────────────────────────────────────────

def fetch_current_hourly(lat=None, lon=None):
    """Urni temp/vlaga/padavine/veter za naslednja 2 dni — vhod za rezervni
    (brez-JS) prikaz na /intervencija/. Isti Open-Meteo forecast endpoint kot
    JS na tej strani kliče v brskalniku (glej Gasilec bootstrap spodaj),
    samo za privzeto lokacijo (Rečica ob Savinji)."""
    params = urllib.parse.urlencode({
        "latitude": lat or fm.LAT, "longitude": lon or fm.LON,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,"
                  "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
        "forecast_days": 2, "timezone": "Europe/Ljubljana",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _compass_svg_py(dir_from_deg, size=128):
    """Strežniška kopija windCompassSvg() iz gasilec.js — glej opombo na vrhu
    te datoteke (JS in Python namerno računata/rišeta isto stvar ločeno, isto
    načelo kot SLO_POLY/buildSloGrid med app.js in generate_storm_map.py)."""
    to_deg = (dir_from_deg + 180) % 360
    cx = cy = size / 2
    r = size / 2 - 16
    labels = [("S", cx, 15), ("V", size - 9, cy + 4), ("J", cx, size - 6), ("Z", 9, cy + 4)]
    labels_html = "".join(
        f'<text x="{x}" y="{y}" text-anchor="middle" font-size="11" font-weight="700" '
        f'fill="currentColor" opacity=".55">{t}</text>' for t, x, y in labels)
    return (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" class="gf-compass" '
            f'aria-hidden="true"><circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="currentColor" '
            f'stroke-opacity=".18" stroke-width="1.5"/>{labels_html}'
            f'<g transform="rotate({to_deg} {cx} {cy})">'
            f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - r + 6}" stroke="currentColor" stroke-width="3" '
            f'stroke-linecap="round"/><path d="M {cx - 7} {cy - r + 18} L {cx} {cy - r + 4} L {cx + 7} '
            f'{cy - r + 18} Z" fill="currentColor"/></g></svg>')


def _angle_diff_py(a, b):
    return abs(((b - a + 540) % 360) - 180)


def _detect_wind_shift_py(times, spd, gust, wdir, start, horizon=12):
    """Strežniška kopija detectWindShift() iz gasilec.js, za rezervni prikaz
    brez JS. Isti pragova (45°, 15 km/h) — glej opombo v gasilec.js."""
    n = min(len(times) - start, horizon)
    for di in range(max(0, n - 1)):
        i = start + di
        for dj in range(di + 1, n):
            j = start + dj
            diff = _angle_diff_py(wdir[i], wdir[j])
            if diff < 45:
                continue
            if max(spd[i] or 0, gust[i] or 0) >= 15 or max(spd[j] or 0, gust[j] or 0) >= 15:
                return {"i": i, "j": j, "degrees": round(diff)}
    return None


def build_intervencija_page(payload, arso_alerts, arso_ok, arso_checked_at):
    today_fwi = payload["fwi"]
    today_level = payload["level"]
    today_isi = next((d["isi"] for d in payload["days"] if d["date"] == payload["date"]), None)

    body_html = '<p class="gf-note">Trenutni podatki za Rečico ob Savinji trenutno niso na voljo.</p>'
    shift_html = ""
    try:
        data = fetch_current_hourly()
        h = data.get("hourly") or {}
        times = h.get("time") or []
        temp = h.get("temperature_2m") or []
        rh = h.get("relative_humidity_2m") or []
        precip = h.get("precipitation") or []
        spd = h.get("wind_speed_10m") or []
        gust = h.get("wind_gusts_10m") or []
        wdir = h.get("wind_direction_10m") or []
        now_iso = _dt.datetime.now().strftime("%Y-%m-%dT%H:00")
        i = next((k for k, t in enumerate(times) if t >= now_iso), 0)
        precip3 = sum(v or 0 for v in precip[i:i + 3])
        body_html = f'''  <div class="gf-interv-body">
      <div class="gf-compass-wrap" id="gf-interv-compass">
        {_compass_svg_py(wdir[i])}
        <div class="gf-compass-lbl">{_dir_label(wdir[i])} → {_dir_label((wdir[i] + 180) % 360)} · {spd[i]:.0f} km/h</div>
      </div>
      <div class="gf-interv-stats" id="gf-interv-stats">
        <div class="gf-stat"><b>{temp[i]:.1f} °C</b><span>Temperatura</span></div>
        <div class="gf-stat"><b>{rh[i]:.0f} %</b><span>Vlaga</span></div>
        <div class="gf-stat"><b>{gust[i]:.0f} km/h</b><span>Sunki vetra</span></div>
        <div class="gf-stat"><b>{precip3:.1f} mm</b><span>Padavine 3 h</span></div>
        <div class="gf-stat"><b>{today_fwi:.1f}</b><span>FWI danes ({_esc(today_level)})</span></div>
        <div class="gf-stat"><b>{today_isi:.1f}</b><span>ISI danes</span></div>
      </div>
    </div>'''
        shift = _detect_wind_shift_py(times, spd, gust, wdir, i)
        if shift:
            shift_html = f'''  <div class="gf-shift-warn" id="gf-interv-shift">
      <b>⚠ MeteoGasilec kriterij: možen obrat vetra</b>
      Ob {times[shift["j"]][11:16]} pričakovan obrat smeri za +{shift["degrees"]}°
      ({_dir_label(wdir[shift["i"]])} → {_dir_label(wdir[shift["j"]])}),
      sunki {gust[shift["i"]]:.0f} → {gust[shift["j"]]:.0f} km/h.
      Ni uradno opozorilo ARSO.
    </div>'''
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  ⚠ intervencija SSR: {e}", file=sys.stderr)

    fwi_json = json.dumps({"fwi": today_fwi, "level": today_level, "isi": today_isi})
    # Za začetno stanje briefinga (preden živi klic morda spodleti) — glej opombo
    # ob lastArsoAlerts spodaj in ob arso_widget_html() zakaj se posnetek ne sme
    # tiho izgubiti.
    arso_reserve_json = json.dumps([
        {"level": a.get("level") or "yellow", "text": a.get("text") or a.get("desc") or "Opozorilo"}
        for a in (arso_alerts if arso_ok else [])
    ])
    inner = f'''  <p class="post-meta">Hiter operativni pogled: dovoli lokacijo (GPS) in v nekaj sekundah dobiš veter,
  morebiten obrat vetra in gumb za briefing. <span id="gf-fwi-note">Indeks FWI/ISI spodaj je izračunan za Rečico ob
  Savinji.</span> Glej <a href="/meteogasilec/metodologija/">metodologijo</a>.</p>
  <div class="gf-interv-card">
    <div class="gf-interv-loc">
      <b id="gf-interv-loc">📍 Rečica ob Savinji (privzeto)</b>
      <button class="gf-btn" id="btn-gps" type="button">📍 Uporabi mojo lokacijo</button>
    </div>
{arso_widget_html(arso_alerts, arso_ok, arso_checked_at, compact=True)}
    <div id="gf-interv-body">
{body_html}
    </div>
    <div class="gf-terrain">
      <h3 style="margin:.2rem 0 .5rem">🏔 Veter + teren</h3>
      <div id="gf-interv-terrain"><p class="gf-note" style="margin:0 0 .5rem">Nalaganje terena …</p></div>
    </div>
    <div id="gf-interv-shift-wrap">
{shift_html}
    </div>
    <p class="gf-note" id="gf-interv-note"></p>
    <p class="gf-note"><a id="gf-interv-map" href="/meteogasilec/karta/" target="_blank" rel="noopener">🗺 Odpri operativno karto (hidranti, požarišča)</a></p>
    <div class="gf-briefing">
      <h2 style="margin-top:0">📋 Briefing</h2>
      <pre id="gf-briefing-pre">Nalaganje…</pre>
      <div class="gf-briefing-actions">
        <button class="gf-btn secondary" id="btn-copy" type="button">📋 Kopiraj briefing</button>
        <button class="gf-btn secondary" id="btn-share" type="button" hidden>📤 Deli</button>
      </div>
    </div>
  </div>
  <script src="/meteogasilec/gasilec.js"></script>
  <script>(function(){{
    var DEFAULT_LAT={fm.LAT!r}, DEFAULT_LON={fm.LON!r};
    var FWI_TODAY={fwi_json};
    var currentFWI={{fwi:FWI_TODAY.fwi,level:FWI_TODAY.level,isi:FWI_TODAY.isi,isLocal:false}};
    var lastData=null;
    var lastArsoAlerts={arso_reserve_json};
    function fmtHM(t){{return t?t.slice(11,16):'—';}}
    function refreshBriefingArso(){{
      if(lastData){{
        lastData.arsoAlerts=lastArsoAlerts;
        document.getElementById('gf-briefing-pre').textContent=Gasilec.buildBriefing(lastData);
      }}
    }}
    Gasilec.renderArsoWidget(document.getElementById('gf-arso-compact'),{{compact:true}}).then(function(res){{
      if(res){{lastArsoAlerts=res.alerts||[];refreshBriefingArso();}}
    }});
    function updateFwiDisplay(){{
      var fwiVal=document.getElementById('gf-fwi-val'),fwiLvl=document.getElementById('gf-fwi-lvl'),
          isiVal=document.getElementById('gf-isi-val'),note=document.getElementById('gf-fwi-note');
      if(fwiVal)fwiVal.textContent=currentFWI.fwi.toFixed(1);
      if(fwiLvl)fwiLvl.textContent='FWI danes ('+currentFWI.level+')'+(currentFWI.isLocal?' · tvoja lokacija':'');
      if(isiVal)isiVal.textContent=currentFWI.isi.toFixed(1);
      if(note)note.textContent=currentFWI.isLocal
        ?'Indeks FWI/ISI spodaj je izračunan za tvojo GPS lokacijo.'
        :'Indeks FWI/ISI spodaj je izračunan za Rečico ob Savinji.';
      if(lastData){{
        lastData.fwi=currentFWI.fwi;lastData.isi=currentFWI.isi;lastData.fwiLevel=currentFWI.level;
        document.getElementById('gf-briefing-pre').textContent=Gasilec.buildBriefing(lastData);
      }}
    }}
    function fetchLocalFwi(lat,lon){{
      var url='https://api.open-meteo.com/v1/forecast?latitude='+lat+'&longitude='+lon
        +'&daily=temperature_2m_max,relative_humidity_2m_min,windspeed_10m_max,precipitation_sum'
        +'&past_days=7&forecast_days=1&timezone=Europe%2FLjubljana';
      fetch(url).then(function(r){{return r.json();}}).then(function(j){{
        var series=Gasilec.fwiSeriesFromDaily(j.daily||{{}});
        if(!series.length)return;
        var today=series[series.length-1];
        currentFWI={{fwi:today.fwi,level:today.level,isi:today.isi,isLocal:true}};
        updateFwiDisplay();
      }}).catch(function(e){{console.warn('lokalni FWI:',e);}});
    }}
    function render(json,label,lat,lon){{
      var h=json.hourly||{{}};
      var times=h.time||[],temp=h.temperature_2m||[],rh=h.relative_humidity_2m||[],
          precip=h.precipitation||[],spd=h.wind_speed_10m||[],gust=h.wind_gusts_10m||[],wdir=h.wind_direction_10m||[];
      var nowIso=new Date().toISOString().slice(0,13)+':00';
      var i=0;for(var k=0;k<times.length;k++){{if(times[k]>=nowIso){{i=k;break;}}}}
      var precip3=0;for(var p=i;p<Math.min(i+3,precip.length);p++){{precip3+=precip[p]||0;}}
      document.getElementById('gf-interv-loc').textContent='📍 '+label;
      document.getElementById('gf-interv-compass').innerHTML=
        Gasilec.windCompassSvg(wdir[i])+'<div class="gf-compass-lbl">'+Gasilec.dirLabel(wdir[i])+' → '+
        Gasilec.dirLabel((wdir[i]+180)%360)+' · '+Math.round(spd[i])+' km/h</div>';
      document.getElementById('gf-interv-stats').innerHTML=
        '<div class="gf-stat"><b>'+temp[i].toFixed(1)+' °C</b><span>Temperatura</span></div>'
        +'<div class="gf-stat"><b>'+Math.round(rh[i])+' %</b><span>Vlaga</span></div>'
        +'<div class="gf-stat"><b>'+Math.round(gust[i])+' km/h</b><span>Sunki vetra</span></div>'
        +'<div class="gf-stat"><b>'+precip3.toFixed(1)+' mm</b><span>Padavine 3 h</span></div>'
        +'<div class="gf-stat"><b id="gf-fwi-val">'+currentFWI.fwi.toFixed(1)+'</b><span id="gf-fwi-lvl">FWI danes ('+currentFWI.level+')</span></div>'
        +'<div class="gf-stat"><b id="gf-isi-val">'+currentFWI.isi.toFixed(1)+'</b><span>ISI danes</span></div>';
      var shift=Gasilec.detectWindShift(times.slice(i),spd.slice(i),gust.slice(i),wdir.slice(i),{{horizonHours:12}});
      var shiftWrap=document.getElementById('gf-interv-shift-wrap');
      if(shift.detected){{
        shiftWrap.innerHTML='<div class="gf-shift-warn"><b>⚠ MeteoGasilec kriterij: možen obrat vetra</b>'
          +'Ob '+fmtHM(shift.toTime)+' pričakovan obrat smeri za +'+shift.degrees+'° ('
          +Gasilec.dirLabel(shift.fromDir)+' → '+Gasilec.dirLabel(shift.toDir)+'), sunki '
          +Math.round(shift.gustBefore)+' → '+Math.round(shift.gustAfter)+' km/h. Ni uradno opozorilo ARSO.</div>';
      }}else{{
        shiftWrap.innerHTML='';
      }}
      lastData={{
        timeLabel:new Date().toLocaleTimeString('sl',{{hour:'2-digit',minute:'2-digit'}}),
        placeLabel:label, temp:temp[i], rh:rh[i], windSpeed:spd[i], windGust:gust[i],
        windFromDeg:wdir[i], precip3h:precip3, fwi:currentFWI.fwi, fwiLevel:currentFWI.level,
        isi:currentFWI.isi, shift:shift.detected?shift:null, arsoAlerts:lastArsoAlerts,
      }};
      document.getElementById('gf-briefing-pre').textContent=Gasilec.buildBriefing(lastData);
      if(lat!=null&&lon!=null){{
        var windToDeg=(wdir[i]+180)%360;
        Gasilec.fetchElevationGrid(parseFloat(lat),parseFloat(lon)).then(function(grid){{
          var sa=Gasilec.computeSlopeAspect(grid);
          Gasilec.renderTerrainWind(document.getElementById('gf-interv-terrain'),sa.aspectDeg,windToDeg,sa.slopeDeg);
        }}).catch(function(e){{console.warn('teren:',e);}});
      }}
    }}
    function load(lat,lon,label){{
      var url='https://api.open-meteo.com/v1/forecast?latitude='+lat+'&longitude='+lon
        +'&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_gusts_10m,wind_direction_10m'
        +'&forecast_days=2&timezone=Europe%2FLjubljana';
      fetch(url).then(function(r){{return r.json();}}).then(function(j){{render(j,label,lat,lon);}}).catch(function(e){{
        console.warn('intervencija:',e);
      }});
    }}
    document.getElementById('btn-gps').addEventListener('click',function(){{
      var note=document.getElementById('gf-interv-note');
      if(!navigator.geolocation){{note.textContent='GPS ni podprt v tem brskalniku — prikazani ostajajo podatki za Rečico ob Savinji.';return;}}
      note.textContent='Pridobivam lokacijo …';
      navigator.geolocation.getCurrentPosition(function(pos){{
        note.textContent='';
        var lat=pos.coords.latitude.toFixed(4),lon=pos.coords.longitude.toFixed(4);
        document.getElementById('gf-interv-map').href='/meteogasilec/karta/?lat='+lat+'&lon='+lon;
        currentFWI={{fwi:FWI_TODAY.fwi,level:FWI_TODAY.level,isi:FWI_TODAY.isi,isLocal:false}};
        load(lat,lon,'Tvoja lokacija ('+lat+', '+lon+')');
        if(Gasilec.distanceKm(parseFloat(lat),parseFloat(lon),DEFAULT_LAT,DEFAULT_LON)>2){{
          fetchLocalFwi(lat,lon);
        }}
      }},function(err){{
        note.textContent='Lokacija ni na voljo (zavrnjeno ali napaka) — prikazani ostajajo podatki za Rečico ob Savinji.';
      }},{{enableHighAccuracy:true,timeout:10000}});
    }});
    Gasilec.wireBriefingButtons(document.getElementById('btn-copy'),document.getElementById('btn-share'),function(){{
      return lastData?Gasilec.buildBriefing(lastData):null;
    }});
    load(DEFAULT_LAT,DEFAULT_LON,'Rečica ob Savinji (privzeto)');
  }})();</script>'''
    return subpage_shell("intervencija", "Intervencija zdaj",
                          "Hiter operativni pogled za gasilske intervencije: veter po GPS lokaciji, samodejni "
                          "detektor obrata vetra in gumb za kopiranje briefinga.", inner)


# ── operativna karta (hidranti + FIRMS) ─────────────────────────────────────

HIDRANTI_JSON = os.path.join(ROOT, "meteogasilec", "hidranti.json")
_STATUS_DOT = {"verified": "🟢", "osm": "🟡", "broken": "🔴"}
_STATUS_LABEL = {"verified": "preverjeno", "osm": "samo OSM", "broken": "nedelujoče"}


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_hydrants():
    try:
        with open(HIDRANTI_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def build_karta_page():
    hdata = load_hydrants()
    items = list((hdata or {}).get("items") or [])
    for it in items:
        it["_dist"] = _haversine_km(fm.LAT, fm.LON, it["lat"], it["lon"])
    items.sort(key=lambda it: it["_dist"])
    nearest = items[:10]

    if nearest:
        rows = "\n".join(
            f'<tr><td>{it["_dist"]:.1f} km</td><td>{_esc(it["label"])}</td>'
            f'<td>{_STATUS_DOT.get(it["status"], "🟡")} {_esc(_STATUS_LABEL.get(it["status"], "samo OSM"))}</td></tr>'
            for it in nearest
        )
        table_html = f'''  <table class="gf-tbl">
    <thead><tr><th>Razdalja od Rečice</th><th>Tip</th><th>Status</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>'''
    else:
        table_html = '<p class="gf-note">Seznam hidrantov trenutno ni na voljo.</p>'

    # _dist je bil samo za SSR razvrščanje — ne pošiljamo ga v klientski JSON.
    hydrants_json = json.dumps([{k: v for k, v in it.items() if k != "_dist"} for it in items], ensure_ascii=False)

    inner = f'''  <p class="post-meta">Hidranti in odvzemna mesta (OpenStreetMap, Zgornja Savinjska dolina) ter zaznana
  požarišča (NASA FIRMS) na eni interaktivni karti. Prikaz je informativen — za dostop z vozilom vedno preveri stanje
  na terenu.</p>
  <div class="gf-map-layers">
    <label><input type="checkbox" id="gf-layer-hydrants" checked> 💧 Hidranti in odvzemna mesta</label>
    <label><input type="checkbox" id="gf-layer-firms"> 🛰 Požarišča (FIRMS)</label>
    <button class="gf-btn" id="btn-gps" type="button">📍 Uporabi mojo lokacijo</button>
  </div>
  <div id="gf-map"></div>
  <p class="gf-note" id="gf-map-note"></p>
  <h2>💧 Najbližji hidranti (od Rečice ob Savinji)</h2>
{table_html}
  <p class="gf-note">Vir: prispevki <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>,
  osveženo dnevno. Status 🟡 »samo OSM« pomeni, da podatka ni potrdilo lokalno gasilsko društvo — pred zanašanjem nanj
  preveri stanje na terenu.</p>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script>(function(){{
    if(typeof L==='undefined'){{
      document.getElementById('gf-map-note').textContent='Interaktivna karta trenutno ni na voljo — glej seznam spodaj.';
      return;
    }}
    var HYDRANTS={hydrants_json};
    var DEFAULT_LAT={fm.LAT!r}, DEFAULT_LON={fm.LON!r};
    var params=new URLSearchParams(location.search);
    var qLat=parseFloat(params.get('lat')), qLon=parseFloat(params.get('lon'));
    var startLat=isFinite(qLat)?qLat:DEFAULT_LAT, startLon=isFinite(qLon)?qLon:DEFAULT_LON;
    var STATUS_COLOR={{verified:'#22c55e',osm:'#f59e0b',broken:'#ef4444'}};
    var STATUS_LABEL={{verified:'preverjeno',osm:'samo OSM',broken:'nedelujoče'}};
    var TYPE_LABEL={{fire_hydrant:'Hidrant',suction_point:'Sesalno mesto',water_tank:'Požarni rezervoar'}};

    var map=L.map('gf-map').setView([startLat,startLon],13);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{
      maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }}).addTo(map);

    var userMarker=L.marker([startLat,startLon],{{title:'Lokacija'}}).addTo(map)
      .bindPopup(isFinite(qLat)?'📍 Izbrana lokacija':'📍 Rečica ob Savinji (privzeto)');

    var hydrantLayer=L.layerGroup().addTo(map);
    HYDRANTS.forEach(function(it){{
      var col=STATUS_COLOR[it.status]||'#f59e0b';
      var m=L.circleMarker([it.lat,it.lon],{{radius:7,color:'#fff',weight:1.5,fillColor:col,fillOpacity:.9}});
      var tagsHtml='';
      if(it.tags){{
        if(it.tags.diameter)tagsHtml+='Premer: '+it.tags.diameter+' mm<br>';
        if(it.tags.pressure)tagsHtml+='Tlak: '+it.tags.pressure+' bar<br>';
        if(it.tags.flow_rate)tagsHtml+='Pretok: '+it.tags.flow_rate+' l/min<br>';
      }}
      m.bindPopup('<b>'+(TYPE_LABEL[it.type]||it.type)+'</b><br>'+tagsHtml
        +(STATUS_LABEL[it.status]||'samo OSM')+'<br><a href="https://www.openstreetmap.org/?mlat='+it.lat+'&mlon='+it.lon
        +'#map=18/'+it.lat+'/'+it.lon+'" target="_blank" rel="noopener">Navigacija →</a>');
      hydrantLayer.addLayer(m);
    }});

    var firmsLayer=L.layerGroup();
    fetch('{WORKER_BASE}/pozari').then(function(r){{return r.json();}}).then(function(d){{
      if(!d||!d.fires)return;
      d.fires.forEach(function(it){{
        if(it.lat==null||it.lon==null)return;
        var m=L.circleMarker([it.lat,it.lon],{{radius:6,color:'#fff',weight:1.5,fillColor:'#dc2626',fillOpacity:.85}});
        m.bindPopup('<b>🛰 Satelitska toplotna anomalija</b><br>'+(it.date||'')+' '+(it.time||'')+' UTC<br>Zaupanje: '+(it.conf||'—'));
        firmsLayer.addLayer(m);
      }});
    }}).catch(function(){{}});

    document.getElementById('gf-layer-hydrants').addEventListener('change',function(e){{
      if(e.target.checked)map.addLayer(hydrantLayer);else map.removeLayer(hydrantLayer);
    }});
    document.getElementById('gf-layer-firms').addEventListener('change',function(e){{
      if(e.target.checked)map.addLayer(firmsLayer);else map.removeLayer(firmsLayer);
    }});

    document.getElementById('btn-gps').addEventListener('click',function(){{
      var note=document.getElementById('gf-map-note');
      if(!navigator.geolocation){{note.textContent='GPS ni podprt v tem brskalniku.';return;}}
      note.textContent='Pridobivam lokacijo …';
      navigator.geolocation.getCurrentPosition(function(pos){{
        note.textContent='';
        var lat=pos.coords.latitude,lon=pos.coords.longitude;
        map.setView([lat,lon],14);
        userMarker.setLatLng([lat,lon]).bindPopup('📍 Tvoja lokacija').openPopup();
      }},function(){{
        note.textContent='Lokacija ni na voljo (zavrnjeno ali napaka).';
      }},{{enableHighAccuracy:true,timeout:10000}});
    }});
  }})();</script>'''
    leaflet_css = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" '
                   'integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">'
                   '<style>#gf-map{height:420px;border-radius:1rem;overflow:hidden;margin:.8rem 0;'
                   'border:1px solid var(--card-border)}.gf-map-layers{display:flex;flex-wrap:wrap;gap:.8rem 1.2rem;'
                   'align-items:center;font-size:.85rem;margin:.6rem 0}.gf-map-layers label{display:flex;'
                   'align-items:center;gap:.35rem;cursor:pointer}</style>')
    return subpage_shell("karta", "Operativna karta",
                          "Hidranti, odvzemna mesta in zaznana požarišča (NASA FIRMS) na eni interaktivni karti za "
                          "Zgornjo Savinjsko dolino.", inner, extra_head=leaflet_css)


# ── gasilski kalkulator ──────────────────────────────────────────────────────

KALKULATOR_HTML = '''  <p class="post-meta">Trije neodvisni hitri izračuni. Vpiši vrednosti — rezultat se izračuna sproti,
  brez gumba. Uporabljaj skupaj s preverjenimi parametri svoje opreme, ne kot edini vir za odločanje.</p>
  <div class="gf-interv-card">
    <h2 style="margin-top:0">🚒 Čas praznjenja cisterne</h2>
    <div class="gf-calc-row">
      <label>Voda v cisterni (L) <input type="number" id="c-vol" value="5000" min="0"></label>
      <label>Skupni pretok (L/min) <input type="number" id="c-flow" value="400" min="1"></label>
    </div>
    <p class="gf-calc-result" id="c-time-out">⏱ —</p>
  </div>
  <div class="gf-interv-card">
    <h2 style="margin-top:0">🧯 Penilo</h2>
    <div class="gf-calc-row">
      <label>Voda (L) <input type="number" id="f-vol" value="4000" min="0"></label>
      <label>Koncentracija (%) <input type="number" id="f-conc" value="3" min="0" max="100" step="0.5"></label>
    </div>
    <p class="gf-calc-result" id="f-out">🧯 —</p>
  </div>
  <div class="gf-interv-card">
    <h2 style="margin-top:0">⬆ Statični tlak (višinska razlika)</h2>
    <div class="gf-calc-row">
      <label>Črpalka (m n.v.) <input type="number" id="h-pump" value="460"></label>
      <label>Ročnik (m n.v.) <input type="number" id="h-nozzle" value="530"></label>
    </div>
    <p class="gf-calc-result" id="h-out">⬆ —</p>
    <p class="gf-note">Približen izračun (0,0981 bar na vsak meter višinske razlike) — brez upoštevanja izgub v cevovodu.</p>
  </div>
  <script>(function(){
    function num(id){var v=parseFloat(document.getElementById(id).value);return isFinite(v)?v:0;}
    function fmtTime(min){
      if(min<=0)return '—';
      var h=Math.floor(min/60),m=Math.round(min%60);
      return (h>0?h+' h ':'')+m+' min';
    }
    function calcCisterna(){
      var vol=num('c-vol'),flow=num('c-flow');
      document.getElementById('c-time-out').textContent='⏱ '+(flow>0?fmtTime(vol/flow):'—');
    }
    function calcPenilo(){
      var vol=num('f-vol'),conc=num('f-conc');
      var foam=vol*conc/100;
      document.getElementById('f-out').textContent='🧯 '+foam.toFixed(0)+' L penila (na '+vol.toFixed(0)+' L vode)';
    }
    function calcVisina(){
      var pump=num('h-pump'),nozzle=num('h-nozzle');
      var dh=nozzle-pump;
      var bar=Math.abs(dh)*0.0981;
      var smer=dh>0?'izguba (ročnik višje)':dh<0?'pridobitev (ročnik nižje)':'brez razlike';
      document.getElementById('h-out').textContent='⬆ Δh='+dh.toFixed(0)+' m → '+bar.toFixed(2)+' bar ('+smer+')';
    }
    ['c-vol','c-flow'].forEach(function(id){document.getElementById(id).addEventListener('input',calcCisterna);});
    ['f-vol','f-conc'].forEach(function(id){document.getElementById(id).addEventListener('input',calcPenilo);});
    ['h-pump','h-nozzle'].forEach(function(id){document.getElementById(id).addEventListener('input',calcVisina);});
    calcCisterna();calcPenilo();calcVisina();
  })();</script>'''


def build_kalkulator_page():
    return subpage_shell("kalkulator", "Gasilski kalkulator",
                          "Čas praznjenja cisterne, potrebno penilo in statični tlak iz višinske razlike — trije "
                          "hitri izračuni za gasilske intervencije.", KALKULATOR_HTML)


# ── vodotoki (ARSO hidro postaje) ────────────────────────────────────────────
# Ponovna uporaba fetch_arso_stations()/station_status() iz
# generate_vodostaj_page.py (uvožen kot `vod` na vrhu datoteke) — ne
# podvajaj branja ARSO hidro XML-ja. Polna slika (GloFAS napoved, zgodovina
# poplav) ostaja na /vodostaj-savinje/, ta stran je samo strnjen prikaz v
# MeteoGasilec kontekstu.

# Isti pragovi/imena kot station_status() v generate_vodostaj_page.py — samo
# barva čipa je tu, ker je le vizualna (Python stran ne zna barv).
_STATION_STATUS_COLOR = {"Normalen": "#22c55e", "Povečan": "#eab308", "Opozorilo": "#f97316", "Alarm": "#ef4444"}


def build_vodotoki_page():
    try:
        stations = vod.fetch_arso_stations()[:3]
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError) as e:
        print(f"  ⚠ vodotoki: {e}", file=sys.stderr)
        stations = []

    if stations:
        cards = []
        for s in stations:
            status = vod.station_status(s["pretok"])
            col = _STATION_STATUS_COLOR.get(status, "#94a3b8")
            cards.append(f'''    <div class="gf-station-card">
      <h3>{_esc(s["name"])}</h3>
      <div class="gf-station-stats">
        <div><b>{seo.num(s["vodostaj"], 0) if s["vodostaj"] is not None else "—"} cm</b><span>Vodostaj</span></div>
        <div><b>{seo.num(s["pretok"], 1) if s["pretok"] is not None else "—"} m³/s</b><span>Pretok</span></div>
      </div>
      <span class="gf-status-chip" style="background:{col}22;color:{col};border:1px solid {col}66">{_esc(status)}</span>
    </div>''')
        table_html = '  <div class="gf-station-grid">\n' + "\n".join(cards) + '\n  </div>'
    else:
        table_html = '<p class="gf-note">Postaje ARSO trenutno niso dosegljive.</p>'

    inner = f'''  <p class="post-meta">Najbližje merilne postaje ARSO ob Savinji — orientacija pri presoji vodnih virov
  med intervencijo.</p>
{table_html}
  <p class="gf-note"><b>Vodostaj postaje ne pove, ali je vodotok dostopen z vozilom</b> — pove le, koliko vode teče
  mimo merilne točke. Za dejanski dostop (breg, globina, pretok na odjemnem mestu) vedno preveri stanje na terenu.
  »Povečan«/»opozorilo«/»alarm« so orientacijski pragovi (postaja Letuš), ne uradna klasifikacija ARSO/URSZR.</p>
  <p class="gf-note">Polna slika — 7-dnevna napoved pretoka (GloFAS) in zgodovina poplav Savinje — je na
  <a href="/vodostaj-savinje/">strani Vodostaj Savinje</a>.</p>'''
    return subpage_shell("vodotoki", "Vodotoki",
                          "Najbližje merilne postaje ARSO ob Savinji — vodostaj, pretok in orientacijska ocena "
                          "stanja za gasilske intervencije v Zgornji Savinjski dolini.", inner)


# level -> (emoji, banner besedilo). Isti FWI_LEVELS imena kot povsod drugod
# na strani (gasilec_model.FWI_LEVELS) — ne nov razred stopenj.
_NASVETI_STATUS = {
    "Nizka": ("✅", "Danes ni posebnih omejitev za kurjenje v naravi."),
    "Zmerna": ("✅", "Danes ni posebnih omejitev za kurjenje v naravi — bodi previden."),
    "Visoka": ("⚠️", "Kurjenje danes odsvetovano — preveri morebitne lokalne odloke."),
    "Zelo visoka": ("🚫", "Kurjenje danes močno odsvetovano — možna prepoved z odlokom občine/URSZR."),
    "Ekstremna": ("🚫", "Kurjenje danes močno odsvetovano — možna prepoved z odlokom občine/URSZR."),
}

_NASVETI_TIPS = [
    (_FI_CIGARETTE, "#f59e0b", "Ne odmetavaj ogorkov", "Cigaretni ogorki v suhi travi ali stelji so pogost vzrok vžiga — vedno v pepelnik ali vodo."),
    (_FI_WATCHFIRE, "#ef4444", "Nadzoruj in pogasi", "Kres oz. ogenj v naravi vedno nadzoruj in ga po končanem kurjenju temeljito pogasi, tudi žerjavico."),
    (_FI_VETER, "#22d3ee", "Pazi na veter", 'Ob sunkih vetra (glej <a href="/meteogasilec/vreme-intervencije/">vreme za intervencije</a>) se ogenj širi bistveno hitreje in nepredvidljivo.'),
]

_NASVETI_CONTACTS = [
    (_FI_PHONE, "#ef4444", "tel:112", "112", "Enotna evropska številka za klic v sili"),
    (_FI_SHIELD, "#84cc16", "https://www.gzs-slo.si/", "Gasilska zveza Slovenije", "gzs-slo.si"),
    (_FI_SHIELD, "#0ea5e9", "https://www.gov.si/drzavni-organi/organi-v-sestavi/uprava-za-zascito-in-resevanje/",
     "URSZR", "Uprava RS za zaščito in reševanje"),
    (_FI_OGROZENOST, "#f59e0b", "https://meteo.arso.gov.si/met/sl/agromet/pozar/", "ARSO",
     "Uradni indeks požarne ogroženosti"),
]


def build_nasveti_page(payload):
    today_level = payload["level"]
    today_color = next((d["color"] for d in payload["days"] if d["date"] == payload["date"]), "#84cc16")
    emoji, msg = _NASVETI_STATUS.get(today_level, ("ℹ️", "Preveri trenutno požarno ogroženost zgoraj."))
    banner = (f'  <div class="gf-status-banner" style="background:{today_color}22;border:1px solid {today_color}66">'
              f'<span class="emoji">{emoji}</span><span>{_esc(msg)} (FWI danes: {_esc(today_level)})</span></div>')

    tips_html = "\n".join(
        f'    <div class="gf-tip-card" style="--fa:{accent};--fa-soft:{_rgba(accent, ".16")}">'
        f'<span class="gf-tip-ic">{icon}</span><div><b>{_esc(title)}</b><p>{text}</p></div></div>'
        for icon, accent, title, text in _NASVETI_TIPS
    )

    contacts_html = "\n".join(
        f'    <a class="gf-contact-card" href="{href}" style="--fa:{accent};--fa-soft:{_rgba(accent, ".16")}" '
        + ('target="_blank" rel="noopener nofollow"' if href.startswith("http") else "")
        + f'><span class="gf-contact-ic">{icon}</span><span><b>{_esc(label)}</b><span>{_esc(sub)}</span></span></a>'
        for icon, accent, href, label, sub in _NASVETI_CONTACTS
    )

    inner = f'''  <p class="post-meta">Kratek povzetek pravil in kontaktov — ne nadomešča uradnih navodil URSZR ali
  lokalnega gasilskega poveljstva.</p>
{banner}
  <h2>🔥 Kurjenje v naravi</h2>
  <p>Kurjenje v naravnem okolju je ob visoki in zelo visoki požarni ogroženosti (glej banner zgoraj) močno
  odsvetovano, ob razglašeni povečani požarni ogroženosti pa je ponekod prepovedano z odlokom občine ali uprave za
  zaščito in reševanje. Pred kurjenjem vedno preveri trenutno stanje in morebitne lokalne omejitve.</p>
  <div class="gf-tip-grid">
{tips_html}
  </div>
  <h2>📞 Kontakti</h2>
  <div class="gf-contact-grid">
{contacts_html}
  </div>'''
    return subpage_shell("nasveti", "Nasveti in kontakti",
                          "Kurjenje v naravi, kdaj je odsvetovano ali prepovedano, in kontakti ob požaru v naravi.",
                          inner)


# (oznaka, ključ v payload["days"] vnosu, kratek opis) — vrstni red je vrstni
# red gradnje kanadskega sistema (trije vlažnostni indeksi → ISI/BUI → FWI).
_METODOLOGIJA_COMPONENTS = [
    ("FFMC", "ffmc", "Vlažnost tanke stelje"),
    ("DMC", "dmc", "Srednje globoka plast"),
    ("DC", "dc", "Globlja, sušna plast"),
    ("ISI", "isi", "Hitrost širjenja"),
    ("BUI", "bui", "Razpoložljivo gorivo"),
    ("FWI", "fwi", "Skupna ocena"),
]


def build_metodologija_page(payload):
    today = next((d for d in payload["days"] if d["date"] == payload["date"]), {}) or {}
    cards_html = "\n".join(
        f'    <div class="gf-component-card"><b>{today[key]}</b><span>{label}</span></div>'
        for label, key, _sub in _METODOLOGIJA_COMPONENTS if today.get(key) is not None
    )
    components_html = f'''  <h3 style="margin:1.2rem 0 .3rem">Današnje vrednosti (Rečica ob Savinji)</h3>
  <div class="gf-component-grid">
{cards_html}
  </div>''' if cards_html else ""

    inner = f'''  <p class="post-meta">MeteoGasilec ni uradna napoved ARSO ali URSZR. Je dodatna, samostojno izračunana
  ocena, namenjena orientaciji — pri odločanju vedno velja uradna ocena in odlok pristojnega organa.</p>
  <h2>🧮 Kanadski Fire Weather Index (FWI)</h2>
  <p>FWI je mednarodno uveljavljena metodologija (Van Wagner, kanadski gozdarski sistem), ki jo za Evropo uporablja
  tudi EFFIS/GWIS (evropski/globalni sistem za spremljanje požarov). Sestavljajo ga trije vlažnostni indeksi in trije
  izpeljani indeksi, ki se dan za dnem gradijo drug na drugem:</p>
  <ul>
    <li><b>FFMC</b> — vlažnost tanke stelje na površini (odziv na uro/dan).</li>
    <li><b>DMC</b> — vlažnost srednje globoke organske plasti (odziv na teden).</li>
    <li><b>DC</b> — sušnost globlje plasti (odziv na mesece — »spomin« na sušno obdobje).</li>
    <li><b>ISI</b> — pričakovana hitrost širjenja ognja glede na veter in FFMC.</li>
    <li><b>BUI</b> — razpoložljivo gorivo za zgorevanje (iz DMC in DC).</li>
    <li><b>FWI</b> — skupna ocena intenzivnosti požara, iz ISI in BUI.</li>
  </ul>
{components_html}
  <p>Izračun poganja dnevna napoved Open-Meteo (temperatura, najnižja relativna vlažnost, veter, padavine) za
  Rečico ob Savinji, 7 dni nazaj (za pravilen zagon vlažnostnih kod) in 7 dni naprej. Ista formula teče strežniško
  (ta stran, tools/gasilec_model.py) in v brskalniku (naslovnica, app.js) — vrednosti za isti dan se ujemata.</p>
  <h2>Kaj indeks ni</h2>
  <ul>
    <li>Ni napoved dejanskega požara — pove le, kako ugodni so pogoji, če bi do vžiga prišlo.</li>
    <li>Ni nadomestilo za uradni <a href="https://meteo.arso.gov.si/met/sl/agromet/pozar/" target="_blank" rel="noopener nofollow">ARSO indeks požarne ogroženosti</a>
    ali odloke lokalnih oblasti.</li>
    <li>Velja za eno točko (Rečica ob Savinji) — v drugih delih Slovenije se razmere lahko razlikujejo.</li>
  </ul>'''
    return subpage_shell("metodologija", "Metodologija",
                          "Kako MeteoGasilec izračuna indeks FWI, kateri podatki ga poganjajo in kaj indeks ni.",
                          inner)


def main():
    print(f"[{TODAY}] Gradim MeteoGasilec …")
    try:
        data = fm.fetch_daily()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Open-Meteo: {e}", file=sys.stderr)
        sys.exit(1)
    days = fm.fwi_series(data.get("daily") or {})
    if not days:
        print("✗ Open-Meteo ni vrnil dnevnih podatkov", file=sys.stderr)
        sys.exit(1)
    payload = fm.free_payload(days)

    os.makedirs(os.path.join(ROOT, "meteogasilec"), exist_ok=True)
    with open(os.path.join(ROOT, "meteogasilec", "index.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # En sam zajem uradnih opozoril ARSO za vso stran (naslovnica + kompakten
    # blok na /intervencija/) — glej arso_widget_html() zakaj se nikoli ne sme
    # tiho izpisati "ni aktivnih", če preverjanje sploh ni uspelo.
    try:
        arso_alerts, _arso_issued = fetch_arso_alerts()
        arso_ok = True
    except Exception as e:  # Worker je lahko nedosegljiv iz katerega koli razloga
        print(f"  ⚠ ARSO opozorila: {e}", file=sys.stderr)
        arso_alerts, arso_ok = [], False
    arso_checked_at = f"{_dt.datetime.now():%-d. %-m. ob %H:%M}"

    build_intervencija_page(payload, arso_alerts, arso_ok, arso_checked_at)
    build_karta_page()
    build_kalkulator_page()
    build_vodotoki_page()
    build_vreme_intervencije_page()
    build_nasveti_page(payload)
    build_metodologija_page(payload)

    # En sam seznam za vidni FAQ in za FAQPage shemo — ločena kopija bi (in je)
    # z besedilom počasi razšla (glej geo_audit.py: shema mora obljubljati
    # samo vprašanja/odgovore, ki so res prikazani).
    qa = [
        ("Je MeteoGasilec uradna napoved?",
         "Ne. Je samostojen izračun iz javnih podatkov Open-Meteo, po kanadski FWI metodologiji, ki jo za "
         "Evropo uporablja EFFIS/GWIS. Uradno oceno objavlja ARSO."),
        ("Zakaj se FWI tu in na naslovnici lahko za trenutek razlikujeta?",
         "Oba računata isto formulo iz iste Open-Meteo napovedi, a naslovnica jo osveži v brskalniku ob "
         "vsakem obisku, ta stran pa enkrat dnevno — v urah po novi napovedi je lahko majhna razlika."),
        ("Kaj pomenijo pike na karti NASA FIRMS?",
         "Satelitsko zaznane toplotne anomalije zadnjih dni, ne nujno potrjeni gozdni požari — glej opombo "
         "ob karti zgoraj."),
    ]
    faq_html = "\n".join(f'  <p><b>{q}</b><br>{a}</p>' for q, a in qa)

    body = f'''{BRAND_SWAP}
{seo.stn_badge()}
  <h1 class="page-title">MeteoGasilec — požarna ogroženost, Rečica ob Savinji</h1>
  <p class="post-meta">Uradna opozorila ARSO in lokalni indeks FWI za Rečico ob Savinji · osvežuje se dnevno ·
  {TODAY.isoformat()}</p>
{arso_widget_html(arso_alerts, arso_ok, arso_checked_at)}
{build_hero(payload)}
{interv_banner_html()}
  <script src="/meteogasilec/gasilec.js"></script>
  <script>(function(){{
    var el=document.getElementById('gf-fresh');
    if(el&&window.Gasilec)Gasilec.renderFreshness(el,el.closest('.gf-hero').dataset.generated,{{greenH:26,yellowH:50}});
    if(window.Gasilec)Gasilec.renderArsoWidget(document.getElementById('gf-arso-body'));
  }})();</script>
{feature_cards_html()}
{firms_widget_html()}
  <h2 id="faq">Pogosta vprašanja</h2>
{faq_html}'''

    url = "/meteogasilec/"
    title = "MeteoGasilec — požarna ogroženost, Rečica ob Savinji"
    desc = (f"Indeks požarne ogroženosti FWI danes: {payload['fwi']} ({payload['level']}). Veter za intervencije, "
            f"aktivna opozorila ARSO in zaznana požarišča NASA FIRMS za Rečico ob Savinji.")
    schema = "\n".join([
        seo.webpage_schema(url, title, desc),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoGasilec", None)]),
        seo.faq_schema(qa),
    ])
    head_extras = schema + "\n" + PAGE_CSS
    html = seo.page_shell(title, desc, url, head_extras, body)
    seo.write_page("meteogasilec/index.html", html, force=True)
    print(f"  → meteogasilec/index.html (FWI {payload['fwi']}, {payload['level']}) + 7 podstrani")


if __name__ == "__main__":
    main()
