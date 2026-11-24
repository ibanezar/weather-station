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
.sk-map{max-width:900px;border-radius:10px;overflow:hidden;background:#0a1424}
.sk-map canvas{width:100%;height:auto;display:block;touch-action:pan-y;cursor:crosshair}
.sk-map:fullscreen,.sk-map:-webkit-full-screen{max-width:none;border-radius:0;display:flex;align-items:center;justify-content:center;background:#050a14}
.sk-map:fullscreen canvas,.sk-map:-webkit-full-screen canvas{width:100vw;height:100vh;object-fit:contain;cursor:pointer}
.sk-scale{height:10px;border-radius:3px;margin:.5rem 0 .2rem;max-width:900px}
.sk-scale-l{display:flex;justify-content:space-between;max-width:900px;font-size:.75rem;color:var(--muted)}
.sk-read{min-height:3em;font-size:.9rem;color:var(--muted);margin:.5rem 0}
.sk-read b{color:var(--text,#e5e7eb)}
.sk-note{font-size:.8rem;color:var(--muted);margin:.2rem 0 1rem}
"""

JS_SRC = r"""
(function(){
  var root=document.getElementById("sk-app"); if(!root) return;
  var SLO=%SLO%, PROXY="%PROXY%", TZ="Europe/Ljubljana", RELIEF_SRC="/zima/snezna-karta/relief.webp";
  var CITIES=[["Ljubljana",14.506,46.056],["Maribor",15.646,46.554],["Celje",15.26,46.231],["Koper",13.73,45.548],
              ["Kranj",14.356,46.239],["Nova Gorica",13.644,45.956],["Novo mesto",15.169,45.804],["Murska Sobota",16.166,46.662,600],
              ["Kranjska Gora",13.786,46.485],["Postojna",14.215,45.775],["Bovec",13.552,46.337],["Slovenj Gradec",15.08,46.51],
              ["Kočevje",14.86,45.64],["Rečica",14.921,46.326]];
  // Barve so izbrane za temno reliefno podlago; mejniki (bins) in enote so isti kot prej.
  var PAL={
    h:{lbl:"Sneženje po urah",unit:"cm/h",d:1,bins:[0.1,0.5,1,2,3,5,8],
       cols:["#8ecbff","#5fb0ff","#4c8dff","#6b73ff","#9a6bff","#c46bff","#f08cff"]},
    l:{lbl:"Meja sneženja",unit:"m",d:0,bins:[400,600,800,1000,1200,1500,1800,2200],
       cols:["#f5fbff","#d6ecff","#a9d6ff","#74b6f5","#4d8fe0","#3a6cc0","#2f4f96","#26386b","#1e2749"]},
    s:{lbl:"Skupaj novega snega",unit:"cm",d:0,bins:[0.5,2,5,10,20,30,50,80],
       cols:["#8ecbff","#5fb0ff","#4c8dff","#5a78ff","#7b6bff","#9a6bff","#b56bff","#d27cff","#f59bff"]}
  };
  var S={v:root.dataset.view||"h",k:(+root.dataset.hours||1)-1,f:0,data:null,raf:0,cv:null,cur:null,rel:null,relOk:false,cssW:760,spd:2,fc:{},oc:null};
  var COMPACT=root.dataset.compact==="1";
  var SPEEDS=[1,2,4];
  var fDate=new Intl.DateTimeFormat("sl-SI",{timeZone:TZ,weekday:"long",day:"numeric",month:"long"});
  var fTime=new Intl.DateTimeFormat("sl-SI",{timeZone:TZ,hour:"2-digit",minute:"2-digit",hourCycle:"h23"});
  var fWd=new Intl.DateTimeFormat("sl-SI",{timeZone:TZ,weekday:"short"});
  function f(x,d){ return x==null||isNaN(x)?"—":x.toFixed(d).replace(".",","); }
  function hex(c){ return [parseInt(c.substr(1,2),16),parseInt(c.substr(3,2),16),parseInt(c.substr(5,2),16)]; }
  function cap(s){ return s.charAt(0).toUpperCase()+s.slice(1); }
  PAL.h.rgb=PAL.h.cols.map(hex); PAL.l.rgb=PAL.l.cols.map(hex); PAL.s.rgb=PAL.s.cols.map(hex);
  function fsEl(){ return document.fullscreenElement||document.webkitFullscreenElement||null; }
  function inSlo(lon,lat){
    var ins=false; for(var i=0,j=SLO.length-1;i<SLO.length;j=i++){
      var xi=SLO[i][0],yi=SLO[i][1],xj=SLO[j][0],yj=SLO[j][1];
      if(((yi>lat)!==(yj>lat))&&(lon<(xj-xi)*(lat-yi)/(yj-yi)+xi)) ins=!ins; }
    return ins;
  }
  function geo(){
    var D=S.data, W=D.nx, H=D.ny, lon1=D.lon0+(W-1)*D.d, lat1=D.lat0+(H-1)*D.d;
    var cs=Math.cos(46.2*Math.PI/180), wpx=S.cssW, hpx=Math.round(wpx*(lat1-D.lat0)/((lon1-D.lon0)*cs));
    return {W:W,H:H,lon0:D.lon0,lat0:D.lat0,lon1:lon1,lat1:lat1,w:wpx,h:hpx};
  }
  // polje za izbrani prikaz in uro: hourly = sneženje v uri, l = meja, s = vsota ur 1..k+1 (predpomnjeno po prikazu in uri)
  function field(v,k){
    var key=v+":"+k; if(S.fc[key]) return S.fc[key];
    var D=S.data, n=D.nx*D.ny, out=new Array(n), i, h;
    if(v==="h"){ for(i=0;i<n;i++) out[i]=D.sn[k][i]==null?null:D.sn[k][i]*D.units.sn; }
    else if(v==="l"){ for(i=0;i<n;i++) out[i]=D.ln[k][i]==null?null:Math.max(0,D.ln[k][i]*D.units.ln); }
    else { for(i=0;i<n;i++){ var sum=0, bad=false; for(h=0;h<=k;h++){ var x=D.sn[h][i]; if(x==null){ bad=true; break; } sum+=x; }
      out[i]=bad?null:sum*D.units.sn; } }
    S.fc[key]=out; return out;
  }
  // vmesna ura (predvajanje): linearni prehod med uro k in k+1; kjer ena od njiju nima podatka, tudi vmesna nima
  function fieldAt(v,k,fr){
    var a=field(v,k); if(!fr||k>=S.data.hours-1) return a;
    var b=field(v,k+1), n=a.length, out=new Array(n), i;
    for(i=0;i<n;i++) out[i]=(a[i]==null||b[i]==null)?null:a[i]*(1-fr)+b[i]*fr;
    return out;
  }
  function cr(p0,p1,p2,p3,t){ return p1+0.5*t*(p2-p0+t*(2*p0-5*p1+4*p2-p3+t*(3*(p1-p2)+p3-p0))); }
  function sample(arr,G,lon,lat,soft){
    var D=S.data, fx=(lon-D.lon0)/D.d, fy=(lat-D.lat0)/D.d;
    var x0=Math.max(0,Math.min(G.W-2,Math.floor(fx))), y0=Math.max(0,Math.min(G.H-2,Math.floor(fy)));
    var u=Math.max(0,Math.min(1,fx-x0)), w=Math.max(0,Math.min(1,fy-y0));
    if(soft){                                            // za izris: kubična (Catmull-Rom) interpolacija, vrednosti v središčih celic ostanejo
      var rows=[], j, i2, ok=true;
      for(j=-1;j<=2&&ok;j++){ var yy=Math.max(0,Math.min(G.H-1,y0+j)), r=[];
        for(i2=-1;i2<=2;i2++){ var v=arr[yy*G.W+Math.max(0,Math.min(G.W-1,x0+i2))]; if(v==null){ ok=false; break; } r.push(v); }
        rows.push(r); }
      if(ok){
        var col=rows.map(function(r){ return cr(r[0],r[1],r[2],r[3],u); });
        return Math.max(0,cr(col[0],col[1],col[2],col[3],w));
      }
    }
    var a=arr[y0*G.W+x0], b=arr[y0*G.W+x0+1], c=arr[(y0+1)*G.W+x0], d=arr[(y0+1)*G.W+x0+1];
    if(a==null||b==null||c==null||d==null) return null;
    return (a*(1-u)+b*u)*(1-w)+(c*(1-u)+d*u)*w;
  }
  function mix(c1,c2,t){ return [c1[0]+(c2[0]-c1[0])*t,c1[1]+(c2[1]-c1[1])*t,c1[2]+(c2[2]-c1[2])*t]; }
  // barva in neprosojnost za vrednost; sneženje: brez barve = brez sneženja, rahel prehod proti prvemu mejniku
  function ramp(v,val){
    var P=PAL[v], b=P.bins, c=P.rgb, n=b.length, i;
    if(val==null) return null;
    if(v==="l"){
      var pos=[b[0]-(b[1]-b[0])/2]; for(i=1;i<n;i++) pos.push((b[i-1]+b[i])/2); pos.push(b[n-1]+(b[n-1]-b[n-2])/2);
      var col;
      if(val<=pos[0]) col=c[0]; else if(val>=pos[n]) col=c[n];
      else { i=0; while(val>=pos[i+1]) i++; col=mix(c[i],c[i+1],(val-pos[i])/(pos[i+1]-pos[i])); }
      return [col[0],col[1],col[2],0.78];
    }
    if(val<0.02) return null;
    var a0=0.42, a1=0.95;
    if(val<b[0]){ var t0=val/b[0]; return [c[0][0],c[0][1],c[0][2],a0*t0]; }
    if(val>=b[n-1]) return [c[n-1][0],c[n-1][1],c[n-1][2],a1];
    i=0; while(val>=b[i+1]) i++;
    var t=(val-b[i])/(b[i+1]-b[i]), cc=mix(c[i],c[i+1],t);
    return [cc[0],cc[1],cc[2],a0+(a1-a0)*((i+t)/(n-1))];
  }
  function msAt(k,fr){ return S.data.t0+(k+1+(fr||0))*3600000; }
  function when(k){ return new Date(msAt(k)).toLocaleString("sl-SI",{timeZone:TZ,weekday:"short",day:"numeric",month:"numeric",hour:"2-digit",minute:"2-digit"}); }
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
    if(!arr.some(function(x){ return x!=null; })){ // model te ure nima (ICON-D2 sega 48 ur od svojega teka): to ni »ni sneženja«
      el.textContent="Za izbrano uro model nima podatkov (ICON-D2 sega 48 ur od svojega zadnjega teka). Izberi zgodnejšo uro."; el.hidden=false; return; }
    var fs=firstSnow(), msg=S.v==="s"?"V izbranem obdobju model nikjer na karti ne napoveduje sneženja.":"V tej uri model nikjer na karti ne napoveduje sneženja.";
    msg+=fs<0?" V naslednjih 48 urah sneženja ni.":" Prvo sneženje v naslednjih 48 urah: "+when(fs)+".";
    el.textContent=msg; el.hidden=false;
  }
  // ───── izris ─────
  function sloPath(ctx,G){
    SLO.forEach(function(p,i){ var q=px(G,p[0],p[1]); i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]); }); ctx.closePath();
  }
  function px(G,lon,lat){ return [(lon-G.lon0)/(G.lon1-G.lon0)*G.w,(G.lat1-lat)/(G.lat1-G.lat0)*G.h]; }
  function overlay(arr,G){ // polje -> majhna slika (6-kratna gostota mreže, vrednosti se interpolirajo pred barvanjem), brskalnik jo gladko poveča
    var UP=6, ow=(G.W-1)*UP+1, oh=(G.H-1)*UP+1;
    if(!S.oc||S.oc.width!==ow){ S.oc=document.createElement("canvas"); S.oc.width=ow; S.oc.height=oh; }
    var octx=S.oc.getContext("2d"), img=octx.createImageData(ow,oh), x, y, cnt=0;
    for(y=0;y<oh;y++) for(x=0;x<ow;x++){
      var lon=G.lon0+x/(ow-1)*(G.lon1-G.lon0), lat=G.lat1-y/(oh-1)*(G.lat1-G.lat0);
      var c=ramp(S.v,sample(arr,G,lon,lat,true)); if(!c) continue;
      var i=(y*ow+x)*4; img.data[i]=c[0]; img.data[i+1]=c[1]; img.data[i+2]=c[2]; img.data[i+3]=Math.round(c[3]*255); if(c[3]>0.2) cnt++;
    }
    octx.putImageData(img,0,0);
    return cnt;
  }
  function label(ctx,t,x,y,size,weight,alpha){
    ctx.font=weight+" "+size+"px system-ui,-apple-system,Segoe UI,Roboto,sans-serif";
    ctx.shadowColor="rgba(2,6,16,.95)"; ctx.shadowBlur=4; ctx.fillStyle="rgba(255,255,255,"+(alpha||1)+")"; ctx.fillText(t,x,y); ctx.shadowBlur=0;
  }
  function frame(){
    if(!S.cv||!S.data) return;
    var cv=S.cv, G=geo(), dpr=Math.min(2,window.devicePixelRatio||1), PW=Math.round(G.w*dpr), PH=Math.round(G.h*dpr);
    if(cv.width!==PW||cv.height!==PH){ cv.width=PW; cv.height=PH; }
    var ctx=cv.getContext("2d"); ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,G.w,G.h);
    ctx.imageSmoothingEnabled=true; ctx.imageSmoothingQuality="high";
    ctx.fillStyle="#0a1424"; ctx.fillRect(0,0,G.w,G.h);
    if(S.relOk) ctx.drawImage(S.rel,0,0,G.w,G.h);
    var arr=fieldAt(S.v,S.k,S.f), cnt=overlay(arr,G);
    // zunaj Slovenije šibkeje: karta ostane berljiva, a poudarek je na državi
    ctx.save(); ctx.beginPath(); ctx.rect(0,0,G.w,G.h); sloPath(ctx,G); ctx.clip("evenodd");
    ctx.fillStyle="rgba(4,9,20,.30)"; ctx.fillRect(0,0,G.w,G.h); ctx.globalAlpha=0.5; ctx.drawImage(S.oc,0,0,G.w,G.h); ctx.restore();
    ctx.save(); ctx.beginPath(); sloPath(ctx,G); ctx.clip(); ctx.drawImage(S.oc,0,0,G.w,G.h); ctx.restore();
    ctx.beginPath(); sloPath(ctx,G); ctx.strokeStyle="rgba(2,6,16,.8)"; ctx.lineWidth=3.2; ctx.stroke();
    ctx.strokeStyle="rgba(235,244,255,.92)"; ctx.lineWidth=1.3; ctx.stroke();
    // kraji
    var fs=Math.max(10,Math.min(13.5,G.w/58)); ctx.textBaseline="middle";
    CITIES.forEach(function(c){ if(c[3]&&G.w<c[3]) return; var q=px(G,c[1],c[2]), me=c[0]==="Rečica";
      ctx.beginPath(); ctx.arc(q[0],q[1],me?4:2.6,0,6.3); ctx.fillStyle=me?"#ffd166":"#fff"; ctx.fill(); ctx.strokeStyle="#0f172a"; ctx.lineWidth=1; ctx.stroke();
      label(ctx,c[0],q[0]+6,q[1],fs,me?"700":"500",1); });
    if(S.cur){ var q=px(G,S.cur[0],S.cur[1]); ctx.beginPath(); ctx.arc(q[0],q[1],7,0,6.3); ctx.strokeStyle="#fff"; ctx.lineWidth=2; ctx.stroke(); }
    // naslov, ura, vir (na sliki, da ostane ob posnetku zaslona)
    var kf=S.k+S.f, ms=Math.round(msAt(S.k,S.f)/300000)*300000, big=Math.max(20,Math.min(30,G.w/26)), pad=Math.max(10,G.w/48);
    ctx.textAlign="left"; label(ctx,PAL[S.v].lbl+" · "+PAL[S.v].unit,pad,pad+fs*0.6,fs+1,"700",.95);
    ctx.textAlign="right"; label(ctx,(S.v==="s"?"do ":"")+fTime.format(new Date(ms)),G.w-pad,pad+big*0.55,big,"700",1);
    label(ctx,cap(fDate.format(new Date(ms))),G.w-pad,pad+big*1.25+fs*0.4,fs,"500",.9);
    ctx.textAlign="left"; label(ctx,"meteorec.si · ICON-D2 · modelska napoved, ne meritev",pad,pad+fs*2.15,Math.max(9,fs-2.5),"400",.7);
    // časovnica
    var tx0=pad, tx1=G.w-pad, ty=G.h-pad*1.05, H=S.data.hours, prog=H>1?kf/(H-1):0;
    ctx.fillStyle="rgba(255,255,255,.28)"; ctx.fillRect(tx0,ty-1.5,tx1-tx0,3);
    ctx.fillStyle="#cfe6ff"; ctx.fillRect(tx0,ty-1.5,(tx1-tx0)*prog,3);
    ctx.textAlign="center"; days().forEach(function(d,i){ if(!i) return; var x=tx0+(tx1-tx0)*d.k/(H-1);
      ctx.fillStyle="rgba(255,255,255,.55)"; ctx.fillRect(x-.5,ty-5,1,10); label(ctx,fWd.format(new Date(d.ms)),x,ty-11,Math.max(9,fs-2.5),"400",.7); });
    ctx.beginPath(); ctx.arc(tx0+(tx1-tx0)*prog,ty,5,0,6.3); ctx.fillStyle="#fff"; ctx.fill(); ctx.strokeStyle="#0f172a"; ctx.lineWidth=1.2; ctx.stroke();
    ctx.textAlign="left";
    cv.dataset.px=String(cnt);                                   // št. vidno pobarvanih točk prekrivnega sloja (za test)
    cv.dataset.rel=S.relOk?"1":"0";
    var nn=arr.filter(function(x){ return x!=null; }).length;
    cv.setAttribute("aria-label",PAL[S.v].lbl+", "+when(S.k)+(nn?"":" — ni podatkov"));
  }
  function scaleHtml(){
    var P=PAL[S.v], top=P.bins[P.bins.length-1];
    return '<div class="sk-scale" style="background:linear-gradient(90deg,'+P.cols.join(",")+')"></div>'+
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
    frame();
    document.getElementById("sk-when").textContent=(S.v==="s"?"do ":"")+when(S.k);
    var rg=document.getElementById("sk-range");
    rg.textContent=S.v==="s"?"Skupaj: "+whenAt(0,-1)+" → "+when(S.k)+" ("+(S.k+1)+" h)":"";
    markDay();
    emptyNote();
    document.getElementById("sk-scale").innerHTML=scaleHtml();
    readout();
  }
  // ───── predvajanje ─────
  function playing(){ return !!S.raf; }
  function setPlayUi(){
    var b=document.getElementById("sk-play"); if(!b) return;
    b.textContent=playing()?"❚❚":"▶"; b.setAttribute("aria-label",playing()?"Premor":"Predvajaj");
  }
  function stop(){ if(S.raf){ cancelAnimationFrame(S.raf); S.raf=0; } S.f=0; setPlayUi(); }
  function play(){
    if(playing()) return;
    var H=S.data.hours, last=0, hold=0, sl=document.getElementById("sk-slider");
    function tick(t){
      if(!S.raf) return;
      var dt=last?Math.min(0.1,(t-last)/1000):0; last=t;
      if(hold>0){ hold-=dt; if(hold<=0){ S.k=0; S.f=0; } }
      else {
        var kf=S.k+S.f+dt*SPEEDS[S.spd];
        if(kf>=H-1){ S.k=H-1; S.f=0; hold=1.2; }
        else { S.k=Math.floor(kf); S.f=kf-S.k; }
      }
      if(sl) sl.value=S.k;
      frame();
      if(Math.floor(t/250)!==Math.floor((t-dt*1000)/250)){ document.getElementById("sk-when").textContent=(S.v==="s"?"do ":"")+when(S.k); markDay(); }
      S.raf=requestAnimationFrame(tick);
    }
    if(S.k>=H-1) S.k=0;
    S.raf=requestAnimationFrame(tick); setPlayUi();
  }
  function seek(k){ stop(); S.k=Math.max(0,Math.min(S.data.hours-1,k)); var sl=document.getElementById("sk-slider"); if(sl) sl.value=S.k; redraw(); }
  function fit(){
    var m=S.cv&&S.cv.parentNode; if(!m) return;
    var w=m.clientWidth||760; if(fsEl()===m) w=Math.max(w,window.innerWidth);
    S.cssW=Math.max(300,Math.min(1000,Math.round(w)));
  }
  function build(){
    var D=S.data, gen=new Date(D.generated).toLocaleString("sl-SI",{timeZone:TZ,hour:"2-digit",minute:"2-digit"});
    stop();
    var fsOk=!!(root.requestFullscreen||root.webkitRequestFullscreen);
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
        '<button type="button" id="sk-now">Na prvo uro</button>'+
        '<button type="button" id="sk-speed" aria-label="Hitrost predvajanja">Hitrost ×'+SPEEDS[S.spd]+'</button>'+
        (fsOk?'<button type="button" id="sk-fs">⛶ Celozaslonski način</button>':'')+'</div>'+
      '<div class="sk-range" id="sk-range"></div>'+
      '<div class="sk-map"><canvas id="sk-cv" role="img"></canvas></div>'+
      '<div class="sk-empty" id="sk-empty" role="status" hidden></div>'+
      '<div id="sk-scale"></div>'+
      '<div class="sk-read" id="sk-read" aria-live="polite">Dotakni se karte: sneženje, skupna količina in meja sneženja na izbrani točki. Predvajanje (▶) kaže, kako se sneženje premika po državi.</div>'+
      '<p class="sk-note">Model '+D.model+' na mreži 0,1° (okoli 8 × 11 km), korak 1 ura; med urami je slika linearno prehajana, zato je gibanje gladko, a ne bolj natančno od modela. Nastalo ob '+gen+(D.stale?" (podatki so nekoliko stari, vir trenutno ne odgovarja)":"")+
      '. Pregled vzorca, ne napoved za posamezno pobočje. Relief: Copernicus DEM GLO-30 (© DLR e.V. 2010–2014, © Airbus Defence and Space GmbH 2014–2018, na voljo prek programa Copernicus Evropske unije in ESA), le kot podlaga.</p>'+
      (COMPACT?'<p><a href="/zima/snezna-karta/">Celotna snežna karta in vprašanja →</a></p>':'');
    S.cv=document.getElementById("sk-cv"); fit();
    var mapEl=S.cv.parentNode;
    function norm(e){ // položaj na karti (0–1), upošteva črne robove v celozaslonskem načinu (object-fit: contain)
      var r=S.cv.getBoundingClientRect(), ratio=S.cv.width/S.cv.height, bw=r.width, bh=r.height, cw=bw, ch=bh, ox=0, oy=0;
      if(bw/bh>ratio){ cw=bh*ratio; ox=(bw-cw)/2; } else { ch=bw/ratio; oy=(bh-ch)/2; }
      return {x:(e.clientX-r.left-ox)/cw,y:(e.clientY-r.top-oy)/ch,H:ch};
    }
    function mv(e){
      var p=norm(e), G=geo();
      if(p.x<0||p.x>1||p.y<0||p.y>1) return;
      var pad=Math.max(10,G.w/48), bottom=(G.h-pad*2.4)/G.h;
      if(e.type==="pointerdown"&&p.y>=bottom){                  // dotik časovnice: preskok na uro
        var x0=pad/G.w, x1=1-pad/G.w; seek(Math.round((Math.max(0,Math.min(1,(p.x-x0)/(x1-x0))))*(S.data.hours-1))); return; }
      if(e.type==="pointerdown"&&fsEl()===mapEl){ playing()?stop():play(); return; }   // celozaslonsko: dotik = predvajaj/premor
      S.cur=[G.lon0+p.x*(G.lon1-G.lon0), G.lat1-p.y*(G.lat1-G.lat0)]; redraw();
    }
    S.cv.addEventListener("pointermove",function(e){ if(e.pointerType==="mouse"||e.buttons) mv(e); });
    S.cv.addEventListener("pointerdown",mv);
    Array.prototype.forEach.call(root.querySelectorAll("button[data-v]"),function(b){
      b.addEventListener("click",function(){ S.v=b.dataset.v; build(); }); });
    var sl=document.getElementById("sk-slider");
    sl.addEventListener("input",function(){ seek(+sl.value); });
    Array.prototype.forEach.call(root.querySelectorAll("button[data-h]"),function(b){
      b.addEventListener("click",function(){ seek(+b.dataset.h-1); }); });
    var dEl=document.getElementById("sk-days");
    days().forEach(function(d,i){ var b=document.createElement("button"); b.type="button"; b.dataset.key=d.key; b.dataset.k=d.k;
      b.textContent=i===0?"Danes":i===1?"Jutri":new Date(d.ms).toLocaleDateString("sl-SI",{timeZone:TZ,weekday:"short",day:"numeric",month:"numeric"});
      b.addEventListener("click",function(){ seek(+b.dataset.k); }); dEl.appendChild(b); });
    document.getElementById("sk-prev").addEventListener("click",function(){ seek(S.k-1); });
    document.getElementById("sk-next").addEventListener("click",function(){ seek(S.k+1); });
    document.getElementById("sk-now").addEventListener("click",function(){ seek(0); });
    document.getElementById("sk-play").addEventListener("click",function(){ playing()?stop():play(); });
    document.getElementById("sk-speed").addEventListener("click",function(){ S.spd=(S.spd+1)%SPEEDS.length; this.textContent="Hitrost ×"+SPEEDS[S.spd]; });
    var fsb=document.getElementById("sk-fs");
    if(fsb) fsb.addEventListener("click",function(){
      if(fsEl()){ (document.exitFullscreen||document.webkitExitFullscreen).call(document); return; }
      var req=mapEl.requestFullscreen||mapEl.webkitRequestFullscreen; if(req) req.call(mapEl);
    });
    redraw();
  }
  var rz=0;
  window.addEventListener("resize",function(){ clearTimeout(rz); rz=setTimeout(function(){ if(S.data&&S.cv){ fit(); frame(); } },120); });
  ["fullscreenchange","webkitfullscreenchange"].forEach(function(ev){ document.addEventListener(ev,function(){ if(S.data&&S.cv){ fit(); frame(); } }); });
  document.addEventListener("visibilitychange",function(){ if(document.hidden&&playing()) stop(); });
  // podlaga (relief) se naloži ločeno: brez nje karta deluje na ravni temni podlagi
  var rel=new Image(); rel.onload=function(){ S.rel=rel; S.relOk=true; if(S.data&&S.cv) frame(); }; rel.src=RELIEF_SRC;
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
  <p class="archive-intro">Izberi prikaz, pritisni ▶ in poglej, kako sneženje potuje po državi (ali povleci drsnik po urah), nato se dotakni karte: pokaže, kje in kdaj bo snežilo,
  na kateri višini dež preide v sneg in koliko novega snega se nabere do izbrane ure. Gre za neposredni izhod modela
  ICON-D2, ne za uradno napoved.</p>
  <div id="sk-app" aria-live="polite">Nalagam snežno karto …</div>
  <h2>Kako brati karto</h2>
  <ul>
    <li><b>Sneženje po urah</b> — modelsko sneženje v izbrani uri (cm svežega snega). Brez barve pomeni brez sneženja.</li>
    <li><b>Meja sneženja</b> — nadmorska višina, nad katero dež prehaja v sneg. Svetlejša barva pomeni nižjo mejo, torej sneg tudi nižje.</li>
    <li><b>Predvajanje</b> — gumb ▶ vrti napoved ura za uro z gladkim prehodom med urami; hitrost izbereš z gumbom »Hitrost«, celozaslonski način pa je primeren za posnetek zaslona. Na sliki sta ura in oznaka vira (ICON-D2, modelska napoved).</li>
    <li><b>Skupaj novega snega</b> — seštevek vseh ur od zdaj do izbrane ure. Hitri gumbi nastavijo 6, 12, 24 ali 48 ur.</li>
  </ul>
  <p class="archive-intro">Podrobna meja sneženja za našo dolino je na strani <a href="/zima/meja-snezenja/" style="color:var(--blue)">Meja sneženja</a>,
  ocena na vrhovih na strani <a href="/vreme-v-gorah/" style="color:var(--blue)">Vreme v gorah</a>, za vožnjo čez prelaze pa
  <a href="/zima/prevoznost-prelazov/" style="color:var(--blue)">Prevoznost prelazov</a>.
  Vir: ICON-D2 (DWD) prek Open-Meteo (open-meteo.com).</p>
{faq}
  <a class="back-link" href="/zima/">← Nazaj na MeteoZima</a>'''


def main():
    title = "Snežna karta Slovenije: sneženje po urah, +48 h"
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
