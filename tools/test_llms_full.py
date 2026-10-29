#!/usr/bin/env python3
"""tools/test_llms_full.py — llms-full.txt (generate_llms_full.py): ključne strani so notri, brez praznih vnosov, brez
notranjih meritev, razumne velikosti, llms.txt povezuje nanj. Zaženi: python3 tools/test_llms_full.py"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_llms_full as g  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


text, n = g.build()
check(n >= 80, f"vsaj 80 strani ({n})")
check(len(text) < 300_000, f"velikost pod 300 kB ({len(text) // 1024} kB)")
for url in ("https://meteorec.si/vreme-recica-ob-savinji/", "https://meteorec.si/tocnost-napovedi/", "https://meteorec.si/gobarska-napoved/",
            "https://meteorec.si/vodostaj-savinje/", "https://meteorec.si/nevihte/"):
    check(url in text, f"vsebuje {url}")
entries = re.split(r"\n## ", text)[1:]
check(len(entries) == n, "število vnosov = število strani")
for e in entries:
    head = e.split("\n", 2)
    check(head[1].startswith("https://meteorec.si/"), f"vnos ima URL: {head[0][:40]}")
    check(len(e) > 120, f"vnos ni prazen: {head[0][:40]}")
low = text.lower()
check("indoor" not in low and not re.search(r"notranj\w*\s+(senzor|merilnik|termometer)", low), "brez notranjih meritev")
check(not re.search(r"\bNone\b|\bnan\b|undefined|\{\{", text), "brez None/nan/undefined")
check("llms-full.txt" in open(os.path.join(g.ROOT, "llms.txt"), encoding="utf-8").read(), "llms.txt povezuje na llms-full.txt")
# določenost: dvakrat zaporedoma isto
check(g.build()[0] == text, "izpis je deterministična")
# razčlenjevanje: stran brez opisa in besedila ni vnos; stran z odstavkom je
check(g.entry_from_html("<html><title>X</title><body><h1>A</h1><nav><p>" + "x" * 80 + "</p></nav></body></html>", "/a/") is None,
      "stran brez opisa in odstavkov ni vnos (navigacija se ne šteje)")
e = g.entry_from_html("<html><title>Naslov</title><meta name=\"description\" content=\"Opis\"><body><h1>A</h1><p>" + "Besedilo odstavka. " * 6 + "</p></body></html>", "/a/")
check(e and e["desc"] == "Opis" and len(e["paras"]) == 1 and e["url"] == "https://meteorec.si/a/", "stran z opisom in odstavkom je vnos")
e = g.entry_from_html("<html><title>T</title><body><h1>A</h1><!-- WX-STATIC:START x --><p>" + "Meritev 12 °C. " * 8 + "</p><!-- WX-STATIC:END --></body></html>", "/a/")
check(e is None, "blok živih meritev (WX-STATIC) je izpuščen")
print(f"\n{fails} razhajanj")
sys.exit(1 if fails else 0)
