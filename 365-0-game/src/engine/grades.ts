// Grade tiers (SPEC 1.8). Tunable here, calibrated by scripts/calibrate.ts.

export const GRADE_IDS = [
  'stormbound',
  'umbrella-carrier',
  'drizzle-dodger',
  'fair-weather-friend',
  'sun-chaser',
  'climate-sage',
  'perfect-forecast',
] as const;
export type GradeId = (typeof GRADE_IDS)[number];

/** Lowest ratio of player perfect days to best possible perfect days for each grade. */
export const GRADE_TIERS: readonly { id: GradeId; min: number }[] = [
  { id: 'perfect-forecast', min: 0.99 },
  { id: 'climate-sage', min: 0.93 },
  { id: 'sun-chaser', min: 0.85 },
  { id: 'fair-weather-friend', min: 0.75 },
  { id: 'drizzle-dodger', min: 0.65 },
  { id: 'umbrella-carrier', min: 0.55 },
  { id: 'stormbound', min: 0 },
];

/**
 * Player wins divided by best possible wins (1 when nothing was possible). Capped at 1: the best possible
 * is measured on the first draws, so a redraw can beat it, but 100 % is the top of the scale.
 */
export function ratio(playerWins: number, bestWins: number): number {
  return bestWins <= 0 ? 1 : Math.min(1, playerWins / bestWins);
}

export function gradeFor(r: number): GradeId {
  for (const tier of GRADE_TIERS) if (r >= tier.min) return tier.id;
  return 'stormbound';
}
