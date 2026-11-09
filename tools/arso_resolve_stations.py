#!/usr/bin/env python3
"""
tools/arso_resolve_stations.py -- enkraten preizkus: katera arhivska ID-ja sta ARSO postaji Gornji Grad (GORNJ-GRA) in
Radegunda (METEO-16036)? Teče samo v Actions (meteo.arso.gov.si iz peskovnika ni dosegljiv).

1. Seznam trenutnih opazovanj ARSO (z imeni, koordinatami in oznakami postaj): poišče Gornji Grad in Radegundo.
2. Arhiv data.xml (padavine 85, višina odeje 88, novi sneg 89) za številčni del oznak in za druge oblike zapisa.
Rezultat: arso-resolve-out/report.md in surovi odgovori; dnevne serije najdenih postaj v data/arso-sneg-postaje/.
Vir podatkov: Agencija Republike Slovenije za okolje. Notranjih meritev ne bere.
"""
import datetime as dt
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arso_snow_stations as a  # noqa: E402

OUT = os.path.join(a.ROOT, "arso-resolve-out")
OBS_LISTS = [
    "/uploads/probase/www/observ/surface/text/sl/observationAms_si_latest.xml",
    "/uploads/probase/www/observ/surface/text/sl/observation_si_latest.xml",
    "/uploads/probase/www/observ/surface/text/sl/observationAms_GORNJ-GRA__history.html",
    "/uploads/probase/www/observ/surface/text/sl/observationAms_GORNJ-GRA_history.html",
    "/uploads/probase/www/observ/surface/text/sl/observationAms_GORNJ-GRA__latest.html",
    "/uploads/probase/www/observ/surface/text/sl/observationAms_METEO-16036_history.html",
    "/uploads/probase/www/observ/surface/text/sl/observationAms_METEO-16036_latest.html",
    "/uploads/probase/www/observ/surface/text/sl/observationAms_METEO-16036__history.html",
]
STATION_IDS = ("GORNJ-GRA_", "RADEG-NDA_")
NAMES = ("gornji grad", "radegunda", "gornj-gra", "16036")
ID_FORMS = ["16036", "METEO-16036", "METEO-16036_", "GORNJ-GRA", "GORNJ-GRA_", "gornj-gra"]


def show_fields(tx, sid, rep):
    """Izpiše neprazna polja bloka <metData> postaje (kaj postaja sploh meri)."""
    for blk in re.findall(r"<metData>(.*?)</metData>", tx, flags=re.S):
        if f"<domain_meteosiId>{sid}</domain_meteosiId>" not in blk:
            continue
        fields = re.findall(r"<(\w+)>([^<]+)</\1>", blk)
        keep = [(k, v) for k, v in fields if not k.endswith(("_desc", "_unit", "_RFC822", "_UTC")) and k not in
                ("domain_title", "domain_shortTitle", "sunrise", "sunset")]
        line = "; ".join(f"{k}={v}" for k, v in keep)
        print(f"[polja {sid}] {line}")
        rep += ["", f"### polja `{sid}`", "```", line[:3000], "```"]
        return
    print(f"[polja {sid}] ni bloka")


def scan_range(lo, hi, batch, rep):
    """Arhivski ID-ji nad 5500: poišči postaje s padavinami, skladnimi z IREICA1 (kot scan_by_correlation)."""
    hist = json.load(open(os.path.join(a.ROOT, "history.json"), encoding="utf-8"))
    ours = {d: v["precipTotal"] for d, v in hist.items() if v.get("src") != "era5" and v.get("precipTotal") is not None}
    cands = []
    for start in range(lo, hi, batch):
        ids = ",".join(str(i) for i in range(start, min(start + batch, hi)))
        st, tx = a.data_xml(ids, "2024-11-01", "2025-03-31", vars_="85,88,89")
        time.sleep(a.PAUSE_S)
        if st != 200 or not tx:
            print(f"[razpon] {start}: HTTP {st}")
            continue
        for sid, series in a.parse_multi(tx).items():
            vals = [v for v in series.values() if v[0] is not None]
            if len(vals) < 60:
                continue
            r, shift, n = a.station_precip_corr(series, ours)
            snow = sum(1 for v in series.values() if v[1] is not None or v[2] is not None)
            print(f"[razpon] id {sid}: dni s padavinami {len(vals)}, r={r}, zamik {shift}, dni s poljem snega {snow}")
            cands.append({"id": sid, "r": r, "shift": shift, "n": n, "snow_field": snow})
    rep += ["", f"## Arhivski ID-ji {lo}..{hi}", "", f"postaj s podatkom: {len(cands)}", "```", json.dumps(cands, ensure_ascii=False)[:3000], "```"]
    return cands


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = ["# ARSO: Gornji Grad in Radegunda", ""]
    for p in OBS_LISTS:
        st, tx = a.get(p)
        print(f"[seznam] {p} -> HTTP {st}, {len(tx)} znakov")
        rep.append(f"- `{p}`: HTTP {st}, {len(tx)} znakov")
        time.sleep(a.PAUSE_S)
        if st != 200 or not tx:
            continue
        with open(os.path.join(OUT, re.sub(r"\W+", "_", p)[-80:] + ".txt"), "w", encoding="utf-8") as f:
            f.write(tx)
        if p.endswith("observationAms_si_latest.xml"):
            for sid in STATION_IDS:
                show_fields(tx, sid, rep)
        low = tx.lower()
        for n in NAMES:
            for m in re.finditer(re.escape(n), low):
                s = max(0, m.start() - 300)
                chunk = re.sub(r"\s+", " ", tx[s:m.end() + 700])
                print(f"   [{n}] ...{chunk}")
                rep += ["", f"### zadetek `{n}`", "```", chunk[:1000], "```"]
                break
    d1, d2 = "2024-11-01", "2025-03-31"
    rep += ["", "## Arhiv data.xml", ""]
    found = []
    for form in ID_FORMS:
        st, tx = a.data_xml(form, d1, d2)
        time.sleep(a.PAUSE_S)
        multi = a.parse_multi(tx) if st == 200 else {}
        sizes = {k: len(v) for k, v in multi.items()}
        print(f"[arhiv] id={form} -> HTTP {st}, {len(tx)} znakov, postaje {sizes}, začetek: {re.sub(chr(10), ' ', tx[:200])}")
        rep.append(f"- id=`{form}`: HTTP {st}, {len(tx)} znakov, postaje/dnevi {sizes}")
        for k, series in multi.items():
            if len(series) >= 30:
                found.append((form, k))
    scan_range(5500, 20000, 150, rep)
    results = []
    for form, k in dict.fromkeys(found):
        st, tx = a.data_xml(form, a.FIRST_DATE, dt.date.today().isoformat())
        time.sleep(a.PAUSE_S)
        series = (a.parse_multi(tx) if st == 200 else {}).get(k) or {}
        days = [[d, v[1], v[2], v[0]] for d, v in sorted(series.items())]
        cov = a.coverage(days)
        print(f"[postaja {form}->{k}] {cov}")
        rep.append(f"- **{form}** (ključ {k}): {json.dumps(cov, ensure_ascii=False)}")
        results.append({"form": form, "key": k, "coverage": cov})
        if days:
            safe = re.sub(r"\W+", "_", k)
            with open(os.path.join(OUT, f"daily-{safe}.json"), "w", encoding="utf-8") as f:
                json.dump({"fields": ["date", "snow_depth_cm", "new_snow_cm", "precip_mm"], "days": days}, f,
                          ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
