#!/usr/bin/env python3
"""
Pristajalna stran »Meteorec za podjetja« (/podjetja/) in zahvala (/podjetja/hvala/).

Vir vsebine je ta datoteka; `podjetja/podjetja.css` in `podjetja/podjetja.js` sta ročno pisana.
Cene: SHOW_PRICES = False skrije vse zneske (kartice kažejo »Cena po ogledu lokacije«), ostalo se ne
spremeni. Po spremembi generator poženi ročno in commitaj (ni v nobenem workflowu).

Stran ne bere nobene meritve postaje; živi gradnik v brskalniku bere samo zunanje vrednosti.
"""
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
<link rel="stylesheet" href="/podjetja/podjetja.css">
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


def ic(name, cls="ic"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false"><path d="{ICONS[name]}" '
            f'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')


STATS = [("calendar", "Od 2019", "lastna postaja IREICA1"), ("refresh", "Vsakih 5 minut", "nova meritev na strani"),
         ("signal", "WiFi ali mobilni internet", "kjer koli stoji postaja"), ("bell", "Opozorila na telefon", "pozeba, veter, nevihta (Pro)")]


def stats_html():
    return "".join(f'<li>{ic(i)}<span><strong>{e(t)}</strong>{e(d)}</span></li>' for i, t, d in STATS)


def photo_html():
    full = os.path.join(ROOT, PHOTO)
    if os.path.exists(full):
        w, h = 1200, 800
        try:
            from PIL import Image
            w, h = Image.open(full).size
        except Exception:
            pass
        art = f'<img src="/{PHOTO}" alt="{e(PHOTO_ALT)}" width="{w}" height="{h}" loading="lazy">'
        cap = "Postaja IREICA1, Rečica ob Savinji, 366 m"
    else:
        art = STATION_SVG
        cap = "Ilustracija vremenske postaje"
    return f'''<section class="band band-dark photo" aria-labelledby="h-foto">
  <div class="wrap photo-grid">
    <figure class="photo-art">{art}<figcaption>{e(cap)}</figcaption></figure>
    <div class="photo-text">
      <h2 id="h-foto">Postaja, ki stoji od leta 2019</h2>
      <p>IREICA1 stoji v Rečici ob Savinji od leta 2019. Njene meritve vidite zgoraj v živo. Isti pristop prenesemo na vašo lokacijo: pravi senzorji na pravem mestu in podatki, ki jih lahko primerjate z napovedjo.</p>
      <ul class="facts">
        <li>{ic("pin")}<span>Postavitev na mesto, ki ga izberemo skupaj</span></li>
        <li>{ic("dash")}<span>Meritve na nadzorni plošči ali v aplikaciji</span></li>
        <li>{ic("bell")}<span>Opozorila, ko vrednost preseže vašo mejo</span></li>
      </ul>
    </div>
  </div>
</section>'''


def price_block(p):
    if not SHOW_PRICES:
        return '<div class="price"><span class="price-note">Cena po ogledu lokacije</span></div>'
    once = ("od " if p["from_"] else "") + eur(p["once"])
    sim = (f'<div class="sim-add" data-sim-add hidden>Brez WiFi: + {eur(SIM_ONCE)} enkratno, + {eur(SIM_MONTH)} na mesec</div>')
    return (f'<div class="price"><div class="price-once"><strong>{once}</strong> <span>enkratno</span></div>'
            f'<div class="price-month">{"od " if p["id"] == "po-meri" else ""}{eur(p["month"])} <span>na mesec</span></div>{sim}</div>')


def package_card(p):
    items = "".join(f"<li>{CHECK}<span>{e(i)}</span></li>" for i in p["items"])
    cls = "card pack" + (" custom" if p.get("custom") else "")
    return f'''      <article class="{cls}" id="paket-{p["id"]}">
        <h3>{e(p["name"])}</h3>
        <p class="for">{e(p["who"])}</p>
        <div class="conn" data-conn>Povezava: WiFi</div>
        <ul>{items}</ul>
        {price_block(p)}
        <a class="btn btn-ghost" href="#povprasevanje" data-paket="{p["id"]}">Izberem paket {e(p["name"])}</a>
      </article>'''


def case_card(c):
    tags = "".join(f'<li>{ic(TAG_ICON[t], "ic-s")}{e(t)}</li>' for t in c["tags"])
    return f'''      <article class="card case" id="{c["id"]}" data-dej="{e(c["dej"])}" tabindex="-1">
        <span class="case-flag" hidden>Ponudba za vas</span>
        <span class="tile">{ic(CASE_ICON[c["id"]])}</span>
        <h3>{e(c["title"])}</h3>
        <p>{e(c["text"])}</p>
        <ul class="tags" aria-label="Kaj spremljate">{tags}</ul>
        <a class="link" href="#povprasevanje" data-segment="{c["id"]}">Zahtevajte ponudbo {ARROW}</a>
      </article>'''


def faq_items():
    return "\n".join(
        f'      <details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in FAQ)


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


PHONE_SVG = '''<svg class="phone" viewBox="0 0 240 440" role="img" aria-label="Primer obvestila o pozebi na telefonu">
        <rect x="10" y="6" width="220" height="428" rx="36" fill="#18232B" stroke="#3B4C58" stroke-width="4"/>
        <rect x="88" y="18" width="64" height="10" rx="5" fill="#3B4C58"/>
        <rect x="26" y="52" width="188" height="92" rx="20" fill="#223340"/>
        <circle cx="52" cy="82" r="14" fill="#E4572E"/>
        <rect x="76" y="70" width="104" height="9" rx="4.5" fill="#E8EEF2"/>
        <rect x="76" y="88" width="126" height="7" rx="3.5" fill="#9FB0BB"/>
        <rect x="76" y="104" width="86" height="7" rx="3.5" fill="#9FB0BB"/>
        <rect x="26" y="160" width="188" height="64" rx="20" fill="#1B2F2B"/>
        <rect x="42" y="176" width="70" height="9" rx="4.5" fill="#5CC2BC"/>
        <rect x="42" y="194" width="130" height="7" rx="3.5" fill="#9FB0BB"/>
        <rect x="26" y="240" width="88" height="84" rx="18" fill="#223340"/>
        <rect x="126" y="240" width="88" height="84" rx="18" fill="#223340"/>
        <path d="M40 304 L58 286 L74 296 L98 266" fill="none" stroke="#5CC2BC" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        <rect x="140" y="256" width="60" height="8" rx="4" fill="#9FB0BB"/>
        <rect x="140" y="276" width="40" height="22" rx="6" fill="#FFD84D"/>
        <rect x="26" y="340" width="188" height="64" rx="20" fill="#223340"/>
      </svg>'''

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
    return head + f'''<body>
<a class="skip" href="#vsebina">Preskoči na vsebino</a>
<header class="top">
  <a class="brand" href="/" aria-label="Meteorec, domača stran"><img src="/logo.svg" alt="" width="32" height="32"><span>Meteo<em>rec</em></span></a>
  <nav aria-label="Razdelki"><a href="#primeri">Primeri</a><a href="#paketi">Paketi</a><a href="#faq">Vprašanja</a><a class="btn btn-sm" href="#povprasevanje">Ponudba</a></nav>
</header>
<main id="vsebina">
<section class="hero" aria-labelledby="h1">
  <div class="wrap hero-grid">
    <div class="hero-text">
      <p class="tag">METEOREC ZA PODJETJA</p>
      <p class="old">Vreme v sosednji dolini.</p>
      <h1 id="h1">Vreme na <mark>vašem polju.</mark></h1>
      <p class="lead">Postavimo vremensko postajo, nastavimo vse in vam predamo nadzorno ploščo ali aplikacijo. Naj vaš posel ne trpi zaradi napačne napovedi.</p>
      <div class="row">
        <a class="btn btn-hero" href="#povprasevanje" data-cta="hero">Zahtevajte ponudbo po meri</a>
        <a class="btn btn-line" href="#paketi">Poglejte pakete</a>
      </div>
    </div>
    <div class="hero-art" aria-hidden="false">
      {PHONE_SVG}
      <div class="chip chip-a" aria-hidden="true"><span class="dot"></span>Primer: opozorilo pred pozebo</div>
      <div class="chip chip-b" aria-hidden="true">Primer: veter pri delu na višini</div>
    </div>
  </div>
</section>
<div class="stats"><ul class="wrap stats-list">{stats_html()}</ul></div>

  <section class="band"><div class="wrap sec" id="primeri" aria-labelledby="h-primeri">
    <h2 id="h-primeri">Za koga je postaja</h2>
    <p>Izberite dejavnost, ki je najbližja vaši. Postajo prilagodimo tistemu, kar morate spremljati.</p>
    <div class="grid cases">
{chr(10).join(case_card(c) for c in CASES)}
    </div>
  </div></section>

  <section class="band band-alt"><div class="wrap sec proof" id="dokaz" aria-labelledby="h-dokaz">
    <h2 id="h-dokaz">Zakaj nam zaupati</h2>
    <div class="proof-grid">
      <div class="proof-text">
        <ul class="facts">
          <li>{CHECK}<span>Od leta 2019 imamo lastno postajo IREICA1 v Rečici ob Savinji (366 m, 46,3258° N, 14,9211° E).</span></li>
          <li>{CHECK}<span>Imamo več let meritev in sistem, ki napovedi ARSO, Open-Meteo in Yr.no primerja z izmerjenimi vrednostmi.</span></li>
          <li>{CHECK}<span>Isto delo, ki ga opravljamo za svojo postajo, opravimo za vašo: postavitev, nastavitev in spremljanje delovanja.</span></li>
        </ul>
        <a class="link" href="/tocnost-napovedi/">Oglejte si primerjavo napovedi z meritvami {ARROW}</a>
      </div>
      <aside class="live" aria-labelledby="live-h">
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

  {photo_html()}

  <section class="band"><div class="wrap sec" id="paketi" aria-labelledby="h-paketi">
    <h2 id="h-paketi">Izberite paket ali ga sestavimo skupaj</h2>
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
    <h2 id="h-kako">Kako poteka</h2>
    <ol class="steps">
{chr(10).join(f'      <li>{ic(STEP_ICON[i])}<strong>{e(t)}</strong><span>{e(d)}</span></li>' for i, (t, d) in enumerate(STEPS))}
    </ol>
  </div></section>

  <section class="band"><div class="wrap sec" id="faq" aria-labelledby="h-faq">
    <h2 id="h-faq">Pogosta vprašanja</h2>
    <div class="faq">
{faq_items()}
    </div>
  </div></section>

  <section class="band"><div class="wrap sec" id="povprasevanje" aria-labelledby="h-vprasalnik">
    <span id="po-meri"></span>
    <h2 id="h-vprasalnik">Povejte nam, kaj potrebujete</h2>
    <p>Izpolnite vprašalnik. Iz odgovorov sestavimo ponudbo po ogledu lokacije.</p>
    <form id="q" novalidate autocomplete="on">
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
<script src="/podjetja/podjetja.js" defer></script>
</body>
</html>
'''


def build_hvala():
    head = page_head("Hvala za povpraševanje", "Prejeli smo vaše povpraševanje. Odgovorimo po ogledu lokacije.",
                     URL + "hvala/", "noindex, follow")
    return head + '''<body>
<header class="top"><a class="brand" href="/" aria-label="Meteorec, domača stran"><img src="/logo.svg" alt="" width="32" height="32"><span>Meteo<em>rec</em></span></a></header>
<main class="wrap thanks">
  <h1>Hvala, prejeli smo povpraševanje.</h1>
  <p class="lead">Odgovorimo vam na e-naslov ali telefon, ki ste ga vpisali, in se dogovorimo za ogled lokacije. Ponudbo pripravimo po ogledu.</p>
  <div class="row"><a class="btn" href="/podjetja/">Nazaj na paket</a><a class="btn btn-ghost" href="/">Na vreme v živo</a></div>
</main>
<script>window.PODJETJA_CFG={"pixel":%s};</script>
<script src="/podjetja/podjetja.js" defer></script>
</body>
</html>
''' % json.dumps(META_PIXEL_ID)


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
