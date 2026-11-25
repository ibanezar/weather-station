# SEO raziskava »Zima in sneg« 2026/27: povzetek in stanje izvedbe (25. 11. 2026)

Vir: `meteorec_seo_raziskava_zima_sneg_2026_27.pdf` (OpenRush, slovenski trg, 25. 11. 2026). **Obsegi iskanj so ocene in zaokrožene vrednosti, niso podatki GSC**; številke (82 ključnih besed, 25 v Top 10, 241 obiskov/mesec) so modelirane. Pred končno razporeditvijo preveri GSC (prikazi, kanibalizacija, indeksacija).

## Poizvedbe iz raziskave (iskanj/mesec, ocena)

sneg 27.100 (mešan namen, ni cilj) · **meja sneženja 5.400** · prihaja sneg 880 · rahlo sneženje 880 · snežna odeja 390 · sneg danes 390 · snežne razmere na smučiščih 390 · Rogla snežne razmere v živo 390 · sneg Slovenija 320 · vreme Golte 2.900 (obstoječa uvrstitev ~19.) · kamere: Kredarica 8.100, Ljubelj 6.600, Planica 4.400, Golte 4.400, Velika planina 3.600, Kriška gora 2.900, Črnivec 1.300 · smučišča: Kope 1.900, Rogla 1.900, Kranjska Gora 1.600, Višarje 1.600, Golte 1.000.

## Stanje po prioritetah iz poročila

| Prioriteta | Naloga | Stanje |
|---|---|---|
| P1 | Meja sneženja: naslov, uvod, FAQ, razširitev, povezave | **Narejeno** (naslov »Meja sneženja danes in jutri: do katere višine bo snežilo«, tabeli po dnevih in po krajih, razdelek o zanesljivosti, 8 FAQ). **Popravljena številka**: stran je kazala surovo ničto izotermo (glej spodaj). |
| P1 | Snegofili: moduli, FAQ | Naslov »Snegofili: sneg v Sloveniji, kamere in napoved«, opis ≤ 160, 3 nova FAQ (koliko snega, kje sneži, kje bo največ), povezave na mejo sneženja in snežno karto. Moduli iz poročila (koliko snega, kje sneži, kje bo največ, kamere) na strani že obstajajo. |
| P1 | Snežna karta: naslov, uvod, opisi, FAQ | Naslov »… kje sneži in koliko snega bo zapadlo«, razdelek »Kje bo snežilo in koliko snega bo zapadlo?«, 4 nova FAQ. Opis ne tekmuje več za »meja sneženja« (kanibalizacija 14. 11.: obe strani poz. 8–9, 0 klikov). |
| P1 | Višina snega: ali potrebuje svojo stran? | **Odločitev: ne zdaj.** Izmerjeno odejo imamo samo za 3 postaje ARSO v dolini (modul »Izmerjena snežna odeja« na Snegofilih); `/zima/snezna-odeja/` je modelska ocena. Samostojna stran bi bila tanka. Ponovno oceni, ko je v GSC viden obseg za »višina snežne odeje«. |
| P1 | Vreme Golte | Naslov in h1 `/vreme-v-gorah/` vodita z »Vreme Golte …«, blok »Sneg na Golteh« (modelski nov sneg iz `data/snegofili.json`, samo svež posnetek), 2 FAQ. Ločene strani `/vreme-golte/` NI (kanibalizacija z obstoječo stranjo). |
| (hub) | Zima kot osrednja stran | Naslov »MeteoZima: zimske razmere, meja sneženja, poledica«, usmerjevalnik »Zimske razmere: kaj iščete?«, 2 FAQ o razliki med mejo sneženja, snežno karto in Snegofili. |
| P2 | Smučišča (Golte, Rogla, Krvavec, Vogel, Kranjska Gora, Kope, Velika planina, Kanin) | **Ni narejeno.** Točke obstajajo na Snegofilih (razen Kope in Višarje), a brez višine podlage in odprtosti smučišč (nimamo vira, ki ga smemo brati samodejno). Samostojna stran ima smisel šele z lastnimi, redno osveženimi podatki. |
| P2 | Kamere (»Spletne kamere v gorah in na smučiščih«) | **Ni narejeno.** Kamerni zid je na Snegofilih (ARSO, DRSI Črnivec, Windy časovni zdrs). **Za Golte, Ljubelj, Planico, Kriško goro in Veliko planino nimamo kamere** (Golte: `kamere: []`); stran brez kamere ne sme nastati (poročilo samo to pravi). Potrebuje vir/dovoljenje. |
| P3 | Izobraževalni članki | Ni narejeno (nekaj ustreznih že obstaja: prvi sneg, bel božič, meja sneženja po višinah v `generate_zima_clanki.py`). |

## Napaka, najdena med delom: »meja sneženja« je bila ničta izoterma

`winter_engine.compute_snow_line()` je kot `current_line_m`, `forecast_24h_m` in dnevno `line_m` zapisal **surovo višino ničte izoterme**, stran, FAQ in snežna karta pa so trdili, da je meja sneženja 250 m pod njo (Snegofili so odmik že upoštevali). Posledica: pri izoterma 760 m je stran pisala »meja pri 760 m«, model pa je sneg štel od ~510 m. Popravljeno: `snow_line_from_freezing_level()` (izoterma − `SNOW_LEVEL_OFFSET_M`, ne pod 0 m); zanesljivost se še računa iz premika surove izoterme. Veljajo od naslednjega teka `zima-forecast.yml`; vrstice v `history` zapisane prej so še izoterma. Zapisani članki (`generate_zima_clanki.py`) so posnetki na dan objave in se ne spreminjajo.

## Merjenje (po poročilu)

GSC: prikazi, kliki, CTR in položaj po ciljni strani; spremljaj tudi »danes«, »jutri«, »v živo« in imena lokacij. Preveri, ali več URL-jev tekmuje za isti namen (meja sneženja / snežna karta). Okoli 12. 12. 2026 (skupaj s presojo naslovnice) primerjaj `/zima/meja-snezenja/` in `/zima/snezna-karta/` za »meja sneženja«, `/snegofili/` za »sneg v Sloveniji« in `/vreme-v-gorah/` za »vreme Golte«.
