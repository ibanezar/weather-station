#!/usr/bin/env python3
"""
tools/generate_svet_snega_page.py — /snegofili/svet-snega/ »Svet snega: vrste, snežinke in kako brati podatke« (23. 11. 2026)

Poljudni vodnik za Snegofile (po pregledu »Snegofili: ponovni vsebinski pregled«: snežna enciklopedija, satelit). Statična stran brez podatkov postaje;
vsebina je splošno znano strokovno ozadje (nastanek snega, oblike kristalov po Nakajevem diagramu, vrste snega na tleh, razmerje padavine : sneg), **ne lastna
raziskava**, številke so orientacijske in tako tudi pišejo. Naše poenostavitve (meja sneženja 250 m pod ničto izotermo, razmerje 1 mm ≈ 1 cm) so izrecno označene
kot poenostavitve. **Satelit**: stran satelitske posnetke samo opisuje in povezuje na ponudnike (korenski naslovi); vdelave in samodejnega prenosa ni (viri iz
razvojnega okolja niso dosegljivi, zato ne obljubljamo nič, česar nismo preverili). Plazovne nevarnosti in nasvetov za ture ni.

Ni v workflowu: po spremembi besedila poženi ročno in commitaj.
Usage: python3 tools/generate_svet_snega_page.py
"""
import html as _html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

URL = "/snegofili/svet-snega/"
TITLE = "Svet snega: vrste, snežinke in kako brati podatke"
DESC = "Kako nastane sneg, zakaj so snežinke različne, kakšen sneg leži na tleh in kako brati modelsko oceno, meritve in satelitske posnetke."
SNOW_LINE_OFFSET_M = 250   # ↔ winter_engine.SNOW_LEVEL_OFFSET_M (test_svet_snega.py)

SATELLITE_LINKS = (
    ("NASA Worldview", "https://worldview.earthdata.nasa.gov/", "satelitski posnetki in sloji snežne odeje (med njimi MODIS), po dnevih"),
    ("Copernicus Browser", "https://browser.dataspace.copernicus.eu/", "posnetki Sentinel-2 in drugih evropskih satelitov z visoko ločljivostjo"),
    ("EUMETSAT View", "https://view.eumetsat.int/", "evropski meteorološki satelitski posnetki skoraj v živo"),
)

FAQ = [
    ("Zakaj ima snežinka šest krakov?",
     "Led ima urejeno kristalno zgradbo z šesterokotno simetrijo, zato kristal, ki raste iz vodne pare, praviloma dobi šest krakov ali šesterokotno obliko. "
     "Podrobna oblika (ploščica, zvezdica, stebriček) pa je odvisna od temperature in vlage v oblaku."),
    ("Ali lahko sneži pri temperaturi nad 0 °C?",
     "Da, pri nekaj stopinjah nad ničlo, če je zrak suh: kosmi se z izhlapevanjem ohlajajo in ne stalijo takoj. Zato meja sneženja ni natanko pri ničli. "
     "Naša ocena je poenostavljena: za mejo vzame višino ničte izoterme, zmanjšano za 250 m."),
    ("Koliko centimetrov snega je 1 mm padavin?",
     "Pogosto rečemo 10 cm snega iz 10 mm padavin (razmerje 10 : 1), a to je samo povprečje. Moker sneg blizu 0 °C je gostejši in da manj centimetrov, suh pršič pri mrazu "
     "je redkejši in da več. Snegofili povsod računajo 1 mm ≈ 1 cm, zato je ocena v skrajnih primerih lahko precej mimo."),
    ("Kaj je pršič?",
     "Svež, suh in lahek sneg pri nizki temperaturi, ki se zlahka vsiplje. Ostane lahek, dokler ga ne zbije veter ali segrevanje. Snegofili kažejo samo modelski potencial "
     "(sneg, temperatura, veter), ne izmerjene kakovosti snega."),
    ("Ali satelit pokaže, koliko snega leži?",
     "Običajno ne. Optični sateliti pokažejo, ali je tla pokrita s snegom, ne pa njegove višine, in to samo, kadar oblaki ne zakrivajo pogleda. "
     "Za višino odeje so potrebne meritve na tleh, na primer postaje ARSO."),
]


def link_list():
    return "".join(f'<li><a href="{u}" target="_blank" rel="noopener">{_html.escape(n)}</a>: {_html.escape(d)}.</li>' for n, u, d in SATELLITE_LINKS)


def build_body():
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Snegofili", "/snegofili/"), ("Svet snega", None)])}
  <h1 class="page-title">Svet snega</h1>
  <p class="post-meta">Vodnik ob Snegofilih · splošno znano ozadje, številke so orientacijske</p>
  <p class="archive-intro">Kako nastane sneg, zakaj so snežinke različne, kakšen sneg leži na tleh in kaj lahko iz podatkov na <a href="/snegofili/">Snegofilih</a> razberete in česa ne.
  To je poljuden pregled splošno znanega strokovnega ozadja, ne naša raziskava; kjer smo kaj poenostavili, je napisano.</p>

  <h2>Kako nastane sneg</h2>
  <p>V oblaku se vodna para in podhlajene kapljice nabirajo na drobnih ledenih kristalih. Kristali rastejo in se sprimejo v snežinke; ko so dovolj težki, padejo.
  Ali bo na tleh sneg ali dež, odloča temperatura vsega sloja zraka pod oblakom: če je ves sloj pod ničlo ali le malo nad njo, kosmi ne stalijo.
  Zato je <b>meja sneženja</b> običajno nekaj sto metrov pod višino ničte izoterme (višina, kjer je temperatura 0 °C). Močnejše padavine zrak ohladijo in mejo spustijo nižje.</p>
  <p><b>Naša poenostavitev:</b> Snegofili mejo sneženja ocenijo kot višino ničte izoterme, zmanjšano za {SNOW_LINE_OFFSET_M} m. To ni fizikalna konstanta, ampak dogovor za vso stran; na terenu je meja lahko višje ali nižje.</p>

  <h2>Oblike snežink</h2>
  <p>Oblika kristala je odvisna od temperature in vlage v oblaku (po Nakajevem diagramu). Meje so približne in se med viri nekoliko razlikujejo:</p>
  <ul>
    <li><b>Razvejane zvezdice (dendriti)</b> nastanejo okoli −15 °C, kadar je vlage veliko.</li>
    <li><b>Tanke ploščice</b> so pogoste med približno −10 in −12 °C.</li>
    <li><b>Stebrički in iglice</b> so pogostejši okoli −5 °C.</li>
    <li>Pri zelo nizkih temperaturah so kristali običajno manjši in preprostejši.</li>
  </ul>
  <p>Šesterokotna simetrija izvira iz urejene zgradbe ledu. Blizu 0 °C se snežinke rade sprimejo v velike, mokre kosme.</p>

  <h2>Vrste snega na tleh</h2>
  <p>Sneg se po padcu spreminja: sesede se, taja, zmrzuje in ga premešča veter. Preprost pregled (ni plazovna razvrstitev):</p>
  <ul>
    <li><b>Pršič</b>: svež, suh in lahek sneg pri nizki temperaturi.</li>
    <li><b>Moker sneg</b>: blizu ali nad 0 °C, težak in gostejši, dober za kepe.</li>
    <li><b>Zbit sneg (vetrna plošča)</b>: veter kristale zdrobi in zbije, zato je sneg gostejši in trši, predvsem ob grebenih in na odprtem.</li>
    <li><b>Zrnati sneg (firn)</b>: po večkratnem taljenju in zmrzovanju kristali zaokrožijo v zrna, značilno spomladi.</li>
    <li><b>Skorja</b>: led na površini po dežju ali taljenju in ponovnem zmrzovanju.</li>
  </ul>
  <p>Gostota svežega snega je zelo različna, grobo od nekaj deset do okoli 200 kg/m³. Model na Snegofilih nima podatka, katera vrsta snega je na terenu.</p>

  <h2>Milimetri padavin in centimetri snega</h2>
  <p>Padavine merimo v milimetrih (kot višina vode). Pri razmerju 10 : 1 da 10 mm padavin 10 cm snega, pri bolj suhem snegu (na primer 15 : 1) 15 cm, pri mokrem (na primer 6 : 1) 6 cm.
  Razmerje je grobo od približno 5 : 1 do več kot 20 : 1. <b>Snegofili povsod računajo 1 mm ≈ 1 cm</b>, zato je ocena novega snega pri skrajnem mrazu lahko prenizka, pri mokrem snegu previsoka.</p>
  <p>Ločimo tri stvari: <b>nov sneg</b> (kar je zapadlo v nekaj urah), <b>višina snežne odeje</b> (kar leži, po sesedanju, taljenju in vetru) in <b>vodna vrednost snega</b> (koliko vode je v odeji).
  Na Snegofilih je nov sneg modelska ocena, višina odeje pa je meritev ARSO, ločena od modela.</p>

  <h2>Kako brati Snegofile</h2>
  <ul>
    <li><b>Model</b>: ocena iz padavin in meje sneženja za celico vremenskega modela. Ne razloči pobočij in dolin. Razdelki: zemljevid, Powder Tracker, Slovenija po regijah, 96-urni pregled, Snežni dogodki.</li>
    <li><b>Meritev</b>: izmerjena višina odeje na postajah ARSO in ročna meritev v Rečici, kjer jo imamo. Prazno polje pomeni, da meritve nimamo, ne da snega ni.</li>
    <li><b>Kamera</b>: sličica ali časovni zdrs, ki jo objavi lastnik kamere. Slika je vedno pomembnejša od ocene.</li>
  </ul>
  <p>Več o tem, kako računamo in izbiramo točke, je pod »Primerjava lokacij« na <a href="/snegofili/#lokacije">Snegofilih</a>. Za Slovenijo glejte tudi
  <a href="/zima/snezna-karta/">snežno karto</a>, <a href="/zima/meja-snezenja/">mejo sneženja</a> in pojem <a href="/slovar/sneg/">sneg</a> v slovarju.</p>

  <h2>Satelitski pogled na sneg</h2>
  <p>Optični sateliti (na primer MODIS z ločljivostjo okoli 500 m ali Sentinel-2 z ločljivostjo 10 do 20 m) razločijo sneg od tal po tem, kako odbija svetlobo.
  Pokažejo <b>pokritost</b>, ne višine snega, in samo takrat, ko oblaki ne zakrivajo pogleda. Snežno pokritost lahko s sličice primerjate z našo modelsko oceno ali kamerami.</p>
  <p><b>Satelitskih posnetkov na Snegofilih ne vdelujemo.</b> Povezave vodijo k ponudnikom in se odprejo v novem zavihku:</p>
  <ul>{link_list()}</ul>

  <h2>Česa podatki ne povedo</h2>
  <p>Ocena novega snega ni plazovni bilten in ni nasvet za turo. Ne pove, ali je smučišče odprto, kakšen je sneg pod površino ali koliko ga je veter prenesel.
  Pred odhodom v gore preverite uradni plazovni bilten pristojne države, <a href="https://meteo.arso.gov.si/" target="_blank" rel="noopener">ARSO</a> in razmere pri koči ali smučišču.
  Šolsko različico opazovanja snega najdete v <a href="/sola/sneg-in-zmrzal/">delovnem listu Sneg in zmrzal pozimi</a>.</p>
{faq_html}
  <a class="back-link" href="/snegofili/">← Nazaj na Snegofile</a>'''


def main():
    assert len(TITLE) <= 60 and len(DESC) <= 160, (len(TITLE), len(DESC))
    body = build_body()
    schema = "\n".join([seo.webpage_schema(URL, TITLE, DESC, date_published="2026-11-23"),
                        seo.crumbs_schema([("Meteorec", "/"), ("Snegofili", "/snegofili/"), ("Svet snega", None)]), seo.faq_schema(FAQ)])
    seo.write_page("snegofili/svet-snega/index.html", seo.page_shell(TITLE, DESC, URL, schema, body), force=True)
    print("  → snegofili/svet-snega/index.html")


if __name__ == "__main__":
    main()
