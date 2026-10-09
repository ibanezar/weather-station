#!/usr/bin/env python3
"""
tools/generate_gobe_po_dezju_post.py — članek »Gobe po dežju 8.–10. oktobra«.

Ročno zasnovan članek (ne dnevni samodejni), nadaljevanje članka o dežu
(generate_dez_oktober_post.py). Vse številke so izračunane ob zagonu:

  * gobarski model (`gobe_model`): indeks po skupinah in območjih, pragovi sprožilnega dežja
    po vrstah in dnevne padavine Open-Meteo po območjih (ISTI zagon, ki ga vidi tudi stran
    /gobarska-napoved/ — ne drug zajem),
  * ansambel in ARSO iz že objavljenega članka o dežu (JSON, vdelan v stran), da imata oba
    članka ISTE številke.

Članek je POSNETEK ob uri zajema — stran to pove. Notranjih meritev ni nikjer (CLAUDE.md, pravilo
na vrhu). Lektura je izklopljena (CLAUDE.md) — besedilo je treba prebrati ročno.

Usage:
    python3 tools/generate_gobe_po_dezju_post.py [--dry-run] [--wire] [--cache FILE]

`--cache FILE`: zagon modela se shrani v FILE (pickle) in naslednjič prebere od tam — Open-Meteo
ob več zaporednih zagonih vrne 429.
"""
import collections
import datetime
import json
import os
import pickle
import re
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import generate_forecast_test_post as ftp  # noqa: E402
import generate_dez_oktober_post as dz  # noqa: E402  (CSS/JS ogrodje interaktivnih grafov)
import gobe_model as gm  # noqa: E402
from generate_seo_pages import num  # noqa: E402

ROOT = seo.ROOT
YEAR = 2026
SLUG = "gobe-po-dezju-8-10-oktobra-kdaj-in-kje-1007"
RAIN_SLUG = "dez-8-9-oktobra-koliko-ga-bo-padlo-1007"
ECO_ORDER = ["razkrojevalka", "lesna", "mikorizna"]
# Barve skupin: slot 1–3 validirane kategorične palete na temni podlagi bloga (#0a0f1c),
# validate_palette.js --mode dark: vsi testi PASS (CVD ΔE 9,4; normalni vid 26,5).
COLORS = {"razkrojevalka": "#3987e5", "lesna": "#d95926", "mikorizna": "#199e70"}
SHORT = {"macrolepiota_procera": "Marela", "pleurotus_ostreatus": "Bukov ostrigar",
         "auricularia_auricula_judae": "Bezgova uhljevka", "hydnum_repandum": "Rumeni ježek",
         "boletus_edulis": "Jurček", "cantharellus_cibarius": "Lisička"}
ECO_NAME = {"razkrojevalka": "Razkrojevalke", "lesna": "Lesne vrste", "mikorizna": "Mikorizne vrste"}
# Vrste, ki jih članek omenja po imenu: (id v species_rules.yaml, skupina je iz modela).
SHOW = ["macrolepiota_procera", "pleurotus_ostreatus", "auricularia_auricula_judae",
        "hydnum_repandum", "boletus_edulis", "cantharellus_cibarius"]
BANDS = [("do 499 m", 0, 500), ("500–799 m", 500, 800), ("800–1099 m", 800, 1100), ("od 1100 m", 1100, 9999)]


def short(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def rng(a, b):
    """»8.–10. 10.« (isti mesec) ali »30. 9.–2. 10.«."""
    da, db = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    if da.month == db.month:
        return f"{da.day}.–{db.day}. {db.month}."
    return f"{da.day}. {da.month}.–{db.day}. {db.month}."


def add_days(iso, n):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=n)).isoformat()


def mm(x):
    return num(x)


def thr_s(x):
    return str(int(x)) if float(x).is_integer() else num(x)


def load_rain_article():
    """Ansambel in ARSO iz objavljenega članka o dežu (JSON med skripto `dez-data`)."""
    path = os.path.join(ROOT, "blog", f"{RAIN_SLUG}.html")
    with open(path, encoding="utf-8") as fh:
        m = re.search(r'id="dez-data">(.*?)</script>', fh.read(), re.S)
    if not m:
        raise SystemExit(f"✗ v {path} ni bloka dez-data")
    return json.loads(m.group(1))


def run_model(cache):
    if cache and os.path.exists(cache):
        with open(cache, "rb") as fh:
            return pickle.load(fh)
    rules = gm.load_rules()
    spots, protected = gm.load_locations(rules)
    locs = gm.fetch_forecast(spots, gm.past_days_needed(rules))
    premium = gm.compute_forecast(rules, spots, locs, gm.load_station_precip(), protected)
    out = (spots, locs, premium)
    if cache:
        with open(cache, "wb") as fh:
            pickle.dump(out, fh)
    return out


def group_mean(loc, day_i, eco, meta):
    v = [s["index"] for s in loc["days"][day_i]["species"] if meta[s["id"]]["ecology"] == eco]
    return st.mean(v)


def build_data(cache):
    R = load_rain_article()
    spots, locs, P = run_model(cache)
    meta = P["species_meta"]
    L = P["locations"]
    home = next(l for l in L if l.get("home"))
    dates = [d["date"] for d in home["days"]]
    ev = R["ev"]
    rain_days = ev["days"]  # 8., 9., 10. 10.
    d1, d3 = rain_days[0], rain_days[-1]

    # dnevne padavine modela v Rečici (isti klic Open-Meteo kot indeks)
    raw = {s["name"]: l for s, l in zip(spots, locs)}
    hd = raw[home["name"]]["daily"]
    hrain = dict(zip(hd["time"], hd["precipitation_sum"]))
    model_mm = round(sum(hrain.get(d) or 0 for d in rain_days), 1)
    extra_day = add_days(d3, 1)
    extra_mm = round(hrain.get(extra_day) or 0, 1)

    # skupine: zamik, vrhovi v Rečici
    eco = {}
    for e in ECO_ORDER:
        sp_ids = [i for i, m in meta.items() if m["ecology"] == e]
        # Skupinski zamik = najpogostejši; posamezna vrsta ima lahko ročno umerjen drug zamik (lisička 4–14).
        lag = collections.Counter(tuple(meta[i]["lag_days"]) for i in sp_ids).most_common(1)[0][0]
        lag = list(lag)
        means = [group_mean(home, i, e, meta) for i in range(len(dates))]
        peak_i = max(range(len(dates)), key=lambda i: means[i])
        best_i = max(range(len(dates)),
                     key=lambda i: max(s["index"] for s in home["days"][i]["species"]
                                       if meta[s["id"]]["ecology"] == e))
        best = max((s for s in home["days"][best_i]["species"] if meta[s["id"]]["ecology"] == e),
                   key=lambda s: s["index"])
        eco[e] = {"lag": lag, "n": len(sp_ids),
                  "win": (add_days(d1, lag[0]), add_days(d3, lag[1])),
                  "mean_now": round(means[0]), "peak_mean": round(means[peak_i]), "peak_date": dates[peak_i],
                  "best": best["index"], "best_date": dates[best_i], "best_name": meta[best["id"]]["name_sl"],
                  "last_mean": round(means[-1]), "means": [round(m, 1) for m in means]}

    # pragovi sprožilnega dežja po vrstah (iz razlage modela: »… 51.7/40 mm …«)
    thr = {}
    for day in home["days"]:
        for s in day["species"]:
            m = re.search(r"/(\d+(?:\.\d+)?) mm", s["explanation"])
            if m and s["id"] not in thr:
                thr[s["id"]] = float(m.group(1))
    totals = sorted(ev["totals"])
    n = len(totals)
    species_rows = []
    for sid in SHOW:
        if sid not in thr:
            raise SystemExit(f"✗ ni praga za {sid}")
        t = thr[sid]
        species_rows.append({"id": sid, "name": meta[sid]["name_sl"], "eco": meta[sid]["ecology"],
                             "lag": meta[sid]["lag_days"], "thr": t,
                             "share": round(100 * sum(1 for v in totals if v >= t) / n)})

    # višinski pasovi: povprečje skupin ob vrhu lesnih vrst
    dkey = [eco["lesna"]["peak_date"], add_days(eco["lesna"]["peak_date"], -1)]
    di = [dates.index(d) for d in dkey if d in dates]
    bands = []
    for name, lo, hi in BANDS:
        ls = [l for l in L if lo <= l["elev_m"] < hi]
        bands.append({"name": name, "n": len(ls),
                      **{e: round(st.mean(group_mean(l, i, e, meta) for l in ls for i in di)) for e in ECO_ORDER},
                      "series": {e: [round(st.mean(group_mean(l, i, e, meta) for l in ls)) for i in range(len(dates))]
                                 for e in ECO_ORDER}})

    # območja po dežju modela
    tot = {}
    for s, l in zip(spots, locs):
        d = l["daily"]
        p = dict(zip(d["time"], d["precipitation_sum"]))
        tot[s["name"]] = round(sum(p.get(x) or 0 for x in rain_days), 1)

    def names(items):
        seen, out = set(), []
        for name, v in items:
            base = name.split(" – ")[0].split(" / ")[0]
            if base not in seen:
                seen.add(base)
                out.append((base, v))
        return out

    ranked = sorted(tot.items(), key=lambda kv: -kv[1])
    wet = names(ranked)[:4]
    dry = names(list(reversed(ranked)))[:3]

    best_i = dates.index(eco["lesna"]["peak_date"])
    high = sum(1 for l in L if l["days"][best_i]["overall"] >= 80)
    return {"R": R, "P": P, "home": home, "dates": dates, "today": dates[0], "ev": ev,
            "d1": d1, "d3": d3, "model_mm": model_mm, "extra_day": extra_day, "extra_mm": extra_mm,
            "eco": eco, "species": species_rows, "bands": bands, "wet": wet, "dry": dry,
            "n_loc": len(L), "n_high": high, "high_date": eco["lesna"]["peak_date"],
            "prot": P.get("protected_areas", []), "meta": meta,
            "soil_now": home["days"][0]["soil_moisture_pct"], "model_version": P.get("model_version", "")}


def table(head, rows, wrap=True):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    t = f'<table class="data-table"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'
    return f'<div class="table-scroll" tabindex="0">{t}</div>' if wrap else t


def verdict(rain, thr):
    r = rain / thr
    if r < 0.85:
        return "pod pragom"
    if r <= 1.15:
        return "na meji"
    return "nad pragom"


def payload(D):
    """Vsi podatki za grafe — besedilo in grafi imajo ENE izračun."""
    eco, ev = D["eco"], D["ev"]
    dates = D["dates"]
    end = max(eco[e]["win"][1] for e in ECO_ORDER)
    span, d = [], dates[0]
    while d <= add_days(end, 1):
        span.append(d)
        d = add_days(d, 1)
    thr_max = max(r["thr"] for r in D["species"])
    maxmm = int(-(-max(D["model_mm"], thr_max * 1.2, ev["p90"]) // 10) * 10)
    return {
        "dates": dates, "span": span, "rain_days": ev["days"], "horizon": dates[-1],
        "groups": [{"key": e, "name": ECO_NAME[e], "color": COLORS[e], "win": list(eco[e]["win"]),
                    "lag": eco[e]["lag"], "mean": eco[e]["means"]} for e in ECO_ORDER],
        "rain": {"p10": ev["p10"], "p50": ev["p50"], "p90": ev["p90"], "arso": ev["arso"],
                 "model": D["model_mm"], "totals": ev["totals"]},
        "species": [{"name": SHORT[r["id"]], "eco": r["eco"], "color": COLORS[r["eco"]], "thr": r["thr"],
                     "lag": r["lag"]} for r in D["species"]],
        "maxmm": maxmm,
        "bands": [{"name": b["name"], "n": b["n"]} for b in D["bands"]],
        "band_series": {e: [b["series"][e] for b in D["bands"]] for e in ECO_ORDER},
    }


CSS_GP = """<style>
/* mini-stat, disclaimer in sources so v blog.css manjkali (definirani so bili samo vdelano v starejših člankih) */
.mini-stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.4rem 0 2rem}
.mini-stat{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:.9rem .8rem;text-align:center}
.ms-label{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-family:'JetBrains Mono',monospace}
.ms-val{font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:1.4rem;line-height:1.1;margin:.18rem 0 .1rem;color:var(--cyan)}
.ms-sub{font-size:.72rem;color:var(--muted)}
@media(max-width:640px){.mini-stat-grid{grid-template-columns:repeat(2,1fr)}}
.disclaimer{background:rgba(239,68,68,.06);border:1px solid var(--card-border);border-radius:10px;padding:.8rem 1rem;margin:1.2rem 0;font-size:.85rem;color:var(--muted)}
.sources{font-size:.82rem;color:var(--muted);border-top:1px solid rgba(255,255,255,.07);margin-top:2.2rem;padding-top:1rem;line-height:1.7}
.gp-det{margin:.2rem 0 1.4rem;font-size:.88rem}
.gp-det summary{cursor:pointer;color:var(--muted)}
.gp-det .table-scroll{margin-top:.6rem}
.dz-fig .dz-ctl button.gp-g[aria-pressed="true"]{border-width:2px}
@media(max-width:520px){.dz-fig.chart-card{padding:.9rem .45rem 1rem;margin-left:-.45rem;margin-right:-.45rem}.dz-fig .dz-ro{font-size:.9rem;line-height:1.5}.dz-fig .dz-hint{font-size:.78rem}}
</style>"""

JS_GP = r"""
var GN={razkrojevalka:'razkrojevalke',lesna:'lesne vrste',mikorizna:'mikorizne vrste'};
function d0(iso){var p=iso.split('-');return (+p[2])+'. '+(+p[1])+'.';}
function dayLab(iso){var p=iso.split('-');return DN[new Date(Date.UTC(+p[0],+p[1]-1,+p[2])).getUTCDay()]+' '+(+p[2])+'.';}
function dot(x,y,c){return '<circle cx="'+x+'" cy="'+y+'" r="4.5" fill="'+c+'" stroke="'+SURF+'" stroke-width="2"/>';}
function spread(ys,gap){var o=ys.map(function(y,i){return {y:y,i:i};}).sort(function(a,b){return a.y-b.y;});
  for(var k=1;k<o.length;k++){if(o[k].y-o[k-1].y<gap)o[k].y=o[k-1].y+gap;}
  var r=[];o.forEach(function(q){r[q.i]=q.y;});return r;}

/* ---- 1: časovnica valov ---- */
(function(){
  var G=D.groups,nd=D.span.length,idx={};D.span.forEach(function(d,i){idx[d]=i;});
  wrap('gp-fig1',function(w){
    var nr=w<460,L=nr?34:40,R=12,T=14,H1=nr?180:120,LH=nr?48:40,Bt=26,H=T+H1+18+G.length*LH+Bt,pw=w-L-R;
    function X(i){return L+(i+.5)/nd*pw;}function Y(v){return T+H1-v/100*H1;}
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Povprečni indeks skupin gob po modelu in okna rasti trosnjakov po dežju" font-family="inherit">';
    var ri=D.rain_days.map(function(d){return idx[d];}),rx0=L+ri[0]/nd*pw,rx1=L+(ri[ri.length-1]+1)/nd*pw;
    s+='<rect x="'+rx0+'" y="'+T+'" width="'+(rx1-rx0)+'" height="'+(H-T-Bt)+'" fill="'+MUTED+'" fill-opacity=".13"/>';
    s+='<text x="'+((rx0+rx1)/2)+'" y="'+(T+11)+'" text-anchor="middle" font-size="11" fill="'+MUTED+'">dež</text>';
    s=axisY(s,L,R,w,Y,[0,50,100],function(t){return t;});
    s+='<text x="'+L+'" y="'+(T-3)+'" font-size="12" fill="'+MUTED+'">indeks skupine, %</text>';
    var hx=L+(idx[D.horizon]+1)/nd*pw;
    s+='<line x1="'+hx+'" x2="'+hx+'" y1="'+T+'" y2="'+(T+H1)+'" stroke="'+MUTED+'" stroke-dasharray="3 3"/>';
    s+='<text x="'+(hx+5)+'" y="'+(T+H1-5)+'" font-size="11" fill="'+MUTED+'">konec modelove napovedi</text>';
    var ends=G.map(function(g){return Y(g.mean[g.mean.length-1]);}),ly=spread(ends,13);
    G.forEach(function(g,k){
      var pts=g.mean.map(function(v,i){return X(idx[D.dates[i]])+','+Y(v);}).join(' ');
      s+='<polyline points="'+pts+'" fill="none" stroke="'+g.color+'" stroke-width="'+(nr?3.2:2.4)+'" stroke-linejoin="round" stroke-linecap="round"/>';
      if(!nr){s+='<rect x="'+(hx+5)+'" y="'+(ly[k]-14+3)+'" width="10" height="10" rx="2" fill="'+g.color+'"/>';
      s+='<text x="'+(hx+19)+'" y="'+(ly[k]-14+13)+'" font-size="12" font-weight="600" fill="'+INK+'">'+g.name+'</text>';}
    });
    G.forEach(function(g,k){
      var y0=T+H1+18+k*LH,xa=L+idx[g.win[0]]/nd*pw,xb=L+(idx[g.win[1]]+1)/nd*pw;
      s+='<text x="'+L+'" y="'+(y0+12)+'" font-size="'+(nr?13:12)+'" fill="'+INK+'">'+g.name+' · '+d0(g.win[0])+'–'+d0(g.win[1])+(w>=520?' <tspan fill="'+MUTED+'">(zamik '+g.lag[0]+'–'+g.lag[1]+' dni)</tspan>':'')+'</text>';
      s+='<rect class="ln" data-k="'+k+'" x="'+xa+'" y="'+(y0+18)+'" width="'+(xb-xa)+'" height="'+(nr?18:12)+'" rx="5" fill="'+g.color+'" fill-opacity=".3"/>';
    });
    var step=w<520?3:2;
    D.span.forEach(function(d,i){if(i%step===0)s+='<text x="'+X(i)+'" y="'+(H-6)+'" text-anchor="middle" font-size="11" fill="'+MUTED+'">'+d0(d).replace(' ',' ')+'</text>';});
    s+='<g class="cur"></g></svg>';
    return {svg:s,w:w,H:H,T:T,L:L,pw:pw,X:X,Y:Y,big:7,inv:function(px){return Math.floor((px-L)/pw*nd);}};
  },function(i,g,svg){
    var d=D.span[i],x=g.X(i),h='<line x1="'+x+'" x2="'+x+'" y1="'+g.T+'" y2="'+(g.H-26)+'" stroke="rgba(255,255,255,.7)" stroke-width="1.5"/>';
    var act=[],mi=D.dates.indexOf(d),vals=[];
    D.groups.forEach(function(gr,k){
      var on=d>=gr.win[0]&&d<=gr.win[1];if(on)act.push(gr.name);
      svg.querySelector('.ln[data-k="'+k+'"]').setAttribute('fill-opacity',on?'.9':'.3');
      if(mi>=0){h+=dot(x,g.Y(gr.mean[mi]),gr.color);vals.push(gr.name+' <b>'+f0(gr.mean[mi])+' %</b>');}
    });
    svg.querySelector('.cur').innerHTML=h;
    return '<b>'+dl(d)+'</b> · v oknu: <b>'+(act.length?act.join(', '):'nobena skupina')+'</b><br>'+
      (mi>=0?'model: '+vals.join(' · '):'<small>za ta dan model še nima napovedi (sega do '+dl(D.horizon)+')</small>');
  },function(){return nd;},5);
})();

/* ---- 2: dež proti pragom ---- */
(function(){
  var S=D.species,Rn=D.rain,MAX=D.maxmm,tot=Rn.totals;
  function share(x){var c=0;tot.forEach(function(v){if(v>=x)c++;});return Math.round(100*c/tot.length);}
  function verdict(r){return r<.85?'pod pragom':r<=1.15?'na meji':'nad pragom';}
  var refs=[['P10',Rn.p10],['mediana',Rn.p50],['P90',Rn.p90],['ARSO',Rn.arso],['model',Rn.model]],host=el('gp-ref'),fig;
  if(host){refs.forEach(function(r){var b=document.createElement('button');b.type='button';b.textContent=r[0]+' '+f1(r[1])+' mm';b.setAttribute('aria-pressed','false');b.dataset.v=Math.round(r[1]);
    b.addEventListener('click',function(){fig.put(+b.dataset.v);});host.appendChild(b);});}
  fig=wrap('gp-fig2',function(w){
    var narrow=w<460,L=Math.round(narrow?w*.27:Math.min(130,w*.34)),R=40,T=44,RH=narrow?42:32,Bt=46,bh=narrow?22:14,H=T+S.length*RH+Bt,pw=w-L-R;
    function X(v){return L+v/MAX*pw;}
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Količina dežja proti pragu sprožilnega dežja po vrstah" font-family="inherit">';
    s+='<rect x="'+X(Rn.p10)+'" y="'+(T-10)+'" width="'+(X(Rn.p90)-X(Rn.p10))+'" height="'+(H-T-Bt+10)+'" fill="'+MUTED+'" fill-opacity=".14"/>';
    s+='<line x1="'+X(Rn.p50)+'" x2="'+X(Rn.p50)+'" y1="'+(T-10)+'" y2="'+(H-Bt)+'" stroke="'+MUTED+'" stroke-width="2"/>';
    s+='<text x="'+((X(Rn.p10)+X(Rn.p90))/2)+'" y="'+(T-16)+'" text-anchor="middle" font-size="11" fill="'+MUTED+'">ansambel P10–P90</text>';
    s+='<line x1="'+X(Rn.model)+'" x2="'+X(Rn.model)+'" y1="'+(T-10)+'" y2="'+(H-Bt)+'" stroke="'+INK+'" stroke-dasharray="4 3" stroke-width="1.5"/>';
    s+='<text x="'+X(Rn.model)+'" y="'+(T-16)+'" text-anchor="middle" font-size="11" fill="'+MUTED+'">model</text>';
    S.forEach(function(sp,k){
      var y=T+k*RH+(narrow?8:6);
      s+='<text x="'+(L-8)+'" y="'+(y+bh-3)+'" text-anchor="end" font-size="'+(narrow?13:12)+'" fill="'+INK+'">'+(narrow?sp.name.split(' ').pop().replace(/^./,function(c){return c.toUpperCase();}):sp.name)+'</text>';
      s+='<rect x="'+L+'" y="'+y+'" width="'+(X(sp.thr)-L)+'" height="'+bh+'" rx="4" fill="'+sp.color+'" fill-opacity=".25"/>';
      s+='<rect class="fl" data-k="'+k+'" x="'+L+'" y="'+y+'" width="0" height="'+bh+'" rx="4" fill="'+sp.color+'"/>';
      s+='<text x="'+(X(sp.thr)+5)+'" y="'+(y+bh-3)+'" font-size="11" fill="'+INK+'" stroke="'+SURF+'" stroke-width="3" paint-order="stroke">'+sp.thr+'</text>';
    });
    for(var v=0;v<=MAX;v+=10)s+='<text x="'+X(v)+'" y="'+(H-28)+'" text-anchor="middle" font-size="11" fill="'+MUTED+'">'+v+'</text>';
    s+='<text x="'+L+'" y="'+(H-10)+'" font-size="11" fill="'+MUTED+'">'+(narrow?'mm dežja 8.–10. 10.':'mm dežja 8.–10. 10. · številka ob stolpcu je prag vrste')+'</text>';
    s+='<g class="cur"></g></svg>';
    return {svg:s,w:w,H:H,T:T,L:L,pw:pw,X:X,big:10,inv:function(px){return Math.round((px-L)/pw*MAX);}};
  },function(i,g,svg){
    var rows=[];
    S.forEach(function(sp,k){
      var r=i/sp.thr;svg.querySelector('.fl[data-k="'+k+'"]').setAttribute('width',Math.max(0,g.X(Math.min(i,sp.thr))-g.L));
      rows.push(sp.name+' <b>'+f0(Math.min(r,9.99)*100)+' %</b> praga ('+verdict(r)+')');
    });
    svg.querySelector('.cur').innerHTML='<line x1="'+g.X(i)+'" x2="'+g.X(i)+'" y1="'+(g.T-10)+'" y2="'+(g.H-46)+'" stroke="rgba(255,255,255,.8)" stroke-width="1.5"/>';
    if(host)Array.prototype.forEach.call(host.children,function(b){b.setAttribute('aria-pressed',+b.dataset.v===i?'true':'false');});
    return 'Pri <b>'+i+' mm</b> dežja ima toliko ali več <b>'+share(i)+' %</b> članov ansambla.<br>'+rows.join(' · ');
  },function(){return MAX+1;},Math.round(Rn.p50));
})();

/* ---- 3: višina ---- */
(function(){
  var B=D.bands,nd=D.dates.length,gi=0,fig,host=el('gp-grp');
  if(host){D.groups.forEach(function(g,k){var b=document.createElement('button');b.type='button';b.className='gp-g';b.textContent=g.name;b.setAttribute('aria-pressed',k===0?'true':'false');
    b.style.borderColor=g.color;b.addEventListener('click',function(){gi=k;Array.prototype.forEach.call(host.children,function(c,j){c.setAttribute('aria-pressed',j===k?'true':'false');});fig.redraw();});host.appendChild(b);});}
  var DASH=['','7 4','2 4','10 3 2 3'];
  fig=wrap('gp-fig3',function(w){
    var nr=w<460,L=nr?34:40,R=nr?14:Math.min(112,w*.3),T=14,H=nr?320:230,Bt=nr?78:26,ph=H-T-Bt,pw=w-L-R,g=D.groups[gi],ser=D.band_series[g.key];
    var all=[];ser.forEach(function(a){all=all.concat(a);});
    var lo=Math.max(0,Math.floor((Math.min.apply(null,all)-5)/10)*10),hi=Math.min(100,Math.ceil((Math.max.apply(null,all)+5)/10)*10),tk=[];
    for(var t=lo;t<=hi;t+=10)tk.push(t);
    function X(i){return L+i/(nd-1)*pw;}function Y(v){return T+ph-(v-lo)/(hi-lo)*ph;}
    var s='<svg viewBox="0 0 '+w+' '+H+'" role="img" aria-label="Povprečni indeks skupine po višinskih pasovih" font-family="inherit">';
    s=axisY(s,L,R,w,Y,tk,function(t){return t;});
    s+='<text x="'+L+'" y="'+(T-3)+'" font-size="12" fill="'+MUTED+'">indeks, % (os od '+lo+') · '+g.name+'</text>';
    var ys=B.map(function(b,k){return Y(ser[k][nd-1]);}),ly=spread(ys,13);
    B.forEach(function(b,k){
      s+='<polyline points="'+ser[k].map(function(v,i){return X(i)+','+Y(v);}).join(' ')+'" fill="none" stroke="'+g.color+'" stroke-width="'+(nr?3.2:2.4)+'" stroke-linejoin="round" stroke-dasharray="'+DASH[k]+'"/>';
      if(nr){var lx=L+(k%2)*(pw/2),ly2=H-Bt+36+Math.floor(k/2)*22;
        s+='<line x1="'+lx+'" x2="'+(lx+26)+'" y1="'+ly2+'" y2="'+ly2+'" stroke="'+g.color+'" stroke-width="3" stroke-dasharray="'+DASH[k]+'"/>';
        s+='<text x="'+(lx+32)+'" y="'+(ly2+4)+'" font-size="12.5" fill="'+INK+'">'+b.name+'</text>';}
      else{s+='<line x1="'+(w-R+6)+'" x2="'+(w-R+22)+'" y1="'+ly[k]+'" y2="'+ly[k]+'" stroke="'+g.color+'" stroke-width="2.4" stroke-dasharray="'+DASH[k]+'"/>';
      s+='<text x="'+(w-R+26)+'" y="'+(ly[k]+4)+'" font-size="11.5" fill="'+INK+'">'+b.name+'</text>';}
    });
    D.dates.forEach(function(d,i){if(nr&&i%2)return;s+='<text x="'+X(i)+'" y="'+(H-Bt+16)+'" text-anchor="middle" font-size="11" fill="'+MUTED+'">'+d0(d).replace(' ',' ')+'</text>';});
    s+='<g class="cur"></g></svg>';
    return {svg:s,w:w,H:H,Bt:Bt,T:T,L:L,pw:pw,X:X,Y:Y,big:1,g:g,ser:ser,inv:function(px){return Math.round((px-L)/pw*(nd-1));}};
  },function(i,g,svg){
    var h='<line x1="'+g.X(i)+'" x2="'+g.X(i)+'" y1="'+g.T+'" y2="'+(g.H-g.Bt)+'" stroke="rgba(255,255,255,.7)" stroke-width="1.5"/>';
    var vals=B.map(function(b,k){h+=dot(g.X(i),g.Y(g.ser[k][i]),g.g.color);return b.name+' <b>'+f0(g.ser[k][i])+' %</b> <small>('+b.n+' območij)</small>';});
    svg.querySelector('.cur').innerHTML=h;
    return '<b>'+dl(D.dates[i])+'</b> · '+g.g.name+', povprečje vseh vrst v skupini:<br>'+vals.join(' · ');
  },function(){return nd;},5);
})();
"""


def figure(fid, ctl, hint):
    return dz.fig(fid, ctl, hint, "gp")


def details(title, tbl):
    return f'<details class="gp-det"><summary>{title}</summary>{tbl}</details>'


def build_article(D):
    ev, eco, R = D["ev"], D["eco"], D["R"]
    d1, d3 = D["d1"], D["d3"]
    rr = rng(d1, d3)
    p50, arso = ev["p50"], ev["arso"]
    mod = D["model_mm"]
    dry = R["dry"]
    win = {e: rng(*eco[e]["win"]) for e in ECO_ORDER}
    sp = {r["id"]: r for r in D["species"]}
    kuk, les, mik = eco["razkrojevalka"], eco["lesna"], eco["mikorizna"]
    share_jurcek = sp["boletus_edulis"]["share"]
    jur_pct = round(100 * p50 / sp["boletus_edulis"]["thr"])

    lead = (f"Po {dry['days']} suhih dneh in samo {mm(dry['sum'])} mm dežja se Rečici {rr} obeta konec suše. "
            f"Gobe bodo, a ne vse hkrati in ne takoj: razkrojevalke in lesne vrste v nekaj dneh po dežju, mikorizne "
            f"(jurček, lisička, rumeni ježek) pa po zamikih, ki jih uporablja model, šele {win['mikorizna']} "
            f"Dež, ki ga napovedujejo ansambli (mediana {mm(p50)} mm), je pri nekaterih vrstah natanko na meji "
            f"praga v našem gobarskem modelu. Grafi spodaj kažejo, kdaj, koliko in kje.")

    stats = ('<div class="mini-stat-grid">'
             f'<div class="mini-stat"><div class="ms-label">Dež {rr}, ansambel</div><div class="ms-val">{mm(p50)} mm</div><div class="ms-sub">mediana, ARSO {mm(arso)} mm</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Dež v modelu gob</div><div class="ms-val">{mm(mod)} mm</div><div class="ms-sub">mokrejši scenarij</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Suša pred dežjem</div><div class="ms-val">{dry["days"]} dni</div><div class="ms-sub">{mm(dry["sum"])} mm</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Mikorizne vrste</div><div class="ms-val" style="font-size:1.15rem">{win["mikorizna"]}</div><div class="ms-sub">okno po zamiku</div></div>'
             '</div>')

    sec1 = [
        stats,
        (f"<strong>Ploščici z dežjem se razlikujeta, ker prideta iz različnih virov.</strong> Prva je ansambel iz "
         f"<a href=\"/blog/{RAIN_SLUG}.html\" style=\"color:var(--blue)\">članka o dežu</a>: mediana {ev['n']} članov za {rr} je {mm(p50)} mm "
         f"(P10 {mm(ev['p10'])}, P90 {mm(ev['p90'])} mm), ARSO {mm(arso)} mm. Druga je dež, ki ga uporablja gobarski model: ta ansambla ne "
         f"uporablja, ampak za vsako od {D['n_loc']} območij dobi eno napoved Open-Meteo, ki je za Rečico bistveno mokrejša, "
         f"<strong>{mm(mod)} mm</strong>."),
        (f"Modelovi indeksi so zato <strong>scenarij mokre napovedi</strong>: če se uresniči mediana ansambla, bodo nižji, predvsem pri vrstah "
         f"z visokim pragom. Ta model za {short(D['extra_day'])} napoveduje še {mm(D['extra_mm'])} mm, kar v članku o dežu ni zajeto."),
        (f"Pomembna je tudi suša: tla so danes po modelu skoraj popolnoma suha ({D['soil_now']} % na modelovi lestvici), zato prvi "
         f"milimetri najprej namočijo prst in steljo."),
    ]

    rows = [[ECO_NAME[e], ex, f"{eco[e]['lag'][0]}–{eco[e]['lag'][1]} dni", win[e]] for e, ex in
            [("razkrojevalka", "marela, poljski kukmak"), ("lesna", "bezgova uhljevka, bukov ostrigar, štorovka"),
             ("mikorizna", "jurček, lisička, rumeni ježek, kostanjevka")]]
    sec2 = [
        (f"Vsaka skupina ima v modelu svoj zamik med sprožilnim dežjem in trosnjaki "
         f"(<a href=\"/blog/trije-vali-gob-po-dezju-0911.html\" style=\"color:var(--blue)\">več v septembrskem članku</a>). "
         f"Računano od prvega do zadnjega dne dežja ({rr}) so okna taka; črte kažejo, kaj za isti čas napove model."),
        figure("gp-fig1", "", "Premaknite kazalec po času ali uporabite ← → (PageUp/PageDown: teden dni). Črte kažejo povprečni indeks "
                              "skupine v Rečici po modelu, pasovi spodaj okno, v katerem pričakujemo trosnjake, siv pas dneve dežja."),
        details("Okna v tabeli", table(["Skupina", "Primeri", "Zamik", "Okno"], rows)),
        (f"V Rečici je povprečni indeks razkrojevalk najvišji {short(kuk['peak_date'])} ({kuk['peak_mean']} %), lesnih vrst "
         f"{short(les['peak_date'])} ({les['peak_mean']} %), najboljša posamezna vrsta pa je "
         f"{les['best_name'].split(' (')[0].lower()} s {les['best']} % ({short(les['best_date'])}). Pri mikoriznih vrstah povprečje skupine "
         f"ne preseže {mik['peak_mean']} %, ker je njihovo okno <strong>zunaj sedemdnevnega horizonta modela</strong>; ta bo začetek okna "
         f"dosegel okoli {short(add_days(mik['win'][0], -6))}. V prvih dneh po dežju torej ne iščite jurčkov: prve pridejo gobe na lesu "
         f"in na stelji."),
    ]

    prow = [[r["name"].split(" (")[0], ECO_NAME[r["eco"]].lower(), f"{r['lag'][0]}–{r['lag'][1]} dni", f"{thr_s(r['thr'])} mm",
             verdict(p50, r["thr"]), f"{r['share']} %", verdict(mod, r["thr"])] for r in D["species"]]
    sec3 = [
        (f"Za vsako vrsto model zahteva določeno količino sprožilnega dežja v njenem oknu. Dež šteje 25 % indeksa, do praga pa točke "
         f"rastejo sorazmerno z dežjem. Premikajte kazalec po količini dežja {rr} in poglejte, koliko praga dosežejo vrste:"),
        figure("gp-fig2", '<div class="dz-ctl" role="group" aria-label="Količina dežja" id="gp-ref"></div>',
               "Premaknite kazalec po osi ali kliknite gumb. Siv pas je razpon ansambla (P10–P90) s črto mediane, črtkana črta je dež, ki "
               "ga uporablja model. Številka ob stolpcu je prag vrste v mm; stolpec se polni do praga."),
        details("Primerjava v tabeli", table(["Vrsta", "Skupina", "Zamik", "Prag", f"Ansambel ({mm(p50)} mm)",
                                              "Članov ansambla ≥ prag", f"Model ({mm(mod)} mm)"], prow)),
        (f"Pragovi so parametri modela, izpeljani iz baze vrst in še <strong>ne umerjeni na terenu</strong>. Pri mediani ansambla sta bukov "
         f"ostrigar in marela na meji, bezgova uhljevka pod pragom, jurček (prag {thr_s(sp['boletus_edulis']['thr'])} mm) doseže okoli "
         f"{jur_pct} % praga, prag pa doseže približno {share_jurcek} % članov ansambla. Pri mokrejšem scenariju so vse omenjene vrste nad "
         f"pragom. Razpon je velik, zato je smiselno počakati na meritev na postaji, preden se odpravite daleč."),
    ]

    brow = [[b["name"], str(b["n"]), f"{b['razkrojevalka']} %", f"{b['lesna']} %", f"{b['mikorizna']} %"] for b in D["bands"]]
    wet = ", ".join(f"{n} ({mm(v)} mm)" for n, v in D["wet"])
    dryt = ", ".join(f"{n} ({mm(v)} mm)" for n, v in D["dry"])
    prot = ", ".join(D["prot"][:3]) if D["prot"] else ""
    sec4 = [
        (f"Pri najboljši posamezni vrsti območja ne razlikujemo: {short(D['high_date'])} jo ima {D['n_high']} od {D['n_loc']} območij nad 80 %. "
         f"Razlike se pokažejo pri povprečju skupin po višini."),
        figure("gp-fig3", '<div class="dz-ctl" role="group" aria-label="Skupina" id="gp-grp"></div>',
               "Izberite skupino in premaknite kazalec po dnevih. Vsaka črta je povprečje indeksa vseh vrst v skupini na območjih "
               "določenega višinskega pasu; vrste črt so v legendi."),
        details("Povprečje za " + f"{short(add_days(D['high_date'], -1))} in {short(D['high_date'])} v tabeli",
                table(["Višina", "Območij", "Razkrojevalke", "Lesne vrste", "Mikorizne vrste"], brow)),
        ("Po modelu so nižje in srednje lege (do približno 800 m) za prve gobe po dežju ugodnejše kot grebeni nad 1100 m: tam je hladneje "
         "in nekatere vrste so zunaj svojega višinskega območja."),
        (f"Dež po območjih se po tem modelu precej razlikuje. Največ ga je južno od Luč, okoli Lučke Bele, Plahojce in Kašnega vrha: {wet}. "
         f"Najmanj na Solčavskem: {dryt}. Gre za en model z mrežo, ki ozkih dolin in grebenov ne razločuje, zato je vzorec (več dežja južno od Luč, "
         f"manj na Solčavskem) zanesljivejši od posameznih številk."),
        (f"Območij v zaščiti{(' (' + prot + ' …)') if prot else ''} model ne ocenjuje; tam preverite omejitve nabiranja. "
         f"Celotna napoved po območjih je na strani <a href=\"/gobarska-napoved/danes/\" style=\"color:var(--blue)\">Danes po gozdovih</a>."),
    ]

    data_json = json.dumps(payload(D), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    helper = dz.JS.split("/* ---- 1:")[0].replace("dez-data", "gp-data")
    code = f'<div><script type="application/json" id="gp-data">{data_json}</script>{dz.CSS}{CSS_GP}{helper}{JS_GP}}})();\n</script></div>'
    sec5 = [
        (f"Za razkrojevalke in lesne vrste je najboljši čas po modelu <strong>{rng(kuk['peak_date'], les['peak_date'])}</strong>, za mikorizne "
         f"vrste pa računajte na okno <strong>{win['mikorizna']}</strong>, če bo dežja dovolj. Ali ga bo dovolj, bomo vedeli, ko bo dež na "
         f"postaji izmerjen."),
        ('<div class="callout"><h3>Skratka</h3>'
         f'<p>Dež {rr} konča {dry["days"]}-dnevno sušo, a jurčkov v prvih dneh ne pričakujte. Najprej pridejo gobe na lesu in razkrojevalke '
         f'({win["razkrojevalka"]}), mikorizne po zamiku {win["mikorizna"]} Pri mediani ansambla ({mm(p50)} mm) jurček doseže okoli {jur_pct} % '
         f'svojega praga, pri mokrejšem scenariju ({mm(mod)} mm) ga presega.</p></div>'),
        ('<div class="disclaimer">Indeks je ocena ugodnosti razmer na podlagi vremena in ni obljuba najdbe. Pred nabiranjem vedno '
         'preverite vrsto z izkušenim nabiralcem ali mikologom – glejte tudi '
         '<a href="/gobarska-napoved/baza-vrst/" style="color:var(--blue)">bazo vrst</a>.</div>'),
        code,
    ]

    src = ('<div class="sources"><strong>Viri:</strong><br>'
           f'Dež: ansambel ECMWF ENS, ICON-EU-EPS in GEFS prek <a href="https://open-meteo.com/" target="_blank" rel="noopener" style="color:var(--blue)">Open-Meteo</a> in ARSO, '
           f'<a href="/blog/{RAIN_SLUG}.html" style="color:var(--blue)">članek o dežu</a>.<br>'
           f'Gobarski indeks, zamiki in pragovi po vrstah: model Meteorec (verzija {D["model_version"]}, '
           '<code>species_rules.yaml</code>), vhodni podatki Open-Meteo. Posnetek ob uri zajema, '
           f'današnji izračun je na <a href="/gobarska-napoved/" style="color:var(--blue)">meteorec.si/gobarska-napoved</a>.<br>'
           'Postaja IREICA1, Rečica ob Savinji · <a href="/" style="color:var(--blue)">meteorec.si</a></div>')

    return {
        "title": "Gobe po dežju 8.–10. oktobra: kdaj in kje jih pričakovati",
        "meta_description": (f"Dež {rr} konča {dry['days']} suhih dni. Gobe na lesu pridejo prve ({rng(*les['win'])}), "
                             f"jurčki {win['mikorizna']} Interaktivni grafi: okna rasti, pragovi dežja, višina."),
        "tags": ["gobe", "gobarski indeks", "napoved", "dež", "oktober", "2026"],
        "section_label": "Gobarski model",
        "og_photo": "gobe-lastna",
        "og_accent_hex": "#34d399",
        "lead": lead,
        "sources_note": src,
        "sections": [
            {"label": "01 — dež", "heading": "Koliko dežja bodo gobe res dobile", "id": "dez", "paragraphs": sec1},
            {"label": "02 — zamik", "heading": "Kdo pride prvi in kdo šele čez dva tedna", "id": "zamik", "paragraphs": sec2},
            {"label": "03 — prag", "heading": "Dež je pri nekaterih vrstah na meji praga", "id": "prag", "paragraphs": sec3},
            {"label": "04 — kje", "heading": "Kje: višina in količina dežja", "id": "kje", "paragraphs": sec4},
            {"label": "05 — kdaj", "heading": "Kdaj v gozd", "id": "kdaj", "paragraphs": sec5},
        ],
    }


def main():
    dry = "--dry-run" in sys.argv
    wire = "--wire" in sys.argv
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    D = build_data(cache)
    article = build_article(D)
    if dry:
        print("TITLE:", article["title"])
        print("LEAD:", article["lead"])
        for s in article["sections"]:
            print("\n##", s["heading"])
            for p in s["paragraphs"]:
                print(re.sub(r"<[^>]+>", " ", p) if p.lstrip().startswith("<") else p)
        print("\nMETA:", article["meta_description"], len(article["meta_description"]))
        return
    ftp.TODAY = D["today"]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Gobe po dežju\n8.–10. oktobra", meta_note="gobarski model",
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
