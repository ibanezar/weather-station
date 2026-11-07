// Haptics and sound. Both are settings; sound is off by default.
import type { Settings } from './storage.ts';

export type HapticKind = 'light' | 'medium' | 'success';

const PATTERNS: Record<HapticKind, number | number[]> = {
  light: 10,
  medium: 20,
  success: [20, 40, 30],
};

export type SoundKind = 'pick' | 'scout' | 'done';

let audio: AudioContext | undefined;

function beep(freq: number, start: number, length: number, gain = 0.06): void {
  if (!audio) return;
  const osc = audio.createOscillator();
  const amp = audio.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq;
  amp.gain.setValueAtTime(0, audio.currentTime + start);
  amp.gain.linearRampToValueAtTime(gain, audio.currentTime + start + 0.01);
  amp.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + start + length);
  osc.connect(amp).connect(audio.destination);
  osc.start(audio.currentTime + start);
  osc.stop(audio.currentTime + start + length + 0.02);
}

export interface Feedback {
  haptic: (kind: HapticKind) => void;
  sound: (kind: SoundKind) => void;
}

export function createFeedback(getSettings: () => Pick<Settings, 'haptics' | 'sound'>): Feedback {
  return {
    haptic(kind) {
      if (!getSettings().haptics) return;
      try {
        navigator.vibrate(PATTERNS[kind]);
      } catch {
        // Not supported (iOS Safari, desktop): silently skip.
      }
    },
    sound(kind) {
      if (!getSettings().sound) return;
      try {
        audio ??= new AudioContext();
        if (kind === 'pick') beep(520, 0, 0.09);
        else if (kind === 'scout') beep(660, 0, 0.08);
        else {
          beep(523, 0, 0.18);
          beep(659, 0.12, 0.18);
          beep(784, 0.24, 0.28);
        }
      } catch {
        // No audio available.
      }
    },
  };
}
