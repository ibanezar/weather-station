#!/usr/bin/env python3
"""
tools/winter_engine.py — skupno podatkovno jedro za /zima/ (MeteoZima) podportal

Enkrat dnevno izračuna zimske indekse iz Open-Meteo napovedi (edini napovedni
vir tukaj — brez notranjih meritev, glej CLAUDE.md) in jih zapiše v
data/winter-data.json, ki ga bereta vsi spoke generatorji v
tools/generate_zima_page.py — isti vzorec kot calculate_frost_risk.py /
generate_frost_page.py (izračun ločen od izrisa strani, da se stran lahko
prerenderira brez ponovnega klica Open-Meteo).

Faza 1 je izračunala dva indeksa (snow_line, black_ice); Faza 2 doda
heating_index (kurilni semafor) in fog (nad-meglo); Faza 3 doda vsakemu
indeksu 7-dnevni pregled (`daily`, glej group_by_day()), tekočo oceno snežne
odeje (snowpack, poenostavljen degree-day model — glej compute_snowpack) in
sezonski dnevnik (season — arhiv brez verifikacije, samo štetje dni po
kategoriji, glej compute_season_stats). Vse to piše v podatke tega vira, ne
kot nove ločene strani — generate_zima_page.py jih doda na obstoječe 5
strani (npr. season na hub, snowpack na novo /zima/snezna-odeja/).

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
SNOWPACK_PATH = os.path.join(ROOT, "data", "winter-snowpack.json")
HISTORY_PATH = os.path.join(ROOT, "data", "winter-history.json")
HISTORY_MAX_AGE_DAYS = 400  # nekaj sezon nazaj — isti rok kot frost-risk-history.json

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

# Znane vzpetine nad dolino, dovolj preverjene za /zima/nad-meglo/ (za razliko
# od ELEVATION_BANDS_M spodaj, ki namenoma ostajajo neimenovani pasovi) —
# Golte (~1400 m) in Menina planina (~1500 m) sta v tools/build_igra_corridors.py
# OBJAVLJENI/preverjeni višini vzletišč (Open-Meteo Elevation API ju napačno
# splošči na 705 m oz. 1077 m, glej opombo tam), Raduha (2062 m) in Smrekovec
# (1577 m) sta vrhova od tam, uporabljena za iste jadralne koridorje. Niso
# naselja (NEARBY_TOWNS), zato ločen seznam samo za to eno stran.
HIGH_POINTS = [
    {"name": "Golte", "elevation_m": 1400},
    {"name": "Menina planina", "elevation_m": 1500},
    {"name": "Smrekovec", "elevation_m": 1577},
    {"name": "Raduha", "elevation_m": 2062},
]

# Gorski prelazi za /zima/prevoznost-prelazov/ — ROČNO VZDRŽEVAN seznam, isti
# vzorec kot HYDRANT_OVERRIDES (fetch_hydrants.py) / CALIBRATION
# (import_species_db.py): ni javnega API-ja za stanje gorskih prelazov v
# Sloveniji, zato "status"/"status_checked" ostaneta None, dokler ju kdo
# ročno ne posodobi tu v kodi (z virom in datumom, isto načelo kot povsod v
# repozitoriju). Nadmorski višini in povezavi STA preverjeni (ne ugibani):
#   - Črnivec, 902 m: sl.wikipedia.org/wiki/Črnivec_(preval)
#   - Pavličevo sedlo, 1339 m: sl.wikipedia.org/wiki/Pavličevo_sedlo,
#     tudi na amzs.si/na-poti/alpski-prelazi/pavlicevo-sedlo-slovenija
# Vremenska ocena (compute_pass_weather) NI enako kot "status" — prva je
# izračunana (temperatura/sneg na tej višini, ista metoda kot povsod v tej
# datoteki), druga je dejansko stanje ceste, ki ga lahko pove samo nekdo, ki
# jo je pravkar videl.
PASSES = [
    {
        "id": "crnivec",
        "name": "Črnivec",
        "elevation_m": 902,
        "connects": "Kamniška Bistrica (Kamnik) ↔ Gornji Grad",
        "source": "https://sl.wikipedia.org/wiki/%C4%8Crnivec_(preval)",
        # Cestna vremenska postaja DRSI na prelazu (glej compute_pass_calibration).
        "drsi_station": 201,
        "status": None,
        "status_checked": None,
    },
    {
        "id": "pavlicevo-sedlo",
        "name": "Pavličevo sedlo",
        "elevation_m": 1339,
        "connects": "Logarska dolina ↔ Bela pri Črni (Avstrija) — mejni prehod",
        "source": "https://sl.wikipedia.org/wiki/Pavli%C4%8Devo_sedlo",
        "status": None,
        "status_checked": None,
    },
]


COMMUTE_HOURS = (6, 7, 8, 14, 15, 16)  # termina 6:00-8:00 in 14:00-16:00
COMMUTE_DAYS = 4                        # danes + 3 dni


def _calib_at(calib, time_iso):
    """Popravek (°C) za uro dneva iz ISO časa, 0 brez umeritve."""
    if not calib or not time_iso:
        return 0.0
    try:
        return calib["bias_by_hour"][int(time_iso[11:13])] or 0.0
    except (KeyError, IndexError, ValueError, TypeError):
        return 0.0


def compute_pass_weather(hourly, idx_now, elevation_m, calib=None):
    """Vremenska ocena NA VIŠINI prelaza — isti lapse-rate/snow_fraction kot
    povsod v tej datoteki, NE stanje ceste (glej opombo pri PASSES)."""
    t_now = hval(hourly, "temperature_2m", idx_now)
    temp_c = (t_now - seo.LAPSE_RATE_C_PER_100M * (elevation_m - ELEV) / 100) if t_now is not None else None

    times = hourly.get("time") or []
    precip = hourly.get("precipitation") or []
    fl = hourly.get("freezing_level_height") or []
    n = len(times)
    window = range(idx_now, min(idx_now + 24, n)) if idx_now is not None else range(0)
    snow_cm = sum((precip[i] or 0) * snow_fraction(elevation_m, fl[i] if i < len(fl) else None) * SNOW_RATIO_CM_PER_MM
                   for i in window if i < len(precip))
    # Vse padavine (dež + sneg) v istem oknu -- /crnivec/ jih na kartici "Sneg"
    # pokaže ločeno od novega snega (dva različna podatka, ne eno število).
    precip_mm = sum((precip[i] or 0) for i in window if i < len(precip))

    # Vhodi za seznam "Čez Črnivec zdaj" na /crnivec/ (generate_crnivec_page.py):
    # padavine ZADNJIH treh ur (vključno s tekočo — "je cesta mokra" je
    # vprašanje o tem, kar je že padlo, ne o napovedi) in surovi vhodi za
    # black_ice_category() za tekočo uro, da jih stran lahko zamenja z
    # izmerjenimi s postaje DRSI. Veter in rosišče sta DOLINSKA (model za
    # Rečico) -- stran ju uporabi samo, kadar meritve s prelaza ni.
    now = None
    if idx_now is not None:
        past = [i for i in range(idx_now - 2, idx_now + 1) if 0 <= i < len(precip)]
        p3 = sum((precip[i] or 0) for i in past)
        s3 = sum((precip[i] or 0) * snow_fraction(elevation_m, fl[i] if i < len(fl) else None)
                 * SNOW_RATIO_CM_PER_MM for i in past)
        bi = black_ice_category_for_hour(hourly, idx_now, elevation_m)
        now = {
            "precip_mm_3h": round(p3, 1),
            "snow_cm_3h": round(s3, 1),
            "precip_mm_now": hval(hourly, "precipitation", idx_now),
            "precip_mm_prev": hval(hourly, "precipitation", idx_now - 1) if idx_now > 0 else 0,
            "cloud_pct": hval(hourly, "cloud_cover", idx_now),
            "wind_kmh_valley": hval(hourly, "wind_speed_10m", idx_now),
            "dew_c_valley": hval(hourly, "dew_point_2m", idx_now),
            "black_ice": bi[0] if bi else None,
        }
    # Surovi urni vhodi za "Naslednjih 6 ur" na /crnivec/ -- stran iz njih
    # sama sestavi vozišče (black_ice_category) s temperaturo, popravljeno z
    # meritvijo DRSI, zato tu ni ocene, samo podatki. precip_3h/snow_3h sta
    # okno treh ur DO vključno te ure (isto kot "now" zgoraj).
    def hour_entry(i, h):
        t_i = hval(hourly, "temperature_2m", i)
        past = [j for j in range(i - 2, i + 1) if 0 <= j < len(precip)]
        return {
            "h": h,
            "time": times[i],
            "temp_c": round(t_i - seo.LAPSE_RATE_C_PER_100M * (elevation_m - ELEV) / 100
                            + _calib_at(calib, times[i]), 1) if t_i is not None else None,
            "precip_mm": hval(hourly, "precipitation", i),
            "snow_frac": round(snow_fraction(elevation_m, fl[i] if i < len(fl) else None), 2),
            "precip_mm_3h": round(sum((precip[j] or 0) for j in past), 1),
            "snow_cm_3h": round(sum((precip[j] or 0) * snow_fraction(elevation_m, fl[j] if j < len(fl) else None)
                                    * SNOW_RATIO_CM_PER_MM for j in past), 1),
            "precip_mm_prev": hval(hourly, "precipitation", i - 1),
            "cloud_pct": hval(hourly, "cloud_cover", i),
            "wind_kmh_valley": hval(hourly, "wind_speed_10m", i),
            "dew_c_valley": hval(hourly, "dew_point_2m", i),
        }

    nxt = [hour_entry(idx_now + h, h) for h in range(1, 7)
           if idx_now is not None and idx_now + h < n]

    # "Na poti v službo in domov" na /crnivec/: ure terminov COMMUTE_HOURS za
    # danes in naslednje dni (COMMUTE_DAYS), od tekoče ure naprej -- termin,
    # ki je že mimo, izpade, delno pretečen ostane s preostankom ur.
    commute = []
    if idx_now is not None and times:
        last_day = (datetime.date.fromisoformat(times[idx_now][:10])
                    + datetime.timedelta(days=COMMUTE_DAYS - 1)).isoformat()
        for i in range(idx_now, n):
            if times[i][:10] > last_day:
                break
            if int(times[i][11:13]) in COMMUTE_HOURS:
                commute.append(hour_entry(i, i - idx_now))
    return {
        "temp_c": round(temp_c, 1) if temp_c is not None else None,
        "expected_snow_cm_24h": round(snow_cm, 1),
        "precip_mm_24h": round(precip_mm, 1),
        "now": now,
        "next_hours": nxt,
        "commute_hours": commute,
        # Modelska temperatura ZDAJ z istim popravkom kot next_hours -- stran
        # iz nje in meritve izračuna, koliko se napoved še razlikuje od
        # meritve (glej forecast_hours v generate_crnivec_page.py).
        "temp_cal_c": (round(temp_c + _calib_at(calib, times[idx_now]), 1)
                       if (temp_c is not None and idx_now is not None) else None),
        "calib": calib,
        "special": compute_pass_special(hourly, idx_now, elevation_m, calib),
    }


def compute_pass_special(hourly, idx_now, elevation_m, calib=None):
    """"Posebne razmere" na /crnivec/: sneg po dnevih (preostanek danes +
    jutri) na višini prelaza, prvi začetek sneženja, meja sneženja med
    padavinami, najvišja verjetnost padavin v urah, ko bi snežilo, in
    poledica v 36 urah (compute_black_ice_for_location -- ista kot za
    kraje, ne nova). Vse iz istega hourly kot ostali indeksi; to je
    modelska napoved, ne stanje ceste, in tako jo stran tudi označi."""
    if idx_now is None:
        return None
    times = hourly.get("time") or []
    precip = hourly.get("precipitation") or []
    fl = hourly.get("freezing_level_height") or []
    n = len(times)
    today = times[idx_now][:10]
    tomorrow = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
    by_day = {today: 0.0, tomorrow: 0.0}
    snow_start, levels, probs = None, [], []
    for i in range(idx_now, min(idx_now + 48, n)):
        p = hval(hourly, "precipitation", i) or 0
        flv = fl[i] if i < len(fl) else None
        frac = snow_fraction(elevation_m, flv)
        cm = p * frac * SNOW_RATIO_CM_PER_MM
        day = times[i][:10]
        if day in by_day:
            by_day[day] += cm
        if cm >= 0.1 and snow_start is None:
            snow_start = times[i]
        if p >= 0.1 and flv is not None:
            levels.append(flv - SNOW_LEVEL_OFFSET_M)
        if frac >= 0.5:
            pp = hval(hourly, "precipitation_probability", i)
            if pp is not None:
                probs.append(pp)
    levels.sort()
    return {
        "snow_cm_by_day": [{"date": d, "cm": round(v, 1)} for d, v in by_day.items()],
        "snow_start": snow_start,
        "snow_level_m": round(levels[len(levels) // 2] / 50) * 50 if levels else None,
        "snow_prob_pct": max(probs) if probs else None,
        "black_ice": compute_black_ice_for_location(hourly, idx_now, elevation_m, calib),
    }


# ── Umerjanje temperature prelaza z meritvami DRSI ────────────────────────
# Temperatura prelaza je napoved za Rečico (366 m), preračunana z gradientom.
# Ponoči to ne drži: hladen zrak se nabira na dnu doline, prelaz je nad njim.
# Primerjava z meritvami postaje DRSI na Črnivcu (september 2026) je
# pokazala, da je tak model ponoči ~3 °C prehladen in podnevi ~1,5 °C
# pretopel -- in je v treh od štirih noči napovedal "visoko" nevarnost
# poledice, ko je bilo na prelazu 5-6 °C. Popravek po uri dneva iz zadnjih
# CALIB_DAYS dni je napako zunaj učnega obdobja zmanjšal z 2,1 na 1,0 °C
# (ponoči z 2,8 na 1,1 °C). Nov je vsak dan, torej sledi letnemu času.
DRSI_HISTORY_URL = "https://www.ceste.si/Vremenske/Vreme/vremenski_podatki"
CALIB_DAYS = 10          # en klic vrne največ ~1800 točk (10-min), 10 dni je ~1440
CALIB_MIN_SAMPLES = 3    # najmanj ur na uro dneva, sicer brez popravka za to uro


def _http_json(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Meteorec-WinterEngine/1.0)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def compute_pass_calibration(station_id, elevation_m, now_local):
    """Povprečno odstopanje (meritev − model) po uri dneva, zglajeno z
    sosednjima urama. Vrne None ob kakršnikoli napaki -- brez umeritve stran
    deluje naprej s surovim modelom (in tako tudi piše)."""
    try:
        frm = (now_local - datetime.timedelta(days=CALIB_DAYS)).strftime("%Y-%m-%dT00:00:00")
        to = now_local.strftime("%Y-%m-%dT%H:%M:%S")
        rows = _http_json(f"{DRSI_HISTORY_URL}?" + urllib.parse.urlencode({
            "weatherStationID": station_id, "fromDate": frm, "toDate": to, "queryCount": 2000}))
        meas = {}
        for r in rows or []:
            t, ts = r.get("outdoorTemperatureC"), str(r.get("timestamp") or "")
            if t is not None and len(ts) >= 13:
                meas.setdefault(ts[:13], []).append(float(t))
        om = _http_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": LAT, "longitude": LON, "hourly": "temperature_2m",
            "timezone": "Europe/Ljubljana", "past_days": CALIB_DAYS, "forecast_days": 1}))
        h = om.get("hourly") or {}
        bins = {hh: [] for hh in range(24)}
        errs = []
        for tm, tv in zip(h.get("time") or [], h.get("temperature_2m") or []):
            m = meas.get(tm[:13])
            if not m or tv is None:
                continue
            model = tv - seo.LAPSE_RATE_C_PER_100M * (elevation_m - ELEV) / 100
            d = sum(m) / len(m) - model
            bins[int(tm[11:13])].append(d)
            errs.append((int(tm[11:13]), d))
        raw = {hh: sum(v) / len(v) for hh, v in bins.items() if len(v) >= CALIB_MIN_SAMPLES}
        if len(raw) < 20:
            log(f"umeritev prelaza: premalo meritev ({len(raw)}/24 ur) -- brez popravka")
            return None
        bias = []
        for hh in range(24):
            near = [raw[(hh + k) % 24] for k in (-1, 0, 1) if (hh + k) % 24 in raw]
            bias.append(round(sum(near) / len(near), 2) if near else 0.0)
        mae_raw = sum(abs(d) for _, d in errs) / len(errs)
        mae_cal = sum(abs(d - bias[hh]) for hh, d in errs) / len(errs)
        log(f"umeritev prelaza (DRSI {station_id}): {len(errs)} ur, MAE {mae_raw:.2f} -> {mae_cal:.2f} °C")
        return {"source": "DRSI", "station": station_id, "days": CALIB_DAYS, "hours": len(errs),
                "bias_by_hour": bias, "mae_raw_c": round(mae_raw, 2), "mae_cal_c": round(mae_cal, 2)}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, KeyError, TypeError) as e:
        log(f"umeritev prelaza ni uspela ({e}) -- brez popravka")
        return None

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

# Snežna odeja: poenostavljen degree-day model (dodaj nov sneg, odštej
# taljenje) — glej opombo pri compute_snowpack(), zakaj je to TEKOČA OCENA,
# ne meritev, in zakaj lahko čez sezono brez senzorja za umerjanje zaide.
MELT_CM_PER_DEGREE_DAY = 0.6  # groba literaturna vrednost za odprt, temperaten sneg

# Tlačni nivoji za oceno inverzije (heating_index/fog) — 925 hPa (~750-800 m),
# 850 hPa (~1400-1500 m) in 700 hPa (~3000 m) so vsi zanesljivo nad postajo
# (366 m) in nad najvišjim NEARBY_TOWNS krajem (Solčava, 644 m).
INVERSION_LEVELS_HPA = [925, 850, 700]
INVERSION_TOLERANCE_C = 0.3  # temperatura, ki pade manj kot toliko, še šteje za "se ni ohladilo"
HEATING_WINDOW_H = 36
HEATING_MIDDAY_EXCLUDE = range(11, 17)  # sonce čez dan praviloma prevetri dolino
FOG_MORNING_HOURS = range(5, 10)
DAILY_FORECAST_DAYS = 7


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


def compute_hourly_48h(hourly, times, idx_now):
    """Surova urna serija (6 ur nazaj za kontekst + 48 ur naprej) za graf
    'Naslednjih 48 ur' na hub strani — NAMENOMA ločena od group_by_day()
    zgoraj, ki agregira po koledarskih dnevih za 7-dnevne preglede; ta graf
    rabi posamezne ure, ne dnevnih povprečij. now_idx je indeks trenutne ure
    ZNOTRAJ te izrezane serije (ne v polni hourly), da ga generate_zima_page.py
    lahko neposredno uporabi za navpično črto "zdaj" brez ponovnega iskanja."""
    if idx_now is None:
        return None
    start = max(idx_now - 6, 0)
    end = min(idx_now + 48, len(times))
    idxs = list(range(start, end))
    if len(idxs) < 2:
        return None
    return {
        "now_idx": idx_now - start,
        "times": [times[i] for i in idxs],
        "temp_c": [hval(hourly, "temperature_2m", i) for i in idxs],
        "precip_mm": [hval(hourly, "precipitation", i) for i in idxs],
    }


def fetch_open_meteo():
    hourly_vars = ["temperature_2m", "dew_point_2m", "cloud_cover", "wind_speed_10m",
                   "precipitation", "freezing_level_height", "precipitation_probability"]
    for hpa in INVERSION_LEVELS_HPA:
        hourly_vars += [f"temperature_{hpa}hPa", f"geopotential_height_{hpa}hPa"]
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": ",".join(hourly_vars),
        "timezone": "Europe/Ljubljana",
        "forecast_days": DAILY_FORECAST_DAYS + 1,  # +1 rezerve, da idx_now sredi dneva ne odreže zadnjega dne
        # compute_snowpack_update potrebuje polnih zadnjih 24 ur NAZAJ od idx_now
        # -- brez tega bi urna serija ob jutranjem cron teku segala šele od
        # polnoči danes (par ur), ne polnega dne, in bi dnevno odejo sistematsko
        # podcenila (in podcenila taljenje) glede na uro, ob kateri teče cron.
        "past_days": 1,
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


def group_by_day(times, idx_now, n_days):
    """Razdeli urno serijo od idx_now naprej po koledarskih dnevih (lokalno) —
    dan 0 je danes (samo preostale ure), naslednjih n_days-1 so polni dnevi.
    Uporabljajo ga vse *_daily() funkcije spodaj, da se logika grupiranja po
    dnevih ne podvaja štirikrat."""
    days = []
    current_date = None
    for i in range(idx_now or 0, len(times)):
        d = times[i][:10]
        if d != current_date:
            if len(days) >= n_days:
                break
            days.append((d, []))
            current_date = d
        days[-1][1].append(i)
    return days[:n_days]


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
        "daily": compute_snow_daily(hourly, times, idx_now),
    }


def compute_snow_daily(hourly, times, idx_now):
    """Dnevni pregled meje sneženja za DAILY_FORECAST_DAYS dni — najnižja
    (najbolj snežna) meja tisti dan + pričakovan sneg na postaji, isti
    snow_fraction()/SNOW_RATIO_CM_PER_MM kot compute_snow_line zgoraj."""
    fl = hourly.get("freezing_level_height") or []
    precip = hourly.get("precipitation") or []
    out = []
    for date, idxs in group_by_day(times, idx_now, DAILY_FORECAST_DAYS):
        day_fl = [fl[i] for i in idxs if i < len(fl) and fl[i] is not None]
        cm = sum((precip[i] or 0) * snow_fraction(ELEV, fl[i] if i < len(fl) else None) * SNOW_RATIO_CM_PER_MM
                  for i in idxs if i < len(precip))
        out.append({
            "date": date,
            "line_m": round(min(day_fl)) if day_fl else None,
            "cm_at_station": round(cm, 1),
        })
    return out


# ── Snežna odeja ──────────────────────────────────────────────────────────

def load_snowpack():
    try:
        return json.load(open(SNOWPACK_PATH, encoding="utf-8"))
    except Exception:
        return {"updated": None, "depth_cm": {}}


def compute_snowpack_update(hourly, times, idx_now, prev_depths):
    """Posodobi tekočo oceno snežne odeje po višinskih pasovih (ELEVATION_BANDS_M):
    doda nov sneg zadnjih 24 ur (isti snow_fraction()/SNOW_RATIO_CM_PER_MM kot
    meja sneženja) in odšteje taljenje po poenostavljenem degree-day modelu
    (MELT_CM_PER_DEGREE_DAY na stopinjo-dan nad 0 °C, temperatura po pasu
    prilagojena z LAPSE_RATE_C_PER_100M).

    To NI mikrofizikalni snežni model in NI verificirana proti meritvi —
    postaja nima senzorja za sneg/tla (glej CLAUDE.md). Zadnjih 24 ur
    (ne napoved naprej) je edino okno, ki je za napovedni API najbližje
    "izmerjenemu" — kliče se enkrat dnevno (glej main(), zaščita pred
    dvojnim štetjem ob ročnem ponovnem zagonu isti dan). Ocena lahko čez
    sezono brez kontrolne točke zaide — stran to pove (generate_zima_page.py)."""
    start = max((idx_now or 0) - 24, 0)
    end = idx_now or 0
    updated = {}
    for e in ELEVATION_BANDS_M:
        new_snow, degree_days = 0.0, 0.0
        for i in range(start, end):
            t = hval(hourly, "temperature_2m", i)
            if t is not None:
                t_band = t - seo.LAPSE_RATE_C_PER_100M * (e - ELEV) / 100
                if t_band > 0:
                    degree_days += t_band / 24  # urni prispevek k stopinja-dnevu
            p = hval(hourly, "precipitation", i)
            fl = hval(hourly, "freezing_level_height", i)
            if p:
                new_snow += p * snow_fraction(e, fl) * SNOW_RATIO_CM_PER_MM
        melt = degree_days * MELT_CM_PER_DEGREE_DAY
        prev = prev_depths.get(str(e), 0.0) or 0.0
        updated[str(e)] = round(max(prev + new_snow - melt, 0.0), 1)
    return updated


def forward_snow_accum(hourly, times, idx_now, elevation_m, n_days):
    """Bruto pričakovan NOV sneg (brez taljenja) v naslednjih n_days dneh za
    en višinski pas — namenoma ločeno število od trenutne odeje (ne eno
    sestavljeno "odeja čez teden dni"), isto načelo kot povsod na strani
    ("dva vira/dve merili se ne smeta zliti v eno število")."""
    total = 0.0
    for _, idxs in group_by_day(times, idx_now, n_days):
        for i in idxs:
            p = hval(hourly, "precipitation", i)
            fl = hval(hourly, "freezing_level_height", i)
            if p:
                total += p * snow_fraction(elevation_m, fl) * SNOW_RATIO_CM_PER_MM
    return round(total, 1)


def compute_snowpack(hourly, times, idx_now, today_iso):
    """Vrne (snowpack_out, changed) — changed=False, če je bila odeja za
    danes že posodobljena (ne podvoji dodajanja/taljenja ob ročnem
    ponovnem zagonu istega dne)."""
    prev = load_snowpack()
    if prev.get("updated") == today_iso:
        depths = prev.get("depth_cm") or {}
        changed = False
    else:
        depths = compute_snowpack_update(hourly, times, idx_now, prev.get("depth_cm") or {})
        changed = True
    by_elevation = [
        {"elevation_m": e, "depth_cm": depths.get(str(e), 0.0),
         "new_snow_7d_cm": forward_snow_accum(hourly, times, idx_now, e, DAILY_FORECAST_DAYS)}
        for e in ELEVATION_BANDS_M
    ]
    return {"updated": today_iso, "depth_cm": depths, "by_elevation": by_elevation}, changed


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


def black_ice_category(t_air_c, cloud_pct, wind_kmh, dew_c, p_now_mm, p_prev_mm):
    """Čisto jedro ocene poledice iz ene ure vhodov, brez hourly niza.
    Ločeno od black_ice_category_for_hour() zato, da ga /crnivec/
    (generate_crnivec_page.py) lahko pokliče z IZMERJENO temperaturo, rosiščem
    in vetrom s postaje DRSI na prelazu namesto modelskih — ista formula, ne
    druga. Klientska kopija je blackIceLive() v generate_crnivec_page.py
    (namerna podvojitev, brskalnik ne more uvoziti Pythona); če spremeniš
    pragove tu, jih spremeni tudi tam."""
    g = ground_temp_c(t_air_c, cloud_pct, wind_kmh)
    if g is None:
        return None
    # Rosišče ne more biti nad temperaturo zraka. Za višje kraje pride
    # rosišče iz doline (model za Rečico), temperatura pa je preračunana na
    # višino -- brez te meje je bilo na 902 m rosišče 6 °C ob zraku 3 °C.
    d = min(dew_c, t_air_c) if dew_c is not None else None
    cat = "nizko"
    if g <= 0.5:
        near_saturated = d is not None and d >= g - 1.0
        wet_then_freezing = (p_now_mm or 0) > 0.1 or (p_prev_mm or 0) > 0.1
        cat = "visoko" if (near_saturated or wet_then_freezing) else "srednje"
    elif g <= 1.5 and d is not None and d >= g - 1.0:
        cat = "srednje"
    return cat, g


def black_ice_category_for_hour(hourly, i, elevation_m, t_offset=0.0):
    """Kategorija poledice za en kraj/eno uro — jedro tako za 36h pogled po
    krajih (compute_black_ice_for_location) kot za dnevni povzetek
    (compute_black_ice_daily); ne podvajaj te logike na klicnem mestu."""
    t_air = hval(hourly, "temperature_2m", i)
    if t_air is None:
        return None
    elev_diff = elevation_m - ELEV
    # Isti gradient kot gen_nearby_town_pages v generate_seo_pages.py — uvožen, ne podvojen.
    t_air_loc = t_air - seo.LAPSE_RATE_C_PER_100M * elev_diff / 100 + (t_offset or 0.0)
    d = hval(hourly, "dew_point_2m", i)
    result = black_ice_category(
        t_air_loc,
        hval(hourly, "cloud_cover", i),
        hval(hourly, "wind_speed_10m", i),
        d,
        hval(hourly, "precipitation", i),
        hval(hourly, "precipitation", i - 1) if i > 0 else 0,
    )
    if result is None:
        return None
    cat, g = result
    return cat, g, d


def compute_black_ice_for_location(hourly, idx_now, elevation_m, calib=None):
    """calib: popravek temperature po urah dneva (compute_pass_calibration) --
    samo za prelaz z meritvijo; kraji v dolini ga nimajo (None)."""
    times = hourly.get("time") or []
    n = len(times)

    risk_hours = []
    worst_rank, worst_ground, worst_dew = -1, None, None

    start = idx_now if idx_now is not None else 0
    end = min(start + 36, n)
    for i in range(start, end):
        result = black_ice_category_for_hour(hourly, i, elevation_m, _calib_at(calib, times[i]))
        if result is None:
            continue
        cat, g, d = result

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


def compute_black_ice_daily(hourly, times, idx_now):
    """Dnevni povzetek poledice za DAILY_FORECAST_DAYS dni — najslabša
    kategorija tisti dan MED VSEMI spremljanimi kraji (ne po kraju posebej,
    da graf ostane en sam, berljiv niz stolpcev; podrobnost po krajih ostane
    na 36h pogledu compute_black_ice_for_location)."""
    out = []
    for date, idxs in group_by_day(times, idx_now, DAILY_FORECAST_DAYS):
        worst_rank = -1
        for loc in BLACK_ICE_LOCATIONS:
            for i in idxs:
                result = black_ice_category_for_hour(hourly, i, loc["elevation_m"])
                if result is None:
                    continue
                rank = RANK_ORDER.index(result[0])
                if rank > worst_rank:
                    worst_rank = rank
        out.append({"date": date, "level": RANK_ORDER[worst_rank] if worst_rank >= 0 else "nizko"})
    return out


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


def hour_heating_category(hourly, i):
    """Kategorija kurilnega semaforja za eno uro (brez izločanja poldanskih
    ur — to naredi klicatelj) — jedro tako za compute_heating_index (36h
    pogled) kot compute_heating_daily (7-dnevni pregled)."""
    _, strength = compute_inversion_profile(hourly, i)
    if strength is None:
        return None
    wind = hval(hourly, "wind_speed_10m", i)
    calm = wind is not None and wind <= 8
    if strength >= 3.0 and calm:
        cat = "visoko"
    elif strength >= 1.5 or (strength > 0 and calm):
        cat = "srednje"
    else:
        cat = "nizko"
    return cat, strength, wind


HEATING_ADVICE = {
    "nizko": "Ni posebnih omejitev za kurjenje — zrak se dobro prevetri.",
    "srednje": "Zmerna inverzija — po možnosti uporabi suha, dobro osušena drva in ne kuri več, kot je nujno.",
    "visoko": ("Močna inverzija ob mirnem vetru — po možnosti odloži kurjenje na poznejši čas "
               "ali dan z boljšo prevetrenostjo."),
}


def compute_heating_index(hourly, idx_now, times):
    """Kurilni semafor: najslabša ocenjena prevetrenost v naslednjih
    HEATING_WINDOW_H urah, izven poldanskih ur (11-16), ko sonce dolino
    praviloma prevetri."""
    n = len(times)
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
        result = hour_heating_category(hourly, i)
        if result is None:
            continue
        cat, strength, wind = result

        if cat == "visoko":
            risk_hours.append(times[i])
        rank = RANK_ORDER.index(cat)
        if rank > worst_rank:
            worst_rank, worst_strength, worst_wind = rank, strength, wind

    level = RANK_ORDER[worst_rank] if worst_rank >= 0 else "nizko"
    return {
        "level": level,
        "inversion_strength_c": worst_strength,
        "wind_kmh": worst_wind,
        "risk_hours": risk_hours[:6],
        "advice": HEATING_ADVICE[level],
        "daily": compute_heating_daily(hourly, times, idx_now),
    }


def compute_heating_daily(hourly, times, idx_now):
    """Dnevni pregled kurilnega semaforja za DAILY_FORECAST_DAYS dni —
    najslabša kategorija tisti dan, izven poldanskih ur, isto pravilo kot
    compute_heating_index."""
    out = []
    for date, idxs in group_by_day(times, idx_now, DAILY_FORECAST_DAYS):
        worst_rank, worst_strength = -1, 0.0
        for i in idxs:
            try:
                hh = int(times[i][11:13])
            except (ValueError, IndexError):
                continue
            if hh in HEATING_MIDDAY_EXCLUDE:
                continue
            result = hour_heating_category(hourly, i)
            if result is None:
                continue
            cat, strength, _ = result
            rank = RANK_ORDER.index(cat)
            if rank > worst_rank:
                worst_rank, worst_strength = rank, strength
        out.append({
            "date": date,
            "level": RANK_ORDER[worst_rank] if worst_rank >= 0 else "nizko",
            "inversion_strength_c": round(worst_strength, 1),
        })
    return out


def compute_fog(hourly, idx_now, times):
    """Nad-meglo: ocenjena zgornja meja megle/nizke oblačnosti naslednje
    jutro, primerjana z višinami postaje + vseh NEARBY_TOWNS krajev + znanih
    vzpetin (HIGH_POINTS zgoraj — Golte, Menina planina, Smrekovec, Raduha;
    preverjene, ne ugibane, glej opombo pri HIGH_POINTS).

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

    top, strength = _fog_top_for_hours(hourly, morning_idxs)
    has_inversion = strength > 0
    morning_date = times[morning_idxs[0]][:10]

    all_locs = ([{"name": "Rečica ob Savinji", "elevation_m": ELEV}]
                + [{"name": t["town"], "elevation_m": t["elev"]} for t in seo.NEARBY_TOWNS]
                + HIGH_POINTS)
    locations = [
        {"name": l["name"], "elevation_m": l["elevation_m"],
         "above": (l["elevation_m"] > top) if has_inversion else None}
        for l in all_locs
    ]
    return {
        "has_inversion": has_inversion,
        "top_m": top if has_inversion else None,
        "morning_date": morning_date,
        "locations": locations,
        "daily": compute_fog_daily(hourly, times, idx_now),
    }


def _fog_top_for_hours(hourly, idxs):
    """Vrne (top_m, strength) za najmočnejšo inverzijo med danimi urami —
    isto načelo kot compute_fog uporablja za svoje FOG_MORNING_HOURS okno,
    tu izpostavljeno tudi za compute_fog_daily spodaj."""
    best_top, best_strength = ELEV, 0.0
    for i in idxs:
        top, strength = compute_inversion_profile(hourly, i)
        if strength is not None and strength > best_strength:
            best_top, best_strength = top, strength
    return best_top, best_strength


def compute_fog_daily(hourly, times, idx_now):
    """Jutranja meja megle za DAILY_FORECAST_DAYS dni — isto pravilo kot
    compute_fog, samo eno jutro na dan namesto enega samega okna."""
    out = []
    for date, idxs in group_by_day(times, idx_now, DAILY_FORECAST_DAYS):
        morning = [i for i in idxs if int(times[i][11:13]) in FOG_MORNING_HOURS]
        if not morning:
            out.append({"date": date, "has_inversion": False, "top_m": None})
            continue
        top, strength = _fog_top_for_hours(hourly, morning)
        has_inversion = strength > 0
        out.append({"date": date, "has_inversion": has_inversion, "top_m": top if has_inversion else None})
    return out


# ── Sezonski dnevnik ──────────────────────────────────────────────────────
# Enostaven arhivski dnevnik (isti upsert/prune vzorec kot
# calculate_frost_risk.py) — BREZ verifikacije proti meritvi (ni je, s čim bi
# te indekse preverili), samo štetje, koliko dni je bila letos katera
# kategorija dosežena. "Sezona" je od 1. novembra najbližje pretekle jeseni.

def load_history_log():
    try:
        return json.load(open(HISTORY_PATH, encoding="utf-8"))
    except Exception:
        return []


def upsert_history(entries, today_iso, snapshot):
    entries[:] = [e for e in entries if e["date"] != today_iso]
    entries.append(snapshot)
    entries.sort(key=lambda e: e["date"])


def prune_history(entries, today):
    cutoff = (today - datetime.timedelta(days=HISTORY_MAX_AGE_DAYS)).isoformat()
    entries[:] = [e for e in entries if e["date"] >= cutoff]


def season_start(today):
    year = today.year if today.month >= 11 else today.year - 1
    return datetime.date(year, 11, 1)


def compute_season_stats(entries, today):
    start = season_start(today)
    season = [e for e in entries if e["date"] >= start.isoformat()]
    return {
        "start_date": start.isoformat(),
        "days_logged": len(season),
        "heating_high_days": sum(1 for e in season if e.get("heating_level") == "visoko"),
        "black_ice_high_days": sum(1 for e in season if e.get("black_ice_level") == "visoko"),
        "snow_days": sum(1 for e in season if (e.get("snow_cm_at_station") or 0) > 0),
    }


def main():
    dry = "--dry-run" in sys.argv[1:]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)
    today_iso = now_local.date().isoformat()

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
    snowpack, snowpack_changed = compute_snowpack(hourly, times, idx_now, today_iso)
    passes = []
    for p in PASSES:
        calib = (compute_pass_calibration(p["drsi_station"], p["elevation_m"], now_local)
                 if p.get("drsi_station") else None)
        passes.append({**p, "weather": compute_pass_weather(hourly, idx_now, p["elevation_m"], calib)})
    hourly_48h = compute_hourly_48h(hourly, times, idx_now)

    locations = []
    for loc in BLACK_ICE_LOCATIONS:
        black_ice = compute_black_ice_for_location(hourly, idx_now, loc["elevation_m"])
        locations.append({
            "id": loc["id"], "name": loc["name"], "elevation_m": loc["elevation_m"],
            "microclimate": loc["microclimate"],
            "indices": {"black_ice": black_ice},
        })

    worst = max((l["indices"]["black_ice"]["risk_level"] for l in locations),
                key=RANK_ORDER.index, default="nizko")

    history_entries = load_history_log()
    upsert_history(history_entries, today_iso, {
        "date": today_iso,
        "snow_line_m": snow_line["current_line_m"],
        "snow_cm_at_station": snow_line["expected_cm_at_station"],
        "heating_level": heating_index["level"],
        "black_ice_level": worst,
        "fog_top_m": fog["top_m"] if fog and fog.get("has_inversion") else None,
    })
    prune_history(history_entries, now_local.date())
    season = compute_season_stats(history_entries, now_local.date())

    out = {
        "generated_at": now_utc.isoformat(),
        "generated_at_local": now_local.strftime("%-d. %-m. %Y ob %H:%M"),
        "station": seo.STATION_ID,
        "snow_line": snow_line,
        "heating_index": heating_index,
        "fog": fog,
        "snowpack": snowpack,
        "season": season,
        "passes": passes,
        "hourly_48h": hourly_48h,
        # Sedmi-dnevni povzetek poledice ni po kraju (glej compute_black_ice_daily) —
        # zato lasten vrhnji ključ, ne del "locations" (ki nosi 36h pogled po krajih).
        "black_ice_outlook": {"daily": compute_black_ice_daily(hourly, times, idx_now)},
        "locations": locations,
    }

    if dry:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if snowpack_changed:
        with open(SNOWPACK_PATH, "w", encoding="utf-8") as f:
            json.dump({"updated": snowpack["updated"], "depth_cm": snowpack["depth_cm"]}, f,
                      indent=2, ensure_ascii=False)
            f.write("\n")

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history_entries, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"data/winter-data.json: meja sneženja {snow_line['current_line_m']} m, "
          f"kurilni semafor {heating_index['level']}, najvišje tveganje poledice: {worst}, "
          f"odeja na postaji {snowpack['depth_cm'].get(str(ELEV), 0)} cm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
