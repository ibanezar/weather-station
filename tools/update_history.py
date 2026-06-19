#!/usr/bin/env python3
"""
Osveži history.json z dnevnimi povzetki iz Cloudflare workerja.

    python3 tools/update_history.py 2026-06

Pokliče <WORKER_URL>/ecowitt-history?start=…&end=… (z Referer glavo, da
prebije zaščito origin), zmerja vrnjene dni v history.json in zapiše
nazaj v istem kompaktnem formatu (urejeno po datumu).
"""
import json, os, sys, calendar, urllib.request

WORKER = os.environ.get("WORKER_URL", "https://weatherireica1.filip-eremita.workers.dev")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ("tempHigh", "tempLow", "tempAvg", "precipTotal",
        "windspeedHigh", "windspeedAvg", "humidityAvg")

def fetch(start, end):
    url = f"{WORKER}/ecowitt-history?start={start}&end={end}"
    req = urllib.request.Request(url, headers={
        "Referer": "https://meteorec.si/",
        "Origin": "https://meteorec.si",
        "Accept": "application/json",
        # brskalniku podoben UA — privzeti Python-urllib UA Cloudflare blokira (403)
        "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)

def main():
    if len(sys.argv) < 2:
        sys.exit("Uporaba: update_history.py YYYY-MM")
    ym = sys.argv[1]
    y, m = int(ym[:4]), int(ym[5:7])
    start, end = f"{ym}-01", f"{ym}-{calendar.monthrange(y, m)[1]:02d}"
    data = fetch(start, end)
    summ = data.get("summaries") if isinstance(data, dict) else None
    if not summ:
        sys.exit(f"Worker ni vrnil podatkov za {ym}: {json.dumps(data)[:200]}")

    hp = os.path.join(ROOT, "history.json")
    hist = json.load(open(hp, encoding="utf-8"))
    added = 0
    for s in summ:
        d = s.get("obsTimeLocal", "")[:10]
        me = s.get("metric") or {}
        if not d.startswith(ym) or me.get("tempAvg") is None:
            continue
        hum = me.get("humidityAvg")
        hist[d] = {
            "tempHigh": me.get("tempHigh"), "tempLow": me.get("tempLow"),
            "tempAvg": me.get("tempAvg"), "precipTotal": me.get("precipTotal", 0),
            "windspeedHigh": me.get("windspeedHigh"), "windspeedAvg": me.get("windspeedAvg"),
            "humidityAvg": float(hum) if hum is not None else None,
        }
        added += 1
    if not added:
        sys.exit(f"Za {ym} ni uporabnih dni v odgovoru workerja.")

    out = {k: hist[k] for k in sorted(hist)}
    json.dump(out, open(hp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"✓ history.json: posodobljenih {added} dni za {ym} (skupaj {len(out)} dni)")

if __name__ == "__main__":
    main()
