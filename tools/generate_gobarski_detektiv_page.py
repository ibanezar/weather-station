#!/usr/bin/env python3
"""
tools/generate_gobarski_detektiv_page.py — »Gobarski detektiv« (/igra/gobarski-detektiv/)

Poučna igra prepoznavanja gob: šest primerov, v vsakem eno goba iz para, ki se
pogosto zamenja (jurček/žolčasti goban, lisička/lažna lisička, kukmak/zelena
mušnica …). Igralec jo pregleda po sledeh in jo poimenuje.

Ta skript piše samo OVOJ: igra/gobarski-detektiv/index.html (glava, noga,
spodnja navigacija, meta, JSON-LD, razlaga, FAQ, opozorilo). Igra sama je v
ročno pisanih igra/gobarski-detektiv/detektiv.js in detektiv.css — generator
ju samo naloži. Stran je statična (brez dnevnega podatka), zato ni v nobenem
workflowu: po spremembi ovoja ga poženi ročno in commitaj rezultat.

Imena in užitnost vrst so ista kot v bazi (species_rules.yaml); preverja ju
tools/test_detektiv.mjs.

Igra bere samo zunanje meritve IREICA1, in to prek workerja `/detektiv/vreme`
(ta bere history.json, ne Ecowitta; notranjih meritev tu ni in ne smejo priti).
Primeri v igri so izmišljeni, vreme na kartici je pravo.

Uporaba:
  python3 tools/generate_gobarski_detektiv_page.py
"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — skupni ovoj strani
from asset_version import asset_href  # noqa: E402

URL = "/igra/gobarski-detektiv/"
TITLE = "Gobarski detektiv — igra prepoznavanja gob"
N_VRST = 32     # število vrst v igri; preverja tools/test_detektiv.py
N_PAROV = 16
DESC = (f"Poučna igra za gobarje: {N_VRST} vrst v {N_PAROV} parih dvojnic. Pregleduj klobuk, liste, nogo "
        "in meso ter loči jurčka od žolčastega gobana, lisičko od lažne in kukmak od zelene mušnice.")
DATE_PUBLISHED = "2026-10-18"

FAQ = [
    ("Ali lahko po igri nabiram in jem gobe?",
     "Ne. Igra je samo vaja za oko in za razmišljanje. Gobe, ki jih nabereš, mora pred jedjo "
     "pregledati usposobljen gobar v pregledovalnici gob. Če nisi povsem prepričan, gobo pusti."),
    ("Zakaj igra nagradi pregled več sledi?",
     "Ker nobena lastnost ni zanesljiva sama zase. Rjav klobuk imata jurček in žolčasti goban, "
     "beli sta lahko užitna šampinjonka in smrtno strupena zelena mušnica. Šele klobuk, spodnja "
     "stran, noga, dno noge, meso z vonjem in okolje skupaj povedo, s čim imaš opravka."),
    ("Od kod so podatki o vrstah?",
     "Imena in užitnost so enaka kot v <a href=\"/gobarska-napoved/baza-vrst/\">bazi vrst</a>, "
     "pare, ki se zamenjajo, pa najdeš tudi na strani "
     "<a href=\"/gobarska-napoved/dvojnice/\">Nevarne dvojnice</a>. Ilustracije so narisane za igro "
     "in so poenostavljene: prave gobe se med seboj razlikujejo bolj kot risbe."),
    ("Ali igra uporablja podatke postaje?",
     "Samo za kartico z vremenom: na začetku in koncu igre pokaže zadnjih sedem dni z zunanjega senzorja "
     "postaje IREICA1 v Rečici ob Savinji (najnižja in najvišja temperatura, padavine). Zgodbe v primerih so "
     "izmišljene in niso vezane na te meritve. Če podatka ni, kartice ni."),
]

WARNING = ('<strong>Pomembno:</strong> igra je samo vaja. Gob <strong>ne uživaj</strong> na podlagi '
           'igre, slike ali spletne strani. Vsako nabrano gobo mora pred jedjo pregledati '
           'usposobljen gobar (pregledovalnica gob). Če nisi povsem prepričan, gobo pusti. '
           'Ob sumu na zastrupitev takoj pokliči <a href="tel:112">112</a>.')


def webapp_schema():
    import json
    data = {
        "@context": "https://schema.org",
        "@type": ["WebApplication", "Game"],
        "@id": f"{seo.SITE}{URL}#igra",
        "name": "Gobarski detektiv",
        "description": DESC,
        "url": f"{seo.SITE}{URL}",
        "inLanguage": "sl",
        "applicationCategory": "GameApplication",
        "genre": "izobraževalna igra",
        "operatingSystem": "Vsak sodoben brskalnik",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        "audience": {"@type": "Audience", "audienceType": "Gobarji začetniki"},
        "author": {"@type": "Person", "name": "Filip Eremita"},
        "isPartOf": {"@id": f"{seo.SITE}/#website"},
        "datePublished": DATE_PUBLISHED,
    }
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n</script>")


def build_body():
    esc = html.escape
    crumbs = [("Meteorec", "/"), ("Gobarska napoved", "/gobarska-napoved/"),
              ("Gobarski detektiv", None)]
    faq_html = ('  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f"    <details><summary>{esc(q)}</summary><p>{a}</p></details>" for q, a in FAQ
    ) + "\n  </div>")
    return f'''{seo.crumbs_html(crumbs)}
  <h1 class="page-title">Gobarski detektiv</h1>
  <p class="post-meta">Poučna igra: preglej sledi, imenuj gobo in loči užitno od nevarne dvojnice</p>
  <p class="archive-intro">{N_VRST} vrst v {N_PAROV} parih, ki jih gobarji radi zamenjajo. Vsak krog je šest primerov,
  vsakič drugačnih. Ugotoviš, ali je ena lastnost dovolj. Običajno ni.</p>

  <section id="gd-app" aria-label="Igra Gobarski detektiv">
    <noscript><p>Igra potrebuje JavaScript. Brez njega si lahko ogledaš
    <a href="/gobarska-napoved/dvojnice/">nevarne dvojnice</a> in
    <a href="/gobarska-napoved/baza-vrst/">bazo vrst</a>.</p></noscript>
  </section>

  <aside class="gd-warning" role="note">{WARNING}</aside>

  <h2>Kako igra deluje</h2>
  <p>Vsak krog ima šest primerov, ki jih igra žreba med {N_PAROV} pari. V vsakem primeru dobiš eno gobo. Z gumbi preglejuješ šest sledi: klobuk, spodnjo stran (cevke ali listi),
  nogo, dno noge, meso z vonjem in okolje, kjer goba raste. Ilustracija se obrne tako, da vidiš, kaj bereš. Nato izbereš, katera od
  treh ponujenih vrst je to. Pravilna vrsta je vredna dve točki, tretjo dobiš, če si pregledal vsaj
  štiri od šestih sledi. Po vsakem odgovoru igra primerja ključne sledi obeh vrst in pove, katero si spregledal. Na koncu vidiš, kje bi bila odločitev nevarna, in lahko ponoviš samo napačne primere. Pari, pri katerih se zmotiš, se v naslednjih krogih ponudijo znova (zapomni si jih samo tvoj brskalnik). Začetnik lahko izbere <strong>način učenja</strong>: brez točk, vse sledi so že odprte.</p>
  <p>Vsak par je resničen. Med njimi so jurček in žolčasti goban, navadna in lažna lisička, poljski
  kukmak in zelena mušnica, pšenična in poljska koprenka, užitna in zlata sirovka ter rdečkasta in
  panterjeva mušnica. Več o njih: <a href="/gobarska-napoved/dvojnice/">Nevarne dvojnice</a>,
  <a href="/gobarska-napoved/strupene-gobe/">Strupene gobe</a>,
  <a href="/gobarska-napoved/baza-vrst/">Baza vrst</a>.</p>
  <p class="gd-sources">Ilustracije so narisane za igro in so poenostavljene. Igra ni določevalni ključ.</p>

{faq_html}
  <a class="back-link" href="/gobarska-napoved/">← Gobarska napoved</a>

  <script src="{asset_href("igra/gobarski-detektiv/detektiv.js")}" defer></script>'''


def main():
    schema = "\n".join([
        seo.webpage_schema(URL, TITLE, DESC, date_published=DATE_PUBLISHED),
        webapp_schema(),
        seo.crumbs_schema([("Meteorec", "/"), ("Gobarska napoved", "/gobarska-napoved/"),
                           ("Gobarski detektiv", None)]),
        # FAQ v shemi mora biti DOBESEDNO isto besedilo kot na strani (geo_audit.py).
        seo.faq_schema(FAQ),
    ])
    head = schema + f'\n<link rel="stylesheet" href="{asset_href("igra/gobarski-detektiv/detektiv.css")}">'
    html_out = seo.page_shell(TITLE, DESC, URL, head, build_body())
    seo.write_page("igra/gobarski-detektiv/index.html", html_out, force=True)
    print("  → igra/gobarski-detektiv/index.html")


if __name__ == "__main__":
    main()
