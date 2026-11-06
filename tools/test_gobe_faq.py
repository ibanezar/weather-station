#!/usr/bin/env python3
"""Odgovori »Na kratko« in FAQ na najbolj AI-citiranih gobarskih straneh (6. 11. 2026).

(1) Štiri objave: FAQPage v JSON-LD = vidna vprašanja in odgovori (isto besedilo), odgovor na vrhu obstaja,
    dateModified = polje `updated` v blog.json.
(2) Strani skupin v bazi vrst: committana stran vsebuje izhod baza_cat_text() (odgovor, vidni FAQ in shemo),
    številke v odgovoru so izpeljane iz species_rules.yaml, v besedilu vprašanj ni HTML-ja."""
import html, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import generate_gobe_page as g
import gobe_model as gm

fails = []
def check(ok, msg):
    if not ok:
        fails.append(msg)
def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
upd = {p["slug"]: p.get("updated") or p["date"] for p in posts}
POSTS = {"kdaj-po-tednu-dezja-zrastejo-gobe-0822": True, "zakaj-po-dezju-gobe-ne-zrastejo-takoj": True,
         "koliko-dni-po-dezju-rastejo-gobe": True, "vpliv-lune-na-rast-gob-0921": True}
for slug in POSTS:
    h = read(f"blog/{slug}.html")
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">\s*(.*?)</script>', h, re.S)]
    faq = [d for d in ld if d.get("@type") == "FAQPage"]
    check(len(faq) == 1, f"{slug}: pričakovan natanko 1 FAQPage, najdenih {len(faq)}")
    if faq:
        qs = [(e["name"], e["acceptedAnswer"]["text"]) for e in faq[0]["mainEntity"]]
        vis = [(html.unescape(q), html.unescape(a)) for q, a in
               re.findall(r'<div class="faq-item">\s*<h3>(.*?)</h3>\s*<p>(.*?)</p>', h, re.S)]
        check(len(qs) >= 3, f"{slug}: manj kot 3 vprašanja")
        check(qs == vis, f"{slug}: shema FAQPage se ne ujema z vidnimi vprašanji")
    check(("Kratek odgovor:" in h) or ("Na kratko:" in h), f"{slug}: ni odgovora na vrhu")
    bp = next((d for d in ld if d.get("@type") == "BlogPosting"), {})
    check(bp.get("dateModified") == upd[slug], f"{slug}: dateModified {bp.get('dateModified')} != updated {upd[slug]}")

rules = gm.load_rules()
sp = rules["species"]
for path, key, label, _t, _d in g.BAZA_CATS:
    subset = ([s for s in sp if g.EDIB_FILTER.get((s.get("edibility") or "").lower().strip()) == key] if key else list(sp))
    ans, qa = g.baza_cat_text(key, subset, sp)
    h = read("gobarska-napoved/baza-vrst/" + (path + "/" if path else "") + "index.html")
    check(f"{len(subset)} " in ans, f"{path or 'vse'}: število vrst ni v odgovoru")
    check(ans in h, f"{path or 'vse'}: odgovor ni v committani strani (poženi generate_gobe_page.py)")
    for q, a in qa:
        check("<" not in q + a, f"{path or 'vse'}: HTML v FAQ besedilu")
        check(f"<summary>{html.escape(q, quote=True)}</summary>" in h.replace("&#x27;", "&#39;") or q in h,
              f"{path or 'vse'}: vprašanje »{q}« ni v strani")
    check('"@type":"FAQPage"' in h, f"{path or 'vse'}: ni sheme FAQPage")
    check("Ob dvomu" in " ".join(a for _, a in qa) or "poznate 100" in ans, f"{path or 'vse'}: manjka varnostno opozorilo")
    if key == "strupena":
        check("112" in ans and g.STRUP_PHONE in " ".join(a for _, a in qa), "strupene: manjka 112 ali številka centra")

if fails:
    print("\n".join("✗ " + f for f in fails)); sys.exit(1)
print("✓ test_gobe_faq: vse OK")
