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


# Nevihtna karta: okno 6–8 (rok 7:00). Padavinska: 7–11, ker podatek ARSO (rr24h) obstaja
# šele po jutranji meritvi ob 06:00 UTC — okno pred njo je vsak tek obsodilo na napako.
print("\nprecip_map_gate (okno po jutranji meritvi)")
m = importlib.import_module("precip_map_gate")
check(run_gate(m, 6) == (False, False), "6:30: pred meritvijo ARSO — nič")
check(run_gate(m, 8) == (True, False), "8:30 (posnetek ob 06:30 UTC poleti): v oknu, objava")
check(run_gate(m, 10) == (True, False), "10:30: še v oknu")
check(run_gate(m, 11) == (True, True), "11:30: pozno — sestavi brez objave")
check(run_gate(m, 20) == (False, False), "20:30: preveč pozno, nič")
check(run_gate(m, 9, last_run="2026-10-01") == (False, False), "karta za danes že narejena: nič")

for name in ("storm_map_gate",):
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

# Večerna kartica (zmrzal/hladno jutro dan prej, 13. 10. 2026): okno 17–23, stanje po
# datumu JUTRIŠNJEGA jutra; jutranja zgodba jutranjih tem opoldne ne sme več objaviti.
print("\nstory_gate --evening")
sg = importlib.import_module("story_gate")


def run_evening(hour, last_for=None, force=False):
    FakeDT.fixed = FakeDT(2026, 10, 1, hour, 30, tzinfo=sg.TZ)
    sg.STATE_EVENING = os.path.join(tempfile.mkdtemp(), "ev.json")
    if last_for:
        sg.save_state({"lastFor": last_for}, sg.STATE_EVENING)
    out = os.path.join(tempfile.mkdtemp(), "out")
    os.environ["GITHUB_OUTPUT"] = out
    fake = type("D", (), {"datetime": FakeDT, "date": datetime.date, "timedelta": datetime.timedelta})
    saved_dt, saved_argv = sg.datetime, sys.argv
    sg.datetime = fake
    sys.argv = ["gate", "check", "--evening"] + (["--force"] if force else [])
    try:
        with redirect_stdout(io.StringIO()):
            sg.main()
    finally:
        sg.datetime, sys.argv = saved_dt, saved_argv
    return dict(line.split("=") for line in open(out).read().split())["proceed"] == "true"


check(not run_evening(14), "14:30: prezgodaj za večerno kartico")
check(run_evening(17), "17:30: v oknu")
check(run_evening(22), "22:30 (zamujen cron): še v oknu")
check(not run_evening(23), "23:30: prepozno")
check(not run_evening(18, last_for="2026-10-02"), "kartica za jutri že objavljena: nič")
check(run_evening(18, last_for="2026-10-01"), "kartica za DANES ne blokira kartice za jutri")
check(run_evening(3, force=True), "--force ni omejen z uro")
sg.STATE_EVENING = os.path.join(tempfile.mkdtemp(), "ev.json")
sg.save_state({"lastFor": "2026-10-02"}, sg.STATE_EVENING)
check(sg.evening_posted_for("2026-10-02") and not sg.evening_posted_for("2026-10-03"),
      "evening_posted_for po datumu")

print("\njutranje teme zgodbe")
sc = importlib.import_module("generate_story_card")
mk = lambda h: datetime.datetime(2026, 10, 1, h, 0)
check(sc.morning_topics_allowed(mk(6), False), "6:00: jutranje teme dovoljene")
check(not sc.morning_topics_allowed(mk(13), False), "13:00: jutro je že mimo")
_c = {"now": mk(11), "hist_yesterday": {"tempHigh": 20.0}, "tmax": 12.0}
check(sc.t_vs_yesterday(_c) is None, "11:00: VS_YESTERDAY po 7:00 ne gre ven")
check(not sc.morning_topics_allowed(mk(6), True), "večerna kartica je že šla ven: ne ponavljaj")

print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)

print("\ndnevna zgodba: samo do 7:00")
check(sg.WINDOW_END == 7, "okno dnevne zgodbe se konča ob 7:00")
