#!/usr/bin/env python3
"""
tools/post_precip_map_to_facebook.py — objavi dnevno padavinsko karto
Slovenije (feed slika) na Facebook strani.

Ločen od tools/post_to_facebook.py, ker ta pričakuje zapis iz blog.json
(slug, title, url) — karta ni blog članek, samo dnevna slika z lastnim
podpisom, prebrana iz og/precip-map/latest.json. Isti vzorec kot
tools/post_storm_map_to_facebook.py.

Objavi se samo, če je latest.json.should_post True (glej
tools/generate_precip_map.py — pod OBILNO se objava tiho preskoči, da ne gre
vsak dan ven "povsod po malem" post).

Link do /padavine-karta/ NI v besedilu objave (manjši organski doseg z
linkom v telesu, isto načelo kot ostale FB objave) — gre kot prvi komentar.

Rabi okoljski spremenljivki FB_PAGE_ID in FB_PAGE_TOKEN (isti secreta kot
ostale FB objave).

Wired into: .github/workflows/precip-map.yml

Usage:
  python3 tools/post_precip_map_to_facebook.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATEST = os.path.join(ROOT, "og", "precip-map", "latest.json")
SITE = "https://meteorec.si"
GRAPH = "https://graph.facebook.com/v21.0"


def build_message(meta):
    return (f"🌧️ Padavine v zadnjih 24 urah — največ v {meta['top_station']}\n\n"
            f"Na tej postaji ARSO je v zadnjih 24 urah padlo {round(meta['top_mm'])} mm dežja. "
            f"Karta prikazuje izmerjene (ne napovedane) padavine na {meta['n_stations']} samodejnih "
            f"postajah ARSO po vsej Sloveniji.")


def main():
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not page_id or not token:
        print("FB_PAGE_ID / FB_PAGE_TOKEN nista nastavljena — preskačem objavo na Facebook.", file=sys.stderr)
        return 0

    meta = json.load(open(LATEST, encoding="utf-8"))
    if not meta.get("should_post"):
        print(f"Največ dežja danes je {round(meta.get('top_mm', 0))} mm — objava se preskoči.")
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
                    "message": f"Vsi podatki: {SITE}/padavine-karta/",
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
