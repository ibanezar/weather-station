#!/usr/bin/env python3
"""
tools/generate_drva_page.py — /zima/poraba-drv/ »Koliko drv za zimo?« (18. 11. 2026)

Kalkulator porabe drv po stopinjskih dneh. Podatki: history.json (postaja IREICA1, samo zunanja `tempAvg`; dnevi z
src == "era5" izpuščeni). Definicija stopinjskih dni je ista kot v članku »Koliko kuriti? Stopinjski dnevi Rečice«
(tools/generate_zima_clanki.py, hdd()): dan s povprečjem pod 12 °C prispeva 20 − T. Kurilna sezona je 1. 10.–30. 4.

- V stran se vdela krivulja kumulativnih stopinjskih dni po sezonah (5 popolnih sezon 2020/21–2024/25 za scenarije,
  2025/26 samo kot izbira »lanske« sezone: manjkajo 4 dnevi, kot v članku), JS (zima/poraba-drv/drva.js, ROČNO pisan,
  model izvožen za Node: tools/test_drva.mjs) računa porabo. Brez JS stran kalkulatorja ne kaže.
- Poraba je sorazmerna s stopinjskimi dnevi: poenostavitev (topla voda, sončni dobitki, način ogrevanja). ORIENTACIJSKO, ne obračun.
- Energija v prostorninskem metru (prm): 500 kg na prm (predpis, Uradni list RS 14/2017) × ~4 kWh/kg pri 20 % vlage, vsakih 10 %
  vode zmanjša kurilno vrednost za ~12 % (občinski priročnik »Les kot energent za ogrevanje«, Lendava). Drevesnih vrst ne ločimo.
  Potrebe po toploti (kWh/m²·leto) so ocene; samo »nizkoenergijska < 35« je iz literature. Izkoristek peči 75 % je naša predpostavka.
- Stran se osvežuje dnevno (seo-smart-routine.yml), da kaže letošnjo sezono do včeraj.
- Notranjih meritev ne uporablja (samo zunanja tempAvg).

Usage:
  python3 tools/generate_drva_page.py
"""
import datetime
import hashlib
import html as _html
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(ROOT, "history.json")
JS_PATH = os.path.join(ROOT, "zima", "poraba-drv", "drva.js")
URL = "/zima/poraba-drv/"
COMPLETE = [2020, 2021, 2022, 2023, 2024]        # popolne sezone (kot v članku o stopinjskih dneh)
LAST_SEASON = 2025                               # 2025/26: manjkajo 4 dnevi, samo kot izbira »lanske« sezone
BASE, ROOM = 12.0, 20.0
MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
       "novembra", "decembra"]

PRESETS = [("", "Izberite (ali vpišite sami)"),
           ("35", "Nizkoenergijska novogradnja (okoli 35)"),
           ("70", "Novejša, dobro izolirana (okoli 70)"),
           ("150", "Starejša, delno obnovljena (okoli 150)"),
           ("220", "Stara, slabo izolirana (okoli 220)")]
DRY = [("suha", "Suha (okoli 20 % vlage)", 2000), ("polsuha", "Polsuha (okoli 30 %)", 1760), ("sveza", "Sveža (okoli 40 %)", 1550)]


def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    return {datetime.date.fromisoformat(k): v for k, v in H.items() if v.get("src") != "era5"}


def hdd(days, d):
    t = (days.get(d) or {}).get("tempAvg")
    return None if t is None else (ROOM - t if t < BASE else 0.0)


def season_days(y, end=None):
    a, b = datetime.date(y, 10, 1), datetime.date(y + 1, 4, 30)
    if end:
        b = min(b, end)
    d = a
    while d <= b:
        yield d
        d += datetime.timedelta(1)


def curve(days, y, end=None):
    cum, out, missing = 0.0, [], 0
    for d in season_days(y, end):
        h = hdd(days, d)
        if h is None:
            missing += 1
            h = 0.0
        cum += h
        out.append(round(cum, 1))
    return out, missing


def dlong(d):
    return f"{d.day}. {MES[d.month]}"


def num(x, dec=0):
    return f"{x:.{dec}f}".replace(".", ",")


def build_data(days):
    last = max(days)
    curves, totals = {}, {}
    for y in COMPLETE:
        c, miss = curve(days, y)
        assert miss <= 1, (y, miss)                               # 2020/21: 1 dan brez meritve (kot v članku: seštevek po razpoložljivih dneh)
        curves[str(y)], totals[str(y)] = c, round(c[-1])
    assert [totals[str(y)] for y in COMPLETE] == [3156, 3281, 2781, 2565, 2817], totals     # enako kot članek o stopinjskih dneh
    c25, miss25 = curve(days, LAST_SEASON)
    assert round(c25[-1]) == 2877 and miss25 == 4, (round(c25[-1]), miss25)
    totals_all = dict(totals)
    totals_all[str(LAST_SEASON)] = round(c25[-1])
    mean = statistics.mean(totals.values())
    assert round(mean) == 2920
    labels = {str(y): f"{y}/{str(y + 1)[2:]}" for y in COMPLETE + [LAST_SEASON]}
    # letošnja sezona do zadnjega dne s podatkom
    this_y = last.year if last.month >= 10 else last.year - 1
    c26, miss26 = curve(days, this_y, end=last)
    idx = len(c26)                                            # dni od 1. 10. do zadnjega dne vključno
    typ = statistics.mean(curves[str(y)][idx - 1] for y in COMPLETE) if 0 < idx <= min(len(c) for c in curves.values()) else None
    this = {"sezona": this_y, "do": last.isoformat(), "hdd": round(c26[-1], 1) if c26 else 0, "typ": round(typ, 1) if typ else None,
            "manjka": miss26}
    return {"curves": curves, "totals": totals, "totalsAll": totals_all, "labels": labels, "mean": round(mean, 1),
            "nSeasons": len(COMPLETE), "this": this}


def faq():
    return [
        ("Kaj je stopinjski dan?",
         "Dan s povprečno temperaturo pod 12 °C prispeva razliko do 20 °C (dan s povprečjem 2 °C prispeva 18 stopinjskih dni), dan s povprečjem 12 °C ali več nič. "
         "Seštevek po sezoni (1. oktober–30. april) pove, kako hladna je bila zima. Poraba za ogrevanje je približno sorazmerna z njim. "
         "Podrobneje o podatkih iz Rečice piše članek o stopinjskih dneh."),
        ("Kako natančen je izračun?",
         "Orientacijski. Način A (lanska poraba) je natančnejši, ker vsebuje vašo hišo, peč in navade; vremensko razliko doda s stopinjskimi dnevi. "
         "Način B (iz hiše) temelji na ocenah potrebe po toploti in izkoristka peči. Tople vode, sončnih dobitkov in izgub peči ne modeliramo. "
         "Zimo, ki bo hladnejša ali toplejša od vseh petih, kalkulator ne zajame."),
        ("Koliko energije je v prostorninskem metru drv?",
         "Prostorninski meter (prm) je kubični meter zloženih polen. Predpis iz Uradnega lista RS (št. 14/2017) ga šteje za 500 kg. "
         "Suha drva (okoli 20 % vlage) imajo okoli 4 kWh na kilogram, vsakih 10 % več vode pa kurilno vrednost zmanjša za okoli 12 % (priročnik »Les kot energent za ogrevanje«). "
         "To je okoli 2000 kWh na prm za suha, 1760 za polsuha in 1550 za sveža drva. Kalkulator pri vlažnejših drvih teže ne spreminja, zato je ocena grob približek. "
         "Težji les (bukev, hrast) ima običajno več energije v prm kot mehek, a razlik v virih nismo preverili, zato vrst ne ločimo. Energijo lahko vpišete sami."),
        ("Zakaj pet sezon in ne več?",
         "Postaja IREICA1 meri od novembra 2019. Sezona 2019/20 je nepopolna, sezona 2025/26 ima 4 manjkajoče dni (2877 stopinjskih dni), zato je med scenariji nismo uporabili; "
         "lahko pa jo izberete kot »lansko« zimo. Pet sezon je malo: najtoplejša in najhladnejša nista meja možnega."),
        ("Kaj pomeni »od danes do 30. 4.«?",
         "Del zime, ki je pred nami: od vrednosti sezone odštejemo stopinjske dni od 1. oktobra do včeraj, kot so se nabrali v vsaki od petih sezon. "
         "Stalni del porabe (topla voda), če ga vpišete, razporedimo enakomerno čez sezono."),
        ("Je to za obračun ali nasvet o ogrevanju?",
         "Ne. Je ocena količine drv za načrtovanje nakupa. Za dimenzioniranje peči, energetsko izkaznico in subvencije se obrnite na strokovnjaka."),
    ]


def build_body(data, js_ver):
    th = data["this"]
    last = datetime.date.fromisoformat(th["do"])
    season_lbl = f"{th['sezona']}/{str(th['sezona'] + 1)[2:]}"
    if th["typ"]:
        diff = 100 * (th["hdd"] / th["typ"] - 1)
        cmp_txt = (f"V petih prejšnjih sezonah se jih je do tega dne nabralo povprečno {num(th['typ'])}, letos je za {num(abs(diff))} % "
                   f"{'več (hladneje)' if diff > 0 else 'manj (topleje)'}.")
    else:
        cmp_txt = ""
    miss_txt = f" Manjka {th['manjka']} dni meritev." if th["manjka"] else ""
    this_html = (f'<p class="archive-intro"><b>Letošnja zima ({season_lbl}) do {dlong(last)}: {num(th["hdd"])} stopinjskih dni.</b> '
                 f'{cmp_txt}{miss_txt}</p>')
    base_opts = "".join(f'<option value="{y}"{" selected" if y == str(LAST_SEASON) else ""}>zima {data["labels"][y]} ({num(t)} stopinjskih dni)</option>'
                        for y, t in sorted(data["totalsAll"].items()))
    preset_opts = "".join(f'<option value="{v}">{_html.escape(l)}</option>' for v, l in PRESETS)
    dry_opts = "".join(f'<option value="{k}">{_html.escape(l)}</option>' for k, l, _ in DRY)
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in faq()) + "\n  </div>"
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Zima", "/zima/"), ("Poraba drv", None)])}
  <h1 class="page-title">Koliko drv potrebujem za zimo? Kalkulator</h1>
  <p class="post-meta">Po stopinjskih dneh iz meritev postaje v Rečici · orientacijski izračun</p>
  <p class="archive-intro">Poraba za ogrevanje je približno sorazmerna s hladnostjo zime. Iz meritev postaje IREICA1 za pet popolnih zim izračunam
  tri scenarije: kot najtoplejša, povprečna in kot najhladnejša zima. Če poznate lansko porabo, jo preračunam; sicer ocenim iz hiše.
  To je ocena za načrtovanje nakupa, ne obračun. Več o stopinjskih dneh v <a href="/blog/stopinjski-dnevi-recica-koliko-kuriti-1027.html">članku</a>;
  za jutrišnje vreme poglejte <a href="/zima/">zimske strani</a>.</p>
  {this_html}
  <style>
  .dr-form{{display:grid;gap:.8rem;max-width:34rem}}
  .dr-form label{{display:grid;gap:.25rem;font-weight:600;font-size:.95rem}}
  .dr-form input,.dr-form select{{min-height:44px;padding:.4rem .6rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem;font-weight:400}}
  .dr-form[hidden]{{display:none}}
  .dr-mode{{display:flex;flex-wrap:wrap;gap:.5rem}}
  .dr-mode label{{display:inline-flex;grid-template-columns:none;align-items:center;gap:.4rem;min-height:44px;padding:0 .9rem;border:1px solid var(--card-border,var(--border));border-radius:99px;cursor:pointer;font-weight:600}}
  .dr-two{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}}
  .dr-two>*{{min-width:0}}
  .dr-form input,.dr-form select{{width:100%;max-width:100%;min-width:0;box-sizing:border-box}}
  .dr-form input[type=radio]{{width:auto;min-height:0}}
  @media(max-width:480px){{.dr-two{{grid-template-columns:1fr}}}}
  .dr-note{{font-weight:400;font-size:.8rem;color:var(--muted)}}
  .dr-res table{{border-collapse:collapse;width:100%;font-size:.9rem}}
  .dr-res th,.dr-res td{{padding:.45rem .5rem;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}}
  .dr-res th:first-child,.dr-res td:first-child{{text-align:left;white-space:normal}}
  .dr-res thead th{{font-size:.78rem;color:var(--muted);font-weight:600}}
  .dr-res{{overflow-x:auto;max-width:100%}}
  .vs-note{{color:var(--muted);font-size:.82rem;line-height:1.5}}
  </style>
  <div class="card" style="margin:1rem 0">
    <div class="clabel">Kalkulator</div>
    <form id="dr-form" class="dr-form" novalidate>
      <div class="dr-mode" role="radiogroup" aria-label="Način izračuna">
        <label><input type="radio" name="dr-mode" value="a" checked> Poznam lansko porabo</label>
        <label><input type="radio" name="dr-mode" value="b"> Ocenim iz hiše</label>
      </div>
      <div id="dr-a" class="dr-form">
        <div class="dr-two">
          <label>Poraba drv (prm)<input id="dr-last" type="number" inputmode="decimal" min="0" step="0.5" placeholder="npr. 10"></label>
          <label>V kateri zimi<select id="dr-base">{base_opts}</select></label>
        </div>
        <label>Del porabe, ki ni odvisen od vremena (%)<input id="dr-fixed" type="number" inputmode="numeric" min="0" max="60" step="5" value="0">
          <span class="dr-note">npr. topla voda in kuhanje na drva; če ga ne poznate, pustite 0.</span></label>
      </div>
      <div id="dr-b" class="dr-form" hidden>
        <div class="dr-two">
          <label>Ogrevana površina (m²)<input id="dr-area" type="number" inputmode="decimal" min="1" step="5" value="120"></label>
          <label>Izkoristek peči (%)<input id="dr-eff" type="number" inputmode="numeric" min="30" max="100" step="5" value="75"></label>
        </div>
        <label>Tip hiše<select id="dr-preset">{preset_opts}</select></label>
        <label>Potrebna toplota (kWh/m² na leto)<input id="dr-q" type="number" inputmode="decimal" min="1" step="5" value="150">
          <span class="dr-note">toplota, ki jo hiša potrebuje v povprečni zimi; vrednosti v meniju so orientacijske ocene.</span></label>
        <div class="dr-two">
          <label>Drva<select id="dr-dry">{dry_opts}</select></label>
          <label>Energija v 1 prm (kWh)<input id="dr-kwh" type="number" inputmode="numeric" min="500" step="50" value="2000"></label>
        </div>
      </div>
      <div class="dr-two">
        <label>Rezerva (%)<input id="dr-rez" type="number" inputmode="numeric" min="0" max="50" step="5" value="10"></label>
        <label>Cena za prm (€, neobvezno)<input id="dr-price" type="number" inputmode="decimal" min="0" step="5"></label>
      </div>
    </form>
    <div id="dr-msg" class="vs-note" aria-live="polite" style="min-height:1.2em"></div>
  </div>
  <h2>Koliko prostorninskih metrov</h2>
  <div class="dr-res" id="dr-out" aria-live="polite"><p class="archive-intro">Vpišite podatke.</p></div>
  <noscript><p class="archive-intro">Kalkulator potrebuje JavaScript.</p></noscript>
  <p class="vs-note">Prostorninski meter (prm) je kubični meter zloženih polen. Račun predpostavlja, da je poraba sorazmerna s stopinjskimi dnevi (dan pod 12 °C prispeva 20 − T)
  v kurilni sezoni 1. 10.–30. 4. Pet sezon je malo: zima je lahko hladnejša od najhladnejše v tabeli. Vir meritev: postaja IREICA1 (zunanji senzor).
  Energija v drvih: 500 kg na prm (Uradni list RS, št. 14/2017) in okoli 4 kWh/kg pri 20 % vlage, vsakih 10 % vode okoli 12 % manj
  (<a href="https://lendava.e-obcina.si/Files/TextContent/76/1613036266552_Les%20kot%20energent%20za%20ogrevanje.pdf">Les kot energent za ogrevanje</a>).</p>
{faq_html}
  <a class="back-link" href="/zima/">← Zima v dolini</a>
<script type="application/json" id="drva-data">{blob}</script>
<script src="{URL}drva.js?v={js_ver}" defer></script>'''


def main():
    days = load()
    data = build_data(days)
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Koliko drv za zimo? Kalkulator po stopinjskih dneh"
    desc = ("Kalkulator porabe drv: iz lanske porabe ali velikosti hiše izračuna prostorninske metre za toplo, povprečno in hladno zimo "
            "po meritvah stopinjskih dni v Rečici.")
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
        seo.crumbs_schema([("Meteorec", "/"), ("Zima", "/zima/"), ("Poraba drv", None)]),
        seo.faq_schema(faq()),
    ])
    page = seo.page_shell(title, desc, URL, schema, build_body(data, js_ver))
    seo.write_page("zima/poraba-drv/index.html", page, force=True)
    print("  → zima/poraba-drv/index.html")


if __name__ == "__main__":
    main()
