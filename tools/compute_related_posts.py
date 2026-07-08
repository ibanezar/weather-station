#!/usr/bin/env python3
"""
tools/compute_related_posts.py — TF-IDF sorodni članki.

Izračuna kosinusno podobnost med dejanskim besedilom vseh blog objav
(ne le skupnimi tagi, kot to danes počne article-enhance.js) in za
vsako objavo zapiše 3 najbolj podobne v blog/related.json.
article-enhance.js to datoteko uporabi kot prednostni vir za sekcijo
"Sorodni članki", z obstoječim ujemanjem po tagih kot rezervo.

Brez zunanjih odvisnosti (ni OpenAI API ključa v tem repozitoriju) --
TF-IDF in kosinusna podobnost sta implementirana v čistem Pythonu,
kar je za korpus te velikosti (~30 objav) povsem zadostno.

Uporaba:
    python3 tools/compute_related_posts.py
Ali kot knjižnica:
    from compute_related_posts import compute_and_write
    compute_and_write(posts)  # posts = že naložen seznam iz blog.json
"""
import json, os, re, math, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kratek seznam najpogostejših slovenskih veznikov/predlogov -- dovolj za
# TF-IDF na tem korpusu, ni potreben popoln lematizator.
STOPWORDS = set("""
in je za se na so ali da ne bo bi ti ga ji mu z s v k h o od do po pri
med ker ki ko naj bodo bila bil bilo smo ste sta sem si tudi tega tem
to ta te tu tam kje kdaj kako zakaj kot pa še to je bila so kar več
kaj kje bolj manj tako lahko že samo tudi ob ta ti oz njen njihov svoj
""".split())


def extract_text(html):
    html = re.sub(r"<script[\s\S]*?</script>", " ", html)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return html


def tokenize(text):
    text = text.lower()
    words = re.findall(r"[a-zščžćđ0-9]+", text)
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def tfidf_vectors(docs_tokens):
    n = len(docs_tokens)
    df = Counter()
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] += 1
    idf = {term: math.log((n + 1) / (df[term] + 1)) + 1 for term in df}
    vectors = []
    for tokens in docs_tokens:
        tf = Counter(tokens)
        total = sum(tf.values()) or 1
        vectors.append({term: (count / total) * idf[term] for term, count in tf.items()})
    return vectors


def cosine(a, b):
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[t] * b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_and_write(posts, top_n=3):
    slugs = [p["slug"] for p in posts]
    docs_tokens = []
    for p in posts:
        path = os.path.join(ROOT, "blog", f"{p['slug']}.html")
        try:
            html = open(path, encoding="utf-8").read()
        except FileNotFoundError:
            docs_tokens.append([])
            continue
        docs_tokens.append(tokenize(extract_text(html)))

    vectors = tfidf_vectors(docs_tokens)
    related = {}
    for i, slug in enumerate(slugs):
        sims = []
        for j, other in enumerate(slugs):
            if i == j:
                continue
            score = cosine(vectors[i], vectors[j])
            if score > 0.03:  # prag: izloči šum skoraj ničelne podobnosti
                sims.append((score, other))
        sims.sort(key=lambda x: -x[0])
        related[slug] = [s for _, s in sims[:top_n]]

    out = os.path.join(ROOT, "blog", "related.json")
    json.dump(related, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(out, "a", encoding="utf-8").write("\n")
    return related


def main():
    posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
    related = compute_and_write(posts)
    nonzero = sum(1 for v in related.values() if v)
    print(f"✓ zapisano: blog/related.json ({len(related)} objav, {nonzero} z vsaj eno sorodno)")


if __name__ == "__main__":
    main()
