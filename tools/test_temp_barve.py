#!/usr/bin/env python3
"""Barvna skala temperature je podatkovna barva, ne znamčna (4. 11. 2026, audit točka 7).

Hladni pas (0-8 °C) je bil #67e8f9: 10 ΔE od cianovega »rec« v logotipu (#22d3ee), zato je ista barva hkrati pomenila »znamka« in
»hladno« (temperatura ima v hero kartici še žarenje). Zdaj nobena stopnja skale `tempColor()` ne sme biti bliže znamčnemu cianu kot MIN_DE_BRAND
(CIE Lab ΔE76), sosednji stopnji morata biti razločljivi, vsaka dovolj kontrastna na podlagi kartice; hladni stopnji v `feelsStyle()` in
na kartici za deljenje sta isti barvi kot v skali.
"""
import math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_parity import js  # noqa: E402  (izrez JS iz prave app.js)

ROOT = os.path.dirname(HERE)
CSS = open(os.path.join(ROOT, "style.css"), encoding="utf-8").read()
APP = open(os.path.join(ROOT, "app.js"), encoding="utf-8").read()

# znamčni cian (logotip »rec«, --cyan) in podlaga hero kartice po temah (izmerjeno 4. 11. 2026)
BRAND_CYAN = {"dark": "#22d3ee", "light": "#0e7490"}
CARD_BG = {"dark": "#0a0f1c", "light": "#f8fcfe"}
MIN_DE_BRAND = 25.0
MIN_DE_ADJACENT = 12.0   # obstoječi par 25/30 °C v svetli temi (#b45309/#c2410c) je 13,8; ostali pari so nad 20
MIN_CONTRAST = 4.5
SAMPLES = [-5, 4, 12, 18, 25, 30, 40]   # po eden iz vsake stopnje: <0, <8, <15, <22, <28, <35, ≥35

fails, checks = [], 0


def check(ok, name, detail=""):
    global checks
    checks += 1
    if not ok:
        fails.append(f"{name} {detail}")


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lab(h):
    r, g, b = [lin(x) for x in rgb(h)]
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def de(a, b):
    return math.dist(lab(a), lab(b))


def lum(h):
    r, g, b = [lin(x) for x in rgb(h)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


# znamčna barva je res še taka (sicer posodobi BRAND_CYAN in preveri ΔE znova)
check(f"--cyan:{BRAND_CYAN['dark']}" in CSS, "znamčni cian (temna tema) se je spremenil v style.css", BRAND_CYAN["dark"])
check(f"--cyan:{BRAND_CYAN['light']}" in CSS, "znamčni cian (svetla tema) se je spremenil v style.css", BRAND_CYAN["light"])

pre = "var _dark=true;function isDark(){return _dark}"
bands = {}
for theme in ("dark", "light"):
    calls = [{"expr": f"(function(){{_dark={'true' if theme == 'dark' else 'false'};return tempColor({t});}})()"} for t in SAMPLES]
    bands[theme] = js("app.js", ["tempColor"], calls, prelude=pre)

for theme, cols in bands.items():
    check(all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in cols), "tempColor vrne #rrggbb", f"{theme}: {cols}")
    for t, c in zip(SAMPLES, cols):
        d = de(c, BRAND_CYAN[theme])
        check(d >= MIN_DE_BRAND, f"skala temperature preblizu znamčnemu cianu ({theme}):", f"{t} °C {c} ΔE {d:.1f} < {MIN_DE_BRAND}")
        k = contrast(c, CARD_BG[theme])
        check(k >= MIN_CONTRAST, f"kontrast stopnje na kartici ({theme}):", f"{t} °C {c} {k:.1f}:1 < {MIN_CONTRAST}")
    for (t1, c1), (t2, c2) in zip(zip(SAMPLES, cols), zip(SAMPLES[1:], cols[1:])):
        d = de(c1, c2)
        check(d >= MIN_DE_ADJACENT, f"sosednji stopnji nista razločljivi ({theme}):", f"{t1} °C {c1} / {t2} °C {c2} ΔE {d:.1f}")

# feelsStyle (oznaka občutka) ima hladni stopnji v isti barvi kot skala
for theme in ("dark", "light"):
    calls = [{"expr": f"(function(){{_dark={'true' if theme == 'dark' else 'false'};return feelsStyle({t}).c;}})()"} for t in (-5, 4)]
    got = js("app.js", ["feelsStyle"], calls, prelude=pre)
    for t, g, want in zip((-5, 4), got, bands[theme][:2]):
        check(g == want, f"feelsStyle ({theme}) {t} °C ni v barvi skale:", f"{g} != {want}")

# kartica za deljenje (vedno temna paleta): hladni stopnji kot v temni skali
m = re.search(r"t < 0\s*\? '(#[0-9a-f]{6})' : t < 8\s*\? '(#[0-9a-f]{6})'", APP)
check(bool(m), "kartica za deljenje: skala ni najdena")
if m:
    check([m.group(1), m.group(2)] == bands["dark"][:2], "kartica za deljenje ni v barvi temne skale:", f"{m.groups()} != {bands['dark'][:2]}")

print(f"{checks} preverjanj, {len(fails)} napak")
for f in fails:
    print("  ✗", f)
sys.exit(1 if fails else 0)
