#!/usr/bin/env python3
"""
tools/generate_rojstni_page.py — /rojstnodnevno-vreme/ »Vreme na vaš rojstni dan« (18. 11. 2026)

Vnesete datum; brskalnik (rojstnodnevno-vreme/rojstni.js, ROČNO pisan, model izvožen za Node: tools/test_rojstni.mjs) iz vdelanih meritev postaje IREICA1
(samo zunanja polja: najvišja, najnižja, padavine; dnevi z src == "era5" izpuščeni, dan z manjkajočim poljem odpade) pokaže vreme tistega dne, če ga postaja
ima (merimo od novembra 2019), in povprečje/ekstreme za ta koledarski dan. Za leta pred meritvami stran ne izmišlja nič (ERA5 ni uporabljen). Vnos ostane v brskalniku.
Ni v workflowu; podatki se spreminjajo počasi: poženi občasno (npr. po novem letu).
"""
import datetime
import hashlib
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(ROOT, "rojstnodnevno-vreme", "rojstni.js")
URL = "/rojstnodnevno-vreme/"


def build_data():
    H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8")); H = H.get("days", H)
    days = {datetime.date.fromisoformat(k): v for k, v in H.items() if v.get("src") != "era5"}
    a, b = min(days), max(days)
    t, n, p = [], [], []
    d = a
    while d <= b:
        v = days.get(d)
        if v and v.get("tempHigh") is not None and v.get("tempLow") is not None and v.get("precipTotal") is not None:
            t.append(round(v["tempHigh"], 1)); n.append(round(v["tempLow"], 1)); p.append(round(v["precipTotal"], 1))
        else:
            t.append(None); n.append(None); p.append(None)
        d += datetime.timedelta(1)
    return {"start": a.isoformat(), "t": t, "n": n, "p": p}, a, b


def faq(first, last):
    return [
        ("Kakšno vreme je bilo na moj rojstni dan?", f"Če je bil to dan med {first} in {last}, stran pokaže izmerjeno najnižjo, najvišjo temperaturo in padavine postaje v Rečici ob Savinji. Za starejše datume postaja nima meritve."),
        ("Zakaj ni podatkov za moje rojstno leto?", "Postaja meri od novembra 2019. Za prejšnja leta stran ne izmišlja vrednosti; pokaže pa povprečje in skrajne vrednosti za ta koledarski dan iz let, ki jih imamo."),
        ("Ali se moj datum kam pošlje?", "Ne. Izračun poteka v vašem brskalniku."),
    ]


def main():
    data, a, b = build_data()
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    fd = lambda d: f"{d.day}. {d.month}. {d.year}"
    title = "Vreme na vaš rojstni dan: kakšno je bilo v dolini?"
    desc = "Vnesite datum in poglejte, kakšno vreme je izmerila postaja v Rečici ob Savinji ta dan, ter povprečje in rekorde za ta koledarski dan."
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    fq = faq(fd(a), fd(b))
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(x)}</p></details>' for q, x in fq) + "\n  </div>"
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Rojstnodnevno vreme", None)])}
  <h1 class="page-title">Vreme na vaš rojstni dan</h1>
  <p class="post-meta">Izmerjeno na postaji IREICA1 · od {fd(a)}</p>
  <p class="archive-intro">Izberite datum. Če je dan med {fd(a)} in {fd(b)}, pokažem izmerjeno vreme; sicer povprečje in skrajne vrednosti za ta koledarski dan. Vnos ostane v vašem brskalniku.</p>
  <style>
  .rd-f{{display:grid;gap:.6rem;max-width:22rem}} .rd-f input{{width:100%;box-sizing:border-box;min-height:44px;padding:.4rem .6rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem}}
  .rd-big{{font-size:1.6rem;font-weight:700;margin:.3rem 0}}
  </style>
  <form id="rd-form" class="rd-f"><label>Datum<input id="rd-datum" type="date" value="2026-06-12"></label></form>
  <div id="rd-out" aria-live="polite" style="margin:1rem 0"></div>
  <noscript><p class="archive-intro">Orodje potrebuje JavaScript.</p></noscript>
  <p class="vs-note">Vir: postaja IREICA1, Rečica ob Savinji (366 m), zunanji senzor. Dan se ne šteje, če manjka katera od meritev. Postaja je amaterska in ni uradna meritev.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script type="application/json" id="rd-data">{blob}</script>
<script src="{URL}rojstni.js?v={js_ver}" defer></script>'''
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
                        seo.crumbs_schema([("Meteorec", "/"), ("Rojstnodnevno vreme", None)]), seo.faq_schema(fq)])
    seo.write_page("rojstnodnevno-vreme/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print(f"  → rojstnodnevno-vreme/index.html ({a} – {b})")


if __name__ == "__main__":
    main()
