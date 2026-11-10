// Sharing a finished run: a text message and an image (SPEC 6.8). The Web Share API is used with the
// image where the browser can share files; otherwise the text is copied and the image is offered as a
// download.
import { shareImageModel, buildShareText } from '../engine/share.ts';
import { chaseKey, gradeKey } from './chase-text.ts';
import type { MessageKey } from '../i18n/index.ts';
import { canvasToBlob, renderShareImage, type ShareFormat } from '../ui/canvas/shareImage.ts';
import { isPatternMode } from '../ui/settings.ts';
import type { App } from './app.ts';
import { cities } from './data.ts';
import type { Session } from './session.ts';
import { contractProgress } from './contracts.ts';

/** Public address of the game. */
export const GAME_URL = 'https://meteorec.si/365-0/';

export type ShareOutcome = 'shared' | 'copied' | 'downloaded' | 'failed';

/** "Daily", or "Daily · Snow and frost" when the run chased something other than sunshine. */
function modeLabel(app: App, session: Session): string {
  const { t } = app.i18n;
  const mode = t(`mode.${session.mode}` as MessageKey);
  return session.chase === 'sun'
    ? mode
    : t('mode.chase', { mode, name: t(chaseKey(session.chase, 'name')) });
}

function contractShareLines(app: App, session: Session): {
  text: string;
  badge: string;
} {
  const result = session.state.result;
  if (!result) throw new Error('no result to share');
  const { t } = app.i18n;
  const objective = contractProgress(session.contract, result.rounds, result.bestRecord, true);
  const name = t(`contract.${session.contract}.name` as MessageKey);
  const progress = t(`contract.${session.contract}.progress` as MessageKey, {
    current: objective.current,
    target: objective.target,
    months: objective.months,
  });
  const status = t(objective.passed ? 'share.contractStatus.pass' : 'share.contractStatus.miss');
  return {
    text: t('share.contractLine', { name, progress, status }),
    badge: t('share.contractBadge', { name, status }),
  };
}

export function shareText(app: App, session: Session): string {
  const result = session.state.result;
  if (!result) throw new Error('no result to share');
  const { t } = app.i18n;
  const contract = contractShareLines(app, session);
  return buildShareText(result, {
    title: t('app.title'),
    modeLabel: modeLabel(app, session),
    recordLabel: t('result.recordLabel'),
    gradeTitle: t(gradeKey(session.chase, result.grade)),
    ...(session.mode === 'daily' && session.date !== undefined ? { date: session.date } : {}),
    contractLine: contract.text,
    challengeLine: t(
      session.mode === 'daily' ? 'share.challenge.daily' : 'share.challenge.endless',
    ),
    url: GAME_URL,
  });
}

export function imageFileName(session: Session, format: ShareFormat): string {
  const day = session.mode === 'daily' && session.date !== undefined ? session.date : 'endless';
  return `365-0-${day}${format === 'story' ? '-story' : ''}.png`;
}

/** Render the share image for a finished session. */
export async function createShareImage(
  app: App,
  session: Session,
  format: ShareFormat,
): Promise<Blob> {
  const result = session.state.result;
  if (!result) throw new Error('no result to share');
  const { t } = app.i18n;
  const contract = contractShareLines(app, session);
  const model = shareImageModel(result, {
    mode: session.mode,
    ...(session.date !== undefined ? { date: session.date } : {}),
  });
  const daily = session.mode === 'daily';
  const canvas = await renderShareImage(
    model,
    {
      title: t('app.title'),
      subtitle: [modeLabel(app, session), daily ? session.date : undefined]
        .filter(Boolean)
        .join(' '),
      gradeTitle: t(gradeKey(session.chase, result.grade)),
      bestLine: t(daily ? 'share.bestToday' : 'share.bestRun', { n: result.bestRecord.w }),
      contractLine: contract.badge,
      youLine: t('result.yours', { n: result.record.w }),
      abbreviations: result.rounds.map((r) => {
        const city = cities.find((c) => c.id === r.cityId);
        return city ? app.fmt.abbreviation(city) : '';
      }),
      url: GAME_URL.replace(/^https:\/\//, ''),
    },
    format,
    isPatternMode(),
  );
  return canvasToBlob(canvas);
}

function download(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 10000);
}

export async function shareResult(
  app: App,
  session: Session,
  format: ShareFormat = 'feed',
): Promise<ShareOutcome> {
  const text = shareText(app, session);
  let blob: Blob | undefined;
  try {
    blob = await createShareImage(app, session, format);
  } catch {
    blob = undefined;
  }

  // 1. The share sheet, with the image where files can be shared.
  try {
    if (typeof navigator.share === 'function') {
      const file = blob
        ? new File([blob], imageFileName(session, format), { type: 'image/png' })
        : undefined;
      if (
        file &&
        typeof navigator.canShare === 'function' &&
        navigator.canShare({ files: [file] })
      ) {
        await navigator.share({ files: [file], text });
      } else {
        await navigator.share({ text });
      }
      return 'shared';
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return 'failed';
  }

  // 2. No share sheet: copy the text and offer the image as a download.
  let copied: boolean;
  try {
    await navigator.clipboard.writeText(text);
    copied = true;
  } catch {
    copied = false;
  }
  if (blob) {
    download(blob, imageFileName(session, format));
    return copied ? 'downloaded' : 'failed';
  }
  return copied ? 'copied' : 'failed';
}

/** Share the daily mystery as text: the share sheet where there is one, otherwise the clipboard. */
export async function shareMystery(
  app: App,
  date: string,
  pointsEarned: number,
  max: number,
): Promise<ShareOutcome> {
  const { t } = app.i18n;
  const text = t('mystery.shareText', {
    date: app.fmt.date(date),
    n: pointsEarned,
    max,
    url: GAME_URL,
  });
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
