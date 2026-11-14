#!/usr/bin/env python3
"""
tools/generate_dez_mraz_post.py -- »82 mm dežja v dveh dneh, v nedeljo pa mraz« (14. 11. 2026).

Ročni podatkovni članek (dva dneva dežja 12.-13. 11. + napoved zmrzali za nedeljo 15. 11.). Številke so izračunane iz
committanih virov, nič ni vtipkano:
  - history.json                (postaja IREICA1: samo zunanja polja; dnevi z src == "era5" se ne štejejo),
  - data/hourly-observations.csv (urna meritev zunanjega senzorja: samo čas dežja),
  - forecast_verification.json  (napovedi, izdane dan prej: Open-Meteo, ECMWF AIFS, WeatherNext 2, MTR),
  - napoved-modela.json + tools/.forecast_pending.json (napoved za 14.-17. 11., mora biti današnja),
  - vodostaj-savinje/index.html (vgrajen posnetek ARSO za Savinjo, `#vod-data`).
Trditve varujejo assert-i: če se podatki spremenijo (npr. postaja izmeri ničlo v noči na nedeljo, napoved ni več današnja),
generator pade -- članek je treba prenoviti, ne zaobiti asserta. Članek je posnetek na dan objave.
Notranjih meritev ne uporablja (glej CLAUDE.md). Lektura prek workflowa je izklopljena: slogovni pregled po docs/slog-pisanja.md.

Usage:
    python3 tools/generate_dez_mraz_post.py [--dry-run] [--text] [--wire] [--force]
"""
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_slane_se_ni_post import (STYLE as BASE_STYLE, num, temp, fig, tiles, legend, first_freeze, NBSP,  # noqa: E402
                                       dm, dlong)

STYLE = BASE_STYLE.replace("</style>", ".sg-pt{cursor:pointer}.sg-pt:hover,.sg-pt:focus,.sg-pt.on{stroke:var(--text);stroke-width:1.6;outline:none}"
                           ".sg-read{min-height:2.6em;margin:.5rem 0 0;padding:.55rem .8rem;border:1px solid var(--card-border);border-radius:12px;font-size:.9rem;line-height:1.45;color:var(--text);background:rgba(255,255,255,.04)}"
                           ".sg-tabs{display:flex;flex-wrap:wrap;gap:.4rem;margin:.3rem 0 .6rem}.sg-tabs button{min-height:44px;min-width:44px;padding:.4rem .9rem;border:1px solid var(--card-border);border-radius:12px;background:transparent;color:var(--muted);font:inherit;font-size:.9rem;cursor:pointer}"
                           ".sg-tabs button[aria-pressed='true']{background:rgba(147,197,253,.16);color:var(--text);font-weight:600}.sg-tabs button:focus-visible{outline:2px solid var(--blue);outline-offset:2px}"
                           ".sg-m{fill:var(--muted)}.sg-i{fill:var(--text)}.sg-g{stroke:var(--card-border)}"
                           ".sg-h{stroke:var(--card-bg);stroke-width:3;paint-order:stroke}</style>")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
SLUG = "dez-82-mm-v-dveh-dneh-v-nedeljo-mraz-1114"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-dez-mraz.txt")
HISTORY = os.path.join(ROOT, "history.json")
HOURLY = os.path.join(ROOT, "data", "hourly-observations.csv")
VERIF = os.path.join(ROOT, "forecast_verification.json")
MODEL = os.path.join(ROOT, "napoved-modela.json")
PENDING = os.path.join(ROOT, "tools", ".forecast_pending.json")
MTRLOG = os.path.join(ROOT, "data", "mtr-live-log.csv")
VODOSTAJ = os.path.join(ROOT, "vodostaj-savinje", "index.html")
TODAY = datetime.date(2026, 11, 14)
D12, D13 = datetime.date(2026, 11, 12), datetime.date(2026, 11, 13)
BLUE, PINK, VIOLET, AMBER, CYAN, GREEN = "#3987e5", "#d55181", "#9085e9", "#fbbf24", "#22d3ee", "#199e70"   # barve virov: preverjena paleta (/tocnost-napovedi/)


def mtr_mm_day_before(target):
    """MTR `mm` (povprečje petih virov): prva osvežitev živega MTR na lokalni dan PRED ciljnim dnevom (iz data/mtr-live-log.csv)."""
    from zoneinfo import ZoneInfo
    t = datetime.date.fromisoformat(target)
    best = None
    for r in csv.DictReader(open(MTRLOG, encoding="utf-8")):
        if r["valid_at"] != target or not r["mm"]:
            continue
        iss = datetime.datetime.fromisoformat(r["issued_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Ljubljana"))
        if iss.date() == t - datetime.timedelta(days=1) and (best is None or iss < best[0]):
            best = (iss, float(r["mm"]))
    assert best, target
    return best[1]


def day(d):
    return d.isoformat()


# ───────────────────────── grafi (inline SVG, barve besedila iz teme strani) ─────────────────────────

def rain_chart(H, w=460):
    """Stolpci: dnevne padavine od 1. do 13. 11.; 12. in 13. poudarjena."""
    pl, pr, pt, pb, h = 34, 10, 22, 28, 230
    ih, iw = h - pt - pb, w - pl - pr
    days = [datetime.date(2026, 11, i) for i in range(1, 14)]
    hi = 60.0
    Y = lambda v: pt + ih * (1 - v / hi)
    slot = iw / len(days)
    bw = slot * 0.72
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Dnevne padavine v Rečici od 1. do 13. novembra 2026: 12. novembra 51,8 mm, 13. novembra 30,7 mm, ostali dnevi do 3,3 mm" xmlns="http://www.w3.org/2000/svg">']
    for v in (0, 20, 40, 60):
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="sg-g" stroke-width="1"/>')
        p.append(f'<text x="{pl - 6}" y="{Y(v) + 3.5:.1f}" text-anchor="end" font-size="10.5" class="sg-m">{v}</text>')
    p.append(f'<text x="{pl}" y="{pt - 8}" font-size="10.5" class="sg-m">mm na dan</text>')
    for i, d in enumerate(days):
        v = H[day(d)]["precipTotal"]
        x = pl + slot * i + (slot - bw) / 2
        big = d in (D12, D13)
        p.append(f'<rect x="{x:.1f}" y="{Y(v):.1f}" width="{bw:.1f}" height="{max(Y(0) - Y(v), 1):.1f}" rx="2" fill="{BLUE}" fill-opacity="{1 if big else .45}"'
                 f' data-t="{dm(d)}: {num(v)} mm padavin" tabindex="0" class="sg-pt"><title>{dm(d)}: {num(v)} mm</title></rect>')
        if big:
            p.append(f'<text x="{x + bw / 2:.1f}" y="{Y(v) - 5:.1f}" text-anchor="middle" font-size="11" font-weight="700" class="sg-i sg-h">{num(v)}</text>')
        if i % 2 == 0 or big:
            p.append(f'<text x="{x + bw / 2:.1f}" y="{h - 9}" text-anchor="middle" font-size="10" class="sg-m">{d.day}.</text>')
    p.append("</svg>")
    return "".join(p)


def forecast_chart(rows, w=460, hi=60.0, nsw=False):
    """rows = [(skupina, [(ime, vrednost, barva|None)])]; vodoravni stolpci, izmerjena vrednost je prva v skupini."""
    pl, pr, pt, rh, gap = 112, 40, 8, 25, 22
    n = sum(len(r[1]) for r in rows)
    h = pt + n * rh + gap * len(rows) + 4
    X = lambda v: pl + (w - pl - pr) * v / hi
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Napovedana in izmerjena količina padavin 12. in 13. novembra po virih" xmlns="http://www.w3.org/2000/svg">']
    y = pt
    for gi, (gname, items) in enumerate(rows):
        ref = items[0][1]
        errs = " · ".join(f"{n_} {'+' if v - ref > 0 else '–' if v - ref < 0 else ''}{num(abs(v - ref))} mm" for n_, v, c_ in items[1:])
        p.append(f'<g class="sg-grp" data-g="{gi}" data-y="{y}" data-h="{gap + len(items) * rh}" data-r="{gname}: izmerjeno {num(ref)} mm. Razlika napovedi od izmerjenega: {errs}"><text x="2" y="{y + 12}" font-size="11.5" font-weight="700" class="sg-i">{gname}</text>')
        y += gap - 4
        for name, v, col in items:
            cy = y + rh / 2
            meas = col is None
            cls = "sg-i" if meas else "sg-m"
            fw = ' font-weight="700"' if meas else ""
            p.append(f'<text x="{pl - 8}" y="{cy + 4:.1f}" text-anchor="end" font-size="11" class="{cls}"{fw}>{name}</text>')
            fill = 'class="sg-i"' if meas else f'fill="{col}"'
            p.append(f'<rect x="{pl}" y="{cy - 8:.1f}" width="{max(X(v) - pl, 1.5):.1f}" height="16" rx="2" {fill} fill-opacity="{1 if meas else .85}"'
                     f' data-t="{gname}, {name}: {num(v)} mm" tabindex="0" class="sg-pt"><title>{gname}, {name}: {num(v)} mm</title></rect>')
            p.append(f'<text x="{X(v) + 5:.1f}" y="{cy + 4:.1f}" font-size="11" font-weight="{700 if meas else 400}" class="sg-i">{num(v)}</text>')
            y += rh
        p.append("</g>")
        y += 4
    p.append("</svg>")
    return "".join(p)


def nights_chart(ns, fc, w=460):
    """Najnižja temperatura vsake noči 1.-13. 11. (izmerjeno) in 14.-17. 11. (napoved MTR, črtkani stolpci)."""
    pl, pr, pt, pb, h = 34, 10, 22, 28, 230
    ih, iw = h - pt - pb, w - pl - pr
    d0 = ns[0][0]
    slots = (fc[-1][0] - d0).days + 1
    lo, hi = -4.0, 10.0
    Y = lambda t: pt + ih * (hi - t) / (hi - lo)
    slot = iw / slots
    bw = slot * 0.72
    X = lambda d: pl + slot * (d - d0).days + (slot - bw) / 2
    p = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Najnižja temperatura vsake noči od 1. do 13. novembra (meritev) in napoved modela MTR za 14. do 17. novembra" xmlns="http://www.w3.org/2000/svg">']
    for t in (-4, 0, 4, 8):
        dash = ' stroke-dasharray="4 3"' if t == 0 else ""
        look = f'stroke="{CYAN}"' if t == 0 else 'class="sg-g"'
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" {look} stroke-width="{1.5 if t == 0 else 1}"{dash}/>')
        p.append(f'<text x="{pl - 6}" y="{Y(t) + 3.5:.1f}" text-anchor="end" font-size="10.5" class="sg-m">{str(t).replace("-", "–")}</text>')
    p.append(f'<text x="{pl}" y="{pt - 8}" font-size="10.5" class="sg-m">najnižja temperatura, °C</text>')
    base = Y(0)
    for d, t in ns:
        x, y = X(d), Y(t)
        frost = t <= 0
        p.append(f'<rect x="{x:.1f}" y="{min(y, base):.1f}" width="{bw:.1f}" height="{max(abs(y - base), 1.5):.1f}" rx="2" fill="{CYAN if frost else BLUE}" fill-opacity="{1 if frost else .5}"'
                 f' data-t="{dm(d)}: najnižja izmerjena {temp(t)}" tabindex="0" class="sg-pt"><title>{dm(d)}: najnižja {temp(t)}</title></rect>')
    for d, t in fc:
        x, y = X(d), Y(t)
        p.append(f'<rect x="{x:.1f}" y="{min(y, base):.1f}" width="{bw:.1f}" height="{max(abs(y - base), 1.5):.1f}" rx="2" fill="{AMBER}" fill-opacity=".2" '
                 f'stroke="{AMBER}" stroke-width="1.4" stroke-dasharray="3 2" data-t="{dm(d)}: napoved MTR {temp(t)}" tabindex="0" class="sg-pt"><title>{dm(d)}: napoved MTR {temp(t)}</title></rect>')
    for d, t in [r for r in ns if r[0].day in (1, 9)] + [r for r in fc if r[0].day == 15]:
        cx = X(d) + bw / 2
        yy = Y(t) + (13 if t < 0 else -5)
        if t < 0 and d >= fc[0][0]:
            yy = Y(t) + 13
        p.append(f'<text x="{cx:.1f}" y="{yy:.1f}" text-anchor="middle" font-size="10.5" font-weight="700" class="sg-i sg-h">{num(t).replace("-", "–")}</text>')
    for d in sorted({r[0] for r in ns + fc if r[0].day in (1, 5, 9, 13, 17)}):
        p.append(f'<text x="{X(d) + bw / 2:.1f}" y="{h - 9}" text-anchor="middle" font-size="10" class="sg-m">{d.day}.</text>')
    p.append("</svg>")
    return "".join(p)


def ifig(ix, title, inner, caption, tabs=None, hint="Dotaknite se stolpca ali ga izberite s tipkovnico: tu se izpiše vrednost."):
    """figure z odčitkom (JS ga odkrije) in izbirnimi zavihki (preklop skupin v grafu)."""
    tb = ""
    if tabs:
        tb = '<div class="sg-tabs" role="group" aria-label="Izbira prikaza" hidden>' + "".join(
            f'<button type="button" data-tab="{i}">{t}</button>' for i, t in enumerate(tabs)) + "</div>"
    return (f'<figure class="vs-fig" data-ix="{ix}"><h3>{title}</h3>{tb}{inner}'
            f'<p class="sg-read" aria-live="polite" hidden data-hint="{hint}">{hint}</p><figcaption>{caption}</figcaption></figure>')


SCRIPT = """<script>
(function(){
  function init(){
    document.querySelectorAll('figure[data-ix]').forEach(function(fig){
      var rd=fig.querySelector('.sg-read'); if(rd) rd.hidden=false;
      fig.querySelectorAll('.sg-pt').forEach(function(el){
        function show(){
          fig.querySelectorAll('.sg-pt.on').forEach(function(x){x.classList.remove('on');});
          el.classList.add('on'); if(rd) rd.textContent=el.getAttribute('data-t');
        }
        el.addEventListener('mouseenter',show); el.addEventListener('focus',show); el.addEventListener('click',show);
      });
      var tabs=fig.querySelector('.sg-tabs');
      if(tabs){
        var svg=fig.querySelector('svg'), vb=svg.getAttribute('viewBox').split(' '), groups=fig.querySelectorAll('.sg-grp'), btns=tabs.querySelectorAll('button');
        tabs.hidden=false;
        function pick(i){
          groups.forEach(function(g,k){
            var on=(k===i); g.style.display=on?'':'none';
            if(on){svg.setAttribute('viewBox','0 '+(+g.getAttribute('data-y')-2)+' '+vb[2]+' '+(+g.getAttribute('data-h')+4)); if(rd) rd.textContent=g.getAttribute('data-r');}
          });
          btns.forEach(function(b,k){b.setAttribute('aria-pressed',k===i?'true':'false');});
        }
        btns.forEach(function(b,k){b.addEventListener('click',function(){pick(k);});});
        pick(groups.length-1);
      }
    });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
</script>"""


# ───────────────────────── podatki ─────────────────────────

def load_vodostaj():
    s = open(VODOSTAJ, encoding="utf-8").read()
    m = re.search(r'id="vod-data">(.*?)</script>', s, re.S)
    return json.loads(m.group(1))


def distinct_events(S):
    """Dvodnevne vsote padavin (dan + prejšnji), brez prekrivanja: pohlepno od največje."""
    prev = lambda k: (datetime.date.fromisoformat(k) - datetime.timedelta(days=1)).isoformat()
    pairs = sorted(((round(S[k]["precipTotal"] + S[prev(k)]["precipTotal"], 1), k) for k in S
                    if prev(k) in S and S[k].get("precipTotal") is not None and S[prev(k)].get("precipTotal") is not None), reverse=True)
    taken, out = set(), []
    for v, k in pairs:
        ks = {k, prev(k)}
        if ks & taken:
            continue
        taken |= ks
        out.append((v, k))
    return out


def build_article():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    S = {k: v for k, v in H.items() if v.get("src") != "era5"}
    assert datetime.date.today() == TODAY, "članek je napisan za 14. 11. 2026"
    assert max(S) == "2026-11-13", f"zadnji dan v history.json je {max(S)}"

    # ---- dež ----
    p12, p13 = S[day(D12)]["precipTotal"], S[day(D13)]["precipTotal"]
    assert (p12, p13) == (51.8, 30.7)
    two = round(p12 + p13, 1)
    assert two == 82.5
    nov = sum(v["precipTotal"] for k, v in S.items() if k.startswith("2026-11") and v.get("precipTotal") is not None)
    assert round(nov, 1) == 96.2
    share = round(100 * two / nov)
    assert share == 86
    others = [S[f"2026-11-{i:02d}"]["precipTotal"] for i in range(1, 12)]
    assert max(others) == 6.3
    ev = distinct_events(S)
    rank = [k for _, k in ev].index(day(D13)) + 1
    assert rank == 6 and [k[:7] for _, k in ev[:6]].count("2026-09") == 1, ev[:7]
    nov_prev = max(v for v, k in ev if k.startswith(("2019-11", "2020-11", "2021-11", "2022-11", "2023-11", "2024-11", "2025-11")))
    assert nov_prev == 62.9, nov_prev
    nov_days = sorted(((v["precipTotal"], k) for k, v in S.items() if k[5:7] == "11" and v.get("precipTotal") is not None), reverse=True)[:2]
    assert nov_days == [(61.8, "2023-11-05"), (51.8, "2026-11-12")], nov_days
    assert S[day(D13)]["pressureLow"] == 988.9 and S[day(D13)]["pressureHigh"] == 1017.3
    assert sorted(k[:7] for _, k in ev[:6]).count("2026-09") == 1 and day(D13) in [k for _, k in ev[:6]]
    pres = sorted((v["pressureLow"], k) for k, v in S.items() if v.get("pressureLow"))
    assert [k for _, k in pres[:4]] == ["2026-02-12", "2023-11-03", "2026-11-12", "2026-11-13"], pres[:4]
    # kdaj je padlo (urni zapis; vsota urnih vrednosti se od dnevne rahlo razlikuje)
    hr = [r for r in csv.DictReader(open(HOURLY, encoding="utf-8")) if r["valid_at_local"][:10] in (day(D12), day(D13)) and r["precip_mm"]]
    tot_h = sum(float(r["precip_mm"]) for r in hr)
    core = sum(float(r["precip_mm"]) for r in hr if "2026-11-12T16:00" <= r["valid_at_local"] <= "2026-11-13T02:00")
    core_pct = round(100 * core / tot_h)
    assert len(hr) == 48 and core_pct == 85, (len(hr), core_pct)

    # ---- napovedi, izdane dan prej ----
    V = json.load(open(VERIF, encoding="utf-8"))
    f12, f13 = V[day(D12)], V[day(D13)]
    assert f12["actual"]["precip"] == p12 and f13["actual"]["precip"] == p13
    om12, ai12, wn12 = f12["open_meteo"]["precip"], f12["aifs"]["precip"], f12["wn2"]["precip"]
    om13, ai13, wn13 = f13["open_meteo"]["precip"], f13["aifs"]["precip"], f13["wn2"]["precip"]
    assert (om12, ai12, wn12) == (33.13, 8.7, 5.4) and (om13, ai13, wn13) == (32.9, 48.5, 42.9)
    sums = {"Open-Meteo": om12 + om13, "ECMWF AIFS": ai12 + ai13, "WeatherNext 2": wn12 + wn13}
    assert all(v < two for v in sums.values()), sums
    mt12, mt13 = mtr_mm_day_before(day(D12)), mtr_mm_day_before(day(D13))
    assert (mt12, mt13) == (39.1, 40.4), (mt12, mt13)
    mtr_sum = round(mt12 + mt13, 1)
    assert mtr_sum == 79.5 and abs(mtr_sum - two) < min(abs(v - two) for v in sums.values()), mtr_sum
    assert f12["meteorec"]["pop"] == 1.0 and f13["meteorec"]["pop"] == 1.0
    assert "precip" not in f12["arso"] and "precip" not in f13["arso"]
    assert round(sums["Open-Meteo"], 1) == 66.0 and round(sums["ECMWF AIFS"], 1) == 57.2 and round(sums["WeatherNext 2"], 1) == 48.3

    # ---- Savinja (ARSO, vgrajen posnetek strani /vodostaj-savinje/) ----
    W = {x["name"]: x for x in load_vodostaj()}
    naz, let, sol = W["Savinja - Nazarje"], W["Savinja - Letuš I"], W["Savinja - Solčava I"]
    for x in (naz, let, sol):
        assert x["datum"] == "2026-11-14 12:30" and x["znacilni"] == "običajni pretok" and x["vv1"], x
    assert (naz["pretok"], naz["vv1"], let["pretok"], let["vv1"]) == (42.0, 310.0, 50.3, 360.0)

    # ---- mraz ----
    ns = [(datetime.date(2026, 11, i), S[f"2026-11-{i:02d}"]["tempLow"]) for i in range(1, 14)]
    frost_nights = [k for k, v in S.items() if "2026-09-01" <= k <= "2026-11-13" and v.get("tempLow") is not None and v["tempLow"] <= 0]
    assert frost_nights == ["2026-10-23", "2026-10-27", "2026-10-28", "2026-11-09"], frost_nights
    coldest = min(S[k]["tempLow"] for k in S if "2026-09-01" <= k <= "2026-11-13")
    assert coldest == -1.7
    ff = {y: first_freeze(H, y) for y in range(2020, 2027)}
    assert ff[2026] == datetime.date(2026, 10, 23)
    later = [y for y in range(2020, 2026) if ff[y].replace(year=2026) > ff[2026].replace(year=2026)]
    assert later == [2022, 2024], later
    mdl = json.load(open(MODEL, encoding="utf-8"))
    gen = datetime.datetime.fromisoformat(mdl["generated_at"].replace("Z", "+00:00"))
    assert gen.date() == TODAY, f"napoved modela ni današnja ({gen.date()})"
    fd = {r["date"]: r for r in mdl["days"]}
    sun, mon, tue = fd["2026-11-15"], fd["2026-11-16"], fd["2026-11-17"]
    assert sun["tmin"] == -2.5 and abs(sun["p_frost"] - .93) < .005 and sun["tmax"] == 7.7 and sun["night_regime"] == "overcast", sun
    pend = {x["target_date"]: x for x in json.load(open(PENDING, encoding="utf-8"))}
    sat_p, sun_p = pend["2026-11-14"], pend["2026-11-15"]
    assert sun_p["made_at"] == "2026-11-14" and sun_p["arso"]["tmin"] == -4 and sun_p["open_meteo"]["tmin"] == -3.0
    assert (sun_p["aifs"]["tmin"], sun_p["wn2"]["tmin"]) == (-1.3, -1.7) and sun_p["arso"]["loc"] == "Ljubno ob Savinji"
    assert sat_p["meteorec"]["tmin"] == -1.3 and sat_p["made_at"] == "2026-11-13"
    fc = [(datetime.date(2026, 11, 14), sat_p["meteorec"]["tmin"]), (datetime.date(2026, 11, 15), sun["tmin"]),
          (datetime.date(2026, 11, 16), mon["tmin"]), (datetime.date(2026, 11, 17), tue["tmin"])]
    assert [t for _, t in fc] == [-1.3, -2.5, 1.4, 5.4], fc
    assert S["2026-11-12"]["tempHigh"] == 13.9
    # preverjanje članka z 21. 10.: MTR je za 23. 10. napovedal 0,1 °C, postaja je izmerila -0,1 °C
    assert S["2026-10-23"]["tempLow"] == -0.1
    assert "0,1" in open(os.path.join(ROOT, "blog", "16-noci-pod-5-c-slane-se-ni-1021.html"), encoding="utf-8").read()

    assert sun["tmin"] < coldest, "nedeljska napoved ni več pod letošnjim minimumom -- prenovi stavek o mrazu"

    # ---- grafi ----
    f_rain = ifig("rain", "Dnevne padavine v Rečici, 1.–13. novembra",
                 rain_chart(S),
                 f"Vsak stolpec prikazuje padavine v enem dnevu. Podatki so meritve dežemera postaje IREICA1. Poudarjena stolpca za 12. in 13. november skupaj predstavljata "
                 f"{num(two)} mm oziroma {share} % vse novembrske količine padavin do vključno 13. novembra ({num(nov)} mm).")
    g12 = ("12. november (napoved z 11. 11.)", [("Izmerjeno", p12, None), ("MTR", mt12, GREEN), ("Open-Meteo", om12, BLUE), ("ECMWF AIFS", ai12, PINK), ("WeatherNext 2", wn12, VIOLET)])
    gsum = ("Oba dneva skupaj", [("Izmerjeno", two, None), ("MTR", mtr_sum, GREEN), ("Open-Meteo", round(sums["Open-Meteo"], 1), BLUE),
                                 ("ECMWF AIFS", round(sums["ECMWF AIFS"], 1), PINK), ("WeatherNext 2", round(sums["WeatherNext 2"], 1), VIOLET)])
    g13 = ("13. november (napoved z 12. 11.)", [("Izmerjeno", p13, None), ("MTR", mt13, GREEN), ("Open-Meteo", om13, BLUE), ("ECMWF AIFS", ai13, PINK), ("WeatherNext 2", wn13, VIOLET)])
    f_fc = ifig("fc", "Koliko dežja so modeli napovedali dan prej in koliko ga je dejansko padlo",
               forecast_chart([g12, g13, gsum], hi=90.0, nsw=True),
               "Napovedane količine padavin, izdane dan pred posameznim dnevom, so prikazane v milimetrih in veljajo za lokacijo Rečice. MTR prikazuje okvirno pričakovano količino, "
               "izračunano kot povprečje petih virov; ne gre za naučen lokalni popravek. Upoštevana je prva osvežitev živega MTR na dan pred dogodkom. "
               "ARSO v tej primerjavi količine padavin ne navaja. Izmerjena količina je dnevna vsota postaje.", tabs=["12. 11.", "13. 11.", "Skupaj"])
    f_cold = ifig("cold", "Najnižje temperature zraka po nočeh",
                 legend([("izmerjeno, nad ničlo", BLUE, "op"), ("izmerjeno, 0 °C ali manj", CYAN, ""),
                         ("napoved MTR za 14.–17. novembra", AMBER, "dash")]) + nights_chart(ns, fc),
                 "Prikazane so najnižje temperature zraka, izmerjene z zunanjim senzorjem postaje IREICA1 med 1. in 13. novembrom. Črtkani stolpci prikazujejo napoved modela MTR "
                 "za obdobje od 14. do 17. novembra: napoved za 14. november je bila izdana 13. novembra, preostale pa zjutraj 14. novembra. Črtkana modra črta označuje 0 °C.")

    t_rain = tiles([
        (num(p12), "mm", "toliko dežja je padlo 12. novembra. To je drugi najmočnejši novembrski dan od leta 2019, za 5. novembrom 2023 (61,8 mm).", False),
        (num(p13), "mm", f"toliko dežja je padlo 13. novembra. Zračni tlak je ta dan narasel z {num(S[day(D13)]['pressureLow'])} na {num(S[day(D13)]['pressureHigh'])} hPa.", False),
        (num(pres[2][0]), "hPa", "najnižji dnevni tlak 12. novembra in tretji najnižji med vsemi dnevi, odkar postaja meri.", False),
    ])
    t_cold = tiles([
        (num(sun["tmin"]).replace("-", "–"), "°C", f"napoved MTR za najnižjo temperaturo v nedeljo, 15. novembra. Najnižja doslej izmerjena temperatura te jeseni je {temp(coldest)}.", True),
        ("93", "%", "MTR ocenjuje tolikšno verjetnost, da bo temperatura zraka padla na 0 °C ali manj.", True),
        (num(sun["tmax"]), "°C", f"napoved MTR za najvišjo temperaturo v nedeljo. Med deževnim dogodkom 12. novembra je najvišja temperatura dosegla {temp(S['2026-11-12']['tempHigh'])}.", False),
    ])

    lead = (f"V dveh dneh, 12. in 13. novembra, je v Rečici padlo <strong>{num(two)} mm</strong> dežja. "
            f"To je {share} % vse novembrske količine padavin, izmerjene do 13. novembra ({num(nov)} mm). "
            f"Po deževnem dogodku sledi občutna ohladitev: model MTR za nedeljsko jutro napoveduje <strong>{temp(sun['tmin'])}</strong>, "
            f"verjetnost, da bo temperatura zraka padla na 0 °C ali manj, pa ocenjuje na {round(sun['p_frost'] * 100)} %.")

    p1 = [
        f"<strong>Kratek odgovor: šlo je za zelo izrazit deževni dogodek, nedeljski mraz pa je za zdaj še napoved.</strong> "
        f"Med vsemi dvodnevnimi seštevki padavin, ki jih je postaja zabeležila od novembra 2019, je ta dogodek <strong>šesti največji</strong>. "
        f"Dvodnevni seštevek je vsota dveh zaporednih koledarskih dni, seštevke, ki se prekrivajo, pa štejem samo enkrat. "
        f"Dva od šestih največjih dogodkov sta se zgodila letos: prvi septembra, drugi pa zdaj. Prejšnji največji dvodnevni novembrski seštevek je bil zabeležen leta 2023 ({num(nov_prev)} mm).",
        t_rain,
        f_rain,
        f"Večina dežja je padla v kratkem času. Po urnih meritvah postaje je {core_pct} % padavin padlo med 16. uro 12. novembra in 2. uro 13. novembra. "
        "Urni seštevek se nekoliko razlikuje od dnevne vsote, zato v članku uporabljam dnevne vsote.",
        f"Vsi preostali novembrski dnevi do vključno 11. novembra so skupaj prinesli {num(nov - two)} mm padavin. Nobeden od njih ni presegel {num(max(others))} mm.",
    ]
    p2 = [
        "Pogledal sem, koliko padavin so različni viri napovedali dan pred vsakim od obravnavanih dni. Trije tuji viri so za oba dneva skupaj napovedali manj padavin, kot jih je dejansko padlo: "
        f"Open-Meteo {num(sums['Open-Meteo'])} mm, ECMWF AIFS {num(sums['ECMWF AIFS'])} mm in Google WeatherNext 2 {num(sums['WeatherNext 2'])} mm. "
        f"Izmerjeni količini se je najbolj približala napoved modela MTR, ki je znašala <strong>{num(mtr_sum)} mm</strong> ({num(mt12)} mm za 12. in {num(mt13)} mm za 13. november). Izmerjenih je bilo {num(two)} mm.",
        f_fc,
        f"Največja odstopanja so bila pri napovedi za <strong>prvi dan</strong>. Za 12. november sta AIFS in WeatherNext 2 napovedala {num(ai12)} oziroma {num(wn12)} mm, padlo pa je {num(p12)} mm. "
        f"Open-Meteo je bil z napovedjo {num(om12, 1)} mm bliže izmerjeni količini, napoved MTR ({num(mt12)} mm) pa se ji je približala še bolj. "
        f"Za 13. november sta bila AIFS in WeatherNext 2 nasprotno previsoka ({num(ai13)} oziroma {num(wn13)} mm v primerjavi z izmerjenimi {num(p13)} mm). "
        f"MTR je napovedal {num(mt13)} mm, Open-Meteo pa je bil z {num(om13)} mm zelo blizu izmerjeni količini.",
        "MTR napovedanih količin ne prilagaja na podlagi meritev postaje. Njegova pričakovana količina je povprečje petih napovednih virov: Open-Meteo best_match in štirih drugih modelov. "
        "Zato odraža skupno mnenje modelov, ne pa lokalnega znanja o razmerah v Rečici. Verjetnost dežja je bila za oba dneva 100 %. "
        "Na podlagi enega dogodka ne morem sklepati, kateri vir je praviloma najboljši. Tokrat se je povprečje več modelov izkazalo za bližje meritvi kot kateri koli od posameznih tujih modelov. "
        "To je skladno s pričakovanjem, vendar samo po sebi še ni dokaz, da je povprečje vedno boljše.",
    ]
    p3 = [
        "Po tolikšni količini dežja bi lahko pričakovali visok vodostaj Savinje. Zato sem pogledal meritve postaj ARSO na spletni strani "
        '<a href="/vodostaj-savinje/" style="color:var(--blue)">Vodostaj Savinje</a>. Ob 12.30 14. novembra so bili pretoki na vseh treh merilnih postajah ob zgornji Savinji v običajnem območju.',
        "<ul>"
        f"<li><strong>Solčava:</strong> {num(sol['pretok'], 2)} m³/s (prag prve stopnje: {num(sol['vv1'], 0)} m³/s)</li>"
        f"<li><strong>Nazarje:</strong> {num(naz['pretok'], 1)} m³/s (prag prve stopnje: {num(naz['vv1'], 0)} m³/s)</li>"
        f"<li><strong>Letuš:</strong> {num(let['pretok'], 1)} m³/s (prag prve stopnje: {num(let['vv1'], 0)} m³/s)</li>"
        "</ul>",
        "<strong>Vir: ARSO.</strong> To je stanje ob 12.30 14. novembra in ne podatek o največjem pretoku med dogodkom. Podatka o vrhu med 12. in 14. novembrom nimam, "
        "zato ne morem povedati, kako visoko je Savinja takrat narasla. Ob zadnjem odčitku pa je bil njen pretok že v običajnem območju. "
        "Količina padavin, izmerjena v Rečici, ni nujno enaka količini padavin v zgornjem porečju, saj postaja meri le na eni lokaciji.",
    ]
    p4 = [
        f"<strong>Nedelja, 15. november.</strong> Model MTR napoveduje najnižjo temperaturo {temp(sun['tmin'])}, "
        f"verjetnost, da bo temperatura zraka padla na 0 °C ali manj, pa ocenjuje na {round(sun['p_frost'] * 100)} %. V noči na nedeljo model napoveduje oblačnost, ne jasnega neba.",
        t_cold,
        f_cold,
        "<ul>"
        f"<li><strong>ARSO</strong> (napoved za Ljubno ob Savinji): {temp(sun_p['arso']['tmin'], 0)}</li>"
        f"<li><strong>Open-Meteo</strong>: {temp(sun_p['open_meteo']['tmin'])}</li>"
        f"<li><strong>MTR</strong>: {temp(sun['tmin'])}</li>"
        f"<li><strong>WeatherNext 2</strong>: {temp(sun_p['wn2']['tmin'])}</li>"
        f"<li><strong>ECMWF AIFS</strong>: {temp(sun_p['aifs']['tmin'])}</li>"
        "</ul>",
        f"Vse napovedi kažejo temperature pod ničlo. Razpon med najhladnejšo in najmilejšo napovedjo je {num(sun_p['aifs']['tmin'] - sun_p['arso']['tmin'])} °C "
        f"(od {num(sun_p['arso']['tmin'], 0).replace('-', '–')} do {num(sun_p['aifs']['tmin']).replace('-', '–')} °C). Napoved ARSO se nanaša na Ljubno ob Savinji, ne na Rečico.",
        f"Temperature okoli ničle v tem delu jeseni niso nenavadne, nedeljska napoved pa bi lahko prinesla najnižjo temperaturo letošnje jeseni. "
        f"Od 1. septembra do 13. novembra je postaja štirikrat izmerila temperaturo zraka 0 °C ali manj: 23., 27. in 28. oktobra ter 9. novembra. Najnižja izmerjena temperatura je bila {temp(coldest)}. "
        f"Prvič je temperatura padla na 0 °C ali manj {dlong(ff[2026])}: pozneje kot v štirih od šestih prejšnjih jeseni, a prej kot v letih 2022 in 2024.",
        'O prvi ničli sem pisal že <a href="/blog/16-noci-pod-5-c-slane-se-ni-1021.html" style="color:var(--blue)">21. oktobra</a>. '
        f"Model MTR je za 23. oktober napovedal 0,1 °C, postaja pa je izmerila {temp(S['2026-10-23']['tempLow'])}. Napoved, ki jo je isti model izdal dan prej, 22. oktobra, je bila 1,4 °C.",
    ]
    p5 = [
        "<ul>"
        "<li><strong>Cesta:</strong> po dvodnevnem dežju so cestišča mokra. Če temperatura zraka pade do ničle ali pod njo, lahko na njih nastane poledica. "
        "Postaja temperature cestišča ne meri, zato ne vem, ali bo do nje dejansko prišlo. Več o tem si lahko preberete na strani "
        '<a href="/zima/poledica/" style="color:var(--blue)">Poledica</a>, razmere na Črnivcu pa spremljate na <a href="https://crnivec.si/" style="color:var(--blue)">crnivec.si</a>.</li>'
        "<li><strong>Vrt in balkon:</strong> rastline, ki ne prenesejo mraza, pokrijte ali prenesite v zavetje. Na travnikih in v mraziščih je lahko hladneje kot pri postaji.</li>"
        "<li><strong>Zunanje pipe in cevi:</strong> v njih lahko ostane voda, zato jih pred nočjo z nizkimi temperaturami izpraznite ali zaščitite.</li>"
        f'<li><strong>Preizkusite se:</strong> v igri <a href="{SITE}/napovej/" style="color:var(--blue)">Prehiti model</a> napovejte najnižjo temperaturo za jutri in jo primerjajte z napovedmi modelov.</li>'
        "</ul>",
    ]
    omejitve = [
        "<ul>"
        "<li><strong>En dogodek, ena postaja.</strong> Iz dvodnevnega deževnega dogodka ne morem sklepati o splošni točnosti modelov ali o trendu. Dež je bil na tej lokaciji izjemen, drugje v dolini pa je lahko padlo drugače.</li>"
        "<li><strong>Napoved ni meritev.</strong> Napovedi za obdobje od 14. do 17. novembra so bile izdane 13. in 14. novembra, do nedelje pa se lahko še spremenijo. "
        "MTR je poskusni model, Open-Meteo, ECMWF AIFS in WeatherNext 2 pa so tuji viri. Nobena od teh napovedi ni uradno opozorilo. "
        'Za uradna opozorila spremljajte <a href="https://vreme.arso.gov.si/napoved" style="color:var(--blue)">ARSO</a>.</li>'
        "<li><strong>Podatki o reki so posnetek trenutnega stanja.</strong> Navedeni pretoki so odčitki ARSO ob 12.30 14. novembra. Podatka o najvišjem pretoku med dogodkom nimam.</li>"
        "<li><strong>Uvrstitev dogodka je omejena na obdobje meritev.</strong> Rang velja za obdobje od novembra 2019, ko je postaja začela meriti, in za dvodnevne seštevke. Ne gre za uradno klimatološko statistiko.</li>"
        "<li><strong>Članek je posnetek stanja na dan objave.</strong> Po nedeljskem jutru se besedilo ne posodobi samodejno.</li>"
        "</ul>",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le ob navedbi avtorja '
        '(Filip Eremita, Meteorec) in neposredne povezave na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    title = "82 mm dežja v dveh dneh, v nedeljo pa mraz"
    assert len(title) <= 60, len(title)
    desc = ("V Rečici je 12. in 13. novembra padlo 82,5 mm dežja, v nedeljo pa napoved kaže do –2,5 °C. Kaj so napovedali modeli in kaj je izmerila postaja?")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — dež", "heading": "Šesti največji dvodnevni seštevek padavin od leta 2019", "id": "dez", "paragraphs": p1},
        {"label": "02 — napoved", "heading": "Napoved MTR se je izmerjeni količini najbolj približala", "id": "napoved", "paragraphs": p2},
        {"label": "03 — Savinja", "heading": "Pretok Savinje je bil ob zadnjem odčitku običajen", "id": "savinja", "paragraphs": p3},
        {"label": "04 — mraz", "heading": "Napoved: v nedeljo zjutraj pod ničlo", "id": "mraz", "paragraphs": p4},
        {"label": "05 — praktično", "heading": "Kaj lahko naredite?", "id": "prakticno", "paragraphs": p5},
        {"label": "06 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
    ]

    def nb(h):
        return re.sub(r"(\d) (°C|%|mm|hPa|m³/s)", lambda m: m.group(1) + NBSP + m.group(2), h)
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["dež", "padavine", "mraz", "zmrzal", "november", "napoved"],
        "section_label": "Podatkovna analiza", "og_photo": "misty-valley", "og_accent_hex": "#93c5fd",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: postaja IREICA1 (dnevne in urne meritve zunanjega senzorja); napovedi Open-Meteo, ECMWF AIFS in Google WeatherNext 2 (prek Open-Meteo) "
                         "ter model MTR (Meteorec; količine padavin so povzete iz dnevnika živih osvežitev data/mtr-live-log.csv), izdane dan pred posameznim dnevom; napoved ARSO za Ljubno ob Savinji; "
                         "podatki o pretoku Savinje: Agencija Republike Slovenije za okolje (ARSO), stanje 14. 11. 2026 ob 12.30."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|figcaption|li|p|div)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace("&shy;", "").replace(NBSP, " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        for p in s["paragraphs"]:
            out.append(clean(p))
            out.append("")
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    article = build_article()
    if "--text" in sys.argv:
        open(TEXT_OUT, "w", encoding="utf-8").write(plain_text(article))
        print("✓ besedilo za lekturo:", os.path.relpath(TEXT_OUT, ROOT))
    if dry:
        print(plain_text(article))
        return
    path = os.path.join(ROOT, "blog", f"{SLUG}.html")
    if os.path.exists(path) and not force:
        print(f"blog/{SLUG}.html že obstaja -- brez ponovne objave (--force za prepis).")
        return
    import generate_forecast_test_post as ftp
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = TODAY.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, TODAY.year, TODAY.month, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="82 mm dežja,\nv nedeljo mraz", meta_note="podatkovna analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    assert html.count("</body>") == 1
    html = html.replace("</body>", SCRIPT + "\n</body>", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html ({round(len(html) / 1024)} kB)")
    if wire or "--og" in sys.argv:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
    if wire:
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml, teme in sorodni članki osveženi.")


if __name__ == "__main__":
    main()
