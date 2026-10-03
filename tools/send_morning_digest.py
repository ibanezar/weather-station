#!/usr/bin/env python3
"""
tools/send_morning_digest.py — sestavi in pošlji jutranji povzetek kot potisno
obvestilo naročnikom, ki so ga izrecno vklopili (glej "🌅 Jutranji povzetek" v
plošči "Moja opozorila", in `digest`/`audience:"digest"` v worker.js).

Podatek za povzetek je zamrznjena napoved MTR za DANES iz `tools/.forecast_pending.json`
(ali dan z današnjim datumom v `napoved-modela.json`) — brez dodatnega omrežnega klica.
Dan se izbere po datumu, ne po `lead`: glej todays_forecast().

Ob nedosegljivem/manjkajočem modelu ali brez PUSH_SECRET konča z napako (exit
1) in ne pošlje ničesar — tišina je varnejša od napačnega ali praznega
obvestila.

Wired into:
  .github/workflows/morning-digest.yml (dvojni cron + tools/digest_gate.py,
  isti vzorec kot daily-story.yml)

Usage:
  python3 tools/send_morning_digest.py [--dry-run]
"""
import datetime, json, os, sys, urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOS = os.path.join(ROOT, "napoved-modela.json")
PENDING = os.path.join(ROOT, "tools", ".forecast_pending.json")
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
# Cloudflare zavrne privzeti »Python-urllib« User-Agent s 403 (glej tools/test_worker_ua.py).
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"


def num(x, d=0):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def today_iso():
    return datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).date().isoformat()


def todays_forecast(today):
    """Napoved MTR za DANES. Vir 1: `tools/.forecast_pending.json` (zamrznjena napoved,
    zabeležena včeraj za današnji dan; verify_forecasts.py jo razreši šele po koncu
    dneva). Vir 2: napoved-modela.json, če vsebuje današnji datum.

    Prej je bral `days[0]` (lead 1) in ga imenoval »Danes«: lead 1 je JUTRI glede na dan
    nastanka datoteke, ki nastane ob 01:35 UTC istega dne — povzetek bi poslal jutrišnje
    številke kot današnje (revizija 1. 10. 2026; poslati se še ni mogel, ker secret
    SUBSCRIBE_SECRET ni nastavljen). Brez današnjega dne se ne pošlje nič."""
    try:
        for e in json.load(open(PENDING, encoding="utf-8")):
            m = e.get("meteorec") or {}
            if e.get("target_date") == today and m.get("tmax") is not None and m.get("tmin") is not None:
                return m
    except Exception:
        pass
    try:
        mos = json.load(open(MOS, encoding="utf-8"))
        d = next((d for d in mos.get("days", []) if d.get("date") == today), None)
        if d and d.get("tmax") is not None and d.get("tmin") is not None:
            return d
    except Exception as e:
        print(f"ERROR: {MOS} ni berljiva ({e}).", file=sys.stderr)
    return None


def build_message(today=None):
    today = today or today_iso()
    fc = todays_forecast(today)
    if not fc:
        print(f"ERROR: ni napovedi MTR za današnji dan ({today}).", file=sys.stderr)
        return None

    tmax, tmin = fc["tmax"], fc["tmin"]
    pop = fc.get("pop")
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
        headers={"Content-Type": "application/json", "User-Agent": WORKER_UA},
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
