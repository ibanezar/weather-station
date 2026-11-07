// One run in progress: the engine state plus what the screens need around it.
import {
  complete,
  dailySeed,
  endlessSeed,
  finish,
  newRun,
  pick,
  scout,
  start,
  undo,
  type Mode,
  type RunState,
} from '../engine/run.ts';
import type { EngineData } from '../engine/types.ts';

export interface Session {
  mode: Mode;
  /** Local date for a daily run. */
  date: string | undefined;
  data: EngineData;
  state: RunState;
}

export function newSession(
  mode: Mode,
  data: EngineData,
  options: { date?: string; entropy?: string },
): Session {
  const seed =
    mode === 'daily'
      ? dailySeed(options.date ?? '')
      : endlessSeed(options.entropy ?? String(Math.random()));
  return { mode, date: options.date, data, state: start(newRun(seed, mode), data) };
}

/** Rebuild a finished run from its seed and picks, e.g. "See today's result" after a restart. */
export function restoreSession(
  mode: Mode,
  data: EngineData,
  seed: string,
  date: string | undefined,
  picks: readonly string[],
): Session {
  let state = start(newRun(seed, mode), data);
  for (const id of picks) state = pick(state, id);
  state = complete(finish(state, data));
  return { mode, date, data, state };
}

export const doPick = (s: Session, cityId: string): void => {
  s.state = pick(s.state, cityId);
};
export const doUndo = (s: Session): void => {
  s.state = undo(s.state);
};
export const doScout = (s: Session, cityId: string): void => {
  s.state = scout(s.state, cityId);
};
export const doFinish = (s: Session): void => {
  s.state = finish(s.state, s.data);
};
export const doComplete = (s: Session): void => {
  s.state = complete(s.state);
};

/** A random entropy string for endless runs, from the browser's crypto (the engine has none). */
export function randomEntropy(): string {
  const bytes = new Uint32Array(2);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(36)).join('');
}
