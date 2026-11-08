// The state machine of one run (SPEC 3): idle, drafting, revealing, done.
// All functions are pure: they return a new state and throw on an illegal transition.
import { findCombos, netsFor } from './combos.ts';
import { generateDraft, ROUNDS } from './draft.ts';
import { getCity } from './lookup.ts';
import {
  DEFAULT_CHASE,
  DRAFT_ATTEMPTS,
  MIN_BEST_WINS,
  chaseBuckets,
  type ChaseId,
} from './chase.ts';
import { gradeFor, ratio, type GradeId } from './grades.ts';
import { resolve } from './outcome.ts';
import {
  addRecords,
  bestPossible,
  emptyRecord,
  record,
  type BestPossible,
  type RoundOption,
} from './score.ts';
import type { DayType } from './thresholds.ts';
import type { DayRecord, DraftRound, EngineData } from './types.ts';

export type Phase = 'idle' | 'drafting' | 'revealing' | 'done';
export type Mode = 'daily' | 'endless';

export const SCOUTS_PER_RUN = 3;

/**
 * The daily seed uses the player's local date, e.g. 365-0:daily:2026-11-06. The sunny game keeps that
 * form; every other chase has its own draft for the day, e.g. 365-0:daily:2026-11-06:snow.
 */
export function dailySeed(date: string, chase: ChaseId = DEFAULT_CHASE): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error(`bad date ${date}`);
  return chase === DEFAULT_CHASE ? `365-0:daily:${date}` : `365-0:daily:${date}:${chase}`;
}

/** Endless runs get their entropy from the caller (the engine has no randomness of its own). */
export function endlessSeed(entropy: string): string {
  return `365-0:endless:${entropy}`;
}

export interface PickedRound {
  round: number;
  month: number;
  cityId: string;
  year: number;
  days: DayType[];
  record: DayRecord;
  /** How many times this month was re-rolled (0 = the first draw stands). */
  rerolls: number;
  /** The best option that round offered. */
  best: RoundOption;
}

export interface RunResult {
  record: DayRecord;
  bestRecord: DayRecord;
  /** Player perfect days divided by best possible perfect days. */
  ratio: number;
  grade: GradeId;
  rounds: PickedRound[];
}

export interface RunState {
  readonly phase: Phase;
  readonly mode: Mode;
  readonly chase: ChaseId;
  readonly seed: string;
  readonly draft: readonly DraftRound[];
  /** Computed at the start of the run. */
  readonly best: BestPossible | undefined;
  readonly picks: readonly string[];
  readonly scoutsLeft: number;
  /** Keys `${round}:${cityId}` of scouted cards. */
  readonly scouted: readonly string[];
  /**
   * How many picks are final. A pick shows its month at once; until the player keeps it
   * (or redraws it) it is the one pending pick, and no further pick can be made.
   */
  readonly settled: number;
  /** Rounds that used a second chance, in order (a round can appear more than once). */
  readonly rerolls: readonly number[];
  readonly result: RunResult | undefined;
}

export function newRun(seed: string, mode: Mode, chase: ChaseId = DEFAULT_CHASE): RunState {
  return {
    phase: 'idle',
    mode,
    chase,
    seed,
    draft: [],
    best: undefined,
    picks: [],
    scoutsLeft: SCOUTS_PER_RUN,
    scouted: [],
    settled: 0,
    rerolls: [],
    result: undefined,
  };
}

function need(state: RunState, phase: Phase, action: string): void {
  if (state.phase !== phase) {
    throw new Error(`cannot ${action} in phase ${state.phase}`);
  }
}

/**
 * idle to drafting: build the draft and the best possible record. A chase other than sunshine needs enough
 * winnable months, so a draft that is too poor for it is replaced by the next attempt for the same seed.
 */
export function start(state: RunState, data: EngineData): RunState {
  need(state, 'idle', 'start');
  let chosen: { draft: DraftRound[]; best: BestPossible } | undefined;
  for (let attempt = 0; attempt < DRAFT_ATTEMPTS; attempt++) {
    const draft = generateDraft(state.seed, data, attempt);
    const best = bestPossible(data, state.seed, draft, state.chase);
    if (!chosen || best.record.w > chosen.best.record.w) chosen = { draft, best };
    if (best.record.w >= MIN_BEST_WINS[state.chase]) {
      chosen = { draft, best };
      break;
    }
  }
  if (!chosen) throw new Error('no draft');
  return { ...state, phase: 'drafting', draft: chosen.draft, best: chosen.best };
}

/** The round the player is choosing for, or undefined once all twelve picks are made. */
export function currentRound(state: RunState): DraftRound | undefined {
  return state.draft[state.picks.length];
}

export function pick(state: RunState, cityId: string): RunState {
  need(state, 'drafting', 'pick');
  if (state.picks.length !== state.settled)
    throw new Error('keep or redraw the current month first');
  const round = currentRound(state);
  if (!round) throw new Error('all rounds are picked');
  if (!(round.cities as readonly string[]).includes(cityId)) {
    throw new Error(`${cityId} is not on offer this round`);
  }
  return { ...state, picks: [...state.picks, cityId] };
}

const scoutKey = (round: number, cityId: string): string => `${String(round)}:${cityId}`;

export function isScouted(state: RunState, cityId: string): boolean {
  return state.scouted.includes(scoutKey(state.picks.length, cityId));
}

/** Spend a scout on one card of the current round. Scouting a card twice is free. */
export function scout(state: RunState, cityId: string): RunState {
  need(state, 'drafting', 'scout');
  const round = currentRound(state);
  if (!round) throw new Error('all rounds are picked');
  if (!(round.cities as readonly string[]).includes(cityId)) {
    throw new Error(`${cityId} is not on offer this round`);
  }
  if (isScouted(state, cityId)) return state;
  if (state.scoutsLeft <= 0) throw new Error('no scouts left');
  return {
    ...state,
    scoutsLeft: state.scoutsLeft - 1,
    scouted: [...state.scouted, scoutKey(state.picks.length, cityId)],
  };
}

/** The bucketed (0 to 4) scout values for a city in a month. */
export function scoutInfo(
  data: Pick<EngineData, 'world'>,
  cityId: string,
  month: number,
  chase: ChaseId = DEFAULT_CHASE,
): { win: number; loss: number } {
  const city = data.world.cities[cityId];
  if (!city) throw new Error(`no world data for ${cityId}`);
  // The sunny game keeps the buckets stored in the world file; the other chases rank the same days again.
  if (chase === DEFAULT_CHASE) return { win: city.sp[month] ?? 0, loss: city.sb[month] ?? 0 };
  return chaseBuckets(data.world, chase, cityId, month);
}

/** What one picked month turned out to be, given the second chances used on it. */
export function monthOf(state: RunState, data: EngineData, i: number): PickedRound {
  const best = state.best;
  if (!best) throw new Error('run was not started');
  const draftRound = state.draft[i] as DraftRound;
  const cityId = state.picks[i];
  if (cityId === undefined) throw new Error(`round ${String(i)} is not picked`);
  const rerolls = state.rerolls.filter((r) => r === i).length;
  const o = resolve(data, state.seed, i, cityId, draftRound.month, draftRound.event, rerolls);
  return {
    round: i,
    month: draftRound.month,
    cityId,
    year: o.year,
    days: o.days,
    record: record(o.days, state.chase),
    rerolls,
    best: (best.rounds[i] as { best: RoundOption }).best,
  };
}

/** The result of the twelve picks, with the re-rolls applied. */
function buildResult(state: RunState, data: EngineData): RunResult {
  const best = state.best;
  if (!best) throw new Error('run was not started');
  let total: DayRecord = emptyRecord();
  const rounds = state.picks.map((_, i) => {
    const picked = monthOf(state, data, i);
    total = addRecords(total, picked.record);
    return picked;
  });
  const r = ratio(total.w, best.record.w);
  return { record: total, bestRecord: best.record, ratio: r, grade: gradeFor(r), rounds };
}

/** drafting to revealing: lock the twelve picks and work out the result. */
export function finish(state: RunState, data: EngineData): RunState {
  need(state, 'drafting', 'finish');
  if (state.picks.length !== ROUNDS || state.settled !== ROUNDS)
    throw new Error('twelve final picks are needed to finish');
  return { ...state, phase: 'revealing', result: buildResult(state, data) };
}

/** Safety nets earned so far: a free one, plus one for each combo the picks completed. */
export function netsTotal(state: RunState, data: Pick<EngineData, 'cities'>): number {
  const picked = state.picks.map((id) => getCity(data, id));
  return netsFor(findCombos(picked).length);
}

export function netsLeft(state: RunState, data: Pick<EngineData, 'cities'>): number {
  return Math.max(0, netsTotal(state, data) - state.rerolls.length);
}

/** The month just picked: what it turned out to be, given the second chances already used on it. */
export function pendingMonth(state: RunState, data: EngineData): PickedRound | undefined {
  if (state.phase !== 'drafting' || state.picks.length !== state.settled + 1) return undefined;
  return monthOf(state, data, state.picks.length - 1);
}

/** Keep the month that was just shown: the pick becomes final. */
export function keep(state: RunState): RunState {
  need(state, 'drafting', 'keep');
  if (state.picks.length !== state.settled + 1) throw new Error('nothing to keep');
  return { ...state, settled: state.picks.length };
}

/**
 * Spend a second chance on the month that was just shown: it is drawn again and shows a different year.
 * The new year stands, better or worse (it can be redrawn again while chances are left).
 */
export function reroll(state: RunState, data: Pick<EngineData, 'cities'>): RunState {
  need(state, 'drafting', 're-roll');
  if (state.picks.length !== state.settled + 1) throw new Error('nothing to redraw');
  if (netsLeft(state, data) <= 0) throw new Error('no second chances left');
  return { ...state, rerolls: [...state.rerolls, state.picks.length - 1] };
}

/** revealing to done: the reveal has played (or was skipped). */
export function complete(state: RunState): RunState {
  need(state, 'revealing', 'complete');
  return { ...state, phase: 'done' };
}
