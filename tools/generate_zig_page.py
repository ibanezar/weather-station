#!/usr/bin/env python3
"""
tools/generate_zig_page.py — /vreme-na-fotografiji/ »Vremenski žig na fotografiji« (18. 11. 2026)

Obiskovalec izbere svojo fotografijo in dan; brskalnik (vreme-na-fotografiji/zig.js, ROČNO pisan, model izvožen za Node: tools/test_zig.mjs) na sliko (canvas)
napiše dnevno najnižjo/najvišjo temperaturo in padavine postaje IREICA1 za ta dan. Fotografija se obdela samo v brskalniku in se nikamor ne naloži.
Žig je DNEVNI (ne urni): urnega arhiva postaja nima (ločljivost Ecowitta velja samo za ~85 dni). Za dan brez popolne meritve žiga ne izmišlja.
Vdelani niz (samo zunanja polja, dnevi z src == "era5" izpuščeni) je enak kot pri /rojstnodnevno-vreme/ (namerna podvojitev: generatorji so samostojni).
Ni v workflowu; po novem letu poženi ročno.
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
JS_PATH = os.path.join(ROOT, "vreme-na-fotografiji", "zig.js")
URL = "/vreme-na-fotografiji/"

FAQ = [
    ("Ali se moja fotografija naloži na strežnik?", "Ne. Slika se obdela v vašem brskalniku; Meteorec je ne prejme."),
    ("Ali žig kaže uro ali dan?", "Dan: najnižjo in najvišjo temperaturo ter padavine tistega dne po meritvah postaje IREICA1 v Rečici ob Savinji. Urnih podatkov za starejše dni postaja nima."),
    ("Zakaj žig za moj datum ni mogoč?", "Postaja meri od novembra 2019, dan pa mora imeti popolne meritve (najvišja, najnižja temperatura in padavine). Vrednosti ne izmišljam."),
    ("Ali je žig uraden podatek?", "Ne. Postaja je amaterska in ni uradna meritev; za tiste, ki fotografirajo drugje v Sloveniji, je to le orientacija za dolino."),
]


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
    return {"start": a.isoformat(), "t": t, "n": n, "p": p}, b


def main():
    data, last = build_data()
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Vremenski žig na fotografiji: dodajte podatke postaje"
    desc = "Izberite svojo fotografijo in dan: na sliko dodamo najnižjo, najvišjo temperaturo in padavine postaje v Rečici. Obdelava je samo v vašem brskalniku."
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Vremenski žig na fotografiji", None)])}
  <h1 class="page-title">Vremenski žig na fotografiji</h1>
  <p class="post-meta">Za vaše zimske in druge fotografije · obdelava samo v brskalniku</p>
  <p class="archive-intro">Izberite fotografijo in dan, ko je nastala. Na sliko napišem, kakšno vreme je izmerila postaja v Rečici ob Savinji. Slika ne zapusti vaše naprave.</p>
  <style>
  .zg-f{{display:grid;gap:.7rem;max-width:30rem}} .zg-f label{{display:grid;gap:.25rem;font-weight:600;font-size:.95rem}}
  .zg-f input{{width:100%;min-width:0;box-sizing:border-box;min-height:44px;padding:.4rem .6rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem;font-weight:400}}
  #zg-cv{{max-width:100%;height:auto;border-radius:12px;margin:1rem 0;display:block}} #zg-cv[width="300"]{{display:none}}
  </style>
  <div class="zg-f">
    <label>Fotografija<input id="zg-file" type="file" accept="image/*"></label>
    <label>Datum posnetka<input id="zg-datum" type="date" value="{last.isoformat()}" min="{data["start"]}" max="{last.isoformat()}"></label>
  </div>
  <div id="zg-msg" class="vs-note" aria-live="polite" style="min-height:1.2em"></div>
  <canvas id="zg-cv" aria-label="Fotografija z vremenskim žigom"></canvas>
  <button id="zg-dl" class="btn" type="button" hidden>Shrani sliko</button>
  <noscript><p class="archive-intro">Orodje potrebuje JavaScript.</p></noscript>
  <p class="vs-note">Vir: postaja IREICA1, Rečica ob Savinji (366 m), zunanji senzor. Dnevna vrednost, ne ura posnetka. Postaja je amaterska in ni uradna meritev.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script type="application/json" id="zg-data">{blob}</script>
<script src="{URL}zig.js?v={js_ver}" defer></script>'''
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
                        seo.crumbs_schema([("Meteorec", "/"), ("Vremenski žig na fotografiji", None)]), seo.faq_schema(FAQ)])
    seo.write_page("vreme-na-fotografiji/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print(f"  → vreme-na-fotografiji/index.html (do {last})")


if __name__ == "__main__":
    main()
