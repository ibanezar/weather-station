// ═══════════════════════════════════════════════════════════
// Cloudflare Worker — IREICA1 Weather Proxy
// ═══════════════════════════════════════════════════════════

const STATION = "IREICA1";
const WU_KEY  = "619a8bb3ba4d42069a8bb3ba4d02061f";
const WU_BASE = "https://api.weather.com/v2/pws/";
const CURRENT_URL = WU_BASE+"observations/current?stationId="+STATION+"&format=json&units=m&apiKey="+WU_KEY+"&numericPrecision=decimal";
const HOURLY_URL  = WU_BASE+"observations/hourly/7day?stationId="+STATION+"&format=json&units=m&apiKey="+WU_KEY+"&numericPrecision=decimal";

const ANTHROPIC_KEY = "REPLACE_WITH_ANTHROPIC_API_KEY";
// GEMINI_KEY: add as Secret in Cloudflare Workers dashboard → Settings → Variables → Secret variables

// Google Maps Weather API key — pridobi na console.cloud.google.com → Weather API
const GOOGLE_WEATHER_KEY = "REPLACE_WITH_GOOGLE_MAPS_API_KEY";

// Kompaktna baza 51 vrst (iz species_rules.yaml) — kontekst za AI prepoznavo fotografij.
const GOBE_SPECIES_DB = [{"id":"boletus_edulis","sl":"Jesenski goban (Jurček)","lat":"Boletus edulis","ed":"Užitna","dbl":"Žolčasti goban (Tylopilus felleus) – neužiten; loči se po izrazito grenkem okusu in rožnati trosovnici."},{"id":"boletus_reticulatus","sl":"Poletni goban","lat":"Boletus reticulatus","ed":"Užitna","dbl":"Žolčasti goban (Tylopilus felleus) – neužiten; loči se po izrazito grenkem okusu in mrežici na betu."},{"id":"boletus_pinophilus","sl":"Borov goban","lat":"Boletus pinophilus","ed":"Užitna","dbl":"Žolčasti goban (Tylopilus felleus) – neužiten, grenak okus. Druge vrste užitnih gobanov."},{"id":"boletus_aereus","sl":"Črni goban","lat":"Boletus aereus","ed":"Užitna","dbl":"Ni nevarnih neposrednih dvojnic zaradi zelo temnega klobuka in čvrstega, nespremenljivega belega mesa."},{"id":"neoboletus_erythropus","sl":"Žametasti goban","lat":"Neoboletus erythropus","ed":"Pogojno užitna","dbl":"Vražji goban (Rubroboletus satanas) – strupen; loči se po zelo svetlem (sivem) klobuku in rasti na apnencu."},{"id":"imleria_badia","sl":"Kostanjevka","lat":"Imleria badia","ed":"Užitna","dbl":"Žolčasti goban (Tylopilus felleus) – neužiten, grenak. Kostanjevka močno pomodri na cevkatem delu ob pritisku."},{"id":"xerocomellus_chrysenteron","sl":"Rdečebetka","lat":"Xerocomellus chrysenteron","ed":"Užitna","dbl":"Sorodni polstenci (npr. rdečeči polstenec), ki so prav tako večinoma užitni."},{"id":"suillus_grevillei","sl":"Macesnova lupljivka","lat":"Suillus grevillei","ed":"Užitna","dbl":"Druge maslenke in lupljivke pod iglavci, ki pa so vse užitne in nekatere prav tako sluzaste."},{"id":"rubroboletus_satanas","sl":"Vražji goban","lat":"Rubroboletus satanas","ed":"Strupena","dbl":"Žametasti goban (Neoboletus erythropus) – užiten po kuhanju (ima temno rjav klobuk, vražji pa siv/bel)."},{"id":"caloboletus_calopus","sl":"Leponogi postavnež","lat":"Caloboletus calopus","ed":"Neužitna","dbl":"Grenki goban (Caloboletus radicans) – neužiten in grenak. Leponogi ima izrazito rdeč spodnji del beta."},{"id":"cantharellus_cibarius","sl":"Navadna lisička","lat":"Cantharellus cibarius","ed":"Užitna","dbl":"Oljkov livkar (Omphalotus olearius) – strupen; raste v šopih na lesu (predvsem na Primorskem pod oljkami/hrasti)."},{"id":"craterellus_tubaeformis","sl":"Lijasta lisička","lat":"Craterellus tubaeformis","ed":"Užitna","dbl":"Zlatorumena lisička (Cantharellus lutescens) – prav tako užitna, nima tako izrazitih letvic."},{"id":"craterellus_cornucopioides","sl":"Črna trobenta","lat":"Craterellus cornucopioides","ed":"Užitna","dbl":"Ni nevarnih dvojnic zaradi specifične trobentaste oblike in povsem črne/sive barve."},{"id":"hydnum_repandum","sl":"Rumeni ježek","lat":"Hydnum repandum","ed":"Užitna","dbl":"Rdečerjavi ježek (Hydnum rufescens) – manjši, bolj oranžen, prav tako užiten (odstranijo se bodičke)."},{"id":"russula_cyanoxantha","sl":"Modrikasta golobica","lat":"Russula cyanoxantha","ed":"Užitna","dbl":"Zelena mušnica (Amanita phalloides) – smrtno strupena; mušnica ima obroček na betu in lupino v dnu beta, golobica ne."},{"id":"russula_vesca","sl":"Užitna golobica","lat":"Russula vesca","ed":"Užitna","dbl":"Druge rdeče golobice – nekatere so pekoče in neužitne/strupene (pripravite test s konico jezika)."},{"id":"russula_virescens","sl":"Zelena golobica","lat":"Russula virescens","ed":"Užitna","dbl":"Zelena mušnica (Amanita phalloides) – smrtno strupena! Mušnica ima kožnat obroček in lupino (vrečko) v dnu beta."},{"id":"russula_emetica","sl":"Bljuvna golobica","lat":"Russula emetica","ed":"Strupena","dbl":"Užitne rdeče golobice – bljuvna je izjemno pekoča in povzroča hude prebavne motnje."},{"id":"lactarius_deliciosus","sl":"Užitna sirovka","lat":"Lactarius deliciosus","ed":"Užitna","dbl":"Navadna tura (Lactarius torminosus) – strupena; raste pod brezami in izloča bel, zelo pekoč mleček."},{"id":"lactarius_deterrimus","sl":"Smrekova sirovka","lat":"Lactarius deterrimus","ed":"Užitna","dbl":"Druge sirovke z oranžnim mlečkom – vse so užitne (smrekova hitro pozeleni na mestih poškodb)."},{"id":"lactifluus_piperatus","sl":"Kravja mlečnica","lat":"Lactifluus piperatus","ed":"Pogojno užitna","dbl":"Polsteni mlečnik (Lactifluus vellereus) – neužiten; ima žametno dlako na klobuku in bolj razmaknjene lističe."},{"id":"lactifluus_vellereus","sl":"Polsteni mlečnik","lat":"Lactifluus vellereus","ed":"Neužitna","dbl":"Kravja mlečnica (Lactifluus piperatus) – pogojno užitna; ima popolnoma gladko kožico klobuka."},{"id":"amanita_caesarea","sl":"Knežja mušnica (Karželj)","lat":"Amanita caesarea","ed":"ZAŠČITENA","dbl":"Rdeča mušnica (Amanita muscaria) – strupena; rdeča mušnica ima bele lističe in bet ter luskice, karželj pa je živo rumen."},{"id":"amanita_rubescens","sl":"Rdečkasta mušnica (Bisernica)","lat":"Amanita rubescens","ed":"Pogojno užitna","dbl":"Panterjeva mušnica (Amanita pantherina) – zelo strupena! Bisernica vedno rdeči na zraku/poškodbah in ima narebren obroček."},{"id":"amanita_muscaria","sl":"Rdeča mušnica","lat":"Amanita muscaria","ed":"Strupena","dbl":"Knežja mušnica (Amanita caesarea) – užitna/zaščitena; karželj ima rumene lističe, bet in obroček."},{"id":"amanita_phalloides","sl":"Zelena mušnica","lat":"Amanita phalloides","ed":"Smrtno strupena","dbl":"Zelena golobica (Russula virescens) – užitna; golobica nima obročka na betu in nima lupine (vrečke) v dnu beta."},{"id":"amanita_pantherina","sl":"Panterjeva mušnica","lat":"Amanita pantherina","ed":"Zelo strupena","dbl":"Rdečkasta mušnica (Amanita rubescens) – užitna; rdečkasta rdeči ob poškodbi, panterjeva pa ne spreminja barve mesa."},{"id":"amanita_virosa","sl":"Koničasta mušnica","lat":"Amanita virosa","ed":"Smrtno strupena","dbl":"Poljski kukmaki (Agaricus campestris) – užitni; kukmaki nimajo lupine v dnu beta, njihovi lističi pa hitro pordečijo ali rjavijo."},{"id":"macrolepiota_procera","sl":"Orjaški dežnik (Marela)","lat":"Macrolepiota procera","ed":"Užitna","dbl":"Strupena rdečeča dežnica (Chlorophyllum brunneum) – strupena; meso ob poškodbi močno pordeči, bet nima marogastega vzorca."},{"id":"agaricus_campestris","sl":"Poljski kukmak","lat":"Agaricus campestris","ed":"Užitna","dbl":"Karbolni kukmak (Agaricus xanthodermus) – strupen; v dnu beta ob prerezu močno porumeni in smrdi po črnilu."},{"id":"agaricus_xanthodermus","sl":"Karbolni kukmak","lat":"Agaricus xanthodermus","ed":"Strupena","dbl":"Poljski kukmak (Agaricus campestris) – užiten; poljski kukmak prijetno diši po mandljih in v dnu beta ne rumeni."},{"id":"cortinarius_caperatus","sl":"Pšenična koprenka","lat":"Cortinarius caperatus","ed":"Užitna","dbl":"Sorodne strupene koprenke – pšenična se loči po narebranem svetlem klobuku z značilnim srebrnkastim prahom."},{"id":"armillaria_mellea","sl":"Sivorumena mraznica (Štorovka)","lat":"Armillaria mellea","ed":"Pogojno užitna","dbl":"Navadna žveplenjača (Hypholoma fasciculare) – strupena; nima obročka na betu, klobuk je žvepleno rumen in zelo grenak."},{"id":"flammulina_velutipes","sl":"Zimska panjevka","lat":"Flammulina velutipes","ed":"Užitna","dbl":"Strupena galerina (Galerina marginata) – smrtno strupena; galerina raste na iglavcih, ima obroček in nima žametnega beta."},{"id":"pleurotus_ostreatus","sl":"Bukov ostrigar","lat":"Pleurotus ostreatus","ed":"Užitna","dbl":"V času njegove rasti (pozno jeseni in pozimi) ni nevarnih podobnih gob na lesu."},{"id":"hypholoma_fasciculare","sl":"Navadna žveplenjača","lat":"Hypholoma fasciculare","ed":"Strupena","dbl":"Sivorumena mraznica (Armillaria mellea) – užitna po kuhanju; mraznica ima nežen obroček, luskice in bel trosni prah."},{"id":"laccaria_amethystina","sl":"Vijoličasta bledivka","lat":"Laccaria amethystina","ed":"Užitna","dbl":"Vijoličasta čeladica (Mycena pura) – strupena; loči se po izrazitem vonju po redkvici in tanjših, gostejših lističih."},{"id":"morchella_esculenta","sl":"Užitni smrček (Mavrah)","lat":"Morchella esculenta","ed":"Užitna","dbl":"Pomladanski hrček (Gyromitra esculenta) – zelo strupen; hrček ima možgansko naguban klobuk in ni votel."},{"id":"morchella_elata","sl":"Koničasti smrček","lat":"Morchella elata","ed":"Užitna","dbl":"Pomladanski hrček (Gyromitra esculenta) – zelo strupen; hrček ima klobuk podoben možganom in nima pravilnih navpičnih jamic."},{"id":"gyromitra_esculenta","sl":"Pomladanski hrček","lat":"Gyromitra esculenta","ed":"Zelo strupena","dbl":"Užitni smrček (Morchella esculenta) – užiten; smrček ima satast klobuk (kot panj) in je v celoti votel."},{"id":"gyromitra_infula","sl":"Jesenski hrček","lat":"Gyromitra infula","ed":"Strupena","dbl":"Rogati hrček (Gyromitra gigas) ali drugi jesenski hrčki, ki so vsi sumljivi in potencialno nevarni."},{"id":"paxillus_involutus","sl":"Navadna podvihanka","lat":"Paxillus involutus","ed":"Smrtno strupena","dbl":"Velike rjave livke – podvihanka se prepozna po močno spodvihanem žametnem robu klobuka in rjavenju ob dotiku."},{"id":"calvatia_gigantea","sl":"Orjaška plešivka","lat":"Calvatia gigantea","ed":"Užitna","dbl":"Zaradi izjemne velikosti (lahko kot velika bela žoga) in kroglaste oblike je praktično nezamenljiva."},{"id":"coprinus_comatus","sl":"Velika tintnica","lat":"Coprinus comatus","ed":"Užitna","dbl":"Gola tintnica (Coprinopsis atramentaria) – pogojno strupena z alkoholom; nima luskastega in visokega valjastega klobuka."},{"id":"auricularia_auricula_judae","sl":"Bezgova uhljevka","lat":"Auricularia auricula-judae","ed":"Užitna","dbl":"Vijoličasta zvedavka (Auricularia mesenterica) – neužitna; nima oblike ušesa in je bolj usnjata."},{"id":"lycoperdon_perlatum","sl":"Betičasta prašnica","lat":"Lycoperdon perlatum","ed":"Užitna","dbl":"Navadna smrdljivka (Scleroderma citrinum) – strupena; zelo trda, lupina je debela, usnjata, meso znotraj hitro počrni."},{"id":"gomphidius_glutinosus","sl":"Veliki slinar","lat":"Gomphidius glutinosus","ed":"Užitna","dbl":"Bakerasti polžar (Chroogomphus rutilus) – užiten; nima prozorne debele sluzi in je ves rdečkasto-bakerne barve."},{"id":"leccinum_scabrum","sl":"Brezov ded","lat":"Leccinum scabrum","ed":"Užitna","dbl":"Žolčasti goban (Tylopilus felleus) – neužiten, izredno grenak; loči se po rožnati trosovnici (cevke pod klobukom)."},{"id":"leccinum_versipelle","sl":"Brezov turek","lat":"Leccinum versipelle","ed":"Užitna","dbl":"Trepetlikov turek (Leccinum aurantiacum) – prav tako užiten in odličen, raste pod trepetlikami/topoli."},{"id":"leccinum_aurantiacum","sl":"Hrastov turek","lat":"Leccinum aurantiacum","ed":"Užitna","dbl":"Druge vrste užitnih turkov in dedov – vsi so varni in odlični za hrano."},{"id":"trametes_versicolor","sl":"Pisana ploskocevka","lat":"Trametes versicolor","ed":"Neužitna","dbl":"Bližnje sorodne ploskocevke – nobena ni strupena, so pa vse preveč lesene za neposredno prehrano."}];

const EW_APP_FALLBACK = "A7E5CAF73FCC9BF859CDE788D69A1C91";
const EW_API_FALLBACK = "0bd213c8-8e54-4bf6-b6da-127a1c605034";
const EW_MAC = "BC:DD:C2:42:8D:56";

// Sosednja postaja IREICA7 v Varpolju (~1,6 km jugozahodno), last prijatelja,
// ki jo javno objavlja kot JSON. Njegov strežnik se osveži približno vsakih
// 5 minut — pogostejše poizvedovanje ne vrne ničesar novega.
const VARPOLJE_URL = "https://varpolje.si/station.json";

// Bbox Zgornje Savinjske doline za MeteoHmeljar zemljevid — isto območje kot
// fetch_hydrants.py (Solčava–Luče–Ljubno–Rečica–Mozirje–Nazarje–Gornji Grad).
// esriGeometryEnvelope pričakuje xmin,ymin,xmax,ymax (lon,lat,lon,lat).
const RABA_BBOX = "14.60,46.26,15.05,46.45";

const ALLOWED_ORIGINS = [
  "https://ibanezar.github.io",
  "https://meteorec.si",
  "https://www.meteorec.si",
  "http://localhost",
  "http://127.0.0.1",
];

const ALLOWED_REFERER_HOSTS = ["facebook.com", "fb.com", "fb.me", "instagram.com", "fbsbx.com"];

function isAllowedOrigin(request) {
  const origin  = request.headers.get("Origin")  || "";
  const referer = request.headers.get("Referer") || "";
  if (!origin && !referer) return true;
  if (ALLOWED_ORIGINS.some(o => origin.startsWith(o) || referer.startsWith(o))) return true;
  // Facebook/Instagram in-app browsers strip Origin and route via shim domains
  // (e.g. lm.facebook.com). Allow their referer hosts — this is public data.
  try {
    const h = new URL(referer).hostname;
    if (ALLOWED_REFERER_HOSTS.some(d => h === d || h.endsWith("." + d))) return true;
  } catch (_) {}
  return false;
}

const CORS_ALLOWED = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Authorization",
};
const CORS_DENY = { "Access-Control-Allow-Origin": "null" };

// ── ARSO official text forecast ────────────────────────────
// Tries several known ARSO endpoints; uses the first that yields prose.
const ARSO_TEXT_ENDPOINTS = [
  "https://vreme.arso.gov.si/api/1.0/nonlocation/",
  "https://meteo.arso.gov.si/uploads/probase/www/fproduct/text/sl/fcast_SLOVENIA_latest.xml",
  "https://meteo.arso.gov.si/uploads/probase/www/fproduct/text/sl/fcast_SI_SAVINJSKA_latest.xml",
];

// Sekcije, ki NISO napoved in ne smejo nikoli v napovedno kartico.
// "OPOZORILO" (oz. warning_si) je isto besedilo, kot že teče v traku na vrhu
// strani — če pride sem, kartica "Napoved za Rečico" podvaja opozorilo.
const ARSO_SKIP_SECTIONS = /^(OPOZORILO|WARNING)/i;

const _arsoClean = s => (s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const _arsoIsProse = s => s.length > 45 && /\s/.test(s) && /[a-zčšžćđA-ZČŠŽ]/.test(s);

// `para` je pri ARSO enkrat niz, enkrat seznam nizov, enkrat seznam objektov
// z lastnim `para` (glej fcast_si_hint) — vse zvedi na seznam čistih nizov.
function _arsoParas(para) {
  const out = [];
  const take = v => {
    if (typeof v === "string") { const s = _arsoClean(v); if (s) out.push(s); }
    else if (Array.isArray(v)) v.forEach(take);
    else if (v && typeof v === "object" && v.para !== undefined) take(v.para);
  };
  take(para);
  return out;
}

// Namensko branje fcast_si_text.section[] iz /api/1.0/nonlocation/.
// Sekcije z nepraznim `title` začnejo novo skupino, sekcije s praznim `title`
// so nadaljevanje prejšnje — tako je "NAPOVED ZA SLOVENIJO" sestavljena iz
// section[0] (nocoj) in section[1] (jutri).
function _arsoFcastSections(parsed) {
  const sections = parsed?.fcast_si_text?.section;
  if (!Array.isArray(sections)) return {};
  const groups = {};
  let current = null;
  for (const sec of sections) {
    const title = _arsoClean(sec?.title).toUpperCase();
    if (title) { current = title; if (!groups[current]) groups[current] = []; }
    if (!current) continue;
    groups[current].push(..._arsoParas(sec?.para).filter(_arsoIsProse));
  }
  for (const k of Object.keys(groups)) if (!groups[k].length) delete groups[k];
  return groups;
}

function _arsoExtractProse(body, ct) {
  const proses = [];
  const push = s => {
    s = _arsoClean(s);
    if (_arsoIsProse(s)) proses.push(s);
  };
  let parsed = null;
  if (/json/i.test(ct) || /^\s*[\{\[]/.test(body)) {
    try { parsed = JSON.parse(body); } catch (_) {}
  }
  if (parsed) {
    // Varovalka: warning_si stoji v odgovoru PRED fcast_si_text, zato bi ga
    // slepi obhod vedno pobral prvega. Napovedi ne sme izriniti opozorilo.
    const walk = (v, key) => {
      if (key === "warning_si") return;
      if (typeof v === "string") push(v);
      else if (Array.isArray(v)) v.forEach(x => walk(x, key));
      else if (v && typeof v === "object") {
        for (const [k, x] of Object.entries(v)) {
          if (k === "title" && ARSO_SKIP_SECTIONS.test(_arsoClean(x))) return;
        }
        for (const [k, x] of Object.entries(v)) walk(x, k);
      }
    };
    walk(parsed, null);
  } else {
    body.replace(/<[^>]+>/g, "\n").split(/\n+/).forEach(push);
  }
  return proses;
}

async function _arsoFetch(url) {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), 6000);
  try {
    const r = await fetch(url, {
      signal: ctrl.signal,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; Meteorec/1.0)",
        "Accept": "application/json,text/xml,*/*",
        "Referer": "https://meteo.arso.gov.si/",
      },
    });
    return r;
  } finally { clearTimeout(to); }
}

const ARSO_TEXT_LIMIT = 600;

function _arsoTrim(t) {
  return t.length > ARSO_TEXT_LIMIT ? t.slice(0, ARSO_TEXT_LIMIT - 20).replace(/\s+\S*$/, "") + "…" : t;
}

async function fetchArsoText() {
  for (const url of ARSO_TEXT_ENDPOINTS) {
    try {
      const r = await _arsoFetch(url);
      if (!r.ok) continue;
      const ct = r.headers.get("content-type") || "";
      const body = await r.text();

      // 1) Strukturirana pot: iz JSON vira preberi točno napovedne sekcije.
      if (/json/i.test(ct) || /^\s*[\{\[]/.test(body)) {
        let parsed = null;
        try { parsed = JSON.parse(body); } catch (_) {}
        const groups = _arsoFcastSections(parsed);
        const fcast = groups["NAPOVED ZA SLOVENIJO"] || [];
        if (fcast.length) {
          let t = fcast.join(" ");
          // Obete pripni le, če se skupaj še prilegajo — sicer raje sama napoved.
          const outlook = groups["OBETI"] || [];
          if (outlook.length) {
            const withOutlook = t + " " + outlook.join(" ");
            if (withOutlook.length <= ARSO_TEXT_LIMIT) t = withOutlook;
          }
          return { text: _arsoTrim(t), title: "Napoved za Slovenijo", source: "ARSO", url };
        }
      }

      // 2) Rezerva za XML vire brez sekcijske sheme.
      const proses = _arsoExtractProse(body, ct);
      if (proses.length) {
        return { text: _arsoTrim(proses.slice(0, 2).join(" ")), title: "ARSO", source: "ARSO", url };
      }
    } catch (_) {}
  }
  return { text: null, title: null, source: null, url: null };
}

// Standard ARSO warning descriptions per type + severity
const WARNING_TEXTS = {
  WarningTS: {
    yellow: { desc: "Možne so krajevne nevihte.", more: "Lokalno možni kratki nalivi, piš vetra in udari strel. Hitro lahko narastejo hudourniški vodotoki." },
    orange: { desc: "Nevihte bodo ponekod z obilnimi padavinami, točo in nevarnimi sunki vetra.", more: "Pričakujte možnost škode. Odmakni se od dreves in daljnovodov." },
    red:    { desc: "Hude nevihte z nevarno točo, izjemno obilnimi padavinami in nevarnimi sunki vetra.", more: "Ostani v zavetju. Izogibaj se poplavljenim cestam in hudourniškim vodam." },
  },
  WarningWind: {
    yellow: { desc: "Pričakovati je močnejše sunke vetra.", more: "Zavarujte predmete na prostem." },
    orange: { desc: "Sunki vetra bodo nevarno močni.", more: "Možna je škoda na objektih. Ne hodite v gozd." },
    red:    { desc: "Izjemno nevarni sunki vetra z nevarnostjo večje škode.", more: "Ostani v zavetju. Nevarnost rušenja objektov." },
  },
  WarningRA: {
    yellow: { desc: "Možni so krajevni obilnejši nalivi.", more: "Bodite pozorni na naraščanje hudourniških voda." },
    orange: { desc: "Obilne padavine z nevarnostjo poplav.", more: "Izogibaj se nižinam ob vodotokih." },
    red:    { desc: "Izjemno obilne padavine z nevarnostjo hudih poplav.", more: "Zapustite območja v bližini voda. Sledite navodilom služb." },
  },
  WarningSN: {
    yellow: { desc: "Možno sneženje.", more: "Na cestah je možna povečana nevarnost." },
    orange: { desc: "Obilno sneženje z nevarnostjo na cestah.", more: "Potujte samo, če je nujno. Prilagodite hitrost." },
    red:    { desc: "Izjemno obilno sneženje.", more: "Ostani doma. Ceste so neprehodne." },
  },
  WarningFG: {
    yellow: { desc: "Možna gosta megla z vidljivostjo pod 200 m.", more: "Prilagodite hitrost vožnje." },
    orange: { desc: "Gosta megla z vidljivostjo pod 50 m.", more: "Izogibajte se vožnji. Prižgite meglenke." },
    red:    { desc: "Izjemno gosta megla.", more: "Ne vozite, če ni nujno potrebno." },
  },
  WarningIC: {
    yellow: { desc: "Možna poledica ali žled.", more: "Previdno na cestah in hodnikih. Preverite cestne razmere." },
    orange: { desc: "Nevarnost poledice ali žleda.", more: "Možna škoda na drevju in infrastrukturi." },
    red:    { desc: "Nevarni žledeni pojavi.", more: "Ostani doma. Nevarnost rušenja dreves in daljnovodov." },
  },
  WarningHT: {
    yellow: { desc: "Visoke temperature.", more: "Pijte dovolj tekočine. Izogibajte se fizičnim naporom v vročini." },
    orange: { desc: "Nevarna vročina.", more: "Poskrbite za starejše in bolne. Ne puščajte živali v zaprtih avtomobilih." },
    red:    { desc: "Nevarno vroče vreme.", more: "Ostanite v hladnih prostorih. Sledite navodilom oblasti." },
  },
  WarningLT: {
    yellow: { desc: "Nizke temperature.", more: "Zaščitite občutljive rastline in živali." },
    orange: { desc: "Mrzlo vreme.", more: "Poskrbite za ogrevanje in zaščito pred mrazom." },
    red:    { desc: "Nevarno mrzlo vreme.", more: "Omejite bivanje zunaj. Nevarnost ozeblin." },
  },
  WarningFF: {
    yellow: { desc: "Povečana požarna ogroženost.", more: "Ne kuriti na prostem. Bodite previdni z ognjem." },
    orange: { desc: "Visoka požarna ogroženost.", more: "Prepoved kurjenja na prostem." },
    red:    { desc: "Kritična požarna ogroženost.", more: "Sledite navodilom gasilcev in oblasti." },
  },
  WarningAV: {
    yellow: { desc: "Možnost sprožitve snežnih plazov.", more: "V goreh bodite previdni na nevarnih pobočjih." },
    orange: { desc: "Povečana nevarnost snežnih plazov.", more: "Izogibajte se gorskim pobočjem." },
    red:    { desc: "Velika nevarnost snežnih plazov.", more: "Ostanite v varnih predelih. Ne hodite v gore." },
  },
};

// Fetch warnings from vreme.arso.gov.si JSON API (same host as text forecast — works from CF Workers)
async function fetchArsoWarnings() {
  const r = await _arsoFetch("https://vreme.arso.gov.si/api/1.0/nonlocation/");
  if (!r.ok) throw new Error("ARSO API " + r.status);
  const data = await r.json();

  // Field is warning_si (not warnings.summary as initially assumed)
  const wsi = data?.warning_si;
  // `updated` je čas, ko je ARSO opozorilo izdal oz. nazadnje posodobil.
  // 15. člen ZDMHS zahteva, da vsak, ki opozorilo povzame, navede vir IN ta
  // čas -- zato ga vračamo odjemalcem skupaj z opozorili.
  const issued = wsi?.updated || null;
  if (!wsi) return { alerts: [], issued: null };

  const now = Date.now();
  const alerts = [];
  const seen = new Set();

  // Walk entire warning_si tree collecting event objects with degree + validEnd
  const walkEvents = (node) => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) { node.forEach(walkEvents); return; }

    // Event object: has degree + (validStart or validEnd or parameter_desc)
    const degree = (node.degree || node.level || "").toLowerCase();
    if (degree && (node.validEnd || node.validStart || node.parameter_desc || node.parameter)) {
      const validEnd = node.validEnd ? new Date(node.validEnd).getTime() : Infinity;
      if (validEnd >= now) {
        const level = ["red", "orange", "yellow"].includes(degree) ? degree : "yellow";
        const typeDesc = node.parameter_desc || node.type_desc || node.parameter || node.type || "Vremensko opozorilo";
        const key = `${typeDesc}:${level}:${node.validStart || ""}`;
        if (!seen.has(key)) {
          seen.add(key);
          let timeStr = "";
          if (node.validStart && node.validEnd) {
            const opts = { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Ljubljana" };
            const dOpts = { weekday: "short", day: "numeric", month: "numeric", timeZone: "Europe/Ljubljana" };
            const s = new Date(node.validStart);
            const e = new Date(node.validEnd);
            const sameDay = s.toLocaleDateString("sl", { timeZone: "Europe/Ljubljana" }) ===
                            e.toLocaleDateString("sl", { timeZone: "Europe/Ljubljana" });
            timeStr = sameDay
              ? ` · ${s.toLocaleDateString("sl", dOpts)} ${s.toLocaleTimeString("sl", opts)}–${e.toLocaleTimeString("sl", opts)}`
              : ` · ${s.toLocaleDateString("sl", dOpts)} ${s.toLocaleTimeString("sl", opts)} – ${e.toLocaleDateString("sl", dOpts)} ${e.toLocaleTimeString("sl", opts)}`;
          }
          const wt = WARNING_TEXTS[node.parameter]?.[level];
          alerts.push({
            level,
            text: typeDesc + timeStr,
            desc: wt?.desc || typeDesc,
            more: wt?.more || "",
            timeStr: timeStr.replace(/^ · /, ""),
            type: node.parameter || "",
            validStart: node.validStart || "",
            validEnd: node.validEnd || "",
          });
        }
      }
      return; // don't recurse into an event node's children
    }
    Object.values(node).forEach(walkEvents);
  };

  walkEvents(wsi);
  return { alerts, issued };
}

// ── Ecowitt helpers ────────────────────────────────────────
const pad = n => String(n).padStart(2, "0");
const fmtDate = d => d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());

async function fetchEcowitt(start, end, env) {
  const app = env?.EW_APP || EW_APP_FALLBACK;
  const api = env?.EW_API || EW_API_FALLBACK;
  if (!app || !api) return null;
  // Ecowitt device/history zahteva GET s query parametri — POST vrne 40010.
  const qs = new URLSearchParams({
    application_key: app, api_key: api, mac: EW_MAC,
    start_date: start+" 00:00:00", end_date: end+" 23:59:59",
    cycle_type: "auto",
    call_back: "outdoor.temperature,outdoor.humidity,wind.wind_speed,rainfall.daily,pressure.relative",
    temp_unitid:"1", pressure_unitid:"5", wind_speed_unitid:"7", rainfall_unitid:"12"
  });
  const res = await fetch("https://api.ecowitt.net/api/v3/device/history?"+qs.toString(), {
    method: "GET",
    headers: {"Accept":"application/json"}
  });
  const json = await res.json();
  if (json.code !== 0) throw new Error("Ecowitt "+json.code+": "+json.msg);
  return json.data;
}

// Rezerva za /current: postaja→Ecowitt oblak deluje, a WU (Weather Underground)
// upload iz Ecowitt konzole je lahko ugasnjen/zastal. Zgradi WU-oblikovan
// observations[0] iz Ecowitt real_time, da ostane fetchCurrent()/applyObs() v
// app.js nespremenjen.
async function fetchEcowittAsWuObs(env) {
  const app = env?.EW_APP || EW_APP_FALLBACK;
  const api = env?.EW_API || EW_API_FALLBACK;
  if (!app || !api) return null;
  const qs = new URLSearchParams({
    application_key: app, api_key: api, mac: EW_MAC,
    call_back: "outdoor,wind,pressure,rainfall,solar_and_uvi",
    temp_unitid: "1", pressure_unitid: "3", wind_speed_unitid: "7",
    rainfall_unitid: "12", solar_irradiance_unitid: "16",
  });
  let json;
  try {
    const res = await fetch("https://api.ecowitt.net/api/v3/device/real_time?" + qs.toString(), {
      headers: { "Accept": "application/json" }
    });
    json = await res.json();
  } catch (_) { return null; }
  if (json?.code !== 0) return null;
  const d = json.data || {};
  const v = x => num(x?.value);
  const temp = v(d.outdoor?.temperature);
  if (temp == null) return null;
  const now = new Date();
  return {
    stationID: STATION,
    obsTimeUtc: now.toISOString(),
    obsTimeLocal: fmtDate(now) + " " + now.toTimeString().slice(0, 8),
    lat: 46.3258, lon: 14.9211,
    humidity: v(d.outdoor?.humidity),
    winddir: v(d.wind?.wind_direction) ?? 0,
    uv: v(d.solar_and_uvi?.uvi),
    softwareType: "Ecowitt (WU rezerva)",
    qcStatus: 1,
    metric: {
      temp,
      dewpt: v(d.outdoor?.dew_point),
      windSpeed: v(d.wind?.wind_speed),
      windGust: v(d.wind?.wind_gust),
      pressure: v(d.pressure?.relative),
      precipRate: v(d.rainfall?.rain_rate),
      precipTotal: v(d.rainfall?.daily),
      solarRadiation: v(d.solar_and_uvi?.solar),
    }
  };
}

const tsToDate = ts => new Date(parseInt(ts)*1000).toISOString().slice(0,10);
const pf = v => v==null?null:typeof v==="object"?parseFloat(v.avg??v.max??Object.values(v)[0])||null:parseFloat(v)||null;
// Ecowitt vrača vrednosti kot skalarje ("19.2") ALI objekte {max,min,avg};
// num() ohrani tudi 0, pHi/pLo robustno izlušči high/low iz obeh oblik.
const num = x => { const n = parseFloat(x); return Number.isFinite(n) ? n : null; };
const pHi = v => (v && typeof v==="object") ? num(v.max??v.avg??v.value??Object.values(v)[0]) : num(v);
const pLo = v => (v && typeof v==="object") ? num(v.min??v.avg??v.value??Object.values(v)[0]) : num(v);

function normalize(data){
  const days={};
  const get=ts=>{const d=tsToDate(ts);if(!days[d])days[d]={obsTimeLocal:d,_h:[],_l:[],_a:[],_wH:[],_wA:[],_hum:[],_r:[]};return days[d];};
  const L=(...p)=>{let c=data;for(const k of p){c=c?.[k];if(c==null)return{};}return c?.list||{};};
  for(const[ts,v] of Object.entries(L("outdoor","temperature")||{})){
    const b=get(ts);b._h.push(pHi(v));b._l.push(pLo(v));b._a.push(pf(v));
  }
  for(const[ts,v] of Object.entries(L("outdoor","humidity")||{})) get(ts)._hum.push(pf(v));
  for(const[ts,v] of Object.entries(L("wind","wind_speed")||{})){
    const b=get(ts);b._wH.push(pHi(v));b._wA.push(pf(v));
  }
  const rList=L("rainfall","daily")||{};
  for(const[ts,v] of Object.entries(rList)) get(ts)._r.push(typeof v==="object"?parseFloat(v.total??v.max??0)||0:parseFloat(v)||0);
  const avg=a=>{const f=a.filter(x=>x!=null);return f.length?f.reduce((x,y)=>x+y,0)/f.length:null;};
  return Object.values(days).map(b=>({obsTimeLocal:b.obsTimeLocal,metric:{
    tempHigh:     b._h.filter(x=>x!=null).length?Math.max(...b._h.filter(x=>x!=null)):null,
    tempLow:      b._l.filter(x=>x!=null).length?Math.min(...b._l.filter(x=>x!=null)):null,
    tempAvg:      avg(b._a),
    windspeedHigh:b._wH.filter(x=>x!=null).length?Math.max(...b._wH.filter(x=>x!=null)):null,
    windspeedAvg: avg(b._wA),
    humidityAvg:  avg(b._hum)!=null?Math.round(avg(b._hum)):null,
    precipTotal:  b._r.length?Math.max(...b._r):0,
  }})).filter(s=>s.metric.tempHigh!=null).sort((a,b)=>a.obsTimeLocal.localeCompare(b.obsTimeLocal));
}

// ── Visitor counter (in-memory, resets on Worker restart) ─
// Za pravi persistentni counter potrebuješ Cloudflare KV binding "COUNTER_KV"
let _memCount = 1000; // začetna vrednost — nastavi po želji
const _memLikes = {}; // fallback za všečke, kadar KV ni na voljo (resetira se ob restartu)
const _memViews = {}; // fallback za oglede člankov, kadar KV ni na voljo
const _memPoll = {}; // fallback za dnevni poll, kadar KV ni na voljo (resetira se ob restartu)
let _memAndroidPoll = { da: 0, ne: 0 }; // fallback za android-poll, kadar KV ni na voljo

// ── Glavni handler ─────────────────────────────────────────
// ── Edge-rendered weather archive page helpers ─────────────────────────────

const MES_NOM_SL = ["januar","februar","marec","april","maj","junij",
                    "julij","avgust","september","oktober","november","december"];
const MES_GEN_SL = ["januarja","februarja","marca","aprila","maja","junija",
                    "julija","avgusta","septembra","oktobra","novembra","decembra"];

function numSl(x, d=1) {
  if (x == null) return "—";
  return x.toFixed(d).replace(".", ",");
}

function renderCurrentMonthPage(yr, mo, days) {
  const y = parseInt(yr), m = parseInt(mo);
  const monNom = MES_NOM_SL[m - 1];
  const monGen = MES_GEN_SL[m - 1];
  const url = `https://meteorec.si/vreme/${yr}/${mo}/`;
  const title = `Vreme — ${monNom.charAt(0).toUpperCase() + monNom.slice(1)} ${y}, Rečica ob Savinji`;
  const tavgs = days.map(([,v]) => v.tempAvg).filter(x => x != null);
  const precs = days.map(([,v]) => v.precipTotal ?? 0);
  const avg = tavgs.length ? (tavgs.reduce((a,b) => a+b,0)/tavgs.length) : null;
  const totalPrec = precs.reduce((a,b) => a+b,0);
  const desc = `${monNom.charAt(0).toUpperCase() + monNom.slice(1)} ${y} v Rečici ob Savinji: povp. temperatura ${numSl(avg)} °C, padavine ${numSl(totalPrec)} mm. Tekoče meritve postaje IREICA1.`;

  const rows = days.slice().reverse().map(([date, v]) => {
    const dd = parseInt(date.slice(8));
    return `<tr><td><a href="/vreme/${yr}/${mo}/${String(dd).padStart(2,'0')}/">${dd}.</a></td>`
      + `<td>${numSl(v.tempAvg)} °C</td>`
      + `<td>${numSl(v.tempLow)} °C / ${numSl(v.tempHigh)} °C</td>`
      + `<td>${numSl(v.precipTotal ?? 0)} mm</td>`
      + `<td>${numSl(v.windspeedHigh)} km/h</td></tr>`;
  }).join("\n");

  return `<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title} | Meteorec</title>
<link rel="canonical" href="${url}">
<meta name="description" content="${desc}">
<meta name="robots" content="index, follow">
<meta property="og:title" content="${title}">
<meta property="og:description" content="${desc}">
<meta property="og:url" content="${url}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:image" content="https://meteorec.si/og-image.jpg">
<meta property="og:locale" content="sl_SI">
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="stylesheet" href="/blog/blog.css">
<link rel="stylesheet" href="/vreme/vreme.css">
</head>
<body>
<div id="bg" aria-hidden="true"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div><div class="blob b4"></div><div class="blob b5"></div></div>
<div class="wrap">
  <header class="site-head">
    <a class="brand" href="/"><img class="brand-logo" src="/logo.svg" alt="" width="42" height="42">
    <span class="brand-name">Meteo<em>rec</em></span></a>
    <nav class="site-nav"><a href="/">Vreme v živo</a><a href="/blog/">Blog</a><a href="/vreme/">Arhiv</a></nav>
  </header>
  <nav class="crumbs" aria-label="Drobtine">
    <a href="/">Meteorec</a> › <a href="/vreme/">Vremenski arhiv</a> › <a href="/vreme/${y}/">${y}</a> › <span aria-current="page">${monNom.charAt(0).toUpperCase() + monNom.slice(1)} ${y}</span>
  </nav>
  <div class="stn-badge"><span></span> IREICA1 · Rečica ob Savinji</div>
  <h1 class="page-title">${monNom.charAt(0).toUpperCase() + monNom.slice(1)} ${y} — Rečica ob Savinji</h1>
  <p class="post-meta">Tekoče meritve · postaja IREICA1 · 366 m n. m. · ${days.length} dni</p>
  <div class="partial-note">Mesec še ni zaključen — prikazani so podatki do danes.</div>
  <div class="stat-grid">
    <div class="stat-card c-temp"><div class="sc-label">Povp. temperatura</div><div class="sc-val">${numSl(avg)} °C</div></div>
    <div class="stat-card c-rain"><div class="sc-label">Padavine skupaj</div><div class="sc-val">${numSl(totalPrec)} mm</div></div>
  </div>
  <h2>Dnevi v mesecu</h2>
  <table class="stats day-table">
    <thead><tr><th>Dan</th><th>Povp. T</th><th>Min / Max T</th><th>Padavine</th><th>Sunek</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <p class="muted-note">Vir: meteorološka postaja IREICA1, Rečica ob Savinji, Savinjska dolina (366 m n. m.).</p>
  <nav class="month-nav">
    <a href="/vreme/${y}/">← ${y}</a>
    <a href="/vreme/">Vsi arhivi</a>
    <span></span>
  </nav>
  <footer class="site-foot">
    <span>© ${y} Meteorec · Rečica ob Savinji</span>
    <span><a href="/">Vreme v živo</a> · <a href="/blog/">Blog</a> · <a href="/vreme/">Arhiv</a></span>
  </footer>
</div>
</body>
</html>`;
}

// ═══════════════════════════════════════════════════════════
// Web Push (VAPID + RFC 8291 aes128gcm) — brez zunanjih knjižnic
// ═══════════════════════════════════════════════════════════
const VAPID_PUBLIC = "BCKBiX8AvTSRv98CufvMl51rpizfpg_LHm9K0rSCQYNJzfxV88tP60_n8mJ7bUEQo02zS02_l-FvTCtkSvfx3iY";
const VAPID_SUBJECT = "mailto:filip.eremita@gmail.com";

const _enc = new TextEncoder();
function _b64u(buf) {
  let s = ""; const b = new Uint8Array(buf);
  for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function _unb64u(str) {
  str = str.replace(/-/g, "+").replace(/_/g, "/"); while (str.length % 4) str += "=";
  const bin = atob(str), out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
function _cat() {
  let n = 0; for (const a of arguments) n += a.length;
  const out = new Uint8Array(n); let o = 0;
  for (const a of arguments) { out.set(a, o); o += a.length; }
  return out;
}
async function _hkdf(salt, ikm, info, len) {
  const key = await crypto.subtle.importKey("raw", ikm, "HKDF", false, ["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt, info }, key, len * 8));
}
async function _vapidJWT(aud, d) {
  const pub = _unb64u(VAPID_PUBLIC);
  const jwk = { kty: "EC", crv: "P-256", d, x: _b64u(pub.subarray(1, 33)), y: _b64u(pub.subarray(33, 65)), ext: true };
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const head = _b64u(_enc.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const body = _b64u(_enc.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 43200, sub: VAPID_SUBJECT })));
  const si = head + "." + body;
  const sig = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, _enc.encode(si)));
  return si + "." + _b64u(sig);
}
async function _encryptPush(payload, p256dhB64, authB64) {
  const ua_pub = _unb64u(p256dhB64), ua_auth = _unb64u(authB64);
  const asKey = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const as_pub = new Uint8Array(await crypto.subtle.exportKey("raw", asKey.publicKey));
  const uaKey = await crypto.subtle.importKey("raw", ua_pub, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const ecdh = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaKey }, asKey.privateKey, 256));
  const prk = await _hkdf(ua_auth, ecdh, _cat(_enc.encode("WebPush: info\0"), ua_pub, as_pub), 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await _hkdf(salt, prk, _enc.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await _hkdf(salt, prk, _enc.encode("Content-Encoding: nonce\0"), 12);
  const content = _cat(_enc.encode(payload), new Uint8Array([0x02]));
  const aes = await crypto.subtle.importKey("raw", cek, { name: "AES-GCM" }, false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, aes, content));
  const header = _cat(salt, new Uint8Array([0, 0, 0x10, 0x00]), new Uint8Array([65]), as_pub);
  return _cat(header, ct);
}
async function _sendPush(env, sub, payloadObj) {
  const url = new URL(sub.endpoint);
  const jwt = await _vapidJWT(url.origin, env.VAPID_PRIVATE);  // env.VAPID_PRIVATE = skrivnost (d)
  const body = await _encryptPush(JSON.stringify(payloadObj), sub.keys.p256dh, sub.keys.auth);
  const res = await fetch(sub.endpoint, {
    method: "POST",
    headers: {
      "Authorization": "vapid t=" + jwt + ", k=" + VAPID_PUBLIC,
      "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream",
      "TTL": "86400"
    },
    body
  });
  return res.status;
}
// Pošlji obvestilo naročnikom (počisti potekle). Vrne {sent, pruned}.
// Brez `filter` gre vsem; z njim samo tistim, ki mu ustrezajo — tako gredo
// obvestila za posamezno vas res le naročnikom te vasi. Potekle naročnine
// počistimo iz celotnega seznama, ne le iz izbranega podniza.
async function _pushAll(env, payload, filter) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return { sent: 0, pruned: 0 };
  let subs = []; try { const o = await r2.get("push/subs.json"); subs = o ? JSON.parse(await o.text()) : []; } catch (_) {}
  const target = filter ? subs.filter(filter) : subs;
  const dead = [];
  await Promise.all(target.map(async s => {
    try { const st = await _sendPush(env, s, payload); if (st === 404 || st === 410) dead.push(s.endpoint); }
    catch (_) {}
  }));
  if (dead.length) await r2.put("push/subs.json", JSON.stringify(subs.filter(x => dead.indexOf(x.endpoint) === -1)), { httpMetadata: { contentType: "application/json" } });
  return { sent: target.length - dead.length, pruned: dead.length };
}

// ── Samodejni pragovni alarm (cron) ────────────────────────
// Pragovi (po dogovoru): sunek >40 km/h, naliv >18 mm/h, vročina ≥30 °C, zmrzal ≤−1 °C.
const PUSH_THRESHOLDS = [
  { key: "gust",  test: m => (m.windGust ?? m.windSpeed ?? 0) > 40, msg: m => "💨 Močan sunek vetra: " + Math.round(m.windGust ?? m.windSpeed) + " km/h v Rečici ob Savinji — prav zdaj." },
  { key: "rain",  test: m => (m.precipRate ?? 0) > 18,             msg: m => "🌧️ Intenziven naliv: " + (m.precipRate).toFixed(1) + " mm/h v Rečici ob Savinji — prav zdaj." },
  { key: "heat",  test: m => (m.temp ?? -99) >= 30,                msg: m => "🌡️ Vročina: " + (m.temp).toFixed(1) + " °C v Rečici ob Savinji." },
  { key: "frost", test: m => (m.temp ?? 99) <= -1,                 msg: m => "🧊 Zmrzal: " + (m.temp).toFixed(1) + " °C v Rečici ob Savinji." },
];
const PUSH_COOLDOWN_MS = 3 * 3600 * 1000;
async function _cronCheckThresholds(env) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return;
  let obs; try { obs = (await (await fetch(CURRENT_URL, { headers: { "Accept": "application/json" } })).json()); } catch (_) { return; }
  const m = obs?.observations?.[0]?.metric; if (!m) return;
  let state = {}; try { const o = await r2.get("push/state.json"); state = o ? JSON.parse(await o.text()) : {}; } catch (_) {}
  const now = Date.now();
  let changed = false;
  for (const t of PUSH_THRESHOLDS) {
    const over = t.test(m);
    const st = state[t.key] || { over: false, lastSent: 0 };
    if (over && !st.over && (now - (st.lastSent || 0) > PUSH_COOLDOWN_MS)) {
      await _pushAll(env, { title: "Meteorec — opozorilo", body: t.msg(m), url: "/", tag: "wx-" + t.key });
      st.lastSent = now;
    }
    st.over = over;
    state[t.key] = st;
    changed = true;
  }
  if (changed) await r2.put("push/state.json", JSON.stringify(state), { httpMetadata: { contentType: "application/json" } });
}

// ── Napovedni alarm — dež/nevihta v naslednjih ~10–45 min (Open-Meteo minutely_15) ──
// Ločeno od PUSH_THRESHOLDS: tisti opozarjajo na trenutne razmere, ta pa na napoved.
const NOWCAST_COOLDOWN_MS = 90 * 60 * 1000; // isti prihajajoči dogodek naznani le enkrat
async function _cronCheckPrecipNowcast(env) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return;
  let data;
  try {
    const url = "https://api.open-meteo.com/v1/forecast?latitude=46.3258&longitude=14.9211"
      + "&minutely_15=precipitation,weather_code&forecast_minutely_15=8&timezone=UTC";
    const ctrl = new AbortController(); const tid = setTimeout(() => ctrl.abort(), 8000);
    data = await (await fetch(url, { signal: ctrl.signal }).finally(() => clearTimeout(tid))).json();
  } catch (_) { return; }
  const m = data?.minutely_15; if (!m?.time?.length) return;

  const now = Date.now();
  const slots = m.time.map((t, i) => ({
    minAway: Math.round((new Date(t).getTime() - now) / 60000),
    precip: m.precipitation?.[i] || 0,
    wmo: m.weather_code?.[i] ?? 0,
  }));
  const nowSlot = slots.find(s => s.minAway >= -7 && s.minAway <= 7);
  const isWetNow = (nowSlot?.precip || 0) >= 0.1;
  const upcoming = slots.filter(s => s.minAway > 7 && s.minAway <= 45);
  const firstWet = upcoming.find(s => s.precip >= 0.1);
  const firstStorm = upcoming.find(s => [95, 96, 99].includes(s.wmo));

  let state = {}; try { const o = await r2.get("push/nowcast_state.json"); state = o ? JSON.parse(await o.text()) : {}; } catch (_) {}
  let changed = false;
  const maybeFire = async (key, hit, msgFn) => {
    const st = state[key] || { over: false, lastSent: 0 };
    const over = !!hit;
    if (over && !st.over && (now - (st.lastSent || 0) > NOWCAST_COOLDOWN_MS)) {
      await _pushAll(env, { title: "Meteorec — napoved", body: msgFn(hit), url: "/", tag: "wx-" + key });
      st.lastSent = now;
    }
    st.over = over;
    state[key] = st;
    changed = true;
  };
  await maybeFire("rain_soon", !isWetNow && firstWet, s => "🌧️ Dež pričakovan čez ~" + s.minAway + " min v Rečici ob Savinji.");
  await maybeFire("storm_soon", firstStorm, s => "⛈️ Nevihta pričakovana čez ~" + s.minAway + " min v Rečici ob Savinji.");
  if (changed) await r2.put("push/nowcast_state.json", JSON.stringify(state), { httpMetadata: { contentType: "application/json" } });
}

// ── Začetek/konec dejanskih padavin na postaji ──────────────
// Ločeno od PUSH_THRESHOLDS (tisti javi šele pri intenzivnem nalivu >18 mm/h).
// Tu: dogodek se šteje za začetega pri ≥1 mm/h, konča pa se šele, ko stopnja pade na 0.
const RAIN_START_THR = 1; // mm/h
async function _cronCheckRainStartStop(env) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return;
  let obs; try { obs = (await (await fetch(CURRENT_URL, { headers: { "Accept": "application/json" } })).json()); } catch (_) { return; }
  const m = obs?.observations?.[0]?.metric; if (!m) return;
  const rate = m.precipRate ?? 0;
  let state = {}; try { const o = await r2.get("push/rain_state.json"); state = o ? JSON.parse(await o.text()) : {}; } catch (_) {}
  const wasRaining = !!state.raining;
  let raining = wasRaining;
  if (!wasRaining && rate >= RAIN_START_THR) {
    await _pushAll(env, { title: "Meteorec — opozorilo", body: "🌧️ Začelo je deževati: " + rate.toFixed(1) + " mm/h v Rečici ob Savinji.", url: "/", tag: "wx-rain-start" });
    raining = true;
  } else if (wasRaining && rate <= 0) {
    await _pushAll(env, { title: "Meteorec — opozorilo", body: "☀️ Dež je ponehal v Rečici ob Savinji.", url: "/", tag: "wx-rain-stop" });
    raining = false;
  }
  if (raining !== wasRaining) await r2.put("push/rain_state.json", JSON.stringify({ raining }), { httpMetadata: { contentType: "application/json" } });
}

// ── Polarni sij: obvestilo ob hudi geomagnetni nevihti ─────
// S 46° s. š. je sij izjemen dogodek, zato je prag namerno visok (Kp ≥ 7).
// Nižje vrednosti bi pomenile obvestila brez pokritja: oval je takrat še nad
// Skandinavijo. Pri Kp ≥ 7 se splača pogledati proti severu, kot maja 2024.
const AURORA_KP_THR = 7;
const AURORA_COOLDOWN_MS = 6 * 3600 * 1000;
async function _cronCheckAurora(env) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return;
  // Sij je viden le v temi. Obvestilo podnevi bi bilo neuporabno, nevihta pa
  // tipično traja več ur, zato ga cron ujame zvečer, če še traja.
  // % 24, ker nekatere izvedbe ICU za polnoč vrnejo "24" namesto "00".
  const hourSI = Number(new Date().toLocaleString("en-GB", { timeZone: "Europe/Ljubljana", hour: "2-digit", hour12: false })) % 24;
  if (hourSI >= 6 && hourSI < 20) return;

  let kp = null;
  try {
    const rows = await (await fetch("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json")).json();
    const obs = (Array.isArray(rows) ? rows : []).filter(r => r?.observed === "observed" && r.kp != null);
    if (obs.length) kp = Number(obs[obs.length - 1].kp);
  } catch (_) { return; }
  if (kp == null || kp < AURORA_KP_THR) return;

  let state = {}; try { const o = await r2.get("push/aurora_state.json"); state = o ? JSON.parse(await o.text()) : {}; } catch (_) {}
  const now = Date.now();
  if (now - (state.lastSent || 0) < AURORA_COOLDOWN_MS) return;

  await _pushAll(env, {
    title: "Meteorec — polarni sij?",
    body: "🌌 Huda geomagnetna nevihta (Kp " + kp.toFixed(1).replace(".", ",") + "). Poglej proti severu — ob jasnem nebu je mogoč rdeč sij nizko nad obzorjem.",
    url: "/", tag: "wx-aurora",
  });
  await r2.put("push/aurora_state.json", JSON.stringify({ lastSent: now, kp }), { httpMetadata: { contentType: "application/json" } });
}

// ═══════════════════════════════════════════════════════════
//  Nowcasting neviht in toče iz radarske slike ARSO
// ═══════════════════════════════════════════════════════════
// Za razliko od _cronCheckPrecipNowcast (ki bere Open-Meteo, torej model na
// mreži nekaj kilometrov z urno osvežitvijo) tu beremo dejansko radarsko
// sliko, ocenimo premik celic in izračunamo, kdaj celica doseže posamezno vas.
//
// Vir: si0-rm-anim.gif — animacija zadnjih 90 minut, nov posnetek vsakih 5 min,
// 821×660 px, 32-barvna paleta, lestvica "MAX RAINFALL RATE" v mm/h.
//
// Preverjeno na primeru 26. 7. 2026 (hindcast na 10-km okolici vasi):
//   dež ≥2 mm/h,   30 min: POD 0,73  FAR 0,20
//   nevihta ≥15,   30 min: POD 0,61  FAR 0,33
//   jedro ≥50,     30 min: POD 0,42  FAR 0,40
//   pri 45 minutah vse troje opazno pade (jedro FAR 0,60) — zato je obzorje
//   za nevihto in točo omejeno na 30 minut, za dež na 45.
// To je en dan in ena vremenska situacija; številke jemlji kot red velikosti.

const RADAR_URL = "https://meteo.arso.gov.si/uploads/probase/www/observ/radar/si0-rm-anim.gif";
const RADAR_MAX_AGE_MIN = 20;      // starejše slike ne uporabimo za nowcast

// Barvna lestvica z legende, od najšibkejše proti najmočnejši.
const RADAR_LEVEL_RGB = [
  [8, 90, 254], [0, 140, 254], [0, 174, 253], [0, 200, 254], [4, 216, 131],
  [66, 235, 66], [108, 249, 0], [184, 250, 0], [249, 250, 0], [254, 198, 0],
  [254, 132, 0], [255, 62, 1], [211, 0, 0], [181, 3, 3], [203, 0, 204],
];
// Legenda označuje vsako drugo polje (.5 1 2 5 15 50 100 mm/h); vmesna polja
// so geometrijska sredina sosedov.
const RADAR_LEVEL_MMH = [0.35, 0.5, 0.7, 1, 1.4, 2, 3.2, 5, 8.7, 15, 27, 50, 71, 100, 140];

// Pragovi v stopnjah lestvice zgoraj.
const RADAR_L_RAIN = 6;            // ≥2 mm/h
const RADAR_L_STORM = 10;          // ≥15 mm/h
const RADAR_L_CORE = 12;           // ≥50 mm/h — jedro, ki zmore točo
const RADAR_CORE_MIN_PX = 6;       // ~1,5 km² — odreže posamezne šumne piksle
const RADAR_HORIZON_RAIN = 45;
const RADAR_HORIZON_STORM = 30;
const RADAR_NEAR_PX = 6;           // ~3 km okoli vasi — dopusti napako lege

// Georeferenca: navadna enakopravokotna projekcija. Umerjeno na 14 mest
// (Ljubljana, Maribor, Celovec, Videm, Bovec …), RMS 1,7 px ≈ 0,85 km.
const RAD_AX = 153.013374, RAD_BX = -1849.035845;
const RAD_AY = -222.729262, RAD_BY = 10607.713236;
const RAD_KM_X = 0.5026, RAD_KM_Y = 0.4964;
const RAD_HEADER_PX = 44;          // naslovna vrstica z legendo — ni padavin
const RAD_STEP_MIN = 5;

function _radLonLat2Px(lon, lat) { return [RAD_AX * lon + RAD_BX, RAD_AY * lat + RAD_BY]; }

// Vasi, med katerimi uporabnik izbira. Koordinate so središča naselij —
// za 40-minutno napoved na 0,5-kilometrski mreži je to dovolj natančno.
// `loc` je mestnik, da so obvestila slovnično pravilna ("v Mozirju", "na Polzeli").
const NOWCAST_VASI = [
  { id: "recica",      name: "Rečica ob Savinji", loc: "v Rečici ob Savinji", lat: 46.3258, lon: 14.9211 },
  { id: "mozirje",     name: "Mozirje",           loc: "v Mozirju",           lat: 46.3389, lon: 14.9603 },
  { id: "nazarje",     name: "Nazarje",           loc: "v Nazarjah",          lat: 46.2903, lon: 14.9481 },
  { id: "ljubno",      name: "Ljubno ob Savinji", loc: "na Ljubnem ob Savinji", lat: 46.3439, lon: 14.8342 },
  { id: "luce",        name: "Luče",              loc: "v Lučah",             lat: 46.3547, lon: 14.7480 },
  { id: "solcava",     name: "Solčava",           loc: "v Solčavi",           lat: 46.4192, lon: 14.6931 },
  { id: "logarska",    name: "Logarska dolina",   loc: "v Logarski dolini",   lat: 46.3925, lon: 14.6289 },
  { id: "gornjigrad",  name: "Gornji Grad",       loc: "v Gornjem Gradu",     lat: 46.2958, lon: 14.8064 },
  { id: "smartnopaka", name: "Šmartno ob Paki",   loc: "v Šmartnem ob Paki",  lat: 46.3308, lon: 15.0339 },
  { id: "sostanj",     name: "Šoštanj",           loc: "v Šoštanju",          lat: 46.3789, lon: 15.0475 },
  { id: "velenje",     name: "Velenje",           loc: "v Velenju",           lat: 46.3592, lon: 15.1103 },
  { id: "braslovce",   name: "Braslovče",         loc: "v Braslovčah",        lat: 46.2872, lon: 15.0403 },
  { id: "polzela",     name: "Polzela",           loc: "na Polzeli",          lat: 46.2811, lon: 15.0722 },
  { id: "prebold",     name: "Prebold",           loc: "v Preboldu",          lat: 46.2364, lon: 15.0919 },
  { id: "zalec",       name: "Žalec",             loc: "v Žalcu",             lat: 46.2519, lon: 15.1647 },
  { id: "vransko",     name: "Vransko",           loc: "na Vranskem",         lat: 46.2450, lon: 14.9508 },
  { id: "celje",       name: "Celje",             loc: "v Celju",             lat: 46.2311, lon: 15.2683 },
];

// ── Dekodirnik GIF ─────────────────────────────────────────
// Delegates/canvas v Workerju ni, zato dekodiramo sami. ARSO uporablja eno
// samo globalno paleto, disposal 1 (okvirji se seštevajo) in prosojni indeks,
// ki se med okvirji spreminja — tudi na barve padavin, zato ga je nujno brati
// iz vsakega GCE posebej, sicer bi si pokvarili prav najmočnejša jedra.
function _gifDecodeFrames(bytes) {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  if (u8[0] !== 0x47 || u8[1] !== 0x49 || u8[2] !== 0x46) throw new Error("ni GIF");
  const w = u8[6] | (u8[7] << 8), h = u8[8] | (u8[9] << 8);
  const flags = u8[10];
  let p = 13, gct = null;
  if (flags & 0x80) { const n = 1 << ((flags & 7) + 1); gct = u8.subarray(p, p + 3 * n); p += 3 * n; }

  const canvas = new Uint8Array(w * h);
  const frames = [];
  let tIndex = -1;
  const skipSub = (i) => { while (u8[i]) i += u8[i] + 1; return i + 1; };

  while (p < u8.length) {
    const b = u8[p];
    if (b === 0x21) {
      if (u8[p + 1] === 0xF9) tIndex = (u8[p + 3] & 1) ? u8[p + 6] : -1;
      p = skipSub(p + 2);
      continue;
    }
    if (b === 0x2C) {
      const left = u8[p + 1] | (u8[p + 2] << 8), top = u8[p + 3] | (u8[p + 4] << 8);
      const fw = u8[p + 5] | (u8[p + 6] << 8), fh = u8[p + 7] | (u8[p + 8] << 8);
      const f = u8[p + 9], interlaced = !!(f & 0x40);
      p += 10;
      if (f & 0x80) p += 3 * (1 << ((f & 7) + 1));
      const minCode = u8[p++];
      let total = 0;
      for (let q = p; u8[q]; q += u8[q] + 1) total += u8[q];
      const data = new Uint8Array(total);
      let dp = 0;
      for (let q = p; u8[q]; q += u8[q] + 1) { data.set(u8.subarray(q + 1, q + 1 + u8[q]), dp); dp += u8[q]; }
      p = skipSub(p);
      const px = _gifLzw(data, minCode, fw * fh);
      if (interlaced) {
        let src = 0;
        for (const [start, step] of [[0, 8], [4, 8], [2, 4], [1, 2]]) {
          for (let y = start; y < fh; y += step) { _gifBlit(canvas, w, h, px, src * fw, left, top + y, fw, tIndex); src++; }
        }
      } else {
        for (let y = 0; y < fh; y++) _gifBlit(canvas, w, h, px, y * fw, left, top + y, fw, tIndex);
      }
      frames.push(canvas.slice());
      continue;
    }
    break;                                   // 0x3B (konec) ali neznan blok
  }
  return { width: w, height: h, palette: gct, frames };
}

function _gifBlit(canvas, cw, ch, px, srcOff, left, y, fw, tIndex) {
  if (y < 0 || y >= ch) return;
  const dst = y * cw + left, n = Math.min(fw, cw - left);
  for (let x = 0; x < n; x++) { const v = px[srcOff + x]; if (v !== tIndex) canvas[dst + x] = v; }
}

function _gifLzw(data, minCodeSize, expected) {
  const out = new Uint8Array(expected);
  const clear = 1 << minCodeSize, eoi = clear + 1;
  const prefix = new Int32Array(4096), suffix = new Uint8Array(4096), stack = new Uint8Array(4096);
  let codeSize = minCodeSize + 1, mask = (1 << codeSize) - 1, next = clear + 2;
  let bitBuf = 0, bitCnt = 0, pos = 0, op = 0, prev = -1, prevFirst = 0;
  for (let i = 0; i < clear; i++) { prefix[i] = -1; suffix[i] = i; }

  while (op < expected) {
    while (bitCnt < codeSize) {
      if (pos >= data.length) return out;    // okrnjen tok — vrni, kar imamo
      bitBuf |= data[pos++] << bitCnt; bitCnt += 8;
    }
    const code = bitBuf & mask;
    bitBuf >>>= codeSize; bitCnt -= codeSize;
    if (code === clear) { codeSize = minCodeSize + 1; mask = (1 << codeSize) - 1; next = clear + 2; prev = -1; continue; }
    if (code === eoi) break;
    let sp = 0, cur = code;
    if (code >= next) { if (prev < 0) break; stack[sp++] = prevFirst; cur = prev; }
    while (cur >= clear) { stack[sp++] = suffix[cur]; cur = prefix[cur]; }
    const first = cur;
    stack[sp++] = first;
    while (sp > 0 && op < expected) out[op++] = stack[--sp];
    if (prev >= 0 && next < 4096) {
      prefix[next] = prev; suffix[next] = first; next++;
      if (next === (1 << codeSize) && codeSize < 12) { codeSize++; mask = (1 << codeSize) - 1; }
    }
    prev = code; prevFirst = first;
  }
  return out;
}

// ── Radarsko polje ─────────────────────────────────────────
// Paleto preslikamo prek RGB in ne prek fiksnih indeksov, da preživimo
// morebitno prerazporeditev barvne tabele pri ARSO.
function _radLut(palette) {
  const lut = new Uint8Array(256);
  for (let i = 0; i < palette.length / 3; i++) {
    const r = palette[i * 3], g = palette[i * 3 + 1], b = palette[i * 3 + 2];
    for (let L = 0; L < RADAR_LEVEL_RGB.length; L++) {
      const c = RADAR_LEVEL_RGB[L];
      if (c[0] === r && c[1] === g && c[2] === b) { lut[i] = L + 1; break; }
    }
  }
  return lut;
}

function _radLevels(frame, lut, w) {
  const out = new Uint8Array(frame.length);
  for (let i = 0; i < frame.length; i++) out[i] = lut[frame[i]];
  out.fill(0, 0, RAD_HEADER_PX * w);
  return out;
}

// Zadnji okvirji so podvojeni (animacija se na koncu ustavi). Ločimo jih po
// vžganem časovnem žigu — padavine se med posnetkoma lahko slučajno ne
// spremenijo, žig pa se vedno.
function _radDistinct(frames, w) {
  const seen = new Set(), keep = [];
  for (const f of frames) {
    let k = "";
    for (let y = 28; y < 38; y++) for (let x = 5; x < 165; x += 2) k += String.fromCharCode(f[y * w + x]);
    if (seen.has(k)) continue;
    seen.add(k); keep.push(f);
  }
  return keep;
}

function _radDownsample(src, w, x0, x1, y0, y1, k) {
  const dw = Math.floor((x1 - x0) / k), dh = Math.floor((y1 - y0) / k);
  const out = new Float32Array(dw * dh);
  for (let y = 0; y < dh; y++) for (let x = 0; x < dw; x++) {
    let s = 0;
    for (let j = 0; j < k; j++) { const row = (y0 + y * k + j) * w + x0 + x * k; for (let i = 0; i < k; i++) s += src[row + i]; }
    out[y * dw + x] = s / (k * k);
  }
  return { data: out, w: dw, h: dh };
}

// Ničelno-povprečna navzkrižna korelacija: odporna na rast in upadanje
// odbojnosti, česar vsota kvadratov razlik ni (tam rast celic potisne
// najboljši zadetek na ničelni zamik).
function _radNcc(A, B, w, h, rad, cx, cy) {
  let best = null;
  for (let dy = cy - rad; dy <= cy + rad; dy++) for (let dx = cx - rad; dx <= cx + rad; dx++) {
    const ax0 = Math.max(0, -dx), ax1 = Math.min(w, w - dx);
    const ay0 = Math.max(0, -dy), ay1 = Math.min(h, h - dy);
    const nw = ax1 - ax0, nh = ay1 - ay0;
    if (nw < 20 || nh < 20) continue;
    let sa = 0, sb = 0; const n = nw * nh;
    for (let y = ay0; y < ay1; y++) { const ra = y * w, rb = (y + dy) * w + dx; for (let x = ax0; x < ax1; x++) { sa += A[ra + x]; sb += B[rb + x]; } }
    const ma = sa / n, mb = sb / n;
    let num = 0, da = 0, db = 0;
    for (let y = ay0; y < ay1; y++) {
      const ra = y * w, rb = (y + dy) * w + dx;
      for (let x = ax0; x < ax1; x++) { const va = A[ra + x] - ma, vb = B[rb + x] - mb; num += va * vb; da += va * va; db += vb * vb; }
    }
    const den = Math.sqrt(da * db);
    if (den <= 0) continue;
    const r = num / den;
    if (!best || r > best.r) best = { r, dx, dy };
  }
  return best;
}

// Premik ocenimo na 15-minutni osnovi: v 5 minutah se celica premakne le
// dober piksel, kar je pod ločljivostjo mreže in vrne ničelni zamik.
function _radMotion(older, newer, w, minutes, roi) {
  const { x0, x1, y0, y1 } = roi, K = 4;
  const A = _radDownsample(older, w, x0, x1, y0, y1, K);
  const B = _radDownsample(newer, w, x0, x1, y0, y1, K);
  const coarse = _radNcc(A.data, B.data, A.w, A.h, 10, 0, 0);
  if (!coarse) return null;
  const sub = (src) => {
    const sw = x1 - x0, sh = y1 - y0, o = new Float32Array(sw * sh);
    for (let y = 0; y < sh; y++) for (let x = 0; x < sw; x++) o[y * sw + x] = src[(y0 + y) * w + x0 + x];
    return o;
  };
  const fine = _radNcc(sub(older), sub(newer), x1 - x0, y1 - y0, 3, coarse.dx * K, coarse.dy * K);
  const best = fine || { dx: coarse.dx * K, dy: coarse.dy * K, r: coarse.r };
  return {
    dxPerMin: best.dx / minutes, dyPerMin: best.dy / minutes, r: best.r,
    kmh: Math.hypot(best.dx * RAD_KM_X, best.dy * RAD_KM_Y) / (minutes / 60),
    smer: (Math.atan2(best.dx * RAD_KM_X, -best.dy * RAD_KM_Y) * 180 / Math.PI + 360) % 360,
  };
}

// Najvišja stopnja in velikost jedra v okencu okoli točke.
function _radProbe(levels, w, h, cx, cy, rad) {
  let max = 0, core = 0;
  const x0 = Math.max(0, Math.round(cx) - rad), x1 = Math.min(w - 1, Math.round(cx) + rad);
  const y0 = Math.max(RAD_HEADER_PX, Math.round(cy) - rad), y1 = Math.min(h - 1, Math.round(cy) + rad);
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    const v = levels[y * w + x];
    if (v > max) max = v;
    if (v >= RADAR_L_CORE) core++;
  }
  return { max, core };
}

// Kar bo ob času t nad vasjo, je zdaj na legi (vas − hitrost·t).
function _radVillage(levels, w, h, motion, vas) {
  const [vx, vy] = _radLonLat2Px(vas.lon, vas.lat);
  const zdaj = _radProbe(levels, w, h, vx, vy, RADAR_NEAR_PX);
  const track = [];
  for (let t = RAD_STEP_MIN; t <= RADAR_HORIZON_RAIN; t += RAD_STEP_MIN) {
    const s = _radProbe(levels, w, h, vx - motion.dxPerMin * t, vy - motion.dyPerMin * t, RADAR_NEAR_PX);
    track.push({ t, level: s.max, core: s.core });
  }
  const first = (test, horizon) => { const hit = track.find(s => s.t <= horizon && test(s)); return hit ? hit.t : null; };
  return {
    id: vas.id, ime: vas.name,
    zdaj: zdaj.max,
    zdajMmh: zdaj.max ? RADAR_LEVEL_MMH[zdaj.max - 1] : 0,
    dez: first(s => s.level >= RADAR_L_RAIN, RADAR_HORIZON_RAIN),
    nevihta: first(s => s.level >= RADAR_L_STORM, RADAR_HORIZON_STORM),
    jedro: first(s => s.core >= RADAR_CORE_MIN_PX, RADAR_HORIZON_STORM),
    // Potek po petminutnih korakih — stran iz njega nariše trak približevanja.
    // `l` je stopnja lestvice, `mmh` pripadajoča jakost.
    potek: track.map(s => ({ t: s.t, l: s.level, mmh: s.level ? RADAR_LEVEL_MMH[s.level - 1] : 0 })),
  };
}

// Okolje za točo — en klic za celotno dolino, saj je zračna masa na 30 km
// praktično enaka. Radarsko jedro samo po sebi ne loči toče od močnega
// naliva, zato ga pogojujemo s CAPE in indeksom dviga.
const HAIL_CAPE_MIN = 700, HAIL_LI_MAX = -3;
async function _radOkolje() {
  try {
    const url = "https://api.open-meteo.com/v1/forecast?latitude=46.3258&longitude=14.9211"
      + "&minutely_15=cape,lifted_index&forecast_minutely_15=4&timezone=UTC";
    const ctrl = new AbortController(); const tid = setTimeout(() => ctrl.abort(), 8000);
    const d = await (await fetch(url, { signal: ctrl.signal }).finally(() => clearTimeout(tid))).json();
    const cape = Math.max(...(d?.minutely_15?.cape || [0]).filter(v => v != null));
    const li = Math.min(...(d?.minutely_15?.lifted_index || [99]).filter(v => v != null));
    return { cape, li, ugodno: cape >= HAIL_CAPE_MIN && li <= HAIL_LI_MAX };
  } catch (_) { return { cape: null, li: null, ugodno: false }; }
}

// Prenesi in razčleni radar; vrne null, če je slika prestara ali nedosegljiva.
async function _radFetch() {
  let res;
  try {
    const ctrl = new AbortController(); const tid = setTimeout(() => ctrl.abort(), 12000);
    res = await fetch(RADAR_URL, { signal: ctrl.signal, cf: { cacheTtl: 60 } }).finally(() => clearTimeout(tid));
  } catch (_) { return null; }
  if (!res.ok) return null;
  const lm = res.headers.get("last-modified");
  const ageMin = lm ? (Date.now() - new Date(lm).getTime()) / 60000 : 0;
  if (ageMin > RADAR_MAX_AGE_MIN) return null;      // zastarela slika — rajši nič kot narobe
  const g = _gifDecodeFrames(new Uint8Array(await res.arrayBuffer()));
  if (!g.palette || g.frames.length < 4) return null;
  const lut = _radLut(g.palette);
  const lv = _radDistinct(g.frames, g.width).map(f => _radLevels(f, lut, g.width));
  if (lv.length < 4) return null;
  const [x0, y0] = _radLonLat2Px(12.6, 47.1), [x1, y1] = _radLonLat2Px(16.5, 45.3);
  const roi = { x0: Math.round(x0), x1: Math.round(x1), y0: Math.round(y0), y1: Math.round(y1) };
  const motion = _radMotion(lv[lv.length - 4], lv[lv.length - 1], g.width, 3 * RAD_STEP_MIN, roi);
  if (!motion) return null;
  return { w: g.width, h: g.height, levels: lv[lv.length - 1], motion, ageMin };
}

// Izračunaj stanje za vse vasi in ga shrani v R2, da ga /nowcast le prebere.
async function _radNowcastAll(env) {
  const rad = await _radFetch();
  if (!rad) return null;
  const okolje = await _radOkolje();
  const vasi = NOWCAST_VASI.map(v => {
    const n = _radVillage(rad.levels, rad.w, rad.h, rad.motion, v);
    n.toca = n.jedro != null && okolje.ugodno;     // jedro + ugodno okolje
    return n;
  });
  const out = {
    ts: new Date().toISOString(),
    starost_min: Math.round(rad.ageMin),
    premik: { kmh: Math.round(rad.motion.kmh), smer: Math.round(rad.motion.smer), r: Number(rad.motion.r.toFixed(2)) },
    okolje, vasi,
  };
  try { await env?.PHOTOS_R2?.put("nowcast/latest.json", JSON.stringify(out), { httpMetadata: { contentType: "application/json" } }); } catch (_) {}
  return out;
}

// Obvesti samo naročnike izbrane vasi. Ločena hladilna doba po vasi in vrsti
// dogodka, da isti prihod celice ne pošlje več obvestil zapored.
const RADAR_COOLDOWN_MS = 60 * 60 * 1000;
async function _cronCheckRadarNowcast(env) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return false;
  const nc = await _radNowcastAll(env);
  if (!nc) return false;

  let subs = []; try { const o = await r2.get("push/subs.json"); subs = o ? JSON.parse(await o.text()) : []; } catch (_) {}
  // Naročnine od prej vasi nimajo — dokler je uporabnik ne izbere, veljajo za
  // postajo v Rečici. Brez tega bi obstoječi naročniki po tej spremembi tiho
  // nehali dobivati napovedna obvestila.
  const vasZaSub = (s) => (NOWCAST_VASI.some(v => v.id === s.vas) ? s.vas : NOWCAST_VASI[0].id);
  const vasiZNarocniki = new Set(subs.map(vasZaSub));
  if (!vasiZNarocniki.size) return true;              // radar deluje, le nihče ni naročen

  let state = {}; try { const o = await r2.get("push/radar_state.json"); state = o ? JSON.parse(await o.text()) : {}; } catch (_) {}
  const now = Date.now();
  let changed = false;

  for (const v of nc.vasi) {
    if (!vasiZNarocniki.has(v.id)) continue;
    const vas = NOWCAST_VASI.find(x => x.id === v.id);
    // Najresnejši dogodek najprej — o isti celici ne pošiljamo dveh obvestil.
    // Vsakič zahtevamo, da dogodek še ni v teku: opozorilo o toči, ki že pada,
    // je le nadloga.
    let key = null, body = null;
    // Vse stavke gradimo z mestnikom (`loc`), ker se le ta ujema z vsemi
    // imeni na seznamu — "se približuje Mozirju" bi zahtevalo še dajalnik.
    if (v.toca && v.zdaj < RADAR_L_CORE) {
      key = "toca";
      body = "🧊 Možnost toče " + vas.loc + ": močno jedro prihaja čez ~" + v.jedro + " min. Radar toče od močnega naliva ne loči zanesljivo — pripravi se, a ne paniči.";
    } else if (v.nevihta != null && v.zdaj < RADAR_L_STORM) {
      key = "nevihta";
      body = "⛈️ Nevihta " + vas.loc + " čez ~" + v.nevihta + " min.";
    } else if (v.dez != null && v.zdaj < RADAR_L_RAIN) {
      key = "dez";
      body = "🌧️ Dež " + vas.loc + " čez ~" + v.dez + " min.";
    }
    if (!key) continue;
    const sKey = v.id + ":" + key;
    const st = state[sKey] || { lastSent: 0 };
    if (now - (st.lastSent || 0) < RADAR_COOLDOWN_MS) continue;
    await _pushAll(env, {
      title: "Meteorec — " + vas.name,
      body, url: "/", tag: "wx-nc-" + v.id + "-" + key,
    }, s => vasZaSub(s) === v.id);
    state[sKey] = { lastSent: now };
    changed = true;
  }
  if (changed) await r2.put("push/radar_state.json", JSON.stringify(state), { httpMetadata: { contentType: "application/json" } });
  return true;
}

// ═══════════════════════════════════════════════════════════
//  Lasten kompozit padavin nad Slovenijo in širšo okolico
// ═══════════════════════════════════════════════════════════
// Nobeden od virov sam ne zadošča, zato ju sestavimo:
//   jedro  — ARSO si0-rm-anim.gif: ~0,5 km in 5 minut, a takoj čez mejo slep;
//   obroč  — EUMETNET OPERA (produkt CIRRUS, največja odbojnost DBZH):
//            1 km, 5 minut, vsa Evropa, CC BY 4.0 in brez prijave.
//
// Georeferenco obeh smo preverili navzkrižno na dežju 1. 8. 2026: polji
// padavin se ujameta celico za celico, preostali zamik je pod 1 km in ga
// pojasnita zaokroževanje na mrežo ter to, da posnetka nista z iste minute.
//
// OPERA GeoTIFF je tlakovan, zato z zahtevkom Range preberemo samo štiri
// ploščice nad našim oknom — ~115 KB namesto 2,7 MB cele datoteke.
const OPERA_S3 = "https://s3.waw3-1.cloudferro.com/openradar-24h";
const OPERA_MAX_AGE_MIN = 30;

// Izsek, ki ga rišemo: Slovenija s celotnim alpsko-jadranskim zaledjem.
// Dva izseka. Široki pokriva alpsko-jadransko zaledje, ozki pa dolino, kjer
// stoji postaja: ta je v celoti znotraj 120 km od Lisce in Pasje ravni, torej
// je čisto ARSO jedro. Ker ga rišemo trikrat finejše od izvornih 0,5 km, ga
// vzorčimo gladko — pri širokem to ne pride v poštev, ker je izris tam
// praktično 1 : 1 z virom in bi glajenje detajl le razmazalo.
const COMP_VIEWS = {
  sirok: {
    lon0: 11.5, lon1: 17.8, lat0: 44.4, lat1: 47.9, w: 1024,
    ime: "Slovenija in širša okolica", gladkoArso: false,
  },
  savinja: {
    lon0: 14.25, lon1: 15.55, lat0: 46.0, lat1: 46.65, w: 640,
    ime: "Zgornja Savinjska dolina", gladkoArso: true,
  },
};
const COMP_VIEW_DEFAULT = "sirok";

// Lambertova azimutalna ploskovno enaka projekcija mreže OPERA (iz GeoTIFF-a).
const LAEA = { lat0: 55, lon0: 10, fe: 1950000, fn: -2100000, a: 6378137, f: 1 / 298.257223563 };

// Naša lestvica v mm/h. Prve stopnje so polprosojne, da šibka polja ne
// prekrijejo zemljevida pod seboj.
const COMP_MMH = [0.1, 0.2, 0.5, 1, 2, 3, 5, 8, 12, 20, 30, 50, 80, 120];
const COMP_RGB = [
  [90, 150, 255], [50, 120, 255], [0, 90, 235], [0, 160, 230], [0, 200, 180],
  [40, 205, 70], [130, 220, 0], [210, 230, 0], [255, 200, 0], [255, 150, 0],
  [255, 90, 0], [225, 20, 20], [175, 0, 60], [190, 0, 190],
];
const COMP_ALPHA = [110, 150, 190, 225, 245, 255, 255, 255, 255, 255, 255, 255, 255, 255];

// Naša radarja in doseg, znotraj katerega ima ARSO prednost pred OPERA.
const COMP_SI_RADARJI = [[46.068, 15.285], [46.099, 14.234]];  // Lisca, Pasja ravan
const COMP_R_JEDRO = 120, COMP_R_ROB = 170;                    // km
const COMP_KM_LAT = 111.32, COMP_KM_LON = 77.2;                // 1° pri ~46,2 °N

// Barvna lestvica zgoraj je lestvica *legende*. Za izris jo podrobimo, ker
// ima obroč zvezne vrednosti in bi ga 14 stopenj razrezalo v vidne pasove.
// Paletni PNG prenese 256 vnosov, zato je to zastonj.
const COMP_SUB = 3;
const _COMP_SCALE = (() => {
  const mmh = [], rgb = [], alpha = [];
  for (let i = 0; i < COMP_MMH.length; i++) {
    const m0 = COMP_MMH[i], m1 = i + 1 < COMP_MMH.length ? COMP_MMH[i + 1] : COMP_MMH[i] * 1.5;
    const c0 = COMP_RGB[i], c1 = i + 1 < COMP_RGB.length ? COMP_RGB[i + 1] : COMP_RGB[i];
    const a0 = COMP_ALPHA[i], a1 = i + 1 < COMP_ALPHA.length ? COMP_ALPHA[i + 1] : COMP_ALPHA[i];
    for (let k = 0; k < COMP_SUB; k++) {
      const t = k / COMP_SUB;
      mmh.push(m0 * Math.pow(m1 / m0, t));                       // geometrično, kot je lestvica
      rgb.push(c0.map((v, j) => Math.round(v + (c1[j] - v) * t)));
      alpha.push(Math.round(a0 + (a1 - a0) * t));
    }
  }
  return { mmh, rgb, alpha };
})();

// ── Projekcije ─────────────────────────────────────────────
// Avtalična širina zahteva logaritem, zato jo računamo enkrat na vrstico.
const _LAEA = (() => {
  const e2 = LAEA.f * (2 - LAEA.f), e = Math.sqrt(e2);
  const q = (p) => { const s = Math.sin(p); return (1 - e2) * (s / (1 - e2 * s * s) - (1 / (2 * e)) * Math.log((1 - e * s) / (1 + e * s))); };
  const p0 = LAEA.lat0 * Math.PI / 180, qp = q(Math.PI / 2);
  const b0 = Math.asin(q(p0) / qp), Rq = LAEA.a * Math.sqrt(qp / 2);
  const m0 = Math.cos(p0) / Math.sqrt(1 - e2 * Math.sin(p0) ** 2);
  return { q, qp, Rq, D: LAEA.a * m0 / (Rq * Math.cos(b0)), sinb0: Math.sin(b0), cosb0: Math.cos(b0) };
})();

function _laeaXY(lat, lon) {
  const b = Math.asin(_LAEA.q(lat * Math.PI / 180) / _LAEA.qp), dl = (lon - LAEA.lon0) * Math.PI / 180;
  const sb = Math.sin(b), cb = Math.cos(b), sd = Math.sin(dl), cd = Math.cos(dl);
  const B = _LAEA.Rq * Math.sqrt(2 / (1 + _LAEA.sinb0 * sb + _LAEA.cosb0 * cb * cd));
  return [B * _LAEA.D * cb * sd + LAEA.fe, (B / _LAEA.D) * (_LAEA.cosb0 * sb - _LAEA.sinb0 * cb * cd) + LAEA.fn];
}

// Sliko rišemo v Web Mercatorju, ker jo Leaflet prek L.imageOverlay položi
// na pravokotnik v prav tej projekciji; enakopravokotna slika bi se raztegnila.
const _mercY = (lat) => Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));
const _mercLat = (y) => (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI;

// ── Bralnik tlakovanega GeoTIFF-a ──────────────────────────
function _tiffIFD(buf) {
  const dv = new DataView(buf);
  if (dv.getUint8(0) !== 0x49 || dv.getUint8(1) !== 0x49) throw new Error("TIFF ni little-endian");
  const ifd = dv.getUint32(4, true), n = dv.getUint16(ifd, true), t = {};
  for (let i = 0; i < n; i++) {
    const o = ifd + 2 + i * 12;
    const tag = dv.getUint16(o, true), typ = dv.getUint16(o + 2, true), cnt = dv.getUint32(o + 4, true);
    const sz = { 3: 2, 4: 4, 12: 8 }[typ];
    if (!sz) continue;
    const at = sz * cnt <= 4 ? o + 8 : dv.getUint32(o + 8, true);
    const v = new Array(cnt);
    for (let k = 0; k < cnt; k++) {
      v[k] = typ === 3 ? dv.getUint16(at + k * 2, true)
           : typ === 4 ? dv.getUint32(at + k * 4, true)
           : dv.getFloat64(at + k * 8, true);
    }
    t[tag] = v;
  }
  return {
    w: t[256][0], h: t[257][0], tw: t[322][0], th: t[323][0], spp: t[277][0],
    offs: t[324], lens: t[325],
    px: t[33550][0], py: t[33550][1], ox: t[33922][3], oy: t[33922][4],
  };
}

async function _inflate(bytes) {
  const ds = new DecompressionStream("deflate");
  const w = ds.writable.getWriter(); w.write(bytes); w.close();
  return new Uint8Array(await new Response(ds.readable).arrayBuffer());
}

// Ključi so OPERA@YYYYMMDDThhmm@0@DBZH.tiff; posnetek pride ~6 minut po
// terminu, zato ob prehodu ure pogledamo tudi prejšnjo.
function _operaPrefix(d) {
  const p = (n) => String(n).padStart(2, "0");
  const Y = d.getUTCFullYear(), M = p(d.getUTCMonth() + 1), D = p(d.getUTCDate());
  return `${Y}/${M}/${D}/OPERA/COMP/OPERA@${Y}${M}${D}T${p(d.getUTCHours())}`;
}

// Ključi zadnjih dveh ur, urejeni od najstarejšega. Dve uri, ker mora seznam
// pokriti celotno animacijo tudi tik po prehodu polne ure.
async function _operaKeys() {
  const out = [];
  for (const back of [3600e3, 0]) {
    try {
      const pfx = _operaPrefix(new Date(Date.now() - back));
      const r = await fetch(`${OPERA_S3}?list-type=2&prefix=${encodeURIComponent(pfx)}&max-keys=200`, { cf: { cacheTtl: 60 } });
      if (!r.ok) continue;
      out.push(...[...(await r.text()).matchAll(/<Key>([^<]+@DBZH\.tiff)<\/Key>/g)].map(m => m[1]));
    } catch (_) {}
  }
  return out.sort();
}

async function _operaLatestKey() {
  const keys = await _operaKeys();
  return keys.length ? keys[keys.length - 1] : null;
}

// Ključ posnetka po časovnem žigu — brez seznama, saj je pot znana.
function _operaKeyForStamp(stamp) {
  const m = stamp.match(/^(\d{4})(\d{2})(\d{2})T(\d{4})$/);
  if (!m) return null;
  return `${m[1]}/${m[2]}/${m[3]}/OPERA/COMP/OPERA@${stamp}@0@DBZH.tiff`;
}

const _compStamp = (key) => (key.match(/@(\d{8}T\d{4})@/) || [])[1] || null;
function _compStampMs(stamp) {
  const m = stamp.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})$/);
  return m ? Date.parse(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:00Z`) : NaN;
}
function _msToStamp(ms) {
  const d = new Date(ms), p = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}T${p(d.getUTCHours())}${p(d.getUTCMinutes())}`;
}

// OPERA včasih obstane za več ur (zunanji vir, CloudFerro S3), ARSO pa teče
// naprej — brez tega bi seznam okvirjev ostal prazen in bi frontend javil
// "Radar ni dosegljiv", čeprav je slovenski kompozit povsem v redu. Vrne
// samo čas zadnjega ARSO okvirja (poravnan na 5-minutno mrežo); sam izris
// tudi brez OPERA že zna narisati samo ARSO jedro (glej _radarComposite).
async function _arsoLatestMs() {
  try {
    const ctrl = new AbortController(); const tid = setTimeout(() => ctrl.abort(), 8000);
    let res = await fetch(RADAR_URL, { method: "HEAD", signal: ctrl.signal, cf: { cacheTtl: 60 } }).finally(() => clearTimeout(tid));
    if (res.status === 405 || res.status === 501) {
      const ctrl2 = new AbortController(); const tid2 = setTimeout(() => ctrl2.abort(), 8000);
      res = await fetch(RADAR_URL, { signal: ctrl2.signal, cf: { cacheTtl: 60 } }).finally(() => clearTimeout(tid2));
    }
    if (!res.ok) return null;
    const lm = res.headers.get("last-modified");
    if (!lm) return null;
    const lmMs = new Date(lm).getTime();
    if (Number.isNaN(lmMs) || (Date.now() - lmMs) / 60000 > RADAR_MAX_AGE_MIN) return null;
    return Math.floor(lmMs / ARSO_STEP_MS) * ARSO_STEP_MS;
  } catch (_) { return null; }
}

// Preberi samo ploščice, ki pokrivajo dano okno v koordinatah mreže.
async function _operaWindow(key, bbox) {
  const url = `${OPERA_S3}/${key}`;
  const head = await fetch(url, { headers: { Range: "bytes=0-16383" }, cf: { cacheTtl: 300 } });
  if (!head.ok) throw new Error("OPERA glava HTTP " + head.status);
  const hdr = _tiffIFD(await head.arrayBuffer());

  const c0 = Math.max(0, Math.floor((bbox.x0 - hdr.ox) / hdr.px));
  const c1 = Math.min(hdr.w - 1, Math.ceil((bbox.x1 - hdr.ox) / hdr.px));
  const r0 = Math.max(0, Math.floor((hdr.oy - bbox.y1) / hdr.py));
  const r1 = Math.min(hdr.h - 1, Math.ceil((hdr.oy - bbox.y0) / hdr.py));
  const ow = c1 - c0 + 1, oh = r1 - r0 + 1;
  const data = new Float32Array(ow * oh).fill(NaN);
  const tx = Math.ceil(hdr.w / hdr.tw);

  const jobs = [];
  for (let tr = Math.floor(r0 / hdr.th); tr <= Math.floor(r1 / hdr.th); tr++) {
    for (let tc = Math.floor(c0 / hdr.tw); tc <= Math.floor(c1 / hdr.tw); tc++) {
      const i = tr * tx + tc;
      jobs.push((async () => {
        const res = await fetch(url, { headers: { Range: `bytes=${hdr.offs[i]}-${hdr.offs[i] + hdr.lens[i] - 1}` }, cf: { cacheTtl: 300 } });
        if (!res.ok) return;
        const raw = await _inflate(new Uint8Array(await res.arrayBuffer()));
        const f = new Float32Array(raw.buffer, raw.byteOffset, Math.floor(raw.byteLength / 4));
        for (let y = 0; y < hdr.th; y++) {
          const gy = tr * hdr.th + y;
          if (gy < r0 || gy > r1) continue;
          for (let x = 0; x < hdr.tw; x++) {
            const gx = tc * hdr.tw + x;
            if (gx < c0 || gx > c1) continue;
            data[(gy - r0) * ow + (gx - c0)] = f[(y * hdr.tw + x) * hdr.spp];
          }
        }
      })());
    }
  }
  await Promise.all(jobs);
  return { data, w: ow, h: oh, c0, r0, ox: hdr.ox, oy: hdr.oy, px: hdr.px, py: hdr.py };
}

// ── Zapis indeksiranega PNG ────────────────────────────────
// Paletni PNG je za radarsko sliko nekajkrat manjši od RGBA, ker so velike
// ploskve enake barve; risalnika v Workerju tako ali tako ni.
const _CRC_T = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function _crc32(b) { let c = 0xffffffff; for (let i = 0; i < b.length; i++) c = _CRC_T[(c ^ b[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }

function _pngChunk(type, data) {
  const out = new Uint8Array(12 + data.length), dv = new DataView(out.buffer);
  dv.setUint32(0, data.length);
  for (let i = 0; i < 4; i++) out[4 + i] = type.charCodeAt(i);
  out.set(data, 8);
  dv.setUint32(8 + data.length, _crc32(out.subarray(4, 8 + data.length)));
  return out;
}

async function _pngIndexed(idx, w, h, rgb, alpha) {
  const raw = new Uint8Array((w + 1) * h);
  for (let y = 0; y < h; y++) raw.set(idx.subarray(y * w, (y + 1) * w), y * (w + 1) + 1);  // filter 0
  const cs = new CompressionStream("deflate");
  const wr = cs.writable.getWriter(); wr.write(raw); wr.close();
  const z = new Uint8Array(await new Response(cs.readable).arrayBuffer());

  const ihdr = new Uint8Array(13), dv = new DataView(ihdr.buffer);
  dv.setUint32(0, w); dv.setUint32(4, h);
  ihdr[8] = 8; ihdr[9] = 3;                       // 8 bitov, paleta
  const plte = new Uint8Array(rgb.length * 3);
  rgb.forEach((c, i) => plte.set(c, i * 3));

  const parts = [
    new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]),
    _pngChunk("IHDR", ihdr), _pngChunk("PLTE", plte),
    _pngChunk("tRNS", new Uint8Array(alpha)),
    _pngChunk("IDAT", z), _pngChunk("IEND", new Uint8Array(0)),
  ];
  const png = new Uint8Array(parts.reduce((s, p) => s + p.length, 0));
  let o = 0; for (const p of parts) { png.set(p, o); o += p.length; }
  return png;
}

// ── Sestavljanje ───────────────────────────────────────────
// Iz ARSO animacije (90 minut, korak 5 minut) vzamemo okvir, ki časovno
// pripada danemu posnetku OPERA, in ne kar zadnjega — sicer bi bilo jedro
// animacije za uro nazaj povsod isto in bi se razhajalo z obročem.
//
// Nacionalni kompozit je hitrejši od evropskega: najnovejši ARSO okvir je
// tipično 5–10 minut pred najnovejšim posnetkom OPERA. Izmerjeno na dveh
// vremenskih situacijah 1. 8. 2026 z navzkrižno korelacijo mask padavin —
// zamik po tej formuli ostane pod pol okvirja (~1 km pri običajni hitrosti
// celic), medtem ko bi parjenje "najnovejši z najnovejšim" zgrešilo za 3 km.
const ARSO_STEP_MS = 5 * 60000;
async function _compArso(stampMs) {
  try {
    const ctrl = new AbortController(); const tid = setTimeout(() => ctrl.abort(), 12000);
    const res = await fetch(RADAR_URL, { signal: ctrl.signal, cf: { cacheTtl: 60 } }).finally(() => clearTimeout(tid));
    if (!res.ok) return null;
    const lm = res.headers.get("last-modified");
    const lmMs = lm ? new Date(lm).getTime() : Date.now();
    if ((Date.now() - lmMs) / 60000 > RADAR_MAX_AGE_MIN) return null;   // animacija stoji
    const g = _gifDecodeFrames(new Uint8Array(await res.arrayBuffer()));
    if (!g.palette || !g.frames.length) return null;
    const frames = _radDistinct(g.frames, g.width);
    if (!frames.length) return null;

    const newestMs = Math.floor(lmMs / ARSO_STEP_MS) * ARSO_STEP_MS;
    const k = Math.round((newestMs - stampMs) / ARSO_STEP_MS);
    const i = frames.length - 1 - k;
    if (i < 0 || i >= frames.length) return null;      // zunaj 90-minutne animacije
    return { levels: _radLevels(frames[i], _radLut(g.palette), g.width), w: g.width, h: g.height, zamikMin: k * 5 };
  } catch (_) { return null; }
}

function _compLevel(mmh) {
  const s = _COMP_SCALE.mmh;
  let L = 0;
  for (let i = 0; i < s.length; i++) if (mmh >= s[i]) L = i + 1;
  return L;
}

// Odbojnost v mm/h. NaN pomeni izmerjeno brez padavin, vrednost pod -1e5
// pa da radar tja ne vidi — to dvoje je treba ločiti, sicer bi luknje v
// pokritju zgladili v suho.
const _dbzMmh = (v) => Number.isNaN(v) ? 0 : Math.pow(Math.pow(10, v / 10) / 200, 1 / 1.6);

// Dvolinearno vzorčenje obroča. Mreža OPERA je 1 km, izris pa pol tega, zato
// najbližji sosed nariše vidne kvadratke; glajenje ne doda podatka, odstrani
// pa stopnice. Če je katerikoli od štirih sosedov zunaj pokritja, se vrnemo
// na najbližjega — drugače bi rob pokritja razmazali v padavine.
function _operaSample(win, fx, fy) {
  const x0 = Math.floor(fx), y0 = Math.floor(fy);
  const x1 = x0 + 1, y1 = y0 + 1;
  if (x0 < 0 || y0 < 0 || x1 >= win.w || y1 >= win.h) {
    const cx = Math.round(fx), cy = Math.round(fy);
    if (cx < 0 || cy < 0 || cx >= win.w || cy >= win.h) return -1;
    const v = win.data[cy * win.w + cx];
    return v < -1e5 ? -1 : _dbzMmh(v);
  }
  const a = win.data[y0 * win.w + x0], b = win.data[y0 * win.w + x1];
  const c = win.data[y1 * win.w + x0], d = win.data[y1 * win.w + x1];
  if (a < -1e5 || b < -1e5 || c < -1e5 || d < -1e5) {
    const v = win.data[Math.round(fy) * win.w + Math.round(fx)];
    return v < -1e5 ? -1 : _dbzMmh(v);
  }
  const tx = fx - x0, ty = fy - y0;
  return (_dbzMmh(a) * (1 - tx) + _dbzMmh(b) * tx) * (1 - ty)
       + (_dbzMmh(c) * (1 - tx) + _dbzMmh(d) * tx) * ty;
}

// Vzorčenje ARSO jedra. Pri gladkem načinu interpoliramo v mm/h in ne po
// stopnjah, ker je lestvica geometrijska in bi vmesne stopnje sicer preskakovale.
function _arsoSample(arso, fx, fy, gladko) {
  const g = (x, y) => { const L = arso.levels[y * arso.w + x]; return L ? RADAR_LEVEL_MMH[L - 1] : 0; };
  const x0 = Math.floor(fx), y0 = Math.floor(fy);
  if (!gladko || x0 < 0 || y0 < 0 || x0 + 1 >= arso.w || y0 + 1 >= arso.h) {
    const x = Math.round(fx), y = Math.round(fy);
    return (x < 0 || y < 0 || x >= arso.w || y >= arso.h) ? null : g(x, y);
  }
  const tx = fx - x0, ty = fy - y0;
  return (g(x0, y0) * (1 - tx) + g(x0 + 1, y0) * tx) * (1 - ty)
       + (g(x0, y0 + 1) * (1 - tx) + g(x0 + 1, y0 + 1) * tx) * ty;
}

// Okno v koordinatah mreže: projekcija ni poravnana z mrežo poldnevnikov,
// zato robove okna vzorčimo in vzamemo očrtani pravokotnik. Izluščeno iz
// _radarComposite, da si ga lahko izposodi tudi cron, kadar mora OPERA/ARSO
// prenesti vnaprej (glej _cronRenderRadarComposite).
function _compBBox(V) {
  const bb = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
  for (let i = 0; i <= 40; i++) {
    const t = i / 40;
    const la = V.lat0 + (V.lat1 - V.lat0) * t, lo = V.lon0 + (V.lon1 - V.lon0) * t;
    for (const [a, b] of [[la, V.lon0], [la, V.lon1], [V.lat0, lo], [V.lat1, lo]]) {
      const [x, y] = _laeaXY(a, b);
      bb.x0 = Math.min(bb.x0, x); bb.x1 = Math.max(bb.x1, x);
      bb.y0 = Math.min(bb.y0, y); bb.y1 = Math.max(bb.y1, y);
    }
  }
  return bb;
}

// Vrne PNG in podatke o obeh virih. Če OPERA odpove, narišemo samo ARSO
// jedro — nepopolna slika je še vedno boljša od napake. `sources`, če
// podan, je že prenesen [win, arso] par (deli ga s sledenjem nevihtnim
// celicam, da se za isti "sirok" izris ne prenese dvakrat).
async function _radarComposite(key, stampMs, view, sources) {
  const V = view || COMP_VIEWS[COMP_VIEW_DEFAULT];
  const W = V.w;
  const H = Math.round(W * (_mercY(V.lat1) - _mercY(V.lat0)) / ((V.lon1 - V.lon0) * Math.PI / 180));
  const y0 = _mercY(V.lat1), y1 = _mercY(V.lat0);

  const [win, arso] = sources || await Promise.all([
    _operaWindow(key, _compBBox(V)).catch(() => null),
    _compArso(stampMs),
  ]);
  if (!win && !arso) throw new Error("noben radarski vir ni dosegljiv");

  const idx = new Uint8Array(W * H);
  const NODATA = _COMP_SCALE.rgb.length + 1;
  const R2_JEDRO = COMP_R_JEDRO * COMP_R_JEDRO, R2_ROB = COMP_R_ROB * COMP_R_ROB;

  // Kar je odvisno samo od stolpca, izračunamo vnaprej — sicer bi sinus in
  // kosinus tekla stotisočkrat.
  const sinDl = new Float64Array(W), cosDl = new Float64Array(W);
  const arsoX = new Float64Array(W), dxKm = new Float64Array(W * COMP_SI_RADARJI.length);
  for (let x = 0; x < W; x++) {
    const lo = V.lon0 + (V.lon1 - V.lon0) * (x + 0.5) / W;
    const dl = (lo - LAEA.lon0) * Math.PI / 180;
    sinDl[x] = Math.sin(dl); cosDl[x] = Math.cos(dl);
    arsoX[x] = RAD_AX * lo + RAD_BX;
    COMP_SI_RADARJI.forEach(([, rlo], k) => { dxKm[k * W + x] = (lo - rlo) * COMP_KM_LON; });
  }

  let nBlind = 0;
  for (let y = 0; y < H; y++) {
    const la = _mercLat(y0 - (y0 - y1) * (y + 0.5) / H);
    const b = Math.asin(_LAEA.q(la * Math.PI / 180) / _LAEA.qp), sb = Math.sin(b), cb = Math.cos(b);
    const arsoY = RAD_AY * la + RAD_BY;
    const dyKm = COMP_SI_RADARJI.map(([rla]) => (la - rla) * COMP_KM_LAT);
    const row = y * W;

    for (let x = 0; x < W; x++) {
      let mmh = -1;                                  // -1 = nihče ne vidi

      if (win) {
        const B = _LAEA.Rq * Math.sqrt(2 / (1 + _LAEA.sinb0 * sb + _LAEA.cosb0 * cb * cosDl[x]));
        const fx = ((B * _LAEA.D * cb * sinDl[x] + LAEA.fe) - win.ox) / win.px - win.c0;
        const fy = (win.oy - ((B / _LAEA.D) * (_LAEA.cosb0 * sb - _LAEA.sinb0 * cb * cosDl[x]) + LAEA.fn)) / win.py - win.r0;
        mmh = _operaSample(win, fx, fy);             // Marshall-Palmer je v _dbzMmh
      }

      if (arso) {
        let d2 = Infinity;
        for (let k = 0; k < COMP_SI_RADARJI.length; k++) {
          const dx = dxKm[k * W + x], dy = dyKm[k];
          const s = dx * dx + dy * dy;
          if (s < d2) d2 = s;
        }
        if (d2 < R2_ROB) {
          const a = _arsoSample(arso, arsoX[x], arsoY, V.gladkoArso);
          // Znotraj dosega naših radarjev ima ARSO prednost (štirikrat boljša
          // ločljivost istih meritev), v prehodnem pasu vzamemo močnejšega od
          // obeh, da na šivu ne nastane luknja.
          if (a != null) {
            if (d2 <= R2_JEDRO) mmh = a;
            else mmh = Math.max(mmh, a);
          }
        }
      }

      if (mmh < 0) { idx[row + x] = NODATA; nBlind++; }
      else idx[row + x] = _compLevel(mmh);
    }
  }

  const png = await _pngIndexed(idx, W, H,
    [[0, 0, 0], ..._COMP_SCALE.rgb, [120, 125, 135]],
    [0, ..._COMP_SCALE.alpha, 45]);
  return { png, w: W, h: H, opera: !!win, arso: !!arso, brezPodatkov: nBlind / (W * H) };
}

// Vsak izrisan okvir hranimo v R2 pod svojim ključem, ker jih animacija
// potrebuje več hkrati. Za uro nazaj je to ~13 slik po 20 KB; starejše
// pobriše _radarCompositePrune. Brez R2 se slika izriše ob vsakem zahtevku.
const COMP_R2_PREFIX = "radar/comp-";
const COMP_ANIM_MIN = 60;                       // dolžina animacije
const COMP_KEEP_MS = (COMP_ANIM_MIN + 20) * 60000;

async function _radarCompositeCached(env, stamp, viewId, sources) {
  const r2 = env?.PHOTOS_R2;
  const vid = COMP_VIEWS[viewId] ? viewId : COMP_VIEW_DEFAULT;
  if (!stamp) {
    const key = await _operaLatestKey();
    stamp = key ? _compStamp(key) : null;
    if (!stamp) {
      const arsoMs = await _arsoLatestMs();
      stamp = arsoMs ? _msToStamp(arsoMs) : null;
    }
    if (!stamp) throw new Error("noben radarski vir ni dosegljiv");
  }
  const r2key = `${COMP_R2_PREFIX}${vid}-${stamp}.png`;

  if (r2) {
    try {
      const o = await r2.get(r2key);
      if (o) return { body: await o.arrayBuffer(), stamp, meta: o.customMetadata || {}, cached: true };
    } catch (_) {}
  }

  const key = _operaKeyForStamp(stamp);
  if (!key) throw new Error("neveljaven časovni žig");
  const c = await _radarComposite(key, _compStampMs(stamp), COMP_VIEWS[vid], sources);
  const meta = {
    stamp, pogled: vid,
    opera: String(c.opera), arso: String(c.arso),
    brezPodatkov: c.brezPodatkov.toFixed(4),
    w: String(c.w), h: String(c.h),
  };
  if (r2) {
    try {
      await r2.put(r2key, c.png, { httpMetadata: { contentType: "image/png" }, customMetadata: meta });
    } catch (_) {}
  }
  return { body: c.png, stamp, meta, cached: false };
}

// Pobriši izrise, ki so padli iz animacije. Teče iz crona, da zahtevki po
// slikah ne plačujejo naštevanja vedra.
async function _radarCompositePrune(env) {
  const r2 = env?.PHOTOS_R2; if (!r2) return 0;
  const cutoff = Date.now() - COMP_KEEP_MS;
  let n = 0;
  try {
    const list = await r2.list({ prefix: COMP_R2_PREFIX, limit: 200 });
    for (const o of list.objects || []) {
      // Ključ je comp-<pogled>-<žig>.png; brez imena pogleda so ostanki
      // prejšnje sheme in gredo prav tako proč.
      const s = (o.key.match(/comp-[a-z]+-(\d{8}T\d{4})\.png$/) || [])[1];
      const ms = s ? _compStampMs(s) : NaN;
      if (Number.isNaN(ms) || ms < cutoff) { await r2.delete(o.key); n++; }
    }
  } catch (_) {}
  return n;
}

// ── ICON kratkoročna napoved (nadaljevanje radarske časovnice) ─────
// AROME (Météo-France) prek Open-Meteo ne pokriva Slovenije — preverjeno:
// meteofrance_arome_france_hd in _france oba vrneta prazno/napako za
// Rečico (150+ km od francoske meje). ICON (DWD, ~2 km) jo pokriva, zato
// po zadnji uri radarja nadaljuje isto animacijo s 6 urami napovedi, samo
// na pogledu "savinja". Open-Meteo nima gotove mreže — samo točkovni API —
// zato vzorčimo grobo mrežo točk v enem batch klicu (vejico ločeni
// latitude/longitude) in izrišemo enako kot kompozitni radar (ista paleta,
// isti PNG izpis), da je prehod iz radarja v napoved viden kot en trak.
const ICON_MODEL = "icon_d2";
const ICON_MODEL_FALLBACK = "icon_eu";
const ICON_HOURS = 6;
const ICON_GRID_NX = 8, ICON_GRID_NY = 6;   // 48 točk; en batch klic na urni tek
const ICON_GRID_INSET = 0.05;               // rahlo znotraj robov, brez ekstrapolacije
const ICON_R2_PREFIX = "icon/";

function _iconGrid(V) {
  const pts = [];
  for (let j = 0; j < ICON_GRID_NY; j++) {
    const lat = V.lat0 + (V.lat1 - V.lat0) * (ICON_GRID_INSET + (1 - 2 * ICON_GRID_INSET) * j / (ICON_GRID_NY - 1));
    for (let i = 0; i < ICON_GRID_NX; i++) {
      const lon = V.lon0 + (V.lon1 - V.lon0) * (ICON_GRID_INSET + (1 - 2 * ICON_GRID_INSET) * i / (ICON_GRID_NX - 1));
      pts.push([lon, lat]);
    }
  }
  return pts;
}

async function _iconFetchModel(pts, model) {
  const lats = pts.map((p) => p[1].toFixed(4)).join(",");
  const lons = pts.map((p) => p[0].toFixed(4)).join(",");
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lats}&longitude=${lons}`
    + `&hourly=precipitation&forecast_hours=${ICON_HOURS}&models=${model}&timezone=UTC`;
  let data;
  try {
    const ctrl = new AbortController(); const tid = setTimeout(() => ctrl.abort(), 15000);
    const res = await fetch(url, { signal: ctrl.signal }).finally(() => clearTimeout(tid));
    if (!res.ok) return null;
    data = await res.json();
  } catch (_) { return null; }
  const list = Array.isArray(data) ? data : [data];
  if (!list.length || list.every((d) => !d || d.error)) return null;
  // Vsako vrnjeno točko ujemi nazaj po njenih lastnih latitude/longitude
  // poljih, ne po vrstnem redu — Open-Meteo vrstnega reda znotraj batch
  // zahtevka ne dokumentira, poceni je biti defenziven.
  const out = pts.map(([lon, lat]) => {
    let best = null, bd = Infinity;
    for (const d of list) {
      if (!d || d.error || !d.hourly?.precipitation) continue;
      const dd = (d.latitude - lat) ** 2 + (d.longitude - lon) ** 2;
      if (dd < bd) { bd = dd; best = d; }
    }
    return best ? { lon, lat, precip: best.hourly.precipitation } : null;
  });
  return out.some((o) => o) ? out : null;
}

async function _iconFetch(V) {
  const pts = _iconGrid(V);
  return (await _iconFetchModel(pts, ICON_MODEL).catch(() => null))
    || (await _iconFetchModel(pts, ICON_MODEL_FALLBACK).catch(() => null));
}

// Dvolinearno vzorčenje grobe ICON mreže (enakomerna v lon/lat, torej brez
// LAEA/Mercator popravkov) — v slogu _arsoSample-a. Manjkajoče sosede
// nadomesti z najbližjim znanim, da rob mreže ne razmaže v ničlo.
function _iconSampleAt(grid, nx, ny, fx, fy, hourIdx) {
  const g = (gx, gy) => {
    const p = grid[gy * nx + gx];
    const v = p ? p.precip[hourIdx] : null;
    return v == null ? null : v;
  };
  const x0 = Math.max(0, Math.min(nx - 1, Math.floor(fx))), y0 = Math.max(0, Math.min(ny - 1, Math.floor(fy)));
  const x1 = Math.max(0, Math.min(nx - 1, x0 + 1)), y1 = Math.max(0, Math.min(ny - 1, y0 + 1));
  const a = g(x0, y0), b = g(x1, y0), c = g(x0, y1), d = g(x1, y1);
  if (a == null && b == null && c == null && d == null) return null;
  const av = a ?? b ?? c ?? d, bv = b ?? a ?? d ?? c, cv = c ?? d ?? a ?? b, dv = d ?? c ?? b ?? a;
  const tx = Math.max(0, Math.min(1, fx - x0)), ty = Math.max(0, Math.min(1, fy - y0));
  return (av * (1 - tx) + bv * tx) * (1 - ty) + (cv * (1 - tx) + dv * tx) * ty;
}

async function _iconFrame(grid, V, hourIdx) {
  const W = V.w;
  const H = Math.round(W * (_mercY(V.lat1) - _mercY(V.lat0)) / ((V.lon1 - V.lon0) * Math.PI / 180));
  const y0m = _mercY(V.lat1), y1m = _mercY(V.lat0);
  const idx = new Uint8Array(W * H);
  const NODATA = _COMP_SCALE.rgb.length + 1;
  const lonMin = V.lon0 + (V.lon1 - V.lon0) * ICON_GRID_INSET, lonSpan = (V.lon1 - V.lon0) * (1 - 2 * ICON_GRID_INSET);
  const latMin = V.lat0 + (V.lat1 - V.lat0) * ICON_GRID_INSET, latSpan = (V.lat1 - V.lat0) * (1 - 2 * ICON_GRID_INSET);
  for (let y = 0; y < H; y++) {
    const la = _mercLat(y0m - (y0m - y1m) * (y + 0.5) / H);
    const fy = ((la - latMin) / latSpan) * (ICON_GRID_NY - 1);
    const row = y * W;
    for (let x = 0; x < W; x++) {
      const lo = V.lon0 + (V.lon1 - V.lon0) * (x + 0.5) / W;
      const fx = ((lo - lonMin) / lonSpan) * (ICON_GRID_NX - 1);
      const mmh = _iconSampleAt(grid, ICON_GRID_NX, ICON_GRID_NY, fx, fy, hourIdx);
      idx[row + x] = mmh == null ? NODATA : _compLevel(mmh);
    }
  }
  return _pngIndexed(idx, W, H, [[0, 0, 0], ..._COMP_SCALE.rgb, [120, 125, 135]], [0, ..._COMP_SCALE.alpha, 45]);
}

// Uro zaokroženo v UTC — Open-Meteo objavlja nov ICON-D2 tek nekajkrat
// dnevno, worker pa nima zanesljivega vpogleda v urnik teka, zato je "urno
// osveževanje" doseženo posredno: manifest se ponovno izriše šele, ko se
// ura spremeni, kar drži cesta cron poceni na preostalih petminutnih tikih.
function _iconRunStamp() {
  const d = new Date(Math.floor(Date.now() / 3600000) * 3600000);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}T${p(d.getUTCHours())}00`;
}

async function _iconCached(env) {
  const r2 = env?.PHOTOS_R2; if (!r2) return null;
  const runStamp = _iconRunStamp();
  const manifestKey = `${ICON_R2_PREFIX}latest.json`;
  try {
    const o = await r2.get(manifestKey);
    if (o) {
      const m = JSON.parse(await o.text());
      if (m.runStamp === runStamp) return m;
    }
  } catch (_) {}

  const V = COMP_VIEWS.savinja;
  const grid = await _iconFetch(V);
  if (!grid) return null;   // gladek propad — cron ne posodobi manifesta, prejšnji ostane veljaven do izteka starosti

  const okvirji = [];
  for (let h = 0; h < ICON_HOURS; h++) {
    const png = await _iconFrame(grid, V, h);
    const zig = `${runStamp}-h${h + 1}`;
    const cas = new Date(_compStampMs(runStamp) + (h + 1) * 3600000).toISOString();
    try {
      await r2.put(`${ICON_R2_PREFIX}frame-${zig}.png`, png, {
        httpMetadata: { contentType: "image/png" },
        customMetadata: { runStamp, h: String(h + 1), cas },
      });
    } catch (_) {}
    okvirji.push({ zig, cas });
  }
  const manifest = { runStamp, cas: new Date().toISOString(), okvirji };
  try { await r2.put(manifestKey, JSON.stringify(manifest), { httpMetadata: { contentType: "application/json" } }); } catch (_) {}
  return manifest;
}

// Vsak urni tek v celoti nadomesti prejšnjega (za razliko od kompozita, kjer
// vsak okvir predstavlja svoj resnični trenutek), zato tu ni časovnega
// cutoffa — zbrišemo preprosto vse, kar ni trenutni runStamp.
async function _iconPrune(env, keepRunStamp) {
  const r2 = env?.PHOTOS_R2; if (!r2) return 0;
  let n = 0;
  try {
    const list = await r2.list({ prefix: ICON_R2_PREFIX, limit: 200 });
    for (const o of list.objects || []) {
      if (o.key === `${ICON_R2_PREFIX}latest.json`) continue;
      const s = (o.key.match(/frame-(\d{8}T\d{4})-h\d+\.png$/) || [])[1];
      if (s !== keepRunStamp) { await r2.delete(o.key); n++; }
    }
  } catch (_) {}
  return n;
}

async function _cronRenderIcon(env) {
  try {
    const m = await _iconCached(env);
    if (m) await _iconPrune(env, m.runStamp);
    return true;
  } catch (_) { return false; }
}

// ── Sledenje nevihtnim celicam ──────────────────────────────
// Nowcast (zgoraj) oceni en skupen premik za celotno polje in ga uporabi na
// oknu okoli vsake vasi. Tu namesto tega prepoznamo posamezne konvektivne
// celice kot povezana območja nad pragom nevihte in jim sledimo med
// posnetki — nekaj, česar noben javni radar (ARSO, Windy) ne prikaže.
// Zaznavanje teče na lastni, enakomerni lon/lat mreži čez cel "sirok"
// izsek (ne na Web Mercator piksel-prostoru izrisa, kjer km/piksel ni
// enakomeren), da sledenje deluje neodvisno od tega, kateri pogled ima
// obiskovalec odprt.
const CELL_STORM_MMH = 15;    // = RADAR_LEVEL_MMH[RADAR_L_STORM - 1] (glej zgoraj) — obseg celice
const CELL_CORE_MMH = 50;     // = RADAR_LEVEL_MMH[RADAR_L_CORE - 1] — jedro, ki zmore točo
const CELL_MIN_AREA_KM2 = 1.5;  // isti koncept kot RADAR_CORE_MIN_PX, prenesen na to mrežo
const CELL_GRID_DEG = 0.015;    // ~420×230 mreža čez "sirok"; poviša (bolj grobo), če je cron počasen
const CELL_MATCH_RADIUS_KM = 20; // dovolj za nevihtno hitrost (~60 km/h) čez 5-minutni cron korak
const CELL_MAX_MISSES = 2;       // celica se opusti po ~2 zaporednih zgrešenih zaznavah (~10 min)
const CELL_TRAIL_MAX = 4;        // koliko zadnjih leg hrani sled vsake celice (vključno s trenutno)
const CELL_R2_STATE = "cells/state.json";
const CELL_R2_LATEST = "cells/latest.json";
const CELL_ETA_RADIUS_KM = 15;   // "gre proti dolini", če najbližji prehod pade znotraj tega
const CELL_ETA_MAX_MIN = 90;     // linearna ekstrapolacija čez to postane nezanesljiva (glej docs/nowcast.md)
const CELL_ETA_MIN_KMH = 3;      // pod tem je smer preveč šumna, da bi iz nje sklepali ETA

// Najbližji prehod (closest point of approach) premočrtne trajektorije
// celice mimo postaje. C0 = lega celice relativno na postajo (vzhod/sever,
// km), V = hitrostni vektor iz istega smer/kmh, ki ga uporablja tudi
// windDir() na frontendu (0 = sever, urno). Standardna CPA formula:
// t_cpa = -(V·C0)/|V|², minimizira |C0 + V·t|. t_cpa <= 0 pomeni, da se
// celica že oddaljuje (najbližji prehod je v preteklosti) — brez ETA.
function _cellEta(cell) {
  if (cell.kmh == null || cell.smer == null || cell.kmh < CELL_ETA_MIN_KMH) return null;
  const rad = cell.smer * Math.PI / 180;
  const vx = cell.kmh * Math.sin(rad), vy = cell.kmh * Math.cos(rad);   // vzhod, sever (km/h)
  // Postaja Rečica ob Savinji — isti koordinati kot povsod drugod v datoteki
  // (npr. NOWCAST_VASI "recica", worker.js:792), brez skupne konstante po
  // uveljavljeni konvenciji te datoteke.
  const c0x = (cell.lon - 14.9211) * COMP_KM_LON, c0y = (cell.lat - 46.3258) * COMP_KM_LAT;
  const vv = vx * vx + vy * vy;
  const tCpa = -(vx * c0x + vy * c0y) / vv;                             // ure
  if (tCpa <= 0) return null;
  const dx = c0x + vx * tCpa, dy = c0y + vy * tCpa;
  const distCpa = Math.hypot(dx, dy);
  if (distCpa > CELL_ETA_RADIUS_KM) return null;
  const etaMin = Math.round(tCpa * 60);
  if (etaMin > CELL_ETA_MAX_MIN) return null;
  return { etaMin, etaKm: Math.round(distCpa * 10) / 10 };
}

// Ista projekcija in prioritetno pravilo (ARSO znotraj COMP_R_JEDRO, OPERA
// sicer) kot glavna izrisna zanka v _radarComposite, a po eni točki namesto
// po vrstici — koda je namerno vzporedna, ne deljena s tisto zanko, da izris
// kompozita ostane nedotaknjen. Če se prioritetno pravilo tam spremeni,
// uskladi tudi tu.
function _cellSample(win, arso, lon, lat) {
  let mmh = -1;
  if (win) {
    const [x, y] = _laeaXY(lat, lon);
    const fx = (x - win.ox) / win.px - win.c0;
    const fy = (win.oy - y) / win.py - win.r0;
    mmh = _operaSample(win, fx, fy);
  }
  if (arso) {
    const [ax, ay] = _radLonLat2Px(lon, lat);
    let d2 = Infinity;
    for (const [rla, rlo] of COMP_SI_RADARJI) {
      const dx = (lon - rlo) * COMP_KM_LON, dy = (lat - rla) * COMP_KM_LAT;
      const s = dx * dx + dy * dy;
      if (s < d2) d2 = s;
    }
    if (d2 < COMP_R_ROB * COMP_R_ROB) {
      const a = _arsoSample(arso, ax, ay, false);
      if (a != null) {
        if (d2 <= COMP_R_JEDRO * COMP_R_JEDRO) mmh = a;
        else mmh = Math.max(mmh, a);
      }
    }
  }
  return mmh < 0 ? 0 : mmh;   // za zaznavo celic je "ni podatka" enako "ni padavin"
}

function _cellField(win, arso) {
  const V = COMP_VIEWS.sirok;
  const nx = Math.max(2, Math.round((V.lon1 - V.lon0) / CELL_GRID_DEG));
  const ny = Math.max(2, Math.round((V.lat1 - V.lat0) / CELL_GRID_DEG));
  const field = new Float32Array(nx * ny);
  for (let j = 0; j < ny; j++) {
    const lat = V.lat0 + (V.lat1 - V.lat0) * (j + 0.5) / ny;
    for (let i = 0; i < nx; i++) {
      const lon = V.lon0 + (V.lon1 - V.lon0) * (i + 0.5) / nx;
      field[j * nx + i] = _cellSample(win, arso, lon, lat);
    }
  }
  return { field, nx, ny, V };
}

// Iterativno (eksplicit sklad, ne rekurzija — globina klicnega sklada je
// resnično tveganje na ~420×230 mreži) 8-povezano flood-fill nad pragom.
function _cellLabel(field, nx, ny, thresholdMmh) {
  const labels = new Int32Array(nx * ny);
  const stack = new Int32Array(nx * ny);
  const cells = [];
  let nextLabel = 0;
  for (let start = 0; start < nx * ny; start++) {
    if (labels[start] !== 0 || field[start] < thresholdMmh) continue;
    nextLabel++;
    let sp = 0;
    stack[sp++] = start;
    labels[start] = nextLabel;
    let pixelCount = 0, sumX = 0, sumY = 0, maxMmh = 0, corePixelCount = 0;
    while (sp > 0) {
      const p = stack[--sp];
      const py = Math.floor(p / nx), px = p - py * nx;
      pixelCount++; sumX += px; sumY += py;
      if (field[p] > maxMmh) maxMmh = field[p];
      if (field[p] >= CELL_CORE_MMH) corePixelCount++;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (!dx && !dy) continue;
          const qx = px + dx, qy = py + dy;
          if (qx < 0 || qy < 0 || qx >= nx || qy >= ny) continue;
          const q = qy * nx + qx;
          if (labels[q] === 0 && field[q] >= thresholdMmh) { labels[q] = nextLabel; stack[sp++] = q; }
        }
      }
    }
    cells.push({ pixelCount, sumX, sumY, maxMmh, corePixelCount });
  }
  return cells;
}

function _cellsFromField(win, arso) {
  const { field, nx, ny, V } = _cellField(win, arso);
  const cells = _cellLabel(field, nx, ny, CELL_STORM_MMH);
  const degLon = (V.lon1 - V.lon0) / nx, degLat = (V.lat1 - V.lat0) / ny;
  const km2PerPx = degLon * COMP_KM_LON * degLat * COMP_KM_LAT;
  const minPx = CELL_MIN_AREA_KM2 / km2PerPx;
  return cells.filter((c) => c.pixelCount >= minPx).map((c) => {
    const cx = c.sumX / c.pixelCount, cy = c.sumY / c.pixelCount;
    return {
      lon: V.lon0 + (V.lon1 - V.lon0) * (cx + 0.5) / nx,
      lat: V.lat0 + (V.lat1 - V.lat0) * (cy + 0.5) / ny,
      areaKm2: Math.round(c.pixelCount * km2PerPx * 10) / 10,
      // Marshall-Palmer (_dbzMmh) lahko na posameznem šumnem/anomalnem pikslu
      // vrne fizikalno nesmiselno visok mm/h; za prikaz porežemo na najvišjo
      // vrednost, ki jo pozna sama radarska lestvica (RADAR_LEVEL_MMH), ne
      // pustimo, da tak izjemek pride kot številka v oznako na karti.
      maxMmh: Math.min(RADAR_LEVEL_MMH[RADAR_LEVEL_MMH.length - 1], Math.round(c.maxMmh * 10) / 10),
      toca: c.maxMmh >= CELL_CORE_MMH && c.corePixelCount * km2PerPx >= CELL_MIN_AREA_KM2,
    };
  });
}

// Ujemanje med posnetki: pohlepno po najbližjem centroidu znotraj
// CELL_MATCH_RADIUS_KM, brez napovedi premika (pri 5-minutnem koraku in
// razumni nevihtni hitrosti je iskalni polmer sam po sebi dovolj — napoved
// premika bi zahtevala hranjenje celotnega prejšnjega polja samo za ta
// namen). Ni Madžarskega algoritma, samo "dovolj dobro, dokumentirana
// omejitev" — enako kot že drugod v tem cevovodu (glej docs/nowcast.md).
async function _cellTrack(env, newCells) {
  const r2 = env?.PHOTOS_R2;
  let state = { nextId: 1, ts: null, cells: [] };
  if (r2) {
    try { const o = await r2.get(CELL_R2_STATE); if (o) state = JSON.parse(await o.text()); } catch (_) {}
  }
  const elapsedMin = state.ts ? (Date.now() - state.ts) / 60000 : null;

  const pairs = [];
  state.cells.forEach((p, pi) => newCells.forEach((n, ni) => {
    const dKm = Math.hypot((n.lon - p.lon) * COMP_KM_LON, (n.lat - p.lat) * COMP_KM_LAT);
    if (dKm <= CELL_MATCH_RADIUS_KM) pairs.push({ pi, ni, dKm });
  }));
  pairs.sort((a, b) => a.dKm - b.dKm);

  const takenP = new Set(), takenN = new Set(), matched = [];
  for (const { pi, ni } of pairs) {
    if (takenP.has(pi) || takenN.has(ni)) continue;
    takenP.add(pi); takenN.add(ni);
    const prev = state.cells[pi], now = newCells[ni];
    let smer = prev.smer ?? null, kmh = prev.kmh ?? null;
    if (elapsedMin && elapsedMin > 0.5) {
      const dx = (now.lon - prev.lon) * COMP_KM_LON, dy = (now.lat - prev.lat) * COMP_KM_LAT;
      kmh = Math.round(Math.hypot(dx, dy) / (elapsedMin / 60) * 10) / 10;
      // dx/dy sta tu prava geografska km (vzhod/sever), za razliko od
      // _radMotion, kjer je dy v ARSO pikslih z obrnjenim predznakom
      // (piksel Y raste proti jugu) — zato tu BREZ negacije dy.
      smer = Math.round((Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360);
    }
    const trail = [...(prev.trail || [[prev.lon, prev.lat]]), [now.lon, now.lat]].slice(-CELL_TRAIL_MAX);
    matched.push({ ...now, id: prev.id, missCount: 0, smer, kmh, trail });
  }
  state.cells.forEach((p, pi) => {
    if (takenP.has(pi)) return;
    // Zgrešena celica: pozicije ne poznamo na novo, zato sledi ne podaljšamo
    // (podvojena zadnja točka bi sled samo skrajšala na eno mesto).
    if ((p.missCount || 0) + 1 <= CELL_MAX_MISSES) matched.push({ ...p, missCount: (p.missCount || 0) + 1 });
  });
  newCells.forEach((n, ni) => {
    if (takenN.has(ni)) return;
    matched.push({ ...n, id: state.nextId++, missCount: 0, smer: null, kmh: null, trail: [[n.lon, n.lat]] });
  });

  const newState = {
    nextId: state.nextId, ts: Date.now(),
    cells: matched.map((c) => ({
      id: c.id, lon: c.lon, lat: c.lat, areaKm2: c.areaKm2, maxMmh: c.maxMmh, toca: c.toca,
      missCount: c.missCount, smer: c.smer, kmh: c.kmh, trail: c.trail,
    })),
  };
  if (r2) { try { await r2.put(CELL_R2_STATE, JSON.stringify(newState)); } catch (_) {} }
  return matched.filter((c) => c.missCount === 0);  // "zgrešene" celice ostanejo v stanju za ujemanje, a se ne kažejo
}

// Enako kot windDir() v app.js — tu ločeno, ker push besedilo sestavimo na
// strežniku, brez dostopa do frontend kode.
function _smerBesedilo(deg) {
  const d = ["S", "SSV", "SV", "VSV", "V", "VJV", "JV", "JJV", "J", "JJZ", "JZ", "ZJZ", "Z", "ZSZ", "SZ", "SSZ"];
  return d[Math.round(deg / 22.5) % 16];
}

// Push obvestilo, ko celica prvič dobi veljaven ETA (glej _cellEta) — ne ob
// vsakem cron tiku, dokler je "na poti", sicer bi za eno nevihto poslali
// obvestilo vsakih 5 minut. cell.id se med sledenjem nikoli ne ponovi (glej
// state.nextId v _cellTrack), zato "enkrat na id" zadošča kot ključ, brez
// ločenega časovnega cooldowna kot pri PUSH_THRESHOLDS/nowcastu zgoraj.
async function _cronPushCellEta(env, celice) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return;
  let notified = {};
  try { const o = await r2.get("push/cell_eta_state.json"); notified = o ? JSON.parse(await o.text()) : {}; } catch (_) {}

  const liveIds = new Set(celice.map((c) => c.id));
  let changed = false;
  for (const id of Object.keys(notified)) {
    if (!liveIds.has(Number(id))) { delete notified[id]; changed = true; }
  }

  for (const c of celice) {
    if (c.eta_min == null || notified[c.id]) continue;
    await _pushAll(env, {
      title: "Meteorec — nevihta se približuje",
      body: "⛈️ Nevihtna celica prihaja proti Rečici ob Savinji čez ~" + c.eta_min + " min ("
        + Math.round(c.kmh) + " km/h, " + _smerBesedilo(c.smer) + ").",
      url: "/", tag: "wx-cell-" + c.id,
    });
    notified[c.id] = true;
    changed = true;
  }
  if (changed) { try { await r2.put("push/cell_eta_state.json", JSON.stringify(notified), { httpMetadata: { contentType: "application/json" } }); } catch (_) {} }
}

async function _cronRenderRadarCells(env, win, arso) {
  try {
    if (!win && !arso) return false;
    const tracked = await _cellTrack(env, _cellsFromField(win, arso));
    const celice = tracked.map((c) => {
      const eta = _cellEta(c);
      return {
        id: c.id, lat: Math.round(c.lat * 1000) / 1000, lon: Math.round(c.lon * 1000) / 1000,
        povrsina_km2: c.areaKm2, mmh: c.maxMmh, toca: !!c.toca,
        smer: c.smer == null ? null : Math.round(c.smer), kmh: c.kmh == null ? null : c.kmh,
        eta_min: eta ? eta.etaMin : null, eta_km: eta ? eta.etaKm : null,
        // [lat,lon] pari, najstarejši prvi — kratka sled zadnjih leg za izris
        // na karti namesto gole pike (glej CELL_TRAIL_MAX).
        sled: (c.trail || []).map(([lo, la]) => [Math.round(la * 1000) / 1000, Math.round(lo * 1000) / 1000]),
      };
    });
    // Najbolj nujna prihajajoča celica (najkrajši ETA) kot pripravljen povzetek
    // za banner — frontend se mu ni treba sam sprehoditi čez seznam. Polje se
    // namerno NE imenuje "opozorilo" — to ime že uporablja mehek odpovedni
    // odgovor spodaj (niz z razlogom), različna oblika bi zmedla odjemalca.
    const prihaja = celice.filter((c) => c.eta_min != null).sort((a, b) => a.eta_min - b.eta_min)[0] || null;
    const out = { cas: new Date().toISOString(), celice, prihaja };
    const r2 = env?.PHOTOS_R2;
    if (r2) await r2.put(CELL_R2_LATEST, JSON.stringify(out), { httpMetadata: { contentType: "application/json" } });
    await _cronPushCellEta(env, celice).catch(() => {});
    return true;
  } catch (_) { return false; }
}

// Cron vsakih 5 minut izriše najnovejši okvir, da je animacija za obiskovalca
// že topla; sproti počisti stare. Za "sirok" pogled si vir OPERA/ARSO izposodi
// naprej v _radarComposite (da se v tej isti funkciji ne prenese dvakrat), a
// sledenje celicam TU ne teče več — glej opombo pri _cronRenderIconAndCells,
// zakaj je na ločenem urniku.
async function _cronRenderRadarComposite(env) {
  try {
    for (const vid of Object.keys(COMP_VIEWS)) {
      if (vid === "sirok") {
        const key = await _operaLatestKey();
        const stamp = key ? _compStamp(key) : null;
        if (stamp) {
          const sirokSources = await Promise.all([
            _operaWindow(_operaKeyForStamp(stamp), _compBBox(COMP_VIEWS.sirok)).catch(() => null),
            _compArso(_compStampMs(stamp)),
          ]);
          await _radarCompositeCached(env, stamp, "sirok", sirokSources).catch(() => null);
          continue;
        }
      }
      await _radarCompositeCached(env, null, vid).catch(() => null);
    }
    await _radarCompositePrune(env);
    return true;
  } catch (_) { return false; }
}

// ICON napoved in sledenje celicam sta bila sprva na istem 5-minutnem
// urniku kot spodnja (že sama po sebi težka) opravila — v praksi se v
// produkciji nista nikoli izvedla (potrjeno: neposreden klic prek HTTP je
// deloval takoj in hitro, isti klic prek scheduled() pa ~40 min/8 tikov ni
// zapisal ničesar), najverjetneje ker si vsi ctx.waitUntil() znotraj ENE
// invokacije delijo en časovni/CPU proračun in so ta dva dodatka zadnja v
// vrsti. Zato tečeta na LASTNEM, za 2 min zamaknjenem cron urniku
// ("2-59/5 * * * *", wrangler.toml) — ločena invokacija scheduled() pomeni
// lasten proračun, brez tekmovanja s spodnjimi opravili. Cena: lasten
// (neshared) prenos OPERA/ARSO za "sirok" namesto souporabe s kompozitom —
// sprejemljivo, ker gre prek istega `cf:{cacheTtl}` robnega predpomnilnika.
async function _cronRenderIconAndCells(env) {
  const t0 = Date.now();
  const iconOk = await _cronRenderIcon(env).catch(() => false);
  let cellsOk = false, cellsErr = null;
  try {
    const key = await _operaLatestKey();
    const stamp = key ? _compStamp(key) : null;
    if (stamp) {
      const [win, arso] = await Promise.all([
        _operaWindow(_operaKeyForStamp(stamp), _compBBox(COMP_VIEWS.sirok)).catch(() => null),
        _compArso(_compStampMs(stamp)),
      ]);
      cellsOk = await _cronRenderRadarCells(env, win, arso);
    }
  } catch (e) { cellsErr = String((e && e.message) || e); }
  const r2 = env?.PHOTOS_R2;
  if (r2) {
    try {
      await r2.put("debug/newradar-cron.json", JSON.stringify({
        cas: new Date().toISOString(), ms: Date.now() - t0, iconOk, cellsOk, cellsErr,
      }), { httpMetadata: { contentType: "application/json" } });
    } catch (_) {}
  }
}

export default {
  async scheduled(event, env, ctx) {
    if (event.cron === "2-59/5 * * * *") {
      ctx.waitUntil(_cronRenderIconAndCells(env));
      return;
    }
    ctx.waitUntil(_cronCheckThresholds(env));
    // Radarski nowcast nadomesti modelski; na model pademo le, če radar odpove,
    // sicer bi za isti dogodek poslali dve obvestili.
    ctx.waitUntil((async () => {
      const ok = await _cronCheckRadarNowcast(env).catch(() => false);
      if (!ok) await _cronCheckPrecipNowcast(env);
    })());
    ctx.waitUntil(_cronCheckRainStartStop(env));
    ctx.waitUntil(_cronCheckAurora(env));
    ctx.waitUntil(_cronRenderRadarComposite(env));
  },
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_ALLOWED });
    }

    const url  = new URL(request.url);
    const path = url.pathname;

    // ── /vreme/YYYY/MM/ — edge-rendered current month archive page ─────────
    // Only intercepts when Worker is deployed as a route on meteorec.si.
    // Pass-through (fetch(request)) lets GitHub Pages serve historical months.
    const vremeMonthMatch = path.match(/^\/vreme\/(\d{4})\/(\d{2})\/?$/);
    if (vremeMonthMatch) {
      const [, yr, mo] = vremeMonthMatch;
      const now = new Date();
      const isCurrentMonth = (parseInt(yr) === now.getUTCFullYear() &&
                              parseInt(mo) === now.getUTCMonth() + 1);
      if (!isCurrentMonth) {
        return fetch(request);
      }
      try {
        const histResp = await fetch("https://meteorec.si/history.json",
          { cf: { cacheTtl: 3600, cacheEverything: true } });
        if (!histResp.ok) return fetch(request);
        const hist = await histResp.json();
        const prefix = `${yr}-${mo}`;
        const days = Object.entries(hist)
          .filter(([d]) => d.startsWith(prefix))
          .sort(([a], [b]) => a < b ? -1 : 1);
        if (!days.length) return fetch(request);
        const html = renderCurrentMonthPage(yr, mo, days);
        return new Response(html, {
          headers: {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "s-maxage=3600, stale-while-revalidate=86400",
            "X-Rendered-By": "worker",
          },
        });
      } catch (_) {
        return fetch(request);
      }
    }

    // /debug-headers — returns all incoming request headers as JSON (no auth required)
    if (path === "/debug-headers") {
      const headers = {};
      for (const [k, v] of request.headers.entries()) headers[k] = v;
      return new Response(JSON.stringify({ headers, origin: request.headers.get("Origin"), referer: request.headers.get("Referer"), allowed: isAllowedOrigin(request) }, null, 2), {
        headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-store" }
      });
    }

    // /ai-debug is openable directly in a browser for troubleshooting.
    // /daily-post/* is opened from e-mail clients (Gmail pošlje tuj Referer)
    // in zavarovan s skrivnostjo oz. HMAC podpisom, ne z Origin kontrolo.
    if (!isAllowedOrigin(request) && path !== "/ai-debug" && !path.startsWith("/daily-post/")) {
      return new Response(
        JSON.stringify({ error: "Nepooblaščen dostop", code: 403 }),
        { status: 403, headers: { ...CORS_DENY, "Content-Type": "application/json" } }
      );
    }

    try {

      // ── /arso-warning ─────────────────────────────────────
      // ARSO uradna vremensko opozorila — ATOM feed (strukturiran, zanesljiv)
      // Regija za Rečico ob Savinji: SLOVENIA_NORTH-EAST
      if (path === "/arso-warning") {
        // Primary: vreme.arso.gov.si JSON API — same host as text forecast, reliable from CF Workers
        try {
          const { alerts, issued } = await fetchArsoWarnings();
          return new Response(JSON.stringify({ alerts, issued, source: "arso-api" }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=300" }
          });
        } catch (e) {
          // Fallback: ARSO ATOM feed (may be blocked on some CF edge nodes)
          const region = url.searchParams.get("region") || "SLOVENIA_NORTH-EAST";
          const atomUrl = `https://meteo.arso.gov.si/uploads/probase/www/warning/text/sl/warning_${region}_latest.atom`;
          try {
            const r = await fetch(atomUrl, {
              headers: {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://meteo.arso.gov.si/",
                "Accept": "application/atom+xml,application/xml,text/xml,*/*",
              }
            });
            if (!r.ok) throw new Error("ATOM HTTP " + r.status);
            const text = await r.text();
            const alerts = [];
            // Čas izdaje opozorila (15. člen ZDMHS) -- prvi <updated> pred
            // prvim <entry> je datum vira, ne posameznega opozorila.
            const feedHead = text.split(/<entry[\s>]/i)[0];
            const issued = (feedHead.match(/<updated[^>]*>([\s\S]*?)<\/updated>/i)?.[1] || '').trim() || null;
            const entryRx = /<entry[\s>]([\s\S]*?)<\/entry>/gi;
            let m;
            while ((m = entryRx.exec(text)) !== null) {
              const entry = m[1];
              const title   = (entry.match(/<title[^>]*>([\s\S]*?)<\/title>/i)  ?.[1] || '').replace(/<[^>]+>/g,' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').trim();
              const summary = (entry.match(/<summary[^>]*>([\s\S]*?)<\/summary>/i)?.[1] || '').replace(/<[^>]+>/g,' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').trim();
              const content = title + ' ' + summary;
              let level = null;
              const capSev = (entry.match(/<cap:severity[^>]*>([\s\S]*?)<\/cap:severity>/i)?.[1] || '').trim().toLowerCase();
              if      (capSev === 'extreme')                        level = 'red';
              else if (capSev === 'severe')                         level = 'orange';
              else if (capSev === 'moderate' || capSev === 'minor') level = 'yellow';
              if (!level) {
                if      (/(rdeče?\s*opozorilo|red\s*warning)/i.test(content))    level = 'red';
                else if (/(oranžno?\s*opozorilo|orange\s*warning)/i.test(content)) level = 'orange';
                else if (/(rumeno?\s*opozorilo|yellow\s*warning)/i.test(content))  level = 'yellow';
              }
              if (level) alerts.push({ level, text: (summary || title).slice(0, 600) });
            }
            return new Response(JSON.stringify({ alerts, issued, source: "arso-atom" }), {
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=300" }
            });
          } catch (e2) {
            return new Response(JSON.stringify({ alerts: [], error: e.message + " / " + e2.message }), {
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
            });
          }
        }
      }

      // ── /google-weather-alerts ───────────────────────────
      // Google Maps Weather API — publicAlerts za koordinate postaje
      // Zahteva: GET /google-weather-alerts
      // Vrne: JSON z alerts[] po Google Weather API formatu
      if (path === "/google-weather-alerts") {
        if (!GOOGLE_WEATHER_KEY || GOOGLE_WEATHER_KEY.startsWith("REPLACE")) {
          return new Response(JSON.stringify({ error: "no_key", alerts: [] }),
            { status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }
        const gwUrl = `https://weather.googleapis.com/v1/publicAlerts:lookup?key=${GOOGLE_WEATHER_KEY}&location.latitude=46.325779&location.longitude=14.921137`;
        const gwRes = await fetch(gwUrl, { headers: { "Accept": "application/json" } });
        if (!gwRes.ok) {
          return new Response(JSON.stringify({ error: "Google Weather HTTP " + gwRes.status, alerts: [] }),
            { status: gwRes.status, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }
        const gwData = await gwRes.json();
        return new Response(JSON.stringify(gwData), {
          headers: {
            ...CORS_ALLOWED,
            "Content-Type": "application/json",
            "Cache-Control": "public, max-age=600",
          }
        });
      }

      // ── /meteoalarm ───────────────────────────────────────
      // MeteoAlarm legacy Atom feed (aktiven), fallback na ARSO ATOM
      if (path === "/meteoalarm") {
        const sources = [
          "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-slovenia",
          "https://meteo.arso.gov.si/uploads/probase/www/warning/text/sl/warning_SLOVENIA_NORTH-EAST_latest.atom",
        ];
        for (const src of sources) {
          try {
            const ctrl = new AbortController();
            const tid  = setTimeout(() => ctrl.abort(), 5000);
            const r = await fetch(src, {
              headers: { "Accept": "application/atom+xml,application/xml,text/xml", "User-Agent": "Mozilla/5.0" },
              signal: ctrl.signal,
            });
            clearTimeout(tid);
            if (!r.ok) continue;
            const text = await r.text();
            if (!text.includes("<entry>") && !text.includes("<item>")) continue;
            return new Response(text, {
              headers: {
                ...CORS_ALLOWED,
                "Content-Type": "application/xml; charset=utf-8",
                "Cache-Control": "public, max-age=600",
              }
            });
          } catch (_) { continue; }
        }
        // Vsi viri so nedostopni — vrni prazen atom
        return new Response(
          '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>MeteoAlarm SI</title></feed>',
          { headers: { ...CORS_ALLOWED, "Content-Type": "application/xml; charset=utf-8" } }
        );
      }

      // ── /counter ──────────────────────────────────────────
      // Persistentni counter zahteva KV binding. Brez KV vrne in-memory vrednost.
      if (path === "/counter") {
        let count = _memCount;
        if (env?.COUNTER_KV) {
          // S KV bindingom: shrani persistentno
          const stored = await env.COUNTER_KV.get("visits");
          count = (parseInt(stored || "0") || _memCount) + 1;
          await env.COUNTER_KV.put("visits", String(count));
        } else {
          _memCount++;
          count = _memCount;
        }
        return new Response(
          JSON.stringify({ count }),
          { headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" } }
        );
      }

      // ── /online ───────────────────────────────────────────
      // Koliko brskalnikov je trenutno na strani. Vsak obiskovalec pošlje
      // "utrip" na ~25 s z naključnim id-jem (?id=); ključ "online:<id>" ima
      // expirationTtl 90 s, torej se sam počisti, če zavihek zapre ali
      // izgubi povezavo — brez eksplicitnega "odjavi se" klica. Število je
      // približno (KV list ima eventual consistency ~60 s), kar je za
      // dekorativen widget dovolj dobro.
      if (path === "/online") {
        const kv = env?.COUNTER_KV;
        if (!kv) {
          return new Response(JSON.stringify({ stevilo: null }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-store" },
          });
        }
        const id = url.searchParams.get("id");
        if (id && /^[a-zA-Z0-9-]{8,64}$/.test(id)) {
          try { await kv.put(`online:${id}`, "1", { expirationTtl: 90 }); } catch (_) {}
        }
        let stevilo = 0;
        try {
          const list = await kv.list({ prefix: "online:", limit: 1000 });
          stevilo = list.keys.length;
        } catch (_) {}
        return new Response(JSON.stringify({ stevilo }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-store" },
        });
      }

      // ── /like ─────────────────────────────────────────────
      // Všečki na blog posta. Ključ v KV: "like:<slug>".
      // GET  /like?slug=xxx            → { slug, count }
      // GET  /like?slugs=a,b,c         → { likes: { a:N, b:N, … } }  (bulk, za seznam bloga)
      // POST /like?slug=xxx&delta=1|-1 → poveča/zmanjša in vrne { slug, count }
      // Persistenca zahteva KV binding COUNTER_KV; brez njega vrne in-memory vrednost.
      if (path === "/like") {
        if (request.method === "GET" && url.searchParams.get("slugs") !== null) {
          const wanted = url.searchParams.get("slugs").split(",").map(s => s.trim().toLowerCase())
            .filter(s => /^[a-z0-9-]{1,120}$/.test(s)).slice(0, 60);
          const likes = {};
          if (env?.COUNTER_KV) {
            await Promise.all(wanted.map(async s => {
              likes[s] = parseInt((await env.COUNTER_KV.get("like:" + s)) || "0") || 0;
            }));
          } else {
            wanted.forEach(s => { likes[s] = _memLikes["like:" + s] || 0; });
          }
          return new Response(JSON.stringify({ likes }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "s-maxage=300" }
          });
        }
        const slug = (url.searchParams.get("slug") || "").toLowerCase();
        // dovolimo le varne sluge (mala črka, številka, vezaj) do 120 znakov
        if (!/^[a-z0-9-]{1,120}$/.test(slug)) {
          return new Response(
            JSON.stringify({ error: "neveljaven slug" }),
            { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
          );
        }
        const key = "like:" + slug;
        let count;
        if (env?.COUNTER_KV) {
          count = parseInt((await env.COUNTER_KV.get(key)) || "0") || 0;
          if (request.method === "POST") {
            const delta = url.searchParams.get("delta") === "-1" ? -1 : 1;
            count = Math.max(0, count + delta);
            await env.COUNTER_KV.put(key, String(count));
          }
        } else {
          _memLikes[key] = _memLikes[key] || 0;
          if (request.method === "POST") {
            const delta = url.searchParams.get("delta") === "-1" ? -1 : 1;
            _memLikes[key] = Math.max(0, _memLikes[key] + delta);
          }
          count = _memLikes[key];
        }
        return new Response(
          JSON.stringify({ slug, count }),
          { headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" } }
        );
      }

      // ── /views ────────────────────────────────────────────
      // Ogledi blog člankov. Ključ v KV: "views:<slug>".
      // GET  /views?slug=xxx     → { slug, count }
      // GET  /views?slugs=a,b,c  → { views: { a:N, b:N, … } }  (bulk, za seznam bloga)
      // POST /views?slug=xxx     → poveča za 1 in vrne { slug, count }
      //
      // Ponavljajoče se štetje istega bralca prepreči odjemalec (blog/views.js
      // pošlje POST samo enkrat na 12 ur na napravo in slug, sicer bere z GET).
      // To hkrati drži število KV zapisov nizko — vsak POST je en zapis.
      // Persistenca zahteva KV binding COUNTER_KV; brez njega vrne in-memory vrednost.
      if (path === "/views") {
        if (request.method === "GET" && url.searchParams.get("slugs") !== null) {
          const wanted = url.searchParams.get("slugs").split(",").map(s => s.trim().toLowerCase())
            .filter(s => /^[a-z0-9-]{1,120}$/.test(s)).slice(0, 60);
          const views = {};
          if (env?.COUNTER_KV) {
            await Promise.all(wanted.map(async s => {
              views[s] = parseInt((await env.COUNTER_KV.get("views:" + s)) || "0") || 0;
            }));
          } else {
            wanted.forEach(s => { views[s] = _memViews["views:" + s] || 0; });
          }
          return new Response(JSON.stringify({ views }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "s-maxage=300" }
          });
        }
        const slug = (url.searchParams.get("slug") || "").toLowerCase();
        if (!/^[a-z0-9-]{1,120}$/.test(slug)) {
          return new Response(
            JSON.stringify({ error: "neveljaven slug" }),
            { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
          );
        }
        const key = "views:" + slug;
        const bump = request.method === "POST";
        let count;
        if (env?.COUNTER_KV) {
          count = parseInt((await env.COUNTER_KV.get(key)) || "0") || 0;
          if (bump) {
            count += 1;
            await env.COUNTER_KV.put(key, String(count));
          }
        } else {
          _memViews[key] = _memViews[key] || 0;
          if (bump) _memViews[key] += 1;
          count = _memViews[key];
        }
        return new Response(
          JSON.stringify({ slug, count }),
          {
            headers: {
              ...CORS_ALLOWED, "Content-Type": "application/json",
              // Branje sme biti kratko predpomnjeno na robu (števec ogledov ne
              // rabi biti na sekundo točen), odgovor na POST pa nikoli.
              "Cache-Control": bump ? "no-store" : "s-maxage=60"
            }
          }
        );
      }

      // ── /poll ─────────────────────────────────────────────
      // Dnevna mikroanketa skupnosti o počutju vremena.
      // Ključ v KV: "poll:YYYY-MM-DD". Vrednost: JSON { perfect, sticky, chilly, raw }.
      // GET  /poll               → { date, counts }
      // POST /poll?option=perfect|sticky|chilly|raw → { date, counts }
      // Persistenca zahteva KV binding COUNTER_KV; brez njega vrne in-memory vrednost.
      if (path === "/poll") {
        const POLL_OPTIONS = ["perfect", "sticky", "chilly", "raw"];
        const today = fmtDate(new Date());
        const key = "poll:" + today;
        let counts;
        if (env?.COUNTER_KV) {
          try { counts = JSON.parse(await env.COUNTER_KV.get(key)) || {}; } catch (_) { counts = {}; }
          if (request.method === "POST") {
            const option = url.searchParams.get("option") || "";
            if (!POLL_OPTIONS.includes(option)) {
              return new Response(
                JSON.stringify({ error: "neveljavna možnost" }),
                { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
              );
            }
            counts[option] = (counts[option] || 0) + 1;
            await env.COUNTER_KV.put(key, JSON.stringify(counts), { expirationTtl: 3 * 86400 });
          }
        } else {
          _memPoll[key] = _memPoll[key] || {};
          if (request.method === "POST") {
            const option = url.searchParams.get("option") || "";
            if (!POLL_OPTIONS.includes(option)) {
              return new Response(
                JSON.stringify({ error: "neveljavna možnost" }),
                { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
              );
            }
            _memPoll[key][option] = (_memPoll[key][option] || 0) + 1;
          }
          counts = _memPoll[key];
        }
        const full = {};
        POLL_OPTIONS.forEach(o => full[o] = counts[o] || 0);
        return new Response(
          JSON.stringify({ date: today, counts: full }),
          { headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" } }
        );
      }

      // ── /android-poll ───────────────────────────────────────
      // Anketa: "Bi si namestil/a pravo Android aplikacijo za Meteorec?"
      // Ključ v KV: "poll:android-app" (trajen, brez izteka). Vrednost: { da, ne }.
      // GET  /android-poll                     → { counts }
      // POST /android-poll?option=da|ne        → { counts }
      // Persistenca zahteva KV binding COUNTER_KV; brez njega vrne in-memory vrednost.
      if (path === "/android-poll") {
        const ANDROID_POLL_OPTIONS = ["da", "ne"];
        const key = "poll:android-app";
        let counts;
        if (env?.COUNTER_KV) {
          try { counts = JSON.parse(await env.COUNTER_KV.get(key)) || {}; } catch (_) { counts = {}; }
          if (request.method === "POST") {
            const option = url.searchParams.get("option") || "";
            if (!ANDROID_POLL_OPTIONS.includes(option)) {
              return new Response(
                JSON.stringify({ error: "neveljavna možnost" }),
                { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
              );
            }
            counts[option] = (counts[option] || 0) + 1;
            await env.COUNTER_KV.put(key, JSON.stringify(counts));
          }
        } else {
          if (request.method === "POST") {
            const option = url.searchParams.get("option") || "";
            if (!ANDROID_POLL_OPTIONS.includes(option)) {
              return new Response(
                JSON.stringify({ error: "neveljavna možnost" }),
                { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
              );
            }
            _memAndroidPoll[option] = (_memAndroidPoll[option] || 0) + 1;
          }
          counts = _memAndroidPoll;
        }
        const full = {};
        ANDROID_POLL_OPTIONS.forEach(o => full[o] = counts[o] || 0);
        return new Response(
          JSON.stringify({ counts: full }),
          { headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" } }
        );
      }

      // ── /ecowitt-history ──────────────────────────────────
      if (path === "/ecowitt-history") {
        const now   = new Date();
        const start = url.searchParams.get("start") || fmtDate(new Date(now - 30*864e5));
        const end   = url.searchParams.get("end")   || fmtDate(now);
        const data  = await fetchEcowitt(start, end, env);
        if (!data) {
          return new Response(
            JSON.stringify({ error: "Ecowitt application_key ni nastavljen" }),
            { status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
          );
        }
        return new Response(
          JSON.stringify({ summaries: normalize(data) }),
          { headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" } }
        );
      }

      // ── /ecowitt-current ──────────────────────────────────
      if (path === "/ecowitt-current") {
        const ewApp = env?.EW_APP || EW_APP_FALLBACK;
        const ewApi = env?.EW_API || EW_API_FALLBACK;
        if (!ewApp || !ewApi) {
          return new Response(JSON.stringify({error:"no_key"}),
            {status:503, headers:{...CORS_ALLOWED,"Content-Type":"application/json"}});
        }
        const ewUrl = "https://api.ecowitt.net/api/v3/device/real_time?" + new URLSearchParams({
          application_key: ewApp, api_key: ewApi, mac: EW_MAC,
          call_back: "all", temp_unitid: "1", pressure_unitid: "3",
          wind_speed_unitid: "7", rainfall_unitid: "12", solar_irradiance_unitid: "16",
        });
        const ewRes = await fetch(ewUrl);
        const ewData = await ewRes.json();
        // Postaja meri tudi v hiši. To je zasebno in ne sodi ven — niti na
        // stran, niti v članke, niti komurkoli, ki ta endpoint pokliče.
        // Režemo tu, pri viru, da noben odjemalec tega sploh ne more videti.
        if (ewData && ewData.data) delete ewData.data.indoor;
        return new Response(JSON.stringify(ewData), {
          headers: {...CORS_ALLOWED, "Content-Type":"application/json", "Cache-Control":"max-age=120"}
        });
      }

      // ── /varpolje-current ─────────────────────────────────
      // Sosednja postaja IREICA7 (Varpolje). Prijateljev strežnik ne pošilja
      // glave CORS, zato je brskalnik na meteorec.si ne sme brati neposredno
      // in gre poizvedba prek nas.
      //
      // Zasebnost velja tudi za sosedovo hišo: če bi se v odgovoru kdaj
      // pojavile notranje meritve, jih režemo tu, pri viru, tako da jih noben
      // odjemalec ne dobi (isto načelo kot pri /ecowitt-current, CLAUDE.md).
      if (path === "/varpolje-current") {
        try {
          const vpRes = await fetch(VARPOLJE_URL, { headers: { "Accept": "application/json" } });
          if (!vpRes.ok) throw new Error("HTTP " + vpRes.status);
          const vpData = await vpRes.json();
          delete vpData.indoor;
          if (vpData && vpData.current) delete vpData.current.indoor;
          return new Response(JSON.stringify(vpData), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=120" }
          });
        } catch (e) {
          return new Response(
            JSON.stringify({ ok: false, error: "varpolje_unreachable", detail: String(e) }),
            { status: 502, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
          );
        }
      }

      // ── /hmeljar-raba ────────────────────────────────────────
      // Hmeljiške parcele (MKGP RABA_ID=1160, uradni GIS sloj RABA) za
      // MeteoHmeljar zemljevid, omejeno na Zgornjo Savinjsko dolino
      // (RABA_BBOX). Uradni geohub.gov.si strežnik ne pošilja
      // Access-Control-Allow-Origin, zato ga brskalnik ne sme brati
      // neposredno (isto načelo kot /varpolje-current) — gre prek nas.
      // RABA se osveži nekajkrat na leto, ne v realnem času, zato dolg
      // predpomnilnik.
      if (path === "/hmeljar-raba") {
        try {
          const rabaUrl = "https://geohub.gov.si/ags/rest/services/TEMELJNE_VSEBINE/GH_MKGP_GERK_RABA/MapServer/1551/query"
            + "?where=RABA_ID%3D1160&outFields=RABA_PID,POVRSINA"
            + "&geometry=" + encodeURIComponent(RABA_BBOX)
            + "&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects"
            + "&returnGeometry=true&outSR=4326&f=geojson";
          const rabaRes = await fetch(rabaUrl, { headers: { "Accept": "application/geo+json" } });
          if (!rabaRes.ok) throw new Error("HTTP " + rabaRes.status);
          const rabaData = await rabaRes.text();
          return new Response(rabaData, {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/geo+json", "Cache-Control": "max-age=86400" }
          });
        } catch (e) {
          return new Response(
            JSON.stringify({ ok: false, error: "raba_unreachable", detail: String(e) }),
            { status: 502, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
          );
        }
      }

      // ── /arso-obs ─────────────────────────────────────────
      if (path === "/arso-obs") {
        const arsoRes = await fetch(
          "https://meteo.arso.gov.si/uploads/probase/www/observ/surface/text/sl/observation_si_latest.xml",
          {headers:{"Accept":"application/xml,text/xml"}}
        );
        const text = await arsoRes.text();
        return new Response(text, {
          headers: {...CORS_ALLOWED, "Content-Type":"application/xml;charset=utf-8", "Cache-Control":"max-age=600"}
        });
      }

      // ── /ai-brief ─────────────────────────────────────────
      if (path === "/ai-brief" && request.method === "POST") {
        if (!ANTHROPIC_KEY || ANTHROPIC_KEY.startsWith("REPLACE")) {
          return new Response(JSON.stringify({error:"no_key"}),
            {status:503, headers:{...CORS_ALLOWED,"Content-Type":"application/json"}});
        }
        const body = await request.json();
        const prompt = `Si vremenski asistent za makro fotografa Filipa v Rečici ob Savinji, Slovenija (dolina Savinje, 366 m n.v.).

Trenutne razmere: ${body.temp}°C, vlaga ${body.hum}%, veter ${body.wind} km/h, ${body.rain > 0 ? body.rain + ' mm/h dežja' : 'brez dežja'}, ${body.cond}.
GDD letos: ${body.gdd} (fenofaza: ${body.phenoPhase}).
Zlata ura: ↑ ${body.goldAM} / ↓ ${body.goldPM}. Sonce: ${body.sunrise} – ${body.sunset}.
Luna: ${body.moon} (${body.moonIllum}% osvetljenosti). Čas: ${body.timeStr}.

Sestavi KRATEK osebni fotografski brief (3–4 kratki stavki) v slovenščini. Vključi:
1. Kateri makro subjekti so danes verjetno aktivni (specifično: žuželke, pajki, rastline glede na GDD in temperature)
2. Najboljši čas za izhod danes (glede na zlato uro in temperature)
3. Konkretno lokacijo v dolini Savinje (reka Savinja, mokrotni travniki, gozdni rob)
4. En specifičen fotografski nasvet za današnje pogoje

Ton: navdušujoč, konkreten, praktičen. Max 4 stavki skupaj.`;

        const aiRes = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
          },
          body: JSON.stringify({
            model: "claude-sonnet-4-20250514",
            max_tokens: 300,
            messages: [{ role: "user", content: prompt }],
          }),
        });
        const aiData = await aiRes.json();
        const text = aiData.content?.[0]?.text || "";
        return new Response(JSON.stringify({brief: text}),
          {headers:{...CORS_ALLOWED,"Content-Type":"application/json","Cache-Control":"no-cache"}});
      }

      // ── /ai-forecast ─────────────────────────────────────
      // yr.no (AROME/MEPS 2.5 km) → daily summaries + besedilna napoved.
      // Besedilo: poskusi uradno ARSO napoved, sicer sestavi popoln opis
      // iz yr.no podatkov (brez AI, brez omejitve dolžine).
      if (path === "/ai-forecast") {
        // Ljubljana UTC offset (UTC+1 winter, UTC+2 summer)
        const ljOff = (() => {
          const d = new Date();
          const jan = new Date(d.getFullYear(), 0, 1);
          const jul = new Date(d.getFullYear(), 6, 1);
          const stdOff = Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());
          return d.getTimezoneOffset() < stdOff ? 2 : 1;
        })();

        // Fetch yr.no forecast + ARSO official text in parallel
        const ctrl = new AbortController();
        setTimeout(() => ctrl.abort(), 8000);
        const [yrRes, arsoTry] = await Promise.allSettled([
          fetch(
            "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=46.3258&lon=14.9211&altitude=366",
            { signal: ctrl.signal, headers: {
              "User-Agent": "Meteorec/1.0 github.com/ibanezar/weather-station filip.eremita@gmail.com",
              "Accept": "application/json",
            } }
          ),
          fetchArsoText(),
        ]);

        if (yrRes.status !== "fulfilled" || !yrRes.value.ok) throw new Error("yr.no nedostopen");
        const yrData = await yrRes.value.json();
        const timeseries = yrData.properties?.timeseries || [];

        // Aggregate hourly → daily (Ljubljana local time)
        const days = {};
        for (const ts of timeseries) {
          const local = new Date(new Date(ts.time).getTime() + ljOff * 3600000);
          const date = local.toISOString().slice(0, 10);
          const hour = local.getUTCHours();
          if (!days[date]) days[date] = { temps: [], winds: [], rain: 0, syms: [], noonSym: null, firstHour: hour };
          const det = ts.data.instant.details;
          days[date].temps.push(det.air_temperature);
          days[date].winds.push(det.wind_speed * 3.6);
          const p = ts.data.next_1_hours?.details?.precipitation_amount;
          if (p != null) days[date].rain += p;
          const sym = ts.data.next_1_hours?.summary?.symbol_code || ts.data.next_6_hours?.summary?.symbol_code;
          if (sym) {
            days[date].syms.push(sym);
            if (hour >= 11 && hour <= 13) days[date].noonSym = sym;
          }
        }

        const SL_DAYS = ['nedelja','ponedeljek','torek','sreda','četrtek','petek','sobota'];
        const SL_SYM = {
          clearsky:'jasno',fair:'pretežno jasno',partlycloudy:'delno oblačno',cloudy:'oblačno',
          fog:'megleno',lightrain:'rahel dež',rain:'dež',heavyrain:'močan dež',
          lightrainshowers:'manjše plohe',rainshowers:'plohe',heavyrainshowers:'močne plohe',
          lightsnow:'rahel sneg',snow:'sneg',heavysnow:'močan sneg',
          sleet:'dež s snegom',lightsleet:'rahel dež s snegom',
          thunderstorm:'nevihta',lightrainandthunder:'dež z grmevino',rainandthunder:'nevihte z dežjem',
        };
        const symLabel = c => {
          const b = (c||'').replace(/_day|_night|_polartwilight/g,'');
          return SL_SYM[b] || b.replace(/_/g,' ');
        };

        const todayKey = new Date(Date.now() + ljOff * 3600000).toISOString().slice(0, 10);
        const tomorrowKey = new Date(Date.now() + ljOff * 3600000 + 86400000).toISOString().slice(0, 10);

        // yr.no vrne časovno vrsto od TRENUTNE ure naprej, zato je "današnji"
        // max zvečer le max preostalih ur dneva (ob 22h npr. 26 °C na dan, ko
        // je postaja izmerila 36,8 °C). Ko je dnevni vrh mimo, ploščice ne
        // označimo več kot "danes", ampak kot "nocoj" — in takrat potrebujemo
        // pravi nočni minimum, ki sega čez polnoč do jutranjih ur.
        const todayFirstHour = days[todayKey]?.firstHour ?? 0;
        const partialToday = todayFirstHour >= 16;
        let nightMin = null;
        if (partialToday) {
          const nightTemps = [];
          for (const ts of timeseries) {
            const local = new Date(new Date(ts.time).getTime() + ljOff * 3600000);
            const date = local.toISOString().slice(0, 10);
            const hour = local.getUTCHours();
            if (date === todayKey || (date === tomorrowKey && hour <= 8)) {
              nightTemps.push(ts.data.instant.details.air_temperature);
            }
          }
          if (nightTemps.length) nightMin = Math.round(Math.min(...nightTemps));
        }

        const summaries = Object.entries(days)
          .filter(([d]) => d >= todayKey)
          .sort(([a],[b]) => a < b ? -1 : 1)
          .slice(0, 7)
          .map(([date, d]) => {
            const dt = new Date(date + 'T12:00:00');
            const rawSym = d.noonSym || d.syms[Math.floor(d.syms.length/2)] || 'partlycloudy_day';
            const isToday = date === todayKey;
            const isPartial = isToday && partialToday;
            return {
              date,
              dayName: isPartial ? 'nocoj' : isToday ? 'danes' : SL_DAYS[dt.getDay()],
              // Pri nepopolnem dnevu je max zavajajoč — vrh je že mimo.
              tmax: isPartial ? null : d.temps.length ? Math.round(Math.max(...d.temps)) : null,
              tmin: isPartial ? nightMin : d.temps.length ? Math.round(Math.min(...d.temps)) : null,
              partial: isPartial || undefined,
              windMax: d.winds.length ? Math.round(Math.max(...d.winds)) : null,
              rain: Math.round(d.rain * 10) / 10,
              symbol: rawSym,        // raw yr.no code (frontend maps to emoji)
              symbolText: symLabel(rawSym),
            };
          });

        if (!summaries.length) throw new Error("yr.no: no data");

        // 1) Lokalno besedilo za Rečico iz yr.no — to je vodilni odstavek
        // kartice. Zavihek se imenuje "Lokalna napoved", zato mora obiskovalec
        // najprej prebrati nekaj o Rečici, ne o Sloveniji.
        const parts = [];
        const s0 = summaries[0];
        if (s0) {
          if (s0.partial) {
            let p = `Nocoj bo na Rečici ob Savinji ${symLabel(s0.symbol)}`;
            if (s0.tmin != null) p += `, najnižja temperatura okoli ${s0.tmin} °C`;
            if (s0.rain >= 0.5) p += `, skupaj okoli ${s0.rain} mm padavin`;
            parts.push(p + ".");
          } else {
            let p = `Danes bo na Rečici ob Savinji ${symLabel(s0.symbol)}, s temperaturo med ${s0.tmin} in ${s0.tmax} °C`;
            if (s0.rain >= 0.5) p += `, skupaj okoli ${s0.rain} mm padavin`;
            if (s0.windMax >= 30) p += `, veter v sunkih do ${s0.windMax} km/h`;
            parts.push(p + ".");
          }
        }
        const s1 = summaries[1];
        if (s1) {
          let p = `Jutri ${symLabel(s1.symbol)}, ${s1.tmin}–${s1.tmax} °C`;
          if (s1.rain >= 0.5) p += `, dež ${s1.rain} mm`;
          parts.push(p + ".");
        }
        // Brief outlook for the rest of the period
        const rest = summaries.slice(2, 5);
        if (rest.length) {
          const trend = rest.map(s => `${s.dayName} ${symLabel(s.symbol)} (${s.tmax}°)`).join(", ");
          parts.push(`V nadaljevanju: ${trend}.`);
        }
        const local = parts.join(" ");

        // 2) Uradna ARSO napoved za Slovenijo — ločeno polje, da ne izrine
        // lokalnega besedila. Opozorila fetchArsoText() ne vrača; ta so v
        // traku na vrhu strani.
        let arso = null, arsoTitle = null;
        if (arsoTry.status === "fulfilled" && arsoTry.value?.text) {
          arso = arsoTry.value.text;
          arsoTitle = arsoTry.value.title || "ARSO";
        }

        return new Response(JSON.stringify({
          summaries, local, arso, arsoTitle, source: "yr.no",
          text: local,   // združljivost s starimi predpomnjenimi odjemalci
        }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-store" }
        });
      }

      // ── /ai-debug ─────────────────────────────────────────
      // Diagnostics: per-endpoint status + sample + extracted prose.
      if (path === "/ai-debug") {
        const out = [];
        for (const url of ARSO_TEXT_ENDPOINTS) {
          const rec = { url };
          try {
            const r = await _arsoFetch(url);
            rec.status = r.status;
            rec.contentType = r.headers.get("content-type") || "";
            const body = await r.text();
            rec.bodyLength = body.length;
            rec.bodyHead = body.slice(0, 700);
            rec.extracted = _arsoExtractProse(body, rec.contentType).slice(0, 3);
            // Naslovi sekcij, ki jih vidi _arsoFcastSections(). Če ARSO
            // preimenuje "NAPOVED ZA SLOVENIJO", se tu takoj vidi, zakaj je
            // napovedna kartica ostala prazna.
            if (/json/i.test(rec.contentType) || /^\s*[\{\[]/.test(body)) {
              try {
                const groups = _arsoFcastSections(JSON.parse(body));
                rec.sections = Object.fromEntries(
                  Object.entries(groups).map(([k, v]) => [k, { paras: v.length, head: (v[0] || "").slice(0, 120) }])
                );
              } catch (e) { rec.sectionsError = String(e); }
            }
          } catch (e) { rec.error = String(e); }
          out.push(rec);
        }
        // Also show raw warnings structure for debugging
        const warningsDebug = { url: "https://vreme.arso.gov.si/api/1.0/nonlocation/" };
        try {
          const r = await _arsoFetch("https://vreme.arso.gov.si/api/1.0/nonlocation/");
          warningsDebug.status = r.status;
          if (r.ok) {
            const data = await r.json();
            warningsDebug.topLevelKeys = Object.keys(data || {});
            // Show first 2000 chars of warning_si
            const wsi = data?.warning_si;
            warningsDebug.warning_si_raw = wsi
              ? JSON.stringify(wsi).slice(0, 2000)
              : "field 'warning_si' not found";
            try { warningsDebug.parsed = await fetchArsoWarnings(); } catch(e2) { warningsDebug.parseError = String(e2); }
          }
        } catch(e) { warningsDebug.error = String(e); }
        return new Response(JSON.stringify({ textEndpoints: out, warningsDebug }, null, 2), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-store" }
        });
      }

      // ── /metar ────────────────────────────────────────────
      if (path === "/metar") {
        const station = url.searchParams.get("ids") || "LJLJ";
        const hours   = url.searchParams.get("hours") || "2";
        // taf=true doda polje rawTaf: uradno letališko napoved za naslednjih
        // 24-30 ur. Stran je doslej brala samo trenutno stanje (rawOb).
        const metarUrl = `https://aviationweather.gov/api/data/metar?ids=${encodeURIComponent(station)}&format=json&taf=true&hours=${hours}`;
        const metarRes = await fetch(metarUrl, {
          headers: { "Accept": "application/json", "User-Agent": "meteorec.si/1.0" },
          cf: { cacheTtl: 600, cacheEverything: true },
        });
        if (!metarRes.ok) throw new Error("METAR HTTP " + metarRes.status);
        const metarData = await metarRes.text();
        return new Response(metarData, {
          headers: {
            ...CORS_ALLOWED,
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "public, max-age=600",
          },
        });
      }

      // ── /pozari ───────────────────────────────────────────
      // NASA FIRMS — dejansko zaznana požarišča (MODIS/VIIRS).
      // Stran indeks FWI že računa po metodologiji EFFIS iz modelskih
      // podatkov; to je torej ocena *nevarnosti*. FIRMS pove, ali kaj v resnici
      // gori — torej modelirano tveganje in resnično stanje eno ob drugem.
      //
      // Zahteva brezplačen MAP_KEY (skrivnost FIRMS_MAP_KEY v Cloudflare).
      // Brez njega vrnemo { configured: false } s statusom 200, da ospredje
      // kartico preprosto skrije, namesto da bi kazalo napako.
      if (path === "/pozari") {
        const KEY = env?.FIRMS_MAP_KEY;
        if (!KEY) {
          return new Response(JSON.stringify({ configured: false }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=3600" }
          });
        }
        const BBOX = "13.3,45.4,16.7,46.9";   // zahod,jug,vzhod,sever — Slovenija
        const DAYS = 3;                        // FIRMS dovoli 1–5
        const SOURCES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"];

        const rows = [];
        const seen = new Set();
        for (const src of SOURCES) {
          const u = `https://firms.modaps.eosdis.nasa.gov/api/area/csv/${KEY}/${src}/${BBOX}/${DAYS}`;
          let txt;
          try {
            const r = await fetch(u, { cf: { cacheTtl: 1800, cacheEverything: true } });
            if (!r.ok) continue;
            txt = await r.text();
          } catch (_) { continue; }
          // Ob neveljavnem ključu FIRMS vrne navadno besedilo, ne CSV.
          if (!txt || !/^latitude,/i.test(txt.trim())) continue;
          const lines = txt.trim().split("\n");
          const head = lines[0].split(",").map(s => s.trim());
          const ix = name => head.indexOf(name);
          const iLat = ix("latitude"), iLon = ix("longitude"), iDate = ix("acq_date"),
                iTime = ix("acq_time"), iConf = ix("confidence"), iFrp = ix("frp"),
                iDn = ix("daynight");
          if (iLat < 0 || iLon < 0) continue;
          for (let i = 1; i < lines.length; i++) {
            const c = lines[i].split(",");
            const lat = parseFloat(c[iLat]), lon = parseFloat(c[iLon]);
            if (!isFinite(lat) || !isFinite(lon)) continue;
            // Isti požar zaznata oba satelita; združimo po grobi celici in času.
            const k = lat.toFixed(3) + "," + lon.toFixed(3) + "," + (c[iDate] || "") + "," + (c[iTime] || "");
            if (seen.has(k)) continue;
            seen.add(k);
            rows.push({
              lat, lon,
              date: c[iDate] || null,
              time: c[iTime] || null,
              conf: iConf >= 0 ? (c[iConf] || "").trim() : null,
              frp: iFrp >= 0 ? parseFloat(c[iFrp]) : null,
              night: iDn >= 0 ? (c[iDn] || "").trim().toUpperCase() === "N" : null,
            });
          }
        }

        // Razdalja od postaje (haversine) — bralca zanima predvsem, kaj je blizu.
        const LAT0 = 46.325779, LON0 = 14.921137;
        const rad = d => d * Math.PI / 180;
        for (const f of rows) {
          const dLat = rad(f.lat - LAT0), dLon = rad(f.lon - LON0);
          const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(LAT0)) * Math.cos(rad(f.lat)) * Math.sin(dLon / 2) ** 2;
          f.dist = Math.round(2 * 6371 * Math.asin(Math.sqrt(a)));
        }
        rows.sort((a, b) => a.dist - b.dist);
        // VIIRS označuje zaupanje s črkami l/n/h, MODIS s številko 0–100.
        const isLow = f => f.conf === "l" || (/^\d+$/.test(f.conf || "") && Number(f.conf) < 30);
        const solid = rows.filter(f => !isLow(f));

        return new Response(JSON.stringify({
          configured: true,
          total: rows.length,
          confident: solid.length,
          nearest: solid[0] || rows[0] || null,
          within50: solid.filter(f => f.dist <= 50).length,
          fires: rows.slice(0, 40),
          days: DAYS,
          source: "NASA FIRMS · VIIRS S-NPP + NOAA-20",
        }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=1800" }
        });
      }

      // ── /sondaza ──────────────────────────────────────────
      // Radiosondaža: izmerjen navpični profil ozračja.
      //
      // Slovenija nima operativne radiosondaže — Ljubljana (WMO 14015) pri
      // UWYO vrne "Unable to retrieve the data" — zato beremo Zagreb (najbližja,
      // ~100 km JV), z Videmom/Rivolto kot rezervo (~150 km Z, gorvodno ob
      // jugozahodnem dotoku).
      //
      // UWYO je vmes prenovil naslove (stari /cgi-bin/sounding vrača 404, nov
      // je /wsgi/sounding) in v besedilnem izpisu ne vrača več izračunanih
      // indeksov, ampak samo profil. CAPE stran že ima iz modela Open-Meteo,
      // zato tu računamo tisto, česar drugje ni in je neposredno berljivo iz
      // meritve: vsebnost vode v stolpcu, temperaturni gradient, višine izoterm
      // (cona rasti toče) in strižni veter.
      if (path === "/sondaza") {
        const STATIONS = [
          { id: "14240", name: "Zagreb", full: "Zagreb/Maksimir", dist: 100, dir: "JV" },
          { id: "16045", name: "Videm",  full: "Udine/Rivolto",   dist: 150, dir: "Z"  },
        ];
        // Sondaže ob 00 in 12 UTC so dosegljive približno dve uri po spustu.
        const now = new Date();
        const cands = [];
        for (let back = 0; back < 3; back++) {
          const d = new Date(now.getTime() - back * 12 * 3600 * 1000);
          const hh = d.getUTCHours() >= 14 ? 12 : d.getUTCHours() >= 2 ? 0 : 12;
          const day = new Date(d);
          if (d.getUTCHours() < 2) day.setUTCDate(day.getUTCDate() - 1);
          const ds = day.toISOString().slice(0, 10);
          const key = ds + " " + String(hh).padStart(2, "0") + ":00:00";
          if (!cands.includes(key)) cands.push(key);
        }

        const parseRows = (html) => {
          const m = html.match(/<PRE>([\s\S]*?)<\/PRE>/i);
          if (!m) return [];
          const rows = [];
          for (const line of m[1].replace(/&[a-z]+;/g, " ").split("\n")) {
            if (!/^\s*\d/.test(line)) continue;
            // Izpis ima fiksne širine 7 znakov; prazno polje pomeni manjkajočo meritev.
            const col = i => { const s = line.slice(i * 7, i * 7 + 7).trim(); return s === "" ? null : parseFloat(s); };
            const r = { p: col(0), z: col(1), t: col(2), td: col(3), mixr: col(5), dir: col(6), spd: col(7) };
            if (r.p == null || r.z == null || !isFinite(r.p) || !isFinite(r.z)) continue;
            rows.push(r);
          }
          return rows;
        };
        const atP = (rows, p, key) => {
          for (let i = 1; i < rows.length; i++) {
            const a = rows[i - 1], b = rows[i];
            if (a[key] == null || b[key] == null) continue;
            if (a.p >= p && b.p <= p) {
              const f = (Math.log(a.p) - Math.log(p)) / (Math.log(a.p) - Math.log(b.p));
              return a[key] + f * (b[key] - a[key]);
            }
          }
          return null;
        };
        const levelOfT = (rows, target) => {
          for (let i = 1; i < rows.length; i++) {
            const a = rows[i - 1], b = rows[i];
            if (a.t == null || b.t == null) continue;
            if (a.t >= target && b.t <= target) {
              const f = (a.t - target) / (a.t - b.t);
              return a.z + f * (b.z - a.z);
            }
          }
          return null;
        };
        // PWAT = (1/(g·ρw))·∫w dp; z mixr v g/kg in dp v hPa se to skrči na Σ(mixr·dp)/98,1 [mm].
        const pwat = (rows) => {
          let s = 0;
          for (let i = 1; i < rows.length; i++) {
            const a = rows[i - 1], b = rows[i];
            if (a.mixr == null || b.mixr == null) continue;
            const dp = a.p - b.p;
            if (dp <= 0) continue;
            s += ((a.mixr + b.mixr) / 2) * dp;
          }
          return s / 98.1;
        };
        const windAt = (rows, z) => {
          let best = null, bd = 1e9;
          for (const r of rows) {
            if (r.spd == null || r.dir == null) continue;
            const d = Math.abs(r.z - z);
            if (d < bd) { bd = d; best = r; }
          }
          if (!best || bd > 600) return null;
          const rad = best.dir * Math.PI / 180;
          return { u: -best.spd * Math.sin(rad), v: -best.spd * Math.cos(rad) };
        };

        let used = null, rows = [];
        outer:
        for (const st of STATIONS) {
          for (const when of cands) {
            const u = "https://weather.uwyo.edu/wsgi/sounding?datetime=" + encodeURIComponent(when)
                    + "&id=" + st.id + "&type=TEXT:LIST&src=UNKNOWN";
            let r;
            try { r = await fetch(u, { headers: { "User-Agent": "meteorec.si/1.0" }, cf: { cacheTtl: 3600, cacheEverything: true } }); }
            catch (_) { continue; }
            if (!r.ok) continue;
            const html = await r.text();
            const parsed = parseRows(html);
            // Kratek profil pomeni okrnjen spust; tak ni uporaben za višinske izoterme.
            if (parsed.length < 200) continue;
            rows = parsed; used = { ...st, when };
            break outer;
          }
        }
        if (!used) {
          return new Response(JSON.stringify({ error: "Sondaža trenutno ni dosegljiva" }), {
            status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
        }

        const sfc = rows[0];
        const t850 = atP(rows, 850, "t"), t500 = atP(rows, 500, "t");
        const z850 = atP(rows, 850, "z"), z500 = atP(rows, 500, "z");
        const lapse = (t850 != null && t500 != null && z850 != null && z500 != null && z500 > z850)
          ? (t850 - t500) / ((z500 - z850) / 1000) : null;
        const fz = levelOfT(rows, 0), m10 = levelOfT(rows, -10), m30 = levelOfT(rows, -30);
        const w0 = windAt(rows, sfc.z), w6 = windAt(rows, sfc.z + 6000);
        const shear = (w0 && w6) ? Math.hypot(w6.u - w0.u, w6.v - w0.v) : null;
        const r1 = v => v == null ? null : Math.round(v * 10) / 10;

        return new Response(JSON.stringify({
          station: used.name, stationFull: used.full, dist: used.dist, dirFrom: used.dir,
          time: used.when, levels: rows.length,
          sfcTemp: r1(sfc.t), sfcDew: r1(sfc.td),
          t850: r1(t850), t500: r1(t500),
          lapse: r1(lapse),
          pwat: r1(pwat(rows)),
          freezing: fz == null ? null : Math.round(fz),
          hailFrom: m10 == null ? null : Math.round(m10),
          hailTo:   m30 == null ? null : Math.round(m30),
          shear: r1(shear), shearKmh: shear == null ? null : Math.round(shear * 3.6),
          source: "University of Wyoming · radiosondaža",
        }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=3600" }
        });
      }

      // ── /vesoljsko-vreme ──────────────────────────────────
      // NOAA SWPC — planetarni indeks Kp in verjetnost polarnega sija.
      // Brez ključa. Kp forecast vsebuje tako izmerjene kot napovedane
      // tritourne vrednosti, zato zadošča en klic.
      //
      // Verjetnosti sija NE računamo iz lastne tabele Kp→širina, ampak jo
      // preberemo iz OVATION modela za točko nad Slovenijo. Datoteka je ~900 kB,
      // zato jo obdela worker, brskalniku pa pošlje samo izvleček.
      if (path === "/vesoljsko-vreme") {
        const SI_LAT = 46, SI_LON = 15;
        const [kpRes, ovRes] = await Promise.all([
          fetch("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
            { cf: { cacheTtl: 900, cacheEverything: true } }),
          fetch("https://services.swpc.noaa.gov/json/ovation_aurora_latest.json",
            { cf: { cacheTtl: 900, cacheEverything: true } }).catch(() => null),
        ]);
        if (!kpRes.ok) throw new Error("SWPC Kp HTTP " + kpRes.status);
        const kpRaw = await kpRes.json();
        const rows = (Array.isArray(kpRaw) ? kpRaw : []).filter(r => r && r.time_tag && r.kp != null);
        const observed  = rows.filter(r => r.observed === "observed");
        const predicted = rows.filter(r => r.observed !== "observed");
        const now = observed.length ? observed[observed.length - 1] : null;
        // Najvišja napovedana vrednost pove, ali se sploh splača spremljati.
        let peak = null;
        for (const r of predicted) if (!peak || Number(r.kp) > Number(peak.kp)) peak = r;

        let auroraProb = null, ovTime = null;
        try {
          if (ovRes && ovRes.ok) {
            const ov = await ovRes.json();
            ovTime = ov["Forecast Time"] || ov["Observation Time"] || null;
            for (const p of (ov.coordinates || [])) {
              if (p[1] === SI_LAT && p[0] === SI_LON) { auroraProb = p[2]; break; }
            }
          }
        } catch (_) { /* Kp je uporaben tudi brez OVATION */ }

        // Kp je logaritemska lestvica; pragovi so postavljeni po tem, kaj je
        // s 46° s. š. res vidno. Sij nad Slovenijo je izjemen dogodek —
        // maja 2024 (Kp 9) je bil viden kot rdeč sij nizko nad severnim obzorjem.
        const kpNow = now ? Number(now.kp) : null;
        const kpPeak = peak ? Number(peak.kp) : null;
        const level = k =>
          k == null ? { key: "unknown", label: "ni podatka",        si: "—" } :
          k >= 8    ? { key: "extreme", label: "huda nevihta",      si: "Rdeč sij nizko nad severnim obzorjem je mogoč — kot maja 2024." } :
          k >= 7    ? { key: "strong",  label: "močna nevihta",     si: "Zelo majhna možnost šibkega sija nizko na severu." } :
          k >= 5    ? { key: "storm",   label: "geomagnetna nevihta", si: "S Slovenije sij še ni viden; oval je nad Skandinavijo." } :
          k >= 4    ? { key: "active",  label: "aktivno",           si: "Sij ni viden pri nas." } :
                      { key: "quiet",   label: "mirno",             si: "Sij ni viden pri nas." };
        return new Response(JSON.stringify({
          kpNow, kpNowTime: now?.time_tag || null,
          kpPeak, kpPeakTime: peak?.time_tag || null,
          nowLevel: level(kpNow), peakLevel: level(kpPeak),
          auroraProb, auroraTime: ovTime,
          history: observed.slice(-16).map(r => ({ t: r.time_tag, kp: Number(r.kp) })),
          forecast: predicted.slice(0, 24).map(r => ({ t: r.time_tag, kp: Number(r.kp) })),
          source: "NOAA SWPC · planetarni Kp + OVATION",
        }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=900" }
        });
      }

      // ── /satelit-sonce ────────────────────────────────────
      // Open-Meteo Satellite Radiation API (EUMETSAT SARAH-3 / MSG, DWD MTG).
      // Za razliko od napovednega obsevanja je to *izmerjeno* s satelita.
      // Vrne dnevno energijo in indeks jasnine (dejansko/ob jasnem nebu) ter
      // današnjo urno krivuljo, poravnano s postajnim senzorjem.
      //
      // POZOR pri primerjavi s postajo: WU poroča solarRadiationHigh, torej
      // urni MAKSIMUM, satelit pa urno POVPREČJE. Ti dve količini nista
      // primerljivi: ob spremenljivi oblačnosti je maksimum znotraj ure lahko
      // 30–40 % nad povprečjem, ob jasnem nebu pa le nekaj odstotkov. Razlika
      // torej meri variabilnost oblačnosti, ne razlike med satelitom in tlemi,
      // zato iz nje NE računamo nobenega kazalnika. Postajno vrsto vrnemo samo
      // za vizualno primerjavo v grafu, izrecno označeno kot urni maksimum.
      if (path === "/satelit-sonce") {
        const satUrl = "https://satellite-api.open-meteo.com/v1/archive"
          + "?latitude=46.325779&longitude=14.921137"
          + "&hourly=shortwave_radiation,shortwave_radiation_clear_sky,sunshine_duration"
          + "&models=satellite_radiation_seamless&past_days=7&forecast_days=1"
          + "&timezone=Europe%2FLjubljana";
        const [satRes, wuRes] = await Promise.all([
          fetch(satUrl, { cf: { cacheTtl: 1800, cacheEverything: true } }),
          fetch(HOURLY_URL, { headers: { "Accept": "application/json" } }).catch(() => null),
        ]);
        if (!satRes.ok) throw new Error("Satellite API HTTP " + satRes.status);
        const sat = await satRes.json();
        const H = sat.hourly || {};
        const times = H.time || [], ghi = H.shortwave_radiation || [],
              clr = H.shortwave_radiation_clear_sky || [], sun = H.sunshine_duration || [];

        // Postajni senzor po urah: ključ "YYYY-MM-DDTHH:00". WU žigosa meritev
        // na koncu ure (HH:59), zato jo pripišemo uri, ki se takrat izteka.
        const stByHour = {};
        try {
          const wu = wuRes && wuRes.ok ? await wuRes.json() : null;
          for (const o of (wu?.observations || [])) {
            const v = o?.solarRadiationHigh;
            if (v == null || !o.obsTimeLocal) continue;
            stByHour[o.obsTimeLocal.slice(0, 13).replace(" ", "T") + ":00"] = v;
          }
        } catch (_) { /* postaja ni nujna — satelit deluje sam zase */ }

        const days = {};
        const todayStr = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Ljubljana" });
        const todayHours = [];
        for (let i = 0; i < times.length; i++) {
          const t = times[i], d = t.slice(0, 10), hr = parseInt(t.slice(11, 13), 10);
          const g = ghi[i], c = clr[i];
          if (g == null || c == null) continue;
          const st = stByHour[t] ?? null;
          if (!days[d]) days[d] = { date: d, ghi: 0, clear: 0, sunSec: 0 };
          const D = days[d];
          D.ghi += g; D.clear += c; D.sunSec += (sun[i] || 0);
          if (d === todayStr) todayHours.push({ h: hr, ghi: Math.round(g), clear: Math.round(c), station: st != null ? Math.round(st) : null });
        }
        const daily = Object.values(days).sort((a, b) => a.date < b.date ? -1 : 1).map(D => ({
          date: D.date,
          kwh:   Math.round(D.ghi) / 1000,           // Wh/m² → kWh/m²
          // Indeks jasnine je razmerje, zato je smiseln tudi za tekoči dan;
          // energija in ure sonca pa se do konca dneva še naberejo.
          index: D.clear > 0 ? Math.round(D.ghi / D.clear * 100) / 100 : null,
          sunHours: Math.round(D.sunSec / 360) / 10,
          partial: D.date === todayStr,
        }));
        return new Response(JSON.stringify({
          daily, today: todayHours,
          source: "Open-Meteo Satellite Radiation · EUMETSAT/DWD",
        }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=1800" }
        });
      }

      // ── /cezmejno ─────────────────────────────────────────
      // GeoSphere Austria (TAWES, 10-min) — čezmejni "gorvodni" signal.
      // Rečica leži južno od Karavank/Kamniško-Savinjskih Alp; ob severnem
      // dotoku zrak pride čez greben. Postaje severno od grebena zato
      // povedo, kaj prihaja, uro ali dve preden to izmerimo doma.
      // Ključ ni potreben. GET /cezmejno → { stations: [...], updatedAt }
      if (path === "/cezmejno") {
        // loc = sklanjano ime za stavke, dist = zračna razdalja od IREICA1,
        // role pojasni, zakaj je postaja na seznamu.
        const AT_STATIONS = [
          { id: "11234", name: "Železna Kapla",  at: "Bad Eisenkappel", alt: 623,  dist: 31, role: "greben" },
          { id: "11232", name: "Pliberk",        at: "Feistritz o. Bleiburg", alt: 522, dist: 29, role: "dolina" },
          { id: "11217", name: "Ljubelj",        at: "Loibl/Tunnel",   alt: 1097, dist: 53, role: "prelaz" },
          { id: "11331", name: "Celovec",        at: "Klagenfurt",     alt: 450,  dist: 58, role: "kotlina" },
          { id: "11214", name: "Preitenegg",     at: "Preitenegg",     alt: 1059, dist: 68, role: "greben" },
        ];
        const PARAMS = "TL,RF,FF,FFX,DD,P,RR,SO";
        const gsUrl = "https://dataset.api.hub.geosphere.at/v1/station/current/tawes-v1-10min"
          + "?station_ids=" + AT_STATIONS.map(s => s.id).join(",")
          + "&parameters=" + PARAMS;
        const gsRes = await fetch(gsUrl, {
          headers: { "Accept": "application/json", "User-Agent": "meteorec.si/1.0" },
          cf: { cacheTtl: 300, cacheEverything: true },
        });
        if (!gsRes.ok) throw new Error("GeoSphere HTTP " + gsRes.status);
        const gs = await gsRes.json();
        // Zadnji časovni korak je pogosto še nepopoln (null), zato za vsak
        // parameter vzamemo zadnjo vrednost, ki ni null.
        const lastVal = p => {
          const arr = p?.data || [];
          for (let i = arr.length - 1; i >= 0; i--) if (arr[i] !== null) return arr[i];
          return null;
        };
        const byId = {};
        for (const f of (gs.features || [])) byId[String(f.properties?.station)] = f.properties?.parameters || {};
        const stations = AT_STATIONS.map(s => {
          const p = byId[s.id] || {};
          const ms = lastVal(p.FF), gust = lastVal(p.FFX);
          return {
            ...s,
            temp:     lastVal(p.TL),
            humidity: lastVal(p.RF),
            // TAWES poroča veter v m/s; doma povsod uporabljamo km/h.
            wind:     ms   != null ? Math.round(ms   * 3.6 * 10) / 10 : null,
            gust:     gust != null ? Math.round(gust * 3.6 * 10) / 10 : null,
            dir:      lastVal(p.DD),
            pressure: lastVal(p.P),
            rain10:   lastVal(p.RR),
          };
        });
        return new Response(JSON.stringify({
          stations,
          updatedAt: (gs.timestamps || []).slice(-1)[0] || null,
          source: "GeoSphere Austria · TAWES",
        }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=300" }
        });
      }

      // ── /radar-composite ──────────────────────────────────
      // Lasten kompozit padavin (ARSO jedro + OPERA obroč) kot paletni PNG v
      // Web Mercatorju; .json vrne meje, legendo in čas posnetka.
      if (path === "/radar-composite" || path === "/radar-composite.json") {
        const vid = COMP_VIEWS[url.searchParams.get("pogled")] ? url.searchParams.get("pogled") : COMP_VIEW_DEFAULT;
        const V = COMP_VIEWS[vid];
        if (path.endsWith(".json")) {
          const keys = await _operaKeys();
          let stamps = keys.map(_compStamp).filter(Boolean);
          // OPERA je zunanji vir in včasih obstane za ure; ARSO pa v tem
          // primeru večinoma teče naprej, zato brez OPERA sestavimo
          // časovnico kar iz njega (glej _arsoLatestMs).
          if (!stamps.length) {
            const arsoMs = await _arsoLatestMs();
            if (arsoMs) {
              stamps = [];
              for (let t = arsoMs - (COMP_ANIM_MIN - 5) * 60000; t <= arsoMs; t += ARSO_STEP_MS) {
                stamps.push(_msToStamp(t));
              }
            }
          }
          const stamp = stamps.length ? stamps[stamps.length - 1] : null;
          const ms = stamp ? _compStampMs(stamp) : NaN;
          // Okvirji animacije: zadnja ura, od najstarejšega proti zdaj.
          const od = ms - COMP_ANIM_MIN * 60000;
          const okvirji = stamps.filter(s => _compStampMs(s) >= od).map(s => ({
            zig: s, cas: new Date(_compStampMs(s)).toISOString(),
          }));
          // Nadaljevanje časovnice z ICON napovedjo — samo na pogledu
          // "savinja" in samo če ni starejša od 90 min (glej _cronRenderIcon).
          let napoved = null;
          if (vid === "savinja") {
            try {
              const o = await env?.PHOTOS_R2?.get(`${ICON_R2_PREFIX}latest.json`);
              if (o) {
                const m = JSON.parse(await o.text());
                const genMs = new Date(m.cas).getTime();
                if (!Number.isNaN(genMs) && Date.now() - genMs < 90 * 60000) {
                  napoved = { slika: "/icon-precip", okvirji: m.okvirji, korak_min: 60 };
                }
              }
            } catch (_) {}
          }
          return new Response(JSON.stringify({
            slika: "/radar-composite",
            cas: Number.isNaN(ms) ? null : new Date(ms).toISOString(),
            starost_min: Number.isNaN(ms) ? null : Math.round((Date.now() - ms) / 60000),
            okvirji,
            napoved,
            korak_min: 5,
            pogled: vid,
            pogledi: Object.entries(COMP_VIEWS).map(([id, v]) => ({
              id, ime: v.ime,
              meje: [[v.lat0, v.lon0], [v.lat1, v.lon1]],
              km_px: Number(((v.lon1 - v.lon0) * COMP_KM_LON / v.w).toFixed(3)),
            })),
            meje: [[V.lat0, V.lon0], [V.lat1, V.lon1]],
            projekcija: "EPSG:3857",
            sirina: V.w,
            legenda: COMP_MMH.map((mmh, i) => ({
              mmh,
              barva: "#" + COMP_RGB[i].map(v => v.toString(16).padStart(2, "0")).join(""),
            })),
            viri: [
              { ime: "ARSO", opis: "kompozit padavin, ~0,5 km", vloga: "Slovenija in 120 km naokoli" },
              { ime: "EUMETNET OPERA", opis: "CIRRUS DBZH, 1 km, CC BY 4.0", vloga: "širša okolica" },
            ],
          }), { headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=120" } });
        }
        // ?t=YYYYMMDDThhmm izriše določen okvir animacije; brez njega zadnjega.
        // Starih okvirjev ne dovolimo poljubno daleč nazaj, ker bi vsak zgrešen
        // ključ pomenil nov izris.
        const tParam = url.searchParams.get("t");
        if (tParam && !/^\d{8}T\d{4}$/.test(tParam)) {
          return new Response(JSON.stringify({ error: "neveljaven t" }), {
            status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
        if (tParam) {
          const ms = _compStampMs(tParam);
          if (Number.isNaN(ms) || Date.now() - ms > COMP_KEEP_MS || ms > Date.now() + 6e5) {
            return new Response(JSON.stringify({ error: "t je zunaj animacije" }), {
              status: 404, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
            });
          }
        }
        const c = await _radarCompositeCached(env, tParam, vid);
        return new Response(c.body, {
          headers: {
            ...CORS_ALLOWED,
            "Content-Type": "image/png",
            // Star okvir se ne spremeni več, zato ga sme brskalnik hraniti dolgo.
            "Cache-Control": tParam ? "public, max-age=86400, immutable" : "public, max-age=120",
            "X-Radar-Stamp": c.stamp || "",
            "X-Radar-Viri": `arso=${c.meta?.arso ?? "?"} opera=${c.meta?.opera ?? "?"}`,
            "X-Radar-Pogled": vid,
            "X-Radar-Cache": c.cached ? "hit" : "miss",
          },
        });
      }

      // ── /icon-precip ────────────────────────────────────────
      // Nadaljevanje radarske časovnice: 6h ICON napoved padavin za dolino
      // (samo pogled "savinja"), izrisana z isto paleto kot kompozit. ?t=
      // je obvezen, oblika <runStamp>-h<N> — iz /radar-composite.json →
      // napoved.okvirji.
      if (path === "/icon-precip") {
        const t = url.searchParams.get("t");
        if (!t || !/^\d{8}T\d{4}-h[1-6]$/.test(t)) {
          return new Response(JSON.stringify({ error: "neveljaven t" }), {
            status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
        const r2 = env?.PHOTOS_R2;
        const o = r2 ? await r2.get(`${ICON_R2_PREFIX}frame-${t}.png`).catch(() => null) : null;
        if (!o) {
          return new Response(JSON.stringify({ error: "okvir ni na voljo" }), {
            status: 404, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
        return new Response(o.body, {
          headers: { ...CORS_ALLOWED, "Content-Type": "image/png", "Cache-Control": "public, max-age=86400, immutable" },
        });
      }

      // ── /radar-cells.json ────────────────────────────────────
      // Sledenje posameznim nevihtnim celicam (za razliko od nowcasta, ki
      // oceni en skupen premik polja): id, lega, površina, jakost, smer in
      // hitrost vsake celice nad pragom nevihte, osveženo vsakih 5 minut
      // skupaj s "sirok" kompozitom.
      if (path === "/radar-cells.json") {
        const r2 = env?.PHOTOS_R2;
        let data = null;
        try {
          const o = r2 ? await r2.get(CELL_R2_LATEST) : null;
          if (o) data = JSON.parse(await o.text());
        } catch (_) {}
        const genMs = data ? new Date(data.cas).getTime() : NaN;
        if (!data || Number.isNaN(genMs) || Date.now() - genMs > 15 * 60000) {
          return new Response(JSON.stringify({ celice: [], cas: null, prihaja: null, opozorilo: "celice trenutno niso na voljo" }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=60" },
          });
        }
        return new Response(JSON.stringify(data), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=120" },
        });
      }

      // ── /arso-radar ───────────────────────────────────────
      if (path === "/arso-radar") {
        const radarRes = await fetch(
          "https://meteo.arso.gov.si/uploads/probase/www/observ/radar/si0-rm-anim.gif",
          { headers: { "Referer": "https://meteo.arso.gov.si/" } }
        );
        if (!radarRes.ok) throw new Error("ARSO radar HTTP " + radarRes.status);
        const buf = await radarRes.arrayBuffer();
        return new Response(buf, {
          headers: { ...CORS_ALLOWED, "Content-Type": "image/gif", "Cache-Control": "public, max-age=300" }
        });
      }

      // ── /arso-cam ─────────────────────────────────────────
      // ARSO ne objavlja več slike na stalnem naslovu. Posnetki so zdaj
      // časovno žigosani (siwc_YYYYMMDD-HHMM_POSTAJA_smer.jpg) in edini način,
      // da dobiš zadnjega, je seznam webcam_list — ta pove tudi, katera
      // postajna oznaka trenutno velja (CELJE je npr. postal CELJE_MEDLOG).
      //
      // ?kamera= sprejme ime kraja ali ARSO oznako, ?smer= stran neba.
      // Privzeta je Logarska dolina — edina kamera v naši dolini.
      if (path === "/arso-cam") {
        const wanted = (url.searchParams.get("kamera") || url.searchParams.get("station") || "Logarska dolina").toLowerCase();
        const wantDir = (url.searchParams.get("smer") || url.searchParams.get("dir") || "").replace(/[^a-z]/gi, "").toLowerCase();

        const listRes = await fetch("https://vreme.arso.gov.si/api/1.0/webcam_list/?lang=sl", {
          headers: { "User-Agent": "Mozilla/5.0", "Referer": "https://vreme.arso.gov.si/" },
          cf: { cacheTtl: 300, cacheEverything: true },
        });
        if (!listRes.ok) throw new Error("Seznam kamer ni dostopen: HTTP " + listRes.status);
        const list = await listRes.json();

        const cams = list?.webcam_list?.features ?? [];

        // Zadnji posnetek kamere; vrne null, če jih nima nobenih. directions
        // našteje vse smeri, ki jih kamera premore, webcam_list pa skoraj
        // vedno nosi posnetke le za eno od njih (48 od 51 kamer), zato se
        // zahtevana smer upošteva le, kadar posnetke res ima.
        const zadnji = (f, prefDir) => {
          const dirs = f.properties?.directions ?? [];
          const framesFor = (dd) => list[`webcam_${f.properties.id}${dd}_data.json`] ?? [];
          const dd = (dirs.includes(prefDir) && framesFor(prefDir).length)
            ? prefDir
            : dirs.find((x) => framesFor(x).length);
          if (!dd) return null;
          const fr = framesFor(dd);
          const l = fr[fr.length - 1];
          return l?.path ? { smer: dd, ...l } : null;
        };

        const opis = (f, z) => ({
          kamera: f.properties.title,
          obmocje: f.properties.parent_title || "",
          smer: z.smer,
          posnet: z.valid || null,
          slika: `/arso-cam?kamera=${encodeURIComponent(f.properties.title)}&smer=${z.smer}`,
        });

        // ?obmocje= vrne vse kamere regije, ki posnetek res imajo — stran tako
        // z eno zahtevo dobi celotno mrežo, namesto po ena na kamero.
        const obmocje = url.searchParams.get("obmocje");
        if (obmocje) {
          const o = obmocje.toLowerCase();
          const kamere = cams
            .filter((f) => (f.properties?.parent_title || "").toLowerCase() === o)
            .map((f) => { const z = zadnji(f, wantDir); return z ? opis(f, z) : null; })
            .filter(Boolean);
          return new Response(JSON.stringify({ obmocje, kamere }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=300" }
          });
        }

        const cam = cams.find((f) => (f.properties?.title || "").toLowerCase() === wanted)
          || cams.find((f) => (f.properties?.id || "").toLowerCase() === wanted)
          || cams.find((f) => (f.properties?.title || "").toLowerCase().includes(wanted));
        if (!cam) {
          return new Response(JSON.stringify({
            error: "Kamera ni najdena",
            nakamere: cams.map((f) => f.properties?.title).filter(Boolean),
          }), { status: 404, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }

        const last = zadnji(cam, wantDir);
        if (!last) {
          // Nekaj kamer (npr. Ptuj, Bovec) je v seznamu, a brez posnetkov.
          return new Response(JSON.stringify({
            error: "Kamera trenutno nima posnetkov",
            kamera: cam.properties.title,
          }), { status: 404, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }
        const dir = last.smer;

        // ?format=json vrne le opis posnetka. Stran ga potrebuje za podnapis
        // (kdaj je bil posnet), sliko pa naloži z <img> na isti endpoint —
        // brskalnik custom glav navzkrižno tako ali tako ne sme brati.
        if (url.searchParams.get("format") === "json") {
          return new Response(JSON.stringify(opis(cam, last)), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=300" }
          });
        }

        const camRes = await fetch("https://vreme.arso.gov.si" + last.path, {
          headers: { "User-Agent": "Mozilla/5.0", "Referer": "https://vreme.arso.gov.si/" },
        });
        if (!camRes.ok) throw new Error("Kamera ni dostopna: HTTP " + camRes.status);
        return new Response(await camRes.arrayBuffer(), {
          headers: {
            ...CORS_ALLOWED,
            "Content-Type": "image/jpeg",
            "Cache-Control": "public, max-age=300",
            "X-Kamera": cam.properties.title,
            "X-Smer": dir || "",
            "X-Posnet": last.valid || "",
          }
        });
      }

      // ── /nasa-power ──────────────────────────────────────
      if (path === "/nasa-power") {
        const qtype = new URL(request.url).searchParams.get("type") || "solar";
        const BASE = "https://power.larc.nasa.gov/api/temporal";
        const LAT_P = "46.3258", LON_P = "14.9211";
        const yr = new Date().getFullYear();
        const urlMap = {
          solar: [
            `${BASE}/monthly/point?parameters=ALLSKY_SFC_SW_DWN&latitude=${LAT_P}&longitude=${LON_P}&start=${yr-1}&end=${yr}&community=RE&format=JSON`,
            `${BASE}/climatology/point?parameters=ALLSKY_SFC_SW_DWN&latitude=${LAT_P}&longitude=${LON_P}&community=RE&format=JSON`,
          ],
          baselines: [
            `${BASE}/climatology/point?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR&latitude=${LAT_P}&longitude=${LON_P}&community=AG&format=JSON`,
          ],
          agro: [
            `${BASE}/climatology/point?parameters=EVPTRNS,ALLSKY_SFC_PAR_TOT,FROST_DAYS&latitude=${LAT_P}&longitude=${LON_P}&community=AG&format=JSON`,
          ],
        };
        const urls = urlMap[qtype] || urlMap.solar;
        try {
          const grab = u => fetch(u, { headers: { "User-Agent": "Mozilla/5.0" } })
            .then(r => r.ok ? r.json() : null)
            .catch(() => null);
          const results = await Promise.all(urls.map(grab));
          // POWER mesečne agregate objavlja z zamikom več mesecev. Če zahtevamo
          // končno leto, ki ga še ni, zavrne CELOTNO zahtevo (422), ne le
          // manjkajočega dela — zato ob neuspehu poskusimo še z letom prej.
          if (qtype === "solar" && !results[0]) {
            // Cel par premaknemo leto nazaj, ne le konca — sicer bi ostalo eno
            // samo leto in primerjava "isti mesec lani" ne bi imela s čim.
            results[0] = await grab(urls[0].replace(`start=${yr - 1}`, `start=${yr - 2}`)
                                           .replace(`end=${yr}`, `end=${yr - 1}`));
          }
          // Namenoma NE uporabimo filter(Boolean): ta ob neuspehu prvega klica
          // premakne indekse, ospredje pa bi klimatologijo prebralo kot mesečni
          // niz in tiho narisalo prazen graf. Mesta zato ohranimo.
          return new Response(JSON.stringify(results.map(r => r ?? null)), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=14400" },
          });
        } catch(e) {
          return new Response(JSON.stringify({ error: e.message }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
      }

      // ── /pvgis ───────────────────────────────────────────
      if (path === "/pvgis") {
        // API v5_2 baze PVGIS-SARAH3 ne pozna (dovoli le NSRDB/ERA5/SARAH2) in
        // vrne 400; SARAH3 je na voljo šele od v5_3 naprej.
        // Brez horirrad=1 MRcalc vrne zapise samo z letnico in mesecem, brez
        // vrednosti obsevanja.
        const pvgisUrl = `https://re.jrc.ec.europa.eu/api/v5_3/MRcalc?lat=46.3258&lon=14.9211&outputformat=json&raddatabase=PVGIS-SARAH3&horirrad=1&browser=0`;
        try {
          const r = await fetch(pvgisUrl, { headers: { "User-Agent": "Mozilla/5.0" } });
          if (!r.ok) throw new Error("HTTP " + r.status);
          const raw = await r.json();
          // MRcalc vrne ~19 let posameznih mesecev v kWh/m² na MESEC, ospredje
          // pa riše 12-mesečno klimatologijo v kWh/m² na DAN. Povprečimo čez
          // leta in delimo z dolžino meseca, ter oddamo v obliki, ki jo
          // ospredje že zna izrisati.
          const DPM = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
          const sums = Array.from({ length: 12 }, () => ({ s: 0, n: 0 }));
          for (const rec of (raw?.outputs?.monthly || [])) {
            const mo = Number(rec?.month), v = Number(rec?.["H(h)_m"]);
            if (!(mo >= 1 && mo <= 12) || !isFinite(v)) continue;
            sums[mo - 1].s += v; sums[mo - 1].n++;
          }
          const fixed = sums.map((o, i) => ({
            month: i + 1,
            H_h: o.n ? Math.round((o.s / o.n / DPM[i]) * 1000) / 1000 : null,
          }));
          const withData = fixed.filter(m => m.H_h != null);
          // Letno povprečje dnevnega obsevanja: vsota mesečnih vsot / 365.
          const annualDaily = withData.length === 12
            ? Math.round(fixed.reduce((a, m, i) => a + m.H_h * DPM[i], 0) / 365.25 * 1000) / 1000
            : null;
          const data = {
            outputs: {
              monthly: { fixed },
              totals: { fixed: annualDaily != null ? { H_h: annualDaily } : {} },
            },
            meta: { years: raw?.inputs?.meteo_data, database: "PVGIS-SARAH3", api: "v5_3" },
          };
          return new Response(JSON.stringify(data), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=604800" },
          });
        } catch(e) {
          return new Response(JSON.stringify({ error: e.message }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
      }

      // ── /enso ────────────────────────────────────────────
      // ── /nao ──────────────────────────────────────────────
      // Severnoatlantska oscilacija. Za srednjeevropske zime pomeni bistveno
      // več kot ENSO, ki ga stran že prikazuje: pozitivna faza prinaša
      // zahodnik in milejše, vlažnejše zime, negativna pa blokade in vdore
      // celinskega mraza. Datoteka je v enaki obliki kot oni.ascii.txt
      // (leto, mesec, vrednost), le brez glave.
      if (path === "/nao") {
        const naoUrl = "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.nao.monthly.b5001.current.ascii";
        try {
          const r = await fetch(naoUrl, { headers: { "User-Agent": "Mozilla/5.0" }, cf: { cacheTtl: 86400, cacheEverything: true } });
          if (!r.ok) throw new Error("HTTP " + r.status);
          const text = await r.text();
          const records = [];
          for (const line of text.trim().split("\n")) {
            const p = line.trim().split(/\s+/);
            if (p.length < 3) continue;
            const y = parseInt(p[0], 10), m = parseInt(p[1], 10), v = parseFloat(p[2]);
            if (!isFinite(y) || !(m >= 1 && m <= 12) || !isFinite(v) || v === -99.9) continue;
            records.push({ y, m, v: Math.round(v * 100) / 100 });
          }
          return new Response(JSON.stringify(records.slice(-36)), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=86400" },
          });
        } catch (e) {
          return new Response(JSON.stringify({ error: e.message }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
      }

      // ── /senzorji ─────────────────────────────────────────
      // Sensor.Community — občanski senzorji delcev. Kakovost zraka ima stran
      // iz modela Open-Meteo; to so dejanske meritve v okolici, torej isto
      // razmerje kot pri WU postajah proti modelu.
      // Brez ključa; zahteva pa lasten User-Agent.
      if (path === "/senzorji") {
        const RADIUS = 40; // km — širše zajame dolino, ožje ostane brez senzorjev
        const scUrl = `https://data.sensor.community/airrohr/v1/filter/area=46.3258,14.9211,${RADIUS}`;
        try {
          const r = await fetch(scUrl, {
            headers: { "User-Agent": "meteorec.si/1.0", "Accept": "application/json" },
            cf: { cacheTtl: 600, cacheEverything: true },
          });
          if (!r.ok) throw new Error("HTTP " + r.status);
          const raw = await r.json();
          // Ena lokacija ima več senzorjev (delci, temperatura, tlak), vsak s
          // svojim zapisom, zato jih združimo po lokaciji.
          const byLoc = {};
          for (const rec of (Array.isArray(raw) ? raw : [])) {
            const L = rec?.location; if (!L) continue;
            if (Number(L.indoor) === 1) continue;   // notranji senzorji niso primerljivi
            const lat = parseFloat(L.latitude), lon = parseFloat(L.longitude);
            if (!isFinite(lat) || !isFinite(lon)) continue;
            const id = String(L.id);
            const o = byLoc[id] || (byLoc[id] = { id, lat, lon, country: L.country || null, ts: rec.timestamp || null });
            if (rec.timestamp && (!o.ts || rec.timestamp > o.ts)) o.ts = rec.timestamp;
            for (const v of (rec.sensordatavalues || [])) {
              const val = parseFloat(v.value);
              if (!isFinite(val)) continue;
              if (v.value_type === "P1") o.pm10 = val;
              else if (v.value_type === "P2") o.pm25 = val;
              else if (v.value_type === "temperature") o.temp = val;
              else if (v.value_type === "humidity") o.hum = val;
            }
          }
          const LAT0 = 46.325779, LON0 = 14.921137, rad = d => d * Math.PI / 180;
          const list = Object.values(byLoc).map(o => {
            const dLat = rad(o.lat - LAT0), dLon = rad(o.lon - LON0);
            const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(LAT0)) * Math.cos(rad(o.lat)) * Math.sin(dLon / 2) ** 2;
            return { ...o, dist: Math.round(2 * 6371 * Math.asin(Math.sqrt(a))) };
          }).filter(o => o.pm10 != null || o.pm25 != null)
            .sort((a, b) => a.dist - b.dist);
          const pm25 = list.map(o => o.pm25).filter(v => v != null);
          const pm10 = list.map(o => o.pm10).filter(v => v != null);
          const avg = a => a.length ? Math.round(a.reduce((x, y) => x + y, 0) / a.length * 10) / 10 : null;
          return new Response(JSON.stringify({
            radius: RADIUS,
            count: list.length,
            avgPm25: avg(pm25), avgPm10: avg(pm10),
            sensors: list.slice(0, 12),
            source: "Sensor.Community",
          }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "public, max-age=600" },
          });
        } catch (e) {
          return new Response(JSON.stringify({ error: e.message }), {
            status: 502, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
      }

      if (path === "/enso") {
        const oniUrl = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt";
        try {
          const r = await fetch(oniUrl, { headers: { "User-Agent": "Mozilla/5.0" } });
          if (!r.ok) throw new Error("HTTP " + r.status);
          const text = await r.text();
          const records = [];
          for (const line of text.trim().split('\n').slice(1)) {
            const p = line.trim().split(/\s+/);
            if (p.length < 3) continue;
            const v = parseFloat(p[2]);
            if (!isNaN(v) && v !== -99.9) records.push({ s: p[0], y: parseInt(p[1]), a: v });
          }
          return new Response(JSON.stringify(records.slice(-36)), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=86400" },
          });
        } catch(e) {
          return new Response(JSON.stringify({ error: e.message }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" },
          });
        }
      }

      // ── /arso-forecast ───────────────────────────────────
      // ARSO krajevna napoved za dolino. Rečice ob Savinji na ARSO seznamu
      // krajev ni (API vrne 404), zato jemljemo najbližje kraje, ki na njem
      // so — Ljubno je ~9 km po dolini navzgor in v isti kotlini.
      if (path === "/arso-forecast") {
        const num = (v) => {
          if (v == null || v === "") return null;
          const n = Number(v);
          return Number.isFinite(n) ? n : null;
        };

        // forecast24h ima txsyn/tnsyn — dnevni maksimum in minimum naravnost
        // od ARSO, brez sklepanja iz vmesnih terminov.
        const daysFrom24h = (props) => (props?.days ?? []).map((day) => {
          const t = (day.timeline || [])[0] || {};
          return {
            valid_date: day.date,
            tmax: num(t.txsyn),
            tmin: num(t.tnsyn),
            precip: num(t.tp_24h_acc),
            shortFcst_sl: t.clouds_shortText_wwsyn_shortText || t.clouds_shortText || t.wwsyn_shortText || "",
          };
        }).filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d.valid_date || ""));

        // Rezerva, če bi ARSO kdaj nehal pošiljati forecast24h: dnevni
        // ekstrem sestavimo iz 3- oz. 6-urnih terminov.
        const daysFromSlots = (props) => {
          const map = {};
          for (const day of props?.days ?? []) {
            for (const slot of day.timeline || []) {
              const d = day.date;
              if (!/^\d{4}-\d{2}-\d{2}$/.test(d || "")) continue;
              if (!map[d]) map[d] = { temps: [], slots: [] };
              const t = num(slot.t);
              if (t != null) map[d].temps.push(t);
              map[d].slots.push(slot);
            }
          }
          return Object.entries(map).sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([date, { temps, slots }]) => {
            // Opoldanski termin je najbolj reprezentativen za opis dneva.
            const noon = slots.find((s) => (s.valid || "").includes("T12:00"))
              || slots[Math.floor(slots.length / 2)] || slots[0] || {};
            return {
              valid_date: date,
              tmax: temps.length ? Math.max(...temps) : null,
              tmin: temps.length ? Math.min(...temps) : null,
              precip: null,
              shortFcst_sl: noon.clouds_shortText_wwsyn_shortText || noon.clouds_shortText || "",
            };
          });
        };

        const arsoLocations = ["Ljubno ob Savinji", "Gornji Grad", "Luče", "Celje"];
        for (const locName of arsoLocations) {
          const arsoUrl = "https://vreme.arso.gov.si/api/1.0/location/?location="
            + encodeURIComponent(locName) + "&lang=sl";
          try {
            const ctrl = new AbortController();
            const tid = setTimeout(() => ctrl.abort(), 8000);
            const r = await fetch(arsoUrl, {
              headers: {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json,*/*",
                "Referer": "https://vreme.arso.gov.si/",
              },
              signal: ctrl.signal,
            });
            clearTimeout(tid);
            if (!r.ok) continue;
            const json = await r.json();
            const props24 = json?.forecast24h?.features?.[0]?.properties;
            let days = daysFrom24h(props24);
            let props = props24;
            if (!days.length) {
              props = json?.forecast6h?.features?.[0]?.properties
                || json?.forecast3h?.features?.[0]?.properties;
              days = daysFromSlots(props);
            }
            if (!days.length) continue;
            const loc = { title: props?.title || locName, name: props?.title || locName, id: props?.id };
            return new Response(JSON.stringify({ location: loc, days, source: arsoUrl }), {
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=1800" }
            });
          } catch (_) { continue; }
        }
        return new Response(JSON.stringify({ error: "ARSO napoved nedostopna" }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      // ── /arso-water ───────────────────────────────────────
      // ARSO hidrološke postaje vzdolž Savinje — vodostaj, pretok in
      // temperatura vode (temp_vode). Primarni vir je uradni ARSO XML, ki
      // dejansko vsebuje izmerjeno temperaturo vode; GeoJSON WebService je
      // rezervni vir (pogosto vrača prazno).
      if (path === "/arso-water") {
        // Referenčna lokacija (Rečica ob Savinji) za razvrščanje po bližini
        const REF_LAT = 46.3258, REF_LON = 14.9211;
        const dist2 = (lat, lon) => (lat - REF_LAT) ** 2 + (lon - REF_LON) ** 2;

        // ── Primarni vir: ARSO XML ──────────────────────────
        try {
          const ctrl = new AbortController();
          const tid = setTimeout(() => ctrl.abort(), 7000);
          const r = await fetch("https://www.arso.gov.si/xml/vode/hidro_podatki_zadnji.xml", {
            headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/xml,text/xml,*/*", "Referer": "https://www.arso.gov.si/" },
            signal: ctrl.signal,
          });
          clearTimeout(tid);
          if (r.ok) {
            const xml = await r.text();
            const decode = (s) => (s || "")
              .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
              .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(parseInt(d, 10)))
              .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"');
            const field = (block, tag) => {
              const m = block.match(new RegExp("<" + tag + ">([\\s\\S]*?)</" + tag + ">"));
              return m ? decode(m[1]).trim() : null;
            };
            const num = (v) => (v == null || v === "" ? null : Number(v));
            const blocks = xml.match(/<postaja\b[\s\S]*?<\/postaja>/g) || [];
            const features = [];
            for (const b of blocks) {
              const lat = num((b.match(/wgs84_sirina="([\d.]+)"/) || [])[1]);
              const lon = num((b.match(/wgs84_dolzina="([\d.]+)"/) || [])[1]);
              if (lat == null || lon == null) continue;
              features.push({
                type: "Feature",
                geometry: { type: "Point", coordinates: [lon, lat] },
                properties: {
                  sifra: (b.match(/sifra="(\d+)"/) || [])[1] || null,
                  reka: field(b, "reka"),
                  merilno_mesto: field(b, "merilno_mesto"),
                  postaja: field(b, "ime_kratko") || field(b, "merilno_mesto"),
                  vodostaj: num(field(b, "vodostaj")),
                  pretok: num(field(b, "pretok")),
                  temperatura: num(field(b, "temp_vode")),
                  datum: field(b, "datum"),
                },
              });
            }
            // Filter: v bližini Rečice, prednost rekam Savinjske doline
            const nearby = features.filter(f => {
              const [lon, lat] = f.geometry.coordinates;
              return lat > 46.0 && lat < 46.7 && lon > 14.3 && lon < 15.5;
            });
            const savinja = nearby.filter(f => /savinj/i.test(f.properties.reka || ""));
            const out = (savinja.length ? savinja : nearby)
              .sort((a, b) => dist2(a.geometry.coordinates[1], a.geometry.coordinates[0])
                            - dist2(b.geometry.coordinates[1], b.geometry.coordinates[0]))
              .slice(0, 6);
            if (out.length) {
              return new Response(JSON.stringify({ stations: out, total: features.length, source: "arso-xml" }), {
                headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=300" }
              });
            }
          }
        } catch (_) { /* pade na GeoJSON rezervo */ }

        // ── Rezervni vir: GeoJSON WebService ────────────────
        const candidates = [
          "https://vode.arso.gov.si/hidWebService.aspx?POST_IZMERJENI_PODATKI_VODOSTAJ_GEOJSON_T=1&rb_Pq=Q%2CTW",
          "https://vode.arso.gov.si/hidWebService.aspx?POST_IZMERJENI_PODATKI_VODOSTAJ_GEOJSON_T=1&rb_Pq=Q",
          "https://vode.arso.gov.si/hidWebService.aspx?POST_IZMERJENI_PODATKI_VODOSTAJ_GEOJSON_T=1",
        ];
        for (const arsoUrl of candidates) {
          try {
            const ctrl = new AbortController();
            const tid = setTimeout(() => ctrl.abort(), 7000);
            const r = await fetch(arsoUrl, {
              headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/json,*/*", "Referer": "https://vode.arso.gov.si/" },
              signal: ctrl.signal,
            });
            clearTimeout(tid);
            if (!r.ok) continue;
            const text = await r.text();
            // Try JSON parse
            let geojson;
            try { geojson = JSON.parse(text); } catch(_) { continue; }
            const features = geojson?.features || geojson?.Features || [];
            // Filter: near Rečica (lat 46.1–46.6, lon 14.4–15.4), prefer Savinja
            const nearby = features.filter(f => {
              const coords = f.geometry?.coordinates;
              if (!coords) return false;
              const [lon, lat] = coords;
              return lat > 46.0 && lat < 46.7 && lon > 14.3 && lon < 15.5;
            });
            const savinja = nearby.filter(f => {
              const p = f.properties || {};
              const txt = JSON.stringify(p).toLowerCase();
              return txt.includes("savinja") || txt.includes("mozirje") || txt.includes("letuš") || txt.includes("letus") || txt.includes("nazarje");
            });
            const out = (savinja.length ? savinja : nearby).slice(0, 6);
            if (!out.length) continue; // brez rezultatov → poskusi naslednji URL
            return new Response(JSON.stringify({ stations: out, total: features.length, source: arsoUrl }), {
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=300" }
            });
          } catch (_) { continue; }
        }
        return new Response(JSON.stringify({ stations: [], error: "ARSO vode nedostopen" }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      // ── /wu-nearby — bližnje WU postaje ──────────────────
      if (path === "/wu-nearby") {
        const lat = url.searchParams.get("lat") || "46.3258";
        const lon = url.searchParams.get("lon") || "14.9211";
        // Try v3 first (more reliable), then v2 fallback
        const urls = [
          `https://api.weather.com/v3/location/near?geocode=${lat},${lon}&product=pws&format=json&language=en-US&apiKey=${WU_KEY}`,
          `https://api.weather.com/v2/pws/nearby?geocode=${lat},${lon}&format=json&units=m&apiKey=${WU_KEY}`,
        ];
        for (const nearUrl of urls) {
          const ctrl = new AbortController();
          const tid = setTimeout(() => ctrl.abort(), 8000);
          try {
            const r = await fetch(nearUrl, { signal: ctrl.signal }).finally(() => clearTimeout(tid));
            if (!r.ok) continue;
            const data = await r.json();
            // Normalize: extract station list from either v3 or v2 format
            const loc = data.location || {};
            const ids = loc.stationIdentifier || loc.stationId || [];
            if (!ids.length) continue;
            return new Response(JSON.stringify(data), {
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=300" }
            });
          } catch (_) { continue; }
        }
        return new Response(JSON.stringify({ error: "WU nearby nedostopen", _debug: "tried v3+v2" }), {
          status: 502, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      // ── /wu-station-history?id=XXX — 7-dnevna zgodovina ─────────
      if (path === "/wu-station-history") {
        const stationId = url.searchParams.get("id");
        if (!stationId) return new Response(JSON.stringify({ error: "id required" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        const histUrl = `https://api.weather.com/v2/pws/observations/daily/7day?stationId=${stationId}&format=json&units=m&apiKey=${WU_KEY}&numericPrecision=decimal`;
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 8000);
        try {
          const r = await fetch(histUrl, { signal: ctrl.signal }).finally(() => clearTimeout(tid));
          const data = await r.json();
          return new Response(JSON.stringify(data), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=3600" }
          });
        } catch (e) {
          return new Response(JSON.stringify({ error: e.message }), {
            status: 502, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
        }
      }

      // ── /wu-station?id=XXX — trenutni podatki za poljubno postajo ──
      if (path === "/wu-station") {
        const stationId = url.searchParams.get("id");
        if (!stationId) return new Response(JSON.stringify({ error: "id required" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        const stUrl = `https://api.weather.com/v2/pws/observations/current?stationId=${stationId}&format=json&units=m&apiKey=${WU_KEY}&numericPrecision=decimal`;
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 8000);
        try {
          const r = await fetch(stUrl, { signal: ctrl.signal }).finally(() => clearTimeout(tid));
          const data = await r.json();
          return new Response(JSON.stringify(data), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=300" }
          });
        } catch (e) {
          return new Response(JSON.stringify({ error: e.message }), {
            status: 502, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
        }
      }

      // ── /feedback ─────────────────────────────────────────
      // GET  ?date=YYYY-MM-DD → { items, stats: { day: { avg, count }, total } }
      // POST { rating, comment, author, forecast, date? } → { ok: true }
      // Storage: feedback/items.json in PHOTOS_R2
      if (path === "/feedback") {
        const r2 = env?.PHOTOS_R2;

        async function _fbRead() {
          if (!r2) return [];
          try {
            const obj = await r2.get("feedback/items.json");
            if (!obj) return [];
            return JSON.parse(await obj.text());
          } catch (_) { return []; }
        }

        async function _fbWrite(items) {
          if (!r2) return;
          await r2.put("feedback/items.json", JSON.stringify(items), {
            httpMetadata: { contentType: "application/json" }
          });
        }

        if (request.method === "GET") {
          const items = await _fbRead();
          const reqDate = url.searchParams.get("date") || new Date().toISOString().slice(0, 10);
          const dayItems = items.filter(i => i.date === reqDate);
          const dayAvg = dayItems.length
            ? dayItems.reduce((s, i) => s + i.rating, 0) / dayItems.length
            : null;
          return new Response(JSON.stringify({
            items: items.slice(0, 60),
            stats: { day: { avg: dayAvg, count: dayItems.length, date: reqDate }, total: items.length }
          }), { headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" } });
        }

        if (request.method === "POST") {
          if (!r2) return new Response(JSON.stringify({ error: "Shramba ni dosegljiva" }), {
            status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
          let body;
          try { body = await request.json(); } catch (_) {
            return new Response(JSON.stringify({ error: "Napačni podatki" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          const rating = parseInt(body.rating);
          if (!rating || rating < 1 || rating > 5) {
            return new Response(JSON.stringify({ error: "Ocena mora biti med 1 in 5" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          // Allow rating for past 2 days; reject anything older
          const nowDate = new Date().toISOString().slice(0, 10);
          const minDate = new Date(); minDate.setDate(minDate.getDate() - 2);
          const minStr  = minDate.toISOString().slice(0, 10);
          const entryDate = (body.date && /^\d{4}-\d{2}-\d{2}$/.test(body.date) && body.date >= minStr)
            ? body.date : nowDate;
          const entry = {
            id: crypto.randomUUID().split("-")[0],
            ts: new Date().toISOString(),
            date: entryDate,
            rating,
            comment: (body.comment || "").slice(0, 300),
            author: (body.author || "Anonimno").slice(0, 60),
            forecast: (body.forecast || "").slice(0, 100),
          };
          const items = await _fbRead();
          items.unshift(entry);
          await _fbWrite(items.slice(0, 200));
          return new Response(JSON.stringify({ ok: true }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
        }
      }

      // ── /observations ──────────────────────────────────────
      // GET  → { counts: {soncno:3, dezuje:1, …}, total, updatedAt }
      // POST { type } → { ok: true }
      // Items expire after 3h; stored in R2 as feedback/observations.json
      if (path === "/observations") {
        const r2 = env?.PHOTOS_R2;
        const OBS_TYPES = ['soncno','oblacno','dezuje','nevihta','megleno','snezi','vetrovno'];
        const OBS_TTL   = 3 * 3600 * 1000;

        async function _obsRead() {
          if (!r2) return [];
          try {
            const obj = await r2.get("feedback/observations.json");
            if (!obj) return [];
            return JSON.parse(await obj.text());
          } catch (_) { return []; }
        }

        // Groba lokacija (za zasebnost zaokrožena na ~1.1 km) — samo znotraj Zgornje Savinjske / Slovenije
        const SI_BOUNDS = { latMin: 45.3, latMax: 47.0, lonMin: 13.2, lonMax: 16.7 };
        function _obsCoord(body) {
          const lat = Number(body?.lat), lon = Number(body?.lon);
          if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
          if (lat < SI_BOUNDS.latMin || lat > SI_BOUNDS.latMax || lon < SI_BOUNDS.lonMin || lon > SI_BOUNDS.lonMax) return null;
          return { lat: Math.round(lat * 100) / 100, lon: Math.round(lon * 100) / 100 };
        }

        if (request.method === "GET") {
          const all   = await _obsRead();
          const now   = Date.now();
          const fresh = all.filter(i => now - new Date(i.ts).getTime() < OBS_TTL);
          const counts = {};
          OBS_TYPES.forEach(t => { counts[t] = 0; });
          fresh.forEach(i => { if (counts[i.type] !== undefined) counts[i.type]++; });
          const reports = fresh
            .filter(i => i.lat != null && i.lon != null)
            .map(i => ({ type: i.type, lat: i.lat, lon: i.lon, ts: i.ts }));
          return new Response(JSON.stringify({ counts, total: fresh.length, reports, updatedAt: new Date().toISOString() }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
          });
        }

        if (request.method === "POST") {
          if (!r2) return new Response(JSON.stringify({ error: "Shramba ni dosegljiva" }), {
            status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
          let body;
          try { body = await request.json(); } catch (_) {
            return new Response(JSON.stringify({ error: "Napačni podatki" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          if (!OBS_TYPES.includes(body.type)) {
            return new Response(JSON.stringify({ error: "Neznana vrsta opazovanja" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          const coord = _obsCoord(body);
          const all   = await _obsRead();
          const now   = Date.now();
          const fresh = all.filter(i => now - new Date(i.ts).getTime() < 6 * 3600 * 1000);
          fresh.unshift({ type: body.type, ts: new Date().toISOString(), ...(coord || {}) });
          await r2.put("feedback/observations.json", JSON.stringify(fresh.slice(0, 500)), {
            httpMetadata: { contentType: "application/json" }
          });
          return new Response(JSON.stringify({ ok: true }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
        }
      }

      // ── Gallery / photo endpoints ──────────────────────────
      // Vsi galerijski objekti živijo pod ključem "photos/…" v istem R2
      // bucketu kot radar cache, feedback in subscriber podatki — list()
      // MORA imeti prefix, sicer se te interne datoteke izlistajo v javnem
      // odgovoru (zgodilo se je, glej git zgodovino).
      const GALLERY_ADMIN_LOCKOUT_MAX = 8;
      const GALLERY_ADMIN_LOCKOUT_TTL = 15 * 60; // sekund
      async function _galleryAdminAuthed(request, env) {
        const secret = env.DELETE_SECRET;
        const auth = request.headers.get("Authorization") || "";
        if (!secret) return { ok: false, status: 401, error: "Nepooblaščen dostop" };
        if (env.COUNTER_KV) {
          const ip = request.headers.get("CF-Connecting-IP") || "unknown";
          const lockKey = "gal_admin_fail:" + ip;
          const fails = parseInt((await env.COUNTER_KV.get(lockKey)) || "0") || 0;
          if (fails >= GALLERY_ADMIN_LOCKOUT_MAX) {
            return { ok: false, status: 429, error: "Preveč neuspešnih poskusov, poskusi kasneje." };
          }
          if (auth !== "Bearer " + secret) {
            await env.COUNTER_KV.put(lockKey, String(fails + 1), { expirationTtl: GALLERY_ADMIN_LOCKOUT_TTL });
            return { ok: false, status: 401, error: "Nepooblaščen dostop" };
          }
          await env.COUNTER_KV.delete(lockKey);
          return { ok: true };
        }
        if (auth !== "Bearer " + secret) return { ok: false, status: 401, error: "Nepooblaščen dostop" };
        return { ok: true };
      }

      if (path === "/gallery") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ photos: [], error: "R2 not bound" }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const categoryFilter = url.searchParams.get("category");
        const cursor = url.searchParams.get("cursor") || undefined;
        const listed = await env.PHOTOS_R2.list({
          prefix: "photos/", limit: 100, cursor, include: ["customMetadata", "httpMetadata"]
        });
        let photos = listed.objects
          .filter(obj => (obj.customMetadata?.status || "approved") !== "pending")
          .sort((a, b) => new Date(b.uploaded) - new Date(a.uploaded))
          .map(obj => ({
            key: obj.key,
            size: obj.size,
            uploaded: obj.uploaded,
            contentType: obj.httpMetadata?.contentType || "image/jpeg",
            category: obj.customMetadata?.category || "general",
            ...(obj.customMetadata || {})
          }));
        if (categoryFilter) photos = photos.filter(p => p.category === categoryFilter);
        return new Response(JSON.stringify({
          photos, truncated: listed.truncated, cursor: listed.truncated ? listed.cursor : null
        }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
        });
      }

      if (path === "/gallery/pending") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ error: "R2 not bound" }), {
          status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const auth = await _galleryAdminAuthed(request, env);
        if (!auth.ok) return new Response(JSON.stringify({ error: auth.error }), {
          status: auth.status, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const listed = await env.PHOTOS_R2.list({
          prefix: "photos/", limit: 100, include: ["customMetadata", "httpMetadata"]
        });
        const photos = listed.objects
          .filter(obj => obj.customMetadata?.status === "pending")
          .sort((a, b) => new Date(b.uploaded) - new Date(a.uploaded))
          .map(obj => ({
            key: obj.key,
            size: obj.size,
            uploaded: obj.uploaded,
            contentType: obj.httpMetadata?.contentType || "image/jpeg",
            ...(obj.customMetadata || {})
          }));
        return new Response(JSON.stringify({ photos }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
        });
      }

      if (path.startsWith("/gallery/approve/") && request.method === "POST") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ error: "R2 not bound" }), {
          status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const auth = await _galleryAdminAuthed(request, env);
        if (!auth.ok) return new Response(JSON.stringify({ error: auth.error }), {
          status: auth.status, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const key = decodeURIComponent(path.slice("/gallery/approve/".length));
        if (!key.startsWith("photos/")) return new Response(JSON.stringify({ error: "Neveljaven ključ" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const obj = await env.PHOTOS_R2.get(key);
        if (!obj) return new Response(JSON.stringify({ error: "Ni najdeno" }), {
          status: 404, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        await env.PHOTOS_R2.put(key, obj.body, {
          httpMetadata: obj.httpMetadata,
          customMetadata: { ...(obj.customMetadata || {}), status: "approved" }
        });
        return new Response(JSON.stringify({ ok: true }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      if (path.startsWith("/gallery/recategorize/") && request.method === "POST") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ error: "R2 not bound" }), {
          status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const auth = await _galleryAdminAuthed(request, env);
        if (!auth.ok) return new Response(JSON.stringify({ error: auth.error }), {
          status: auth.status, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const key = decodeURIComponent(path.slice("/gallery/recategorize/".length));
        if (!key.startsWith("photos/")) return new Response(JSON.stringify({ error: "Neveljaven ključ" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const category = (url.searchParams.get("category") || "general").slice(0, 30);
        const obj = await env.PHOTOS_R2.get(key);
        if (!obj) return new Response(JSON.stringify({ error: "Ni najdeno" }), {
          status: 404, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        await env.PHOTOS_R2.put(key, obj.body, {
          httpMetadata: obj.httpMetadata,
          customMetadata: { ...(obj.customMetadata || {}), category }
        });
        return new Response(JSON.stringify({ ok: true }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      // Zamenja binarno vsebino obstoječe fotke (npr. klientsko pomanjšana
      // različica) ob ohranitvi customMetadata (title/caption/author/status
      // ...) — uporablja galleryOptimizeExisting() v app.js za enkratno
      // zmanjšanje že naloženih (prevelikih) fotk brez potrebe po ločenem
      // "izbriši + znova naloži" koraku, ki bi izgubil odobritev/opis.
      if (path.startsWith("/gallery/replace/") && request.method === "POST") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ error: "R2 not bound" }), {
          status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const auth = await _galleryAdminAuthed(request, env);
        if (!auth.ok) return new Response(JSON.stringify({ error: auth.error }), {
          status: auth.status, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const key = decodeURIComponent(path.slice("/gallery/replace/".length));
        if (!key.startsWith("photos/")) return new Response(JSON.stringify({ error: "Neveljaven ključ" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const existing = await env.PHOTOS_R2.head(key);
        if (!existing) return new Response(JSON.stringify({ error: "Ni najdeno" }), {
          status: 404, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        let fd;
        try { fd = await request.formData(); } catch (e) {
          return new Response(JSON.stringify({ error: "Napačni podatki" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }
        const file = fd.get("photo");
        if (!file || !file.size) return new Response(JSON.stringify({ error: "Ni datoteke" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        if (file.size > 20 * 1024 * 1024) return new Response(JSON.stringify({ error: "Datoteka je prevelika (max 20 MB)" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        await env.PHOTOS_R2.put(key, file.stream(), {
          httpMetadata: { contentType: file.type || existing.httpMetadata?.contentType },
          customMetadata: existing.customMetadata
        });
        return new Response(JSON.stringify({ ok: true }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      if (path === "/gallery/upload" && request.method === "POST") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ error: "R2 not bound" }), {
          status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        let fd;
        try { fd = await request.formData(); } catch (e) {
          return new Response(JSON.stringify({ error: "Napačni podatki" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }
        const file = fd.get("photo");
        if (!file || !file.size) return new Response(JSON.stringify({ error: "Ni datoteke" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const allowed = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];
        if (!allowed.includes(file.type)) return new Response(JSON.stringify({ error: "Podprti formati: JPEG, PNG, WebP" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        if (file.size > 20 * 1024 * 1024) return new Response(JSON.stringify({ error: "Datoteka je prevelika (max 20 MB)" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const ext = file.type === "image/png" ? "png" : file.type === "image/webp" ? "webp" : "jpg";
        const uuid = crypto.randomUUID().split("-")[0];
        const key = `photos/${Date.now()}-${uuid}.${ext}`;
        const category = (fd.get("category") || "general").slice(0, 30);
        await env.PHOTOS_R2.put(key, file.stream(), {
          httpMetadata: { contentType: file.type },
          customMetadata: {
            title:      (fd.get("title")   || "").slice(0, 120),
            caption:    (fd.get("caption") || "").slice(0, 500),
            author:     (fd.get("author")  || "Anonimno").slice(0, 60),
            weather:    (fd.get("weather") || "").slice(0, 200),
            category,
            location:   (fd.get("location") || "").slice(0, 120),
            uploadedAt: new Date().toISOString(),
            status:     "pending"
          }
        });
        return new Response(JSON.stringify({ ok: true, key }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      if (path.startsWith("/gallery/img/")) {
        if (!env.PHOTOS_R2) return new Response("R2 not bound", { status: 503 });
        const key = decodeURIComponent(path.slice("/gallery/img/".length));
        if (!key.startsWith("photos/")) return new Response("Not found", { status: 404 });
        const obj = await env.PHOTOS_R2.get(key);
        if (!obj) return new Response("Not found", { status: 404 });
        return new Response(obj.body, {
          headers: {
            ...CORS_ALLOWED,
            "Content-Type": obj.httpMetadata?.contentType || "image/jpeg",
            "Cache-Control": "public, max-age=31536000, immutable",
          }
        });
      }

      if (path.startsWith("/gallery/delete/") && request.method === "DELETE") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ error: "R2 not bound" }), {
          status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const auth = await _galleryAdminAuthed(request, env);
        if (!auth.ok) return new Response(JSON.stringify({ error: auth.error }), {
          status: auth.status, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const key = decodeURIComponent(path.slice("/gallery/delete/".length));
        if (!key.startsWith("photos/")) return new Response(JSON.stringify({ error: "Neveljaven ključ" }), {
          status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        await env.PHOTOS_R2.delete(key);
        return new Response(JSON.stringify({ ok: true }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      // ── /blog-comments ─────────────────────────────────────
      // Komentarji + ocene pod blog članki, shranjeni v R2 po slug-u
      // (blog-comments/{slug}.json).
      //   GET  ?slug=…  → { comments:[…], rating:{avg,count} }
      //   POST { slug, comment, author?, rating? } → { ok:true }
      if (path === "/blog-comments") {
        const r2 = env?.PHOTOS_R2;
        const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,80}$/;

        const _key = slug => `blog-comments/${slug}.json`;

        async function _cRead(slug) {
          if (!r2) return [];
          try {
            const obj = await r2.get(_key(slug));
            if (!obj) return [];
            return JSON.parse(await obj.text());
          } catch (_) { return []; }
        }
        async function _cWrite(slug, items) {
          if (!r2) return;
          await r2.put(_key(slug), JSON.stringify(items), {
            httpMetadata: { contentType: "application/json" }
          });
        }
        function _stats(items) {
          const rated = items.filter(i => i.rating);
          const avg = rated.length
            ? rated.reduce((s, i) => s + i.rating, 0) / rated.length
            : null;
          return { avg, count: rated.length };
        }

        if (request.method === "GET") {
          // Bulk povprečne ocene za več člankov naenkrat (za seznam blogov):
          //   ?slugs=a,b,c → { ratings: { a:{avg,count}, … } }
          const slugsParam = url.searchParams.get("slugs");
          if (slugsParam !== null) {
            const wanted = slugsParam.split(",").map(s => s.trim())
              .filter(s => SLUG_RE.test(s)).slice(0, 60);
            const ratings = {};
            const comments = {};
            await Promise.all(wanted.map(async s => {
              const items = await _cRead(s);
              ratings[s] = _stats(items);
              comments[s] = items.filter(i => i.comment && i.comment.length).length;
            }));
            return new Response(JSON.stringify({ ratings, comments }), {
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "s-maxage=300" }
            });
          }
          const slug = url.searchParams.get("slug") || "";
          if (!SLUG_RE.test(slug)) {
            return new Response(JSON.stringify({ comments: [], rating: { avg: null, count: 0 } }), {
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
            });
          }
          const items = await _cRead(slug);
          // Ne razkrivamo honeypota/skritih polj — vrni le javne dele
          const pub = items.map(i => ({
            id: i.id, ts: i.ts, author: i.author, comment: i.comment, rating: i.rating || null
          }));
          return new Response(JSON.stringify({ comments: pub.slice(0, 200), rating: _stats(items) }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
          });
        }

        if (request.method === "POST") {
          if (!r2) return new Response(JSON.stringify({ error: "Shramba ni dosegljiva" }), {
            status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
          let body;
          try { body = await request.json(); } catch (_) {
            return new Response(JSON.stringify({ error: "Napačni podatki" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          const slug = (body.slug || "").trim();
          if (!SLUG_RE.test(slug)) {
            return new Response(JSON.stringify({ error: "Neznan članek" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          // Honeypot — boti izpolnijo skrito polje "website"
          if (body.website) {
            return new Response(JSON.stringify({ ok: true }), { headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          const comment = (body.comment || "").trim();
          const rating  = body.rating ? parseInt(body.rating) : null;
          if (!comment && !rating) {
            return new Response(JSON.stringify({ error: "Napiši komentar ali oddaj oceno" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          if (comment.length > 1500) {
            return new Response(JSON.stringify({ error: "Komentar je predolg (največ 1500 znakov)" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          if (rating !== null && (rating < 1 || rating > 5)) {
            return new Response(JSON.stringify({ error: "Ocena mora biti med 1 in 5" }), { status: 400, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          const items = await _cRead(slug);
          // Preprosta zaščita pred podvajanjem: isti komentar v zadnji minuti
          const now = Date.now();
          const dup = items.some(i =>
            i.comment === comment && (now - new Date(i.ts).getTime()) < 60000);
          if (dup) {
            return new Response(JSON.stringify({ ok: true }), { headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
          }
          const entry = {
            id: crypto.randomUUID().split("-")[0],
            ts: new Date().toISOString(),
            author: (body.author || "Anonimno").slice(0, 60).trim() || "Anonimno",
            comment: comment.slice(0, 1500),
            rating: rating,
          };
          items.unshift(entry);
          await _cWrite(slug, items.slice(0, 500));

          // E-obvestilo lastniku ob novem komentarju (v ozadju).
          // Zahteva skrivnost RESEND_API_KEY (Cloudflare → Settings → Variables).
          // Neobvezno: NOTIFY_EMAIL (prejemnik), NOTIFY_FROM (pošiljatelj).
          if (env?.RESEND_API_KEY) {
            const to   = env.NOTIFY_EMAIL || "filip.eremita@gmail.com";
            const from = env.NOTIFY_FROM  || "Meteorec komentarji <onboarding@resend.dev>";
            const artUrl = `https://meteorec.si/blog/${slug}.html#komentarji`;
            const esc = s => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            const ratingLine = entry.rating ? `<p>Ocena: ${"★".repeat(entry.rating)}${"☆".repeat(5 - entry.rating)} (${entry.rating}/5)</p>` : "";
            const html =
              `<p><strong>${esc(entry.author)}</strong> je komentiral članek <a href="${artUrl}">${esc(slug)}</a>:</p>` +
              ratingLine +
              (entry.comment ? `<blockquote style="border-left:3px solid #4d9ff8;margin:0;padding:.2rem 0 .2rem 1rem;color:#333">${esc(entry.comment)}</blockquote>` : "") +
              `<p><a href="${artUrl}">Odpri komentarje →</a></p>`;
            ctx.waitUntil(
              fetch("https://api.resend.com/emails", {
                method: "POST",
                headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
                body: JSON.stringify({
                  from, to,
                  subject: `Nov komentar na blogu: ${slug}`,
                  html,
                }),
              }).catch(() => {})
            );
          }

          return new Response(JSON.stringify({ ok: true, comment: {
            id: entry.id, ts: entry.ts, author: entry.author, comment: entry.comment, rating: entry.rating
          }, rating: _stats(items) }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
        }

        return new Response(JSON.stringify({ error: "Nedovoljena metoda" }), {
          status: 405, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
      }

      // ── /blog-subscribe (+ /confirm, /unsubscribe, /notify) ─────
      // E-prijava na nove blog članke z dvojnim opt-in.
      //   POST /blog-subscribe               { email }         → pošlje potrditveno e-pošto
      //   GET  /blog-subscribe/confirm?token=…                 → potrdi naročnino (HTML)
      //   GET  /blog-subscribe/unsubscribe?token=…             → odjava (HTML)
      //   POST /blog-subscribe/notify        { secret, slug? } → obvesti vse naročnike
      // Shramba v R2: subscribers/pending.json + subscribers/confirmed.json
      if (path === "/blog-subscribe" || path.startsWith("/blog-subscribe/")) {
        const r2 = env?.PHOTOS_R2;
        const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
        const base = url.origin;

        async function _read(key) {
          if (!r2) return [];
          try { const o = await r2.get(key); return o ? JSON.parse(await o.text()) : []; }
          catch (_) { return []; }
        }
        async function _write(key, arr) {
          if (!r2) return;
          await r2.put(key, JSON.stringify(arr), { httpMetadata: { contentType: "application/json" } });
        }
        function _esc(s) {
          return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }
        function _page(title, body) {
          return `<!doctype html><html lang="sl"><head><meta charset="utf-8">` +
            `<meta name="viewport" content="width=device-width,initial-scale=1">` +
            `<title>${_esc(title)} · Meteorec</title>` +
            `<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;` +
            `background:#04070e;color:#e8edf8;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;padding:1.5rem}` +
            `.card{max-width:440px;background:rgba(10,15,28,.94);border:1px solid rgba(255,255,255,.11);` +
            `border-radius:16px;padding:2rem;text-align:center;box-shadow:0 4px 28px rgba(0,0,0,.3)}` +
            `h1{font-size:1.3rem;margin:0 0 .6rem}p{color:#adc0d8;line-height:1.6;margin:.4rem 0}` +
            `a{color:#4d9ff8;text-decoration:none}</style></head>` +
            `<body><div class="card">${body}<p style="margin-top:1.2rem"><a href="https://meteorec.si/blog/">← Na blog</a></p></div></body></html>`;
        }
        function _htmlResp(html, status) {
          return new Response(html, { status: status || 200, headers: { ...CORS_ALLOWED, "Content-Type": "text/html; charset=utf-8" } });
        }
        function _json(obj, status) {
          return new Response(JSON.stringify(obj), { status: status || 200, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }
        function _sendMail(to, subject, html) {
          if (!env?.RESEND_API_KEY) return Promise.resolve();
          const from = env.SUBSCRIBE_FROM || env.NOTIFY_FROM || "Meteorec <onboarding@resend.dev>";
          return fetch("https://api.resend.com/emails", {
            method: "POST",
            headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
            body: JSON.stringify({ from, to, subject, html }),
          }).catch(() => {});
        }

        // ── POST /blog-subscribe → nova prijava (pending + potrditvena e-pošta)
        if (path === "/blog-subscribe" && request.method === "POST") {
          if (!r2) return _json({ error: "Shramba ni dosegljiva" }, 503);
          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          if (body.website) return _json({ ok: true }); // honeypot
          const email = (body.email || "").trim().toLowerCase();
          if (!EMAIL_RE.test(email) || email.length > 120) return _json({ error: "Neveljaven e-naslov" }, 400);

          const confirmed = await _read("subscribers/confirmed.json");
          if (confirmed.some(s => s.email === email)) return _json({ ok: true, already: true });

          const pending = await _read("subscribers/pending.json");
          let rec = pending.find(s => s.email === email);
          if (!rec) {
            rec = { email, token: crypto.randomUUID().replace(/-/g, ""), ts: new Date().toISOString() };
            pending.unshift(rec);
            await _write("subscribers/pending.json", pending.slice(0, 2000));
          }
          const link = `${base}/blog-subscribe/confirm?token=${rec.token}`;
          ctx.waitUntil(_sendMail(email, "Potrdi naročnino na Meteorec blog",
            `<p>Pozdravljen!</p><p>Za dokončanje naročnine na nove članke bloga <strong>Meteorec</strong> potrdi svoj e-naslov:</p>` +
            `<p><a href="${link}" style="display:inline-block;background:#4d9ff8;color:#04070e;padding:.6rem 1.2rem;border-radius:8px;text-decoration:none;font-weight:600">Potrdi naročnino</a></p>` +
            `<p style="color:#888;font-size:.85rem">Če se nisi prijavil, to sporočilo preprosto prezri.</p>`));
          return _json({ ok: true });
        }

        // ── GET /blog-subscribe/confirm?token=…
        if (path === "/blog-subscribe/confirm" && request.method === "GET") {
          const token = url.searchParams.get("token") || "";
          if (!token) return _htmlResp(_page("Napaka", "<h1>Neveljavna povezava</h1><p>Manjka žeton za potrditev.</p>"), 400);
          const pending = await _read("subscribers/pending.json");
          const idx = pending.findIndex(s => s.token === token);
          if (idx === -1) {
            // morda že potrjeno
            const confirmed0 = await _read("subscribers/confirmed.json");
            if (confirmed0.some(s => s.token === token))
              return _htmlResp(_page("Že potrjeno", "<h1>Naročnina je že aktivna ✅</h1><p>Hvala, tvoj e-naslov je že potrjen.</p>"));
            return _htmlResp(_page("Napaka", "<h1>Povezava ni veljavna</h1><p>Žeton ne obstaja ali je potekel.</p>"), 404);
          }
          const rec = pending.splice(idx, 1)[0];
          await _write("subscribers/pending.json", pending);
          const confirmed = await _read("subscribers/confirmed.json");
          if (!confirmed.some(s => s.email === rec.email)) {
            confirmed.unshift({ email: rec.email, token: rec.token, ts: new Date().toISOString() });
            await _write("subscribers/confirmed.json", confirmed);
          }
          return _htmlResp(_page("Potrjeno", "<h1>Naročnina potrjena 🎉</h1><p>Odslej boš ob vsakem novem članku prejel e-obvestilo. Hvala!</p>"));
        }

        // ── GET /blog-subscribe/unsubscribe?token=…
        if (path === "/blog-subscribe/unsubscribe" && request.method === "GET") {
          const token = url.searchParams.get("token") || "";
          const confirmed = await _read("subscribers/confirmed.json");
          const next = confirmed.filter(s => s.token !== token);
          if (next.length !== confirmed.length) await _write("subscribers/confirmed.json", next);
          return _htmlResp(_page("Odjava", "<h1>Odjavljen 👋</h1><p>Ne bomo ti več pošiljali obvestil o novih člankih. Kadarkoli se lahko znova prijaviš.</p>"));
        }

        // ── POST /blog-subscribe/notify { secret, slug? } → obvesti naročnike
        if (path === "/blog-subscribe/notify" && request.method === "POST") {
          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          const secret = env.SUBSCRIBE_SECRET || env.DELETE_SECRET;
          if (!secret || body.secret !== secret) return _json({ error: "Nedovoljeno" }, 401);

          // Metapodatke lahko podamo neposredno (body.post) — tako ni odvisnosti
          // od že objavljenega blog.json (npr. tik po objavi, pred osvežitvijo Pages).
          let post = null;
          if (body.post && body.post.slug && body.post.title) {
            post = body.post;
          } else {
            let posts = [];
            try { posts = await (await fetch("https://meteorec.si/blog.json", { cf: { cacheTtl: 60 } })).json(); }
            catch (_) { return _json({ error: "blog.json ni dosegljiv" }, 502); }
            post = body.slug ? posts.find(p => p.slug === body.slug) : posts[0];
          }
          if (!post) return _json({ error: "Članek ni najden" }, 404);

          const confirmed = await _read("subscribers/confirmed.json");
          const artUrl = "https://meteorec.si" + (post.url && post.url.startsWith("/") ? post.url : "/blog/" + post.slug + ".html");
          ctx.waitUntil((async () => {
            for (const s of confirmed) {
              const unsub = `${base}/blog-subscribe/unsubscribe?token=${s.token}`;
              await _sendMail(s.email, "Nov članek na Meteorec blogu: " + post.title,
                `<h2 style="margin:0 0 .5rem">${_esc(post.title)}</h2>` +
                (post.summary ? `<p style="color:#444">${_esc(post.summary)}</p>` : "") +
                `<p><a href="${artUrl}" style="display:inline-block;background:#4d9ff8;color:#04070e;padding:.6rem 1.2rem;border-radius:8px;text-decoration:none;font-weight:600">Preberi članek →</a></p>` +
                `<hr style="border:none;border-top:1px solid #eee;margin:1.5rem 0"><p style="color:#999;font-size:.8rem">Prejemaš, ker si naročen na Meteorec blog. <a href="${unsub}" style="color:#999">Odjava</a></p>`);
            }
          })());
          return _json({ ok: true, sent: confirmed.length, post: post.slug });
        }

        return _json({ error: "Nedovoljena metoda ali pot" }, 405);
      }

      // ── /premium (gobarska napoved — plačljivi dostop) ──────
      //   POST /premium/data      Bearer PREMIUM_SYNC_KEY → store forecast JSON (from GitHub Action)
      //   POST /premium/webhook   Paddle Billing notification (signature-verified)
      //   POST /premium/login     { email } → magic link via Resend
      //   GET  /premium/verify    Bearer token → { ok, plan, expires }
      //   GET  /premium/forecast  Bearer token → premium forecast JSON
      //   GET  /premium/alerts    Bearer token → saved custom alert rules
      //   POST /premium/alerts    Bearer token → replace custom alert rules
      //   POST /premium/notify    Bearer PREMIUM_SYNC_KEY → per-subscriber rule check + email (from CI, daily)
      // Storage (COUNTER_KV):
      //   premium:data              — latest premium forecast JSON
      //   premium:sub:<email>       — { email, plan, expires, customer_id, updated }
      //   premium:tok:<token>       — { email, ts }  (TTL 90 days; sub expiry re-checked on every read)
      //   premium:alertrules:<email> — [{ species_id, location, min_elev_m, threshold }, …] (max 5)
      //   premium:alertstate:<email> — { date } — last day this subscriber's alert fired (cooldown)
      if (path.startsWith("/premium/")) {
        const kv = env?.COUNTER_KV;
        const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
        const PAGE_URL = "https://meteorec.si/gobarska-napoved/";
        const TOKEN_TTL_S = 60 * 60 * 24 * 90;
        const LOGIN_RL_MAX = 5;
        const LOGIN_RL_TTL_S = 15 * 60; // sekund — isto okno kot gallery admin lockout

        function _json(obj, status) {
          return new Response(JSON.stringify(obj), {
            status: status || 200,
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-store" },
          });
        }
        function _sendMail(to, subject, html) {
          if (!env?.RESEND_API_KEY) return Promise.resolve();
          const from = env.PREMIUM_FROM || env.NOTIFY_FROM || "Meteorec <onboarding@resend.dev>";
          return fetch("https://api.resend.com/emails", {
            method: "POST",
            headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
            body: JSON.stringify({ from, to, subject, html }),
          }).catch(() => {});
        }
        async function _hmacHex(secret, msg) {
          const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret),
            { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
          const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
          return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("");
        }
        function _tsEqual(a, b) {
          // constant-time string comparison
          if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
          let r = 0;
          for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
          return r === 0;
        }
        function _bearer() {
          const h = request.headers.get("Authorization") || "";
          if (h.startsWith("Bearer ")) return h.slice(7).trim();
          return (url.searchParams.get("token") || "").trim();
        }
        async function _subFor(email) {
          try { return JSON.parse(await kv.get(`premium:sub:${email}`)); } catch (_) { return null; }
        }
        async function _newToken(email) {
          const tok = (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, "");
          await kv.put(`premium:tok:${tok}`, JSON.stringify({ email, ts: new Date().toISOString() }),
            { expirationTtl: TOKEN_TTL_S });
          return tok;
        }
        async function _authedSub() {
          // token → subscriber record, or null when token/subscription invalid
          const tok = _bearer();
          if (!tok) return null;
          let rec; try { rec = JSON.parse(await kv.get(`premium:tok:${tok}`)); } catch (_) { return null; }
          if (!rec?.email) return null;
          const sub = await _subFor(rec.email);
          if (!sub?.expires || new Date(sub.expires) < new Date()) return null;
          return sub;
        }
        function _magicLinkMail(link) {
          return `<p>Pozdravljen, gobar!</p>` +
            `<p>Tvoj dostop do <strong>gobarske napovedi Premium</strong> (7-dnevna napoved po vrstah in lokacijah):</p>` +
            `<p><a href="${link}" style="display:inline-block;background:#4d9ff8;color:#04070e;padding:.6rem 1.2rem;border-radius:8px;text-decoration:none;font-weight:600">Odpri gobarsko napoved 🍄</a></p>` +
            `<p style="color:#888;font-size:.85rem">Povezava velja 90 dni in deluje na vseh tvojih napravah. ` +
            `Nov dostop lahko kadarkoli zahtevaš na ${PAGE_URL} z istim e-naslovom.</p>` +
            `<p style="color:#888;font-size:.85rem">Napoved je indeks ugodnosti pogojev, ne obljuba najdbe — gozd ima vedno zadnjo besedo.</p>`;
        }

        if (!kv) return _json({ error: "Shramba ni dosegljiva" }, 503);

        // ── POST /premium/data — GitHub Action pushes the daily premium JSON
        if (path === "/premium/data" && request.method === "POST") {
          const syncKey = env?.PREMIUM_SYNC_KEY;
          const auth = request.headers.get("Authorization") || "";
          if (!syncKey || !_tsEqual(auth, `Bearer ${syncKey}`)) return _json({ error: "Nedovoljeno" }, 401);
          const raw = await request.text();
          // Bila je 1 MiB — z rastjo baze indeksiranih vrst (108 danes) je
          // dnevni payload prerasel to mejo (~2 MiB) nekje okrog 18. 7. 2026,
          // vsak dnevni push je od takrat tiho odpovedal s 413 (gobe-forecast.yml
          // ob curl -sf/napaki samo opozori in nadaljuje), KV pa je ves ta čas
          // tiho postrezala mesec dni staro napoved. 8 MiB pusti precej prostora
          // za nadaljnjo rast baze (KV vrednosti dovolijo do 25 MiB).
          if (raw.length > 8 * 1024 * 1024) return _json({ error: "Preveliko" }, 413);
          let parsed;
          try { parsed = JSON.parse(raw); } catch (_) { return _json({ error: "Neveljaven JSON" }, 400); }
          if (!Array.isArray(parsed?.locations) || !parsed.locations.length)
            return _json({ error: "Manjkajo lokacije" }, 422);
          await kv.put("premium:data", raw);
          return _json({ ok: true, bytes: raw.length, generated: parsed.generated || null });
        }

        // ── POST /premium/webhook — Paddle Billing notifications
        if (path === "/premium/webhook" && request.method === "POST") {
          const secret = env?.PADDLE_WEBHOOK_SECRET;
          if (!secret) return _json({ error: "Webhook ni konfiguriran" }, 503);
          const raw = await request.text();
          // Paddle-Signature: ts=<unix>;h1=<hmac-sha256 of "<ts>:<raw body>">
          const sig = Object.fromEntries((request.headers.get("Paddle-Signature") || "")
            .split(";").map(p => p.split("=")));
          if (!sig.ts || !sig.h1) return _json({ error: "Manjka podpis" }, 401);
          const expected = await _hmacHex(secret, `${sig.ts}:${raw}`);
          if (!_tsEqual(expected, sig.h1)) return _json({ error: "Neveljaven podpis" }, 401);

          let evt; try { evt = JSON.parse(raw); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          // transaction.completed covers both the first purchase and every
          // subscription renewal; expiry-based access makes cancel events moot.
          if (evt.event_type !== "transaction.completed")
            return _json({ ok: true, ignored: evt.event_type || "?" });

          const data = evt.data || {};
          let email = (data.custom_data?.email || "").toLowerCase().trim();
          if (!EMAIL_RE.test(email)) {
            // Fall back to the Paddle customer record
            email = "";
            if (env?.PADDLE_API_KEY && data.customer_id) {
              try {
                const base = env.PADDLE_API_BASE || "https://api.paddle.com";
                const r = await fetch(`${base}/customers/${data.customer_id}`,
                  { headers: { "Authorization": `Bearer ${env.PADDLE_API_KEY}` } });
                if (r.ok) email = ((await r.json())?.data?.email || "").toLowerCase().trim();
              } catch (_) {}
            }
          }
          if (!EMAIL_RE.test(email)) return _json({ error: "E-naslova ni bilo mogoče ugotoviti" }, 422);

          const isSeason = (data.items || []).some(it => it?.price?.id && it.price.id === env.PADDLE_PRICE_SEASON);
          const plan = isSeason ? "sezona" : "mesecna";
          const now = new Date();
          let expires;
          if (isSeason) {
            const [mm, dd] = (env.PREMIUM_SEASON_END || "11-30").split("-").map(Number);
            expires = new Date(Date.UTC(now.getUTCFullYear(), mm - 1, dd, 23, 59, 59));
            if (expires < now) expires = new Date(Date.UTC(now.getUTCFullYear() + 1, mm - 1, dd, 23, 59, 59));
          } else {
            expires = new Date(now.getTime() + 33 * 864e5); // 30 days + grace for renewal lag
          }
          const prev = await _subFor(email);
          if (prev?.expires && new Date(prev.expires) > expires) expires = new Date(prev.expires);
          await kv.put(`premium:sub:${email}`, JSON.stringify({
            email, plan, expires: expires.toISOString(),
            customer_id: data.customer_id || null, updated: now.toISOString(),
          }));
          // Send the access link right away — no separate login step after payment
          const tok = await _newToken(email);
          ctx.waitUntil(_sendMail(email, "Tvoj dostop do gobarske napovedi Premium 🍄",
            _magicLinkMail(`${PAGE_URL}?token=${tok}`)));
          return _json({ ok: true, plan });
        }

        // ── POST /premium/login { email } — (re)send magic link
        if (path === "/premium/login" && request.method === "POST") {
          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          if (body.website) return _json({ ok: true }); // honeypot
          const email = (body.email || "").trim().toLowerCase();
          if (!EMAIL_RE.test(email) || email.length > 120) return _json({ error: "Neveljaven e-naslov" }, 400);
          // Rate-limit per email so a script can't hammer the mail-send path.
          // Same neutral response as success either way — a different reply
          // here would itself leak "this email is being rate-limited", which
          // is as much of an oracle as leaking subscription status.
          if (kv) {
            const rlKey = "premium_login_rl:" + email;
            const count = parseInt((await kv.get(rlKey)) || "0") || 0;
            if (count >= LOGIN_RL_MAX) {
              return _json({ ok: true, msg: "Če je e-naslov naročen, smo nanj poslali povezavo za dostop." });
            }
            await kv.put(rlKey, String(count + 1), { expirationTtl: LOGIN_RL_TTL_S });
          }
          const sub = await _subFor(email);
          if (sub?.expires && new Date(sub.expires) > new Date()) {
            const tok = await _newToken(email);
            ctx.waitUntil(_sendMail(email, "Povezava do gobarske napovedi Premium 🍄",
              _magicLinkMail(`${PAGE_URL}?token=${tok}`)));
          }
          // Same answer either way — don't reveal who is subscribed
          return _json({ ok: true, msg: "Če je e-naslov naročen, smo nanj poslali povezavo za dostop." });
        }

        // ── GET /premium/verify — is this token still good?
        if (path === "/premium/verify" && request.method === "GET") {
          const sub = await _authedSub();
          if (!sub) return _json({ ok: false }, 401);
          return _json({ ok: true, plan: sub.plan, expires: sub.expires });
        }

        // ── GET /premium/forecast — the paid payload
        // Sezonski zagon: ko je env.PREMIUM_FREE_LAUNCH="true" (wrangler.toml),
        // gre napoved ven brez žetona — glej PREMIUM_FREE_LAUNCH v
        // tools/generate_gobe_page.py. AI prepoznava, alarmi in dnevnik ostanejo
        // za pravim naročniškim žetonom ne glede na to zastavico.
        if (path === "/premium/forecast" && request.method === "GET") {
          const freeLaunch = String(env?.PREMIUM_FREE_LAUNCH || "").toLowerCase() === "true";
          if (!freeLaunch) {
            const sub = await _authedSub();
            if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          }
          const data = await kv.get("premium:data");
          if (!data) return _json({ error: "Napoved še ni pripravljena" }, 503);
          return new Response(data, {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-store" },
          });
        }

        // ── POST /premium/identify — AI prepoznava gobe iz fotografije (Claude vision)
        if (path === "/premium/identify" && request.method === "POST") {
          const sub = await _authedSub();
          if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          if (!env.ANTHROPIC_KEY) return _json({ error: "AI prepoznava trenutno ni na voljo" }, 503);

          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          const raw = String(body.image || "");
          const m = raw.match(/^data:(image\/(?:jpeg|png|webp));base64,(.+)$/s);
          if (!m) return _json({ error: "Manjka slika (jpeg/png/webp)" }, 400);
          const [, mediaType, imgB64] = m;
          if (imgB64.length > 6_000_000) return _json({ error: "Slika je prevelika" }, 413);

          const dbLines = GOBE_SPECIES_DB.map(s =>
            `- ${s.sl} (${s.lat}) — ${s.ed}${s.dbl ? "; dvojnica: " + s.dbl : ""}`).join("\n");
          const prompt = `Si mikološki pomočnik za gobarje v Zgornji Savinjski dolini, Slovenija. Uporabnik je poslal fotografijo gobe, najdene na terenu.

Referenčna baza vrst te doline (uporabi ta slovenska imena, kadar gre za isto vrsto):
${dbLines}

Naloga:
1. Predlagaj 1–3 najverjetnejše vrste (najprej najbolj verjetna), po možnosti iz zgornje baze.
2. Za vsak predlog: slovensko in latinsko ime, zanesljivost (nizka/srednja/visoka), kratko utemeljitev (barva, oblika, rast, habitat) in užitnost.
3. Če obstaja nevarna dvojnica, jo IZRECNO navedi z opozorilom.
4. Če fotografija ni dovolj jasna, ali gre morda za mušnico (Amanita) ali drug nevaren rod, bodi še posebej previden in to jasno povej.

Rezultat sporoči IZKLJUČNO s klicem orodja "report_identification" — ne piši nobenega besedila izven tega klica.

POMEMBNO: Nikoli ne trdi 100% gotovosti. Vedno spomni uporabnika, naj se ob najmanjšem dvomu obrne na mikologa ali gobarsko društvo, preden gobo zaužije.`;

          const tool = {
            name: "report_identification",
            description: "Poroča o prepoznanih kandidatih za vrsto gobe na fotografiji.",
            input_schema: {
              type: "object",
              properties: {
                candidates: {
                  type: "array",
                  items: {
                    type: "object",
                    properties: {
                      name_sl: { type: "string" },
                      name_lat: { type: "string" },
                      confidence: { type: "string", enum: ["nizka", "srednja", "visoka"] },
                      reasoning: { type: "string" },
                      edibility: { type: "string" },
                      warning: { type: "string" },
                    },
                    required: ["name_sl", "confidence", "reasoning", "edibility"],
                  },
                },
                unclear: { type: "boolean" },
                note: { type: "string" },
              },
              required: ["candidates", "unclear", "note"],
            },
          };

          let aiRes;
          try {
            aiRes = await fetch("https://api.anthropic.com/v1/messages", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "x-api-key": env.ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
              },
              body: JSON.stringify({
                model: "claude-sonnet-5",
                max_tokens: 1024,
                tools: [tool],
                tool_choice: { type: "tool", name: "report_identification" },
                messages: [{
                  role: "user",
                  content: [
                    { type: "image", source: { type: "base64", media_type: mediaType, data: imgB64 } },
                    { type: "text", text: prompt },
                  ],
                }],
              }),
            });
          } catch (_) { return _json({ error: "AI storitev ni dosegljiva (omrežje)" }, 502); }
          if (!aiRes.ok) {
            let detail = "";
            try { detail = (await aiRes.json())?.error?.message || ""; } catch (_) {}
            return _json({ error: "AI storitev ni dosegljiva", upstream_status: aiRes.status, upstream_detail: detail }, 502);
          }
          const aiData = await aiRes.json();
          const toolUse = (aiData.content || []).find(c => c.type === "tool_use" && c.name === "report_identification");
          if (!toolUse || !toolUse.input) {
            return _json({ error: "Napaka pri obdelavi odgovora", stop_reason: aiData.stop_reason || null }, 500);
          }
          const parsed = toolUse.input;
          return _json({ ok: true, candidates: parsed.candidates || [], unclear: !!parsed.unclear, note: parsed.note || "" });
        }

        // ── Gobarjev dnevnik: sinhronizacija med napravami (premium) ──────────
        // Fotografije gredo v R2 (ločeno od metapodatkov, da KV zapis ostane majhen).
        async function _diaryPhotoHash(email) {
          const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email));
          return [...new Uint8Array(digest)].slice(0, 8).map(b => b.toString(16).padStart(2, "0")).join("");
        }

        // ── POST /premium/diary/photo { image: dataURL } → { ok, url }
        if (path === "/premium/diary/photo" && request.method === "POST") {
          const sub = await _authedSub();
          if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          if (!env.PHOTOS_R2) return _json({ error: "Shramba slik ni na voljo" }, 503);
          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          const raw = String(body.image || "");
          const m = raw.match(/^data:(image\/(?:jpeg|png|webp));base64,(.+)$/s);
          if (!m) return _json({ error: "Manjka slika (jpeg/png/webp)" }, 400);
          const [, mediaType, imgB64] = m;
          if (imgB64.length > 4_000_000) return _json({ error: "Slika je prevelika" }, 413);
          const ext = mediaType === "image/png" ? "png" : mediaType === "image/webp" ? "webp" : "jpg";
          const owner = await _diaryPhotoHash(sub.email);
          const uuid = crypto.randomUUID().split("-")[0];
          const key = `diary/${owner}/${Date.now()}-${uuid}.${ext}`;
          const bytes = Uint8Array.from(atob(imgB64), c => c.charCodeAt(0));
          await env.PHOTOS_R2.put(key, bytes, { httpMetadata: { contentType: mediaType } });
          return _json({ ok: true, url: `/premium/diary/img/${key}` });
        }

        // ── GET /premium/diary/img/<key> — serve a diary photo (own photos only)
        if (path.startsWith("/premium/diary/img/")) {
          const sub = await _authedSub();
          if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          if (!env.PHOTOS_R2) return _json({ error: "Shramba slik ni na voljo" }, 503);
          const key = path.slice("/premium/diary/img/".length);
          const owner = await _diaryPhotoHash(sub.email);
          if (!key.startsWith(`diary/${owner}/`)) return _json({ error: "Ni dovoljeno" }, 403);
          const obj = await env.PHOTOS_R2.get(key);
          if (!obj) return new Response("Not found", { status: 404, headers: CORS_ALLOWED });
          return new Response(obj.body, {
            headers: { ...CORS_ALLOWED, "Content-Type": obj.httpMetadata?.contentType || "image/jpeg",
              "Cache-Control": "private, max-age=86400" },
          });
        }

        // ── GET /premium/diary — vrni celoten dnevnik za napravo/e
        if (path === "/premium/diary" && request.method === "GET") {
          const sub = await _authedSub();
          if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          let entries = [];
          try { entries = JSON.parse(await kv.get(`premium:diary:${sub.email}`)) || []; } catch (_) {}
          return _json({ ok: true, entries });
        }

        // ── POST /premium/diary { entries:[...] } — zamenjaj celoten dnevnik
        if (path === "/premium/diary" && request.method === "POST") {
          const sub = await _authedSub();
          if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          if (!Array.isArray(body.entries)) return _json({ error: "Manjka seznam najdb" }, 422);
          if (body.entries.length > 2000) return _json({ error: "Predolg dnevnik" }, 413);
          const raw = JSON.stringify(body.entries);
          if (raw.length > 1024 * 1024) return _json({ error: "Dnevnik je prevelik" }, 413);
          await kv.put(`premium:diary:${sub.email}`, raw);
          return _json({ ok: true, count: body.entries.length });
        }

        // ── GET /premium/alerts — vrni lastna pravila za "moje alarme"
        if (path === "/premium/alerts" && request.method === "GET") {
          const sub = await _authedSub();
          if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          let rules = [];
          try { rules = JSON.parse(await kv.get(`premium:alertrules:${sub.email}`)) || []; } catch (_) {}
          return _json({ ok: true, rules });
        }

        // ── POST /premium/alerts { rules:[{species_id,location,min_elev_m,threshold}] }
        // Vsako pravilo se preveri ob dnevnem /premium/notify: species_id/location
        // null = katerakoli vrsta/območje (isto kot stari privzeti globalni alarm).
        if (path === "/premium/alerts" && request.method === "POST") {
          const sub = await _authedSub();
          if (!sub) return _json({ error: "Neveljaven ali potekel dostop", code: 401 }, 401);
          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          if (!Array.isArray(body.rules)) return _json({ error: "Manjka seznam pravil" }, 422);
          const MAX_RULES = 5;
          if (body.rules.length > MAX_RULES) return _json({ error: `Največ ${MAX_RULES} alarmov` }, 413);

          let knownSpecies = null, knownLocations = null;
          try {
            const raw = await kv.get("premium:data");
            if (raw) {
              const data = JSON.parse(raw);
              knownSpecies = new Set(Object.keys(data.species_meta || {}));
              knownLocations = new Set((data.locations || []).map(l => l.name));
            }
          } catch (_) {}

          const clean = [];
          for (const r of body.rules) {
            if (!r || typeof r !== "object") continue;
            const species_id = r.species_id ? String(r.species_id).slice(0, 80) : null;
            if (species_id && knownSpecies && !knownSpecies.has(species_id))
              return _json({ error: "Neznana vrsta v pravilu" }, 422);
            const location = r.location ? String(r.location).slice(0, 80) : null;
            if (location && knownLocations && !knownLocations.has(location))
              return _json({ error: "Neznano območje v pravilu" }, 422);
            const min_elev_m = (r.min_elev_m === null || r.min_elev_m === undefined || r.min_elev_m === "")
              ? null : Math.max(0, Math.min(3000, parseInt(r.min_elev_m, 10) || 0));
            const threshold = Math.max(1, Math.min(100, parseInt(r.threshold, 10) || 70));
            clean.push({ species_id, location, min_elev_m, threshold });
          }
          await kv.put(`premium:alertrules:${sub.email}`, JSON.stringify(clean));
          return _json({ ok: true, count: clean.length });
        }

        // ── POST /premium/notify — daily per-user "my conditions match" alert (from CI)
        // Each subscriber has up to 5 rules (premium:alertrules:<email>); a
        // subscriber with none saved yet falls back to the original single
        // "any species, any forest, ≥ PREMIUM_ALERT_THRESHOLD" behaviour, so
        // existing subscribers keep getting alerts without any action.
        if (path === "/premium/notify" && request.method === "POST") {
          const secret = env.PREMIUM_SYNC_KEY;
          const auth = request.headers.get("Authorization") || "";
          if (!secret || !_tsEqual(auth, `Bearer ${secret}`)) return _json({ error: "Nedovoljeno" }, 401);

          const raw = await kv.get("premium:data");
          if (!raw) return _json({ error: "Ni podatkov" }, 503);
          let data; try { data = JSON.parse(raw); } catch (_) { return _json({ error: "Pokvarjeni podatki" }, 500); }
          const meta = data.species_meta || {};
          const defaultThreshold = parseInt(env.PREMIUM_ALERT_THRESHOLD || "70", 10);
          const cooldownD = parseInt(env.PREMIUM_ALERT_COOLDOWN_DAYS || "5", 10);
          const today = new Date().toISOString().slice(0, 10);

          // Best (forest, species) match for one rule among today's data, or
          // null if nothing in scope reaches the rule's own threshold.
          function evalRule(rule) {
            let best = null;
            for (const loc of data.locations || []) {
              if (rule.location && loc.name !== rule.location) continue;
              if (rule.min_elev_m != null && (loc.elev_m == null || loc.elev_m < rule.min_elev_m)) continue;
              const d0 = (loc.days || [])[0];
              if (!d0) continue;
              let index, species;
              if (rule.species_id) {
                const s = (d0.species || []).find(x => x.id === rule.species_id);
                if (!s) continue;
                index = s.index; species = meta[rule.species_id]?.name_sl || rule.species_id;
              } else {
                index = d0.overall;
                const top = (d0.species || [])[0];
                species = top ? (meta[top.id]?.name_sl || null) : null;
              }
              if (!best || index > best.index) best = { index, level: d0.level, forest: loc.name, species };
            }
            return (best && best.index >= (rule.threshold || defaultThreshold)) ? best : null;
          }

          const toNotify = []; // { email, hits }
          let checked = 0;
          let cursor;
          do {
            const page = await kv.list({ prefix: "premium:sub:", cursor });
            for (const k of page.keys) {
              let s; try { s = JSON.parse(await kv.get(k.name)); } catch (_) { continue; }
              if (!s?.email || s.alerts === false) continue;
              if (!s.expires || new Date(s.expires) < new Date()) continue;
              checked++;

              let rules;
              try { rules = JSON.parse(await kv.get(`premium:alertrules:${s.email}`)); } catch (_) { rules = null; }
              if (!Array.isArray(rules) || !rules.length)
                rules = [{ species_id: null, location: null, min_elev_m: null, threshold: defaultThreshold }];

              const hits = rules.map(evalRule).filter(Boolean);
              if (!hits.length) continue;

              const stateKey = `premium:alertstate:${s.email}`;
              let state; try { state = JSON.parse(await kv.get(stateKey)); } catch (_) { state = null; }
              if (state?.date) {
                const days = (Date.parse(today) - Date.parse(state.date)) / 864e5;
                if (days < cooldownD) continue;
              }
              hits.sort((a, b) => b.index - a.index);
              toNotify.push({ email: s.email, hits });
              await kv.put(stateKey, JSON.stringify({ date: today }));
            }
            cursor = page.list_complete ? null : page.cursor;
          } while (cursor);

          ctx.waitUntil((async () => {
            for (const { email, hits } of toNotify) {
              const best = hits[0];
              const rows = hits.map(h => `<li><strong>${h.forest}</strong>` +
                (h.species ? ` — ${h.species}` : "") + `: <strong>${h.index}% (${h.level})</strong></li>`).join("");
              const tok = await _newToken(email);
              const off = `${url.origin}/premium/alerts/off?token=${tok}`;
              await _sendMail(email, `🍄 Gobarski pogoji ustrezajo tvojemu alarmu — ${best.forest} ${best.index}%`,
                `<p>Pozdravljen, gobar!</p>` +
                `<p>Tvoji pogoji za alarm so danes izpolnjeni:</p><ul>${rows}</ul>` +
                `<p><a href="${PAGE_URL}?token=${tok}" style="display:inline-block;background:#4d9ff8;color:#04070e;padding:.6rem 1.2rem;border-radius:8px;text-decoration:none;font-weight:600">Odpri 7-dnevno napoved po vrstah 🍄</a></p>` +
                `<p style="color:#888;font-size:.85rem">Indeks je ocena ugodnosti pogojev, ne obljuba najdbe — gozd ima zadnjo besedo.</p>` +
                `<hr style="border:none;border-top:1px solid #eee;margin:1.2rem 0"><p style="color:#999;font-size:.8rem"><a href="${off}" style="color:#999">Ne želim več obvestil o pogojih</a></p>`);
            }
          })());
          return _json({ ok: true, checked, notified: toNotify.length });
        }

        // ── GET /premium/alerts/off?token=… — opt out of the optimal-conditions email
        if (path === "/premium/alerts/off" && request.method === "GET") {
          const tok = _bearer();
          let rec; try { rec = JSON.parse(await kv.get(`premium:tok:${tok}`)); } catch (_) { rec = null; }
          if (rec?.email) {
            const sub = await _subFor(rec.email);
            if (sub) { sub.alerts = false; await kv.put(`premium:sub:${rec.email}`, JSON.stringify(sub)); }
          }
          return new Response(
            "<!doctype html><meta charset=utf-8><body style='font-family:system-ui;background:#04070e;color:#e8edf8;text-align:center;padding:3rem'>" +
            "<h1>Odjavljen 👋</h1><p>Ne bomo ti več pošiljali obvestil o optimalnih pogojih. Dostop do napovedi ostane aktiven.</p>" +
            "<p><a href='" + PAGE_URL + "' style='color:#4d9ff8'>← Na gobarsko napoved</a></p></body>",
            { headers: { ...CORS_ALLOWED, "Content-Type": "text/html; charset=utf-8" } });
        }

        return _json({ error: "Nedovoljena metoda ali pot" }, 405);
      }

      // ── /daily-post (jutranji predlogi članka + izbira po e-pošti) ─────
      //   POST /daily-post/proposals { secret, date, proposals:[{id,title,teaser}] }
      //        → shrani v KV in Filipu pošlje e-mail s povezavami za izbiro
      //   GET  /daily-post/pick?date=…&id=…&sig=…
      //        → preveri HMAC podpis in sproži GitHub workflow za objavo izbranega
      if (path === "/daily-post/proposals" || path === "/daily-post/pick") {
        const GH_REPO = "ibanezar/weather-station";
        const secret = env.SUBSCRIBE_SECRET || env.DELETE_SECRET;
        const _esc = s => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const _json = (obj, status) => new Response(JSON.stringify(obj), {
          status: status || 200, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const _page = (title, body, status) => new Response(
          `<!doctype html><html lang="sl"><head><meta charset="utf-8">` +
          `<meta name="viewport" content="width=device-width,initial-scale=1">` +
          `<title>${_esc(title)} · Meteorec</title>` +
          `<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;` +
          `background:#04070e;color:#e8edf8;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;padding:1.5rem}` +
          `.card{max-width:440px;background:rgba(10,15,28,.94);border:1px solid rgba(255,255,255,.11);` +
          `border-radius:16px;padding:2rem;text-align:center;box-shadow:0 4px 28px rgba(0,0,0,.3)}` +
          `h1{font-size:1.3rem;margin:0 0 .6rem}p{color:#adc0d8;line-height:1.6;margin:.4rem 0}` +
          `a{color:#4d9ff8;text-decoration:none}</style></head>` +
          `<body><div class="card">${body}<p style="margin-top:1.2rem"><a href="https://meteorec.si/blog/">← Na blog</a></p></div></body></html>`,
          { status: status || 200, headers: { "Content-Type": "text/html; charset=utf-8" } });
        const _hmacHex = async (msg) => {
          const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret),
            { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
          const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
          return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("");
        };
        const _kvKey = d => "dailypost:" + d;

        if (path === "/daily-post/proposals" && request.method === "POST") {
          let body;
          try { body = await request.json(); } catch (_) { return _json({ error: "Napačni podatki" }, 400); }
          if (!secret || body.secret !== secret) return _json({ error: "Nedovoljeno" }, 401);
          const date = String(body.date || "");
          if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return _json({ error: "Neveljaven datum" }, 400);
          const proposals = (Array.isArray(body.proposals) ? body.proposals : [])
            .slice(0, 5)
            .map(p => ({
              id: String(p.id || "").slice(0, 60),
              title: String(p.title || "").slice(0, 200),
              teaser: String(p.teaser || "").slice(0, 600),
            }))
            .filter(p => p.id && p.title);
          if (!proposals.length) return _json({ error: "Ni predlogov" }, 400);
          await env.COUNTER_KV.put(_kvKey(date), JSON.stringify({ proposals, picked: null }),
            { expirationTtl: 3 * 86400 });

          const items = [];
          for (let i = 0; i < proposals.length; i++) {
            const p = proposals[i];
            const sig = await _hmacHex(date + "|" + p.id);
            const link = `${url.origin}/daily-post/pick?date=${encodeURIComponent(date)}&id=${encodeURIComponent(p.id)}&sig=${sig}`;
            items.push(
              `<div style="margin:0 0 1.6rem">` +
              `<p style="margin:0 0 .3rem;font-size:.8rem;color:#999">Predlog ${i + 1}</p>` +
              `<h3 style="margin:0 0 .4rem">${_esc(p.title)}</h3>` +
              (p.teaser ? `<p style="margin:0 0 .6rem;color:#444">${_esc(p.teaser)}</p>` : "") +
              `<a href="${link}" style="display:inline-block;background:#4d9ff8;color:#04070e;padding:.5rem 1.1rem;border-radius:8px;text-decoration:none;font-weight:600">Objavi ta članek →</a>` +
              `</div>`);
          }
          const html =
            `<h2 style="margin:0 0 1rem">Predlogi za današnji članek (${_esc(date)})</h2>` + items.join("") +
            `<hr style="border:none;border-top:1px solid #eee;margin:1.5rem 0">` +
            `<p style="color:#999;font-size:.8rem">Klik na gumb sproži pisanje in objavo izbranega članka ` +
            `(na blogu je čez ~5 minut). Izbereš lahko samo enega. Če ne izbereš nobenega, danes ne bo objave.</p>`;
          if (env.RESEND_API_KEY) {
            const from = env.NOTIFY_FROM || "Meteorec <onboarding@resend.dev>";
            const to = env.DAILY_POST_EMAIL || "filip.eremita@gmail.com";
            ctx.waitUntil(fetch("https://api.resend.com/emails", {
              method: "POST",
              headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
              body: JSON.stringify({ from, to, subject: `Meteorec: 3 predlogi za dnevni članek (${date})`, html }),
            }).catch(() => {}));
          }
          return _json({ ok: true, proposals: proposals.length, emailed: Boolean(env.RESEND_API_KEY) });
        }

        if (path === "/daily-post/pick" && request.method === "GET") {
          if (!secret) return _page("Napaka", "<h1>Strežnik ni pravilno nastavljen</h1><p>Manjka skrivnost za preverjanje povezave.</p>", 503);
          const date = url.searchParams.get("date") || "";
          const id = url.searchParams.get("id") || "";
          const sig = url.searchParams.get("sig") || "";
          if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !id || (await _hmacHex(date + "|" + id)) !== sig) {
            return _page("Neveljavna povezava", "<h1>Povezava ni veljavna</h1><p>Podpis se ne ujema ali pa je povezava okrnjena.</p>", 403);
          }
          let rec = null;
          try { rec = JSON.parse(await env.COUNTER_KV.get(_kvKey(date))); } catch (_) {}
          if (!rec) return _page("Poteklo", "<h1>Predlogi niso več na voljo</h1><p>Za ta dan ni shranjenih predlogov (povezave veljajo 3 dni).</p>", 404);
          const chosen = (rec.proposals || []).find(p => p.id === id);
          if (!chosen) return _page("Napaka", "<h1>Predlog ne obstaja</h1><p>Ta predlog ni med shranjenimi za izbrani dan.</p>", 404);
          if (rec.picked) {
            const prev = (rec.proposals || []).find(p => p.id === rec.picked);
            return _page("Že izbrano", `<h1>Izbira je že opravljena ✅</h1><p>Za ta dan je izbran: <strong>${_esc(prev ? prev.title : rec.picked)}</strong>.</p>`);
          }
          if (!env.GH_WORKFLOW_TOKEN) {
            return _page("Ročni korak", `<h1>Worker nima GH_WORKFLOW_TOKEN</h1>` +
              `<p>Objave ne morem sprožiti samodejno. Odpri <a href="https://github.com/${GH_REPO}/actions/workflows/daily-post.yml">workflow »Dnevni članek«</a>, ` +
              `klikni »Run workflow« in v polje choice vpiši: <strong>${_esc(id)}</strong>.</p>`, 503);
          }
          // Označi izbiro PRED sprožitvijo (zaščita pred dvojnim klikom); ob
          // neuspehu sprožitve izbiro povrni, da je ponovni poskus mogoč.
          rec.picked = id;
          await env.COUNTER_KV.put(_kvKey(date), JSON.stringify(rec), { expirationTtl: 3 * 86400 });
          const ghRes = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/workflows/daily-post.yml/dispatches`, {
            method: "POST",
            headers: {
              "Authorization": `Bearer ${env.GH_WORKFLOW_TOKEN}`,
              "Accept": "application/vnd.github+json",
              "Content-Type": "application/json",
              "User-Agent": "Meteorec-Worker/1.0 (+https://meteorec.si)",
            },
            body: JSON.stringify({ ref: "main", inputs: { choice: id } }),
          });
          if (ghRes.status !== 204) {
            rec.picked = null;
            await env.COUNTER_KV.put(_kvKey(date), JSON.stringify(rec), { expirationTtl: 3 * 86400 });
            const detail = (await ghRes.text()).slice(0, 200);
            return _page("Napaka", `<h1>Objave ni bilo mogoče sprožiti</h1><p>GitHub je vrnil ${ghRes.status}.</p>` +
              `<p style="font-size:.8rem;color:#8a97ad">${_esc(detail)}</p>` +
              `<p>Poskusi znova čez minuto ali sproži workflow ročno (choice: <strong>${_esc(id)}</strong>).</p>`, 502);
          }
          return _page("Izbrano", `<h1>Članek je v izdelavi ✅</h1><p><strong>${_esc(chosen.title)}</strong></p>` +
            `<p>Pisanje, lektura in objava trajajo približno 5 minut, nato bo članek na blogu.</p>`);
        }

        return _json({ error: "Nedovoljena metoda" }, 405);
      }

      // ── /push (web push obvestila) ──────────────────────────
      //   GET  /push/vapid                       → { publicKey }
      //   POST /push/subscribe   { subscription } → shrani naročnino
      //   POST /push/unsubscribe { endpoint }     → odstrani
      //   POST /push/send        { secret, title, body, url? } → pošlji vsem
      // Naročnine v R2: push/subs.json
      // ── /nowcast — stanje po vaseh + seznam vasi za izbirnik ──
      //   GET /nowcast/vasi   → seznam vasi (za spustni seznam na strani)
      //   GET /nowcast        → zadnji izračun za vse vasi
      //   GET /nowcast?vas=id → samo ena vas
      if (path === "/nowcast/vasi" && request.method === "GET") {
        return new Response(JSON.stringify({ vasi: NOWCAST_VASI.map(v => ({ id: v.id, ime: v.name })) }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=86400" }
        });
      }
      if (path === "/nowcast" && request.method === "GET") {
        let data = null;
        try { const o = await env?.PHOTOS_R2?.get("nowcast/latest.json"); data = o ? JSON.parse(await o.text()) : null; } catch (_) {}
        // Predpomnjeni izračun je star največ en cron (5 min); če ga (še) ni,
        // ga izračunamo sproti, da stran ni prazna ob prvem obisku.
        const starost = data ? (Date.now() - new Date(data.ts).getTime()) / 60000 : Infinity;
        if (!data || starost > 12) data = (await _radNowcastAll(env).catch(() => null)) || data;
        if (!data) return new Response(JSON.stringify({ error: "Radarska slika ni dosegljiva" }), {
          status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const vas = url.searchParams.get("vas");
        const body = vas ? { ...data, vasi: data.vasi.filter(v => v.id === vas) } : data;
        return new Response(JSON.stringify(body), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=120" }
        });
      }

      if (path === "/push/vapid" && request.method === "GET") {
        return new Response(JSON.stringify({ publicKey: VAPID_PUBLIC }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=86400" }
        });
      }
      if (path === "/push/subscribe" || path === "/push/unsubscribe" || path === "/push/send") {
        const r2 = env?.PHOTOS_R2;
        const KEY = "push/subs.json";
        const pj = (o, s) => new Response(JSON.stringify(o), { status: s || 200, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        async function pRead() { if (!r2) return []; try { const o = await r2.get(KEY); return o ? JSON.parse(await o.text()) : []; } catch (_) { return []; } }
        async function pWrite(a) { if (r2) await r2.put(KEY, JSON.stringify(a), { httpMetadata: { contentType: "application/json" } }); }

        if (request.method !== "POST") return pj({ error: "Nedovoljena metoda" }, 405);
        let body; try { body = await request.json(); } catch (_) { return pj({ error: "Napačni podatki" }, 400); }

        if (path === "/push/subscribe") {
          if (!r2) return pj({ error: "Shramba ni dosegljiva" }, 503);
          const s = body.subscription || body;
          if (!s || !s.endpoint || !s.keys || !s.keys.p256dh || !s.keys.auth) return pj({ error: "Neveljavna naročnina" }, 400);
          // Vas je edini podatek o lokaciji, ki ga hranimo — izbrana s seznama,
          // ne iz GPS. Neznan id zavržemo, da v shrambo ne pride poljuben niz.
          const vas = NOWCAST_VASI.some(v => v.id === body.vas) ? body.vas : null;
          // "digest" (jutranji povzetek) je LOČEN opt-in od splošnih vremenskih
          // opozoril — kdor vklopi 🔔 Obvestila, je pristal na huda vremena in
          // nowcast, ne na dnevni potisk. Zato ga posodobimo samo, če ga klic
          // izrecno pošlje (boolean), sicer obstoječa vrednost ostane
          // nedotaknjena — klic, ki posodablja samo vas, drugače ne bi smel
          // tiho izklopiti že vklopljenega povzetka.
          const hasDigest = typeof body.digest === "boolean";
          const subs = await pRead();
          const obstoječa = subs.find(x => x.endpoint === s.endpoint);
          if (obstoječa) {
            let changed = false;
            if (vas && obstoječa.vas !== vas) { obstoječa.vas = vas; changed = true; }
            if (hasDigest && obstoječa.digest !== body.digest) { obstoječa.digest = body.digest; changed = true; }
            if (changed) await pWrite(subs);
          } else {
            subs.push({ endpoint: s.endpoint, keys: { p256dh: s.keys.p256dh, auth: s.keys.auth }, vas, digest: hasDigest ? body.digest : false, ts: new Date().toISOString() });
            await pWrite(subs.slice(0, 5000));
          }
          return pj({ ok: true, count: subs.length, vas });
        }
        if (path === "/push/unsubscribe") {
          if (!r2) return pj({ ok: true });
          const ep = body.endpoint || (body.subscription && body.subscription.endpoint);
          const subs = await pRead();
          const next = subs.filter(x => x.endpoint !== ep);
          if (next.length !== subs.length) await pWrite(next);
          return pj({ ok: true });
        }
        if (path === "/push/send") {
          const secret = env.SUBSCRIBE_SECRET || env.DELETE_SECRET;
          if (!secret || body.secret !== secret) return pj({ error: "Nedovoljeno" }, 401);
          if (!env.VAPID_PRIVATE) return pj({ error: "VAPID_PRIVATE ni nastavljen" }, 503);
          const payload = { title: (body.title || "Meteorec").slice(0, 100), body: (body.body || "").slice(0, 300), url: body.url || "/", tag: body.tag || "meteorec" };
          // audience:"digest" cilja samo naročnike, ki so vklopili jutranji
          // povzetek (glej /push/subscribe zgoraj) — brez tega parametra je
          // vedenje nespremenjeno (pošlje vsem), kot doslej za huda vremena.
          const filter = body.audience === "digest" ? (s => s.digest === true) : null;
          const res = await _pushAll(env, payload, filter);
          return pj({ ok: true, ...res });
        }
      }

      // ── /current ali /hourly ──────────────────────────────
      const apiUrl = path === "/hourly" ? HOURLY_URL : CURRENT_URL;
      const res = await fetch(apiUrl, { headers: { "Accept": "application/json" } });
      const bodyText = await res.text();

      // Weather Underground se polni prek Ecowitt-konzolinega WU-uploada; ta
      // lahko odpove (npr. ugasnjen upload), medtem ko postaja sama še naprej
      // normalno poroča v Ecowitt oblak. V takem primeru je WU odgovor prazen
      // ali zastarel (obsTimeUtc star >30 min) — za "/current" zato preverimo
      // svežino in po potrebi preklopimo na Ecowitt real_time kot rezervo, da
      // se osrednji prikaz na strani ne "zamrzne".
      if (path !== "/hourly") {
        let obs = null;
        try { obs = JSON.parse(bodyText)?.observations?.[0]; } catch (_) { /* ignore */ }
        const ageMin = obs?.obsTimeUtc
          ? (Date.now() - new Date(obs.obsTimeUtc).getTime()) / 60000
          : Infinity;
        // WU upload je lahko "svež" po času, a s praznimi (null) meritvami —
        // ne samo zastarel. Rezervo zato sprožimo tudi, če manjka temperatura.
        if (!obs || ageMin > 30 || obs?.metric?.temp == null) {
          const fallback = await fetchEcowittAsWuObs(env);
          if (fallback) {
            return new Response(JSON.stringify({ observations: [fallback] }), {
              status: 200,
              headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
            });
          }
        }
      }

      return new Response(bodyText, {
        status: res.status,
        headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
      });

    } catch (e) {
      return new Response(
        JSON.stringify({ error: e.message }),
        { status: 500, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } }
      );
    }
  }
};
