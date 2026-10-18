/*
 * igra/gobarski-detektiv/detektiv.js — »Gobarski detektiv« (/igra/gobarski-detektiv/)
 *
 * ROČNO pisana, samostojna datoteka (ni generirana). Model (primeri, točkovanje,
 * sestava kroga) je ločen od prikaza in izvožen za Node (tools/test_detektiv.mjs),
 * isti vzorec kot napovej.js in igra.js.
 *
 * Igra je POUČNA: uči, da se gobe ne prepoznava po eni lastnosti, in da je pri
 * sumu pravilna odločitev »pusti«. Ne nadomešča pregleda pri usposobljenem gobarju.
 * Imena in užitnost so ista kot v bazi vrst na /gobarska-napoved/baza-vrst/.
 */
(function (root) {
  'use strict';

  /* ── Podatki ─────────────────────────────────────────────────────────────
   * Par = dve vrsti, ki se pogosto zamenjata. Krog je KROG_DOLZINA parov, iz
   * vsakega natanko en primerek; kateri pari in kateri primerek, se vsakič žreba.
   * edib: u = užitna, p = pogojno užitna, n = neužitna, s = strupena, z = zelo strupena, d = smrtno strupena.
   * Sledi (6 mest): klobuk, spodaj, noga, dno, meso, okolje.
   * spec = parametri za SVG (glej risi()). */
  var SLEDI = ['klobuk', 'spodaj', 'noga', 'dno', 'meso', 'okolje'];
  var SLEDI_IME = {
    klobuk: 'Klobuk', spodaj: 'Spodnja stran', noga: 'Noga',
    dno: 'Dno noge', meso: 'Meso in vonj', okolje: 'Kje raste'
  };
  var SLEDI_POGLED = { klobuk: 'cela', spodaj: 'spodaj', noga: 'cela', dno: 'dno', meso: 'dno', okolje: 'cela' };

  var EDIB = {
    u: ['Užitna', 'ok'], p: ['Pogojno užitna', 'warn'], n: ['Neužitna', 'warn'],
    s: ['Strupena', 'bad'], z: ['Zelo strupena', 'bad'], d: ['Smrtno strupena', 'bad']
  };

  var PARI = [
    {
      id: 'goban', naslov: 'Primer: košara iz smrekovega gozda',
      uvod: 'Sosed je v gozdu nad vasjo odrezal veliko rjavo gobo s klobukom in cevkami. Pravi, da je jurček. Preveri.',
      razlaga: 'Oba imata rjav klobuk in cevke, zato ju je lahko zamenjati. Loči ju mreža na nogi (pri jurčku fina in bela, pri žolčastem gobanu groba in temna), barva cevk (pri žolčastem gobanu postanejo rožnate) in okus mesa (grenak). Žolčasti goban ni strupen, a en sam osebek pokvari celo jed.',
      vrste: [
        {
          id: 'jurcek', ime: 'Jesenski goban (Jurček)', lat: 'Boletus edulis', edib: 'u', q: 'Jesenski goban (Jurček)', kat: 'uzitne',
          spec: { klobuk: '#8a5a33', rob: '#d9b98c', oblika: 'kupola', sirina: 78, visina: 52, dno: 'cevke', cevke: '#efe7c8', noga: '#e2cfa6', nogaV: 78, nogaS: 38, nogaS2: 52, mreza: 'bela', ovoj: null, obroc: null, rez: '#f6f2e4' },
          sledi: {
            klobuk: 'Klobuk meri 12 cm, je kostanjevo rjav, gladek in v vlagi rahlo lepljiv. Rob je svetlejši.',
            spodaj: 'Spodaj so cevke: bele do rumenkasto oljčne. Ob pritisku ne spremenijo barve.',
            noga: 'Noga je čokata in sodčasta. Na zgornji tretjini ima fino belo mrežico.',
            dno: 'Spodaj je noga odebeljena, brez vrečaste ovojnice v tleh.',
            meso: 'Meso je belo in se ob prerezu ne spremeni. Vonj je prijeten, rahlo po lešnikih.',
            okolje: 'Smrekov gozd na 700 m, med mahom in borovnicami. Septembrski dež.'
          }
        },
        {
          id: 'zolcasti', ime: 'Žolčasti goban', lat: 'Tylopilus felleus', edib: 'n', q: 'Žolčasti goban', kat: 'neuzitne',
          spec: { klobuk: '#8d6a46', rob: '#a98660', oblika: 'kupola', sirina: 76, visina: 48, dno: 'cevke', cevke: '#e8c9c0', noga: '#b88f62', nogaV: 86, nogaS: 32, nogaS2: 42, mreza: 'temna', ovoj: null, obroc: null, rez: '#f3e3dc' },
          sledi: {
            klobuk: 'Klobuk meri 11 cm, je rjav in gladek, na pogled zelo podoben jurčku. Rob ni opazno svetlejši.',
            spodaj: 'Cevke so sprva bele, a pri pritisku in starosti postanejo mesnato rožnate.',
            noga: 'Noga je nekoliko vitkejša. Po večjem delu je pokrita z grobo, temno rjavo mrežo.',
            dno: 'Spodaj je noga zaobljena in rahlo odebeljena. Temna mreža sega skoraj do dna.',
            meso: 'Meso je belo, ob rezu rahlo rožnato. Vonj je neizrazit, okus pa neprijetno grenak.',
            okolje: 'Iglasti gozd, ob panjih in koreninah smrek.'
          }
        }
      ]
    },
    {
      id: 'lisicka', naslov: 'Primer: oranžna najdba na mahu',
      uvod: 'Pohodnica je ob gozdni poti našla šop oranžnih gob in jih hoče speči. Lisičke ali kaj drugega?',
      razlaga: 'Prava lisička nima pravih listov, ampak topo, vilasto razvejano grebenje, ki teče po nogi navzdol, in diši po marelicah. Lažna lisička ima tanke, goste prave liste, je bolj oranžna in ima žametast, temnejši klobuk. Ni smrtno strupena, a je neokusna in lahko povzroči prebavne težave.',
      vrste: [
        {
          id: 'lisicka', ime: 'Navadna lisička', lat: 'Cantharellus cibarius', edib: 'u', q: 'Navadna lisička', kat: 'uzitne',
          spec: { klobuk: '#e3a21f', rob: '#f0be4e', oblika: 'lijak', sirina: 80, visina: 30, dno: 'grebeni', cevke: '#eab33c', noga: '#e8ac2c', nogaV: 62, nogaS: 40, nogaS2: 26, mreza: null, ovoj: null, obroc: null, rez: '#f5ecd2' },
          sledi: {
            klobuk: 'Jajčasto rumen, 6 cm, valovit in v sredini vdrt. Rob je nepravilno naguban.',
            spodaj: 'Namesto pravih listov so topi, žilam podobni grebeni. Vilasto se razvejajo in segajo daleč po nogi navzdol.',
            noga: 'Noga je polna in debela, brez obročka. Klobuk in noga se zlivata brez ostre meje, enake barve.',
            dno: 'Proti dnu se noga zoži. Ovojnice ni.',
            meso: 'Meso je čvrsto, vlaknato in belkasto. Trga se po dolžini. Vonj je po marelicah.',
            okolje: 'Mešan gozd s smreko in bukvijo, mahovita tla, konec avgusta.'
          }
        },
        {
          id: 'lazna', ime: 'Lažna lisička', lat: 'Hygrophoropsis aurantiaca', edib: 'n', q: 'Lažna lisička', kat: 'neuzitne',
          spec: { klobuk: '#c2641b', rob: '#d9833a', oblika: 'lijak', sirina: 66, visina: 26, dno: 'listi', cevke: '#e8801f', noga: '#a9551a', nogaV: 58, nogaS: 22, nogaS2: 24, mreza: null, ovoj: null, obroc: null, rez: '#f2d8ae' },
          sledi: {
            klobuk: 'Oranžno rjav, žametnat, na sredini temnejši. Rob je zavit navznoter.',
            spodaj: 'Pravi, tanki in gosti listi, ki se večkrat vilasto delijo. So živo oranžni, bolj kot klobuk.',
            noga: 'Noga je tanka in temnejša od klobuka. Klobuk in noga sta dobro ločljiva.',
            dno: 'Ob dnu je noga rahlo odebeljena in temno rjava.',
            meso: 'Meso je mehko, rumenkasto oranžno. Brez izrazitega vonja, po marelicah ne diši.',
            okolje: 'Iglasti gozd, med iglicami in na trhlem lesu.'
          }
        }
      ]
    },
    {
      id: 'kukmak', naslov: 'Primer: bela goba na travniku',
      uvod: 'Otroci so na robu travnika našli belo gobo. Ded pravi: »To je šampinjon, jedla sem jih že kot deklica.« Preveri.',
      razlaga: 'To je klasična smrtna zamenjava. Poljski kukmak ima v mladosti rožnate, pozneje čokoladne liste, nima ovojnice ob dnu in raste na odprtem travniku. Zelena mušnica ima vedno bele liste, viseč obroček in gomolj z vrečasto ovojnico, ki je pogosto pod zemljo. Zato goba vedno izkopljemo, ne odrežemo. Zastrupitev se pokaže šele čez 6 do 24 ur.',
      vrste: [
        {
          id: 'kukmak', ime: 'Poljski kukmak', lat: 'Agaricus campestris', edib: 'u', q: 'Poljski kukmak', kat: 'uzitne',
          spec: { klobuk: '#f1ede4', rob: '#fffdf6', oblika: 'kupola', sirina: 66, visina: 44, dno: 'listi', cevke: '#d98a8d', noga: '#f3efe6', nogaV: 56, nogaS: 24, nogaS2: 20, mreza: null, ovoj: null, obroc: 'tanek', rez: '#fbf4ee' },
          sledi: {
            klobuk: 'Bel, svilnat, 7 cm. Rob je rahlo zavit, sredina rahlo luskasta.',
            spodaj: 'Listi so v mladosti živo rožnati, pozneje čokoladno rjavi do skoraj črni. Nikoli niso beli.',
            noga: 'Noga je kratka in bela, z ozkim, enostavnim obročkom.',
            dno: 'Brez gomolja in brez vrečaste ovojnice. Proti dnu se noga zoži.',
            meso: 'Meso je belo, ob rezu rahlo rožnato. Vonj je prijeten, po gobah, ne sladkast.',
            okolje: 'Pašnik in gnojen travnik, odprt prostor. Po dežju jeseni.'
          }
        },
        {
          id: 'zelena', ime: 'Zelena mušnica', lat: 'Amanita phalloides', edib: 'd', q: 'Zelena mušnica', kat: 'strupene',
          spec: { klobuk: '#8f9a58', rob: '#b2b97a', oblika: 'kupola', sirina: 68, visina: 46, dno: 'listi', cevke: '#f4f1e6', noga: '#eeeadb', nogaV: 70, nogaS: 22, nogaS2: 34, mreza: null, ovoj: 'vreca', obroc: 'visec', rez: '#fbf9f0' },
          sledi: {
            klobuk: 'Oljčno zelenkast, svilnat in gladek, 8 cm, z vlakni. Rob je brez črt.',
            spodaj: 'Listi so beli. Tudi pri starih gobah ostanejo beli.',
            noga: 'Noga je bela, rahlo valovito progasta, z visečim obročkom kot krilce.',
            dno: 'Spodaj se noga razširi v gomolj, ovit v vrečasto ovojnico, ki je pogosto skrita pod zemljo.',
            meso: 'Meso je belo. Vonj je sladkast, pri starejših neprijeten, po gnilem.',
            okolje: 'Listnati gozd s hrasti in bukvami, tudi rob travnika.'
          }
        }
      ]
    },
    {
      id: 'dezniki', naslov: 'Primer: dežniki ob gozdnem robu',
      uvod: 'Gobar začetnik je nabral dežnike, da bi jih ocvrl. Eden mu je kar pošteno majhen. Pomagaj mu.',
      razlaga: 'Orjaški dežnik (marela) je velik, ima na nogi vzorec kot kačja koža in obroč, ki ga lahko premakneš gor in dol. Smrdljiva marelica je majhna, gladka na nogi, njen obroček je minljiv, vonj pa neprijeten. Pravilo: dežnik, ki je manjši od dlani, ne spada v košaro.',
      vrste: [
        {
          id: 'marela', ime: 'Orjaški dežnik (Marela)', lat: 'Macrolepiota procera', edib: 'u', q: 'Orjaški dežnik (Marela)', kat: 'uzitne',
          spec: { klobuk: '#d8c3a3', rob: '#e9dcc3', oblika: 'kupola', sirina: 96, visina: 44, dno: 'listi', cevke: '#f4efe2', noga: '#d9c8a8', nogaV: 108, nogaS: 16, nogaS2: 24, mreza: 'kaca', ovoj: null, obroc: 'drsni', luske: '#8d6a43', izboklina: '#6e4d2d', rez: '#fbf7ec' },
          sledi: {
            klobuk: 'Velik, 18 cm, z izrazito temno izboklino na sredini in rjavimi luskami na svetli podlagi.',
            spodaj: 'Listi so beli, gosti in prosti: ne dosežejo noge.',
            noga: 'Visoka, 25 cm, tanka, z vzorcem kot kačja koža. Ima obroč, ki ga lahko premakneš gor in dol.',
            dno: 'Spodaj je noga rahlo gomoljasto odebeljena, brez ovojnice.',
            meso: 'Meso je belo in mehko. Vonj je prijeten, po lešnikih.',
            okolje: 'Svetel gozdni rob in jase, 600 m.'
          }
        },
        {
          id: 'marelica', ime: 'Smrdljiva marelica', lat: 'Lepiota cristata', edib: 's', q: 'Smrdljiva marelica', kat: 'strupene',
          spec: { klobuk: '#efe8da', rob: '#f7f3ea', oblika: 'kupola', sirina: 38, visina: 26, dno: 'listi', cevke: '#f3eddf', noga: '#efe6d6', nogaV: 52, nogaS: 9, nogaS2: 11, mreza: null, ovoj: null, obroc: 'tanek', luske: '#a2503a', izboklina: '#8f3f2c', rez: '#f8f4e8' },
          sledi: {
            klobuk: 'Majhen, le 4 cm. Sredina je rdečkasto rjava, okoli nje drobne luske na beli podlagi.',
            spodaj: 'Listi so beli do kremni in prosti.',
            noga: 'Nizka, 5 cm, tanka in gladka, brez kačjega vzorca. Obroček je drobcen in minljiv.',
            dno: 'Spodaj brez gomolja in brez ovojnice.',
            meso: 'Meso je tanko. Vonj je neprijeten, po gumi ali plinu.',
            okolje: 'Trava ob gozdni poti, vrtovi, med odpadlim listjem.'
          }
        }
      ]
    },
    {
      id: 'tintnice', naslov: 'Primer: tintnice na pikniku',
      uvod: 'Družina pripravlja piknik. Zraven bodo pečene tintnice in kozarec vina. Katero tintnico so nabrali?',
      razlaga: 'Velika tintnica je odlična, ko je mlada. Prepoznaš jo po visokem valju z dolgimi luskami. Gola tintnica je siva in gladka, in ob alkoholu povzroči zastrupitev: rdečica, razbijanje srca, slabost. Težave se lahko pojavijo tudi do dva dni po obroku, če popiješ alkohol. Zato jo na seznamu najdemo kot strupeno.',
      vrste: [
        {
          id: 'velika', ime: 'Velika tintnica', lat: 'Coprinus comatus', edib: 'u', q: 'Velika tintnica', kat: 'uzitne',
          spec: { klobuk: '#f2eee4', rob: '#fffdf7', oblika: 'valj', sirina: 34, visina: 82, dno: 'listi', cevke: '#222', noga: '#f3efe4', nogaV: 62, nogaS: 12, nogaS2: 16, mreza: null, ovoj: null, obroc: 'drsni', luske: '#c9ae88', rez: '#fbf8ee' },
          sledi: {
            klobuk: 'Visok valj, 6 × 12 cm, bel, z dolgimi, odstopajočimi luskami.',
            spodaj: 'Listi so sprva beli, nato rožnati. Od roba navzgor se spremenijo v črno tekočino.',
            noga: 'Bela, vlaknata, votla, z drsnim obročkom.',
            dno: 'Noga je spodaj brez gomolja in brez ovojnice.',
            meso: 'Meso je belo in mehko, vonj blag. Hitro se pokvari: uporabna je le čisto mlada.',
            okolje: 'Travnik, poti, nasuta zemlja. Raste v skupinah.'
          }
        },
        {
          id: 'gola', ime: 'Gola tintnica', lat: 'Coprinopsis atramentaria', edib: 's', q: 'Gola tintnica', kat: 'strupene',
          spec: { klobuk: '#9b9a96', rob: '#b8b7b2', oblika: 'zvonec', sirina: 46, visina: 52, dno: 'listi', cevke: '#3a3a3a', noga: '#f1eee8', nogaV: 60, nogaS: 12, nogaS2: 15, mreza: null, ovoj: null, obroc: 'sled', rez: '#e9e6df' },
          sledi: {
            klobuk: 'Jajčast do zvončast, 5 cm, siv in gladek, brez dolgih lusk.',
            spodaj: 'Listi so sivkasti in se počasi razpustijo v črno tekočino.',
            noga: 'Bela, gladka, votla. Na spodnji tretjini je komaj viden obročast sled, ne drsi.',
            dno: 'Spodaj brez gomolja. Raste v šopih iz iste točke.',
            meso: 'Meso je tanko in sivkasto. Vonj je blag.',
            okolje: 'Vrtovi in grmovje, ob starih panjih. V šopih.'
          }
        }
      ]
    },
    {
      id: 'musnice', naslov: 'Primer: dve mušnici, ena v košari',
      uvod: 'Gobarka pravi, da je nabrala bisernice. V gozdu raste več mušnic, zato jo je treba preveriti.',
      razlaga: 'Rdečkasta mušnica (bisernica) je dobra le dobro kuhana, in ob rezu ali poškodbi počasi zardi. Panterjeva mušnica je zelo strupena. Ima ozek gladek obroček, belo bradavičast temnejši klobuk in meso, ki ne zardi. Rdečkasto spoznaš po zardevanju in progastem obročku. Brez zardevanja in progastega obročka je ne nabiraj.',
      vrste: [
        {
          id: 'rdeckasta', ime: 'Rdečkasta mušnica (Bisernica)', lat: 'Amanita rubescens', edib: 'p', q: 'Rdečkasta mušnica (Bisernica)', kat: 'pogojno-uzitne',
          spec: { klobuk: '#b98a72', rob: '#cba48c', oblika: 'kupola', sirina: 72, visina: 48, dno: 'listi', cevke: '#f3ede5', noga: '#ead7cc', nogaV: 70, nogaS: 22, nogaS2: 34, mreza: null, ovoj: 'gomolj', obroc: 'progast', bradavice: '#e9e1d7', rez: '#f2c9be' },
          sledi: {
            klobuk: 'Rjavkasto rožnat, 9 cm, posut z umazano belimi do sivimi kosmiči.',
            spodaj: 'Listi so beli, ob dotiku se obarvajo z rdečkastimi lisami.',
            noga: 'Noga ima viseč obroček, ki je na zgornji strani rebrasto progast. Ob poškodbi zardi.',
            dno: 'Spodaj je noga gomoljasto odebeljena, brez vrečaste ovojnice. Rdeče lise so od črvov.',
            meso: 'Meso je belo, ob prerezu se počasi obarva rožnato do rdeče. Vonj je blag.',
            okolje: 'Mešan gozd, smreke in bukve. Poletje, jesen.'
          }
        },
        {
          id: 'panterjeva', ime: 'Panterjeva mušnica', lat: 'Amanita pantherina', edib: 'z', q: 'Panterjeva mušnica', kat: 'strupene',
          spec: { klobuk: '#6b4a33', rob: '#8a6446', oblika: 'kupola', sirina: 72, visina: 48, dno: 'listi', cevke: '#f6f3ea', noga: '#f1ece1', nogaV: 70, nogaS: 20, nogaS2: 30, mreza: null, ovoj: 'rob', obroc: 'gladek', bradavice: '#fbf8f0', rez: '#fbf8f0' },
          sledi: {
            klobuk: 'Temno rjav, 9 cm, z belimi bradavicami v krogih. Rob je progast.',
            spodaj: 'Listi so beli in ne spremenijo barve.',
            noga: 'Noga je bela, z ozkim, gladkim obročkom brez prog.',
            dno: 'Spodaj je gomolj z enim ali dvema ozkima obročema, kot škorenj z manšeto.',
            meso: 'Meso je belo in se ob rezu ne spremeni. Vonj je rahlo po redkvici.',
            okolje: 'Mešan gozd, bukev in smreka. Poletje, jesen.'
          }
        }
      ]
    },
    {
      id: 'mraznice', naslov: 'Primer: šop na starem panju',
      uvod: 'Ob gozdni cesti je na trhlem panju zrasel šop rjavkastih gob. Sprehajalec jih že vidi v juhi. Previdno.',
      razlaga: 'Obe rasteta v šopih na lesu, zato ju je lahko zamenjati. Sivorumena mraznica ima bele liste z rjastimi pegami, obroček in črne vrvice ob koreninah. Navadna žveplenjača je žveplenorumena, brez obročka, njeni listi pa so zelenkasto sivi in nazadnje škrlatno rjavi, okus pa grenak. Mraznica je užitna le dobro kuhana.',
      vrste: [
        {
          id: 'mraznica', ime: 'Sivorumena mraznica (Štorovka)', lat: 'Armillaria mellea', edib: 'p', q: 'Sivorumena mraznica (Štorovka)', kat: 'pogojno-uzitne',
          spec: { klobuk: '#b98a4c', rob: '#d2a96a', oblika: 'kupola', sirina: 52, visina: 30, dno: 'listi', cevke: '#efe6cf', noga: '#d6b98a', nogaV: 70, nogaS: 14, nogaS2: 18, mreza: null, ovoj: null, obroc: 'visec', luske: '#6b4a26', rez: '#f4eede' },
          sledi: {
            klobuk: 'Medeno rjav, 7 cm, v sredini z drobnimi temnimi luskami. Rob je rahlo progast.',
            spodaj: 'Listi so beli do kremni, pozneje z rjastimi pegami.',
            noga: 'Žilava in vlaknata, z belim do rumenkastim obročkom, ki visi kot krilce.',
            dno: 'Noge so spodaj zraščene v šop. Ob koreninah so črne vrvice (rizomorfe).',
            meso: 'Meso je belo in žilavo. Vonj je prijeten, rahlo po gobah. Surovo je trpko.',
            okolje: 'Šop na panju ali ob korenini drevesa, listnati in iglasti gozd.'
          }
        },
        {
          id: 'zveplenjaca', ime: 'Navadna žveplenjača', lat: 'Hypholoma fasciculare', edib: 's', q: 'Navadna žveplenjača', kat: 'strupene',
          spec: { klobuk: '#d9c030', rob: '#e8d86a', oblika: 'kupola', sirina: 48, visina: 28, dno: 'listi', listiBarva: 'rgba(110,120,40,.55)', cevke: '#d9cf6a', noga: '#d9c868', nogaV: 64, nogaS: 10, nogaS2: 11, mreza: null, ovoj: null, obroc: null, izboklina: '#b86a1c', rez: '#f2e6a0' },
          sledi: {
            klobuk: 'Žveplenorumen, 5 cm, sredina oranžno rjava. Na robu so ostanki koprene.',
            spodaj: 'Listi so sprva žveplenorumeni, nato zelenkasto sivi in na koncu škrlatno rjavi.',
            noga: 'Tanka in rumena, brez pravega obročka. V zgornjem delu je le nežna sled koprene.',
            dno: 'Spodaj je temnejša, rjavkasta. Gobe rastejo v gostih šopih.',
            meso: 'Meso je rumenkasto in neprijetno grenko. Vonj je neprijeten, po plesni.',
            okolje: 'Šop na panju ali štoru, listnati in iglasti gozd, od pomladi do pozne jeseni.'
          }
        }
      ]
    },
    {
      id: 'sirovke', naslov: 'Primer: oranžna goba z mlekom',
      uvod: 'Gobar je v hrastovem gozdu našel oranžno gobo, ki ob rezu izteka mleko. »Sirovka, torej užitna,« pravi. Preveri.',
      razlaga: 'Užitna sirovka izteka korenjasto oranžno mleko, ki ostane oranžno, in se ob poškodbi obarva zeleno. Zlata sirovka ima mleko, ki je sprva belo in v nekaj minutah porumeni; stran jo vodi kot strupeno. Mleko in barvne spremembe so ključne: barva klobuka sama ne zadošča.',
      vrste: [
        {
          id: 'sirovka', ime: 'Užitna sirovka', lat: 'Lactarius deliciosus', edib: 'u', q: 'Užitna sirovka', kat: 'uzitne',
          spec: { klobuk: '#d9812b', rob: '#e6a45c', oblika: 'lijak', sirina: 58, visina: 24, dno: 'listi', listiBarva: 'rgba(210,120,40,.75)', cevke: '#e49a4a', noga: '#e0a060', nogaV: 44, nogaS: 20, nogaS2: 18, mreza: null, ovoj: null, obroc: null, krogi: '#a85a1d', rez: '#f0a860' },
          sledi: {
            klobuk: 'Oranžen, 9 cm, z jasnimi koncentričnimi krogi. Ob poškodbi se obarva zeleno.',
            spodaj: 'Listi so oranžni in gosti. Ob dotiku se obarvajo zeleno.',
            noga: 'Kratka, oranžna in votla, z vdrtimi plitvimi jamicami.',
            dno: 'Spodaj brez gomolja. Noga je ob dnu rahlo zožena.',
            meso: 'Ob rezu izteka korenjasto oranžno mleko, ki ostane oranžno še dolgo.',
            okolje: 'Borov in smrekov gozd, med iglicami.'
          }
        },
        {
          id: 'zlata', ime: 'Zlata sirovka', lat: 'Lactarius chrysorrheus', edib: 's', q: 'Zlata sirovka', kat: 'strupene',
          spec: { klobuk: '#e3b799', rob: '#efccb2', oblika: 'lijak', sirina: 52, visina: 22, dno: 'listi', listiBarva: 'rgba(215,175,150,.7)', cevke: '#ecc5a8', noga: '#ecd0b8', nogaV: 46, nogaS: 14, nogaS2: 14, mreza: null, ovoj: null, obroc: null, krogi: '#c99478', rez: '#faf3d0' },
          sledi: {
            klobuk: 'Bledo oranžno rožnat, 7 cm, z nejasnimi krogi. V sredini je vdrt.',
            spodaj: 'Listi so kremno rožnati in gosti.',
            noga: 'Bledo rožnata in polna, brez jamic.',
            dno: 'Spodaj brez gomolja.',
            meso: 'Mleko je sprva belo, v nekaj minutah pa porumeni. Okus je pekoč.',
            okolje: 'Hrastov gozd na toplejših legah, tudi pod gabrom.'
          }
        }
      ]
    },
    {
      id: 'gobani', naslov: 'Primer: goban z rdečimi cevkami',
      uvod: 'Na apnenčastem pobočju stoji debela goba z rdečimi cevkami. Prijatelj trdi, da je »samo velik goban«. Preglej jo.',
      razlaga: 'Oba imata rdeče ustje cevk in meso, ki zamodri. Preprosti goban ima oljčno rjav klobuk in gosto rdečo mrežo po nogi, vražji goban bled, siv klobuk in zelo trebušasto nogo. Preprosti goban je užiten le dobro kuhan, vražji je strupen. Pri gobanih z rdečimi cevkami se v dvomu ustavi.',
      vrste: [
        {
          id: 'preprosti', ime: 'Preprosti goban', lat: 'Suillellus luridus', edib: 'p', q: 'Preprosti goban', kat: 'pogojno-uzitne',
          spec: { klobuk: '#7a6a3a', rob: '#9a8a55', oblika: 'kupola', sirina: 76, visina: 46, dno: 'cevke', cevke: '#cf5a2a', noga: '#e0b84a', nogaV: 70, nogaS: 38, nogaS2: 46, mreza: 'rdeca', ovoj: null, obroc: null, rez: '#6a86b4' },
          sledi: {
            klobuk: 'Oljčno rjav, 11 cm, žametast. Ob pritisku se obarva modro.',
            spodaj: 'Cevke so rumene, ustja oranžno rdeča. Ob pritisku se hitro obarvajo modro.',
            noga: 'Rumenkasta, z gosto rdečo mrežico po večjem delu noge.',
            dno: 'Spodaj odebeljena in rdečkasto rjava.',
            meso: 'Meso je rumeno in ob prerezu hitro postane temno modro. Vonj je prijeten.',
            okolje: 'Listnati gozd s hrasti in bukvami, apnenčasta tla.'
          }
        },
        {
          id: 'vrazji', ime: 'Vražji goban', lat: 'Rubroboletus satanas', edib: 's', q: 'Vražji goban', kat: 'strupene',
          spec: { klobuk: '#cfcab8', rob: '#e2dece', oblika: 'kupola', sirina: 86, visina: 50, dno: 'cevke', cevke: '#c0302a', noga: '#d9a44a', nogaV: 56, nogaS: 52, nogaS2: 70, mreza: 'rdeca', ovoj: null, obroc: null, rez: '#e8e3c8' },
          sledi: {
            klobuk: 'Bledo siv do bel, 13 cm, debel in blazinast.',
            spodaj: 'Cevke so rumene, ustja krvavo rdeča. Modro se obarvajo počasi.',
            noga: 'Zelo čokata in trebušasta, rumeno rdeča, z drobno rdečo mrežico.',
            dno: 'Noga je spodaj izrazito odebeljena, gomoljasta, ob dnu temno rdeča.',
            meso: 'Meso je belkasto in ob prerezu počasi rahlo zamodri. Pri starejših gobah je vonj neprijeten, po gnilem.',
            okolje: 'Topel hrastov in bukov gozd na apnencu. Redka vrsta.'
          }
        }
      ]
    },
    {
      id: 'zelene', naslov: 'Primer: zelenkasta goba pod borom',
      uvod: 'Na peščenem robu borovega gozda je trop zelenkastih gob. »Zelena golobica,« je prepričan nabiralec. Preveri.',
      razlaga: 'Zelena golobica je krhka kot steklo, z razpokanim zelenim klobukom in belimi listi. Zelenkasta kolobarnica ima žveplenorumene, ne krhke liste in rumen klobuk; hujši primeri zaužitja večjih količin so povzročili poškodbe mišic. Vedno preveri barvo listov in krhkost mesa.',
      vrste: [
        {
          id: 'zgolobica', ime: 'Zelena golobica', lat: 'Russula virescens', edib: 'u', q: 'Zelena golobica', kat: 'uzitne',
          spec: { klobuk: '#8fa86a', rob: '#b3c58e', oblika: 'kupola', sirina: 74, visina: 44, dno: 'listi', listiBarva: 'rgba(230,230,215,.7)', cevke: '#f4f1e6', noga: '#f2efe4', nogaV: 52, nogaS: 24, nogaS2: 26, mreza: null, ovoj: null, obroc: null, luske: '#5e7a3e', rez: '#fbf9f0' },
          sledi: {
            klobuk: 'Zelenkast, 9 cm. Površina je razpokana v ploščate, žametne luske.',
            spodaj: 'Listi so beli in krhki. Lomijo se kot steklo.',
            noga: 'Bela, kratka in čokata, brez obročka.',
            dno: 'Spodaj brez gomolja in brez ovojnice.',
            meso: 'Meso je belo in krhko. Vonj je blag, okus sladkast.',
            okolje: 'Svetel listnati gozd s hrastom, poleti in jeseni.'
          }
        },
        {
          id: 'kolobarnica', ime: 'Zelenkasta kolobarnica', lat: 'Tricholoma equestre', edib: 's', q: 'Zelenkasta kolobarnica', kat: 'strupene',
          spec: { klobuk: '#cdbb3a', rob: '#e4d66a', oblika: 'kupola', sirina: 66, visina: 40, dno: 'listi', listiBarva: 'rgba(215,200,60,.65)', cevke: '#e3d864', noga: '#e4d98a', nogaV: 48, nogaS: 22, nogaS2: 24, mreza: null, ovoj: null, obroc: null, izboklina: '#8a8a2c', rez: '#f3eec6' },
          sledi: {
            klobuk: 'Žveplenorumen z zelenkasto sredino, 8 cm, rahlo lepljiv.',
            spodaj: 'Listi so žveplenorumeni in gosti. Niso krhki.',
            noga: 'Rumenkasta in polna, brez obročka.',
            dno: 'Spodaj brez gomolja. Noga je zakopana globoko v pesek.',
            meso: 'Meso je belkasto do rumenkasto in žilavo. Vonj je po moki.',
            okolje: 'Borov gozd na peščenih tleh.'
          }
        }
      ]
    },
    {
      id: 'kukmaki2', naslov: 'Primer: beli kukmaki v parku',
      uvod: 'V mestnem parku raste več belih gob s krilcem. Upokojenka pravi: »Prava šampinjonka, kot iz trgovine.« Ali drži?',
      razlaga: 'Karbolni kukmak ob rezu pri dnu noge zasije kromovo rumeno in diši po karbolu. Rjavoluski kukmak ob rezu zardi, vonj pa je prijeten. Pri vsakem kukmaku zato prereži dno noge in povohaj.',
      vrste: [
        {
          id: 'rjavoluski', ime: 'Rjavoluski kukmak', lat: 'Agaricus sylvaticus', edib: 'u', q: 'Rjavoluski kukmak', kat: 'uzitne',
          spec: { klobuk: '#a07a55', rob: '#cfb08a', oblika: 'kupola', sirina: 62, visina: 40, dno: 'listi', listiBarva: 'rgba(120,70,70,.5)', cevke: '#e8b3b3', noga: '#efe6dc', nogaV: 56, nogaS: 18, nogaS2: 26, mreza: null, ovoj: null, obroc: 'visec', luske: '#6e4a30', rez: '#f2c6b8' },
          sledi: {
            klobuk: 'Rjav, 9 cm, pokrit z drobnimi rjavimi luskami na svetli podlagi.',
            spodaj: 'Listi so sprva svetlo rožnati, pozneje temno rjavi.',
            noga: 'Bela, z obročkom v obliki krilca. Ob pritisku rahlo zardi.',
            dno: 'Spodaj odebeljena, brez vrečaste ovojnice.',
            meso: 'Ob rezu postane rdečkasto, čez nekaj minut rjavkasto. Vonj je prijeten, po gobah ali mandljih.',
            okolje: 'Smrekov gozd, med iglicami.'
          }
        },
        {
          id: 'karbolni', ime: 'Karbolni kukmak', lat: 'Agaricus xanthodermus', edib: 's', q: 'Karbolni kukmak', kat: 'strupene',
          spec: { klobuk: '#e8e4d8', rob: '#f4f1e8', oblika: 'kupola', sirina: 64, visina: 44, dno: 'listi', listiBarva: 'rgba(110,70,70,.5)', cevke: '#e3b6b6', noga: '#efeadf', nogaV: 56, nogaS: 18, nogaS2: 28, mreza: null, ovoj: null, obroc: 'visec', rez: '#e8cf3a' },
          sledi: {
            klobuk: 'Bel do sivkast, 9 cm, kockaste oblike. Ob dotiku se obarva rumeno.',
            spodaj: 'Listi so sprva rožnati, pozneje temno rjavi.',
            noga: 'Bela, z velikim obročkom. Spodaj je rumenkasto obarvana.',
            dno: 'Spodaj odebeljena. Ob rezu pri dnu noge hitro zasije kromovo rumeno.',
            meso: 'Ob rezu pri dnu noge zasije kromovo rumeno. Vonj je po karbolu ali črnilu.',
            okolje: 'Park, vrt, rob gozda, tudi travnik.'
          }
        }
      ]
    },
    {
      id: 'dezniki2', naslov: 'Primer: dežnik z bodicami',
      uvod: 'Na gozdnem robu rastejo dežnikom podobne gobe. Ena ima klobuk, kot da bi bil pokrit z drobnimi bodicami. Preglej jo.',
      razlaga: 'Poljski dežnik ima kožico klobuka razpokano v velike ploščate krpe in gladko nogo. Bodičasti dežnik ima ostre, vzravnane bodice, nogo pod obročkom luskasto in neprijeten vonj. Če klobuk ni velik in gladek, dežnika ne nabiraj.',
      vrste: [
        {
          id: 'poljski', ime: 'Poljski dežnik', lat: 'Macrolepiota excoriata', edib: 'u', q: 'Poljski dežnik', kat: 'uzitne',
          spec: { klobuk: '#d9c7a4', rob: '#ece1c6', oblika: 'kupola', sirina: 66, visina: 34, dno: 'listi', cevke: '#f4efe2', noga: '#e2d2b0', nogaV: 80, nogaS: 12, nogaS2: 18, mreza: null, ovoj: null, obroc: 'drsni', luske: '#bba17a', izboklina: '#9d7b4e', rez: '#fbf8ee' },
          sledi: {
            klobuk: 'Svetlo rjav, 10 cm. Kožica je razpokana v velike ploščate krpe.',
            spodaj: 'Listi so beli in prosti.',
            noga: 'Gladka, svetla, 12 cm, z enostavnim premičnim obročkom.',
            dno: 'Spodaj rahlo odebeljena, brez ovojnice.',
            meso: 'Meso je belo in mehko. Vonj je prijeten.',
            okolje: 'Pašnik in travnik, tudi rob gozda na odprtem.'
          }
        },
        {
          id: 'bodicasti', ime: 'Bodičasti dežnik', lat: 'Echinoderma asperum', edib: 's', q: 'Bodičasti dežnik', kat: 'strupene',
          spec: { klobuk: '#a35b3d', rob: '#c48660', oblika: 'kupola', sirina: 46, visina: 30, dno: 'listi', cevke: '#f3ede0', noga: '#d9bfa4', nogaV: 56, nogaS: 11, nogaS2: 14, mreza: null, ovoj: null, obroc: 'tanek', bodice: '#6e2f1d', rez: '#f8f2e4' },
          sledi: {
            klobuk: 'Rdečkasto rjav, 7 cm, pokrit z ostrimi, vzravnanimi bodicami.',
            spodaj: 'Listi so beli do kremni.',
            noga: 'Pod obročkom luskasta in kosmata, nad njim gladka.',
            dno: 'Spodaj brez gomolja.',
            meso: 'Meso je belo. Vonj je neprijeten.',
            okolje: 'Gozd in kompost, med odpadlim listjem.'
          }
        }
      ]
    },
    {
      id: 'golobice', naslov: 'Primer: rdeča golobica na mahu',
      uvod: 'Otrok je v mahu našel rdečo gobo in jo hoče pokazati učiteljici. Mama pravi, da so golobice vse užitne. Res?',
      razlaga: 'Mnoge golobice so užitne, a ne vse. Užitna golobica ima blag, oreškast okus in bledo rožnat klobuk. Bljuvna golobica je svetleče rdeča in zelo pekoča; povzroča bruhanje. Pravilo: pekoča golobica ne gre v košaro.',
      vrste: [
        {
          id: 'vesca', ime: 'Užitna golobica', lat: 'Russula vesca', edib: 'u', q: 'Užitna golobica', kat: 'uzitne',
          spec: { klobuk: '#c9a79a', rob: '#dcc2b6', oblika: 'kupola', sirina: 60, visina: 36, dno: 'listi', listiBarva: 'rgba(235,225,205,.7)', cevke: '#f4f0e4', noga: '#f2eee4', nogaV: 46, nogaS: 22, nogaS2: 20, mreza: null, ovoj: null, obroc: null, rez: '#fbf9f0' },
          sledi: {
            klobuk: 'Bledo rožnato rjav, 8 cm. Kožica ne sega do roba in razkrije konce listov.',
            spodaj: 'Listi so beli, gosti in krhki.',
            noga: 'Bela in čokata, lahko z rjastimi pegami.',
            dno: 'Spodaj rahlo zožena, brez ovojnice.',
            meso: 'Meso je belo in trdno. Okus je blag, oreškast.',
            okolje: 'Listnati gozd, bukev in hrast.'
          }
        },
        {
          id: 'bljuvna', ime: 'Bljuvna golobica', lat: 'Russula emetica', edib: 's', q: 'Bljuvna golobica', kat: 'strupene',
          spec: { klobuk: '#c3202c', rob: '#d9505a', oblika: 'kupola', sirina: 54, visina: 34, dno: 'listi', listiBarva: 'rgba(235,230,220,.7)', cevke: '#f4efe6', noga: '#f1ddd8', nogaV: 48, nogaS: 18, nogaS2: 18, mreza: null, ovoj: null, obroc: null, rez: '#fbf8f0' },
          sledi: {
            klobuk: 'Sijoče češnjevo rdeč, 6 cm, lepljiv, z rahlo progastim robom.',
            spodaj: 'Listi so beli.',
            noga: 'Bela do rožnata in krhka.',
            dno: 'Spodaj brez gomolja.',
            meso: 'Meso je belo in krhko. Okus je zelo pekoč.',
            okolje: 'Iglasti gozd, vlažna mahovita tla, tudi močvirje.'
          }
        }
      ]
    },
    {
      id: 'mlecnici', naslov: 'Primer: mlečnica pod brezo',
      uvod: 'Pod brezo rastejo oranžkaste gobe, ob rezu pa izteka mleko. Nabiralec: »Mlečnice so dobre za vlaganje.« Preveri.',
      razlaga: 'Sočna mlečnica izteka obilo belega mleka, ki porjavi, klobuk pa je žametast in gladek. Kosmata mlečnica ima kosmat, navznoter zavit rob in pekoče mleko; surova je strupena.',
      vrste: [
        {
          id: 'socna', ime: 'Sočna mlečnica', lat: 'Lactifluus volemus', edib: 'u', q: 'Sočna mlečnica', kat: 'uzitne',
          spec: { klobuk: '#b9783a', rob: '#cf9660', oblika: 'kupola', sirina: 60, visina: 30, dno: 'listi', listiBarva: 'rgba(235,215,185,.7)', cevke: '#eadbc3', noga: '#c8935a', nogaV: 60, nogaS: 20, nogaS2: 22, mreza: null, ovoj: null, obroc: null, rez: '#f8eed8' },
          sledi: {
            klobuk: 'Oranžno rjav, 10 cm, žametast, z gladkim robom.',
            spodaj: 'Listi so kremni in gosti.',
            noga: 'Čvrsta, oranžno rjava in gladka.',
            dno: 'Spodaj brez gomolja.',
            meso: 'Ob rezu izteka obilo belega mleka, ki ob zraku porjavi. Pri starejših gobah je vonj po ribah.',
            okolje: 'Listnati gozd, bukev in hrast, jeseni.'
          }
        },
        {
          id: 'kosmata', ime: 'Kosmata mlečnica', lat: 'Lactarius torminosus', edib: 's', q: 'Kosmata mlečnica', kat: 'strupene',
          spec: { klobuk: '#e1a98d', rob: '#efc3ab', oblika: 'lijak', sirina: 56, visina: 24, dno: 'listi', listiBarva: 'rgba(235,215,195,.7)', cevke: '#eadac8', noga: '#eacbb8', nogaV: 40, nogaS: 18, nogaS2: 18, mreza: null, ovoj: null, obroc: null, krogi: '#b87c62', rez: '#faf3e6' },
          sledi: {
            klobuk: 'Rožnat do bledo oranžen, 8 cm, s krogi in kosmatim, navznoter zavitim robom.',
            spodaj: 'Listi so kremni in gosti.',
            noga: 'Kratka, bledo rožnata in votla, z jamicami.',
            dno: 'Spodaj rahlo zožena.',
            meso: 'Mleko je belo in ostro, pekoče. Meso je krhko.',
            okolje: 'Pod brezami, na vlažnih tleh.'
          }
        }
      ]
    },
    {
      id: 'koprenke', naslov: 'Primer: rjavi klobuki v bukovem gozdu',
      uvod: 'Na kislih tleh pod bukvami raste skupina rdečkasto rjavih gob. Gobar jih šteje za »navadne koprenke«. Pomagaj mu.',
      razlaga: 'To je ena nevarnejših zamenjav: poljska koprenka vsebuje strup, ki po nekaj dneh poškoduje ledvice, ko je obrok že pozabljen. Pšenična koprenka ima velik obroček in svilnato svetel rob klobuka, poljska koprenka obroča nima in diši po redkvici. Brez obročka in z vonjem po redkvici gobe ne nabiraj.',
      vrste: [
        {
          id: 'psenicna', ime: 'Pšenična koprenka', lat: 'Cortinarius caperatus', edib: 'u', q: 'Pšenična koprenka', kat: 'uzitne',
          spec: { klobuk: '#c9a24a', rob: '#e6cf9a', oblika: 'kupola', sirina: 66, visina: 38, dno: 'listi', listiBarva: 'rgba(150,100,60,.5)', cevke: '#d6b58a', noga: '#e2d5b4', nogaV: 62, nogaS: 24, nogaS2: 30, mreza: null, ovoj: null, obroc: 'visec', krogi: '#a8842f', rez: '#f9f5e8' },
          sledi: {
            klobuk: 'Ocker rumen, 9 cm, nagubran, na robu svilnato svetel kot oprašen.',
            spodaj: 'Listi so glinasto rjavi in gosti.',
            noga: 'Debela in svetla, s širokim, membranastim obročkom.',
            dno: 'Spodaj brez gomolja in brez ovojnice.',
            meso: 'Meso je belo. Vonj je prijeten.',
            okolje: 'Smrekov gozd, mah in borovnice, pozno poleti in jeseni.'
          }
        },
        {
          id: 'poljska', ime: 'Poljska koprenka', lat: 'Cortinarius orellanus', edib: 'd', q: 'Poljska koprenka', kat: 'strupene',
          spec: { klobuk: '#b5601f', rob: '#cf8240', oblika: 'kupola', sirina: 50, visina: 30, dno: 'listi', listiBarva: 'rgba(170,80,30,.75)', cevke: '#c26a2a', noga: '#c99a5a', nogaV: 64, nogaS: 14, nogaS2: 16, mreza: null, ovoj: null, obroc: null, izboklina: '#8a4513', rez: '#ecd79a' },
          sledi: {
            klobuk: 'Oranžno rjav, 6 cm, drobno žametast, v sredini rahla izboklina.',
            spodaj: 'Listi so rjasto oranžni in razmaknjeni.',
            noga: 'Rumenkasto rjava, brez pravega obročka. Le sledi rjavih nitk (koprene).',
            dno: 'Spodaj rahlo odebeljena, brez ovojnice.',
            meso: 'Meso je rumenkasto. Vonj je po redkvici.',
            okolje: 'Bukov in hrastov gozd, kisla tla.'
          }
        }
      ]
    },
    {
      id: 'kolobarnice', naslov: 'Primer: siva goba pod smreko',
      uvod: 'V gorskem smrekovem gozdu je velika siva goba. »Kolobarnica, jedla sem jih že,« pravi nabiralka. Katera?',
      razlaga: 'Pegasta kolobarnica je večja, mesnata in ima grobe luske; prstena je manjša, tanka in drobno luskasta. Pegasta je zelo strupena. Po velikosti in debelini mesa ju je mogoče ločiti, a pri sivih kolobarnicah je zamenjava pogosta in nevarna.',
      vrste: [
        {
          id: 'prstena', ime: 'Prstena kolobarnica', lat: 'Tricholoma terreum', edib: 'u', q: 'Prstena kolobarnica', kat: 'uzitne',
          spec: { klobuk: '#8a8c8f', rob: '#a8aaad', oblika: 'kupola', sirina: 48, visina: 28, dno: 'listi', listiBarva: 'rgba(210,210,205,.7)', cevke: '#e8e8e4', noga: '#ecebe6', nogaV: 46, nogaS: 12, nogaS2: 13, mreza: null, ovoj: null, obroc: null, luske: '#5c5e62', rez: '#f5f5f2' },
          sledi: {
            klobuk: 'Siv, 5 cm, pokrit z drobnimi, mehkimi sivimi luskami. Sredina je temnejša.',
            spodaj: 'Listi so beli do sivkasti in redki.',
            noga: 'Bela in tanka, brez obročka.',
            dno: 'Spodaj brez gomolja.',
            meso: 'Meso je tanko in belo. Vonj je po moki, okus blag.',
            okolje: 'Iglasti gozd, pod borom in smreko, pozno jeseni.'
          }
        },
        {
          id: 'pegasta', ime: 'Pegasta kolobarnica', lat: 'Tricholoma pardinum', edib: 'z', q: 'Pegasta kolobarnica', kat: 'strupene',
          spec: { klobuk: '#7b7466', rob: '#9a9382', oblika: 'kupola', sirina: 76, visina: 46, dno: 'listi', listiBarva: 'rgba(235,230,215,.75)', cevke: '#f0ecdc', noga: '#e6dfc4', nogaV: 60, nogaS: 30, nogaS2: 34, mreza: null, ovoj: null, obroc: null, luske: '#4c453a', rez: '#faf8f0' },
          sledi: {
            klobuk: 'Siv, 12 cm, debel, z velikimi grobimi sivorjavimi luskami.',
            spodaj: 'Listi so debeli in beli, pri starih gobah z rumenkastimi do zelenkastimi pegami.',
            noga: 'Debela in čvrsta, bela do rumenkasta, brez obročka.',
            dno: 'Spodaj odebeljena, brez ovojnice.',
            meso: 'Meso je belo in zelo debelo. Vonj je po moki.',
            okolje: 'Gorski smrekov gozd na apnencu.'
          }
        }
      ]
    }
  ];

  /* Sledi, ki par res ločijo (po razlagi para). Po odgovoru igra pokaže, ali jih je igralec pregledal. */
  var KLJUCNE_SLEDI = {
    goban: ['noga', 'spodaj', 'meso'], lisicka: ['spodaj', 'meso', 'klobuk'], kukmak: ['spodaj', 'dno', 'noga'],
    dezniki: ['klobuk', 'noga', 'meso'], tintnice: ['klobuk', 'noga', 'dno'], musnice: ['noga', 'meso', 'spodaj'],
    mraznice: ['spodaj', 'noga', 'dno'], sirovke: ['meso', 'spodaj'], gobani: ['klobuk', 'noga', 'dno'],
    zelene: ['spodaj', 'meso'], kukmaki2: ['dno', 'meso'], dezniki2: ['klobuk', 'noga'],
    golobice: ['meso', 'klobuk'], mlecnici: ['meso', 'klobuk'], koprenke: ['noga', 'meso', 'klobuk'],
    kolobarnice: ['klobuk', 'spodaj']
  };
  PARI.forEach(function (p) { p.kljuc = KLJUCNE_SLEDI[p.id] || []; });

  var STRIPOV = SLEDI.length;
  var MIN_SLEDI_ZA_BONUS = 4;     // preglej vsaj toliko sledi, da dobiš bonus
  var T_PRAVILNO = 2;
  var T_BONUS = 1;
  var MAX_SIBKIH = 2;             // največ toliko šibkih parov na krog
  var KROG_DOLZINA = 6;           // primerov v enem krogu (iz vseh parov se žreba šest)
  var NAJVEC_TOCK = KROG_DOLZINA * (T_PRAVILNO + T_BONUS);

  /* ── Model ───────────────────────────────────────────────────────────── */
  function nakljucno(rng, n) { return Math.floor(rng() * n); }

  function premesaj(arr, rng) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = nakljucno(rng, i + 1), t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  /* En primer iz para z indeksom pi: ena njegova vrsta je resnica, ponudbi doda vrsto iz drugega para. */
  function sestaviPrimer(pi, rng) {
    var par = PARI[pi];
    var ti = nakljucno(rng, par.vrste.length);
    var resnica = par.vrste[ti];
    var drug = PARI[(pi + 1 + nakljucno(rng, PARI.length - 1)) % PARI.length];
    var vabljiva = drug.vrste[nakljucno(rng, drug.vrste.length)];
    var ponudba = premesaj(par.vrste.concat([vabljiva]), rng).map(function (v) { return v.id; });
    return { par: par.id, resnica: resnica.id, ponudba: ponudba };
  }

  /* Krog: KROG_DOLZINA naključnih parov, iz vsakega en primerek; ponujene so
   * obe vrsti para in ena vrsta iz drugega para (ta ni nikoli iz istega para).
   * Z `parIds` se krog sestavi samo iz teh parov (ponovitev napačnih primerov). */
  function sestaviKrog(rng, parIds, sibki) {
    rng = rng || Math.random;
    var indeksi, sibkiIdx = [];
    if (parIds) {
      indeksi = parIds.map(function (id) { return PARI.indexOf(najdiPar(id)); }).filter(function (i) { return i >= 0; });
    } else {
      // Šibka področja (pari, kjer se je igralec že zmotil): do MAX_SIBKIH jih ponudimo znova, ostalo je naključno.
      sibkiIdx = premesaj(Object.keys(sibki || {}).map(function (id) { return PARI.indexOf(najdiPar(id)); })
        .filter(function (i) { return i >= 0; }), rng).slice(0, MAX_SIBKIH);
      var ostali = premesaj(PARI.map(function (_, i) { return i; }).filter(function (i) { return sibkiIdx.indexOf(i) < 0; }), rng);
      indeksi = premesaj(sibkiIdx.concat(ostali.slice(0, KROG_DOLZINA - sibkiIdx.length)), rng);
    }
    return indeksi.map(function (pi) {
      var pr = sestaviPrimer(pi, rng);
      if (sibkiIdx.indexOf(pi) >= 0) pr.sibek = true;
      return pr;
    });
  }

  function najdiVrsto(id) {
    for (var i = 0; i < PARI.length; i++)
      for (var j = 0; j < PARI[i].vrste.length; j++)
        if (PARI[i].vrste[j].id === id) return PARI[i].vrste[j];
    return null;
  }
  function najdiPar(id) {
    for (var i = 0; i < PARI.length; i++) if (PARI[i].id === id) return PARI[i];
    return null;
  }

  /* Ocena enega primera. »Nevarna napaka« = igralec bi pojedel nekaj, kar ni
   * užitno ali pogojno užitno brez priprave. */
  function oceni(primer, izbranId, steviloSledi) {
    var res = najdiVrsto(primer.resnica), izb = najdiVrsto(izbranId);
    var prav = izbranId === primer.resnica;
    var tocke = 0, bonus = false;
    if (prav) {
      tocke = T_PRAVILNO;
      if (steviloSledi >= MIN_SLEDI_ZA_BONUS) { tocke += T_BONUS; bonus = true; }
    }
    var nevarna = !prav && !!izb && (izb.edib === 'u') && res.edib !== 'u';
    return { prav: prav, tocke: tocke, bonus: bonus, nevarna: nevarna, resnica: res, izbrana: izb };
  }

  /* Katere ključne sledi para je igralec pregledal in katere spregledal. */
  function kljucneSledi(parId, pregledane) {
    var par = najdiPar(parId), kljuc = par ? par.kljuc : [];
    return {
      pregledane: kljuc.filter(function (k) { return pregledane[k]; }),
      spregledane: kljuc.filter(function (k) { return !pregledane[k]; })
    };
  }

  function naziv(tocke, najvec) {
    var d = tocke / (najvec || NAJVEC_TOCK);
    if (d >= 0.9) return 'Mojster detektiv';
    if (d >= 0.65) return 'Gobji detektiv';
    if (d >= 0.35) return 'Pripravnik';
    return 'Začetnik: raje vprašaj izkušenega gobarja';
  }

  /* Povzetek vremena iz /detektiv/vreme (zadnji dnevi IREICA1: date, tmax, tmin, precip).
   * Samo računa nad podanimi dnevi; brez dni vrne null (kartica se ne pokaže). */
  function povzetekVremena(days) {
    if (!days || !days.length) return null;
    var tmax = -Infinity, tmin = Infinity, dez = 0, dniDez = 0, zadnjiDez = null;
    days.forEach(function (d) {
      if (d.tmax > tmax) tmax = d.tmax;
      if (d.tmin < tmin) tmin = d.tmin;
      dez += d.precip;
      if (d.precip >= 0.2) { dniDez++; zadnjiDez = d.date; }
    });
    return { n: days.length, tmin: tmin, tmax: tmax, dez: Math.round(dez * 10) / 10, dniDez: dniDez,
             zadnjiDez: zadnjiDez, zadnji: days[days.length - 1].date };
  }

  var model = {
    povzetekVremena: povzetekVremena,
    PARI: PARI, SLEDI: SLEDI, SLEDI_IME: SLEDI_IME, EDIB: EDIB,
    NAJVEC_TOCK: NAJVEC_TOCK, MAX_SIBKIH: MAX_SIBKIH, KROG_DOLZINA: KROG_DOLZINA, MIN_SLEDI_ZA_BONUS: MIN_SLEDI_ZA_BONUS,
    sestaviKrog: sestaviKrog, oceni: oceni, naziv: naziv, kljucneSledi: kljucneSledi,
    najdiVrsto: najdiVrsto, najdiPar: najdiPar
  };

  if (typeof module !== 'undefined' && module.exports) { module.exports = model; }
  if (typeof document === 'undefined') { return; }

  /* ── Risanje gob (SVG) ───────────────────────────────────────────────── */
  var NS = 'http://www.w3.org/2000/svg';

  function seme(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return function () {
      h += 0x6D2B79F5; var t = h;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function capPot(cx, y, w, h, oblika) {
    var k = { kupola: 1.3, lijak: 0.95, valj: 1.0, zvonec: 1.45 }[oblika] || 1.3;
    if (oblika === 'valj') {
      return 'M' + (cx - w) + ',' + y + ' L' + (cx - w) + ',' + (y - h * 0.65) +
        ' Q' + (cx - w) + ',' + (y - h) + ' ' + cx + ',' + (y - h) +
        ' Q' + (cx + w) + ',' + (y - h) + ' ' + (cx + w) + ',' + (y - h * 0.65) +
        ' L' + (cx + w) + ',' + y + ' Q' + cx + ',' + (y + 6) + ' ' + (cx - w) + ',' + y + 'Z';
    }
    if (oblika === 'zvonec') {
      return 'M' + (cx - w) + ',' + y + ' C' + (cx - w) + ',' + (y - h * 1.2) + ' ' + (cx - w * 0.55) + ',' + (y - h * 1.15) + ' ' + cx + ',' + (y - h * 1.15) +
        ' C' + (cx + w * 0.55) + ',' + (y - h * 1.15) + ' ' + (cx + w) + ',' + (y - h * 1.2) + ' ' + (cx + w) + ',' + y +
        ' Q' + cx + ',' + (y + 7) + ' ' + (cx - w) + ',' + y + 'Z';
    }
    return 'M' + (cx - w) + ',' + y + ' C' + (cx - w) + ',' + (y - h * k) + ' ' + (cx + w) + ',' + (y - h * k) + ' ' + (cx + w) + ',' + y +
      ' Q' + cx + ',' + (y + h * 0.22) + ' ' + (cx - w) + ',' + y + 'Z';
  }

  function el(ime, atr, notr) {
    var s = '<' + ime;
    for (var k in atr) { if (atr[k] != null) s += ' ' + k + '="' + atr[k] + '"'; }
    return s + (notr == null ? '/>' : '>' + notr + '</' + ime + '>');
  }

  function tla(v) {
    return el('ellipse', { cx: 150, cy: 232, rx: 128, ry: 14, fill: '#2b2118' }) +
      el('ellipse', { cx: 150, cy: 229, rx: 122, ry: 10, fill: '#46341f' }) +
      el('path', { d: 'M40 226 q6 -14 12 0 M70 228 q5 -10 10 0 M222 227 q6 -13 12 0 M248 229 q4 -9 8 0', stroke: '#4f7a3b', 'stroke-width': 2.4, fill: 'none', 'stroke-linecap': 'round' });
  }

  function risiCelo(sp, id) {
    var cx = 150, baza = 226, w = sp.sirina, h = sp.visina;
    var stebloZgoraj = baza - sp.nogaV;
    var capY = stebloZgoraj + (sp.oblika === 'lijak' ? 6 : 4);
    var rng = seme(id), g = '';
    // ovojnica ob dnu (za nogo)
    if (sp.ovoj === 'vreca') {
      g += el('path', { d: 'M' + (cx - 26) + ',' + baza + ' C' + (cx - 30) + ',' + (baza - 26) + ' ' + (cx - 14) + ',' + (baza - 42) + ' ' + (cx - 8) + ',' + (baza - 36) + ' L' + (cx + 8) + ',' + (baza - 36) + ' C' + (cx + 14) + ',' + (baza - 42) + ' ' + (cx + 30) + ',' + (baza - 26) + ' ' + (cx + 26) + ',' + baza + 'Z', fill: '#f4f0e2', stroke: '#c9c1a7', 'stroke-width': 1.2 });
    }
    // noga
    var s1 = sp.nogaS, s2 = sp.nogaS2;
    g += el('path', { d: 'M' + (cx - s1 / 2) + ',' + capY + ' C' + (cx - s1 / 2) + ',' + (capY + sp.nogaV * 0.45) + ' ' + (cx - s2 / 2) + ',' + (baza - sp.nogaV * 0.25) + ' ' + (cx - s2 / 2) + ',' + baza +
      ' L' + (cx + s2 / 2) + ',' + baza + ' C' + (cx + s2 / 2) + ',' + (baza - sp.nogaV * 0.25) + ' ' + (cx + s1 / 2) + ',' + (capY + sp.nogaV * 0.45) + ' ' + (cx + s1 / 2) + ',' + capY + 'Z', fill: sp.noga, stroke: 'rgba(0,0,0,.25)', 'stroke-width': 1 });
    if (sp.ovoj === 'gomolj' || sp.ovoj === 'rob') {
      g += el('ellipse', { cx: cx, cy: baza - 8, rx: s2 / 2 + 8, ry: 12, fill: sp.noga, stroke: 'rgba(0,0,0,.25)', 'stroke-width': 1 });
      if (sp.ovoj === 'rob') g += el('path', { d: 'M' + (cx - s2 / 2 - 7) + ',' + (baza - 14) + ' q' + (s2 / 2 + 7) + ',6 ' + (s2 + 14) + ',0 M' + (cx - s2 / 2 - 5) + ',' + (baza - 8) + ' q' + (s2 / 2 + 5) + ',6 ' + (s2 + 10) + ',0', stroke: '#b9b09a', 'stroke-width': 1.6, fill: 'none' });
    }
    // vzorci na nogi
    if (sp.mreza === 'bela' || sp.mreza === 'temna' || sp.mreza === 'rdeca') {
      var kol = sp.mreza === 'bela' ? '#fffaf0' : sp.mreza === 'rdeca' ? '#b3262d' : '#5a3a22', dol = sp.mreza === 'bela' ? sp.nogaV * 0.35 : sp.nogaV * 0.8, d = '';
      for (var i = 0; i < dol; i += 6) {
        var wi = s1 / 2 - 4 + (s2 / 2 - s1 / 2) * (i / sp.nogaV);
        d += 'M' + (cx - wi) + ',' + (capY + 6 + i) + ' l' + wi + ',5 l' + wi + ',-5 M' + (cx - wi) + ',' + (capY + 9 + i) + ' l' + wi + ',5 l' + wi + ',-5 ';
      }
      g += el('path', { d: d, stroke: kol, 'stroke-width': sp.mreza === 'bela' ? 1 : 1.5, fill: 'none', opacity: sp.mreza === 'bela' ? 0.85 : 0.9 });
    }
    if (sp.mreza === 'kaca') {
      var dk = '';
      for (var y = capY + 20; y < baza - 8; y += 7) {
        var ww = (s1 + (s2 - s1) * ((y - capY) / sp.nogaV)) / 2 - 1;
        dk += 'M' + (cx - ww) + ',' + y + ' l' + (ww / 2) + ',4 l' + (ww / 2) + ',-4 l' + (ww / 2) + ',4 l' + (ww / 2) + ',-4 ';
      }
      g += el('path', { d: dk, stroke: sp.luske || '#8d6a43', 'stroke-width': 1.4, fill: 'none', opacity: 0.8 });
    }
    // obroček
    var ry = capY + sp.nogaV * 0.2;
    if (sp.obroc) {
      var rw = { tanek: s1 * 0.95, visec: s1 * 1.9, progast: s1 * 1.9, gladek: s1 * 1.2, drsni: s1 * 1.9, sled: s1 * 0.6 }[sp.obroc] || s1;
      if (sp.obroc === 'sled') ry = capY + sp.nogaV * 0.55;
      g += el('path', { d: 'M' + (cx - rw / 2 - 2) + ',' + ry + ' Q' + cx + ',' + (ry + 12) + ' ' + (cx + rw / 2 + 2) + ',' + ry + ' L' + (cx + rw / 2) + ',' + (ry + 4) + ' Q' + cx + ',' + (ry + 16) + ' ' + (cx - rw / 2) + ',' + (ry + 4) + 'Z', fill: sp.obroc === 'sled' ? 'rgba(80,60,40,.35)' : '#f7f2e4', stroke: '#b9b09a', 'stroke-width': 1 });
      if (sp.obroc === 'progast') {
        var pr = '';
        for (var q = -rw / 2 + 4; q < rw / 2; q += 4) pr += 'M' + (cx + q) + ',' + (ry + 2) + ' l0,6 ';
        g += el('path', { d: pr, stroke: '#9f9784', 'stroke-width': 0.9, fill: 'none' });
      }
    }
    // klobuk
    g += el('path', { d: capPot(cx, capY, w, h, sp.oblika), fill: sp.klobuk, stroke: 'rgba(0,0,0,.28)', 'stroke-width': 1.2 });
    g += el('path', { d: 'M' + (cx - w + 4) + ',' + (capY - 3) + ' Q' + cx + ',' + (capY + 5) + ' ' + (cx + w - 4) + ',' + (capY - 3), fill: 'none', stroke: sp.rob, 'stroke-width': 3.2, opacity: 0.75, 'stroke-linecap': 'round' });
    if (sp.oblika === 'lijak') g += el('ellipse', { cx: cx, cy: capY - h * 0.4, rx: w * 0.4, ry: h * 0.22, fill: 'rgba(0,0,0,.18)' });
    if (sp.izboklina) g += el('ellipse', { cx: cx, cy: capY - h * 0.85, rx: w * 0.2, ry: h * 0.16, fill: sp.izboklina });
    if (sp.krogi) {
      var kr = '';
      for (var q = 1; q <= 3; q++) kr += 'M' + (cx - w * q / 3.6) + ',' + (capY - h * 0.15) + ' Q' + cx + ',' + (capY - h * (0.3 + 0.22 * q)) + ' ' + (cx + w * q / 3.6) + ',' + (capY - h * 0.15) + ' ';
      g += el('path', { d: kr, stroke: sp.krogi, 'stroke-width': 1.6, fill: 'none', opacity: 0.8 });
    }
    if (sp.bodice) {
      for (var bi = 0; bi < Math.round(w / 2.4); bi++) {
        var ba = rng() * Math.PI, br = rng() * 0.85;
        var bx = cx + Math.cos(ba) * w * br * (rng() < 0.5 ? -1 : 1), by = capY - Math.sin(ba) * h * 0.9 * (1 - br * br * 0.4);
        g += el('path', { d: 'M' + (bx - 2).toFixed(1) + ',' + by.toFixed(1) + ' l2,-6 l2,6Z', fill: sp.bodice, opacity: 0.9 });
      }
    }
    // luske, bradavice
    var n = Math.round(w / 3.2);
    for (var j = 0; j < n; j++) {
      var a = rng() * Math.PI, rr = rng() * 0.88;
      var px = cx + Math.cos(a) * w * rr * (rng() < 0.5 ? -1 : 1), py = capY - Math.sin(a) * h * 0.95 * (1 - rr * rr * 0.4) * 0.9;
      if (sp.bradavice) g += el('circle', { cx: px.toFixed(1), cy: py.toFixed(1), r: (1.6 + rng() * 1.8).toFixed(1), fill: sp.bradavice, opacity: 0.92 });
      else if (sp.luske) g += el('ellipse', { cx: px.toFixed(1), cy: py.toFixed(1), rx: (2 + rng() * 3).toFixed(1), ry: 1.4, fill: sp.luske, opacity: 0.7 });
    }
    return g;
  }

  function risiSpodaj(sp, id) {
    var cx = 150, cy = 120, rx = Math.min(sp.sirina * 1.5, 128), ry = rx * 0.68, rng = seme(id + 'u'), g = '';
    g += el('ellipse', { cx: cx, cy: cy, rx: rx, ry: ry, fill: sp.klobuk, stroke: 'rgba(0,0,0,.3)', 'stroke-width': 1.2 });
    g += el('ellipse', { cx: cx, cy: cy, rx: rx - 7, ry: ry - 6, fill: sp.cevke });
    var d = '', i, a;
    if (sp.dno === 'cevke') {
      for (var r = 12; r < rx - 8; r += 7) {
        var m = Math.round(r * 0.9);
        for (i = 0; i < m; i++) {
          a = (i / m) * Math.PI * 2;
          d += 'M' + (cx + Math.cos(a) * r).toFixed(1) + ',' + (cy + Math.sin(a) * r * 0.68).toFixed(1) + ' l0.1,0 ';
        }
      }
      g += el('path', { d: d, stroke: 'rgba(0,0,0,.4)', 'stroke-width': 2.3, 'stroke-linecap': 'round', fill: 'none' });
    } else {
      var cnt = sp.dno === 'grebeni' ? 26 : 74;
      for (i = 0; i < cnt; i++) {
        a = (i / cnt) * Math.PI * 2;
        var r0 = 12, r1 = rx - 8, x0 = cx + Math.cos(a) * r0, y0 = cy + Math.sin(a) * r0 * 0.68, x1 = cx + Math.cos(a) * r1, y1 = cy + Math.sin(a) * r1 * 0.68;
        d += 'M' + x0.toFixed(1) + ',' + y0.toFixed(1) + ' L' + x1.toFixed(1) + ',' + y1.toFixed(1) + ' ';
        if (sp.dno === 'grebeni' || (sp.dno === 'listi' && rng() < 0.3)) {
          var am = a + 0.07, xm = cx + Math.cos(am) * (r1 * 0.62), ym = cy + Math.sin(am) * (r1 * 0.62) * 0.68;
          d += 'M' + xm.toFixed(1) + ',' + ym.toFixed(1) + ' L' + (cx + Math.cos(a + 0.12) * r1).toFixed(1) + ',' + (cy + Math.sin(a + 0.12) * r1 * 0.68).toFixed(1) + ' ';
        }
      }
      var barva = sp.dno === 'listi' ? (sp.listiBarva || { kukmak: 'rgba(92,40,48,.55)', velika: 'rgba(30,30,30,.55)', gola: 'rgba(40,40,40,.5)' }[id] || 'rgba(120,100,80,.45)') : 'rgba(110,60,10,.5)';
      g += el('path', { d: d, stroke: barva, 'stroke-width': sp.dno === 'grebeni' ? 3 : 1.6, fill: 'none', 'stroke-linecap': 'round' });
    }
    g += el('ellipse', { cx: cx, cy: cy, rx: Math.max(sp.nogaS * 0.5, 7), ry: Math.max(sp.nogaS * 0.34, 5), fill: sp.noga, stroke: 'rgba(0,0,0,.35)', 'stroke-width': 1 });
    return g;
  }

  function risiDno(sp, id) {
    var cx = 150, g = '';
    g += el('rect', { x: 0, y: 150, width: 300, height: 110, fill: '#3b2a1b' });
    g += el('path', { d: 'M0 150 Q40 142 80 150 T160 150 T240 150 T300 150', fill: 'none', stroke: '#4f7a3b', 'stroke-width': 4 });
    var s2 = Math.max(sp.nogaS2, 10) * 1.5, zg = 40, spod = 200;
    if (sp.ovoj === 'vreca') {
      g += el('path', { d: 'M' + (cx - s2 * 0.85) + ',' + spod + ' C' + (cx - s2) + ',' + (zg + 60) + ' ' + (cx - s2 * 0.4) + ',' + (zg + 20) + ' ' + (cx - 8) + ',' + (zg + 34) + ' L' + (cx + 8) + ',' + (zg + 34) + ' C' + (cx + s2 * 0.4) + ',' + (zg + 20) + ' ' + (cx + s2) + ',' + (zg + 60) + ' ' + (cx + s2 * 0.85) + ',' + spod + 'Z', fill: '#f4f0e2', stroke: '#c9c1a7', 'stroke-width': 1.5 });
    }
    var topW = Math.max(sp.nogaS, 10) * 1.2, botW = s2;
    g += el('path', { d: 'M' + (cx - topW / 2) + ',' + zg + ' L' + (cx - botW / 2) + ',' + spod + ' Q' + cx + ',' + (spod + 12) + ' ' + (cx + botW / 2) + ',' + spod + ' L' + (cx + topW / 2) + ',' + zg + 'Z', fill: sp.noga, stroke: 'rgba(0,0,0,.3)', 'stroke-width': 1.2 });
    if (sp.ovoj === 'gomolj' || sp.ovoj === 'rob') {
      g += el('ellipse', { cx: cx, cy: spod - 12, rx: botW / 2 + 14, ry: 22, fill: sp.noga, stroke: 'rgba(0,0,0,.3)', 'stroke-width': 1.2 });
      if (sp.ovoj === 'rob') g += el('path', { d: 'M' + (cx - botW / 2 - 12) + ',' + (spod - 26) + ' q' + (botW / 2 + 12) + ',8 ' + (botW + 24) + ',0 M' + (cx - botW / 2 - 9) + ',' + (spod - 16) + ' q' + (botW / 2 + 9) + ',8 ' + (botW + 18) + ',0', stroke: '#b9b09a', 'stroke-width': 2, fill: 'none' });
    }
    if (sp.mreza === 'temna' || sp.mreza === 'rdeca') {
      var dd = '';
      for (var y = zg + 6; y < spod - 4; y += 9) {
        var wy = (topW + (botW - topW) * ((y - zg) / (spod - zg))) - 4;   // širina noge na tej višini
        dd += 'M' + (cx - wy / 2) + ',' + y + ' l' + (wy / 4) + ',6 l' + (wy / 4) + ',-6 l' + (wy / 4) + ',6 l' + (wy / 4) + ',-6 ';
      }
      g += el('path', { d: dd, stroke: sp.mreza === 'rdeca' ? '#b3262d' : '#5a3a22', 'stroke-width': 1.7, fill: 'none', opacity: 0.9 });
    }
    // presek
    g += el('circle', { cx: 245, cy: 58, r: 30, fill: sp.rez, stroke: 'rgba(255,255,255,.4)', 'stroke-width': 2 });
    g += el('text', { x: 245, y: 104, 'text-anchor': 'middle', 'font-size': 12, fill: '#d8dfec', 'font-family': 'sans-serif' }, 'presek mesa');
    return g;
  }

  function risi(vrsta, pogled) {
    var sp = vrsta.spec, vsebina;
    if (pogled === 'spodaj') vsebina = risiSpodaj(sp, vrsta.id);
    else if (pogled === 'dno') vsebina = risiDno(sp, vrsta.id);
    else vsebina = tla() + '<g transform="translate(150 228) scale(1.18) translate(-150 -228)">' + risiCelo(sp, vrsta.id) + '</g>';
    var opis = { cela: 'Celotna goba od strani', spodaj: 'Goba od spodaj', dno: 'Dno noge in presek mesa' }[pogled === 'spodaj' || pogled === 'dno' ? pogled : 'cela'];
    return '<svg viewBox="0 0 300 260" role="img" aria-label="' + opis + '" class="gd-svg">' +
      '<rect width="300" height="260" rx="14" fill="#1a2535"/>' + vsebina + '</svg>';
  }

  /* ── Prikaz ──────────────────────────────────────────────────────────── */
  root.GobarskiDetektiv = { model: model, risi: risi };   // za ročni pregled ilustracij

  var app = document.getElementById('gd-app');
  if (!app) { return; }

  var VREME_WORKER = 'https://weatherireica1.filip-eremita.workers.dev';
  var vreme = null;          // povzetek zadnjih dni IREICA1; null = ni podatka, kartice ni

  function dec(x) { return x.toFixed(1).replace('.', ','); }   // meritve vedno z decimalko
  function datumKratko(iso) { var p = iso.split('-'); return parseInt(p[2], 10) + '. ' + parseInt(p[1], 10) + '.'; }

  function vremeHtml() {
    if (!vreme) return '';
    var danes = new Date().toISOString().slice(0, 10);
    var staro = (Date.parse(danes) - Date.parse(vreme.zadnji)) / 86400000 > 3;
    var dez = vreme.dez > 0
      ? 'padavine skupaj ' + dec(vreme.dez) + ' mm (' + vreme.dniDez + (vreme.dniDez === 1 ? ' dan' : ' dni') + ' z dežjem' +
        (vreme.zadnjiDez ? ', zadnji dež ' + datumKratko(vreme.zadnjiDez) : '') + ')'
      : 'brez padavin';
    return '<div class="gd-vreme"><p class="gd-vreme-title">Vreme v Rečici ob Savinji, zadnjih ' + vreme.n + ' dni</p>' +
      '<p>Od ' + dec(vreme.tmin) + ' °C do ' + dec(vreme.tmax) + ' °C, ' + dez + '.' +
      (staro ? ' Zadnji zapis: ' + datumKratko(vreme.zadnji) + '.' : '') + '</p>' +
      '<p class="gd-vreme-note">Meritve postaje IREICA1 (zunanji senzor). Zgodbe v igri so izmišljene, vreme je pravo. ' +
      'Gobe rastejo po dežju in ob primernih temperaturah: <a href="/gobarska-napoved/danes/">gobarski indeks za danes</a>.</p></div>';
  }

  function naloziVreme() {
    if (!window.fetch) return;
    fetch(VREME_WORKER + '/detektiv/vreme')
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || !j.ok) return;
        vreme = povzetekVremena(j.days);
        var slot = document.getElementById('gd-vreme-slot');
        if (slot) slot.innerHTML = vremeHtml();
      })
      .catch(function () { /* brez podatka kartice ni, vrednosti se ne izmišljajo */ });
  }

  var KLJUC = 'gobarski-detektiv-rekord';
  var stanje = null;

  function shraniRekord(t) {
    try {
      var r = parseInt(localStorage.getItem(KLJUC) || '0', 10) || 0;
      if (t > r) { localStorage.setItem(KLJUC, String(t)); return t; }
      return r;
    } catch (e) { return t; }
  }
  function preberiRekord() {
    try { return parseInt(localStorage.getItem(KLJUC) || '0', 10) || 0; } catch (e) { return 0; }
  }

  /* Šibka področja: {parId: koliko zaporednih zmot}; pravilen odgovor par odstrani. Samo v brskalniku. */
  var KLJUC_SIBKI = 'gobarski-detektiv-sibki';
  function preberiSibke() {
    try {
      var o = JSON.parse(localStorage.getItem(KLJUC_SIBKI) || '{}');
      return o && typeof o === 'object' ? o : {};
    } catch (e) { return {}; }
  }
  function zabeleziOdgovor(parId, prav) {
    try {
      var o = preberiSibke();
      if (prav) delete o[parId]; else o[parId] = Math.min((o[parId] || 0) + 1, 3);
      localStorage.setItem(KLJUC_SIBKI, JSON.stringify(o));
    } catch (e) { /* brez shrambe igra deluje naprej */ }
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  function oznaka(edib) {
    var e = EDIB[edib];
    return '<span class="gd-tag gd-tag-' + e[1] + '">' + e[0] + '</span>';
  }

  function stVrst() { return PARI.reduce(function (n, p) { return n + p.vrste.length; }, 0); }

  /* Analitika: GA4 prek gtag, če je naložen. Brez osebnih podatkov, brez njega igra deluje enako. */
  function dogodek(ime, par) {
    try { if (typeof window.gtag === 'function') window.gtag('event', ime, par || {}); } catch (e) { /* analitika ni nujna */ }
  }

  function zacetek() {
    var r = preberiRekord(), nSibkih = Object.keys(preberiSibke()).filter(function (id) { return najdiPar(id); }).length;
    app.innerHTML =
      '<div class="gd-start">' +
      '<p class="gd-kicker">Poučna igra · ' + KROG_DOLZINA + ' primerov v krogu · ' + stVrst() + ' vrst · ~4 minute</p>' +
      '<h2 class="gd-h2">Si pripravljen na primer?</h2>' +
      '<p>V vsakem primeru dobiš eno gobo. Preglej jo z lupo: klobuk, spodnjo stran, nogo, dno noge, meso z vonjem in okolje (skupaj ' + STRIPOV + ' sledi). Nato jo imenuj. ' +
      'Dobrega detektiva ne preslepi ena lastnost, zato nagradimo, če pregledaš vsaj ' + MIN_SLEDI_ZA_BONUS + ' sledi.</p>' +
      '<ul class="gd-rules"><li><strong>2 točki</strong> za pravilno vrsto</li><li><strong>+1 točka</strong>, če si pregledal vsaj ' + MIN_SLEDI_ZA_BONUS + ' od ' + STRIPOV + ' sledi</li><li>Največ ' + NAJVEC_TOCK + ' točk</li></ul>' +
      (r ? '<p class="gd-best">Tvoj rekord v tem brskalniku: <strong>' + r + ' / ' + NAJVEC_TOCK + '</strong></p>' : '') +
      '<div id="gd-vreme-slot">' + vremeHtml() + '</div>' +
      (nSibkih ? '<p class="gd-best">Šibka področja: <strong>' + nSibkih + '</strong> ' + (nSibkih === 1 ? 'par' : nSibkih === 2 ? 'para' : 'parov') + ', pri katerih si se zmotil. V naslednjem krogu jih do ' + MAX_SIBKIH + ' ponudimo znova.</p>' : '') +
      '<div class="gd-actions"><button type="button" class="gd-btn gd-btn-main" id="gd-go">Detektivski izziv</button>' +
      '<button type="button" class="gd-btn" id="gd-learn">Način učenja</button></div>' +
      '<p class="gd-best">Učenje: brez točk, vse sledi so odprte. Izziv: točke, sledi odpiraš sam.</p>' +
      '</div>';
    document.getElementById('gd-go').addEventListener('click', function () { novaIgra(); });
    document.getElementById('gd-learn').addEventListener('click', function () { novaIgra(null, true); });
  }

  /* parIds: ponovitev samo napačnih parov; brez njih je to poln krog. */
  function novaIgra(parIds, ucenje) {
    var krog = sestaviKrog(null, parIds, preberiSibke());
    stanje = { krog: krog, i: 0, tocke: 0, nevarne: 0, odgovori: [], pogled: 'cela', sledi: {},
               najvec: krog.length * (T_PRAVILNO + T_BONUS), ponovitev: !!parIds, ucenje: !!ucenje };
    dogodek(parIds ? 'retry_wrong_answers' : ucenje ? 'learn_start' : 'game_start', { primerov: krog.length });
    primer();
  }

  function trenutni() { return stanje.krog[stanje.i]; }

  function stSledi() { return Object.keys(stanje.sledi).length; }

  /* Vrstica napredka: koliko sledi je pregledanih in koliko jih je še za bonus. */
  function sledBesedilo() {
    var n = stSledi();
    return 'Sledi ' + n + ' / ' + STRIPOV;
  }

  function bonusNamig() {
    var manjka = MIN_SLEDI_ZA_BONUS - stSledi();
    return manjka > 0 ? 'Za bonus točko še ' + manjka + (manjka === 1 ? ' sled' : ' sledi') : 'Bonus točka je tvoja';
  }

  function primer() {
    var p = trenutni(), par = najdiPar(p.par), vrsta = najdiVrsto(p.resnica);
    stanje.sledi = {}; stanje.pogled = 'cela'; stanje.zaklenjen = false;
    var gumbi = SLEDI.map(function (k) {
      return '<button type="button" class="gd-clue-btn" data-clue="' + k + '" aria-pressed="false"><span class="gd-clue-mark" aria-hidden="true"></span>' + SLEDI_IME[k] + '</button>';
    }).join('');
    var tabs = [['cela', 'Od strani'], ['spodaj', 'Od spodaj'], ['dno', 'Dno in presek']].map(function (t) {
      return '<button type="button" class="gd-tab' + (t[0] === 'cela' ? ' is-on' : '') + '" data-view="' + t[0] + '" aria-pressed="' + (t[0] === 'cela') + '">' + t[1] + '</button>';
    }).join('');
    var opcije = p.ponudba.map(function (id) {
      var v = najdiVrsto(id);
      return '<button type="button" class="gd-answer" data-id="' + id + '"><span class="gd-answer-name">' + esc(v.ime) + '</span><span class="gd-answer-lat">' + esc(v.lat) + '</span></button>';
    }).join('');
    app.innerHTML =
      '<div class="gd-hudbar">' +
      '<div class="gd-hud"><span>Primer ' + (stanje.i + 1) + ' / ' + stanje.krog.length + '</span><span id="gd-sledi">' + sledBesedilo() + '</span>' + (stanje.ucenje ? '<span>Učenje</span>' : '<span>Točke: <strong id="gd-pts">' + stanje.tocke + '</strong></span>') + '</div>' +
      '<div class="gd-progress" aria-hidden="true"><span style="width:' + (stanje.i / stanje.krog.length * 100) + '%"></span></div></div>' +
      (p.sibek ? '<p class="gd-weak">Ponovitev: pri tem paru si se že zmotil.</p>' : '') +
      '<h2 class="gd-h2">' + esc(par.naslov) + '</h2>' +
      '<p class="gd-story">' + esc(par.uvod) + '</p>' +
      '<div class="gd-stage">' +
      '<div class="gd-view"><div class="gd-tabs" role="group" aria-label="Pogled na gobo">' + tabs + '</div><div id="gd-art">' + risi(vrsta, 'cela') + '</div></div>' +
      '<div class="gd-lens"><p class="gd-lens-title">Lupa: preglej sledi <span id="gd-count" class="gd-count">0 / ' + STRIPOV + '</span></p>' +
      '<p class="gd-bonus" id="gd-bonus">' + (stanje.ucenje ? 'Vse sledi so odprte. Preberi jih in izberi vrsto.' : bonusNamig()) + '</p>' +
      '<div class="gd-clues">' + gumbi + '</div>' +
      '<ul class="gd-found" id="gd-found" aria-live="polite"><li class="gd-found-empty">Še nisi pregledal nobene sledi. Najnovejša je vedno na vrhu.</li></ul></div>' +
      '</div>' +
      '<h3 class="gd-h3">Kaj je to?</h3><div class="gd-answers" id="gd-answers">' + opcije + '</div>' +
      '<div id="gd-result" aria-live="polite"></div>';
    app.querySelectorAll('.gd-clue-btn').forEach(function (b) { b.addEventListener('click', function () { pregledaj(b.getAttribute('data-clue'), b); }); });
    app.querySelectorAll('.gd-tab').forEach(function (b) { b.addEventListener('click', function () { nastaviPogled(b.getAttribute('data-view')); }); });
    app.querySelectorAll('.gd-answer').forEach(function (b) { b.addEventListener('click', function () { odgovori(b.getAttribute('data-id')); }); });
    if (stanje.ucenje) {   // učenje: vse sledi so že odprte
      app.querySelectorAll('.gd-clue-btn').forEach(function (b) { pregledaj(b.getAttribute('data-clue'), b, true); });
      nastaviPogled('cela');
    }
  }

  function nastaviPogled(v) {
    stanje.pogled = v;
    var vrsta = najdiVrsto(trenutni().resnica);
    document.getElementById('gd-art').innerHTML = risi(vrsta, v);
    app.querySelectorAll('.gd-tab').forEach(function (b) {
      var on = b.getAttribute('data-view') === v;
      b.classList.toggle('is-on', on); b.setAttribute('aria-pressed', on);
    });
  }

  function pregledaj(k, gumb, tiho) {
    if (stanje.zaklenjen) return;
    var vrsta = najdiVrsto(trenutni().resnica);
    if (!stanje.sledi[k]) {
      stanje.sledi[k] = true;
      gumb.classList.add('is-done'); gumb.setAttribute('aria-pressed', 'true');
      var list = document.getElementById('gd-found');
      var prazen = list.querySelector('.gd-found-empty');
      if (prazen) list.removeChild(prazen);
      var li = document.createElement('li');
      li.className = 'is-new';
      li.innerHTML = '<strong>' + SLEDI_IME[k] + ':</strong> ' + esc(vrsta.sledi[k]);
      list.insertBefore(li, list.firstChild);   // najnovejša zgoraj: na telefonu je vidna brez pomikanja
      document.getElementById('gd-count').textContent = stSledi() + ' / ' + STRIPOV;
      document.getElementById('gd-sledi').textContent = sledBesedilo();
      document.getElementById('gd-bonus').textContent = bonusNamig();
      if (!tiho) dogodek('clue_opened', { sled: k });
    }
    if (!tiho) nastaviPogled(SLEDI_POGLED[k]);
  }

  /* Primerjalna kartica: ključne sledi pravilne vrste in njene dvojnice, ostale v zložljivem delu.
   * Besedilo je isto, kot ga igra pokaže med pregledom (en vir: sledi vrste). */
  function primerjavaHtml(par, res, pregledane) {
    var drugaVrsta = par.vrste.filter(function (v) { return v.id !== res.id; })[0];
    function vrstica(k) {
      var vid = pregledane[k] ? '<span class="gd-cmp-seen">pregledano</span>' : '';
      return '<div class="gd-cmp-row"><p class="gd-cmp-label">' + SLEDI_IME[k] + ' ' + vid + '</p>' +
        '<p class="gd-cmp-a"><strong>' + esc(res.ime) + ':</strong> ' + esc(res.sledi[k]) + '</p>' +
        '<p class="gd-cmp-b"><strong>' + esc(drugaVrsta.ime) + ':</strong> ' + esc(drugaVrsta.sledi[k]) + '</p></div>';
    }
    var ostale = SLEDI.filter(function (k) { return par.kljuc.indexOf(k) < 0; });
    return '<div class="gd-cmp"><h3 class="gd-h3">Ključna razlika</h3>' +
      par.kljuc.map(vrstica).join('') +
      (ostale.length ? '<details class="gd-cmp-more"><summary>Vse ostale sledi</summary>' + ostale.map(vrstica).join('') + '</details>' : '') +
      '</div>';
  }

  function povratnaSled(par, o) {
    var k = kljucneSledi(par.id, stanje.sledi);
    var imena = function (a) { return a.map(function (x) { return SLEDI_IME[x].toLowerCase(); }).join(', '); };
    if (!par.kljuc.length) return '';
    if (!k.spregledane.length) return '<p class="gd-coach gd-coach-ok">Pregledal si vse ključne sledi tega para: ' + imena(k.pregledane) + '.</p>';
    if (o.prav) return '<p class="gd-coach">Prav si ugotovil, a ' + (k.pregledane.length ? 'ključnih sledi nisi pregledal vseh' : 'nobene ključne sledi nisi pregledal') +
      '. Para ločijo: ' + imena(par.kljuc) + '. Spregledal si: ' + imena(k.spregledane) + '.</p>';
    return '<p class="gd-coach gd-coach-bad">Spregledal si ' + (k.spregledane.length > 1 ? 'ključne sledi' : 'ključno sled') + ': ' + imena(k.spregledane) + '. Ravno te dve vrsti ločijo.</p>';
  }

  function odgovori(id) {
    if (stanje.zaklenjen) return;
    stanje.zaklenjen = true;
    var p = trenutni(), n = stSledi();
    var o = oceni(p, id, n);
    if (stanje.ucenje) { o.tocke = 0; o.bonus = false; }
    stanje.tocke += o.tocke;
    zabeleziOdgovor(p.par, o.prav);
    if (o.nevarna) stanje.nevarne++;
    stanje.odgovori.push({ par: p.par, prav: o.prav, tocke: o.tocke, nevarna: o.nevarna });
    dogodek('answer_submitted', { nacin: stanje.ucenje ? 'ucenje' : 'izziv', par: p.par, pravilno: o.prav ? 1 : 0, sledi: n });
    if (!stanje.ucenje) document.getElementById('gd-pts').textContent = stanje.tocke;
    document.getElementById('gd-sledi').textContent = sledBesedilo();
    app.querySelectorAll('.gd-answer').forEach(function (b) {
      var bid = b.getAttribute('data-id');
      b.disabled = true;
      if (bid === p.resnica) b.classList.add('is-right');
      else if (bid === id) b.classList.add('is-wrong');
    });
    app.querySelectorAll('.gd-clue-btn').forEach(function (b) { b.disabled = true; });
    var par = najdiPar(p.par), res = o.resnica;
    var glava = o.prav
      ? '<p class="gd-verdict gd-verdict-ok">Pravilno! To je <strong>' + esc(res.ime) + '</strong> · ' + oznaka(res.edib) + '</p>'
      : '<p class="gd-verdict gd-verdict-bad">Ni pravilno. To je <strong>' + esc(res.ime) + '</strong> · ' + oznaka(res.edib) + '</p>';
    var tocke = stanje.ucenje ? '' : o.prav
      ? '<p class="gd-score">+' + o.tocke + ' ' + (o.tocke === 1 ? 'točka' : 'točki') + (o.bonus ? ' (z bonusom za temeljit pregled)' : ' (brez bonusa: pregledal si ' + n + ' od ' + STRIPOV + ' sledi, za bonus jih je treba ' + MIN_SLEDI_ZA_BONUS + ')') + '</p>'
      : '<p class="gd-score">0 točk</p>';
    var nevarna = o.nevarna ? '<p class="gd-danger"><strong>Nevarna napaka:</strong> če bi to pojedel, bi pojedel ' + esc(res.ime.toLowerCase()) + '. V resnici bi se tu moral ustaviti in gobo pustiti.</p>' : '';
    var dvojnica = par.vrste.filter(function (v) { return v.id !== res.id; })[0];
    var zadnji = stanje.i === stanje.krog.length - 1;
    var rez = document.getElementById('gd-result');
    rez.innerHTML =
      '<div class="gd-reveal" id="gd-reveal" tabindex="-1">' + glava + tocke + nevarna + povratnaSled(par, o) +
      '<p>' + esc(par.razlaga) + '</p>' +
      primerjavaHtml(par, res, stanje.sledi) +
      '<p class="gd-more"><a data-vrsta="' + res.id + '" href="/gobarska-napoved/baza-vrst/' + res.kat + '/?q=' + encodeURIComponent(res.q) + '">Poglej ' + esc(res.ime) + ' v bazi vrst →</a> · ' +
      '<a data-vrsta="' + dvojnica.id + '" href="/gobarska-napoved/baza-vrst/' + dvojnica.kat + '/?q=' + encodeURIComponent(dvojnica.q) + '">' + esc(dvojnica.ime) + ' →</a> · ' +
      '<a data-vrsta="dvojnice" href="/gobarska-napoved/dvojnice/">Vse nevarne dvojnice →</a></p>' +
      '<button type="button" class="gd-btn gd-btn-main gd-next" id="gd-next">' + (zadnji ? 'Poglej rezultat' : 'Naslednji primer') + '</button></div>';
    rez.querySelectorAll('a[data-vrsta]').forEach(function (a) {
      a.addEventListener('click', function () { dogodek('species_link_opened', { vrsta: a.getAttribute('data-vrsta') }); });
    });
    document.getElementById('gd-next').addEventListener('click', function () {
      if (zadnji) konec(); else { stanje.i++; primer(); window.scrollTo({ top: app.getBoundingClientRect().top + window.scrollY - 70, behavior: 'smooth' }); }
    });
    // Razlaga mora biti prva, ki jo igralec vidi: fokus na kartico, ne na gumb pod njo.
    var kartica = document.getElementById('gd-reveal');
    kartica.focus({ preventScroll: true });
    kartica.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function konec() {
    var polni = !stanje.ponovitev && !stanje.ucenje;
    var rekord = polni ? shraniRekord(stanje.tocke) : preberiRekord();
    var vrstice = stanje.odgovori.map(function (o) {
      var par = najdiPar(o.par);
      return '<li class="' + (o.prav ? 'is-ok' : 'is-bad') + '"><span>' + esc(par.naslov.replace(/^Primer: /, '')) + '</span><strong>' + (o.prav ? '+' + o.tocke : '0') + '</strong></li>';
    }).join('');
    var napacni = stanje.odgovori.filter(function (o) { return !o.prav; }).map(function (o) { return o.par; });
    var opozorilo = stanje.nevarne
      ? '<p class="gd-danger">V ' + stanje.nevarne + (stanje.nevarne === 1 ? ' primeru' : ' primerih') + ' bi pojedel neužitno ali strupeno gobo. Ravno zato gob ne nabiramo po slikah in ugibanju.</p>' : '';
    var pravilnih = stanje.odgovori.length - napacni.length;
    var besedilo = 'Gobarski detektiv: ' + stanje.tocke + ' / ' + stanje.najvec + ' (' + naziv(stanje.tocke, stanje.najvec) + '). Poskusi še ti: https://meteorec.si/igra/gobarski-detektiv/';
    dogodek('game_completed', { nacin: stanje.ucenje ? 'ucenje' : 'izziv', tocke: stanje.tocke, najvec: stanje.najvec, pravilnih: pravilnih, ponovitev: stanje.ponovitev ? 1 : 0 });
    app.innerHTML =
      '<div class="gd-end">' +
      '<p class="gd-kicker">' + (stanje.ucenje ? 'Učenje končano' : stanje.ponovitev ? 'Ponovitev napačnih primerov končana' : 'Preiskava zaključena') + '</p>' +
      (stanje.ucenje
        ? '<h2 class="gd-h2">Pravilnih odgovorov: ' + pravilnih + ' od ' + stanje.odgovori.length + '</h2>' +
          '<p class="gd-best">V učenju ni točk. Ko si pripravljen, poskusi izziv.</p>'
        : '<h2 class="gd-h2">' + esc(naziv(stanje.tocke, stanje.najvec)) + '</h2>' +
          '<p class="gd-bigscore"><strong>' + stanje.tocke + '</strong> / ' + stanje.najvec + '</p>' +
          '<p class="gd-best">Pravilnih odgovorov: ' + pravilnih + ' od ' + stanje.odgovori.length + '. Rekord v tem brskalniku: ' + rekord + ' / ' + NAJVEC_TOCK + '</p>') +
      '<ul class="gd-summary">' + vrstice + '</ul>' + opozorilo +
      '<div class="gd-final-warning" role="note"><strong>Pomembno:</strong> ta igra je samo vaja. Gob <strong>ne uživaj</strong> na podlagi igre, slike ali spletne strani. Vsako nabrano gobo mora pred jedjo pregledati usposobljen gobar (pregledovalnica gob). Če nisi povsem prepričan, gobo pusti. Ob sumu na zastrupitev takoj pokliči <a href="tel:112">112</a>.</div>' +
      '<div id="gd-vreme-slot">' + vremeHtml() + '</div>' +
      '<div class="gd-actions">' +
      (napacni.length ? '<button type="button" class="gd-btn gd-btn-main" id="gd-retry">Ponovi napačne primere (' + napacni.length + ')</button>' : '') +
      '<button type="button" class="gd-btn' + (napacni.length ? '' : ' gd-btn-main') + '" id="gd-again">' + (stanje.ucenje ? 'Izziv s točkami' : 'Nova preiskava') + '</button>' +
      (stanje.ucenje ? '' : '<button type="button" class="gd-btn" id="gd-share">Kopiraj rezultat</button>') + '</div>' +
      '<p id="gd-share-msg" class="gd-share-msg" aria-live="polite"></p>' +
      '<p class="gd-more"><a href="/gobarska-napoved/dvojnice/">Nevarne dvojnice →</a> · <a href="/gobarska-napoved/baza-vrst/">Baza vrst →</a> · <a href="/gobarska-napoved/strupene-gobe/">Strupene gobe →</a></p>' +
      '</div>';
    document.getElementById('gd-again').addEventListener('click', function () { novaIgra(); });
    var retry = document.getElementById('gd-retry');
    if (retry) retry.addEventListener('click', function () { novaIgra(napacni, stanje.ucenje); });
    var deli = document.getElementById('gd-share');
    if (deli) deli.addEventListener('click', function () {
      var msg = document.getElementById('gd-share-msg');
      function ok() { msg.textContent = 'Kopirano.'; }
      function ne() { msg.textContent = besedilo; }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(besedilo).then(ok, ne); else ne();
    });
    window.scrollTo({ top: app.getBoundingClientRect().top + window.scrollY - 70, behavior: 'smooth' });
  }

  zacetek();
  naloziVreme();
})(typeof window !== 'undefined' ? window : globalThis);
