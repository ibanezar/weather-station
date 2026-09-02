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
  5. Zastarelost dateModified na ključnih, redno osveženih straneh —
     zastarel datum je napačen signal svežosti za vsak sistem, ki bere
     samo shemo, ne dejanske vsebine.
  6. Skoraj podvojena vsebina med kraji v dolini (vreme-*) — predlogi
     istega generatorja se lahko razlikujejo samo po imenu kraja, kar je
     ravno vzorec, ki ga Google in AI sistemi kaznujejo kot tanko/podvojeno
     vsebino.
  7. Neveljavne @id reference — {"@id": "..."} brez ustrezne definicije
     tega @id kjerkoli na strani je pokvarjena povezava znotraj grafa
     entitet, enako resno kot mrtva <a href>.

Preverjanji 5 in 6 sta opozorili (ne blokirata izhodne kode) — gre za mehka
signala, ne za zlomljeno shemo. Preverjanje 7 je napaka.

Samo pregled — nič ne popravlja. Izhodni status 1, če najde napake.

Zaženi:
  python3 tools/geo_audit.py
"""
import difflib, json, os, re, sys, glob, datetime

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


# 5) Zastarelost dateModified na ključnih straneh ----------------------------

# Prag = največ dovoljenih dni med dateModified in danes, preden stran
# postane opozorilo. Grobo po dejanski frekvenci osveževanja (dnevni cron
# dobi tesen prag, mesečni širšega) — namenoma velikodušno, da en sam
# zamujen tek crona še ne sproži lažnega alarma (isto načelo kot 🟡/🔴 prag
# v meteogasilec/gasilec.js).
FRESHNESS_PAGES = {
    "klima/index.html": 2, "padavine/index.html": 2, "temperatura/index.html": 2,
    "teden/index.html": 8, "trendi/index.html": 8,
    "tocnost-napovedi/index.html": 2, "gobarska-napoved/index.html": 2,
    "meteogasilec/index.html": 2, "nevihte/index.html": 1,
    "agrometeo/index.html": 2, "test-napovedi/index.html": 32,
}
DATE_MOD_RE = re.compile(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})')


def check_freshness(notes):
    today = datetime.date.today()
    for page, max_days in FRESHNESS_PAGES.items():
        path = os.path.join(ROOT, page)
        if not os.path.exists(path):
            continue
        m = DATE_MOD_RE.search(read(path))
        if not m:
            continue
        age = (today - datetime.date.fromisoformat(m.group(1))).days
        if age > max_days:
            notes.append(f"ZASTAREL dateModified: {page} — {m.group(1)} ({age} dni nazaj, prag {max_days})")


# 6) Skoraj podvojena vsebina med kraji v dolini -----------------------------

NEARBY_TOWN_PAGES = [
    "vreme-mozirje/index.html", "vreme-nazarje/index.html",
    "vreme-ljubno-ob-savinji/index.html", "vreme-gornji-grad/index.html",
    "vreme-luce/index.html", "vreme-solcava/index.html",
    "vreme-kamp-menina/index.html", "vreme-logarska-dolina/index.html",
    "vreme-forest-camping-mozirje/index.html", "vreme-glamping-savinja/index.html",
    "vreme-herbal-glamping-ljubno/index.html",
]
TAG_STRIP_RE = re.compile(r"<[^>]+>")
NEAR_DUP_THRESHOLD = 0.85


def main_content_text(html):
    """Besedilo med <h1> in footerjem -- izloči skupno glavo/nogo, ki bi
    podobnost med KATERIMA KOLI dvema stranema strani napihnila umetno."""
    start = html.find("<h1")
    end = html.find('<footer class="site-foot">')
    if start == -1 or end == -1 or end <= start:
        return None
    body = html[start:end]
    body = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", body)
    return re.sub(r"\s+", " ", TAG_STRIP_RE.sub(" ", body)).strip()


def check_near_duplicate_towns(notes):
    texts = {}
    for page in NEARBY_TOWN_PAGES:
        path = os.path.join(ROOT, page)
        if not os.path.exists(path):
            continue
        text = main_content_text(read(path))
        if text:
            texts[page] = text
    pages = list(texts.items())
    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            page_a, text_a = pages[i]
            page_b, text_b = pages[j]
            ratio = difflib.SequenceMatcher(None, text_a, text_b).ratio()
            if ratio >= NEAR_DUP_THRESHOLD:
                notes.append(
                    f"SKORAJ PODVOJENA VSEBINA: {page_a} ↔ {page_b} — "
                    f"{ratio:.0%} podobnosti glavnega besedila")


# 7) Neveljavne @id reference -------------------------------------------------

ID_DEF_RE = re.compile(r'"@id"\s*:\s*"([^"]+)"')
BARE_ID_REF_RE = re.compile(r'\{\s*"@id"\s*:\s*"([^"]+)"\s*\}')


def check_id_references(problems):
    all_ids = set()
    all_refs = []  # (path, id)
    for path in all_html_files():
        html = read(path)
        for block in LDJSON_RE.findall(html):
            if '"@id"' not in block:
                continue
            refs_here = [(path, m.group(1)) for m in BARE_ID_REF_RE.finditer(block)]
            # Definicije = "@id" ki NI del gole {"@id": "..."} reference --
            # zamaskiraj reference, preden štejemo definicije, sicer bi
            # referenca sama sebe "potrdila" kot veljavno.
            masked = BARE_ID_REF_RE.sub("", block)
            for m in ID_DEF_RE.finditer(masked):
                all_ids.add(m.group(1))
            all_refs.extend(refs_here)
    for path, ref_id in all_refs:
        if ref_id not in all_ids:
            problems.append(f"NEVELJAVNA @id REFERENCA: {rel(path)} → {ref_id} (ni definirana nikjer na strani)")


def audit():
    problems, notes = [], []

    check_jsonld_validity(problems)
    check_faq_consistency(problems)
    check_author_entities(notes)
    check_llms_txt(problems)
    check_freshness(notes)
    check_near_duplicate_towns(notes)
    check_id_references(problems)

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
