// The dot map behind the daily mystery: where a latitude and longitude land on a grid of dots.
// Equirectangular, matching the land mask in src/data/worldmask.json (see scripts/world-mask/build.mjs).

export interface WorldMask {
  /** Degrees per cell. */
  step: number;
  /** Latitude of the top edge, in degrees north. */
  top: number;
  cols: number;
  /** One string per row, from the top; '1' is land. */
  rows: string[];
}

/** Where a place falls, as fractions (0 to 1) of the map's width and height. */
export function project(
  mask: Pick<WorldMask, 'top'>,
  latitude: number,
  longitude: number,
): { x: number; y: number } {
  const clamp = (v: number): number => Math.min(1, Math.max(0, v));
  return {
    x: clamp((longitude + 180) / 360),
    y: clamp((mask.top - latitude) / (2 * mask.top)),
  };
}

/** True when the cell at (col, row) is land. */
export function isLand(mask: WorldMask, col: number, row: number): boolean {
  return mask.rows[row]?.[col] === '1';
}
