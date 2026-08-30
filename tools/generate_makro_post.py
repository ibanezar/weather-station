#!/usr/bin/env python3
"""
tools/generate_makro_post.py — osebni makro-fotografski arhiv /makro/
-----------------------------------------------------------------------
Ni SEO-gonjen produkt kot preostanek strani -- osebni arhiv Filipovih makro
fotografij (žuželke, kasneje morda gobe/rastline), z vremenskim kontekstom
IREICA1 ob dnevu opažanja.

Vsak dan (`makro-daily.yml`):
  1. Poišče najstarejšo čakajočo fotko v `makro-inbox/` (glej README.md tam za
     format sidecar YAML-a) -- queue, ne "objavi takoj ob nalaganju", da lahko
     Filip naloži več fotk naenkrat in se objavljajo ena na dan.
  2. Prebere metapodatke: sidecar YAML > EXIF > privzete vrednosti (lokacija
     IREICA1, glej DEFAULT_LAT/DEFAULT_LON spodaj).
  3. Če manjka `vrsta`, poskusi iNaturalist Computer Vision (best-effort --
     rabi INATURALIST_API_TOKEN, glej identify_species()). Brez zanesljivega
     zadetka fotka gre v makro-inbox/pregled/ za ROČNO identifikacijo --
     napačna samodejna identifikacija bi bila slabša kot nobena (isto načelo
     kot tools/invasive_watch.py in fetch_species_photos.py).
  4. Iz history.json izračuna vremenski kontekst dneva opažanja (temperatura,
     padavine, GDD10 od 1.1., primerjava s koledarskim povprečjem).
  5. Pokliče Claude API za besedilo (naravoslovni del + ločen vremenski blok,
     glej SYSTEM_PROMPT) in isti lektor prehod kot dnevni članek
     (generate_daily_post.call_lektor -- preverja slovnico/dejstva/anglicizme).
  6. Zapiše /makro/<vrsta-slug>/index.html (ena stalna stran na vrsto -- nova
     opažanja iste vrste se dodajo v dnevnik opažanj na isti strani, ne nova
     stran na fotko), posodobi data/makro.json in pokliče
     generate_makro_page.py za /makro/index.html + sitemap-makro.xml.

Uporaba:
    python3 tools/generate_makro_post.py [--wire] [--dry-run]

    --dry-run  samo pove, katero vrsto bi objavil, brez klica Claude API.
    --wire     dejansko zapiše stran, posodobi katalog/sitemap/hub in premakne
               fotko v makro-inbox/objavljeno/. Brez --wire skripta pokliče
               Claude API in izpiše osnutek na stdout, a ničesar ne zapiše —
               isti vzorec kot pri ostalih generatorjih objav v repozitoriju.

Potrebne env spremenljivke:
    ANTHROPIC_API_KEY     -- Claude API ključ (isti secret kot dnevni članek)
    INATURALIST_API_TOKEN -- opcijsko, za samodejno identifikacijo (glej zgoraj)

Datum opažanja pride iz sidecarja/EXIF-a/imena datoteke (glej resolve_metadata),
ne od "danes" -- POST_DATE tu torej ni relevanten (v nasprotju z ostalimi
generatorji bloga).
"""
import datetime, html, json, os, re, shutil, sys, urllib.error, urllib.request

import yaml
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_daily_post import ANTHROPIC_MODEL, call_lektor, hexrgb, stream_claude, LAT as STATION_LAT, LON as STATION_LON  # noqa: E402
import generate_seo_pages as seo  # noqa: E402 -- shared template helpers (page_shell, crumbs, ...)
import generate_makro_page  # noqa: E402 -- /makro/ hub + sitemap-makro.xml

ROOT = seo.ROOT
SITE = seo.SITE

INBOX = os.path.join(ROOT, "makro-inbox")
PUBLISHED_DIR = os.path.join(INBOX, "objavljeno")
REVIEW_DIR = os.path.join(INBOX, "pregled")
IMG_EXTS = (".jpg", ".jpeg", ".png")
CATALOG_FILE = os.path.join(ROOT, "data", "makro.json")

DEFAULT_LAT, DEFAULT_LON = STATION_LAT, STATION_LON
DEFAULT_LOCATION_LABEL = "Rečica ob Savinji"
GDD_BASE_C = 10.0


# ── Nabiralnik: EXIF, sidecar, razrešitev metapodatkov ───────────────────────

def sidecar_path(photo_path):
    base, _ = os.path.splitext(photo_path)
    return base + ".yaml"


def load_sidecar(photo_path):
    p = sidecar_path(photo_path)
    if os.path.isfile(p):
        try:
            return yaml.safe_load(open(p, encoding="utf-8")) or {}
        except Exception as e:
            print(f"⚠ sidecar {p} ni veljaven YAML, ignoriram: {e}")
    return {}


def _gps_to_deg(coord, ref):
    if not coord:
        return None
    try:
        d, m, s = coord
        val = float(d) + float(m) / 60 + float(s) / 3600
    except (TypeError, ValueError):
        return None
    if ref in ("S", "W"):
        val = -val
    return round(val, 6)


def read_exif(photo_path):
    """Vrne {"datum":..., "lat":..., "lon":...} iz EXIF; manjkajoča polja None.
    GPS/DateTimeOriginal živita v ločenih EXIF pod-IFD-jih (0x8825/0x8769),
    ne neposredno na vrhu -- Pillovih exif.get_ifd() klica potrebna dva."""
    out = {"datum": None, "lat": None, "lon": None}
    try:
        img = Image.open(photo_path)
        exif = img.getexif()
        if not exif:
            return out
        exif_ifd = exif.get_ifd(0x8769) or {}
        dt = exif_ifd.get(0x9003) or exif.get(0x9003)
        if dt:
            try:
                out["datum"] = datetime.datetime.strptime(dt, "%Y:%m:%d %H:%M:%S").date().isoformat()
            except ValueError:
                pass
        gps_ifd = exif.get_ifd(0x8825) or {}
        if gps_ifd:
            out["lat"] = _gps_to_deg(gps_ifd.get(2), gps_ifd.get(1))
            out["lon"] = _gps_to_deg(gps_ifd.get(4), gps_ifd.get(3))
    except Exception as e:
        print(f"⚠ EXIF branje ni uspelo za {photo_path}: {e}")
    return out


def resolve_metadata(photo_path):
    sc = load_sidecar(photo_path)
    exif = read_exif(photo_path)

    datum = sc.get("datum") or exif.get("datum")
    if not datum:
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", os.path.basename(photo_path))
        datum = m.group(1) if m else datetime.date.fromtimestamp(os.path.getmtime(photo_path)).isoformat()

    lok = sc.get("lokacija") if isinstance(sc.get("lokacija"), dict) else {}
    lat = lok.get("lat", exif.get("lat"))
    lon = lok.get("lon", exif.get("lon"))
    label = lok.get("label") or DEFAULT_LOCATION_LABEL
    if lat is None:
        lat = DEFAULT_LAT
    if lon is None:
        lon = DEFAULT_LON

    return {
        "datum": datum,
        "lat": lat,
        "lon": lon,
        "location_label": label,
        "vrsta": (sc.get("vrsta") or "").strip(),
        "sci": (sc.get("sci") or "").strip(),
        "opomba": (sc.get("opomba") or "").strip(),
    }


def queue_files():
    if not os.path.isdir(INBOX):
        return []
    files = [f for f in os.listdir(INBOX)
             if f.lower().endswith(IMG_EXTS) and os.path.isfile(os.path.join(INBOX, f))]
    files.sort()
    return files


# ── iNaturalist Computer Vision (best-effort) ────────────────────────────────
# POZOR: score_image zahteva pravi OAuth uporabniški token (ne samo API ključ),
# ki ga trenutno nimamo nastavljenega (glej README v makro-inbox/) -- brez
# INATURALIST_API_TOKEN ta funkcija VEDNO vrne None in fotka gre v pregled/.
# To je namerno: napačna samodejna identifikacija bi bila slabša kot ročna
# (isto načelo kot fallback v tools/invasive_watch.py).

INAT_CV_URL = "https://api.inaturalist.org/v1/computervision/score_image"
INAT_MIN_SCORE = 60.0


def identify_species(photo_path, lat, lon, datum):
    token = os.environ.get("INATURALIST_API_TOKEN")
    if not token:
        return None
    try:
        boundary = "----meteorecMakroBoundary"
        fields = {"lat": str(lat), "lng": str(lon), "observed_on": datum}
        body = bytearray()
        for k, v in fields.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo.jpg"\r\n'
                  f'Content-Type: image/jpeg\r\n\r\n').encode()
        with open(photo_path, "rb") as f:
            body += f.read()
        body += f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            INAT_CV_URL, data=bytes(body), method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {token}",
                "User-Agent": "Meteorec-Makro/1.0 (https://meteorec.si; kontakt: filip.eremita@gmail.com)",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        results = data.get("results") or []
        if not results:
            return None
        top = results[0]
        score = float(top.get("combined_score") or 0)
        if score < INAT_MIN_SCORE:
            print(f"  iNaturalist zadetek prenizko zanesljiv ({score:.0f} %), pošiljam v ročni pregled.")
            return None
        taxon = top.get("taxon") or {}
        return {
            "vrsta": taxon.get("preferred_common_name") or taxon.get("name"),
            "sci": taxon.get("name"),
            "confidence": score,
        }
    except Exception as e:
        print(f"⚠ iNaturalist identifikacija ni uspela, pošiljam v ročni pregled: {e}")
        return None


# ── Vremenski kontekst iz history.json ───────────────────────────────────────

def load_history():
    return json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))


def gdd10_ytd(hist, date_iso, base=GDD_BASE_C):
    year = date_iso[:4]
    total = 0.0
    for d, v in hist.items():
        if not d.startswith(year) or d > date_iso:
            continue
        hi, lo = v.get("tempHigh"), v.get("tempLow")
        if hi is None or lo is None:
            continue
        total += max(0.0, (hi + lo) / 2 - base)
    return round(total, 1)


def climatology_high_for_mmdd(hist, mmdd, exclude_year):
    highs = [v["tempHigh"] for d, v in hist.items()
             if d[5:] == mmdd and not d.startswith(exclude_year) and v.get("tempHigh") is not None]
    return round(sum(highs) / len(highs), 1) if highs else None


def weather_context(hist, date_iso):
    v = hist.get(date_iso) or {}
    normal_high = climatology_high_for_mmdd(hist, date_iso[5:], exclude_year=date_iso[:4])
    ctx = {
        "datum": date_iso,
        "temp_visoka": v.get("tempHigh"),
        "temp_nizka": v.get("tempLow"),
        "padavine_mm": v.get("precipTotal"),
        "vlaga_povp_odstotki": v.get("humidityAvg"),
        "gdd10_letos_do_danes": gdd10_ytd(hist, date_iso),
        "koledarsko_povprecje_visoke_temp": normal_high,
    }
    if v.get("tempHigh") is not None and normal_high is not None:
        diff = round(v["tempHigh"] - normal_high, 1)
        if abs(diff) >= 2:
            ctx["odstopanje_od_povprecja"] = f"{'+' if diff > 0 else ''}{diff} °C od koledarskega povprečja za ta dan"
    return ctx


# ── Katalog data/makro.json ──────────────────────────────────────────────────

def load_catalog():
    try:
        return json.load(open(CATALOG_FILE, encoding="utf-8"))
    except Exception:
        return {"updated": None, "species": []}


def save_catalog(cat):
    cat["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    json.dump(cat, open(CATALOG_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(CATALOG_FILE, "a", encoding="utf-8").write("\n")


def slugify(text):
    t = text.lower().strip()
    for a, b in (("č", "c"), ("š", "s"), ("ž", "z"), ("ć", "c"), ("đ", "d")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:60].rstrip("-")


def find_species_entry(cat, slug):
    for sp in cat["species"]:
        if sp["slug"] == slug:
            return sp
    return None


def invasive_link_for(vrsta, sci):
    """Če je vrsta na seznamu invazivk (data/invasive_species.json -- isti vir
    kot tools/invasive_watch.py), poveže na /invazivke/ -- interno linkanje iz
    Korak 6. Ujemanje po znanstvenem ALI slovenskem imenu (case-insensitive)."""
    try:
        cfg = json.load(open(os.path.join(ROOT, "data", "invasive_species.json"), encoding="utf-8"))
    except Exception:
        return None
    sci_l, vrsta_l = (sci or "").lower(), (vrsta or "").lower()
    for sp in cfg.get("species", []):
        if (sci_l and sp.get("sci", "").lower() == sci_l) or (vrsta_l and sp.get("sl", "").lower() == vrsta_l):
            return "/invazivke/"
    return None


# ── Slika: EXIF-orientacija popravljena, pomanjšana kopija za splet ─────────

def save_web_photo(src_path, slug, date_iso):
    dest_dir = os.path.join(ROOT, "img", "makro", slug)
    os.makedirs(dest_dir, exist_ok=True)
    ext = ".jpg"
    dest_name = f"{date_iso}{ext}"
    dest_path = os.path.join(dest_dir, dest_name)
    # Če ista vrsta že ima fotko za ta datum (dve fotke isti dan), dodaj indeks.
    i = 2
    while os.path.exists(dest_path):
        dest_name = f"{date_iso}-{i}{ext}"
        dest_path = os.path.join(dest_dir, dest_name)
        i += 1

    img = Image.open(src_path)
    img = ImageOps.exif_transpose(img)  # popravi rotacijo, EXIF se pri save() itak ne prenese naprej
    img = img.convert("RGB")
    max_w = 1600
    if img.width > max_w:
        new_h = round(img.height * max_w / img.width)
        img = img.resize((max_w, new_h), Image.LANCZOS)
    img.save(dest_path, "JPEG", quality=85)
    return f"/img/makro/{slug}/{dest_name}", img.width, img.height


# ── Claude: naravoslovni opis + ločen vremenski blok, nato lektura ──────────

SYSTEM_PROMPT = """Si urednik osebnega makro-fotografskega arhiva na meteorec.si (osebna vremenska
postaja IREICA1, Rečica ob Savinji, Zgornja Savinjska dolina, Slovenija). Filip Eremita fotografira
žuželke (kasneje morda gobe/rastline) v okolici postaje in za vsako fotografijo napiše kratek
naravoslovni zapis, povezan z vremenskim kontekstom dneva opažanja.

STROGA PRAVILA:
- Naravoslovni del (habitat, videz, vedenje, taksonomija) naj temelji na splošno znanih, preverljivih
  dejstvih o vrsti. Če česa nisi prepričan, formuliraj splošneje ali izpusti -- NIČESAR ne izmišljuj
  (ne natančnih številk, ne citatov, ne trditev, ki jih ne bi znal utemeljiti).
- Vremenski kontekst (temperatura, GDD, primerjava s povprečjem) uporabi SAMO iz podanega bloka
  `vremenski_kontekst` -- to je izmerjen, preverjen vir, ne mešaj vanj ugibanj. Nameni mu ločeno
  polje `weather_note`, ne razpršuj vremenskih trditev po naravoslovnih odsekih.
- Naraven uredniški slovenski ton, brez pretirane formalnosti, brez klišejev, osebna perspektiva
  (Filipovo opažanje, ne enciklopedijski članek).
- SKUPAJ 250-450 besed v lead + paragraphs poljih -- kratek osebni zapis, ne dolg članek.
- Naslov po vzorcu "[Vrsta]: [kratek vremenski/sezonski hook]".
- Vrni SAMO veljaven JSON (brez markdown fence, brez dodatnega besedila) v tej shemi:
{
  "title": "...",
  "meta_description": "150-160 znakov",
  "alt_text": "opisen alt-text za fotografijo (kaj je na sliki, ne 'fotografija ...'), do 120 znakov",
  "tags": ["...", "makro"],
  "og_accent_hex": "#rrggbb",
  "lead": "uvodni odstavek, 2-3 povedi",
  "sections": [
    {"label": "01 — kratek naslov odseka", "heading": "H2 naslov", "id": "kebab-case-id",
     "paragraphs": ["odstavek"]}
  ],
  "weather_note": "1-2 povedi, ki povežeta TO opažanje z vremenskim kontekstom dneva",
  "sources_note": "en stavek o virih (lastno opažanje Filipa Eremite, splošno znanje o vrsti, IREICA1 za vremenske podatke)"
}
2-3 odseki v sections (npr. prepoznavanje/videz, habitat, vedenje/življenjski cikel)."""


def call_claude_makro(meta, weather_ctx, extra_context):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY manjka.")

    context = {
        "vrsta": meta["vrsta"],
        "znanstveno_ime": meta.get("sci") or None,
        "filipova_opomba": meta.get("opomba") or None,
        "datum_opazanja": meta["datum"],
        "lokacija": meta["location_label"],
        "vremenski_kontekst": weather_ctx,
        **extra_context,
    }
    user_prompt = ("Podatki za zapis o novem makro opažanju:\n"
                   + json.dumps(context, ensure_ascii=False, indent=2)
                   + "\n\nNapiši zapis za meteorec.si/makro/ po sistemskih navodilih.")

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4000,
        "thinking": {"type": "disabled"},
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        text = stream_claude(payload, api_key)
    except urllib.error.HTTPError as e:
        sys.exit(f"Claude API napaka {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
    except (TimeoutError, urllib.error.URLError) as e:
        sys.exit(f"Claude API klic ni uspel (timeout/omrežje): {e}")
    except RuntimeError as e:
        sys.exit(str(e))

    if not text:
        sys.exit("Claude ni vrnil besedila.")
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(cleaned)


# ── HTML stran za eno vrsto (/makro/<slug>/) ────────────────────────────────

EXTRA_STYLE = '''<style>
.mk-hero{margin:.4rem 0 1.6rem}
.mk-hero img{display:block;width:100%;height:auto;border-radius:16px;border:1px solid var(--card-border)}
.mk-log{margin:1.6rem 0 0;padding:0;list-style:none}
.mk-log li{display:flex;gap:.8rem;align-items:center;padding:.6rem 0;border-bottom:1px solid var(--border)}
.mk-log li:last-child{border-bottom:0}
.mk-log img{width:56px;height:56px;object-fit:cover;border-radius:10px;border:1px solid var(--card-border);flex:none}
.mk-log .mk-log-meta{font-size:.85rem;color:var(--muted)}
</style>'''


def build_sections_html(sections):
    parts = []
    for s in sections:
        paras = "\n".join(f"    <p>{p}</p>" for p in s["paragraphs"])
        parts.append(f'    <span class="section-label">{s["label"]}</span>\n'
                      f'    <h2 id="{s["id"]}">{s["heading"]}</h2>\n{paras}')
    return "\n\n".join(parts)


def build_species_page(sp, article, sighting, w, h):
    slug = sp["slug"]
    url = sp["url"]
    title = article["title"]
    desc = article["meta_description"]
    date_str = seo.fmtd(sighting["date"])

    wc = sighting.get("weather") or {}
    stat_rows = []
    if sp.get("sci"):
        stat_rows.append(("Znanstveno ime", f'<em>{sp["sci"]}</em>'))
    stat_rows.append(("Datum opažanja", date_str))
    if wc.get("temp_visoka") is not None:
        lo_txt = f'{wc["temp_nizka"]:.1f} °C' if wc.get("temp_nizka") is not None else "—"
        stat_rows.append(("Temperatura", f'{wc["temp_visoka"]:.1f} °C / {lo_txt}'))
    if wc.get("padavine_mm") is not None:
        stat_rows.append(("Padavine ta dan", f'{wc["padavine_mm"]:.1f} mm'))
    if wc.get("gdd10_letos_do_danes") is not None:
        cmp_txt = ""
        if wc.get("koledarsko_povprecje_visoke_temp") is not None:
            cmp_txt = f' (koledarsko povprečje: {wc["koledarsko_povprecje_visoke_temp"]:.1f} °C)'
        stat_rows.append(("GDD₁₀ letos do tega dne", f'{wc["gdd10_letos_do_danes"]:.0f}{cmp_txt}'))
    rows_html = "\n".join(f"      <tr><th>{k}</th><td>{v}</td></tr>" for k, v in stat_rows)

    sections_html = build_sections_html(article["sections"])

    weather_note_html = ""
    if article.get("weather_note"):
        weather_note_html = (f'\n    <div class="callout">\n'
                              f'      <p><strong>Vremenski kontekst:</strong> {article["weather_note"]}</p>\n'
                              f'    </div>\n')

    link_html = ""
    if sp.get("invasive_link"):
        link_html = (f'\n    <p style="color:var(--muted);font-size:.9rem">Ta vrsta je tudi na seznamu '
                      f'invazivnih vrst v dolini — <a href="{sp["invasive_link"]}" style="color:var(--blue)">'
                      f'poglej razširjenost na /invazivke/</a>.</p>\n')

    log_items = []
    for s in reversed(sp["sightings"]):
        log_items.append(
            f'    <li><img src="{s["photo"]}" alt="" loading="lazy">'
            f'<span class="mk-log-meta">{seo.fmtd(s["date"])}'
            f'{" · " + s["location_label"] if s.get("location_label") else ""}</span></li>'
        )
    log_html = ""
    if len(sp["sightings"]) > 1:
        log_html = (f'\n    <h2 id="dnevnik-opazanj">Dnevnik opažanj — {sp["sl"]}</h2>\n'
                     f'    <ul class="mk-log">\n' + "\n".join(log_items) + "\n    </ul>\n")

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Makro arhiv", "/makro/"), (sp["sl"], None)])}
  <article>
    <div class="stn-badge"><span></span> Makro arhiv · IREICA1 · Rečica ob Savinji</div>
    <h1>{title}</h1>
    <p class="post-meta">{date_str} · Filip Eremita · {sighting.get("location_label", DEFAULT_LOCATION_LABEL)}</p>

    <figure class="mk-hero">
      <img src="{sighting["photo"]}" alt="{html.escape(article["alt_text"])}" width="{w}" height="{h}" loading="eager">
    </figure>

    <p class="lead">{article["lead"]}</p>

    <table class="stats">
{rows_html}
    </table>

{sections_html}
{weather_note_html}{link_html}
    <p style="color:var(--muted);font-size:.9rem;margin-top:2rem">{article["sources_note"]}</p>
{log_html}
    <a class="back-link" href="/makro/">← Vse vrste v makro arhivu</a>
  </article>'''

    head_extras = (EXTRA_STYLE + "\n" + seo.crumbs_schema([("Meteorec", "/"), ("Makro arhiv", "/makro/"), (sp["sl"], None)])
                   + "\n" + seo.webpage_schema(url, title, desc, date_published=sighting["date"],
                                                image=f"{SITE}{sighting['photo']}"))
    page_html = seo.page_shell(title, desc, url, head_extras, body, og_image=f"{SITE}{sighting['photo']}")
    rel_path = url.lstrip("/") + "index.html"  # url je že "/makro/<slug>/" -- ne podvajaj "makro/"
    seo.write_page(rel_path, page_html, force=True)
    print(f"✓ zapisano: {rel_path}")


# ── Glavni tok ────────────────────────────────────────────────────────────

def main():
    wire = "--wire" in sys.argv
    dry_run = "--dry-run" in sys.argv

    os.makedirs(PUBLISHED_DIR, exist_ok=True)
    os.makedirs(REVIEW_DIR, exist_ok=True)

    queue = queue_files()
    if not queue:
        print("Nabiralnik makro-inbox/ je prazen — nič za objaviti danes.")
        return

    hist = load_history()
    cat = load_catalog()
    published = False

    for fname in queue:
        photo_path = os.path.join(INBOX, fname)
        meta = resolve_metadata(photo_path)
        print(f"→ obravnavam {fname} (datum {meta['datum']}, vrsta: {meta['vrsta'] or '(neznana)'})")

        if not meta["vrsta"]:
            guess = identify_species(photo_path, meta["lat"], meta["lon"], meta["datum"])
            if guess:
                meta["vrsta"], meta["sci"] = guess["vrsta"], guess["sci"] or meta["sci"]
                print(f"  ✓ iNaturalist predlog: {meta['vrsta']} ({guess['confidence']:.0f} %)")
            else:
                if dry_run:
                    print("  (--dry-run) vrsta ni določena — šlo bi v makro-inbox/pregled/ za ročni vpis.")
                    continue
                dest = os.path.join(REVIEW_DIR, fname)
                sc_src, sc_dest = sidecar_path(photo_path), sidecar_path(dest)
                shutil.move(photo_path, dest)
                if os.path.isfile(sc_src):
                    shutil.move(sc_src, sc_dest)
                print("  ⚠ vrsta ni določena — premaknjeno v makro-inbox/pregled/ za ročni vpis.")
                continue

        # Prva fotka v vrsti, ki ima znano vrsto -- objavimo TO (queue red se
        # sicer ohranja po datumu v imenu, torej "en na dan" v praksi pomeni
        # najstarejšo že identificirano fotko).
        slug = slugify(meta["vrsta"])
        sp = find_species_entry(cat, slug)
        is_first_this_year = not sp or not any(s["date"].startswith(meta["datum"][:4]) for s in sp["sightings"])

        wctx = weather_context(hist, meta["datum"])
        extra_context = {
            "prejsnja_opazanja_te_vrste": len(sp["sightings"]) if sp else 0,
            "prvo_letosnje_opazanje": is_first_this_year,
        }

        if dry_run:
            print(f"  (--dry-run) objavil bi vrsto '{meta['vrsta']}' -> /makro/{slug}/")
            return

        print("  Kličem Claude API (osnutek)...")
        draft = call_claude_makro(meta, wctx, extra_context)

        print("  Lektura...")
        review = call_lektor(draft, {"vremenski_kontekst": wctx, "filipova_opomba": meta.get("opomba")})
        if review.get("issues"):
            for i in review["issues"]:
                print(f"   - {i}")
        # call_lektor je splošen (uvožen iz generate_daily_post.py) -- njegov
        # prompt kot ponazoritev sheme navaja POLJA DNEVNEGA ČLANKA
        # (section_label, og_photo, callout), ki jih moja shema nima (ima pa
        # alt_text, weather_note, ki jih dnevni članek nima). Če bi lektor
        # zato kako polje izpustil, padi nazaj na osnutek namesto da stran
        # pade na manjkajočem ključu ali izgubi vsebino.
        corrected = review.get("corrected") or {}
        article = {**draft, **{k: v for k, v in corrected.items() if v not in (None, "", [])}}

        if not wire:
            print(f"\n— Brez --wire: nič ni zapisano/objavljeno. Osnutek za '{meta['vrsta']}':\n"
                  + json.dumps(article, ensure_ascii=False, indent=2))
            return

        photo_url, w, h = save_web_photo(photo_path, slug, meta["datum"])

        sighting = {
            "date": meta["datum"],
            "photo": photo_url,
            "lat": meta["lat"], "lon": meta["lon"],
            "location_label": meta["location_label"],
            "weather": wctx,
            "note": meta.get("opomba") or None,
        }

        if sp is None:
            sp = {
                "slug": slug,
                "sl": meta["vrsta"],
                "sci": meta.get("sci") or None,
                "url": f"/makro/{slug}/",
                "summary": article["meta_description"],
                "cover_photo": photo_url,
                "first_seen": meta["datum"],
                "last_seen": meta["datum"],
                "og_accent_hex": article.get("og_accent_hex", "#38bdf8"),
                "invasive_link": invasive_link_for(meta["vrsta"], meta.get("sci")),
                "sightings": [sighting],
            }
            cat["species"].append(sp)
        else:
            sp["sci"] = sp.get("sci") or meta.get("sci")
            sp["summary"] = article["meta_description"]
            sp["cover_photo"] = photo_url
            sp["last_seen"] = meta["datum"]
            sp["og_accent_hex"] = article.get("og_accent_hex", sp.get("og_accent_hex", "#38bdf8"))
            sp["sightings"].append(sighting)
            sp["sightings"].sort(key=lambda s: s["date"])

        build_species_page(sp, article, sighting, w, h)

        try:
            from generate_og_images import make_og
            os.environ["DRIVE_PHOTO_PATH"] = photo_path  # ista pot kot fetch_drive_photo -> DRIVE_PHOTO_PATH
            make_og({
                "slug": f"makro-{slug}",
                "title": meta["vrsta"][:40],
                "subtitle": f'Makro arhiv · {seo.fmtd(meta["datum"])}',
                "section": "Makro",
                "accent": hexrgb(article.get("og_accent_hex", "#38bdf8")),
                "photo": "misty-valley",  # rezerva, prepiše jo DRIVE_PHOTO_PATH zgoraj
            })
        except Exception as e:
            print(f"⚠ OG slika preskočena: {e}")

        save_catalog(cat)
        generate_makro_page.build()

        dest = os.path.join(PUBLISHED_DIR, fname)
        sc_src, sc_dest = sidecar_path(photo_path), sidecar_path(dest)
        shutil.move(photo_path, dest)
        if os.path.isfile(sc_src):
            shutil.move(sc_src, sc_dest)

        print(f"✓ objavljeno: /makro/{slug}/ (opažanje {meta['datum']})")
        published = True
        break

    if not published:
        print("Nobena fotka v nabiralniku ni imela (ali dobila) določene vrste — nič ni bilo objavljeno danes.")


if __name__ == "__main__":
    main()
