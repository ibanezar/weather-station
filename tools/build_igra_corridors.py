#!/usr/bin/env python3
"""
tools/build_igra_corridors.py — sestavi igra/koridorji.json

Igra /igra/ ne leti več po eni sami osi. Vsak dan izbere KORIDOR glede na
veter — tako, kot pilot izbere smer preleta. Ta skript pripravi geometrijo
vseh koridorjev: potek, mejnike in višinski profil.

Zakaj ločen skript in ne del dnevnega generatorja: teren se ne spreminja z
vremenom. Zajem višin je enkraten, rezultat pa se commita kot igra/koridorji.json
in ga tools/generate_igra_page.py samo prebere. Dnevni tek tako nima odvisnosti
od Elevation API-ja in ene točke odpovedi manj.

VIŠINE — dvoje, ker je vir zanesljiv samo v dolini:
  * Dolinsko dno zajame Open-Meteo Elevation API vzdolž lomljenke skozi prave
    kraje. Tam je točen (preverjeno: Rečica 374 m, Mozirje 338 m, Celje 241 m).
  * Vzletišče Golte ta vir močno splošči — vrne ~705 m namesto ~1400 m (isto
    velja za Menino planino, 1077 m namesto ~1500 m). Zato je prvih nekaj
    kilometrov spusta z Golt pribito na objavljeno višino vzletišča in se
    zlije v DEM (`max` od obojega, da nikoli ne pademo pod dejanski teren).
    NE poskušaj tega nadomestiti s samim Elevation API-jem — preverjeno je,
    da gora ne vidi.

Posledica te omejitve: koridorji, ki prečkajo visokogorje (Raduha 2062 m,
Smrekovec 1577 m), so v igri LAŽJI od resničnosti, ker jim vir vrhove zniža.
To je na strani tudi napisano.

Uporaba:
  python3 tools/build_igra_corridors.py [--dry-run]
"""
import datetime
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "igra", "koridorji.json")

R_ZEMLJE = 6371.0
KORAK_M = 250                 # ločljivost profila
VZLET = {"ime": "Golte", "lat": 46.372, "lon": 14.805, "visina": 1400}
# Čez toliko kilometrov se spust z vzletišča zlije v DEM. ~310 m/km ustreza
# pobočju Golt proti dolini.
ZLIVANJE_KM = 4.5

# Koridorji: lomljenke skozi prave kraje. Vsak se začne na vzletišču.
# `konec_km` je nekaj čez zadnji mejnik, da let ni odrezan točno na njem.
KORIDORJI = [
    {
        "id": "celje",
        "ime": "Savinjska dolina proti Celju",
        "kratko": "proti Celju",
        "opis": "Klasičen prelet po dolini navzdol. Najdaljši koridor, "
                "najnižji teren — dolg dan gre lahko do konca.",
        "tocke": [
            ("Golte", 46.372, 14.805),
            # Ljubno ni okras: brez njega gre lomljenka naravnost z Golt na
            # Rečico in reže čez pobočje Golt (DEM tam pokaže 779 m pri 6 km),
            # kar je stena, ki je z drsenja z vzletišča ni mogoče preleteti.
            # Pravi prelet se spusti v dolino pri Ljubnem in šele nato po
            # Savinji navzdol.
            ("Ljubno", 46.3436, 14.8339),
            ("Rečica", 46.3258, 14.9211),
            ("Mozirje", 46.3376, 14.9605),
            ("Letuš", 46.2925, 14.9908),
            ("Braslovče", 46.2803, 15.0430),
            ("Polzela", 46.2812, 15.0733),
            ("Žalec", 46.2517, 15.1650),
            ("Celje", 46.2311, 15.2683),
        ],
        "rezerva_km": 2.3,
    },
    {
        "id": "solcava",
        "ime": "Zgornja Savinjska proti Solčavi",
        "kratko": "proti Solčavi",
        "opis": "Navzgor po dolini v gore. Kratek in zahteven: teren se dviga, "
                "dolina se oži, Logarska je slepa ulica.",
        "tocke": [
            ("Golte", 46.372, 14.805),
            ("Luče", 46.3541, 14.7479),
            ("Solčava", 46.4198, 14.6928),
            ("Logarska dolina", 46.3931, 14.6236),
        ],
        "rezerva_km": 1.7,
    },
    {
        "id": "kamnik",
        "ime": "Čez Gornji Grad in Menino proti Kamniku",
        "kratko": "proti Kamniku",
        "opis": "Čez Dreto in planoto. Vmes je greben, ki ga moraš preleteti "
                "z višino — brez enega dobrega dviga ne gre.",
        "tocke": [
            ("Golte", 46.372, 14.805),
            ("Gornji Grad", 46.2963, 14.8078),
            ("Kamnik", 46.2258, 14.6117),
        ],
        "rezerva_km": 2.0,
    },
    {
        "id": "crna",
        "ime": "Čez Raduho na Koroško",
        "kratko": "proti Črni",
        "opis": "Najkrajši in najbolj zoprn: čez gorsko pregrado na drugo "
                "stran. Brez visokega stropa sploh ne prideš čez.",
        "tocke": [
            ("Golte", 46.372, 14.805),
            ("Črna na Koroškem", 46.4703, 14.8503),
        ],
        "rezerva_km": 2.5,
    },
]


def razdalja(a, b):
    dn = math.radians(b[0] - a[0]) * R_ZEMLJE
    de = math.radians(b[1] - a[1]) * R_ZEMLJE * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dn, de)


def azimut(a, b):
    dn = math.radians(b[0] - a[0]) * R_ZEMLJE
    de = math.radians(b[1] - a[1]) * R_ZEMLJE * math.cos(math.radians((a[0] + b[0]) / 2))
    return (math.degrees(math.atan2(de, dn)) + 360) % 360


# Vir je ob gradnji vračal 503, kadar so klici prihitali drug za drugim, zato
# manjši kosi, premor med njimi in dolg odlog ob napaki. Skript teče redko, čas
# torej ni pomemben — zanesljivost je.
KOS = 50
PREMOR_S = 2.0
ODLOGI_S = [5, 15, 30, 60, 90]


def get(url):
    zadnja = None
    for odlog in ODLOGI_S + [None]:
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            zadnja = e
            if odlog is None:
                break
            print(f"    vir odklonil ({type(e).__name__}), počakam {odlog} s …", flush=True)
            time.sleep(odlog)
    raise zadnja


def visine(tocke):
    """Elevation API po kosih; vrne seznam višin za dane (lat, lon)."""
    out = []
    for i in range(0, len(tocke), KOS):
        kos = tocke[i:i + KOS]
        q = urllib.parse.urlencode({
            "latitude": ",".join(f"{a:.5f}" for a, _ in kos),
            "longitude": ",".join(f"{b:.5f}" for _, b in kos),
        })
        out += get(f"https://api.open-meteo.com/v1/elevation?{q}")["elevation"]
        if i + KOS < len(tocke):
            time.sleep(PREMOR_S)
    return out


def vzorci_poti(tocke, korak_km):
    """Točke vzdolž lomljenke na enakomeren korak + kumulativne razdalje vozlišč."""
    odseki = [razdalja(tocke[i], tocke[i + 1]) for i in range(len(tocke) - 1)]
    skupaj = sum(odseki)
    vozlisca, acc = [0.0], 0.0
    for s in odseki:
        acc += s
        vozlisca.append(acc)

    pts, d = [], 0.0
    while d <= skupaj + 1e-9:
        acc = 0.0
        for i, s in enumerate(odseki):
            if d <= acc + s or i == len(odseki) - 1:
                t = (d - acc) / s if s > 0 else 0.0
                a, b = tocke[i], tocke[i + 1]
                pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
                break
            acc += s
        d += korak_km
    return pts, vozlisca, skupaj, odseki


def sestavi(kor):
    imena = [t[0] for t in kor["tocke"]]
    koord = [(t[1], t[2]) for t in kor["tocke"]]
    korak_km = KORAK_M / 1000.0

    pts, vozlisca, skupaj, odseki = vzorci_poti(koord, korak_km)
    konec_km = round(skupaj + kor["rezerva_km"], 2)

    # Profil do konca koridorja (rezervo podaljšamo z zadnjo višino).
    n = int(round(konec_km / korak_km)) + 1
    dem = visine(pts)
    while len(dem) < n:
        dem.append(dem[-1])
    dem = dem[:n]

    # Spust z vzletišča: vir gore splošči, zato prvih ZLIVANJE_KM pribijemo na
    # objavljeno višino Golt in vzamemo max z DEM, da ne pademo pod teren.
    h = []
    for i, e in enumerate(dem):
        km = i * korak_km
        spust = VZLET["visina"] * max(0.0, 1.0 - km / ZLIVANJE_KM)
        h.append(int(round(max(e, spust))))

    mejniki = [{"km": round(vozlisca[i], 2), "ime": imena[i]} for i in range(len(imena))]

    # Odseki za projekcijo vetra: lomljenka nima enega samega azimuta, zato
    # generator hrbtnik računa kot z dolžino uteženo povprečje po odsekih.
    odseki_out = [{"dolzina_km": round(odseki[i], 3),
                   "azimut": round(azimut(koord[i], koord[i + 1]), 1)}
                  for i in range(len(odseki))]

    return {
        "id": kor["id"], "ime": kor["ime"], "kratko": kor["kratko"],
        "opis": kor["opis"],
        "azimut": round(azimut(koord[0], koord[-1]), 1),
        "odseki": odseki_out,
        "dolzina_km": round(skupaj, 2),
        "konec_km": konec_km,
        "najvisja_m": max(h), "najnizja_m": min(h),
        "mejniki": mejniki,
        "teren": {"korak_m": KORAK_M, "od_km": 0, "h": h},
    }


def main():
    dry = "--dry-run" in sys.argv
    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc)
                     .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "vzletisce": VZLET,
        "vir_visin": ("dolinsko dno: Open-Meteo Elevation API vzdolž lomljenke; "
                      "vzletišče Golte po objavljeni višini, ker ta vir gore splošči"),
        "koridorji": [],
    }
    for kor in KORIDORJI:
        print(f"  {kor['id']:10s} …", end=" ", flush=True)
        k = sestavi(kor)
        out["koridorji"].append(k)
        print(f"{k['dolzina_km']:5.1f} km · {len(k['teren']['h'])} vzorcev · "
              f"{k['najnizja_m']}–{k['najvisja_m']} m · azimut {k['azimut']:.0f}°")

    if dry:
        print("\n--dry-run: ne zapišem.")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"\n→ {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
