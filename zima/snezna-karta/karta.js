
(function(){
  var root=document.getElementById("sk-app"); if(!root) return;
  var SLO=[[16.242,46.876],[16.291,46.873],[16.347,46.84],[16.34,46.804],[16.313,46.798],[16.312,46.778],[16.33,46.778],[16.319,46.756],[16.357,46.716],[16.371,46.722],[16.369,46.704],[16.427,46.695],[16.42,46.658],[16.393,46.664],[16.385,46.652],[16.392,46.634],[16.445,46.611],[16.483,46.566],[16.508,46.565],[16.531,46.531],[16.525,46.505],[16.597,46.476],[16.595,46.465],[16.561,46.478],[16.526,46.468],[16.532,46.478],[16.487,46.508],[16.441,46.515],[16.427,46.533],[16.407,46.527],[16.368,46.555],[16.337,46.543],[16.34,46.529],[16.242,46.498],[16.273,46.415],[16.307,46.396],[16.302,46.378],[16.19,46.378],[16.141,46.405],[16.058,46.394],[16.05,46.382],[16.077,46.346],[16.035,46.336],[16.014,46.309],[15.977,46.312],[15.955,46.294],[15.791,46.259],[15.801,46.243],[15.768,46.21],[15.675,46.227],[15.648,46.217],[15.645,46.188],[15.596,46.146],[15.613,46.133],[15.605,46.112],[15.619,46.092],[15.731,46.044],[15.701,45.999],[15.706,45.921],[15.68,45.904],[15.691,45.885],[15.678,45.869],[15.709,45.846],[15.665,45.841],[15.642,45.821],[15.573,45.853],[15.56,45.836],[15.539,45.848],[15.521,45.822],[15.493,45.832],[15.466,45.818],[15.465,45.795],[15.399,45.792],[15.26,45.726],[15.323,45.674],[15.319,45.694],[15.355,45.714],[15.364,45.694],[15.349,45.672],[15.369,45.69],[15.406,45.648],[15.345,45.646],[15.349,45.635],[15.306,45.632],[15.306,45.613],[15.277,45.604],[15.297,45.586],[15.304,45.534],[15.385,45.488],[15.346,45.458],[15.273,45.465],[15.226,45.427],[15.194,45.436],[15.158,45.425],[15.085,45.468],[15.085,45.482],[14.987,45.497],[14.933,45.528],[14.914,45.519],[14.905,45.477],[14.817,45.462],[14.796,45.503],[14.719,45.534],[14.69,45.527],[14.7,45.563],[14.689,45.581],[14.597,45.628],[14.61,45.659],[14.57,45.673],[14.543,45.622],[14.502,45.608],[14.488,45.537],[14.323,45.47],[14.286,45.49],[14.266,45.483],[14.245,45.505],[14.214,45.493],[14.207,45.47],[14.074,45.484],[14.002,45.52],[14.001,45.508],[13.962,45.506],[13.996,45.473],[13.971,45.448],[13.909,45.451],[13.887,45.426],[13.856,45.426],[13.815,45.434],[13.786,45.466],[13.676,45.443],[13.587,45.477],[13.595,45.507],[13.565,45.53],[13.719,45.544],[13.746,45.569],[13.709,45.593],[13.839,45.582],[13.918,45.633],[13.834,45.687],[13.834,45.707],[13.796,45.743],[13.668,45.799],[13.596,45.808],[13.576,45.854],[13.637,45.935],[13.642,45.983],[13.59,45.989],[13.539,45.965],[13.477,46.006],[13.508,46.034],[13.497,46.058],[13.644,46.137],[13.664,46.178],[13.634,46.192],[13.567,46.186],[13.546,46.212],[13.48,46.225],[13.444,46.225],[13.446,46.213],[13.423,46.206],[13.41,46.216],[13.422,46.234],[13.375,46.298],[13.44,46.323],[13.439,46.359],[13.566,46.399],[13.597,46.439],[13.693,46.443],[13.714,46.523],[13.795,46.506],[13.913,46.521],[14.007,46.481],[14.052,46.492],[14.12,46.477],[14.164,46.434],[14.283,46.443],[14.328,46.431],[14.429,46.447],[14.442,46.424],[14.48,46.414],[14.521,46.426],[14.565,46.372],[14.597,46.437],[14.675,46.451],[14.683,46.467],[14.701,46.466],[14.715,46.499],[14.819,46.509],[14.823,46.544],[14.868,46.605],[14.919,46.603],[14.923,46.62],[14.956,46.633],[14.979,46.601],[15.04,46.65],[15.144,46.659],[15.236,46.64],[15.419,46.655],[15.456,46.638],[15.467,46.614],[15.5,46.615],[15.542,46.63],[15.546,46.67],[15.595,46.69],[15.623,46.68],[15.653,46.691],[15.65,46.706],[15.769,46.699],[15.841,46.722],[15.909,46.711],[16.038,46.656],[16.03,46.711],[16.005,46.717],[15.986,46.752],[15.997,46.812],[15.986,46.826],[16.058,46.839],[16.114,46.869],[16.156,46.854],[16.242,46.876]], PROXY="https://weatherireica1.filip-eremita.workers.dev", TZ="Europe/Ljubljana";
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
    if(!arr.some(function(x){ return x!=null; })){ // model te ure nima (ICON-D2 sega 48 ur od svojega teka): to ni »ni sneženja«
      el.textContent="Za izbrano uro model nima podatkov (ICON-D2 sega 48 ur od svojega zadnjega teka). Izberi zgodnejšo uro."; el.hidden=false; return; }
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
