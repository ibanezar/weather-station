#!/usr/bin/env python3
"""
Ali so živa osvežitev MTR čez dan (mtr-live.yml) boljše od jutranje zamrznjene napovedi?

  eval_live_refresh.py [LOG.csv] [forecast_verification.json]

Dnevnik: data/mtr-live-log.csv (predict_recica_mos.py --live, od 24. 10. 2026). Zamrznjena napoved in
meritev sta v forecast_verification.json (`meteorec`, `actual`). Za vsak ciljni dan se vzame zadnja
osvežitev v razredu `hours_before` (ure od izdaje do začetka dneva po lokalnem času) in primerja z
zamrznjeno napovedjo NA ISTIH dneh: MAE, uparjena razlika in 7-dnevni blokovni bootstrap (kot eval_mtr3).
Čisti Python (brez numpy), da ga lahko uvozi test v parity.yml.

Pazi:
  - model je naučen na jutranjem zajemu D+1; poznejši vhodi so svežji, a to NI naučeno in prvič se
    meri šele tu. Dobitek bi pomenil, da je svežji vhod koristen kljub temu, izguba, da popravek
    ni prenosljiv.
  - hours_before ≤ 0: dan že teče (termin 22:40 UTC, `today` je še UTC datum) — taka osvežitev vključuje
    del meritve in je POŠTENO ne primerjaj z zamrznjeno (razred je izpisan ločeno in označen).
  - pod MIN_DAYS dnevi na razred se rezultat ne razglasi (izpiše se samo »premalo dni«).
"""
import csv, json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "data", "mtr-live-log.csv")
VER = os.path.join(ROOT, "forecast_verification.json")
BUCKETS = [("že teče (≤0 h)", None, 0), ("0–6 h", 0, 6), ("6–12 h", 6, 12), ("12–18 h", 12, 18),
           ("18–24 h", 18, 24), ("24–36 h", 24, 36), (">36 h", 36, 10 ** 6)]
MIN_DAYS, BLOCK, REPS = 20, 7, 2000


def bucket_of(h):
    for name, lo, hi in BUCKETS:
        if (lo is None or h > lo) and h <= hi:
            return name
    return None


def boot(diffs, rng):
    """Povprečje in 95 % interval blokovnega bootstrapa (diffs v časovnem vrstnem redu)."""
    n = len(diffs)
    blk = min(BLOCK, n)
    means = []
    for _ in range(REPS):
        xs = []
        while len(xs) < n:
            s = rng.randrange(0, n - blk + 1)
            xs += diffs[s:s + blk]
        means.append(sum(xs[:n]) / n)
    means.sort()
    return sum(diffs) / n, means[int(0.025 * REPS)], means[int(0.975 * REPS) - 1]


def analyze(log_rows, verification):
    """{razred: {cilj: {n, mae_live, mae_frozen, diff, lo, hi}}} za cilja tmax, tmin."""
    best = {}      # (valid_at, razred) -> vrstica z najmanjšim hours_before v razredu
    for r in log_rows:
        try:
            h = float(r["hours_before"])
        except (KeyError, TypeError, ValueError):
            continue
        b = bucket_of(h)
        key = (r["valid_at"], b)
        if b and (key not in best or h < float(best[key]["hours_before"])):
            best[key] = r
    out = {}
    rng = random.Random(7)
    for name, _, _ in BUCKETS:
        res = {}
        for tg in ("tmax", "tmin"):
            days = []
            for (v, b), r in sorted(best.items()):
                if b != name:
                    continue
                ver = verification.get(v) or {}
                act, frz = (ver.get("actual") or {}).get(tg), (ver.get("meteorec") or {}).get(tg)
                live = r.get(tg)
                if act is None or frz is None or live in (None, ""):
                    continue
                days.append((v, abs(float(live) - act), abs(frz - act)))
            if not days:
                continue
            d = [f - l for _, l, f in days]      # > 0: osvežitev boljša od zamrznjene
            row = {"n": len(days), "mae_live": sum(x[1] for x in days) / len(days),
                   "mae_frozen": sum(x[2] for x in days) / len(days)}
            if len(days) >= MIN_DAYS:
                row["diff"], row["lo"], row["hi"] = boot(d, rng)
            res[tg] = row
        if res:
            out[name] = res
    return out


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else LOG
    ver = sys.argv[2] if len(sys.argv) > 2 else VER
    if not os.path.exists(log):
        print("Dnevnika še ni — ga ustvari prva osvežitev (mtr-live.yml).")
        return 0
    with open(log, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    res = analyze(rows, json.load(open(ver, encoding="utf-8")))
    if not res:
        print(f"{len(rows)} vrstic v dnevniku, a nobenega razrešenega dne (meritev + zamrznjena napoved).")
        return 0
    print("diff = MAE(zamrznjena) − MAE(osvežitev); > 0 pomeni, da je osvežitev boljša\n")
    for name, byt in res.items():
        for tg, r in byt.items():
            if "diff" in r:
                flag = "REAL+" if r["lo"] > 0 else "WORSE" if r["hi"] < 0 else "šum"
                tail = f"diff={r['diff']:+.3f} CI[{r['lo']:+.3f},{r['hi']:+.3f}] {flag}"
            else:
                tail = f"premalo dni (< {MIN_DAYS}), ni sklepa"
            warn = "  [dan že teče — primerjava ni poštena]" if name.startswith("že teče") else ""
            print(f"{name:15s} {tg} n={r['n']:3d} MAE osvežitev={r['mae_live']:.2f} zamrznjena={r['mae_frozen']:.2f}  {tail}{warn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
