#!/usr/bin/env python3
"""tools/test_zima_gate.py — vrata zima-forecast.yml, ponovni poskusi Open-Meteo in preverjanje svežine (26. 11. 2026).

Ozadje: 25. 11. 2026 je en »handshake operation timed out« pustil crnivec.si na podatkih z 24. 11., tek pa je bil zelen,
GitHubov cron pa je zimo zagnal šele ob 16:00 UTC. Preverja:
  - `zima_gate.decide()`: skozi spusti samo tek, ki podatkov danes (po lokalnem datumu) še ni osvežil, ali `--force`;
  - `zima_gate.check_fresh()`: meja 30 h;
  - `winter_engine.fetch_open_meteo_retry()`: 4 poskusi z zamiki 5/15/45 s, ob izčrpanju vrže zadnjo napako, `main()` pa jo ujame;
  - zgradbo workflowa (posel `gate`, `needs`, `force` privzeto true, zadnji korak `require-fresh`) in da worker zimo sproži z `force: "false"`.
"""
import datetime
import importlib.util
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
FAILS = []


def check(ok, name, detail=""):
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UTC = datetime.timezone.utc
gate = load("zima_gate")


def at(y, mo, d, h, mi=0):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=UTC)


# ── vrata ─────────────────────────────────────────────────────────────────
now = at(2026, 11, 26, 4, 10)          # 5:10 po naši uri
ok, why = gate.decide(now, at(2026, 11, 25, 16, 13))
check(ok is True, "včerajšnji podatki: tek gre skozi", why)
ok, why = gate.decide(now, at(2026, 11, 26, 3, 5))
check(ok is False, "podatki osveženi danes ob 4:05 po naši uri: tek se preskoči", why)
ok, why = gate.decide(now, at(2026, 11, 26, 3, 5), force=True)
check(ok is True, "--force obide vrata", why)
ok, why = gate.decide(now, None)
check(ok is True, "brez winter-data.json tek gre skozi", why)
# lokalni datum, ne UTC: osvežitev ob 23:30 UTC (= 0:30 po naši uri naslednjega dne) je že »današnja« ob 4:10 UTC
ok, why = gate.decide(now, at(2026, 11, 25, 23, 30))
check(ok is False, "osvežitev ob 0:30 po naši uri šteje za današnjo (lokalni, ne UTC datum)", why)
ok, why = gate.decide(at(2026, 11, 26, 22, 45), at(2026, 11, 26, 3, 5))
check(ok is False, "ob 23:45 po naši uri je še isti lokalni dan: preskok", why)
ok, why = gate.decide(at(2026, 11, 26, 23, 30), at(2026, 11, 26, 3, 5))
check(ok is True, "ob 0:30 po naši uri je naslednji lokalni dan: tek gre skozi", why)
# po napaki (generated_at se ni premaknil) naslednji termin 30 min pozneje poskusi znova
stale = at(2026, 11, 25, 16, 13)
check(gate.decide(at(2026, 11, 26, 4, 40), stale)[0] and gate.decide(at(2026, 11, 26, 5, 40), stale)[0],
      "po neuspeli osvežitvi vsi naslednji termini poskusijo znova")

# ── svežina ───────────────────────────────────────────────────────────────
check(gate.check_fresh(at(2026, 11, 26, 10), at(2026, 11, 25, 16, 13))[0], "20 h star podatek še ni napaka")
check(gate.check_fresh(at(2026, 11, 26, 22), at(2026, 11, 25, 16, 0), 30)[0], "30 h je še v redu (meja je stroga)")
check(not gate.check_fresh(at(2026, 11, 26, 23), at(2026, 11, 25, 16, 0), 30)[0], "31 h star podatek je napaka")
check(not gate.check_fresh(at(2026, 11, 26, 10), None)[0], "brez časa osvežitve je napaka")

# izpis za GITHUB_OUTPUT
with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, "out")
    os.environ["GITHUB_OUTPUT"] = out
    gate.load_generated = lambda *a, **k: datetime.datetime.now(UTC)
    gate.main(["check"])
    gate.load_generated = lambda *a, **k: datetime.datetime.now(UTC) - datetime.timedelta(days=2)
    gate.main(["check"])
    lines = open(out, encoding="utf-8").read().split()
    check(lines == ["proceed=false", "proceed=true"], "GITHUB_OUTPUT: svež podatek false, star true", str(lines))
    check(gate.main(["require-fresh", "30"]) == 1, "require-fresh: 2 dni star podatek da izhod 1")
    gate.load_generated = lambda *a, **k: datetime.datetime.now(UTC)
    check(gate.main(["require-fresh", "30"]) == 0, "require-fresh: svež podatek da izhod 0")
os.environ.pop("GITHUB_OUTPUT", None)

# ── ponovni poskusi Open-Meteo ────────────────────────────────────────────
we = load("winter_engine")
check(we.OM_RETRY_DELAYS_S == (5, 15, 45), "zamiki ponovnih poskusov 5/15/45 s", str(we.OM_RETRY_DELAYS_S))


def flaky(fail_times):
    state = {"n": 0}

    def fetch():
        state["n"] += 1
        if state["n"] <= fail_times:
            raise TimeoutError("_ssl.c:994: The handshake operation timed out")
        return {"hourly": {"time": []}}
    return fetch, state


sleeps = []
we.fetch_open_meteo, st = flaky(0)
r = we.fetch_open_meteo_retry(sleep=sleeps.append)
check(r == {"hourly": {"time": []}} and st["n"] == 1 and sleeps == [], "uspešen prvi poskus: brez čakanja", str((st, sleeps)))

sleeps = []
we.fetch_open_meteo, st = flaky(2)
r = we.fetch_open_meteo_retry(sleep=sleeps.append)
check(r is not None and st["n"] == 3 and sleeps == [5, 15], "dva izpada, tretji uspe (čakanje 5 s in 15 s)", str((st, sleeps)))

sleeps = []
we.fetch_open_meteo, st = flaky(99)
try:
    we.fetch_open_meteo_retry(sleep=sleeps.append)
    check(False, "po štirih izpadih vrže napako")
except TimeoutError:
    check(st["n"] == 4 and sleeps == [5, 15, 45], "štirje poskusi, trije zamiki, nato napaka", str((st, sleeps)))

# main(): izpad se ujame, stari winter-data.json ostane, izhod 0 (rdeč tek poskrbi require-fresh)
real_sleep = time.sleep
time.sleep = lambda s: None
try:
    we.fetch_open_meteo, st = flaky(99)
    before = os.path.getmtime(os.path.join(ROOT, "data", "winter-data.json")) if os.path.exists(os.path.join(ROOT, "data", "winter-data.json")) else None
    rc = we.main()
    after = os.path.getmtime(os.path.join(ROOT, "data", "winter-data.json")) if os.path.exists(os.path.join(ROOT, "data", "winter-data.json")) else None
    check(rc == 0 and st["n"] == 4, "main() ob izpadu: 4 poskusi in izhod 0", str((rc, st)))
    check(before == after, "main() ob izpadu ne spremeni data/winter-data.json")
finally:
    time.sleep = real_sleep

# ── zgradba workflowa in workerja ─────────────────────────────────────────
wf = open(os.path.join(ROOT, ".github", "workflows", "zima-forecast.yml"), encoding="utf-8").read()
check(re.search(r"^  gate:\n", wf, re.M) is not None, "workflow ima posel gate")
check("needs: gate" in wf and "needs.gate.outputs.proceed == 'true'" in wf, "posel zima čaka na gate in se preskoči brez proceed=true")
check(re.search(r"inputs:\s*\n\s+force:\s*\n(?:.*\n){1,3}?\s+default: 'true'", wf) is not None, "ročni zagon ima force privzeto true")
check("inputs.force == 'true'" in wf and "'--force'" in wf, "force=true se prenese vratom kot --force")
runs = re.findall(r"^        run: (.+)$", wf, re.M)
check(bool(runs) and "zima_gate.py require-fresh" in runs[-1], "zadnji korak je require-fresh", runs[-1] if runs else "")
check("zima_gate.py check" in wf, "gate kliče zima_gate.py check")

worker = open(os.path.join(ROOT, "worker.js"), encoding="utf-8").read()
check('"zima-forecast.yml": await _cronDispatchGithubWorkflow(env, "zima-forecast.yml", { force: "false" })' in worker,
      "worker zimo sproži s force: \"false\"")

print(f"{len(FAILS)} napak" if FAILS else "✓ vsi testi zima_gate uspešni")
sys.exit(1 if FAILS else 0)
