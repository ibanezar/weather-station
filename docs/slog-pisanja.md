# Slogovni vodnik za besedila na Meteorcu (OSNUTEK)

Osnutek, 10. 10. 2026. Pravila z oznako **[potrdi]** sem sklepal iz Filipovih popravkov in odzivov, ne iz izrecne želje. Filip jih potrdi, spremeni ali črta. Vodnik velja za članke, objave na FB/IG, kartice in odgovore na komentarje. Ne zamenjuje lekture (`lektura.yml`, izklopljena od 2. 10. 2026), ampak ji prihrani delo.

## 1. Glas

- **Vikanje** bralca (»Poznate takšnega gobarja?«), nikoli tikanje v člankih. V komentarjih na FB tudi vikanje, razen če bralec tika prvi. **[potrdi]**
- **Prva oseba ednine** za avtorja (»pripravil sem«), ne množina »mi« razen pri skupni skrbi (»nam pomagajo opažanja«). Ne mešati ednine in množine v istem odstavku.
- **Naravna, pogovorna slovenščina**, kakršno bi govoril sosed čez plot, a brez narečja in žargona. Raje »Poznate takšnega gobarja?« kot »Ali ste že kdaj opazili pojav …«.
- **Topel, ne vzvišen.** Bralec, ki trdi nasprotno (»gobe rastejo čez noč«), ima pogosto delno prav. Najprej mu to priznamo, nato razložimo razliko. Ne pišemo »niste nabirali« ali podobnih očitkov.
- **Humor je dovoljen**, če je bralec v njem pripadnik, ne tarča (»Sosed: polna košara. Vi: stari klobuki.«).

## 2. Struktura članka

- **Naslov do 60 znakov** (Google odreže, glej `seo_title()`), brez dvopičja, če gre brez. Najbolje deluje relatabilen prizor ali konkretna številka (»Zakaj vaš sosed vedno najde gobe, vi pa ne?«, »8–16 dni«). Ne uporabljamo vabljivih naslovov, ki jih besedilo ne izpolni.
- **Uvod: odgovor ali prizor v prvih dveh stavkih.** Če je mogoče, s konkretno številko. Po podatkih strani so objave z napisanim uvodom in številko prinesle večino dosega.
- **Kratek odgovor najprej** (»Kratek odgovor: pol res.«), nato razlaga in grafi.
- **Odstavki do 4 stavkov.** Seznam, kadar so 3 ali več vzporednih stvari. Razdelki z oznako (`section-label`) in naslovom, ki je sam po sebi odgovor.
- **Konec: kaj naj bralec naredi** (povezava na napoved, kalkulator, vpis opažanja), ne povzetek.

## 3. Trditve in poštenost

- **Modelska ocena ni meritev.** Vedno povemo, kaj je meritev (postaja IREICA1), kaj model in kaj opažanje. Ne zlivamo virov v eno številko.
- **Omilimo absolutne trditve**, kadar podatki ne dopuščajo gotovosti: »po naših ocenah«, »običajno«, »pogosto«, ne »vedno«, »nikoli«, »dokazano«. **[potrdi]**
- **Vsaka številka ima vir ali oznako** (iNaturalist, Open-Meteo, postaja, model). Predobjavo (preprint) označimo kot nerecenzirano. Česa nismo našli, napišemo (»natančnega trajanja v virih nismo našli«).
- **Zdravje in varnost:** pri gobah vedno opozorilo na zamenjavo in povezava na strupene gobe ali dvojnice. Podatkov o zastrupitvah ne povzemamo, dokler jih ne preverimo pri uradnem viru.
- **Ne izmišljamo.** Primerov, citatov, izkušenj gobarjev ali števil, ki jih ni v podatkih, ne pišemo.
- **Notranjih meritev** (hiša) ni nikjer, nikoli (glej `CLAUDE.md`).

## 4. Zapis (tipografija in številke)

| Stvar | Pravilo | Primer |
|---|---|---|
| Narekovaji | slovenski »…« | »zraste čez noč« |
| Pomišljaj | en pomišljaj (–) z razmaki med besedama, brez razmakov med številkama | gobe – torej – rastejo; 8–16 dni |
| Vezaj | samo v sestavljenih besedah | hmeljsko-pivovarski |
| Decimalna vejica | vedno vejica | 26,6 mm; 12,0 °C |
| Enote | presledek pred enoto | 26,6 mm; 13 °C; 366 m |
| Datum | »10. oktobra 2026«; v tabelah »10. 10.« | 9. 10. |
| Ura | 7.30 ali 7:30, dosledno v eni objavi | **[potrdi]** |
| Odstotek | presledek: 14 % | 82 % |
| Naslovi | samo prva beseda z veliko | »Kaj je odločilo: tri tedne vremena« |
| Latinska imena | poševno, v oklepaju ob prvi omembi | jurček (*Boletus edulis*) |

## 5. Besedišče in pogoste napake

**Raje to:**

| Namesto | Pišemo |
|---|---|
| rastni zamik, lag | zamik po dežju |
| fruiting body | trosnjak (v besedilu tudi »goba«) |
| MTR, MOS | model MTR; ob prvi omembi: »Meteorec napovedni model« |
| trigger | sprožilec; »sproži« |
| feedback | odziv, povratna informacija |
| za vsak primer | v vsakem primeru |
| na dnevni bazi | vsak dan |
| trpniška oblika (»je bilo ugotovljeno«) | »ugotovili smo«, »podatki kažejo« |

**Napake, ki sem jih že naredil (naj se ne ponovijo):**

- »dež se seštevka« → **sešteva** (glagol *seštevati*).
- »A zdaj že velika goba je začela …« → »A goba, ki je zdaj velika, je začela …« (red stavkov, brez nepotrebnega »že«).
- Mešanje ednine in množine pri avtorju (»pripravil sem« in »pripravili smo« v istem odstavku).
- Predolg uvod z več podatki v enem stavku → razbiti na dva.
- »Opažanja nam pomagajo preverjati« brez povezave → vedno povezava na kraj, kjer opažanje vnesejo.

## 6. Slovnica: mesta, kjer se najpogosteje zmotim

Pravila z oznako **[potrdi]** so tista, kjer se normativni viri in sodobna raba razlikujejo.

**Števniki in samostalniki** (najpogostejša past):

| Število | Pravilo | Primer |
|---|---|---|
| 1 | ednina, imenovalnik | 1 goba, 1 dan |
| 2 | dvojina | 2 gobi, dva dneva |
| 3, 4 | množina, imenovalnik | 3 gobe, 4 dni |
| 5 in več | množina, **rodilnik** | 5 gob, 18 kosov, 26 dni |
| z enoto | rodilnik snovi | 26,6 mm **dežja**, 20 mm padavin |

- Pri številkah v besedilu zapisujemo **»2 dni«**, v celoti pa »dva dneva«. **[potrdi]**
- »Pol dneva«, »pol ure«, »poldrugi dan«: ne »0,5 dneva«.
- Število in količina z rodilnikom: »veliko dežja«, »malo gob«, »nekaj dni«.

**Skloni in predlogi:**

- **po + mestnik:** »po dežju«, »po suši«, »po tednu« (ne »po dež«).
- **zaradi, brez, med, od, do + rodilnik:** »zaradi suše«, »do 9. oktobra«.
- **kljub + dajalnik** (sodobno tudi rodilnik): »kljub dežju«. **[potrdi]**
- **v/na:** »v gozdu«, »na Golteh«, »v dolini«, »na postaji«. Kraj, kjer je kaj, mestnik; kam gre, tožilnik (»gre v gozd«).
- **Zanikanje + rodilnik:** »ni gob«, »ne vidim sledi« (ne »ni gobe«, »ne vidim sled«).

**Besedni red:**

- **Naslonski členki** (se, si, je, bi, ga, mu, mi, vam) so na **drugem mestu** v stavku: »Zjutraj se je pokazala«, »Včeraj mi je rekel«. Ne: »Zjutraj je se pokazala«. Stavek se ne začne z naslonskim členkom.
- **Vrstni red členkov:** bi → je/so → se/si → ga/jo/jih: »Rad bi se ga spomnil«.
- **Povedek na koncu** je pogosto zvenel kot knjižna nemščina. Raje: »Odločilo se je pred tedni« kot »Pred tedni se je odločilo«.

**Ločila:**

- **Vejica pred**: ki, ker, da, ko, če, kjer, čeprav, vendar, a, torej, namreč, saj, zato ker.
- **Vrinjeni stavek** ima vejico na obeh straneh: »Goba, ki je danes velika, je začela nastajati dni prej.«
- **Pred »in« vejice ne pišemo**, razen če povezuje dva stavka z različnim osebkom. **[potrdi]**
- **»tako … kot«, »ne le … ampak tudi«**: brez vejice pred »kot«, vejica pred »ampak«.
- **Dvopičje** za naštevanje ali razlago, **pomišljaj** za premor (»Drži – a ne popolnoma.«).

**Glagol in čas:**

- **Preteklik** brez »sem« v 3. osebi (»je«, »so«), v 1. in 2. osebi je »sem«, »si« obvezen (»pripravil sem«).
- **Vid:** »doseže« (dovršni) za trenutek, »dosega« (nedovršni) za proces. Za napoved: »bo padlo«, »bo deževalo«.
- **Trpnik** le, kadar je izvajalec nepomemben (»opažanja so zbrana«). Sicer tvornik: »zbrali smo«.
- **Deležnik na -č / -ši** v naslovih in uvodih zamenjamo s stavkom: »gobe, ki rastejo«, ne »rastoče gobe«, razen kjer je izraz ustaljen.

**Pridevniki in kazalni zaimki:**

- **»ta« / »ta isti«:** ne »ta isti dan« po nepotrebnem. Raje »isti dan«.
- **Svojilni zaimek:** »svoj« ob osebku (»gobar najde svoje mesto«), »njegov« za drugega (»sosed in njegova košara«).
- **Stopnjevanje:** »bolj suh« (ne »suhejši« v pisanem jeziku, razen »suhejši« kot sodobna raba; **[potrdi]**), »najsuhši«.

**Pogoste napake v zadnjih besedilih:**

- Glagol **seštevati**, ne »seštevka« (»dež se sešteva«).
- **»kateri«** namesto »ki« v dolgih stavkih: raje »ki«.
- **Dvojina pri »jurček«:** »dva jurčka« (ne »dve jurčka«). Rod: **jurček** je moški, **goba** ženski, **lisička** ženski, **trosnjak** moški.
- **Podvojeno »že … že«** v istem stavku.
- Predolg **stavčni člen pred povedkom**: razbijte stavek.

## 7. Objave na FB/IG

- **Link objava** (ne slika s povezavo v komentarju). Uvod z relatabilnim prizorom ali številko, 3–5 kratkih stavkov, vprašanje na koncu, povezava z UTM (`utm_source=facebook&utm_medium=social&utm_campaign=<tip>`).
- Emoji zmerno (1–3), samo kadar so del tona (🍄).
- **Kartica:** največ en naslov in ena grafika, fotografija je glavna. Ne več kot 15–20 besed. Če ima kartica vir, ga navedemo v nogi.
- **Odgovori na komentarje:** do 3 stavke, najprej priznanje, nato dodatek. Ne prepiramo se. Na vprašanje, na katero ne vemo, odgovorimo »tega ne vemo, preverimo« in preverimo.

## 8. Preverjanje pred objavo

1. Naslov ≤ 60 znakov. Opis ≤ 160.
2. Vsaka številka v besedilu je v grafu, tabeli ali viru.
3. Preberi nasglas: kje se zatakneš, tam stavek razbij.
4. Iskanje po anglicizmih, trpniku in slovničnih pastih iz razdelka 6 (`call_lektor` ali ročno).
5. `geo_audit.py`, `seo_audit.py`, `test_privacy.py`.
6. Po objavi: IndexNow in (če je namenjeno) objava FB/IG.

## Odprta vprašanja za Filipa

- Vikanje ali tikanje v komentarjih na FB? Zdaj vikam.
- Ura: »7.30« ali »7:30«?
- Emoji: kje so za vas še sprejemljivi, kje ne?
- Kdaj »jaz« in kdaj »mi«? Kaj je Meteorec: oseba (Filip) ali ekipa?
- Je kakšna beseda, ki je ne želite nikoli videti (npr. »fenomenalno«, »neverjetno«)?
