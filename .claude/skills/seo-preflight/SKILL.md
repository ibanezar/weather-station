---
name: seo-preflight
description: Preflight checklist za SEO/GEO/zasebnost pred zaključkom dela, ki doda ali spremeni stran, generator, sitemap ali blog objavo v meteorec.si. Zažene seo_audit.py in geo_audit.py, preveri CORE registracijo novih strani, dolžino <title>, novosti.json git add past in uhajanje notranjih meritev. Uporabi pred commitom/PR-jem, ne kot nadomestilo za lekturo.
---

# SEO/GEO preflight za Meteorec

Ta skill je kodifikacija pravil iz `CLAUDE.md`, ki so bila v preteklosti
prekršena tiho (napaka je bila commitana in ostala neopažena tedne ali
mesece — glej datume incidentov spodaj). Namen ni nadomestiti `seo_audit.py`
ali `geo_audit.py`, ampak zagotoviti, da se **dejansko poženeta** in da se
njuno poročilo prebere, preden je delo "končano".

Zaženi ta checklist, kadar seja v tem branchu:
- doda novo stran ali podstran (nov generator, nova `/pot/`),
- spremeni `sitemap.xml`, `seo_audit.py` (`CORE`), ali kateri koli
  `generate_*_page.py`,
- doda ali uredi blog objavo (ročno ali prek generatorja),
- spremeni `worker.js` endpoint, ki vrača surove postajne podatke, ali kodo,
  ki bere Ecowitt/Varpolje odgovor.

Ni potreben za spremembe, ki se ne dotikajo strani/sitemapa/vsebine (npr.
sprememba formule v `gasilec_model.py`, popravek testa).

## 1. Poženi oba avditorja

```bash
python3 tools/seo_audit.py       # pokritost sitemapa + on-page; ne popravlja
python3 tools/geo_audit.py       # JSON-LD, FAQPage, avtorska entiteta, @id
```

- `seo_audit.py` brez `--fix` samo poroča — ne-nič izhod pomeni, da nekaj
  manjka v sitemapu ali na strani. Če manjka pokritost, popravi z
  `python3 tools/seo_audit.py --fix` (aditivno, nikoli ne odstranjuje).
- `geo_audit.py` mora vrniti **0 napak** za vsako novo stran ali generator —
  to ni priporočilo, je pogoj (glej razdelek "GEO" v `CLAUDE.md`).
- Če katerikoli od njiju javi napako, je delo nedokončano, dokler ni
  popravljena — ne nadaljuj na commit/PR z rdečim avditorjem.

## 2. Nova stran je registrirana na EDINEM pravem mestu

Vsaka nova stran/podstran (gobarska, meteogasilec, igra, test-napovedi …)
mora biti v `CORE` v `tools/seo_audit.py`. To je edini seznam ključnih
strani v repozitoriju — **ne uvajaj drugega**. 17. 8. 2026 sta obstajala dva
seznama in sta se razšla: 13 strani je bilo večino dni v nobenem sitemapu.

```bash
grep -n "^CORE" -A2 tools/seo_audit.py | head -5   # samo za orientacijo
```

Preveri ročno, da je nova pot dodana v `CORE` (slovar v `tools/seo_audit.py`)
z ustreznim `changefreq`/`priority` — `seo_audit.py` iz koraka 1 to sicer
odkrije, tale korak je samo opomnik, zakaj napaka sploh obstaja.

`sitemap-seo.xml` (klimatološke hub strani, `/novosti/*`) je **ločen**
sitemap od `sitemap.xml` — `generate_monthly_post.py` `wire_all()` ga
namenoma izpusti iz svojega prepisa. Ne dodajaj teh poti tudi v `CORE`.

## 3. `<title>` gre skozi `seo_title()`

Google odreže naslove nad 60 znakov; Semrush to javi kot napako. Vsak nov
ali spremenjen `<title>` mora nastati kot:

```python
f"<title>{seo_title(title)}</title>"
```

(`seo_title` iz `tools/generate_monthly_post.py`, drugi argument je
pripona npr. `" | Meteorec, Rečica ob Savinji"`). Funkcija skrajša samo
title tag — h1/og:title/JSON-LD/`blog.json` pusti pri miru.

```bash
grep -rn "<title>" --include="*.py" tools/ | grep -v "seo_title("
```

Vsaka vrstica, ki se izpiše zgoraj in gradi `<title>` mimo `seo_title()`, je
sumljiva — preveri jo ročno (nekateri zadetki so statični, kratki naslovi v
predlogah, kar je v redu).

## 4. Notranje meritve se NE širijo dlje od izvora

Zgodilo se je 30. 7. 2026: surov Ecowitt odgovor je šel naravnost v model in
dnevni članek je objavil notranjo temperaturo. Blok `indoor` se izbriše na
**štirih** mestih — če dodajaš nov vir postajnih podatkov ali novega
odjemalca, ki bere `/ecowitt-current` ali `/varpolje-current`, preveri, da
si dodal peto zarezo, ne da si se zanesel na obstoječe štiri:

```bash
grep -rn "indoor" worker.js tools/generate_daily_post.py tools/generate_story_card.py app.js
```

Pričakovani rezultat je izbris/`pop`/`delete` bloka `indoor` v vsakem od teh
štirih mest (`worker.js` dvakrat — Ecowitt in Varpolje proxy). Če dodajaš nov
tretji odjemalec surovega odgovora, dodaj enak `pop("indoor", None)` /
`delete data.indoor` **pred** karkoli drugim, kar dela s podatki — ne šele
pred prikazom.

## 5. `novosti.json` in `novosti/` gresta v git skupaj

Če je skript spremenil `novosti.json` (SEO smart routina, vremenski
dogodki), mora `git add` zajeti **oba**: `novosti/ novosti.json`. 19.–20. 8.
2026 je koraku manjkal `novosti.json` — strani so ostajale žive, dogodek pa
je po izteku 30-dnevnega okna tiho izginil iz `/novosti/` in
`sitemap-seo.xml`.

```bash
git status --porcelain novosti/ novosti.json
```

Če se pri enem od dveh pojavi sprememba, se mora pri drugem tudi (ali pa je
bila sprememba samo interna/brez novega dogodka).

## 6. Lektura (samo za blog objave, ne za orodja/strani brez besedila)

- Samodejni članki: lektura je vgrajena (`call_lektor` v
  `generate_daily_post.py`) — nič dodatnega ni treba.
- Ročno napisan ali naknadno urejen članek: po merge-u na `main` je treba
  pognati workflow **"Lektura obstoječih objav"** (`lektura.yml`) z
  `slugs=<slug>`. To ni del preflighta na branchu (workflow teče na `main`),
  ampak opomnik, da delo ni končano samo z merge-em.

## Povzetek izhoda

Na koncu na kratko povej uporabniku: rezultat `seo_audit.py`/`geo_audit.py`
(zeleno/rdeče + če rdeče, kaj), ali je nova stran v `CORE`, ali `<title>`
gre skozi `seo_title()`, ali je `indoor` zaščiten na vseh relevantnih
mestih, in če gre za objavo — opomni na `lektura.yml`.
