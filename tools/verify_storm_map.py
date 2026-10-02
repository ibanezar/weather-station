#!/usr/bin/env python3
"""
tools/verify_storm_map.py — preverjanje nevihtne karte Slovenije proti dejanskim
strelam.

Nevihtna karta (tools/generate_storm_map.py) vsako jutro objavi oceno
potenciala po mrežnih točkah. `LightningLogger` (worker.js) vse leto neprekinjeno
beleži strele omrežja Blitzortung znotraj 200 km od postaje. Ta skript ju
primerja: za vsak končan dan vzame arhivirano napoved
(data/storm-map-forecasts/<datum>.json) in od workerja prebere strele od izdaje
karte do polnoči, združene po celicah iste mreže
(`/strele-zgodovina.json?celice=1`). Rezultat je izmerjena zanesljivost karte,
kot jo imajo MTR in semafor — namesto da bi se zanesli, da formula »menda
deluje«.

Pravila, ki jih ne obračaj:

- **Okno je od izdaje karte do polnoči, ne ves dan.** Ocena pomeni »najvišja
  pričakovana od zdaj do konca dneva«; karta, ki je zaradi zamude crona nastala
  ob 13:00, se ne sme kaznovati za jutranjo nevihto.
- **Prazen zapis ni »ni strel«.** Dan se šteje samo, če je bila povezava
  LightningLoggerja ≥ 90 % oken živa (pokritost beleži keepAlive vsakih 5 min).
  Prej zapisan dan ali dan z luknjo se označi kot preskočen z razlogom — stran ga
  ne šteje, a ga ne skrije.
- **Opazovanje je celica, ne točka.** Strela šteje za točko, če je v celici
  45,45 + 0,18·k / 13,4 + 0,22·j (približno 20 × 17 km, razmik točk na karti) —
  ocena na karti je za območje, ne za koordinato.
- **Majhen vzorec se ne prodaja kot zanesljivost.** Dokler ni vsaj
  MIN_STORM_DAYS dni s strelami nad Slovenijo, stran pove, da je rezultat zgoden.
  Oktober–marec ima malo neviht, zato bo to trajalo.

Piše:
  data/storm-map-verification.json  — dnevi + skupne številke
  nevihte/index.html                — blok med WX-STORMVERIF (isti vzorec kot WX-STORMMAP)

Usage:
  python3 tools/verify_storm_map.py run [--dry-run]   # preveri končane dni, zapiši, vgradi
  python3 tools/verify_storm_map.py inject            # samo vgradi zadnji rezultat na stran
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORECAST_DIR = os.path.join(ROOT, "data", "storm-map-forecasts")
RESULTS = os.path.join(ROOT, "data", "storm-map-verification.json")
PAGE = os.path.join(ROOT, "nevihte", "index.html")
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
# Cloudflare zavrne privzeti »Python-urllib« User-Agent s 403 (glej tools/test_worker_ua.py).
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
TZ = ZoneInfo("Europe/Ljubljana")

START = "<!-- WX-STORMVERIF:START (auto: tools/verify_storm_map.py) -->"
END = "<!-- WX-STORMVERIF:END -->"

MIN_COVERAGE = 0.90          # delež 5-minutnih oken z živo povezavo
MIN_STORM_DAYS = 10          # dni s strelami nad Slovenijo za »zanesljiv« sklep
RETENTION_DAYS = 14          # toliko časa worker hrani surove strele
THRESHOLDS = (8, 22, 40)     # NIZKO / ZMERNO / VISOKO — kot score_level() v generate_storm_map.py
LEVELS = ("BREZ", "NIZKO", "ZMERNO", "VISOKO", "EKSTREMNO")
LEVEL_SL = {"BREZ": "brez", "NIZKO": "nizko", "ZMERNO": "zmerno", "VISOKO": "visoko", "EKSTREMNO": "ekstremno"}


def score_level(s):
    """Isti pragovi kot generate_storm_map.score_level() (test_parity.py preveri)."""
    if s >= 60:
        return "EKSTREMNO"
    if s >= 40:
        return "VISOKO"
    if s >= 22:
        return "ZMERNO"
    if s >= 8:
        return "NIZKO"
    return "BREZ"


def day_window(fc):
    """[od, do) v ms: od izdaje karte do lokalne polnoči."""
    issued = datetime.datetime.fromisoformat(fc["issued_at"])
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=TZ)
    day = datetime.date.fromisoformat(fc["date"])
    end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(0, 0), tzinfo=TZ)
    return int(issued.timestamp() * 1000), int(end.timestamp() * 1000)


def verify_day(fc, resp):
    """Preveri eno napoved proti odgovoru workerja (`cells`). Čista funkcija.
    Vrne zapis dneva; `status` je "ok" ali "skipped" z `reason`."""
    od, do_ = day_window(fc)
    rec = {"date": fc["date"], "issued_at": fc["issued_at"], "n_points": len(fc["points"]),
           "national_score": fc["national"]["score"]}
    total_slots = resp.get("slots_total") or 0
    cov = (resp.get("slots_connected") or 0) / total_slots if total_slots else 0.0
    rec["coverage"] = round(cov, 3)
    since = resp.get("uptime_since")
    if since is None or since > od + 600000:   # 10 min tolerance: zapis pokritosti se je začel po izdaji karte
        rec.update(status="skipped", reason="zapis pokritosti se je začel po izdaji karte")
        return rec
    if cov < MIN_COVERAGE:
        rec.update(status="skipped", reason=f"povezava zapisovalnika strel je bila živa le {round(cov * 100)} % časa")
        return rec

    g = fc["grid"]
    hit = {(c["k"], c["j"]): c["n"] for c in resp.get("cells", [])}
    levels = {lv: {"n": 0, "obs": 0} for lv in LEVELS}
    cont = {str(t): {"a": 0, "b": 0, "c": 0, "d": 0} for t in THRESHOLDS}
    storm_cells = 0
    for la, lo, score, _hour in fc["points"]:
        k, j = round((la - g["lat0"]) / g["dlat"]), round((lo - g["lon0"]) / g["dlon"])
        obs = hit.get((k, j), 0) > 0
        storm_cells += obs
        lv = levels[score_level(score)]
        lv["n"] += 1
        lv["obs"] += obs
        for t in THRESHOLDS:
            key = "a" if (score >= t and obs) else "b" if score >= t else "c" if obs else "d"
            cont[str(t)][key] += 1
    rec.update(status="ok", strike_cells=storm_cells, strikes=resp.get("total", 0),
               storm_day=storm_cells > 0, levels=levels, contingency=cont)
    return rec


def summarize(days):
    """Skupne številke iz dnevov s statusom ok."""
    ok = [d for d in days if d.get("status") == "ok"]
    levels = {lv: {"n": 0, "obs": 0} for lv in LEVELS}
    cont = {str(t): {"a": 0, "b": 0, "c": 0, "d": 0} for t in THRESHOLDS}
    for d in ok:
        for lv in LEVELS:
            levels[lv]["n"] += d["levels"][lv]["n"]
            levels[lv]["obs"] += d["levels"][lv]["obs"]
        for t in cont:
            for k in "abcd":
                cont[t][k] += d["contingency"][t][k]
    # dnevna raven: karta je nekje napovedala >= ZMERNO proti dnevu s strelami
    day = {"a": 0, "b": 0, "c": 0, "d": 0}
    for d in ok:
        pred = d["national_score"] >= THRESHOLDS[1]
        key = "a" if (pred and d["storm_day"]) else "b" if pred else "c" if d["storm_day"] else "d"
        day[key] += 1
    return {"days_ok": len(ok), "days_skipped": len(days) - len(ok),
            "storm_days": sum(1 for d in ok if d["storm_day"]),
            "first_date": ok[0]["date"] if ok else None, "last_date": ok[-1]["date"] if ok else None,
            "levels": levels, "contingency": cont, "day_level": day}


def load_results():
    try:
        with open(RESULTS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"days": []}


def fetch_cells(od, do_):
    q = urllib.parse.urlencode({"celice": 1, "od": od, "do": do_})
    req = urllib.request.Request(f"{WORKER}/strele-zgodovina.json?{q}", headers={"Accept": "application/json", "User-Agent": WORKER_UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def pending_days(results, today):
    """Končani dnevi z arhivirano napovedjo, ki še niso preverjeni, in so v roku hrambe strel."""
    done = {d["date"] for d in results.get("days", [])}
    out = []
    if not os.path.isdir(FORECAST_DIR):
        return out
    for name in sorted(os.listdir(FORECAST_DIR)):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.json", name)
        if not m:
            continue
        d = datetime.date.fromisoformat(m.group(1))
        if d >= today or m.group(1) in done:
            continue
        out.append((d, os.path.join(FORECAST_DIR, name)))
    return out


# ── Prikaz na /nevihte/ ───────────────────────────────────────────────────

def pct(a, b):
    return "—" if not b else f"{round(100 * a / b)} %"


def esc(s):
    return html.escape(str(s), quote=True)


def build_block(results):
    s = results.get("summary") or summarize(results.get("days", []))
    intro = (
        '  <p class="archive-intro">Vsak dan po polnoči primerjamo oceno karte po mrežnih točkah z dejansko '
        'zabeleženimi streli omrežja Blitzortung (stalni zapis naše postaje, do 200 km). Točka je »zadeta«, če je '
        'v njeni celici (približno 20 × 17 km) od izdaje karte do polnoči udarila vsaj ena strela. Dnevi, ko je '
        'bila povezava zapisovalnika prekinjena, se ne štejejo — prazen zapis bi sicer pomenil »ni strel«, '
        'čeprav jih nismo mogli videti.</p>\n')
    head = f'{START}\n  <h2 id="preverjanje">Kako zanesljiva je karta? Preverjanje proti strelam</h2>\n{intro}'
    if not s["days_ok"]:
        body = ('  <p class="muted-note">Preverjanje se je šele začelo — prvi rezultati bodo po prvem končanem '
                'dnevu z zabeleženo karto.</p>\n')
        return head + body + f'  {END}'
    rows = "".join(
        f'<tr><td>{LEVEL_SL[lv]}</td><td>{s["levels"][lv]["n"]}</td><td>{s["levels"][lv]["obs"]}</td>'
        f'<td>{pct(s["levels"][lv]["obs"], s["levels"][lv]["n"])}</td></tr>'
        for lv in LEVELS)
    dl = s["day_level"]
    pred_days = dl["a"] + dl["b"]
    early = ""
    if s["storm_days"] < MIN_STORM_DAYS:
        early = (f'  <p class="muted-note"><strong>Zgoden rezultat:</strong> dni s strelami nad Slovenijo je '
                 f'{s["storm_days"]}, za zanesljiv sklep jih potrebujemo vsaj {MIN_STORM_DAYS}. '
                 f'Čez zimo jih je malo; številke se bodo ustalile s sezono neviht.</p>\n')
    body = (
        f'  <p>Preverjenih dni: <strong>{s["days_ok"]}</strong> ({esc(s["first_date"])} – {esc(s["last_date"])}), '
        f'od tega s strelami nad Slovenijo: <strong>{s["storm_days"]}</strong>. '
        f'Dni, ko je karta nekje napovedala vsaj zmeren potencial: {pred_days}, od tega je res streljalo {dl["a"]}. '
        f'Dni s strelami, ki jih karta ni napovedala: {dl["c"]}.</p>\n'
        f'  <div class="table-scroll" tabindex="0"><table class="data-table">\n'
        f'  <thead><tr><th>Ocena karte</th><th>Točk</th><th>S strelami</th><th>Delež</th></tr></thead>\n'
        f'  <tbody>{rows}</tbody></table></div>\n{early}')
    return head + body + f'  {END}'


def inject(results, dry=False):
    if not os.path.exists(PAGE):
        print(f"ERROR: {PAGE} ne obstaja.", file=sys.stderr)
        return 1
    page = open(PAGE, encoding="utf-8").read()
    if START not in page or END not in page:
        print("ERROR: markerjev WX-STORMVERIF ni v /nevihte/ — poženi najprej "
              "tools/generate_nevihte_page.py.", file=sys.stderr)
        return 1
    block = build_block(results)
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, page, flags=re.S)
    if dry:
        print("--dry-run:", "sprememba" if new != page else "brez sprememb")
        return 0
    if new != page:
        open(PAGE, "w", encoding="utf-8").write(new)
        print("nevihte/index.html: preverjanje karte posodobljeno.")
    return 0


def run(dry=False):
    results = load_results()
    now = datetime.datetime.now(TZ)
    today = now.date()
    days = results.get("days", [])
    for d, path in pending_days(results, today):
        if (today - d).days > RETENTION_DAYS - 1:
            days.append({"date": d.isoformat(), "status": "skipped", "reason": "strele za ta dan niso več na voljo"})
            continue
        fc = json.load(open(path, encoding="utf-8"))
        od, do_ = day_window(fc)
        try:
            resp = fetch_cells(od, min(do_, int(now.timestamp() * 1000)))
        except Exception as e:  # noqa: BLE001 — dan ostane nepreverjen, jutri ponovno
            print(f"⚠ {d}: strele niso dosegljive ({e}) — poskus jutri", file=sys.stderr)
            continue
        rec = verify_day(fc, resp)
        days.append(rec)
        print(f"  {d}: {rec['status']}" + (f" — {rec['reason']}" if rec["status"] == "skipped" else
              f" — {rec['strike_cells']}/{rec['n_points']} točk s strelami"))
    days.sort(key=lambda x: x["date"])
    results = {"generated_at": now.isoformat(),
               "method": "celica 45,45+0,18k / 13,4+0,22j, okno od izdaje karte do polnoči, pokritost >= 90 %",
               "days": days, "summary": summarize(days)}
    if dry:
        print(json.dumps(results["summary"], ensure_ascii=False))
        return 0
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return inject(results)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "inject":
        return inject(load_results(), dry="--dry-run" in sys.argv)
    return run(dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
