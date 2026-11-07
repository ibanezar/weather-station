// Seeded random numbers (SPEC 3). Everything random in the game goes through here.

/** xmur3: string hash that yields a stream of 32-bit seeds. */
export function xmur3(str: string): () => number {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return h >>> 0;
  };
}

/** sfc32: small fast generator; returns floats in [0, 1). */
export function sfc32(a: number, b: number, c: number, d: number): () => number {
  return () => {
    a >>>= 0;
    b >>>= 0;
    c >>>= 0;
    d >>>= 0;
    let t = (a + b) | 0;
    a = b ^ (b >>> 9);
    b = (c + (c << 3)) | 0;
    c = (c << 21) | (c >>> 11);
    d = (d + 1) | 0;
    t = (t + d) | 0;
    c = (c + t) | 0;
    return (t >>> 0) / 4294967296;
  };
}

export type Rng = () => number;

/** Separator that cannot appear in a seed part, so ('ab','c') and ('a','bc') differ. */
const SEP = '\u001f';

/**
 * Independent generator for the given parts, e.g. makeRng(seed, 'year', round, cityId). The same
 * parts always give the same stream, and different parts give unrelated streams.
 */
export function makeRng(...parts: (string | number)[]): Rng {
  const seed = xmur3(parts.map(String).join(SEP));
  const rng = sfc32(seed(), seed(), seed(), seed());
  for (let i = 0; i < 12; i++) rng(); // warm up
  return rng;
}

/** Integer in [0, n). */
export function randInt(rng: Rng, n: number): number {
  return Math.floor(rng() * n);
}

/** Fisher-Yates shuffle; returns a new array. */
export function shuffle<T>(items: readonly T[], rng: Rng): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = randInt(rng, i + 1);
    const a = out[i] as T;
    out[i] = out[j] as T;
    out[j] = a;
  }
  return out;
}
