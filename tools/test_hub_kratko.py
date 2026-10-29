#!/usr/bin/env python3
"""tools/test_hub_kratko.py — blok »Na kratko« na /klima/, /padavine/, /temperatura/ (seo_smart_routine.kratko_html).
Strani se generirajo v pomnilnik (write_page nadomeščen), številke v bloku morajo biti iste kot v FAQ / tabelah iste strani
in izračunane iz history.json. Zaženi: python3 tools/test_hub_kratko.py"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_smart_routine as S  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


pages = {}
S.write_page = lambda rel, html, force=True: pages.__setitem__(rel, html)
H = json.load(open(os.path.join(S.ROOT, "history.json"), encoding="utf-8"))
# isti vhod kot main(): celoten history.json (compute_climate ga sam filtrira)
normals, a_prec, a_frost, a_hot, full_years = S.compute_climate(H)
last = max(H)
urls = []
S.gen_klima(normals, a_prec, a_frost, a_hot, full_years, last, urls)
S.gen_padavine(normals, a_prec, full_years, last, urls)
S.gen_temperatura(normals, a_frost, a_hot, full_years, last, urls)


def kratko(rel):
    html = pages[rel]
    m = re.search(r"<strong>Na kratko:</strong>(.*?)</p>", html, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else None


avg_prec = round(sum(a_prec[y] for y in full_years) / len(full_years))
avg_frost = round(sum(a_frost[y] for y in full_years) / len(full_years))
k = kratko("klima/index.html")
check(k is not None, "klima: blok Na kratko obstaja")
check(f"povprečno {avg_prec} mm padavin na leto" in (k or ""), f"klima: povprečne letne padavine natanko {avg_prec} mm")
check(f"povprečno {avg_frost}" in (k or ""), f"klima: dni z mrazom {avg_frost}")
check("Posodobljeno:" in (k or ""), "klima: vidna oznaka Posodobljeno")
check(str(avg_prec) in re.sub(r"<[^>]+>", "", pages["klima/index.html"].split("pogosta-vprasanja-klima")[1]), "klima: ista letna količina v FAQ")
check("polnih letih" in (k or "") and str(full_years[0]) in k and str(full_years[-1]) in k, "klima: obdobje polnih let")

k = kratko("padavine/index.html")
check(k is not None and f"{avg_prec}" in k, "padavine: blok z isto povprečno letno količino")
check(k is not None and "najbolj mokro" in k and "najbolj suho" in k, "padavine: najbolj mokro in suho leto")
wet = max(full_years, key=lambda y: a_prec[y]); dry = min(full_years, key=lambda y: a_prec[y])
check(k is not None and f"najbolj mokro {wet}: {round(a_prec[wet])} mm" in k and f"najbolj suho {dry}: {round(a_prec[dry])} mm" in k,
      f"padavine: najbolj mokro {wet} in najbolj suho {dry} leto z natančnima vrednostma")
check(k is not None and f"padavine: povprečno {avg_prec} mm" not in k and f"povprečno {avg_prec} mm padavin na leto" in k, "padavine: povprečje natanko")
check(k is not None and "Posodobljeno:" in k, "padavine: vidna oznaka Posodobljeno")
ytd = a_prec.get(int(last[:4]))
check(k is not None and (ytd is None or f"{round(ytd)} mm" in k), "padavine: letos do danes")

k = kratko("temperatura/index.html")
check(k is not None and "Rekordi postaje" in k and "dni z mrazom" in k, "temperatura: rekordi in mrzli dnevi")
tmax = max(v["tempHigh"] for v in H.values() if v.get("tempHigh") is not None)
tmin = min(v["tempLow"] for v in H.values() if v.get("tempLow") is not None)
check(k is not None and S.num(tmax) in k and S.num(tmin) in k, f"temperatura: absolutna rekorda {S.num(tmax)} / {S.num(tmin)} °C")
check(k is not None and "Posodobljeno:" in k, "temperatura: vidna oznaka Posodobljeno")
# /rekord/ (generate_seo_pages.gen_records_page): preveri objavljeno stran proti history.json
rek = open(os.path.join(S.ROOT, "rekord", "index.html"), encoding="utf-8").read()
m = re.search(r"<strong>Na kratko:</strong>(.*?)</p>", rek, re.S)
kr = re.sub(r"<[^>]+>", "", m.group(1)) if m else ""
check(bool(kr), "rekord: blok Na kratko obstaja")
check(S.num(tmax) in kr and S.num(tmin) in kr, f"rekord: absolutna rekorda {S.num(tmax)} / {S.num(tmin)} °C")
check("Posodobljeno:" in kr, "rekord: vidna oznaka Posodobljeno")
pmax = max(v["precipTotal"] for v in H.values() if v.get("precipTotal") is not None and v.get("src") != "era5")
check(S.num(pmax) in kr, f"rekord: dnevni rekord padavin {S.num(pmax)} mm")
check("indoor" not in rek.lower(), "rekord: brez indoor")
for rel, html in pages.items():
    check("indoor" not in html.lower() and not re.search(r"\bNone\b|\bnan\b", re.sub(r"<[^>]+>", " ", html.split("Na kratko")[1][:900])), f"{rel}: brez indoor/None/nan v bloku")
print(f"\n{fails} razhajanj")
sys.exit(1 if fails else 0)
