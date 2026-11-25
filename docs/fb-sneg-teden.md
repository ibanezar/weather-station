# FB/IG objave: »Sneg ta teden: v dolini kaže na sredo in četrtek« (21. 11. 2026)

Štiri kartice 1080×1350 (`og/sneg-prihodnji-teden-sreda-cetrtek-1121-kartica-N.jpg`, izdela jih
`python3 tools/generate_sneg_teden_card_variants.py`) in besedilo za vsako. Pisano po `docs/slog-pisanja.md`
(razdelek 7): link objava, uvod s številko, kratki stavki, vprašanje na koncu, UTM povezava, vikanje.
Vsaka kartica ima svojo `utm_campaign`, da GA4 loči, katera prinese klike. Kartice so namenjene tudi IG (feed).

**Številke so posnetek napovedi z 25. 11. 2026 ob 7. uri (sedma različica; torek ob 9. uri: 89 %, 9 cm, sre ob 4. uri; sobota ob 9. uri: 91 %, 12 cm, sre ob 15. uri; sobota ob 23. uri: 96 %, 16 cm, sre ob 11. uri; nedelja ob 10. uri: 98 %, 17 cm, sre ob 11. uri; ponedeljek ob 6. uri: 98 %, 14 cm, sre ob 12. uri; ponedeljek ob 18. uri: 94 %, 13 cm, sre ob 8. uri; sreda ob 7. uri: 95 %, 12 cm, sre ob 2. uri).** Modeli se osvežujejo večkrat na dan in do srede se bo
napoved še premaknila, zlasti čas začetka. Pred vsako objavo ponovite `python3 tools/sneg_teden_data.py` in
`python3 tools/generate_sneg_teden_card_variants.py`: generator kartic pade, če posnetek ni današnji ali če napoved
ne podpira več trditev članka (pri tem se številke na kartici in v članku razidejo, zato razlike v besedilu
spodaj popravite ročno). **Kartice 1–3 ne držijo več, ko sneženje v sredo začne (in po četrtku sploh ne).**

Predlagan vrstni red:

1. **Sreda zjutraj: kartica 1.** 95 % in vprašanje, ali že sneži; napoved je spet močnejša kot včeraj.
2. **Sreda dopoldne: kartica 4 (zgodovina in ugibalnik).** Kartica 2 (kdaj) je v sredo slabša: mediana ure prvega sneženja (2. ura) je že mimo, zato jo objavite samo kot pregled, ne kot napoved.
3. **Sreda popoldne ali zvečer: kartica 3 (koliko), pred glavnim sneženjem v četrtek.** Po četrtku nobena kartica ne drži več.

Opombe: besedilo vsake napovedi pove, da je to model, ne uradno opozorilo; sneženje ni isto kot obležanje.
Članek je bil šestkrat posodobljen z novimi zagoni modelov (razdelek na vrhu članka pove, kaj se je spremenilo).
Za arhivske fotografije v članku (ne na karticah) velja podpis »ilustracija«.

---

## Kartica 1 — »Sneg ta teden: sreda in četrtek« (95 %)

❄️ Bo v dolini sneg? Po današnjih izračunih da, največ ga bo v četrtek.

Vsaj 1 cm novega snega v Rečici med sredo in četrtkom napoveduje 95 % od 143 članov ansamblov, mediana je 12 cm (včeraj 9 cm). Danes je količina še majhna (vsaj 1 cm pri 48 % članov), največ naj bi zapadlo v četrtek (92 %).

Temperatura se drži blizu 0 °C, zato je v dolini vprašanje, ali bo padal sneg ali dež. Sneži pa ni isto kot obleži: to je izračun iz padavin in temperature, ne napoved debeline snežne odeje. Modelska napoved, ne uradno opozorilo.

Ali že sneži pri vas?

👉 https://meteorec.si/blog/sneg-prihodnji-teden-sreda-cetrtek-1121.html?utm_source=facebook&utm_medium=social&utm_campaign=sneg-teden-1

## Kartica 2 — »Prvi sneg v dolini: v sredo zgodaj zjutraj« (sre 2.00)

⏰ Kdaj bo v dolini prvič zasneženo?

Ansambli so prve snežinke v Rečici postavili v noč na sredo, okoli 2. ure (mediana; pri 80 % članov med 23. uro v torek in 5. uro v sredo). V sredo je količina še majhna: vsaj 1 cm napoveduje 48 % članov, v četrtek pa 92 %.

Temperatura je ves čas blizu 0 °C: mediana najvišje je v sredo 4,0 °C, v četrtek 2,7 °C. Za petek in vikend se napoved razide.

Ali je pri vas že zapadel prvi sneg? Napišite uro in kraj.

👉 https://meteorec.si/blog/sneg-prihodnji-teden-sreda-cetrtek-1121.html?utm_source=facebook&utm_medium=social&utm_campaign=sneg-teden-2

## Kartica 3 — »Koliko snega pade v sredo in četrtek?« (12 cm)

📏 Koliko snega lahko pade med sredo in četrtkom?

Mediana novega snega je v Rečici 12 cm (razpon od 3 do 20 cm), na 700 m 22 cm, na Golteh 25 cm. V dolini odloča, ali je temperatura v času padavin pod ali nad 0,5 °C: ansambel GEFS za četrtek vidi sneg le pri 68 % članov, ECMWF in ICON-EPS pa pri 96 % ali več.

Računam, da 1 mm padavin da 1 cm snega; pri mokrem snegu blizu 0 °C ga je lahko manj, zato številke jemljite kot zgornji del verjetnega razpona.

Koliko ga pričakujete na svojem dvorišču?

👉 https://meteorec.si/blog/sneg-prihodnji-teden-sreda-cetrtek-1121.html?utm_source=facebook&utm_medium=social&utm_campaign=sneg-teden-3

## Kartica 4 — »Prvi sneg v dolini bi bil zgoden« (2. 12.)

🗓️ Če sneg zapade v sredo ali četrtek, bo to zgodnji prvi sneg.

V zadnjih sedmih zimah je v Gornjem Gradu (ARSO) prva snežna odeja z višino vsaj 1 cm nastala med 22. novembrom in 25. decembrom, mediana je 2. december. Prej kot 26. novembra se je to zgodilo samo enkrat (22. 11. 2024). Letos je do 25. novembra v dolini še ni bilo.

Ste v ugibalniku prvega snega že oddali datum? Merilo je isto: najmanj 1 cm snežne odeje na ARSO postaji Gornji Grad.

👉 https://meteorec.si/zima/sneg-ugibalnik/?utm_source=facebook&utm_medium=social&utm_campaign=sneg-teden-4

(Kartica 4 vodi na ugibalnik, ne na članek: vprašanje na koncu je o ugibanju datuma. Članek je omenjen v prvem komentarju, če ga želite.)
