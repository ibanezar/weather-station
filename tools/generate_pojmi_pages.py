#!/usr/bin/env python3
"""
/pojmi/ — kratki vremenski pojmi z odgovorom v prvih dveh stavkih in eno številko
s postaje IREICA1 (inverzija, kumulonimbus, vetrna roža, hladna fronta, barometer,
albedo).

Zakaj: Search Console (18. 6.–15. 10. 2026) kaže poizvedbe »inverzija« (129 prikazov),
»temperaturna inverzija« (75), »kumulonimbus« (133), »vetrna roža« (182), »hladna fronta«
(347), »barometer« (118), »albedo« (173) na položaju 8–9, a skoraj brez klikov: ustrezne
strani nismo imeli ali je bila le del daljšega članka. Vsaka stran odgovori na pojem
in pove, kaj o njem kaže naša postaja.

Številke so iz history.json (samo prave meritve, brez ERA5 ocen); vsaka stran pove, na
koliko dneh stoji. Brez klicev na zunanje vire. Teče mesečno v seo-smart-routine.yml
(številke se skoraj ne spreminjajo), ročno po spremembi besedila.
"""
import datetime
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_seo_pages import (  # noqa: E402
    ROOT, MES_GEN, page_shell, crumbs_html, crumbs_schema, faq_schema,
    webpage_schema, num, load_history, stn_badge,
)

HUB_URL = "/pojmi/"


def fmt_date(iso):
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f"{d}. {MES_GEN[m]} {y}"


def real_days(hist):
    """Dnevi s pravo meritvijo postaje (brez ERA5 nadomestkov)."""
    return {k: v for k, v in hist.items() if v.get("src") != "era5"}


# ── Številke s postaje ───────────────────────────────────────────────────────

def fact_inverzija(hist):
    d = real_days(hist)
    winter = [v for k, v in d.items()
              if k[5:7] in ("12", "01", "02") and v.get("pressureAvg") is not None
              and v.get("tempHigh") is not None and v.get("tempLow") is not None]
    hi = [v["tempHigh"] - v["tempLow"] for v in winter if v["pressureAvg"] >= 1020]
    lo = [v["tempHigh"] - v["tempLow"] for v in winter if v["pressureAvg"] < 1010]
    if len(hi) < 30 or len(lo) < 30:
        return None
    return {"hi_n": len(hi), "hi": st.mean(hi), "lo_n": len(lo), "lo": st.mean(lo)}


def fact_barometer(hist):
    d = {k: v for k, v in real_days(hist).items()
         if v.get("pressureAvg") is not None and v.get("precipTotal") is not None}
    ks = sorted(d)
    all_wet, drop_wet = [], []
    for a, b in zip(ks, ks[1:]):
        if (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days != 1:
            continue
        wet = d[b]["precipTotal"] >= 1.0
        all_wet.append(wet)
        if d[b]["pressureAvg"] - d[a]["pressureAvg"] <= -5:
            drop_wet.append(wet)
    if len(drop_wet) < 30:
        return None
    pl = min((v["pressureLow"], k) for k, v in real_days(hist).items() if v.get("pressureLow"))
    ph = max((v["pressureHigh"], k) for k, v in real_days(hist).items() if v.get("pressureHigh"))
    return {"n_all": len(all_wet), "p_all": sum(all_wet) / len(all_wet),
            "n_drop": len(drop_wet), "p_drop": sum(drop_wet) / len(drop_wet),
            "low": pl, "high": ph}


def fact_front(hist):
    d = {k: v for k, v in real_days(hist).items() if v.get("tempAvg") is not None}
    best = None
    for a, b in zip(sorted(d), sorted(d)[1:]):
        if (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days != 1:
            continue
        delta = d[b]["tempAvg"] - d[a]["tempAvg"]
        if best is None or delta < best[0]:
            best = (delta, a, b)
    if not best:
        return None
    delta, a, b = best
    return {"delta": delta, "a": a, "b": b, "ta": d[a]["tempAvg"], "tb": d[b]["tempAvg"],
            "rain": d[b].get("precipTotal"), "pa": d[a].get("pressureAvg"),
            "pb": d[b].get("pressureAvg")}


def fact_cb(hist):
    d = real_days(hist)
    p = max((v["precipTotal"], k) for k, v in d.items() if v.get("precipTotal") is not None)
    n30 = sum(1 for v in d.values() if (v.get("precipTotal") or 0) >= 30)
    return {"rain": p[0], "date": p[1], "n30": n30}


def fact_albedo(hist):
    d = real_days(hist)

    def mean_month(mm):
        v = [x["solarHigh"] for k, x in d.items() if k[5:7] == mm and x.get("solarHigh")]
        return (st.mean(v), len(v)) if len(v) >= 30 else (None, len(v))
    jun, nj = mean_month("06")
    dec, nd = mean_month("12")
    if jun is None or dec is None:
        return None
    return {"jun": jun, "dec": dec, "nj": nj, "nd": nd}


# ── Strani ───────────────────────────────────────────────────────────────────

def pages(hist):
    """[{slug, title, h1, desc, answer, body_html, faq, links}] — brez ogrodja."""
    out = []

    # Inverzija
    f = fact_inverzija(hist)
    fact = ""
    if f:
        fact = (f'<p>Postaja IREICA1 ne meri višinskega profila, a pozimi (december–februar) vidimo '
                f'značilen vzorec: ob visokem tlaku (nad 1020 hPa, {f["hi_n"]} dni) je povprečni dnevni razpon '
                f'temperature {num(f["hi"])} °C, ob nizkem (pod 1010 hPa, {f["lo_n"]} dni) pa {num(f["lo"])} °C. '
                f'Jasne, mirne anticiklonske noči so tiste, ki dno doline najbolj ohladijo. To je posreden '
                f'kazalnik, ne meritev inverzije.</p>')
    out.append(dict(
        slug="inverzija",
        title="Temperaturna inverzija: kaj je in kako nastane",
        h1="Temperaturna inverzija",
        desc=("Temperaturna inverzija je stanje, ko je zrak ob tleh hladnejši od zraka više. "
              "Kako nastane, zakaj prinaša meglo in slabši zrak v dolini ter kaj kaže postaja v Rečici."),
        answer=("Temperaturna inverzija je stanje, ko je zrak ob tleh hladnejši od zraka više. "
                "Običajno temperatura z višino pada, približno 0,65 °C na 100 m; pri inverziji se to obrne."),
        body_html=f'''
  <h2>Kako nastane</h2>
  <p>Ob jasni, mirni noči tla oddajajo toploto v vesolje in se ohladijo. Hladen zrak je težji, zato zdrsi
  po pobočjih in se nabere na dnu doline, nad njim pa ostane toplejši zrak. V ozki dolini, kot je
  Zgornja Savinjska, se to zgodi pogosteje kot na odprti ravnini. Najpogosteje je to v hladni polovici
  leta in pod anticiklonom.</p>
  <h2>Kaj prinese</h2>
  <ul>
    <li><strong>Megla in nizka oblačnost</strong> v dolini, medtem ko je na višjih legah sončno.</li>
    <li><strong>Slana in zmrzal</strong> na dnu doline, ob nekaj sto metrov višje toplejšem zraku.</li>
    <li><strong>Slabši zrak</strong>: dim in izpusti ostanejo pod »pokrovom« toplejšega zraka.</li>
    <li><strong>Toplejša pobočja</strong>: zato je v dolini lahko hladneje kot na hribu nad njo.</li>
  </ul>
  <h2>Kaj kaže postaja</h2>
  {fact}
  <p>Kdaj je inverzija v dolini zares, vidite na naslovni strani, na kartici »Dolina zdaj«: iz izmerjene
  temperature v Rečici (366 m), Gornjem Gradu (428 m) in na Črnivcu (903 m) se izračuna, ali je
  zrak v dolini hladnejši od višine. Več o megli in inverziji v dolini:
  <a href="/blog/reke-megle-temperaturna-inverzija-recica-savinji.html">Reke megle in temperaturna inverzija</a>.</p>''',
        faq=[
            ("Kaj je temperaturna inverzija?",
             "Stanje, ko je zrak ob tleh hladnejši od zraka više. Običajno temperatura z višino pada."),
            ("Kdaj nastane inverzija?",
             "Običajno ob jasnih, mirnih nočeh, zlasti v hladni polovici leta in pod anticiklonom. "
             "Hladen zrak se nabere na dnu doline."),
            ("Zakaj je ob inverziji v dolini megla?",
             "Hladen zrak na dnu doline se ohladi do rosišča, vlaga se kondenzira, topel zrak nad njim pa "
             "preprečuje, da bi se megla dvignila."),
        ],
        links=[("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji: mikroklima doline"),
               ("/kakovost-zraka/", "Kakovost zraka"), ("/", "Dolina zdaj (naslovna stran)")],
    ))

    # Kumulonimbus
    f = fact_cb(hist)
    fact = ""
    if f:
        fact = (f'<p>Največ dežja v enem dnevu je postaja izmerila {fmt_date(f["date"])}: {num(f["rain"])} mm. '
                f'Dni z 30 mm ali več je bilo doslej {f["n30"]}. Takšne količine praviloma prinesejo ravno nevihte '
                f'ali dolgotrajnejše frontalne padavine; razlike ne moremo brati iz dnevne vsote.</p>')
    out.append(dict(
        slug="kumulonimbus",
        title="Kumulonimbus: nevihtni oblak in kako ga prepoznati",
        h1="Kumulonimbus",
        desc=("Kumulonimbus (Cb) je visok nevihtni oblak s plohami, streli, točo in sunki vetra. "
              "Kako nastane, kako ga prepoznate in kaj to pomeni v Zgornji Savinjski dolini."),
        answer=("Kumulonimbus (kratica Cb) je visok nevihtni oblak, ki raste navpično več kilometrov visoko. "
                "Prinaša plohe, strele, pogosto točo in sunke vetra."),
        body_html=f'''
  <h2>Kako nastane</h2>
  <p>Potrebuje tri stvari: vlažen zrak ob tleh, nestabilno ozračje (zrak, ki se ob dvigu ne ohlaja prehitro
  nazaj) in dvig, ki gibanje sproži, na primer segreta tla, pobočje ali hladna fronta. Dvigajoči se zrak
  se ohlaja, vodna para kondenzira, sproščena toplota pa dviganje še okrepi. Vrh oblaka lahko seže do
  10–12 km, zgoraj se razširi v značilno »nakovalo« iz ledenih kristalov.</p>
  <h2>Kako ga prepoznate</h2>
  <ul>
    <li>Kopičast oblak, ki hitro raste navzgor (to je predstopnja kumulonimbusa).</li>
    <li>Temna, ravna baza in plohe pod njo.</li>
    <li>Nakovalo ali vlaknast vrh. Če slišite grmenje, je strela dovolj blizu, da je nevarna.</li>
  </ul>
  <h2>Kaj kaže postaja</h2>
  {fact}
  <p>Trenutne strele in nevihtne razmere za dolino so na strani <a href="/nevihte/">Nevihte</a>, toča pa na
  <a href="/toca/">Toča</a>. To niso uradna opozorila: ob nevarnih razmerah spremljajte ARSO.
  Slikovni vodnik po oblakih je med gradivi <a href="/sola/kljuc-oblakov/">Meteorec Šola</a>.</p>''',
        faq=[
            ("Kaj pomeni kratica Cb?",
             "Kumulonimbus, latinsko cumulonimbus: nevihtni oblak z navpično rastjo."),
            ("Kako visok je kumulonimbus?",
             "Vrh lahko doseže 10–12 km, v tropih še više. Baza je običajno nekaj sto metrov do dva kilometra nad tlemi."),
            ("Koliko časa traja posamezna nevihtna celica?",
             "Posamezna celica običajno živi od pol ure do ure. Daljše nevihte so sestavljene iz več celic "
             "ali iz organiziranih sistemov."),
        ],
        links=[("/nevihte/", "Nevihte: karta in strele"), ("/toca/", "Toča"),
               ("/sola/kljuc-oblakov/", "Ključ oblakov")],
    ))

    # Vetrna roža
    out.append(dict(
        slug="vetrna-roza",
        title="Vetrna roža: kako jo preberete",
        h1="Vetrna roža",
        desc=("Vetrna roža pokaže, iz katerih smeri in kako pogosto piha veter. Kako jo preberete in "
              "kje najdete vetrno rožo za Rečico ob Savinji."),
        answer=("Vetrna roža je diagram, ki pokaže, iz katerih smeri veter piha in kako pogosto. "
                "Najdaljši krak kaže prevladujočo smer, torej tisto, od koder piha najpogosteje."),
        body_html='''
  <h2>Kako jo preberete</h2>
  <ul>
    <li><strong>Smer pomeni, od koder piha.</strong> Krak proti zahodu pomeni zahodni veter, ki piha z zahoda proti vzhodu.</li>
    <li><strong>Dolžina kraka</strong> je delež časa (ali število meritev) v tej smeri. Daljši krak, pogostejši veter.</li>
    <li><strong>Barve ali odseki</strong> razdelijo krak po hitrosti: kratki šibki sunki, dolgi pa močnejši.</li>
    <li><strong>Zatišje</strong> se običajno vpiše posebej, ker brez vetra smeri ni.</li>
  </ul>
  <h2>Zakaj se razlikuje od kraja do kraja</h2>
  <p>V dolinah teren usmerja veter, zato se pogosto kaže en ali dva izrazita kraka vzdolž doline, ne glede
  na splošni veter nad njo. Roža za nižino ali greben izgleda drugače kot roža za dno ozke doline.
  Za oceno vetra na določenem mestu zato ne zadošča roža iz drugega kraja.</p>
  <h2>Kje najdete našo</h2>
  <p>Na <a href="/">naslovni strani</a> je kartica »Roža vetrov – zadnjih 7 dni« iz meritev postaje IREICA1
  v Rečici ob Savinji. Merjenje vetra v dolini ni enako kot na odprtem prostoru: okolica postaje
  (zgradbe, drevesa) vpliva na vrednosti. Merjenje vetra z domačo vetrnico je opisano v gradivu
  <a href="/sola/veter-vetrnica/">Veter: vetrnica in merilnik vetra</a>.</p>''',
        faq=[
            ("Ali vetrna roža kaže smer, od koder piha, ali kamor piha?",
             "Od koder piha. Krak proti zahodu pomeni zahodni veter."),
            ("Kaj je prevladujoča smer vetra?",
             "Smer, iz katere veter piha najpogosteje v opazovanem obdobju."),
            ("Zakaj roža vetrov za dolino kaže vzdolž doline?",
             "Pobočja doline usmerjajo zračni tok, zato je veter pogosto poravnan z dolino."),
        ],
        links=[("/", "Roža vetrov (naslovna stran)"), ("/sola/veter-vetrnica/", "Vetrnica in merilnik vetra")],
    ))

    # Hladna fronta
    f = fact_front(hist)
    fact = ""
    if f:
        fact = (f'<p>Največji padec povprečne dnevne temperature iz enega dneva v drugega je postaja izmerila '
                f'{fmt_date(f["a"])} → {fmt_date(f["b"])}: s {num(f["ta"])} °C na {num(f["tb"])} °C '
                f'(razlika {num(abs(f["delta"]))} °C). Padlo je {num(f["rain"])} mm dežja, povprečni '
                f'zračni tlak je bil {num(f["pa"], 0)} hPa pred in {num(f["pb"], 0)} hPa po prehodu. '
                f'Primer ni dokaz o fronti (postaja front ne meri), le značilna slika.</p>')
    out.append(dict(
        slug="hladna-fronta",
        title="Hladna fronta: kaj je in kaj prinese",
        h1="Hladna fronta",
        desc=("Hladna fronta je meja, kjer hladen zrak izpodrine toplejšega. Kaj prinese (padec temperature, "
              "plohe, veter) in kako se pozna na postaji v Rečici."),
        answer=("Hladna fronta je meja, kjer hladnejši zrak izpodrine toplejšega. Po prehodu običajno "
                "temperatura pade, veter se obrne in nebo se razjasni."),
        body_html=f'''
  <h2>Kaj se zgodi ob prehodu</h2>
  <ul>
    <li><strong>Pred fronto:</strong> topleje, tlak pada, veter se krepi.</li>
    <li><strong>Ob fronti:</strong> plohe ali nevihte, sunki vetra, hiter obrat smeri.</li>
    <li><strong>Za fronto:</strong> hladneje, tlak spet naraste, veter se obrne in pogosto je jasneje.</li>
  </ul>
  <h2>Zakaj so plohe</h2>
  <p>Hladen zrak se vrine pod toplejšega in ga potisne navzgor. Če je topel zrak vlažen in
  nestabilen, se v njem razvijejo kopičasti oblaki; v poletni polovici leta so to lahko
  <a href="/pojmi/kumulonimbus/">kumulonimbusi</a>.</p>
  <h2>Kaj kaže postaja</h2>
  {fact}
  <p>Prihod fronte se pogosto najavi s padanjem tlaka (glej <a href="/pojmi/barometer/">barometer</a>).
  Napoved za naslednje dni je na <a href="/vreme-recica-ob-savinji/">Vreme Rečica ob Savinji</a>.</p>''',
        faq=[
            ("Kako se hladna fronta razlikuje od tople?",
             "Pri hladni fronti hladen zrak izpodriva toplejšega, padavine so običajno krajše in močnejše. "
             "Pri topli fronti toplejši zrak drsi nad hladnejšega, padavine so običajno trajnejše in šibkejše."),
            ("Kaj se zgodi s temperaturo po prehodu hladne fronte?",
             "Običajno pade, pogosto za nekaj stopinj v enem dnevu. Velikost padca je odvisna od "
             "letnega časa in od razlike med zračnima masama."),
            ("Kako prepoznam prihod hladne fronte?",
             "Tlak pada, veter se krepi, na zahodu se kopičijo oblaki, po prehodu se tlak dvigne."),
        ],
        links=[("/pojmi/barometer/", "Barometer"), ("/pojmi/kumulonimbus/", "Kumulonimbus"),
               ("/nevihte/", "Nevihte")],
    ))

    # Barometer
    f = fact_barometer(hist)
    fact = ""
    if f:
        fact = (f'<p>Na naših {f["n_all"]} dneh z meritvijo je bilo {num(f["p_all"] * 100, 0)} % dni z vsaj 1 mm dežja. '
                f'Po dnevih, ko je povprečni tlak padel za 5 hPa ali več ({f["n_drop"]} dni), jih je bilo '
                f'{num(f["p_drop"] * 100, 0)} %. Padec tlaka torej dež napove nekoliko pogosteje, a ne zanesljivo: '
                f'je namig, ne obljuba. Najnižji izmerjeni dnevni tlak je {num(f["low"][0])} hPa '
                f'({fmt_date(f["low"][1])}), najvišji {num(f["high"][0])} hPa ({fmt_date(f["high"][1])}).</p>')
    out.append(dict(
        slug="barometer",
        title="Barometer in zračni tlak: kaj nam pove o vremenu",
        h1="Barometer in zračni tlak",
        desc=("Barometer meri zračni tlak. Kaj pomeni padanje in naraščanje tlaka, kolikšen je običajen tlak "
              "in kolikokrat je po padcu tlaka res dež, po meritvah iz Rečice."),
        answer=("Barometer meri zračni tlak, običajno v hektopaskalih (hPa). Padajoč tlak praviloma "
                "napoveduje poslabšanje vremena, naraščajoč izboljšanje."),
        body_html=f'''
  <h2>Kako ga brati</h2>
  <ul>
    <li><strong>Vrednost</strong>: okoli 1013 hPa je povprečje na morski gladini. Nad 1020 hPa običajno pomeni anticiklon, pod 1005 hPa ciklon.</li>
    <li><strong>Trend je pomembnejši od vrednosti</strong>: pomembno je, ali tlak pada ali narašča. Padec za okoli 3,5 hPa v 3 urah pomorske napovedi imenujejo hitro padanje.</li>
    <li><strong>Hiter padec</strong> je pogosto znak bližajoče se fronte.</li>
    <li><strong>Vremenske postaje običajno prikazujejo tlak, preračunan na morsko gladino</strong>, da je primerjava med kraji smiselna. Neposredna meritev na 366 m bi bila nižja.</li>
  </ul>
  <h2>Kaj kaže postaja</h2>
  {fact}
  <p>Trenutni tlak je na naslovni strani. Za razumevanje, kaj se zgodi ob padcu, glej
  <a href="/pojmi/hladna-fronta/">hladno fronto</a>.</p>''',
        faq=[
            ("Kaj je normalen zračni tlak?",
             "Okoli 1013 hPa na morski gladini. V Sloveniji se vrednosti običajno gibljejo med približno 990 in 1030 hPa."),
            ("Ali nizek tlak vedno pomeni dež?",
             "Ne. Nizek tlak vremenu le naklanja, a padavine so odvisne tudi od vlage, ozračja in terena."),
            ("Kaj pomeni hiter padec tlaka?",
             "Običajno se približuje fronta ali ciklon: sledi lahko veter, plohe ali nevihta."),
        ],
        links=[("/", "Zračni tlak v živo (naslovna stran)"), ("/pojmi/hladna-fronta/", "Hladna fronta"),
               ("/biovreme/", "Biovreme")],
    ))

    # Albedo
    f = fact_albedo(hist)
    fact = ""
    if f:
        fact = (f'<p>Postaja meri vpadno sončno sevanje, ne odbitega, zato albedo ne moremo izmeriti. '
                f'Lahko pa vidimo, koliko energije sploh pride: povprečni dnevni vrh sevanja je junija '
                f'{num(f["jun"], 0)} W/m² ({f["nj"]} dni), decembra pa {num(f["dec"], 0)} W/m² ({f["nd"]} dni). '
                f'Pozimi je torej na voljo približno {num(f["jun"] / f["dec"], 0)}-krat manj, od tega pa sneg odbije večino.</p>')
    out.append(dict(
        slug="albedo",
        title="Albedo: koliko sončne svetlobe odbije površje",
        h1="Albedo",
        desc=("Albedo je delež sončnega sevanja, ki ga površje odbije. Kakšen je pri snegu, travi, gozdu in vodi "
              "ter zakaj sneg v dolini ohladi noči."),
        answer=("Albedo je delež vpadnega sončnega sevanja, ki ga površje odbije nazaj. "
                "Vrednost je med 0 (vse vpije) in 1 (vse odbije)."),
        body_html=f'''
  <h2>Primeri</h2>
  <table class="stats">
    <tr><th>Sveži sneg</th><td>približno 0,8–0,9</td></tr>
    <tr><th>Trava, polje</th><td>približno 0,15–0,25</td></tr>
    <tr><th>Gozd (iglavci)</th><td>približno 0,1</td></tr>
    <tr><th>Mirna voda</th><td>približno 0,05–0,1 (višje pri nizkem soncu)</td></tr>
    <tr><th>Zemlja kot celota</th><td>približno 0,3</td></tr>
  </table>
  <p class="muted-note">Vrednosti so tipični razponi iz literature, ne meritve naše postaje.</p>
  <h2>Zakaj je pomemben</h2>
  <p>Svetla površina odbije večino svetlobe, zato se segreva počasi in sneg v soncu ne skopni tako hitro,
  kot bi pričakovali. Sneg hkrati slabo prevaja toploto iz tal, zato se njegova površina ponoči močno
  ohladi. Snežna odeja v dolini tako krepi <a href="/pojmi/inverzija/">inverzijo</a> in zmrzal.
  Ko sneg skopni, se albedo zmanjša, tla se bolj segrejejo, sneg pa se še hitreje topi:
  to je povratna zanka albeda.</p>
  <h2>Kaj kaže postaja</h2>
  {fact}
  <p>Snežno odejo in mejo sneženja spremljamo na strani <a href="/zima/">Zima</a>.</p>''',
        faq=[
            ("Kaj je albedo?",
             "Delež vpadnega sončnega sevanja, ki ga površje odbije. Vrednost je med 0 in 1."),
            ("Kakšen je albedo snega?",
             "Za sveži sneg približno 0,8–0,9, za staro, umazano snežno odejo manj."),
            ("Zakaj je nad snegom ponoči hladneje?",
             "Sneg dobro oddaja toploto v vesolje in jo slabo prevaja iz tal, zato se zgornja plast močno ohladi."),
        ],
        links=[("/zima/", "Zima: sneg in poledica"), ("/pojmi/inverzija/", "Temperaturna inverzija")],
    ))
    return out


# ── Gradnja HTML ─────────────────────────────────────────────────────────────

def build_page(p, lastmod):
    url = f"{HUB_URL}{p['slug']}/"
    crumbs = [("Meteorec", "/"), ("Vremenski pojmi", HUB_URL), (p["h1"], None)]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in p["faq"]) + "\n  </div>"
    links = "\n".join(f'    <li><a href="{h}">{t}</a></li>' for h, t in p["links"])
    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">{p["h1"]}</h1>
  <p class="archive-intro"><strong>Na kratko:</strong> {p["answer"]}</p>{p["body_html"]}
{faq_html}
  <h2>Naprej</h2>
  <ul>
{links}
    <li><a href="{HUB_URL}">Vsi vremenski pojmi</a></li>
  </ul>
  <p class="muted-note">Številke so izračunane iz meritev postaje IREICA1 v Rečici ob Savinji
  (zadnja posodobitev: {fmt_date(lastmod)}). Besedilo je splošna razlaga pojma, ne uradna napoved.</p>
  <a class="back-link" href="{HUB_URL}">← Vremenski pojmi</a>'''
    schema = "\n".join([
        webpage_schema(url, p["title"], p["desc"]),
        crumbs_schema(crumbs),
        faq_schema(p["faq"]),
    ])
    return page_shell(p["title"], p["desc"], url, schema, body)


def build_hub(items, lastmod):
    title = "Vremenski pojmi: inverzija, fronta, barometer"
    desc = ("Kratki odgovori na pogosta vremenska vprašanja: inverzija, kumulonimbus, vetrna roža, "
            "hladna fronta, barometer in albedo, s podatki postaje v Rečici ob Savinji.")
    crumbs = [("Meteorec", "/"), ("Vremenski pojmi", None)]
    cards = "\n".join(
        f'    <a class="phenom-card" href="{HUB_URL}{p["slug"]}/">{p["h1"]}'
        f'<div class="ph-count">{p["answer"].split(". ")[0]}.</div></a>' for p in items)
    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">Vremenski pojmi</h1>
  <p class="archive-intro">Kratki odgovori na vprašanja, ki jih bralci pogosto iščejo, vsak z eno številko
  iz meritev postaje v Rečici ob Savinji.</p>
  <div class="card-grid">
{cards}
  </div>
  <p class="muted-note">Zadnja posodobitev: {fmt_date(lastmod)}.</p>'''
    schema = "\n".join([webpage_schema(HUB_URL, title, desc), crumbs_schema(crumbs)])
    return page_shell(title, desc, HUB_URL, schema, body)


def main():
    hist = load_history()
    lastmod = max(real_days(hist))
    items = pages(hist)
    written = []
    for p in items:
        rel = os.path.join("pojmi", p["slug"], "index.html")
        os.makedirs(os.path.join(ROOT, "pojmi", p["slug"]), exist_ok=True)
        with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as fh:
            fh.write(build_page(p, lastmod))
        written.append(rel)
    os.makedirs(os.path.join(ROOT, "pojmi"), exist_ok=True)
    with open(os.path.join(ROOT, "pojmi", "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_hub(items, lastmod))
    written.append("pojmi/index.html")
    print("✓", ", ".join(written))


if __name__ == "__main__":
    main()
