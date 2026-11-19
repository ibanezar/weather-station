#!/usr/bin/env python3
"""
tools/generate_sneg_ugibalnik_page.py — /zima/sneg-ugibalnik/ (18. 11. 2026)

Snežni ugibalnik »Kdaj bo prvi sneg?«: obiskovalec ugiba datum, ko bo na ARSO postaji Gornji Grad (428 m, 9 km od Rečice)
prvič ležal vsaj 1 cm snega. Resnica je dogodek `prvi-sneg-<sezona>` v novosti.json (detect_first_snow() v
tools/seo_smart_routine.py), ki ga tools/sneg_ugibalnik_resolve.py prepiše v data/sneg-ugibalnik.json.

- Ovoj in besedilo piše ta generator; obrazec, statistiko in lestvico izriše ročno pisan zima/sneg-ugibalnik/ugibalnik.js
  (model je izvožen za Node: tools/test_sneg.mjs). Ugibi so na workerju (/sneg/ugibanje, /sneg/ugibanja).
- Klimatologija (prvi dan z >= 1 cm po sezonah) je izračunana iz arhiva ARSO (data/arso-sneg-postaje/daily-1748.json);
  nič ni vtipkano. Višino odeje, ne novega snega, merimo enako kot stran /novosti/.
- Postaja IREICA1 snega ne meri: stran tega ne trdi; Gornji Grad je ARSO postaja, ne Rečica.
- Ugibalnik je zabava (brez nagrad); lestvica je v brskalniku iz javnega seznama ugibov (brez id-jev).

Usage:
  python3 tools/generate_sneg_ugibalnik_page.py
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
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"
URL = "/zima/sneg-ugibalnik/"
SEZONA = 2026
ARCHIVE = os.path.join(ROOT, "data", "arso-sneg-postaje", "daily-1748.json")
JS_PATH = os.path.join(ROOT, "zima", "sneg-ugibalnik", "ugibalnik.js")
STATE_URL = "/data/sneg-ugibalnik.json"
MIN_CM = 1.0                                  # kot SNOW_MIN_CM v seo_smart_routine.py
MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
       "novembra", "decembra"]


def dlong(d):
    return f"{d.day}. {MES[d.month]}"


def first_snow_by_season():
    """[(sezona, datum)] = prvi dan od 1. 10. do 30. 6. z višino odeje >= 1 cm v Gornjem Gradu (arhiv ARSO, ID 1748)."""
    rows = json.load(open(ARCHIVE, encoding="utf-8"))["days"]
    out = []
    for y in range(2019, SEZONA):
        lo, hi = f"{y}-10-01", f"{y + 1}-07-01"
        season = [r for r in rows if lo <= r[0] < hi]
        assert sum(1 for r in season if r[1] is not None) >= 0.95 * len(season), (y, "arhiv ima luknje")
        first = next((r[0] for r in season if r[1] is not None and r[1] >= MIN_CM), None)
        if first:
            out.append((y, datetime.date.fromisoformat(first)))
    return out


def faq():
    return [
        ("Kaj šteje za prvi sneg?",
         "Dan, ko ARSO postaja Gornji Grad (428 m, okoli 9 km od Rečice) prvič v sezoni, ki se začne 1. oktobra, izmeri višino snežne odeje vsaj 1 cm. "
         "To je isti pogoj kot na strani Novosti. Šteje višina odeje, ne novo zapadli sneg. Postaja IREICA1 v Rečici snega ne meri, zato je merilo ARSO."),
        ("Kako se določi zmagovalec?",
         "Zmaga ugib z najmanjšo razliko v dneh od dejanskega datuma. Pri izenačenju zmaga prej oddan ugib. "
         "Ugibi, oddani po prvem snegu, se ne štejejo. Ugibalnik je zabava, brez nagrad."),
        ("Ali lahko ugib spremenim?",
         "Ne, ugib je zaklenjen. Račun ni potreben: brskalnik si zapomni naključno oznako, zato je en ugib mogoč na brskalnik. "
         "Kdor izbriše podatke brskalnika, lahko ugiba znova, zato je lestvica le igra, ne uradni izid."),
        ("Kdaj bo rezultat znan?",
         "Ko ARSO v Gornjem Gradu zabeleži 1 cm snega. Našo zaznavo poganjamo vsak dan, arhiv ARSO pa zaostaja, zato se lahko rezultat pojavi z zamudo nekaj dni. "
         "Če podatkov za nekaj dni ni, stran to pove (datum je tedaj »prvi v podatkih, ki jih imamo«)."),
        ("Kaj shranite o meni?",
         "Datum vašega ugiba, čas oddaje, neobvezen vzdevek in naključno oznako brskalnika. Naslova IP v zapisu ni; za omejitev zlorab strežnik "
         "do 24 ur hrani števec oddaj po naslovu IP, ki se sam izbriše. Vzdevek je javen, zato ne vpisujte pravega imena, če tega ne želite."),
        ("Kaj pravijo pretekle zime?",
         "Spodnja tabela kaže prvi dan z vsaj 1 cm snega v Gornjem Gradu po zimah od 2019/20. To so izmerjeni podatki ARSO, ne napoved. "
         "Sedem zim je malo, zato razpon služi kot izhodišče, ne kot pravilo."),
    ]


def build_body(clim, js_ver):
    ys = [d for _, d in clim]
    ordinal = [(d - datetime.date(d.year, 10, 1)).days for d in ys]
    med = datetime.date(ys[0].year, 10, 1) + datetime.timedelta(days=int(statistics.median(ordinal)))
    lo, hi = min(ys, key=lambda d: (d - datetime.date(d.year, 10, 1)).days), max(ys, key=lambda d: (d - datetime.date(d.year, 10, 1)).days)
    rows = "".join(f"<tr><td>{y}/{str(y + 1)[2:]}</td><td>{dlong(d)} {d.year}</td></tr>" for y, d in clim)
    tbl = (f'<div class="vs-tbl" tabindex="0" role="region" aria-label="Prvi sneg po zimah"><table><thead><tr><th>Zima</th>'
           f'<th>Prvi dan z vsaj 1 cm snega</th></tr></thead><tbody>{rows}</tbody></table></div>')
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in faq()) + "\n  </div>"
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Zima", "/zima/"), ("Snežni ugibalnik", None)])}
  <h1 class="page-title">Kdaj bo prvi sneg? Ugibalnik za Savinjsko dolino</h1>
  <p class="post-meta">Zima {SEZONA}/{str(SEZONA + 1)[2:]} · zabava brez nagrad</p>
  <p class="archive-intro">Izberite datum, ko bo na ARSO postaji Gornji Grad (428 m) prvič ležal vsaj 1 cm snega. Zmaga ugib, ki je najbližje.
  Merilo je ARSO, ne postaja v Rečici, ker ta snega ne meri. Za napoved poglejte <a href="/zima/snezna-karta/">snežno karto</a>
  in <a href="/zima/">zimske strani</a>. Še en ugibalnik: <a href="/ugibalnik-zmrzal/">kdaj bo prva zmrzal</a>.</p>
  <style>
  .ug-form{{display:grid;gap:.7rem;max-width:26rem}}
  .ug-form label{{display:grid;gap:.25rem;font-weight:600}}
  .ug-form input{{min-height:44px;padding:.4rem .6rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem}}
  .ug-bars{{display:grid;gap:.3rem;margin:.6rem 0}}
  .ug-bar{{display:grid;grid-template-columns:3.6rem 1fr 1.8rem;gap:.5rem;align-items:center;font-size:.85rem}}
  .ug-bar-t{{display:block;height:.9rem;background:rgba(138,160,189,.18);border-radius:99px;overflow:hidden}}
  .ug-bar-t i{{display:block;height:100%;background:var(--blue,#3987e5);border-radius:99px}}
  .ug-bar-n{{text-align:right;color:var(--muted)}}
  .ug-rank{{padding-left:1.3rem;display:grid;gap:.3rem}}
  .vs-tbl{{overflow-x:auto;max-width:100%;margin:1rem 0}}
  .vs-tbl table{{border-collapse:collapse;width:100%;max-width:30rem;font-size:.9rem}}
  .vs-tbl th,.vs-tbl td{{padding:.42rem .5rem;text-align:left;border-bottom:1px solid var(--border)}}
  .vs-note{{color:var(--muted);font-size:.82rem;line-height:1.5}}
  </style>
  <div id="ug-app" data-api="{WORKER_BASE}" data-state="{STATE_URL}" data-sezona="{SEZONA}">
    <div class="card" style="margin-bottom:1rem">
      <div class="clabel">Vaš ugib</div>
      <p class="archive-intro" id="ug-stanje" aria-live="polite">Nalagam …</p>
      <div id="ug-form"></div>
      <div id="ug-msg" aria-live="polite" style="min-height:1.4em;font-size:.9rem;margin-top:.4rem"></div>
    </div>
    <h2>Kaj ugibajo drugi</h2>
    <div id="ug-stat" aria-live="polite"><p class="archive-intro">Nalagam …</p></div>
    <div id="ug-rang"></div>
  </div>
  <noscript><p class="archive-intro">Ugibalnik potrebuje JavaScript.</p></noscript>
  <h2>Kaj pravijo pretekle zime</h2>
  <p class="archive-intro">V Gornjem Gradu je prvi sneg (vsaj 1 cm) v zadnjih {len(clim)} zimah ležal med {dlong(lo)} in {dlong(hi)},
  srednji datum (mediana) je {dlong(med)}. To je izhodišče, ne napoved.</p>
  {tbl}
  <p class="vs-note">Vir: ARSO, višina snežne odeje, postaja Gornji Grad (arhiv meritev); od 1. oktobra do 30. junija vsake zime.</p>
{faq_html}
  <a class="back-link" href="/zima/">← Zima v dolini</a>
<script src="{URL}ugibalnik.js?v={js_ver}" defer></script>'''


def main():
    clim = first_snow_by_season()
    assert len(clim) == SEZONA - 2019, clim
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Kdaj bo prvi sneg? Ugibalnik za Savinjsko dolino"
    desc = ("Ugibajte datum prvega snega (vsaj 1 cm) v Gornjem Gradu. Zmaga najbližji ugib. "
            "Pretekle zime kažejo, kdaj je sneg v dolini običajno prvič obležal.")
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
        seo.crumbs_schema([("Meteorec", "/"), ("Zima", "/zima/"), ("Snežni ugibalnik", None)]),
        seo.faq_schema(faq()),
    ])
    page = seo.page_shell(title, desc, URL, schema, build_body(clim, js_ver))
    seo.write_page("zima/sneg-ugibalnik/index.html", page, force=True)
    print("  → zima/sneg-ugibalnik/index.html")


if __name__ == "__main__":
    main()
