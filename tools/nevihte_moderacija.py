#!/usr/bin/env python3
"""
tools/nevihte_moderacija.py — ROČNO orodje (ni v nobenem workflowu) za
moderacijo poročil o neurjih (/nevihte/porocila/, worker.js /nevihte/porocila/*).

Rabi DELETE_SECRET (isto geslo kot galerija), lokalno kot okoljska spremenljivka.

Usage:
  python3 tools/nevihte_moderacija.py list
  python3 tools/nevihte_moderacija.py odobri <id> [<id> ...]
  python3 tools/nevihte_moderacija.py zavrni <id> [<id> ...]
"""
import json
import os
import sys
import urllib.error
import urllib.request

WORKER = "https://weatherireica1.filip-eremita.workers.dev"
# Cloudflare privzeti Python-urllib zavrne s 403 (glej CLAUDE.md).
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"


def call(path, data=None):
    headers = {"Authorization": "Bearer " + os.environ["DELETE_SECRET"], "User-Agent": WORKER_UA}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(WORKER + path, data=body, headers=headers,  # WORKER_UA v headers
                                 method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Napaka {e.code}: {e.read().decode()[:200]}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "odobri", "zavrni"):
        sys.exit(__doc__)
    if sys.argv[1] == "list":
        items = call("/nevihte/porocila/cakajoca")["cakajoca"]
        if not items:
            print("Ni čakajočih poročil.")
        for i in items:
            print(f"[{i['id']}] {i['ts']}  {i['tip']} · {i['kraj']} ({i['regija']})")
            if i.get("opis"):
                print(f"    \"{i['opis']}\"")
        return
    for pid in sys.argv[2:]:
        r = call("/nevihte/porocila/moderacija", {"id": pid, "odlocitev": sys.argv[1]})
        print(pid, "→", r["status"])


if __name__ == "__main__":
    main()
