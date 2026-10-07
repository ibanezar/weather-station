#!/usr/bin/env python3
"""
tools/generate_nevihte_porocila_page.py — /nevihte/porocila/

Javna, MODERIRANA poročila bralcev o neurjih (toča, naliv, veter, strele,
tornado). Ideja po neurje.si; izvedba po našem vzorcu (glej CLAUDE.md,
razdelek »Poročila o neurjih«):

- Obrazec pošlje poročilo na worker (`POST /nevihte/porocilo`), kjer čaka na
  odobritev. Javni seznam (`GET /nevihte/porocila`) vrne samo odobrena.
- Kraj + regija, brez GPS in brez fotografij (fotografije bi terjale lastno
  moderacijo in odstranjevanje EXIF).
- Statična stran je samo okvir (razlaga, FAQ); seznam se ne da izrisati
  strežniško, ker se spreminja sproti, zato ga JS prenese ob nalaganju.
- Poročilo bralca NI uradno opozorilo in ni meritev postaje — stran to pove.

TIPI in REGIJE sta namerna podvojitev worker.js (NP_TIPI, NP_REGIJE) —
tools/test_parity.py ju primerja.

Usage:
  python3 tools/generate_nevihte_porocila_page.py
"""
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"

TIPI = [
    ("naliv", "🌧️ Naliv"),
    ("veter", "🌬️ Silovit veter"),
    ("strele", "⚡ Strele"),
    ("toca", "🟠 Toča"),
    ("nevihta", "⛈️ Neurje"),
    ("tornado", "🌪️ Tornado"),
]
REGIJE = [
    "Savinjska", "Koroška", "Gorenjska", "Osrednjeslovenska", "Zasavska", "Posavska",
    "Jugovzhodna Slovenija", "Primorsko-notranjska", "Goriška", "Obalno-kraška",
    "Podravska", "Pomurska",
]

FAQ = [
    ("Ali je poročilo bralca uradno opozorilo?",
     "Ne. Poročilo je opažanje posameznika, ki ga pred objavo pregledamo, a ga ne moremo preveriti. "
     "Za ukrepanje veljajo opozorila ARSO in navodila civilne zaščite."),
    ("Zakaj poročilo ni takoj vidno?",
     "Vsako poročilo pred objavo pregleda urednik. Tako ostane seznam uporaben in brez zlorab."),
    ("Zakaj ne morem dodati fotografije ali natančne lokacije?",
     "Zaenkrat zbiramo samo vrsto pojava, regijo in kraj. Fotografije bi terjale lastno moderacijo in "
     "odstranjevanje podatkov o lokaciji iz datotek, natančna lokacija pa bi razkrila zasebna zemljišča."),
    ("Ali moram imeti račun?",
     "Ne. Prijava ni potrebna; poročilo zavarujemo pred zlorabami s skritim poljem in omejitvijo "
     "števila poročil na uro."),
]


def build_body():
    tip_opts = "".join(f'<option value="{t}">{_html.escape(l)}</option>' for t, l in TIPI)
    reg_opts = "".join(f'<option value="{_html.escape(r)}">{_html.escape(r)}</option>' for r in REGIJE)
    labels = json.dumps({t: l for t, l in TIPI}, ensure_ascii=False)
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ
    ) + "\n  </div>"
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Nevihte", "/nevihte/"), ("Poročila o neurjih", None)])}
  <h1 class="page-title">Poročila o neurjih — kaj se dogaja v Sloveniji</h1>
  <p class="post-meta">Opažanja bralcev, pregledana pred objavo · seznam zadnjih 48 ur</p>
  <p class="archive-intro">Si opazil točo, naliv, močan veter, strele ali tornado? Sporoči, kje — pomagaš drugim
  in nam pri ocenjevanju nevihtne karte. Poročilo je <b>opažanje bralca</b>, ne meritev postaje in ne uradno
  opozorilo. Za razmere v Rečici glej <a href="/nevihte/">nevihtno napoved</a>.</p>
  <div class="card" id="np-card" style="margin-bottom:1rem">
    <div class="clabel">🌩 Pošlji poročilo</div>
    <form id="np-form" style="display:grid;gap:.6rem;margin-top:.6rem">
      <input type="text" id="np-website" name="website" autocomplete="off" tabindex="-1"
        style="position:absolute;left:-9999px" aria-hidden="true">
      <select id="np-tip" required aria-label="Kaj si opazil?"><option value="">Kaj si opazil?</option>{tip_opts}</select>
      <select id="np-regija" required aria-label="Regija"><option value="">Katera regija?</option>{reg_opts}</select>
      <input type="text" id="np-kraj" placeholder="Kraj (naselje)" maxlength="60" required>
      <input type="text" id="np-opis" placeholder="Kratek opis, npr. velikost toče (neobvezno)" maxlength="300">
      <button type="submit" class="mtn-avk-link" style="justify-self:start">Pošlji poročilo</button>
    </form>
    <div id="np-msg" aria-live="polite" style="margin-top:.5rem;font-size:.85rem"></div>
  </div>
  <h2>Zadnja potrjena poročila</h2>
  <div id="np-list" aria-live="polite"><p class="archive-intro">Nalagam …</p></div>
  <noscript><p class="archive-intro">Seznam poročil se prikaže z JavaScriptom.</p></noscript>
{faq_html}
  <a class="back-link" href="/nevihte/">← Nevihtna napoved</a>
<script>
(function(){{
  var API="{WORKER_BASE}";
  var TIPI={labels};
  var form=document.getElementById("np-form");
  if(!form)return;
  var msg=document.getElementById("np-msg"), list=document.getElementById("np-list");
  function rel(iso){{
    var m=Math.floor((Date.now()-new Date(iso).getTime())/60000);
    if(m<1)return "pravkar"; if(m<60)return "pred "+m+" min";
    var h=Math.floor(m/60); if(h<24)return "pred "+h+" h";
    return "pred "+Math.floor(h/24)+" dnevi";
  }}
  // Vse besedilo je uporabniški vnos — samo textContent, nikoli innerHTML z nizom.
  function render(items){{
    list.innerHTML="";
    if(!items.length){{
      var p=document.createElement("p"); p.className="archive-intro";
      p.textContent="Zadnjih 48 ur ni potrjenih poročil."; list.appendChild(p); return;
    }}
    items.forEach(function(o){{
      var row=document.createElement("div"); row.className="card"; row.style.marginBottom=".5rem";
      var h=document.createElement("strong"); h.textContent=(TIPI[o.tip]||o.tip)+" · "+o.kraj;
      var meta=document.createElement("div"); meta.style.cssText="font-size:.8rem;color:var(--muted)";
      meta.textContent=o.regija+" · "+rel(o.ts);
      row.appendChild(h); row.appendChild(meta);
      if(o.opis){{ var d=document.createElement("div"); d.textContent=o.opis; row.appendChild(d); }}
      list.appendChild(row);
    }});
  }}
  function load(){{
    fetch(API+"/nevihte/porocila?ur=48").then(function(r){{return r.json();}})
      .then(function(d){{ render(d.porocila||[]); }})
      .catch(function(){{ list.textContent="Seznama ni bilo mogoče naložiti."; }});
  }}
  form.addEventListener("submit",function(ev){{
    ev.preventDefault();
    var btn=form.querySelector("button[type=submit]");
    var body={{tip:document.getElementById("np-tip").value,regija:document.getElementById("np-regija").value,
      kraj:document.getElementById("np-kraj").value.trim(),opis:document.getElementById("np-opis").value.trim(),
      website:document.getElementById("np-website").value}};
    if(!body.tip||!body.regija||!body.kraj){{ msg.textContent="Izberi pojav, regijo in vpiši kraj."; return; }}
    btn.disabled=true; msg.textContent="Pošiljam …";
    fetch(API+"/nevihte/porocilo",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(body)}})
      .then(function(r){{return r.json().then(function(d){{return {{ok:r.ok,d:d}};}});}})
      .then(function(res){{
        btn.disabled=false;
        if(!res.ok){{ msg.textContent=(res.d&&res.d.error)||"Napaka pri pošiljanju."; return; }}
        msg.textContent="Hvala! Poročilo čaka na pregled in bo kmalu objavljeno.";
        form.reset();
      }})
      .catch(function(){{ btn.disabled=false; msg.textContent="Napaka pri pošiljanju — poskusi znova."; }});
  }});
  load();
}})();
</script>'''


def main():
    url = "/nevihte/porocila/"
    title = "Poročila o neurjih — toča, naliv, veter, strele"
    desc = ("Opažanja bralcev o toči, nalivih, močnem vetru, strelah in tornadih po Sloveniji. "
            "Poročila pregleda urednik pred objavo; niso uradno opozorilo.")
    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-10-07"),
        seo.crumbs_schema([("Meteorec", "/"), ("Nevihte", "/nevihte/"), ("Poročila o neurjih", None)]),
        seo.faq_schema(FAQ),
    ])
    page = seo.page_shell(title, desc, url, schema, build_body())
    seo.write_page("nevihte/porocila/index.html", page, force=True)
    print("  → nevihte/porocila/index.html")


if __name__ == "__main__":
    main()
