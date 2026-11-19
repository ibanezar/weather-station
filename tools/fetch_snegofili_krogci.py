#!/usr/bin/env python3
"""tools/fetch_snegofili_krogci.py — ROČNO orodje: mala krožna fotografija kraja za vsako točko Snegofilov (Wikimedia Commons).

Za vsako točko iz data/snegofili-tocke.json poišče prosto fotografijo (CC0, javna domena, CC BY, CC BY-SA), vzame sličico 250 px,
izreže kvadrat 128 px in jo zapiše v snegofili/img/kraji/<id>.jpg; avtor, licenca in povezava so v snegofili/img/kraji/credits.json
(navedba je obvezna in se izpiše na strani). Že narejene točke preskoči. Wikimedia vrača 429 z Retry-After: skript počaka.
`OVERRIDE` (id → naslov datoteke) ima prednost pred iskanjem: tam popravi napačen zadetek (pregled: --sheet kontaktni list).

  python3 tools/fetch_snegofili_krogci.py [--gap 8] [--only id1,id2] [--sheet POT.jpg]
"""
import argparse, html, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "snegofili", "img", "kraji")
UA = "MeteorecPhotoFetch/1.0 (https://meteorec.si/; weather site, license-compliant image use)"
API = "https://commons.wikimedia.org/w/api.php"
OK_LIC = re.compile(r"^(CC0|Public domain|CC BY(-SA)?\b)", re.I)
BAD = re.compile(r"map|karte|logo|panorama_of|diagram|coat|wappen|flag|poster|plan|schema|skimap|piste|brochure", re.I)
# iskalni niz po točki (privzeto: ime + drzava); popravi, če je zadetek neustrezen
QUERY = {"crnivec": "Črnivec prelaz", "pokljuka": "Pokljuka planota", "vrsic": "Vršič prelaz", "dachstein": "Dachstein Hallstätter Gletscher",
         "kronplatz": "Kronplatz Plan de Corones", "pordoi": "Passo Pordoi", "dobratsch": "Dobratsch Villacher Alpe", "st-anton": "St. Anton am Arlberg",
         "st-christoph": "St. Christoph am Arlberg", "canazei": "Canazei Val di Fassa", "val-gardena": "Ortisei Val Gardena",
         "alta-badia": "Corvara Alta Badia", "marmolada-fedaia": "Marmolada", "cervinia": "Breuil-Cervinia", "pavlicevo-sedlo": "Pavličevo sedlo",
         "urslja-gora": "Uršlja gora", "menina-planina": "Menina planina", "logarska-dolina": "Logarska dolina", "velika-planina": "Velika planina",
         "kranjska-gora": "Kranjska Gora", "aiguille-du-midi": "Aiguille du Midi", "sljeme": "Sljeme Medvednica", "platak": "Platak Risnjak"}
OVERRIDE = {}  # id -> "File:....jpg"


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()).strip()


def get(url, tries=10):
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


def api(**p):
    p["format"] = "json"
    return json.loads(get(API + "?" + urllib.parse.urlencode(p)))


def pick(point):
    pid, name = point["id"], point["ime"]
    q = QUERY.get(pid, name)
    key = norm(re.sub(r"\(.*?\)", "", name)).split()
    key = [w for w in key if len(w) > 2][:2]
    if pid in OVERRIDE:
        d = api(action="query", titles=OVERRIDE[pid], prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=250,
                iiextmetadatafilter="LicenseShortName|Artist|LicenseUrl")
    else:
        d = api(action="query", generator="search", gsrsearch=q + " filetype:bitmap", gsrnamespace=6, gsrlimit=30, prop="imageinfo",
                iiprop="url|size|extmetadata", iiurlwidth=250, iiextmetadatafilter="LicenseShortName|Artist|LicenseUrl")
    best = None
    for pg in (d.get("query", {}).get("pages", {}) or {}).values():
        ii = (pg.get("imageinfo") or [None])[0]
        if not ii or not ii.get("thumburl"):
            continue
        md = ii["extmetadata"]
        lic = md.get("LicenseShortName", {}).get("value", "")
        title = pg["title"]
        if not OK_LIC.match(lic) or BAD.search(title) or ii["width"] < 700:
            continue
        ratio = ii["width"] / max(1, ii["height"])
        score = 0
        if pid in OVERRIDE:
            score = 100
        else:
            if not any(w in norm(title) for w in key):
                continue
            score += 5 if re.search(r"winter|snow|zima|sneg|schnee|neige|inverno", title, re.I) else 0
            score += 3 if 1.2 <= ratio <= 1.9 else 0
            score += 2 if ii["width"] >= 2000 else 0
        if best is None or score > best[0]:
            best = (score, title, ii, lic, md)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=int, default=8)
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", default="")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    pts = json.load(open(os.path.join(ROOT, "data", "snegofili-tocke.json"), encoding="utf-8"))
    pts = pts.get("tocke", pts) if isinstance(pts, dict) else pts
    cp = os.path.join(OUT, "credits.json")
    cr = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    only = set(filter(None, a.only.split(",")))
    for p in pts:
        if only and p["id"] not in only:
            continue
        if p["id"] in cr and os.path.exists(os.path.join(OUT, p["id"] + ".jpg")):
            continue
        time.sleep(a.gap)
        b = pick(p)
        if not b:
            print("brez zadetka:", p["id"], flush=True)
            continue
        _, title, ii, lic, md = b
        time.sleep(a.gap)
        u = ii["thumburl"].replace("https://thumb.wikimedia.org/", "https://upload.wikimedia.org/").split("?")[0]
        im = Image.open(io.BytesIO(get(u))).convert("RGB")
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((128, 128), Image.LANCZOS)
        im.save(os.path.join(OUT, p["id"] + ".jpg"), "JPEG", quality=72, optimize=True)
        cr[p["id"]] = {"naslov": title[5:], "avtor": html.unescape(re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", ""))).strip()[:120],
                       "licenca": lic, "licenca_url": md.get("LicenseUrl", {}).get("value", ""), "stran": ii["descriptionurl"]}
        json.dump(cr, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("→", p["id"], "|", title, "|", lic, flush=True)
    if a.sheet:
        ids = [p["id"] for p in pts if os.path.exists(os.path.join(OUT, p["id"] + ".jpg"))]
        cols = 9
        sh = Image.new("RGB", (cols * 140, ((len(ids) + cols - 1) // cols) * 150), "#222")
        d = ImageDraw.Draw(sh)
        for i, pid in enumerate(ids):
            x, y = (i % cols) * 140, (i // cols) * 150
            sh.paste(Image.open(os.path.join(OUT, pid + ".jpg")), (x + 6, y + 2))
            d.text((x + 6, y + 133), pid[:20], fill="white")
        sh.save(a.sheet, "JPEG", quality=80)


if __name__ == "__main__":
    main()
