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

`tools/lektor_existing_posts.py` po dejansko apliciranih popravkih zapiše tudi
`dateModified` v JSON-LD in `updated` v `blog.json` (prek `touch_existing()`) —
prej je lektura besedilo spremenila, shema pa je še naprej trdila, da je stran
nespremenjena od objave (najdeno pri GEO pregledu, popravljeno 2. 9. 2026).

## Objava člankov

- Vse izpeljane datoteke (blog.json, blog/index.html, sitemap.xml,
  blog/rss.xml, blog/tema/*, blog/related.json, OG slika) ureja
  `wire_all()` iz `tools/generate_monthly_post.py` — nikoli ročno.
- **Fiksni del `sitemap.xml` je `CORE` iz `tools/seo_audit.py`** — ne seznam v
  `rewrite_sitemap_and_index()`. Seznama sta bila nekoč dva in sta se razšla:
  podstrani gobarske napovedi so bile samo v `CORE`, zato jih je vsaka objava
  članka (ki sitemap prepiše na novo) pobrisala, nedeljski `seo-audit.yml` pa
  vrnil — 13 strani je bilo večino dni v nobenem sitemapu. Popravljeno
  17. 8. 2026; **ne uvajaj drugega seznama ključnih strani**.
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
- **`tools/short_links.py`** — kratke povezave `meteorec.si/i/<koda>`.
  Instagram povezave **nikjer** ne naredi klikabilne (ne v podpisu, ne v
  komentarju; API ne pozna nalepke s povezavo v zgodbah) — klikabilna je samo
  povezava v bio. Bralec jo mora pretipkati, zato gre v prvi komentar kratka
  koda in ne polni URL članka (čez 70 znakov). Strani `i/<koda>.html` (meta
  refresh + canonical + `noindex`) in preslikavo `i/index.json` piše
  `wire_all()` — **izpeljano, ročno se ne ureja**; `--backfill` naredi kode za
  vse članke iz `blog.json`. Koda je izpeljana iz sluga (sha256) in se ob trku
  podaljša, zato je merodajen `i/index.json` (`lookup()`), ne izračun. Objavljena
  koda se ne spreminja. V sitemap preusmeritve ne gredo. Facebook povezave
  linkificira sam, zato tam kratke ni.

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

- `tools/generate_story_card.py` ima ~26 tem (registrator `@topic(ime,
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
  15:00, in poskrbi, da gre zgodba ven enkrat na dan (stanje v
  `tools/.story_state.json`). Tako termin drži poleti in pozimi, prenese pa tudi
  zamudo GitHubovega crona — konec avgusta 2026 je ta štiri dni zapored zamujal
  6-12 ur namesto običajne 1-2 uri in okno 6:00-12:00 vsakič zgrešil (nobena
  kartica ni šla ven); okno je bilo zato razširjeno do 15:00.
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

## Statična meritev (WX-STATIC) — dve strani, ne ena

`tools/inject_current_weather.py` piše zadnjo meritev kot **crawlable HTML** med
markerja `<!-- WX-STATIC:START … -->` / `<!-- WX-STATIC:END -->`. Cilji so v
`TARGETS`; trenutno sta dva:

- `index.html` — poleg bloka popravi še junaško kartico, tabelo zadnjih 7 dni in
  dnevni povzetek (to obstaja samo tu);
- `vreme-recica-ob-savinji/index.html` — samo blok, takoj pod `<h1>`.

Zakaj tudi pristajalna stran: »vreme rečica ob savinji« je s ~1 950 prikazi in
pozicijo ~9,5 največja neizkoriščena poizvedba, stran pa je obiskovalca po
trenutno vreme pošiljala na naslovno. Zdaj nanj odgovori sama.

- Sklepni stavek bloka je za vsako stran svoj (`TAIL_*`) — na pristajalni strani
  nad blokom ni žive kartice, zato tam ne sme pisati »posodablja se zgoraj«.
- Besedilo bloka gradita `build_block_history()` / `build_block_live()`.
  `generate_seo_pages.py` prvo **uvozi** (ne prepiše) za rezervni zapis, ki ga
  zapiše ob generiranju strani — dva prepisa bi se razšla.
- Markerja na pristajalno stran zapiše generator; če ju ni, skript javi napako za
  tisto stran in nadaljuje z drugo (izhod 1).
- Osvežujeta `prerender-current.yml` (urno, `--live`) in `generate-seo-pages.yml`
  (takoj po generiranju, da stran ni pol dneva na rezervnem zapisu).
- **Notranjih meritev tu ni** in ne smejo priti — velja pravilo z vrha dokumenta.
- Razred bloka je `CLS_*`: na naslovni strani `wx-static` (v `style.css` namenoma
  vizualno skrit — vrednosti kaže živa kartica), na pristajalni `wx-static wx-now`,
  ker tam žive kartice ni in mora biti viden. **Vidnost mora biti izrecna**: prej je
  bil viden le zato, ker se `style.css` na tej strani ne naloži (nalagajo se
  `fonts.css`, `blog.css`, `vreme.css`) — to je bilo naključje, ne odločitev.

## Opozorila ARSO gredo na `/nevihte/`, ne v blog

Prej je vsako opozorilo ARSO dobilo svojo blog objavo in šlo na FB/IG. GA4
(21. 7. – 17. 8. 2026) pokaže, da jih nihče ni bral: 5 objav, 10 ogledov,
**0 sekund** povprečnega časa branja, v Search Consoleu skupaj en klik. Objave
niso prinesle obiska, so pa redčile blog (12 od 99 objav) in sitemap.

Opozorilo je **stanje, ne novica** — velja nekaj ur in se prekliče. Zato:

- `tools/inject_arso_warnings.py` piše aktivna opozorila med markerja `WX-ARSO`
  na `/nevihte/`; `arso-newsjack.yml` teče vsakih 15 minut in nič ne objavlja.
- Čas preverjanja je v besedilu **samo datum, brez ure** — ura bi ob ciklu 15
  minut delala ~96 commitov na dan, tudi ko se opozorila ne spremenijo.
- 15. člen ZDMHS (navedba vira in časa izdaje ARSO) velja tudi tu — `fmt_issued()`
  in `classify()` sta uvožena iz `generate_arso_newsjack_post.py`, ne podvojena.
- 12 prejšnjih objav je pretvorjenih v **preusmeritve** na `/nevihte/` (noindex +
  canonical), ne izbrisanih — indeksirani URL-ji se ne smejo sesuti v 404.
- `generate_arso_newsjack_post.py` ostaja v repozitoriju zaradi teh dveh funkcij
  in zgodovine; kot generator objav se ne uporablja več.

## Nevihtna karta Slovenije (WX-STORMMAP)

Vsak dan mora biti do 7:00 zjutraj po naši uri pripravljena nova karta (zahteva
31. 8. 2026, prej je bil termin 10:00) — `tools/generate_storm_map.py` sestavi **lastno**
statično karto nevihtnega potenciala za vso Slovenijo (ne kopija tuje karte,
npr. Neurje.si) in jo `tools/inject_storm_map.py` vgradi med markerja
WX-STORMMAP na `/nevihte/` — isti vzorec kot WX-ARSO zgoraj (rezervni blok v
`generate_nevihte_page.py`, injektor javi napako in konča z 1, če markerjev
ni).

- **Ocena je ista formula kot povsod na strani** — `storm_threat_score()` iz
  `generate_nevihte_page.py` je uvožena, ne podvojena. Mreža točk, obris
  Slovenije in barvna lestvica pa so prepisani iz app.js (`SLO_POLY`,
  `SLO_CITIES`, `buildSloGrid`, `sloScoreColor` — živi zavihek »Lovec na
  nevihte« → karta Slovenije na naslovni strani). JS in Python ne moreta
  deliti iste kode — **če spremeniš eno, spremeni tudi drugo**.
- Ocena na vsaki mrežni točki je **najvišja pričakovana danes** (od zdaj do
  konca dneva), ne trenutna — karta pove, kaj lahko danes pričakuješ.
- Piše `og/storm-map/<datum>.jpg` (1080×1350, feed) in `<datum>-story.jpg`
  (1080×1920, zgodba) + `latest.json` (kazalec + `should_post`). Stare karte
  (>14 dni) pobriše sam, isto kot dnevna zgodba.
- **FB/IG (feed + zgodba, oboje) gresta ven samo, če je nekje v Sloveniji
  danes vsaj ZMERNO** (ocena >= 22) — `should_post` v `latest.json`,
  preverjajo ga `tools/post_storm_map_to_facebook.py`,
  `tools/post_storm_map_to_instagram.py` in workflow sam (za zgodbo). Razlog:
  vsakodnevna objava "brez neviht" bi imela isto usodo kot stare ARSO objave
  (glej razdelek zgoraj — 0 sekund povprečnega časa branja).
- Zgodba gre prek obstoječih `tools/post_story_to_facebook.py` /
  `post_story_to_instagram.py` (sprejmeta URL slike kot argument) — ni
  podvojenega objavljalnika za zgodbe, samo za feed (karta ni blog članek iz
  `blog.json`, zato `tools/post_to_facebook.py`/`post_to_instagram.py` ne
  ustrezata).
- **Termin:** isti dvojni-cron + gate vzorec kot dnevna zgodba
  (`tools/storm_map_gate.py`, okno 6:00–8:00 — trdi rok je 7:00 zjutraj,
  lastno stanje `tools/.storm_map_state.json` — ločeno od `.story_state.json`).
  Če cron zamudi tudi to okno, `nevihte-forecast.yml` vgradi zadnjo znano
  karto, jasno označeno kot staro (glej `tools/inject_storm_map.py`) — raje
  star podatek kot prazna stran.
- Slovenija je širša kot visoka, zato bi sredinjena karta na pokončni zgodbi
  (9:16) pustila velik prazen pas nad/pod njo — `render()` v
  `generate_storm_map.py` zato karto poravna na vrh in prazen prostor pod njo
  (če ga je dovolj) zapolni s seznamom potenciala po mestih namesto praznine.

## Stalno beleženje strel (LightningLogger)

Kartica "Strele v bližini" (`#ltg-list`, `app.js` `connectLightning()`) se poveže
neposredno iz brskalnika na Blitzortung WebSocket (`ws1/ws2/ws7/ws8.blitzortung.org`
— izmenično, ker imata `live.`/`ws.` gostitelja potekla TLS certifikata) in kaže
strele zadnjo uro. To je **klientski prikaz, ne zapis** — deluje samo, dokler ima
kdo stran odprto v naprednem pogledu (`runAdvancedOnly()`), zato ni primerna
osnova za zgodovino (31. 8. 2026: `_ltgRetry` v `connectLightning()` sploh ni bila
deklarirana, zato se povezava nikoli ni vzpostavila — glej git zgodovino; to je
ločena napaka od tega, da klient sam po sebi ne more biti trajen zapisovalnik).

Za trajen zapis skrbi **`LightningLogger`**, Durable Object v `worker.js`:

- Drži lastno, trajno odhodno WebSocket povezavo na isto Blitzortung omrežje
  (ista `_ltgDecode` LZW-dekodirna logika kot v app.js, namerna podvojitev —
  strežnik nima dostopa do klientske kode, isto načelo kot `_smerBesedilo`).
- Vsako strelo znotraj 200 km od postaje (isti obseg kot klientska kartica)
  zapiše v svoj SQLite: surove dogodke (`strikes`, 14 dni, isti rok kot stare
  karte/zgodbe drugod) in trajne dnevne povzetke (`daily` — število + najbližja
  razdalja), isto načelo kot `history.json`.
- **Durable Objecti se zbudijo šele ob prvem dohodnem klicu** — zato obstoječi
  5-minutni cron v `scheduled()` (`_cronKeepLightningAlive`) DO vsakič "prebudi"
  in preveri/obnovi povezavo. Brez tega klica bi DO ostal speč in se nikoli ne
  bi povezal.
- Javno bran prek `GET /strele-zgodovina.json` (`?ur=`, `?dni=`) — ločeno od
  klientske kartice, ki bere neposredno iz svoje WebSocket povezave.
- **Cena:** dokler je odhodna WebSocket povezava odprta, se DO ne more
  hibernirati in se ves čas zaračunava po trajanju (GB-s) — okvirno
  ~10.800 GB-s/dan pri privzetih 128 MB. Brezplačni plan ima 13.000 GB-s/dan
  (zelo tesno), plačljiv (5 $/mesec) ima 400.000 GB-s/mesec vključenih (dovolj
  rezerve). Ob prekoračitvi na brezplačnem planu klici v ta DO preprosto
  odpovedo (ni doplačila) — ločen meter od običajnih Worker zahtev, torej
  ostala stran ostane nedotaknjena. Podrobnosti in vezava v `wrangler.toml`.
- Zaenkrat samo zapisuje — na strani (razen surovega JSON endpointa) še ni
  prikazana zgodovina/statistika. Nova prikazna kartica bi šla v `app.js` po
  istem vzorcu kot obstoječa (`#ltg-list`), z lastnim poizvedovanjem na zgornji
  endpoint namesto na klientsko WebSocket povezavo.

## Napoved na pristajalni strani

`tools/inject_forecast.py` piše 7-dnevno napoved (`WX-FC7`) in napoved po urah
(`WX-FCH`) na `/vreme-recica-ob-savinji/`. Razlog je isti kot pri meritvi:
»vreme rečica ob savinji po urah« in »… 14 dni« sta poizvedbi, na kateri je stran
odgovarjala le z besedilom »napoved je na naslovni strani«.

- **Vira se ne zlivata v eno številko** (isto načelo kot na kartici za zgodbe):
  Open-Meteo pokriva vseh 7 dni, MTR ima **svoj stolpec** in samo dneve, za katere
  je naučen. Ime različice se izpelje iz `model_version` — ne zapisuj ga trdo.
- Ob nedosegljivem Open-Meteo skript pusti staro napoved in konča z 0 — raje malo
  stara napoved kot prazna stran. Brez markerjev javi napako in vrne 1.
- Rezervni zapis (ob generiranju strani) je iz committanega `napoved-modela.json`,
  ker je to edini napovedni vir v repozitoriju.

### `.data-table` / `.table-scroll` živita v `vreme/vreme.css`

Razreda sta bila v uporabi na 12 straneh `/vreme/mesec/*/`, definirana pa v nobenem
CSS — tabele so se izrisovale s privzetim slogom brskalnika, povezave v njih pa v
privzeti modri (kontrast 2,1:1 na temnem ozadju). Popravljeno 17. 8. 2026; isti slog
uporablja napoved. Če dodajaš tabelo na stran, ki nalaga `vreme.css`, uporabi ta
razreda in ne novih.

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

## Sosednja postaja Varpolje (IREICA7) — dolinski dvoboj

Prijatelj iz Varpolja (občina Rečica ob Savinji, ~1,6 km jugozahodno, isto dno
doline) svojo postajo javno objavlja kot JSON na
`https://varpolje.si/station.json`. Vključena je kot **primerjava**, ker ena
sama postaja ne more pokazati, koliko se dve točki v isti dolini razideta —
razlika je največja zjutraj, ko se na dnu doline nabira hladen zrak.

**IREICA1 ostaja edina referenca.** Sosednja postaja je gost:

- **ne** gre v `history.json`, **ne** v učenje ali napovedovanje modela MTR in
  **ne** na semafor `/tocnost-napovedi/`. Tam se meri Filipova postaja in nič
  drugega — sicer se arhiv in izmerjena veščina modela tiho popačita.
- V vsakem prikazu je meritev IREICA1 navedena prva in vizualno poudarjena.

Kje je vključena:

- `worker.js`, `/varpolje-current` — proxy do `varpolje.si/station.json`.
  Prek workerja gre zato, ker sosedov strežnik ne pošilja glave CORS in je
  brskalnik na meteorec.si ne sme brati neposredno. Vir se osveži na ~5 minut,
  zato `Cache-Control: max-age=120`. **Zasebnost velja tudi za sosedovo hišo**:
  blok notranjih meritev se izbriše pri viru, čeprav ga trenutni odgovor nima
  (glej pravilo na vrhu tega dokumenta).
- `app.js`, `fetchValleyDuel()` + kartica `#duel-card` v `index.html` —
  obe temperaturi, razlika in razlaga. Kartica ni `simple-keep`, torej je v
  preprostem pogledu skrita; klic gre skozi `runAdvancedOnly()`, interval pa se
  sproži samo v naprednem pogledu (drugače bi se klici kopičili v vrsti).
  Navedba prijatelja je konstanta `DUEL_NEIGHBOUR`.
- `tools/generate_story_card.py`, tema `VALLEY_DUEL` (prioriteta 47) — kartica
  za zgodbo se sproži samo ob razliki **≥ 2 °C** in samo, če sosedov posnetek
  ni starejši od 45 minut. Zastarel posnetek ni primerjava, ampak dve različni
  uri. Ker zgodbe nimajo podpisa, je navedba prijatelja tretja vrstica
  statistike na sami sliki.

Če se vir kdaj ustavi ali spremeni obliko, vse tri točke tiho odpadejo
(kartica pove, da postaja ni dosegljiva, tema zgodbe se ne uvrsti) — nobena
druga stran od tega ni odvisna.

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

## Gobarski model — rastni zamik po ekoloških skupinah

Vsaka vrsta v `species_rules.yaml` ima `ecology` (`mikorizna`, `razkrojevalka`,
`lesna`) in iz skupine izpeljan `fruiting_lag_days`. Model za ta zamik
**premakne obe padavinski okni nazaj v čas** (`gobe_model.eval_species`):
sprožilni dež se šteje v oknu `lag_min`–`lag_max` dni pred dnem napovedi,
zaloga vode pa 14 dni do začetka tega okna.

- **Ne vračaj okna, ki se konča danes.** Prav to je bila napaka v v1.1: dež
  izpred dveh dni je jurčku dvignil indeks enako kot kukmaku, čeprav mikorizna
  vrsta pred 8–16 dnevi po dežju ne more roditi. Pripombo je javno postavil
  bralec na FB, popravljeno v v1.2 (12. 8. 2026).
- Vlaga tal in zračna vlaga **ostaneta na tekočem dnevu** — zamaknjeni okni
  povesta, ali je bil trosnjak sploh sprožen, ta dva pa, ali danes lahko
  nabrekne in se ne posuši.
- **Lesne vrste tečejo po zračni, ne talni temperaturi** (v1.3): rastejo na
  lesu nad tlemi in talne temperature na 6–18 cm ne čutijo. Iz istega razloga
  zanje **ne velja geološki množitelj** — podlaga gozda ne odloča, kaj raste na
  bezgovi veji. Trapez sestavi model iz `air_temp` in `scoring.temperature.
  air_shoulder_c`. Komponenta se zato imenuje `temperature`, ne `soil_temp`.
- Prag `rain_7d_min` je izražen kot 7-dnevna kumulativa in se preračuna na
  dolžino okna vrste, da skupine z daljšim oknom niso samodejno v prednosti.
- Kdor spreminja zamike, mora poskrbeti tudi za dolžino zgodovine:
  `past_days_needed()` pove, koliko preteklih dni potrebuje poizvedba, in isto
  funkcijo uporabi `gobe_trend.py` za zalet pred 1. aprilom. Prekratka
  zgodovina se ne javi kot napaka — okno se tiho skrajša.
- `species_rules.yaml` nastane iz `data/baza_gob.xlsx` prek
  `tools/import_species_db.py`; skupino izpelje `derive_ecology()` iz stolpca
  substrat. Ročni popravek v YAML regeneracija povozi — popravi skript.

### Ročno umerjanje posameznih vrst

Indeks je **delež izpolnjenih zahtev vrste**, ne primerjava med vrstami. Vrsta z
ohlapnimi pragovi zato zasede vrh, še preden je v gozdu kaj za nabrat — bezgova
uhljevka je bila edina celoletna vrsta z najnižjimi pragovi in je bila v
petletnem backtestu najboljši dan vsakega leta, vselej s 100 %.

Take primere popravi tabela `CALIBRATION` v `tools/import_species_db.py`: ključ
je slug vrste, vrednosti prepišejo polja iz baze, `razlog` pa se izpiše kot
`# ROČNO UMERJENO: …` v YAML. **Vsak vnos potrebuje razlog** in gre vanjo šele,
ko je primerjava med vrstami dokazljivo popačena — ne zato, da bi popravil vtis
o posameznem dnevu.

## Baza vrst: preverjeno jedro in razširjeni seznam

Baza ima 300 vrst iz dveh virov, ki ju uvoznik združi (in ju ne mešaj):

- `data/baza_gob.xlsx` — 145 vrst, zbranih na terenu; v YAML gredo z
  `verified: true` in indeks dobijo po pravilu užitnosti.
- `data/baza_gob_dodatek.csv` — 155 vrst, izbranih po dejanskih zapisih o
  pojavljanju v Sloveniji (GBIF, rangirano po številu zapisov) in opisanih po
  literaturi. V YAML gredo z `verified: false`, indeks pa dobijo **samo**, kjer
  stolpec `Indeks` pravi `da`. Zato je CSV in ne vrstice v xlsx: sestavljene
  trditve o užitnosti in dvojnicah morajo biti vidne v diffu.

Pravila, ki jih ne obračaj:

- **Nepreverjena vrsta praviloma ne dobi indeksa.** Indeks pomeni »pojdi po to
  gobo«; dokler vrsta ni preverjena na terenu, to ni pošteno. Trenutno jih ima
  indeks 10 od 155 — same nezamenljive užitne vrste.
- Na kartici vrste je oznaka »ni terensko preverjeno«; ne odstranjuj je, dokler
  vrsta ni res preverjena (takrat gre vrstica iz CSV v xlsx).
- Pri dodajanju vrst preveri sinonime: GBIF vrača tudi stara imena
  (`Boletus badius` = `Imleria badia`), uvoznik pa lovi le enak slug. Primerjaj
  po sprejetem imenu **in** po vrstnem imenu proti obstoječim vrstam.
- Fotografije doda `tools/fetch_species_photos.py` z Wikimedia Commons; sprejme
  samo licence z dovoljeno objavo (CC0, javna domena, CC BY, CC BY-SA, GFDL) in
  vsako vpiše v `CREDITS.json`, ki se izriše v tabelo virov. Vrsta brez proste
  slike ostane pri rezervnem prikazu — to ni napaka. Sito zavrne mikroskopijo
  in risbe **po kategorijah na Commons**, ne po imenu datoteke: ime tega ne
  izda, kategorija »Fungal spores« pa. `--target dvojnice` polni primerjalne
  slike, imeni datotek vzame iz generatorja strani.

### Baza vrst je razbita na strani po užitnosti

`/baza-vrst/` ima vseh 300 vrst, pod njo pa so `uzitne`, `pogojno-uzitne`,
`strupene` in `neuzitne` (`BAZA_CATS` + `species_section_html()`). Razlog je
dvojen: ena stran s 300 karticami je 405 kB, skupina pa 100–170 kB, in vsaka
skupina je svoj iskalni cilj (»užitne gobe«, »strupene gobe«).

- Med skupinami se hodi **po povezavah, ne s filtrom v JS** — vsaka ima svoj
  URL, naslov in canonical. Iskanje in »V sezoni zdaj« sta filtra v JS znotraj
  trenutne strani.
- Kartice so vse v HTML, naenkrat se jih izriše 24 (`SP_JS`), gumb odpre
  naslednjih 48. **Ne prestavljaj izrisa v JSON** — prav ta seznam je vsebina,
  po kateri stran najdejo iskalniki; brez JS morajo biti vidne vse.
- Nova skupina gre v `BAZA_CATS` in v `CORE` v `tools/seo_audit.py`, sicer je
  v nobenem sitemapu ni.

### Glavna stran gobarja je pristajalna, ne zbirna

`/gobarska-napoved/` nosi samo junaško kartico z dnevnim indeksom, **mrežo
zmožnosti** (`GOBE_CATEGORIES` → `.gp-feat`, grupirano v 4 skupine — glej
spodaj), premium s cenikom in pogosta vprašanja. Vse ostalo ima svojo stran:
`danes` (indeks po območjih), `tereni`, `nasveti`, `dnevnik`, poleg že prej
ločenih `zemljevid`, `koledar`, `trend`, `baza-vrst`, `dvojnice`.

- **Kartice zmožnosti so grupirane v 4 skupine** (`GOBE_CATEGORIES` v
  `tools/generate_gobe_page.py`): 🍄 Napoved, 🗺 Kje nabirati, 🔍 Prepoznaj
  gobo, ♡ Moje gobe — popravljeno 24. 8. 2026, ko je zunanji UX pregled
  pravilno opozoril, da je prejšnji ploski seznam (13 enakovrednih kartic,
  `GOBE_FEATURES`) uporabnika soočil z vsem naenkrat namesto da bi ga vodil.
  **Nova zmožnost ni nov razdelek na glavni strani** — dobi svojo podstran
  (`subpage_shell()`) in vnos pod ustrezno od 4 skupin v `GOBE_CATEGORIES`.
  Redkeje obiskane podstrani (koledar, trend, metodologija, nasveti, FAQ) so
  namesto lastne kartice samo povezava v vrstici `GOBE_MORE` pod skupinami —
  za tja sodi vse, kar ni ena od štirih glavnih uporabnikovih namer.
- Brez uvrstitve (v `GOBE_CATEGORIES` ali `GOBE_MORE`) je podstran
  nedosegljiva, ker drugih menijev na strani ni (hitri meni je odstranjen,
  spodnja navigacija je omejena na pet ciljev).
- Vsaka kartica ima **risano ikono** (`_FI_*`, 24×24, obris `currentColor` +
  ploskve istega currentColor z nizko prekrivnostjo) in svoj poudarek `--fa`.
  **Ne uporabljaj emoji** — med platformami se razlikujejo in se ne dajo
  prebarvati. Preveri, da je ikona berljiva pri ~20 px; drobni detajli
  (goba v lupi, klicaj v trikotniku) se pri tej velikosti zlijejo.
- Nova podstran gre tudi v `CORE` v `tools/seo_audit.py` — sicer je ni v nobenem
  sitemapu. To je edini vpis: iz `CORE` jo poberta tako `--fix` kot `wire_all()`.
- FAQ ostane na glavni strani, ker nosi `FAQPage` strukturirane podatke za
  glavni URL.

## SEO smart routina — hub strani in vremenski dogodki

`tools/seo_smart_routine.py` teče dnevno ob 01:45 UTC
(`.github/workflows/seo-smart-routine.yml`, po `update-history.yml`, pred
`generate-seo-pages.yml`) in vzdržuje dve stvari, ki ju drugi generatorji ne
pokrivajo:

- **Klimatološke hub strani** — `/klima/`, `/padavine/`, `/temperatura/`,
  `/teden/` — mesečne norme, letne vsote, rekordi, samodejni FAQ, izračunani
  iz celotne `history.json`. Osvežujejo se ob vsakem teku (`force=True`).
- **Vremenski dogodki** (`/novosti/<slug>/` + indeks `/novosti/`) —
  `detect_events()`/`detect_heat_waves()`/`detect_droughts()` v zadnjih 30
  (oz. 30 za valove/sušo) dneh zaznajo nove absolutne rekorde, rekorde za
  koledarski dan, sezonska prva, toplotne valove in sušna obdobja. Vsak
  dogodek dobi svojo stran (ustvari se enkrat, potem ostane nespremenjena) in
  vnos v **`novosti.json`** — to je edini vir resnice za to, kateri dogodki
  sploh obstajajo; ko dogodek pade iz 30-dnevnega okna zaznave, ga skript ne
  najde več sam, zato mora priti iz shranjenega kataloga.

Svoj **`sitemap-seo.xml`** (ne `sitemap.xml`) — isti vzorec kot
`sitemap-weather.xml` za arhiv vremena; oba sta v `robots.txt` in v
`SITEMAPS` v `tools/seo_audit.py`. `generate_monthly_post.py` `wire_all()`
te strani zato izpusti iz svojega prepisa sitemap.xml — ne podvajaj vpisov
med sitemapi. Po teku pošlje IndexNow za vse spremenjene URL-je
(`--skip-indexnow` za ročni preizkus).

**`novosti.json` je v korenu repozitorija, ne v mapi `novosti/`** — v
`git add` koraku delavnega toka ju je treba navesti ločeno
(`novosti/ novosti.json`). 19.–20. 8. 2026 je koraku manjkal `novosti.json`,
zato se je katalog lokalno pravilno posodabljal, a nikoli commital: strani
so nastajale in ostajale žive, ko pa je dogodek padel iz 30-dnevnega okna
zaznave, je tiho izginil iz `/novosti/` in iz `sitemap-seo.xml`, ker ga v
(stalno starem) katalogu ni bilo. Popravljeno; 3 tako osirotele strani so
bile ročno povrnjene v katalog. Če spreminjaš, kaj skript zapiše na disk, se
prepričaj, da isto pot pokriva tudi `git add`.

## Test napovedi (`/test-napovedi/`) — primerjava modelov proti IREICA1

Ločeno od `/tocnost-napovedi/` (ta meri samo ARSO+Open-Meteo+MTR pri D+1, dan za
dnem). `/test-napovedi/` meri **pet Open-Meteo virov (ECMWF IFS, ICON, GFS,
ARPEGE, best_match) po vodilnem času D+1..D+7**, z izhodiščema klimatologija in
persistenca — ker Open-Meteo Previous Runs API (`previous-runs-api.open-meteo.com`,
spremenljivke `..._previous_dayN`) za te modele arhivira nazaj do sredine 2024,
je bilo možno enkraten backfill namesto čakanja na sprotno beleženje.

- `tools/build_forecast_archive.py` — zajame urne `_previous_day1..7` vrednosti,
  agregira v dnevni Tmax/Tmin/padavine **po lokalnem času (Europe/Ljubljana)** in
  piše `data/forecast-archive.csv` (dodaja samo nove vrstice, arhiva ne prepisuje).
  Dnevni tek kliče z majhnim `--past-days` (10) — poln backfill (~820) je bil
  enkraten.
- `tools/log_forward_forecasts.py` — ARSO (prek Worker `/arso-forecast`) in
  Yr/MET Norway (`api.met.no`, obvezen User-Agent) nimata arhiva nazaj, zato se
  beležita sproti od uvedbe naprej, v isto shemo kot zgoraj
  (`data/forecast-forward-log.csv`) — `tools/compute_forecast_test_metrics.py`
  ju bere po isti poti, samo z manj zgodovine.
- `tools/log_hourly_observations.py` — urne meritve IREICA1 za bodočo analizo
  "pristranskost po urah dneva" iz prvotnega načrta. **Ecowitt vrne polno 5-min
  ločljivost samo za zadnjih ~90 dni** (starejše poizvedbe so na strežniku že
  podvzorčene na ~6 točk/dan — preverjeno ob gradnji, ni v Ecowitt dokumentaciji)
  — zato tega ni šlo zapolniti za nazaj kot arhiv napovedi zgoraj, samo od zdaj
  naprej. Ker bi hkrati potrebovali tudi urne (ne dnevne) napovedi vseh petih
  virov za nazaj — kar bi `data/forecast-archive.csv` napihnilo ~150×, na
  velikost, ki v repozitorij ne sodi — stran namesto tega prikaže primerjavo
  Tmax- proti Tmin-pristranskosti pri D+1 (ista zgodba — spregledana nočna
  inverzija — brez urnega arhiva).
- `tools/compute_forecast_test_metrics.py` — MAE/bias/RMSE/delež >3 °C in
  kontingenčna tabela za padavine (0,2 in 5 mm), po (vir, vodilni čas), proti
  klimatologiji (±7 dni okoli koledarskega dne, iz cele postajne zgodovine —
  ne ERA5, postaja ima dovolj let sama) in persistenci. Piše
  `data/test-napovedi.json`.
- `tools/generate_test_napovedi_page.py` — `test-napovedi/index.html` (grafi so
  inline SVG, izrisani v brskalniku iz `/data/test-napovedi.json` — isti vzorec
  kot `TREND_JS` v `generate_gobe_page.py`, brez zunanjih JS knjižnic) in javni
  `test-napovedi/podatki.csv` (samo razrešeni dnevi, licenca CC BY 4.0 v glavi).
- `tools/generate_forecast_test_post.py` — mesečni povzetek (predloga s pravimi
  izračunanimi številkami, brez LLM osnutka — isti vzorec kot
  `invasive_watch.py` — nato en prehod lekture prek `generate_daily_post.call_lektor`).
  `--wire` pokliče `wire_all()`.
- **FB/IG objava je namenoma izklopljena** za mesečni članek (drugače od ostalih
  petih objavljalnih workflowov) — nova vrsta vsebine, prva objava naj gre skozi
  ročni pregled, preden se doda.
- Delavna toka: `test-napovedi-daily.yml` (01:50 UTC, po `update-history.yml` in
  `forecast-verify.yml`) in `test-napovedi-monthly.yml` (1. v mesecu, 05:15 UTC).

## Agrometeo (`/agrometeo/` + zavihek na naslovni strani) — modelirana ocena, ne diagnoza

Bralec je 28. 8. 2026 pravilno opozoril, da je stran svoje modelirane ocene prikazovala
z večjo agronomsko gotovostjo, kot jo GDD/vremenski model dejansko lahko zagotovi:
»Hmelj: 1144 GDD — storžki · obiranje čez 106 GDD« ob dejanskem stanju, ko je IHPS že
sredi avgusta poročal, da je Savinjski golding v tehnološki zrelosti — in »Hmeljeva
pepelovka — 100 %«, kar bralcu zveni kot skoraj potrjena bolezen, ne kot weather-suitability
heuristika. Popravljeno v `tools/generate_agrometeo_page.py` in `app.js`
(`_buildAgroHop`/`_buildAgroHopDisease`/`_buildAgroSpray`):

- **GDD pove modelirano razvojno fazo, ne tehnološko zrelost.** Fenološka tabela (`HOP_STAGES`)
  ostaja (uporabna groba ocena), a besedilo okrog nje zdaj eksplicitno pravi, da gre za oceno
  iz enega dejavnika (temperature) za dolino kot celoto — dejanska zrelost je odvisna tudi od
  sorte, tehnoloških ukrepov, tal in lokacije. Poleg nje je nova, **ročno vzdrževana** tabela
  »Tehnološka zrelost — IHPS« (`IHPS_STATUS` v obeh datotekah, namerna podvojitev, isto načelo
  kot `HOP_STAGES`) — vpiši ročno ob vsaki novi objavi na ihps.si, z virom in datumom. Ne
  izpeljuj statusa iz GDD.
- **Bolezni: »primernost«, ne »tveganje %«.** `hop_disease_risk()`/`_buildAgroHopDisease()`
  računata odstotek še naprej (za barvo/dolžino stolpička), a stran ga ne izpisuje kot
  »Tveganje 100 %« — izpiše samo kvalitativno oznako (`suitability_label()`: nizka/zmerna/visoka
  primernost) in eksplicitno opombo, da gre za meteorološki indikator, ne prognostično napoved
  ali diagnozo po metodologiji IHPS.
- **»Okno za škropljenje« → »Meteorološko okno za nanos«**, povsod (h2, FAQ, `clabel` v
  `index.html`), z opombo, da ocena upošteva samo veter/padavine/temperaturo — ne etikete
  sredstva, zanašanja, bližine voda ali opraševalcev; pred uporabo FFS preveri etiketo, FITO-INFO
  in priporočila IHPS.
- **Freshness na `/agrometeo/`**: stran generira cron (`agrometeo-forecast.yml`, dnevno) in je,
  za razliko od zavihka na naslovni strani (ta vedno kliče Open-Meteo v živo), statičen posnetek
  — če cron enkrat ali večkrat izostane, stran tiho kaže vse starejši datum brez opozorila. Zdaj
  `data-generated` na strani + vgrajen inline `<script>` (isti prag kot MeteoGasilec: 🟡 26–50h,
  🔴 >50h) izpiše »Podatki niso sveži« in nad 50h doda »trenutnih priporočil ne uporabljajte za
  odločanje«. Ne skrivaj stare vrednosti, samo jo označi — isto načelo kot `renderFreshness()`
  v `meteogasilec/gasilec.js`.

## MeteoGasilec — dva načina uporabe

`/meteogasilec/` ima od 28. 8. 2026 dva na sebi: **pripravljalni** (dnevni FWI,
metodologija, FIRMS, vreme za intervencije — vse za Rečico ob Savinji) in
**operativni** (`/meteogasilec/intervencija/` — hiter pogled med intervencijo:
GPS lokacija, grafičen veter, detektor obrata vetra, kopiraj briefing).

- **`meteogasilec/gasilec.js`** — nova skupna klientska datoteka, ROČNO pisana
  (ni generirana), deljena med vsemi `/meteogasilec/*` stranmi. Vsebuje kompas
  (`windCompassSvg`), detektor obrata vetra (`angleDiff`/`detectWindShift`),
  freshness (`renderFreshness`) in generator briefinga (`buildBriefing`). Ta
  strani ne nalagajo `app.js` (samostojne, self-contained — enako kot FIRMS
  widget), zato je bilo to potrebno, da FWI/kompas logika ne bi postala tretja
  ločena kopija iste stvari (poleg `app.js` in `gasilec_model.py`). Načelo
  "generatorji strani si ne delijo knjižnic" iz tega dokumenta velja med
  RAZLIČNIMI Python generatorji — ne med podstranmi ENEGA generatorja
  (`generate_gasilec_page.py` generira vseh sedem `/meteogasilec/*` strani).
  FWI izračun v tej datoteki (`calcOneDayFWI`/`fwiClass`) je namerna dobesedna
  kopija iz `app.js` (glej opombo na vrhu `gasilec_model.py`) — če spremeniš
  formulo/pragove, popravi vse tri kopije (app.js, gasilec_model.py,
  gasilec.js). Isto velja za 16-smerna imena vetra (`_DIRS` v
  `generate_gasilec_page.py` ↔ `GASILEC_DIRS` v gasilec.js).
- **GPS na `/intervencija/` velja za vreme/veter VEDNO, za FWI/ISI pa samo, če
  je lokacija >2 km od Rečice ob Savinji** — pod tem pragom ostane prikazan
  FWI za Rečico (`meteogasilec/index.json`, zgrajen dnevno), nad njim JS
  pokliče Open-Meteo `daily` za GPS točko in prek `Gasilec.fwiSeriesFromDaily()`
  (gasilec.js) preračuna lokalni FWI/ISI — četrta namerna kopija iste FWI
  formule (poleg app.js, gasilec_model.py, gasilec.js-ovega `calcOneDayFWI`),
  ker klientska stran ne more klicati Python kode. Opomba pod naslovom
  (`#gf-fwi-note`) vedno pove, za katero lokacijo je FWI prikazan.
- **Obrat vetra ≥45° je MeteoGasilec kriterij, ne uradno opozorilo ARSO** —
  vedno tako označen. Prag: obrat smeri >=45° IN veter/sunki na vsaj eni
  strani >=15 km/h (da se pri skoraj brezvetrju ne sproža po nepotrebnem).
- **Uradna opozorila ARSO so jasno ločena od MeteoGasilec lastnih ocen — in
  pred njimi po vrstnem redu na strani** (uradni status nad FWI heroj, ne pod
  njim — 28. 8. 2026 popravljeno po zunanjem UX pregledu, ki je opozoril, da
  bi uporabnik FWI-jevo besedno oznako, npr. »Visoka«, lahko zamenjal za
  uradno oceno). `generate_gasilec_page.py` (`fetch_arso_alerts` = uvožen
  `fetch_alerts()` iz `generate_arso_newsjack_post.py`, isti Worker
  `/arso-warning` endpoint kot `/nevihte/` WX-ARSO) zajame opozorila **ob
  generiranju strani** in jih izriše strežniško (`arso_widget_html()`) — stran
  je varnostno-kritična, zato nalagajoč se placeholder ("Preverjam …") ne sme
  biti edino, kar vidi uporabnik ali crawler, dokler JS ne odgovori. Klientski
  `Gasilec.renderArsoWidget()` ta posnetek ob nalaganju osveži z živimi podatki
  (opozorilo je stanje, ne novica — enkrat-dnevni posnetek bi v urah zastaral,
  glej razdelek o ARSO opozorilih zgoraj), **če pa živi klic spodleti, posnetka
  ne izbriše niti ne prepiše z "ni aktivnih"** — oboje bi bila varnostno
  nevarna napačno-pomirjujoča trditev. Iz istega razloga `fetch_ok=False` (Worker
  nedosegljiv že ob generiranju) izpiše "ni bilo mogoče preveriti", nikoli "ni
  aktivnih opozoril". Prikazan na `/meteogasilec/` (razdelek »🏛 Uradna
  opozorila«, nad FWI kartico) in strnjeno na `/intervencija/` (nad vremensko
  kartico, isto načelo), od koder se aktivna opozorila (vključno z rezervnim
  posnetkom, če se živi klic ni še izvedel ali je spodletel) vključijo tudi v
  »Kopiraj briefing« (`buildBriefing()`).
- **Veter + teren** (`/intervencija/`, razdelek »🏔 Veter + teren«) — za
  trenutno aktivno lokacijo (GPS ali privzeta Rečica) `Gasilec.
  fetchElevationGrid()` pokliče Open-Meteo Elevation API za mrežo 3×3
  (korak 90 m — ločljivost DEM-a, ki ga API uporablja), `computeSlopeAspect()`
  iz nje izračuna naklon/ekspozicijo po Horn (1981) metodi (standardni GIS
  algoritem, isti kot ArcGIS/QGIS — **enotno testiran z Node na sintetičnih
  mrežah znane smeri pred vklopom**, ker gre za novo geometrijo, ne kopijo
  obstoječe formule). Opozorilo "veter in pobočje sta poravnana" je
  MeteoGasilec kriterij (razlika ≤45°), namenoma poenostavljen (brez
  vegetacije/gostote gozda) — jasna opomba na strani. Povsem klientsko, brez
  strežniške rezerve (odvisno od trenutne lokacije, enako kot lokalni FWI).
- **Vodotoki** (`/meteogasilec/vodotoki/`) — NE podvaja ARSO hidro branja:
  uvozi `fetch_arso_stations()`/`station_status()` iz
  `tools/generate_vodostaj_page.py` (obstoječa polna stran `/vodostaj-savinje/`
  z GloFAS napovedjo in zgodovino poplav), prikaže samo 3 najbližje postaje ob
  Savinji + povezavo na polno stran. Besedilo namenoma pravi "najbližji
  vodotok/postaja", NE "vodo lahko črpaš" — vodostaj ne pove nič o fizičnem
  dostopu vozila.
- **Freshness sistem — nikoli ne skrivaj stare vrednosti, samo jo označi.**
  `renderFreshness()` izpiše 🟢 (<26h, en dnevni tek zamujen), 🟡 (26–50h) ali
  🔴 (>50h, zamujena ≥2 teka) glede na `data-generated` na `.gf-hero`. Uveden
  po incidentu, ko je stran tiho kazala včerajšnji datum brez opozorila.
- **Hidranti (`meteogasilec/hidranti.json`) so cron + statičen JSON, NE Worker
  proxy.** `tools/fetch_hydrants.py` teče enkrat dnevno znotraj
  `gasilec-forecast.yml` (ne ločen delavni tok — hidranti se spreminjajo
  redko) in povpraša javni Overpass strežnik za bbox **Zgornje Savinjske
  doline** (Solčava–Luče–Ljubno–Rečica–Mozirje–Nazarje–Gornji Grad,
  `46.26,14.60,46.45,15.05`) — regionalno, ne nacionalno, isti lokalni
  značaj kot preostanek strani. Overpass glavni strežnik (`overpass-api.de`)
  je pri gradnji zavračal zahteve iz podatkovnega centra (connection reset) —
  zato `OVERPASS_MIRRORS` poskusi več javnih zrcal po vrsti
  (`overpass.openstreetmap.fr` prvo, ker je delovalo zanesljivo). Ob napaki
  vseh zrcal skript obdrži star `hidranti.json` in konča z 0 — isto načelo
  "raje star podatek kot prazna stran" kot `inject_forecast.py`. Tri stanja
  hidranta (🟢 preverjeno/🟡 samo OSM/🔴 nedelujoče) gredo prek ročne
  `HYDRANT_OVERRIDES` tabele v `fetch_hydrants.py` — isti vzorec (ključ +
  obvezen `razlog`) kot `CALIBRATION` v `import_species_db.py`.
- **`/meteogasilec/karta/` je prva stran v repozitoriju z zunanjo JS
  knjižnico** (Leaflet 1.9.4 prek `unpkg.com`, samo na tej strani, z SRI
  `integrity` atributom na obeh `<script>`/`<link>` tagih). Doslej so vse
  karte na strani (nevihtni potencial, gobarska) risane kot lasten
  vektor/SVG — to zadošča za nacionalni pregled, ne pa za "najdi pot do
  hidranta 180 m stran", kjer je prava ulična karta (OSM raster ploščice)
  bistvo funkcije. Stran ima strežniško izrisan rezervni seznam 10
  najbližjih hidrantov (brez JS/za pajke) in klientsko Leaflet karto s sloji
  (hidranti iz `hidranti.json`, FIRMS prek Worker `/pozari`, isti klic kot
  `firms_widget_html()`). Če se Leaflet iz kakršnega koli razloga ne
  naloži, inline skript to preveri (`typeof L==='undefined'`) in pusti samo
  rezervni seznam — nikoli ne podre strani z nedefinirano spremenljivko.
- `/intervencija/` gumb "Odpri operativno karto" vodi na
  `/meteogasilec/karta/?lat=..&lon=..` (karta prebere query parametra in se
  centrira nanju), ne več na surov OpenStreetMap URL.
- `/meteogasilec/kalkulator/` (cisterna, penilo, statični tlak) je povsem
  klientski, brez zunanjih podatkov — formule ostanejo lokalne v
  `build_kalkulator_page()`, ne v `gasilec.js` (nič drugega jih ne rabi).
- Nova `/meteogasilec/*` podstran gre tudi v `CORE` v `tools/seo_audit.py` —
  isto pravilo kot za gobarske in ostale podstrani drugod v tem dokumentu.

## GEO — citiranost pri AI asistentih

`tools/geo_audit.py` preverja tisto, kar `seo_audit.py` ne: veljavnost
JSON-LD, ujemanje FAQPage sheme z vidno vsebino, avtorsko entiteto,
zastarelost `dateModified` na ključnih straneh, skoraj podvojeno vsebino med
kraji v dolini in neveljavne `@id` reference. Poganjaj ga **ob vsaki novi
strani ali generatorju** — isto načelo kot obvezna lektura zgoraj: nova stran
ni končana, dokler `geo_audit.py` zanjo ne javi 0 napak. Novo strukturirano
entiteto (Person/Organization/Place `sameAs`) dodajaj v skupni register
(`PLACE_SAMEAS` v `generate_monthly_post.py`), ne kot vtipkan niz na novem
mestu — glej opombo pri registru, zakaj.

**Sledenje omembam** (`data/geo-mentions.json`, prazen seznam do prvega
vnosa) — ročen, mesečni dnevnik, ne avtomatiziran sistem: isti nabor
vprašanj vsak mesec vprašaj ChatGPT, Perplexity in Google AI Overview
("vreme rečica ob savinji zdaj", "vreme zgornja savinjska dolina po urah",
"gobarska napoved zgornja savinjska dolina", "kaj je rosišče", "je danes
nevarnost požara v savinjski dolini") in zapiši, ali/kako omenijo
meteorec.si. Brez tega ni mogoče vedeti, ali GEO delo sploh kaj spremeni.

## Razvoj

- Razvoj na seji veji, merge v `main` prek PR; `main` je produkcija
  (GitHub Pages + auto-deploy Cloudflare workerja ob spremembi worker.js).
