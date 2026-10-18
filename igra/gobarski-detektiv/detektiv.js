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
   * Par = dve vrsti, ki se pogosto zamenjata. V krogu je iz vsakega para
   * natanko en primerek; kateri, se vsakič žreba.
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
    }
  ];

  var STRIPOV = SLEDI.length;
  var MIN_SLEDI_ZA_BONUS = 4;     // preglej vsaj toliko sledi, da dobiš bonus
  var T_PRAVILNO = 2;
  var T_BONUS = 1;
  var NAJVEC_TOCK = PARI.length * (T_PRAVILNO + T_BONUS);

  /* ── Model ───────────────────────────────────────────────────────────── */
  function nakljucno(rng, n) { return Math.floor(rng() * n); }

  function premesaj(arr, rng) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = nakljucno(rng, i + 1), t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  /* Krog: iz vsakega para en primerek, v premešanem vrstnem redu; ponujene so
   * obe vrsti para in ena vrsta iz drugega para (ta ni nikoli iz istega para). */
  function sestaviKrog(rng) {
    rng = rng || Math.random;
    var vrstniRed = premesaj(PARI.map(function (_, i) { return i; }), rng);
    return vrstniRed.map(function (pi) {
      var par = PARI[pi];
      var ti = nakljucno(rng, par.vrste.length);
      var resnica = par.vrste[ti];
      var drug = PARI[(pi + 1 + nakljucno(rng, PARI.length - 1)) % PARI.length];
      var vabljiva = drug.vrste[nakljucno(rng, drug.vrste.length)];
      var ponudba = premesaj(par.vrste.concat([vabljiva]), rng).map(function (v) { return v.id; });
      return { par: par.id, resnica: resnica.id, ponudba: ponudba };
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

  function naziv(tocke) {
    var d = tocke / NAJVEC_TOCK;
    if (d >= 0.9) return 'Mojster detektiv';
    if (d >= 0.65) return 'Gobji detektiv';
    if (d >= 0.35) return 'Pripravnik';
    return 'Začetnik: raje vprašaj izkušenega gobarja';
  }

  var model = {
    PARI: PARI, SLEDI: SLEDI, SLEDI_IME: SLEDI_IME, EDIB: EDIB,
    NAJVEC_TOCK: NAJVEC_TOCK, MIN_SLEDI_ZA_BONUS: MIN_SLEDI_ZA_BONUS,
    sestaviKrog: sestaviKrog, oceni: oceni, naziv: naziv,
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
    if (sp.mreza === 'bela' || sp.mreza === 'temna') {
      var kol = sp.mreza === 'bela' ? '#fffaf0' : '#5a3a22', dol = sp.mreza === 'bela' ? sp.nogaV * 0.35 : sp.nogaV * 0.8, d = '';
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
      var barva = sp.dno === 'listi' ? ({ kukmak: 'rgba(92,40,48,.55)', velika: 'rgba(30,30,30,.55)', gola: 'rgba(40,40,40,.5)' }[id] || 'rgba(120,100,80,.45)') : 'rgba(110,60,10,.5)';
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
    if (sp.mreza === 'temna') {
      var dd = '';
      for (var y = zg + 6; y < spod - 4; y += 9) dd += 'M' + (cx - botW / 2) + ',' + y + ' l' + (botW / 4) + ',6 l' + (botW / 4) + ',-6 l' + (botW / 4) + ',6 l' + (botW / 4) + ',-6 ';
      g += el('path', { d: dd, stroke: '#5a3a22', 'stroke-width': 1.7, fill: 'none', opacity: 0.9 });
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

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  function oznaka(edib) {
    var e = EDIB[edib];
    return '<span class="gd-tag gd-tag-' + e[1] + '">' + e[0] + '</span>';
  }

  function zacetek() {
    var r = preberiRekord();
    app.innerHTML =
      '<div class="gd-start">' +
      '<p class="gd-kicker">Poučna igra · ' + PARI.length + ' primerov · ~4 minute</p>' +
      '<h2 class="gd-h2">Si pripravljen na primer?</h2>' +
      '<p>V vsakem primeru dobiš eno gobo. Preglej jo z lupo: klobuk, spodnjo stran, nogo, dno in meso. Nato jo imenuj. ' +
      'Dobra detektiva ne preslepi ena lastnost, zato nagradimo, če pregledaš vsaj ' + MIN_SLEDI_ZA_BONUS + ' sledi.</p>' +
      '<ul class="gd-rules"><li><strong>2 točki</strong> za pravilno vrsto</li><li><strong>+1 točka</strong>, če si pregledal vsaj ' + MIN_SLEDI_ZA_BONUS + ' od ' + STRIPOV + ' sledi</li><li>Največ ' + NAJVEC_TOCK + ' točk</li></ul>' +
      (r ? '<p class="gd-best">Tvoj rekord v tem brskalniku: <strong>' + r + ' / ' + NAJVEC_TOCK + '</strong></p>' : '') +
      '<button type="button" class="gd-btn gd-btn-main" id="gd-go">Začni preiskavo</button>' +
      '</div>';
    document.getElementById('gd-go').addEventListener('click', novaIgra);
  }

  function novaIgra() {
    stanje = { krog: sestaviKrog(), i: 0, tocke: 0, nevarne: 0, odgovori: [], pogled: 'cela', sledi: {} };
    primer();
  }

  function trenutni() { return stanje.krog[stanje.i]; }

  function primer() {
    var p = trenutni(), par = najdiPar(p.par), vrsta = najdiVrsto(p.resnica);
    stanje.sledi = {}; stanje.pogled = 'cela'; stanje.zaklenjen = false;
    var gumbi = SLEDI.map(function (k) {
      return '<button type="button" class="gd-clue-btn" data-clue="' + k + '" aria-pressed="false">' + SLEDI_IME[k] + '</button>';
    }).join('');
    var tabs = [['cela', 'Od strani'], ['spodaj', 'Od spodaj'], ['dno', 'Dno in presek']].map(function (t) {
      return '<button type="button" class="gd-tab' + (t[0] === 'cela' ? ' is-on' : '') + '" data-view="' + t[0] + '" aria-pressed="' + (t[0] === 'cela') + '">' + t[1] + '</button>';
    }).join('');
    var opcije = p.ponudba.map(function (id) {
      var v = najdiVrsto(id);
      return '<button type="button" class="gd-answer" data-id="' + id + '"><span class="gd-answer-name">' + esc(v.ime) + '</span><span class="gd-answer-lat">' + esc(v.lat) + '</span></button>';
    }).join('');
    app.innerHTML =
      '<div class="gd-hud"><span>Primer ' + (stanje.i + 1) + ' / ' + stanje.krog.length + '</span><span>Točke: <strong id="gd-pts">' + stanje.tocke + '</strong></span></div>' +
      '<div class="gd-progress" aria-hidden="true"><span style="width:' + (stanje.i / stanje.krog.length * 100) + '%"></span></div>' +
      '<h2 class="gd-h2">' + esc(par.naslov) + '</h2>' +
      '<p class="gd-story">' + esc(par.uvod) + '</p>' +
      '<div class="gd-stage">' +
      '<div class="gd-view"><div class="gd-tabs" role="group" aria-label="Pogled na gobo">' + tabs + '</div><div id="gd-art">' + risi(vrsta, 'cela') + '</div></div>' +
      '<div class="gd-lens"><p class="gd-lens-title">Lupa: preglej sledi <span id="gd-count" class="gd-count">0 / ' + STRIPOV + '</span></p>' +
      '<div class="gd-clues">' + gumbi + '</div>' +
      '<ul class="gd-found" id="gd-found" aria-live="polite"><li class="gd-found-empty">Še nisi pregledal nobene sledi.</li></ul></div>' +
      '</div>' +
      '<h3 class="gd-h3">Kaj je to?</h3><div class="gd-answers" id="gd-answers">' + opcije + '</div>' +
      '<div id="gd-result" aria-live="polite"></div>';
    app.querySelectorAll('.gd-clue-btn').forEach(function (b) { b.addEventListener('click', function () { pregledaj(b.getAttribute('data-clue'), b); }); });
    app.querySelectorAll('.gd-tab').forEach(function (b) { b.addEventListener('click', function () { nastaviPogled(b.getAttribute('data-view')); }); });
    app.querySelectorAll('.gd-answer').forEach(function (b) { b.addEventListener('click', function () { odgovori(b.getAttribute('data-id')); }); });
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

  function pregledaj(k, gumb) {
    if (stanje.zaklenjen) return;
    var vrsta = najdiVrsto(trenutni().resnica);
    if (!stanje.sledi[k]) {
      stanje.sledi[k] = true;
      gumb.classList.add('is-done'); gumb.setAttribute('aria-pressed', 'true');
      var list = document.getElementById('gd-found');
      var prazen = list.querySelector('.gd-found-empty');
      if (prazen) list.removeChild(prazen);
      var li = document.createElement('li');
      li.innerHTML = '<strong>' + SLEDI_IME[k] + ':</strong> ' + esc(vrsta.sledi[k]);
      list.appendChild(li);
      document.getElementById('gd-count').textContent = Object.keys(stanje.sledi).length + ' / ' + STRIPOV;
    }
    nastaviPogled(SLEDI_POGLED[k]);
  }

  function odgovori(id) {
    if (stanje.zaklenjen) return;
    stanje.zaklenjen = true;
    var p = trenutni(), n = Object.keys(stanje.sledi).length;
    var o = oceni(p, id, n);
    stanje.tocke += o.tocke;
    if (o.nevarna) stanje.nevarne++;
    stanje.odgovori.push({ par: p.par, prav: o.prav, tocke: o.tocke, nevarna: o.nevarna });
    document.getElementById('gd-pts').textContent = stanje.tocke;
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
    var tocke = o.prav
      ? '<p class="gd-score">+' + o.tocke + ' ' + (o.tocke === 1 ? 'točka' : 'točki') + (o.bonus ? ' (z bonusom za temeljit pregled)' : ' (brez bonusa: pregledal si ' + n + ' od ' + STRIPOV + ' sledi, za bonus jih je treba ' + MIN_SLEDI_ZA_BONUS + ')') + '</p>'
      : '<p class="gd-score">0 točk</p>';
    var nevarna = o.nevarna ? '<p class="gd-danger"><strong>Nevarna napaka:</strong> če bi to pojedel, bi pojedel ' + esc(res.ime.toLowerCase()) + '. V resnici bi se tu moral ustaviti in gobo pustiti.</p>' : '';
    var zadnji = stanje.i === stanje.krog.length - 1;
    document.getElementById('gd-result').innerHTML =
      '<div class="gd-reveal">' + glava + tocke + nevarna +
      '<p>' + esc(par.razlaga) + '</p>' +
      '<p class="gd-more"><a href="/gobarska-napoved/baza-vrst/' + res.kat + '/?q=' + encodeURIComponent(res.q) + '">Poglej ' + esc(res.ime) + ' v bazi vrst →</a></p>' +
      '<button type="button" class="gd-btn gd-btn-main" id="gd-next">' + (zadnji ? 'Poglej rezultat' : 'Naslednji primer') + '</button></div>';
    var next = document.getElementById('gd-next');
    next.addEventListener('click', function () { if (zadnji) konec(); else { stanje.i++; primer(); window.scrollTo({ top: app.getBoundingClientRect().top + window.scrollY - 70, behavior: 'smooth' }); } });
    next.focus({ preventScroll: false });
  }

  function konec() {
    var rekord = shraniRekord(stanje.tocke);
    var vrstice = stanje.odgovori.map(function (o) {
      var par = najdiPar(o.par);
      return '<li class="' + (o.prav ? 'is-ok' : 'is-bad') + '"><span>' + esc(par.naslov.replace(/^Primer: /, '')) + '</span><strong>' + (o.prav ? '+' + o.tocke : '0') + '</strong></li>';
    }).join('');
    var opozorilo = stanje.nevarne
      ? '<p class="gd-danger">V ' + stanje.nevarne + (stanje.nevarne === 1 ? ' primeru' : ' primerih') + ' bi pojedel neužitno ali strupeno gobo. Ravno zato gob ne nabiramo po slikah in ugibanju.</p>' : '';
    var besedilo = 'Gobarski detektiv: ' + stanje.tocke + ' / ' + NAJVEC_TOCK + ' (' + naziv(stanje.tocke) + '). Poskusi še ti: https://meteorec.si/igra/gobarski-detektiv/';
    app.innerHTML =
      '<div class="gd-end">' +
      '<p class="gd-kicker">Preiskava zaključena</p>' +
      '<h2 class="gd-h2">' + esc(naziv(stanje.tocke)) + '</h2>' +
      '<p class="gd-bigscore"><strong>' + stanje.tocke + '</strong> / ' + NAJVEC_TOCK + '</p>' +
      '<p class="gd-best">Rekord v tem brskalniku: ' + rekord + ' / ' + NAJVEC_TOCK + '</p>' +
      '<ul class="gd-summary">' + vrstice + '</ul>' + opozorilo +
      '<div class="gd-final-warning" role="note"><strong>Pomembno:</strong> ta igra je samo vaja. Gob <strong>ne uživaj</strong> na podlagi igre, slike ali spletne strani. Vsako nabrano gobo mora pred jedjo pregledati usposobljen gobar (pregledovalnica gob). Če nisi povsem prepričan, gobo pusti. Ob sumu na zastrupitev takoj pokliči <a href="tel:112">112</a>.</div>' +
      '<div class="gd-actions"><button type="button" class="gd-btn gd-btn-main" id="gd-again">Nova preiskava</button>' +
      '<button type="button" class="gd-btn" id="gd-share">Kopiraj rezultat</button></div>' +
      '<p id="gd-share-msg" class="gd-share-msg" aria-live="polite"></p>' +
      '<p class="gd-more"><a href="/gobarska-napoved/dvojnice/">Nevarne dvojnice →</a> · <a href="/gobarska-napoved/baza-vrst/">Baza vrst →</a> · <a href="/gobarska-napoved/strupene-gobe/">Strupene gobe →</a></p>' +
      '</div>';
    document.getElementById('gd-again').addEventListener('click', novaIgra);
    document.getElementById('gd-share').addEventListener('click', function () {
      var msg = document.getElementById('gd-share-msg');
      function ok() { msg.textContent = 'Kopirano.'; }
      function ne() { msg.textContent = besedilo; }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(besedilo).then(ok, ne); else ne();
    });
    window.scrollTo({ top: app.getBoundingClientRect().top + window.scrollY - 70, behavior: 'smooth' });
  }

  zacetek();
})(typeof window !== 'undefined' ? window : globalThis);
