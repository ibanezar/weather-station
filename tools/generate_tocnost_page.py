#!/usr/bin/env python3
"""
tools/generate_tocnost_page.py — /tocnost-napovedi/ forecast-accuracy scoreboard

Generates /tocnost-napovedi/index.html from forecast_verification.json (built
daily by tools/verify_forecasts.py): a running, transparent scoreboard of how
close the ARSO and Open-Meteo day-ahead forecasts for Rečica ob Savinji came
to what the station actually measured. Nobody publishes this systematically
for a Slovenian valley — it's a genuine, unique content type built entirely
from data this station already has.

Četrti tekmovalec je ECMWF AIFS — AI model, ki ga Windy prikazuje kot 15-dnevni
podaljšek modela ECMWF. Tu je zato, da se pove, kar se sicer ne meri nikjer:
koliko AI model pri 0,25° ločljivosti zaleže na dnu ozke doline.

Za ARSO in Open-Meteo semafor nima zgodovine za nazaj (ARSO arhiva napovedi ne
objavlja, Open-Meteo smo začeli beležiti sproti) — raste dan za dnem. AIFS je
izjema, ker Open-Meteo hrani arhiv preteklih napovedi; napolnil ga je
tools/backfill_aifs_verification.py. Stran to pove namesto da bi delala vtis,
da so vsi viri merjeni enako dolgo.

Usage:
  python3 tools/generate_tocnost_page.py
"""
import json, os, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
VERIFICATION_PATH = os.path.join(ROOT, "forecast_verification.json")
MODEL_PATH = os.path.join(ROOT, "model", "recica-mos.json")


def load_verification():
    try:
        with open(VERIFICATION_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_model():
    try:
        with open(MODEL_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def source_stats(records, source):
    tmax_errs = [r[source]["err_tmax"] for r in records if r.get(source) and r[source].get("err_tmax") is not None]
    tmin_errs = [r[source]["err_tmin"] for r in records if r.get(source) and r[source].get("err_tmin") is not None]
    n = sum(1 for r in records if r.get(source))
    return {
        "n": n,
        "mae_tmax": st.mean(tmax_errs) if tmax_errs else None,
        "mae_tmin": st.mean(tmin_errs) if tmin_errs else None,
    }


def pred_txt(src):
    """»28,4 °C (±1,1)« za posamezno napoved v tabeli zadnjih dni."""
    if not src or src.get("tmax") is None:
        return "—"
    return f'{seo.num(src.get("tmax"))} °C (±{seo.num(src.get("err_tmax"))})'


def mae_txt(stats):
    """»±1,2 °C« ali pomišljaj, kadar vir tisti mesec ni napovedoval."""
    if stats["mae_tmax"] is None:
        return "—"
    return f'±{seo.num(stats["mae_tmax"])} °C'


def build_body(verification):
    dates = sorted(verification.keys())
    records = [verification[d] for d in dates]
    n_days = len(records)
    first_date = dates[0] if dates else None

    arso_stats = source_stats(records, "arso")
    om_stats = source_stats(records, "open_meteo")
    mos_stats = source_stats(records, "meteorec")
    aifs_stats = source_stats(records, "aifs")
    has_mos = mos_stats["n"] > 0
    has_aifs = aifs_stats["n"] > 0

    # MTR — ime lastnega modela. Različica se izpelje iz zadnjega zapisa, ki jo
    # nosi (meteorec.model_version), da se oznaka sama dvigne, ko se model kdaj
    # znova nauči pod novo verzijo — nikjer je ne zapisujemo trdo.
    mtr_ver = next((r["meteorec"].get("model_version") for r in reversed(records)
                    if r.get("meteorec") and r["meteorec"].get("model_version")), None)
    mtr_label = f"MTR v{mtr_ver.split('.')[0]}" if mtr_ver else "MTR"

    # ARSO nima napovedne točke za Rečico, zato njegova napoved prihaja iz
    # najbližjega kraja na njihovem seznamu. Kateri je to, povemo naravnost —
    # sicer bi številka izpadla kot napoved za Rečico, kar ni.
    arso_loc = next((r["arso"].get("loc") for r in reversed(records)
                     if r.get("arso") and r["arso"].get("loc")), None)
    arso_note = ""
    if arso_loc and arso_loc != "Rečica ob Savinji":
        arso_note = (f' ARSO za Rečico ob Savinji ne objavlja krajevne napovedi, zato jemljemo '
                     f'najbližji kraj z njihovega seznama — {arso_loc}. Open-Meteo je vezan '
                     f'neposredno na koordinate postaje.')

    if n_days == 0:
        status = ('  <div class="warn-banner lvl-none">Zbiranje podatkov se je začelo danes, '
                   f'{TODAY.isoformat()}. Napovedi ARSO in Open-Meteo za jutri se dnevno beležijo, '
                   'primerjava z dejansko meritvijo pa se izpiše, ko dan mine — prvi rezultati bodo '
                   'na voljo v naslednjih dneh.</div>')
    else:
        parts = []
        if om_stats["mae_tmax"] is not None:
            parts.append(f'Open-Meteo: povprečna napaka najvišje temperature ±{seo.num(om_stats["mae_tmax"])} °C')
        if arso_stats["mae_tmax"] is not None:
            parts.append(f'ARSO: ±{seo.num(arso_stats["mae_tmax"])} °C')
        if aifs_stats["mae_tmax"] is not None:
            parts.append(f'ECMWF AIFS: ±{seo.num(aifs_stats["mae_tmax"])} °C')
        if mos_stats["mae_tmax"] is not None:
            parts.append(f'{mtr_label}: ±{seo.num(mos_stats["mae_tmax"])} °C')
        status =(f'  <p class="archive-intro"><strong>{n_days} razrešenih dni</strong> od {seo.fmtd(first_date)}. '
                   f'{"; ".join(parts)}.</p>')

    mos_intro = (f'  <p class="archive-intro"><strong>Tretji tekmovalec je {mtr_label} (Meteorec)</strong> — '
                 'naš lastni model za to dolino. Ne napoveduje vremena iz nič — vzame Open-Meteo kot vhod in '
                 'ga popravi s tem, česar globalni model za dno te doline ne zna: postaja je podnevi toplejša, '
                 'ponoči pa hladnejša od modelske mreže, ob jasnih in mirnih nočeh se na dnu doline nabere '
                 'hladen zrak. Popravek je naučen na meritvah te postaje. Meri se z istim merilom kot ARSO in '
                 'Open-Meteo, na isti tabeli — tudi kadar izgubi.</p>') if has_mos else ""

    # AIFS: koliko dni je napolnjenih iz arhiva in ne zabeleženih sproti. To ni
    # kozmetika — arhivski zapis je nastal po drugi poti (urne vrednosti,
    # sešteto v dnevne) in bralec mora vedeti, kje meja teče.
    aifs_archive_n = sum(1 for r in records if (r.get("aifs") or {}).get("src") == "archive")
    aifs_note = (f' Prvih {aifs_archive_n} dni je napolnjenih iz arhiva preteklih napovedi '
                 'Open-Meteo (AIFS je edini vir tu, ki tak arhiv sploh ima), naprej se beleži '
                 'sproti kot vsi ostali.') if aifs_archive_n else ""
    aifs_model_id = next((r["aifs"].get("model") for r in reversed(records)
                          if r.get("aifs") and r["aifs"].get("model")), "ecmwf_aifs025_single")
    aifs_method = (f' ECMWF AIFS jemljemo prek Open-Meteo (model {aifs_model_id}); dnevi, napolnjeni iz '
                   'arhiva preteklih napovedi, so sešteti iz urnih vrednosti, sproti zabeleženi pa iz '
                   'dnevne agregacije Open-Meteo — razlika je nekaj desetink stopinje.') if has_aifs else ""
    aifs_intro = ('  <p class="archive-intro"><strong>Četrti tekmovalec je ECMWF AIFS</strong> — AI model '
                  'Evropskega centra za srednjeročne napovedi, ki od februarja 2025 teče operativno in ga '
                  'Windy prikazuje kot 15-dnevni podaljšek modela ECMWF. Vremena ne računa iz enačb, ampak '
                  'ga je napovedovanja naučila nevronska mreža na štiridesetih letih arhiva. Teče v '
                  'ločljivosti 0,25° (~28 km) in v šesturnih korakih, kar pomeni, da naše doline ne vidi — '
                  'na tej tabeli je zato predvsem odgovor na vprašanje, ali AI po sebi odtehta lokalno '
                  f'ločljivost.{aifs_note}</p>') if has_aifs else ""

    intro = ('  <p class="archive-intro">Vsak dan zabeležimo, kaj ARSO in Open-Meteo napovesta za jutrišnjo '
             'najvišjo/najnižjo temperaturo v Rečici ob Savinji, naslednji dan pa to primerjamo z dejansko '
             'meritvijo postaje IREICA1. Nobene napovedi ne popravimo ali izbrišemo za nazaj; '
             'popravi se lahko le meritev, s katero jo primerjamo, in sicer takrat, ko arhiv postaje '
             'naknadno dopolni nepopoln dan. To je surova, tekoča ocena napovedne uspešnosti za to '
             'konkretno dolino, ne za Slovenijo na splošno.</p>')

    # ── Scoreboard kartice ──────────────────────────────────────────────
    def stat_card(label, stats, cls):
        val = seo.num(stats["mae_tmax"]) if stats["mae_tmax"] is not None else "—"
        return (f'    <div class="stat-card {cls}"><div class="sc-label">{label}</div>'
                f'<div class="sc-val">±{val}</div><div class="sc-sub">°C povp. napaka maks. T · {stats["n"]} napovedi</div></div>')

    cards = ('  <div class="stat-grid">\n'
              + stat_card("ARSO", arso_stats, "c-temp") + "\n"
              + stat_card("Open-Meteo", om_stats, "c-rain") + "\n"
              + (stat_card("ECMWF AIFS", aifs_stats, "c-wind") + "\n" if has_aifs else "")
              + (stat_card(mtr_label, mos_stats, "c-up") + "\n" if has_mos else "")
              + '  </div>') if n_days else ""

    # ── Mesečni scoreboard ──────────────────────────────────────────────
    by_month = defaultdict(list)
    for d, r in zip(dates, records):
        by_month[d[:7]].append(r)
    month_rows = []
    for ym in sorted(by_month, reverse=True):
        recs = by_month[ym]
        a = source_stats(recs, "arso")
        o = source_stats(recs, "open_meteo")
        mm = source_stats(recs, "meteorec")
        ai = source_stats(recs, "aifs")
        y, m = int(ym[:4]), int(ym[5:7])
        a_txt = mae_txt(a)
        o_txt = mae_txt(o)
        ai_col = f'<td>{mae_txt(ai)}</td>' if has_aifs else ""
        m_col = f'<td>{mae_txt(mm)}</td>' if has_mos else ""
        month_rows.append(f'    <tr><th>{seo.MES_NOM[m].capitalize()} {y}</th><td>{a_txt}</td><td>{o_txt}</td>{ai_col}{m_col}<td>{len(recs)}</td></tr>')
    month_head = ('    <tr><th>Mesec</th><th>ARSO povp. napaka</th><th>Open-Meteo povp. napaka</th>'
                  + ('<th>ECMWF AIFS</th>' if has_aifs else '')
                  + (f'<th>{mtr_label}</th>' if has_mos else '') + '<th>Dni</th></tr>\n')
    month_table = ('  <table class="stats">\n'
                    + month_head
                    + "\n".join(month_rows) + '\n  </table>') if month_rows else \
        '  <p class="muted-note">Še ni dovolj podatkov za mesečni pregled.</p>'

    # ── Zadnji dnevi ─────────────────────────────────────────────────────
    recent = list(reversed(dates))[:20]
    recent_rows = []
    for d in recent:
        r = verification[d]
        act = r.get("actual", {})
        a = r.get("arso") or {}
        o = r.get("open_meteo") or {}
        mm = r.get("meteorec") or {}
        ai = r.get("aifs") or {}
        a_txt = pred_txt(a)
        o_txt = pred_txt(o)
        ai_col = f'<td>{pred_txt(ai)}</td>' if has_aifs else ""
        m_col = f'<td>{pred_txt(mm)}</td>' if has_mos else ""
        recent_rows.append(
            f'    <tr><th><a href="/vreme/{d[:4]}/{d[5:7]}/{d[8:10]}/">{seo.fmtd(d)}</a></th>'
            f'<td>{seo.num(act.get("tmax"))} °C</td><td>{a_txt}</td><td>{o_txt}</td>{ai_col}{m_col}</tr>'
        )
    recent_head = ('    <tr><th>Datum</th><th>Dejanska maks. T</th><th>ARSO je napovedal</th>'
                   '<th>Open-Meteo je napovedal</th>'
                   + ('<th>AIFS je napovedal</th>' if has_aifs else '')
                   + (f'<th>{mtr_label} je napovedal</th>' if has_mos else '') + '</tr>\n')
    recent_table = ('  <table class="stats">\n'
                     + recent_head
                     + "\n".join(recent_rows) + '\n  </table>') if recent_rows else \
        '  <p class="muted-note">Še ni razrešenih dni.</p>'

    intro_block = intro + ("\n" + mos_intro if mos_intro else "") + ("\n" + aifs_intro if aifs_intro else "")

    # ── MTR: veščina po vodilnem času (D+1..D+3), hindcast ob učenju ─────
    # Ločeno od scoreboarda zgoraj: kartice/mesečni pregled merijo samo D+1,
    # sproti, na dneh, ki so se dejansko zgodili po objavi. Ta razdelek bere
    # model/recica-mos.json (piše ga train_recica_mos.py) -- leave-one-year-out
    # ocena vseh treh vodilnih časov, izračunana ob zadnjem učenju.
    skill_section = ""
    if has_mos:
        model = load_model()
        leads = model.get("leads") or {}
        if leads:
            def pct_txt(v):
                return f'{seo.num(v)} %' if v is not None else "—"

            lead_nums = sorted(leads, key=int)
            lead_rows = []
            year_blocks = []
            for ln in lead_nums:
                entry = leads[ln] or {}
                tmax_sk = (entry.get("skill") or {}).get("tmax") or {}
                tmin_sk = (entry.get("skill") or {}).get("tmin") or {}
                lead_rows.append(
                    f'    <tr><th>D+{ln}</th>'
                    f'<td>±{seo.num(tmax_sk.get("mae_open_meteo"))} °C</td>'
                    f'<td>±{seo.num(tmax_sk.get("mae_meteorec"))} °C</td>'
                    f'<td>{pct_txt(tmax_sk.get("improvement_pct"))}</td>'
                    f'<td>±{seo.num(tmin_sk.get("mae_open_meteo"))} °C</td>'
                    f'<td>±{seo.num(tmin_sk.get("mae_meteorec"))} °C</td>'
                    f'<td>{pct_txt(tmin_sk.get("improvement_pct"))}</td>'
                    f'<td>{tmax_sk.get("n", "—")}</td></tr>'
                )

                tmax_py = tmax_sk.get("per_year") or {}
                tmin_py = tmin_sk.get("per_year") or {}
                years = sorted(set(tmax_py) | set(tmin_py))
                if years:
                    py_rows = []
                    for y in years:
                        ty, ny = tmax_py.get(y) or {}, tmin_py.get(y) or {}
                        py_rows.append(
                            f'      <tr><th>{y}</th>'
                            f'<td>±{seo.num(ty.get("open_meteo"))} °C</td>'
                            f'<td>±{seo.num(ty.get("meteorec"))} °C</td>'
                            f'<td>±{seo.num(ny.get("open_meteo"))} °C</td>'
                            f'<td>±{seo.num(ny.get("meteorec"))} °C</td>'
                            f'<td>{ty.get("n", "—")}</td></tr>'
                        )
                    year_blocks.append(
                        f'    <details><summary>D+{ln} po letih</summary>\n'
                        '      <table class="stats">\n'
                        f'      <tr><th>Leto</th><th colspan="2">Tmax (Open-Meteo / {mtr_label})</th>'
                        f'<th colspan="2">Tmin (Open-Meteo / {mtr_label})</th><th>Vzorcev</th></tr>\n'
                        + "\n".join(py_rows) + '\n      </table>\n    </details>'
                    )

            trained_iso = (model.get("trained_at") or "")[:10]
            trained_txt = seo.fmtd(trained_iso) if len(trained_iso) == 10 else "—"
            lead_table = (
                '  <table class="stats">\n'
                '    <tr><th>Vodilni čas</th><th colspan="3">Maks. temp. (Tmax)</th>'
                '<th colspan="3">Min. temp. (Tmin)</th><th>Vzorcev</th></tr>\n'
                f'    <tr><th></th><th>Open-Meteo</th><th>{mtr_label}</th><th>Izboljšava</th>'
                f'<th>Open-Meteo</th><th>{mtr_label}</th><th>Izboljšava</th><th></th></tr>\n'
                + "\n".join(lead_rows) + '\n  </table>'
            )
            skill_section = (
                f'  <h2>{mtr_label}: veščina glede na vodilni čas</h2>\n'
                '  <p class="archive-intro">To ni ista številka kot zgoraj — kartice in mesečni pregled merijo '
                'samo napoved za jutri (D+1), sproti, na dneh, ki so se dejansko zgodili po objavi. Spodnja '
                f'tabela je hindcast ob zadnjem učenju modela ({trained_txt}): izpuščanje celega leta iz učne '
                'množice in ocena na izpuščenem, za vse tri vodilne čase (D+1 do D+3) in ločeno po letih.</p>\n'
                + lead_table
                + ('\n  <div class="faq">\n' + "\n".join(year_blocks) + '\n  </div>' if year_blocks else '')
            )

    # ── FAQ ─────────────────────────────────────────────────────────────
    qa = [
        ("Kako točna je vremenska napoved za Zgornjo Savinjsko dolino?",
         "Ta stran dnevno meri, za koliko stopinj se napovedi ARSO in Open-Meteo za naslednji dan povprečno "
         "zmotijo glede na dejansko meritev postaje IREICA1 v Rečici ob Savinji. Trenutna povprečna napaka "
         "je prikazana zgoraj in se dnevno posodablja — nobene napovedi ne popravljamo za nazaj."),
        ("Je ARSO napoved zanesljiva?",
         "Odvisno od obdobja in spremenljivke — glej mesečni pregled spodaj. Ta stran meri samo dan vnaprej "
         "napovedano najvišjo/najnižjo temperaturo za eno konkretno lokacijo (Rečica ob Savinji), ne "
         "splošne zanesljivosti ARSO napovedi za Slovenijo."),
        ("Zakaj se primerjava začne šele nedavno?",
         "ARSO ne objavlja arhiva preteklih napovedi, zato primerjave zanj ni mogoče izračunati za nazaj — "
         "beležimo jo dan za dnem, odkar ta stran obstaja. Izjema je ECMWF AIFS: Open-Meteo za svoje modele "
         "hrani arhiv preteklih napovedi, zato je AIFS napolnjen tudi za dneve pred tem."),
        ("Kje je primerjava za naslednjih nekaj ur (ne dni)?",
         "Uro-natančno primerjavo lastnega statističnega modela (Holt-Winters), Open-Meteo in postaje za "
         "zadnjih 24 ur najdeš na naslovni strani v razdelku »AI napoved«."),
    ]
    # Vprašanje o lastnem modelu se pojavi šele, ko ima model kaj pokazati —
    # dokler ni razrešenih dni, bi bilo obljuba brez številk.
    if has_aifs:
        qa.insert(2, (
            "Kateri AI model uporablja Windy in ali je boljši?",
            "Windy ne razvija svojega modela — prikazuje ECMWF AIFS, AI model Evropskega centra za "
            "srednjeročne napovedi, kot 15-dnevni podaljšek modela ECMWF. Na tej tabeli teče pod istim "
            "merilom kot vsi ostali. Pri nas ga omejuje ločljivost: AIFS računa na mreži 0,25° (~28 km), "
            "kar je za ozko dolino pregrobo — dno doline vidi kot pobočje. Za sinoptično sliko nekaj dni "
            "vnaprej je to lahko odličen model, za najvišjo temperaturo v Rečici pa številke v tabeli "
            "povedo, kje dejansko je."))
    if has_mos:
        qa.insert(4 if has_aifs else 3, (
            f"Kaj je {mtr_label}?",
            "MTR (Meteorec) je lastni statistični model za Rečico ob Savinji. Vzame napoved Open-Meteo in ji "
            "doda popravek, naučen na meritvah postaje IREICA1 — kako se dno doline sistematično razlikuje od "
            "modelske mreže. Napoveduje najvišjo in najnižjo temperaturo ter verjetnost padavin za en do tri "
            "dni vnaprej. Količine padavin ne popravlja, ker se je pri preizkusu izkazalo, da tega ne zna "
            "bolje od Open-Meteo. Model je poskusen in se meri javno, na tej tabeli — tudi kadar izgubi."))

    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Točnost napovedi", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Točnost vremenske napovedi — Rečica ob Savinji</h1>
  <p class="post-meta">{" vs. ".join(["ARSO", "Open-Meteo"] + (["ECMWF AIFS"] if has_aifs else []) + ([mtr_label] if has_mos else []) + ["dejanska meritev"])} · {n_days} razrešenih dni · {TODAY.isoformat()}</p>
{intro_block}
{status}
{cards}
{skill_section}
  <h2>Mesečni pregled</h2>
{month_table}
  <h2>Zadnji dnevi</h2>
{recent_table}
{faq_html}
  <p class="muted-note">Metodologija: vsak dan zabeležimo napoved ARSO in Open-Meteo za jutrišnjo najvišjo/
  najnižjo temperaturo v Rečici ob Savinji; ko dan mine, ju primerjamo z dejansko dnevno meritvijo postaje
  IREICA1. Napaka je absolutna razlika v °C. Nobena pretekla napoved se ne popravlja ali briše; kadar
  arhiv postaje naknadno dopolni meritev za pretekli dan, napako preračunamo na dopolnjeno meritev.{arso_note}{aifs_method}</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body


def main():
    verification = load_verification()
    body = build_body(verification)

    url = "/tocnost-napovedi/"
    title = "Točnost vremenske napovedi — Rečica ob Savinji"
    n = len(verification)
    desc = (f"Koliko točna je vremenska napoved za Zgornjo Savinjsko dolino? Dnevni scoreboard ARSO, "
            f"Open-Meteo in AI modela ECMWF AIFS proti dejanskim meritvam postaje IREICA1 — "
            f"{n} razrešenih dni.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-14"),
        seo.crumbs_schema([("Meteorec", "/"), ("Točnost napovedi", None)]),
        seo.named_dataset_schema(
            url, "Verifikacija vremenske napovedi — Rečica ob Savinji",
            "Dnevna primerjava napovedi ARSO, Open-Meteo in ECMWF AIFS z dejansko meritvijo postaje IREICA1.",
            variable_measured=[{"@type": "PropertyValue", "name": "Razrešeni dnevi", "value": n, "unitText": "dni"}],
        ),
    ])

    html_out = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("tocnost-napovedi/index.html", html_out, force=True)
    print(f"  → tocnost-napovedi/index.html ({n} razrešenih dni)")


if __name__ == "__main__":
    main()
