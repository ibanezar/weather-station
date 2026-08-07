#!/usr/bin/env python3
"""
tools/post_story_to_facebook.py — objavi dnevno kartico kot zgodbo na FB strani.

Facebook objavi slikovno zgodbo v dveh korakih:
  1. POST /{page-id}/photos?url=...&published=false  -> photo_id (neobjavljena slika)
  2. POST /{page-id}/photo_stories?photo_id=...      -> zgodba je objavljena

Zgodbe nimajo besedila/podpisa -- vse, kar naj bralec vidi, mora biti na sami
sliki (glej tools/generate_story_card.py).

Rabi okoljski spremenljivki FB_PAGE_ID in FB_PAGE_TOKEN (GitHub secreta),
enaka kot tools/post_to_facebook.py.

Wired into: .github/workflows/daily-story.yml

Usage:
  python3 tools/post_story_to_facebook.py [image_url]
  (brez argumenta: URL prebere iz og/story/latest.json)
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATEST = os.path.join(ROOT, "og", "story", "latest.json")
GRAPH = "https://graph.facebook.com/v21.0"


def api_post(path, token, **params):
    payload = urllib.parse.urlencode({**params, "access_token": token}).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def main():
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not page_id or not token:
        print("FB_PAGE_ID / FB_PAGE_TOKEN nista nastavljena — preskačem zgodbo na Facebooku.",
              file=sys.stderr)
        return 0

    if len(sys.argv) > 1:
        image_url = sys.argv[1]
    else:
        with open(LATEST, encoding="utf-8") as f:
            image_url = json.load(f)["image"]

    try:
        # 1) naloži sliko, a je ne objavi v feed -- služi samo kot vir za zgodbo
        photo = api_post(f"{page_id}/photos", token, url=image_url, published="false")
        photo_id = photo.get("id")
        if not photo_id:
            print(f"Facebook: nalaganje slike ni vrnilo id-ja ({photo}).", file=sys.stderr)
            return 1
        # 2) objavi zgodbo
        result = api_post(f"{page_id}/photo_stories", token, photo_id=photo_id)
        print(f"Facebook zgodba: objavljeno — {result}")
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:600]
        print(f"Facebook zgodba, napaka {e.code}: {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Facebook zgodba, napaka: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
