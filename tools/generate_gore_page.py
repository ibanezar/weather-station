#!/usr/bin/env python3
"""
tools/generate_gore_page.py — /vreme-v-gorah/

Vreme na višini nad dolino: Golte, Menina planina, Smrekovec in Raduha. Ideja po neurje.si
(»Napoved za gore«); izvedba je naša: bere `data/winter-data.json` → `mountains`, ki ga piše
`tools/winter_engine.py` (`compute_mountains`) — generator sam nima API-ja (isto načelo kot
generate_zima_page.py).

Kar stran je in ni:
- OCENA NA VIŠINI iz javne napovedi za Rečico: temperatura z gradientom, veter z interpolacijo
  med 10 m in nivoji 925/850/700 hPa, občutena temperatura po formuli vetrnega hlajenja.
- NI meritev in NI uradna gorska napoved: model ne vidi terena (grebeni so vetrovnejši,
  padavine so dolinske brez orografskega ojačanja). Stran to pove in napoti na ARSO.

Usage:
  python3 tools/generate_gore_page.py
"""
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

DATA_PATH = os.path.join(seo.ROOT, "data", "winter-data.json")
DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

FAQ = [
    ("Je to uradna napoved za gore?",
     "Ne. To je ocena na višini vrha, izračunana iz javne napovedi Open-Meteo za Rečico ob Savinji. "
     "Za uradne napovedi in opozorila glej ARSO. Pred turo preveri tudi razmere pri oskrbovani koči."),
    ("Kako se izračuna temperatura na vrhu?",
     "Od temperature v Rečici (366 m) odštejemo standardni gradient, približno 0,65 °C na vsakih 100 m višine. "
     "Pri jasnem in mirnem vremenu ali ob inverziji je dejanska razlika drugačna — v inverziji je na vrhu lahko "
     "toplejše kot v dolini."),
    ("Kaj je občutena temperatura?",
     "Temperatura, ki jo telo občuti zaradi vetra (vetrno hlajenje). Računamo jo po standardni formuli za "
     "temperature do 10 °C in veter nad 4,8 km/h; sicer je enaka temperaturi zraka."),
    ("Zakaj je veter na grebenu lahko močnejši od prikazanega?",
     "Veter ocenjujemo z interpolacijo med vetrom pri tleh in vetrom na nivojih 925, 850 in 700 hPa. Model ne "
     "vidi terena: greben, sedlo ali žleb lahko veter pospešijo, zato sunki na izpostavljenih mestih presegajo "
     "prikazano vrednost."),
]


def num(x, d=0):
    if x is None:
        return "—"
    out = f"{x:.{d}f}"
    if out.lstrip("-").strip("0.") == "":  # »-0« ni berljivo
        out = out.lstrip("-")
    return out.replace(".", ",")


def fmt_day(iso, first):
    import datetime
    if first:
        return "danes"
    d = datetime.date.fromisoformat(iso)
    return f"{DAN_KRATKO[d.weekday()]} {d.day}. {d.month}."


def peak_html(pk):
    now = pk["now"]
    rows = []
    for i, d in enumerate(pk["daily"]):
        fl = (f"{num(d['freezing_min_m'])}–{num(d['freezing_max_m'])} m"
              if d.get("freezing_min_m") is not None else "—")
        rows.append(
            f'      <tr><th scope="row">{fmt_day(d["date"], i == 0)}</th>'
            f'<td>{num(d["tmin_c"], 0)} … {num(d["tmax_c"], 0)} °C</td>'
            f'<td>{num(d["felt_min_c"], 0)} °C</td>'
            f'<td>{num(d["wind_max_kmh"])} km/h</td>'
            f'<td>{num(d["precip_mm"], 1)} mm</td>'
            f'<td>{num(d["snow_cm"], 0)} cm</td>'
            f'<td>{fl}</td></tr>')
    return (
        f'  <h2>{_html.escape(pk["name"])} ({pk["elevation_m"]} m)</h2>\n'
        f'  <p class="archive-intro">Zdaj: <strong>{num(now["temp_c"], 1)} °C</strong>, občutena '
        f'<strong>{num(now["felt_c"], 0)} °C</strong>, veter ~<strong>{num(now["wind_kmh"])} km/h</strong>.</p>\n'
        '  <table class="stats">\n'
        '    <thead><tr><th scope="col">Dan</th><th scope="col">Temperatura</th><th scope="col">Občutena (min)</th>'
        '<th scope="col">Veter (max)</th><th scope="col">Padavine</th><th scope="col">Sneg</th>'
        '<th scope="col">Ničta izoterma</th></tr></thead>\n'
        '    <tbody>\n' + "\n".join(rows) + '\n    </tbody>\n  </table>')


def build_body(m):
    peaks = m["peaks"]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ
    ) + "\n  </div>"
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Vreme v gorah", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Vreme v gorah — Golte, Menina planina, Smrekovec, Raduha</h1>
  <p class="post-meta">Ocena na višini vrha · posodobljeno {_html.escape(m.get("generated_at_local", "—"))}</p>
  <p class="archive-intro">Temperatura, občutena temperatura, veter in ničta izoterma na višini štirih vrhov nad
  Zgornjo Savinjsko dolino. To je <b>modelska ocena</b> iz napovedi za Rečico, ne meritev in ne uradna gorska
  napoved — grebeni so navadno vetrovnejši od prikazanega, padavine pa so dolinske. Za ture glej tudi
  <a href="/zima/">MeteoZimo</a> (meja sneženja, snežna odeja) in <a href="/nevihte/">nevihtno napoved</a>.</p>
{chr(10).join(peak_html(pk) for pk in peaks)}
  <h2>Kako beremo tabelo</h2>
  <p class="archive-intro"><strong>Ničta izoterma</strong> je višina, kjer je temperatura 0 °C — nad njo je sneg,
  pod njo dež. <strong>Občutena temperatura</strong> upošteva veter. <strong>Sneg</strong> je ocena novega snega
  iz padavin in višine ničte izoterme (približno 1 cm na 1 mm padavin).</p>
{faq_html}
  <p class="muted-note">Ni uradna napoved. Pred turo preveri
  <a href="https://meteo.arso.gov.si/" target="_blank" rel="noopener">ARSO</a>, razmere pri koči in svojo
  pripravljenost; v gorah se vreme hitro spremeni.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    m = data.get("mountains")
    if not m or not m.get("peaks"):
        print("✗ data/winter-data.json nima ključa mountains — najprej poženi tools/winter_engine.py.",
              file=sys.stderr)
        return 1
    url = "/vreme-v-gorah/"
    title = "Vreme v gorah — Golte, Menina, Smrekovec, Raduha"
    desc = ("Temperatura, občutena temperatura, veter in ničta izoterma na višini vrhov nad Zgornjo Savinjsko "
            "dolino: Golte, Menina planina, Smrekovec, Raduha. Modelska ocena, ne uradna napoved.")
    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-10-07"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vreme v gorah", None)]),
        seo.faq_schema(FAQ),
    ])
    page = seo.page_shell(title, desc, url, schema, build_body(m))
    seo.write_page("vreme-v-gorah/index.html", page, force=True)
    print("  → vreme-v-gorah/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
