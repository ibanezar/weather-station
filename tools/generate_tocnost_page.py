#!/usr/bin/env python3
"""
tools/generate_tocnost_page.py — /tocnost-napovedi/ forecast-accuracy scoreboard

Generates /tocnost-napovedi/index.html from forecast_verification.json (built
daily by tools/verify_forecasts.py): a running, transparent scoreboard of how
close the ARSO and Open-Meteo day-ahead forecasts for Rečica ob Savinji came
to what the station actually measured. Nobody publishes this systematically
for a Slovenian valley — it's a genuine, unique content type built entirely
from data this station already has.

Četrti tekmovalec je ECMWF AIFS — AI model, ki ga Windy prikazuje kot 15-dnevni
podaljšek modela ECMWF. Tu je zato, da se pove, kar se sicer ne meri nikjer:
koliko AI model pri 0,25° ločljivosti zaleže na dnu ozke doline.

Peti je Google DeepMind WeatherNext 2 (povprečje 64-članskega AI ansambla,
prek Open-Meteo). Isto vprašanje, drug AI model — in drug razvijalec.

Za ARSO in Open-Meteo semafor nima zgodovine za nazaj (ARSO arhiva napovedi ne
objavlja, Open-Meteo smo začeli beležiti sproti) — raste dan za dnem. AI modela
sta izjema, ker Open-Meteo hrani arhiv preteklih napovedi; napolnil ju je
tools/backfill_aifs_verification.py (WeatherNext 2 šele od 5. 9. 2026). Stran to pove namesto da bi delala vtis,
da so vsi viri merjeni enako dolgo.

Usage:
  python3 tools/generate_tocnost_page.py
"""
import datetime, json, math, os, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
VERIFICATION_PATH = os.path.join(ROOT, "forecast_verification.json")
MODEL_PATH = os.path.join(ROOT, "model", "recica-mos.json")

# ── Vizualna plast ───────────────────────────────────────────────────────────
# Vse je izrisano strežniško (HTML/CSS + inline SVG): stran deluje brez JS, vsebino vidijo tudi
# pajki, graf pa ne čaka na prenos forecast_verification.json (prej je pet črt čez 30 dni
# nastalo šele v brskalniku in bilo neberljivo).
#
# BARVE VIROV so preverjene z validate_palette.js (skill dataviz, --mode dark, podlaga #0a0f1c):
#   ARSO #c98500 · Open-Meteo #3987e5 · AIFS #d55181 · WN2 #9085e9 · MTR #199e70
# Vse preizkuse prestanejo v TEM vrstnem redu (najslabši sosednji par: CVD ΔE 9,4, normalni vid 19,7).
# Prejšnja paleta (#a78bfa ob #60a5fa) je pri barvni slepoti padla (ΔE 0,3). Barva pripada viru, ne
# mestu na lestvici; besedilo nikoli ne nosi barve serije, identiteto nosijo pika, legenda in oznake.
# Če barve menjaš, ju poženi skozi validator -- ne ugibaj.
SRC_DEFS = [  # (ključ, ime, kratko ime v tabelah)
    ("arso", "ARSO", "ARSO"),
    ("open_meteo", "Open-Meteo", "Open-Meteo"),
    ("aifs", "ECMWF AIFS", "AIFS"),
    ("wn2", "WeatherNext 2", "WN2"),
    ("meteorec", "MTR", "MTR"),
]
MES_KRATKO = ["", "jan.", "feb.", "mar.", "apr.", "maj", "jun.", "jul.", "avg.", "sep.", "okt.", "nov.", "dec."]

CHART_CSS = """<style>
:root{--s-arso:#c98500;--s-open_meteo:#3987e5;--s-aifs:#d55181;--s-wn2:#9085e9;--s-meteorec:#199e70;
  --tnc-surface:#0a0f1c;--tnc-grid:rgba(255,255,255,.08)}
.tnc-card{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:1rem 1.1rem;margin:.8rem 0 1rem}
.tnc-grid2{display:grid;gap:.8rem;grid-template-columns:minmax(0,1fr);margin:.8rem 0 1rem}
.tnc-grid2 .tnc-card{margin:0}
@media(min-width:760px){.tnc-grid2{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
.tnc-h3{font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:700;color:#fff;margin:0 0 .1rem}
.tnc-sub{font-size:.76rem;color:var(--muted);margin:0 0 .7rem;line-height:1.4}
.tnc-cap{font-size:.78rem;color:var(--muted);line-height:1.5;margin:.2rem 0 1.2rem}
.tnc-dot{display:inline-block;width:.62rem;height:.62rem;border-radius:50%;background:var(--c);margin-right:.4rem;vertical-align:baseline;flex:none}
.tnc-legend{display:flex;flex-wrap:wrap;gap:.3rem 1rem;margin:.9rem 0 .2rem;font-size:.84rem;color:var(--text)}
.tnc-legend span{display:inline-flex;align-items:center}
.tnc-legend span i.tnc-dot{margin-right:.4rem}

/* odgovor */
.tnc-answer{border-left:3px solid var(--green,#34d399);padding:.1rem 0 .1rem .95rem;margin:1rem 0 .4rem}
.tnc-answer p{margin:.3rem 0}
.tnc-answer>p:first-child{font-size:1.04rem;line-height:1.65;color:var(--text)}
.tnc-note{margin:.3rem 0}
.tnc-note summary{cursor:pointer;font-size:.8rem;color:var(--cyan,#22d3ee);padding:.2rem 0}
.tnc-note .muted-note{margin:.3rem 0 .2rem}

/* lestvica */
.lb{list-style:none;margin:0;padding:0}
.lb-row{display:grid;grid-template-columns:1.1rem 7.4rem minmax(0,1fr) 3rem;align-items:center;gap:.5rem;padding:.3rem 0}
.lb-rank{font-family:'JetBrains Mono',monospace;font-size:.72rem;font-weight:600;color:var(--muted)}
.lb-name{font-size:.86rem;color:var(--muted);white-space:nowrap;display:flex;align-items:center}
.lb-bar{display:block;height:.72rem;background:rgba(255,255,255,.05);border-radius:0 4px 4px 0;overflow:hidden}
.lb-bar b{display:block;height:100%;background:var(--c);border-radius:0 4px 4px 0}
.lb-val{text-align:right;font-size:.9rem;font-weight:600;font-variant-numeric:tabular-nums;color:var(--text)}
.lb-row.is-best .lb-name,.lb-row.is-best .lb-val{color:#fff;font-weight:700}
.lb-row.is-best .lb-rank{color:var(--green,#34d399)}
@media(max-width:420px){.lb-row{grid-template-columns:1rem 6.6rem minmax(0,1fr) 2.7rem;gap:.4rem}.lb-name{font-size:.82rem}}

/* včeraj: točkovni prikaz */
.dp-key{display:flex;flex-wrap:wrap;gap:.2rem 1rem;font-size:.78rem;color:var(--muted);margin:0 0 .5rem;align-items:center}
.dp-key span{display:inline-flex;align-items:center;gap:.4rem}
.dp-key .k-act{display:inline-block;width:2px;height:.9rem;background:#fff}
.dp-key .k-dot{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;background:#8da0bd}
.dp-row{display:grid;grid-template-columns:6.6rem minmax(0,1fr) 4.4rem;align-items:center;gap:.5rem;border-bottom:1px solid rgba(255,255,255,.06)}
.dp-row:last-child{border-bottom:0}
.dp-name{font-size:.84rem;color:var(--text);display:flex;align-items:center;white-space:nowrap}
.dp-track{position:relative;height:2.3rem;display:block}
.dp-track u{position:absolute;top:0;bottom:0;width:1px;background:var(--tnc-grid)}
.dp-act{position:absolute;top:.2rem;bottom:.2rem;width:2px;margin-left:-1px;background:#fff;border-radius:1px;z-index:1}
.dp-gap{position:absolute;top:50%;height:3px;margin-top:-1.5px;background:var(--c);opacity:.6;border-radius:2px}
.dp-dot{position:absolute;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:var(--c);box-shadow:0 0 0 2px var(--tnc-surface);z-index:2}
.dp-val{text-align:right;font-size:.9rem;font-weight:700;color:#fff;font-variant-numeric:tabular-nums;line-height:1.15}
.dp-val em{display:block;font-style:normal;font-weight:500;font-size:.74rem;color:var(--muted)}
.dp-axis{border-bottom:0}
.dp-axis .dp-track{height:1.1rem}
.dp-axis .dp-track span{position:absolute;top:0;transform:translateX(-50%);font-size:.7rem;color:var(--muted);font-variant-numeric:tabular-nums}
@media(max-width:420px){.dp-row{grid-template-columns:5.6rem minmax(0,1fr) 3.9rem;gap:.3rem}.dp-name{font-size:.78rem}.dp-name .tnc-dot,.bs-name .tnc-dot{margin-right:.3rem}}

/* pristranskost */
.bs-row{display:grid;grid-template-columns:6.6rem minmax(0,1fr) 3.6rem;align-items:center;gap:.5rem;padding:.28rem 0}
.bs-name{font-size:.84rem;color:var(--text);display:flex;align-items:center;white-space:nowrap}
.bs-track{position:relative;height:1rem;display:block}
.bs-track::before{content:"";position:absolute;left:50%;top:-.15rem;bottom:-.15rem;width:1px;background:#8da0bd}
.bs-track b{position:absolute;top:2px;bottom:2px;background:var(--c)}
.bs-track b.neg{right:50%;border-radius:4px 0 0 4px}
.bs-track b.pos{left:50%;border-radius:0 4px 4px 0}
.bs-val{text-align:right;font-size:.88rem;font-weight:600;color:var(--text);font-variant-numeric:tabular-nums}
.bs-axis{display:grid;grid-template-columns:6.6rem minmax(0,1fr) 3.6rem;gap:.5rem;font-size:.7rem;color:var(--muted);margin-bottom:.1rem}
.bs-axis span:nth-child(2){display:flex;justify-content:space-between}
@media(max-width:420px){.bs-row,.bs-axis{grid-template-columns:5.6rem minmax(0,1fr) 3.3rem;gap:.3rem}.bs-name{font-size:.78rem}}

/* trend */
.tnc-svg{width:100%;height:auto;display:block;max-width:600px;margin:0 auto}
.tnc-svg .sv-t{fill:var(--muted);font-size:11.5px;font-family:Inter,system-ui,sans-serif}
.tnc-svg .sv-l{fill:var(--text);font-size:11.5px;font-weight:600;font-family:Inter,system-ui,sans-serif}

/* toplotne tabele */
.tnc-heat{width:100%;border-collapse:separate;border-spacing:2px;table-layout:fixed;font-size:.85rem}
.tnc-heat caption{caption-side:top;text-align:left;font-size:.76rem;color:var(--muted);padding:0 0 .5rem;line-height:1.4}
.tnc-heat th{font-weight:500;color:var(--muted);font-size:.68rem;text-align:center;padding:.1rem 0 .3rem;vertical-align:bottom;line-height:1.2;word-break:break-word}
.tnc-heat th i.tnc-dot{display:block;margin:0 auto .25rem}
.tnc-heat td,.tnc-heat tbody th{padding:.34rem 0;border-radius:6px;text-align:center;font-variant-numeric:tabular-nums;vertical-align:middle}
.tnc-heat tbody th{text-align:left;color:var(--text);font-size:.8rem;font-weight:500;padding-left:.15rem;white-space:nowrap}
.tnc-heat tbody th a{color:var(--cyan,#22d3ee);text-decoration:none}
.tnc-heat tbody th a:hover{text-decoration:underline}
.tnc-heat td{color:#fff;font-weight:600;background:rgba(255,255,255,.03)}
.tnc-heat td.hv{background:color-mix(in srgb,#22d3ee calc(var(--h,0)*38%),rgba(255,255,255,.03))}
.tnc-heat td.best{box-shadow:inset 0 0 0 1.5px #fff}
.tnc-heat td.na{color:var(--muted);font-weight:400}
.tnc-heat td.meas{color:var(--text);font-weight:500;background:none}
.tnc-heat td small{display:block;font-weight:400;font-size:.66rem;color:var(--muted);line-height:1.1;margin-top:.05rem}
.tnc-heat tr.tot th,.tnc-heat tr.tot td{border-top:0;box-shadow:none}
.tnc-heat tr.tot th{color:#fff;font-weight:700}
.tnc-heat-key{display:flex;flex-wrap:wrap;gap:.2rem 1rem;align-items:center;font-size:.74rem;color:var(--muted);margin-top:.6rem}
.tnc-heat-key .hk-ramp{display:inline-block;width:3.4rem;height:.7rem;border-radius:3px;background:linear-gradient(90deg,rgba(255,255,255,.05),color-mix(in srgb,#22d3ee 38%,rgba(255,255,255,.03)));vertical-align:middle;margin:0 .35rem}
.tnc-heat-key .hk-best{display:inline-block;width:1.2rem;height:.8rem;border-radius:3px;box-shadow:inset 0 0 0 1.5px #fff;vertical-align:middle;margin-right:.35rem}

/* MTR po vodilnem času */
.sk-grp{padding:.5rem 0 .4rem;border-bottom:1px solid rgba(255,255,255,.06)}
.sk-grp:last-child{border-bottom:0}
.sk-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.15rem}
.sk-lead{font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:700;color:var(--text)}
.sk-imp{font-size:.76rem;color:var(--green,#34d399);font-weight:700;white-space:nowrap}
.sk-line{display:grid;grid-template-columns:6.4rem minmax(0,1fr) 2.8rem;gap:.5rem;align-items:center;padding:.14rem 0}
.sk-who{font-size:.8rem;color:var(--muted);display:flex;align-items:center;white-space:nowrap}
@media(max-width:420px){.sk-line{grid-template-columns:5.6rem minmax(0,1fr) 2.6rem;gap:.4rem}.sk-who{font-size:.76rem}}

.tnc-who{margin:1.2rem 0}
.tnc-who>summary{cursor:pointer;font-weight:600;color:var(--text);padding:.6rem .9rem;background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;font-size:.95rem}
.tnc-who[open]>summary{border-radius:12px 12px 0 0}
.tnc-who-body{border:1px solid var(--card-border);border-top:0;border-radius:0 0 12px 12px;padding:.9rem 1rem .2rem}
.best-val{color:var(--green);font-weight:700}
</style>"""


# ── Pomožne funkcije za izris ────────────────────────────────────────────────
def _dot(key):
    return f'<i class="tnc-dot" style="--c:var(--s-{key})"></i>'


def _common_days(verification, keys):
    """Dnevi, ko so napovedovali VSI viri (sicer bi se primerjale različne množice dni) – isto pravilo kot answer_block."""
    dates = sorted(verification)

    def common(window):
        return [d for d in window
                if all(verification[d].get(k) and verification[d][k].get("err_tmax") is not None
                       and verification[d][k].get("err_tmin") is not None for k in keys)]
    days_all, days_30 = common(dates), common(dates[-30:])
    if len(days_30) >= 15:
        return days_30, "zadnjih 30 dni"
    return days_all, "vseh razrešenih dneh"


def _signed(sgn):
    """–1,8 / +1,0 / 0,0 (pomišljaj za minus, kot predpisuje slogovni vodnik)."""
    if abs(sgn) < 0.05:
        return "0,0"
    return ("–" if sgn < 0 else "+") + seo.num(abs(sgn))


def legend_html(series):
    return ('<div class="tnc-legend" aria-label="Legenda virov">' +
            "".join(f'<span>{_dot(s["key"])}{s["label"]}</span>' for s in series) + '</div>')


def leaderboard_html(verification, series):
    """Lestvica: vodoravni stolpci povprečne absolutne napake, urejeni od najboljšega; ena plošča za Tmax, ena za Tmin."""
    keys = [s["key"] for s in series]
    days, label = _common_days(verification, keys)
    if len(days) < 10 or len(series) < 2:
        return ""
    panels = []
    for field, title in (("err_tmax", "Najvišja temperatura"), ("err_tmin", "Najnižja temperatura")):
        mae = {k: st.mean(verification[d][k][field] for d in days) for k in keys}
        order = sorted(series, key=lambda s: mae[s["key"]])
        top = max(mae.values()) or 1
        rows = []
        for i, s in enumerate(order):
            v = mae[s["key"]]
            rows.append(
                f'<li class="lb-row{" is-best" if i == 0 else ""}"><span class="lb-rank">{i + 1}</span>'
                f'<span class="lb-name">{_dot(s["key"])}{s["label"]}</span>'
                f'<span class="lb-bar"><b style="width:{max(v / top * 100, 2):.1f}%;--c:var(--s-{s["key"]})"></b></span>'
                f'<span class="lb-val">±{seo.num(v)}</span></li>')
        panels.append(f'<div class="tnc-card"><h3 class="tnc-h3">{title}</h3>'
                      f'<p class="tnc-sub">povprečna napaka (°C), manj je bolje</p>'
                      f'<ol class="lb">{"".join(rows)}</ol></div>')
    return ('<div class="tnc-grid2">' + "".join(panels) + '</div>\n'
            f'  <p class="tnc-cap">Primerjani so samo dnevi, ko so napovedovali vsi viri ({len(days)} dni v {label}). '
            'Napaka = absolutna razlika napovedi za jutri od meritve IREICA1. Pri majhnem vzorcu se vrstni red hitro zamenja.</p>')


def latest_day_block(verification, series):
    """Včerajšnji dan na temperaturni osi: bela črta je meritev, pika napoved vsakega vira, daljica med njima napaka."""
    if not verification:
        return ""
    d = max(verification)
    rec = verification[d]
    actual = rec.get("actual") or {}
    a = actual.get("tmax")
    if a is None:
        return ""
    got = [(s, rec[s["key"]]["tmax"]) for s in series
           if rec.get(s["key"]) and rec[s["key"]].get("tmax") is not None]
    if not got:
        return ""
    vals = [a] + [v for _, v in got]
    span = max(vals) - min(vals)
    step = 1 if span <= 8 else 2 if span <= 16 else 5
    lo = math.floor((min(vals) - 0.8) / step) * step
    hi = math.ceil((max(vals) + 0.8) / step) * step
    rng = (hi - lo) or 1

    def pos(v):
        return (v - lo) / rng * 100
    ticks = list(range(int(lo), int(hi) + 1, int(step)))
    grid = "".join(f'<u style="left:{pos(t):.2f}%"></u>' for t in ticks)
    axis = ('<div class="dp-row dp-axis" aria-hidden="true"><span></span><span class="dp-track">' +
            "".join(f'<span style="left:{pos(t):.2f}%">{t}</span>' for t in ticks) + '</span><span></span></div>')
    rows = []
    for s, v in got:
        diff = v - a
        left, width = sorted([pos(a), pos(v)])[0], abs(pos(v) - pos(a))
        word = ("zadela v desetinko" if abs(diff) < 0.05 else
                f'{"podcenila" if diff < 0 else "precenila"} za {seo.num(abs(diff))} °C')
        rows.append(
            f'<div class="dp-row" role="img" aria-label="{s["label"]}: napoved {seo.num(v)} °C, {word}">'
            f'<span class="dp-name">{_dot(s["key"])}{s["short"]}</span>'
            f'<span class="dp-track">{grid}<i class="dp-act" style="left:{pos(a):.2f}%"></i>'
            f'<i class="dp-gap" style="left:{left:.2f}%;width:{width:.2f}%;--c:var(--s-{s["key"]})"></i>'
            f'<b class="dp-dot" style="left:{pos(v):.2f}%;--c:var(--s-{s["key"]})"></b></span>'
            f'<span class="dp-val">{seo.num(v)} °C<em>{_signed(diff)}</em></span></div>')
    best = min(got, key=lambda x: abs(x[1] - a))
    worst = max(got, key=lambda x: abs(x[1] - a))
    verdict = (f'Najbližje meritvi je bil {best[0]["label"]} (napaka {seo.num(abs(best[1] - a))} °C), '
               f'najdlje {worst[0]["label"]} ({seo.num(abs(worst[1] - a))} °C).') if len(got) >= 2 else ""
    # padavine: samo viri, ki jih napovedujejo (ARSO zapisi jih nimajo – prazna vrednost bi brala kot 0 mm)
    pr = [(s, rec[s["key"]]["precip"]) for s in series
          if rec.get(s["key"]) and rec[s["key"]].get("precip") is not None]
    precip = ""
    if pr and actual.get("precip") is not None:
        precip = (f' Padavine: izmerjeno {seo.num(actual["precip"])} mm; napovedali so ' +
                  ", ".join(f'{s["short"]} {seo.num(v)} mm' for s, v in pr) + '.')
    return (f'  <h2 id="vceraj">Kako točna je bila napoved za {seo.fmtd(d)}?</h2>\n'
            f'  <p class="archive-intro">Postaja IREICA1 je tega dne izmerila najvišjo temperaturo '
            f'<strong>{seo.num(a)} °C</strong>. Dan prej so viri napovedali:</p>\n'
            f'  <div class="tnc-card">\n'
            f'    <div class="dp-key"><span><i class="k-act"></i>meritev {seo.num(a)} °C</span>'
            f'<span><i class="k-dot"></i>napoved vira</span><span>desno: napoved in napaka (napoved − meritev, °C)</span></div>\n'
            f'    {axis}\n    ' + "\n    ".join(rows) + '\n  </div>\n'
            f'  <p class="tnc-cap">{verdict}{precip}</p>')


def bias_html(verification, series):
    """Stalna pristranskost: povprečna predznačena napaka (napoved − meritev). Ločuje odmik od naključno zgrešenih dni."""
    keys = [s["key"] for s in series]
    days, label = _common_days(verification, keys)
    if len(days) < 10:
        return ""
    panels, notes = [], []
    for field, title, adj in (("tmax", "Najvišja temperatura", "najvišji"), ("tmin", "Najnižja temperatura", "najnižji")):
        b = {}
        for s in series:
            diffs = [verification[d][s["key"]][field] - verification[d]["actual"][field] for d in days
                     if verification[d][s["key"]].get(field) is not None and verification[d].get("actual", {}).get(field) is not None]
            if len(diffs) >= 10:
                b[s["key"]] = st.mean(diffs)
        if not b:
            continue
        bound = max(1.0, math.ceil(max(abs(v) for v in b.values()) * 2) / 2)
        rows = []
        for s in series:
            if s["key"] not in b:
                continue
            v = b[s["key"]]
            w = abs(v) / bound * 50
            cls = "neg" if v < 0 else "pos"
            rows.append(
                f'<div class="bs-row" role="img" aria-label="{s["label"]}: {_signed(v)} °C">'
                f'<span class="bs-name">{_dot(s["key"])}{s["short"]}</span>'
                f'<span class="bs-track"><b class="{cls}" style="width:{w:.1f}%;--c:var(--s-{s["key"]})"></b></span>'
                f'<span class="bs-val">{_signed(v)}</span></div>')
        panels.append(
            f'<div class="tnc-card"><h3 class="tnc-h3">{title}</h3>'
            f'<p class="tnc-sub">povprečna napaka s predznakom (°C)</p>'
            f'<div class="bs-axis" aria-hidden="true"><span></span><span><span>← pod meritvijo</span><span>nad →</span></span><span></span></div>'
            + "".join(rows) + '</div>')
        below = sum(1 for v in b.values() if v < -0.05)
        above = sum(1 for v in b.values() if v > 0.05)
        notes.append(f'pri {adj} temperaturi je {below} od {len(b)} virov v povprečju pod meritvijo, {above} nad njo')
    if not panels:
        return ""
    return ('  <h2 id="pristranskost">Se viri zmotijo v isto smer?</h2>\n'
            '  <p class="archive-intro">Napaka ni vedno naključna. Če je vir dan za dnem na isti strani meritve, '
            'je to stalen odmik: dolina je drugačna od modelske mreže, ali pa postaja od kraja, za katerega vir napoveduje. '
            'Spodaj je povprečna napaka s predznakom na istih dneh kot lestvica.</p>\n'
            '  <div class="tnc-grid2">' + "".join(panels) + '</div>\n'
            f'  <p class="tnc-cap">V povprečju {"; ".join(notes)}. Odmik ni nujno napaka vira: pri vseh modelih je najvišja temperatura pod, '
            'najnižja pa nad meritvijo, kar kaže, da dnevnega razpona dna doline ne ujamejo (glej Test napovedi).</p>')


def trend_html(verification, series, win=7, min_n=4):
    """Drseče 7-dnevno povprečje napake Tmax po virih – črte so čitljive, ker je dnevni šum izglajen (dnevne vrednosti so v tabeli)."""
    dates = sorted(verification)
    if len(dates) < 12:
        return ""
    d0 = datetime.date.fromisoformat(dates[0])
    xs = [(datetime.date.fromisoformat(d) - d0).days for d in dates]
    span = max(xs) or 1
    lines = {}
    for s in series:
        pts = []
        for i, d in enumerate(dates):
            vals = [verification[dd][s["key"]]["err_tmax"] for dd in dates[max(0, i - win + 1):i + 1]
                    if verification[dd].get(s["key"]) and verification[dd][s["key"]].get("err_tmax") is not None]
            if len(vals) >= min_n:
                pts.append((xs[i], st.mean(vals)))
        if len(pts) >= 2:
            lines[s["key"]] = pts
    if not lines:
        return ""
    W, H, pl, pr, pt, pb = 420, 260, 26, 96, 12, 26
    pw, ph = W - pl - pr, H - pt - pb
    ymax = max(v for p in lines.values() for _, v in p)
    ystep = 1 if ymax <= 5 else 2
    ytop = math.ceil(ymax / ystep) * ystep

    def X(x):
        return pl + pw * x / span

    def Y(v):
        return pt + ph * (1 - v / ytop)
    g = []
    for t in range(0, int(ytop) + 1, int(ystep)):
        g.append(f'<line x1="{pl}" y1="{Y(t):.1f}" x2="{W - pr}" y2="{Y(t):.1f}" stroke="rgba(255,255,255,.08)"/>')
        g.append(f'<text class="sv-t" x="{pl - 5}" y="{Y(t) + 3.5:.1f}" text-anchor="end">{t}</text>')
    seen = set()
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym in seen:
            continue
        seen.add(ym)
        x = X(xs[i])
        if x > W - pr - 18:
            continue
        anchor = "start" if i == 0 else "middle"
        g.append(f'<line x1="{x:.1f}" y1="{pt + ph}" x2="{x:.1f}" y2="{pt + ph + 4}" stroke="rgba(255,255,255,.25)"/>')
        g.append(f'<text class="sv-t" x="{x:.1f}" y="{H - 8}" text-anchor="{anchor}">{MES_KRATKO[int(d[5:7])]}</text>')
    ends = []
    order = [s for s in series if s["key"] in lines and s["key"] != "meteorec"] + [s for s in series if s["key"] == "meteorec" and s["key"] in lines]
    for s in order:  # MTR zadnji, da je na vrhu
        pts = lines[s["key"]]
        path = " ".join(f'{X(x):.1f},{Y(v):.1f}' for x, v in pts)
        g.append(f'<polyline points="{path}" fill="none" stroke="var(--s-{s["key"]})" stroke-width="2" '
                 f'stroke-linecap="round" stroke-linejoin="round"><title>{s["label"]}</title></polyline>')
        ex, ev = pts[-1]
        g.append(f'<circle cx="{X(ex):.1f}" cy="{Y(ev):.1f}" r="3.5" fill="var(--s-{s["key"]})" stroke="var(--tnc-surface)" stroke-width="2"/>')
        ends.append([Y(ev), s, ev])
    ends.sort(key=lambda e: e[0])
    for i in range(1, len(ends)):  # razmik oznak, da se ne prekrivajo
        if ends[i][0] - ends[i - 1][0] < 12:
            ends[i][0] = ends[i - 1][0] + 12
    for y, s, ev in ends:
        g.append(f'<text class="sv-l" x="{W - pr + 8}" y="{y + 3.5:.1f}">{s["short"]} {seo.num(ev)}</text>')
    last = ", ".join(f'{s["label"]} ±{seo.num(lines[s["key"]][-1][1])} °C' for s in series if s["key"] in lines)
    aria = (f'Drseče sedemdnevno povprečje napake napovedi najvišje temperature po virih, od {seo.fmtd(dates[0])} do '
            f'{seo.fmtd(dates[-1])}. Zadnja vrednost: {last}.')
    svg = (f'<svg viewBox="0 0 {W} {H}" class="tnc-svg" role="img" aria-label="{aria}" preserveAspectRatio="xMidYMid meet">'
           + "".join(g) + '</svg>')
    return ('  <h2 id="gibanje">Kako se napaka giblje skozi čas?</h2>\n'
            '  <p class="archive-intro">Drseče sedemdnevno povprečje napake najvišje temperature: ko črta pada, '
            'je vir zadnji teden zadel bolje kot prej. Posamezne dneve vidite v tabeli »Zadnji dnevi«.</p>\n'
            f'  <figure class="tnc-card" style="margin-left:0;margin-right:0">{svg}'
            f'{legend_html(series)}</figure>')


def _heat(v, scale):
    return f' style="--h:{min(max(v / scale, 0), 1):.2f}"'


def _heat_head(series, lead, tail=""):
    return ("<thead><tr>" + lead + "".join(f'<th scope="col">{_dot(s["key"])}{s["short"]}</th>' for s in series) + tail + "</tr></thead>")


HEAT_KEY = ('<div class="tnc-heat-key"><span>svetlejše ozadje = večja napaka<i class="hk-ramp"></i></span>'
            '<span><i class="hk-best"></i>najmanjša napaka v vrstici</span></div>')


def month_table_html(verification, series):
    dates = sorted(verification)
    if not dates:
        return ""
    by_month = defaultdict(list)
    for d in dates:
        by_month[d[:7]].append(verification[d])

    def row(label, recs, cls=""):
        stats = {s["key"]: source_stats(recs, s["key"]) for s in series}
        best = best_keys({k: v["mae_tmax"] for k, v in stats.items()})
        cells = []
        for s in series:
            v = stats[s["key"]]["mae_tmax"]
            if v is None:
                cells.append('<td class="na">—</td>')
            else:
                cells.append(f'<td class="hv{" best" if s["key"] in best else ""}"{_heat(v, 5.0)}>{seo.num(v)}</td>')
        return (f'<tr{cls}><th scope="row">{label}</th>' + "".join(cells) +
                f'<td class="meas">{len(recs)}</td></tr>')

    body = [row("Skupaj", [verification[d] for d in dates], ' class="tot"')]
    for ym in sorted(by_month, reverse=True):
        body.append(row(f'{MES_KRATKO[int(ym[5:7])]} {ym[:4]}', by_month[ym]))
    return ('  <h2>Mesečni pregled</h2>\n'
            '  <div class="tnc-card"><table class="tnc-heat">\n'
            '    <caption>Povprečna napaka najvišje temperature (°C) po mesecih. Vir je lahko v mesecu napovedoval le del dni, '
            'zato vrstica »Skupaj« ni povsem primerljiva med viri.</caption>\n'
            '    <colgroup><col style="width:4.4rem">' + '<col>' * len(series) + '<col style="width:2.2rem"></colgroup>\n    '
            + _heat_head(series, '<th scope="col"></th>', '<th scope="col">Dni</th>') + '\n    <tbody>\n      '
            + "\n      ".join(body) + '\n    </tbody>\n  </table>' + HEAT_KEY + '</div>')


def days_table_html(verification, series, n=20):
    dates = list(reversed(sorted(verification)))[:n]
    if not dates:
        return '  <p class="muted-note">Še ni razrešenih dni.</p>'
    rows = []
    for d in dates:
        r = verification[d]
        act = (r.get("actual") or {}).get("tmax")
        best = best_keys({s["key"]: (r.get(s["key"]) or {}).get("err_tmax") for s in series})
        cells = []
        for s in series:
            src = r.get(s["key"]) or {}
            e, p = src.get("err_tmax"), src.get("tmax")
            if e is None or p is None:
                cells.append('<td class="na">—</td>')
            else:
                cells.append(f'<td class="hv{" best" if s["key"] in best else ""}"{_heat(e, 6.0)} '
                             f'title="{s["label"]}: napoved {seo.num(p)} °C, meritev {seo.num(act)} °C">'
                             f'{seo.num(e)}<small>{seo.num(p)}</small></td>')
        rows.append(f'<tr><th scope="row"><a href="/vreme/{d[:4]}/{d[5:7]}/{d[8:10]}/">{int(d[8:10])}. {int(d[5:7])}.</a></th>'
                    f'<td class="meas">{seo.num(act)}</td>' + "".join(cells) + '</tr>')
    return ('  <h2>Zadnji dnevi</h2>\n'
            f'  <div class="tnc-card"><table class="tnc-heat">\n'
            '    <caption>Najvišja temperatura po dnevih. Velika številka je napaka napovedi, mala pod njo napovedana '
            'temperatura (°C); prvi stolpec je meritev IREICA1.</caption>\n'
            '    <colgroup><col style="width:3.2rem"><col style="width:3rem">' + '<col>' * len(series) + '</colgroup>\n    '
            + _heat_head(series, '<th scope="col">Datum</th><th scope="col">Izmer&shy;jeno</th>') + '\n    <tbody>\n      '
            + "\n      ".join(rows) + '\n    </tbody>\n  </table>' + HEAT_KEY + '</div>')


def skill_html(leads, mtr_label, om_label="Open-Meteo"):
    """MTR proti Open-Meteo po vodilnem času (hindcast ob učenju): parni stolpci, izboljšava ob skupini."""
    nums = sorted(leads, key=int)
    allv = [v for ln in nums for fld in ("tmax", "tmin")
            for v in (((leads[ln].get("skill") or {}).get(fld) or {}).get("mae_open_meteo"),
                      ((leads[ln].get("skill") or {}).get(fld) or {}).get("mae_meteorec")) if v is not None]
    if not allv:
        return ""
    top = max(allv)
    panels = []
    for fld, title in (("tmax", "Najvišja temperatura"), ("tmin", "Najnižja temperatura")):
        grps = []
        for ln in nums:
            sk = ((leads[ln] or {}).get("skill") or {}).get(fld) or {}
            om, mt, imp = sk.get("mae_open_meteo"), sk.get("mae_meteorec"), sk.get("improvement_pct")
            if om is None or mt is None:
                continue
            lines = "".join(
                f'<div class="sk-line"><span class="sk-who">{_dot(k)}{nm}</span>'
                f'<span class="lb-bar"><b style="width:{max(v / top * 100, 2):.1f}%;--c:var(--s-{k})"></b></span>'
                f'<span class="lb-val">±{seo.num(v)}</span></div>'
                for k, nm, v in (("open_meteo", om_label, om), ("meteorec", mtr_label, mt)))
            grps.append(f'<div class="sk-grp"><div class="sk-head"><span class="sk-lead">D+{ln}</span>'
                        f'<span class="sk-imp">{seo.num(imp) + " % manj napake" if imp is not None else ""}</span></div>{lines}</div>')
        if grps:
            panels.append(f'<div class="tnc-card"><h3 class="tnc-h3">{title}</h3>'
                          f'<p class="tnc-sub">povprečna napaka (°C), hindcast ob učenju</p>{"".join(grps)}</div>')
    return '<div class="tnc-grid2">' + "".join(panels) + '</div>' if panels else ""


def load_verification():
    try:
        with open(VERIFICATION_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_model():
    try:
        with open(MODEL_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def source_stats(records, source):
    tmax_errs = [r[source]["err_tmax"] for r in records if r.get(source) and r[source].get("err_tmax") is not None]
    tmin_errs = [r[source]["err_tmin"] for r in records if r.get(source) and r[source].get("err_tmin") is not None]
    n = sum(1 for r in records if r.get(source))
    return {
        "n": n,
        "mae_tmax": st.mean(tmax_errs) if tmax_errs else None,
        "mae_tmin": st.mean(tmin_errs) if tmin_errs else None,
    }


def pred_txt(src, is_best=False):
    """»28,4 °C (±1,1)« za posamezno napoved v tabeli zadnjih dni."""
    if not src or src.get("tmax") is None:
        return "—"
    txt = f'{seo.num(src.get("tmax"))} °C (±{seo.num(src.get("err_tmax"))})'
    return f'<span class="best-val">{txt}</span>' if is_best else txt


def mae_txt(stats, is_best=False):
    """»±1,2 °C« ali pomišljaj, kadar vir tisti mesec ni napovedoval."""
    if stats["mae_tmax"] is None:
        return "—"
    txt = f'±{seo.num(stats["mae_tmax"])} °C'
    return f'<span class="best-val">{txt}</span>' if is_best else txt


def best_keys(vals):
    """Ključi z najmanjšo (najboljšo) vrednostjo, za poudarek v tabeli — samo,
    če sta na voljo vsaj dva vira tisti dan/mesec, sicer bi bil poudarek en
    sam stolpec brez primerjave."""
    present = {k: v for k, v in vals.items() if v is not None}
    if len(present) < 2:
        return set()
    m = min(present.values())
    return {k for k, v in present.items() if abs(v - m) < 1e-9}


def answer_block(verification, labels):
    """»Na kratko«: odgovor na vprašanje, ki ga zastavljajo iskalniki in AI povzetki (kateri vir je za Rečico
    najbolj natančen), v prvih dveh stavkih in s številko. Primerja samo dneve, ko so napovedovali VSI vključeni
    viri (sicer bi ARSO in AIFS merila različne dni). Razliko med prvim in drugim označi za zanesljivo le, če
    interval ±1,96 SE parjenih dnevnih napak ne vključuje ničle."""
    dates = sorted(verification)
    keys = [k for k, _ in labels]
    name = dict(labels)

    def common(window):
        out = []
        for d in window:
            rec = verification[d]
            if all(rec.get(k) and rec[k].get("err_tmax") is not None and rec[k].get("err_tmin") is not None for k in keys):
                out.append(d)
        return out

    def rank(days, field):
        vals = {k: [verification[d][k][field] for d in days] for k in keys}
        mae = {k: st.mean(v) for k, v in vals.items()}
        order = sorted(keys, key=lambda k: mae[k])
        reliable = False
        if len(days) >= 10 and len(order) >= 2:
            diff = [b - a for a, b in zip(vals[order[0]], vals[order[1]])]
            se = st.stdev(diff) / (len(diff) ** 0.5) if len(diff) > 1 else 0
            reliable = st.mean(diff) - 1.96 * se > 0
        return order, mae, reliable

    days_all = common(dates)
    if len(days_all) < 10 or len(keys) < 2:
        return ""
    days_30 = common(dates[-30:])
    use, label = (days_30, "zadnjih 30 dneh") if len(days_30) >= 15 else (days_all, "razrešenih dneh od " + seo.fmtd(days_all[0]))
    parts = []
    for field, what in (("err_tmax", "najvišji"), ("err_tmin", "najnižji")):
        order, mae, reliable = rank(use, field)
        rest = ", ".join(f'{name[k]} ±{seo.num(mae[k])} °C' for k in order[1:])
        verdict = "" if reliable else " (razlika do drugega ni statistično zanesljiva)"
        parts.append(f'pri {what} temperaturi {name[order[0]]} (±{seo.num(mae[order[0]])} °C){verdict}; za njim {rest}')
    # Napaka, ki je skoraj vsa stalna pristranskost (npr. ARSO za Ljubno proti postaji v Rečici), ni naključno
    # zgrešen dan: to povemo, sicer bi bralec lestvico bral kot kakovost napovedovalca.
    biased = []
    for k in keys:
        signed = [verification[d][k]["tmax"] - verification[d]["actual"]["tmax"] for d in use
                  if verification[d][k].get("tmax") is not None and verification[d].get("actual", {}).get("tmax") is not None]
        if len(signed) >= 10:
            b, m = st.mean(signed), st.mean(abs(x) for x in signed)
            if m >= 2 and abs(b) >= 0.8 * m:
                biased.append((name[k], b, st.mean(abs(x - b) for x in signed)))
    bias_txt = ''
    if biased:
        bias_txt = (' Pri nekaterih virih je večina napake stalna pristranskost pri najvišji temperaturi, ne naključno zgrešeni dnevi: '
                    + "; ".join(f'{n} je povprečno {seo.num(abs(b))} °C {"pod" if b < 0 else "nad"} meritvijo (brez tega odmika bi bila napaka ±{seo.num(r)} °C)'
                                for n, b, r in biased)
                    + '. Odmik ni nujno napaka vira: pri vseh modelih je najvišja temperatura pod, najnižja pa nad meritvijo, kar kaže, da dnevnega razpona dna doline ne ujamejo (glej Test napovedi).')
    return (f'  <div class="tnc-answer">\n'
            f'  <p><strong>Na kratko:</strong> v {label}, v katerih so napovedovali vsi viri ({len(use)} dni), '
            f'je bil za Rečico ob Savinji najbolj natančen ' + "; ".join(parts) + '.</p>\n'
            f'  <details class="tnc-note"><summary>Pogoji meritve in opomba o pristranskosti</summary>\n'
            f'  <p class="muted-note">Povprečna absolutna napaka napovedi za jutri proti meritvi IREICA1. '
            f'Pri majhnem vzorcu se vrstni red hitro zamenja; iz enega meseca ne sklepajte.{bias_txt}</p></details>\n'
            f'  <p class="muted-note">Posodobljeno: {seo.fmtd(TODAY.isoformat())}.</p>\n  </div>')


def build_body(verification):
    dates = sorted(verification.keys())
    records = [verification[d] for d in dates]
    n_days = len(records)
    first_date = dates[0] if dates else None

    arso_stats = source_stats(records, "arso")
    om_stats = source_stats(records, "open_meteo")
    mos_stats = source_stats(records, "meteorec")
    aifs_stats = source_stats(records, "aifs")
    wn2_stats = source_stats(records, "wn2")
    has_mos = mos_stats["n"] > 0
    has_aifs = aifs_stats["n"] > 0
    has_wn2 = wn2_stats["n"] > 0

    # MTR — ime lastnega modela. Različica se izpelje iz zadnjega zapisa, ki jo
    # nosi (meteorec.model_version), da se oznaka sama dvigne, ko se model kdaj
    # znova nauči pod novo verzijo — nikjer je ne zapisujemo trdo.
    mtr_ver = next((r["meteorec"].get("model_version") for r in reversed(records)
                    if r.get("meteorec") and r["meteorec"].get("model_version")), None)
    mtr_label = f"MTR v{mtr_ver.split('.')[0]}" if mtr_ver else "MTR"

    # ARSO nima napovedne točke za Rečico, zato njegova napoved prihaja iz
    # najbližjega kraja na njihovem seznamu. Kateri je to, povemo naravnost —
    # sicer bi številka izpadla kot napoved za Rečico, kar ni.
    arso_loc = next((r["arso"].get("loc") for r in reversed(records)
                     if r.get("arso") and r["arso"].get("loc")), None)
    arso_note = ""
    if arso_loc and arso_loc != "Rečica ob Savinji":
        arso_note = (f' ARSO za Rečico ob Savinji ne objavlja krajevne napovedi, zato jemljemo '
                     f'najbližji kraj z njihovega seznama — {arso_loc}. Open-Meteo je vezan '
                     f'neposredno na koordinate postaje.')

    if n_days == 0:
        status = ('  <div class="warn-banner lvl-none">Zbiranje podatkov se je začelo danes, '
                   f'{TODAY.isoformat()}. Napovedi ARSO in Open-Meteo za jutri se dnevno beležijo, '
                   'primerjava z dejansko meritvijo pa se izpiše, ko dan mine — prvi rezultati bodo '
                   'na voljo v naslednjih dneh.</div>')
    else:
        parts = []
        if om_stats["mae_tmax"] is not None:
            parts.append(f'Open-Meteo: povprečna napaka najvišje temperature ±{seo.num(om_stats["mae_tmax"])} °C')
        if arso_stats["mae_tmax"] is not None:
            parts.append(f'ARSO: ±{seo.num(arso_stats["mae_tmax"])} °C')
        if aifs_stats["mae_tmax"] is not None:
            parts.append(f'ECMWF AIFS: ±{seo.num(aifs_stats["mae_tmax"])} °C')
        if wn2_stats["mae_tmax"] is not None:
            parts.append(f'WeatherNext 2: ±{seo.num(wn2_stats["mae_tmax"])} °C '
                         f'({wn2_stats["n"]} dni)')
        if mos_stats["mae_tmax"] is not None:
            parts.append(f'{mtr_label}: ±{seo.num(mos_stats["mae_tmax"])} °C')
        status =(f'  <p class="archive-intro"><strong>{n_days} razrešenih dni</strong> od {seo.fmtd(first_date)}. '
                   f'{"; ".join(parts)}.</p>')

    mos_intro = (f'  <p class="archive-intro"><strong>Tretji tekmovalec je {mtr_label} (Meteorec)</strong> — '
                 'naš lastni model za to dolino. Ne napoveduje vremena iz nič — vzame Open-Meteo kot vhod in '
                 'ga popravi s tem, česar globalni model za dno te doline ne zna: postaja je podnevi toplejša, '
                 'ponoči pa hladnejša od modelske mreže, ob jasnih in mirnih nočeh se na dnu doline nabere '
                 'hladen zrak. Popravek je naučen na meritvah te postaje. Meri se z istim merilom kot ARSO in '
                 'Open-Meteo, na isti tabeli — tudi kadar izgubi.</p>') if has_mos else ""

    # AIFS: koliko dni je napolnjenih iz arhiva in ne zabeleženih sproti. To ni
    # kozmetika — arhivski zapis je nastal po drugi poti (urne vrednosti,
    # sešteto v dnevne) in bralec mora vedeti, kje meja teče.
    aifs_archive_n = sum(1 for r in records if (r.get("aifs") or {}).get("src") == "archive")
    aifs_note = (f' Prvih {aifs_archive_n} dni je napolnjenih iz arhiva preteklih napovedi '
                 'Open-Meteo (AIFS je edini vir tu, ki tak arhiv sploh ima), naprej se beleži '
                 'sproti kot vsi ostali.') if aifs_archive_n else ""
    aifs_model_id = next((r["aifs"].get("model") for r in reversed(records)
                          if r.get("aifs") and r["aifs"].get("model")), "ecmwf_aifs025_single")
    aifs_method = (f' ECMWF AIFS jemljemo prek Open-Meteo (model {aifs_model_id}); dnevi, napolnjeni iz '
                   'arhiva preteklih napovedi, so sešteti iz urnih vrednosti, sproti zabeleženi pa iz '
                   'dnevne agregacije Open-Meteo — razlika je nekaj desetink stopinje.') if has_aifs else ""
    aifs_intro = ('  <p class="archive-intro"><strong>Četrti tekmovalec je ECMWF AIFS</strong> — AI model '
                  'Evropskega centra za srednjeročne napovedi, ki od februarja 2025 teče operativno in ga '
                  'Windy prikazuje kot 15-dnevni podaljšek modela ECMWF. Vremena ne računa iz enačb, ampak '
                  'ga je napovedovanja naučila nevronska mreža na štiridesetih letih arhiva. Teče v '
                  'ločljivosti 0,25° (~28 km) in v šesturnih korakih, kar pomeni, da naše doline ne vidi — '
                  'na tej tabeli je zato predvsem odgovor na vprašanje, ali AI po sebi odtehta lokalno '
                  f'ločljivost.{aifs_note}</p>') if has_aifs else ""

    # WeatherNext 2: isti vzorec kot AIFS, a s krajšim arhivom in svojim
    # opozorilom — šesturni koraki pomenijo, da dnevni vrh in minimum skoraj
    # nikoli ne padeta na uro, ki jo model sploh izračuna.
    wn2_first = next((d for d, r in zip(dates, records) if r.get("wn2")), None)
    wn2_archive_n = sum(1 for r in records if (r.get("wn2") or {}).get("src") == "archive")
    wn2_note = (f' Prvih {wn2_archive_n} dni je napolnjenih iz arhiva preteklih napovedi '
                'Open-Meteo, naprej se beleži sproti.') if wn2_archive_n else ""
    wn2_intro = ('  <p class="archive-intro"><strong>Peti tekmovalec je Google DeepMind WeatherNext 2</strong> — '
                 'Googlov AI model, povprečje 64 članov ansambla, ki ga Google uporablja tudi v svojih '
                 'vremenskih napovedih. Kot AIFS teče v ločljivosti 0,25° (~28 km) in šesturnih korakih: '
                 'dnevno najvišjo in najnižjo temperaturo vzamemo iz štirih vrednosti na dan, zato '
                 'popoldanski vrh in jutranji minimum praviloma zgreši, kar se pozna v napaki. '
                 f'Na semaforju je od {seo.fmtd(wn2_first) if wn2_first else "—"}, ker Open-Meteo njegov '
                 f'arhiv preteklih napovedi hrani šele od takrat.{wn2_note}</p>') if has_wn2 else ""
    wn2_method = (' Google DeepMind WeatherNext 2 jemljemo prek ensemble API-ja Open-Meteo (model '
                  'google_weathernext2_ensemble_mean, povprečje članov izračuna Open-Meteo). '
                  'Vir: Google DeepMind WeatherNext 2, CC BY 4.0.') if has_wn2 else ""

    intro = ('  <p class="archive-intro">Vsak dan zabeležimo, kaj ARSO in Open-Meteo napovesta za jutrišnjo '
             'najvišjo/najnižjo temperaturo v Rečici ob Savinji, naslednji dan pa to primerjamo z dejansko '
             'meritvijo postaje IREICA1. Nobene napovedi ne popravimo ali izbrišemo za nazaj; '
             'popravi se lahko le meritev, s katero jo primerjamo, in sicer takrat, ko arhiv postaje '
             'naknadno dopolni nepopoln dan. To je surova, tekoča ocena napovedne uspešnosti za to '
             'konkretno dolino, ne za Slovenijo na splošno.</p>')

    series = [dict(key=k, label=(mtr_label if k == 'meteorec' else n), short=(mtr_label if k == 'meteorec' else sh))
              for k, n, sh in SRC_DEFS
              if source_stats(records, k)['n'] > 0]

    intro_block = (intro + ("\n" + mos_intro if mos_intro else "")
                   + ("\n" + aifs_intro if aifs_intro else "") + ("\n" + wn2_intro if wn2_intro else ""))

    # ── MTR: veščina po vodilnem času (D+1..D+3), hindcast ob učenju ─────
    # Ločeno od scoreboarda zgoraj: kartice/mesečni pregled merijo samo D+1,
    # sproti, na dneh, ki so se dejansko zgodili po objavi. Ta razdelek bere
    # model/recica-mos.json (piše ga train_recica_mos.py) -- leave-one-year-out
    # ocena vseh treh vodilnih časov, izračunana ob zadnjem učenju.
    skill_section = ""
    if has_mos:
        model = load_model()
        leads = model.get("leads") or {}
        if leads:
            lead_nums = sorted(leads, key=int)
            year_blocks = []
            for ln in lead_nums:
                entry = leads[ln] or {}
                tmax_sk = (entry.get("skill") or {}).get("tmax") or {}
                tmin_sk = (entry.get("skill") or {}).get("tmin") or {}
                tmax_py = tmax_sk.get("per_year") or {}
                tmin_py = tmin_sk.get("per_year") or {}
                years = sorted(set(tmax_py) | set(tmin_py))
                if years:
                    py_rows = []
                    for y in years:
                        ty, ny = tmax_py.get(y) or {}, tmin_py.get(y) or {}
                        py_rows.append(
                            f'      <tr><th>{y}</th>'
                            f'<td>±{seo.num(ty.get("open_meteo"))} °C</td>'
                            f'<td>±{seo.num(ty.get("meteorec"))} °C</td>'
                            f'<td>±{seo.num(ny.get("open_meteo"))} °C</td>'
                            f'<td>±{seo.num(ny.get("meteorec"))} °C</td>'
                            f'<td>{ty.get("n", "—")}</td></tr>'
                        )
                    year_blocks.append(
                        f'    <details><summary>D+{ln} po letih</summary>\n'
                        '      <div class="table-scroll" tabindex="0"><table class="stats">\n'
                        f'      <tr><th>Leto</th><th colspan="2">Tmax (Open-Meteo / {mtr_label})</th>'
                        f'<th colspan="2">Tmin (Open-Meteo / {mtr_label})</th><th>Vzorcev</th></tr>\n'
                        + "\n".join(py_rows) + '\n      </table></div>\n    </details>'
                    )

            trained_iso = (model.get("trained_at") or "")[:10]
            trained_txt = seo.fmtd(trained_iso) if len(trained_iso) == 10 else "—"
            n_samples = max((((leads[ln] or {}).get("skill") or {}).get("tmax") or {}).get("n", 0) for ln in lead_nums)
            skill_section = (
                f'  <h2>{mtr_label}: veščina glede na vodilni čas</h2>\n'
                '  <p class="archive-intro">To ni ista številka kot zgoraj: lestvica meri samo napoved za jutri (D+1), sproti, '
                f'na dnevih, ki so se dejansko zgodili po objavi. Spodnji stolpci so hindcast ob zadnjem učenju modela ({trained_txt}): '
                'izpuščanje celega leta iz učne množice in ocena na izpuščenem, za vse tri vodilne čase (D+1 do D+3).</p>\n'
                + skill_html(leads, mtr_label)
                + f'\n  <p class="tnc-cap">{n_samples} vzorcev na vodilni čas. Zelena številka ob skupini je zmanjšanje povprečne napake proti Open-Meteo.</p>'
                + ('\n  <div class="faq">\n' + "\n".join(year_blocks) + '\n  </div>' if year_blocks else '')
            )

    # ── FAQ ─────────────────────────────────────────────────────────────
    qa = [
        ("Kako točna je vremenska napoved za Zgornjo Savinjsko dolino?",
         "Ta stran dnevno meri, za koliko stopinj se napovedi ARSO in Open-Meteo za naslednji dan povprečno "
         "zmotijo glede na dejansko meritev postaje IREICA1 v Rečici ob Savinji. Trenutna povprečna napaka "
         "je prikazana zgoraj in se dnevno posodablja — nobene napovedi ne popravljamo za nazaj."),
        ("Je ARSO napoved zanesljiva?",
         "Odvisno od obdobja in spremenljivke — glej mesečni pregled spodaj. Ta stran meri samo dan vnaprej "
         "napovedano najvišjo/najnižjo temperaturo za eno konkretno lokacijo (Rečica ob Savinji), ne "
         "splošne zanesljivosti ARSO napovedi za Slovenijo."),
        ("Zakaj se primerjava začne šele nedavno?",
         "ARSO ne objavlja arhiva preteklih napovedi, zato primerjave zanj ni mogoče izračunati za nazaj — "
         "beležimo jo dan za dnem, odkar ta stran obstaja. Izjemi sta AI modela ECMWF AIFS in Google "
         "WeatherNext 2: Open-Meteo zanju hrani arhiv preteklih napovedi, zato sta napolnjena tudi za dneve "
         "pred tem — WeatherNext 2 le od začetka septembra 2026, ker arhiv pri Open-Meteo prej ne sega."),
        ("Kje je primerjava za naslednjih nekaj ur (ne dni)?",
         "Uro-natančno primerjavo lastnega statističnega modela (Holt-Winters), Open-Meteo in postaje za "
         "zadnjih 24 ur najdeš na naslovni strani v razdelku »AI napoved«."),
    ]
    # Vprašanje o lastnem modelu se pojavi šele, ko ima model kaj pokazati —
    # dokler ni razrešenih dni, bi bilo obljuba brez številk.
    if has_aifs:
        qa.insert(2, (
            "Kateri AI model uporablja Windy in ali je boljši?",
            "Windy ne razvija svojega modela — prikazuje ECMWF AIFS, AI model Evropskega centra za "
            "srednjeročne napovedi, kot 15-dnevni podaljšek modela ECMWF. Na tej tabeli teče pod istim "
            "merilom kot vsi ostali. Pri nas ga omejuje ločljivost: AIFS računa na mreži 0,25° (~28 km), "
            "kar je za ozko dolino pregrobo — dno doline vidi kot pobočje. Za sinoptično sliko nekaj dni "
            "vnaprej je to lahko odličen model, za najvišjo temperaturo v Rečici pa številke v tabeli "
            "povedo, kje dejansko je."))
    if has_wn2:
        qa.insert(3 if has_aifs else 2, (
            "Kako točen je Googlov AI vremenski model za našo dolino?",
            "Google DeepMind WeatherNext 2 je na tej tabeli pod istim merilom kot vsi ostali. Pri nas ga "
            "omejujeta ločljivost 0,25° (~28 km) in šesturni koraki — najvišjo in najnižjo temperaturo dneva "
            "vzamemo iz štirih vrednosti na dan, zato popoldanski vrh in jutranji minimum praviloma zgreši. "
            "Novejši WeatherNext 3 (5 km, urni koraki, učen tudi na meritvah postaj) prosto ni dostopen; "
            "ko bo, ga bomo dodali kot ločen vir."))
    if has_mos:
        qa.insert(3 + has_aifs + has_wn2, (
            f"Kaj je {mtr_label}?",
            "MTR (Meteorec) je lastni statistični model za Rečico ob Savinji. Vzame napoved Open-Meteo in ji "
            "doda popravek, naučen na meritvah postaje IREICA1 — kako se dno doline sistematično razlikuje od "
            "modelske mreže. Napoveduje najvišjo in najnižjo temperaturo ter verjetnost padavin za en do tri "
            "dni vnaprej. Količine padavin ne popravlja, ker se je pri preizkusu izkazalo, da tega ne zna "
            "bolje od Open-Meteo. Model je poskusen in se meri javno, na tej tabeli — tudi kadar izgubi."))

    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    latest_block = latest_day_block(verification, series)
    answer_html = answer_block(verification, [(x["key"], x["label"]) for x in series])
    leader_html = leaderboard_html(verification, series)
    leader_block = ('  <h2 id="lestvica">Lestvica: kdo je najbližje meritvi?</h2>\n' + leader_html) if leader_html else ""
    bias_block = bias_html(verification, series)
    trend_block = trend_html(verification, series)
    month_block = month_table_html(verification, series)
    days_block = days_table_html(verification, series)
    who_block = ('  <details class="tnc-who"><summary>Kdo tekmuje in kako merimo</summary>\n  <div class="tnc-who-body">\n'
                 + status + "\n" + intro_block + "\n  </div></details>")

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Točnost napovedi", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Točnost vremenske napovedi — Rečica ob Savinji</h1>
  <p class="post-meta">{" vs. ".join(["ARSO", "Open-Meteo"] + (["ECMWF AIFS"] if has_aifs else []) + (["WeatherNext 2"] if has_wn2 else []) + ([mtr_label] if has_mos else []) + ["dejanska meritev"])} · {n_days} razrešenih dni · {TODAY.isoformat()}</p>
{answer_html}
  {legend_html(series)}
{leader_block}
{latest_block}
{bias_block}
{trend_block}
{skill_section}
{month_block}
{days_block}
{who_block}
  <h2>Misliš, da zmoreš bolje?</h2>
  <p class="archive-intro">V igri <a href="/napovej/"><strong>Prehiti model</strong></a> vsak dan napoveš
  jutrišnjo najvišjo in najnižjo temperaturo za Rečico, naslednje jutro pa te oceni ista meritev in isto
  pravilo kot vse vire na tej strani. Modeli računajo na mreži in dna doline ne vidijo — kdor ve, kdaj
  se v njej nabere hladen zrak, jih lahko premaga.</p>
{faq_html}
  <p class="muted-note">Metodologija: vsak dan zabeležimo napoved ARSO in Open-Meteo za jutrišnjo najvišjo/
  najnižjo temperaturo v Rečici ob Savinji; ko dan mine, ju primerjamo z dejansko dnevno meritvijo postaje
  IREICA1. Napaka je absolutna razlika v °C. Nobena pretekla napoved se ne popravlja ali briše; kadar
  arhiv postaje naknadno dopolni meritev za pretekli dan, napako preračunamo na dopolnjeno meritev.{arso_note}{aifs_method}{wn2_method}</p>
  <p class="muted-note">Vir napovedi ARSO: Agencija Republike Slovenije za okolje (<a href="https://meteo.arso.gov.si" target="_blank" rel="noopener">ARSO</a>).</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body


def main():
    verification = load_verification()
    body = build_body(verification)

    url = "/tocnost-napovedi/"
    title = "Točnost vremenske napovedi — Rečica ob Savinji"
    n = len(verification)
    desc = (f"Koliko točna je vremenska napoved za Zgornjo Savinjsko dolino? Dnevni scoreboard ARSO, "
            f"Open-Meteo, MTR ter AI modelov ECMWF AIFS in Google WeatherNext 2 proti meritvam IREICA1 — "
            f"{n} razrešenih dni.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-14"),
        seo.crumbs_schema([("Meteorec", "/"), ("Točnost napovedi", None)]),
        seo.named_dataset_schema(
            url, "Verifikacija vremenske napovedi — Rečica ob Savinji",
            ("Dnevna primerjava napovedi ARSO, Open-Meteo, lokalnega modela MTR, ECMWF AIFS in Google "
             "DeepMind WeatherNext 2 za "
             "jutrišnjo najvišjo in najnižjo temperaturo ter padavine z dejansko meritvijo postaje IREICA1."),
            variable_measured=[
                {"@type": "PropertyValue", "name": "Napaka napovedi najvišje temperature", "unitText": "°C"},
                {"@type": "PropertyValue", "name": "Napaka napovedi najnižje temperature", "unitText": "°C"},
                {"@type": "PropertyValue", "name": "Razrešeni dnevi", "value": n, "unitText": "dni"},
            ],
            temporal_coverage=(f"{min(verification)}/{max(verification)}" if verification else None),
            distribution={"@type": "DataDownload", "encodingFormat": "application/json",
                          "contentUrl": f"{seo.SITE}/forecast_verification.json"},
        ),
    ]) + "\n" + CHART_CSS

    html_out = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("tocnost-napovedi/index.html", html_out, force=True)
    print(f"  → tocnost-napovedi/index.html ({n} razrešenih dni)")


if __name__ == "__main__":
    main()
