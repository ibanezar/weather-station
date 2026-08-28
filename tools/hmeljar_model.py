#!/usr/bin/env python3
"""
tools/hmeljar_model.py — SprayScore, PeronosporaRisk, PepelovkaRisk, WaterBalance,
StormRisk in Decision Engine za MeteoHmeljar — REFERENČNA implementacija.

MeteoHmeljar je za vse hmeljarje v dolini (klik na poljubno parcelo na karti,
glej /meteohmeljar/), ne en znan seznam parcel — zato v produkciji NE teče ta
datoteka, ampak njena JS podvojitev meteohmeljar/hmeljar.js, CLIENT-SIDE, na
zahtevo (Python ne teče v brskalniku; ni izvedljivo strežniško cron-generirati
stran za vsako od stotih možnih kliknjenih parcel v dolini). Ta datoteka
ostaja kot berljiva specifikacija formul in osnova za teste — če spremeniš
formulo/prag tu, popravi tudi v meteohmeljar/hmeljar.js (isto načelo kot
gasilec_model.py/app.js/gasilec.js, glej opombo na vrhu gasilec_model.py).

Namerno LOČENO od tools/generate_agrometeo_page.py (GDD, fenologija, grob
dolinski bolezenski indeks, škropilno okno za celo Zgornjo Savinjsko dolino) —
to je parcelno natančen engine z lastnim configom (operation_profile na
parcelo), ne dolinski povzetek. Kjer je formula namerno enaka (GDD₁₀/
fenologija — HOP_STAGES spodaj), je to zapisano kot komentar, ne uvoz.

Vse funkcije so čiste (brez I/O). Podrobna specifikacija formul (še vedno
veljavna — samo arhitektura okrog njih se je spremenila iz cron/YAML v
klik/karto): docs/meteohmeljar-v0.1-spec.md

GDD₁₀/fenologija ostaneta vezana na postajo (history.json) — vse parcele so v
istem delu doline kot IREICA1, in postajna zgodovina je za akumulacijo skozi
sezono bolj avtoritativna od kratkega Open-Meteo okna (isti razlog kot v
generate_agrometeo_page.py). SprayScore/PeronosporaRisk/PepelovkaRisk/
WaterBalance/StormRisk pa so vezani na TOČNE koordinate parcele (Open-Meteo),
ker so parcele lahko na različnih razdaljah od postaje in bi mešanje virov med
parcelami dalo neprimerljive rezultate.
"""

# ── fenologija (namerna kopija HOP_STAGES iz generate_agrometeo_page.py) ────

HOP_STAGES = [
    (0, 60, "Mirovanje", "💤"),
    (60, 150, "Odganjanje poganjkov", "🌱"),
    (150, 400, "Vzdolžna rast trt", "🌿"),
    (400, 600, "Stransko razvejanje", "🌾"),
    (600, 950, "Cvetenje in razvoj storžkov", "🌸"),
    (950, 1250, "Oblikovanje storžkov", "🍺"),
    (1250, float("inf"), "Tehnološka zrelost / obiranje", "🎉"),
]


def gdd10(hist, today):
    """Vsota efektivnih temperatur (baza 10 °C) od 1. januarja `today.year` do
    `today`, iz postajne zgodovine (history.json)."""
    year = today.year
    today_s = today.isoformat()
    total = 0.0
    for k in sorted(hist.keys()):
        if not (f"{year}-01-01" <= k <= today_s):
            continue
        v = hist[k]
        th, tl, ta = v.get("tempHigh"), v.get("tempLow"), v.get("tempAvg")
        avg = (th + tl) / 2 if (th is not None and tl is not None) else ta
        if avg is not None:
            total += max(0, avg - 10)
    return round(total)


def hop_stage(gdd10_value):
    for lo, hi, label, emoji in HOP_STAGES:
        if lo <= gdd10_value < hi:
            return lo, hi, label, emoji
    return HOP_STAGES[-1]


# ── operation_profile privzete vrednosti (§1.1 spec) ─────────────────────────
# NIČ od tega ni trdo kodirano v scoring funkcijah spodaj — vedno pride iz
# profila parcele (data/hmeljar_parcele.yaml). To so samo privzete vrednosti,
# ki jih parcela podeduje, če ne poda lastnega operation_profile.

DEFAULT_OPERATION_PROFILE = {
    "wind_optimal_kmh": 2,
    "wind_max_kmh": 8,
    "gust_max_kmh": 15,
    "temperature_min_c": 8,
    "temperature_max_c": 25,
    "temperature_shoulder_low_c": 12,
    "temperature_shoulder_high_c": 22,
    "rainfree_hours_required": 4,
    "rh_wet_leaf_pct": 95,
    "rh_taper_start_pct": 70,
    "wet_leaf_allowed": False,
    "precip_prob_gate_pct": 50,
    "precip_prob_taper_pct": 40,
}


def _lerp_down(x, lo, hi):
    """100 pri x<=lo, linearno proti 0 pri x>=hi."""
    if hi <= lo:
        return 100.0 if x <= lo else 0.0
    return max(0.0, min(100.0, 100.0 * (hi - x) / (hi - lo)))


def _lerp_up(x, lo, hi):
    """0 pri x<=lo, linearno proti 100 pri x>=hi."""
    if hi <= lo:
        return 100.0 if x >= hi else 0.0
    return max(0.0, min(100.0, 100.0 * (x - lo) / (hi - lo)))


def _get(hourly, key, idx, default=None):
    lst = hourly.get(key) or []
    return lst[idx] if idx < len(lst) else default


# ── SprayScore (§2 spec) ─────────────────────────────────────────────────────

def wind_component(wind, profile):
    if wind <= profile["wind_optimal_kmh"]:
        return 100.0
    return _lerp_down(wind, profile["wind_optimal_kmh"], profile["wind_max_kmh"])


def temp_component(temp, profile):
    lo_sh = profile["temperature_shoulder_low_c"]
    hi_sh = profile["temperature_shoulder_high_c"]
    if lo_sh <= temp <= hi_sh:
        return 100.0
    if temp < lo_sh:
        return _lerp_up(temp, profile["temperature_min_c"], lo_sh)
    return _lerp_down(temp, hi_sh, profile["temperature_max_c"])


def rh_component(rh, profile):
    if rh <= profile["rh_taper_start_pct"]:
        return 100.0
    return _lerp_down(rh, profile["rh_taper_start_pct"], profile["rh_wet_leaf_pct"])


def rainfree_component(hours_to_next_rain, profile):
    required = profile["rainfree_hours_required"]
    if hours_to_next_rain < required:
        return 0.0
    span = max(0.5 * required, 1e-6)
    return max(0.0, min(100.0, 100.0 * (hours_to_next_rain - required) / span))


def hours_to_next_rain(hourly, start_idx, profile, horizon=48):
    """Koliko ur od `start_idx` naprej do prve ure z verjetnostjo padavin nad
    `precip_prob_taper_pct` ali dejanskimi padavinami. Omejeno na `horizon`."""
    precip = hourly.get("precipitation") or []
    prob = hourly.get("precipitation_probability") or []
    n = min(max(len(precip), len(prob)), start_idx + horizon)
    for i in range(start_idx, n):
        p = precip[i] if i < len(precip) else None
        q = prob[i] if i < len(prob) else None
        if (p is not None and p > 0.1) or (q is not None and q > profile["precip_prob_taper_pct"]):
            return i - start_idx
    return horizon


def spray_score_hour(hourly, idx, profile):
    """SprayScore (0–100) za eno uro na indeksu `idx` v `hourly` (Open-Meteo
    hourly odgovor). Vrne (score, components) — components pove razlog izpada
    ali posamezne mehke komponente, za razlago v UI."""
    wind = _get(hourly, "wind_speed_10m", idx)
    gust = _get(hourly, "wind_gusts_10m", idx)
    precip = _get(hourly, "precipitation", idx)
    prob = _get(hourly, "precipitation_probability", idx)
    temp = _get(hourly, "temperature_2m", idx)
    rh = _get(hourly, "relative_humidity_2m", idx)

    if None in (wind, gust, precip, temp, rh):
        return 0.0, {"reason": "manjkajoč podatek"}

    # trdi izpadi (§2.1) — meje vedno iz profila, nič trdo kodirano
    if wind > profile["wind_max_kmh"]:
        return 0.0, {"reason": "veter"}
    if gust > profile["gust_max_kmh"]:
        return 0.0, {"reason": "sunki vetra"}
    if precip > 0.1 or (prob is not None and prob > profile["precip_prob_gate_pct"]):
        return 0.0, {"reason": "padavine"}
    if temp < profile["temperature_min_c"] or temp > profile["temperature_max_c"]:
        return 0.0, {"reason": "temperatura"}
    if not profile["wet_leaf_allowed"] and rh >= profile["rh_wet_leaf_pct"]:
        return 0.0, {"reason": "mokro listje"}

    htr = hours_to_next_rain(hourly, idx, profile)
    comps = {
        "veter": wind_component(wind, profile),
        "temperatura": temp_component(temp, profile),
        "vlaga": rh_component(rh, profile),
        "brez_dezja": rainfree_component(htr, profile),
    }
    return min(comps.values()), comps


def spray_score_series(hourly, profile, hours=168):
    """`hourly` mora biti že poravnan tako, da je indeks 0 = trenutna ura
    (glej slice_hourly() v generate_hmeljar_page.py)."""
    n = min(hours, len(hourly.get("time") or []))
    out = []
    for i in range(n):
        score, comps = spray_score_hour(hourly, i, profile)
        out.append({"time": hourly["time"][i], "score": round(score), "components": comps})
    return out


def tier(score):
    if score >= 70:
        return "green"
    if score >= 40:
        return "yellow"
    return "red"


def spray_windows(series):
    """Strnjena zaporedja istega nivoja (green/yellow/red) — brez premoščanja
    vrzeli (glej §2.3 spec: trda meja, ne zamegljen prehod)."""
    runs = []
    cur = None
    for i, pt in enumerate(series):
        t = tier(pt["score"])
        if cur and cur["tier"] == t:
            cur["end"] = pt["time"]
            cur["end_idx"] = i
            cur["hours"].append(pt)
        else:
            if cur:
                runs.append(cur)
            cur = {"tier": t, "start": pt["time"], "start_idx": i, "end": pt["time"], "end_idx": i, "hours": [pt]}
    if cur:
        runs.append(cur)
    return runs


def best_window(runs, within_hours=24, min_hours=3):
    """Najdaljši 🟢 niz dolg vsaj `min_hours`, ki se začne znotraj
    `within_hours` — pri enaki dolžini zmaga zgodnejši (jutranji
    veter/temperatura sta praviloma ugodnejša). Kratek osamljen 🟢 niz (npr.
    ena ura sredi sicer rdečega dneva) ni uporabno "okno" in se ne poroča."""
    candidates = [r for r in runs
                  if r["tier"] == "green" and r["start_idx"] < within_hours and len(r["hours"]) >= min_hours]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (len(r["hours"]), -r["start_idx"]))


def window_close_reason(series, run):
    """Razlog, zakaj se okno zapre — komponenta, ki je na prvi uri po robu
    najnižja (ali trdi izpad, če gre za to)."""
    nxt = run["end_idx"] + 1
    if nxt >= len(series):
        return None
    comps = series[nxt]["components"]
    if "reason" in comps:
        return comps["reason"]
    return min(comps, key=comps.get)


# ── PeronosporaRisk / PepelovkaRisk (§3 spec) ────────────────────────────────
# Pragi so prvi približek iz citirane literature (APS Journals za peronosporo,
# Oregon State model za pepelovko), NE validirani na slovenskih podatkih.
# "Meteorološka ugodnost", ne diagnoza — glej opombo v spec dokumentu §3.

def _wet_hours_stats(hourly, start, end):
    temps = hourly.get("temperature_2m") or []
    rh = hourly.get("relative_humidity_2m") or []
    precip = hourly.get("precipitation") or []
    is_day = hourly.get("is_day") or []
    ur_rh80 = 0
    wet_degree_hours = 0.0
    night_temps = []
    for i in range(start, end):
        t = temps[i] if i < len(temps) else None
        h = rh[i] if i < len(rh) else None
        p = precip[i] if i < len(precip) else None
        d = is_day[i] if i < len(is_day) else None
        if h is not None and h >= 80:
            ur_rh80 += 1
        wet = (h is not None and h >= 90) or (p is not None and p > 0)
        if wet and t is not None and 10 <= t <= 25:
            wet_degree_hours += t
        if d == 0 and t is not None:
            night_temps.append(t)
    night_avg = sum(night_temps) / len(night_temps) if night_temps else None
    return ur_rh80, wet_degree_hours, night_avg


def _night_temp_score(night_avg):
    if night_avg is None:
        return 50.0  # brez podatka (npr. ni nočnih ur v oknu) — nevtralno
    if 12 <= night_avg <= 20:
        return 100.0
    if night_avg < 12:
        return _lerp_up(night_avg, 5, 12)
    return _lerp_down(night_avg, 20, 27)


def _peronospora_period_score(hourly, start, end):
    ur_rh80, wet_degree_hours, night_avg = _wet_hours_stats(hourly, start, end)
    rh80_score = min(100.0, ur_rh80 / 16 * 100)
    # KALIBRACIJA — placeholder do validacije na dejanskih pojavih (glej spec §3.1)
    wet_score = min(100.0, wet_degree_hours / 150 * 100)
    night_score = _night_temp_score(night_avg)
    return 0.4 * rh80_score + 0.4 * wet_score + 0.2 * night_score


def peronospora_risk(hourly_trailing, hourly_forward):
    """`hourly_trailing`: zadnjih ~24h opazovanih ur. `hourly_forward`:
    naslednjih ~24-48h napovedanih ur. Trailing tehta več (0,6), ker je
    izmerjen, forward (0,4) je samo smeren (za trend)."""
    trailing = _peronospora_period_score(hourly_trailing, 0, len(hourly_trailing.get("time") or []))
    fwd_n = min(48, len(hourly_forward.get("time") or []))
    forward = _peronospora_period_score(hourly_forward, 0, fwd_n)
    return round(0.6 * trailing + 0.4 * forward)


def _pepelovka_period_score(hourly, start, end):
    temps = hourly.get("temperature_2m") or []
    rh = hourly.get("relative_humidity_2m") or []
    precip = hourly.get("precipitation") or []
    consecutive = 0
    max_consecutive = 0
    rain_mm = 0.0
    for i in range(start, end):
        t = temps[i] if i < len(temps) else None
        h = rh[i] if i < len(rh) else None
        p = precip[i] if i < len(precip) else None
        favorable = t is not None and 16 <= t <= 27 and t <= 28 and (h is None or h < 90)
        consecutive = consecutive + 1 if favorable else 0
        max_consecutive = max(max_consecutive, consecutive)
        if p:
            rain_mm += p
    score = min(100.0, max_consecutive / 6 * 100)
    if rain_mm >= 5:
        score *= 0.5  # dovolj padavin zmanjšuje tveganje (Oregon model)
    return score


def pepelovka_risk(hourly_trailing, hourly_forward):
    trailing = _pepelovka_period_score(hourly_trailing, 0, len(hourly_trailing.get("time") or []))
    fwd_n = min(48, len(hourly_forward.get("time") or []))
    forward = _pepelovka_period_score(hourly_forward, 0, fwd_n)
    return round(0.6 * trailing + 0.4 * forward)


def risk_label(pct):
    return "Nizko" if pct < 30 else "Zmerno" if pct < 60 else "Visoko"


# ── WaterBalance (§4 spec) ───────────────────────────────────────────────────
# Samo meteorološka bilanca (padavine - ETo) v v0.1, brez tal/Kc.

def daily_balance(precip, et0):
    if precip is None or et0 is None:
        return None
    return precip - et0


def cumulative_deficit(prev_cd, today_balance, today_rain):
    """cd[danes] = min(0, cd[včeraj] + bilanca(danes)); RESET na 0, če je
    danes padlo >=15mm (aproksimacija napolnitve talnega profila). `prev_cd`
    pride iz dnevnika (glej generate_hmeljar_page.py) — brez tega bi
    primanjkljaj lahko računali samo znotraj enega Open-Meteo okna."""
    if today_rain is not None and today_rain >= 15:
        return 0.0
    if today_balance is None:
        return prev_cd
    return min(0.0, prev_cd + today_balance)


def water_balance_trend(balance_7d_now, balance_7d_3d_ago):
    if balance_7d_3d_ago is None:
        return "neznano"
    delta = balance_7d_now - balance_7d_3d_ago
    if abs(delta) < 3:
        return "stabilno"
    return "izboljšuje se" if delta > 0 else "primanjkljaj narašča"


# ── StormRisk (§5 spec) ──────────────────────────────────────────────────────
# Filozofija je namerna kopija storm_threat_score() (generate_nevihte_page.py)
# — ne uvožena (drug generator) — prilagojena na 6-12h okno za eno parcelo.

def gust_risk(gust):
    if gust is None:
        return 0.0
    return _lerp_up(gust, 40, 90)  # PRVI PRIBLIŽEK za trelis — potrebna lokalna kalibracija


def precip_intensity_risk(precip_mm_h):
    if precip_mm_h is None:
        return 0.0
    return _lerp_up(precip_mm_h, 2, 20)


def thunder_risk(cape, precip_prob, precip):
    if cape is not None:
        return _lerp_up(cape, 500, 2500)
    # brez CAPE (fallback): posredna heuristika, jasno označena v UI
    if precip_prob is not None and precip is not None and precip_prob > 60 and precip > 5:
        return 100.0
    return 0.0


def storm_risk_hour(hourly, idx):
    gust = _get(hourly, "wind_gusts_10m", idx)
    precip = _get(hourly, "precipitation", idx)
    prob = _get(hourly, "precipitation_probability", idx)
    cape = _get(hourly, "cape", idx)
    comps = {
        "veter": gust_risk(gust),
        "naliv": precip_intensity_risk(precip),
        "nevihta": thunder_risk(cape, prob, precip),
    }
    return max(comps.values()), comps


STORM_ARSO_LABELS = {"veter": "veter", "naliv": "obilne padavine", "nevihta": "nevihte"}


def storm_summary(hourly_next12, official_warning_active):
    """`official_warning_active`: ali aktivno opozorilo ARSO (oranžno/rdeče,
    tip nevihte/veter/padavine) velja za območje parcele — izračuna klicatelj
    prek classify()/fetch_alerts() iz generate_arso_newsjack_post.py (glej
    §5 spec — uradno opozorilo dvigne oceno, nikoli je ne zniža ali prekrije)."""
    n = len(hourly_next12.get("time") or [])
    best_score, best_idx, best_driver = 0.0, None, None
    first_event_idx = None
    for i in range(n):
        score, comps = storm_risk_hour(hourly_next12, i)
        if official_warning_active:
            score = max(score, 80.0)
        if first_event_idx is None and score >= 50:
            first_event_idx = i
        if score > best_score:
            best_score, best_idx, best_driver = score, i, max(comps, key=comps.get)
    return {
        "max_score": round(best_score),
        "time_to_event_h": first_event_idx,
        "driver": STORM_ARSO_LABELS.get(best_driver, best_driver),
    }


# ── Decision Engine (§6 spec) ────────────────────────────────────────────────
# Deterministično, predlogno — BREZ LLM klica (operativno orodje, urno
# osveženo — zanesljivost/latenca/strošek LLM klica in ponovljivost tu niso
# sprejemljivi, isto načelo kot generate_forecast_test_post.py/invasive_watch.py).

def _fmt_hm(iso_time):
    return iso_time[11:16]


def decide(*, storm, best_win, spray_series, peronospora_prev, peronospora_now,
           pepelovka_prev, pepelovka_now, cumulative_deficit_now, deficit_threshold=-30.0):
    """Vrne največ 3 postavke, v prednostnem vrstnem redu (§6): nevarnost >
    škropilno okno > bolezenski preskok > vodni primanjkljaj."""
    items = []

    if storm["max_score"] >= 70:
        cas = f'čez ~{storm["time_to_event_h"]}h' if storm["time_to_event_h"] is not None else "danes"
        items.append({"type": "storm",
                       "text": f'⛈️ Nevarnost neurja {cas} — glavno tveganje: {storm["driver"]}.'})

    if best_win and len(best_win["hours"]) >= 3:
        reason = window_close_reason(spray_series, best_win)
        zapira = f' Zapira se zaradi: {reason}.' if reason else ""
        items.append({"type": "spray",
                       "text": f'🧪 Dobro škropilno okno: {_fmt_hm(best_win["start"])}–{_fmt_hm(best_win["end"])}.{zapira}'})

    for name, prev, now in (("Peronospora", peronospora_prev, peronospora_now),
                             ("Pepelovka", pepelovka_prev, pepelovka_now)):
        if prev is not None and now is not None:
            lp, ln = risk_label(prev), risk_label(now)
            if lp != ln:
                arrow = "↑" if now > prev else "↓"
                items.append({"type": "disease",
                               "text": f'🍃 {name}: tveganje {lp.lower()} {arrow} {ln.lower()}.'})

    if cumulative_deficit_now is not None and cumulative_deficit_now <= deficit_threshold:
        items.append({"type": "water",
                       "text": f'💧 Vodni primanjkljaj ({round(cumulative_deficit_now)} mm) presega prag ({round(deficit_threshold)} mm).'})

    return items[:3]
