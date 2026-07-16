#!/usr/bin/env python3
"""
Lektura že objavljenih blog člankov.
------------------------------------
Za podane sluge (ali zadnjih N objav iz blog.json) pošlje vidno besedilo
članka Claude lektorju (ista pravila kot LEKTOR_PROMPT v generate_daily_post:
slovnica, slog, anglicizmi/kalki, prekomerni trpnik) in vrnjene popravke
aplicira kot NATANČNE zamenjave besedila v HTML datoteki.

Zamenjave se aplicirajo samo, če se stari niz v datoteki pojavi natanko
enkrat -- s tem ni tveganja za poseg v strukturo, skripte ali metapodatke.
Naslov članka in meta opis se NE spreminjata (slug in blog.json ostaneta
veljavna), zato ponovno povezovanje (wire) ni potrebno.

Uporaba:
    python3 tools/lektor_existing_posts.py [slug1 slug2 ...]
    python3 tools/lektor_existing_posts.py --last 3

Potrebne env spremenljivke:
    ANTHROPIC_API_KEY
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import ROOT
from generate_daily_post import ANTHROPIC_MODEL, stream_claude

LEKTOR_REPLACE_PROMPT = """Si natančen slovenski lektor za blog meteorec.si. Dobiš HTML že objavljenega
članka. Tvoja naloga je najti in popraviti jezikovne napake v VIDNEM besedilu
članka (lead, odstavki, H2/H3 naslovi odsekov, callout).

Preveri:
1. SLOVNICA IN PRAVOPIS -- sklanjanje, vejice, ločila, velika/mala začetnica
   pri strokovnih izrazih (npr. "arso" -> "ARSO").
2. ANGLICIZMI IN KALKI -- dobesedni prevodi angleških fraz, ki v slovenščini
   ne zvenijo naravno; prekomerna raba trpnika ("je bilo izmerjeno"), kjer bi
   naravna slovenščina uporabila tvornik ali "se"; angleški narekovaji " "
   namesto slovenskih „ "; vezaj namesto pomišljaja, kjer sodi pomišljaj.
3. SLOG -- ponavljajoče se fraze, prazno besedičenje, toga formulacija.

STROGA PRAVILA:
- NE spreminjaj naslova članka (h1, <title>, og:*, JSON-LD), meta opisa,
  URL-jev, števil, merskih enot ali česarkoli znotraj <script> ali atributov.
- NE preoblikuj povedi, ki so že naravne -- popravi samo dejanske napake.
- Vsak popravek vrni kot par old/new, kjer je "old" DOBESEDEN niz iz podanega
  HTML (vključno z morebitnimi HTML oznakami znotraj povedi, presledki in
  ločili) in dovolj dolg, da se v datoteki pojavi natanko enkrat (po potrebi
  vključi nekaj sosednjih besed).

Vrni SAMO veljaven JSON (brez markdown fence) v tej shemi:
{
  "issues": ["kratek opis vsake najdene težave"],
  "replacements": [
    {"old": "dobeseden niz iz HTML", "new": "popravljen niz"}
  ]
}
Če napak ni, vrni prazna seznama."""


def load_last_slugs(n):
    posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    return [p["slug"] for p in posts[:n]]


def lektor_file(slug, api_key):
    path = os.path.join(ROOT, "blog", f"{slug}.html")
    try:
        html = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"⚠ {slug}: blog/{slug}.html ne obstaja -- preskačem.")
        return False

    # Za prompt odstranimo <script> bloke (manj šuma, nič popravkov v njih);
    # zamenjave se aplicirajo na izvirni datoteki, kjer velja pravilo "natanko 1x".
    stripped = re.sub(r"<script[\s\S]*?</script>", "", html)

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8000,
        # Lektura po fiksnem kontrolnem seznamu ne potrebuje razmišljanja --
        # glej opombo pri call_lektor v generate_daily_post.py.
        "thinking": {"type": "disabled"},
        "system": LEKTOR_REPLACE_PROMPT,
        "messages": [{"role": "user", "content": "HTML članka za lekturo:\n\n" + stripped}],
    }
    text = stream_claude(payload, api_key)
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.M).strip()
    result = json.loads(cleaned)

    print(f"\n── {slug}")
    for issue in result.get("issues", []):
        print(f"   - {issue}")

    applied = skipped = 0
    for rep in result.get("replacements", []):
        old, new = rep.get("old", ""), rep.get("new", "")
        if not old or old == new:
            continue
        count = html.count(old)
        if count != 1:
            print(f"   ⚠ preskočeno (najdeno {count}x namesto 1x): {old[:80]!r}")
            skipped += 1
            continue
        html = html.replace(old, new)
        applied += 1

    if applied:
        open(path, "w", encoding="utf-8").write(html)
        print(f"   ✓ {applied} popravkov apliciranih" + (f", {skipped} preskočenih" if skipped else ""))
        return True
    print("   (brez sprememb)" + (f" -- {skipped} popravkov preskočenih" if skipped else ""))
    return False


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY manjka.")

    args = [a for a in sys.argv[1:] if a]
    if "--last" in args:
        i = args.index("--last")
        n = int(args[i + 1]) if i + 1 < len(args) else 3
        slugs = load_last_slugs(n)
    elif args:
        slugs = args
    else:
        slugs = load_last_slugs(3)

    print("Lektura objav:", ", ".join(slugs))
    changed = sum(1 for s in slugs if lektor_file(s, api_key))
    print(f"\nSkupaj spremenjenih datotek: {changed}/{len(slugs)}")


if __name__ == "__main__":
    main()
