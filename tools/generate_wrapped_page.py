#!/usr/bin/env python3
"""
tools/generate_wrapped_page.py — /vreme-2026/ »Vreme 2026 v dolini« (18. 11. 2026)

Letni pregled iz meritev IREICA1 (history.json, samo zunanja polja, dnevi z src == "era5" izpuščeni): najhladnejša noč, najtoplejši dan, najmokrejši dan,
najmočnejši sunek, število zmrzalnih noči in vročih dni, dnevi z dežjem, skupne padavine. Leto je »do zadnjega dne meritev«; stran to izpiše (do konca leta
je pregled delen). Dnevi brez meritve se ne štejejo (manjkajoč dan ni »0«); delež pokritosti je na strani. Primerjava z lanskim letom samo za isti
razpon dni (1. 1.–zadnji dan).
Ni v workflowu; ob koncu leta (ali občasno) poženi ročno in commitaj.
"""
import datetime
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "/vreme-2026/"
YEAR = 2026


def load():
    H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    H = H.get("days", H)
    return {datetime.date.fromisoformat(k): v for k, v in H.items() if v.get("src") != "era5"}


def f1(x):
    return f"{x:.1f}".replace(".", ",").replace("-", "−")


def dstr(d):
    return f"{d.day}. {d.month}. {d.year}"


def stats(days, year, upto):
    sel = {d: v for d, v in days.items() if d.year == year and d <= upto.replace(year=year)}
    def col(k):
        return [(d, v[k]) for d, v in sel.items() if v.get(k) is not None]
    lows, highs, rain, gust = col("tempLow"), col("tempHigh"), col("precipTotal"), col("windgustHigh")
    span = (upto.replace(year=year) - datetime.date(year, 1, 1)).days + 1
    return dict(
        n=len(sel), span=span,
        cold=min(lows, key=lambda a: a[1]) if lows else None,
        hot=max(highs, key=lambda a: a[1]) if highs else None,
        wet=max(rain, key=lambda a: a[1]) if rain else None,
        gust=max(gust, key=lambda a: a[1]) if gust else None,
        frost=sum(1 for _, x in lows if x <= 0), n_low=len(lows),
        hotdays=sum(1 for _, x in highs if x >= 30), n_high=len(highs),
        rainy=sum(1 for _, x in rain if x >= 0.2), n_rain=len(rain),
        total=sum(x for _, x in rain),
    )


def faq():
    return [
        ("Od kod so podatki?", "Iz meritev postaje IREICA1 v Rečici ob Savinji (zunanji senzor). Dnevi, ko meritve ni, se ne štejejo; delež pokritih dni je izpisan na strani."),
        ("Zakaj leto še ni končano?", "Pregled je do zadnjega dne meritev; številke se do konca leta lahko spremenijo. Ob koncu leta ga osvežimo."),
        ("Ali je to uradna statistika?", "Ne. Postaja je amaterska (Ecowitt, brez uradne kalibracije). Za uradne podatke velja ARSO."),
    ]


def main():
    days = load()
    last = max(d for d in days if d.year == YEAR)
    s, p = stats(days, YEAR, last), stats(days, YEAR - 1, last)
    assert s["cold"] and s["hot"] and s["wet"] and s["gust"], "premalo podatkov"
    cover = 100 * s["n"] / s["span"]
    title = f"Vreme {YEAR} v dolini: najhladnejša noč in rekordi"
    desc = f"Pregled vremenskega leta {YEAR} v Rečici ob Savinji: najhladnejša noč, najtoplejši dan, najmokrejši dan, zmrzali in padavine po meritvah postaje."
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))

    def tile(lbl, big, sub):
        return f'<div class="wr-t"><div class="wr-l">{_html.escape(lbl)}</div><div class="wr-b">{_html.escape(big)}</div><div class="wr-s">{_html.escape(sub)}</div></div>'

    cmp_rain = ""
    if p["n"] >= 0.8 * p["span"] and p["n_rain"] >= 0.8 * p["span"]:
        cmp_rain = f' Lani do istega dne: {f1(p["total"])} mm.'
    tiles = "".join([
        tile("Najhladnejša noč", f"{f1(s['cold'][1])} °C", dstr(s["cold"][0])),
        tile("Najtoplejši dan", f"{f1(s['hot'][1])} °C", dstr(s["hot"][0])),
        tile("Najmokrejši dan", f"{f1(s['wet'][1])} mm", dstr(s["wet"][0])),
        tile("Najmočnejši sunek", f"{s['gust'][1]:.0f} km/h".replace(".", ","), dstr(s["gust"][0])),
        tile("Noči z zmrzaljo", str(s["frost"]), f"od {s['n_low']} dni z meritvijo najnižje"),
        tile("Vroči dnevi (≥ 30 °C)", str(s["hotdays"]), f"od {s['n_high']} dni z meritvijo najvišje"),
        tile("Dnevi z dežjem", str(s["rainy"]), f"od {s['n_rain']} dni, vsaj 0,2 mm"),
        tile("Padavine skupaj", f"{f1(s['total'])} mm", f"1. 1.–{last.day}. {last.month}.{cmp_rain}"),
    ])
    fq = faq()
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in fq) + "\n  </div>"
    body = f'''{seo.crumbs_html([("Meteorec", "/"), (f"Vreme {YEAR}", None)])}
  <h1 class="page-title">Vreme {YEAR} v dolini</h1>
  <p class="post-meta">Do {dstr(last)} · postaja IREICA1 · pokritost {cover:.0f} % dni</p>
  <p class="archive-intro">Leto v številkah iz izmerjenih podatkov. Pregled je delen do konca leta in se tedaj osveži. Dnevi brez meritve se ne štejejo.</p>
  <style>
  .wr-g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(13rem,1fr));gap:.7rem;margin:1rem 0}}
  .wr-t{{padding:.9rem 1rem;border-radius:16px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);min-width:0}}
  .wr-l{{font-size:.82rem;color:var(--muted)}} .wr-b{{font-size:1.9rem;font-weight:700;line-height:1.2}} .wr-s{{font-size:.85rem;color:var(--muted)}}
  </style>
  <div class="wr-g">{tiles}</div>
  <p class="vs-note">Vir: postaja IREICA1, Rečica ob Savinji (366 m), zunanji senzor. Najnižja temperatura je dnevna najnižja (običajno ob zori).
  Padavine so seštevek dnevnih vrednosti dni z meritvijo. Postaja je amaterska in ni uradna meritev.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>'''
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
                        seo.crumbs_schema([("Meteorec", "/"), (f"Vreme {YEAR}", None)]), seo.faq_schema(fq)])
    seo.write_page("vreme-2026/index.html", seo.page_shell(title, desc, URL, schema, body), force=True)
    print(f"  → vreme-2026/index.html (do {last}, {s['n']} dni, pokritost {cover:.0f} %)")


if __name__ == "__main__":
    main()
