#!/usr/bin/env python3
"""tools/test_svet_snega.py — /snegofili/svet-snega/: naslov in opis, FAQ ↔ shema, povezave, usklajenost z winter_engine, satelit samo povezave.
Zaženi: python3 tools/test_svet_snega.py"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_svet_snega_page as g  # noqa: E402
import winter_engine as we  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


check(len(g.TITLE) <= 60 and len(g.DESC) <= 160, "naslov ≤ 60 in opis ≤ 160 znakov")
check(g.SNOW_LINE_OFFSET_M == we.SNOW_LEVEL_OFFSET_M, "meja sneženja: odmik na strani = winter_engine.SNOW_LEVEL_OFFSET_M")
check(we.SNOW_RATIO_CM_PER_MM == 1.0, "razmerje 1 mm ≈ 1 cm: besedilo na strani zahteva razmerje 1,0")
page = open(os.path.join(ROOT, "snegofili", "svet-snega", "index.html"), encoding="utf-8").read()
check(g.build_body().split("\n")[1] in page, "committana stran vsebuje izhod generatorja")
for q, a in g.FAQ:
    check(q in page and a[:40] in page, f"FAQ je viden na strani: {q}")
check('"@type":"FAQPage"' in page.replace(" ", ""), "shema FAQPage")
check(page.count("<h1") == 1, "natanko en h1")
# satelit: samo povezave na korenske naslove ponudnikov, nobene vdelave
body = g.build_body()
check("<iframe" not in body and "<img" not in body, "satelit: brez vdelave (iframe) in brez slik tretjih")
for n, u, d in g.SATELLITE_LINKS:
    check(u.startswith("https://") and u.count("/") == 3 and u.endswith("/"), f"satelit: korenski naslov ponudnika {n}")
    check(f'href="{u}" target="_blank" rel="noopener"' in body, f"satelit: povezava {n} se odpre v novem zavihku z rel=noopener")
check("Satelitskih posnetkov na Snegofilih ne vdelujemo" in body, "satelit: stran pove, da posnetkov ne vdelujemo")
for href in re.findall(r'href="(/[^"#]*)', body):
    path = os.path.join(ROOT, href.lstrip("/"), "index.html") if href != "/" else os.path.join(ROOT, "index.html")
    check(os.path.exists(path), f"notranja povezava obstaja: {href}")
check("plazovn" in body.lower() and "ni plazovni bilten" in body.lower(), "opozorilo: ni plazovni bilten")
check("indoor" not in page.lower() and "tempinf" not in page.lower(), "brez notranjih meritev")
seo_audit = open(os.path.join(ROOT, "tools", "seo_audit.py"), encoding="utf-8").read()
check('"snegofili/svet-snega/"' in seo_audit, "stran je v CORE (seo_audit.py)")
check("snegofili/svet-snega/" in open(os.path.join(ROOT, "llms.txt"), encoding="utf-8").read(), "stran je v llms.txt")
check("/snegofili/svet-snega/" in open(os.path.join(ROOT, "snegofili", "index.html"), encoding="utf-8").read(), "Snegofili povezujejo na Svet snega")

print("OK" if not fails else f"{fails} napak")
sys.exit(1 if fails else 0)
