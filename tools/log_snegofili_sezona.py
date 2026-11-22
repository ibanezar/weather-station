#!/usr/bin/env python3
"""
tools/log_snegofili_sezona.py — dnevni dnevnik modelskega novega snega po točkah → data/snegofili-sezona.csv

Zakaj: Snegofili kažejo samo okno −72…+72 ur; sezonskega seštevka ni mogoče izračunati za nazaj (Open-Meteo iz peskovnika ni dosegljiv, arhiv
modelskih napovedi za te točke ne obstaja). Zato se od uvedbe naprej vsak dan zapiše, koliko snega je po modelu zapadlo v vsakem POLNEM
lokalnem dnevu. Dan, ki ga ni bilo ob nobenem teku, ostane prazen: nikoli ga ne ocenjujemo za nazaj.

Vir je snegofili/ure.json (ga piše snegofili_data.py: ista ocena kot povsod, padavine × delež snega × razmerje; serija 144 ur, 72 nazaj).
Ura z žigom T velja za T−1h … T, torej lokalni dan D sestavljajo žigi D 01:00 … D+1 00:00. Dan se zapiše šele, ko je njegov zadnji žig
res za nami (najmanj ena ura pred »zdaj«), in se prepiše z vrednostjo poznejšega teka (model nazaj popravlja).

Kar je in ni: MODELSKA ocena, ne meritev. Notranjih meritev ta skript ne bere.
Format: date,id,cm (po datumu in id). Sezona = oktober–april (lokalni mesec dneva).

Usage: python3 tools/log_snegofili_sezona.py
"""
import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOURS_PATH = os.path.join(ROOT, "snegofili", "ure.json")
OUT_PATH = os.path.join(ROOT, "data", "snegofili-sezona.csv")
SEASON_MONTHS = (10, 11, 12, 1, 2, 3, 4)
MAX_AGE_H = 36   # serija starejša od tega ni »zdajšnja«: stari ure.json ne sme pisati v dnevnik kot svež


def complete_days(now_local_iso, n_hours=144, now_index=71):
    """[(datum, i_začetek, i_konec)] za lokalne dneve, ki so v seriji CELI in se je njihov zadnji žig že iztekel (konec ≤ now_index − 1)."""
    now = datetime.datetime.fromisoformat(now_local_iso)
    t0 = now - datetime.timedelta(hours=now_index)

    def idx(t):
        d = (t - t0).total_seconds() / 3600
        return int(round(d))
    out = []
    day = (t0 + datetime.timedelta(hours=1)).date()
    while True:
        start = datetime.datetime.combine(day, datetime.time(1, 0))
        end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(0, 0))
        i0, i1 = idx(start), idx(end)
        if i1 > now_index - 1:
            break
        if i0 >= 0 and day.month in SEASON_MONTHS:
            out.append((day.isoformat(), i0, i1))
        day += datetime.timedelta(days=1)
    return out


def day_totals(series_by_id, days):
    """{(datum, id): cm}; sn je v desetinkah cm."""
    res = {}
    for sid, s in series_by_id.items():
        sn = s.get("sn") or []
        for date, i0, i1 in days:
            if i1 >= len(sn):
                continue
            seg = sn[i0:i1 + 1]
            if len(seg) != 24 or any(v is None for v in seg):
                continue
            res[(date, sid)] = round(sum(seg) / 10, 1)
    return res


def read_log(path=OUT_PATH):
    res = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    res[(r["date"], r["id"])] = float(r["cm"])
                except (ValueError, KeyError):
                    continue
    return res


def write_log(data, path=OUT_PATH):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "id", "cm"])
        for (date, sid), cm in sorted(data.items()):
            w.writerow([date, sid, f"{cm:g}"])


def main():
    if not os.path.exists(HOURS_PATH):
        print("ni snegofili/ure.json — nič za zapisati")
        return 0
    with open(HOURS_PATH, encoding="utf-8") as f:
        u = json.load(f)
    try:
        gen = datetime.datetime.strptime(u["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        age_h = (datetime.datetime.now(datetime.timezone.utc) - gen).total_seconds() / 3600
    except (KeyError, ValueError):
        print("✗ ure.json brez veljavnega generated_at — ne zapišem nič", file=sys.stderr)
        return 0
    if age_h > MAX_AGE_H:
        print(f"ure.json je star {age_h:.0f} h — ne zapišem nič (prejšnji tek je izpadel)")
        return 0
    if not u.get("now_local") or u.get("now_index") != 71 or u.get("hours") != 144:
        print("✗ nepričakovana oblika ure.json — ne zapišem nič", file=sys.stderr)
        return 0
    days = complete_days(u["now_local"], u["hours"], u["now_index"])
    new = day_totals(u.get("tocke") or {}, days)
    if not new:
        print("ni polnih dni sezone v seriji")
        return 0
    log = read_log()
    log.update(new)
    write_log(log)
    print(f"data/snegofili-sezona.csv: {len({d for d, _ in new})} dni, {len(new)} vnosov (skupaj {len(log)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
