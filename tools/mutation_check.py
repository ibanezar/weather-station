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
    ("push vnaprej: meje pragov (worker)", "worker.js", "const FC_THR_LIMITS = { wind: [10, 200]", "const FC_THR_LIMITS = { wind: [10, 201]"),
    ("push vnaprej: meje pragov (app.js)", "app.js", "const FC_THR_LIMITS={wind:[10,200]", "const FC_THR_LIMITS={wind:[10,199]"),
    ("igra Črnivec: najkrajši čas (worker)", "worker.js", "const CRN_IGRA_MIN_S = 130;", "const CRN_IGRA_MIN_S = 30;"),
    ("Termika: dolžina koridorja (worker)", "worker.js", "celje: 44.57", "celje: 44.0"),
    ("opažanja gob: količine (worker)", "worker.js", 'const KOLICINE = ["posamezno", "nekaj", "obilo", "nic"]; // "nic" = iskal sem, a nisem našel (negativen podatek)', 'const KOLICINE = ["posamezno", "nekaj", "obilo", "nic", "veliko"]; // "nic" = iskal sem, a nisem našel (negativen podatek)'),
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
    ("značka: cona (worker)", "worker.js", 'else if (tempC != null && tempC > 5) {\n              // Ob megli', 'else if (tempC != null && tempC > 6) {\n              // Ob megli'),
    ("prag mokrega dne (napovej.js)", "napovej/napovej.js", "var MOKER_MM = 0.2;", "var MOKER_MM = 0.3;"),
    # ── časovna vrata kart (test_gates.py) ────────────────────────────────────
    ("vrata: konec okna (nevihtna)", "tools/storm_map_gate.py", "WINDOW_END = 8 ", "WINDOW_END = 9 ", "test_gates.py"),
    ("vrata: pozni tek odstranjen (nevihtna)", "tools/storm_map_gate.py", "if WINDOW_END <= now.hour < LATE_END:", "if False:", "test_gates.py"),
    ("vrata: pozni tek brez zgornje meje (padavinska)", "tools/precip_map_gate.py", "LATE_END = 20", "LATE_END = 24", "test_gates.py"),
    ("vrata: okno pred meritvijo ARSO (padavinska)", "tools/precip_map_gate.py", "WINDOW_START = 7 ", "WINDOW_START = 6 ", "test_gates.py"),
    # ── zastareli vhodi (test_stale_inputs.py) ────────────────────────────────
    ("zastareli vhod: zgodba po lead", "tools/generate_story_card.py", 'if d.get("date") == date_iso), None)', 'if d.get("lead") == 1), None)', "test_stale_inputs.py"),
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
    # ── varovalke javnih vnosov in zimski cevovod (29. 10. 2026) ──────────────
    ("push: dovoljeni naslovi [29.10.]", "worker.js", 'return u.protocol === "https:" && !u.port && PUSH_HOST_OK.some(r => r.test(u.hostname));', 'return u.protocol === "https:";', "test_worker_abuse.mjs"),
    ("push: omejitev prijav [29.10.]", "worker.js", '"push_sub_rl", 30, 3600', '"push_sub_rl", 3000, 3600', "test_worker_abuse.mjs"),
    ("push: telo ni objekt [29.10.]", "worker.js", 'if (!body || typeof body !== "object") return pj({ error: "Napačni podatki" }, 400);', "", "test_worker_abuse.mjs"),
    ("napovej: omejitev po IP [29.10.]", "worker.js", '"napovej_vnos_rl", 10, 86400', '"napovej_vnos_rl", 10000, 86400', "test_worker_abuse.mjs"),
    ("igra: omejitev po IP [29.10.]", "worker.js", '"igra_rez_rl", 60, 3600', '"igra_rez_rl", 6000, 3600', "test_worker_abuse.mjs"),
    ("igra: zgornja meja slovarja [29.10.]", "worker.js", "obstojeci = _capPlayers(obstojeci, 1000, (a, b) => b.km - a.km);", "", "test_worker_abuse.mjs"),
    ("črnivec igra: omejitev po IP [29.10.]", "worker.js", '"crn_igra_rl", 60, 3600', '"crn_igra_rl", 6000, 3600', "test_worker_abuse.mjs"),
    ("komentarji: omejitev po IP [29.10.]", "worker.js", '"blog_comment_rl", 15, 3600', '"blog_comment_rl", 1500, 3600', "test_worker_abuse.mjs"),
    ("opažanja vremena: omejitev po IP [29.10.]", "worker.js", '"obs_rl", 10, 3600', '"obs_rl", 1000, 3600', "test_worker_abuse.mjs"),
    ("snežna karta: ura brez podatkov [29.10.]", "zima/snezna-karta/karta.js", "if(!arr.some(function(x){ return x!=null; })){", "if(false){", "test_snezna_karta.mjs"),
    ("točnost: zanesljivost razlike [29.10.]", "tools/generate_tocnost_page.py", "reliable = st.mean(diff) - 1.96 * se > 0", "reliable = True", "test_tocnost_answer.py"),
    ("točnost: stalna pristranskost [29.10.]", "tools/generate_tocnost_page.py", "if m >= 2 and abs(b) >= 0.8 * m:", "if False:", "test_tocnost_answer.py"),
    ("točnost: najmanj skupnih dni [29.10.]", "tools/generate_tocnost_page.py", "if len(days_all) < 10 or len(keys) < 2:", "if False:", "test_tocnost_answer.py"),
    ("llms-full: brez praznih vnosov [29.10.]", "tools/generate_llms_full.py", "    if not paras and not desc:\n        return None", "    pass", "test_llms_full.py"),
    ("zimski scenarij: topla plast žleda [29.10.]", "tools/winter_engine.py", "FREEZING_RAIN_WARM_MIN_C = 0.5 ", "FREEZING_RAIN_WARM_MIN_C = 3.0 ", "test_winter_scenario.py"),
    ("zimski scenarij: mraz pri tleh [29.10.]", "tools/winter_engine.py", "FREEZING_RAIN_T2M_MAX_C = 0.0 ", "FREEZING_RAIN_T2M_MAX_C = -5.0 ", "test_winter_scenario.py"),
    ("zimski scenarij: padavine žleda [29.10.]", "tools/winter_engine.py", "FREEZING_RAIN_PRECIP_MIN_MM = 0.1 ", "FREEZING_RAIN_PRECIP_MIN_MM = 1.0 ", "test_winter_scenario.py"),
    ("zimski scenarij: meja sneženja [29.10.]", "tools/winter_engine.py", "    effective = freezing_level_m - SNOW_LEVEL_OFFSET_M\n", "    effective = freezing_level_m + SNOW_LEVEL_OFFSET_M\n", "test_winter_scenario.py"),
    ("zimski scenarij: razmerje snega [29.10.]", "tools/winter_engine.py", "SNOW_RATIO_CM_PER_MM = 1", "SNOW_RATIO_CM_PER_MM = 0", "test_winter_scenario.py"),
    ("stratosfera: SSW samo pozimi [29.10.]", "tools/generate_stratosfera_page.py", "if winter and u < 0:", "if u < 0:", "test_atmos.py"),
    ("dnevne strani: veto vsote dežja [29.10.]", "tools/day_score_common.py", "def rain_pts(c, d, h0=8, h1=18, cap=3, sum_veto=0.5):", "def rain_pts(c, d, h0=8, h1=18, cap=3, sum_veto=5.0):", "test_day_pages.py"),
    ("zasebnost: članek z notranjo meritvijo [29.10.]", "blog/vroc-julijski-dan-v-zgornji-savinjski-dolini-kaj-pravijo-ste-0712.html", "<p>Sončno obsevanje", "<p>Notranji senzor kaže 25,1 °C. Sončno obsevanje", "test_privacy.py"),
    ("zasebnost: ecowitt-history [29.10.]", "worker.js", 'call_back: "outdoor.temperature,outdoor.humidity,wind.wind_speed,rainfall.daily,pressure.relative",', 'call_back: "outdoor.temperature,indoor.temperature,outdoor.humidity,wind.wind_speed,rainfall.daily,pressure.relative",', "test_privacy.py"),
    ("avtorizacija: podpis Paddle [30.10.]", "worker.js", "if (!_tsEqual(expected, sig.h1)) return _json({ error: \"Neveljaven podpis\" }, 401);", "", "test_worker_auth.mjs"),
    ("avtorizacija: ključ premium/data [30.10.]", "worker.js", "if (!syncKey || !_tsEqual(auth, `Bearer ${syncKey}`)) return _json({ error: \"Nedovoljeno\" }, 401);", "", "test_worker_auth.mjs"),
    ("avtorizacija: potek naročnine [30.10.]", "worker.js", "if (!sub?.expires || new Date(sub.expires) < new Date()) return null;", "if (!sub?.expires) return null;", "test_worker_auth.mjs"),
    ("avtorizacija: zaklep admin [30.10.]", "worker.js", "if (fails >= GALLERY_ADMIN_LOCKOUT_MAX) {", "if (false) {", "test_worker_auth.mjs"),
    ("avtorizacija: moderacija [30.10.]", "worker.js", "if (path === \"/nevihte/porocila/moderacija\" && request.method === \"POST\") {\n          if (!(await _npAdmin())) return _json({ error: \"Nepooblaščen dostop\" }, 401);", "if (path === \"/nevihte/porocila/moderacija\" && request.method === \"POST\") {", "test_worker_auth.mjs"),
    ("avtorizacija: push/send skrivnost [30.10.]", "worker.js", "if (!secret || !_safeEq(body.secret, secret)) return pj({ error: \"Nedovoljeno\" }, 401);", "", "test_worker_auth.mjs"),
    ("avtorizacija: gobe/alarm-notify [30.10.]", "worker.js", "if (!secret || !_safeEq(auth, `Bearer ${secret}`)) return j({ error: \"Nedovoljeno\" }, 401);", "", "test_worker_auth.mjs"),
    ("avtorizacija: premium/subscribers [30.10.]", "worker.js", "const auth = await _galleryAdminAuthed(request, env);\n          if (!auth.ok) return _json({ error: auth.error }, auth.status);\n          const cursor", "const cursor", "test_worker_auth.mjs"),
    ("lektura_scan: odstotek [30.10.]", "tools/lektura_scan.py", 'r"(?<![\\w.,])\\d+(?:,\\d+)?%"', 'r"(?<![\\w.,])\\d+(?:,\\d+)?%%"', "test_lektura_scan.py"),
    ("lektura_scan: izrez skript [30.10.]", "tools/lektura_scan.py", 'body = re.sub(r"<(script|style|svg|noscript|template|code|pre)\\b.*?</\\1>", " ", body, flags=re.S | re.I)', 'pass', "test_lektura_scan.py"),
    ("vrata pozebe: sezona [30.10.]", "tools/frost_gate.py", "SEASON_MONTHS = (3, 4, 5)", "SEASON_MONTHS = (3, 4, 5, 6)", "test_gates_daily.py"),
    ("vrata pozebe: popoldansko okno [30.10.]", "tools/frost_gate.py", '"afternoon": (14, 17)', '"afternoon": (14, 18)', "test_gates_daily.py"),
    ("vrata pozebe: stanje po terminu [30.10.]", "tools/frost_gate.py", "if state.get(slot, {}).get(\"lastRun\") == today and not force:", "if state.get(\"lastRun\") == today and not force:", "test_gates_daily.py"),
    ("vrata igre: konec okna [30.10.]", "tools/igra_gate.py", "WINDOW_END = 12 ", "WINDOW_END = 13 ", "test_gates_daily.py"),
    ("vrata igre: začetek okna [30.10.]", "tools/igra_gate.py", "WINDOW_START = 5 ", "WINDOW_START = 4 ", "test_gates_daily.py"),
    ("vrata povzetka: konec okna [30.10.]", "tools/digest_gate.py", "WINDOW_END = 18 ", "WINDOW_END = 19 ", "test_gates_daily.py"),
    ("vrata povzetka: že poslan [30.10.]", "tools/digest_gate.py", 'if state.get("lastSent") == today and not force:', 'if False:', "test_gates_daily.py"),
    ("vrata zgodovine: era5 ni meritev [30.10.]", "tools/update_history_gate.py", '.get("src") == "station":', '.get("src") in ("station", "era5"):', "test_gates_daily.py"),
    ("hub Na kratko: povprečne padavine [29.10.]", "tools/seo_smart_routine.py", 'f"{num(avg_ann_prec, 0)} mm padavin na leto; dni z mrazom', 'f"{num(avg_ann_prec, 1)} mm padavin na leto; dni z mrazom', "test_hub_kratko.py"),
    ("hub Na kratko: najbolj suho leto [29.10.]", "tools/seo_smart_routine.py", "najbolj suho {min_year}: {num(ann_prec_full[min_year], 0)} mm", "najbolj suho {min_year}: {num(ann_prec_full[max_year], 0)} mm", "test_hub_kratko.py"),
    ("hub Na kratko: rekord temperature [29.10.]", "tools/seo_smart_routine.py", "Rekordi postaje: {num(abs_max[1])} °C", "Rekordi postaje: {num(abs_min[1])} °C", "test_hub_kratko.py"),
]


def clear_bytecode():
    """Mutacija enake dolžine v isti sekundi bi pustila veljaven (mutiran) .pyc — zato ga povozimo."""
    for dirpath, dirs, _ in os.walk(os.path.join(ROOT, "tools")):
        for d in list(dirs):
            if d == "__pycache__":
                subprocess.run(["rm", "-rf", os.path.join(dirpath, d)])
                dirs.remove(d)


def pw_path():
    """Pot do Playwright za preizkuse v brskalniku (test_snezna_karta.mjs); PW iz okolja ima prednost."""
    if os.environ.get("PW"):
        return os.environ["PW"]
    try:
        return os.path.join(subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip(), "playwright")
    except OSError:
        return "playwright"


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
            cmd = (["node", os.path.join(ROOT, "tools", test)] if test.endswith(".mjs")
                   else [sys.executable, "-B", os.path.join(ROOT, "tools", test)])
            r = subprocess.run(cmd, cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PW": pw_path()},
                               capture_output=True, text=True, timeout=300)
        finally:
            git("checkout", "--", rel)
            clear_bytecode()
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
