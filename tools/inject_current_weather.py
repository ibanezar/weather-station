#!/usr/bin/env python3
"""
tools/inject_current_weather.py — Pre-render the latest known measurement into
static, crawlable HTML in index.html.

The homepage hero ("Trenutno vreme") is filled by JavaScript, so search engines
see only "—" placeholders. This script injects a real measurement between marker
comments in index.html, giving crawlers real content. The live JS hero is
untouched and still updates on load.

Two modes:
  (default)  inject the last known daily summary from history.json (value + date)
  --live     fetch the current observation from the Weather Underground PWS API
             (station IREICA1) and inject instantaneous values + exact time;
             falls back to the daily summary if the API is unreachable.

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
HIST = os.path.join(ROOT, "history.json")

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


def wrap(text):
    return f'{START}\n  <p class="wx-static" id="wx-static">{text}</p>\n  {END}'


def build_block_history():
    hist = json.load(open(HIST, encoding="utf-8"))
    last = max(hist.keys())
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
            f'(<time datetime="{last}">{fmtd(last)}</time>): {summary} '
            f'Trenutne vrednosti v živo se posodabljajo zgoraj, vsak dan ima svojo stran v '
            f'<a href="/vreme/">vremenskem arhivu</a>.')
    return wrap(text)


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


def build_block_live(obs):
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
            f'{", ".join(parts)}. '
            f'Vrednosti v živo se posodabljajo zgoraj; pretekli dnevi so v '
            f'<a href="/vreme/">vremenskem arhivu</a>.')
    return wrap(text)


def main():
    live = "--live" in sys.argv[1:]
    block = None
    if live:
        obs = fetch_live_wu()
        if obs:
            block = build_block_live(obs)
    if block is None:
        block = build_block_history()
    html = open(INDEX, encoding="utf-8").read()

    if START in html and END in html:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), block, html, flags=re.S)
    else:
        print("ERROR: markers not found in index.html — add them once first.", file=sys.stderr)
        return 1

    if new != html:
        open(INDEX, "w", encoding="utf-8").write(new)
        print("index.html: posodobljena statična meritev.")
    else:
        print("index.html: brez sprememb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
