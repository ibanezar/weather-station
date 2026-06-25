// ═══════════════════════════════════════════════════════════
// Cloudflare Worker — IREICA1 Weather Proxy
// ═══════════════════════════════════════════════════════════

const STATION = "IREICA1";
const WU_KEY  = "619a8bb3ba4d42069a8bb3ba4d02061f";
const WU_BASE = "https://api.weather.com/v2/pws/";
const CURRENT_URL = WU_BASE+"observations/current?stationId="+STATION+"&format=json&units=m&apiKey="+WU_KEY;
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

function isAllowedOrigin(request) {
  const origin  = request.headers.get("Origin")  || "";
  const referer = request.headers.get("Referer") || "";
  // Facebook IAB and other embedded WebViews either strip Origin entirely or
  // send the literal string "null" (opaque-origin sandboxed context).
  if (!origin || origin === "null") {
    if (!referer) return true;
    return ALLOWED_ORIGINS.some(o => referer.startsWith(o));
  }
  return ALLOWED_ORIGINS.some(o => origin.startsWith(o) || referer.startsWith(o));
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
  const body = new URLSearchParams({
    application_key: app, api_key: api, mac: EW_MAC,
    start_date: start+" 00:00:00", end_date: end+" 23:59:59",
    cycle_type: "1",
    call_back: "outdoor.temperature,outdoor.humidity,wind.wind_speed,rainfall.daily,pressure.relative",
    temp_unitid:"1", pressure_unitid:"5", wind_speed_unitid:"7", rainfall_unitid:"12"
  });
  const res = await fetch("https://api.ecowitt.net/api/v3/device/history", {
    method: "POST",
    headers: {"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"},
    body: body.toString()
  });
  const json = await res.json();
  if (json.code !== 0) throw new Error("Ecowitt "+json.code+": "+json.msg);
  return json.data;
}

const tsToDate = ts => new Date(parseInt(ts)*1000).toISOString().slice(0,10);
const pf = v => v==null?null:typeof v==="object"?parseFloat(v.avg??v.max??Object.values(v)[0])||null:parseFloat(v)||null;

function normalize(data){
  const days={};
  const get=ts=>{const d=tsToDate(ts);if(!days[d])days[d]={obsTimeLocal:d,_h:[],_l:[],_a:[],_wH:[],_wA:[],_hum:[],_r:[]};return days[d];};
  const L=(...p)=>{let c=data;for(const k of p){c=c?.[k];if(c==null)return{};}return c?.list||{};};
  for(const[ts,v] of Object.entries(L("outdoor","temperature")||{})){
    const b=get(ts);b._h.push(parseFloat(v.max??v.avg??0)||null);b._l.push(parseFloat(v.min??v.avg??0)||null);b._a.push(pf(v));
  }
  for(const[ts,v] of Object.entries(L("outdoor","humidity")||{})) get(ts)._hum.push(pf(v));
  for(const[ts,v] of Object.entries(L("wind","wind_speed")||{})){
    const b=get(ts);b._wH.push(parseFloat(v.max??v.avg??0)||null);b._wA.push(pf(v));
  }
  const rList=L("rainfall","daily")||{};
  for(const[ts,v] of Object.entries(rList)) get(ts)._r.push(typeof v==="object"?parseFloat(v.total??v.max??0)||0:parseFloat(v)||0);
  const avg=a=>{const f=a.filter(x=>x!=null);return f.length?f.reduce((x,y)=>x+y,0)/f.length:null;};
  return Object.values(days).map(b=>({obsTimeLocal:b.obsTimeLocal,metric:{
    tempHigh:     b._h.filter(x=>x).length?Math.max(...b._h.filter(x=>x)):null,
    tempLow:      b._l.filter(x=>x).length?Math.min(...b._l.filter(x=>x)):null,
    tempAvg:      avg(b._a),
    windspeedHigh:b._wH.filter(x=>x).length?Math.max(...b._wH.filter(x=>x)):null,
    windspeedAvg: avg(b._wA),
    humidityAvg:  avg(b._hum)!=null?Math.round(avg(b._hum)):null,
    precipTotal:  b._r.length?Math.max(...b._r):0,
  }})).filter(s=>s.metric.tempHigh!=null).sort((a,b)=>a.obsTimeLocal.localeCompare(b.obsTimeLocal));
}

// ── Visitor counter (in-memory, resets on Worker restart) ─
// Za pravi persistentni counter potrebuješ Cloudflare KV binding "COUNTER_KV"
let _memCount = 1000; // začetna vrednost — nastavi po želji

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

export default {
  async fetch(request, env) {
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
      // ARSO hidrološka postaja — vodostaj Savinje pri Mozirju/Letušu
      // Poskusi GeoJSON feed z vsemi postajami, filtriraj za Savinjo v bližini
      if (path === "/arso-water") {
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
            const ct = r.headers.get("Content-Type") || "";
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
