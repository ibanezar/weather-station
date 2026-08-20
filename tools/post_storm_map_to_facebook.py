#!/usr/bin/env python3
"""
tools/post_storm_map_to_facebook.py — objavi dnevno nevihtno karto Slovenije
(feed slika) na Facebook strani.

Ločen od tools/post_to_facebook.py, ker ta pričakuje zapis iz blog.json
(slug, title, url) — karta ni blog članek, samo dnevna slika z lastnim
podpisom, prebrana iz og/storm-map/latest.json.

Objavi se samo, če je latest.json.should_post True (glej
tools/generate_storm_map.py — pod ZMERNO se objava tiho preskoči, da ne gre
vsak dan ven prazen "brez neviht" post).

Link do /nevihte/ NI v besedilu objave, ker naj bi objave z linkom v telesu
dosegle manjši organski doseg (isto načelo kot tools/post_to_facebook.py) —
gre kot prvi komentar.

Rabi okoljski spremenljivki FB_PAGE_ID in FB_PAGE_TOKEN (isti secreta kot
ostale FB objave).

Wired into: .github/workflows/storm-map.yml

Usage:
  python3 tools/post_storm_map_to_facebook.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATEST = os.path.join(ROOT, "og", "storm-map", "latest.json")
SITE = "https://meteorec.si"
GRAPH = "https://graph.facebook.com/v21.0"


def build_message(meta):
    return (f"⛈️ Nevihtna karta Slovenije — danes {meta['national_level'].lower()}\n\n"
            f"Najvišji nevihtni potencial danes je pričakovan bliže "
            f"{meta['national_place']}. Karta prikazuje oceno po vsej Sloveniji, "
            f"izračunano iz podatkov Open-Meteo — ni uradno opozorilo ARSO.")


def main():
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not page_id or not token:
        print("FB_PAGE_ID / FB_PAGE_TOKEN nista nastavljena — preskačem objavo na Facebook.", file=sys.stderr)
        return 0

    meta = json.load(open(LATEST, encoding="utf-8"))
    if not meta.get("should_post"):
        print(f"Nevihtni potencial danes je {meta.get('national_level')} — objava se preskoči.")
        return 0

    message = build_message(meta)
    payload = urllib.parse.urlencode({
        "url": meta["image"], "caption": message, "access_token": token,
    }).encode()
    try:
        req = urllib.request.Request(f"{GRAPH}/{page_id}/photos", data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        post_id = data.get("post_id") or data.get("id")
        print(f"Facebook: karta objavljena — post_id={post_id}")
        if post_id:
            try:
                comment = urllib.parse.urlencode({
                    "message": f"Vsi indeksi in podrobnosti: {SITE}/nevihte/",
                    "access_token": token,
                }).encode()
                req2 = urllib.request.Request(f"{GRAPH}/{post_id}/comments", data=comment, method="POST")
                with urllib.request.urlopen(req2, timeout=15):
                    pass
                print("Facebook: link dodan kot prvi komentar.")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                print(f"Facebook: dodajanje linka v komentar spodletelo ({e.code}: {body}).", file=sys.stderr)
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"Facebook napaka {e.code}: {body}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
