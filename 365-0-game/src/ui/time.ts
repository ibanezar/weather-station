/**
 * Read a CSS time such as "200ms", ".2s" or "0s" as milliseconds. The build minifies "200ms" to ".2s",
 * so the unit has to be read, not assumed. Returns 0 for anything that is not a time.
 */
export function cssTimeToMs(raw: string): number {
  const text = raw.trim().toLowerCase();
  const n = parseFloat(text);
  if (!Number.isFinite(n)) return 0;
  if (text.endsWith('ms')) return n;
  if (text.endsWith('s')) return n * 1000;
  return 0;
}
