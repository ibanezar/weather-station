#!/usr/bin/env python3
"""
tools/seed_view_counts.py — enkratna napolnitev števcev ogledov iz GoatCounterja

Števci ogledov (blog/views.js → Worker /views → KV ključ "views:<slug>") so
začeli pri nič, čeprav so bili članki brani že prej. GoatCounter, ki na strani
teče od začetka, to zgodovino ima — samo javno dostopna ni (javni števci so
izklopljeni, /counter/<pot>.json vrne 403), zato jo je treba prenesti z API
žetonom.

Zgodovino zna dobiti po dveh poteh; uporabi tisto, ki je na voljo:
  • GOATCOUNTER_TOKEN je nastavljen → API /api/v0/stats/hits. En klic za vse
    poti in poljubno časovno okno prek --start.
  • žetona ni → javni števci /counter/<pot>.json. Brez žetona, a zahteva
    vklopljeno »Allow adding visitor counts on your website« v nastavitvah,
    en klic na članek in samo skupni seštevek brez časovnega okna.

Kaj naredi:
  1. Prebere število obiskovalcev po poteh (na enega od zgornjih načinov).
  2. Poti /blog/<slug>.html preslika v sluge in obdrži samo tiste, ki so
     dejansko v blog.json.
  3. Trenutne vrednosti prebere prek Workerjevega /views?slugs=… (en klic,
     brez Cloudflare poverilnic).
  4. Za vsak slug izračuna max(trenutno, zgodovina) in zapiše samo tam, kjer
     bi se vrednost povečala.

Zaradi koraka 4 je skripta idempotentna: drugi zagon ne spremeni ničesar in
sproti nabranih ogledov nikoli ne povozi navzdol.

POZOR: GoatCounterjev `count` je število OBISKOVALCEV, ne prikazov strani.
To se dobro ujema s štetjem v views.js (ena naprava = en ogled na 12 ur),
zato sta vrstici primerljivi; nista pa isto kot skupno število prikazov.

Privzeto teče na suho (izpiše, kaj bi naredil). Zapiše šele z --apply.

Okoljske spremenljivke:
    GOATCOUNTER_TOKEN       neobvezno: API žeton z dovoljenjem za branje
                            statistike (GoatCounter → Settings → API tokens).
                            Brez njega se berejo javni števci.
    CLOUDFLARE_API_TOKEN    žeton z dovoljenjem za pisanje v KV
    CLOUDFLARE_ACCOUNT_ID   ID računa
    GOATCOUNTER_SITE        neobvezno, privzeto ibanezar.goatcounter.com
    KV_NAMESPACE_ID         neobvezno, privzeto vrednost iz wrangler.toml

Uporaba:
    python3 tools/seed_view_counts.py                 # na suho
    python3 tools/seed_view_counts.py --apply         # dejanski zapis
    python3 tools/seed_view_counts.py --start 2019-01-01 --apply
"""
import argparse, glob, json, os, re, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SITE = "ibanezar.goatcounter.com"
DEFAULT_KV_ID = "ad19629f12a042dd8cd90c64a68662b4"  # COUNTER_KV iz wrangler.toml
PAGE_LIMIT = 200  # poti na stran pri GoatCounterju

# Naslovi so nastavljivi prek okolja samo zato, da je skripto mogoče pognati
# proti preizkusnim strežnikom; v normalni rabi se ne nastavljajo.
WORKER = os.environ.get("WORKER_BASE") or "https://weatherireica1.filip-eremita.workers.dev"
CF_API = os.environ.get("CF_API_BASE") or "https://api.cloudflare.com/client/v4"


def site_base(site):
    """Dovoli 'primer.goatcounter.com' ali 'http://127.0.0.1:8912'."""
    return site if "://" in site else "https://" + site


def http(url, method="GET", headers=None, body=None, timeout=30):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"✗ {method} {url.split('?')[0]} → HTTP {e.code}\n  {detail}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise SystemExit(f"✗ {method} {url.split('?')[0]} ni dosegljiv: {e}")


# ── 1. GoatCounter ──────────────────────────────────────────────────────────
def fetch_goatcounter(site, token, start, end):
    """Vrne {pot: število obiskovalcev}. Stran se lista prek exclude_paths —
    GoatCounter nima kurzorja, ampak pričakuje seznam že videnih path ID-jev."""
    base = f"{site_base(site)}/api/v0/stats/hits"
    headers = {"Authorization": f"Bearer {token}"}
    seen_ids, hits, page = [], {}, 0
    while True:
        page += 1
        q = {"start": start, "limit": str(PAGE_LIMIT)}
        if end:
            q["end"] = end
        url = base + "?" + urllib.parse.urlencode(q)
        # exclude_paths je ponovljiv parameter, ne seznam ločen z vejicami
        for pid in seen_ids:
            url += "&exclude_paths=" + str(pid)
        data = http(url, headers=headers)
        batch = data.get("hits") or []
        for h in batch:
            if h.get("event"):
                continue  # dogodki niso ogledi strani
            path = h.get("path") or ""
            hits[path] = hits.get(path, 0) + int(h.get("count") or 0)
            if h.get("path_id") is not None:
                seen_ids.append(h["path_id"])
        print(f"  GoatCounter stran {page}: {len(batch)} poti (skupaj {len(hits)})")
        if not data.get("more") or not batch:
            break
        if page >= 40:
            print("  ⚠ ustavljam se pri 40 straneh — preveri obseg.", file=sys.stderr)
            break
    return hits


def known_slugs():
    """Vsi slugi, ki na strani dejansko obstajajo in imajo števec ogledov.

    Ne zadošča blog.json: nekaj starejših člankov (npr. poplave-2023,
    el-nino-2026) je še vedno objavljenih in povezanih iz drugih zapisov,
    v seznamu pa jih ni. Tudi ti nosijo views.js, zato njihove zgodovine
    ne smemo zavreči — merodajne so datoteke v blog/."""
    slugs = {
        os.path.basename(f)[:-len(".html")]
        for f in glob.glob(os.path.join(ROOT, "blog", "*.html"))
    }
    slugs.discard("index")
    try:
        posts = json.load(open(os.path.join(ROOT, "blog.json"), encoding="utf-8"))
        slugs |= {p["slug"] for p in posts}
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        pass
    return {s for s in slugs if re.fullmatch(r"[a-z0-9-]{1,120}", s)}


def fetch_public_counts(site, slugs):
    """Brez API žetona: prebere javne števce /counter/<pot>.json.

    Deluje samo, če je v GoatCounterju vklopljeno »Allow adding visitor counts
    on your website«. En klic na članek (za ~80 člankov je to sprejemljivo,
    ker gre za enkratno opravilo), `count` pa je oblikovan niz s tisočicami
    (»1,234«), zato iz njega poberemo same števke."""
    base = site_base(site)
    counts, denied = {}, 0
    for i, slug in enumerate(sorted(slugs), 1):
        path = urllib.parse.quote(f"/blog/{slug}.html", safe="")
        try:
            data = http(f"{base}/counter/{path}.json", timeout=15)
        except SystemExit as e:
            if "HTTP 403" in str(e):
                denied += 1
                continue          # javni števci izklopljeni
            if "HTTP 404" in str(e):
                continue          # te poti GoatCounter ne pozna (ni bila obiskana)
            raise
        n = re.sub(r"\D", "", str(data.get("count") or ""))
        if n and int(n):
            counts[f"/blog/{slug}.html"] = int(n)
        if i % 20 == 0:
            print(f"  … {i}/{len(slugs)}")
    if denied and not counts:
        raise SystemExit(
            "✗ GoatCounter vrača 403 za javne števce.\n"
            "  Vklopi »Allow adding visitor counts on your website« v nastavitvah,\n"
            "  ali pa nastavi GOATCOUNTER_TOKEN in bo šlo prek API-ja."
        )
    return counts


def path_to_slug(path):
    """/blog/foo.html?utm=x → foo ; karkoli drugega → None"""
    p = urllib.parse.urlsplit(path).path
    if not p.startswith("/blog/"):
        return None
    slug = p[len("/blog/"):].rstrip("/")
    slug = re.sub(r"\.html?$", "", slug, flags=re.I)
    return slug if re.fullmatch(r"[a-z0-9-]{1,120}", slug) else None


def map_to_slugs(hits, known):
    """Sešteje obiskovalce po slugu; vrne (mapirano, preskočeno)."""
    out, skipped = {}, {}
    for path, n in hits.items():
        slug = path_to_slug(path)
        if slug and slug in known:
            out[slug] = out.get(slug, 0) + n
        elif n:
            skipped[path] = n
    return out, skipped


# ── 2. trenutno stanje prek Workerja ────────────────────────────────────────
def fetch_current(slugs):
    """Prebere obstoječe števce prek /views?slugs=… v svežnjih po 60
    (Worker več kot toliko slugov na klic ne obdela)."""
    current = {}
    batch = [s for s in slugs]
    for i in range(0, len(batch), 60):
        chunk = batch[i:i + 60]
        url = f"{WORKER}/views?slugs=" + urllib.parse.quote(",".join(chunk))
        data = http(url)
        views = data.get("views")
        if not isinstance(views, dict):
            raise SystemExit(
                "✗ Worker ni vrnil polja 'views'. Endpoint /views najbrž še ni\n"
                "  razporejen — najprej zlij spremembo workerja v main."
            )
        current.update(views)
    return current


# ── 3. zapis v KV ───────────────────────────────────────────────────────────
def kv_bulk_put(account_id, namespace_id, token, pairs):
    url = f"{CF_API}/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/bulk"
    body = [{"key": k, "value": str(v)} for k, v in pairs]
    res = http(url, method="PUT", headers={"Authorization": f"Bearer {token}"}, body=body)
    if not res.get("success"):
        raise SystemExit(f"✗ Cloudflare KV zapis ni uspel: {json.dumps(res)[:400]}")
    return len(body)


def main():
    ap = argparse.ArgumentParser(description="Napolni števce ogledov iz GoatCounterja.")
    ap.add_argument("--start", default="2019-01-01", help="začetni datum (privzeto 2019-01-01)")
    ap.add_argument("--end", default=None, help="končni datum (privzeto: danes)")
    ap.add_argument("--apply", action="store_true", help="dejansko zapiši v KV")
    args = ap.parse_args()

    gc_token = os.environ.get("GOATCOUNTER_TOKEN")
    site = os.environ.get("GOATCOUNTER_SITE") or DEFAULT_SITE
    ns_id = os.environ.get("KV_NAMESPACE_ID") or DEFAULT_KV_ID

    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    cf_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    # Preverimo že tu, da ob --apply ne pridemo do konca vsega dela in šele
    # takrat ugotovimo, da manjka poverilnica.
    if args.apply and not (cf_token and cf_account):
        raise SystemExit("✗ CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID nista nastavljena.")

    known = known_slugs()
    print(f"Člankov s števcem: {len(known)}")

    # Dve enakovredni poti do iste številke: API žeton (en klic za vse poti,
    # poljubno časovno okno) ali javni števci (brez žetona, a en klic na
    # članek in samo skupni seštevek). Vzamemo, kar je na voljo.
    if gc_token:
        print(f"\n1) Berem GoatCounter API ({site}, od {args.start}) …")
        hits = fetch_goatcounter(site, gc_token, args.start, args.end)
    else:
        print(f"\n1) Berem javne števce GoatCounterja ({site}) …")
        print("   (GOATCOUNTER_TOKEN ni nastavljen — za časovno omejitev "
              "z --start bi bil potreben žeton)")
        hits = fetch_public_counts(site, known)
    historic, skipped = map_to_slugs(hits, known)
    print(f"   → {len(historic)} člankov z zgodovino, "
          f"{sum(historic.values())} obiskovalcev skupaj")
    if skipped:
        top = sorted(skipped.items(), key=lambda kv: -kv[1])[:5]
        print(f"   (izven /blog/ ali brez ujemanja: {len(skipped)} poti, "
              f"npr. {', '.join(p for p, _ in top)})")
    if not historic:
        print("Ni česa napolniti.")
        return 0

    print("\n2) Berem trenutne števce prek Workerja …")
    current = fetch_current(sorted(historic))

    # max() namesto seštevka: sproti nabranih ogledov ne podvojimo, hkrati pa
    # ponovni zagon ne spremeni ničesar.
    changes = []
    for slug in sorted(historic, key=lambda s: -historic[s]):
        now, hist = int(current.get(slug, 0)), historic[slug]
        if hist > now:
            changes.append((slug, now, hist))

    print(f"\n3) Za posodobitev: {len(changes)} od {len(historic)}")
    for slug, now, hist in changes[:15]:
        print(f"   {hist:>7}  (zdaj {now:>5})  {slug}")
    if len(changes) > 15:
        print(f"   … in še {len(changes) - 15}")

    if not changes:
        print("\nVse je že vsaj tako visoko kot v GoatCounterju — nič za storiti.")
        return 0

    if not args.apply:
        print("\nTo je bil suhi tek. Za dejanski zapis dodaj --apply.")
        return 0

    print("\n4) Zapisujem v KV …")
    n = kv_bulk_put(cf_account, ns_id, cf_token,
                    [("views:" + slug, hist) for slug, _, hist in changes])
    print(f"✓ Zapisanih {n} ključev.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
