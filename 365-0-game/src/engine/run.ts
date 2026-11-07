// The state machine of one run (SPEC 3): idle, drafting, revealing, done.
// All functions are pure: they return a new state and throw on an illegal transition.
import { findCombos, netsFor } from './combos.ts';
import { generateDraft, ROUNDS } from './draft.ts';
import { getCity } from './lookup.ts';
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

/** The daily seed uses the player's local date, e.g. 365-0:daily:2026-11-06. */
export function dailySeed(date: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error(`bad date ${date}`);
  return `365-0:daily:${date}`;
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
  readonly seed: string;
  readonly draft: readonly DraftRound[];
  /** Computed at the start of the run. */
  readonly best: BestPossible | undefined;
  readonly picks: readonly string[];
  readonly scoutsLeft: number;
  /** Keys `${round}:${cityId}` of scouted cards. */
  readonly scouted: readonly string[];
  /** True right after a pick, until it is undone or the picks are locked. */
  readonly undoable: boolean;
  /** Rounds that used a safety net, in order (a round can appear more than once). */
  readonly rerolls: readonly number[];
  readonly result: RunResult | undefined;
}

export function newRun(seed: string, mode: Mode): RunState {
  return {
    phase: 'idle',
    mode,
    seed,
    draft: [],
    best: undefined,
    picks: [],
    scoutsLeft: SCOUTS_PER_RUN,
    scouted: [],
    undoable: false,
    rerolls: [],
    result: undefined,
  };
}

function need(state: RunState, phase: Phase, action: string): void {
  if (state.phase !== phase) {
    throw new Error(`cannot ${action} in phase ${state.phase}`);
  }
}

/** idle to drafting: build the draft and the best possible record. */
export function start(state: RunState, data: EngineData): RunState {
  need(state, 'idle', 'start');
  const draft = generateDraft(state.seed, data);
  return { ...state, phase: 'drafting', draft, best: bestPossible(data, state.seed, draft) };
}

/** The round the player is choosing for, or undefined once all twelve picks are made. */
export function currentRound(state: RunState): DraftRound | undefined {
  return state.draft[state.picks.length];
}

export function pick(state: RunState, cityId: string): RunState {
  need(state, 'drafting', 'pick');
  const round = currentRound(state);
  if (!round) throw new Error('all rounds are picked');
  if (!(round.cities as readonly string[]).includes(cityId)) {
    throw new Error(`${cityId} is not on offer this round`);
  }
  return { ...state, picks: [...state.picks, cityId], undoable: true };
}

/** Free, and only for the most recent pick. */
export function undo(state: RunState): RunState {
  need(state, 'drafting', 'undo');
  if (!state.undoable || state.picks.length === 0) throw new Error('nothing to undo');
  return { ...state, picks: state.picks.slice(0, -1), undoable: false };
}

/**
 * The Android back gesture: take back the latest pick, whether or not its undo toast is still showing.
 * Outcomes stay hidden until the reveal, so going back gives no information advantage, and used scouts
 * stay used.
 */
export function stepBack(state: RunState): RunState {
  need(state, 'drafting', 'step back');
  if (state.picks.length === 0) throw new Error('nothing to step back to');
  return { ...state, picks: state.picks.slice(0, -1), undoable: false };
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
): { perfect: number; bad: number } {
  const city = data.world.cities[cityId];
  if (!city) throw new Error(`no world data for ${cityId}`);
  return { perfect: city.sp[month] ?? 0, bad: city.sb[month] ?? 0 };
}

/** The result of the twelve picks, with the re-rolls applied. */
function buildResult(state: RunState, data: EngineData): RunResult {
  const best = state.best;
  if (!best) throw new Error('run was not started');
  let total: DayRecord = emptyRecord();
  const rounds = state.picks.map((cityId, i): PickedRound => {
    const draftRound = state.draft[i] as DraftRound;
    const rerolls = state.rerolls.filter((r) => r === i).length;
    const o = resolve(data, state.seed, i, cityId, draftRound.month, draftRound.event, rerolls);
    const rec = record(o.days);
    total = addRecords(total, rec);
    return {
      round: i,
      month: draftRound.month,
      cityId,
      year: o.year,
      days: o.days,
      record: rec,
      rerolls,
      best: (best.rounds[i] as { best: RoundOption }).best,
    };
  });
  const r = ratio(total.w, best.record.w);
  return { record: total, bestRecord: best.record, ratio: r, grade: gradeFor(r), rounds };
}

/** drafting to revealing: lock the twelve picks and work out the result. */
export function finish(state: RunState, data: EngineData): RunState {
  need(state, 'drafting', 'finish');
  if (state.picks.length !== ROUNDS) throw new Error('twelve picks are needed to finish');
  return { ...state, phase: 'revealing', undoable: false, result: buildResult(state, data) };
}

/** Safety nets earned so far: a free one, plus one for each combo the picks completed. */
export function netsTotal(state: RunState, data: Pick<EngineData, 'cities'>): number {
  const picked = state.picks.map((id) => getCity(data, id));
  return netsFor(findCombos(picked).length);
}

export function netsLeft(state: RunState, data: Pick<EngineData, 'cities'>): number {
  return Math.max(0, netsTotal(state, data) - state.rerolls.length);
}

/**
 * Spend a safety net on one month: it is drawn again and shows a different year. The new year stands,
 * better or worse. Only after the reveal, so the player has seen the month they are giving up.
 */
export function reroll(state: RunState, data: EngineData, round: number): RunState {
  need(state, 'done', 're-roll');
  if (!Number.isInteger(round) || round < 0 || round >= ROUNDS) throw new Error('no such round');
  if (netsLeft(state, data) <= 0) throw new Error('no safety nets left');
  const next = { ...state, rerolls: [...state.rerolls, round] };
  return { ...next, result: buildResult(next, data) };
}

/** revealing to done: the reveal has played (or was skipped). */
export function complete(state: RunState): RunState {
  need(state, 'revealing', 'complete');
  return { ...state, phase: 'done' };
}
