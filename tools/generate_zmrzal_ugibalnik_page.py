#!/usr/bin/env python3
"""
tools/generate_zmrzal_ugibalnik_page.py — /ugibalnik-zmrzal/ (19. 11. 2026)

Ugibalnik »Kdaj bo prva zmrzal?«: obiskovalec ugiba datum, ko bo postaja IREICA1 v Rečici ob Savinji prvič (od 1. septembra) izmerila najnižjo
temperaturo dneva <= 0 °C. Resnica je dogodek `prva-zmrzal-<sezona>` v novosti.json (detect_events() v tools/seo_smart_routine.py), ki ga
tools/zmrzal_ugibalnik_resolve.py prepiše v data/zmrzal-ugibalnik.json. Šteje zmrzal (zrak <= 0 °C), ne slana (led na površini): postaja meri
zrak, zato stran tega ne meša.

- Ovoj in besedilo piše ta generator; obrazec, statistiko in lestvico izriše ISTA ročno pisana datoteka kot pri snežnem ugibalniku
  (zima/sneg-ugibalnik/ugibalnik.js; nastavitve so atributi data-* na #ug-app). Ugibi so na workerju (/zmrzal/ugibanje, /zmrzal/ugibanja).
- Sezona se NE zapiše v stran: JS jo izračuna iz datuma (začne se 1. avgusta), razreševalnik teče dnevno, zato se stran ob prehodu sezone
  ne sme regenerirati. Generator osveži samo klimatologijo (po koncu sezone ali ob večji posodobitvi history.json): ROČNO, ni v workflowu.
- Klimatologija (prva zmrzal po jesenih 2020–) je izračunana iz history.json (samo meritve postaje, dnevi `src != era5`); nič ni vtipkano.
  Postaja meri od novembra 2019, zato je prva celotna jesen 2020. Jesen brez izmerjene zmrzali do 31. 12. se ne šteje med datume.
- Ugibalnik je zabava (brez nagrad); lestvica je v brskalniku iz javnega seznama ugibov (brez id-jev).

Usage:
  python3 tools/generate_zmrzal_ugibalnik_page.py
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
URL = "/ugibalnik-zmrzal/"
HISTORY = os.path.join(ROOT, "history.json")
JS_PATH = os.path.join(ROOT, "zima", "sneg-ugibalnik", "ugibalnik.js")
JS_URL = "/zima/sneg-ugibalnik/ugibalnik.js"
STATE_URL = "/data/zmrzal-ugibalnik.json"
FIRST_SEASON = 2020
MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
       "novembra", "decembra"]
TXT = {
    "share": "Moj ugib za prvo zmrzal v Rečici ob Savinji: {d}. Kdaj bo po vašem? {url}",
    "label": "Datum, ko bo v Rečici ob Savinji prvič (od 1. septembra) izmerjena zmrzal (najnižja temperatura dneva 0 °C ali manj)",
    "closed": "Ugibanje je zaprto: prva zmrzal je že bila.",
    "closedEnd": "Ugibanje je zaprto. Nova igra se začne 1. avgusta.",
    "locked": " Ugib je zaklenjen. Lestvica bo znana, ko postaja IREICA1 prvič izmeri najnižjo temperaturo dneva 0 °C ali manj.",
    "mine": "Vaš ugib: {d}.",
    "result": "Prva zmrzal je bila {d}.",
    "winner": " Zmagal je ugib z najmanjšo razliko v dneh.",
    "late": "Vaš ugib je bil oddan po prvi zmrzali in se ne šteje.",
    "none": "Prve zmrzali letos postaja še ni izmerila (najnižja temperatura dneva še ni bila 0 °C ali manj).",
    "state": "Prva zmrzal: {d}.",
    "noEvent": "Do konca decembra zmrzali ni bilo ali ugibanje še ni odprto: nova igra se začne 1. avgusta.",
}


def dlong(d):
    return f"{d.day}. {MES[d.month]}"


def first_frost_by_season():
    """[(sezona, datum, tempLow)] = prvi dan od 1. 9. do 31. 12. z najnižjo temperaturo <= 0 °C (samo meritve postaje, brez ERA5)."""
    h = json.load(open(HISTORY, encoding="utf-8"))
    today = datetime.date.today()
    out = []
    for y in range(FIRST_SEASON, today.year + 1):
        end = f"{y}-12-31"
        days = sorted(d for d in h if f"{y}-09-01" <= d <= end and h[d].get("src") != "era5")
        if not days:
            continue
        have = [d for d in days if h[d].get("tempLow") is not None]
        first = next((d for d in have if h[d]["tempLow"] <= 0), None)
        if not first:
            continue
        # pokritost: dnevi do prvega datuma morajo biti izmerjeni (sicer »prva v podatkih, ki jih imamo«)
        span = (datetime.date.fromisoformat(first) - datetime.date(y, 9, 1)).days + 1
        assert sum(1 for d in have if d <= first) >= 0.95 * span, (y, "podatki do prve zmrzali imajo luknje")
        out.append((y, datetime.date.fromisoformat(first), h[first]["tempLow"]))
    return out


def faq(n):
    return [
        ("Kaj šteje za prvo zmrzal?",
         "Prvi dan od 1. septembra, ko postaja IREICA1 v Rečici ob Savinji (366 m) izmeri najnižjo temperaturo dneva 0 °C ali manj. "
         "To je isti pogoj kot na strani Novosti (Prva zmrzal sezone). Šteje temperatura zraka, ne slana: slana je led na površini in je "
         "lahko tudi pri plusu."),
        ("Kdaj se igra začne in konča?",
         "Odpre se 1. avgusta. Ugibate lahko datum od 1. septembra do 31. decembra. Ko postaja prvič izmeri zmrzal, se ugibanje zapre. "
         "Če do konca decembra zmrzali ni, zmagovalca ni."),
        ("Kako se določi zmagovalec?",
         "Zmaga ugib z najmanjšo razliko v dneh od dejanskega datuma. Pri izenačenju zmaga prej oddan ugib. "
         "Ugibi, oddani na dan zmrzali ali po njej, se ne štejejo. Ugibalnik je zabava, brez nagrad."),
        ("Ali lahko ugib spremenim?",
         "Ne, ugib je zaklenjen. Račun ni potreben: brskalnik si zapomni naključno oznako, zato je en ugib mogoč na brskalnik. "
         "Kdor izbriše podatke brskalnika, lahko ugiba znova, zato je lestvica le igra, ne uradni izid."),
        ("Kdaj bo rezultat znan?",
         "Ko postaja izmeri zmrzal. Zaznavo poganjamo vsak dan, zato se rezultat pojavi do dan ali dva pozneje."),
        ("Kaj shranite o meni?",
         "Datum vašega ugiba, čas oddaje, neobvezen vzdevek in naključno oznako brskalnika. Naslova IP v zapisu ni; za omejitev zlorab strežnik "
         "do 24 ur hrani števec oddaj po naslovu IP, ki se sam izbriše. Vzdevek je javen, zato ne vpisujte pravega imena, če tega ne želite."),
        ("Kaj pravijo pretekle jeseni?",
         "Spodnja tabela kaže prvi dan z zmrzaljo po jesenih od 2020. To so izmerjeni podatki postaje, ne napoved. "
         f"{n} jeseni je malo, zato razpon služi kot izhodišče, ne kot pravilo."),
    ]


def build_body(clim, js_ver):
    ys = [d for _, d, _ in clim]
    ordinal = [(d - datetime.date(d.year, 9, 1)).days for d in ys]
    med = datetime.date(ys[0].year, 9, 1) + datetime.timedelta(days=int(statistics.median(ordinal)))
    lo = min(ys, key=lambda d: (d - datetime.date(d.year, 9, 1)).days)
    hi = max(ys, key=lambda d: (d - datetime.date(d.year, 9, 1)).days)
    rows = "".join(f"<tr><td>{y}</td><td>{dlong(d)} {d.year}</td><td>{str(t).replace('.', ',')} °C</td></tr>" for y, d, t in clim)
    tbl = ('<div class="vs-tbl" tabindex="0" role="region" aria-label="Prva zmrzal po jesenih"><table><thead><tr><th>Jesen</th>'
           f'<th>Prva zmrzal</th><th>Najnižja</th></tr></thead><tbody>{rows}</tbody></table></div>')
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in faq(len(clim))) + "\n  </div>"
    txt = _html.escape(json.dumps(TXT, ensure_ascii=False), quote=True)
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Ugibalnik prve zmrzali", None)])}
  <h1 class="page-title">Kdaj bo prva zmrzal? Ugibalnik za Savinjsko dolino</h1>
  <p class="post-meta">Igra se odpre 1. avgusta · zabava brez nagrad</p>
  <p class="archive-intro">Izberite datum, ko bo postaja IREICA1 v Rečici ob Savinji od 1. septembra prvič izmerila najnižjo temperaturo dneva 0 °C ali manj.
  Zmaga ugib, ki je najbližje. Šteje zmrzal (zrak), ne slana. Za napoved poglejte <a href="/opozorilo-pred-pozebo/">opozorilo pred pozebo</a>
  in <a href="/sezona/">sezonski vodič</a>. Pozimi ugibamo še <a href="/zima/sneg-ugibalnik/">prvi sneg</a>.</p>
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
  <div id="ug-app" data-api="{WORKER_BASE}" data-state="{STATE_URL}" data-prefix="/zmrzal" data-key="prva_zmrzal" data-id-key="wx-zmrzal-ugib-id" data-moj-key="wx-zmrzal-ugib-moj" data-season-month="8" data-max-md="12-31" data-max-next="0" data-min-md="09-01" data-txt="{txt}">
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
  <h2>Kaj pravijo pretekle jeseni</h2>
  <p class="archive-intro">V Rečici je bila prva zmrzal (najnižja temperatura dneva 0 °C ali manj, od 1. septembra) v zadnjih {len(clim)} jesenih med
  {dlong(lo)} in {dlong(hi)}, srednji datum (mediana) je {dlong(med)}. To je izhodišče, ne napoved.</p>
  {tbl}
  <p class="vs-note">Vir: meritve postaje IREICA1 (najnižja temperatura dneva), od 1. septembra do 31. decembra vsake jeseni; postaja meri od novembra 2019.
  Postaja je amaterska in stoji na dnu doline, zato je zmrzal lahko drugje (višje, na grebenih) pozneje, v kotlinah prej.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script src="{JS_URL}?v={js_ver}" defer></script>'''


def main():
    clim = first_frost_by_season()
    assert len(clim) >= 5, clim
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Kdaj bo prva zmrzal? Ugibalnik za Savinjsko dolino"
    desc = ("Ugibajte datum prve zmrzali v Rečici ob Savinji (0 °C ali manj, od 1. septembra). Zmaga najbližji ugib. "
            "Pretekle jeseni kažejo, kdaj je zmrzal običajno prva.")
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published="2026-11-19"),
        seo.crumbs_schema([("Meteorec", "/"), ("Ugibalnik prve zmrzali", None)]),
        seo.faq_schema(faq(len(clim))),
    ])
    page = seo.page_shell(title, desc, URL, schema, build_body(clim, js_ver))
    seo.write_page("ugibalnik-zmrzal/index.html", page, force=True)
    print("  → ugibalnik-zmrzal/index.html")


if __name__ == "__main__":
    main()
