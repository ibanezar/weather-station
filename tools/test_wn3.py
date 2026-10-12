#!/usr/bin/env python3
"""tools/test_wn3.py — zajem WeatherNext 3 (fetch_wn3.py), brez omrežja in poverilnic.

Preverja čisto logiko: lokalni dan (tudi 23/25 ur ob prehodu ure), izbiro
inicializacije in datuma objave, horizont, ekstreme, najbližjo celico, iskanje
mape inicializacije, načrt zajema, ponovne poskuse in dodajanje v arhiv."""
import datetime, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_wn3 as W  # noqa: E402

D, UTC = datetime.date, datetime.timezone.utc
fails = []


def check(ok, name):
    if not ok:
        fails.append(name)
        print("  ✗", name)


def utc(y, m, d, h=0):
    return datetime.datetime(y, m, d, h, tzinfo=UTC)


# ── lokalni dan ──────────────────────────────────────────────────────────────
zima = W.local_day_valid_times(D(2026, 1, 2))
check(len(zima) == 24 and zima[0] == utc(2026, 1, 1, 23) and zima[-1] == utc(2026, 1, 2, 22),
      "lokalni dan pozimi (CET): 23:00 UTC prejšnji dan .. 22:00 UTC")
poletje = W.local_day_valid_times(D(2026, 7, 1))
check(len(poletje) == 24 and poletje[0] == utc(2026, 6, 30, 22), "lokalni dan poleti (CEST): 22:00 UTC")
check(len(W.local_day_valid_times(D(2026, 3, 29))) == 23, "prehod na poletni čas: 23 ur")
check(len(W.local_day_valid_times(D(2026, 10, 25))) == 25, "prehod na zimski čas: 25 ur")

# ── objava in inicializacija ─────────────────────────────────────────────────
check(W.issued_date(utc(2026, 10, 11, 18)) == D(2026, 10, 12), "18 UTC D-1 je dostopna D")
check(W.issued_date(utc(2026, 10, 12, 0)) == D(2026, 10, 12), "00 UTC D je dostopna D")
check(W.issued_date(utc(2026, 10, 12, 12)) == D(2026, 10, 12), "12 UTC D je dostopna D")
check(W.issued_date(utc(2026, 10, 12, 18)) == D(2026, 10, 13), "18 UTC D je dostopna D+1")

# ── indeksi za dan, horizont ─────────────────────────────────────────────────
init = utc(2026, 1, 1, 18)


def axis(init, n):
    """Os lead_time: i-ti indeks je init + (i+1) h."""
    return {init + datetime.timedelta(hours=i + 1): i for i in range(n)}


idx = W.indices_for_day(init, D(2026, 1, 3), axis(init, 360))
check(idx is not None and len(idx) == 24, "dan v horizontu: 24 indeksov")
# 3. 1. lokalno = 2. 1. 23:00 UTC .. 3. 1. 22:00 UTC; lead = 29..52 h od 1. 1. 18 UTC -> indeksi 28..51
check(idx == list(range(28, 52)), f"indeksi lead-1: {idx[:2] if idx else idx}")
check(W.indices_for_day(init, D(2026, 1, 3), axis(init, 40)) is None, "manjka ura -> None")
check(W.indices_for_day(init, D(2026, 1, 2), axis(init, 360)) is not None, "lead 1 d (2. 1.) v horizontu")
check(W.indices_for_day(init, D(2026, 1, 1), axis(init, 360)) is None, "dan, ki se začne pred inicializacijo -> None")
# os je dovolj dolga, da pade samo horizont (361+ ur), ne manjkajoča ura
# 15. 1. sega do 340 h, 16. 1. do 364 h (init 1. 1. 18 UTC)
check(W.indices_for_day(init, D(2026, 1, 16), axis(init, 400)) is None, "364 h -> None (horizont, ne os)")
check(W.indices_for_day(init, D(2026, 1, 15), axis(init, 400)) is not None, "340 h je še v horizontu")
# trenutek = inicializacija (lead 0) ni napoved: prva ura dneva sovpada z init
z0 = utc(2026, 1, 1, 23)
os0 = {z0 + datetime.timedelta(hours=i): i for i in range(0, 60)}
check(W.indices_for_day(z0, D(2026, 1, 2), os0) is None, "lead 0 h -> None")
check(W.INIT_HOUR == 18, "privzeta inicializacija 18 UTC je namerna (glej docstring fetch_wn3.py)")

# ── ekstremi ─────────────────────────────────────────────────────────────────
check(W.daily_extrema([273.15 + t for t in (-5.84, 3.26, -8.14, 5.64)]) == (5.6, -8.1), "Tmax/Tmin iz K")
check(W.daily_extrema([280.0, float("nan")]) is None, "NaN -> None")
check(W.daily_extrema([280.0, None]) is None, "None -> None")
check(W.daily_extrema([]) is None, "prazno -> None")

# ── najbližja celica ─────────────────────────────────────────────────────────
lats_asc = [round(-90 + 0.05 * i, 2) for i in range(3601)]
check(abs(lats_asc[W.nearest_index(lats_asc, 46.325779)] - 46.35) < 1e-6, "najbližja širina (naraščajoča)")
check(abs(lats_asc[W.nearest_index(lats_asc, 46.30)] - 46.30) < 1e-6, "točna širina")
check(W.nearest_index(lats_asc[::-1], 46.325779) == len(lats_asc) - 1 - W.nearest_index(lats_asc, 46.325779),
      "padajoča os")
lons = [round(0.05 * i, 2) for i in range(7200)]
check(abs(lons[W.nearest_index(lons, W.lon_to_grid(14.921137))] - 14.90) < 1e-6, "najbližja dolžina")
check(W.lon_to_grid(-10) == 350 and W.lon_to_grid(14.9) == 14.9, "dolžine 0..360")

# ── mapa inicializacije ──────────────────────────────────────────────────────
names = ["20260101_00hr_01_preds", "20260101_18hr_01_preds", "20260101_18hr_02_preds/",
         "20260102_18hr_01_preds", "20260101_18hr_xx_preds", "weathernext.pdf"]
check(W.find_prefix(names, utc(2026, 1, 1, 18)) == "20260101_18hr_02_preds", "najvišja različica")
check(W.find_prefix(names, utc(2026, 1, 1, 0)) == "20260101_00hr_01_preds", "00 UTC")
check(W.find_prefix(names, utc(2026, 1, 1, 12)) is None, "manjkajoča inicializacija -> None")
check(W.find_prefix(["20260101_18hr_01_preds"], utc(2026, 1, 1, 18)) == "20260101_18hr_01_preds", "ena različica")

# ── načrt zajema ─────────────────────────────────────────────────────────────
now = utc(2026, 10, 12, 10)
p = W.plan(now, D(2026, 10, 10), D(2026, 10, 12), [1], 18, set())
check([(i.day, v.isoformat(), n) for i, v, n in p] ==
      [(10, "2026-10-12", 1), (11, "2026-10-13", 1)], f"načrt: {[(i.day, v.isoformat()) for i, v, n in p]}")
# 18 UTC 12. 10. je objavljena šele ~01:00 UTC 13. 10. -> ni v načrtu
check(all(i.day != 12 for i, v, n in p), "še neobjavljena inicializacija ni v načrtu")
p2 = W.plan(now, D(2026, 10, 10), D(2026, 10, 12), [1], 18, {("2026-10-10T18", "2026-10-12")})
check([i.day for i, v, n in p2] == [11], "že zajeto se preskoči")
p3 = W.plan(now, D(2026, 10, 11), D(2026, 10, 11), [1, 2, 3], 18, set())
check([n for i, v, n in p3] == [1, 2, 3] and [v.day for i, v, n in p3] == [13, 14, 15], "več vodilnih dni")
p4 = W.plan(utc(2026, 10, 12, 6, ), D(2026, 10, 12), D(2026, 10, 12), [1], 0, set())
check(p4 == [], "00 UTC ob 6:00 še ni objavljena (objava ~6:50)")
p5 = W.plan(utc(2026, 10, 12, 7), D(2026, 10, 12), D(2026, 10, 12), [1], 0, set())
check(len(p5) == 1 and p5[0][1] == D(2026, 10, 13), "00 UTC ob 7:00 je objavljena, lead 1 = jutri")

# ── cela vrstica z lažnim bralnikom ──────────────────────────────────────────
init = utc(2026, 1, 1, 18)
ax = axis(init, 360)
temps = {}  # indeks -> K
for t, i in ax.items():
    lokalno = t.astimezone(W.TZ)
    temps[i] = 273.15 + (lokalno.hour - 5) * 0.5 - 8   # Tmin ob 0:00 = -10.5, Tmax ob 23:00 = 1.0


def read_many(indices):
    return [temps[i] for i in indices]


row = W.build_row(init, D(2026, 1, 3), 1, ax, read_many, (46.35, 14.9))
check(row is not None and row["tmax_c"] == 1.0 and row["tmin_c"] == -10.5,
      f"vrstica ekstremi: {row and (row['tmax_c'], row['tmin_c'])}")
check(row["lead_days"] == 1 and row["issued_at"] == "2026-01-02" and row["init_at"] == "2026-01-01T18"
      and row["valid_at"] == "2026-01-03" and row["model"] == "wn3", f"vrstica polja: {row}")
check(row["cell_lat"] == 46.35 and row["cell_lon"] == 14.9, "celica v vrstici")
check(W.build_row(init, D(2026, 1, 3), 1, axis(init, 40), read_many, (0, 0)) is None, "vrstica brez ur -> None")
check(W.build_row(init, D(2026, 1, 3), 1, ax, lambda ix: [280.0] * 23 + [float("nan")], (0, 0)) is None,
      "vrstica z NaN -> None")

# ── ponovni poskusi ──────────────────────────────────────────────────────────
calls = []
pavze = []


def flaky():
    calls.append(1)
    if len(calls) < 3:
        raise TimeoutError("zatika")
    return 42


check(W.with_retries(flaky, tries=4, sleep=pavze.append) == 42 and len(calls) == 3 and pavze == [1, 2],
      f"ponovni poskusi: {len(calls)} klicev, pavze {pavze}")
try:
    W.with_retries(lambda: (_ for _ in ()).throw(OSError("mrtvo")), tries=2, sleep=lambda s: None)
    check(False, "po zadnjem poskusu vrže napako")
except OSError:
    pass

# ── arhiv: samo dodaja, ne prepisuje ─────────────────────────────────────────
with tempfile.TemporaryDirectory() as tmp:
    pot = os.path.join(tmp, "data", "wn3-archive.csv")
    check(W.append_rows([row], pot) == 1, "prvi zapis")
    check(W.append_rows([row], pot) == 0, "dvojnik se ne doda")
    spremenjen = dict(row, tmax_c=99.0)
    check(W.append_rows([spremenjen], pot) == 0, "obstoječa vrstica se ne prepiše")
    drug = dict(row, valid_at="2026-01-04", init_at="2026-01-02T18")
    check(W.append_rows([drug], pot) == 1, "nova vrstica se doda")
    vrstice = open(pot, encoding="utf-8").read().splitlines()
    check(vrstice[0].startswith("model,lead_days,valid_at") and len(vrstice) == 3 and "99.0" not in "".join(vrstice),
          f"datoteka: {len(vrstice)} vrstic, glava ena sama")
    check(W.load_existing(pot) == {("2026-01-01T18", "2026-01-03"), ("2026-01-02T18", "2026-01-04")}, "load_existing")
    check(W.append_rows([], pot) == 0, "prazen seznam")

print("OK" if not fails else f"{len(fails)} FAIL")
sys.exit(1 if fails else 0)
