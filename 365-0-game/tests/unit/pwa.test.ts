import { Script } from 'node:vm';
import { describe, expect, it } from 'vitest';
import { buildServiceWorker, SW_TEMPLATE } from '../../scripts/vite-pwa.ts';

describe('service worker generation', () => {
  const precache = ['./index.html', './assets/index-abc.js', './data/world.v1.json'];
  const sw = buildServiceWorker(precache, 'v123456789abc');

  it('fills in the version and the precache list', () => {
    expect(sw).toContain("const VERSION = 'v123456789abc';");
    expect(sw).not.toContain('__VERSION__');
    expect(sw).not.toContain('__PRECACHE__');
    for (const file of precache) expect(sw).toContain(file);
  });

  it('is valid JavaScript with the three lifecycle handlers', () => {
    expect(() => new Script(sw)).not.toThrow();
    for (const event of ['install', 'activate', 'fetch']) {
      expect(sw).toContain(`addEventListener('${event}'`);
    }
  });

  it('only handles same-origin GET requests and serves the app shell for page loads', () => {
    expect(SW_TEMPLATE).toContain("request.method !== 'GET'");
    expect(SW_TEMPLATE).toContain('origin !== self.location.origin');
    expect(SW_TEMPLATE).toContain("request.mode === 'navigate'");
    expect(SW_TEMPLATE).toContain("caches.match('./index.html'");
    expect(SW_TEMPLATE).toContain('ignoreVary: true');
  });

  it('removes old caches of this app only, and takes control of open pages', () => {
    expect(SW_TEMPLATE).toContain("k.startsWith('365-0-')");
    expect(SW_TEMPLATE).toContain('clients.claim()');
  });

  it('gives a different cache name for a different version', () => {
    expect(buildServiceWorker(precache, 'aaa')).not.toBe(buildServiceWorker(precache, 'bbb'));
  });
});
