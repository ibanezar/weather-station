#!/usr/bin/env python3
"""
tools/generate_stratosfera_page.py — /stratosfera/ (21. 10. 2026)

Polarni vrtinec in nenadna stratosferska segrevanja (SSW): zonalni veter na 10 hPa pri 60 °N in povprečna
temperatura polarne kape (60–90 °N) na 10 hPa, iz analiz in napovedi NOAA GFS (odprti podatki na AWS,
`noaa-gfs-bdp-pds`). Ideja po polarnivrtinec.si (»Stratosfera«, »SSW«); izračun in besedilo sta naša.

Kar stran je in ni:
- SPREMLJANJE IN NAPOVED IZ ENEGA MODELA (GFS, determinističen tek do +10 dni). Obrat zahodnika (u < 0) pozimi je
  kriterij za glavni SSW po WMO; učinek na pritalno vreme je statističen in zakasnjen za tedne, ne napoved vremena.
- Zgodovina se NABIRA: `data/stratosfera.json` hrani dnevne vrednosti (analiza 00 UTC), osnovni zagon pa jih nazaj
  napolni za zadnjih BACKFILL_DAYS dni iz arhiva GFS. `data/stratosfera-klima.json` (enkraten `--climatology`)
  hrani razpon let 2021–2025 po dnevih v letu, da je vrednost mogoče primerjati — to je KRATEK vzorec (5 let), ne
  uradna klimatologija, in tako tudi piše.
- Brez podatkov postaje; notranjih meritev tu ni.

Usage:
  python3 tools/generate_stratosfera_page.py                 # posodobi zgodovino + napoved, zapiši stran
  python3 tools/generate_stratosfera_page.py --climatology   # ENKRATNO: razpon let 2021–2025 (traja nekaj minut)
"""
import argparse
import datetime
import html as _html
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atmos_common as ac  # noqa: E402

GFS = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{ymd}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fff:03d}"
DATA_PATH = os.path.join(ac.ROOT, "data", "stratosfera.json")
CLIMA_PATH = os.path.join(ac.ROOT, "data", "stratosfera-klima.json")
REL = "/stratosfera/"
BACKFILL_DAYS = 75
FC_STEPS = list(range(0, 241, 24))
GREEN, PURPLE, AMBER = "#34d399", "#c084fc", "#fbbf24"

FAQ = [
    ("Kaj je polarni vrtinec?",
     "Širok ciklon hladnega zraka v stratosferi (od okoli 10 do 50 km) nad polarnim območjem, ki se jeseni okrepi in "
     "pozimi obkroža pol z zahodnim vetrom. Ko je močan, je hladen zrak »zaprt« nad Arktiko; ko se razmaje ali razdeli, "
     "se lahko del hladnega zraka prelije proti jugu."),
    ("Kaj je nenadno stratosfersko segrevanje (SSW)?",
     "Hitro segrevanje polarne stratosfere (za več deset stopinj v nekaj dneh), ki oslabi ali obrne zahodni veter. Po "
     "definiciji WMO je glavni SSW tisti, pri katerem se v zimskih mesecih zonalni veter na 10 hPa pri 60 °N obrne iz "
     "zahodnega v vzhodnega. Pomeni šibek polarni vrtinec, ne pa nujno mraza pri nas."),
    ("Ali SSW pomeni mrzlo zimo v Sloveniji?",
     "Ne nujno. Po številnih primerih sledi v enem do šestih tednih negativen AO in večja možnost prodorov hladnega "
     "zraka v srednji Evropi, a zveza ni zanesljiva: nekateri SSW na pritalno vreme ne vplivajo, v nekaterih "
     "zimah je hladno tudi brez njega. Stran zato ne napoveduje mraza, samo spremlja vrtinec."),
    ("Kaj prikazuje graf zonalnega vetra pri 60 °N?",
     "Povprečje zahodno-vzhodne komponente vetra vzdolž kroga 60 °N na višini 10 hPa (okoli 30 km). Pozitivno je "
     "zahodnik: vrtinec obstaja in je močan. Ko vrednost pade pod 0 pozimi, je izpolnjen kriterij za glavni SSW."),
    ("Od kod so podatki in kako sveži so?",
     "Iz modela NOAA GFS (odprti podatki): analiza ob 00 UTC za zgodovino in determinističen tek do +10 dni. En "
     "model je omejitev — pri SSW se napovedi različnih modelov pogosto razlikujejo za nekaj dni. Zgodovino "
     "stran sama hrani od prve objave; razpon prejšnjih let je kratek vzorec (zadnji štiri do pet zim)."),
]


# ── Prenos GFS (bajtna območja prek .idx) ────────────────────────────────────

def gfs_url(init, step):
    return GFS.format(ymd=init.strftime("%Y%m%d"), hh=f"{init.hour:02d}", fff=step)


def gfs_available(init, step):
    try:
        ac.http_get(gfs_url(init, step) + ".idx", tries=1, timeout=30)
        return True
    except Exception:  # noqa: BLE001
        return False


def idx_range(parts, var, level):
    """Iz razčlenjenega .idx (seznam polj po ':') vrne glavo Range za spremenljivko in nivo (mb), ali None."""
    for i, p in enumerate(parts):
        if len(p) > 4 and p[3] == var and p[4] == f"{level} mb":
            start = int(p[1])
            return f"bytes={start}-{int(parts[i + 1][1]) - 1}" if i + 1 < len(parts) else f"bytes={start}-"
    return None


def gfs_fields(init, step, wanted=(("UGRD", 10), ("TMP", 10))):
    """Prenese samo zahtevana polja GFS prek bajtnih območij v .idx. Vrne {(var, nivo): (lats, lons, vals)}."""
    url = gfs_url(init, step)
    parts = [ln.split(":") for ln in ac.http_get(url + ".idx", timeout=60).decode().splitlines()]
    out = {}
    for var, level in wanted:
        rng = idx_range(parts, var, level)
        if rng is None:
            continue
        blob = ac.http_get(url, headers={"Range": rng}, timeout=120)
        for _s, _l, _st, lats, lons, vals in ac.grib_messages(blob):
            out[(var, level)] = (lats, lons, vals)
    return out


def stats_from_fields(f):
    """Zonalni veter 10 hPa pri 60 °N (m/s) in povprečna temperatura polarne kape 60–90 °N (°C, uteženo s cos φ)."""
    import numpy as np
    lats, lons, u = f[("UGRD", 10)]
    j = int(np.argmin(np.abs(lats - 60.0)))
    u60 = float(np.mean(u[j]))
    res = {"u60": round(u60, 2)}
    if ("TMP", 10) in f:
        la, _lo, t = f[("TMP", 10)]
        sel = la >= 60.0
        w = np.cos(np.radians(la[sel]))
        res["t"] = round(float((t[sel].mean(axis=1) * w).sum() / w.sum()) - 273.15, 2)
    return res


def day_stats(day, with_temp=True):
    init = datetime.datetime(day.year, day.month, day.day, 0)
    wanted = (("UGRD", 10), ("TMP", 10)) if with_temp else (("UGRD", 10),)
    return stats_from_fields(gfs_fields(init, 0, wanted))


def latest_run(now=None):
    """Zadnji GFS tek, ki ima že vse korake do +240 h (sicer pred njim)."""
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    t = datetime.datetime(now.year, now.month, now.day, (now.hour // 6) * 6)
    for _ in range(6):
        if gfs_available(t, FC_STEPS[-1]):
            return t
        t -= datetime.timedelta(hours=6)
    return None


def fetch_forecast(init):
    def one(step):
        try:
            return step, stats_from_fields(gfs_fields(init, step))
        except Exception as e:  # noqa: BLE001
            print(f"  ! f{step:03d}: {e}", file=sys.stderr)
            return step, None
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = dict(ex.map(one, FC_STEPS))
    steps = []
    for s in FC_STEPS:
        if res.get(s):
            valid = init + datetime.timedelta(hours=s)
            steps.append({"date": valid.strftime("%Y-%m-%dT%H"), "step": s, **res[s]})
    return steps


def backfill(history, days):
    today = datetime.date.today()
    want = [today - datetime.timedelta(days=i) for i in range(1, days + 1)]
    todo = [d for d in want if d.isoformat() not in history]

    def one(d):
        try:
            return d, day_stats(d)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {d}: {e}", file=sys.stderr)
            return d, None
    with ThreadPoolExecutor(max_workers=4) as ex:
        for d, st in ex.map(one, todo):
            if st:
                history[d.isoformat()] = st
    return len(todo)


# ── Klimatološki razpon (enkratno) ───────────────────────────────────────────

def build_climatology(years=(2021, 2022, 2023, 2024, 2025), step_days=3):
    """Vrednosti u60 (00 UTC analiza) vsake 3 dni od 1. 10. do 30. 4. za zime 2021/22 … 2025/26, shranjeno po
    mesecu-in-dnevu; stran iz tega izpelje min/povprečje/maks."""
    jobs = []
    for y in years:
        d = datetime.date(y, 10, 1)
        end = datetime.date(y + 1, 4, 30)
        while d <= end:
            if d >= datetime.date(2021, 3, 1):
                jobs.append(d)
            d += datetime.timedelta(days=step_days)

    def one(d):
        try:
            return d, day_stats(d, with_temp=False)["u60"]
        except Exception as e:  # noqa: BLE001
            print(f"  ! {d}: {e}", file=sys.stderr)
            return d, None
    out = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for d, v in ex.map(one, jobs):
            if v is not None:
                out[d.isoformat()] = v
    ac.write_json(CLIMA_PATH, {"u60": out, "built_at": ac.now_utc_iso(),
                               "note": "00 UTC analiza GFS, vsake 3 dni, zime 2021/22–2025/26"})
    print(f"  → {CLIMA_PATH}: {len(out)} vzorcev")


def clima_band(clima, start, end):
    """Razpon (min, povprečje, maks) po datumu med start in end iz vzorcev prejšnjih zim (±4 dni okno)."""
    if not clima:
        return []
    samples = [(datetime.date.fromisoformat(k), v) for k, v in clima["u60"].items()]
    out = []
    d = start
    while d <= end:
        vals = []
        for sd, v in samples:
            try:
                same = sd.replace(year=d.year)
            except ValueError:
                continue
            if abs((same - d).days) <= 4:
                vals.append(v)
        if len(vals) >= 5:
            out.append((d, min(vals), sum(vals) / len(vals), max(vals)))
        d += datetime.timedelta(days=1)
    return out


# ── Stanje in besedilo ───────────────────────────────────────────────────────

def classify(history, fc, today):
    """Stanje vrtinca iz podatkov. Vrne (koda, stavek)."""
    days = sorted(history)
    if not days:
        return "neznano", "Podatkov še ni."
    last_d = datetime.date.fromisoformat(days[-1])
    u = history[days[-1]]["u60"]
    winter = last_d.month in (11, 12, 1, 2, 3)
    fut_min = min((s["u60"] for s in fc), default=None)
    fut_neg = next((s for s in fc if s["u60"] < 0 and s["step"] > 0), None)
    if winter and u < 0:
        return "ssw", (f"Zonalni veter na 10 hPa pri 60 °N je {ac.num(u, 1)} m/s: zahodnik se je obrnil v vzhodnika, "
                       f"kar je kriterij za glavni SSW po WMO.")
    if winter and fut_neg:
        d = datetime.datetime.strptime(fut_neg["date"], "%Y-%m-%dT%H").date()
        return "napoved", (f"GFS napoveduje obrat zahodnika pri 60 °N (pod 0) okoli {ac.fmt_date(d)} "
                           f"({ac.num(fut_neg['u60'], 1)} m/s). Ena napoved ni zanesljiva — pri SSW se modeli "
                           f"pogosto razhajajo.")
    if last_d.month in (5, 6, 7, 8, 9):
        return "poletje", ("Poleti je stratosfera nad polom naravno pod vzhodnim vetrom: polarnega vrtinca ni in SSW ni "
                           "mogoč.")
    if last_d.month == 10 and u < 10:
        return "gradi", (f"Polarni vrtinec se šele krepi: zonalni veter na 10 hPa pri 60 °N je {ac.num(u, 1)} m/s.")
    return "stabilno", (f"Polarni vrtinec obstaja: zonalni veter na 10 hPa pri 60 °N je {ac.num(u, 1)} m/s "
                        f"(zahodnik), do obrata je še daleč.")


def trend_text(history):
    days = sorted(history)
    if len(days) < 8:
        return ""
    d1, d0 = days[-1], days[-8]
    du = history[d1]["u60"] - history[d0]["u60"]
    parts = [f"V zadnjih sedmih dneh se je veter pri 60 °N spremenil za {ac.num(du, 1, True)} m/s"]
    if "t" in history[d1] and "t" in history[d0]:
        dt = history[d1]["t"] - history[d0]["t"]
        parts.append(f"temperatura polarne kape (60–90 °N, 10 hPa) za {ac.num(dt, 1, True)} °C na "
                     f"{ac.num(history[d1]['t'], 1)} °C")
    return ", ".join(parts) + "."


def build_body(d, clima, stale_note=""):
    history = d["history"]
    fc = d["forecast"]["steps"]
    days = sorted(history)
    last_d = datetime.date.fromisoformat(days[-1])
    code, state = classify(history, fc, last_d)
    series_u = [(datetime.date.fromisoformat(k), history[k]["u60"]) for k in days]
    fc_u = [(datetime.datetime.strptime(s["date"], "%Y-%m-%dT%H").date(), s["u60"]) for s in fc]
    band = clima_band(clima, series_u[0][0], fc_u[-1][0] if fc_u else last_d)
    series = []
    if band:
        series.append({"name": "razpon", "color": AMBER, "pts": [], "band": [(a, lo, hi) for a, lo, _m, hi in band]})
        series.append({"name": "povprečje", "color": AMBER, "pts": [(a, m) for a, _lo, m, _hi in band], "width": 1.3,
                       "dash": "3 3"})
    series.append({"name": "analiza", "color": GREEN, "pts": series_u, "width": 2.2})
    if fc_u:
        series.append({"name": "GFS", "color": PURPLE, "pts": [(last_d, series_u[-1][1])] + fc_u[1:], "width": 2,
                       "dash": "5 3"})
    leg = [(GREEN, "analiza GFS (00 UTC)", False), (PURPLE, "napoved GFS do +10 dni", True)]
    if band:
        leg += [(AMBER, "razpon in povprečje zim 2021–2025 (kratek vzorec)", True)]
    chart_u = ac.legend(leg) + ac.line_chart(
        series, marker=(last_d, "zadnja analiza"), unit="m/s", zero=True,
        aria=("Graf zonalnega vetra na 10 hPa pri 60 stopinj severne širine: analiza zadnjih "
              f"{len(days)} dni in napoved GFS do +10 dni."), yfmt=lambda v: ac.num(v, 0))
    t_hist = [(datetime.date.fromisoformat(k), history[k]["t"]) for k in days if "t" in history[k]]
    t_fc = [(datetime.datetime.strptime(s["date"], "%Y-%m-%dT%H").date(), s["t"]) for s in fc if "t" in s]
    ser_t = [{"name": "analiza", "color": GREEN, "pts": t_hist, "width": 2.2}]
    if t_fc and t_hist:
        ser_t.append({"name": "GFS", "color": PURPLE, "pts": [(last_d, t_hist[-1][1])] + t_fc[1:], "width": 2,
                      "dash": "5 3"})
    chart_t = ac.legend([(GREEN, "analiza GFS (00 UTC)", False), (PURPLE, "napoved GFS", True)]) + ac.line_chart(
        ser_t, marker=(last_d, "zadnja analiza"), unit="°C", zero=False,
        aria="Graf povprečne temperature polarne kape (60–90 stopinj severne širine) na 10 hPa.",
        yfmt=lambda v: ac.num(v, 0)) if t_hist else ""
    cur = history[days[-1]]
    kpi = (f'  <div class="callout"><strong>Veter 10 hPa, 60 °N: {ac.num(cur["u60"], 1)} m/s</strong>'
           + (f' · <strong>polarna kapa: {ac.num(cur["t"], 1)} °C</strong>' if "t" in cur else "")
           + f'<br>{_html.escape(state)}<br><span class="muted-note">Analiza {ac.fmt_date(last_d)} '
             f'{_html.escape(trend_text(history))} Stran osvežena {_html.escape(ac.fmt_dt_local(d["generated_at"]))}.'
             f'</span></div>')
    return f'''  <h1 class="page-title">Stratosfera in polarni vrtinec: SSW, veter na 10 hPa</h1>
  <p class="archive-intro">Polarni vrtinec je zahodni veter v stratosferi okoli pola. Če se pozimi oslabi ali
  obrne, govorimo o nenadnem stratosferskem segrevanju (SSW), ki lahko v tednih sledi spremeni vreme v srednji
  Evropi. Stran spremlja zonalni veter pri 60 °N in temperaturo polarne kape iz modela NOAA GFS. To je
  <b>spremljanje, ne napoved vremena</b>: SSW ne pomeni nujno mraza v Rečici. Povezava s pritalnimi tokovi je
  na strani <a href="/indeksi/">indeksov AO in NAO</a>, razmere nad Evropo pa na
  <a href="/sinopticna/">sinoptični karti</a>.</p>
{stale_note}{kpi}
  <h2>Zonalni veter na 10 hPa pri 60 °N</h2>
{chart_u}
  <p class="muted-note">Pozitivno je zahodnik (vrtinec obstaja), pod 0 pozimi je kriterij za glavni SSW.
  Pasovi zim 2021–2025 so le kratek vzorec iz analiz GFS, ne uradna klimatologija.</p>
{('  <h2>Temperatura polarne kape na 10 hPa</h2>' + chr(10) + chart_t) if chart_t else ''}
  <h2>Kaj je to za nas</h2>
  <p class="archive-intro">SSW se zgodi v približno polovici zim, a le v delu primerov mu v enem do šestih tednih
  sledi negativen AO in hladno obdobje nad srednjo Evropo. Zato ga obravnavamo kot dodatni signal, ne kot napoved.
  Za dolino Zgornje Savinjske je pri mrazu bolj kot stratosfera pomembna lokalna inverzija — poglej
  <a href="/zima/">MeteoZimo</a> in <a href="/klima/">klimo Rečice</a>.</p>
  <p class="muted-note">Vir: NOAA GFS (odprti podatki, AWS Open Data). Izračun: povprečje po vseh dolžinah
  vzdolž 60 °N (veter) in uteženo s cos φ za 60–90 °N (temperatura). En model, 0,25°.</p>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--climatology", action="store_true", help="enkratno: razpon zim 2021–2025")
    ap.add_argument("--backfill-days", type=int, default=BACKFILL_DAYS)
    args = ap.parse_args()
    if args.climatology:
        build_climatology()
        return 0
    d = ac.read_json(DATA_PATH, {"history": {}, "forecast": {"steps": []}})
    stale = ""
    try:
        n = backfill(d["history"], args.backfill_days)
        init = latest_run()
        if init is None:
            raise RuntimeError("noben GFS tek ni dosegljiv")
        d["forecast"] = {"init": init.strftime("%Y-%m-%dT%H"), "steps": fetch_forecast(init)}
        if not d["forecast"]["steps"]:
            raise RuntimeError("prazna napoved")
        d["generated_at"] = ac.now_utc_iso()
        keep = sorted(d["history"])[-(args.backfill_days + 30):]
        d["history"] = {k: d["history"][k] for k in keep}
        ac.write_json(DATA_PATH, d)
        print(f"  zgodovina {len(d['history'])} dni (novih poskusov: {n}), napoved iz {d['forecast']['init']}")
    except Exception as e:  # noqa: BLE001
        print(f"✗ GFS: {e}", file=sys.stderr)
        if not d["history"] or not d["forecast"].get("steps"):
            return 1
        stale = (f'  <p class="callout"><strong>Podatki niso sveži:</strong> NOAA GFS ob zadnjem teku ni bil '
                 f'dosegljiv, prikazan je posnetek z {_html.escape(ac.fmt_dt_local(d["generated_at"]))}.</p>\n')
    clima = ac.read_json(CLIMA_PATH)
    title = "Stratosfera in polarni vrtinec: veter na 10 hPa, SSW"
    desc = ("Veter na 10 hPa pri 60 °N, polarna kapa in SSW iz modela GFS: zadnji meseci in napoved za 10 dni. "
            "Spremljanje vrtinca, ne napoved mraza.")
    ac.write_site_page(REL + "index.html", REL, title, desc, build_body(d, clima, stale), FAQ,
                       "Stratosfera in polarni vrtinec", "2026-10-22", modified=d["generated_at"][:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
