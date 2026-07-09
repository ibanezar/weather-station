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

const EW_APP_FALLBACK = "A7E5CAF73FCC9BF859CDE788D69A1C91";
const EW_API_FALLBACK = "0bd213c8-8e54-4bf6-b6da-127a1c605034";
const EW_MAC = "BC:DD:C2:42:8D:56";

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

function _arsoExtractProse(body, ct) {
  const proses = [];
  const isProse = s => s.length > 45 && /\s/.test(s) && /[a-zčšžćđA-ZČŠŽ]/.test(s);
  const push = s => {
    s = (s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    if (isProse(s)) proses.push(s);
  };
  let parsed = null;
  if (/json/i.test(ct) || /^\s*[\{\[]/.test(body)) {
    try { parsed = JSON.parse(body); } catch (_) {}
  }
  if (parsed) {
    const walk = v => {
      if (typeof v === "string") push(v);
      else if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v === "object") Object.values(v).forEach(walk);
    };
    walk(parsed);
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

async function fetchArsoText() {
  for (const url of ARSO_TEXT_ENDPOINTS) {
    try {
      const r = await _arsoFetch(url);
      if (!r.ok) continue;
      const ct = r.headers.get("content-type") || "";
      const proses = _arsoExtractProse(await r.text(), ct);
      if (proses.length) {
        let t = proses.slice(0, 2).join(" ");
        if (t.length > 600) t = t.slice(0, 580).replace(/\s+\S*$/, "") + "…";
        return { text: t, source: "ARSO", url };
      }
    } catch (_) {}
  }
  return { text: null, source: null, url: null };
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
  if (!wsi) return [];

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
          });
        }
      }
      return; // don't recurse into an event node's children
    }
    Object.values(node).forEach(walkEvents);
  };

  walkEvents(wsi);
  return alerts;
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
const _memPoll = {}; // fallback za dnevni poll, kadar KV ni na voljo (resetira se ob restartu)

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
// Pošlji obvestilo VSEM naročnikom (počisti potekle). Vrne {sent, pruned}.
async function _pushAll(env, payload) {
  const r2 = env?.PHOTOS_R2; if (!r2 || !env.VAPID_PRIVATE) return { sent: 0, pruned: 0 };
  let subs = []; try { const o = await r2.get("push/subs.json"); subs = o ? JSON.parse(await o.text()) : []; } catch (_) {}
  const dead = [];
  await Promise.all(subs.map(async s => {
    try { const st = await _sendPush(env, s, payload); if (st === 404 || st === 410) dead.push(s.endpoint); }
    catch (_) {}
  }));
  if (dead.length) await r2.put("push/subs.json", JSON.stringify(subs.filter(x => dead.indexOf(x.endpoint) === -1)), { httpMetadata: { contentType: "application/json" } });
  return { sent: subs.length - dead.length, pruned: dead.length };
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

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(_cronCheckThresholds(env));
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

    // /ai-debug is openable directly in a browser for troubleshooting
    if (!isAllowedOrigin(request) && path !== "/ai-debug") {
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
          const alerts = await fetchArsoWarnings();
          return new Response(JSON.stringify({ alerts, source: "arso-api" }), {
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
            return new Response(JSON.stringify({ alerts, source: "arso-atom" }), {
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

      // ── /like ─────────────────────────────────────────────
      // Všečki na blog posta. Ključ v KV: "like:<slug>".
      // GET  /like?slug=xxx            → { slug, count }
      // POST /like?slug=xxx&delta=1|-1 → poveča/zmanjša in vrne { slug, count }
      // Persistenca zahteva KV binding COUNTER_KV; brez njega vrne in-memory vrednost.
      if (path === "/like") {
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
        return new Response(JSON.stringify(ewData), {
          headers: {...CORS_ALLOWED, "Content-Type":"application/json", "Cache-Control":"max-age=120"}
        });
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
          if (!days[date]) days[date] = { temps: [], winds: [], rain: 0, syms: [], noonSym: null };
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
        const summaries = Object.entries(days)
          .filter(([d]) => d >= todayKey)
          .sort(([a],[b]) => a < b ? -1 : 1)
          .slice(0, 7)
          .map(([date, d]) => {
            const dt = new Date(date + 'T12:00:00');
            const rawSym = d.noonSym || d.syms[Math.floor(d.syms.length/2)] || 'partlycloudy_day';
            const isToday = date === todayKey;
            return {
              date,
              dayName: isToday ? 'danes' : SL_DAYS[dt.getDay()],
              tmax: d.temps.length ? Math.round(Math.max(...d.temps)) : null,
              tmin: d.temps.length ? Math.round(Math.min(...d.temps)) : null,
              windMax: d.winds.length ? Math.round(Math.max(...d.winds)) : null,
              rain: Math.round(d.rain * 10) / 10,
              symbol: rawSym,        // raw yr.no code (frontend maps to emoji)
              symbolText: symLabel(rawSym),
            };
          });

        if (!summaries.length) throw new Error("yr.no: no data");

        // 1) ARSO official Slovenian text forecast (tried via fetchArsoText)
        let text = null, source = "yr.no";
        if (arsoTry.status === "fulfilled" && arsoTry.value?.text) {
          text = arsoTry.value.text;
          source = "ARSO";
        }

        // 2) Fallback: build a complete description from yr.no summaries
        if (!text) {
          const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
          const parts = [];
          const s0 = summaries[0];
          if (s0) {
            let p = `Danes bo na Rečici ob Savinji ${symLabel(s0.symbol)}, s temperaturo med ${s0.tmin} in ${s0.tmax} °C`;
            if (s0.rain >= 0.5) p += `, skupaj okoli ${s0.rain} mm padavin`;
            if (s0.windMax >= 30) p += `, veter v sunkih do ${s0.windMax} km/h`;
            parts.push(p + ".");
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
          text = parts.join(" ");
          source = "yr.no";
        }

        return new Response(JSON.stringify({ summaries, text, source }), {
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
        const metarUrl = `https://aviationweather.gov/api/data/metar?ids=${encodeURIComponent(station)}&format=json&taf=false&hours=${hours}`;
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
      if (path === "/arso-cam") {
        const station = url.searchParams.get("station") || "CELJE";
        const dir     = url.searchParams.get("dir")     || "sw";
        const s = station.replace(/[^A-Z0-9_-]/gi, "");
        const d = dir.replace(/[^a-z]/g, "");
        const camUrl = `https://meteo.arso.gov.si/uploads/probase/www/observ/webcam/${s}_dir/siwc_${s}_${d}.jpg`;
        const camRes = await fetch(camUrl, { headers: { "Referer": "https://meteo.arso.gov.si/" } });
        if (!camRes.ok) throw new Error("Kamera ni dostopna: HTTP " + camRes.status);
        const buf = await camRes.arrayBuffer();
        return new Response(buf, {
          headers: { ...CORS_ALLOWED, "Content-Type": "image/jpeg", "Cache-Control": "public, max-age=120" }
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
          const results = await Promise.all(
            urls.map(u => fetch(u, { headers: { "User-Agent": "Mozilla/5.0" } })
              .then(r => r.ok ? r.json() : null)
              .catch(() => null))
          );
          const filtered = results.filter(Boolean);
          return new Response(JSON.stringify(filtered), {
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
        const pvgisUrl = `https://re.jrc.ec.europa.eu/api/v5_2/MRcalc?lat=46.3258&lon=14.9211&outputformat=json&raddatabase=PVGIS-SARAH3&browser=0`;
        try {
          const r = await fetch(pvgisUrl, { headers: { "User-Agent": "Mozilla/5.0" } });
          if (!r.ok) throw new Error("HTTP " + r.status);
          const data = await r.json();
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
      // ARSO krajevna napoved — Rečica ob Savinji
      if (path === "/arso-forecast") {
        // Aggregate ARSO hourly/3-hourly metric slots into daily summaries
        const aggregateArsoDaily = (metric) => {
          if (!metric || !metric.length) return [];
          const map = {};
          for (const slot of metric) {
            const valid = slot.valid || '';
            const d = valid.slice(0, 10); // "YYYY-MM-DD" from ISO with offset
            if (!d.match(/^\d{4}-\d{2}-\d{2}$/)) continue;
            if (!map[d]) map[d] = { temps: [], slots: [] };
            if (slot.t != null) map[d].temps.push(slot.t);
            map[d].slots.push(slot);
          }
          return Object.entries(map).sort((a,b) => a[0] < b[0] ? -1 : 1).map(([date, {temps, slots}]) => {
            const tmax = temps.length ? Math.max(...temps) : null;
            const tmin = temps.length ? Math.min(...temps) : null;
            // Pick midday slot for the most representative description
            const noon = slots.find(s => (s.valid||'').includes('T12:00'))
              || slots.find(s => (s.valid||'').includes('T11:00'))
              || slots.find(s => (s.valid||'').includes('T13:00'))
              || slots[Math.floor(slots.length / 2)]
              || slots[0];
            const desc = noon.nn || noon.clouds_lowAlt_shortText || noon.weather_shortText_sl || '';
            return { valid_date: date, tmax, tmin, shortFcst_sl: desc };
          });
        }

        const arsoUrls = [
          "https://vreme.arso.gov.si/api/1.0/location/?location=Re%C4%8Dica+ob+Savinji&lang=sl",
          "https://vreme.arso.gov.si/api/1.0/forecast_geo/?lat=46.3258&lon=14.9211&lang=sl",
        ];
        for (const arsoUrl of arsoUrls) {
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
            // Normalize — ARSO returns {forecast:{location:{},metric:[]}} or {forecast:{...}}
            const fc = json?.forecast ?? json;
            const loc = fc?.location ?? {};
            // If ARSO provides already-daily data, use it; otherwise aggregate hourly metric slots
            let days = fc?.days ?? [];
            if (!days.length && fc?.metric?.length) {
              days = aggregateArsoDaily(fc.metric);
            }
            if (!days.length) continue;
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
      if (path === "/gallery") {
        if (!env.PHOTOS_R2) return new Response(JSON.stringify({ photos: [], error: "R2 not bound" }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
        });
        const listed = await env.PHOTOS_R2.list({ include: ["customMetadata", "httpMetadata"] });
        const photos = listed.objects
          .sort((a, b) => new Date(b.uploaded) - new Date(a.uploaded))
          .map(obj => ({
            key: obj.key,
            size: obj.size,
            uploaded: obj.uploaded,
            contentType: obj.httpMetadata?.contentType || "image/jpeg",
            ...(obj.customMetadata || {})
          }));
        return new Response(JSON.stringify({ photos, truncated: listed.truncated }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "no-cache" }
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
        await env.PHOTOS_R2.put(key, file.stream(), {
          httpMetadata: { contentType: file.type },
          customMetadata: {
            title:      (fd.get("title")   || "").slice(0, 120),
            caption:    (fd.get("caption") || "").slice(0, 500),
            author:     (fd.get("author")  || "Anonimno").slice(0, 60),
            weather:    (fd.get("weather") || "").slice(0, 200),
            uploadedAt: new Date().toISOString()
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
        const secret = env.DELETE_SECRET;
        const auth = request.headers.get("Authorization") || "";
        if (!secret || auth !== "Bearer " + secret) {
          return new Response(JSON.stringify({ error: "Nepooblaščen dostop" }), {
            status: 401, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
        }
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

      // ── /push (web push obvestila) ──────────────────────────
      //   GET  /push/vapid                       → { publicKey }
      //   POST /push/subscribe   { subscription } → shrani naročnino
      //   POST /push/unsubscribe { endpoint }     → odstrani
      //   POST /push/send        { secret, title, body, url? } → pošlji vsem
      // Naročnine v R2: push/subs.json
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
          const subs = await pRead();
          if (!subs.some(x => x.endpoint === s.endpoint)) {
            subs.push({ endpoint: s.endpoint, keys: { p256dh: s.keys.p256dh, auth: s.keys.auth }, ts: new Date().toISOString() });
            await pWrite(subs.slice(0, 5000));
          }
          return pj({ ok: true, count: subs.length });
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
          const res = await _pushAll(env, payload);
          return pj({ ok: true, ...res });
        }
      }

      // ── /current ali /hourly ──────────────────────────────
      const apiUrl = path === "/hourly" ? HOURLY_URL : CURRENT_URL;
      const res = await fetch(apiUrl, { headers: { "Accept": "application/json" } });
      return new Response(await res.text(), {
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
