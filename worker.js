// ═══════════════════════════════════════════════════════════
// Cloudflare Worker — IREICA1 Weather Proxy
// ═══════════════════════════════════════════════════════════

const STATION = "IREICA1";
const WU_KEY  = "619a8bb3ba4d42069a8bb3ba4d02061f";
const WU_BASE = "https://api.weather.com/v2/pws/";
const CURRENT_URL = WU_BASE+"observations/current?stationId="+STATION+"&format=json&units=m&apiKey="+WU_KEY;
const HOURLY_URL  = WU_BASE+"observations/hourly/7day?stationId="+STATION+"&format=json&units=m&apiKey="+WU_KEY+"&numericPrecision=decimal";

const ANTHROPIC_KEY = "REPLACE_WITH_ANTHROPIC_API_KEY";

// Ambee Weather Intelligence — pollen + AQI (registracija: ambeedata.com, free tier)
const AMBEE_KEY = "REPLACE_WITH_AMBEE_API_KEY";

// Google Maps Weather API key — pridobi na console.cloud.google.com → Weather API
const GOOGLE_WEATHER_KEY = "REPLACE_WITH_GOOGLE_MAPS_API_KEY";

const EW_APP = "66FE60BEB1C87BEBB8572050299DC8BA";
const EW_API = "a713a55b-9cb5-4dbb-8ad2-8e3f8f6b0661";
const EW_MAC = "BC:DD:C2:42:8D:56";

const ALLOWED_ORIGINS = [
  "https://ibanezar.github.io",
  "http://localhost",
  "http://127.0.0.1",
];

function isAllowedOrigin(request) {
  const origin  = request.headers.get("Origin")  || "";
  const referer = request.headers.get("Referer") || "";
  return ALLOWED_ORIGINS.some(o => origin.startsWith(o) || referer.startsWith(o));
}

const CORS_ALLOWED = {
  "Access-Control-Allow-Origin":  "https://ibanezar.github.io",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};
const CORS_DENY = { "Access-Control-Allow-Origin": "null" };

// ── Ecowitt helpers ────────────────────────────────────────
const pad = n => String(n).padStart(2, "0");
const fmtDate = d => d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());

async function fetchEcowitt(start, end) {
  if (EW_APP.startsWith("REPLACE")) return null;
  const body = new URLSearchParams({
    application_key: EW_APP, api_key: EW_API, mac: EW_MAC,
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
export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_ALLOWED });
    }
    if (!isAllowedOrigin(request)) {
      return new Response(
        JSON.stringify({ error: "Nepooblaščen dostop", code: 403 }),
        { status: 403, headers: { ...CORS_DENY, "Content-Type": "application/json" } }
      );
    }

    const url  = new URL(request.url);
    const path = url.pathname;

    try {

      // ── /arso-warning ─────────────────────────────────────
      // ARSO uradna vremensko opozorila — ATOM feed (strukturiran, zanesljiv)
      // Regija za Rečico ob Savinji: SLOVENIA_NORTH-EAST
      if (path === "/arso-warning") {
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
          if (!r.ok) throw new Error("ARSO HTTP " + r.status);
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
            // Primary: CAP severity attribute (structured, reliable)
            const capSev = (entry.match(/<cap:severity[^>]*>([\s\S]*?)<\/cap:severity>/i)?.[1] || '').trim().toLowerCase();
            if      (capSev === 'extreme')                    level = 'red';
            else if (capSev === 'severe')                     level = 'orange';
            else if (capSev === 'moderate' || capSev === 'minor') level = 'yellow';
            // Fallback: explicit color word in title/summary
            if (!level) {
              if      (/(rdeče?\s*opozorilo|red\s*warning)/i.test(content))    level = 'red';
              else if (/(oranžno?\s*opozorilo|orange\s*warning)/i.test(content)) level = 'orange';
              else if (/(rumeno?\s*opozorilo|yellow\s*warning)/i.test(content))  level = 'yellow';
            }
            if (level) alerts.push({ level, text: (summary || title).slice(0, 600) });
          }
          return new Response(JSON.stringify({ alerts, url: atomUrl }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=600" }
          });
        } catch (e) {
          return new Response(JSON.stringify({ alerts: [], error: e.message }), {
            headers: { ...CORS_ALLOWED, "Content-Type": "application/json" }
          });
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
        const data  = await fetchEcowitt(start, end);
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
        if (!EW_APP || EW_APP.startsWith("REPLACE") || !EW_API || EW_API.startsWith("REPLACE")) {
          return new Response(JSON.stringify({error:"no_key"}),
            {status:503, headers:{...CORS_ALLOWED,"Content-Type":"application/json"}});
        }
        const ewUrl = "https://api.ecowitt.net/api/v3/device/real_time?" + new URLSearchParams({
          application_key: EW_APP, api_key: EW_API, mac: EW_MAC,
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

      // ── /pollen ───────────────────────────────────────────
      // Ambee pollen + AQI — registracija: ambeedata.com → API Keys
      if (path === "/pollen") {
        if (!AMBEE_KEY || AMBEE_KEY.startsWith("REPLACE")) {
          return new Response(JSON.stringify({ error: "no_key" }),
            { status: 503, headers: { ...CORS_ALLOWED, "Content-Type": "application/json" } });
        }
        const lat = 46.325779, lng = 14.921137;
        const [polRes, aqRes] = await Promise.all([
          fetch(`https://api.ambeedata.com/latest/pollen/by-lat-lng?lat=${lat}&lng=${lng}`, {
            headers: { "x-api-key": AMBEE_KEY, "Accept": "application/json" }
          }),
          fetch(`https://api.ambeedata.com/latest/by-lat-lng?lat=${lat}&lng=${lng}`, {
            headers: { "x-api-key": AMBEE_KEY, "Accept": "application/json" }
          }),
        ]);
        const polData = polRes.ok ? await polRes.json() : null;
        const aqData  = aqRes.ok  ? await aqRes.json()  : null;
        return new Response(JSON.stringify({ pollen: polData, aqi: aqData }), {
          headers: { ...CORS_ALLOWED, "Content-Type": "application/json", "Cache-Control": "max-age=10800" }
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
