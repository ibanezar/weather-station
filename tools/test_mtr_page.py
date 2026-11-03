#!/usr/bin/env python3
"""
tools/test_mtr_page.py — /mtr/ in kartice »Kuhinja« v zavihku MTR (tools/generate_mtr_page.py).

Preveri: committana stran in blok v index.html sta enaka izhodu generatorja (vsebina je na enem mestu, ob
spremembi poženi generator); naslov ≤ 60 znakov, opis ≤ 160; vsaka skripta v tabeli »Ponovi sam« obstaja;
števila v kratkem odgovoru in FAQ se ujemajo z docs/model-recica.md; JS števcev na strani in v app.js imata
ista besedila (namerna podvojitev); brez notranjih meritev; stran je v CORE, sitemapu in llms.txt.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import generate_mtr_page as g  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✓ " if ok else "  ✗ ") + name)
    fails += 0 if ok else 1


def read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


page = read(g.REL)
check("committana stran je enaka izhodu generatorja", page == g.build_page())

idx = read("index.html")
m = re.search(r"[ \t]*<!-- MTR-KUHINJA:START.*?<!-- MTR-KUHINJA:END -->\n", idx, re.S)
check("index.html ima blok MTR-KUHINJA", bool(m))
check("blok v index.html je enak izhodu generatorja",
      bool(m) and m.group(0) == f"    {g.M_START}\n{g.tab_cards()}    {g.M_END}\n")

title = re.search(r"<title>(.*?)</title>", page).group(1)
desc = re.search(r'<meta name="description" content="([^"]*)"', page).group(1)
check(f"<title> ≤ 60 znakov ({len(title)})", len(title) <= 60)
check(f"opis ≤ 160 znakov ({len(desc)})", len(desc) <= 160)
check("canonical kaže na /mtr/", 'rel="canonical" href="https://meteorec.si/mtr/"' in page)
check("h1 je en sam", page.count("<h1>") == 1)

scripts = set(re.findall(r"(eval_[a-z0-9_]+\.py|fetch_[a-z_]+_cache\.py)", " ".join(
    [b for _, b, _ in g.REPRO_OFFLINE + g.REPRO_NET] + [b for _, b in g.REPRO_CACHE])))
missing = [s for s in sorted(scripts) if not os.path.exists(os.path.join(ROOT, "tools", "ai", s))]
check(f"vse skripte iz »Ponovi sam« obstajajo ({len(scripts)})", scripts and not missing)
if missing:
    print("    manjkajo:", missing)
for _, cmd, _ in g.REPRO_OFFLINE + g.REPRO_NET:
    pth = re.search(r"python3 (\S+\.py)", cmd)
    if pth and not os.path.exists(os.path.join(ROOT, pth.group(1))):
        check("ukaz kaže na obstoječo skripto: " + pth.group(1), False)
files = [p for p, _ in g.DATA_FILES]
check("vse datoteke v »Podatki« obstajajo (data/mtr-pending.json je committan)",
      all(os.path.exists(os.path.join(ROOT, p)) for p in files))
# vsaka skripta iz tabele je v dokumentu omenjena (sled do poskusa)
doc = read("docs/model-recica.md")
check("skripte iz tabele so omenjene v docs/model-recica.md",
      all(s in doc for s in scripts - {"fetch_hourly_cache.py", "fetch_profile_cache.py", "fetch_wind_cache.py",
                                       "eval_significance.py", "eval_mtr_calibration.py", "eval_mtr2_hourly.py"}))

# številke v kratkem odgovoru so v dokumentu (več-modelni Tmax, walk-forward 2024-05-26 → 2026-10-05)
for n in ("1,04", "1,24", "1,40"):
    check(f"{n} °C (Tmax D+1/D+2/D+3) je v dokumentu", re.search(r"\| *D\+\d *\| *\d,\d\d °C *\| *" + re.escape(n) + " °C", doc))
check("obdobje 26. 5. 2024 – 5. 10. 2026 ustreza dokumentu (2024-05-26 → 2026-10-05)",
      "2024-05-26 → 2026-10-05" in doc and "26. 5. 2024 do 5. 10. 2026" in page)
check("12 poskusov v tabeli in v lead besedilu llms.txt", len(g.NEG) == 12 and "12 poskusov" in read("llms.txt"))

# JS števcev: ista besedila na strani in v app.js
app = read("app.js")
for t in ("Najbolj zapolnjen razred: ", "Zimskih dni (nov–feb) v dnevniku: ", "dni zajema skupaj: ",
          "Dni s snegom nad 1 cm v dnevniku doslej: ", "/data/mtr-pending.json"):
    check(f"JS števcev: »{t}« na strani in v app.js", t in page and t in app)

check("brez notranjih meritev", "indoor" not in page.lower() and "tempinf" not in page.lower())
seo_audit = read("tools/seo_audit.py")
check('stran je v CORE (seo_audit.py)', '"mtr/"' in seo_audit)
check("stran je v sitemap.xml", "<loc>https://meteorec.si/mtr/</loc>" in read("sitemap.xml"))
check("stran je v llms.txt", "https://meteorec.si/mtr/" in read("llms.txt"))

print("\n%d napak" % fails if fails else "\nVse v redu.")
sys.exit(1 if fails else 0)
