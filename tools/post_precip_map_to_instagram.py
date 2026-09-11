#!/usr/bin/env python3
"""
tools/post_precip_map_to_instagram.py — objavi dnevno padavinsko karto
Slovenije (feed slika) na Instagramu.

Glej tools/post_precip_map_to_facebook.py za razlog, zakaj je ta ločena od
tools/post_to_instagram.py (karta ni blog članek). Isti pogoj should_post iz
og/precip-map/latest.json velja tudi tu.

Instagram povezave nikjer ne naredi klikabilne (glej tools/post_to_instagram.py),
zato gre v komentar polni URL — kratkih povezav (tools/short_links.py) tu ni,
ker karta ni članek iz blog.json.

Rabi okoljski spremenljivki IG_ACCOUNT_ID in IG_ACCESS_TOKEN (isti secreta
kot ostale IG objave).

Wired into: .github/workflows/precip-map.yml

Usage:
  python3 tools/post_precip_map_to_instagram.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATEST = os.path.join(ROOT, "og", "precip-map", "latest.json")
SITE = "https://meteorec.si"
GRAPH = "https://graph.instagram.com/v21.0"


def build_caption(meta):
    return (f"🌧️ Padavine v zadnjih 24 urah — največ v {meta['top_station']}\n\n"
            f"Na tej postaji ARSO je v zadnjih 24 urah padlo {round(meta['top_mm'])} mm dežja. "
            f"Karta prikazuje izmerjene (ne napovedane) padavine na {meta['n_stations']} samodejnih "
            "postajah ARSO po vsej Sloveniji.\n\n"
            "Vsi podatki: povezava je v prvem komentarju.\n\n"
            "#meteorec #vreme #padavine #slovenija")


def api_post(path, token, **params):
    payload = urllib.parse.urlencode({**params, "access_token": token}).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    account_id = os.environ.get("IG_ACCOUNT_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not account_id or not token:
        print("IG_ACCOUNT_ID / IG_ACCESS_TOKEN nista nastavljena — preskačem objavo na Instagram.", file=sys.stderr)
        return 0

    meta = json.load(open(LATEST, encoding="utf-8"))
    if not meta.get("should_post"):
        print(f"Največ dežja danes je {round(meta.get('top_mm', 0))} mm — objava se preskoči.")
        return 0

    caption = build_caption(meta)
    try:
        container = api_post(f"{account_id}/media", token, image_url=meta["image"], caption=caption)
        creation_id = container["id"]
        time.sleep(3)
        result = api_post(f"{account_id}/media_publish", token, creation_id=creation_id)
        print(f"Instagram: karta objavljena — {result}")
        media_id = result["id"]
        try:
            api_post(f"{media_id}/comments", token,
                     message=f"Vsi podatki: {SITE}/padavine-karta/\n"
                             "(Instagram povezav ne naredi klikabilnih — prepiši jo v brskalnik.)")
            print("Instagram: link dodan kot prvi komentar.")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            print(f"Instagram: dodajanje linka v komentar spodletelo ({e.code}: {body}).", file=sys.stderr)
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"Instagram napaka {e.code}: {body}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
