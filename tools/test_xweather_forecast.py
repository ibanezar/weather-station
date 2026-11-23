#!/usr/bin/env python3
"""tools/test_xweather_forecast.py — zajem napovedi XWeather (lažen odgovor, brez omrežja).

Preverja: urno → dnevno po lokalnem času, preskok odrezanega dne, ovoj odgovora (seznam ali slovar),
napako API-ja, preskok brez secretov in da se ključ nikoli ne izpiše.
"""
import contextlib, datetime, io, json, os, sys, zoneinfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import log_forward_forecasts as L  # noqa: E402

L.TZ_LJ = zoneinfo.ZoneInfo("Europe/Ljubljana")
fails = []


def check(ok, name):
    if not ok:
        fails.append(name)
        print("  ✗", name)


def hours(first_day, n_days, start_hour=0, temp=None, precip=0.1):
    """Urne točke od first_day ob start_hour (lokalno, +01:00 pozimi)."""
    out = []
    t0 = datetime.datetime.fromisoformat(f"{first_day}T{start_hour:02d}:00:00+01:00")
    for i in range(n_days * 24):
        t = t0 + datetime.timedelta(hours=i)
        local_h = (start_hour + i) % 24
        tc = temp(local_h) if temp else float(local_h)
        out.append({"dateTimeISO": t.isoformat(), "tempC": tc, "precipMM": precip})
    return out


today = datetime.date(2026, 11, 23)

# 1) polni dnevi: 24.-25. 11., zadnji dan 26. 11. odrezan na 10 ur
per = hours("2026-11-24", 2, temp=lambda h: -2.0 + h * 0.5) + hours("2026-11-26", 1)[:10]
rows = L.parse_xweather({"success": True, "error": None, "response": [{"periods": per}]}, today)
by = {r["valid_at"]: r for r in rows}
check(set(by) == {"2026-11-24", "2026-11-25"}, f"dnevi {sorted(by)}")
r = by["2026-11-24"]
check(r["model"] == "xweather" and r["lead_days"] == 1 and r["issued_at"] == "2026-11-23", "polja")
check(r["tmax_c"] == 9.5 and r["tmin_c"] == -2.0, f"tmax/tmin {r['tmax_c']} {r['tmin_c']}")
check(r["precip_mm"] == 2.4, f"padavine {r['precip_mm']}")

# 2) ovoj je lahko slovar namesto seznama
rows2 = L.parse_xweather({"success": True, "response": {"periods": per}}, today)
check(len(rows2) == 2, "ovoj slovar")

# 3) lokalni dan, ne UTC: točka 23:30 UTC (= 00:30 naslednjega dne) spada v naslednji lokalni dan
per3 = hours("2026-11-24", 1)
per3.append({"dateTimeISO": "2026-11-24T23:30:00+00:00", "tempC": 30.0, "precipMM": 0})
rows3 = {r["valid_at"] for r in L.parse_xweather({"response": [{"periods": per3}]}, today)}
check("2026-11-24" in rows3 and "2026-11-25" not in rows3, "25. 11. ima samo 1 točko (odrezan)")
d24 = next(r for r in L.parse_xweather({"response": [{"periods": per3}]}, today) if r["valid_at"] == "2026-11-24")
check(d24["tmax_c"] == 23.0, "30 °C ob 00:30 25. 11. ne sme v 24. 11.")

# 4) ura brez padavin: vsota samo iz razpoložljivih; brez vseh padavin prazno
per4 = [{"dateTimeISO": p["dateTimeISO"], "tempC": p["tempC"]} for p in hours("2026-11-24", 1)]
rows4 = L.parse_xweather({"response": [{"periods": per4}]}, today)
check(len(rows4) == 1 and rows4[0]["precip_mm"] is None, "padavine None")

# 5) lead 0 in prek MAX_LEAD
per5 = hours("2026-11-23", 1) + hours("2026-12-05", 1)
check(L.parse_xweather({"response": [{"periods": per5}]}, today) == [], "lead 0 in > 7 izpuščena")

# 6) napaka API-ja
try:
    L.parse_xweather({"success": False, "error": {"code": "invalid_client", "description": "tajno"}}, today)
    check(False, "napaka API-ja mora vreči izjemo")
except L.XWeatherError as e:
    check("invalid_client" in str(e) and "tajno" not in str(e), "koda napake, brez opisa")

# 7) brez secretov: preskok, brez omrežja
for k in ("XWEATHER_CLIENT_ID", "XWEATHER_CLIENT_SECRET"):
    os.environ.pop(k, None)
check(L.fetch_xweather(today) is None, "brez secretov None")

# 8) s secreti: lažen urlopen; ključ v URL-ju, a nikoli v izpisu; prazen odgovor ne podre
os.environ["XWEATHER_CLIENT_ID"] = "dummy-id"
os.environ["XWEATHER_CLIENT_SECRET"] = "dummy-secret-123"
seen = {}


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def fake_urlopen(req, timeout=0):
    seen["url"] = req.full_url
    seen["ua"] = req.get_header("User-agent")
    return FakeResp(json.dumps({"success": True, "response": [{"periods": per}]}).encode())


orig = L.urllib.request.urlopen
L.urllib.request.urlopen = fake_urlopen
try:
    got = L.fetch_xweather(today)
finally:
    L.urllib.request.urlopen = orig
check(len(got) == 2, "fetch_xweather vrne dneve")
check("filter=1hr" in seen["url"] and "client_id=dummy-id" in seen["url"], "parametri zahtevka")
check("@" not in (seen["ua"] or ""), "User-Agent brez kontaktnega naslova")

# 9) main(): napaka omrežja ne izpiše ključa in ne podre zajema
def boom(req, timeout=0):
    raise L.urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)


def only_xweather_boom(req, timeout=0):
    if "xweather" in req.full_url:
        return boom(req, timeout)
    raise L.urllib.error.URLError("offline")


L.urllib.request.urlopen = only_xweather_boom
buf = io.StringIO()
L.FORWARD_LOG_PATH = os.path.join(os.environ.get("TMPDIR", "/tmp"), "xw-test-forward-log.csv")
if os.path.exists(L.FORWARD_LOG_PATH):
    os.remove(L.FORWARD_LOG_PATH)
try:
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        L.main()
finally:
    L.urllib.request.urlopen = orig
    if os.path.exists(L.FORWARD_LOG_PATH):
        os.remove(L.FORWARD_LOG_PATH)
out = buf.getvalue()
check("dummy-secret-123" not in out and "dummy-id" not in out, "ključ ni v izpisu")
check("XWeather" in out and "HTTP 401" in out, "izpis napake z kodo")

# 10) HTTP 401 s telesom: izpiše se koda razloga, ne pa opis in ne ključ
def unauthorized(req, timeout=0):
    body = json.dumps({"success": False, "error": {"code": "invalid_client",
                                                   "description": "dummy-secret-123"}}).encode()
    raise L.urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(body))


L.urllib.request.urlopen = unauthorized
try:
    L.fetch_xweather(today)
    check(False, "401 mora vreči XWeatherError")
except L.XWeatherError as e:
    check(str(e) == "HTTP 401: invalid_client", f"koda iz telesa: {e}")
    check("dummy-secret-123" not in str(e), "opis napake ne uide")
finally:
    L.urllib.request.urlopen = orig

print("OK" if not fails else f"{len(fails)} FAIL")
sys.exit(1 if fails else 0)
