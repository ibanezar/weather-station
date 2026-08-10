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
- `tools/generate_story_card.py`, `fetch_current()` — blok se izbriše, ker gre
  kartica na FB/IG zgodbe; na njej sme biti samo zunanja temperatura.

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

### `<title>` ne sme čez 60 znakov

Google daljše naslove odreže, Semrush javi »too much text within the title
tags«. Zato gre vsak `<title>` skozi `seo_title()` iz
`tools/generate_monthly_post.py` — **novi predlogi in generatorji naj ga
uporabijo enako** (`<title>{seo_title(title)}</title>`, drugi argument je
pripona, npr. `" | Meteorec, Rečica ob Savinji"`).

Funkcija skrajša **samo title tag** — naslov članka (h1, `og:title`, JSON-LD,
`blog.json`) pusti nedotaknjen, ker se ta objavlja tudi na FB/IG in ga lektor
po pravilu ne spreminja. Vzame najbogatejšo različico naslova, ki se še
prilega (cel naslov → brez oklepajskega dodatka → do dvopičja/pomišljaja), in
pripono doda le, če po tem ostane pod mejo.

Modelu je meja 60 znakov povedana že v pozivu (`generate_daily_post.py` in
`generate_daily_proposals.py`), tako da so naslovi praviloma dovolj kratki že
ob nastanku; `seo_title()` je varovalka za ostalo.

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

### Dnevna zgodba (story) ob 6:00

Poleg objav ob člankih gre vsak dan zjutraj ven še kartica v formatu zgodbe
(1080×1920) — `.github/workflows/daily-story.yml`.

- `tools/generate_story_card.py` ima ~24 tem (registrator `@topic(ime,
  prioriteta)`, seznam `TOPICS`), vsaka s 5+ besedilnimi različicami (skupaj
  čez 100 — `python3 tools/generate_story_card.py --list-topics` izpiše
  natančno število). Vsaka tema je funkcija `t_*(ctx)`, ki vrne kartico ali
  `None`, če danes ne velja (npr. FROST rabi `tmin<=0`); izmed upravičenih
  zmaga tista z najvišjo prioriteto (zmrzal/sneg/nevihta pred splošnim
  povzetkom). Besedilna različica se izbere determinístično po datumu
  (`hashlib.sha256(datum|ime_teme)`), da je isti dan vedno ista, drug dan pa
  praviloma drugačna. Podatkovni viri: napoved + UV/veter/sončni vzhod
  (Open-Meteo), ARSO, kakovost zraka + cvetni prah (Open-Meteo air-quality),
  gobarski indeks (`gobarska-napoved/index.json`) in `history.json` (rekordi,
  primerjava z včeraj, suh niz). Zapiše `og/story/<datum>.jpg` +
  `og/story/latest.json`, stare kartice (>14 dni) pobriše sam.
- Nova tema gre v isto datoteko: funkcija `t_ime(ctx)` z `@topic("IME",
  prioriteta)`, vrne `card(...)` ali `None`. **Ne uvažaj** modelov iz drugih
  generatorjev (npr. `gobe_model.py`) — ta skript bere samo že objavljene,
  committane JSON-e (isto načelo kot drugod v repozitoriju: generatorji strani
  so samostojni, ne si delijo knjižnic).
- Padavinska številka ARSO in verjetnost Open-Meteo sta na kartici **označeni z
  virom** in se ne zlivata v eno število — ta dva vira se pri padavinah pogosto
  močno razideta.
- Dolga vrednost v statistiki (npr. ime gobje vrste) se v `render()` skrajša
  (`fit_value_text()`) — brez tega pade čez oznako na levi, ker se je prej
  merilo proti celotni širini vrstice namesto proti prostoru, ki ga oznaka
  pusti.
- Objavita `tools/post_story_to_facebook.py` (`/photos?published=false` →
  `/photo_stories`) in `tools/post_story_to_instagram.py`
  (`media_type=STORIES` → `/media_publish`). Zgodbe nimajo podpisa — vse mora
  biti na sliki. Uporabljata iste secrete kot objave člankov.
- **Termin:** cron teče po UTC, zato sta nastavljena dva (04:00 in 05:00 UTC),
  `tools/story_gate.py` pa spusti skozi samo tistega, ki je pri nas med 6:00 in
  12:00, in poskrbi, da gre zgodba ven enkrat na dan (stanje v
  `tools/.story_state.json`). Tako termin drži poleti in pozimi, prenese pa tudi
  običajno zamudo GitHubovega crona.
- Ker FB/IG sliko poberata prek javnega URL-ja, workflow po push-u počaka, da jo
  GitHub Pages res postreže (do 10 minut), preden objavi.

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

## Preprost ⇄ napredni pogled domače strani

Domača stran ima dve različici, med katerima obiskovalec preklaplja z gumbom
**Prikaz** na vrhu (in s ponudbo na dnu strani):

- **preprosto** — samo trenutno vreme, dnevni povzetek, obeti, radar in
  7-dnevna napoved, večja pisava, brez zavihkov;
- **napredno** — vse, kot doslej.

Kako je narejeno:

- Izbira se hrani v `localStorage` pod `wx-mode`, postavi jo inline skripta v
  `<head>` (kot tema), tako da ob nalaganju ni preskoka. Deljive povezave:
  `?pogled=preprosto` / `?pogled=napredno`.
- **Privzeto je napredno** — brez izbire, brez JS in za pajke se torej ne
  skrije nič. Tega ne obračaj: preprosti pogled skriva večino vsebine in bi
  kot privzetek stran osiromašil tudi za iskalnike.
- Skrivanje je v `style.css` (razdelek »PREPROST ⇄ NAPREDNI POGLED«) po načelu
  **allowlist**: v `#tab-current` ostane vidno samo tisto, kar ima razred
  `simple-keep`. **Nova kartica na domači strani je torej v preprostem pogledu
  samodejno skrita** — če sodi med bistvene, ji dopiši `simple-keep`.
- V `app.js` je logika pri `setWxMode()` / `chooseWxMode()`. Delo, ki polni
  skrite kartice ali drži odprto povezavo (strele, pelod, vremenska umetnost,
  kamere, normale …), je v `init()` ovito v `runAdvancedOnly()` — v vrsto gre
  in se izvede šele ob preklopu na napredni pogled. Novo tako delo dodajaj
  enako.

## MTR — lastni napovedni model (MOS)

**MTR (Meteorec)** je poskusni statistični model za Rečico: vzame Open-Meteo
kot vhod in mu doda popravek za dno doline, naučen na meritvah postaje.
Prikazana različica (»MTR v1« ipd.) se izpelje iz `model_version` — nikjer je
ne zapisuj trdo. Podrobno v `docs/model-recica.md`.

Interni identifikatorji (`meteorec` ključ v `forecast_verification.json`,
imena datotek/funkcij) ostajajo nespremenjeni — MTR je prikazna znamka nad
tem stikom, ne preimenovanje kode.

- `tools/train_recica_mos.py` → `model/recica-mos.json` (koeficienti + izmerjena
  veščina). **Datoteke ne ureja nihče ročno** — nastane samo iz učenja, mesečno
  prek `mos-train.yml` ali ročno.
- `tools/predict_recica_mos.py` → `napoved-modela.json`, teče v
  `forecast-verify.yml` **pred** `verify_forecasts.py`, ki napoved zabeleži kot
  tretji vir na semaforju `/tocnost-napovedi/` — ob ARSO in Open-Meteo, po istem
  merilu. Kartica v `app.js` je `fetchMosForecast()` (+ sparkline
  `drawMosSpark()`).
- Četrti vir na semaforju je **ECMWF AIFS** (`models=ecmwf_aifs025_single` prek
  Open-Meteo) — AI model, ki ga Windy prikazuje kot 15-dnevni podaljšek modela
  ECMWF. Edini vir tu z arhivom preteklih napovedi, zato ga
  `tools/backfill_aifs_verification.py` napolni tudi za nazaj; isti skript v
  workflowu zapolni dneve, ki bi viru ušli. Ločljivost 0,25° pomeni, da doline
  ne vidi — na semaforju je zato pošteno, a slabo, in tako je tudi povedano.
- Značilke gradi ena sama funkcija (`train_recica_mos.daily_features`), ki jo
  napovedovalnik uvozi. **Ne podvajaj je** — dva prepisa se razideta in model
  tiho dobiva druge vhode, kot jih pozna.
- Model se uči **samo** iz `history.json` in Open-Meteo. Nobenih notranjih
  meritev; datoteka `all_Rečiškapstaja(...).xlsx` ima stolpce `Indoor` in se v
  tem cevovodu ne uporablja.

## Razvoj

- Razvoj na seji veji, merge v `main` prek PR; `main` je produkcija
  (GitHub Pages + auto-deploy Cloudflare workerja ob spremembi worker.js).
