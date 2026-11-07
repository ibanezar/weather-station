// Cached id lookups over the injected data, plus the event/tag matching rule.
import type { SeedCity } from '../data/types.ts';
import type { EngineData, WorldEvent } from './types.ts';

const cityCache = new WeakMap<readonly SeedCity[], Map<string, SeedCity>>();
const eventCache = new WeakMap<readonly WorldEvent[], Map<string, WorldEvent>>();

export function getCity(data: Pick<EngineData, 'cities'>, id: string): SeedCity {
  let map = cityCache.get(data.cities);
  if (!map) {
    map = new Map(data.cities.map((c) => [c.id, c]));
    cityCache.set(data.cities, map);
  }
  const city = map.get(id);
  if (!city) throw new Error(`unknown city ${id}`);
  return city;
}

export function getEvent(data: Pick<EngineData, 'events'>, id: string): WorldEvent {
  let map = eventCache.get(data.events);
  if (!map) {
    map = new Map(data.events.map((e) => [e.id, e]));
    eventCache.set(data.events, map);
  }
  const event = map.get(id);
  if (!event) throw new Error(`unknown event ${id}`);
  return event;
}

/** An event affects a city when the event covers all tags or shares at least one tag with it. */
export function eventAffects(event: WorldEvent, city: Pick<SeedCity, 'tags'>): boolean {
  if (event.tags === 'all') return true;
  const tags = event.tags;
  return city.tags.some((t) => tags.includes(t));
}
