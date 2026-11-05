#!/usr/bin/env python3
"""tools/generate_vreme_za_vrtnarje_page.py — /vreme-za-vrtnarje/: kaj vreme zahteva od vrtnarja v naslednjih 5 dneh.

DRUGAČE od ostalih strani »vreme za …«: raven ni »kako lep je dan«, ampak **koliko ukrepanja vreme zahteva**
(brez skrbi, pozorno, ukrepajte, nujno): zmrzal (kritje), vročina in suša (zalivanje, senčenje), veter, močan dež,
toča/nevihta. Zato je opozorilo na telefon (gradnik opozoril) tu posebej uporabno: »jutri ukrepajte«.

ZMRZAL je edini dejavnik, ki ne gre samo iz Open-Meteo: modeli so ob jasnih mirnih nočeh na dnu doline običajno
previsoki (docs/model-recica.md, CLAUDE.md »MTR«). Za prve tri noči se zato uporabi naš model MTR (`napoved-modela.json`,
zamrznjena dnevna napoved, dan izbran PO DATUMU, ne po `lead`); za ostale noči Open-Meteo, in to piše ob dejavniku.
Vira se ne zlivata: detajl vedno pove, od kod je številka.

Ni agronomski nasvet; škropljenja in sredstev stran ne obravnava (etiketa, FITO-INFO). Notranjih meritev ni.
"""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, wind_pts  # noqa: E402
import generate_seo_pages as seo  # noqa: E402

MTR_FILE = os.path.join(seo.ROOT, "napoved-modela.json")
FROST_P_TH = (0.15, 0.40, 0.70)     # MTR p_frost: 1 / 2 / 3 točke (naša izbira)
OM_NIGHT_TH = (4, 2, 0)             # Open-Meteo najnižja noči: ≤ 4 °C = 1, ≤ 2 °C = 2, ≤ 0 °C = 3
SLANA_TMIN_C = 3                    # jasna mirna noč in najnižja ≤ 3 °C: slana možna (vsaj 1 točka)
_MTR = None                         # {datum: dan iz napoved-modela.json}; test ga podtakne


def mtr_by_date():
    global _MTR
    if _MTR is None:
        try:
            with open(MTR_FILE, encoding="utf-8") as f:
                _MTR = {x["date"]: x for x in json.load(f).get("days", []) if x.get("date")}
        except (OSError, ValueError, KeyError):
            _MTR = {}
    return _MTR


def _next(d, n=1):
    return (datetime.date.fromisoformat(d) + datetime.timedelta(days=n)).isoformat()


def frost_points(c, d):
    """Zmrzal v noči, ki se začne zvečer dneva d (jutro d+1): (točke, besedilo). Vir je naveden v besedilu."""
    m = mtr_by_date().get(_next(d))
    if m and m.get("p_frost") is not None and m.get("tmin") is not None:
        p, tmin = float(m["p_frost"]), float(m["tmin"])
        pts = 0 if p < FROST_P_TH[0] else 1 if p < FROST_P_TH[1] else 2 if p < FROST_P_TH[2] else 3
        slana = m.get("night_regime") == "clear_calm" and tmin <= SLANA_TMIN_C
        if slana and pts < 1:
            pts = 1
        pct = "pod 10" if p < 0.10 else seo.num(round(p * 20) * 5, 0)   # kot kartica MTR: na 5 %, pod 10 % ne trdimo številke
        txt = (f"MTR: zmrzal {pct} %, najnižja okoli {seo.num(tmin, 0)} °C"
               + (", jasna mirna noč (slana možna)" if slana else ""))
        return pts, txt
    v = c.vals("temperature_2m", d, 22, 23) + c.vals("temperature_2m", _next(d), 0, 7)
    if len(v) < 10:
        return 0, "napoved za noč še ni na voljo"
    nm = min(v)
    pts = 3 if nm <= OM_NIGHT_TH[2] else 2 if nm <= OM_NIGHT_TH[1] else 1 if nm <= OM_NIGHT_TH[0] else 0
    return pts, f"Open-Meteo: najnižja noči {seo.num(nm, 0)} °C (na dnu doline je ob jasni noči pogosto hladneje)"


def dry_points(c, d, tmax):
    """Suša: malo padavin zadnjih 7 dni ob toplem vremenu. Modelske padavine, vlage tal ne meri."""
    s, n = 0.0, 0
    for k in range(7):
        dd = _next(d, -k)
        vals = c.vals("precipitation", dd)
        if vals:
            s += sum(vals)
            n += 1
    if n < 6 or tmax is None:
        return 0, "model ne vrača podatka"
    if tmax < 18:
        return 0, f"padavine 7 dni {seo.num(s, 0)} mm, hladno: zalivanje ni potrebno"
    pts = 3 if (s < 3 and tmax >= 25) else 2 if (s < 8 and tmax >= 20) else 1 if (s < 15 and tmax >= 18) else 0
    return pts, f"padavine zadnjih 7 dni {seo.num(s, 0)} mm, popoldne do {seo.num(tmax, 0)} °C"


def day_fn(c, d):
    pts, det = {}, {}
    pts["zmrzal"], det["zmrzal"] = frost_points(c, d)
    tmax = max(c.vals("temperature_2m", d, 11, 17), default=None)
    pts["vrocina"] = bands(tmax, (28, 32, 35))
    det["vrocina"] = f"popoldne do {seo.num(tmax, 0)} °C" if tmax is not None else "model ne vrača podatka"
    pts["susa"], det["susa"] = dry_points(c, d, tmax)
    pts["veter"], det["veter"] = wind_pts(c, d, (25, 35, 45), (45, 60, 75), 8, 20)
    mm = sum(c.vals("precipitation", d, 0, 23))
    pts["dez"] = 3 if mm >= 30 else 2 if mm >= 15 else 1 if mm >= 8 else 0
    det["dez"] = f"padavine čez dan {seo.num(mm, 0)} mm"
    codes = c.vals("weather_code", d, 8, 22)
    hail = any(x >= 96 for x in codes)
    storm = any(x >= 95 for x in codes)
    pts["nevihta"] = 3 if hail else 2 if storm else 0
    det["nevihta"] = "napovedana nevihta s točo" if hail else "napovedana nevihta" if storm else "brez neviht"
    return pts, det


def hour_fn(c, h):
    """Okno za delo na vrtu (0–3): suho, ne premrzlo, ne prevroče, brez vetra in teme."""
    a = c.at("apparent_temperature", h)
    prob = c.at("precipitation_probability", h) or 0
    pr = c.at("precipitation", h) or 0
    gust = c.at("wind_gusts_10m", h) or 0
    rad = c.at("shortwave_radiation", h)
    s = 0
    if a is not None:
        s = 3 if a < 0 else 2 if a < 4 else 1 if a < 8 else 0
        s = max(s, 1 if a >= 28 else 0, 2 if a >= 32 else 0, 3 if a >= 35 else 0)
    s = max(s, 3 if pr >= 0.5 else 2 if (pr >= 0.2 or prob >= 60) else 1 if prob >= 30 else 0)
    s = max(s, 2 if gust >= 55 else 1 if gust >= 40 else 0)
    if rad is not None and rad < 10:
        s = max(s, 2)
    if (c.at("weather_code", h) or 0) >= 95:
        s = 3
    return s


CFG = {
    "url": "/vreme-za-vrtnarje/", "slug": "vreme-za-vrtnarje", "crumb": "Vreme za vrtnarje",
    "short": "Vreme za vrtnarje",
    "title": "Vreme za vrtnarje: zmrzal, suša in veter, 5 dni",
    "h1": "Vreme za vrtnarje: kdaj kriti, zalivati in delati",
    "meta": "Zmrzal, vročina, suša, veter, dež in toča",
    "kicker": "Vrt danes · Zgornja Savinjska dolina",
    "levels": ["brez skrbi", "pozorno", "ukrepajte", "nujno"],
    "advice": [
        "Vreme vrtu ne dela težav. Običajno delo.",
        "Spremljajte razmere. Pripravite pokrivala ali zalivanje, če bi se poslabšalo.",
        "Ukrepajte pred večerom: zaščitite občutljive rastline ali prilagodite delo (razlogi so zgoraj).",
        "Nujno ukrepajte: vreme lahko poškoduje rastline (zmrzal, vročina, toča ali veter).",
    ],
    "th": (1, 2, 3), "day_fn": day_fn, "hour_fn": hour_fn, "past_days": 7,
    "groups": [("Zmrzal", "Zmrzal in slana", ["zmrzal"]),
               ("Voda", "Vročina in suša", ["vrocina", "susa"]),
               ("Neurje", "Veter, dež in neurje", ["veter", "dez", "nevihta"])],
    "group_icons": ["d", "c", "a"],
    "factors": [
        ("zmrzal", "Zmrzal ponoči", "Slana ali zmrzal poškoduje občutljive vrtnine (paradižnik, fižol, kumare, buče); noč šteje od večera do jutra naslednjega dne."),
        ("vrocina", "Vročina", "Pri visoki temperaturi rastline več izhlapevajo: zalivanje in senčenje mladih rastlin."),
        ("susa", "Suša", "Malo padavin zadnjih 7 dni ob toplem vremenu pomeni zalivanje. To je ocena iz padavin modela, ne meritev vlage tal."),
        ("veter", "Veter", "Močan veter lomi in podira visoke rastline, suši tla in ruši opore; model je v dolini običajno previsok."),
        ("dez", "Močan dež", "Velike količine dežja zamočijo tla, spirajo zemljo in zavirajo delo na težkih tleh."),
        ("nevihta", "Toča in nevihta", "Toča poškoduje liste in plodove; pred njo se lahko le pokrije, zato nevihta šteje takoj veliko."),
    ],
    "rules": [
        ("Zmrzal (MTR, prve tri noči)", "verjetnost zmrzali 15 / 40 / 70 %; jasna mirna noč in ≤ 3 °C = vsaj 1", "najnižja okoli … °C"),
        ("Zmrzal (Open-Meteo, ostale noči)", "najnižja noči ≤ 4 / 2 / 0 °C", "od 22.00 do 7.00; za zadnji dan napoved noči še ni na voljo"),
        ("Vročina (11.–17. ure)", "28 / 32 / 35 °C", "najvišja temperatura zraka"),
        ("Suša", "padavine 7 dni < 15 / 8 / 3 mm ob najvišji ≥ 18 / 20 / 25 °C", "pod 18 °C ni ovire"),
        ("Veter (8.–20. ure)", "povprečno 25 / 35 / 45 km/h; sunki 45 / 60 / 75 km/h", "pri sunkih in povprečju velja višja točka"),
        ("Močan dež", "8 / 15 / 30 mm čez dan", "dnevna vsota"),
        ("Toča in nevihta", "nevihta = 2, toča = 3", "koda vremena ≥ 95 / ≥ 96"),
    ],
    "method_intro": "Ocena sešteje točke šestih dejavnikov (0–3 na dejavnik, manj je bolje). Raven pove, koliko ukrepanja vreme zahteva: brez točk brez skrbi, 1 točka pozorno, 2 točki ukrepajte, 3 točke ali več nujno (tudi en sam izrazit dejavnik, na primer zmrzal ali toča). Pragovi so naši in veljajo za občutljive vrtnine; vir vsake številke je naveden ob dejavniku.",
    "limits": ["<strong>Rastline se razlikujejo:</strong> paradižnik, fižol, kumare in buče poškoduje že slana, zelje, por in korenovke prenesejo več mraza. Ocena velja za občutljive.",
               "<strong>Zmrzal na dnu doline:</strong> modeli so ob jasnih mirnih nočeh pogosto previsoki, ker se hladen zrak nabira v dolini. Zato je za prve tri noči uporabljen model MTR, naučen na postaji IREICA1; za ostale noči samo Open-Meteo, kar je ob dejavniku napisano.",
               "<strong>Lega vrta:</strong> v kotanji je ponoči hladneje, na pobočju nad dolino pogosto topleje. Ocena velja za postajo v Rečici ob Savinji.",
               "<strong>Škropljenje in sredstva</strong> stran ne obravnava: upoštevajte etiketo sredstva in FITO-INFO."],
    "intro_q": "Kaj vreme zahteva od vrtnarja?",
    "intro_a": "Najprej zmrzal: ob jasni mirni noči je slana mogoča že pri 3–4 °C v zraku. Nato vročina in suša (zalivanje), veter in toča (opore, pokrivala). Ocena zato ne pove, kako lep je dan, ampak koliko ukrepanja zahteva.",
    "disclaimer_lead": "Ocena je pripomoček, ne agronomski nasvet.",
    "disclaimer": "Odločitve o pridelavi so vaše; pri škropljenju upoštevajte etiketo sredstva in FITO-INFO.",
    "window_label": "Najboljše okno za delo na vrtu", "window_none": "Danes ni dobrega okna za delo na prostem.",
    "strip_title": "Delo na vrtu po urah", "strip_intro": "Ocena po urah od 6.00 do 22.00 (suho, ne premrzlo in ne prevroče, brez močnega vetra in teme).",
    "faq": [
        ("Pri kateri temperaturi zmrzne vrtnine?", "Občutljive vrtnine (paradižnik, fižol, kumare, buče) poškoduje že slana ali rahla zmrzal. Ob jasni, mirni noči je slana mogoča tudi, ko zrak na 2 m kaže 3–4 °C, ker so rastline hladnejše od zraka."),
        ("Zakaj ocena zmrzali uporablja model MTR?", "Open-Meteo ima na dnu doline ob jasnih mirnih nočeh običajno previsoko najnižjo temperaturo. MTR je naš model, naučen na meritvah postaje IREICA1 v Rečici, zato je za prve tri noči bližje stanju v dolini. Za nadaljnje noči ga ni, zato je tam uporabljen Open-Meteo, kar je ob dejavniku označeno."),
        ("Kdaj je prva jesenska zmrzal v dolini?", "Datum je vsako leto drugačen. Mediano, najzgodnejšo in najpoznejšo prvo jesensko zmrzal ter zadnjo spomladansko s postaje IREICA1 pokaže stran Sezona v dolini."),
        ("Ali ocena meri vlago tal?", "Ne. Suša je ocena iz padavin modela zadnjih 7 dni in temperature. Pred zalivanjem preverite prst."),
        ("Kaj je razlika od Opozorila pred pozebo?", "Opozorilo pred pozebo ocenjuje pozebo sadnega drevja v času cvetenja (marec–maj). Ta stran velja vse leto za vrt in poleg zmrzali zajame še vročino, sušo, veter, dež in točo."),
        ("Ali stran svetuje škropljenje?", "Ne. Za sredstva in odmerke upoštevajte etiketo in FITO-INFO."),
    ],
    "links": [("/sezona/", "Sezona v dolini →"), ("/opozorilo-pred-pozebo/", "Opozorilo pred pozebo →"), ("/agrometeo/", "Agrometeo →"), ("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"),
              ("/tocnost-napovedi/", "Točnost napovedi →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Vreme za vrtnarje danes: {lvl}. Zmrzal, vročina, suša, veter in toča za 5 dni z modelom MTR za dno doline ter okno za delo na vrtu.",
}

if __name__ == "__main__":
    D.main(CFG)
