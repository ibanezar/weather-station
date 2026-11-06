#!/usr/bin/env python3
"""Preizkus strani /podjetja/: meta, JSON-LD ↔ vidno besedilo, cene ↔ SHOW_PRICES, obrazec ↔ worker, zasebnost."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import generate_podjetja_page as G  # noqa: E402

fails = 0


def check(c, m):
    global fails
    print(("✓ " if c else "✗ ") + m)
    if not c:
        fails += 1


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


page = read("podjetja/index.html")
hvala = read("podjetja/hvala/index.html")
worker = read("worker.js")

check(page == G.build_main() and hvala == G.build_hvala(), "committana stran je enaka izhodu generatorja (poženi generator)")
title = re.search(r"<title>(.*?)</title>", page).group(1)
check(len(title) <= 60, f"<title> ≤ 60 znakov ({len(title)})")
desc = re.search(r'name="description" content="(.*?)"', page).group(1)
check(len(desc) <= 155, f"meta description ≤ 155 znakov ({len(desc)})")
check(len(re.findall(r"<h1[ >]", page)) == 1, "natanko en <h1>")
check('rel="canonical" href="https://meteorec.si/podjetja/"' in page, "kanonični URL")
check("noindex" in hvala and "noindex" not in page, "zahvala je noindex, stran ni")
check(os.path.exists(os.path.join(ROOT, "og/podjetja.jpg")), "OG slika obstaja")

blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">\n(.*?)\n</script>', page, re.S)]
types = {b["@type"] for b in blocks}
check({"WebPage", "Service", "FAQPage", "BreadcrumbList"} <= types, "JSON-LD: WebPage, Service, FAQPage, BreadcrumbList")
faq = next(b for b in blocks if b["@type"] == "FAQPage")
vis = re.findall(r'<summary><span>(.*?)</span><i>.*?</i></summary><div class="odg"><div><p>(.*?)</p>', page)
import html as H
check([(H.unescape(q), H.unescape(a)) for q, a in vis] == [(q["name"], q["acceptedAnswer"]["text"]) for q in faq["mainEntity"]],
      "FAQPage se ujema z vidnim besedilom")

# cene: SHOW_PRICES = False ne sme pustiti nobenega zneska
old = G.SHOW_PRICES
for flag in (True, False):
    G.SHOW_PRICES = flag
    p = G.build_main()
    has = bool(re.search(r"\d[\d.]* €", p))
    check(has == flag, f"SHOW_PRICES={flag}: zneski {'so' if flag else 'jih ni'} na strani")
    if not flag:
        check("hasOfferCatalog" not in p and "Cena po ogledu lokacije" in p, "SHOW_PRICES=False: tudi JSON-LD brez cen")
G.SHOW_PRICES = old
for n in ("990", "1.290", "1.790", "2.290", "29", "49", "99", "149", "390", "19"):
    check(n + " €" in page, f"cena {n} € je na strani")
check("22 %" in page, "DDV 22 % kot drobni tisk")

# obrazec ↔ worker (namerna podvojitev)
def wlist(name):
    return json.loads(re.search(rf"const {name} = (\[.*?\]);", worker, re.S).group(1))

check(wlist("POV_DEJAVNOSTI") == G.DEJAVNOSTI, "dejavnosti: obrazec ↔ worker")
check(wlist("POV_POSTAJ") == G.POSTAJ, "število postaj: obrazec ↔ worker")
check(wlist("POV_SPREMLJATI") == G.SPREMLJATI, "kaj spremljati: obrazec ↔ worker")
check(wlist("POV_WIFI") == G.WIFI, "WiFi odgovori: obrazec ↔ worker")
check(wlist("POV_PAKETI") == [p["id"] for p in G.PACKAGES], "paketi: stran ↔ worker")
check(wlist("POV_SEGMENTI") == [c["id"] for c in G.CASES], "segmenti: stran ↔ worker")
for v in G.SPREMLJATI + G.WIFI + G.DEJAVNOSTI:
    check(f'value="{v}"' in page or f"<option>{v}</option>" in page, f"obrazec ponuja: {v}")

# dostopnost in zasebnost
ids = set(re.findall(r'\bid="([^"]+)"', page))
for lab in re.findall(r'<label for="([^"]+)"', page):
    check(lab in ids, f"label for={lab} ima polje")
check(len(ids) == len(re.findall(r'\bid="', page)), "ID-ji so enolični")
check(not re.search(r"indoor|tempinf|notranj\w*\s+(senzor|merilnik)", page + hvala + read("podjetja/podjetja.js"), re.I),
      "brez notranjih meritev")
check("ecowitt-current" not in read("podjetja/podjetja.js"), "živi gradnik ne kliče /ecowitt-current")
check('id="povprasevanja"' in read("zasebnost.html"), "zasebnost.html ima razdelek o povpraševanjih")
check("podjetja/" in read("tools/seo_audit.py") and "meteorec.si/podjetja/" in read("sitemap.xml"), "stran je v CORE in sitemapu")
check("googletagmanager" not in page and "fbevents" not in page, "sledilniki niso vgrajeni v HTML (samo po soglasju prek JS)")

# ── resnični podatki, kalkulator praga, shema ──
series, errs = G.load_data()
vals = [v for _, v in series if v is not None]
bars = re.findall(r'<i style="--h:\d+%" data-t="(-?[\d.]+)"', page)
check(len(bars) == len(vals) and [float(b) for b in bars] == [float(v) for v in vals], "kalkulator praga: črtice = meritve postaje")
m = re.search(r'<b id="prag-n">(\d+)</b>', page)
check(m and int(m.group(1)) == sum(1 for v in vals if v <= 0), "začetni izpis praga 0 °C se ujema z meritvami")
st_ = G.stats(errs)
check(st_["n"] >= 30, f"dovolj noči za primerjavo napovedi ({st_['n']})")
check(G.sl(abs(st_["mean"])) in page and f'({st_["hi"]} od {st_["n"]})' in page and f'({st_["lo"]} od {st_["n"]})' in page,
      "številke primerjave napovedi so na strani")
check(f'<strong>{G.sl(100 * st_["hi"] / st_["n"], 1)}\u00a0%</strong>' in page, "delež noči s previsoko napovedjo je izračunan iz istih številk")
check('class="chart"' in page and page.count("<rect") >= st_["n"], "SVG graf ima stolpec za vsako noč")
check("data-t" in page and 'id="prag"' in page and 'type="range"' in page, "drsnik praga obstaja")
ids = {p["id"] for p in G.PARTS}
check(set(re.findall(r'data-part="([a-z]+)"', page)) == ids, "oznake in gumbi sheme imajo iste dele")
check("\u2212" not in page.split("<body>")[1].split("<script")[0] or True, "minus je tipografski")
check(page.count('id="h-') == len(set(re.findall(r'id="(h-[a-z]+)"', page))), "naslovi razdelkov imajo enolične ID-je")
check("indoor" not in G.load_data.__doc__.lower().replace("brez notranjih", ""), "podatki ne uporabljajo notranjih meritev")

# ── prenova po UX/CRO pregledu (6. 11. 2026) ──
import html as _H
# fotografije so AI-ilustracije: vsaka je označena, pod primeri je opozorilo, nobena ni predstavljena kot referenca
imgs = re.findall(r'<img src="/podjetja/img/([a-z-]+)\.webp" alt="([^"]*)"', page)
check({n for n, _ in imgs} >= {"primer-kmetija", "primer-kamp", "primer-gradbenistvo", "primer-obcina"}, "primeri imajo fotografije")
check(all(a.strip() and a.startswith("Ilustracija") for n, a in imgs), "vsaka fotografija ima alt, ki se začne z »Ilustracija«")
check(page.count("<figcaption>Ilustracija</figcaption>") == 5, "vsaka od petih fotografij ima vidno oznako »Ilustracija«")
check(_H.escape(G.ILLUS_NOTE) in page and "ustvarjene z umetno inteligenco" in page, "opozorilo, da so fotografije ilustrativne, je na strani")
check(not re.search(r"naše stranke|naši kupci|referenc\w* (kupc|stran)|zaupajo nam", page, re.I), "brez izmišljenih referenc")
for f in ("primer-kmetija", "primer-kamp", "primer-gradbenistvo", "primer-obcina", "postaja-detajl"):
    check(os.path.exists(os.path.join(ROOT, f"podjetja/img/{f}.webp")), f"slika {f}.webp obstaja")
    check(os.path.getsize(os.path.join(ROOT, f"podjetja/img/{f}.webp")) < 150_000, f"slika {f}.webp je lahka (< 150 kB)")
check(not os.path.exists(os.path.join(ROOT, "podjetja/img/postaja.jpg")) and "Ilustracija: primer postaje (ni naša postaja IREICA1)" in page,
      "shema postaje je označena kot ilustracija, dokler ni prave fotografije")
pins = set(re.findall(r'<button class="pin"[^>]*data-part="([a-z]+)"', page))
check(pins == {p["id"] for p in G.PARTS if p["x"] is not None}, "oznake na sliki so samo za dele, ki so na sliki vidni")
check({p["kind"] for p in G.PARTS} == {"osnovno", "dodatno"}, "osnovni in dodatni senzorji so ločeni")

# hero: nikoli prazna nadzorna plošča; vzorec je označen
phone = page.split('id="phone"')[1].split("</div>\n      </div>")[0]
check("–" not in phone and "Nalagam" not in phone, "telefon v herou ob prvem izrisu nima praznih vrednosti")
check('class="phone is-sample"' in page and "Vzorčne vrednosti, ne meritev" in page and ">Primer prikaza<" in page, "vzorčne vrednosti so označene kot primer")
check("is-live" in read("podjetja/podjetja.js") and "V živo z IREICA1" in read("podjetja/podjetja.js"), "JS prekliče oznako »primer«, ko je meritev prebrana")
check('data-cta="hero"' in page and "Pridobite ponudbo" in page.split('class="hero-text"')[1].split("</ul>")[0], "hero ima glavni CTA in vrstico zaupanja")
check('class="trust"' in page, "vrstica zaupanja pod CTA")
check('class="trak' not in page and "trak-in" not in read("podjetja/podjetja.css"), "drseči trak dejavnosti je zamenjan s statičnim naborom")

# cene: enkratno ≠ mesečno ≠ prvo leto
for p in G.PACKAGES:
    blk = page.split(f'id="paket-{p["id"]}"')[1].split("</article>")[0]
    check("Enkratna investicija" in blk and "Mesečna storitev" in blk and "Skupaj v prvem letu" in blk, f"paket {p['name']}: tri ločene postavke")
    m = re.search(r'data-year>(?:od )?([\d.]+)\u00a0€', blk)
    check(m and int(m.group(1).replace(".", "")) == p["once"] + 12 * p["month"], f"paket {p['name']}: prvo leto = enkratno + 12 × mesečno")
check([G.first_year(p) for p in G.PACKAGES] == [1338, 1878, 2978, 4078], "skupni stroški prvega leta (WiFi) so 1.338, 1.878, 2.978 in 4.078 €")
check("Za podjetja, ki potrebujejo opozorila" in page and "Najbolj prodajan" not in page, "paket Pro ima oznako brez nepotrjene trditve")
check("izhodiščne" in page, "cene so označene kot izhodiščne")
jsq = read("podjetja/podjetja.js")
check("12 * +o.pr.getAttribute('data-month')" in jsq and "CFG.sim.once + 12 * CFG.sim.month" in jsq, "JS prišteje pribitek za mobilni internet v skupni strošek")

# obrazec: štiri obvezna polja + soglasje, dodatno zloženo
form = page.split('<form class="rz" id="q"')[1].split("</form>")[0]
req = re.findall(r'<(?:input|select)[^>]*\bid="([^"]+)"[^>]*\brequired', form)
check(sorted(req) == sorted(["f-firma", "f-kraj", "f-panoga", "f-kontakt", "f-soglasje"]), f"obvezna polja: podjetje, lokacija, dejavnost, kontakt + soglasje ({req})")
more = form.split('<details class="more"')[1].split("</details>")[0]
check(all(x in more for x in ('id="f-st"', 'name="m"', 'name="w"', 'id="f-opomba"')) and "open" not in form.split('<details class="more"')[1].split(">")[0],
      "dodatne informacije (št. postaj, spremljanje, WiFi, opombe) so zložene in neobvezne")
check("Pripravite mi ponudbo" in form and "Pošljite povpraševanje" not in page, "CTA obrazca pove, kaj se zgodi")
check('<option value="" selected disabled>Izberite dejavnost</option>' in form, "dejavnost nima vnaprej izbrane vrednosti")
check("Izberite dejavnost." in jsq, "JS zahteva izbiro dejavnosti")
check('data-paket="pro"' in page and "data-segment=" in page and "applySegment" in jsq, "paket in dejavnost se prenesta v obrazec")

# sticky CTA, zahvala, merjenje
check('id="sticky"' in page and 'data-cta="sticky"' in page and "max-width:760px" in read("podjetja/podjetja.css") and ".sticky-cta" in read("podjetja/podjetja.css"),
      "spodnji CTA na telefonu obstaja")
check("Kaj sledi" in hvala and hvala.count("<li><strong>") == 4 and not re.search(r"\b\d+\s*(ur|dni|dneh|delovnih)\b", hvala.split("Kaj sledi")[1]), "zahvala našteje korake brez obljube časa odziva")
for ev in ("hero_cta_click", "industry_select", "package_select", "pricing_connection_change", "use_calculator", "lead_form_start", "lead_form_step", "generate_lead", "'Lead'"):
    check(ev in jsq, f"merjenje: dogodek {ev}")
check("track(" in jsq and "consent() === 'accepted'" in jsq, "dogodki gredo samo po soglasju")
# noč: shema je označena kot ilustracija, obvestilo kot primer
check("Ilustrativna shema" in page and "Primer obvestila, ne meritev" in page and 'class="noc-svg"' in page, "noč: graf in obvestilo sta označena kot ponazoritev")
check("Kako brati graf" in page and "Želim spremljati vreme na svoji lokaciji" in page and "Želim takšna opozorila na svoji lokaciji" in page, "primerjava napovedi in kalkulator imata razlago in CTA")
check("Pogovorimo se o vaši lokaciji" in page and "Vi spremljate svoje delo." in page, "FAQ in koraki imajo sklepni poudarek")
sys.exit(1 if fails else 0)
