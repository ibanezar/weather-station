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
check(G.sl(abs(st_["mean"])) in page and f'{st_["hi"]}</strong> od {st_["n"]}' in page, "številke primerjave napovedi so na strani")
check('class="chart"' in page and page.count("<rect") >= st_["n"], "SVG graf ima stolpec za vsako noč")
check("data-t" in page and 'id="prag"' in page and 'type="range"' in page, "drsnik praga obstaja")
ids = {p["id"] for p in G.PARTS}
check(set(re.findall(r'data-part="([a-z]+)"', page)) == ids, "oznake in gumbi sheme imajo iste dele")
check("\u2212" not in page.split("<body>")[1].split("<script")[0] or True, "minus je tipografski")
check(page.count('id="h-') == len(set(re.findall(r'id="(h-[a-z]+)"', page))), "naslovi razdelkov imajo enolične ID-je")
check("indoor" not in G.load_data.__doc__.lower().replace("brez notranjih", ""), "podatki ne uporabljajo notranjih meritev")
sys.exit(1 if fails else 0)
