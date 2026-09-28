#!/usr/bin/env python3
"""
tools/build_crnivec_igra_proga.py — ENKRATNO: prava proga za igro »Čez Črnivec«
(crnivec.si/igra/) iz OpenStreetMap.

Vzame cesto R1-225 (way ref=225) iz OSM prek Overpass, sestavi najkrajšo pot od
Stahovice do Gornjega Grada, doda višinski profil (Open-Meteo Elevation, DEM
90 m) in pot pretvori v progo igre. Zapiše crnivec-igra/proga.json, ki ga
generator (tools/generate_crnivec_igra.py) vdela v stran, igra
(crnivec-igra/voznja.js) pa iz njega zgradi cesto.

STISKANJE: 18 km ceste bi pri resnični hitrosti trajalo četrt ure, zato je
proga v igri krajša. Stisnjena NI enakomerno: enakomerno bi vsak ovinek
zožilo za isti faktor in serpentina s polmerom 15 m bi postala 2 m. Faktor je
odvisen od ukrivljenosti (compress()): ravnine in blagi ovinki se stisnejo
močno, ostri skoraj nič, in noben ovinek v igri ni ožji od K_GAME_MAX. KOTI
vseh zavojev ostanejo pravi (smer ceste je ista), zato je zaporedje ovinkov
tisto, ki ga pozna vsak, ki se vozi čez; dolžine med njimi pa niso.

Poleg geometrije zapiše kilometrino za vsak meter igre (km), višinski profil,
kilometer vrha in naselja ob cesti (iz imen OSM odsekov).

Podatki: © OpenStreetMap contributors (ODbL) — navedba je na strani igre.
Višine: Open-Meteo Elevation API (Copernicus DEM).

Usage:
  python3 tools/build_crnivec_igra_proga.py [--visine FILE]

  --visine FILE  JSON {"z": [...]} z že prenesenimi višinami (ista pot, vsakih
                 200 m) -- kadar Open-Meteo Elevation ni dosegljiv.
"""
import heapq
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "crnivec-igra", "proga.json")
OVERPASS_MIRRORS = [
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
QUERY = '[out:json][timeout:60];way["ref"="225"]["highway"](46.20,14.60,46.32,14.90);out geom;'
PLACES = ('[out:json][timeout:60];node["place"~"^(village|hamlet|town)$"](46.24,14.62,46.31,14.83);'
          'out;')
START = (46.2572, 14.6405)     # Stahovica
END = (46.2958, 14.8064)       # Gornji Grad
PASS_ELEV = 902
STEP_REAL = 10                 # vzorčenje prave poti (m)
GAME_LEN_TARGET = 3400         # dolžina proge v igri (m) -- ~3 min vožnje po suhem
A_COMPRESS = 150               # kako hitro ukrivljenost zmanjša stiskanje
K_GAME_MAX = 0.075             # najožji ovinek v igri: polmer ~13 m (volan zmore 10 m)
K_REF = 0.035                  # ukrivljenost (R 28 m), pri kateri igra doseže ~3/4 K_GAME_MAX
PLACE_MAX_M = 250              # naselje (OSM place) šteje za »ob cesti«, če je bližje
UA = {"User-Agent": "Meteorec/1.0 (crnivec.si; igra Cez Crnivec)"}  # glava mora biti ASCII


def hav(a, b):
    r = 6371000
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    x = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def fetch_osm(query=QUERY):
    for url in OVERPASS_MIRRORS:
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(), headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)["elements"]
        except Exception as e:  # noqa: BLE001 -- poskusi naslednje zrcalo
            print(f"⚠ {url}: {e}", file=sys.stderr)
    raise SystemExit("✗ Overpass ni dosegljiv.")


def route(els):
    """Najkrajša pot po grafu odsekov od START do END; vrne [(lat, lon, ime)]."""
    graph, pos, name = {}, {}, {}
    for e in els:
        nm = e.get("tags", {}).get("name")
        for n, g in zip(e["nodes"], e["geometry"]):
            pos[n] = (g["lat"], g["lon"])
            if nm and n not in name:
                name[n] = nm
        for a, b in zip(e["nodes"], e["nodes"][1:]):
            w = hav(pos[a], pos[b])
            graph.setdefault(a, []).append((b, w))
            graph.setdefault(b, []).append((a, w))
    s = min(pos, key=lambda n: hav(pos[n], START))
    t = min(pos, key=lambda n: hav(pos[n], END))
    dist, prev, pq = {s: 0}, {}, [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t:
            break
        if d > dist[u]:
            continue
        for v, w in graph.get(u, []):
            if d + w < dist.get(v, 1e18):
                dist[v], prev[v] = d + w, u
                heapq.heappush(pq, (d + w, v))
    path = [t]
    while path[-1] != s:
        path.append(prev[path[-1]])
    return [(*pos[n], name.get(n)) for n in reversed(path)]


def resample(path):
    cum = [0.0]
    for a, b in zip(path, path[1:]):
        cum.append(cum[-1] + hav(a[:2], b[:2]))
    out, j = [], 0
    for i in range(int(cum[-1] // STEP_REAL) + 1):
        s = i * STEP_REAL
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        f = (s - cum[j]) / max(1e-9, cum[j + 1] - cum[j])
        a, b = path[j], path[j + 1]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] if f < 0.5 else b[2]))
    return out, cum[-1]


def elevations(pts):
    q = urllib.parse.urlencode({"latitude": ",".join(f"{p[0]:.5f}" for p in pts),
                                "longitude": ",".join(f"{p[1]:.5f}" for p in pts)})
    for t in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    "https://api.open-meteo.com/v1/elevation?" + q, headers=UA), timeout=30) as r:
                return json.load(r)["elevation"]
        except Exception as e:  # noqa: BLE001 -- 429/časovna omejitev: počakaj in poskusi znova
            print(f"⚠ elevation: {e}", file=sys.stderr)
            time.sleep(20 * (t + 1))
    raise SystemExit("✗ Open-Meteo Elevation ni dosegljiv.")


def headings(pts):
    """Smer na zaslonu: h = atan2(-vzhod, sever) -- večji h zavije levo, isto kot
    v voznja.js (smer (-sin h, -cos h), sever gor)."""
    lat0 = pts[0][0]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110540
    xy = [((p[1] - pts[0][1]) * kx, (p[0] - pts[0][0]) * ky) for p in pts]
    h = [math.atan2(-(xy[i + 1][0] - xy[i][0]), xy[i + 1][1] - xy[i][1]) for i in range(len(xy) - 1)]
    un = [h[0]]
    for v in h[1:]:
        d = (v - un[-1] + math.pi) % (2 * math.pi) - math.pi
        un.append(un[-1] + d)
    # rahlo glajenje (3 vzorci = 30 m), da šum vozlišč OSM ne postane ovinek
    return [sum(un[max(0, i - 1):i + 2]) / len(un[max(0, i - 1):i + 2]) for i in range(len(un))]


def compress(k, c0):
    """Faktor stiskanja (pravi m na m igre) glede na ukrivljenost: ravnine c0,
    ostri ovinki ~1 (pod 1 se ovinek celo raztegne, da ni ožji od K_GAME_MAX)."""
    c = c0 / (1 + A_COMPRESS * abs(k))
    if abs(k) > 1e-6:
        c = min(c, K_GAME_MAX / abs(k))
    return max(0.6, c)


def k_game(k, c0):
    """Ukrivljenost v igri. Ostri ovinki obdržijo pravi kot (k * c); blagi so
    omejeni z nasičeno krivuljo -- tam se del kota izgubi, sicer bi bila pri
    7700° zavojev na 3,4 km vsa proga en sam ovinek."""
    g = K_GAME_MAX * math.tanh(abs(k) / K_REF)
    return math.copysign(min(abs(k) * compress(k, c0), g), k)


def to_game(h):
    kr = [(h[i + 1] - h[i]) / STEP_REAL for i in range(len(h) - 1)]

    def game_len(c0):
        return sum(STEP_REAL / compress(k, c0) for k in kr)
    lo, hi = 1.0, 80.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if game_len(mid) > GAME_LEN_TARGET:   # predolga -> stisni bolj
            lo = mid
        else:
            hi = mid
    c0 = (lo + hi) / 2
    # Po vzorcih prave poti: dolžina v igri in ukrivljenost; nato na 1 m igre.
    kg, kms = [], []
    pos, acc = 0.0, 0.0
    for i, k in enumerate(kr):
        dg = STEP_REAL / compress(k, c0)
        kk = k_game(k, c0)
        end = pos + dg
        while acc + 1 <= end + 1e-9:
            f = (acc - pos) / dg
            kg.append(kk)
            kms.append((i + max(0.0, f)) * STEP_REAL / 1000)
            acc += 1
        pos = end
    kg[-1] = 0.0
    return c0, h[0], kg, kms


def villages(pts, places):
    """Naselja ob cesti: OSM place (vas/zaselek/trg) bližje od PLACE_MAX_M,
    s kilometrom najbližje točke ceste. Imena odsekov (way name) niso naselja,
    ampak naslovi -- »Tirosek« velja za 10 km ceste."""
    out = []
    for pl in places:
        nm = pl.get("tags", {}).get("name")
        if not nm:
            continue
        best = min(range(len(pts)), key=lambda i: hav(pts[i][:2], (pl["lat"], pl["lon"])))
        d = hav(pts[best][:2], (pl["lat"], pl["lon"]))
        if d <= PLACE_MAX_M:
            out.append({"ime": nm, "km": round(best * STEP_REAL / 1000, 2),
                        "tip": pl["tags"].get("place")})
    return sorted(out, key=lambda v: v["km"])


def main():
    path = route(fetch_osm())
    places = fetch_osm(PLACES)
    pts, total = resample(path)
    total_km = total / 1000
    prof_pts = pts[::20]
    if "--visine" in sys.argv:
        with open(sys.argv[sys.argv.index("--visine") + 1], encoding="utf-8") as f:
            z = json.load(f)["z"]
        if len(z) != len(prof_pts):
            raise SystemExit(f"✗ --visine: {len(z)} točk, pot jih rabi {len(prof_pts)}")
    else:
        z = elevations(prof_pts)
    vrh_i = max(range(len(z)), key=lambda i: z[i])
    # DEM (90 m) vrh prelaza precení/podcení; cesta na vrhu je 902 m
    off = z[vrh_i] - PASS_ELEV
    profil = [[round(i * 20 * STEP_REAL / 1000, 2), round(v - off * max(0.0, 1 - abs(i - vrh_i) / 6))]
              for i, v in enumerate(z)]
    profil.append([round(total_km, 2), round(z[-1])])
    c0, h0, kg, kms = to_game(headings(pts))
    data = {
        "vir": "© OpenStreetMap contributors (ODbL), višine Open-Meteo (Copernicus DEM)",
        "cesta": "R1-225 Stahovica–Črnivec–Gornji Grad",
        "dolzina_km": round(total_km, 2),
        "vrh_km": profil[vrh_i][0],
        "c0": round(c0, 2),
        "h0": round(h0, 5),
        "k": [round(v, 5) for v in kg],
        "km": [round(v, 3) for v in kms],
        "profil": profil,
        "naselja": villages(pts, places),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    tight = sum(1 for v in kg if abs(v) > 1 / 30)
    kot = math.degrees(sum(abs(v) for v in kg))
    print(f"✓ {OUT}: {total_km:.2f} km ceste → {len(kg)} m igre (c0={c0:.1f}), vrh km {data['vrh_km']}, "
          f"ostrih ovinkov {tight} m, zavojev {kot:.0f}°, naselja: {[v['ime'] for v in data['naselja']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
