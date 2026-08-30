#!/usr/bin/env python3
"""
tools/log_valley_duel.py — dnevni zapis primerjave IREICA1 (Rečica ob Savinji)
in sosednje postaje Varpolje (IREICA7), ob isti uri vsak dan.

Zakaj: 30. 8. 2026 je bilo predlagano besedilo o jutranji razliki med
postajama (2,5 °C ob 8.28), a brez zgodovine primerjav ni bilo mogoče
preveriti, ali gre za redkost ali pogost pojav. generate_story_card.py to
isto primerjavo sicer računa vsako jutro za temo VALLEY_DUEL, a rezultata
nikamor ne zapiše trajno (namerno -- glej CLAUDE.md, razdelek "Sosednja
postaja Varpolje"), zato ni bilo mogoče preveriti nazaj: pregled šestih
jutranjih tekov (17., 20.-24. 8.) ni pokazal niti enega dne z razliko
>= 2 °C ob uri preverjanja (~6.40-6.50). Ta skript zgradi dejansko,
preverljivo zgodovino, preden se piše članek na podlagi vtisa.

POZOR (CLAUDE.md): ta dnevnik je diagnostično orodje za pripravo članka in
NE sme postati vhod v history.json, v učenje ali napovedovanje modela MTR,
niti na semafor /tocnost-napovedi/. IREICA1 ostaja edina referenca -- ta
dnevnik služi samo primerjavi med dvema postajama.

Piše data/valley-duel-log.csv (date, time_local, ireica1_c, varpolje_c,
diff_c, varpolje_age_min). Doda kvečjemu eno vrstico na dan, obstoječih ne
prepiše -- isto načelo kot log_hourly_observations.py.

Usage:
  python3 tools/log_valley_duel.py
"""
import csv
import datetime
import json
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "data", "valley-duel-log.csv")
FIELDS = ["date", "time_local", "ireica1_c", "varpolje_c", "diff_c", "varpolje_age_min"]
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
TZ = ZoneInfo("Europe/Ljubljana")


def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "meteorec-valley-duel-log/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_ireica1():
    """Trenutna zunanja temperatura IREICA1. Blok indoor se v odgovor sploh ne
    vrne (izbrisan pri viru v workerju, CLAUDE.md) -- tu ni kaj dodatno
    odstraniti, samo pravilno prebrati zunanjo vrednost."""
    try:
        data = fetch_json(f"{WORKER}/ecowitt-current")
        payload = data.get("data") or {}
        val = ((payload.get("outdoor") or {}).get("temperature") or {}).get("value")
        return float(val) if val is not None else None
    except Exception as e:
        print(f"⚠ IREICA1 ni dosegljiva: {e}", file=sys.stderr)
        return None


def fetch_varpolje():
    try:
        data = fetch_json(f"{WORKER}/varpolje-current")
        temp = (data.get("current") or {}).get("temp_c")
        if temp is None:
            return None, None
        age_min = None
        upd = data.get("updated_utc")
        if upd:
            stamp = datetime.datetime.fromisoformat(upd.replace("Z", "+00:00"))
            age_min = (datetime.datetime.now(datetime.timezone.utc) - stamp).total_seconds() / 60
        return float(temp), age_min
    except Exception as e:
        print(f"⚠ Varpolje ni dosegljiva: {e}", file=sys.stderr)
        return None, None


def load_existing():
    rows, seen_dates = [], set()
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                seen_dates.add(row["date"])
    return rows, seen_dates


def save(rows):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    now = datetime.datetime.now(TZ)
    today = now.date().isoformat()
    rows, seen = load_existing()

    if today in seen:
        print(f"{today} je že zabeležen, preskačem zajem.")
        return

    ireica1 = fetch_ireica1()
    varpolje, age_min = fetch_varpolje()

    if ireica1 is None or varpolje is None:
        print("⚠ Manjka meritev ene od postaj, vrstice ne dodajam.", file=sys.stderr)
        return

    diff = round(ireica1 - varpolje, 1)
    rows.append({
        "date": today,
        "time_local": now.strftime("%H:%M"),
        "ireica1_c": ireica1,
        "varpolje_c": varpolje,
        "diff_c": diff,
        "varpolje_age_min": round(age_min, 1) if age_min is not None else "",
    })
    save(rows)
    print(f"✓ {today} {now.strftime('%H:%M')}: IREICA1 {ireica1} °C, Varpolje {varpolje} °C, "
          f"razlika {diff:+.1f} °C ({len(rows)} vrstic skupaj).")


if __name__ == "__main__":
    main()
