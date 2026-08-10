#!/usr/bin/env python3
"""
tools/verify_forecasts.py — daily forecast verification pipeline

Nobody in Slovenia systematically tracks whether ARSO's or Open-Meteo's
day-ahead forecast for a specific valley actually verifies. This station
has the ground truth (history.json) to do it.

Two-step, once per day (after update-history.yml has written yesterday's
actual measurement):

  1. RESOLVE — any pending prediction whose target_date now has an actual
     measurement in history.json gets its error computed (|predicted -
     actual| for tmax/tmin, and precip for Open-Meteo) and is appended to
     forecast_verification.json (permanent, append-only scoreboard log).
  1b. REFRESH — re-score already-resolved days against the current archive.
     Predictions are never touched; only the measurement they are compared
     against follows history.json, which keeps correcting partial days after
     the fact. Without this the scoreboard freezes whatever the archive
     happened to say the morning after, and publishes errors nobody made.
  2. PREDICT — fetch tomorrow's ARSO forecast (via the Cloudflare Worker,
     which proxies vreme.arso.gov.si — ARSO blocks cloud IPs) and Open-Meteo
     forecast, and log both as a new pending prediction to be resolved
     tomorrow. Our own local MOS model (tools/predict_recica_mos.py, read from
     napoved-modela.json) is logged as a third contestant and scored by exactly
     the same rule — the whole point is that it can lose in public. ECMWF AIFS
     (the AI model Windy shows as its 15-day ECMWF extension) is the fourth,
     fetched from the same Open-Meteo endpoint with models=ecmwf_aifs025_single.

Za ARSO in Open-Meteo semafor nima zgodovine za nazaj: ARSO ne objavlja arhiva
preteklih napovedi, Open-Meteo pa smo tu začeli beležiti sproti. AIFS je izjema
— Open-Meteo hrani arhiv preteklih napovedi (*_previous_dayN), zato ga je
tools/backfill_aifs_verification.py napolnil za nazaj do prvega dne semaforja.
Ti zapisi imajo src "archive"; sproti zabeleženi imajo "live".

State:
  tools/.forecast_pending.json    — predictions awaiting resolution
  forecast_verification.json      — resolved verification records (public)

Usage:
  python3 tools/verify_forecasts.py
"""
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
LAT, LON = seo.LAT, seo.LON
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-ForecastVerify/1.0; +https://meteorec.si)"}

PENDING_PATH = os.path.join(ROOT, "tools", ".forecast_pending.json")
VERIFICATION_PATH = os.path.join(ROOT, "forecast_verification.json")
MODEL_FORECAST_PATH = os.path.join(ROOT, "napoved-modela.json")

WET_DAY_MM = 0.2  # isti prag kot pri učenju modela (train_recica_mos.py)

# ECMWF AIFS — AI model, ki ga ECMWF operativno poganja od 25. 2. 2025 in ga
# Windy prikazuje kot 15-dnevni podaljšek modela ECMWF. Prek Open-Meteo je
# dostopen brez ključa. Ločljivost 0,25° (~28 km), 6-urni koraki: doline ne
# razreši, zato je tu predvsem merilo, koliko sinoptična veščina zaleže brez
# lokalne ločljivosti.
AIFS_MODEL = "ecmwf_aifs025_single"


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_arso_tomorrow(target_date):
    """ARSO day-ahead tmax/tmin, plus the place the forecast is actually for.

    ARSO has no forecast point for Rečica ob Savinji, so the Worker falls back
    to the nearest place on its list (Ljubno ob Savinji, ~9 km up the same
    valley). We record which one answered so the public page can say so
    instead of implying the forecast was issued for Rečica itself.
    """
    req = urllib.request.Request(f"{WORKER}/arso-forecast", headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    loc = (data.get("location") or {}).get("title")
    for day in data.get("days", []):
        if day.get("valid_date") == target_date:
            return {"tmax": day.get("tmax"), "tmin": day.get("tmin"), "loc": loc}
    return None


def fetch_open_meteo_tomorrow(target_date, model=None):
    """Open-Meteo napoved za `target_date`. Brez `model` je to privzeti seamless
    (pri nas ICON-D2 ~2 km); z `model` je to en sam imenovan model — tako gre po
    isti poti tudi AIFS in se meri po povsem istem pravilu."""
    q = {
        "latitude": LAT, "longitude": LON,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Europe/Ljubljana",
        "forecast_days": 3,
    }
    if model:
        q["models"] = model
    params = urllib.parse.urlencode(q)
    req = urllib.request.Request(f"https://api.open-meteo.com/v1/forecast?{params}", headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    d = data.get("daily", {})
    times = d.get("time", [])
    if target_date not in times:
        return None
    i = times.index(target_date)
    tmax = (d.get("temperature_2m_max") or [None] * len(times))[i]
    tmin = (d.get("temperature_2m_min") or [None] * len(times))[i]
    precip = (d.get("precipitation_sum") or [None] * len(times))[i]
    return {"tmax": tmax, "tmin": tmin, "precip": precip}


def err(pred, actual):
    if pred is None or actual is None:
        return None
    return round(abs(pred - actual), 1)


def fetch_model_tomorrow(target_date):
    """Napoved lastnega modela za `target_date` iz napoved-modela.json.

    Datoteko zapiše tools/predict_recica_mos.py v istem zagonu workflowa, malo
    pred tem skriptom. Če je ni (model še ni naučen, Open-Meteo je odpovedal),
    se preprosto ne zabeleži nič — semafor teče naprej z ostalima dvema viroma.
    """
    data = load_json(MODEL_FORECAST_PATH, None)
    if not data:
        return None

    # Datoteka mora biti od danes. Če je predvčerajšnja, je jutrišnji datum v njej
    # še vedno — a kot napoved za dva dni vnaprej. Zabeležili bi jo kot enodnevno
    # in model bi na semaforju tekmoval pod napačnim pogojem.
    stamp = (data.get("generated_at") or "")[:10]
    if stamp != datetime.date.today().isoformat():
        print(f"  ⚠ napoved-modela.json je z dne {stamp or '?'}, ne od danes — preskočeno.",
              file=sys.stderr)
        return None

    for day in data.get("days", []):
        if day.get("date") == target_date and day.get("lead") == 1:
            return {"tmax": day.get("tmax"), "tmin": day.get("tmin"),
                    "pop": day.get("pop"), "lead": day.get("lead"),
                    "model_version": data.get("model_version")}
    return None


def build_record(target, made_at, actual, arso, om, meteorec=None, aifs=None):
    """Assemble one verification record from a prediction + the measurement."""
    actual_tmax = actual.get("tempHigh")
    actual_tmin = actual.get("tempLow")
    actual_precip = actual.get("precipTotal")

    record = {
        "date": target,
        "made_at": made_at,
        "actual": {"tmax": actual_tmax, "tmin": actual_tmin, "precip": actual_precip},
    }
    if arso:
        record["arso"] = {
            "tmax": arso.get("tmax"), "tmin": arso.get("tmin"),
            "loc": arso.get("loc"),
            "err_tmax": err(arso.get("tmax"), actual_tmax),
            "err_tmin": err(arso.get("tmin"), actual_tmin),
        }
    if om:
        record["open_meteo"] = {
            "tmax": om.get("tmax"), "tmin": om.get("tmin"), "precip": om.get("precip"),
            "err_tmax": err(om.get("tmax"), actual_tmax),
            "err_tmin": err(om.get("tmin"), actual_tmin),
            "err_precip": err(om.get("precip"), actual_precip),
        }
    if aifs:
        record["aifs"] = {
            "tmax": aifs.get("tmax"), "tmin": aifs.get("tmin"), "precip": aifs.get("precip"),
            "model": aifs.get("model") or AIFS_MODEL,
            # "live" = zabeleženo dan prej kot vsi ostali viri; "archive" =
            # napolnjeno za nazaj iz arhiva napovedi. Razlika je majhna, a jo
            # zapišemo, da je na strani lahko povedana.
            "src": aifs.get("src") or "live",
            "err_tmax": err(aifs.get("tmax"), actual_tmax),
            "err_tmin": err(aifs.get("tmin"), actual_tmin),
            "err_precip": err(aifs.get("precip"), actual_precip),
        }
    if meteorec:
        wet = None if actual_precip is None else (1.0 if actual_precip >= WET_DAY_MM else 0.0)
        pop = meteorec.get("pop")
        record["meteorec"] = {
            "tmax": meteorec.get("tmax"), "tmin": meteorec.get("tmin"),
            "pop": pop, "lead": meteorec.get("lead"),
            "model_version": meteorec.get("model_version"),
            "err_tmax": err(meteorec.get("tmax"), actual_tmax),
            "err_tmin": err(meteorec.get("tmin"), actual_tmin),
            "wet": wet,
            # Brierjeva ocena za verjetnostno napoved padavin: (p − dejansko)².
            # Manjše je bolje; klimatologija doline je ~0,25.
            "brier": None if (pop is None or wet is None) else round((pop - wet) ** 2, 3),
        }
    return record


def refresh_actuals(verification, hist):
    """Re-sync resolved records against the station archive.

    A record is resolved the morning after its target date, but history.json
    keeps filling in: a day whose measurement was still partial when we read
    it gets corrected later by update_history.py. The prediction is frozen —
    that is the whole point of the scoreboard — but the measurement it is
    scored against must track the archive, or we publish an error that was
    never made. Missing archive days are left untouched.
    """
    changed = []
    for date, record in verification.items():
        actual = hist.get(date)
        if actual is None:
            continue
        fresh = build_record(
            date, record.get("made_at"), actual,
            record.get("arso"), record.get("open_meteo"), record.get("meteorec"),
            record.get("aifs"),
        )
        if fresh != record:
            old = (record.get("actual") or {}).get("tmax")
            new = (fresh.get("actual") or {}).get("tmax")
            verification[date] = fresh
            changed.append((date, old, new))
    return changed


def resolve_pending(pending, hist, verification):
    still_pending = []
    resolved = 0
    for entry in pending:
        target = entry["target_date"]
        actual = hist.get(target)
        if actual is None:
            # Not measured yet (or station gap) — keep waiting, but drop if
            # it's more than 5 days stale to avoid an ever-growing queue.
            made = entry.get("made_at", target)
            try:
                age = (datetime.date.today() - datetime.date.fromisoformat(made)).days
            except ValueError:
                age = 0
            if age <= 5:
                still_pending.append(entry)
            continue

        verification[target] = build_record(
            target, entry.get("made_at"), actual,
            entry.get("arso"), entry.get("open_meteo"), entry.get("meteorec"),
            entry.get("aifs"),
        )
        resolved += 1
    return still_pending, resolved


def main():
    today = datetime.date.today()
    tomorrow = (today + datetime.timedelta(days=1)).isoformat()

    hist = seo.load_history()
    pending = load_json(PENDING_PATH, [])
    verification = load_json(VERIFICATION_PATH, {})

    still_pending, resolved = resolve_pending(pending, hist, verification)
    print(f"[{today}] Razrešenih napovedi: {resolved}, v čakalni vrsti: {len(still_pending)}")

    changed = refresh_actuals(verification, hist)
    if changed:
        print(f"  Uskladitev z arhivom: popravljenih dni {len(changed)}")
        for date, old, new in changed:
            print(f"    {date}: dejanski maks. {old} → {new} °C")

    if any(e["target_date"] == tomorrow for e in still_pending):
        print(f"  Napoved za {tomorrow} je že zabeležena, preskačem.")
    else:
        arso = om = aifs = None
        try:
            arso = fetch_arso_tomorrow(tomorrow)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  ⚠ ARSO napoved nedosegljiva: {e}", file=sys.stderr)
        try:
            om = fetch_open_meteo_tomorrow(tomorrow)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  ⚠ Open-Meteo napoved nedosegljiva: {e}", file=sys.stderr)
        try:
            aifs = fetch_open_meteo_tomorrow(tomorrow, model=AIFS_MODEL)
            if aifs:
                aifs["model"] = AIFS_MODEL
                aifs["src"] = "live"
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  ⚠ AIFS napoved nedosegljiva: {e}", file=sys.stderr)
        meteorec = fetch_model_tomorrow(tomorrow)
        if meteorec is None:
            print("  ⚠ Napovedi lastnega modela ni — napoved-modela.json manjka ali je stara.",
                  file=sys.stderr)

        if arso or om or meteorec or aifs:
            still_pending.append({
                "target_date": tomorrow,
                "made_at": today.isoformat(),
                "arso": arso,
                "open_meteo": om,
                "meteorec": meteorec,
                "aifs": aifs,
            })
            print(f"  Zabeležena napoved za {tomorrow}: ARSO={'da' if arso else 'ne'}, "
                  f"Open-Meteo={'da' if om else 'ne'}, AIFS={'da' if aifs else 'ne'}, "
                  f"naš model={'da' if meteorec else 'ne'}")
        else:
            print("  ✗ Nobenega vira napovedi ni bilo mogoče pridobiti.", file=sys.stderr)

    save_json(PENDING_PATH, still_pending)
    save_json(VERIFICATION_PATH, verification)
    print(f"  → forecast_verification.json: {len(verification)} razrešenih dni")


if __name__ == "__main__":
    main()
