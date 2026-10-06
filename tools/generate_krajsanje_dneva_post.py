#!/usr/bin/env python3
"""
tools/generate_krajsanje_dneva_post.py — članek »Krajšanje dneva« z interaktivnimi grafi.

Ročno zasnovan članek (ne dnevni samodejni): dolžino dneva, sončni vzhod in zahod za
Rečico ob Savinji izračuna Python (NOAA približek, ±2 min, ravno obzorje), v stran
vgradi vse vrednosti kot JSON, JS pa jih samo izriše (kazalec, razponi, tipkovnica).
Tako ima besedilo in graf ENE izračun — dveh kopij formule ni.

Drugi graf postavi dolžino dneva ob bok izmerjeni povprečni dnevni temperaturi postaje
IREICA1 (history.json, samo zunanja temperatura) in pokaže, da toplota zaostaja za
soncem. Notranjih meritev ni nikjer (CLAUDE.md, pravilo na vrhu).

Lektura je trenutno izklopljena (CLAUDE.md) — besedilo je treba prebrati ročno.

Usage:
    python3 tools/generate_krajsanje_dneva_post.py [--dry-run] [--wire]
"""
import datetime
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import generate_forecast_test_post as ftp  # noqa: E402
from generate_seo_pages import num  # noqa: E402

ROOT = seo.ROOT
LAT, LON = 46.325779, 14.921137  # IREICA1
TZ = ZoneInfo("Europe/Ljubljana")
YEAR = 2026
SLUG = "krajsanje-dneva-recica-ob-savinji-1005"
DNEVI = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]


def sun_minutes(d):
    """(vzhod, zahod) v minutah lokalnega časa; zenit 90,833° (refrakcija + sončni disk)."""
    n = d.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    la = math.radians(LAT)
    c = (math.cos(math.radians(90.833)) - math.sin(la) * math.sin(decl)) / (math.cos(la) * math.cos(decl))
    ha = math.degrees(math.acos(c))
    off = TZ.utcoffset(datetime.datetime(d.year, d.month, d.day, 12)).total_seconds() / 60
    return 720 - 4 * (LON + ha) - eqt + off, 720 - 4 * (LON - ha) - eqt + off


def hm(m):
    m = round(m)
    return f"{m // 60}:{m % 60:02d}"


def ur_min(m):
    m = round(m)
    return f"{m // 60} h {m % 60:02d} min"


def short(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def yearly_series():
    days = [datetime.date(YEAR, 1, 1) + datetime.timedelta(i) for i in range(365)]
    prev = sun_minutes(days[0] - datetime.timedelta(1))
    rise, sett, dur = [], [], []
    for d in days:
        r, s = sun_minutes(d)
        rise.append(r)
        sett.append(s)
        dur.append(s - r)
    pd = prev[1] - prev[0]
    dd = [round(dur[0] - pd, 3)] + [round(dur[i] - dur[i - 1], 3) for i in range(1, 365)]
    d7 = [round(dur[i] - (dur[i - 7] if i >= 7 else dur[0] - 7 * dd[0]), 2) for i in range(365)]
    return days, rise, sett, dur, dd, d7


def temp_climatology(days):
    """Povprečje tempAvg po koledarskem dnevu čez vsa leta meritev, zglajeno s 31-dnevnim
    krožnim drsečim povprečjem. 29. februar izpuščen (tabela ima 365 dni)."""
    hist = seo.load_history()
    acc = {}
    for iso, v in hist.items():
        if v.get("src") not in (None, "station") or v.get("tempAvg") is None:
            continue
        key = iso[5:]
        if key == "02-29":
            continue
        acc.setdefault(key, []).append(v["tempAvg"])
    raw, cnt = [], []
    for d in days:
        vals = acc.get(f"{d.month:02d}-{d.day:02d}", [])
        raw.append(sum(vals) / len(vals) if vals else None)
        cnt.append(len(vals))
    if any(x is None for x in raw):
        raise SystemExit("history.json nima vseh koledarskih dni — brez grafa temperature.")
    sm = []
    for i in range(365):
        w = [raw[(i + k) % 365] for k in range(-15, 16)]
        sm.append(round(sum(w) / len(w), 2))
    years = sorted({iso[:4] for iso in hist})
    return sm, min(cnt), years[0], years[-1]


def build_data():
    days, rise, sett, dur, dd, d7 = yearly_series()
    temp, min_n, y0, y1 = temp_climatology(days)
    iso = [d.isoformat() for d in days]
    # prehoda ur: zadnja nedelja marca in oktobra
    dst = []
    for i in range(1, 365):
        a = TZ.utcoffset(datetime.datetime.combine(days[i - 1], datetime.time(12)))
        b = TZ.utcoffset(datetime.datetime.combine(days[i], datetime.time(12)))
        if a != b:
            dst.append(i)
    return {
        "n": 365, "dates": iso,
        "rise_m": [round(x, 2) for x in rise], "set_m": [round(x, 2) for x in sett],
        "dur_m": [round(x, 2) for x in dur], "d": dd, "d7": d7, "temp": temp,
        "dst": dst, "today": iso.index(os.environ.get("POST_DATE") or datetime.date.today().isoformat()),
        "temp_years": [y0, y1], "temp_min_n": min_n,
    }


def facts(D):
    iso, dur, rise, sett, dd = D["dates"], D["dur_m"], D["rise_m"], D["set_m"], D["d"]
    t = D["today"]
    # Solsticija: dolžina dneva ob njih je ravna (razlike pod sekundo), zato argmax skače za dan —
    # vzamemo koledarska datuma astronomskih solsticijev 2026 (21. 6. in 21. 12.).
    i_sol_s = iso.index(f"{YEAR}-06-21")
    i_sol_w = iso.index(f"{YEAR}-12-21")
    f = {"t": t, "today": iso[t], "dur_today": dur[t], "rise_today": rise[t], "set_today": sett[t],
         "d_today": dd[t], "d7_today": D["d7"][t],
         "sum_max": dur[i_sol_s], "sum_i": i_sol_s, "win_min": dur[i_sol_w], "win_i": i_sol_w,
         "left": dur[t] - dur[i_sol_w], "lost": dur[i_sol_s] - dur[t]}
    # najhitrejše krajšanje (jeseni), najhitrejše daljšanje (spomladi)
    f["fast_i"] = min(range(365), key=lambda i: dd[i])
    f["fast"] = dd[f["fast_i"]]
    f["grow_i"] = max(range(365), key=lambda i: dd[i])
    f["grow"] = dd[f["grow_i"]]
    f["eq_i"] = min(range(365), key=lambda i: abs(dur[i] - 720))
    f["eq2_i"] = max(range(365), key=lambda i: -abs(dur[i] - 720) if i > 200 else -1e9)
    f["eq_aut"] = min(range(200, 365), key=lambda i: abs(dur[i] - 720))
    f["eq_spr"] = min(range(0, 200), key=lambda i: abs(dur[i] - 720))
    # prvi dan pod mejo (po današnjem)
    def below(h):
        for i in range(t, 365):
            if dur[i] < h * 60:
                return i
    f["b10"], f["b9"] = below(10), below(9)
    # najzgodnejši zahod / najpoznejši vzhod: vrednosti brez skoka ure
    # najzgodnejši zahod gledamo šele po prehodu na zimski čas
    f["early_set_i"] = min(range(D["dst"][1], 365), key=lambda i: sett[i])
    f["late_rise_i"] = max(range(D["dst"][1], 365), key=lambda i: rise[i])
    # oktober: vzhod in zahod 1. 10. in 24. 10. (pred prehodom ure)
    a = iso.index(f"{YEAR}-10-01")
    b = D["dst"][1] - 1
    f["oct_a"], f["oct_b"] = a, b
    # zahod ob prehodu
    f["dst_set_before"], f["dst_set_after"] = sett[D["dst"][1] - 1], sett[D["dst"][1]]
    f["dst_rise_before"], f["dst_rise_after"] = rise[D["dst"][1] - 1], rise[D["dst"][1]]
    # temperatura
    tmp = D["temp"]
    f["tmax_i"] = tmp.index(max(tmp))
    f["tmin_i"] = tmp.index(min(tmp))
    f["tmax"], f["tmin"] = max(tmp), min(tmp)
    f["lag_hot"] = f["tmax_i"] - i_sol_s
    f["lag_cold"] = f["tmin_i"] + 365 - i_sol_w
    f["d_sol_s"], f["d_sol_w"] = abs(dd[i_sol_s]), abs(dd[i_sol_w])
    f["i_nov1"], f["i_dec1"] = iso.index(f"{YEAR}-11-01"), iso.index(f"{YEAR}-12-01")
    f["i_nov5"] = iso.index(f"{YEAR}-11-05")
    f["t_now"], f["t_nov"], f["t_dec"] = tmp[t], tmp[f["i_nov5"]], tmp[f["i_dec1"]]
    f["i_dec1_tmp"] = f["i_dec1"]
    # povprečne mesečne temperature (polni meseci, vsa leta)
    hist = seo.load_history()
    mm = {}
    for k, v in hist.items():
        if v.get("tempAvg") is not None and v.get("src") in (None, "station"):
            mm.setdefault((k[:4], int(k[5:7])), []).append(v["tempAvg"])
    per = {}
    for (y, mo), vals in mm.items():
        if len(vals) >= 27:
            per.setdefault(mo, []).append(sum(vals) / len(vals))
    f["mon"] = {mo: sum(v) / len(v) for mo, v in per.items() if len(v) >= 4}
    return f


def weekly_table(D, f):
    iso, dur, rise, sett = D["dates"], D["dur_m"], D["rise_m"], D["set_m"]
    rows = []
    idxs = list(range(f["t"], f["win_i"], 7)) + [f["win_i"]]
    prev = None
    for i in idxs:
        week = f"{dur[i] - dur[prev]:+.0f}".replace("-", "−") if prev is not None else "—"
        mark = " (najkrajši dan)" if i == f["win_i"] else ""
        rows.append(f"<tr><td>{short(iso[i])}{mark}</td><td>{hm(rise[i])}</td><td>{hm(sett[i])}</td>"
                    f"<td>{ur_min(dur[i])}</td><td>{week}</td></tr>")
        prev = i
    return ('<div class="table-scroll" tabindex="0"><table class="data-table"><thead><tr>'
            '<th>Datum</th><th>Vzhod</th><th>Zahod</th><th>Dolžina dneva</th><th>Sprememba od prejšnje vrstice (min)</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')


CSS = """<style>
.dn-fig{margin:1rem 0 1.8rem}
.dn-fig .dn-ctl{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.8rem}
.dn-fig .dn-ctl button{font:inherit;font-size:.82rem;color:var(--text);background:transparent;border:1px solid var(--card-border);border-radius:999px;padding:.35rem .85rem;cursor:pointer}
.dn-fig .dn-ctl button[aria-pressed="true"]{background:rgba(57,135,229,.22);border-color:#3987e5}
.dn-fig .dn-ctl button:focus-visible,.dn-fig .dn-plot:focus-visible{outline:2px solid #3987e5;outline-offset:2px}
.dn-fig .dn-ro{font-size:.92rem;line-height:1.55;min-height:3.2em;margin:.2rem 0 .6rem}
.dn-fig .dn-plot{touch-action:pan-y;outline-offset:4px;border-radius:8px}
.dn-fig svg{display:block;width:100%;height:auto;user-select:none;-webkit-user-select:none}
.dn-fig .dn-hint{color:var(--muted);font-size:.8rem;margin-top:.4rem}
.dn-fig details{margin-top:.6rem;color:var(--muted);font-size:.85rem}
</style>"""

JS = r"""<script>
(function(){
var D=JSON.parse(document.getElementById('dan-data').textContent);
var DN=['ned','pon','tor','sre','čet','pet','sob'];
var MS=['jan','feb','mar','apr','maj','jun','jul','avg','sep','okt','nov','dec'];
var BLUE='#3987e5',GREEN='#059669',PURPLE='#a855f7',ORANGE='#d95926',INK='#e8edf8',MUTED='#adc0d8',SURF='#0a0f1c';
function dobj(i){var p=D.dates[i].split('-');return new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));}
function dl(i){var d=dobj(i);return DN[d.getUTCDay()]+', '+d.getUTCDate()+'. '+(d.getUTCMonth()+1)+'.';}
function hm(m){m=Math.round(m);return Math.floor(m/60)+':'+('0'+m%60).slice(-2);}
function du(m){m=Math.round(m);return Math.floor(m/60)+' h '+('0'+m%60).slice(-2)+' min';}
function sg(x,d){var a=Math.abs(x).toFixed(d).replace('.',',');return (x>0.04?'+':x<-0.04?'−':'±')+a;}
function f1(x){return x.toFixed(1).replace('.',',');}
function monthStarts(a,b){var r=[];for(var i=a;i<=b;i++){var d=dobj(i);if(d.getUTCDate()===1)r.push([i,MS[d.getUTCMonth()]]);}return r;}

function Fig(el,cfg){
  var plot=el.querySelector('.dn-plot'),ro=el.querySelector('.dn-ro');
  var rng=cfg.ranges?cfg.ranges[0][1]:[0,D.n-1],cur=D.today,W=0,geo=null,svg=null;
  function build(){
    W=Math.max(300,Math.min(780,plot.clientWidth||600));
    var L=40,R=12,top=6,x0=rng[0],x1=rng[1],y=top,ps=[];
    cfg.panels.forEach(function(p){
      var ty=y,py=y+22,ph=p.h;
      ps.push({p:p,ty:ty,py:py,ph:ph});y=py+ph+22;
    });
    var H=y+2;
    function X(i){return L+(i-x0)/(x1-x0)*(W-L-R);}
    geo={L:L,R:R,X:X,x0:x0,x1:x1,ps:ps,H:H};
    var s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+cfg.label+'" font-family="inherit">';
    var ms=monthStarts(x0,x1);
    ps.forEach(function(q,pi){
      var p=q.p;
      function Y(v){return q.py+q.ph-(v-p.y0)/(p.y1-p.y0)*q.ph;}
      q.Y=Y;
      s+='<text x="'+L+'" y="'+(q.ty+12)+'" font-size="12" fill="'+MUTED+'">'+p.title+'</text>';
      var lx=W-R;
      for(var k=p.series.length-1;k>=0&&p.series.length>1;k--){
        var se=p.series[k];lx-=se.name.length*6.6+22;
        s+='<rect x="'+lx+'" y="'+(q.ty+4)+'" width="12" height="3" fill="'+se.c+'"/><text x="'+(lx+16)+'" y="'+(q.ty+12)+'" font-size="12" fill="'+MUTED+'">'+se.name+'</text>';
      }
      p.ticks.forEach(function(t){
        var yy=Y(t);
        s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+yy+'" y2="'+yy+'" stroke="rgba(255,255,255,'+(t===0&&p.zero?'.35':'.10')+')"/>';
        s+='<text x="'+(L-6)+'" y="'+(yy+4)+'" text-anchor="end" font-size="12" fill="'+MUTED+'">'+(p.tf?p.tf(t):t)+'</text>';
      });
      ms.forEach(function(m){
        var xx=X(m[0]);
        s+='<line x1="'+xx+'" x2="'+xx+'" y1="'+(q.py+q.ph)+'" y2="'+(q.py+q.ph+4)+'" stroke="rgba(255,255,255,.25)"/>';
        if(pi===ps.length-1&&(x1-x0>200||m[1]!=='jan'||true))s+='<text x="'+(xx+3)+'" y="'+(q.py+q.ph+16)+'" font-size="12" fill="'+MUTED+'">'+m[1]+'</text>';
      });
      (cfg.vlines||[]).forEach(function(v){
        if(v.i<x0||v.i>x1||(v.panels&&v.panels.indexOf(pi)<0))return;
        var xx=X(v.i);
        s+='<line x1="'+xx+'" x2="'+xx+'" y1="'+q.py+'" y2="'+(q.py+q.ph)+'" stroke="'+v.c+'" stroke-dasharray="4 3" stroke-width="1.2"/>';
        if(v.label&&pi===v.labelPanel)s+='<text x="'+(xx+(v.anchor==='end'?-4:4))+'" y="'+(v.pos==='bottom'?q.py+q.ph-8:v.pos==='mid'?q.py+q.ph/2+4:q.py+14)+'" text-anchor="'+(v.anchor||'start')+'" font-size="12" fill="'+INK+'">'+v.label+'</text>';
      });
      if(p.zero===false){}
      p.series.forEach(function(se){
        var d='',pen=false;
        for(var i=x0;i<=x1;i++){
          if(se.brk&&D.dst.indexOf(i)>=0)pen=false;
          d+=(pen?'L':'M')+X(i).toFixed(1)+' '+Y(se.v(i)).toFixed(1);pen=true;
        }
        if(p.area){
          var z=Y(0);
          s+='<path d="'+d+'L'+X(x1).toFixed(1)+' '+z+'L'+X(x0).toFixed(1)+' '+z+'Z" fill="'+se.c+'" fill-opacity=".16" stroke="none"/>';
        }
        s+='<path d="'+d+'" fill="none" stroke="'+se.c+'" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
      });
      if(D.today>=x0&&D.today<=x1)s+='<circle cx="'+X(D.today)+'" cy="'+Y(p.series[0].v(D.today))+'" r="3" fill="none" stroke="'+INK+'" stroke-width="1.2"/>';
    });
    if(D.today>=x0&&D.today<=x1){var lp=ps[ps.length-1];s+='<text x="'+X(D.today)+'" y="'+(lp.py+lp.ph+30)+'" text-anchor="middle" font-size="12" fill="'+INK+'">danes</text>';}
    s+='<g class="cur"></g></svg>';
    plot.innerHTML=s;svg=plot.querySelector('svg');
    place(cur);
  }
  function place(i){
    i=Math.max(rng[0],Math.min(rng[1],Math.round(i)));cur=i;
    var g=svg.querySelector('.cur'),s='',a=geo.ps[0],b=geo.ps[geo.ps.length-1],xx=geo.X(i);
    s+='<line x1="'+xx+'" x2="'+xx+'" y1="'+a.py+'" y2="'+(b.py+b.ph)+'" stroke="rgba(255,255,255,.6)" stroke-width="1"/>';
    geo.ps.forEach(function(q){q.p.series.forEach(function(se){
      s+='<circle cx="'+xx+'" cy="'+q.Y(se.v(i))+'" r="4.5" fill="'+se.c+'" stroke="'+SURF+'" stroke-width="2"/>';
    });});
    g.innerHTML=s;
    ro.innerHTML=cfg.readout(i);
  }
  function fromEvent(e){
    var r=svg.getBoundingClientRect(),px=(e.clientX-r.left)*(W/r.width);
    return geo.x0+(px-geo.L)/(W-geo.L-geo.R)*(geo.x1-geo.x0);
  }
  var down=false;
  plot.addEventListener('pointerdown',function(e){down=true;place(fromEvent(e));});
  plot.addEventListener('pointermove',function(e){if(e.pointerType==='mouse'||down)place(fromEvent(e));});
  window.addEventListener('pointerup',function(){down=false;});
  plot.addEventListener('keydown',function(e){
    var k=e.key,st={ArrowLeft:-1,ArrowRight:1,PageDown:-7,PageUp:7}[k];
    if(st){place(cur+st);e.preventDefault();}
    else if(k==='Home'){place(rng[0]);e.preventDefault();}
    else if(k==='End'){place(rng[1]);e.preventDefault();}
  });
  var btns=el.querySelectorAll('.dn-ctl button');
  Array.prototype.forEach.call(btns,function(b){
    b.addEventListener('click',function(){
      if(b.dataset.r==='today'){place(D.today);return;}
      var r=cfg.ranges[+b.dataset.r][1];rng=r;
      Array.prototype.forEach.call(btns,function(x){if(x.dataset.r!=='today')x.setAttribute('aria-pressed',x===b?'true':'false');});
      build();
    });
  });
  var rt;window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(function(){if(Math.abs((plot.clientWidth||0)-W)>2)build();},120);});
  build();
}

var T=D.today;
var f1el=document.getElementById('dn-fig1');
if(f1el)Fig(f1el,{
  label:'Dolžina dneva, sprememba po dnevih ter sončni vzhod in zahod v Rečici ob Savinji v letu 2026',
  ranges:[['Celo leto',[0,D.n-1]],['Jesen in zima',[243,D.n-1]]],
  vlines:[{i:D.dst[0],c:MUTED,label:'poletni čas',labelPanel:2,pos:'mid',panels:[2]},{i:D.dst[1],c:MUTED,label:'zimski čas',labelPanel:2,pos:'mid',anchor:'end',panels:[2]}],
  panels:[
    {title:'Dolžina dneva (ure)',h:120,y0:8,y1:16.5,ticks:[8,10,12,14,16],series:[{c:BLUE,name:'dolžina dneva',v:function(i){return D.dur_m[i]/60;}}]},
    {title:'Sprememba glede na prejšnji dan (min)',h:100,y0:-3.4,y1:3.4,ticks:[-3,-2,-1,0,1,2,3],zero:true,area:true,tf:function(t){return t>0?'+'+t:(t<0?'−'+(-t):t);},series:[{c:BLUE,name:'sprememba',v:function(i){return D.d[i];}}]},
    {title:'Sončni vzhod in zahod (lokalni čas)',h:130,y0:4,y1:21.5,ticks:[4,8,12,16,20],tf:function(t){return t+':00';},series:[{c:GREEN,name:'vzhod',brk:true,v:function(i){return D.rise_m[i]/60;}},{c:PURPLE,name:'zahod',brk:true,v:function(i){return D.set_m[i]/60;}}]}
  ],
  readout:function(i){
    var s='<b>'+dl(i)+'</b>'+(i===T?' (danes)':'')+' · vzhod <b>'+hm(D.rise_m[i])+'</b> · zahod <b>'+hm(D.set_m[i])+'</b> · dan <b>'+du(D.dur_m[i])+'</b><br>'+
      '<b>'+sg(D.d[i],1)+' min</b> glede na prejšnji dan, <b>'+sg(D.d7[i],0)+' min</b> glede na teden prej';
    if(D.dst.indexOf(i)>=0)s+=' · <i>ta dan se ura premakne ('+(D.dst[0]===i?'poletni':'zimski')+' čas)</i>';
    return s;
  }
});

var f2el=document.getElementById('dn-fig2');
if(f2el)Fig(f2el,{
  label:'Dolžina dneva in povprečna dnevna temperatura postaje IREICA1 skozi leto',
  vlines:[{i:D.sol_s,c:BLUE,label:"najdaljši dan",labelPanel:0,anchor:"end",pos:"bottom"},{i:D.sol_w,c:BLUE,label:"najkrajši dan",labelPanel:0,anchor:"end"},{i:D.tmin_i,c:ORANGE,label:"najhladneje",labelPanel:1}],
  panels:[
    {title:'Dolžina dneva (ure)',h:100,y0:8,y1:16.5,ticks:[8,10,12,14,16],series:[{c:BLUE,name:'dolžina dneva',v:function(i){return D.dur_m[i]/60;}}]},
    {title:'Tipična povprečna dnevna temperatura (°C)',h:100,y0:-2,y1:22,ticks:[0,5,10,15,20],zero:true,series:[{c:ORANGE,name:'temperatura',v:function(i){return D.temp[i];}}]}
  ],
  readout:function(i){
    return '<b>'+dl(i)+'</b> · dan <b>'+du(D.dur_m[i])+'</b> · tipična povprečna temperatura <b>'+f1(D.temp[i])+' °C</b>';
  }
});
})();
</script>"""


def fig_html(fid, ctl, hint, table_html=""):
    return (f'<div class="chart-card dn-fig" id="{fid}">{ctl}<div class="dn-ro" role="status"></div>'
            f'<div class="dn-plot" tabindex="0" role="group" aria-label="Graf. Puščici levo in desno premakneta '
            f'kazalec za en dan, PageUp in PageDown za teden."></div>'
            f'<p class="dn-hint">{hint}</p>{table_html}</div>')


def build_article(D, f):
    iso = D["dates"]
    t = f["t"]
    dst_f = D["dst"][1]
    d_today = -f["d_today"]
    lost = f["lost"]
    left = f["left"]
    lead = (f"Danes, 5. oktobra, je dan v Rečici ob Savinji dolg {ur_min(f['dur_today'])}: sonce vzide ob "
            f"{hm(f['rise_today'])}, zaide ob {hm(f['set_today'])}. Vsak dan je krajši za približno "
            f"{num(d_today)} minute, do zimskega solsticija pa bomo izgubili še {ur_min(left)}. "
            f"Krajšanje ni enakomerno — in spodnji grafi to pokažejo, ko z miško (ali prstom) potujete po letu.")

    fig1_ctl = ('<div class="dn-ctl"><button type="button" data-r="0" aria-pressed="true">Celo leto</button>'
                '<button type="button" data-r="1" aria-pressed="false">Jesen in zima</button>'
                '<button type="button" data-r="today">Danes</button></div>')
    fig1 = fig_html("dn-fig1", fig1_ctl,
                    "Premaknite kazalec po grafu ali ga izberite s tipkami ← → (PageUp/PageDown: teden). "
                    "Vrednosti so izračunane za koordinate postaje IREICA1.")
    fig2 = fig_html("dn-fig2", "",
                    "Temperatura je povprečje dnevnih povprečij postaje IREICA1 za isti koledarski dan "
                    f"v letih {D['temp_years'][0]}–{D['temp_years'][1]}, zglajeno s 31-dnevnim drsečim povprečjem.")

    fast_i, grow_i = f["fast_i"], f["grow_i"]
    sec1 = [
        fig1,
        f"Od najdaljšega dne, {short(iso[f['sum_i']])}, ko je bil dan dolg {ur_min(f['sum_max'])}, je do danes "
        f"minilo {ur_min(lost)} dnevne svetlobe. Do najkrajšega dne, {short(iso[f['win_i']])}, ko bo dan dolg samo "
        f"{ur_min(f['win_min'])}, jih bo odpadlo še {ur_min(left)}. Skupaj je torej razlika med poletjem in zimo "
        f"{ur_min(f['sum_max'] - f['win_min'])}.",
        f"Pod mejo 10 ur pade dan {short(iso[f['b10']])}, pod mejo 9 ur pa {short(iso[f['b9']])}",
    ]
    sec2 = [
        f"Srednji graf kaže, da je krajšanje najhitrejše okoli jesenskega enakonočja: največ je {num(-f['fast'])} min "
        f"na dan ({short(iso[fast_i])}). Spomladi je zrcalna slika, najhitrejše daljšanje je {num(f['grow'])} min na dan "
        f"({short(iso[grow_i])}). Ob solsticijih se dolžina dneva skoraj ne spreminja: {short(iso[f['sum_i']])} je sprememba "
        f"{num(f['d_sol_s'], 2)} min, {short(iso[f['win_i']])} pa {num(f['d_sol_w'], 2)} min na dan.",
        "Vzrok je geometrija. Okoli enakonočja sonce seka obzorje pod največjim kotom, hkrati pa se njegova "
        "deklinacija iz dneva v dan spreminja najhitreje, zato se vzhod in zahod vsak dan premakneta za največ. Ob "
        "solsticiju je deklinacija skoraj mirna, zato se dolžina dneva komaj spremeni.",
        f"Najhitrejše krajšanje smo torej že prestali. Danes izgubimo {num(d_today)} min na dan, 1. novembra "
        f"{num(-D['d'][f['i_nov1']])} min, 1. decembra {num(-D['d'][f['i_dec1']])} min, ob zimskem solsticiju pa skoraj nič.",
    ]
    ei = f["early_set_i"]
    li = f["late_rise_i"]
    a, b = f["oct_a"], f["oct_b"]
    sec3 = [
        f"Dan se skrajša na dveh koncih. Med {short(iso[a])} in {short(iso[b])} (pred menjavo ure) se vzhod pomakne "
        f"z {hm(D['rise_m'][a])} na {hm(D['rise_m'][b])}, zahod pa z {hm(D['set_m'][a])} na {hm(D['set_m'][b])}. "
        f"Jutra so torej temnejša za {round(D['rise_m'][b] - D['rise_m'][a])} min, večeri za "
        f"{round(D['set_m'][a] - D['set_m'][b])} min.",
        f"Potem pride menjava ure. V noči na {short(iso[dst_f])} se ura pomakne nazaj: sonce zaide že ob "
        f"{hm(f['dst_set_after'])} namesto ob {hm(f['dst_set_before'])}, vzide pa ob {hm(f['dst_rise_after'])} namesto "
        f"ob {hm(f['dst_rise_before'])}. Dan sam se zaradi tega ne skrajša — samo prestavi se, večer dobi eno uro manj, "
        f"jutro eno uro več svetlobe.",
        f"Najkrajši dan ni dan z najzgodnejšim zahodom. Najzgodneje sonce zaide okoli {short(iso[ei])} "
        f"(ob {hm(D['set_m'][ei])}), najpozneje pa vzide šele okoli {short(iso[li])} (ob {hm(D['rise_m'][li])}), "
        f"torej več kot teden dni pred oziroma po zimskem solsticiju. Vzrok je razlika med pravim sončnim časom in uro: "
        f"pravi opoldan se te tedne iz dneva v dan pomika pozneje po uri, zato se zahod začne zamikati nazaj, še preden "
        f"se dan neha krajšati, vzhod pa še zamuja, ko se dan že daljša.",
    ]
    sec4 = [
        "Tabela navaja vsak teden do zimskega solsticija (ure v lokalnem času, upoštevan je prehod na zimski čas).",
        weekly_table(D, f),
    ]
    sec5 = [
        fig2,
        f"Najdaljši dan je {short(iso[f['sum_i']])}, najtoplejši mesec pa je julij: po meritvah postaje ima povprečno "
        f"{num(f['mon'][7])} °C, junij {num(f['mon'][6])} °C, avgust {num(f['mon'][8])} °C. Najkrajši dan je "
        f"{short(iso[f['win_i']])}, najhladnejši mesec pa januar ({num(f['mon'][1])} °C; december {num(f['mon'][12])} °C, "
        f"februar {num(f['mon'][2])} °C). Najhladnejši dan tipičnega poteka je {short(iso[f['tmin_i']])}, "
        f"{f['lag_cold']} dni po solsticiju.",
        f"Zaostanek je običajen: zemlja in zrak se segrevata in ohlajata počasi, zato temperatura sledi sončnemu "
        f"obsevanju z zamikom nekaj tednov. Zdaj pomeni: tipična povprečna dnevna temperatura pade s {num(f['t_now'])} °C "
        f"5. oktobra na {num(f['t_nov'])} °C 5. novembra in {num(f['t_dec'])} °C 1. decembra — ohlajanje se "
        f"torej nadaljuje, čeprav se dan krajša vse počasneje.",
    ]
    sec6 = [
        "Sončni vzhod in zahod sta izračunana po poenostavljenem astronomskem modelu (NOAA) za koordinate postaje "
        f"IREICA1 ({num(LAT, 4)} °N, {num(LON, 4)} °E), z upoštevano refrakcijo in navideznim premerom sonca (zenitni kot "
        "90,833°). Napaka je do približno dveh minut. Uradni podatki (ARSO, Astronomsko društvo) se lahko razlikujejo za minuto ali dve.",
        "Račun predpostavlja ravno obzorje. Rečica leži v ozki dolini, zato sonce dejansko vzide pozneje in zaide prej "
        "(na dnu doline pogosto za več deset minut, odvisno od pobočij) — dolžina dneva, ki jo čutite na vrtu, "
        "je torej krajša od astronomske, spremembe po dnevih pa so enake.",
        "Temperaturna krivulja je iz meritev postaje IREICA1 (zunanja temperatura) in ima samo nekaj let podatkov, "
        "zato je to tipični potek v zadnjih letih, ne dolgoletna klimatološka norma; poletni vrh je na krivulji ploščat in nanj vplivajo posamezni vročinski valovi.",
    ]
    data_script = (f'<div><script type="application/json" id="dan-data">{json.dumps(dict(D, sol_s=f["sum_i"], sol_w=f["win_i"], tmin_i=f["tmin_i"]), ensure_ascii=False, separators=(",", ":"))}</script>'
                   f'{CSS}{JS}</div>')
    sec6.append(data_script)

    return {
        "title": "Krajšanje dneva: koliko minut izgubimo vsak dan",
        "meta_description": (f"Danes je dan v Rečici ob Savinji dolg {ur_min(f['dur_today'])} in se krajša za "
                             f"{num(d_today)} min na dan. Interaktivni grafi: vzhod, zahod, dolžina dneva in temperatura."),
        "tags": ["analiza", "oktober", "2026", "sonce", "dolžina dneva"],
        "section_label": "Analiza",
        "og_photo": "weather-station",
        "og_accent_hex": "#f59e0b",
        "lead": lead,
        "sections": [
            {"label": "01 — dolžina dneva", "heading": "Kako hitro nam dan uhaja", "id": "dolzina", "paragraphs": sec1},
            {"label": "02 — hitrost", "heading": "Zakaj krajšanje ni enakomerno", "id": "hitrost", "paragraphs": sec2},
            {"label": "03 — vzhod in zahod", "heading": "Jutra in večeri, menjava ure", "id": "vzhod-zahod", "paragraphs": sec3},
            {"label": "04 — do solsticija", "heading": "Teden za tednom do najkrajšega dne", "id": "tabela", "paragraphs": sec4},
            {"label": "05 — temperatura", "heading": "Toplota zaostaja za soncem", "id": "temperatura", "paragraphs": sec5},
            {"label": "06 — metodologija", "heading": "Od kod številke in kaj ne drži povsem", "id": "metodologija", "paragraphs": sec6},
        ],
        "callout": None,
        "sources_note": "Vir: astronomski izračun za koordinate postaje IREICA1, meritve postaje IREICA1 (Meteorec), history.json.",
    }


def main():
    dry = "--dry-run" in sys.argv
    wire = "--wire" in sys.argv
    D = build_data()
    f = facts(D)
    article = build_article(D, f)
    if dry:
        print(json.dumps({k: (v if not isinstance(v, float) else round(v, 2)) for k, v in f.items()}, ensure_ascii=False))
        for s in article["sections"]:
            print("\n##", s["heading"])
            for p in s["paragraphs"]:
                if not p.lstrip().startswith("<"):
                    print(p)
        print("\nLEAD:", article["lead"])
        return
    ftp.TODAY = D["dates"][D["today"]]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Krajšanje dneva", meta_note="analiza",
        nav_label="O postaji", nav_href="/o-postaji.html")
    with open(os.path.join(ROOT, "blog", f"{slug}.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
