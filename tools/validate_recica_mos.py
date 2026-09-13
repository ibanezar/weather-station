#!/usr/bin/env python3
"""
tools/validate_recica_mos.py — FAZA 4 validacija izboljšav MTR (MOS).

Primerja štiri variante na ISTIH vzorcih in isti walk-forward validaciji
(train_recica_mos.walk_forward_cv, select_lambda — glej tam za metodologijo:
zaporedne mesečne rezine, učenje samo na preteklosti, regularizacija izbrana
z notranjo časovno validacijo):

  (a) surov Open-Meteo            — brez modela, om_tmax/om_tmin
  (b) obstoječi MTR                — temp_vector(..., use_bias=False, use_cond=False)
  (c) MTR + sprememba 1 (bias)     — temp_vector(..., use_bias=True,  use_cond=False)
  (d) MTR + obe spremembi          — temp_vector(..., use_bias=True,  use_cond=True)

Ločeno za Tmax/Tmin, ločeno po vodilnem času (D+1..D+3) in po letnem času.
Ne piše ničesar v model/ ali napoved-modela.json — samo bere arhiv in poroča.

Uporaba:
  python3 tools/validate_recica_mos.py
  python3 tools/validate_recica_mos.py --out data/mtr-validation-report.csv
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_recica_mos as mos  # noqa: E402

ROOT = mos.ROOT
DEFAULT_CSV = os.path.join(ROOT, "data", "mtr-validation-report.csv")
DEFAULT_MD = os.path.join(ROOT, "data", "mtr-validation-report.md")

VARIANTS = [
    ("obstojeci_MTR", False, False),
    ("MTR_sprememba1_bias", True, False),
    ("MTR_obe_spremembi", True, True),
]


def archive_rows_cached(lead, start, end, cache, no_cache=False):
    key = f"lead{lead}:{start}:{end}"
    if key in cache:
        print(f"D+{lead}: iz predpomnilnika")
        return mos._rows_from_cache(cache[key])
    print(f"D+{lead}: zajemam arhiv napovedi")
    rows = mos.fetch_archived_forecasts(lead, start, end)
    if not no_cache:
        cache[key] = mos._rows_to_cache(rows)
        mos.save_cache(cache)
    return rows


def main():
    ap = argparse.ArgumentParser(description="Validacija izboljšav MTR (walk-forward, 4 variante).")
    ap.add_argument("--from", dest="start", default=mos.TRAIN_START)
    ap.add_argument("--to", dest="end", default=None)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default=DEFAULT_CSV, help="CSV pot (privzeto data/mtr-validation-report.csv)")
    ap.add_argument("--out-md", default=DEFAULT_MD, help="Markdown pot")
    args = ap.parse_args()

    end = args.end or (mos.dt.date.today() - mos.dt.timedelta(days=1)).isoformat()
    hist = mos.load_history()
    cache = {} if args.no_cache else mos.load_cache()

    print("D+1 arhiv za pristranskost …")
    lead1_rows = archive_rows_cached(1, args.start, end, cache, args.no_cache)
    bias_series = mos.build_bias_series(lead1_rows, hist)
    print(f"  pristranskost izračunana za {len(bias_series['tmax'])} dni")

    rows_out = []  # vrstice za CSV/markdown

    for lead in mos.LEADS:
        rows = lead1_rows if lead == 1 else archive_rows_cached(lead, args.start, end, cache, args.no_cache)
        samples = mos.build_samples(rows, hist, lead, bias_series)
        if len(samples) < 200:
            print(f"⚠ D+{lead}: premalo vzorcev ({len(samples)}) — preskočeno", file=sys.stderr)
            continue
        print(f"\nD+{lead}: {len(samples)} vzorcev ({samples[0]['date']} → {samples[-1]['date']})")

        for target, om_key in (("tmax", "om_tmax"), ("tmin", "om_tmin")):
            variant_skills = {}
            for label, use_bias, use_cond in VARIANTS:
                skill = mos.walk_forward_cv(samples, target, om_key, with_aifs=False,
                                            use_bias=use_bias, use_cond=use_cond)
                variant_skills[label] = skill
                if skill:
                    print(f"  {target} D+{lead} {label}: MAE {skill['mae_meteorec']} °C "
                          f"(OM {skill['mae_open_meteo']} °C, {skill['improvement_pct']:+.1f} %)")
                else:
                    print(f"  {target} D+{lead} {label}: ni bilo mogoče oceniti (premalo zgodovine)")

            base = next((s for s in variant_skills.values() if s), None)
            if base is None:
                continue

            # (a) surov Open-Meteo — enak za vse variante, en zapis na (target, lead, rezina)
            def om_row(slice_name, skill_dict):
                rows_out.append({
                    "target": target, "lead": lead, "slice": slice_name, "variant": "a_surov_open_meteo",
                    "n": skill_dict["n"], "mae": skill_dict["mae_open_meteo"],
                    "rmse": skill_dict["rmse_open_meteo"], "skill_vs_om": 0.0,
                })

            om_row("celotno_obdobje", base)
            for season, sd in base.get("per_season", {}).items():
                om_row(season, sd)

            for label, _, _ in VARIANTS:
                skill = variant_skills[label]
                if not skill:
                    continue
                om_mae = skill["mae_open_meteo"]
                rows_out.append({
                    "target": target, "lead": lead, "slice": "celotno_obdobje", "variant": label,
                    "n": skill["n"], "mae": skill["mae_meteorec"], "rmse": skill["rmse_meteorec"],
                    "skill_vs_om": round(1 - skill["mae_meteorec"] / om_mae, 3) if om_mae else None,
                })
                for season, sd in skill.get("per_season", {}).items():
                    s_om_mae = sd["mae_open_meteo"]
                    rows_out.append({
                        "target": target, "lead": lead, "slice": season, "variant": label,
                        "n": sd["n"], "mae": sd["mae_meteorec"], "rmse": sd["rmse_meteorec"],
                        "skill_vs_om": round(1 - sd["mae_meteorec"] / s_om_mae, 3) if s_om_mae else None,
                    })

    # ── Izpis in shranjevanje ────────────────────────────────────────────────
    cols = ["target", "lead", "slice", "variant", "n", "mae", "rmse", "skill_vs_om"]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_out)
    print(f"\n→ {os.path.relpath(args.out, ROOT)}: {len(rows_out)} vrstic")

    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("# MTR — validacija izboljšav (walk-forward)\n\n")
        f.write(f"Obdobje: {args.start} → {end}. Metodologija: `train_recica_mos.walk_forward_cv` "
                f"(zaporedne mesečne rezine, {mos.OUTER_FOLDS} zunanjih, učenje samo na preteklosti; "
                f"regularizacija izbrana z notranjo časovno validacijo, `select_lambda`).\n\n")
        f.write("| cilj | vodilni čas | rezina | varianta | n | MAE °C | RMSE °C | veščina proti OM |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in rows_out:
            sv = f"{r['skill_vs_om']:.1%}" if r["skill_vs_om"] is not None else ""
            f.write(f"| {r['target']} | D+{r['lead']} | {r['slice']} | {r['variant']} | {r['n']} | "
                    f"{r['mae']} | {r['rmse']} | {sv} |\n")
    print(f"→ {os.path.relpath(args.out_md, ROOT)}")

    # ── Opozorilo o poslabšanju (PRAVILA: ne objavi, javi in počakaj) ────────
    regressions = []
    by_key = {}
    for r in rows_out:
        by_key.setdefault((r["target"], r["lead"], r["slice"]), {})[r["variant"]] = r
    for (target, lead, slc), variants in by_key.items():
        prev = variants.get("obstojeci_MTR")
        for label in ("MTR_sprememba1_bias", "MTR_obe_spremembi"):
            cur = variants.get(label)
            if prev and cur and cur["mae"] > prev["mae"]:
                regressions.append(f"{target} D+{lead} [{slc}]: {label} MAE {cur['mae']} > "
                                   f"obstoječi MTR MAE {prev['mae']}")
    if regressions:
        print(f"\n⚠ POSLABŠANJE pri {len(regressions)} celicah — glej {os.path.relpath(args.out_md, ROOT)}:")
        for r in regressions[:20]:
            print(f"   - {r}")
        print("  Pravilo: tega NE objavi. Počakaj na odločitev, preden zaženeš train_recica_mos.py "
              "z --use-bias/--use-cond za produkcijo.")
    else:
        print("\n✓ Nobene celice s poslabšanjem proti obstoječemu MTR.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
