# Meteorec — navodila za delo z blogom

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

## Razvoj

- Razvoj na seji veji, merge v `main` prek PR; `main` je produkcija
  (GitHub Pages + auto-deploy Cloudflare workerja ob spremembi worker.js).
