#!/usr/bin/env python3
"""tools/fetch_snegofili_photos.py — ROČNO orodje: prenese proste fotografije z Wikimedia Commons za /snegofili/.

  python3 tools/fetch_snegofili_photos.py --out snegofili/img --width 2000 "File:Ime datoteke.jpg" ...

Sprejme samo licence, ki dovoljujejo objavo (CC0, javna domena, CC BY, CC BY-SA), zmanjša sliko (brez EXIF) in zapiše
avtorja, licenco in povezavo do vira v `<out>/credits.json` (obvezna navedba ob sliki na strani).
Wikimedia omejuje hitrost (HTTP 429 z Retry-After): skript počaka, kolikor zahtevajo, in med slikami drži razmik.
Odjemalec se predstavi z imenom in javnim naslovom strani (brez osebnih podatkov).
"""
import argparse, html, io, json, os, re, sys, time, urllib.parse, urllib.request
from PIL import Image

UA = "MeteorecPhotoFetch/1.0 (https://meteorec.si/; weather site, license-compliant image use)"
API = "https://commons.wikimedia.org/w/api.php"
OK_LIC = re.compile(r"^(CC0|Public domain|CC BY(-SA)?\b)", re.I)


def get(url, tries=8):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = min(900, int(e.headers.get("Retry-After") or 60 * (k + 1)) + 5)
            print(f"  429, čakam {wait} s", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise SystemExit("še vedno 429")


def info(titles):
    p = dict(action="query", format="json", titles="|".join(titles), prop="imageinfo", iiprop="url|size|extmetadata",
             iiextmetadatafilter="LicenseShortName|Artist|LicenseUrl")
    d = json.loads(get(API + "?" + urllib.parse.urlencode(p)))
    out = {}
    for pg in d["query"]["pages"].values():
        ii = (pg.get("imageinfo") or [None])[0]
        if not ii:
            print("ni slike:", pg.get("title"), file=sys.stderr)
            continue
        md = ii["extmetadata"]
        out[pg["title"]] = dict(
            licenca=md["LicenseShortName"]["value"], licenca_url=md.get("LicenseUrl", {}).get("value", ""),
            avtor=html.unescape(re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", ""))).strip(),
            stran=ii["descriptionurl"], url=ii["url"], w=ii["width"], h=ii["height"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("titles", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=2000)
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--gap", type=int, default=25, help="razmik med prenosi (s)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cpath = os.path.join(a.out, "credits.json")
    credits = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
    meta = info([t if t.startswith("File:") else "File:" + t for t in a.titles])
    for i, (title, m) in enumerate(meta.items()):
        if not OK_LIC.match(m["licenca"]):
            print("preskočeno (licenca):", title, m["licenca"]); continue
        slug = re.sub(r"[^a-z0-9]+", "-", title[5:].rsplit(".", 1)[0].lower()).strip("-")[:60]
        if os.path.exists(os.path.join(a.out, slug + ".jpg")):
            print("že je:", slug); continue
        if i:
            time.sleep(a.gap)
        print("prenašam", title, m["licenca"], f'{m["w"]}x{m["h"]}', flush=True)
        im = Image.open(io.BytesIO(get(m["url"]))).convert("RGB")
        if im.width > a.width:
            im = im.resize((a.width, round(im.height * a.width / im.width)), Image.LANCZOS)
        im.save(os.path.join(a.out, slug + ".jpg"), "JPEG", quality=a.quality, optimize=True, progressive=True)
        credits[slug] = {k: m[k] for k in ("avtor", "licenca", "licenca_url", "stran")} | {"naslov": title[5:], "w": im.width, "h": im.height}
        json.dump(credits, open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  →", slug, f"{im.width}x{im.height}", flush=True)


if __name__ == "__main__":
    main()
