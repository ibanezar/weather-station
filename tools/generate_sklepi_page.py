#!/usr/bin/env python3
"""
tools/generate_sklepi_page.py — /sklepi/: vreme in bolečine v sklepih (napoved dejavnikov, graf tlaka, dnevnik, analiza)

Konfiguracija za day_score_common.py + lastni razdelki, po vzoru /migrena/ in /adhd/:
  * za vpliv vremena na bolečino v sklepih so dokazi MEŠANI (majhne povprečne povezave, velike razlike med ljudmi),
    zato stran ne napoveduje bolečine, ampak kaže dejavnike, ki jih ljudje najpogosteje omenjajo, in pusti bralcu preveriti
    SVOJ vzorec;
  * dnevnik bolečine (0–10 na dan) je samo v brskalniku (localStorage), na strežnik ne gre nič;
  * analiza: Spearmanova korelacija bolečine z dejavniki po meritvah postaje IREICA1 (history.json, samo ZUNANJA polja,
    dnevi z src == "era5" so reanaliza in se ne štejejo). Pri več primerjavah hkrati je merilo strožje (|z| > 2,58) in pod
    14 dnevi stran ne trdi nič. Ni dokaz vzročnosti in ni zdravniški nasvet.

JS sklAnalyze() živi samo tu; test_sklepi.py ga poganja z Nodom proti Python referenci (Spearman).
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, bands_desc, mean, wind_pts, esc  # noqa: E402
import generate_seo_pages as seo  # noqa: E402
import generate_migrena_page as M  # noqa: E402  (pressure_drops, pressure_chart, DROP_TH, LOW_P_TH, EXTRA_CSS)

MIN_DAYS = 14          # pod tem stran ne trdi nič
MIN_PAIRS = 8          # najmanj parov za posamezen dejavnik
Z_CRIT = 2.58          # strožje od 1,96: primerjamo ~10 dejavnikov hkrati
DAMP_RH = (85, 92)
COLD_APP = (5, 0)      # občutena (povprečje 8.–20.) ≤ 5 = 1, ≤ 0 = 2


def day_fn(c, d):
    pts, det = {}, {}
    drop = M.pressure_drops(c, d)
    pts["tlak_pad"] = bands(drop, M.DROP_TH) if drop is not None else 0
    det["tlak_pad"] = (f"tlak pade do {seo.num(drop, 1)} hPa v 24 h" if drop is not None and drop >= M.DROP_TH[0]
                       else f"brez izrazitega padca tlaka (največ {seo.num(max(drop, 0), 1)} hPa v 24 h)" if drop is not None
                       else "model ne vrača podatka")
    p = mean(c.vals("pressure_msl", d))
    pts["tlak_nizek"] = bands_desc(p, M.LOW_P_TH)
    det["tlak_nizek"] = f"tlak povprečno {seo.num(p, 0)} hPa" if p is not None else "model ne vrača podatka"
    rh = mean(c.vals("relative_humidity_2m", d))
    pts["vlaga"] = 0 if rh is None else 2 if rh >= DAMP_RH[1] else 1 if rh >= DAMP_RH[0] else 0
    det["vlaga"] = f"vlaga povprečno {seo.num(rh, 0)} %" if rh is not None else "model ne vrača podatka"
    w, wt = wind_pts(c, d, (25, 40, 55), (45, 60, 75), 6, 22)
    pts["veter"], det["veter"] = min(w, 2), wt
    a = mean(c.vals("apparent_temperature", d, 8, 20))
    pts["mraz"] = 0 if a is None else 2 if a <= COLD_APP[1] else 1 if a <= COLD_APP[0] else 0
    det["mraz"] = f"občutena čez dan povprečno {seo.num(a, 0)} °C" if a is not None else "model ne vrača podatka"
    return pts, det


# ── Analiza dnevnika (JS) ────────────────────────────────────────────────────

SKL_ANALYZE_JS = r"""function sklAnalyze(hist,entries){
  function prev(d,n){var t=new Date(d+'T12:00:00Z');t.setUTCDate(t.getUTCDate()-n);return t.toISOString().slice(0,10);}
  function row(d){var r=hist[d];return r&&r.src!=='era5'?r:null;}
  function g(d,k){var r=row(d);return r&&typeof r[k]==='number'?r[k]:null;}
  function diff(d,k,n){var a=g(d,k),b=g(prev(d,n),k);return a==null||b==null?null:a-b;}
  var M=[
   {id:'dP0',label:'Zračni tlak: sprememba glede na prejšnji dan',unit:'hPa',dec:1,f:function(d){return diff(d,'pressureAvg',1);}},
   {id:'dP1',label:'Zračni tlak: sprememba dan prej',unit:'hPa',dec:1,f:function(d){return diff(prev(d,1),'pressureAvg',1);}},
   {id:'P',label:'Zračni tlak (dnevno povprečje)',unit:'hPa',dec:0,f:function(d){return g(d,'pressureAvg');}},
   {id:'rP',label:'Dnevno nihanje tlaka',unit:'hPa',dec:1,f:function(d){var a=g(d,'pressureHigh'),b=g(d,'pressureLow');return a==null||b==null?null:a-b;}},
   {id:'T',label:'Povprečna temperatura',unit:'°C',dec:1,f:function(d){return g(d,'tempAvg');}},
   {id:'dT',label:'Temperatura: sprememba povprečja glede na včeraj',unit:'°C',dec:1,f:function(d){return diff(d,'tempAvg',1);}},
   {id:'RH',label:'Povprečna vlaga',unit:'%',dec:0,f:function(d){return g(d,'humidityAvg');}},
   {id:'gust',label:'Največji sunek vetra',unit:'km/h',dec:0,f:function(d){return g(d,'windgustHigh');}},
   {id:'rain',label:'Padavine',unit:'mm',dec:1,f:function(d){return g(d,'precipTotal');}},
   {id:'sun',label:'Največje sončno sevanje',unit:'W/m²',dec:0,f:function(d){return g(d,'solarHigh');}}];
  var seen={},E=[],total=(entries||[]).length;
  (entries||[]).slice().reverse().forEach(function(e){if(e&&!seen[e.d]&&typeof e.p==='number'&&e.p>=0&&e.p<=10&&row(e.d)){seen[e.d]=1;E.push({d:e.d,p:e.p});}});
  E.sort(function(a,b){return a.d<b.d?-1:1;});
  var out={nEntries:total,nUsed:E.length,rows:[],enough:E.length>=__MIN_DAYS__,from:E.length?E[0].d:null,to:E.length?E[E.length-1].d:null,zCrit:__Z_CRIT__};
  function ranks(x){var idx=x.map(function(v,i){return i;}).sort(function(a,b){return x[a]-x[b];}),r=new Array(x.length),i=0;
    while(i<idx.length){var j=i;while(j+1<idx.length&&x[idx[j+1]]===x[idx[i]])j++;var a=(i+j)/2+1;for(var k=i;k<=j;k++)r[idx[k]]=a;i=j+1;}return r;}
  function spearman(x,y){var a=ranks(x),b=ranks(y),n=x.length,ma=0,mb=0,i;for(i=0;i<n;i++){ma+=a[i];mb+=b[i];}ma/=n;mb/=n;
    var sab=0,saa=0,sbb=0;for(i=0;i<n;i++){sab+=(a[i]-ma)*(b[i]-mb);saa+=(a[i]-ma)*(a[i]-ma);sbb+=(b[i]-mb)*(b[i]-mb);}
    return saa>0&&sbb>0?sab/Math.sqrt(saa*sbb):null;}
  M.forEach(function(m){
    var xs=[],ys=[];E.forEach(function(e){var v=m.f(e.d);if(v!=null){xs.push(v);ys.push(e.p);}});
    if(xs.length<__MIN_PAIRS__)return;
    var rho=spearman(xs,ys);if(rho==null)return;
    var z=Math.atanh(Math.max(-0.999999,Math.min(0.999999,rho)))*Math.sqrt(xs.length-3);
    out.rows.push({id:m.id,label:m.label,unit:m.unit,dec:m.dec,n:xs.length,rho:rho,z:z,sig:out.enough&&Math.abs(z)>__Z_CRIT__});
  });
  out.rows.sort(function(a,b){return Math.abs(b.rho)-Math.abs(a.rho);});
  return out;
}""".replace("__MIN_DAYS__", str(MIN_DAYS)).replace("__MIN_PAIRS__", str(MIN_PAIRS)).replace("__Z_CRIT__", str(Z_CRIT))

CLIENT_JS = r"""
function $(id){return document.getElementById(id);}
function ymd(d){return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2);}
function nf(v,d){return v==null?'—':v.toFixed(d).replace('.',',').replace('-','−');}
function ls(k,def){try{var v=JSON.parse(localStorage.getItem(k));return v==null?def:v;}catch(e){return def;}}
function sv(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch(e){}}
var DK='wx-sklepi-dnevnik',diary=ls(DK,[]);
if(!Array.isArray(diary))diary=[];
function fd(d){var p=d.split('-');return (+p[2])+'. '+(+p[1])+'. '+p[0];}
function saveDiary(){diary.sort(function(a,b){return a.d<b.d?1:-1;});sv(DK,diary);}
function renderDiary(){
  var tb=$('skl-tbody');tb.textContent='';
  diary.forEach(function(e,i){var tr=document.createElement('tr');
    [fd(e.d),e.p+' od 10',e.n||''].forEach(function(t){var td=document.createElement('td');td.textContent=t;tr.appendChild(td);});
    var td=document.createElement('td'),b=document.createElement('button');b.type='button';b.className='dv-btn';b.textContent='Izbriši';b.setAttribute('aria-label','Izbriši zapis '+e.d);
    b.addEventListener('click',function(){diary.splice(i,1);saveDiary();renderDiary();});td.appendChild(b);tr.appendChild(td);tb.appendChild(tr);});
  $('skl-count').textContent=diary.length?('Zapisov v dnevniku: '+diary.length+'.'):'Dnevnik je prazen.';
  $('skl-table').hidden=!diary.length;$('skl-export').disabled=!diary.length;$('skl-clear').disabled=!diary.length;$('skl-analyze').disabled=!diary.length;
}
var di=$('skl-date'),pa=$('skl-pain'),po=$('skl-pain-out');di.max=ymd(new Date());di.value=ymd(new Date());
pa.addEventListener('input',function(){po.textContent=pa.value;});
$('skl-add').addEventListener('click',function(){
  var d=di.value;if(!d||d>ymd(new Date())){$('skl-msg').textContent='Izberite datum, ki ni v prihodnosti.';return;}
  var p=Math.max(0,Math.min(10,Math.round(+pa.value)));
  diary=diary.filter(function(e){return e.d!==d;});
  diary.push({d:d,p:p,n:($('skl-note').value||'').slice(0,200)});
  saveDiary();renderDiary();$('skl-note').value='';$('skl-msg').textContent='Zapis za '+d+' je shranjen v tem brskalniku.';
});
$('skl-clear').addEventListener('click',function(){if(confirm('Izbrišem celoten dnevnik v tem brskalniku?')){diary=[];saveDiary();renderDiary();$('skl-result').textContent='';}});
function csvCell(v){v=String(v==null?'':v);return /[;"\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}
$('skl-export').addEventListener('click',function(){
  var rows=[['datum','bolecina_0_10','opomba']].concat(diary.slice().sort(function(a,b){return a.d<b.d?-1:1;}).map(function(e){return [e.d,e.p,e.n];}));
  var blob=new Blob(['﻿'+rows.map(function(r){return r.map(csvCell).join(';');}).join('\r\n')],{type:'text/csv;charset=utf-8'});
  var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='sklepi-dnevnik.csv';document.body.appendChild(a);a.click();document.body.removeChild(a);setTimeout(function(){URL.revokeObjectURL(a.href);},1000);
});
function strength(r){var a=Math.abs(r);return a<0.2?'zanemarljiva':a<0.4?'šibka':a<0.6?'zmerna':'močna';}
$('skl-analyze').addEventListener('click',function(){
  var out=$('skl-result');out.textContent='Nalagam podatke postaje …';
  fetch('/history.json').then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(h){
    var res=sklAnalyze(h,diary);out.textContent='';
    var p=document.createElement('p');
    if(!res.nUsed){p.textContent='Za vaše datume ni podatkov postaje (zadnji dan v podatkih je včerajšnji).';out.appendChild(p);return;}
    p.textContent='Primerjava bolečine v '+res.nUsed+' dneh ('+fd(res.from)+' do '+fd(res.to)+') z vremenom po meritvah postaje IREICA1 v Rečici ob Savinji. Pozitivna povezava pomeni več bolečine ob višji vrednosti dejavnika.';
    out.appendChild(p);
    var w=document.createElement('p');w.className='muted-note';
    w.textContent=res.enough?'To je opis vaših zapisov, ne dokaz, da vreme povzroča bolečino. Primerja se več dejavnikov hkrati, zato je merilo za »izstopa« strožje, a kakšna povezava je lahko še vedno naključna. Bolečina sosednjih dni je podobna, kar učinek navidezno poveča.'
      :'Premalo zapisov za sklepe (potrebnih je vsaj '+__MIN_DAYS__+' dni). Številke so samo opis.';
    out.appendChild(w);
    var t=document.createElement('table');t.className='stats';var hr=document.createElement('tr');
    ['Dejavnik','Povezava','Dni',''].forEach(function(x){var th=document.createElement('th');th.textContent=x;hr.appendChild(th);});t.appendChild(hr);
    res.rows.forEach(function(r){var tr=document.createElement('tr');
      [r.label,(r.rho>0?'+':'')+nf(r.rho,2)+' ('+strength(r.rho)+')',String(r.n),r.sig?'izstopa':''].forEach(function(x,i){var c=document.createElement(i?'td':'th');c.textContent=x;if(i===3&&x)c.style.fontWeight='700';tr.appendChild(c);});t.appendChild(tr);});
    out.appendChild(t);
  }).catch(function(){out.textContent='Podatkov postaje ni bilo mogoče naložiti. Poskusite znova.';});
});
renderDiary();
""".replace("__MIN_DAYS__", str(MIN_DAYS))


def client_script(cfg, days):
    return "<script>\n(function(){\n" + SKL_ANALYZE_JS + "\n" + CLIENT_JS + "\n})();\n</script>"


def sections(cfg, c, days, today):
    chart = M.pressure_chart(c, today, tail="ki ga nekateri ljudje s sklepnimi težavami povezujejo z bolečino (dokazi so mešani)")
    evidence = '''  <h2>Kaj o vremenu in sklepih vemo – in česa ne</h2>
  <div class="dv-card" style="font-size:.92rem">
    <p style="margin:.55rem 0">Veliko ljudi s sklepnimi težavami poroča, da se bolečina spreminja z vremenom, najpogosteje ob padcu zračnega tlaka, vlagi, vetru in mrazu. Raziskave so mešane: nekatere najdejo majhne povezave, druge nobene, med ljudmi pa so razlike velike.</p>
    <p style="margin:.55rem 0"><strong>Ne vemo</strong>, ali vreme bolečino povzroča ali jo le okrepi, in zakaj se ljudje tako različno odzivajo. Zato ocena bolečine ne napoveduje; kaže samo dejavnike, ki jih ljudje najpogosteje omenjajo.</p>
    <p style="margin:.55rem 0"><strong>Lahko preverite sami:</strong> dnevnik spodaj primerja vaše zapise bolečine z meritvami postaje in pokaže, ali se pri vas kaj ujema.</p>
    <p class="dv-why" style="margin:.55rem 0">Vir: Dixon, W. G. in sod. (2019), projekt Cloudy with a Chance of Pain (več tisoč ljudi s kronično bolečino, dnevnik v aplikaciji): majhne povprečne povezave bolečine z visoko vlago, nizkim tlakom in močnim vetrom. npj Digital Medicine.</p>
  </div>'''
    red = ('  <div class="dv-red"><strong>Kdaj k zdravniku:</strong> sklep, ki je nenadno otekel, rdeč in topel; bolečina z vročino; bolečina po poškodbi ali padcu; '
           'sklepa ne morete obremeniti ali premikati; bolečina, ki se hitro slabša ali je ponoči neznosna. Pokličite osebnega zdravnika; '
           'ob hudi poškodbi ali znakih okužbe z vročino iščite nujno pomoč (112).</div>')
    diary = '''  <h2 id="dnevnik">Moj dnevnik bolečine</h2>
  <p class="archive-intro">Vsak dan vpišite, kako hudo vas boli (0 = nič, 10 = najhujša). Dnevnik je <strong>samo v vašem brskalniku</strong> (localStorage): ne gre na strežnik, ne pošilja se nikamor in ga brez vašega izvoza nihče ne vidi. Če izbrišete podatke brskalnika, ga izgubite, zato ga občasno izvozite (CSV, na primer za pogovor z zdravnikom).</p>
  <div class="dv-card"><form class="dv-form" id="skl-form" onsubmit="return false">
    <label>Datum <input type="date" id="skl-date"></label>
    <label>Bolečina: <strong><output id="skl-pain-out">3</output> od 10</strong> <input type="range" id="skl-pain" min="0" max="10" step="1" value="3"></label>
    <label>Opomba (neobvezno, največ 200 znakov) <textarea id="skl-note" maxlength="200" rows="2"></textarea></label>
    <div class="dv-actions"><button type="button" class="dv-btn dv-btn-p" id="skl-add">Dodaj zapis</button>
      <button type="button" class="dv-btn" id="skl-export" disabled>Izvozi CSV (za zdravnika)</button>
      <button type="button" class="dv-btn" id="skl-clear" disabled>Počisti dnevnik</button></div>
    <p class="dv-status" id="skl-msg" role="status" aria-live="polite"></p>
  </form>
  <p class="dv-status" id="skl-count">Dnevnik je prazen.</p>
  <div class="table-scroll" tabindex="0"><table class="stats" id="skl-table" hidden><thead><tr><th>Datum</th><th>Bolečina</th><th>Opomba</th><th></th></tr></thead><tbody id="skl-tbody"></tbody></table></div></div>
  <h2>Ali se moja bolečina ujema z vremenom?</h2>
  <p class="archive-intro">Primerjava vaših zapisov z meritvami postaje IREICA1 v Rečici ob Savinji: tlak in njegova sprememba, temperatura, vlaga, sunki, padavine, sonce. Če živite drugje, so podatki le približek vašega vremena. Pod 14 zapisi stran ne trdi nič.</p>
  <div class="dv-actions"><button type="button" class="dv-btn dv-btn-p" id="skl-analyze" disabled>Primerjaj mojo bolečino z vremenom</button></div>
  <div id="skl-result" aria-live="polite"></div>'''
    return {"after_cards": chart + "\n" + evidence + "\n" + red + "\n" + diary}


CFG = {
    "url": "/sklepi/", "slug": "sklepi", "crumb": "Vreme in sklepi",
    "short": "Vreme in sklepi",
    "title": "Vreme in sklepi: napoved za 5 dni in dnevnik bolečine",
    "h1": "Vreme in bolečine v sklepih: napoved in dnevnik",
    "meta": "Zračni tlak, vlaga, veter in mraz",
    "kicker": "Vremenski dejavniki za sklepe danes · Zgornja Savinjska dolina",
    "levels": ["nizko", "zmerno", "povišano", "visoko"],
    "advice": [
        "Vremenskih dejavnikov, ki jih ljudje povezujejo z bolečino v sklepih, je malo. Ravnajte po svojem običajnem načrtu.",
        "Nekaj dejavnikov. Bodite pozorni na svoje počutje; dnevnik pokaže, ali se pri vas kaj ujema.",
        "Več dejavnikov hkrati. Če ste občutljivi na vreme, si dan načrtujte nekoliko bolj prizanesljivo.",
        "Veliko dejavnikov hkrati. Ravnajte po načrtu, ki ste ga dogovorili z zdravnikom.",
    ],
    "th": (2, 4, 7), "day_fn": day_fn, "hour_fn": None,
    "groups": [("Tlak", "Zračni tlak", ["tlak_pad", "tlak_nizek"]),
               ("Vlaga in veter", "Vlaga in veter", ["vlaga", "veter"]),
               ("Temperatura", "Mraz", ["mraz"])],
    "group_icons": ["a", "b", "d"],
    "factors": [
        ("tlak_pad", "Padec zračnega tlaka", "V raziskavi z dnevnikom bolečine je bila majhna povezava z nizkim tlakom; hiter padec tlaka ob prehodu fronte ljudje omenjajo pogosto."),
        ("tlak_nizek", "Nizek zračni tlak", "Nizek tlak spremlja slabo vreme in fronte; povezava z bolečino je majhna in pri ljudeh različna."),
        ("vlaga", "Visoka vlaga", "V raziskavi je bila majhna povezava z visoko vlago; ocena šteje največ 2 točki."),
        ("veter", "Veter", "V raziskavi je bila majhna povezava z močnim vetrom; ocena šteje največ 2 točki, model je v dolini običajno previsok."),
        ("mraz", "Mrzlo vreme", "Mraz ljudje pogosto omenjajo (okorelost), dokazi so šibkejši; ocena šteje največ 2 točki."),
    ],
    "rules": [
        ("Padec tlaka", "3 / 5 / 8 hPa v 24 h", "največji padec v dnevu"),
        ("Nizek tlak", "pod 1008 / 1002 / 995 hPa", "dnevno povprečje"),
        ("Vlaga", "≥ 85 % = 1, ≥ 92 % = 2", "dnevno povprečje, največ 2 točki"),
        ("Veter (6.–22. ure)", "povprečno 25 / 40 / 55 km/h; sunki 45 / 60 / 75 km/h", "največ 2 točki"),
        ("Mraz (8.–20. ure)", "občutena ≤ 5 °C = 1, ≤ 0 °C = 2", "povprečje, največ 2 točki"),
    ],
    "method_intro": "Ocena sešteje točke petih dejavnikov (0–3 na dejavnik, največ 12; manj je bolje). Raven: do 1 točke nizko, 2–3 zmerno, 4–6 povišano, 7 ali več visoko; izrazit dejavnik (3 točke) da vsaj »povišano«. Pragovi so naši, niso klinični: pokažejo, koliko dejavnikov, ki jih ljudje najpogosteje povezujejo z bolečino, je hkrati prisotnih.",
    "limits": ["<strong>Dokazi so mešani.</strong> Povezave v raziskavah so majhne in med ljudmi različne; ocena zato ne napoveduje bolečine in ne trdi, da vreme bolečino povzroča.",
               "<strong>Bolečino v sklepih določa veliko drugega:</strong> bolezen, obremenitev, spanje, počutje in zdravljenje. Ocena zajema samo vreme.",
               "<strong>Analiza dnevnika</strong> je opis vaših zapisov. Bolečina sosednjih dni je podobna, dejavnikov je veliko, vzorec pa običajno majhen; pri manj kot 14 zapisih stran ne trdi nič."],
    "intro_q": "Ali vreme vpliva na bolečine v sklepih?",
    "intro_a": "Veliko ljudi poroča o povezavi s padcem tlaka, vlago, vetrom in mrazom. Raziskave so mešane: povezave so majhne, med ljudmi pa zelo različne. Zato stran poleg napovedi ponuja dnevnik, ki pokaže vaš lasten vzorec.",
    "disclaimer_lead": "To ni zdravniški nasvet.",
    "disclaimer": "Ocena prikazuje vremenske dejavnike, ne napoveduje bolečine in ne nadomešča zdravljenja. Zdravila in ukrepe določa vaš zdravnik.",
    "faq": [
        ("Ali vreme res vpliva na bolečine v sklepih?", "Pri nekaterih ljudeh da, pri drugih ne; raziskave so mešane. V britanski raziskavi z dnevnikom bolečine (Cloudy with a Chance of Pain, Dixon in sod., 2019) so bile povezave z vlago, tlakom in vetrom majhne, med ljudmi pa različne. Zato stran pokaže dejavnike in vam omogoča preveriti svoj vzorec."),
        ("Ali dnevnik bolečine gre na strežnik?", "Ne. Dnevnik je samo v vašem brskalniku (localStorage) in ga stran ne pošilja nikamor. Če izbrišete podatke brskalnika, ga izgubite, zato ga izvozite v CSV."),
        ("Kako zanesljiva je analiza?", "Je opis vaših zapisov, ne dokaz. Primerja se več dejavnikov hkrati, zato je merilo za »izstopa« strožje, a kakšna povezava je lahko še naključna. Pod 14 zapisi stran sklepov ne trdi."),
        ("Katere podatke uporablja analiza?", "Zunanje meritve postaje IREICA1 v Rečici ob Savinji (tlak, temperatura, vlaga, vetrni sunki, padavine, sonce). Dnevi, ki jih postaja ni merila, se ne štejejo. Če živite drugje, je vreme pri vas lahko drugačno."),
        ("Kdaj moram k zdravniku?", "Ob nenadoma otekli, rdeči in topli sklepi, bolečini z vročino, bolečini po poškodbi, če sklepa ne morete obremeniti ali ob hitro slabšajoči bolečini pokličite osebnega zdravnika. Ob hudi poškodbi ali znakih okužbe z vročino iščite nujno pomoč (112)."),
    ],
    "links": [("/migrena/", "Vreme in migrena →"), ("/biovreme/", "Biovreme →"), ("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"),
              ("/astma/", "Vreme in astma →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Vreme in sklepi danes: {lvl}. Tlak, vlaga, veter in mraz za 5 dni, graf tlaka ter dnevnik bolečine samo v vašem brskalniku.",
    "sections": sections, "script": client_script,
}


def main():
    D.CSS = D.CSS + "\n" + M.EXTRA_CSS
    D.main(CFG)


if __name__ == "__main__":
    main()
