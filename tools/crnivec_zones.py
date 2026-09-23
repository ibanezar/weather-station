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

# Coni merilnika, levo (najboljše) proti desno (najslabše) — isti vrstni red
# kot na klasičnem "risk" merilniku. "mid" je sredina cone na polkrogu
# (180°=levo, 0°=desno, 90°=zgoraj) — uporabi ga needle_angle() v
# generate_crnivec_page.py.
ZONES = [
    {"id": "sonce",    "label": "SUHO K POPR",    "desc": "Popolnoma čisto, cesta je suha.",
     "color": "#16a34a", "mid": 157.5},
    {"id": "nekaj",    "label": "JE, PA NEKAJ",   "desc": "Nekaj snega ali ledu, zato previdno.",
     "color": "#eab308", "mid": 112.5},
    {"id": "verige",   "label": "VZEMI VERIGE",   "desc": "Sneg ali led na cesti, verige so priporočljive.",
     "color": "#ea580c", "mid": 67.5},
    {"id": "spolzko",  "label": "SPOLZKO, PAZI",  "desc": "Cesta je spolzka, vozite zelo previdno.",
     "color": "#dc2626", "mid": 22.5},
]


def pick_zone(weather):
    """Resnična izbira cone iz izračunanega vremena na Črnivcu (weather =
    passes["crnivec"]["weather"] iz winter_engine.py) — samo nalepka/barva
    je šala, uvrstitev ne."""
    temp = (weather or {}).get("temp_c")
    snow = (weather or {}).get("expected_snow_cm_24h") or 0
    if snow >= 2:
        return ZONES[2]  # verige
    if temp is not None and temp <= 0:
        return ZONES[3]  # spolzko
    if temp is not None and temp > 5:
        return ZONES[0]  # sonce
    return ZONES[1]  # nekaj vmes
