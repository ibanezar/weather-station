#!/bin/bash
# wrf/server/remote.sh — teče NA najetem strežniku (Ubuntu, root), ki ga požene .github/workflows/wrf-run.yml prek SSH.
# Spremenljivke: INIT, HOURS, PROFILE, IMAGE, SETUP_ONLY=1 (samo pripravi podatke), GHCR_USER/GHCR_TOKEN (prijava v ghcr.io).
# Statika (WPS_GEOG + Copernicus ploščice) je na priključenem disku (volume) in se prenese samo enkrat.
set -euo pipefail
: "${IMAGE:?}" "${INIT:?}"
HOURS="${HOURS:-36}"; PROFILE="${PROFILE:-prod}"

VOL=$(ls -d /mnt/HC_Volume_* 2>/dev/null | head -1 || true)
[ -n "$VOL" ] || { echo "✗ disk (volume) ni priključen"; exit 1; }
mkdir -p "$VOL/geog" "$VOL/work"

if ! command -v docker >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq docker.io python3-venv python3-pip curl >/dev/null
fi
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
docker pull -q "$IMAGE"

# ── enkratna statika ──
if [ ! -f "$VOL/geog/.geog-ok" ]; then
  echo "== WPS_GEOG (≈2,6 GB prenos, ≈29 GB razpakirano)"
  cd "$VOL/geog"
  # TLS preverjanja NE izklapljamo: če veriga potrdil ucar.edu ne gre skozi, skripta tukaj pade in to je napaka za pregled
  curl -fL --retry 4 -O https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_high_res_mandatory.tar.gz
  tar xzf geog_high_res_mandatory.tar.gz && rm geog_high_res_mandatory.tar.gz
  touch .geog-ok
fi
if [ ! -f "$VOL/geog/.dem-ok" ]; then
  echo "== Copernicus DEM → ploščice WPS"
  python3 -m venv /opt/dem && /opt/dem/bin/pip install -q numpy tifffile imagecodecs
  /opt/dem/bin/python /work/wrf/dem_tiles.py build "$VOL/geog/WPS_GEOG"
  touch "$VOL/geog/.dem-ok"
fi
[ "${SETUP_ONLY:-}" = "1" ] && { echo "✓ podatki pripravljeni"; exit 0; }

echo "== tek $INIT, $HOURS h, profil $PROFILE, $(nproc) jeder"
rm -rf "$VOL/work/out" "$VOL/work/run-"*
docker run --rm -v /work:/srv/repo:ro -v "$VOL/work":/work -v "$VOL/geog":/geog \
  -e INIT="$INIT" -e HOURS="$HOURS" -e PROFILE="$PROFILE" -e NP="$(nproc)" -e OUT=/work/out \
  "$IMAGE" bash /srv/repo/wrf/run.sh
ls -l "$VOL/work/out"
cp "$VOL/work/out/"recica-*.json /work/ 2>/dev/null || true
