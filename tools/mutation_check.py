#!/usr/bin/env python3
"""
tools/mutation_check.py — ali test_parity.py res ujame razhajanje?

Test je koristen le, če pade, ko se koda pokvari. Ta skript po vrsti vnese po eno majhno
napako (MUTACIJE: sprememba praga, konstante, oznake, obrnjen pogoj, odstranjena
varovalka), požene PRIPADAJOČI test (privzeto `tools/test_parity.py`, sicer peti element
vnosa) in pričakuje padec. Mutant, ki preživi (test kljub napaki prehaja), je koda, ki je
test NE pokriva.

Datoteke se po vsaki mutaciji povrnejo z `git checkout` — zato mora biti drevo
čisto za datoteke v tabeli (skript sicer odkloni). Ne zaženi ga vzporedno z delom.

Usage:  python3 tools/mutation_check.py [-k podniz]       (traja ~6 s na mutacijo; vse ~6 min)
Izhod:  1, če kak mutant preživi.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (opis, datoteka, staro, novo[, test])  — `staro` se mora v datoteki pojaviti natanko enkrat;
# `test` je skripta v tools/ (privzeto test_parity.py)
MUTACIJE = [
    ("FWI razred (app.js)", "app.js", "if(v<5.2)return{label:'Nizka'", "if(v<5.3)return{label:'Nizka'"),
    ("FWI razred (gasilec.js)", "meteogasilec/gasilec.js", "if (v < 11.2) return { label: 'Zmerna'", "if (v < 11.3) return { label: 'Zmerna'"),
    ("FWI razred (Python)", "tools/gasilec_model.py", '("Zelo visoka", "#ef4444", 21.3, 38.0)', '("Zelo visoka", "#ef4444", 21.3, 39.0)'),
    ("FWI formula (app.js): DC", "app.js", "0.36*(T+2.8)+Lf", "0.36*(T+2.9)+Lf"),
    ("vodostaj: približni prag (app.js)", "app.js", "const _RIVER_THRESHOLDS={normal:30,raised:80", "const _RIVER_THRESHOLDS={normal:30,raised:81"),
    ("vodostaj: približni prag (Python)", "tools/generate_vodostaj_page.py", 'THRESHOLDS = {"raised": 80', 'THRESHOLDS = {"raised": 81'),
    ("poledica: sevalni primanjkljaj (Python)", "tools/winter_engine.py", "GROUND_OFFSET_MAX_C = 3.0", "GROUND_OFFSET_MAX_C = 2.9"),
    ("poledica: sevalni primanjkljaj (JS na strani)", "crnivec-site/index.html", "var off = 3.0;", "var off = 2.9;"),
    ("poledica: prag rosišča (Python)", "tools/winter_engine.py", "near_saturated = d is not None and d >= g - 1.0", "near_saturated = d is not None and d >= g - 1.1"),
    ("vozišče: padavine 3 h (Python)", "tools/generate_crnivec_page.py", '(precip_3h or 0) >= 0.2:', '(precip_3h or 0) >= 0.3:'),
    ("vozišče: padavine 3 h (JS na strani)", "crnivec-site/index.html", '(p3 || 0) >= 0.2', '(p3 || 0) >= 0.3'),
    ("izzvenevanje popravka (Python)", "tools/generate_crnivec_page.py", "NEXT_BIAS_HOURS = 6\n", "NEXT_BIAS_HOURS = 5\n"),
    ("meja sneženja: odmik (Python)", "tools/winter_engine.py", "SNOW_LEVEL_OFFSET_M = 250", "SNOW_LEVEL_OFFSET_M = 260"),
    ("FNV-1a: praštevilo (JS na strani)", "crnivec-site/index.html", "0x01000193", "0x01000194"),
    ("napovej: toleranca (worker)", "worker.js", "const NAPOVEJ_TOL_T = 5;", "const NAPOVEJ_TOL_T = 6;"),
    ("napovej: toleranca (napovej.js)", "napovej/napovej.js", "var TOL_T = 5;", "var TOL_T = 6;"),
    ("igra Črnivec: najkrajši čas (worker)", "worker.js", "const CRN_IGRA_MIN_S = 130;", "const CRN_IGRA_MIN_S = 30;"),
    ("Termika: dolžina koridorja (worker)", "worker.js", "celje: 44.57", "celje: 44.0"),
    ("opažanja gob: količine (worker)", "worker.js", 'const KOLICINE = ["posamezno", "nekaj", "obilo"];', 'const KOLICINE = ["posamezno", "nekaj", "obilo", "veliko"];'),
    ("gobarski prag (JS na strani)", "gobarska-napoved/index.html", 'if(p>=75)return"Odlično"', 'if(p>=76)return"Odlično"'),
    ("nevihtna karta: stopnja (app.js)", "app.js", "if(s>=60)return'Ekstremno'", "if(s>=61)return'Ekstremno'"),
    ("nevihtna karta: mesto (app.js)", "app.js", "const SLO_CITIES=[\n  {n:'Ljubljana',la:46.056", "const SLO_CITIES=[\n  {n:'Ljubljana',la:46.057"),
    ("nevihtna karta: stopnja (Python)", "tools/generate_storm_map.py", "    if s >= 40:\n        return \"VISOKO\"", "    if s >= 41:\n        return \"VISOKO\""),
    ("smeri vetra (worker)", "worker.js", 'const d = ["S", "SSV",', 'const d = ["S", "SNV",'),
    ("smeri vetra (gasilec.js)", "meteogasilec/gasilec.js", "'S', 'SSV', 'SV'", "'S', 'SNV', 'SV'"),
    ("ocena dneva Termika (Python)", "tools/generate_igra_page.py", "elif dvig < 1.0:", "elif dvig < 1.1:"),
    ("ocena dneva Termika (igra.js)", "igra/igra.js", "if (climb < 1.0) return { title: 'Šibek dan'", "if (climb < 1.1) return { title: 'Šibek dan'"),
    ("hmelj: stopnja (app.js)", "app.js", "{min:150, max:400,", "{min:150, max:410,"),
    ("bolezni: oznaka (Python)", "tools/generate_agrometeo_page.py", 'return "nizka" if pct < 30', 'return "nizka" if pct < 31'),
    ("starost meritve DRSI (worker)", "worker.js", "/ 60000 <= 40) ? st : null", "/ 60000 <= 41) ? st : null"),
    ("prag sunkov (worker)", "worker.js", "CRN_SUNKI_KMH = 70", "CRN_SUNKI_KMH = 71"),
    ("značka: konstanta (worker)", "worker.js", "const SNOW_OFFSET = 250, SNOW_HALFWIDTH = 100;", "const SNOW_OFFSET = 260, SNOW_HALFWIDTH = 100;"),
    ("značka: cona (worker)", "worker.js", 'else if (tempC != null && tempC > 5) { zoneLabel = "suho"', 'else if (tempC != null && tempC > 6) { zoneLabel = "suho"'),
    ("prag mokrega dne (napovej.js)", "napovej/napovej.js", "var MOKER_MM = 0.2;", "var MOKER_MM = 0.3;"),
    # ── časovna vrata kart (test_gates.py) ────────────────────────────────────
    ("vrata: konec okna (nevihtna)", "tools/storm_map_gate.py", "WINDOW_END = 8 ", "WINDOW_END = 9 ", "test_gates.py"),
    ("vrata: pozni tek odstranjen (nevihtna)", "tools/storm_map_gate.py", "if WINDOW_END <= now.hour < LATE_END:", "if False:", "test_gates.py"),
    ("vrata: pozni tek brez zgornje meje (padavinska)", "tools/precip_map_gate.py", "LATE_END = 20", "LATE_END = 24", "test_gates.py"),
    ("vrata: začetek okna (padavinska)", "tools/precip_map_gate.py", "WINDOW_START = 6 ", "WINDOW_START = 5 ", "test_gates.py"),
    # ── zastareli vhodi (test_stale_inputs.py) ────────────────────────────────
    ("zastareli vhod: zgodba po lead", "tools/generate_story_card.py", 'if d.get("date") == tomorrow_iso), None)', 'if d.get("lead") == 1), None)', "test_stale_inputs.py"),
    ("zastareli vhod: članek po lead", "tools/generate_daily_post.py", 'if d.get("date") == tomorrow), None)', 'if d.get("lead") == 1), None)', "test_stale_inputs.py"),
    ("zastareli vhod: gasilska karta brez datuma", "tools/generate_gasilec_page.py", 'storm.get("date") != TODAY.isoformat()', 'False', "test_stale_inputs.py"),
    ("zastareli vhod: povzetek po lead", "tools/send_morning_digest.py", 'if d.get("date") == today), None)', 'if d.get("lead") == 1), None)', "test_stale_inputs.py"),
    ("zastareli vhod: povzetek pending brez datuma", "tools/send_morning_digest.py", 'if e.get("target_date") == today and', 'if True and', "test_stale_inputs.py"),
    # ── preverjanje karte proti strelam (test_storm_verify.py) ────────────────
    ("preverjanje: pokritost", "tools/verify_storm_map.py", "MIN_COVERAGE = 0.90", "MIN_COVERAGE = 0.30", "test_storm_verify.py"),
    ("preverjanje: začetek zapisa pokritosti", "tools/verify_storm_map.py", "since > od + 600000", "False", "test_storm_verify.py"),
    ("preverjanje: kontingenca (zadetek)", "tools/verify_storm_map.py", 'key = "a" if (score >= t and obs) else', 'key = "a" if (score > t and obs) else', "test_storm_verify.py"),
    ("preverjanje: stopnja ZMERNO", "tools/verify_storm_map.py", "    if s >= 22:\n        return \"ZMERNO\"", "    if s >= 23:\n        return \"ZMERNO\"", "test_storm_verify.py"),
    ("preverjanje: SQL celice (izhodišče mreže)", "worker.js", "(lat - 45.45) / 0.18", "(lat - 45.40) / 0.18", "test_storm_verify.py"),
    # ── LightningLogger (test_lightning_logger.py) ────────────────────────────
    ("strele: zombi prag", "worker.js", "const LTG_STALE_MS = 180000;", "const LTG_STALE_MS = 9999999;", "test_lightning_logger.py"),
    ("strele: odpiranje se nikoli ne zamenja", "worker.js", "const LTG_CONNECT_TIMEOUT_MS = 20000;", "const LTG_CONNECT_TIMEOUT_MS = 99999999;", "test_lightning_logger.py"),
    ("strele: alarm ob prekinitvi", "worker.js", "const dropped = () => { if (this.ws === ws) { this.ws = null; this._scheduleReconnect(LTG_RECONNECT_MS); } };", "const dropped = () => { if (this.ws === ws) { this.ws = null; } };", "test_lightning_logger.py"),
    ("strele: stara vtičnica se ne zapre", "worker.js", "try { this.ws.close(); } catch (_) {}\n      this.ws = null;", "this.ws = null;", "test_lightning_logger.py"),
    ("strele: stari close pobriše novo vtičnico", "worker.js", "const dropped = () => { if (this.ws === ws) {", "const dropped = () => { if (true) {", "test_lightning_logger.py"),
    # ── varuh svežine / zdravje workerja (test_freshness.py) ──────────────────
    ("svežina: prag starosti", "tools/check_freshness.py", '"stale" if age > max_h else "ok"', '"stale" if age > max_h * 100 else "ok"', "test_freshness.py"),
    ("zdravje: čakanje na prvi tek", "worker.js", "const waiting = !rec && since != null && (now - since) / 60000 <= maxMin;", "const waiting = false;", "test_freshness.py"),
    ("zdravje: zapis prvega časa", "worker.js", 'if (!(await kv.get("cron:health:_since"))) await kv.put("cron:health:_since", String(t0));', "", "test_freshness.py"),
    # ── posnetek rr24h (test_precip_snapshot.py) ──────────────────────────────
    ("rr24h: neberljivo število ni postaja", "worker.js", "if (!isFinite(mm)) continue;", "", "test_precip_snapshot.py"),
    # ── dolinski profil (test_valley_profile.py) ──────────────────────────────
    ("profil: prag inverzije", "app.js", "if(lapse>0){kind='inversion'", "if(lapse>0.5){kind='inversion'", "test_valley_profile.py"),
    ("profil: prag običajnega gradienta", "app.js", "else if(lapse>-0.9){kind='normal'", "else if(lapse>-1.2){kind='normal'", "test_valley_profile.py"),
    # ── zasebnost (test_privacy.py) ───────────────────────────────────────────
    ("zasebnost: worker /ecowitt-current", "worker.js", "if (ewData && ewData.data) delete ewData.data.indoor;", "", "test_privacy.py"),
    ("zasebnost: worker /varpolje-current", "worker.js", "          delete vpData.indoor;\n", "", "test_privacy.py"),
    ("zasebnost: kartica zgodbe", "tools/generate_story_card.py", 'payload.pop("indoor", None)', "pass", "test_privacy.py"),
    ("zasebnost: dnevni članek", "tools/generate_daily_post.py", 'current["data"].pop("indoor", None)', "pass", "test_privacy.py"),
    ("zasebnost: zmrzal", "tools/calculate_frost_risk.py", 'current["data"].pop("indoor", None)', "pass", "test_privacy.py"),
    ("zasebnost: korenska kopija članka", "generate_daily_post.py", 'current["data"].pop("indoor", None)', "pass", "test_privacy.py"),
]


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def main():
    only = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv else None
    dirty = git("status", "--porcelain", "--", *sorted({m[1] for m in MUTACIJE})).stdout.strip()
    if dirty:
        print("Datoteke iz tabele imajo neshranjene spremembe — najprej jih shrani ali povrni:\n" + dirty)
        return 2
    survived, skipped, ran = [], [], 0
    for opis, rel, old, new, *rest in MUTACIJE:
        test = rest[0] if rest else "test_parity.py"
        if only and only not in opis:
            continue
        path = os.path.join(ROOT, rel)
        src = open(path, encoding="utf-8").read()
        if src.count(old) != 1:
            skipped.append((opis, f"vzorec se v {rel} pojavi {src.count(old)}×, pričakovan 1×"))
            continue
        try:
            open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", test)], cwd=ROOT,
                               capture_output=True, text=True, timeout=300)
        finally:
            git("checkout", "--", rel)
        killed = r.returncode != 0
        ran += 1
        print(f"{'✓ ujet   ' if killed else '✗ PREŽIVEL'} {opis}")
        if not killed:
            survived.append(opis)
    print(f"\n{ran - len(survived)} ujetih, {len(survived)} preživelih, {len(skipped)} preskočenih")
    for opis, why in skipped:
        print(f"  preskočeno: {opis} — {why}")
    for opis in survived:
        print(f"  PREŽIVEL: {opis}")
    return 1 if survived or skipped else 0


if __name__ == "__main__":
    sys.exit(main())
