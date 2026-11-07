// Day-type thresholds and classifier (SPEC 1.4). Pure: used by the data build script and the engine.
// Tuned on the real data (scripts/tune.ts, 7 Nov 2026): the SPEC starting values gave 10% perfect and 48% bad
// days, so a random run was Stormbound 72% of the time. These give about 32% perfect, 40% ok, 29% bad overall.
// "Perfect" still needs under 1 mm of rain; only the rain *loss* starts at 5 mm (ERA5 drizzles on too many days).

/** One character per day in the stored data. */
export type DayType = 'p' | 'o' | 'r' | 's' | 'h' | 'f';

export const DAY_TYPE_CHARS: readonly DayType[] = ['p', 'o', 'r', 's', 'h', 'f'];

/** Win = perfect, draw = ok, loss = anything else (SPEC 1.3). */
export function isLoss(type: DayType): boolean {
  return type === 'r' || type === 's' || type === 'h' || type === 'f';
}

export interface Thresholds {
  storm: { codes: readonly number[]; gustKmhMin: number; precipMmMin: number };
  freeze: { tmaxCMax: number; snowCmMin: number };
  heat: { tmaxCMin: number };
  rain: { precipMmMin: number };
  perfect: {
    tmaxCMin: number;
    tmaxCMax: number;
    tminCMin: number;
    /** Exclusive: "under this many mm". */
    precipMmMax: number;
    /** Exclusive: "under this many km/h". */
    gustKmhMax: number;
    /** Inclusive; skipped when cloud cover is unknown. */
    cloudPctMax: number;
  };
}

export const THRESHOLDS: Thresholds = {
  storm: {
    /** WMO thunderstorm codes. */
    codes: [95, 96, 99],
    gustKmhMin: 70,
    precipMmMin: 30,
  },
  freeze: { tmaxCMax: 3, snowCmMin: 1 },
  heat: { tmaxCMin: 36 },
  rain: { precipMmMin: 5 },
  perfect: {
    tmaxCMin: 16,
    tmaxCMax: 32,
    tminCMin: 5,
    precipMmMax: 1,
    gustKmhMax: 50,
    cloudPctMax: 90,
  },
};

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
export function classifyDay(day: DailyWeather, t: Thresholds = THRESHOLDS): DayType {
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
