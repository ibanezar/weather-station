# Prompt knjižnica — Claude za SEO/GEO delo na Meteorecu

Ročna knjižnica promptov za seje, v katerih Filip z Claude pripravlja ali
ureja vsebino ročno (evergreen blog članki, nove hub strani, mesečni
pregled). **Ne podvaja avtomatike** — dnevni/mesečni/storm-watch članki
gredo skozi `generate_daily_post.py`/`generate_monthly_post.py`
(predloge + `call_claude()` + obvezna `call_lektor()`), ta datoteka je za
vse, kar nastane ali se ureja v ročni seji.

Vsak prompt spodaj je že napolnjen s pravim kontekstom Meteoreca namesto
oglatih oklepajev — kopiraj in prilagodi konkretnemu članku/strani.

## Pravila, ki veljajo za VSAK prompt spodaj

- **Nobene številke ne izmisli.** Vsaka statistika, rekord ali primerjava
  mora izhajati iz `history.json`, `model/recica-mos.json`,
  `data/test-napovedi.json` ali podatka, ki ga Filip prilepi v pogovor — ne
  iz splošnega vedenja modela o vremenu nasploh.
- **Ne piši o notranjih meritvah.** Glej pravilo na vrhu CLAUDE.md — noben
  prompt spodaj ne sme dobiti surovega Ecowitt odgovora z blokom `indoor`.
- **Nikoli ne urejaj ročno datoteke, ki jo piše generator** (`blog.json`,
  `sitemap.xml`, katera koli `*/index.html` pod nadzorom `wire_all()` ali
  `generate_*_page.py`). Prompti za JSON-LD/meta spodaj so za strani, ki
  jih Filip piše/ureja ročno (npr. nov `docs/*` ali enkratna stran) — ne za
  strani, ki jih izpiše generator.
- **Vsak članek gre pred objavo skozi lekturo** (glej "Lektura je OBVEZNA"
  v CLAUDE.md). Prompti spodaj lekture ne nadomestijo.
- **Po vsakem ročnem popravku že objavljenega članka** poženi
  `lektura.yml` z `slugs=<slug>` — samodejno popravi `dateModified`/`updated`
  (glej `touch_existing()` v CLAUDE.md).

---

## 1. Raziskava ključnih besed in namena

### Klasifikacija namena za seznam poizvedb
Uporabno pred novim evergreen člankom, ko Filip iz Search Console ali lastne
domišljije prinese seznam kandidatnih poizvedb.

```
Ti si SEO strateg, specializiran za analizo namena iskanja. Spodaj je seznam
poizvedb, vezanih na vreme/podnebje/gobarstvo v Zgornji Savinjski dolini
(Rečica ob Savinji, Mozirje, Nazarje, Ljubno ob Savinji, Logarska dolina).
Za vsako:
1. Označi primarni namen (informativen / navigacijski / transakcijski /
   komercialen).
2. Če je namen dvoumen, to označi in razloži v enem stavku.
3. Predlagaj ustrezen format vsebine (evergreen razlagalec, hub stran,
   dnevni podatkovni zapis, FAQ).

Vrni kot tabelo. Seznam poizvedb:
[prilepi seznam]
```

### Analiza SERP-a za razliko od obstoječega
```
Tukaj so naslovi in meta opisi prvih 10 Googlovih rezultatov za poizvedbo
"[poizvedba]". Analiziraj jih:
1. Kateri urednikovski kot prevladuje pri večini rezultatov?
2. Kateri format prevladuje (seznam, vodič, primerjava, definicija)?
3. Katere podteme, povezane s to poizvedbo, manjkajo ali so pokrite le
   površno?
4. Na podlagi teh vrzeli predlagaj 2 diferencirana kota, ki bi ju lahko
   Meteorec ubral — z lastnimi meritvami postaje IREICA1, ne generično.

Rezultati:
[prilepi naslove + opise]
```

## 2. SEO brief za nov evergreen članek

```
Ti si urednik na Meteorecu, vremenskem blogu za Rečico ob Savinji in
Zgornjo Savinjsko dolino, ki piše izključno iz lastnih meritev postaje
IREICA1 (od 2019) in lastnih napovednih/gobarskih modelov. Iz spodnjih
podatkov sestavi celoten brief:
1. Ponovi natančen namen iskanja za to temo.
2. Predlagaj 3 diferencirane urednikovske kote glede na to, kaj že
   prevladuje v SERP-u (povzetek spodaj).
3. Zgradi H1–H3 strukturo, ki logično pokrije celotno temo.
4. Naštej vprašanja, ki jih mora vsebina odgovoriti, vključno z implicitnimi.
5. Navedi entitete in sekundarne izraze za naravno vpletanje (kraji v
   dolini, meteorološki pojmi iz /slovar/, ustrezne hub strani za notranjo
   povezavo — /nevihte/, /vodostaj-savinje/, /agrometeo/, /klima/ ipd.).

Ključna tema: [tema] | Kaj prevladuje v SERP-u: [povzetek]
Moji lastni podatki/kot (meritve, rekordi, primerjava z lansko sezono):
[prilepi]
```

## 3. Diferenciacija — iz generičnega v konkretno

```
Tukaj je odstavek, ki se mi zdi preveč generičen. Prepiši ga z uporabo
spodnjih podatkov iz `history.json`/lastnih meritev IREICA1, ne da bi
spremenil temo, a nadomesti abstraktne trditve s konkretnimi, preverljivimi
številkami:

Izvirni odstavek:
[prilepi odstavek]

Podatki za vključitev (iz history.json ali drugega vira v repozitoriju):
[prilepi]
```

## 4. Kalibracija tona

Uporabno **pred** pisanjem osnutka, ne namesto lekture — lektor (`call_lektor`)
kalibracijo tona preveri šele naknadno.

```
Tukaj sta 2 odlomka že objavljenih Meteorec člankov, katerih ton mi je
všeč (stil, ritem stavkov, register). Analiziraj, kaj ta ton označuje, nato
ga uporabi pri pisanju spodnjega briefa. Izogibaj se šablonskim prehodom
("poleg tega", "vredno je omeniti") in dobesednim prevodom iz angleščine
(kalki, prekomerni trpnik, angleški narekovaji, vezaj namesto pomišljaja —
to preverja tudi lektor, a naj se temu izogneva že osnutek). Variiraj
dolžino stavkov.

Referenčna odlomka:
[prilepi 2 odlomka]

Brief, ki naj bo napisan v tem tonu:
[prilepi brief]
```

## 5. On-page in AI-citljivost (za ročno pisane strani)

### FAQ z visoko izlečno vrednostjo
```
Iz spodnje vsebine ustvari 6 FAQ vprašanj, ki predvidevajo naslednja
vprašanja bralca, ne da bi ponavljala, kar je že v telesu članka. Za vsako
vprašanje napiši samostojen, popoln odgovor v 2–4 stavkih, razumljiv brez
preostanka strani — to je odgovor, ki bi ga lahko AI asistent izluščil
dobesedno.

Vsebina članka:
[prilepi vsebino ali povzetek]
```

### Manjkajoče entitete
```
Tukaj je članek o [tema]. Identificiraj pomembne entitete (kraje v dolini,
meteorološke pojme, ARSO/Open-Meteo/ECMWF, sorodne pojme iz /slovar/), ki
so običajno povezane s to temo, a v trenutnem besedilu ne nastopajo. Za
vsako manjkajočo entiteto navedi, kje in kako jo naravno vključiti.

Pomni: nova entiteta (Person/Organization/Place s sameAs) gre v skupni
register `PLACE_SAMEAS` v tools/generate_monthly_post.py, ne kot vtipkan
niz na novem mestu (glej CLAUDE.md, razdelek GEO).

Članek:
[prilepi vsebino]
```

### JSON-LD — SAMO za ročno pisano stran, ki je noben generator ne piše
```
Ustvari veljaven JSON-LD za to stran, tip [Article / FAQPage / HowTo].
Uporabi samo informacije, ki so eksplicitno navedene v spodnji vsebini — ne
izmišljuj avtorja, datuma ali ocene, ki je nisem podal. Označi vsako
obvezno polje, ki ga iz vsebine ne moreš zapolniti.

Vsebina strani:
[prilepi]
Manjkajoča polja, ki jih bom dopolnil ročno: [avtor, datum ...]
```

### Preoblikovanje obstoječega članka za AI-citljivost
```
Tukaj je obstoječi Meteorec članek. Preoblikuj ga za maksimalno citljivost
pri AI asistentih, brez spremembe vsebine:
1. Vsak razdelek naj se začne z neposrednim odgovorom, šele nato razlaga.
2. Podnaslove preoblikuj v eksplicitna vprašanja, kjer je smiselno.
3. Označi odstavke, ki so razumljivi le v kontekstu prejšnjega odstavka, in
   jih prepiši, da stojijo samostojno.
4. Označi vsako nejasno trditev, ki bi jo moral zaostriti s konkretnim
   podatkom iz history.json.

Po uporabi te predloge na že objavljenem članku: poženi `lektura.yml` z
`slugs=<slug>`, da se `dateModified`/`updated` pravilno posodobita.

Članek:
[prilepi]
```

## 6. Meritev, prioritizacija, arhiv

### Analiza Search Console izvoza
```
Tukaj je izvoz iz Google Search Console (strani, poizvedbe, impresije,
kliki, CTR, povprečna pozicija) za zadnje 3 mesece na meteorec.si. Analiziraj
in:
1. Označi strani na poziciji 8–20 (quick-win priložnost, blizu prve strani).
2. Označi strani z CTR bistveno pod povprečjem za njihovo pozicijo.
3. Označi opazen padec impresij na strani, ki jih je prej imela bistveno več.
4. Predlagaj prioritiziran akcijski načrt za največ 5 strani.

Izvoz:
[prilepi podatke]
```

### Odločitev nova stran vs. konsolidacija
Dopolnitev k `tools/content_health_audit.py`, ki kanibalizacijske pare že
najde po TF-IDF podobnosti (razdelek `KONSOLIDIRAJ` v poročilu) — ta prompt
je za kvalitativno odločitev na tistem seznamu.

```
Ta dva članka na Meteorecu se lahko kanibalizirata za podoben namen
(izpis `tools/content_health_audit.py` spodaj). Priporoči, ali ju
konsolidirati v enega (s 301 preusmeritvijo drugega) ali ju obdržati
ločena, in odločitev utemelji glede na prekrivanje namena in porazdelitev
prometa/notranjih povezav.

Par: [slug A] / [slug B]
Izpis pregleda: [prilepi vrstico iz KONSOLIDIRAJ]
```

**POZOR** (enako kot v vodiču): nobenega članka ne pobriši ali preusmeri
samo na podlagi tega odgovora — najprej ročno preveri povratne povezave in
netipične poizvedbe v Search Console. Enako velja za izpis
`content_health_audit.py` — glej opozorilo v glavi tega orodja.

### Mesečno poročilo
```
Iz spodnjih podatkov (organski promet, povprečna pozicija in konverzije to
mesec vs. prejšnji mesec) napiši jedrnato poročilo. Strukturiraj v 4 dele:
3-stavčni povzetek, ključni dogodki meseca, verjetna razlaga sprememb,
načrtovane akcije za naslednji mesec.

Podatki:
[prilepi ključne številke]
```

## 7. Kontrola kakovosti pred objavo

### Fact-check pregled
```
Preglej ta osnutek in označi vsako faktično trditev, statistiko ali
poimenovan vir, ki potrebuje ročno preverjanje pred objavo — brez
prepisovanja same vsebine.

Osnutek:
[prilepi osnutek]
```

### Detektor generične vsebine
```
Oceni ta osnutek od 1 do 10, kako generično oz. diferencirano se bere, in
oceno utemelji s konkretnimi stavki, ki bi se brali enako na kateremkoli
konkurenčnem vremenskem viru (ARSO, Windy, splošne vremenske aplikacije) —
brez sklicevanja na lastne meritve postaje IREICA1 ali lastne modele.

Osnutek:
[prilepi osnutek]
```

## 8. Odločanje

### Matrika vpliv/napor
```
Tukaj je [n] kandidatnih SEO/vsebinskih akcij z grobo oceno vpliva (1-5) in
napora (1-5): [prilepi seznam]. Razporedi jih v matriko vpliv/napor 2×2,
navedi, v kateri kvadrant sodi vsaka, in priporoči 5, ki naj se izvedejo ta
mesec.
```

---

## Kaj namenoma NI vključeno

Nekateri prompti iz splošnega vodiča za Meteorec niso relevantni in tu niso
vključeni: pregled Google Business Profile in odzivov na ocene (Meteorec ni
lokalno podjetje s fizično lokacijo, ki bi jo obiskovalci ocenjevali),
pregled/nakup povratnih povezav (ni link-building ekipe, glej razdelek
Avtoriteta v splošnem vodiču le kot ozadje), gradnja panela za sledenje AI
vidnosti (to je že `docs/geo-prompt-panel.md`, ne podvajaj tukaj).
