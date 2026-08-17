#!/usr/bin/env python3
"""
tools/short_links.py — kratke povezave meteorec.si/i/<koda> za družbena omrežja.

Zakaj sploh: Instagram povezave v podpisu ali komentarju **nikoli** ne naredi
klikabilne — ostane golo besedilo, ki ga mora bralec pretipkati. Polni URL
članka je dolg čez 70 znakov in tega na telefonu ne pretipka nihče. Kratka
povezava (`meteorec.si/i/a7k9`) je dovolj kratka, da se da.

Kako: za vsak članek nastane majhna preusmeritvena stran `i/<koda>.html`
(meta refresh + `location.replace` + canonical na članek, `noindex`), preslikava
koda → slug pa se hrani v `i/index.json`. Strani in indeks so **izpeljane
datoteke** — piše jih `wire_all()` iz `tools/generate_monthly_post.py` ob objavi
članka, ročno se jih ne ureja.

Koda se izpelje determinístično iz sluga (sha256), tako da je za isti članek
vedno ista. Ob trku (dva sluga, ista koda) se koda podaljša za en znak, zato je
`i/index.json` merodajen vir — odjemalci naj kodo berejo z `lookup()`, ne
računajo sami.

Preusmeritvene strani so `noindex`: iskalnik naj indeksira članek, ne bližnjice.
V sitemap zato ne gredo.

Uporablja: tools/generate_monthly_post.py (`wire_all`), tools/post_to_instagram.py.
Facebook povezave linkificira sam, zato tam kratka povezava ni potrebna.

Usage:
  python3 tools/short_links.py --backfill   # kode za vse članke iz blog.json
  python3 tools/short_links.py <slug>       # izpiše kratko povezavo članka
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
SHORT_DIR = "i"
INDEX_NAME = "index.json"

# Brez 0/1/l/o — na majhni pisavi se zamenjajo, kodo pa se tipka na roko.
ALPHABET = "23456789abcdefghijkmnpqrstuvwxyz"
MIN_LEN = 4
MAX_LEN = 12


def _index_path(root=ROOT):
    return os.path.join(root, SHORT_DIR, INDEX_NAME)


def load_index(root=ROOT):
    """Preslikava koda → slug. Manjkajoč ali pokvarjen indeks je prazen."""
    try:
        with open(_index_path(root), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_index(index, root=ROOT):
    path = _index_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(index.items())), f, ensure_ascii=False, indent=2)
        f.write("\n")


def code_for(slug, length=MIN_LEN):
    """Determinístična koda dolžine `length` iz sluga."""
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    num = int.from_bytes(digest, "big")
    out = []
    for _ in range(length):
        num, rem = divmod(num, len(ALPHABET))
        out.append(ALPHABET[rem])
    return "".join(out)


def lookup(slug, root=ROOT):
    """Koda članka iz indeksa, ali None, če je še nima."""
    for code, mapped in load_index(root).items():
        if mapped == slug:
            return code
    return None


def short_url(code):
    return f"{SITE}/{SHORT_DIR}/{code}"


def _redirect_html(slug, target):
    return f"""<!doctype html>
<html lang="sl">
<head>
<meta charset="utf-8">
<title>Preusmeritev na članek</title>
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace("{target}");</script>
<style>body{{font:16px/1.6 system-ui,sans-serif;margin:3rem auto;max-width:40rem;padding:0 1rem}}</style>
</head>
<body>
<p>Preusmerjam na članek …</p>
<p>Če se stran ne odpre sama: <a href="{target}">{slug}</a></p>
</body>
</html>
"""


def ensure(slug, url, root=ROOT):
    """Poskrbi za kratko povezavo članka; vrne kodo.

    Če članek kodo že ima, se ta ohrani (objavljene povezave morajo držati) —
    preusmeritvena stran se le prepiše, če se je URL članka spremenil.
    """
    index = load_index(root)
    existing = lookup(slug, root)
    if existing:
        code = existing
    else:
        code = None
        for length in range(MIN_LEN, MAX_LEN + 1):
            candidate = code_for(slug, length)
            if index.get(candidate) in (None, slug):
                code = candidate
                break
        if code is None:  # praktično nedosegljivo (32^12 možnosti)
            raise RuntimeError(f"Ni proste kratke kode za slug {slug!r}.")
        index[code] = slug
        _save_index(index, root)

    target = url if url.startswith("http") else f"{SITE}{url}"
    page = os.path.join(root, SHORT_DIR, f"{code}.html")
    os.makedirs(os.path.dirname(page), exist_ok=True)
    html = _redirect_html(slug, target)
    if not os.path.exists(page) or open(page, encoding="utf-8").read() != html:
        with open(page, "w", encoding="utf-8") as f:
            f.write(html)
    return code


def backfill(root=ROOT):
    """Kratke povezave za vse članke iz blog.json (za starejše objave/reposte)."""
    with open(os.path.join(root, "blog.json"), encoding="utf-8") as f:
        posts = json.load(f)
    made = 0
    for post in posts:
        slug, url = post.get("slug"), post.get("url")
        if not slug or not url:
            continue
        if lookup(slug, root) is None:
            made += 1
        ensure(slug, url, root)
    print(f"✓ kratke povezave: {len(posts)} člankov, {made} novih kod")
    return made


def main():
    args = sys.argv[1:]
    if args and args[0] == "--backfill":
        backfill()
        return 0
    if not args:
        print(__doc__.strip().splitlines()[-2].strip(), file=sys.stderr)
        return 2
    code = lookup(args[0])
    if not code:
        print(f"Slug {args[0]!r} nima kratke povezave.", file=sys.stderr)
        return 1
    print(short_url(code))
    return 0


if __name__ == "__main__":
    sys.exit(main())
