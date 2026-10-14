# Osnutek: napoved se v dolini zmoti v isto smer

Stanje: **osnutek za Filipa**, ni objavljen, ni v `blog.json`, brez lekture (`lektura.yml` je izklopljena od 2. 10. 2026). Pisano po `docs/slog-pisanja.md`.

**Vse številke so že izračunane in preverjene** (skript `tools/study_napoved_po_dneh.py` → `data/napoved-po-dneh.json`; ponovljivo z `python3 tools/study_napoved_po_dneh.py`). Pred pisanjem sem preveril, da jedro trditve drži, ne po njem.

## Naslov (izbira)

1. **Zakaj je napoved podnevi prehladna? 866 dni testa** (50), priporočam
2. **Napoved se pri nas zmoti v isto smer** (38), nevtralnejši
3. **Ali sedmi dan napovedi sploh kaj velja?** (39), za iskalnike »vreme 14 dni«

**Meta opis (≤ 160 znakov):** Svetovna modela sta za Rečico jutri podnevi v 8 od 10 dni prehladna. En popravek zmanjša napako za 40 %. Preverili smo 866 dni meritev postaje.

---

## Besedilo

**Kratek odgovor: napoved ni slaba, ampak ne pozna dna doline.** Model ECMWF IFS je za jutri v Rečici podnevi prenizek v 86 % dni, v povprečju za 1,9 °C. Model GFS je ponoči previsok v 84 % dni, v povprečju za 2,6 °C. Napaka gre skoraj vedno v isto smer, zato jo je mogoče popraviti. En sam popravek zmanjša napako jutrišnje najvišje temperature z 2,2 na 1,3 °C.

Poznate občutek, da je pri vas podnevi toplejše, kot piše na telefonu? Tokrat sem ga preveril na podatkih.

### 01 — Kaj smo primerjali

Napovedi sta dva svetovna modela, ECMWF IFS in GFS, v obliki, kot ju prikazuje Open-Meteo: kaj sta model napovedala 1 do 7 dni prej. Meritev je postaja IREICA1 v Rečici ob Savinji. Primerjava obsega 866 dni, od 26. maja 2024 do 12. oktobra 2026. Izhodišči sta dve preprosti »napovedi«: povprečje za ta datum v drugih letih (klimatologija) in »enako kot pred toliko dnevi« (persistenca). Model je koristen le, če ju premaga.

### 02 — Smer napake

| Jutrišnja napoved | IFS | GFS |
|---|---|---|
| Najvišja temperatura: povprečna napaka | −1,9 °C | −1,3 °C |
| … delež dni, ko je model prenizek | 86 % | 79 % |
| Najnižja temperatura: povprečna napaka | +1,3 °C | +2,6 °C |
| … delež dni, ko je model previsok | 73 % | 84 % |

Model torej v dolini podnevi podcenjuje vročino, ponoči pa hlad. Pri najvišji temperaturi je pristranskost IFS −1,2 do −2,3 °C v vseh štirih letnih časih (največja poleti). Pozimi sta pristranskost IFS pri najnižji temperaturi (+0,2 °C) in pristranskost GFS pri najvišji (−0,2 °C) majhni.

Verjeten razlog je geografski: modelska celica je velika več kilometrov, dolina Savinje pa je ozka. Ponoči se hladen zrak steka na dno doline, podnevi se dno hitreje segreje. Tega model v povprečni celici ne vidi. To je razlaga, ne dokaz.

### 03 — En popravek

Ker napaka gre v isto smer, jo lahko odštejemo. Popravek je ena številka za vsak vodilni čas, izračunana na **drugih letih**, ne na dnevu, ki ga ocenjujemo:

| Povprečna napaka (°C) | surovo | s popravkom | klimatologija |
|---|---|---|---|
| IFS, Tmax, jutri | 2,2 | 1,3 | 3,5 |
| IFS, Tmax, čez 3 dni | 2,3 | 1,5 | 3,5 |
| IFS, Tmax, čez 5 dni | 2,5 | 1,9 | 3,5 |
| IFS, Tmin, jutri | 2,0 | 1,7 | 2,8 |
| GFS, Tmin, jutri | 3,0 | 2,1 | 2,8 |

GFS je ponoči v dolini surov slabši od preprostega »kot običajno za ta datum« (3,0 proti 2,8 °C), s popravkom pa ga premaga. Zato je smiselno ločiti dve vprašanji: ali je model pameten in ali je model prilagojen vašemu kraju.

### 04 — Sedmi dan

Kako hitro napoved izgublja vrednost? Delež dni, ko se najvišja temperatura zmoti za več kot 3 °C:

| Vodilni čas | IFS | GFS | »kot običajno« |
|---|---|---|---|
| jutri | 24 % | 19 % | 51 % |
| čez 3 dni | 26 % | 25 % | 51 % |
| čez 5 dni | 33 % | 29 % | 51 % |
| čez 7 dni | 42 % | 37 % | 51 % |

Sedmi dan je torej še malo boljši od povprečja, a ne veliko. Pri nočni temperaturi 6. in 7. dne model **ni boljši** od povprečja za ta datum (povprečna napaka IFS 2,9 oziroma 3,0 °C, GFS 3,1 oziroma 3,2 °C, »kot običajno« 2,8 °C).

Za dež je slika podobna. Če je IFS sedem dni vnaprej napovedal dež, ga v 43 % primerov ni bilo (padlo je manj kot 0,2 mm). Za jutri je takih zgrešenih alarmov 29 %.

Preprosto »enako kot danes« tudi ni dobra rešitev. Že za tri dni naprej je napaka najvišje temperature (4,0 °C) večja kot pri povprečju za ta datum (3,5 °C).

### 05 — Česa ne vemo

- **Samo dva modela in 2,4 leta.** Arhiv napovedi sega do maja 2024. V daljšem obdobju se pristranskost po letnih časih lahko drugače porazdeli.
- **Popravek je preprost**: ena številka na vodilni čas, ne glede na letni čas ali vremenski položaj. Boljši popravek je lahko boljši, to je delo modela MTR.
- **Za več kot 7 dni nimamo preverjenih napovedi.** Ali sta 10- in 14-dnevna napoved v dolini uporabni, iz teh podatkov ne vemo. Trend pada, zato ni razloga, da bi pričakovali čudež.
- **Padavine** so ocenjene samo s pragom 0,2 mm (kakršen koli dež) in ne povedo nič o količini.

### 06 — Kaj naj naredite

Brez računanja: podnevi pričakujte v Rečici nekoliko več, kot piše v aplikaciji, ponoči nekoliko manj. To pravilo velja za naš kraj in ta dva modela, za vaš kraj ne nujno. Naš [napovedni model MTR](/primerjava-modelov/) naredi to popravljanje sam, [semafor točnosti](/tocnost-napovedi/) pa kaže, kako se odreže v primerjavi z ARSO in Open-Meteo. Vse primerjave modelov so na strani [test napovedi](/test-napovedi/).

*Podatki: postaja IREICA1 (history.json), Open-Meteo Previous Runs (ECMWF IFS, GFS). Primerjava 26. 5. 2024–12. 10. 2026, 866 dni.*

---

## Opombe za Filipa (ne gredo v članek)

- **Zakaj ta ideja drži:** trditev sem preveril, preden sem pisal. Smer napake je enaka v 79–86 % dni in v vseh štirih letnih časih za IFS Tmax; popravek je ocenjen na drugih letih, torej ni v-vzorcu prilagojen; izhodišča so poštena za vsak vodilni čas (v `test-napovedi.json` je persistenca samo D+1, tu sem jo izračunal za D+k).
- **ICON je izpuščen namenoma:** nima D+7, med D+1 in D+2 pa je v arhivu sumljiv skok napake Tmin (1,5 → 2,4 °C), verjetno artefakt. Ne bi se zanesel nanj. ICON je pri jutrišnji Tmax najboljši (1,4 °C), to lahko dodaš kot opombo.
- **Prekrivanje:** `/test-napovedi/` že pokaže pristranskost, mesečni članki objavljajo MAE in zmagovalca. Novo je (a) pošteno »kot danes« za D+k, (b) en popravek, naučen na drugih letih, (c) sedmi dan z deležem napak > 3 °C, (d) smer napake po dnevih in letnih časih. Zgodbo bi bilo lepo povezati z vprašanjem bralcev »vreme Rečica 14 dni« (po `CLAUDE.md` poizvedba s prikazi); a o 14 dneh podatkov nimamo in je tako napisano.
- **Dve trditvi preverjam še enkrat pred objavo:** »1,9 °C povprečna napaka« je D+1 za IFS iz arhiva (JSON: −1,86); »2,6 °C GFS ponoči« (+2,58).
- **Dodati:** vrstico »Uporaba vsebine« (CLAUDE.md), `seo-preflight`, ročni slogovni pregled. 
- Skript in `data/napoved-po-dneh.json` sta commitana, da so številke ponovljive. Skripta ne poganja noben workflow.
