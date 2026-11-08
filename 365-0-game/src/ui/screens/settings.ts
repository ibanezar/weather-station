import type { App } from '../../app/app.ts';
import { canInstall, onInstallChange, promptInstall } from '../../app/install.ts';
import type { Unit } from '../../app/storage.ts';
import type { Locale, MessageKey } from '../../i18n/index.ts';
import type { MotionSetting, PatternSetting, ThemeSetting } from '../settings.ts';
import { backButton } from '../components/backButton.ts';
import { button } from '../components/button.ts';
import { confirmDialog } from '../components/confirm.ts';
import { segmented } from '../components/segmented.ts';
import { toggle } from '../components/toggle.ts';
import { showToast } from '../components/toast.ts';
import { h, mount } from '../dom.ts';

function row(label: string, control: HTMLElement, hint?: string): HTMLElement {
  const id = `row-${label.toLowerCase().replace(/\W+/g, '-')}`;
  return h(
    'div',
    { class: 'settings__row' },
    h('span', { class: 'settings__label', id }, label),
    control,
    hint ? h('p', { class: 'muted settings__hint' }, hint) : null,
  );
}

export function renderSettings(app: App, root: HTMLElement): void {
  const { t } = app.i18n;
  const s = app.store.state.settings;
  const change = (apply: () => void): void => {
    app.store.update(() => {
      apply();
    });
    app.applySettings();
    app.render();
  };
  const key = (k: string): MessageKey => k as MessageKey;

  mount(
    root,
    h(
      'main',
      { class: 'screen' },
      backButton(t('settings.back'), () => {
        app.go('home');
      }),
      h('h1', null, t('settings.title')),
      h(
        'div',
        { class: 'settings' },
        row(
          t('settings.units'),
          segmented<Unit>(
            t('settings.units'),
            [
              { value: 'c', label: t('settings.units.c') },
              { value: 'f', label: t('settings.units.f') },
            ],
            s.unit,
            (v) => {
              change(() => {
                s.unit = v;
              });
            },
          ),
        ),
        row(
          t('settings.language'),
          segmented<Locale>(
            t('settings.language'),
            [
              { value: 'en', label: t('settings.language.en') },
              { value: 'sl', label: t('settings.language.sl') },
            ],
            s.language,
            (v) => {
              change(() => {
                s.language = v;
              });
            },
          ),
        ),
        row(
          t('settings.theme'),
          segmented<ThemeSetting>(
            t('settings.theme'),
            (['system', 'light', 'dark'] as const).map((v) => ({
              value: v,
              label: t(key(`settings.theme.${v}`)),
            })),
            s.theme,
            (v) => {
              change(() => {
                s.theme = v;
              });
            },
          ),
        ),
        row(
          t('settings.motion'),
          segmented<MotionSetting>(
            t('settings.motion'),
            (['system', 'reduce', 'full'] as const).map((v) => ({
              value: v,
              label: t(key(`settings.motion.${v}`)),
            })),
            s.motion,
            (v) => {
              change(() => {
                s.motion = v;
              });
            },
          ),
        ),
        row(
          t('settings.pattern'),
          segmented<PatternSetting>(
            t('settings.pattern'),
            (['auto', 'on', 'off'] as const).map((v) => ({
              value: v,
              label: t(key(`settings.pattern.${v}`)),
            })),
            s.pattern,
            (v) => {
              change(() => {
                s.pattern = v;
              });
            },
          ),
          t('settings.pattern.hint'),
        ),
        toggle(t('settings.haptics'), s.haptics, t('settings.on'), t('settings.off'), (v) => {
          app.store.update(() => {
            s.haptics = v;
          });
          if (v) app.feedback.haptic('light');
        }),
        toggle(t('settings.sound'), s.sound, t('settings.on'), t('settings.off'), (v) => {
          app.store.update(() => {
            s.sound = v;
          });
          if (v) app.feedback.sound('pick');
        }),
        toggle(t('settings.counts'), s.counts, t('settings.on'), t('settings.off'), (v) => {
          app.store.update(() => {
            s.counts = v;
          });
        }),
        h('p', { class: 'muted settings__hint' }, t('settings.counts.hint')),
      ),
      h(
        'nav',
        { class: 'settings__links', 'aria-label': t('settings.data') },
        button({
          label: t('settings.howItWorks'),
          variant: 'secondary',
          icon: 'info',
          full: true,
          onClick: () => {
            app.go('how');
          },
        }),
        button({
          label: t('settings.about'),
          variant: 'secondary',
          full: true,
          onClick: () => {
            app.go('about');
          },
        }),
        button({
          label: t('settings.privacy'),
          variant: 'secondary',
          full: true,
          onClick: () => {
            app.go('privacy');
          },
        }),
      ),
      canInstall()
        ? h(
            'div',
            { class: 'settings__install' },
            button({
              label: t('settings.install'),
              variant: 'secondary',
              full: true,
              onClick: () => {
                void promptInstall();
              },
            }),
            h('p', { class: 'muted settings__hint' }, t('settings.installHint')),
          )
        : null,
      h('p', { class: 'muted settings__attribution' }, t('about.attribution')),
      button({
        label: t('settings.reset'),
        variant: 'quiet',
        onClick: () => {
          confirmDialog({
            title: t('settings.reset'),
            body: t('settings.resetBody'),
            confirmLabel: t('settings.resetConfirm'),
            cancelLabel: t('settings.resetCancel'),
            onConfirm: () => {
              app.store.resetProgress();
              showToast({ message: t('settings.resetDone') });
            },
          });
        },
      }),
    ),
  );
  // The browser may offer installation after the page has loaded: show the button when it does.
  app.onLeave(
    onInstallChange(() => {
      if (app.route === 'settings') app.render();
    }),
  );
}
