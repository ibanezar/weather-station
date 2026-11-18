#!/usr/bin/env python3
"""
tools/generate_prireditev_page.py — /vreme-za-prireditev/ »Vreme za poroko in prireditve: najboljši datum« (18. 11. 2026)

Klimatologija po datumih iz meritev postaje IREICA1: za izbran datum in merilo (padavine, najvišja, najnižja temperatura)
JS izračuna, v kolikšnem deležu dni v oknu ±w dni (v vseh letih meritev) je bil dan »primeren«, kaže točno ta datum po letih
in najboljše datume v ±14 dneh. To NI napoved (za zadnji teden velja napoved).

- Podatki: history.json, samo zunanja polja tempHigh/tempLow/precipTotal; dnevi z src == "era5" so izpuščeni, dan z manjkajočim
  poljem se ne šteje. Vdelani v stran (#pr-data, ~40 kB); JS (vreme-za-prireditev/prireditev.js, ROČNO pisan, model izvožen za Node:
  tools/test_prireditev.mjs) računa sproti, zato je merilo mogoče spreminjati.
- Merila profilov (poroka/veselica/šport) so moja izbira in so vidna ter spremenljiva; stran to pove. Sedem let je malo; interval
  je optimističen (sosednji dnevi so soodvisni). Toča, nevihte in veter v podatkih niso upoštevani.
- Statična tabela po mesecih (rezerva brez JS) je izračunana iz vseh dni meseca, ne iz okna ±w.
- Ni v workflowu: podatki se spreminjajo počasi; po novem letu ga poženi ročno (ali ob večjem posodabljanju history.json).
- Notranjih meritev ne uporablja.

Usage:
  python3 tools/generate_prireditev_page.py
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
HISTORY = os.path.join(ROOT, "history.json")
JS_PATH = os.path.join(ROOT, "vreme-za-prireditev", "prireditev.js")
URL = "/vreme-za-prireditev/"
MESECI = ["", "januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober", "november", "december"]
POROKA = dict(rain=0.2, lo=18.0, hi=30.0)          # kot PROFILES.poroka v prireditev.js


def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    return {datetime.date.fromisoformat(k): v for k, v in H.items() if v.get("src") != "era5"}


def build_data(days):
    a, b = min(days), max(days)
    t, n, p = [], [], []
    d = a
    complete = 0
    while d <= b:
        v = days.get(d)
        if v and v.get("tempHigh") is not None and v.get("tempLow") is not None and v.get("precipTotal") is not None:
            t.append(round(v["tempHigh"], 1)); n.append(round(v["tempLow"], 1)); p.append(round(v["precipTotal"], 1))
            complete += 1
        else:
            t.append(None); n.append(None); p.append(None)
        d += datetime.timedelta(1)
    return {"start": a.isoformat(), "t": t, "n": n, "p": p}, complete


def month_table(data):
    start = datetime.date.fromisoformat(data["start"])
    rows = {m: [] for m in range(1, 13)}
    for i, (tx, tn, pp) in enumerate(zip(data["t"], data["n"], data["p"])):
        if tx is None:
            continue
        d = start + datetime.timedelta(i)
        rows[d.month].append((tx, tn, pp))
    out = []
    for m in range(1, 13):
        r = rows[m]
        dry = sum(1 for x in r if x[2] < 0.2) / len(r)
        good = sum(1 for x in r if x[2] < POROKA["rain"] and POROKA["lo"] <= x[0] <= POROKA["hi"]) / len(r)
        out.append((m, statistics.mean(x[0] for x in r), dry, good, len(r)))
    return out


def faq(n_years, complete):
    return [
        ("Kako je izračunan »primeren dan«?",
         "Dan je primeren, če je padlo manj padavin od praga (pri poroki 0,2 mm) in je bila najvišja temperatura v izbranem obsegu (pri poroki 18–30 °C). "
         "Za izbran datum preštejem take dneve v oknu ±7 dni v vseh letih meritev in izračunam delež. Merila lahko spremenite pod »Prilagodi merila«."),
        ("Je to napoved vremena?",
         "Ne. Je klimatologija: kaj se je na ta datum dogajalo v preteklih letih na postaji v Rečici. Za zadnji teden pred dogodkom je boljša napoved; "
         "za dogodek, ki je daleč, pove, kako tvegan je datum."),
        ("Koliko podatkov je za izračun?",
         f"Postaja IREICA1 meri od novembra 2019. Za večino datumov je na voljo {n_years} let, v oknu ±7 dni okoli 100 dni. "
         "Sedem let je malo, zato so razlike med sosednjimi datumi v okviru naključja, razpon pri deležu pa je optimističen, ker so sosednji dnevi podobni."),
        ("Zakaj dež čez cel dan, če je prireditev samo nekaj ur?",
         "Postaja beleži padavine za cel dan. Padavine pod pragom 0,2 mm so strožje merilo, kot ga zahteva ura prireditve: marsikateri dan z dežjem je imel suho popoldne. "
         "Merilo zato zrahljajte (npr. 1 ali 2 mm), če ni težav z manjšo plohou."),
        ("Ali upoštevate nevihte, točo in veter?",
         "Ne. V podatkih so samo dnevne padavine, najvišja in najnižja temperatura. Toča in nevihte ob poletnih popoldnevih za zunanjo prireditev pomenijo dodatno tveganje, ki ga stran ne meri."),
        ("Velja to tudi za moj kraj?",
         "Podatki so z ene postaje na dnu doline v Rečici ob Savinji (366 m). Na višjih legah je običajno hladneje in več padavin, ob večji vodi drugače. "
         "Stran je orientacija za Zgornjo Savinjsko dolino, ne za vso Slovenijo."),
    ]


def build_body(data, js_ver, mt, n_years, complete, first, last):
    mrows = "".join(
        f"<tr><th scope=\"row\">{MESECI[m]}</th><td>{tx:.1f}".replace(".", ",") + f"</td><td>{100 * dry:.0f} %</td><td>{100 * good:.0f} %</td></tr>"
        for m, tx, dry, good, _ in mt)
    mtbl = ('<div class="pr-tbl" tabindex="0" role="region" aria-label="Mesečna klimatologija"><table><thead><tr><th>Mesec</th>'
            '<th>Povprečna najvišja (°C)</th><th>Dnevi brez dežja</th><th>Primerni dnevi (poroka)</th></tr></thead><tbody>'
            f'{mrows}</tbody></table></div>')
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in faq(n_years, complete)) + "\n  </div>"
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Vreme za prireditev", None)])}
  <h1 class="page-title">Vreme za poroko in prireditve: kateri datum je najboljši?</h1>
  <p class="post-meta">Klimatologija po datumih iz meritev postaje v Rečici · {n_years} let podatkov</p>
  <p class="archive-intro">Izberite datum in vrsto dogodka: pokazal bom, v kolikšnem deležu dni okoli tega datuma je bilo vreme primerno (brez dežja in v ustrezni temperaturi),
  kaj se je zgodilo točno na ta dan v prejšnjih letih in kateri sosednji datumi so se obnesli bolje. To ni napoved: za zadnji teden pred dogodkom poglejte
  <a href="/vreme-recica-ob-savinji/">napoved za Rečico</a>.</p>
  <style>
  .pr-form{{display:grid;gap:.8rem;max-width:34rem}}
  .pr-form label{{display:grid;gap:.25rem;font-weight:600;font-size:.95rem}}
  .pr-form input,.pr-form select{{width:100%;max-width:100%;min-width:0;box-sizing:border-box;min-height:44px;padding:.4rem .6rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem;font-weight:400}}
  .pr-two{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}}
  .pr-two>*{{min-width:0}}
  @media(max-width:480px){{.pr-two{{grid-template-columns:1fr}}}}
  .pr-form details{{border:1px solid var(--card-border,var(--border));border-radius:12px;padding:.5rem .8rem}}
  .pr-form summary{{cursor:pointer;font-weight:600}}
  .pr-tbl{{overflow-x:auto;max-width:100%;margin:.6rem 0}}
  .pr-tbl table{{border-collapse:collapse;width:100%;font-size:.9rem}}
  .pr-tbl th,.pr-tbl td{{padding:.42rem .5rem;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}}
  .pr-tbl th:first-child,.pr-tbl td:first-child{{text-align:left}}
  .pr-best{{padding-left:1.3rem;display:grid;gap:.25rem}}
  .pr-note,.vs-note{{color:var(--muted);font-size:.82rem;line-height:1.5}}
  </style>
  <div class="card" style="margin:1rem 0">
    <div class="clabel">Izberite datum in dogodek</div>
    <form id="pr-form" class="pr-form" novalidate>
      <div class="pr-two">
        <label>Datum (leto je poljubno)<input id="pr-datum" type="date" value="2027-06-12"></label>
        <label>Vrsta dogodka<select id="pr-prof">
          <option value="poroka">Poroka ali slovesnost na prostem</option>
          <option value="veselica">Večerna prireditev (veselica, piknik)</option>
          <option value="sport">Šport, izlet, tek</option></select></label>
      </div>
      <label>Okno okoli datuma<select id="pr-w"><option value="3">±3 dni (manj podatkov, natančneje)</option><option value="7" selected>±7 dni</option><option value="14">±14 dni (več podatkov)</option></select></label>
      <details><summary>Prilagodi merila</summary>
        <div class="pr-two" style="margin-top:.6rem">
          <label>Padavine pod (mm)<input id="pr-rain" type="number" inputmode="decimal" min="0" step="0.2"></label>
          <label>Najnižja od (°C, neobvezno)<input id="pr-nmin" type="number" inputmode="decimal" step="1"></label>
          <label>Najvišja od (°C)<input id="pr-tlo" type="number" inputmode="decimal" step="1"></label>
          <label>Najvišja do (°C)<input id="pr-thi" type="number" inputmode="decimal" step="1"></label>
        </div>
      </details>
    </form>
    <div id="pr-msg" class="vs-note" aria-live="polite" style="min-height:1.2em"></div>
  </div>
  <div id="pr-out" aria-live="polite"><p class="archive-intro">Izberite datum.</p></div>
  <noscript><p class="archive-intro">Kalkulator potrebuje JavaScript; mesečni pregled je spodaj.</p></noscript>
  <h2>Po mesecih</h2>
  <p class="archive-intro">Vsi dnevi meseca iz {n_years} let ({first} do {last}). »Primerni dnevi« so tisti, ko je padlo manj kot 0,2 mm in je bila najvišja med 18 in 30 °C.</p>
  {mtbl}
  <p class="vs-note">Vir: postaja IREICA1, Rečica ob Savinji (366 m), zunanji senzor. Dan se ne šteje, če manjka katera od meritev (največja, najmanjša temperatura ali padavine).
  Merila za poroko, večerno prireditev in šport so moja izbira; spremenite jih lahko v obrazcu.</p>
{faq_html}
  <a class="back-link" href="/">← Vreme v Rečici</a>
<script type="application/json" id="pr-data">{blob}</script>
<script src="{URL}prireditev.js?v={js_ver}" defer></script>'''


def main():
    days = load()
    data, complete = build_data(days)
    first, last = min(days), max(days)
    n_years = round((last - first).days / 365.25)
    js_ver = hashlib.md5(open(JS_PATH, "rb").read()).hexdigest()[:8]
    title = "Vreme za poroko in prireditve: najboljši datum"
    desc = ("Kateri datum je najboljši za poroko ali prireditev na prostem? Delež dni brez dežja in z ustrezno temperaturo po meritvah postaje v Rečici.")
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    fmt_d = lambda d: f"{d.day}. {d.month}. {d.year}"
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vreme za prireditev", None)]),
        seo.faq_schema(faq(n_years, complete)),
    ])
    body = build_body(data, js_ver, month_table(data), n_years, complete, fmt_d(first), fmt_d(last))
    page = seo.page_shell(title, desc, URL, schema, body)
    seo.write_page("vreme-za-prireditev/index.html", page, force=True)
    print(f"  → vreme-za-prireditev/index.html ({complete} dni z vsemi tremi polji, {len(data['t'])} dni v nizu)")


if __name__ == "__main__":
    main()
