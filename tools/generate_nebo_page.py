#!/usr/bin/env python3
"""
tools/generate_nebo_page.py — /nebo-nocoj/ »Nebo nocoj: polarni sij in utrinki« (18. 11. 2026)

Ovoj za nebo-nocoj/nebo.js (ROČNO pisan, model izvožen za Node: tools/test_nebo.mjs). JS ob nalaganju pokliče NOAA SWPC (napoved Kp, CORS odprt) in Open-Meteo
(oblačnost za Rečico), presodi, ali je polarni sij nocoj pri nas možen (Kp ≥ 7 IN nočna oblačnost < 70 %; Kp 6 je mejno), in pokaže naslednji roj utrinkov
(vrhovi po IMO: Leonidi 17. 11., Geminidi 14. 12., Ursidi 22. 12., Kvadrantidi 3. 1.) z osvetljenostjo lune. Prag Kp 7 je pravilo palca za geomagnetno širino
Slovenije, ne garancija. Brez podatka stran ne trdi možnosti. Push obvestil še ni. Ni v workflowu; podatki so v brskalniku. Notranjih meritev ne uporablja.
"""
import hashlib
import html as _html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(ROOT, "nebo-nocoj", "nebo.js")
URL = "/nebo-nocoj/"

FAQ = [
    ("Ali je pri nas mogoče videti polarni sij?", "Redko. Običajno ga ob močni geomagnetni nevihti (stopnja Kp 7 ali več) vidimo nizko nad severnim obzorjem, pogosto šele na fotografiji. Pogoj sta tudi jasno nebo in temna lokacija."),
    ("Od kod je napoved?", "Kp je napoved ameriške službe NOAA SWPC, oblačnost je modelska napoved Open-Meteo za Rečico ob Savinji. Stran ne napoveduje sončne aktivnosti sama."),
    ("Kaj je ZHR pri rojih utrinkov?", "Zenitna urna frekvenca: največ utrinkov na uro, ki jih opazovalec vidi pri idealnem nebu z radiantom v zenitu. V resnici jih je običajno bistveno manj. Vrednosti so po podatkih Mednarodne organizacije za meteore (IMO)."),
    ("Zakaj luna moti?", "Svetla luna zasenči šibke utrinke. Stran izračuna osvetljenost lune približno (na dan natančno); nad 50 % so slabši pogoji."),
]


def main():
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Nebo nocoj: polarni sij in utrinki nad dolino"
    desc = "Ali je nocoj nad Slovenijo možen polarni sij? Napoved Kp in oblačnosti za Rečico ob Savinji ter naslednji roj utrinkov (Geminidi, Kvadrantidi) z lunino fazo."
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Nebo nocoj", None)])}
  <h1 class="page-title">Nebo nocoj: polarni sij in utrinki</h1>
  <p class="post-meta">Napoved Kp (NOAA SWPC) · oblačnost (Open-Meteo) · roji utrinkov (IMO)</p>
  <p class="archive-intro">Polarni sij je pri nas redek in terja močno geomagnetno nevihto in jasno nebo; utrinki so pogostejši. Stran združi napoved za nocoj in pove, kdaj je naslednji roj.</p>
  <style>.nb-big{{font-size:1.7rem;font-weight:700;margin:.3rem 0}}#nb-out .card{{margin:.8rem 0}}</style>
  <div id="nb-out" aria-live="polite"><p class="archive-intro">Nalagam podatke …</p></div>
  <noscript><p class="archive-intro">Stran potrebuje JavaScript.</p></noscript>
  <p class="vs-note">Pravilo Kp ≥ 7 je približek za geomagnetno širino Slovenije, ne garancija. Brez podatka stran ne trdi, da je sij možen. Podatki se berejo neposredno iz brskalnika (NOAA SWPC, Open-Meteo); obiskovalec ne pošilja ničesar.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script src="{URL}nebo.js?v={js_ver}" defer></script>'''
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
                        seo.crumbs_schema([("Meteorec", "/"), ("Nebo nocoj", None)]), seo.faq_schema(FAQ)])
    seo.write_page("nebo-nocoj/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print("  → nebo-nocoj/index.html")


if __name__ == "__main__":
    main()
