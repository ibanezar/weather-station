#!/usr/bin/env python3
"""
tools/generate_jutro_page.py — /jutro-v-dolini/ (3. 11. 2026): kdaj se po jasni noči dolina ogreje.

Dva dela, ki sta oba naša:
1. ČAS PRVEGA ŽARKA na dnu doline (Rečica) — izračunan iz terena, `tools/sonce_horizont.py` (isto kot /sonce-v-dolini/).
2. ZAMIK od prvega žarka do dviga temperature za 3 °C nad jutranjim minimumom — IZMERJEN na postaji IREICA1 na jasnih,
   mirnih jutrih, `tools/eval_jutro.py` (data/jutro-zamik.json). Napoved = prvi žarek + izmerjeni zamik.

Kdaj napovedi NE objavimo (stran to pove, ne molči):
- jutro po modelu ni jasno in mirno (oblačnost ≥ 30 % ali veter ≥ 6 km/h): pravilo velja samo za tak primer;
- za ta mesec ni dovolj izmerjenih jasnih jutr (< `MIN_N`): zamika pozimi ne izposojamo iz poletja.

Napovedi se beležijo v `data/jutro-napovedi.csv` (ena vrstica na ciljni dan, zadnja pred dnevom ostane) in jih
`eval_jutro.py` primerja z izmerjenim. Brez te zanke bi bila stran trditev, ne preverjena trditev.

Vhodi: data/winter-data.json → warmup (piše winter_engine.py), data/jutro-zamik.json, data/horizons.json.
Usage:
  python3 tools/generate_jutro_page.py
"""
import csv
import datetime
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import eval_jutro as ej  # noqa: E402
import sonce_horizont as sh  # noqa: E402

URL = "/jutro-v-dolini/"
PUBLISHED = "2026-11-03"
DATA_PATH = os.path.join(seo.ROOT, "data", "winter-data.json")
STATS_PATH = ej.OUT_PATH
PRED_PATH = ej.PRED_PATH
CLOUD_MAX_PCT = 30
WIND_MAX_KMH = 6.0  # model; postaja meri ~polovico (CLAUDE.md: Veter in sunki v dolini)
PRECIP_MAX_MM = 0.2
DAN = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
MESECI_GEN = ["januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra",
              "oktobra", "novembra", "decembra"]
PRED_FIELDS = ["date", "issued", "first_min", "lo_min", "mid_min", "hi_min", "tmin_fc", "clear_calm"]

FAQ = [
    ("Kdaj se dolina ogreje po jasni noči?",
     "Dno doline se ogreje, ko sonce pride do tal. Na jasnih, mirnih jutrih od julija do oktobra je temperatura za 3 °C "
     "narasla v povprečju poldrugo uro po prvem žarku (odstopanje približno pol ure). Pozimi tega še nimamo izmerjenega."),
    ("Je to napoved zmrzali?",
     "Ne. Stran ne napoveduje, ali bo zmrzal, ampak kdaj se jutranji mraz ob jasnem vremenu začne umikati. Za zmrzal glejte "
     "napoved v modelu MTR na naslovni strani."),
    ("Zakaj stran včasih ne poda ure?",
     "Ker pravilo velja samo za jasno in mirno jutro. Pri megli, oblakih ali vetru je zamik drugačen. Prav tako ure ne podam "
     "za mesec, v katerem še nimam dovolj izmerjenih jasnih jutr."),
    ("Kako veste, kdaj pride sonce do doline?",
     "Iz terena: obzorje v vseh smereh je izračunano iz Copernicus DEM, položaj sonca po algoritmu NOAA/Meeus. Podrobnosti in "
     "izračun za druge kraje so na strani »Sonce v dolini«."),
]


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def fmt_iso(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}"


def round5(x):
    return int(5 * round(x / 5.0))


def predict_morning(m, place, stats):
    """Zapis za eno jutro: prvi žarek, ocena jasno/mirno, napoved časa dviga za 3 °C (ali razlog, da je ni)."""
    date = datetime.date.fromisoformat(m["date"])
    pr = sh.day_profile(place["lat"], place["lon"], place["horizon"], date)
    clear_calm = (m["cloud_pct"] < CLOUD_MAX_PCT and m["wind_kmh"] < WIND_MAX_KMH and m["precip_mm"] < PRECIP_MAX_MM)
    lag = ej.lag_for_month(stats.get("meseci", {}), date.month, stats.get("min_n", ej.MIN_N))
    rec = {"date": m["date"], "pr": pr, "clear_calm": clear_calm, "lag": lag, "m": m}
    if pr["first"] is not None and clear_calm and lag:
        mid = pr["first"] + lag["mean_h"] * 60
        rec.update(lo=round5(mid - lag["sd_h"] * 60), mid=round5(mid), hi=round5(mid + lag["sd_h"] * 60))
    return rec


def log_predictions(recs, today):
    """Zabeleži napovedi za jutra, ki še niso začela teči (ciljni dan strogo po današnjem): danes ob izdaji je jutro
    že napol mimo in ne bi bilo več »napoved dan prej«. Za isti ciljni dan zadnja izdaja pred njim prepiše prejšnje."""
    rows = []
    if os.path.exists(PRED_PATH):
        with open(PRED_PATH, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    by_date = {r["date"]: r for r in rows}
    for r in recs:
        if r["date"] <= today.isoformat():
            continue
        by_date[r["date"]] = {"date": r["date"], "issued": today.isoformat(),
                              "first_min": r["pr"]["first"] if r["pr"]["first"] is not None else "",
                              "lo_min": r.get("lo", ""), "mid_min": r.get("mid", ""), "hi_min": r.get("hi", ""),
                              "tmin_fc": r["m"]["tmin_c"], "clear_calm": "1" if "mid" in r else "0"}
    out = sorted(by_date.values(), key=lambda r: r["date"])[-400:]
    os.makedirs(os.path.dirname(PRED_PATH), exist_ok=True)
    with open(PRED_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PRED_FIELDS)
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in PRED_FIELDS})


def fmt_morning(r):
    date = datetime.date.fromisoformat(r["date"])
    day = f"{DAN[date.weekday()]}, {date.day}. {MESECI_GEN[date.month - 1]}"
    pr, m, lag = r["pr"], r["m"], r["lag"]
    fr = sh.hhmm(pr["first"])
    flat = sh.hhmm(pr["flat_rise"])
    facts = (f'Prvi žarek v Rečici ob <strong>{fr}</strong> (koledarski vzhod {flat}). '
             f'Model za jutro: najnižja temperatura ~{round(m["tmin_c"])} °C ob {m["tmin_hour"]}. uri, '
             f'oblačnost {m["cloud_pct"]} %, veter {str(m["wind_kmh"]).replace(".", ",")} km/h.')
    if "mid" in r:
        verdict = (f'Jasno in mirno jutro: temperatura naj bi za 3 °C narasla <strong>približno ob {sh.hhmm(r["mid"])}</strong> '
                   f'(razpon {sh.hhmm(r["lo"])}–{sh.hhmm(r["hi"])}).')
    elif not r["clear_calm"]:
        why = []
        if m["cloud_pct"] >= CLOUD_MAX_PCT:
            why.append(f'oblačnost {m["cloud_pct"]} %')
        if m["wind_kmh"] >= WIND_MAX_KMH:
            why.append(f'veter {str(m["wind_kmh"]).replace(".", ",")} km/h')
        if m["precip_mm"] >= PRECIP_MAX_MM:
            why.append("padavine")
        verdict = ('Jutro ne bo jasno in mirno (' + ", ".join(why) + '): pravilo ne velja in časa ne napovedujem. '
                   'Sonce do tal pride ob prvem žarku, če nebo ni prekrito; megla ali oblak pa ga lahko zakrijeta za več ur.')
    elif not lag:
        verdict = ('Za ta čas v letu še nimam dovolj izmerjenih jasnih in mirnih jutr, zato časa ne napovedujem. '
                   'Pozimi je zamik verjetno daljši kot jeseni, a ga še nisem izmeril.')
    else:
        verdict = "Prvega žarka ta dan zaradi terena ni."
    return (f'  <div class="jd-day"><h3>{day}</h3>\n    <p>{facts}</p>\n    <p class="jd-verdict">{verdict}</p></div>')


def stats_table(stats):
    rows = []
    names = ["januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober",
             "november", "december"]
    for m in range(1, 13):
        s = stats.get("meseci", {}).get(str(m))
        if not s:
            rows.append(f'      <tr><th scope="row">{names[m - 1].capitalize()}</th><td>0</td><td>—</td></tr>')
            continue
        mean = s["sum"] / s["n"]
        rows.append(f'      <tr><th scope="row">{names[m - 1].capitalize()}</th><td>{s["n"]}</td>'
                    f'<td>{str(round(mean, 1)).replace(".", ",")} h</td></tr>')
    return ('  <table class="stats">\n    <thead><tr><th scope="col">Mesec</th><th scope="col">Jasnih, mirnih jutr</th>'
            '<th scope="col">Povprečni zamik (prvi žarek → +3 °C)</th></tr></thead>\n    <tbody>\n'
            + "\n".join(rows) + '\n    </tbody>\n  </table>')


def track_record_html(stats):
    pv = stats.get("preverjanje") or {"n": 0}
    if pv.get("n", 0) >= 10:
        return (f'  <p class="archive-intro">Doslej je bilo ocenjenih {pv["n"]} napovedi na jasnih, mirnih jutrih: '
                f'povprečna napaka {int(pv["mae_min"])} min, v napovedanem razponu jih je bilo {pv["v_razponu"]}.</p>')
    return ('  <p class="archive-intro">Napovedi beležim od 3. novembra 2026 in jih primerjam z izmerjenim dvigom '
            f'temperature. Doslej jih je ocenjenih {pv.get("n", 0)}; rezultat objavim, ko jih bo vsaj 10.</p>')


def build_body(recs, stats, generated):
    n_total = stats.get("jasna_mirna_jutra", 0)
    per = stats.get("obdobje") or ["?", "?"]
    morning_html = "\n".join(fmt_morning(r) for r in recs) if recs else (
        '  <p class="archive-intro">Napoved za naslednja jutra trenutno ni na voljo.</p>')
    lead = ('<strong>Kratek odgovor:</strong> na jasnih, mirnih jutrih od julija do oktobra se je dolina v Rečici '
            'za 3 °C ogrela v povprečju <strong>poldrugo uro po prvem žarku</strong>, ki pride do dolinskega dna. Prvi žarek '
            'poznam iz terena, zamik pa sem izmeril na postaji.')
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Jutro v dolini", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Kdaj se po jasni noči ogreje dolina</h1>
  <p class="post-meta">Rečica ob Savinji{(" · napoved posodobljena " + _html.escape(generated)) if generated else ""}</p>
  <p class="archive-intro">{lead}</p>
  <p class="archive-intro">Po jasni, mirni noči se hladen zrak nabere na dnu doline. Ogreje se šele, ko sonce preseže
  grebene in pogleda do tal. Zato je ura drugačna kot po koledarju: v Rečici pride prvi žarek zjutraj pozneje, v Solčavi pa
  pozimi do tal ne pride več mesecev (glej <a href="/sonce-v-dolini/">Sonce v dolini</a>).</p>

  <h2>Naslednja jutra</h2>
{morning_html}

  <h2>Kako to vem</h2>
  <p class="archive-intro">Zamik sem izmeril na {n_total} jasnih in mirnih jutrih ({fmt_iso(per[0])} do {fmt_iso(per[1])}). Jutro štejem za jasno in
  mirno, če je bil dnevni razpon temperature vsaj 10 °C in povprečni veter od polnoči do 7. ure pod 3 km/h. Jutranji minimum je
  najnižje urno povprečje do 10. ure, dvig je prvi trenutek, ko urno povprečje preseže minimum za 3 °C.</p>
{stats_table(stats)}
  <p class="muted-note">Zamik za posamezni mesec zberem iz sosednjih mesecev, šele ko je skupaj vsaj {stats.get("min_n", ej.MIN_N)}
  jutr. Zimskih meritev še ni (podatke imam od 13. julija 2026), zato za december, januar in februar časa ne napovedujem.</p>

  <h2>Preverjanje napovedi</h2>
{track_record_html(stats)}

  <h2>Kaj ta stran ni</h2>
  <ul>
    <li>Ni napoved zmrzali ali megle. Stran ne ve, ali bo megla; za zgornjo mejo megle glejte <a href="/zima/nad-meglo/">Nad meglo</a>.</li>
    <li>Ni meritev prihodnosti: čas dviga je ocena iz prvega žarka in povprečnega zamika, odstopanje je približno pol ure.</li>
    <li>Modelska oblačnost in veter prihajata iz Open-Meteo; model veter na tej postaji približno podvoji, zato uporabljam prag 6 km/h
    namesto 3 km/h, kolikor je prag pri meritvah.</li>
  </ul>
  <p class="muted-note">Prvi žarek: <a href="/sonce-v-dolini/">Sonce v dolini</a> · Zima: <a href="/zima/">MeteoZima</a> ·
  <a href="/vreme-recica-ob-savinji/">Vreme Rečica ob Savinji</a>.</p>'''


CSS = '''<style>
.jd-day{margin:1rem 0;padding:.9rem 1rem;border:1px solid rgba(128,128,128,.35);border-radius:.8rem}
.jd-day h3{margin:0 0 .4rem;font-size:1.05rem}
.jd-day p{margin:.3rem 0}
.jd-verdict{font-size:1.02rem}
</style>'''


def main():
    data = read_json(DATA_PATH)
    stats = read_json(STATS_PATH)
    hz = sh.load_horizons()
    place = next(p for p in hz["places"] if p["id"] == "recica")
    if not data:
        print("✗ data/winter-data.json manjka — najprej poženi tools/winter_engine.py.", file=sys.stderr)
        return 1
    if "warmup" not in data:
        print("⚠ data/winter-data.json še nima ključa warmup (winter_engine ga doda ob prvem teku): "
              "stran brez napovedi za jutra.", file=sys.stderr)
    if not stats:
        print("✗ data/jutro-zamik.json manjka — poženi tools/eval_jutro.py.", file=sys.stderr)
        return 1
    warm = data.get("warmup") or {}
    today = datetime.date.today()
    # stara napoved (workflow ni stekel): jutra, ki so že mimo, ne kažemo
    mornings = [m for m in (warm.get("mornings") or []) if m["date"] >= today.isoformat()]
    recs = [predict_morning(m, place, stats) for m in mornings]
    log_predictions(recs, today)
    generated = warm.get("generated_at_local")
    title = "Kdaj se po jasni noči ogreje dolina"
    desc = ("Kdaj se dolina v Rečici ob Savinji ogreje po jasni, mirni noči: čas prvega žarka iz terena in izmerjen zamik "
            "do dviga temperature za 3 °C. Ocena, ne napoved zmrzali.")
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ
    ) + "\n  </div>"
    body = build_body(recs, stats, generated) + "\n" + faq_html + '\n  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'
    schema = "\n".join([seo.webpage_schema(URL, title, desc, date_published=PUBLISHED),
                        seo.crumbs_schema([("Meteorec", "/"), ("Jutro v dolini", None)]), seo.faq_schema(FAQ)])
    page = seo.page_shell(title, desc, URL, schema + "\n" + CSS, body)
    seo.write_page("jutro-v-dolini/index.html", page, force=True)
    print("  → jutro-v-dolini/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
