#!/usr/bin/env python3
"""tools/lektura_scan.py — lokalni, deterministični pregled slogovnih pasti v blogu (brez API-ja; lektura.yml je izklopljena).

Pravila izhajajo iz docs/slog-pisanja.md (razdelka 4–6): zapis števk in enot, narekovaji, pomišljaj, ura, decimalna vejica, znani
anglicizmi in napake. To NI lektura: najde mesta, kjer je napaka verjetna (ne vedno), in jih izpiše z odlomkom. Besedilo se izreže
iz <article> (brez skript, slogov, SVG, kode) — vezaji v URL-jih, atributih in imenih datotek se ne štejejo.

Uporaba:
  python3 tools/lektura_scan.py                    # vsi članki, povzetek po pravilih
  python3 tools/lektura_scan.py blog/x.html -v     # en članek, vsa mesta
  python3 tools/lektura_scan.py --md docs/lektura-scan-2026-10.md   # poročilo za pregled
"""
import argparse
import glob
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (id, opis, regex, zastavice). Regex deluje na golem besedilu članka (en niz, presledki normalizirani).
UNITS = r"(?:mm|cm|km/h|km|m/s|m³/s|hPa|W/m²|m|kg|g|l|min|h|ur|dni|%)"
RULES = [
    ("odstotek-brez-presledka", "Odstotek brez presledka (pravilo: 14 %)", r"(?<![\w.,])\d+(?:,\d+)?%", 0),
    ("enota-brez-presledka", "Enota brez presledka za številko (pravilo: 366 m, 12 °C)", r"(?<![\w.,/-])\d+(?:,\d+)?(?:°C|mm|cm|km/h|hPa|m/s)\b", 0),
    ("decimalna-pika", "Decimalna pika namesto vejice pred enoto", r"(?<![\w.,])\d{1,3}\.\d{1,2}\s?(?:°C|mm|cm|km/h|hPa|m/s|W/m²|%)", 0),
    ("ura-z-dvopicjem", "Ura z dvopičjem (pravilo: ob 7.30, ob 8. uri)", r"\bob\s+\d{1,2}:\d{2}\b", 0),
    ("ravni-narekovaji", "Ravni narekovaji \"…\" (pravilo: »…«)", r"(?<![\w=])\"[A-ZČŠŽa-zčšž][^\"<>\n]{2,80}\"", 0),
    ("ameriški-zaključek", "Narekovaj „…” z ameriškim zaključkom (pravilno „…“ ali »…«)", r"„[^“”\"\n]{1,80}”", 0),
    ("drug-slog-narekovajev", "Narekovaji „…“ (pravopisno dovoljeni, a vodnik predpisuje »…«; informativno)", r"„[^“”\"\n]{1,80}“", 0),
    ("vezaj-kot-pomislaj", "Vezaj z presledki kot pomišljaj (pravilo: – )", r"(?<=\S) (?:-|--) (?=\S)", 0),
    ("vezaj-v-obsegu", "Vezaj v obsegu številk (pravilo: 8–16)", r"(?<![\w./-])\d{1,4}-\d{1,4}\s(?:dni|dneva|mm|cm|km|°C|let|ur|m)\b", 0),
    ("presledek-pred-ločilom", "Presledek pred vejico ali piko", r"\w \s?[,.;](?=\s|$)", 0),
    ("podvojena-beseda", "Podvojena beseda", r"\b([a-zčšžA-ZČŠŽ]{3,}) \1\b", re.I),
    ("dva-presledka", "Dva zaporedna presledka (po izrezu)", r"(?<=\S)  (?=\S)", 0),
    ("števnik-5-dneva", "Števnik 5 ali več z dvojino (pravilo: 5 dni, 5 gob)", r"(?<![\d.,])(?:[5-9]|1\d|2[0-9])\s(?:dneva|gobi)\b", 0),
    ("števnik-1-dni", "Števnik 1 z množino", r"(?<![\d.,])1\s(?:dni|gobe|meseci)\b", 0),
    ("seštevka", "Znana napaka: „seštevka“ (pravilno: sešteva)", r"\bseštevk[ae]\b(?= se)|\bse seštevka\b", 0),
    ("anglicizem", "Anglicizem iz vodnika (rastni zamik/lag, trigger, feedback, na dnevni bazi, za vsak primer)",
     r"\b(?:trigger\w*|feedback\w*|fruiting body|na dnevni bazi|za vsak primer|lag\b|baseline)", re.I),
    ("kateri-v-dolgem-stavku", "»kateri« namesto »ki« (vodnik razdelek 6; preveri ročno)", r", kateri (?:je|so|se|bi|ima|imajo)\b", 0),
    ("skupaj-pisano-v-letu", "»v letu 2026« namesto kratke oblike (informativno): ne štejemo", r"(?!)", 0),
]
RULES = [r for r in RULES if r[0] != "skupaj-pisano-v-letu"]
COMPILED = [(i, d, re.compile(rx, fl)) for i, d, rx, fl in RULES]


def article_text(raw):
    m = re.search(r"<article\b.*?</article>", raw, re.S) or re.search(r"<main\b.*?</main>", raw, re.S)
    body = m.group(0) if m else raw
    body = re.sub(r"<(script|style|svg|noscript|template|code|pre)\b.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<(nav|header|footer|form|button)\b.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"</t[dh]>", " | ", body, flags=re.I)
    body = re.sub(r"</?(p|h1|h2|h3|h4|li|tr|div|br|section|figcaption|blockquote)\b[^>]*>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body).replace(" ", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", body)).strip()


def scan_text(text):
    hits = []
    for rid, desc, rx in COMPILED:
        for m in rx.finditer(text):
            a, b = max(0, m.start() - 50), min(len(text), m.end() + 50)
            if rid == "anglicizem" and re.search(r"\b(?:the|of|and|reveals|syndrome)\b", text[a:b]):
                continue   # citat v angleščini (literatura), ne anglicizem v slovenskem stavku
            hits.append((rid, desc, text[a:b].replace("\n", " ⏎ "), m.group(0)))
    return hits


def scan_file(path):
    return scan_text(article_text(open(path, encoding="utf-8").read()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("-v", action="store_true", help="izpiši vsa mesta")
    ap.add_argument("--md", help="zapiši poročilo v Markdown")
    args = ap.parse_args()
    files = args.files or sorted(glob.glob(os.path.join(ROOT, "blog", "*.html")))
    files = [f for f in files if os.path.basename(f) not in ("index.html",) and "/tema/" not in f]
    by_rule, by_file = {}, {}
    for f in files:
        for h in scan_file(f):
            by_rule.setdefault(h[0], []).append((f, h))
            by_file.setdefault(f, []).append(h)
    if args.md:
        out = ["# Lokalni slogovni pregled bloga (lektura_scan.py)\n",
               f"Pregledanih člankov: {len(files)}. Najdenih sumljivih mest: {sum(len(v) for v in by_rule.values())}. "
               "To je seznam za pregled, **ne lektura**: pravila najdejo verjetne napake, ne vseh in ne vedno pravih.\n",
               "| Pravilo | Mest | Člankov |\n|---|---|---|"]
        desc = {i: d for i, d, _ in COMPILED}
        for rid, items in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
            out.append(f"| {desc[rid]} | {len(items)} | {len({f for f, _ in items})} |")
        for rid, items in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
            out.append(f"\n## {desc[rid]}\n")
            for f, h in items[:40]:
                out.append(f"- `{os.path.basename(f)}`: …{h[2]}…")
            if len(items) > 40:
                out.append(f"- … in še {len(items) - 40} mest")
        open(args.md, "w", encoding="utf-8").write("\n".join(out) + "\n")
        print(f"zapisano: {args.md}")
        return 0
    for rid, items in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(items):5d}  {rid}  ({len({f for f, _ in items})} člankov)")
        if args.v:
            for f, h in items:
                print(f"        {os.path.basename(f)}: …{h[2]}…")
    print(f"\n{len(files)} člankov, {sum(len(v) for v in by_rule.values())} mest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
