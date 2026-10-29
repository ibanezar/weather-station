#!/usr/bin/env python3
"""Strani, ki prikazujejo podatke ARSO, morajo imeti navedbo vira (ARSO: 'Vir: Agencija
Republike Slovenije za okolje' ali 'Vir: ARSO'; 14. člen ZDMHS, meteo.arso.gov.si/.../copyright.html)."""
import re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = ["tocnost-napovedi/index.html", "test-napovedi/index.html",
         "meteogasilec/vodotoki/index.html", "vodostaj-savinje/index.html",
         "padavine-karta/index.html", "meteogasilec/index.html", "toca/index.html", "nevihte/index.html"]
OK = re.compile(r"(Vir[a-z]*(?:<[^>]+>|[^<]){0,60}(ARSO|Agencij\w+ (RS|Republike Slovenije) za okolje))"
                r"|(Agencija Republike Slovenije za okolje)", re.I)
bad = [p for p in PAGES if (ROOT / p).exists() and not OK.search((ROOT / p).read_text(encoding="utf-8"))]
for p in bad:
    print("manjka navedba vira ARSO:", p)
print("OK" if not bad else f"{len(bad)} strani brez navedbe")
sys.exit(1 if bad else 0)
