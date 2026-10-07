#!/usr/bin/env python3
"""
tools/generate_primerjava_modelov_page.py — /primerjava-modelov/

Napoved več modelov za Rečico ob Savinji drugo nad drugo: ICON-D2, ICON-EU,
ECMWF IFS (Open-Meteo) in AROME Avstrija z ansamblom (GeoSphere, 2,5 km).
Zamisel je Neurje.si-jeva primerjava modelov (ICON-D2, ICON-EU, ALADIN/SI,
C-LAEF), le da je tu ena točka — naša dolina — in ne karta Slovenije.

Podatki se nalagajo **v brskalniku** (oba vira imata CORS), ker se modelski
teki menjajo čez dan: statičen posnetek ob 7:00 bi do popoldneva kazal stari
tek (GitHubov cron zamuja ure, glej CLAUDE.md). Generator zato piše samo
besedilo, metodologijo in FAQ; dinamično je le tabela »kdo je bil doslej
najbližje« iz data/test-napovedi.json, ki jo osveži test-napovedi-daily.yml.

Notranjih meritev tu ni (stran sploh ne bere postaje).

Usage:
  python3 tools/generate_primerjava_modelov_page.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
TODAY = seo.TODAY
LAT, LON = 46.325779, 14.921137  # IREICA1 (isto kot inject_forecast.py)
TEST_JSON = os.path.join(ROOT, "data", "test-napovedi.json")
URL = "/primerjava-modelov/"

# Modeli, ki jih stran kaže, in njihov razločljiv par v arhivu /test-napovedi/
# (ICON-D2 in AROME tam nista: arhiv za njiju ne obstaja, zato sta brez ocene).
VERIFIED = [("ecmwf_ifs025", "ECMWF IFS"), ("icon_seamless", "ICON (best_match na ICON)")]


def verified_table():
    try:
        d = json.load(open(TEST_JSON, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
    rows = []
    for key, label in VERIFIED:
        r = ((d.get("results") or {}).get(key) or {}).get("1") or {}
        tx, tn = (r.get("tmax") or {}), (r.get("tmin") or {})
        if tx.get("mae") is None or tn.get("mae") is None:
            continue
        rows.append(f'    <tr><th>{label}</th><td>±{seo.num(tx["mae"])} °C</td>'
                    f'<td>±{seo.num(tn["mae"])} °C</td></tr>')
    if not rows:
        return ""
    n = d.get("n_compared_days") or d.get("n_obs_days", 0)
    return f'''  <h2 id="kdo-drzi">Kateri model je doslej držal v dolini?</h2>
  <p class="archive-intro">Povprečna napaka napovedi za jutri (D+1) proti meritvi postaje IREICA1,
  {n} razrešenih dni. ICON-D2 in AROME v tem arhivu še nista, zato za njiju ocene ni, dokler je ne naberemo sproti.
  Celotna lestvica: <a href="/test-napovedi/" style="color:var(--blue)">test napovedi</a>.</p>
  <div class="table-scroll" tabindex="0"><table class="stats">
    <tr><th>Model</th><th>Tmax</th><th>Tmin</th></tr>
{chr(10).join(rows)}
  </table></div>'''


FAQ = [
    ("Zakaj primerjava modelov za eno točko, ne karta?",
     "Karta pokaže, kje bo kaj padlo, ne pove pa, kateremu modelu verjeti v naši ozki dolini. Zato tu "
     "primerjamo modele za eno točko — Rečico ob Savinji — po urah. Kjer se modeli razhajajo, je napoved "
     "negotova; kjer se ujemajo, je zaupanje večje."),
    ("Kaj je AROME in zakaj ne C-LAEF 1 km?",
     "AROME je model avstrijske službe GeoSphere Austria z mrežo 2,5 km, ki pokriva tudi Slovenijo. Njihov "
     "ansambel na isti mreži rišemo kot pas negotovosti (10.–90. percentil). Različica C-LAEF z mrežo 1 km, "
     "ki jo kaže Neurje.si, ni javno dostopna kot točkovna napoved, zato je tu ni."),
    ("Zakaj se modeli razlikujejo?",
     "Imajo različno ločljivost mreže (ECMWF ~25 km, ICON-EU ~6,5 km, ICON-D2 ~2 km, AROME 2,5 km), različne "
     "začetne pogoje in različne fizikalne parametrizacije. Dno ozke doline je pod mrežno celico skoraj "
     "neviden detajl, zato je razlika največja pri nočni temperaturi in pri padavinah."),
    ("Je to uradna napoved?",
     "Ne. Gre za neposredne izhode modelov, ne za napoved forecasterja; za ukrepanje veljata ARSO in "
     "opozorila URSZR."),
    ("Kako pogosto se podatki osvežijo?",
     "Ob vsakem nalaganju strani se prenese zadnji dostopni tek vsakega modela. Modeli se osvežujejo "
     "na nekaj ur (AROME in ICON-D2 pogosteje, ICON-EU in ECMWF redkeje). Ura teka AROME je izpisana pod grafom."),
]

CSS = """<style>
.pm-tabs{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0 .6rem}
.pm-tabs button{font:inherit;font-size:.85rem;padding:.35rem .8rem;border-radius:999px;cursor:pointer;
  background:transparent;color:var(--muted);border:1px solid rgba(255,255,255,.18)}
.pm-tabs button[aria-pressed="true"]{color:var(--text,#e5e7eb);border-color:var(--cyan,#38bdf8);
  background:rgba(56,189,248,.12)}
.pm-tabs .pm-sep{width:1px;background:rgba(255,255,255,.15);margin:0 .3rem}
.pm-svg{width:100%;height:auto;display:block;touch-action:pan-y}
.pm-legend{display:flex;flex-wrap:wrap;gap:.9rem;margin:.4rem 0;font-size:.82rem;color:var(--muted)}
.pm-legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:.35rem;vertical-align:middle}
.pm-legend i.band{height:10px;opacity:.35}
.pm-read{min-height:2.6em;font-size:.85rem;color:var(--muted);margin:.3rem 0}
.pm-read b{color:var(--text,#e5e7eb)}
.pm-note{font-size:.8rem;color:var(--muted);margin:.2rem 0 1rem}
.pm-verdict{margin:1rem 0;padding:.8rem 1rem;border-left:3px solid var(--cyan,#38bdf8);
  background:rgba(56,189,248,.07);border-radius:4px}
</style>"""

JS = r"""<script>
(function(){
  var LAT=%LAT%, LON=%LON%;
  var root=document.getElementById("pm-app"); if(!root) return;
  var MODELS=[
    {id:"icon_d2",label:"ICON-D2",col:"#38bdf8"},
    {id:"icon_eu",label:"ICON-EU",col:"#f59e0b"},
    {id:"ecmwf_ifs025",label:"ECMWF IFS",col:"#a78bfa"},
    {id:"arome",label:"AROME (GeoSphere)",col:"#34d399"}
  ];
  var VARS={
    temp:{label:"Temperatura",unit:"°C",d:1},
    rain:{label:"Padavine (skupaj)",unit:"mm",d:1},
    gust:{label:"Sunki vetra",unit:"km/h",d:0},
    cloud:{label:"Oblačnost",unit:"%",d:0}
  };
  var state={v:"temp",h:48,data:null,info:{}};
  var TZ="Europe/Ljubljana";
  var HOURF=new Intl.DateTimeFormat("en-GB",{timeZone:TZ,hour:"2-digit",hourCycle:"h23"});

  function fmtT(ms,o){ return new Date(ms).toLocaleString("sl-SI",Object.assign({timeZone:TZ},o)); }
  function hhmm(ms){ return fmtT(ms,{hour:"2-digit",minute:"2-digit"}); }
  function dayLbl(ms){ return fmtT(ms,{weekday:"short",day:"numeric",month:"numeric"}); }
  function f(x,d){ return x==null||isNaN(x)?"—":x.toFixed(d).replace(".",","); }
  function pad(n){ return (n<10?"0":"")+n; }
  function get(url){
    return fetch(url,{cache:"no-store"}).then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); });
  }

  // ── viri ────────────────────────────────────────────────────────────────
  // Skupna oblika: data[id] = {t:[ms], temp:[], rain:[], gust:[], cloud:[], lo:[], hi:[]}
  function loadOpenMeteo(){
    var u="https://api.open-meteo.com/v1/forecast?latitude="+LAT+"&longitude="+LON+
      "&hourly=temperature_2m,precipitation,wind_gusts_10m,cloud_cover"+
      "&models=icon_d2,icon_eu,ecmwf_ifs025&forecast_days=3&timezone=UTC";
    return get(u).then(function(j){
      var H=j.hourly, t=H.time.map(function(s){ return Date.parse(s+":00Z"); }), out={};
      ["icon_d2","icon_eu","ecmwf_ifs025"].forEach(function(m){
        out[m]={t:t,temp:H["temperature_2m_"+m],rain:H["precipitation_"+m],
                gust:H["wind_gusts_10m_"+m],cloud:H["cloud_cover_"+m]};
      });
      return out;
    });
  }
  function loadArome(){
    var base="https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/";
    var ll="?lat_lon="+LAT+","+LON+"&output_format=geojson&parameters=";
    function par(j){ return j.features[0].properties.parameters; }
    var res={};
    return get(base+"nwp-v1-1h-2500m"+ll+"t2m,rr_acc,ugust,vgust,tcc").then(function(j){
      var P=par(j), t=j.timestamps.map(Date.parse);
      var acc=P.rr_acc.data, rain=acc.map(function(v,i){
        return i===0||v==null||acc[i-1]==null?null:Math.max(0,v-acc[i-1]); });
      var gust=P.ugust.data.map(function(u,i){
        var v=P.vgust.data[i]; return u==null||v==null?null:Math.sqrt(u*u+v*v)*3.6; });
      res={t:t,temp:P.t2m.data,rain:rain,gust:gust,
           cloud:P.tcc.data.map(function(c){ return c==null?null:c*100; })};
      state.info.aromeRun=Date.parse(j.reference_time);
      // ansambel: pas negotovosti za temperaturo (drugi, zaporedni klic)
      return get(base+"ensemble-v1-1h-2500m"+ll+"t2m_p10,t2m_p90").then(function(e){
        var Q=par(e), m={};
        e.timestamps.forEach(function(s,i){ m[Date.parse(s)]=[Q.t2m_p10.data[i],Q.t2m_p90.data[i]]; });
        res.lo=res.t.map(function(x){ return m[x]?m[x][0]:null; });
        res.hi=res.t.map(function(x){ return m[x]?m[x][1]:null; });
        return res;
      }).catch(function(){ return res; });
    });
  }

  // ── izračuni ────────────────────────────────────────────────────────────
  function windowIdx(s){ // indeksi ur v oknu [naslednja polna ura, +h]
    var start=Math.ceil(Date.now()/3600000)*3600000, end=start+state.h*3600000, ix=[];
    s.t.forEach(function(x,i){ if(x>=start&&x<=end) ix.push(i); });
    return ix;
  }
  function series(m,v){
    var s=state.data[m]; if(!s) return null;
    var ix=windowIdx(s), pts=[], run=0;
    ix.forEach(function(i){
      var y=s[v][i]; if(y==null||isNaN(y)){ return; }
      if(v==="rain"){ run+=y; y=run; }
      pts.push({t:s.t[i],y:y,lo:s.lo?s.lo[i]:null,hi:s.hi?s.hi[i]:null});
    });
    return pts.length>1?pts:null;
  }
  function stats(m){
    var s=state.data[m]; if(!s) return null;
    var ix=windowIdx(s); if(!ix.length) return null;
    function col(k){ return ix.map(function(i){ return s[k][i]; }).filter(function(x){ return x!=null&&!isNaN(x); }); }
    var T=col("temp"),R=col("rain"),G=col("gust"),C=col("cloud");
    return {tmax:T.length?Math.max.apply(null,T):null, tmin:T.length?Math.min.apply(null,T):null,
      rain:R.length?R.reduce(function(a,b){return a+b;},0):null,
      gust:G.length?Math.max.apply(null,G):null,
      cloud:C.length?C.reduce(function(a,b){return a+b;},0)/C.length:null,
      n:ix.length};
  }

  // ── izris ───────────────────────────────────────────────────────────────
  function chart(){
    var v=state.v, all=[], hasBand=false;
    MODELS.forEach(function(m){
      var p=series(m.id,v); if(!p) return;
      all.push({m:m,p:p});
      if(v==="temp"&&m.id==="arome"&&p[0].lo!=null) hasBand=true;
    });
    if(!all.length) return '<p class="pm-note">Ni podatkov za izbrano okno.</p>';
    var W=680,H=290,L=40,R=12,T=12,B=34, pw=W-L-R, ph=H-T-B;
    var t0=Infinity,t1=-Infinity,lo=Infinity,hi=-Infinity;
    all.forEach(function(a){ a.p.forEach(function(q){
      t0=Math.min(t0,q.t); t1=Math.max(t1,q.t);
      lo=Math.min(lo,q.y); hi=Math.max(hi,q.y);
      if(hasBand&&a.m.id==="arome"&&q.lo!=null){ lo=Math.min(lo,q.lo); hi=Math.max(hi,q.hi); }
    }); });
    if(v==="rain"||v==="gust") lo=0;
    if(v==="cloud"){ lo=0; hi=100; }
    if(hi-lo<(v==="rain"?1:2)) hi=lo+(v==="rain"?1:2);
    var pad2=(v==="temp"||v==="gust")?(hi-lo)*0.08:0; hi+=pad2; if(v==="temp") lo-=pad2;
    function X(t){ return L+pw*(t-t0)/(t1-t0); }
    function Y(y){ return T+ph*(1-(y-lo)/(hi-lo)); }
    var svg='<svg class="pm-svg" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+VARS[v].label+
      ' po modelih za naslednjih '+state.h+' ur" id="pm-svg">';
    for(var i=0;i<=4;i++){
      var yv=lo+(hi-lo)*i/4;
      svg+='<line x1="'+L+'" y1="'+Y(yv)+'" x2="'+(W-R)+'" y2="'+Y(yv)+'" stroke="currentColor" stroke-opacity=".1"/>'+
        '<text x="'+(L-6)+'" y="'+(Y(yv)+3)+'" text-anchor="end" font-size="10" fill="currentColor" fill-opacity=".65">'+
        f(yv,VARS[v].d)+'</text>';
    }
    if(v==="temp"&&lo<0&&hi>0) svg+='<line x1="'+L+'" y1="'+Y(0)+'" x2="'+(W-R)+'" y2="'+Y(0)+'" stroke="currentColor" stroke-opacity=".35" stroke-dasharray="3,3"/>';
    // oznake časa: vsakih 6 ur (lokalni čas), ob polnoči dan
    var step=state.h>24?6:3;
    for(var tt=Math.ceil(t0/3600000)*3600000;tt<=t1;tt+=3600000){
      var h=+HOURF.format(new Date(tt));
      if(h%step) continue;
      svg+='<line x1="'+X(tt)+'" y1="'+T+'" x2="'+X(tt)+'" y2="'+(T+ph)+'" stroke="currentColor" stroke-opacity="'+(h===0?.22:.06)+'"/>'+
        '<text x="'+X(tt)+'" y="'+(H-18)+'" text-anchor="middle" font-size="10" fill="currentColor" fill-opacity=".65">'+pad(h)+'</text>';
      if(h===0) svg+='<text x="'+X(tt)+'" y="'+(H-5)+'" text-anchor="middle" font-size="10" fill="currentColor" fill-opacity=".8">'+dayLbl(tt)+'</text>';
    }
    all.forEach(function(a){
      if(hasBand&&a.m.id==="arome"){
        var up=[],dn=[];
        a.p.forEach(function(q){ if(q.lo!=null){ up.push(X(q.t)+","+Y(q.hi)); dn.unshift(X(q.t)+","+Y(q.lo)); } });
        if(up.length>1) svg+='<polygon points="'+up.concat(dn).join(" ")+'" fill="'+a.m.col+'" fill-opacity=".16"/>';
      }
      var d=a.p.map(function(q){ return X(q.t)+","+Y(q.y); }).join(" ");
      svg+='<polyline points="'+d+'" fill="none" stroke="'+a.m.col+'" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>';
    });
    svg+='<line id="pm-cur" x1="0" y1="'+T+'" x2="0" y2="'+(T+ph)+'" stroke="currentColor" stroke-opacity=".5" visibility="hidden"/></svg>';
    var leg='<div class="pm-legend">'+all.map(function(a){
      return '<span><i style="background:'+a.m.col+'"></i>'+a.m.label+'</span>'; }).join("")+
      (hasBand?'<span><i class="band" style="background:#34d399"></i>pas AROME ansambla (10.–90. percentil)</span>':'')+'</div>';
    root._geo={all:all,X:X,t0:t0,t1:t1,L:L,pw:pw,W:W};
    return svg+leg+'<div class="pm-read" id="pm-read">Pokaži s kazalcem na grafu vrednosti po modelih.</div>';
  }
  function attachHover(){
    var svg=document.getElementById("pm-svg"); if(!svg||!root._geo) return;
    var g=root._geo, cur=document.getElementById("pm-cur"), rd=document.getElementById("pm-read");
    function move(e){
      var r=svg.getBoundingClientRect(), px=(e.clientX-r.left)/r.width*g.W;
      var t=g.t0+(px-g.L)/g.pw*(g.t1-g.t0);
      t=Math.round(t/3600000)*3600000; if(t<g.t0||t>g.t1) return;
      cur.setAttribute("x1",g.X(t)); cur.setAttribute("x2",g.X(t)); cur.setAttribute("visibility","visible");
      var parts=g.all.map(function(a){
        var q=a.p.filter(function(z){ return z.t===t; })[0];
        return '<span style="color:'+a.m.col+'">●</span> '+a.m.label+' <b>'+(q?f(q.y,VARS[state.v].d)+" "+VARS[state.v].unit:"—")+'</b>';
      });
      rd.innerHTML=dayLbl(t)+' '+hhmm(t)+' · '+parts.join(' · ');
    }
    svg.addEventListener("pointermove",move); svg.addEventListener("pointerdown",move);
  }

  function table(){
    var rows="", S={}, ids=[];
    MODELS.forEach(function(m){ var s=stats(m.id); if(s){ S[m.id]=s; ids.push(m.id); } });
    if(!ids.length) return "";
    function cell(x,d,u){ return '<td>'+(x==null?"—":f(x,d)+" "+u)+'</td>'; }
    MODELS.forEach(function(m){
      var s=S[m.id]; if(!s) return;
      rows+='<tr><th><span style="color:'+m.col+'">●</span> '+m.label+'</th>'+
        cell(s.tmin,1,"°C")+cell(s.tmax,1,"°C")+cell(s.rain,1,"mm")+cell(s.gust,0,"km/h")+cell(s.cloud,0,"%")+'</tr>';
    });
    function spread(k){
      var a=ids.map(function(i){ return S[i][k]; }).filter(function(x){ return x!=null; });
      return a.length>1?Math.max.apply(null,a)-Math.min.apply(null,a):null;
    }
    var st=spread("tmax"), sn=spread("tmin"), sr=spread("rain");
    rows+='<tr><th>Razpon med modeli</th>'+cell(sn,1,"°C")+cell(st,1,"°C")+cell(sr,1,"mm")+cell(spread("gust"),0,"km/h")+cell(spread("cloud"),0,"%")+'</tr>';
    var verdict="";
    if(st!=null&&sr!=null){
      var tw=st<=1?"se ujemajo":(st<=2.5?"se zmerno razhajajo":"se močno razhajajo");
      var rr=Math.max.apply(null,ids.map(function(i){ return S[i].rain||0; }));
      var rw=rr<0.5?"Noben model ne napoveduje pomembnih padavin."
        :(sr<=Math.max(1,rr*0.35)?"Modeli se pri padavinah v glavnem strinjajo ("+f(rr,1)+" mm najvišja vsota)."
        :"Pri padavinah se modeli razhajajo ("+f(Math.min.apply(null,ids.map(function(i){return S[i].rain||0;})),1)+"–"+f(rr,1)+" mm): količina in čas sta negotova.");
      verdict='<div class="pm-verdict">Pri najvišji temperaturi modeli <b>'+tw+'</b> (razpon '+f(st,1)+' °C). '+rw+'</div>';
    }
    return verdict+'<div class="table-scroll" tabindex="0"><table class="stats"><tr><th>Naslednjih '+state.h+' ur</th><th>Tmin</th><th>Tmax</th><th>Padavine</th><th>Najvišji sunek</th><th>Oblačnost (pov.)</th></tr>'+rows+'</table></div>';
  }

  function render(){
    var tabs='<div class="pm-tabs" role="group" aria-label="Spremenljivka">'+
      Object.keys(VARS).map(function(k){ return '<button type="button" data-v="'+k+'" aria-pressed="'+(state.v===k)+'">'+VARS[k].label+'</button>'; }).join("")+
      '<span class="pm-sep"></span>'+
      [24,48].map(function(h){ return '<button type="button" data-h="'+h+'" aria-pressed="'+(state.h===h)+'">'+h+' ur</button>'; }).join("")+'</div>';
    var inf=[], fails=state.info.fail||[];
    if(state.info.aromeRun) inf.push("Tek AROME: "+dayLbl(state.info.aromeRun)+" "+hhmm(state.info.aromeRun)+".");
    inf.push("Ure so po lokalnem času (Rečica).");
    if(fails.length) inf.push("Ni dosegljivo: "+fails.join(", ")+".");
    root.innerHTML=tabs+chart()+'<p class="pm-note">'+inf.join(" ")+'</p>'+table();
    attachHover();
    Array.prototype.forEach.call(root.querySelectorAll("button"),function(b){
      b.addEventListener("click",function(){
        if(b.dataset.v) state.v=b.dataset.v; if(b.dataset.h) state.h=+b.dataset.h; render();
      });
    });
  }

  root.textContent="Nalagam napovedi modelov …";
  state.data={}; state.info.fail=[];
  var jobs=[
    loadOpenMeteo().then(function(o){ Object.keys(o).forEach(function(k){ state.data[k]=o[k]; }); })
      .catch(function(){ state.info.fail.push("ICON-D2, ICON-EU, ECMWF (Open-Meteo)"); }),
    loadArome().then(function(o){ state.data.arome=o; })
      .catch(function(){ state.info.fail.push("AROME (GeoSphere)"); })
  ];
  Promise.all(jobs).then(function(){
    if(!Object.keys(state.data).length){ root.textContent="Napovedi modelov trenutno niso dosegljive. Poskusi znova čez nekaj minut."; return; }
    render();
  });
})();
</script>""".replace("%LAT%", str(LAT)).replace("%LON%", str(LON))


def build_body():
    faq = ("  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in FAQ) + "\n  </div>")
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Primerjava modelov", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Primerjava vremenskih modelov za Rečico ob Savinji</h1>
  <p class="post-meta">ICON-D2 · ICON-EU · ECMWF IFS · AROME (GeoSphere) — zadnji tek vsakega modela, v živo</p>
  <p class="archive-intro">Isti kraj, isti čas, štirje modeli. Kjer se črte ujemajo, je napoved zanesljiva;
  kjer se razhajajo, je negotova — in prav takrat se splača pogledati, kateri model je doslej v naši dolini
  držal bolje (spodaj). Gre za neposredne izhode modelov, ne za uradno napoved.</p>
  <div id="pm-app" aria-live="polite">Nalagam napovedi modelov …</div>
{verified_table()}
  <h2>Modeli v primerjavi</h2>
  <div class="table-scroll" tabindex="0"><table class="stats">
    <tr><th>Model</th><th>Izdajatelj</th><th>Mreža</th><th>Doseg</th></tr>
    <tr><th>ICON-D2</th><th>DWD (Nemčija)</th><td>~2 km</td><td>48 ur, Srednja Evropa</td></tr>
    <tr><th>ICON-EU</th><th>DWD (Nemčija)</th><td>~6,5 km</td><td>120 ur, Evropa</td></tr>
    <tr><th>ECMWF IFS</th><th>ECMWF</th><td>~25 km</td><td>10 dni, svet</td></tr>
    <tr><th>AROME + ansambel</th><th>GeoSphere Austria</th><td>2,5 km</td><td>60 ur, Alpe in okolica</td></tr>
  </table></div>
  <p class="archive-intro">Vrednosti so za najbližjo mrežno celico točke postaje IREICA1 (Open-Meteo) oziroma
  za celico AROME, ki ji leži najbliže. Nobena celica ne razloči dna ozke doline, zato modelska temperatura ponoči
  praviloma ni enaka izmerjeni — to meri <a href="/test-napovedi/" style="color:var(--blue)">test napovedi</a>.
  Viri: Open-Meteo (open-meteo.com), GeoSphere Austria (data.hub.geosphere.at, licenca CC BY 4.0).</p>
{faq}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''


def main():
    title = "Primerjava vremenskih modelov za Rečico"
    desc = ("Napoved ICON-D2, ICON-EU, ECMWF in AROME (GeoSphere) za Rečico ob Savinji drugo nad drugo: "
            "temperatura, padavine, sunki in oblačnost po urah, razpon med modeli in ocena, kateri model "
            "je v dolini doslej držal bolje.")
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published=TODAY.isoformat()),
        seo.crumbs_schema([("Meteorec", "/"), ("Primerjava modelov", None)]),
        seo.faq_schema(FAQ),
    ])
    html_out = seo.page_shell(title, desc, URL, schema + "\n" + CSS, build_body() + "\n" + JS)
    seo.write_page("primerjava-modelov/index.html", html_out, force=True)
    print("  → primerjava-modelov/index.html")


if __name__ == "__main__":
    main()
