#!/usr/bin/env python3
"""
Analiza poplav 3.–6. avgusta 2023 iz podatkov postaje IREICA1 + primerjava z 2026.

Poseben primer: history.json za 3.–6. avgust 2023 NIMA zapisov (postaja je bila
med ujmo brez povezave). Dnevnih vsot za te štiri dni ni mogoče obnoviti iz
dnevnih zapisov, PAČ PA iz kumulativnih števcev dežemera (tedenski/mesečni/letni),
ki so tekli naprej in so bili ob vrnitvi postaje na omrežje pravilni.

    python3 tools/analiza_poplave_2023.py

Skripta ne spreminja nobene datoteke — samo izpiše številke.
"""
import json
import os
import datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "history.json")
XLSX = os.path.join(ROOT, "all_Rečiškapstaja(201901010000-202605240925).xlsx")

# Kumulativni števci dežemera, prebrani iz Ecowitt izvoza (stolpci Weekly/Monthly/
# Yearly). Vrednost v vrstici za dan D je stanje števca ob ~2.00 naslednjega dne,
# torej kumulativa do konca dneva D.
COUNTERS = {
    # dan:        (dnevno, tedensko, mesečno, letno)
    "2023-08-02": (0.0, 52.9, 31.0, 5126.3),
    "2023-08-07": (0.3, 4.1, 288.3, 5383.6),
}

YEARS = range(2020, 2027)


def load():
    with open(HIST, encoding="utf-8") as f:
        return json.load(f)


def rain(h, d):
    r = h.get(d)
    return None if r is None else r.get("precipTotal")


def total(h, a, b):
    """Vsota padavin med a in b (vključno), brez manjkajočih dni."""
    return sum(v["precipTotal"] for k, v in h.items() if a <= k <= b)


def rolling(h, end, n):
    e = dt.date.fromisoformat(end)
    s, miss = 0.0, 0
    for i in range(n):
        v = rain(h, (e - dt.timedelta(days=i)).isoformat())
        if v is None:
            miss += 1
        else:
            s += v
    return s, miss


def api(h, end, k=0.92, n=120):
    """Indeks predhodne namočenosti — vsota padavin z eksponentnim upadanjem."""
    e = dt.date.fromisoformat(end)
    s = 0.0
    for i in range(n):
        v = rain(h, (e - dt.timedelta(days=i)).isoformat())
        if v:
            s += v * (k ** i)
    return s


def h1(t):
    print("\n" + "═" * 78)
    print(t)
    print("═" * 78)


def main():
    h = load()
    days = sorted(h)

    h1("1 — VRZEL V NIZU IN OBNOVITEV IZ ŠTEVCEV DEŽEMERA")
    gap = [f"2023-08-{d:02d}" for d in range(1, 9)]
    for d in gap:
        v = rain(h, d)
        print(f"  {d}  " + ("NI ZAPISA (postaja brez povezave)" if v is None else f"{v:6.1f} mm"))

    d2, d7 = COUNTERS["2023-08-02"], COUNTERS["2023-08-07"]
    mesecno = d7[2] - d2[2]          # prirast mesečnega števca 3.–7. 8.
    letno = d7[3] - d2[3]            # neodvisna kontrola z letnim števcem
    dogodek = mesecno - d7[0]        # odštejemo dež 7. 8.
    # Tedenski števec se ponastavi v soboto; 5. 8. 2023 je bila sobota,
    # zato tedenska vrednost 7. 8. pokriva 5.–7. avgust.
    peti_sesti = d7[1] - d7[0]
    tretji_cetrti = dogodek - peti_sesti

    print(f"\n  mesečni števec  2. 8. = {d2[2]:7.1f} mm → 7. 8. = {d7[2]:7.1f} mm   (prirast {mesecno:6.1f} mm)")
    print(f"  letni števec    2. 8. = {d2[3]:7.1f} mm → 7. 8. = {d7[3]:7.1f} mm   (prirast {letno:6.1f} mm)")
    print(f"  → števca se ujemata na {abs(mesecno - letno):.1f} mm — vrednost je zanesljiva")
    print(f"\n  3.–6. avgust 2023 skupaj      {dogodek:6.1f} mm")
    print(f"    od tega 5.–6. avgust        {peti_sesti:6.1f} mm   (iz tedenskega števca)")
    print(f"    → 3.–4. avgust (noč ujme)   {tretji_cetrti:6.1f} mm")

    avg_znano = total(h, "2023-08-01", "2023-08-31")
    print(f"\n  avgust 2023 skupaj = {avg_znano:.1f} (zabeleženi dnevi) + {dogodek:.1f} = {avg_znano + dogodek:.1f} mm")
    leto = total(h, "2023-01-01", "2023-12-31")
    print(f"  leto 2023 skupaj   = {leto:.1f} + {dogodek:.1f} = {leto + dogodek:.1f} mm")

    h1("2 — KAKO IZJEMEN JE DOGODEK V NIZU POSTAJE")
    top = sorted(((v["precipTotal"], k) for k, v in h.items()), reverse=True)[:8]
    print("  Največje dnevne vsote v celotnem nizu (brez vrzeli 3.–6. 8. 2023):")
    for v, k in top:
        print(f"    {k}  {v:6.1f} mm")
    dvo = []
    for i in range(1, len(days)):
        a, b = days[i - 1], days[i]
        if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days == 1:
            dvo.append((h[a]["precipTotal"] + h[b]["precipTotal"], a))
    najv2 = max(dvo)
    print(f"\n  Največja dvodnevna vsota (brez ujme): {najv2[0]:.1f} mm ({najv2[1]} +1 dan)")
    print(f"  Ujma 3.–4. 8. 2023:                  {tretji_cetrti:.1f} mm  →  {tretji_cetrti / najv2[0]:.1f}× več")

    h1("3 — PREDHODNA NAMOČENOST PRED 3. AVGUSTOM")
    print("  leto  datum        7 dni   14 dni   30 dni   60 dni   90 dni     API")
    for y in YEARS:
        end = f"{y}-08-02" if y < 2026 else "2026-07-29"
        cols = []
        for n in (7, 14, 30, 60, 90):
            s, m = rolling(h, end, n)
            cols.append(f"{s:7.1f}")
        print(f"  {y}  {end}  " + " ".join(cols) + f"  {api(h, end):7.1f}")
    print("\n  (2026 je odrezan na 29. 7., ker novejših meritev v nizu še ni)")

    h1("4 — MESEČNE VSOTE: 2023 IN 2026 PROTI POVPREČJU")
    print("  mesec   2023      2026    povpr. 2020–2025   2026 / povpr.")
    for m in range(1, 13):
        v23 = total(h, f"2023-{m:02d}-01", f"2023-{m:02d}-31")
        if m == 8:
            v23 += dogodek
        v26 = total(h, f"2026-{m:02d}-01", f"2026-{m:02d}-31")
        hist = [total(h, f"{y}-{m:02d}-01", f"{y}-{m:02d}-31") for y in range(2020, 2026)]
        avg = sum(hist) / len(hist)
        pct = f"{100 * v26 / avg:5.0f} %" if v26 else "    —"
        print(f"    {m:02d}   {v23:6.1f}   {v26:6.1f}          {avg:6.1f}        {pct}")

    h1("5 — POLETNA BILANCA 1. JUNIJ → 29. JULIJ")
    for y in YEARS:
        print(f"    {y}: {total(h, f'{y}-06-01', f'{y}-07-29'):6.1f} mm")
    jun_avg7 = total(h, "2023-06-01", "2023-07-31") + total(h, "2023-08-01", "2023-08-02") + dogodek + 0.3
    print(f"\n    2023, 1. 6. → 7. 8. (z ujmo): {jun_avg7:.1f} mm")

    h1("6 — VLAGA IN VETER: JULIJ PO LETIH")
    print("  leto  rosišče   vlaga   Tmax povpr.   najv. sunek")
    for y in YEARS:
        sel = [h[k] for k in days if k.startswith(f"{y}-07")]
        dp = [r["dewptAvg"] for r in sel if r.get("dewptAvg") is not None]
        hu = [r["humidityAvg"] for r in sel if r.get("humidityAvg") is not None]
        tx = [r["tempHigh"] for r in sel]
        wg = [r.get("windgustHigh") for r in sel if r.get("windgustHigh") is not None]
        if dp:
            print(f"  {y}  {sum(dp)/len(dp):5.1f} °C  {sum(hu)/len(hu):5.1f} %      "
                  f"{sum(tx)/len(tx):5.1f} °C      {max(wg):5.1f} km/h")

    h1("7 — 2026: KAKO SUHO JE PRED AVGUSTOM")
    d26 = [k for k in days if k.startswith("2026")]
    for thr in (1, 5, 10, 20):
        zadnji = max((k for k in d26 if h[k]["precipTotal"] >= thr), default=None)
        if zadnji:
            dni = (dt.date.fromisoformat(d26[-1]) - dt.date.fromisoformat(zadnji)).days
            print(f"    zadnji dan z ≥{thr:2d} mm: {zadnji}  ({dni} dni pred {d26[-1]})")
    streak, start, best = 0, None, []
    for k in d26:
        if h[k]["precipTotal"] < 1.0:
            streak += 1
            start = start or k
        else:
            if streak >= 7:
                best.append((streak, start, k))
            streak, start = 0, None
    if streak >= 7:
        best.append((streak, start, d26[-1]))
    print("\n    najdaljši nizi dni pod 1 mm v 2026:")
    for s, a, b in sorted(best, reverse=True)[:5]:
        print(f"      {s:3d} dni   {a} → {b}")


if __name__ == "__main__":
    main()
