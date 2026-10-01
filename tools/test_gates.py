#!/usr/bin/env python3
"""tools/test_gates.py — preizkus časovnih vrat (gate) za dnevne karte.

Gate je od 31. 8. (nevihtna) oz. 11. 9. (padavinska karta) tiho zavračal vsak tek,
ker GitHubov cron zamuja 5-7 ur, okno pa je bilo 6:00-8:00 — workflow je »uspel«
brez dela in karte ni bilo en mesec. Ta test zaklene vedenje: v oknu = objava,
po oknu do LATE_END = sestavi brez objave (late), čez to ali ob že narejeni karti =
nič. Zaženi:  python3 tools/test_gates.py
"""
import datetime
import importlib
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CHECKS = 0
FAILS = []


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


class FakeDT(datetime.datetime):
    fixed = None

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


def run_gate(mod, hour, last_run=None, force=False):
    tz = mod.TZ
    FakeDT.fixed = FakeDT(2026, 10, 1, hour, 30, tzinfo=tz)
    state = os.path.join(tempfile.mkdtemp(), "state.json")
    mod.STATE = state
    if last_run:
        mod.save_state({"lastRun": last_run})
    out = os.path.join(tempfile.mkdtemp(), "out")
    os.environ["GITHUB_OUTPUT"] = out
    fake = type("D", (), {"datetime": FakeDT, "date": datetime.date, "timedelta": datetime.timedelta})
    saved_dt, saved_argv = mod.datetime, sys.argv
    mod.datetime = fake
    sys.argv = ["gate", "check"] + (["--force"] if force else [])
    try:
        with redirect_stdout(io.StringIO()):
            mod.main()
    finally:
        mod.datetime, sys.argv = saved_dt, saved_argv
    kv = dict(line.split("=") for line in open(out).read().split())
    return kv["proceed"] == "true", kv["late"] == "true"


for name in ("storm_map_gate", "precip_map_gate"):
    print(f"\n{name}")
    m = importlib.import_module(name)
    check(run_gate(m, 5) == (False, False), "pred oknom: nič")
    check(run_gate(m, 6) == (True, False), "6:30: v oknu, objava")
    check(run_gate(m, 7) == (True, False), "7:30: v oknu, objava")
    check(run_gate(m, 8) == (True, True), "8:30: pozno — sestavi brez objave")
    check(run_gate(m, 13) == (True, True), "13:30 (tipičen zamujen cron): sestavi brez objave")
    check(run_gate(m, 19) == (True, True), "19:30: še pozno")
    check(run_gate(m, 20) == (False, False), "20:30: preveč pozno, nič")
    check(run_gate(m, 7, last_run="2026-10-01") == (False, False), "karta za danes že narejena: nič")
    check(run_gate(m, 13, last_run="2026-10-01") == (False, False), "pozni tek ne podvoji že narejene karte")
    check(run_gate(m, 7, last_run="2026-09-30") == (True, False), "včerajšnja karta ne blokira današnje")
    check(run_gate(m, 3, force=True) == (True, False), "--force ni pozno in ni omejeno z uro")

print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
