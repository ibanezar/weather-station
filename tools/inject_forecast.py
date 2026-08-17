#!/usr/bin/env python3
"""
tools/inject_forecast.py — Pre-render the forecast into static, crawlable HTML
on /vreme-recica-ob-savinji/.

Zakaj: »vreme rečica ob savinji po urah« (42 prikazov, poz. 10,0) in »… 14 dni«
(20 prikazov, poz. 9,1) sta poizvedbi, na kateri je stran doslej odgovarjala
samo z besedilom »napoved je na naslovni strani«. Napovedi na strani ni bilo, in
tisto, česar na strani ni, ne more rangirati. Skupaj s krovno poizvedbo
(~1 950 prikazov na poz. ~9,5) je to največja neizkoriščena lokalna vrzel.

Dva bloka med markerji:
  WX-FC7   — 7-dnevna napoved (tabela)
  WX-FCH   — napoved po urah za naslednjih ~24 ur (tabela)

Viri se NE zlivajo v eno številko (isto načelo kot na kartici za zgodbe):
  - Open-Meteo za vse dni in ure;
  - MTR (`napoved-modela.json`) je lasten model s popravkom za dno doline in ima
    v tabeli SVOJ stolpec, samo za dneve, ki jih pokriva (lead 1–3).
Ime modela (»MTR v1«) se izpelje iz `model_version` — nikjer ni zapisano trdo.

Ob nedosegljivem API-ju skript pusti obstoječo vsebino pri miru (raje malo stara
napoved kot prazna stran) in vrne 0; brez markerjev javi napako in vrne 1.

Wired into:
  .github/workflows/prerender-current.yml (urno)

Usage:
  python3 tools/inject_forecast.py [--dry-run]
"""
import json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "vreme-recica-ob-savinji", "index.html")
MOS = os.path.join(ROOT, "napoved-modela.json")

LAT, LON = 46.325779, 14.921137

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


def fetch_open_meteo():
    """7 dni dnevne napovedi + urna napoved. None ob katerikoli napaki."""
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
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
        print(f"Open-Meteo ni dosegljiv ({e}) — napoved ostane nespremenjena.",
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


def build_fc7(om, mos, mos_label):
    """7-dnevna tabela. MTR ima svoj stolpec in se z Open-Meteo ne zliva."""
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


def build_fch(om):
    """Napoved po urah za naslednjih ~24 ur, v 3-urnih korakih."""
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
            f'  <h2 id="po-urah">Vreme po urah za Rečico ob Savinji</h2>\n'
            f'  <div class="table-scroll">\n'
            f'  <table class="data-table">\n'
            f'    <caption>Naslednjih 24 ur v 3-urnih korakih (Open-Meteo, časovni pas '
            f'Europe/Ljubljana). Podrobnejši urni prikaz je na '
            f'<a href="/">naslovni strani</a>.</caption>\n'
            f'    <thead><tr><th>Ura</th><th>Temperatura (°C)</th><th>Padavine (mm)</th>'
            f'<th>Verjetnost</th><th>Veter (km/h)</th></tr></thead>\n'
            f'    <tbody>\n' + "\n".join(rows) + f'\n    </tbody>\n  </table>\n  </div>\n'
            f'  {FCH_END}')


def replace_block(html, start, end, block):
    return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block,
                  html, flags=re.S)


def main():
    dry = "--dry-run" in sys.argv[1:]
    if not os.path.exists(PAGE):
        print(f"ERROR: {PAGE} ne obstaja.", file=sys.stderr)
        return 1
    html = open(PAGE, encoding="utf-8").read()

    missing = [n for n, s, e in (("WX-FC7", FC7_START, FC7_END),
                                 ("WX-FCH", FCH_START, FCH_END))
               if s not in html or e not in html]
    if missing:
        print(f"ERROR: markerjev ni v strani: {', '.join(missing)} — "
              f"poženi najprej tools/generate_seo_pages.py.", file=sys.stderr)
        return 1

    om = fetch_open_meteo()
    if om is None:
        return 0                      # pusti staro napoved, ne izprazni strani

    mos, mos_label = load_mos()
    new = replace_block(html, FC7_START, FC7_END, build_fc7(om, mos, mos_label))
    new = replace_block(new, FCH_START, FCH_END, build_fch(om))

    if dry:
        print("--dry-run: sprememb ne zapisujem.")
        print("spremenjeno" if new != html else "brez sprememb")
        return 0
    if new != html:
        open(PAGE, "w", encoding="utf-8").write(new)
        print("vreme-recica-ob-savinji/index.html: posodobljena napoved.")
    else:
        print("vreme-recica-ob-savinji/index.html: napoved brez sprememb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
