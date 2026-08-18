#!/usr/bin/env python3
"""
tools/inject_arso_warnings.py — aktivna opozorila ARSO na /nevihte/.

Zakaj: doslej je vsako opozorilo dobilo svojo blog objavo. GA4 (21. 7. – 17. 8.)
pokaže, da jih nihče ne bere — 5 objav, 10 ogledov, **0 sekund** povprečnega
časa branja; v Search Consoleu skupaj en klik. Objave torej niso prinesle
obiska, so pa redčile blog (12 od 99 objav) in sitemap ter šle na FB/IG.

Opozorilo je stanje, ne novica: velja nekaj ur in se prekliče. Zato gre na
obstoječo stran /nevihte/, ki je za to tema, in ne v ločeno objavo z datumom.

Blok med markerjema WX-ARSO. Ko opozoril ni, blok to izrecno pove — prazen blok
bi bral kot okvara.

15. člen ZDMHS: kdor povzame opozorilo ARSO, mora navesti vir in čas izdaje.
Oboje ostaja v izpisu, ker je zahteva vezana na povzemanje, ne na to, kje je
povzetek objavljen. Čas izdaje in razvrstitev gradita isti funkciji kot doslej
(uvoženi iz generate_arso_newsjack_post) — ne podvajaj ju.

Wired into:
  .github/workflows/arso-newsjack.yml

Usage:
  python3 tools/inject_arso_warnings.py [--dry-run]
"""
import html
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_arso_newsjack_post import LOCAL_TZ, classify, fetch_alerts, fmt_issued

PAGE = os.path.join(ROOT, "nevihte", "index.html")
START = "<!-- WX-ARSO:START (auto: tools/inject_arso_warnings.py) -->"
END = "<!-- WX-ARSO:END -->"


def esc(s):
    return html.escape(str(s or ""), quote=True)


def sklon(n):
    """Slovenska števna oblika: ednina, dvojina, 3–4, 5+.

    Brez tega bi pisalo »je aktivnih 4 opozorila«. Odloča zadnji dve števki,
    ker 102 sledi isti obliki kot 2.
    """
    r100, r10 = n % 100, n % 10
    if r100 != 11 and r10 == 1:
        return f"je aktivno <strong>{n}</strong> opozorilo"
    if r100 not in (12, 13, 14) and r10 == 2:
        return f"sta aktivni <strong>{n}</strong> opozorili"
    if r100 not in (12, 13, 14) and r10 in (3, 4):
        return f"so aktivna <strong>{n}</strong> opozorila"
    return f"je aktivnih <strong>{n}</strong> opozoril"


def build_block(alerts, issued, now_utc):
    stamp, exact = fmt_issued(issued, now_utc)
    # Samo datum, brez ure: workflow teče vsakih 15 minut in ura v besedilu bi
    # ob vsakem zagonu ustvarila commit, tudi ko se opozorila niso spremenila
    # (~96 commitov na dan iz čistega šuma). Za svežino aktivnih opozoril je
    # merodajen čas izdaje ARSO, ki je v izpisu tako ali tako.
    checked = f"{now_utc.astimezone(LOCAL_TZ):%-d. %-m. %Y}"

    if not alerts:
        body = ('  <p class="archive-intro">Za severovzhodno Slovenijo trenutno <strong>ni '
                'aktivnih opozoril</strong> ARSO. Preverjeno '
                f'<time datetime="{now_utc.astimezone(LOCAL_TZ):%Y-%m-%d}">{checked}</time>.</p>')
    else:
        cards = []
        for a in alerts:
            cat = classify(a) or {}
            text = a.get("text") or a.get("desc") or a.get("more") or ""
            # `practical` je nasvet, kaj storiti — edino, kar je objava dodala
            # čez golo ARSO besedilo, zato ga obdržimo.
            practical = cat.get("practical", "")
            link = ""
            if cat.get("link_url") and cat.get("link_label"):
                link = (f'\n      <p class="muted-note" style="margin:.5rem 0 0">'
                        f'<a href="{esc(cat["link_url"])}">{esc(cat["link_label"])}</a></p>')
            cards.append(
                f'    <div class="card" style="margin-bottom:.9rem">\n'
                f'      <div class="clabel">{cat.get("icon", "⚠️")} '
                f'{esc(cat.get("label", "vreme"))}</div>\n'
                f'      <p class="archive-intro" style="margin:0">{esc(text) or "—"}</p>'
                + (f'\n      <p style="margin:.6rem 0 0">{practical}</p>' if practical else "")
                + link + '\n    </div>')
        body = (f'  <p class="archive-intro">Za severovzhodno Slovenijo {sklon(len(alerts))} '
                f'ARSO. Vir: Agencija RS za okolje, '
                f'{esc(stamp)}; preverjeno '
                f'<time datetime="{now_utc.astimezone(LOCAL_TZ):%Y-%m-%d}">{checked}</time>. '
                f'Uradno besedilo in opozorila za vso Slovenijo so na '
                f'<a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank" '
                f'rel="noopener">strani ARSO</a>.</p>\n'
                + "\n".join(cards))

    return (f'{START}\n'
            f'  <h2 id="opozorila">Aktivna opozorila ARSO</h2>\n'
            f'{body}\n'
            f'  {END}')


def main():
    dry = "--dry-run" in sys.argv[1:]
    if not os.path.exists(PAGE):
        print(f"ERROR: {PAGE} ne obstaja.", file=sys.stderr)
        return 1
    page = open(PAGE, encoding="utf-8").read()
    if START not in page or END not in page:
        print("ERROR: markerjev WX-ARSO ni v /nevihte/ — poženi najprej "
              "tools/generate_nevihte_page.py.", file=sys.stderr)
        return 1

    now_utc = datetime.now(timezone.utc)
    try:
        alerts, issued = fetch_alerts()
    except Exception as e:
        # Raje staro stanje kot prazna stran; workflow naj zaradi tega ne pade.
        print(f"ARSO vir ni dosegljiv ({e}) — blok ostane nespremenjen.", file=sys.stderr)
        return 0

    block = build_block(alerts, issued, now_utc)
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, page, flags=re.S)

    if dry:
        print(f"--dry-run: {len(alerts)} opozoril; "
              f"{'sprememba' if new != page else 'brez sprememb'}")
        return 0
    if new != page:
        open(PAGE, "w", encoding="utf-8").write(new)
        print(f"nevihte/index.html: {len(alerts)} aktivnih opozoril ARSO.")
    else:
        print("nevihte/index.html: opozorila brez sprememb.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
