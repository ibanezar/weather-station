// Game data: the city index and events are bundled; the weather itself is a lazy-loaded file.
import eventsJson from '../../data/events.json';
import cityIndex from '../data/cities.index.json';
import type { SeedCity, World } from '../data/types.ts';
import type { MysteryFile } from '../engine/mystery.ts';
import type { EngineData, WorldEvent } from '../engine/types.ts';

export const cities = cityIndex as SeedCity[];
export const events = eventsJson as WorldEvent[];

let worldPromise: Promise<World> | undefined;

/** Fetch world.v1.json once; a failed load can be retried. */
export function loadWorld(): Promise<World> {
  worldPromise ??= fetch(new URL('data/world.v1.json', document.baseURI))
    .then((res) => {
      if (!res.ok) throw new Error(`world data: HTTP ${String(res.status)}`);
      return res.json() as Promise<World>;
    })
    .catch((err: unknown) => {
      worldPromise = undefined;
      throw err;
    });
  return worldPromise;
}

/** Start loading the weather data while the player is on Home (idle time, no spinner). */
export function prefetchWorld(): void {
  const start = (): void => {
    loadWorld().catch(() => {
      // Ignore here: the real load, when the player starts a run, shows the error and a retry.
    });
  };
  if ('requestIdleCallback' in window) window.requestIdleCallback(start);
  else setTimeout(start, 1500);
}

export async function loadEngineData(): Promise<EngineData> {
  return { cities, events, world: await loadWorld() };
}

let mysteryPromise: Promise<MysteryFile> | undefined;

/** Fetch mystery.v1.json once (only the daily mystery needs it); a failed load can be retried. */
export function loadMystery(): Promise<MysteryFile> {
  mysteryPromise ??= fetch(new URL('data/mystery.v1.json', document.baseURI))
    .then(async (res) => {
      if (!res.ok) throw new Error(`mystery data: HTTP ${String(res.status)}`);
      const file = (await res.json()) as Partial<MysteryFile>;
      if (file.v !== 1 || !Array.isArray(file.puzzles) || file.puzzles.length === 0)
        throw new Error('mystery data: unexpected shape');
      return file as MysteryFile;
    })
    .catch((err: unknown) => {
      mysteryPromise = undefined;
      throw err;
    });
  return mysteryPromise;
}
