#!/usr/bin/env python3
"""
tools/ai/eval_megla_sevanje.py — ali sevanje IREICA1 pove, KDAJ se dvigne jutranja megla? (raziskava, 5. 11. 2026)

Članek o jutranji megli (`kdaj-se-dvigne-jutranja-megla-dolina-1027`) meri samo »nasičen zrak« (temperatura − rosišče ≤ 0,5 °C),
ker vidljivosti nihče ne meri. Ideja: ko se megla dvigne, sevanje skoči. Imamo 5-minutno jutranje sevanje (`data/solar-5min.csv`).

Merilo: k(t) = izmerjeno sevanje / sevanje ob jasnem nebu (Haurwitz, položaj sonca iz `sonce_horizont`). Čas »sevanje prebije« =
prvi trenutek, ko je k ≥ K_LIFT šest zaporednih točk (30 min). Primerjamo ga z urnim časom konca nasičenosti (rosišče) na dneh z meglo
ob 7. uri (nasičen zrak in veter < 3 km/h, kot v članku) in na dneh BREZ megle.

Zakaj je rezultat lahko samo OPOZORILO, ne metoda: IREICA1 prejme sonce mediano ~2 h po izračunanem prvem žarku (CLAUDE.md, »Sonce
v dolini«; domneva: senca ob senzorju). Čas, ko k preseže prag, zato vsebuje to senco, ne samo megle. Referenca je ISTA analiza na dneh
brez megle (dolžina sence brez megle): razlika med meglenimi in nemeglenimi dnevi je tisto, kar pove o megli.

Usage:
  python3 tools/ai/eval_megla_sevanje.py [--md docs/analiza-megla-sevanje.md]
"""
import csv
import datetime
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import eval_sonce as es  # noqa: E402  (load_days, minute)
import generate_seo_pages as seo  # noqa: E402  (LAT, LON)
import sonce_horizont as sh  # noqa: E402  (sun_position)
from zoneinfo import ZoneInfo  # noqa: E402

TZ = ZoneInfo("Europe/Ljubljana")
HOURLY = os.path.join(ROOT, "data", "hourly-observations.csv")
K_LIFT = 0.5
HOLD_PTS = 6
MIN_ELEV_DEG = 5.0        # pod tem je razmerje k nestabilno (model jasnega neba je tam preradodaren)
MIN_PEAK_K = 0.6          # jutro, ko sevanje nikoli ne doseže 60 % jasnega neba, je oblačno: ne ocenjujemo


def clear_sky(elev_deg):
    """Haurwitz (1945): GHI ob jasnem nebu v W/m² iz višine sonca."""
    if elev_deg <= 0:
        return 0.0
    c = math.sin(math.radians(elev_deg))
    return 1098.0 * c * math.exp(-0.057 / c)


def elevation(day, minute_local):
    h, m = divmod(int(minute_local), 60)
    dt = datetime.datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
    e, _ = sh.sun_position(seo.LAT, seo.LON, dt.timestamp())
    return float(e)


def radiation_lift(day, series):
    """Prvi trenutek (minuta dneva), ko je k ≥ K_LIFT HOLD_PTS točk zapored; None, če jutro ni jasno ali ni preboja."""
    pts = [(m, v, elevation(day, m)) for m, v in sorted(series) if m < 13 * 60]
    pts = [(m, v, e) for m, v, e in pts if e >= MIN_ELEV_DEG]
    ks = [(m, v / clear_sky(e)) for m, v, e in pts]
    if len(ks) < HOLD_PTS or max(k for _, k in ks) < MIN_PEAK_K:
        return None, None
    for i in range(len(ks) - HOLD_PTS + 1):
        if all(ks[i + j][1] >= K_LIFT for j in range(HOLD_PTS)):
            return ks[i][0], round(max(k for _, k in ks), 2)
    return None, round(max(k for _, k in ks), 2)


def hourly_days(path=HOURLY):
    by = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        t = datetime.datetime.fromisoformat(r["valid_at_local"])
        by.setdefault(t.date(), {})[t.hour] = r
    return by


def dew_lift(h):
    """Kot v članku: nasičeno ob 5. uri, nato zadnja zaporedna nasičena ura do 12. Vrne (nasičeno ob 7 in mirno, minuta konca nasičenosti)."""
    sat = lambda r: float(r["temp_c"]) - float(r["dewpoint_c"]) <= 0.5
    if 5 not in h or 7 not in h or 12 not in h:
        return None
    at7 = sat(h[7]) and float(h[7]["wind_kmh"] or 0) < 3
    last = None
    if sat(h[5]):
        hr = 5
        while hr + 1 <= 12 and hr + 1 in h and sat(h[hr + 1]):
            hr += 1
        last = (hr + 1) * 60 if hr < 12 else None       # None = nasičeno še ob 12. uri (cenzurirano)
    return at7, last


def analyse():
    rad = es.load_days()
    hrs = hourly_days()
    rows = []
    for d_s, ser in sorted(rad.items()):
        d = datetime.date.fromisoformat(d_s)
        if d not in hrs:
            continue
        r = dew_lift(hrs[d])
        if r is None:
            continue
        at7, dew_end = r
        t_rad, peak = radiation_lift(d, ser)
        rows.append({"date": d_s, "fog7": at7, "dew_end": dew_end, "rad": t_rad, "peak_k": peak})
    return rows


def med(x):
    return round(statistics.median(x), 1) if x else None


def hm(m):
    return "—" if m is None else f"{int(m) // 60}.{int(m) % 60:02d}"


def report(rows):
    fog = [r for r in rows if r["fog7"]]
    nofog = [r for r in rows if not r["fog7"]]
    fog_ok = [r for r in fog if r["rad"] is not None and r["dew_end"] is not None]
    nofog_ok = [r for r in nofog if r["rad"] is not None]
    out = {"dni": len(rows), "z_meglo_ob_7": len(fog), "brez_megle": len(nofog),
           "megla_z_obema_casoma": len(fog_ok), "brez_megle_z_prebojem": len(nofog_ok),
           "brez_megle_mediana_prebija": hm(med([r["rad"] for r in nofog_ok])),
           "megla_mediana_prebija": hm(med([r["rad"] for r in fog_ok])),
           "megla_mediana_konca_nasicenosti": hm(med([r["dew_end"] for r in fog_ok]))}
    d = [r["rad"] - r["dew_end"] for r in fog_ok]
    out["razlika_prebij_minus_rosisce_min"] = med(d)
    out["razlika_mad_min"] = med([abs(x - statistics.median(d)) for x in d]) if d else None
    xs = [r["dew_end"] for r in fog_ok]
    ys = [r["rad"] for r in fog_ok]
    out["spearman"] = None
    if len(xs) >= 8:
        rank = lambda a: [sorted(a).index(v) + (a.count(v) - 1) / 2 for v in a]
        rx, ry = rank(xs), rank(ys)
        mx, my = statistics.mean(rx), statistics.mean(ry)
        num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
        den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
        out["spearman"] = round(num / den, 2) if den else None
    return out, fog_ok, nofog_ok


def main():
    global K_LIFT
    if "--k" in sys.argv:
        K_LIFT = float(sys.argv[sys.argv.index("--k") + 1])
    rows = analyse()
    if "--from" in sys.argv:                                  # npr. --from 2026-09-15: samo jesen (nizko sonce)
        rows = [r for r in rows if r["date"] >= sys.argv[sys.argv.index("--from") + 1]]
    out, fog_ok, nofog_ok = report(rows)
    print(__import__("json").dumps(out, ensure_ascii=False, indent=1))
    if "--md" in sys.argv:
        path = sys.argv[sys.argv.index("--md") + 1]
        lines = ["| datum | konec nasičenosti (rosišče) | sevanje prebije | najvišji k |", "|---|---|---|---|"]
        for r in fog_ok:
            lines.append(f"| {r['date']} | {hm(r['dew_end'])} | {hm(r['rad'])} | {r['peak_k']} |")
        open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
