// Sharing a finished run. The text message is built by the engine (SPEC 6.8); the Web Share API is
// used where available, otherwise the text goes to the clipboard.
import { buildShareText } from '../engine/share.ts';
import type { Session } from './session.ts';
import type { App } from './app.ts';
import type { MessageKey } from '../i18n/index.ts';

/** Public address of the game. */
export const GAME_URL = 'https://meteorec.si/365-0/';

export type ShareOutcome = 'shared' | 'copied' | 'failed';

export function shareText(app: App, session: Session): string {
  const result = session.state.result;
  if (!result) throw new Error('no result to share');
  const { t } = app.i18n;
  return buildShareText(result, {
    title: t('app.title'),
    modeLabel: t(`mode.${session.mode}` as MessageKey),
    recordLabel: t('result.recordLabel'),
    gradeTitle: t(`grade.${result.grade}` as MessageKey),
    ...(session.mode === 'daily' && session.date !== undefined ? { date: session.date } : {}),
    url: GAME_URL,
  });
}

export async function shareResult(app: App, session: Session): Promise<ShareOutcome> {
  const text = shareText(app, session);
  try {
    if (typeof navigator.share === 'function') {
      await navigator.share({ text });
      return 'shared';
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return 'failed';
  }
  try {
    await navigator.clipboard.writeText(text);
    return 'copied';
  } catch {
    return 'failed';
  }
}
