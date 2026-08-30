#!/usr/bin/env python3
"""
tools/generate_makro_page.py — /makro/ pillar page + sitemap-makro.xml

Zgradi /makro/index.html (pregled vseh vrst v osebnem makro-fotografskem
arhivu, glej tools/generate_makro_post.py) iz data/makro.json, in svoj
sitemap-makro.xml -- isti vzorec ločenega sitemapa kot sitemap-weather.xml in
sitemap-seo.xml (glej robots.txt + SITEMAPS v tools/seo_audit.py), ker gre za
samostojno vrsto vsebine, ne za blog objave (te ureja wire_all()) ali
klimatološke/dogodkovne strani (te seo_smart_routine.py).

Kliče jo generate_makro_post.py po vsaki novi objavi; lahko jo poženeš tudi
samostojno, da hub stran obnoviš brez nove fotke (npr. po ročnem popravku
data/makro.json).

Uporaba:
    python3 tools/generate_makro_page.py
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 -- shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
CATALOG_FILE = os.path.join(ROOT, "data", "makro.json")
SITEMAP_FILE = os.path.join(ROOT, "sitemap-makro.xml")

INTRO = (
    "Osebni arhiv makro fotografij ob postaji IREICA1 — žuželke, srečane na sprehodih po Rečici "
    "ob Savinji, vsaka z vremenskim kontekstom dneva, ko je bila fotografirana. Ni skrbno kurirana "
    "SEO stran, ampak dnevnik: kar je pred fotoaparatom pristalo, to je tu."
)


def sl_opazanj(n):
    """Sklanjaj 'opažanje' po slovenski dvojini (1/2/3-4/5+) -- glej tudi
    sl_opazovanj() v tools/invasive_watch.py, ista slovnica, druga beseda."""
    n100 = n % 100
    if n100 == 1:
        return f"{n} opažanje"
    if n100 == 2:
        return f"{n} opažanji"
    if n100 in (3, 4):
        return f"{n} opažanja"
    return f"{n} opažanj"


def load_catalog():
    try:
        return json.load(open(CATALOG_FILE, encoding="utf-8"))
    except Exception:
        return {"updated": None, "species": []}


def build_index_html(cat):
    species = sorted(cat["species"], key=lambda s: s["last_seen"], reverse=True)

    if not species:
        cards_html = '    <p style="color:var(--muted)">Arhiv je še prazen — prva fotografija je na poti.</p>'
    else:
        cards = []
        for sp in species:
            n_txt = sl_opazanj(len(sp["sightings"]))
            sci_html = f' · <em>{sp["sci"]}</em>' if sp.get("sci") else ""
            cards.append(
                f'    <a class="mk-card" href="{sp["url"]}">\n'
                f'      <img src="{sp["cover_photo"]}" alt="" loading="lazy" width="200" height="200">\n'
                f'      <div class="mk-card-body">\n'
                f'        <h3>{sp["sl"]}{sci_html}</h3>\n'
                f'        <p>{n_txt} · nazadnje {seo.fmtd(sp["last_seen"])}</p>\n'
                f'      </div>\n'
                f'    </a>'
            )
        cards_html = '    <div class="mk-grid">\n' + "\n".join(cards) + "\n    </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Makro arhiv", None)])}
  <article>
    <div class="stn-badge"><span></span> Makro arhiv · IREICA1 · Rečica ob Savinji</div>
    <h1>Makro arhiv</h1>
    <p class="lead">{INTRO}</p>

{cards_html}
  </article>'''

    extra_style = '''<style>
.mk-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1rem;margin:1.6rem 0}
.mk-card{display:flex;gap:.8rem;align-items:center;background:var(--card-bg);border:1px solid var(--card-border);
  border-radius:14px;padding:.7rem;text-decoration:none;color:inherit}
.mk-card img{width:64px;height:64px;object-fit:cover;border-radius:10px;flex:none}
.mk-card h3{margin:0 0 .2rem;font-size:.95rem;color:var(--text)}
.mk-card p{margin:0;font-size:.8rem;color:var(--muted)}
</style>'''

    head_extras = extra_style + "\n" + seo.crumbs_schema([("Meteorec", "/"), ("Makro arhiv", None)]) \
        + "\n" + seo.webpage_schema("/makro/", "Makro arhiv", INTRO)
    return seo.page_shell("Makro arhiv", INTRO, "/makro/", head_extras, body)


def write_sitemap(cat):
    today = datetime.date.today().isoformat()
    entries = [(f"{SITE}/makro/", today, "weekly", "0.4")]
    for sp in cat["species"]:
        entries.append((f"{SITE}{sp['url']}", sp.get("last_seen", today), "monthly", "0.4"))
    parts = [
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{cf}</changefreq>\n    <priority>{prio}</priority>\n  </url>"
        for loc, lastmod, cf, prio in entries
    ]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(parts) + "\n</urlset>\n")
    open(SITEMAP_FILE, "w", encoding="utf-8").write(xml)
    return len(entries)


def build():
    cat = load_catalog()
    html = build_index_html(cat)
    seo.write_page("makro/index.html", html, force=True)
    n = write_sitemap(cat)
    print(f"✓ makro/index.html + sitemap-makro.xml ({n} URL-jev, {len(cat['species'])} vrst)")


if __name__ == "__main__":
    build()
