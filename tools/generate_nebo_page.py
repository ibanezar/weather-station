#!/usr/bin/env python3
"""
tools/generate_nebo_page.py — /nebo-nocoj/ »Nebo nocoj: polarni sij in utrinki« (18. 11. 2026)

Ovoj za nebo-nocoj/nebo.js (ROČNO pisan, model izvožen za Node: tools/test_nebo.mjs). JS ob nalaganju pokliče NOAA SWPC (napoved Kp, CORS odprt) in Open-Meteo
(oblačnost za Rečico), presodi, ali je polarni sij nocoj pri nas možen (Kp ≥ 7 IN nočna oblačnost < 70 %; Kp 6 je mejno), in pokaže naslednji roj utrinkov
(vrhovi po IMO: Leonidi 17. 11., Geminidi 14. 12., Ursidi 22. 12., Kvadrantidi 3. 1.) z osvetljenostjo lune. Prag Kp 7 je pravilo palca za geomagnetno širino
Slovenije, ne garancija. Brez podatka stran ne trdi možnosti. Opozorilo na telefon (19. 11. 2026, izbirno): vrh roja utrinkov ali možen sij pri jasnem nebu; strežnik v worker.js (»Nebo alarm«, test tools/test_nebo_alarm.mjs). Ni v workflowu; podatki so v brskalniku. Notranjih meritev ne uporablja.
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
    ("Ali lahko dobim obvestilo na telefon?", "Da, izbirno. Na tej strani vklopite opozorilo za vrh roja utrinkov in/ali za možen polarni sij. Obvestilo pride zvečer (med 17. in 23. uro) in samo, kadar nočna oblačnost ni visoka (pod 70 %); za sij mora biti napovedan tudi Kp 7 ali več. Največ eno obvestilo na vrsto in večer. Je modelska ocena, ne obljuba."),
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
  <style>.nb-big{{font-size:1.7rem;font-weight:700;margin:.3rem 0}}#nb-out .card,#nb-alarm{{margin:.8rem 0}}.nb-al{{display:flex;gap:.6rem;align-items:flex-start;padding:.45rem 0;min-height:44px}}.nb-al input{{margin-top:.25rem;width:1.1rem;height:1.1rem}}.nb-row{{margin:.6rem 0;display:flex;gap:.6rem;flex-wrap:wrap}}.nb-btn{{min-height:44px;padding:.5rem 1rem;border-radius:8px;border:1px solid #2368c8;background:#2368c8;color:#fff;font:inherit;font-weight:700;cursor:pointer}}.nb-btn-s{{background:transparent;color:inherit;border-color:rgba(128,128,128,.6);font-weight:400}}.nb-btn:disabled{{opacity:.5;cursor:not-allowed}}#nb-alarm a{{color:#7dd3fc;text-decoration:underline}}</style>
  <div id="nb-out" aria-live="polite"><p class="archive-intro">Nalagam podatke …</p></div>
  <div class="card" id="nb-alarm" hidden>
    <div class="clabel">Opozorilo na telefon</div>
    <p>Obvestilo zvečer (med 17. in 23. uro), samo ko nočna oblačnost ni visoka. Izberite, kaj želite:</p>
    <label class="nb-al"><input type="checkbox" id="nb-al-roji" checked> Vrh roja utrinkov (nočna oblačnost pod 70 %)</label>
    <label class="nb-al"><input type="checkbox" id="nb-al-sij"> Možen polarni sij (napovedani Kp 7 ali več in nočna oblačnost pod 70 %)</label>
    <div class="nb-row"><button type="button" class="nb-btn" id="nb-al-on">Vklopi opozorilo</button> <button type="button" class="nb-btn nb-btn-s" id="nb-al-off" hidden>Izklopi</button></div>
    <p class="vs-note" id="nb-al-ios" hidden>Na iPhonu obvestila delujejo samo v aplikaciji, dodani na začetni zaslon (Deli, nato Dodaj na začetni zaslon).</p>
    <p class="vs-note" id="nb-al-msg" aria-live="polite"></p>
    <p class="vs-note">Modelska ocena, ne obljuba. Strežnik shrani samo naslovnico naročnine in vaši dve izbiri; izklop ju izbriše. Splošno obvestilo o močni geomagnetni nevihti (Kp 7 ali več) že prejemajo vsi, ki imajo vklopljena obvestila na <a href="/">naslovni strani</a>.</p>
  </div>
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
