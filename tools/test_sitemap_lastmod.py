#!/usr/bin/env python3
"""Test tools/sitemap_lastmod.py: lastmod samo naprej, samo strani z dateModified, nikoli iz prihodnosti.
Plus: zimski generatorji res pišejo dateModified (webpage_schema) in je geo_audit vidi."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitemap_lastmod as sl  # noqa: E402

fails = []


def check(name, cond):
    if not cond:
        fails.append(name)
        print("✗", name)


SM = """<urlset>
  <url>
    <loc>https://meteorec.si/zima/a/</loc>
    <lastmod>2026-11-25</lastmod>
    <changefreq>daily</changefreq>
  </url>
  <url>
    <loc>https://meteorec.si/zima/b/</loc>
    <lastmod>2026-11-27</lastmod>
  </url>
  <url>
    <loc>https://meteorec.si/zima/c/</loc>
    <lastmod>2026-11-20</lastmod>
  </url>
  <url>
    <loc>https://meteorec.si/zima/d/</loc>
    <lastmod>2026-11-20</lastmod>
  </url>
</urlset>"""
DM = {"https://meteorec.si/zima/a/": "2026-11-28",   # naprej
      "https://meteorec.si/zima/b/": "2026-11-26",   # nazaj: ne
      "https://meteorec.si/zima/c/": None,           # brez dateModified: ne
      "https://meteorec.si/zima/d/": "2027-01-01"}   # prihodnost: ne

new, ch = sl.sync(SM, DM.get, today="2026-11-28")
check("naprej", "<lastmod>2026-11-28</lastmod>" in new and len(ch) == 1)
check("nazaj ne", "<lastmod>2026-11-27</lastmod>" in new)
check("brez dateModified ne", new.count("<lastmod>2026-11-20</lastmod>") == 2)
check("prihodnost ne", "2027-01-01" not in new)
check("changefreq ostane", new.count("<changefreq>daily</changefreq>") == 1)
check("idempotentno", sl.sync(new, DM.get, today="2026-11-28")[1] == [])
check("tuj URL", sl.local_path("https://example.com/x/") is None)
check("pot strani", sl.local_path("https://meteorec.si/zima/a/").endswith(os.path.join("zima", "a", "index.html")))

# webpage_schema: dateModified se zapiše samo, če je podan
import generate_seo_pages as seo  # noqa: E402
a = seo.webpage_schema("/x/", "t", "d", date_published="2026-01-01")
b = seo.webpage_schema("/x/", "t", "d", date_published="2026-01-01", date_modified="2026-11-28")
check("brez date_modified ga ni", "dateModified" not in a)
check("z date_modified je", '"dateModified":"2026-11-28"' in b)
check("local_date_from_iso UTC->lokalno", seo.local_date_from_iso("2026-11-27T23:30:00+00:00") == "2026-11-28")
check("local_date_from_iso Z", seo.local_date_from_iso("2026-11-28T04:11:11Z") == "2026-11-28")
check("local_date_from_iso napaka", seo.local_date_from_iso("") is None and seo.local_date_from_iso("xx") is None)

print(f"sitemap lastmod: {len(fails)} napak")
sys.exit(1 if fails else 0)
