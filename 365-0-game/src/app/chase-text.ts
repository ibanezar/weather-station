// Words and swatches for a chase (what the player is chasing): the texts live in the i18n catalogs under
// chase.<id>.*, the grade names under grade.<id>.* for the sunny game and grade.<chase>.<id> for the others.
import { CHASES, DEFAULT_CHASE, type ChaseId } from '../engine/chase.ts';
import type { GradeId } from '../engine/grades.ts';
import { DAY_TYPE_CHARS, type DayType } from '../engine/thresholds.ts';
import type { MessageKey } from '../i18n/index.ts';
import type { IconName } from '../ui/icons/index.ts';

/** The day-type icon that stands for each chase. */
export const CHASE_ICON: Record<ChaseId, IconName> = {
  sun: 'perfect',
  snow: 'freeze',
  rain: 'rain',
  storm: 'storm',
  heat: 'heat',
};

export function chaseKey(chase: ChaseId, key: string): MessageKey {
  return `chase.${chase}.${key}` as MessageKey;
}

export function gradeKey(chase: ChaseId, grade: GradeId): MessageKey {
  return (chase === DEFAULT_CHASE ? `grade.${grade}` : `grade.${chase}.${grade}`) as MessageKey;
}

/** Day types that are neither a win nor a loss in a chase. */
export function drawTypes(chase: ChaseId): DayType[] {
  const def = CHASES[chase];
  return DAY_TYPE_CHARS.filter((t) => !def.win.includes(t) && !def.loss.includes(t));
}

/** The swatches of the Win, Draw and Loss chips: the day types each one stands for. */
export function chaseSwatches(chase: ChaseId): {
  win: DayType[];
  draw: DayType[];
  loss: DayType[];
} {
  const def = CHASES[chase];
  return { win: [...def.win], draw: drawTypes(chase), loss: [...def.loss] };
}
