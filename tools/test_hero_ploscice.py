#!/usr/bin/env python3
"""Hierarhija ploščic in lestvice vrednosti v hero kartici (4. 11. 2026, audit točki 8 in 9).

8: ploščice imajo dve ravni (`--hb-bg1/bd1/sh1` = glavna ploščica in »Danes«, `--hb-bg2/bd2/sh2` = meritve, podrobnosti, noga, hitra vprašanja);
   nobena ploščica v `.hero-b` ne sme več uporabljati skupne `--hero-bg`/`--sh-1`.
9: lestvice vrednosti (vlaga, veter, tlak, razpon dneva) so ENA nevtralna sekvenčna lestvica brez barvnega pomena; semantične barve imata samo UV in PM₂,₅ (razredi EAQI so pragovi),
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


def rules_with(css, selector):
    """Telesa VSEH pravil, v katerih je `selector` natanko eden od selektorjev (tudi v skupnem pravilu `a,b,c{...}`)."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in [x.strip() for x in m.group(1).split(",")]:
            out.append(m.group(2))
    return out


# ---- 8: ravni ploščic ----
for tok in ("--hb-bg1", "--hb-bd1", "--hb-sh1", "--hb-bg2", "--hb-bd2", "--hb-sh2"):
    check(len(re.findall(re.escape(tok) + r":", CSS)) >= 2, "raven ploščic: spremenljivka ni definirana za obe temi", tok)

base = rule(CSS, ".hero-b .hb-tile") or ""
check("var(--hb-bg2)" in base and "var(--hb-bd2)" in base and "var(--hb-sh2)" in base, "`.hero-b .hb-tile` ni raven 2", base)
l1 = rule(CSS, ".hero-b .hero-top.hb-tile") or ""
check("var(--hb-bg1)" in l1 and "var(--hb-bd1)" in l1 and "var(--hb-sh1)" in l1, "glavna ploščica ni raven 1", l1)
# »Danes« je raven 1 kot glavna ploščica: VSAKO pravilo, ki ga zadene in nastavlja podlago, rob ali senco, mora uporabiti spremenljivke ravni 1
# (prej: rule() je za oba selektorja vrnil isto skupno pravilo in je bila primerjava vedno resnična).
for sel in (".hero-b .hero-top.hb-tile", ".hero-b .hb-day.hb-tile"):
    found = rules_with(CSS, sel)
    check(len(found) >= 1, "raven 1: pravilo ni najdeno", sel)
    for body in found:
        for prop, var in (("background", "--hb-bg1"), ("border-color", "--hb-bd1"), ("box-shadow", "--hb-sh1")):
            if re.search(r"(^|;)\s*" + prop + r"\s*:", body):
                check(f"var({var})" in body, f"{sel}: `{prop}` ne uporablja {var}", body)
# in obe sta v istem pravilu (sicer se lahko ena razide)
check(any(".hero-b .hero-top.hb-tile" in m.group(1) and ".hero-b .hb-day.hb-tile" in m.group(1)
          for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS)), "»Danes« in glavna ploščica nista v istem pravilu ravni 1")
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

# ---- kritični CSS: display:contents (5. 11. 2026) ----
# `.hero-b .hero-left{display:contents}` nima lastne škatle, zato ga je critical_css.mjs izpustil in je bila glavna ploščica do prihoda
# celotnega CSS flex (159 px), potem mreža (180 px): CLS 0,17 na telefonu. Vsako hero pravilo z display:contents mora biti tudi v kritičnem CSS.
HTML = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
_m = re.search(r'<style id="critical-css">(.*?)</style>', HTML, re.S)
CRIT = _m.group(1) if _m else ""
check(bool(CRIT), "kritični CSS ni najden v index.html")
for sel in (".hero .hero-left", ".hero-b .hero-left"):
    full = [b for b in rules_with(CSS, sel) if "display:contents" in b.replace(" ", "")]
    crit = [b for b in rules_with(CRIT, sel) if "display:contents" in b.replace(" ", "")]
    check(bool(full) and bool(crit), f"{sel}{{display:contents}} manjka v kritičnem CSS (poženi node tools/critical_css.mjs)", f"celoten={len(full)} kritičen={len(crit)}")

# ---- 9: lestvice ----
SCALES = {"hum": "seq", "wind": "seq", "pres": "seq", "range": "seq", "uv": "semantic", "pm": "semantic", "rain": "fill", "moon": "depiction"}
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
    # nobeno drugo pravilo ne sme lestvici vsiliti drugačnega ozadja: pravil z --sc-bg, ki zadenejo selektor `.hm-scale-<k>`
    # (tudi v skupnem pravilu), je natanko eno -- skupno nevtralno. Prej je regex ujel samo zadnji selektor v seznamu (range).
    over = [b for b in rules_with(CSS, f".hm-scale-{k}") if "--sc-bg" in b]
    check(len(over) == 1, f"lestvica {k}: pravil z --sc-bg je {len(over)}, mora biti natanko eno (skupno nevtralno)", str(over))
    # tudi sestavljeni selektorji (`.hm-scale-<k>.x`, `[data-…] .hm-scale-<k>`), ki bi ozadje prepisali
    extra = [sel.strip() for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS) if "--sc-bg" in m.group(2)
             for sel in m.group(1).split(",") if re.search(r"\.hm-scale-" + k + r"(?![a-z-])", sel) and sel.strip() != f".hm-scale-{k}"]
    check(not extra, f"lestvica {k}: sestavljen selektor z --sc-bg", str(extra))

print(f"{checks} preverjanj, {len(fails)} napak")
for f in fails:
    print("  ✗", f)
sys.exit(1 if fails else 0)
