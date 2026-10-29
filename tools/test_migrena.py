#!/usr/bin/env python3
"""Test /migrena/: točke, graf tlaka, JS (dvLevel ↔ level_index, migAnalyze na sintetičnih podatkih), izris. Brez omrežja."""
import datetime, json, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
import generate_migrena_page as M  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


TODAY = datetime.date(2026, 6, 10)


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
pts, det = M.day_fn(c, TODAY.isoformat())
check("miren dan: 0 točk tlaka in 'brez izrazitega padca'", pts["tlak_pad"] == 0 and "brez izrazitega" in det["tlak_pad"])
# padec 8 hPa čez 24 ur v sredini 3. dneva
press = [1015.0] * len(times)
for i, t in enumerate(times):
    if t >= f"{TODAY.isoformat()}T00:00":
        press[i] = 1015 - min(10.0, (i - times.index(f"{TODAY.isoformat()}T00:00")) / 2)
c2, _ = synth(pressure_msl=press)
drop = M.pressure_drops(c2, TODAY.isoformat())
check("padec tlaka 24 h se izračuna (≈ 10 hPa)", drop is not None and 9.5 <= drop <= 10.01)
pts2, _ = M.day_fn(c2, TODAY.isoformat())
check("padec 10 hPa = 3 točke (veto)", pts2["tlak_pad"] == 3)
check("brez 24 ur zgodovine ni padca (None)", M.pressure_drops(D.Ctx({"time": times[:10], "pressure_msl": [1000] * 10}), times[0][:10]) is None)
check("nevihta = 2 točki", M.day_fn(synth(weather_code=95)[0], TODAY.isoformat())[0]["nevihta"] == 2)
check("nizek tlak 990 = 3", M.day_fn(synth(pressure_msl=990)[0], TODAY.isoformat())[0]["tlak_nizek"] == 3)
check("vlaga 93 % = 2, 25 % = 1", M.day_fn(synth(relative_humidity_2m=93)[0], TODAY.isoformat())[0]["vlaga"] == 2
      and M.day_fn(synth(relative_humidity_2m=25)[0], TODAY.isoformat())[0]["vlaga"] == 1)
check("UV največ 2", M.day_fn(synth(uv_index=12)[0], TODAY.isoformat())[0]["svetloba"] == 2)
check("konfiguracija usklajena", {k for _, _, ks in M.CFG["groups"] for k in ks} == {k for k, _, _ in M.CFG["factors"]} == set(M.TRIGGERS)
      and len(M.CFG["groups"]) <= 4)

# ── graf tlaka ──
now = datetime.datetime(2026, 6, 10, 12)
series, key = M.pressure_series(c2, now)
check("serija obsega −24…+72 h", len(series) == 97 and key == "2026-06-10T12:00")
sm = M.pressure_summary(series, key)
check("povzetek: najstrmejši padec in najnižji tlak", sm and sm["drop"] > 0 and sm["low"] <= min(p for _, p, _ in series) + 1e-9)
check("zapis časa", M.when_text("2026-06-10T14:00") == "sre ob 14.00")

# ── JS: dvLevel ↔ level_index, migAnalyze ──
def node(js, arg):
    r = subprocess.run(["node", "-e", js, arg], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


import itertools
cases = []
for combo in itertools.product(range(4), repeat=3):
    pts_ = {k: 0 for k in M.TRIGGERS}
    pts_["tlak_pad"], pts_["nevihta"], pts_["vlaga"] = combo
    for w in ({}, {"tlak_pad": 2}, {"nevihta": 2, "vlaga": 2}):
        cases.append((pts_, w))
js = D.JS_CORE + """
var c=JSON.parse(process.argv[1]);console.log(JSON.stringify(c.map(function(x){return [dvScore(x[0],x[1]),dvLevel(x[0],x[1],%s,%d,%d)];})));""" % (
    json.dumps(list(M.CFG["th"])), D.FLOOR_PTS, D.FLOOR_LEVEL)
rc, out, err = node(js, json.dumps(cases))
ok = rc == 0 and all(
    g[0] == sum(p[k] * w.get(k, 1) for k in p) and g[1] == D.level_index(g[0], max(p.values()), M.CFG["th"])
    for g, (p, w) in zip(json.loads(out), cases))
check(f"JS dvLevel ↔ level_index na {len(cases)} primerih", ok)


def hist_data(attack_drop):
    """200 dni; tlak z dnevnim naključnim hodom (deterministično); napadi na dneve z velikim padcem, če attack_drop."""
    import random
    rnd = random.Random(7)
    start = datetime.date(2026, 1, 1)
    h, p, atk = {}, 1015.0, []
    for i in range(200):
        d = (start + datetime.timedelta(days=i)).isoformat()
        p += rnd.uniform(-6, 6)
        p = min(max(p, 985), 1040)
        h[d] = {"pressureAvg": p, "pressureHigh": p + 1, "pressureLow": p - 1, "tempAvg": 10 + rnd.uniform(-5, 5),
                "humidityAvg": 70 + rnd.uniform(-10, 10), "windgustHigh": 10, "precipTotal": 0, "solarHigh": 300}
    days = sorted(h)
    if attack_drop:
        for a, b in zip(days, days[1:]):
            pass
        for i in range(1, len(days)):
            if h[days[i]]["pressureAvg"] - h[days[i - 1]]["pressureAvg"] <= -4.2 and len(atk) < 10 and i % 4 == 0:
                atk.append(days[i])
    else:
        atk = [days[i] for i in range(20, 190, 17)]
    return h, atk


for label, drop in (("padec tlaka", True), ("naključni napadi", False)):
    h, atk = hist_data(drop)
    js = M.MIG_ANALYZE_JS + "\nvar a=JSON.parse(process.argv[1]);console.log(JSON.stringify(migAnalyze(a.h,a.a)));"
    rc, out, err = node(js, json.dumps({"h": h, "a": atk}))
    res = json.loads(out) if rc == 0 else {}
    check(f"migAnalyze teče ({label})", rc == 0 and res.get("nUsed") == len(atk) and len(res.get("rows", [])) >= 8)
    row = next((r for r in res.get("rows", []) if r["id"] == "dP0"), None)
    if drop:
        check("napadi ob padcu tlaka: dP0 negativen in izstopa", row and row["diff"] < -1 and row["sig"] and res["enough"] or (row and row["diff"] < -1 and row["sig"]))
        check("delež padcev ≥ 4 hPa je pri napadih višji", res["drop"]["p"] is not None and res["drop"]["p"] > (res["dropBase"]["p"] or 0))
    else:
        check("naključni napadi: tlak ne izstopa za več kot 1 dP0 po absolutni vrednosti", row and abs(row["diff"]) < 2)
rc, out, err = node(M.MIG_ANALYZE_JS + "\nconsole.log(JSON.stringify(migAnalyze({},[])),JSON.stringify(migAnalyze({'2026-01-01':{}},['2026-01-01','2026-01-01'])));", "x")
check("migAnalyze brez podatkov ne pade", rc == 0 and '"nUsed":0' in out)
h, atk = hist_data(False)
rc, out, err = node(M.MIG_ANALYZE_JS + "\nvar a=JSON.parse(process.argv[1]);console.log(JSON.stringify(migAnalyze(a.h,a.a.slice(0,2))));", json.dumps({"h": h, "a": atk}))
check("pod 5 napadov: enough = false", rc == 0 and json.loads(out)["enough"] is False)

# ── izris ──
page, days = D.build_page(M.CFG, synth(**{"weather_code": 95})[0], TODAY)
body = page.split("</head>")[1]
check("brez notranjih meritev", "indoor" not in page.lower())
check("rdeče zastavice in 112", "112" in body and "Kdaj nujno k zdravniku" in body)
check("dnevnik samo v brskalniku", "samo v vašem brskalniku" in body and "localStorage" in body)
check("opozorilo: ni zdravniški nasvet", "To ni zdravniški nasvet." in body)
check("ikona glave z bliskom obstaja kot datoteka in je na strani",
      'alt="Glava z bliskom"' in body and os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img/migrena/glava-blisk.png")))
for i in ("mig-apply", "mig-reset", "mig-trig", "mig-date", "mig-add", "mig-export", "mig-clear", "mig-analyze", "mig-result", "mig-form",
          "mig-aura", "mig-note", "mig-msg", "mig-count", "mig-table", "mig-tbody", "mig-trig-status", "dv-days", "dv-hero", "dv-hero-l", "dv-needle"):
    if f'id="{i}"' not in body:
        check(f"element #{i} obstaja", False)
check("vsi elementi za JS obstajajo", not [f for f in fails if f.startswith("element #")])
script = re.search(r"<script>\n(\(function.*?)</script>", body, re.S)
check("odjemalski skript najden", bool(script))
if script:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script.group(1))
    r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
    os.unlink(f.name)
    check("odjemalski skript je veljaven JS", r.returncode == 0)
check("naslov ≤ 60 znakov", len(M.CFG["title"]) <= 60)
# alarm: izbirnik praga ↔ worker.js (namerna podvojitev)
wsrc = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker.js"), encoding="utf-8").read()
m = re.search(r"const MIG_THR_ALLOWED = \[([0-9, ]+)\]", wsrc)
check("prag alarma: izbirnik ↔ MIG_THR_ALLOWED v worker.js", m and [int(x) for x in m.group(1).split(",")] == [v for v, _ in M.ALARM_THR])
check("privzeti prag je med dovoljenimi", f"const MIG_THR_DEFAULT = 5;" in wsrc and 5 in [v for v, _ in M.ALARM_THR])
for i in ("mig-alarm", "mig-alarm-on", "mig-alarm-off", "mig-alarm-thr", "mig-alarm-msg", "mig-alarm-ios"):
    check(f"alarm: element #{i}", f'id="{i}"' in body)
check("alarm: strežnik hrani samo naslovnico in prag (besedilo)", "samo naslovnico naročnine in prag" in body)
check("alarm: odjemalec pošilja site:'migrena'", "site:'migrena'" in body)
sys.exit(1 if fails else 0)
