// One-off: builds src/data/worldmask.json, the land/sea mask behind the dot map of the daily mystery.
//
//   cd 365-0-game && npm i --no-save world-atlas@2.0.2 topojson-client@3.1.0 d3-geo@3.1.1 \
//     && node scripts/world-mask/build.mjs
//
// Natural Earth land polygons (public domain, via the world-atlas package) are sampled on a 3-degree
// grid: a cell is land when at least two of five sample points inside it are. The output is committed;
// the three packages are not dependencies of the game.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { geoContains } from 'd3-geo';
import { feature } from 'topojson-client';

const root = join(import.meta.dirname, '../..');
const topo = JSON.parse(
  readFileSync(join(root, 'node_modules/world-atlas/land-110m.json'), 'utf8'),
);
const land = feature(topo, topo.objects.land);

const STEP = 3;
const COLS = 360 / STEP;
const TOP = 81; // latitude of the top edge: covers Longyearbyen (78 N) and McMurdo (78 S)
const ROWS = (TOP * 2) / STEP;
const rows = [];
for (let r = 0; r < ROWS; r++) {
  let line = '';
  const lat0 = TOP - r * STEP;
  for (let c = 0; c < COLS; c++) {
    const lon0 = -180 + c * STEP;
    const samples = [
      [0.5, 0.5],
      [0.25, 0.25],
      [0.75, 0.25],
      [0.25, 0.75],
      [0.75, 0.75],
    ];
    const hits = samples.filter(([dx, dy]) =>
      geoContains(land, [lon0 + dx * STEP, lat0 - dy * STEP]),
    ).length;
    line += hits >= 2 ? '1' : '0';
  }
  rows.push(line);
}
const out = { step: STEP, top: TOP, cols: COLS, rows };
writeFileSync(join(root, 'src/data/worldmask.json'), JSON.stringify(out) + '\n');
console.log(`worldmask: ${String(COLS)} x ${String(ROWS)}, ${String(rows.join('').replaceAll('0', '').length)} land cells`);
