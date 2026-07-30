# Meteorec — navodila za delo z blogom

## NIKOLI ne objavljaj meritev iz hiše

Postaja poleg zunanjih meri tudi **notranjo temperaturo in vlago**. To je
Filipova zasebna stvar in ne gre ven — ne v članek, ne na stran, ne v
objavo na FB/IG. Nobene izjeme.

Kje je to zarezano (če dodajaš nov vir ali odjemalca, zareži tudi tam):

- `worker.js`, `/ecowitt-current` — blok `indoor` se izbriše pri viru, tako
  da ga noben odjemalec sploh ne dobi.
- `tools/generate_daily_post.py`, `fetch_current()` — blok se izbriše še
  enkrat, ker gre cel odgovor v `call_claude()` kot `trenutne_razmere` in bi
  model o njem pisal, če bi ga videl.
- `app.js`, Ecowitt kartica — notranjih meritev ne prikazuje.

Zgodilo se je 30. 7. 2026: dnevni članek je objavil notranjo temperaturo in
občuteno temperaturo v hiši, ker je surov Ecowitt odgovor romal naravnost v
model. Odstavek je odstranjen, obe zarezi sta postavljeni.

## Lektura je OBVEZNA za vsak članek

Vsak blog članek — ne glede na to, ali ga generira avtomatika ali je napisan
ročno v seji — mora pred koncem dela skozi lekturo:

- Samodejni članki (dnevni, mesečni, storm-watch): lektura je vgrajena v
  `tools/generate_daily_post.py` (`call_lektor`).
- Ročno napisani ali naknadno urejeni članki: po objavi na `main` obvezno
  poženi workflow **"Lektura obstoječih objav"** (`lektura.yml`) z inputom
  `slugs=<slug članka>`. Workflow popravke sam commita na `main`.

Lektor preverja slovnico, slog, interno konsistentnost in — posebej pomembno —
anglicizme/kalke (dobesedni prevodi, prekomerni trpnik, angleški narekovaji,
vezaj namesto pomišljaja).

## Objava člankov

- Vse izpeljane datoteke (blog.json, blog/index.html, sitemap.xml,
  blog/rss.xml, blog/tema/*, blog/related.json, OG slika) ureja
  `wire_all()` iz `tools/generate_monthly_post.py` — nikoli ročno.
- Po objavi na `main` pošlji IndexNow ping (glej korak v `daily-post.yml`).
- Dnevni članki gredo prek sistema jutranjih predlogov: cron pripravi tri
  predloge, Filip po e-pošti izbere, klik sproži objavo (`daily-post.yml`).

## Objava na Facebook in Instagram

Vsak nov članek, ki ga `wire_all()` zapiše v `blog.json`, se samodejno objavi
tudi na FB strani in IG računu Meteorec — vklopljeno v vseh petih
objavljalnih workflowih (`daily-post.yml`, `monthly-post.yml`,
`storm-watch.yml`, `arso-newsjack.yml`, `invasive-watch.yml`), kot zadnja
koraka po uspešnem push-u na `main` (`continue-on-error: true`, da napaka na
FB/IG ne podre objave članka).

- **`tools/post_to_facebook.py`** — Graph API, najprej `/photos` (OG slika +
  caption + link), ob napaki fallback na `/feed` (samo link). Besedilo objave
  je prilagojeno tipu članka glede na predpono sluga (glej `PREFIXES` v
  skripti).
- **`tools/post_to_instagram.py`** — Instagram Graph API, dvostopenjsko
  (`/media` container → `/media_publish`). Uporablja isto OG sliko.
- **`tools/fb_comments.py`** — ROČNO orodje (ni v nobenem workflowu) za
  pregled/odgovarjanje na FB komentarje: `list [--unanswered-only]`,
  `reply <comment_id> "besedilo"`.
- **`tools/fb_page_stats.py`** — ročno orodje za pregled odziva (samo
  deljenja — všečki/komentarji niso dostopni brez polnega Meta App Review).
- **`.github/workflows/social-repost.yml`** — ročni workflow_dispatch za
  (re)objavo poljubnega članka po slugu (prazno = zadnji), uporaben tudi za
  end-to-end test secretov.

Potrebni GitHub Secrets: `FB_PAGE_ID`, `FB_PAGE_TOKEN` (trajni Page Access
Token — Meta app "Meteorec", App ID 4757580174464018), `IG_ACCOUNT_ID`,
`IG_ACCESS_TOKEN` (Instagram Business Login token, ~60 dni, ročno se osveži
prek `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=<trenutni>`
— brez app secreta).

**Pozor:** FB Page Token se lahko nepričakovano invalidira ("session
invalidated" napaka), če se na Facebook računu zgodi karkoli, kar sproži
varnostno ponastavitev seje (npr. prijave v nova zasebna okna/naprave). Če
`post_to_facebook.py` odpove z OAuthException code 190, je treba token
ponovno generirati prek Graph API Explorerja (isti postopek kot za prvotno
nastavitev — glej git zgodovino za natančen tok).

## Razvoj

- Razvoj na seji veji, merge v `main` prek PR; `main` je produkcija
  (GitHub Pages + auto-deploy Cloudflare workerja ob spremembi worker.js).
