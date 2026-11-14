#!/usr/bin/env python3
"""Preizkus ponovitev pri klicu Open-Meteo v inject_forecast.py (14. 11. 2026): prehodna napaka ne sme pustiti
krajevnih strani na rezervnem besedilu; po izčrpanih poskusih vrne None (stara napoved ostane)."""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject_forecast as IF  # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"✗ {name} {detail}")


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self, *a):
        return b'{"hourly":{},"daily":{}}'


IF.FETCH_RETRY_WAITS_S = (0, 0, 0)
real = urllib.request.urlopen
try:
    for fails_before_ok, expect_ok in ((0, True), (2, True), (3, False)):
        n = [0]

        def fake(req, timeout=0, _f=fails_before_ok, _n=n):
            _n[0] += 1
            if _n[0] <= _f:
                raise OSError("handshake timed out")
            return _Resp()

        urllib.request.urlopen = fake
        res = IF.fetch_open_meteo(46.3, 14.9)
        check(f"{fails_before_ok} neuspehov → {'podatek' if expect_ok else 'None'}", (res is not None) == expect_ok)
        check(f"{fails_before_ok} neuspehov: število klicev", n[0] == min(fails_before_ok + 1, 3), str(n[0]))
finally:
    urllib.request.urlopen = real

check("premor med kraji je nastavljen", IF.INTER_TOWN_PAUSE_S > 0)
check("koordinate Logarske v TOWNS", any(t[0] == "vreme-logarska-dolina" for t in IF.TOWNS))
print(f"{ok} preverjanj, {fail} napak")
sys.exit(1 if fail else 0)
