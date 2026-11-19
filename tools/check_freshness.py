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

To vključuje tudi zdravje Cloudflare cron opravil (`worker_health()`, workerjev /health).
"""
import csv
import datetime
import json
import os
import re
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
#   način "csvcol"    — CSV z glavo: stolpec (parameter) zadnje vrstice, datum YYYY-MM-DD ali ISO čas
#   način "firstdate" — datoteka je seznam, polje z datumom prvega (najnovejšega) zapisa
#   način "regexdate" — besedilna datoteka (HTML), parameter = regex, ki v prvi skupini zajame datum YYYY-MM-DD
REGISTER = [
    # Nevihtna karta in njeno preverjanje sta na pavzi do aprila 2027 (28. 10. 2026) -- vrstici vrni ob vklopu:
    #   ("Nevihtna karta Slovenije", "og/storm-map/latest.json", "date", "date", 36,
    #    "storm-map.yml + tools/storm_map_gate.py (okno, GH_DISPATCH_TOKEN)"),
    #   ("Preverjanje nevihtne karte", "data/storm-map-verification.json", "ts", "generated_at", 36, "storm-verify.yml"),
    ("Padavinska karta Slovenije", "og/precip-map/latest.json", "date", "date", 36,
     "precip-map.yml: vrata + jutranji posnetek rr24h v workerju (/arso-rr24h, cron 06:30 UTC)"),
    # 168 h (22. 10. 2026, Filip): okno 6:00-7:00 (story_gate.py) + zamujanje GitHubovega crona
    # brez GH_DISPATCH_TOKEN pomenita, da zgodbe pogosto ni -- to je znana posledica odločitve,
    # ne okvara. Alarm šele, ko je ni teden dni.
    ("Dnevna zgodba (FB/IG)", "og/story/latest.json", "ts", "generated_at", 168,
     "daily-story.yml + tools/story_gate.py"),
    ("Termika: nivo igre", "igra/nivo.json", "ts", "generated", 36,
     "padalci-forecast.yml + tools/igra_gate.py (okno 5:00–12:00)"),
    ("Napoved MTR", "napoved-modela.json", "ts", "generated_at", 36,
     "forecast-verify.yml → predict_recica_mos.py"),
    # Živa osvežitev za kartice (mtr-live.yml, 4 termini/dan); radodaren prag zaradi zamud crona.
    ("Napoved MTR (živa)", "napoved-modela-live.json", "ts", "generated_at", 36,
     "mtr-live.yml → predict_recica_mos.py --live"),
    # MTR sneg (proksi): zunaj sezone (maj-sept) se datoteka zapiše enkrat na dan s praznim seznamom (utrip).
    ("MTR sneg (proksi)", "napoved-snega.json", "ts", "generated_at", 36,
     "sneg-forecast.yml → predict_sneg_mos.py"),
    # Resnica za MTR sneg: dnevne serije ARSO postaj v dolini (arhiv zaostaja nekaj dni; osvezeno.json piše vsak tek).
    ("ARSO sneg - serije postaj v dolini", "data/arso-sneg-postaje/osvezeno.json", "ts", "generated_at", 72,
     "arso-sneg-refresh.yml → refresh_arso_sneg.py"),
    # Resnica za MTR sneg: dnevne serije ARSO postaj v dolini (arhiv zaostaja nekaj dni; osvezeno.json piše vsak tek).
    ("ARSO sneg: serije postaj v dolini", "data/arso-sneg-postaje/osvezeno.json", "ts", "generated_at", 72,
     "arso-sneg-refresh.yml → refresh_arso_sneg.py"),
    ("MTR: števci odprtih poskusov", "data/mtr-pending.json", "ts", "generated_at", 36,
     "mtr-live.yml → tools/mtr_pending.py"),
    ("Točnost MTR", "data/mtr-accuracy.json", "ts", "generated_at", 36,
     "forecast-verify.yml"),
    ("Test napovedi", "data/test-napovedi.json", "ts", "generated_at", 36,
     "test-napovedi-daily.yml"),
    ("Sevanje soseda (primerjava prvega žarka)", "data/sonce-varpolje.json", "date", "generated", 72,
     "test-napovedi-daily.yml → log_varpolje_solar.py (vir: worker cron varpolje_solar)"),
    ("Gobarska napoved", "gobarska-napoved/index.json", "ts", "generated", 36,
     "gobe-forecast.yml"),
    ("MeteoGasilec", "meteogasilec/index.json", "ts", "generated", 36,
     "gasilec-forecast.yml"),
    ("Zima / Črnivec", "data/winter-data.json", "ts", "generated_at", 36,
     "zima-forecast.yml"),
    ("Zimska opozorila (ocene za push)", "data/zima-ocene.json", "ts", "generated", 36,
     "zima-forecast.yml"),
    # Snegofili: korak v zima-forecast.yml je continue-on-error (Open-Meteo 429), zato 48 h (en izpadel tek ni napaka).
    ("Snegofili (sneg po alpskem loku)", "data/snegofili.json", "ts", "generated_at", 48,
     "zima-forecast.yml → tools/snegofili_data.py (korak je continue-on-error)"),
    ("Jutro v dolini (zamik prvi žarek → ogrevanje)", "data/jutro-zamik.json", "date", "generated", 60,
     "zima-forecast.yml (korak je continue-on-error)"),
    # 19. 11. 2026: squash PR-ja je povozil botov commit in kartica »Včeraj rekord za …« je ostala dan za zgodovino; izdelek je v index.html, ne v JSON.
    ("Dnevno dejstvo na naslovnici", "index.html", "regexdate", r'daily-fact-card" data-date="(\d{4}-\d{2}-\d{2})"', 60,
     "update-history.yml (generate_daily_fact.py); če zaostaja za history.json, glej commit bota"),
    ("Zgodovina meritev (history.json)", "history.json", "maxkey", None, 60,
     "update-history.yml (Ecowitt)"),
    ("Verifikacija napovedi", "forecast_verification.json", "maxkey", None, 72,
     "forecast-verify.yml"),
    # Tedenski povzetek: ponedeljki 04:40 UTC (cron zamuja ure), zadnji teden se konča v nedeljo -> 9 dni + rezerva za izpad enega teka.
    ("Dolina v tednu (tedenski povzetek)", "data/dolina-v-tednu.json", "firstdate", "week_end", 24 * 11,
     "dolina-v-tednu.yml → generate_dolina_v_tednu.py"),
    # Dnevniki, ki se nabirajo samo s tekočim zajemom (izpad dneva je nepovraten, glej razdelek Test napovedi): zato jih spremljamo.
    ("Dnevnik: napovedi profila (zajem naprej)", "data/profile-forward-log.csv", "csvcol", "issued_at", 60,
     "test-napovedi-daily.yml → log_profile_forecasts.py"),
    ("Dnevnik: ansambli (zajem naprej)", "data/ensemble-forward-log.csv", "csvcol", "issued_at", 60,
     "test-napovedi-daily.yml → log_ensemble_forecasts.py"),
    ("Dnevnik: ARSO in Yr (zajem naprej)", "data/forecast-forward-log.csv", "csvcol", "issued_at", 60,
     "test-napovedi-daily.yml → log_forward_forecasts.py"),
    ("Dnevnik: urne meritve IREICA1", "data/hourly-observations.csv", "csvcol", "valid_at_local", 60,
     "test-napovedi-daily.yml → log_hourly_observations.py (Ecowitt podvzorči starejše od ~90 dni)"),
    ("Dnevnik: 5-min sevanje IREICA1", "data/solar-5min.csv", "csvcol", "date", 60,
     "test-napovedi-daily.yml → log_solar_5min.py (backfill: hourly-backfill.yml)"),
    ("Dnevnik: 5-min sevanje Varpolje", "data/varpolje-solar-5min.csv", "csvcol", "date", 60,
     "test-napovedi-daily.yml → log_varpolje_solar.py (vir: worker cron varpolje_solar, hrani 72 h)"),
    ("Dnevnik: osvežitve MTR (živa)", "data/mtr-live-log.csv", "csvcol", "issued_at", 36,
     "mtr-live.yml → predict_recica_mos.py --live"),
    ("Odčitki snega ARSO (živo)", "data/arso-snow-live.csv", "csvcol", "valid_utc", 48,
     "arso-snow-live.yml (4×/dan)"),
    ("Preverjanje MTR snega", "data/sneg-verification.json", "ts", "generated_at", 48,
     "sneg-forecast.yml → verify_sneg.py"),
    ("Preverjanje prvega žarka (IREICA1)", "data/sonce-preverjanje.json", "date", "generated", 72,
     "test-napovedi-daily.yml → eval_sonce.py"),
    ("Dolinski dvoboj", "data/valley-duel-log.csv", "csvdate", None, 60,
     "valley-duel-log.yml"),
    ("Model MTR (mesečno učenje)", "model/recica-mos.json", "ts", "trained_at", 24 * 40,
     "mos-train.yml"),
    ("Indeksi AO/NAO/ENSO", "data/indeksi.json", "ts", "generated_at", 36,
     "atmos-forecast.yml → generate_indeksi_page.py (NOAA CPC)"),
    ("Stratosfera (GFS)", "data/stratosfera.json", "ts", "generated_at", 36,
     "atmos-forecast.yml → generate_stratosfera_page.py (GFS na AWS)"),
    ("Saharski prah (CAMS)", "data/prah.json", "ts", "generated_at", 36,
     "atmos-forecast.yml → generate_prah_page.py (Open-Meteo)"),
    ("Sinoptična karta (ECMWF)", "data/sinopticna.json", "ts", "generated_at", 48,
     "atmos-forecast.yml → generate_sinopticna_page.py (ECMWF open data, 00 UTC tek)"),
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
        if mode == "regexdate":
            with open(full, encoding="utf-8") as f:
                m = re.search(param, f.read())
            return end_of_day(m.group(1)) if m else None
        if mode == "csvdate":
            with open(full, encoding="utf-8") as f:
                rows = [r for r in csv.reader(f) if r]
            return end_of_day(rows[-1][0])
        if mode == "csvcol":
            with open(full, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            v = rows[-1][param].strip()
            return end_of_day(v) if len(v) == 10 else parse_ts(v)
        with open(full, encoding="utf-8") as f:
            data = json.load(f)
        if mode == "firstdate":
            return end_of_day(data[0][param])
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
        stamp = t.astimezone(TZ) - datetime.timedelta(seconds=1) if mode in ("date", "maxkey", "csvdate", "csvcol", "regexdate") else t.astimezone(TZ)
        label = stamp.strftime("%-d. %-m. %Y") + ("" if mode in ("date", "maxkey", "csvdate", "csvcol", "regexdate") else stamp.strftime(" %H:%M"))
        out.append({"name": name, "path": path, "status": "stale" if age > max_h else "ok",
                    "age_h": round(age, 1), "max_h": max_h, "hint": hint, "updated": label})
    return out


WORKER = "https://weatherireica1.filip-eremita.workers.dev"
# Cloudflare zavrne privzeti »Python-urllib« User-Agent s 403 (glej tools/test_worker_ua.py).
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"


def worker_health(fetch=None):
    """Zdravje Cloudflare cron opravil iz workerjevega /health (glej _cronBeat v worker.js).
    Opravilo je »neuspešno«, če je zadnji tek javil napako, in »zastarelo«, če ni teklo
    dlje, kot dovoljuje CRON_JOBS. `fetch` je za teste."""
    try:
        if fetch is None:
            import urllib.request
            with urllib.request.urlopen(urllib.request.Request(f"{WORKER}/health", headers={"User-Agent": WORKER_UA}), timeout=20) as r:
                data = json.load(r)
        else:
            data = fetch()
        jobs = data["jobs"]
    except Exception as e:  # noqa: BLE001
        return [{"name": "Worker: cron opravila", "path": "/health", "status": "unreadable", "age_h": None,
                 "max_h": None, "hint": f"/health ni dosegljiv ali ni veljaven ({type(e).__name__}) — deploy-worker.yml, Cloudflare"}]
    out = []
    for name, j in sorted(jobs.items()):
        age_h = None if j.get("age_min") is None else round(j["age_min"] / 60, 1)
        status = "ok"
        if j.get("stale"):
            status = "stale"
        elif not j.get("ok"):
            status = "failing"
        out.append({"name": f"Worker cron: {name}", "path": "/health", "status": status, "age_h": age_h,
                    "max_h": round(j["max_min"] / 60, 1) if j.get("max_min") else None,
                    "hint": (j.get("err") or "zadnji tek je uspel") if status != "ok" else "ok",
                    "updated": "—" if age_h is None else f"pred {fmt_age(age_h)}"})
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
        icon = {"ok": "✅", "stale": "⚠️ zastarelo", "unreadable": "❌ ni berljivo", "failing": "❌ napaka"}[r["status"]]
        lines.append(f"| {r['name']} (`{r['path']}`) | {icon} | {fmt_age(r['age_h'])} | {fmt_age(r['max_h'])} | "
                     f"{r.get('updated', '—')} | {r['hint']} |")
    return "\n".join(lines) + "\n", len(bad)


def main():
    results = evaluate() + worker_health()
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
