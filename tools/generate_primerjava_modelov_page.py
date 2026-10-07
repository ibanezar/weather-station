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
PROXY = "https://weatherireica1.filip-eremita.workers.dev"  # isti worker kot povsod drugje


def slo_poly_js():
    """Obris Slovenije vzamemo iz app.js (en vir; JS in Python ne moreta deliti kode, a
    obris je podatek). Če ga ni več, generator pade — raje to kot karta brez obrisa."""
    import re
    m = re.search(r"const SLO_POLY=(\[\[.*?\]\]);", open(os.path.join(ROOT, "app.js"), encoding="utf-8").read(), re.S)
    if not m:
        sys.exit("SLO_POLY ni v app.js — karta modelov potrebuje obris Slovenije")
    return m.group(1)

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
.pm-maps{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}
@media (max-width:640px){.pm-maps{grid-template-columns:1fr}}
.pm-map{position:relative}
.pm-map canvas{width:100%;height:auto;display:block;border-radius:6px;background:rgba(255,255,255,.04);touch-action:pan-y}
.pm-map-t{font-family:'JetBrains Mono',monospace;font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;margin:0 0 .25rem}
.pm-ctrl{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem;margin:.6rem 0}
.pm-ctrl input[type=range]{flex:1;min-width:140px}
.pm-ctrl button{font:inherit;font-size:.85rem;padding:.3rem .8rem;border-radius:999px;cursor:pointer;
  background:transparent;color:var(--muted);border:1px solid rgba(255,255,255,.18)}
.pm-scale{display:flex;height:10px;border-radius:3px;overflow:hidden;margin:.2rem 0}
.pm-scale i{flex:1}
.pm-scale-l{display:flex;justify-content:space-between;font-size:.72rem;color:var(--muted)}
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


MAP_JS = r"""<script>
(function(){
  var root=document.getElementById("pm-maps"); if(!root) return;
  var SLO=%SLO%;
  var PROXY="%PROXY%", TZ="Europe/Ljubljana";
  var ORDER=["icon_d2","icon_eu","ecmwf_ifs025","arome"];
  var CITIES=[["Ljubljana",14.506,46.056],["Maribor",15.646,46.554],["Celje",15.26,46.231],["Koper",13.73,45.548],
              ["Murska Sobota",16.166,46.658],["Rečica",14.921,46.326]];
  // Lestvice: ColorBrewer YlGnBu (padavine), RdYlBu obrnjen (temperatura), YlOrRd (sunki).
  var PAL={
    p:{lbl:"Skupne padavine od zdaj",unit:"mm",d:1,bins:[0.2,1,2,5,10,20,40,80,150],
       cols:["#ffffcc","#c7e9b4","#7fcdbb","#41b6c4","#1d91c0","#225ea8","#253494","#081d58","#4a1486"]},
    g:{lbl:"Najvišji sunek",unit:"km/h",d:0,bins:[20,30,40,50,60,80,100,120],
       cols:["#ffffb2","#fed976","#feb24c","#fd8d3c","#fc4e2a","#e31a1c","#bd0026","#800026","#4d004b"]},
    t:{lbl:"Temperatura",unit:"°C",d:1,stops:["#4575b4","#91bfdb","#e0f3f8","#ffffbf","#fee090","#fc8d59","#d73027"]}
  };
  var S={v:"p",k:0,data:null,play:null,cv:{}};
  function f(x,d){ return x==null||isNaN(x)?"—":x.toFixed(d).replace(".",","); }
  function hex(c){ return [parseInt(c.substr(1,2),16),parseInt(c.substr(3,2),16),parseInt(c.substr(5,2),16)]; }
  function lerp(a,b,u){ return [a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u,a[2]+(b[2]-a[2])*u]; }
  function colorFor(v,range){
    var P=PAL[S.v];
    if(S.v==="t"){
      var u=Math.max(0,Math.min(1,(v-range[0])/(range[1]-range[0])))*(P.stops.length-1), i=Math.min(P.stops.length-2,Math.floor(u));
      return lerp(hex(P.stops[i]),hex(P.stops[i+1]),u-i);
    }
    var n=0; while(n<P.bins.length&&v>=P.bins[n]) n++;
    if(S.v==="p") return n===0?null:hex(P.cols[n-1]);   // pod 0,2 mm = suho, brez barve
    return hex(P.cols[n]);
  }
  function tempRange(){
    var lo=1e9,hi=-1e9;
    ORDER.forEach(function(id){ var m=S.data.models[id]; if(!m) return; m.t[S.k].forEach(function(x){ if(x!=null){ lo=Math.min(lo,x); hi=Math.max(hi,x);} }); });
    lo=Math.floor(lo/2)*2; hi=Math.ceil(hi/2)*2; if(hi-lo<6) hi=lo+6; return [lo,hi];
  }
  function inSlo(lon,lat){
    var ins=false; for(var i=0,j=SLO.length-1;i<SLO.length;j=i++){
      var xi=SLO[i][0],yi=SLO[i][1],xj=SLO[j][0],yj=SLO[j][1];
      if(((yi>lat)!==(yj>lat))&&(lon<(xj-xi)*(lat-yi)/(yj-yi)+xi)) ins=!ins; }
    return ins;
  }
  function geo(){
    var D=S.data, W=D.nx, H=D.ny, lon1=D.lon0+(W-1)*D.d, lat1=D.lat0+(H-1)*D.d;
    var cs=Math.cos(46.2*Math.PI/180), wpx=360, hpx=Math.round(wpx*(lat1-D.lat0)/((lon1-D.lon0)*cs));
    return {W:W,H:H,lon0:D.lon0,lat0:D.lat0,lon1:lon1,lat1:lat1,w:wpx,h:hpx};
  }
  function sample(arr,G,lon,lat){      // bilinearno; null, če manjka kateri koli kot
    var D=S.data, fx=(lon-D.lon0)/D.d, fy=(lat-D.lat0)/D.d;
    var x0=Math.max(0,Math.min(G.W-2,Math.floor(fx))), y0=Math.max(0,Math.min(G.H-2,Math.floor(fy)));
    var u=fx-x0, w=fy-y0, a=arr[y0*G.W+x0], b=arr[y0*G.W+x0+1], c=arr[(y0+1)*G.W+x0], d=arr[(y0+1)*G.W+x0+1];
    if(a==null||b==null||c==null||d==null) return null;
    return (a*(1-u)+b*u)*(1-w)+(c*(1-u)+d*u)*w;
  }
  function draw(id){
    var m=S.data.models[id], cv=S.cv[id]; if(!cv) return;
    var G=geo(), dpr=Math.min(2,window.devicePixelRatio||1);
    cv.width=G.w*dpr; cv.height=G.h*dpr;
    var ctx=cv.getContext("2d"); ctx.setTransform(dpr,0,0,dpr,0,0);
    var arr=m[S.v][S.k], rng=S.v==="t"?tempRange():null;
    var img=ctx.createImageData(G.w*dpr,G.h*dpr);
    for(var y=0;y<G.h*dpr;y++) for(var x=0;x<G.w*dpr;x++){
      var lon=G.lon0+(x/(G.w*dpr-1))*(G.lon1-G.lon0), lat=G.lat1-(y/(G.h*dpr-1))*(G.lat1-G.lat0);
      var v=sample(arr,G,lon,lat), i=(y*G.w*dpr+x)*4;
      if(v==null) continue;
      var c=colorFor(v,rng); if(!c) continue;
      var out=!inSlo(lon,lat);
      img.data[i]=c[0]; img.data[i+1]=c[1]; img.data[i+2]=c[2]; img.data[i+3]=out?110:235;
    }
    ctx.putImageData(img,0,0);
    function px(lon,lat){ return [(lon-G.lon0)/(G.lon1-G.lon0)*G.w,(G.lat1-lat)/(G.lat1-G.lat0)*G.h]; }
    ctx.beginPath(); SLO.forEach(function(p,i){ var q=px(p[0],p[1]); i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]); });
    ctx.closePath(); ctx.strokeStyle="rgba(15,23,42,.7)"; ctx.lineWidth=2.6; ctx.stroke();
    ctx.strokeStyle="rgba(255,255,255,.9)"; ctx.lineWidth=1; ctx.stroke();
    ctx.font="10px sans-serif"; ctx.textBaseline="middle";
    CITIES.forEach(function(c){ var q=px(c[1],c[2]); ctx.beginPath(); ctx.arc(q[0],q[1],c[0]==="Rečica"?3.4:2,0,6.3);
      ctx.fillStyle=c[0]==="Rečica"?"#fff":"rgba(255,255,255,.8)"; ctx.fill(); ctx.strokeStyle="#0f172a"; ctx.lineWidth=1; ctx.stroke();
      ctx.fillStyle="#fff"; ctx.shadowColor="#000"; ctx.shadowBlur=3; ctx.fillText(c[0],q[0]+5,q[1]); ctx.shadowBlur=0; });
    if(cv._cur){ var q=px(cv._cur[0],cv._cur[1]); ctx.beginPath(); ctx.arc(q[0],q[1],5,0,6.3); ctx.strokeStyle="#fff"; ctx.lineWidth=1.5; ctx.stroke(); }
    var nn=arr.filter(function(x){ return x!=null; }).length;
    cv.setAttribute("aria-label",m.label+": "+PAL[S.v].lbl+", "+(nn?"podatki na voljo":"ni podatkov za to uro"));
    cv._nodata=!nn;
    if(!nn){ ctx.fillStyle="rgba(15,23,42,.7)"; ctx.fillRect(0,0,G.w,G.h); ctx.fillStyle="#fff"; ctx.font="12px sans-serif"; ctx.textAlign="center";
      ctx.fillText("ni podatkov za to uro (model sega krajše)",G.w/2,G.h/2); ctx.textAlign="start"; }
  }
  function scaleHtml(){
    var P=PAL[S.v], cols, labs;
    if(S.v==="t"){ var r=tempRange(); cols=P.stops; labs=[r[0],r[1]].map(function(x){ return x+" °C"; }); }
    else { cols=P.cols; labs=[0,P.bins[P.bins.length-1]+"+"]; }
    return '<div class="pm-scale">'+cols.map(function(c){ return '<i style="background:'+c+'"></i>'; }).join("")+'</div>'+
      '<div class="pm-scale-l"><span>'+(S.v==="t"?labs[0]:(S.v==="p"?"0,2":"0"))+'</span><span>'+PAL[S.v].lbl+' ('+P.unit+')</span><span>'+labs[1]+'</span></div>';
  }
  function when(k){ var t=S.data.t0+(k+1)*S.data.stepH*3600000;
    return new Date(t).toLocaleString("sl-SI",{timeZone:TZ,weekday:"short",hour:"2-digit",minute:"2-digit"}); }
  function readout(lon,lat){
    var G=geo(), parts=ORDER.map(function(id){ var m=S.data.models[id]; if(!m) return null;
      var v=sample(m[S.v][S.k],G,lon,lat); return m.label+' <b>'+(v==null?"—":f(v,PAL[S.v].d)+" "+PAL[S.v].unit)+'</b>'; }).filter(Boolean);
    document.getElementById("pm-map-read").innerHTML=lat.toFixed(2).replace(".",",")+" °N, "+lon.toFixed(2).replace(".",",")+" °E · "+parts.join(" · ");
  }
  function drawAll(){
    ORDER.forEach(draw);
    document.getElementById("pm-map-when").textContent=(S.v==="p"?"od zdaj do ":"")+when(S.k);
    document.getElementById("pm-map-scale").innerHTML=scaleHtml();
  }
  function build(){
    var D=S.data;
    var run=D.models.arome&&D.models.arome.run?" Tek AROME: "+new Date(D.models.arome.run).toLocaleString("sl-SI",{timeZone:TZ,hour:"2-digit",minute:"2-digit"})+".":"";
    var fail=(D.failed&&D.failed.length)?" Ni dosegljivo: "+D.failed.join(", ")+".":"";
    root.innerHTML=
      '<div class="pm-tabs" role="group" aria-label="Spremenljivka na karti">'+
        ["p","t","g"].map(function(k){ return '<button type="button" data-mv="'+k+'" aria-pressed="'+(S.v===k)+'">'+PAL[k].lbl+'</button>'; }).join("")+'</div>'+
      '<div class="pm-ctrl"><button type="button" id="pm-play" aria-label="Predvajaj">▶</button>'+
        '<input type="range" id="pm-slider" min="0" max="'+(D.steps-1)+'" value="'+S.k+'" aria-label="Ura napovedi">'+
        '<strong id="pm-map-when"></strong></div>'+
      '<div class="pm-maps">'+ORDER.filter(function(id){ return D.models[id]; }).map(function(id){
        return '<div class="pm-map"><p class="pm-map-t">'+D.models[id].label+'</p><canvas id="pm-cv-'+id+'" role="img"></canvas></div>'; }).join("")+'</div>'+
      '<div id="pm-map-scale"></div>'+
      '<div class="pm-read" id="pm-map-read">Dotakni se karte: vrednosti vseh modelov na isti točki.</div>'+
      '<p class="pm-note">Mreža 0,1° (okoli 8 × 11 km), korak 3 ure. Prikaz je pregled vzorca, ne zamenjava za modele v polni ločljivosti (ICON-D2 2 km, AROME 2,5 km).'+run+fail+' Nastalo '+
      new Date(D.generated).toLocaleString("sl-SI",{timeZone:TZ,hour:"2-digit",minute:"2-digit"})+'.</p>';
    ORDER.forEach(function(id){
      var cv=document.getElementById("pm-cv-"+id); if(!cv) return; S.cv[id]=cv;
      function mv(e){
        var r=cv.getBoundingClientRect(), G=geo(),
            lon=G.lon0+(e.clientX-r.left)/r.width*(G.lon1-G.lon0), lat=G.lat1-(e.clientY-r.top)/r.height*(G.lat1-G.lat0);
        ORDER.forEach(function(o){ if(S.cv[o]) S.cv[o]._cur=[lon,lat]; }); drawAll(); readout(lon,lat);
      }
      cv.addEventListener("pointermove",mv); cv.addEventListener("pointerdown",mv);
    });
    Array.prototype.forEach.call(root.querySelectorAll("button[data-mv]"),function(b){
      b.addEventListener("click",function(){ S.v=b.dataset.mv; build(); }); });
    var sl=document.getElementById("pm-slider");
    sl.addEventListener("input",function(){ S.k=+sl.value; drawAll(); });
    document.getElementById("pm-play").addEventListener("click",function(){
      if(S.play){ clearInterval(S.play); S.play=null; this.textContent="▶"; return; }
      var btn=this; btn.textContent="❚❚";
      S.play=setInterval(function(){ S.k=(S.k+1)%S.data.steps; sl.value=S.k; drawAll(); },700);
    });
    drawAll();
  }
  root.textContent="Nalagam karte modelov …";
  fetch(PROXY+"/modeli-karta.json").then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); })
    .then(function(d){ if(!d.models||!Object.keys(d.models).length) throw new Error("prazno"); S.data=d; build(); })
    .catch(function(){ root.textContent="Karte modelov trenutno niso dosegljive. Primerjava za Rečico zgoraj deluje neodvisno."; });
})();
</script>""".replace("%SLO%", slo_poly_js()).replace("%PROXY%", PROXY)


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
  <h2 id="karte">Karte modelov za Slovenijo</h2>
  <p class="archive-intro">Isti trenutek na štirih kartah hkrati: povleci drsnik, preklopi spremenljivko ali se dotakni karte
  in preberi vrednost vseh modelov na isti točki. Padavine so skupne od zdaj do izbrane ure.</p>
  <div id="pm-maps" aria-live="polite">Nalagam karte modelov …</div>
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
    html_out = seo.page_shell(title, desc, URL, schema + "\n" + CSS, build_body() + "\n" + JS + "\n" + MAP_JS)
    seo.write_page("primerjava-modelov/index.html", html_out, force=True)
    print("  → primerjava-modelov/index.html")


if __name__ == "__main__":
    main()
