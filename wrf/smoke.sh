#!/bin/bash
# wrf/smoke.sh — preizkus celotnega cevovoda BREZ 29 GB WPS_GEOG: sintetični statični podatki + pravi GFS + tri majhne domene.
# Dokaže, da namelisti, WPS, real in wrf tečejo in da se mreže ujemajo. Rezultat NI napoved (teren in raba tal sta
# izmišljena, razen terena Copernicus, če je v $GEOG/cop30m) in se ne sme primerjati z meritvami.
#
#   docker run --rm -v $PWD:/work -v /tmp/geog:/geog meteorec-wrf bash /work/wrf/smoke.sh
#
# Spremenljivke: INIT (privzeto včeraj 00 UTC), HOURS (6), NP (nproc). Čas: ~10 min na 4 jedrih.
set -euo pipefail
G=/geog/WPS_GEOG
if [ ! -d "$G/topo_gmted2010_30s" ]; then
  python3 /work/wrf/synthetic_geog.py "$G" /opt/WPS/geogrid/GEOGRID.TBL.ARW
fi
export INIT="${INIT:-$(date -u -d yesterday +%Y%m%d)00}"
export HOURS="${HOURS:-6}" PROFILE=test
bash /work/wrf/run.sh
ls -la /work/out/recica-"$INIT".json
