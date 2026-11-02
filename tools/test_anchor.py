#!/usr/bin/env python3
"""tools/test_anchor.py — preizkus anchorHours() iz app.js (napoved ur zasidrana na meritev).

JS funkcija se IZREŽE iz prave datoteke (isti pomočnik kot test_parity.py) in poženejo se mejni primeri:
  - brez sveže meritve ostane napoved nespremenjena,
  - ob »zdaj« krivulja sovpade z meritvijo, nato popravek linearno izzveni v ANCHOR_HOURS,
  - popravek je omejen na ANCHOR_MAX_C,
  - modelska temperatura ob »zdaj« je interpolirana, ne zaokrožena na uro.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILS = []


def js(calls):
    p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")],
                       input=json.dumps({"file": "app.js", "names": ["anchorHours", "ANCHOR_HOURS", "ANCHOR_MAX_C",
                                                                        "ANCHOR_MAX_AGE_MIN"],
                                         "prelude": "", "calls": calls}),
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    out = json.loads(p.stdout)
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["results"]


def check(ok, name, detail=""):
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


T0 = 1_700_000_000_000          # »zdaj« = celotna ura + 20 min
NOW = T0 + 20 * 60_000
H = 3_600_000


def hours(temps, start=T0):
    return "[" + ",".join(f"{{t:new Date({start + i * H}),temp:{v}}}" for i, v in enumerate(temps)) + "]"


def call(temps, obs, age=2, now=NOW, start=T0):
    return {"expr": f"anchorHours({hours(temps, start)},{now},{obs},{age})"}


def main():
    flat = [4.0] * 12
    r = js([
        call(flat, 6.0),                          # 0: meritev 2 °C nad modelom
        call(flat, 6.0, age=45),                  # 1: meritev stara
        call(flat, "null"),                       # 2: ni meritve
        call(flat, 20.0),                         # 3: nerealna razlika, omejitev
        call([2.0, 4.0, 6.0, 8.0, 8.0, 8.0, 8.0, 8.0], 6.0),         # 4: interpolacija ob 0:20
        call(flat, -1.0),                         # 5: negativen popravek
        {"expr": "[ANCHOR_HOURS, ANCHOR_MAX_C, ANCHOR_MAX_AGE_MIN]"},  # 6
        {"expr": "anchorHours([],0,5,1)"},         # 7: prazen seznam
        call(flat, 6.0, now=T0 - 20 * 60_000),    # 8: »zdaj« pred prvo uro (prva ura = zdaj + 40 min)
    ])
    H_, MAXC, MAXAGE = r[6]
    # 0: popravek +2, linearno izzveni; ura i je (i·60 − 20) min za »zdaj«
    t0 = r[0]["temps"]
    check(abs(r[0]["offset"] - 2.0) < 1e-9, "offset 2 °C", str(r[0]["offset"]))
    check(abs(t0[0] - 6.0) < 1e-9, "ura pred »zdaj« ima poln popravek, ne več", str(t0[0]))
    check(all(abs(t0[i] - (4.0 + 2.0 * max(0, 1 - ((i * 60 - 20) / 60) / H_))) < 1e-9 for i in range(1, 12)),
          "linearno izzvenevanje", str(t0))
    check(abs(t0[7] - 4.0) < 1e-9 and abs(t0[11] - 4.0) < 1e-9, "po ANCHOR_HOURS ostane surov model", str(t0))
    check(all(t0[i] >= t0[i + 1] - 1e-9 for i in range(11)), "izzvenevanje je monotono")
    # 1, 2, 7: brez sveže meritve se nič ne spremeni
    check(r[1]["offset"] == 0 and r[1]["temps"] == flat, "stara meritev ne zasidra")
    check(r[2]["offset"] == 0 and r[2]["temps"] == flat, "brez meritve ne zasidra")
    check(r[7]["temps"] == [] and r[7]["offset"] == 0, "prazen seznam")
    # 3: omejitev
    check(r[3]["offset"] == MAXC, "popravek omejen", str(r[3]["offset"]))
    # 4: model ob 0:20 = 2 + (4−2)·20/60 = 2,667; popravek 6 − 2,667 = 3,333
    check(abs(r[4]["offset"] - (6.0 - (2.0 + 2.0 * 20 / 60))) < 1e-9, "interpolacija modela ob »zdaj«", str(r[4]["offset"]))
    # 5: negativen popravek
    check(r[5]["offset"] == -MAXC, "negativen popravek, omejen", str(r[5]["offset"]))
    # 8: »zdaj« pred prvo uro, uporabi prvo vrednost
    check(abs(r[8]["offset"] - 2.0) < 1e-9, "pred prvo uro velja prva vrednost", str(r[8]["offset"]))
    check(MAXAGE == 30 and H_ == 6, "konstante", str(r[6]))
    if FAILS:
        print(f"✗ {len(FAILS)} napak")
        sys.exit(1)
    print("✓ test_anchor: vse v redu")


if __name__ == "__main__":
    main()
