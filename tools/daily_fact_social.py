#!/usr/bin/env python3
"""
tools/daily_fact_social.py — pripravi dnevno objavo "dnevno dejstvo" za FB/IG.

Isto dejstvo, ki ga tools/generate_daily_fact.py postavi na naslovnico, gre
enkrat dnevno tudi na FB stran in IG račun — tako se objavlja tudi ob dnevih,
ko dnevni članek ne nastane (članek čaka na Filipovo izbiro v jutranjem
e-mailu, objave brez izbire ni).

Dejstvo je vedno preverljivo in izračunano iz history.json (dnevni ZUNANJI
agregati postaje) — brez modela in brez /ecowitt-current, torej notranje
meritve po tej poti sploh ne morejo priti ven.

Skript samo PRIPRAVI objavo (kartica + besedilo) in nastavi izhode za
workflow; sliko mora nato workflow potisniti na main in počakati na deploy,
šele potem lahko tools/post_social.py objavi — FB in IG sliko prenašata po
javnem URL-ju.

Preskoči (skip=true), če:
  * ni dovolj podatkov za dejstvo,
  * je danes že izšel članek (blog.json[0].date == danes) — ta ima svojo
    objavo na FB/IG in dve objavi na dan sta preveč,
  * je dejstvo istega dne že bilo pripravljeno (stanje v .daily_fact_social_state.json).

Wired into: .github/workflows/daily-fact-social.yml

Usage:
  python3 tools/daily_fact_social.py            # pripravi (ali preskoči)
  python3 tools/daily_fact_social.py --dry-run  # samo izpiši, brez zapisa
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_daily_fact import dm_label, num, pick_fact, plain
from make_social_card import OUT_DIR, make_card

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_JSON = os.path.join(ROOT, "blog.json")
STATE = os.path.join(ROOT, "tools", ".daily_fact_social_state.json")
SITE = "https://meteorec.si"
TZ = ZoneInfo("Europe/Berlin")

# Koliko kartic ohranimo v og/social/ — FB in IG si sliko ob objavi prekopirata
# na svoj strežnik, zato starejših datotek ne rabimo, repozitorij pa ostane vitek.
KEEP_CARDS = 14

# Poudarek in fotka ozadja glede na tip dejstva (tools/generate_daily_fact.py).
STYLE = {
    "rekord":        ((245, 158, 11), "drought",          "🏆", "NOV REKORD"),
    "blizu-rekorda": ((249, 115, 22), "dusk-storm",       "📈", "BLIZU REKORDA"),
    "niz-moker":     ((56, 189, 248), "rain-overcast",    "🌧️", "DNEVNO DEJSTVO"),
    "niz-suh":       ((245, 158, 11), "drought",          "☀️", "DNEVNO DEJSTVO"),
    "vroc-dan":      ((239, 68, 68),  "drought",          "🌡️", "DNEVNO DEJSTVO"),
    "hladen-dan":    ((34, 211, 238), "night-fog-valley", "❄️", "DNEVNO DEJSTVO"),
    "lani":          ((77, 159, 248), "weather-station",  "📊", "DNEVNO DEJSTVO"),
}
DEFAULT_STYLE = ((77, 159, 248), "weather-station", "📊", "DNEVNO DEJSTVO")

HASHTAGS = {
    "rekord":        "#rekord #vreme",
    "blizu-rekorda": "#rekord #vreme",
    "niz-moker":     "#dez #vreme",
    "niz-suh":       "#susa #vreme",
    "vroc-dan":      "#vrocina #vreme",
    "hladen-dan":    "#mraz #vreme",
    "lani":          "#vreme #podnebje",
}


def today_iso():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def article_published_today():
    try:
        posts = json.load(open(BLOG_JSON, encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(posts) and posts[0].get("date") == today_iso()


def already_done(fact_date):
    try:
        state = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return state.get("last_fact_date") == fact_date


def stats_for(day):
    """Vrstica meritev na dnu kartice — zunanji dnevni agregati."""
    out = []
    if day.get("tempHigh") is not None:
        out.append(("Najvišja", f"{num(day['tempHigh'])} °C"))
    if day.get("tempLow") is not None:
        out.append(("Najnižja", f"{num(day['tempLow'])} °C"))
    if day.get("precipTotal") is not None:
        out.append(("Padavine", f"{num(day['precipTotal'])} mm"))
    return out


def build_caption(fact, for_instagram):
    accent, photo, icon, label = STYLE.get(fact["kind"], DEFAULT_STYLE)
    day = fact["day"]
    parts = [f"{icon} {label.capitalize()} · {dm_label(fact['date'])}", plain(fact["text"])]

    measured = ", ".join(f"{lab.lower()} {val}" for lab, val in stats_for(day))
    if measured:
        # Brez ponovne omembe postaje — dejstvo samo jo že navede.
        parts.append(f"Dan v številkah: {measured}.")

    if for_instagram:
        parts.append("Vse meritve v živo na meteorec.si (povezava je tudi v bio).")
    else:
        parts.append(f"Vse meritve v živo: {SITE}/")

    tags = HASHTAGS.get(fact["kind"], "#vreme")
    parts.append(f"#meteorec {tags} #RecicaObSavinji #ZgornjaSavinjskaDolina #IREICA1")
    return "\n\n".join(parts)


def prune_old_cards(keep_path):
    """Pobriše vse razen zadnjih KEEP_CARDS kartic dnevnega dejstva."""
    if not os.path.isdir(OUT_DIR):
        return []
    cards = sorted(f for f in os.listdir(OUT_DIR) if f.startswith("dejstvo-") and f.endswith(".jpg"))
    removed = []
    for name in cards[:-KEEP_CARDS] if len(cards) > KEEP_CARDS else []:
        path = os.path.join(OUT_DIR, name)
        if os.path.abspath(path) == os.path.abspath(keep_path):
            continue
        os.remove(path)
        removed.append(name)
    return removed


def emit(**outputs):
    """Izhodi za GitHub Actions (in v log, za ročni zagon)."""
    for key, value in outputs.items():
        print(f"{key}={value}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            for key, value in outputs.items():
                fh.write(f"{key}={value}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="izpiši besedilo objave, brez kartice in brez zapisa stanja")
    ap.add_argument("--force", action="store_true",
                    help="pripravi tudi, če je dan že obdelan ali je danes izšel članek")
    ap.add_argument("--caption-dir", default=tempfile.gettempdir())
    args = ap.parse_args()
    caption_dir = args.caption_dir or tempfile.gettempdir()

    fact = pick_fact()
    if fact is None:
        print("Premalo podatkov za dnevno dejstvo — brez objave.")
        emit(skip="true")
        return 0

    if not args.force:
        if article_published_today():
            print("Danes je že izšel članek (ta ima svojo objavo na FB/IG) — brez objave dejstva.")
            emit(skip="true")
            return 0
        if already_done(fact["date"]):
            print(f"Dejstvo za {fact['date']} je že bilo objavljeno — brez ponovne objave.")
            emit(skip="true")
            return 0

    caption_fb = build_caption(fact, for_instagram=False)
    caption_ig = build_caption(fact, for_instagram=True)

    if args.dry_run:
        print("\n--- Facebook ---\n" + caption_fb)
        print("\n--- Instagram ---\n" + caption_ig)
        return 0

    accent, photo, _, label = STYLE.get(fact["kind"], DEFAULT_STYLE)
    card_rel = f"og/social/dejstvo-{fact['date']}.jpg"
    make_card(os.path.join(ROOT, card_rel),
              headline=plain(fact["text"]),
              badge=f"{label} · {dm_label(fact['date']).upper()}",
              stats=stats_for(fact["day"]),
              accent=accent,
              photo=photo)

    removed = prune_old_cards(os.path.join(ROOT, card_rel))
    if removed:
        print(f"Pobrisane stare kartice: {', '.join(removed)}")

    fb_path = os.path.join(caption_dir, "dejstvo_fb.txt")
    ig_path = os.path.join(caption_dir, "dejstvo_ig.txt")
    open(fb_path, "w", encoding="utf-8").write(caption_fb)
    open(ig_path, "w", encoding="utf-8").write(caption_ig)

    json.dump({"last_fact_date": fact["date"], "kind": fact["kind"],
               "prepared_at": datetime.now(TZ).isoformat(timespec="seconds")},
              open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    emit(skip="false",
         card_path=card_rel,
         image_url=f"{SITE}/{card_rel}",
         caption_fb=fb_path,
         caption_ig=ig_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
