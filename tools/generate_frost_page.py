#!/usr/bin/env python3
"""
tools/generate_frost_page.py — /opozorilo-pred-pozebo/ pillar page

Bere data/frost-risk.json (tools/calculate_frost_risk.py) in
data/frost-risk-history.json (verificiran dnevnik napoved/dejansko) ter iz
njiju sestavi statično stran po istem vzorcu kot ostale spoke strani
(tools/generate_agrometeo_page.py, tools/generate_nevihte_page.py) — ne kliče
nobenega API-ja sama, izračun je ločen (calculate_frost_risk.py), da se stran
lahko prerenderira brez ponovnega klica ARSO/Open-Meteo/postaje.

Zunaj sezone (ni marec-maj) frost-risk.json nima kategorij po vrstah (glej
calculate_frost_risk.py: in_season=False -> species=[]) -- stran to pove
izrecno namesto da bi tiho prikazala "nizko tveganje", kar bi bilo zavajajoče.

Usage:
  python3 tools/generate_frost_page.py
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY

RISK_PATH = os.path.join(ROOT, "data", "frost-risk.json")
LOG_PATH = os.path.join(ROOT, "data", "frost-risk-history.json")

CAT_LABEL = {"NIZKO": "Nizko tveganje", "SREDNJE": "Srednje tveganje", "VISOKO": "Visoko tveganje"}
CAT_CLASS = {"NIZKO": "frost-nizko", "SREDNJE": "frost-srednje", "VISOKO": "frost-visoko"}
CAT_ICON = {"NIZKO": "🟢", "SREDNJE": "🟡", "VISOKO": "🔴"}


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def num(x, d=1):
    return seo.num(x, d)


def signed_num(x, d=1):
    return f"{x:+.{d}f}".replace(".", ",")


def fmtd_short(iso):
    """'2026-04-05' -> '5. 4.' -- ista konvencija kot ostale spoke strani (npr.
    frost_rows v tools/generate_agrometeo_page.py), brez vodilnih ničel."""
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f"{d}. {m}."


BADGE_CLASS = {"NIZKO": "badge-risk-nizko", "SREDNJE": "badge-risk-srednje", "VISOKO": "badge-risk-visoko"}


def cat_badge_html(cat):
    if cat is None:
        return '<span class="badge-risk badge-risk-none">ni podatka</span>'
    return f'<span class="badge-risk {BADGE_CLASS[cat]}">{CAT_ICON[cat]} {CAT_LABEL[cat]}</span>'


# ── Hero ──────────────────────────────────────────────────────────────────

def build_hero(risk):
    in_season = risk.get("in_season")
    night0 = risk["nights"][0]
    pred = night0.get("predicted_min_c")
    worst = night0.get("worst")

    if not in_season:
        cls, cat_text = "frost-izven", "Ni sezona pozebe"
        sub = ("Model teče v sezoni pozebe za sadno drevje (1. marec – 31. maj). Trenutno prikazani "
               f"podatki so zgolj informativni — nocojšnji pričakovani minimum je {num(pred)} °C "
               f"({night0.get('source') or 'vir ni na voljo'}).")
    elif worst is None or pred is None:
        cls, cat_text = "frost-izven", "Ni podatka"
        sub = "Postaja ali napovedni vir trenutno ni dosegljiv — prikazani so zadnji znani podatki."
    else:
        cat = worst["category"]
        cls, cat_text = CAT_CLASS[cat], CAT_LABEL[cat]
        sub = (f'Pričakovan minimum nocoj: <strong>{num(pred)} °C</strong> ({night0.get("source")}). '
               f'Najbolj ogrožena je trenutno <strong>{worst["name"].lower()}</strong> '
               f'(faza {worst["phenophase_name"]}, prag {num(worst["t10"])} / {num(worst["t90"])} °C '
               f'pri 10 % / 90 % poškodb).')

    comp = night0.get("radiative")
    comp_html = ""
    if comp:
        comp_html = (
            '  <details class="frost-model-detail">\n'
            '    <summary>Kako je izračunano</summary>\n'
            f'    <p class="muted-note">Temperatura ob sončnem zahodu {num(comp["temp_sunset_c"])} °C, zdaj '
            f'{num(comp["temp_now_c"])} °C — ohlajanje {num(comp["cooling_rate_c_per_h"], 2)} °C/h, '
            f'ekstrapolirano še {num(comp["hours_to_dawn"], 1)} h do zore (z dušenjem, ker se sevalno '
            f'ohlajanje čez noč upočasnjuje). Popravki za preostanek noči: oblačnost '
            f'{num(comp["avg_cloud_pct"], 0) if comp.get("avg_cloud_pct") is not None else "—"} % '
            f'({signed_num(comp["cloud_corr_c"])} °C), veter '
            f'{num(comp["avg_wind_kmh"], 1) if comp.get("avg_wind_kmh") is not None else "—"} km/h '
            f'({signed_num(comp["wind_corr_c"])} °C), vlaga '
            f'{num(comp["avg_rh_pct"], 0) if comp.get("avg_rh_pct") is not None else "—"} % '
            f'({signed_num(comp["rh_corr_c"])} °C).</p>\n'
            '  </details>'
        )

    return f'''  <div class="card frost-hero {cls}" style="margin-bottom:1.2rem">
    <div class="clabel">{CAT_ICON.get(worst["category"], "⚪") if (in_season and worst) else "⚪"} Trenutno tveganje pozebe</div>
    <div class="fh-cat">{cat_text}</div>
    <p class="fh-sub">{sub}</p>
{comp_html}
  </div>''', (worst["category"] if (in_season and worst) else None)


# ── 3-dnevni pregled ──────────────────────────────────────────────────────

def build_outlook(risk):
    rows = []
    for n in risk["nights"]:
        pred = n.get("predicted_min_c")
        worst = n.get("worst")
        cat = worst["category"] if worst else None
        rows.append(
            f'      <tr><th>{n["label"].capitalize()} ({fmtd_short(n["date"])})</th>'
            f'<td>{num(pred) if pred is not None else "—"} °C · {n.get("source") or "—"} — '
            f'{cat_badge_html(cat)}</td></tr>'
        )
    return '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"


# ── Fenofaza po vrstah ────────────────────────────────────────────────────

def build_phenophase_table(risk):
    species = risk["nights"][0].get("species") or []
    if not species:
        return ('  <p class="muted-note">Fenofaze se spremljajo v sezoni pozebe (1. marec – 31. maj). '
                'Zunaj sezone je sadno drevje v mirovanju in mrazoodporno do zelo nizkih temperatur.</p>')
    rows = []
    for sp in species:
        src = "ročni vnos" if sp["phenophase_source"] == "ročno" else "koledarski privzetek"
        rows.append(
            f'      <tr><th>{sp["name"]}</th><td>{sp["phenophase_name"]} ({src}) — prag poškodb '
            f'{num(sp["t10"])} / {num(sp["t90"])} °C (10 % / 90 %) — {cat_badge_html(sp["category"])}</td></tr>'
        )
    return '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"


# ── Priporočeni ukrepi ────────────────────────────────────────────────────

ACTIONS = {
    "NIZKO": ["Posebni ukrepi niso potrebni.", "Spremljaj napoved za naslednje noči — tveganje se lahko spremeni."],
    "SREDNJE": [
        "Pokrij občutljive nasade (agrotekstil, folija) pred večerom, če je mogoče.",
        "Pripravi opremo za ogrevanje (sveče, mala kurišča) ali oroševanje za primer, da se napoved poslabša.",
        "Izogibaj se obrezovanju tik pred pričakovano pozebo — rane povečajo občutljivost.",
    ],
    "VISOKO": [
        "Oroševanje (aspersion): stalno škropljenje vode med nočjo ščiti popke/cvetove z izsevano toploto ledenja (0 °C) — deluje le, če traja neprekinjeno do jutra in je dovolj vode.",
        "Ogrevanje: sveče ali mala kurišča med vrstami dvignejo temperaturo v spodnjem sloju zraka za 1-2 °C.",
        "Mešanje zraka: ventilatorji ali helikopter razbijejo temperaturni obrat (topel zrak nad hladnim dnom doline).",
        "Mulčenje tal poveča toplotno kapaciteto tal in zmanjša sevalno ohlajanje ponoči.",
        "Če nimaš aktivne zaščite, obiranje/zaščita ni več izvedljiva čez noč — spremljaj škodo zjutraj in prilagodi negovalne ukrepe.",
    ],
}


def build_actions(cat):
    if cat is None:
        cat = "NIZKO"
    items = "\n".join(f"    <li>{a}</li>" for a in ACTIONS[cat])
    return f'  <ul class="frost-actions">\n{items}\n  </ul>'


# ── Zgodovina: graf + tabela ──────────────────────────────────────────────

def history_chart_svg(entries):
    """Dvojna črta (napoved / dejansko) čez sezono, isti server-rendered SVG
    vzorec kot hero_sparkline_svg v tools/generate_gobe_page.py -- brez JS,
    ker gre stran skozi statični pre-render."""
    verified = [e for e in entries if e.get("actual_min_c") is not None]
    if not verified:
        return None
    verified.sort(key=lambda e: e["date"])
    w, h, pad_l, pad_r, pad_t, pad_b = 640, 200, 36, 12, 14, 24
    vals = [e["predicted_min_c"] for e in verified] + [e["actual_min_c"] for e in verified] + [0]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    lo -= 0.5; hi += 0.5
    n = len(verified)
    x_of = lambda i: pad_l + (w - pad_l - pad_r) * (0 if n == 1 else i / (n - 1))
    y_of = lambda v: pad_t + (h - pad_t - pad_b) * (1 - (v - lo) / (hi - lo))

    pred_pts = " ".join(f"{x_of(i):.1f},{y_of(e['predicted_min_c']):.1f}" for i, e in enumerate(verified))
    act_pts = " ".join(f"{x_of(i):.1f},{y_of(e['actual_min_c']):.1f}" for i, e in enumerate(verified))
    y0 = y_of(0)

    dots = []
    for i, e in enumerate(verified):
        color = {"NIZKO": "#38bdf8", "SREDNJE": "#fbbf24", "VISOKO": "#f87171"}.get(e.get("actual_category"), "#94a3b8")
        dots.append(f'<circle cx="{x_of(i):.1f}" cy="{y_of(e["actual_min_c"]):.1f}" r="3.2" fill="{color}"/>')

    first_lbl = fmtd_short(verified[0]["date"])
    last_lbl = fmtd_short(verified[-1]["date"])

    return (
        f'<svg viewBox="0 0 {w} {h}" class="frost-chart" role="img" '
        f'aria-label="Napovedan proti dejanskemu minimumu skozi sezono pozebe">'
        f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{w-pad_r}" y2="{y0:.1f}" stroke="#475569" stroke-width="1" stroke-dasharray="3,3"/>'
        f'<text x="{pad_l-6}" y="{y0+3:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">0°</text>'
        f'<polyline points="{pred_pts}" fill="none" stroke="#94a3b8" stroke-width="1.6" stroke-dasharray="4,3" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<polyline points="{act_pts}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        + "".join(dots) +
        f'<text x="{pad_l}" y="{h-4}" font-size="9" fill="#94a3b8">{first_lbl}</text>'
        f'<text x="{w-pad_r}" y="{h-4}" text-anchor="end" font-size="9" fill="#94a3b8">{last_lbl}</text>'
        f'</svg>'
    )


def build_history(entries):
    year_prefix = f"{TODAY.year}-"
    season_entries = [e for e in entries if e["date"].startswith(year_prefix) and e["date"][5:7] in ("03", "04", "05")]
    if not season_entries:
        return ('  <p class="muted-note">V letošnji sezoni pozebe (1. marec – 31. maj) še ni bilo napovedi za '
                'primerjavo — graf se napolni sproti, ko model beleži noči v sezoni.</p>')
    season_entries.sort(key=lambda e: e["date"])
    chart = history_chart_svg(season_entries)
    chart_html = (f'  <div class="frost-chart-wrap">{chart}'
                   '<p class="muted-note" style="margin-top:.3rem">Sivo črtkano: napoved modela · Modro (barvano po dejanski kategoriji): dejansko izmerjen minimum IREICA1.</p></div>\n'
                  ) if chart else ""
    rows = []
    for e in reversed(season_entries[-14:]):
        d = fmtd_short(e["date"])
        actual = f'{num(e["actual_min_c"])} °C ({CAT_LABEL.get(e["actual_category"], "—")})' if e.get("actual_min_c") is not None else "čaka na jutranjo meritev"
        rows.append(
            f'      <tr><th>{d}</th><td>napoved {num(e["predicted_min_c"])} °C ({CAT_LABEL.get(e["predicted_category"], "—")}, '
            f'{e["worst_species_name"]}) — dejansko {actual}</td></tr>'
        )
    table = '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"
    return chart_html + table


# ── FAQ ───────────────────────────────────────────────────────────────────

FAQ = [
    ("Kdaj je pozeba najbolj nevarna?",
     "Radiacijska (tla-sevalna) pozeba je najpogostejša ob jasnih, mirnih nočeh brez oblačnosti in vetra — takrat "
     "tla in zrak najhitreje izgubljajo toploto proti jasnemu nebu, minimum pa je običajno tik pred sončnim vzhodom. "
     "Adventivna pozeba nastane ob vdoru hladne zračne mase (fronta) in je redkejša, a lahko prizadene širše območje "
     "ne glede na oblačnost."),
    ("Kako zaščitim sadovnjak pred pozebo?",
     "Najučinkovitejši ukrepi so neprekinjeno oroševanje (voda ob zmrzovanju sprošča toploto), ogrevanje (sveče, mala "
     "kurišča) in mešanje zraka (ventilatorji), ki razbijejo temperaturni obrat. Mulčenje tal in izogibanje obrezovanju "
     "tik pred pozebo dodatno zmanjšata tveganje. Glej razdelek »Priporočeni ukrepi« zgoraj za podrobnosti po stopnji tveganja."),
    ("Zakaj je nocojšnja napoved drugačna od jutrišnje?",
     "Nocojšnji minimum ocenjuje lokalni model iz dejanske hitrosti ohlajanja postaje IREICA1 po sončnem zahodu — to "
     "je mikroklimatski (radiacijski) pojav, ki ga sinoptična napoved ne vidi. Naslednji dve noči še nimata te "
     "lokalne meritve, zato uporabljata ARSO napoved neposredno."),
    ("Kaj pomenita »10 % poškodb« in »90 % poškodb«?",
     "To sta standardna praga iz raziskav sadjarstva (WSU/Utah State): pri temperaturi za 10 % poškodb pričakujemo "
     "poškodbe na približno desetini popkov/cvetov dane fenofaze, pri 90 % pa na večini. Vmesne temperature pomenijo "
     "delne, a resne izgube."),
]


def build_faq():
    items = "\n".join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in FAQ)
    return f'  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n{items}\n  </div>'


def main():
    risk = load_json(RISK_PATH)
    if not risk:
        print("✗ data/frost-risk.json manjka -- najprej poženi tools/calculate_frost_risk.py.", file=sys.stderr)
        return 1
    log_entries = load_json(LOG_PATH, default=[])

    hero_html, hero_cat = build_hero(risk)
    outlook = build_outlook(risk)
    phen_table = build_phenophase_table(risk)
    actions = build_actions(hero_cat)
    history = build_history(log_entries)
    faq_html = build_faq()

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Opozorilo pred pozebo", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Opozorilo pred pozebo — Savinjska dolina</h1>
  <p class="post-meta">Tveganje pozebe za sadno drevje iz meritev IREICA1 + napovedi ARSO · posodobljeno {risk.get("generated_at_local", "—")}</p>
{hero_html}
  <h2>Naslednje tri noči</h2>
{outlook}
  <h2>Trenutna fenofaza po vrstah</h2>
  <p class="archive-intro">Prag poškodb je odvisen od razvojne faze — isto drevo je sredi cvetenja veliko bolj
  občutljivo kot v mirovanju. Fenofaza se v sezoni (marec–maj) lahko ročno popravi v
  <code>data/phenophase-current.json</code>, sicer velja grob koledarski privzetek.</p>
{phen_table}
  <h2>Priporočeni ukrepi</h2>
{actions}
  <h2>Zgodovina — napoved proti dejanskemu</h2>
{history}
{faq_html}
  <p class="muted-note">Model uporablja izključno meritve postaje IREICA1 in javne napovedne vire (ARSO, Open-Meteo) —
  brez notranjih meritev. Radiacijski model je poskusen; za odločitve z visokim tveganjem (zaščita nasada) preveri
  tudi uradno opozorilo ARSO na <a href="/nevihte/">strani opozoril</a>.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    url = "/opozorilo-pred-pozebo/"
    title = "Opozorilo pred pozebo — Savinjska dolina"
    if hero_cat:
        desc = (f'{CAT_LABEL[hero_cat]} pozebe nocoj za sadno drevje v Savinjski dolini — pričakovan minimum, '
                f'fenofaza po vrstah in priporočeni ukrepi, iz meritev postaje IREICA1.')
    else:
        desc = ("Tveganje pozebe za sadno drevje v Savinjski dolini po fenofazi — pričakovan nočni minimum, "
                "3-dnevni pregled in priporočeni ukrepi, iz meritev postaje IREICA1 in napovedi ARSO.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-08-27"),
        seo.crumbs_schema([("Meteorec", "/"), ("Opozorilo pred pozebo", None)]),
        seo.faq_schema(FAQ),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("opozorilo-pred-pozebo/index.html", html, force=True)
    print(f"  → opozorilo-pred-pozebo/index.html ({hero_cat or ('izven sezone' if not risk.get('in_season') else 'ni podatka')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
