// Applies the visual settings to <html>. The CSS reads these attributes (see tokens.css, grid.css).

export type ThemeSetting = 'system' | 'light' | 'dark';
export type PatternSetting = 'auto' | 'on' | 'off';
export type MotionSetting = 'system' | 'reduce' | 'full';

export interface VisualSettings {
  theme: ThemeSetting;
  pattern: PatternSetting;
  motion: MotionSetting;
}

export const DEFAULT_VISUAL_SETTINGS: VisualSettings = {
  theme: 'system',
  pattern: 'auto',
  motion: 'system',
};

function setOrClear(el: HTMLElement, attribute: string, value: string | undefined): void {
  if (value === undefined) el.removeAttribute(attribute);
  else el.setAttribute(attribute, value);
}

export function applyVisualSettings(
  s: Partial<VisualSettings>,
  root = document.documentElement,
): void {
  if (s.theme !== undefined)
    setOrClear(root, 'data-theme', s.theme === 'system' ? undefined : s.theme);
  if (s.pattern !== undefined)
    setOrClear(root, 'data-pattern', s.pattern === 'auto' ? undefined : s.pattern);
  if (s.motion !== undefined)
    setOrClear(root, 'data-motion', s.motion === 'system' ? undefined : s.motion);
}

/** True when loss tiles should carry patterns: the setting, or the system asking for more contrast. */
export function isPatternMode(root = document.documentElement): boolean {
  const v = root.dataset['pattern'];
  if (v === 'on') return true;
  if (v === 'off') return false;
  return window.matchMedia('(prefers-contrast: more)').matches;
}

/** True when animation should be skipped: the in-app override, or the system setting. */
export function isReducedMotion(root = document.documentElement): boolean {
  const v = root.dataset['motion'];
  if (v === 'reduce') return true;
  if (v === 'full') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
