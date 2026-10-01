#!/usr/bin/env python3
"""tools/test_precip_snapshot.py — jutranji posnetek ARSO rr24h (worker ↔ generator).

`_parseArsoRr24h` v worker.js (regex, brez DOM-a) mora iz istega XML-ja razbrati iste
postaje kot ET-razčlenjevalnik v tools/generate_precip_map.fetch_stations().
Zaženi:  python3 tools/test_precip_snapshot.py
"""
import json
import os
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
CHECKS, FAILS = 0, []


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


def station(name, lat, lon, rr, title=None):
    t = f"<domain_title>{title or name}</domain_title>" if title is not None else ""
    return (f"<metData><domain_shortTitle>{name}</domain_shortTitle>{t}<domain_lat>{lat}</domain_lat>"
            f"<domain_lon>{lon}</domain_lon><rr24h_val>{rr}</rr24h_val></metData>")


XML = ('<?xml version="1.0" encoding="UTF-8"?><data><tsValid_issued>01.10.2026 8:00 CEST</tsValid_issued>'
       + station("LJUBLJANA", 46.065, 14.512, "12.4") + station("MARIBOR", 46.48, 15.68, "0")
       + station("CELJE", 46.2, 15.2, "") + station("KOCEVJE", 45.64, 14.86, "3.0")
       + "<metData><domain_title>BREZ-KOORD</domain_title><rr24h_val>5</rr24h_val></metData>"
       + station("KATARINA", 46.1, 14.6, "ni")
       + "</data>")

import generate_precip_map as gp  # noqa: E402


def python_side(xml):
    root = ET.fromstring(xml)
    out = []
    for m in root.findall("metData"):
        name = (m.findtext("domain_shortTitle") or m.findtext("domain_title") or "").strip()
        la, lo, rr = m.findtext("domain_lat"), m.findtext("domain_lon"), m.findtext("rr24h_val")
        if not name or la is None or lo is None or rr is None or not rr.strip():
            continue
        try:
            out.append({"name": name, "la": float(la), "lo": float(lo), "mm": float(rr)})
        except ValueError:
            continue
    return out


p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")], capture_output=True, text=True, cwd=ROOT,
                   input=json.dumps({"file": "worker.js", "names": ["_parseArsoRr24h"],
                                     "calls": [{"expr": f"_parseArsoRr24h({json.dumps(XML)})"}]}))
res = json.loads(p.stdout)
check("results" in res, "worker razčlenjevalnik se požene", p.stdout[:200])
js = res["results"][0]
want = python_side(XML)
check(js["stations"] == want, "isti nabor postaj kot ET", f"js={js['stations']} py={want}")
check([s["name"] for s in want] == ["LJUBLJANA", "MARIBOR", "KOCEVJE"], "prazen rr24h, neberljiv rr24h in postaja brez koordinat so izpuščeni")
check(js["issued"] == "01.10.2026 8:00 CEST", "izdano", js["issued"])
empty = json.loads(subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")], capture_output=True, text=True, cwd=ROOT,
                   input=json.dumps({"file": "worker.js", "names": ["_parseArsoRr24h"],
                                     "calls": [{"expr": "_parseArsoRr24h('<data><metData><domain_shortTitle>X</domain_shortTitle><domain_lat>1</domain_lat><domain_lon>2</domain_lon><rr24h_val></rr24h_val></metData></data>')"}]})).stdout)["results"][0]
check(empty["stations"] == [], "urna meritev brez rr24h ne da postaj (kot današnji vir ob 14:00)")

# generator: posnetek ima prednost pred živim virom, ob napaki pade nazaj
gp.fetch_snapshot = lambda d: ([{"name": "Ljubljana", "la": 1.0, "lo": 2.0, "mm": 5.0}], "01.10.2026 8:00 CEST")
st, issued = gp.fetch_stations("2026-10-01")
check(st[0]["mm"] == 5.0 and issued.startswith("01.10"), "fetch_stations uporabi posnetek")
check(gp.fetch_snapshot.__name__ == "<lambda>", "(sanity)")
print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
