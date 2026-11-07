// Day-type thresholds and classifier (SPEC 1.4). Pure: used by the data build script and the engine.
// These are starting values, to be tuned after reviewing the real data (see docs/data-report.md).

/** One character per day in the stored data. */
export type DayType = 'p' | 'o' | 'r' | 's' | 'h' | 'f';

export const DAY_TYPE_CHARS: readonly DayType[] = ['p', 'o', 'r', 's', 'h', 'f'];

/** Win = perfect, draw = ok, loss = anything else (SPEC 1.3). */
export function isLoss(type: DayType): boolean {
  return type === 'r' || type === 's' || type === 'h' || type === 'f';
}

export const THRESHOLDS = {
  storm: {
    /** WMO thunderstorm codes. */
    codes: [95, 96, 99] as readonly number[],
    gustKmhMin: 70,
    precipMmMin: 30,
  },
  freeze: { tmaxCMax: 3, snowCmMin: 1 },
  heat: { tmaxCMin: 34 },
  rain: { precipMmMin: 1 },
  perfect: {
    tmaxCMin: 19,
    tmaxCMax: 28,
    tminCMin: 9,
    precipMmMax: 1, // exclusive: "under 1 mm"
    gustKmhMax: 40, // exclusive: "under 40 km/h"
    cloudPctMax: 65, // inclusive: "at most 65 percent"; skipped when cloud cover is unknown
  },
} as const;

export interface DailyWeather {
  /** Daily maximum 2 m temperature, °C. */
  tmax: number;
  /** Daily minimum 2 m temperature, °C. */
  tmin: number;
  /** Total precipitation, mm. */
  precip: number;
  /** Snowfall, cm. */
  snow: number;
  /** Maximum 10 m wind gust, km/h. */
  gust: number;
  /** WMO weather code. */
  code: number;
  /** Mean cloud cover, percent. Undefined when the source has none. */
  cloud?: number | undefined;
}

/** Precedence when several apply: storm, freeze, heat, rain, perfect, ok. */
export function classifyDay(day: DailyWeather): DayType {
  const t = THRESHOLDS;
  if (
    t.storm.codes.includes(day.code) ||
    day.gust >= t.storm.gustKmhMin ||
    day.precip >= t.storm.precipMmMin
  ) {
    return 's';
  }
  if (day.tmax <= t.freeze.tmaxCMax || day.snow >= t.freeze.snowCmMin) return 'f';
  if (day.tmax >= t.heat.tmaxCMin) return 'h';
  if (day.precip >= t.rain.precipMmMin) return 'r';
  const p = t.perfect;
  const cloudOk = day.cloud === undefined || day.cloud <= p.cloudPctMax;
  if (
    day.tmax >= p.tmaxCMin &&
    day.tmax <= p.tmaxCMax &&
    day.tmin >= p.tminCMin &&
    day.precip < p.precipMmMax &&
    day.gust < p.gustKmhMax &&
    cloudOk
  ) {
    return 'p';
  }
  return 'o';
}
