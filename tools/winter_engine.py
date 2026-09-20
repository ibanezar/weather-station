#!/usr/bin/env python3
"""
tools/winter_engine.py — skupno podatkovno jedro za /zima/ podportal (Faza 1)

Enkrat dnevno izračuna zimske indekse iz Open-Meteo napovedi (edini napovedni
vir tukaj — brez notranjih meritev, glej CLAUDE.md) in jih zapiše v
data/winter-data.json, ki ga bereta oba spoke generatorja v
tools/generate_zima_page.py — isti vzorec kot calculate_frost_risk.py /
generate_frost_page.py (izračun ločen od izrisa strani, da se stran lahko
prerenderira brez ponovnega klica Open-Meteo).

Faza 1 (glej spec) je izračunala dva indeksa (snow_line, black_ice); Faza 2
dodaja heating_index (kurilni semafor) in fog (nad-meglo) — glej spodaj.

  - snow_line (meja sneženja) — REGIONALEN indeks, ne po krajih: ničta
    izoterma (Open-Meteo `freezing_level_height`) je sinoptična količina, ki
    se znotraj ~7 km dolinskega dna med Rečico in Ljubnim ne razlikuje.
    Zato ni v `locations[]` kot v prvotnem osnutku sheme, ampak samostojen
    vrhnji ključ z razčlenitvijo po VIŠINSKIH PASOVIH (dno doline -> planine),
    ne po naseljih — s tem stran dejansko odgovori "koliko snega više", ne le
    ponovi isto številko za vsak kraj v dolini.
  - black_ice (poledica) — nasprotno JE krajevno različen: cestna/mostna
    poledica je posledica sevalnega ohlajanja, ki se med že dokumentiranimi
    mikroklimami dolinskih krajev (glej NEARBY_TOWNS v generate_seo_pages.py
    — Nazarje ob sotočju je vlažnejše, Gornji Grad v zaprti stranski dolini
    ima močnejšo inverzijo …) dejansko razlikuje.
  - heating_index (kurilni semafor, Faza 2) in fog (nad-meglo, Faza 2) — oba
    REGIONALNA (isto načelo kot snow_line), izpeljana iz istega
    `compute_inversion_profile()`: primerjava temperature na postaji (2 m) s
    temperaturo na 925/850/700 hPa (Open-Meteo `geopotential_height_*hPa` +
    `temperature_*hPa`) poišče, do katere višine temperatura z višino NE
    pada — to je ocenjena zgornja meja temperaturne inverzije. Ta izračun
    prej NI obstajal nikjer v repozitoriju (preverjeno pred pisanjem) — ni ga
    torej treba uvažati, a heating_index in fog ga MORATA deliti (isto
    izhodišče), ne vsak svoje. `/kakovost-zraka/` (obstoječa stran, AQI iz
    Open-Meteo air-quality API) je namenoma NE podvojena tu — heating_index
    meri prevetrenost/inverzijo, ne koncentracijo delcev; kurilni semafor
    stran nanjo samo linka.

Lokacije za black_ice so postaja (Rečica ob Savinji) + 4 sosednja naselja iz
NEARBY_TOWNS (Mozirje, Nazarje, Ljubno ob Savinji, Gornji Grad) — koordinate,
nadmorske višine in mikroklimatski opisi so UVOŽENI, ne podvojeni (dva ločena
seznama istih krajev bi se prej ali slej razšla — isto načelo velja povsod v
repozitoriju). Solčava in Luče sta v NEARBY_TOWNS, a sta za Fazo 1 namenoma
izpuščeni (glej spec §3 "širi kasneje").

Meja sneženja/expected_cm ni uradna mikrofizika padavinske faze, ampak
uveljavljen sinoptičen približek: dejanska meja sneženja (snow level) je
navadno SNOW_LEVEL_OFFSET_M pod ničto izotermo (padavina se ob padanju skozi
podnasičen zrak ohlaja), s prehodnim pasom SNOW_BAND_HALFWIDTH_M, sneg pa iz
padavin (mm) pretvorjen s približkom SNOW_RATIO_CM_PER_MM (splošno znano
razmerje ~10:1). To je groba ocena, ne meritev — stran to eksplicitno pove
(glej generate_zima_page.py) namesto da bi kazala lažno natančnost.

Ground_temp_c za black_ice služi istemu namenu kot radiacijski popravek v
calculate_frost_risk.py (sevalno ohlajanje pod temperaturo zraka ob
jasnem/mirnem vremenu), a je NAMENOMA ločena, preprostejša implementacija —
tu ne ekstrapoliramo iz dejanskega ohlajanja postaje (frost model to počne za
en sam nocojšnji minimum), ampak iz napovedanih cloud_cover/wind_speed za
vsako izmed prihodnjih ur posebej, ker poledica potrebuje okno do +36h, ne
enega nočnega minimuma.

Piše: data/winter-data.json
Wired into: .github/workflows/zima-forecast.yml (pred generate_zima_page.py)

Usage:
  python3 tools/winter_engine.py [--dry-run]
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — NEARBY_TOWNS/LAPSE_RATE/LAT/LON/ELEV, uvoženo ne podvojeno

ROOT = seo.ROOT
LAT, LON, ELEV = seo.LAT, seo.LON, seo.ELEV
OUT_PATH = os.path.join(ROOT, "data", "winter-data.json")

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Ljubljana")
except Exception:
    LOCAL_TZ = datetime.timezone.utc

# ── Lokacije za black_ice: postaja + 4 naselja iz NEARBY_TOWNS (glej opombo zgoraj) ──
_TOWN_SLUGS_PHASE1 = {"vreme-mozirje", "vreme-nazarje", "vreme-ljubno-ob-savinji", "vreme-gornji-grad"}
BLACK_ICE_LOCATIONS = [
    {"id": "recica-ob-savinji", "name": "Rečica ob Savinji", "elevation_m": ELEV,
     "microclimate": "Dno doline pri postaji IREICA1 — referenčna lokacija za ostale."},
] + [
    {"id": t["slug"].replace("vreme-", ""), "name": t["town"], "elevation_m": t["elev"],
     "microclimate": t["microclimate"]}
    for t in seo.NEARBY_TOWNS if t["slug"] in _TOWN_SLUGS_PHASE1
]

# Višinski pasovi za meja sneženja — dno doline (postajna višina) do planinske
# ravni. NAMENOMA ne poimenujemo konkretnih vrhov s trdno višino (Golte,
# Menina, Raduha se med seboj razlikujejo za stotine metrov in bi bila trdna
# povezava število↔ime ugibana) — generate_zima_page.py jih omeni le opisno.
ELEVATION_BANDS_M = [ELEV, 600, 900, 1200, 1600]

SNOW_LEVEL_OFFSET_M = 250    # meja sneženja je navadno toliko pod ničto izotermo
SNOW_BAND_HALFWIDTH_M = 100  # prehodni pas (dež/sneg mešano) okoli te meje
SNOW_RATIO_CM_PER_MM = 1.0   # ~10:1 približek (1 mm padavin ≈ 1 cm svežega snega)

GROUND_OFFSET_MAX_C = 3.0    # največji sevalni primanjkljaj cestišča pod zrakom (jasno, mirno)
RANK_ORDER = ["nizko", "srednje", "visoko"]

# Tlačni nivoji za oceno inverzije (heating_index/fog) — 925 hPa (~750-800 m),
# 850 hPa (~1400-1500 m) in 700 hPa (~3000 m) so vsi zanesljivo nad postajo
# (366 m) in nad najvišjim NEARBY_TOWNS krajem (Solčava, 644 m).
INVERSION_LEVELS_HPA = [925, 850, 700]
INVERSION_TOLERANCE_C = 0.3  # temperatura, ki pade manj kot toliko, še šteje za "se ni ohladilo"
HEATING_WINDOW_H = 36
HEATING_MIDDAY_EXCLUDE = range(11, 17)  # sonce čez dan praviloma prevetri dolino
FOG_MORNING_HOURS = range(5, 10)


def log(msg):
    print(msg, file=sys.stderr)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def interp(x, x0, y0, x1, y1):
    if x is None:
        return None
    if x <= x0:
        return y0
    if x >= x1:
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def hval(hourly, key, i):
    arr = hourly.get(key) or []
    return arr[i] if 0 <= i < len(arr) else None


def fetch_open_meteo():
    hourly_vars = ["temperature_2m", "dew_point_2m", "cloud_cover", "wind_speed_10m",
                   "precipitation", "freezing_level_height"]
    for hpa in INVERSION_LEVELS_HPA:
        hourly_vars += [f"temperature_{hpa}hPa", f"geopotential_height_{hpa}hPa"]
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": ",".join(hourly_vars),
        "timezone": "Europe/Ljubljana",
        "forecast_days": 3,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Meteorec-WinterEngine/1.0)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def nearest_hour_index(times, now_local):
    """Najbližji indeks v urni seriji Open-Meteo (naivni lokalni čas, isti
    parsing vzorec kot overnight_avgs v calculate_frost_risk.py)."""
    now_naive = now_local.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    best_i, best_diff = None, None
    for i, t in enumerate(times):
        try:
            dt = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M")
        except ValueError:
            continue
        diff = abs((dt - now_naive).total_seconds())
        if dt == now_naive:
            return i
        if best_diff is None or diff < best_diff:
            best_i, best_diff = i, diff
    return best_i


# ── Meja sneženja ─────────────────────────────────────────────────────────

def snow_fraction(elevation_m, freezing_level_m):
    if freezing_level_m is None:
        return 0.0
    effective = freezing_level_m - SNOW_LEVEL_OFFSET_M
    lo, hi = effective - SNOW_BAND_HALFWIDTH_M, effective + SNOW_BAND_HALFWIDTH_M
    return clamp(interp(elevation_m, lo, 0.0, hi, 1.0), 0.0, 1.0)


def compute_snow_line(hourly, idx_now):
    times = hourly.get("time") or []
    fl = hourly.get("freezing_level_height") or []
    precip = hourly.get("precipitation") or []
    n = len(times)
    idx_24h = min(idx_now + 24, n - 1) if idx_now is not None else None

    current_line_m = fl[idx_now] if idx_now is not None and idx_now < len(fl) else None
    forecast_24h_m = fl[idx_24h] if idx_24h is not None and idx_24h < len(fl) else None

    window = range(idx_now, min(idx_now + 24, n)) if idx_now is not None else range(0)
    by_elevation = []
    for e in ELEVATION_BANDS_M:
        cm = 0.0
        for i in window:
            p = precip[i] if i < len(precip) else None
            f = fl[i] if i < len(fl) else None
            if p:
                cm += p * snow_fraction(e, f) * SNOW_RATIO_CM_PER_MM
        by_elevation.append({"elevation_m": e, "cm": round(cm, 1)})

    expected_cm_at_station = next((b["cm"] for b in by_elevation if b["elevation_m"] == ELEV), None)

    if current_line_m is None or forecast_24h_m is None:
        confidence = None
    else:
        swing = abs(forecast_24h_m - current_line_m)
        confidence = "visoka" if swing < 150 else ("srednja" if swing < 400 else "nizka")

    return {
        "current_line_m": round(current_line_m) if current_line_m is not None else None,
        "forecast_24h_m": round(forecast_24h_m) if forecast_24h_m is not None else None,
        "expected_cm_at_station": expected_cm_at_station,
        "expected_cm_by_elevation": by_elevation,
        "confidence": confidence,
    }


# ── Poledica (black ice) ──────────────────────────────────────────────────

def ground_temp_c(air_temp_c, cloud_pct, wind_kmh):
    """Groba ocena cestne/mostne temperature pod temperaturo zraka: jasno in
    mirno vreme sevalno ohladi cestišče do GROUND_OFFSET_MAX_C pod zrakom,
    oblačnost/veter primanjkljaj dušita proti nič — glej opombo na vrhu
    datoteke, zakaj to ni isti izračun kot v calculate_frost_risk.py."""
    if air_temp_c is None:
        return None
    offset = GROUND_OFFSET_MAX_C
    if cloud_pct is not None:
        offset *= clamp(interp(cloud_pct, 20, 1.0, 80, 0.0), 0.0, 1.0)
    if wind_kmh is not None:
        offset *= clamp(interp(wind_kmh, 5, 1.0, 20, 0.15), 0.0, 1.0)
    return air_temp_c - offset


def compute_black_ice_for_location(hourly, idx_now, elevation_m):
    times = hourly.get("time") or []
    temp = hourly.get("temperature_2m") or []
    dew = hourly.get("dew_point_2m") or []
    cloud = hourly.get("cloud_cover") or []
    wind = hourly.get("wind_speed_10m") or []
    precip = hourly.get("precipitation") or []
    n = len(times)
    elev_diff = elevation_m - ELEV

    risk_hours = []
    worst_rank, worst_ground, worst_dew = -1, None, None

    start = idx_now if idx_now is not None else 0
    end = min(start + 36, n)
    for i in range(start, end):
        t_air = temp[i] if i < len(temp) else None
        if t_air is None:
            continue
        # Isti gradient kot gen_nearby_town_pages v generate_seo_pages.py — uvožen, ne podvojen.
        t_air_loc = t_air - seo.LAPSE_RATE_C_PER_100M * elev_diff / 100
        c = cloud[i] if i < len(cloud) else None
        w = wind[i] if i < len(wind) else None
        d = dew[i] if i < len(dew) else None
        p_now = precip[i] if i < len(precip) else 0
        p_prev = precip[i - 1] if i > 0 and (i - 1) < len(precip) else 0

        g = ground_temp_c(t_air_loc, c, w)
        if g is None:
            continue

        cat = "nizko"
        if g <= 0.5:
            near_saturated = d is not None and d >= g - 1.0
            wet_then_freezing = (p_now or 0) > 0.1 or (p_prev or 0) > 0.1
            cat = "visoko" if (near_saturated or wet_then_freezing) else "srednje"
        elif g <= 1.5 and d is not None and d >= g - 1.0:
            cat = "srednje"

        if cat == "visoko":
            risk_hours.append(times[i])
        rank = RANK_ORDER.index(cat)
        if rank > worst_rank:
            worst_rank = rank
            worst_ground = round(g, 1)
            worst_dew = round(d, 1) if d is not None else None

    risk_level = RANK_ORDER[worst_rank] if worst_rank >= 0 else "nizko"
    return {
        "risk_level": risk_level,
        "risk_hours": risk_hours[:6],
        "affected_spots": ["mostovi", "senčni odseki", "stranske ceste"],
        "ground_temp_c": worst_ground,
        "dew_point_c": worst_dew,
    }


# ── Skupna ocena inverzije (heating_index + fog) ─────────────────────────

def compute_inversion_profile(hourly, i):
    """Vrne (inversion_top_m, inversion_strength_c) za eno uro. Sestavi profil
    postaja (2 m) -> 925 -> 850 -> 700 hPa in poišče najvišjo točko, do katere
    temperatura z višino NE pada (inverzija/izotermija) — to je ocenjena
    zgornja meja temperaturne inverzije (in s tem megle/nizke oblačnosti pod
    njo). Če se ohlaja že takoj nad tlemi, inverzije ni: vrne (ELEV, 0.0)."""
    t2m = hval(hourly, "temperature_2m", i)
    if t2m is None:
        return None, None
    profile = [(ELEV, t2m)]
    for hpa in INVERSION_LEVELS_HPA:
        h = hval(hourly, f"geopotential_height_{hpa}hPa", i)
        t = hval(hourly, f"temperature_{hpa}hPa", i)
        if h is not None and t is not None and h > profile[-1][0]:
            profile.append((h, t))

    top_h, top_t = profile[0]
    base_t = t2m
    strength = 0.0
    for h, t in profile[1:]:
        if t >= top_t - INVERSION_TOLERANCE_C:
            top_h, top_t = h, t
            strength = max(strength, t - base_t)
        else:
            break
    return (round(top_h) if strength > 0 else ELEV), round(strength, 1)


def compute_heating_index(hourly, idx_now, times):
    """Kurilni semafor: najslabša ocenjena prevetrenost v naslednjih
    HEATING_WINDOW_H urah, izven poldanskih ur (11-16), ko sonce dolino
    praviloma prevetri. Kombinira jakost inverzije in veter — isto načelo
    (interp/clamp pragovi) kot ground_temp_c zgoraj, ne nova formula
    "od nikoder"."""
    n = len(times)
    wind_arr = hourly.get("wind_speed_10m") or []
    start = idx_now if idx_now is not None else 0
    end = min(start + HEATING_WINDOW_H, n)

    risk_hours = []
    worst_rank, worst_strength, worst_wind = -1, None, None
    for i in range(start, end):
        try:
            hh = int(times[i][11:13])
        except (ValueError, IndexError):
            continue
        if hh in HEATING_MIDDAY_EXCLUDE:
            continue
        _, strength = compute_inversion_profile(hourly, i)
        if strength is None:
            continue
        wind = wind_arr[i] if i < len(wind_arr) else None
        calm = wind is not None and wind <= 8

        if strength >= 3.0 and calm:
            cat = "visoko"
        elif strength >= 1.5 or (strength > 0 and calm):
            cat = "srednje"
        else:
            cat = "nizko"

        if cat == "visoko":
            risk_hours.append(times[i])
        rank = RANK_ORDER.index(cat)
        if rank > worst_rank:
            worst_rank, worst_strength, worst_wind = rank, strength, wind

    level = RANK_ORDER[worst_rank] if worst_rank >= 0 else "nizko"
    advice = {
        "nizko": "Ni posebnih omejitev za kurjenje — zrak se dobro prevetri.",
        "srednje": "Zmerna inverzija — po možnosti uporabi suha, dobro osušena drva in ne kuri več, kot je nujno.",
        "visoko": ("Močna inverzija ob mirnem vetru — po možnosti odloži kurjenje na poznejši čas "
                   "ali dan z boljšo prevetrenostjo."),
    }[level]
    return {
        "level": level,
        "inversion_strength_c": worst_strength,
        "wind_kmh": worst_wind,
        "risk_hours": risk_hours[:6],
        "advice": advice,
    }


def compute_fog(hourly, idx_now, times):
    """Nad-meglo: ocenjena zgornja meja megle/nizke oblačnosti naslednje
    jutro, primerjana z višinami postaje + vseh NEARBY_TOWNS krajev (glej
    opombo v generate_zima_page.py, zakaj samo ti, brez ugibanih vrhov).

    Predstavniška ura znotraj FOG_MORNING_HOURS je tista z NAJMOČNEJŠO
    inverzijo, ne tista z najnižjim vrhom -- uro brez inverzije sploh
    (strength=0) compute_inversion_profile vrne kot (ELEV, 0.0), zato bi
    min() čez okno skoraj vedno padel na ELEV, brž ko ena sama ura v oknu
    nima inverzije, in indeks bi bil skoraj vedno neuporaben. Če NOBENA ura
    v oknu ne pokaže inverzije, to pove has_inversion=False namesto da bi
    primerjala višine proti smiselno neobstoječi megli."""
    n = len(times)
    morning_idxs = []
    for i in range(idx_now or 0, min((idx_now or 0) + 48, n)):
        try:
            hh = int(times[i][11:13])
        except (ValueError, IndexError):
            continue
        if hh in FOG_MORNING_HOURS:
            morning_idxs.append(i)
    if not morning_idxs:
        return None

    best_top, best_strength = ELEV, 0.0
    for i in morning_idxs:
        top, strength = compute_inversion_profile(hourly, i)
        if strength is not None and strength > best_strength:
            best_top, best_strength = top, strength

    has_inversion = best_strength > 0
    morning_date = times[morning_idxs[0]][:10]

    all_locs = [{"name": "Rečica ob Savinji", "elevation_m": ELEV}] + [
        {"name": t["town"], "elevation_m": t["elev"]} for t in seo.NEARBY_TOWNS
    ]
    locations = [
        {"name": l["name"], "elevation_m": l["elevation_m"],
         "above": (l["elevation_m"] > best_top) if has_inversion else None}
        for l in all_locs
    ]
    return {
        "has_inversion": has_inversion,
        "top_m": best_top if has_inversion else None,
        "morning_date": morning_date,
        "locations": locations,
    }


def main():
    dry = "--dry-run" in sys.argv[1:]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)

    try:
        om = fetch_open_meteo()
    except Exception as e:
        log(f"✗ Open-Meteo ni uspel: {e} -- puščam star data/winter-data.json.")
        return 0 if not dry else 1

    hourly = om.get("hourly") or {}
    times = hourly.get("time") or []
    idx_now = nearest_hour_index(times, now_local)
    if idx_now is None:
        log("✗ Ni bilo mogoče najti trenutne ure v napovedi -- puščam star data/winter-data.json.")
        return 0 if not dry else 1

    snow_line = compute_snow_line(hourly, idx_now)
    heating_index = compute_heating_index(hourly, idx_now, times)
    fog = compute_fog(hourly, idx_now, times)

    locations = []
    for loc in BLACK_ICE_LOCATIONS:
        black_ice = compute_black_ice_for_location(hourly, idx_now, loc["elevation_m"])
        locations.append({
            "id": loc["id"], "name": loc["name"], "elevation_m": loc["elevation_m"],
            "microclimate": loc["microclimate"],
            "indices": {"black_ice": black_ice},
        })

    out = {
        "generated_at": now_utc.isoformat(),
        "generated_at_local": now_local.strftime("%-d. %-m. %Y ob %H:%M"),
        "station": seo.STATION_ID,
        "snow_line": snow_line,
        "heating_index": heating_index,
        "fog": fog,
        "locations": locations,
    }

    worst = max((l["indices"]["black_ice"]["risk_level"] for l in locations),
                key=RANK_ORDER.index, default="nizko")

    if dry:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"data/winter-data.json: meja sneženja {snow_line['current_line_m']} m, "
          f"kurilni semafor {heating_index['level']}, najvišje tveganje poledice: {worst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
