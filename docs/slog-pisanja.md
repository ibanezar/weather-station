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
| Pomišljaj | med besedama z razmaki (SP § 381), »od … do« stično brez razmakov (SP § 394), negativna temperatura stično (SP § 397) | gobe – torej – rastejo; 8–16 dni; v letih 2021–2026; –3 °C |
| Vezaj | samo v sestavljenih besedah | hmeljsko-pivovarski |
| Decimalna vejica | vedno vejica | 26,6 mm; 12,0 °C |
| Enote | presledek pred enoto | 26,6 mm; 13 °C; 366 m |
| Datum | »10. oktobra 2026«; v tabelah »10. 10.« | 9. 10. |
| Ura | pika med uro in minutami (SP § 255); cela ura »ob 8. uri«; dvopičje samo za digitalni prikaz (SP § 370) | ob 7.30; ob 8. uri |
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

Preverjeno v Slovenskem pravopisu (2001): števniki »dva dni«, »kljub« z dajalnikom, vejica pred »in«, zapis ure, pomišljaj, decimalna vejica (viri na koncu). Z oznako **[potrdi]** ostajajo pravila, ki jih v Pravopisu nisem našel ali kjer se norma in raba razlikujeta.

**Števniki in samostalniki** (najpogostejša past):

| Število | Pravilo | Primer |
|---|---|---|
| 1 | ednina, imenovalnik | 1 goba, 1 dan |
| 2 | dvojina | 2 gobi, dva dneva |
| 3, 4 | množina, imenovalnik | 3 gobe, 4 dni |
| 5 in več | množina, **rodilnik** | 5 gob, 18 kosov, 26 dni |
| z enoto | rodilnik snovi | 26,6 mm **dežja**, 20 mm padavin |

- Pri številkah v besedilu zapisujemo **»2 dni«**, v celoti »dva dni« ali »dva dneva«. Pravopis v iztočnici *dan* navaja »čez dva dni«, v iztočnici *odrejati* »dva dneva«, torej sta obe obliki pravilni (Fran, Slovenski pravopis).
- »Pol dneva«, »pol ure«, »poldrugi dan«: ne »0,5 dneva«.
- Število in količina z rodilnikom: »veliko dežja«, »malo gob«, »nekaj dni«.

**Skloni in predlogi:**

- **po + mestnik:** »po dežju«, »po suši«, »po tednu« (ne »po dež«).
- **zaradi, brez, med, od, do + rodilnik:** »zaradi suše«, »do 9. oktobra«.
- **kljub + dajalnik:** »kljub dežju«, »kljub vsemu«, »kljub temu da …«. Pravopis ga vodi kot »nepravi predlog z dajalnikom« (Fran, Slovenski pravopis, *kljub*).
- **v/na:** »v gozdu«, »na Golteh«, »v dolini«, »na postaji«. Kraj, kjer je kaj, mestnik; kam gre, tožilnik (»gre v gozd«).
- **Zanikanje + rodilnik:** »ni gob«, »ne vidim sledi« (ne »ni gobe«, »ne vidim sled«).

**Besedni red:**

- **Naslonski členki** (se, si, je, bi, ga, mu, mi, vam) so na **drugem mestu** v stavku: »Zjutraj se je pokazala«, »Včeraj mi je rekel«. Stavek se ne začne z naslonskim členkom. Pri več členkih skupaj (»bi se ga«) vrstnega reda sam ne uganjujem, ampak ga preveri lektor.

**Ločila:**

- **Vejica pred**: ki, ker, da, ko, če, kjer, čeprav, vendar, a, torej, namreč, saj, zato ker.
- **Vrinjeni stavek** ima vejico na obeh straneh: »Goba, ki je danes velika, je začela nastajati dni prej.«
- **Pred vezalnim »in« vejice ne pišemo** (SP § 316). Pišemo jo, kadar jo zahteva vrinjeni ali vmesni stavek (§ 321: »Povej mi, kje si bil ves ta čas, in pojdi potem hitro na postajo«), in lahko pred »in«, če sta osebka slabo združljiva (»Komaj je zatisnil oči, se je zbudil, in dan je bil.«).
- **»tako … kot«, »ne le … ampak tudi«**: brez vejice pred »kot«, vejica pred »ampak«.
- **Dvopičje** za naštevanje ali razlago, **pomišljaj** za premor (»Drži – a ne popolnoma.«).

**Glagol in čas:**

- **Preteklik** brez »sem« v 3. osebi (»je«, »so«), v 1. in 2. osebi je »sem«, »si« obvezen (»pripravil sem«).
- **Vid:** »doseže« (dovršni) za trenutek, »dosega« (nedovršni) za proces. Za napoved: »bo padlo«, »bo deževalo«.
- **Trpnik** le, kadar je izvajalec nepomemben (»opažanja so zbrana«). Sicer tvornik: »zbrali smo«.
- **Deležnik na -č / -ši** v naslovih in uvodih zamenjamo s stavkom: »gobe, ki rastejo«, ne »rastoče gobe«, razen kjer je izraz ustaljen.

**Pridevniki in kazalni zaimki:**

- **Svojilni zaimek:** »svoj« ob osebku (»gobar najde svoje mesto«), »njegov« za drugega (»sosed in njegova košara«).
- **Stopnjevanje:** »suh, suhejši (ali bolj suh), najsuhši«; kjer sem negotov, pišem opisno (»manj dežja«). **[potrdi]**

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

## 9. Niša: kako pišejo ARSO in gobarji (10. 10. 2026)

Povzetek branja besedil, ne kopija. Namen: uporabljati besede, ki jih bralec že pozna, in ne trditi bolj gotovo kot viri.

**ARSO (besedilna napoved za Slovenijo, 10. 10. 2026 ob 17h)**

- **Zgradba:** glava (kraj, datum, ura izdaje) → povzetek → podrobna napoved (večer in noč, nato jutri po delih dneva) → obeti → vremenska slika → sosednje pokrajine → vir. Naši članki o napovedi lahko sledijo istemu vrstnemu redu, da bralec ve, kje je kaj.
- **Kratki stavki v prihodnjiku:** »Zvečer in ponoči bo ponekod rahlo rosilo.« »V nedeljo se bo jasnilo, po nižinah bo dopoldne megleno.«
- **Kakovost in obseg z besedo, ne z odstotkom:** ponekod, kakšna ploha, po nižinah, na Primorskem; pretežno jasno; megla ali nizka oblačnost; šibka burja.
- **Časovni izrazi:** zvečer, ponoči, dopoldne, v noči na ponedeljek, jutri, v nedeljo.
- **Številke v napovedi so cele in v obsegu:** »od 5 do 11«, »do 22 °C«, brez decimalk. Napoved ne lažna natančnost.
- **Ura izdaje:** »ob 17h« (Pravopis § 253 dovoljuje obliko »ob 8h«).

*Za Meteorec:* **napoved zaokrožimo na cela števila, meritev (IREICA1) pišemo z decimalko** (26,6 mm; 12,0 °C). To je pošteno do obeh. Ko navajamo uradno ARSO opozorilo, ostane obvezna navedba vira in časa izdaje (15. člen ZDMHS, glej `CLAUDE.md`).

**Gobarji in mikologi (n1info, 24ur/STA)**

- **Besede, ki jih bralec pozna:** *gobarska sezona, gobar, rastišče, potencial rasti, samonikle glive, tržno zanimive vrste, zavarovane vrste, količinsko nabiranje, dovolilnice*. V običajnem besedilu »goba«, »gobe«; »glive« v strokovnem ali pravnem okviru.
- **Slog poročil:** informativen naslov (trditev ali vprašanje), kratek aktualen uvod s časom (»Ob začetku gobarske sezone …«), izjave strokovnjakov kot citati, podnaslovi v obliki vprašanj (»Zakaj ne bi imeli dovolilnic?«).
- **Kaj strokovnjaki pravijo o razmerah:** suša je glavni omejitveni dejavnik; noči ne smejo biti prehladne; sezona lahko traja do decembra; **tik po dežju v gozd ni priporočljivo** (dež in megla spereta značilnosti klobuka, zato je prepoznavanje težje). To je drug razlog za »počakajte« kot naš zamik rasti, zato ju v člankih ločimo.
- **Ljudski prag:** v starem poročilu (STA, 2013) predsednik Mikološke zveze Slovenije pravi, da gobe začnejo rasti ob 33 litrih dežja na m² naenkrat; vira članek ne navaja. Pri nas tega **ne navajamo kot dejstvo** (naš model uporablja 25 mm v 7 dneh za jurčka in zalogo vode v 14 dneh). Če bralec to omeni, odgovorimo, da je ljudski prag in da je odvisen od vrste in tal.
- **Luna:** gobarji pogosto omenjajo polno luno kot spodbudo za rast. Imamo članek o tem (`vpliv-lune-na-rast-gob-0921`); pišemo previdno (»po izkušnjah gobarjev«), ne kot dokazan učinek.

**Kar prevzamemo:** kratke stavke, lokacijske kvalifikatorje (ponekod, po nižinah), podnaslove-vprašanja, besedo »rastišče«. **Česar ne:** neutemeljenih pragov, čustveno obarvanih besed (»ropanje«), trditev brez vira.

## 10. Preverjanje pred objavo

1. Naslov ≤ 60 znakov. Opis ≤ 160.
2. Vsaka številka v besedilu je v grafu, tabeli ali viru.
3. Preberi nasglas: kje se zatakneš, tam stavek razbij.
4. Iskanje po anglicizmih, trpniku in slovničnih pastih iz razdelka 6 (`call_lektor` ali ročno).
5. `geo_audit.py`, `seo_audit.py`, `test_privacy.py`.
6. Po objavi: IndexNow in (če je namenjeno) objava FB/IG.

## Odprta vprašanja za Filipa

- Vikanje ali tikanje v komentarjih na FB? Zdaj vikam.
- Emoji: kje so za vas še sprejemljivi, kje ne?
- Kdaj »jaz« in kdaj »mi«? Kaj je Meteorec: oseba (Filip) ali ekipa?
- Je kakšna beseda, ki je ne želite nikoli videti (npr. »fenomenalno«, »neverjetno«)?

## Viri in kaj sem preveril (10. 10. 2026)

- **Slovenski pravopis 2001, pravila** (PDF, Fran): https://www.fran.si/134/slovenski-pravopis/datoteke/Pravopis_Pravila.pdf — § 255–256 (zapis ure), § 316–321 (vejica pred »in«), § 351 (decimalna vejica), § 370 (dvopičje na digitalnih urah), § 381 (pomišljaj med besedami), § 394 in § 397 (pomišljaj »od … do« in negativna števila).
- **Iztočnice v Pravopisu:** *kljub* (https://www.fran.si/134/slovenski-pravopis/3752874/kljub), *dan* (https://www.fran.si/134/slovenski-pravopis/3732256/dan).
- **Jezikovna svetovalnica ZRC SAZU:** strani odgovorov (`svetovalnica.zrc-sazu.si/topic/…`) iz tega okolja ne morem brati (HTTP 403), zato nisem povzemal ničesar iz njih. Iskanje prek Frana (`dictionaryId=151`) vrne samo vprašanja. Zanimivi zapisi za branje: zapis ure (https://svetovalnica.zrc-sazu.si/topic/1490), »kljub visokim letom« (/topic/5512), vejica pred »in« (/topic/2366).
- **Še ni preverjeno:** presledek pred % in enotami (SI-uzus, v Pravopisu nisem našel pravila), stopnjevanje »suhejši«, »kateri« proti »ki«, zapis latinskih imen.
- **ARSO besedilna napoved:** https://meteo.arso.gov.si/uploads/probase/www/fproduct/text/sl/fcast_si_text.html (prebrano 10. 10. 2026).
- **Gobarji:** https://n1info.si/novice/slovenija/bliza-se-glavna-sezona-gobarjenja-na-kaj-ob-tem-opozarja-strokovnjakinja/ (Metka Bertoncelj, Gobarsko mikološko društvo Ljubljana) in https://www.24ur.com/ne-najdete-gob-doslej-gre-za-eno-najslabsih-gobarskih-sezon.html (STA, 15. 9. 2013, Mikološka zveza Slovenije).
