#!/usr/bin/env python3
"""
tools/generate_zima_page.py — MeteoZima, /zima/ podportal (hub + 2 spoke strani, Faza 1)

"MeteoZima" je ime podportala. Glava (logo + ime) se na vseh treh straneh
klientsko zamenja z zimsko izdajo — BRAND_SWAP spodaj, isti vzorec kot
BRAND_SWAP v generate_gobe_page.py (MeteoGobar) — logo je zima/logo-zima.svg,
ista ilustrativna družina kot logo.svg/logo-gobar.svg (64×64, gradienti), ne
ploski ikonski slog spodnjega menija. seo.IC_METEOZIMA (ta slednji slog) je
ločena, še neuporabljena priprava za app_bottomnav() — vstop v glavno
navigacijo CLAUDE.md veže na prvi sneg/november, ne na datum gradnje, zato je
(za razliko od glave) namenoma še ni tu.

Bere data/winter-data.json (tools/winter_engine.py) in iz njega sestavi tri
statične strani po istem vzorcu kot ostale spoke strani
(tools/generate_frost_page.py, tools/generate_agrometeo_page.py) — ne kliče
nobenega API-ja sama, izračun je ločen (winter_engine.py), da se strani
lahko prerenderirajo brez ponovnega klica Open-Meteo:

  /zima/                    — hub: povzetek obeh indeksov za danes/jutri
  /zima/meja-snezenja/      — meja sneženja po višinskih pasovih
  /zima/poledica/           — tveganje poledice po krajih v dolini

Preostalih 15 spoke strani iz specifikacije (kurilni semafor, prevoznost
prelazov, snežna odeja …) NAMENOMA ni tu — Faza 1 gradi samo jedro + dve
najmočnejši strani po specifikaciji, širitev je ločeno delo.

Usage:
  python3 tools/generate_zima_page.py
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY

DATA_PATH = os.path.join(ROOT, "data", "winter-data.json")

# Zamenja glavo (logo + ime) na vseh treh straneh z MeteoZima izdajo, klientsko
# -- isti vzorec kot BRAND_SWAP v generate_gobe_page.py (MeteoGobar). Namenoma
# tako, ne s spreminjanjem skupnega HEADER-ja v generate_seo_pages.py -- vsaka
# druga generirana stran obdrži navadno glavo Meteorec nespremenjeno.
BRAND_SWAP = '''<script>(function(){
  var img=document.querySelector(".site-head .brand-logo");
  var nm=document.querySelector(".site-head .brand-name");
  if(img){img.src="/zima/logo-zima.svg";img.alt="MeteoZima";}
  if(nm){nm.innerHTML="Meteo<em>Zima</em>";}
})();</script>'''

RISK_LABEL = {"nizko": "Nizko tveganje", "srednje": "Srednje tveganje", "visoko": "Visoko tveganje"}
RISK_ICON = {"nizko": "🟢", "srednje": "🟡", "visoko": "🔴"}
RISK_CLASS = {"nizko": "badge-risk-nizko", "srednje": "badge-risk-srednje", "visoko": "badge-risk-visoko"}
CONF_LABEL = {"visoka": "visoka zanesljivost", "srednja": "srednja zanesljivost", "nizka": "nizka zanesljivost"}


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def num(x, d=1):
    return seo.num(x, d)


def risk_badge(level):
    if level is None:
        return '<span class="badge-risk badge-risk-none">ni podatka</span>'
    return f'<span class="badge-risk {RISK_CLASS[level]}">{RISK_ICON[level]} {RISK_LABEL[level]}</span>'


def fmt_hour(iso):
    """'2026-11-16T05:00' -> 'jutri, 05:00' / 'danes, 05:00' glede na TODAY."""
    try:
        dt = datetime.datetime.strptime(iso[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return iso
    d = dt.date()
    if d == TODAY:
        day = "danes"
    elif d == TODAY + datetime.timedelta(days=1):
        day = "jutri"
    else:
        day = f"{d.day}. {d.month}."
    return f"{day}, {dt.strftime('%H:%M')}"


# ── /zima/ hub ────────────────────────────────────────────────────────────

def build_hub_body(data):
    snow = data["snow_line"]
    locations = data["locations"]
    worst_loc = max(locations, key=lambda l: ["nizko", "srednje", "visoko"].index(l["indices"]["black_ice"]["risk_level"]))
    worst_level = worst_loc["indices"]["black_ice"]["risk_level"]

    line_m = snow.get("current_line_m")
    if line_m is None:
        snow_verdict = "Meja sneženja trenutno ni na voljo."
    elif line_m > 1700:
        snow_verdict = f"Meja sneženja je danes pri {line_m} m — nad vsemi spremljanimi višinami v dolini, sneg ni pričakovan."
    else:
        below = [b for b in snow["expected_cm_by_elevation"] if b["cm"] > 0]
        if below:
            snow_verdict = (f"Meja sneženja je pri {line_m} m — nad {below[0]['elevation_m']} m n. m. "
                             f"je v naslednjih 24 h pričakovanih do {num(max(b['cm'] for b in below), 1)} cm snega.")
        else:
            snow_verdict = f"Meja sneženja je pri {line_m} m, a v naslednjih 24 h ni pričakovanih pomembnejših padavin."

    ice_verdict = (f"Danes ni povečanega tveganja poledice v dolini."
                   if worst_level == "nizko" else
                   f"Najbolj izpostavljen je trenutno kraj {worst_loc['name']} — {risk_badge(worst_level)}.")

    cards = f'''  <div class="card-grid">
    <a class="phenom-card" href="/zima/meja-snezenja/">Meja sneženja
      <div class="ph-count">{num(line_m, 0) if line_m is not None else "—"} m n. m.</div></a>
    <a class="phenom-card" href="/zima/poledica/">Tveganje poledice
      <div class="ph-count">{RISK_ICON.get(worst_level, "⚪")} {RISK_LABEL.get(worst_level, "ni podatka")}</div></a>
  </div>'''

    faq = [
        ("Katere kraje pokriva MeteoZima?", "Rečico ob Savinji (postaja IREICA1), Mozirje, Nazarje, Ljubno ob "
         "Savinji in Gornji Grad — ista naselja kot na straneh »Vreme po krajih v dolini«."),
        ("Ali je to uradno opozorilo?", "Ne. Oba indeksa sta ocena Meteoreca iz javnih napovednih virov "
         "(Open-Meteo), ne uradno opozorilo ARSO. Za uradna opozorila glej "
         "<a href=\"/nevihte/\">stran opozoril</a>."),
    ]

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Zimski nadzorni center — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">❄️ Meja sneženja</div>
    <p class="fh-sub">{snow_verdict}</p>
  </div>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🧊 Poledica</div>
    <p class="fh-sub">{ice_verdict}</p>
  </div>
{cards}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Podatki izhajajo iz javne napovedi Open-Meteo za postajo IREICA1 in okoliška
  naselja, brez notranjih meritev. MeteoZima je v prvi fazi — meja sneženja in poledica; nadaljnji
  zimski indeksi (kurilni semafor, prevoznost prelazov, snežna odeja …) sledijo pozneje.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>''', faq


# ── /zima/meja-snezenja/ ─────────────────────────────────────────────────

def build_snow_line_body(data):
    snow = data["snow_line"]
    line_m = snow.get("current_line_m")
    fc_m = snow.get("forecast_24h_m")
    conf = snow.get("confidence")

    if line_m is None:
        hero_sub = "Meja sneženja trenutno ni na voljo — poskusi znova pozneje."
    else:
        trend = ""
        if fc_m is not None and line_m is not None:
            diff = fc_m - line_m
            if abs(diff) >= 100:
                trend = f" V naslednjih 24 h se pričakuje premik na {fc_m} m ({'dvig' if diff > 0 else 'spust'})."
        # Zanesljivost prikažemo samo, kadar je meja dovolj nizko, da je sploh
        # relevantna za spremljane pasove (do 1600 m) — nad tem je "nizka
        # zanesljivost" pri 4000+ m samo zmedla bi bralca brez razloga.
        conf_txt = f" ({CONF_LABEL.get(conf, 'ocena')})" if conf and line_m <= 2000 else ""
        hero_sub = f'Trenutna meja sneženja je pri <strong>{line_m} m n. m.</strong>{conf_txt}.{trend}'

    rows = []
    for b in snow["expected_cm_by_elevation"]:
        rows.append(f'      <tr><th>{b["elevation_m"]} m n. m.</th><td>{num(b["cm"], 1)} cm v naslednjih 24 h</td></tr>')
    table = '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"

    faq = [
        ("Kaj pomeni »meja sneženja«?", "To je nadmorska višina, nad katero padavine padajo kot sneg — "
         "izpeljana iz ničte izoterme (Open-Meteo), znižane za približno 200–300 m, ker se padavina ob "
         "padanju skozi zrak dodatno ohlaja. Pod to mejo pada dež, tik ob njej pa mešano."),
        ("Zakaj ni številke za konkretno goro (Golte, Menina …)?", "Ker bi bila trdna povezava številka-vrh "
         "ugibana — vrhovi v okolici se med seboj razlikujejo za stotine metrov nadmorske višine. Namesto "
         "tega tabela pokaže pričakovan sneg po višinskih pasovih; za goro nad določeno višino preberi "
         "ustrezno vrstico."),
        ("Kako natančna je ocena?", "Uporablja splošno znan sinoptičen približek (~10:1 razmerje padavine/sneg, "
         "meja sneženja ~200–300 m pod ničto izotermo), ne uradne mikrofizike padavin. Za odločitve z visokim "
         "tveganjem (gorske ture, prevoznost) preveri tudi uradno napoved ARSO."),
    ]

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Meja sneženja", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Meja sneženja — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">❄️ Trenutna meja sneženja</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
  <h2>Pričakovan sneg po višinskih pasovih (naslednjih 24 h)</h2>
{table}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Ocena Meteoreca iz javne napovedi Open-Meteo, ne uradno opozorilo ARSO. Meja
  sneženja je regionalna vrednost in se znotraj dolinskega dna Zgornje Savinjske doline ne razlikuje
  pomembno med kraji — razlika je v nadmorski višini, ne v legi.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


# ── /zima/poledica/ ──────────────────────────────────────────────────────

def build_black_ice_body(data):
    locations = data["locations"]
    rows = []
    for loc in locations:
        bi = loc["indices"]["black_ice"]
        hours = ", ".join(fmt_hour(h) for h in bi["risk_hours"][:4]) if bi["risk_hours"] else "—"
        detail = (f'{risk_badge(bi["risk_level"])} — cestišče ~{num(bi["ground_temp_c"], 1)} °C, '
                   f'rosišče {num(bi["dew_point_c"], 1)} °C. Ure tveganja: {hours}.'
                   if bi["ground_temp_c"] is not None else risk_badge(bi["risk_level"]))
        rows.append(f'      <tr><th>{loc["name"]} ({loc["elevation_m"]} m)</th><td>{detail}</td></tr>')
    table = '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"

    micro_items = "\n".join(f'    <li><strong>{l["name"]}:</strong> {l["microclimate"]}</li>' for l in locations)

    faq = [
        ("Je to uradno opozorilo ARSO?", "Ne. To je Meteorecov lasten kriterij (ocenjena temperatura cestišča "
         "proti rosišču, iz javne napovedi Open-Meteo) — enako poimenovana previdnostna opomba kot pri "
         "MeteoGasilcu, ne uradna prometna informacija. Za uradna opozorila in stanje cest preveri ARSO in "
         "promet.si."),
        ("Zakaj se ocena razlikuje po krajih, čeprav so si blizu?", "Ker uporablja dokumentirane mikroklimatske "
         "razlike med kraji v dolini (glej spodaj) in nadmorsko višino — ne isto številko za vso dolino."),
        ("Zakaj so mostovi posebej omenjeni?", "Mostovi in nadvozi se ohlajajo z obeh strani (zgoraj in "
         "spodaj) in zato zmrznejo prej kot cestišče na tleh — splošno znano pravilo cestne meteorologije, ne "
         "izračunano posebej za vsak most."),
    ]

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Poledica", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Tveganje poledice — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <h2>Ocena po krajih (naslednjih 36 h)</h2>
{table}
  <h2>Mikroklima po krajih</h2>
  <ul>
{micro_items}
  </ul>
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Ocena upošteva samo sevalno ohlajanje cestišča (oblačnost, veter, temperatura,
  rosišče) — ne posipa, prometne obremenitve ali dejanskega stanja vozišča. Vedno preveri tudi uradna
  opozorila ARSO na <a href="/nevihte/">strani opozoril</a>.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


def main():
    data = load_json(DATA_PATH)
    if not data:
        print("✗ data/winter-data.json manjka -- najprej poženi tools/winter_engine.py.", file=sys.stderr)
        return 1

    # ── hub ──
    body, faq = build_hub_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/", "MeteoZima — Zgornja Savinjska dolina",
                            "MeteoZima — zimski nadzorni center: meja sneženja in tveganje poledice za "
                            "Zgornjo Savinjsko dolino, iz meritev IREICA1 in javne napovedi.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("MeteoZima — Zgornja Savinjska dolina",
                           "MeteoZima: meja sneženja in tveganje poledice za Zgornjo Savinjsko dolino, "
                           "posodobljeno dnevno.",
                           "/zima/", schema, body)
    seo.write_page("zima/index.html", html, force=True)
    print("  → zima/index.html")

    # ── meja-snezenja ──
    body, faq = build_snow_line_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/meja-snezenja/", "Meja sneženja — Zgornja Savinjska dolina",
                            "Trenutna in 24-urna napoved meje sneženja po višinskih pasovih za Zgornjo "
                            "Savinjsko dolino.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Meja sneženja", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Meja sneženja — Zgornja Savinjska dolina",
                           "Trenutna meja sneženja in pričakovan sneg po višinskih pasovih, posodobljeno dnevno.",
                           "/zima/meja-snezenja/", schema, body)
    seo.write_page("zima/meja-snezenja/index.html", html, force=True)
    print("  → zima/meja-snezenja/index.html")

    # ── poledica ──
    body, faq = build_black_ice_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/poledica/", "Tveganje poledice — Zgornja Savinjska dolina",
                            "Ocena tveganja poledice po krajih Zgornje Savinjske doline, iz meritev "
                            "IREICA1 in javne napovedi.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Poledica", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Tveganje poledice — Zgornja Savinjska dolina",
                           "Ocena tveganja poledice po krajih Zgornje Savinjske doline, posodobljeno dnevno.",
                           "/zima/poledica/", schema, body)
    seo.write_page("zima/poledica/index.html", html, force=True)
    print("  → zima/poledica/index.html")

    return 0


if __name__ == "__main__":
    sys.exit(main())
