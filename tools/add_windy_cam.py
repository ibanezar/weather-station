#!/usr/bin/env python3
"""tools/add_windy_cam.py — vnos kamere Windy v data/snegofili-tocke.json iz kode iframe z https://embed.windy.com/config/webcam.

Kako: na strani config/webcam izberi kamero, kopiraj kodo za vdelavo (iframe) in jo daj temu skriptu:
  python3 tools/add_windy_cam.py <id točke> '<iframe ... src="https://webcams.windy.com/...">'  [--naslov "Kamera Kitzbühel"]
Skript vzame samo src, preveri https in dovoljenega gostitelja (kot valid_embed() v generatorju), zapiše embed_kind=windy,
embed_terms (pogoji Windy), checked = današnji datum in ponudnika »Windy«. Brez omrežja. Navedba »Webcams provided by windy.com«
je v generatorju že obvezna. Z datumom potrjuješ, da si pogoje uporabe Windy pogledal ti.
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "snegofili-tocke.json")
HOSTS = ("webcams.windy.com", "embed.windy.com")
TERMS = "https://api.windy.com/webcams/terms"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tocka")
    ap.add_argument("iframe", help="koda iframe ali kar URL")
    ap.add_argument("--naslov", default=None)
    a = ap.parse_args()
    m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', a.iframe)
    src = html.unescape(m.group(1) if m else a.iframe.strip())
    u = urlparse(src)
    if u.scheme != "https" or u.hostname not in HOSTS:
        print(f"✗ src mora biti https na enem od: {', '.join(HOSTS)} (dobil: {src[:80]})", file=sys.stderr)
        return 1
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)
    p = next((x for x in data["tocke"] if x["id"] == a.tocka), None)
    if not p:
        print(f"✗ točke »{a.tocka}« ni; veljavne: {', '.join(x['id'] for x in data['tocke'])}", file=sys.stderr)
        return 1
    cams = [c for c in p.get("kamere") or [] if c.get("embed") != src]
    cams.append({"naslov": a.naslov or f"Kamera {p['ime']}", "url": "https://www.windy.com/webcams", "ponudnik": "Windy",
                 "embed_kind": "windy", "embed": src, "embed_terms": TERMS, "checked": datetime.date.today().isoformat()})
    p["kamere"] = cams
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"✓ {p['ime']}: dodana kamera Windy ({u.hostname}). Poženi: python3 tools/generate_snegofili_page.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
