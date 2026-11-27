#!/usr/bin/env python3
"""
tools/melt_precip.py — PROTOTIP: loči »taljenje« od padavin v urnem zapisu dežemera IREICA1.

Dežemer je prekucni in (po podatkih) neogrevan: sneg, ki pade ob ≤ 0 °C, obleži v lijaku
(izmerjeno 0,0 mm), nato ga čez uro ali več stali topleje ali sonce in dežemer to zapiše kot
»dež«, ko nič ne pada (primer 26. 11. 2026: 7 ur 0,0 mm, nato 1,5 mm ob 14–15 h pri 0,7 °C in
69 W/m²). Isto velja za slano/ivje v lijaku ob jutranjem segrevanju (0,2–0,5 mm ob prvem soncu).

Razredi (na ravni UR, odločitev je na ravni »serije« zaporednih ur s padavinami):
  precip    = padavine, ki so v tisti uri res padale (dež, moker sneg, ki se tali sproti)
  melt      = verjetno taljenje snega/ivja, ki je obležalo v lijaku (ne nove padavine)
  uncertain = osamljen drobec (≤ 0,5 mm, ena ura) ponoči pri ledišču: lahko rosa/sneg, lahko ivje

Pragovi so presoja iz nekaj dogodkov (glej spodaj), zato je izhod »ocena«, ne meritev;
pravih padavin v tisti uri ne vemo (edino preverjanje: 26. 11. 2026 ob 14–17 h je bilo suho,
potrdil lastnik postaje). Notranjih meritev ne bere.

V history.json gre od 27. 11. 2026 `precipMelt` (mm taljenja v dnevu, samo razred 'melt'):
piše ga update_history.py iz 5-minutnih podatkov Ecowitt (`hours_from_ecowitt()`), `precipTotal`
ostane nespremenjen. Ta datoteka je tudi CLI za raziskovanje po urnem zapisu
data/hourly-observations.csv (tam je urna vsota malo nižja: prirastek čez mejo ure se izgubi).

Uporaba:
  python3 tools/melt_precip.py                    # zadnjih 60 dni, ure z deležem taljenja
  python3 tools/melt_precip.py --from 2026-11-24 --to 2026-11-27 -v
"""
import argparse, csv, datetime as dt, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "hourly-observations.csv")

LIQUID_T = 1.5      # °C: pri tej urni temperaturi ali več je serija padavin zanesljivo tekoča (ni taljenje)
COLD_T = 0.5        # °C: lijak je bil hladen, če je v prejšnjih COLD_HOURS urah temperatura padla na to ali pod
COLD_HOURS = 12
SUN_MIN = 10.0      # W/m²: urno povprečje sevanja, ki že segreva lijak (lijak se na soncu segreje bolj kot zrak)
GAP_HOURS = 1       # največ toliko ur brez padavin še šteje za isto serijo
SMALL_MM = 0.5      # osamljen drobec: serija skupaj ≤ tega in samo ena ura


def _f(x):
    try:
        return float(x) if x not in ("", None) else None
    except ValueError:
        return None


def load_hours(path=CSV_PATH):
    """{datetime: {t, p, s}} iz urnega zapisa (lokalni čas, polne ure)."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                ts = dt.datetime.strptime(r["valid_at_local"], "%Y-%m-%dT%H:%M")
            except (KeyError, ValueError):
                continue
            out[ts] = {"t": _f(r.get("temp_c")), "p": _f(r.get("precip_mm")) or 0.0,
                       "s": _f(r.get("solar_wm2"))}
    return out


def _runs(hours):
    """Serije ur s padavinami (> 0), vrzel do GAP_HOURS ur brez padavin ne prekine serije."""
    wet = sorted(ts for ts, v in hours.items() if v["p"] and v["p"] > 0)
    runs, cur = [], []
    for ts in wet:
        if cur and (ts - cur[-1]) > dt.timedelta(hours=GAP_HOURS + 1):
            runs.append(cur); cur = []
        cur.append(ts)
    if cur:
        runs.append(cur)
    return runs


def classify(hours):
    """{datetime: 'precip'|'melt'|'uncertain'} za vsako uro z padavinami."""
    kinds = {}
    for run in _runs(hours):
        ts0 = run[0]
        temps = [hours[t]["t"] for t in run if hours[t]["t"] is not None]
        prior = [hours[t]["t"] for t in (ts0 - dt.timedelta(hours=k) for k in range(1, COLD_HOURS + 1))
                 if t in hours and hours[t]["t"] is not None]
        total = sum(hours[t]["p"] for t in run)
        sun = any((hours[t]["s"] or 0) >= SUN_MIN for t in run)
        if not temps or any(x >= LIQUID_T for x in temps):
            kind = "precip"                      # dovolj toplo za tekoče padavine
        elif not prior or min(prior) > COLD_T:
            kind = "precip"                      # lijak ni bil hladen: ni kaj taliti
        elif sun:
            kind = "melt"                        # hladen lijak + sonce, brez toplega dežja
        elif len(run) == 1 and total <= SMALL_MM:
            kind = "uncertain"                   # ponoči pri ledišču, en drobec
        else:
            kind = "precip"                      # nočne padavine ob 0…1,5 °C (moker sneg se tali sproti)
        for t in run:
            kinds[t] = kind
    return kinds


def melt_mm_by_day(hours, kinds=None):
    """{datum: mm taljenja}. Šteje SAMO razred 'melt'; 'uncertain' ostane v padavinah (previdno)."""
    kinds = kinds if kinds is not None else classify(hours)
    out = {}
    for ts, k in kinds.items():
        if k == "melt":
            d = ts.date().isoformat()
            out[d] = out.get(d, 0.0) + hours[ts]["p"]
    return {d: round(v, 1) for d, v in out.items()}


def daily(hours, kinds):
    """{datum: {precip, melt, uncertain, hours_missing}} (mm, samo iz urnih vrednosti)."""
    days = {}
    for ts, k in kinds.items():
        d = days.setdefault(ts.date().isoformat(), {"precip": 0.0, "melt": 0.0, "uncertain": 0.0})
        d[k] = round(d[k] + hours[ts]["p"], 1)
    for d, v in days.items():
        n = sum(1 for ts in hours if ts.date().isoformat() == d)
        v["hours_missing"] = 24 - n
    return days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d0"); ap.add_argument("--to", dest="d1")
    ap.add_argument("-v", action="store_true", help="izpiši vsako uro z padavinami")
    a = ap.parse_args()
    hours = load_hours()
    last = max(hours).date()
    d1 = dt.date.fromisoformat(a.d1) if a.d1 else last
    d0 = dt.date.fromisoformat(a.d0) if a.d0 else d1 - dt.timedelta(days=60)
    kinds = classify(hours)
    if a.v:
        for ts in sorted(kinds):
            if d0 <= ts.date() <= d1:
                h = hours[ts]
                print(f"{ts:%m-%d %H:%M} {kinds[ts]:9s} {h['p']:4.1f} mm  T {h['t']}  sonce {h['s']}")
    print("\ndan         padavine  taljenje  negotovo  manjka ur")
    for d, v in sorted(daily(hours, kinds).items()):
        if d0 <= dt.date.fromisoformat(d) <= d1 and (v["melt"] or v["uncertain"] or a.v):
            print(f"{d}  {v['precip']:8.1f}  {v['melt']:8.1f}  {v['uncertain']:8.1f}  {v['hours_missing']:9d}")


if __name__ == "__main__":
    main()
