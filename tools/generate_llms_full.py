#!/usr/bin/env python3
"""tools/generate_llms_full.py — llms-full.txt: besedilo ključnih strani na enem mestu (GEO, faza 4 načrta 27. 10. 2026).

llms.txt je kazalo; llms-full.txt vsebuje za vsako stran iz `CORE` (tools/seo_audit.py) naslov, naslov URL, opis in prvih nekaj
odstavkov (odgovor v prvih stavkih), da ga model ali pajek prebere brez 100 zahtev. Besedilo je izrezano iz že objavljenih
HTML strani — nič ni vtipkano, zato ne more odstopati od strani. Vrstni red je tisti iz `CORE`. Bloki z živimi meritvami
(WX-STATIC) so izpuščeni, da datoteka ne spremeni vsak dan zaradi ene številke. Notranjih meritev ni (test_privacy pregleda
tudi to datoteko). Zaženi: python3 tools/generate_llms_full.py
"""
import html as htmlmod
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import seo_audit  # noqa: E402

OUT = os.path.join(ROOT, "llms-full.txt")
MAX_CHARS_PER_PAGE = 1100
MAX_PARAS = 4
MIN_PARA = 60
HEADER = """# Meteorec — celotno besedilo ključnih strani

> Vreme za Rečico ob Savinji (Zgornja Savinjska dolina, Slovenija) iz lastne postaje IREICA1. Spodaj je za vsako ključno stran
> naslov, naslov URL, opis in uvodno besedilo, izrezano iz objavljene strani. Kazalo s kratkimi opisi je v /llms.txt.
> Meritve postaje so označene kot meritve; modelske napovedi (Open-Meteo, ECMWF, ICON, MTR) so označene kot modelske ocene, ne uradna opozorila.
> Za uradna opozorila velja ARSO (arso.gov.si).
"""


def clean(s):
    s = re.sub(r"<!-- WX-STATIC:START.*?WX-STATIC:END -->", " ", s, flags=re.S)
    s = re.sub(r"<(script|style|svg|noscript|template)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<(nav|header|footer|form|button|select|details)\b.*?</\1>", " ", s, flags=re.S | re.I)
    return s


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    t = htmlmod.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def page_entry(path):
    f = path.strip("/")
    f = os.path.join(ROOT, f + "/index.html" if not f.endswith(".html") else f)
    if not os.path.exists(f):
        return None
    return entry_from_html(open(f, encoding="utf-8").read(), path)


def entry_from_html(raw, path):
    """Vnos iz HTML strani; None, če stran nima ne opisa ne uvodnega besedila (prazen vnos modelu ne koristi)."""
    title = text_of((re.search(r"<title>(.*?)</title>", raw, re.S) or [None, ""])[1])
    desc = ""
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', raw)
    if m:
        desc = htmlmod.unescape(m.group(1)).strip()
    body = clean(raw)
    h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", body, re.S)
    after = body[h1.end():] if h1 else body
    paras, total = [], 0
    for p in re.findall(r"<(?:p|li)\b[^>]*>(.*?)</(?:p|li)>", after, re.S):
        t = text_of(p)
        if len(t) < MIN_PARA or t in paras:
            continue
        if total + len(t) > MAX_CHARS_PER_PAGE and paras:
            break
        paras.append(t[:MAX_CHARS_PER_PAGE])
        total += len(t)
        if len(paras) >= MAX_PARAS:
            break
    if not paras and not desc:
        return None
    return {"url": "https://meteorec.si" + (path if path.startswith("/") else "/" + path), "title": title or text_of(h1.group(1) if h1 else path),
            "desc": desc, "paras": paras}


def build():
    out = [HEADER]
    n = 0
    for path in seo_audit.CORE:
        e = page_entry(path)
        if not e:
            continue
        n += 1
        out.append(f"\n## {e['title']}\n{e['url']}\n")
        if e["desc"]:
            out.append(f"> {e['desc']}\n")
        for p in e["paras"]:
            out.append(f"\n{p}\n")
    return "".join(out), n


def main():
    text, n = build()
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"llms-full.txt: {n} strani, {len(text) // 1024} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
