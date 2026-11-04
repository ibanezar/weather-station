#!/usr/bin/env python3
"""Hierarhija ploščic in lestvice vrednosti v hero kartici (4. 11. 2026, audit točki 8 in 9).

8: ploščice imajo dve ravni (`--hb-bg1/bd1/sh1` = glavna ploščica in »Danes«, `--hb-bg2/bd2/sh2` = meritve, podrobnosti, noga, hitra vprašanja);
   nobena ploščica v `.hero-b` ne sme več uporabljati skupne `--hero-bg`/`--sh-1`.
9: lestvice vrednosti (vlaga, veter, tlak, razpon dneva) so ENA nevtralna sekvenčna lestvica brez barvnega pomena; semantične barve ima samo UV,
   dež je polnilo količine, luna je upodobitev. Nova lestvica mora biti v seznamu SCALES, da je odločitev zavestna.

Tudi: pravila ravni so v minificiranem `style.min.css` (clean-css 5.3.3 je ob drugačnem vrstnem redu tiho izpustil `.hero-b .hb-tile`).
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = re.sub(r"/\*.*?\*/", "", open(os.path.join(ROOT, "style.css"), encoding="utf-8").read(), flags=re.S)  # brez komentarjev
MIN = open(os.path.join(ROOT, "style.min.css"), encoding="utf-8").read()

fails, checks = [], 0


def check(ok, name, detail=""):
    global checks
    checks += 1
    if not ok:
        fails.append(f"{name} {detail}")


def rule(css, selector_start):
    """Telo prvega pravila, katerega seznam selektorjev vsebuje `selector_start` (brez @media)."""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sels = [x.strip() for x in m.group(1).split(",")]
        if any(s.endswith(selector_start) or s == selector_start for s in sels):
            return m.group(2)
    return None


# ---- 8: ravni ploščic ----
for tok in ("--hb-bg1", "--hb-bd1", "--hb-sh1", "--hb-bg2", "--hb-bd2", "--hb-sh2"):
    check(len(re.findall(re.escape(tok) + r":", CSS)) >= 2, "raven ploščic: spremenljivka ni definirana za obe temi", tok)

base = rule(CSS, ".hero-b .hb-tile") or ""
check("var(--hb-bg2)" in base and "var(--hb-bd2)" in base and "var(--hb-sh2)" in base, "`.hero-b .hb-tile` ni raven 2", base)
l1 = rule(CSS, ".hero-b .hero-top.hb-tile") or ""
check("var(--hb-bg1)" in l1 and "var(--hb-bd1)" in l1 and "var(--hb-sh1)" in l1, "glavna ploščica ni raven 1", l1)
l1b = rule(CSS, ".hero-b .hb-day.hb-tile") or ""
check(l1b == l1, "»Danes« nima enakega sloga kot glavna ploščica", l1b)
hm = rule(CSS, ".hero-b .hm") or ""
check("var(--hb-bg2)" in hm and "var(--hero-bg)" not in hm and "var(--sh-1)" not in hm, "`.hero-b .hm` ni raven 2", hm)
summ = rule(CSS, ".hb-more>summary") or ""
check("var(--hb-bg2)" in summ, "»Več podrobnosti« ni raven 2", summ)
# raven 1 mora biti res močnejša: senca ima, raven 2 je ravna
check(re.search(r"--hb-sh2:\s*none", CSS) is not None, "raven 2 mora biti brez sence")
check(re.search(r"--hb-sh1:\s*0 \d+px \d+px", CSS) is not None, "raven 1 mora imeti senco")

# minificirani CSS vsebuje pravila ravni
check(".hero-b .hb-tile{background:var(--hb-bg2)" in MIN, "style.min.css: manjka `.hero-b .hb-tile` (poženi npm run minify; clean-css ga lahko izpusti)")
check("background:var(--hb-bg1)" in MIN and "hb-day.hb-tile" in MIN, "style.min.css: manjka raven 1")
check("--hb-bg2:rgba(255,255,255" in MIN and "--hb-bg2:rgba(12,18,32" in MIN, "style.min.css: manjkajo spremenljivke ravni")

# ---- 9: lestvice ----
SCALES = {"hum": "seq", "wind": "seq", "pres": "seq", "range": "seq", "uv": "semantic", "rain": "fill", "moon": "depiction"}
found = set(re.findall(r"\.hm-scale-([a-z]+)\s*[{,>:]", CSS))
check(found <= set(SCALES), "nova lestvica brez odločitve (dodaj v SCALES v testu):", str(sorted(found - set(SCALES))))
seq_rule = None
for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
    sels = [x.strip() for x in m.group(1).split(",")]
    if ".hm-scale-hum" in sels:
        seq_rule = (sels, m.group(2))
        break
check(seq_rule is not None, "nevtralna lestvica: pravilo ni najdeno")
if seq_rule:
    sels, body = seq_rule
    for k in ("hum", "wind", "pres", "range"):
        check(f".hm-scale-{k}" in sels, "lestvica ni v skupnem nevtralnem pravilu:", k)
    check(not re.search(r"#[0-9a-fA-F]{3,6}\b", body), "nevtralna lestvica ima barvo s pomenom (hex):", body)
    check("var(--text)" in body and "var(--amber)" not in body and "var(--purple)" not in body and "var(--c-cool)" not in body, "nevtralna lestvica mora izhajati iz barve besedila", body)
uv = rule(CSS, ".hm-scale-uv") or ""
check("#22c55e" in uv and "#ef4444" in uv, "UV ima semantične barve (prag)", uv)
for k in ("hum", "wind", "pres", "range"):
    # nobeno drugo pravilo ne sme lestvici vsiliti drugačnega ozadja
    others = [m.group(0) for m in re.finditer(r"[^{}]*\.hm-scale-" + k + r"\s*\{[^{}]*--sc-bg:[^{}]*\}", CSS)]
    check(len(others) <= 1, f"lestvica {k} ima več pravil za --sc-bg", str(len(others)))

print(f"{checks} preverjanj, {len(fails)} napak")
for f in fails:
    print("  ✗", f)
sys.exit(1 if fails else 0)
