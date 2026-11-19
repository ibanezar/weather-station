#!/usr/bin/env python3
"""tools/test_first_frost.py — prva zmrzal jeseni (seo_smart_routine.detect_events, dogodek `prva-zmrzal`).

19. 11. 2026 je bilo ugotovljeno, da dogodek ni nastal NIKOLI: pogoj »prej ni bilo zmrzali« je štel vse zmrzali od 1. januarja, zimska
zmrzal istega leta pa je bila vedno ob strani. Zdaj šteje samo zmrzal julija ali avgusta. Preverja tudi okno iskanja (30 dni),
začetek sezone 1. september in prag (tempLow <= 0). Ta dogodek je resnica ugibalnika zmrzali (tools/zmrzal_ugibalnik_resolve.py).
Zaženi: python3 tools/test_first_frost.py"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_smart_routine as m  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


def hist(start, end, low=5.0, **override):
    """Dnevi od start do end (vključno) z isto tempLow; override = {datum: tempLow}."""
    d, out = start, {}
    while d <= end:
        out[d.isoformat()] = {"tempHigh": low + 8, "tempLow": override.get(d.isoformat(), low), "precipTotal": 0.0}
        d += datetime.timedelta(days=1)
    return out


def frost_events(h, today, look=30):
    m.TODAY = today
    return [e for e in m.detect_events(h, lookback_days=look) if e["type"] == "prva-zmrzal"]


T = datetime.date(2026, 11, 19)
base = dict(start=datetime.date(2026, 1, 1), end=T)
# zimska zmrzal (januar, februar) + prva jesenska 23. 10.: dogodek MORA nastati (prej ga zimske zmrzali niso pustile)
h = hist(**base, **{"2026-01-10": -6.0, "2026-02-03": -2.0, "2026-10-23": -0.4, "2026-11-05": -3.0})
ev = frost_events(h, T)
check(len(ev) == 1, "zimska zmrzal istega leta ne prepreči dogodka")
check(ev and ev[0]["date"] == "2026-10-23" and ev[0]["slug"] == "prva-zmrzal-2026" and ev[0]["value"] == -0.4, "datum, slug in vrednost prve zmrzali")
# prag: 0,0 je zmrzal (<= 0), 0,1 ni
T2 = datetime.date(2026, 10, 20)
ev = frost_events(hist(datetime.date(2026, 1, 1), T2, **{"2026-10-10": 0.1, "2026-10-12": 0.0}), T2)
check(ev and ev[0]["date"] == "2026-10-12", "0,0 °C je zmrzal, 0,1 °C ni")
# zmrzal pred 1. septembrom ni »prva jesenska«: dogodek ne nastane, če je bila zmrzal poleti
check(frost_events(hist(**base, **{"2026-08-30": -1.0, "2026-10-23": -2.0}), T) == [], "zmrzal avgusta: jesenska prva ni prva zmrzal sezone")
# zmrzal junija ne šteje kot poletna zmrzal (pozna spomladanska je drug dogodek): jesenska prva nastane
check(len(frost_events(hist(**base, **{"2026-06-02": -1.0, "2026-10-23": -2.0}), T)) == 1, "junijska zmrzal ne prepreči jesenske")
# začetek sezone 1. september: zmrzal 31. 8. ni v sezoni, naslednja je prva
T3 = datetime.date(2026, 10, 1)
ev = frost_events(hist(datetime.date(2026, 1, 1), T3, **{"2026-08-31": 3.0, "2026-09-20": -1.0}), T3)
check(ev and ev[0]["date"] == "2026-09-20", "zmrzal 20. 9. je prva")
check(frost_events(hist(datetime.date(2026, 1, 1), T3, **{"2026-08-31": -1.0}), T3) == [], "zmrzal 31. 8. ni v sezoni (od 1. septembra)")
# okno iskanja: prva zmrzal pred več kot 30 dnevi (zdaj 19. 11., prva 10. 10.) dogodka ne ustvari
check(frost_events(hist(**base, **{"2026-10-10": -1.0, "2026-11-05": -2.0}), T) == [], "prva zmrzal starejša od 30 dni: ni dogodka")
check(len(frost_events(hist(**base, **{"2026-10-20": -1.0}), T)) == 1, "prva zmrzal v oknu 30 dni")
# brez zmrzali ni dogodka; pred 1. septembrom ga ni
check(frost_events(hist(**base), T) == [], "brez zmrzali ni dogodka")
check(frost_events(hist(datetime.date(2026, 1, 1), datetime.date(2026, 8, 20), **{"2026-08-10": -1.0}), datetime.date(2026, 8, 20)) == [], "pred 1. septembrom ni jesenskega dogodka")

print("OK" if not fails else f"{fails} napak")
sys.exit(1 if fails else 0)
