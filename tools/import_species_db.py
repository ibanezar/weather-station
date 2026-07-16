#!/usr/bin/env python3
"""
tools/import_species_db.py — build species_rules.yaml from data/baza_gob.xlsx

The Excel workbook (50-species Zgornja Savinjska database) is the seed; this
script converts it into species_rules.yaml, which is the hand-editable source
of truth the model reads. Run manually whenever the workbook changes — NOT in
the daily CI workflow.

Everything the script *derives* (soil-temp window from the air-temp threshold,
rain thresholds, elevation band, geology affinity, temp-drop requirement) is
emitted with a "# TODO: kalibriraj" marker, so calibration targets stay visible.
Directly-sourced fields (season, air temp, mycorrhiza, doubles, edibility) are not
marked.

Usage:
  python3 tools/import_species_db.py            # regenerate species_rules.yaml
  python3 tools/import_species_db.py --stdout   # print YAML, don't write
"""
import argparse
import datetime as dt
import os
import re
import sys
import unicodedata

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "data", "baza_gob.xlsx")
OUT = os.path.join(ROOT, "species_rules.yaml")

# Column indices in the "Baza Gob" sheet (0-based), from the workbook header.
C_NAME_SL, C_NAME_LAT, C_EDIB, C_SEASON, C_AIRTEMP = 0, 1, 2, 3, 4
C_MYCO, C_SUBSTRATE, C_SOILPH, C_DOUBLES = 5, 6, 7, 8
C_ELEV, C_FREQ, C_GEOLOGY = 12, 13, 14
C_MOIST7, C_OPTTEMP = 15, 16

SL_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
             "jul": 7, "avg": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
MONTH_LAST = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
              7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

# Edibility categories that get a foraging index (everything else is reference /
# dangerous-double material only).
INDEXED_EDIBILITY = {"užitna", "pogojno užitna"}

# Terrain definitions — three productive geological terrains of the valley,
# plus the strictly-protected zones (no foraging).
TERRAINS = [
    ("kisla", "Kislo/vulkansko pogorje (Smrekovec)",
     "Silikatna kisla tla; dobro zadržujejo vlago. Kraljestvo jurčka in žametastega gobana."),
    ("bazicna", "Karbonatni masivi (Golte, Menina, Raduha)",
     "Apnenčasta bazična tla; hitreje se sušijo. Kraljestvo marele in poletnega gobana."),
    ("vlazna", "Rečni logi in dolinske terase",
     "Stalno vlažna tla ob Savinji in Dreti. Kraljestvo smrčkov in uhljevk."),
]

# Forecast spots, each tagged with a terrain. Logarska dolina is a strictly
# protected area (foraging forbidden) per the workbook — kept, but flagged so
# the model never ranks it as a picking spot.
LOCATIONS = [
    ("Rečica ob Savinji",   46.326, 14.921, 400,  "vlazna",  True,  False),
    ("Gozdovi nad Ljubnim", 46.348, 14.834, 700,  "kisla",   False, False),
    ("Smrekovško pogorje",  46.430, 14.860, 1300, "kisla",   False, False),
    ("Golte",               46.348, 14.840, 1300, "bazicna", False, False),
    ("Dobrovlje – Čreta",   46.300, 14.860, 900,  "bazicna", False, False),
    ("Logarska dolina",     46.392, 14.628, 750,  "vlazna",  False, True),
]


# ── parsing helpers ──────────────────────────────────────────────────────────

def slugify(name_lat):
    s = unicodedata.normalize("NFKD", name_lat).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "vrsta"


def parse_season(text):
    """'Sep – Nov' → ('09.01', '11.30'); 'Celotno leto' → whole year."""
    t = (text or "").strip().lower()
    if "celotno" in t or "vse leto" in t:
        return "01.01", "12.31"
    months = [SL_MONTHS[m] for m in re.findall(r"[a-zčšž]+", t) if m in SL_MONTHS]
    if len(months) >= 2:
        a, b = months[0], months[-1]
    elif len(months) == 1:
        a = b = months[0]
    else:
        return None, None
    return f"{a:02d}.01", f"{b:02d}.{MONTH_LAST[b]:02d}"


def parse_temp_range(text):
    """'8 – 15 °C' / '-2 do 8 °C' → (min, max)."""
    nums = [int(n) for n in re.findall(r"-?\d+", text or "")]
    if len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1])
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None


def parse_moisture(text):
    """'25-35' → low end 25 (mm, 7-day cumulative trigger)."""
    nums = [int(n) for n in re.findall(r"\d+", text or "")]
    return nums[0] if nums else 20


def derive_soil_temp(air_lo, air_hi, offset, shoulder):
    """Soil-temp trapezoid derived from the air-temp favourable band.
    Soil at 6-18 cm is cooler and more damped than air; offset/shoulder are
    calibration knobs. Clamped to a non-negative, monotonic trapezoid."""
    opt_low = air_lo + offset
    opt_high = air_hi + offset
    tmin = opt_low - shoulder
    tmax = opt_high + shoulder
    vals = [max(0.0, v) for v in (tmin, opt_low, opt_high, tmax)]
    # enforce min <= opt_low <= opt_high <= max after clamping
    for i in range(1, 4):
        vals[i] = max(vals[i], vals[i - 1])
    return [round(v, 1) for v in vals]


def derive_elevation(text):
    """Rough elevation band (m) from the free-text zone description."""
    t = (text or "").lower()
    if "vse viš" in t or "od ravnin" in t or "povsod" in t:
        return 300, 1600
    if any(k in t for k in ("gorsk", "alpsk", "višj", "hribovit", "predalpsk")):
        return 600, 1600
    if any(k in t for k in ("nižin", "ravnin", "dolin", "nižje", "log")):
        return 250, 900
    return 300, 1400


def derive_geology(geology, soil_ph):
    """Categorical terrain affinity from geology + soil-pH keywords."""
    t = f"{geology or ''} {soil_ph or ''}".lower()
    scores = {
        "kisla":   sum(k in t for k in ("kisl", "silikat", "vulkan", "igličev", "borovnic")),
        "bazicna": sum(k in t for k in ("apnen", "bazičn", "karbonat", "dolomit")),
        "vlazna":  sum(k in t for k in ("vlažn", "mokrot", "šotn", "barjansk", "ob rek", "log", "obrežj")),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "nevtralna"


def derive_frequency_factor(text):
    """Local-presence prior from the 'Pogostost v Zg. Savinjski' text. Keeps a
    weather-favourable but locally absent/rare species from topping the list.
    Calibration values — flagged TODO in the YAML."""
    t = (text or "").lower()
    if any(k in t for k in ("odsot", "praktično odsot", "povsem odsot")):
        return 0.2
    if "redk" in t or "redek" in t or "redka" in t:
        return 0.4
    if "manj pogost" in t:
        return 0.7
    if any(k in t for k in ("izjemno pogost", "zelo pogost", "množično", "obilno", "neizogibn")):
        return 1.0
    if "pogost" in t or "prisot" in t or "najdem" in t:
        return 0.9
    return 0.8


def derive_requires_temp_drop(season_start):
    """Late-season species (fruiting from August onward) treat night cooling
    as a trigger; earlier species do not. Heuristic — flagged for calibration."""
    try:
        return int(season_start.split(".")[0]) >= 8
    except (AttributeError, ValueError):
        return False


def split_list(text):
    """'Smreka, bukev, bor, hrast' → ['smreka','bukev','bor','hrast']."""
    if not text:
        return []
    return [p.strip().lower() for p in re.split(r"[,;/]| in ", text) if p.strip()]


# ── YAML emitter (hand-rendered to keep inline TODO comments) ─────────────────

def q(s):
    """Double-quoted YAML scalar with escaping."""
    s = "" if s is None else str(s).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", " ").strip()
    return f'"{s}"'


def yaml_list(items):
    return "[" + ", ".join(q(i) for i in items) + "]"


def build_yaml(species):
    L = []
    L.append("# species_rules.yaml — pravila gobarskega modela po vrstah")
    L.append("#")
    L.append("# AVTOMATSKO GENERIRANO iz data/baza_gob.xlsx prek")
    L.append("# tools/import_species_db.py. To datoteko lahko ročno urejaš in kalibriraš —")
    L.append("# regeneracija jo prepiše, zato spremembe pomeni prenesti tudi v bazo ali skript.")
    L.append("#")
    L.append("# Izpeljane vrednosti (talno-temp. okno, padavinski pragovi, višina, geološka")
    L.append("# afiniteta, nočna ohladitev) so označene '# TODO: kalibriraj'. Neposredno iz")
    L.append("# baze (sezona, zračni prag, mikoriza, dvojnice, užitnost) niso.")
    L.append(f"# Zadnja regeneracija: {dt.date.today().isoformat()} · {len(species)} vrst.")
    L.append("")

    # Global weights
    L.append("# Globalne uteži za izračun indeksa (0–100)")
    L.append("weights:")
    L.append("  soil_temp: 0.35        # ujemanje talne temp. z optimalnim oknom vrste")
    L.append("  rain_7d: 0.25          # kumulativne padavine 7 dni")
    L.append("  rain_14d: 0.15         # kumulativne padavine 14 dni")
    L.append("  soil_moisture: 0.10")
    L.append("  humidity: 0.08")
    L.append("  temp_drop: 0.07        # nočna ohladitev kot sprožilec")
    L.append("")

    # Scoring knobs
    L.append("# Globalni kalibracijski parametri točkovanja (veljajo za vse vrste).")
    L.append("scoring:")
    L.append("  rain:")
    L.append("    oversat_ratio: 3.0       # TODO: kalibriraj — večkratnik praga, kjer se začne prenamočenost")
    L.append("    oversat_max_ratio: 6.0   # TODO: kalibriraj — večkratnik praga, kjer je upad največji")
    L.append("    oversat_factor: 0.5      # TODO: kalibriraj — minimalni prispevek ob ekstremni namočenosti")
    L.append("  soil_moisture:")
    L.append("    dry: 0.12                # TODO: kalibriraj — pod tem prispevek 0")
    L.append("    full: 0.28               # TODO: kalibriraj — nad tem polni prispevek")
    L.append("  humidity:")
    L.append("    rh_low: 60               # TODO: kalibriraj")
    L.append("    rh_full: 85              # TODO: kalibriraj")
    L.append("    dewpoint_spread_full: 2.0  # TODO: kalibriraj")
    L.append("  temp_drop:")
    L.append("    window_days: 5           # TODO: kalibriraj")
    L.append("    min_drop_c: 3.0          # TODO: kalibriraj")
    L.append("    persist_days: 4          # TODO: kalibriraj")
    L.append("  elevation:")
    L.append("    out_of_range_factor: 0.7  # TODO: kalibriraj")
    L.append("  # Izpeljava talno-temp. okna iz zračnega praga (soil hladnejši/dušen od zraka).")
    L.append("  soil_temp_from_air:")
    L.append("    offset_c: -2.0           # TODO: kalibriraj — zamik zrak→tla")
    L.append("    shoulder_c: 4.0          # TODO: kalibriraj — širina ramen trapeza")
    L.append("  # Ujemanje geološke afinitete vrste s terenom lokacije.")
    L.append("  geology:")
    L.append("    match_factor: 1.15       # TODO: kalibriraj — afiniteta se ujema s terenom")
    L.append("    mismatch_factor: 0.75    # TODO: kalibriraj — afiniteta se NE ujema")
    L.append("    neutral_factor: 1.0      # vrsta brez izrazite geološke preference")
    L.append("")

    # Terrains
    L.append("# Geološki tereni doline (za geo-afiniteto v izračunu po lokaciji).")
    L.append("terrains:")
    for tid, name, note in TERRAINS:
        L.append(f"  - id: {tid}")
        L.append(f"    name_sl: {q(name)}")
        L.append(f"    note: {q(note)}")
    L.append("")

    # Locations
    L.append("# Napovedne točke. protected=true → zaščiteno območje, ne prikazuj kot nabiralno mesto.")
    L.append("locations:")
    for name, lat, lon, elev, terr, home, prot in LOCATIONS:
        L.append(f"  - name: {q(name)}")
        L.append(f"    lat: {lat}")
        L.append(f"    lon: {lon}")
        L.append(f"    elev_m: {elev}")
        L.append(f"    terrain: {terr}")
        L.append(f"    home: {'true' if home else 'false'}")
        L.append(f"    protected: {'true' if prot else 'false'}")
    L.append("")

    # Species
    L.append("# Vrste. gets_index=true dobijo gobarski indeks; ostale so referenca / dvojnice.")
    L.append("species:")
    for s in species:
        L.append(f"  - id: {s['id']}")
        L.append(f"    name_sl: {q(s['name_sl'])}")
        L.append(f"    name_lat: {q(s['name_lat'])}")
        L.append(f"    edibility: {q(s['edibility'])}")
        L.append(f"    gets_index: {'true' if s['gets_index'] else 'false'}")
        L.append(f"    frequency: {q(s['frequency'])}")
        L.append(f"    frequency_factor: {s['frequency_factor']}   # TODO: kalibriraj (lokalna prisotnost)")
        st = s["season"]
        L.append(f'    season: {{ start: "{st[0]}", end: "{st[1]}" }}')
        at = s["air_temp"]
        L.append(f"    air_temp: {{ min: {at[0]}, max: {at[1]} }}  # zračni prag iz baze")
        so = s["soil_temp"]
        L.append(f"    soil_temp: {{ min: {so[0]}, opt_low: {so[1]}, opt_high: {so[2]}, max: {so[3]} }}  # TODO: kalibriraj (izpeljano iz air_temp)")
        L.append(f"    rain_7d_min: {s['rain_7d_min']}        # TODO: kalibriraj (baza: vlaga 7d)")
        L.append(f"    rain_14d_min: {s['rain_14d_min']}       # TODO: kalibriraj")
        fl = s["fruiting_lag_days"]
        L.append(f"    fruiting_lag_days: {{ min: {fl[0]}, max: {fl[1]} }}  # TODO: kalibriraj")
        L.append(f"    mycorrhiza: {yaml_list(s['mycorrhiza'])}")
        L.append(f"    substrate: {q(s['substrate'])}")
        L.append(f"    soil_ph: {q(s['soil_ph'])}")
        L.append(f"    geology_affinity: {s['geology_affinity']}   # TODO: kalibriraj")
        L.append(f"    elevation_zone: {q(s['elevation_zone'])}")
        ep = s["elevation_pref_m"]
        L.append(f"    elevation_pref_m: {{ min: {ep[0]}, max: {ep[1]} }}  # TODO: kalibriraj")
        L.append(f"    requires_temp_drop: {'true' if s['requires_temp_drop'] else 'false'}   # TODO: kalibriraj")
        L.append(f"    doubles: {q(s['doubles'])}")
    L.append("")
    return "\n".join(L)


# ── main ─────────────────────────────────────────────────────────────────────

def read_species():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["Baza Gob"]
    rows = list(ws.iter_rows(values_only=True))
    out = []
    for r in rows[1:]:
        if not r[C_NAME_SL] or not r[C_NAME_LAT]:
            continue
        edib = (r[C_EDIB] or "").strip()
        season = parse_season(r[C_SEASON])
        air_lo, air_hi = parse_temp_range(r[C_AIRTEMP])
        if air_lo is None:
            air_lo, air_hi = 10, 18  # fallback, unlikely
        soil = derive_soil_temp(air_lo, air_hi, offset=-2.0, shoulder=4.0)
        rain7 = parse_moisture(r[C_MOIST7])
        elev_min, elev_max = derive_elevation(r[C_ELEV])
        out.append({
            "id": slugify(r[C_NAME_LAT]),
            "name_sl": r[C_NAME_SL],
            "name_lat": r[C_NAME_LAT],
            "edibility": edib,
            "gets_index": edib.lower() in INDEXED_EDIBILITY,
            "frequency": r[C_FREQ],
            "frequency_factor": derive_frequency_factor(r[C_FREQ]),
            "season": season if season[0] else ("01.01", "12.31"),
            "air_temp": (air_lo, air_hi),
            "soil_temp": soil,
            "rain_7d_min": rain7,
            "rain_14d_min": rain7 * 2,
            "fruiting_lag_days": (7, 14),
            "mycorrhiza": split_list(r[C_MYCO]),
            "substrate": r[C_SUBSTRATE],
            "soil_ph": r[C_SOILPH],
            "geology_affinity": derive_geology(r[C_GEOLOGY], r[C_SOILPH]),
            "elevation_zone": r[C_ELEV],
            "elevation_pref_m": (elev_min, elev_max),
            "requires_temp_drop": derive_requires_temp_drop(season[0]),
            "doubles": r[C_DOUBLES],
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="Build species_rules.yaml from data/baza_gob.xlsx")
    ap.add_argument("--stdout", action="store_true", help="print YAML, don't write file")
    args = ap.parse_args()

    if not os.path.exists(XLSX):
        print(f"✗ Baza ni najdena: {XLSX}", file=sys.stderr)
        sys.exit(1)

    species = read_species()
    indexed = sum(1 for s in species if s["gets_index"])
    yaml_text = build_yaml(species)

    if args.stdout:
        print(yaml_text)
        return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(yaml_text)
    print(f"→ {OUT}")
    print(f"  {len(species)} vrst · {indexed} z indeksom · {len(species) - indexed} referenca/dvojnice")


if __name__ == "__main__":
    main()
