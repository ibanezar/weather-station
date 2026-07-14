#!/usr/bin/env python3
"""
tools/generate_tocnost_page.py — /tocnost-napovedi/ forecast-accuracy scoreboard

Generates /tocnost-napovedi/index.html from forecast_verification.json (built
daily by tools/verify_forecasts.py): a running, transparent scoreboard of how
close the ARSO and Open-Meteo day-ahead forecasts for Rečica ob Savinji came
to what the station actually measured. Nobody publishes this systematically
for a Slovenian valley — it's a genuine, unique content type built entirely
from data this station already has.

The scoreboard has no historical backfill (forecast providers don't publish
retroactive archives) — it starts accumulating from whenever the pipeline
first ran and grows one resolved day at a time. The page is honest about
that instead of pretending otherwise.

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


def load_verification():
    try:
        with open(VERIFICATION_PATH, encoding="utf-8") as f:
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


def build_body(verification):
    dates = sorted(verification.keys())
    records = [verification[d] for d in dates]
    n_days = len(records)
    first_date = dates[0] if dates else None

    arso_stats = source_stats(records, "arso")
    om_stats = source_stats(records, "open_meteo")

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
        status = (f'  <p class="archive-intro"><strong>{n_days} razrešenih dni</strong> od {seo.fmtd(first_date)}. '
                   f'{"; ".join(parts)}.</p>')

    intro = ('  <p class="archive-intro">Vsak dan zabeležimo, kaj ARSO in Open-Meteo napovesta za jutrišnjo '
             'najvišjo/najnižjo temperaturo v Rečici ob Savinji, naslednji dan pa to primerjamo z dejansko '
             'meritvijo postaje IREICA1. Nič se ne popravlja za nazaj — to je surova, tekoča ocena '
             'napovedne uspešnosti za to konkretno dolino, ne za Slovenijo na splošno.</p>')

    # ── Scoreboard kartice ──────────────────────────────────────────────
    def stat_card(label, stats, cls):
        val = seo.num(stats["mae_tmax"]) if stats["mae_tmax"] is not None else "—"
        return (f'    <div class="stat-card {cls}"><div class="sc-label">{label}</div>'
                f'<div class="sc-val">±{val}</div><div class="sc-sub">°C povp. napaka maks. T · {stats["n"]} napovedi</div></div>')

    cards = ('  <div class="stat-grid">\n'
              + stat_card("ARSO", arso_stats, "c-temp") + "\n"
              + stat_card("Open-Meteo", om_stats, "c-rain") + "\n"
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
        y, m = int(ym[:4]), int(ym[5:7])
        a_txt = f'±{seo.num(a["mae_tmax"])} °C' if a["mae_tmax"] is not None else "—"
        o_txt = f'±{seo.num(o["mae_tmax"])} °C' if o["mae_tmax"] is not None else "—"
        month_rows.append(f'    <tr><th>{seo.MES_NOM[m].capitalize()} {y}</th><td>{a_txt}</td><td>{o_txt}</td><td>{len(recs)}</td></tr>')
    month_table = ('  <table class="stats">\n'
                    '    <tr><th>Mesec</th><th>ARSO povp. napaka</th><th>Open-Meteo povp. napaka</th><th>Dni</th></tr>\n'
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
        a_txt = f'{seo.num(a.get("tmax"))} °C (±{seo.num(a.get("err_tmax"))})' if a.get("tmax") is not None else "—"
        o_txt = f'{seo.num(o.get("tmax"))} °C (±{seo.num(o.get("err_tmax"))})' if o.get("tmax") is not None else "—"
        recent_rows.append(
            f'    <tr><th><a href="/vreme/{d[:4]}/{d[5:7]}/{d[8:10]}/">{seo.fmtd(d)}</a></th>'
            f'<td>{seo.num(act.get("tmax"))} °C</td><td>{a_txt}</td><td>{o_txt}</td></tr>'
        )
    recent_table = ('  <table class="stats">\n'
                     '    <tr><th>Datum</th><th>Dejanska maks. T</th><th>ARSO je napovedal</th><th>Open-Meteo je napovedal</th></tr>\n'
                     + "\n".join(recent_rows) + '\n  </table>') if recent_rows else \
        '  <p class="muted-note">Še ni razrešenih dni.</p>'

    # ── FAQ ─────────────────────────────────────────────────────────────
    qa = [
        ("Kako točna je vremenska napoved za Zgornjo Savinjsko dolino?",
         "Ta stran dnevno meri, za koliko stopinj se napovedi ARSO in Open-Meteo za naslednji dan povprečno "
         "zmotijo glede na dejansko meritev postaje IREICA1 v Rečici ob Savinji. Trenutna povprečna napaka "
         "je prikazana zgoraj in se dnevno posodablja — brez popravljanja za nazaj."),
        ("Je ARSO napoved zanesljiva?",
         "Odvisno od obdobja in spremenljivke — glej mesečni pregled spodaj. Ta stran meri samo dan vnaprej "
         "napovedano najvišjo/najnižjo temperaturo za eno konkretno lokacijo (Rečica ob Savinji), ne "
         "splošne zanesljivosti ARSO napovedi za Slovenijo."),
        ("Zakaj se primerjava začne šele nedavno?",
         "ARSO in Open-Meteo ne objavljata arhiva preteklih napovedi, zato primerjave ni mogoče izračunati "
         "za nazaj — beležimo jo dan za dnem, odkar ta stran obstaja."),
        ("Kje je primerjava za naslednjih nekaj ur (ne dni)?",
         "Uro-natančno primerjavo lastnega statističnega modela (Holt-Winters), Open-Meteo in postaje za "
         "zadnjih 24 ur najdeš na naslovni strani v razdelku »AI napoved«."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Točnost napovedi", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Točnost vremenske napovedi — Rečica ob Savinji</h1>
  <p class="post-meta">ARSO vs. Open-Meteo vs. dejanska meritev · {n_days} razrešenih dni · {TODAY.isoformat()}</p>
{intro}
{status}
{cards}
  <h2>Mesečni pregled</h2>
{month_table}
  <h2>Zadnji dnevi</h2>
{recent_table}
{faq_html}
  <p class="muted-note">Metodologija: vsak dan zabeležimo napoved ARSO in Open-Meteo za jutrišnjo najvišjo/
  najnižjo temperaturo v Rečici ob Savinji; ko dan mine, ju primerjamo z dejansko dnevno meritvijo postaje
  IREICA1. Napaka je absolutna razlika v °C. Nobena pretekla napoved se ne popravlja ali briše.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body


def main():
    verification = load_verification()
    body = build_body(verification)

    url = "/tocnost-napovedi/"
    title = "Točnost vremenske napovedi — Rečica ob Savinji"
    n = len(verification)
    desc = (f"Koliko točna je vremenska napoved za Zgornjo Savinjsko dolino? Dnevni scoreboard ARSO vs. "
            f"Open-Meteo proti dejanskim meritvam postaje IREICA1 — {n} razrešenih dni.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-14"),
        seo.crumbs_schema([("Meteorec", "/"), ("Točnost napovedi", None)]),
        seo.named_dataset_schema(
            url, "Verifikacija vremenske napovedi — Rečica ob Savinji",
            "Dnevna primerjava napovedi ARSO in Open-Meteo z dejansko meritvijo postaje IREICA1.",
            variable_measured=[{"@type": "PropertyValue", "name": "Razrešeni dnevi", "value": n, "unitText": "dni"}],
        ),
    ])

    html_out = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("tocnost-napovedi/index.html", html_out, force=True)
    print(f"  → tocnost-napovedi/index.html ({n} razrešenih dni)")


if __name__ == "__main__":
    main()
