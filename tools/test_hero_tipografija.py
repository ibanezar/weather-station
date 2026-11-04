#!/usr/bin/env python3
"""Tipografska lestvica hero kartice (4. 11. 2026, audit točka 6).

Vsako pravilo v style.css, ki velja za hero kartico (`.hero-b …`, stolpci grafa `.hsc-col`, hitra vprašanja `.qa-…`, gumba `.sc-btn`),
sme velikost pisave izraziti samo z lestvico `--fs-xs/sm/md/lg/val/val-wide/xl` (ali relativno: em, %, inherit). Pred tem je bilo v kartici 18
velikosti (deset med 10 in 14 px) in ~40 besedil pod 12 px. Prikazne številke (temperatura, ikone) so izjema in so naštete.

Tudi: lestvica je v style.css definirana, najmanjša stopnja je 12 px, in v hero kartici ni nobenega drobnega vgrajenega font-size
(razen enot, ki jih CSS preglasi).
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(ROOT, "style.css"), encoding="utf-8").read()

TOKENS = {"--fs-xs": 12, "--fs-sm": 13, "--fs-md": 16, "--fs-lg": 20, "--fs-val": 24, "--fs-val-wide": 28, "--fs-xl": 32}
# Prikazne številke in ikone: velikost ni besedilo v lestvici.
DISPLAY_OK = (".temp-huge", ".hero-icon", ".hb-icon", ".dfc-icon", ".qa-art", ".temp-unit-sup", ".sc-icon", "#cond-icon", ".hm-ic")
SCOPE = re.compile(r"(^|[\s,>+~])(\.hero-b\b|\.hsc-col\b|\.qa-(pill|tl|tv|ts|tm)\b|\.sc-btn\b|\.sc-desc\b)")

fails = []
checks = 0


def check(ok, name, detail=""):
    global checks
    checks += 1
    if not ok:
        fails.append(f"{name} {detail}")


def rules(css):
    """Vrne (selektor, telo) za vsako pravilo, tudi znotraj @media."""
    out, i, n = [], 0, len(css)
    stack = []
    start = 0
    while i < n:
        c = css[i]
        if css.startswith("/*", i):
            j = css.find("*/", i + 2)
            i = j + 2 if j >= 0 else n
            start = i
            continue
        if c == "{":
            head = css[start:i].strip()
            if head.startswith("@media") or head.startswith("@supports") or head.startswith("@container"):
                stack.append("at")
                start = i + 1
            else:
                depth, j = 1, i + 1
                while j < n and depth:
                    if css[j] == "{":
                        depth += 1
                    elif css[j] == "}":
                        depth -= 1
                    j += 1
                out.append((head, css[i + 1:j - 1]))
                i = j
                start = i
                continue
        elif c == "}":
            if stack:
                stack.pop()
            start = i + 1
        i += 1
    return out


def font_sizes(body):
    # samo `font-size:`, ne `font-size-adjust`, ne dela `font:` (preveri se posebej)
    return re.findall(r"(?<![\w-])font-size\s*:\s*([^;}]+)", body)


def ok_value(v):
    v = v.strip().replace("!important", "").strip()
    if v.startswith("var(--fs-"):
        return True
    if v.startswith("clamp(") and "var(--fs-" in v:
        return True
    if v in ("inherit", "initial", "unset") or re.fullmatch(r"[\d.]+(em|%)", v):
        return True
    return False


for sel, body in rules(CSS):
    if not SCOPE.search(sel):
        continue
    if any(d in sel for d in DISPLAY_OK):
        continue
    for v in font_sizes(body):
        check(ok_value(v), "pisava zunaj lestvice:", f"{sel.strip()[:70]} {{ font-size:{v.strip()} }}")
    m = re.search(r"(?<![\w-])font\s*:\s*([^;}]+)", body)
    if m:
        check("var(--fs-" in m.group(1), "stenografija font: zunaj lestvice:", f"{sel.strip()[:70]} {{ font:{m.group(1).strip()} }}")

# lestvica je definirana in ima razumne vrednosti
for tok, px in TOKENS.items():
    m = re.search(re.escape(tok) + r":\s*([\d.]+)rem", CSS)
    check(bool(m) and abs(float(m.group(1)) * 16 - px) < 0.01, "lestvica:", f"{tok} = {m.group(1) + 'rem' if m else 'manjka'}, pričakovano {px} px")
check(min(TOKENS.values()) >= 12, "najmanjša stopnja je 12 px")

# vgrajeni majhni font-size v HTML/JS hero kartice: dovoljeni samo za enote, ki jih CSS preglasi (`.hm-val>span[style]`, `.hm-sub [style*=font-size]`)
CSS_RESETS_INLINE = ".hero-b .hm-val>span[style]" in CSS and '.hero-b .hm-sub [style*="font-size"]' in CSS
check(CSS_RESETS_INLINE, "enote z vgrajenim font-size so preglasene v CSS")

print(f"{checks} preverjanj, {len(fails)} napak")
for f in fails:
    print("  ✗", f)
sys.exit(1 if fails else 0)
