#!/usr/bin/env python3
"""tools/check_snegofili_cams.py — ali imena `arso_cam` v data/snegofili-tocke.json obstajajo v seznamu kamer ARSO.

Worker `/arso-cam` za neznano kamero vrne 404 z `nakamere` (seznam imen). Skript izpiše razliko v povzetek teka;
izhod je vedno 0 (informativen korak, ne sme podreti objave).
Usage: python3 tools/check_snegofili_cams.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
WORKER_UA = "Mozilla/5.0 (compatible; Meteorec-Snegofili/1.0)"


def main():
    with open(os.path.join(ROOT, "data", "snegofili-tocke.json"), encoding="utf-8") as f:
        pts = json.load(f)["tocke"]
    wanted = sorted({p["arso_cam"] for p in pts if p.get("arso_cam")})
    url = PROXY + "/arso-cam?kamera=" + urllib.parse.quote("__ni-take-kamere__")
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": WORKER_UA}), timeout=30)
        print("✗ nepričakovan odgovor workerja (ni 404)")
        return 0
    except urllib.error.HTTPError as e:
        try:
            names = json.loads(e.read().decode("utf-8")).get("nakamere") or []
        except (ValueError, OSError):
            names = []
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"✗ worker nedosegljiv: {e}")
        return 0
    if not names:
        print("✗ seznam kamer ARSO je prazen ali ga ni bilo mogoče prebrati")
        return 0
    low = {n.lower(): n for n in names}
    for w in wanted:
        print(("✓ " if w.lower() in low else "✗ NI V SEZNAMU ") + w)
    print("Kamere ARSO (" + str(len(names)) + "): " + ", ".join(sorted(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
