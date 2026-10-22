#!/usr/bin/env python3
"""
tools/anketa_rezultati.py — ROČNO orodje (ni v nobenem workflowu) za branje
anonimne ankete obiskovalcev (popup od 2. obiska, worker.js /anketa).

Rabi DELETE_SECRET (isto geslo kot galerija), lokalno kot okoljska spremenljivka.

Usage:
  python3 tools/anketa_rezultati.py          # štetje po vprašanjih + zadnji prosti odgovori
  python3 tools/anketa_rezultati.py --csv    # vsi odgovori kot CSV
"""
import csv
import json
import os
import sys
import urllib.request
from collections import Counter

WORKER = "https://weatherireica1.filip-eremita.workers.dev"
# Cloudflare privzeti Python-urllib zavrne s 403 (glej CLAUDE.md).
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
TITLES = {"q1": "Kaj jih je pripeljalo", "q2": "Kaj jim je najbolj všeč", "q3": "Kako so nas našli",
          "q5": "Aplikacija za telefon"}


def fetch():
    req = urllib.request.Request(WORKER + "/anketa/rezultati",
                                 headers={"Authorization": "Bearer " + os.environ["DELETE_SECRET"],
                                          "User-Agent": WORKER_UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["odgovori"]


def main():
    rows = fetch()
    if "--csv" in sys.argv:
        w = csv.writer(sys.stdout)
        w.writerow(["ts", "q1", "q2", "q3", "q5", "q4"])
        for r in rows:
            w.writerow([r.get("ts"), r.get("q1", ""), r.get("q2", ""), r.get("q3", ""), r.get("q5", ""), r.get("q4", "")])
        return
    print(f"Odgovorov: {len(rows)}")
    for q, title in TITLES.items():
        c = Counter(r[q] for r in rows if r.get(q))
        print(f"\n{title} (n={sum(c.values())}):")
        for k, n in c.most_common():
            print(f"  {k:<10} {n}")
    free = [r for r in rows if r.get("q4")]
    print(f"\nKaj manjka (zadnjih {min(20, len(free))} od {len(free)}):")
    for r in free[:20]:
        print(f"  [{r['ts'][:10]}] {r['q4']}")


if __name__ == "__main__":
    main()
