#!/usr/bin/env python3
"""
tools/fetch_wn3.py — dnevni zajem Tmax/Tmin Google DeepMind WeatherNext 3 (WN3)
za Rečico, kot vhod za razširitev modela MTR (glej docs/model-recica.md).

Vir: Zarr v Google Cloud Storage, vedro s PREDIZRAČUNANO STATISTIKO
(gs://weathernext3_statistics_spatial/weathernext_3_0_0_statistics/zarr/
2026_to_present/<YYYYMMDD_HHhr_NN_preds>/predictions.zarr). Vedro NI Requester
Pays; dostop je vezan na odobritev obrazca WeatherNext Data Request.
Spremenljivka: `station_head_temperature_2m_mean` (0,05°, ~5 km; povprečje
64 članov, postajna glava je naučena na meritvah postaj).

Zakaj Zarr in ne BigQuery: tabela 0,05° v BigQuery je razvrščena po geografiji,
a poizvedba za eno točko kljub temu javi ~1 TB branja (preverjeno 12. 10. 2026,
`maximum_bytes_billed` je poizvedbo zavrnil). Zarr ima kos = ENA URA za CELOTNO
globalno mrežo (`chunks=(1, 3601, 7200)`, ~78 MB stisnjeno), zato je en dan
napovedi ~24 kosov = ~1,9 GB prenosa. Dolg enojni prenos se v Cloud Shellu
zatika (isti kos je ob ponovitvah obstal pri 42 in 67 MB), zato ima vsako branje
časovno omejitev in ponovne poskuse.

Kaj se zapiše (data/wn3-archive.csv, samo DODAJA, nikoli ne prepisuje):
  model=wn3, lead_days, valid_at (lokalni dan), issued_at, init_at (UTC),
  tmax_c, tmin_c, cell_lat, cell_lon.
Shema je podmnožica `forecast-archive.csv` (+ init_at, celica), da jo bere
isti nalagalnik.

Pravila, ki jih ne obračaj:
  * Dan je LOKALNI dan (Europe/Ljubljana), ne UTC — ista definicija kot pri
    meritvah in `build_forecast_archive.py`. Na dan prehoda ure ima 23 ali 25 ur;
    dan se obdrži samo, če so VSE ure prisotne (sicer bi bil Tmax/Tmin lažen).
  * `issued_at` je datum, ko je napoved DOSTOPNA (inicializacija + 7 h; GCS jo
    objavi ~6 h 50 min po inicializaciji), ne datum inicializacije. Tako je
    `lead_days = valid_at - issued_at` primerljiv z ostalimi viri v arhivu.
  * Privzeta inicializacija je 18 UTC: jutranji tek MTR (cron zamuja ure) je
    nikoli ne ujame pred objavo, in je 6-urna (horizont 360 h; vmesne urne
    inicializacije segajo le 48 h).
  * Dnevni Tmax/Tmin sta ekstrema URNE POVPREČJA ansambla, ne povprečje
    ekstremov članov — to je vedno nižji Tmax in višji Tmin kot pri članih.
  * Zgodovina pred 1. 1. 2026 NI v tem vedru (`2025/` manjka, `2024/` je
    najverjetneje v učnem vzorcu modela — ne učiti na njem, dokler ni potrjeno).
  * Notranjih meritev tu ni (ta skript bere samo napoved).

Odvisnosti (samo pri pravem zajemu, uvoz je leni): xarray, zarr, obstore.
Poverilnice: privzete Google (ADC ali GOOGLE_APPLICATION_CREDENTIALS).

Usage:
  python3 tools/fetch_wn3.py --plan                 # kaj bi se zajelo (brez omrežja)
  python3 tools/fetch_wn3.py --days 3 [--leads 1]   # zadnje 3 inicializacije
  python3 tools/fetch_wn3.py --since 2026-01-01     # zgodovina (zelo veliko podatkov)
"""
import argparse, csv, datetime, math, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT, LON = 46.325779, 14.921137
TZ = ZoneInfo("Europe/Ljubljana")
UTC = datetime.timezone.utc

BUCKET = "weathernext3_statistics_spatial"
STATS_ROOT = "weathernext_3_0_0_statistics/zarr/2026_to_present"
VAR = "station_head_temperature_2m_mean"
MODEL = "wn3"
ARCHIVE_PATH = os.path.join(ROOT, "data", "wn3-archive.csv")
FIELDS = ["model", "lead_days", "valid_at", "issued_at", "init_at",
          "tmax_c", "tmin_c", "cell_lat", "cell_lon"]

INIT_HOUR = 18          # UTC; 6-urna inicializacija (00/06/12/18), horizont 360 h
PUBLISH_DELAY_H = 7     # objava v GCS ~6 h 50 min po inicializaciji
MAX_LEAD_H = 360        # horizont 6-urnih inicializacij
READ_THREADS = 8
READ_TRIES = 4          # ponovni poskusi ob zatikanju/prekinitvi
READ_TIMEOUT = "60s"


# ── čista logika (testirana v tools/test_wn3.py, brez omrežja) ───────────────

def init_dt(date, hour):
    return datetime.datetime(date.year, date.month, date.day, hour, tzinfo=UTC)


def issued_date(init):
    """Datum, ko je napoved dostopna (UTC). 18 UTC D-1 -> D, 00 UTC D -> D."""
    return (init + datetime.timedelta(hours=PUBLISH_DELAY_H)).date()


def local_day_valid_times(valid_date):
    """UTC trenutki vseh ur lokalnega dne (24; 23/25 na dan prehoda ure)."""
    start = datetime.datetime(valid_date.year, valid_date.month, valid_date.day, tzinfo=TZ)
    nxt = valid_date + datetime.timedelta(days=1)
    end = datetime.datetime(nxt.year, nxt.month, nxt.day, tzinfo=TZ)
    t = start.astimezone(UTC)
    t_end = end.astimezone(UTC)
    out = []
    while t < t_end:
        out.append(t)
        t += datetime.timedelta(hours=1)
    return out


def indices_for_day(init, valid_date, index_by_valid):
    """Indeksi na osi `lead_time` za vse ure lokalnega dne ali None, če katera
    manjka ali je zunaj horizonta (1..MAX_LEAD_H ur od inicializacije)."""
    times = local_day_valid_times(valid_date)
    idx = []
    for t in times:
        lead_h = (t - init).total_seconds() / 3600
        if lead_h < 1 or lead_h > MAX_LEAD_H or t not in index_by_valid:
            return None
        idx.append(index_by_valid[t])
    return idx


def daily_extrema(kelvin):
    """Tmax/Tmin v °C iz urnih vrednosti v K; None, če karkoli ni končno število."""
    vals = list(kelvin)
    if not vals or any(v is None or not math.isfinite(v) for v in vals):
        return None
    return round(max(vals) - 273.15, 1), round(min(vals) - 273.15, 1)


def nearest_index(coords, target):
    """Indeks najbližje vrednosti (koordinate so lahko padajoče)."""
    return min(range(len(coords)), key=lambda i: abs(coords[i] - target))


def lon_to_grid(lon):
    """Mreža WN3 ima dolžine 0..360."""
    return lon % 360


def find_prefix(names, init):
    """Mapa inicializacije med imeni `YYYYMMDD_HHhr_NN_preds`; pri več različicah
    (NN) najvišja. None, če inicializacije (še) ni."""
    head = f"{init:%Y%m%d}_{init:%H}hr_"
    best = None
    for n in names:
        n = n.strip("/").split("/")[-1]
        if not (n.startswith(head) and n.endswith("_preds")):
            continue
        mid = n[len(head):-len("_preds")]
        if mid.isdigit() and (best is None or int(mid) > best[0]):
            best = (int(mid), n)
    return best[1] if best else None


def plan(now, since, until, leads, init_hour, existing):
    """Seznam (init, valid_date, lead_days) za zajem: inicializacije od `since` do
    `until` (datumi), samo že objavljene (`init + PUBLISH_DELAY_H <= now`) in samo
    kar še ni v arhivu (`existing` = množica (init_at, valid_at))."""
    out = []
    d = since
    while d <= until:
        init = init_dt(d, init_hour)
        if init + datetime.timedelta(hours=PUBLISH_DELAY_H) <= now:
            issued = issued_date(init)
            for n in leads:
                valid = issued + datetime.timedelta(days=n)
                if (init.strftime("%Y-%m-%dT%H"), valid.isoformat()) not in existing:
                    out.append((init, valid, n))
        d += datetime.timedelta(days=1)
    return out


def build_row(init, valid_date, lead_days, index_by_valid, read_many, cell):
    """Ena vrstica arhiva ali None (dan z manjkajočo uro, zunaj horizonta, NaN)."""
    idx = indices_for_day(init, valid_date, index_by_valid)
    if idx is None:
        return None
    ext = daily_extrema(read_many(idx))
    if ext is None:
        return None
    issued = issued_date(init)
    return {
        "model": MODEL, "lead_days": (valid_date - issued).days,
        "valid_at": valid_date.isoformat(), "issued_at": issued.isoformat(),
        "init_at": init.strftime("%Y-%m-%dT%H"),
        "tmax_c": ext[0], "tmin_c": ext[1],
        "cell_lat": cell[0], "cell_lon": cell[1],
    }


def load_existing(path=ARCHIVE_PATH):
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                seen.add((r["init_at"], r["valid_at"]))
    return seen


def append_rows(rows, path=ARCHIVE_PATH):
    """Doda samo nove vrstice; obstoječih ne prepiše (isto kot forecast-archive)."""
    if not rows:
        return 0
    seen = load_existing(path)
    new = [r for r in rows if (r["init_at"], r["valid_at"]) not in seen]
    if not new:
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_header = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(new)
    return len(new)


def with_retries(fn, tries=READ_TRIES, sleep=time.sleep):
    """fn() z ponovnimi poskusi (1 s, 2 s, 3 s …); po zadnjem vrže zadnjo napako."""
    last = None
    for k in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — omrežne napake so raznovrstne
            last = e
            if k < tries - 1:
                sleep(1 + k)
    raise last


# ── omrežni del (leni uvozi; ni pokrit s testom brez poverilnic) ──────────────

def _store(prefix=""):
    import obstore
    return obstore.store.GCSStore(bucket=BUCKET, prefix=prefix,
                                  client_options={"timeout": READ_TIMEOUT})


def list_init_dirs():
    import obstore
    res = obstore.list_with_delimiter(_store(), STATS_ROOT)
    return [p.rstrip("/").split("/")[-1] for p in res["common_prefixes"]]


def open_init(prefix):
    """-> (ds, index_by_valid, ilat, ilon, cell). Brez dask (chunks=None)."""
    import numpy as np, xarray as xr, zarr
    store = _store(f"{STATS_ROOT}/{prefix}/predictions.zarr")
    ds = xr.open_zarr(zarr.storage.ObjectStore(store), chunks=None)
    valid = ds["datetime"].values
    index_by_valid = {
        datetime.datetime.fromtimestamp(int(v.astype("datetime64[s]").astype("int64")), UTC): i
        for i, v in enumerate(valid)
    }
    lats = [float(x) for x in ds["lat_0p05"].values]
    lons = [float(x) for x in ds["lon_0p05"].values]
    ilat = nearest_index(lats, LAT)
    ilon = nearest_index(lons, lon_to_grid(LON))
    cell = (round(lats[ilat], 3), round(lons[ilon], 3))
    return ds, index_by_valid, ilat, ilon, cell


def make_reader(ds, ilat, ilon):
    def one(i):
        return with_retries(lambda: float(
            ds[VAR].isel(lead_time=i, lat_0p05=ilat, lon_0p05=ilon).values))

    def read_many(indices):
        with ThreadPoolExecutor(READ_THREADS) as ex:
            return list(ex.map(one, indices))
    return read_many


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--days", type=int, default=3,
                    help="zadnjih N dni inicializacij (privzeto 3)")
    ap.add_argument("--since", help="prvi datum inicializacije (YYYY-MM-DD); povozi --days")
    ap.add_argument("--leads", default="1", help="vodilni dnevi, npr. 1 ali 1,2,3")
    ap.add_argument("--init-hour", type=int, default=INIT_HOUR, choices=(0, 6, 12, 18))
    ap.add_argument("--plan", action="store_true", help="samo izpiši načrt, brez omrežja")
    a = ap.parse_args(argv)

    now = datetime.datetime.now(UTC)
    until = now.date()
    since = (datetime.date.fromisoformat(a.since) if a.since
             else until - datetime.timedelta(days=a.days - 1))
    leads = [int(x) for x in a.leads.split(",")]
    todo = plan(now, since, until, leads, a.init_hour, load_existing())
    for init, valid, n in todo:
        print(f"  init {init:%Y-%m-%d %H}Z -> {valid} (lead {n})")
    print(f"za zajem: {len(todo)} dni (~{len(todo) * 1.9:.1f} GB)")
    if a.plan or not todo:
        return 0

    names = list_init_dirs()
    by_init = {}
    for init, valid, n in todo:
        by_init.setdefault(init, []).append((valid, n))
    fails = 0
    for init, valids in sorted(by_init.items()):
        prefix = find_prefix(names, init)
        if prefix is None:
            print(f"  init {init:%Y-%m-%d %H}Z: še ni v vedru — preskočeno")
            continue
        try:
            ds, idx_by_valid, ilat, ilon, cell = open_init(prefix)
            read_many = make_reader(ds, ilat, ilon)
            rows = []
            for valid, n in valids:
                row = build_row(init, valid, n, idx_by_valid, read_many, cell)
                if row is None:
                    print(f"  {init:%Y-%m-%d %H}Z / {valid}: manjka ura ali podatek — preskočeno")
                    fails += 1
                else:
                    rows.append(row)
            print(f"  {init:%Y-%m-%d %H}Z: +{append_rows(rows)} vrstic")
        except Exception as e:  # noqa: BLE001
            print(f"  {init:%Y-%m-%d %H}Z: NAPAKA {type(e).__name__}: {e}")
            fails += 1
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
