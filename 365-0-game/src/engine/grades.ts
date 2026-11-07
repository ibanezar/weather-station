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

/** Player perfect days divided by best possible perfect days (1 when nothing was possible). */
export function ratio(playerWins: number, bestWins: number): number {
  return bestWins <= 0 ? 1 : playerWins / bestWins;
}

export function gradeFor(r: number): GradeId {
  for (const tier of GRADE_TIERS) if (r >= tier.min) return tier.id;
  return 'stormbound';
}
