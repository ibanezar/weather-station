#!/usr/bin/env python3
"""
tools/geo_audit.py — GEO (Generative Engine Optimization) pregled za meteorec.si

seo_audit.py preverja pokritost sitemapa in osnovne on-page elemente. Ta
skript preverja tisto, kar je specifično za citiranje s strani AI odgovorljivih
sistemov (ChatGPT, Perplexity, Google AI Overviews):

  1. Veljavnost JSON-LD — nerazveljaven blok je za strukturirano branje
     nekega orodja, kot da ga sploh ni.
  2. Ujemanje FAQPage sheme z vidno vsebino — shema, ki obljublja vprašanje
     ali odgovor, ki ga na strani dejansko ni, je natanko tisto, zaradi
     česar Google in AI sistemi shemi prenehajo zaupati.
  3. Doslednost avtorske entitete na blog objavah — ali `author` v
     BlogPosting/NewsArticle kaže nazaj na isto, prepoznavno osebo
     (`sameAs`/`url`/`@id`), ali je le gola vrstica z imenom brez vezave na
     entiteto z index.html/o-postaji.html.
  4. Mrtve povezave v llms.txt — če AI orodje prebere llms.txt in mu prva
     povezava vrne 404, je zaupanje v preostanek datoteke vprašljivo.

Samo pregled — nič ne popravlja. Izhodni status 1, če najde napake.

Zaženi:
  python3 tools/geo_audit.py
"""
import json, os, re, sys, glob, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
TODAY = datetime.date.today().isoformat()

LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
SKIP_DIRS = {".git", "node_modules", "tools", ".github"}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def local_path(page):
    if page == "" or page.endswith("/"):
        return os.path.join(ROOT, page, "index.html")
    return os.path.join(ROOT, page)


def all_html_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".html"):
                yield os.path.join(dirpath, fn)


def ldjson_nodes(block):
    """Razpakira en JSON-LD blok v seznam vozlišč (podpre @graph)."""
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        return None  # neveljaven — poroča ga check_jsonld_validity
    if isinstance(data, dict) and isinstance(data.get("@graph"), list):
        return data["@graph"]
    if isinstance(data, list):
        return data
    return [data]


def has_type(node, type_name):
    t = node.get("@type")
    if isinstance(t, list):
        return type_name in t
    return t == type_name


def rel(path):
    return os.path.relpath(path, ROOT)


# 1) Veljavnost JSON-LD ------------------------------------------------------

def check_jsonld_validity(problems):
    for path in all_html_files():
        html = read(path)
        for i, block in enumerate(LDJSON_RE.findall(html), start=1):
            try:
                json.loads(block)
            except json.JSONDecodeError as e:
                problems.append(f"NEVELJAVEN JSON-LD: {rel(path)} (blok #{i}): {e}")


# 2) FAQPage shema proti vidni vsebini ---------------------------------------

def check_faq_consistency(problems):
    for path in all_html_files():
        html = read(path)
        for block in LDJSON_RE.findall(html):
            if '"FAQPage"' not in block:
                continue
            nodes = ldjson_nodes(block)
            if nodes is None:
                continue
            for node in nodes:
                if not (isinstance(node, dict) and has_type(node, "FAQPage")):
                    continue
                for q in node.get("mainEntity", []):
                    qname = (q.get("name") or "").strip()
                    answer = q.get("acceptedAnswer") or {}
                    atext = (answer.get("text") or "").strip()
                    if qname and qname not in html:
                        problems.append(
                            f"FAQ SHEMA BREZ VIDNE VSEBINE: {rel(path)} — "
                            f"vprašanje ni v vidnem HTML: \"{qname[:70]}\"")
                    if atext and atext not in html:
                        problems.append(
                            f"FAQ SHEMA BREZ VIDNE VSEBINE: {rel(path)} — "
                            f"odgovor ni v vidnem HTML (vprašanje: \"{qname[:40]}\")")


# 3) Doslednost avtorske entitete na blog objavah ----------------------------

def check_author_entities(notes):
    bare, linked = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "blog", "*.html"))):
        html = read(path)
        for block in LDJSON_RE.findall(html):
            if '"BlogPosting"' not in block and '"NewsArticle"' not in block:
                continue
            nodes = ldjson_nodes(block)
            if nodes is None:
                continue
            for node in nodes:
                if not (isinstance(node, dict) and
                        (has_type(node, "BlogPosting") or has_type(node, "NewsArticle"))):
                    continue
                author = node.get("author")
                if not isinstance(author, dict):
                    continue
                if author.get("sameAs") or author.get("url") or author.get("@id"):
                    linked.append(rel(path))
                else:
                    bare.append(rel(path))
    if bare:
        examples = ", ".join(bare[:3])
        more = f" (+{len(bare) - 3} drugih)" if len(bare) > 3 else ""
        notes.append(
            f"AVTOR BREZ POVEZANE ENTITETE: {len(bare)} blog objav ima "
            f"\"author\": {{ \"@type\": \"Person\", \"name\": \"Filip Eremita\" }} "
            f"brez sameAs/url nazaj na isto osebo, ki jo pozna index.html "
            f"(#person) — npr. {examples}{more}. AI sistem, ki bere eno "
            f"objavo samo zase, avtorja ne more povezati z znano entiteto.")


# 4) llms.txt — mrtve povezave ------------------------------------------------

def check_llms_txt(problems):
    p = os.path.join(ROOT, "llms.txt")
    if not os.path.exists(p):
        problems.append("MANJKA llms.txt")
        return
    text = read(p)
    for url in re.findall(r"\((https://meteorec\.si/[^\s)]+)\)", text):
        page = url[len(SITE) + 1:]
        if page.endswith((".json",)):
            exists = os.path.exists(os.path.join(ROOT, page))
        else:
            exists = os.path.exists(local_path(page))
        if not exists:
            problems.append(f"llms.txt KAŽE NA MANJKAJOČO STRAN: {url}")


def audit():
    problems, notes = [], []

    check_jsonld_validity(problems)
    check_faq_consistency(problems)
    check_author_entities(notes)
    check_llms_txt(problems)

    lines = [f"# GEO audit — {TODAY}", ""]
    if problems:
        lines.append(f"## Napake ({len(problems)})")
        lines += [f"- ❌ {p}" for p in problems]
    if notes:
        lines.append("")
        lines.append(f"## Opozorila ({len(notes)})")
        lines += [f"- ⚠️ {n}" for n in notes]
    if not problems and not notes:
        lines.append("✅ Brez napak — JSON-LD velja, FAQ shema se ujema z vsebino, llms.txt kaže na obstoječe strani.")

    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(audit())
