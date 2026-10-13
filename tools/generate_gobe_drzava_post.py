#!/usr/bin/env python3
"""
tools/generate_gobe_drzava_post.py — »Bi gobarski indeks deloval po vsej Sloveniji?« (13. 10. 2026).

Ročno napisan članek (ne samodejni generator). Številke pridejo iz že committanih datotek
(gobarska-napoved/index.json, indeks-zgodovina.json, izbirnik.json, species_rules.yaml); trditve o tem,
česa model ne zna, so omejene na tisto, kar piše v CLAUDE.md in na /gobarska-napoved/metodologija/.
Državnega indeksa članek NE izračuna — razloži, zakaj ga ni.

Po CLAUDE.md gre po objavi skozi lekturo (lektura.yml je od 2. 10. 2026 izklopljena; do ponovnega vklopa
ostane pregled po docs/slog-pisanja.md).

Usage:
    python3 tools/generate_gobe_drzava_post.py [--wire] [--dry-run] [--force]
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
SLUG = "gobarski-indeks-po-vsej-sloveniji-1013"
GOBE = os.path.join(ROOT, "gobarska-napoved")


def link(href, text):
    return f'<a href="{href}" style="color:var(--blue)">{text}</a>'


def load():
    idx = json.load(open(os.path.join(GOBE, "index.json"), encoding="utf-8"))
    hist = json.load(open(os.path.join(GOBE, "indeks-zgodovina.json"), encoding="utf-8"))
    import yaml
    rules = yaml.safe_load(open(os.path.join(ROOT, "species_rules.yaml"), encoding="utf-8"))
    locs = [l for l in rules["locations"] if not l.get("protected")]   # zaščitena območja so izločena povsod
    assert len(locs) == idx["locations_count"], "število območij se ne ujema z index.json"
    return idx, hist, locs


def build_article(idx, hist, locs):
    elev = [l["elev_m"] for l in locs]
    emin, emax = min(elev), max(elev)
    last, first = hist[-1], hist[-6]
    assert last["index"] > first["index"], "uvod trdi, da indeks narašča"
    n_loc, n_sp = idx["locations_count"], idx["species_count"]
    d_last = datetime.date.fromisoformat(last["date"])
    d_first = datetime.date.fromisoformat(first["date"])

    lead = "</p>\n<p class=\"lead\">".join([
        f"Kratek odgovor: za zdaj ne. Gobarski indeks danes velja za "
        f"{n_loc} nabiralnih območij v Zgornji Savinjski dolini, ne za vso državo. V Rečici ob Savinji je "
        f"{d_last.day}. {d_last.month}. dosegel {last['index']} %, {d_first.day}. {d_first.month}. pa le {first['index']} %.",
        "Državne številke nimam, ker bi jo moral sestaviti iz podatkov, ki jih za druge kraje nimam. Spodaj je, kaj bi se "
        "prenesel po državi, česa ne in kaj bi za pošteno državno oceno potreboval.",
    ])

    p1 = [
        f"Model računa indeks za {n_loc} območij na višini od {emin} do {emax} m. Vsako območje ima zapisan teren "
        "(kisla, bazična ali vlažna podlaga), indeks pa je izračunan po vrstah: trenutno jih ima indeks "
        f"{n_sp}. Vsa območja so v isti dolini, zato je tudi prikaz na "
        + link("/gobarska-napoved/danes/", "strani Danes po gozdovih") + " omejen nanjo.",
        "Dežja za Rečico ne vzame iz modela, ampak iz lastne postaje IREICA1. Za druga območja doline uporabi Open-Meteo. "
        "Model se je učil na zgodovini te postaje in napovedi Open-Meteo, ne na podatkih iz drugih regij.",
    ]
    p2 = [
        "Del modela ni vezan na kraj in bi se brez težav preselil drugam:",
        "<ul>"
        "<li><strong>Vreme.</strong> Padavine, temperaturo in vlago tal ter zračno vlago Open-Meteo vrne za vsako točko v Sloveniji.</li>"
        "<li><strong>Zamik po dežju.</strong> Vrste so razdeljene na razkrojevalke, lesne in mikorizne, vsaka skupina pa ima svoje okno. "
        "Jurček po dežju ne zraste čez noč, kukmak je hitrejši. To je lastnost vrste, ne doline.</li>"
        "<li><strong>Seznam vrst.</strong> Nanaša se na vso državo, ne le na dolino.</li>"
        "</ul>",
        "Zamik lisičke sem preveril tudi na opažanjih iz vse Slovenije (iNaturalist), zato je ta del modela najmanj odvisen od "
        "doline. Pri drugih vrstah take študije nimam.",
    ]
    p3 = [
        "Težave se začnejo pri tem, kar model o kraju predpostavlja:",
        "<ul>"
        "<li><strong>Teren.</strong> Pri vsakem območju je zapisano, ali je podlaga kisla, bazična ali vlažna. Pri jurčku to pomeni "
        "večji ali manjši popravek indeksa. Za območje, ki ga nimam na seznamu, tega podatka ni.</li>"
        "<li><strong>Višina.</strong> Vrste imajo najljubšo višino. Moja območja so razporejena med "
        f"{emin} in {emax} m, nižinske Slovenije in Primorske pa v modelu ni.</li>"
        "<li><strong>Lokalni dež.</strong> Open-Meteo ima grobo mrežo in lokalnih razlik v dolinah ne ujame vedno. Zato sem za Rečico "
        "vzel postajo; drugje je ni.</li>"
        "<li><strong>Preverjanje.</strong> Pet let nazaj sem indeks preizkusil samo na Rečici. Za druge kraje ne vem, ali bi "
        "dan z visokim indeksom res pomenil več gob.</li>"
        "</ul>",
        "Modela v nobenem primeru ne bi preprosto razširil čez vso državo in napisal »v Sloveniji je danes 60 %«. "
        "Povprečje čez Pomurje, Kras in Pohorje ne bi povedalo ničesar o nobenem gozdu.",
    ]
    p4 = [
        "Če bi se lotil državne ocene, bi jo naredil po korakih:",
        "<ol>"
        "<li>Mreža točk po vsej državi, tako kot jo že imam za nevihtno karto, z vremenom iz Open-Meteo.</li>"
        "<li>Teren in višina za vsako točko iz javnih kart, ne ročno.</li>"
        "<li>Ocena je jasno označena kot <strong>groba</strong>: brez lokalne postaje in brez preverjanja, ločeno od indeksa doline.</li>"
        "<li>Preverjanje z opažanji gobarjev, preden bi kdo na oceno zaupal.</li>"
        "</ol>",
        "Prvi trije koraki so delo. Četrtega ne morem narediti sam.",
    ]
    p5 = [
        "Obrazec »Dodaj opažanje« na strani " + link("/gobarska-napoved/danes/", "Danes po gozdovih") +
        " sprejme območje, vrsto in količino, brez natančne lokacije. Opažanje je javno. Zaenkrat obrazec ponuja samo območja doline, "
        "zato lahko pomagate bralci iz doline. Če nabirate drugje, mi sporočite, od kod in katere vrste. To mi pove, kje se "
        "splača začeti.",
        "Pred nabiranjem preverite vrsto. Strupene gobe in dvojnice so na strani "
        + link("/gobarska-napoved/strupene-gobe/", "Strupene gobe") + ". Indeks pove, kdaj so pogoji ugodni, ne katera goba je užitna.",
    ]
    p6 = [
        "<ul>"
        "<li>Gobarski indeks, model v1.3: " + link("/gobarska-napoved/metodologija/", "kako deluje") + ".</li>"
        "<li>Meritve postaje IREICA1 (Meteorec) in napoved Open-Meteo. Notranjih meritev v članku ni.</li>"
        "<li>Zgodovina indeksa: gobarska-napoved/indeks-zgodovina.json.</li>"
        "</ul>",
        "<strong>Uporaba vsebine:</strong> Besedilo lahko povzemate le z navedbo avtorja (Filip Eremita, Meteorec) in "
        "neposredno povezavo na ta članek. Za prepis se predhodno dogovorite z avtorjem.",
    ]

    title = "Bi gobarski indeks deloval po vsej Sloveniji?"
    desc = ("Gobarski indeks danes velja za Zgornjo Savinjsko dolino. Kaj bi se preneslo po državi in česa model "
            "brez lokalnih podatkov ne zna.")
    assert len(title) <= 60 and len(desc) <= 160, (len(title), len(desc))
    sections = [
        {"label": "01 — kje velja", "heading": "Kje indeks danes velja", "id": "kje", "paragraphs": p1},
        {"label": "02 — kaj se prenese", "heading": "Kaj bi se preneslo drugam", "id": "prenese", "paragraphs": p2},
        {"label": "03 — česa ni", "heading": "Česa modelu drugje manjka", "id": "manjka", "paragraphs": p3},
        {"label": "04 — pot", "heading": "Kako bi nastala državna ocena", "id": "pot", "paragraphs": p4},
        {"label": "05 — kaj lahko storite", "heading": "Kaj lahko storite", "id": "storite", "paragraphs": p5},
        {"label": "06 — viri", "heading": "Viri", "id": "viri", "paragraphs": p6},
    ]
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "gobarski-indeks", "model", "Slovenija"],
        "section_label": "Gobarska napoved", "og_photo": "weather-station", "og_accent_hex": "#34d399",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": "Podatki: gobarski indeks Meteorec (model v" + idx["model_version"] + "), postaja IREICA1, Open-Meteo.",
    }


def main():
    wire, dry, force = "--wire" in sys.argv, "--dry-run" in sys.argv, "--force" in sys.argv
    article = build_article(*load())
    if dry:
        print(json.dumps(article, ensure_ascii=False, indent=2))
        return
    path = os.path.join(ROOT, "blog", f"{SLUG}.html")
    if os.path.exists(path) and not force:
        print(f"blog/{SLUG}.html že obstaja — brez ponovne objave (--force za prepis).")
        return

    import generate_forecast_test_post as ftp
    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = today.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, today.year, today.month, now_utc, slug=SLUG,
        back=("/gobarska-napoved/", "← Gobarska napoved"), og_title="Gobarski indeks\npo vsej državi?",
        meta_note="podatkovni članek", nav_label="O postaji", nav_href="/o-postaji.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
