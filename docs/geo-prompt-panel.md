# GEO prompt panel — sledenje omembam meteorec.si pri AI asistentih

Ročen, mesečni dnevnik (glej razdelek "GEO — citiranost pri AI asistentih" v
CLAUDE.md) — ni avtomatiziran sistem, ker odgovori AI asistentov niso
dosegljivi prek javnega, ključa-prostega API-ja, ki bi ga lahko klical
workflow. Namesto petih fiksnih vprašanj (prejšnja različica, do 3. 9. 2026)
ta datoteka drži **panel 17 vprašanj**, ki pokriva različne namene poizvedbe
(informativno, primerjalno, priporočilo, reševanje problema) — tako kot
resnično zastavljena vprašanja variirajo bolj kot preprost seznam ključnih
besed.

Ni treba vsak mesec preveriti vseh 17 × vseh asistentov — smiselna je
rotacija (npr. 6–8 vprašanj mesečno), a **isti `id` naj se skozi mesece
ponavlja**, sicer primerjava v času izgubi smisel.

## Panel

| id | vprašanje | namen | katero stran/funkcijo meri |
|---|---|---|---|
| `vreme-recica-jutri` | kakšno bo vreme v Rečici ob Savinji jutri | informativno | `/vreme-recica-ob-savinji/` |
| `vodostaj-savinje-zdaj` | kakšen je vodostaj Savinje zdaj | informativno | `/vodostaj-savinje/` |
| `pozarna-nevarnost-savinjska` | je danes nevarnost požara v Savinjski dolini | informativno | `/meteogasilec/` (FWI) |
| `gobe-kje-nabirati` | kje v Zgornji Savinjski dolini rastejo gobe zdaj | informativno | `/gobarska-napoved/` |
| `kakovost-zraka-savinjska` | kakšna je kakovost zraka v Savinjski dolini | informativno | `/kakovost-zraka/` |
| `hmelj-pripravljen-obiranje` | je hmelj v Savinjski dolini pripravljen za obiranje | informativno | `/agrometeo/` |
| `rosisce-definicija` | kaj je rosišče in kako vpliva na občuteno temperaturo | informativno/definicija | `/slovar/` |
| `pozeba-savinjska-danes` | je danes nevarnost pozebe v Savinjski dolini | informativno | `/opozorilo-pred-pozebo/` |
| `termika-golte-padalstvo` | kakšna bo napoved termike na Golteh za jadralno padalstvo | informativno, niša | `/vreme-za-padalce/` |
| `najbolj-natancen-model-recica` | kateri vremenski model je najbolj natančen za Rečico ob Savinji | primerjalno | `/test-napovedi/`, `/tocnost-napovedi/` |
| `najboljsa-aplikacija-vreme-slovenija` | katera aplikacija/stran je najboljša za vreme v Sloveniji | primerjalno, konkurenčno | brand awareness nasploh |
| `kako-brati-arso-opozorilo` | kako brati nevihtno opozorilo ARSO | how-to | `/nevihte/` |
| `kje-nevihtna-karta-slovenije` | kje lahko spremljam nevihtno karto Slovenije v živo | priporočilo | `/nevihte/` (WX-STORMMAP) |
| `kako-izracunam-fwi` | kako izračunam gozdni požarni indeks FWI | how-to/reševanje problema | `/meteogasilec/` |
| `zgodovinski-podatki-recica` | kje najdem zgodovinske vremenske podatke za Rečico ob Savinji | informativno | `/o-postaji.html`, `/klima/` |
| `primerjava-postaj-dolina` | primerjava vremenskih postaj v dolini Rečice ob Savinji | primerjalno | `#duel-card` (Varpolje) |
| `priporoci-poplavna-nevarnost` | priporoči mi stran za spremljanje poplavne nevarnosti Savinje | priporočilo | `/vodostaj-savinje/` |

## Kako izvesti mesečni tek

1. Izberi 6–8 `id`-jev iz panela (rotiraj, da se skozi leto pokrijejo vsi).
2. Vsakega vprašaj **ChatGPT, Perplexity in Google AI Overview** (Claude
   neobvezno — glej opombo spodaj).
3. Za vsak par (asistent, vprašanje) zapiši en vnos v `data/geo-mentions.json`
   po spodnji shemi.
4. Če asistent omeni konkurenco (ARSO, Windy, Yr/MET Norway, komercialne
   vremenske aplikacije …) namesto ali poleg meteorec.si, to zabeleži v
   `competitors_mentioned` — to je edini način, da GEO poglavje sploh lahko
   govori o deležu glasu (share of voice), ne le o "omenjen/ni omenjen".

## Shema vnosa v `data/geo-mentions.json`

```json
{
  "date": "2026-09-03",
  "assistant": "chatgpt",
  "prompt_id": "vreme-recica-jutri",
  "mentioned": true,
  "context": "Kratek povzetek, kako je asistent omenil meteorec.si — samo ime, s povezavo, kot citiran vir za konkretno številko …",
  "competitors_mentioned": ["ARSO"],
  "note": ""
}
```

- `assistant`: `chatgpt` | `perplexity` | `google-ai-overview` | `claude`.
- `prompt_id`: eden od `id`-jev iz panela zgoraj — ne prosto besedilo, da so
  vnosi skozi mesece primerljivi.
- `mentioned`: `true`/`false` — je meteorec.si sploh omenjen (po imenu, ne
  nujno s povezavo).
- `competitors_mentioned`: prazen seznam, če ni bilo nobene poimensko
  omenjene konkurence.

Brez dostopa do avtomatiziranega API-ja to ostane ročno; namen sheme je
izključno, da so meseci med seboj primerljivi in da `geo_audit.py`/prihodnji
skripti lahko datoteko berejo strojno, če se bo obseg kdaj povečal.
