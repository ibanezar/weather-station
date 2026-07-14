#!/usr/bin/env python3
"""
tools/inject_record_watch.py — "Record Watch" freshness hook

Injects a static, crawlable sentence into index.html: how close today's
measurement is to the all-time record for this specific calendar day
(e.g. "Danes smo 2,3 °C od rekorda za 14. julij"), or — when today's value
IS the new record for this calendar day — an announcement of that instead.

This is a narrower, more frequently newsworthy statistic than the site's
absolute all-time record (see /rekord/): it compares only to the same
month-day across all prior years, so most days have a real number worth
stating, not just "not a record."

Wired into: .github/workflows/update-history.yml (daily, once yesterday's
final measurement is in history.json).

Usage:
  python3 tools/inject_record_watch.py
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
HIST = os.path.join(ROOT, "history.json")

START = "<!-- WX-RECORD-WATCH:START (auto: tools/inject_record_watch.py) -->"
END = "<!-- WX-RECORD-WATCH:END -->"

MES_NOM = {1: "januar", 2: "februar", 3: "marec", 4: "april", 5: "maj",
           6: "junij", 7: "julij", 8: "avgust", 9: "september", 10: "oktober",
           11: "november", 12: "december"}


def num(x, d=1):
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def wrap(text):
    return f'{START}\n  <p class="wx-static" id="wx-record-watch">{text}</p>\n  {END}'


def build_block():
    hist = json.load(open(HIST, encoding="utf-8"))
    real = [k for k in hist if hist[k].get("src") != "era5"]
    if not real:
        return None
    last = max(real)
    today_v = hist[last].get("tempHigh")
    if today_v is None:
        return None

    mmdd = last[5:]
    dm_label = f"{int(last[8:10])}. {MES_NOM[int(last[5:7])]}"
    prior = [(d, v["tempHigh"]) for d, v in hist.items()
             if d != last and d[5:] == mmdd and v.get("tempHigh") is not None]
    if len(prior) < 2:
        return None  # premalo let za smiseln rekord tega koledarskega dne

    rec_date, rec_val = max(prior, key=lambda dv: dv[1])
    years = len({d[:4] for d, _ in prior})

    if today_v > rec_val:
        text = (f'Danes ({dm_label}) smo na Rečici ob Savinji postavili nov rekord za ta koledarski dan: '
                 f'<strong>{num(today_v)} °C</strong> — prejšnji rekord je bil {num(rec_val)} °C '
                 f'({rec_date[:4]}), v {years}-letni zgodovini meritev postaje IREICA1 na ta dan.')
    else:
        diff = rec_val - today_v
        text = (f'Danes ({dm_label}) je bilo na Rečici ob Savinji {num(today_v)} °C — '
                 f'<strong>{num(diff)} °C</strong> od rekorda za ta koledarski dan '
                 f'({num(rec_val)} °C, {rec_date[:4]}), v {years}-letni zgodovini meritev postaje IREICA1.')

    return wrap(text)


def main():
    block = build_block()
    if block is None:
        print("Premalo podatkov za rekord tega koledarskega dne — preskačem.")
        return 0

    html = open(INDEX, encoding="utf-8").read()
    if START not in html or END not in html:
        print("ERROR: markers not found in index.html — add them once first.", file=sys.stderr)
        return 1

    new = re.sub(re.escape(START) + r".*?" + re.escape(END), block, html, flags=re.S)
    if new != html:
        open(INDEX, "w", encoding="utf-8").write(new)
        print("index.html: posodobljen 'record watch' blok.")
    else:
        print("index.html: brez sprememb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
