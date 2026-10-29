#!/usr/bin/env python3
"""tools/test_gates_daily.py — časovna vrata brez lastnega testa: frost_gate, igra_gate, digest_gate, update_history_gate.

Dopolnilo k test_gates.py (karte in zgodba). Ista motivacija: gate, ki tiho zavrne vsak tek, je »uspešen« workflow brez dela
(nevihtna karta 31. 8. – 1. 10. 2026). Zaklene okna, stanje po terminu/dnevu, --force in sezono pozebe.
Zaženi: python3 tools/test_gates_daily.py"""
import datetime
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import digest_gate  # noqa: E402
import frost_gate  # noqa: E402
import igra_gate  # noqa: E402
import update_history_gate  # noqa: E402

FAILS = []
CHECKS = 0


def check(ok, name):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print("  ✗", name)


class FakeDT(datetime.datetime):
    fixed = None

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


def run(mod, args, when, state=None, state_attr="STATE"):
    """Požene mod.main() ob lokalnem času `when` (naivni datetime v pasu mod.TZ); vrne (proceed|None, state_po_zagonu)."""
    FakeDT.fixed = FakeDT(when.year, when.month, when.day, when.hour, when.minute, tzinfo=mod.TZ)
    path = os.path.join(tempfile.mkdtemp(), "state.json")
    setattr(mod, state_attr, path)
    if state is not None:
        json.dump(state, open(path, "w", encoding="utf-8"))
    out = os.path.join(tempfile.mkdtemp(), "out")
    os.environ["GITHUB_OUTPUT"] = out
    saved_dt, saved_argv = mod.datetime, sys.argv
    mod.datetime = type("D", (), {"datetime": FakeDT, "date": datetime.date, "timedelta": datetime.timedelta})
    sys.argv = ["gate"] + args
    try:
        with redirect_stdout(io.StringIO()):
            mod.main()
    finally:
        mod.datetime, sys.argv = saved_dt, saved_argv
    proceed = None
    if os.path.exists(out):
        proceed = dict(line.split("=") for line in open(out).read().split()).get("proceed") == "true"
    after = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return proceed, after


D = lambda m, d, h, mi=0: datetime.datetime(2026, m, d, h, mi)  # noqa: E731

# ── frost_gate: sezona marec–maj, dva termina, stanje po terminu ──
check(run(frost_gate, ["check", "afternoon"], D(4, 10, 15))[0] is True, "frost: popoldanski termin v oknu 14–17")
check(run(frost_gate, ["check", "afternoon"], D(4, 10, 13, 59))[0] is False, "frost: pred 14. uro ne")
check(run(frost_gate, ["check", "afternoon"], D(4, 10, 17))[0] is False, "frost: od 17. ure ne")
check(run(frost_gate, ["check", "evening"], D(4, 10, 19))[0] is True, "frost: večerni termin ob 19.")
check(run(frost_gate, ["check", "evening"], D(4, 10, 22))[0] is False, "frost: večerni termin od 22. ne")
check(run(frost_gate, ["check", "evening"], D(7, 10, 20))[0] is False, "frost: julij je izven sezone")
check(run(frost_gate, ["check", "evening", "--force"], D(7, 10, 20))[0] is False, "frost: izven sezone tudi --force ne")
check(run(frost_gate, ["check", "evening", "--force"], D(4, 10, 12))[0] is True, "frost: --force v sezoni preskoči okno")
check(run(frost_gate, ["check", "afternoon"], D(4, 10, 15), {"afternoon": {"lastRun": "2026-04-10"}})[0] is False, "frost: termin že opravljen danes")
check(run(frost_gate, ["check", "evening"], D(4, 10, 20), {"afternoon": {"lastRun": "2026-04-10"}})[0] is True, "frost: popoldanski tek ne blokira večernega")
check(run(frost_gate, ["check", "afternoon"], D(4, 10, 15), {"afternoon": {"lastRun": "2026-04-09"}})[0] is True, "frost: včerajšnji tek ne blokira")
check(run(frost_gate, ["mark", "evening"], D(4, 10, 20))[1].get("evening", {}).get("lastRun") == "2026-04-10", "frost: mark zapiše termin za današnji dan")
check("afternoon" not in run(frost_gate, ["mark", "evening"], D(4, 10, 20))[1], "frost: mark večernega ne zapiše popoldanskega")

# ── igra_gate: okno 5–12, enkrat na dan ──
check(run(igra_gate, ["check"], D(10, 29, 4, 59))[0] is False, "igra: pred 5. uro ne")
check(run(igra_gate, ["check"], D(10, 29, 5))[0] is True, "igra: od 5. ure da")
check(run(igra_gate, ["check"], D(10, 29, 11, 59))[0] is True, "igra: 11.59 še da")
check(run(igra_gate, ["check"], D(10, 29, 12))[0] is False, "igra: od 12. ure ne (isti dan, isti nivo)")
check(run(igra_gate, ["check"], D(10, 29, 8), {"lastRun": "2026-10-29"})[0] is False, "igra: nivo že sestavljen danes")
check(run(igra_gate, ["check"], D(10, 29, 8), {"lastRun": "2026-10-28"})[0] is True, "igra: včerajšnji nivo ne blokira")
check(run(igra_gate, ["check", "--force"], D(10, 29, 15), {"lastRun": "2026-10-29"})[0] is True, "igra: --force preskoči vse")
check(run(igra_gate, ["mark"], D(10, 29, 8))[1].get("lastRun") == "2026-10-29", "igra: mark zapiše današnji dan")

# ── digest_gate: okno 7–18, enkrat na dan ──
check(run(digest_gate, ["check"], D(10, 29, 6, 59))[0] is False, "digest: pred 7. uro ne")
check(run(digest_gate, ["check"], D(10, 29, 7))[0] is True, "digest: od 7. ure da")
check(run(digest_gate, ["check"], D(10, 29, 17, 59))[0] is True, "digest: 17.59 še da (cron zamuja ure)")
check(run(digest_gate, ["check"], D(10, 29, 18))[0] is False, "digest: od 18. ure ne")
check(run(digest_gate, ["check"], D(10, 29, 9), {"lastSent": "2026-10-29"})[0] is False, "digest: že poslan danes")
check(run(digest_gate, ["check"], D(10, 29, 9), {"lastSent": "2026-10-28"})[0] is True, "digest: včerajšnji ne blokira")
check(run(digest_gate, ["mark"], D(10, 29, 9))[1].get("lastSent") == "2026-10-29", "digest: mark zapiše lastSent")

# ── update_history_gate: stanje je history.json ──
def hist_gate(hist, force=False, raw=None):
    path = os.path.join(tempfile.mkdtemp(), "history.json")
    if raw is not None:
        open(path, "w").write(raw)
    elif hist is not None:
        json.dump(hist, open(path, "w"))
    update_history_gate.HIST = path
    FakeDT.fixed = FakeDT(2026, 10, 29, 9, 0, tzinfo=update_history_gate.TZ)
    out = os.path.join(tempfile.mkdtemp(), "out")
    os.environ["GITHUB_OUTPUT"] = out
    saved, argv = update_history_gate.datetime, sys.argv
    update_history_gate.datetime = FakeDT
    sys.argv = ["gate"] + (["--force"] if force else [])
    try:
        with redirect_stdout(io.StringIO()):
            update_history_gate.main()
    finally:
        update_history_gate.datetime, sys.argv = saved, argv
    return dict(line.split("=") for line in open(out).read().split())["proceed"] == "true"


check(hist_gate({"2026-10-28": {"src": "station"}}) is False, "history: včeraj že z meritvijo postaje -> ne")
check(hist_gate({"2026-10-28": {"src": "era5"}}) is True, "history: včeraj samo ERA5 -> da (postaja je morda spet dosegljiva)")
check(hist_gate({"2026-10-27": {"src": "station"}}) is True, "history: včerajšnjega dne ni -> da")
check(hist_gate({"2026-10-28": {"src": "station"}}, force=True) is True, "history: --force vedno da")
check(hist_gate(None, raw="{ni json") is True, "history: neberljiva datoteka -> da (raje poskusi kot molči)")
check(hist_gate({"2026-10-28": {}}) is True, "history: včeraj brez polja src -> da")

print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
