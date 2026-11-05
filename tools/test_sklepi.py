#!/usr/bin/env python3
"""Test /sklepi/: točke dejavnikov, sklAnalyze (JS) proti Python referenci Spearmana, izris, ID-ji za JS. Brez omrežja."""
import datetime, json, math, os, random, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
import generate_sklepi_page as S  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


TODAY = datetime.date(2026, 6, 10)
DAY = TODAY.isoformat()


def synth(**o):
    base = dict(temperature_2m=20, apparent_temperature=20, relative_humidity_2m=50, dew_point_2m=9, wind_speed_10m=12,
                wind_gusts_10m=20, wind_direction_10m=180, precipitation=0, precipitation_probability=0, weather_code=1,
                pressure_msl=1015, shortwave_radiation=450, uv_index=4, cloud_cover=20)
    base.update(o)
    times = []
    for i in range(-2, 5):
        d = TODAY + datetime.timedelta(days=i)
        times += [f"{d.isoformat()}T{h:02d}:00" for h in range(24)]
    h = {"time": times}
    for k, v in base.items():
        h[k] = list(v) if isinstance(v, (list, tuple)) else [v] * len(times)
    return D.Ctx(h), times


# ── točke ──
c, times = synth()
pts, det = S.day_fn(c, DAY)
check("miren dan: vse 0", sum(pts.values()) == 0 and "brez izrazitega" in det["tlak_pad"])
press = [1015.0] * len(times)
i0 = times.index(f"{DAY}T00:00")
for i in range(i0, len(times)):
    press[i] = 1015 - min(10.0, (i - i0) / 2)
check("padec tlaka 10 hPa v 24 h = 3 točke", S.day_fn(synth(pressure_msl=press)[0], DAY)[0]["tlak_pad"] == 3)
check("nizek tlak 990 = 3", S.day_fn(synth(pressure_msl=990)[0], DAY)[0]["tlak_nizek"] == 3)
check("vlaga 86 % = 1, 93 % = 2, 50 % = 0",
      [S.day_fn(synth(relative_humidity_2m=v)[0], DAY)[0]["vlaga"] for v in (86, 93, 50)] == [1, 2, 0])
check("suha zrak ni dejavnik (vlaga 20 % = 0)", S.day_fn(synth(relative_humidity_2m=20)[0], DAY)[0]["vlaga"] == 0)
check("veter največ 2 točki", S.day_fn(synth(wind_speed_10m=80, wind_gusts_10m=120)[0], DAY)[0]["veter"] == 2)
check("mraz: občutena 3 °C = 1, −2 °C = 2, 10 °C = 0",
      [S.day_fn(synth(apparent_temperature=v)[0], DAY)[0]["mraz"] for v in (3, -2, 10)] == [1, 2, 0])
check("konfiguracija usklajena", {k for _, _, ks in S.CFG["groups"] for k in ks} == {k for k, _, _ in S.CFG["factors"]}
      and set(S.day_fn(synth()[0], DAY)[0]) == {k for k, _, _ in S.CFG["factors"]} and len(S.CFG["groups"]) <= 4)
check("nevihta in dež ne vplivata na oceno (ni dokaza)", "nevihta" not in {k for k, _, _ in S.CFG["factors"]})


# ── JS: sklAnalyze proti Python referenci ──
def node(js, arg):
    r = subprocess.run(["node", "-e", js, arg], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def ranks(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    a, b = ranks(x), ranks(y)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    sab = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    saa = sum((p - ma) ** 2 for p in a)
    sbb = sum((q - mb) ** 2 for q in b)
    return sab / math.sqrt(saa * sbb) if saa > 0 and sbb > 0 else None


def make_hist(n=80, seed=3, pain_from_drop=False, noise=1.0):
    rnd = random.Random(seed)
    start = datetime.date(2026, 1, 1)
    h, entries, p = {}, [], 1015.0
    prev_p = p
    for i in range(n):
        d = (start + datetime.timedelta(days=i)).isoformat()
        prev_p = p
        p = min(max(p + rnd.uniform(-6, 6), 985), 1040)
        h[d] = {"pressureAvg": p, "pressureHigh": p + 1, "pressureLow": p - 1, "tempAvg": 10 + rnd.uniform(-5, 5), "humidityAvg": 70 + rnd.uniform(-10, 10),
                "windgustHigh": 10 + rnd.uniform(0, 20), "precipTotal": rnd.choice([0, 0, 0.2, 3]), "solarHigh": 300 + rnd.uniform(-50, 50), "src": "ecowitt"}
        dp = p - prev_p
        pain = 5 + (-0.9 * dp if pain_from_drop else rnd.uniform(-2.5, 2.5)) + rnd.gauss(0, noise)
        entries.append({"d": d, "p": int(min(10, max(0, round(pain))))})
    return h, entries


def run(h, e):
    rc, out, err = node(S.SKL_ANALYZE_JS + "\nvar a=JSON.parse(process.argv[1]);console.log(JSON.stringify(sklAnalyze(a.h,a.e)));", json.dumps({"h": h, "e": e}))
    return json.loads(out) if rc == 0 else None


h, e = make_hist(pain_from_drop=True)
res = run(h, e)
check("sklAnalyze teče in vrne vrstice", res and res["nUsed"] == len(e) and len(res["rows"]) >= 8)
row = next((r for r in res["rows"] if r["id"] == "dP0"), None)
check("bolečina ob padcu tlaka: dP0 negativen in izstopa", row and row["rho"] < -0.5 and row["sig"] and res["enough"])
# Python referenca za vse vrstice
dates = [x["d"] for x in e]
ref = {
    "dP0": [h[d]["pressureAvg"] - h[(datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat()]["pressureAvg"]
            if (datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat() in h else None for d in dates],
    "P": [h[d]["pressureAvg"] for d in dates], "T": [h[d]["tempAvg"] for d in dates], "RH": [h[d]["humidityAvg"] for d in dates],
    "gust": [h[d]["windgustHigh"] for d in dates], "rain": [h[d]["precipTotal"] for d in dates], "sun": [h[d]["solarHigh"] for d in dates],
    "rP": [h[d]["pressureHigh"] - h[d]["pressureLow"] for d in dates],
}
okpar = True
for r in res["rows"]:
    if r["id"] not in ref:
        continue
    pairs = [(v, x["p"]) for v, x in zip(ref[r["id"]], e) if v is not None]
    py = spearman([a for a, _ in pairs], [b for _, b in pairs])
    if py is None or abs(py - r["rho"]) > 1e-9 or r["n"] != len(pairs):
        okpar = False
        print("   razlika", r["id"], py, r["rho"], r["n"], len(pairs))
check("JS Spearman = Python referenca (z vezmi, ranki povprečeni)", okpar)

h2, e2 = make_hist(pain_from_drop=False, seed=11)
res2 = run(h2, e2)
check("naključna bolečina: nič ne izstopa", res2 and not any(r["sig"] for r in res2["rows"]))
check("naključna bolečina: povezave so majhne (|rho| < 0,5)", res2 and all(abs(r["rho"]) < 0.5 for r in res2["rows"]))

res3 = run(h, e[:S.MIN_DAYS - 1])
check("pod 14 zapisi: enough = false in nič ne izstopa", res3 and res3["enough"] is False and not any(r["sig"] for r in res3["rows"]))
res4 = run(h, e[:S.MIN_DAYS])
check("natanko 14 zapisov: enough = true", res4 and res4["enough"] is True)

# reanaliza (era5) ni meritev; neveljavne vrednosti in podvojeni datumi
h5 = {d: dict(v) for d, v in h.items()}
for d in list(h5)[:30]:
    h5[d]["src"] = "era5"
res5 = run(h5, e)
check("dnevi z src=era5 se ne štejejo", res5 and res5["nUsed"] == len(e) - 30)
bad = e[:20] + [{"d": e[0]["d"], "p": 9}, {"d": e[1]["d"], "p": 11}, {"d": e[2]["d"], "p": -1}, {"d": "2030-01-01", "p": 5}, {"d": e[3]["d"], "p": "7"}]
res6 = run(h, bad)
check("neveljavni zapisi (11, −1, niz, brez podatkov) se zavržejo, podvojen datum šteje zadnji",
      res6 and res6["nUsed"] == 20 and res6["nEntries"] == len(bad))
check("brez podatkov ne pade", run({}, []) and run({}, [])["nUsed"] == 0)
flat = [{"d": x["d"], "p": 4} for x in e]
resf = run(h, flat)
check("stalna bolečina: brez vrstic (ni variance), ne pade", resf is not None and resf["rows"] == [])
check("merilo za izstopanje je strožje od 1,96", S.Z_CRIT > 1.96 and res["zCrit"] == S.Z_CRIT)

# ── izris ──
page, days = D.build_page(S.CFG, synth(relative_humidity_2m=95)[0], TODAY)
body = page.split("</head>")[1]
check("brez notranjih meritev", "indoor" not in page.lower())
check("opozorilo: ni zdravniški nasvet", "To ni zdravniški nasvet." in body)
check("rdeče zastavice in 112", "112" in body and "Kdaj k zdravniku" in body)
check("dnevnik samo v brskalniku", "samo v vašem brskalniku" in body and "localStorage" in body)
_t = body.lower()
for neg in ("ne dokaz, da vreme povzroča bolečino", "ne trdi, da vreme bolečino povzroča", "ali vreme bolečino povzroča ali jo le okrepi"):
    _t = _t.replace(neg, "")   # zanikanja vzročnosti stran mora povedati
check("stran nikjer ne trdi, da vreme povzroča bolečino", "ne vemo" in _t and not re.search(r"povzroča\s+bolečin|bolečin\w*\s+povzroča|sproži\w*\s+bolečin", _t))
check("navedek raziskave (Dixon, 2019)", "Dixon" in body and "2019" in body)
for i in ("skl-form", "skl-date", "skl-pain", "skl-pain-out", "skl-note", "skl-add", "skl-export", "skl-clear", "skl-analyze", "skl-result",
          "skl-msg", "skl-count", "skl-table", "skl-tbody", "dv-days", "dv-hero", "ov-alert"):
    if f'id="{i}"' not in body:
        check(f"element #{i} obstaja", False)
check("vsi elementi za JS obstajajo", not [f for f in fails if f.startswith("element #")])
script = re.search(r"<script>\n(\(function\(\)\{\nfunction sklAnalyze.*?)</script>", body, re.S)
check("odjemalski skript najden", bool(script))
if script:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script.group(1))
    r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
    os.unlink(f.name)
    check("odjemalski skript je veljaven JS", r.returncode == 0)
check("gradnik opozoril je na strani (opozorila po ocenah)", "Opozorilo na telefon" in body)
check("naslov ≤ 60 znakov, opis ≤ 160", len(S.CFG["title"]) <= 60 and all(len(S.CFG["desc"](l)) <= 160 for l in S.CFG["levels"]))
sys.exit(1 if fails else 0)
