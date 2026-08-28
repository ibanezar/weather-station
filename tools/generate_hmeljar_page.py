#!/usr/bin/env python3
"""
tools/generate_hmeljar_page.py — /meteohmeljar/: interaktivna karta hmeljišč.

MeteoHmeljar je za VSE hmeljarje v dolini, ne eno znano gospodarstvo — zato ni
(več) seznama parcel v repozitoriju. Namesto tega karta (Leaflet + OSM, isti
vzorec/SRI kot meteogasilec/karta/) prikaže hmeljiške parcele iz uradnega
MKGP GIS sloja RABA (RABA_ID=1160) za Zgornjo Savinjsko dolino, prek Worker
proxyja `/hmeljar-raba` (geohub.gov.si ne pošilja Access-Control-Allow-Origin,
zato ga brskalnik ne sme brati neposredno — isto načelo kot /varpolje-current
v worker.js). Klik na parcelo izračuna SprayScore/PeronosporaRisk/
PepelovkaRisk/WaterBalance/StormRisk CLIENT-SIDE v meteohmeljar/hmeljar.js —
strežniško vnaprej generirati stran za VSAKO možno kliknjeno parcelo v dolini
ni izvedljivo.

Ta stran je zato POVSEM STATIČNA (isto kot meteogasilec/karta/) — generator se
požene enkrat (ali ob spremembi predloge), ne na cron urniku; zato tudi ni
delavnega toka .github/workflows/*.yml zanjo.

tools/hmeljar_model.py ostaja referenčna Python implementacija istih formul
(berljiva specifikacija + osnova za teste) — meteohmeljar/hmeljar.js jih
namerno podvoji v JS, ker Python v brskalniku ne teče (isto načelo kot
gasilec_model.py/app.js/gasilec.js, glej opombo na vrhu gasilec_model.py).
Ker ni strežniškega cron teka na kliknjeno točko, hmeljar.js nima dostopa do
vztrajnega dnevnika: WaterBalance kumulativni primanjkljaj zato računa iz
enega daljšega Open-Meteo okna (60 pretečenih dni) namesto iz shranjenega
stanja, PeronosporaRisk/PepelovkaRisk pa (za zdaj) ne kažeta dnevnega trenda.

Usage:
  python3 tools/generate_hmeljar_page.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

LEAFLET_CSS = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" '
               'integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">'
               '<style>#hm-map{height:440px;border-radius:1rem;overflow:hidden;margin:.8rem 0;'
               'border:1px solid var(--card-border)}</style>')

DESC = ("Interaktivna karta hmeljišč Zgornje Savinjske doline (uradni MKGP GIS sloj) — klikni parcelo za "
        "škropilno okno, tveganje za peronosporo/pepelovko, vodno bilanco in nevarnost neurja na tisti točki.")


def build_page():
    inner = f'''  <p class="post-meta">{DESC}</p>
  <div id="hm-map"></div>
  <p class="gf-note" id="hm-map-note">Nalagam hmeljišča …</p>
  <div id="hm-dashboard"></div>
  <p class="muted-note">Meje parcel so iz javnega sloja rabe tal (MKGP RABA), ne evidence lastništva — preveri, da je
  izbrana parcela res tvoja, preden se odločaš po njej. Meteorološko okno za škropljenje je ocena, ne navodilo — nikoli
  ne preglasi registracije, etikete ali navodil konkretnega fitofarmacevtskega sredstva.</p>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script src="/meteohmeljar/hmeljar.js"></script>'''

    crumbs = [("Meteorec", "/"), ("MeteoHmeljar", None)]
    schema = "\n".join([
        seo.webpage_schema("/meteohmeljar/", "MeteoHmeljar", DESC),
        seo.crumbs_schema(crumbs),
    ])
    body = f'''{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">MeteoHmeljar</h1>
{inner}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    html = seo.page_shell("MeteoHmeljar — karta hmeljišč", DESC, "/meteohmeljar/",
                           schema + "\n" + LEAFLET_CSS, body)
    seo.write_page("meteohmeljar/index.html", html, force=True)


def main():
    build_page()
    print("→ meteohmeljar/index.html")


if __name__ == "__main__":
    main()
