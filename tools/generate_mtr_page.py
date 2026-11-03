#!/usr/bin/env python3
"""
tools/generate_mtr_page.py — /mtr/ »Kako nastaja MTR« in kartice »Kuhinja« v zavihku MTR na naslovnici.

Vsebina kuhinje (časovnica, poskusi, ki niso uspeli, čaka na podatke, ponovi sam) je ZAPISANA TU, na enem mestu,
po docs/model-recica.md. Generator iz nje naredi:
  1. samostojno stran /mtr/ (da jo najdeta iskalnik in AI asistent; zavihek na naslovnici nima svojega URL-ja),
  2. tri kartice v index.html med markerjema MTR-KUHINJA:START/END (zavihek MTR → »03 · Kuhinja«).
Ni v nobenem workflowu: ob novem poskusu ali vgrajeni spremembi popravi seznam spodaj + poglavje v dokumentu,
poženi ga in commitaj (`python3 tools/test_mtr_page.py` preveri, da je committano enako izhodu generatorja).

Števci »Čaka na podatke« se na obeh mestih naložijo v brskalniku iz data/mtr-pending.json
(tools/mtr_pending.py). Besedila s HTML entitetami (&nbsp;) so zapisana kot HTML.

Usage:
  python3 tools/generate_mtr_page.py
"""
import html as _html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

URL = "/mtr/"
REL = "mtr/index.html"
PUBLISHED = "2026-11-03"
MODIFIED = "2026-11-03"       # ročno: popravi ob vsaki spremembi vsebine spodaj
INDEX_HTML = os.path.join(seo.ROOT, "index.html")
M_START = "<!-- MTR-KUHINJA:START (tools/generate_mtr_page.py: ne urejaj ročno) -->"
M_END = "<!-- MTR-KUHINJA:END -->"

# ── Vsebina ──────────────────────────────────────────────────────────────────

# (razred pike, datum, besedilo)
HIST = [
    ("", "v1", "Ridge popravek Open-Meteo na meritvah IREICA1 (od 2024). Tmax/Tmin, verjetnost padavin, zmrzal, pas P10–P90."),
    ("h-b", "6. 10. 2026", "Več-modelni Tmax (IFS, GFS, ICON, ARPEGE): D+1 1,11→1,04, D+2 1,34→1,24, D+3 1,53→1,40&nbsp;°C. Pri Tmin je dobitek šum, zato tam ni vklopljeno."),
    ("h-b", "6. 10. 2026", "Verjetnost zmrzali in razlog za popravek (jasna in mirna noč, oblačno). Backtest 366 dni, 99 zmrzalnih noči: Brierjeva ocena 0,07 proti 0,20 pri klimatologiji (manj je bolje). V srednjem območju (30–70&nbsp;%) je zmrzal pogostejša od napovedi."),
    ("h-v", "23. 10. 2026", "Ločen pas negotovosti Tmax po vrsti noči (jasna / oblačna): pokritost 72–81&nbsp;% v vseh razredih."),
    ("h-v", "23. 10. 2026", "Živa osvežitev: kartice na strani berejo napoved, osveženo štirikrat na dan ob novih tekih Open-Meteo. Semafor točnosti meri naprej samo zamrznjeno jutranjo napoved. Ali so poznejše osvežitve boljše, še ne vemo: dnevnik teče, za sklep je treba vsaj 20 dni na razred."),
    ("h-a", "24. 10. 2026", "Veter in sunki, umerjeni na postajo. Postaja stoji na zavetrnem dnu doline, zato Open-Meteo povprečni veter precenjuje za polovico (razmerje 0,50). Povprečni veter popravi že skala; pri sunkih je napaka D+1 3,9 proti 7,1&nbsp;km/h pri surovem modelu. Na semaforju ga ni, ker tam veter ni merjen."),
    ("h-a", "24. 10. 2026", "Začetek beleženja pravih napovedi višinskega profila, oblačnosti po slojih in snega (D+1 do D+3). Open-Meteo za te spremenljivke nima arhiva, zato jih zbiramo sproti. Ocena koristi je mogoča šele po zimi 2026/27."),
    ("h-t", "2. 11. 2026", "Krivulja na junaški kartici je zasidrana na zadnjo meritev: razlika meritev – model izzveni v 6 urah. To je samo prikaz in ne vpliva na točnost."),
    ("h-t", "3. 11. 2026", "Čas izzvenevanja zasidranja je prvič izmerjen (13. 7.–1. 11., okoli 108 dni, napoved izpred dneva): utež napake pade z 0,88 po 1 uri na 0,34 po 6 urah in 0,14 po 12 urah, kar je bližje linearnemu izzvenevanju čez 9 ur kot čez 6. Povprečna MAE čez 1–12 ur: brez zasidranja 1,69&nbsp;°C, 6 ur 1,52&nbsp;°C, 9 ur 1,50&nbsp;°C. Razlika med 6 in 9 urami (0,02&nbsp;°C) je v mejah šuma, zato ostaja 6 ur."),
]

CHIPS = {"slabse": ("Slabše", "c-red"), "brez": ("Brez dobitka", "c-gray"),
         "uhaj": ("Uhajanje", "c-amb"), "premalo": ("Premalo podatkov", "c-vio")}

# (izid, naslov, datum, besedilo)
NEG = [
    ("slabse", "LightGBM nad arhivom več modelov", "6. 10.", "Slabši od v1: Tmin D+2 1,40 proti 1,27&nbsp;°C."),
    ("brez", "Predhodno učenje na 7 letih ERA5", "6. 10.", "Dobitek največ 0,007&nbsp;°C čez prejšnjo vrstico."),
    ("brez", "Kazalnik zaupanja iz razhajanja modelov", "6. 10.", "Povezava med razhajanjem in napako je šibka (Spearman 0,04–0,19), pri Tmin D+1 in D+3 je ni. Semafor, ki ne napove napake, bi bil laž, zato ga ni."),
    ("brez", "Verjetnost padavin: LightGBM in povprečje z v1", "6. 10.", "Brierjeva ocena D+1 0,172→0,165, D+2 in D+3 brez dobitka."),
    ("brez", "Značilke po režimu noči", "23. 10.", "Jasna in mirna noč, mokri dnevi, razlika temperatura – rosišče: razlika MAE od –0,023 do +0,013&nbsp;°C, interval zaupanja vedno zajema 0."),
    ("brez", "Ločen pas negotovosti za Tmin in zmrzal", "23. 10.", "Brierjeva ocena zmrzali 0,0632 proti 0,0631. Pri Tmax pomaga, zato je tam vgrajen."),
    ("brez", "Sončni čas in mejna plast", "24. 10.", "Razlike MAE pod 0,01&nbsp;°C pri obeh. Sončni čas je prava napoved, ne zlepljena serija."),
    ("uhaj", "Višinski nivoji in sloji oblačnosti", "24. 10.", "Navidezni dobitek narašča z vodilnim časom, kontrola z zlepljenim »nowcastom« ga pri Tmax preseže: razložen je z uhajanjem informacije. Pri Tmin (stabilnost T925 – T2m) dobitka 0,16&nbsp;°C ni mogoče ločiti od uhajanja (strop 0,22–0,30&nbsp;°C)."),
    ("premalo", "Višina snega in vlaga tal", "24. 10.", "V vzorcu je samo 20 dni s snegom nad 1&nbsp;cm od 779. Ni ovrženo, ni preizkušljivo."),
    ("slabse", "Utež novejših dni", "24. 10.", "Polčas 90, 180 in 365 dni nikjer ne pomaga, pri 90 dneh je Tmax slabši za 0,06–0,09&nbsp;°C. Dokaza za drift postaje ni."),
    ("brez", "Krčenje popravka po režimu noči", "24. 10.", "Naučena utež je 1,0–1,2, ne pod 1: popravek nikjer ni prestrog. Slabši Tmin v »vmesnih« dnevih je lastnost teh dni, ne napaka popravka."),
    ("slabse", "Izbirnik modela po meteoblue mLM", "2. 11.", "Model, ki je bil zadnjih 3–30 dni najboljši, ni boljši napovednik jutrišnjega: Tmax D+1 1,46&nbsp;°C proti 1,39&nbsp;°C pri stalnem ICON. Koristi odštevanje nedavne napake, ki jo MTR že ima."),
]

NEG_LEAD = ("Vsi poskusi so walk-forward po mesecih na zadnjem letu (366–392 dni), razlika je preverjena z uparjenim "
            "blokovnim bootstrapom. Neuspeh objavljamo enako kot uspeh: v model niso prišli, ker ne držijo.")
NEG_KEY = [("slabse", "slabši od osnove"), ("brez", "razlika v mejah šuma"),
           ("uhaj", "dobitek razloži informacija, ki je ob napovedi ni bilo"),
           ("premalo", "ni preizkušljivo")]

PEND_LEAD = ("Odprti poskusi, ki jih zdaj ni mogoče pošteno oceniti. Vsak ima prag iz dokumentacije modela; "
             "dokler ni dosežen, ne trdimo nič.")
# (naslov, oznaka, razred, opis, ključ števca ali None)
PEND = [
    ("Ali so poznejše osvežitve boljše od jutranje napovedi?", "Zbiramo", "c-grn",
     "Živo osvežitev (štirikrat na dan) primerjamo z zamrznjeno jutranjo napovedjo na istih dneh. Sklep je mogoč šele pri vsaj 20 razrešenih dneh na razred ur do začetka dneva. Do takrat ne trdimo, da so poznejše osvežitve boljše.", "live"),
    ("Ali višinski profil izboljša Tmin?", "Zbiramo", "c-grn",
     "Stabilnost med T925 in T2m je edini kandidat s fizikalnim razlogom (nočna inverzija). Pošten odgovor terja prave napovedi izpred 1–3 dni in meritve za iste dneve, zato ga ni pred koncem zime 2026/27.", "profile"),
    ("Sneg in vlaga tal", "Čaka na zimo", "c-vio",
     'V zadnjem letu je bilo samo 20 dni s snegom nad 1&nbsp;cm od 779, kar ne zadošča za sklep. Prag ni določen: ocena je mogoča, ko bo snega dovolj za primerjavo. <em data-pend="snow"></em>', None),
    ("Pas negotovosti Tmax ob jasnih nočeh", "Brez roka", "c-gray",
     "Pri D+3 pokritost pasu P10–P90 ob jasnih nočeh je 72&nbsp;% namesto 80&nbsp;%, razred ima le 74 dni (stanje 23. 10.). Ponovitev, ko se razred poveča.", None),
    ("Ali se postaja skozi leta premika?", "2027", "c-gray",
     "Rast drevja, gradnja ali staranje senzorja bi lahko spreminjali povprečni ostanek. Za zdaj dokaza ni; poskus z utežjo novejših dni ponovimo po dveh letih meritev.", None),
    ("Čas izzvenevanja zasidranja (6 ur)", "Ponovi po zimi", "c-vio",
     "Prvi tek delovnega toka <code>mtr-anchor-eval.yml</code> (3. 11.) kaže počasnejše izzvenevanje od 6 ur, najbližje je 9 ur, a je razlika v MAE le 0,02&nbsp;°C in v mejah šuma. Meri obstojnost napake napovedi izpred dneva, ne napovedi, izdane ob meritvi, in zajame samo poletje in jesen. Ponovitev po zimi 2026/27, ko bo meritev več; do takrat ostaja 6 ur.", None),
]

# »Ponovi sam«: (poskus, ukaz, kaj potrebuje). Skripte so v tools/ai/ in niso v nobenem workflowu.
REPRO_OFFLINE = [
    ("Izbirnik modela (2. 11.)", "python3 tools/ai/eval_selector.py 2025-10-01",
     "data/forecast-archive.csv in history.json (obe v repozitoriju), brez omrežja"),
    ("Živa osvežitev proti zamrznjeni (od 24. 10.)", "python3 tools/ai/eval_live_refresh.py",
     "data/mtr-live-log.csv in forecast_verification.json, brez omrežja; do 20 dni na razred izpiše »premalo dni«"),
    ("Števci »Čaka na podatke«", "python3 tools/mtr_pending.py", "iste datoteke kot zgoraj in data/profile-forward-log.csv"),
]
REPRO_CACHE = [
    ("LightGBM nad arhivom, več-modelni Tmax (6. 10.)", "eval_mtr2.py, eval_mtr2_hourly.py, eval_mtr2_models.py"),
    ("Kazalnik zaupanja, zmrzal, padavine (6. 10.)", "eval_confidence.py, eval_frost.py, eval_mtr_calibration.py, eval_significance.py"),
    ("Značilke po režimu noči, pas negotovosti (23. 10.)", "eval_mtr3.py, eval_mtr_sd.py"),
    ("Višinski nivoji, sončni čas, mejna plast, sneg (24. 10.)", "eval_mtr4.py"),
    ("Utež novejših dni, krčenje popravka (24. 10.)", "eval_mtr5_recency.py, eval_mtr6_shrink.py"),
    ("Veter in sunki (24. 10.)", "eval_mtr7_wind.py"),
]
REPRO_NET = [
    ("Čas izzvenevanja zasidranja (2. 11.)", "python3 tools/ai/eval_anchor.py --from 2026-07-13 --lead 1",
     "omrežje (Open-Meteo) in data/hourly-observations.csv; na GitHubovem tekaču kot delovni tok mtr-anchor-eval.yml (ročni zagon, prvi rezultat 3. 11.)"),
]
DATA_FILES = [
    ("data/mtr-live-log.csv", "dnevnik živih osvežitev MTR (od 24. 10. 2026)"),
    ("data/profile-forward-log.csv", "prave napovedi višinskega profila, oblačnosti in snega (od 24. 10. 2026)"),
    ("data/forecast-archive.csv", "dnevni arhiv napovedi več modelov po vodilnem času (od 26. 5. 2024)"),
    ("data/mtr-pending.json", "števci odprtih poskusov (osvežuje se štirikrat na dan)"),
    ("model/recica-mos.json", "koeficienti modela in izmerjena veščina"),
    ("test-napovedi/podatki.csv", "razrešeni dnevi primerjave modelov proti IREICA1 (CC BY 4.0)"),
]

FAQ = [
    ("Je MTR uradna napoved?",
     "Ne. MTR je poskusni statistični model za eno točko, Rečico ob Savinji. Uradne napovedi in opozorila izdaja "
     "Agencija Republike Slovenije za okolje (ARSO)."),
    ("Kako natančen je MTR?",
     "V walk-forward preizkusu od 26. 5. 2024 do 5. 10. 2026 je povprečna absolutna napaka najvišje temperature 1,04 °C "
     "pri D+1, 1,24 °C pri D+2 in 1,40 °C pri D+3. Sprotno primerjavo z ARSO, Open-Meteo, ECMWF AIFS in WeatherNext 2 "
     "kaže stran Točnost napovedi, ki meri vsak dan proti meritvam postaje IREICA1."),
    ("Zakaj objavljate poskuse, ki niso uspeli?",
     "Ker bi sicer bilo videti, kot da vsaka zamisel deluje. Poskus, ki je v mejah šuma, ne dokazuje, da zamisel ne drži, "
     "dokazuje pa, da je na teh podatkih ne moremo uporabiti. Ob vsakem poskusu je številka in izid; pri uhajanju "
     "informacije in premalo podatkih ne trdimo ne uspeha ne neuspeha."),
    ("Ali lahko poskuse ponovim sam?",
     "Da. Skripte so v mapi tools/ai/ v repozitoriju, vhodne datoteke so javne, tabela »Ponovi sam« pa pove, kaj "
     "posamezen poskus potrebuje. Pri poskusih iz urnih arhivov je treba najprej prenesti predpomnilnik z Open-Meteo; "
     "zaradi omejitev API-ja to priporočamo na GitHubovem tekaču."),
]

REPO = "https://github.com/ibanezar/weather-station/blob/main/"
DOC_URL = REPO + "docs/model-recica.md"


# ── Kartice za naslovnico (zavihek MTR) ──────────────────────────────────────

def _chip(key):
    label, cls = CHIPS[key]
    return f'<i class="mtr-chip {cls}">{label}</i>'


def _bar(key):
    return ('<div class="mtr-pend-bar" data-pend="%s" hidden><div class="mtr-pend-track" role="progressbar" '
            'aria-valuemin="0" aria-valuenow="0" aria-valuemax="100" aria-label="Napredek zbiranja podatkov"><i></i></div>'
            '<small></small></div>' % key)


def tab_cards():
    h = "".join(
        f'        <div class="mtr-hist-row{(" " + c) if c else ""}"><b>{d}</b><span>{t}</span></div>\n'
        for c, d, t in HIST)
    n = "".join(
        f'        <div class="mtr-neg-row">{_chip(k)}<div><b>{ti}<small>{d}</small></b><span>{t}</span></div></div>\n'
        for k, ti, d, t in NEG)
    key = " · ".join(f"{_chip(k)} {t}" for k, t in NEG_KEY)
    p = "".join(
        f'        <div class="mtr-pend-row"><div class="mtr-pend-hd"><b>{ti}</b><i class="mtr-chip {cc}">{ch}</i></div>'
        f'<span>{de}</span>{_bar(k) if k else ""}</div>\n'
        for ti, ch, cc, de, k in PEND)
    icon = '<svg class="ic" aria-hidden="true"><use href="#i-target"/></svg>'
    return (
        '    <div class="card mtr-quiet" style="margin-bottom:1.25rem">\n'
        f'      <div class="clabel" style="margin:0 0 .6rem">{icon} Kako je nastal</div>\n'
        '      <div class="mtr-hist" id="mos-hist">\n' + h + '      </div>\n    </div>\n\n'
        '    <div class="card mtr-quiet" style="margin-bottom:1.25rem">\n'
        f'      <div class="clabel" style="margin:0 0 .6rem">{icon} Poskusi, ki niso uspeli</div>\n'
        f'      <p class="mtr-neg-lead">{NEG_LEAD}</p>\n'
        f'      <p class="mtr-neg-key">{key}</p>\n'
        '      <div class="mtr-neg" id="mos-neg">\n' + n + '      </div>\n'
        f'      <p class="mtr-note">Skripte so v <code>tools/ai/</code>, podrobnosti in vse številke v '
        f'<a href="{DOC_URL}">docs/model-recica.md</a>.</p>\n'
        '    </div>\n\n'
        '    <div class="card mtr-quiet" style="margin-bottom:1.25rem">\n'
        f'      <div class="clabel" style="margin:0 0 .6rem">{icon} Čaka na podatke</div>\n'
        f'      <p class="mtr-neg-lead">{PEND_LEAD}</p>\n'
        '      <div class="mtr-pend" id="mos-pend">\n' + p + '      </div>\n'
        '      <p class="mtr-note" id="mos-pend-note"></p>\n'
        '    </div>\n\n'
        f'    <a href="{URL}" class="mtn-avk-link" style="margin-bottom:1.25rem">Celotna zgodba z ukazi za ponovitev →</a>\n')


def inject_tab(path=INDEX_HTML):
    s = open(path, encoding="utf-8").read()
    block = f"    {M_START}\n{tab_cards()}    {M_END}\n"
    pat = re.compile(r"[ \t]*" + re.escape("<!-- MTR-KUHINJA:START") + r".*?" + re.escape(M_END) + r"\n", re.S)
    if not pat.search(s):
        raise SystemExit("✗ index.html nima markerjev MTR-KUHINJA:START/END")
    out = pat.sub(lambda m: block, s, count=1)
    if out != s:
        open(path, "w", encoding="utf-8").write(out)
    return out != s


# ── Samostojna stran /mtr/ ───────────────────────────────────────────────────

EXTRA_CSS = """<style>
.mk-lead{font-size:1.05rem;line-height:1.6;margin:.2rem 0 1.4rem}
.mk-hist,.mk-neg,.mk-pend{list-style:none;margin:0 0 1.6rem;padding:0}
.mk-hist li,.mk-neg li,.mk-pend li{padding:.75rem 0;border-top:1px solid var(--border);line-height:1.55}
.mk-hist li:first-child,.mk-neg li:first-child,.mk-pend li:first-child{border-top:0}
.mk-hist b,.mk-neg b,.mk-pend b{color:var(--text)}
.mk-hist .d{display:inline-block;min-width:7.5rem;font-weight:700}
.mk-hist .d::before{content:'';display:inline-block;width:.55rem;height:.55rem;border-radius:50%;margin-right:.5rem;background:var(--green)}
.mk-hist .h-b .d::before{background:#38bdf8}.mk-hist .h-v .d::before{background:#a78bfa}
.mk-hist .h-a .d::before{background:#fbbf24}.mk-hist .h-t .d::before{background:#5eead4}
.mk-hist span.t,.mk-neg span.t,.mk-pend span.t{color:var(--muted)}
.mk-row{display:flex;gap:.6rem 1rem;flex-wrap:wrap;align-items:baseline}
.mk-chip{display:inline-block;font-style:normal;font-size:.74rem;font-weight:600;line-height:1.3;padding:.1rem .55rem;border-radius:999px;border:1px solid var(--c,#94a3b8);background:rgba(128,128,128,.12);color:var(--text);white-space:nowrap}
.mk-chip.c-red{--c:#f87171}.mk-chip.c-gray{--c:#94a3b8}.mk-chip.c-amb{--c:#fbbf24}.mk-chip.c-vio{--c:#a78bfa}.mk-chip.c-grn{--c:#34d399}
.mk-neg small{margin-left:.5rem;color:var(--muted);font-weight:400}
.mk-key{font-size:.82rem;color:var(--muted);line-height:2;margin:0 0 .6rem}
.mk-bar{margin-top:.5rem}.mk-bar[hidden]{display:none}
.mk-track{height:6px;border-radius:3px;background:rgba(128,128,128,.28);overflow:hidden}
.mk-track i{display:block;height:100%;width:var(--p,0%);min-width:3px;border-radius:3px;background:#34d399}
.mk-bar small{display:block;margin-top:.3rem;font-size:.78rem;color:var(--muted)}
.mk-cmd{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;word-break:break-word}
.mk-tbl{width:100%;border-collapse:collapse;margin:.6rem 0 1.4rem;font-size:.9rem}
.mk-tbl th,.mk-tbl td{text-align:left;vertical-align:top;padding:.6rem .8rem;border-bottom:1px solid var(--border)}
.mk-tbl th{color:var(--muted);font-weight:600;font-size:.8rem}
.mk-data li{margin:.3rem 0;line-height:1.5}
</style>"""

# Namerna podvojitev renderMtrPending() v app.js (isti ključi data-pend in ista besedila; preverja test_mtr_page.py)
PEND_JS = """<script>
(function(){
  fetch('/data/mtr-pending.json?_='+Math.floor(Date.now()/36e5)).then(function(r){return r.ok?r.json():null}).catch(function(){return null}).then(function(d){
    if(!d)return;
    var root=document.getElementById('mk-pend');if(!root)return;
    function bar(key,n,target,txt){
      var el=root.querySelector('[data-pend="'+key+'"]');
      if(!el||!(target>0)||!isFinite(n))return;
      var pct=Math.max(0,Math.min(100,Math.round(n/target*100)));
      var tr=el.querySelector('.mk-track');
      tr.style.setProperty('--p',pct+'%');tr.setAttribute('aria-valuenow',String(pct));tr.setAttribute('aria-valuetext',txt);
      el.querySelector('small').textContent=txt;el.hidden=false;
    }
    var L=d.live;
    if(L&&L.classes){var v=Object.keys(L.classes).map(function(k){return L.classes[k]});
      if(v.length){var lo=Math.min.apply(null,v),hi=Math.max.apply(null,v);
        bar('live',L.best,L.target,'Najbolj zapolnjen razred: '+L.best+' od '+L.target+' dni'+(lo!==hi?' (razredi: '+lo+'–'+hi+')':''));}}
    var P=d.profile;
    if(P){bar('profile',P.winter_days,P.target,'Zimskih dni (nov–feb) v dnevniku: '+P.winter_days+' od '+P.target+' · dni zajema skupaj: '+P.days);
      var sn=root.querySelector('[data-pend="snow"]');
      if(sn&&isFinite(P.snow_days))sn.textContent='Dni s snegom nad 1 cm v dnevniku doslej: '+P.snow_days+'.';}
    var note=document.getElementById('mk-pend-note');
    if(note&&d.generated_at){var t=new Date(d.generated_at);
      if(!isNaN(t))note.textContent='Števci so izračunani iz dnevnikov v repozitoriju, stanje '+t.toLocaleDateString('sl',{day:'numeric',month:'numeric'});}
  });
})();
</script>"""


def _mk_chip(cls, label):
    return f'<i class="mk-chip {cls}">{label}</i>'


def build_body():
    hist = "".join(f'    <li class="{c}"><span class="d">{d}</span><span class="t">{t}</span></li>\n'
                   for c, d, t in HIST)
    neg = "".join(
        f'    <li><div class="mk-row"><b>{ti}<small>{d}</small></b>{_mk_chip(CHIPS[k][1], CHIPS[k][0])}</div>'
        f'<span class="t">{t}</span></li>\n' for k, ti, d, t in NEG)
    key = " · ".join(f"{_mk_chip(CHIPS[k][1], CHIPS[k][0])} {t}" for k, t in NEG_KEY)
    pend = "".join(
        f'    <li><div class="mk-row"><b>{ti}</b>{_mk_chip(cc, ch)}</div><span class="t">{de}</span>'
        + (('<div class="mk-bar" data-pend="%s" hidden><div class="mk-track" role="progressbar" aria-valuemin="0" '
            'aria-valuenow="0" aria-valuemax="100" aria-label="Napredek zbiranja podatkov"><i></i></div><small></small></div>')
           % k if k else "") + '</li>\n'
        for ti, ch, cc, de, k in PEND)
    rep_off = "".join(
        f'      <tr><td>{a}</td><td class="mk-cmd">{b}</td><td>{c}</td></tr>\n' for a, b, c in REPRO_OFFLINE)
    rep_net = "".join(
        f'      <tr><td>{a}</td><td class="mk-cmd">{b}</td><td>{c}</td></tr>\n' for a, b, c in REPRO_NET)
    rep_cache = "".join(
        f'      <tr><td>{a}</td><td class="mk-cmd">{b}</td><td>predpomnilnik urnih arhivov (glej zgoraj)</td></tr>\n'
        for a, b in REPRO_CACHE)
    data = "".join(
        f'    <li><a href="/{p}">{p}</a>: {t}</li>\n' for p, t in DATA_FILES)
    related = ('  <p class="muted-note">Sorodno: <a href="/tocnost-napovedi/">Točnost napovedi (semafor)</a> · '
               '<a href="/test-napovedi/">Test napovedi: pet virov proti postaji</a> · '
               '<a href="/trendi/">Trendi</a> · <a href="/primerjava-modelov/">Primerjava modelov</a> · '
               '<a href="/vreme-recica-ob-savinji/">Vreme v Rečici</a></p>')
    return (
        '  <h1>MTR: kako nastaja napovedni model za Rečico</h1>\n'
        f'  <p class="muted-note">Posodobljeno: 3. 11. 2026. Model: model/recica-mos.json. Postaja: IREICA1.</p>\n'
        '  <p class="mk-lead" id="mk-kratko"><strong>Na kratko:</strong> MTR (Meteorec napovedni model) je statistični '
        'popravek napovedi Open-Meteo za dno doline pri Rečici ob Savinji, naučen na meritvah postaje IREICA1. '
        'Popravlja najvišjo in najnižjo dnevno temperaturo, računa verjetnost zmrzali in pas negotovosti P10–P90 '
        'ter umerja veter in sunke. V walk-forward preizkusu od 26. 5. 2024 do 5. 10. 2026 je povprečna absolutna napaka '
        'najvišje temperature 1,04&nbsp;°C pri D+1, 1,24&nbsp;°C pri D+2 in 1,40&nbsp;°C pri D+3. Ta stran pokaže, '
        'kako je nastal, kaj smo poskusili in zavrgli, kaj še čaka na podatke in kako vse ponoviti sami.</p>\n'
        '  <h2>Kako je nastal</h2>\n  <ol class="mk-hist">\n' + hist + '  </ol>\n'
        '  <h2>Poskusi, ki niso uspeli</h2>\n'
        f'  <p>{NEG_LEAD}</p>\n  <p class="mk-key">{key}</p>\n  <ul class="mk-neg">\n' + neg + '  </ul>\n'
        '  <h2>Čaka na podatke</h2>\n'
        f'  <p>{PEND_LEAD}</p>\n  <ul class="mk-pend" id="mk-pend">\n' + pend + '  </ul>\n'
        '  <p class="muted-note" id="mk-pend-note"></p>\n'
        '  <h2>Ponovi sam</h2>\n'
        '  <p>Skripte so v mapi <code>tools/ai/</code> v repozitoriju in niso v nobenem delovnem toku. Poženite jih iz korena '
        'repozitorija; argumenti so v glavi vsake skripte. Brez omrežja delujejo prve tri vrstice, ostale potrebujejo urne arhive napovedi iz Open-Meteo, ki jih '
        'naredi <code>tools/ai/fetch_hourly_cache.py</code> (za profile <code>fetch_profile_cache.py</code>, za veter '
        '<code>fetch_wind_cache.py</code>). Iz razvojne seje z deljenim IP-jem Open-Meteo skoraj stalno vrača napako 429, '
        'zato predpomnilnik naredi na GitHubovem tekaču (primer: delovni tok <code>mtr2-eval.yml</code>).</p>\n'
        '  <div class="tbl-x" tabindex="0"><table class="mk-tbl">\n'
        '    <thead><tr><th scope="col">Poskus</th><th scope="col">Ukaz ali skripta</th><th scope="col">Potrebuje</th></tr></thead>\n'
        '    <tbody>\n' + rep_off + rep_cache + rep_net + '    </tbody>\n  </table></div>\n'
        f'  <p>Kontrolo uhajanja informacije, uparjeni blokovni bootstrap in vse številke najdete v '
        f'<a href="{DOC_URL}">docs/model-recica.md</a>.</p>\n'
        '  <h2>Podatki</h2>\n  <ul class="mk-data">\n' + data + '  </ul>\n'
        '  <p class="muted-note"><strong>Uporaba vsebine:</strong> povzemanje je dovoljeno z navedbo avtorja (Meteorec) in '
        'povezavo na to stran. Za prepis ali vdelavo grafov vprašajte. Dokaz o prvenstvu: datum objave in zgodovina '
        'sprememb v repozitoriju.</p>\n'
        + related)


def build_page():
    title = "MTR: kako nastaja napovedni model za Rečico"
    desc = ("Kako je nastal MTR, Meteorec napovedni model za dno doline pri Rečici: časovnica, poskusi, ki niso uspeli, "
            "odprta vprašanja in ukazi za ponovitev.")
    crumbs = [("Meteorec", "/"), ("MTR", None)]
    faq_html = ('  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ)
        + "\n  </div>")
    body = (f'{seo.crumbs_html(crumbs)}\n{seo.stn_badge()}\n{build_body()}\n{faq_html}\n'
            '  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>')
    wp = seo.webpage_schema(URL, title, desc, date_published=PUBLISHED,
                            speakable=["#mk-kratko"])
    wp = wp.replace(f'"datePublished":"{PUBLISHED}"', f'"datePublished":"{PUBLISHED}","dateModified":"{MODIFIED}"')
    schema = "\n".join([wp, seo.crumbs_schema(crumbs), seo.faq_schema(FAQ)])
    return seo.page_shell(title, desc, URL, schema + "\n" + EXTRA_CSS, body + "\n" + PEND_JS)


def main():
    seo.write_page(REL, build_page(), force=True)
    print(f"  → {REL}")
    print("  → index.html (kartice Kuhinja)" if inject_tab() else "  = index.html brez sprememb")
    return 0


if __name__ == "__main__":
    sys.exit(main())
