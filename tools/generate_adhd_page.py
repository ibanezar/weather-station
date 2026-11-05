#!/usr/bin/env python3
"""tools/generate_adhd_page.py — /adhd/: vreme in ADHD (5 dni + okno za gibanje na prostem po urah).

POMEMBNA RAZLIKA od /migrena/ in /astma/: za vpliv vremena NA SIMPTOME ADHD ni trdnih dokazov, zato ocena
ne trdi, da vreme sproži simptome. Meri tri stvari, ki jih vreme res spreminja in ki so pri ADHD pogosto del
vsakdanjih navad: gibanje na prostem, spanje (topla noč) in prenašanje vročine (+ dnevna svetloba kot šibak
dejavnik). Ne dodajaj dejavnikov tipa »tlak sproži nemir« brez dokaza.

Ni zdravniški nasvet. Modelska napoved Open-Meteo za Rečico ob Savinji; notranjih meritev postaje tu ni in ne smejo
priti (CLAUDE.md). Konfiguracija za day_score_common.py (isti pogon kot /vreme-za-pse/).
"""
import datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, bands_desc, mean, rain_pts, storm_pts, wind_pts, esc  # noqa: E402
import generate_seo_pages as seo  # noqa: E402

HEAT_TH = (28, 32, 35)          # občutena °C
COLD_TH = (0, -5, -10)          # najtoplejša občutena °C v dnevu; nižje = slabše
NIGHT_TH = (16, 18, 20)         # najnižja temperatura noči, °C (20 °C = tropska noč)
LIGHT_MIN_WM2 = 120             # pod tem je dan »temen« (1 točka)
FAB_TAYLOR = ("Faber Taylor, A. in Kuo, F. E. (2009). Children with attention deficits concentrate better after walk in the park. "
              "Journal of Attention Disorders, 12(5), 402–409.")


def night_min(c, d):
    """Najnižja temperatura noči, ki se začne zvečer dneva d (22.00 do 6.00 naslednjega dne), ali None.
    Brez celotne noči (zadnji dan napovedi nima jutra po sebi) ocene ne ugibamo."""
    nxt = (datetime.date.fromisoformat(d) + datetime.timedelta(days=1)).isoformat()
    v = c.vals("temperature_2m", d, 22, 23) + c.vals("temperature_2m", nxt, 0, 6)
    return min(v) if len(v) >= 9 else None


def day_fn(c, d):
    pts, det = {}, {}
    pts["dez"], det["dez"] = rain_pts(c, d, 8, 19, cap=2, sum_veto=2.0)
    cmax = max(c.vals("apparent_temperature", d, 9, 16), default=None)
    pts["mraz"] = bands_desc(cmax, COLD_TH)
    det["mraz"] = (f"najtoplejši del dneva občutena do {seo.num(cmax, 0)} °C" if cmax is not None else "model ne vrača podatka")
    w, wt = wind_pts(c, d, (15, 25, 35), (35, 50, 65), 9, 18)
    pts["veter"], det["veter"] = min(w, 2), wt
    pts["nevihta"], det["nevihta"] = storm_pts(c, d, 8, 20)
    hmax = max(c.vals("apparent_temperature", d, 10, 18), default=None)
    pts["vrocina"] = bands(hmax, HEAT_TH)
    det["vrocina"] = f"občutena do {seo.num(hmax, 0)} °C" if hmax is not None else "model ne vrača podatka"
    nm = night_min(c, d)
    pts["noc"] = bands(nm, NIGHT_TH)
    det["noc"] = (f"najnižja temperatura noči {seo.num(nm, 0)} °C" if nm is not None
                  else "napoved za noč še ni na voljo")
    sun = mean(c.vals("shortwave_radiation", d, 10, 15))
    pts["svetloba"] = 1 if (sun is not None and sun < LIGHT_MIN_WM2) else 0
    det["svetloba"] = (f"sončno sevanje opoldne povprečno {seo.num(sun, 0)} W/m²" if sun is not None else "model ne vrača podatka")
    return pts, det


def hour_fn(c, h):
    """Ocena ure za gibanje na prostem (0–3). Temne ure štejejo kot zmerna ovira."""
    a = c.at("apparent_temperature", h)
    prob = c.at("precipitation_probability", h) or 0
    pr = c.at("precipitation", h) or 0
    gust = c.at("wind_gusts_10m", h) or 0
    rad = c.at("shortwave_radiation", h)
    s = 0
    if a is not None:
        s = max(bands(a, HEAT_TH), bands_desc(a, COLD_TH))
    s = max(s, 3 if pr >= 0.5 else 2 if (pr >= 0.2 or prob >= 60) else 1 if prob >= 30 else 0)
    s = max(s, 2 if gust >= 55 else 1 if gust >= 40 else 0)
    if rad is not None and rad < 10:
        s = max(s, 2)
    if (c.at("weather_code", h) or 0) >= 95:
        s = 3
    return s


SCHOOL_WALK_HOURS = (7, 8)        # urna vrednost z žigom T velja za T-1..T: zajame pot med 6.00 in 8.00
AFTER_SCHOOL = (13, 19)


def school_walk(c, d, from_hour=0):
    """Pot v šolo: najslabša ura med 7.00 in 8.00 (raven kot pri oknu po urah) + občutena temperatura, dež in tema.
    Vrne (raven, besedilo) ali None, če je čas že mimo."""
    hrs = [h for h in SCHOOL_WALK_HOURS if h >= from_hour]
    if not hrs:
        return None
    keys = [f"{d}T{h:02d}:00" for h in hrs]
    lvl = max(hour_fn(c, k) for k in keys)
    app = [c.at("apparent_temperature", k) for k in keys if c.at("apparent_temperature", k) is not None]
    prob = max((c.at("precipitation_probability", k) or 0 for k in keys), default=0)
    dark = any((c.at("shortwave_radiation", k) is not None and c.at("shortwave_radiation", k) < 10) for k in keys)
    parts = [f"občutena {seo.num(min(app), 0)} °C"] if app else []
    if prob >= 50:
        parts.append(f"dež verjeten ({seo.num(prob, 0)} %)")
    if dark:
        parts.append("še temno")
    return lvl, ", ".join(parts) or "model ne vrača podatka"


def after_school(c, d, from_hour=0):
    """Najboljše okno po pouku (13.00–19.00) ali besedilo, zakaj ga ni. None = že mimo."""
    sc = D.hour_scores(CFG, c, d, AFTER_SCHOOL[0], AFTER_SCHOOL[1], max(from_hour, AFTER_SCHOOL[0]))
    if not sc:
        return None
    win = D.best_window(sc)
    return D.fmt_hours(*win) if win else "ni dobrega okna"


def parent_html(c, today):
    """Cel dan, ne od trenutne ure: stran je posnetek, ki ga cron zgradi ob poljubni uri (zamuja tudi po več ur),
    »že mimo« bi bil pogosto napačen. Zato from_hour tu ni uporabljen (funkciji ga znata zaradi testov)."""
    rows = []
    for i, label in enumerate(("Danes", "Jutri")):
        d = (today + datetime.timedelta(days=i)).isoformat()
        w = school_walk(c, d)
        walk = f"<strong>{esc(CFG['levels'][w[0]])}</strong> · {esc(w[1])}"
        a = after_school(c, d)
        rows.append(f"    <tr><th>{label}</th><td>{walk}</td><td>{esc(a)}</td></tr>")
    return f'''  <h2>Za starše: pot v šolo in čas po pouku</h2>
  <p class="archive-intro">Dva praktična trenutka dneva: kako bo na poti v šolo (med 7.00 in 8.00) in kdaj je po pouku (13.00–19.00) najboljše okno za gibanje na prostem. Za šolske dni; ob vikendih in počitnicah glejte okno po urah spodaj.</p>
  <div class="table-scroll" tabindex="0"><table class="stats">
    <tr><th></th><td>Pot v šolo (7.00–8.00)</td><td>Najboljše okno po pouku</td></tr>
{chr(10).join(rows)}
  </table></div>
  <p class="muted-note">Modelska napoved. Raven poti v šolo je enaka kot pri oknu po urah; »še temno« pomeni, da zunaj ob tisti uri še ni dnevne svetlobe (poskrbite za odsevnike).</p>'''


def sections(cfg, c, days, today):
    """Razdelek »Kaj vemo in česa ne«: brez tega bi stran delovala, kot da vreme dokazano vpliva na ADHD."""
    return {"after_hero": parent_html(c, today),
            "after_cards": f'''  <h2>Kaj o vremenu in ADHD vemo – in česa ne</h2>
  <div class="dv-card" style="font-size:.92rem">
    <div class="dv-grp" style="--gc:var(--g-1)"><h3>{D.icon("b", 18)}Česa ne vemo</h3>
      <p>Trdnih dokazov, da bi vreme (tlak, veter, vlaga, temperatura) samo po sebi poslabšalo simptome ADHD, ni. Zato ocena ne napoveduje simptomov in vremena ne obravnava kot sprožilca.</p></div>
    <div class="dv-grp" style="--gc:var(--g-3)"><h3>{D.icon("c", 18)}Kaj vreme spremeni</h3>
      <ul>
        <li><strong>Gibanje na prostem.</strong> Pri otrocih z ADHD so v majhni raziskavi (17 otrok) po 20-minutnem sprehodu v parku bolje reševali nalogo pozornosti kot po sprehodu po mestu. Vzorec je majhen, a gibanje na splošno pogosto koristi pozornosti. Dež, mraz, vročina in nevihte gibanje na prostem otežijo.</li>
        <li><strong>Spanje.</strong> Težave s spanjem so pri ADHD pogoste, pomanjkanje spanja pa pozornost še poslabša. Tople noči (od 20&nbsp;°C naprej jim pravimo tropske) spanje motijo.</li>
        <li><strong>Vročina in zdravila.</strong> Nekatera zdravila za ADHD lahko vplivajo na potenje, žejo in apetit. V vročini je zato smiselno piti več in iskati senco. Zdravil zaradi vremena ne spreminjajte sami; vprašajte zdravnika ali lekarnika.</li>
      </ul>
      <p class="dv-why">Vir za raziskavo: {esc(FAB_TAYLOR)}</p></div>
  </div>'''}


CFG = {
    "url": "/adhd/", "slug": "adhd", "crumb": "Vreme in ADHD",
    "short": "Vreme in ADHD",
    "title": "Vreme in ADHD pri otrocih: gibanje in spanje, 5 dni",
    "h1": "Vreme in ADHD pri otrocih: gibanje, spanje in vročina",
    "meta": "Za starše otrok z ADHD: dež, mraz, vročina, veter, nevihte, topla noč in svetloba",
    "kicker": "Za starše: gibanje in spanje danes · Zgornja Savinjska dolina",
    "levels": ["ugodno", "dobro", "zahtevno", "težavno"],
    "advice": [
        "Ugodni pogoji za gibanje na prostem in spanje. Izkoristite dnevno svetlobo.",
        "Pogoji so dobri; gibanje na prostem načrtujte v ugodnejšem delu dneva (okno po urah je spodaj).",
        "Vreme otežuje gibanje na prostem ali spanje. Poiščite krajše okno zunaj ali gibanje prestavite v zaprt prostor.",
        "Vreme bivanje na prostem zelo omejuje. Gibanje prestavite v zaprt prostor (stopnice, raztezanje, kratki odmori).",
    ],
    "th": (1, 2, 5), "day_fn": day_fn, "hour_fn": hour_fn,
    "groups": [("Gibanje", "Gibanje na prostem", ["dez", "mraz", "veter", "nevihta"]),
               ("Vročina", "Vročina in spanje", ["vrocina", "noc"]),
               ("Svetloba", "Svetloba", ["svetloba"])],
    "group_icons": ["b", "d", "c"],
    "factors": [
        ("dez", "Dež", "Dež gibanje na prostem otežuje; šteje največ 2 točki."),
        ("mraz", "Mraz", "Če je še v najtoplejšem delu dneva zelo mrzlo, je okno za gibanje na prostem kratko."),
        ("veter", "Veter", "Močan veter bivanje na prostem otežuje; šteje največ 2 točki. Ni ocena vpliva na simptome."),
        ("nevihta", "Nevihta", "Strela je nevarna; nevihta je takoj izrazita ovira za bivanje na prostem."),
        ("vrocina", "Vročina", "Vročina otežuje gibanje, nekatera zdravila za ADHD pa lahko vplivajo na potenje in žejo; pomembni so pitje in senca."),
        ("noc", "Topla noč", "Težave s spanjem so pri ADHD pogoste, tople noči pa spanje dodatno motijo. Uporabljena je napoved zunanje temperature."),
        ("svetloba", "Dnevna svetloba", "Svetel dan podpira uro telesa; ocena je omejena na 1 točko."),
    ],
    "rules": [
        ("Dež (8.–19. ure)", "verjetnost 20 / 40 / 60 %; ≥ 2 mm = 2", "največ 2 točki"),
        ("Mraz (9.–16. ure)", "najtoplejša občutena pod 0 / –5 / –10 °C", "najvišja občutena v dnevu"),
        ("Veter (9.–18. ure)", "povprečno 15 / 25 / 35 km/h; sunki 35 / 50 / 65 km/h", "največ 2 točki"),
        ("Nevihta (8.–20. ure)", "napovedana = 3", "koda vremena ≥ 95"),
        ("Vročina (10.–18. ure)", "občutena 28 / 32 / 35 °C", "najvišja občutena"),
        ("Topla noč", "najnižja temperatura noči 16 / 18 / 20 °C", "od 22.00 do 6.00; za zadnji dan napoved noči še ni na voljo"),
        ("Svetloba (10.–15. ure)", "sončno sevanje pod 120 W/m² = 1", "največ 1 točka"),
    ],
    "method_intro": "Ocena sešteje točke sedmih dejavnikov (0–3 na dejavnik, skupaj največ 17; manj je bolje). Raven: brez točk ugodno, 1 točka dobro, 2–4 točke zahtevno, 5 točk ali več težavno; izrazit dejavnik (3 točke) vedno da vsaj »zahtevno«. Pragovi so naši, niso klinični: pomagajo presoditi, kako udobno bo gibanje na prostem in spanje.",
    "limits": ["<strong>Dokazi o vplivu vremena na simptome so skromni.</strong> Ocena zato ne napoveduje simptomov; meri pogoje za navade, ki ADHD pogosto pomagajo (gibanje, spanje).",
               "<strong>ADHD je pri vsakem drugačen.</strong> Kar pomaga enemu (jutranji sprehod), drugemu ne pomaga nujno; dnevni urnik, šola in služba pogosto odločajo bolj kot vreme.",
               "<strong>Topla noč</strong> je ocena iz napovedi zunanje temperature, ne podatek o temperaturi v spalnici."],
    "intro_q": "Ali vreme vpliva na ADHD?",
    "intro_a": "Trdnih dokazov, da bi vreme samo po sebi poslabšalo simptome ADHD, ni. Vreme pa vpliva na navade, ki so pri ADHD pogosto pomembne: gibanje na prostem, spanje in prenašanje vročine. Ocena zato meri, kako vreme te navade olajša ali otežuje.",
    "disclaimer_lead": "To ni zdravniški nasvet.",
    "disclaimer": "Ocena ne napoveduje simptomov in ne nadomešča zdravljenja ali nasveta strokovnjaka. Zdravil zaradi vremena ne spreminjajte sami; za vprašanja o zdravilih se obrnite na zdravnika ali lekarnika.",
    "window_label": "Najboljše okno za gibanje na prostem", "window_none": "Danes ni dobrega okna za gibanje na prostem.",
    "strip_title": "Gibanje na prostem po urah", "strip_intro": "Ocena po urah od 6.00 do 22.00; temne ure štejejo kot zmerna ovira.",
    "faq": [
        ("Ali vreme vpliva na simptome ADHD?", "Trdnih dokazov za to ni. Vreme pa spreminja pogoje za gibanje na prostem, spanje in prenašanje vročine, ki so pri ADHD pogosto pomembni. Ocena meri to, ne simptomov."),
        ("Zakaj stran ocenjuje gibanje na prostem?", "Pri otrocih z ADHD so v majhni raziskavi (17 otrok; Faber Taylor in Kuo, 2009) po sprehodu v parku bolje reševali nalogo pozornosti kot po sprehodu po mestu. Vzorec je majhen, zato je to spodbuda za preizkus, ne zagotovilo."),
        ("Ali vročina vpliva na zdravila za ADHD?", "Nekatera zdravila lahko vplivajo na potenje, žejo in apetit, zato je v vročini smiselno piti več in iskati senco. Zdravil zaradi vremena ne spreminjajte sami; vprašajte zdravnika ali lekarnika."),
        ("Zakaj ocena upošteva toplo noč?", "Težave s spanjem so pri ADHD pogoste, tople noči pa spanje dodatno motijo. Ocena uporablja napoved zunanje najnižje temperature (od 20 °C naprej je tropska noč); temperature v spalnici ne pozna."),
        ("Ali naj otroka ob slabem vremenu pustim brez gibanja?", "Ne nujno. Ob dežju ali mrazu poskusite krajši odmor na prostem v ugodnejšem delu dneva ali gibanje v zaprtem prostoru (stopnice, raztezanje, kratki odmori med nalogami). Stran ne trdi, da je gibanje zdravilo; je le pogoj, ki ga vreme olajša ali otežuje."),
        ("Za koga je stran namenjena?", "Predvsem za starše otrok z ADHD, ki načrtujejo pot v šolo, čas po pouku in popoldanske dejavnosti. Uporabna je tudi za odrasle, a oceno razlagajte enako: kot pogoje za navade, ne kot napoved simptomov."),
        ("Ali je stran zdravniški nasvet?", "Ne. Je pregled vremenskih pogojev iz modelske napovedi. Za diagnozo, zdravljenje in zdravila se obrnite na zdravnika."),
    ],
    "links": [("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"), ("/biovreme/", "Biovreme →"),
              ("/astma/", "Vreme in astma →"), ("/migrena/", "Vreme in migrena →"),
              ("/vreme-za-kolesarje/", "Vreme za kolesarje →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Vreme in ADHD pri otrocih danes: {lvl}. Za starše: pot v šolo, okno za gibanje po pouku, spanje in vročina za 5 dni.",
    "sections": sections,
}

if __name__ == "__main__":
    D.main(CFG)
