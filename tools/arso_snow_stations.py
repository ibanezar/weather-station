#!/usr/bin/env python3
"""
tools/arso_snow_stations.py -- ali ARSO arhiv ima opazovan sneg za postajo blizu Rečice?

Namen: MTR sneg (tools/train_sneg_mos.py) je učen na PROKSIJU, ker IREICA1 snega ne meri. Če ARSO-va padavinska
ali klimatološka postaja v Zgornji Savinjski dolini (nižina, < ~700 m) meri višino snežne odeje in novi sneg, je to
prva prava resnica. Skript:
  1. poišče seznam postaj ARSO arhiva (končna točka ni dokumentirana: preizkusi več kandidatov in izpiše odgovore),
  2. izbere postaje v radiju RADIUS_KM od Rečice (IREICA1),
  3. za vsako prenese dnevni arhiv (spremenljivke 85 padavine, 88 višina snežne odeje, 89 novi sneg; isto kot
     generate_crnivec_page.update_arso_cache) in izpiše pokritost: koliko dni in zim ima podatek o snegu,
  4. za postaje z dovolj podatka primerja proksi v Rečici z opazovanim novim snegom (kontingenčna tabela).

Teče v GitHub Actions (meteo.arso.gov.si iz peskovnika ni dosegljiv): .github/workflows/arso-snow-stations.yml.
Piše arso-snow-out/ (surovi odgovori, seznam postaj, poročilo). Notranjih meritev ne bere. Navedba vira ob
vsakem javnem prikazu: »Vir: Agencija Republike Slovenije za okolje« (CLAUDE.md, navedba vira ARSO).
ARSO obremenimo čim manj: nekaj deset zahtevkov s premorom.

usage: arso_snow_stations.py [--radius 35] [--out arso-snow-out]
"""
import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://meteo.arso.gov.si"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-SnowCheck/1.0; +https://meteorec.si)",
      "Referer": "https://meteo.arso.gov.si/met/sl/app/webmet/"}
LAT, LON = 46.325779, 14.921137          # IREICA1
FIRST_DATE = "2020-07-01"
PAUSE_S = 1.0
MAX_ELEV_M = 700                          # nižina; Črnivec (848 m) se vedno izpiše, a ni nižina
LIST_CANDIDATES = [
    "/webmet/archive/locations.xml?lang=si",
    "/webmet/archive/locations.xml?lang=si&type=1",
    "/webmet/archive/locations.xml?lang=si&type=daily",
    "/webmet/archive/locations.xml?lang=si&group=dailyData0&type=daily",
    "/webmet/archive/data.xml?lang=si&type=locations",
    "/met/sl/archive/",
    "/met/sl/app/webmet/",
]
APP_JS_PATTERN = r"(?:archive|locations?|\.xml|station|postaj)"


def get(path, timeout=60):
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, f"NAPAKA {e}"


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def pick(attrs, *names):
    low = {k.lower(): v for k, v in attrs.items()}
    for n in names:
        if n in low and low[n] not in (None, ""):
            return low[n]
    return None


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_stations(text):
    """Splošno razčlenjevanje: XML z elementi, ki imajo id + koordinate, ali JS objekti `{ ... id:"123" ... }`.
    Oblika ni dokumentirana, zato iščemo kar je videti kot postaja."""
    out, seen = [], set()
    try:
        root = ET.fromstring(text)
        for el in root.iter():
            a = dict(el.attrib)
            a.update({c.tag: (c.text or "") for c in el if len(c) == 0 and c.text})
            sid = pick(a, "id", "sid", "station_id")
            lat = num(pick(a, "lat", "latitude", "y"))
            lon = num(pick(a, "lon", "lng", "longitude", "x"))
            if sid and lat is not None and lon is not None and 45 < lat < 47.5 and 13 < lon < 17 and sid not in seen:
                seen.add(sid)
                out.append({"id": sid, "name": pick(a, "name", "title", "naziv", "ime") or el.tag,
                            "lat": lat, "lon": lon, "elev": num(pick(a, "alt", "elev", "h", "visina", "z")),
                            "attrs": a})
    except ET.ParseError:
        pass
    if out:
        return out
    for blob in re.findall(r"\{[^{}]*\}", text):
        pairs = dict(re.findall(r'(\w+)\s*:\s*"([^"]*)"', blob))
        pairs.update({k: v for k, v in re.findall(r"(\w+)\s*:\s*(-?\d+(?:\.\d+)?)\b", blob)})
        sid = pick(pairs, "id", "sid")
        lat = num(pick(pairs, "lat", "latitude", "y"))
        lon = num(pick(pairs, "lon", "lng", "longitude", "x"))
        if sid and lat is not None and lon is not None and 45 < lat < 47.5 and 13 < lon < 17 and sid not in seen:
            seen.add(sid)
            out.append({"id": sid, "name": pick(pairs, "name", "title", "naziv", "ime") or "?", "lat": lat, "lon": lon,
                        "elev": num(pick(pairs, "alt", "elev", "h", "visina", "z")), "attrs": pairs})
    return out


def parse_daily(text):
    """Kot generate_crnivec_page._arso_parse: ključi točk so minute od 1. 1. 1800, p0/p1/p2 po vrstnem redu
    zahtevanih spremenljivk (85, 88, 89). Vrne [[datum, višina odeje, novi sneg, padavine], ...]."""
    names = re.findall(r"(p\d):\{ pid:\"(\d+)\"", text)
    pid_of = {pk: pid for pk, pid in names}
    body = text.split("points:{", 1)[1] if "points:{" in text else ""
    base = dt.datetime(1800, 1, 1)
    days = []
    for key, vals in re.findall(r"_(\d+):\{([^{}]*)\}", body):
        v = dict(re.findall(r'(p\d):"([^"]*)"', vals))
        if not v:
            continue
        d = (base + dt.timedelta(minutes=int(key))).date().isoformat()

        def f(pid):
            for pk, pp in pid_of.items():
                if pp == pid and v.get(pk) not in (None, ""):
                    return num(v[pk])
            return None
        days.append([d, f("88"), f("89"), f("85")])
    return days


def season_of(d):
    y, m = int(d[:4]), int(d[5:7])
    return y if m >= 7 else y - 1


def coverage(days):
    snow_obs = [r for r in days if r[1] is not None or r[2] is not None]
    seasons = {}
    for r in snow_obs:
        if int(r[0][5:7]) in (11, 12, 1, 2, 3, 4):
            seasons.setdefault(season_of(r[0]), []).append(r)
    return {
        "days": len(days), "days_with_snow_field": len(snow_obs),
        "first": days[0][0] if days else None, "last": days[-1][0] if days else None,
        "snow_depth_ge1_days": sum(1 for r in days if (r[1] or 0) >= 1),
        "new_snow_ge1_days": sum(1 for r in days if (r[2] or 0) >= 1),
        "winter_days_with_snow_field": {str(k): len(v) for k, v in sorted(seasons.items())},
    }


def proxy_truth():
    """Proksi iz train_sneg_mos (ena definicija): {datum: 0/1} za dneve z meritvijo postaje."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import train_sneg_mos as tsm
    return {d: v[2] for d, v in tsm.load_truth().items()}


def confusion(days, proxy):
    """Opazovan novi sneg >= 1 cm (ali rast višine odeje) proti proksiju v Rečici; samo zimski meseci, samo dnevi z obema."""
    tp = fp = fn = tn = 0
    prev = {}
    for d, depth, new, _ in days:
        prev[d] = depth
    for d, depth, new, _ in days:
        if int(d[5:7]) not in (11, 12, 1, 2, 3, 4) or d not in proxy or (depth is None and new is None):
            continue
        obs = 1 if ((new or 0) >= 1) else 0
        p = proxy[d]
        tp += obs and p
        fp += (not obs) and p
        fn += obs and (not p)
        tn += (not obs) and (not p)
    n = tp + fp + fn + tn
    return {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "hit_rate": round(tp / (tp + fn), 2) if tp + fn else None,
            "false_alarm_ratio": round(fp / (tp + fp), 2) if tp + fp else None}


PUJS_ROOT = "/uploads/meteo/app/webmet/pujs"
PUJS_MAP = {"ACADEMA.PUJS.AMEBA": PUJS_ROOT + "/ameba", "ACADEMA.PUJS.ROOT": PUJS_ROOT, "PUJS.ROOT": PUJS_ROOT,
            "ACADEMA.PUJS.PROG": PUJS_ROOT + "/prog", "PUJS.PROG": PUJS_ROOT + "/prog", "PUJS.AMEBA": PUJS_ROOT + "/ameba",
            "ACADEMA.LANG": "sl"}
KEYWORDS = r"(?:ARCHIVE\.ROOT|URL\.ARCHIVE|locations?|stations?\.xml|\.xml\?|lang=|data\.xml|\.ROOT\s*\+)"


def crawl_ameba(out_dir, start, max_files=40):
    """Rekurzivno prebere verigo XML-jev aplikacije arhiva (`AcademaPUJS.queue({src: ...})`) in izpiše vse, kar omenja
    arhiv, postaje, lokacije ali parametre zahtevkov. Struktura je neformalna (Academa), zato se naslovi sestavijo
    iz konstant, ki jih zapiše settings.xml."""
    todo, seen, hits = list(start), set(), []
    while todo and len(seen) < max_files:
        path = todo.pop(0)
        if path in seen:
            continue
        seen.add(path)
        st, tx = get(path)
        time.sleep(PAUSE_S)
        print(f"[crawl] {path} -> HTTP {st}, {len(tx)} znakov")
        if st != 200 or not tx:
            continue
        with open(os.path.join(out_dir, "crawl-" + re.sub(r"\W+", "_", path)[-70:] + ".txt"), "w", encoding="utf-8") as f:
            f.write(tx)
        if len(tx) <= 5000:     # majhne konfiguracijske datoteke verige izpišemo v celoti
            print(f"[celoten] {path}: {re.sub(r'\s+', ' ', tx)}")
        for m in re.finditer(KEYWORDS, tx, flags=re.I):
            a, b = max(0, m.start() - 160), min(len(tx), m.end() + 220)
            hits.append((path, re.sub(r"\s+", " ", tx[a:b])))
        for pre, rest in re.findall(r"src:\s*([A-Za-z_.]+)\s*\+\s*\"([^\"]+)\"", tx):
            if pre in PUJS_MAP:
                nxt = PUJS_MAP[pre] + rest
                if nxt not in seen:
                    todo.append(nxt)
        for lit in re.findall(r"src:\s*\"([^\"]+\.xml)\"", tx):
            if lit not in seen:
                todo.append(lit)
    # kratek seznam datotek, nato samo zares pomembna mesta (generatorske funkcije izpustimo: izris tabel)
    print("[crawl] datoteke:", ", ".join(sorted(x.rsplit("/", 1)[-1] for x in seen)))
    shown, count = {}, 0
    for path, w in hits:
        if "generators" in path or count >= 70:
            continue
        if not re.search(r"(?:ARCHIVE\.ROOT|URL\.ARCHIVE|locations?|stations?\.xml|\.xml\?|lang=|data\.xml|\.ROOT\s*\+)", w, flags=re.I):
            continue
        key = (path, w[:60])
        if key in shown:
            continue
        shown[key] = 1
        count += 1
        print(f"   ~ [{path.rsplit('/', 1)[-1]}] {w[:420]}")
    return seen


def probe_locations():
    """Mreža možnih naslovov seznama postaj (sicer 500): ime datoteke x vrsta postaje x skupina."""
    found = []
    for name in ("locations.xml",):
        for typ in ("1", "2", "3", "4"):
            for extra in ("", "&group=dailyData0&type=daily"):
                path = f"/webmet/archive/{name}?lang=si&type={typ}{extra}" if not extra else \
                       f"/webmet/archive/{name}?lang=si&stype={typ}{extra}"
                st, tx = get(path, timeout=30)
                time.sleep(0.4)
                if st == 200 and tx:
                    print(f"[mreža] {path} -> HTTP 200, {len(tx)} znakov: {re.sub(chr(10), ' ', tx[:200])}")
                    found.append((path, tx))
    print(f"[mreža] zadetkov: {len(found)}")
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=35.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "arso-snow-out"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    report = ["# ARSO snežne postaje blizu Rečice", ""]

    stations, used = [], None
    for cand in LIST_CANDIDATES:
        st, text = get(cand)
        head = re.sub(r"\s+", " ", text[:400])
        print(f"[seznam] {cand} -> HTTP {st}, {len(text)} znakov: {head}")
        with open(os.path.join(a.out, "list-" + re.sub(r"\W+", "_", cand)[:60] + ".txt"), "w", encoding="utf-8") as f:
            f.write(text)
        report.append(f"- `{cand}`: HTTP {st}, {len(text)} znakov")
        time.sleep(PAUSE_S)
        if st == 200 and text:
            found = parse_stations(text)
            print(f"   -> razpoznanih postaj: {len(found)}")
            if len(found) > len(stations):
                stations, used = found, cand
            if "<html" in text.lower() or "<!doctype" in text.lower():
                # diagnostika: kaj stran nalaga (iframe, skripte, obrazci, izbirniki, vse kar omenja webmet/xml)
                tags = re.findall(r"<(?:iframe|script|form|select|option|input|a)\b[^>]*>", text, flags=re.I)
                print(f"   oznake ({len(tags)}):")
                for t in tags[:120]:
                    print("     ", re.sub(r"\s+", " ", t)[:220])
                for m in re.finditer(r"[^\n]{0,160}(?:webmet|\.xml|locations|ajax|getJSON|XMLHttp)[^\n]{0,160}", text):
                    print("   ~", re.sub(r"\s+", " ", m.group(0))[:320])
            if cand.endswith("/webmet/"):       # aplikacija arhiva: preberi njene skripte in izpiši, od kod jemlje postaje
                srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, flags=re.I)
                srcs += re.findall(r'["\']([^"\']+\.js(?:\?[^"\']*)?)["\']', text)
                # glavni modul aplikacije in nastavitve (v strani zapisani kot '/uploads/meteo/app/webmet/bin/app' ...)
                srcs += ["/uploads/meteo/app/webmet/bin/app.js", "/uploads/meteo/app/webmet/bin/app",
                         "/uploads/meteo/app/webmet/pujs/settings.xml",
                         # PUJS.ARCHIVE.INIT = PUJS.AMEBA + "/init.xml"; PUJS.AMEBA = PUJS.ROOT + "/ameba"
                         "/uploads/meteo/app/webmet/pujs/ameba/init.xml",
                         "/uploads/meteo/app/webmet/pujs/ameba/settings.xml",
                         "/uploads/meteo/app/webmet/pujs/default.xml"]
                srcs += re.findall(r'["\'](/uploads/meteo/app/webmet/[^"\']+)["\']', text)
                for src in list(dict.fromkeys(srcs))[:40]:
                    if src.startswith("//") and "arso" not in src:
                        continue
                    url = urllib.parse.urljoin(BASE + cand, src)
                    if "arso.gov.si" not in url:
                        continue
                    stj, tj = get(url)
                    print(f"   [js] {url} -> HTTP {stj}, {len(tj)} znakov")
                    time.sleep(PAUSE_S)
                    with open(os.path.join(a.out, "js-" + re.sub(r"\W+", "_", url)[-70:] + ".txt"), "w", encoding="utf-8") as fj:
                        fj.write(tj)
                    if url.endswith(".xml"):
                        print("      xml:", re.sub(r"\s+", " ", tj[:4500]))
                    if len(tj) < 400:
                        print("      celoten odgovor:", re.sub(r"\s+", " ", tj))
                    if len(tj) > 150000:
                        continue    # knjižnice (jquery, highcharts) preskoči
                    for m in re.finditer(r"[^\n;{}]{0,200}" + APP_JS_PATTERN + r"[^\n;{}]{0,260}", tj, flags=re.I):
                        print("      ~", re.sub(r"\s+", " ", m.group(0))[:340])
            if cand.endswith("/archive/"):      # stran: poišči še XML/JS povezave, ki jih nalaga
                links = sorted(set(re.findall(r'["\']([^"\']+\.(?:xml|js|json)[^"\']*)["\']', text)))
                print("   povezave na strani:", links[:40])
                report.append(f"  povezave na strani: {links[:40]}")
                for l in links:
                    if "locat" in l.lower() or "station" in l.lower() or "archive" in l.lower():
                        st2, t2 = get(urllib.parse.urljoin(BASE + "/met/sl/archive/", l))
                        f2 = parse_stations(t2) if st2 == 200 else []
                        print(f"   [{l}] HTTP {st2}, {len(t2)} znakov, postaj {len(f2)}")
                        time.sleep(PAUSE_S)
                        if len(f2) > len(stations):
                            stations, used = f2, l
    if not stations:
        crawl_ameba(a.out, [PUJS_ROOT + "/ameba/index.xml", PUJS_ROOT + "/ameba/default.xml", PUJS_ROOT + "/prog/default.xml",
                            PUJS_ROOT + "/prog/init.xml", PUJS_ROOT + "/menu.xml"])
        for path, tx in probe_locations():
            found = parse_stations(tx)
            print(f"   {path}: razpoznanih postaj {len(found)}")
            if len(found) > len(stations):
                stations, used = found, path
    report += ["", f"Seznam postaj: **{used or 'NI NAJDEN'}**, postaj: {len(stations)}", ""]
    with open(os.path.join(a.out, "stations.json"), "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, indent=1)
    if not stations:
        print("✗ Seznama postaj ni bilo mogoče razpoznati -- poglej surove odgovore v artefaktu.")
        open(os.path.join(a.out, "report.md"), "w", encoding="utf-8").write("\n".join(report) + "\n")
        return 0

    near = sorted(({**s, "dist_km": round(km(LAT, LON, s["lat"], s["lon"]), 1)} for s in stations),
                  key=lambda s: s["dist_km"])
    near = [s for s in near if s["dist_km"] <= a.radius]
    print(f"\nPostaje v {a.radius:.0f} km od Rečice: {len(near)}")
    for s in near:
        print(f"  {s['dist_km']:5.1f} km  id {s['id']:>6}  {s['name']:30s} {s['elev']} m  {s['attrs']}")
    report += [f"## Postaje v {a.radius:.0f} km", "", "| km | id | ime | višina | atributi |", "|---|---|---|---|---|"]
    report += [f"| {s['dist_km']} | {s['id']} | {s['name']} | {s['elev']} | `{json.dumps(s['attrs'], ensure_ascii=False)[:160]}` |"
               for s in near]

    proxy = proxy_truth()
    today = dt.date.today().isoformat()
    results = []
    for s in near:
        params = urllib.parse.urlencode({"lang": "si", "vars": "85,88,89", "group": "dailyData0", "type": "daily",
                                         "id": s["id"], "d1": FIRST_DATE, "d2": today})
        st, text = get(f"/webmet/archive/data.xml?{params}")
        time.sleep(PAUSE_S)
        days = parse_daily(text) if st == 200 else []
        cov = coverage(days)
        conf = confusion(days, proxy) if cov["days_with_snow_field"] else None
        results.append({"station": {k: s[k] for k in ("id", "name", "lat", "lon", "elev", "dist_km")},
                        "http": st, "coverage": cov, "vs_proxy": conf})
        print(f"[{s['id']}] {s['name']}: HTTP {st}, dni {cov['days']}, s poljem snega {cov['days_with_snow_field']}, "
              f"nov sneg >= 1 cm {cov['new_snow_ge1_days']} dni, zime {cov['winter_days_with_snow_field']}, vs proksi {conf}")
        if days:
            with open(os.path.join(a.out, f"daily-{s['id']}.json"), "w", encoding="utf-8") as f:
                json.dump({"fields": ["date", "snow_depth_cm", "new_snow_cm", "precip_mm"], "days": days}, f,
                          ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    report += ["", "## Pokritost z opazovanim snegom", "",
               "| id | ime | km | m | dni | dni s poljem snega | nov sneg ≥ 1 cm | zimski dnevi s snegom po zimah | vs proksi (tp/fp/fn/tn) |",
               "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        s, c, v = r["station"], r["coverage"], r["vs_proxy"]
        report.append(f"| {s['id']} | {s['name']} | {s['dist_km']} | {s['elev']} | {c['days']} | {c['days_with_snow_field']} | "
                      f"{c['new_snow_ge1_days']} | {c['winter_days_with_snow_field']} | "
                      f"{(str(v['tp']) + '/' + str(v['fp']) + '/' + str(v['fn']) + '/' + str(v['tn'])) if v else '-'} |")
    open(os.path.join(a.out, "report.md"), "w", encoding="utf-8").write("\n".join(report) + "\n")
    print("\n→ " + os.path.join(a.out, "report.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
