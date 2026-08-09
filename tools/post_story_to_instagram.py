#!/usr/bin/env python3
"""
tools/post_story_to_instagram.py — objavi dnevno kartico kot zgodbo na Instagramu.

Instagram objavi zgodbo po istem dvostopenjskem postopku kot navadno objavo,
le da ima container media_type=STORIES:
  1. POST /{ig-user-id}/media?image_url=...&media_type=STORIES -> creation_id
  2. (počakaj, da je container FINISHED)
  3. POST /{ig-user-id}/media_publish?creation_id=...          -> zgodba je objavljena

Zgodbe nimajo podpisa -- vse je na sami sliki (glej generate_story_card.py).

Rabi okoljski spremenljivki IG_ACCOUNT_ID in IG_ACCESS_TOKEN (GitHub secreta),
enaka kot tools/post_to_instagram.py.

Wired into: .github/workflows/daily-story.yml

Usage:
  python3 tools/post_story_to_instagram.py [image_url]
  (brez argumenta: URL prebere iz og/story/latest.json)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATEST = os.path.join(ROOT, "og", "story", "latest.json")
GRAPH = "https://graph.instagram.com/v21.0"

# Koliko časa čakamo, da Instagram obdela sliko v containerju.
POLL_TRIES = 12
POLL_WAIT = 5


def api_post(path, token, **params):
    payload = urllib.parse.urlencode({**params, "access_token": token}).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def api_get(path, token, **params):
    qs = urllib.parse.urlencode({**params, "access_token": token})
    req = urllib.request.Request(f"{GRAPH}/{path}?{qs}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def wait_ready(creation_id, token):
    """Počaka, da gre container iz IN_PROGRESS v FINISHED.

    Objava neobdelanega containerja vrne napako, zato ne objavljamo na slepo.
    """
    for _ in range(POLL_TRIES):
        try:
            st = api_get(creation_id, token, fields="status_code").get("status_code")
        except urllib.error.HTTPError:
            st = None
        if st == "FINISHED":
            return True
        if st == "ERROR":
            return False
        time.sleep(POLL_WAIT)
    return False


def main():
    account_id = os.environ.get("IG_ACCOUNT_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not account_id or not token:
        print("IG_ACCOUNT_ID / IG_ACCESS_TOKEN nista nastavljena — preskačem zgodbo na Instagramu.",
              file=sys.stderr)
        return 0

    if len(sys.argv) > 1:
        image_url = sys.argv[1]
    else:
        with open(LATEST, encoding="utf-8") as f:
            image_url = json.load(f)["image"]
        # Glej enak komentar v post_story_to_facebook.py: Cloudflare zna 404,
        # ujet med GitHub Pages deployem, predpomniti za skoraj eno leto, zato
        # Instagramov pobiralec slike dobi svež query-string, ne gol URL.
        image_url += ("&" if "?" in image_url else "?") + f"cb={int(time.time())}"

    try:
        container = api_post(f"{account_id}/media", token,
                             image_url=image_url, media_type="STORIES")
        creation_id = container.get("id")
        if not creation_id:
            print(f"Instagram: container ni vrnil id-ja ({container}).", file=sys.stderr)
            return 1
        if not wait_ready(creation_id, token):
            print("Instagram: container ni bil pravočasno obdelan — zgodba ni objavljena.",
                  file=sys.stderr)
            return 1
        result = api_post(f"{account_id}/media_publish", token, creation_id=creation_id)
        print(f"Instagram zgodba: objavljeno — {result}")
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:600]
        print(f"Instagram zgodba, napaka {e.code}: {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Instagram zgodba, napaka: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
