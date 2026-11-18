#!/usr/bin/env python3
"""
tools/generate_sneg_porocila_page.py — /zima/sneg-porocila/ (18. 11. 2026)

»Ali je pri vas sneg?«: enogumbna anonimna poročila bralcev o snegu po regiji in višinskem pasu. Postaja IREICA1 snega
ne meri, zato poskusni model MTR sneg (kartica »Sneg v dolini«) nima izmerjene resnice; to je poceni način, da jo dobimo.

- Obrazec pošlje en dotik (`POST /sneg/porocilo`): stanje + višinski pas + regija. BREZ prostega besedila, GPS, imena,
  IP-ja ali id-ja v zapisu, zato brez moderacije (druga pot kot pri /nevihte/porocila/, kjer je besedilo bralcev).
- Javni so samo agregati po celici (regija × pas), `GET /sneg/porocila`; sodba šele od 3 poročil, od katerih vsaj 60 % pove isto.
- Poročilo bralca NI meritev in ni uradna informacija — stran to pove.
- STANJA, PASOVI in REGIJE so namerna podvojitev worker.js (SNEG_STANJA, SNEG_PASOVI, SNEG_REGIJE);
  tools/test_parity.py jih primerja. Pragovi sodbe (3, 60 %) so v workerju (SNEG_MIN_N, SNEG_MIN_SHARE) in v besedilu strani.

Usage:
  python3 tools/generate_sneg_porocila_page.py
"""
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"
URL = "/zima/sneg-porocila/"
MIN_N, MIN_SHARE = 3, 60                      # worker: SNEG_MIN_N, SNEG_MIN_SHARE * 100

STANJA = [
    ("lezi", "Sneg leži"),
    ("pada", "Sneži"),
    ("dez-sneg", "Dež s snegom"),
    ("brez", "Brez snega"),
]
PASOVI = [
    ("p0", "do 400 m"),
    ("p1", "400–700 m"),
    ("p2", "700–1000 m"),
    ("p3", "nad 1000 m"),
]
REGIJE = [
    "Savinjska", "Koroška", "Gorenjska", "Osrednjeslovenska", "Zasavska", "Posavska",
    "Jugovzhodna Slovenija", "Primorsko-notranjska", "Goriška", "Obalno-kraška",
    "Podravska", "Pomurska",
]

FAQ = [
    ("Zakaj zbirate poročila o snegu?",
     "Postaja IREICA1 snega ne meri. Naš poskusni model MTR sneg v dolini napoveduje, a ga ne moremo primerjati z izmerjenim. "
     "Vaša poročila pokažejo, kje je sneg dejansko ležal, in so zato koristna za preverjanje modela."),
    ("Je poročilo bralca meritev ali uradna informacija?",
     "Ne. Je opažanje posameznika, ki ga ne moremo preveriti. Za ukrepanje veljajo uradna opozorila ARSO in stanje cest na promet.si."),
    (f"Kdaj stran pokaže sodbo za območje?",
     f"Ko so za isto regijo in višinski pas v zadnjih 24 urah vsaj {MIN_N} poročila in jih vsaj {MIN_SHARE} % pove isto. "
     "Sicer piše »premalo poročil« ali »poročila se razhajajo«. Tako ena napačna ali šaljiva oddaja ne more spremeniti slike."),
    ("Kaj izberem za višinski pas?",
     "Nadmorsko višino kraja, kjer ste. Postaja IREICA1 v Rečici ob Savinji stoji na 366 m, ARSO postaja Gornji Grad na 428 m "
     "in Radegunda na 794 m. Če višine ne veste, jo poiščite na zemljevidu ali izberite najbližji pas."),
    ("Kaj shranite o meni?",
     "Samo čas (na minuto), regijo, višinski pas in stanje. Imena, kraja, lokacije, naslova IP in naprave v zapisu ni. "
     "Za omejitev zlorab strežnik za 2 uri hrani kratko oznako, sestavljeno iz naslova IP in izbranega območja, ki se sama izbriše. "
     "V brskalniku si zapomnimo samo vašo izbiro regije in pasu."),
    ("Zakaj ne morem poročati večkrat?",
     "Za isto regijo in isti višinski pas je poročilo z iste naprave mogoče enkrat na 2 uri. Eno stanje naj bo en glas, ne en klik."),
]


def build_body():
    reg_opts = "".join(f'<option value="{_html.escape(r)}">{_html.escape(r)}</option>' for r in REGIJE)
    pas_opts = "".join(
        f'<label class="sn-pas"><input type="radio" name="sn-pas" value="{p}"><span>{_html.escape(l)}</span></label>'
        for p, l in PASOVI)
    st_btns = "".join(
        f'<button type="button" class="sn-btn sn-{s}" data-stanje="{s}">{_html.escape(l)}</button>' for s, l in STANJA)
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ
    ) + "\n  </div>"
    js = JS.replace("__API__", WORKER_BASE) \
        .replace("__STANJA__", json.dumps({s: l for s, l in STANJA}, ensure_ascii=False)) \
        .replace("__PASOVI__", json.dumps({p: l for p, l in PASOVI}, ensure_ascii=False)) \
        .replace("__MINN__", str(MIN_N))
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Zima", "/zima/"), ("Poročila o snegu", None)])}
  <h1 class="page-title">Ali je pri vas sneg? Poročila bralcev</h1>
  <p class="post-meta">Anonimno, en dotik · pregled zadnjih 24 ur</p>
  <p class="archive-intro">Postaja v Rečici snega ne meri, zato je vaš dotik edini način, da vemo, kje je sneg res ležal.
  Izberite, kje ste, in povejte, kakšno je stanje. Poročilo je <b>opažanje bralca</b>, ne meritev in ne uradna informacija;
  za razmere na cestah glejte <a href="https://www.promet.si/">promet.si</a>, za napoved pa
  <a href="/zima/snezna-karta/">snežno karto</a> in <a href="/zima/">zimske strani</a>.</p>
  <style>
  .sn-wrap{{display:grid;gap:.9rem;margin:1rem 0}}
  .sn-row{{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center}}
  .sn-row select{{min-height:44px;padding:.4rem .6rem;border-radius:10px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);font-size:1rem}}
  .sn-pas{{display:inline-flex}}
  .sn-pas input{{position:absolute;opacity:0;width:1px;height:1px}}
  .sn-pas span{{display:inline-block;min-height:44px;line-height:44px;padding:0 .9rem;border-radius:99px;border:1px solid var(--card-border,var(--border));cursor:pointer;font-size:.95rem}}
  .sn-pas input:checked+span{{background:var(--blue,#3987e5);color:#fff;border-color:transparent}}
  .sn-pas input:focus-visible+span{{outline:2px solid var(--blue,#3987e5);outline-offset:2px}}
  .sn-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem}}
  .sn-btn{{min-height:64px;font-size:1.05rem;font-weight:600;border-radius:14px;border:1px solid var(--card-border,var(--border));background:var(--card-bg);color:var(--text);cursor:pointer}}
  .sn-btn:hover,.sn-btn:focus-visible{{border-color:var(--blue,#3987e5);outline:none}}
  .sn-btn[disabled]{{opacity:.55;cursor:default}}
  .sn-msg{{min-height:1.4em;font-size:.9rem}}
  .sn-cell{{display:flex;flex-wrap:wrap;gap:.2rem .8rem;justify-content:space-between;align-items:baseline;padding:.7rem .9rem;margin-bottom:.5rem;border:1px solid var(--card-border,var(--border));border-radius:12px;background:var(--card-bg)}}
  .sn-cell b{{font-weight:600}}
  .sn-verdict{{font-weight:600}}
  .sn-meta{{flex-basis:100%;font-size:.82rem;color:var(--muted)}}
  @media(min-width:560px){{.sn-grid{{grid-template-columns:repeat(4,minmax(0,1fr))}}}}
  </style>
  <div class="card sn-wrap" id="sn-card">
    <div class="clabel">Pošljite poročilo</div>
    <input type="text" id="sn-website" autocomplete="off" tabindex="-1" style="position:absolute;left:-9999px" aria-hidden="true">
    <div class="sn-row">
      <label for="sn-regija"><b>1. Regija</b></label>
      <select id="sn-regija" aria-label="Regija">{reg_opts}</select>
    </div>
    <div class="sn-row" role="radiogroup" aria-label="Višinski pas">
      <b>2. Višina kraja</b> {pas_opts}
    </div>
    <div><b>3. Kakšno je stanje?</b> (en dotik pošlje poročilo)</div>
    <div class="sn-grid" id="sn-btns">{st_btns}</div>
    <div class="sn-msg" id="sn-msg" aria-live="polite"></div>
  </div>
  <h2>Poročila v zadnjih <span id="sn-ur">24</span> urah</h2>
  <p class="archive-intro">Sodba za območje se pokaže od {MIN_N} poročil, če jih vsaj {MIN_SHARE} % pove isto.
  <button type="button" id="sn-toggle" class="mtn-avk-link" style="margin-left:.4rem">Pokaži 72 ur</button></p>
  <div id="sn-list" aria-live="polite"><p class="archive-intro">Nalagam …</p></div>
  <noscript><p class="archive-intro">Poročila in pregled se prikažejo z JavaScriptom.</p></noscript>
{faq_html}
  <a class="back-link" href="/zima/">← Zima v dolini</a>
<script>
{js}
</script>'''


JS = r"""(function(){
  var API="__API__", STANJA=__STANJA__, PASOVI=__PASOVI__, MINN=__MINN__;
  var reg=document.getElementById("sn-regija"), msg=document.getElementById("sn-msg"), list=document.getElementById("sn-list");
  var btns=document.querySelectorAll("#sn-btns .sn-btn"), pasEls=document.querySelectorAll("input[name=sn-pas]");
  if(!reg||!list)return;
  var ur=24;
  function ls(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v);}catch(e){return null;}}
  var saved=ls("wx-sneg-kje");
  try{saved=saved?JSON.parse(saved):null;}catch(e){saved=null;}
  if(saved&&saved.regija)reg.value=saved.regija;
  if(saved&&saved.pas){pasEls.forEach(function(p){if(p.value===saved.pas)p.checked=true;});}
  function pas(){var c=document.querySelector("input[name=sn-pas]:checked");return c?c.value:"";}
  function rel(iso){
    var m=Math.floor((Date.now()-new Date(iso).getTime())/60000);
    if(m<1)return "pravkar"; if(m<60)return "pred "+m+" min";
    var h=Math.floor(m/60); return "pred "+h+" h";
  }
  var ORDER=["lezi","pada","dez-sneg","brez"];
  function render(d){
    list.innerHTML="";
    var cells=(d&&d.celice)||[];
    if(!cells.length){
      var p=document.createElement("p");p.className="archive-intro";
      p.textContent="V zadnjih "+ur+" urah ni poročil. Bodite prvi.";list.appendChild(p);return;
    }
    cells.forEach(function(c){
      var row=document.createElement("div");row.className="sn-cell";
      var h=document.createElement("b");h.textContent=c.regija+" · "+(PASOVI[c.pas]||c.pas);
      var v=document.createElement("span");v.className="sn-verdict";
      if(c.sodba){v.textContent="Večina: "+(STANJA[c.sodba]||c.sodba).toLowerCase();}
      else if(c.n<MINN){v.textContent="Premalo poročil ("+c.n+" od "+MINN+")";}
      else{v.textContent="Poročila se razhajajo";}
      var meta=document.createElement("span");meta.className="sn-meta";
      var parts=[];ORDER.forEach(function(s){if(c.stanja[s])parts.push((STANJA[s]||s).toLowerCase()+" "+c.stanja[s]);});
      meta.textContent=parts.join(" · ")+" · zadnje "+rel(c.zadnje);
      row.appendChild(h);row.appendChild(v);row.appendChild(meta);list.appendChild(row);
    });
  }
  function load(){
    fetch(API+"/sneg/porocila?ur="+ur).then(function(r){return r.json();}).then(render)
      .catch(function(){list.textContent="Pregleda ni bilo mogoče naložiti.";});
  }
  btns.forEach(function(b){
    b.addEventListener("click",function(){
      var p=pas();
      if(!p){msg.textContent="Najprej izberite višino kraja (korak 2).";return;}
      var body={stanje:b.getAttribute("data-stanje"),pas:p,regija:reg.value,website:document.getElementById("sn-website").value};
      btns.forEach(function(x){x.disabled=true;});msg.textContent="Pošiljam …";
      fetch(API+"/sneg/porocilo",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
        .then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d};});})
        .then(function(res){
          btns.forEach(function(x){x.disabled=false;});
          if(!res.ok){msg.textContent=(res.d&&res.d.error)||"Napaka pri pošiljanju.";return;}
          ls("wx-sneg-kje",JSON.stringify({regija:reg.value,pas:p}));
          msg.textContent="Hvala, poročilo je zabeleženo. Pregled spodaj se posodobi, ko je dovolj glasov.";
          load();
        })
        .catch(function(){btns.forEach(function(x){x.disabled=false;});msg.textContent="Napaka pri pošiljanju, poskusite znova.";});
    });
  });
  document.getElementById("sn-toggle").addEventListener("click",function(){
    ur=ur===24?72:24;document.getElementById("sn-ur").textContent=String(ur);
    this.textContent=ur===24?"Pokaži 72 ur":"Pokaži 24 ur";load();
  });
  load();
})();"""


def main():
    title = "Ali je pri vas sneg? Poročila bralcev"
    desc = ("Anonimna poročila bralcev o snegu po regijah in višinskih pasovih: sneg leži, sneži ali ga ni. "
            "Opažanja, ne meritve; pomagajo preverjati napoved snega.")
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published="2026-11-18"),
        seo.crumbs_schema([("Meteorec", "/"), ("Zima", "/zima/"), ("Poročila o snegu", None)]),
        seo.faq_schema(FAQ),
    ])
    page = seo.page_shell(title, desc, URL, schema, build_body())
    seo.write_page("zima/sneg-porocila/index.html", page, force=True)
    print("  → zima/sneg-porocila/index.html")


if __name__ == "__main__":
    main()
