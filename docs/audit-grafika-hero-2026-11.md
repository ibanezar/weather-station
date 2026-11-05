# Audit grafične podobe in hero kartic (4. 11. 2026)

Drugi audit po `docs/redesign-qa.md` (21. 10.). Tisti je meril Lighthouse in kontrast po prenovi; ta gleda **oblikovalsko skladnost in berljivost hero kartice** (`.hero-b`, junaška kartica na naslovnici) ter okolice nad njo.

## Kako je bilo merjeno

- Živa stran `https://meteorec.si/` z živimi podatki, 4. 11. 2026 ob ~21.30 po naši uri (noč, megla/oblačno, brez dežja).
- Playwright + Chromium: 390 px (2×), 320 px, 1280 px; temna in svetla tema; posnetek `.hero-b` s skritimi lepljivimi elementi (ARSO pasica, spodnja navigacija) in z odprtim »Več podrobnosti«.
- axe-core 4.10.2 (wcag2a/aa, 2.1 aa, 2.2 aa) samo na `.hero-b`, DOM meritve pisav, polmerov, tap-ciljev.
- **Meje:** ena vremenska situacija (noč, brez padavin, brez nevihte/snega); poskusi z dnevnim stanjem, alarmom in snegom niso narejeni. Preprost pogled in prvi obisk (pasica, ponudba pogleda) nista pregledana. Barvne preslikave `data-wx` za dež/sneg/nevihto so ocenjene iz kode, ne iz posnetka.

## Povzetek

Zasnova (ploščice, glava z ikono, lestvice, graf »Danes«) je dobra in na namizju (1280 px) deluje kot celota. Ni težav z razlitjem na 320 px. Težave so v **podrobnostih, ki kvarijo zaupanje**: ena napačna ikona, ena protislovna vrstica, ena prazna vizualizacija, kontrasti v svetli temi in brez pravega tipografskega merila. Nobena ni velika; skupaj jih je za en popravljalni krog.

## P0: popravi najprej

### 1. Ikona stanja kaže sonce ponoči in ne ustreza oznaki
Hero kartica ob 21.30, vlaga 99 %, oznaka **»Oblačno«**, ikona **`fog-day.svg`** (sonce nad meglo).
Vzrok: `_condImg()` (`app.js:7391`) bere `_WXCOND_ICON[_wxCond]`, kjer je `fog → 'fog-day'`. Ključ `'fog-night'` v preslikavi obstaja, a ga `_wxCond` nikoli ne postane (obe mesti, ki ga računata, `app.js:11612` in `:11948`, vrneta samo `'fog'`). Pogoj je `hum>91 && wind<5 && uv<1`, kar je ponoči skoraj vedno res, zato ponoči vlažna noč pomeni sonce. Datoteka `icons/weather/fog-night.svg` obstaja.
Predlog: ponoči `fog-night`; in če je oznaka »Oblačno«, ikona ne sme biti megla (ali pa oznaka »Megleno«). Ikona in oznaka naj prideta iz iste odločitve.

### 2. Ploščica »Padlo danes« si nasprotuje
Isti kvadrat pravi hkrati: `6,3 mm` · `napoved: suho` · `MTR: dež 85 % · ~2,0 mm · ≥ 5 mm 5 %`. Pod njo pa ploščica »Dež: Ne kaže, verjetnost 0 %«. Berljivo kot trije različni odgovori na isto vprašanje. Najverjetneje MTR vrstica govori o celotnem (že mimo) današnjem dnevu, `napoved: suho` o preostanku dneva, `Dež` o naslednjih 24 h, a tega bralec ne more vedeti.
Predlog: ena časovna os na ploščico. V ploščici samo »v preostanku dneva: suho«; MTR (ki ga drži zamrznjena dnevna napoved) umakni, ko je dan že večinoma mimo, ali ga označi z »za cel dan«. Na 320 px se vrstica zlomi v štiri kratke vrstice.

### 3. Vrstica pod številko dežja je prazna in laže z obliko
Pod `6,3 mm` je siva proga brez polnila. Kodira trenutno intenziteto (0 mm/h), ne količine, ki je tik nad njo. Oko prebere »6,3 od česa? skoraj nič«.
Predlog: ali nariši polnilo za današnjo vsoto (z oznako, kaj je poln pas), ali progo skrij, dokler ne dežuje, ali jo označi (»zdaj 0 mm/h«), ker ta napis že obstaja pod njo.

### 4. Kontrast v svetli temi pade (axe, serious)
| Element | Kontrast | Cilj |
|---|---|---|
| ure v grafu »Danes« (`15`, `18`), pretekle ure | 2,26 | 4,5 |
| temperature preteklih ur (`6,5°`, `5,9°`) | 3,49 | 4,5 |
| gumba »Poslušaj vreme«, »Deli karto« (besedilo `#5b6b60` na `#0ea5e9`) | **2,03** | 4,5 |
Temna tema: samo ure `15`, `18` pri 4,23 (skoraj).
Gumba sta prosojna na živo modri podlagi svetle teme: `.sc-btn` (`style.css:2934`) ima `background:transparent` in `color:var(--muted)`; v svetli temi je `--bg:#0ea5e9`, kar je samo za kartice rešeno z belo podlago, za gumba pa ne. Predlog: v `.hero-b` gumbu daj lastno podlago kartice ali temno besedilo.
Pretekle ure so namerno utišane; utišanje naj ostane, a pri `--muted` z višjo kromo, ne z manjšo prekrivnostjo (isto pravilo kot v `CLAUDE.md`, »Kontrast«).

### 5. Emoji in decimalna pika še vedno v prikazu podatkov
- Vrstica nad hero (`app.js:2450`, `:2456`): `📊 Tlak: 1029 hPa`, `🌧 Padavine danes: 6.3 mm`. **Pika namesto vejice** (`toFixed(1)`), v sosednji ploščici je `6,3`. Podvaja tlak in padavine iz hero ploščic nekaj centimetrov nižje.
- Noga hero kartice: `❄️` pred »3. 11. letos 1. najhladnejši …« (v temni temi okrogla ikona, v svetli skoraj nevidna).
Pravilo v `CLAUDE.md` (»Brez emojijev v prikazu podatkov«) je to izrecno prepovedalo. Predlog: ikone iz SVG sklada, `toLocaleString('sl-SI')` ali obstoječa funkcija za formatiranje števil, in ukinitev vrstice, če podvaja ploščici.

## P1: kmalu

### 6. Tipografsko merilo ne obstaja
V hero kartici je **18 različnih velikosti pisave**, med 10 in 14 px kar deset: 10,5 / 10,56 / 10,88 / 11,2 / 11,84 / 12 / 12,48 / 12,8 / 13,12 / 13,6. Skoraj vse so `rem` z dvomestnimi desetinkami (`.61rem`, `.65rem`, `.68rem`).
**~40 besedilnih vozlišč je pod 12 px**: ure v grafu (10,56), temperature v grafu (11,2), `km/h` (11,2), gumba »Poslušaj«/»Deli« (10,88), oznaka `NE` (9,92), oznaka »↑ 8,1° · jutri« (10,5).
Predlog (5 stopenj): 12 / 13 / 15 / 24 / 48+ ter eno mesto za številčne oznake. Pod 12 px ne gre nič, kar nosi podatek.

### 7. Barvni kanal temperature = barva znamke
Temperatura je **cian z žarenjem** (izmerjeno `#67e8f9`, `text-shadow` 40 px), `rec` v logotipu je `#22d3ee`, enak odtenek družine ima tudi aktivni zavihek in gumb »Napredno«. Cian pri 5,7 °C pomeni »hladno«; v poletni vročini bo oranžno, torej bo isti element menjal barvo, znamka pa ostaja cian. Dve vlogi skoraj iste barve, in žarenje ob številki je najmočnejši efekt na strani.
Predlog: znamko drži v zeleno-modrem registru, barvno skalo temperature pa označi kot podatkovno barvo (legenda ali skala pod številko). Žarenje zmanjšaj pri majhnih podatkovnih številkah (pod 30 px) in pusti samo na glavni številki.

### 8. Vse ploščice so enako močne
Glavna ploščica, »Danes«, štiri meritve, noga in hitra vprašanja imajo **enak videz** (`rgba(12,18,32,.85)`, rob 1 px belo 10 %, polmer 20 px, enaka senca). Hierarhijo prenaša samo velikost. Na telefonu je hero kartica 1361 px, torej 1,6 zaslona, in oko ne ve, kje je središče po prvi številki.
Predlog: glavni ploščici (temperatura + »Danes«) daj močnejšo podlago, štiri meritve pa lažjo (brez roba ali brez sence). Eno raven poudarka, ne tri.

### 9. Pet različnih gradientnih lestvic v petih ploščicah
Vlaga (rjavo→modro), veter (zeleno→rumeno→rdeče), tlak (vijolična), UV, luna (rumena). Veter z rdečim koncem sporoča nevarnost, a meja 0–50 km/h je izbira prikaza (`CLAUDE.md`). Vlaga 99 % je pri koncu rjavo→modre lestvice s križcem, kar ne pove, ali je to »veliko« ali »nasičeno«.
Predlog: ena sekvenčna lestvica za vrednosti (svetlo→temno ene barve), semantična (rdeča/rumena/zelena) samo tam, kjer obstaja prag (UV, PM). Vlaga in tlak sta »neutralna«.

### 10. Graf »Danes«: črta v drugi barvi kot številka, najvišja je jutrišnja
- Črta je bledo zeleno-siva, številka cian, oznake bele. Isti podatek v treh barvah, črta je najšibkejša.
- Pod naslovom »Danes do približno 6 °C« je oznaka **»↑ 8,1° · jutri 13:00«**. Namerno (`CLAUDE.md`: zvečer je najtoplejša ura že jutri), a naslov in oznaka sta si na pogled v nasprotju. Predlog: naslov »Naslednjih 24 ur«, ko dnevni vrh ni več v današnjem dnevu.
- V svetli temi so ikone oblakov v stolpcih **skoraj nevidne** (bel/siv oblak na beli ploščici), prav tako ikona sonca v glavni ploščici in `❄️` v nogi.

### 11. Sosednja postaja v hero kartici (PM2,5 Varpolje)
V razširjenem delu ploščica »PM₂,₅ · Varpolje **215,0** µg/m³, Nevarno« je v vijolični, brez lestvice, medtem ko imajo vse druge ploščice lestvico. Hero je podpisan z IREICA1, ploščica je sosedova (`CLAUDE.md`: gost, ne referenca). 215 µg/m³ je izjemna vrednost, ki jo je smiselno **obdati z virom in časom** (»Varpolje, senzor sosedove postaje, pred N min«) in z lestvico, da je primerljiva z drugimi.

## P2: poliranje

12. **Streaki na levem robu glavne ploščice.** Na vseh treh velikostih se v zgornjem levem delu vidijo vodoravne mrene meglene teksture, ki izgledajo kot napaka izrisa (pretrgana tekstura ob robu). Brez tega bi bila ploščica čistejša. Vzrok nisem preveril; prvi sumljivec je risanje na platnu (`#hero-canvas`) ob levem robu.
13. **Glava nad hero je težka**: do prve ploščice je **~535 px** (logotip, pila s postajo, 4 pilule, preklopnik pogleda, vrstica stanja, 3 gumbi, zavihki, pas z vsebino). Temperatura se začne pri ~595 px na 844-pikselskem zaslonu, torej v spodnji tretjini; z ARSO opozorilom pasica to še potisne. Preklopnik pogleda in vrstica gumbov bi se dala združiti v eno vrstico.
14. **Tap-cilji**: »Poslušaj vreme«, »Deli karto« in povezava MTR so visoki 30 px (pod 44 px, kolikor priporočata Apple in Material; WCAG 2.2 AA zahteva 24 px, torej ni kršitev, na `/valovi/` pa `CLAUDE.md` že predpisuje ≥ 48 px). Na 320 px se gumba prelomita v dve neporavnani vrstici.
15. **Polmeri**: 20, 16, 14, 13, 30, 50, 99, 999 px in 50 %. Dovolj bi bili 12 / 20 / pilula.
16. **Skok vrstice »verjetnost 0 %«** na 320 px: znak `%` pade v novo vrstico (nedeljiv presledek `&nbsp;` med številom in `%`).

## Kaj deluje (ne spreminjaj)

- Glava ploščic z ikono v barvnem čipu (`.hm-ic`) in vrednost nad lestvico: berljivo, enotno.
- Graf »Danes« s stolpci po 3 ure in vlečenjem: najboljši del hero kartice; ostane brez spremembe, razen barv (točka 10).
- Hitra vprašanja (Zmrzal/Dež/Megla): čista struktura, stanje (Da/Blizu/Ne) je v oznaki, ne samo v barvi.
- Razmerja na namizju (1280 px): mreža 2 + 2 ploščici z mini grafi je lepša kot telefonska različica; ploščice na namizju so »polne«, na telefonu so humidity in wind prazne spodaj (~60 px zraka) in bi jih bilo bolje skrajšati.
- Dostopnost v temni temi je praktično čista (axe: samo dve vrstici ob 4,23).

## Predlagan vrstni red dela

1. Ikona stanja ponoči (točka 1), vejica/emoji v pasu (5), kontrast gumbov in ur v svetli temi (4): vsaj tri ure dela, vidno takoj.
2. Ploščica dežja: ena časovna os + proga (2, 3).
3. Tipografska lestvica (6) in barvna vloga temperature (7): to je odločitev za Filipa, ne samo popravek.
4. Hierarhija ploščic (8) in lestvice (9) skupaj, ker se dotikata istega CSS bloka (`.hm`).
5. Po vsaki spremembi: `npm run minify && node tools/critical_css.mjs` (`CLAUDE.md`, kritični CSS je izpeljan), nato meritev CLS pod omejitvijo omrežja (3 teki).

## Odprta vprašanja za Filipa

- Je temperatura v ciana z žarenjem namerna znamčna poteza, ali naj postane podatkovna barva (točka 7)?
- Ali naj `MTR: dež …` ostane na ploščici dežja čez dan, ali samo zjutraj (točka 2)?
- Pila MeteoGobar / Črnivec / MeteoZima: so pred hero kartico po sili ali po izbiri (točka 13)?

## Stanje popravkov (4. 11. 2026)

Narejeno: točke 1–16 (commiti na veji `claude/vigilant-carson-lm96r2`; opis v `CLAUDE.md`, razdelki »Ikona stanja …«, »Ploščica »Padlo danes« …«, »Tipografska lestvica hero kartice« in »Graf »Danes«, PM₂,₅, megla, tap-cilji, polmeri«).

- **13 delno:** glava je 16 px nižja (po izbiri pogleda je podnapis gumbov skrit na ≤ 560 px), preklopnik pogleda in vrstica obvestil nista združena (to je odločitev o postavitvi, ne popravek). Temperatura začne pri ~519 px (390 px) oz. ~543 px (320 px) namesto ~535 px.
- **Ugotovljeno ob merjenju, ni popravljeno:** na 1280 px CLS niha 0,11 ali 0,35–0,40 (`ticker-wrap` skoči za ~36 px navzgor ob ~1,1 s, `title-row` 102→100 px). Enako na neprilagojeni različici (preverjeno s `git stash`), torej ni posledica teh popravkov; vzrok je v glavi na namizju (verjetno zamenjava pisave ali prihod celotnega CSS).
