#!/usr/bin/env python3
"""
tools/probe_om_models.py — ali imajo novi modeli Open-Meteo arhiv napovedi (previous_dayN)?

Open-Meteo 1.8.0 (3. 11. 2026) je dodal DWD AICON, ICON-D2-RUC in NOAA RRFS, v izbirniku Previous Runs API
pa so samo nekateri modeli (dokumentacija si nasprotuje). Arhiv previous_dayN je pogoj, da model lahko
ocenimo na semaforju (/test-napovedi/) po istem merilu kot ostale. Skript za vsakega kandidata:

  1. preveri, ali ID sploh velja v forecast API-ju (`models=<id>`, nekaj ur),
  2. v Previous Runs API-ju prebere temperature_2m_previous_day1..3 za Rečico za zadnjih PAST_DAYS dni
     in izpiše število vrednosti, prvi dan z vrednostjo in delež pokritih ur.

Nič ne zapiše v repozitorij: izhod je v povzetku teka (.github/workflows/om-models-probe.yml). Ker gre samo
za poizvedbo, ni ocene kakovosti in ni vira za objavo. Peskovnik razvojne seje ima deljen IP in dnevno kvoto
Open-Meteo skoraj stalno porabljeno, zato teče na tekaču.

Usage:
  python3 tools/probe_om_models.py [--past-days N] [--models id1,id2,...]
"""
import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Ista točka kot ostali arhivski skripti (tools/build_forecast_archive.py).
LAT, LON = 46.325779, 14.921137
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-ModelProbe/1.0; +https://meteorec.si)"}
FORECAST = "https://api.open-meteo.com/v1/forecast"
PREVIOUS = "https://previous-runs-api.open-meteo.com/v1/forecast"
LEADS = (1, 2, 3)

# (id, kratko ime, opomba). ID-jev novih modelov nisem mogel preveriti (kvota), zato je za vsak model več kandidatov;
# neveljaven ID da v forecast API-ju napako in se pokaže kot takšen.
CANDIDATES = [
    ("ecmwf_aifs025_single", "ECMWF AIFS (kontrola, ima arhiv)", "referenca: že na semaforju"),
    ("icon_d2", "ICON-D2 (sedanji ID)", "v CLAUDE.md: brez arhiva; preveri"),
    ("dwd_icon_d2", "ICON-D2 (DWD ID)", ""),
    ("dwd_icon_d2_native", "ICON-D2 Native", "v izbirniku Previous Runs"),
    ("dwd_aicon", "DWD AICON", "novo v 1.8.0"),
    ("dwd_aicon_native", "DWD AICON Native", "novo v 1.8.0, ime po vzoru drugih Native"),
    ("dwd_icon_d2_ruc", "ICON-D2-RUC", "novo v 1.8.0"),
    ("dwd_icon_d2_ruc_native", "ICON-D2-RUC Native", "novo v 1.8.0"),
    ("ncep_aigfs025", "NOAA AIGFS 0,25°", "v izbirniku Previous Runs"),
    ("ncep_hgefs025", "NOAA HGEFS 0,25° (ansambel)", "v izbirniku Previous Runs"),
]


def get(url, params, timeout=90, tries=3):
    """GET z ponovnim poskusom ob 429/5xx. Vrne (json|None, napaka|None)."""
    full = url + "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers=UA), timeout=timeout) as r:
                data = json.load(r)
            if isinstance(data, dict) and data.get("error"):
                return None, str(data.get("reason", "napaka"))[:160]
            return data, None
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
                body = json.loads(body).get("reason", body)
            except Exception:
                pass
            last = "HTTP %s: %s" % (e.code, str(body)[:160])
            if e.code in (429, 500, 502, 503, 504) and i + 1 < tries:
                time.sleep(15 * (i + 1))
                continue
            return None, last
        except Exception as e:  # omrežje, razčlenjevanje
            last = "%s: %s" % (type(e).__name__, str(e)[:120])
            if i + 1 < tries:
                time.sleep(5)
                continue
            return None, last
    return None, last


def probe_live(model):
    data, err = get(FORECAST, {
        "latitude": LAT, "longitude": LON, "models": model,
        "hourly": "temperature_2m", "forecast_hours": 6, "timezone": "UTC",
    })
    if err:
        low = err.lower()
        # Kvota ali izpad vira NI dokaz, da ID ne velja: ločimo, sicer bi poročilo lagalo.
        if "429" in err or "limit" in low or "quota" in low or "timed out" in low or "HTTP 5" in err:
            return None, err
        return False, err
    vals = ((data or {}).get("hourly") or {}).get("temperature_2m") or []
    n = sum(1 for v in vals if v is not None)
    return n > 0, ("%d/%d ur z vrednostjo" % (n, len(vals)))


def probe_previous(model, past_days):
    q = {
        "latitude": LAT, "longitude": LON, "models": model, "timezone": "UTC",
        "past_days": past_days, "forecast_days": 1,
        "hourly": ",".join("temperature_2m_previous_day%d" % n for n in LEADS),
    }
    data, err = get(PREVIOUS, q, timeout=180)
    if err:
        return None, err
    h = (data or {}).get("hourly") or {}
    times = h.get("time") or []
    out = {}
    for n in LEADS:
        vals = h.get("temperature_2m_previous_day%d" % n) or []
        have = [t for t, v in zip(times, vals) if v is not None]
        out[n] = {
            "n": len(have), "of": len(times),
            "first": have[0][:10] if have else None,
            "last": have[-1][:10] if have else None,
        }
    return out, None


def hourly_previous_day1(model, past_days):
    """{ura: temperature_2m_previous_day1} za model; None ob napaki."""
    data, err = get(PREVIOUS, {
        "latitude": LAT, "longitude": LON, "models": model, "timezone": "UTC",
        "past_days": past_days, "forecast_days": 1, "hourly": "temperature_2m_previous_day1",
    }, timeout=180)
    if err:
        return None, err
    h = (data or {}).get("hourly") or {}
    return dict(zip(h.get("time") or [], h.get("temperature_2m_previous_day1") or [])), None


def run_diff(pair, past_days):
    """Ali model A pri D+1 doda kaj k modelu B? Primerja urno previous_day1 temperaturo (npr. icon_d2 proti
    icon_seamless: seamless pri D+1 verjetno že vzame ICON-D2, zato bi bila samostojna vrstica na semaforju odveč)."""
    a_id, b_id = pair
    print("\nPrimerjava previous_day1 temperature_2m: %s proti %s (zadnjih %d dni)" % (a_id, b_id, past_days))
    a, ea = hourly_previous_day1(a_id, past_days)
    time.sleep(2)
    b, eb = hourly_previous_day1(b_id, past_days)
    if a is None or b is None:
        print("  ni odgovora: %s / %s" % (ea, eb))
        return
    common = [t for t in a if a[t] is not None and b.get(t) is not None]
    if not common:
        print("  ni skupnih ur z vrednostjo")
        return
    d = [abs(a[t] - b[t]) for t in common]
    same = sum(1 for x in d if x < 0.05)
    print("  skupnih ur: %d" % len(d))
    print("  povprečna |razlika|: %.3f °C, največja: %.2f °C" % (sum(d) / len(d), max(d)))
    print("  ur z razliko < 0,05 °C: %d (%.1f %%)" % (same, 100.0 * same / len(d)))
    verdict = ("praktično isti podatek: samostojna vrstica na semaforju ne doda ničesar"
               if same / len(d) > 0.9 else "podatka se razlikujeta: vrstica bi lahko kaj dodala")
    print("  zaključek: " + verdict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--past-days", type=int, default=400)
    ap.add_argument("--models", default="")
    ap.add_argument("--diff", default="", help="A,B: primerjaj previous_day1 temperaturo dveh modelov")
    a = ap.parse_args()
    if a.diff:
        pair = [m.strip() for m in a.diff.split(",") if m.strip()]
        if len(pair) != 2:
            print("--diff zahteva natanko dva ID-ja (A,B)", file=sys.stderr)
            return 2
        print("Diff probe, Rečica (%.4f, %.4f)" % (LAT, LON))
        run_diff(pair, a.past_days)
        if not a.models:
            return 0
    wanted = [m.strip() for m in a.models.split(",") if m.strip()]
    cands = [c for c in CANDIDATES if not wanted or c[0] in wanted]
    for m in wanted:
        if m not in [c[0] for c in CANDIDATES]:
            cands.append((m, m, "ročno naveden"))

    print("Previous Runs probe, Rečica (%.4f, %.4f), okno %d dni, %s UTC\n" % (
        LAT, LON, a.past_days, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")))
    rows = []
    for mid, label, note in cands:
        live_ok, live_msg = probe_live(mid)  # True / False (ID ne velja) / None (kvota ali izpad: ni odgovora)
        time.sleep(2)
        if live_ok is False:
            prev, prev_err = None, "preskočeno: ID ne velja v forecast API-ju"
        elif live_ok is None:
            prev, prev_err = None, "preskočeno: forecast API ni odgovoril (kvota ali izpad)"
        else:
            prev, prev_err = probe_previous(mid, a.past_days)
        time.sleep(2)
        rows.append((mid, label, note, live_ok, live_msg, prev, prev_err))
        print("== %s (%s)" % (mid, label))
        print("   forecast API: %s — %s" % ({True: "OK", False: "NE", None: "BREZ ODGOVORA"}[live_ok], live_msg))
        if prev is None:
            print("   previous runs: %s" % prev_err)
        else:
            for n in LEADS:
                p = prev[n]
                cov = (100.0 * p["n"] / p["of"]) if p["of"] else 0.0
                print("   previous_day%d: %d/%d ur (%.0f %%), od %s do %s" % (
                    n, p["n"], p["of"], cov, p["first"], p["last"]))
        sys.stdout.flush()

    print("\nPovzetek")
    print("| ID | forecast API | previous_day1 | prvi dan | zadnji dan | zaključek |")
    print("|---|---|---|---|---|---|")
    for mid, label, note, live_ok, live_msg, prev, prev_err in rows:
        if prev is None:
            if live_ok is False:
                concl = "ID ne velja"
            elif live_ok is None:
                concl = "ni odgovora (kvota ali izpad), ponovi"
            else:
                concl = "napaka: " + str(prev_err)[:60]
            print("| `%s` | %s | — | — | — | %s |" % (mid, {True: "OK", False: "NE", None: "?"}[live_ok], concl))
            continue
        p = prev[1]
        if p["n"] == 0:
            concl = "ID velja, a brez arhiva"
        else:
            cov = 100.0 * p["n"] / p["of"]
            concl = "arhiv je (%.0f %% ur v oknu)" % cov
        print("| `%s` | OK | %d | %s | %s | %s |" % (mid, p["n"], p["first"] or "—", p["last"] or "—", concl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
