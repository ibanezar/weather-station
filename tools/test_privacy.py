#!/usr/bin/env python3
"""tools/test_privacy.py — notranje meritve iz hiše NIKOLI ne smejo ven.

CLAUDE.md (prvi razdelek): postaja meri tudi notranjo temperaturo in vlago, to je
Filipova zasebna stvar. Pravilo je »zarezano« na več mestih, a nič ni preverjalo,
da zarezi res držita — ob novem odjemalcu je pravilo lahko tiho pozabljeno (30. 7.
2026 je dnevni članek objavil notranjo temperaturo). Ta test preverja VEDENJE:

1. worker.js: PRAVI worker se požene z lažnim Ecowittom/Varpoljem, ki vrneta blok
   `indoor`; javne točke (/ecowitt-current, /varpolje-current, /current) ne smejo
   vsebovati ne ključa ne vrednosti.
2. Python odjemalci (dnevni članek, kartica za zgodbe, zmrzal, korenska kopija):
   fetch_current() ob odgovoru z `indoor` ne sme vrniti ničesar od tega.
3. Vsak NOV odjemalec /ecowitt-current mora biti v seznamu in vsebovati zarezo.
4. Javne datoteke (stran, JSON, zgodovina) ne vsebujejo `indoor`.

Zaženi:  python3 tools/test_privacy.py
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FAILS = []
CHECKS = 0
MARKERS = ["23.47", "47.3", "24.11", "11.23"]  # vrednosti notranjih senzorjev v lažnem odgovoru


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append((name, detail))
        print(f"  ✗ {name}  {detail}"[:500])


def leaks(text):
    low = text.lower()
    found = ["ključ `indoor`"] if "indoor" in low else []
    found += [f"vrednost {m}" for m in MARKERS if m in text]
    return found


def section(title):
    print(f"\n{title}")


def test_worker():
    section("worker.js — javne končne točke z lažnim Ecowittom in Varpoljem")
    p = subprocess.run(["node", os.path.join(HERE, "_privacy_worker.mjs")], capture_output=True, text=True,
                       cwd=ROOT, timeout=120)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        check(False, "worker se ne zažene", (p.stdout + p.stderr)[:400])
        return
    for path, r in out.items():
        check(r["status"] == 200, f"worker {path}: odgovor", f"status={r['status']} {r['body'][:120]}")
        check(not leaks(r["body"]), f"worker {path}: notranje meritve", ", ".join(leaks(r["body"])))
    # lažni odgovor mora res vsebovati zunanje podatke, sicer test nič ne dokazuje
    check('"12.3"' in out["/ecowitt-current"]["body"], "worker /ecowitt-current: zunanja temperatura je prisotna")
    check("11.9" in out["/varpolje-current"]["body"], "worker /varpolje-current: zunanja temperatura je prisotna")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FAKE = {"code": 0, "data": {
    "outdoor": {"temperature": {"value": "12.3"}, "humidity": {"value": "80"}},
    "indoor": {"temperature": {"value": "23.47"}, "humidity": {"value": "47.3"},
               "feels_like": {"value": "24.11"}, "dew_point": {"value": "11.23"}},
    "wind": {"wind_speed": {"value": "2"}}}}


def test_python_clients():
    section("Python odjemalci — fetch_current() ob odgovoru z blokom `indoor`")
    clients = [("tools/generate_daily_post.py", "daily_tools"), ("generate_daily_post.py", "daily_root"),
               ("tools/generate_story_card.py", "story"), ("tools/calculate_frost_risk.py", "frost")]
    for path, name in clients:
        try:
            mod = _load(path, name)
        except Exception as e:  # noqa: BLE001
            check(False, f"{path}: uvoz", repr(e))
            continue
        mod.fetch_json = lambda *a, **k: json.loads(json.dumps(FAKE))
        try:
            res = mod.fetch_current()
        except Exception as e:  # noqa: BLE001
            check(False, f"{path}: fetch_current()", repr(e))
            continue
        text = json.dumps(res, ensure_ascii=False)
        check(not leaks(text), f"{path}: fetch_current() ne vrne notranjih meritev", ", ".join(leaks(text)))
        check("12.3" in text, f"{path}: zunanja temperatura je ostala", text[:120])


# Odjemalci /ecowitt-current. Vsak NOV mora biti tu in imeti zarezo (ali brati samo zunanje).
KNOWN_CLIENTS = {
    "worker.js": "vir (zareže delete ewData.data.indoor)",
    "generate_daily_post.py": "zareza",
    "tools/generate_daily_post.py": "zareza",
    "tools/generate_story_card.py": "zareza",
    "tools/calculate_frost_risk.py": "zareza",
    "tools/log_valley_duel.py": "bere samo outdoor.temperature",
}


def test_new_clients():
    section("Novi odjemalci /ecowitt-current")
    files = subprocess.run(["git", "ls-files", "*.py", "*.js", "*.mjs", "*.yml", "*.sh"], capture_output=True,
                           text=True, cwd=ROOT).stdout.split()
    found = []
    for f in files:
        if f.endswith(".min.js") or f.startswith(("node_modules/", "tools/test_")) or "/_privacy" in f:
            continue
        try:
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                if "ecowitt-current" in fh.read():
                    found.append(f)
        except OSError:
            continue
    for f in found:
        check(f in KNOWN_CLIENTS, f"nov odjemalec /ecowitt-current: {f}",
              "zareži blok `indoor` (data.pop('indoor', None)) in ga dodaj v KNOWN_CLIENTS v tools/test_privacy.py "
              "ter v test_python_clients(), če ima fetch_current()")
    for f in KNOWN_CLIENTS:
        check(f in found, f"KNOWN_CLIENTS: {f} ne kliče več /ecowitt-current", "odstrani iz seznama")


def test_public_files():
    section("Javne datoteke ne omenjajo `indoor`")
    must_be_clean = ["app.js", "index.html", "style.css", "tools/inject_current_weather.py", "history.json",
                     "blog.json", "napoved-modela.json", "forecast_verification.json", "meteogasilec/index.json",
                     "og/story/latest.json", "llms.txt", "manifest.json", "sw.js"]
    for f in must_be_clean:
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        check("indoor" not in text.lower(), f"{f}: ne vsebuje `indoor`",
              f"{len(re.findall('indoor', text, re.I))} omemb")


def main():
    for t in (test_worker, test_python_clients, test_new_clients, test_public_files):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILS.append((t.__name__, repr(e)))
            print(f"  ✗ izjema: {e!r}")
    print(f"\n{CHECKS} preverjanj, {len(FAILS)} kršitev")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
