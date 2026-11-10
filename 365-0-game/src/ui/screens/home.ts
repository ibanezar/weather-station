import { activeStreak, localDate } from '../../app/dates.ts';
import type { App } from '../../app/app.ts';
import { loadEngineData, prefetchWorld } from '../../app/data.ts';
import { installMode, onInstallChange, promptInstall } from '../../app/install.ts';
import { newSession, randomEntropy, restoreSession } from '../../app/session.ts';
import { dailySeed } from '../../engine/run.ts';
import { CHASE_IDS, type ChaseId } from '../../engine/chase.ts';
import { CHASE_ICON, chaseKey } from '../../app/chase-text.ts';
import { dailyKey } from '../../app/storage.ts';
import {
  CONTRACT_IDS,
  DEFAULT_CONTRACT,
  isContractId,
  type ContractId,
} from '../../app/contracts.ts';
import { icon } from '../icons/index.ts';
import { button } from '../components/button.ts';
import { chip } from '../components/chip.ts';
import type { MessageKey } from '../../i18n/index.ts';
import { h, mount } from '../dom.ts';
import { THRESHOLDS } from '../../engine/thresholds.ts';
import { cities } from '../../app/data.ts';
import { logoMark } from '../components/logo.ts';

/** Start (or reopen) a run. Shows the load error with a retry when the weather data cannot load. */
export async function startRun(
  app: App,
  mode: 'daily' | 'endless',
  ui: { btn: HTMLButtonElement; message: HTMLElement },
): Promise<void> {
  const { t } = app.i18n;
  const today = localDate();
  const chase = app.store.state.settings.chase;
  const contract = app.store.state.settings.contract ?? DEFAULT_CONTRACT;
  ui.btn.disabled = true;
  ui.message.textContent = '';
  app.store.update((st) => {
    st.onboarded = true;
  });
  try {
    const data = await loadEngineData();
    if (mode === 'daily') {
      const done = app.store.state.daily[dailyKey(today, chase)];
      if (done) {
        app.session = restoreSession(
          'daily',
          data,
          dailySeed(today, chase),
          today,
          done.picks,
          done.rerolls ?? [],
          chase,
          done.contract ?? DEFAULT_CONTRACT,
        );
        app.go('result');
        return;
      }
    }
    app.session = newSession(mode, data, {
      date: today,
      entropy: randomEntropy(),
      chase,
      contract,
    });
    app.count({ ev: 'start', mode, chase });
    app.go('draft');
  } catch {
    ui.message.textContent = `${t('error.world')} `;
    ui.message.append(
      button({
        label: t('error.retry'),
        variant: 'secondary',
        onClick: () => void startRun(app, mode, ui),
      }),
    );
    ui.btn.disabled = false;
  }
}

export function renderHome(app: App, root: HTMLElement): void {
  const { t, plural } = app.i18n;
  const today = localDate();
  const streak = activeStreak(app.store.state.streak, today);
  const message = h('p', { class: 'screen__error', role: 'alert' });
  let chase: ChaseId = app.store.state.settings.chase;
  let contract: ContractId = app.store.state.settings.contract ?? DEFAULT_CONTRACT;
  const range = app.fmt.range(THRESHOLDS.perfect.tmaxCMin, THRESHOLDS.perfect.tmaxCMax);

  const dailyBtn = button({
    label: t('home.playDaily'),
    variant: 'primary',
    full: true,
    onClick: () => void startRun(app, 'daily', { btn: dailyBtn, message }),
  });
  const endlessBtn = button({
    label: t('home.playEndless'),
    variant: 'secondary',
    full: true,
    onClick: () => void startRun(app, 'endless', { btn: endlessBtn, message }),
  });

  const mysteryDone = app.store.state.mystery[today]?.done === true;
  const mysteryBtn = button({
    label: mysteryDone ? t('home.mysterySee') : t('home.mystery'),
    variant: 'secondary',
    icon: 'pin',
    full: true,
    onClick: () => {
      app.store.update((st) => {
        st.onboarded = true;
      });
      app.go('mystery');
    },
  });

  // Install: the browser's own dialog where it offers one, the Share-menu steps on iPhone, nothing otherwise.
  const installSlot = h('div', { class: 'home__install' });
  const drawInstall = (): void => {
    const mode = installMode();
    if (mode === 'none') {
      installSlot.replaceChildren();
      return;
    }
    const hint = h('p', { class: 'muted home__install-hint', role: 'status' });
    const installBtn = button({
      label: t('home.install'),
      variant: 'secondary',
      icon: 'install',
      full: true,
      onClick: () => {
        if (mode === 'prompt') void promptInstall();
        else hint.textContent = t('home.installIos');
      },
    });
    installSlot.replaceChildren(installBtn, hint);
  };
  drawInstall();

  const step3Title = h('strong', { class: 'home__step-title' });
  const stepTitle = (n: number): HTMLElement =>
    n === 3
      ? step3Title
      : h('strong', { class: 'home__step-title' }, t(`home.step${String(n)}.title` as MessageKey));
  const steps = [1, 2, 3].map((n) =>
    h(
      'li',
      { class: 'home__step' },
      h('span', { class: 'home__num num', 'aria-hidden': 'true' }, String(n)),
      h(
        'div',
        null,
        stepTitle(n),
        h('p', { class: 'muted home__step-text' }, t(`home.step${String(n)}.text` as MessageKey)),
      ),
    ),
  );

  // What to chase: sunshine, snow, rain, storms or heat. Native radio buttons, so the keyboard works for free.
  const chaseNote = h('p', { class: 'muted home__chase-note', 'aria-live': 'polite' });
  const chaseRules = h('p', { class: 'muted home__chase-rules', 'aria-live': 'polite' });
  const bestSlot = h('p', { class: 'muted num home__best' });
  const dailyNote = h('p', { class: 'muted home__daily num' });
  const applyChase = (): void => {
    const done = app.store.state.daily[dailyKey(today, chase)] !== undefined;
    dailyBtn
      .querySelector('span')
      ?.replaceChildren(done ? t('home.seeResult') : t('home.playDaily'));
    chaseNote.textContent = t(chaseKey(chase, 'short'), { range });
    chaseRules.textContent = t(chaseKey(chase, 'rules'));
    step3Title.textContent = t(chaseKey(chase, 'step3'));
    const best = app.store.state.bestEndless[chase];
    bestSlot.textContent = best ? t('home.bestEndless', { record: app.fmt.record(best) }) : '';
    dailyNote.textContent = `${t('home.dailyCaption')}${streak >= 2 ? ` · ${plural('home.streak', streak)}` : ''}`;
  };
  const contractSummary = h('summary', { class: 'contract-picker__summary' });
  const contractDescription = h('p', { class: 'contract-picker__description muted' });
  const contractSelect = h(
    'select',
    {
      class: 'contract-picker__select',
      'aria-label': t('contract.title'),
      onChange: (event: Event) => {
        const selected = (event.currentTarget as HTMLSelectElement).value;
        if (!isContractId(selected)) return;
        contract = selected;
        app.store.update((st) => {
          st.settings.contract = selected;
        });
        contractSummary.textContent = t('contract.selected', {
          name: t(`contract.${selected}.name` as MessageKey),
        });
        contractDescription.textContent = t(`contract.${selected}.description` as MessageKey);
      },
    },
    ...CONTRACT_IDS.map((id) =>
      h(
        'option',
        { value: id, selected: id === contract },
        t(`contract.${id}.name` as MessageKey),
      ),
    ),
  );
  const currentContractName = t(`contract.${contract}.name` as MessageKey);
  contractSummary.textContent = t('contract.selected', { name: currentContractName });
  contractDescription.textContent = t(`contract.${contract}.description` as MessageKey);
  const contractPicker = h(
    'section',
    { class: 'contract-picker', 'aria-label': t('contract.title') },
    h('details', { class: 'contract-picker__details' }, contractSummary, contractSelect),
    contractDescription,
  );

  const picker = h(
    'fieldset',
    { class: 'chase-picker' },
    h('legend', { class: 'chase-picker__legend' }, t('chase.title')),
    h(
      'div',
      { class: 'chase-picker__options' },
      ...CHASE_IDS.map((id) => {
        const input = h('input', {
          type: 'radio',
          name: 'chase',
          value: id,
          class: 'chase-opt__input',
          checked: id === chase,
          onChange: () => {
            chase = id;
            document.documentElement.dataset['chase'] = id;
            app.store.update((st) => {
              st.settings.chase = id;
            });
            applyChase();
          },
        });
        return h(
          'label',
          { class: 'chase-opt' },
          input,
          h(
            'span',
            { class: 'chase-opt__box' },
            icon(CHASE_ICON[id], { size: 26 }),
            h('span', { class: 'chase-opt__name' }, t(chaseKey(id, 'pick'))),
          ),
        );
      }),
    ),
    chaseNote,
    chaseRules,
  );

  mount(
    root,
    h(
      'main',
      { class: 'screen screen--home' },
      h(
        'header',
        { class: 'home__head' },
        h(
          'div',
          { class: 'home__brand' },
          logoMark(64),
          h('h1', { class: 'home__title' }, t('app.title')),
        ),
        h('p', { class: 'home__tagline' }, t('app.tagline')),
        h('p', { class: 'home__pitch' }, t('home.pitch')),
      ),
      picker,
      contractPicker,
      h('ol', { class: 'home__steps', 'aria-label': t('onboarding.title') }, ...steps),
      h(
        'div',
        { class: 'screen__actions' },
        message,
        dailyBtn,
        dailyNote,
        endlessBtn,
        mysteryBtn,
        h('p', { class: 'muted home__mystery-note' }, t('home.mysteryNote')),
        installSlot,
        bestSlot,
      ),
      h(
        'section',
        { class: 'home__legend', 'aria-label': t('home.dayTypes') },
        h('h2', { class: 'home__legend-title' }, t('home.dayTypes')),
        h(
          'div',
          { class: 'home__chips' },
          chip({ label: t('home.dayPerfect'), swatch: 'p' }),
          chip({ label: t('home.dayOk'), swatch: 'o' }),
          chip({ label: t('home.dayRain'), swatch: 'r' }),
          chip({ label: t('home.dayStorm'), swatch: 's' }),
          chip({ label: t('home.dayHeat'), swatch: 'h' }),
          chip({ label: t('home.dayFreeze'), swatch: 'f' }),
        ),
        h('p', { class: 'muted home__facts' }, t('home.facts', { cities: cities.length })),
      ),
      h(
        'nav',
        { class: 'home__links', 'aria-label': t('home.settings') },
        button({
          label: t('home.settings'),
          variant: 'quiet',
          icon: 'settings',
          onClick: () => {
            app.go('settings');
          },
        }),
        button({
          label: t('home.stats'),
          variant: 'quiet',
          icon: 'stats',
          onClick: () => {
            app.go('stats');
          },
        }),
        button({
          label: t('home.howItWorks'),
          variant: 'quiet',
          icon: 'info',
          onClick: () => {
            app.go('how');
          },
        }),
      ),
    ),
  );
  applyChase();
  app.onLeave(onInstallChange(drawInstall));
  prefetchWorld();
}
