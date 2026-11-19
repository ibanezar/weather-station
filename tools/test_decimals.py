#!/usr/bin/env python3
"""tools/test_decimals.py — osrednja normalizacija decimalne vejice v zavihkih (`_slDecText()` iz app.js).

JS se IZREŽE iz prave datoteke (isti pomočnik kot test_parity.py). Preverja, da pretvori decimalke (1–2 decimalki),
NE pa tisočic (»2.541 dni«), datumov, različic, poti, ID-jev in »CC BY 4.0«. Zaženi: python3 tools/test_decimals.py"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CASES = [
    # (vhod, pričakovano)
    ("7.5°C", "7,5°C"),
    ("Jan: 1.5 mm", "Jan: 1,5 mm"),
    ("Jan 2025: 1.37 kWh/m²/dan", "Jan 2025: 1,37 kWh/m²/dan"),
    ("+29.23", "+29,23"),
    ("-3.2°", "-3,2°"),
    ("Tmax 14.5 in Tmin 3.2", "Tmax 14,5 in Tmin 3,2"),
    ("ločljivost 0.25°", "ločljivost 0,25°"),
    ("(5.5)", "(5,5)"),
    # ostane nespremenjeno
    ("2.541 dni", "2.541 dni"),            # tisočica (3 števke)
    ("12.345.678", "12.345.678"),
    ("2.11.", "2.11."),                     # datum z zaključno piko
    ("12.3.2026", "12.3.2026"),
    ("pon 2.11. ob 10:30", "pon 2.11. ob 10:30"),
    ("CC BY 4.0", "CC BY 4.0"),
    ("v2.1", "v2.1"),
    ("Chart.js 4.4.1", "Chart.js 4.4.1"),
    ("https://x.si/a1.5/b", "https://x.si/a1.5/b"),
    ("#id1.5", "#id1.5"),
    ("meteo.arso.gov.si", "meteo.arso.gov.si"),
    ("Konec stavka je 5.", "Konec stavka je 5."),
    ("", ""),
]


def main():
    p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")],
                       input=json.dumps({"file": "app.js", "names": ["_SL_DEC", "_slDecText"], "prelude": "",
                                         "calls": [{"fn": "_slDecText", "args": [a]} for a, _ in CASES]}),
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    out = json.loads(p.stdout)
    if "error" in out:
        print("NAPAKA:", out["error"])
        return 1
    fails = 0
    for (a, want), got in zip(CASES, out["results"]):
        if got != want:
            fails += 1
            print(f"  ✗ {a!r}: pričakovano {want!r}, dobljeno {got!r}")
    # idempotenca: drugi prehod ne spremeni ničesar
    p2 = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")],
                        input=json.dumps({"file": "app.js", "names": ["_SL_DEC", "_slDecText"], "prelude": "",
                                          "calls": [{"fn": "_slDecText", "args": [w]} for _, w in CASES]}),
                        capture_output=True, text=True, cwd=ROOT, timeout=60)
    for (_, w), got in zip(CASES, json.loads(p2.stdout)["results"]):
        if got != w:
            fails += 1
            print(f"  ✗ ni idempotentno: {w!r} -> {got!r}")
    # preslikava emojijev: vsaka ikona mora biti v spritu naslovnice, krogi imajo barvo
    q = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")],
                       input=json.dumps({"file": "app.js", "names": ["_EMO_NORM", "_EMO_DOT"], "prelude": "",
                                         "calls": [{"expr": "JSON.stringify([_EMO_NORM,_EMO_DOT])"}]}),
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    norm, dot = json.loads(json.loads(q.stdout)["results"][0])
    sprite = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    for emo, name in norm.items():
        if f'id="i-{name}"' not in sprite:
            fails += 1
            print(f"  ✗ ikone {name} ({emo}) ni v spritu: dodaj v EXTRA v tools/emoji_to_icons.py in ga poženi")
    for emo, col in dot.items():
        if not (len(col) == 7 and col.startswith("#")):
            fails += 1
            print(f"  ✗ barva kroga {emo}: {col!r}")
    if set(norm) & set(dot):
        fails += 1
        print("  ✗ emoji je hkrati ikona in krog")
    print(f"{len(CASES) * 2 + len(norm) + len(dot)} preverjanj, {fails} napak")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
