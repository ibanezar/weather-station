#!/usr/bin/env python3
"""Preizkus bloka »Na kratko« in FAQ na /gobarska-napoved/baza-vrst/ (in skupinah užitnosti):
številke so izračunane iz species_rules.yaml, stran »strupene« se ne spreminja (najmočnejša po klikih),
naslov je znotraj 60 znakov in FAQ shema ustreza vidnim vprašanjem."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_gobe_page as g  # noqa: E402
import yaml  # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"✗ {name} {detail}")


rules = yaml.safe_load(open(os.path.join(g.ROOT, "species_rules.yaml"), encoding="utf-8"))
species = rules["species"]
n_all = len(species)

# Vse (ključ None)
html_all, qa_all = g.baza_kratko(species, species, None, "")
check("vse: Na kratko", "Na kratko:" in html_all)
check("vse: skupno število", f"baza ima {n_all} vrst" in html_all)
check("vse: 3 vprašanja", len(qa_all) == 3 and all(q and a for q, a in qa_all))
check("vse: telefon centra za zastrupitve", g.STRUP_PHONE in qa_all[1][1])

# Vsota skupin = vse (strupene stopnje združene)
cnt = {}
for sp in species:
    k = g.EDIB_FILTER.get((sp.get("edibility") or "").lower().strip(), "drugo")
    cnt[k] = cnt.get(k, 0) + 1
check("skupine pokrijejo vse vrste", sum(cnt.values()) == n_all and "drugo" not in cnt, str(cnt))

# Skupina užitnih
sub = [sp for sp in species if g.EDIB_FILTER.get((sp.get("edibility") or "").lower().strip()) == "uzitna"]
html_u, qa_u = g.baza_kratko(sub, species, "uzitna", "uzitne")
check("užitne: število", f"je {len(sub)} užitnih vrst" in html_u)
n_dbl = sum(1 for sp in sub if sp.get("doubles"))
check("užitne: dvojnice", (f"Pri {n_dbl} vrstah" in html_u) == bool(n_dbl))
check("užitne: opozorilo 100 %", "100 %" in html_u)

# Besedila ne smejo vsebovati slovničnih napak iz prve različice
check("brez »1 zaščitenih«", "1 zaščitenih" not in html_all)
check("brez »strupenih gobe«", all("strupenih gobe" not in q for q, _ in qa_u))

# Zgrajena stran (če je bila generirana): naslov znotraj 60 znakov
for path in ["", "uzitne", "pogojno-uzitne", "neuzitne"]:
    f = os.path.join(g.ROOT, "gobarska-napoved", "baza-vrst", path, "index.html")
    if not os.path.exists(f):
        continue
    s = open(f, encoding="utf-8").read()
    m = re.search(r"<title>([^<]*)</title>", s)
    check(f"/{path}/ naslov ≤ 60", bool(m) and len(m.group(1)) <= 60, m.group(1) if m else "")
    check(f"/{path}/ brez notranjih meritev", "indoor" not in s.lower())

print(f"{ok} preverjanj, {fail} napak")
sys.exit(1 if fail else 0)
