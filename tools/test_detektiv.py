#!/usr/bin/env python3
"""Preizkus igre »Gobarski detektiv« (igra/gobarski-detektiv/detektiv.js):
model (sestava kroga, ocenjevanje), popolnost podatkov in usklajenost imen ter
užitnosti z bazo vrst (species_rules.yaml). Model teče v Nodu, brez DOM-a."""
import json, os, subprocess, sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "igra", "gobarski-detektiv", "detektiv.js")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"✗ {name} {detail}")


def node(expr):
    code = f"const m=require({json.dumps(JS)});console.log(JSON.stringify({expr}))"
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr)
        sys.exit(1)
    return json.loads(r.stdout)


pari = node("m.PARI")
sledi = node("m.SLEDI")
baza = {s["name_sl"]: s for s in yaml.safe_load(open(os.path.join(ROOT, "species_rules.yaml"), encoding="utf-8"))["species"]}
EDIB = {"u": "Užitna", "p": "Pogojno užitna", "n": "Neužitna", "s": "Strupena", "z": "Zelo strupena", "d": "Smrtno strupena"}
KAT = {"u": "uzitne", "p": "pogojno-uzitne", "n": "neuzitne", "s": "strupene", "z": "strupene", "d": "strupene"}

# 1) Vsak par ima dve vrsti, vse sledi, razlago in uvod; id-ji so enolični.
ids = set()
for p in pari:
    check(f"par {p['id']}: dve vrsti", len(p["vrste"]) == 2)
    check(f"par {p['id']}: uvod in razlaga", bool(p["uvod"]) and bool(p["razlaga"]))
    for v in p["vrste"]:
        check(f"vrsta {v['id']} enolična", v["id"] not in ids)
        ids.add(v["id"])
        for k in sledi:
            check(f"{v['id']}: sled {k}", bool(v["sledi"].get(k)))
        check(f"{v['id']}: spec ima klobuk/nogo", all(k in v["spec"] for k in ("klobuk", "noga", "sirina", "visina", "nogaV")))

# 2) Ime in užitnost sta ista kot v bazi vrst; povezava kaže v pravo skupino.
for p in pari:
    for v in p["vrste"]:
        b = baza.get(v["ime"])
        check(f"{v['ime']}: je v bazi", b is not None)
        if b:
            check(f"{v['ime']}: užitnost {EDIB[v['edib']]} = {b['edibility']}", EDIB[v["edib"]] == b["edibility"])
            check(f"{v['ime']}: skupina {v['kat']}", v["kat"] == KAT[v["edib"]])

# 3) Krog: KROG_DOLZINA različnih parov, resnica iz para, ponudba = par + tuja vrsta.
KROG = node("m.KROG_DOLZINA")
check("v bazi igre je vsaj 30 vrst", sum(len(p["vrste"]) for p in pari) >= 30)
for seed in range(40):
    krog = node(f"(()=>{{let s={seed}+1;const r=()=>{{s=(s*16807)%2147483647;return s/2147483647}};return m.sestaviKrog(r)}})()")
    check("krog: dolžina in različni pari", len(krog) == KROG and len({k["par"] for k in krog}) == KROG)
    for k in krog:
        par = next(p for p in pari if p["id"] == k["par"])
        parids = {v["id"] for v in par["vrste"]}
        check("resnica iz para", k["resnica"] in parids)
        check("ponudba 3 različne", len(set(k["ponudba"])) == 3 and parids <= set(k["ponudba"]))
        check("resnica v ponudbi", k["resnica"] in k["ponudba"])

# 3b) Čez veliko krogov se pojavi vsak par in vsaka vrsta (žrebanje ne zanemari nobenega).
vidni_pari, vidne_vrste = set(), set()
# Math.random (ne šibek LCG iz zgornjih krogov: pri majhnem semenu so prve vrednosti skoraj enake)
for k in node("Array.from({length:300},()=>m.sestaviKrog()).flat()"):
    vidni_pari.add(k["par"]); vidne_vrste.add(k["resnica"])
check("vsak par se pojavi", vidni_pari == {p["id"] for p in pari})
check("vsaka vrsta je kdaj resnica", vidne_vrste == ids)

# 4) Ocenjevanje.
def ocena(par, resnica, izbrana, n):
    return node(f"m.oceni({{par:{json.dumps(par)},resnica:{json.dumps(resnica)}}},{json.dumps(izbrana)},{n})")

o = ocena("goban", "jurcek", "jurcek", 4)
check("pravilno + bonus = 3", o["tocke"] == 3 and o["bonus"])
o = ocena("goban", "jurcek", "jurcek", 3)
check("pravilno brez bonusa = 2", o["tocke"] == 2 and not o["bonus"])
o = ocena("goban", "jurcek", "zolcasti", 6)
check("napačno = 0", o["tocke"] == 0 and not o["prav"])
o = ocena("kukmak", "zelena", "kukmak", 6)
check("užitna namesto smrtno strupene = nevarna napaka", o["nevarna"] and o["tocke"] == 0)
o = ocena("kukmak", "kukmak", "zelena", 6)
check("strupena namesto užitne ni nevarna (ne bi je pojedel)", not o["nevarna"])
o = ocena("goban", "zolcasti", "jurcek", 2)
check("jurček namesto žolčastega = nevarna napaka", o["nevarna"])
check("največ točk", node("m.NAJVEC_TOCK") == 3 * KROG)
check("naziv 0 točk", "Začetnik" in node("m.naziv(0)"))
check("naziv max", node("m.naziv(m.NAJVEC_TOCK)") == "Mojster detektiv")

# 4b) Povzetek vremena (kartica z IREICA1).
pv = node("m.povzetekVremena([{date:'2026-10-16',tmax:14.2,tmin:5.1,precip:0},{date:'2026-10-17',tmax:19.4,tmin:4.6,precip:0.1},{date:'2026-10-18',tmax:12,tmin:7,precip:6.4}])")
check("povzetek vremena", pv == {"n": 3, "tmin": 4.6, "tmax": 19.4, "dez": 6.5, "dniDez": 1, "zadnjiDez": "2026-10-18", "zadnji": "2026-10-18"}, str(pv))
check("brez dni ni povzetka", node("[m.povzetekVremena([]), m.povzetekVremena(null)]") == [None, None])

# 5) Opozorilo je na strani in v igri.
html = open(os.path.join(ROOT, "igra", "gobarski-detektiv", "index.html"), encoding="utf-8").read()
check("opozorilo na strani", 'class="gd-warning"' in html and "ne uživaj" in html)
check("opozorilo ob koncu igre", "gd-final-warning" in open(JS, encoding="utf-8").read())
n_vrst = sum(len(p["vrste"]) for p in pari)
check("generator navaja pravo število vrst in parov", f"{n_vrst} vrst v {len(pari)} parih" in html, f"({n_vrst}/{len(pari)})")
check("lang=sl", '<html lang="sl">' in html)
check("brez notranjih meritev", "indoor" not in html.lower() and "indoor" not in open(JS, encoding="utf-8").read().lower())

print(f"{ok} preverjanj uspelo, {fail} neuspelih")
sys.exit(1 if fail else 0)
