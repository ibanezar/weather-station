#!/usr/bin/env python3
"""
tools/generate_prah_page.py — /prah/ (21. 10. 2026)

Saharski prah in drobni delci nad Evropo in Slovenijo: zemljevid največje urne koncentracije prahu pri tleh
(µg/m³) po dnevih za naslednje 4 dni (CAMS globalni model prek Open-Meteo, mreža 2° × 2,5°), ter napoved prahu,
PM10 in PM2,5 za več krajev v Sloveniji (CAMS Evropa, 0,1°) in urni graf za Rečico. Ideja po polarnivrtinec.si
(»Prah in zrak«); `/kakovost-zraka/` kaže trenutno stanje za dolino, tu je širša slika in napoved.

Kar stran je in ni:
- MODELSKA NAPOVED (Copernicus CAMS), ne meritev. Meritve onesnaženosti so na ARSO (zrak.arso.gov.si).
- Za prah ni uradnih mejnih vrednosti: razredi »nizka/zmerna/visoka« so NAŠA delitev za lažje branje. Za PM10 velja
  mejna dnevna vrednost EU 50 µg/m³, smernica WHO (2021) 45 µg/m³ — navedeni sta kot primerjava.
- Brez podatkov postaje; notranjih meritev tu ni.

Usage:
  python3 tools/generate_prah_page.py
"""
import datetime
import html as _html
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atmos_common as ac  # noqa: E402

API = "https://air-quality-api.open-meteo.com/v1/air-quality"
REL = "/prah/"
DATA_PATH = os.path.join(ac.ROOT, "data", "prah.json")
OUT_DIR = os.path.join(ac.ROOT, "prah", "karte")
DAYS = 4
GRID_LATS = [22 + 2 * i for i in range(20)]            # 22 … 60 °N
GRID_LONS = [-20 + 2.5 * i for i in range(27)]          # −20 … 45 °E
CITIES = [("Rečica ob Savinji", 46.33, 14.92), ("Ljubljana", 46.056, 14.505), ("Maribor", 46.554, 15.646),
          ("Celje", 46.23, 15.267), ("Koper", 45.548, 13.73), ("Nova Gorica", 45.956, 13.648)]
CITY_NAME_RECICA = CITIES[0][0]
LEVELS = [5, 10, 20, 50, 100, 200, 500, 1000, 2000]
COLORS = ["#fff7bc", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02", "#993404", "#662506"]
GREEN, PURPLE, AMBER = "#34d399", "#c084fc", "#fbbf24"
CREDIT = "Vir: CAMS prek Open-Meteo (CC BY 4.0) · meteorec.si · model, ne meritev"
DUST_LOW, DUST_HIGH = 10.0, 50.0  # naša delitev v µg/m³ (glej opombo v glavi)

FAQ = [
    ("Od kod pride saharski prah in zakaj ga vidimo v Sloveniji?",
     "Ob južnih vetrovih pred ciklonom nad zahodnim Sredozemljem se prah s puščave dvigne in v nekaj dneh prepotuje "
     "nad Sredozemlje in srednjo Evropo. Najpogosteje je to spomladi in jeseni. Prah vidimo kot rumenkasto "
     "motno nebo, rdečkast sneg v gorah in plast prahu na avtomobilih po dežju."),
    ("Je prah nevaren za zdravje?",
     "Višje koncentracije drobnih delcev (PM10, PM2,5) lahko dražijo dihala, zlasti pri bolnikih z astmo in "
     "boleznimi srca. Prah je del PM10. Za PM10 velja mejna dnevna vrednost EU 50 µg/m³ in smernica WHO 45 µg/m³. "
     "Ta stran ni zdravstveno opozorilo; za uradne podatke o onesnaženosti glej ARSO."),
    ("Kaj pomenijo razredi nizka, zmerna in visoka?",
     "To je naša delitev za lažje branje, ne uradna mejna vrednost: nizka pod 10 µg/m³, zmerna od 10 do 50, visoka "
     "nad 50. Za prah uradnih meja ni, ker gre za naravni pojav; odločilni so PM10 in PM2,5."),
    ("Kako točna je napoved prahu?",
     "Model CAMS dobro ujame, da se prah bliža, slabše pa točen čas in količino. Na zemljevidu je največja urna "
     "vrednost v dnevu in ima mrežo 2° × 2,5°, zato je prikazan pregled, ne podatek za kraj. Za kraje velja "
     "natančnejša (0,1°) napoved v tabeli."),
    ("Kako se razlikuje od strani Kakovost zraka?",
     "Kakovost zraka kaže trenutno stanje, cvetni prah in zdravstvene nasvete za Zgornjo Savinjsko dolino. Ta stran "
     "kaže napoved prahu za več dni in širšo sliko nad Evropo in Sredozemljem."),
]


def fetch(points, hourly, domains=None, days=DAYS):
    """Open-Meteo Air Quality; točke v kosih po 100. Vrne seznam odgovorov (po vrstnem redu)."""
    out = []
    for i in range(0, len(points), 100):
        chunk = points[i:i + 100]
        q = {"latitude": ",".join(str(p[0]) for p in chunk), "longitude": ",".join(str(p[1]) for p in chunk),
             "hourly": ",".join(hourly), "forecast_days": str(days), "timezone": "Europe/Ljubljana"}
        if domains:
            q["domains"] = domains
        data = json.loads(ac.http_get(API + "?" + urllib.parse.urlencode(q, safe=","), timeout=60))
        out.extend(data if isinstance(data, list) else [data])
    if len(out) != len(points):
        raise RuntimeError(f"Open-Meteo je vrnil {len(out)} točk namesto {len(points)}")
    return out


def daily_max(times, vals):
    """Urne vrednosti → {datum: največja} po lokalnem dnevu (časi so že v Europe/Ljubljana)."""
    out = {}
    for t, v in zip(times, vals):
        if v is None:
            continue
        d = t[:10]
        if d not in out or v > out[d]:
            out[d] = v
    return out


def build_grid():
    pts = [(a, o) for a in GRID_LATS for o in GRID_LONS]
    resp = fetch(pts, ["dust"], domains="cams_global")
    grids = {}
    for (a, o), r in zip(pts, resp):
        dm = daily_max(r["hourly"]["time"], r["hourly"]["dust"])
        for d, v in dm.items():
            grids.setdefault(d, {})[(a, o)] = v
    days = sorted(grids)[:DAYS]
    return days, grids


def draw_map(grid, day, path):
    import numpy as np
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from scipy.ndimage import zoom
    Z = np.array([[grid.get((a, o), np.nan) for o in GRID_LONS] for a in GRID_LATS], dtype=float)
    Z = np.nan_to_num(Z, nan=0.0)
    f = 6
    Zf = np.clip(zoom(Z, f, order=3, mode="nearest"), 0, None)
    lats = np.linspace(GRID_LATS[0], GRID_LATS[-1], Zf.shape[0])
    lons = np.linspace(GRID_LONS[0], GRID_LONS[-1], Zf.shape[1])
    LON, LAT = np.meshgrid(lons, lats)
    X, Y = ac.LCC.xy(LON, LAT)
    d = datetime.date.fromisoformat(day)
    fig, ax = ac.new_map("Saharski prah: največja urna koncentracija pri tleh (µg/m³)",
                         f"{ac.fmt_date(d, True)} · CAMS, model z mrežo 2° × 2,5° (pregled, ne podatek za kraj)", CREDIT)
    cmap = ListedColormap(COLORS)
    norm = BoundaryNorm(LEVELS, cmap.N)
    cf = ax.contourf(X, Y, Zf, levels=LEVELS, cmap=cmap, norm=norm, extend="max", alpha=0.85, zorder=2)
    x, y = ac.LCC.xy(14.92, 46.33)
    ax.plot([x], [y], marker="o", ms=5, mfc="#e11d48", mec="white", mew=1.2, zorder=12)
    ax.text(x + 40, y - 70, "Rečica", fontsize=8, color="#be123c", zorder=12, fontweight="bold")
    cax = fig.add_axes([0.52, 0.035, 0.46, 0.014])
    cb = fig.colorbar(cf, cax=cax, orientation="horizontal", ticks=LEVELS)
    cb.ax.tick_params(labelsize=7, length=2)
    cb.outline.set_linewidth(0.4)
    ac.save_webp(fig, path)


def build_cities():
    pts = [(c[1], c[2]) for c in CITIES]
    resp = fetch(pts, ["dust", "pm10", "pm2_5"])
    out = []
    for (name, _a, _o), r in zip(CITIES, resp):
        h = r["hourly"]
        out.append({"name": name, "time": h["time"], "dust": h["dust"], "pm10": h["pm10"], "pm2_5": h["pm2_5"]})
    return out


def cls(v):
    if v is None:
        return "—"
    return "nizka" if v < DUST_LOW else "zmerna" if v < DUST_HIGH else "visoka"


def day_label(day, i):
    d = datetime.date.fromisoformat(day)
    names = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
    return "danes" if i == 0 else f"{names[d.weekday()]} {d.day}. {d.month}."


def build_body(d, stale_note=""):
    days = d["days"]
    cities = d["cities"]
    rows_dust, rows_pm = [], []
    for c in cities:
        dmx = daily_max(c["time"], c["dust"])
        pmx = daily_max(c["time"], c["pm10"])
        rows_dust.append(f'      <tr><th scope="row">{_html.escape(c["name"])}</th>' + "".join(
            f'<td>{ac.num(dmx.get(day), 0)}</td>' for day in days) + '</tr>')
        rows_pm.append(f'      <tr><th scope="row">{_html.escape(c["name"])}</th>' + "".join(
            f'<td>{ac.num(pmx.get(day), 0)}</td>' for day in days) + '</tr>')
    head = "".join(f'<th scope="col">{_html.escape(day_label(day, i))}</th>' for i, day in enumerate(days))
    rec = next(c for c in cities if c["name"] == CITY_NAME_RECICA)
    rec_max = max((v for v in rec["dust"] if v is not None), default=0)
    rec_dust = daily_max(rec["time"], rec["dust"])
    peak_day = max(rec_dust, key=rec_dust.get)
    if rec_max >= DUST_HIGH:
        state = (f"Za Rečico ob Savinji model napoveduje visoko koncentracijo prahu: do {ac.num(rec_max, 0)} µg/m³ "
                 f"({ac.fmt_date(peak_day)}).")
    elif rec_max >= DUST_LOW:
        state = (f"Za Rečico ob Savinji model napoveduje zmerno koncentracijo prahu, največ {ac.num(rec_max, 0)} µg/m³ "
                 f"({ac.fmt_date(peak_day)}).")
    else:
        state = (f"Za Rečico ob Savinji model v naslednjih {len(days)} dneh ne napoveduje opaznega prahu (največ "
                 f"{ac.num(rec_max, 1)} µg/m³).")
    # urni graf Rečica
    ts = [datetime.datetime.fromisoformat(t) for t in rec["time"]]
    series = []
    for key, color, label in (("pm10", AMBER, "PM10"), ("dust", PURPLE, "prah")):
        p = []
        for t, v in zip(ts, rec[key]):
            if v is not None:
                p.append((_FracDate(t), v))
        series.append({"name": label, "color": color, "pts": p, "width": 2})
    chart = ac.legend([(AMBER, "PM10", False), (PURPLE, "prah (dust)", False)]) + ac.line_chart(
        series, zero=True, unit="µg/m³", aria="Urni graf prahu in PM10 za Rečico ob Savinji za naslednje štiri dni.",
        yfmt=lambda v: ac.num(v, 0), hlines=[(50, "PM10 50 (mejna dnevna vrednost EU)")])
    imgs = "\n".join(
        f'    <figure style="margin:1rem 0"><img src="/prah/karte/prah-{i}.webp?v={d["generated_at"][:10]}" '
        f'width="960" height="740" loading="{"eager" if i == 0 else "lazy"}" alt="Zemljevid največje urne koncentracije '
        f'saharskega prahu pri tleh nad Evropo in Sredozemljem, {_html.escape(day_label(day, i))}" '
        f'style="width:100%;height:auto;border-radius:12px"><figcaption class="muted-note">'
        f'{_html.escape(day_label(day, i).capitalize())} ({ac.fmt_date(day)})</figcaption></figure>'
        for i, day in enumerate(days))
    return f'''  <h1 class="page-title">Saharski prah nad Evropo in Slovenijo: napoved</h1>
  <p class="archive-intro">Zemljevid največje urne koncentracije prahu pri tleh za naslednje štiri dni in napoved za
  slovenske kraje. Iz modela Copernicus CAMS, <b>ne iz meritev</b>. Trenutno stanje v dolini, cvetni prah in
  zdravstvene nasvete najdeš na strani <a href="/kakovost-zraka/">Kakovost zraka</a>; za uradne meritve onesnaženosti
  je ARSO.</p>
{stale_note}  <div class="callout"><strong>{_html.escape(state)}</strong><br><span class="muted-note">Stran osvežena
  {_html.escape(ac.fmt_dt_local(d["generated_at"]))}. Razredi so naša delitev (pod 10 nizka, 10–50 zmerna, nad 50
  visoka µg/m³), ne uradna mejna vrednost.</span></div>
  <h2>Zemljevid po dnevih</h2>
{imgs}
  <h2>Prah po krajih (največja vrednost v dnevu, µg/m³)</h2>
  <table class="stats">
    <thead><tr><th scope="col">Kraj</th>{head}</tr></thead>
    <tbody>
{chr(10).join(rows_dust)}
    </tbody>
  </table>
  <h2>PM10 po krajih (največja vrednost v dnevu, µg/m³)</h2>
  <table class="stats">
    <thead><tr><th scope="col">Kraj</th>{head}</tr></thead>
    <tbody>
{chr(10).join(rows_pm)}
    </tbody>
  </table>
  <p class="muted-note">Za PM10 velja mejna dnevna vrednost EU 50 µg/m³ (smernica WHO 2021: 45 µg/m³). PM10 vključuje
  prah, a tudi promet, kurjavo in drugo; v hladni polovici leta ga v dolinah povečajo inverzije.</p>
  <h2>Rečica ob Savinji po urah</h2>
{chart}
  <h2>Kaj je prah v praksi</h2>
  <p class="archive-intro">Saharski prah ne pomeni nujno slabega zraka pri tleh: velik del ga je v višinah in ga vidimo kot
  motno, rumenkasto nebo ter rdečkast sneg ali blato po dežju. Ko ga veter ali padavine spustijo k tlom, se poviša
  PM10. Če je prah napovedan, a so vrednosti nizke, bo večinoma višje v ozračju.</p>
  <p class="muted-note">Vir: Copernicus Atmosphere Monitoring Service (CAMS) prek Open-Meteo, licenca
  <a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener" target="_blank">CC BY 4.0</a>. Izris je naš.
  Tu je samo modelska napoved, za zdravstvene odločitve upoštevaj ARSO.</p>'''


class _FracDate:
    """datetime, ki se obnaša kot datum v line_chart (toordinal z ulomkom dneva) — urna ločljivost grafa."""

    def __init__(self, dt):
        self.dt = dt
        self.day = dt.day
        self.month = dt.month

    def toordinal(self):
        return self.dt.toordinal() + (self.dt.hour + self.dt.minute / 60.0) / 24.0


def main():
    stale = ""
    try:
        days, grids = build_grid()
        cities = build_cities()
        generated = ac.now_utc_iso()
        for i, day in enumerate(days):
            draw_map(grids[day], day, os.path.join(OUT_DIR, f"prah-{i}.webp"))
            print(f"  → prah/karte/prah-{i}.webp")
        d = {"generated_at": generated, "days": days, "cities": cities,
             "source": "Copernicus CAMS via Open-Meteo, CC BY 4.0"}
        ac.write_json(DATA_PATH, d)
    except Exception as e:  # noqa: BLE001
        print(f"✗ Open-Meteo/CAMS: {e}", file=sys.stderr)
        d = ac.read_json(DATA_PATH)
        if not d:
            return 1
        stale = (f'  <p class="callout"><strong>Podatki niso sveži:</strong> vir ob zadnjem teku ni bil dosegljiv, '
                 f'prikazan je posnetek z {_html.escape(ac.fmt_dt_local(d["generated_at"]))}.</p>\n')
    title = "Saharski prah nad Evropo in Slovenijo: napoved"
    desc = ("Napoved saharskega prahu za 4 dni: zemljevid Evrope ter prah in PM10 za slovenske kraje. "
            "Model CAMS, ne meritev.")
    ac.write_site_page(REL + "index.html", REL, title, desc, build_body(d, stale), FAQ, "Saharski prah", "2026-10-22",
                       modified=d["generated_at"][:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
