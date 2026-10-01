#!/usr/bin/env python3
"""
tools/generate_year_review_post.py — »Vremensko leto v številkah« (1. oktobra).

Povzame pravkar končano vremensko (hidrološko) leto, 1. 10. – 30. 9., za
Rečico ob Savinji iz meritev postaje IREICA1: odstopanje od norme, mesto med
dosedanjimi leti, ekstremi, vroči/mrzli dnevi, prva/zadnja zmrzal in pregled po
mesecih. Zakaj oktober–september: tako leto zajame celo zimo naenkrat in
konča s poletjem, ki je ravno za nami — koledarsko leto zimo razreže na dva kosa.

Isti vzorec kot generate_forecast_test_post.py — predloga s pravimi
izračunanimi številkami (brez LLM osnutka, da se nič ne izmisli), nato EN
prehod lekture (call_lektor) — lektura je obvezna za vsak članek (CLAUDE.md).
Pragovi dni (vroč, zmrzal, tropska noč) in norme so isti kot na arhivskih
straneh (generate_seo_pages / seo_smart_routine), uvoženi, ne podvojeni.

Usage:
    python3 tools/generate_year_review_post.py [--wire] [--dry-run] [--force] [--end-year 2026]
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
from generate_seo_pages import is_hot, is_frost, is_tropical_night, num  # noqa: E402
from seo_smart_routine import compute_climate  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
# Leto mora biti skoraj polno, sicer ni primerljivo (arhiv se začne novembra 2019).
MIN_DAYS = 330


def hydro_months(end_year):
    return [(end_year - 1, m) for m in (10, 11, 12)] + [(end_year, m) for m in range(1, 10)]


def year_entries(hist, end_year):
    out = []
    for y, m in hydro_months(end_year):
        pre = f"{y}-{m:02d}-"
        out += [(d, v) for d, v in hist.items() if d.startswith(pre)]
    return sorted(out)


def label(end_year):
    return f"{end_year - 1}/{str(end_year)[2:]}"


def year_summary(hist, end_year, normals):
    e = year_entries(hist, end_year)
    if len(e) < MIN_DAYS:
        return None
    s = seo.month_stats(e)
    s["t_norm"] = seo.normal_temp_for_period(e, normals)
    # Normo padavin seštejemo po mesecih (leto pokriva dva koledarska leta).
    p_norm = 0.0
    for y, m in hydro_months(end_year):
        me = [(d, v) for d, v in e if d.startswith(f"{y}-{m:02d}-")]
        p_norm += seo.normal_precip_for_period(me, normals, y) or 0.0
    s["p_norm"] = p_norm or None
    s["hot"] = sum(1 for _, v in e if is_hot(v))
    s["frost"] = sum(1 for _, v in e if is_frost(v))
    s["trop"] = sum(1 for _, v in e if is_tropical_night(v))

    def ext(key, fn):
        c = [(d, v[key]) for d, v in e if v.get(key) is not None]
        return fn(c, key=lambda x: x[1]) if c else (None, None)

    s["hi"] = ext("tempHigh", max)
    s["lo"] = ext("tempLow", min)
    s["wet"] = ext("precipTotal", max)
    s["gust"] = ext("windgustHigh", max)
    autumn = [d for d, v in e if d < f"{end_year}-01-01" and is_frost(v)]
    spring = [d for d, v in e if f"{end_year}-01-01" <= d <= f"{end_year}-06-30" and is_frost(v)]
    s["first_frost"] = autumn[0] if autumn else None
    s["last_frost"] = spring[-1] if spring else None
    s["months"] = []
    for y, m in hydro_months(end_year):
        me = [(d, v) for d, v in e if d.startswith(f"{y}-{m:02d}-")]
        ms = seo.month_stats(me)
        if ms:
            ms["t_norm"] = seo.normal_temp_for_period(me, normals)
            ms["p_norm"] = seo.normal_precip_for_period(me, normals, y)
            s["months"].append((y, m, ms))
    return s


def ranks(hist, end_year, normals, key):
    """Mesto leta med vsemi primerljivimi vremenskimi leti (1 = največ)."""
    vals = {}
    for ey in range(2020, end_year + 1):
        ys = year_summary(hist, ey, normals)
        if ys and ys.get(key) is not None:
            vals[ey] = ys[key]
    if end_year not in vals:
        return None
    return 1 + sum(1 for v in vals.values() if v > vals[end_year]), len(vals)


def _signed(d):
    if num(abs(d)) == "0,0":
        return "±0,0 °C"
    return f"{'+' if d >= 0 else '−'}{num(abs(d))} °C"


def build_article(end_year, s, t_rank, p_rank):
    lab = label(end_year)
    t_dev = s["tavg"] - s["t_norm"] if s.get("t_norm") is not None else None
    p_pct = s["prec_total"] / s["p_norm"] * 100 if s.get("p_norm") else None
    lead = (f"Vremensko leto {lab} (od 1. oktobra {end_year - 1} do 30. septembra {end_year}) je "
            f"v Rečici ob Savinji prineslo povprečno temperaturo {num(s['tavg'])} °C in "
            f"{num(s['prec_total'], 0)} mm padavin")
    if t_dev is not None:
        lead += f" — {_signed(t_dev)} glede na dolgoletno povprečje postaje"
    lead += "."
    if t_rank:
        pos, n = t_rank
        ph = seo.rank_phrase(t_rank, "najtoplejše", "najhladnejše")
        lead += (f" Med {n} vremenskimi leti, odkar postaja meri, je bilo "
                 + (f"{ph}." if ph else "po temperaturi točno na sredini."))

    p1 = []
    if p_pct is not None:
        word = ("več kot običajno" if p_pct >= 105 else "manj kot običajno" if p_pct <= 95
                else "približno toliko kot običajno")
        p1.append(f"Padavin je bilo {num(p_pct, 0)} % dolgoletnega povprečja, torej {word}"
                  + (f" ({ph} od {p_rank[1]} let)"
                     if p_rank and (ph := seo.rank_phrase(p_rank, "najbolj namočeno", "najbolj suho"))
                     else "") + ".")
    p1.append(f"Dni z več kot 0,2 mm padavin je bilo {s['prec_days']}.")

    hi_d, hi_v = s["hi"]
    lo_d, lo_v = s["lo"]
    wd, wv = s["wet"]
    gd, gv = s["gust"]
    ext = []
    if hi_v is not None:
        ext.append(f"<li>Najtoplejši dan: <strong>{num(hi_v)} °C</strong>, {seo.fmtd(hi_d)}</li>")
    if lo_v is not None:
        ext.append(f"<li>Najhladnejša noč: <strong>{num(lo_v)} °C</strong>, {seo.fmtd(lo_d)}</li>")
    if wv is not None:
        ext.append(f"<li>Največ padavin v enem dnevu: <strong>{num(wv)} mm</strong>, {seo.fmtd(wd)}</li>")
    if gv is not None:
        ext.append(f"<li>Najmočnejši sunek vetra: <strong>{num(gv)} km/h</strong>, {seo.fmtd(gd)}</li>")
    ext_html = "<ul>" + "".join(ext) + "</ul>"

    days = (f"Vročih dni (najvišja temperatura vsaj 30 °C) je bilo {s['hot']}, dni z zmrzaljo "
            f"(najnižja temperatura 0 °C ali manj) {s['frost']}"
            + (f", tropskih noči {s['trop']}" if s["trop"] else "") + ".")
    frost_bits = []
    if s["first_frost"]:
        frost_bits.append(f"prva jesenska zmrzal je bila {seo.fmtd(s['first_frost'])}")
    if s["last_frost"]:
        frost_bits.append(f"zadnja spomladanska {seo.fmtd(s['last_frost'])}")
    if frost_bits:
        days += " " + ", ".join(frost_bits).capitalize() + "."

    rows = []
    for y, m, ms in s["months"]:
        dev = _signed(ms["tavg"] - ms["t_norm"]) if ms.get("t_norm") is not None else "—"
        pp = f"{num(ms['prec_total'] / ms['p_norm'] * 100, 0)} %" if ms.get("p_norm") else "—"
        rows.append(f'<tr><td><a href="/vreme/{y}/{m:02d}/">{seo.MES_NOM[m].capitalize()} {y}</a></td>'
                    f'<td>{num(ms["tavg"])} °C</td><td>{dev}</td>'
                    f'<td>{num(ms["prec_total"], 0)} mm</td><td>{pp}</td></tr>')
    table = ('<div class="table-scroll"><table class="data-table"><thead><tr><th>Mesec</th>'
             '<th>Povp. T</th><th>Odstopanje</th><th>Padavine</th><th>Od norme</th></tr></thead>'
             '<tbody>' + "".join(rows) + '</tbody></table></div>')

    title = f"Vremensko leto {lab} v Rečici ob Savinji v številkah"
    return {
        "title": title,
        "meta_description": (f"Vremensko leto {lab} v Rečici ob Savinji: {num(s['tavg'])} °C, "
                             f"{num(s['prec_total'], 0)} mm padavin, {s['hot']} vročih dni in "
                             f"{s['frost']} dni z zmrzaljo. Meritve postaje IREICA1."),
        "tags": ["letni-pregled", "klima", str(end_year)],
        "section_label": "Letni pregled",
        "og_photo": "weather-station",
        "og_accent_hex": "#f59e0b",
        "lead": lead,
        "sections": [
            {"label": "01 — padavine", "heading": "Koliko je padlo", "id": "padavine", "paragraphs": p1},
            {"label": "02 — ekstremi", "heading": "Ekstremi leta", "id": "ekstremi", "paragraphs": [ext_html]},
            {"label": "03 — dnevi", "heading": "Vroči dnevi in zmrzal", "id": "dnevi", "paragraphs": [days]},
            {"label": "04 — po mesecih", "heading": "Mesec za mesecem", "id": "meseci", "paragraphs": [table]},
            {"label": "05 — metodologija", "heading": "Od kod številke", "id": "metodologija", "paragraphs": [
                "Vse vrednosti so izmerjene na postaji IREICA1 v Rečici ob Savinji (366 m). Dolgoletno "
                "povprečje je povprečje polnih let meritev postaje, ne 30-letna klimatološka serija ARSO, "
                "zato je odstopanje treba brati kot primerjavo z zadnjimi leti v tej dolini. "
                f'Vsi dnevi so v <a href="{SITE}/vreme/" style="color:var(--blue)">vremenskem arhivu</a>.'
            ]},
        ],
        "callout": None,
        "sources_note": "Vir: meritve postaje IREICA1 (Meteorec), history.json, licenca CC BY 4.0.",
    }


def main():
    wire = "--wire" in sys.argv
    dry = "--dry-run" in sys.argv
    today = datetime.date.today()
    end_year = today.year if today.month >= 10 else today.year - 1
    if "--end-year" in sys.argv:
        end_year = int(sys.argv[sys.argv.index("--end-year") + 1])

    slug = f"vremensko-leto-{end_year - 1}-{end_year}"
    if not dry and "--force" not in sys.argv and os.path.exists(os.path.join(ROOT, "blog", f"{slug}.html")):
        # Objavljen članek se ne prepisuje (FB/IG, lektura, dateModified) — enkrat na leto.
        print(f"blog/{slug}.html že obstaja — brez ponovne objave (--force za prepis).")
        return

    hist = seo.load_history()
    normals, *_ = compute_climate(hist)
    s = year_summary(hist, end_year, normals)
    if not s:
        print(f"Vremensko leto {label(end_year)} nima dovolj meritev (< {MIN_DAYS} dni) — brez objave.")
        return
    t_rank = ranks(hist, end_year, normals, "tavg")
    p_rank = ranks(hist, end_year, normals, "prec_total")
    article = build_article(end_year, s, t_rank, p_rank)
    if dry:
        print(json.dumps(article, ensure_ascii=False, indent=2))
        return

    # Uvoz tu: generate_forecast_test_post potegne meritvene module, ki jih --dry-run ne rabi.
    import generate_forecast_test_post as ftp
    from generate_daily_post import call_lektor
    if os.environ.get("ANTHROPIC_API_KEY"):
        review = call_lektor(article, {"leto": label(end_year), "povzetek": {
            k: s[k] for k in ("tavg", "t_norm", "prec_total", "p_norm", "hot", "frost", "trop")}})
        for i in review.get("issues") or []:
            print(f"  lektor: {i}")
        final = review.get("corrected") or article
    else:
        print("  ⚠ ANTHROPIC_API_KEY ni nastavljen -- lektura preskočena.")
        final = article

    ftp.TODAY = today.isoformat()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        final, end_year, 9, now_utc, slug=slug,
        back=("/vreme/", "← Vremenski arhiv"),
        og_title=f"Vremensko leto\n{label(end_year)}",
        meta_note="samodejni letni pregled")
    with open(os.path.join(ROOT, "blog", f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
