#!/usr/bin/env python3
"""
tools/generate_snezna_karta_page.py — /zima/snezna-karta/

Snežna karta Slovenije: sneženje po urah, meja sneženja in skupni novi sneg v izbranem
obdobju na eni karti. Zamisel je Neurje.si-jev »Snow Map«; izvedba je naša: mreža 0,1°
ICON-D2 (Open-Meteo), ki jo sestavi worker (`/sneg-karta.json`, `_snegKarta()`).

Vse številke se nalagajo **v brskalniku** (modelski teki se menjajo čez dan, GitHubov cron
zamuja ure — glej CLAUDE.md); generator piše samo besedilo, metodologijo in FAQ, zato ga ni
treba poganjati po urniku. Stran ne bere postaje, notranjih meritev torej ni.

Usage:
  python3 tools/generate_snezna_karta_page.py
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
TODAY = seo.TODAY
URL = "/zima/snezna-karta/"
PROXY = "https://weatherireica1.filip-eremita.workers.dev"  # isti worker kot povsod drugje


def slo_poly_js():
    """Obris Slovenije iz app.js (en vir, kot pri /primerjava-modelov/)."""
    m = re.search(r"const SLO_POLY=(\[\[.*?\]\]);", open(os.path.join(ROOT, "app.js"), encoding="utf-8").read(), re.S)
    if not m:
        sys.exit("SLO_POLY ni v app.js — snežna karta potrebuje obris Slovenije")
    return m.group(1)


FAQ = [
    ("Od kod so podatki na snežni karti?",
     "Iz modela ICON-D2 (DWD, ločljivost ~2 km), ki ga prek Open-Meteo prebere naš strežnik na mreži 0,1° "
     "(okoli 8 × 11 km) nad Slovenijo. Karta kaže zadnji razpoložljivi tek, osvežuje se vsake pol ure."),
    ("Kako je izračunana meja sneženja?",
     "Kot ničta izoterma modela minus 250 m — isti približek kot na strani Meja sneženja. Padavina se ob padanju "
     "skozi nenasičen zrak ohladi, zato sneži nekoliko pod višino, kjer je 0 °C. To je groba ocena, ne meritev."),
    ("Koliko snega pove karta?",
     "Količina je modelsko sneženje (cm svežega snega v uri) in ni višina snežne odeje: sneg se tudi sesede in tali, "
     "ob meji sneženja pa je mokrejši in ga je manj. Za skupno količino se urne vrednosti seštejejo od zdaj do izbrane ure."),
    ("Zakaj se karta razlikuje od ARSO?",
     "ARSO uporablja drug model in ročno presoja napovedovalcev. Mreža 0,1° ne razloči ozkih dolin in posameznih "
     "pobočij, zato so lokalna odstopanja pričakovana. Za ukrepanje in opozorila veljata ARSO in uradni viri."),
    ("Ali je to uradna napoved sneženja?",
     "Ne. Gre za neposredni izhod modela, pregled vzorca nad Slovenijo. Pred potjo v gore ali čez prelaze preveri "
     "ARSO, promet.si in stanje na cesti."),
]

CSS_SRC = """
.sk-tabs{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0}
.sk-tabs button,.sk-ctrl button{font:inherit;font-size:.9rem;padding:.45rem .9rem;border-radius:999px;cursor:pointer;
  background:transparent;color:var(--muted);border:1px solid rgba(255,255,255,.18);min-height:40px}
.sk-tabs button[aria-pressed="true"]{color:var(--text,#e5e7eb);border-color:var(--cyan,#38bdf8);background:rgba(56,189,248,.12)}
.sk-ctrl{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem;margin:.6rem 0}
.sk-ctrl input[type=range]{flex:1;min-width:160px;min-height:32px}
.sk-ctrl button[aria-pressed="true"]{color:var(--text,#e5e7eb);border-color:var(--cyan,#38bdf8);background:rgba(56,189,248,.12)}
.sk-empty{max-width:760px;margin:.5rem 0;padding:.6rem .9rem;border-left:3px solid var(--cyan,#38bdf8);background:rgba(56,189,248,.07);border-radius:4px;font-size:.9rem}
.sk-range{font-size:.85rem;color:var(--muted);min-height:1.3em}
.sk-ctrl strong{min-width:9ch}
.sk-map canvas{width:100%;max-width:760px;height:auto;display:block;border-radius:8px;background:rgba(255,255,255,.04);touch-action:pan-y}
.sk-scale{display:flex;height:10px;border-radius:3px;overflow:hidden;margin:.5rem 0 .2rem;max-width:760px}
.sk-scale i{flex:1}
.sk-scale-l{display:flex;justify-content:space-between;max-width:760px;font-size:.75rem;color:var(--muted)}
.sk-read{min-height:3em;font-size:.9rem;color:var(--muted);margin:.5rem 0}
.sk-read b{color:var(--text,#e5e7eb)}
.sk-note{font-size:.8rem;color:var(--muted);margin:.2rem 0 1rem}
"""

JS_SRC = r"""
(function(){
  var root=document.getElementById("sk-app"); if(!root) return;
  var SLO=%SLO%, PROXY="%PROXY%", TZ="Europe/Ljubljana";
  var CITIES=[["Ljubljana",14.506,46.056],["Maribor",15.646,46.554],["Celje",15.26,46.231],["Koper",13.73,45.548],
              ["Kranj",14.356,46.239],["Rečica",14.921,46.326]];
  var PAL={
    h:{lbl:"Sneženje po urah",unit:"cm/h",d:1,bins:[0.1,0.5,1,2,3,5,8],
       cols:["#deebf7","#bdd7e7","#6baed6","#3182bd","#08519c","#6a51a3","#54278f"]},
    l:{lbl:"Meja sneženja",unit:"m",d:0,bins:[400,600,800,1000,1200,1500,1800,2200],
       cols:["#08306b","#08519c","#2171b5","#4292c6","#6baed6","#9ecae1","#c6dbef","#deebf7","#f7fbff"]},
    s:{lbl:"Skupaj novega snega",unit:"cm",d:0,bins:[0.5,2,5,10,20,30,50,80],
       cols:["#deebf7","#bdd7e7","#9ecae1","#6baed6","#3182bd","#08519c","#6a51a3","#54278f","#3f007d"]}
  };
  var S={v:root.dataset.view||"h",k:(+root.dataset.hours||1)-1,data:null,play:null,cv:null,cur:null};
  var COMPACT=root.dataset.compact==="1";
  function f(x,d){ return x==null||isNaN(x)?"—":x.toFixed(d).replace(".",","); }
  function hex(c){ return [parseInt(c.substr(1,2),16),parseInt(c.substr(3,2),16),parseInt(c.substr(5,2),16)]; }
  function inSlo(lon,lat){
    var ins=false; for(var i=0,j=SLO.length-1;i<SLO.length;j=i++){
      var xi=SLO[i][0],yi=SLO[i][1],xj=SLO[j][0],yj=SLO[j][1];
      if(((yi>lat)!==(yj>lat))&&(lon<(xj-xi)*(lat-yi)/(yj-yi)+xi)) ins=!ins; }
    return ins;
  }
  function geo(){
    var D=S.data, W=D.nx, H=D.ny, lon1=D.lon0+(W-1)*D.d, lat1=D.lat0+(H-1)*D.d;
    var cs=Math.cos(46.2*Math.PI/180), wpx=720, hpx=Math.round(wpx*(lat1-D.lat0)/((lon1-D.lon0)*cs));
    return {W:W,H:H,lon0:D.lon0,lat0:D.lat0,lon1:lon1,lat1:lat1,w:wpx,h:hpx};
  }
  // polje za izbrani prikaz in uro: hourly = sneženje v uri, l = meja, s = vsota ur 1..k+1
  function field(v,k){
    var D=S.data, n=D.nx*D.ny, out=new Array(n), i, h;
    if(v==="h"){ for(i=0;i<n;i++) out[i]=D.sn[k][i]==null?null:D.sn[k][i]*D.units.sn; }
    else if(v==="l"){ for(i=0;i<n;i++) out[i]=D.ln[k][i]==null?null:Math.max(0,D.ln[k][i]*D.units.ln); }
    else { for(i=0;i<n;i++){ var sum=0, bad=false; for(h=0;h<=k;h++){ var x=D.sn[h][i]; if(x==null){ bad=true; break; } sum+=x; }
      out[i]=bad?null:sum*D.units.sn; } }
    return out;
  }
  function colorFor(v,val){
    var P=PAL[v], n=0; while(n<P.bins.length&&val>=P.bins[n]) n++;
    if(v==="l") return hex(P.cols[n]);
    return n===0?null:hex(P.cols[n-1]);       // brez sneženja = brez barve
  }
  function sample(arr,G,lon,lat){
    var D=S.data, fx=(lon-D.lon0)/D.d, fy=(lat-D.lat0)/D.d;
    var x0=Math.max(0,Math.min(G.W-2,Math.floor(fx))), y0=Math.max(0,Math.min(G.H-2,Math.floor(fy)));
    var u=fx-x0, w=fy-y0, a=arr[y0*G.W+x0], b=arr[y0*G.W+x0+1], c=arr[(y0+1)*G.W+x0], d=arr[(y0+1)*G.W+x0+1];
    if(a==null||b==null||c==null||d==null) return null;
    return (a*(1-u)+b*u)*(1-w)+(c*(1-u)+d*u)*w;
  }
  function when(k){ var t=S.data.t0+(k+1)*3600000;
    return new Date(t).toLocaleString("sl-SI",{timeZone:TZ,weekday:"short",day:"numeric",month:"numeric",hour:"2-digit",minute:"2-digit"}); }
  function whenAt(k,off){ var t=S.data.t0+(k+1+(off||0))*3600000;
    return new Date(t).toLocaleString("sl-SI",{timeZone:TZ,weekday:"short",day:"numeric",month:"numeric",hour:"2-digit",minute:"2-digit"}); }
  function dayKey(ms){ return new Date(ms).toLocaleDateString("sl-SI",{timeZone:TZ,year:"numeric",month:"numeric",day:"numeric"}); }
  function days(){ // prva ura vsakega koledarskega dne (po naši uri) v podatkih
    var D=S.data, out=[], seen={}, k;
    for(k=0;k<D.hours;k++){ var ms=D.t0+(k+1)*3600000, key=dayKey(ms);
      if(!seen[key]){ seen[key]=1; out.push({k:k,key:key,ms:ms}); } }
    return out;
  }
  function markDay(){
    var cur=dayKey(S.data.t0+(S.k+1)*3600000);
    Array.prototype.forEach.call(document.querySelectorAll("#sk-days button"),function(b){ b.setAttribute("aria-pressed",String(b.dataset.key===cur)); });
  }
  function firstSnow(){ // prva ura z vsaj enim 0,1 cm sneženja kjerkoli na mreži
    var D=S.data, k, i; for(k=0;k<D.hours;k++) for(i=0;i<D.sn[k].length;i++) if(D.sn[k][i]>=1) return k;
    return -1;
  }
  function emptyNote(){
    var el=document.getElementById("sk-empty"); if(!el) return;
    if(S.v==="l"){ el.hidden=true; return; }
    var arr=field(S.v,S.k), has=arr.some(function(x){ return x!=null&&x>=0.1; });
    if(has){ el.hidden=true; return; }
    var fs=firstSnow(), msg=S.v==="s"?"V izbranem obdobju model nikjer na karti ne napoveduje sneženja.":"V tej uri model nikjer na karti ne napoveduje sneženja.";
    msg+=fs<0?" V naslednjih 48 urah sneženja ni.":" Prvo sneženje v naslednjih 48 urah: "+when(fs)+".";
    el.textContent=msg; el.hidden=false;
  }
  function draw(){
    var cv=S.cv, G=geo(), dpr=Math.min(2,window.devicePixelRatio||1), PW=G.w*dpr, PH=G.h*dpr;
    cv.width=PW; cv.height=PH;
    var ctx=cv.getContext("2d"); ctx.setTransform(dpr,0,0,dpr,0,0);
    var arr=field(S.v,S.k), img=ctx.createImageData(PW,PH), x, y;
    for(y=0;y<PH;y++) for(x=0;x<PW;x++){
      var lon=G.lon0+(x/(PW-1))*(G.lon1-G.lon0), lat=G.lat1-(y/(PH-1))*(G.lat1-G.lat0);
      var val=sample(arr,G,lon,lat); if(val==null) continue;
      var c=colorFor(S.v,val); if(!c) continue;
      var i=(y*PW+x)*4; img.data[i]=c[0]; img.data[i+1]=c[1]; img.data[i+2]=c[2]; img.data[i+3]=inSlo(lon,lat)?235:110;
    }
    ctx.putImageData(img,0,0);
    function px(lon,lat){ return [(lon-G.lon0)/(G.lon1-G.lon0)*G.w,(G.lat1-lat)/(G.lat1-G.lat0)*G.h]; }
    ctx.beginPath(); SLO.forEach(function(p,i){ var q=px(p[0],p[1]); i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]); });
    ctx.closePath(); ctx.strokeStyle="rgba(15,23,42,.75)"; ctx.lineWidth=3; ctx.stroke();
    ctx.strokeStyle="rgba(255,255,255,.9)"; ctx.lineWidth=1.2; ctx.stroke();
    ctx.font="12px sans-serif"; ctx.textBaseline="middle";
    CITIES.forEach(function(c){ var q=px(c[1],c[2]); ctx.beginPath(); ctx.arc(q[0],q[1],c[0]==="Rečica"?4:2.6,0,6.3);
      ctx.fillStyle="#fff"; ctx.fill(); ctx.strokeStyle="#0f172a"; ctx.lineWidth=1; ctx.stroke();
      ctx.shadowColor="#000"; ctx.shadowBlur=3; ctx.fillText(c[0],q[0]+6,q[1]); ctx.shadowBlur=0; });
    if(S.cur){ var q=px(S.cur[0],S.cur[1]); ctx.beginPath(); ctx.arc(q[0],q[1],6,0,6.3); ctx.strokeStyle="#fff"; ctx.lineWidth=2; ctx.stroke(); }
    var nn=arr.filter(function(x){ return x!=null; }).length;
    cv.setAttribute("aria-label",PAL[S.v].lbl+", "+when(S.k)+(nn?"":" — ni podatkov"));
  }
  function scaleHtml(){
    var P=PAL[S.v], top=P.bins[P.bins.length-1];
    return '<div class="sk-scale">'+P.cols.map(function(c){ return '<i style="background:'+c+'"></i>'; }).join("")+'</div>'+
      '<div class="sk-scale-l"><span>'+(S.v==="l"?"nižje":f(P.bins[0],P.d===0?0:1))+'</span><span>'+P.lbl+' ('+P.unit+')</span><span>'+(S.v==="l"?"višje":top+"+")+'</span></div>';
  }
  function readout(){
    if(!S.cur){ return; }
    var D=S.data, G=geo(), lon=S.cur[0], lat=S.cur[1], z=sample(D.z,G,lon,lat);
    var h=sample(field("h",S.k),G,lon,lat), l=sample(field("l",S.k),G,lon,lat), s=sample(field("s",S.k),G,lon,lat);
    var line=l==null?"—":f(l,0)+" m";
    var verdict=(l!=null&&z!=null)?(z>=l?"<b>nad</b> mejo sneženja (sneg)":"<b>pod</b> mejo sneženja (dež ali moker sneg)"):"";
    document.getElementById("sk-read").innerHTML=lat.toFixed(2).replace(".",",")+" °N, "+lon.toFixed(2).replace(".",",")+" °E · višina modela <b>"+
      (z==null?"—":f(z,0)+" m")+"</b> · "+when(S.k)+"<br>sneženje v tej uri <b>"+f(h,1)+" cm</b> · skupaj do tedaj <b>"+f(s,1)+" cm</b> · meja sneženja <b>"+line+"</b>"+
      (verdict?" · točka je "+verdict:"");
  }
  function redraw(){
    draw();
    document.getElementById("sk-when").textContent=(S.v==="s"?"do ":"")+when(S.k);
    var rg=document.getElementById("sk-range");
    rg.textContent=S.v==="s"?"Skupaj: "+whenAt(0,-1)+" → "+when(S.k)+" ("+(S.k+1)+" h)":"";
    markDay();
    emptyNote();
    document.getElementById("sk-scale").innerHTML=scaleHtml();
    readout();
  }
  function build(){
    var D=S.data, gen=new Date(D.generated).toLocaleString("sl-SI",{timeZone:TZ,hour:"2-digit",minute:"2-digit"});
    root.innerHTML=
      '<div class="sk-tabs" role="group" aria-label="Prikaz">'+["h","l","s"].map(function(k){
        return '<button type="button" data-v="'+k+'" aria-pressed="'+(S.v===k)+'">'+PAL[k].lbl+'</button>'; }).join("")+'</div>'+
      '<div class="sk-ctrl"><button type="button" id="sk-play" aria-label="Predvajaj">▶</button>'+
        '<input type="range" id="sk-slider" min="0" max="'+(D.hours-1)+'" value="'+S.k+'" aria-label="Ura napovedi">'+
        '<strong id="sk-when"></strong></div>'+
      '<div class="sk-ctrl" id="sk-days" aria-label="Izbira dneva"></div>'+
      '<div class="sk-ctrl" id="sk-quick" aria-label="Hitra izbira obdobja">'+
        '<button type="button" id="sk-prev" aria-label="Ura nazaj">⏮</button><button type="button" id="sk-next" aria-label="Ura naprej">⏭</button>'+
        [6,12,24,48].map(function(h){ return '<button type="button" data-h="'+h+'">'+(S.v==="s"?"Do +":"+")+h+' h</button>'; }).join("")+
        '<button type="button" id="sk-now">Na prvo uro</button></div>'+
      '<div class="sk-range" id="sk-range"></div>'+
      '<div class="sk-map"><canvas id="sk-cv" role="img"></canvas></div>'+
      '<div class="sk-empty" id="sk-empty" role="status" hidden></div>'+
      '<div id="sk-scale"></div>'+
      '<div class="sk-read" id="sk-read" aria-live="polite">Dotakni se karte: sneženje, skupna količina in meja sneženja na izbrani točki.</div>'+
      '<p class="sk-note">Model '+D.model+' na mreži 0,1° (okoli 8 × 11 km), korak 1 ura. Nastalo ob '+gen+(D.stale?" (podatki so nekoliko stari, vir trenutno ne odgovarja)":"")+
      '. Pregled vzorca, ne napoved za posamezno pobočje.</p>'+
      (COMPACT?'<p><a href="/zima/snezna-karta/">Celotna snežna karta in vprašanja →</a></p>':'');
    S.cv=document.getElementById("sk-cv");
    function mv(e){
      var r=S.cv.getBoundingClientRect(), G=geo();
      S.cur=[G.lon0+(e.clientX-r.left)/r.width*(G.lon1-G.lon0), G.lat1-(e.clientY-r.top)/r.height*(G.lat1-G.lat0)]; redraw();
    }
    S.cv.addEventListener("pointermove",function(e){ if(e.pointerType==="mouse"||e.buttons) mv(e); });
    S.cv.addEventListener("pointerdown",mv);
    Array.prototype.forEach.call(root.querySelectorAll("button[data-v]"),function(b){
      b.addEventListener("click",function(){ S.v=b.dataset.v; build(); }); });
    var sl=document.getElementById("sk-slider");
    sl.addEventListener("input",function(){ S.k=+sl.value; redraw(); });
    Array.prototype.forEach.call(root.querySelectorAll("button[data-h]"),function(b){
      b.addEventListener("click",function(){ S.k=+b.dataset.h-1; sl.value=S.k; redraw(); }); });
    var dEl=document.getElementById("sk-days");
    days().forEach(function(d,i){ var b=document.createElement("button"); b.type="button"; b.dataset.key=d.key; b.dataset.k=d.k;
      b.textContent=i===0?"Danes":i===1?"Jutri":new Date(d.ms).toLocaleDateString("sl-SI",{timeZone:TZ,weekday:"short",day:"numeric",month:"numeric"});
      b.addEventListener("click",function(){ S.k=+b.dataset.k; sl.value=S.k; redraw(); }); dEl.appendChild(b); });
    document.getElementById("sk-prev").addEventListener("click",function(){ S.k=Math.max(0,S.k-1); sl.value=S.k; redraw(); });
    document.getElementById("sk-next").addEventListener("click",function(){ S.k=Math.min(S.data.hours-1,S.k+1); sl.value=S.k; redraw(); });
    document.getElementById("sk-now").addEventListener("click",function(){ S.k=0; sl.value=0; redraw(); });
    document.getElementById("sk-play").addEventListener("click",function(){
      if(S.play){ clearInterval(S.play); S.play=null; this.textContent="▶"; return; }
      var btn=this; btn.textContent="❚❚";
      S.play=setInterval(function(){ S.k=(S.k+1)%S.data.hours; sl.value=S.k; redraw(); },500);
    });
    if(S.play){ clearInterval(S.play); S.play=null; }
    redraw();
  }
  root.textContent="Nalagam snežno karto …";
  fetch(PROXY+"/sneg-karta.json").then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); })
    .then(function(d){ if(!d.sn||!d.sn.length) throw new Error("prazno"); S.data=d; build(); })
    .catch(function(){ root.textContent="Snežna karta trenutno ni dosegljiva. Poskusi znova čez nekaj minut ali poglej Mejo sneženja za Rečico."; });
})();
""".replace("%SLO%", slo_poly_js()).replace("%PROXY%", PROXY)

ASSET_DIR = "zima/snezna-karta"


def head_assets():
    """Povezavi na skupna CSS/JS (stran in hub /zima/ nalagata isto datoteko; ?v= je zgoščena vsebina)."""
    import hashlib
    v = hashlib.sha1((CSS_SRC + JS_SRC).encode("utf-8")).hexdigest()[:8]   # vsebina, ne datum: sprememba istega dne zaobide predpomnilnik
    return (f'<link rel="stylesheet" href="/{ASSET_DIR}/karta.css?v={v}">\n'
            f'<script src="/{ASSET_DIR}/karta.js?v={v}" defer></script>')


def write_assets():
    os.makedirs(os.path.join(ROOT, ASSET_DIR), exist_ok=True)
    for name, src in (("karta.css", CSS_SRC), ("karta.js", JS_SRC)):
        with open(os.path.join(ROOT, ASSET_DIR, name), "w", encoding="utf-8") as fh:
            fh.write(src)


def build_body():
    faq = ("  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in FAQ) + "\n  </div>")
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Zima", "/zima/"), ("Snežna karta", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Snežna karta Slovenije</h1>
  <p class="post-meta">Sneženje po urah · meja sneženja · skupni novi sneg — na eni karti, do +48 ur</p>
  <p class="archive-intro">Izberi prikaz, povleci drsnik po urah in se dotakni karte: pokaže, kje in kdaj bo snežilo,
  na kateri višini dež preide v sneg in koliko novega snega se nabere do izbrane ure. Gre za neposredni izhod modela
  ICON-D2, ne za uradno napoved.</p>
  <div id="sk-app" aria-live="polite">Nalagam snežno karto …</div>
  <h2>Kako brati karto</h2>
  <ul>
    <li><b>Sneženje po urah</b> — modelsko sneženje v izbrani uri (cm svežega snega). Brez barve pomeni brez sneženja.</li>
    <li><b>Meja sneženja</b> — nadmorska višina, nad katero dež prehaja v sneg. Temnejša barva pomeni nižjo mejo, torej sneg tudi nižje.</li>
    <li><b>Skupaj novega snega</b> — seštevek vseh ur od zdaj do izbrane ure. Hitri gumbi nastavijo 6, 12, 24 ali 48 ur.</li>
  </ul>
  <p class="archive-intro">Podrobna meja sneženja za našo dolino je na strani <a href="/zima/meja-snezenja/" style="color:var(--blue)">Meja sneženja</a>,
  ocena na vrhovih na strani <a href="/vreme-v-gorah/" style="color:var(--blue)">Vreme v gorah</a>, za vožnjo čez prelaze pa
  <a href="/zima/prevoznost-prelazov/" style="color:var(--blue)">Prevoznost prelazov</a>.
  Vir: ICON-D2 (DWD) prek Open-Meteo (open-meteo.com).</p>
{faq}
  <a class="back-link" href="/zima/">← Nazaj na MeteoZima</a>'''


def main():
    title = "Snežna karta Slovenije: sneženje in meja"
    desc = ("Snežna karta Slovenije do +48 ur: sneženje po urah, meja sneženja in skupni novi sneg v izbranem obdobju "
            "na eni karti. Model ICON-D2, ne uradna napoved.")
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published=TODAY.isoformat()),
        seo.crumbs_schema([("Meteorec", "/"), ("Zima", "/zima/"), ("Snežna karta", None)]),
        seo.faq_schema(FAQ),
    ])
    write_assets()
    html_out = seo.page_shell(title, desc, URL, schema + "\n" + head_assets(), build_body())
    seo.write_page("zima/snezna-karta/index.html", html_out, force=True)
    print("  → zima/snezna-karta/index.html")


if __name__ == "__main__":
    main()
