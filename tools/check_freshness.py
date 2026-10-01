#!/usr/bin/env python3
"""
tools/check_freshness.py — ali dnevni izdelki sploh nastajajo?

Od 31. 8. (nevihtna karta) oz. 11. 9. (padavinska karta) nobena nova karta ni
nastala, a je workflow vsak dan »uspel«: časovna vrata (tools/*_gate.py) so tek
tiho zavrnila, ker GitHubov cron zamuja 5-7 ur. Nihče ni bil obveščen — odkrito
je bilo šele po mesecu dni naključno. Zeleno kljukico workflowa zato ne štejemo
za dokaz; ta skript gleda IZDELEK: kdaj je bil zadnjič zapisan.

REGISTER spodaj navaja datoteko, polje s časom in največjo dovoljeno starost.
Praga sta zavestno radodarna (cron zamuja ure); namen je ujeti okvare, ki trajajo
dneve, ne zamude. Datumski izdelek (`date`) se šteje od konca tistega dne.

Piše poročilo v Markdown (stdout, $GITHUB_STEP_SUMMARY, --report FILE) in
v $GITHUB_OUTPUT `stale=<število>`. Izhod je vedno 0 — opozorilo odpre workflow
(.github/workflows/freshness-watch.yml) kot GitHub issue z oznako `stale-output`.

Nov dnevni izdelek = nova vrstica v REGISTER (test_freshness.py preveri, da se
vsaka vrstica res razreši).

Usage:
  python3 tools/check_freshness.py [--report FILE]
"""
import csv
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = ZoneInfo("Europe/Ljubljana")
UTC = datetime.timezone.utc

# (ime, datoteka, način, parameter, največja starost v urah, kaj preveriti)
#   način "ts"        — polje z ISO časom (parameter = ime polja)
#   način "date"      — polje z datumom YYYY-MM-DD (starost od konca tistega dne)
#   način "maxkey"    — največji datumski ključ v objektu (history.json …)
#   način "csvdate"   — datum v prvem stolpcu zadnje vrstice CSV
REGISTER = [
    ("Nevihtna karta Slovenije", "og/storm-map/latest.json", "date", "date", 36,
     "storm-map.yml + tools/storm_map_gate.py (okno, GH_DISPATCH_TOKEN)"),
    ("Padavinska karta Slovenije", "og/precip-map/latest.json", "date", "date", 36,
     "precip-map.yml: vrata + jutranji posnetek rr24h v workerju (/arso-rr24h, cron 06:30 UTC)"),
    ("Dnevna zgodba (FB/IG)", "og/story/latest.json", "ts", "generated_at", 36,
     "daily-story.yml + tools/story_gate.py"),
    ("Termika: nivo igre", "igra/nivo.json", "ts", "generated", 36,
     "padalci-forecast.yml + tools/igra_gate.py (okno 5:00–12:00)"),
    ("Napoved MTR", "napoved-modela.json", "ts", "generated_at", 36,
     "forecast-verify.yml → predict_recica_mos.py"),
    ("Točnost MTR", "data/mtr-accuracy.json", "ts", "generated_at", 36,
     "forecast-verify.yml"),
    ("Test napovedi", "data/test-napovedi.json", "ts", "generated_at", 36,
     "test-napovedi-daily.yml"),
    ("Gobarska napoved", "gobarska-napoved/index.json", "ts", "generated", 36,
     "gobe-forecast.yml"),
    ("MeteoGasilec", "meteogasilec/index.json", "ts", "generated", 36,
     "gasilec-forecast.yml"),
    ("Zima / Črnivec", "data/winter-data.json", "ts", "generated_at", 36,
     "zima-forecast.yml"),
    ("Preverjanje nevihtne karte", "data/storm-map-verification.json", "ts", "generated_at", 36,
     "storm-verify.yml"),
    ("Zgodovina meritev (history.json)", "history.json", "maxkey", None, 60,
     "update-history.yml (Ecowitt)"),
    ("Verifikacija napovedi", "forecast_verification.json", "maxkey", None, 72,
     "forecast-verify.yml"),
    ("Dolinski dvoboj", "data/valley-duel-log.csv", "csvdate", None, 60,
     "valley-duel-log.yml"),
    ("Model MTR (mesečno učenje)", "model/recica-mos.json", "ts", "trained_at", 24 * 40,
     "mos-train.yml"),
]


def parse_ts(v):
    t = datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t


def end_of_day(d):
    day = datetime.date.fromisoformat(d)
    return datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(0, 0), tzinfo=TZ)


def read_time(path, mode, param):
    """Čas zadnje osvežitve izdelka (aware datetime) ali None, če ga ni mogoče prebrati."""
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return None
    try:
        if mode == "csvdate":
            with open(full, encoding="utf-8") as f:
                rows = [r for r in csv.reader(f) if r]
            return end_of_day(rows[-1][0])
        with open(full, encoding="utf-8") as f:
            data = json.load(f)
        if mode == "ts":
            return parse_ts(data[param])
        if mode == "date":
            return end_of_day(data[param])
        if mode == "maxkey":
            return end_of_day(max(k for k in data if len(k) == 10 and k[4] == "-"))
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    return None


def evaluate(now=None, register=None):
    now = now or datetime.datetime.now(UTC)
    out = []
    for name, path, mode, param, max_h, hint in (register or REGISTER):
        t = read_time(path, mode, param)
        if t is None:
            out.append({"name": name, "path": path, "status": "unreadable", "age_h": None, "max_h": max_h, "hint": hint})
            continue
        age = max(0.0, (now - t).total_seconds() / 3600)
        # datumski izdelki merijo od konca dneva, zato jim ura (00:00) nič ne pove
        stamp = t.astimezone(TZ) - datetime.timedelta(seconds=1) if mode in ("date", "maxkey", "csvdate") else t.astimezone(TZ)
        label = stamp.strftime("%-d. %-m. %Y") + ("" if mode in ("date", "maxkey", "csvdate") else stamp.strftime(" %H:%M"))
        out.append({"name": name, "path": path, "status": "stale" if age > max_h else "ok",
                    "age_h": round(age, 1), "max_h": max_h, "hint": hint, "updated": label})
    return out


def fmt_age(h):
    if h is None:
        return "—"
    return f"{h:.0f} h" if h < 72 else f"{h / 24:.0f} dni"


def report(results):
    bad = [r for r in results if r["status"] != "ok"]
    lines = []
    if bad:
        lines.append(f"**{len(bad)} od {len(results)} izdelkov ne nastaja ali je zastarelo.** Zelena kljukica "
                     "workflowa ni dokaz — preveri izdelek in kar je ob njem (vrata, cron, secret).\n")
    else:
        lines.append(f"Vseh {len(results)} izdelkov je svežih.\n")
    lines.append("| Izdelek | Stanje | Starost | Dovoljeno | Zadnja osvežitev | Kje iskati |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda r: (r["status"] == "ok", r["name"])):
        icon = {"ok": "✅", "stale": "⚠️ zastarelo", "unreadable": "❌ ni berljivo"}[r["status"]]
        lines.append(f"| {r['name']} (`{r['path']}`) | {icon} | {fmt_age(r['age_h'])} | {fmt_age(r['max_h'])} | "
                     f"{r.get('updated', '—')} | {r['hint']} |")
    return "\n".join(lines) + "\n", len(bad)


def main():
    results = evaluate()
    text, n_bad = report(results)
    print(text)
    if "--report" in sys.argv:
        with open(sys.argv[sys.argv.index("--report") + 1], "w", encoding="utf-8") as f:
            f.write(text)
    for env, content in (("GITHUB_STEP_SUMMARY", text), ("GITHUB_OUTPUT", f"stale={n_bad}\n")):
        p = os.environ.get(env)
        if p:
            with open(p, "a", encoding="utf-8") as f:
                f.write(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
