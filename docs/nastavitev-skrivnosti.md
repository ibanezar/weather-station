# Manjkajoči skrivnosti (stanje 1. 10. 2026)

Dve stvari lahko nastavi samo lastnik; brez njiju del avtomatike tiho ne dela.

## 1. `GH_DISPATCH_TOKEN` (Cloudflare Worker)

**Zakaj:** GitHubov cron zamuja 5–7 ur, zato jutranje karte (nevihtna, padavinska) zgrešijo
svoje okno. Worker jih zato sam sproži (`_cronDispatchScheduledWorkflows`), a samo z žetonom.
Od 31. 8. ni bilo niti enega `workflow_dispatch`; `/health` kaže `dispatch: manjka GH_DISPATCH_TOKEN`.

1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**.
2. Repository access: **Only select repositories → `ibanezar/weather-station`**.
3. Permissions → Repository: **Actions: Read and write** (Metadata: Read se doda sam).
4. Rok veljavnosti: najdlje, kar dovoliš (ob poteku se `/health` spet obarva).
5. V korenu repozitorija: `npx wrangler secret put GH_DISPATCH_TOKEN` in prilepi žeton
   (ali Cloudflare → Workers & Pages → `weatherireica1` → Settings → Variables and Secrets → Add,
   tip *Secret*).
6. Preveri: čez 5–10 minut `https://weatherireica1.filip-eremita.workers.dev/health` → `dispatch`
   ima `ok: true`; v Actions se pojavijo teki z dogodkom `workflow_dispatch`.

## 2. `SUBSCRIBE_SECRET` (GitHub Actions)

**Zakaj:** `morning-digest.yml` vsak dan pade (rdeč), ker nima gesla za pošiljanje
jutranjega povzetka prek workerja. Naročniki zato ne dobijo nič.

1. Poišči vrednost, ki jo ima worker: Cloudflare → `weatherireica1` → Settings → Variables and
   Secrets → `SUBSCRIBE_SECRET` (če ga ni, worker vzame `DELETE_SECRET`). Vrednosti secreta
   Cloudflare ne pokaže — če je ne poznaš, nastavi novo na obeh straneh
   (`npx wrangler secret put SUBSCRIBE_SECRET`).
2. GitHub → repozitorij → **Settings → Secrets and variables → Actions → New repository secret**,
   ime `SUBSCRIBE_SECRET`, ista vrednost.
3. Preveri: Actions → *Morning digest* → **Run workflow**; tek mora biti zelen.
