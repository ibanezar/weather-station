#!/usr/bin/env python3
"""tools/test_lektura_scan.py — pravila lektura_scan.py: vsako ima pozitiven in negativen primer (ne sme ujeti pravilnega zapisa).
Zaženi: python3 tools/test_lektura_scan.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lektura_scan as L  # noqa: E402

fails = 0


def ids(text):
    return {h[0] for h in L.scan_text(text)}


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


CASES = [
    # (pravilo, slab zapis, dober zapis)
    ("odstotek-brez-presledka", "Vlažnost je 52,6% zjutraj.", "Vlažnost je 52,6 % zjutraj."),
    ("enota-brez-presledka", "Temperatura 33,6°C in 16,5mm dežja.", "Temperatura 33,6 °C in 16,5 mm dežja."),
    ("decimalna-pika", "Talna temperatura 15.0 °C je previsoka.", "Talna temperatura 15,0 °C je previsoka."),
    ("ura-z-dvopicjem", "Odčitek ob 8:04 zjutraj.", "Odčitek ob 8.04 zjutraj."),
    ("ravni-narekovaji", 'Rekel je "povprečno leto" in odšel.', "Rekel je »povprečno leto« in odšel."),
    ("ameriški-zaključek", "dolina se „napolni” z vročino", "dolina se „napolni“ z vročino"),
    ("vezaj-kot-pomislaj", "vodo - tak dan je pogosto", "vodo – tak dan je pogosto"),
    ("vezaj-kot-pomislaj", "suho -- skoraj brez dežja", "suho – skoraj brez dežja"),
    ("vezaj-v-obsegu", "pade pod 18-19 °C še ponoči", "pade pod 18–19 °C še ponoči"),
    ("podvojena-beseda", "To je pomembno pomembno za gobarje.", "To je pomembno za gobarje."),
    ("števnik-5-dneva", "Čez 5 dneva se ohladi.", "Čez 5 dni se ohladi."),
    ("števnik-1-dni", "Pozno ponoči je 1 dni suho.", "Pozno ponoči je 1 dan suho."),
    ("anglicizem", "Sprožil je trigger v modelu.", "Sprožil je sprožilec v modelu."),
]
for rid, bad, good in CASES:
    check(rid in ids(bad), f"{rid}: zazna »{bad}«")
    check(rid not in ids(good), f"{rid}: ne zazna pravilnega »{good}«")

# izjeme, ki ne smejo sprožiti
check("podvojena-beseda" not in ids("Če je je preveč, se valovi skrijejo; kot je je odšlo."), "podvojena: »je je« je pravilno (delitveni rodilnik)")
check("odstotek-brez-presledka" not in ids("Delež je 14 % od 100 %."), "odstotek: pravilen zapis")
check("anglicizem" not in ids("Pauly, D. (1995): Anecdotes and the shifting baseline syndrome of fisheries."), "anglicizem: angleški citat se izpusti")
check("enota-brez-presledka" not in ids("vir: https://example.si/podatki/12mm-slika"), "enota: URL ni besedilo (vezaj/pot)")
check("drug-slog-narekovajev" in ids("pravi „zadeti“ dogodek"), "narekovaji „…“ so informativno označeni")
check("ravni-narekovaji" not in ids("pravi „zadeti“ dogodek"), "narekovaji „…“ niso ravni")

# izrez besedila: atributi, skripte, tabela
html_ = ('<html><body><article><p>Pade 5 mm dežja.</p><a href="/x-18-19-dni.html" title="a - b">povezava</a>'
         '<script>var s = "12mm - 5%";</script><table><tr><td>28. 10.–7. 11.</td><td>26 mm</td></tr></table></article></body></html>')
t = L.article_text(html_)
check("12mm" not in t and "title" not in t, "izrez: skripta in atributi niso besedilo")
check("11. | 26 mm" in t or "11. |" in t, "izrez: celice tabele so ločene (datum + količina ne tvorita 11.26 mm)")
check("decimalna-pika" not in ids(t), "izrez: sosednji celici se ne zlijeta v decimalko")
print(f"\n{fails} razhajanj")
sys.exit(1 if fails else 0)
