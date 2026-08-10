# SEO sistem — meteorec.si

Ta stran dokumentira **sistem**, ne posamezen cikel — za sezonski/vsebinski
plan glej `docs/seo-plan-2026-07.md` (datiran primer takega cikla). Zgled za
obliko tega dokumenta: `docs/model-recica.md`.

```
history.json ──────────┬─▶ seo_smart_routine.py ──▶ /klima/ /padavine/
                        │      (dnevno, 01:45 UTC)     /temperatura/ /teden/
                        │                              /novosti/<slug>/
                        │                              sitemap-seo.xml
                        │
                        ├─▶ generate_seo_pages.py ───▶ /vreme/YYYY/MM/DD/
                        │      (dnevno, 04:00 UTC)     /rekord/ /pojavi/ sezone
                        │                              sitemap-weather.xml
                        │
blog.json ──────────────┴─▶ generate_monthly_post.py ─▶ sitemap.xml, blog/index.html,
                             wire_all()                  blog/tema/*, blog/rss.xml,
                             (ob vsaki objavi)            blog/related.json, OG slika

sitemap.xml + sitemap-seo.xml + sitemap-weather.xml ──▶ seo_audit.py ──▶ poroča vrzeli,
                                    (tedensko, ned 04:40 UTC, --fix)      --fix jih zapre

push na main (*.html, sitemap.xml) ──▶ indexnow.yml ──▶ IndexNow ping
```

## Trije sitemapi

Vsi trije so navedeni v `robots.txt`. Nobenega se ne ureja ročno — vsak ima
svojega lastnika:

| Sitemap | Vsebuje | Ureja |
|---|---|---|
| `sitemap.xml` | domača, `/blog/`, ključne hub strani, vsaka blog objava, `blog/tema/<tag>/` | `rewrite_sitemap_and_index()` v `generate_monthly_post.py` (prek `wire_all()`); aditivno popravlja tudi `seo_audit.py --fix` |
| `sitemap-weather.xml` | programatski arhiv (`/vreme/YYYY/MM/DD/`, sezone, `/pojavi/*`, `/slovar/*`) | `generate_seo_pages.py` |
| `sitemap-seo.xml` | hub strani (`/klima/`, `/padavine/`, `/temperatura/`, `/teden/`) + `/novosti/<slug>/` dogodkovne strani | `seo_smart_routine.py` |

`robots.txt` blokira `/zasebnost.html`, `/blog.json`, `/docs/`; izrecno
dovoljuje `history.json` (CC BY 4.0 dataset, glej `o-postaji.html`).

## `seo_smart_routine.py` — hub in dogodkovne strani

Dnevno (`.github/workflows/seo-smart-routine.yml`, `45 1 * * *`, po
`update-history.yml` ob 01:15, pred `generate-seo-pages.yml` ob 04:00):

1. **Klimatološke norme** iz cele `history.json` (`compute_climate()`) →
   `/klima/`, `/padavine/`, `/temperatura/` (mesečna povprečja, absolutni
   rekordi, letni trendi, FAQPage JSON-LD za dolgi rep poizvedb tipa "kdaj je
   v Rečici ob Savinji najtopleje").
2. **`/teden/`** — zadnjih 7 polnih dni proti klimatološkemu povprečju.
3. **Zaznava dogodkov** (`detect_events`, `detect_heat_waves`,
   `detect_droughts`, zadnjih 14–30 dni): novi absolutni rekordi, rekord za
   koledarski dan, sezonska prva (zmrzal, vroč dan), toplotni valovi (3+ dni
   ≥ 30 °C), sušna obdobja (7+ dni < 1 mm) → vsak dobi stran pod
   `/novosti/<slug>/` (generira se **enkrat**, `gen_event_page(..., force=False)`
   — kasnejši teki je ne prepišejo) in vnos v `novosti.json` (trajni katalog,
   `load_novosti_catalog()`/`save_novosti_catalog()`, brez duplikatov po
   `slug`).
4. Zapiše `sitemap-seo.xml`, pingne IndexNow za nove/spremenjene URL-je.

Vse HTML gradnike (header, footer, mobilni bottom-nav, JSON-LD helperji za
`WebPage`/`BreadcrumbList`/`FAQPage`/`Dataset`/`NewsArticle`) ta datoteka
namenoma podvaja iz `generate_seo_pages.py`, namesto da bi jih delila prek
uvoza — edina izjema je `seo_title()` (glej spodaj), ki jo obe uvažata iz
`generate_monthly_post.py`. Isto načelo kot drugod v repozitoriju:
generatorji strani so samostojni.

## `seo_audit.py` — tedenski nadzor pokritosti

Tedensko (`.github/workflows/seo-audit.yml`, ned `40 4 * * 0`, `--fix`):

- **`CORE`** (slovar na vrhu datoteke) — seznam ključnih strani, ki MORAJO
  biti v vsaj enem sitemapu. Nova hub stran (npr. nov `generate_*_page.py`)
  sodi sem, sicer jo audit ne ujame, če pade iz sitemapa.
- Preveri, da je vsaka `blog.json` objava v `sitemap.xml`.
- Preveri, da v `sitemap.xml` ni mrtvih povezav (`<loc>` brez ustrezne
  datoteke).
- On-page pregled vzorca strani (`ONPAGE_SAMPLE`): `<title>`, meta
  description, canonical, `og:image`, JSON-LD prisotnost (samo prisotnost,
  ne vsebinska pravilnost).
- `--fix` aditivno doda manjkajoče vnose v `sitemap.xml` in osveži `<lastmod>`
  domače strani in `/blog/` na datum zadnje objave. **Nikoli ne odstrani ali
  prerazporedi** obstoječih vnosov. Brez `--fix` samo poroča (izhodni status
  1 ob napakah — teden dni po uvedbi je to ujelo vrzel pri `/trendi/`, ki
  dolgo ni bil v nobenem sitemapu).

## `seo_title()` — edina deljena SEO funkcija

`generate_monthly_post.py`, uvožena v `generate_seo_pages.py` in
`seo_smart_routine.py`. Skrajša **samo `<title>` tag** na 60 znakov (Google
sicer odreže, Semrush javi "too much text"); h1/og:title/JSON-LD
headline/`blog.json` title pusti nedotaknjene, ker gredo tudi na FB/IG.
Podrobno pravilo je v `CLAUDE.md` (`### <title> ne sme čez 60 znakov`) — nov
generator strani mora to funkcijo uvoziti, ne podvajati.

## IndexNow

Ključ `d4e7a1b3c9f2e5d8a0b6c3f7e2d1a4b9` — datoteka
`d4e7a1b3c9f2e5d8a0b6c3f7e2d1a4b9.txt` v korenu, isti niz je trdo zapisan v
`.github/workflows/indexnow.yml` in v `seo_smart_routine.py`
(`INDEXNOW_KEY`). Pingano iz štirih mest:

- `indexnow.yml` — ob vsakem push na `main`, ki dotakne `*.html`,
  `blog/*.html` ali `sitemap.xml`; diffa `HEAD~1..HEAD` in vedno doda
  `sitemap.xml`.
- `seo_smart_routine.py` — za svoje nove/spremenjene hub in `/novosti/` strani.
- `seo-audit.yml` — samo če je `--fix` dejansko spremenil `sitemap.xml`.
- `monthly-post.yml` — poseben korak ob mesečni objavi.

## JSON-LD po straneh

- Blog objave: `BlogPosting` + `BreadcrumbList`.
- Domača stran: en `@graph` z `WebSite`, `WebPage` (+ `speakable`),
  `ImageObject`, `Organization`, `Person`, kombiniran
  `["LocalBusiness","DataCatalog"]` z naslovom/geo.
- `seo_smart_routine.py` hub/dogodkovne strani: `WebPage`, `BreadcrumbList`,
  `Dataset` (klima/padavine), `FAQPage` (klima/padavine).
- Tag strani (`blog/tema/*`): `CollectionPage` + `BreadcrumbList`.

Vse `Place`-sheme uporabljajo preverjen Wikidata entity Q969326 (naselje, ne
občina) — `RECICA_SAMEAS` v `seo_smart_routine.py`.

## Kaj (namerno) manjka

- **Ni programske GSC/Bing Webmaster integracije.** Vse omembe "Search
  Console" v kodi so komentarji ali ročna navodila Filipu (prijava, pregled
  Coverage/Pages) — ni service-account ključa, ni API klica. Impresije/CTR se
  spremljajo ročno.
- `sitemap-index.xml` namesto treh ločenih sitemapov v `robots.txt` — omenjeno
  kot ideja v `docs/seo-plan-2026-07.md` §7, ni izvedeno.
- `Dataset` shema za `/vreme/` arhivske strani (samo hub strani jo imajo) —
  isti backlog.

## Vzdrževanje

- Nova hub/programatska stran → dodaj v `CORE` v `seo_audit.py`, sicer audit
  ne zazna, če izpade iz sitemapa.
- Nov generator strani → `seo_title()` uvozi iz `generate_monthly_post.py`,
  HTML/JSON-LD gradnike po vzoru obstoječih (ne deli kode med generatorji,
  glej zgoraj).
- `novosti.json` se ne ureja ročno — nastane in raste samo iz
  `seo_smart_routine.py`; posamezna `/novosti/<slug>/` stran se, ko je enkrat
  zapisana, ne prepiše več (glej `gen_event_page(..., force=False)`).
- Notranje meritve (`indoor` blok) v to cev nikoli ne pridejo — glej
  `CLAUDE.md`, razdelek "NIKOLI ne objavljaj meritev iz hiše"; ta cev tako
  ali tako bere samo `history.json` in generirane strani, ne surovega
  Ecowitt odgovora.
