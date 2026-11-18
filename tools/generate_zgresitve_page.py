#!/usr/bin/env python3
"""
tools/generate_zgresitve_page.py — /zgresitve/ »Največje zgrešitve napovedi« (18. 11. 2026)

Iz forecast_verification.json (isti zapisi kot semafor /tocnost-napovedi/: napoved dan prej proti meritvi IREICA1) za vsak mesec izbere tri dni
z največjo absolutno napako katerega koli vira (ARSO, Open-Meteo, ECMWF AIFS, WeatherNext 2, MTR) pri najvišji ali najnižji temperaturi in pokaže vse
vire za ta dan. Samo mesece z vsaj 15 razrešenimi dnevi. Napaka je |napoved − meritev| iz polja err_*; vira se ne zlivata.
Pregled, kdo se je kdaj zmotil, ne ocena kakovosti: en dan ni povprečje (za to je /tocnost-napovedi/). Ni v workflowu; po koncu meseca poženi ročno.
ARSO je napoved za Ljubno ob Savinji (postaja ARSO), ne za Rečico; to piše pod tabelo.
"""
import datetime
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "/zgresitve/"
SOURCES = [("arso", "ARSO"), ("open_meteo", "Open-Meteo"), ("aifs", "ECMWF AIFS"), ("wn2", "WeatherNext 2"), ("meteorec", "MTR")]
MESECI = ["", "januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober", "november", "december"]
MIN_DAYS = 15
TOP = 3


def f1(x):
    return f"{x:.1f}".replace(".", ",").replace("-", "−")


def worst(rec):
    """(največja absolutna napaka, vir, spremenljivka) za dan."""
    best = None
    for key, name in SOURCES:
        s = rec.get(key) or {}
        for var in ("tmax", "tmin"):
            e = s.get("err_" + var)
            if e is not None and (best is None or abs(e) > best[0]):
                best = (abs(e), name, var)
    return best


def pick(V):
    by_month = {}
    for k, rec in V.items():
        a = rec.get("actual") or {}
        if a.get("tmax") is None or a.get("tmin") is None:
            continue
        w = worst(rec)
        if w:
            by_month.setdefault(k[:7], []).append((w, k, rec))
    out = {}
    for m, rows in sorted(by_month.items()):
        if len(rows) >= MIN_DAYS:
            out[m] = (len(rows), sorted(rows, key=lambda r: (-r[0][0], r[1]))[:TOP])
    return out


def day_table(rec):
    a = rec["actual"]
    head = "<tr><th></th><th>Najvišja</th><th>Najnižja</th></tr>"
    rows = [f'<tr class="zg-act"><th scope="row">Izmerjeno</th><td>{f1(a["tmax"])} °C</td><td>{f1(a["tmin"])} °C</td></tr>']
    for key, name in SOURCES:
        s = rec.get(key) or {}
        if s.get("tmax") is None and s.get("tmin") is None:
            continue
        def cell(var):
            v, e = s.get(var), s.get("err_" + var)
            if v is None:
                return "<td>—</td>"
            return f"<td>{f1(v)} °C" + (f' <span class="zg-e">({"+" if v - a[var] >= 0 else "−"}{f1(abs(v - a[var]))})</span>' if True else "") + "</td>"
        rows.append(f'<tr><th scope="row">{name}</th>{cell("tmax")}{cell("tmin")}</tr>')
    return f'<div class="zg-tbl" tabindex="0" role="region" aria-label="Napovedi in meritev"><table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def faq():
    return [
        ("Kako so izbrani dnevi?", "Za vsak mesec z vsaj 15 razrešenimi dnevi so izbrani trije dnevi z največjo absolutno napako katerega koli vira pri najvišji ali najnižji temperaturi."),
        ("Ali je vir z največjo napako najslabši?", "Ne. En dan ni povprečje. Dolgoročno primerjavo najdete na strani Točnost napovedi."),
        ("Za katero lokacijo je napoved ARSO?", "Za Ljubno ob Savinji (postaja ARSO), ostali viri za koordinate postaje v Rečici. Zato je primerjava za ARSO pošteno le v povprečju, ne po posameznih dnevih."),
    ]


def main():
    V = json.load(open(os.path.join(ROOT, "forecast_verification.json"), encoding="utf-8"))
    months = pick(V)
    assert months, "ni mesecev z dovolj dnevi"
    title = "Največje zgrešitve napovedi: dnevi, ko so se zmotili"
    desc = "Za vsak mesec trije dnevi z največjo napako napovedi (ARSO, Open-Meteo, AIFS, WeatherNext 2, MTR) proti meritvi postaje v Rečici ob Savinji."
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    sections = []
    for m in sorted(months, reverse=True):
        n, rows = months[m]
        y, mo = int(m[:4]), int(m[5:])
        items = []
        for (e, name, var), k, rec in rows:
            d = datetime.date.fromisoformat(k)
            what = "najvišji" if var == "tmax" else "najnižji"
            items.append(f'<article class="card zg-day"><h3>{d.day}. {d.month}. {d.year}</h3>'
                         f'<p><strong>{_html.escape(name)}</strong> se je zmotil za {f1(e)} °C pri {what} temperaturi.</p>{day_table(rec)}</article>')
        sections.append(f'<section><h2>{MESECI[mo].capitalize()} {y}</h2><p class="vs-note">{n} razrešenih dni.</p>{"".join(items)}</section>')
    fq = faq()
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in fq) + "\n  </div>"
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Točnost napovedi", "/tocnost-napovedi/"), ("Zgrešitve", None)])}
  <h1 class="page-title">Največje zgrešitve napovedi</h1>
  <p class="post-meta">Napoved dan prej proti meritvi postaje IREICA1</p>
  <p class="archive-intro">Napovedi se zmotijo, in vsak mesec se zmoti kdo drug. Za vsak mesec so tu trije dnevi z največjo napako. V oklepaju je odstopanje napovedi od meritve.
  Povprečno točnost virov najdete na strani <a href="/tocnost-napovedi/">Točnost napovedi</a>.</p>
  <style>
  .zg-day{{margin:.8rem 0}} .zg-tbl{{overflow-x:auto;max-width:100%}}
  .zg-tbl table{{border-collapse:collapse;width:100%;font-size:.9rem}}
  .zg-tbl th,.zg-tbl td{{padding:.35rem .5rem;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}}
  .zg-tbl th:first-child{{text-align:left}} .zg-act{{font-weight:700}} .zg-e{{color:var(--muted);font-size:.85em}}
  </style>
  {"".join(sections)}
  <p class="vs-note">Vir: forecast_verification.json (napoved, izdana dan prej, proti meritvi IREICA1). Napoved ARSO je za Ljubno ob Savinji. Postaja je amaterska in ni uradna meritev.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>'''
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
                        seo.crumbs_schema([("Meteorec", "/"), ("Točnost napovedi", "/tocnost-napovedi/"), ("Zgrešitve", None)]), seo.faq_schema(fq)])
    seo.write_page("zgresitve/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print(f"  → zgresitve/index.html ({len(months)} mesecev)")


if __name__ == "__main__":
    main()
