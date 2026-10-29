#!/usr/bin/env python3
"""tools/ai/eval_station_bias.py — je postaja IREICA1 »topla«, ali modeli dolino podcenjujejo? (29. 10. 2026)

Vprašanje po izidu bloka »Na kratko« na /tocnost-napovedi/: vsi viri imajo pri Tmax negativno pristranskost (ARSO −4,4 °C,
WN2 −3,2, AIFS −2,1, Open-Meteo −1,2). Skript loči tri razlage iz že committanih podatkov (brez omrežja):
  1. senzor je topel      -> bi moral biti topel tudi proti sosednji postaji Varpolje (IREICA7) v istem dnu doline;
  2. modeli ne vidijo doline -> pristranskost Tmax negativna in Tmin pozitivna v VSEH mesecih (premajhen dnevni razpon), tudi pozimi;
  3. ARSO ima odmik, ne šuma -> pristranskost velika, a šum (MAE po odštetem odmiku) primerljiv z Open-Meteo.
Piše na stdout (Markdown); docs/analiza-pristranskost-postaje.md je shranjen izpis. Zaženi: python3 tools/ai/eval_station_bias.py
"""
import collections
import csv
import json
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_obs():
    H = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    return {d: (r.get("tempHigh"), r.get("tempLow")) for d, r in H.items() if r.get("src") in ("station", "wu")}


def model_bias(obs, model, lead=1):
    by = collections.defaultdict(lambda: ([], []))
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "forecast-archive.csv"), encoding="utf-8")):
        if r["model"] != model or int(r["lead_days"]) != lead:
            continue
        o = obs.get(r["valid_at"])
        if not o or o[0] is None or r["tmax_c"] == "":
            continue
        by[r["valid_at"][:7]][0].append(float(r["tmax_c"]) - o[0])
        if r["tmin_c"] != "" and o[1] is not None:
            by[r["valid_at"][:7]][1].append(float(r["tmin_c"]) - o[1])
    return by


def main():
    obs = load_obs()
    out = ["# Pristranskost postaje ali modelov? (IREICA1, D+1)\n"]
    out.append("## 1. Modeli proti postaji, D+1, vsi razrešeni dnevi\n")
    out.append("| Model | n | Tmax pristranskost | Tmax MAE | Tmin pristranskost | Mesecev s Tmax < 0 |\n|---|---|---|---|---|---|")
    for m in ("best_match", "icon_seamless", "ecmwf_ifs025", "gfs_seamless", "meteofrance_arpege_europe"):
        b = model_bias(obs, m)
        x = [v for a, _ in b.values() for v in a]
        n_ = [v for _, c in b.values() for v in c]
        neg = sum(1 for a, _ in b.values() if a and st.mean(a) < 0)
        out.append(f"| {m} | {len(x)} | {st.mean(x):+.2f} | {st.mean(abs(v) for v in x):.2f} | {st.mean(n_):+.2f} | {neg} od {len(b)} |")
    b = model_bias(obs, "best_match")
    cold = [mm for mm in b if mm[5:7] in ("12", "01", "02")]
    out.append(f"\nbest_match, **zimski meseci** (dec–feb, nizko sonce): Tmax pristranskost "
               f"{st.mean([v for mm in cold for v in b[mm][0]]):+.2f} °C, Tmin {st.mean([v for mm in cold for v in b[mm][1]]):+.2f} °C "
               f"(n = {sum(len(b[mm][0]) for mm in cold)}).")

    out.append("\n## 2. IREICA1 proti sosednji postaji Varpolje (IREICA7), čez dan\n")
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "valley-duel-log.csv"), encoding="utf-8")))
    mid = [float(r["diff_c"]) for r in rows if r["diff_c"] and 11 <= int(r["time_local"][:2]) <= 15]
    out.append(f"Opoldne (11–15 h): povprečna razlika IREICA1 − Varpolje **{st.mean(mid):+.2f} °C** (n = {len(mid)}, en zapis na dan, "
               f"od {rows[0]['date']} do {rows[-1]['date']}).")

    out.append("\n## 3. ARSO: odmik ali šum?\n")
    V = json.load(open(os.path.join(ROOT, "forecast_verification.json"), encoding="utf-8"))
    R = []
    for d, r in sorted(V.items()):
        a, o, act = r.get("arso"), r.get("open_meteo"), r.get("actual") or {}
        if a and o and None not in (a.get("tmax"), o.get("tmax"), act.get("tmax"), a.get("tmin"), o.get("tmin"), act.get("tmin")):
            R.append((a["tmax"], a["tmin"], o["tmax"], o["tmin"], act["tmax"], act["tmin"]))
    out.append(f"Dnevi, ko imata ARSO in Open-Meteo napoved: {len(R)}.\n")
    out.append("| | pristranskost | MAE | MAE po odštetem odmiku |\n|---|---|---|---|")

    def line(name, x, y):
        d = [a - b for a, b in zip(x, y)]
        m = st.mean(d)
        out.append(f"| {name} | {m:+.2f} | {st.mean(abs(v) for v in d):.2f} | {st.mean(abs(v - m) for v in d):.2f} |")
    col = lambda i: [r[i] for r in R]  # noqa: E731
    line("ARSO − meritev, Tmax", col(0), col(4))
    line("Open-Meteo − meritev, Tmax", col(2), col(4))
    line("ARSO − Open-Meteo, Tmax", col(0), col(2))
    line("ARSO − meritev, Tmin", col(1), col(5))
    line("Open-Meteo − meritev, Tmin", col(3), col(5))
    for name, sub in (("jasni dnevi (razpon ≥ 12 °C)", [r for r in R if r[4] - r[5] >= 12]), ("oblačni dnevi (razpon < 8 °C)", [r for r in R if r[4] - r[5] < 8])):
        if sub:
            out.append(f"\n{name}, n = {len(sub)}: ARSO − meritev Tmax {st.mean(r[0] - r[4] for r in sub):+.2f} °C, "
                       f"Open-Meteo − meritev {st.mean(r[2] - r[4] for r in sub):+.2f} °C.")
    print("\n".join(out))


if __name__ == "__main__":
    main()
