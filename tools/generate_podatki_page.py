#!/usr/bin/env python3
"""
tools/generate_podatki_page.py — /podatki/ HTML-first data digest

Generates /podatki/index.html: a single, JS-free page with plain HTML
tables (current conditions, all-time records, monthly climate normals) and
short, self-contained, citable sentences — built for AI answer engines
(Google AI Overviews, ChatGPT, Perplexity) that don't render JavaScript and
prefer to quote a short, unambiguous fact with a source link.

This complements llms.txt (machine-readable site index) with a
human-and-machine-readable single-page fact sheet: the two together are
the site's GEO/AEO surface.

Usage:
  python3 tools/generate_podatki_page.py
"""
import os, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY


def monthly_normals(hist):
    """Povprečna dnevna maks./min. temperatura in povprečna letna vsota
    padavin za posamezni koledarski mesec — POVPREČJE dnevnih vrednosti,
    ne ekstrem (seo.month_stats vrača ekstreme znotraj serije, zato ni
    primeren za klimatološke norme)."""
    by_month = defaultdict(list)
    for d, v in hist.items():
        by_month[int(d[5:7])].append((d, v))
    rows = []
    for m in range(1, 13):
        entries = by_month.get(m, [])
        if len(entries) < 20:
            continue
        thigh = [v["tempHigh"] for _, v in entries if v.get("tempHigh") is not None]
        tlow = [v["tempLow"] for _, v in entries if v.get("tempLow") is not None]
        years = {d[:4] for d, _ in entries}
        total_precip = sum(v.get("precipTotal", 0) or 0 for _, v in entries)
        avg_tmax = st.mean(thigh) if thigh else None
        avg_tmin = st.mean(tlow) if tlow else None
        avg_precip = total_precip / len(years) if years else None
        rows.append((m, avg_tmax, avg_tmin, avg_precip))
    return rows


def build_body(hist, facts):
    last_date = max(hist.keys())
    last = hist[last_date]
    first_date = facts["first_date"]

    # ── Trenutne razmere ────────────────────────────────────────────────
    cur_rows = [
        ("Datum zadnje meritve", seo.fmtd(last_date)),
        ("Najvišja dnevna temperatura", f'{seo.num(last.get("tempHigh"))} °C' if last.get("tempHigh") is not None else "—"),
        ("Najnižja dnevna temperatura", f'{seo.num(last.get("tempLow"))} °C' if last.get("tempLow") is not None else "—"),
        ("Povprečna dnevna temperatura", f'{seo.num(last.get("tempAvg"))} °C' if last.get("tempAvg") is not None else "—"),
        ("Padavine", f'{seo.num(last.get("precipTotal", 0))} mm'),
        ("Povprečna relativna vlažnost", f'{seo.num(last.get("humidityAvg"), 0)} %' if last.get("humidityAvg") is not None else "—"),
        ("Najmočnejši sunek vetra", f'{seo.num(last.get("windgustHigh"))} km/h' if last.get("windgustHigh") is not None else "—"),
    ]
    cur_table = "  <table class=\"stats\">\n" + "\n".join(
        f'    <tr><th>{k}</th><td>{v}</td></tr>' for k, v in cur_rows
    ) + "\n  </table>"

    # ── Rekordi ─────────────────────────────────────────────────────────
    rec_rows = [
        ("Absolutno najvišja temperatura", f'{seo.num(facts["tmax_v"])} °C', seo.fmtd(facts["tmax_d"])),
        ("Absolutno najnižja temperatura", f'{seo.num(facts["tmin_v"])} °C', seo.fmtd(facts["tmin_d"])),
        ("Dnevni rekord padavin", f'{seo.num(facts["prec_v"])} mm', seo.fmtd(facts["prec_d"])),
        ("Najmočnejši izmerjeni sunek vetra", f'{seo.num(facts["wind_v"])} km/h', seo.fmtd(facts["wind_d"])),
    ]
    rec_table = "  <table class=\"stats\">\n" + "\n".join(
        f'    <tr><th>{k}</th><td>{v}</td><td>{d}</td></tr>' for k, v, d in rec_rows
    ) + "\n  </table>"

    # ── Klimatološke norme po mesecih ──────────────────────────────────
    norms = monthly_normals(hist)
    norm_rows = "\n".join(
        f'    <tr><th>{seo.MES_NOM[m].capitalize()}</th>'
        f'<td>{seo.num(tmax)} °C</td><td>{seo.num(tmin)} °C</td><td>{seo.num(prec, 0)} mm</td></tr>'
        for m, tmax, tmin, prec in norms
    )
    norm_table = ('  <table class="stats">\n'
                  '    <tr><th>Mesec</th><th>Povp. maks.</th><th>Povp. min.</th><th>Povp. padavine</th></tr>\n'
                  f'{norm_rows}\n  </table>')

    # ── Kratki, citabilni stavki ────────────────────────────────────────
    facts_list = [
        (f'Najvišja izmerjena temperatura na Rečici ob Savinji je {seo.num(facts["tmax_v"])} °C '
         f'({seo.fmtd(facts["tmax_d"])}), izmerjena na postaji IREICA1.'),
        (f'Najnižja izmerjena temperatura na Rečici ob Savinji je {seo.num(facts["tmin_v"])} °C '
         f'({seo.fmtd(facts["tmin_d"])}).'),
        (f'Dnevni rekord padavin na postaji IREICA1 znaša {seo.num(facts["prec_v"])} mm '
         f'({seo.fmtd(facts["prec_d"])}).'),
        (f'Povprečna letna količina padavin v Rečici ob Savinji je približno '
         f'{seo.num(facts["annual_precip"], 0)} mm.' if facts.get("annual_precip") is not None else ""),
        (f'Meteorološka postaja IREICA1 v Rečici ob Savinji (366 m n. m., 46,325779° S, 14,921137° V) '
         f'neprekinjeno meri vreme od {seo.fmtd(first_date)}.'),
        (f'Do {seo.fmtd(last_date)} je postaja IREICA1 zabeležila {facts["n_days"]} dni meritev.'),
    ]
    facts_list = [f for f in facts_list if f]
    facts_html = "  <ul class=\"muted-note\" style=\"list-style:disc;padding-left:1.2rem;line-height:1.8\">\n" + "\n".join(
        f'    <li>{f}</li>' for f in facts_list
    ) + "\n  </ul>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Podatki", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Podatki — Rečica ob Savinji (IREICA1)</h1>
  <p class="post-meta">Ena stran, samo HTML tabele — trenutne meritve, rekordi in klimatološke norme · {TODAY.isoformat()}</p>
  <p class="archive-intro">Meteorološka postaja IREICA1 pri Rečici ob Savinji (Zgornja Savinjska dolina, 366 m n. m.,
  46,325779° S, 14,921137° V) neprekinjeno meri vreme od {seo.fmtd(first_date)}. Ta stran zbira ključne podatke
  brez JavaScripta, za enostavno branje in citiranje. Polni arhiv je na <a href="/vreme/">/vreme/</a>,
  surovi podatki v <a href="/history.json">history.json</a> (CC BY 4.0 — navedi "Meteorec (meteorec.si), postaja IREICA1").</p>

  <h2>Trenutne razmere (zadnja znana dnevna meritev)</h2>
{cur_table}

  <h2>Vsi časi — rekordi</h2>
{rec_table}

  <h2>Klimatološke norme po mesecih</h2>
  <p class="archive-intro">Dolgoletno povprečje najvišje/najnižje dnevne temperature in mesečne količine
  padavin, izračunano iz vseh razpoložljivih let meritev na postaji IREICA1.</p>
{norm_table}

  <h2>Ključna dejstva</h2>
{facts_html}

  <h2>O postaji in podatkih</h2>
  <table class="stats">
    <tr><th>Oznaka postaje</th><td>{seo.STATION_ID}</td></tr>
    <tr><th>Lokacija</th><td>Rečica ob Savinji, Zgornja Savinjska dolina, Slovenija</td></tr>
    <tr><th>Koordinate</th><td>46,325779° S, 14,921137° V</td></tr>
    <tr><th>Nadmorska višina</th><td>{seo.ELEV} m</td></tr>
    <tr><th>Meritve od</th><td>{seo.fmtd(first_date)}</td></tr>
    <tr><th>Licenca</th><td>CC BY 4.0</td></tr>
    <tr><th>Strojno berljiv indeks</th><td><a href="/llms.txt">/llms.txt</a></td></tr>
  </table>

  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body


def main():
    hist = seo.load_history()
    facts = seo.climate_facts(hist) if hasattr(seo, "climate_facts") else None
    if facts is None:
        print("✗ generate_seo_pages.climate_facts ni na voljo", file=sys.stderr)
        sys.exit(1)

    body = build_body(hist, facts)

    url = "/podatki/"
    title = "Podatki — Rečica ob Savinji (IREICA1)"
    desc = ("Vremenski podatki Rečice ob Savinji brez JavaScripta: trenutne meritve, vsi časi rekordi in "
            "klimatološke norme po mesecih, postaja IREICA1, meritve od 2019.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-14"),
        seo.crumbs_schema([("Meteorec", "/"), ("Podatki", None)]),
    ])

    html_out = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("podatki/index.html", html_out, force=True)
    print(f"  → podatki/index.html ({facts['n_days']} dni meritev)")


if __name__ == "__main__":
    main()
