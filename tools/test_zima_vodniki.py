#!/usr/bin/env python3
"""Notranje povezave 6. 11. 2026 (GSC): zimski vodniki z /zima/ in naslovnice, kraji v blogu in nogi.

Preverja: (1) vsak slug v WINTER_GUIDES obstaja v blog.json in kot datoteka ter je povezan v committanem
/zima/; (2) naslovnica povezuje iste vodnike in vse kraje, ki jih kaže pas »Vreme po krajih«;
(3) DATA_LINKS (blog) in footer_html() (arhiv) vsebujeta Mozirje in Nazarje, cilji obstajajo;
(4) <title> naslovnice ni daljši od 60 znakov in se ne ujema z naslovom pristajalne strani
(dve strani z istim namenom si sicer konkurirata za isto poizvedbo)."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import generate_zima_page as zima
import generate_monthly_post as mp
import generate_seo_pages as seo

fails = []
def check(ok, msg):
    if not ok:
        fails.append(msg)

def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
posts = posts if isinstance(posts, list) else posts.get("posts", posts)
slugs = {p["slug"] for p in posts}
hub, home = read("zima/index.html"), read("index.html")

check(len(zima.WINTER_GUIDES) == 8, "WINTER_GUIDES: pričakovanih 8 člankov")
for slug, *_ in zima.WINTER_GUIDES:
    check(slug in slugs, f"{slug}: ni v blog.json")
    check(os.path.exists(os.path.join(ROOT, "blog", slug + ".html")), f"{slug}: manjka datoteka")
    check(f'href="/blog/{slug}.html"' in hub, f"{slug}: ni povezan z /zima/ (poženi generate_zima_page.py)")

for href in ["/vreme-mozirje/", "/vreme-nazarje/", "/vreme-recica-ob-savinji/", "/vreme-ljubno-ob-savinji/",
             "/vreme-gornji-grad/", "/vreme-luce/", "/vreme-solcava/", "/vreme-zgornja-savinjska-dolina/"]:
    check(f'<a href="{href}">Vreme ' in home, f"naslovnica: ni besedilne povezave {href} z »Vreme …«")
    check(os.path.exists(os.path.join(ROOT, href.strip("/"), "index.html")), f"{href}: stran ne obstaja")
for slug in ["kdaj-menjati-zimske-gume-recica-1027", "kdaj-pade-prvi-sneg-v-dolini-recica-1027",
             "crnivec-pozimi-sneg-verige-1027", "zled-ali-poledica-razlika-1027"]:
    check(f'href="/blog/{slug}.html"' in home, f"naslovnica: ni povezave na {slug}")

data_hrefs = [h for h, _ in mp.DATA_LINKS]
foot = seo.footer_html()
for href in ["/vreme-mozirje/", "/vreme-nazarje/"]:
    check(href in data_hrefs, f"DATA_LINKS: manjka {href}")
    check(f'href="{href}"' in foot, f"footer_html(): manjka {href}")
for p in posts[:5]:
    html = read(f"blog/{p['slug']}.html")
    check('href="/vreme-mozirje/"' in html or "podatki:start" not in html, f"{p['slug']}: blok »Vreme in podatki« brez Mozirja")

t_home = re.search(r"<title>([^<]*)</title>", home).group(1)
t_land = re.search(r"<title>([^<]*)</title>", read("vreme-recica-ob-savinji/index.html")).group(1)
check(len(t_home) <= 60, f"naslov naslovnice {len(t_home)} znakov")
check("Vreme Rečica ob Savinji" not in t_home, "naslovnica in pristajalna stran imata isti ciljni izraz v naslovu")
check(t_home.split("|")[0] != t_land.split("|")[0], "enaka naslova naslovnice in pristajalne strani")

if fails:
    print("\n".join("✗ " + f for f in fails))
    sys.exit(1)
print("✓ test_zima_vodniki: vse OK")
