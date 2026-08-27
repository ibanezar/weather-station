#!/usr/bin/env python3
"""
tools/send_morning_digest.py — sestavi in pošlji jutranji povzetek kot potisno
obvestilo naročnikom, ki so ga izrecno vklopili (glej "🌅 Jutranji povzetek" v
plošči "Moja opozorila", in `digest`/`audience:"digest"` v worker.js).

Podatek za povzetek je `napoved-modela.json` (MTR, `days[0]`, lead=1) —
committana datoteka, ki jo `tools/predict_recica_mos.py` osveži enkrat dnevno
v forecast-verify.yml, torej brez dodatnega omrežnega klica tu. `lead=1` je
napoved za "jutri" v trenutku nastanka (zvečer), kar je "danes" v trenutku, ko
se ta skript zjutraj požene — glej opombo pri MTR v CLAUDE.md.

Ob nedosegljivem/manjkajočem modelu ali brez PUSH_SECRET konča z napako (exit
1) in ne pošlje ničesar — tišina je varnejša od napačnega ali praznega
obvestila.

Wired into:
  .github/workflows/morning-digest.yml (dvojni cron + tools/digest_gate.py,
  isti vzorec kot daily-story.yml)

Usage:
  python3 tools/send_morning_digest.py [--dry-run]
"""
import json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOS = os.path.join(ROOT, "napoved-modela.json")
WORKER = "https://weatherireica1.filip-eremita.workers.dev"


def num(x, d=0):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def build_message():
    try:
        mos = json.load(open(MOS, encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: {MOS} ni berljiva ({e}).", file=sys.stderr)
        return None
    today = next((d for d in mos.get("days", []) if d.get("lead") == 1), None)
    if not today or today.get("tmax") is None or today.get("tmin") is None:
        print("ERROR: napoved-modela.json nima veljavnega D+1 dneva.", file=sys.stderr)
        return None

    tmax, tmin = today["tmax"], today["tmin"]
    pop = today.get("pop")
    pop_txt = f" · {round(pop * 100)} % možnost dežja" if isinstance(pop, (int, float)) else ""
    body = f"Danes {num(tmax)}° / {num(tmin)}° C{pop_txt}."
    return {
        "title": "Meteorec — jutranji povzetek",
        "body": body,
        "url": "/",
        "tag": "meteorec-digest",
    }


def main():
    dry = "--dry-run" in sys.argv[1:]
    msg = build_message()
    if msg is None:
        return 1
    print(f"Sporočilo: {msg['title']} — {msg['body']}")

    if dry:
        print("--dry-run: ne pošiljam.")
        return 0

    secret = os.environ.get("PUSH_SECRET")
    if not secret:
        print("ERROR: PUSH_SECRET ni nastavljen (GitHub secret SUBSCRIBE_SECRET, "
              "isti kot na Cloudflare Workerju).", file=sys.stderr)
        return 1

    payload = {**msg, "secret": secret, "audience": "digest"}
    req = urllib.request.Request(
        f"{WORKER}/push/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.load(r)
    except Exception as e:
        print(f"ERROR: /push/send ni uspel ({e}).", file=sys.stderr)
        return 1

    print(f"Poslano: {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
