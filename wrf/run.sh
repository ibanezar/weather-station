#!/bin/bash
# wrf/run.sh — celoten cevovod WPS → real → wrf → izvleček za Rečico, znotraj slike meteorec-wrf.
#
#   docker run --rm -v $PWD:/work -v /data/geog:/geog -e INIT=2026102212 -e HOURS=36 meteorec-wrf bash /work/wrf/run.sh
#
# Spremenljivke: INIT (YYYYMMDDHH, UTC; obvezno), HOURS (36), PROFILE (prod|test), NP (št. jeder), GEOG (/geog/WPS_GEOG),
# GFS_DIR (/work/gfs; prenese ga wrf/fetch_gfs.py, če ga ni), OUT (/work/out), STOP_AFTER (geogrid|ungrib|metgrid|real),
# SKIP_UNGRIB=1, MAX_SLOPE_DEG (omejitev naklona terena, 22; 0 = izklop), NAMELIST_SED (poskusi), SMOOTH_PASSES (glajenje terena; privzeto 1), PBL (ysu|myj), SKIP_WPS=1 / SKIP_REAL=1 (ponovni zagon samo WRF), GEOG_RES (npr. 10m za preizkus s skromnimi podatki). Če obstaja $GEOG/cop30m, se uporabi lasten DEM za domene ≤ 1,5 km.
set -euo pipefail
ulimit -s unlimited || true   # WRF brez neomejenega sklada pade z »munmap_chunk(): invalid pointer«

: "${INIT:?INIT=YYYYMMDDHH je obvezen}"
HOURS="${HOURS:-36}"
PROFILE="${PROFILE:-prod}"
NP="${NP:-$(nproc)}"
GEOG="${GEOG:-/geog/WPS_GEOG}"
GFS_DIR="${GFS_DIR:-/work/gfs}"
OUT="${OUT:-/work/out}"
RUN="/work/run-${INIT}-${PROFILE}"
SRC="$(cd "$(dirname "$0")" && pwd)"
T0=$(date +%s)
step() { echo "[$(( $(date +%s) - T0 )) s] $*"; }

mkdir -p "$RUN" "$OUT"
cd "$RUN"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"

step "namelisti ($PROFILE, init $INIT, $HOURS h)"
DEM_FLAG=""
[ -d "$GEOG/cop30m" ] && DEM_FLAG="--dem"   # lasten DEM (wrf/dem_tiles.py build) → d03/d04 z 30 m terenom
python3 "$SRC/config.py" render "$RUN" --init "$INIT" --hours "$HOURS" --profile "$PROFILE" --geog "$GEOG" ${GEOG_RES:+--geog-res "$GEOG_RES"} ${PBL:+--pbl "$PBL"} $DEM_FLAG

# Poskusni kavelj: NAMELIST_SED="s/dzbot = .*/dzbot = 50.,/" prilagodi namelist.input pred tekom (za eksperimente, ne za dnevni tek)
[ -n "${NAMELIST_SED:-}" ] && sed -i "$NAMELIST_SED" "$RUN/namelist.input"

# ── WPS ──────────────────────────────────────────────────────────────────────
if [ "${SKIP_WPS:-}" = "1" ] && ls "$RUN"/wps/met_em.d01.* >/dev/null 2>&1; then
  step "WPS preskočen (SKIP_WPS=1, met_em obstajajo)"
  cd "$RUN/wps"
else
mkdir -p wps && cd wps
for f in geogrid.exe ungrib.exe metgrid.exe link_grib.csh; do ln -sf /opt/WPS/$f .; done
cp -r /opt/WPS/geogrid /opt/WPS/metgrid . 2>/dev/null || true   # kopija, da jo lahko prilagodimo (DEM)
mkdir -p ungrib && ln -sf /opt/WPS/ungrib/Variable_Tables/Vtable.GFS Vtable
cp "$RUN/namelist.wps" .

if [ -n "$DEM_FLAG" ]; then
  step "lasten DEM (Copernicus 30 m)"
  python3 "$SRC/dem_tiles.py" patch-table geogrid/GEOGRID.TBL ${SMOOTH_PASSES:+--smooth "$SMOOTH_PASSES"}
elif [ -n "${SMOOTH_PASSES:-}" ]; then
  python3 "$SRC/dem_tiles.py" patch-table geogrid/GEOGRID.TBL --no-dem --smooth "$SMOOTH_PASSES"
fi

step "geogrid"
./geogrid.exe > geogrid.log 2>&1 || { tail -30 geogrid.log; exit 1; }
tail -2 geogrid.log
# strm teren pri 0,5 km sesuje WRF (glej wrf/limit_slope.py): omeji naklone na MAX_SLOPE_DEG (privzeto 30°, 0 = izklop)
if [ "${MAX_SLOPE_DEG:-22}" != "0" ]; then
  step "omejitev naklona terena (${MAX_SLOPE_DEG:-22}°)"
  python3 "$SRC/limit_slope.py" geo_em.d0*.nc --max-deg "${MAX_SLOPE_DEG:-22}"
fi
[ "${STOP_AFTER:-}" = "geogrid" ] && exit 0

if [ ! -d "$GFS_DIR" ] || [ -z "$(ls "$GFS_DIR"/*.grib2 2>/dev/null)" ]; then
  step "prenos GFS"
  python3 "$SRC/fetch_gfs.py" --init "$INIT" --hours "$HOURS" --out "$GFS_DIR"
fi
if [ "${SKIP_UNGRIB:-}" = "1" ] && ls GFS:* >/dev/null 2>&1; then
  step "ungrib preskočen (SKIP_UNGRIB=1, GFS:* obstajajo)"
else
  step "ungrib"
  ./link_grib.csh "$GFS_DIR"/gfs.*.grib2
  ./ungrib.exe > ungrib.log 2>&1 || { tail -30 ungrib.log; exit 1; }
  tail -2 ungrib.log
fi
[ "${STOP_AFTER:-}" = "ungrib" ] && exit 0

step "metgrid"
./metgrid.exe > metgrid.log 2>&1 || { tail -30 metgrid.log; exit 1; }
tail -2 metgrid.log
ls met_em.d01.* | wc -l | xargs echo "met_em d01 datotek:"
[ "${STOP_AFTER:-}" = "metgrid" ] && exit 0
fi
cd "$RUN"

# ── WRF ──────────────────────────────────────────────────────────────────────
mkdir -p wrf && cd wrf
for f in /opt/WRF/run/*; do b=$(basename "$f"); case "$b" in namelist.input) ;; *) ln -sf "$f" . ;; esac; done
cp "$RUN/namelist.input" .
ln -sf "$RUN"/wps/met_em.d0* .

# številko nivojev iz podatkov, ne ugibanja (GFS jih ima 34 ali 41 — odvisno od polj)
NL=$(python3 - <<'PY'
import glob
from netCDF4 import Dataset
f = sorted(glob.glob("met_em.d01.*"))[0]
print(Dataset(f).dimensions["num_metgrid_levels"].size)
PY
)
sed -i "s/num_metgrid_levels *= *[0-9]*/num_metgrid_levels = $NL/" namelist.input
if [ "${SKIP_REAL:-}" = "1" ] && ls wrfinput_d01 >/dev/null 2>&1; then
  step "real preskočen (SKIP_REAL=1)"
else
  step "real (num_metgrid_levels = $NL, $NP procesov)"
  mpirun -np "$NP" ./real.exe > real.log 2>&1 || true
  grep -q "SUCCESS COMPLETE REAL_EM" rsl.error.0000 || { tail -30 rsl.error.0000; exit 1; }
  [ "${STOP_AFTER:-}" = "real" ] && exit 0
fi

step "wrf (to traja dolgo)"
mpirun -np "$NP" ./wrf.exe > wrf.log 2>&1 || true
grep -q "SUCCESS COMPLETE WRF" rsl.error.0000 || { tail -30 rsl.error.0000; exit 1; }

step "izvleček za Rečico"
python3 "$SRC/extract.py" --dir "$RUN/wrf" --out "$OUT/recica-${INIT}.json" --init "$INIT"
step "konec"
