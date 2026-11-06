#!/usr/bin/env python3
"""
Pristajalna stran »Meteorec za podjetja« (/podjetja/) in zahvala (/podjetja/hvala/).

Vir vsebine je ta datoteka; `podjetja/podjetja.css` in `podjetja/podjetja.js` sta ročno pisana.
Cene: SHOW_PRICES = False skrije vse zneske (kartice kažejo »Cena po ogledu lokacije«), ostalo se ne
spremeni. Po spremembi generator poženi ročno in commitaj (ni v nobenem workflowu).

Stran ne bere nobene meritve postaje; živi gradnik v brskalniku bere samo zunanje vrednosti.

Fotografije v podjetja/img/primer-*.webp in postaja-detajl.webp so AI-generirane ILUSTRACIJE (ne naša
oprema, ne stranke): vsaka je na strani označena, pod primeri je opozorilo (ILLUS_NOTE).
"""
import datetime
import hashlib
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_monthly_post import seo_title  # noqa: E402

SITE = "https://meteorec.si"
WORKER = "https://weatherireica1.filip-eremita.workers.dev"   # isti PROXY kot v app.js
URL = "/podjetja/"

SHOW_PRICES = True          # eno stikalo: skrije vse cene in pribitek za mobilni internet
META_PIXEL_ID = ""          # prazno = Meta Pixel se ne naloži (vpiši ID, ko obstaja)
CONTACT_EMAIL = "filip.eremita@gmail.com"   # prikaže se samo, če oddaja obrazca spodleti
VAT_PCT = 22

TITLE = "Vremenska postaja za kmetijo in podjetje"
DESC = ("Vremensko postajo postavimo, nastavimo in predamo z nadzorno ploščo ter opozorili na telefon. "
        "Za kmetije, turizem, gradbeništvo in občine.")

SIM_ONCE, SIM_MONTH = 390, 19

PACKAGES = [
    dict(id="osnovni", name="Osnovni", once=990, month=29, from_=True,
         who="Za podjetja, ki želijo samo zanesljive podatke za svojo lokacijo.",
         items=["Vremenska postaja in namestitev", "Osnovne nastavitve", "Javna stran ali vtičnik za vašo spletno stran"]),
    dict(id="pro", name="Pro", once=1290, month=49, from_=False,
         who="Za tiste, ki morajo pravočasno ukrepati.",
         items=["Vse iz paketa Osnovni", "Nadzorna plošča ali aplikacija",
                "Opozorila na telefon (pozeba, veter, nevihta)"]),
    dict(id="premium", name="Premium", once=1790, month=99, from_=False,
         who="Za podjetja, ki jim vreme neposredno določa dohodek.",
         items=["Vse iz paketa Pro", "Senzor strel in dva senzorja vlage tal",
                "Lokalna napoved, popravljena z vašimi podatki", "Mesečno poročilo o natančnosti",
                "Prednostna podpora"]),
    dict(id="po-meri", name="Po meri", once=2290, month=149, from_=True,
         who="Vi povejte, kaj potrebujete. Mi sestavimo ostalo.",
         items=["Dodatni senzorji", "Več postaj na več lokacijah",
                "Nadzorna plošča in opozorila po vaših pravilih", "Vse iz drugih paketov, kar potrebujete"],
         custom=True),
]

CASES = [
    dict(id="kmetija", page="kmetije", dej="Kmetijstvo, sadjarstvo, vinogradništvo", title="Kmetija in sadovnjak",
         text="Pozeba, toča in vlaga tal na vašem nasadu, ne v sosednji dolini. Opozorilo dobite, ko je še čas za ukrep.",
         tags=["Pozeba", "Toča", "Vlaga tal"], img="primer-kmetija", w=1200, h=800,
         alt="Ilustracija: vremenska postaja v sadovnjaku z jabolki ob jutranji megli"),
    dict(id="kamp", page="turizem", dej="Turizem in gostinstvo", title="Kamp in turizem",
         text="Nevihte, višina vode in veter za goste na prostem. Odločitev o terasi ali prireditvi temelji na meritvi pri vas.",
         tags=["Nevihte", "Višina vode", "Veter"], img="primer-kamp", w=800, h=450,
         alt="Ilustracija: vremenska postaja ob glamping šotorih in lesenih kočah v hribovitem okolju"),
    dict(id="gradbenistvo", page="gradbenistvo", dej="Gradbeništvo", title="Gradbeništvo",
         text="Veter pri delu na višini ter dež in temperatura pri vgrajevanju betona. Beton ne čaka na napačno napoved.",
         tags=["Veter", "Dež", "Temperatura"], img="primer-gradbenistvo", w=800, h=450,
         alt="Ilustracija: vremenska postaja na gradbišču z dvigalom in delavcema v zaščitni opremi"),
    dict(id="obcina", page="obcine", dej="Občina ali javna ustanova", title="Občina in prireditve",
         text="Neurja, veter in dež za prebivalce ter odločitve o prireditvah na prostem, vtičnik za občinsko spletno stran.",
         tags=["Neurja", "Veter", "Vtičnik"], img="primer-obcina", w=800, h=450,
         alt="Ilustracija: vremenska postaja na mestnem trgu med pripravo prireditve"),
]
ILLUS_NOTE = ("Fotografije so ilustrativne (ustvarjene z umetno inteligenco). Prikazana oprema je splošna ponazoritev: "
              "ni fotografija naše opreme, konkretne postavitve ali stranke.")

STEPS = [
    ("Ogled lokacije", "Pogledamo, kje bo postaja stala, in preverimo povezavo (WiFi ali mobilni internet)."),
    ("Postavitev postaje", "Namestimo postajo in senzorje na dogovorjeno mesto."),
    ("Nastavitve", "Nastavimo meritve, nadzorno ploščo in opozorila po vaših pravilih."),
    ("Predaja in usposabljanje", "Pokažemo, kako berete podatke in kaj sprožijo opozorila."),
    ("Podpora", "Spremljamo delovanje postaje in vam svetujemo, kadar je treba."),
]

def faq_list():
    """Vprašanja se sestavijo ob gradnji: odgovor o mobilni povezavi vsebuje zneske samo, če je SHOW_PRICES."""
    return [
        ("Kaj, če na lokaciji ni WiFi?",
         "Postaja se poveže prek mobilnega interneta. Pred postavitvijo preverimo pokritost na lokaciji. "
         + ("Za povezavo brez WiFi velja pribitek: 390\u00a0€ enkratno in 19\u00a0€ na mesec (brez DDV). " if SHOW_PRICES
            else "Za povezavo brez WiFi velja pribitek. ")
         + "Mobilni podatkovni paket (SIM) plačate posebej, po tarifi svojega operaterja: v pribitek ni vštet."),
        ("Koliko časa traja postavitev?",
         "Rok je odvisen od lokacije, povezave in izbranih senzorjev. Dogovorimo ga po ogledu lokacije in ga zapišemo v ponudbo."),
        ("Kdo vzdržuje postajo, če senzor izpade?",
         "Podpora je vključena v mesečno naročnino. Kako hitro se odzovemo in kaj zajema zamenjava senzorja, "
         "zapišemo v ponudbo; paket Premium ima prednostno podporo."),
        ("Ali lahko podatke pokažem na svoji spletni strani?",
         "Da. Že paket Osnovni vključuje javno stran ali vtičnik za vašo spletno stran. "
         "Za občine pripravimo vtičnik za občinsko spletno stran."),
        ("Ali je napoved zanesljiva?",
         "Napoved je informativna. Popolne natančnosti ne jamčimo, nobena vremenska napoved je ne more. "
         "Zato v paketu Premium vsak mesec dobite poročilo o natančnosti, ki napoved primerja z meritvami vaše postaje."),
        ("Kaj pomeni paket po meri?",
         "Vi povejte, kaj morate spremljati. Mi sestavimo postajo, senzorje, nadzorno ploščo in opozorila po vaših pravilih. "
         "Izpolnite vprašalnik spodaj, ponudbo pripravimo po ogledu lokacije."),
    ]

DEJAVNOSTI = ["Kmetijstvo, sadjarstvo, vinogradništvo", "Gradbeništvo", "Turizem in gostinstvo",
              "Prireditve in šport", "Občina ali javna ustanova", "Drugo"]
POSTAJ = ["1", "2 do 3", "4 ali več"]
SPREMLJATI = ["pozeba", "veter", "dež in toča", "vlaga tal", "strele", "požarna ogroženost", "temperatura in megla"]
SPREMLJATI_LBL = ["Pozeba", "Veter", "Dež in toča", "Vlaga tal", "Strele", "Požarna ogroženost", "Temperatura in megla"]
WIFI = ["Da, WiFi je na voljo", "Ne, potreben je mobilni internet", "Ne vem, preverite z mano"]
WIFI_LBL = ["Da", "Ne", "Ne vem"]

CHECK = ('<svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M4 10.5l4 4 8-9" fill="none" '
         'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>')
ARROW = ('<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M4 10h11M11 5l5 5-5 5" fill="none" '
         'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')

e = html.escape


def ver(rel):
    """Pečat vsebine za ?v= : Cloudflare in brskalnik hranita datoteke leto dni (max-age=31536000),
    zato brez njega sprememba CSS/JS ostane nevidna. Pečat se izračuna iz datoteke, ne piše ročno."""
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def eur(n):
    return f"{n:,}".replace(",", ".") + " €"


def page_head(title, desc, canonical, robots, og_title=None, extra=""):
    full = SITE + canonical
    t = e(seo_title(title))
    ogt = e(og_title or title)
    d = e(desc)
    pix = ""
    return f'''<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>document.documentElement.classList.add('js');</script>
<script>(function(){{try{{var t=localStorage.getItem('wx-theme');if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
<title>{t}</title>
<link rel="canonical" href="{full}">
<link rel="alternate" hreflang="sl" href="{full}">
<link rel="alternate" hreflang="x-default" href="{full}">
<meta name="description" content="{d}">
<meta name="robots" content="{robots}">
<meta name="author" content="Filip Eremita">
<meta name="theme-color" content="#10181E">
<meta property="og:type" content="website">
<meta property="og:url" content="{full}">
<meta property="og:site_name" content="Meteorec">
<meta property="og:title" content="{ogt}">
<meta property="og:description" content="{d}">
<meta property="og:image" content="{SITE}/og/podjetja.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="sl_SI">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{ogt}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{SITE}/og/podjetja.jpg">
<link rel="preload" href="/podjetja/fonts/Bricolage-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/podjetja/fonts/DMSans-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/podjetja/podjetja.css?v={ver("podjetja/podjetja.css")}">
{extra}</head>
'''


def ld(obj):
    return ('<script type="application/ld+json">\n'
            + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n</script>\n")


ICONS = {
    "snow": "M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9M9 4.5l3 2.5 3-2.5M9 19.5l3-2.5 3 2.5",
    "wind": "M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h8",
    "hail": "M7 14a4 4 0 1 1 1.2-7.8A5 5 0 0 1 18 8a3.5 3.5 0 0 1-.5 6M8 17v2M12 17v3M16 17v2",
    "drop": "M12 3s6 6.2 6 10.5A6 6 0 0 1 6 13.5C6 9.2 12 3 12 3z",
    "bolt": "M13 2L5 14h6l-1 8 8-12h-6l1-8z",
    "flame": "M12 3c1 3 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 1-9z",
    "thermo": "M10 14.5V5a2 2 0 1 1 4 0v9.5a4 4 0 1 1-4 0zM12 9v7",
    "sprout": "M12 21v-9M12 12c0-4 3-6 7-6 0 4-3 6-7 6zM12 15c0-3-2-5-6-5 0 3 2 5 6 5z",
    "tent": "M3 20L12 5l9 15zM12 5v15M9 20l3-6 3 6",
    "hardhat": "M3 17h18M5 17a7 7 0 0 1 14 0M12 6v4M9 8l1 2.5M15 8l-1 2.5",
    "landmark": "M3 20h18M5 20V10M9 20V10M15 20V10M19 20V10M2 10l10-6 10 6z",
    "wifi": "M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 19.5h.01",
    "signal": "M5 20v-4M10 20v-8M15 20V8M20 20V4",
    "bell": "M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 21h4",
    "calendar": "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
    "refresh": "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
    "pin": "M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11zM9.5 10a2.5 2.5 0 1 0 5 0 2.5 2.5 0 1 0-5 0",
    "tool": "M14.5 5.5a4 4 0 0 0-5 5L3 17l4 4 6.5-6.5a4 4 0 0 0 5-5l-3 3-2.5-.5-.5-2.5z",
    "sliders": "M4 7h10M18 7h2M4 17h2M10 17h10M16 4v6M8 14v6",
    "check": "M3 12a9 9 0 1 0 18 0 9 9 0 1 0-18 0M8 12l3 3 5-6",
    "headset": "M4 14v-2a8 8 0 0 1 16 0v2M4 14h3v5H4zM17 14h3v5h-3zM20 19c0 2-2 2-5 2",
}
TAG_ICON = {"Pozeba": "snow", "Toča": "hail", "Vlaga tal": "drop", "Nevihte": "bolt", "Višina vode": "drop", "Veter": "wind",
            "Dež": "hail", "Temperatura": "thermo", "Požarna ogroženost": "flame", "Neurja": "bolt", "Vtičnik": "dash"}
ICONS["dash"] = "M3 4h18v12H3zM8 20h8M12 16v4M7 12l3-3 3 2 4-4"
CASE_ICON = {"kmetija": "sprout", "kamp": "tent", "gradbenistvo": "hardhat", "obcina": "landmark"}
STEP_ICON = ["pin", "tool", "sliders", "check", "headset"]
PHOTO = "podjetja/img/postaja.jpg"   # prava fotografija IREICA1; ko obstaja, nadomesti ilustracijo
PHOTO_ALT = "Vremenska postaja IREICA1 v Rečici ob Savinji"
ILLUS = "podjetja/img/postaja-detajl.webp"   # AI-ilustracija splošne postaje, ne IREICA1; velja, dokler ni prave fotografije
ILLUS_ALT = "Ilustracija: bližnji prikaz vremenske postaje z merilnikom vetra, zaščito za temperaturo in vlago, dežemerom in sončno celico"


def ic(name, cls="ic"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false"><path d="{ICONS[name]}" '
            f'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')


STATS = [("calendar", "Od 2019", "lastna postaja IREICA1"), ("refresh", "Vsakih 5 minut", "nova meritev na strani"),
         ("signal", "WiFi ali mobilni internet", "kjer koli stoji postaja"), ("bell", "Opozorila na telefon", "pozeba, veter, nevihta (Pro)")]


TRUST = ["Lastna postaja IREICA1 od 2019", "Postavitev, nastavitev in predaja", "Podpora v mesečni naročnini"]


def trust_html():
    return "".join(f'<li>{CHECK}<span>{e(t)}</span></li>' for t in TRUST)


def stats_html():
    return "".join(f'<li>{ic(i)}<span><strong>{e(t)}</strong>{e(d)}</span></li>' for i, t, d in STATS)


# ── Resnični podatki: postaja IREICA1 proti napovedi ─────────────────────────────────────
def sl(x, d=1, plus=False):
    t = f"{x:+.{d}f}" if plus else f"{x:.{d}f}"
    return t.replace("-", "−").replace(".", ",")


def noci(n):
    return f"{n} noč" if n % 100 == 1 else f"{n} noči"


def dan_word(n):
    """Samostalnik »dan« ob številu (1 dan, 2 dneva, 3+ dni); isto pravilo je v podjetja.js."""
    m = n % 100
    return "dan" if m == 1 else ("dneva" if m == 2 else "dni")


def dnevi_s(n):
    return f"{n} dan" if n % 100 == 1 else (f"{n} dneva" if n % 100 == 2 else (f"{n} dni" if n % 100 in (3, 4) else f"{n} dni"))


def fmt_date_y(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}"


def fmt_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def load_data():
    """Samo ZUNANJE meritve postaje (tempLow) in napoved Open-Meteo izdana dan prej. Brez notranjih meritev."""
    with open(os.path.join(ROOT, "history.json"), encoding="utf-8") as f:
        hist = json.load(f)
    with open(os.path.join(ROOT, "forecast_verification.json"), encoding="utf-8") as f:
        ver_ = json.load(f)
    meas = {d: v["tempLow"] for d, v in hist.items() if v.get("src") in ("station", "wu") and v.get("tempLow") is not None}
    last = max(meas)
    end = datetime.date.fromisoformat(last)
    days = [(end - datetime.timedelta(days=i)).isoformat() for i in range(364, -1, -1)]
    series = [(d, meas.get(d)) for d in days]
    errs = []
    for d in sorted(ver_):
        r = ver_[d]
        a = (r.get("actual") or {}).get("tmin")
        f_ = (r.get("open_meteo") or {}).get("tmin")
        if a is not None and f_ is not None:
            errs.append((d, round(f_ - a, 2), f_, a))
    return series, errs


def stats(errs):
    n = len(errs)
    mean = sum(e for _, e, _, _ in errs) / n
    hi = sum(1 for _, e, _, _ in errs if e >= 2)
    lo = sum(1 for _, e, _, _ in errs if e <= -2)
    return dict(n=n, mean=mean, hi=hi, lo=lo, d0=errs[0][0], d1=errs[-1][0])


def error_svg(errs, st_):
    W, H, L, R, T, B = 760, 270, 46, 92, 16, 30
    plot_h = H - T - B
    zero = T + plot_h / 2
    sc = (plot_h / 2) / 6.0
    n = len(errs)
    bw = (W - L - R) / n
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{e(error_alt(st_))}" preserveAspectRatio="none">']
    for v in (-4, -2, 0, 2, 4):
        y = zero - v * sc
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" class="{"z" if v == 0 else "g"}"/>'
                   f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" class="t">{sl(v, 0, True) if v else "0"} °C</text>')
    for i, (d, err, f_, a) in enumerate(errs):
        c = max(-6.0, min(6.0, err))
        h = abs(c) * sc
        x = L + i * bw
        y = zero - h if c >= 0 else zero
        cls = "up" if err > 0 else "dn"
        tip = f"{fmt_date(d)}: napoved {sl(f_)} °C, meritev {sl(a)} °C"
        out.append(f'<rect x="{x + .6:.2f}" y="{y:.2f}" width="{max(bw - 1.2, .8):.2f}" height="{max(h, .6):.2f}" class="{cls}"><title>{e(tip)}</title></rect>')
    ym = zero - max(-6, min(6, st_["mean"])) * sc
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{ym:.1f}" y2="{ym:.1f}" class="m"/>')
    out.append(f'<text x="{W - R + 8}" y="{ym - 2:.1f}" class="t m">povprečje</text><text x="{W - R + 8}" y="{ym + 13:.1f}" class="t m">{sl(st_["mean"], 1, True)}\u00a0°C</text>')
    out.append(f'<text x="{L}" y="{H - 8}" class="t d">{fmt_date(errs[0][0])}</text>'
               f'<text x="{W - R}" y="{H - 8}" text-anchor="end" class="t d">{fmt_date(errs[-1][0])}</text>')
    out.append('</svg>')
    return "".join(out)


def error_alt(st_):
    smer = "previsoka" if st_["mean"] > 0 else "prenizka"
    return (f"Razlika med napovedjo in meritvijo najnižje temperature za {st_['n']} noči. Povprečno je bila napoved "
            f"{sl(abs(st_['mean']))} °C {smer}.")


def napoved_html(errs):
    st_ = stats(errs)
    smer = "previsoka" if st_["mean"] > 0 else "prenizka"
    n = st_["n"]

    def pc(k):
        return sl(100 * k / n, 1)
    return f'''<section class="band" id="pozeba" aria-labelledby="h-pozeba"><div class="wrap sec">
    <h2 class="rz" id="h-pozeba">Napoved je za dolino. Vi imate polje.</h2>
    <p class="rz">Napoved, ki jo vidite v aplikaciji, velja za celico na zemljevidu, ne za vaš nasad ali gradbišče. Spodaj je primerjava z našo pravo meritvijo.</p>
    <div class="data-grid">
      <div class="bignum rz">
        <b>{sl(abs(st_["mean"]), 1, True) if st_["mean"] > 0 else sl(st_["mean"], 1, True)} °C</b>
        <span>Povprečna napaka napovedi najnižje nočne temperature: napoved je bila {smer}. Obdobje: {fmt_date(st_["d0"])} do {fmt_date(st_["d1"])}, {noci(n)}.</span>
        <ul>
          <li><strong>{pc(st_["hi"])}\u00a0%</strong> noči: napoved za več kot 2 °C previsoka <small>({st_["hi"]} od {n})</small></li>
          <li><strong>{pc(st_["lo"])}\u00a0%</strong> noči: napoved za več kot 2 °C prenizka <small>({st_["lo"]} od {n})</small></li>
        </ul>
      </div>
      <figure class="rz">
        {error_svg(errs, st_)}
        <figcaption><span class="lg up"></span>napoved toplejša od meritve <span class="lg dn"></span>napoved hladnejša od meritve. <strong>Kako brati graf:</strong> vsak stolpec je ena noč, višji stolpec pomeni večje odstopanje napovedi od meritve. Vir: napoved Open-Meteo, izdana dan prej, in meritev postaje IREICA1 v Rečici ob Savinji. <a href="/tocnost-napovedi/">Primerjava več virov</a>.</figcaption>
      </figure>
    </div>
    <div class="cta-line rz"><p>Na vaši lokaciji so lahko odstopanja drugačna. Zato je smiselno spremljati dejanske meritve.</p>
      <a class="btn" href="#povprasevanje" data-cta="napoved">Želim spremljati vreme na svoji lokaciji</a></div>
  </div></section>'''


def prag_html(series):
    vals = [t for _, t in series if t is not None]
    n = len(vals)
    lo, hi = min(vals), max(vals)
    bars = []
    for d, t in series:
        if t is None:
            bars.append('<i class="na"></i>')
        else:
            h = 14 + (t - lo) / (hi - lo) * 86
            bars.append(f'<i style="--h:{h:.0f}%" data-t="{t}" title="{fmt_date(d)}: {sl(t)} °C"></i>')
    cnt = sum(1 for t in vals if t <= 0)
    coldest = min(series, key=lambda x: 99 if x[1] is None else x[1])
    return f'''<div class="calc rz" id="prag-kalk" data-n="{n}">
      <div class="calc-head"><h3>Kolikokrat bi vas postaja opozorila v zadnjih 12 mesecih?</h3>
      <p>Nastavite mejo, pod katero želite opozorilo. Vsaka črtica predstavlja en dan. Obarvani so dnevi, ko je temperatura dosegla nastavljeno mejo ali padla pod njo.</p></div>
      <div class="calc-ctl"><label for="prag">Opozori me, ko temperatura pade na</label>
        <output id="prag-v" for="prag">0 °C</output>
        <input type="range" id="prag" min="-10" max="5" step="1" value="0" aria-describedby="prag-t prag-hint"></div>
      <p class="calc-hint" id="prag-hint">Ničla: zmrzal. Osnovna meja za pozebo pri cvetju in mladih poganjkih (okvirno, odvisno od vrste in faze rasti).</p>
      <div class="calc-res" aria-live="polite"><b id="prag-n">{cnt}</b><span id="prag-t">{dan_word(cnt)} od {n} dni z meritvijo, ko je postaja izmerila 0 °C ali manj.</span></div>
      <div class="noci" id="noci" aria-hidden="true">{"".join(bars)}</div>
      <div class="noci-os"><span>{fmt_date(series[0][0])}</span><span>najhladnejša: {sl(min(vals))} °C ({fmt_date(coldest[0])})</span><span>{fmt_date(series[-1][0])}</span></div>
      <p class="fine">Meritev postaje IREICA1 v Rečici ob Savinji (dnevni minimum, {fmt_date_y(series[0][0])} do {fmt_date_y(series[-1][0])}, {n} dni z meritvijo). To je zgodovina ene konkretne postaje: na vašem polju bo število opozoril drugačno, ravno zato je smiselna lastna postaja. Brez meritve na lokaciji tega ne veste.</p>
      <div><a class="btn" href="#povprasevanje" data-cta="kalkulator">Želim takšna opozorila na svoji lokaciji</a></div>
    </div>'''


NOC = [("21.00", "moon", "Večer", "Napoved obeta jasno noč, najnižja temperatura naj bi ostala nad ničlo."),
       ("00.40", "thermo", "Ohlajanje", "Postaja na vašem polju beleži, da zrak pada hitreje, kot je napovedano."),
       ("02.10", "bell", "Opozorilo", "Temperatura doseže mejo, ki ste jo nastavili. Telefon zavibrira."),
       ("02.25", "flame", "Ukrep", "Zaščito (škropljenje, ogrevanje, kritje) vklopite, ko je še čas."),
       ("07.30", "dash", "Pregled", "Zjutraj vidite, kdaj je padlo in kako dolgo je trajalo.")]
ICONS["moon"] = "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"


# Ilustrativna krivulja noči (ni meritev): ura od 21.00 (h) in temperatura (°C). Napoved ostane nad ničlo,
# meritev na polju pade pod mejo ob 02.10.
NOC_MERITEV = [(0, 4.2), (2.0, 3.0), (3.67, 2.0), (5.17, 0.0), (6.8, -1.6), (8.5, -2.4), (9.8, -1.2), (10.5, 0.2)]
NOC_NAPOVED = [(0, 4.4), (2.0, 3.6), (3.67, 3.0), (5.17, 2.4), (6.8, 1.9), (8.5, 1.5), (9.8, 1.9), (10.5, 2.4)]


def _smooth(pts):
    """Catmull-Rom → kubični Bézier (nežna krivulja skozi točke)."""
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def noc_svg():
    W, H, L, R, T, B = 640, 250, 44, 16, 14, 34
    tmin, tmax, hmax = -4.0, 6.0, 10.5
    X = lambda h: L + h / hmax * (W - L - R)
    Y = lambda t: T + (tmax - t) / (tmax - tmin) * (H - T - B)
    act = [(X(h), Y(t)) for h, t in NOC_MERITEV]
    fc = [(X(h), Y(t)) for h, t in NOC_NAPOVED]
    out = [f'<svg class="noc-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Ilustrativen potek temperature od 21.00 do 7.30: '
           f'napoved ostane nad ničlo, meritev na polju pade pod nastavljeno mejo ob 2.10 in doseže najnižjo vrednost okoli 5.30.">']
    for t in (-4, -2, 0, 2, 4, 6):
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="{"nz" if t == 0 else "ng"}"/>'
                   f'<text x="{L - 8}" y="{Y(t) + 4:.1f}" text-anchor="end" class="nt">{sl(t, 0, True) if t else "0"}</text>')
    # območje pod mejo (od presečišča do 07.30), samo ponazoritev
    x0 = X(5.17)
    area = f"M{x0:.1f},{Y(0):.1f} " + " ".join(f"L{x:.1f},{min(y, Y(0)):.1f}" for x, y in act[3:]) + f" L{act[-1][0]:.1f},{Y(0):.1f} Z"
    out.append(f'<path d="{area}" class="na"/>')
    out.append(f'<path d="{_smooth(fc)}" class="nf"/>')
    out.append(f'<path d="{_smooth(act)}" class="nm"/>')
    for h, lab in ((0, "21.00"), (3.67, "00.40"), (5.17, "02.10"), (10.5, "07.30")):
        out.append(f'<text x="{X(h):.1f}" y="{H - 10}" text-anchor="{"end" if h == 10.5 else ("start" if h == 0 else "middle")}" class="nt">{lab}</text>')
    out.append(f'<circle cx="{X(3.67):.1f}" cy="{Y(2.0):.1f}" r="5" class="nd"/>')
    out.append(f'<circle cx="{X(5.17):.1f}" cy="{Y(0):.1f}" r="9" class="nb"/><circle cx="{X(5.17):.1f}" cy="{Y(0):.1f}" r="4.5" class="nb2"/>')
    out.append(f'<text x="{X(5.17) + 14:.1f}" y="{Y(0) - 12:.1f}" class="nl">02.10 opozorilo</text>')
    out.append(f'<text x="{W - R}" y="{Y(NOC_NAPOVED[-1][1]) - 8:.1f}" text-anchor="end" class="nl nlf">napoved</text>')
    out.append(f'<text x="{X(8.5):.1f}" y="{Y(-2.4) + 20:.1f}" text-anchor="middle" class="nl nlm">meritev na polju</text>')
    out.append(f'<text x="{L + 4}" y="{Y(0) + 15:.1f}" class="nt nmeja">vaša meja 0\u00a0°C</text>')
    out.append('</svg>')
    return "".join(out)


NOTIF_HTML = '''<div class="notif" role="img" aria-label="Primer obvestila na zaslonu telefona: opozorilo pred pozebo">
      <span class="notif-app"><img src="/logo.svg" alt="" width="18" height="18">Meteorec <i>zdaj</i></span>
      <b>Opozorilo: pozeba</b>
      <span>Temperatura na vašem polju je padla na 0,0\u00a0°C, vaša meja je 0\u00a0°C. Zaščito vklopite, dokler je še čas.</span>
      <small>Primer obvestila, ne meritev</small>
    </div>'''


def noc_html():
    items = "".join(
        f'<li style="--i:{i}"><span class="cas">{t}</span><span class="pika">{ic(icon)}</span><h3>{e(h)}</h3><p>{e(txt)}</p></li>'
        for i, (t, icon, h, txt) in enumerate(NOC))
    return f'''<section class="band band-dark" id="noc" aria-labelledby="h-noc"><div class="wrap sec">
    <p class="oz rz">PRIMER</p>
    <h2 class="rz" id="h-noc">Ena noč na vašem polju</h2>
    <p class="rz">Izmišljen primer, kako lahko poteka noč s pozebo. Ure in vrednosti so ponazoritev, ne meritev.</p>
    <div class="noc-top rz">
      <figure class="noc-fig">{noc_svg()}<figcaption>Ilustrativna shema: napoved pravi, da bo noč ostala nad ničlo, postaja na polju pa izmeri drugače.</figcaption></figure>
      {NOTIF_HTML}
    </div>
    <ol class="noc" id="noc-list">{items}</ol>
    <div class="cta-line rz"><p>Takšno obvestilo dobite na telefon v paketu Pro.</p><a class="btn btn-hero" href="#paketi" data-cta="noc">Poglejte pakete</a></div>
  </div></section>'''


# x, y = položaj oznake v % slike postaja-detajl.webp (992 × 1740 izvirnik). Del brez x/y na sliki ni viden.
PARTS = [
    dict(id="veter", name="Merilnik vetra", x=30, y=16, kind="osnovno",
         text="Meri hitrost in smer vetra ter sunke. Za delo na višini, nanos sredstev in prireditve na prostem."),
    dict(id="dez", name="Dežemer", x=74, y=53, kind="osnovno",
         text="Meri količino in jakost padavin. Za betoniranje, košnjo, obiranje in odločitve o termenu del."),
    dict(id="temp", name="Temperatura in vlaga", x=28, y=44, kind="osnovno",
         text="Senzor v zaščitnem ohišju meri temperaturo in vlago zraka. Iz tega izračunamo tudi rosišče, osnovo za opozorilo pred pozebo."),
    dict(id="sonce", name="Sončna celica", x=48, y=75, kind="osnovno",
         text="Napaja postajo tam, kjer ni vtičnice. Način napajanja izberemo po ogledu lokacije."),
    dict(id="zbiralnik", name="Zbiralnik podatkov", x=None, y=None, kind="osnovno",
         text="Zbira meritve in jih pošlje prek WiFi ali mobilnega interneta na nadzorno ploščo ali v aplikacijo. Na tej ilustraciji ni vidno."),
    dict(id="tla", name="Vlaga tal", x=None, y=None, kind="dodatno",
         text="Meri vlažnost tal na izbrani globini. Za odločitve o namakanju in vstopu na zemljišče. Paket Premium ali Po meri."),
    dict(id="voda", name="Višina vode", x=None, y=None, kind="dodatno",
         text="Meri višino vode ob potoku ali reki. Za odločitve v kampih in na prizoriščih ob vodi. Dodatni senzor po dogovoru (paket Po meri)."),
    dict(id="strele", name="Senzor strel", x=None, y=None, kind="dodatno",
         text="Zazna strele v okolici. Za zgodnejše opozorilo pri delu in prireditvah na prostem. Paket Premium ali Po meri."),
]


def shema_html():
    full = os.path.join(ROOT, PHOTO)
    pins = ""
    from PIL import Image
    if os.path.exists(full):
        w, h = Image.open(full).size
        art = f'<img src="/{PHOTO}" alt="{e(PHOTO_ALT)}" width="{w}" height="{h}" loading="lazy">'
        cap = "Postaja IREICA1, Rečica ob Savinji, 366 m"
    else:
        w, h = Image.open(os.path.join(ROOT, ILLUS)).size
        art = f'<img class="foto" src="/{ILLUS}" alt="{e(ILLUS_ALT)}" width="{w}" height="{h}" loading="lazy">'
        cap = "Ilustracija: primer postaje (ni naša postaja IREICA1). Kliknite oznako."
        pins = "".join(
            f'<button class="pin" type="button" data-part="{p["id"]}" style="left:{p["x"]}%;top:{p["y"]}%" aria-label="{e(p["name"])}"><span>{i}</span></button>'
            for i, p in enumerate(PARTS, 1) if p["x"] is not None)

    def li(i, p):
        return (f'<li><button class="part" type="button" data-part="{p["id"]}" data-text="{e(p["text"])}" aria-pressed="false">'
                f'<span class="num">{i}</span><span>{e(p["name"])}</span></button></li>')
    base = "".join(li(i, p) for i, p in enumerate(PARTS, 1) if p["kind"] == "osnovno")
    extra = "".join(li(i, p) for i, p in enumerate(PARTS, 1) if p["kind"] == "dodatno")
    return f'''<section class="band band-dark photo" id="shema" aria-labelledby="h-shema">
  <div class="wrap photo-grid">
    <figure class="photo-art rz"><div class="art-wrap">{art}{pins}</div><figcaption>{e(cap)}</figcaption></figure>
    <div class="photo-text rz">
      <h2 class="rz" id="h-shema">Kaj meri postaja in za katero odločitev</h2>
      <p>Izberite del postaje in poglejte, kaj meri ter za kaj ga uporabite.</p>
      <p class="grp">Osnovna postaja</p>
      <ul class="parts">{base}</ul>
      <p class="grp">Dodatni senzorji (po dogovoru)</p>
      <ul class="parts">{extra}</ul>
      <div class="part-info" id="part-info" aria-live="polite"><b id="part-name">{e(PARTS[0]["name"])}</b><p id="part-text">{e(PARTS[0]["text"])}</p></div>
    </div>
  </div>
</section>'''


def izjava_html():
    return '''<section class="band band-yellow" aria-label="Sporočilo"><div class="wrap"><p class="izjava rz">Napoved ne pozna vašega polja. <span>Postaja ga pozna.</span></p></div></section>'''


def first_year(p):
    """Enkratna cena + 12 mesečnih naročnin (brez DDV, povezava WiFi). Sim pribitek doda JS."""
    return p["once"] + 12 * p["month"]


def price_block(p):
    if not SHOW_PRICES:
        return '<div class="price"><span class="price-note">Cena po ogledu lokacije</span></div>'
    od = "od " if p["from_"] else ""
    od_m = "od " if p["id"] == "po-meri" else ""
    sim = (f'<div class="sim-add" data-sim-add hidden>Brez WiFi: + {eur(SIM_ONCE)} enkratno, + {eur(SIM_MONTH)} na mesec. Podatkovni paket (SIM) ni vštet.</div>')
    return (f'<div class="price" data-once="{p["once"]}" data-month="{p["month"]}">'
            f'<div class="price-row"><span class="price-lbl">Enkratna investicija</span>'
            f'<span class="price-once"><strong>{od}{eur(p["once"])}</strong></span></div>'
            f'<div class="price-row"><span class="price-lbl">Mesečna storitev</span>'
            f'<span class="price-month"><strong>{od_m}{eur(p["month"])}</strong> <span>na mesec</span></span></div>'
            f'<div class="price-row price-sum"><span class="price-lbl">Skupaj v prvem letu</span>'
            f'<span><strong data-year>{od}{eur(first_year(p))}</strong></span></div>'
            f'<span class="price-basis" data-basis>Brez DDV · povezava WiFi</span>{sim}</div>')


def package_card(p):
    items = "".join(f"<li>{CHECK}<span>{e(i)}</span></li>" for i in p["items"])
    cls = "card pack rz" + (" custom" if p.get("custom") else "") + (" feat" if p["id"] == "pro" else "")
    flag = '<span class="feat-flag">Za podjetja, ki potrebujejo opozorila</span>' if p["id"] == "pro" else ""
    return f'''      <article class="{cls}" id="paket-{p["id"]}">
        {flag}<h3>{e(p["name"])}</h3>
        <p class="for">{e(p["who"])}</p>
        <div class="conn" data-conn>Povezava: WiFi</div>
        <ul>{items}</ul>
        {price_block(p)}
        <a class="btn {"" if p["id"] == "pro" else "btn-ghost"}" href="#povprasevanje" data-paket="{p["id"]}" aria-label="Izberem paket {e(p["name"])}">Izberem paket {e(p["name"])}</a>
      </article>'''


def case_card(c):
    tags = "".join(f'<li>{ic(TAG_ICON[t], "ic-s")}{e(t)}</li>' for t in c["tags"])
    return f'''      <article class="card case rz" id="{c["id"]}" data-dej="{e(c["dej"])}" tabindex="-1">
        <figure class="case-ph"><img src="/podjetja/img/{c["img"]}.webp" alt="{e(c["alt"])}" width="{c["w"]}" height="{c["h"]}" loading="lazy" decoding="async"><figcaption>Ilustracija</figcaption></figure>
        <span class="case-flag" hidden>Ponudba za vas</span>
        <div class="case-body">
          <h3>{ic(CASE_ICON[c["id"]], "ic-t")}{e(c["title"])}</h3>
          <p>{e(c["text"])}</p>
          <ul class="tags" aria-label="Kaj spremljate">{tags}</ul>
          <div class="case-links"><a class="link" href="{seg_url(SEG_BY_SLUG[c["page"]])}">Več za {e(SEG_BY_SLUG[c["page"]]["nav"].lower())} {ARROW}</a>
          <a class="link link-sec" href="#povprasevanje" data-segment="{c["id"]}">Pridobite ponudbo</a></div>
        </div>
      </article>'''


PLUS = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 12h14M12 5v14" fill="none" stroke="currentColor" '
        'stroke-width="2.2" stroke-linecap="round"/></svg>')

MARQUEE = ["Kmetije", "Sadovnjaki", "Vinogradi", "Hmeljarji", "Čebelarji", "Kampi", "Turizem", "Gostinstvo",
           "Gradbeništvo", "Občine", "Prireditve", "Športni klubi"]


def marquee_html():
    """Statičen nabor dejavnosti (drseči trak je bil odstranjen: gibanje brez prodajne vrednosti, na telefonu moteče)."""
    return "".join(f"<li>{e(m)}</li>" for m in MARQUEE)


def faq_items(items=None):
    return "\n".join(
        f'      <details class="rz"><summary><span>{e(q)}</span><i>{PLUS}</i></summary><div class="odg"><div><p>{e(a)}</p></div></div></details>'
        for q, a in (items or faq_list()))


def schema_blocks(url=URL, title=TITLE, desc=DESC, audience="Kmetije, turizem, gradbeništvo, občine", faq=None,
                  crumbs=None):
    faq = faq or faq_list()
    page = {"@context": "https://schema.org", "@type": "WebPage", "@id": SITE + url, "name": title,
            "description": desc, "url": SITE + url, "inLanguage": "sl",
            "isPartOf": {"@id": SITE + "/#website"}, "image": SITE + "/og/podjetja.jpg"}
    service = {
        "@context": "https://schema.org", "@type": "Service", "@id": SITE + url + "#storitev",
        "name": "Vremenska postaja za podjetja z nadzorno ploščo in opozorili",
        "serviceType": "Postavitev in vzdrževanje vremenske postaje",
        "description": desc,
        "provider": {"@type": "Organization", "name": "Meteorec", "url": SITE + "/",
                     "founder": {"@id": SITE + "/#person"}},
        "areaServed": {"@type": "AdministrativeArea", "name": "Zgornja Savinjska dolina"},
        "audience": {"@type": "BusinessAudience", "name": audience},
    }
    if SHOW_PRICES:
        service["hasOfferCatalog"] = {
            "@type": "OfferCatalog", "name": "Paketi",
            "itemListElement": [{
                "@type": "Offer", "name": p["name"], "priceCurrency": "EUR",
                "priceSpecification": {"@type": "PriceSpecification", "price": str(p["once"]),
                                       "priceCurrency": "EUR", "valueAddedTaxIncluded": False},
                "description": "; ".join(p["items"]),
            } for p in PACKAGES]}
    faqld = {"@context": "https://schema.org", "@type": "FAQPage",
             "mainEntity": [{"@type": "Question", "name": q,
                             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    crumbs = crumbs or [("Meteorec", SITE + "/"), ("Za podjetja", None)]
    items = []
    for i, (name, item) in enumerate(crumbs, 1):
        d = {"@type": "ListItem", "position": i, "name": name}
        if item:
            d["item"] = item
        items.append(d)
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}
    return ld(page) + ld(service) + ld(faqld) + ld(bc)


# Vzorčne vrednosti (SAMPLE): dokler se prava meritev ne naloži, telefon nikoli ni prazen. Označene so kot
# »primer«; JS jih ob uspešnem branju zamenja z živo meritvijo (razred is-live) in spremeni oznako.
SAMPLE = dict(temp="−1,2\u00a0°C", hum="86\u00a0%", pres="1018\u00a0hPa", wind="8\u00a0km/h", rain="0,0\u00a0mm",
              dew="−3,1\u00a0°C", gust="14\u00a0km/h")

PHONE_HTML = f'''<div class="phone is-sample" id="phone" role="img" aria-label="Primer prikaza na telefonu z vzorčnimi vrednostmi in primerom opozorila">
        <span class="ph-notch"></span>
        <div class="ph-screen">
          <div class="ph-head"><span class="ph-brand">Meteo<em>rec</em></span><span class="ph-stn" id="ph-stn">Primer prikaza</span></div>
          <div class="ph-hero"><span class="ph-lbl">Zdaj</span><strong id="ph-temp">{SAMPLE["temp"]}</strong><span class="ph-sub" id="ph-time">Vzorčne vrednosti, ne meritev</span></div>
          <div class="ph-grid">
            <div class="ph-t t-hum"><span>Vlaga</span><b id="ph-hum">{SAMPLE["hum"]}</b></div>
            <div class="ph-t t-pres"><span>Tlak</span><b id="ph-pres">{SAMPLE["pres"]}</b></div>
            <div class="ph-t t-wind"><span>Veter</span><b id="ph-wind">{SAMPLE["wind"]}</b></div>
            <div class="ph-t t-rain"><span>Dež danes</span><b id="ph-rain">{SAMPLE["rain"]}</b></div>
            <div class="ph-t t-dew"><span>Rosišče</span><b id="ph-dew">{SAMPLE["dew"]}</b></div>
            <div class="ph-t t-gust"><span>Sunki</span><b id="ph-gust">{SAMPLE["gust"]}</b></div>
          </div>
          <div class="ph-alert" id="ph-alert"><span class="ph-tag">Primer opozorila</span><b id="ph-al-t">Pozeba ponoči</b><span id="ph-al-b">Temperatura bo padla pod vašo mejo. Ukrepajte pravočasno.</span></div>
        </div>
      </div>'''

STATION_SVG = '''<svg class="station" viewBox="0 0 200 360" aria-hidden="true" focusable="false">
        <rect x="94" y="150" width="12" height="190" rx="4" fill="#6B7A84"/>
        <rect x="60" y="334" width="80" height="12" rx="6" fill="#6B7A84"/>
        <rect x="84" y="196" width="32" height="8" rx="4" fill="#55626B"/>
        <path d="M100 58 V28" stroke="#6B7A84" stroke-width="5" stroke-linecap="round"/>
        <circle cx="100" cy="24" r="8" fill="#E4572E"/>
        <rect x="56" y="58" width="88" height="104" rx="30" fill="#FFFFFF" stroke="#6B7A84" stroke-width="5"/>
        <rect x="68" y="72" width="64" height="20" rx="10" fill="#1F6F6B"/>
        <rect x="74" y="108" width="52" height="6" rx="3" fill="#C9D3D9"/>
        <rect x="74" y="122" width="52" height="6" rx="3" fill="#C9D3D9"/>
        <rect x="74" y="136" width="52" height="6" rx="3" fill="#C9D3D9"/>
      </svg>'''

FIELD = {
    "chips_m": "\n".join(
        f'          <label for="m{i}"><input type="checkbox" id="m{i}" name="m" value="{v}">{l}</label>'
        for i, (v, l) in enumerate(zip(SPREMLJATI, SPREMLJATI_LBL), 1)),
    "chips_w": "\n".join(
        f'          <label for="w{i}"><input type="radio" id="w{i}" name="w" value="{v}"{" checked" if i == 3 else ""}>{l}</label>'
        for i, (v, l) in enumerate(zip(WIFI, WIFI_LBL), 1)),
    "dej": "".join(f"<option>{e(d)}</option>" for d in DEJAVNOSTI),
    "postaj": "".join(f"<option>{e(d)}</option>" for d in POSTAJ),
}


def cfg_json(segment=None, dej=None):
    cfg = {"worker": WORKER, "pixel": META_PIXEL_ID, "email": CONTACT_EMAIL, "showPrices": SHOW_PRICES,
           "sim": {"once": SIM_ONCE, "month": SIM_MONTH}}
    if segment:
        cfg["segment"] = segment      # podstran dejavnosti: obrazec dobi dejavnost vnaprej
        cfg["dej"] = dej
    return json.dumps(cfg, ensure_ascii=False)


def top_html(nav, mob):
    """Glava + mobilni meni. nav/mob: seznami (href, besedilo); gumb »Pridobite ponudbo« je vedno zadnji."""
    links = "".join(f'<a href="{h}">{e(t)}</a>' for h, t in nav)
    mlinks = "".join(f'<a href="{h}">{e(t)}</a>' for h, t in mob)
    return f'''<a class="skip" href="#vsebina">Preskoči na vsebino</a>
<header class="top"><div class="wrap top-in">
  <a class="brand" href="/" aria-label="Meteorec, domača stran"><img src="/logo.svg" alt="" width="32" height="32"><span>Meteo<em>rec</em></span></a>
  <nav aria-label="Razdelki">{links}<a class="btn btn-sm" href="#povprasevanje" data-cta="nav">Pridobite ponudbo</a></nav>
  <button class="burger" id="burger" type="button" aria-label="Odpri meni" aria-expanded="false" aria-controls="mob"><i></i><i></i></button>
</div></header>
<nav class="mob" id="mob" aria-label="Meni">
  {mlinks}
  <a class="btn btn-hero" href="#povprasevanje" data-cta="meni">Pridobite ponudbo</a>
</nav>
'''


def vat_note():
    if not SHOW_PRICES:
        return ""
    return (f'<p class="fine">Vse cene so izhodiščne in brez DDV; obračunamo ga po stopnji {VAT_PCT} %. '
            f'Končno ceno določimo po ogledu lokacije. Skupaj v prvem letu = enkratna investicija + 12 mesečnih naročnin. '
            f'Pri mobilnem internetu podatkovni paket (SIM) plačate posebej.</p>')


def packages_html(intro=None):
    intro = intro or ("Najprej povezava: postaja potrebuje pot do interneta. Kjer imate WiFi, je preprosto. Kjer ga nimate, "
                      "uporabimo mobilni internet. Spremembe se takoj vidijo v vseh paketih.")
    return f'''  <section class="band"><div class="wrap sec" id="paketi" aria-labelledby="h-paketi">
    <h2 class="rz" id="h-paketi">Izberite paket ali ga sestavimo skupaj</h2>
    <p>{e(intro)}</p>
    <fieldset class="seg">
      <legend>Povezava postaje</legend>
      <label for="c-wifi"><input type="radio" name="conn" id="c-wifi" value="wifi" checked>Z WiFi signalom</label>
      <label for="c-sim"><input type="radio" name="conn" id="c-sim" value="sim">Brez WiFi (mobilni internet)</label>
    </fieldset>
    <p class="note" id="conn-note" aria-live="polite"></p>
    <div class="grid packs">
{chr(10).join(package_card(p) for p in PACKAGES)}
    </div>
    {vat_note()}
  </div></section>

'''


def steps_html():
    return f'''  <section class="band band-alt"><div class="wrap sec" id="kako" aria-labelledby="h-kako">
    <h2 class="rz" id="h-kako">Od povpraševanja do delujoče postaje v petih korakih</h2>
    <ol class="steps">
{chr(10).join(f'      <li class="rz">{ic(STEP_ICON[i])}<strong>{e(t)}</strong><span>{e(d)}</span></li>' for i, (t, d) in enumerate(STEPS))}
    </ol>
    <p class="steps-note rz"><strong>Vi spremljate svoje delo.</strong> Za delovanje vremenske postaje poskrbimo mi.</p>
  </div></section>

'''


def faq_html(items=None):
    return f'''  <section class="band"><div class="wrap sec" id="faq" aria-labelledby="h-faq">
    <h2 class="rz" id="h-faq">Pogosta vprašanja</h2>
    <div class="faq">
{faq_items(items)}
    </div>
    <div class="faq-cta rz"><h3>Še vedno niste prepričani, kateri paket potrebujete?</h3>
      <p>Povejte nam, kaj potrebujete. Pomagali vam bomo izbrati pravo rešitev.</p>
      <a class="btn" href="#povprasevanje" data-cta="faq">Pogovorimo se o vaši lokaciji</a></div>
  </div></section>

'''


def proof_html():
    return f'''  <section class="band band-alt"><div class="wrap sec proof" id="dokaz" aria-labelledby="h-dokaz">
    <h2 class="rz" id="h-dokaz">Zakaj nam zaupati</h2>
    <div class="proof-grid">
      <div class="proof-text">
        <ul class="facts">
          <li>{CHECK}<span>Od leta 2019 imamo lastno postajo IREICA1 v Rečici ob Savinji (366 m, 46,3258° N, 14,9211° E).</span></li>
          <li>{CHECK}<span>Imamo več let meritev in sistem, ki napovedi ARSO, Open-Meteo in Yr.no primerja z izmerjenimi vrednostmi.</span></li>
          <li>{CHECK}<span>Isto delo, ki ga opravljamo za svojo postajo, opravimo za vašo: postavitev, nastavitev in spremljanje delovanja.</span></li>
        </ul>
        <a class="link" href="/tocnost-napovedi/">Oglejte si primerjavo napovedi z meritvami {ARROW}</a>
      </div>
      <aside class="live rz" aria-labelledby="live-h">
        <h3 id="live-h">Zdaj na postaji IREICA1</h3>
        <dl class="live-grid">
          <div><dt>Temperatura</dt><dd id="lw-temp"><span class="skel" aria-hidden="true"></span><span class="sr">Nalagam</span></dd></div>
          <div><dt>Veter</dt><dd id="lw-wind"><span class="skel" aria-hidden="true"></span><span class="sr">Nalagam</span></dd></div>
          <div><dt>Dež danes</dt><dd id="lw-rain"><span class="skel" aria-hidden="true"></span><span class="sr">Nalagam</span></dd></div>
        </dl>
        <p class="live-time" id="lw-time" aria-live="polite">Nalagam zadnjo meritev.</p>
      </aside>
    </div>
  </div></section>

'''


def form_html():
    return f'''  <section class="band band-alt"><div class="wrap sec" id="povprasevanje" aria-labelledby="h-vprasalnik">
    <span id="po-meri"></span>
    <h2 class="rz" id="h-vprasalnik">Pridobite ponudbo za svojo lokacijo</h2>
    <p>Povejte nam nekaj osnovnih informacij. Pripravili bomo predlog vremenske postaje glede na vaše potrebe. Ponudbo oblikujemo po ogledu lokacije.</p>
    <form class="rz" id="q" novalidate autocomplete="on">
      <p class="chosen" id="chosen" hidden></p>
      <div class="f"><label for="f-firma"><span>Podjetje ali kmetija *</span></label><input type="text" id="f-firma" name="firma" autocomplete="organization" placeholder="Ime podjetja ali kmetije" maxlength="120" required></div>
      <div class="f"><label for="f-kraj"><span>Lokacija postaje *</span></label><input type="text" id="f-kraj" name="kraj" placeholder="Kraj, naselje ali območje" maxlength="160" required></div>
      <div class="f"><label for="f-panoga"><span>Vaša dejavnost *</span></label><select id="f-panoga" name="dejavnost" required><option value="" selected disabled>Izberite dejavnost</option>{FIELD["dej"]}</select></div>
      <div class="f"><label for="f-kontakt"><span>E-pošta ali telefonska številka *</span></label><input type="text" id="f-kontakt" name="kontakt" autocomplete="email" inputmode="email" placeholder="Kako vas lahko kontaktiramo?" maxlength="120" required aria-describedby="kontakt-help"><small id="kontakt-help">Vpišite enega od obeh. Na ta naslov ali številko odgovorimo.</small></div>
      <details class="more" id="dodatno">
        <summary><span>Dodatne informacije (neobvezno)</span><i>{PLUS}</i></summary>
        <div class="more-in">
          <div class="f"><label for="f-st"><span>Koliko postaj potrebujete?</span></label><select id="f-st" name="postaj">{FIELD["postaj"]}</select></div>
          <fieldset class="f wide"><legend>Kaj želite spremljati?</legend>
            <div class="chips">
{FIELD["chips_m"]}
            </div>
          </fieldset>
          <fieldset class="f wide"><legend>Ali imate WiFi?</legend>
            <div class="chips">
{FIELD["chips_w"]}
            </div>
          </fieldset>
          <div class="f wide"><label for="f-opomba"><span>Opombe in posebne želje</span></label><textarea id="f-opomba" name="opomba" rows="3" maxlength="1000"></textarea></div>
        </div>
      </details>
      <div class="f wide hp" aria-hidden="true"><label for="f-web">Spletna stran</label><input type="text" id="f-web" name="website" tabindex="-1" autocomplete="off"></div>
      <input type="hidden" name="paket" id="h-paket"><input type="hidden" name="povezava" id="h-povezava"><input type="hidden" name="segment" id="h-segment">
      <input type="hidden" name="utm_source"><input type="hidden" name="utm_medium"><input type="hidden" name="utm_campaign"><input type="hidden" name="utm_content"><input type="hidden" name="fbclid">
      <div class="f wide consent"><label for="f-soglasje"><input type="checkbox" id="f-soglasje" name="soglasje" required><span>Strinjam se, da Meteorec obdela moje podatke za pripravo ponudbe, kot piše v <a href="/zasebnost.html#povprasevanja">politiki zasebnosti</a>.</span></label></div>
      <p class="err" id="form-err" role="alert" hidden></p>
      <div class="f wide"><button class="btn" type="submit" id="send">Pripravite mi ponudbo</button><small class="req">* obvezna polja</small></div>
      <noscript><p class="err">Za oddajo obrazca potrebujete vklopljen JavaScript.</p></noscript>
    </form>
  </div></section>
'''


def bottom_html(cfg):
    return f'''<footer class="foot">
  <div class="wrap">
    <span>Meteorec, Zgornja Savinjska dolina · <a href="/">meteorec.si</a></span>
    <span><a href="/zasebnost.html">Zasebnost</a> · <a href="/o-postaji.html">O postaji</a> · <a href="/tocnost-napovedi/">Točnost napovedi</a></span>
  </div>
</footer>
<div class="sticky-cta" id="sticky" hidden>
  <span class="sticky-t"><strong>Vremenska postaja za vaše podjetje</strong><span>Ponudba po meri vaše lokacije</span></span>
  <a class="btn btn-hero" href="#povprasevanje" data-cta="sticky">Pridobite ponudbo</a>
</div>
<div class="cookie" id="cookie" role="region" aria-label="Piškotki in merjenje obiska" hidden>
  <p>Z vašim soglasjem merimo obisk in uspeh oglasov (Google, Meta). Brez soglasja se ti sledilniki ne naložijo. <a href="/zasebnost.html">Več</a></p>
  <div class="row"><button class="btn btn-sm" type="button" data-consent="accepted">Sprejmem</button><button class="btn btn-sm btn-ghost" type="button" data-consent="declined">Zavrnem</button></div>
</div>
<script>window.PODJETJA_CFG={cfg};</script>
<script src="/podjetja/podjetja.js?v={ver("podjetja/podjetja.js")}" defer></script>
</body>
</html>
'''


def hero_html(tag, old, words, lead, cta2, img, w, h, alt, crumb=None):
    """Hero. words = (navadni del, označeni del); H1 se animira po besedah, kot na glavni strani."""
    plain, marked = words
    i = 0
    spans = []
    for wd in plain.split():
        spans.append(f'<span class="rv"><span style="--i:{i}">{e(wd)}</span></span>')
        i += 1
    mk = []
    for wd in marked.split():
        mk.append(f'<span class="rv"><span style="--i:{i}">{e(wd)}</span></span>')
        i += 1
    h1 = " ".join(spans) + " <mark>" + " ".join(mk) + "</mark>"
    return f'''<section class="hero" aria-labelledby="h1">
  <div class="aurora" aria-hidden="true"><i></i><i></i></div>
  <div class="wrap hero-grid">
    <div class="hero-text">
      {f'<p class="crumbs"><a href="{URL}">Za podjetja</a> <span aria-hidden="true">/</span> {e(crumb)}</p>' if crumb else ""}
      <p class="tag">{e(tag)}</p>
      <p class="old">{e(old)}</p>
      <h1 id="h1">{h1}</h1>
      <p class="lead">{e(lead)}</p>
      <div class="row">
        <a class="btn btn-hero" href="#povprasevanje" data-cta="hero">Pridobite ponudbo</a>
        <a class="btn btn-line" href="{cta2[0]}" data-cta="hero-paketi">{e(cta2[1])}</a>
      </div>
      <ul class="trust" aria-label="Zakaj Meteorec">{trust_html()}</ul>
    </div>
    <div class="hero-art" aria-hidden="false">
      <figure class="hero-ph"><img src="/podjetja/img/{img}.webp" alt="{e(alt)}" width="{w}" height="{h}" fetchpriority="high" decoding="async"><figcaption>Ilustracija</figcaption></figure>
      {PHONE_HTML}
      <div class="chip chip-a" id="chip-live" aria-hidden="true"><span class="dot"></span><span id="chip-live-t">Primer prikaza</span></div>
      <div class="chip chip-b" aria-hidden="true">Opozorila na telefon</div>
    </div>
  </div>
</section>
'''


def build_main():
    cfg = cfg_json()
    head = page_head(TITLE, DESC, URL, "index, follow, max-image-preview:large", og_title="Vreme na vašem polju",
                     extra=schema_blocks())
    series, errs = load_data()
    c0 = CASES[0]
    return head + "<body>\n" + top_html(
        [("#primeri", "Primeri"), ("#pozeba", "Dokaz"), ("#paketi", "Paketi"), ("#faq", "Vprašanja")],
        [("#primeri", "Primeri"), ("#paketi", "Paketi"), ("#kako", "Kako poteka"), ("#faq", "Vprašanja")]) + f'''<main id="vsebina">
''' + hero_html("METEOREC ZA PODJETJA", "Vreme v sosednji dolini.", ("Vreme na", "vašem polju."),
                  "Vaša lastna vremenska postaja z meritvami na vaši lokaciji in opozorili na telefon. Postavimo jo, nastavimo in predamo. Manj tveganja, boljše odločitve.",
                  ("#paketi", "Oglejte si pakete"), c0["img"], c0["w"], c0["h"], c0["alt"]) + f'''<div class="stats"><ul class="wrap stats-list">{stats_html()}</ul></div>

  <div class="dej"><div class="wrap"><p class="dej-lbl">Za koga</p><ul class="dej-list" aria-label="Za koga je postaja">{marquee_html()}</ul></div></div>

  <section class="band"><div class="wrap sec" id="primeri" aria-labelledby="h-primeri">
    <h2 class="rz" id="h-primeri">Kaj vam postaja pove v vaši dejavnosti</h2>
    <p>Izberite dejavnost, ki je najbližja vaši. Postajo prilagodimo tistemu, kar morate spremljati, izbira pa gre v povpraševanje.</p>
    <div class="grid cases">
{chr(10).join(case_card(c) for c in CASES)}
    </div>
    <p class="fine illus-note">{e(ILLUS_NOTE)}</p>
  </div></section>

  {izjava_html()}

  {napoved_html(errs)}

  <section class="band band-alt" id="prag-sekcija"><div class="wrap sec">{prag_html(series)}</div></section>

  {noc_html()}

''' + proof_html() + shema_html() + "\n" + packages_html() + steps_html() + faq_html() + form_html() + "</main>\n" + bottom_html(cfg)


# ── Podstrani po dejavnostih (/podjetja/kmetije/ …) ───────────────────────────────────────────
# Vsebina je ZAPISANA TUKAJ in uporablja samo trditve, ki jih že nosi glavna stran (paketi, deli postaje, FAQ).
# Brez izmišljenih strank, števil, rokov in certifikatov. Ob nejasni trditvi je besedilo omiljeno ali izpuščeno.
FAQ_WIFI, FAQ_ROK = "@wifi", "@rok"   # skupni vprašanji iz faq_list() (en vir besedila; zneski ob SHOW_PRICES)
SEG_PAGES = [
    dict(slug="kmetije", seg="kmetija", nav="Kmetije", case=0,
         title="Vremenska postaja za kmetijo in sadovnjak",
         desc="Lastna vremenska postaja za kmetijo, sadovnjak in vinograd: pozeba, veter, dež in vlaga tal na vaši lokaciji, opozorilo na telefon.",
         audience="Kmetije, sadjarji, vinogradniki",
         tag="METEOREC ZA KMETIJE IN SADOVNJAKE", old="Napoved za dolino.", words=("Vreme na", "vašem nasadu."),
         lead="Lastna vremenska postaja na njivi, v sadovnjaku ali vinogradu: pozeba, veter, dež in vlaga tal na vaši lokaciji, ne v sosednji dolini. Opozorilo na telefon, ko temperatura doseže vašo mejo.",
         h2="Kaj vam postaja pove na kmetiji",
         intro="Pozeba je lokalna: kotanja je lahko hladnejša od bližnjega pobočja. Zato odločitev o zaščiti temelji na meritvi pri vas.",
         odl=[("snow", "Pozeba", "Opozorilo, ko temperatura na vašem nasadu pade na mejo, ki ste jo nastavili. Zaščito (škropljenje, ogrevanje, kritje) vklopite, dokler je še čas.", "Pro"),
              ("hail", "Nevihte in veter", "Opozorilo na telefon za veter in nevihto (Pro), senzor strel (Premium). Toče postaja ne zazna in je ne napove.", "Pro, Premium"),
              ("drop", "Vlaga tal", "Dva senzorja vlage tal sta del paketa Premium. Pomagata pri odločitvah o namakanju in vstopu na zemljišče.", "Premium"),
              ("wind", "Veter in dež pri delu", "Meteorološko okno za nanos sredstev, košnjo in obiranje: veter in padavine na vaši lokaciji. Etiketa sredstva in navodila ostajajo vaša odgovornost.", "Osnovni, Pro")],
         dokaz=True,
         faq=[("Ali postaja napove pozebo?",
               "Postaja meri temperaturo in rosišče na vaši lokaciji in vas opozori, ko dosežete mejo, ki jo nastavite. Napovedi pozebe ne nadomešča: je meritev tam, kjer napoved zgreši. Primerjavo napovedi z meritvijo vidite na tej strani."),
              ("Kje naj stoji postaja v sadovnjaku?",
               "Mesto določimo ob ogledu lokacije. Pomembno je, da meri reprezentativno za nasad: višina, hladne kotanje in bližina dreves lahko spremenijo meritev."),
              ("Ali lahko opozorila nastavim po svojih mejah?",
               "Opozorila na telefon (pozeba, veter, nevihta) so v paketu Pro, mejo nastavite vi. Paket Po meri doda opozorila po vaših pravilih."),
              ("Ali postaja nadomešča uradna opozorila ARSO?",
               "Ne. Uradna opozorila izdaja ARSO. Naša postaja je meritev na vaši lokaciji; skupaj dasta boljšo sliko."),
              FAQ_WIFI, FAQ_ROK]),
    dict(slug="turizem", seg="kamp", nav="Turizem", case=1,
         title="Vremenska postaja za kamp, turizem in gostinstvo",
         desc="Vremenska postaja za kamp, glamping in gostinstvo: nevihta, veter, dež in višina vode na vaši lokaciji, opozorilo na telefon, vreme na spletni strani.",
         audience="Kampi, turistične kmetije, gostinstvo",
         tag="METEOREC ZA TURIZEM IN GOSTINSTVO", old="Vreme po občutku.", words=("Vreme v", "vašem kampu."),
         lead="Vremenska postaja v vašem kampu, na terasi ali ob prizorišču: veter, dež in nevihte na lokaciji, opozorilo na telefon in trenutno vreme na vaši spletni strani.",
         h2="Kaj vam postaja pove pri turizmu",
         intro="Za gosta ni pomembno vreme v dolini, ampak pri vas. Odločitev o terasi, izletu ali prireditvi temelji na meritvi na vaši lokaciji.",
         odl=[("bolt", "Nevihte", "Opozorilo na telefon (Pro) in senzor strel (Premium): odločitev o umiku gostov s terase, bazena ali prireditve temelji na meritvi pri vas.", "Pro, Premium"),
              ("wind", "Veter in dež", "Senčniki, šotori in oprema na prostem: veter, sunki in padavine na vaši lokaciji, ne v dolini. Odločitev o terasi, izletu ali prireditvi na prostem.", "Osnovni, Pro"),
              ("drop", "Višina vode", "Senzor za višino vode je dodatni senzor po dogovoru: pomemben, če kamp ali prizorišče stoji ob potoku ali reki. Mesto in izvedbo senzorja določimo ob ogledu.", "Po meri"),
              ("dash", "Vreme za goste", "Javna stran ali vtičnik za vašo spletno stran: gost vidi trenutno vreme na vaši lokaciji.", "Osnovni")],
         dokaz=False,
         faq=[("Ali lahko meritve pokažem gostom?",
               "Da. Že paket Osnovni vključuje javno stran ali vtičnik za vašo spletno stran, na katerem gost vidi trenutno vreme na vaši lokaciji."),
              ("Ali postaja zazna strele?",
               "Senzor strel je del paketa Premium (ali Po meri). Kako vas opozorimo pred nevihto na vaši lokaciji, dogovorimo ob ogledu."),
              ("Ali postaja odloči o umiku gostov?",
               "Ne. Postaja pokaže meritev in pošlje opozorilo ob meji, ki jo nastavite. Odločitev in varnost gostov ostajata vaši, uradna opozorila izdaja ARSO."),
              FAQ_WIFI, FAQ_ROK]),
    dict(slug="gradbenistvo", seg="gradbenistvo", nav="Gradbeništvo", case=2,
         title="Vremenska postaja za gradbišče",
         desc="Vremenska postaja za gradbišče: veter, dež, temperatura in mraz na lokaciji, opozorilo na telefon, napajanje s sončno celico.",
         audience="Gradbena podjetja, izvajalci del",
         tag="METEOREC ZA GRADBENIŠTVO", old="Vreme z druge strani doline.", words=("Vreme na", "vašem gradbišču."),
         lead="Vremenska postaja na gradbišču: veter, dež in temperatura tam, kjer delate, in opozorilo na telefon, ko dosežete mejo, ki jo določite. Beton ne čaka na napačno napoved.",
         h2="Kaj vam postaja pove na gradbišču",
         intro="Gradbišče je pogosto na izpostavljeni točki, kjer se vreme razlikuje od napovedi za mesto. Postaja pokaže, kaj se dogaja pri vas.",
         odl=[("wind", "Veter pri delu na višini", "Meritev vetra in sunkov na gradbišču ter opozorilo ob meji. Mejo za delo na višini in z dvigalom določite po navodilih proizvajalca in svojem načrtu varnosti.", "Osnovni, Pro"),
              ("drop", "Dež in beton", "Padavine in temperatura med vgrajevanjem betona, izmerjene na gradbišču. Pogoje vgrajevanja določa vaš projekt in standard.", "Osnovni"),
              ("thermo", "Mraz ponoči", "Opozorilo, ko temperatura pade na vašo mejo, na primer za zaščito sveže vgrajenega betona.", "Pro"),
              ("dash", "Pregled na telefonu", "Nadzorna plošča ali aplikacija: vodja gradbišča vidi razmere brez obiska lokacije.", "Pro")],
         dokaz=False,
         faq=[("Ali postaja deluje brez vtičnice?",
               "Postaja ima sončno celico. Način napajanja izberemo po ogledu lokacije."),
              ("Ali postaja nadomešča meritve, ki jih zahteva projekt?",
               "Ne. Postaja je lokalni vir razmer za odločanje, ne uradna meritev. Za meritve, ki jih predpisuje projekt ali standard, upoštevajte zahteve odgovorne osebe."),
              ("Ali lahko postavite več postaj na več gradbišč?",
               "Paket Po meri vključuje več postaj na več lokacijah. Število in mesta dogovorimo ob ogledu."),
              FAQ_WIFI, FAQ_ROK]),
    dict(slug="obcine", seg="obcina", nav="Občine", case=3,
         title="Vremenska postaja za občino in javne ustanove",
         desc="Vremenska postaja za občino in javne ustanove: neurja, veter in dež, opozorilo na telefon in vtičnik za občinsko spletno stran.",
         audience="Občine, javne ustanove, organizatorji prireditev",
         tag="METEOREC ZA OBČINE IN PRIREDITVE", old="Vreme za celo regijo.", words=("Vreme v", "vaši občini."),
         lead="Vremenska postaja za občino ali javno ustanovo: neurja, veter in dež na vašem območju, opozorilo na telefon in vtičnik z vremenom za občinsko spletno stran.",
         h2="Kaj vam postaja pove v občini",
         intro="Prebivalci in služba, ki odloča o prireditvah in zaščiti, potrebujejo meritev za svoj kraj, ne za regijo. Uradna opozorila ostanejo pri ARSO in URSZR, postaja pa pokaže razmere pri vas.",
         odl=[("wind", "Veter in dež", "Trenutne meritve vetra in padavin za vaš kraj, ne za regijo: osnova za hitre odločitve službe, ki skrbi za javne površine.", "Osnovni"),
              ("bolt", "Neurja", "Opozorilo na telefon in meritve vetra ter dežja, ob paketu Premium tudi senzor strel: hitrejši odziv službe, ki odloča.", "Pro, Premium"),
              ("tent", "Prireditve na prostem", "Odločitev o prireditvi (nevihta, veter, dež) na podlagi meritve na prizorišču.", "Osnovni, Pro"),
              ("dash", "Vtičnik za občinsko stran", "Prebivalci vidijo trenutno vreme v svoji občini na občinski spletni strani.", "Osnovni")],
         dokaz=False,
         faq=[("Ali je to uradno opozorilo za prebivalce?",
               "Ne. Uradna opozorila izdajata ARSO in URSZR. Meritve in opozorila Meteorec so dopolnilo, ki kaže razmere pri vas."),
              ("Ali lahko postaje postavite na več krajev v občini?",
               "Paket Po meri vključuje več postaj na več lokacijah. Število in mesta dogovorimo ob ogledu."),
              ("Ali lahko podatke pokažemo na občinski spletni strani?",
               "Da. Za občine pripravimo vtičnik za občinsko spletno stran; javna stran ali vtičnik je že del paketa Osnovni."),
              FAQ_WIFI, FAQ_ROK]),
]
SEG_BY_SLUG = {s_["slug"]: s_ for s_ in SEG_PAGES}


def seg_url(s_):
    return f"{URL}{s_['slug']}/"


def decisions_html(sg):
    cards = "".join(
        f'<article class="card dec rz"><span class="tile">{ic(icon)}</span><h3>{e(t)}</h3><p>{e(txt)}</p>'
        f'<span class="dec-pkg">Paket: {e(pk)}</span></article>' for icon, t, txt, pk in sg["odl"])
    primer = ""
    if sg.get("primer"):
        primer = f'<p class="rz"><a class="link" href="{sg["primer"][0]}">{e(sg["primer"][1])} {ARROW}</a></p>'
    return f'''  <section class="band"><div class="wrap sec" id="odlocitve" aria-labelledby="h-odlocitve">
    <h2 class="rz" id="h-odlocitve">{e(sg["h2"])}</h2>
    <p>{e(sg["intro"])}</p>
    <div class="grid decs">{cards}</div>
    {primer}
    <p class="fine illus-note">Pri vsakem področju je navedeno, v katerem paketu je. Opozorila so pomoč pri odločanju, ne uradno opozorilo.</p>
  </div></section>

'''


def others_html(sg):
    links = "".join(f'<li><a href="{seg_url(o)}">{e(o["nav"])}</a></li>' for o in SEG_PAGES if o is not sg)
    return (f'  <section class="band"><div class="wrap sec" aria-labelledby="h-druge"><h2 class="rz" id="h-druge">Druge dejavnosti</h2>'
            f'<ul class="dej-list" aria-label="Druge dejavnosti">{links}'
            f'<li><a href="{URL}">Vse dejavnosti</a></li></ul></div></section>\n\n')


def build_segment(sg):
    url = seg_url(sg)
    case = CASES[sg["case"]]
    shared = {FAQ_WIFI: faq_list()[0], FAQ_ROK: faq_list()[1]}
    faq = [shared.get(x, x) for x in sg["faq"]]
    head = page_head(sg["title"], sg["desc"], url, "index, follow, max-image-preview:large",
                     og_title=sg["title"],
                     extra=schema_blocks(url, sg["title"], sg["desc"], sg["audience"], faq,
                                         [("Meteorec", SITE + "/"), ("Za podjetja", SITE + URL), (sg["nav"], None)]))
    dok = ""
    if sg.get("dokaz"):
        series, errs = load_data()
        dok = napoved_html(errs) + f'''

  <section class="band band-alt" id="prag-sekcija"><div class="wrap sec">{prag_html(series)}</div></section>

  ''' + noc_html() + "\n"
    nav = [(URL, "Za podjetja"), ("#odlocitve", "Kaj spremljate")] + ([("#pozeba", "Dokaz")] if sg.get("dokaz") else []) + \
        [("#paketi", "Paketi"), ("#faq", "Vprašanja")]
    body = ("<body>\n" + top_html(nav, nav) + '<main id="vsebina">\n'
            + hero_html(sg["tag"], sg["old"], sg["words"], sg["lead"], ("#paketi", "Oglejte si pakete"),
                        case["img"], case["w"], case["h"], case["alt"], crumb=sg["nav"])
            + decisions_html(sg) + dok
            + proof_html() + (shema_html() + "\n" if sg.get("dokaz") else "")
            + f'  <p class="wrap fine illus-note">{e(ILLUS_NOTE)}</p>\n\n'
            + packages_html() + steps_html() + faq_html(faq) + others_html(sg) + form_html() + "</main>\n"
            + bottom_html(cfg_json(sg["seg"], case["dej"])))
    return head + body


def build_hvala():
    head = page_head("Hvala za povpraševanje", "Prejeli smo vaše povpraševanje. Odgovorimo po ogledu lokacije.",
                     URL + "hvala/", "noindex, follow")
    return head + '''<body>
<header class="top"><div class="wrap top-in"><a class="brand" href="/" aria-label="Meteorec, domača stran"><img src="/logo.svg" alt="" width="32" height="32"><span>Meteo<em>rec</em></span></a></div></header>
<main class="wrap thanks">
  <h1>Hvala, prejeli smo povpraševanje.</h1>
  <p class="lead">Odgovorimo vam na e-naslov ali telefon, ki ste ga vpisali, in se dogovorimo za ogled lokacije. Ponudbo pripravimo po ogledu.</p>
  <h2 class="next-h">Kaj sledi</h2>
  <ol class="next">
    <li><strong>Povpraševanje smo prejeli.</strong><span>Vaše podatke obdelamo samo za pripravo ponudbe.</span></li>
    <li><strong>Pregledamo lokacijo in zahteve.</strong><span>Preverimo, kaj morate spremljati in kje bo postaja stala.</span></li>
    <li><strong>Dogovorimo povezavo in postavitev.</strong><span>WiFi ali mobilni internet, napajanje in mesto postaje.</span></li>
    <li><strong>Pripravimo predlog rešitve.</strong><span>Ponudbo oblikujemo po ogledu lokacije.</span></li>
  </ol>
  <div class="row"><a class="btn" href="/podjetja/">Nazaj na paket</a><a class="btn btn-ghost" href="/">Na vreme v živo</a></div>
</main>
<script>window.PODJETJA_CFG={"pixel":%s};</script>
<script src="/podjetja/podjetja.js?v=%s" defer></script>
</body>
</html>
''' % (json.dumps(META_PIXEL_ID), ver("podjetja/podjetja.js"))


def write(rel, content):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print("zapisano", rel, len(content), "znakov")


def main():
    write("podjetja/index.html", build_main())
    write("podjetja/hvala/index.html", build_hvala())
    for sg in SEG_PAGES:
        write(f"podjetja/{sg['slug']}/index.html", build_segment(sg))


if __name__ == "__main__":
    main()
