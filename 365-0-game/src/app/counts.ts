// Anonymous play counts. When a game starts or finishes the game tells the meteorec.si server which chase it
// was, whether it was a daily or an endless run and, at the end, the grade. There is no identifier, no
// account and no record of who sent it; the server keeps only totals. It can be switched off in Settings,
// and it never runs outside the live site (development, tests and previews send nothing).
import type { ChaseId } from '../engine/chase.ts';
import type { GradeId } from '../engine/grades.ts';

export const COUNTS_URL = 'https://weatherireica1.filip-eremita.workers.dev/365-0/stat';

export interface CountEvent {
  ev: 'start' | 'finish';
  mode: 'daily' | 'endless';
  chase: ChaseId;
  /** Only on a finish. */
  grade?: GradeId;
  /** Only on a finish: how many second chances were used. */
  rerolls?: number;
}

export type CountSender = (url: string, body: string) => void;

/** True only on the live site: counts from a development server or a test run would pollute the totals. */
export function isLiveSite(hostname: string): boolean {
  return hostname === 'meteorec.si' || hostname === 'www.meteorec.si';
}

const browserSender: CountSender = (url, body) => {
  if (!isLiveSite(location.hostname) || !navigator.onLine) return;
  // text/plain keeps this a "simple" request: no preflight, and keepalive lets it finish when the page closes.
  void fetch(url, {
    method: 'POST',
    body,
    keepalive: true,
    credentials: 'omit',
    headers: { 'Content-Type': 'text/plain' },
  }).catch(() => {
    // A count is never worth an error: offline or blocked, the game goes on.
  });
};

export function sendCount(
  enabled: boolean,
  event: CountEvent,
  send: CountSender = browserSender,
): void {
  if (!enabled) return;
  try {
    send(COUNTS_URL, JSON.stringify(event));
  } catch {
    // ignore
  }
}
