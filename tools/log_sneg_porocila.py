#!/usr/bin/env python3
"""
tools/log_sneg_porocila.py — dnevni arhiv agregatov poročil o snegu (18. 11. 2026).

Worker hrani poročila (`/sneg/porocila`) samo 72 ur. Za preverjanje MTR snega (verify_sneg.py) jih moramo ohraniti:
enkrat na dan (seo-smart-routine.yml, ~01:45 UTC) prenese javne AGREGATE zadnjih 24 ur in jih doda v
data/sneg-porocila-dnevno.csv (regija × pas: število poročil po stanjih in sodba). Posameznih poročil ni (jih strežnik ne objavlja).

- Datoteka je samo dopolnjena; če je od zadnjega zapisa < 20 h, se tek preskoči (cron zamuja in včasih teče dvakrat; okna se ne smejo prekrivati).
- Ob nedosegljivem workerju ali brez poročil se nič ne zapiše (izhod 0): praznine ne smemo brati kot »ni snega«.
- Poročilo bralca je neverificirano opažanje, ne meritev; tako ga tudi obravnava vsak potrošnik te datoteke.
- Notranjih meritev ne bere.

Usage:
    python3 tools/log_sneg_porocila.py
"""
import csv
import datetime
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sneg-porocila-dnevno.csv")
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
HEADER = ["izdano_utc", "ur", "regija", "pas", "n", "lezi", "pada", "dez_sneg", "brez", "sodba", "zadnje_utc"]
MIN_GAP_H = 20


def fetch(ur=24):
    req = urllib.request.Request(f"{WORKER}/sneg/porocila?ur={ur}", headers={"User-Agent": WORKER_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def rows_from(d, now, ur=24):
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    out = []
    for c in sorted(d.get("celice") or [], key=lambda c: (c["regija"], c["pas"])):
        s = c.get("stanja") or {}
        out.append([stamp, ur, c["regija"], c["pas"], c["n"], s.get("lezi", 0), s.get("pada", 0), s.get("dez-sneg", 0),
                    s.get("brez", 0), c.get("sodba") or "", c.get("zadnje", "")])
    return out


def last_stamp(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
    except OSError:
        return None
    if len(rows) < 2:
        return None
    return datetime.datetime.strptime(rows[-1][0], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)


def main(path=OUT, now=None, fetcher=fetch):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    last = last_stamp(path)
    if last and (now - last) < datetime.timedelta(hours=MIN_GAP_H):
        print(f"Preskočeno: zadnji zapis je star {(now - last).total_seconds() / 3600:.1f} h (< {MIN_GAP_H} h).")
        return 0
    try:
        d = fetcher(24)
    except Exception as e:  # noqa: BLE001
        print(f"Worker ni dosegljiv ({e}); nič zapisano.")
        return 0
    rows = rows_from(d, now)
    if not rows:
        print("V zadnjih 24 urah ni poročil; nič zapisano.")
        return 0
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HEADER)
        w.writerows(rows)
    print(f"✓ {os.path.relpath(path, ROOT)}: +{len(rows)} celic ({sum(r[4] for r in rows)} poročil)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
