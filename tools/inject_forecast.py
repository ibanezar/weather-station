#!/usr/bin/env python3
"""
tools/inject_forecast.py — Pre-render the forecast into static, crawlable HTML
on /vreme-recica-ob-savinji/ and, since 27. 8. 2026, the six vreme-* village
pages that have their own real coordinates (NEARBY_TOWNS in
tools/generate_seo_pages.py — Mozirje, Nazarje, Ljubno ob Savinji, Gornji
Grad, Luče, Solčava).

Zakaj: »vreme rečica ob savinji po urah« (42 prikazov, poz. 10,0) in »… 14 dni«
(20 prikazov, poz. 9,1) sta poizvedbi, na kateri je stran doslej odgovarjala
samo z besedilom »napoved je na naslovni strani«. Napovedi na strani ni bilo, in
tisto, česar na strani ni, ne more rangirati. Skupaj s krovno poizvedbo
(~1 950 prikazov na poz. ~9,5) je to največja neizkoriščena lokalna vrzel.
Enak razlog velja za vaška imena v poizvedbah ("vreme mozirje", "vreme nazarje"
…) — te strani so doslej obiskovalca (in iskalnik) pošiljale nazaj na naslovno.

Dva bloka med markerji na vsaki strani:
  WX-FC7   — 7-dnevna napoved (tabela)
  WX-FCH   — napoved po urah za naslednjih ~24 ur (tabela)

Postaja (Rečica ob Savinji) dobi svoj MTR stolpec — svoj model, naučen na
meritvah te postaje (glej build_fc7_station). Vaške strani ga NE dobijo: MTR
popravlja pristranskost te postaje, ne bi bilo pošteno trditi enako natančnost
za kraj nekaj km stran, ki ga model sploh ne pozna (isto načelo kot povsod v
repozitoriju — "IREICA1 ostaja edina referenca"). Vaške strani zato dobijo
čisto Open-Meteo napoved za SVOJE koordinate — to je resnična, ne izpeljana
vrednost, in se razlikuje stran od strani.

Koordinate vasi so podvojene iz NEARBY_TOWNS v tools/generate_seo_pages.py, ne
uvožene — ta modul že uvaža inject_forecast (za daylabel/num/markerje), uvoz v
obratno smer bi naredil krožno odvisnost. Če se koordinate kraja kdaj
spremenijo, popravi na obeh mestih.

Ob nedosegljivem API-ju skript za posamezno stran pusti obstoječo vsebino pri
miru (raje malo stara napoved kot prazna stran); manjkajoči markerji na
posamezni strani javijo napako za TO stran in ne ustavijo ostalih — isti vzorec
kot TARGETS v tools/inject_current_weather.py.

Wired into:
  .github/workflows/prerender-current.yml (urno) — PATHS v tistem workflowu
  mora vsebovati vse ciljne strani, sicer se napoved lokalno posodobi, a nikoli
  ne commita (ista napaka kot pri novosti.json, glej CLAUDE.md).

Usage:
  python3 tools/inject_forecast.py [--dry-run]
"""
import json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATION_PAGE = os.path.join(ROOT, "vreme-recica-ob-savinji", "index.html")
MOS = os.path.join(ROOT, "napoved-modela.json")

LAT, LON = 46.325779, 14.921137  # IREICA1

# (slug, ime kraja v imenovalniku, lat, lon) — glej opombo o podvojitvi zgoraj.
TOWNS = [
    ("vreme-mozirje", "Mozirje", 46.338050, 14.957203),
    ("vreme-nazarje", "Nazarje", 46.320208, 14.953128),
    ("vreme-ljubno-ob-savinji", "Ljubno ob Savinji", 46.349700, 14.834347),
    ("vreme-gornji-grad", "Gornji Grad", 46.296042, 14.807663),
    ("vreme-luce", "Luče", 46.356461, 14.743625),
    ("vreme-solcava", "Solčava", 46.420125, 14.691811),
]

FC7_START = "<!-- WX-FC7:START (auto: tools/inject_forecast.py) -->"
FC7_END = "<!-- WX-FC7:END -->"
FCH_START = "<!-- WX-FCH:START (auto: tools/inject_forecast.py) -->"
FCH_END = "<!-- WX-FCH:END -->"

DAYS_SHORT = ["pon.", "tor.", "sre.", "čet.", "pet.", "sob.", "ned."]
MES_ABBR = {1: "jan.", 2: "feb.", 3: "mar.", 4: "apr.", 5: "maj", 6: "jun.",
            7: "jul.", 8: "avg.", 9: "sep.", 10: "okt.", 11: "nov.", 12: "dec."}


def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def daylabel(iso):
    d = datetime.strptime(iso[:10], "%Y-%m-%d")
    return f"{DAYS_SHORT[d.weekday()]} {d.day}. {MES_ABBR[d.month]}"


def fetch_open_meteo(lat=LAT, lon=LON):
    """7 dni dnevne napovedi + urna napoved za dano koordinato. None ob napaki."""
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "daily": ("temperature_2m_max,temperature_2m_min,precipitation_sum,"
                  "precipitation_probability_max,wind_speed_10m_max"),
        "hourly": "temperature_2m,precipitation,precipitation_probability,wind_speed_10m",
        "timezone": "Europe/Ljubljana",
        "forecast_days": 7,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:
        print(f"Open-Meteo ni dosegljiv za {lat},{lon} ({e}) — napoved ostane nespremenjena.",
              file=sys.stderr)
        return None


def load_mos():
    """MTR napoved po datumih + prikazno ime različice. ({}, None) če je ni."""
    try:
        d = json.load(open(MOS, encoding="utf-8"))
    except Exception:
        return {}, None
    by_date = {x["date"]: x for x in d.get("days", []) if x.get("date")}
    ver = d.get("model_version")
    label = f"MTR v{ver.split('.')[0]}" if ver else "MTR"
    return by_date, label


def build_fc7_station(om, mos, mos_label):
    """7-dnevna tabela za postajo. MTR ima svoj stolpec in se z Open-Meteo ne zliva."""
    d = om["daily"]
    rows = []
    have_mos = False
    for i, day in enumerate(d["time"]):
        m = mos.get(day)
        if m:
            have_mos = True
        mos_cell = (f"{num(m['tmax'])} / {num(m['tmin'])}" if m else
                    '<span class="muted">—</span>')
        pop = d["precipitation_probability_max"][i]
        rows.append(
            f"      <tr><td>{daylabel(day)}</td>"
            f"<td>{mos_cell}</td>"
            f"<td>{num(d['temperature_2m_max'][i])} / {num(d['temperature_2m_min'][i])}</td>"
            f"<td>{num(d['precipitation_sum'][i])}</td>"
            f"<td>{num(pop, 0) if pop is not None else '—'} %</td>"
            f"<td>{num(d['wind_speed_10m_max'][i], 0)}</td></tr>")

    mos_note = (f"Stolpec {mos_label} je lastni model Meteorec s popravkom za dno doline; "
                f"pokriva prve dni, za katere je naučen. Vira sta navedena ločeno in se "
                f"ne zlivata v eno številko."
                if have_mos else
                f"{mos_label} za te dni trenutno nima napovedi, zato je stolpec prazen.")

    return (f'{FC7_START}\n'
            f'  <h2 id="napoved">Napoved za Rečico ob Savinji, 7 dni</h2>\n'
            f'  <div class="table-scroll">\n'
            f'  <table class="data-table">\n'
            f'    <caption>Najvišja / najnižja temperatura (°C), padavine (mm), verjetnost '
            f'padavin in najmočnejši veter (km/h). {mos_note} '
            f'Osveženo vsako uro.</caption>\n'
            f'    <thead><tr><th>Dan</th><th>{mos_label} (°C)</th><th>Open-Meteo (°C)</th>'
            f'<th>Padavine (mm)</th><th>Verjetnost</th><th>Veter (km/h)</th></tr></thead>\n'
            f'    <tbody>\n' + "\n".join(rows) + f'\n    </tbody>\n  </table>\n  </div>\n'
            f'  {FC7_END}')


def build_fc7_town(om, town):
    """7-dnevna tabela za vaško stran — samo Open-Meteo, za koordinate kraja
    samega (ne postaje), zato brez MTR stolpca (glej opombo na vrhu datoteke)."""
    d = om["daily"]
    rows = []
    for i, day in enumerate(d["time"]):
        pop = d["precipitation_probability_max"][i]
        rows.append(
            f"      <tr><td>{daylabel(day)}</td>"
            f"<td>{num(d['temperature_2m_max'][i])} / {num(d['temperature_2m_min'][i])}</td>"
            f"<td>{num(d['precipitation_sum'][i])}</td>"
            f"<td>{num(pop, 0) if pop is not None else '—'} %</td>"
            f"<td>{num(d['wind_speed_10m_max'][i], 0)}</td></tr>")

    return (f'{FC7_START}\n'
            f'  <h2 id="napoved">Napoved, {town} — 7 dni</h2>\n'
            f'  <div class="table-scroll">\n'
            f'  <table class="data-table">\n'
            f'    <caption>Open-Meteo napoved za koordinate kraja {town} — modelska ocena, '
            f'ne meritev postaje IREICA1. Najvišja/najnižja temperatura (°C), padavine (mm), '
            f'verjetnost padavin in najmočnejši veter (km/h). Osveženo vsako uro.</caption>\n'
            f'    <thead><tr><th>Dan</th><th>Temperatura (°C)</th>'
            f'<th>Padavine (mm)</th><th>Verjetnost</th><th>Veter (km/h)</th></tr></thead>\n'
            f'    <tbody>\n' + "\n".join(rows) + f'\n    </tbody>\n  </table>\n  </div>\n'
            f'  {FC7_END}')


def build_fch(om, heading, caption_tail):
    """Napoved po urah za naslednjih ~24 ur, v 3-urnih korakih. Skupna za
    postajo in vaške strani — le naslov in opomba v napisu se razlikujeta."""
    h = om["hourly"]
    now = datetime.now(timezone.utc).astimezone()
    idx = [i for i, t in enumerate(h["time"])
           if datetime.fromisoformat(t).astimezone(now.tzinfo) >= now.replace(minute=0, second=0, microsecond=0)]
    if not idx:
        idx = list(range(len(h["time"])))
    pick = idx[:24:3]

    rows = []
    for i in pick:
        t = datetime.fromisoformat(h["time"][i])
        pop = h["precipitation_probability"][i]
        rows.append(
            f"      <tr><td>{daylabel(h['time'][i])}, {t.strftime('%H:%M')}</td>"
            f"<td>{num(h['temperature_2m'][i])}</td>"
            f"<td>{num(h['precipitation'][i])}</td>"
            f"<td>{num(pop, 0) if pop is not None else '—'} %</td>"
            f"<td>{num(h['wind_speed_10m'][i], 0)}</td></tr>")

    return (f'{FCH_START}\n'
            f'  <h2 id="po-urah">{heading}</h2>\n'
            f'  <div class="table-scroll">\n'
            f'  <table class="data-table">\n'
            f'    <caption>Naslednjih 24 ur v 3-urnih korakih (Open-Meteo, časovni pas '
            f'Europe/Ljubljana). {caption_tail}</caption>\n'
            f'    <thead><tr><th>Ura</th><th>Temperatura (°C)</th><th>Padavine (mm)</th>'
            f'<th>Verjetnost</th><th>Veter (km/h)</th></tr></thead>\n'
            f'    <tbody>\n' + "\n".join(rows) + f'\n    </tbody>\n  </table>\n  </div>\n'
            f'  {FCH_END}')


def replace_block(html, start, end, block):
    return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block,
                  html, flags=re.S)


def inject_page(page_path, fc7_html, fch_html):
    """Vbrizga oba bloka v eno stran. Vrne 'ok' | 'no-markers' | 'unchanged' | 'updated'."""
    if not os.path.exists(page_path):
        print(f"ERROR: {page_path} ne obstaja.", file=sys.stderr)
        return "no-markers"
    html = open(page_path, encoding="utf-8").read()
    missing = [n for n, s, e in (("WX-FC7", FC7_START, FC7_END), ("WX-FCH", FCH_START, FCH_END))
               if s not in html or e not in html]
    if missing:
        print(f"ERROR: markerjev ni v strani {page_path}: {', '.join(missing)} — "
              f"poženi najprej tools/generate_seo_pages.py.", file=sys.stderr)
        return "no-markers"
    new = replace_block(html, FC7_START, FC7_END, fc7_html)
    new = replace_block(new, FCH_START, FCH_END, fch_html)
    if new == html:
        print(f"{page_path}: napoved brez sprememb.")
        return "unchanged"
    open(page_path, "w", encoding="utf-8").write(new)
    print(f"{page_path}: posodobljena napoved.")
    return "updated"


def main():
    dry = "--dry-run" in sys.argv[1:]
    exit_code = 0

    # ── Postaja: nespremenjeno vedenje (MTR stolpec, lastne koordinate) ──
    om = fetch_open_meteo(LAT, LON)
    if om is not None:
        mos, mos_label = load_mos()
        fc7 = build_fc7_station(om, mos, mos_label)
        fch = build_fch(om, "Vreme po urah za Rečico ob Savinji",
                         'Podrobnejši urni prikaz je na <a href="/">naslovni strani</a>.')
        if dry:
            print(f"--dry-run: {STATION_PAGE} bi se posodobil.")
        else:
            if inject_page(STATION_PAGE, fc7, fch) == "no-markers":
                exit_code = 1
    # Nedosegljiv Open-Meteo za postajo ni napaka — pusti staro napoved (glej docstring).

    # ── Vaške strani: Open-Meteo za svoje koordinate, brez MTR stolpca ──
    for slug, town, lat, lon in TOWNS:
        page_path = os.path.join(ROOT, slug, "index.html")
        om = fetch_open_meteo(lat, lon)
        if om is None:
            continue
        fc7 = build_fc7_town(om, town)
        fch = build_fch(om, f"Vreme po urah, {town}",
                         f'Za koordinate kraja {town}, ne za postajo IREICA1.')
        if dry:
            print(f"--dry-run: {page_path} bi se posodobil.")
            continue
        if inject_page(page_path, fc7, fch) == "no-markers":
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
