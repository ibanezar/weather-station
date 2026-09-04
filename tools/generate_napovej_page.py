#!/usr/bin/env python3
"""
tools/generate_napovej_page.py — »Prehiti model« (/napovej/)

Igra, v kateri obiskovalec vsak dan napove jutrišnjo najvišjo in najnižjo
temperaturo ter dež za Rečico ob Savinji — in ga naslednji dan oceni meritev
postaje IREICA1 po ISTEM pravilu kot ARSO, Open-Meteo, MTR in ECMWF AIFS na
semaforju /tocnost-napovedi/.

Nasprotniki niso izmišljeni. So natanko iste čakajoče napovedi, ki jih vsak
dan zabeleži tools/verify_forecasts.py v tools/.forecast_pending.json in jih
naslednji dan razreši v forecast_verification.json. Ta skript OBEH DATOTEK NE
PIŠE in napovedi ne zajema na novo — samo prebere, kar je verifikacijski
cevovod že naredil. Drug zajem bi pomenil drugo napoved pod istim imenom in
dva semaforja, ki se razideta (isto načelo kot daily_features pri MTR ali
storm_threat_score() pri nevihtni karti).

Zapiše dvoje:
  napovej/krog.json   — krog dneva, bere ga igra v brskalniku
  napovej/index.html  — krog vdelan v stran (#np-krog) + strežniško izrisan
                        obrazec, namigi, tabela zadnjih dni, pravila in FAQ

Igra ničesar ne skriva: napovedi modelov za jutri so v isti datoteki, ki jo
naloži brskalnik (in objavljene drugod po strani). Pred oddajo jih vmesnik
samo ne kaže — kdor jih prepiše, ne igra proti modelu, ampak je model.

Uporaba:
  python3 tools/generate_napovej_page.py
"""
import datetime
import html
import json
import os
import statistics as stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — skupni ovoj strani
from asset_version import asset_href  # noqa: E402

ROOT = seo.ROOT
TODAY = seo.TODAY

URL = "/napovej/"
TITLE = "Prehiti model — napovej jutrišnje vreme"
PENDING_PATH = os.path.join(ROOT, "tools", ".forecast_pending.json")
VERIFICATION_PATH = os.path.join(ROOT, "forecast_verification.json")

# Koliko razrešenih dni gre v krog. Igralčeva sezona se meri samo na dnevih, ki
# jih je igral, zato mora biti okno daljše od pričakovanega premora — 90 dni
# pomeni, da po dvomesečnem izostanku še vedno vidi svoj rezultat. Datoteka je
# pri tem majhna (~25 kB).
OKNO_DNI = 90

# Prag mokrega dneva — isti kot v verify_forecasts.py (WET_DAY_MM) in v
# napovej/napovej.js (MOKER_MM). Če ga spremeniš, spremeni na vseh treh mestih.
MOKER_MM = 0.2

# Klimatološko okno okoli koledarskega dne. ±7 dni je isto okno kot pri
# klimatološki osnovi na /test-napovedi/ — igralec dobi isto merilo, po katerem
# se tam meri, ali je napoved sploh boljša od povprečja.
KLIMA_OKNO = 7

VIRI = [
    ("arso", "ARSO"),
    ("open_meteo", "Open-Meteo"),
    ("meteorec", "MTR"),
    ("aifs", "ECMWF AIFS"),
]


def nalozi(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def napoved_vira(vir_id, d):
    """Zapis vira v obliki, ki jo pozna igra: temperaturi vedno, padavine pa v
    milimetrih (Open-Meteo, AIFS) ali kot verjetnost (MTR, `pop`). ARSO objavlja
    besedno napoved brez milimetrov — tam padavin preprosto ni in igra tega ne
    zamolči, ampak pri njem stolpec pusti prazen."""
    if not d:
        return None
    out = {"tmax": d.get("tmax"), "tmin": d.get("tmin")}
    if d.get("precip") is not None:
        out["dez"] = d.get("precip")
    if d.get("pop") is not None:
        out["pop"] = d.get("pop")
    if vir_id == "meteorec" and d.get("model_version"):
        out["verzija"] = d.get("model_version")
    return out


def krog_modelov(pending, tarca):
    """Napovedi vseh virov za tarčni dan iz čakalne vrste verifikacije."""
    for e in pending:
        if e.get("target_date") == tarca:
            modeli = {}
            for vid, _ in VIRI:
                n = napoved_vira(vid, e.get(vid))
                if n:
                    modeli[vid] = n
            return modeli, e.get("made_at")
    return {}, None


def razreseni(verifikacija, do_dneva):
    """Zadnjih OKNO_DNI razrešenih dni: dejanska meritev + kaj je napovedal vsak vir."""
    meja = (do_dneva - datetime.timedelta(days=OKNO_DNI)).isoformat()
    out = {}
    for datum, r in verifikacija.items():
        if datum < meja:
            continue
        dej = r.get("actual") or {}
        if dej.get("tmax") is None or dej.get("tmin") is None:
            continue
        modeli = {}
        for vid, _ in VIRI:
            n = napoved_vira(vid, r.get(vid))
            if n:
                modeli[vid] = n
        out[datum] = {
            "dejansko": {"tmax": dej.get("tmax"), "tmin": dej.get("tmin"),
                         "dez": dej.get("precip")},
            "modeli": modeli,
        }
    return dict(sorted(out.items()))


def klima_za_dan(hist, dan):
    """Klimatologija koledarskega dne iz cele zgodovine postaje: mediana najvišje
    in najnižje temperature ter delež mokrih dni v oknu ±KLIMA_OKNO dni.

    Mediana in ne povprečje: nekaj vročinskih valov v sedmih letih povprečje
    potegne navzgor bolj, kot bi igralcu koristilo kot izhodišče."""
    tmax, tmin, mokri, n = [], [], 0, 0
    for k in range(-KLIMA_OKNO, KLIMA_OKNO + 1):
        d = dan + datetime.timedelta(days=k)
        mmdd = f"{d.month:02d}-{d.day:02d}"
        for datum, v in hist.items():
            if datum[5:] != mmdd:
                continue
            if v.get("tempHigh") is not None:
                tmax.append(v["tempHigh"])
            if v.get("tempLow") is not None:
                tmin.append(v["tempLow"])
            p = v.get("precipTotal")
            if p is not None:
                n += 1
                if p >= MOKER_MM:
                    mokri += 1
    return {
        "tmax_med": round(stat.median(tmax), 1) if tmax else None,
        "tmax_min": round(min(tmax), 1) if tmax else None,
        "tmax_max": round(max(tmax), 1) if tmax else None,
        "tmin_med": round(stat.median(tmin), 1) if tmin else None,
        "tmin_min": round(min(tmin), 1) if tmin else None,
        "tmin_max": round(max(tmin), 1) if tmin else None,
        "dez_delez": round(100 * mokri / n) if n else None,
        "n": len(tmax),
    }


def zadnja_meritev(hist):
    """Zadnji dan s polno meritvijo — izhodišče persistence, ki ga obrazec ponudi
    kot začetno vrednost. Ni namig modela, ampak najbolj poštena ničelna
    napoved: »jutri bo kot danes«."""
    for datum in sorted(hist, reverse=True):
        v = hist[datum]
        if v.get("tempHigh") is not None and v.get("tempLow") is not None:
            return {"datum": datum, "tmax": v.get("tempHigh"), "tmin": v.get("tempLow"),
                    "dez": v.get("precipTotal")}
    return {}


def sestavi_krog(hist, pending, verifikacija):
    tarca = (TODAY + datetime.timedelta(days=1)).isoformat()
    modeli, izdano = krog_modelov(pending, tarca)
    if not modeli:
        # Verifikacijski cevovod danes ni zabeležil napovedi (izpad vira ali
        # workflowa). Krog vseeno objavimo, a s tarčo, ki jo ima čakalna vrsta —
        # igra sama zavrne oddajo za dan, ki že teče, in to pove. Raje star
        # podatek kot prazna stran (isto načelo kot inject_forecast.py).
        if pending:
            zadnji = max(pending, key=lambda e: e.get("target_date", ""))
            tarca = zadnji.get("target_date", tarca)
            modeli, izdano = krog_modelov(pending, tarca)
    tarcni_dan = datetime.date.fromisoformat(tarca)
    return {
        "generirano": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "tarca": tarca,
        "izdano": izdano,
        "modeli": modeli,
        "namig": {"klima": klima_za_dan(hist, tarcni_dan), "vceraj": zadnja_meritev(hist)},
        "razreseni": razreseni(verifikacija, TODAY),
    }


# ── Besedilo ────────────────────────────────────────────────────────────────

def num(v, d=1):
    if v is None:
        return "—"
    return f"{v:.{d}f}".replace(".", ",")


def datum_slo(iso):
    if not iso:
        return "—"
    p = iso.split("-")
    return f"{int(p[2])}. {int(p[1])}. {p[0]}"


def opis_dneva(krog):
    """Besedilo, ki se z vsakim krogom spremeni — to je vsebina strani, ne okras.
    Pove, kje je jutrišnji dan glede na klimatologijo in kako daleč vsaksebi so
    modeli, ker prav razhajanje med njimi pove, kdaj ima igralec sploh možnost."""
    k = krog["namig"]["klima"]
    modeli = krog["modeli"]
    tmaxi = [m["tmax"] for m in modeli.values() if m.get("tmax") is not None]
    if not tmaxi or k.get("tmax_med") is None:
        return ("Krog za jutri še ni sestavljen — napovedi modelov danes ni bilo mogoče "
                "zabeležiti. Stran se osveži vsako jutro.")
    razpon = max(tmaxi) - min(tmaxi)
    odklon = stat.mean(tmaxi) - k["tmax_med"]

    if razpon >= 3:
        strinjanje = (f"Modeli si niso enotni: med najhladnejšim in najtoplejšim je "
                      f"{num(razpon)} °C razlike. Takrat ima človek, ki pozna dolino, "
                      f"največ možnosti — vsaj eden od njih se bo zmotil.")
    elif razpon >= 1.5:
        strinjanje = (f"Modeli se razhajajo za {num(razpon)} °C. Dovolj, da izbira med "
                      f"njimi nekaj šteje.")
    else:
        strinjanje = ("Modeli se strinjajo skoraj do desetinke. Takšen dan je težko "
                      "dobiti — če jih hočeš premagati, moraš vedeti nekaj, česar nimajo.")

    if odklon > 3:
        glede = f"Jutri naj bi bilo krepko topleje od običajnega za ta datum (mediana {num(k['tmax_med'])} °C)."
    elif odklon < -3:
        glede = f"Jutri naj bi bilo občutno hladneje od običajnega za ta datum (mediana {num(k['tmax_med'])} °C)."
    else:
        glede = f"Jutri naj bi bil povprečen dan za ta čas (mediana {num(k['tmax_med'])} °C)."

    return f"{glede} {strinjanje}"


def tabela_zadnjih(krog, n=10):
    raz = krog["razreseni"]
    dnevi = sorted(raz, reverse=True)[:n]
    if not dnevi:
        return ""
    glave = "".join(f"<th>{ime}</th>" for _, ime in VIRI)
    vrstice = []
    for d in dnevi:
        r = raz[d]
        dej = r["dejansko"]
        celice = []
        for vid, _ in VIRI:
            m = r["modeli"].get(vid)
            if not m or m.get("tmax") is None:
                celice.append("<td>—</td>")
                continue
            nap = abs(m["tmax"] - dej["tmax"])
            celice.append(f'<td>{num(m["tmax"])} °C<small> ±{num(nap)}</small></td>')
        vrstice.append(f'    <tr><th>{datum_slo(d)}</th><td><strong>{num(dej["tmax"])} °C</strong></td>'
                       + "".join(celice) + "</tr>")
    return ('  <table class="np-table np-wide">\n'
            f'    <tr><th>Dan</th><th>Izmerjeno</th>{glave}</tr>\n'
            + "\n".join(vrstice) + "\n  </table>")


FAQ = [
    ("Kdo me ocenjuje?",
     "Postaja IREICA1 v Rečici ob Savinji. Naslednji dan zjutraj se v arhiv zapiše dejanska "
     "najvišja in najnižja temperatura ter vsota padavin, in tvoja napoved se meri proti tej "
     "meritvi — po istem pravilu kot napovedi ARSO, Open-Meteo, MTR in ECMWF AIFS na strani "
     "<a href=\"/tocnost-napovedi/\">Točnost napovedi</a>."),
    ("Zakaj glavna ocena ne upošteva dežja?",
     "Ker ga polovica tekmovalcev ne napoveduje v milimetrih: ARSO objavlja besedno napoved, "
     "MTR pa verjetnost padavin, ne količine. Skupna ocena zato teče samo po temperaturah, kjer "
     "so vsi na istem merilu. Dež se meri posebej — kot delež dni, ko je vir pravilno zadel, ali "
     "bo padlo vsaj 0,2 mm."),
    ("Kako se računajo točke?",
     "Vsaka temperatura je vredna od 0 do 100 točk: 100 pri popolnem zadetku, 0 pri napaki 5 °C "
     "ali več, vmes linearno. Skupna ocena je povprečje obeh. Isti izračun velja za igralca in "
     "za modele — nihče nima olajšave."),
    ("Ali lahko preprosto prepišem Open-Meteo?",
     "Lahko, napoved je javna. A potem ne igraš proti modelu, ampak si model: tvoja sezonska "
     "napaka bo enaka njegovi. Igra je zanimiva prav zato, ker moraš vedeti nekaj, česar model "
     "ne ve — recimo, da se v jasni mirni noči na dnu te doline nabere hladen zrak in je jutranja "
     "temperatura nižja, kot računa mreža na 2 km."),
    ("Kje se hrani moj rezultat?",
     "Dvoje ločenega. Tvoja sezona (»Tvoja sezona« zgoraj, niz oddanih dni) je samo v tvojem "
     "brskalniku (localStorage) — ni računa, ni gesla, in ker teče pri tebi, jo je mogoče "
     "prirediti; goljufija tam škodi samo tvojemu lastnemu vpogledu. Javna lestvica pa ni "
     "prepisljiva: ob zaklepu gre napoved tudi na strežnik, ki jo naslednje jutro sam oceni proti "
     "izmerjenemu dnevu — kar vidiš na lestvici, ni izračunano v tvojem brskalniku."),
    ("Zakaj so modeli merjeni samo na dnevih, ki sem jih igral?",
     "Ker bi bila primerjava tvojih petih dni z njihovimi petdesetimi dvoje različnih meritev na "
     "isti tabeli. Model je lahko dober mesec dni in pade v enem samem fenskem dnevu — če tistega "
     "dne nisi igral, ne sme šteti ne tebi ne njemu."),
    ("Ali je to napoved, na katero se lahko zanesem?",
     "Ne. To je igra. Za dejansko napoved glej <a href=\"/\">trenutno vreme in napoved</a> ali "
     "uradno napoved <a href=\"https://www.arso.gov.si/\" rel=\"nofollow\">ARSO</a>. Napovedi "
     "modelov so tu prikazane kot nasprotniki, ne kot priporočilo."),
]


def build_body(krog, svez):
    esc = html.escape
    crumbs = [("Meteorec", "/"), ("Točnost napovedi", "/tocnost-napovedi/"), ("Prehiti model", None)]
    k = krog["namig"]["klima"]
    v = krog["namig"]["vceraj"]
    tarca = krog["tarca"]

    # Začetne vrednosti obrazca so VČERAJŠNJA MERITEV, ne napoved modela:
    # persistenca je poštena ničelna napoved in ne izda, kaj mislijo modeli.
    z_tmax = v.get("tmax") if v.get("tmax") is not None else (k.get("tmax_med") or 20)
    z_tmin = v.get("tmin") if v.get("tmin") is not None else (k.get("tmin_med") or 10)

    def polje(idb, oznaka, enota, zac, lo, hi, korak):
        # `value` gre v <input type="number"> in mora biti s piko: vejica je za
        # brskalnik neveljavna vrednost in polje ostane prazno. Vejica sodi v
        # besedilo strani, ne v atribut.
        v0 = f"{(zac if zac is not None else 0):.1f}"
        return f'''      <label class="np-field" for="{idb}">
        <span class="np-field-lbl">{oznaka}<em>{enota}</em></span>
        <input type="number" id="{idb}" value="{v0}" min="{lo}" max="{hi}" step="{korak}"
               inputmode="decimal" required>
        <input type="range" id="{idb}-r" value="{v0}"
               min="{lo}" max="{hi}" step="{korak}" aria-hidden="true" tabindex="-1">
      </label>'''

    obrazec = f'''  <div class="np-card" id="np-play">
    <form id="np-form" novalidate>
      <p class="np-kicker">Napoved za {datum_slo(tarca)}</p>
{polje("np-tmax", "Najvišja temperatura", "°C", z_tmax, -20, 45, "0.1")}
{polje("np-tmin", "Najnižja temperatura", "°C", z_tmin, -25, 30, "0.1")}
{polje("np-dez", "Padavine", "mm", 0, 0, 60, "0.1")}
      <label class="np-field np-field-text" for="np-ime">
        <span class="np-field-lbl">Vzdevek za lestvico<em>neobvezno, do 24 znakov</em></span>
        <input type="text" id="np-ime" maxlength="24" placeholder="Anonimni" autocomplete="nickname">
      </label>
      <button type="submit" class="np-btn">Zakleni napoved</button>
      <p class="np-note" id="np-msg">Oddaš lahko enkrat. Jutri zjutraj te oceni meritev postaje.</p>
    </form>
    <div id="np-locked" hidden></div>
  </div>
  <div class="np-card" id="np-result" hidden></div>
  <div class="np-card" id="np-season" hidden></div>
  <div class="np-card" id="np-leaderboard">
    <h2 class="np-h2">Lestvica</h2>
    <p class="np-note">Najboljši rezultat vsakega igralca — ocenjen na strežniku, ne v tvojem
    brskalniku, zato ga ni mogoče prirediti. Šteje samo napoved, oddana pred zaklepom.</p>
    <div class="np-tabs" role="tablist">
      <button type="button" class="np-btn np-ghost np-tab" data-obdobje="dan" aria-pressed="true">Danes</button>
      <button type="button" class="np-btn np-ghost np-tab" data-obdobje="teden" aria-pressed="false">Ta teden</button>
      <button type="button" class="np-btn np-ghost np-tab" data-obdobje="mesec" aria-pressed="false">Ta mesec</button>
    </div>
    <div id="np-leaderboard-body"><p class="np-note">Nalagam …</p></div>
  </div>'''

    namigi = f'''  <ul class="np-hints">
    <li><b>Običajno za ta dan</b><span id="np-h-tmax">{num(k.get("tmax_med"))} °C</span>
      <em>mediana najvišje, ±{KLIMA_OKNO} dni, {k.get("n") or 0} meritev</em></li>
    <li><b>Običajna najnižja</b><span id="np-h-tmin">{num(k.get("tmin_med"))} °C</span>
      <em>razpon {num(k.get("tmin_min"))} do {num(k.get("tmin_max"))} °C</em></li>
    <li><b>Verjetnost dežja</b><span id="np-h-dez">{k.get("dez_delez") if k.get("dez_delez") is not None else "—"} %</span>
      <em>delež dni z vsaj {num(MOKER_MM)} mm</em></li>
    <li><b>Zadnja meritev <span id="np-h-datum">{datum_slo(v.get("datum"))}</span></b>
      <span id="np-h-vtmax">{num(v.get("tmax"))} °C</span><em>najvišja</em></li>
    <li><b>&nbsp;</b><span id="np-h-vtmin">{num(v.get("tmin"))} °C</span><em>najnižja</em></li>
    <li><b>&nbsp;</b><span id="np-h-vdez">{num(v.get("dez"))} mm</span><em>padavine</em></li>
  </ul>'''

    faq_html = ('  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f"    <details><summary>{esc(q)}</summary><p>{a}</p></details>" for q, a in FAQ
    ) + "\n  </div>")

    krog_json = json.dumps(krog, ensure_ascii=False, separators=(",", ":"))

    return f'''{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">Prehiti model</h1>
  <p class="post-meta">Napovej jutrišnje vreme za Rečico ob Savinji in se pomeri z ARSO,
  Open-Meteo, MTR in ECMWF AIFS · krog za {datum_slo(tarca)}</p>
  <p class="archive-intro">{esc(opis_dneva(krog))}</p>

{obrazec}
  <p class="np-source">{esc(svez)}</p>

  <h2>Kaj veš o jutrišnjem dnevu</h2>
  <p class="archive-intro">Toliko ti pove sam arhiv postaje — brez modela. Obrazec je
  prednastavljen na zadnjo izmerjeno vrednost, ker je »jutri bo kot danes« najbolj poštena
  ničelna napoved: če je ne znaš premagati, je nobena druga številka ni vredna.</p>
{namigi}

  <h2>Pravila</h2>
  <table class="stats">
    <tr><th>Kdaj</th><td>Vsako jutro se objavi nov krog za naslednji dan. Napoved oddaš do
      polnoči; za dan, ki že teče, igra napovedi ne sprejema.</td></tr>
    <tr><th>Kaj</th><td>Najvišja in najnižja temperatura ter vsota padavin, kot jih izmeri
      postaja IREICA1 na dnu doline v Rečici ob Savinji — ne v Ljubljani, ne na Golteh.</td></tr>
    <tr><th>Ocena</th><td>Vsaka temperatura od 0 do 100 točk: 100 pri popolnem zadetku, 0 pri
      napaki 5 °C ali več. Skupna ocena je povprečje obeh, isti izračun za igralca in za
      modele.</td></tr>
    <tr><th>Nasprotniki</th><td>ARSO (napoved za Ljubno ob Savinji, najbližji kraj z njihovega
      seznama), Open-Meteo, naš lastni model MTR in ECMWF AIFS. To so iste napovedi, ki se dnevno
      merijo na <a href="/tocnost-napovedi/">semaforju točnosti</a>.</td></tr>
    <tr><th>Dež</th><td>Meri se posebej: ali je vir zadel, da bo padlo vsaj {num(MOKER_MM)} mm.
      ARSO in MTR milimetrov ne napovesta, zato pri njiju ta stolpec ostane prazen ali pa se
      izpelje iz verjetnosti.</td></tr>
    <tr><th>Lestvica</th><td>Prikazuje najboljši dan vsakega igralca v obdobju (glavna ocena, brez
      dežja) — dan se pomeri opolnoči, teden in mesec pa tečeta koledarsko. Vzdevek je neobvezen;
      brez njega nastopiš kot »Anonimni«.</td></tr>
  </table>

  <h2>Kako premagati model</h2>
  <p class="archive-intro">Modeli računajo na mreži. Open-Meteo je pri nas ICON-D2 z ločljivostjo
  približno 2 km, ECMWF AIFS 0,25° (~28 km) — ta doline sploh ne vidi in ji vrh in dno zlije v eno
  povprečno višino. Kar mreža spregleda, je prav tisto, kar dolina naredi vsako noč:</p>
  <table class="stats">
    <tr><th><a href="/slovar/temperaturna-inverzija/">Inverzija</a></th><td>Ob jasni, mirni noči se
      hladen zrak steka na dno doline. Jutranja temperatura je takrat nižja od modelske, včasih za
      več stopinj — to je najpogostejša napaka vseh štirih virov in tvoja največja priložnost.</td></tr>
    <tr><th>Veter</th><td>Že šibek veter premeša zrak in inverzijo razbije. Če je za noč napovedan
      veter, najnižje temperature ne tiščite prenizko.</td></tr>
    <tr><th>Oblačnost</th><td>Oblaki delujejo kot odeja: pod njimi noč ostane topla, dan pa hladnejši.
      Jasna noč pomeni nizko jutro, jasen dan visok popoldan.</td></tr>
    <tr><th>Nevihta</th><td>Popoldanska ploha lahko najvišjo temperaturo odreže sredi dneva. Modeli
      to vedo v povprečju, ne pa, ali bo celica šla čez našo dolino ali mimo.</td></tr>
    <tr><th>Sneg in fen</th><td>Sneg na tleh drži dan hladen tudi ob soncu, jugozahodni fen pa pozimi
      dvigne temperaturo hitreje, kot večina modelov pričakuje.</td></tr>
  </table>

  <h2>Zadnji dnevi: kako so se odrezali modeli</h2>
  <p class="archive-intro">Najvišja temperatura, kot jo je izmerila postaja, in kaj je dan prej
  napovedal vsak vir (v drobnem je odstopanje). Ista tabela, ki jo boš od jutri imel tudi zase.</p>
{tabela_zadnjih(krog)}
  <p class="muted-note">Popolna, dan za dnem rastoča primerjava vseh štirih virov je na strani
  <a href="/tocnost-napovedi/">Točnost napovedi</a>; primerjava po vodilnem času D+1 do D+7 pa na
  <a href="/test-napovedi/">Test napovedi</a>.</p>

{faq_html}
  <p class="muted-note">Igra ni napoved in ni pripomoček za odločanje. Napovedi modelov so tu
  prikazane kot nasprotniki v igri; za dejansko vremensko sliko glej <a href="/">naslovno stran</a>,
  za uradna opozorila pa <a href="/nevihte/">Nevihte in opozorila</a>.</p>
  <a class="back-link" href="/tocnost-napovedi/">← Točnost napovedi</a>

  <script type="application/json" id="np-krog">{krog_json}</script>
  <script src="{asset_href("napovej/napovej.js")}" defer></script>'''


def main():
    hist = seo.load_history()
    pending = nalozi(PENDING_PATH, [])
    verifikacija = nalozi(VERIFICATION_PATH, {})
    krog = sestavi_krog(hist, pending, verifikacija)

    os.makedirs(os.path.join(ROOT, "napovej"), exist_ok=True)
    with open(os.path.join(ROOT, "napovej", "krog.json"), "w", encoding="utf-8") as f:
        json.dump(krog, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    jutri = (TODAY + datetime.timedelta(days=1)).isoformat()
    n_mod = len(krog["modeli"])
    if krog["tarca"] == jutri and n_mod:
        svez = (f"🟢 Krog za {datum_slo(krog['tarca'])} · {n_mod} nasprotnikov · "
                f"napovedi zabeležene {datum_slo(krog.get('izdano'))}")
    elif n_mod:
        svez = (f"🟡 Zadnji krog je za {datum_slo(krog['tarca'])} — današnjih napovedi ni bilo "
                f"mogoče zabeležiti, zato nov krog še ni odprt.")
    else:
        svez = ("🔴 Napovedi modelov za jutri ni bilo mogoče prebrati, zato krog nima "
                "nasprotnikov. Stran se osveži vsako jutro.")

    desc = (f"Napovej jutrišnjo najvišjo in najnižjo temperaturo za Rečico ob Savinji in se "
            f"pomeri z ARSO, Open-Meteo, MTR in ECMWF AIFS. Oceni te meritev postaje — po istem "
            f"pravilu kot njih. Krog za {datum_slo(krog['tarca'])}.")

    schema = "\n".join([
        seo.webpage_schema(URL, TITLE, desc, date_published="2026-09-03"),
        seo.crumbs_schema([("Meteorec", "/"), ("Točnost napovedi", "/tocnost-napovedi/"),
                           ("Prehiti model", None)]),
        # FAQ v shemi mora biti DOBESEDNO isto besedilo kot na strani, vključno s
        # povezavami — tools/geo_audit.py išče odgovor kot niz v HTML in bi
        # očiščena različica javila neujemanje (isto kot pri /igra/).
        seo.faq_schema(FAQ),
    ])
    head = schema + f'\n<link rel="stylesheet" href="{asset_href("napovej/napovej.css")}">'

    html_out = seo.page_shell(TITLE, desc, URL, head, build_body(krog, svez))
    seo.write_page("napovej/index.html", html_out, force=True)
    print(f"  → napovej/index.html + napovej/krog.json (tarča {krog['tarca']}, "
          f"{n_mod} nasprotnikov, {len(krog['razreseni'])} razrešenih dni)")


if __name__ == "__main__":
    main()
