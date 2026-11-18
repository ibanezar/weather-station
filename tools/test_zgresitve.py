#!/usr/bin/env python3
"""Test /zgresitve/: izbor dni (mesec ≥ 15 dni, največja |napaka|), skladnost err_* z napoved − meritev, brez None/notranjih ključev."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import generate_zgresitve_page as Z
bad = 0
def chk(c, m):
    global bad
    if not c:
        bad += 1; print("NAPAKA:", m)
V = json.load(open(os.path.join(ROOT, "forecast_verification.json"), encoding="utf-8"))
months = Z.pick(V)
for m, (n, rows) in months.items():
    chk(n >= Z.MIN_DAYS, f"{m}: premalo dni")
    errs = [r[0][0] for r in rows]
    chk(errs == sorted(errs, reverse=True), f"{m}: vrstni red")
    allmax = max(Z.worst(r)[0] for k, r in V.items() if k.startswith(m) and (r.get("actual") or {}).get("tmax") is not None and Z.worst(r))
    chk(errs[0] == allmax, f"{m}: prvi ni največja napaka")
# err_* ustreza |napoved − meritev| (zaokroževanje 0,1)
cnt = 0
for k, r in V.items():
    a = r.get("actual") or {}
    for key, _ in Z.SOURCES:
        s = r.get(key) or {}
        for var in ("tmax", "tmin"):
            if s.get(var) is not None and s.get("err_" + var) is not None and a.get(var) is not None:
                cnt += 1
                if abs(abs(s[var] - a[var]) - abs(s["err_" + var])) > 0.11:
                    chk(False, f"{k} {key} {var}: err ne ustreza"); break
chk(cnt > 100, "premalo primerjav")
# majhen sintetičen primer
syn = {f"2026-01-{d:02d}": {"actual": {"tmax": 5, "tmin": 0}, "open_meteo": {"tmax": 5 + (9 if d == 3 else 1), "tmin": 0, "err_tmax": 9 if d == 3 else 1, "err_tmin": 0}} for d in range(1, 21)}
p = Z.pick(syn); chk(list(p) == ["2026-01"] and p["2026-01"][1][0][1] == "2026-01-03", "sintetičen: izbran dan 3. 1.")
chk(Z.pick({k: v for k, v in list(syn.items())[:10]}) == {}, "mesec s < 15 dnevi se izpusti")
html = open(os.path.join(ROOT, "zgresitve", "index.html"), encoding="utf-8").read()
chk(not re.search(r"None|NaN|undefined", html) and not re.search(r"indoor|tempinf", html, re.I), "None/NaN/notranji ključi v strani")
print("zgresitve:", "OK" if not bad else f"{bad} napak"); sys.exit(1 if bad else 0)
