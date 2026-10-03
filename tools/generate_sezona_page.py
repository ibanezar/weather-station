#!/usr/bin/env python3
"""
/sezona/ — »Kaj se ta čas dogaja v dolini«: sezonski vodič po Meteorecu.

Stran ne prinaša novih podatkov, ampak poveže obstoječe strani, ki so v tem
letnem času pomembne (jeseni gobe, prelazi in megla; pozimi poledica …), in
jim doda tisto, česar nobena od njih nima: klimatologijo letnega časa s
postaje (kdaj je običajno prva jesenska zmrzal, kdaj zadnja spomladanska,
koliko vročih dni) in kje je letošnje leto glede na to.

Vse številke so iz history.json in že committanih JSON-ov (gobarski indeks,
napoved MTR) — brez klicev na zunanje vire, isto načelo kot generate_story_card.
Datoteke drugih workflowov se berejo po DATUMU, ne po vrstnem redu workflowov
(glej CLAUDE.md, »Vrstni red workflowov ni zagotovljen«).

Teče dnevno v seo-smart-routine.yml.
"""
import datetime
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_seo_pages import (  # noqa: E402
    ROOT, SITE, MES_GEN, page_shell, crumbs_html, crumbs_schema, faq_schema,
    webpage_schema, fmtd, num, load_history, stn_badge,
)

URL = "/sezona/"
OUT = os.path.join(ROOT, "sezona", "index.html")

SEASONS = {
    "pomlad": {"months": (3, 4, 5), "label": "Pomlad", "loc": "spomladi"},
    "poletje": {"months": (6, 7, 8), "label": "Poletje", "loc": "poleti"},
    "jesen": {"months": (9, 10, 11), "label": "Jesen", "loc": "jeseni"},
    "zima": {"months": (12, 1, 2), "label": "Zima", "loc": "pozimi"},
}

# Povezave po letnem času: (pot, naslov, zakaj zdaj). Samo obstoječe strani —
# test_sezona.py preveri, da vsaka lokalna pot obstaja.
LINKS = {
    "jesen": [
        ("/gobarska-napoved/", "Gobarska napoved", "jesen je glavna gobarska sezona — indeks po območjih in vrstah"),
        ("https://crnivec.si/", "Črnivec", "prve slane in poledica na prelazu pridejo pred dolino"),
        ("/zima/", "Zima in prelazi", "meja sneženja in prevoznost prelazov, ko se ohladi"),
        ("/vodostaj-savinje/", "Vodostaj Savinje", "jesenska deževja so čas visokih voda"),
        ("/meteohmeljar/", "MeteoHmeljar", "po obiranju: stanje hmeljišč in agrometeorologija"),
        ("/vreme-za-padalce/", "Vreme za padalce", "mirni jesenski dnevi z inverzijo in meglo v dolini"),
        ("/opozorilo-pred-pozebo/", "Opozorilo pred pozebo", "ob prvi zmrzali: vrt in rože na balkonu"),
    ],
    "zima": [
        ("https://crnivec.si/", "Črnivec", "poledica, sneg in kamera na prelazu"),
        ("/zima/", "Zima in prelazi", "snežna odeja, meja sneženja, prevoznost prelazov"),
        ("/kakovost-zraka/", "Kakovost zraka", "pozimi inverzija zadrži dim v dolini"),
        ("/biovreme/", "Biovreme", "mraz in hitre spremembe tlaka"),
        ("/vreme/mesec/", "Vreme po mesecih", "koliko mraza je v dolini običajno"),
    ],
    "pomlad": [
        ("/opozorilo-pred-pozebo/", "Opozorilo pred pozebo", "pozebe po cvetenju so najdražje"),
        ("/agrometeo/", "Agrometeo", "začetek rastne dobe, toplotne vsote"),
        ("/kakovost-zraka/", "Kakovost zraka in cvetni prah", "pelod breze in trav"),
        ("/gobarska-napoved/", "Gobarska napoved", "smrčki in prve spomladanske vrste"),
        ("/invazivke/", "Invazivke", "kdaj se začnejo razraščati"),
    ],
    "poletje": [
        ("/nevihte/", "Nevihte", "nevihtna karta Slovenije in opozorila ARSO"),
        ("/toca/", "Toča", "poletna toča v dolini"),
        ("/vreme-za-padalce/", "Vreme za padalce", "termika z Golt"),
        ("/igra/", "Termika", "igra preleta na današnjem vremenu"),
        ("/meteohmeljar/", "MeteoHmeljar", "hmelj pred obiranjem"),
        ("/gobarska-napoved/", "Gobarska napoved", "poletne gobe po nevihtah"),
    ],
}

MIN_YEARS = 3


def season_of(d):
    for key, s in SEASONS.items():
        if d.month in s["months"]:
            return key
    raise ValueError(d)


def _doy(month, day):
    """Dan v nenavadnem (ne-prestopnem) letu — mediana datumov med leti."""
    return datetime.date(2001, month, day).timetuple().tm_yday


def _from_doy(doy):
    d = datetime.date(2001, 1, 1) + datetime.timedelta(days=int(round(doy)) - 1)
    return f"{d.day}. {MES_GEN[d.month]}"


def _low(v):
    return v.get("tempLow")


def first_autumn_frost(hist, year):
    """Prvi dan od 1. 7. z Tmin ≤ 0 °C. None, če ga ni ali leto ni pokrito
    (brez meritve 1. 9. ne vemo, ali ni bilo zmrzali že prej)."""
    if f"{year}-09-01" not in hist:
        return None
    d = datetime.date(year, 7, 1)
    end = datetime.date(year + 1, 1, 31)
    while d <= end:
        v = hist.get(d.isoformat())
        if v and _low(v) is not None and _low(v) <= 0:
            return d
        d += datetime.timedelta(days=1)
    return None


def last_spring_frost(hist, year):
    """Zadnji dan do 30. 6. z Tmin ≤ 0 °C. Zahteva pokrit maj in junij."""
    if f"{year}-05-15" not in hist or f"{year}-06-30" not in hist:
        return None
    last = None
    d = datetime.date(year, 1, 1)
    while d <= datetime.date(year, 6, 30):
        v = hist.get(d.isoformat())
        if v and _low(v) is not None and _low(v) <= 0:
            last = d
        d += datetime.timedelta(days=1)
    return last


def date_climatology(dates):
    """Mediana, najzgodnejši in najpoznejši datum (po dnevu v letu)."""
    if len(dates) < MIN_YEARS:
        return None
    doys = sorted((_doy(d.month, d.day), d) for d in dates)
    return {
        "median": _from_doy(st.median(x for x, _ in doys)),
        "earliest": doys[0][1],
        "latest": doys[-1][1],
        "n": len(doys),
    }


def hot_days_per_summer(hist, year):
    """Število vročih dni (Tmax ≥ 30 °C) v juniju–avgustu; None, če poletje ni
    skoraj polno pokrito."""
    days = [hist.get(f"{year}-{m:02d}-{d:02d}") for m in (6, 7, 8) for d in range(1, 32)
            if _valid(year, m, d)]
    have = [v for v in days if v and v.get("tempHigh") is not None]
    if len(have) < 80:
        return None
    return sum(1 for v in have if v["tempHigh"] >= 30)


def frost_days_per_winter(hist, year):
    """Dnevi z zmrzaljo v zimi dec(year-1)–feb(year); None, če ni skoraj polna."""
    days = []
    for (yy, m) in ((year - 1, 12), (year, 1), (year, 2)):
        days += [hist.get(f"{yy}-{m:02d}-{d:02d}") for d in range(1, 32) if _valid(yy, m, d)]
    have = [v for v in days if v and _low(v) is not None]
    if len(have) < 80:
        return None
    return sum(1 for v in have if _low(v) <= 0)


def _valid(y, m, d):
    try:
        datetime.date(y, m, d)
        return True
    except ValueError:
        return False


def read_gobe(today):
    try:
        d = json.load(open(os.path.join(ROOT, "gobarska-napoved", "index.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if d.get("date") == today.isoformat() else None


def read_mtr(today):
    """Dnevi napovedi MTR od danes naprej, izbrani po datumu (ne po lead)."""
    try:
        d = json.load(open(os.path.join(ROOT, "napoved-modela.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = [x for x in d.get("days", []) if x.get("date", "") >= today.isoformat()]
    return sorted(out, key=lambda x: x["date"])[:4]


def season_facts(hist, season, today):
    """(odstavki, qa) za letni čas — klimatologija postaje + letošnje stanje."""
    paras, qa = [], []
    y = today.year
    if season in ("jesen", "zima"):
        # Jesensko leto: frost v jeseni leta y, ali pozimi (jan) — za januar je to y-1.
        fy = y if today.month >= 7 else y - 1
        firsts = [f for f in (first_autumn_frost(hist, yy) for yy in range(2019, fy))
                  if f is not None]
        clim = date_climatology(firsts)
        this = first_autumn_frost(hist, fy)
        if clim:
            txt = (f"Prva jesenska zmrzal (najnižja temperatura ≤ 0 °C) je v Rečici ob Savinji "
                   f"običajno okoli <strong>{clim['median']}</strong> — najzgodneje "
                   f"{fmtd(clim['earliest'].isoformat())}, najpozneje "
                   f"{fmtd(clim['latest'].isoformat())} ({clim['n']} let meritev).")
            if this and this <= today:
                txt += (f" Letos je bila prva zmrzal {fmtd(this.isoformat())}." if fy == y
                        else f" Jeseni {fy} je bila prva zmrzal {fmtd(this.isoformat())}.")
            elif season == "jesen":
                lows = [(d, _low(v)) for d, v in hist.items()
                        if d >= f"{fy}-08-01" and _low(v) is not None]
                if lows:
                    d, lo = min(lows, key=lambda x: x[1])
                    txt += (f" Letos je še ni bilo — najnižja temperatura od avgusta je bila "
                            f"{num(lo)} °C ({fmtd(d)}).")
            paras.append(txt)
            qa.append(("Kdaj je v Rečici ob Savinji prva jesenska zmrzal?",
                       f"Po meritvah postaje IREICA1 običajno okoli {clim['median']}; "
                       f"v {clim['n']} letih najzgodneje {fmtd(clim['earliest'].isoformat())} "
                       f"in najpozneje {fmtd(clim['latest'].isoformat())}."))
    if season == "zima":
        wy = y if today.month <= 2 else y + 1
        counts = [c for c in (frost_days_per_winter(hist, yy) for yy in range(2020, wy))
                  if c is not None]
        if len(counts) >= MIN_YEARS:
            avg = st.mean(counts)
            paras.append(f"Zima ima v dolini povprečno <strong>{num(avg, 0)} dni z zmrzaljo</strong> "
                         f"(od {min(counts)} do {max(counts)} v {len(counts)} zimah).")
            qa.append(("Koliko dni z zmrzaljo ima zima v Rečici ob Savinji?",
                       f"Povprečno {num(avg, 0)}, od {min(counts)} do {max(counts)} v "
                       f"{len(counts)} zimah meritev postaje IREICA1."))
    if season == "pomlad":
        lasts = [f for f in (last_spring_frost(hist, yy) for yy in range(2020, y))
                 if f is not None]
        clim = date_climatology(lasts)
        if clim:
            paras.append(f"Zadnja spomladanska zmrzal je v Rečici ob Savinji običajno okoli "
                         f"<strong>{clim['median']}</strong> — najzgodneje "
                         f"{fmtd(clim['earliest'].isoformat())}, najpozneje "
                         f"{fmtd(clim['latest'].isoformat())} ({clim['n']} let meritev).")
            qa.append(("Kdaj je v Rečici ob Savinji zadnja spomladanska zmrzal?",
                       f"Po meritvah postaje IREICA1 običajno okoli {clim['median']}; "
                       f"najpozneje {fmtd(clim['latest'].isoformat())}. Do takrat je sadike "
                       f"varneje pustiti pod streho."))
    if season == "poletje":
        counts = {yy: c for yy in range(2020, y)
                  if (c := hot_days_per_summer(hist, yy)) is not None}
        if len(counts) >= MIN_YEARS:
            avg = st.mean(counts.values())
            top = max(counts, key=counts.get)
            paras.append(f"Poletje ima v dolini povprečno <strong>{num(avg, 0)} vročih dni</strong> "
                         f"(najvišja temperatura ≥ 30 °C); največ jih je bilo leta {top} "
                         f"({counts[top]}).")
            qa.append(("Koliko vročih dni ima poletje v Rečici ob Savinji?",
                       f"Povprečno {num(avg, 0)} dni s temperaturo 30 °C ali več; največ "
                       f"leta {top}, {counts[top]}."))
    return paras, qa


def now_block(today, gobe, mtr, season):
    items = []
    if gobe:
        items.append(f'<li><a href="/gobarska-napoved/">Gobarski indeks danes</a>: '
                     f'<strong>{gobe["index"]}</strong> ({gobe["level"].lower()}), '
                     f'najbolj obetavna vrsta {gobe["top_species_sl"].lower()}.</li>')
    if mtr:
        lows = [(x["date"], x["tmin"]) for x in mtr if x.get("tmin") is not None]
        if lows:
            d, lo = min(lows, key=lambda x: x[1])
            when = "danes" if d == today.isoformat() else fmtd(d)
            frost = " — <strong>možna zmrzal</strong>" if lo <= 1 else ""
            items.append(f'<li>Najnižja napovedana temperatura v naslednjih dneh '
                         f'(model <a href="/#tab-mtr">MTR</a>): {num(lo)} °C, {when}{frost}.</li>')
    if not items:
        return ""
    return ("  <h2>Ta čas v dolini</h2>\n  <ul class=\"sz-now\">\n    "
            + "\n    ".join(items) + "\n  </ul>\n")


def links_block(season):
    rows = []
    for href, name, why in LINKS[season]:
        rows.append(f'    <li><a href="{href}">{name}</a> — {why}</li>')
    return ("  <h2>Kaj na Meteorecu pogledati zdaj</h2>\n  <ul class=\"sz-links\">\n"
            + "\n".join(rows) + "\n  </ul>\n")


def past_seasons_block(season, today):
    links = []
    for yy in range(today.year, 2018, -1):
        slug = f"zima-{yy - 1}-{yy}" if season == "zima" else f"{season}-{yy}"
        if os.path.exists(os.path.join(ROOT, slug, "index.html")):
            label = f"Zima {yy - 1}–{yy}" if season == "zima" else f"{SEASONS[season]['label']} {yy}"
            links.append(f'<a href="/{slug}/">{label}</a>')
    if not links:
        return ""
    return ("  <h2>Pretekla leta</h2>\n  <p class=\"archive-intro\">"
            + " · ".join(links[:6]) + "</p>\n")


def build(hist, today):
    season = season_of(today)
    s = SEASONS[season]
    gobe = read_gobe(today) if season in ("jesen", "poletje", "pomlad") else None
    mtr = read_mtr(today)
    paras, qa = season_facts(hist, season, today)

    title = f"{s['label']} v Rečici ob Savinji: kaj se zdaj dogaja v dolini"
    desc = (f"{s['label']} v Zgornji Savinjski dolini po meritvah postaje IREICA1: "
            f"kdaj je običajno zmrzal, kaj se dogaja ta teden in katere napovedi so zdaj pomembne.")
    crumbs = [("Meteorec", "/"), (f"{s['label']} v dolini", None)]
    facts = "".join(f'  <p class="archive-intro">{p}</p>\n' for p in paras)
    faq_html = ""
    if qa:
        faq_html = ("  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
            f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
        ) + "\n  </div>\n")
    body = f'''{crumbs_html(crumbs)}
{stn_badge()}
  <h1 class="page-title">{s['label']} v Rečici ob Savinji</h1>
  <p class="post-meta">Posodobljeno {fmtd(today.isoformat())} · meritve postaje IREICA1</p>
  <p class="archive-intro">Kaj se {s['loc']} dogaja v Zgornji Savinjski dolini, kaj pravijo meritve
  postaje iz prejšnjih let in katere Meteorecove strani so ta čas najbolj uporabne.</p>
{facts}{now_block(today, gobe, mtr, season)}{links_block(season)}{past_seasons_block(season, today)}{faq_html}'''
    schema = "\n".join(x for x in (
        webpage_schema(URL, title, desc, today.isoformat()),
        crumbs_schema(crumbs),
        faq_schema(qa) if qa else "",
    ) if x)
    return page_shell(title, desc, URL, schema, body)


def main():
    today = datetime.date.today()
    html = build(load_history(), today)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ {URL} ({season_of(today)})")


if __name__ == "__main__":
    main()
