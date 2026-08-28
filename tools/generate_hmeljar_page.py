#!/usr/bin/env python3
"""
tools/generate_hmeljar_page.py — /meteohmeljar/: hub stran + interaktivna karta hmeljišč.

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

Postavitev je namerno hub-stran (hero + kartice, isti vizualni jezik kot
/meteogasilec/ in /gobarska-napoved/ — glej PAGE_CSS/GOBE_CATEGORIES v teh
generatorjih), ne golo besedilo + karta, ki je bralo kot članek. Razredi
(`hm-*`) so LASTNA kopija tega vizualnega vzorca, ne uvoz — generatorji si ne
delijo knjižnic/CSS med seboj (isto pravilo kot povsod v repozitoriju).

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

DESC = ("Interaktivna karta hmeljišč Zgornje Savinjske doline (uradni MKGP GIS sloj) — klikni parcelo za "
        "škropilno okno, tveganje za peronosporo/pepelovko, vodno bilanco in nevarnost neurja na tisti točki.")


def _rgba(hex_color, alpha):
    """#rrggbb → rgba(r,g,b,alpha) — ista tehnika kot _rgba() v generate_gasilec_page.py/
    generate_gobe_page.py, lokalna kopija (glej opombo na vrhu datoteke)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


HM_CSS = """<style>
.hm-hero{position:relative;overflow:hidden;border:1px solid var(--card-border);border-radius:1.1rem;
  padding:1.6rem;margin:.6rem 0 1.4rem;box-shadow:var(--card-shadow);color:#fff;
  background:linear-gradient(200deg,rgba(10,20,8,.55) 0%,rgba(8,16,6,.82) 55%,rgba(8,16,6,.95) 100%),
    url('/og/bg/spring.jpg') center 45%/cover}
.hm-hero h1{margin:0 0 .4rem;font-size:1.5rem}
.hm-hero p{margin:.3rem 0 0;font-size:.9rem;color:rgba(255,255,255,.85);line-height:1.55;max-width:58ch}
.hm-hero-flow{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin-top:1.1rem;font-size:.82rem;
  color:rgba(255,255,255,.92)}
.hm-hero-flow span{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.24);border-radius:999px;
  padding:.3rem .8rem}
.hm-hero-flow i{opacity:.55;font-style:normal}
.hm-feat{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:.8rem;margin:0 0 1.6rem}
.hm-feat-card{position:relative;overflow:hidden;border:1px solid var(--card-border);border-radius:.9rem;
  padding:1rem 1.1rem 1.1rem;background:var(--card-bg);box-shadow:var(--card-shadow)}
.hm-feat-card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--fa)}
.hm-feat-ic{display:inline-flex;align-items:center;justify-content:center;width:2.4rem;height:2.4rem;
  border-radius:12px;background:var(--fa-soft);color:var(--fa)}
.hm-feat-ic svg{width:1.4rem;height:1.4rem;display:block}
.hm-feat-title{display:block;font-weight:700;margin:.5rem 0 .2rem}
.hm-feat-sub{display:block;font-size:.78rem;color:var(--muted);line-height:1.4}
.hm-map-card{border:1px solid var(--card-border);border-radius:1rem;padding:1.1rem;background:var(--card-bg);
  box-shadow:var(--card-shadow);margin:0 0 1.2rem}
.hm-map-card h2{margin:0 0 .3rem}
#hm-map{height:440px;border-radius:.8rem;overflow:hidden;margin:.8rem 0;border:1px solid var(--card-border)}
@media (max-width:480px){
  .hm-feat{grid-template-columns:repeat(2,1fr)}
  .hm-feat-sub{display:none}
}
</style>"""

LEAFLET_CSS = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" '
               'integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">')

# Lastna kopija BRAND_SWAP iz generate_gasilec_page.py (drug generator, ne
# uvoženo — glej opombo na vrhu datoteke). Zamenja logo/ime v skupnem
# site-head z MeteoHmeljar znamko, tako da stran deluje kot samostojen
# produkt, ne kot podstran Meteorec bloga — isto kar naredi MeteoGasilec.
BRAND_SWAP = '''<script>(function(){
  var img=document.querySelector(".site-head .brand-logo");
  var nm=document.querySelector(".site-head .brand-name");
  if(img){img.src="/meteohmeljar/logo-hmeljar.svg";img.alt="MeteoHmeljar";}
  if(nm){nm.innerHTML="Meteo<em>Hmeljar</em>";}
})();</script>'''

_FI_SPRAY = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
             '<path d="M4 7h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
             '<path d="M8 7c0 2.5-2 3-2 5.2a2 2 0 0 0 4 0C10 10 8 9.5 8 7Z" fill="currentColor" fill-opacity=".18" '
             'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
             '<path d="M14 7c0 2.5-2 3-2 5.2a2 2 0 0 0 4 0C16 10 14 9.5 14 7Z" fill="currentColor" fill-opacity=".18" '
             'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
             '<path d="M19 10.2c0 1.9-1.5 2.3-1.5 3.9a1.5 1.5 0 0 0 3 0c0-1.6-1.5-2-1.5-3.9Z" '
             'fill="currentColor" fill-opacity=".18" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>'
             '</svg>')

_FI_LEAF = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M5 19C5 10 11 5 19 5c0 8-5 14-14 14Z" fill="currentColor" fill-opacity=".15" '
            'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
            '<path d="M6.5 17.5c3-5 6-7.5 10.5-10.3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
            '<circle cx="17.3" cy="17.3" r="3" fill="#000" fill-opacity=".001" stroke="currentColor" stroke-width="1.3"/>'
            '<path d="M17.3 15.9v1.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
            '<circle cx="17.3" cy="18.6" r=".5" fill="currentColor"/>'
            '</svg>')

_FI_DROP = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M12 3C8 9 5 12.5 5 15.5a7 7 0 0 0 14 0C19 12.5 16 9 12 3Z" fill="currentColor" fill-opacity=".18" '
            'stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>'
            '<path d="M9 15.5c0 1.7 1.3 3 3 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
            '</svg>')

_FI_STORM = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
             '<path d="M7 16a4 4 0 0 1 .6-7.96A5 5 0 0 1 17 9a3.5 3.5 0 0 1-.5 7H7Z" fill="currentColor" fill-opacity=".15" '
             'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
             '<path d="M13.2 12 10 16.3h2.6L11 20.5l4.2-5.1h-2.5l1.6-3.4Z" fill="currentColor" '
             'stroke="currentColor" stroke-width=".8" stroke-linejoin="round"/>'
             '</svg>')

FEATURES = [
    (_FI_SPRAY, "#0ea5e9", "Škropljenje",
     "Najboljše urno okno naslednjih 24 h — veter, dež, temperatura in vlaga strnjeni v en semafor."),
    (_FI_LEAF, "#84cc16", "Bolezni",
     "Peronospora in pepelovka: meteorološka ugodnost za okužbo, ločeno po boleznih, ne eno skupno število."),
    (_FI_DROP, "#0891b2", "Voda",
     "7-dnevna in 3-dnevna vodna bilanca (padavine − ET₀) ter kumulativni primanjkljaj zadnjih 60 dni."),
    (_FI_STORM, "#ef4444", "Nevarnosti",
     "Ocena tveganja neurja za naslednjih 12 h, dvignjena, kadar velja aktivno opozorilo ARSO."),
]


def hero_html():
    return '''  <div class="hm-hero">
    <h1>🌿 MeteoHmeljar</h1>
    <p>Vreme → agronomska interpretacija → operativna odločitev. Klikni svoje hmeljišče na karti spodaj in v
    nekaj sekundah dobiš škropilno okno, tveganje za bolezni, vodno bilanco in nevarnost neurja — za tisto točko,
    ne za celo dolino.</p>
    <div class="hm-hero-flow"><span>🌦 Vreme</span><i>→</i><span>🧠 Interpretacija</span><i>→</i><span>✅ Odločitev</span></div>
  </div>'''


def feature_cards_html():
    cards = []
    for icon, accent, title, sub in FEATURES:
        cards.append(
            f'    <div class="hm-feat-card" style="--fa:{accent};--fa-soft:{_rgba(accent, ".16")}">'
            f'<span class="hm-feat-ic" aria-hidden="true">{icon}</span>'
            f'<span class="hm-feat-title">{title}</span>'
            f'<span class="hm-feat-sub">{sub}</span></div>'
        )
    return '  <div class="hm-feat">\n' + "\n".join(cards) + '\n  </div>'


def map_section_html():
    return '''  <div class="hm-map-card">
    <h2>🗺️ Poišči svojo parcelo</h2>
    <p class="muted-note" style="margin:0">Hmeljišča iz uradnega MKGP GIS sloja RABA, Zgornja Savinjska dolina.</p>
    <div id="hm-map"></div>
    <p class="muted-note" id="hm-map-note">Nalagam hmeljišča …</p>
    <div id="hm-dashboard"></div>
  </div>
  <p class="muted-note">Meje parcel so iz javnega sloja rabe tal (MKGP RABA), ne evidence lastništva — preveri, da je
  izbrana parcela res tvoja, preden se odločaš po njej. Meteorološko okno za škropljenje je ocena, ne navodilo — nikoli
  ne preglasi registracije, etikete ali navodil konkretnega fitofarmacevtskega sredstva.</p>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script src="/meteohmeljar/hmeljar.js"></script>'''


def build_page():
    inner = f'''{hero_html()}
{feature_cards_html()}
{map_section_html()}'''

    crumbs = [("Meteorec", "/"), ("MeteoHmeljar", None)]
    schema = "\n".join([
        seo.webpage_schema("/meteohmeljar/", "MeteoHmeljar", DESC),
        seo.crumbs_schema(crumbs),
    ])
    body = f'''{BRAND_SWAP}
{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
{inner}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    html = seo.page_shell("MeteoHmeljar — karta hmeljišč", DESC, "/meteohmeljar/",
                           schema + "\n" + HM_CSS + LEAFLET_CSS, body)
    seo.write_page("meteohmeljar/index.html", html, force=True)


def main():
    build_page()
    print("→ meteohmeljar/index.html")


if __name__ == "__main__":
    main()
