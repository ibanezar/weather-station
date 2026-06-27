#!/usr/bin/env python3
"""
tools/inject_current_weather.py — Pre-render the latest known measurement into
static, crawlable HTML in index.html.

The homepage hero ("Trenutno vreme") is filled by JavaScript, so search engines
see only "—" placeholders. This script injects the last known daily measurement
from history.json (value + date) between marker comments in index.html, giving
crawlers real content. The live JS hero is untouched and still updates on load.

Run after history.json is refreshed (wired into .github/workflows/update-history.yml).

Usage:
  python3 tools/inject_current_weather.py
"""
import json, os, re, sys

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


def build_block():
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
    return f'{START}\n  <p class="wx-static" id="wx-static">{text}</p>\n  {END}'


def main():
    block = build_block()
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
