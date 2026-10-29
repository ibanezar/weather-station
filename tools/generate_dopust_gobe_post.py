#!/usr/bin/env python3
"""
tools/generate_dopust_gobe_post.py -- »Prvi vikend po dežju je za jurčke prezgodaj« (22. 10. 2026).

Ročno napisan podatkovni članek po osnutku docs/osnutek-dopust-gobe.md. Številke pridejo iz committanih virov:
  - history.json        (postaja IREICA1: samo zunanje dnevne padavine, brez ERA5 nadomestkov),
  - species_rules.yaml  (okna zamika po dežju: jurček 8-16 dni, lisička 4-14 dni).
Koledarski del (tabela) je aritmetika oken in je v besedilu tako povedan; pravi podatek je štetje dogodkov z dežjem.
Trditve varujejo assert-i: če se podatki spremenijo, generator pade -- besedilo je treba pregledati, ne zaobiti asserta.

OPOMBA: osnutek je navajal 52 dogodkov in lisičko 37 od 52 v prvem vikendu. Z jasno definicijo (spodaj) in
komaj izračunano tabelo je rezultat 53 dogodkov in lisička 28 od 53 (okoli polovice). Članek navaja te številke.

Članek se ne objavi samodejno: brez --wire samo zapiše datoteko blog/<slug>.html. Ročni članek po CLAUDE.md gre
skozi lekturo (`lektura.yml` je od 2. 10. 2026 izklopljena -- do ponovnega vklopa slogovni pregled po docs/slog-pisanja.md).
Notranjih meritev postaje članek ne uporablja.

Usage:
    python3 tools/generate_dopust_gobe_post.py [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(ROOT, "history.json")
RULES = os.path.join(ROOT, "species_rules.yaml")
SLUG = "prvi-vikend-po-dezju-jurcki-1022"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-dopust-gobe.txt")
NBSP = " "

# Definicija dogodka z dežjem: dnevi z vsaj 3 mm, med sosednjima dnevoma največ en dan vrzeli, skupaj vsaj 20 mm;
# avgust-november 2020-2026 (leto brez meritve postaje ne šteje).
DAY_MM, GAP_DAYS, EVENT_MM = 3.0, 2, 20.0
MONTHS, Y0, Y1 = (8, 11), 2020, 2026
JURCEK, LISICKA = (8, 16), (4, 14)
_DAN_SHORT = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
_MES = ["", "januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra", "oktobra",
        "novembra", "decembra"]


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def load():
    H = json.load(open(HISTORY, encoding="utf-8"))
    H = H.get("days", H)
    return {k: v for k, v in H.items() if v.get("src") != "era5" and v.get("precipTotal") is not None}


def events(H):
    days = sorted(k for k, v in H.items() if v["precipTotal"] >= DAY_MM
                  and MONTHS[0] <= int(k[5:7]) <= MONTHS[1] and Y0 <= int(k[:4]) <= Y1)
    out, cur = [], []
    for k in days:
        D = datetime.date.fromisoformat(k)
        if cur and (D - datetime.date.fromisoformat(cur[-1])).days <= GAP_DAYS:
            cur.append(k)
        else:
            if cur:
                out.append(cur)
            cur = [k]
    if cur:
        out.append(cur)
    return [e for e in out if sum(H[k]["precipTotal"] for k in e) >= EVENT_MM]


def weekends(end_wd):
    """Dnevi po zadnjem deževnem dnevu (weekday 0=pon), ki so vikend: (prvi vikend, drugi vikend).
    Če dež konča sobota, je prvi vikend samo nedelja (dan 1)."""
    wk = [i for i in range(1, 15) if (end_wd + i) % 7 >= 5]
    first = [wk[0]] + ([wk[1]] if (end_wd + wk[0]) % 7 == 5 else [])
    second = [i for i in wk if i not in first][:2]
    return first, second


def in_window(days, win):
    return any(win[0] <= d <= win[1] for d in days)


def counts(evs):
    j1 = l1 = j2 = 0
    for e in evs:
        first, second = weekends(datetime.date.fromisoformat(e[-1]).weekday())
        j1 += in_window(first, JURCEK)
        l1 += in_window(first, LISICKA)
        j2 += in_window(second, JURCEK)
    return j1, l1, j2


def table(rows_html):
    return ('<div class="vs-tbl"><table><thead><tr><th>Zadnji deževni dan</th><th>Prvi vikend (dan po dežju)</th>'
            '<th>Drugi vikend (dan po dežju)</th><th>Prvi vikend v oknu lisičke (4–14)</th>'
            '<th>Drugi vikend v oknu jurčka (8–16)</th></tr></thead><tbody>' + rows_html + '</tbody></table></div>')


def calendar_rows():
    rows = []
    for wd in range(7):
        first, second = weekends(wd)
        l = [d for d in first if LISICKA[0] <= d <= LISICKA[1]]
        l_txt = "da" if len(l) == len(first) else ("deloma" if l else "ne")
        j = [d for d in second if JURCEK[0] <= d <= JURCEK[1]]
        j_txt = "da" if len(j) == len(second) else ("deloma" if j else "ne")
        rows.append(f"<tr><td>{_DAN_SHORT[wd]}</td><td>{', '.join(str(d) + '.' for d in first)}</td>"
                    f"<td>{', '.join(str(d) + '.' for d in second)}</td><td>{l_txt}</td><td>{j_txt}</td></tr>")
    return "".join(rows)


STYLE = """<style>
.vs-tbl{overflow-x:auto;max-width:100%;margin:1rem 0}
.vs-tbl table{border-collapse:collapse;width:100%;font-size:.86rem}
.vs-tbl th,.vs-tbl td{padding:.42rem .5rem;text-align:right;border-bottom:1px solid var(--border)}
.vs-tbl td{white-space:nowrap}
.vs-tbl th{vertical-align:bottom;line-height:1.3;color:var(--muted);font-weight:600;font-size:.76rem}
.vs-tbl th:first-child,.vs-tbl td:first-child{text-align:left}
.vs-note{color:var(--muted);font-size:.9rem;line-height:1.55}
</style>"""


def build_article(H):
    evs = events(H)
    n = len(evs)
    j1, l1, j2 = counts(evs)
    assert n == 53, n
    assert (j1, l1, j2) == (0, 28, 53), (j1, l1, j2)

    # primer: september 2026
    p10, p11 = H["2026-09-10"]["precipTotal"], H["2026-09-11"]["precipTotal"]
    assert (round(p10, 1), round(p11, 1), round(p10 + p11, 1)) == (85.1, 35.6, 120.7), (p10, p11)
    ex = datetime.date(2026, 9, 11)
    assert ex.weekday() == 4                                   # petek
    assert H.get("2026-09-12", {}).get("precipTotal", 0) < DAY_MM and any(e[-1] == "2026-09-11" for e in evs)

    # začetek dogodka po dnevu v tednu
    starts = [0] * 7
    for e in evs:
        starts[datetime.date.fromisoformat(e[0]).weekday()] += 1
    top = sorted(range(7), key=lambda i: -starts[i])[:2]
    assert sum(starts) == n

    pct_l = round(100 * l1 / n)
    title = "Prvi vikend po dežju je za jurčke prezgodaj"
    assert len(title) <= 60
    desc = ("V petek dežuje, v soboto greste v gozd, pa ni nič. Po modelu je prvi vikend za jurčke prezgodaj, "
            "za lisičke je ravno prav le približno v polovici primerov.")
    assert len(desc) <= 160, len(desc)

    lead = ('<strong>Kratek odgovor: prvi vikend po dežju je za jurčka po našem modelu prezgodaj.</strong> '
            'Ni slaba sreča in ni sosedova skrivnost, ampak koledar. Drugi vikend je po istem modelu za jurčka v oknu.')
    intro = ('Poznate takšen teden? V petek vsa dolina dežuje, v soboto zjutraj greste v gozd, pa so tla mokra in klobukov ni. '
             'V torek vas sosed vpraša, ali ste že bili, v soboto pa se pohvali s košaro. Zdi se, kot da gobe rastejo takrat, '
             'ko ste v službi ali drugje.')
    p1 = [
        intro,
        'Model za mikorizne vrste računa, da po sprožilnem dežju mine 8–16 dni, preden zraste trosnjak (jurček), za lisičko pa '
        '4–14 dni. Okno jurčka je torej 9 dni dolgo in vedno vsebuje vsaj eno soboto in eno nedeljo. Prvi vikend po dežju pa pade v prvih 1–7 '
        'dneh, zato je pri jurčku vedno pred oknom. To je čisti koledarski račun, brez podatkov postaje:',
        table(calendar_rows()),
    ]
    p2 = [
        f'V Rečici je 10. septembra padlo {num(p10)} mm, 11. septembra še {num(p11)} mm, skupaj {num(p10 + p11)} mm. '
        'Zadnji deževni dan je bil petek. Prvi vikend (12. in 13. septembra) je bil 1. in 2. dan po dežju, za jurčka torej močno '
        'prezgodaj. Okno jurčka se je po modelu začelo 19. septembra in je trajalo do 27. septembra; drugi vikend (19. in 20. '
        'septembra) je bil v njem. Prvi zabeleženi opažanji bralcev sta 20. in 21. septembra.',
    ]
    p3 = [
        f'Pregledal sem padavine postaje IREICA1 od avgusta do novembra v letih {Y0}–{Y1}. Dogodek dežja je skupina dni z vsaj '
        f'{num(DAY_MM, 0)} mm (vrzel največ en dan), skupaj vsaj {num(EVENT_MM, 0)} mm. Takih dogodkov je bilo {n}. Pri vsakem sem '
        'preveril, ali vsaj en dan prvega oziroma drugega vikenda po zadnjem deževnem dnevu pade v okno vrste.',
        f'<ul><li>Pri <strong>jurčku</strong> noben dan prvega vikenda po dežju ni bil v oknu 8–16 dni v nobenem od {n} dogodkov. Vsaj en dan drugega vikenda je bil '
        f'v oknu v vseh {n}. To sledi iz koledarja; številka le pokaže, da prvi vikend ni redka izjema, ampak pravilo.</li>'
        f'<li>Pri <strong>lisički</strong> je bil vsaj en dan prvega vikenda v oknu 4–14 dni v {l1} od {n} dogodkov, torej v okoli {pct_l} %. '
        'Če dežuje v petek ali četrtek, je za lisičko prvi vikend prezgodaj; če dežuje na začetku tedna, je večinoma ravno prav.</li></ul>',
        f'Dež sam na dan v tednu ne gleda. Dogodki so se začeli v vseh dnevih tedna, najpogosteje v '
        f'{["ponedeljek", "torek", "sredo", "četrtek", "petek", "soboto", "nedeljo"][top[0]]} ({starts[top[0]]} od {n}) in v '
        f'{["ponedeljek", "torek", "sredo", "četrtek", "petek", "soboto", "nedeljo"][top[1]]} ({starts[top[1]]} od {n}).',
    ]
    p4 = [
        '<ul>'
        '<li><strong>Zamiki so modelska ocena.</strong> Okno 8–16 dni za jurčka je v bazi označeno kot nekalibrirano. Za lisičko ga podpira '
        'analiza iNaturalista, ki kaže mediano 6–7 dni po začetku dežja; za jurčka je podpora šibkejša.</li>'
        '<li><strong>Opažanje ni prvi trosnjak.</strong> Stari trosnjaki se fotografirajo še dolgo, zato je zamik v opažanjih zgornja ocena.</li>'
        '<li><strong>Dopusta ne merimo.</strong> Članek ne trdi, da gobe ne rastejo, ko ste v službi, ampak da je vzorec delno posledica koledarja.</li>'
        '<li><strong>Model ne pozna vašega gozda.</strong> Višina, tla in suša pred dežjem lahko okno premaknejo za več dni; '
        '<a href="/gobarska-napoved/valovi/" style="color:var(--blue)">kalkulator rasti po dežju</a> vzame del tega v račun.</li>'
        '</ul>',
    ]
    p5 = [
        'Če dežuje v četrtek ali petek, <strong>prvi vikend preskočite</strong> (za lisičke ga lahko izkoristite, če je dež padel na '
        'začetku tedna). Pojdite drugi vikend, ko je jurček po modelu v oknu. V '
        '<a href="/gobarska-napoved/valovi/" style="color:var(--blue)">kalkulator rasti po dežju</a> vpišite datum dežja in količino '
        'in preberite okno za svoje območje.',
        'Gobe nabirajte samo, če jih zanesljivo poznate. Dvojnice jurčka in druge strupene vrste so na strani '
        '<a href="/gobarska-napoved/strupene-gobe/" style="color:var(--blue)">strupene gobe</a>.',
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]
    sections = [
        {"label": "01 — koledar", "heading": "Koledar", "id": "koledar", "paragraphs": p1},
        {"label": "02 — primer", "heading": "Primer: september 2026", "id": "primer", "paragraphs": p2},
        {"label": "03 — postaja", "heading": "Kaj pravijo padavine postaje", "id": "postaja", "paragraphs": p3},
        {"label": "04 — omejitve", "heading": "Česa ne vemo", "id": "omejitve", "paragraphs": p4},
        {"label": "05 — praktično", "heading": "Kaj naj naredite", "id": "prakticno", "paragraphs": p5},
    ]

    def nb(h):
        return re.sub(r"(\d) (°C|%|mm)", lambda m: m.group(1) + NBSP + m.group(2), h)
    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [nb(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["gobe", "jurcki", "lisicke", "dez", "podatki"],
        "section_label": "Podatkovna analiza", "og_photo": "misty-valley", "og_accent_hex": "#34d399",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": (f"Viri: postaja IREICA1 (dnevne padavine, history.json, avgust–november {Y0}–{Y1}); model Meteorec "
                         "(okna zamika po skupinah, species_rules.yaml); iNaturalist × Open-Meteo (analiza zamika lisičke)."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|li|p|div|tr)[^>]*>", "\n", h)
        h = re.sub(r"</t[dh]>", " | ", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace(NBSP, " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        for p in s["paragraphs"]:
            out += [clean(p), ""]
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    article = build_article(load())
    if "--text" in sys.argv:
        open(TEXT_OUT, "w", encoding="utf-8").write(plain_text(article))
        print("✓ besedilo za pregled:", os.path.relpath(TEXT_OUT, ROOT))
    if dry:
        print(plain_text(article))
        return
    path = os.path.join(ROOT, "blog", f"{SLUG}.html")
    if os.path.exists(path) and not force:
        print(f"blog/{SLUG}.html že obstaja -- brez ponovne objave (--force za prepis).")
        return
    import generate_forecast_test_post as ftp
    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = today.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, today.year, today.month, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Prvi vikend po dežju\nje za jurčke prezgodaj", meta_note="podatkovna analiza",
        nav_label="Gobarska napoved", nav_href="/gobarska-napoved/")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire or "--og" in sys.argv:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
    if wire:
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml, teme in sorodni članki osveženi.")


if __name__ == "__main__":
    main()
