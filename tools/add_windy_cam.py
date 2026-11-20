#!/usr/bin/env python3
"""tools/add_windy_cam.py — vnos kamer Windy v data/snegofili-tocke.json iz kode za vdelavo z https://embed.windy.com/config/webcam.

Windy ponuja dve obliki; obe sta podprti (skripta player.js se NE izvaja, iz podatkov se sestavi iframe):
  1) <a name="windy-webcam-timelapse-player" data-id="1385535601" data-play="day" href="https://www.windy.com/webcams/...">Kredarica</a>
     → iframe https://webcams.windy.com/webcams/public/embed/player/<id>/<play> (day = časovni zdrs zadnjega dne, NI tok v živo)
  2) <iframe src="https://webcams.windy.com/...">
Uporaba (en vnos):  python3 tools/add_windy_cam.py <id točke> '<koda>' [--cam-id ID] [--naslov "..."] [--svet]
--svet: točka je s seznama »Po svetu« (data/snegofili-svet-tocke.json), npr. niseko, hakuba, whistler.
Z več sidri v kodi izberi --cam-id. Skript preveri https in dovoljenega gostitelja (kot valid_embed() v generatorju), zapiše embed_kind=windy,
embed_terms (pogoji Windy), checked = današnji datum in ponudnika Windy. Z datumom potrjuješ, da si pogoje uporabe Windy pogledal ti.
Brez omrežja. Navedba »Webcams provided by windy.com« je v lightboxu obvezna.
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
PATH_SVET = os.path.join(ROOT, "data", "snegofili-svet-tocke.json")  # rubrika »Po svetu« (--svet)
HOSTS = ("webcams.windy.com", "embed.windy.com")
TERMS = "https://api.windy.com/webcams/terms"
PLAYER = "https://webcams.windy.com/webcams/public/embed/player/{id}/{play}"


def parse(code):
    """Vrne seznam {id, play, naslov, src}; prazno, če oblike ne prepozna."""
    out = []
    for m in re.finditer(r"<a\b([^>]*windy-webcam[^>]*)>(.*?)</a>", code, re.S | re.I):
        attrs = dict(re.findall(r'([\w-]+)\s*=\s*"([^"]*)"', m.group(1)))
        cid, play = attrs.get("data-id", ""), attrs.get("data-play", "day")
        if re.fullmatch(r"\d{4,15}", cid) and re.fullmatch(r"[a-z]{3,12}", play):
            out.append({"id": cid, "play": play, "naslov": html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip(),
                        "src": PLAYER.format(id=cid, play=play), "url": f"https://www.windy.com/webcams/{cid}"})
    if not out:
        m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', code)
        src = html.unescape(m.group(1) if m else code.strip())
        out.append({"id": "", "play": "", "naslov": "", "src": src, "url": "https://www.windy.com/webcams"})
    return out


def add(data, tocka, cam, naslov=None, today=None):
    """Doda ali zamenja kamero v točki. Vrne ime točke; ValueError ob neveljavnem vnosu."""
    u = urlparse(cam["src"])
    if u.scheme != "https" or u.hostname not in HOSTS:
        raise ValueError(f"src mora biti https na enem od: {', '.join(HOSTS)} (dobil: {cam['src'][:80]})")
    p = next((x for x in data["tocke"] if x["id"] == tocka), None)
    if not p:
        raise ValueError(f"točke »{tocka}« ni")
    cams = [c for c in p.get("kamere") or [] if c.get("embed") != cam["src"]]
    cams.append({"naslov": naslov or cam.get("naslov") or f"Kamera {p['ime']}", "url": cam["url"], "ponudnik": "Windy",
                 "embed_kind": "windy", "embed": cam["src"], "embed_terms": TERMS,
                 "checked": today or datetime.date.today().isoformat()})
    p["kamere"] = cams
    return p["ime"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tocka")
    ap.add_argument("koda")
    ap.add_argument("--cam-id", default=None)
    ap.add_argument("--naslov", default=None)
    ap.add_argument("--svet", action="store_true", help="točka je iz rubrike »Po svetu«")
    a = ap.parse_args()
    cams = parse(a.koda)
    if a.cam_id:
        cams = [c for c in cams if c["id"] == a.cam_id]
    if len(cams) != 1:
        print(f"✗ v kodi je {len(cams)} kamer; izberi eno z --cam-id (id-ji: {', '.join(c['id'] for c in parse(a.koda))})", file=sys.stderr)
        return 1
    path = PATH_SVET if a.svet else PATH
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    try:
        ime = add(data, a.tocka, cams[0], a.naslov)
    except ValueError as e:
        print(f"✗ {e}; veljavne točke: {', '.join(x['id'] for x in data['tocke'])}" if "ni" in str(e) and "točke" in str(e) else f"✗ {e}", file=sys.stderr)
        return 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"✓ {ime}: dodana kamera Windy ({cams[0]['naslov'] or cams[0]['src'][:50]}). Poženi: python3 tools/generate_snegofili_page.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
