#!/usr/bin/env python3
"""
tools/generate_advent_page.py — /adventni-koledar/ »Adventni koledar doline« (18. 11. 2026)

24 vrat, vsaka odpre dejstvo s postaje za koledarski dan 1.–24. decembra iz meritev IREICA1 (samo zunanja polja, dnevi z src == "era5" izpuščeni):
najhladnejša/najtoplejša noč za ta datum, najmokrejši dan, delež let z zmrzaljo ... Vrsta dejstva se menja po vratih (`KINDS`), vse številke so
izračunane iz history.json (nič ni vtipkano). Vrata odpre JS po lokalnem datumu (Europe/Ljubljana) -- prej kot 1. decembra so zaklenjena,
po 24. so odprta vsa. Vsebina je v HTML (JSON), ker je datum odvisen od obiskovalca; za pajke je vidna vrstica s pojasnilom.
To so zgodovinski podatki, ne napoved. Ni v workflowu: po novem letu / ob večji posodobitvi history.json ga poženi ročno.
"""
import datetime
import hashlib
import html as _html
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(ROOT, "adventni-koledar", "advent.js")
URL = "/adventni-koledar/"
KINDS = ["cold", "warm", "rain", "mean", "frost", "wind"]
MIN_YEARS = 4


def load():
    H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    H = H.get("days", H)
    return {datetime.date.fromisoformat(k): v for k, v in H.items() if v.get("src") != "era5"}


def fnum(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def rows_for(days, month, day):
    out = []
    for y in range(2019, datetime.date.today().year + 1):
        try:
            v = days.get(datetime.date(y, month, day))
        except ValueError:
            continue
        if v:
            out.append((y, v))
    return out


def door(days, d):
    rows = rows_for(days, 12, d)
    kind = KINDS[(d - 1) % len(KINDS)]
    n = len(rows)
    if n < MIN_YEARS:
        return None
    ys = lambda key: [(y, v[key]) for y, v in rows if v.get(key) is not None]
    if kind == "cold":
        s = ys("tempLow"); y, t = min(s, key=lambda a: a[1]); m = statistics.mean(x for _, x in s)
        return dict(h=f"{fnum(t)} °C", t=f"Najhladnejša noč {d}. decembra v dolini", p=f"Leta {y}. Povprečna najnižja za ta datum: {fnum(m)} °C ({len(s)} let).")
    if kind == "warm":
        s = ys("tempHigh"); y, t = max(s, key=lambda a: a[1]); m = statistics.mean(x for _, x in s)
        return dict(h=f"{fnum(t)} °C", t=f"Najtoplejši {d}. december", p=f"Leta {y}. Povprečna najvišja za ta datum: {fnum(m)} °C ({len(s)} let).")
    if kind == "rain":
        s = ys("precipTotal"); y, p = max(s, key=lambda a: a[1]); wet = sum(1 for _, x in s if x >= 0.2)
        return dict(h=f"{fnum(p)} mm", t=f"Največ padavin {d}. decembra", p=f"Leta {y}. Dež (vsaj 0,2 mm) je bil v {wet} od {len(s)} let.")
    if kind == "mean":
        s = ys("tempAvg"); m = statistics.mean(x for _, x in s)
        dec = [v["tempAvg"] for k, v in days.items() if k.month == 12 and k.day <= 24 and v.get("tempAvg") is not None]
        dm = statistics.mean(dec)
        diff = m - dm
        rel = "toplejši" if diff > 0.3 else "hladnejši" if diff < -0.3 else "tak kot ostali"
        return dict(h=f"{fnum(m)} °C", t=f"Povprečna temperatura {d}. decembra", p=f"Povprečje {len(s)} let; dan je {rel} od povprečja 1.–24. decembra ({fnum(dm)} °C).")
    if kind == "frost":
        s = ys("tempLow"); z = sum(1 for _, x in s if x <= 0)
        return dict(h=f"{z} od {len(s)}", t=f"Let z zmrzaljo {d}. decembra", p="Noč z najnižjo temperaturo 0 °C ali manj, izmerjeno na dnu doline.")
    s = ys("windgustHigh"); y, g = max(s, key=lambda a: a[1])
    return dict(h=f"{fnum(g, 0)} km/h", t=f"Najmočnejši sunek {d}. decembra", p=f"Leta {y}. Izmerjen sunek, ne povprečni veter.")


def faq(n_years):
    return [
        ("Kaj je v adventnem koledarju?", f"Vsaka vrata odprejo eno izmerjeno dejstvo s postaje IREICA1 za ta koledarski dan decembra iz {n_years} let: najhladnejša noč, najtoplejši dan, največ padavin, zmrzal, sunki."),
        ("Ali je to napoved?", "Ne. Vse so izmerjene vrednosti iz preteklih let. Za prihajajoči teden poglejte napoved za Rečico."),
        ("Zakaj so vrata zaklenjena?", "Vrata se odprejo na izbrani dan po vaši uri. Prej kot 1. decembra so vsa zaklenjena, po 24. decembru so odprta vsa."),
    ]


def main():
    days = load()
    doors = {d: door(days, d) for d in range(1, 25)}
    assert all(doors.values()), [d for d, v in doors.items() if not v]
    first, last = min(days), max(days)
    n_years = round((last - first).days / 365.25)
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Adventni koledar doline: 24 vrat z vremenom"
    desc = "24 vrat do božiča: vsaka odpre eno izmerjeno dejstvo s postaje v Rečici ob Savinji za ta dan decembra (najhladnejša noč, rekordi, zmrzal)."
    assert len(title) <= 60 and len(desc) <= 160
    blob = json.dumps(doors, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    fq = faq(n_years)
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in fq) + "\n  </div>"
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Adventni koledar", None)])}
  <h1 class="page-title">Adventni koledar doline</h1>
  <p class="post-meta">24 vrat · izmerjeni podatki postaje IREICA1 · {n_years} let</p>
  <p class="archive-intro">Vsak dan decembra odpre ena vrata: izmerjeno dejstvo za ta datum v Rečici ob Savinji. To so pretekla leta, ne napoved.</p>
  <style>
  .adv{{display:grid;grid-template-columns:repeat(auto-fill,minmax(5.2rem,1fr));gap:.6rem;margin:1rem 0;padding:0;list-style:none}}
  .adv button{{width:100%;aspect-ratio:1;min-height:44px;border-radius:14px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1.4rem;font-weight:700;cursor:pointer}}
  .adv button[disabled]{{opacity:.45;cursor:not-allowed}}
  .adv button[aria-pressed="true"]{{background:var(--accent,#2f7d5b);color:#fff}}
  #adv-out{{min-height:7rem}}
  .adv-big{{font-size:2.2rem;font-weight:700}}
  </style>
  <ul class="adv" id="adv"></ul>
  <div class="card" id="adv-out" aria-live="polite"><p class="archive-intro">Izberite odprta vrata.</p></div>
  <noscript><p class="archive-intro">Koledar potrebuje JavaScript.</p></noscript>
  <p class="vs-note">Vir: postaja IREICA1, Rečica ob Savinji (366 m), zunanji senzor, {first.day}. {first.month}. {first.year}–{last.day}. {last.month}. {last.year}. Za datum se upošteva le leto z meritvijo; najmanj {MIN_YEARS} let.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script type="application/json" id="adv-data">{blob}</script>
<script src="{URL}advent.js?v={js_ver}" defer></script>'''
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
                        seo.crumbs_schema([("Meteorec", "/"), ("Adventni koledar", None)]), seo.faq_schema(fq)])
    seo.write_page("adventni-koledar/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print("  → adventni-koledar/index.html")


if __name__ == "__main__":
    main()
