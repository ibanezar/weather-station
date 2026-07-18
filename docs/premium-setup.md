# Gobarska napoved Premium — postavitev

Enkratna navodila za aktivacijo plačljivega dostopa. Arhitektura:

```
Paddle checkout ──webhook──▶ Worker /premium/webhook ──▶ KV: premium:sub:<email>
                                      │
                                      └─▶ Resend: magic link ▶ uporabnik
GitHub Action (dnevno) ──▶ Worker /premium/data ──▶ KV: premium:data
Stran /gobarska-napoved/ ──token──▶ Worker /premium/forecast ──▶ premium JSON
```

Brez uporabniških računov: e-naslov + žeton (magic link, 90 dni). Dostop poteče
z naročnino (`expires` v KV), žetona ni treba preklicevati.

## 1. Paddle (plačila, merchant-of-record)

1. Registriraj se na [paddle.com](https://www.paddle.com) (najprej **sandbox**
   za test: sandbox-vendors.paddle.com). Paddle je merchant-of-record — DDV in
   račune za EU kupce ureja Paddle, ti fakturiraš samo Paddlu (pomembno za s.p.).
2. **Catalog → Products**: ustvari produkt »Gobarska napoved Premium« z dvema cenama:
   - mesečna naročnina **3,99 €/mesec** (recurring),
   - sezonski dostop **24,99 €** (one-time).
3. Zapiši oba **price ID** (`pri_…`) v `wrangler.toml` →
   `PADDLE_PRICE_MONTHLY` / `PADDLE_PRICE_SEASON`.
4. **Developer tools → Notifications**: nova destinacija
   `https://weatherireica1.filip-eremita.workers.dev/premium/webhook`,
   naročena samo na dogodek **`transaction.completed`**. Zapiši **webhook secret**.
5. **Developer tools → Authentication**: ustvari **API key** (za branje
   e-naslova kupca iz `customer_id`) in **client-side token** (za Paddle.js na strani).
6. Checkout poteka prek **Paddle.js overlay** neposredno na strani /gobarska-napoved/
   (brez preusmeritve). V `tools/generate_gobe_page.py` (vrh datoteke) nastavi:
   - `PADDLE_CLIENT_TOKEN` — client-side token iz koraka 5,
   - `PADDLE_PRICE_MONTHLY` / `PADDLE_PRICE_SEASON` — ista price ID-ja kot v `wrangler.toml`,
   - `PADDLE_ENV` — `"sandbox"` za test, `"production"` za v živo.
   Dokler je `PADDLE_CLIENT_TOKEN` prazen, gumbi varno padejo na `#pricing` (stran deluje).
   Email kupca webhook dobi iz Paddla (customer_id), zato posebni checkout link ni potreben.

Za sandbox test nastavi v `wrangler.toml` še
`PADDLE_API_BASE = "https://sandbox-api.paddle.com"` (pred produkcijo vrni), v
`generate_gobe_page.py` pa `PADDLE_ENV = "sandbox"`.

## 2. Cloudflare Worker — skrivnosti

```sh
wrangler secret put PREMIUM_SYNC_KEY      # poljuben dolg naključen niz, npr. `openssl rand -hex 32`
wrangler secret put PADDLE_WEBHOOK_SECRET # iz koraka 1.4
wrangler secret put PADDLE_API_KEY        # iz koraka 1.5
# RESEND_API_KEY že obstaja (blog-subscribe)
```

Worker se avtomatsko deploya ob pushu `worker.js`/`wrangler.toml` na `main`
(`deploy-worker.yml`).

## 3. GitHub — skrivnost za dnevni push podatkov

Repo → Settings → Secrets and variables → Actions → **New repository secret**:

- `PREMIUM_SYNC_KEY` — ista vrednost kot v koraku 2.

Workflow `gobe-forecast.yml` vsak dan ob 5:00 UTC izračuna model
(`tools/gobe_model.py`), commita free JSON in premium JSON potisne v KV.
Če skrivnost ni nastavljena, se KV push tiho preskoči (nič se ne podre).

## 4. Test (sandbox)

```sh
# 1) ročni push podatkov
python3 tools/gobe_model.py --out-premium /tmp/premium.json
curl -X POST https://weatherireica1.filip-eremita.workers.dev/premium/data \
  -H "Authorization: Bearer $PREMIUM_SYNC_KEY" --data-binary @/tmp/premium.json

# 2) testni nakup prek Paddle sandbox checkouta (kartica 4242 4242 4242 4242)
#    → na e-naslov prispe magic link oblike
#    https://meteorec.si/gobarska-napoved/?token=…

# 3) preveri dostop
curl "https://weatherireica1.filip-eremita.workers.dev/premium/verify?token=TOKEN"
curl "https://weatherireica1.filip-eremita.workers.dev/premium/forecast?token=TOKEN"

# 4) ponovni magic link ("pozabljen dostop")
curl -X POST https://weatherireica1.filip-eremita.workers.dev/premium/login \
  -H "Content-Type: application/json" -d '{"email":"kupec@example.com"}'
```

## 4b. E-mail alarm "moji pogoji" (faza 4 + lastna pravila)

Vsak naročnik si na strani (razdelek 🔔 Moji alarmi) lahko nastavi do 5 lastnih
pravil: vrsta (ali katerakoli), nabiralno območje (ali katerokoli), najnižja
nadmorska višina (neobvezno) in prag v %. Pravila se shranijo prek
`GET`/`POST /premium/alerts` (Bearer token naročnika) v KV kot
`premium:alertrules:<email>`.

Dnevni workflow po pushu podatkov pokliče `POST /premium/notify` (Bearer
`PREMIUM_SYNC_KEY`). Worker za vsakega aktivnega naročnika, ki ni izklopil
obvestil:

- prebere njegova shranjena pravila; če jih naročnik še ni nastavil, uporabi
  privzeto pravilo "katerakoli vrsta, katerokoli območje, prag
  `PREMIUM_ALERT_THRESHOLD`" (70) — obstoječi naročniki torej alarme dobivajo
  naprej brez kakršnekoli akcije,
- pošlje samo, če vsaj eno pravilo doseže svoj prag,
- ne pogosteje kot vsakih `PREMIUM_ALERT_COOLDOWN_DAYS` (5) dni **na naročnika**
  (KV `premium:alertstate:<email>`, proti spamu).

Vsak alarm vsebuje magic link (takojšen dostop) in povezavo za odjavo od
obvestil (`/premium/alerts/off?token=…`) — dostop do napovedi ob tem ostane.
Privzeti prag in razmik nastaviš v `wrangler.toml` ([vars]); pošiljanje
uporablja obstoječi `RESEND_API_KEY`. Ročni test: `curl -X POST
…/premium/notify -H "Authorization: Bearer $PREMIUM_SYNC_KEY"` → odgovor pove
`checked` (aktivni naročniki) in `notified` (dejansko poslano).

## 5. Ročno upravljanje naročnikov (brez UI)

KV ključ `premium:sub:<email>` v Cloudflare dashboardu (Workers → KV →
COUNTER_KV). Ročna aktivacija (npr. prijatelju, novinarju):

```json
{"email":"nekdo@example.com","plan":"sezona","expires":"2026-11-30T23:59:59Z","updated":"2026-07-16T00:00:00Z"}
```

nato mu pošlji povezavo prek `POST /premium/login`.

## Opombe

- **Zasebnost**: v KV se hrani samo e-naslov in stanje naročnine — dopolni
  `zasebnost.html` (upravljavec, namen, Paddle in Resend kot obdelovalca).
- **Preklic naročnine**: dostop velja do `expires`; ob mesečnem podaljšanju
  Paddle sproži nov `transaction.completed`, ki datum podaljša. Preklicanih
  dogodkov ni treba obdelovati.
- **Stroški**: Paddle ~5 % + 0,50 € na transakcijo; Worker/KV/Resend v brezplačnih
  okvirih → fiksni strošek 0 €/mesec.
