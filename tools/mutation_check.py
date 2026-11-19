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
    ("svežina: seznam bere prvi zapis", "tools/check_freshness.py", 'end_of_day(data[0][param])', 'end_of_day(data[-1][param])', "test_freshness.py"),
    ("svežina: prag starosti", "tools/check_freshness.py", '"stale" if age > max_h else "ok"', '"stale" if age > max_h * 100 else "ok"', "test_freshness.py"),
    ("zdravje: čakanje na prvi tek", "worker.js", "const waiting = !rec && since != null && (now - since) / 60000 <= maxMin;", "const waiting = false;", "test_freshness.py"),
    ("zdravje: zapis prvega časa", "worker.js", 'if (!(await kv.get("cron:health:_since"))) await kv.put("cron:health:_since", String(t0));', "", "test_freshness.py"),
    # ── posnetek rr24h (test_precip_snapshot.py) ──────────────────────────────
    ("rr24h: neberljivo število ni postaja", "worker.js", "if (!isFinite(mm)) continue;", "", "test_precip_snapshot.py"),
    # ── dolinski profil (test_valley_profile.py) ──────────────────────────────
    ("profil: prag inverzije", "app.js", "if(lapse>0){kind='inversion'", "if(lapse>0.5){kind='inversion'", "test_valley_profile.py"),
    ("profil: prag običajnega gradienta", "app.js", "else if(lapse>-0.9){kind='normal'", "else if(lapse>-1.2){kind='normal'", "test_valley_profile.py"),
    # ── napoved ur zasidrana na meritev (test_anchor.py) ──────────────────────
    ("sidro: izzvenevanje", "app.js", "const w=Math.max(0,1-(h.t.getTime()-nowMs)/(ANCHOR_HOURS*3600000));", "const w=1;", "test_anchor.py"),
    ("sidro: omejitev popravka", "app.js", "Math.max(-ANCHOR_MAX_C,Math.min(ANCHOR_MAX_C,obsT-modelNow))", "obsT-modelNow", "test_anchor.py"),
    ("sidro: starost meritve", "app.js", "!(obsAgeMin<=ANCHOR_MAX_AGE_MIN)", "false", "test_anchor.py"),
    ("sidro: interpolacija modela", "app.js", "modelNow+=(nx.temp-modelNow)*(nowMs-ti)/(tn-ti);", "", "test_anchor.py"),
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
    ("365-0 štetje: omejitev po IP [8.11.]", "worker.js", '"g365_rl", 120, 3600', '"g365_rl", 120000, 3600', "test_g365_stat.mjs"),
    ("365-0 štetje: preverjanje teme [8.11.]", "worker.js", '(!mystery && !G365_CHASES.includes(chase))) {', '(!mystery && false)) {', "test_g365_stat.mjs"),
    ("365-0 štetje: točke uganke [8.11.]", "worker.js", "if (Number.isInteger(pts) && pts >= 0 && pts <= 4)", "if (true)", "test_g365_stat.mjs"),
    ("365-0 štetje: preverjanje ocene [8.11.]", "worker.js", 'if (G365_GRADES.includes(body.grade))', 'if (body.grade)', "test_g365_stat.mjs"),
    ("sneg: omejitev poročil po IP [18.11.]", "worker.js", '"sneg_porocilo_rl", 30, 3600', '"sneg_porocilo_rl", 30000, 3600', "test_sneg.mjs"),
    ("sneg: ista celica enkrat na 2 uri [18.11.]", "worker.js", "if (await kv.get(cellKey)) return _sj(", "if (false) return _sj(", "test_sneg.mjs"),
    ("sneg: najmanj poročil za sodbo [18.11.]", "worker.js", "const SNEG_MIN_N = 3;", "const SNEG_MIN_N = 2;", "test_sneg.mjs"),
    ("sneg: delež soglasja za sodbo [18.11.]", "worker.js", "const SNEG_MIN_SHARE = 0.6;", "const SNEG_MIN_SHARE = 0.5;", "test_sneg.mjs"),
    ("ugibalnik: en ugib na igralca [18.11.]", "worker.js", 'if (ex) return _sj({ error: "Že si ugibal.", datum: ex.datum }, 409);', "", "test_sneg.mjs"),
    ("ugibalnik: obseg datuma [18.11.]", "worker.js", "if (datum < _danesLj() || datum >", "if (false || datum >", "test_sneg.mjs"),
    ("ugibalnik: ugib na dan snega se ne šteje [18.11.]", "zima/sneg-ugibalnik/ugibalnik.js", "return ljDate(g[2]) < resolved;", "return ljDate(g[2]) <= resolved;", "test_sneg.mjs"),
    ("ugibalnik: izenačenje po času oddaje [18.11.]", "zima/sneg-ugibalnik/ugibalnik.js", "a.razlika - b.razlika || (a.ts", "b.razlika - a.razlika || (a.ts", "test_sneg.mjs"),
    ("drva: način B (energija v prm) [18.11.]", "zima/poraba-drv/drva.js", "return area * q / eff * (hdd / refTotal) / kwhPrm;", "return area * q * eff * (hdd / refTotal) / kwhPrm;", "test_drva.mjs"),
    ("drva: način A (stalni del) [18.11.]", "zima/poraba-drv/drva.js", "return lastPrm * (fixed * (frac == null ? 1 : frac) + (1 - fixed) * hdd / baseTotal);", "return lastPrm * (fixed + (1 - fixed) * hdd / baseTotal);", "test_drva.mjs"),
    ("drva: preostanek sezone [18.11.]", "zima/poraba-drv/drva.js", "return Math.max(0, total - curve[idx - 1]);", "return Math.max(0, total - curve[idx]);", "test_drva.mjs"),
    ("prireditev: prag padavin strogo pod [18.11.]", "vreme-za-prireditev/prireditev.js", "return d.p < c.rain &&", "return d.p <= c.rain &&", "test_prireditev.mjs"),
    ("prireditev: okno ±w [18.11.]", "vreme-za-prireditev/prireditev.js", "for (var o = -w; o <= w; o++) {", "for (var o = -w; o < w; o++) {", "test_prireditev.mjs"),
    ("prireditev: manjkajoč podatek [18.11.]", "vreme-za-prireditev/prireditev.js", "if (data.t[i] == null || data.n[i]", "if (data.n[i]", "test_prireditev.mjs"),
    ("advent: januar je po sezoni [18.11.]", "adventni-koledar/advent.js", "if (dt.m === 1) return 24;", "if (dt.m === 1) return 0;", "test_advent.mjs"),
    ("advent: 24. 12. odpre zadnja vrata [18.11.]", "adventni-koledar/advent.js", "return Math.min(24, dt.d);", "return Math.min(23, dt.d);", "test_advent.mjs"),
    ("rojstni: manjkajoče polje odpade [18.11.]", "rojstnodnevno-vreme/rojstni.js", "if (data.t[i] == null || data.n[i] == null || data.p[i] == null) continue;", "if (data.t[i] == null) continue;", "test_rojstni.mjs"),
    ("rojstni: najhladneje je najnižja [18.11.]", "rojstnodnevno-vreme/rojstni.js", "if (rows[j].n < cold.n) cold = rows[j];", "if (rows[j].n > cold.n) cold = rows[j];", "test_rojstni.mjs"),
    ("zgrešitve: mesec z dovolj dnevi [18.11.]", "tools/generate_zgresitve_page.py", "if len(rows) >= MIN_DAYS:", "if len(rows) >= 1:", "test_zgresitve.py"),
    ("zgrešitve: največja napaka najprej [18.11.]", "tools/generate_zgresitve_page.py", "key=lambda r: (-r[0][0], r[1]))[:TOP]", "key=lambda r: (r[0][0], r[1]))[:TOP]", "test_zgresitve.py"),
    ("wrapped: zmrzal ≤ 0 [18.11.]", "tools/generate_wrapped_page.py", "frost=sum(1 for _, x in lows if x <= 0)", "frost=sum(1 for _, x in lows if x < 0)", "test_wrapped.py"),
    ("nebo: prag Kp 7 [18.11.]", "nebo-nocoj/nebo.js", "var KP_LIMIT = 7, KP_EDGE = 6;", "var KP_LIMIT = 6, KP_EDGE = 5;", "test_nebo.mjs"),
    ("nebo: oblačno od 70 % [18.11.]", "nebo-nocoj/nebo.js", "if (c < 70) return", "if (c < 80) return", "test_nebo.mjs"),
    ("nebo: sij brez Kp ne trdi možnosti [18.11.]", "nebo-nocoj/nebo.js", "var go = (k.lvl === 'go') && c.lvl !== 'no';", "var go = (k.lvl === 'go' || k.lvl === 'edge') && c.lvl !== 'no';", "test_nebo.mjs"),
    ("nebo: luna moti nad 50 % [18.11.]", "nebo-nocoj/nebo.js", "bad: m > 0.5", "bad: m > 0.9", "test_nebo.mjs"),
    ("elektrarna: PR množi energijo [18.11.]", "sonce-elektrarna/elektrarna.js", "days[d].kwh += Math.max(0, gti[i]) / 1000 * kwp * pr;", "days[d].kwh += Math.max(0, gti[i]) / 1000 * kwp;", "test_elektrarna.mjs"),
    ("elektrarna: negativno sevanje je 0 [18.11.]", "sonce-elektrarna/elektrarna.js", "else days[d].kwh += Math.max(0, gti[i])", "else days[d].kwh += (gti[i])", "test_elektrarna.mjs"),
    ("elektrarna: manjkajoča ura označi dan [18.11.]", "sonce-elektrarna/elektrarna.js", "if (gti[i] == null) days[d].missing++;", "if (gti[i] == null) days[d].missing += 0;", "test_elektrarna.mjs"),
    ("elektrarna: zgornja meja kWp [18.11.]", "sonce-elektrarna/elektrarna.js", "clamp(num(o.kwp, DEF.kwp), 0.1, 1000)", "clamp(num(o.kwp, DEF.kwp), 0.1, 100000)", "test_elektrarna.mjs"),
    ("zig: padavine pod 0,2 mm so brez [18.11.]", "vreme-na-fotografiji/zig.js", "(d.p >= 0.2 ?", "(d.p > 0 ?", "test_zig.mjs"),
    ("zig: manjkajoč dan brez žiga [18.11.]", "vreme-na-fotografiji/zig.js", "data.t[i] == null || data.n[i] == null || data.p[i] == null) return null;", "data.t[i] == null) return null;", "test_zig.mjs"),
    ("prireditev: izenačenje po bližini [18.11.]", "vreme-za-prireditev/prireditev.js", "b.p - a.p || Math.abs(a.off) - Math.abs(b.off);", "b.p - a.p || Math.abs(b.off) - Math.abs(a.off);", "test_prireditev.mjs"),
    ("tedenski: prag odstopanja temperature [18.11.]", "tools/generate_dolina_v_tednu.py", "elif anom is not None and abs(anom) >= 2:", "elif anom is not None and abs(anom) >= 4:", "test_dolina_v_tednu.py"),
    ("tedenski: prag mokrega tedna [18.11.]", "tools/generate_dolina_v_tednu.py", "rain >= 20 and rain >= 2 * r_norm", "rain >= 30 and rain >= 2 * r_norm", "test_dolina_v_tednu.py"),
    ("tedenski: najmanj dni meritev [18.11.]", "tools/generate_dolina_v_tednu.py", "MIN_DAYS = 6 ", "MIN_DAYS = 7 ", "test_dolina_v_tednu.py"),
    ("tedenski: najmanj prejšnjih let [18.11.]", "tools/generate_dolina_v_tednu.py", "MIN_PRIOR_YEARS = 3\n", "MIN_PRIOR_YEARS = 2\n", "test_dolina_v_tednu.py"),
    ("tedenski: prag zmrzali [18.11.]", "tools/generate_dolina_v_tednu.py", "elif frost >= 4:", "elif frost >= 5:", "test_dolina_v_tednu.py"),
    ("tedenski: omejitev prijav po IP [18.11.]", "worker.js", '"tedenski_rl", 5, 3600', '"tedenski_rl", 5000, 3600', "test_tedenski.mjs"),
    ("tedenski: povezava za odjavo obvezna [18.11.]", "worker.js", '|| !html.includes("{{ODJAVA}}"))', ')', "test_tedenski.mjs"),
    ("tedenski: en teden samo enkrat [18.11.]", "worker.js", "if (kv && !body.force && await kv.get(key))", "if (false)", "test_tedenski.mjs"),
    ("tedenski: samo potrjeni prejmejo [18.11.]", "worker.js", "const confirmed = await _rd(CONF);\n          if (!confirmed.length) return _js({ ok: true, sent: 0 });", "const confirmed = (await _rd(CONF)).concat(await _rd(PEND));\n          if (!confirmed.length) return _js({ ok: true, sent: 0 });", "test_tedenski.mjs"),
    ("drva: indeks dneva po novem letu [18.11.]", "zima/poraba-drv/drva.js", "Date.UTC(y - 1, 9, 1)) / 86400000);", "Date.UTC(y, 9, 1)) / 86400000);", "test_drva.mjs"),
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
    ("zimska opozorila: svežina po strani [29.10.]", "worker.js", "if (!page || !fresh(page)) continue;", "if (!page) continue;", "test_ocene.mjs"),
    ("zimska opozorila: meja novega snega [29.10.]", "tools/generate_zima_page.py", "SNEG_CM_BANDS = (0.2, 1.0, 5.0)", "SNEG_CM_BANDS = (0.2, 1.0, 50.0)", "test_zima_alarm.py"),
    ("zimska opozorila: meja inverzije [29.10.]", "tools/generate_zima_page.py", "MEGLA_TOP_BANDS = (500, 900)", "MEGLA_TOP_BANDS = (500, 9000)", "test_zima_alarm.py"),
    ("zimska opozorila: vrhovi nad meglo [29.10.]", "tools/generate_zima_page.py", 'l["elevation_m"] >= 1000 and l["elevation_m"] > top]', 'l["elevation_m"] >= 1000]', "test_zima_alarm.py"),
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
    ("hero lestvice: veter (app.js) [31.10.]", "app.js", "wind:n(s.wind)!=null?[s.wind/50*100", "wind:n(s.wind)!=null?[s.wind/60*100"),
    ("hero lestvice: tlak (Python) [31.10.]", "tools/inject_current_weather.py", "((pres - 980) / 60 * 100, None)", "((pres - 990) / 60 * 100, None)"),
    ("hero lestvice: dež (app.js) [31.10., od 4.11. količina]", "app.js", "Math.sqrt(Math.min(30,Math.max(0,s.rt))/30)*100", "Math.sqrt(Math.min(30,Math.max(0,s.rt))/32)*100"),
    # ── hero ikona: noč po sončnem zahodu, ikona pretekle ure, barva grafa (5. 11. 2026) ──
    ("hero noč: zahod namesto ure (app.js)", "app.js", "const night=_isNightAt(when,obs);", "const night=(when||new Date()).getHours()>22;"),
    ("hero noč: zahod namesto ure (Python)", "tools/inject_current_weather.py", "return local < st[0] or local > st[1]", "return local.hour < 5 or local.hour > 22"),
    ("hero ikona: pretekla ura prevzame _wxCond", "app.js", "const wc=(!past&&typeof _wxCond==='string')?_wxCond:'';", "const wc=typeof _wxCond==='string'?_wxCond:'';"),
    ("hero graf: pas 15–22 °C ni barva besedila", "app.js", "if(t>=15&&t<22)return isDark()?'#bef264':'#4d7c0f';", "if(false)return '';", "test_temp_barve.py"),
    ("sevanje soseda: starost posnetka", "worker.js", "const VPS_MAX_AGE_MS = 15 * 60000;", "const VPS_MAX_AGE_MS = 150 * 60000;", "test_varpolje_solar.py"),
    ("sevanje soseda: zadrževanje", "worker.js", "const VPS_HOLD_MS = 72 * 3600000;", "const VPS_HOLD_MS = 720 * 3600000;", "test_varpolje_solar.py"),
    ("sevanje soseda: prag razlike", "tools/eval_sonce_varpolje.py", "BIG_DIFF_MIN = 30.0", "BIG_DIFF_MIN = 130.0", "test_varpolje_solar.py"),
    ("izvoz podatkov: dnevi iz reanalize", "tools/export_dataset.py", 'EXCLUDE_SRC = {"era5"}', 'EXCLUDE_SRC = set()', "test_dataset_export.py"),
    ("zenodo: osnutek brez --publish", "tools/zenodo_publish.py", "    if do_publish:\n", "    if True:\n", "test_dataset_export.py"),
    ("čuvaj videza: meja CLS", "tools/visual_watch.mjs", "export const CLS_MAX = 0.10;", "export const CLS_MAX = 0.60;", "test_visual_watch.mjs"),
    ("čuvaj videza: mediana teh tekov", "tools/visual_watch.mjs", "const m = median(v);\n    if (!(m <= CLS_MAX))", "const m = Math.max(...v);\n    if (!(m <= CLS_MAX))", "test_visual_watch.mjs"),
    ("čuvaj videza: meja INP", "tools/visual_watch.mjs", "export const INP_MAX = 800;", "export const INP_MAX = 5000;", "test_visual_watch.mjs"),
    ("čuvaj videza: dotik šteje največji dogodek", "tools/visual_watch.mjs", "Math.max(by.get(e.id) || 0, e.d)", "e.d", "test_visual_watch.mjs"),
    ("čuvaj videza: dogodki brez interactionId", "tools/visual_watch.mjs", "if (e && e.id) by.set", "if (e) by.set", "test_visual_watch.mjs"),
    ("hero stavek: vrh jutri (24 ur)", "app.js", "const tomorrowPeak=Math.round(nMax)>Math.round(tMaxToday)&&", "const tomorrowPeak=false&&"),
    # ── Snegofili (test_snegofili.py, 19. 11. 2026) ──
    ("snegofili: zacetek okna naprej ne šteje ure, ki teče", "tools/snegofili_data.py", '("next24", idx_now + 1, idx_now + 24)', '("next24", idx_now, idx_now + 24)', "test_snegofili.py"),
    ("snegofili: okno nazaj 24 ur", "tools/snegofili_data.py", '("past24", idx_now - 23, idx_now)', '("past24", idx_now - 24, idx_now)', "test_snegofili.py"),
    ("snegofili: premalo ur nazaj: točka odpade", "tools/snegofili_data.py", 'idx_now < 71 or', 'idx_now < 40 or', "test_snegofili.py"),
    ("snegofili: izmerjeno ARSO starejše od 24 h ne velja", "tools/snegofili_data.py", 'if 0 <= age_h <= ARSO_MAX_AGE_H:', 'if 0 <= age_h:', "test_snegofili.py"),
    ("snegofili: meja sneženja: ±100 m do sneg", "tools/generate_snegofili_page.py", '"snow" if d >= 100 else', '"snow" if d >= 0 else', "test_snegofili.py"),
    ("snegofili: stopnje snega: prag 5 cm", "tools/generate_snegofili_page.py", '0 if cm < 5 else', '0 if cm < 6 else', "test_snegofili.py"),
    ("snegofili: vdelava: potrdilo pogojev in datum", "tools/generate_snegofili_page.py", 'not c.get("embed_terms") or not c.get("checked")', 'not c.get("checked")', "test_snegofili.py"),
    ("snegofili: vdelava: samo https", "tools/generate_snegofili_page.py", 'if u.scheme != "https" or u.hostname not in EMBED_HOSTS[kind]:', 'if u.hostname not in EMBED_HOSTS[kind]:', "test_snegofili.py"),
    ("snegofili: vdelava: dovoljen gostitelj", "tools/generate_snegofili_page.py", 'if u.scheme != "https" or u.hostname not in EMBED_HOSTS[kind]:', 'if u.scheme != "https":', "test_snegofili.py"),
    ("snegofili: povzetek: doseg izleta TRIP_KM", "tools/generate_snegofili_page.py", 'r["km_od_recice"] <= TRIP_KM and', 'r["km_od_recice"] >= TRIP_KM and', "test_snegofili.py"),
    ("snegofili: tuja kamera: samo https povezava", "tools/generate_snegofili_page.py", 'if str(c.get("url", "")).startswith("https://"):', 'if str(c.get("url", "")):', "test_snegofili.py"),
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
