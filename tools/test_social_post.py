#!/usr/bin/env python3
"""
tools/test_social_post.py — preverja objavljanje na FB/IG (brez omrežja).

  * new_slugs: samo novi slugi s predpono (napaka: vsak ponedeljek se je
    ponovno objavilo zadnjih 5 invazivka-člankov);
  * UTM na Facebook linku in v preusmeritvi kratke povezave (canonical čist);
  * already_posted: zazna isti link/besedilo v zadnjih dneh, ob napaki API-ja
    ne blokira objave;
  * main: link objava je privzeta, FB_FORCE preskoči preverjanje dvojnika.

Teče: python3 tools/test_social_post.py
"""
import datetime
import io
import json
import os
import sys
import tempfile
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import new_slugs as ns  # noqa: E402
import post_to_facebook as fb  # noqa: E402
import short_links  # noqa: E402

FAILS = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


# ── new_slugs ────────────────────────────────────────────────────────────────
with tempfile.TemporaryDirectory() as d:
    before = os.path.join(d, "before.json")
    after = os.path.join(d, "after.json")
    json.dump([{"slug": "invazivka-a"}, {"slug": "drugo"}], open(before, "w"))
    json.dump([{"slug": "invazivka-c"}, {"slug": "drugo-2"}, {"slug": "invazivka-a"},
               {"slug": "drugo"}], open(after, "w"))
    check("new_slugs: samo novi s predpono",
          ns.new_slugs(before, after, "invazivka") == ["invazivka-c"])
    check("new_slugs: brez predpone vsi novi",
          ns.new_slugs(before, after, "") == ["invazivka-c", "drugo-2"])
    check("new_slugs: manjkajoč posnetek = vsi novi",
          ns.new_slugs(os.path.join(d, "ni.json"), after, "invazivka")
          == ["invazivka-c", "invazivka-a"])
    check("new_slugs: omejitev", len(ns.new_slugs(before, after, "", limit=1)) == 1)

# ── UTM ──────────────────────────────────────────────────────────────────────
u = fb.with_utm("https://meteorec.si/blog/x.html", "invazivka-foo")
check("utm: vir facebook", "utm_source=facebook" in u and "utm_medium=social" in u)
check("utm: kampanja po tipu", "utm_campaign=invazivke" in u)
check("utm: privzeta kampanja", "utm_campaign=clanek" in fb.with_utm("https://x/y", "dnevni-123"))
check("utm: obstoječ query", fb.with_utm("https://x/y?a=1", "s").startswith("https://x/y?a=1&utm_"))

html = short_links._redirect_html("slug", "https://meteorec.si/blog/x.html")
check("kratka povezava: canonical brez UTM",
      '<link rel="canonical" href="https://meteorec.si/blog/x.html">' in html)
check("kratka povezava: preusmeritev z UTM instagram",
      "utm_source=instagram" in html and "utm_medium=social" in html)
check("kratka povezava: & v atributu je escapiran", "&amp;utm_medium=social" in html)

# ── already_posted ───────────────────────────────────────────────────────────
NOW = datetime.datetime.now(datetime.timezone.utc)


def iso(days_ago):
    return (NOW - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(items=None, error=None):
    def _open(req, timeout=0):
        if error:
            raise error
        return Resp(json.dumps({"data": items}).encode())
    return _open


URL = "https://meteorec.si/blog/x.html"
MSG = "Naslov članka\n\nPovzetek"
orig = fb.urllib.request.urlopen

fb.urllib.request.urlopen = fake_urlopen([{"created_time": iso(0.2), "link": URL + "?utm_source=facebook"}])
check("dvojnik: isti link", fb.already_posted("1", "t", URL, MSG) is True)
fb.urllib.request.urlopen = fake_urlopen([{"created_time": iso(0.2), "message": "Naslov članka\n\nDrugo"}])
check("dvojnik: isti naslov", fb.already_posted("1", "t", URL, MSG) is True)
fb.urllib.request.urlopen = fake_urlopen([{"created_time": iso(10), "link": URL}])
check("dvojnik: star zapis ne šteje", fb.already_posted("1", "t", URL, MSG) is False)
fb.urllib.request.urlopen = fake_urlopen([{"created_time": iso(0.2), "link": "https://meteorec.si/blog/drug.html",
                                           "message": "Nekaj drugega"}])
check("dvojnik: drug članek ne blokira", fb.already_posted("1", "t", URL, MSG) is False)
fb.urllib.request.urlopen = fake_urlopen(error=urllib.error.URLError("403"))
check("dvojnik: napaka API-ja ne blokira objave", fb.already_posted("1", "t", URL, MSG) is False)
fb.urllib.request.urlopen = orig

# ── main: način objave ───────────────────────────────────────────────────────
calls = []


def run_main(env, already=False):
    calls.clear()
    keep = {k: os.environ.get(k) for k in ("FB_PAGE_ID", "FB_PAGE_TOKEN", "FB_FORCE", "FB_POST_MODE")}
    for k in keep:
        os.environ.pop(k, None)
    os.environ.update({"FB_PAGE_ID": "1", "FB_PAGE_TOKEN": "t", **env})
    fb.already_posted = lambda *a, **k: already
    fb.post_link_only = lambda page, tok, msg, url: calls.append(("link", url)) or "{}"
    fb.post_with_photo = lambda page, tok, post, msg: calls.append(("photo", None)) or "pid"
    fb.post_link_comment = lambda pid, tok, url: calls.append(("comment", url))
    argv = sys.argv
    sys.argv = ["x", json.load(open(fb.BLOG_JSON, encoding="utf-8"))[0]["slug"]]
    try:
        fb.main()
    finally:
        sys.argv = argv
        for k, v in keep.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    return list(calls)


c = run_main({})
check("main: privzeto link objava z UTM", len(c) == 1 and c[0][0] == "link" and "utm_source=facebook" in c[0][1])
c = run_main({"FB_POST_MODE": "photo"})
check("main: način photo = slika + komentar", [x[0] for x in c] == ["photo", "comment"])
c = run_main({}, already=True)
check("main: dvojnik se preskoči", c == [])
c = run_main({"FB_FORCE": "1"}, already=True)
check("main: FB_FORCE preskoči preverjanje", len(c) == 1 and c[0][0] == "link")

print(f"\n{len(FAILS)} napak" if FAILS else "\nvse OK")
sys.exit(1 if FAILS else 0)
