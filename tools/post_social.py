#!/usr/bin/env python3
"""
tools/post_social.py — objavi poljubno sliko + besedilo na FB stran in IG
račun Meteorec.

Za razliko od tools/post_to_facebook.py in tools/post_to_instagram.py, ki
objavita članek iz blog.json (slug -> OG slika -> povezava), je ta skript
splošen: dobi URL slike in besedilo. Namenjen je samostojnim dnevnim
objavam, ki niso članek — prva je dnevno dejstvo
(tools/daily_fact_social.py), po istem tiru pa lahko kasneje tečejo še
pragovi/rekordi, gobarski indeks, nevihtna napoved …

Slika mora biti javno dostopna PREDEN se skript zažene — tako FB kot IG jo
prenašata po URL-ju s svojih strežnikov. V workflowu zato med generiranjem
kartice in objavo stojita `git push` na main in `wait_for_deploy.py --url`.

Rabi GitHub secrete FB_PAGE_ID/FB_PAGE_TOKEN in IG_ACCOUNT_ID/IG_ACCESS_TOKEN.
Če par manjka, se tisto omrežje tiho preskoči (izhodna koda 0).

Usage:
  python3 tools/post_social.py --image-url URL --text-file pot/do/besedila.txt \
      [--link https://meteorec.si/] [--only fb|ig]
  python3 tools/post_social.py --image-url URL --text "besedilo objave"
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FB_GRAPH = "https://graph.facebook.com/v21.0"
IG_GRAPH = "https://graph.instagram.com/v21.0"


def api_post(base, path, **params):
    payload = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{base}/{path}", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def err_body(e):
    return e.read().decode("utf-8", "replace")[:500]


def post_facebook(image_url, text, link):
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not page_id or not token:
        print("FB_PAGE_ID / FB_PAGE_TOKEN nista nastavljena — preskačem Facebook.", file=sys.stderr)
        return None

    try:
        res = api_post(FB_GRAPH, f"{page_id}/photos", url=image_url,
                       caption=text, access_token=token)
        print(f"Facebook: objavljeno — {res}")
        return True
    except urllib.error.HTTPError as e:
        print(f"Facebook /photos napaka {e.code}: {err_body(e)}", file=sys.stderr)

    # Fallback na navadno objavo — brez slike, a objava vseeno gre ven.
    try:
        params = {"message": text, "access_token": token}
        if link:
            params["link"] = link
        res = api_post(FB_GRAPH, f"{page_id}/feed", **params)
        print(f"Facebook: objavljeno brez slike — {res}")
        return True
    except urllib.error.HTTPError as e:
        print(f"Facebook /feed napaka {e.code}: {err_body(e)}", file=sys.stderr)
        return False


def post_instagram(image_url, text):
    account_id = os.environ.get("IG_ACCOUNT_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not account_id or not token:
        print("IG_ACCOUNT_ID / IG_ACCESS_TOKEN nista nastavljena — preskačem Instagram.", file=sys.stderr)
        return None

    try:
        container = api_post(IG_GRAPH, f"{account_id}/media", image_url=image_url,
                             caption=text, access_token=token)
        time.sleep(3)  # IG včasih rabi trenutek, da container obdela sliko
        res = api_post(IG_GRAPH, f"{account_id}/media_publish",
                       creation_id=container["id"], access_token=token)
        print(f"Instagram: objavljeno — {res}")
        return True
    except urllib.error.HTTPError as e:
        print(f"Instagram napaka {e.code}: {err_body(e)}", file=sys.stderr)
        return False
    except (KeyError, ValueError) as e:
        print(f"Instagram: nepričakovan odgovor — {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-url", required=True)
    ap.add_argument("--text")
    ap.add_argument("--text-file")
    ap.add_argument("--link", default="")
    ap.add_argument("--only", choices=("fb", "ig"))
    args = ap.parse_args()

    if args.text_file:
        text = open(args.text_file, encoding="utf-8").read().strip()
    elif args.text:
        text = args.text
    else:
        print("Manjka --text ali --text-file.", file=sys.stderr)
        return 2

    results = []
    if args.only != "ig":
        results.append(post_facebook(args.image_url, text, args.link))
    if args.only != "fb":
        # IG v podpisu ne odpre povezav — zato v besedilu stoji "povezava v bio".
        results.append(post_instagram(args.image_url, text))

    attempted = [r for r in results if r is not None]
    if attempted and not any(attempted):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
