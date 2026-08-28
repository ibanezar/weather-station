#!/usr/bin/env python3
"""
tools/generate_hmeljar_page.py — MeteoHmeljar: /meteohmeljar/ + parcelne strani.

Bere data/hmeljar_parcele.yaml (parcele + operation_profiles), za vsako
aktivno parcelo pokliče Open-Meteo (urno + dnevno, na TOČNIH koordinatah
parcele) in ARSO opozorila (isti Worker vir kot /nevihte/ — fetch_alerts()/
classify() sta uvožena iz generate_arso_newsjack_post.py, ne podvojena, isti
vzorec kot inject_arso_warnings.py), izračuna SprayScore/PeronosporaRisk/
PepelovkaRisk/WaterBalance/StormRisk prek tools/hmeljar_model.py (fm) in
izriše statično stran na parcelo + skupni indeks.

Fenologija (GDD₁₀) ostaja vezana na postajo (history.json), ne na parcelo —
glej opombo na vrhu hmeljar_model.py.

Dnevnik na parcelo (data/meteohmeljar/<id>-log.json, zadnjih 14 dni) hrani
PeronosporaRisk/PepelovkaRisk/cumulative_deficit/balance_7d za trend puščice
in Decision Engine ("preskok" bolezenskega nivoja) — cumulative_deficit je po
definiciji tekoč seštevek (glej §4 spec), ki ga ni mogoče izpeljati samo iz
enega Open-Meteo okna.

Ob nedosegljivem viru za posamezno parcelo: stran za to parcelo ostane stara,
tek nadaljuje z ostalimi (isto načelo kot inject_forecast.py — raje stara
stran kot prazna).

Podrobna specifikacija: docs/meteohmeljar-v0.1-spec.md

Wired into:
  .github/workflows/hmeljar-forecast.yml (urno)

Usage:
  python3 tools/generate_hmeljar_page.py
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo   # noqa: E402 — shared template helpers
import hmeljar_model as fm         # noqa: E402 — SprayScore/PeronosporaRisk/… engine
from generate_arso_newsjack_post import LOCAL_TZ, fetch_alerts  # noqa: E402 — ne podvajaj

ROOT = seo.ROOT
TODAY = seo.TODAY
PARCELE_YAML = os.path.join(ROOT, "data", "hmeljar_parcele.yaml")
LOG_DIR = os.path.join(ROOT, "data", "meteohmeljar")
HOURLY_FIELDS = ("temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,"
                  "wind_speed_10m,wind_gusts_10m,is_day,cape")
STORM_ARSO_TYPES = {"WarningTS", "WarningWind", "WarningRA"}
DAN_KRATKO = ["ned", "pon", "tor", "sre", "čet", "pet", "sob"]


# ── config + viri ─────────────────────────────────────────────────────────

def load_parcele():
    with open(PARCELE_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    profiles = data.get("operation_profiles") or {}
    out = []
    for p in data.get("parcele") or []:
        profile = dict(fm.DEFAULT_OPERATION_PROFILE)
        profile.update(profiles.get(p.get("operation_profile"), {}) or {})
        p = dict(p)
        p["profile"] = profile
        out.append(p)
    return out


def fetch_hourly(lat, lon):
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": HOURLY_FIELDS,
        "past_days": 2, "forecast_days": 7,
        "timezone": "Europe/Ljubljana",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_daily(lat, lon):
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "daily": "et0_fao_evapotranspiration,precipitation_sum",
        "past_days": 2, "forecast_days": 7,
        "timezone": "Europe/Ljubljana",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def slice_hourly(hourly, start, end):
    keys = ["time", "temperature_2m", "relative_humidity_2m", "precipitation",
            "precipitation_probability", "wind_speed_10m", "wind_gusts_10m", "is_day", "cape"]
    start = max(0, start)
    return {k: (hourly.get(k) or [])[start:end] for k in keys}


def now_index(times):
    now_key = dt.datetime.now().strftime("%Y-%m-%dT%H:00")
    for i, t in enumerate(times):
        if t >= now_key:
            return i
    return max(0, len(times) - 1)


def official_storm_warning_active(alerts):
    return any(a.get("type") in STORM_ARSO_TYPES and a.get("level") in ("orange", "red") for a in alerts)


# ── dnevnik (trend + kumulativni primanjkljaj) ──────────────────────────────

def load_log(parcela_id):
    path = os.path.join(LOG_DIR, f"{parcela_id}-log.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def save_log(parcela_id, entries):
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"{parcela_id}-log.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries[-14:], f, ensure_ascii=False, indent=1)
        f.write("\n")


def upsert_today(log, today_iso, values):
    if log and log[-1]["date"] == today_iso:
        log[-1].update(values)
    else:
        log.append({"date": today_iso, **values})
    return log


def log_entry_for_date(log, iso):
    return next((e for e in log if e["date"] == iso), None)


def prev_cumulative_deficit(log, today_iso):
    """Kumulativni primanjkljaj je tekoč seštevek — 'včerajšnja' vrednost
    pride iz dnevnika, ne iz enega Open-Meteo okna (glej §4 spec)."""
    if log and log[-1]["date"] == today_iso and len(log) >= 2:
        return log[-2]["cumulative_deficit"]
    if log and log[-1]["date"] != today_iso:
        return log[-1]["cumulative_deficit"]
    return 0.0


def compute_water_balance(daily, log, today_iso):
    dates = daily.get("time") or []
    precip = daily.get("precipitation_sum") or []
    et0 = daily.get("et0_fao_evapotranspiration") or []
    if today_iso not in dates:
        return None
    idx = dates.index(today_iso)
    today_rain = precip[idx] if idx < len(precip) else None
    today_et0 = et0[idx] if idx < len(et0) else None
    today_balance = fm.daily_balance(today_rain, today_et0)

    prev_cd = prev_cumulative_deficit(log, today_iso)
    cd_today = fm.cumulative_deficit(prev_cd, today_balance, today_rain)

    lo7 = max(0, idx - 6)
    balance_7d = sum((fm.daily_balance(precip[i] if i < len(precip) else None,
                                        et0[i] if i < len(et0) else None) or 0)
                      for i in range(lo7, idx + 1))
    hi3 = min(len(dates), idx + 4)
    balance_3d_fwd = sum((fm.daily_balance(precip[i] if i < len(precip) else None,
                                            et0[i] if i < len(et0) else None) or 0)
                          for i in range(idx + 1, hi3))

    three_days_ago = (dt.date.fromisoformat(today_iso) - dt.timedelta(days=3)).isoformat()
    prior_entry = log_entry_for_date(log, three_days_ago)
    trend = fm.water_balance_trend(balance_7d, prior_entry["balance_7d"] if prior_entry else None)

    return {
        "cumulative_deficit": round(cd_today, 1),
        "balance_7d": round(balance_7d, 1),
        "balance_3d_fwd": round(balance_3d_fwd, 1),
        "trend": trend,
    }


# ── rendering ────────────────────────────────────────────────────────────

def _day_label(iso_date, i):
    if i == 0:
        return "danes"
    if i == 1:
        return "jutri"
    d = dt.date.fromisoformat(iso_date)
    return DAN_KRATKO[(d.weekday() + 1) % 7] + f" {d.day}. {d.month}."


def render_bar(points):
    if not points:
        return ""
    colors = {"green": "#22c55e", "yellow": "#f59e0b", "red": "#ef4444"}
    w = 100.0 / len(points)
    segs = "".join(
        f'<span title="{p["time"][11:16]} — {p["score"]}" style="display:inline-block;'
        f'width:{w:.3f}%;height:100%;background:{colors[fm.tier(p["score"])]}"></span>'
        for p in points
    )
    return f'<div style="display:flex;height:14px;border-radius:4px;overflow:hidden;margin:.4rem 0">{segs}</div>'


def day_summary(spray_series, hourly_forward_all, date_iso):
    day_spray = [p for p in spray_series if p["time"][:10] == date_iso]
    has_green = any(fm.tier(p["score"]) == "green" for p in day_spray)
    has_yellow = any(fm.tier(p["score"]) == "yellow" for p in day_spray)
    idxs = [i for i, t in enumerate(hourly_forward_all.get("time") or []) if t[:10] == date_iso]
    storm_max = 0.0
    for i in idxs:
        s, _ = fm.storm_risk_hour(hourly_forward_all, i)
        storm_max = max(storm_max, s)
    if storm_max >= 50:
        return "🔴", "možne nevihte / naliv"
    if has_green:
        return "🟢", "dobro okno za škropljenje"
    if has_yellow:
        return "🟡", "delno primerno za škropljenje"
    return "🔴", "neprimerno za škropljenje"


def render_parcela_body(parcela, gdd, stage_label, stage_emoji, spray_series, best_win,
                         peronospora_now, pepelovka_now, water, storm, decision,
                         hourly_forward_all, now_utc):
    n = seo.num
    profile = parcela["profile"]

    pheno_html = (f'  <p class="post-meta">{stage_emoji} Fenologija (dolina): <strong>{stage_label}</strong> '
                  f'(GDD₁₀ {gdd}) · {parcela.get("sorta","—")} · {n(parcela.get("povrsina_ha"), 1)} ha · '
                  f'osveženo {now_utc.astimezone(LOCAL_TZ):%-d. %-m. %Y ob %H:%M}</p>')

    dec_html = ("\n".join(f'    <p style="margin:.3rem 0">{d["text"]}</p>' for d in decision)
                if decision else
                '    <p class="archive-intro" style="margin:0">Brez posebnosti — pogoji so v mejah, nič ne izstopa.</p>')
    hero = f'''  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">📋 Danes je pomembno</div>
{dec_html}
  </div>'''

    today_date = spray_series[0]["time"][:10] if spray_series else None
    today_pts = [p for p in spray_series if p["time"][:10] == today_date]
    bar = render_bar(today_pts)
    if best_win:
        reason = fm.window_close_reason(spray_series, best_win)
        okno_txt = (f'Najboljše okno: <strong>{best_win["start"][11:16]}–{best_win["end"][11:16]}</strong>'
                    + (f' (zapira se zaradi: {reason})' if reason else ''))
    else:
        okno_txt = "V naslednjih 24 h ni dobrega škropilnega okna (vsaj 3 ure zapored)."
    spray_html = f'''  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">🧪 Škropljenje</div>
{bar}
    <p class="archive-intro" style="margin:.4rem 0 0">{okno_txt}</p>
    <p class="muted-note">Pragovi (operation_profile): veter do {n(profile["wind_max_kmh"], 0)} km/h, sunki do
    {n(profile["gust_max_kmh"], 0)} km/h, {n(profile["temperature_min_c"], 0)}–{n(profile["temperature_max_c"], 0)} °C,
    vsaj {profile["rainfree_hours_required"]}h brez dežja po nanosu. Meteorološko okno — nikoli ne preglasi
    registracije, etikete ali navodil konkretnega FFS.</p>
  </div>'''

    disease_html = f'''  <div class="card" style="margin-bottom:1rem">
    <table class="stats">
      <tr><th>Peronospora</th><td>{peronospora_now} % — {fm.risk_label(peronospora_now)}</td></tr>
      <tr><th>Pepelovka</th><td>{pepelovka_now} % — {fm.risk_label(pepelovka_now)}</td></tr>
    </table>
    <p class="muted-note">Meteorološka ugodnost za okužbo, ni diagnoza — pragi so prvi približek iz tuje
    literature (APS/Oregon State), še ne umerjeni na slovenskih podatkih.</p>
  </div>'''

    if water:
        b7 = water["balance_7d"]; b3 = water["balance_3d_fwd"]; cd = water["cumulative_deficit"]
        water_html = f'''  <div class="card" style="margin-bottom:1rem">
    <table class="stats">
      <tr><th>7-dnevna bilanca</th><td>{"+" if b7 >= 0 else ""}{n(b7, 1)} mm</td></tr>
      <tr><th>Naslednji 3 dnevi (napoved)</th><td>{"+" if b3 >= 0 else ""}{n(b3, 1)} mm</td></tr>
      <tr><th>Kumulativni primanjkljaj</th><td>{n(cd, 1)} mm</td></tr>
      <tr><th>Trend</th><td>{water["trend"]}</td></tr>
    </table>
    <p class="muted-note">Samo meteorološka bilanca (padavine − ET₀, FAO Penman-Monteith) — brez tal ali
    koeficienta rastline (Kc) v v0.1.</p>
  </div>'''
    else:
        water_html = '  <p class="muted-note">Vodna bilanca trenutno ni na voljo.</p>'

    storm_cas = (f'čez ~{storm["time_to_event_h"]}h' if storm["time_to_event_h"] is not None
                 else "ni pričakovana v naslednjih 12h")
    storm_driver_txt = f', glavno tveganje: {storm["driver"]}' if storm["driver"] else ""
    storm_html = f'''  <div class="card" style="margin-bottom:1rem">
    <p class="archive-intro" style="margin:0">Ocena za naslednjih 12h: <strong>{storm["max_score"]}/100</strong>
    ({storm_cas}{storm_driver_txt}).</p>
    <p class="muted-note">Lastna ocena (sunki, intenziteta padavin, posredna ocena neviht) — ločena od uradnih
    opozoril ARSO, ki so vključena kot dvig ocene, kadar veljajo.</p>
  </div>'''

    outlook_rows = []
    for i in range(1, 4):
        d = (TODAY + dt.timedelta(days=i)).isoformat()
        badge, note = day_summary(spray_series, hourly_forward_all, d)
        outlook_rows.append(f'      <tr><th>{_day_label(d, i)}</th><td>{badge} {note}</td></tr>')
    outlook_html = '  <table class="stats">\n' + "\n".join(outlook_rows) + "\n  </table>"

    return f'''{pheno_html}
{hero}
{spray_html}
  <h2>Bolezni</h2>
{disease_html}
  <h2>Voda</h2>
{water_html}
  <h2>Nevarnosti</h2>
{storm_html}
  <h2>Naslednji 3 dnevi</h2>
{outlook_html}'''


def parcela_shell(slug, title, desc, inner_html):
    url = f"/meteohmeljar/{slug}/"
    crumbs = [("Meteorec", "/"), ("MeteoHmeljar", "/meteohmeljar/"), (title, None)]
    schema = "\n".join([seo.webpage_schema(url, title, desc), seo.crumbs_schema(crumbs)])
    body = f'''{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">{title}</h1>
{inner_html}
  <a class="back-link" href="/meteohmeljar/">← Nazaj na MeteoHmeljar</a>'''
    html = seo.page_shell(f"{title} — MeteoHmeljar", desc, url, schema, body)
    seo.write_page(f"meteohmeljar/{slug}/index.html", html, force=True)
    return url


def render_index(results):
    if not results:
        rows = '  <p class="archive-intro">Trenutno ni aktivnih parcel.</p>'
    else:
        cards = []
        for r in results:
            headline = r["decision"][0]["text"] if r["decision"] else "Brez posebnosti."
            cards.append(f'''  <div class="card" style="margin-bottom:1rem">
    <div class="clabel"><a href="{r["url"]}">{r["naziv"]}</a></div>
    <p class="archive-intro" style="margin:.3rem 0 0">{headline}</p>
  </div>''')
        rows = "\n".join(cards)
    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("MeteoHmeljar", None)])}
{seo.stn_badge()}
  <h1 class="page-title">MeteoHmeljar — parcele</h1>
  <p class="post-meta">Vreme → agronomska interpretacija → operativna odločitev, po parceli, za hmeljišča
  v Zgornji Savinjski dolini.</p>
{rows}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''
    desc = ("Škropilno okno, tveganje za peronosporo/pepelovko, vodna bilanca in nevarnost neurja po "
            "parceli za hmeljišča v Zgornji Savinjski dolini.")
    schema = "\n".join([
        seo.webpage_schema("/meteohmeljar/", "MeteoHmeljar", desc),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoHmeljar", None)]),
    ])
    html = seo.page_shell("MeteoHmeljar — parcele", desc, "/meteohmeljar/", schema, body)
    seo.write_page("meteohmeljar/index.html", html, force=True)


# ── glavni tek ───────────────────────────────────────────────────────────

def process_parcela(parcela, hist, now_utc, alerts):
    lat, lon, profile = parcela["lat"], parcela["lon"], parcela["profile"]
    slug = parcela["id"]
    today_iso = TODAY.isoformat()

    hourly_raw = fetch_hourly(lat, lon).get("hourly") or {}
    daily_raw = fetch_daily(lat, lon).get("daily") or {}
    idx = now_index(hourly_raw.get("time") or [])

    hourly_trailing = slice_hourly(hourly_raw, idx - 24, idx)
    hourly_forward48 = slice_hourly(hourly_raw, idx, idx + 48)
    hourly_forward_all = slice_hourly(hourly_raw, idx, len(hourly_raw.get("time") or []))
    hourly_next12 = slice_hourly(hourly_raw, idx, idx + 12)

    gdd = fm.gdd10(hist, TODAY)
    _, _, stage_label, stage_emoji = fm.hop_stage(gdd)

    spray_series = fm.spray_score_series(hourly_forward_all, profile)
    runs = fm.spray_windows(spray_series)
    best_win = fm.best_window(runs)

    peronospora_now = fm.peronospora_risk(hourly_trailing, hourly_forward48)
    pepelovka_now = fm.pepelovka_risk(hourly_trailing, hourly_forward48)

    log = load_log(slug)
    yesterday_entry = log_entry_for_date(log, (TODAY - dt.timedelta(days=1)).isoformat())
    peronospora_prev = yesterday_entry["peronospora_risk"] if yesterday_entry else None
    pepelovka_prev = yesterday_entry["pepelovka_risk"] if yesterday_entry else None

    water = compute_water_balance(daily_raw, log, today_iso)
    storm = fm.storm_summary(hourly_next12, official_storm_warning_active(alerts))

    decision = fm.decide(
        storm=storm, best_win=best_win, spray_series=spray_series,
        peronospora_prev=peronospora_prev, peronospora_now=peronospora_now,
        pepelovka_prev=pepelovka_prev, pepelovka_now=pepelovka_now,
        cumulative_deficit_now=water["cumulative_deficit"] if water else None,
    )

    log = upsert_today(log, today_iso, {
        "peronospora_risk": peronospora_now,
        "pepelovka_risk": pepelovka_now,
        "cumulative_deficit": water["cumulative_deficit"] if water else 0.0,
        "balance_7d": water["balance_7d"] if water else None,
    })
    save_log(slug, log)

    body = render_parcela_body(parcela, gdd, stage_label, stage_emoji, spray_series, best_win,
                                peronospora_now, pepelovka_now, water, storm, decision,
                                hourly_forward_all, now_utc)
    desc = (f'MeteoHmeljar za {parcela["naziv"]}: škropilno okno, tveganje za peronosporo/pepelovko, '
            f'vodna bilanca in nevarnost neurja, osveženo urno.')
    url = parcela_shell(slug, parcela["naziv"], desc, body)

    return {"id": slug, "naziv": parcela["naziv"], "url": url, "decision": decision,
            "storm_max": storm["max_score"], "best_win": best_win,
            "peronospora": peronospora_now, "pepelovka": pepelovka_now}


def main():
    print(f"[{TODAY}] MeteoHmeljar: nalagam parcele in postajno zgodovino …")
    parcele = load_parcele()
    active = [p for p in parcele if p.get("aktivna")]
    if not active:
        print("✗ Ni aktivnih parcel v data/hmeljar_parcele.yaml", file=sys.stderr)
        return 1

    hist = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    now_utc = dt.datetime.now(dt.timezone.utc)

    try:
        alerts, _issued = fetch_alerts()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"⚠ ARSO opozorila nedosegljiva ({e}) — StormRisk brez uradnega dviga.", file=sys.stderr)
        alerts = []

    results = []
    for p in active:
        try:
            results.append(process_parcela(p, hist, now_utc, alerts))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"⚠ {p['id']}: vir ni dosegljiv ({e}) — stran ostane stara.", file=sys.stderr)
            continue

    if not results:
        print("✗ Nobene parcele ni bilo mogoče obdelati.", file=sys.stderr)
        return 1

    render_index(results)
    for r in results:
        print(f"  → {r['url']} (okno: {'da' if r['best_win'] else 'ne'}, "
              f"Peronospora {r['peronospora']}%, Pepelovka {r['pepelovka']}%, Nevihta {r['storm_max']}/100)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
