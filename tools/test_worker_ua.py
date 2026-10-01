#!/usr/bin/env python3
"""tools/test_worker_ua.py — vsak klic workerja iz Pythona mora poslati User-Agent.

Cloudflare privzeti »Python-urllib/3.x« zavrne s 403 (preverjeno 1. 10. 2026). Tak klic je
tiho pokvaril jutranji povzetek (403 je izgledal kot napačno geslo), branje jutranjega
posnetka padavin, preverjanje nevihtne karte in branje /health — vsi so ob napaki samo
padli nazaj ali javili »nedosegljivo«. Test poišče vsak `Request(`/`urlopen(` v tools/*.py,
katerega argument omenja worker, in zahteva User-Agent v istem klicu.
Zaženi:  python3 tools/test_worker_ua.py
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WORKER_HINT = re.compile(r"WORKER|workers\.dev|PROXY")
bad = []
checked = 0
for path in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
    if os.path.basename(path) == "test_worker_ua.py":
        continue
    src = open(path, encoding="utf-8").read()
    for m in re.finditer(r"urllib\.request\.(Request|urlopen)\(", src):
        # argument klica do zaključnega oklepaja (dovolj za ena- ali večvrstične klice)
        depth, i = 1, m.end()
        while i < len(src) and depth:
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        arg = src[m.end():i]
        first = arg.split(",")[0]
        if not WORKER_HINT.search(first):
            continue
        if m.group(1) == "urlopen" and not first.strip().startswith(("f\"", "f'", "\"", "'")):
            continue  # urlopen(req) — glava je na Request zgoraj
        checked += 1
        if "User-Agent" not in arg and "UA" not in arg:
            line = src.count("\n", 0, m.start()) + 1
            bad.append(f"{os.path.relpath(path, os.path.dirname(ROOT))}:{line}")
for b in bad:
    print(f"  ✗ klic workerja brez User-Agent: {b}")
print(f"\n{checked} klicev workerja, {len(bad)} brez User-Agent")
sys.exit(1 if bad or not checked else 0)
