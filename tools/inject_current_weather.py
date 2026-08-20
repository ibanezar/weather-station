#!/usr/bin/env python3
"""
tools/inject_current_weather.py — Pre-render the latest known measurement into
static, crawlable HTML in index.html.

The homepage hero ("Trenutno vreme") is filled by JavaScript, so search engines
see only "—" placeholders — and browsers can't paint the LCP element (the big
temperature number) until app.js has loaded, run, and fetched live data. This
script injects a real measurement between marker comments in index.html, and
(in --live mode) also patches the hero's number spans directly so the page
paints real values on first render. The live JS hero is untouched code-wise
and still overwrites these numbers with fresh data once it loads.

Two modes:
  (default)  inject the last known daily summary from history.json (value + date)
  --live     fetch the current observation from the Weather Underground PWS API
             (station IREICA1), inject instantaneous values + exact time into the
             WX-STATIC text block, and patch the hero card's number spans;
             falls back to the daily summary (text block only) if the API is
             unreachable.

Wired into:
  .github/workflows/update-history.yml   (daily, default mode)
  .github/workflows/prerender-current.yml (hourly, --live mode)

Usage:
  python3 tools/inject_current_weather.py [--live]
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
RECICA = os.path.join(ROOT, "vreme-recica-ob-savinji", "index.html")
HIST = os.path.join(ROOT, "history.json")

# Strani, ki dobijo statično meritev, in sklepni stavek bloka za vsako. Besedilo
# se razlikuje, ker ima naslovna stran nad blokom živo kartico, pristajalna pa ne
# — na njej bi »posodabljajo zgoraj« kazalo na nekaj, česar tam ni.
# Naslovna stran napovedi nima v statičnem HTML (nima markerjev WX-FC7/WX-FCH —
# ta sta samo na pristajalni strani), zato jo pajek brez JS tu ne vidi. Sklepni
# stavek ga zato napoti na statično tabelo napovedi, namesto da bi napoved ostala
# dosegljiva le prek JavaScripta.
TAIL_INDEX = ('Vrednosti v živo se posodabljajo zgoraj; pretekli dnevi so v '
              '<a href="/vreme/">vremenskem arhivu</a>, '
              '<a href="/vreme-recica-ob-savinji/#napoved">napoved za prihodnje dni</a> '
              'pa na strani Vreme Rečica ob Savinji.')
TAIL_RECICA = ('Meritev se osveži vsako uro. Pretekli dnevi so v '
               '<a href="/vreme/">vremenskem arhivu</a>, vrednosti v živo in urna '
               'napoved pa na <a href="/">naslovni strani</a>.')

# Razred bloka. Na naslovni strani je `wx-static` v style.css namenoma vizualno
# skrit — vrednosti tam prikazuje živa kartica, blok je le berljiv dvojnik za
# iskalnike. Na pristajalni strani žive kartice ni, zato mora biti blok viden;
# `wx-now` (vreme/vreme.css) to pove izrecno. Prej je bil viden le zato, ker se
# style.css na tisti strani ne naloži — to ni bila odločitev, ampak naključje.
CLS_INDEX = "wx-static"
CLS_RECICA = "wx-static wx-now"
TARGETS = [(INDEX, TAIL_INDEX, CLS_INDEX), (RECICA, TAIL_RECICA, CLS_RECICA)]

START = "<!-- WX-STATIC:START (auto: tools/inject_current_weather.py) -->"
END = "<!-- WX-STATIC:END -->"

MES_GEN = {1: "januarja", 2: "februarja", 3: "marca", 4: "aprila", 5: "maja",
           6: "junija", 7: "julija", 8: "avgusta", 9: "septembra", 10: "oktobra",
           11: "novembra", 12: "decembra"}


def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def fmtd(iso):
    y, m, dd = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f"{dd}. {MES_GEN[m]} {y}"


WU_URL = ("https://api.weather.com/v2/pws/observations/current"
          "?stationId=IREICA1&format=json&units=m&apiKey=619a8bb3ba4d42069a8bb3ba4d02061f")

# Isti WU API, isti ključ in postaja kot WU_URL zgoraj — samo drug endpoint
# (uro-natančna zgodovina zadnjih 7 dni namesto trenutne meritve), da lahko
# napolnimo 7-dnevno tabelo in dnevni min/max/povprečje z realnimi podatki.
WU_HOURLY_URL = ("https://api.weather.com/v2/pws/observations/hourly/7day"
                  "?stationId=IREICA1&format=json&units=m&apiKey=619a8bb3ba4d42069a8bb3ba4d02061f"
                  "&numericPrecision=decimal")

MES_ABBR = {1: "jan.", 2: "feb.", 3: "mar.", 4: "apr.", 5: "maj", 6: "jun.",
            7: "jul.", 8: "avg.", 9: "sep.", 10: "okt.", 11: "nov.", 12: "dec."}


def wrap(text, cls=CLS_INDEX):
    return f'{START}\n  <p class="{cls}" id="wx-static">{text}</p>\n  {END}'


def build_block_history(tail=TAIL_INDEX, cls=CLS_INDEX):
    hist = json.load(open(HIST, encoding="utf-8"))
    # Zadnji dan s PRAVO meritvijo: modelske (ERA5) ocene preskočimo, da uvod ne
    # prikazuje rezervnih podatkov kot "meritev postaje IREICA1".
    real = [k for k in hist if hist[k].get("src") != "era5"]
    last = max(real) if real else max(hist)
    v = hist[last]

    parts = [f"povprečna temperatura {num(v.get('tempAvg'))} °C"]
    if v.get("tempHigh") is not None and v.get("tempLow") is not None:
        parts.append(f"najvišja {num(v['tempHigh'])} °C, najnižja {num(v['tempLow'])} °C")
    parts.append(f"{num(v.get('precipTotal', 0))} mm padavin")
    if v.get("humidityAvg") is not None:
        parts.append(f"relativna vlažnost {num(v['humidityAvg'], 0)} %")
    if v.get("windspeedHigh") is not None:
        parts.append(f"najmočnejši sunek vetra {num(v['windspeedHigh'])} km/h")
    summary = ", ".join(parts[:2]) + " — " + ", ".join(parts[2:]) + "."

    text = (f'Zadnja znana dnevna meritev meteorološke postaje IREICA1 na Rečici ob Savinji '
            f'(<time datetime="{last}">{fmtd(last)}</time>): {summary} {tail}')
    return wrap(text, cls)


def fetch_live_wu():
    """Return the current WU observation for IREICA1, or None on any failure."""
    try:
        with urllib.request.urlopen(WU_URL, timeout=15) as r:
            obs = json.loads(r.read())["observations"][0]
        age_min = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(obs["obsTimeUtc"].replace("Z", "+00:00"))
                   ).total_seconds() / 60
        if age_min > 180:        # stale (station offline) → fall back to history
            return None
        return obs
    except Exception as e:
        print(f"WU API ni dosegljiv ({e}) — fallback na history.json.", file=sys.stderr)
        return None


def build_block_live(obs, tail=TAIL_INDEX, cls=CLS_INDEX):
    m = obs.get("metric", {})
    # obsTimeLocal e.g. "2026-06-27 14:35:00"
    local = obs.get("obsTimeLocal", "")
    dt = datetime.strptime(local, "%Y-%m-%d %H:%M:%S") if local else datetime.now()
    iso, hhmm = dt.strftime("%Y-%m-%dT%H:%M"), dt.strftime("%H:%M")

    parts = [f"temperatura {num(m.get('temp'))} °C"]
    if m.get("dewpt") is not None:
        parts.append(f"rosišče {num(m['dewpt'])} °C")
    if obs.get("humidity") is not None:
        parts.append(f"relativna vlažnost {num(obs['humidity'], 0)} %")
    if m.get("windSpeed") is not None:
        gust = f" (sunki {num(m.get('windGust'))} km/h)" if m.get("windGust") is not None else ""
        parts.append(f"veter {num(m['windSpeed'])} km/h{gust}")
    if m.get("pressure") is not None:
        parts.append(f"zračni tlak {num(m['pressure'], 0)} hPa")
    if m.get("precipTotal") is not None:
        parts.append(f"padavine danes {num(m['precipTotal'])} mm")

    text = (f'Trenutno vreme na Rečici ob Savinji '
            f'(meritev postaje IREICA1 ob <time datetime="{iso}">{hhmm}</time>, {fmtd(iso)}): '
            f'{", ".join(parts)}. {tail}')
    return wrap(text, cls)


def js_num(x):
    """Mimic JS Number→string coercion (5.0 → '5', 5.3 → '5.3'), dot decimal."""
    f = float(x)
    return str(int(f)) if f == int(f) else str(f)


def _patch_span(html, elem_id, value_text, drop_shimmer=True):
    """Replace the text right after `id="elem_id"...>` up to the next '<',
    optionally dropping a `skel-shimmer` class so the pre-rendered value
    doesn't show the loading animation before JS hydrates it."""
    pattern = re.compile(
        r'(<[a-z]+\b[^>]*\bid="' + re.escape(elem_id) + r'"[^>]*>)([^<]*)'
    )

    def repl(m):
        tag = m.group(1)
        if drop_shimmer:
            tag = re.sub(r'\s*\bskel-shimmer\b', '', tag)
            tag = re.sub(r'\s+class=""', '', tag)
        return tag + value_text

    return pattern.subn(repl, html, count=1)


def patch_hero(html, obs):
    """Fill the hero card's number spans with the live observation so the
    LCP element (the big temperature) paints from static HTML instead of
    waiting on the client-side fetch. Condition icon/label are left as-is —
    they need app.js's fuller condition classification.

    If the observation itself is missing temp (seen in practice: a station
    telemetry gap where WU returns pressure but nulls everything else), skip
    patching entirely rather than showing a bare "—" with the loading
    shimmer removed — that would look more broken than the skeleton state."""
    m = obs.get("metric", {})
    if m.get("temp") is None:
        print("OPOZORILO: WU obs brez temp — hero ni popravljen, ostane skelet.", file=sys.stderr)
        return html
    humidity = obs.get("humidity")
    uv = obs.get("uv") or 0
    feels = m.get("heatIndex")
    if feels is None:
        feels = m.get("windChill")
    if feels is None:
        feels = m.get("temp")
    gust = m.get("windGust")
    if gust is None:
        gust = m.get("windSpeed")

    patches = [
        ("temp-val", num(m.get("temp"), 1)),
        ("feels-val", num(feels, 1)),
        ("dewpt-hero", num(m.get("dewpt"), 1)),
        ("hs-humidity", num(humidity, 0)),
        ("hs-pressure", num(m.get("pressure"), 1)),
        ("hs-wind", num(m.get("windSpeed"), 1)),
        ("hs-gust", num(gust, 1)),
        ("hs-rain-today", num(m.get("precipTotal", 0), 1)),
        ("hs-uv", js_num(uv) if uv else "—"),
    ]
    for elem_id, value_text in patches:
        html, n = _patch_span(html, elem_id, value_text)
        if n == 0:
            print(f"OPOZORILO: hero element #{elem_id} ni najden — preskočeno.", file=sys.stderr)

    rr = m.get("precipRate", 0) or 0
    html = re.sub(
        r'(<span id="hs-rain-rate"[^>]*>)intenziteta: [^<]*(</span>)',
        lambda mo: mo.group(1) + f"intenziteta: {num(rr, 1)} mm/h" + mo.group(2),
        html, count=1,
    )
    return html


def fetch_hourly_wu():
    """Return the last 7 days of hourly WU observations for IREICA1, or None
    on any failure (network error, malformed response)."""
    try:
        with urllib.request.urlopen(WU_HOURLY_URL, timeout=20) as r:
            data = json.loads(r.read())
        obs = data.get("observations") or []
        return obs or None
    except Exception as e:
        print(f"WU hourly API ni dosegljiv ({e}) — 7-dnevna tabela in dnevni "
              f"min/max ostaneta nespremenjena.", file=sys.stderr)
        return None


def fmt_hist_date(iso):
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f"{d}. {MES_ABBR[m]} {y}"


def build_daily_summaries(observations):
    """Group hourly WU observations into daily min/max/avg summaries — the
    Python equivalent of buildDailySummaries() in app.js, applied to the same
    hourly/7day endpoint the client fetches once JS hydrates. Note: in this
    WU API humidityAvg lives on the observation itself, not under `metric`
    (unlike tempAvg/windspeedAvg/precipTotal) — read it from there."""
    by_day = {}
    for o in observations:
        day = (o.get("obsTimeLocal") or "")[:10]
        if not day:
            continue
        m = o.get("metric", {})
        d = by_day.setdefault(day, {"highs": [], "lows": [], "temps": [],
                                     "rains": [], "winds": [], "gusts": [], "hums": []})
        if m.get("tempHigh") is not None:
            d["highs"].append(m["tempHigh"])
        elif m.get("tempAvg") is not None:
            d["highs"].append(m["tempAvg"])
        if m.get("tempLow") is not None:
            d["lows"].append(m["tempLow"])
        elif m.get("tempAvg") is not None:
            d["lows"].append(m["tempAvg"])
        if m.get("tempAvg") is not None:
            d["temps"].append(m["tempAvg"])
        if m.get("precipTotal") is not None:
            d["rains"].append(m["precipTotal"])
        if m.get("windspeedAvg") is not None:
            d["winds"].append(m["windspeedAvg"])
        if m.get("windspeedHigh") is not None:
            d["gusts"].append(m["windspeedHigh"])
        hum = o.get("humidityAvg", m.get("humidityAvg"))
        if hum is not None:
            d["hums"].append(hum)

    out = []
    for day, d in by_day.items():
        out.append({
            "date": day,
            "tempHigh": max(d["highs"]) if d["highs"] else None,
            "tempLow": min(d["lows"]) if d["lows"] else None,
            "tempAvg": (sum(d["temps"]) / len(d["temps"])) if d["temps"] else None,
            "precipTotal": max(d["rains"]) if d["rains"] else 0,
            "windspeedAvg": (sum(d["winds"]) / len(d["winds"])) if d["winds"] else None,
            "windspeedHigh": max(d["gusts"]) if d["gusts"] else None,
            "humidityAvg": round(sum(d["hums"]) / len(d["hums"])) if d["hums"] else None,
        })
    out.sort(key=lambda x: x["date"])
    return out


def build_day_stats(observations):
    """Today's high/low/avg temperature + times — Python equivalent of
    applyDayStats() in app.js. "Today" is taken as the most recent
    observation's own local date rather than the build machine's date, so a
    build running just after local midnight doesn't misclassify."""
    if not observations:
        return None
    today = max((o.get("obsTimeLocal") or "")[:10] for o in observations if o.get("obsTimeLocal"))
    today_obs = [o for o in observations if (o.get("obsTimeLocal") or "").startswith(today)]
    max_t = min_t = max_time = min_time = None
    temp_sum, count, total_rain = 0.0, 0, 0.0
    for o in today_obs:
        m = o.get("metric", {})
        t = m.get("tempAvg")
        if t is None:
            continue
        local = o.get("obsTimeLocal", "")
        hhmm = local[11:16] if len(local) >= 16 else ""
        if max_t is None or t > max_t:
            max_t, max_time = t, hhmm
        if min_t is None or t < min_t:
            min_t, min_time = t, hhmm
        temp_sum += t
        count += 1
        total_rain = max(total_rain, m.get("precipTotal") or 0)
    if count == 0:
        return None
    return {"high": max_t, "low": min_t, "avg": temp_sum / count,
            "hiTime": max_time, "loTime": min_time, "rain": total_rain}


def build_history_rows(daily):
    """Mirror applyHistory()'s row markup in app.js exactly (same classes,
    same inline unit-span style) so JS hydration doesn't cause a visible
    style flash when it overwrites these rows with fresh data."""
    u = '<span style="font-size:.74rem;color:var(--muted);margin-left:1px">'
    rows = []
    for d in list(reversed(daily))[:7]:
        rows.append(
            "<tr>"
            f"<td>{fmt_hist_date(d['date'])}</td>"
            f"<td class=\"td-high\">{num(d['tempHigh'], 1)}{u}°C</span></td>"
            f"<td class=\"td-low\">{num(d['tempLow'], 1)}{u}°C</span></td>"
            f"<td>{num(d['tempAvg'], 1)}{u}°C</span></td>"
            f"<td class=\"td-rain\">{num(d['precipTotal'], 1)}{u}mm</span></td>"
            f"<td>{num(d['windspeedAvg'], 1)}{u}km/h</span></td>"
            f"<td style=\"color:var(--purple)\">{num(d['windspeedHigh'], 1)}{u}km/h</span></td>"
            f"<td>{num(d['humidityAvg'], 0)}{u}%</span></td>"
            "</tr>"
        )
    return "\n".join(rows)


def patch_history_table(html, daily):
    rows_html = build_history_rows(daily)
    pattern = re.compile(r'(<tbody id="history-tbody">).*?(</tbody>)', re.S)
    new_html, n = pattern.subn(lambda m: m.group(1) + "\n" + rows_html + "\n          " + m.group(2), html, count=1)
    if n == 0:
        print("OPOZORILO: #history-tbody ni najden — 7-dnevna tabela preskočena.", file=sys.stderr)
        return html
    return new_html


def patch_day_summary(html, stats):
    """Fill the day-high/day-low/day-avg block (and their times) — kept to
    exactly the three items named for pre-rendering; "Dež danes" (day-rain)
    is left as-is."""
    patches = [
        ("day-high", num(stats["high"], 1)),
        ("day-low", num(stats["low"], 1)),
        ("day-avg", num(stats["avg"], 1)),
    ]
    if stats.get("hiTime"):
        patches.append(("day-hi-time", stats["hiTime"]))
    if stats.get("loTime"):
        patches.append(("day-lo-time", stats["loTime"]))
    for elem_id, value_text in patches:
        html, n = _patch_span(html, elem_id, value_text)
        if n == 0:
            print(f"OPOZORILO: dnevni element #{elem_id} ni najden — preskočeno.", file=sys.stderr)
    return html


def main():
    live = "--live" in sys.argv[1:]
    obs = fetch_live_wu() if live else None

    # Urne podatke poberemo enkrat in jih uporabimo samo na naslovni strani
    # (tabela zadnjih 7 dni in dnevni povzetek obstajata le tam).
    hourly = fetch_hourly_wu() if live else None

    rc = 0
    for path, tail, cls in TARGETS:
        rel = os.path.relpath(path, ROOT)
        if not os.path.exists(path):
            print(f"OPOZORILO: {rel} ne obstaja — preskočeno.", file=sys.stderr)
            continue

        block = build_block_live(obs, tail, cls) if obs else build_block_history(tail, cls)
        html = open(path, encoding="utf-8").read()

        if START not in html or END not in html:
            print(f"ERROR: markerjev ni v {rel} — dodaj jih enkrat.", file=sys.stderr)
            rc = 1
            continue
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), block, html, flags=re.S)

        if path == INDEX:
            if obs:
                new = patch_hero(new, obs)
            if hourly:
                daily = build_daily_summaries(hourly)
                if daily:
                    new = patch_history_table(new, daily)
                stats = build_day_stats(hourly)
                if stats:
                    new = patch_day_summary(new, stats)

        if new != html:
            open(path, "w", encoding="utf-8").write(new)
            print(f"{rel}: posodobljena statična meritev.")
        else:
            print(f"{rel}: brez sprememb.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
