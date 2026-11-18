#!/usr/bin/env python3
"""
tools/generate_elektrarna_page.py — /sonce-elektrarna/ »Napoved proizvodnje sončne elektrarne« (18. 11. 2026)

Ovoj za sonce-elektrarna/elektrarna.js (ROČNO pisan, model izvožen za Node: tools/test_elektrarna.mjs). Brskalnik pokliče Open-Meteo `global_tilted_irradiance`
za Rečico z izbranim naklonom in azimutom (0 = jug) in izračuna energijo = Σ sevanje/1000 × kWp × PR. PR (učinkovitost sistema, privzeto 80 %) je moja
predpostavka (izgube razsmernika, kablov, temperature, umazanije) in je spremenljiv; sence, snega na modulih in omejitev razsmernika ne upošteva. To je ocena iz
MODELSKE napovedi, ne meritev postaje in ne garancija. Postaja IREICA1 sevanje meri, a ga ta stran ne primerja (v history.json je samo dnevni maksimum).
Ni v workflowu. Notranjih meritev ne uporablja.
"""
import hashlib
import html as _html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(ROOT, "sonce-elektrarna", "elektrarna.js")
URL = "/sonce-elektrarna/"

FAQ = [
    ("Kako je izračunana proizvodnja?", "Open-Meteo napove sevanje na nagnjeno ploskev (naklon in smer, ki ju vnesete). Energija je vsota urnih vrednosti v kWh/m² × moč sistema (kWp) × učinkovitost sistema (privzeto 80 %)."),
    ("Zakaj učinkovitost 80 %?", "To je moja predpostavka za običajen sistem (izgube razsmernika, kablov, temperature in umazanije). Vaš sistem je lahko boljši ali slabši; vrednost lahko spremenite."),
    ("Kaj ocena ne upošteva?", "Sence stavb in dreves, sneg na modulih, omejitev moči razsmernika in staranje modulov. Pozimi je ocena zato lahko občutno previsoka."),
    ("Ali je to meritev ali napoved?", "Napoved iz modela Open-Meteo za Rečico ob Savinji, ne meritev vaše elektrarne in ne meritev postaje."),
]


def main():
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Napoved proizvodnje sončne elektrarne za Rečico"
    desc = "Koliko kWh bo v naslednjih 7 dneh proizvedla vaša sončna elektrarna v Zgornji Savinjski dolini? Vnesite moč, naklon in smer; ocena iz napovedi sevanja."
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Sončna elektrarna", None)])}
  <h1 class="page-title">Napoved proizvodnje sončne elektrarne</h1>
  <p class="post-meta">Ocena za 7 dni iz napovedi sevanja Open-Meteo za Rečico ob Savinji</p>
  <p class="archive-intro">Vnesite moč elektrarne, naklon in smer streh: pokazal bom, koliko kWh lahko pričakujete vsak dan v naslednjem tednu. To je ocena iz modelske napovedi, ne garancija.</p>
  <style>
  .el-f{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem;max-width:34rem}} .el-f label{{display:grid;gap:.25rem;font-weight:600;font-size:.95rem;min-width:0}}
  .el-f input{{width:100%;min-width:0;box-sizing:border-box;min-height:44px;padding:.4rem .6rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem;font-weight:400}}
  .el-f button{{grid-column:1/-1;min-height:44px}} @media(max-width:480px){{.el-f{{grid-template-columns:1fr}}}}
  .el-row{{display:grid;grid-template-columns:3.2rem minmax(0,1fr) 6.5rem;gap:.6rem;align-items:center;margin:.35rem 0}}
  .el-w{{height:.9rem;border-radius:6px;background:var(--card-bg);border:1px solid var(--border);overflow:hidden}} .el-bar{{height:100%;background:var(--accent,#2f7d5b)}} .el-v{{text-align:right;font-variant-numeric:tabular-nums}}
  </style>
  <form id="el-form" class="el-f">
    <label>Moč (kWp)<input id="el-kwp" type="text" inputmode="decimal" value="5"></label>
    <label>Naklon streh (°)<input id="el-tilt" type="number" min="0" max="90" step="1" value="35"></label>
    <label>Smer (0 = jug, −90 vzhod, 90 zahod)<input id="el-az" type="number" min="-180" max="180" step="5" value="0"></label>
    <label>Učinkovitost sistema (%)<input id="el-pr" type="number" min="50" max="95" step="1" value="80"></label>
    <button type="submit" class="btn">Izračunaj</button>
  </form>
  <div id="el-msg" class="vs-note" aria-live="polite" style="min-height:1.2em"></div>
  <div id="el-out" aria-live="polite" style="margin:1rem 0;max-width:34rem"></div>
  <noscript><p class="archive-intro">Orodje potrebuje JavaScript.</p></noscript>
  <p class="vs-note">Vir: Open-Meteo (global_tilted_irradiance) za koordinate postaje. Ocena ne upošteva senc, snega in omejitve razsmernika. Vnos ostane v vašem brskalniku.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script src="{URL}elektrarna.js?v={js_ver}" defer></script>'''
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
                        seo.crumbs_schema([("Meteorec", "/"), ("Sončna elektrarna", None)]), seo.faq_schema(FAQ)])
    seo.write_page("sonce-elektrarna/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print("  → sonce-elektrarna/index.html")


if __name__ == "__main__":
    main()
