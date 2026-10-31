#!/usr/bin/env python3
"""
Pristajalna stran »Meteorec za podjetja« (/podjetja/) in zahvala (/podjetja/hvala/).

Vir vsebine je ta datoteka; `podjetja/podjetja.css` in `podjetja/podjetja.js` sta ročno pisana.
Cene: SHOW_PRICES = False skrije vse zneske (kartice kažejo »Cena po ogledu lokacije«), ostalo se ne
spremeni. Po spremembi generator poženi ročno in commitaj (ni v nobenem workflowu).

Stran ne bere nobene meritve postaje; živi gradnik v brskalniku bere samo zunanje vrednosti.
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
    dict(id="kmetija", dej="Kmetijstvo, sadjarstvo, vinogradništvo", title="Kmetija in sadovnjak",
         text="Pozeba, toča in vlaga tal na vašem nasadu, ne v sosednji dolini. Opozorilo dobite, ko je še čas za ukrep.",
         tags=["Pozeba", "Toča", "Vlaga tal"]),
    dict(id="kamp", dej="Turizem in gostinstvo", title="Kamp in turizem",
         text="Nevihte, višina vode in veter za goste na prostem. Odločitev o terasi ali prireditvi temelji na meritvi pri vas.",
         tags=["Nevihte", "Višina vode", "Veter"]),
    dict(id="gradbenistvo", dej="Gradbeništvo", title="Gradbeništvo",
         text="Veter pri delu na višini ter dež in temperatura pri vgrajevanju betona. Beton ne čaka na napačno napoved.",
         tags=["Veter", "Dež", "Temperatura"]),
    dict(id="obcina", dej="Občina ali javna ustanova", title="Občina",
         text="Požarna ogroženost in neurja za prebivalce, vtičnik za občinsko spletno stran.",
         tags=["Požarna ogroženost", "Neurja", "Vtičnik"]),
]

STEPS = [
    ("Ogled lokacije", "Pogledamo, kje bo postaja stala, in preverimo povezavo (WiFi ali mobilni internet)."),
    ("Postavitev postaje", "Namestimo postajo in senzorje na dogovorjeno mesto."),
    ("Nastavitve", "Nastavimo meritve, nadzorno ploščo in opozorila po vaših pravilih."),
    ("Predaja in usposabljanje", "Pokažemo, kako berete podatke in kaj sprožijo opozorila."),
    ("Podpora", "Spremljamo delovanje postaje in vam svetujemo, kadar je treba."),
]

FAQ = [
    ("Kaj, če na lokaciji ni WiFi?",
     "Postaja se poveže prek mobilnega interneta. Pred postavitvijo preverimo pokritost na lokaciji. "
     "Za povezavo brez WiFi velja pribitek, naročnina za mobilni internet pa je dodaten strošek."),
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
ILLUS = "podjetja/img/postaja-ilustracija.webp"   # splošna ilustracija, ne IREICA1; velja, dokler ni prave fotografije
ILLUS_ALT = "Ilustracija vremenske postaje s senzorji vetra, dežja in temperature ter sončno celico"


def ic(name, cls="ic"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false"><path d="{ICONS[name]}" '
            f'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')


STATS = [("calendar", "Od 2019", "lastna postaja IREICA1"), ("refresh", "Vsakih 5 minut", "nova meritev na strani"),
         ("signal", "WiFi ali mobilni internet", "kjer koli stoji postaja"), ("bell", "Opozorila na telefon", "pozeba, veter, nevihta (Pro)")]


def stats_html():
    return "".join(f'<li>{ic(i)}<span><strong>{e(t)}</strong>{e(d)}</span></li>' for i, t, d in STATS)


# ── Resnični podatki: postaja IREICA1 proti napovedi ─────────────────────────────────────
def sl(x, d=1, plus=False):
    t = f"{x:+.{d}f}" if plus else f"{x:.{d}f}"
    return t.replace("-", "−").replace(".", ",")


def noci(n):
    return f"{n} noč" if n % 100 == 1 else f"{n} noči"


def dnevi_s(n):
    return f"{n} dan" if n % 100 == 1 else (f"{n} dneva" if n % 100 == 2 else (f"{n} dni" if n % 100 in (3, 4) else f"{n} dni"))


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
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{e(error_alt(st_))}" preserveAspectRatio="xMidYMid meet">']
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
    return f'''<section class="band" id="pozeba" aria-labelledby="h-pozeba"><div class="wrap sec">
    <h2 class="rz" id="h-pozeba">Napoved je za dolino. Vi imate polje.</h2>
    <p class="rz">Napoved, ki jo vidite v aplikaciji, velja za celico na zemljevidu, ne za vaš nasad ali gradbišče. Spodaj je primerjava z našo pravo meritvijo.</p>
    <div class="data-grid">
      <div class="bignum rz">
        <b>{sl(abs(st_["mean"]), 1, True) if st_["mean"] > 0 else sl(st_["mean"], 1, True)} °C</b>
        <span>Povprečna napaka napovedi najnižje nočne temperature: napoved je bila {smer}. Obdobje: {fmt_date(st_["d0"])} do {fmt_date(st_["d1"])}, {noci(st_["n"])}.</span>
        <ul>
          <li><strong>{st_["hi"]}</strong> od {st_["n"]} noči: napoved za več kot 2 °C previsoka</li>
          <li><strong>{st_["lo"]}</strong> od {st_["n"]} noči: napoved za več kot 2 °C prenizka</li>
        </ul>
      </div>
      <figure class="rz">
        {error_svg(errs, st_)}
        <figcaption><span class="lg up"></span>napoved toplejša od meritve <span class="lg dn"></span>napoved hladnejša od meritve. Vsak stolpec je ena noč. Vir: napoved Open-Meteo, izdana dan prej, in meritev postaje IREICA1 v Rečici ob Savinji. <a href="/tocnost-napovedi/">Primerjava več virov</a>.</figcaption>
      </figure>
    </div>
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
      <div class="calc-head"><h3>Koliko noči bi vas lani opozorila postaja?</h3>
      <p>Nastavite mejo, pod katero želite opozorilo. Vsaka črtica je en dan zadnjih 12 mesecev, obarvani so dnevi, ko je postaja izmerila toliko ali manj.</p></div>
      <div class="calc-ctl"><label for="prag">Opozori me, ko temperatura pade na</label>
        <output id="prag-v" for="prag">0 °C</output>
        <input type="range" id="prag" min="-10" max="5" step="1" value="0" aria-describedby="prag-t"></div>
      <div class="calc-res" aria-live="polite"><b id="prag-n">{cnt}</b><span id="prag-t">{"noč" if cnt % 100 == 1 else "noči"} od {n} z meritvijo, ko je postaja izmerila 0 °C ali manj.</span></div>
      <div class="noci" id="noci" aria-hidden="true">{"".join(bars)}</div>
      <div class="noci-os"><span>{fmt_date(series[0][0])}</span><span>najhladnejša: {sl(min(vals))} °C ({fmt_date(coldest[0])})</span><span>{fmt_date(series[-1][0])}</span></div>
      <p class="fine">Meritev postaje IREICA1 v Rečici ob Savinji (dnevni minimum). Na vašem polju bo drugače, ravno zato je smiselna lastna postaja. Brez meritve na lokaciji tega ne veste.</p>
    </div>'''


NOC = [("21.00", "moon", "Večer", "Napoved obeta jasno noč, najnižja temperatura naj bi ostala nad ničlo."),
       ("00.40", "thermo", "Ohlajanje", "Postaja na vašem polju beleži, da zrak pada hitreje, kot je napovedano."),
       ("02.10", "bell", "Opozorilo", "Temperatura doseže mejo, ki ste jo nastavili. Telefon zavibrira."),
       ("02.25", "flame", "Ukrep", "Zaščito (škropljenje, ogrevanje, kritje) vklopite, ko je še čas."),
       ("07.30", "dash", "Pregled", "Zjutraj vidite, kdaj je padlo in kako dolgo je trajalo.")]
ICONS["moon"] = "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"


def noc_html():
    items = "".join(
        f'<li style="--i:{i}"><span class="cas">{t}</span><span class="pika">{ic(icon)}</span><h3>{e(h)}</h3><p>{e(txt)}</p></li>'
        for i, (t, icon, h, txt) in enumerate(NOC))
    return f'''<section class="band band-dark" id="noc" aria-labelledby="h-noc"><div class="wrap sec">
    <p class="oz rz">PRIMER</p>
    <h2 class="rz" id="h-noc">Ena noč na vašem polju</h2>
    <p class="rz">Izmišljen primer, kako lahko poteka noč s pozebo. Ure in vrednosti so ponazoritev, ne meritev.</p>
    <ol class="noc" id="noc-list">{items}</ol>
  </div></section>'''


PARTS = [
    dict(id="veter", name="Merilnik vetra", x=52, y=5, text="Meri hitrost in smer vetra ter sunke. Za delo na višini, nanos sredstev in prireditve na prostem."),
    dict(id="dez", name="Dežemer", x=89, y=41, text="Meri količino in jakost padavin. Za betoniranje, košnjo, obiranje in odločitve o termenu del."),
    dict(id="temp", name="Temperatura in vlaga", x=71, y=70, text="Senzor v zaščitnem ohišju meri temperaturo in vlago zraka. Iz tega izračunamo tudi rosišče, osnovo za opozorilo pred pozebo."),
    dict(id="sonce", name="Sončna celica", x=27, y=38, text="Napaja postajo tam, kjer ni vtičnice. Način napajanja izberemo po ogledu lokacije."),
    dict(id="zbiralnik", name="Zbiralnik podatkov", x=53, y=86, text="Zbira meritve in jih pošlje prek WiFi ali mobilnega interneta na nadzorno ploščo ali v aplikacijo."),
]


def shema_html():
    full = os.path.join(ROOT, PHOTO)
    pins = ""
    if os.path.exists(full):
        from PIL import Image
        w, h = Image.open(full).size
        art = f'<img src="/{PHOTO}" alt="{e(PHOTO_ALT)}" width="{w}" height="{h}" loading="lazy">'
        cap = "Postaja IREICA1, Rečica ob Savinji, 366 m"
    else:
        from PIL import Image
        w, h = Image.open(os.path.join(ROOT, ILLUS)).size
        art = f'<img class="illus" src="/{ILLUS}" alt="{e(ILLUS_ALT)}" width="{w}" height="{h}" loading="lazy">'
        cap = "Ilustracija: primer postaje (ni naša postaja IREICA1)"
        pins = "".join(
            f'<button class="pin" type="button" data-part="{p["id"]}" style="left:{p["x"]}%;top:{p["y"]}%" aria-label="{e(p["name"])}"><span>{i}</span></button>'
            for i, p in enumerate(PARTS, 1))
    lst = "".join(
        f'<li><button class="part" type="button" data-part="{p["id"]}" data-text="{e(p["text"])}" aria-pressed="false"><span class="num">{i}</span><span>{e(p["name"])}</span></button></li>'
        for i, p in enumerate(PARTS, 1))
    return f'''<section class="band band-dark photo" id="shema" aria-labelledby="h-shema">
  <div class="wrap photo-grid">
    <figure class="photo-art rz"><div class="art-wrap">{art}{pins}</div><figcaption>{e(cap)}</figcaption></figure>
    <div class="photo-text rz">
      <h2 class="rz" id="h-shema">Kaj meri postaja</h2>
      <p>Izberite del postaje in poglejte, kaj meri ter za kaj ga uporabite.</p>
      <ul class="parts">{lst}</ul>
      <div class="part-info" id="part-info" aria-live="polite"><b id="part-name">{e(PARTS[0]["name"])}</b><p id="part-text">{e(PARTS[0]["text"])}</p></div>
      <p class="fine">Vlaga tal, senzor strel in drugi senzorji so po dogovoru (paket Premium ali Po meri).</p>
    </div>
  </div>
</section>'''


def izjava_html():
    return '''<section class="band band-yellow" aria-label="Sporočilo"><div class="wrap"><p class="izjava rz">Napoved ne pozna vašega polja. <span>Postaja ga pozna.</span></p></div></section>'''


def price_block(p):
    if not SHOW_PRICES:
        return '<div class="price"><span class="price-note">Cena po ogledu lokacije</span></div>'
    once = ("od " if p["from_"] else "") + eur(p["once"])
    sim = (f'<div class="sim-add" data-sim-add hidden>Brez WiFi: + {eur(SIM_ONCE)} enkratno, + {eur(SIM_MONTH)} na mesec</div>')
    return (f'<div class="price"><div class="price-once"><strong>{once}</strong> <span>enkratno</span></div>'
            f'<div class="price-month">{"od " if p["id"] == "po-meri" else ""}{eur(p["month"])} <span>na mesec</span></div>{sim}</div>')


def package_card(p):
    items = "".join(f"<li>{CHECK}<span>{e(i)}</span></li>" for i in p["items"])
    cls = "card pack rz" + (" custom" if p.get("custom") else "")
    return f'''      <article class="{cls}" id="paket-{p["id"]}">
        <h3>{e(p["name"])}</h3>
        <p class="for">{e(p["who"])}</p>
        <div class="conn" data-conn>Povezava: WiFi</div>
        <ul>{items}</ul>
        {price_block(p)}
        <a class="btn btn-ghost" href="#povprasevanje" data-paket="{p["id"]}" aria-label="Izberem paket {e(p["name"])}">Izberem paket</a>
      </article>'''


def case_card(c):
    tags = "".join(f'<li>{ic(TAG_ICON[t], "ic-s")}{e(t)}</li>' for t in c["tags"])
    return f'''      <article class="card case rz" id="{c["id"]}" data-dej="{e(c["dej"])}" tabindex="-1">
        <span class="case-flag" hidden>Ponudba za vas</span>
        <span class="tile">{ic(CASE_ICON[c["id"]])}</span>
        <h3>{e(c["title"])}</h3>
        <p>{e(c["text"])}</p>
        <ul class="tags" aria-label="Kaj spremljate">{tags}</ul>
        <a class="link" href="#povprasevanje" data-segment="{c["id"]}">Zahtevajte ponudbo {ARROW}</a>
      </article>'''


PLUS = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 12h14M12 5v14" fill="none" stroke="currentColor" '
        'stroke-width="2.2" stroke-linecap="round"/></svg>')

MARQUEE = ["Kmetije", "Sadovnjaki", "Vinogradi", "Hmeljarji", "Čebelarji", "Kampi", "Turizem", "Gostinstvo",
           "Gradbeništvo", "Občine", "Prireditve", "Športni klubi"]


def marquee_html():
    one = "".join(f"<span>{e(m)}</span>" for m in MARQUEE)
    return one + one.replace("<span>", '<span aria-hidden="true">')


def faq_items():
    return "\n".join(
        f'      <details class="rz"><summary><span>{e(q)}</span><i>{PLUS}</i></summary><div class="odg"><div><p>{e(a)}</p></div></div></details>' for q, a in FAQ)


def schema_blocks():
    page = {"@context": "https://schema.org", "@type": "WebPage", "@id": SITE + URL, "name": TITLE,
            "description": DESC, "url": SITE + URL, "inLanguage": "sl",
            "isPartOf": {"@id": SITE + "/#website"}, "image": SITE + "/og/podjetja.jpg"}
    service = {
        "@context": "https://schema.org", "@type": "Service", "@id": SITE + URL + "#storitev",
        "name": "Vremenska postaja za podjetja z nadzorno ploščo in opozorili",
        "serviceType": "Postavitev in vzdrževanje vremenske postaje",
        "description": DESC,
        "provider": {"@type": "Organization", "name": "Meteorec", "url": SITE + "/",
                     "founder": {"@id": SITE + "/#person"}},
        "areaServed": {"@type": "AdministrativeArea", "name": "Zgornja Savinjska dolina"},
        "audience": {"@type": "BusinessAudience", "name": "Kmetije, turizem, gradbeništvo, občine"},
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
    faq = {"@context": "https://schema.org", "@type": "FAQPage",
           "mainEntity": [{"@type": "Question", "name": q,
                           "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Meteorec", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "Za podjetja"}]}
    return ld(page) + ld(service) + ld(faq) + ld(crumbs)


PHONE_HTML = '''<div class="phone" role="img" aria-label="Primer prikaza na telefonu: živa meritev postaje IREICA1 in primer opozorila">
        <span class="ph-notch"></span>
        <div class="ph-screen">
          <div class="ph-head"><span class="ph-brand">Meteo<em>rec</em></span><span class="ph-stn">IREICA1 · Rečica</span></div>
          <div class="ph-hero"><span class="ph-lbl">Zdaj</span><strong id="ph-temp">–</strong><span class="ph-sub" id="ph-time">Nalagam meritev</span></div>
          <div class="ph-grid">
            <div class="ph-t t-hum"><span>Vlaga</span><b id="ph-hum">–</b></div>
            <div class="ph-t t-pres"><span>Tlak</span><b id="ph-pres">–</b></div>
            <div class="ph-t t-wind"><span>Veter</span><b id="ph-wind">–</b></div>
            <div class="ph-t t-rain"><span>Dež danes</span><b id="ph-rain">–</b></div>
            <div class="ph-t t-dew"><span>Rosišče</span><b id="ph-dew">–</b></div>
            <div class="ph-t t-gust"><span>Sunki</span><b id="ph-gust">–</b></div>
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


def build_main():
    cfg = {"worker": WORKER, "pixel": META_PIXEL_ID, "email": CONTACT_EMAIL, "showPrices": SHOW_PRICES,
           "sim": {"once": SIM_ONCE, "month": SIM_MONTH}}
    head = page_head(TITLE, DESC, URL, "index, follow, max-image-preview:large", og_title="Vreme na vašem polju",
                     extra=schema_blocks())
    vat = (f'<p class="fine">Vse cene so brez DDV; obračunamo ga po stopnji {VAT_PCT} %. '
           f'Končno ceno določimo po ogledu lokacije.</p>') if SHOW_PRICES else ""
    sim_note = ""
    series, errs = load_data()
    return head + f'''<body>
<a class="skip" href="#vsebina">Preskoči na vsebino</a>
<header class="top"><div class="wrap top-in">
  <a class="brand" href="/" aria-label="Meteorec, domača stran"><img src="/logo.svg" alt="" width="32" height="32"><span>Meteo<em>rec</em></span></a>
  <nav aria-label="Razdelki"><a href="#primeri">Primeri</a><a href="#paketi">Paketi</a><a href="#faq">Vprašanja</a><a class="btn btn-sm" href="#povprasevanje">Ponudba</a></nav>
  <button class="burger" id="burger" type="button" aria-label="Odpri meni" aria-expanded="false" aria-controls="mob"><i></i><i></i></button>
</div></header>
<nav class="mob" id="mob" aria-label="Meni">
  <a href="#primeri">Primeri</a><a href="#paketi">Paketi</a><a href="#kako">Kako poteka</a><a href="#faq">Vprašanja</a>
  <a class="btn btn-hero" href="#povprasevanje">Zahtevajte ponudbo</a>
</nav>
<main id="vsebina">
<section class="hero" aria-labelledby="h1">
  <div class="aurora" aria-hidden="true"><i></i><i></i></div>
  <div class="wrap hero-grid">
    <div class="hero-text">
      <p class="tag">METEOREC ZA PODJETJA</p>
      <p class="old">Vreme v sosednji dolini.</p>
      <h1 id="h1"><span class="rv"><span style="--i:0">Vreme</span></span> <span class="rv"><span style="--i:1">na</span></span> <mark><span class="rv"><span style="--i:2">vašem</span></span> <span class="rv"><span style="--i:3">polju.</span></span></mark></h1>
      <p class="lead">Postavimo vremensko postajo, nastavimo vse in vam predamo nadzorno ploščo ali aplikacijo. Naj vaš posel ne trpi zaradi napačne napovedi.</p>
      <div class="row">
        <a class="btn btn-hero" href="#povprasevanje" data-cta="hero">Zahtevajte ponudbo po meri</a>
        <a class="btn btn-line" href="#paketi">Poglejte pakete</a>
      </div>
    </div>
    <div class="hero-art" aria-hidden="false">
      {PHONE_HTML}
      <div class="chip chip-a" aria-hidden="true"><span class="dot live-dot"></span>V živo z IREICA1</div>
      <div class="chip chip-b" aria-hidden="true">Opozorila na telefon</div>
    </div>
  </div>
</section>
<div class="stats"><ul class="wrap stats-list">{stats_html()}</ul></div>

  <div class="trak" aria-label="Za koga"><div class="trak-in">{marquee_html()}</div></div>

  <section class="band"><div class="wrap sec" id="primeri" aria-labelledby="h-primeri">
    <h2 class="rz" id="h-primeri">Za koga je postaja</h2>
    <p>Izberite dejavnost, ki je najbližja vaši. Postajo prilagodimo tistemu, kar morate spremljati.</p>
    <div class="grid cases">
{chr(10).join(case_card(c) for c in CASES)}
    </div>
  </div></section>

  {izjava_html()}

  {napoved_html(errs)}

  <section class="band band-alt" id="prag-sekcija"><div class="wrap sec">{prag_html(series)}</div></section>

  {noc_html()}

  <section class="band band-alt"><div class="wrap sec proof" id="dokaz" aria-labelledby="h-dokaz">
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
          <div><dt>Temperatura</dt><dd id="lw-temp">…</dd></div>
          <div><dt>Veter</dt><dd id="lw-wind">…</dd></div>
          <div><dt>Dež danes</dt><dd id="lw-rain">…</dd></div>
        </dl>
        <p class="live-time" id="lw-time" aria-live="polite">Nalagam zadnjo meritev.</p>
      </aside>
    </div>
  </div></section>

  {shema_html()}

  <section class="band"><div class="wrap sec" id="paketi" aria-labelledby="h-paketi">
    <h2 class="rz" id="h-paketi">Izberite paket ali ga sestavimo skupaj</h2>
    <p>Najprej povezava: postaja potrebuje pot do interneta. Kjer imate WiFi, je preprosto. Kjer ga nimate, uporabimo mobilni internet.</p>
    <fieldset class="seg">
      <legend>Povezava postaje</legend>
      <label for="c-wifi"><input type="radio" name="conn" id="c-wifi" value="wifi" checked>Z WiFi signalom</label>
      <label for="c-sim"><input type="radio" name="conn" id="c-sim" value="sim">Brez WiFi (mobilni internet)</label>
    </fieldset>
    <p class="note" id="conn-note" aria-live="polite"></p>
    <div class="grid packs">
{chr(10).join(package_card(p) for p in PACKAGES)}
    </div>
    {vat}{sim_note}
  </div></section>

  <section class="band band-alt"><div class="wrap sec" id="kako" aria-labelledby="h-kako">
    <h2 class="rz" id="h-kako">Kako poteka</h2>
    <ol class="steps">
{chr(10).join(f'      <li class="rz">{ic(STEP_ICON[i])}<strong>{e(t)}</strong><span>{e(d)}</span></li>' for i, (t, d) in enumerate(STEPS))}
    </ol>
  </div></section>

  <section class="band"><div class="wrap sec" id="faq" aria-labelledby="h-faq">
    <h2 class="rz" id="h-faq">Pogosta vprašanja</h2>
    <div class="faq">
{faq_items()}
    </div>
  </div></section>

  <section class="band band-alt"><div class="wrap sec" id="povprasevanje" aria-labelledby="h-vprasalnik">
    <span id="po-meri"></span>
    <h2 class="rz" id="h-vprasalnik">Povejte nam, kaj potrebujete</h2>
    <p>Izpolnite vprašalnik. Iz odgovorov sestavimo ponudbo po ogledu lokacije.</p>
    <form class="rz" id="q" novalidate autocomplete="on">
      <p class="chosen" id="chosen" hidden></p>
      <div class="f"><label for="f-firma"><span>Podjetje ali kmetija</span></label><input type="text" id="f-firma" name="firma" autocomplete="organization" maxlength="120" required></div>
      <div class="f"><label for="f-kraj"><span>Kraj in lokacija postaje</span></label><input type="text" id="f-kraj" name="kraj" placeholder="npr. sadovnjak nad vasjo" maxlength="160" required></div>
      <div class="f"><label for="f-panoga"><span>Dejavnost</span></label><select id="f-panoga" name="dejavnost">{FIELD["dej"]}</select></div>
      <div class="f"><label for="f-st"><span>Število postaj</span></label><select id="f-st" name="postaj">{FIELD["postaj"]}</select></div>
      <fieldset class="f wide"><legend>Kaj morate spremljati?</legend>
        <div class="chips">
{FIELD["chips_m"]}
        </div>
      </fieldset>
      <fieldset class="f wide"><legend>Je na lokaciji WiFi signal?</legend>
        <div class="chips">
{FIELD["chips_w"]}
        </div>
      </fieldset>
      <div class="f wide"><label for="f-opomba"><span>Opombe in posebne želje (neobvezno)</span></label><textarea id="f-opomba" name="opomba" rows="3" maxlength="1000"></textarea></div>
      <div class="f wide"><label for="f-kontakt"><span>E-naslov ali telefonska številka</span></label><input type="text" id="f-kontakt" name="kontakt" autocomplete="email" inputmode="email" maxlength="120" required aria-describedby="kontakt-help"><small id="kontakt-help">Vpišite enega od obeh. Na ta naslov ali številko odgovorimo.</small></div>
      <div class="f wide hp" aria-hidden="true"><label for="f-web">Spletna stran</label><input type="text" id="f-web" name="website" tabindex="-1" autocomplete="off"></div>
      <input type="hidden" name="paket" id="h-paket"><input type="hidden" name="povezava" id="h-povezava"><input type="hidden" name="segment" id="h-segment">
      <input type="hidden" name="utm_source"><input type="hidden" name="utm_medium"><input type="hidden" name="utm_campaign"><input type="hidden" name="utm_content"><input type="hidden" name="fbclid">
      <div class="f wide consent"><label for="f-soglasje"><input type="checkbox" id="f-soglasje" name="soglasje" required><span>Strinjam se, da Meteorec obdela moje podatke za pripravo ponudbe, kot piše v <a href="/zasebnost.html#povprasevanja">politiki zasebnosti</a>.</span></label></div>
      <p class="err" id="form-err" role="alert" hidden></p>
      <div class="f wide"><button class="btn" type="submit" id="send">Pošljite povpraševanje</button></div>
      <noscript><p class="err">Za oddajo obrazca potrebujete vklopljen JavaScript.</p></noscript>
    </form>
  </div></section>
</main>
<footer class="foot">
  <div class="wrap">
    <span>Meteorec, Zgornja Savinjska dolina · <a href="/">meteorec.si</a></span>
    <span><a href="/zasebnost.html">Zasebnost</a> · <a href="/o-postaji.html">O postaji</a> · <a href="/tocnost-napovedi/">Točnost napovedi</a></span>
  </div>
</footer>
<div class="cookie" id="cookie" role="region" aria-label="Piškotki in merjenje obiska" hidden>
  <p>Z vašim soglasjem merimo obisk in uspeh oglasov (Google, Meta). Brez soglasja se ti sledilniki ne naložijo. <a href="/zasebnost.html">Več</a></p>
  <div class="row"><button class="btn btn-sm" type="button" data-consent="accepted">Sprejmem</button><button class="btn btn-sm btn-ghost" type="button" data-consent="declined">Zavrnem</button></div>
</div>
<script>window.PODJETJA_CFG={json.dumps(cfg, ensure_ascii=False)};</script>
<script src="/podjetja/podjetja.js?v={ver("podjetja/podjetja.js")}" defer></script>
</body>
</html>
'''


def build_hvala():
    head = page_head("Hvala za povpraševanje", "Prejeli smo vaše povpraševanje. Odgovorimo po ogledu lokacije.",
                     URL + "hvala/", "noindex, follow")
    return head + '''<body>
<header class="top"><div class="wrap top-in"><a class="brand" href="/" aria-label="Meteorec, domača stran"><img src="/logo.svg" alt="" width="32" height="32"><span>Meteo<em>rec</em></span></a></div></header>
<main class="wrap thanks">
  <h1>Hvala, prejeli smo povpraševanje.</h1>
  <p class="lead">Odgovorimo vam na e-naslov ali telefon, ki ste ga vpisali, in se dogovorimo za ogled lokacije. Ponudbo pripravimo po ogledu.</p>
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


if __name__ == "__main__":
    main()
