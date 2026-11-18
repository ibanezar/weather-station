#!/usr/bin/env python3
"""
tools/send_dolina_v_tednu.py — pošlje zadnji tedenski povzetek »Dolina v tednu« potrjenim naročnikom (prek workerja).

Vzame najnovejši zapis iz data/dolina-v-tednu.json, sestavi e-pošto (`generate_dolina_v_tednu.email_html`) in jo pošlje na
`POST /tedenski/poslji`. Worker pošlje en teden samo enkrat (KV), zato je ponovni zagon varen. Brez skrivnosti (`NOTIFY_SECRET`)
konča z napako in ne pošlje ničesar. Zapis tedna mora biti današnji ali iz zadnjih 9 dni (stari povzetek se ne pošlje).

Poganja ga `.github/workflows/dolina-v-tednu.yml`, samo če je nastavljena repozitorijska spremenljivka `TEDENSKI_POSLJI=true`
(privzeto izklopljeno, dokler lastnik ne potrdi pošiljanja in ni nastavljen Resend).

Usage:
    python3 tools/send_dolina_v_tednu.py [--dry-run] [--force]
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_dolina_v_tednu as G  # noqa: E402

WORKER = "https://weatherireica1.filip-eremita.workers.dev"
# Cloudflare zavrne privzeti »Python-urllib« User-Agent s 403 (glej tools/test_worker_ua.py).
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
MAX_AGE_DAYS = 9


def latest_record(path=G.DATA, today=None):
    today = today or datetime.date.today()
    data = json.load(open(path, encoding="utf-8"))
    if not data:
        raise SystemExit("Ni zapisa tedna.")
    rec = data[0]
    age = (today - datetime.date.fromisoformat(rec["week_end"])).days
    if age > MAX_AGE_DAYS:
        raise SystemExit(f"Zadnji zapis ({rec['week_start']}) je star {age} dni: povzetka ne pošljem.")
    return rec


def payload(rec, secret, force=False):
    p = {"secret": secret, "week": rec["week_start"], "subject": rec["subject"], "html": G.email_html(rec)}
    if force:
        p["force"] = True
    return p


def post(p, opener=urllib.request.urlopen):
    req = urllib.request.Request(f"{WORKER}/tedenski/poslji", data=json.dumps(p).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": WORKER_UA}, method="POST")
    with opener(req, timeout=30) as r:
        return r.status, json.load(r)


def main():
    rec = latest_record()
    secret = os.environ.get("NOTIFY_SECRET", "")
    if "--dry-run" in sys.argv:
        print(rec["subject"])
        print(G.email_html(rec))
        return 0
    if not secret:
        print("Manjka NOTIFY_SECRET (isto kot SUBSCRIBE_SECRET na workerju): nič poslano.", file=sys.stderr)
        return 1
    try:
        status, body = post(payload(rec, secret, "--force" in sys.argv))
    except urllib.error.HTTPError as e:
        print(f"Napaka {e.code}: {e.read().decode('utf-8', 'replace')[:200]}", file=sys.stderr)
        return 1
    print(f"{status}: {body}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
