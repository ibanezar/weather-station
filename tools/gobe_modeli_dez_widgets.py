"""
tools/gobe_modeli_dez_widgets.py — interaktivni grafi za članek »Še ena priložnost za gobe? Modeli se ne strinjajo«.

Nadomestijo tri tabele iz članka (tabele ostanejo v zloženem razdelku za bralnike zaslona in iskalnike):

  A  dež po dnevih     — stolpec = mediana, črta = P10–P90; izbira vira (vsi trije ansambli ali posamezen)
  C  posamezni izračuni — naloženi stolpci po modelih (dnevi so barvni odseki), konec napovedi označen
  B  133 napovedi       — ena pika = en član ansambla; drsnik »če pade X mm« obarva pike nad X
  SP vrste              — kartice vrst: prag, okno, delež napovedi nad pragom pri izbrani količini (isti drsnik)

Vse številke pridejo iz iste analize kot besedilo (`generate_gobe_modeli_dez_post.analyse`), v JS ni nobene vtipkane
vrednosti razen barv. Vanilla JS, brez knjižnic; graf se prerisuje ob spremembi širine (telefon).
"""
import json
import statistics as st

POOL_COLOR = "#34d399"
DAY_COLORS = ["#7dd3fc", "#38bdf8", "#0ea5e9", "#0369a1", "#164e63"]

CSS = """<style>
.mz{margin:1.4rem 0 1.8rem;background:var(--card-bg,rgba(10,15,28,.94));border:1px solid var(--card-border,rgba(255,255,255,.11));border-radius:16px;padding:1rem 1rem .9rem}
.mz-h{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.02rem;margin:0 0 .15rem;color:var(--text,#e8ecef)}
.mz-s{font-size:.82rem;color:var(--muted,#adc0d8);margin:0 0 .8rem;line-height:1.5}
.mz-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 .7rem}
.mz-chip{font:600 .78rem 'Inter',system-ui,sans-serif;color:var(--muted,#adc0d8);background:transparent;border:1px solid var(--card-border,rgba(255,255,255,.11));border-radius:999px;padding:.38rem .8rem;cursor:pointer;min-height:36px}
.mz-chip[aria-pressed="true"]{color:#04140e;background:#34d399;border-color:#34d399}
.mz-chip:focus-visible,.mz-range:focus-visible{outline:2px solid #34d399;outline-offset:2px}
.mz-fig{position:relative}
.mz-fig svg{display:block;width:100%;height:auto;overflow:visible}
.mz-fig text{font-family:'Inter',system-ui,sans-serif;fill:var(--muted,#adc0d8)}
.mz-fig .mz-v{fill:var(--text,#e8ecef);font-weight:700}
.mz-fig .mz-grid{stroke:rgba(128,140,160,.22)}
.mz-fig [data-tip]{cursor:pointer}
.mz-tip{position:absolute;pointer-events:none;z-index:3;background:#0b1222;color:#eaf0f7;border:1px solid rgba(255,255,255,.18);border-radius:10px;padding:.45rem .65rem;font-size:.78rem;line-height:1.4;max-width:240px;opacity:0;transition:opacity .12s;box-shadow:0 6px 20px rgba(0,0,0,.35)}
.mz-tip b{color:#fff}
.mz-leg{display:flex;flex-wrap:wrap;gap:.3rem .9rem;font-size:.76rem;color:var(--muted,#adc0d8);margin:.5rem 0 0}
.mz-leg i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:.35rem;vertical-align:-1px}
.mz-slide{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;margin:0 0 .5rem}
.mz-slide label{font-size:.85rem;font-weight:600;color:var(--text,#e8ecef)}
.mz-range{flex:1 1 220px;min-width:180px;accent-color:#34d399;height:34px}
.mz-val{font:800 1.5rem 'Space Grotesk',sans-serif;color:#34d399;min-width:4.6ch;text-align:right}
.mz-sum{font-size:.88rem;color:var(--text,#e8ecef);margin:.2rem 0 .6rem}
.mz-sum b{color:#34d399}
.mz-pre{display:flex;gap:.4rem;flex-wrap:wrap;margin:0 0 .6rem}
.mz-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:.7rem;margin:.4rem 0 0}
.mz-card{border:1px solid var(--card-border,rgba(255,255,255,.11));border-radius:14px;padding:.8rem .85rem;background:rgba(255,255,255,.02);transition:border-color .2s}
.mz-card[data-on="1"]{border-color:#34d399}
.mz-card .n{font:700 1rem 'Space Grotesk',sans-serif;color:var(--text,#e8ecef)}
.mz-card .w{font-size:.78rem;color:var(--muted,#adc0d8);margin:.1rem 0 .55rem}
.mz-bar{height:10px;border-radius:6px;background:rgba(128,140,160,.22);overflow:hidden}
.mz-bar>span{display:block;height:100%;border-radius:6px;background:#e0a63a;transition:width .25s,background .25s}
.mz-card[data-on="1"] .mz-bar>span{background:#34d399}
.mz-card .t{font-size:.78rem;color:var(--muted,#adc0d8);margin-top:.45rem;line-height:1.45}
.mz-card .t b{color:var(--text,#e8ecef)}
.mz-det{margin:.7rem 0 0;font-size:.85rem}
.mz-det summary{cursor:pointer;color:var(--muted,#adc0d8);padding:.3rem 0}
@media(max-width:560px){.mz{padding:.8rem .7rem}.mz-val{font-size:1.25rem}}
</style>"""

JS = r"""
(function(){
var D=JSON.parse(document.getElementById('mz-data').textContent);
var X=D.med, mmf=function(v){return String(Math.round(v));};
var tipEl={};
function tipFor(host){
  if(tipEl[host.id])return tipEl[host.id];
  var t=document.createElement('div');t.className='mz-tip';t.setAttribute('role','status');host.appendChild(t);tipEl[host.id]=t;
  function show(e){
    var n=e.target.closest&&e.target.closest('[data-tip]');
    if(!n||!host.contains(n)){t.style.opacity=0;return;}
    t.innerHTML=n.getAttribute('data-tip');
    var r=host.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
    t.style.opacity=1;
    var w=t.offsetWidth,left=Math.max(4,Math.min(r.width-w-4,x-w/2));
    t.style.left=left+'px';t.style.top=Math.max(0,y-t.offsetHeight-14)+'px';
  }
  host.addEventListener('pointermove',show);host.addEventListener('pointerdown',show);
  host.addEventListener('pointerleave',function(){t.style.opacity=0;});
  return t;
}
function W(host){return Math.max(280,host.clientWidth||600);}
function ticks(max,step){var a=[];for(var v=0;v<=max;v+=step)a.push(v);return a;}

/* ---------- A: dež po dnevih ---------- */
var aKey='pool';
function srcA(k){return k==='pool'?{lab:'vsi trije ansambli',col:D.poolCol,pd:D.pool}:(function(){var e=D.ens.filter(function(x){return x.id===k})[0];return {lab:e.lab,col:e.col,pd:e.perday};})();}
function drawA(){
  var host=document.getElementById('mz-a'),w=W(host),narrow=w<520,h=narrow?290:330;
  var m={l:narrow?34:42,r:10,t:26,b:46},s=srcA(aKey),n=D.days.length,pw=w-m.l-m.r,ph=h-m.t-m.b,mx=40;
  var Y=function(v){return m.t+ph*(1-Math.min(v,mx)/mx);},sl=pw/n,fs=narrow?11:12.5;
  var o='<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="Dež po dnevih od torka do sobote: '+s.lab+', mediana in razpon P10–P90">';
  ticks(mx,10).forEach(function(v){o+='<line class="mz-grid" x1="'+m.l+'" x2="'+(w-m.r)+'" y1="'+Y(v)+'" y2="'+Y(v)+'"/><text x="'+(m.l-6)+'" y="'+(Y(v)+4)+'" text-anchor="end" font-size="'+fs+'">'+v+'</text>';});
  o+='<text x="'+m.l+'" y="14" font-size="'+fs+'">mm na dan</text>';
  D.days.forEach(function(d,i){
    var cx=m.l+sl*(i+.5),p=s.pd[i],bw=Math.min(58,sl*.52);
    if(d.dry){o+='<rect x="'+(m.l+sl*i+3)+'" y="'+m.t+'" width="'+(sl-6)+'" height="'+ph+'" rx="10" fill="rgba(125,211,252,.07)"/><text x="'+cx+'" y="'+(m.t+14)+'" text-anchor="middle" font-size="'+(fs-1)+'">skoraj suho</text>';}
    o+='<text x="'+cx+'" y="'+(h-m.b+20)+'" text-anchor="middle" font-size="'+fs+'">'+d.lab+'</text>';
    if(!p){o+='<text x="'+cx+'" y="'+(Y(0)-8)+'" text-anchor="middle" font-size="'+(fs-1)+'">ni napovedi</text><rect x="'+(cx-bw/2)+'" y="'+m.t+'" width="'+bw+'" height="'+ph+'" fill="transparent" data-tip="<b>'+d.long+'</b><br>'+s.lab+' do tja ne sega."/>';return;}
    var tip='<b>'+d.long+'</b><br>'+s.lab+'<br>mediana <b>'+mmf(p.med)+' mm</b><br>P10–P90: '+mmf(p.p10)+'–'+mmf(p.p90)+' mm';
    var bh=Math.max(2,Y(0)-Y(p.med));
    o+='<g data-tip="'+tip+'"><rect x="'+(cx-bw/2)+'" y="'+Y(p.med)+'" width="'+bw+'" height="'+bh+'" rx="7" fill="'+s.col+'" fill-opacity="'+(d.dry?.55:.95)+'"/>'
      +'<line x1="'+cx+'" x2="'+cx+'" y1="'+Y(p.p90)+'" y2="'+Y(p.p10)+'" stroke="var(--text,#e8ecef)" stroke-width="2.4" stroke-linecap="round"/>'
      +'<line x1="'+(cx-9)+'" x2="'+(cx+9)+'" y1="'+Y(p.p90)+'" y2="'+Y(p.p90)+'" stroke="var(--text,#e8ecef)" stroke-width="2.4" stroke-linecap="round"/>'
      +'<text class="mz-v" x="'+cx+'" y="'+(Y(Math.max(p.med,p.p90))-8)+'" text-anchor="middle" font-size="'+(narrow?13:15)+'">'+mmf(p.med)+'</text>'
      +'<rect x="'+(cx-sl/2+4)+'" y="'+m.t+'" width="'+(sl-8)+'" height="'+ph+'" fill="transparent"/></g>';
  });
  o+='</svg>';
  document.getElementById('mz-a-fig').innerHTML=o;
  document.getElementById('mz-a-note').textContent=s.lab+': stolpec je mediana, črta razpon od 10. do 90. percentila članov.';
}
function chipsA(){
  var h=document.getElementById('mz-a-chips'),items=[{id:'pool',lab:'Vsi trije do sobote'}].concat(D.ens.map(function(e){return {id:e.id,lab:e.lab};}));
  h.innerHTML='';items.forEach(function(it){var b=document.createElement('button');b.type='button';b.className='mz-chip';b.textContent=it.lab;b.setAttribute('aria-pressed',it.id===aKey);
    b.onclick=function(){aKey=it.id;Array.prototype.forEach.call(h.children,function(c){c.setAttribute('aria-pressed',c===b);});drawA();};h.appendChild(b);});
}

/* ---------- C: posamezni izračuni ---------- */
function drawC(){
  var host=document.getElementById('mz-c'),w=W(host),narrow=w<520,rh=narrow?30:34,gap=narrow?10:12;
  var m={l:narrow?92:150,r:narrow?40:52,t:8,b:30},rows=D.det,h=m.t+rows.length*(rh+gap)+m.b,mx=D.detMax,pw=w-m.l-m.r;
  var X0=function(v){return m.l+pw*v/mx;},fs=narrow?11:12.5;
  var o='<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="Dež po dnevih za vsak model, naloženi stolpci">';
  ticks(mx,20).forEach(function(v){o+='<line class="mz-grid" x1="'+X0(v)+'" x2="'+X0(v)+'" y1="'+m.t+'" y2="'+(h-m.b)+'"/><text x="'+X0(v)+'" y="'+(h-m.b+18)+'" text-anchor="middle" font-size="'+fs+'">'+v+' mm</text>';});
  rows.forEach(function(r,i){
    var y=m.t+i*(rh+gap),acc=0;
    o+='<text x="'+(m.l-8)+'" y="'+(y+rh/2+4)+'" text-anchor="end" font-size="'+fs+'" style="fill:var(--text,#e8ecef)">'+(narrow?r.short:r.lab)+'</text>';
    var any=false;
    r.days.forEach(function(v,k){
      if(v===null||v<=0){return;}
      any=true;var x=X0(acc),wd=X0(acc+v)-x;
      o+='<rect data-tip="<b>'+r.lab+'</b><br>'+D.days[k].long+': <b>'+mmf(v)+' mm</b>" x="'+x+'" y="'+y+'" width="'+Math.max(wd,1.5)+'" height="'+rh+'" fill="'+D.dayCol[k]+'" stroke="var(--card-bg,rgba(10,15,28,.94))" stroke-width="1.5" rx="3"/>';
      acc+=v;
    });
    if(r.full){o+='<text class="mz-v" x="'+(X0(acc)+7)+'" y="'+(y+rh/2+5)+'" font-size="'+(fs+1)+'">'+mmf(acc)+'</text>';}
    else{
      var txt=any?'do '+r.last:(r.last?'do '+r.last:'ni podatkov');
      o+='<g data-tip="<b>'+r.lab+'</b><br>Napoved sega do '+r.lastLong+'.<br>Dnevi po tem so prazni, ne suhi."><line x1="'+(X0(acc)+4)+'" x2="'+(X0(acc)+4)+'" y1="'+(y+3)+'" y2="'+(y+rh-3)+'" stroke="var(--muted,#adc0d8)" stroke-width="2" stroke-dasharray="3 3"/>'
        +'<text x="'+(X0(acc)+10)+'" y="'+(y+rh/2+4)+'" font-size="'+(fs-1)+'">'+txt+'</text></g>';
    }
  });
  o+='</svg>';
  document.getElementById('mz-c-fig').innerHTML=o;
}

/* ---------- B: 133 napovedi ---------- */
function drawB(){
  var host=document.getElementById('mz-b'),w=W(host),narrow=w<520,rh=narrow?66:78,r=narrow?3.3:4.4;
  var m={l:narrow?64:112,r:12,t:22,b:30},h=m.t+D.dots.length*rh+m.b,mx=D.dotMax,pw=w-m.l-m.r,fs=narrow?11:12.5;
  var Xs=function(v){return m.l+pw*Math.min(v,mx)/mx;};
  var o='<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="Skupna količina dežja 20. do 24. oktobra, ena pika je en član ansambla">';
  ticks(mx,20).forEach(function(v){o+='<line class="mz-grid" x1="'+Xs(v)+'" x2="'+Xs(v)+'" y1="'+m.t+'" y2="'+(h-m.b)+'"/><text x="'+Xs(v)+'" y="'+(h-m.b+18)+'" text-anchor="middle" font-size="'+fs+'">'+v+' mm</text>';});
  D.species.forEach(function(s){o+='<path d="M'+Xs(s.thr)+','+(m.t-2)+' l-5,-9 l10,0 z" fill="#e0a63a" data-tip="<b>'+s.name+'</b><br>sprožilni prag '+mmf(s.thr)+' mm"/>';});
  D.dots.forEach(function(e,i){
    var cy=m.t+rh*(i+.5),placed=[];
    o+='<text x="'+(m.l-8)+'" y="'+(cy+4)+'" text-anchor="end" font-size="'+fs+'" style="fill:var(--text,#e8ecef)">'+(narrow?e.short:e.lab)+'</text>';
    e.tot.forEach(function(v){
      var x=Xs(v),k=0,y=cy,ok=false;
      while(!ok&&k<60){var off=((k+1)>>1)*(2*r+.6)*(k%2?1:-1);y=cy+(k===0?0:off);ok=placed.every(function(p){var dx=p[0]-x,dy=p[1]-y;return dx*dx+dy*dy>=(2*r+.4)*(2*r+.4);});k++;}
      placed.push([x,y]);
      var on=v>=X;
      o+='<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+e.col+'" fill-opacity="'+(on?.95:.22)+'" data-tip="'+e.lab+': <b>'+mmf(v)+' mm</b>"/>';
    });
  });
  o+='<line x1="'+Xs(X)+'" x2="'+Xs(X)+'" y1="'+(m.t-2)+'" y2="'+(h-m.b)+'" stroke="#34d399" stroke-width="2.5"/><text class="mz-v" x="'+Math.min(w-m.r-30,Math.max(m.l+20,Xs(X)))+'" y="'+(h-m.b+18+13)+'" text-anchor="middle" font-size="'+(fs+1)+'" style="fill:#34d399">'+mmf(X)+' mm</text>';
  o+='</svg>';
  document.getElementById('mz-b-fig').innerHTML=o;
}
function shareGE(v){var n=0,t=0;D.dots.forEach(function(e){e.tot.forEach(function(x){t++;if(x>=v)n++;});});return {n:n,t:t};}

/* ---------- SP: vrste ---------- */
function drawSP(){
  var h=document.getElementById('mz-sp-cards'),o='';
  D.species.forEach(function(s){
    var sh=shareGE(s.thr),on=X>=s.thr,pct=Math.round(100*Math.min(X/s.thr,1));
    o+='<div class="mz-card" data-on="'+(on?1:0)+'"><div class="n">'+s.name+'</div><div class="w">okno '+s.win+' · zamik '+s.lag[0]+'–'+s.lag[1]+' dni</div>'
      +'<div class="mz-bar" role="img" aria-label="'+s.name+': '+pct+' % praga"><span style="width:'+pct+'%"></span></div>'
      +'<div class="t">prag <b>'+mmf(s.thr)+' mm</b> · pri '+mmf(X)+' mm <b>'+(on?'polna ocena dežja':pct+' % ocene')+'</b><br>prag preseže '+sh.n+' od '+sh.t+' napovedi (<b>'+Math.round(100*sh.n/sh.t)+' %</b>)</div></div>';
  });
  h.innerHTML=o;
}
function sums(){
  var s=shareGE(X);
  Array.prototype.forEach.call(document.querySelectorAll('.mz-sum-x'),function(e){e.innerHTML='Vsaj <b>'+mmf(X)+' mm</b> do sobote napoveduje <b>'+s.n+' od '+s.t+'</b> članov ('+Math.round(100*s.n/s.t)+' %).';});
  Array.prototype.forEach.call(document.querySelectorAll('.mz-val'),function(e){e.textContent=mmf(X)+' mm';});
  Array.prototype.forEach.call(document.querySelectorAll('.mz-range'),function(e){e.value=X;});
}
function setX(v){X=Math.max(0,Math.min(D.sliderMax,+v));sums();drawB();drawSP();}
function wireSliders(){
  Array.prototype.forEach.call(document.querySelectorAll('.mz-range'),function(e){e.max=D.sliderMax;e.addEventListener('input',function(){setX(e.value);});});
  Array.prototype.forEach.call(document.querySelectorAll('.mz-pre'),function(h){
    D.presets.forEach(function(p){var b=document.createElement('button');b.type='button';b.className='mz-chip';b.textContent=p.lab;b.onclick=function(){setX(p.v);};h.appendChild(b);});});
}
function all(){drawA();drawC();drawB();drawSP();}
['mz-a','mz-b','mz-c'].forEach(function(id){tipFor(document.getElementById(id));});
chipsA();wireSliders();sums();all();
var rt;window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(function(){drawA();drawC();drawB();},120);});
})();
"""


def _stat(v):
    v = sorted(v)
    n = len(v)

    def q(p):
        k = (n - 1) * p
        lo = int(k)
        hi = min(lo + 1, n - 1)
        return v[lo] + (v[hi] - v[lo]) * (k - lo)
    return {"med": round(st.median(v), 2), "p10": round(q(.1), 2), "p90": round(q(.9), 2)}


def data_json(S, A, days, wd, until, lab_short, species):
    """species: [(id, ime, okno besedilo)] po začetku okna."""
    ev = days
    pool_pd = []
    for dd in ev:
        pool_pd.append(_stat([x[dd] for m in A["full_ens"] for x in S["ens"][m]["members"]]))
    dlab = []
    for dd, p in zip(ev, pool_pd):
        dlab.append({"d": dd, "lab": f"{wd(dd)[:3]} {int(dd[8:])}. {int(dd[5:7])}.",
                     "long": f"{wd(dd)}, {int(dd[8:])}. {int(dd[5:7])}.", "dry": p["med"] < 1.5})
    ens = []
    for m, lab, n, col in ens_def(A):
        e = A["ens"][m]
        ens.append({"id": m, "lab": lab, "col": col, "perday": [None if e["perday"][dd] is None else
                    {k: round(e["perday"][dd][k], 2) for k in ("med", "p10", "p90")} for dd in ev]})
    dots = [{"lab": A["ens"][m]["lab"], "short": A["ens"][m]["lab"].replace("ECMWF ", "").replace(" ENS", ""),
             "col": A["ens"][m]["col"], "tot": [round(x, 1) for x in A["ens"][m]["tot"]]} for m in A["full_ens"]]
    det = []
    for m, d in A["det"].items():
        if m == "icon_d2":
            vals = [None] * len(ev)
        else:
            vals = [None if d["days"][dd] is None else round(d["days"][dd], 1) for dd in ev]
        last = d["last"]
        det.append({"id": m, "lab": d["lab"].replace(" (umetna inteligenca)", " (AI)"), "short": lab_short(m), "days": vals, "full": d["full"],
                    "last": None if d["full"] else until(last).replace(" ob ", " ob ").replace(". uri", ". uri"),
                    "lastLong": None if d["full"] else until(last)})
    det.sort(key=lambda r: (not r["full"], -(sum(v or 0 for v in r["days"]))))
    med = round(st.median(A["pool"]), 1)
    return {
        "days": dlab, "pool": pool_pd, "poolCol": POOL_COLOR, "ens": [e for e in ens if A["ens"][e["id"]]["perday"][ev[0]] is not None],
        "dots": dots, "dotMax": 100, "det": det, "detMax": 70, "dayCol": DAY_COLORS,
        "species": [{"id": sid, "name": name, "lag": A["sp"][sid]["lag"], "win": win, "thr": round(A["sp"][sid]["thr"], 1)}
                    for sid, name, win in species],
        "med": round(med), "sliderMax": 70,
        "presets": [{"lab": f"P10 · {round(_stat(A['pool'])['p10'])} mm", "v": round(_stat(A['pool'])['p10'])},
                    {"lab": f"mediana · {round(med)} mm", "v": round(med)},
                    {"lab": f"P90 · {round(_stat(A['pool'])['p90'])} mm", "v": round(_stat(A['pool'])['p90'])}],
    }


def ens_def(A):
    return [(m, A["ens"][m]["lab"], A["ens"][m]["n"], A["ens"][m]["col"]) for m in A["ens"]]


def _slider(label_id):
    return ('<div class="mz-slide"><label for="%s">Če pade skupaj</label>'
            '<input class="mz-range" id="%s" type="range" min="0" max="70" step="1" value="27" aria-label="Količina dežja v milimetrih">'
            '<span class="mz-val" aria-live="polite"></span></div>' % (label_id, label_id))


def widget_a():
    return ('<div class="mz"><h3 class="mz-h">Dež po dnevih: kdaj in koliko</h3>'
            '<p class="mz-s">Izberite vir. Stolpec je mediana članov, črta razpon od 10. do 90. percentila. Dotaknite se stolpca za številke.</p>'
            '<div class="mz-chips" id="mz-a-chips" role="group" aria-label="Izbira ansambla"></div>'
            '<div class="mz-fig" id="mz-a"><div id="mz-a-fig"></div></div><p class="mz-s" id="mz-a-note" style="margin:.5rem 0 0"></p></div>')


def widget_c():
    leg = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for c, n in zip(DAY_COLORS, ["torek", "sreda", "četrtek", "petek", "sobota"]))
    return ('<div class="mz"><h3 class="mz-h">Posamezni izračuni: skupaj in po dnevih</h3>'
            '<p class="mz-s">En izračun vsakega modela. Barvni odseki so dnevi, številka je vsota do sobote. Črtkana črta pomeni, da napoved tam preneha: naprej dnevi niso suhi, ampak prazni.</p>'
            f'<div class="mz-fig" id="mz-c"><div id="mz-c-fig"></div></div><div class="mz-leg" aria-hidden="true">{leg}</div></div>')


def widget_b():
    return ('<div class="mz"><h3 class="mz-h">133 napovedi, ena pika za vsako</h3>'
            '<p class="mz-s">Vsaka pika je en član ansambla: skupna količina dežja 20.–24. oktobra. Premaknite drsnik in poglejte, koliko napovedi doseže izbrano količino. '
            'Rumeni trikotniki na vrhu so sprožilni pragovi vrst.</p>' + _slider("mz-r1") +
            '<div class="mz-pre"></div><p class="mz-sum mz-sum-x"></p>'
            '<div class="mz-fig" id="mz-b"><div id="mz-b-fig"></div></div></div>')


def widget_sp(data):
    return ('<div class="mz"><h3 class="mz-h">Katera vrsta pri kateri količini</h3>'
            '<p class="mz-s">Kartice sledijo istemu drsniku. Pod pragom model dež šteje sorazmerno, nad njim je ocena polna. To je samo sprožilni dež, ne indeks vrste.</p>' + _slider("mz-r2") +
            '<div class="mz-pre"></div><p class="mz-sum mz-sum-x"></p><div class="mz-cards" id="mz-sp-cards"></div></div>'
            '<script type="application/json" id="mz-data">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + '</script>'
            + CSS + '<script>' + JS + '</script>')


def details(summary, table_html):
    return f'<details class="mz-det"><summary>{summary}</summary>{table_html}</details>'
