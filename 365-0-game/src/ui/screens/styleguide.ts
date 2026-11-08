// /styleguide: every token and component in one place, for light and dark, pattern mode and
// narrow widths. A developer page: it is not linked from the app and its labels are not translated.
import cities from '../../data/cities.index.json';
import type { SeedCity } from '../../data/types.ts';
import { makeRng } from '../../engine/rng.ts';
import { DAY_TYPE_CHARS, type DayType } from '../../engine/thresholds.ts';
import { drawGrid, resolvePalette, type GridColumn } from '../canvas/grid.ts';
import { button } from '../components/button.ts';
import { chip, swatch } from '../components/chip.ts';
import { cityCard } from '../components/cityCard.ts';
import { progress } from '../components/progress.ts';
import { showToast } from '../components/toast.ts';
import { h, mount } from '../dom.ts';
import { ARCHETYPE_ICONS, DAY_ICONS, icon, ICONS, type IconName } from '../icons/index.ts';
import {
  applyVisualSettings,
  DEFAULT_VISUAL_SETTINGS,
  isPatternMode,
  type VisualSettings,
} from '../settings.ts';

const index = cities as SeedCity[];
const countries = new Intl.DisplayNames(['en'], { type: 'region' });
const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

const DAY_NAMES: Record<DayType, string> = {
  p: 'perfect',
  o: 'ok',
  r: 'rain',
  s: 'storm',
  h: 'heat',
  f: 'freeze',
};

/** A believable year for the specimen grid. */
function sampleYear(): GridColumn[] {
  const rng = makeRng('styleguide');
  return DAYS_IN_MONTH.map((n, m) => {
    const warm = Math.sin(((m - 3) / 12) * Math.PI * 2) * 0.5 + 0.5;
    const days = Array.from({ length: n }, (): DayType => {
      const x = rng();
      if (x < 0.1 + warm * 0.22) return 'p';
      if (x < 0.5) return 'o';
      if (x < 0.72) return 'r';
      if (x < 0.78) return 's';
      if (x < 0.78 + warm * 0.06) return 'h';
      return m < 3 || m > 9 ? 'f' : 'o';
    });
    return { days };
  });
}

function section(title: string, ...children: (Node | string)[]): HTMLElement {
  return h('section', { class: 'sg-section' }, h('h2', null, title), ...children);
}

function swatchRow(name: string, cssVar: string): HTMLElement {
  return h(
    'li',
    { class: 'sg-token' },
    h('span', { class: 'sg-token__chip', style: `background:var(${cssVar})` }),
    h('code', null, name),
  );
}

function segmented<T extends string>(
  label: string,
  options: readonly T[],
  current: T,
  onChange: (value: T) => void,
): HTMLElement {
  const buttons = options.map((value) =>
    h(
      'button',
      { type: 'button', class: 'sg-seg__btn', 'aria-pressed': String(value === current) },
      value,
    ),
  );
  buttons.forEach((b, i) => {
    b.addEventListener('click', () => {
      for (const other of buttons) other.setAttribute('aria-pressed', String(other === b));
      onChange(options[i] as T);
    });
  });
  const group = h('div', { class: 'sg-seg', role: 'group', 'aria-label': label }, ...buttons);
  return h('div', { class: 'sg-control' }, h('span', { class: 'sg-control__label' }, label), group);
}

function sampleCards(): HTMLElement[] {
  const wanted = ['reykjavik', 'singapore', 'phoenix'];
  return wanted.map((id, i) => {
    const c = index.find((x) => x.id === id) as SeedCity;
    const temps = [11, 28, 41];
    const card = cityCard({
      name: c.name.en,
      country: countries.of(c.country) ?? c.country,
      temperature: `${String(temps[i])}°`,
      archetype: c.archetype,
      archetypeLabel: c.archetype,
      pickAction: 'Pick this city',
      scoutLabel: 'Scout',
      scoutFullLabel: `Scout ${c.name.en}`,
      scoutedLabel: 'Scouted',
      winLabel: 'Perfect days',
      lossLabel: 'Bad days',
      stepText: (b) => `${String(b + 1)} of 5`,
      onPick: () =>
        showToast({ message: `Picked ${c.name.en}`, actionLabel: 'Undo', durationMs: 2000 }),
      onScout: () => {
        card.showScout({ win: [1, 0, 4][i] as number, loss: [2, 4, 0][i] as number });
      },
    });
    return card.el;
  });
}

export function renderStyleguide(root: HTMLElement): void {
  const settings: VisualSettings = { ...DEFAULT_VISUAL_SETTINGS };
  const columns = sampleYear();
  const canvas = h('canvas', {
    role: 'img',
    'aria-label': 'Sample year: twelve months of daily weather tiles',
  });
  const reveal = h('input', {
    type: 'range',
    min: '0',
    max: '365',
    value: '365',
    id: 'sg-reveal',
    class: 'sg-range',
  });
  const wellEl = h('div', { class: 'well grid-panel' });

  const redraw = (): void => {
    drawGrid(canvas, columns, resolvePalette(wellEl), {
      pattern: isPatternMode(),
      revealed: Number(reveal.value),
    });
  };
  reveal.addEventListener('input', redraw);
  new ResizeObserver(redraw).observe(wellEl);

  const set = (patch: Partial<VisualSettings>): void => {
    Object.assign(settings, patch);
    applyVisualSettings(patch);
    requestAnimationFrame(redraw);
  };

  const prog = progress({
    total: 12,
    roundText: (c, t) => `Round ${String(c)} of ${String(t)}`,
    chancesText: (n) => `${String(n)} second chances`,
    scoutsText: (n) => `${String(n)} scouts left`,
  });
  prog.update(3, 2, 1);

  const frames = h(
    'div',
    { class: 'sg-frames' },
    ...[360, 430].map((w) =>
      h(
        'div',
        { class: 'sg-frame', style: `width:${String(w)}px` },
        h('p', { class: 'sg-frame__title muted' }, `${String(w)} px wide`),
        h('div', { class: 'sg-stack' }, ...sampleCards()),
      ),
    ),
  );

  const labels = h(
    'div',
    { class: 'grid-panel__labels', 'aria-hidden': 'true' },
    ...MONTHS.map((m) => h('span', null, m)),
  );
  wellEl.append(labels, canvas);

  mount(
    root,
    h(
      'header',
      { class: 'sg-header' },
      h('h1', null, 'Styleguide'),
      h('p', { class: 'muted' }, 'Tokens and components. Use the controls to check every mode.'),
      h(
        'div',
        { class: 'sg-controls' },
        segmented('Theme', ['system', 'light', 'dark'] as const, 'system', (theme) => {
          set({ theme });
        }),
        segmented('Patterns', ['auto', 'on', 'off'] as const, 'auto', (pattern) => {
          set({ pattern });
        }),
        segmented('Motion', ['system', 'reduce', 'full'] as const, 'system', (motion) => {
          set({ motion });
        }),
      ),
    ),
    section(
      'Colour',
      h(
        'ul',
        { class: 'sg-tokens' },
        swatchRow('surface', '--surface'),
        swatchRow('raised', '--raised'),
        swatchRow('ink', '--ink'),
        swatchRow('ink-muted', '--ink-muted'),
        swatchRow('well', '--well'),
        swatchRow('accent', '--accent'),
      ),
      h(
        'ul',
        { class: 'sg-tokens sg-tokens--day well' },
        ...DAY_TYPE_CHARS.map((t) =>
          h(
            'li',
            { class: 'sg-token' },
            h('span', {
              class: `sg-token__chip day-${t}`,
              style: 'background-color:var(--day);background-image:var(--pat,none)',
            }),
            h('code', null, DAY_NAMES[t]),
          ),
        ),
      ),
    ),
    section(
      'Type',
      h('p', { class: 'sg-record num' }, '214-91-60'),
      h('h1', null, 'Display 44'),
      h('h2', null, 'Heading 28'),
      h('h3', null, 'Title 20'),
      h('p', null, 'Body 17. A clear, friendly grotesque for everything that is not a number.'),
      h('p', { class: 'muted', style: 'font-size:var(--text-small)' }, 'Small 15, muted.'),
      h('p', { class: 'muted', style: 'font-size:var(--text-caption)' }, 'Caption 13, muted.'),
    ),
    section(
      'Icons',
      h('p', { class: 'muted' }, 'Day types'),
      h('ul', { class: 'sg-icons' }, ...DAY_ICONS.map((n) => iconCell(n))),
      h('p', { class: 'muted' }, 'Climate archetypes'),
      h('ul', { class: 'sg-icons' }, ...ARCHETYPE_ICONS.map((n) => iconCell(n))),
      h('p', { class: 'muted' }, 'Interface'),
      h(
        'ul',
        { class: 'sg-icons' },
        ...(Object.keys(ICONS) as IconName[])
          .filter(
            (n) =>
              !(DAY_ICONS as readonly string[]).includes(n) &&
              !(ARCHETYPE_ICONS as readonly string[]).includes(n),
          )
          .map((n) => iconCell(n)),
      ),
    ),
    section(
      'Buttons and chips',
      h(
        'div',
        { class: 'sg-stack' },
        button({ label: 'Play daily', variant: 'primary', full: true }),
        button({ label: 'Play endless', variant: 'secondary', full: true }),
        button({ label: 'How it works', variant: 'quiet' }),
        button({ label: 'Share result', variant: 'primary', icon: 'share' }),
        button({ label: 'Disabled', disabled: true }),
      ),
      h(
        'div',
        { class: 'legend' },
        chip({ label: 'Win', swatch: 'p' }),
        chip({ label: 'Draw', swatch: 'o' }),
        chip({ label: 'Loss', swatch: 'loss' }),
        chip({ label: 'Heatwave: hot places run hotter', tone: 'event', icon: 'heat' }),
        chip({ label: '5-day streak', icon: 'streak' }),
      ),
    ),
    section('Progress', prog.el),
    section('City cards', h('p', { class: 'muted' }, 'Tap Scout to flip a card.'), frames),
    section(
      'Year grid',
      wellEl,
      h(
        'div',
        { class: 'legend sg-legend' },
        ...DAY_TYPE_CHARS.map((t) =>
          h('span', { class: 'chip' }, swatch(t), h('span', null, DAY_NAMES[t])),
        ),
      ),
      h('label', { for: 'sg-reveal', class: 'muted' }, 'Tiles revealed'),
      reveal,
    ),
    section(
      'Toast',
      button({
        label: 'Show undo toast',
        icon: 'undo',
        onClick: () => showToast({ message: 'Picked Reykjavik', actionLabel: 'Undo' }),
      }),
    ),
  );
  requestAnimationFrame(redraw);
}

function iconCell(name: IconName): HTMLElement {
  return h(
    'li',
    { class: 'sg-icon' },
    icon(name, { label: name, size: 32 }),
    h('code', null, name),
  );
}
