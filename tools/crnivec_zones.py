#!/usr/bin/env python3
"""
tools/crnivec_zones.py — deljena klasifikacija con za prelaz Črnivec.

ZONES in pick_zone() rabita tako generate_crnivec_page.py (merilnik,
poročanje) kot generate_story_card.py (tema CRNIVEC — namig na humorno
stran ob nosilnih dneh). Zato živita tu, v lastnem modulu brez odvisnosti do
obeh: generate_crnivec_page.py uvaža dry_streak() iz generate_story_card.py,
zato bi obraten uvoz (generate_story_card.py -> generate_crnivec_page.py)
naredil krožno odvisnost med njima.
"""
import datetime
import json
import sys
import urllib.error
import urllib.request

# Coni merilnika, levo (najboljše) proti desno (najslabše) — isti vrstni red
# kot na klasičnem "risk" merilniku. "mid" je sredina cone na polkrogu
# (180°=levo, 0°=desno, 90°=zgoraj) — uporabi ga needle_angle() v
# generate_crnivec_page.py.
ZONES = [
    {"id": "sonce",    "label": "SUHO K POPR",    "desc": "Popolnoma čisto, cesta je suha.",
     "color": "#16a34a", "mid": 157.5},
    {"id": "nekaj",    "label": "TAK-TAK",   "desc": "Nekaj snega ali ledu, zato previdno.",
     "color": "#eab308", "mid": 112.5},
    {"id": "verige",   "label": "VZEMI VERIGE",   "desc": "Sneg ali led na cesti, verige so priporočljive.",
     "color": "#ea580c", "mid": 67.5},
    {"id": "spolzko",  "label": "SPOLZKO, PAZI",  "desc": "Cesta je spolzka, vozite zelo previdno.",
     "color": "#dc2626", "mid": 22.5},
]


# Meritev s cestne vremenske postaje DRSI na prelazu (postaja 201), prek
# /crnivec-drsi v worker.js (ta jo normalizira in predpomni 5 min). Postaja
# meri na 10 minut; starejša meritev od DRSI_MAX_AGE_MIN ni več "zdaj".
# Klientski kopiji: DRSI_MAX_AGE_MIN v generate_crnivec_page.py (JS) in
# _drsiCrnivec() v worker.js -- če spremeniš prag, ga spremeni povsod.
DRSI_URL = "https://weatherireica1.filip-eremita.workers.dev/crnivec-drsi"
DRSI_MAX_AGE_MIN = 40


# Višini postaj DRSI iz DEM (Open-Meteo Elevation API za njuni koordinati,
# preverjeno 25. 9. 2026) -- ne ugibani. Razlika 475 m je osnova za
# "Črnivec proti dolini" (valley_compare v generate_crnivec_page.py).
DRSI_ELEV_M = {"crnivec": 903, "gornji_grad": 428}


def _fresh(st):
    try:
        ts = datetime.datetime.fromisoformat(st["ts"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
    return (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 60 <= DRSI_MAX_AGE_MIN


def fetch_drsi_postaje():
    """Sveže meritve vseh postaj iz /crnivec-drsi ({"crnivec": {...},
    "gornji_grad": {...}}); postaja s staro meritvijo manjka. {} ob napaki."""
    try:
        req = urllib.request.Request(DRSI_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; Meteorec-Crnivec/1.0)"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        postaje = (data or {}).get("postaje") or {}
        return {k: v for k, v in postaje.items() if v and _fresh(v)}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, AttributeError) as e:
        print(f"⚠ DRSI meritve niso na voljo: {e}", file=sys.stderr)
        return {}


def fetch_drsi_crnivec():
    """Sveža meritev s prelaza ali None."""
    return fetch_drsi_postaje().get("crnivec")


def with_measurement(weather, drsi):
    """Kopija weather, v kateri je temp_c IZMERJENA na prelazu, kadar je
    meritev DRSI sveža (od 25. 9. 2026 indeks poganja meritev, ne model --
    model je ob inverziji ali ohlajanju zgrešil ničlo, ko je bilo na prelazu
    že pod njo). Sneg ostane iz modela (DRSI ga ne meri). temp_src pove
    prikazu, od kod je številka, da jo lahko pošteno označi."""
    w = dict(weather or {})
    t = (drsi or {}).get("temp_c")
    if t is not None:
        w["temp_c"] = t
        w["temp_src"] = "izmerjeno"
        w["temp_measured_at"] = drsi.get("ts")
    else:
        w["temp_src"] = "ocena"
    return w


def pick_zone(weather):
    """Resnična izbira cone iz vremena na Črnivcu (weather =
    passes["crnivec"]["weather"] iz winter_engine.py, s temperaturo iz
    meritve DRSI, kadar je -- glej with_measurement) — samo nalepka/barva
    je šala, uvrstitev ne. Kopiji: pickZoneLive (JS na strani) in
    /crnivec/znacka.svg v worker.js."""
    temp = (weather or {}).get("temp_c")
    snow = (weather or {}).get("expected_snow_cm_24h") or 0
    if snow >= 2:
        return ZONES[2]  # verige
    if temp is not None and temp <= 0:
        return ZONES[3]  # spolzko
    if temp is not None and temp > 5:
        return ZONES[0]  # sonce
    return ZONES[1]  # nekaj vmes
