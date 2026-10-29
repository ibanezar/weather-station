#!/usr/bin/env python3
"""
tools/generate_migrena_page.py — /migrena/: vreme in migrena (napoved sprožilcev, graf tlaka, dnevnik napadov, analiza)

Konfiguracija za day_score_common.py + lastni razdelki:
  * graf zračnega tlaka od -24 h do +72 h s poudarjenimi padci (>= 5 hPa v 24 h),
  * osebni sprožilci (utež x2) in prag, shranjeno samo v brskalniku (localStorage),
  * dnevnik napadov (samo v brskalniku, izvoz CSV) in analiza: primerja dneve napadov z ostalimi dnevi
    po meritvah postaje IREICA1 iz history.json (ZUNANJI podatki; notranjih meritev ni in ne smejo priti).

Ni zdravniški nasvet. Analiza je opis majhnega vzorca, ne dokaz vzročnosti. JS migAnalyze() živi samo v tej
datoteki; test_migrena.py ga poganja z Nodom na sintetičnih podatkih. dvLevel() je podvojitev level_index()
(test primerja).
"""
import datetime, json, os, sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, bands_desc, mean, storm_pts, wind_pts, esc  # noqa: E402
import generate_seo_pages as seo  # noqa: E402

DROP_TH = (3, 5, 8)     # hPa v 24 h: pod 3 = 0, 3-5 = 1, 5-8 = 2, 8+ = 3
DROP_MARK = 5           # na grafu poudarjen padec od te vrednosti
LOW_P_TH = (1008, 1002, 995)
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"
# Meje praga alarma: podvojitev MIG_THR_ALLOWED v worker.js (test_migrena.py primerja).
ALARM_THR = ((3, "občutljivo: padec za 3 hPa ali več"), (5, "običajno: padec za 5 hPa ali več"), (8, "samo izrazit padec: 8 hPa ali več"))
TRIGGERS = {
    "tlak_pad": "hiter padec zračnega tlaka", "tlak_nizek": "nizek zračni tlak",
    "sprememba": "hitre spremembe temperature", "vrocina": "vročina in soparnost", "nevihta": "nevihte",
    "veter": "močan veter (jugo, fen)", "vlaga": "zelo vlažen ali suh zrak", "svetloba": "močna svetloba (UV)",
}

# Ikona glave z bliskom: Filipova slika (img/migrena/glava-blisk.png, 128 px; original 512 px ni v repozitoriju).
HEAD_ICON = ('<img class="dv-art" src="/img/migrena/glava-blisk.png" width="64" height="64" alt="Glava z bliskom" '
             'decoding="async">')


# ── Dejavniki ────────────────────────────────────────────────────────────────

def pressure_drops(c, date_iso):
    """Največji padec tlaka v 24 h (hPa, pozitivno) med urami izbranega dne; None brez podatkov."""
    arr = c.h.get("pressure_msl") or []
    best = None
    for i in c.by_date.get(date_iso, []):
        if i - 24 < 0 or i >= len(arr) or arr[i] is None or arr[i - 24] is None:
            continue
        drop = arr[i - 24] - arr[i]
        best = drop if best is None else max(best, drop)
    return best


def _prev(d, n):
    return (datetime.date.fromisoformat(d) - datetime.timedelta(days=n)).isoformat()


def day_fn(c, d):
    pts, det = {}, {}
    drop = pressure_drops(c, d)
    pts["tlak_pad"] = bands(drop, DROP_TH) if drop is not None else 0
    det["tlak_pad"] = (f"tlak pade do {seo.num(drop, 1)} hPa v 24 h" if drop is not None and drop >= DROP_TH[0]
                       else f"brez izrazitega padca tlaka (največ {seo.num(max(drop, 0), 1)} hPa v 24 h)" if drop is not None
                       else "model ne vrača podatka")
    p = mean(c.vals("pressure_msl", d))
    pts["tlak_nizek"] = bands_desc(p, LOW_P_TH)
    det["tlak_nizek"] = f"tlak povprečno {seo.num(p, 0)} hPa" if p is not None else "model ne vrača podatka"
    t, tp = mean(c.vals("temperature_2m", d)), mean(c.vals("temperature_2m", _prev(d, 1)))
    dt = None if (t is None or tp is None) else t - tp
    pts["sprememba"] = bands(abs(dt), (5, 8, 11)) if dt is not None else 0
    det["sprememba"] = (f"povprečje {'+' if dt > 0 else '−'}{seo.num(abs(dt), 0)} °C glede na včeraj"
                        if dt is not None else "model ne vrača podatka")
    a = max(c.vals("apparent_temperature", d, 10, 18), default=None)
    pts["vrocina"] = bands(a, (28, 32, 35))
    det["vrocina"] = f"občutena do {seo.num(a, 0)} °C" if a is not None else "model ne vrača podatka"
    sp, st = storm_pts(c, d, 6, 22)
    pts["nevihta"], det["nevihta"] = (2 if sp else 0), st
    pts["veter"], det["veter"] = wind_pts(c, d, (25, 40, 55), (40, 55, 70), 6, 22)
    rh = mean(c.vals("relative_humidity_2m", d))
    pts["vlaga"] = 0 if rh is None else 2 if rh >= 92 else 1 if (rh >= 85 or rh < 30) else 0
    det["vlaga"] = f"vlaga povprečno {seo.num(rh, 0)} %" if rh is not None else "model ne vrača podatka"
    uv = max(c.vals("uv_index", d, 9, 17), default=None)
    pts["svetloba"] = 0 if uv is None else min(bands(uv, (6, 8, 10)), 2)
    det["svetloba"] = f"UV indeks do {seo.num(uv, 0)}" if uv is not None else "model ne vrača podatka"
    return pts, det


# ── Graf tlaka ───────────────────────────────────────────────────────────────

def pressure_series(c, now):
    """[(čas ISO, tlak)] od -24 h do +72 h glede na celo uro now."""
    arr = c.h.get("pressure_msl") or []
    key = now.strftime("%Y-%m-%dT%H:00")
    try:
        i0 = c.times.index(key)
    except ValueError:
        return [], None
    out = []
    for i in range(max(i0 - 24, 24), min(i0 + 73, len(c.times))):
        if i < len(arr) and arr[i] is not None and arr[i - 24] is not None:
            out.append((c.times[i], arr[i], arr[i - 24]))
    return out, key


def when_text(iso):
    d = datetime.datetime.fromisoformat(iso)
    return f"{D.DAN_KRATKO[d.weekday()]} ob {d.hour}.00"


def pressure_summary(series, now_key):
    """Najstrmejši padec v prihodnjih 72 h in najnižji tlak (besedilo + vrednosti)."""
    fut = [(t, p, p24) for t, p, p24 in series if t >= now_key]
    if not fut:
        return None
    worst = max(fut, key=lambda x: x[2] - x[1])
    low = min(fut, key=lambda x: x[1])
    return {"drop": worst[2] - worst[1], "drop_at": worst[0], "low": low[1], "low_at": low[0]}


def pressure_chart(c, today):
    now = datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    series, now_key = pressure_series(c, now)
    if len(series) < 24:
        return ""
    W, H = 640, 250
    pl, pr, pt, pb = 40, 16, 20, 34
    pw, ph = W - pl - pr, H - pt - pb
    vals = [p for _, p, _ in series]
    lo, hi = min(vals) - 1, max(vals) + 1
    if hi - lo < 10:
        mid = (hi + lo) / 2
        lo, hi = mid - 5, mid + 5
    n = len(series)
    x = lambda i: pl + pw * i / (n - 1)
    y = lambda v: pt + ph * (1 - (v - lo) / (hi - lo))
    out = [f'<svg class="dv-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Zračni tlak od 24 ur nazaj do 72 ur naprej">']
    step = 2 if hi - lo <= 16 else 5
    v = int(lo // step * step + step)
    while v < hi:
        out.append(f'<line x1="{pl}" x2="{pl + pw}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="var(--dv-grid)"/>')
        out.append(f'<text x="{pl - 6}" y="{y(v) + 3:.1f}" text-anchor="end" font-size="10" fill="var(--dv-ink2)">{v}</text>')
        v += step
    # pasovi padca >= DROP_MARK hPa v 24 h
    i = 0
    while i < n:
        if series[i][2] - series[i][1] >= DROP_MARK:
            j = i
            while j + 1 < n and series[j + 1][2] - series[j + 1][1] >= DROP_MARK:
                j += 1
            out.append(f'<rect x="{x(i) - 1:.1f}" y="{pt}" width="{max(x(j) - x(i), 3) + 2:.1f}" height="{ph}" fill="var(--l-2)" opacity=".18"><title>Padec ≥ {DROP_MARK} hPa v 24 h</title></rect>')
            i = j + 1
        else:
            i += 1
    pts_ = " ".join(f"{x(k):.1f},{y(p):.1f}" for k, (_, p, _) in enumerate(series))
    now_i = next((k for k, (t, _, _) in enumerate(series) if t >= now_key), 0)
    out.append(f'<polyline points="{pts_}" fill="none" stroke="var(--g-1)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>')
    out.append(f'<line x1="{x(now_i):.1f}" x2="{x(now_i):.1f}" y1="{pt}" y2="{pt + ph}" stroke="var(--dv-ink)" stroke-dasharray="4 3" opacity=".7"/>')
    out.append(f'<text x="{x(now_i) + 4:.1f}" y="{pt + 10}" font-size="10" fill="var(--dv-ink)">zdaj</text>')
    lo_k = min(range(n), key=lambda k: series[k][1])
    hi_k = max(range(n), key=lambda k: series[k][1])
    for k, lab in ((hi_k, "najvišji"), (lo_k, "najnižji")):
        out.append(f'<circle cx="{x(k):.1f}" cy="{y(series[k][1]):.1f}" r="4" fill="var(--g-1)" stroke="var(--dv-surface)" stroke-width="2"/>')
        out.append(f'<text x="{min(max(x(k), pl + 30), pl + pw - 30):.1f}" y="{y(series[k][1]) + (-9 if lab == "najvišji" else 16):.1f}" text-anchor="middle" '
                   f'font-size="11" font-weight="700" fill="var(--dv-ink)">{seo.num(series[k][1], 0)} hPa</text>')
    for k in range(0, n, 12):
        t = datetime.datetime.fromisoformat(series[k][0])
        out.append(f'<text x="{x(k):.1f}" y="{H - 12}" text-anchor="middle" font-size="10" fill="var(--dv-ink2)">{D.DAN_KRATKO[t.weekday()]} {t.hour}.00</text>')
    out.append("</svg>")
    sm = pressure_summary(series, now_key)
    txt = ""
    if sm:
        if sm["drop"] >= DROP_TH[0]:
            txt = (f"V naslednjih 72 urah tlak najstrmeje pade za {seo.num(sm['drop'], 1)} hPa v 24 urah (do {when_text(sm['drop_at'])}). "
                   f"Najnižji tlak: {seo.num(sm['low'], 0)} hPa ({when_text(sm['low_at'])}).")
        else:
            txt = (f"V naslednjih 72 urah ni izrazitega padca tlaka (največ {seo.num(max(sm['drop'], 0), 1)} hPa v 24 urah). "
                   f"Najnižji tlak: {seo.num(sm['low'], 0)} hPa ({when_text(sm['low_at'])}).")
    return ('  <h2>Zračni tlak: 24 ur nazaj, 72 ur naprej</h2>\n'
            f'  <p class="archive-intro">{esc(txt)} Oranžen pas označuje padec za {DROP_MARK} hPa ali več v 24 urah, ki ga veliko ljudi z migreno omenja kot sprožilec.</p>\n'
            '  <div class="dv-card">' + "".join(out) +
            '\n    <p class="muted-note">Modelska napoved Open-Meteo za Rečico (tlak na morski gladini). Črtkana črta je trenutek izračuna.</p></div>')


# ── Dnevnik in analiza (JS) ──────────────────────────────────────────────────

MIG_ANALYZE_JS = r"""function migAnalyze(hist,attacks){
  function prev(d,n){var t=new Date(d+'T12:00:00Z');t.setUTCDate(t.getUTCDate()-n);return t.toISOString().slice(0,10);}
  function g(d,k){var r=hist[d];return r&&typeof r[k]==='number'?r[k]:null;}
  function diff(d,k,n){var a=g(d,k),b=g(prev(d,n),k);return a==null||b==null?null:a-b;}
  var M=[
   {id:'dP0',label:'Zračni tlak: sprememba glede na prejšnji dan (dan napada)',unit:'hPa',dec:1,f:function(d){return diff(d,'pressureAvg',1);}},
   {id:'dP1',label:'Zračni tlak: sprememba (dan pred napadom)',unit:'hPa',dec:1,f:function(d){return diff(prev(d,1),'pressureAvg',1);}},
   {id:'P',label:'Zračni tlak (dnevno povprečje)',unit:'hPa',dec:0,f:function(d){return g(d,'pressureAvg');}},
   {id:'rP',label:'Dnevno nihanje tlaka',unit:'hPa',dec:1,f:function(d){var a=g(d,'pressureHigh'),b=g(d,'pressureLow');return a==null||b==null?null:a-b;}},
   {id:'dT',label:'Temperatura: sprememba povprečja glede na včeraj',unit:'°C',dec:1,f:function(d){return diff(d,'tempAvg',1);}},
   {id:'T',label:'Povprečna temperatura',unit:'°C',dec:1,f:function(d){return g(d,'tempAvg');}},
   {id:'RH',label:'Povprečna vlaga',unit:'%',dec:0,f:function(d){return g(d,'humidityAvg');}},
   {id:'gust',label:'Največji sunek vetra',unit:'km/h',dec:0,f:function(d){return g(d,'windgustHigh');}},
   {id:'rain',label:'Padavine',unit:'mm',dec:1,f:function(d){return g(d,'precipTotal');}},
   {id:'sun',label:'Največje sončno sevanje',unit:'W/m²',dec:0,f:function(d){return g(d,'solarHigh');}}];
  var seen={},A=[];
  (attacks||[]).forEach(function(d){if(!seen[d]&&hist[d]){seen[d]=1;A.push(d);}});
  A.sort();
  var out={nAttacks:(attacks||[]).length,nUsed:A.length,nBase:0,rows:[],enough:false,from:A[0]||null,to:A[A.length-1]||null};
  if(!A.length)return out;
  var near={};A.forEach(function(d){near[d]=1;near[prev(d,1)]=1;near[prev(d,-1)]=1;});
  var B=[];for(var d=A[0];d<=A[A.length-1];d=prev(d,-1)){if(hist[d]&&!near[d])B.push(d);}
  out.nBase=B.length;
  function mv(x){var a=x.length,m=0,i;for(i=0;i<a;i++)m+=x[i];m/=a;var v=0;for(i=0;i<a;i++)v+=(x[i]-m)*(x[i]-m);return{m:m,v:a>1?v/(a-1):0,n:a};}
  M.forEach(function(m){
    var xa=A.map(m.f).filter(function(v){return v!=null;}),xb=B.map(m.f).filter(function(v){return v!=null;});
    if(xa.length<2||xb.length<2)return;
    var a=mv(xa),b=mv(xb),diff=a.m-b.m,se=Math.sqrt(a.v/a.n+b.v/b.n);
    out.rows.push({id:m.id,label:m.label,unit:m.unit,dec:m.dec,nA:a.n,nB:b.n,meanA:a.m,meanB:b.m,diff:diff,se:se,sig:a.n>=3&&b.n>=3&&Math.abs(diff)>1.96*se});
  });
  function dropDay(d){var a=diff(d,'pressureAvg',1),b=diff(prev(d,1),'pressureAvg',1);var m=null;if(a!=null)m=a;if(b!=null)m=m==null?b:Math.min(m,b);return m;}
  function share(days){var n=0,k=0;days.forEach(function(d){var v=dropDay(d);if(v!=null){n++;if(v<=-4)k++;}});return{n:n,k:k,p:n?k/n:null};}
  out.drop=share(A);out.dropBase=share(B);
  out.enough=A.length>=5&&B.length>=10;
  return out;
}"""

CLIENT_JS = r"""
function $(id){return document.getElementById(id);}
function ymd(d){return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2);}
function nf(v,d){return v==null?'—':v.toFixed(d).replace('.',',').replace('-','−');}
function ls(k,def){try{var v=JSON.parse(localStorage.getItem(k));return v==null?def:v;}catch(e){return def;}}
function sv(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch(e){}}
/* Osebni sprožilci */
var TK='wx-migrena-sprozilci',sel=ls(TK,[]);
function weights(s){var w={};s.forEach(function(k){w[k]=D.weight;});return w;}
function render(){
  var w=weights(sel),cards=document.querySelectorAll('#dv-days .dv-day');
  D.days.forEach(function(d,i){var c=cards[i];if(!c)return;
    var l=dvLevel(d.pts,w,D.th,D.floor,D.floorLevel),sc=dvScore(d.pts,w);
    c.style.setProperty('--c','var(--l-'+l+')');c.querySelector('.dv-lvl').textContent=D.levels[l];
    c.querySelector('.dv-sc').textContent=sc+(sc===1?' točka':sc===2?' točki':(sc===3||sc===4)?' točke':' točk')+(sel.length?' (z mojimi sprožilci)':'');
    var r=Object.keys(d.pts).filter(function(k){return d.pts[k]>0;}).sort(function(a,b){return d.pts[b]*(w[b]||1)-d.pts[a]*(w[a]||1);}).slice(0,2).map(function(k){return d.detail[k];});
    var ul=c.querySelector('ul');ul.textContent='';(r.length?r:['brez izrazitih sprožilcev']).forEach(function(t){var li=document.createElement('li');li.textContent=t;ul.appendChild(li);});
    if(i===0){var h=$('dv-hero');if(h)h.style.setProperty('--c','var(--l-'+l+')');var hl=$('dv-hero-l');if(hl)hl.textContent=D.levels[l];
      var nd=$('dv-needle');if(nd)nd.setAttribute('transform','rotate('+(180*Math.min(sc,D.top)/D.top).toFixed(1)+' 110 110)');}
  });
  var st=$('mig-trig-status');if(st)st.textContent=sel.length?'Uporabljeni sprožilci (štejejo dvojno): '+sel.map(function(k){return D.names[k];}).join(', ')+'.':'Brez osebnih sprožilcev: vsi dejavniki štejejo enako.';
}
var boxes=document.querySelectorAll('#mig-trig input');
boxes.forEach(function(b){b.checked=sel.indexOf(b.value)>=0;});
$('mig-apply').addEventListener('click',function(){sel=[].filter.call(boxes,function(x){return x.checked;}).map(function(x){return x.value;});sv(TK,sel);render();});
$('mig-reset').addEventListener('click',function(){boxes.forEach(function(b){b.checked=false;});sel=[];sv(TK,sel);render();});
render();
/* Dnevnik napadov */
var DK='wx-migrena-dnevnik',diary=ls(DK,[]);
var SEV=['','blag','zmeren','hud'];
function fd(d){var p=d.split('-');return (+p[2])+'. '+(+p[1])+'. '+p[0];}
function saveDiary(){diary.sort(function(a,b){return a.d<b.d?1:-1;});sv(DK,diary);}
function renderDiary(){
  var tb=$('mig-tbody');tb.textContent='';
  diary.forEach(function(e,i){var tr=document.createElement('tr');
    [fd(e.d),SEV[e.s]||'',e.a?'da':'ne',e.n||''].forEach(function(t){var td=document.createElement('td');td.textContent=t;tr.appendChild(td);});
    var td=document.createElement('td'),b=document.createElement('button');b.type='button';b.className='dv-btn';b.textContent='Izbriši';b.setAttribute('aria-label','Izbriši napad '+e.d);
    b.addEventListener('click',function(){diary.splice(i,1);saveDiary();renderDiary();});td.appendChild(b);tr.appendChild(td);tb.appendChild(tr);});
  $('mig-count').textContent=diary.length?('Vnosov v dnevniku: '+diary.length+'.'):'Dnevnik je prazen.';
  $('mig-table').hidden=!diary.length;$('mig-export').disabled=!diary.length;$('mig-clear').disabled=!diary.length;$('mig-analyze').disabled=!diary.length;
}
var di=$('mig-date');di.max=ymd(new Date());di.value=ymd(new Date());
$('mig-add').addEventListener('click',function(){
  var d=di.value;if(!d||d>ymd(new Date())){$('mig-msg').textContent='Izberite datum, ki ni v prihodnosti.';return;}
  var s=+(document.querySelector('#mig-form input[name=sev]:checked')||{value:2}).value;
  diary=diary.filter(function(e){return e.d!==d;});
  diary.push({d:d,s:s,a:$('mig-aura').checked,n:($('mig-note').value||'').slice(0,200)});
  saveDiary();renderDiary();$('mig-note').value='';$('mig-msg').textContent='Napad za '+d+' je shranjen v tem brskalniku.';
});
$('mig-clear').addEventListener('click',function(){if(confirm('Izbrišem celoten dnevnik v tem brskalniku?')){diary=[];saveDiary();renderDiary();$('mig-result').textContent='';}});
function csvCell(v){v=String(v==null?'':v);return /[;"\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}
$('mig-export').addEventListener('click',function(){
  var rows=[['datum','jakost','avra','opomba']].concat(diary.slice().sort(function(a,b){return a.d<b.d?-1:1;}).map(function(e){return [e.d,SEV[e.s],e.a?'da':'ne',e.n];}));
  var blob=new Blob(['﻿'+rows.map(function(r){return r.map(csvCell).join(';');}).join('\r\n')],{type:'text/csv;charset=utf-8'});
  var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='migrena-dnevnik.csv';document.body.appendChild(a);a.click();document.body.removeChild(a);setTimeout(function(){URL.revokeObjectURL(a.href);},1000);
});
/* Analiza */
function pct(p){return p==null?'—':Math.round(p*100)+' %';}
$('mig-analyze').addEventListener('click',function(){
  var out=$('mig-result');out.textContent='Nalagam podatke postaje …';
  fetch('/history.json').then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(h){
    var res=migAnalyze(h,diary.map(function(e){return e.d;}));out.textContent='';
    var p=document.createElement('p');
    if(!res.nUsed){p.textContent='Za vaše datume ni podatkov postaje (zadnji dan v podatkih je včerajšnji).';out.appendChild(p);return;}
    p.textContent='Primerjava '+res.nUsed+' dni napada z '+res.nBase+' ostalimi dnevi med prvim in zadnjim napadom (dnevi neposredno ob napadu so izključeni). Podatki: postaja IREICA1, Rečica ob Savinji.';
    out.appendChild(p);
    var w=document.createElement('p');w.className='muted-note';
    w.textContent=res.enough?'Vzorec je še majhen: razlika je opis vaših napadov, ne dokaz, da je dejavnik vzrok. Označeno »izstopa« pomeni, da je razlika večja od naključnega nihanja.'
      :'Premalo podatkov za zanesljive sklepe (potrebnih je vsaj 5 napadov in 10 primerjalnih dni). Številke so samo opis.';
    out.appendChild(w);
    if(res.drop&&res.drop.n){var q=document.createElement('p');q.innerHTML='';
      q.textContent='Padec tlaka za vsaj 4 hPa (v dnevu napada ali dan prej): pri '+pct(res.drop.p)+' napadov ('+res.drop.k+' od '+res.drop.n+') proti '+pct(res.dropBase.p)+' ostalih dni.';
      out.appendChild(q);}
    var t=document.createElement('table');t.className='stats';var hr=document.createElement('tr');
    ['Dejavnik','Dnevi napada','Ostali dnevi','Razlika',''].forEach(function(x){var th=document.createElement('th');th.textContent=x;hr.appendChild(th);});t.appendChild(hr);
    res.rows.forEach(function(r){var tr=document.createElement('tr');
      [r.label,nf(r.meanA,r.dec)+' '+r.unit,nf(r.meanB,r.dec)+' '+r.unit,(r.diff>0?'+':'')+nf(r.diff,r.dec)+' ± '+nf(1.96*r.se,r.dec),r.sig?'izstopa':''].forEach(function(x,i){var c=document.createElement(i?'td':'th');c.textContent=x;if(i===4&&x)c.style.fontWeight='700';tr.appendChild(c);});t.appendChild(tr);});
    out.appendChild(t);
  }).catch(function(){out.textContent='Podatkov postaje ni bilo mogoče naložiti. Poskusite znova.';});
});
renderDiary();
/* Opozorilo na telefon (Web Push): strežnik shrani samo naslovnico naročnine in prag */
(function(){
  var box=$('mig-alarm');if(!box)return;
  var onB=$('mig-alarm-on'),offB=$('mig-alarm-off'),thr=$('mig-alarm-thr'),msg=$('mig-alarm-msg'),ios=$('mig-alarm-ios'),AK='wx-migrena-alarm';
  var standalone=(window.matchMedia&&matchMedia('(display-mode: standalone)').matches)||navigator.standalone===true;
  var isIOS=/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  var st=ls(AK,null);if(st&&st.thr)thr.value=String(st.thr);
  function say(t){msg.textContent=t||'';}
  function show(){offB.hidden=!st;onB.textContent=st?'Shrani nov prag':'Vklopi opozorilo';say(st?'Opozorilo je vklopljeno (prag '+st.thr+' hPa v 24 urah).':'');}
  if(isIOS&&!standalone){box.hidden=false;ios.hidden=false;onB.disabled=true;return;}
  if(!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window))return;
  box.hidden=false;show();
  function b64(s){var p='='.repeat((4-s.length%4)%4),b=(s+p).replace(/-/g,'+').replace(/_/g,'/'),r=atob(b),o=new Uint8Array(r.length);for(var i=0;i<r.length;i++)o[i]=r.charCodeAt(i);return o;}
  function post(path,body){return fetch(D.api+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j;});});}
  function getSub(){return navigator.serviceWorker.register('/sw.js').then(function(){return navigator.serviceWorker.ready;}).then(function(reg){return reg.pushManager.getSubscription().then(function(sub){return {reg:reg,sub:sub};});});}
  onB.addEventListener('click',function(){
    if(Notification.permission==='denied'){say('Obvestila so za to stran v brskalniku blokirana. Dovolite jih v nastavitvah strani.');return;}
    Notification.requestPermission().then(function(p){
      if(p!=='granted'){say('Brez dovoljenja za obvestila alarm ne more delovati.');return;}
      onB.disabled=true;
      return getSub().then(function(x){if(x.sub)return x.sub;
        return fetch(D.api+'/push/vapid').then(function(r){return r.json();}).then(function(v){return x.reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64(v.publicKey)});});})
      .then(function(sub){return post('/push/subscribe',{site:'migrena',subscription:sub.toJSON(),thr:+thr.value});})
      .then(function(r){st={thr:r.thr};sv(AK,st);show();})
      .catch(function(e){say('Ni uspelo: '+(e&&e.message?e.message:'poskusite znova čez nekaj minut')+'.');})
      .then(function(){onB.disabled=false;});
    });
  });
  offB.addEventListener('click',function(){
    offB.disabled=true;
    getSub().then(function(x){return x.sub?post('/push/unsubscribe',{site:'migrena',endpoint:x.sub.endpoint}):null;})
    .then(function(){st=null;try{localStorage.removeItem(AK);}catch(e){}show();say('Opozorilo je izklopljeno, naslovnica in prag sta izbrisana s strežnika.');})
    .catch(function(e){say('Ni uspelo: '+(e&&e.message?e.message:'poskusite znova')+'.');}).then(function(){offB.disabled=false;});
  });
})();
"""


def client_script(cfg, days):
    payload = {
        "days": [{"pts": d["pts"], "detail": d["detail"]} for d in days],
        "th": list(cfg["th"]), "floor": D.FLOOR_PTS, "floorLevel": D.FLOOR_LEVEL, "levels": cfg["levels"],
        "weight": 2, "top": D.top_of(cfg), "names": TRIGGERS, "api": WORKER_BASE,
    }
    return ("<script>\n(function(){\n" + D.JS_CORE + "\n" + MIG_ANALYZE_JS + "\nvar D=" + json.dumps(payload, ensure_ascii=False) + ";\n"
            + CLIENT_JS + "\n})();\n</script>")


EXTRA_CSS = """<style>
.dv-form{display:grid;gap:.8rem;margin:.6rem 0}
.dv-form input[type=date],.dv-form textarea{min-height:44px;padding:.5rem .7rem;border-radius:8px;border:1px solid var(--dv-grid);background:transparent;color:var(--dv-ink);font:inherit;max-width:100%}
.dv-chipsel{display:flex;flex-wrap:wrap;gap:.5rem}
.dv-chipsel label,.dv-trig label{display:flex;align-items:center;gap:.4rem;padding:.45rem .7rem;border:1px solid var(--dv-grid);border-radius:8px;cursor:pointer;min-height:44px;font-size:.88rem}
.dv-trig{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0}
.dv-trig input,.dv-chipsel input{width:18px;height:18px}
.dv-actions{display:flex;flex-wrap:wrap;gap:.6rem;margin:.4rem 0}
.dv-btn{min-height:44px;padding:.5rem 1rem;border-radius:8px;border:1px solid var(--dv-grid);background:transparent;color:var(--dv-ink);font:inherit;cursor:pointer}
.dv-btn:disabled{opacity:.45;cursor:not-allowed}
.dv-btn-p{background:#2a6fcf;border-color:#2a6fcf;color:#fff;font-weight:700}
.dv-status{font-size:.88rem;color:var(--dv-ink);margin:.4rem 0}
.dv-red{border-left:4px solid var(--l-3);padding:.7rem 1rem;margin:1rem 0;background:color-mix(in srgb,var(--l-3) 10%,transparent);border-radius:0 10px 10px 0;font-size:.9rem}
</style>"""


def trigger_boxes():
    return "".join(f'<label><input type="checkbox" value="{k}"> {esc(v)}</label>' for k, v in TRIGGERS.items())


def sections(cfg, c, days, today):
    chart = pressure_chart(c, today)
    personal = f'''  <h2>Moji sprožilci</h2>
  <p class="archive-intro">Označite, na kaj ste občutljivi, in pritisnite »Uporabi moje sprožilce«. Ti dejavniki bodo v oceni šteli dvojno. Izbira ostane samo v tem brskalniku.</p>
  <div class="dv-trig" id="mig-trig" role="group" aria-label="Moji sprožilci">{trigger_boxes()}</div>
  <div class="dv-actions"><button type="button" class="dv-btn dv-btn-p" id="mig-apply">Uporabi moje sprožilce</button><button type="button" class="dv-btn" id="mig-reset">Ponastavi</button></div>
  <p class="dv-status" id="mig-trig-status" role="status" aria-live="polite">Brez osebnih sprožilcev: vsi dejavniki štejejo enako.</p>'''
    opts = "".join(f'<option value="{v}"{" selected" if v == 5 else ""}>{esc(t)}</option>' for v, t in ALARM_THR)
    alarm = f'''  <div id="mig-alarm" hidden>
  <h2>Opozorilo na telefon ob padcu tlaka</h2>
  <p class="archive-intro">Če vklopite obvestilo, vam javimo, ko model napove padec zračnega tlaka čez izbrani prag v naslednjih 24 urah. Preverja se enkrat na uro, med 22.00 in 7.00 miruje. Vsak padec sporočimo enkrat. Strežnik shrani samo naslovnico naročnine in prag; dnevnika napadov ne vidi.</p>
  <div class="dv-card"><div class="dv-form"><label>Prag <select id="mig-alarm-thr" class="dv-btn">{opts}</select></label>
    <div class="dv-actions"><button type="button" class="dv-btn dv-btn-p" id="mig-alarm-on">Vklopi opozorilo</button><button type="button" class="dv-btn" id="mig-alarm-off" hidden>Izklopi</button></div>
    <p class="dv-status" id="mig-alarm-msg" role="status" aria-live="polite"></p>
    <p class="muted-note" id="mig-alarm-ios" hidden><b>iPhone in iPad:</b> obvestila delujejo samo v nameščeni aplikaciji. V Safariju tapnite »Deli« in »Dodaj na začetni zaslon«, odprite Meteorec z začetnega zaslona in alarm vklopite tam.</p>
    <p class="muted-note">Napoved je modelska (Open-Meteo), ne zdravniški nasvet; alarm ne napove napada.</p></div></div>
  </div>'''
    diary = '''  <h2 id="dnevnik">Moj dnevnik napadov</h2>
  <p class="archive-intro">Vpišite dneve napadov. Dnevnik je <strong>samo v vašem brskalniku</strong> (localStorage): ne gre na strežnik, ne pošilja se nikamor in ga brez vašega izvoza nihče ne vidi. Če izbrišete podatke brskalnika, ga izgubite, zato ga občasno izvozite.</p>
  <div class="dv-card"><form class="dv-form" id="mig-form" onsubmit="return false">
    <label>Datum napada <input type="date" id="mig-date"></label>
    <div class="dv-chipsel" role="radiogroup" aria-label="Jakost napada"><span>Jakost:</span>
      <label><input type="radio" name="sev" value="1"> blag</label><label><input type="radio" name="sev" value="2" checked> zmeren</label><label><input type="radio" name="sev" value="3"> hud</label>
      <label><input type="checkbox" id="mig-aura"> z avro</label></div>
    <label>Opomba (neobvezno, največ 200 znakov) <textarea id="mig-note" maxlength="200" rows="2"></textarea></label>
    <div class="dv-actions"><button type="button" class="dv-btn dv-btn-p" id="mig-add">Dodaj napad</button>
      <button type="button" class="dv-btn" id="mig-export" disabled>Izvozi CSV (za zdravnika)</button>
      <button type="button" class="dv-btn" id="mig-clear" disabled>Počisti dnevnik</button></div>
    <p class="dv-status" id="mig-msg" role="status" aria-live="polite"></p>
  </form>
  <p class="dv-status" id="mig-count">Dnevnik je prazen.</p>
  <div class="table-scroll" tabindex="0"><table class="stats" id="mig-table" hidden><thead><tr><th>Datum</th><th>Jakost</th><th>Avra</th><th>Opomba</th><th></th></tr></thead><tbody id="mig-tbody"></tbody></table></div></div>
  <h2>Ali se moji napadi ujemajo z vremenom?</h2>
  <p class="archive-intro">Primerjava vaših napadov z dnevi brez napada po meritvah postaje IREICA1 v Rečici ob Savinji: sprememba in višina tlaka, temperatura, vlaga, sunki, padavine, sonce. Če živite drugje, so podatki le približek vašega vremena.</p>
  <div class="dv-actions"><button type="button" class="dv-btn dv-btn-p" id="mig-analyze" disabled>Primerjaj moje napade z vremenom</button></div>
  <div id="mig-result" aria-live="polite"></div>'''
    red = ('  <div class="dv-red"><strong>Kdaj nujno k zdravniku (112):</strong> nenaden, izredno hud glavobol (»najhujši v življenju«), '
           'glavobol z oslabelostjo ali motnjami govora in vida, zmedenostjo, krči, vročino s togim tilnikom ali po poškodbi glave. '
           'Tudi če se vaš običajni napad bistveno spremeni, se posvetujte z zdravnikom.</div>')
    return {"after_cards": chart + "\n" + red + "\n" + personal + "\n" + alarm + "\n" + diary}


CFG = {
    "url": "/migrena/", "slug": "migrena", "crumb": "Vreme in migrena",
    "short": "Vreme in migrena", "no_ocene": True,   # ima svoj alarm (padec tlaka), brez splošnega gradnika
    "title": "Vreme in migrena: sprožilci in dnevnik napadov",
    "h1": "Vreme in migrena: napoved sprožilcev in dnevnik napadov",
    "meta": "Tlak, temperatura, nevihte, veter, vlaga in svetloba",
    "kicker": "Migrenski sprožilci danes · Zgornja Savinjska dolina",
    "hero_art": HEAD_ICON,
    "levels": ["nizko", "zmerno", "povišano", "visoko"],
    "advice": [
        "Vreme danes ni izrazit sprožilec. Ravnajte po svojem načrtu zdravljenja.",
        "Nekaj vremenskih sprožilcev; bodite pozorni na prve znake in na svoje navade (spanje, pitje, obroki).",
        "Več vremenskih sprožilcev; če poznate svoje opozorilne znake, ravnajte po načrtu, ki ste ga dogovorili z zdravnikom.",
        "Veliko vremenskih sprožilcev hkrati; ravnajte po svojem načrtu zdravljenja in si po možnosti omogočite mirnejši dan.",
    ],
    "th": (2, 5, 8), "day_fn": day_fn, "hour_fn": None,
    "groups": [("Tlak", "Zračni tlak", ["tlak_pad", "tlak_nizek"]), ("Temperatura", "Temperatura", ["sprememba", "vrocina"]),
               ("Nevihte", "Nevihte in veter", ["nevihta", "veter"]), ("Zrak", "Vlaga in svetloba", ["vlaga", "svetloba"])],
    "group_icons": ["a", "d", "b", "c"],
    "factors": [
        ("tlak_pad", "Padec zračnega tlaka", "Hiter padec tlaka (zlasti ob prehodu fronte) je med najpogosteje omenjenimi vremenskimi sprožilci; dokazi so mešani in osebni."),
        ("tlak_nizek", "Nizek zračni tlak", "Nizek tlak spremlja slabo vreme in fronte; nekateri ljudje se na samo višino tlaka odzovejo."),
        ("sprememba", "Sprememba temperature", "Hiter skok ali padec povprečne temperature glede na včeraj."),
        ("vrocina", "Vročina in soparnost", "Vročina, dehidracija in soparnost so pogosto omenjeni sprožilci."),
        ("nevihta", "Nevihta", "Nevihte (tudi strele in nihanje tlaka) omenjajo nekateri kot sprožilec; nevihta je ocenjena z 2 točkama."),
        ("veter", "Veter", "Močan, suh ali sunkovit veter (npr. jugo, fen) je omenjen kot sprožilec; prikazana je tudi prevladujoča smer."),
        ("vlaga", "Zračna vlaga", "Zelo vlažen (od 85 %) ali zelo suh zrak (pod 30 %) je za nekatere sprožilec."),
        ("svetloba", "Močna svetloba (UV)", "Bleščeča svetloba je znan sprožilec; ocena je omejena na 2 točki."),
    ],
    "rules": [
        ("Padec tlaka", "3 / 5 / 8 hPa v 24 h", "največji padec v dnevu"),
        ("Nizek tlak", "pod 1008 / 1002 / 995 hPa", "dnevno povprečje"),
        ("Sprememba temperature", "±5 / 8 / 11 °C", "povprečje glede na včeraj"),
        ("Vročina", "28 / 32 / 35 °C občutene", "največ 10.–18. ure"),
        ("Nevihta", "napovedana = 2", "koda vremena ≥ 95"),
        ("Veter", "povprečno 25 / 40 / 55 km/h; sunki 40 / 55 / 70 km/h", "6.–22. ure"),
        ("Vlaga", "≥ 85 % ali < 30 % = 1; ≥ 92 % = 2", "dnevno povprečje"),
        ("Svetloba (UV)", "6 / 8 / 10", "največ 2 točki"),
    ],
    "method_intro": "Ocena sešteje točke osmih vremenskih dejavnikov (0–3 na dejavnik, manj je bolje; skupaj največ 24). Raven: do 1 točke nizko, 2–4 zmerno, 5–7 povišano, 8 ali več visoko; izrazit dejavnik (3 točke) da vsaj »povišano«. To je informativni model brez klinične veljave; vsak ima svoje sprožilce, zato jih v razdelku »Moji sprožilci« lahko utežite.",
    "limits": ["<strong>Migrena ima veliko sprožilcev, ki niso vreme:</strong> spanje, stres, obroki, alkohol, hormoni in drugo. Ocena zajema samo vreme.",
               "<strong>Dokazi o vremenu so mešani:</strong> del ljudi vremenske vzorce res zazna, pri drugih povezave ni. Zato je pomemben dnevnik, ne splošna ocena.",
               "<strong>Analiza dnevnika</strong> primerja vaše napade z meritvami postaje v Rečici; majhen vzorec in lega postaje omejujeta zaključke."],
    "intro_q": "Ali vreme sproži migreno?",
    "intro_a": "Veliko ljudi z migreno poroča o sprožilcih, kot so hiter padec zračnega tlaka, nevihte, vročina in močna svetloba; raziskave so mešane in je zelo osebno. Zato stran poleg napovedi ponuja dnevnik, ki pokaže vaš lasten vzorec.",
    "disclaimer_lead": "To ni zdravniški nasvet.",
    "disclaimer": "Ocena prikazuje vremenske sprožilce, ne napoveduje napada in ne nadomešča načrta zdravljenja. Zdravila in ukrepe določa vaš zdravnik.",
    "faq": [
        ("Ali res padec zračnega tlaka sproži migreno?", "Pri nekaterih ljudeh da, pri drugih ne; raziskave so mešane. Stran zato pokaže padce tlaka na grafu in vam v dnevniku omogoči preveriti, ali se ujemajo z vašimi napadi."),
        ("Ali dnevnik napadov gre na strežnik?", "Ne. Dnevnik je samo v vašem brskalniku (localStorage) in ga stran ne pošilja nikamor. Če izbrišete podatke brskalnika, ga izgubite, zato ga izvozite v CSV."),
        ("Kako zanesljiva je analiza mojih napadov?", "Je opis vašega vzorca, ne dokaz. S peščico napadov so razlike lahko naključne; stran označi samo razlike, ki so večje od naključnega nihanja, in pri manj kot 5 napadih sklepov ne trdi."),
        ("Katere podatke uporablja analiza?", "Zunanje meritve postaje IREICA1 v Rečici ob Savinji (tlak, temperatura, vlaga, vetrni sunki, padavine, sonce). Če živite drugje, je vreme pri vas lahko drugačno."),
        ("Kdaj moram takoj k zdravniku?", "Ob nenadnem izredno hudem glavobolu, ob oslabelosti, motnjah govora ali vida, zmedenosti, krčih, vročini s togim tilnikom ali po poškodbi glave pokličite 112. Ob bistveni spremembi običajnih napadov se posvetujte z zdravnikom."),
    ],
    "links": [("/biovreme/", "Biovreme →"), ("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"),
              ("/kakovost-zraka/", "Kakovost zraka →"), ("/astma/", "Vreme in astma →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Migrenski sprožilci danes: {lvl}. Padec tlaka, nevihte, vročina, veter in svetloba za 5 dni, graf tlaka ter dnevnik napadov samo v vašem brskalniku.",
    "sections": sections, "script": client_script,
}


def main():
    # CSS stran doda skupni pogon; dodatni stili za obrazce so v glave strani prek CSS.
    D.CSS = D.CSS + "\n" + EXTRA_CSS
    D.main(CFG)


if __name__ == "__main__":
    main()
