#!/usr/bin/env python3
"""
tools/seo_audit.py — SEO health check + sitemap vzdrževanje za meteorec.si

Dva načina delovanja:
  (privzeto)  samo pregled — poroča o vrzelih v pokritosti sitemapa,
              o manjkajočih on-page elementih ter o predolgih/podvojenih
              naslovih in opisih; vrne izhodni status 1, če najde napake.
  --fix       aditivno popravi sitemap.xml — doda manjkajoče ključne strani in
              blog objave ter osveži <lastmod> za domačo stran in /blog/.
              Nikoli ne odstrani ali prerazporedi obstoječih vnosov.

Namen: samodejno ujeti napake tipa "stran obstaja, a je ni v nobenem sitemapu"
(npr. /trendi/), odpraviti ročno delo pri dodajanju novih blog objav v sitemap,
ter opozoriti, kadar samodejno generirane strani (hub/novosti/mesečni blog)
dobijo naslov ali opis, ki ga Google v rezultatih obreže, ali podvojen
naslov/opis kot druga stran na strani.

Zaženi:
  python3 tools/seo_audit.py            # pregled; ne-nič izhod ob napakah
  python3 tools/seo_audit.py --fix      # popravi sitemap.xml na mestu
"""
import json, os, re, sys, datetime
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
TODAY = datetime.date.today().isoformat()
SITEMAPS = ["sitemap.xml", "sitemap-seo.xml", "sitemap-weather.xml"]

# Ključne strani, ki MORAJO biti pokrite v vsaj enem sitemapu.
# Metapodatki (changefreq, priority) se uporabijo le, ko stran dodajamo v sitemap.xml.
CORE = {
    "":                          ("hourly",  "1.0"),
    "blog/":                     ("weekly",  "0.8"),
    "o-postaji.html":            ("monthly", "0.6"),
    "gobarska-napoved/":         ("daily",   "0.8"),
    "vodostaj-savinje/":         ("daily",   "0.8"),
    "nevihte/":                  ("daily",   "0.8"),
    "agrometeo/":                ("daily",   "0.7"),
    "kakovost-zraka/":           ("daily",   "0.7"),
    "vreme-za-padalce/":         ("daily",   "0.6"),
    "trendi/":                   ("weekly",  "0.7"),
    "klima/":                    ("weekly",  "0.8"),
    "padavine/":                 ("weekly",  "0.8"),
    "temperatura/":              ("weekly",  "0.8"),
    "teden/":                    ("weekly",  "0.7"),
    "rekord/":                   ("weekly",  "0.7"),
    "pojavi/":                   ("weekly",  "0.7"),
    "novosti/":                  ("weekly",  "0.7"),
    "vreme/":                    ("daily",   "0.7"),
    "slovar/":                   ("monthly", "0.6"),
    "vreme-recica-ob-savinji/":  ("daily",   "0.7"),
    "vreme-mozirje/":            ("daily",   "0.6"),
    "vreme-nazarje/":            ("daily",   "0.6"),
    "vreme-ljubno-ob-savinji/":  ("daily",   "0.6"),
}

# Strani, na katerih preverimo osnovne on-page SEO elemente.
ONPAGE_SAMPLE = [
    "index.html", "o-postaji.html",
    "trendi/index.html", "klima/index.html", "padavine/index.html",
    "temperatura/index.html", "gobarska-napoved/index.html",
    "nevihte/index.html", "vreme-recica-ob-savinji/index.html",
]
ONPAGE_CHECKS = {
    "<title>":          re.compile(r"<title>.+?</title>", re.I | re.S),
    "meta description": re.compile(r'<meta[^>]+name=["\']description["\']', re.I),
    "canonical":        re.compile(r'<link[^>]+rel=["\']canonical["\']', re.I),
    "og:image":         re.compile(r'<meta[^>]+property=["\']og:image["\']', re.I),
    "JSON-LD":          re.compile(r'application/ld\+json', re.I),
}

# Priporočene dolžine za SERP prikaz (Google praviloma obreže naslov okrog
# 60 znakov in opis okrog 160 znakov; prekratek opis pomeni izgubljen prostor).
TITLE_MAX = 65
DESC_MIN, DESC_MAX = 50, 165
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
MAX_LISTED = 15  # omeji dolžino poročila; skupno število je vedno navedeno


def local_path(page):
    """Preslikaj javno pot v lokalno datoteko."""
    if page == "":
        return os.path.join(ROOT, "index.html")
    if page.endswith("/"):
        return os.path.join(ROOT, page, "index.html")
    return os.path.join(ROOT, page)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def sitemap_locs(text):
    return set(re.findall(r"<loc>(.*?)</loc>", text))


def all_sitemap_urls():
    urls = set()
    for sm in SITEMAPS:
        p = os.path.join(ROOT, sm)
        if os.path.exists(p):
            urls |= sitemap_locs(read(p))
    return urls


def url_block(url, lastmod, changefreq, priority):
    return (f"  <url>\n"
            f"    <loc>{url}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>\n")


def set_lastmod(text, url, date):
    """Osveži <lastmod> znotraj bloka <url> za dani loc."""
    pat = re.compile(
        r"(<url>\s*<loc>" + re.escape(url) + r"</loc>\s*<lastmod>)(.*?)(</lastmod>)",
        re.S)
    return pat.sub(lambda m: m.group(1) + date + m.group(3), text, count=1)


def audit(fix=False):
    problems, notes, additions = [], [], []
    union = all_sitemap_urls()

    # 1) Pokritost ključnih strani ------------------------------------------
    to_add = []  # (page, changefreq, priority) — samo tiste z obstoječo datoteko
    for page, (cf, prio) in CORE.items():
        url = f"{SITE}/{page}"
        exists = os.path.exists(local_path(page))
        if not exists:
            problems.append(f"KLJUČNA STRAN NE OBSTAJA: /{page} (v CORE seznamu, a ni datoteke)")
            continue
        if url not in union:
            problems.append(f"NI V SITEMAPU: {url}")
            to_add.append((page, cf, prio))

    # 2) Blog objave morajo biti v sitemap.xml ------------------------------
    blog = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    blog_urls = []  # (url, date)
    for post in blog:
        slug = post.get("slug")
        rel = post.get("url") or f"/blog/{slug}.html"
        if not rel.startswith("/"):
            rel = "/" + rel
        url = SITE + rel
        date = (post.get("date") or TODAY)[:10]
        blog_urls.append((url, date))
        if url not in union:
            problems.append(f"BLOG NI V SITEMAPU: {url}")

    # 3) Nobene mrtve povezave v sitemap.xml (loc → obstoječa datoteka) ------
    main = read(os.path.join(ROOT, "sitemap.xml"))
    for loc in sorted(sitemap_locs(main)):
        if not loc.startswith(SITE):
            continue
        page = loc[len(SITE) + 1:]  # odstrani "https://meteorec.si/"
        if not os.path.exists(local_path(page)):
            problems.append(f"MRTVA POVEZAVA v sitemap.xml: {loc} (ni datoteke {local_path(page)})")

    # 4) On-page osnovni elementi -------------------------------------------
    for rel in ONPAGE_SAMPLE:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        html = read(p)
        for name, pat in ONPAGE_CHECKS.items():
            if not pat.search(html):
                notes.append(f"ON-PAGE: /{rel} nima elementa '{name}'")

    # 5) Naslovi in opisi — dolžina in podvajanje po celotnem spletnem mestu --
    titles, descs = defaultdict(list), defaultdict(list)
    long_titles, bad_descs = [], []
    for loc in sorted(union):
        if not loc.startswith(SITE):
            continue
        page = loc[len(SITE) + 1:]
        p = local_path(page)
        if not os.path.exists(p):
            continue
        html = read(p)
        tm = TITLE_RE.search(html)
        if tm:
            title = re.sub(r"\s+", " ", tm.group(1)).strip()
            titles[title].append(page)
            if len(title) > TITLE_MAX:
                long_titles.append((len(title), page))
        dm = DESC_RE.search(html)
        if dm:
            desc = re.sub(r"\s+", " ", dm.group(1)).strip()
            descs[desc].append(page)
            if not (DESC_MIN <= len(desc) <= DESC_MAX):
                bad_descs.append((len(desc), page))

    dup_titles = {t: pages for t, pages in titles.items() if len(pages) > 1}
    dup_descs = {d: pages for d, pages in descs.items() if len(pages) > 1}

    for length, page in sorted(long_titles, reverse=True)[:MAX_LISTED]:
        notes.append(f"DOLG NASLOV ({length} zn., meja {TITLE_MAX}): /{page}")
    if len(long_titles) > MAX_LISTED:
        notes.append(f"... in še {len(long_titles) - MAX_LISTED} strani s predolgim naslovom")

    for length, page in sorted(bad_descs, reverse=True)[:MAX_LISTED]:
        why = "predolg" if length > DESC_MAX else "prekratek"
        notes.append(f"OPIS {why} ({length} zn., priporočeno {DESC_MIN}-{DESC_MAX}): /{page}")
    if len(bad_descs) > MAX_LISTED:
        notes.append(f"... in še {len(bad_descs) - MAX_LISTED} strani z neustrezno dolžino opisa")

    for title, pages in list(dup_titles.items())[:MAX_LISTED]:
        problems.append(f"PODVOJEN NASLOV na {len(pages)} straneh: \"{title}\" — {', '.join('/' + p for p in pages[:4])}")
    if len(dup_titles) > MAX_LISTED:
        problems.append(f"... in še {len(dup_titles) - MAX_LISTED} skupin podvojenih naslovov")

    for desc, pages in list(dup_descs.items())[:MAX_LISTED]:
        problems.append(f"PODVOJEN OPIS na {len(pages)} straneh: \"{desc[:70]}...\" — {', '.join('/' + p for p in pages[:4])}")
    if len(dup_descs) > MAX_LISTED:
        problems.append(f"... in še {len(dup_descs) - MAX_LISTED} skupin podvojenih opisov")

    # ── FIX -----------------------------------------------------------------
    if fix:
        changed = main
        insert = ""
        for page, cf, prio in to_add:
            url = f"{SITE}/{page}"
            insert += url_block(url, TODAY, cf, prio)
            additions.append(url)
        for url, date in blog_urls:
            if f"<loc>{url}</loc>" not in changed and f"<loc>{url}</loc>" not in insert:
                insert += url_block(url, date, "monthly", "0.7")
                additions.append(url)
        if insert:
            changed = changed.replace("</urlset>", insert + "</urlset>", 1)
        # Osveži lastmod domače strani in /blog/ na najnovejši datum objave.
        latest = max((d for _, d in blog_urls), default=TODAY)
        changed = set_lastmod(changed, f"{SITE}/", latest)
        changed = set_lastmod(changed, f"{SITE}/blog/", latest)
        if changed != main:
            with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
                f.write(changed)

    # ── Poročilo ------------------------------------------------------------
    lines = []
    lines.append(f"# SEO audit — {TODAY}")
    lines.append("")
    lines.append(f"- Sitemap URL-ov skupaj: **{len(union)}**")
    lines.append(f"- Ključnih strani (CORE): **{len(CORE)}**")
    lines.append(f"- Blog objav: **{len(blog_urls)}**")
    if fix and additions:
        lines.append("")
        lines.append(f"## Dodano v sitemap.xml ({len(additions)})")
        lines += [f"- {u}" for u in additions]
    if problems:
        lines.append("")
        lines.append(f"## Napake ({len(problems)})")
        lines += [f"- ❌ {p}" for p in problems]
    if notes:
        lines.append("")
        lines.append(f"## Opozorila ({len(notes)})")
        lines += [f"- ⚠️ {n}" for n in notes]
    if not problems and not notes:
        lines.append("")
        lines.append("✅ Brez napak — pokritost in on-page osnove so v redu.")

    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")

    # Po --fix so pokritostne napake odpravljene; vrni 0.
    # Brez --fix: ne-nič izhod, če ostajajo strukturne napake.
    remaining = 0 if fix else len(problems)
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(audit(fix="--fix" in sys.argv))
