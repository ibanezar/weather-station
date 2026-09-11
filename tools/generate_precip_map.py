#!/usr/bin/env python3
"""
tools/generate_precip_map.py — dnevna karta izmerjenih padavin (ARSO postaje).

Naslov obiskovalca (10. 9. 2026, ob sliki nacionalne karte zunanje strani
Neurje.si): bi Meteorec lahko naredil kaj podobnega? Ta skript je odgovor —
**lastna** karta, ne kopija tuje: podatki so uradne meritve ARSO (isti vir,
ki ga uporablja worker.js `/arso-obs` za primerjavo ene postaje v
`fetchARSOComparison()` v app.js), izris pa je Meteorčev.

Vir: `observation_si_latest.xml` (isti endpoint kot `/arso-obs`, tu prebran
neposredno — python tek ni v brskalniku, CORS torej ni ovira). Polje
`rr24h_val` je 24-urna kumulativa padavin na vsaki postaji; kolekcija "si"
ima ~20 glavnih samodejnih postaj (redkeje posejano kot Neurje.sijeva karta,
ki verjetno vleče iz gostejše interne mreže — glej pogovor pred to
spremembo). To ni interpolirano polje kot pri nevihtni karti — vsaka
postaja dobi svoj "bunkast" prikaz z izmerjeno vrednostjo, kot na izvorni
sliki.

Geografsko ogrodje (SLO_POLY, STATION, font) je
**uvoženo** iz tools/generate_storm_map.py, ne podvojeno — oba skripta sta
Python in si zato (drugače kot pri JS/Python paru drugod v repozitoriju)
lahko delita isto konstanto brez tveganja razhajanja.

Za razliko od nevihtne karte (ki se vgradi v obstoječo /nevihte/ prek
markerjev) ima ta karta **svojo samostojno stran** `/padavine-karta/` —
namerna odločitev (glej pogovor), ker gre za drugačno vrsto podatka
(izmerjeno, ne napovedano) in drugačno temo (padavine, ne nevihtni
potencial). Stran se v celoti prigenerira vsak dan (kot klimatološke hub
strani v seo_smart_routine.py), ne prek rezerviranih markerjev — nima
ročno urejane vsebine, ki bi jo bilo treba ohraniti med teki.

Piše:
  og/precip-map/<datum>.jpg        — različica za objavo (1080×1350, feed)
  og/precip-map/<datum>-story.jpg  — različica za zgodbo (1080×1920)
  og/precip-map/latest.json        — kazalec + should_post
  padavine-karta/index.html        — javna stran

`should_post`: FB/IG feed + zgodba naj gresta ven **samo**, če je nekje v
Sloveniji v zadnjih 24h padlo vsaj OBILNO (>=30 mm) — isto načelo kot pri
nevihtni karti: vsakodnevna objava "povsod po malem" bi imela isto usodo
kot stare ARSO newsjack objave (glej CLAUDE.md, razdelek o opozorilih
ARSO — 0 sekund povprečnega časa branja).

Wired into: .github/workflows/precip-map.yml

Usage:
  python3 tools/generate_precip_map.py [--dry-run]
"""
import datetime
import html
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_storm_map import SLO_POLY, STATION, font  # noqa: E402
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
OUT_DIR = os.path.join(ROOT, "og", "precip-map")
KEEP_DAYS = 14

OBS_URL = "https://meteo.arso.gov.si/uploads/probase/www/observ/surface/text/sl/observation_si_latest.xml"

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Ljubljana")
except Exception:
    TZ = datetime.timezone.utc

# 24h mm → (oznaka, barva). Diskretni pragovi (ne gladek prehod kot pri
# nevihtni karti), ker gre za izmerjeno vrednost na točki, ne za
# interpolirano polje — vsaka postaja dobi svojo barvo/oznako.
BANDS = [
    (0,   "BREZ",        (100, 116, 139)),
    (0.1, "ŠIBKO",       (56, 189, 248)),
    (10,  "ZMERNO",      (52, 211, 153)),
    (30,  "OBILNO",      (251, 191, 36)),
    (60,  "ZELO OBILNO", (249, 115, 22)),
    (100, "EKSTREMNO",   (220, 38, 38)),
]
POST_THRESHOLD_MM = 30  # OBILNO — pod tem se FB/IG objava preskoči

WHITE, MUTED, DIM = (255, 255, 255), (208, 219, 235), (150, 163, 186)
BG_TOP, BG_BOT = (10, 8, 24), (5, 5, 12)
C_PURPLE = (167, 139, 250)

CONNECTORS = {"pri", "ob", "na", "v", "in", "pod", "nad"}


def title_sl(s):
    words = s.strip().lower().split()
    return " ".join(w if w in CONNECTORS else w.capitalize() for w in words)


def band_for(mm):
    b = BANDS[0]
    for lo, label, color in BANDS:
        if mm >= lo:
            b = (lo, label, color)
    return b[1], b[2]


def fetch_stations():
    req = urllib.request.Request(
        OBS_URL,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/xml,text/xml,*/*",
                 "Referer": "https://meteo.arso.gov.si/"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    root = ET.fromstring(data)
    issued = (root.findtext(".//tsValid_issued") or "").strip()
    out = []
    for m in root.findall("metData"):
        name = (m.findtext("domain_shortTitle") or m.findtext("domain_title") or "").strip()
        lat_s, lon_s = m.findtext("domain_lat"), m.findtext("domain_lon")
        rr_s = m.findtext("rr24h_val")
        if not name or lat_s is None or lon_s is None or rr_s is None or not rr_s.strip():
            continue
        try:
            lat, lon, mm = float(lat_s), float(lon_s), float(rr_s)
        except ValueError:
            continue
        out.append({"name": title_sl(name), "la": lat, "lo": lon, "mm": mm})
    if not out:
        raise ValueError("ARSO XML ni vrnil nobene postaje z rr24h_val")
    return out, issued


def luminance(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def draw_map(img, stations, box, bbox):
    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    min_lo, max_lo, min_la, max_la = bbox

    def to_px(lon, lat):
        return (bx0 + (lon - min_lo) / (max_lo - min_lo) * bw,
                by0 + (max_la - lat) / (max_la - min_la) * bh)

    d = ImageDraw.Draw(img)
    poly_px = [to_px(lon, lat) for lon, lat in SLO_POLY]
    d.polygon(poly_px, fill=(30, 41, 59, 130))
    d.line(poly_px, fill=(255, 255, 255, 210), width=3, joint="curve")

    sx, sy = to_px(STATION["lo"], STATION["la"])
    d.ellipse([sx - 7, sy - 7, sx + 7, sy + 7], fill=C_PURPLE, outline=WHITE, width=2)
    f_home = font("LiberationSans-Regular.ttf", 20)
    d.text((sx + 12, sy - 11), "Rečica ob Savinji", font=f_home, fill=MUTED)

    # Postajna imena namenoma niso izpisana na sami karti (referenčna slika
    # Neurje.si prav tako nosi samo številke v obročkih) — pri 20 postajah na
    # tesnem prostoru bi se besedilo prekrivalo z bližnjimi oznakami in ob
    # robu karte odrezalo (preverjeno, glej prvi izris). Imena so v razpredelnici
    # in seznamu "Postaje z največ dežja" pod karto.
    f_num = font("LiberationSans-Bold.ttf", 26)
    for s in stations:
        x, y = to_px(s["lo"], s["la"])
        label = f'{round(s["mm"])}'
        _, color = band_for(s["mm"])
        tb = d.textbbox((0, 0), label, font=f_num)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        padx, pady = 12, 8
        pw = max(tw + 2 * padx, 46)
        ph = th + 2 * pady
        x0, y0, x1, y1 = x - pw / 2, y - ph / 2, x + pw / 2, y + ph / 2
        d.rounded_rectangle([x0, y0, x1, y1], radius=ph / 2, fill=color, outline=WHITE, width=2)
        txt_fill = WHITE if luminance(color) < 150 else (20, 24, 33)
        d.text((x - tw / 2 - tb[0], y - th / 2 - tb[1]), label, font=f_num, fill=txt_fill)


def render(w, h, top, bottom, stations, summary, now, issued):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for row in range(h):
        t = row / h
        col = tuple(round(BG_TOP[k] + (BG_BOT[k] - BG_TOP[k]) * t) for k in range(3))
        gd.line([(0, row), (w, row)], fill=(*col, 255))
    img = Image.alpha_composite(img, grad)
    d = ImageDraw.Draw(img)

    pad = 70
    f_brand = font("LiberationSans-Bold.ttf", 40)
    f_date = font("LiberationSans-Regular.ttf", 26)
    f_title = font("LiberationSans-Bold.ttf", 48)
    f_sub = font("LiberationSans-Regular.ttf", 28)
    f_legend = font("LiberationSans-Bold.ttf", 19)
    f_foot = font("LiberationSans-Regular.ttf", 24)
    f_foot_b = font("LiberationSans-Bold.ttf", 28)

    y = top
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA")
    ls = 84
    logo = logo.resize((ls, ls), Image.LANCZOS)
    img.paste(logo, (pad, y), logo)
    d = ImageDraw.Draw(img)
    d.text((pad + ls + 22, y), "METEOREC", font=f_brand, fill=WHITE)
    DNI = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
    MES = ["januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust",
           "september", "oktober", "november", "december"]
    datum = f"{DNI[now.weekday()]}, {now.day}. {MES[now.month - 1]} · izdano ob {now:%H:%M}"
    d.text((pad + ls + 24, y + 46), datum, font=f_date, fill=DIM)

    y += ls + 46
    d.text((pad, y), "Padavine — zadnjih 24 ur", font=f_title, fill=WHITE)
    y += 62
    d.text((pad, y), "Izmerjeno na samodejnih postajah ARSO", font=f_sub, fill=MUTED)
    y += 52

    legend_h = 56
    foot_h = 130
    map_top = y + 14
    bottom_block_top = bottom - legend_h - foot_h - 20
    map_box_w = w - 2 * pad

    min_lo = min(p[0] for p in SLO_POLY) - 0.05
    max_lo = max(p[0] for p in SLO_POLY) + 0.05
    min_la = min(p[1] for p in SLO_POLY) - 0.05
    max_la = max(p[1] for p in SLO_POLY) + 0.05
    lat_corr = 0.69
    geo_w, geo_h = (max_lo - min_lo) * lat_corr, (max_la - min_la)
    # Slovenija je širša kot visoka -- na pokončni zgodbi bi sredinjena karta
    # pustila prazen pas nad/pod njo (isto načelo kot generate_storm_map.py:
    # render); karta je zato poravnana na vrh, preostanek do noge pa
    # zapolni seznam postaj z največ dežja namesto da bi ostal prazen.
    scale = min(map_box_w / geo_w, (bottom_block_top - map_top) / geo_h)
    bw, bh = round(geo_w * scale), round(geo_h * scale)
    bx0 = pad + (map_box_w - bw) // 2
    by0 = map_top
    draw_map(img, stations, (bx0, by0, bx0 + bw, by0 + bh), (min_lo, max_lo, min_la, max_la))
    d = ImageDraw.Draw(img)

    # Fiksna vrstična višina (berljiva pisava), ne skrčena glede na prostor —
    # prvi izris je pri malo prostora (feed, ne zgodba) stisnil vrstice pod
    # višino pisave in besedilo se je prekrivalo. Namesto tega vzame samo
    # toliko vrstic, kot jih pri tej višini dejansko gre noter.
    ROW_H = 40
    list_top = by0 + bh + 30
    header_h = 42
    avail = bottom_block_top - list_top - header_h - 16
    rows_fit = max(0, avail // ROW_H)
    n_show = min(len(stations), rows_fit * 2, 8)
    if n_show >= 2:
        f_row_lbl = font("LiberationSans-Regular.ttf", 26)
        f_row_val = font("LiberationSans-Bold.ttf", 26)
        ranked = sorted(stations, key=lambda s: -s["mm"])[:n_show]
        d.text((pad, list_top), "Postaje z največ dežja", font=f_sub, fill=MUTED)
        row_top = list_top + header_h
        n_rows = (len(ranked) + 1) // 2
        col_w = map_box_w // 2
        for i, s in enumerate(ranked):
            col, row = divmod(i, n_rows)
            rx = pad + col * col_w
            ry = row_top + row * ROW_H
            _, color = band_for(s["mm"])
            d.ellipse([rx, ry + 5, rx + 16, ry + 21], fill=color)
            d.text((rx + 26, ry), s["name"], font=f_row_lbl, fill=MUTED)
            val = f'{round(s["mm"])} mm'
            tb = d.textbbox((0, 0), val, font=f_row_val)
            d.text((rx + col_w - 40 - (tb[2] - tb[0]), ry), val, font=f_row_val, fill=WHITE)

    ly = bottom_block_top
    lx = pad
    for _, label, col in BANDS:
        d.rounded_rectangle([lx, ly, lx + 22, ly + 22], radius=5, fill=col)
        tb = d.textbbox((0, 0), label, font=f_legend)
        d.text((lx + 30, ly), label, font=f_legend, fill=MUTED)
        lx += 30 + (tb[2] - tb[0]) + 22

    fy = ly + legend_h
    d.line([(pad, fy), (w - pad, fy)], fill=(255, 255, 255, 40), width=1)
    fy += 20
    top_line = f"Največ dežja: {summary['top_name']} — {round(summary['top_mm'])} mm/24h"
    d.text((pad, fy), top_line, font=f_foot_b, fill=WHITE)
    fy += 40
    d.text((pad, fy), f"Vir: ARSO, samodejne postaje, izdano {issued}. meteorec.si/padavine-karta",
           font=f_foot, fill=DIM)

    return img.convert("RGB")


def prune_old(today):
    if not os.path.isdir(OUT_DIR):
        return []
    cutoff = today - datetime.timedelta(days=KEEP_DAYS)
    removed = []
    for name in os.listdir(OUT_DIR):
        if not name.endswith(".jpg"):
            continue
        base = name[:-4].split("-story")[0]
        try:
            d = datetime.date.fromisoformat(base)
        except ValueError:
            continue
        if d < cutoff:
            os.remove(os.path.join(OUT_DIR, name))
            removed.append(name)
    return removed


# ── Stran /padavine-karta/ ───────────────────────────────────────────────────

def esc(s):
    return html.escape(str(s or ""), quote=True)


def build_page(stations, summary, meta, now):
    ranked = sorted(stations, key=lambda s: -s["mm"])
    rows = "\n".join(
        f'      <tr><th>{esc(s["name"])}</th><td>{round(s["mm"])} mm — {band_for(s["mm"])[0].lower()}</td></tr>'
        for s in ranked
    )
    table = '  <table class="stats">\n' + rows + '\n  </table>'

    range_labels = ["0 mm", "0,1–9 mm", "10–29 mm", "30–59 mm", "60–99 mm", "100+ mm"]
    legend_html = (
        '  <ul style="list-style:none;padding:0;margin:1rem 0;display:flex;flex-wrap:wrap;gap:.5rem 1.2rem">\n'
        + "\n".join(
            f'    <li style="font-size:.85rem;color:var(--muted)"><span style="display:inline-block;'
            f'width:12px;height:12px;border-radius:3px;margin-right:.4rem;vertical-align:middle;'
            f'background:rgb{color}"></span>{label} ({rng})</li>'
            for (_lo, label, color), rng in zip(BANDS, range_labels)
        ) + "\n  </ul>"
    )

    answer = (f'  <p class="archive-intro">V zadnjih 24 urah je največ dežja po meritvah ARSO padlo v '
              f'<strong>{esc(summary["top_name"])}</strong> — {round(summary["top_mm"])} mm. Karta prikazuje '
              f'izmerjeno (ne napovedano) 24-urno kumulativo padavin na {len(stations)} samodejnih postajah ARSO '
              f'po vsej Sloveniji, izdano {esc(meta["issued"])}.</p>')

    img_html = (f'  <img src="{esc(meta["image"])}" alt="Padavine v zadnjih 24 urah po postajah ARSO, '
                f'{esc(meta["date"])}" loading="lazy" '
                f'style="width:100%;max-width:720px;border-radius:16px;display:block;margin:0 auto">')

    faq = [
        ("Od kod so podatki na karti?",
         "Uradne meritve Agencije RS za okolje (ARSO) — 24-urna kumulativa padavin na samodejnih vremenskih "
         "postajah, isti javni vir kot vreme.arso.gov.si."),
        ("Je to napoved ali izmerjena vrednost?",
         "Izmerjena vrednost — koliko dežja je dejansko padlo v zadnjih 24 urah. Za napoved padavin glej "
         "<a href=\"/vreme-recica-ob-savinji/\">napoved po urah</a> ali <a href=\"/nevihte/\">nevihtno napoved</a>."),
        ("Zakaj karta prikazuje samo ~20 postaj?",
         "To je javno objavljena nacionalna mreža glavnih samodejnih postaj ARSO. Meteorec meri lastno postajo "
         "IREICA1 v Rečici ob Savinji, ki v to nacionalno mrežo ni vključena — glej <a href=\"/\">trenutne "
         "razmere</a>."),
        ("Kako pogosto se karta osvežuje?",
         "Enkrat dnevno, zjutraj do 7:00."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Padavinska karta", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Padavinska karta Slovenije — zadnjih 24 ur</h1>
  <p class="post-meta">Izmerjene padavine na samodejnih postajah ARSO · osvežuje se dnevno · {meta["date"]}</p>
{answer}
{img_html}
{legend_html}
  <h2>Postaje po padavinah, od največ do najmanj</h2>
{table}
  <p class="muted-note">Vir podatkov: <a href="https://meteo.arso.gov.si/" target="_blank" rel="noopener">ARSO</a>,
  samodejne vremenske postaje. Karta ni uradno opozorilo ARSO — za opozorila glej
  <a href="/nevihte/">/nevihte/</a>.</p>
{faq_html}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''
    return body


def main():
    dry = "--dry-run" in sys.argv[1:]
    now = datetime.datetime.now(TZ)
    today = now.date()

    print(f"[{today}] Sestavljam padavinsko karto Slovenije …")
    try:
        stations, issued = fetch_stations()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError, ValueError) as e:
        print(f"✗ Napaka pri pridobivanju podatkov ARSO: {e}", file=sys.stderr)
        return 1

    top = max(stations, key=lambda s: s["mm"])
    summary = {"top_name": top["name"], "top_mm": top["mm"]}
    should_post = summary["top_mm"] >= POST_THRESHOLD_MM
    print(f"  → {len(stations)} postaj, največ dežja: {summary['top_name']} "
          f"({round(summary['top_mm'])} mm) — should_post={should_post}")

    if dry:
        print("(--dry-run: slike in stran niso zapisane)")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    feed = render(1080, 1350, 60, 1290, stations, summary, now, issued)
    story = render(1080, 1920, 200, 1700, stations, summary, now, issued)

    name = f"{today.isoformat()}.jpg"
    name_story = f"{today.isoformat()}-story.jpg"
    feed.save(os.path.join(OUT_DIR, name), "JPEG", quality=90)
    story.save(os.path.join(OUT_DIR, name_story), "JPEG", quality=90)
    print(f"✓ zapisano: og/precip-map/{name} + {name_story}")

    removed = prune_old(today)
    if removed:
        print(f"✓ pobrisane stare karte: {', '.join(sorted(removed))}")

    meta = {
        "date": today.isoformat(),
        "issued": issued,
        "issued_at": now.isoformat(),
        "top_station": summary["top_name"],
        "top_mm": summary["top_mm"],
        "n_stations": len(stations),
        "should_post": should_post,
        "image": f"{SITE}/og/precip-map/{name}",
        "image_story": f"{SITE}/og/precip-map/{name_story}",
    }
    with open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    body = build_page(stations, summary, meta, now)
    url = "/padavine-karta/"
    title = "Padavinska karta Slovenije — zadnjih 24 ur"
    desc = (f"Izmerjene padavine zadnjih 24 ur na {len(stations)} samodejnih postajah ARSO po vsej Sloveniji — "
            f"največ danes {summary['top_name']} ({round(summary['top_mm'])} mm). Dnevno osvežena karta.")
    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published=today.isoformat(), image=meta["image"]),
        seo.crumbs_schema([("Meteorec", "/"), ("Padavinska karta", None)]),
        seo.named_dataset_schema(
            url, "Padavinska karta Slovenije — izmerjene padavine ARSO (24h)",
            "Dnevna karta 24-urne kumulative padavin na samodejnih vremenskih postajah ARSO po vsej Sloveniji.",
            variable_measured=[{"@type": "PropertyValue", "name": "Padavine 24h", "unitText": "mm"}],
        ),
    ])
    html_out = seo.page_shell(title, desc, url, schema, body, og_image=meta["image"])
    seo.write_page("padavine-karta/index.html", html_out, force=True)
    print("  → padavine-karta/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
