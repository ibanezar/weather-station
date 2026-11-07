// `npm run data`: fetch 10 years of daily weather per city, classify every day, write the game data.
//
//   node scripts/build-data.ts [--only=id,id] [--offline] [--years=2016-2025] [--delay-ms=300]
//                         [--max-wait-hours=0]
//
// Responses are cached in scripts/.cache/ (gitignored). The free API allows about 10,000 weighted
// calls per day and this job needs more than one day's worth, so the script stops cleanly at the
// limit (exit code 75) and a re-run carries on from the cache. In the Claude cloud sandbox run it
// with NODE_USE_ENV_PROXY=1 so that fetch uses the session proxy. With --max-wait-hours=N the script
// sleeps through a rate limit that resets within N hours instead of stopping (used by the CI job).
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';
import type { SeedCity } from '../src/data/types.ts';
import {
  buildWorld,
  combineYears,
  parseYear,
  type ApiResponse,
  type CityDays,
  type ParsedYear,
} from './lib/build.ts';
import { getCityYear, RateLimitError, readCache } from './lib/fetch.ts';
import { renderReport, findFlags, type GridMeta } from './lib/report.ts';
import { validateIndex, validateSeed, validateWorld } from './lib/validate.ts';

const EXIT_TEMPFAIL = 75;

const root = join(import.meta.dirname, '..');
const paths = {
  seed: join(root, 'data/cities.seed.json'),
  cache: join(root, 'scripts/.cache'),
  world: join(root, 'public/data/world.v1.json'),
  index: join(root, 'src/data/cities.index.json'),
  report: join(root, 'docs/data-report.md'),
};

function arg(name: string): string | undefined {
  const prefix = `--${name}=`;
  return process.argv.find((a) => a.startsWith(prefix))?.slice(prefix.length);
}
const flag = (name: string): boolean => process.argv.includes(`--${name}`);

const log = (msg: string): void => {
  console.log(msg);
};

function parseYears(spec: string): number[] {
  const m = /^(\d{4})-(\d{4})$/.exec(spec);
  if (!m) throw new Error(`--years must look like 2016-2025, got ${spec}`);
  const from = Number(m[1]);
  const to = Number(m[2]);
  return Array.from({ length: to - from + 1 }, (_, i) => from + i);
}

async function main(): Promise<void> {
  const seedRaw: unknown = JSON.parse(readFileSync(paths.seed, 'utf8'));
  const seedErrors = validateSeed(seedRaw);
  if (seedErrors.length > 0) {
    console.error(seedErrors.join('\n'));
    process.exit(1);
  }
  const seed = seedRaw as SeedCity[];

  const years = parseYears(arg('years') ?? '2016-2025');
  const only = arg('only')?.split(',');
  const offline = flag('offline');
  const delayMs = Number(arg('delay-ms') ?? 300);
  const targets = only ? seed.filter((c) => only.includes(c.id)) : seed;
  if (only && targets.length !== only.length) {
    throw new Error(`--only names an unknown city: ${only.join(',')}`);
  }

  const total = targets.length * years.length;
  const maxWaitSec = Number(arg('max-wait-hours') ?? 0) * 3600;
  let have = 0;
  let fetched = 0;
  let missing: string[] = [];
  const responses = new Map<string, ApiResponse>();

  /** One pass over every city-year. Returns the rate-limit error that stopped it, if any. */
  const collect = async (): Promise<RateLimitError | undefined> => {
    have = 0;
    missing = [];
    for (const city of targets) {
      for (const year of years) {
        const key = `${city.id}/${String(year)}`;
        if (offline) {
          // Cache only: never touches the network.
          const cached = readCache(paths.cache, city.id, year);
          if (cached) {
            responses.set(key, cached);
            have += 1;
          } else {
            missing.push(key);
          }
          continue;
        }
        try {
          const { data, fromCache } = await getCityYear(city, year, { cacheDir: paths.cache, log });
          responses.set(key, data);
          have += 1;
          if (!fromCache) {
            fetched += 1;
            log(`fetched ${key} (${String(have)}/${String(total)})`);
            await new Promise((r) => setTimeout(r, delayMs));
          }
        } catch (err) {
          if (err instanceof RateLimitError) return err;
          throw err;
        }
      }
    }
    return undefined;
  };

  let stoppedBy: RateLimitError | undefined;
  for (;;) {
    stoppedBy = await collect();
    const wait = stoppedBy?.retryAfterSec;
    if (stoppedBy && wait !== undefined && wait <= maxWaitSec) {
      log(
        `${stoppedBy.kind} limit reached with ${String(have)}/${String(total)} cached; ` +
          `waiting ${(wait / 3600).toFixed(2)} h for the reset.`,
      );
      await new Promise((r) => setTimeout(r, (wait + 30) * 1000));
      continue;
    }
    break;
  }

  if (stoppedBy) {
    const hours = stoppedBy.retryAfterSec
      ? ` Try again in about ${(stoppedBy.retryAfterSec / 3600).toFixed(1)} h.`
      : '';
    console.error(
      `\nStopped by the ${stoppedBy.kind} rate limit after ${String(fetched)} new request(s): ${stoppedBy.message.replace(/\.$/, '')}.${hours}`,
    );
    console.error(`${String(have)} of ${String(total)} city-years are cached. Re-run to continue.`);
    process.exit(EXIT_TEMPFAIL);
  }
  if (missing.length > 0 || have < total) {
    console.error(`\n${String(total - have)} city-year(s) are not cached; run without --offline.`);
    process.exit(EXIT_TEMPFAIL);
  }
  log(`\nAll ${String(total)} city-years available (${String(fetched)} fetched this run).`);

  if (only) {
    log('--only given: cache filled, no output written.');
    return;
  }

  // Classify.
  const cities: Record<string, CityDays> = {};
  const meta: Record<string, GridMeta> = {};
  let cloudMissing = 0;
  for (const city of seed) {
    const parsed: ParsedYear[] = years.map((year) => {
      const resp = responses.get(`${city.id}/${String(year)}`);
      if (!resp) throw new Error(`${city.id} ${String(year)}: not loaded`);
      return parseYear(resp, year, `${city.id} ${String(year)}`);
    });
    cloudMissing += parsed.reduce((a, p) => a + p.cloudMissing, 0);
    cities[city.id] = combineYears(parsed);
    const first = responses.get(`${city.id}/${String(years[0])}`);
    if (first) {
      meta[city.id] = {
        gridLat: first.latitude,
        gridLon: first.longitude,
        elevation: first.elevation,
      };
    }
  }
  if (cloudMissing > 0) {
    log(
      `Note: cloud cover was missing on ${String(cloudMissing)} day(s); the cloud condition was skipped for them.`,
    );
  }

  const world = buildWorld(seed, cities, years);
  const worldJson = JSON.stringify(world);
  const gz = gzipSync(worldJson, { level: 9 });

  mkdirSync(join(root, 'public/data'), { recursive: true });
  mkdirSync(join(root, 'src/data'), { recursive: true });
  mkdirSync(join(root, 'docs'), { recursive: true });
  writeFileSync(paths.world, worldJson + '\n');
  writeFileSync(paths.index, JSON.stringify(seed, null, 2) + '\n');

  const input = {
    seed,
    world,
    meta,
    rawBytes: Buffer.byteLength(worldJson),
    gzBytes: gz.length,
    generated: new Date().toISOString().slice(0, 10),
  };
  writeFileSync(paths.report, renderReport(input));

  const errors = [
    ...validateWorld(world, seed),
    ...validateIndex(JSON.parse(readFileSync(paths.index, 'utf8')), seed),
  ];
  const flags = findFlags(input);
  const unexplained = flags.filter((f) => f.explained === undefined);

  log(`world.v1.json: ${String(input.rawBytes)} bytes raw, ${String(input.gzBytes)} gzipped`);
  log(
    `Report written to docs/data-report.md. Flags: ${String(flags.length)} (${String(unexplained.length)} unexplained).`,
  );
  for (const f of unexplained) log(`  ${f.id}: ${f.rule}`);
  if (errors.length > 0) {
    console.error('Validation failed:\n' + errors.slice(0, 20).join('\n'));
    process.exit(1);
  }
  if (!existsSync(paths.world)) throw new Error('world file was not written');
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
